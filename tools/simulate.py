#!/usr/bin/env python3
"""Play the game very fast, to check the pacing.

Balancing an idle game by playing it is not practical -- the whole point is that
it takes hours. So this drives `game/economy.py` directly at a one-second step
and reports how long each tier unlock takes.

Two players are simulated, because a single "optimal" number is misleading:

  * **sharp** reinvests immediately and always automates the best thing it can.
    This is the floor on how long a run takes.
  * **casual** checks in every twenty minutes, buys something, wanders off.
    This is closer to how the game will actually be played, and it is the number
    that has to land inside the target.

Target: the full six-tier run in 6-10 hours of play. Tiers 4-6 are not authored
yet (phase 2), so those are projected from the cost and value curves, which are
authored for all six.

    python3 tools/simulate.py
    python3 tools/simulate.py --verbose
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game import buckets, economy                       # noqa: E402
from game.buckets import BY_ID, PRODUCERS               # noqa: E402
from game.economy import Placement                      # noqa: E402

STEP = 1.0
MAX_HOURS = 24


class Sim:
    def __init__(self, name: str, decide_every: float):
        self.name = name
        self.decide_every = decide_every        # seconds between decisions
        self.t = 0.0
        self.coins = float(economy.STARTING_COINS)
        self.ceiling = 1
        self.stock: dict[str, float] = {"clay": 1, "water": 1}
        self.item_bucket = {b.id: b.id for b in buckets.ALL}
        self.next_id = 1
        self.earned = 0.0
        self._recipe_cache: dict[int, dict[str, tuple[str, str] | None]] = {}
        self.unlocked_at: dict[int, float] = {1: 0.0}
        self.placements: list[Placement] = [
            self._producer("clay"),
            self._producer("water"),
        ]

    def _producer(self, bucket_id: str, autosell: bool = False) -> Placement:
        p = Placement(
            id=self.next_id, kind="producer", bucket_id=bucket_id,
            item_key=bucket_id, autosell=autosell,
        )
        self.next_id += 1
        return p

    def _factory(self, out: str, a: str, b: str) -> Placement:
        p = Placement(
            id=self.next_id, kind="factory", bucket_id=out,
            inputs=(a, b), output_item=out, autosell=True,
        )
        self.next_id += 1
        return p

    @property
    def slots_free(self) -> int:
        return economy.yard_slots(self.ceiling) - len(self.placements)

    def step(self) -> None:
        result = economy.tick(
            self.placements, self.stock, self.t, self.t + STEP, self.item_bucket
        )
        self.coins += result.coins_earned
        self.earned += result.coins_earned
        self.t += STEP

    @property
    def realised_income_per_hour(self) -> float:
        """Coins actually banked per hour, from autosell *and* manual selling.

        `economy.income_per_hour` only counts autosell placements, so it reads
        zero for a player who sells by hand -- which is every player for the
        first few minutes. Projecting from that gave a 10,000-hour run.
        """
        return self.earned / max(self.t / 3600, 1e-9)

    # Keep enough of each item to feed crafting; sell the rest. Without this the
    # simulated player earns literally nothing, because producers default to
    # autosell off -- which is correct for the game (you need the clay) but means
    # early income comes entirely from choosing to sell surplus.
    RESERVE = 25

    def sell_surplus(self) -> None:
        for item_key, qty in list(self.stock.items()):
            surplus = int(qty) - self.RESERVE
            if surplus <= 0:
                continue
            bucket_id = self.item_bucket.get(item_key)
            if not bucket_id:
                continue
            coins = economy.sale_price(bucket_id, surplus)
            self.coins += coins
            self.earned += coins
            self.stock[item_key] = qty - surplus

    def decide(self) -> None:
        """Sell surplus, then spend on the best thing available.

        Not a clever optimiser -- deliberately. A real player sells what is
        piling up and buys the obvious next upgrade. If the pacing only works
        for a perfect optimiser then the pacing does not work.
        """
        self.sell_surplus()

        # 1. Unlock the next tier the moment it is affordable. It multiplies
        #    everything downstream, so it is always the best purchase.
        cost = economy.unlock_cost(self.ceiling + 1)
        if cost is not None and self.coins >= cost:
            self.coins -= cost
            self.ceiling += 1
            self.unlocked_at[self.ceiling] = self.t
            return

        # 2. Automate the highest-tier recipe the ceiling allows and we can feed.
        for bucket in sorted(buckets.ALL, key=lambda b: -b.tier):
            if bucket.tier > self.ceiling or bucket.tier < 2:
                continue
            recipe = self._recipe_for(bucket)
            if recipe is None:
                continue
            a, b = recipe
            already = any(p.kind == "factory" and p.bucket_id == bucket.id
                          for p in self.placements)
            place_cost = buckets.factory_place_cost(bucket.id)
            if already or self.slots_free <= 0 or self.coins < place_cost:
                continue
            # Only automate something whose inputs are actually being produced,
            # or the factory just sits there stalled.
            if not self._can_feed(a) or not self._can_feed(b):
                continue
            self.coins -= place_cost
            self.placements.append(self._factory(bucket.id, a, b))
            return

        # 3. Otherwise add raw supply.
        for bucket_id, producer in sorted(PRODUCERS.items(), key=lambda kv: kv[1].place_cost):
            if BY_ID[bucket_id].tier > self.ceiling:
                continue
            if self.slots_free <= 0 or self.coins < producer.place_cost:
                continue
            self.coins -= producer.place_cost
            self.placements.append(self._producer(bucket_id))
            return

    def _recipe_for(self, bucket) -> tuple[str, str] | None:
        """Find the cheapest authored pair that makes `bucket`.

        Memoised per ceiling: this is an O(n^2) sweep over the whole table and it
        was being run for every candidate on every decision tick, which is what
        made the first version of this script take minutes instead of seconds.
        """
        cache = self._recipe_cache.setdefault(self.ceiling, {})
        if bucket.id in cache:
            return cache[bucket.id]

        from game.traits import Bucket, combine

        best = None
        for a in buckets.ALL:
            for b in buckets.ALL:
                if a.id > b.id:
                    continue
                out = combine(a, b, self.ceiling, buckets.ALL)
                if isinstance(out, Bucket) and out.id == bucket.id:
                    weight = a.tier + b.tier
                    if best is None or weight < best[0]:
                        best = (weight, a.id, b.id)
        cache[bucket.id] = (best[1], best[2]) if best else None
        return cache[bucket.id]

    def _can_feed(self, item_key: str) -> bool:
        """Is this item produced by something, or already piling up?"""
        if self.stock.get(item_key, 0) > 5:
            return True
        for p in self.placements:
            produced = p.output_item if p.kind == "factory" else (p.item_key or p.bucket_id)
            if produced == item_key and not p.autosell:
                return True
        return False

    def run(self, verbose: bool = False) -> dict[int, float]:
        next_decision = 0.0
        while self.t < MAX_HOURS * 3600:
            self.step()
            if self.t >= next_decision:
                self.decide()
                next_decision = self.t + self.decide_every
            if self.ceiling >= buckets.MAX_AUTHORED_TIER:
                break
            if verbose and int(self.t) % 1800 == 0:
                print(f"    {self.t/3600:5.1f}h  tier {self.ceiling}  "
                      f"{self.coins:>10,.0f} coins  "
                      f"{self.realised_income_per_hour:>9,.0f}/hr  "
                      f"{len(self.placements)}/{economy.yard_slots(self.ceiling)} slots")
        return self.unlocked_at


def project_remaining(income_per_hour: float) -> dict[int, float]:
    """Extrapolate tiers 4-6 from the authored cost curve.

    Assumes income scales with the tier's value ratio each time -- optimistic on
    setup time, pessimistic on how much a player will automate. Good enough to
    tell 8 hours from 80.
    """
    out: dict[int, float] = {}
    income = max(income_per_hour, 1.0)
    for tier in range(buckets.MAX_AUTHORED_TIER + 1, 7):
        cost = buckets.TIER_UNLOCK_COST.get(tier)
        if cost is None:
            continue
        ratio = buckets.TIER_SELL_VALUE[tier - 1] / buckets.TIER_SELL_VALUE[tier - 2]
        income *= ratio
        out[tier] = cost / income
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    print(f"Authored tiers: 1-{buckets.MAX_AUTHORED_TIER}   "
          f"buckets: {len(buckets.ALL)}\n")

    total_hours = {}
    for name, cadence in (("sharp", 20.0), ("casual", 1200.0)):
        print(f"  {name} (decides every {cadence/60:.0f} min)")
        sim = Sim(name, cadence)
        unlocked = sim.run(verbose=args.verbose)

        for tier in sorted(unlocked):
            if tier == 1:
                continue
            print(f"    tier {tier} at {unlocked[tier]/3600:5.2f}h")

        reached = max(unlocked)
        income = sim.realised_income_per_hour
        elapsed = unlocked.get(reached, sim.t) / 3600
        if reached < 6:
            projected = project_remaining(income)
            for tier, hours in projected.items():
                elapsed += hours
                print(f"    tier {tier} at {elapsed:5.2f}h  (projected)")
        total_hours[name] = elapsed
        print(f"    -> full run ~{elapsed:.1f}h   "
              f"(income at tier {reached}: {income:,.0f}/hr)\n")

    low, high = 6.0, 10.0
    casual = total_hours["casual"]
    verdict = "OK" if low <= casual <= high else "OUT OF TARGET"
    print(f"Target 6-10h for a casual run. Casual: {casual:.1f}h  [{verdict}]")
    if verdict != "OK":
        # Unlock cost is the lever: it is the dominant sink, so it moves the run
        # length almost linearly. Raising sell value to *lengthen* a run is
        # backwards -- an earlier version of this message said exactly that.
        direction = "up" if casual < low else "down"
        factor = (low + high) / 2 / casual
        print(f"  Adjust TIER_UNLOCK_COST in game/buckets.py {direction} "
              f"(roughly x{factor:.2f} on tiers 4-6).")
    return 0 if verdict == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
