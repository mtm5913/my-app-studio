"""Evidence safety, local refresh and command behavior without claiming learner understanding."""

import argparse
import io
import json
import os
from pathlib import Path
import socket
import subprocess

import pytest

import studio
from studio_tools import live, progress


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    """An isolated clone-shaped workspace contains no real learner data or server access."""
    monkeypatch.setattr(studio, "ROOT", tmp_path)
    monkeypatch.setattr(progress, "ROOT", tmp_path)
    monkeypatch.setattr(progress, "STATE", tmp_path / "runtime")
    (tmp_path / "app").mkdir()
    (tmp_path / "app/main.py").write_text("VALUE = 1\n")
    (tmp_path / "studio.json").write_text('{"implemented_through": 0}\n')
    return tmp_path


def test_revision_ignores_runtime_and_changes_for_saved_app(workspace):
    before = live.revision(workspace)
    (workspace / "runtime").mkdir()
    (workspace / "runtime/private.json").write_text('{"secret": "fixture"}')
    assert live.revision(workspace) == before
    (workspace / "app/main.py").write_text("VALUE = 2\n")
    assert live.revision(workspace) != before


def test_revision_does_not_read_symlinked_private_file(workspace):
    before = live.revision(workspace)
    secret = workspace / "private.json"
    secret.write_text('{"secret": "fixture"}')
    (workspace / "app/private.json").symlink_to(secret)
    assert live.revision(workspace) == before


def test_fingerprint_ignores_notes_but_covers_contracts(workspace):
    before = progress.source_fingerprint()
    (workspace / "LEARNING.md").write_text("Actual learner note\n")
    assert progress.source_fingerprint() == before
    (workspace / "contracts").mkdir()
    (workspace / "contracts/test_homepage.py").write_text("assert True\n")
    assert progress.source_fingerprint() != before


def test_changed_shared_fixtures_invalidate_a_full_check(workspace):
    (workspace / "studio.json").write_text('{"implemented_through": 1}\n')
    (workspace / "conftest.py").write_text('"""Isolated fixtures."""\n')
    progress.record_check(1, progress.source_fingerprint())
    assert progress.check_evidence("APP-001")["current"]
    (workspace / "conftest.py").write_text('"""Changed fixture behavior."""\n')
    assert not progress.check_evidence("APP-001")["current"]


def test_foundation_receipt_does_not_complete_a_feature(workspace):
    progress.record_check(0, progress.source_fingerprint())
    assert not progress.check_evidence("APP-001")["current"]


def test_full_feature_receipt_requires_declared_stage_and_current_source(workspace):
    progress.record_check(1, progress.source_fingerprint())
    assert not progress.check_evidence("APP-001")["current"]
    (workspace / "studio.json").write_text('{"implemented_through": 1}\n')
    progress.record_check(1, progress.source_fingerprint())
    assert progress.check_evidence("APP-001")["current"]
    (workspace / "app/main.py").write_text("VALUE = 2\n")
    assert not progress.check_evidence("APP-001")["current"]


def test_later_feature_pass_is_cumulative(workspace):
    (workspace / "studio.json").write_text('{"implemented_through": 3}\n')
    progress.record_check(3, progress.source_fingerprint())
    assert progress.check_evidence("APP-001")["current"]
    assert progress.check_evidence("APP-003")["current"]


def test_receipt_without_actual_browser_pass_is_insufficient(workspace):
    (workspace / "studio.json").write_text('{"implemented_through": 1}\n')
    progress.record_check(1, progress.source_fingerprint())
    path = progress.STATE / "check-APP-001.json"
    report = json.loads(path.read_text())
    report["browser"] = "not run"
    progress.save_json(path, report)
    assert not progress.check_evidence("APP-001")["current"]


@pytest.mark.parametrize("name", ["APP-000", "APP-004", "../APP-001", "APP-001;echo"])
def test_only_known_lessons_are_accepted(name):
    with pytest.raises(ValueError):
        progress.lesson_number(name)


def test_learner_record_presence_keeps_lessons_separate():
    text = "## APP-001\n" + "\n".join(
        f"- {field}: My actual observation." for field in progress.CHECKPOINTS
    )
    text += "\n## APP-002\n- Prediction: Pending.\n"
    assert all(progress.learner_sections(text, "APP-001").values())
    assert not any(progress.learner_sections(text, "APP-002").values())


def test_pending_and_hidden_example_are_not_actual_records():
    text = (
        "## APP-001\n"
        "- Prediction: Pending.\n"
        "- Check interpretation: Not recorded.\n"
        "- Browser observation: Earlier conversation unavailable.\n"
        "<!-- - Keep decision: an example, not a record -->\n"
    )
    assert not any(progress.learner_sections(text, "APP-001").values())


def test_issue_links_must_be_exact_and_in_own_repository():
    assert (
        progress.issue_number("https://github.com/student/app/issues/7", "student/app")
        == 7
    )
    for url in (
        "https://github.com/other/app/issues/7",
        "https://github.com/student/app/pull/7",
        "https://github.com/student/app/issues/7?anything=true",
    ):
        with pytest.raises(ValueError):
            progress.issue_number(url, "student/app")


def test_github_checks_selected_pr_commit_and_latest_job(monkeypatch):
    calls = []

    def github(path):
        calls.append(path)
        if "/issues/" in path:
            return {
                "number": 7,
                "state": "closed",
                "created_at": "date",
                "body": "<!-- studio:APP-001 -->",
            }
        if "/pulls/" in path:
            return {
                "body": "Closes #7",
                "head": {"sha": "head"},
                "merge_commit_sha": "merge",
                "merged_at": "date",
            }
        return {
            "check_runs": [
                {"id": 1, "name": "check", "conclusion": "success"},
                {"id": 2, "name": "check", "conclusion": "failure"},
                {"id": 3, "name": "windows", "conclusion": "success"},
            ]
        }

    monkeypatch.setattr(progress, "github", github)
    config = {
        "APP-001": {
            "issue_url": "https://github.com/student/app/issues/7",
            "pr_url": "https://github.com/student/app/pull/8",
        }
    }
    result = progress.github_evidence(config, "student/app", "APP-001")
    assert result["issue"] and result["pr"] and result["merged"]
    assert not result["ci"]
    assert "repos/student/app/commits/merge/check-runs?per_page=100" in calls


@pytest.mark.parametrize("windows", [None, "failure", "skipped", "success"])
def test_ci_requires_both_actual_platform_jobs(monkeypatch, windows):
    def github(path):
        if "/issues/" in path:
            return {
                "number": 7,
                "state": "closed",
                "created_at": "date",
                "body": "<!-- studio:APP-001 -->",
            }
        if "/pulls/" in path:
            return {
                "body": "Closes #7",
                "head": {"sha": "head"},
                "merge_commit_sha": "merge",
                "merged_at": "date",
            }
        jobs = [{"id": 1, "name": "check", "conclusion": "success"}]
        if windows:
            jobs.append({"id": 2, "name": "windows", "conclusion": windows})
        return {"check_runs": jobs}

    monkeypatch.setattr(progress, "github", github)
    config = {
        "APP-001": {
            "issue_url": "https://github.com/student/app/issues/7",
            "pr_url": "https://github.com/student/app/pull/8",
        }
    }
    result = progress.github_evidence(config, "student/app", "APP-001")
    assert result["ci"] == (windows == "success")


def test_github_cannot_borrow_another_lesson_issue(monkeypatch):
    monkeypatch.setattr(
        progress, "github", lambda _path: {"body": "<!-- studio:APP-002 -->"}
    )
    result = progress.github_evidence(
        {"APP-001": {"issue_url": "https://github.com/student/app/issues/7"}},
        "student/app",
        "APP-001",
    )
    assert not result["issue"]


def test_publication_rejects_dirty_records_and_new_unpublished_commit(workspace):
    def git(*arguments):
        return subprocess.run(
            ["git", *arguments],
            cwd=workspace,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

    git("init", "-q")
    git("config", "user.name", "Fixture")
    git("config", "user.email", "fixture@example.invalid")
    for name in ("LEARNING.md", "SPEC.md"):
        (workspace / name).write_text("Fixture record\n")
    git("add", ".")
    git("commit", "-qm", "Initial fixture")
    head = git("rev-parse", "HEAD")
    remote = {"publication_shas": [head]}
    assert all(progress.publication_state(remote).values())
    (workspace / "LEARNING.md").write_text("Unpublished new observation\n")
    assert not progress.publication_state(remote)["clean"]
    git("add", ".")
    git("commit", "-qm", "New local record")
    assert not progress.publication_state(remote)["revision_matches"]


def test_occupied_port_is_not_taken_from_another_app(monkeypatch, workspace):
    monkeypatch.setattr(studio, "require_python", lambda: Path("python"))
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]
        with pytest.raises(ValueError, match="already in use"):
            studio.run(argparse.Namespace(port=port, plain=False))


@pytest.mark.skipif(os.name == "nt", reason="POSIX TIME_WAIT restart semantics")
def test_recent_connection_does_not_block_restarting_a_stopped_app(
    monkeypatch, workspace
):
    monkeypatch.setattr(studio, "require_python", lambda: Path("prepared-python"))
    calls = []
    monkeypatch.setattr(
        subprocess, "run", lambda command, **_kwargs: calls.append(command)
    )
    with socket.socket() as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]
        with socket.create_connection(("127.0.0.1", port)) as client:
            connection, _ = listener.accept()
            connection.shutdown(socket.SHUT_WR)
            connection.close()
            assert client.recv(1) == b""
    # The server closed first, leaving a real recent connection in TIME_WAIT.
    # A plain bind recreates the student's original false port-conflict error.
    with socket.socket() as unreusable:
        with pytest.raises(OSError):
            unreusable.bind(("127.0.0.1", port))
    studio.run(argparse.Namespace(port=port, plain=True))
    assert len(calls) == 1
    assert calls[0][calls[0].index("--port") + 1] == str(port)


def test_run_uses_explicit_factory_and_loopback_settings(monkeypatch, workspace):
    monkeypatch.setattr(studio, "require_python", lambda: Path("prepared-python"))
    calls = []

    def execute(command, **kwargs):
        calls.append((command, kwargs))

    monkeypatch.setattr(subprocess, "run", execute)
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    studio.run(argparse.Namespace(port=port, plain=True))
    command, options = calls[0]
    assert "app.main:create_app" in command
    assert "--factory" in command
    assert "--no-access-log" in command
    assert command[command.index("--host") + 1] == "127.0.0.1"
    assert "--reload" not in command
    assert options["env"]["APP_ORIGIN"] == f"http://127.0.0.1:{port}"
    assert options["env"]["APP_MODE"] == "development"
    assert options["env"]["STUDIO_LIVE_RELOAD"] == "0"


def test_declared_stage_rejects_boolean_and_unknown_levels(workspace):
    for value in (True, -1, 4, "1", 1.0):
        (workspace / "studio.json").write_text(
            json.dumps({"implemented_through": value})
        )
        with pytest.raises(ValueError):
            studio.declared_stage()


def test_malformed_stage_document_is_actionable_not_a_traceback(workspace):
    (workspace / "studio.json").write_text("[]\n")
    with pytest.raises(ValueError, match="integer from 0 to 3"):
        studio.declared_stage()
    assert not progress.check_evidence("APP-001")["current"]


@pytest.mark.parametrize(
    "reference",
    [
        "Closes other/app#7",
        "Closes https://github.com/other/app/issues/7",
        "Closes #70",
        "See #7/extra",
    ],
)
def test_pr_cannot_borrow_foreign_or_ambiguous_issue_reference(monkeypatch, reference):
    def github(path):
        if "/issues/" in path:
            return {
                "number": 7,
                "state": "closed",
                "created_at": "date",
                "body": "<!-- studio:APP-001 -->",
            }
        return {"body": reference, "head": {"sha": "head"}}

    monkeypatch.setattr(progress, "github", github)
    config = {
        "APP-001": {
            "issue_url": "https://github.com/student/app/issues/7",
            "pr_url": "https://github.com/student/app/pull/8",
        }
    }
    assert not progress.github_evidence(config, "student/app", "APP-001")["pr"]


def test_fast_check_never_records_full_browser_evidence(monkeypatch, workspace):
    monkeypatch.setattr(studio, "require_python", lambda: Path("python"))
    commands = []

    def execute(command, **_kwargs):
        commands.append(command)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(subprocess, "run", execute)
    studio.check(argparse.Namespace(lesson="APP-001", fast=True))
    assert not (workspace / "runtime/check-APP-001.json").exists()
    assert not any("e2e" in command for command in commands)


def test_failed_full_check_removes_previous_receipt(monkeypatch, workspace):
    monkeypatch.setattr(studio, "require_python", lambda: Path("python"))
    progress.record_check(1, progress.source_fingerprint())
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda command, **_kwargs: subprocess.CompletedProcess(command, 1),
    )
    with pytest.raises(ValueError, match="Checks failed"):
        studio.check(argparse.Namespace(lesson="APP-001", fast=False))
    assert not (workspace / "runtime/check-APP-001.json").exists()


def test_failed_earlier_full_check_cannot_reuse_later_receipt(monkeypatch, workspace):
    (workspace / "studio.json").write_text('{"implemented_through": 3}\n')
    progress.record_check(3, progress.source_fingerprint())
    assert progress.check_evidence("APP-001")["current"]
    monkeypatch.setattr(studio, "require_python", lambda: Path("python"))
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda command, **_kwargs: subprocess.CompletedProcess(command, 1),
    )
    with pytest.raises(ValueError, match="Checks failed"):
        studio.check(argparse.Namespace(lesson="APP-001", fast=False))
    assert not progress.check_evidence("APP-001")["current"]


def test_missing_environment_full_attempt_invalidates_previous_receipt(
    monkeypatch, workspace
):
    progress.record_check(3, progress.source_fingerprint())
    monkeypatch.setattr(
        studio,
        "require_python",
        lambda: (_ for _ in ()).throw(ValueError("Missing environment")),
    )
    with pytest.raises(ValueError, match="Missing environment"):
        studio.check(argparse.Namespace(lesson="APP-001", fast=False))
    assert not list(progress.STATE.glob("check-*.json"))


def test_output_supports_symbols_even_with_redirected_windows_code_page(monkeypatch):
    buffer = io.BytesIO()
    stream = io.TextIOWrapper(buffer, encoding="cp1252")
    monkeypatch.setattr(studio.sys, "stdout", stream)
    monkeypatch.setattr(studio.sys, "stderr", stream)
    monkeypatch.delenv("PYTHONUTF8", raising=False)
    studio.prepare_output()
    print("✅ Ready")
    stream.flush()
    assert buffer.getvalue().decode("utf-8").splitlines() == ["✅ Ready"]
    assert studio.os.environ["PYTHONUTF8"] == "1"


def test_closed_issue_and_good_records_are_not_enough_without_current_checks(
    monkeypatch, workspace
):
    (workspace / "LEARNING.md").write_text(
        "## APP-001\n"
        + "\n".join(f"- {field}: Actual record." for field in progress.CHECKPOINTS)
    )
    monkeypatch.setattr(progress, "repository", lambda: "student/app")
    monkeypatch.setattr(
        progress,
        "github_evidence",
        lambda *_args: {
            "issue": True,
            "pr": True,
            "ci": True,
            "merged": True,
            "issue_state": "closed",
            "details": [],
        },
    )
    monkeypatch.setattr(
        progress,
        "publication_state",
        lambda _remote: {"tracked": True, "clean": True, "revision_matches": True},
    )
    assert not progress.status("APP-001")["ready_for_instructor_review"]


def test_role_command_reenters_virtualenv_even_when_python_is_symlinked(
    monkeypatch, workspace
):
    calls = []
    python = workspace / ".venv/bin/python"
    monkeypatch.setattr(studio, "require_python", lambda: python)
    monkeypatch.setattr(studio.sys, "prefix", str(workspace / "base-python"))
    monkeypatch.setattr(
        studio.sys, "argv", ["studio.py", "user", "role", "learner", "--role", "admin"]
    )
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda command, **_kwargs: calls.append(command),
    )
    studio.user_role(argparse.Namespace(username="learner", role="admin"))
    assert calls == [
        [
            str(python),
            str(workspace / "studio.py"),
            "user",
            "role",
            "learner",
            "--role",
            "admin",
        ]
    ]


@pytest.mark.parametrize(
    "remote,next_action,unwanted",
    [
        (
            {
                "ci": False,
                "merged": True,
                "issue_state": "closed",
                "checks": {"check": None, "windows": None},
            },
            "wait for pending check/windows jobs",
            "close the lesson issue",
        ),
        (
            {"ci": True, "merged": False, "issue_state": "open"},
            "decide whether to merge",
            "close the lesson issue",
        ),
        (
            {
                "ci": False,
                "merged": True,
                "issue_state": "closed",
                "checks": {"check": "success", "windows": "failure"},
            },
            "inspect the failed or skipped check/windows job",
            "close the lesson issue",
        ),
        (
            {"ci": True, "merged": True, "issue_state": "open"},
            "close the lesson issue",
            "decide whether to merge",
        ),
    ],
)
def test_progress_names_the_actual_remaining_publication_step(
    capsys, remote, next_action, unwanted
):
    result = {
        "lesson": "APP-001",
        "checks": {"current": True},
        "learner_records": {name: True for name in progress.CHECKPOINTS},
        "publication": {"tracked": True, "clean": True, "revision_matches": True},
        "github": {"issue": True, "pr": True, "details": [], **remote},
        "ready_for_instructor_review": False,
    }
    progress.display(result)
    output = capsys.readouterr().out
    assert next_action in output
    assert unwanted not in output
    assert "Evidence ready for instructor review" not in output
