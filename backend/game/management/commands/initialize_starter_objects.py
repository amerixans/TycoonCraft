from django.core.management.base import BaseCommand
from game.models import GameObject
from decimal import Decimal


class Command(BaseCommand):
    help = 'Initialize starter objects for the game'

    def handle(self, *args, **kwargs):
        starter_objects = [
            {
                'object_name': 'Rock',
                'era_name': 'Hunter-Gatherer',
                'is_keystone': False,
                'category': 'natural',
                'quality_tier': 'common',
                'cost': Decimal('10'),
                'time_crystal_cost': Decimal('0'),
                'income_per_second': Decimal('0'),
                'time_crystal_generation': Decimal('0'),
                'build_time_sec': 0,
                'operation_duration_sec': 300,
                'retire_payout_coins_pct': Decimal('0.2'),
                'sellback_pct': Decimal('0.2'),
                'cap_per_civ': None,
                'footprint_w': 1,
                'footprint_h': 1,
                'size': Decimal('0.5'),
                'global_modifiers': [],
                'flavor_text': 'A simple rock. Hard and useful.',
                'image_path': '/media/objects/starter-rock.png'
            },
            {
                'object_name': 'Stick',
                'era_name': 'Hunter-Gatherer',
                'is_keystone': False,
                'category': 'natural',
                'quality_tier': 'common',
                'cost': Decimal('10'),
                'time_crystal_cost': Decimal('0'),
                'income_per_second': Decimal('0'),
                'time_crystal_generation': Decimal('0'),
                'build_time_sec': 0,
                'operation_duration_sec': 300,
                'retire_payout_coins_pct': Decimal('0.2'),
                'sellback_pct': Decimal('0.2'),
                'cap_per_civ': None,
                'footprint_w': 1,
                'footprint_h': 1,
                'size': Decimal('0.5'),
                'global_modifiers': [],
                'flavor_text': 'A sturdy stick. Nature\'s first tool.',
                'image_path': '/media/objects/starter-stick.png'
            },
            {
                'object_name': 'Water',
                'era_name': 'Hunter-Gatherer',
                'is_keystone': False,
                'category': 'natural',
                'quality_tier': 'common',
                'cost': Decimal('10'),
                'time_crystal_cost': Decimal('0'),
                'income_per_second': Decimal('0'),
                'time_crystal_generation': Decimal('0'),
                'build_time_sec': 0,
                'operation_duration_sec': 300,
                'retire_payout_coins_pct': Decimal('0.2'),
                'sellback_pct': Decimal('0.2'),
                'cap_per_civ': None,
                'footprint_w': 1,
                'footprint_h': 1,
                'size': Decimal('0.5'),
                'global_modifiers': [],
                'flavor_text': 'Pure water. Essential for life.',
                'image_path': '/media/objects/starter-water.png'
            },
            {
                'object_name': 'Dirt',
                'era_name': 'Hunter-Gatherer',
                'is_keystone': False,
                'category': 'natural',
                'quality_tier': 'common',
                'cost': Decimal('10'),
                'time_crystal_cost': Decimal('0'),
                'income_per_second': Decimal('0'),
                'time_crystal_generation': Decimal('0'),
                'build_time_sec': 0,
                'operation_duration_sec': 300,
                'retire_payout_coins_pct': Decimal('0.2'),
                'sellback_pct': Decimal('0.2'),
                'cap_per_civ': None,
                'footprint_w': 1,
                'footprint_h': 1,
                'size': Decimal('0.5'),
                'global_modifiers': [],
                'flavor_text': 'Rich earth. The foundation of all.',
                'image_path': '/media/objects/starter-dirt.png'
            }
        ]

        for obj_data in starter_objects:
            obj, created = GameObject.objects.get_or_create(
                object_name=obj_data['object_name'],
                defaults=obj_data
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created {obj.object_name}'))
            else:
                self.stdout.write(self.style.WARNING(f'{obj.object_name} already exists'))

        self.stdout.write(self.style.SUCCESS('Starter objects initialized!'))
