"""Learner-chosen return paths stay useful without becoming open redirects."""

import re

import pytest

from app import database

PASSWORD = "a disposable navigation passphrase"


def form_token(client, path):
    """Read CSRF through the public form, just as a browser does."""
    page = client.get(path)
    assert page.status_code == 200
    return re.search(r'name="csrf_token" value="([^"]+)"', page.text).group(1)


def create_member(client):
    """Create a disposable member using guarded JSON signup."""
    token = client.get("/api/csrf").json()["csrf_token"]
    response = client.post(
        "/api/signup",
        json={"username": "navigation_member", "password": PASSWORD},
        headers={"X-CSRF-Token": token},
    )
    assert response.status_code == 201


def test_public_preview_cannot_expose_member_identity(client):
    """A sample page is public; the real page and identity endpoint stay guarded."""
    response = client.get("/preview")
    assert response.status_code == 200
    assert "sample content only" in response.text
    assert 'href="/dashboard"' in response.text
    assert client.get("/api/me").status_code == 401
    private = client.get("/dashboard", follow_redirects=False)
    assert private.status_code == 303
    assert private.headers["location"] == "/login?next=%2Fdashboard"
    assert "Welcome," not in private.text


@pytest.mark.parametrize("target", ["/", "/dashboard"])
def test_login_destination_and_errors_preserve_only_safe_intent(client, target):
    """Standalone login returns home, while requested member access resumes."""
    create_member(client)
    token = form_token(client, "/login")
    fields = {
        "username": "navigation_member",
        "password": "wrong",
        "next": target,
        "csrf_token": token,
    }
    failure = client.post("/login", data=fields)
    assert failure.status_code == 401
    assert f'name="next" value="{target}"' in failure.text
    response = client.post(
        "/login", data={**fields, "password": PASSWORD}, follow_redirects=False
    )
    assert response.status_code == 303
    assert response.headers["location"] == target
    assert client.get("/api/me").status_code == 200


@pytest.mark.parametrize(
    "target",
    [
        "https://evil.example",
        "//evil.example",
        "/\\evil.example",
        "/admin",
        "/dashboard?x=1",
        "/dashboard#x",
        "%2F%2Fevil.example",
    ],
)
def test_untrusted_return_paths_fall_back_to_home(client, target):
    """Neither query nor hidden fields can redirect a login off-site."""
    create_member(client)
    page = client.get("/login", params={"next": target})
    assert 'name="next" value="/"' in page.text
    token = form_token(client, "/login")
    response = client.post(
        "/login",
        data={
            "username": "navigation_member",
            "password": PASSWORD,
            "next": target,
            "csrf_token": token,
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/"


def test_signup_keeps_requested_destination_until_login(client):
    """New visitors retain the requested member-space action across registration."""
    token = form_token(client, "/signup?next=%2Fdashboard")
    signup = client.post(
        "/signup",
        data={
            "username": "new_member",
            "password": PASSWORD,
            "next": "/dashboard",
            "csrf_token": token,
        },
        follow_redirects=False,
    )
    assert signup.status_code == 303
    assert signup.headers["location"] == "/login?next=%2Fdashboard"
    assert client.get("/api/me").status_code == 401
    token = form_token(client, signup.headers["location"])
    login = client.post(
        "/login",
        data={
            "username": "new_member",
            "password": PASSWORD,
            "next": "/dashboard",
            "csrf_token": token,
        },
        follow_redirects=False,
    )
    assert login.headers["location"] == "/dashboard"


def test_expired_session_cannot_open_private_page(client, settings):
    """The integrated route still enforces prepared server-side expiry."""
    create_member(client)
    token = form_token(client, "/login")
    client.post(
        "/login",
        data={
            "username": "navigation_member",
            "password": PASSWORD,
            "csrf_token": token,
        },
    )
    with database.connect(settings) as connection:
        connection.execute("UPDATE sessions SET expires_at = 0")
    assert client.get("/api/me").status_code == 401
    assert client.get("/dashboard", follow_redirects=False).status_code == 303
