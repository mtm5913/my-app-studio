"""Member-only food questions with CSRF, explicit sharing and persistent limits."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app import database, food_ai, security
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
