# Era Progression System Implementation

## Overview
This implementation adds complete era progression functionality to TycoonCraft, enabling automatic era unlocks when keystone objects are placed and proper era assignment for crafted objects.

## Backend Changes Made

### 1. New Helper Functions in `views.py`

Three new helper functions have been added to manage era progression:

```python
def get_next_era(current_era):
    """Get the next era in sequence, or None if at the end."""
    
def get_unlocked_eras(profile):
    """Get list of all eras unlocked by the player."""
    
def get_higher_era(era_a, era_b):
    """Get the higher (more advanced) era between two eras."""
```

### 2. Modified `place_object` View - Auto-Unlock Era

The `place_object` endpoint now automatically unlocks the next era when a keystone object is placed:

**Key Changes:**
- After placing an object, checks if `game_object.is_keystone` is True
- If it's a keystone, the object's `era_name` IS the era it unlocks
- Creates an `EraUnlock` record if not already unlocked
- Updates the player's `current_era` to the newly unlocked era
- Returns enhanced response with `era_unlocked` and congratulatory message

**Example Response when placing keystone:**
```json
{
  "id": 123,
  "game_object": {...},
  "x": 10,
  "y": 10,
  "era_unlocked": "Agriculture",
  "message": "Congratulations! You have unlocked the Agriculture era!"
}
```

### 3. Modified `call_openai_crafting` - Era Context

The crafting function now receives and uses era context to guide AI generation:

**New Parameters:**
- `unlocked_eras`: List of all eras the player has unlocked
- `current_era`: The player's current era

**Era Context Passed to AI:**
The function now builds a detailed era context block that includes:
- Current era
- All unlocked eras
- The higher input era
- The next potential era
- Critical era assignment rules

**Critical Era Assignment Rules (passed to AI):**

1. **For KEYSTONE objects (is_keystone: true):**
   - MUST be assigned to the NEXT era beyond the higher input era
   - Example: Combining Agriculture objects → keystone is "Metallurgy"
   - This is because placing the keystone unlocks that next era

2. **For REGULAR objects (is_keystone: false):**
   - MUST be assigned to the higher era of the two inputs
   - Example: Hunter-Gatherer + Agriculture → result is Agriculture
   - Never assign beyond player's highest unlocked era + 1

### 4. Updated `craft_objects` View

The crafting endpoint now:
- Retrieves player's unlocked eras before calling AI
- Passes era context to `call_openai_crafting`
- Ensures the AI has full context for proper era assignment

## How Era Progression Works

### The Complete Flow:

1. **Starting State:**
   - Player starts in "Hunter-Gatherer" era
   - Has access to 4 starter objects: Rock, Stick, Water, Dirt

2. **Crafting Within Era:**
   - Player crafts objects within Hunter-Gatherer era
   - Regular objects remain in Hunter-Gatherer era
   - Eventually discovers/crafts a keystone combination

3. **Keystone Discovery:**
   - When two objects combine to make a keystone (e.g., Fire + Wood = Campfire)
   - The AI creates this object with:
     - `is_keystone: true`
     - `era_name: "Agriculture"` (the NEXT era, not current)
     - Usually `cap_per_civ: 1-3` (limited quantity)

4. **Placing the Keystone:**
   - Player places the Campfire keystone object
   - Backend automatically:
     - Creates `EraUnlock` for "Agriculture"
     - Updates `profile.current_era` to "Agriculture"
     - Returns success message with era unlock notification

5. **New Era Access:**
   - Player now has Agriculture era unlocked
   - Can craft with Agriculture-era objects
   - Combining Hunter-Gatherer + Agriculture items creates Agriculture items
   - Eventually works toward the Agriculture keystone (Fertilizer)

6. **Progression Continues:**
   - Agriculture keystone → unlocks Metallurgy
   - Metallurgy keystone → unlocks Steam & Industry
   - And so on through all 10 eras

### Era Sequence:
1. Hunter-Gatherer (starting, unlocked by default)
2. Agriculture (unlocked by Campfire keystone)
3. Metallurgy (unlocked by Fertilizer keystone)
4. Steam & Industry (unlocked by Metal keystone)
5. Electric Age (unlocked by Boiler keystone)
6. Computing (unlocked by Generator keystone)
7. Futurism (unlocked by Microchip keystone)
8. Interstellar (unlocked by Nanofab keystone)
9. Arcana (unlocked by FTL Relay keystone)
10. Beyond (unlocked by Ley Capacitor keystone)

## Frontend Considerations

### Required Frontend Changes:

1. **Era Display:**
   - Show current era in player profile/HUD
   - Display list of unlocked eras
   - Visual indicator for era progression

2. **Keystone Indicators:**
   - Mark keystone objects with special icon/badge
   - Show which era a keystone will unlock
   - Highlight keystone objects in discovery list

3. **Era Unlock Notification:**
   - Show celebration/modal when new era is unlocked
   - Display era unlock message from backend response
   - Animate transition to new era

4. **Crafting UI:**
   - Show era of each object
   - Indicate when combining objects from different eras
   - Display potential result era before crafting

5. **Object Filtering:**
   - Filter objects by era
   - Show which objects are from which era
   - Highlight newly accessible objects after era unlock

### Example Frontend Response Handling:

```javascript
// When placing an object
const response = await placeObject(objectId, x, y);

if (response.era_unlocked) {
  // Show celebration modal
  showEraUnlockCelebration(response.era_unlocked, response.message);
  
  // Update UI
  refreshPlayerProfile();
  refreshAvailableObjects();
  
  // Play sound effect
  playEraUnlockSound();
}
```

## Testing the Implementation

### Test Scenario 1: First Era Unlock
1. Create new account (starts in Hunter-Gatherer)
2. Craft objects until you create a keystone
3. Place the keystone object
4. Verify:
   - New era is unlocked
   - `current_era` is updated
   - Response includes unlock message
   - Can now craft with new era objects

### Test Scenario 2: Cross-Era Crafting
1. Have two eras unlocked (e.g., Hunter-Gatherer + Agriculture)
2. Combine an object from each era
3. Verify:
   - Result is in the higher era (Agriculture)
   - Object stats scale appropriately
   - Era assignment is correct

### Test Scenario 3: Keystone Creation
1. Craft a combination that should produce a keystone
2. Verify:
   - `is_keystone` is true
   - `era_name` is the NEXT era (not current)
   - `cap_per_civ` is limited (1-3)
   - Object is thematically significant

## Database Considerations

### No Migration Required
The implementation uses existing models:
- `EraUnlock` model already exists
- `GameObject.is_keystone` field already exists
- `PlayerProfile.current_era` field already exists

### Existing Data
- Existing keystone objects may need their `era_name` corrected
- Should be tagged with the era they UNLOCK, not the era they're from
- Run a data migration script if needed to fix existing keystones

## Configuration

### Settings Variables (already in settings.py):
```python
ERA_CRYSTAL_COSTS = {
    "Hunter-Gatherer": 0,
    "Agriculture": 10,
    "Metallurgy": 50,
    # ... etc
}
```

### Note on Crystal Costs:
- Crystal costs are for MANUAL era unlock (via `/api/unlock-era/`)
- Keystone placement unlocks eras automatically WITHOUT crystal cost
- This is intentional - two paths to progression:
  1. Natural path: Craft and place keystones
  2. Fast path: Spend time crystals to skip ahead

## API Endpoint Changes

### Updated Endpoints:

#### POST `/api/place/`
**New Response Fields:**
- `era_unlocked` (string, optional): Name of newly unlocked era
- `message` (string, optional): Congratulatory message

**Example:**
```json
{
  "id": 123,
  "game_object": {...},
  "x": 10,
  "y": 10,
  "placed_at": "2025-10-15T12:00:00Z",
  "is_operational": true,
  "era_unlocked": "Agriculture",
  "message": "Congratulations! You have unlocked the Agriculture era!"
}
```

### No Changes to Other Endpoints:
- `/api/craft/` - Same interface, improved internal logic
- `/api/game-state/` - Same response structure
- `/api/unlock-era/` - Still available for manual unlocks

## Benefits of This Implementation

1. **Seamless Progression:** Players naturally discover and unlock eras through gameplay
2. **Clear Goals:** Keystones provide clear progression milestones
3. **AI-Guided:** OpenAI generates appropriate keystone and regular objects with correct era assignments
4. **Flexible:** Still allows manual era unlocks via time crystals
5. **Scalable:** Works for all 10 eras without special cases

## Summary

This implementation provides a complete era progression system where:
- Keystone objects are properly tagged with the era they unlock
- Placing keystones automatically unlocks new eras
- AI crafting respects era progression rules
- Players have clear progression paths through all 10 eras
- The system scales naturally from Hunter-Gatherer to Beyond

The backend is now fully functional. Frontend changes will enhance the player experience but are not strictly required for the system to work.
