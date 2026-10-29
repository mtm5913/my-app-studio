"""Show actual evidence gaps without grading learning or trusting timestamps alone."""

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "runtime"
INSTRUCTOR = "kaw393939/is373-app-studio"
REQUIRED_JOBS = {"check", "windows"}
CHECKPOINTS = (
    "Prediction",
    "Check interpretation",
    "Browser observation",
    "Keep decision",
    "Review",
)


def lesson_number(value):
    """Accept only the three named lessons, preventing path or command injection."""
    match = re.fullmatch(r"APP-00([123])", value)
    if not match:
        raise ValueError("Choose APP-001, APP-002 or APP-003.")
    return int(match.group(1))


def save_json(path, value):
    """Write local records atomically; generated progress stays out of Git."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary.chmod(0o600)
    temporary.replace(path)


def configuration():
    """A student can start without a configured issue or a pasted GitHub token."""
    path = STATE / "progress.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def source_fingerprint():
    """Invalidate receipts when app code, checks or their configuration changes."""
    files = [
        ROOT / name
        for name in ("studio.py", "studio.json", "pyproject.toml", "conftest.py")
    ]
    files.extend(ROOT.glob("requirements*.txt"))
    for folder in ("app", "studio_tools", "tests", "contracts", ".github/workflows"):
        files.extend((ROOT / folder).rglob("*"))
    digest = hashlib.sha256()
    for path in sorted(set(files)):
        if (
            path.is_file()
            and not path.is_symlink()
            and "__pycache__" not in path.parts
            and path.suffix not in {".pyc", ".sqlite", ".db"}
        ):
            digest.update(path.relative_to(ROOT).as_posix().encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def record_check(level, fingerprint):
    """Record a real full command result; this is a local receipt, not a certificate."""
    name = f"APP-{level:03}" if level else "foundation"
    save_json(
        STATE / f"check-{name}.json",
        {
            "status": "passed",
            "implemented_through": level,
            "source_fingerprint": fingerprint,
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "scope": "Black, Pylint, pytest and actual Chromium journeys",
            "browser": "passed",
        },
    )


def check_evidence(lesson):
    """A foundation pass never stands in for unfinished feature contracts."""
    required = lesson_number(lesson)
    stage_document = json.loads((ROOT / "studio.json").read_text(encoding="utf-8"))
    declared = (
        stage_document.get("implemented_through")
        if isinstance(stage_document, dict)
        else None
    )
    if (
        not isinstance(declared, int)
        or isinstance(declared, bool)
        or declared not in range(required, 4)
    ):
        return {"current": False, "observed_at": None}
    fingerprint = source_fingerprint()
    for level in range(3, required - 1, -1):
        path = STATE / f"check-APP-{level:03}.json"
        if path.exists():
            report = json.loads(path.read_text(encoding="utf-8"))
            if (
                report.get("status") == "passed"
                and report.get("implemented_through", 0) >= required
                and report.get("source_fingerprint") == fingerprint
                and report.get("browser") == "passed"
            ):
                return {"current": True, "observed_at": report.get("observed_at")}
    return {"current": False, "observed_at": None}


def repository():
    """Use the class SSH remote and keep evidence inside the student's own copy."""
    result = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    match = re.fullmatch(
        r"git@github\.com:([\w.-]+/[\w.-]+?)(?:\.git)?\s*", result.stdout
    )
    if not match:
        raise ValueError("Use your GitHub SSH clone: git@github.com:USERNAME/REPO.git")
    return match.group(1)


def issue_number(url, repo, kind="issues"):
    """Reject unrelated repositories and ambiguous URLs used as evidence."""
    match = re.fullmatch(
        rf"https://github\.com/{re.escape(repo)}/{kind}/([1-9]\d*)", url
    )
    if not match:
        raise ValueError(f"Use an actual {kind} URL in your repository: {repo}")
    return int(match.group(1))


def github(path):
    """Read public GitHub state; an existing optional token is never displayed."""
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "IS373-Studio"}
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request("https://api.github.com/" + path, headers=headers)
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.load(response)


def github_evidence(config, repo, lesson):
    """Check the real issue, linked PR and latest check at the selected PR revision."""
    result = {"issue": False, "pr": False, "ci": False, "merged": False, "details": []}
    links = config.get(lesson, {})
    if not links.get("issue_url"):
        result["details"].append(
            f"Create your {lesson} issue and record its actual URL."
        )
        return result
    try:
        number = issue_number(links["issue_url"], repo)
        issue = github(f"repos/{repo}/issues/{number}")
        if issue.get("pull_request") or f"<!-- studio:{lesson} -->" not in (
            issue.get("body") or ""
        ):
            raise ValueError(f"The issue must use the {lesson} lesson template.")
        result.update(
            issue=True, issue_state=issue["state"], issue_created_at=issue["created_at"]
        )
        if not links.get("pr_url"):
            result["details"].append("Publish the reviewed work in a PR and link it.")
            return result
        number = issue_number(links["pr_url"], repo, "pull")
        pull = github(f"repos/{repo}/pulls/{number}")
        reference = (
            rf"(?:(?<![\w/#])#|https://github\.com/{re.escape(repo)}/issues/)"
            rf"{issue['number']}(?![\w/?#])"
        )
        if not re.search(reference, pull.get("body") or ""):
            raise ValueError("The PR body must reference your actual lesson issue.")
        result.update(
            pr=True,
            merged=bool(pull.get("merged_at")),
            publication_shas=[
                sha
                for sha in (pull["head"]["sha"], pull.get("merge_commit_sha"))
                if sha
            ],
        )
        commit = pull.get("merge_commit_sha") or pull["head"]["sha"]
        checks = github(f"repos/{repo}/commits/{commit}/check-runs?per_page=100")
        latest = {}
        for row in sorted(checks.get("check_runs", []), key=lambda item: item["id"]):
            latest[row["name"]] = row
        result["ci"] = all(
            latest.get(name, {}).get("conclusion") == "success"
            for name in REQUIRED_JOBS
        )
        result["checks"] = {
            name: latest.get(name, {}).get("conclusion", "not found")
            for name in sorted(REQUIRED_JOBS)
        }
        if not result["ci"]:
            result["details"].append(
                "Required check/windows jobs are missing, pending or failed."
            )
    except (ValueError, KeyError, OSError, urllib.error.URLError) as error:
        result["details"].append(
            f"GitHub evidence not verified: {error}. "
            "Ask your coach; do not paste a token."
        )
    return result


def learner_sections(text, lesson):
    """Detect missing records without claiming understanding or authorship."""
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    section = re.search(
        rf"^## {re.escape(lesson)}\b[^\n]*\n(.*?)(?=^## |\Z)", text, re.M | re.S
    )
    content = section.group(1) if section else ""
    pending = re.compile(
        r"^(pending|not yet evidenced|not recorded|not reviewed|"
        r"earlier conversation unavailable)\b",
        re.I,
    )
    records = {}
    for name in CHECKPOINTS:
        match = re.search(
            rf"^- \*?\*?{re.escape(name)}\*?\*?:\s*(.*?)(?=^- |\Z)",
            content,
            re.M | re.S,
        )
        value = match.group(1).strip().strip("*_` ") if match else ""
        records[name] = bool(value) and not pending.match(value)
    return records


def publication_state(remote):
    """Unpublished local edits cannot borrow an earlier green merged PR."""
    result = {"tracked": False, "clean": False, "revision_matches": False}
    try:

        def git(*arguments):
            return subprocess.run(
                ["git", *arguments],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()

        git("ls-files", "--error-unmatch", "LEARNING.md", "SPEC.md", "studio.json")
        result["tracked"] = True
        result["clean"] = not git("status", "--porcelain")
        result["revision_matches"] = git("rev-parse", "HEAD") in remote.get(
            "publication_shas", []
        )
    except (OSError, subprocess.CalledProcessError):
        pass
    return result


def status(lesson, online=True):
    """Combine independent technical, learner-record and publication observations."""
    repo = repository()
    records = learner_sections(
        (ROOT / "LEARNING.md").read_text(encoding="utf-8"), lesson
    )
    checks = check_evidence(lesson)
    remote = (
        github_evidence(configuration(), repo, lesson)
        if online
        else {"details": ["GitHub not checked (--offline)."]}
    )
    publication = publication_state(remote)
    ready = bool(
        checks["current"]
        and all(records.values())
        and all(publication.values())
        and all(remote.get(key) for key in ("issue", "pr", "ci", "merged"))
        and remote.get("issue_state") == "closed"
    )
    return {
        "lesson": lesson,
        "checks": checks,
        "learner_records": records,
        "github": remote,
        "publication": publication,
        "ready_for_instructor_review": ready,
        "scope": (
            "Record presence and selected checks; "
            "no automatic grade or proof of learning."
        ),
    }


def display(result):
    """Use one next action, avoiding a wall of demands during the conversation."""
    print(result["lesson"] + " · Evidence status")
    print(
        ("✅ Current" if result["checks"]["current"] else "🟡 Needed")
        + ": full feature checks, including Chromium"
    )
    for name, recorded in result["learner_records"].items():
        print(("✅ Recorded: " if recorded else "🟡 Needed: ") + name)
    for detail in result["github"]["details"]:
        print("🟡 " + detail)
    if result["ready_for_instructor_review"]:
        print("✅ Evidence ready for instructor review. This is not a grade.")
    elif not result["learner_records"]["Prediction"]:
        print(
            "👉 Next: discuss your prediction with your coach before the plan. "
            "Preserve any earlier gap; do not invent a prediction after implementation."
        )
    elif not result["checks"]["current"]:
        print("👉 Next: ask your coach to run the full check for this feature.")
    elif not all(result["learner_records"].values()):
        missing = next(
            name for name, recorded in result["learner_records"].items() if not recorded
        )
        print("👉 Next: discuss " + missing.lower() + " using your actual experience.")
    else:
        print("👉 Next: " + publication_next_step(result))


def publication_next_step(result):
    """Respond to the actual pending GitHub step instead of reopening finished work."""
    publication = result["publication"]
    remote = result["github"]
    prerequisites = (
        (
            not publication["tracked"] or not publication["clean"],
            "publish your reviewed work and return to a clean Git revision.",
        ),
        (
            not remote.get("issue"),
            "ask your coach to verify your actual lesson issue link.",
        ),
        (
            not remote.get("pr"),
            "publish the reviewed work in a PR and record its actual link.",
        ),
    )
    for missing, action in prerequisites:
        if missing:
            return action
    if not remote.get("ci"):
        return ci_next_step(remote)
    if not publication["revision_matches"]:
        return "use the clean revision from your linked PR; your coach can help."
    if not remote.get("merged"):
        return "review the passing PR with your coach and decide whether to merge it."
    if remote.get("issue_state") == "open":
        return "review the kept result with your coach, then close the lesson issue."
    return (
        "ask your coach to verify the remaining GitHub evidence; "
        "completion is unverified."
    )


def ci_next_step(remote):
    """Distinguish a running or missing job from a completed unsuccessful one."""
    conclusions = remote.get("checks", {}).values()
    if any(value not in {None, "not found", "success"} for value in conclusions):
        return (
            "inspect the failed or skipped check/windows job with your coach, "
            "fix the cause and rerun the checks."
        )
    return (
        "wait for pending check/windows jobs to finish; "
        "ask your coach to inspect the PR if either job is missing."
    )
