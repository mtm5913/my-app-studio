"""Deterministic checks for the prepared security tools, before feature work starts."""

import os
import ctypes
from pathlib import Path
import re
import subprocess
import tempfile
import time
from types import SimpleNamespace

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.testclient import TestClient
import jwt
from pydantic import ValidationError
import pytest

from app import database, security
from app import private_files
from app import settings as settings_module
from app.schemas import LoginInput, SignupInput
from app.settings import Settings

PASSPHRASE = "an example only passphrase 42"


def _canonical_windows_principal(sid):
    """Let Windows canonicalize its own SID aliases, such as runneradmin's LA."""
    security_api = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel_api = ctypes.WinDLL("kernel32", use_last_error=True)
    descriptor = ctypes.c_void_p()
    text = ctypes.c_wchar_p()
    security_api.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [
        ctypes.c_wchar_p,
        ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.c_void_p,
    ]
    security_api.ConvertSecurityDescriptorToStringSecurityDescriptorW.argtypes = [
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_wchar_p),
        ctypes.c_void_p,
    ]
    kernel_api.LocalFree.argtypes = [ctypes.c_void_p]
    kernel_api.LocalFree.restype = ctypes.c_void_p
    try:
        if not security_api.ConvertStringSecurityDescriptorToSecurityDescriptorW(
            f"D:P(A;;FA;;;{sid})", 1, ctypes.byref(descriptor), None
        ):
            return None
        if not security_api.ConvertSecurityDescriptorToStringSecurityDescriptorW(
            descriptor, 1, 4, ctypes.byref(text), None
        ):
            return None
        entries = re.findall(r"\(([^()]+)\)", text.value)
        return entries[0].split(";")[-1] if len(entries) == 1 else None
    finally:
        if text:
            kernel_api.LocalFree(ctypes.cast(text, ctypes.c_void_p))
        if descriptor:
            kernel_api.LocalFree(descriptor)


def _matches_private_dacl(contents, principal):
    entries = re.findall(r"\(([^()]+)\)", contents)
    return (
        principal is not None
        and len(entries) == 1
        and bool(re.search(r"D:[A-Z]*P", contents))
        and entries[0].split(";")[0] == "A"
        and entries[0].split(";")[2] == "FA"
        and entries[0].split(";")[-1] == principal
    )


def _has_private_permissions(path):
    """Use actual owner-only DACL evidence on Windows, never POSIX mode bits."""
    if os.name != "nt":
        return path.stat().st_mode & 0o077 == 0
    executable = Path(os.environ["SystemRoot"]) / "System32" / "icacls.exe"
    with tempfile.TemporaryDirectory(prefix="studio-acl-") as directory:
        export = Path(directory) / "permissions.txt"
        result = subprocess.run(
            [str(executable), str(path), "/save", str(export), "/Q"],
            check=False,
            capture_output=True,
            timeout=15,
        )
        if result.returncode:
            return False
        # icacls /save emits UTF-16 little-endian, sometimes without a BOM.
        contents = export.read_bytes().decode("utf-16-le").lstrip("\ufeff")
    sid = private_files._windows_user_sid()
    return _matches_private_dacl(contents, _canonical_windows_principal(sid))


@pytest.mark.parametrize(
    "contents,principal,expected",
    [
        ("D:PAI(A;;FA;;;LA)", "LA", True),
        ("D:P(A;;FA;;;S-1-5-21-1-2-3-1001)", "S-1-5-21-1-2-3-1001", True),
        ("D:P(A;;FA;;;BA)", "LA", False),
        ("D:P(A;;FA;;;LA)(A;;FA;;;BA)", "LA", False),
        ("D:AI(A;;FA;;;LA)", "LA", False),
        ("D:P(A;;FR;;;LA)", "LA", False),
        ("D:P(D;;FA;;;LA)", "LA", False),
    ],
)
def test_acl_evidence_requires_only_the_exact_owner_with_full_access(
    contents, principal, expected
):
    """Accept a canonical owner alias without accepting groups or extra access."""
    assert _matches_private_dacl(contents, principal) is expected


@pytest.fixture(name="security_settings")
def fixture_security_settings(tmp_path):
    """A fresh database and signing key keep test accounts out of personal data."""
    settings = Settings(
        mode="development",
        origin="http://127.0.0.1:8000",
        database=tmp_path / "security.sqlite3",
        secret="test-only-key-that-is-long-enough-" + "a" * 32,
    )
    database.initialize(settings)
    return settings


@pytest.fixture(name="security_client")
def fixture_security_client(security_settings):
    """Test the helpers through actual HTTP requests without solving student routes."""
    app = FastAPI()
    app.state.settings = security_settings

    @app.get("/csrf")
    def token(request: Request, response: Response):
        return {"csrf_token": security.csrf_token(request, response)}

    @app.post("/signup")
    def signup(request: Request, credentials: SignupInput):
        security.require_csrf(request, request.headers.get("X-CSRF-Token"))
        security.limit_signup(request)
        return security.signup(
            security_settings, credentials.username, credentials.password
        )

    @app.post("/login")
    def login(request: Request, response: Response, credentials: LoginInput):
        security.require_csrf(request, request.headers.get("X-CSRF-Token"))
        return security.login(
            request, response, credentials.username, credentials.password
        )

    @app.post("/logout")
    def logout(request: Request, response: Response):
        security.require_csrf(request, request.headers.get("X-CSRF-Token"))
        security.logout(request, response)
        return {"message": "Logged out"}

    @app.get("/me")
    def me(request: Request):
        return security.require_user(request)

    @app.get("/admin")
    def admin(request: Request):
        return security.require_admin(request)

    with TestClient(app, base_url=security_settings.origin) as client:
        yield client


def _csrf(client):
    return {"X-CSRF-Token": client.get("/csrf").json()["csrf_token"]}


def _member(client):
    credentials = {"username": "learner", "password": PASSPHRASE}
    response = client.post("/signup", json=credentials, headers=_csrf(client))
    assert response.status_code == 200
    response = client.post("/login", json=credentials, headers=_csrf(client))
    assert response.status_code == 200
    return response


def test_argon_hash_is_salted_and_verifiable():
    """Two equal passwords do not create equal stored credentials."""
    first = security.hash_password(PASSPHRASE)
    second = security.hash_password(PASSPHRASE)
    assert first.startswith("$argon2id$")
    assert first != second
    assert PASSPHRASE not in first
    assert security.verify_password(PASSPHRASE, first)
    assert not security.verify_password("the wrong passphrase", first)


@pytest.mark.parametrize("password", ["short", "a" * 129])
def test_signup_rejects_password_lengths(password):
    """Enforce length before an expensive hash rather than truncating input."""
    with pytest.raises(ValidationError):
        SignupInput(username="learner", password=password)


def test_signup_allows_spaces_unicode_and_blocks_role_input():
    """Passphrases are flexible; authorization fields are never public inputs."""
    assert (
        SignupInput(username="LEARNER", password="a long café passphrase 你好").username
        == "learner"
    )
    with pytest.raises(ValidationError):
        SignupInput(username="learner", password=PASSPHRASE, role="admin")


@pytest.mark.parametrize("username", ["ab", "a b c", "<script>", "a" * 33])
def test_signup_rejects_ambiguous_usernames(username):
    """Normalization has a defined, small username contract."""
    with pytest.raises(ValidationError):
        SignupInput(username=username, password=PASSPHRASE)


def test_signup_stores_only_hash_and_member(security_settings):
    """The first account has no special privileges and duplicates stay unique."""
    user = security.signup(security_settings, "LEARNER", PASSPHRASE)
    assert set(user) == {"id", "username", "role"}
    assert user["role"] == "member"
    with database.connect(security_settings) as connection:
        row = connection.execute("SELECT * FROM users").fetchone()
    assert row["username"] == "learner"
    assert row["password_hash"].startswith("$argon2id$")
    with pytest.raises(HTTPException) as caught:
        security.signup(security_settings, "learner", PASSPHRASE)
    assert caught.value.status_code == 409


def test_anonymous_member_admin_and_immediate_downgrade(
    security_client, security_settings
):
    """The same signed token follows the current database role on every request."""
    assert security_client.get("/me").status_code == 401
    _member(security_client)
    assert security_client.get("/me").status_code == 200
    assert security_client.get("/admin").status_code == 403
    assert database.set_role(security_settings, "learner", "admin")
    assert security_client.get("/admin").status_code == 200
    assert database.set_role(security_settings, "learner", "member")
    assert security_client.get("/admin").status_code == 403
    assert not database.set_role(security_settings, "missing", "admin")
    with pytest.raises(ValueError):
        database.set_role(security_settings, "learner", "super-admin")


def test_csrf_required_for_login_and_rotated_after_login(security_client):
    """A pre-login form token cannot authorize a later authenticated action."""
    before = _csrf(security_client)
    credentials = {"username": "learner", "password": PASSPHRASE}
    assert security_client.post("/signup", json=credentials).status_code == 403
    assert (
        security_client.post("/signup", json=credentials, headers=before).status_code
        == 200
    )
    assert security_client.post("/login", json=credentials).status_code == 403
    assert (
        security_client.post("/login", json=credentials, headers=before).status_code
        == 200
    )
    assert security_client.post("/logout", headers=before).status_code == 403
    valid = _csrf(security_client)
    assert valid != before
    assert security_client.post("/logout", headers=valid).status_code == 200


def test_cross_origin_and_bad_csrf_do_not_mutate(security_client):
    """An attacker origin cannot reuse even a known valid form token."""
    credentials = {"username": "learner", "password": PASSPHRASE}
    headers = _csrf(security_client)
    headers["Origin"] = "https://attacker.example"
    assert (
        security_client.post("/signup", json=credentials, headers=headers).status_code
        == 403
    )
    assert (
        security_client.post(
            "/signup", json=credentials, headers={"X-CSRF-Token": "wrong"}
        ).status_code
        == 403
    )
    headers = _csrf(security_client)
    headers["Sec-Fetch-Site"] = "cross-site"
    assert (
        security_client.post("/signup", json=credentials, headers=headers).status_code
        == 403
    )
    assert security_client.get("/logout").status_code == 405


def test_non_ascii_csrf_header_is_rejected_without_a_server_error(security_client):
    """Malformed header bytes must fail closed before constant-time comparison."""
    _csrf(security_client)
    response = security_client.post(
        "/signup",
        json={"username": "learner", "password": PASSPHRASE},
        headers=[(b"X-CSRF-Token", "é".encode("utf-8"))],
    )
    assert response.status_code == 403


def test_login_rotates_session_and_logout_rejects_copied_jwt(
    security_client, security_settings
):
    """Deleting a browser cookie alone would fail this replay check."""
    before = _csrf(security_client)
    anonymous = security_client.cookies.get(security_settings.cookie_name)
    _member(security_client)
    token = security_client.cookies.get(security_settings.cookie_name)
    assert token != anonymous
    claims = jwt.decode(
        token,
        security_settings.secret,
        algorithms=["HS256"],
        issuer=security_settings.origin,
        audience=security.AUDIENCE,
    )
    assert claims["jti"] and "role" not in claims
    assert claims["exp"] - claims["iat"] <= 15 * 60
    assert security_client.post("/logout", headers=before).status_code == 403
    assert (
        security_client.post("/logout", headers=_csrf(security_client)).status_code
        == 200
    )
    security_client.cookies.set(security_settings.cookie_name, token)
    assert security_client.get("/me").status_code == 401


@pytest.mark.parametrize(
    "change",
    [
        "signature",
        "expired",
        "issuer",
        "audience",
        "missing",
        "unknown-session",
        "none",
        "HS384",
        "type",
    ],
)
def test_invalid_jwts_are_rejected(security_client, security_settings, change):
    """Do not confuse a parsable JWT or bearer header with authenticated identity."""
    _member(security_client)
    token = security_client.cookies.get(security_settings.cookie_name)
    claims = jwt.decode(token, options={"verify_signature": False})
    algorithm = "HS256"
    secret = security_settings.secret
    token_type = security.TOKEN_TYPE
    if change == "signature":
        secret = "a completely different signing key 123"
    elif change == "expired":
        claims["exp"] = int(time.time()) - 1
    elif change == "issuer":
        claims["iss"] = "https://different.example"
    elif change == "audience":
        claims["aud"] = "different-api"
    elif change == "missing":
        claims.pop("exp")
    elif change == "unknown-session":
        claims["jti"] = "not-a-real-session"
    elif change == "none":
        algorithm, secret = "none", None
    elif change == "HS384":
        algorithm = "HS384"
    elif change == "type":
        token_type = "different+jwt"
    altered = jwt.encode(
        claims, secret, algorithm=algorithm, headers={"typ": token_type}
    )
    security_client.cookies.set(security_settings.cookie_name, altered)
    assert security_client.get("/me").status_code == 401


def test_unknown_user_and_wrong_password_share_error(security_client):
    """User lookup does not reveal which part of a login attempt was incorrect."""
    _member(security_client)
    headers = _csrf(security_client)
    wrong = security_client.post(
        "/login", json={"username": "learner", "password": "wrong"}, headers=headers
    )
    unknown = security_client.post(
        "/login", json={"username": "missing", "password": "wrong"}, headers=headers
    )
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def test_login_throttle_survives_browser_restart_and_expires(
    security_client, monkeypatch
):
    """Throttling is database state, not a resettable in-memory counter."""
    credentials = {"username": "missing", "password": "wrong"}
    for _ in range(5):
        assert (
            security_client.post(
                "/login", json=credentials, headers=_csrf(security_client)
            ).status_code
            == 401
        )
    security_client.cookies.clear()
    assert (
        security_client.post(
            "/login", json=credentials, headers=_csrf(security_client)
        ).status_code
        == 429
    )
    real_now = security._now()
    monkeypatch.setattr(security, "_now", lambda: real_now + 301)
    assert (
        security_client.post(
            "/login", json=credentials, headers=_csrf(security_client)
        ).status_code
        == 401
    )


def test_signup_throttle_limits_hashing_before_account_creation(security_client):
    """A cookie reset cannot bypass the persistent public signup limit."""
    for number in range(10):
        response = security_client.post(
            "/signup",
            json={"username": f"learner_{number}", "password": PASSPHRASE},
            headers=_csrf(security_client),
        )
        assert response.status_code == 200
    security_client.cookies.clear()
    response = security_client.post(
        "/signup",
        json={"username": "another_learner", "password": PASSPHRASE},
        headers=_csrf(security_client),
    )
    assert response.status_code == 429


def test_expired_server_session_rejected(security_client, security_settings):
    """A still-signed token cannot resurrect an expired SQLite session."""
    _member(security_client)
    with database.connect(security_settings) as connection:
        connection.execute("UPDATE sessions SET expires_at = 0")
    assert security_client.get("/me").status_code == 401


def test_production_cookie_flags(security_client, security_settings):
    """The hosted cookie cannot be read by scripts or sent over plain HTTP."""
    secure = Settings(
        mode="production",
        origin="https://studio.example",
        database=security_settings.database,
        secret=security_settings.secret,
    )
    security_client.app.state.settings = secure
    response = security_client.get("/csrf")
    cookie = response.headers["set-cookie"].lower()
    assert "__host-studio-session=" in cookie
    assert "secure" in cookie and "httponly" in cookie and "samesite=lax" in cookie
    assert "domain=" not in cookie


def test_development_secret_is_private_and_persistent(tmp_path, monkeypatch):
    """Restarting the dev server does not silently log everyone out."""
    monkeypatch.setattr(settings_module, "ROOT", tmp_path)
    for name in ("APP_MODE", "APP_ORIGIN", "APP_SECRET", "APP_DATABASE"):
        monkeypatch.delenv(name, raising=False)
    first = Settings.load()
    assert first.secret == Settings.load().secret
    assert len(first.secret) >= 32
    assert _has_private_permissions(tmp_path / "runtime" / "development-secret")
    assert _has_private_permissions(tmp_path / "runtime")


@pytest.mark.parametrize(
    "mode,origin,secret",
    [
        ("production", "https://studio.example", ""),
        ("production", "http://studio.example", "x" * 40),
        ("development", "http://0.0.0.0:8000", "x" * 40),
        ("development", "http://127.0.0.1:8000/path", "x" * 40),
        ("development", "http://@127.0.0.1:8000", "x" * 40),
        ("development", "http://127.0.0.1:8000?", "x" * 40),
        ("development", "http://127.0.0.1:\n8000", "x" * 40),
        ("staging", "https://studio.example", "x" * 40),
    ],
)
def test_settings_fail_closed(mode, origin, secret, monkeypatch):
    """No implicit hosted configuration or development-wide network exposure."""
    monkeypatch.setenv("APP_MODE", mode)
    monkeypatch.setenv("APP_ORIGIN", origin)
    monkeypatch.setenv("APP_SECRET", secret)
    with pytest.raises(ValueError):
        Settings.load()


def test_database_permissions_and_parameterized_identity(security_settings):
    """Stored runtime data is private; an input string cannot become SQL syntax."""
    assert _has_private_permissions(Path(security_settings.database))
    assert not database.set_role(security_settings, "learner' OR 1=1 --", "admin")
    assert os.path.exists(security_settings.database)


@pytest.mark.skipif(os.name == "nt", reason="Windows private files use actual DACLs.")
def test_existing_insecure_posix_secret_is_rejected_without_silent_repair(
    tmp_path, monkeypatch
):
    """The previous fail-closed POSIX behavior remains meaningful."""
    monkeypatch.setattr(settings_module, "ROOT", tmp_path)
    path = tmp_path / "runtime" / "development-secret"
    path.parent.mkdir()
    path.write_text("a private key that is long enough to load", encoding="utf-8")
    path.chmod(0o644)
    with pytest.raises(ValueError, match="private file permissions"):
        settings_module._development_secret(path.parent)
    assert path.stat().st_mode & 0o077 != 0


def test_windows_acl_uses_numeric_owner_and_removes_other_grants(tmp_path, monkeypatch):
    """The Windows branch performs real ACL operations, not chmod camouflage."""
    commands = []
    sid = "S-1-5-21-100-200-300-1001"

    def command(name, arguments):
        commands.append((name, arguments))
        return f'"class\\learner","{sid}"\n' if name == "whoami.exe" else ""

    monkeypatch.setattr(private_files, "WINDOWS", True)
    monkeypatch.setattr(private_files, "_windows_command", command)
    path = tmp_path / "a file with spaces"
    path.write_text("", encoding="utf-8")
    private_files.private_file(path)
    assert commands == [
        ("whoami.exe", ["/user", "/fo", "csv", "/nh"]),
        ("icacls.exe", [str(path), "/reset", "/Q"]),
        (
            "icacls.exe",
            [str(path), "/inheritance:r", "/grant:r", f"*{sid}:(F)", "/Q"],
        ),
    ]


def test_private_directory_never_changes_an_existing_arbitrary_parent(
    tmp_path, monkeypatch
):
    """Only app-owned or newly created folders can have their permissions changed."""
    commands = []
    monkeypatch.setattr(private_files, "WINDOWS", True)
    monkeypatch.setattr(
        private_files,
        "_windows_acl",
        lambda path, directory: commands.append((path, directory)),
    )
    private_files.private_directory(tmp_path)
    assert commands == []
    new_directory = tmp_path / "private-app-data"
    private_files.private_directory(new_directory)
    assert commands == [(new_directory, True)]
    private_files.private_directory(new_directory, app_owned=True)
    assert commands == [(new_directory, True), (new_directory, True)]


def test_windows_directory_acl_is_inherited_by_app_runtime_files(tmp_path, monkeypatch):
    """SQLite journals and newly created secrets inherit the owner-only directory ACL."""
    commands = []

    def command(name, arguments):
        commands.append((name, arguments))
        return (
            '"class\\learner","S-1-5-21-100-200-300-1001"\n'
            if name == "whoami.exe"
            else ""
        )

    monkeypatch.setattr(private_files, "WINDOWS", True)
    monkeypatch.setattr(private_files, "_windows_command", command)
    directory = tmp_path / "app-runtime"
    private_files.private_directory(directory)
    assert commands[-1][1][-2:] == ["*S-1-5-21-100-200-300-1001:(OI)(CI)(F)", "/Q"]
    assert all("/T" not in arguments for _, arguments in commands)


def test_windows_acl_failure_is_closed_and_does_not_print_identity(monkeypatch):
    """Captured command output must not become a public error or a SID log."""
    sid = "S-1-5-21-100-200-300-1001"
    monkeypatch.setattr(
        private_files.subprocess,
        "run",
        lambda *_arguments, **_options: SimpleNamespace(
            returncode=1, stdout=f"private identity {sid}", stderr="denied"
        ),
    )
    with pytest.raises(ValueError) as caught:
        private_files._windows_user_sid()
    assert sid not in str(caught.value)


def test_windows_owner_sid_must_be_a_numeric_identity(monkeypatch):
    """Unexpected command output cannot become an ACL principal or shell input."""
    monkeypatch.setattr(
        private_files,
        "_windows_command",
        lambda *_arguments: '"class\\learner","unexpected identity"\n',
    )
    with pytest.raises(ValueError, match="current file owner"):
        private_files._windows_user_sid()
