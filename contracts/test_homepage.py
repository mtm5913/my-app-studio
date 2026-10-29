"""APP-001 acceptance: an agreed real brand replaces the neutral starter."""

import re

from app.branding import load_brand


def test_brand_brief_has_decisions():
    """Check record presence and coherent output; a human evaluates the design."""
    brand = load_brand()
    for key in ("name", "audience", "promise", "archetype", "design_direction"):
        assert brand[key].strip() not in {"", "Not chosen yet", "Your Project"}, key
    assert len(brand["voice"]) >= 2
    assert "Not chosen yet" not in brand["voice"]
    assert len(set(brand["palette"].values())) >= 3


def test_chosen_brand_reaches_the_homepage(client):
    """The saved brief must appear in the actual rendered page, not only a file."""
    brand = load_brand()
    response = client.get("/")
    assert response.status_code == 200
    assert brand["name"] in response.text
    assert brand["headline"] in response.text
    assert brand["promise"] in response.text
    assert "Your Project" not in response.text
    assert re.search(r"<h1[^>]*>[^<]+</h1>", response.text)
    assert (
        client.get("/static/logo.svg")
        .headers["content-type"]
        .startswith("image/svg+xml")
    )
