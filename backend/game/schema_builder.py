"""
Schema Builder - Dynamically generates JSON schemas based on era configurations.

This module builds era-aware schemas for OpenAI structured output by injecting
era-specific stat ranges into the base schema template.
"""

import json
import os
from django.conf import settings
from typing import Dict, Any
from .era_loader import get_era_loader


def _read_file_json(directory: str, filename: str) -> Dict[str, Any]:
    """Helper to read a JSON file."""
    path = os.path.join(directory, filename)
    with open(path, 'r') as f:
        return json.load(f)


def build_era_aware_schema(era_a_name: str, era_b_name: str) -> Dict[str, Any]:
    """
    Build an era-aware schema for crafting by injecting stat ranges from the higher era.

    Args:
        era_a_name: Name of first input era
        era_b_name: Name of second input era

    Returns:
        Complete JSON schema dict with era-specific stat ranges
    """
    loader = get_era_loader()
    prompts_dir = os.path.join(settings.BASE_DIR, "prompts")

    # Load the base schema
    base_schema = _read_file_json(prompts_dir, "object_schema.json")

    # Get the combined stat ranges (from the higher era)
    stat_ranges = loader.get_combined_stat_ranges(era_a_name, era_b_name)

    if not stat_ranges:
        # Fallback to base schema if no ranges found
        return base_schema

    # Clone the schema so we don't mutate the original
    schema = json.loads(json.dumps(base_schema))

    # Navigate to the properties section
    if 'schema' in schema and 'properties' in schema['schema']:
        properties = schema['schema']['properties']

        # Update cost range
        if 'cost' in properties and 'cost' in stat_ranges:
            properties['cost']['minimum'] = stat_ranges['cost']['min']
            properties['cost']['maximum'] = stat_ranges['cost']['max']

        # Update income_per_second range
        if 'income_per_second' in properties and 'income_per_second' in stat_ranges:
            properties['income_per_second']['minimum'] = stat_ranges['income_per_second']['min']
            properties['income_per_second']['maximum'] = stat_ranges['income_per_second']['max']

        # Update build_time_sec range
        if 'build_time_sec' in properties and 'build_time_sec' in stat_ranges:
            properties['build_time_sec']['minimum'] = stat_ranges['build_time_sec']['min']
            properties['build_time_sec']['maximum'] = stat_ranges['build_time_sec']['max']

        # Update operation_duration_sec range
        if 'operation_duration_sec' in properties and 'operation_duration_sec' in stat_ranges:
            properties['operation_duration_sec']['minimum'] = stat_ranges['operation_duration_sec']['min']
            properties['operation_duration_sec']['maximum'] = stat_ranges['operation_duration_sec']['max']

        # Update retire_payout.coins_pct range
        if 'retire_payout' in properties and 'properties' in properties['retire_payout']:
            if 'coins_pct' in properties['retire_payout']['properties'] and 'retire_payout_coins_pct' in stat_ranges:
                properties['retire_payout']['properties']['coins_pct']['minimum'] = stat_ranges['retire_payout_coins_pct']['min']
                properties['retire_payout']['properties']['coins_pct']['maximum'] = stat_ranges['retire_payout_coins_pct']['max']

        # Update sellback_pct range
        if 'sellback_pct' in properties and 'sellback_pct' in stat_ranges:
            properties['sellback_pct']['minimum'] = stat_ranges['sellback_pct']['min']
            properties['sellback_pct']['maximum'] = stat_ranges['sellback_pct']['max']

        # Update footprint ranges
        if 'footprint' in properties and 'properties' in properties['footprint']:
            if 'w' in properties['footprint']['properties']:
                properties['footprint']['properties']['w']['minimum'] = stat_ranges.get('footprint_min', 1)
                properties['footprint']['properties']['w']['maximum'] = stat_ranges.get('footprint_max', 20)
            if 'h' in properties['footprint']['properties']:
                properties['footprint']['properties']['h']['minimum'] = stat_ranges.get('footprint_min', 1)
                properties['footprint']['properties']['h']['maximum'] = stat_ranges.get('footprint_max', 20)

        # Update size range
        if 'size' in properties:
            properties['size']['minimum'] = stat_ranges.get('size_min', 0.5)
            properties['size']['maximum'] = stat_ranges.get('size_max', 20)

        # Update time_crystal_cost range
        if 'time_crystal_cost' in properties and 'time_crystal_cost' in stat_ranges:
            properties['time_crystal_cost']['minimum'] = stat_ranges['time_crystal_cost']['min']
            properties['time_crystal_cost']['maximum'] = stat_ranges['time_crystal_cost'].get('max', 0)

        # Update time_crystal_generation range
        if 'time_crystal_generation' in properties and 'time_crystal_generation' in stat_ranges:
            properties['time_crystal_generation']['minimum'] = stat_ranges['time_crystal_generation']['min']
            properties['time_crystal_generation']['maximum'] = stat_ranges['time_crystal_generation'].get('max', 1)

    return schema


def get_base_schema() -> Dict[str, Any]:
    """
    Get the base schema without any era-specific modifications.
    Useful for validation or reference.
    """
    prompts_dir = os.path.join(settings.BASE_DIR, "prompts")
    return _read_file_json(prompts_dir, "object_schema.json")
