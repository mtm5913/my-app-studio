"""Prepared authentication primitives, separate from the student's feature routes."""

import secrets
import sqlite3
import time
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, Request, Response
import jwt
from jwt import InvalidTokenError
from pwdlib import PasswordHash

from app.database import connect
from app.schemas import SignupInput
from app.settings import Settings

PASSWORD_HASH = PasswordHash.recommended()
DUMMY_HASH = PASSWORD_HASH.hash("not-an-account: constant-time unknown-user comparison")
AUDIENCE = "is373-app-studio"
TOKEN_TYPE = "studio-session+jwt"
ATTEMPT_WINDOW = 300


def hash_password(password: str) -> str:
    """Argon2id creates its own random salt; never save the plaintext."""
    return PASSWORD_HASH.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Compare with the library's verifier, including the dummy unknown-user path."""
    return PASSWORD_HASH.verify(password, password_hash)


def _settings(request: Request) -> Settings:
    return request.app.state.settings


def _now() -> int:
    return int(time.time())


def _session_row(settings: Settings, session_id: str) -> sqlite3.Row | None:
    with connect(settings) as connection:
        return connection.execute(
            "SELECT * FROM sessions WHERE id = ? AND revoked = 0 AND expires_at > ?",
            (session_id, _now()),
        ).fetchone()


def _claims(settings: Settings, token: str) -> dict[str, Any] | None:
    try:
        if jwt.get_unverified_header(token).get("typ") != TOKEN_TYPE:
            return None
        claims = jwt.decode(
            token,
            settings.secret,
            algorithms=["HS256"],
            audience=AUDIENCE,
            issuer=settings.origin,
            options={"require": ["sub", "jti", "iat", "exp", "iss", "aud"]},
        )
        if not isinstance(claims["sub"], str) or not isinstance(claims["jti"], str):
            return None
        return claims
    except (InvalidTokenError, ValueError, TypeError, KeyError):
        return None


def authenticate(request: Request) -> dict[str, str] | None:
    """A signature alone is insufficient: require an active session and current user."""
    settings = _settings(request)
    token = request.cookies.get(settings.cookie_name, "")
    if len(token) > 4096:
        return None
    claims = _claims(settings, token)
    if not claims:
        return None
    with connect(settings) as connection:
        row = connection.execute(
            """SELECT users.id, users.username, users.role, sessions.id AS session_id
               FROM sessions JOIN users ON users.id = sessions.user_id
               WHERE sessions.id = ? AND users.id = ?
                 AND sessions.revoked = 0 AND sessions.expires_at > ?""",
            (claims["jti"], claims["sub"], _now()),
        ).fetchone()
    return dict(row) if row else None


def require_user(request: Request) -> dict[str, str]:
    """Reusable API dependency; HTML routes can explicitly redirect anonymous users."""
    user = authenticate(request)
    if user is None:
        raise HTTPException(
            401, "Please log in.", headers={"WWW-Authenticate": "Bearer"}
        )
    return user


def require_admin(request: Request) -> dict[str, str]:
    """Check the database role on every request, including after a role downgrade."""
    user = require_user(request)
    if user["role"] != "admin":
        raise HTTPException(403, "This page requires an admin account.")
    return user


def _cookie(response: Response, settings: Settings, value: str) -> None:
    response.set_cookie(
        settings.cookie_name,
        value,
        max_age=settings.session_minutes * 60,
        secure=settings.cookie_secure,
        httponly=True,
        samesite="lax",
        path="/",
    )


def _new_session(settings: Settings, user_id: str | None) -> tuple[str, str, int]:
    session_id = secrets.token_urlsafe(32)
    token = secrets.token_urlsafe(32)
    expires = _now() + settings.session_minutes * 60
    with connect(settings) as connection:
        connection.execute("DELETE FROM sessions WHERE expires_at <= ?", (_now(),))
        connection.execute(
            "INSERT INTO sessions (id, user_id, csrf_token, expires_at) "
            "VALUES (?, ?, ?, ?)",
            (session_id, user_id, token, expires),
        )
    return session_id, token, expires


def _request_session(request: Request) -> sqlite3.Row | None:
    settings = _settings(request)
    value = request.cookies.get(settings.cookie_name, "")
    if len(value) > 4096:
        return None
    claims = _claims(settings, value)
    if claims:
        row = _session_row(settings, claims["jti"])
        return row if row and row["user_id"] == claims["sub"] else None
    # Anonymous session cookies are opaque random identifiers, never bearer tokens.
    if len(value) != 43 or "." in value:
        return None
    row = _session_row(settings, value)
    return row if row and row["user_id"] is None else None


def csrf_token(request: Request, response: Response) -> str:
    """Issue a synchronizer token, including before signup or login."""
    row = _request_session(request)
    if row:
        return row["csrf_token"]
    settings = _settings(request)
    session_id, token, _ = _new_session(settings, None)
    _cookie(response, settings, session_id)
    return token


def require_csrf(request: Request, supplied: str | None) -> None:
    """Validate actual server session state; SameSite cookies are only another layer."""
    origin = request.headers.get("origin")
    if origin and origin != _settings(request).origin:
        raise HTTPException(403, "Refresh this page and try again.")
    if request.headers.get("sec-fetch-site") == "cross-site":
        raise HTTPException(403, "Refresh this page and try again.")
    if (
        not isinstance(supplied, str)
        or not supplied
        or len(supplied) > 128
        or not supplied.isascii()
    ):
        raise HTTPException(403, "Refresh this page and try again.")
    row = _request_session(request)
    if not row or not secrets.compare_digest(row["csrf_token"], supplied):
        raise HTTPException(403, "Refresh this page and try again.")


def signup(settings: Settings, username: str, password: str) -> dict[str, str]:
    """Create a member; callers cannot supply IDs, roles or stored hashes."""
    credentials = SignupInput(username=username, password=password)
    user = {"id": str(uuid4()), "username": credentials.username, "role": "member"}
    try:
        with connect(settings) as connection:
            connection.execute(
                "INSERT INTO users (id, username, password_hash, role) "
                "VALUES (?, ?, ?, ?)",
                (user["id"], user["username"], hash_password(password), "member"),
            )
    except sqlite3.IntegrityError as error:
        raise HTTPException(409, "That username is unavailable.") from error
    return user


def _consume_buckets(
    request: Request, buckets: tuple[tuple[str, int], ...], action: str
) -> None:
    settings = _settings(request)
    now = _now()
    with connect(settings) as connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            "DELETE FROM login_attempts WHERE started_at <= ?", (now - ATTEMPT_WINDOW,)
        )
        for bucket, limit in buckets:
            row = connection.execute(
                "SELECT attempts FROM login_attempts WHERE bucket = ?", (bucket,)
            ).fetchone()
            if row and row["attempts"] >= limit:
                raise HTTPException(
                    429,
                    f"Too many {action} attempts. Wait five minutes and try again.",
                    headers={"Retry-After": str(ATTEMPT_WINDOW)},
                )
        for bucket, _ in buckets:
            connection.execute(
                """INSERT INTO login_attempts (bucket, started_at, attempts)
                   VALUES (?, ?, 1)
                   ON CONFLICT(bucket) DO UPDATE SET attempts = attempts + 1""",
                (bucket, now),
            )
        # Keep the private throttle bounded even when random usernames are attempted.
        connection.execute("""DELETE FROM login_attempts WHERE bucket IN (
                 SELECT bucket FROM login_attempts ORDER BY started_at DESC
                 LIMIT -1 OFFSET 10000)""")


def limit_signup(request: Request) -> None:
    """Bound public account creation before spending time and memory on Argon2."""
    client = request.client.host if request.client else "unknown"
    _consume_buckets(request, ((f"signup-ip:{client}", 10),), "signup")


def _consume_attempt(request: Request, username: str) -> None:
    client = request.client.host if request.client else "unknown"
    _consume_buckets(request, ((f"user:{username}", 5), (f"ip:{client}", 30)), "login")


def login(
    request: Request, response: Response, username: str, password: str
) -> dict[str, str]:
    """Authenticate, rotate the pre-session, and issue a short-lived signed cookie."""
    settings = _settings(request)
    username = username.strip().lower()
    _consume_attempt(request, username)
    with connect(settings) as connection:
        row = connection.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
    valid = verify_password(password, row["password_hash"] if row else DUMMY_HASH)
    if not row or not valid:
        raise HTTPException(401, "The username or password is incorrect.")
    previous = _request_session(request)
    session_id, _, expires = _new_session(settings, row["id"])
    with connect(settings) as connection:
        if previous:
            connection.execute(
                "UPDATE sessions SET revoked = 1 WHERE id = ?", (previous["id"],)
            )
        connection.execute(
            "DELETE FROM login_attempts WHERE bucket = ?", (f"user:{username}",)
        )
    token = jwt.encode(
        {
            "sub": row["id"],
            "jti": session_id,
            "iat": _now(),
            "exp": expires,
            "iss": settings.origin,
            "aud": AUDIENCE,
        },
        settings.secret,
        algorithm="HS256",
        headers={"typ": TOKEN_TYPE},
    )
    _cookie(response, settings, token)
    return {key: row[key] for key in ("id", "username", "role")}


def logout(request: Request, response: Response) -> None:
    """Revoke the validated session, so replay fails even if a cookie was copied."""
    settings = _settings(request)
    row = _request_session(request)
    if row:
        with connect(settings) as connection:
            connection.execute(
                "UPDATE sessions SET revoked = 1 WHERE id = ?", (row["id"],)
            )
    response.delete_cookie(
        settings.cookie_name,
        secure=settings.cookie_secure,
        httponly=True,
        samesite="lax",
        path="/",
    )
