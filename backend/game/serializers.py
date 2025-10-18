from rest_framework import serializers
from django.contrib.auth.models import User
from .models import (
    GameObject, PlayerProfile, Discovery, PlacedObject, 
    CraftingRecipe, EraUnlock
)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email']


class GameObjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = GameObject
        fields = [
            'id', 'object_name', 'era_name', 'is_keystone', 'category',
            'quality_tier', 'cost', 'time_crystal_cost', 'income_per_second',
            'time_crystal_generation', 'build_time_sec', 'operation_duration_sec',
            'retire_payout_coins_pct', 'sellback_pct', 'cap_per_civ',
            'footprint_w', 'footprint_h', 'size', 'global_modifiers',
            'flavor_text', 'image_path'
        ]


class PlayerProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = PlayerProfile
        fields = [
            'id', 'user', 'coins', 'time_crystals', 'current_era',
            'is_pro', 'last_coin_update', 'created_at', 'updated_at'
        ]


class DiscoverySerializer(serializers.ModelSerializer):
    game_object = GameObjectSerializer(read_only=True)
    
    class Meta:
        model = Discovery
        fields = ['id', 'game_object', 'discovered_at']


class PlacedObjectSerializer(serializers.ModelSerializer):
    game_object = GameObjectSerializer(read_only=True)
    
    class Meta:
        model = PlacedObject
        fields = [
            'id', 'game_object', 'x', 'y', 'placed_at',
            'build_complete_at', 'retire_at', 'is_operational', 'is_building'
        ]


class CraftingRecipeSerializer(serializers.ModelSerializer):
    object_a = GameObjectSerializer(read_only=True)
    object_b = GameObjectSerializer(read_only=True)
    result = GameObjectSerializer(read_only=True)
    
    class Meta:
        model = CraftingRecipe
        fields = ['id', 'object_a', 'object_b', 'result', 'created_at']


class EraUnlockSerializer(serializers.ModelSerializer):
    class Meta:
        model = EraUnlock
        fields = ['id', 'era_name', 'unlocked_at']


class GameStateSerializer(serializers.Serializer):
    """Complete game state for save/load"""
    profile = PlayerProfileSerializer()
    discoveries = DiscoverySerializer(many=True)
    placed_objects = PlacedObjectSerializer(many=True)
    era_unlocks = EraUnlockSerializer(many=True)
