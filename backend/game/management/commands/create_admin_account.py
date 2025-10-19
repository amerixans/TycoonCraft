import os

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from decimal import Decimal
from game.models import (
    PlayerProfile, GameObject, Discovery, EraUnlock
)

class Command(BaseCommand):
    help = 'Creates an admin testing account with special privileges'

    def handle(self, *args, **options):
        username = os.getenv("GAME_ADMIN_USERNAME", "admin")
        password = (
            os.getenv("GAME_ADMIN_PASSWORD")
            or os.getenv("DJANGO_ADMIN_PASSWORD")
            or os.getenv("DJANGO_SUPERUSER_PASSWORD")
        )

        if not password:
            raise CommandError(
                "Admin password not provided. Set GAME_ADMIN_PASSWORD or "
                "DJANGO_ADMIN_PASSWORD before running this command."
            )
        
        # Check if admin user already exists
        if User.objects.filter(username=username).exists():
            self.stdout.write(self.style.WARNING(f'User "{username}" already exists. Updating...'))
            user = User.objects.get(username=username)
            user.set_password(password)
            user.save()
        else:
            self.stdout.write(self.style.SUCCESS(f'Creating user "{username}"...'))
            user = User.objects.create_user(username=username, password=password)
        
        # Mark user as superuser for admin panel access
        user.is_staff = True
        user.is_superuser = True
        user.save()
        
        # Get or create profile
        profile, created = PlayerProfile.objects.get_or_create(
            user=user,
            defaults={
                'coins': Decimal('500'),
                'time_crystals': Decimal('0'),
                'current_era': 'Hunter-Gatherer',
                'is_pro': True
            }
        )
        
        if not created:
            # Reset to default values if profile already exists
            profile.coins = Decimal('500')
            profile.time_crystals = Decimal('0')
            profile.current_era = 'Hunter-Gatherer'
            profile.is_pro = True
            profile.save()
            self.stdout.write(self.style.SUCCESS('Updated existing profile'))
        else:
            self.stdout.write(self.style.SUCCESS('Created new profile'))
        
        # Give access to all crafted items
        all_objects = GameObject.objects.all()
        existing_discoveries = Discovery.objects.filter(player=profile).values_list('game_object_id', flat=True)
        
        discoveries_to_create = []
        for game_obj in all_objects:
            if game_obj.id not in existing_discoveries:
                discoveries_to_create.append(
                    Discovery(player=profile, game_object=game_obj)
                )
        
        if discoveries_to_create:
            Discovery.objects.bulk_create(discoveries_to_create)
            self.stdout.write(self.style.SUCCESS(f'Added {len(discoveries_to_create)} new discoveries'))
        else:
            self.stdout.write(self.style.SUCCESS('Already has all discoveries'))
        
        # Unlock all eras
        eras = [
            "Hunter-Gatherer", "Agriculture", "Metallurgy", "Steam & Industry",
            "Electric Age", "Computing", "Futurism", "Interstellar", "Arcana", "Beyond"
        ]
        
        existing_era_unlocks = EraUnlock.objects.filter(player=profile).values_list('era_name', flat=True)
        
        era_unlocks_to_create = []
        for era_name in eras:
            if era_name not in existing_era_unlocks:
                era_unlocks_to_create.append(
                    EraUnlock(player=profile, era_name=era_name)
                )
        
        if era_unlocks_to_create:
            EraUnlock.objects.bulk_create(era_unlocks_to_create)
            self.stdout.write(self.style.SUCCESS(f'Unlocked {len(era_unlocks_to_create)} new eras'))
        else:
            self.stdout.write(self.style.SUCCESS('Already has all eras unlocked'))
        
        # Set current era to the last one
        profile.current_era = 'Beyond'
        profile.save()
        
        self.stdout.write(self.style.SUCCESS('='*50))
        self.stdout.write(self.style.SUCCESS('Admin account created successfully!'))
        self.stdout.write(self.style.SUCCESS(f'Username: {username}'))
        self.stdout.write(self.style.SUCCESS(f'Coins: {profile.coins}'))
        self.stdout.write(self.style.SUCCESS(f'Time Crystals: {profile.time_crystals}'))
        self.stdout.write(self.style.SUCCESS(f'Total Discoveries: {Discovery.objects.filter(player=profile).count()}'))
        self.stdout.write(self.style.SUCCESS(f'Eras Unlocked: {EraUnlock.objects.filter(player=profile).count()}'))
        self.stdout.write(self.style.SUCCESS('Special Privileges:'))
        self.stdout.write(self.style.SUCCESS('  - Pro status (1000 daily API calls)'))
        self.stdout.write(self.style.SUCCESS('  - Can go negative on coins when buying/crafting'))
        self.stdout.write(self.style.SUCCESS('  - Has access to all crafted items'))
        self.stdout.write(self.style.SUCCESS('  - Has access to all eras'))
        self.stdout.write(self.style.SUCCESS('='*50))
