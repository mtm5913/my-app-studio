"""Private runtime files use POSIX modes or actual Windows owner-only DACLs."""

import csv
import io
import os
from pathlib import Path
import re
import subprocess

WINDOWS = os.name == "nt"


def _windows_command(name: str, arguments: list[str]) -> str:
    executable = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / name
    try:
        result = subprocess.run(
            [str(executable), *arguments],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise ValueError(
            "Windows could not protect this app's private runtime files."
        ) from None
    if result.returncode:
        raise ValueError("Windows could not protect this app's private runtime files.")
    return result.stdout


def _windows_user_sid() -> str:
    output = _windows_command("whoami.exe", ["/user", "/fo", "csv", "/nh"])
    rows = list(csv.reader(io.StringIO(output)))
    if len(rows) != 1 or len(rows[0]) != 2:
        raise ValueError("Windows could not identify the current file owner.")
    sid = rows[0][1].strip()
    if not re.fullmatch(r"S-\d+(?:-\d+)+", sid):
        raise ValueError("Windows could not identify the current file owner.")
    return sid


def _windows_acl(path: Path, directory: bool) -> None:
    sid = _windows_user_sid()
    # Reset removes old explicit ACEs. The second operation removes inherited ACEs
    # and grants this user only. Never recurse or alter an arbitrary parent folder.
    _windows_command("icacls.exe", [str(path), "/reset", "/Q"])
    rights = "(OI)(CI)(F)" if directory else "(F)"
    _windows_command(
        "icacls.exe",
        [str(path), "/inheritance:r", "/grant:r", f"*{sid}:{rights}", "/Q"],
    )


def private_directory(path: Path, *, app_owned: bool = False) -> None:
    """Protect folders we create or explicitly own, leaving other parent ACLs alone."""
    if path.is_symlink() or (WINDOWS and path.is_junction()):
        raise ValueError("The app's runtime directory cannot be a symbolic link.")
    try:
        path.mkdir(parents=True, mode=0o700)
    except FileExistsError:
        if not path.is_dir():
            raise ValueError("The app's runtime path must be a directory.") from None
        if not app_owned:
            return
    if WINDOWS:
        _windows_acl(path, directory=True)
    else:
        path.chmod(0o700)


def private_file(path: Path, *, reject_insecure: bool = False) -> None:
    """Protect one file before using it; do not mistake Windows mode bits for ACLs."""
    if path.is_symlink() or not path.is_file():
        raise ValueError("Private runtime data must be an ordinary file.")
    if WINDOWS:
        _windows_acl(path, directory=False)
    else:
        if reject_insecure and path.stat().st_mode & 0o077:
            raise ValueError(
                "The development secret must have private file permissions."
            )
        path.chmod(0o600)
