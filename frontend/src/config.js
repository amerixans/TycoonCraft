/**
 * Shared game configuration
 *
 * This config is centralized to avoid duplication between backend and frontend.
 * Keep in sync with backend/game/config.py
 */

// Era progression
export const ERAS = [
  'Hunter-Gatherer', 'Agriculture', 'Metallurgy', 'Steam & Industry',
  'Electric Age', 'Computing', 'Futurism', 'Interstellar', 'Arcana', 'Beyond'
];

// Crystal costs to unlock each era
export const ERA_CRYSTAL_COSTS = {
  'Hunter-Gatherer': 0,
  'Agriculture': 10,
  'Metallurgy': 50,
  'Steam & Industry': 250,
  'Electric Age': 1200,
  'Computing': 6000,
  'Futurism': 30000,
  'Interstellar': 150000,
  'Arcana': 800000,
  'Beyond': 4000000,
};

// Coin costs to craft objects in each era
export const ERA_CRAFTING_COSTS = {
  'Hunter-Gatherer': 50 * 2,
  'Agriculture': 250 * 3,
  'Metallurgy': 1250 * 4,
  'Steam & Industry': 6250 * 5,
  'Electric Age': 31250 * 6,
  'Computing': 156250 * 7,
  'Futurism': 781250 * 8,
  'Interstellar': 3906250 * 9,
  'Arcana': 19531250 * 10,
  'Beyond': 97656250 * 11,
};

/**
 * Get the index of an era (0-based from Hunter-Gatherer to Beyond)
 */
export function getEraIndex(eraName) {
  return ERAS.indexOf(eraName);
}

/**
 * Get the next era in sequence, or null if at the end
 */
export function getNextEra(currentEra) {
  const index = ERAS.indexOf(currentEra);
  if (index >= 0 && index < ERAS.length - 1) {
    return ERAS[index + 1];
  }
  return null;
}

/**
 * Get the higher (more advanced) era between two eras
 */
export function getHigherEra(eraA, eraB) {
  const indexA = ERAS.indexOf(eraA);
  const indexB = ERAS.indexOf(eraB);
  if (indexA < 0) return eraB;
  if (indexB < 0) return eraA;
  return ERAS[Math.max(indexA, indexB)];
}

/**
 * Get the coin cost to craft objects in a given era
 */
export function getCraftingCost(eraName) {
  return ERA_CRAFTING_COSTS[eraName] || 50;
}

/**
 * Get the crystal cost to unlock a given era
 */
export function getUnlockCost(eraName) {
  return ERA_CRYSTAL_COSTS[eraName] || 0;
}
