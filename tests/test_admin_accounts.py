"""The agreed admin overview exposes only usernames and current roles."""

from app import database
from contracts.test_roles import member


def test_overview_fields_and_navigation_follow_current_role(client, settings):
    """An existing session gains and loses both the list and its navigation."""
    member(client)
    assert 'href="/admin"' not in client.get("/dashboard").text
    assert database.set_role(settings, "learner", "admin")
    assert client.get("/api/admin").json() == {
        "users": [{"username": "learner", "role": "admin"}]
    }
    page = client.get("/admin")
    assert page.status_code == 200
    assert "Accounts and permissions" in page.text
    assert 'href="/admin"' in page.text
    assert "password_hash" not in page.text
    assert database.set_role(settings, "learner", "member")
    denied = client.get("/admin")
    assert denied.status_code == 403
    assert "Accounts and permissions" not in denied.text
    assert 'href="/admin"' not in denied.text
