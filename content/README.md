Bundled, read-only game content baked into the image.

`recipes.json` is the pre-generated name pack (see `tools/build_recipes.py`).
It exists so early players get instant results rather than waiting on an API
call for combinations somebody was always going to make first — which was
complaint #1 about the first version of the game.

Runtime state does NOT live here. The player database is in the
`tycooncraft-data` docker volume mounted at /app/data, so it survives
redeploys; `data/` is gitignored for exactly that reason.
