# TycoonCraft

Rub two things together and see what falls out. Then build the factories that
make them, sell the output, and buy your way up six tiers of industry.

Live at **<https://collabcanvas.org/tycooncraft/>**.

A [collabcanvas microapp](https://github.com/amerixans/collab-canvas/blob/main/docs/MICROAPP_GUIDE.md):
one container, SQLite in a volume, one loopback port, mounted under
`/tycooncraft/`. No build step — the frontend is ES modules served as-is.

> **This is a rewrite.** The first version was Django + DRF + Postgres + Create
> React App, and it did not work. `docs/WHAT-WENT-WRONG.md` is the autopsy; it is
> worth reading before changing the crafting rules, because most of the design
> here exists to avoid a specific thing that broke.

---

## The loop

```
place producers ──▶ they make raw items ──▶ combine two items (costs coins)
      ▲                                              │
      │                                              ▼
      │                                    discover a new item type
      │                                              │
      │                                              ▼
      └──── coins ◀── sell output ◀── automate that recipe in a factory
                          │
                          ▼
                 buy the next TIER ──▶ every recipe now reaches higher
```

You land with a Clay Pit and a Well already running and one of each in stock, so
the first thing available is a *craft*, not a wait.

## Why combining does not spiral

The problem this design exists to solve: if a craft is "two nouns in, a
model-invented noun out", results only ever get *more specific*. Nothing pulls
back toward generality, so you end up with Smoke Stack, then Double Smoke Stack,
then Reinforced Composite Smoke Stack Mk III, and no idea which of your eighty
items is any good.

So the model does not decide anything mechanical. An item's mechanical identity
is a **bucket**: a `(kind, traits, tier)` triple where `kind` is one of 8,
`traits` are one to three of a closed set of 16, and every bucket that exists is
hand-authored in [`game/buckets.py`](game/buckets.py). Combining is a pure
function over buckets ([`game/traits.py`](game/traits.py)). The model is called
afterwards, and only to put a name on something whose properties are already
fixed.

Four things follow, and they are the whole design:

| | |
| --- | --- |
| **Duds are free** | If the resolved bucket is one of the inputs, nothing happens — no coins, no API call, no row. Smoke Stack + Smoke Stack cannot become Double Smoke Stack, because no authored bucket takes `{hot, structure}` twice and returns something new. |
| **Recipes match traits, not names** | A factory wants "any *hot mineral*", so Glass and Fired Brick are interchangeable. You can never be blocked waiting for one specific noun. |
| **Names stay unbounded** | The name is a function of the input *pair*, so Clay + Ember and Sand + Ember are the same bucket with different personalities. Bounded mechanics, unbounded flavour. |
| **The model cannot break the game** | With no API key at all, items get deterministic names from their traits and everything else works. `/health` says `{"llm": "unconfigured"}`. |

### Tiers gate the ceiling, not your ability to craft

A craft can only reach as high as your unlocked tier. At ceiling 3, two tier-3s
combine into a *lateral* tier-3. Buy tier 4 and the same combination now yields
tier 4 — so every old pairing is worth retrying after an unlock.

And once you have filled the buckets reachable at your ceiling, everything starts
coming back as duds. That is the game telling you to go buy the next tier: the
dud mechanic doubles as the pacing signal.

### Nothing goes obsolete

Every tier-N chain consumes tier-1 stock somewhere at the bottom. Clay is not
something you outgrow, it is infrastructure — your first Clay Pit is still
earning in hour ten.

---

## Running it

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt pytest

python app.py                          # http://127.0.0.1:8080/
BASE_PATH=/tycooncraft python app.py   # http://127.0.0.1:8080/tycooncraft/
```

**Run it both ways before pushing.** Serving fine at `/` and 404ing every asset
at `/tycooncraft/` is the failure this kind of app is most prone to, and CI
checks exactly that — including walking the real ES module graph, because a
hardcoded list of URLs to curl passes happily while the app is broken.

Or with Docker, the way the droplet runs it:

```bash
cp .env.example .env
docker compose up -d --build
```

## Sound

Web Audio only — no files, nothing to download. `public/src/audio.js`.

The music is **generative rather than a loop**, for a specific reason: this is an
idle game, so the tab stays open for hours, and a loop that is pleasant for three
minutes is unbearable for two hours — you start hearing the seam. So it is a slow
pad over a four-chord walk with a sparse bell line on top, and none of it is
quantised tightly enough to form a hook.

**The pad's chord widens as you unlock tiers.** Tier 1 is a bare open fifth:
industrial, unresolved, slightly bleak. By tier 6 it is a major ninth. The music
brightens as you get richer, which is the arc of the whole game expressed in the
one channel that costs no screen space.

Discovery borrows Poggle's trick outright, because it works: each consecutive find
steps up a major pentatonic, so a run plays a rising phrase, and from the third a
quiet fifth joins on top. Pentatonic because every interval in it is consonant, so
a lucky eight-discovery streak cannot land on a sour note. A dud breaks the run.

There's a ♪ button in the top bar and the choice is remembered in `localStorage`.

## Tests

```bash
pytest -m "not live"        # traits, buckets, economy, balance, naming, API
pytest -s -k resolution     # prints what every combination resolves to
node tests/audio.test.mjs   # drives audio.js under a stubbed AudioContext
```

`tests/test_traits.py::test_resolution_table` is the one to read after editing
the bucket table. A too-loose `needs` **shadows** a sibling rather than
erroring, and that report is what surfaces it.

`tests/test_balance.py` is a ratchet on the pacing: it fails if a casual run
stops landing in 6–10 hours. Tune with `tools/simulate.py`.

## The tools

| | |
| --- | --- |
| `tools/simulate.py` | Plays the game at ~4000x speed and reports time-to-each-tier for a sharp and a casual player. The tuning instrument for `TIER_UNLOCK_COST`. |
| `tools/build_recipes.py` | Pre-generates every item name offline via the Batch API at half price into `content/recipes.json`. **102 names for about $0.14**, after which tiers 1–3 need no API calls at all. `--dry-run` to see the plan. |
| `tools/build_tile.py` | Draws `public/tile.gif` — 600×300, 48 frames, ~100 KB. Stays small by keeping the background bit-identical between frames and sharing one palette; see the comments. |

## Where things live

```
app.py                 routes, BASE_PATH stripping, /health
game/traits.py         the vocabularies and the combine function — pure, no I/O
game/buckets.py        the authored content: every item, and what makes it
game/economy.py        production, offline accrual, selling — pure, no I/O
game/naming.py         the one model call, plus its fallback
game/store.py          SQLite; one connection behind one lock
content/recipes.json   pre-generated names, baked into the image
public/index.html      one page, relative URLs only
public/src/main.js     state, polling, the three columns
public/src/bench.js    the drag-one-thing-onto-another surface
public/src/audio.js    generative music and SFX, Web Audio only
public/src/fx.js       particles, toasts, floating numbers, shake
```

`traits.py`, `buckets.py` and `economy.py` have no I/O on purpose — that is what
lets the balance simulator play a full run in under a second.

## Two things worth knowing before you change anything

**The item key format is load-bearing.** `mud<clay+water` encodes the result
bucket and its two input buckets, sorted. That is what keeps the name space
bounded (a few hundred names covers the whole game, so the pack can hold all of
them) and what lets a factory work out its own inputs. `store.item_key_for` and
`tools/build_recipes.py:item_key_for` must agree exactly.

**A missing API key is a supported state, not an outage.** Deploy first, add the
key second. Items named while keyless are marked `is_fallback` and get upgraded
the next time somebody makes them.

## Deploying

See [`docs/DEPLOY.md`](docs/DEPLOY.md). Short version: push to `main`.
