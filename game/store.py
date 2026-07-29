"""SQLite persistence.

One connection guarded by one lock. That is deliberate and it is why
`gunicorn_config.py` runs a single process: SQLite permits one writer, so
keeping every write behind one in-process lock means there is no cross-process
contention that could lose a save. For three friends this is not a compromise,
it is simply correct, and it removes a whole category of bug that is miserable
to reproduce.

The item registry is **global and append-only**. Two players who make the same
combination get the same name, so the first to find it is credited and everyone
after gets an instant, free lookup instead of an API call. Nothing is ever
deleted -- v1 could wipe every player's discoveries and buildings when one
player's craft tripped a validation mismatch, because the shared row cascaded.
"""

from __future__ import annotations

import json
import os
import secrets
import sqlite3
import threading
import time
from typing import Dict, List, Optional, Tuple

from . import buckets, economy
from .buckets import BY_ID
from .economy import Placement

_lock = threading.RLock()
_conn: Optional[sqlite3.Connection] = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    item_key    TEXT PRIMARY KEY,
    bucket_id   TEXT NOT NULL,
    name        TEXT NOT NULL,
    emoji       TEXT NOT NULL,
    flavor      TEXT NOT NULL DEFAULT '',
    first_by    TEXT,
    created_at  REAL NOT NULL,
    is_fallback INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS players (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    coins       REAL NOT NULL,
    ceiling     INTEGER NOT NULL,
    created_at  REAL NOT NULL,
    last_tick   REAL NOT NULL,
    last_gather REAL NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS stock (
    player_id TEXT NOT NULL,
    item_key  TEXT NOT NULL,
    qty       REAL NOT NULL,
    PRIMARY KEY (player_id, item_key)
);

CREATE TABLE IF NOT EXISTS discoveries (
    player_id     TEXT NOT NULL,
    item_key      TEXT NOT NULL,
    discovered_at REAL NOT NULL,
    PRIMARY KEY (player_id, item_key)
);

CREATE TABLE IF NOT EXISTS placements (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id   TEXT NOT NULL,
    kind        TEXT NOT NULL,
    bucket_id   TEXT NOT NULL,
    progress    REAL NOT NULL DEFAULT 0,
    input_a     TEXT,
    input_b     TEXT,
    output_item TEXT,
    item_key    TEXT,
    autosell    INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_stock_player ON stock(player_id);
CREATE INDEX IF NOT EXISTS idx_disc_player ON discoveries(player_id);
CREATE INDEX IF NOT EXISTS idx_place_player ON placements(player_id);
"""

# Hand-authored so the opening reads well. Everything else in the game is named
# by the model, but the first four items are the player's introduction to the
# tone, so they are not left to chance.
STARTER_ITEMS = {
    "clay":  ("Clay",  "\U0001f7e4", "Wet earth that remembers what you do to it"),
    "water": ("Water", "\U0001f4a7", "Runs downhill, dissolves nearly anything"),
    "seed":  ("Seed",  "\U0001f331", "Small, patient, and full of intent"),
    "ember": ("Ember", "\U0001f525", "Still hot — keep it fed"),
}


def data_dir() -> str:
    return os.environ.get("DATA_DIR", "data")


def connect() -> sqlite3.Connection:
    global _conn
    with _lock:
        if _conn is not None:
            return _conn
        os.makedirs(data_dir(), exist_ok=True)
        path = os.path.join(data_dir(), "tycooncraft.sqlite3")
        _conn = sqlite3.connect(path, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        # WAL so a reader is never blocked by the writer; NORMAL because losing
        # the last few seconds of an idle game to a hard power cut is an
        # acceptable trade for not fsyncing on every production tick.
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.execute("PRAGMA synchronous=NORMAL")
        _conn.execute("PRAGMA foreign_keys=ON")
        _conn.executescript(SCHEMA)
        _conn.commit()
        _seed_starter_items(_conn)
        _seed_recipe_pack(_conn)
        return _conn


def _seed_starter_items(conn: sqlite3.Connection) -> None:
    now = time.time()
    for bucket_id, (name, emoji, flavor) in STARTER_ITEMS.items():
        conn.execute(
            "INSERT OR IGNORE INTO items"
            " (item_key, bucket_id, name, emoji, flavor, first_by, created_at, is_fallback)"
            " VALUES (?,?,?,?,?,NULL,?,0)",
            (bucket_id, bucket_id, name, emoji, flavor, now),
        )
    conn.commit()


def _seed_recipe_pack(conn: sqlite3.Connection) -> None:
    """Load the pre-generated names into the registry.

    Seeding rather than special-casing the craft path means there is exactly one
    way a name is looked up, and the API is only ever called for a combination
    nobody anticipated. After a full pack, tiers 1-3 need no runtime API calls
    at all -- which is the real answer to "the first players just wait".

    `first_by` stays NULL, so being the first player to actually *make* one is
    still a claimable first discovery. The pack supplies names, not credit.
    """
    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "content", "recipes.json"
    )
    try:
        with open(path, "r", encoding="utf-8") as handle:
            pack = json.load(handle)
    except (OSError, ValueError):
        return                                  # no pack is a supported state

    rows = []
    now = time.time()
    for item_key, entry in (pack.get("names") or {}).items():
        parsed = parse_item_key(item_key)
        bucket_id = parsed[0] if parsed else item_key
        if bucket_id not in BY_ID:
            continue                            # content drifted; skip, don't crash
        rows.append(
            (
                item_key, bucket_id, entry.get("name", ""), entry.get("emoji", ""),
                entry.get("flavor", ""), None, now, 0,
            )
        )
    if not rows:
        return
    conn.executemany(
        "INSERT OR IGNORE INTO items"
        " (item_key, bucket_id, name, emoji, flavor, first_by, created_at, is_fallback)"
        " VALUES (?,?,?,?,?,?,?,?)",
        rows,
    )
    conn.commit()


def claim_first(item_key: str, player_name: str) -> bool:
    """Claim the first-discovery credit. True if this player got it.

    Separate from item creation so a pre-generated name still leaves the credit
    unclaimed for whoever actually makes the thing first. Atomic via the
    `first_by IS NULL` predicate, so two simultaneous crafts cannot both win.
    """
    conn = connect()
    with _lock:
        cur = conn.execute(
            "UPDATE items SET first_by=? WHERE item_key=? AND first_by IS NULL",
            (player_name, item_key),
        )
        conn.commit()
        return cur.rowcount > 0


def reset_for_tests() -> None:
    """Drop the cached connection so a test can point DATA_DIR somewhere else."""
    global _conn
    with _lock:
        if _conn is not None:
            _conn.close()
        _conn = None


# --------------------------------------------------------------------------
# Item registry
# --------------------------------------------------------------------------

def item_key_for(bucket_id: str, a_bucket: str, b_bucket: str) -> str:
    """Identity of a named item.

    Keyed by the result bucket plus the *sorted input buckets* -- not the input
    items. That is what keeps the name space bounded: at most one name per
    (result, input-pair-of-buckets), so a few hundred names covers the whole
    game and the pre-generated pack can hold all of them.

    Keying on input *items* instead would let keys nest recursively and grow
    without limit, which is v1's unbounded-noun problem wearing a different hat.
    Sorted so A+B and B+A are one entry.
    """
    lo, hi = sorted((a_bucket, b_bucket))
    return f"{bucket_id}<{lo}+{hi}"


def parse_item_key(item_key: str) -> Optional[Tuple[str, str, str]]:
    """Pull `(result_bucket, input_bucket_a, input_bucket_b)` back out of a key.

    The key already records which buckets made the thing, so a factory does not
    need the client to tell it -- it can find the player's own items in those
    buckets. That is one fewer thing a hand-written POST can lie about, and one
    fewer decision to put in front of the player.

    Returns None for starter keys, which have no inputs.
    """
    if "<" not in item_key:
        return None
    result, _, rest = item_key.partition("<")
    a, _, b = rest.partition("+")
    if not (result and a and b):
        return None
    return result, a, b


def get_item(item_key: str) -> Optional[sqlite3.Row]:
    conn = connect()
    with _lock:
        return conn.execute(
            "SELECT * FROM items WHERE item_key=?", (item_key,)
        ).fetchone()


def put_item(
    item_key: str,
    bucket_id: str,
    name: str,
    emoji: str,
    flavor: str,
    first_by: Optional[str],
    is_fallback: bool,
) -> sqlite3.Row:
    """Register a name, or return the one already there.

    INSERT OR IGNORE, then read back: two players crafting the same new
    combination in the same second both get a valid item and only one of them
    is credited, rather than one of them getting an IntegrityError.
    """
    conn = connect()
    with _lock:
        conn.execute(
            "INSERT OR IGNORE INTO items"
            " (item_key, bucket_id, name, emoji, flavor, first_by, created_at, is_fallback)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (item_key, bucket_id, name, emoji, flavor, first_by, time.time(), int(is_fallback)),
        )
        conn.commit()
        return conn.execute("SELECT * FROM items WHERE item_key=?", (item_key,)).fetchone()


def upgrade_fallback_name(item_key: str, name: str, emoji: str, flavor: str) -> None:
    """Replace a deterministic fallback with a real name, once only.

    This is what makes it safe to deploy before the API key is in place: items
    named while keyless get upgraded the next time somebody makes them.
    """
    conn = connect()
    with _lock:
        conn.execute(
            "UPDATE items SET name=?, emoji=?, flavor=?, is_fallback=0"
            " WHERE item_key=? AND is_fallback=1",
            (name, emoji, flavor, item_key),
        )
        conn.commit()


def find_item_by_bucket(bucket_id: str, prefer_player: Optional[str] = None) -> Optional[str]:
    """An existing named item in this bucket, preferring one the player knows.

    Producers yield a *bucket*, but stock is keyed by named item -- so a Kiln
    has to pick which of the charcoals it makes. Reusing an item the player has
    already discovered keeps their shelf from filling with several differently
    named but mechanically identical piles.
    """
    conn = connect()
    with _lock:
        if prefer_player:
            row = conn.execute(
                "SELECT i.item_key FROM items i"
                " JOIN discoveries d ON d.item_key = i.item_key"
                " WHERE i.bucket_id=? AND d.player_id=?"
                " ORDER BY d.discovered_at LIMIT 1",
                (bucket_id, prefer_player),
            ).fetchone()
            if row:
                return row["item_key"]
        row = conn.execute(
            "SELECT item_key FROM items WHERE bucket_id=? ORDER BY created_at LIMIT 1",
            (bucket_id,),
        ).fetchone()
        return row["item_key"] if row else None


def item_bucket_map() -> Dict[str, str]:
    conn = connect()
    with _lock:
        rows = conn.execute("SELECT item_key, bucket_id FROM items").fetchall()
    return {r["item_key"]: r["bucket_id"] for r in rows}


def recent_discoveries(limit: int = 12) -> List[sqlite3.Row]:
    """The live feed: what anyone found lately. Cheap social pressure, and it is
    the thing that makes being first worth something."""
    conn = connect()
    with _lock:
        return conn.execute(
            "SELECT item_key, name, emoji, bucket_id, first_by, created_at FROM items"
            " WHERE first_by IS NOT NULL ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()


# --------------------------------------------------------------------------
# Players
# --------------------------------------------------------------------------

def create_player(name: str) -> sqlite3.Row:
    """A new player. No password -- the id *is* the credential, handed back as a
    resume link, matching how whiteboard and poggle work. A login wall is heavy
    friction for three friends.
    """
    conn = connect()
    pid = secrets.token_urlsafe(16)
    now = time.time()
    with _lock:
        conn.execute(
            "INSERT INTO players (id, name, coins, ceiling, created_at, last_tick, last_gather)"
            " VALUES (?,?,?,?,?,?,0)",
            (pid, name.strip()[:24] or "Anon", economy.STARTING_COINS, 1, now, now),
        )
        for bucket_id in STARTER_ITEMS:
            conn.execute(
                "INSERT INTO discoveries (player_id, item_key, discovered_at) VALUES (?,?,?)",
                (pid, bucket_id, now),
            )
        # Two producers already running and one of each in stock, so the very
        # first action available is a *craft*, not a wait. Drag clay onto water
        # and something new appears within seconds of arriving.
        #
        # This is the direct fix for "if you are one of the first players you
        # just wait a while for stuff to generate". The Seed Bed and Ember Pit
        # are the first things money is actually for.
        for bucket_id in ("clay", "water"):
            conn.execute(
                "INSERT INTO placements (player_id, kind, bucket_id, item_key, progress)"
                " VALUES (?,'producer',?,?,0)",
                (pid, bucket_id, bucket_id),
            )
            conn.execute(
                "INSERT INTO stock (player_id, item_key, qty) VALUES (?,?,1)",
                (pid, bucket_id),
            )
        conn.commit()
        return conn.execute("SELECT * FROM players WHERE id=?", (pid,)).fetchone()


def get_player(pid: str) -> Optional[sqlite3.Row]:
    conn = connect()
    with _lock:
        return conn.execute("SELECT * FROM players WHERE id=?", (pid,)).fetchone()


def set_coins(pid: str, coins: float) -> None:
    conn = connect()
    with _lock:
        conn.execute("UPDATE players SET coins=? WHERE id=?", (max(0.0, coins), pid))
        conn.commit()


def set_ceiling(pid: str, ceiling: int) -> None:
    conn = connect()
    with _lock:
        conn.execute("UPDATE players SET ceiling=? WHERE id=?", (ceiling, pid))
        conn.commit()


def set_last_gather(pid: str, when: float) -> None:
    conn = connect()
    with _lock:
        conn.execute("UPDATE players SET last_gather=? WHERE id=?", (when, pid))
        conn.commit()


# --------------------------------------------------------------------------
# Stock, discoveries, placements
# --------------------------------------------------------------------------

def get_stock(pid: str) -> Dict[str, float]:
    conn = connect()
    with _lock:
        rows = conn.execute(
            "SELECT item_key, qty FROM stock WHERE player_id=?", (pid,)
        ).fetchall()
    return {r["item_key"]: r["qty"] for r in rows}


def write_stock(pid: str, stock: Dict[str, float]) -> None:
    """Replace the player's stock wholesale.

    `tick()` mutates a dict in memory and this writes the result, so partial
    production survives a restart. Deleting emptied rows keeps the table from
    filling with zeroes over a long run.
    """
    conn = connect()
    with _lock:
        conn.execute("DELETE FROM stock WHERE player_id=?", (pid,))
        conn.executemany(
            "INSERT INTO stock (player_id, item_key, qty) VALUES (?,?,?)",
            [(pid, k, v) for k, v in stock.items() if v > 0],
        )
        conn.commit()


def get_discoveries(pid: str) -> List[str]:
    conn = connect()
    with _lock:
        rows = conn.execute(
            "SELECT item_key FROM discoveries WHERE player_id=? ORDER BY discovered_at",
            (pid,),
        ).fetchall()
    return [r["item_key"] for r in rows]


def record_discovery(pid: str, item_key: str) -> bool:
    """Returns True if this is new *for this player*."""
    conn = connect()
    with _lock:
        cur = conn.execute(
            "INSERT OR IGNORE INTO discoveries (player_id, item_key, discovered_at)"
            " VALUES (?,?,?)",
            (pid, item_key, time.time()),
        )
        conn.commit()
        return cur.rowcount > 0


def get_placements(pid: str) -> List[Placement]:
    conn = connect()
    with _lock:
        rows = conn.execute(
            "SELECT * FROM placements WHERE player_id=? ORDER BY id", (pid,)
        ).fetchall()
    out = []
    for r in rows:
        out.append(
            Placement(
                id=r["id"],
                kind=r["kind"],
                bucket_id=r["bucket_id"],
                progress=r["progress"],
                inputs=(r["input_a"], r["input_b"]) if r["input_a"] else (),
                output_item=r["output_item"] or "",
                item_key=r["item_key"] or "",
                autosell=bool(r["autosell"]),
            )
        )
    return out


def write_placements(placements: List[Placement]) -> None:
    """Persist progress after a tick. Only the mutable columns."""
    conn = connect()
    with _lock:
        conn.executemany(
            "UPDATE placements SET progress=? WHERE id=?",
            [(p.progress, p.id) for p in placements],
        )
        conn.commit()


def add_producer(pid: str, bucket_id: str, item_key: str, autosell: bool) -> int:
    conn = connect()
    with _lock:
        cur = conn.execute(
            "INSERT INTO placements (player_id, kind, bucket_id, item_key, autosell)"
            " VALUES (?,'producer',?,?,?)",
            (pid, bucket_id, item_key, int(autosell)),
        )
        conn.commit()
        return cur.lastrowid


def add_factory(
    pid: str, output_bucket: str, output_item: str, a: str, b: str, autosell: bool
) -> int:
    conn = connect()
    with _lock:
        cur = conn.execute(
            "INSERT INTO placements"
            " (player_id, kind, bucket_id, input_a, input_b, output_item, autosell)"
            " VALUES (?,'factory',?,?,?,?,?)",
            (pid, output_bucket, a, b, output_item, int(autosell)),
        )
        conn.commit()
        return cur.lastrowid


def remove_placement(pid: str, placement_id: int) -> Optional[sqlite3.Row]:
    conn = connect()
    with _lock:
        row = conn.execute(
            "SELECT * FROM placements WHERE id=? AND player_id=?", (placement_id, pid)
        ).fetchone()
        if row is None:
            return None
        conn.execute("DELETE FROM placements WHERE id=?", (placement_id,))
        conn.commit()
        return row


def set_autosell(pid: str, placement_id: int, on: bool) -> bool:
    conn = connect()
    with _lock:
        cur = conn.execute(
            "UPDATE placements SET autosell=? WHERE id=? AND player_id=?",
            (int(on), placement_id, pid),
        )
        conn.commit()
        return cur.rowcount > 0


def count_placements(pid: str) -> int:
    conn = connect()
    with _lock:
        return conn.execute(
            "SELECT COUNT(*) AS n FROM placements WHERE player_id=?", (pid,)
        ).fetchone()["n"]


# --------------------------------------------------------------------------
# The one place time passes
# --------------------------------------------------------------------------

def tick_player(pid: str, now: Optional[float] = None) -> economy.TickResult:
    """Run production forward and persist. Called on every request that reads or
    changes state, so `last_tick` is never stale and offline time is never lost.
    """
    now = time.time() if now is None else now
    player = get_player(pid)
    if player is None:
        return economy.TickResult()

    placements = get_placements(pid)
    stock = get_stock(pid)

    result = economy.tick(
        placements, stock, player["last_tick"], now, item_bucket_map()
    )

    conn = connect()
    with _lock:
        write_stock(pid, stock)
        write_placements(placements)
        conn.execute(
            "UPDATE players SET coins=coins+?, last_tick=? WHERE id=?",
            (result.coins_earned, now, pid),
        )
        conn.commit()
    return result


def stats() -> Dict[str, int]:
    """For /health. Reporting something real makes this the first useful place
    to look when the droplet is misbehaving."""
    conn = connect()
    with _lock:
        return {
            "players": conn.execute("SELECT COUNT(*) n FROM players").fetchone()["n"],
            "items_named": conn.execute("SELECT COUNT(*) n FROM items").fetchone()["n"],
            "fallback_names": conn.execute(
                "SELECT COUNT(*) n FROM items WHERE is_fallback=1"
            ).fetchone()["n"],
            "placements": conn.execute("SELECT COUNT(*) n FROM placements").fetchone()["n"],
        }
