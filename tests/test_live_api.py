"""Smoke-test the real container over HTTP.

The in-process tests in `test_api.py` cover behaviour. This covers the things
only a real container can be wrong about: that BASE_PATH stripping works
end-to-end, that the API answers under the mount prefix, and that a brand-new
player can complete a craft with no ANTHROPIC_API_KEY set.

    BASE_URL=http://127.0.0.1:8081/tycooncraft pytest tests/test_live_api.py
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

import pytest

pytestmark = pytest.mark.live

BASE_URL = os.environ.get("BASE_URL")


@pytest.fixture(scope="module")
def base() -> str:
    if not BASE_URL:
        pytest.skip("set BASE_URL to run the live API test")
    return BASE_URL.rstrip("/") + "/"


def call(url: str, body=None, player: str | None = None):
    headers = {"Content-Type": "application/json"}
    if player:
        headers["X-Player"] = player
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, headers=headers,
                                     method="POST" if data else "GET")
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return response.status, json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as err:
        return err.code, json.loads(err.read() or b"{}")


def test_health_reports_the_mount_and_the_key_state(base):
    status, body = call(base + "health")
    assert status == 200
    assert body["ok"] is True
    assert body["app"] == "tycooncraft"
    # The prefix the container was told to serve, echoed back. If this is "/"
    # while BASE_URL has a prefix, BASE_PATH never reached the process.
    assert body["base"] in ("/", "/tycooncraft")
    assert body["llm"] in ("ready", "unconfigured")


def test_a_new_player_can_craft_over_http(base):
    """The whole loop, through the real container, with no API key configured."""
    status, body = call(base + "api/new", {"name": "SmokeTest"})
    assert status == 201, body
    player = body["player"]

    status, state = call(base + "api/state", player=player)
    assert status == 200, state
    held = {i["key"]: i["held"] for i in state["items"]}
    assert held.get("clay", 0) >= 1 and held.get("water", 0) >= 1, (
        "a new player must start able to craft, not waiting"
    )
    assert state["ceiling"] == 1

    # At ceiling 1 there is nothing above the starters, so this must be a free
    # dud rather than an error or a charge.
    status, dud = call(base + "api/craft", {"a": "clay", "b": "water"}, player=player)
    assert status == 200, dud
    assert dud["dud"] is True
    assert dud["reason"]

    status, after = call(base + "api/state", player=player)
    assert after["coins"] == state["coins"], "a dud must not cost coins"


def test_unknown_player_is_rejected_over_http(base):
    status, _ = call(base + "api/state", player="not-a-real-id")
    assert status == 401


def test_the_page_and_its_stylesheet_are_served(base):
    with urllib.request.urlopen(base, timeout=10) as response:
        assert response.status == 200
        html = response.read().decode()
    assert "TycoonCraft" in html
    with urllib.request.urlopen(base + "src/style.css", timeout=10) as response:
        assert response.status == 200
