"""Explicit local and hosted settings; development secrets stay private."""

from dataclasses import dataclass
import os
from pathlib import Path
import secrets
from urllib.parse import urlsplit

from app.private_files import private_directory, private_file

ROOT = Path(__file__).resolve().parents[1]


def _origin(value: str, mode: str) -> str:
    if any(character.isspace() for character in value):
        raise ValueError("APP_ORIGIN cannot contain whitespace.")
    parsed = urlsplit(value)
    invalid_components = (
        not parsed.hostname,
        parsed.username is not None or parsed.password is not None,
        "?" in value or "#" in value,
        parsed.path not in {"", "/"},
    )
    if any(invalid_components):
        raise ValueError(
            "APP_ORIGIN must be one origin, without a path or credentials."
        )
    try:
        port = parsed.port
    except ValueError as error:
        raise ValueError("APP_ORIGIN has an invalid port.") from error
    if mode == "production" and parsed.scheme != "https":
        raise ValueError("Production APP_ORIGIN must use HTTPS.")
    if mode == "development" and (
        parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
    ):
        raise ValueError("Development APP_ORIGIN must use HTTP on a loopback host.")
    hostname = parsed.hostname.encode("idna").decode("ascii")
    hostname = f"[{hostname}]" if ":" in hostname else hostname
    suffix = (
        f":{port}" if port and port != {"http": 80, "https": 443}[parsed.scheme] else ""
    )
    return f"{parsed.scheme}://{hostname}{suffix}"


def _development_secret(directory: Path) -> str:
    private_directory(directory, app_owned=True)
    path = directory / "development-secret"
    if path.is_symlink():
        raise ValueError("The development secret must be an ordinary private file.")
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        private_file(path, reject_insecure=True)
        return path.read_text(encoding="utf-8").strip()
    secret = secrets.token_urlsafe(48)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        private_file(path)
        stream.write(secret)
    return secret


@dataclass(frozen=True)
class Settings:
    """Settings are injected into the app and tests rather than global credentials."""

    mode: str
    origin: str
    database: Path
    secret: str
    session_minutes: int = 15

    @property
    def cookie_secure(self) -> bool:
        """Only explicit loopback development can use an insecure cookie."""
        return self.mode == "production"

    @property
    def cookie_name(self) -> str:
        """The hosted prefix prevents Domain cookies and insecure cookie injection."""
        return "__Host-studio-session" if self.cookie_secure else "studio-session"

    @classmethod
    def load(cls) -> "Settings":
        """Load environment configuration, failing closed for hosted deployments."""
        mode = os.environ.get("APP_MODE", "development")
        if mode not in {"development", "production"}:
            raise ValueError("APP_MODE must be development or production.")
        default_origin = "http://127.0.0.1:8000" if mode == "development" else ""
        origin = _origin(os.environ.get("APP_ORIGIN", default_origin), mode)
        database = Path(
            os.environ.get("APP_DATABASE", str(ROOT / "runtime" / "studio.sqlite3"))
        ).expanduser()
        secret = os.environ.get("APP_SECRET", "")
        if not secret and mode == "development":
            secret = _development_secret(ROOT / "runtime")
        if len(secret.encode("utf-8")) < 32:
            raise ValueError(
                "APP_SECRET must contain at least 32 bytes; keep it private."
            )
        if secret.lower() in {"change-me" * 4, "your-secret-key-here" * 2}:
            raise ValueError(
                "Replace the example APP_SECRET with a random private key."
            )
        return cls(mode=mode, origin=origin, database=database, secret=secret)
