from django.contrib import admin
from .models import (
    GameObject, PlayerProfile, Discovery, PlacedObject,
    CraftingRecipe, RateLimit, EraUnlock
)


@admin.register(GameObject)
class GameObjectAdmin(admin.ModelAdmin):
    list_display = ['object_name', 'era_name', 'category', 'is_keystone', 'cost', 'income_per_second']
    list_filter = ['era_name', 'category', 'is_keystone', 'quality_tier']
    search_fields = ['object_name', 'flavor_text']


@admin.register(PlayerProfile)
class PlayerProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'coins', 'time_crystals', 'current_era', 'created_at']
    list_filter = ['current_era']
    search_fields = ['user__username']


@admin.register(Discovery)
class DiscoveryAdmin(admin.ModelAdmin):
    list_display = ['player', 'game_object', 'discovered_at']
    list_filter = ['discovered_at']
    search_fields = ['player__user__username', 'game_object__object_name']


@admin.register(PlacedObject)
class PlacedObjectAdmin(admin.ModelAdmin):
    list_display = ['player', 'game_object', 'x', 'y', 'is_operational', 'placed_at']
    list_filter = ['is_operational', 'is_building']
    search_fields = ['player__user__username', 'game_object__object_name']


@admin.register(CraftingRecipe)
class CraftingRecipeAdmin(admin.ModelAdmin):
    list_display = ['object_a', 'object_b', 'result', 'discovered_by', 'created_at']
    search_fields = ['object_a__object_name', 'object_b__object_name', 'result__object_name']


@admin.register(RateLimit)
class RateLimitAdmin(admin.ModelAdmin):
    list_display = ['player', 'limit_type', 'count', 'window_start']
    list_filter = ['limit_type']


@admin.register(EraUnlock)
class EraUnlockAdmin(admin.ModelAdmin):
    list_display = ['player', 'era_name', 'unlocked_at']
    list_filter = ['era_name']
    search_fields = ['player__user__username']
