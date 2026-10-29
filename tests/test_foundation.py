"""Foundation checks pass without claiming that student features are finished."""

import json

import pytest

from app import branding


def test_home_and_health_are_real_routes(client):
    """The starting page runs through FastAPI and references real local assets."""
    page = client.get("/")
    assert page.status_code == 200
    assert '<html lang="en">' in page.text
    assert 'href="/static/site.css"' in page.text
    assert client.get("/static/site.css").status_code == 200
    assert client.get("/static/logo.svg").status_code == 200
    assert client.get("/docs").status_code == 200
    assert "cdn.jsdelivr" not in client.get("/docs").text
    assert "/health" in client.get("/openapi.json").json()["paths"]
    assert client.get("/health").json() == {"status": "ok", "mode": "development"}


def test_unknown_route_and_security_headers(client):
    """A working homepage must not make unknown routes or framing acceptable."""
    assert client.get("/not-a-feature").status_code == 404
    response = client.get("/")
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert response.headers["cache-control"] == "no-store"


def test_brand_text_is_escaped(client, tmp_path, monkeypatch):
    """Content is data, not a route for an HTML script to execute."""
    brand = branding.load_brand()
    brand["headline"] = '<script>alert("never")</script>'
    path = tmp_path / "brand.json"
    path.write_text(json.dumps(brand))
    monkeypatch.setattr(branding, "BRAND_FILE", path)
    response = client.get("/")
    assert "<script>alert" not in response.text
    assert "&lt;script&gt;" in response.text


def test_css_tokens_reject_executable_syntax(tmp_path, monkeypatch):
    """Only expected color values enter the generated CSS."""
    brand = branding.load_brand()
    brand["palette"]["accent"] = "red;} body{background:url(https://other.invalid)"
    path = tmp_path / "brand.json"
    path.write_text(json.dumps(brand))
    monkeypatch.setattr(branding, "BRAND_FILE", path)
    with pytest.raises(ValueError, match="six-digit"):
        branding.stylesheet()


def test_plain_mode_disables_browser_refresh(client):
    """The ordinary refresh endpoint reports an observation, not runtime secrets."""
    response = client.get("/__studio/revision")
    assert response.status_code == 200
    assert set(response.json()) == {"revision"}
    client.app.state.live_reload = False
    assert client.get("/__studio/revision").status_code == 404
    assert "/static/live.js" not in client.get("/").text
