"""Guard the one CSS invariant the game's readability depends on.

Tier is the single most useful thing a card can tell you at a glance -- it is
what sale value, craft cost and "is this worth automating" all key off -- and it
is communicated by one thing only: a 3px coloured stripe down the left edge.

That stripe is a `border-left`, which means any *later* rule for the same element
that uses the `border-color` or `border` shorthand silently erases it. That is
not hypothetical. `.item.ready` did exactly this, and because nearly every item
in a healthy game is affordable, nearly every shelf card was painted gold and the
six-colour ramp was invisible. Nothing errored; the app just quietly stopped
communicating its most important number.

A visual review catches that once. This catches it forever.
"""

from __future__ import annotations

import re
from pathlib import Path

CSS = Path(__file__).resolve().parent.parent / "public" / "src" / "style.css"

# `selector { declarations }`. Declarations may not contain braces, so an @media
# wrapper never matches as a rule of its own while the rules nested inside it do
# -- which is what we want, since those are the ones that can clobber a border.
RULE = re.compile(r"([^{}]+)\{([^{}]*)\}")

# The shorthands that reset all four sides. `border-left-color` and the
# per-side longhands are fine, which is the whole point.
SHORTHAND = re.compile(r"(?:^|;)\s*border(?:-color)?\s*:", re.MULTILINE)


def _rules(text: str) -> list[tuple[str, str]]:
    stripped = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    return [(m.group(1).strip(), m.group(2)) for m in RULE.finditer(stripped)]


def test_the_tier_stripe_is_never_overwritten() -> None:
    rules = _rules(CSS.read_text(encoding="utf-8"))

    # Which base selectors carry a tier stripe, and where they are declared.
    striped: dict[str, int] = {}
    for i, (selector, body) in enumerate(rules):
        if "--tier-color" in body and "border-left" in body:
            for one in selector.split(","):
                # ".item" out of ".item", ".bench-item" out of ".bench-item".
                base = re.match(r"\.[\w-]+", one.strip())
                if base:
                    striped.setdefault(base.group(0), i)

    assert striped, (
        "no rule declares a tier stripe -- either style.css moved the tier signal "
        "somewhere else (update this test) or the stripe was lost entirely"
    )

    offenders = []
    for base, declared_at in striped.items():
        for i, (selector, body) in enumerate(rules[declared_at + 1 :], declared_at + 1):
            for one in selector.split(","):
                one = one.strip()
                # Only rules targeting the striped element ITSELF -- a state or
                # pseudo-class on it. A descendant (".item .chip") is a different
                # element and cannot affect the parent's border.
                if not re.match(rf"{re.escape(base)}(?:[.:\[]|$)", one):
                    continue
                if SHORTHAND.search(body):
                    offenders.append(f"{one} (rule {i}) resets the {base} tier stripe")

    assert not offenders, (
        "these rules use a border/border-color shorthand on an element whose left "
        "edge carries its tier colour, which erases it. Set the three other sides "
        "by name instead (border-top-color / -right-color / -bottom-color):\n  "
        + "\n  ".join(offenders)
    )


def test_the_ramp_is_six_distinct_colours() -> None:
    """--t1..--t6 must all exist and differ. fx.js reads these at runtime rather
    than keeping its own copy, so a missing one degrades to grey silently."""
    text = CSS.read_text(encoding="utf-8")
    ramp = {}
    for tier in range(1, 7):
        m = re.search(rf"--t{tier}:\s*([^;]+);", text)
        assert m, f"--t{tier} is not defined; fx.js tierColor({tier}) would fall back to grey"
        ramp[tier] = m.group(1).strip().lower()

    assert len(set(ramp.values())) == 6, f"two tiers share a colour: {ramp}"
