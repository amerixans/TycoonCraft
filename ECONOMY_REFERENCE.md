# TycoonCraft Economy Reference Guide
## Quick Lookup for Balancing Objects

### 📊 Economy Tiers by Era

```
ERA 1: HUNTER-GATHERER
├─ Cost: 50 - 1,000 coins
├─ Income: 1 - 10 coins/sec
├─ ROI: 30-500 seconds (0.5-8 min)
├─ Duration: 300-5,000 seconds (5-83 min)
└─ Examples: Berry Patch (100c, 2c/s), Stone Tool (300c, 5c/s)

ERA 2: AGRICULTURE
├─ Cost: 800 - 8,000 coins
├─ Income: 5 - 80 coins/sec
├─ ROI: 30-500 seconds (0.5-8 min)
├─ Duration: 300-5,000 seconds (5-83 min)
└─ Examples: Farm (2,000c, 15c/s), Granary (5,000c, 40c/s)

ERA 3: METALLURGY
├─ Cost: 5,000 - 50,000 coins
├─ Income: 30 - 500 coins/sec
├─ ROI: 30-500 seconds (0.5-8 min)
├─ Duration: 300-5,000 seconds (5-83 min)
└─ Examples: Mine (15,000c, 100c/s), Forge (35,000c, 300c/s)

ERA 4: STEAM & INDUSTRY
├─ Cost: 40,000 - 400,000 coins
├─ Income: 200 - 3,000 coins/sec
├─ ROI: 30-500 seconds (0.5-8 min)
├─ Duration: 300-5,000 seconds (5-83 min)
└─ Examples: Steam Engine (100,000c, 500c/s), Factory (300,000c, 2,000c/s)

ERA 5: ELECTRIC AGE
├─ Cost: 300,000 - 3,000,000 coins
├─ Income: 1,500 - 25,000 coins/sec
├─ ROI: 70-1,000 seconds (1-17 min)
├─ Duration: 1,000-10,000 seconds (17-167 min)
└─ Examples: Dynamo (800,000c, 5,000c/s), Power Grid (2,500,000c, 20,000c/s)

ERA 6: COMPUTING
├─ Cost: 2,000,000 - 20,000,000 coins
├─ Income: 10,000 - 180,000 coins/sec
├─ ROI: 70-1,000 seconds (1-17 min)
├─ Duration: 1,000-10,000 seconds (17-167 min)
└─ Examples: Computer (6,000,000c, 40,000c/s), Data Center (15,000,000c, 120,000c/s)

ERA 7: FUTURISM
├─ Cost: 15,000,000 - 150,000,000 coins
├─ Income: 75,000 - 1,200,000 coins/sec
├─ ROI: 70-1,000 seconds (1-17 min)
├─ Duration: 1,000-10,000 seconds (17-167 min)
└─ Examples: Drone Bay (40,000,000c, 250,000c/s), Fusion Reactor (120,000,000c, 900,000c/s)

ERA 8: INTERSTELLAR
├─ Cost: 100,000,000 - 1,000,000,000 coins
├─ Income: 500,000 - 8,000,000 coins/sec
├─ ROI: 100-2,000 seconds (1.5-33 min)
├─ Duration: 2,000-30,000 seconds (33-500 min)
└─ Examples: Orbital Farm (250,000,000c, 1,500,000c/s), Starport (800,000,000c, 6,000,000c/s)

ERA 9: ARCANA
├─ Cost: 800,000,000 - 8,000,000,000 coins
├─ Income: 4,000,000 - 60,000,000 coins/sec
├─ ROI: 100-2,000 seconds (1.5-33 min)
├─ Duration: 2,000-30,000 seconds (33-500 min)
└─ Examples: Mana Well (2,000,000,000c, 10,000,000c/s), Arcane Tower (6,000,000,000c, 45,000,000c/s)

ERA 10: BEYOND
├─ Cost: 6,000,000,000 - 60,000,000,000 coins
├─ Income: 30,000,000 - 500,000,000 coins/sec
├─ ROI: 100-2,000 seconds (1.5-33 min)
├─ Duration: 2,000-30,000 seconds (33-500 min)
└─ Examples: World Forge (15,000,000,000c, 80,000,000c/s), Reality Printer (50,000,000,000c, 400,000,000c/s)
```

### 🎯 ROI Calculation

**Formula:** `ROI (seconds) = cost / income_per_second`

**Target Ranges:**
- Early Eras (1-4): 30-500 seconds
- Mid Eras (5-7): 70-1,000 seconds
- Late Eras (8-10): 100-2,000 seconds

**Example:**
- Cost: 1,000 coins
- Income: 5 coins/second
- ROI: 1,000 / 5 = 200 seconds (3.3 minutes) ✅ Good for early era

### ⏱️ Operation Duration

**Formula:** `duration = ROI × multiplier`
- Typical multiplier: 5× to 20×
- Common: 10× ROI

**Example:**
- ROI: 200 seconds
- Duration: 200 × 10 = 2,000 seconds (33 minutes)

### 💎 Quality Tier Distribution

| Tier | % of Objects | Income Multiplier | Cost Multiplier | Time Crystal Rate |
|------|--------------|-------------------|-----------------|-------------------|
| Common | 70% | 1.0× | 1.0× | 0 |
| Uncommon | 20% | 1.2× | 1.3× | 0 |
| Rare | 7% | 1.5× | 1.8× | 0.001-0.01 |
| Epic | 2% | 2.0× | 2.5× | 0.01-0.03 |
| Legendary | 1% | 3.0× | 4.0× | 0.03-0.05 |

### 🏛️ Keystone Objects (Special Rules)

**All keystones must follow these rules:**
- `is_keystone: true`
- `cap_per_civ: 1-3` (usually 1)
- `quality_tier: "legendary"` (recommended)
- `era_name:` **NEXT era after inputs** (critical!)

**Keystone List:**

| Name | Recipe | Era Assigned | Unlocks |
|------|--------|--------------|---------|
| Campfire | Fire + Wood | Agriculture | Agriculture |
| Fertilizer | Animal + Plant | Metallurgy | Metallurgy |
| Metal | Ore + Fire | Steam & Industry | Steam & Industry |
| Boiler | Metal + Water | Electric Age | Electric Age |
| Generator | Metal + Magnet | Computing | Computing |
| Microchip | Silicon + Circuit | Futurism | Futurism |
| Nanofab | Assembler + Microchip | Interstellar | Interstellar |
| FTL Relay | Fusion + Crystal | Arcana | Arcana |
| Ley Capacitor | Crystal + Ritual | Beyond | Beyond |
| Seed AI | Quantum Core + Archive | Beyond | (final) |

**Keystone Economy:**
- Cost: Top 25% of era range
- Income: Top 25% of era range
- ROI: Middle of target range (balanced)
- Duration: Long (15× to 20× ROI)
- Retire payout: 40-50% (valuable)
- Global modifiers: YES (powerful auras)

### 📏 Footprint Guidelines

**Small (1-3 tiles):**
- Natural resources
- Basic structures
- Personal items
- Cost: Lower end of era

**Medium (4-8 tiles):**
- Farms & workshops
- Residential buildings
- Small factories
- Cost: Middle of era

**Large (9-15 tiles):**
- Major factories
- Power plants
- Research facilities
- Cost: Upper-middle of era

**Massive (16-20 tiles):**
- Wonders
- Keystones
- Late-era megastructures
- Cost: Top of era range

### 🎲 Variance for Interest

Add 10-20% random variance to avoid predictability:

```
Base Income: 100 coins/sec
Variance: ±15%
Range: 85-115 coins/sec
```

This makes each object feel unique even within the same era.

### 💰 Retire vs Sellback Payout

**Retire Payout (natural end):**
- Common: 20-30%
- Uncommon: 25-35%
- Rare: 30-40%
- Epic: 35-45%
- Legendary/Keystone: 40-50%

**Sellback (manual deletion):**
- Usually 10-15% less than retire payout
- Common: 10-20%
- Uncommon: 15-25%
- Rare: 20-30%
- Epic: 25-35%
- Legendary: 30-40%

This encourages completing the object's lifecycle.

### 🌟 Global Modifier Guidelines

**When to Add:**
- Wonders (always)
- Keystones (usually)
- Power/logistics hubs (sometimes)
- Special buildings (rarely)

**Typical Values:**
- `income_multiplier`: 1.05-1.15 (modest boost)
- `income_multiplier`: 1.20-1.40 (wonders only, max_stacks=1)
- `cost_multiplier`: 0.90-1.00 (rare; usually no change)
- `build_time_multiplier`: 0.85-1.00 (faster is better)
- `operation_duration_multiplier`: 1.00-1.15 (longer is usually better)

**Categories to Boost:**
- Power buildings → boost: factory, mine
- Research buildings → boost: factory, research
- Cultural buildings → boost: housing, cultural
- Wonders → boost: multiple categories

### ⚡ Quick Balance Check

**Is my object balanced?**

✅ ROI within target range for era
✅ Cost fits era's range
✅ Income is integer ≥ 1
✅ Duration is 5-20× ROI
✅ Footprint makes sense for cost
✅ Quality tier matches power level
✅ Keystone? Check era = NEXT after inputs
✅ Keystones have cap_per_civ 1-3

**Common Mistakes:**

❌ Keystone in same era as inputs
❌ Cost too low for era
❌ Income < 1 or fractional
❌ ROI too long (boring) or too short (OP)
❌ Duration too short (not worth placing)
❌ Keystone with cap_per_civ = null
❌ Common object with global modifiers

### 🎮 Synergy Examples

**Good Synergies to Create:**

1. **Resource Chain:**
   - Mine → Ore (intermediate)
   - Ore + Fire → Metal (processed)
   - Metal + Tool → Advanced Item

2. **Support Buildings:**
   - Well → +10% to farms
   - Power Plant → +15% to factories
   - Library → +20% to research

3. **Combo Bonuses:**
   - Farm + Granary → better yield
   - Factory + Rail → faster production
   - Computer + Network → automation

4. **Era Transitions:**
   - Late objects in current era produce inputs for next era
   - Example: Agriculture's "Flax" used in Metallurgy's "Rope"

---

**Need Help?** Reference the full `crafting_recipe.txt` for detailed guidance!
