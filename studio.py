#!/usr/bin/env python3
"""Prepared app studio: setup, run, check, progress and trusted role management."""

import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import webbrowser

from studio_tools import progress

ROOT = Path(__file__).resolve().parent


def prepare_output():
    """Keep helpful symbols readable in Windows terminals and redirected CI output."""
    os.environ.setdefault("PYTHONUTF8", "1")
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")


def environment_python():
    """Resolve this clone's Python without requiring shell activation."""
    return (
        ROOT
        / ".venv"
        / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    )


def setup():
    """Prepare pinned dependencies only after the student has connected their coach."""
    if sys.version_info < (3, 12):
        raise ValueError(
            "Use class Python 3.12 or later; your coach can help locate it."
        )
    python = environment_python()
    if not python.exists():
        subprocess.run([sys.executable, "-m", "venv", str(ROOT / ".venv")], check=True)
    subprocess.run(
        [str(python), "-m", "pip", "install", "-r", "requirements.txt"],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(
        [str(python), "-m", "playwright", "install", "chromium"], cwd=ROOT, check=True
    )
    print("✅ Setup ready. Return to your coach, then run python3 studio.py run.")


def require_python():
    """Provide a clear recovery step instead of invoking the wrong interpreter."""
    python = environment_python()
    if not python.exists():
        raise ValueError("Run python3 studio.py setup first; your coach can help.")
    return python


def run(args):
    """Run a loopback development server; never stop another app to take its port."""
    python = require_python()
    if not 1024 <= args.port <= 65535:
        raise ValueError("Choose an available local port between 1024 and 65535.")
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            if os.name != "nt":
                # Match Uvicorn's POSIX restart behavior after a closed connection.
                # Windows SO_REUSEADDR could share an active listener, so omit it.
                probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            probe.bind(("127.0.0.1", args.port))
    except OSError as error:
        raise ValueError(
            f"Port {args.port} is already in use. Keep the other app running; "
            "ask your coach to use --port 8001 or another available port."
        ) from error
    url = f"http://127.0.0.1:{args.port}"
    environment = dict(
        os.environ,
        APP_MODE="development",
        APP_ORIGIN=url,
        STUDIO_LIVE_RELOAD="0" if args.plain else "1",
    )
    command = [
        str(python),
        "-m",
        "uvicorn",
        "app.main:create_app",
        "--factory",
        "--no-access-log",
        "--host",
        "127.0.0.1",
        "--port",
        str(args.port),
    ]
    if not args.plain:
        command.extend(["--reload", "--reload-dir", "app"])
    print(f"Open {url}", flush=True)
    print(
        (
            "Leave this terminal running. Saved app edits refresh the browser. "
            "Ctrl+C stops the app."
            if not args.plain
            else "Plain mode: no automatic restart or refresh. Ctrl+C stops the app."
        ),
        flush=True,
    )
    subprocess.run(command, cwd=ROOT, env=environment, check=True)


def declared_stage():
    """The starter declares stage zero; only agreed completed stages advance it."""
    configuration = json.loads((ROOT / "studio.json").read_text(encoding="utf-8"))
    level = (
        configuration.get("implemented_through")
        if isinstance(configuration, dict)
        else None
    )
    if (
        not isinstance(level, int)
        or isinstance(level, bool)
        or level not in (0, 1, 2, 3)
    ):
        raise ValueError(
            "studio.json implemented_through must be an integer from 0 to 3."
        )
    return level


def check(args):
    """Run deterministic checks, keeping foundation and unfinished features distinct."""
    if not args.fast:
        for receipt in progress.STATE.glob("check-*.json"):
            receipt.unlink()
    python = require_python()
    level = progress.lesson_number(args.lesson) if args.lesson else declared_stage()
    selected = f"APP-{level:03}" if level else "foundation"
    fingerprint = progress.source_fingerprint()
    paths = ["app", "studio.py", "studio_tools", "conftest.py", "tests", "contracts"]
    paths = [name for name in paths if (ROOT / name).exists()]
    commands = [
        ("Black · formatting", ["black", "--check", *paths]),
        ("Pylint · app and tooling", ["pylint", "app", "studio.py", "studio_tools"]),
        ("pytest · prepared foundation", ["pytest", "-q", "tests", "-m", "not e2e"]),
    ]
    contracts = ["test_homepage.py", "test_accounts.py", "test_roles.py"][:level]
    if contracts:
        commands.append(
            (
                f"pytest · contracts through {selected}",
                ["pytest", "-q", *[f"contracts/{name}" for name in contracts]],
            )
        )
    if not args.fast:
        commands.append(
            ("pytest · real Chromium journeys", ["pytest", "-q", "tests", "-m", "e2e"])
        )
    environment = dict(os.environ, APP_TEST_LESSON=str(level))
    failed = []
    for name, arguments in commands:
        print("\n" + name, flush=True)
        result = subprocess.run(
            [str(python), "-m", *arguments], cwd=ROOT, env=environment, check=False
        )
        if result.returncode:
            failed.append(name)
    if fingerprint != progress.source_fingerprint():
        failed.append("source files changed during checks; run the check again")
    if failed:
        raise ValueError("Checks failed: " + "; ".join(failed))
    if args.fast:
        print(
            "🟡 Fast checks passed. Chromium was omitted; no full receipt was recorded."
        )
    else:
        progress.record_check(level, fingerprint)
        print("✅ Full " + selected + " checks passed, including actual Chromium.")
    if not level:
        print(
            "APP-001, APP-002 and APP-003 remain pending. "
            "A foundation pass is not a feature pass."
        )
    print("These checks do not grade your decisions or prove understanding.")


def lesson_issue(args):
    """Open the prepared issue form or store actual own-repository evidence links."""
    repo = progress.repository()
    if repo == progress.INSTRUCTOR:
        raise ValueError("Create your own template copy and SSH-clone it first.")
    if args.url or args.pr:
        config = progress.configuration()
        links = config.setdefault(args.lesson, {})
        for value, key, kind in (
            (args.url, "issue_url", "issues"),
            (args.pr, "pr_url", "pull"),
        ):
            if value:
                progress.issue_number(value, repo, kind)
                links[key] = value
        progress.save_json(progress.STATE / "progress.json", config)
        print(
            "✅ Evidence link saved locally. "
            "status checks its actual contents separately."
        )
        return
    template = args.lesson.lower() + ".md"
    url = f"https://github.com/{repo}/issues/new?template={template}"
    print("Create this lesson issue in your own repository using this form:")
    print(url)
    if args.open:
        webbrowser.open(url)
    print(
        "Then record it: "
        f"python3 studio.py issue --lesson {args.lesson} --url ISSUE_URL"
    )


def user_role(args):
    """A trusted local operator controls roles; signup never grants admin authority."""
    python = require_python()
    if Path(sys.prefix).resolve() != (ROOT / ".venv").resolve():
        subprocess.run(
            [str(python), str(ROOT / "studio.py"), *sys.argv[1:]], check=True
        )
        return
    # Import inside the prepared interpreter, after setup installs dependencies.
    from app import database  # pylint: disable=import-outside-toplevel
    from app.settings import Settings  # pylint: disable=import-outside-toplevel

    settings = Settings.load()
    database.initialize(settings)
    if not database.set_role(settings, args.username, args.role):
        raise ValueError("No matching user. Have that person sign up first.")
    print(
        "✅ Role updated in this configured local database. "
        "Existing tokens are rechecked."
    )


def main():
    """Keep actions explicit and failures actionable without exposing secrets."""
    prepare_output()
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser(
        "setup", help="prepare this clone's pinned environment and Chromium"
    )
    launch = commands.add_parser(
        "run", help="start the local app with automatic refresh"
    )
    launch.add_argument("--port", type=int, default=8000)
    launch.add_argument(
        "--plain", action="store_true", help="disable automatic restart/refresh"
    )
    tests = commands.add_parser(
        "check", help="run formatting, analysis, pytest and Chromium"
    )
    tests.add_argument("--lesson", choices=[f"APP-{n:03}" for n in range(1, 4)])
    tests.add_argument(
        "--fast", action="store_true", help="omit Chromium; not a full check"
    )
    issue = commands.add_parser(
        "issue", help="find a lesson issue form or record real links"
    )
    issue.add_argument(
        "--lesson", required=True, choices=[f"APP-{n:03}" for n in range(1, 4)]
    )
    issue.add_argument("--url")
    issue.add_argument("--pr")
    issue.add_argument(
        "--open", action="store_true", help="open the form in your browser"
    )
    state = commands.add_parser(
        "status", help="show evidence gaps and one next checkpoint"
    )
    state.add_argument(
        "--lesson", required=True, choices=[f"APP-{n:03}" for n in range(1, 4)]
    )
    state.add_argument(
        "--offline", action="store_true", help="skip GitHub; never reports completion"
    )
    user = commands.add_parser(
        "user", help="trusted operator management in the configured database"
    )
    operations = user.add_subparsers(dest="operation", required=True)
    role = operations.add_parser(
        "role", help="change an existing user's member/admin role"
    )
    role.add_argument("username")
    role.add_argument("--role", required=True, choices=["member", "admin"])
    args = parser.parse_args()
    try:
        if args.command == "setup":
            setup()
        elif args.command == "run":
            run(args)
        elif args.command == "check":
            check(args)
        elif args.command == "issue":
            lesson_issue(args)
        elif args.command == "status":
            progress.display(progress.status(args.lesson, not args.offline))
        elif args.command == "user":
            user_role(args)
    except KeyboardInterrupt:
        print("\nApp stopped. Your saved work remains in this clone.")
    except (ValueError, RuntimeError, OSError, subprocess.SubprocessError) as error:
        parser.exit(1, f"🟡 {error}\nYour coach can help resolve this step.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
