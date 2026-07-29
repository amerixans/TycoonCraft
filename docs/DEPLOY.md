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

### 3. Add the API key — the one manual step

**The game works without this.** Items get deterministic names built from their
traits, `/health` reports `{"llm": "unconfigured"}`, and nothing errors. So
deploy first, verify it works, then add the key.

```bash
ssh deploy@167.172.248.41
cd /opt/tycooncraft
# .env already exists -- add-app.sh wrote BASE_PATH and HOST_PORT into it.
# Append the key; do not overwrite the file.
echo 'ANTHROPIC_API_KEY=sk-ant-...' >> .env
docker compose up -d          # picks up the new environment
curl -s http://127.0.0.1:$(grep HOST_PORT .env | cut -d= -f2)/tycooncraft/health | jq .llm
# -> "ready"
```

**Why here and not in GitHub:**

| | |
| --- | --- |
| `/opt/tycooncraft/.env` on the droplet | ✅ where it goes. `.env` is gitignored, so it survives the `git reset --hard origin/main` that every deploy runs. |
| A GitHub Actions secret | ❌ Actions never calls the API. It would put the key somewhere it is not needed. |
| The DigitalOcean console | ❌ there is no DO configuration for a microapp. |
| Committed to the repo | ❌ obviously, but worth saying: `.gitignore` blocks `.env` for this reason. |

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
