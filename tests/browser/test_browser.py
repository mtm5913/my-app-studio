"""Real Chromium checks; each run names its actual implemented lesson scope."""

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid

import pytest
from playwright.sync_api import expect

ROOT = Path(__file__).resolve().parents[2]
LEVEL = int(os.getenv("APP_TEST_LESSON", "0"))
pytestmark = pytest.mark.e2e


@dataclass
class BrowserServer:
    """Keep inherited process configuration out of assertion reports."""

    url: str
    environment: dict = field(repr=False)


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    """Start only an isolated loopback fixture with temporary account data."""
    directory = tmp_path_factory.mktemp("app-browser")
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    url = f"http://127.0.0.1:{port}"
    environment = dict(
        os.environ,
        APP_MODE="development",
        APP_ORIGIN=url,
        APP_DATABASE=str(directory / "browser.sqlite3"),
        APP_SECRET="disposable-browser-test-key-" + uuid.uuid4().hex,
        STUDIO_LIVE_RELOAD="0",
    )
    with (directory / "server.log").open("w") as output:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:create_app",
                "--factory",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            cwd=ROOT,
            env=environment,
            stdout=output,
            stderr=subprocess.STDOUT,
        )
        try:
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                try:
                    with urllib.request.urlopen(url + "/health", timeout=1) as response:
                        assert json.load(response)["status"] == "ok"
                    break
                except (OSError, urllib.error.URLError):
                    if process.poll() is not None:
                        raise RuntimeError(
                            "Isolated browser app failed to start"
                        ) from None
                    time.sleep(0.1)
            else:
                raise RuntimeError("Isolated browser app did not become ready")
            yield BrowserServer(url=url, environment=environment)
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def test_homepage_keyboard_and_mobile_layout(page, server):
    """Check real rendering/navigation, including a narrow viewport and keyboard."""
    page.goto(server.url)
    expect(page.get_by_role("heading", level=1)).to_be_visible()
    page.keyboard.press("Tab")
    expect(page.get_by_role("link", name="Skip to content")).to_be_focused()
    page.keyboard.press("Enter")
    expect(page.locator("#main")).to_be_focused()
    page.set_viewport_size({"width": 390, "height": 844})
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    assert (
        page.locator(".button").evaluate(
            "element => element.getBoundingClientRect().height"
        )
        >= 44
    )
    assert page.get_by_role("navigation", name="Main navigation").is_visible()
    if LEVEL >= 1:
        expect(page.get_by_text("Your Project", exact=True)).to_have_count(0)


def test_current_lesson_browser_journey(page, server):
    """Only implemented scope is claimed; stage zero is explicitly foundation only."""
    page.goto(server.url)
    if LEVEL < 2:
        primary = page.locator(".hero .button")
        destination = primary.get_attribute("href")
        assert destination and destination.startswith("#") and len(destination) > 1
        primary.click()
        expect(page.locator(destination)).to_be_in_viewport()
        assert page.request.get(server.url + "/signup").status == 404
        assert page.request.get(server.url + "/not-a-feature").status == 404
        return
    username = "browser_" + uuid.uuid4().hex[:10]
    password = "a disposable browser passphrase"
    page.goto(server.url + "/signup")
    page.get_by_label("Username", exact=True).fill(username)
    page.get_by_label("Password", exact=True).fill(password)
    page.get_by_role("button", name="Create account", exact=True).click()
    expect(page.get_by_role("heading", name="Log in", exact=True)).to_be_visible()
    page.get_by_label("Username", exact=True).fill(username)
    page.get_by_label("Password", exact=True).fill("the wrong disposable passphrase")
    page.get_by_role("button", name="Log in", exact=True).click()
    expect(page.get_by_role("alert")).to_be_visible()
    page.get_by_label("Username", exact=True).fill(username)
    page.get_by_label("Password", exact=True).fill(password)
    page.get_by_role("button", name="Log in", exact=True).click()
    expect(
        page.get_by_role("heading", name="Your member space", exact=True)
    ).to_be_visible()
    cookies = page.context.cookies()
    session = next(cookie for cookie in cookies if cookie["name"] == "studio-session")
    assert session["httpOnly"] and session["sameSite"] == "Lax"
    if LEVEL >= 3:
        _check_role_boundary(page, server, username)
    page.goto(server.url + "/dashboard")
    page.get_by_role("button", name="Log out", exact=True).click()
    assert page.request.get(server.url + "/api/me").status == 401
    replay = page.request.get(
        server.url + "/api/me",
        headers={"Cookie": session["name"] + "=" + session["value"]},
    )
    assert replay.status == 401
    page.goto(server.url + "/dashboard")
    expect(page.get_by_role("heading", name="Log in", exact=True)).to_be_visible()


def _check_role_boundary(page, server, username):
    """The trusted CLI changes DB roles; an existing JWT never overrides the DB."""
    assert page.request.get(server.url + "/api/admin").status == 403
    page.goto(server.url + "/admin")
    expect(
        page.get_by_role("heading", name="Admin access required", exact=True)
    ).to_be_visible()
    for role, status in (("admin", 200), ("member", 403)):
        subprocess.run(
            [sys.executable, "studio.py", "user", "role", username, "--role", role],
            cwd=ROOT,
            env=server.environment,
            check=True,
            capture_output=True,
            text=True,
        )
        assert page.request.get(server.url + "/api/admin").status == status
        if role == "admin":
            page.goto(server.url + "/admin")
            expect(
                page.get_by_role("heading", name="Administration", exact=True)
            ).to_be_visible()
