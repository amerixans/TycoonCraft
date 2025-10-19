/**
 * Aura helper utilities shared across the frontend.
 */

/**
 * Return true if the object provides at least one global aura modifier.
 */
export const hasAura = (gameObject) =>
  Array.isArray(gameObject?.global_modifiers) &&
  gameObject.global_modifiers.length > 0;

/**
 * Format a multiplier (e.g. 1.08) as a signed percentage string (+8%).
 * Optionally force a fixed number of decimals.
 */
export const formatMultiplier = (multiplier, precision = 0) => {
  if (multiplier === undefined || multiplier === null) return '0%';

  const delta = (Number(multiplier) - 1) * 100;
  const formatted = delta.toFixed(Math.max(0, precision));
  if (Number.isNaN(delta)) return '0%';
  if (delta === 0) return '+0%';
  return `${delta > 0 ? '+' : ''}${formatted.replace(/^-/, '')}%`;
};

/**
 * Build a map of active aura modifiers keyed by category.
 * Mirrors backend logic (build_modifier_map).
 */
export const buildModifierMap = (placedObjects = []) => {
  const modifierMap = new Map();
  const sourceCounts = new Map();

  placedObjects.forEach((placed) => {
    const modifiers = placed?.game_object?.global_modifiers || [];
    if (!modifiers.length) return;

    modifiers.forEach((modifier, idx) => {
      const activeWhen = modifier?.active_when || 'operational';

      if (activeWhen === 'operational' && !placed.is_operational) {
        return;
      }
      if (
        activeWhen === 'placed' &&
        !(placed.is_operational || placed.is_building)
      ) {
        return;
      }
      const affectedCategories = modifier?.affected_categories || [];
      if (!affectedCategories.length) return;

      const maxStacks = Math.max(
        1,
        parseInt(modifier?.max_stacks ?? 1, 10) || 1
      );
      const sourceKey = `${placed.game_object?.id || 'unknown'}:${idx}`;
      const currentStacks = sourceCounts.get(sourceKey) || 0;
      if (currentStacks >= maxStacks) return;
      sourceCounts.set(sourceKey, currentStacks + 1);

      affectedCategories.forEach((category) => {
        if (!modifierMap.has(category)) {
          modifierMap.set(category, []);
        }
        modifierMap.get(category).push({
          stacking:
            modifier?.stacking === 'additive' ? 'additive' : 'multiplicative',
          income_multiplier: Number(modifier?.income_multiplier ?? 1),
          cost_multiplier: Number(modifier?.cost_multiplier ?? 1),
          build_time_multiplier: Number(modifier?.build_time_multiplier ?? 1),
          operation_duration_multiplier: Number(
            modifier?.operation_duration_multiplier ?? 1
          ),
          source: placed.game_object?.object_name || 'Unknown',
          raw: modifier,
        });
      });
    });
  });

  return modifierMap;
};

/**
 * Aggregate modifiers for a single category.
 */
export const calculateCategoryMultipliers = (
  modifierMap,
  category,
  fields = ['income_multiplier', 'build_time_multiplier', 'operation_duration_multiplier', 'cost_multiplier']
) => {
  const modifiers = modifierMap instanceof Map
    ? modifierMap.get(category)
    : modifierMap?.[category];

  const result = {};
  fields.forEach((field) => {
    let total = 1;
    (modifiers || []).forEach((modifier) => {
      const value = Number(modifier?.[field] ?? 1);
      if (modifier.stacking === 'additive') {
        total += value - 1;
      } else {
        total *= value;
      }
    });
    if (total < 0) total = 0;
    result[field] = total;
  });
  return result;
};

/**
 * Summarise all active modifiers for quick HUD display.
 */
export const summariseActiveAuras = (modifierMap) => {
  const entries = [];
  if (modifierMap instanceof Map) {
    modifierMap.forEach((mods, category) => {
      entries.push({
        category,
        income_multiplier: calculateCategoryMultipliers(
          modifierMap,
          category,
          ['income_multiplier']
        ).income_multiplier,
        build_time_multiplier: calculateCategoryMultipliers(
          modifierMap,
          category,
          ['build_time_multiplier']
        ).build_time_multiplier,
        operation_duration_multiplier: calculateCategoryMultipliers(
          modifierMap,
          category,
          ['operation_duration_multiplier']
        ).operation_duration_multiplier,
        sources: mods.map((mod) => ({
          source: mod.source,
          income_multiplier: mod.income_multiplier,
          build_time_multiplier: mod.build_time_multiplier,
          operation_duration_multiplier: mod.operation_duration_multiplier,
          raw: mod.raw,
        })),
      });
    });
  }
  return entries;
};

export const describeAuraModifier = (modifier) => {
  const categories = (modifier?.affected_categories || []).join(', ') || 'All categories';
  const effects = [];

  const pushEffect = (label, value) => {
    const numeric = Number(value ?? 1);
    if (Number.isNaN(numeric) || Math.abs(numeric - 1) < 0.001) return;
    effects.push(`${label} ${formatMultiplier(numeric, Math.abs(numeric - 1) < 0.1 ? 1 : 0)}`);
  };

  pushEffect('Income', modifier?.income_multiplier);
  pushEffect('Build time', modifier?.build_time_multiplier);
  pushEffect('Lifespan', modifier?.operation_duration_multiplier);
  pushEffect('Cost', modifier?.cost_multiplier);

  const activation = modifier?.active_when === 'placed' ? 'Active while placed' : 'Active while operational';
  const maxStacks = Number(modifier?.max_stacks ?? 1);
  const stacking = modifier?.stacking === 'additive' ? 'additive' : 'multiplicative';

  return {
    categories,
    effects,
    activation,
    stacking,
    maxStacks,
  };
};
