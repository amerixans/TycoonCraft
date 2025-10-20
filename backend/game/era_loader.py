"""
Era Loader - Single source of truth for all era definitions.

This module loads era configuration from YAML files in the backend/eras/ directory
and provides a clean API for accessing era data throughout the application.
"""

import os
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any
from django.conf import settings


class EraLoader:
    """
    Singleton class that loads and caches era definitions from YAML files.
    """

    _instance = None
    _eras: List[Dict[str, Any]] = None
    _eras_by_name: Dict[str, Dict[str, Any]] = None
    _eras_by_order: Dict[int, Dict[str, Any]] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EraLoader, cls).__new__(cls)
            cls._instance._load_eras()
        return cls._instance

    def _load_eras(self):
        """Load all era YAML files from the eras directory."""
        eras_dir = Path(settings.BASE_DIR) / "eras"

        if not eras_dir.exists():
            raise FileNotFoundError(f"Eras directory not found: {eras_dir}")

        era_files = sorted(eras_dir.glob("*.yaml"))

        if not era_files:
            raise FileNotFoundError(f"No era YAML files found in {eras_dir}")

        self._eras = []
        self._eras_by_name = {}
        self._eras_by_order = {}

        for era_file in era_files:
            with open(era_file, 'r') as f:
                era_data = yaml.safe_load(f)

                # Validate required fields
                required_fields = ['order', 'name', 'crystal_unlock_cost', 'crafting_cost',
                                 'canvas_size', 'stat_ranges', 'prompt_description', 'keystone', 'starters']
                for field in required_fields:
                    if field not in era_data:
                        raise ValueError(f"Era file {era_file} missing required field: {field}")

                self._eras.append(era_data)
                self._eras_by_name[era_data['name']] = era_data
                self._eras_by_order[era_data['order']] = era_data

        # Sort eras by order
        self._eras.sort(key=lambda x: x['order'])

    def get_all_eras(self) -> List[Dict[str, Any]]:
        """Get all eras in order."""
        return self._eras.copy()

    def get_all_era_names(self) -> List[str]:
        """Get list of all era names in order."""
        return [era['name'] for era in self._eras]

    def get_era_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Get era data by name."""
        return self._eras_by_name.get(name)

    def get_era_by_order(self, order: int) -> Optional[Dict[str, Any]]:
        """Get era data by order (1-indexed)."""
        return self._eras_by_order.get(order)

    def get_era_order(self, name: str) -> int:
        """Get the order/index of an era by name (1-indexed)."""
        era = self.get_era_by_name(name)
        return era['order'] if era else -1

    def get_next_era(self, current_era: str) -> Optional[str]:
        """Get the next era name in sequence, or None if at the end."""
        era = self.get_era_by_name(current_era)
        if not era:
            return None

        next_order = era['order'] + 1
        next_era = self.get_era_by_order(next_order)
        return next_era['name'] if next_era else None

    def get_higher_era(self, era_a: str, era_b: str) -> str:
        """Get the higher (more advanced) era between two eras."""
        order_a = self.get_era_order(era_a)
        order_b = self.get_era_order(era_b)

        if order_a < 0:
            return era_b
        if order_b < 0:
            return era_a

        return era_a if order_a >= order_b else era_b

    def get_stat_ranges(self, era_name: str) -> Optional[Dict[str, Any]]:
        """Get stat ranges for a given era."""
        era = self.get_era_by_name(era_name)
        return era['stat_ranges'] if era else None

    def get_combined_stat_ranges(self, era_a: str, era_b: str) -> Dict[str, Any]:
        """
        Get combined stat ranges for two eras (used when crafting).
        Returns the ranges from the higher era.
        """
        higher_era = self.get_higher_era(era_a, era_b)
        return self.get_stat_ranges(higher_era) or {}

    def get_prompt_description(self, era_name: str) -> str:
        """Get the prompt description text for an era."""
        era = self.get_era_by_name(era_name)
        return era['prompt_description'] if era else ""

    def get_all_prompt_descriptions(self) -> str:
        """
        Get all era prompt descriptions concatenated together.
        This is injected into the crafting_recipe.txt template.
        """
        descriptions = []
        for era in self._eras:
            descriptions.append(era['prompt_description'].strip())
        return "\n\n".join(descriptions)

    def get_keystone_definition(self, era_name: str) -> Optional[Dict[str, Any]]:
        """Get keystone definition for an era."""
        era = self.get_era_by_name(era_name)
        return era['keystone'] if era else None

    def get_predefined_recipes(self, era_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get predefined recipes. If era_name is provided, get only that era's recipes.
        Otherwise, get all predefined recipes from all eras.

        Loads recipes from two sources:
        1. keystone.recipe_chain - recipes that lead to the keystone
        2. recipes - general predefined recipes for the era
        """
        recipes = []

        if era_name:
            era = self.get_era_by_name(era_name)
            if era:
                # Load keystone recipes
                if 'keystone' in era and 'recipe_chain' in era['keystone']:
                    recipes.extend(era['keystone']['recipe_chain'])
                # Load general recipes
                if 'recipes' in era:
                    recipes.extend(era['recipes'])
        else:
            # Get all recipes from all eras
            for era in self._eras:
                # Load keystone recipes
                if 'keystone' in era and 'recipe_chain' in era['keystone']:
                    recipes.extend(era['keystone']['recipe_chain'])
                # Load general recipes
                if 'recipes' in era:
                    recipes.extend(era['recipes'])

        return recipes

    def get_starter_objects(self, era_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get starter objects. If era_name is provided, get only that era's starters.
        Otherwise, get all starter objects from all eras.
        """
        starters = []

        if era_name:
            era = self.get_era_by_name(era_name)
            if era and 'starters' in era:
                starters.extend(era['starters'])
        else:
            # Get all starters from all eras
            for era in self._eras:
                if 'starters' in era:
                    starters.extend(era['starters'])

        return starters

    def get_crafting_cost(self, era_name: str) -> int:
        """Get the coin cost to craft objects in a given era."""
        era = self.get_era_by_name(era_name)
        return era['crafting_cost'] if era else 50

    def get_unlock_cost(self, era_name: str) -> int:
        """Get the crystal cost to unlock a given era."""
        era = self.get_era_by_name(era_name)
        return era['crystal_unlock_cost'] if era else 0

    def get_era_costs_dict(self) -> Dict[str, Dict[str, int]]:
        """
        Get a dictionary mapping era names to their costs.
        Returns: {"Era Name": {"crystal_unlock_cost": X, "crafting_cost": Y}}
        """
        costs = {}
        for era in self._eras:
            costs[era['name']] = {
                'crystal_unlock_cost': era['crystal_unlock_cost'],
                'crafting_cost': era['crafting_cost']
            }
        return costs


# Global singleton instance
_era_loader_instance = None


def get_era_loader() -> EraLoader:
    """Get the global EraLoader singleton instance."""
    global _era_loader_instance
    if _era_loader_instance is None:
        _era_loader_instance = EraLoader()
    return _era_loader_instance
