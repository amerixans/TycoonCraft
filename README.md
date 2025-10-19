# TycoonCraft

TycoonCraft is a web-based incremental crafting tycoon where players combine objects to discover new technology, build a civilization on a grid canvas, and march through ten eras of human progress. The backend generates new object definitions and artwork with OpenAI while enforcing rate limits, tiered accounts, and grid-based placement rules. The React frontend provides the crafting UI, placement canvas, modals, and theming controls.

## Gameplay Systems

- **Crafting** – Players unlock a catalog of objects and can craft any pair of discoveries from the same era. New recipes call OpenAI (`gpt-5-mini`) using the structured prompts in `backend/prompts/`. Predefined recipes and schema validation keep outputs aligned with game balance.
- **Canvas & Buildings** – Objects are placed on a 1000×1000 grid with footprint collision checks, build timers, retirement payouts, and global modifiers. Keystone completions automatically unlock the next era and seed starter objects.
- **Economy Loop** – Coins and time crystals accrue from operational objects each time the server processes a request. Costs scale per era via `config.py`, and retire/sellback percentages are stored with each object.
- **Era Progression** – Ten eras (Hunter-Gatherer → Beyond) are shared across backend and frontend references. Players can advance via keystones or by purchasing unlocks with crystals.
- **Accounts, Saves & Upgrades** – Session-authenticated users can register, login, export/import cloud saves, and redeem upgrade keys for higher API limits. An admin command provisions a fully unlocked testing profile.
- **Rate Limits** – Daily and per-minute limits protect OpenAI usage. Tiered limits depend on `PlayerProfile.is_pro`, with upgrade keys and admin overrides handled server-side.

## Tech Stack

- **Backend**: Django 4.2, Django REST Framework, `python-dotenv`, PostgreSQL, `requests` for OpenAI calls.
- **Frontend**: React 18 with Create React App, Axios, `react-zoom-pan-pinch` for canvas controls.
- **AI**: OpenAI Responses API (`gpt-5-mini`) for object generation and Images API (`gpt-image-1-mini`) for artwork.
- **Deployment**: Gunicorn + Nginx (see `deployment.md`/`deploy.sh` for scripts and checklist).

## Repository Layout

```
TycoonCraft/
├── backend/
│   ├── manage.py
│   ├── requirements.txt
│   ├── tycooncraft/
│   │   ├── settings.py          # Loads backend/.env, Postgres & media config
│   │   └── urls.py              # Routes /admin and /api
│   ├── game/
│   │   ├── config.py            # Shared era metadata & cost helpers
│   │   ├── models.py            # GameObject, CraftingRecipe, PlayerProfile, ...
│   │   ├── serializers.py       # DRF serializers & import validation schemas
│   │   ├── views.py             # REST endpoints, OpenAI integration, economy loop
│   │   ├── services/
│   │   │   └── rate_limit.py    # Daily & per-minute throttling helpers
│   │   └── management/commands/
│   │       ├── create_admin_account.py
│   │       ├── generate_upgrade_keys.py
│   │       └── initialize_starter_objects.py
│   ├── media/objects/           # Seed art and generated object images
│   └── prompts/                 # Prompt templates & schemas (JSON + text)
├── frontend/
│   ├── package.json
│   ├── public/index.html
│   └── src/
│       ├── App.js               # App shell, auth, notifications, theming
│       ├── GameInfo.js          # In-game help modal content
│       ├── api.js               # Axios client with CSRF handling
│       ├── config.js            # Era constants mirrored from backend/config.py
│       ├── components/          # Canvas, CraftingArea, CraftingQueue, Sidebar, ...
│       └── utils/formatNumber.js
├── API_REFERENCE.md             # Endpoint details and payload examples
├── QUICKSTART.md                # Condensed setup instructions
├── deployment.md                # Hosting guide
├── deploy.sh / update.sh        # Helper scripts for deployment
└── README.md                    # (this document)
```

## Backend Highlights

- **Configuration (`backend/tycooncraft/settings.py`)**
  - Loads environment variables from `backend/.env` via `python-dotenv`.
  - Defaults to PostgreSQL; configure `DB_*` settings for local/remote databases.
  - Serves user-uploaded/generated assets from `MEDIA_URL=/media/` backed by `backend/media`.
  - Enforces DRF session authentication with CSRF protection and optional CORS allowlists.

- **Game App (`backend/game/`)**
  - `models.py` defines game state: `GameObject`, `CraftingRecipe`, `PlayerProfile`, `Discovery`, `PlacedObject`, `EraUnlock`, `RateLimit`, and `UpgradeKey`.
  - `views.py` exposes REST endpoints, orchestrates rate limiting, updates coins/crystals, calls OpenAI for new objects/images, stores generated art, validates imports, and handles upgrade key redemption.
  - `config.py` centralizes era ordering, crafting costs, and unlock costs used by both crafting and UI.
  - `services/rate_limit.py` implements tiered daily quotas plus legacy per-minute throttles feeding into crafting endpoints.
  - `management/commands/` contains utilities:
    - `initialize_starter_objects` seeds the database with starter content (including image paths).
    - `generate_upgrade_keys` tops the database up to 1000 keys and writes them to `backend/upgrade_keys.txt`.
    - `create_admin_account` provisions the `admin` superuser with all discoveries, unlocked eras, and Pro status, using the password from `DJANGO_SUPERUSER_PASSWORD`/`DJANGO_ADMIN_PASSWORD`.
  - `prompts/` include text templates and JSON schemas that drive OpenAI structured output (capsules, schema, predefined recipes).
  - `media/objects/` stores baseline art for starter items and newly generated images keyed by crafting pairs.

## Frontend Highlights

- **`src/App.js`** manages authentication flow, periodic game-state polling (5s interval), crafting queues/results, notifications, modals (info, era unlocks, discoveries, upgrade), and theme selection persisted in `localStorage`.
- **`src/api.js`** wraps Axios with CSRF token extraction from cookies and exposes typed helpers for `/api/register`, `/api/login`, `/api/game-state`, `/api/object-catalog`, `/api/craft`, `/api/place`, `/api/remove`, `/api/unlock-era`, `/api/export`, `/api/import`, and `/api/redeem-upgrade-key`.
- **Components**:
  - `Sidebar` lists discoveries with search/filtering and detail modals.
  - `CraftingArea`, `CraftingQueue`, and `CraftingResults` organize crafting inputs, in-flight operations, and previously discovered outputs.
  - `Canvas` renders the placement grid with drag/zoom controls (`react-zoom-pan-pinch`), footprint highlights, and removal actions.
- **Supporting Modules**:
  - `config.js` mirrors backend era constants to keep UI costs/unlock values in sync.
  - `GameInfo.js` powers the in-app help modal with HTML content.
  - `formatNumber.js` formats large coin/crystal values for readability.
- Frontend respects `REACT_APP_API_URL` (falls back to `/api`) and caches the object catalog in `sessionStorage` to avoid repeated large payloads.

## Environment & Configuration

Create `backend/.env` with the required settings:

```
DJANGO_SECRET_KEY=replace-me
DEBUG=True
OPENAI_API_KEY=sk-...
DB_NAME=tycooncraft
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=localhost
DB_PORT=5432
# Optional convenience admin account for local testing:
# DJANGO_SUPERUSER_USERNAME=admin
# DJANGO_SUPERUSER_PASSWORD=replace-with-strong-password
# Optional in production:
# CORS_ALLOWED_ORIGINS=https://app.tycooncraft.com,https://admin.tycooncraft.com
```

Additional notes:

- `RATE_LIMIT_*` values default from `settings.py` and can be overridden via environment variables if needed.
- Generated images are written under `backend/media/objects`; ensure the directory is writable by the Django process.
- For React, create `.env.local` with `REACT_APP_API_URL=http://localhost:8000/api` when running frontend and backend on different hosts.

## Local Development

1. **Database**
   ```bash
   createdb tycooncraft
   ```
   Update the `.env` credentials to match your local PostgreSQL setup.

2. **Backend**
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate        # Windows: venv\Scripts\activate
   pip install -r requirements.txt

   python manage.py migrate
   python manage.py initialize_starter_objects
   python manage.py generate_upgrade_keys    # optional but recommended before testing upgrades
   DJANGO_SUPERUSER_PASSWORD=your-strong-password python manage.py create_admin_account     # optional admin convenience account
   python manage.py runserver
   ```

3. **Frontend**
   ```bash
   cd frontend
   npm install
   npm start
   ```

4. **Usage**
   - Frontend served at http://localhost:3000 (CRA dev server).
   - Backend API at http://localhost:8000/api/.
   - Django admin at http://localhost:8000/admin/ (username defaults to `admin`; password comes from the `DJANGO_SUPERUSER_PASSWORD` you supplied when running `create_admin_account`).

## API Endpoints

All endpoints live under `/api/` and use session authentication (CSRF protected). Key routes:

- `GET /api/` – Health check and endpoint listing.
- `POST /api/register/` – Create user (`username`, `password`, `email` optional).
- `POST /api/login/` / `POST /api/logout/` – Session management.
- `GET /api/object-catalog/` – Full `GameObject` catalog (cache-friendly).
- `GET /api/game-state/` – Player profile, discoveries, placements, era unlocks.
- `POST /api/craft/` – Craft two objects (`object_a_id`, `object_b_id`); enforces era match, rate limits, costs, OpenAI generation.
- `POST /api/place/` – Place an object (`object_id`, `x`, `y`); checks coins, crystals, caps, overlaps, bounds.
- `POST /api/remove/` – Remove a placed object (`placed_id`) and refund coins based on sellback percentage.
- `POST /api/unlock-era/` – Spend crystals to unlock the next era and receive that era’s starter objects.
- `GET /api/export/` / `POST /api/import/` – Backup/restore player state with serializer validation.
- `POST /api/redeem-upgrade-key/` – Upgrade account to Pro using a generated key.

Refer to `API_REFERENCE.md` for payload/response samples and edge-case descriptions.

## Data Model Highlights

- `GameObject` – Canonical object definitions, including economy stats, footprint, modifiers, keystone flag, and `is_starter`.
- `CraftingRecipe` – Linking table storing combinations discovered (enforces uniqueness per ordered pair).
- `PlayerProfile` – Coins, crystals, current era, Pro flag, timestamps, and one-to-one with `auth.User`.
- `Discovery` & `PlacedObject` – Track per-player discoveries and grid placements with operational state.
- `EraUnlock` – Records unlocked eras; keystone completions append entries automatically.
- `RateLimit` – Tracks both per-player and global throttles for minute/day windows.
- `UpgradeKey` – Redeemable tokens for tier upgrades; generated via management command.

## Management Commands

Run from the `backend` directory:

- `python manage.py initialize_starter_objects` – Seeds starter objects across eras with stats and image references.
- `python manage.py generate_upgrade_keys` – Ensures 1000 upgrade keys exist and writes unredeemed keys into `backend/upgrade_keys.txt`.
- `python manage.py create_admin_account` – Creates/refreshes an `admin` superuser with all discoveries, eras, and Pro privileges (requires `DJANGO_SUPERUSER_PASSWORD` or `DJANGO_ADMIN_PASSWORD` to be set; `DJANGO_SUPERUSER_USERNAME` defaults to `admin`).

## AI Prompts & Assets

- `backend/prompts/` contains:
  - `crafting_recipe.txt` – Prompt template for crafting requests (filled with capsules and era context).
  - `object_capsule.json` & `object_schema.json` – Structured schema definitions consumed by the Responses API.
  - `image_prompt.txt` – Prompt for image generation.
  - `predefined_recipes.json` – Hard-coded overrides for specific combinations (enforces deterministic outputs).
- Generated images are saved as hashed filenames under `media/objects/`. Starter art ships in the repo so seeded items display immediately.

## Troubleshooting

- **Missing OpenAI key** – Crafting returns `OPENAI_API_KEY is not configured` (RuntimeError). Set the key in `backend/.env` and restart Django.
- **Era mismatch errors** – Crafting rejects cross-era inputs with `error_type: era_mismatch`. Ensure both inputs belong to the same era.
- **Rate limit responses** – `HTTP 429` indicates per-minute or daily limits exceeded. Upgrade to Pro, wait for reset, or adjust limits via settings.
- **Space occupied / Out of bounds** – Placement checks for overlap and a 1000×1000 grid; adjust coordinates or remove conflicting objects.
- **Key already redeemed / Invalid key** – Upgrade responses mirror `UpgradeKey` status; regenerate keys if needed via management command.

## Additional Documentation

This repository also includes:

- `QUICKSTART.md` – Quick checklist for new environments.
- `PROJECT_SUMMARY.md` – High-level product summary.
- `API_REFERENCE.md` – Detailed API write-up.
- `DEPLOYMENT_CHECKLIST.md` & `deployment.md` – Production deployment guidance.
- `ERA_PROGRESSION_IMPLEMENTATION.md` – Notes on era logic and historical context.

Use these references for deeper dives into mechanics, deployment, or integrations.
