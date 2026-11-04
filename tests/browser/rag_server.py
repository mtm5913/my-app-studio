"""Isolated browser fixture only: real HTTP streaming, fake provider, no API spend."""

import asyncio

from app.main import create_app as application_factory
from app import food_ai


async def fixture_stream(_config, question, _history, _passages):
    """A pause after the first delta lets Chromium prove incremental rendering."""
    yield {"type": "delta", "text": "Whole grains contain "}
    await asyncio.sleep(1)
    if "interrupt" in question.lower():
        yield {"type": "error", "message": "The test provider disconnected."}
        return
    yield {"type": "delta", "text": "bran, germ and endosperm. [1]"}
    yield {"type": "done"}


def create_app():
    """Only the test subprocess imports this replacement provider."""
    food_ai.stream_grounded = fixture_stream
    return application_factory()
