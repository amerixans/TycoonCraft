from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.urls import reverse
from django.db.models import Count
from .models import (
    GameObject, PlayerProfile, Discovery, PlacedObject,
    CraftingRecipe, RateLimit, EraUnlock, UpgradeKey
)


# Customize admin site headers
admin.site.site_header = "TycoonCraft Administration"
admin.site.site_title = "TycoonCraft Admin"
admin.site.index_title = "Game Management Dashboard"


@admin.register(GameObject)
class GameObjectAdmin(admin.ModelAdmin):
    list_display = [
        'object_name', 'era_badge', 'category_badge', 'keystone_badge',
        'cost', 'income_per_second', 'quality_tier', 'created_at'
    ]
    list_filter = ['era_name', 'category', 'is_keystone', 'quality_tier', 'is_starter']
    search_fields = ['object_name', 'flavor_text']
    readonly_fields = ['created_at', 'created_by', 'image_preview']
    list_per_page = 50

    fieldsets = (
        ('Basic Information', {
            'fields': ('object_name', 'era_name', 'category', 'quality_tier', 'flavor_text')
        }),
        ('Object Properties', {
            'fields': ('is_keystone', 'is_starter', 'size', 'footprint_w', 'footprint_h')
        }),
        ('Economy', {
            'fields': ('cost', 'time_crystal_cost', 'income_per_second', 'time_crystal_generation',
                      'retire_payout_coins_pct', 'sellback_pct')
        }),
        ('Timing', {
            'fields': ('build_time_sec', 'operation_duration_sec', 'cap_per_civ')
        }),
        ('Advanced', {
            'fields': ('global_modifiers', 'image_path', 'image_preview'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'created_by'),
            'classes': ('collapse',)
        }),
    )

    def era_badge(self, obj):
        """Display era as a colored badge"""
        colors = {
            'Hunter-Gatherer': '#8B4513',
            'Agricultural': '#228B22',
            'Ancient': '#DAA520',
            'Classical': '#4169E1',
            'Medieval': '#8B0000',
            'Renaissance': '#9370DB',
            'Industrial': '#708090',
            'Modern': '#FF6347',
            'Information': '#00CED1',
            'Beyond': '#FF1493',
        }
        color = colors.get(obj.era_name, '#666666')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-size: 11px; font-weight: bold;">{}</span>',
            color, obj.era_name
        )
    era_badge.short_description = 'Era'

    def category_badge(self, obj):
        """Display category as a badge"""
        return format_html(
            '<span style="background-color: #6c757d; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            obj.category
        )
    category_badge.short_description = 'Category'

    def keystone_badge(self, obj):
        """Display keystone status with icon"""
        if obj.is_keystone:
            return format_html(
                '<span style="color: #ffd700; font-size: 16px;" title="Keystone">★</span>'
            )
        return format_html('<span style="color: #ccc;">-</span>')
    keystone_badge.short_description = 'Key'

    def image_preview(self, obj):
        """Show image preview if available"""
        if obj.image_path:
            return format_html(
                '<img src="/media/{}" style="max-width: 200px; max-height: 200px;" />',
                obj.image_path
            )
        return "No image"
    image_preview.short_description = 'Image Preview'


@admin.register(PlayerProfile)
class PlayerProfileAdmin(admin.ModelAdmin):
    list_display = [
        'username_link', 'coins_display', 'time_crystals_display',
        'current_era', 'pro_badge', 'created_at'
    ]
    list_filter = ['current_era', 'is_pro', 'created_at']
    search_fields = ['user__username', 'user__email']
    readonly_fields = ['created_at', 'updated_at', 'last_coin_update']
    list_per_page = 50

    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('Resources', {
            'fields': ('coins', 'time_crystals', 'current_era')
        }),
        ('Status', {
            'fields': ('is_pro', 'last_coin_update')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    inlines = []

    def username_link(self, obj):
        """Display username with link to user admin"""
        url = reverse('admin:auth_user_change', args=[obj.user.id])
        return format_html('<a href="{}">{}</a>', url, obj.user.username)
    username_link.short_description = 'Username'
    username_link.admin_order_field = 'user__username'

    def coins_display(self, obj):
        """Display coins with formatting"""
        return format_html(
            '<span style="color: #d4af37; font-weight: bold;">{:,.2f}</span>',
            obj.coins
        )
    coins_display.short_description = 'Coins'
    coins_display.admin_order_field = 'coins'

    def time_crystals_display(self, obj):
        """Display time crystals with formatting"""
        return format_html(
            '<span style="color: #4169e1; font-weight: bold;">{:,.2f}</span>',
            obj.time_crystals
        )
    time_crystals_display.short_description = 'Time Crystals'
    time_crystals_display.admin_order_field = 'time_crystals'

    def pro_badge(self, obj):
        """Display pro status badge"""
        if obj.is_pro:
            return format_html(
                '<span style="background-color: #28a745; color: white; padding: 3px 8px; '
                'border-radius: 3px; font-size: 11px; font-weight: bold;">PRO</span>'
            )
        return format_html(
            '<span style="background-color: #6c757d; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-size: 11px;">Standard</span>'
        )
    pro_badge.short_description = 'Tier'


@admin.register(Discovery)
class DiscoveryAdmin(admin.ModelAdmin):
    list_display = ['player_link', 'object_link', 'era_info', 'discovered_at']
    list_filter = ['discovered_at', 'game_object__era_name']
    search_fields = ['player__user__username', 'game_object__object_name']
    readonly_fields = ['discovered_at']
    list_per_page = 100

    def player_link(self, obj):
        """Link to player profile"""
        url = reverse('admin:game_playerprofile_change', args=[obj.player.id])
        return format_html('<a href="{}">{}</a>', url, obj.player.user.username)
    player_link.short_description = 'Player'
    player_link.admin_order_field = 'player__user__username'

    def object_link(self, obj):
        """Link to game object"""
        url = reverse('admin:game_gameobject_change', args=[obj.game_object.id])
        return format_html('<a href="{}">{}</a>', url, obj.game_object.object_name)
    object_link.short_description = 'Object'
    object_link.admin_order_field = 'game_object__object_name'

    def era_info(self, obj):
        """Display era information"""
        return obj.game_object.era_name
    era_info.short_description = 'Era'
    era_info.admin_order_field = 'game_object__era_name'


@admin.register(PlacedObject)
class PlacedObjectAdmin(admin.ModelAdmin):
    list_display = [
        'player_link', 'object_link', 'position', 'status_badge',
        'placed_at', 'build_complete_at'
    ]
    list_filter = ['is_operational', 'is_building', 'placed_at']
    search_fields = ['player__user__username', 'game_object__object_name']
    readonly_fields = ['placed_at']
    list_per_page = 100

    fieldsets = (
        ('Object', {
            'fields': ('player', 'game_object')
        }),
        ('Position', {
            'fields': ('x', 'y')
        }),
        ('Status', {
            'fields': ('is_operational', 'is_building', 'placed_at', 'build_complete_at', 'retire_at')
        }),
    )

    def player_link(self, obj):
        """Link to player profile"""
        url = reverse('admin:game_playerprofile_change', args=[obj.player.id])
        return format_html('<a href="{}">{}</a>', url, obj.player.user.username)
    player_link.short_description = 'Player'
    player_link.admin_order_field = 'player__user__username'

    def object_link(self, obj):
        """Link to game object"""
        url = reverse('admin:game_gameobject_change', args=[obj.game_object.id])
        return format_html('<a href="{}">{}</a>', url, obj.game_object.object_name)
    object_link.short_description = 'Object'
    object_link.admin_order_field = 'game_object__object_name'

    def position(self, obj):
        """Display position coordinates"""
        return f"({obj.x}, {obj.y})"
    position.short_description = 'Position'

    def status_badge(self, obj):
        """Display status with colored badge"""
        if obj.is_operational:
            return format_html(
                '<span style="background-color: #28a745; color: white; padding: 3px 8px; '
                'border-radius: 3px; font-size: 11px;">● Operational</span>'
            )
        elif obj.is_building:
            return format_html(
                '<span style="background-color: #ffc107; color: black; padding: 3px 8px; '
                'border-radius: 3px; font-size: 11px;">⚒ Building</span>'
            )
        else:
            return format_html(
                '<span style="background-color: #dc3545; color: white; padding: 3px 8px; '
                'border-radius: 3px; font-size: 11px;">● Retired</span>'
            )
    status_badge.short_description = 'Status'


@admin.register(CraftingRecipe)
class CraftingRecipeAdmin(admin.ModelAdmin):
    list_display = ['recipe_formula', 'result_link', 'discoverer', 'created_at']
    search_fields = [
        'object_a__object_name', 'object_b__object_name',
        'result__object_name', 'discovered_by__username'
    ]
    readonly_fields = ['created_at']
    list_per_page = 100

    fieldsets = (
        ('Recipe', {
            'fields': ('object_a', 'object_b', 'result')
        }),
        ('Discovery', {
            'fields': ('discovered_by', 'created_at')
        }),
    )

    def recipe_formula(self, obj):
        """Display recipe formula"""
        return format_html(
            '{} <span style="color: #999;">+</span> {} <span style="color: #999;">=</span>',
            obj.object_a.object_name, obj.object_b.object_name
        )
    recipe_formula.short_description = 'Recipe'

    def result_link(self, obj):
        """Link to result object"""
        url = reverse('admin:game_gameobject_change', args=[obj.result.id])
        return format_html('<a href="{}">{}</a>', url, obj.result.object_name)
    result_link.short_description = 'Result'
    result_link.admin_order_field = 'result__object_name'

    def discoverer(self, obj):
        """Display discoverer"""
        if obj.discovered_by:
            return obj.discovered_by.username
        return format_html('<span style="color: #999;">System</span>')
    discoverer.short_description = 'Discovered By'
    discoverer.admin_order_field = 'discovered_by__username'


@admin.register(RateLimit)
class RateLimitAdmin(admin.ModelAdmin):
    list_display = ['player_name', 'limit_type', 'count_display', 'window_start']
    list_filter = ['limit_type', 'window_start']
    readonly_fields = ['window_start']
    list_per_page = 100

    def player_name(self, obj):
        """Display player name"""
        if obj.player:
            url = reverse('admin:game_playerprofile_change', args=[obj.player.id])
            return format_html('<a href="{}">{}</a>', url, obj.player.user.username)
        return format_html('<span style="font-weight: bold; color: #dc3545;">Global</span>')
    player_name.short_description = 'Player'

    def count_display(self, obj):
        """Display count with visual indicator"""
        return format_html(
            '<span style="font-weight: bold; color: #007bff;">{}</span>',
            obj.count
        )
    count_display.short_description = 'Count'
    count_display.admin_order_field = 'count'


@admin.register(EraUnlock)
class EraUnlockAdmin(admin.ModelAdmin):
    list_display = ['player_link', 'era_badge', 'unlocked_at']
    list_filter = ['era_name', 'unlocked_at']
    search_fields = ['player__user__username', 'era_name']
    readonly_fields = ['unlocked_at']
    list_per_page = 100

    def player_link(self, obj):
        """Link to player profile"""
        url = reverse('admin:game_playerprofile_change', args=[obj.player.id])
        return format_html('<a href="{}">{}</a>', url, obj.player.user.username)
    player_link.short_description = 'Player'
    player_link.admin_order_field = 'player__user__username'

    def era_badge(self, obj):
        """Display era as a colored badge"""
        colors = {
            'Hunter-Gatherer': '#8B4513',
            'Agricultural': '#228B22',
            'Ancient': '#DAA520',
            'Classical': '#4169E1',
            'Medieval': '#8B0000',
            'Renaissance': '#9370DB',
            'Industrial': '#708090',
            'Modern': '#FF6347',
            'Information': '#00CED1',
            'Beyond': '#FF1493',
        }
        color = colors.get(obj.era_name, '#666666')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-size: 11px; font-weight: bold;">{}</span>',
            color, obj.era_name
        )
    era_badge.short_description = 'Era'
    era_badge.admin_order_field = 'era_name'


@admin.register(UpgradeKey)
class UpgradeKeyAdmin(admin.ModelAdmin):
    list_display = ['key_display', 'status_badge', 'redeemed_by_link', 'redeemed_at', 'created_at']
    list_filter = ['is_redeemed', 'created_at', 'redeemed_at']
    search_fields = ['key', 'redeemed_by__username']
    readonly_fields = ['created_at', 'redeemed_at', 'redeemed_by']
    list_per_page = 100

    fieldsets = (
        ('Key Information', {
            'fields': ('key', 'is_redeemed')
        }),
        ('Redemption', {
            'fields': ('redeemed_by', 'redeemed_at')
        }),
        ('Metadata', {
            'fields': ('created_at',)
        }),
    )

    def key_display(self, obj):
        """Display key with monospace font"""
        return format_html(
            '<code style="background: #f4f4f4; padding: 2px 6px; border-radius: 3px;">{}</code>',
            obj.key
        )
    key_display.short_description = 'Key'
    key_display.admin_order_field = 'key'

    def status_badge(self, obj):
        """Display redemption status"""
        if obj.is_redeemed:
            return format_html(
                '<span style="background-color: #dc3545; color: white; padding: 3px 8px; '
                'border-radius: 3px; font-size: 11px;">✓ Redeemed</span>'
            )
        return format_html(
            '<span style="background-color: #28a745; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-size: 11px;">Available</span>'
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'is_redeemed'

    def redeemed_by_link(self, obj):
        """Link to user who redeemed"""
        if obj.redeemed_by:
            url = reverse('admin:auth_user_change', args=[obj.redeemed_by.id])
            return format_html('<a href="{}">{}</a>', url, obj.redeemed_by.username)
        return format_html('<span style="color: #999;">-</span>')
    redeemed_by_link.short_description = 'Redeemed By'
    redeemed_by_link.admin_order_field = 'redeemed_by__username'
