"""End-to-end tests through the Flask test client.

Runs with no ANTHROPIC_API_KEY on purpose. Playing keylessly is a supported
state -- it is what makes "deploy first, add the key second" safe -- so the
whole loop has to work with fallback names, and these tests are the proof.
"""

from __future__ import annotations

import os

import pytest


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("BASE_PATH", "")

    from game import store

    store.reset_for_tests()
    import importlib

    import app as app_module

    importlib.reload(app_module)
    app_module.app.config.update(TESTING=True)
    with app_module.app.test_client() as c:
        yield c
    store.reset_for_tests()


def new_player(client, name="Tester"):
    res = client.post("/api/new", json={"name": name})
    assert res.status_code == 201
    return res.get_json()["player"]


def state(client, pid):
    res = client.get("/api/state", headers={"X-Player": pid})
    assert res.status_code == 200
    return res.get_json()


def test_health_works_without_an_api_key(client):
    res = client.get("/health")
    assert res.status_code == 200
    body = res.get_json()
    assert body["ok"] is True
    # The whole point: no key is a reported state, not a failure.
    assert body["llm"] == "unconfigured"
    assert body["tiers_available"] == 3


def test_unknown_player_is_rejected(client):
    assert client.get("/api/state").status_code == 401
    assert client.get("/api/state", headers={"X-Player": "nope"}).status_code == 401


def test_a_new_player_can_craft_immediately(client):
    """The opening must offer a craft, not a wait.

    v1's complaint #1 was "if you are one of the first players you just wait a
    while". A new player here lands with two producers running and one of each
    in stock, so the first move available is a discovery.
    """
    pid = new_player(client)
    s = state(client, pid)

    assert s["coins"] == 30
    assert s["ceiling"] == 1
    held = {i["key"]: i["held"] for i in s["items"]}
    assert held["clay"] >= 1 and held["water"] >= 1
    assert len(s["yard"]) == 2
    assert s["yard_used"] < s["yard_slots"], "must have room to build"


def test_crafting_at_ceiling_one_is_a_free_dud(client):
    """Nothing exists above the starters until tier 2 is bought, so the craft
    must be refused free of charge rather than half-charged."""
    pid = new_player(client)
    before = state(client, pid)["coins"]

    res = client.post("/api/craft", json={"a": "clay", "b": "water"},
                      headers={"X-Player": pid})
    assert res.status_code == 200
    assert res.get_json()["dud"] is True

    assert state(client, pid)["coins"] == before, "a dud must never cost coins"


def unlock_to(client, pid, tier):
    """Grant coins and buy up to `tier`. Uses the real endpoint so the unlock
    path itself is exercised rather than bypassed."""
    from game import store

    for target in range(2, tier + 1):
        from game import economy

        store.set_coins(pid, economy.unlock_cost(target) + 500)
        res = client.post("/api/unlock", headers={"X-Player": pid})
        assert res.status_code == 200, res.get_json()
        assert res.get_json()["ceiling"] == target


def test_the_full_loop(client):
    """Craft, discover, place a factory, let it run, sell, unlock."""
    pid = new_player(client)
    unlock_to(client, pid, 2)

    res = client.post("/api/craft", json={"a": "clay", "b": "water"},
                      headers={"X-Player": pid})
    assert res.status_code == 201, res.get_json()
    body = res.get_json()
    assert body["dud"] is False
    assert body["new_to_you"] is True
    assert body["first_in_world"] is True

    mud = body["item"]
    assert mud["tier"] == 2
    assert mud["bucket"] == "mud"
    assert mud["provisional"] is True, "no API key, so the name is a fallback"
    assert mud["name"], "even a fallback must produce a usable name"

    # The inputs were consumed -- this is a production chain, not a copier.
    s = state(client, pid)
    held = {i["key"]: i["held"] for i in s["items"]}
    assert held.get("clay", 0) == 0
    assert held.get(mud["key"], 0) == 1

    # Selling it back gives tier-2 money.
    res = client.post("/api/sell", json={"item": mud["key"], "all": True},
                      headers={"X-Player": pid})
    assert res.status_code == 200
    assert res.get_json()["coins"] == mud["sells_for"]


def test_the_same_pair_is_only_a_first_discovery_once(client):
    """Second player, same combination: instant, free, and credited to the
    first. This is what makes the shared registry worth having."""
    from game import store

    a = new_player(client, "Alex")
    b = new_player(client, "Sam")
    for pid in (a, b):
        unlock_to(client, pid, 2)
        store.set_coins(pid, 500)

    first = client.post("/api/craft", json={"a": "clay", "b": "water"},
                        headers={"X-Player": a}).get_json()
    assert first["first_in_world"] is True

    # Sam needs stock again; the first craft ate it.
    store.write_stock(b, {"clay": 2, "water": 2})
    second = client.post("/api/craft", json={"a": "clay", "b": "water"},
                         headers={"X-Player": b}).get_json()
    assert second["first_in_world"] is False
    assert second["new_to_you"] is True
    assert second["item"]["name"] == first["item"]["name"]
    assert second["item"]["first_by"] == "Alex"


def test_cannot_craft_without_stock(client):
    pid = new_player(client)
    unlock_to(client, pid, 2)
    from game import store

    store.write_stock(pid, {"clay": 1})   # no water
    res = client.post("/api/craft", json={"a": "clay", "b": "water"},
                      headers={"X-Player": pid})
    assert res.status_code == 400
    assert res.get_json()["kind"] == "stock"


def test_cannot_craft_without_coins(client):
    pid = new_player(client)
    unlock_to(client, pid, 2)
    from game import store

    store.set_coins(pid, 0)
    store.write_stock(pid, {"clay": 2, "water": 2})
    res = client.post("/api/craft", json={"a": "clay", "b": "water"},
                      headers={"X-Player": pid})
    assert res.status_code == 400
    assert res.get_json()["kind"] == "coins"


def test_cannot_automate_something_undiscovered(client):
    """A hand-written POST must not be able to invent a recipe. v1 trusted
    client-supplied values in more than one place and handed out free money."""
    from game import store

    pid = new_player(client)
    unlock_to(client, pid, 2)
    store.set_coins(pid, 5000)

    res = client.post(
        "/api/place",
        json={"kind": "factory", "output": "mud<clay+water"},
        headers={"X-Player": pid},
    )
    assert res.status_code == 400
    assert "not discovered" in res.get_json()["error"]


def test_cannot_automate_a_starter(client):
    """Starters have no recipe, so there is nothing to automate."""
    from game import store

    pid = new_player(client)
    store.set_coins(pid, 5000)
    res = client.post("/api/place", json={"kind": "factory", "output": "clay"},
                      headers={"X-Player": pid})
    assert res.status_code == 400
    assert res.get_json()["error"] == "that cannot be automated"


def test_cannot_automate_a_recipe_above_your_tier(client):
    """Discovered at ceiling 3, then somehow back at ceiling 2: the factory must
    be refused rather than quietly producing above the ceiling."""
    from game import store

    pid = new_player(client)
    unlock_to(client, pid, 3)
    store.set_coins(pid, 50000)
    store.write_stock(pid, {"clay": 20, "water": 20})
    mud = client.post("/api/craft", json={"a": "clay", "b": "water"},
                      headers={"X-Player": pid}).get_json()["item"]
    # mud + ember: {mineral, wet} + {hot} -> ceramic at tier 3.
    store.write_stock(pid, {"ember": 5, mud["key"]: 5})
    ceramic = client.post("/api/craft", json={"a": mud["key"], "b": "ember"},
                          headers={"X-Player": pid}).get_json()
    assert ceramic.get("dud") is False, ceramic
    assert ceramic["item"]["tier"] == 3

    store.set_ceiling(pid, 2)
    res = client.post("/api/place",
                      json={"kind": "factory", "output": ceramic["item"]["key"]},
                      headers={"X-Player": pid})
    assert res.status_code == 400
    assert res.get_json()["kind"] == "tier"


def test_a_factory_produces_over_time(client):
    from game import store

    pid = new_player(client)
    unlock_to(client, pid, 2)
    store.set_coins(pid, 5000)
    mud = client.post("/api/craft", json={"a": "clay", "b": "water"},
                      headers={"X-Player": pid}).get_json()["item"]

    res = client.post(
        "/api/place",
        json={"kind": "factory", "output": mud["key"], "autosell": True},
        headers={"X-Player": pid},
    )
    assert res.status_code == 201, res.get_json()

    # Give it inputs and wind the clock back so the next tick sees elapsed time.
    store.write_stock(pid, {"clay": 50, "water": 50})
    conn = store.connect()
    conn.execute("UPDATE players SET last_tick = last_tick - 120 WHERE id=?", (pid,))
    conn.commit()

    before = store.get_player(pid)["coins"]
    store.tick_player(pid)
    after = store.get_player(pid)["coins"]
    assert after > before, "an autosell factory with inputs must earn coins"


def test_hand_gather_has_a_server_side_cooldown(client):
    pid = new_player(client)
    placement = state(client, pid)["yard"][0]["id"]

    first = client.post("/api/gather", json={"placement": placement},
                        headers={"X-Player": pid})
    assert first.status_code == 200

    second = client.post("/api/gather", json={"placement": placement},
                         headers={"X-Player": pid})
    assert second.status_code == 429, "the cooldown must be enforced server-side"


def test_yard_slots_are_enforced(client):
    from game import store

    pid = new_player(client)
    store.set_coins(pid, 100000)
    # Two producers already placed; fill the rest of the tier-1 yard.
    for bucket in ("seed", "ember"):
        res = client.post("/api/place", json={"kind": "producer", "item": bucket},
                          headers={"X-Player": pid})
        assert res.status_code == 201, res.get_json()

    res = client.post("/api/place", json={"kind": "producer", "item": "seed"},
                      headers={"X-Player": pid})
    assert res.status_code == 400
    assert res.get_json()["kind"] == "slots"


def test_unlock_stops_at_authored_content(client):
    from game import store

    pid = new_player(client)
    unlock_to(client, pid, 3)
    store.set_coins(pid, 10_000_000)
    res = client.post("/api/unlock", headers={"X-Player": pid})
    assert res.status_code == 400
    assert res.get_json()["kind"] == "max"


def test_removing_a_placement_refunds_half(client):
    from game import store

    pid = new_player(client)
    store.set_coins(pid, 1000)
    placed = client.post("/api/place", json={"kind": "producer", "item": "ember"},
                         headers={"X-Player": pid}).get_json()
    before = store.get_player(pid)["coins"]
    res = client.post("/api/remove", json={"placement": placed["placed"]},
                      headers={"X-Player": pid})
    assert res.status_code == 200
    assert res.get_json()["refund"] == placed["cost"] // 2
    assert store.get_player(pid)["coins"] == before + placed["cost"] // 2


def test_resume_link_works(client):
    """No passwords: the id is the credential, handed back as ?p= so a player
    can come back on another device."""
    pid = new_player(client)
    res = client.get(f"/api/state?p={pid}")
    assert res.status_code == 200
    assert res.get_json()["ceiling"] == 1


def test_offline_time_is_credited_on_the_next_request(client):
    """The v1 bug, at the API level: come back later and the yard has worked."""
    from game import store

    pid = new_player(client)
    conn = store.connect()
    conn.execute("UPDATE players SET last_tick = last_tick - 600 WHERE id=?", (pid,))
    conn.commit()

    s = state(client, pid)
    held = {i["key"]: i["held"] for i in s["items"]}
    # 600s of a 6s clay pit and a 5s well, minus the one of each we started with.
    assert held["clay"] > 90, f"expected ~100 clay from ten minutes, got {held}"
    assert held["water"] > 110
    assert s["offline"]["seconds_applied"] == pytest.approx(600, abs=5)


def test_feed_credits_the_finder(client):
    from game import store

    pid = new_player(client)
    unlock_to(client, pid, 2)
    store.set_coins(pid, 500)
    client.post("/api/craft", json={"a": "clay", "b": "water"},
                headers={"X-Player": pid})

    feed = client.get("/api/feed").get_json()["feed"]
    assert feed and feed[0]["by"] == "Tester"


def test_a_self_pair_key_is_not_offered_as_automatable(client):
    """`_ensure_producer_output` mints keys like `charcoal<charcoal+charcoal` for a
    producer whose output nobody has crafted. X + X is always a dud, so offering
    to automate it would fail with a confusing "above your tier" message."""
    from game import store

    pid = new_player(client)
    store.set_coins(pid, 100000)
    store.put_item("charcoal<charcoal+charcoal", "charcoal", "Test Coal", "\U0001f525",
                   "", None, True)
    store.record_discovery(pid, "charcoal<charcoal+charcoal")

    item = next(i for i in state(client, pid)["items"]
                if i["key"] == "charcoal<charcoal+charcoal")
    assert item["automatable"] is False

    res = client.post("/api/place",
                      json={"kind": "factory", "output": "charcoal<charcoal+charcoal"},
                      headers={"X-Player": pid})
    assert res.status_code == 400
    assert res.get_json()["error"] == "that cannot be automated"
