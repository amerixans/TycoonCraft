# What went wrong the first time

An autopsy of TycoonCraft v1 (Django + DRF + Postgres + Create React App, last
pushed 2025-10-20), kept in the repo because most of v2's design exists to avoid
a specific thing listed here. If you are about to change the crafting rules, the
economy, or the deploy, read the relevant section first.

Ordered worst-first. Line references are to v1, recoverable from git history.

---

## A. Progression was hard-broken

### A1. The keystone chain never enforced its own output

In every `backend/eras/*.yaml`, `is_keystone: true` and `output_name:` sat as
*siblings* of `overrides:`:

```yaml
- comment: "HG-3 (Keystone)"
  input_a: "Fire"
  input_b: "Rock"
  output_name: "Hearth"      # <- never read
  is_keystone: true          # <- never read
  overrides:                 # <- only this was applied
    era_name: "Hunter-Gatherer"
    cost: 10000
```

`views.py:413` returned only `recipe.get("overrides", {})`. So neither the
required name nor the keystone flag was ever applied, and progression depended on
the model spontaneously naming Fire + Rock exactly `"Hearth"`.

Meanwhile `prompts/crafting_recipe.txt:138` forbade reusing input stems, and
line 147 gave **"Stone + Fire → Pit Kiln ✓"** as the *correct* answer. The prompt
was actively steering away from the game's only progression mechanic.

And `CraftingRecipe` had `unique_together = [object_a, object_b]` with no player
scope, so the recipe table was global: **the first player in the world to miss
the name locked that era's gate for everyone, permanently.**

> **v2:** mechanics are resolved server-side before the model is called. The model
> only names things whose properties are already fixed, so it cannot break
> progression. See `game/traits.py`.

### A2. There was no second way out of tier 1

`01_hunter_gatherer.yaml` set `time_crystal_generation: {min: 0, max: 0}`, so you
could not earn a single crystal in Hunter-Gatherer — and Agriculture cost 10.
Both the keystone path and the purchase path were closed.

> **v2:** one currency. Tier unlock is a coin purchase you can always work toward.

### A3. Eight of ten unlock hints named items no recipe could produce

| Era | `unlock_message` said | Chain actually ended at |
| --- | --- | --- |
| Metallurgy | Blast Furnace | Boiler |
| Steam & Industry | Telegraph | Dynamo |
| Electric Age | Analytical Engine | Transistor |
| Computing | Quantum Computer | Lithography |
| Futurism | Warp Drive | Fusion Core |
| Interstellar | Spell Codex | Aether Array |
| Arcana | Reality Stone | Reality Loom |

The UI told you to craft something that did not exist.

> **v2:** `tests/test_traits.py::test_all_buckets_reachable` fails if any authored
> content is unreachable.

### A4. A name collision hard-blocked tier 5 → 6

Era 5's chain output was `"Transistor"`, which `initialize_starter_objects` had
*already* seeded as an era-6 **starter** with `is_keystone=False`.
`GameObject.object_name` was unique, so `views.py:945` took the existing-object
branch and linked the recipe to the era-6 starter. Computing was unreachable by
keystone.

> **v2:** identity is a `(kind, traits, tier)` bucket id, not a globally-unique
> display name. Starters are `craftable=False` and a test asserts no craft can
> ever produce one.

### A5. Same-era-only crafting

`views.py:870` rejected any cross-era pair, so most pairs in your inventory were
illegal. This is the direct cause of "it was all too easy to get stuck or not be
able to make things at all."

> **v2:** any two items may always be combined. The tier ceiling limits how *high*
> a result can reach, never whether the craft happens.

### A6. One player's craft could delete another player's buildings

When `validate_predefined_match` failed, `views.py:904` called
`result_obj.delete()` on the **shared** `GameObject`. `Discovery.game_object` and
`PlacedObject.game_object` were both `on_delete=CASCADE`, so this silently wiped
every player's discovery and every placed building of that type, plus every
recipe using it as an input. It triggered whenever a stored object's cost or era
drifted from the YAML — i.e. any time you retuned a number.

> **v2:** the item registry is append-only. Nothing is ever hard-deleted.

---

## B. The redundancy spiral

This was the biggest complaint, and it was a property of the mechanic rather than
of the prompt.

A craft was `f(A, B) → a noun invented by a model`. The noun space is unbounded
and the cheapest move available is conjunction ("Double Smoke Stack") or
modification ("Reinforced X Mk II"). Nothing ever pulled back toward generality,
so specificity increased monotonically. The prompt already had five separate
anti-concatenation rules and it happened anyway.

Two aggravating factors: near-duplicate names became distinct rows ("Smoke stack"
and "Smokestack" were different `object_name` values), and nothing ever signalled
which of your eighty items was good.

> **v2:** see the README's "Why combining does not spiral". Mechanics live in a
> closed vocabulary; the dud check makes a degenerate combination free and
> instant; recipes match traits rather than names.

---

## C. Latency and cost

Two blocking sequential API calls inside one HTTP request: `gpt-5-mini` with
`reasoning: {effort: "medium"}` on a ~4,000-token prompt (`views.py:562`), then
`gpt-image-1-mini` at 1024×1024 `quality: medium` (`views.py:659`). Client
timeouts were 60s and 120s, so a gunicorn worker would 504 before the client saw
anything. About **$0.015 and 30–60 seconds per discovery**, with no pre-seeding,
no queue, and no optimistic UI.

> **v2:** one ~600-in/~60-out call (~$0.003, ~1s), duds resolve with no call at
> all, and `tools/build_recipes.py` pre-names the entire authored game for ~$0.14
> so tiers 1–3 need no runtime calls whatsoever.

---

## D. The economy could not work

| | |
| --- | --- |
| All four tier-1 starters had `income_per_second: 0` | They were inert. |
| Hearth cost **10,000** to place | Tier-1 income capped at 10/s. Era 4's keystone cost **900,000,000**; era 9's cost **1.15 quintillion**. |
| **Offline earnings were silently lost** | `update_player_coins` (`views.py:258`) skipped any object whose `retire_at` had passed, so being away a day credited **zero** instead of the hour the building actually ran. |
| Buildings deleted themselves | `operation_duration_sec` retired everything you placed. |
| One DB write per second per client | `App.js:409` polled every `1000ms` (the README claimed 5s), and every call ran `update_player_coins` → `player.save()` plus a full re-serialisation of all discoveries and placements. |
| Free money, twice | `/api/add-coin/` (`views.py:1390`, routed) let any logged-in user mint coins. `import_game` trusted client-supplied `coins` up to 10¹⁸ — export, edit the JSON, import. |

> **v2:** `game/economy.py` is pure and directly tested;
> `test_offline_accrual_is_not_lost` is the regression test for the third row.
> Nothing expires. Polling is 3s with client-side interpolation. There is no
> coin-minting endpoint and no import.

---

## E. The starting items

- Tier-1 starters were inert and cost 10 coins each.
- "Cat" was an Agriculture starter.
- Later tiers handed you *finished buildings*, not ingredients — "Orbital
  Telescope", "Quantum Lab", "Satellite Bus", "Radiation Shielding", "Archive
  Mirror", "Convergence Anchor", "Manifold Bridge". There is no intuition for
  combining two of those.
- The era ordering was incoherent: Interstellar → **Arcana** → Beyond.

> **v2:** four raw, obviously-combinable starters — Clay `{mineral}`, Water
> `{wet}`, Seed `{grown, alive}`, Ember `{hot}` — and a test asserting all six
> pairs react and give six different results.

---

## F. Aesthetics and feel

- **`prompts/image_prompt.txt` was two complete, contradictory prompts
  concatenated**, with a literal `Object to create: [ ]` artifact and a stray
  `#gpt` marker between them — and `{{object_final_name}}` only substituted into
  the *second* half. That is why the art was inconsistent.
- **The crafting UI never showed the art.** `CraftingArea.js:92` and `:112`
  rendered `object_name` as text in both slots, so the sprite you paid $0.01 for
  was not on screen while you crafted.
- Two slots and a "Craft Now!" button is a form, not a toy.
- **Zero audio.** No `Audio`, no Web Audio, no sound files anywhere.
- 31 `@keyframes` total across all CSS, mostly modal fades.

> **v2:** emoji (instant, free, and what the genre actually uses), an open bench
> you drag one thing onto another on, particles, and a reveal moment. Generative
> music and the full juice pass are phase 2.

---

## G. It could not deploy to collabcanvas

- **Far over budget.** The droplet is one shared `s-1vcpu-1gb` (961 MB, ~200 MB
  per app). Django + DRF + Postgres + gunicorn + a CRA build does not fit, and
  Postgres is not part of the platform.
- **`deploy.sh` would have fought the platform and could take the whole domain
  down.** It `apt-get install`ed postgresql/nginx/certbot, wrote
  `/etc/nginx/sites-available/tycooncraft`, `rm -f`ed `sites-enabled/default`,
  and ran `certbot --nginx` plus `systemctl restart nginx`.
- None of the four contract files existed: no `app.json`, `public/tile.gif`,
  `Dockerfile`, or `docker-compose.yml`. No `/health`. No `BASE_PATH` handling.
- CRA needed a build step and hardcoded `"proxy": "http://localhost:8000"`.

---

## H. Correctness and hygiene

- **Zero tests.** No test file anywhere in the repo.
- Daily discovery caps (20/day standard), pro tiers, and 1,000 pre-generated
  upgrade keys — for a game three friends were going to play.
- The `sessionStorage` object catalog was never invalidated (`App.js:389`), so
  anything discovered in the current session was missing from it. It also shipped
  *every* object every player had ever created — an unboundedly growing payload.
- Image filenames collided: `md5(f"{object_a.id}{object_b.id}")`
  (`views.py:1037`) hashes ids 1+23 and 12+3 to the same `"123"`.
- `increment_rate_limit` (`services/rate_limit.py:164`) never reset its window.
- An O(n) Python overlap scan per placement (`views.py:1108`) loaded every placed
  object, and the bounds check ran *after* it.
- `SECRET_KEY` fell back to a hardcoded `django-insecure-…` default.
- ~25 markdown docs for a 17k-line repo, much of it stale and self-contradictory
  (`START_HERE.txt`, `INDEX.md`, `PROJECT_SUMMARY.md`, `QUICKSTART.md`,
  `ERA_CONSOLIDATION_SUMMARY.md`, `DEPLOYMENT_CHECKLIST.md`, …). The README
  documented 5s polling; the code polled at 1s.
- Build artifacts committed at `mnt/user-data/outputs/tycooncraft/`.

---

## The one-line summary

v1 asked a language model to be the game designer, the economist, and the artist
on every craft, then gated all progression behind it guessing one exact string —
while the prompt told it not to. v2 asks it to name things.

---

## Where v1's generated art went

The 59 starter sprites lived at `backend/media/objects/starter-*.png`. They are
**not** in the working tree: they are 1024×1024 RGBA at ~1.3 MB each — 81 MB in
total, which every CI checkout would have paid for — and at that size they are
raw generation output rather than usable 64×64 sprite seeds.

They remain in git history, which is all the phase-2 sprite pass needs:

```bash
git log --oneline -- backend/media/objects        # find the last commit with them
git show <sha>:backend/media/objects/starter-clay.png > /tmp/clay.png
```
