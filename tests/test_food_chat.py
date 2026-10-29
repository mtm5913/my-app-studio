"""Paid requests are mocked; verify consent, boundaries and safe provider output."""

from unittest.mock import patch

import httpx
import pytest

from app import database, food_ai
from contracts.test_roles import member


def payload(**changes):
    """A general food question has no member identity or record context."""
    return {
        "question": "How can I cook beans?",
        "search": False,
        "share_question": True,
        **changes,
    }


def headers(client):
    """Use the real current session's CSRF token."""
    return {"X-CSRF-Token": client.get("/api/csrf").json()["csrf_token"]}


def test_guests_cannot_access_paid_feature(client):
    response = client.get("/ask", follow_redirects=False)
    assert response.headers["location"] == "/login?next=%2Fask"
    with patch("app.food_ai.ask") as provider:
        assert (
            client.post(
                "/api/food-chat", json=payload(), headers=headers(client)
            ).status_code
            == 401
        )
        provider.assert_not_called()


def test_missing_key_and_csrf_do_not_call_provider(client):
    member(client)
    with (
        patch("app.food_ai.AIConfig.load", return_value=food_ai.AIConfig(key="")),
        patch("app.food_ai.ask") as provider,
    ):
        assert client.post("/api/food-chat", json=payload()).status_code == 403
        assert (
            client.post(
                "/api/food-chat", json=payload(), headers=headers(client)
            ).status_code
            == 503
        )
        assert "isn’t connected yet" in client.get("/ask").text
        provider.assert_not_called()


@pytest.mark.parametrize(
    "change",
    [
        {"share_question": False},
        {"question": "  "},
        {"question": "a" * 1201},
        {"model": "injected"},
    ],
)
def test_invalid_or_unconsented_requests_never_call_provider(client, change):
    member(client)
    with patch("app.food_ai.ask") as provider:
        assert (
            client.post(
                "/api/food-chat", json=payload(**change), headers=headers(client)
            ).status_code
            == 422
        )
        provider.assert_not_called()


def test_only_question_and_search_pass_to_provider_and_limit_persists(client, settings):
    member(client)
    config = food_ai.AIConfig(key="test-only-not-real")
    result = {"answer": "Try adding beans to soup.", "sources": []}
    with (
        patch("app.food_ai.AIConfig.load", return_value=config),
        patch("app.food_ai.ask", return_value=result) as provider,
    ):
        for _ in range(10):
            assert (
                client.post(
                    "/api/food-chat", json=payload(), headers=headers(client)
                ).json()
                == result
            )
        provider.assert_called_with(config, "How can I cook beans?", False)
        assert (
            client.post(
                "/api/food-chat", json=payload(), headers=headers(client)
            ).status_code
            == 429
        )
        assert provider.call_count == 10
    with database.connect(settings) as connection:
        assert connection.execute("SELECT attempts FROM ai_usage").fetchone()[0] == 10


def test_form_answer_is_escaped_and_provider_errors_are_generic(client):
    member(client)
    config = food_ai.AIConfig(key="test-only-not-real")
    with (
        patch("app.food_ai.AIConfig.load", return_value=config),
        patch(
            "app.food_ai.ask",
            return_value={"answer": "<script>alert(1)</script>", "sources": []},
        ),
    ):
        csrf = client.get("/api/csrf").json()["csrf_token"]
        response = client.post("/ask", data={**payload(), "csrf_token": csrf})
        assert response.status_code == 200
        assert "&lt;script&gt;" in response.text
        assert "<script>alert(1)</script>" not in response.text


def test_request_contract_and_search_citations():
    recorded = []

    def respond(request):
        import json

        recorded.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": "Beans contain fiber.",
                                "annotations": [
                                    {
                                        "type": "url_citation",
                                        "url": "https://www.usda.gov/",
                                        "title": "USDA",
                                    },
                                    {
                                        "type": "url_citation",
                                        "url": "javascript:alert(1)",
                                        "title": "Unsafe",
                                    },
                                ],
                            }
                        ],
                    }
                ],
            },
        )

    original_client = httpx.Client
    with patch(
        "app.food_ai.httpx.Client",
        side_effect=lambda **kwargs: original_client(
            transport=httpx.MockTransport(respond), **kwargs
        ),
    ):
        result = food_ai.ask(
            food_ai.AIConfig(key="test-only"), "Tell me about beans", True
        )
    assert recorded[0]["store"] is False
    assert recorded[0]["max_output_tokens"] == 700
    assert recorded[0]["tools"][0]["type"] == "web_search"
    assert "filters" not in recorded[0]["tools"][0]
    assert result["sources"] == [{"url": "https://www.usda.gov/", "title": "USDA"}]


def test_provider_failure_never_exposes_secrets():
    with patch(
        "app.food_ai.httpx.Client.post",
        side_effect=httpx.ConnectError("secret content"),
    ):
        with pytest.raises(Exception) as failure:
            food_ai.ask(food_ai.AIConfig(key="secret-key"), "Food question", False)
    assert failure.value.status_code == 503
    assert "secret" not in failure.value.detail
