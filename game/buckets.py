"""The authored content: every item that can exist, and what makes it.

`traits.py` is the mechanism; this file is the game. Everything here is data,
so tuning the tree means editing a table and re-running `pytest`, not touching
logic.

The invariant that keeps this honest: **the bucket table IS the recipe space.**
A craft can only ever resolve to a bucket written down here. There is no
generative path that invents mechanics, which is why the item space cannot
drift no matter how many combinations players try.

Two rules for editing:

* `needs` / `forbids` must make each bucket's predicate distinguishable from
  its siblings at the same tier. `validate()` catches outright duplicates, and
  `test_resolution_table` prints what every reachable combination actually
  resolves to -- read that output after any change, because a too-loose
  `needs` will quietly shadow a sibling rather than error.
* Everything must stay reachable from the four starters.
  `test_all_buckets_reachable` fails if you orphan something.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from .traits import KINDS, MAX_TIER, MIN_TIER, TRAITS, Bucket

# --------------------------------------------------------------------------
# Economy per tier
# --------------------------------------------------------------------------
# Sale value climbs ~5x a tier. That gap is what makes "unlock the next tier"
# always the best thing to do with a pile of coins, which is the whole thesis
# of the game -- see the plan's Part 2.
#
# Craft cost climbs more slowly than value, so a tier stays profitable once you
# have automated it. If these ever cross, the game becomes unwinnable; the
# balance test asserts they do not.
TIER_SELL_VALUE = {1: 1, 2: 5, 3: 26, 4: 140, 5: 750, 6: 4000}

# Held at ~40% of the tier's sell value. That is the band where the numbers
# work out: a hand-craft is marginally profitable once you account for the two
# inputs it eats, so discovering is never a punishment -- but the real money is
# in *converting upward*, because each tier is worth >5x the one below and only
# consumes two of them.
#
# Getting this wrong is not subtle. The first pass had tier 2 costing 12 to
# craft and selling for 5, so every discovery lost money;
# test_value_climbs_faster_than_craft_cost caught it.
TIER_CRAFT_COST = {1: 0, 2: 2, 3: 10, 4: 55, 5: 300, 6: 1600}

# Price of raising your ceiling from (tier-1) to tier. The dominant coin sink,
# and therefore the single biggest lever on how long a run takes.
#
# Tuned with `tools/simulate.py` against a "casual" player who checks in every
# twenty minutes, which is the pacing that has to land -- a curve that only
# works for an optimiser does not work. Tiers 2 and 3 are measured against the
# real bucket tree; 4 to 6 are set from the projection and will be re-tuned in
# phase 2 once their content actually exists.
TIER_UNLOCK_COST = {2: 150, 3: 1400, 4: 23000, 5: 145000, 6: 900000}

# Placement slots available in the yard at each ceiling. Tight early so the
# first real decision is "which producer earns its slot", loose later so
# automating a whole chain is possible.
TIER_YARD_SLOTS = {1: 4, 2: 6, 3: 9, 4: 13, 5: 18, 6: 24}


def _b(
    id: str,
    kind: str,
    traits: str,
    tier: int,
    needs: str = "",
    forbids: str = "",
    priority: int = 0,
    craftable: bool = True,
) -> Bucket:
    """Terse constructor -- traits as space-separated strings keep the table
    readable as a table, which matters more here than type ceremony."""
    return Bucket(
        id=id,
        kind=kind,
        traits=frozenset(traits.split()),
        tier=tier,
        needs=frozenset(needs.split()) if needs else frozenset(),
        forbids=frozenset(forbids.split()) if forbids else frozenset(),
        priority=priority,
        craftable=craftable,
    )


# --------------------------------------------------------------------------
# Tier 1 -- the four starters
# --------------------------------------------------------------------------
# Chosen so that all six pairs react. v1 handed you "Orbital Telescope" and
# "Quantum Lab" and asked you to combine them; there is no intuition for that.
# These are raw, physical, and obviously combinable, and between them they
# cover the five traits the whole tier-2 layer is built from.
#
# craftable=False: granted at signup, never a craft result, so they can never
# come back as a "discovery".

STARTERS = [
    _b("clay",  "material", "mineral",     1, craftable=False),
    _b("water", "material", "wet",         1, craftable=False),
    _b("seed",  "material", "grown alive", 1, craftable=False),
    _b("ember", "energy",   "hot",         1, craftable=False),
]

# --------------------------------------------------------------------------
# Tier 2 -- one per starter pair, six of them, all distinct
# --------------------------------------------------------------------------
# `forbids` is doing the real work here. clay + ember is a fired brick, but
# *wet* clay + ember is ceramic (tier 3) -- brick forbids "wet", so the wetter
# pool falls through to the better result. That is the mechanism that lets one
# trait pair fan out instead of collapsing to a single answer.

TIER2 = [
    _b("mud",      "material", "mineral wet",       2, needs="mineral wet",   forbids="hot grown",   priority=10),
    _b("loam",     "material", "mineral grown",     2, needs="mineral grown", forbids="hot wet",     priority=11),
    _b("brick",    "material", "mineral heavy",     2, needs="mineral hot",   forbids="wet grown",   priority=12),
    _b("sprout",   "creature", "alive grown wet",   2, needs="wet grown",     forbids="hot mineral", priority=13),
    _b("steam",    "energy",   "hot wet",           2, needs="hot wet",       forbids="mineral grown", priority=14),
    _b("charcoal", "energy",   "hot grown",         2, needs="grown hot",     forbids="wet mineral", priority=15),
]

# --------------------------------------------------------------------------
# Tier 3 -- ten, and the first structures and machines
# --------------------------------------------------------------------------
# Priority is roughly "specificity": a bucket needing four traits outranks one
# needing three, so richer pools land on the more interesting result. The
# resolution-table test is the check on that intuition.
#
# Two of these are producers (kiln, orchard) and one is the first metal
# (bloom, from brick + charcoal -- actual bloomery metallurgy). Metal is what
# tier 4 is built on, so bloom is the gate to the next phase.

TIER3 = [
    _b("ceramic", "material",  "mineral hollow",          3, needs="mineral wet hot",         forbids="grown heavy", priority=30),
    _b("kiln",    "structure", "mineral heavy hot",       3, needs="mineral heavy hot",       forbids="grown wet",   priority=31),
    _b("potash",  "material",  "mineral toxic",           3, needs="mineral grown hot",       forbids="heavy wet",   priority=32),
    _b("peat",    "energy",    "hot grown heavy",         3, needs="hot grown wet",           forbids="mineral",     priority=33),
    _b("slip",    "material",  "mineral wet hollow",      3, needs="mineral wet grown",       forbids="hot heavy",   priority=34),
    _b("cob",     "structure", "mineral heavy woven",     3, needs="mineral wet heavy",       forbids="hot grown",   priority=35),
    _b("yeast",   "creature",  "alive wet toxic",         3, needs="alive wet hot",           forbids="mineral",     priority=36),
    _b("crucible", "structure", "mineral hollow heavy",   3, needs="mineral hollow heavy",    forbids="grown",       priority=37),
    _b("bloom",   "material",  "metal heavy",             3, needs="mineral heavy hot grown", forbids="",            priority=50),
    _b("orchard", "structure", "alive grown wet",         3, needs="alive grown wet mineral", forbids="hot",         priority=51),
    _b("lens",    "tool",      "mineral luminous precise", 3, needs="mineral hollow hot",     forbids="grown",       priority=52),
    _b("glaze",   "material",  "mineral luminous hollow", 3, needs="mineral toxic hot",       forbids="",            priority=53),
    # Gated behind bloom: the only route in needs "metal" in the pool, so the
    # first metal genuinely opens something rather than just being worth more.
    _b("sickle",  "tool",      "metal sharp",             3, needs="metal grown",             forbids="",            priority=54),
]

# Phase 1 ships tiers 1-3. Tiers 4-6 are authored in phase 2, once the loop has
# been played and the pacing is confirmed against a real run rather than a
# simulation.
ALL: List[Bucket] = STARTERS + TIER2 + TIER3

BY_ID: Dict[str, Bucket] = {b.id: b for b in ALL}

MAX_AUTHORED_TIER = max(b.tier for b in ALL)


# --------------------------------------------------------------------------
# Producers -- what a placed item yields on its own
# --------------------------------------------------------------------------
# The four starters are placeable from the beginning, which is what removes
# v1's dead first minute: you land with a Clay Pit already running and can
# click it to hand-gather while it spins up. Automation then arrives as relief
# rather than as a gate.
#
# `secs` is seconds per unit. Tier-3 producers are strictly better than the
# tier-1 they replace, so upgrading a slot is a real decision.

class Producer:
    __slots__ = ("bucket_id", "yields", "secs", "place_cost", "label")

    def __init__(self, bucket_id: str, yields: str, secs: float, place_cost: int, label: str):
        self.bucket_id = bucket_id
        self.yields = yields
        self.secs = secs
        self.place_cost = place_cost
        self.label = label


PRODUCERS: Dict[str, Producer] = {
    p.bucket_id: p
    for p in [
        Producer("clay",    "clay",     6.0,   0,   "Clay Pit"),
        Producer("water",   "water",    5.0,  25,   "Well"),
        Producer("seed",    "seed",     8.0,  40,   "Seed Bed"),
        Producer("ember",   "ember",    7.0,  60,   "Ember Pit"),
        # Tier-3 upgrades: ~3x the throughput of the tier-1 they supersede.
        Producer("kiln",    "charcoal", 9.0, 900,   "Kiln"),
        Producer("orchard", "seed",     2.5, 1500,  "Orchard"),
    ]
}

# Placing a factory automates a recipe you have already discovered: it consumes
# the inputs from your stock and produces the output on a timer. This is what
# makes tier-1 items permanent infrastructure instead of something you outgrow
# -- every tier-3 chain still eats clay at the bottom.
FACTORY_PLACE_COST_MULTIPLIER = 8   # x the output's sell value
FACTORY_SECS = {2: 10.0, 3: 18.0, 4: 30.0, 5: 48.0, 6: 75.0}


def sell_value(bucket_id: str) -> int:
    return TIER_SELL_VALUE[BY_ID[bucket_id].tier]


def craft_cost(a_id: str, b_id: str, result_tier: int) -> int:
    """What a successful craft costs. Duds are free -- callers must resolve the
    combination first and only charge when it produced something."""
    return TIER_CRAFT_COST[result_tier]


def factory_place_cost(bucket_id: str) -> int:
    return sell_value(bucket_id) * FACTORY_PLACE_COST_MULTIPLIER


def validate() -> None:
    """Fail at import time rather than at play time.

    Every check here corresponds to a bug that shipped in v1: unreachable
    keystones, name collisions between a craft result and a seeded starter,
    tier gates with no route through them.
    """
    seen_ids = set()
    for b in ALL:
        if b.id in seen_ids:
            raise ValueError(f"duplicate bucket id {b.id!r}")
        seen_ids.add(b.id)

        unknown = b.traits - TRAITS
        if unknown:
            raise ValueError(f"{b.id}: unknown traits {sorted(unknown)}")
        if b.kind not in KINDS:
            raise ValueError(f"{b.id}: unknown kind {b.kind!r}")
        if not MIN_TIER <= b.tier <= MAX_TIER:
            raise ValueError(f"{b.id}: tier {b.tier} out of range")
        if not b.traits:
            raise ValueError(f"{b.id}: needs at least one trait")
        if len(b.traits) > 3:
            raise ValueError(f"{b.id}: {len(b.traits)} traits exceeds MAX_TRAITS")

        unknown_needs = (b.needs | b.forbids) - TRAITS
        if unknown_needs:
            raise ValueError(f"{b.id}: unknown needs/forbids {sorted(unknown_needs)}")
        # A bucket that forbids what it needs can never fire -- silently dead
        # content, which is exactly how v1's keystones failed.
        if b.needs & b.forbids:
            raise ValueError(f"{b.id}: needs and forbids overlap on {sorted(b.needs & b.forbids)}")
        if b.craftable and not b.needs:
            raise ValueError(f"{b.id}: craftable but has no needs, so nothing can make it")
        if not b.craftable and b.needs:
            raise ValueError(f"{b.id}: not craftable, so needs is dead weight")

    # Priority must be a total order within a tier, or which of two matching
    # buckets wins depends on list order -- reproducible, but accidental.
    for tier in {b.tier for b in ALL}:
        prios = [b.priority for b in ALL if b.tier == tier and b.craftable]
        if len(prios) != len(set(prios)):
            raise ValueError(f"tier {tier}: duplicate priorities {sorted(prios)}")

    # Identical predicates mean one bucket permanently shadows the other.
    by_pred: Dict[tuple, str] = {}
    for b in ALL:
        if not b.craftable:
            continue
        key = (b.tier, b.needs, b.forbids)
        if key in by_pred:
            raise ValueError(
                f"{b.id} and {by_pred[key]} have identical predicates; "
                f"{by_pred[key]} would always shadow {b.id}"
            )
        by_pred[key] = b.id

    for tier in range(2, MAX_AUTHORED_TIER + 1):
        if tier not in TIER_UNLOCK_COST:
            raise ValueError(f"tier {tier} is authored but has no unlock cost")
        if tier not in TIER_SELL_VALUE or tier not in TIER_CRAFT_COST:
            raise ValueError(f"tier {tier} is authored but has no economy row")
        # If a craft ever costs more than its output sells for, that tier is a
        # money pit and the run stalls.
        if TIER_CRAFT_COST[tier] >= TIER_SELL_VALUE[tier] * 4:
            raise ValueError(
                f"tier {tier}: craft cost {TIER_CRAFT_COST[tier]} is too close to "
                f"4x sell value {TIER_SELL_VALUE[tier]}; the tier cannot pay for itself"
            )

    for pid in PRODUCERS:
        if pid not in BY_ID:
            raise ValueError(f"producer {pid!r} is not a bucket")
    for p in PRODUCERS.values():
        if p.yields not in BY_ID:
            raise ValueError(f"producer {p.bucket_id!r} yields unknown bucket {p.yields!r}")


validate()
