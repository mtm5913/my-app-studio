"""Member-only food questions with CSRF, explicit sharing and persistent limits."""

from datetime import datetime, timezone
import json
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse, StreamingResponse
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app import database, food_ai, retrieval, security
from app.features.accounts import account_url, api_csrf, render

router = APIRouter()


class FoodQuestion(BaseModel):
    """The client cannot send system prompts, models or account/record context."""

    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=3, max_length=1200, strict=True)
    search: bool = False
    share_question: bool

    @field_validator("question")
    @classmethod
    def trim_question(cls, value):
        """Whitespace alone is not a question."""
        if len(value.strip()) < 3:
            raise ValueError("Write a food question of at least three characters.")
        return value.strip()


def reserve_request(request, user):
    """Count attempts atomically across workers; no questions enter the database."""
    day = datetime.now(timezone.utc).date().isoformat()
    with database.connect(request.app.state.settings) as connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("DELETE FROM ai_usage WHERE day != ?", (day,))
        count = connection.execute(
            "SELECT COALESCE(SUM(attempts), 0) FROM ai_usage WHERE day = ?", (day,)
        ).fetchone()[0]
        own = connection.execute(
            "SELECT attempts FROM ai_usage WHERE day = ? AND user_id = ?",
            (day, user["id"]),
        ).fetchone()
        if count >= 100 or (own and own[0] >= 10):
            raise HTTPException(
                429,
                "Today's question limit has been reached. Please come back tomorrow.",
            )
        connection.execute(
            "INSERT INTO ai_usage(day, user_id, attempts) VALUES (?, ?, 1) "
            "ON CONFLICT(day, user_id) DO UPDATE SET attempts = attempts + 1",
            (day, user["id"]),
        )


def answer_question(request, user, question):
    """Both forms and API requests share consent, configuration and limits."""
    if not question.share_question:
        raise HTTPException(
            422, "Please agree to send this question to OpenAI before asking."
        )
    config = food_ai.AIConfig.load()
    if not config.key:
        raise HTTPException(
            503,
            "Ask Olive isn't connected yet. The project owner needs to add an API key.",
        )
    reserve_request(request, user)
    return food_ai.ask(config, question.question, question.search)


@router.get("/ask", include_in_schema=False)
def chat_page(request: Request):
    """A public link never grants access to paid requests."""
    if not security.authenticate(request):
        return RedirectResponse(account_url("/login", "/ask"), status_code=303)
    return render(
        request,
        "ask.html",
        connected=bool(food_ai.AIConfig.load().key),
        result=None,
        error=None,
    )


@router.post("/api/food-chat", dependencies=[Depends(api_csrf)])
def chat_api(
    request: Request, question: FoodQuestion, user=Depends(security.require_user)
):
    """Bounded authenticated JSON equivalent of the member form."""
    return answer_question(request, user, question)


@router.post("/ask", include_in_schema=False)
async def chat_form(request: Request):
    """Require the existing session and CSRF before making a paid call."""
    user = security.require_user(request)
    form = dict(await request.form(max_fields=4, max_files=0))
    security.require_csrf(request, form.pop("csrf_token", None))
    result, error, status = None, None, 200
    try:
        question = FoodQuestion.model_validate(form)
        result = await run_in_threadpool(answer_question, request, user, question)
    except ValidationError:
        error, status = (
            "Write a question (3–1200 characters) and agree to send it to OpenAI.",
            422,
        )
    except HTTPException as failure:
        error, status = failure.detail, failure.status_code
    return render(
        request,
        "ask.html",
        status=status,
        connected=bool(food_ai.AIConfig.load().key),
        result=result,
        error=error,
    )


class ChatMessage(BaseModel):
    """Conversation is request data, never privileged instructions."""

    model_config = ConfigDict(extra="forbid")
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000, strict=True)


class GroundedQuestion(BaseModel):
    """Bound conversation size and accept only the two public message roles."""

    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=3, max_length=1200, strict=True)
    share_question: bool
    history: list[ChatMessage] = Field(default_factory=list, max_length=6)

    @field_validator("question")
    @classmethod
    def trim_question(cls, value):
        """Reject blank questions before retrieval or a paid request."""
        return FoodQuestion.trim_question(value)

    @field_validator("history")
    @classmethod
    def valid_history(cls, value):
        """Only complete alternating pairs fit the current short conversation."""
        if len(value) % 2 or sum(len(m.content) for m in value) > 12000:
            raise ValueError("Start a new chat or shorten the conversation.")
        if any(
            m.role != ("user" if i % 2 == 0 else "assistant")
            for i, m in enumerate(value)
        ):
            raise ValueError("Conversation messages must alternate user and assistant.")
        return value


def stream_event(event):
    """One JSON object per line; escaping protects the framing boundary."""
    return json.dumps(event, ensure_ascii=False) + "\n"


@router.post("/api/food-chat/stream", dependencies=[Depends(api_csrf)])
async def grounded_chat(
    request: Request, question: GroundedQuestion, user=Depends(security.require_user)
):
    """Retrieve before generation and stream progress without server chat storage."""
    if not question.share_question:
        raise HTTPException(422, "Please agree to send this conversation to OpenAI.")
    history = [message.model_dump() for message in question.history]
    passages = retrieval.retrieve(question.question, history)
    config = food_ai.AIConfig.load()
    if passages and not config.key:
        raise HTTPException(
            503,
            "Ask Olive isn't connected yet. "
            "Please ask the project owner to check the API key.",
        )
    reserve_request(request, user)

    async def events():
        yield stream_event({"type": "sources", "sources": retrieval.sources(passages)})
        if not passages:
            yield stream_event({"type": "delta", "text": retrieval.REFUSAL})
            yield stream_event({"type": "done", "grounded": False})
            return
        async for event in food_ai.stream_grounded(
            config, question.question, history, passages
        ):
            if await request.is_disconnected():
                return
            yield stream_event(event)

    return StreamingResponse(
        events(),
        media_type="application/x-ndjson",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-store"},
    )
