"""TycoonCraft -- HTTP layer.

Two things here are load-bearing for the platform contract:

* **BASE_PATH is stripped defensively.** nginx proxies `/tycooncraft/` to us with
  the prefix already removed, so we see `/`. But the *browser* is at
  `/tycooncraft/`, and stripping it ourselves anyway means the app serves
  correctly both proxied and hit directly -- which is what makes the CI smoke
  test able to check the real deployed configuration.

* **`/health` answers without an API key.** A missing key is a supported state,
  not an outage: items fall back to deterministic names and health says
  `{"llm": "unconfigured"}`. That is what makes it safe to deploy first and add
  the key second.

Auth is a player id in an `X-Player` header, kept in the browser's localStorage
and also accepted as `?p=` for the resume link. No cookies at all, which means
no CSRF surface to get wrong -- a custom header cannot be set by a cross-origin
form post.
"""

from __future__ import annotations

import os
import time
from typing import Optional, Tuple

from flask import Flask, jsonify, request, send_from_directory

from game import buckets, economy, naming, store
from game.buckets import ALL, BY_ID, PRODUCERS
from game.traits import Bucket, Dud, combine

BASE_PATH = (os.environ.get("BASE_PATH") or "").rstrip("/")
PUBLIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "public")

STARTED_AT = time.time()

app = Flask(__name__, static_folder=None)


class StripBasePath:
    """Make `/tycooncraft/foo` and `/foo` the same request.

    Defensive on purpose: in production nginx has already stripped the prefix,
    so this is a no-op there. It matters for running the container directly,
    which is how the smoke test exercises the subpath configuration.
    """

    def __init__(self, wsgi_app, prefix: str):
        self.wsgi_app = wsgi_app
        self.prefix = prefix

    def __call__(self, environ, start_response):
        if self.prefix:
            path = environ.get("PATH_INFO", "")
            if path.startswith(self.prefix):
                environ["PATH_INFO"] = path[len(self.prefix):] or "/"
                environ["SCRIPT_NAME"] = environ.get("SCRIPT_NAME", "") + self.prefix
        return self.wsgi_app(environ, start_response)


app.wsgi_app = StripBasePath(app.wsgi_app, BASE_PATH)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def current_player() -> Optional[str]:
    pid = request.headers.get("X-Player") or request.args.get("p")
    if not pid:
        return None
    return pid if store.get_player(pid) else None


def need_player() -> Tuple[Optional[str], Optional[object]]:
    pid = current_player()
    if pid is None:
        return None, (jsonify({"error": "unknown player"}), 401)
    return pid, None


def item_payload(item_key: str) -> Optional[dict]:
    row = store.get_item(item_key)
    if row is None:
        return None
    bucket = BY_ID.get(row["bucket_id"])
    if bucket is None:
        return None
    return {
        "key": item_key,
        "bucket": bucket.id,
        "name": row["name"],
        "emoji": row["emoji"],
        "flavor": row["flavor"],
        "kind": bucket.kind,
        "traits": sorted(bucket.traits),
        "tier": bucket.tier,
        "sells_for": buckets.sell_value(bucket.id),
        "first_by": row["first_by"],
        "provisional": bool(row["is_fallback"]),
        # Placeable as a producer (a Kiln, a Well) -- and what it would cost.
        "produces": PRODUCERS[bucket.id].label if bucket.id in PRODUCERS else None,
        "produce_cost": PRODUCERS[bucket.id].place_cost if bucket.id in PRODUCERS else None,
        # Automatable as a factory: true for anything that was crafted, since
        # its key records which two buckets make it. Starters have no recipe.
        "automatable": store.parse_item_key(item_key) is not None,
        "factory_cost": buckets.factory_place_cost(bucket.id),
    }


# --------------------------------------------------------------------------
# Platform contract
# --------------------------------------------------------------------------

@app.get("/health")
def health():
    """Report something real -- when the droplet misbehaves this is the first
    place anyone looks, and `{"ok": true}` alone would tell them nothing."""
    try:
        counts = store.stats()
        db_ok = True
    except Exception:
        counts = {}
        db_ok = False

    return jsonify(
        {
            "ok": db_ok,
            "app": "tycooncraft",
            "base": BASE_PATH or "/",
            "uptime_secs": round(time.time() - STARTED_AT, 1),
            # "unconfigured" is a normal state: the game plays with fallback
            # names. This is how you tell the key never made it into .env.
            "llm": "ready" if naming.configured() else "unconfigured",
            "model": naming.MODEL,
            "tiers_available": buckets.MAX_AUTHORED_TIER,
            "buckets": len(ALL),
            **counts,
        }
    ), (200 if db_ok else 503)


@app.get("/")
def index():
    return send_from_directory(PUBLIC_DIR, "index.html")


@app.get("/src/<path:filename>")
def src(filename: str):
    return send_from_directory(os.path.join(PUBLIC_DIR, "src"), filename)


@app.get("/tile.gif")
def tile():
    return send_from_directory(PUBLIC_DIR, "tile.gif")


@app.get("/favicon.ico")
def favicon():
    return ("", 204)


# --------------------------------------------------------------------------
# Game API
# --------------------------------------------------------------------------

@app.post("/api/new")
def api_new():
    name = (request.json or {}).get("name", "")
    player = store.create_player(name)
    return jsonify({"player": player["id"], "name": player["name"]}), 201


@app.get("/api/state")
def api_state():
    pid, err = need_player()
    if err:
        return err

    tick = store.tick_player(pid)
    player = store.get_player(pid)
    stock = store.get_stock(pid)
    placements = store.get_placements(pid)
    item_bucket = store.item_bucket_map()

    known = []
    for key in store.get_discoveries(pid):
        payload = item_payload(key)
        if payload:
            payload["held"] = int(stock.get(key, 0))
            known.append(payload)

    yard = []
    for p in placements:
        out_key = p.output_item if p.kind == "factory" else (p.item_key or p.bucket_id)
        out = store.get_item(out_key)
        yard.append(
            {
                "id": p.id,
                "kind": p.kind,
                "label": PRODUCERS[p.bucket_id].label if p.kind == "producer" else "Factory",
                "output": out_key,
                "output_name": out["name"] if out else out_key,
                "output_emoji": out["emoji"] if out else "",
                "inputs": list(p.inputs),
                "secs": p.secs_per_unit(),
                "progress": round(p.progress, 2),
                "autosell": p.autosell,
                "stalled": p.id in tick.stalled,
            }
        )

    ceiling = player["ceiling"]
    next_tier = ceiling + 1
    return jsonify(
        {
            "name": player["name"],
            "coins": int(player["coins"]),
            "ceiling": ceiling,
            "max_tier": buckets.MAX_AUTHORED_TIER,
            "next_tier_cost": economy.unlock_cost(next_tier),
            "yard_slots": economy.yard_slots(ceiling),
            "yard_used": len(placements),
            "income_per_hour": round(economy.income_per_hour(placements, item_bucket)),
            "items": known,
            "yard": yard,
            "offline": {
                "seconds_applied": round(tick.seconds_applied),
                "seconds_dropped": round(tick.seconds_dropped),
                "coins_earned": round(tick.coins_earned, 1),
            },
        }
    )


@app.post("/api/craft")
def api_craft():
    """The core move. Duds resolve before any spend and before any API call.

    Order matters: resolve first, and only then charge. Charging for "nothing
    happened" would punish the experimentation that is how a player learns the
    trait system in the first place.
    """
    pid, err = need_player()
    if err:
        return err
    store.tick_player(pid)

    body = request.json or {}
    a_key, b_key = body.get("a"), body.get("b")
    a_row, b_row = store.get_item(a_key or ""), store.get_item(b_key or "")
    if not a_row or not b_row:
        return jsonify({"error": "unknown item"}), 400

    a_bucket, b_bucket = BY_ID.get(a_row["bucket_id"]), BY_ID.get(b_row["bucket_id"])
    if not a_bucket or not b_bucket:
        return jsonify({"error": "unknown bucket"}), 400

    player = store.get_player(pid)
    stock = store.get_stock(pid)

    need = 2 if a_key == b_key else 1
    if stock.get(a_key, 0) < need or stock.get(b_key, 0) < 1:
        return jsonify({"error": "not enough of those in stock", "kind": "stock"}), 400

    result = combine(a_bucket, b_bucket, player["ceiling"], ALL)
    if isinstance(result, Dud):
        # Free, instant, no row, no charge. The reason is shown so the player
        # learns the system rather than just losing a click.
        return jsonify({"dud": True, "reason": result.reason})

    cost = buckets.TIER_CRAFT_COST[result.tier]
    if player["coins"] < cost:
        return jsonify({"error": "not enough coins", "kind": "coins", "cost": cost}), 400

    item_key = store.item_key_for(result.id, a_bucket.id, b_bucket.id)
    existing = store.get_item(item_key)

    if existing is None:
        # Nobody -- and no pre-generated pack -- has this combination. The only
        # case that costs an API call, and the only one that can be slow.
        name, emoji, flavor, is_fallback = naming.name_discovery(
            a_row["name"], b_row["name"], result
        )
        store.put_item(item_key, result.id, name, emoji, flavor, None, is_fallback)
    elif existing["is_fallback"] and naming.configured():
        # Named while the droplet had no key; upgrade it now that it does.
        name, emoji, flavor, is_fallback = naming.name_discovery(
            a_row["name"], b_row["name"], result
        )
        if not is_fallback:
            store.upgrade_fallback_name(item_key, name, emoji, flavor)

    stock[a_key] = stock.get(a_key, 0) - need
    if a_key != b_key:
        stock[b_key] = stock.get(b_key, 0) - 1
    stock[item_key] = stock.get(item_key, 0) + 1
    store.write_stock(pid, {k: v for k, v in stock.items() if v > 0})
    store.set_coins(pid, player["coins"] - cost)

    # Credit is claimed separately from naming, so a pre-generated name still
    # leaves the first-discovery badge for whoever actually makes it first.
    first_in_world = store.claim_first(item_key, player["name"])
    newly_known = store.record_discovery(pid, item_key)
    payload = item_payload(item_key)
    payload["held"] = int(stock.get(item_key, 0))

    return jsonify(
        {
            "dud": False,
            "item": payload,
            "cost": cost,
            "new_to_you": newly_known,
            "first_in_world": first_in_world,
        }
    ), (201 if newly_known else 200)


@app.post("/api/gather")
def api_gather():
    """Hand-gather: complete a producer's current cycle.

    Cooldown is enforced here rather than in the browser. Not because three
    friends will script it, but because a client-side cooldown is a suggestion.
    """
    pid, err = need_player()
    if err:
        return err
    store.tick_player(pid)

    placement_id = (request.json or {}).get("placement")
    player = store.get_player(pid)
    now = time.time()

    if now - player["last_gather"] < economy.HAND_GATHER_COOLDOWN_SECS:
        return jsonify({"error": "still cooling down", "kind": "cooldown"}), 429

    placements = store.get_placements(pid)
    target = next((p for p in placements if p.id == placement_id), None)
    if target is None:
        return jsonify({"error": "no such placement"}), 404
    if not economy.hand_gather(target, now, 0):
        return jsonify({"error": "that is not a producer"}), 400

    store.write_placements([target])
    store.set_last_gather(pid, now)
    # Roll the completed cycle into stock immediately so the click feels instant.
    store.tick_player(pid, now + 0.001)
    return jsonify({"ok": True})


@app.post("/api/sell")
def api_sell():
    pid, err = need_player()
    if err:
        return err
    store.tick_player(pid)

    body = request.json or {}
    item_key = body.get("item")
    row = store.get_item(item_key or "")
    if row is None:
        return jsonify({"error": "unknown item"}), 400

    stock = store.get_stock(pid)
    held = int(stock.get(item_key, 0))
    qty = held if body.get("all") else int(body.get("qty", 1))
    qty = max(0, min(qty, held))
    if qty == 0:
        return jsonify({"error": "none in stock", "kind": "stock"}), 400

    coins = economy.sale_price(row["bucket_id"], qty)
    stock[item_key] = held - qty
    store.write_stock(pid, {k: v for k, v in stock.items() if v > 0})
    player = store.get_player(pid)
    store.set_coins(pid, player["coins"] + coins)
    return jsonify({"sold": qty, "coins": coins})


@app.post("/api/place")
def api_place():
    """Put a producer or a factory in the yard.

    A factory automates a recipe already discovered, which is what turns a
    known combination into passive income -- and what makes tier-1 items
    permanent infrastructure rather than something you outgrow.
    """
    pid, err = need_player()
    if err:
        return err
    store.tick_player(pid)

    player = store.get_player(pid)
    if store.count_placements(pid) >= economy.yard_slots(player["ceiling"]):
        return jsonify({"error": "the yard is full", "kind": "slots"}), 400

    body = request.json or {}
    kind = body.get("kind")
    autosell = bool(body.get("autosell", False))
    known = set(store.get_discoveries(pid))

    if kind == "producer":
        item_key = body.get("item") or ""
        row = store.get_item(item_key)
        if row is None or item_key not in known:
            return jsonify({"error": "you have not discovered that"}), 400
        if row["bucket_id"] not in PRODUCERS:
            return jsonify({"error": "that cannot produce anything"}), 400

        producer = PRODUCERS[row["bucket_id"]]
        if player["coins"] < producer.place_cost:
            return jsonify(
                {"error": "not enough coins", "kind": "coins", "cost": producer.place_cost}
            ), 400

        # A producer yields a *bucket*, but stock is keyed by named item -- a
        # Kiln has to pick which of the charcoals it makes.
        yield_item = _ensure_producer_output(producer.yields, pid)
        store.set_coins(pid, player["coins"] - producer.place_cost)
        # A Kiln yields charcoal whether or not you ever crafted charcoal, so
        # record it — otherwise it produces into an item the shelf never shows.
        store.record_discovery(pid, yield_item)
        placed_id = store.add_producer(pid, row["bucket_id"], yield_item, autosell)
        return jsonify({"placed": placed_id, "cost": producer.place_cost}), 201

    if kind == "factory":
        out_key = body.get("output") or ""
        if out_key not in known:
            return jsonify({"error": "you have not discovered that"}), 400

        out_row = store.get_item(out_key)
        parsed = store.parse_item_key(out_key)
        if not out_row or not parsed:
            return jsonify({"error": "that cannot be automated"}), 400
        result_bucket, a_bucket, b_bucket = parsed

        # Re-resolve from the buckets rather than trusting anything the client
        # said. A hand-written POST must not be able to invent a recipe.
        check = combine(BY_ID[a_bucket], BY_ID[b_bucket], player["ceiling"], ALL)
        if not isinstance(check, Bucket) or check.id != result_bucket:
            return jsonify(
                {"error": "that recipe is above your tier", "kind": "tier"}
            ), 400

        # Pick which of the player's items feed it. They are interchangeable
        # within a bucket, so any discovered one will do.
        a_key = store.find_item_by_bucket(a_bucket, prefer_player=pid)
        b_key = store.find_item_by_bucket(b_bucket, prefer_player=pid)
        if not a_key or not b_key:
            return jsonify(
                {"error": "you have none of the ingredients yet", "kind": "stock"}
            ), 400

        cost = buckets.factory_place_cost(out_row["bucket_id"])
        if player["coins"] < cost:
            return jsonify({"error": "not enough coins", "kind": "coins", "cost": cost}), 400

        store.set_coins(pid, player["coins"] - cost)
        new_id = store.add_factory(
            pid, out_row["bucket_id"], out_key, a_key, b_key, autosell
        )
        return jsonify({"placed": new_id, "cost": cost}), 201

    return jsonify({"error": "kind must be producer or factory"}), 400


def _ensure_producer_output(bucket_id: str, pid: str) -> str:
    """Pick the named item a producer should yield.

    Prefer one the player already knows, so a Kiln stocks the same charcoal
    they discovered rather than a second, differently-named, mechanically
    identical pile. Only mint a new name when the bucket has never been seen by
    anyone -- which is possible, since a producer can yield something the
    player has not crafted yet.
    """
    if bucket_id in store.STARTER_ITEMS:
        return bucket_id

    existing = store.find_item_by_bucket(bucket_id, prefer_player=pid)
    if existing:
        return existing

    key = store.item_key_for(bucket_id, bucket_id, bucket_id)
    bucket = BY_ID[bucket_id]
    name, emoji, flavor, is_fallback = naming.name_discovery(
        bucket_id.replace("_", " ").title(), "itself", bucket
    )
    store.put_item(key, bucket_id, name, emoji, flavor, None, is_fallback)
    return key


@app.post("/api/remove")
def api_remove():
    pid, err = need_player()
    if err:
        return err
    store.tick_player(pid)

    placement_id = (request.json or {}).get("placement")
    row = store.remove_placement(pid, placement_id)
    if row is None:
        return jsonify({"error": "no such placement"}), 404

    # Half back. Enough that reorganising the yard is not punishing, little
    # enough that churning placements is not a strategy.
    if row["kind"] == "producer":
        paid = PRODUCERS[row["bucket_id"]].place_cost
    else:
        paid = buckets.factory_place_cost(row["bucket_id"])
    refund = paid // 2
    player = store.get_player(pid)
    store.set_coins(pid, player["coins"] + refund)
    return jsonify({"removed": placement_id, "refund": refund})


@app.post("/api/autosell")
def api_autosell():
    pid, err = need_player()
    if err:
        return err
    body = request.json or {}
    ok = store.set_autosell(pid, body.get("placement"), bool(body.get("on")))
    return (jsonify({"ok": True}) if ok else (jsonify({"error": "no such placement"}), 404))


@app.post("/api/unlock")
def api_unlock():
    """Raise the tier ceiling. The dominant coin sink and the main progression
    beat -- it does not unblock crafting, it raises how high a craft can reach.
    """
    pid, err = need_player()
    if err:
        return err
    store.tick_player(pid)

    player = store.get_player(pid)
    target = player["ceiling"] + 1
    cost = economy.unlock_cost(target)
    if cost is None:
        return jsonify(
            {
                "error": f"tier {target} is not built yet — you have finished "
                         f"everything in this build",
                "kind": "max",
            }
        ), 400
    if player["coins"] < cost:
        return jsonify({"error": "not enough coins", "kind": "coins", "cost": cost}), 400

    store.set_coins(pid, player["coins"] - cost)
    store.set_ceiling(pid, target)
    return jsonify({"ceiling": target, "cost": cost})


@app.get("/api/feed")
def api_feed():
    rows = store.recent_discoveries()
    return jsonify(
        {
            "feed": [
                {
                    "name": r["name"],
                    "emoji": r["emoji"],
                    "by": r["first_by"],
                    "tier": BY_ID[r["bucket_id"]].tier if r["bucket_id"] in BY_ID else 0,
                    "at": r["created_at"],
                }
                for r in rows
            ]
        }
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 8080)), debug=True)
