"""Shared game configuration constants.

This module centralizes era definitions, costs, and other game configuration
that would otherwise be duplicated across backend and frontend.
"""

# Era progression
ERAS = [
    "Hunter-Gatherer", "Agriculture", "Metallurgy", "Steam & Industry",
    "Electric Age", "Computing", "Futurism", "Interstellar", "Arcana", "Beyond"
]

# Crystal costs to unlock each era
ERA_CRYSTAL_COSTS = {
    "Hunter-Gatherer": 0,
    "Agriculture": 10,
    "Metallurgy": 50,
    "Steam & Industry": 250,
    "Electric Age": 1200,
    "Computing": 6000,
    "Futurism": 30000,
    "Interstellar": 150000,
    "Arcana": 800000,
    "Beyond": 4000000,
}

# Coin costs to craft objects in each era
ERA_CRAFTING_COSTS = {
    "Hunter-Gatherer": 50 * 2,
    "Agriculture": 250 * 3,
    "Metallurgy": 1250 * 4,
    "Steam & Industry": 6250 * 5,
    "Electric Age": 31250 * 6,
    "Computing": 156250 * 7,
    "Futurism": 781250 * 8,
    "Interstellar": 3906250 * 9,
    "Arcana": 19531250 * 10,
    "Beyond": 97656250 * 11,
}


def get_era_index(era_name):
    """Get the index of an era (0-based from Hunter-Gatherer to Beyond)."""
    try:
        return ERAS.index(era_name)
    except ValueError:
        return -1


def get_next_era(current_era):
    """Get the next era in sequence, or None if at the end."""
    try:
        current_index = ERAS.index(current_era)
        if current_index < len(ERAS) - 1:
            return ERAS[current_index + 1]
    except ValueError:
        pass
    return None


def get_higher_era(era_a, era_b):
    """Get the higher (more advanced) era between two eras."""
    try:
        index_a = ERAS.index(era_a)
        index_b = ERAS.index(era_b)
        return ERAS[max(index_a, index_b)]
    except ValueError:
        return era_a  # fallback


def get_crafting_cost(era_name):
    """Get the coin cost to craft objects in a given era."""
    return ERA_CRAFTING_COSTS.get(era_name, 50)


def get_unlock_cost(era_name):
    """Get the crystal cost to unlock a given era."""
    return ERA_CRYSTAL_COSTS.get(era_name, 0)
