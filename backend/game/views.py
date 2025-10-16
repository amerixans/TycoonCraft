# views.py

from decimal import Decimal
from datetime import timedelta
import base64
import hashlib
import json
import os
import time

import requests
from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .models import (
    GameObject, PlayerProfile, Discovery, PlacedObject,
    CraftingRecipe, RateLimit, EraUnlock
)
from .serializers import (
    GameObjectSerializer, PlayerProfileSerializer, DiscoverySerializer,
    PlacedObjectSerializer, UserSerializer, EraUnlockSerializer
)

# -----------------------------
# Era definitions / costs
# -----------------------------

ERAS = [
    "Hunter-Gatherer", "Agriculture", "Metallurgy", "Steam & Industry",
    "Electric Age", "Computing", "Futurism", "Interstellar", "Arcana", "Beyond"
]

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

# -----------------------------
# Era progression helpers
# -----------------------------

def get_next_era(current_era):
    """Get the next era in sequence, or None if at the end."""
    try:
        current_index = ERAS.index(current_era)
        if current_index < len(ERAS) - 1:
            return ERAS[current_index + 1]
    except ValueError:
        pass
    return None


def get_unlocked_eras(profile):
    """Get list of all eras unlocked by the player."""
    era_unlocks = EraUnlock.objects.filter(player=profile).values_list('era_name', flat=True)
    return list(era_unlocks)


def get_higher_era(era_a, era_b):
    """Get the higher (more advanced) era between two eras."""
    try:
        index_a = ERAS.index(era_a)
        index_b = ERAS.index(era_b)
        return ERAS[max(index_a, index_b)]
    except ValueError:
        return era_a  # fallback


# -----------------------------
# Rate limiting helpers
# -----------------------------

def check_rate_limit(player, limit_type):
    """Check if rate limit is exceeded."""
    now = timezone.now()

    rate_limit, _ = RateLimit.objects.get_or_create(
        player=player if limit_type == "user_discovery" else None,
        limit_type=limit_type,
        defaults={"window_start": now, "count": 0},
    )

    # Reset if window expired
    window = getattr(settings, "RATE_LIMIT_WINDOW", 60)  # seconds
    if (now - rate_limit.window_start).total_seconds() >= window:
        rate_limit.count = 0
        rate_limit.window_start = now
        rate_limit.save()

    max_limit = (
        getattr(settings, "RATE_LIMIT_USER_DISCOVERIES", 10)
        if limit_type == "user_discovery"
        else getattr(settings, "RATE_LIMIT_GLOBAL_API_CALLS", 100)
    )

    if rate_limit.count >= max_limit:
        return False, max_limit - rate_limit.count

    return True, max_limit - rate_limit.count


def increment_rate_limit(player, limit_type):
    """Increment rate limit counter."""
    rate_limit, _ = RateLimit.objects.get_or_create(
        player=player if limit_type == "user_discovery" else None,
        limit_type=limit_type,
        defaults={"window_start": timezone.now(), "count": 0},
    )
    rate_limit.count += 1
    rate_limit.save()


# -----------------------------
# Player coin/tc updates
# -----------------------------

def update_player_coins(player):
    """Calculate and update coins/time crystals from operational placed objects."""
    now = timezone.now()
    
    # Check for completed buildings and transition them to operational
    completed_buildings = PlacedObject.objects.filter(
        player=player,
        is_building=True,
        build_complete_at__lte=now
    )
    
    if completed_buildings.exists():
        completed_buildings.update(
            is_building=False,
            is_operational=True
        )
    
    time_elapsed = (now - player.last_coin_update).total_seconds()

    operational_objects = (
        PlacedObject.objects
        .filter(player=player, is_operational=True, retire_at__gt=now)
        .select_related("game_object")
    )

    total_income = Decimal("0")
    total_crystals = Decimal("0")

    for placed in operational_objects:
        # Apply global modifiers
        income_multiplier = Decimal("1")

        modifier_objects = (
            PlacedObject.objects
            .filter(player=player, is_operational=True, retire_at__gt=now)
            .exclude(id=placed.id)
            .select_related("game_object")
        )

        for mod_obj in modifier_objects:
            modifiers = mod_obj.game_object.global_modifiers or []
            for mod in modifiers:
                if mod.get("active_when") == "operational":
                    if placed.game_object.category in mod.get("affected_categories", []):
                        income_mult = Decimal(str(mod.get("income_multiplier", 1)))
                        if mod.get("stacking") == "multiplicative":
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

def call_openai_crafting(object_a, object_b, unlocked_eras, current_era):
    """
    Call OpenAI (Responses API) to generate a new object definition via structured output.
    Uses server-to-server endpoint: POST /v1/responses
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
   - The object MUST be assigned to the NEXT era beyond the higher input era
   - Example: If combining Agriculture objects, the keystone should be "Metallurgy"
   - This is because placing the keystone unlocks that next era
   
2. For REGULAR objects (is_keystone: false):
   - The object MUST be assigned to the higher era of the two inputs
   - Example: If combining Hunter-Gatherer + Agriculture, result is Agriculture
   - Never assign to an era beyond the player's highest unlocked era + 1
   
3. Keystone identification:
   - Check the era definitions for "Keystone to Unlock" entries
   - Only set is_keystone: true if the crafted object matches that keystone concept
   - Example: "Campfire" for Hunter-Gatherer, "Fertilizer" for Agriculture, etc.
"""

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

    return parsed


def call_openai_image(object_name):
    """
    Call OpenAI Images API with gpt-image-1-mini.
    Uses POST /v1/images (returns base64 in data[0].b64_json).
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
    return base64.b64decode(b64)


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
        coins=getattr(settings, "STARTING_COINS", Decimal("0"))
    )

    # Starter objects
    starter_objects = GameObject.objects.filter(object_name__in=["Rock", "Stick", "Water", "Dirt"])
    for obj in starter_objects:
        Discovery.objects.create(player=profile, game_object=obj)

    # Unlock first era
    EraUnlock.objects.create(player=profile, era_name="Hunter-Gatherer")

    login(request, user)

    return Response({
        "user": UserSerializer(user).data,
        "profile": PlayerProfileSerializer(profile).data
    }, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([AllowAny])
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
def game_state(request):
    """Get complete game state."""
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
        "all_objects": GameObjectSerializer(GameObject.objects.all(), many=True).data,
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

    # Check user rate limit
    allowed, _ = check_rate_limit(profile, "user_discovery")
    if not allowed:
        return Response({"error": "Rate limit exceeded. Please wait."}, status=status.HTTP_429_TOO_MANY_REQUESTS)

    # Check global rate limit
    allowed_global, _ = check_rate_limit(None, "global_api")
    if not allowed_global:
        return Response({"error": "Server busy. Please try again later."}, status=status.HTTP_429_TOO_MANY_REQUESTS)

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

    # Normalize order
    if object_a.id > object_b.id:
        object_a, object_b = object_b, object_a

    # Pre-existing recipe?
    existing_recipe = CraftingRecipe.objects.filter(object_a=object_a, object_b=object_b).select_related("result").first()
    if existing_recipe:
        result_obj = existing_recipe.result
        discovery, created = Discovery.objects.get_or_create(player=profile, game_object=result_obj)
        return Response({
            "object": GameObjectSerializer(result_obj).data,
            "newly_discovered": created,
            "newly_created": False,
        })

    # New recipe → count, then call OpenAI OUTSIDE DB transaction
    increment_rate_limit(profile, "user_discovery")
    increment_rate_limit(None, "global_api")

    # Get player's era context
    unlocked_eras = get_unlocked_eras(profile)
    current_era = profile.current_era

    try:
        obj_data = call_openai_crafting(object_a, object_b, unlocked_eras, current_era)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_502_BAD_GATEWAY)

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

            Discovery.objects.create(player=profile, game_object=new_obj)

            return Response({
                "object": GameObjectSerializer(new_obj).data,
                "newly_discovered": True,
                "newly_created": True,
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

    if profile.coins < game_object.cost:
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

    # Auto-unlock next era if this is a keystone object
    response_data = PlacedObjectSerializer(placed).data
    if game_object.is_keystone:
        # The keystone's era_name IS the era it unlocks
        era_to_unlock = game_object.era_name
        
        # Check if not already unlocked
        if not EraUnlock.objects.filter(player=profile, era_name=era_to_unlock).exists():
            # Unlock the era (no crystal cost when unlocking via keystone)
            EraUnlock.objects.create(player=profile, era_name=era_to_unlock)
            profile.current_era = era_to_unlock
            profile.save()
            
            # Add unlock info to response
            response_data['era_unlocked'] = era_to_unlock
            response_data['message'] = f'Congratulations! You have unlocked the {era_to_unlock} era!'

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
    """Import game state from JSON."""
    data = request.data
    profile = request.user.profile

    with transaction.atomic():
        PlacedObject.objects.filter(player=profile).delete()
        Discovery.objects.filter(player=profile).delete()
        EraUnlock.objects.filter(player=profile).delete()

        profile.coins = Decimal(str(data["profile"]["coins"]))
        profile.time_crystals = Decimal(str(data["profile"]["time_crystals"]))
        profile.current_era = data["profile"]["current_era"]
        profile.save()

        # Restore discoveries
        for disc in data.get("discoveries", []):
            try:
                obj = GameObject.objects.get(id=disc["game_object"]["id"])
                Discovery.objects.create(player=profile, game_object=obj)
            except GameObject.DoesNotExist:
                pass

        # Restore placed objects
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
                pass

        # Restore era unlocks
        for unlock in data.get("era_unlocks", []):
            EraUnlock.objects.create(player=profile, era_name=unlock["era_name"])

    return Response({"success": True})
