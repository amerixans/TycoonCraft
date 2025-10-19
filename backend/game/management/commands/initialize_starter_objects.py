from django.core.management.base import BaseCommand
from game.models import GameObject
from game.era_loader import get_era_loader
from decimal import Decimal


class Command(BaseCommand):
    help = 'Initialize starter objects for the game from era YAML files'

    def handle(self, *args, **kwargs):
        era_loader = get_era_loader()

        # Get all starter objects from all eras
        all_starters = era_loader.get_starter_objects()

        self.stdout.write(self.style.SUCCESS(f'Found {len(all_starters)} starter objects across all eras'))

        for obj_data in all_starters.copy():
            # Convert numeric strings to Decimal where needed
            processed_data = {}
            for key, value in obj_data.items():
                if key in ['cost', 'time_crystal_cost', 'income_per_second', 'time_crystal_generation',
                          'retire_payout_coins_pct', 'sellback_pct', 'size']:
                    processed_data[key] = Decimal(str(value))
                else:
                    processed_data[key] = value

            # Ensure is_starter is True
            processed_data['is_starter'] = True

            obj, created = GameObject.objects.get_or_create(
                object_name=processed_data['object_name'],
                defaults=processed_data
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created {obj.object_name}'))
            else:
                # Always update is_starter=True for existing objects
                if not obj.is_starter:
                    obj.is_starter = True
                    obj.save(update_fields=['is_starter'])
                    self.stdout.write(self.style.SUCCESS(f'Updated {obj.object_name} (marked as starter)'))
                else:
                    self.stdout.write(self.style.WARNING(f'{obj.object_name} already exists'))

        self.stdout.write(self.style.SUCCESS('Starter objects initialized!'))
