"""APP-003 acceptance: server authorization works even when URLs are typed directly."""

import jwt

from app import database


def member(client):
    """Create a disposable member through the account feature's public API."""
    credentials = {"username": "learner", "password": "a disposable test password"}
    token = client.get("/api/csrf")
    assert token.status_code == 200, "Finish APP-002 before APP-003."
    headers = {"X-CSRF-Token": token.json()["csrf_token"]}
    assert (
        client.post("/api/signup", json=credentials, headers=headers).status_code == 201
    )
    assert (
        client.post("/api/login", json=credentials, headers=headers).status_code == 200
    )


def test_anonymous_is_401_and_html_redirects_to_login(client):
    """The absence of a menu link is never an authorization control."""
    assert client.get("/api/admin").status_code == 401
    response = client.get("/admin", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_member_is_403_for_api_and_direct_page(client):
    """Logged in is different from permitted to administer the app."""
    member(client)
    assert client.get("/api/me").json()["role"] == "member"
    assert client.get("/api/admin").status_code == 403
    assert client.get("/admin").status_code == 403


def test_trusted_role_change_applies_to_the_existing_session(client, settings):
    """Promotion and downgrade are read from the database on each request."""
    member(client)
    assert database.set_role(settings, "learner", "admin")
    assert client.get("/api/admin").status_code == 200
    assert client.get("/admin").status_code == 200
    assert client.get("/api/me").json()["role"] == "admin"
    assert database.set_role(settings, "learner", "member")
    assert client.get("/api/admin").status_code == 403
    assert client.get("/admin").status_code == 403


def test_a_role_claim_cannot_override_the_current_database_role(client, settings):
    """Even a stale legitimate role claim must never be used for permission checks."""
    member(client)
    token = client.cookies.get(settings.cookie_name)
    claims = jwt.decode(token, options={"verify_signature": False})
    claims["role"] = "admin"
    altered = jwt.encode(
        claims,
        settings.secret,
        algorithm="HS256",
        headers={"typ": jwt.get_unverified_header(token)["typ"]},
    )
    client.cookies.set(settings.cookie_name, altered)
    assert client.get("/api/admin").status_code == 403
    assert client.get("/api/me").json()["role"] == "member"
