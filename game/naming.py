"""Names a discovery. The only place a language model is involved.

The critical property: **this call cannot break the game.** By the time it runs,
the result's kind, traits and tier are already decided by `traits.combine()`,
the coins are already accounted for, and the item already exists. All that is
missing is a label. If the API is slow, erroring, or unconfigured, we write a
deterministic fallback name and the player never blocks.

That is the inverse of v1, where the model decided all eighteen economic stats
*and* the item's identity -- so a bad generation broke progression permanently
and globally.

Cost, for the record: ~600 input tokens and ~60 output on `claude-sonnet-5`, so
about $0.003 per never-before-seen combination and roughly a second. v1 spent
~$0.015 and 30-60s on two sequential calls, one of which rendered a
1024x1024 image that the crafting UI never displayed. Already-named
combinations cost nothing at all -- they are a dict lookup.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Optional, Tuple

from .traits import TRAIT_ORDER, Bucket, fallback_name

log = logging.getLogger("tycooncraft.naming")

MODEL = "claude-sonnet-5"

# The response is ~60 tokens, but adaptive thinking shares this budget, so it
# needs headroom -- max_tokens caps thinking plus text together. We are only
# billed for what is generated, so a generous ceiling costs nothing and avoids
# a truncated name.
MAX_TOKENS = 2000

# Shorter than gunicorn's 60s worker timeout, so a slow API turns into a
# fallback name rather than a killed worker.
TIMEOUT_SECS = 20.0

SYSTEM = """\
You name items in a crafting game. The player has combined two things and the \
game has already decided what came out — its category, its properties and its \
tier. Your only job is to put a name on it.

Reply with a name, one emoji, and one line of flavour text.

Rules for the name:
- One to three words. Title Case.
- It must fit the properties you are given. A "hot mineral" thing should sound \
fired, kilned, or smelted.
- Do not glue the two input names together. "Clay Ember" and "Fired Brick \
Water" are the failure mode. Name the *result*, as a thing in its own right.
- Prefer the concrete and physical over the abstract and grand. "Pit Kiln" and \
"Bloomery Slag" beat "Essence of Flame".
- Real words for real things where one exists. Invent only when nothing fits.
- Higher tiers may sound more refined and deliberate; tier 1 and 2 should sound \
like raw stuff you found or roughly made.

Flavour text: under eighty characters, one sentence, no final period. Dry \
rather than whimsical. It may hint at what the thing is good for.

The emoji should read at small size. Prefer one obvious glyph over a clever one.\
"""

SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "emoji": {"type": "string"},
        "flavor": {"type": "string"},
    },
    "required": ["name", "emoji", "flavor"],
    "additionalProperties": False,
}

_client = None
_client_failed = False


def configured() -> bool:
    """Whether a key is present. Surfaced on /health so a misconfigured droplet
    is visible without having to craft something and squint at the name."""
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def _get_client():
    """Lazy singleton. Building the client at import time would make the whole
    app fail to boot without a key, and running keyless is a supported state."""
    global _client, _client_failed
    if _client is not None or _client_failed:
        return _client
    try:
        import anthropic

        _client = anthropic.Anthropic(timeout=TIMEOUT_SECS, max_retries=1)
    except Exception:
        log.exception("could not construct the Anthropic client; using fallback names")
        _client_failed = True
    return _client


def build_prompt(a_name: str, b_name: str, bucket: Bucket) -> str:
    traits = ", ".join(t for t in TRAIT_ORDER if t in bucket.traits)
    return (
        f"Inputs: {a_name} + {b_name}\n"
        f"Result category: {bucket.kind}\n"
        f"Result properties: {traits}\n"
        f"Result tier: {bucket.tier} of 6\n\n"
        f"Name this result."
    )


def clean_name(raw: str) -> str:
    """Trim the model's name to something that fits on a card.

    Not validation -- structured output already guarantees a string. This is
    presentation: strip quotes it sometimes wraps things in, collapse
    whitespace, and cap at four words so a long answer cannot break the layout.
    """
    text = re.sub(r'^["\'\s]+|["\'\s.]+$', "", raw)
    text = re.sub(r"\s+", " ", text)
    words = text.split(" ")[:4]
    return " ".join(words) or "Unnamed Thing"


def clean_emoji(raw: str) -> str:
    """Keep the first glyph. Models occasionally return two, or an emoji plus a
    word; either would wreck the card grid."""
    stripped = raw.strip()
    if not stripped:
        return ""
    # Take the first grapheme-ish run: a base codepoint plus any joiners,
    # variation selectors and skin-tone modifiers that belong to it.
    out = [stripped[0]]
    for ch in stripped[1:]:
        if ch in "‍️" or "\U0001f3fb" <= ch <= "\U0001f3ff" or out[-1] == "‍":
            out.append(ch)
        else:
            break
    return "".join(out)


def clean_flavor(raw: str) -> str:
    text = re.sub(r"\s+", " ", raw).strip().rstrip(".")
    return text[:100]


def name_discovery(
    a_name: str,
    b_name: str,
    bucket: Bucket,
) -> Tuple[str, str, str, bool]:
    """Return (name, emoji, flavor, is_fallback).

    Never raises. `is_fallback` is recorded on the item so a later run can
    upgrade it once a key is configured, which is what makes "deploy first,
    add the key second" safe.
    """
    client = _get_client() if configured() else None
    if client is None:
        name, emoji = fallback_name(a_name, b_name, bucket)
        return name, emoji, bucket.describe(), True

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM,
            # Adaptive at low effort rather than disabled: for Sonnet 5 that is
            # the recommended shape for short, scoped, latency-sensitive work,
            # and disabling thinking outright has its own failure modes.
            thinking={"type": "adaptive"},
            output_config={
                "effort": "low",
                "format": {"type": "json_schema", "schema": SCHEMA},
            },
            messages=[{"role": "user", "content": build_prompt(a_name, b_name, bucket)}],
        )
    except Exception:
        log.exception("naming call failed for %s + %s", a_name, b_name)
        name, emoji = fallback_name(a_name, b_name, bucket)
        return name, emoji, bucket.describe(), True

    # Safety classifiers can decline with HTTP 200 and stop_reason "refusal",
    # in which case `content` is empty or partial -- so check before indexing.
    if getattr(response, "stop_reason", None) == "refusal":
        log.warning("naming call refused for %s + %s", a_name, b_name)
        name, emoji = fallback_name(a_name, b_name, bucket)
        return name, emoji, bucket.describe(), True

    try:
        import json

        text = next(b.text for b in response.content if b.type == "text")
        payload = json.loads(text)
        name = clean_name(payload["name"])
        emoji = clean_emoji(payload["emoji"]) or fallback_name(a_name, b_name, bucket)[1]
        flavor = clean_flavor(payload["flavor"])
    except Exception:
        log.exception("could not read the naming response for %s + %s", a_name, b_name)
        name, emoji = fallback_name(a_name, b_name, bucket)
        return name, emoji, bucket.describe(), True

    return name, emoji, flavor, False
