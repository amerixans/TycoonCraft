# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TycoonCraft is a civilization-crafting tycoon game built with Django REST Framework (backend) and React (frontend). Players combine objects to discover new items, progressing through 10 eras from Hunter-Gatherer to Beyond. The game uses OpenAI's GPT-5-mini for object generation and GPT-image-1-mini for visual assets.

## Development Commands

### Backend (from `backend/`)

```bash
# Setup
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Database setup (requires PostgreSQL)
python manage.py migrate
python manage.py initialize_starter_objects
python manage.py createsuperuser

# Run development server
python manage.py runserver

# Other management commands
python manage.py shell          # Django shell
python manage.py dbshell        # Database shell
python manage.py generate_upgrade_keys  # Create pro upgrade keys
```

### Frontend (from `frontend/`)

```bash
# Setup and run
npm install
npm start       # Dev server on :3000
npm run build   # Production build
npm test        # Run tests
```

### Environment Variables

Create `.env` in project root with:
- `DJANGO_SECRET_KEY` - Django secret key
- `DEBUG` - True/False
- `OPENAI_API_KEY` - Required for crafting/image generation
- `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` - PostgreSQL config

## Architecture

### Request Flow

1. **Frontend** (React) → CSRF-protected session-based requests → **Backend** (Django REST)
2. **Crafting flow**: User combines two objects → Backend checks for existing recipe → If new, calls OpenAI Responses API → Stores result globally → Returns to user
3. **API Client**: `frontend/src/api.js` handles all backend communication with CSRF token injection

### Database Models (`backend/game/models.py`)

- **GameObject**: Object definitions with stats, era, category, costs, income, footprint, global_modifiers (JSONField)
- **CraftingRecipe**: Maps (object_a, object_b) → result, globally cached
- **PlayerProfile**: User state (coins, time_crystals, current_era, is_pro)
- **Discovery**: Player-specific object discoveries
- **PlacedObject**: Objects on player's 1000x1000 canvas with position, build/retire times, operational status
- **EraUnlock**: Tracks unlocked eras per player
- **RateLimit**: Tracks per-minute and daily rate limits
- **UpgradeKey**: Redeemable keys for pro status (500 daily calls vs 20 standard)

### Key Backend Files

- `backend/game/views.py`: All game logic and API endpoints
  - Crafting logic: `craft_objects()` at line 806
  - Rate limiting: `check_daily_rate_limit()`, `check_global_daily_rate_limit()`
  - Coin updates: `update_player_coins()` at line 262 (handles global_modifiers, building completion, keystone unlocks)
  - OpenAI integration: `call_openai_crafting()` at line 546, `call_openai_image()` at line 675
  - Predefined recipes: `load_predefined_recipes()`, `get_predefined_recipe()`, `validate_predefined_match()`
- `backend/game/serializers.py`: DRF serializers for API responses
- `backend/prompts/`: AI prompt templates and JSON schemas
  - `crafting_recipe.txt`: Main crafting prompt template
  - `object_schema.json`: Structured output schema for OpenAI
  - `predefined_recipes.json`: Authoritative recipe overrides

### Frontend Components

- `App.js`: Main application state and layout
- `components/Sidebar.js`: Object discovery list and crafting interface
- `components/CraftingArea.js`: Drag-and-drop crafting UI
- `components/Canvas.js`: Grid-based object placement with zoom/pan
- `components/CraftingQueue.js`: Queued crafting system
- `api.js`: Axios client with CSRF token handling

## Critical Code Patterns

### Numeric Comparisons

All numeric fields use `DecimalField`. When comparing values, code normalizes to float with epsilon tolerance:

```python
# See _values_equal() in backend/game/views.py:419
abs(float(actual) - float(expected)) < 1e-9
```

Always respect this pattern to avoid floating-point precision issues.

### Global Modifiers System

Objects can have `global_modifiers` (JSONField) that affect other objects:

```json
{
  "active_when": "operational",
  "affected_categories": ["natural", "tool"],
  "income_multiplier": 1.5,
  "stacking": "multiplicative"  // or "additive"
}
```

Applied in `update_player_coins()` at backend/game/views.py:262.

### Predefined Recipes

Authoritative overrides loaded from `backend/prompts/predefined_recipes.json`:
- `load_predefined_recipes()`: Loads and caches recipes
- `get_predefined_recipe(obj_a, obj_b)`: Finds match (checks both orderings)
- `validate_predefined_match(game_object, overrides)`: Validates existing objects against specs
- If existing recipe doesn't match predefined specs, it's deleted and regenerated

### Era Progression

10 eras defined in `backend/game/views.py:36-52`:
- Each era has crystal cost to unlock (ERA_CRYSTAL_COSTS) and crafting cost (ERA_CRAFTING_COSTS)
- Crafting two objects from different eras results in error (backend/game/views.py:854)
- Result era is the higher of the two input eras
- Keystone objects unlock the NEXT era when placed and operational
- Keystones belong to the SAME era as their inputs but unlock the next era

### Rate Limiting

Two-tier system:
1. **Daily limits** (primary): Standard=20, Pro=500, Admin=1000, Global=4000
   - Enforced by `check_daily_rate_limit()` and `check_global_daily_rate_limit()`
2. **Per-minute limits** (legacy): 4 user discoveries/min, 50 global API calls/min
   - Kept for system stability

### Admin User Handling

The admin user (`username == "admin" && is_superuser`) can:
- Go negative on coins when crafting/placing objects
- Has 1000 daily API calls instead of tier-based limits
- Check via `is_admin_user()` in backend/game/views.py:254

## API Endpoints

All endpoints under `/api/`:

**Auth**: `POST /register/`, `POST /login/`, `POST /logout/`

**Game**:
- `GET /game-state/` - Complete game state
- `POST /craft/` - Craft objects (may call OpenAI)
- `POST /place/` - Place object on canvas
- `POST /remove/` - Remove placed object with refund
- `POST /unlock-era/` - Unlock next era with crystals
- `GET /export/` - Export game state JSON
- `POST /import/` - Import game state JSON
- `POST /redeem-upgrade-key/` - Upgrade to pro status

## OpenAI Integration

Server-side calls using Responses API (`POST /v1/responses`):

1. **Crafting**: Uses structured output with JSON schema (`object_schema.json`)
   - Model: `gpt-5-mini`
   - Prompt template: `backend/prompts/crafting_recipe.txt`
   - Input: Object capsules with era context
   - Output: Complete GameObject specification

2. **Images**: Direct image generation
   - Model: `gpt-image-1-mini`
   - Prompt template: `backend/prompts/image_prompt.txt`
   - Size: 1024x1024, transparent background
   - Returns: base64 image saved to `media/objects/`

## Important Gotchas

1. **Changing numeric fields**: May break predefined recipe validation. `validate_predefined_match()` relies on exact field names like `footprint_w`, `retire_payout_coins_pct`.

2. **Missing OPENAI_API_KEY**: Code raises at runtime if key is not in environment/settings.

3. **Predefined recipes matching**: String-based on `object_name`, checks both input orderings.

4. **Canvas overlap**: Simple AABB collision detection in `place_object()` at backend/game/views.py:1094.

5. **Era mismatch errors**: Players cannot combine objects from different eras (added to prevent confusion).

6. **Keystone auto-unlock**: When a keystone finishes building, it automatically unlocks the NEXT era (checked in `update_player_coins()`).

## Testing Notes

No unit tests currently in repo. When adding tests:
- Use Django `TestCase`
- Focus on: crafting flow (predefined vs OpenAI), `update_player_coins()` modifier stacking, rate limiting
- Mock OpenAI API calls to avoid hitting real endpoints

## Related Documentation

See `.github/copilot-instructions.md` for additional code patterns and hotspots.
