"""Tests for the naming call and, importantly, its fallback.

The interesting one is `test_the_sdk_accepts_the_request_we_build`. The pinned
SDK was originally `anthropic==0.69.0`, which does not have `output_config` as a
parameter -- so every naming call raised TypeError, was swallowed by the
except-and-fall-back path, and the game quietly stopped inventing names. Nothing
errored, `/health` still said `"ready"`, and the only symptom was that everything
was called "Fired Stock". This test makes that failure loud.
"""

from __future__ import annotations

import inspect

import pytest

from game import naming
from game.buckets import BY_ID
from game.traits import fallback_name


def test_the_sdk_accepts_the_request_we_build():
    """Every parameter `name_discovery` passes must exist on the installed SDK.

    Checked by signature rather than by making a call, so it runs in CI with no
    API key. A missing parameter here means silent permanent fallback.
    """
    anthropic = pytest.importorskip("anthropic")
    signature = inspect.signature(anthropic.Anthropic().messages.create)
    accepted = set(signature.parameters)

    required = {"model", "max_tokens", "system", "thinking", "output_config", "messages"}
    missing = required - accepted
    assert not missing, (
        f"the installed anthropic SDK ({anthropic.__version__}) does not accept "
        f"{sorted(missing)}. Every naming call would raise and silently fall back "
        f"to deterministic names. Raise the pin in requirements.txt."
    )


def test_the_batch_tool_can_build_its_request_types():
    """`tools/build_recipes.py` imports these lazily, so a missing type would
    only surface when you actually ran the (paid) pre-generation."""
    pytest.importorskip("anthropic")
    from anthropic.types.message_create_params import (  # noqa: F401
        MessageCreateParamsNonStreaming,
    )
    from anthropic.types.messages.batch_create_params import Request  # noqa: F401


def test_model_is_the_one_we_chose():
    # A typo here fails at runtime with a 404 and falls back silently, so it is
    # worth asserting rather than trusting.
    assert naming.MODEL == "claude-sonnet-5"


def test_no_key_means_fallback_not_failure(monkeypatch):
    """The whole "deploy first, add the key second" story depends on this."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert naming.configured() is False

    name, emoji, flavor, is_fallback = naming.name_discovery("Clay", "Ember", BY_ID["brick"])
    assert is_fallback is True
    assert name and emoji and flavor
    # Deterministic, so a later real call can replace it exactly once.
    again = naming.name_discovery("Clay", "Ember", BY_ID["brick"])
    assert again[:3] == (name, emoji, flavor)


def test_every_bucket_gets_a_distinct_fallback_name():
    """No two buckets may share a fallback name.

    A keyless game where `mud` and `brick` are both called "Lithic Stock" reads
    as broken, not as graceful degradation. Two earlier attempts at this built
    the name from traits and both collided -- first `mud` with `brick`, then four
    buckets all landing on "Lithic Shell". The trait vocabulary is too small to
    name a three-trait space; the bucket ids already are unique.
    """
    from game.buckets import ALL

    seen: dict[str, list[str]] = {}
    for bucket in ALL:
        name, _ = fallback_name("A", "B", bucket)
        seen.setdefault(name, []).append(bucket.id)
    collisions = {k: v for k, v in seen.items() if len(v) > 1}
    assert not collisions, f"fallback names collide: {collisions}"


def test_fallback_distinguishes_two_items_in_the_same_bucket():
    """`ceramic<clay+steam` and `ceramic<mud+ember` are mechanically the same
    thing but must not both be plain "Ceramic" on the shelf."""
    a, _ = fallback_name("Clay", "Steam", BY_ID["ceramic"])
    b, _ = fallback_name("Mud", "Ember", BY_ID["ceramic"])
    assert a != b
    assert "Ceramic" in a and "Ceramic" in b


def test_fallback_is_stable_across_processes():
    """Python salts str.__hash__ per process, so a name derived from hash()
    would change on every restart -- and an item already in the database would
    suddenly be called something else."""
    import subprocess
    import sys

    code = (
        "from game.traits import fallback_name;"
        "from game.buckets import BY_ID;"
        "print(fallback_name('Clay', 'Ember', BY_ID['brick'])[0])"
    )
    runs = {
        subprocess.run([sys.executable, "-c", code], capture_output=True,
                       text=True, check=True).stdout.strip()
        for _ in range(2)
    }
    assert len(runs) == 1, f"fallback name varies between processes: {runs}"


@pytest.mark.parametrize(
    "raw,expected",
    [
        ('"Pit Kiln"', "Pit Kiln"),
        ("  Fired   Brick  ", "Fired Brick"),
        ("Bloomery Slag.", "Bloomery Slag"),
        ("A Very Long Name That Keeps Going Forever", "A Very Long Name"),
        ("", "Unnamed Thing"),
    ],
)
def test_clean_name(raw, expected):
    assert naming.clean_name(raw) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("\U0001f9f1", "\U0001f9f1"),
        ("\U0001f9f1\U0001f525", "\U0001f9f1"),          # only the first glyph
        ("\U0001f9f1 a brick", "\U0001f9f1"),
        ("  \U0001f4a7  ", "\U0001f4a7"),
        ("", ""),
    ],
)
def test_clean_emoji_keeps_one_glyph(raw, expected):
    assert naming.clean_emoji(raw) == expected


def test_clean_flavor_is_bounded():
    long = "word " * 100
    out = naming.clean_flavor(long)
    assert len(out) <= 100
    assert "  " not in out


def test_prompt_mentions_the_result_properties():
    """The model is told what the thing *is*; it only chooses the label. If the
    traits stopped reaching the prompt, names would drift off the mechanics."""
    prompt = naming.build_prompt("Clay", "Ember", BY_ID["brick"])
    assert "Clay" in prompt and "Ember" in prompt
    assert "mineral" in prompt and "heavy" in prompt
    assert "material" in prompt
    assert "Result tier: 2 of 6" in prompt
