"""Parameterized SQLite store; accounts and sessions stay in private runtime data."""

from contextlib import contextmanager
import os
from pathlib import Path
import sqlite3
from typing import Iterator

from app import settings as settings_module
from app.private_files import private_directory, private_file
from app.settings import Settings


@contextmanager
def connect(settings: Settings) -> Iterator[sqlite3.Connection]:
    """Open one transaction and always close its connection."""
    connection = sqlite3.connect(settings.database, timeout=5)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize(settings: Settings) -> None:
    """Create the prepared storage without creating an account or assigning an admin."""
    path = Path(settings.database)
    private_directory(
        path.parent,
        app_owned=path.parent.resolve() == (settings_module.ROOT / "runtime").resolve(),
    )
    if path.is_symlink():
        raise ValueError("APP_DATABASE must be an ordinary private file.")
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        if not path.is_file():
            raise ValueError("APP_DATABASE must be an ordinary private file.") from None
    else:
        os.close(descriptor)
    private_file(path)
    with connect(settings) as connection:
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'member' CHECK(role IN ('member', 'admin'))
            );
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                user_id TEXT REFERENCES users(id) ON DELETE CASCADE,
                csrf_token TEXT NOT NULL,
                expires_at INTEGER NOT NULL,
                revoked INTEGER NOT NULL DEFAULT 0 CHECK(revoked IN (0, 1))
            );
            CREATE TABLE IF NOT EXISTS login_attempts (
                bucket TEXT PRIMARY KEY,
                started_at INTEGER NOT NULL,
                attempts INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS sessions_expiry ON sessions(expires_at);
            CREATE INDEX IF NOT EXISTS attempts_start ON login_attempts(started_at);
            """)


def set_role(settings: Settings, username: str, role: str) -> bool:
    """Trusted local administration; a public signup can never select a role."""
    if role not in {"member", "admin"}:
        raise ValueError("The role must be member or admin.")
    with connect(settings) as connection:
        result = connection.execute(
            "UPDATE users SET role = ? WHERE username = ?",
            (role, username.strip().lower()),
        )
        return result.rowcount == 1
