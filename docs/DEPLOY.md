# Deploying TycoonCraft

One container on the shared collabcanvas droplet
(`collabcanvas`, `167.172.248.41`). There is **no DigitalOcean step** — the
droplet already exists and this is just another container on it. Do not create a
droplet, an App Platform app, or a domain, and do not touch ports 80 or 443.

## Before the first deploy

Every deploy after the first is just `git push`, so this section runs once.

### 1. Check it locally, both ways

```bash
docker compose up --build                          # serves at /
BASE_PATH=/tycooncraft docker compose up --build   # as the droplet runs it
```

The second is the one that matters. An app that works only at the domain root
404s all of its own assets the moment it is mounted, and the failure looks like a
broken app rather than a path bug.

```bash
pytest -m "not live"
BASE_URL=http://127.0.0.1:8080/tycooncraft pytest tests/test_module_graph.py tests/test_live_api.py
```

### 2. Onboard

From your Mac, with the repo already pushed to GitHub:

```bash
../collab-canvas/bin/onboard-app.sh tycooncraft
```

That does the whole thing and is safe to re-run: makes a read-only deploy key on
the droplet, registers it on the repo, sets the three Actions secrets, clones to
`/opt/tycooncraft`, allocates a free port, writes the nginx snippet, starts the
container, waits for `/health`, and publishes the tile.

### 3. Add the API key

**The game works without this.** Items get deterministic names built from their
traits, `/health` reports `{"llm": "unconfigured"}`, and nothing errors. So
deploy first, verify it works, then add the key.

Either place works. **The GitHub secret is the better default** — it survives a
droplet rebuild and rotating it means editing one field.

#### Option A — a GitHub Actions secret (recommended)

**Settings → Secrets and variables → Actions → New repository secret**, named
exactly `ANTHROPIC_API_KEY`. Then **Actions → ci-and-deploy → Run workflow** to
deliver it without needing a commit.

The deploy job forwards the secret over the existing SSH connection and writes it
into the droplet's `.env`. Two details in that script matter:

- It **rebuilds** `.env` rather than `sed`-ing it, so a key containing `|` or `&`
  cannot corrupt the file, and `BASE_PATH` / `HOST_PORT` — which `add-app.sh` owns
  and the app cannot start without — are preserved.
- It **does nothing if the secret is unset.** Without that guard, a repo with no
  secret would silently blank a working key on every deploy.

The workflow log ends with `naming: ready` or `naming: unconfigured`, so you can
confirm it took without going and curling anything. It never prints the key.

Note that Actions still never *calls* the API — it only delivers the key. The
naming call happens on the droplet.

#### Option B — straight onto the droplet

Fine if you would rather the key never touch GitHub. Note `add-app.sh` already
seeded `.env` from `.env.example`, so there is an **empty `ANTHROPIC_API_KEY=`
line already there** — fill it in rather than appending a second one.

```bash
ssh deploy@167.172.248.41
cd /opt/tycooncraft
nano .env                     # fill in the ANTHROPIC_API_KEY= line
docker compose up -d          # picks up the new environment
curl -s "http://127.0.0.1:$(grep '^HOST_PORT' .env | cut -d= -f2)/tycooncraft/health" | jq .llm
# -> "ready"
```

If you use Option B, leave the GitHub secret unset — otherwise the next deploy
overwrites what you typed with the secret's value.

#### Where it does *not* go

| | |
| --- | --- |
| The DigitalOcean console | ❌ there is no DO configuration for a microapp. |
| Committed to the repo | ❌ `.gitignore` blocks `.env` for exactly this reason. |

Get a key at <https://console.anthropic.com> → **Create Key**.

Cost is small enough to be worth stating plainly: a never-before-seen
combination is ~600 input and ~60 output tokens on `claude-sonnet-5`, so about
**$0.003**. Everything already named is a database lookup and costs nothing.

### 4. Pre-generate the names — strongly recommended

With the key on **your Mac** (not the droplet), name the entire authored game
ahead of time:

```bash
python3 tools/build_recipes.py --dry-run      # see the plan and the cost
ANTHROPIC_API_KEY=sk-ant-... python3 tools/build_recipes.py
git add content/recipes.json && git commit -m "Pre-generate tier 1-3 names" && git push
```

**102 names for about $0.14**, via the Batch API at half price. After this, tiers
1–3 make no API calls at all, so the first player gets the same instant
experience as the hundredth — which was the loudest complaint about the first
version of the game.

The pack is baked into the image and loaded into the item registry on boot.
`first_by` stays NULL for pre-generated names, so being the first player to
actually *make* something is still a claimable first discovery.

## Every deploy after that

Push to `main`. CI validates the manifest and tile, runs the unit tests, builds
the image, smoke-tests it at both `/` and `/tycooncraft/` **with no API key**,
walks the ES module graph, then SSHes in and runs:

```bash
cd /opt/tycooncraft
git fetch --all && git reset --hard origin/main
docker compose up -d --build
/opt/collab-canvas/deploy/publish-app.sh tycooncraft   # refresh tile + blurb
```

That last line is why editing `app.json` or redrawing the tile updates the front
page on the next push.

## Done means

Not "the workflow went green". All three:

```bash
curl -fsS -o /dev/null -w '%{http_code}\n' https://collabcanvas.org/tycooncraft/
curl -s https://collabcanvas.org/apps.json | jq -r '.[].name' | grep -x tycooncraft
curl -fsS -o /dev/null -w '%{http_code}\n' \
  "https://collabcanvas.org$(curl -s https://collabcanvas.org/apps.json | jq -r '.[]|select(.name=="tycooncraft").tile')"
```

The app answers, it is in the registry, and its tile loads.

## Operating

```bash
cd /opt/tycooncraft
docker compose ps
docker compose logs -f --tail=100
curl -s http://127.0.0.1:$(grep HOST_PORT .env | cut -d= -f2)/tycooncraft/health | jq
```

`/health` reports something real, so it is the first place to look:

```json
{
  "ok": true,
  "base": "/tycooncraft",
  "llm": "ready",
  "players": 3,
  "items_named": 118,
  "fallback_names": 0,
  "placements": 27
}
```

| Symptom | Cause |
| --- | --- |
| Items have names like "Fired Stock", `fallback_names` climbing | No API key in `.env`, or it is invalid. Step 3. |
| `llm: "unconfigured"` | Same. Note this is a *valid* state — the game plays fine. |
| Stuck on a blank page, server healthy | The module graph 404'd. Almost always a `../..` import climbing above the mount, or an absolute `/src/…`. Check the network tab, not the logs. `tests/test_module_graph.py` catches this. |
| 502 on the whole domain | A bad nginx snippet got in. `sudo nginx -t` names the file. Not us unless someone hand-edited `snippets/apps/`. |
| Everyone's save vanished | The `tycooncraft-data` volume was purged. `remove-app.sh --purge` does that; plain `remove-app.sh` does not. |

## State and backups

The SQLite database lives in the `tycooncraft-data` docker volume mounted at
`/app/data`, so it survives redeploys. `content/recipes.json` is baked into the
image and is *not* state — it is content.

There is no `deploy/backup.sh` yet, so this app is **not** in the nightly backup
rotation. For three friends and a game you can replay, that is a deliberate
choice rather than an oversight; add one if that changes.
