# views.py

from decimal import Decimal
from datetime import timedelta
import base64
import hashlib
import io
import json
import os
import time

import requests
from PIL import Image
from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .models import (
    GameObject, PlayerProfile, Discovery, PlacedObject,
    CraftingRecipe, RateLimit, EraUnlock, UpgradeKey
)
from .serializers import (
    GameObjectSerializer, PlayerProfileSerializer, DiscoverySerializer,
    PlacedObjectSerializer, UserSerializer, EraUnlockSerializer,
    GameStateImportSerializer
)
from .services.rate_limit import (
    check_daily_rate_limit, check_global_daily_rate_limit,
    increment_daily_rate_limit, increment_global_daily_rate_limit,
    get_daily_rate_limit, check_rate_limit, increment_rate_limit,
    is_admin_user
)
from .config import (
    ERAS, ERA_CRYSTAL_COSTS, ERA_CRAFTING_COSTS,
    get_next_era, get_higher_era, get_crafting_cost, get_unlock_cost
)


# Era progression helper
def get_unlocked_eras(profile):
    """Get list of all eras unlocked by the player."""
    era_unlocks = EraUnlock.objects.filter(player=profile).values_list('era_name', flat=True)
    return list(era_unlocks)


# -----------------------------
# Player coin/tc updates
# -----------------------------

def update_player_coins(player):
    """Calculate and update coins/time crystals from operational placed objects.

    Optimized to cache operational objects and modifiers to reduce database queries
    from O(n²) to O(n).

    Also handles retiring objects that have reached their retirement time, applies
    retirement payouts, and removes them from the player's canvas.
    """
    now = timezone.now()

    # Check for completed buildings and transition them to operational
    completed_buildings = PlacedObject.objects.filter(
        player=player,
        is_building=True,
        build_complete_at__lte=now
    ).select_related("game_object")

    if completed_buildings.exists():
        # Check for keystone objects that just finished building
        for placed in completed_buildings:
            if placed.game_object.is_keystone:
                # Unlock the NEXT era
                era_to_unlock = get_next_era(placed.game_object.era_name)

                if era_to_unlock:  # Make sure there is a next era
                    # Check if not already unlocked
                    if not EraUnlock.objects.filter(player=player, era_name=era_to_unlock).exists():
                        # Unlock the era (no crystal cost when unlocking via keystone)
                        EraUnlock.objects.create(player=player, era_name=era_to_unlock)
                        player.current_era = era_to_unlock
                        player.save()

                        # Give starter objects for the newly unlocked era
                        starter_objects = GameObject.objects.filter(is_starter=True, era_name=era_to_unlock)
                        for obj in starter_objects:
                            Discovery.objects.get_or_create(player=player, game_object=obj)

        completed_buildings.update(
            is_building=False,
            is_operational=True
        )

    # **NEW: Check for retiring objects and apply payouts**
    retiring_objects = PlacedObject.objects.filter(
        player=player,
        is_operational=True,
        retire_at__lte=now
    ).select_related("game_object")

    for placed in retiring_objects:
        # Calculate retirement payout
        original_cost = placed.game_object.cost
        retire_payout_pct = Decimal(str(placed.game_object.retire_payout_coins_pct))
        retirement_payout = original_cost * retire_payout_pct

        # Add payout to player coins
        player.coins += retirement_payout

        # Mark object as retired (set is_operational to False)
        # This allows frontend to show retirement animation before deletion
        placed.is_operational = False
        placed.save()

    time_elapsed = (now - player.last_coin_update).total_seconds()

    # Fetch all operational objects once and cache them
    # Filter for objects that either haven't been assigned a retire_at time yet (NULL)
    # or haven't reached their retirement time yet
    operational_objects = list(
        PlacedObject.objects
        .filter(player=player, is_operational=True)
        .filter(Q(retire_at__isnull=True) | Q(retire_at__gt=now))
        .select_related("game_object")
    )

    total_income = Decimal("0")
    total_crystals = Decimal("0")

    # Build modifier map: for each category, collect all active modifiers
    # This avoids looping through all objects for each object
    modifier_map = {}  # category -> list of (income_multiplier, stacking_type)

    for mod_obj in operational_objects:
        modifiers = mod_obj.game_object.global_modifiers or []
        for mod in modifiers:
            if mod.get("active_when") == "operational":
                affected_categories = mod.get("affected_categories", [])
                income_mult = Decimal(str(mod.get("income_multiplier", 1)))
                stacking = mod.get("stacking", "multiplicative")

                for category in affected_categories:
                    if category not in modifier_map:
                        modifier_map[category] = []
                    modifier_map[category].append((income_mult, stacking))

    # Calculate income for each operational object, using the modifier map
    for placed in operational_objects:
        income_multiplier = Decimal("1")

        # Apply modifiers from the map for this object's category
        if placed.game_object.category in modifier_map:
            for income_mult, stacking in modifier_map[placed.game_object.category]:
                if stacking == "multiplicative":
                    income_multiplier *= income_mult
                else:
                    income_multiplier += (income_mult - Decimal("1"))

        total_income += placed.game_object.income_per_second * income_multiplier
        total_crystals += placed.game_object.time_crystal_generation

    coins_earned = total_income * Decimal(str(time_elapsed))
    crystals_earned = total_crystals * Decimal(str(time_elapsed))

    player.coins += coins_earned
    player.time_crystals += crystals_earned
    player.last_coin_update = now
    player.save()

    return coins_earned, crystals_earned


def validate_predefined_match(game_object, predefined_overrides):
    """
    Check if existing game object matches predefined specifications.
    Returns True if all predefined fields match, False otherwise.
    """
    if not predefined_overrides:
        return True
    
    for key, expected_value in predefined_overrides.items():
        # Handle nested dict fields that need special mapping to model fields
        if key == 'retire_payout' and isinstance(expected_value, dict):
            # Handle retire_payout as a nested dict
            for sub_key, sub_value in expected_value.items():
                if sub_key == 'coins_pct':
                    actual_value = game_object.retire_payout_coins_pct
                    actual_normalized = _normalize_value(actual_value)
                    expected_normalized = _normalize_value(sub_value)
                    if not _values_equal(actual_normalized, expected_normalized):
                        return False
            continue
        
        if key == 'footprint' and isinstance(expected_value, dict):
            # Handle footprint as a nested dict
            for sub_key, sub_value in expected_value.items():
                field_name = f"footprint_{sub_key}"
                actual_value = getattr(game_object, field_name, None)
                actual_normalized = _normalize_value(actual_value)
                expected_normalized = _normalize_value(sub_value)
                if not _values_equal(actual_normalized, expected_normalized):
                    return False
            continue
        
        # Get actual value from game object for simple fields
        if '.' in key:
            # Handle dotted notation (legacy support)
            parts = key.split('.')
            if parts[0] == 'retire_payout':
                if parts[1] == 'coins_pct':
                    actual_value = game_object.retire_payout_coins_pct
                else:
                    continue
            elif parts[0] == 'footprint':
                field_name = f"footprint_{parts[1]}"
                actual_value = getattr(game_object, field_name, None)
            else:
                # Try to get from dict/JSON field
                parent = getattr(game_object, parts[0], None)
                if isinstance(parent, dict):
                    actual_value = parent.get(parts[1])
                else:
                    continue
        else:
            actual_value = getattr(game_object, key, None)
        
        # Normalize values for comparison
        actual_normalized = _normalize_value(actual_value)
        expected_normalized = _normalize_value(expected_value)
        
        # Compare with appropriate method
        if not _values_equal(actual_normalized, expected_normalized):
            return False
    
    return True


def _normalize_value(value):
    """Normalize a value for comparison."""
    # Convert Decimal to float (but not bool, since bool is a subclass of int)
    if hasattr(value, '__float__') and not isinstance(value, bool):
        return float(value)
    # Keep None, lists, dicts, strings, bools as-is
    return value


def _values_equal(actual, expected):
    """Check if two values are equal, with special handling for floats."""
    # Handle None
    if actual is None and expected is None:
        return True
    if actual is None or expected is None:
        return False
    
    # Handle numeric comparisons with tolerance for floating point precision
    if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        # Use small epsilon for float comparison to handle precision issues
        return abs(float(actual) - float(expected)) < 1e-9
    
    # Handle list comparison
    if isinstance(actual, list) and isinstance(expected, list):
        if len(actual) != len(expected):
            return False
        return all(_values_equal(a, e) for a, e in zip(actual, expected))
    
    # Handle dict comparison
    if isinstance(actual, dict) and isinstance(expected, dict):
        if set(actual.keys()) != set(expected.keys()):
            return False
        return all(_values_equal(actual.get(k), expected.get(k)) for k in actual.keys())
    
    # Direct comparison for everything else (strings, bools, etc.)
    return actual == expected


# -----------------------------
# Predefined recipes
# -----------------------------

_PREDEFINED_RECIPES_CACHE = None

def load_predefined_recipes():
    """Load predefined recipes from JSON file."""
    global _PREDEFINED_RECIPES_CACHE
    if _PREDEFINED_RECIPES_CACHE is not None:
        return _PREDEFINED_RECIPES_CACHE
    
    recipes_path = os.path.join(settings.BASE_DIR, "prompts", "predefined_recipes.json")
    if not os.path.exists(recipes_path):
        _PREDEFINED_RECIPES_CACHE = []
        return []
    
    with open(recipes_path, "r", encoding="utf-8") as f:
        _PREDEFINED_RECIPES_CACHE = json.load(f)
    return _PREDEFINED_RECIPES_CACHE


def get_predefined_recipe(object_a, object_b):
    """Check if there's a predefined recipe for this combination."""
    recipes = load_predefined_recipes()
    
    for recipe in recipes:
        # Check both orderings
        if ((recipe["input_a"] == object_a.object_name and recipe["input_b"] == object_b.object_name) or
            (recipe["input_a"] == object_b.object_name and recipe["input_b"] == object_a.object_name)):
            return recipe.get("output", {})
    
    return None


# -----------------------------
# OpenAI helpers
# -----------------------------

OPENAI_BASE_URL = "https://api.openai.com"

def _require_openai_key():
    api_key = getattr(settings, "OPENAI_API_KEY", None)
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured in settings.")
    return api_key

def _openai_headers():
    return {
        "Authorization": f"Bearer {_require_openai_key()}",
        "Content-Type": "application/json",
    }

def _read_file_text(*parts):
    with open(os.path.join(*parts), "r", encoding="utf-8") as f:
        return f.read()

def _read_file_json(*parts):
    with open(os.path.join(*parts), "r", encoding="utf-8") as f:
        return json.load(f)

def _extract_responses_text(res_json):
    """
    Robustly extract the assistant's text from a Responses API REST response.
    The SDK offers response.output_text, but here we parse the raw JSON.
    """
    # 1) Direct convenience field (if present)
    if isinstance(res_json, dict) and res_json.get("output_text"):
        return res_json["output_text"]

    # 2) "output" array with messages/content blocks
    output = res_json.get("output")
    if isinstance(output, list):
        # Find any content block with text
        for item in output:
            # Newer shape: type: "message" + content: [{type: "...", text: "..."}]
            content = item.get("content")
            if isinstance(content, list):
                for c in content:
                    if c.get("type") in ("output_text", "input_text", "text") and c.get("text"):
                        return c["text"]
            # Older possible shapes
            if isinstance(item, dict):
                if item.get("type") in ("output_text", "text") and item.get("text"):
                    return item["text"]

    # 3) "content" (some early payloads)
    content = res_json.get("content")
    if isinstance(content, list):
        for c in content:
            if c.get("type") in ("output_text", "text") and c.get("text"):
                return c["text"]
    if isinstance(content, str):
        return content

    # 4) Nothing worked
    raise ValueError("Unable to parse text from OpenAI Responses API response.")

def call_openai_crafting(object_a, object_b, unlocked_eras, current_era, predefined_overrides=None):
    """
    Call OpenAI (Responses API) to generate a new object definition via structured output.
    Uses server-to-server endpoint: POST /v1/responses
    
    predefined_overrides: dict of field values that MUST be respected in the output
    """

    prompts_dir = os.path.join(settings.BASE_DIR, "prompts")
    prompt_template = _read_file_text(prompts_dir, "crafting_recipe.txt")
    capsule_schema = _read_file_json(prompts_dir, "object_capsule.json")  # present for ref; not directly posted
    object_schema = _read_file_json(prompts_dir, "object_schema.json")

    # Build capsules
    capsule_a = {
        "object_name": object_a.object_name,
        "era_name": object_a.era_name,
        "category": object_a.category,
        "is_keystone": object_a.is_keystone,
        "quality_tier": object_a.quality_tier,
        "notes": f"Income: {object_a.income_per_second}/s, Cost: {object_a.cost}",
    }
    capsule_b = {
        "object_name": object_b.object_name,
        "era_name": object_b.era_name,
        "category": object_b.category,
        "is_keystone": object_b.is_keystone,
        "quality_tier": object_b.quality_tier,
        "notes": f"Income: {object_b.income_per_second}/s, Cost: {object_b.cost}",
    }

    # Determine the higher era between the two objects
    higher_era = get_higher_era(object_a.era_name, object_b.era_name)
    next_era = get_next_era(higher_era)
    
    # Build era context for the prompt
    era_context = f"""
PLAYER ERA CONTEXT:
• Current Era: {current_era}
• Unlocked Eras: {', '.join(unlocked_eras)}
• Higher Input Era: {higher_era}
• Next Potential Era: {next_era if next_era else 'None (at max era)'}

CRITICAL ERA ASSIGNMENT RULES:
1. For KEYSTONE objects (is_keystone: true):
   - The object MUST be assigned to the SAME era as the higher input era
   - Example: If combining Agriculture objects, the keystone should be "Agriculture"
   - Placing this keystone will unlock the NEXT era for the player
   
2. For REGULAR objects (is_keystone: false):
   - The object MUST be assigned to the higher era of the two inputs
   - Example: If combining Hunter-Gatherer + Agriculture, result is Agriculture
   - Never assign to an era beyond the player's highest unlocked era + 1
   
3. Keystone identification:
   - Check the era definitions for "Keystone to Unlock" entries
   - Only set is_keystone: true if the crafted object matches that keystone concept
   - Example: "Campfire" for Hunter-Gatherer, "Fertilizer" for Agriculture, etc.
"""

    # Add predefined constraints if any
    if predefined_overrides:
        constraints_text = "\n\nPREDEFINED CONSTRAINTS (MUST BE RESPECTED):\n"
        constraints_text += "The following fields have been predefined and MUST match exactly:\n"
        for key, value in predefined_overrides.items():
            constraints_text += f"  • {key}: {json.dumps(value)}\n"
        constraints_text += "\nAll other fields should be generated normally following the game rules.\n"
        era_context += constraints_text

    # Fill prompt
    prompt = (
        prompt_template
        .replace("{{object_a_capsule}}", json.dumps(capsule_a, indent=2))
        .replace("{{object_b_capsule}}", json.dumps(capsule_b, indent=2))
    ) + "\n" + era_context

    # Build payload for structured output
    payload = {
        "model": "gpt-5-mini",
        "input": prompt,
        "reasoning": {"effort": "medium"},
        "text": {
            "format": {
                "type": "json_schema",
                "name": "crafting_object",
                # ⬇️ Use the actual JSON Schema, not the wrapper
                "schema": object_schema["schema"],
                "strict": True
            }
        }
    }

    # Count against limits before calling (as your code already did)
    # Call
    resp = requests.post(
        f"{OPENAI_BASE_URL}/v1/responses",
        headers=_openai_headers(),
        json=payload,
        timeout=60,
    )
    if resp.status_code != 200:
        raise Exception(f"OpenAI API error: {resp.text}")

    res_json = resp.json()
    text = _extract_responses_text(res_json)

    try:
        parsed = json.loads(text)
    except Exception as e:
        raise ValueError(f"Failed to parse JSON from model output: {e}\nRaw: {text[:500]}")

    # Apply predefined overrides to the result
    if predefined_overrides:
        for key, value in predefined_overrides.items():
            # Handle nested fields like retire_payout.coins_pct
            if '.' in key:
                parts = key.split('.')
                target = parsed
                for part in parts[:-1]:
                    if part not in target:
                        target[part] = {}
                    target = target[part]
                target[parts[-1]] = value
            else:
                parsed[key] = value

    return parsed


def _compress_image(image_bytes):
    """
    Compress image bytes using PIL while maintaining quality.

    Uses the IMAGE_COMPRESSION_QUALITY setting from settings.py.
    Returns compressed image as PNG bytes.
    """
    try:
        from PIL import Image
        import io

        # Load image from bytes
        img = Image.open(io.BytesIO(image_bytes))

        # Convert RGBA to RGB if needed (PNG to PNG with quality setting)
        if img.mode in ('RGBA', 'LA', 'P'):
            # Create white background for transparency
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
            img = background

        # Get compression quality from settings
        quality = getattr(settings, 'IMAGE_COMPRESSION_QUALITY', 85)

        # Compress and save to bytes
        output = io.BytesIO()
        img.save(output, format='PNG', optimize=True, quality=quality)
        return output.getvalue()
    except ImportError:
        # If PIL not available, return original bytes
        return image_bytes


def call_openai_image(object_name):
    """
    Call OpenAI Images API with gpt-image-1-mini.
    Uses POST /v1/images (returns base64 in data[0].b64_json).

    Image is automatically compressed after generation using settings.IMAGE_COMPRESSION_QUALITY.
    """

    prompts_dir = os.path.join(settings.BASE_DIR, "prompts")
    prompt_template = _read_file_text(prompts_dir, "image_prompt.txt")
    prompt = prompt_template.replace("{{object_final_name}}", object_name)

    payload = {
        "model": "gpt-image-1-mini",
        "prompt": prompt,
        "size": "1024x1024",
        "background": "transparent",
        "quality": "medium",
    }

    resp = requests.post(
        f"{OPENAI_BASE_URL}/v1/images/generations",
        headers=_openai_headers(),
        json=payload,
        timeout=120,
    )
    if resp.status_code != 200:
        raise Exception(f"OpenAI Image API error: {resp.text}")

    res = resp.json()
    data = (res.get("data") or [{}])
    b64 = data[0].get("b64_json")
    if not b64:
        raise Exception("Image API: missing b64_json in response")

    image_bytes = base64.b64decode(b64)

    # Compress the image before returning
    compressed_bytes = _compress_image(image_bytes)
    return compressed_bytes


# -----------------------------
# Auth & profile endpoints
# -----------------------------

@api_view(["POST"])
@permission_classes([AllowAny])
def register(request):
    """Register a new user."""
    username = request.data.get("username")
    password = request.data.get("password")
    email = request.data.get("email", "")

    if not username or not password:
        return Response({"error": "Username and password required"}, status=status.HTTP_400_BAD_REQUEST)

    if User.objects.filter(username=username).exists():
        return Response({"error": "Username already exists"}, status=status.HTTP_400_BAD_REQUEST)

    user = User.objects.create_user(username=username, password=password, email=email)

    profile = PlayerProfile.objects.create(
        user=user,
        coins=getattr(settings, "STARTING_COINS", Decimal("0")),
        is_pro=False
    )

    # Unlock first era
    EraUnlock.objects.create(player=profile, era_name="Hunter-Gatherer")

    # Give starter objects for Hunter-Gatherer era
    starter_objects = GameObject.objects.filter(is_starter=True, era_name="Hunter-Gatherer")
    for obj in starter_objects:
        Discovery.objects.create(player=profile, game_object=obj)

    login(request, user)

    return Response({
        "user": UserSerializer(user).data,
        "profile": PlayerProfileSerializer(profile).data
    }, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([AllowAny])
@ensure_csrf_cookie
def login_view(request):
    """Login user."""
    username = request.data.get("username")
    password = request.data.get("password")

    user = authenticate(username=username, password=password)
    if user is None:
        return Response({"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)

    login(request, user)
    profile, _ = PlayerProfile.objects.get_or_create(user=user)

    return Response({
        "user": UserSerializer(user).data,
        "profile": PlayerProfileSerializer(profile).data
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout_view(request):
    """Logout user."""
    logout(request)
    return Response({"success": True})


# -----------------------------
# Game state endpoints
# -----------------------------

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_object_catalog(request):
    """Get static GameObject catalog (cacheable, rarely changes).

    This endpoint serves all game objects and can be cached on the client side
    to reduce polling payload and database load.
    """
    all_objects = GameObject.objects.all()
    return Response({
        "all_objects": GameObjectSerializer(all_objects, many=True).data,
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def game_state(request):
    """Get player-specific game state (excluding static catalog).

    Optimized to exclude the large all_objects catalog which is served
    separately and can be cached by the client.
    """
    update_player_coins(request.user.profile)

    profile = request.user.profile
    discoveries = Discovery.objects.filter(player=profile).select_related("game_object")
    placed_objects = PlacedObject.objects.filter(player=profile).select_related("game_object")
    era_unlocks = EraUnlock.objects.filter(player=profile)

    return Response({
        "profile": PlayerProfileSerializer(profile).data,
        "discoveries": DiscoverySerializer(discoveries, many=True).data,
        "placed_objects": PlacedObjectSerializer(placed_objects, many=True).data,
        "era_unlocks": EraUnlockSerializer(era_unlocks, many=True).data,
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def craft_objects(request):
    """Craft two objects together (may call OpenAI if it's a new recipe)."""
    object_a_id = request.data.get("object_a_id")
    object_b_id = request.data.get("object_b_id")

    if not object_a_id or not object_b_id:
        return Response({"error": "Both objects required"}, status=status.HTTP_400_BAD_REQUEST)

    profile = request.user.profile

    # Check daily user rate limit (tier-based)
    allowed, remaining = check_daily_rate_limit(request.user)
    if not allowed:
        limit = get_daily_rate_limit(request.user)
        return Response({
            "error": f"You have reached your discovery limit for the day. It will reset tomorrow.",
            "limit": limit,
            "reset_at": "tomorrow at midnight UTC"
        }, status=status.HTTP_429_TOO_MANY_REQUESTS)

    # Check global daily rate limit (4000 per day across all users)
    allowed_global_daily, _ = check_global_daily_rate_limit()
    if not allowed_global_daily:
        global_limit = getattr(settings, "RATE_LIMIT_DAILY_GLOBAL", 4000)
        return Response({
            "error": f"Server has reached its daily discovery limit. Please try again tomorrow.",
            "global_limit": global_limit,
            "reset_at": "tomorrow at midnight UTC"
        }, status=status.HTTP_429_TOO_MANY_REQUESTS)

    # Check legacy global rate limit (per-minute for system stability)
    allowed_global, _ = check_rate_limit(None, "global_api")
    if not allowed_global:
        return Response({"error": "Server is temporarily busy. Please try again in a moment."}, status=status.HTTP_429_TOO_MANY_REQUESTS)

    try:
        object_a = GameObject.objects.get(id=object_a_id)
        object_b = GameObject.objects.get(id=object_b_id)
    except GameObject.DoesNotExist:
        return Response({"error": "Object not found"}, status=status.HTTP_404_NOT_FOUND)

    # Ensure player knows both
    if not Discovery.objects.filter(player=profile, game_object=object_a).exists():
        return Response({"error": "You have not discovered object A"}, status=status.HTTP_403_FORBIDDEN)
    if not Discovery.objects.filter(player=profile, game_object=object_b).exists():
        return Response({"error": "You have not discovered object B"}, status=status.HTTP_403_FORBIDDEN)

    # Validate that both objects are from the same era
    if object_a.era_name != object_b.era_name:
        return Response({
            "error": f"Cannot combine items from different eras. {object_a.object_name} is from {object_a.era_name}, but {object_b.object_name} is from {object_b.era_name}. Only items from the same era can be combined.",
            "error_type": "era_mismatch",
            "object_a_era": object_a.era_name,
            "object_b_era": object_b.era_name
        }, status=status.HTTP_400_BAD_REQUEST)

    # Normalize order
    if object_a.id > object_b.id:
        object_a, object_b = object_b, object_a

    # Calculate crafting cost based on higher era
    higher_era = get_higher_era(object_a.era_name, object_b.era_name)
    crafting_cost = Decimal(str(ERA_CRAFTING_COSTS.get(higher_era, 50)))
    
    # Check if player has enough coins (allow admin to go negative)
    update_player_coins(profile)
    if profile.coins < crafting_cost and not is_admin_user(request.user):
        return Response({
            "error": f"Insufficient coins. Crafting costs {crafting_cost} coins (based on {higher_era} era)."
        }, status=status.HTTP_400_BAD_REQUEST)

    # Check for predefined recipe first
    predefined_overrides = get_predefined_recipe(object_a, object_b)
    
    # Pre-existing recipe?
    existing_recipe = CraftingRecipe.objects.filter(object_a=object_a, object_b=object_b).select_related("result").first()
    if existing_recipe:
        result_obj = existing_recipe.result
        
        # Validate against predefined recipe if one exists
        if predefined_overrides and not validate_predefined_match(result_obj, predefined_overrides):
            # Specs don't match - delete old object and regenerate
            result_obj.delete()
            existing_recipe.delete()
            # Continue to generation below (fall through to create new recipe)
        else:
            # Recipe exists and matches predefined specs (or no predefined specs)
            # Deduct crafting cost
            profile.coins -= crafting_cost
            profile.save()
            
            # Check if player already discovered this
            discovery, created = Discovery.objects.get_or_create(player=profile, game_object=result_obj)
            
            # Return the existing recipe result without calling OpenAI
            return Response({
                "object": GameObjectSerializer(result_obj).data,
                "newly_discovered": created,
                "newly_created": False,
                "crafting_cost": float(crafting_cost),
                "used_existing_recipe": True,
            })

    # New recipe → count, then call OpenAI OUTSIDE DB transaction
    increment_rate_limit(profile, "user_discovery")
    increment_rate_limit(None, "global_api")
    increment_daily_rate_limit(request.user)
    increment_global_daily_rate_limit()

    # Get player's era context
    unlocked_eras = get_unlocked_eras(profile)
    current_era = profile.current_era

    # predefined_overrides already retrieved above

    try:
        obj_data = call_openai_crafting(object_a, object_b, unlocked_eras, current_era, predefined_overrides)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_502_BAD_GATEWAY)

    # Check if an object with this name already exists (handle duplicates gracefully)
    existing_obj = GameObject.objects.filter(object_name=obj_data.get("object_name")).first()
    
    if existing_obj:
        # Object with this name already exists
        # Check if this player already discovered it
        already_discovered = Discovery.objects.filter(player=profile, game_object=existing_obj).exists()
        
        if already_discovered:
            # Player already knows this object - just inform them and save the recipe
            profile.coins -= crafting_cost
            profile.save()
            
            # Create recipe linking these inputs to the existing result (if not already exists)
            CraftingRecipe.objects.get_or_create(
                object_a=object_a,
                object_b=object_b,
                defaults={
                    "result": existing_obj,
                    "discovered_by": request.user,
                }
            )
            
            return Response({
                "object": GameObjectSerializer(existing_obj).data,
                "newly_discovered": False,
                "newly_created": False,
                "message": f"That combination creates {existing_obj.object_name}, which you have already discovered!",
                "crafting_cost": float(crafting_cost),
            })
        else:
            # Player hasn't discovered it yet - link recipe and mark as discovered
            try:
                with transaction.atomic():
                    # Create recipe linking these inputs to the existing result
                    CraftingRecipe.objects.create(
                        object_a=object_a,
                        object_b=object_b,
                        result=existing_obj,
                        discovered_by=request.user,
                    )

                    # Deduct crafting cost
                    profile.coins -= crafting_cost
                    profile.save()

                    # Mark as discovered for this player
                    Discovery.objects.create(player=profile, game_object=existing_obj)

                    return Response({
                        "object": GameObjectSerializer(existing_obj).data,
                        "newly_discovered": True,
                        "newly_created": False,
                        "duplicate_name_handled": True,
                        "crafting_cost": float(crafting_cost),
                    }, status=status.HTTP_201_CREATED)

            except Exception as e:
                return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # Prepare image (second API call) and count it
    increment_rate_limit(None, "global_api")
    try:
        image_bytes = call_openai_image(obj_data.get("object_name", "New Object"))
    except Exception as e:
        return Response({"error": f"Image generation failed: {e}"}, status=status.HTTP_502_BAD_GATEWAY)

    # Create DB records atomically; write image file within this block using bytes already in memory
    try:
        with transaction.atomic():
            new_obj = GameObject.objects.create(
                object_name=obj_data["object_name"],
                era_name=obj_data["era_name"],
                is_keystone=obj_data.get("is_keystone", False),
                category=obj_data["category"],
                quality_tier=obj_data.get("quality_tier", "common"),
                cost=Decimal(str(obj_data["cost"])),
                time_crystal_cost=Decimal(str(obj_data.get("time_crystal_cost", 0))),
                income_per_second=Decimal(str(obj_data["income_per_second"])),
                time_crystal_generation=Decimal(str(obj_data.get("time_crystal_generation", 0))),
                build_time_sec=obj_data.get("build_time_sec", 0),
                operation_duration_sec=obj_data["operation_duration_sec"],
                retire_payout_coins_pct=Decimal(str(obj_data["retire_payout"]["coins_pct"])),
                sellback_pct=Decimal(str(obj_data["sellback_pct"])),
                cap_per_civ=obj_data.get("cap_per_civ"),
                footprint_w=obj_data["footprint"]["w"],
                footprint_h=obj_data["footprint"]["h"],
                size=Decimal(str(obj_data["size"])),
                global_modifiers=obj_data.get("global_modifiers", []),
                flavor_text=obj_data.get("flavor_text", ""),
                created_by=request.user,
            )

            # Save image to media
            media_dir = os.path.join(settings.MEDIA_ROOT, "objects")
            os.makedirs(media_dir, exist_ok=True)
            image_hash = hashlib.md5(f"{object_a.id}{object_b.id}".encode()).hexdigest()
            image_filename = f"{image_hash}.png"
            image_path = os.path.join(media_dir, image_filename)

            with open(image_path, "wb") as f:
                f.write(image_bytes)

            new_obj.image_path = f"/media/objects/{image_filename}"
            new_obj.save()

            CraftingRecipe.objects.create(
                object_a=object_a,
                object_b=object_b,
                result=new_obj,
                discovered_by=request.user,
            )

            # Deduct crafting cost
            profile.coins -= crafting_cost
            profile.save()

            Discovery.objects.create(player=profile, game_object=new_obj)

            return Response({
                "object": GameObjectSerializer(new_obj).data,
                "newly_discovered": True,
                "newly_created": True,
                "crafting_cost": float(crafting_cost),
            }, status=status.HTTP_201_CREATED)

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def place_object(request):
    """Place an object on the canvas."""
    object_id = request.data.get("object_id")
    x = request.data.get("x")
    y = request.data.get("y")

    if object_id is None or x is None or y is None:
        return Response({"error": "object_id, x, and y required"}, status=status.HTTP_400_BAD_REQUEST)

    profile = request.user.profile
    update_player_coins(profile)

    try:
        game_object = GameObject.objects.get(id=object_id)
    except GameObject.DoesNotExist:
        return Response({"error": "Object not found"}, status=status.HTTP_404_NOT_FOUND)

    if not Discovery.objects.filter(player=profile, game_object=game_object).exists():
        return Response({"error": "Object not discovered"}, status=status.HTTP_403_FORBIDDEN)

    # Allow admin to go negative on coins when placing objects
    if profile.coins < game_object.cost and not is_admin_user(request.user):
        return Response({"error": "Insufficient coins"}, status=status.HTTP_400_BAD_REQUEST)

    if profile.time_crystals < game_object.time_crystal_cost:
        return Response({"error": "Insufficient time crystals"}, status=status.HTTP_400_BAD_REQUEST)

    if game_object.cap_per_civ:
        count = PlacedObject.objects.filter(player=profile, game_object=game_object).count()
        if count >= game_object.cap_per_civ:
            return Response({"error": "Placement cap reached for this object"}, status=status.HTTP_400_BAD_REQUEST)

    # Simple overlap check
    x = int(x)
    y = int(y)
    for placed in PlacedObject.objects.filter(player=profile).select_related("game_object"):
        if (
            x < placed.x + placed.game_object.footprint_w and
            x + game_object.footprint_w > placed.x and
            y < placed.y + placed.game_object.footprint_h and
            y + game_object.footprint_h > placed.y
        ):
            return Response({"error": "Space occupied"}, status=status.HTTP_400_BAD_REQUEST)

    # Bounds (adjust if your canvas differs)
    if x < 0 or y < 0 or x + game_object.footprint_w > 1000 or y + game_object.footprint_h > 1000:
        return Response({"error": "Out of bounds"}, status=status.HTTP_400_BAD_REQUEST)

    # Deduct cost
    profile.coins -= game_object.cost
    profile.time_crystals -= game_object.time_crystal_cost
    profile.save()

    now = timezone.now()
    build_complete = now + timedelta(seconds=game_object.build_time_sec)
    retire_at = build_complete + timedelta(seconds=game_object.operation_duration_sec)

    placed = PlacedObject.objects.create(
        player=profile,
        game_object=game_object,
        x=x,
        y=y,
        placed_at=now,
        build_complete_at=build_complete,
        retire_at=retire_at,
        is_building=game_object.build_time_sec > 0,
        is_operational=game_object.build_time_sec == 0,
    )

    response_data = PlacedObjectSerializer(placed).data
    return Response(response_data, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def remove_object(request):
    """Remove a placed object and refund coins."""
    placed_id = request.data.get("placed_id")
    if not placed_id:
        return Response({"error": "placed_id required"}, status=status.HTTP_400_BAD_REQUEST)

    profile = request.user.profile
    update_player_coins(profile)

    try:
        placed = PlacedObject.objects.get(id=placed_id, player=profile)
    except PlacedObject.DoesNotExist:
        return Response({"error": "Placed object not found"}, status=status.HTTP_404_NOT_FOUND)

    refund = placed.game_object.cost * placed.game_object.sellback_pct
    profile.coins += refund
    profile.save()

    placed.delete()

    return Response({"refund": float(refund), "coins": float(profile.coins)})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def unlock_era(request):
    """Unlock the next era."""
    era_name = request.data.get("era_name")
    if not era_name or era_name not in ERAS:
        return Response({"error": "Invalid era"}, status=status.HTTP_400_BAD_REQUEST)

    profile = request.user.profile
    update_player_coins(profile)

    if EraUnlock.objects.filter(player=profile, era_name=era_name).exists():
        return Response({"error": "Era already unlocked"}, status=status.HTTP_400_BAD_REQUEST)

    cost = ERA_CRYSTAL_COSTS.get(era_name, 0)
    if profile.time_crystals < cost:
        return Response({"error": "Insufficient time crystals"}, status=status.HTTP_400_BAD_REQUEST)

    profile.time_crystals -= cost
    profile.current_era = era_name
    profile.save()

    unlock = EraUnlock.objects.create(player=profile, era_name=era_name)

    # Give starter objects for the newly unlocked era
    starter_objects = GameObject.objects.filter(is_starter=True, era_name=era_name)
    for obj in starter_objects:
        Discovery.objects.get_or_create(player=profile, game_object=obj)

    return Response({
        "era_unlock": EraUnlockSerializer(unlock).data,
        "profile": PlayerProfileSerializer(profile).data
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def export_game(request):
    """Export game state as JSON."""
    profile = request.user.profile
    update_player_coins(profile)

    discoveries = Discovery.objects.filter(player=profile).select_related("game_object")
    placed_objects = PlacedObject.objects.filter(player=profile).select_related("game_object")
    era_unlocks = EraUnlock.objects.filter(player=profile)

    data = {
        "profile": PlayerProfileSerializer(profile).data,
        "discoveries": DiscoverySerializer(discoveries, many=True).data,
        "placed_objects": PlacedObjectSerializer(placed_objects, many=True).data,
        "era_unlocks": EraUnlockSerializer(era_unlocks, many=True).data,
    }
    return Response(data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def import_game(request):
    """Import game state from JSON with validation."""
    # Validate the import data using the schema serializer
    serializer = GameStateImportSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {"error": "Invalid import data", "details": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )

    data = serializer.validated_data
    profile = request.user.profile

    with transaction.atomic():
        PlacedObject.objects.filter(player=profile).delete()
        Discovery.objects.filter(player=profile).delete()
        EraUnlock.objects.filter(player=profile).delete()

        # Update profile with validated data
        profile.coins = data["profile"]["coins"]
        profile.time_crystals = data["profile"]["time_crystals"]
        profile.current_era = data["profile"]["current_era"]
        if "is_pro" in data["profile"]:
            profile.is_pro = data["profile"]["is_pro"]
        profile.save()

        # Restore discoveries from validated data
        for disc in data.get("discoveries", []):
            try:
                obj = GameObject.objects.get(id=disc["game_object"]["id"])
                Discovery.objects.create(player=profile, game_object=obj)
            except GameObject.DoesNotExist:
                # Silently skip non-existent objects
                pass

        # Restore placed objects from validated data
        for placed in data.get("placed_objects", []):
            try:
                obj = GameObject.objects.get(id=placed["game_object"]["id"])
                PlacedObject.objects.create(
                    player=profile,
                    game_object=obj,
                    x=placed["x"],
                    y=placed["y"],
                    placed_at=placed["placed_at"],
                    build_complete_at=placed["build_complete_at"],
                    retire_at=placed["retire_at"],
                    is_building=placed["is_building"],
                    is_operational=placed["is_operational"],
                )
            except GameObject.DoesNotExist:
                # Silently skip non-existent objects
                pass

        # Restore era unlocks from validated data
        for unlock in data.get("era_unlocks", []):
            EraUnlock.objects.create(player=profile, era_name=unlock["era_name"])

    return Response({"success": True})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def redeem_upgrade_key(request):
    """Redeem an upgrade key to unlock pro status."""
    key = request.data.get("key", "").strip()
    
    if not key:
        return Response({"error": "Key is required"}, status=status.HTTP_400_BAD_REQUEST)
    
    profile = request.user.profile
    
    # Check if user is already pro
    if profile.is_pro:
        return Response({"error": "You already have pro status"}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        upgrade_key = UpgradeKey.objects.get(key=key)
    except UpgradeKey.DoesNotExist:
        return Response({"error": "Invalid key"}, status=status.HTTP_404_NOT_FOUND)
    
    if upgrade_key.is_redeemed:
        return Response({"error": "This key has already been redeemed"}, status=status.HTTP_400_BAD_REQUEST)
    
    # Redeem the key
    upgrade_key.is_redeemed = True
    upgrade_key.redeemed_by = request.user
    upgrade_key.redeemed_at = timezone.now()
    upgrade_key.save()
    
    # Upgrade the user
    profile.is_pro = True
    profile.save()
    
    return Response({
        "success": True,
        "message": "Successfully upgraded to Pro! You now have 500 daily API calls.",
        "profile": PlayerProfileSerializer(profile).data
    }, status=status.HTTP_200_OK)
