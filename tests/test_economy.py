"""Tests for production, offline accrual and selling.

`test_offline_accrual_is_not_lost` is the important one: it is the regression
test for the v1 bug where being away for a day credited zero coins because
`update_player_coins` skipped every building whose `retire_at` had passed.
"""

from __future__ import annotations

import pytest

from game import buckets, economy
from game.economy import OFFLINE_CAP_SECS, Placement, tick

# clay: 6.0s per unit. water: 5.0s.
ITEM_BUCKET = {"clay": "clay", "water": "water", "mud": "mud", "brick": "brick"}


def producer(pid=1, bucket="clay", autosell=False, progress=0.0):
    return Placement(
        id=pid, kind="producer", bucket_id=bucket, item_key=bucket,
        progress=progress, autosell=autosell,
    )


def factory(pid=9, out_bucket="mud", inputs=("clay", "water"), autosell=False):
    return Placement(
        id=pid, kind="factory", bucket_id=out_bucket, inputs=inputs,
        output_item=out_bucket, autosell=autosell,
    )


def test_producer_yields_on_schedule():
    p = producer()
    stock = {}
    result = tick([p], stock, last_tick=0, now=60, item_bucket=ITEM_BUCKET)
    # 60s at 6s each
    assert stock["clay"] == 10
    assert result.produced["clay"] == 10


def test_partial_progress_is_kept_not_dropped():
    """A tick that lands mid-cycle must bank the remainder, or frequent polling
    would starve production -- the client polls every couple of seconds."""
    p = producer()
    stock = {}
    for _ in range(6):
        tick([p], stock, last_tick=0, now=1, item_bucket=ITEM_BUCKET)
        p.progress = p.progress  # explicit: state carries across ticks
    # Six one-second ticks on a 6s producer is exactly one unit.
    assert stock.get("clay", 0) == 1


def test_offline_accrual_is_not_lost():
    """Away for two hours, come back to two hours of production.

    v1 credited nothing here. This is the whole reason this module is pure and
    directly testable.
    """
    p = producer()
    stock = {}
    two_hours = 2 * 3600
    tick([p], stock, last_tick=0, now=two_hours, item_bucket=ITEM_BUCKET)
    assert stock["clay"] == two_hours // 6


def test_offline_is_capped_and_says_so():
    p = producer()
    stock = {}
    result = tick([p], stock, last_tick=0, now=48 * 3600, item_bucket=ITEM_BUCKET)
    assert stock["clay"] == OFFLINE_CAP_SECS // 6
    assert result.seconds_applied == OFFLINE_CAP_SECS
    # Reported rather than hidden, so the UI can say "your yard was full".
    assert result.seconds_dropped == pytest.approx(48 * 3600 - OFFLINE_CAP_SECS)


def test_no_time_no_production():
    p = producer()
    stock = {}
    result = tick([p], stock, last_tick=100, now=100, item_bucket=ITEM_BUCKET)
    assert stock == {}
    assert result.seconds_applied == 0


def test_clock_going_backwards_produces_nothing():
    """Never trust a clock. A negative interval must not run production
    backwards or hand out free units."""
    p = producer()
    stock = {"clay": 3}
    tick([p], stock, last_tick=500, now=100, item_bucket=ITEM_BUCKET)
    assert stock == {"clay": 3}


def test_autosell_turns_output_into_coins_not_stock():
    p = producer(autosell=True)
    stock = {}
    result = tick([p], stock, last_tick=0, now=60, item_bucket=ITEM_BUCKET)
    assert stock == {}
    assert result.coins_earned == 10 * buckets.sell_value("clay")


def test_factory_consumes_inputs_and_yields_output():
    f = factory()
    stock = {"clay": 10, "water": 10}
    secs = buckets.FACTORY_SECS[buckets.BY_ID["mud"].tier]
    result = tick([f], stock, last_tick=0, now=secs * 3, item_bucket=ITEM_BUCKET)
    assert stock["mud"] == 3
    assert stock["clay"] == 7
    assert stock["water"] == 7
    assert not result.stalled


def test_factory_stalls_when_starved_and_reports_it():
    """The supply problem that makes this a production chain rather than a coin
    faucet. Throughput is capped by the scarcer input."""
    f = factory()
    stock = {"clay": 2, "water": 0}
    secs = buckets.FACTORY_SECS[buckets.BY_ID["mud"].tier]
    result = tick([f], stock, last_tick=0, now=secs * 5, item_bucket=ITEM_BUCKET)
    assert stock.get("mud", 0) == 0
    assert stock["clay"] == 2          # nothing consumed without a full recipe
    assert f.id in result.stalled


def test_a_starved_factory_does_not_bank_a_week_of_output():
    """Left starved for a long time then fed, a factory must not fire a week's
    worth of production in one tick."""
    f = factory()
    secs = buckets.FACTORY_SECS[buckets.BY_ID["mud"].tier]
    stock = {}
    tick([f], stock, last_tick=0, now=7 * 86400, item_bucket=ITEM_BUCKET)
    assert f.progress <= secs

    stock = {"clay": 100, "water": 100}
    tick([f], stock, last_tick=0, now=1, item_bucket=ITEM_BUCKET)
    assert stock["mud"] <= 1


def test_stock_never_goes_negative():
    f = factory()
    stock = {"clay": 1, "water": 1}
    secs = buckets.FACTORY_SECS[buckets.BY_ID["mud"].tier]
    tick([f], stock, last_tick=0, now=secs * 20, item_bucket=ITEM_BUCKET)
    assert all(v >= 0 for v in stock.values())
    assert stock.get("mud") == 1


def test_sale_price_floors_partial_units():
    """Partial quantities are production progress, not merchandise."""
    assert economy.sale_price("clay", 3.9) == 3 * buckets.sell_value("clay")
    assert economy.sale_price("clay", 0.5) == 0


def test_value_climbs_faster_than_craft_cost():
    """The promise that makes "unlock the next tier" always the right move.

    If craft cost ever caught up with sale value the run would stall, so this
    guards the shape of the curve rather than any single number.
    """
    for tier in range(2, buckets.MAX_AUTHORED_TIER + 1):
        value = buckets.TIER_SELL_VALUE[tier]
        cost = buckets.TIER_CRAFT_COST[tier]
        assert cost < value, f"tier {tier} costs more to craft than it sells for"

        # The real invariant: a craft consumes two items from the tier below,
        # so it is only worth doing if the output beats the inputs *plus* the
        # craft fee. If this goes negative the chain is a money pit and the run
        # stalls no matter how much you automate.
        inputs = 2 * buckets.TIER_SELL_VALUE[tier - 1]
        assert value - inputs - cost > 0, (
            f"tier {tier}: output {value} does not cover {inputs} of inputs "
            f"plus {cost} to craft"
        )

    ratios = [
        buckets.TIER_SELL_VALUE[t] / buckets.TIER_SELL_VALUE[t - 1]
        for t in range(2, buckets.MAX_AUTHORED_TIER + 1)
    ]
    assert min(ratios) >= 3, f"tier value should climb at least 3x, got {ratios}"


def test_automating_a_recipe_pays_back_in_reasonable_time():
    """A factory must repay its place cost quickly enough to feel worth it --
    automation is the fantasy, so it must not be a chore to justify."""
    for bucket_id in ("mud", "brick", "ceramic"):
        bucket = buckets.BY_ID[bucket_id]
        place = buckets.factory_place_cost(bucket_id)
        net_per_unit = (
            buckets.TIER_SELL_VALUE[bucket.tier]
            - 2 * buckets.TIER_SELL_VALUE[bucket.tier - 1]
        )
        assert net_per_unit > 0
        secs = buckets.FACTORY_SECS[bucket.tier]
        payback_mins = (place / net_per_unit) * secs / 60
        assert payback_mins < 12, (
            f"{bucket_id} factory takes {payback_mins:.0f} min to pay back"
        )


def test_yard_slots_grow_with_ceiling():
    slots = [economy.yard_slots(t) for t in range(1, 7)]
    assert slots == sorted(slots)
    assert slots[0] >= 4, "must fit the two starting producers plus room to grow"


def test_unlock_cost_is_none_past_authored_content():
    assert economy.unlock_cost(buckets.MAX_AUTHORED_TIER) is not None
    assert economy.unlock_cost(buckets.MAX_AUTHORED_TIER + 1) is None


def test_income_per_hour_counts_only_autosell():
    p_off = producer(pid=1, autosell=False)
    p_on = producer(pid=2, autosell=True)
    assert economy.income_per_hour([p_off], ITEM_BUCKET) == 0
    assert economy.income_per_hour([p_on], ITEM_BUCKET) > 0
