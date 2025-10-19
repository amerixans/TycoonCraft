/**
 * Shared game configuration
 *
 * ERA DEFINITIONS ARE NOW LOADED FROM THE BACKEND API.
 * This module fetches era configuration from /api/era-config/ and caches it.
 */

import { game } from './api';

// Cache key for sessionStorage
const ERA_CONFIG_CACHE_KEY = 'tycooncraft_era_config';

// In-memory cache
let eraConfigCache = null;

/**
 * Load era configuration from API or cache
 * @returns {Promise<Object>} Era configuration object
 */
export async function loadEraConfig() {
  // Return in-memory cache if available
  if (eraConfigCache) {
    return eraConfigCache;
  }

  // Try sessionStorage cache
  const cached = sessionStorage.getItem(ERA_CONFIG_CACHE_KEY);
  if (cached) {
    try {
      eraConfigCache = JSON.parse(cached);
      return eraConfigCache;
    } catch (e) {
      // Invalid cache, will refetch
      sessionStorage.removeItem(ERA_CONFIG_CACHE_KEY);
    }
  }

  // Fetch from API
  try {
    const response = await game.getEraConfig();
    eraConfigCache = response.data;

    // Cache in sessionStorage
    sessionStorage.setItem(ERA_CONFIG_CACHE_KEY, JSON.stringify(eraConfigCache));

    return eraConfigCache;
  } catch (error) {
    console.error('Failed to load era config:', error);

    // Fallback to hardcoded values if API fails
    const fallback = {
      eras: [
        { order: 1, name: 'Hunter-Gatherer', crystal_unlock_cost: 0, crafting_cost: 100 },
        { order: 2, name: 'Agriculture', crystal_unlock_cost: 10, crafting_cost: 750 },
        { order: 3, name: 'Metallurgy', crystal_unlock_cost: 50, crafting_cost: 5000 },
        { order: 4, name: 'Steam & Industry', crystal_unlock_cost: 250, crafting_cost: 31250 },
        { order: 5, name: 'Electric Age', crystal_unlock_cost: 1200, crafting_cost: 187500 },
        { order: 6, name: 'Computing', crystal_unlock_cost: 6000, crafting_cost: 1093750 },
        { order: 7, name: 'Futurism', crystal_unlock_cost: 30000, crafting_cost: 6250000 },
        { order: 8, name: 'Interstellar', crystal_unlock_cost: 150000, crafting_cost: 35156250 },
        { order: 9, name: 'Arcana', crystal_unlock_cost: 800000, crafting_cost: 195312500 },
        { order: 10, name: 'Beyond', crystal_unlock_cost: 4000000, crafting_cost: 1073218750 },
      ]
    };
    eraConfigCache = fallback;
    return fallback;
  }
}

/**
 * Clear the era config cache (useful for testing or manual refresh)
 */
export function clearEraConfigCache() {
  eraConfigCache = null;
  sessionStorage.removeItem(ERA_CONFIG_CACHE_KEY);
}

// Legacy exports for backward compatibility
// These are synchronous but will use cached data

/**
 * Get list of all era names
 * NOTE: Returns cached data or empty array if not loaded yet
 */
export const ERAS = [];

/**
 * Get era crystal costs
 * NOTE: Returns cached data or empty object if not loaded yet
 */
export const ERA_CRYSTAL_COSTS = {};

/**
 * Get era crafting costs
 * NOTE: Returns cached data or empty object if not loaded yet
 */
export const ERA_CRAFTING_COSTS = {};

/**
 * Initialize legacy constants from cache
 * Call this after loadEraConfig() completes
 */
function _updateLegacyExports() {
  if (!eraConfigCache) return;

  // Clear and repopulate arrays/objects
  ERAS.length = 0;
  Object.keys(ERA_CRYSTAL_COSTS).forEach(k => delete ERA_CRYSTAL_COSTS[k]);
  Object.keys(ERA_CRAFTING_COSTS).forEach(k => delete ERA_CRAFTING_COSTS[k]);

  eraConfigCache.eras.forEach(era => {
    ERAS.push(era.name);
    ERA_CRYSTAL_COSTS[era.name] = era.crystal_unlock_cost;
    ERA_CRAFTING_COSTS[era.name] = era.crafting_cost;
  });
}

/**
 * Get the index of an era (0-based from Hunter-Gatherer to Beyond)
 */
export function getEraIndex(eraName) {
  if (!eraConfigCache) return -1;
  const era = eraConfigCache.eras.find(e => e.name === eraName);
  return era ? era.order - 1 : -1;
}

/**
 * Get the next era in sequence, or null if at the end
 */
export function getNextEra(currentEra) {
  if (!eraConfigCache) return null;
  const currentIndex = eraConfigCache.eras.findIndex(e => e.name === currentEra);
  if (currentIndex >= 0 && currentIndex < eraConfigCache.eras.length - 1) {
    return eraConfigCache.eras[currentIndex + 1].name;
  }
  return null;
}

/**
 * Get the higher (more advanced) era between two eras
 */
export function getHigherEra(eraA, eraB) {
  if (!eraConfigCache) return eraA;
  const indexA = eraConfigCache.eras.findIndex(e => e.name === eraA);
  const indexB = eraConfigCache.eras.findIndex(e => e.name === eraB);
  if (indexA < 0) return eraB;
  if (indexB < 0) return eraA;
  return eraConfigCache.eras[Math.max(indexA, indexB)].name;
}

/**
 * Get the coin cost to craft objects in a given era
 */
export function getCraftingCost(eraName) {
  if (!eraConfigCache) return 50;
  const era = eraConfigCache.eras.find(e => e.name === eraName);
  return era ? era.crafting_cost : 50;
}

/**
 * Get the crystal cost to unlock a given era
 */
export function getUnlockCost(eraName) {
  if (!eraConfigCache) return 0;
  const era = eraConfigCache.eras.find(e => e.name === eraName);
  return era ? era.crystal_unlock_cost : 0;
}

// Auto-load configuration when module is imported
// This initializes the cache for synchronous access
loadEraConfig().then(_updateLegacyExports).catch(err => {
  console.error('Failed to auto-load era config:', err);
});
