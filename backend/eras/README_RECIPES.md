# General Recipes Feature

## Overview

You can now define predefined recipes in the era YAML files in two ways:

1. **Keystone Recipe Chains** - Required recipes that lead to the era's keystone (already existed)
2. **General Recipes** - NEW! Optional predefined recipes outside the keystone chain

## How It Works

### Defining General Recipes

Add a `recipes` section to any era YAML file:

```yaml
# ==============================================================================
# GENERAL RECIPES (Optional predefined recipes outside the keystone chain)
# ==============================================================================
recipes:
  - comment: "Water + Stick = Fishing Rod"
    input_a: "Water"
    input_b: "Stick"
    output_name: "Fishing Rod"
    overrides:
      era_name: "Hunter-Gatherer"
      category: "tool"
      cost: 500
      income_per_second: 5

  - comment: "Rock + Rock = Heavy Stone"
    input_a: "Rock"
    input_b: "Rock"
    output_name: "Heavy Stone"
    overrides:
      era_name: "Hunter-Gatherer"
      category: "natural"
      cost: 100
      footprint:
        w: 2
        h: 2
```

### What Happens When a Recipe is Crafted

1. **First time crafting**: OpenAI generates the object based on your `overrides` specifications
2. **Subsequent crafts**: Uses the cached recipe from the database
3. **If you change the YAML**: Next craft will detect the mismatch, delete the old object, and call OpenAI again with new specs
4. **Once it matches**: No more OpenAI calls until you change the YAML again

### Available Override Fields

You can override any GameObject field in the `overrides` section:

#### Basic Fields
- `object_name` (automatically set from `output_name`, but can override)
- `era_name`
- `category` (e.g., "natural", "tool", "power", "factory")
- `quality_tier` (e.g., "common", "uncommon", "rare")
- `is_keystone` (true/false)

#### Economic Fields
- `cost` (coin cost to craft/place)
- `income_per_second` (coins generated per second)
- `time_crystal_cost` (crystals required to place)
- `time_crystal_generation` (crystals generated)

#### Timing Fields
- `build_time_sec` (seconds to build)
- `operation_duration_sec` (seconds before retiring)

#### Spatial Fields
- `footprint` (as dict):
  ```yaml
  footprint:
    w: 2
    h: 3
  ```
- `size` (visual size multiplier, e.g., 0.5, 1.0, 2.0)

#### Payout Fields
- `retire_payout` (as dict):
  ```yaml
  retire_payout:
    coins_pct: 0.3  # 30% of cost back
  ```
- `sellback_pct` (immediate removal payout)

#### Advanced Fields
- `cap_per_civ` (max number allowed, null for unlimited)
- `global_modifiers` (array of modifier objects):
  ```yaml
  global_modifiers:
    - active_when: "operational"
      affected_categories: ["power"]
      income_multiplier: 1.12
      stacking: "multiplicative"
      max_stacks: 1
  ```

## Examples

### Simple Recipe with Basic Overrides

```yaml
recipes:
  - comment: "Stick + Dry Grass = Torch"
    input_a: "Stick"
    input_b: "Dry Grass"
    output_name: "Torch"
    overrides:
      era_name: "Hunter-Gatherer"
      category: "tool"
      cost: 200
```

### Complex Recipe with Advanced Overrides

```yaml
recipes:
  - comment: "Iron + Gear = Advanced Machine"
    input_a: "Iron"
    input_b: "Gear"
    output_name: "Advanced Machine"
    overrides:
      era_name: "Steam & Industry"
      category: "factory"
      cost: 50000
      income_per_second: 500
      build_time_sec: 60
      operation_duration_sec: 5000
      footprint:
        w: 4
        h: 4
      size: 3.0
      cap_per_civ: 5
      global_modifiers:
        - active_when: "operational"
          affected_categories: ["factory"]
          income_multiplier: 1.05
          stacking: "multiplicative"
```

## Important Notes

1. **Recipe matching is order-independent**: "Water + Stick" is the same as "Stick + Water"
2. **Recipes are era-specific**: Place recipes in the YAML file of the appropriate era
3. **Input objects must exist**: Make sure the input objects are either starters or craftable
4. **Validation is strict**: The system validates numeric fields with floating-point precision tolerance (1e-9)
5. **Changes require restart**: The recipe cache is loaded at startup. After modifying YAMLs, restart the Django server

## Testing Your Recipes

1. Add the recipe to an era YAML file
2. Restart the Django server to reload the cache
3. In the game, craft the two objects together
4. The first craft will call OpenAI and create the object with your specifications
5. Verify the object has the correct stats
6. Future crafts of the same combination will use the cached recipe

## Troubleshooting

### Recipe Not Loading
- Check that the `recipes` section is at the root level of the YAML (same level as `starters`, `keystone`, etc.)
- Ensure proper YAML indentation (use spaces, not tabs)
- Restart the Django server

### OpenAI Keeps Getting Called
- Check that the override fields match the existing object exactly
- Remember that numeric fields use epsilon comparison (1e-9 tolerance)
- Check server logs for validation errors

### Recipe Doesn't Match Inputs
- Verify the input object names are spelled correctly (case-sensitive)
- Ensure both input objects exist in the game
- Check that both objects are from the same era (cross-era crafting is not allowed)
