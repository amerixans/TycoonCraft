"""Production, offline accrual, selling, and tier unlocks.

Deliberately pure: every function here takes plain dicts and a timestamp and
returns plain data. `store.py` owns persistence. That split is what lets
`tools/simulate.py` play a full six-hour run in a fraction of a second to check
the pacing, which is the only practical way to balance an idle game.

Two v1 bugs this file exists to not repeat:

* **Offline earnings were silently zeroed.** v1's `update_player_coins` skipped
  any building whose `retire_at` had passed, so being away for a day credited
  nothing at all instead of the hour the building had actually been running.
  Here, `tick()` is the single path by which time passes, it is called on every
  request, and it is exercised directly by `test_offline_accrual`.

* **Buildings deleted themselves.** v1 retired everything you placed, so coins
  spent on a building bought a thing that expired. Nothing here expires.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from . import buckets
from .buckets import BY_ID, PRODUCERS

# Come back tomorrow and you get eight hours of production, not twenty-four.
# Enough that sleeping is rewarded, not so much that the game plays itself
# while you are away -- and it bounds the arithmetic in `tick()`, so a player
# who vanishes for a month does not return to an integer overflow.
OFFLINE_CAP_SECS = 8 * 3600

# Enough to afford exactly one tier-2 craft. The first discovery should land in
# the first fifteen seconds, before the player has had to think about money;
# after that, income is the constraint.
STARTING_COINS = 30

# Clicking a producer completes its current cycle rather than granting a free
# unit, so hand-gathering can never outpace the machine by more than one unit
# per click. The cooldown is server-enforced -- not because three friends will
# script it, but because a client-only cooldown is not a rule, it is a request.
HAND_GATHER_COOLDOWN_SECS = 0.5


@dataclass
class Placement:
    """Something in the yard, earning.

    A producer yields its item from nothing. A factory runs a recipe: it
    consumes one of each input from stock and yields one output. That
    consumption is what keeps tier-1 items permanently valuable -- every
    tier-3 chain still eats clay at the bottom, so your first Clay Pit is still
    load-bearing in hour ten.
    """

    id: int
    kind: str                      # "producer" | "factory"
    bucket_id: str                 # producer: the producer. factory: its output.
    progress: float = 0.0          # seconds banked toward the next unit
    inputs: Tuple[str, str] = ()   # factory only: the two input item keys
    output_item: str = ""          # factory only: the item key it yields
    item_key: str = ""             # producer only: the item key it yields
    autosell: bool = False         # sell output on completion instead of stocking it

    def secs_per_unit(self) -> float:
        if self.kind == "producer":
            return PRODUCERS[self.bucket_id].secs
        return buckets.FACTORY_SECS[BY_ID[self.bucket_id].tier]


@dataclass
class TickResult:
    coins_earned: float = 0.0
    produced: Dict[str, float] = field(default_factory=dict)
    consumed: Dict[str, float] = field(default_factory=dict)
    stalled: List[int] = field(default_factory=list)   # placement ids short on inputs
    seconds_applied: float = 0.0
    seconds_dropped: float = 0.0   # elapsed beyond the offline cap


def tick(
    placements: List[Placement],
    stock: Dict[str, float],
    last_tick: float,
    now: float,
    item_bucket: Dict[str, str],
) -> TickResult:
    """Advance every placement from `last_tick` to `now`.

    `stock` is mutated in place -- callers persist it afterwards. `item_bucket`
    maps item keys to bucket ids so sale values can be looked up without the
    item registry being passed around.

    Clamping to OFFLINE_CAP_SECS is reported in `seconds_dropped` rather than
    hidden, so the UI can honestly say "your yard was full" instead of a
    player quietly wondering where their afternoon went.
    """
    result = TickResult()

    elapsed = max(0.0, now - last_tick)
    if elapsed > OFFLINE_CAP_SECS:
        result.seconds_dropped = elapsed - OFFLINE_CAP_SECS
        elapsed = OFFLINE_CAP_SECS
    result.seconds_applied = elapsed

    if elapsed <= 0:
        return result

    for placement in placements:
        secs = placement.secs_per_unit()
        if secs <= 0:                      # authored bad data; skip rather than divide
            continue

        banked = placement.progress + elapsed
        units = int(banked // secs)

        if placement.kind == "producer":
            if units:
                key = placement.item_key or placement.bucket_id
                _credit(placement, result, stock, key, units, item_bucket)
            placement.progress = banked - units * secs
            continue

        # Factory. Each unit needs one of each input, so throughput is capped
        # by the scarcer input -- that cap is the supply problem that makes this
        # a production chain rather than a coin faucet.
        a, b = placement.inputs
        if units:
            # How many units of each input one run costs. a == b cannot arise
            # from a real recipe (self-combination is always a dud), but a
            # hand-edited database should starve rather than double-spend.
            need = {a: 1, b: 1} if a != b else {a: 2}
            affordable = int(min(stock.get(k, 0.0) // n for k, n in need.items()))
            runs = max(0, min(units, affordable))

            if runs:
                for key, per_run in need.items():
                    _debit(result, stock, key, runs * per_run)
                _credit(placement, result, stock, placement.output_item, runs, item_bucket)

            if runs < units:
                result.stalled.append(placement.id)
                # Bank at most one unit of progress while starved, so a factory
                # that has been idle for a week does not fire a week's worth of
                # output the instant its inputs arrive.
                placement.progress = min(banked - runs * secs, secs)
            else:
                placement.progress = banked - units * secs
        else:
            placement.progress = banked

    return result


def _credit(
    placement: Placement,
    result: TickResult,
    stock: Dict[str, float],
    item_key: str,
    units: int,
    item_bucket: Dict[str, str],
) -> None:
    if placement.autosell:
        bucket_id = item_bucket.get(item_key)
        if bucket_id:
            result.coins_earned += units * buckets.sell_value(bucket_id)
            return
        # Unknown item and autosell on: stock it rather than silently vaporising
        # the output. Falling through is the safe direction.
    stock[item_key] = stock.get(item_key, 0.0) + units
    result.produced[item_key] = result.produced.get(item_key, 0.0) + units


def _debit(result: TickResult, stock: Dict[str, float], item_key: str, units: float) -> None:
    stock[item_key] = stock.get(item_key, 0.0) - units
    if stock[item_key] <= 0:
        stock.pop(item_key, None)
    result.consumed[item_key] = result.consumed.get(item_key, 0.0) + units


def hand_gather(placement: Placement, now: float, last_gather: float) -> bool:
    """Complete a producer's current cycle. Returns False if still cooling down.

    This is what removes v1's dead opening minute: you land with a Clay Pit and
    can click it, so there is something to do in second one and automation
    arrives as relief rather than as a gate.
    """
    if placement.kind != "producer":
        return False
    if now - last_gather < HAND_GATHER_COOLDOWN_SECS:
        return False
    placement.progress = placement.secs_per_unit()
    return True


def sale_price(bucket_id: str, qty: float) -> int:
    """Coins for selling `qty`. Floored: partial units are production progress,
    not merchandise."""
    return int(qty) * buckets.sell_value(bucket_id)


def yard_slots(ceiling: int) -> int:
    return buckets.TIER_YARD_SLOTS[min(ceiling, max(buckets.TIER_YARD_SLOTS))]


def unlock_cost(tier: int) -> Optional[int]:
    """Coins to raise the ceiling to `tier`, or None if there is no such tier
    (yet -- tiers 4-6 land in phase 2)."""
    if tier > buckets.MAX_AUTHORED_TIER:
        return None
    return buckets.TIER_UNLOCK_COST.get(tier)


def income_per_hour(
    placements: List[Placement],
    item_bucket: Dict[str, str],
) -> float:
    """Best-case coins/hour, assuming no factory ever starves.

    Displayed in the UI and used by the balance sim as an upper bound. Real
    income is lower whenever a chain is input-limited, which is the interesting
    case and the reason this is labelled "best case" on screen.
    """
    total = 0.0
    for p in placements:
        if not p.autosell:
            continue
        key = p.output_item if p.kind == "factory" else (p.item_key or p.bucket_id)
        bucket_id = item_bucket.get(key)
        if not bucket_id:
            continue
        total += (3600.0 / p.secs_per_unit()) * buckets.sell_value(bucket_id)
    return total
