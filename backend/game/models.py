from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import json

class GameObject(models.Model):
    """Stores the definition of a crafted object"""
    object_name = models.CharField(max_length=200, unique=True)
    era_name = models.CharField(max_length=50)
    is_keystone = models.BooleanField(default=False)
    is_starter = models.BooleanField(default=False)
    category = models.CharField(max_length=50)
    quality_tier = models.CharField(max_length=50, default='common')
    
    cost = models.DecimalField(max_digits=20, decimal_places=2)
    time_crystal_cost = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    income_per_second = models.DecimalField(max_digits=20, decimal_places=4)
    time_crystal_generation = models.DecimalField(max_digits=20, decimal_places=6, default=0)
    
    build_time_sec = models.IntegerField(default=0)
    operation_duration_sec = models.IntegerField()
    retire_payout_coins_pct = models.DecimalField(max_digits=5, decimal_places=4)
    sellback_pct = models.DecimalField(max_digits=5, decimal_places=4)
    cap_per_civ = models.IntegerField(null=True, blank=True)
    
    footprint_w = models.IntegerField()
    footprint_h = models.IntegerField()
    size = models.DecimalField(max_digits=10, decimal_places=2)
    
    global_modifiers = models.JSONField(default=list, blank=True)
    flavor_text = models.TextField(max_length=200, blank=True)
    
    image_path = models.CharField(max_length=500, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['object_name']),
            models.Index(fields=['era_name']),
        ]
    
    def __str__(self):
        return self.object_name


class CraftingRecipe(models.Model):
    """Tracks which two objects combine to make a third"""
    object_a = models.ForeignKey(GameObject, on_delete=models.CASCADE, related_name='recipes_as_a')
    object_b = models.ForeignKey(GameObject, on_delete=models.CASCADE, related_name='recipes_as_b')
    result = models.ForeignKey(GameObject, on_delete=models.CASCADE, related_name='recipes_as_result')
    
    created_at = models.DateTimeField(auto_now_add=True)
    discovered_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        unique_together = [['object_a', 'object_b']]
        indexes = [
            models.Index(fields=['object_a', 'object_b']),
        ]
    
    def __str__(self):
        return f"{self.object_a.object_name} + {self.object_b.object_name} = {self.result.object_name}"


class PlayerProfile(models.Model):
    """Extended user profile for game state"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    coins = models.DecimalField(max_digits=20, decimal_places=2, default=500)
    time_crystals = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    current_era = models.CharField(max_length=50, default='Hunter-Gatherer')
    
    last_coin_update = models.DateTimeField(default=timezone.now)
    
    # Pro status: True for upgraded users and admin, False for standard
    is_pro = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.username}'s profile"


class Discovery(models.Model):
    """Tracks which objects a player has discovered"""
    player = models.ForeignKey(PlayerProfile, on_delete=models.CASCADE, related_name='discoveries')
    game_object = models.ForeignKey(GameObject, on_delete=models.CASCADE)
    discovered_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = [['player', 'game_object']]
        indexes = [
            models.Index(fields=['player', 'game_object']),
        ]
    
    def __str__(self):
        return f"{self.player.user.username} discovered {self.game_object.object_name}"


class PlacedObject(models.Model):
    """Tracks objects placed on a player's canvas"""
    player = models.ForeignKey(PlayerProfile, on_delete=models.CASCADE, related_name='placed_objects')
    game_object = models.ForeignKey(GameObject, on_delete=models.CASCADE)
    
    x = models.IntegerField()
    y = models.IntegerField()
    
    placed_at = models.DateTimeField(default=timezone.now)
    build_complete_at = models.DateTimeField()
    retire_at = models.DateTimeField(null=True, blank=True)
    
    is_operational = models.BooleanField(default=False)
    is_building = models.BooleanField(default=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['player', 'is_operational']),
        ]
    
    def __str__(self):
        return f"{self.game_object.object_name} at ({self.x},{self.y})"


class RateLimit(models.Model):
    """Tracks rate limiting for API calls"""
    player = models.ForeignKey(PlayerProfile, on_delete=models.CASCADE, related_name='rate_limits', null=True, blank=True)
    limit_type = models.CharField(max_length=50)  # 'user_discovery' or 'global_api'
    count = models.IntegerField(default=0)
    window_start = models.DateTimeField(default=timezone.now)
    
    class Meta:
        unique_together = [['player', 'limit_type']]
        indexes = [
            models.Index(fields=['limit_type', 'window_start']),
        ]


class EraUnlock(models.Model):
    """Tracks which eras a player has unlocked"""
    player = models.ForeignKey(PlayerProfile, on_delete=models.CASCADE, related_name='era_unlocks')
    era_name = models.CharField(max_length=50)
    unlocked_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = [['player', 'era_name']]
    
    def __str__(self):
        return f"{self.player.user.username} unlocked {self.era_name}"


class UpgradeKey(models.Model):
    """Stores upgrade keys that can be redeemed for pro status"""
    key = models.CharField(max_length=100, unique=True)
    is_redeemed = models.BooleanField(default=False)
    redeemed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    redeemed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['key']),
            models.Index(fields=['is_redeemed']),
        ]
    
    def __str__(self):
        return f"{self.key} - {'Redeemed' if self.is_redeemed else 'Available'}"
