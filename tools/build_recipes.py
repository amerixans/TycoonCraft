#!/usr/bin/env python3
"""Pre-generate every item name, offline, at half price.

    python3 tools/build_recipes.py --dry-run     # plan only, no API calls
    ANTHROPIC_API_KEY=sk-ant-... python3 tools/build_recipes.py

This is the real answer to the loudest complaint about the first version of the
game: *"if you are one of the first players you just wait a while for stuff to
generate."* Every combination reachable in the authored tiers is named here,
ahead of time, and baked into `content/recipes.json`. After a full run the game
makes **no API calls at all** for tiers 1-3 -- a discovery is a dict lookup, so
the first player has exactly the same instant experience as the hundredth.

Two reasons this is a separate offline tool rather than a warm-up on boot:

* **The Batch API is half price.** These requests are not latency-sensitive, so
  paying interactive rates for them would be waste.
* **It runs on your Mac, not the droplet.** The droplet never needs a key to
  serve a fully-packed game, which keeps the deployment simpler and the key in
  one fewer place.

Names are generated tier by tier, because a tier-3 prompt needs the *names* of
its tier-2 inputs -- and those are decided by the tier-2 pass. Going out of order
would mean naming things from bucket ids ("mud", "brick") instead of from the
names players will actually see.
"""

from __future__ import annotations

import argparse
import itertools
import json
import os
import sys
import time
from typing import Dict, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game import buckets, naming                            # noqa: E402
from game.buckets import ALL, BY_ID, STARTERS               # noqa: E402
from game.traits import Bucket, combine                     # noqa: E402

PACK = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "content", "recipes.json"
)

# Matches store.STARTER_ITEMS. Duplicated deliberately: importing store here
# would open a database, and this tool has no business doing that.
STARTER_NAMES = {
    "clay": "Clay",
    "water": "Water",
    "seed": "Seed",
    "ember": "Ember",
}

POLL_SECS = 20
MAX_WAIT_SECS = 60 * 60


def item_key_for(bucket_id: str, a: str, b: str) -> str:
    """Must match store.item_key_for exactly, or the pack will not be found."""
    lo, hi = sorted((a, b))
    return f"{bucket_id}<{lo}+{hi}"


def plan() -> Dict[int, list[Tuple[str, str, str]]]:
    """Every (result, input_a, input_b) triple, grouped by result tier.

    Enumerated from the authored tree rather than from anything a player has
    done, so the pack covers the whole reachable space up front.
    """
    ceiling = buckets.MAX_AUTHORED_TIER
    by_tier: Dict[int, list[Tuple[str, str, str]]] = {}
    seen: set[str] = set()

    for a, b in itertools.combinations_with_replacement(ALL, 2):
        result = combine(a, b, ceiling, ALL)
        if not isinstance(result, Bucket):
            continue                                    # a dud needs no name
        key = item_key_for(result.id, a.id, b.id)
        if key in seen:
            continue
        seen.add(key)
        lo, hi = sorted((a.id, b.id))
        by_tier.setdefault(result.tier, []).append((result.id, lo, hi))

    for triples in by_tier.values():
        triples.sort()
    return by_tier


def canonical_names(pack: dict, by_tier: Dict[int, list], upto_tier: int) -> Dict[str, str]:
    """One representative display name per bucket, for use in prompts.

    Several item keys can share a bucket (Fired Brick and Glass are both tier-2
    hot minerals). For prompting purposes any of them will do; picking the
    lowest key keeps it deterministic so re-running the tool is reproducible.
    """
    names = dict(STARTER_NAMES)
    for tier in range(2, upto_tier + 1):
        for result_id, a, b in by_tier.get(tier, []):
            key = item_key_for(result_id, a, b)
            entry = pack["names"].get(key)
            if entry and result_id not in names:
                names[result_id] = entry["name"]
    return names


def build_requests(triples: list, names: Dict[str, str]) -> list:
    from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
    from anthropic.types.messages.batch_create_params import Request

    requests = []
    for result_id, a, b in triples:
        bucket = BY_ID[result_id]
        a_name, b_name = names.get(a), names.get(b)
        if not a_name or not b_name:
            # An input bucket we have not named yet. Should not happen when
            # walking tiers in order; skip rather than prompt with a bucket id.
            print(f"    skipping {result_id}<{a}+{b}: no name yet for "
                  f"{a if not a_name else b}")
            continue
        requests.append(
            Request(
                custom_id=item_key_for(result_id, a, b).replace("<", "__").replace("+", "_"),
                params=MessageCreateParamsNonStreaming(
                    model=naming.MODEL,
                    max_tokens=naming.MAX_TOKENS,
                    system=naming.SYSTEM,
                    thinking={"type": "adaptive"},
                    output_config={
                        "effort": "low",
                        "format": {"type": "json_schema", "schema": naming.SCHEMA},
                    },
                    messages=[{
                        "role": "user",
                        "content": naming.build_prompt(a_name, b_name, bucket),
                    }],
                ),
            )
        )
    return requests


def decode(custom_id: str) -> str:
    """Undo the custom_id mangling. Batch ids allow a limited character set."""
    bucket, _, rest = custom_id.partition("__")
    a, _, b = rest.partition("_")
    return f"{bucket}<{a}+{b}"


def run_batch(client, requests: list) -> Dict[str, dict]:
    batch = client.messages.batches.create(requests=requests)
    print(f"    batch {batch.id} submitted with {len(requests)} requests")

    waited = 0
    while True:
        batch = client.messages.batches.retrieve(batch.id)
        if batch.processing_status == "ended":
            break
        if waited >= MAX_WAIT_SECS:
            raise SystemExit(f"batch {batch.id} still running after {waited}s; "
                             f"re-run later and it will resume from the pack")
        counts = batch.request_counts
        print(f"    {batch.processing_status}: {counts.succeeded} done, "
              f"{counts.processing} processing, {counts.errored} errored")
        time.sleep(POLL_SECS)
        waited += POLL_SECS

    out: Dict[str, dict] = {}
    errors = 0
    for result in client.messages.batches.results(batch.id):
        if result.result.type != "succeeded":
            errors += 1
            continue
        message = result.result.message
        # Safety classifiers can decline with a 200 and an empty content list.
        if message.stop_reason == "refusal":
            errors += 1
            continue
        try:
            text = next(b.text for b in message.content if b.type == "text")
            payload = json.loads(text)
            out[decode(result.custom_id)] = {
                "name": naming.clean_name(payload["name"]),
                "emoji": naming.clean_emoji(payload["emoji"]),
                "flavor": naming.clean_flavor(payload["flavor"]),
            }
        except Exception:
            errors += 1

    print(f"    {len(out)} named, {errors} failed "
          f"(failures fall back at runtime, so this is not fatal)")
    return out


def load_pack() -> dict:
    try:
        with open(PACK, "r", encoding="utf-8") as handle:
            pack = json.load(handle)
            pack.setdefault("names", {})
            return pack
    except (OSError, ValueError):
        return {"generated": None, "model": naming.MODEL, "names": {}}


def save_pack(pack: dict) -> None:
    pack["model"] = naming.MODEL
    pack["generated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with open(PACK, "w", encoding="utf-8") as handle:
        json.dump(pack, handle, indent=1, ensure_ascii=False, sort_keys=True)
        handle.write("\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="show the plan and the cost estimate, call nothing")
    parser.add_argument("--force", action="store_true",
                        help="re-name combinations already in the pack")
    args = parser.parse_args()

    by_tier = plan()
    total = sum(len(v) for v in by_tier.values())
    pack = load_pack()
    have = len(pack["names"])

    print(f"Authored tiers 1-{buckets.MAX_AUTHORED_TIER}, {len(ALL)} buckets")
    for tier in sorted(by_tier):
        print(f"  tier {tier}: {len(by_tier[tier])} named combinations")
    print(f"  total: {total}   already in the pack: {have}\n")

    # ~600 in / ~60 out per request on Sonnet 5 ($3/$15 per MTok), halved by the
    # Batch API. Printed rather than assumed so the number is auditable.
    per_request = (600 / 1e6) * 3.0 + (60 / 1e6) * 15.0
    todo = total if args.force else max(0, total - have)
    print(f"Estimated cost: {todo} x ${per_request:.5f} / 2 (batch discount) "
          f"= ${todo * per_request / 2:.2f}\n")

    if args.dry_run:
        print("Dry run. Nothing called, nothing written.")
        return 0

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY is not set.\n"
              "  The game runs without it -- items get deterministic fallback\n"
              "  names -- but this tool needs it. Get one at console.anthropic.com.")
        return 1

    import anthropic

    client = anthropic.Anthropic()

    for tier in sorted(by_tier):
        triples = by_tier[tier]
        if not args.force:
            triples = [t for t in triples
                       if item_key_for(t[0], t[1], t[2]) not in pack["names"]]
        if not triples:
            print(f"  tier {tier}: already complete")
            continue

        print(f"  tier {tier}: naming {len(triples)}")
        # Names must exist for the inputs, which live one tier down -- hence
        # walking tiers in order rather than submitting one giant batch.
        names = canonical_names(pack, by_tier, tier - 1)
        requests = build_requests(triples, names)
        if not requests:
            continue
        pack["names"].update(run_batch(client, requests))
        # Written after every tier so an interrupted run keeps its progress and
        # a re-run picks up where it stopped.
        save_pack(pack)

    save_pack(pack)
    print(f"\nWrote {PACK} with {len(pack['names'])} names.")
    print("Rebuild the image so it is baked in: docker compose up -d --build")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
