<!-- TycoonCraft: Repository-specific instructions for AI coding agents -->
# TycoonCraft — quick orientation for code-writing agents

This file highlights the concrete, discoverable patterns and hotspots in the codebase so an AI agent can be productive right away. Refer to the named files for authoritative behavior.

- Project layout (important files)
  - `backend/` — Django REST API; key files: `manage.py`, `requirements.txt`, `tycooncraft/settings.py`.
  - `backend/game/` — main app: `models.py`, `views.py`, `serializers.py`, `urls.py`, `management/commands/initialize_starter_objects.py`.
  - `backend/prompts/` — AI prompt templates and schemas: `crafting_recipe.txt`, `image_prompt.txt`, `object_capsule.json`, `object_schema.json`, `predefined_recipes.json`.
  - `frontend/` — React app: `package.json`, `src/api.js`, `src/components/*` (Canvas, CraftingArea, Sidebar).

- Big-picture architecture
  - Frontend (React) talks to the Django API under `/api/*` (session-based auth). See `frontend/src/api.js` for client patterns.
  - Game domain objects are stored in `GameObject`, `CraftingRecipe`, `PlacedObject`, `PlayerProfile` (see `backend/game/models.py`).
  - Crafting: first-time combinations call the OpenAI Responses API (server->server) to produce a structured object; results are persisted and cached globally.
  - Prompts + structured schemas live in `backend/prompts/`. Use these files when generating or validating AI-driven outputs.

- Notable code patterns & conventions to follow
  - Numeric fields use Django `DecimalField`. When comparing numeric values, the code normalizes to float and uses a tiny epsilon (see `_values_equal` in `backend/game/views.py`). Respect this when changing logic or tests.
  - `global_modifiers` is a JSONField containing modifier objects with keys like `active_when`, `affected_categories`, `income_multiplier`, and `stacking` (see `update_player_coins` in `views.py`).
  - Predefined recipes are authoritative overrides: load with `load_predefined_recipes()` and test matches with `get_predefined_recipe()` and `validate_predefined_match()`.
  - Rate limits are enforced by `RateLimit` model and configured in `tycooncraft/settings.py` (`RATE_LIMIT_USER_DISCOVERIES`, `RATE_LIMIT_GLOBAL_API_CALLS`, `RATE_LIMIT_WINDOW`).

- OpenAI integration specifics
  - Server-side calls use the Responses API (POST /v1/responses). The code expects `OPENAI_API_KEY` in environment or `.env` loaded by `settings.py`.
  - Prompt templates & schemas: `backend/prompts/crafting_recipe.txt`, `object_capsule.json`, `object_schema.json`. If implementing generation logic, reuse these files and the parsing helpers (`_extract_responses_text`).

- How to run & common dev workflows (explicit)
  - Backend: from `backend/`:
    - Create venv, install: `python -m venv venv && source venv/bin/activate && pip install -r requirements.txt`
    - DB: PostgreSQL; env vars: `DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT` (settings load `.env` from project root).
    - Migrate & seed: `python manage.py migrate && python manage.py initialize_starter_objects`
    - Run dev server: `python manage.py runserver`
  - Frontend: from `frontend/`: `npm install && npm start` (dev server at :3000).
  - Useful management action: `python manage.py initialize_starter_objects` creates the 4 starter objects.

- API hotspots & examples
  - Crafting: `POST /api/craft/` body `{"object_a_id": 1, "object_b_id": 2}` — backend enforces per-user discovery rate limits.
  - Place/remove: `POST /api/place/`, `POST /api/remove/` with payloads shown in README.
  - Export/import whole state: `GET /api/export/`, `POST /api/import/` (use `GameStateSerializer` for format reference in `serializers.py`).

- Tests, logging, and debugging pointers
  - There are no unit tests in the repo; when adding tests, prefer Django `TestCase` and exercises around: crafting flow (predefined match vs OpenAI call), `update_player_coins` (modifier stacking), and rate limiting.
  - Logs: check Django logs (configured by deploy), and `MEDIA_ROOT` for image artifacts (see `tycooncraft/settings.py`).

- Small gotchas to watch for
  - Changing numeric fields or serializer shapes can break predefined recipe validation—`validate_predefined_match()` is tolerant but relies on field names like `footprint_w`, `retire_payout_coins_pct`.
  - OpenAI key must be present in `.env` or `OPENAI_API_KEY` env var; code raises at runtime if missing.
  - `predefined_recipes.json` ordering is matched for either input ordering but matching is string-based on `object_name`.

If anything above is unclear, tell me which area (backend prompts, crafting flow, or frontend API client) you want expanded and I will iterate.
