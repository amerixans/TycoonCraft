"""Guard the pacing.

`tools/simulate.py` is the tuning instrument; this is the ratchet. Without it,
any later change to a production rate, a craft cost or a tier price can quietly
turn an eight-hour run into a forty-hour one, and nobody would find out until a
friend gave up halfway through.

Cheap enough to run on every commit: the sim steps one simulated second at a
time but the whole thing is arithmetic over ~20 placements.
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

from game import buckets                       # noqa: E402
from simulate import Sim, project_remaining     # noqa: E402

TARGET_LOW_HOURS = 6.0
TARGET_HIGH_HOURS = 10.0


def full_run_hours(decide_every: float) -> tuple[float, dict[int, float]]:
    sim = Sim("test", decide_every)
    unlocked = sim.run()
    reached = max(unlocked)
    hours = unlocked[reached] / 3600
    for _, extra in project_remaining(sim.realised_income_per_hour).items():
        hours += extra
    return hours, unlocked


def test_a_casual_run_lands_in_the_target_window():
    """Someone who checks in every twenty minutes should finish in 6-10 hours.

    This is the number that matters. A curve that only works for a player who
    reinvests every coin the instant they earn it is not balanced, it is
    balanced-for-one-person.
    """
    hours, _ = full_run_hours(decide_every=1200.0)
    assert TARGET_LOW_HOURS <= hours <= TARGET_HIGH_HOURS, (
        f"a casual run takes {hours:.1f}h, outside the {TARGET_LOW_HOURS}-"
        f"{TARGET_HIGH_HOURS}h target. Adjust TIER_UNLOCK_COST in game/buckets.py "
        f"and re-run tools/simulate.py."
    )


def test_an_optimal_run_is_not_trivially_short():
    """Playing well should be rewarded, but not by a factor of ten. If the sharp
    run collapses to under an hour the tier costs have stopped mattering."""
    hours, _ = full_run_hours(decide_every=20.0)
    assert hours > 2.0, f"an optimal run finishes in {hours:.1f}h — too fast to feel like progress"


def test_the_early_game_is_not_a_wait():
    """Tier 2 inside the first half hour, tier 3 inside two hours.

    The opening is where v1 lost people ("if you are one of the first players you
    just wait a while"), so the first unlock has to arrive while the player is
    still curious.
    """
    _, unlocked = full_run_hours(decide_every=1200.0)
    assert unlocked[2] / 3600 < 0.5, (
        f"tier 2 takes {unlocked[2]/3600:.2f}h — the first unlock must land early"
    )
    assert unlocked[3] / 3600 < 2.0, f"tier 3 takes {unlocked[3]/3600:.2f}h"


def test_every_authored_tier_is_reachable_in_the_sim():
    """Not just priced -- actually achievable by the decision policy. A tier
    whose recipes cannot be fed is a wall, which is what v1 shipped."""
    _, unlocked = full_run_hours(decide_every=1200.0)
    assert max(unlocked) == buckets.MAX_AUTHORED_TIER, (
        f"the simulated player stalled at tier {max(unlocked)} of "
        f"{buckets.MAX_AUTHORED_TIER}"
    )


def test_unlock_costs_climb_monotonically():
    costs = [buckets.TIER_UNLOCK_COST[t] for t in sorted(buckets.TIER_UNLOCK_COST)]
    assert costs == sorted(costs)
    # Each tier should cost meaningfully more, or the ceiling stops being a
    # decision and becomes a formality.
    for a, b in zip(costs, costs[1:]):
        assert b >= a * 3, f"unlock costs {a} -> {b} barely climb"
