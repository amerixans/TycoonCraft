"""The combination engine.

This module is the answer to the question that killed the first version of the
game: *what stops "Smoke Stack + Smoke Stack = Double Smoke Stack"?*

In v1 a craft was `f(A, B) -> a noun invented by a language model`. The noun
space is unbounded and the cheapest move available to any model is conjunction
("Double X") or modification ("Reinforced X Mk II"), so results got strictly
more specific forever with nothing pulling them back. No prompt fixes that --
v1's prompt had five separate anti-concatenation rules and it happened anyway,
because it is a property of the mechanic, not of the wording.

So here the model does not decide anything mechanical. An item's mechanical
identity is a **bucket**: a (kind, traits, tier) triple drawn from closed
vocabularies, and every bucket that exists is hand-authored in `buckets.py`.
Combining is a pure function over those buckets. The model is called afterwards,
and only to put a name on something whose properties are already fixed.

Three things fall out of that, and they are the whole design:

1. If the resolved bucket is one the player already has as an input, the craft
   is a **dud** -- resolved here, for free, with no API call and no new row.
   Smoke Stack + Smoke Stack cannot become Double Smoke Stack because no
   authored bucket takes `{hot, structure}` and returns something new.

2. Recipes match on *traits*, not on item names, so two items in the same
   bucket are interchangeable everywhere. You can never be blocked waiting for
   one specific noun to show up -- which was v1's other great sin.

3. The tier ceiling limits how high a craft can reach, never whether it can
   happen. At the ceiling you get lateral results; once the lateral space is
   exhausted everything turns to duds, and that is the game telling you it is
   time to buy the next tier.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import FrozenSet, Iterable, Optional

# --------------------------------------------------------------------------
# The closed vocabularies
# --------------------------------------------------------------------------
# Adding to these is a content decision, not a code change -- but nothing may
# be *removed* without migrating the bucket table, so `validate()` in
# buckets.py checks every authored bucket against these sets at import time.

TRAITS: FrozenSet[str] = frozenset({
    "hot", "cold", "wet", "sharp", "heavy", "alive", "grown", "mineral",
    "metal", "powered", "precise", "sacred", "toxic", "hollow", "woven",
    "luminous",
})

KINDS: FrozenSet[str] = frozenset({
    "material", "tool", "creature", "structure", "machine", "energy",
    "idea", "artifact",
})

# How many traits an item may carry. Three is a deliberate ceiling: it keeps
# the reachable bucket space small enough to author by hand and balance, and it
# keeps the UI honest (three chips fit on a card).
MAX_TRAITS = 3

MIN_TIER = 1
MAX_TIER = 6


@dataclass(frozen=True, slots=True)
class Bucket:
    """An item's mechanical identity. Two items in the same bucket are
    mechanically interchangeable; only their name, emoji and flavour differ.

    Frozen and slotted because these are hashed, compared and held in sets on
    every craft -- identity is the entire point of the type.
    """

    id: str
    kind: str
    traits: FrozenSet[str]
    tier: int

    # Reaction predicate. A craft resolves to this bucket when `needs` is a
    # subset of the combined trait pool of both inputs and `forbids` is
    # disjoint from it. `forbids` is what lets one trait pair fan out to
    # several results: clay + ember is a fired brick, but *wet* clay + ember is
    # ceramic, because fired_brick forbids "wet".
    needs: FrozenSet[str] = frozenset()
    forbids: FrozenSet[str] = frozenset()

    # Tie-break when several buckets match the same pool at the same tier.
    # Higher wins. Distinct within a tier -- enforced by validate().
    priority: int = 0

    # Reachable only by combining, never granted. Starters set this False.
    craftable: bool = True

    def matches(self, pool: FrozenSet[str]) -> bool:
        """Would a craft whose combined trait pool is `pool` resolve here?"""
        return (
            self.craftable
            and self.needs <= pool
            and not (self.forbids & pool)
        )

    def describe(self) -> str:
        """Human-readable identity, for fallback names and debug output."""
        order = [t for t in TRAIT_ORDER if t in self.traits]
        return f"tier-{self.tier} {' '.join(order)} {self.kind}"


# Stable trait ordering for display and for deterministic trimming. Roughly
# "most defining first": a thing's material nature reads before its state,
# which reads before its refinements.
TRAIT_ORDER = (
    "alive", "grown", "mineral", "metal", "woven", "hollow",
    "hot", "cold", "wet", "powered", "luminous", "sacred",
    "sharp", "heavy", "precise", "toxic",
)


class Dud:
    """Not an error -- a legitimate, informative, *free* outcome.

    Charging coins for "nothing happened" would make experimenting miserable,
    and experimenting is how a player learns the trait system. So duds are
    resolved before any spend and before any API call. `reason` is shown in the
    UI so the player learns something rather than just losing a click.
    """

    __slots__ = ("reason",)

    NO_REACTION = "these two don't react"
    SAME_AS_INPUT = "you'd just get the same thing back"
    AT_CEILING = "nothing new at this tier — unlock the next one"

    def __init__(self, reason: str) -> None:
        self.reason = reason

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"Dud({self.reason!r})"


def trait_pool(a: Bucket, b: Bucket) -> FrozenSet[str]:
    """The traits a craft has to work with.

    Union, so the operation is commutative: A+B and B+A are the same craft,
    which players absolutely expect and which halves the recipe cache.
    """
    return a.traits | b.traits


def trim_traits(traits: Iterable[str]) -> FrozenSet[str]:
    """Cut a trait set down to MAX_TRAITS, keeping the most defining ones.

    Deterministic via TRAIT_ORDER -- never rely on set iteration order here,
    it varies by process and would make the recipe cache non-reproducible.
    """
    ranked = [t for t in TRAIT_ORDER if t in traits]
    return frozenset(ranked[:MAX_TRAITS])


def combine(
    a: Bucket,
    b: Bucket,
    ceiling: int,
    catalogue: Iterable[Bucket],
) -> Bucket | Dud:
    """Resolve a craft. Pure, deterministic, commutative, and free.

    `ceiling` is the player's unlocked tier. It bounds how high the result can
    reach -- it never blocks the craft itself, which is the fix for v1's
    "same era only" rule that made most pairs in your inventory illegal.

    The result is the highest-tier authored bucket that (a) matches the
    combined trait pool, (b) sits at the input tier or one above it, and
    (c) is within the ceiling. Preferring the highest tier is what makes
    "unlock a tier, then retry your old combinations" pay off.
    """
    pool = trait_pool(a, b)
    base = max(a.tier, b.tier)

    # One above the inputs is the reward for using good ingredients; never two,
    # or the tier curve stops meaning anything.
    reachable = [t for t in (base + 1, base) if MIN_TIER <= t <= min(ceiling, MAX_TIER)]
    if not reachable:
        return Dud(Dud.AT_CEILING)

    candidates = [
        bucket
        for bucket in catalogue
        if bucket.tier in reachable and bucket.matches(pool)
    ]
    if not candidates:
        # Distinguish "you have not unlocked the thing this would make" from
        # "these genuinely don't react", so the message can teach.
        blocked_above = any(
            bucket.matches(pool) and base < bucket.tier <= MAX_TIER
            for bucket in catalogue
        )
        return Dud(Dud.AT_CEILING if blocked_above else Dud.NO_REACTION)

    # Highest tier first, then authored priority. `id` last so the ordering is
    # total and the cache is reproducible across processes.
    candidates.sort(key=lambda x: (x.tier, x.priority, x.id), reverse=True)
    result = candidates[0]

    # The dud check that kills the specificity spiral. Note it compares
    # buckets, not names: two differently-named items in the same bucket are
    # the same thing, so this catches "Smokestack + Smoke stack" too.
    if result.id in (a.id, b.id):
        return Dud(Dud.SAME_AS_INPUT)

    return result


_KIND_EMOJI = {
    "material": "\U0001f9f1", "tool": "\U0001f528", "creature": "\U0001f43e",
    "structure": "\U0001f3da", "machine": "⚙", "energy": "⚡",
    "idea": "\U0001f4a1", "artifact": "\U0001f52e",
}

# Distinguishes two items that share a bucket -- `ceramic<clay+steam` and
# `ceramic<mud+ember` are mechanically identical but should not both be called
# plain "Ceramic" on the shelf. Chosen by hash of the input pair, so it is
# stable across processes and across restarts.
_QUALIFIERS = (
    "Rough", "Fine", "Coarse", "Pale", "Dark", "Common", "Crude", "Keen",
)


def fallback_name(a_name: str, b_name: str, bucket: Bucket) -> tuple[str, str]:
    """A name and emoji for when the API is unreachable, slow, or unconfigured.

    The game must stay playable with no API key at all -- that is why this
    exists, and why /health reports `{"llm": "unconfigured"}` rather than
    failing.

    The noun is the bucket id, which is already a hand-authored English word
    ("Ceramic", "Crucible", "Sickle"), so it is unique by construction and reads
    like an actual item. Two earlier attempts built the name out of traits
    instead and both collided badly -- `mud` and `brick` came out identical, then
    four different buckets all came out "Lithic Shell". Trait vocabularies are
    too small to name a 3-trait space uniquely; the ids already are unique,
    because `buckets.validate()` enforces it.

    Deterministic, so the same pair always yields the same fallback and a later
    successful call can replace it exactly once.
    """
    noun = bucket.id.replace("_", " ").title()

    # Stable across runs: Python's str hash is salted per process, so derive the
    # qualifier from the characters instead.
    pair = "".join(sorted((a_name, b_name)))
    index = sum(pair.encode("utf-8")) % len(_QUALIFIERS)

    return f"{_QUALIFIERS[index]} {noun}", _KIND_EMOJI[bucket.kind]
