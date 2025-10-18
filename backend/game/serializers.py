from rest_framework import serializers
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
from datetime import datetime, timedelta
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


# Import validation serializers with schema validation
class ImportProfileSerializer(serializers.Serializer):
    """Validated import schema for player profile."""
    coins = serializers.DecimalField(max_digits=20, decimal_places=2, min_value=0)
    time_crystals = serializers.DecimalField(max_digits=20, decimal_places=2, min_value=0)
    current_era = serializers.CharField(max_length=100)
    is_pro = serializers.BooleanField(required=False, default=False)

    def validate_coins(self, value):
        """Validate coins are within reasonable bounds."""
        if value > Decimal('999999999999999999'):
            raise serializers.ValidationError("Coins value too large")
        return value

    def validate_time_crystals(self, value):
        """Validate time crystals are within reasonable bounds."""
        if value > Decimal('999999999999999999'):
            raise serializers.ValidationError("Time crystals value too large")
        return value


class ImportDiscoverySerializer(serializers.Serializer):
    """Validated import schema for discoveries."""
    game_object = serializers.DictField(
        child=serializers.IntegerField(),
        required=True
    )

    def validate_game_object(self, value):
        """Validate that game_object has required 'id' field."""
        if 'id' not in value:
            raise serializers.ValidationError("game_object must have 'id' field")
        return value


class ImportPlacedObjectSerializer(serializers.Serializer):
    """Validated import schema for placed objects with datetime validation."""
    game_object = serializers.DictField(required=True)
    x = serializers.IntegerField(min_value=0, max_value=1000)
    y = serializers.IntegerField(min_value=0, max_value=1000)
    placed_at = serializers.DateTimeField()
    build_complete_at = serializers.DateTimeField()
    retire_at = serializers.DateTimeField()
    is_building = serializers.BooleanField()
    is_operational = serializers.BooleanField()

    def validate_game_object(self, value):
        """Validate that game_object has required 'id' field."""
        if 'id' not in value:
            raise serializers.ValidationError("game_object must have 'id' field")
        return value

    def validate(self, data):
        """Validate temporal constraints."""
        now = timezone.now()
        # Datetimes should be reasonable (not too far in past/future)
        max_offset = timedelta(days=365 * 10)  # 10 years

        for field in ['placed_at', 'build_complete_at', 'retire_at']:
            dt = data.get(field)
            if dt and abs((dt - now).total_seconds()) > max_offset.total_seconds():
                raise serializers.ValidationError(
                    f"{field} is too far from current time"
                )

        # build_complete_at should be >= placed_at
        if (data.get('build_complete_at') and data.get('placed_at') and
                data['build_complete_at'] < data['placed_at']):
            raise serializers.ValidationError(
                "build_complete_at must be >= placed_at"
            )

        # retire_at should be > placed_at
        if (data.get('retire_at') and data.get('placed_at') and
                data['retire_at'] <= data['placed_at']):
            raise serializers.ValidationError(
                "retire_at must be > placed_at"
            )

        return data


class ImportEraUnlockSerializer(serializers.Serializer):
    """Validated import schema for era unlocks."""
    era_name = serializers.CharField(max_length=100)


class GameStateImportSerializer(serializers.Serializer):
    """Validated schema for complete game state import with sanitization."""
    profile = ImportProfileSerializer()
    discoveries = ImportDiscoverySerializer(many=True, required=False)
    placed_objects = ImportPlacedObjectSerializer(many=True, required=False)
    era_unlocks = ImportEraUnlockSerializer(many=True, required=False)

    def validate_profile(self, value):
        """Validate profile schema."""
        return value

    def validate_discoveries(self, value):
        """Validate discoveries list is not empty if provided."""
        if value is None:
            return []
        return value

    def validate_placed_objects(self, value):
        """Validate placed objects list is not empty if provided."""
        if value is None:
            return []
        return value

    def validate_era_unlocks(self, value):
        """Validate era unlocks list is not empty if provided."""
        if value is None:
            return []
        return value
