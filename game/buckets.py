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
TIER_SELL_VALUE = {
    1: 1, 2: 5, 3: 26, 4: 140, 5: 750, 6: 4000,
    7: 21_000, 8: 110_000, 9: 580_000,
}

# Held at ~40% of the tier's sell value. That is the band where the numbers
# work out: a hand-craft is marginally profitable once you account for the two
# inputs it eats, so discovering is never a punishment -- but the real money is
# in *converting upward*, because each tier is worth >5x the one below and only
# consumes two of them.
#
# Getting this wrong is not subtle. The first pass had tier 2 costing 12 to
# craft and selling for 5, so every discovery lost money;
# test_value_climbs_faster_than_craft_cost caught it.
TIER_CRAFT_COST = {
    1: 0, 2: 2, 3: 10, 4: 55, 5: 300, 6: 1600,
    7: 8_400, 8: 44_000, 9: 230_000,
}

# Price of raising your ceiling from (tier-1) to tier. The dominant coin sink,
# and therefore the single biggest lever on how long a run takes.
#
# Tuned with `tools/simulate.py` against a "casual" player who checks in every
# twenty minutes, which is the pacing that has to land -- a curve that only
# works for an optimiser does not work. Every tier is now measured against the
# real bucket tree; phase 2 (tiers 4-9) replaced the projections these were
# first set from.
TIER_UNLOCK_COST = {
    2: 150, 3: 1400, 4: 23000, 5: 145000, 6: 900000,
    # 7-9 follow the same ~6x ratio the 4-6 stretch settled on; tuned against
    # tools/simulate.py the same way, now against the real tree rather than a
    # projection.
    7: 5_500_000, 8: 33_000_000, 9: 200_000_000,
}

# Placement slots available in the yard at each ceiling. Tight early so the
# first real decision is "which producer earns its slot", loose later so
# automating a whole chain is possible.
TIER_YARD_SLOTS = {1: 4, 2: 6, 3: 9, 4: 13, 5: 18, 6: 24, 7: 30, 8: 37, 9: 45}


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

# --------------------------------------------------------------------------
# Tier 4 -- ironworking. Metal stops being a curiosity and becomes the base
# of everything above it.
# --------------------------------------------------------------------------
# bloom (the tier-3 keystone) fans out three ways depending on what it is
# worked with: alone in heat it refines to iron, over a mineral hearth it
# builds the forge, against grown things it turns farm tool. `frost` is the
# quiet keystone here -- it introduces "cold" (evaporative cooling in porous
# ceramic, which is real), and the whole cold line above tier 4 hangs off it.

TIER4 = [
    _b("iron",    "material",  "metal heavy",            4, needs="metal hot",             forbids="mineral grown wet", priority=70),
    _b("forge",   "structure", "mineral heavy hot",      4, needs="metal mineral hot",     forbids="grown wet",         priority=71),
    _b("coke",    "energy",    "hot heavy toxic",        4, needs="toxic hot",             forbids="wet metal alive",   priority=72),
    _b("plough",  "tool",      "metal sharp heavy",      4, needs="metal sharp grown",     forbids="wet hot",           priority=73),
    _b("alembic", "structure", "mineral hollow precise", 4, needs="mineral hollow hot wet", forbids="heavy grown",      priority=74),
    # Needs four traits on purpose: three would be a subset of slip's own
    # traits, and slip + slip must stay a dud (test_self_combination).
    _b("frost",   "material",  "cold wet",               4, needs="mineral hollow heavy wet", forbids="hot grown",      priority=75),
    _b("ox",      "creature",  "alive heavy grown",      4, needs="alive grown heavy",     forbids="mineral metal toxic", priority=76),
    _b("mirror",  "tool",      "mineral luminous precise", 4, needs="luminous precise hollow", forbids="grown wet",     priority=77),
]

# --------------------------------------------------------------------------
# Tier 5 -- power. The waterwheel is the keystone: it introduces "powered",
# and every machine above tier 5 needs it somewhere in its ancestry.
# --------------------------------------------------------------------------
# The other quiet debut is the cold chain (frost -> icehouse) and the grown
# chain getting a second wind (greenhouse), so a tier-5 yard is not just
# metal on metal.

TIER5 = [
    _b("steel",      "material",  "metal precise heavy",  5, needs="metal hot toxic",        forbids="wet grown alive", priority=90),
    _b("waterwheel", "machine",   "powered wet heavy",    5, needs="metal heavy wet",        forbids="hot grown toxic", priority=91),
    _b("lathe",      "machine",   "metal precise powered", 5, needs="powered metal sharp",   forbids="grown",           priority=92),
    _b("icehouse",   "structure", "cold hollow heavy",    5, needs="cold mineral heavy",     forbids="hot",             priority=93),
    _b("acid",       "material",  "wet toxic",            5, needs="precise toxic",          forbids="grown metal cold", priority=94),
    _b("greenhouse", "structure", "alive grown luminous", 5, needs="alive grown luminous",   forbids="hot toxic metal", priority=95),
    _b("mill",       "structure", "mineral heavy powered", 5, needs="powered mineral",       forbids="hot toxic",       priority=96),
    # Outranks mill: a woven pool should land here, and every loom pool also
    # contains "powered mineral".
    _b("loom",       "machine",   "woven precise powered", 5, needs="powered woven",         forbids="hot",             priority=97),
]

# --------------------------------------------------------------------------
# Tier 6 -- industry. Powered machines compound: the dynamo marries power to
# light, and everything scientific above tier 6 descends from it.
# --------------------------------------------------------------------------

TIER6 = [
    _b("engine",        "machine",   "powered hot heavy",     6, needs="metal precise hot wet",  forbids="grown toxic",     priority=110),
    _b("dynamo",        "machine",   "powered luminous precise", 6, needs="powered precise luminous", forbids="grown hot",  priority=111),
    _b("blast_furnace", "structure", "mineral heavy hot",     6, needs="powered hot toxic",      forbids="alive wet",       priority=112),
    _b("automaton",     "machine",   "alive powered precise", 6, needs="powered precise alive",  forbids="grown",           priority=113),
    _b("cold_store",    "machine",   "cold powered hollow",   6, needs="cold powered",           forbids="hot",             priority=114),
    _b("chronometer",   "tool",      "metal precise luminous", 6, needs="metal precise luminous", forbids="powered wet hot", priority=115),
    _b("cloth",         "material",  "woven precise",         6, needs="woven powered grown",    forbids="mineral hot",     priority=116),
]

# Phase 2: tiers 4-9, authored against a played tier 1-3 rather than a
# simulation. Same discipline as above -- every bucket hand-authored, one
# keystone per tier gating the next tier's defining trait.
# --------------------------------------------------------------------------
# Tier 7 -- knowledge. The first "idea" (theory, distilled from instruments)
# and the first "sacred" thing (the temple). Ideas weigh nothing and gate
# everything above them.
# --------------------------------------------------------------------------
# theory needs four traits on purpose: three would be a subset of the
# chronometer's own traits and chronometer + chronometer must stay a dud.

TIER7 = [
    _b("theory",      "idea",      "luminous precise",        7, needs="metal precise luminous mineral", forbids="powered hot wet grown", priority=130),
    # Outranks theory: every observatory pool also contains theory's needs,
    # but only pools with "hollow" should build the dome.
    _b("observatory", "structure", "luminous precise hollow", 7, needs="precise luminous hollow", forbids="powered wet",   priority=131),
    _b("temple",      "structure", "sacred mineral luminous", 7, needs="woven luminous precise",  forbids="powered hot toxic", priority=132),
    _b("turbine",     "machine",   "powered precise heavy",   7, needs="powered hot luminous",    forbids="grown mineral", priority=133),
    _b("serum",       "material",  "alive precise toxic",     7, needs="alive precise toxic",     forbids="mineral hot",   priority=134),
    _b("press",       "machine",   "woven metal powered",     7, needs="woven metal powered",     forbids="hot grown sacred", priority=135),
]

# --------------------------------------------------------------------------
# Tier 8 -- the first artifacts. Sacred things start combining with the
# industrial line, which is where the endgame's flavour lives.
# --------------------------------------------------------------------------

TIER8 = [
    _b("reactor", "machine",  "powered luminous toxic", 8, needs="powered precise toxic", forbids="alive sacred grown", priority=150),
    _b("oracle",  "artifact", "sacred luminous precise", 8, needs="sacred precise",       forbids="powered wet toxic",  priority=151),
    # Outranks oracle: a sacred + metal pool should land here, and those pools
    # usually carry "precise" too.
    _b("relic",   "artifact", "sacred metal luminous",  8, needs="sacred metal",          forbids="alive grown",        priority=152),
    _b("airship", "machine",  "powered hollow woven",   8, needs="powered hollow heavy",  forbids="sacred grown toxic", priority=153),
    # Outranks oracle for the same reason as relic: serum pools carry precise.
    _b("panacea", "material", "alive sacred wet",       8, needs="alive sacred",          forbids="powered metal",      priority=154),
    _b("archive", "idea",     "luminous woven precise", 8, needs="woven luminous",        forbids="hot wet grown mineral", priority=155),
]

# --------------------------------------------------------------------------
# Tier 9 -- capstones. Five endings, one per line the game has been growing:
# power, life, metal, knowledge, and the sky. Nothing needs anything above
# these; they are what the whole yard was for.
# --------------------------------------------------------------------------

TIER9 = [
    _b("world_engine", "artifact", "powered sacred precise", 9, needs="powered sacred",      forbids="grown wet",          priority=170),
    _b("genesis_seed", "artifact", "alive sacred luminous",  9, needs="alive sacred grown",  forbids="powered toxic metal", priority=171),
    _b("star_forge",   "artifact", "metal sacred hot",       9, needs="sacred metal hot",    forbids="alive wet",          priority=172),
    _b("revelation",   "idea",     "sacred luminous woven",  9, needs="sacred woven",        forbids="powered metal hot",  priority=173),
    _b("leviathan",    "creature", "alive powered hollow",   9, needs="powered alive hollow", forbids="sacred mineral",    priority=174),
]

ALL: List[Bucket] = (
    STARTERS + TIER2 + TIER3 + TIER4 + TIER5 + TIER6 + TIER7 + TIER8 + TIER9
)

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
        # The same pattern continued up the tree: every third tier or so, a
        # structure that mass-produces the item the next stretch of chains
        # eats. Without these, a tier-7 chain needs the whole pyramid below it
        # standing in the yard, and the slots run out long before the coins do.
        Producer("forge",         "bloom",  12.0, 2500,    "Forge"),
        Producer("greenhouse",    "sprout",  4.0, 12000,   "Greenhouse"),
        Producer("blast_furnace", "iron",   15.0, 60000,   "Blast Furnace"),
        Producer("reactor",       "steel",  20.0, 1200000, "Reactor"),
    ]
}

# Placing a factory automates a recipe you have already discovered: it consumes
# the inputs from your stock and produces the output on a timer. This is what
# makes tier-1 items permanent infrastructure instead of something you outgrow
# -- every tier-3 chain still eats clay at the bottom.
FACTORY_PLACE_COST_MULTIPLIER = 8   # x the output's sell value
FACTORY_SECS = {2: 10.0, 3: 18.0, 4: 30.0, 5: 48.0, 6: 75.0, 7: 110.0, 8: 160.0, 9: 240.0}


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
