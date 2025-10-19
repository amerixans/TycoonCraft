"""Shared game configuration constants.

This module centralizes era definitions, costs, and other game configuration
that would otherwise be duplicated across backend and frontend.

ERA DEFINITIONS ARE NOW LOADED FROM YAML FILES.
This module provides backward-compatible exports that delegate to era_loader.py
"""

from .era_loader import get_era_loader

# Get the era loader singleton
_loader = get_era_loader()

# Era progression - now loaded from YAML files
ERAS = _loader.get_all_era_names()

# Crystal costs to unlock each era - now loaded from YAML files
ERA_CRYSTAL_COSTS = {
    era['name']: era['crystal_unlock_cost']
    for era in _loader.get_all_eras()
}

# Coin costs to craft objects in each era - now loaded from YAML files
ERA_CRAFTING_COSTS = {
    era['name']: era['crafting_cost']
    for era in _loader.get_all_eras()
}


def get_era_index(era_name):
    """Get the index of an era (0-based from Hunter-Gatherer to Beyond)."""
    order = _loader.get_era_order(era_name)
    return order - 1 if order > 0 else -1


def get_next_era(current_era):
    """Get the next era in sequence, or None if at the end."""
    return _loader.get_next_era(current_era)


def get_higher_era(era_a, era_b):
    """Get the higher (more advanced) era between two eras."""
    return _loader.get_higher_era(era_a, era_b)


def get_crafting_cost(era_name):
    """Get the coin cost to craft objects in a given era."""
    return _loader.get_crafting_cost(era_name)


def get_unlock_cost(era_name):
    """Get the crystal cost to unlock a given era."""
    return _loader.get_unlock_cost(era_name)
