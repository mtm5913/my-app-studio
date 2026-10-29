"""APP-002 acceptance: valid accounts, rejected requests, and real session state."""

import re

from fastapi.testclient import TestClient
from app import database
from app.main import create_app

PASSWORD = "a disposable test password"


def csrf(client):
    """Get a token through the same public endpoint as a same-origin API client."""
    response = client.get("/api/csrf")
    assert response.status_code == 200, "Implement APP-002 before running its contract."
    assert response.headers["cache-control"] == "no-store"
    return {"X-CSRF-Token": response.json()["csrf_token"]}


def credentials():
    """Use disposable credentials; no real student or hosted account is involved."""
    return {"username": "learner", "password": PASSWORD}


def register(client):
    """Create a member through the actual signup endpoint."""
    response = client.post("/api/signup", json=credentials(), headers=csrf(client))
    assert response.status_code == 201
    return response


def login(client):
    """Authenticate through the actual endpoint and its CSRF requirement."""
    response = client.post("/api/login", json=credentials(), headers=csrf(client))
    assert response.status_code == 200
    return response


def test_valid_signup_is_a_member_and_stores_a_hash(client, settings):
    """Signup supplies identity, not administrative privileges."""
    response = register(client)
    assert set(response.json()) == {"id", "username", "role"}
    assert response.json()["role"] == "member"
    assert PASSWORD not in response.text
    with database.connect(settings) as connection:
        row = connection.execute("SELECT * FROM users").fetchone()
    assert row["password_hash"].startswith("$argon2id$")
    assert row["password_hash"] != PASSWORD


def test_duplicate_username_and_invalid_signup_do_not_add_accounts(client, settings):
    """Unique normalized usernames, length limits, and role-injection rejection."""
    register(client)
    duplicate = {**credentials(), "username": "LEARNER"}
    assert (
        client.post("/api/signup", json=duplicate, headers=csrf(client)).status_code
        == 409
    )
    for invalid in (
        {**credentials(), "username": "a"},
        {**credentials(), "password": "short"},
        {**credentials(), "password": "x" * 129},
        {**credentials(), "role": "admin"},
    ):
        response = client.post("/api/signup", json=invalid, headers=csrf(client))
        assert response.status_code == 422
        assert PASSWORD not in response.text
        assert "password_hash" not in response.text
    with database.connect(settings) as connection:
        assert connection.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1


def test_login_authenticates_but_does_not_return_a_token_in_json(client, settings):
    """The browser receives HttpOnly state while API output remains public identity."""
    assert client.get("/api/me").status_code == 401
    register(client)
    response = login(client)
    assert set(response.json()) == {"id", "username", "role"}
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie
    assert "domain=" not in cookie
    assert client.cookies.get(settings.cookie_name)
    me = client.get("/api/me")
    assert me.status_code == 200
    assert me.json()["username"] == "learner"
    assert set(me.json()) == {"id", "username", "role"}


def test_login_failures_are_generic_and_throttled(client):
    """Wrong passwords and unknown accounts do not disclose different errors."""
    register(client)
    wrong = client.post(
        "/api/login", json={**credentials(), "password": "wrong"}, headers=csrf(client)
    )
    unknown = client.post(
        "/api/login",
        json={"username": "missing", "password": "wrong"},
        headers=csrf(client),
    )
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()
    for _ in range(4):
        assert (
            client.post(
                "/api/login",
                json={"username": "missing", "password": "wrong"},
                headers=csrf(client),
            ).status_code
            == 401
        )
    limited = client.post(
        "/api/login",
        json={"username": "missing", "password": "wrong"},
        headers=csrf(client),
    )
    assert limited.status_code == 429
    assert int(limited.headers["retry-after"]) > 0


def test_signup_throttles_before_unbounded_password_hashing(client):
    """The prepared signup guard persists across fresh browser sessions."""
    for number in range(10):
        response = client.post(
            "/api/signup",
            json={"username": f"member_{number}", "password": PASSWORD},
            headers=csrf(client),
        )
        assert response.status_code == 201
    client.cookies.clear()
    response = client.post(
        "/api/signup",
        json={"username": "another_member", "password": PASSWORD},
        headers=csrf(client),
    )
    assert response.status_code == 429


def test_csrf_is_required_and_rotated_at_login(client):
    """Protect unauthenticated forms as well as authenticated state changes."""
    before = csrf(client)
    assert client.post("/api/signup", json=credentials()).status_code == 403
    assert (
        client.post(
            "/api/signup", json=credentials(), headers={"X-CSRF-Token": "wrong"}
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/signup",
            json=credentials(),
            headers={**before, "Origin": "https://attacker.example"},
        ).status_code
        == 403
    )
    assert (
        client.post("/api/signup", json=credentials(), headers=before).status_code
        == 201
    )
    assert client.post("/api/login", json=credentials()).status_code == 403
    assert (
        client.post("/api/login", json=credentials(), headers=before).status_code == 200
    )
    assert client.post("/api/logout", headers=before).status_code == 403
    assert csrf(client) != before


def test_logout_revokes_a_copied_token_and_get_does_not_log_out(client, settings):
    """Prove server revocation rather than only deleting a cookie in one browser."""
    register(client)
    login(client)
    copied = client.cookies.get(settings.cookie_name)
    assert client.get("/api/logout").status_code == 405
    assert client.get("/api/me").status_code == 200
    assert client.post("/api/logout", headers=csrf(client)).status_code == 200
    assert not client.cookies.get(settings.cookie_name)
    client.cookies.set(settings.cookie_name, copied)
    assert client.get("/api/me").status_code == 401


def test_accounts_survive_an_app_restart(client, settings):
    """A separate app instance uses the same database, not a process-local user list."""
    register(client)
    with TestClient(create_app(settings), base_url=settings.origin) as restarted:
        login(restarted)
        assert restarted.get("/api/me").json()["username"] == "learner"


def test_unicode_csrf_form_values_are_rejected_without_mutation(client, settings):
    """Actual HTML handlers should recover from malformed tokens rather than 500."""
    assert client.get("/signup").status_code == 200
    response = client.post(
        "/signup", data={**credentials(), "csrf_token": "é"}, follow_redirects=False
    )
    assert response.status_code == 403
    with database.connect(settings) as connection:
        assert connection.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0
    register(client)
    response = client.post(
        "/login", data={**credentials(), "csrf_token": "é"}, follow_redirects=False
    )
    assert response.status_code == 403
    assert client.get("/api/me").status_code == 401


def test_wrong_html_login_retains_only_the_validated_username(client):
    """A password mistake should not require retyping a valid username."""
    register(client)
    form = client.get("/login")
    token = re.search(r'name="csrf_token" value="([^"]+)"', form.text).group(1)
    wrong_password = "a deliberately wrong password"
    response = client.post(
        "/login",
        data={
            "username": " LEARNER ",
            "password": wrong_password,
            "csrf_token": token,
        },
    )
    assert response.status_code == 401
    username = re.search(r'<input[^>]*name="username"[^>]*>', response.text).group(0)
    password = re.search(r'<input[^>]*name="password"[^>]*>', response.text).group(0)
    assert 'value="learner"' in username
    assert "value=" not in password
    assert wrong_password not in response.text
    assert PASSWORD not in response.text
    assert client.get("/api/me").status_code == 401


def test_duplicate_html_signup_retains_username_without_password(client):
    """An unavailable username error keeps only the validated, normalized identity."""
    register(client)
    form = client.get("/signup")
    token = re.search(r'name="csrf_token" value="([^"]+)"', form.text).group(1)
    response = client.post(
        "/signup",
        data={**credentials(), "username": "LEARNER", "csrf_token": token},
    )
    assert response.status_code == 409
    username = re.search(r'<input[^>]*name="username"[^>]*>', response.text).group(0)
    password = re.search(r'<input[^>]*name="password"[^>]*>', response.text).group(0)
    assert 'value="learner"' in username
    assert "value=" not in password
    assert PASSWORD not in response.text


def test_browser_forms_have_a_recoverable_signup_login_logout_path(client):
    """HTML navigation reaches the same guarded services as the JSON endpoints."""
    assert (
        client.get("/dashboard", follow_redirects=False).headers["location"] == "/login"
    )
    signup = client.get("/signup")
    assert signup.status_code == 200
    token = re.search(r'name="csrf_token" value="([^"]+)"', signup.text).group(1)
    response = client.post(
        "/signup", data={**credentials(), "csrf_token": token}, follow_redirects=False
    )
    assert response.status_code == 303
    form = client.get(response.headers["location"])
    token = re.search(r'name="csrf_token" value="([^"]+)"', form.text).group(1)
    response = client.post(
        "/login", data={**credentials(), "csrf_token": token}, follow_redirects=False
    )
    assert response.status_code == 303 and response.headers["location"] == "/dashboard"
    dashboard = client.get("/dashboard")
    assert dashboard.status_code == 200 and "learner" in dashboard.text
    token = re.search(r'name="csrf_token" value="([^"]+)"', dashboard.text).group(1)
    assert (
        client.post(
            "/logout", data={"csrf_token": token}, follow_redirects=False
        ).status_code
        == 303
    )
    assert client.get("/dashboard", follow_redirects=False).status_code == 303
