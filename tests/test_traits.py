"""Tests for the combination engine and the authored tree.

The load-bearing one is `test_resolution_table`: it walks every combination a
player can actually reach and prints what each resolves to. Read its output
(`pytest -s -k resolution`) after any edit to the bucket table -- a too-loose
`needs` shadows a sibling rather than erroring, and this is what surfaces that.
"""

from __future__ import annotations

import itertools

import pytest

from game import buckets
from game.buckets import ALL, BY_ID, STARTERS
from game.traits import MAX_TRAITS, TRAIT_ORDER, TRAITS, Bucket, Dud, combine


def reachable(ceiling: int) -> set[str]:
    """Every bucket a player can hold, starting from the four starters.

    Fixed-point iteration rather than a one-pass sweep: tier-3 results need
    tier-2 inputs that themselves have to be discovered first, so a single pass
    would under-report.
    """
    held = {b.id for b in STARTERS}
    while True:
        grown = set(held)
        for a_id, b_id in itertools.combinations_with_replacement(sorted(held), 2):
            result = combine(BY_ID[a_id], BY_ID[b_id], ceiling, ALL)
            if isinstance(result, Bucket):
                grown.add(result.id)
        if grown == held:
            return held
        held = grown


def test_validate_passes_at_import():
    # buckets.validate() runs at import; calling it again is cheap and makes the
    # dependency explicit rather than implicit in the import graph.
    buckets.validate()


def test_starters_are_not_craftable():
    # v1's era-5 keystone collided with an era-6 *starter* of the same name and
    # hard-blocked progression. Starters must never be reachable as results.
    for s in STARTERS:
        assert not s.craftable, f"{s.id} is a starter and must not be craftable"

    for a, b in itertools.combinations_with_replacement(STARTERS, 2):
        result = combine(a, b, buckets.MAX_AUTHORED_TIER, ALL)
        if isinstance(result, Bucket):
            assert result.id not in {s.id for s in STARTERS}


def test_all_six_starter_pairs_react():
    """The opening must have no dead ends -- this is complaint #5 and #3 both.

    A new player has exactly four items and six possible moves. If any of them
    is a dud, the first thirty seconds teach that the game is broken.
    """
    results = {}
    for a, b in itertools.combinations(STARTERS, 2):
        result = combine(a, b, 2, ALL)
        assert isinstance(result, Bucket), (
            f"{a.id} + {b.id} is a dud at ceiling 2 -- the opening must always react"
        )
        results[(a.id, b.id)] = result.id

    # And each pair must give something *different*, or the opening feels fake.
    assert len(set(results.values())) == 6, (
        f"starter pairs collapse onto {len(set(results.values()))} results: {results}"
    )


def test_combine_is_commutative():
    """A + B and B + A must be the same craft. Players expect it, and it halves
    the recipe cache."""
    for a, b in itertools.combinations_with_replacement(ALL, 2):
        for ceiling in (1, 2, 3):
            ab = combine(a, b, ceiling, ALL)
            ba = combine(b, a, ceiling, ALL)
            a_id = ab.id if isinstance(ab, Bucket) else None
            b_id = ba.id if isinstance(ba, Bucket) else None
            assert a_id == b_id, f"{a.id}+{b.id} != {b.id}+{a.id} at ceiling {ceiling}"


def test_self_combination_is_always_a_dud():
    """X + X can never produce something new.

    This is the "Smoke Stack + Smoke Stack = Double Smoke Stack" test -- the
    single most-cited complaint about v1. It holds structurally: the pool of
    X + X is X's own traits, so the best match is X itself, and the dud check
    catches it.
    """
    for b in ALL:
        for ceiling in (1, 2, 3):
            result = combine(b, b, ceiling, ALL)
            assert isinstance(result, Dud), (
                f"{b.id} + {b.id} produced {result.id if isinstance(result, Bucket) else result}"
            )


def test_never_exceeds_ceiling():
    for a, b in itertools.combinations_with_replacement(ALL, 2):
        for ceiling in (1, 2, 3):
            result = combine(a, b, ceiling, ALL)
            if isinstance(result, Bucket):
                assert result.tier <= ceiling, (
                    f"{a.id}+{b.id} produced tier {result.tier} at ceiling {ceiling}"
                )


def test_never_jumps_more_than_one_tier():
    for a, b in itertools.combinations_with_replacement(ALL, 2):
        result = combine(a, b, buckets.MAX_AUTHORED_TIER, ALL)
        if isinstance(result, Bucket):
            assert result.tier <= max(a.tier, b.tier) + 1, (
                f"{a.id}(t{a.tier})+{b.id}(t{b.tier}) jumped to t{result.tier}"
            )


def test_ceiling_one_produces_nothing():
    """At ceiling 1 there is nothing above the starters, so every craft is a
    dud. Sanity check on the gate itself."""
    for a, b in itertools.combinations_with_replacement(STARTERS, 2):
        assert isinstance(combine(a, b, 1, ALL), Dud)


def test_all_buckets_reachable():
    """No orphaned content. v1 shipped eight unlock hints naming items that no
    recipe could produce; this is the test that would have caught it."""
    held = reachable(buckets.MAX_AUTHORED_TIER)
    orphans = {b.id for b in ALL} - held
    assert not orphans, f"unreachable buckets: {sorted(orphans)}"


def test_raising_the_ceiling_unlocks_strictly_more():
    """The core progression promise: buying a tier must never take anything
    away, and must always add something."""
    prev = reachable(1)
    for ceiling in (2, 3):
        now = reachable(ceiling)
        assert prev < now, f"ceiling {ceiling} added nothing over {ceiling - 1}"
        prev = now


def test_at_the_ceiling_the_space_runs_dry():
    """Once every reachable bucket is held, everything must come back a dud.

    This is the pacing signal, not just a nicety: running dry is how the game
    tells the player to go buy the next tier. If some combination kept
    producing new things forever we would be back to v1's endless drift.
    """
    for ceiling in (2, 3):
        held = reachable(ceiling)
        for a_id, b_id in itertools.combinations_with_replacement(sorted(held), 2):
            result = combine(BY_ID[a_id], BY_ID[b_id], ceiling, ALL)
            if isinstance(result, Bucket):
                assert result.id in held, (
                    f"at ceiling {ceiling} the space was supposed to be closed, but "
                    f"{a_id}+{b_id} produced the new bucket {result.id}"
                )


def test_trait_order_covers_every_trait():
    """trim_traits and describe() both walk TRAIT_ORDER; a trait missing from it
    would be silently dropped from display and from trimming."""
    assert set(TRAIT_ORDER) == TRAITS
    assert len(TRAIT_ORDER) == len(TRAITS)


def test_no_bucket_exceeds_max_traits():
    for b in ALL:
        assert len(b.traits) <= MAX_TRAITS


def test_resolution_table(capsys):
    """Not an assertion so much as a report. Run with -s and read it."""
    ceiling = buckets.MAX_AUTHORED_TIER
    held = sorted(reachable(ceiling), key=lambda i: (BY_ID[i].tier, i))

    lines = ["", f"{'a':<10} {'b':<10} -> result", "-" * 44]
    duds = 0
    for a_id, b_id in itertools.combinations_with_replacement(held, 2):
        result = combine(BY_ID[a_id], BY_ID[b_id], ceiling, ALL)
        if isinstance(result, Bucket):
            lines.append(f"{a_id:<10} {b_id:<10} -> {result.id} (t{result.tier})")
        else:
            duds += 1
    lines.append("-" * 44)
    total = len(held) * (len(held) + 1) // 2
    lines.append(f"{total - duds} productive / {total} pairs, {duds} duds")
    lines.append(f"{len(held)} buckets reachable at ceiling {ceiling}")

    with capsys.disabled():
        print("\n".join(lines))

    # A tree where almost everything is a dud is not fun to explore.
    productive_ratio = (total - duds) / total
    assert productive_ratio > 0.10, (
        f"only {productive_ratio:.0%} of pairs do anything -- the tree is too sparse"
    )
