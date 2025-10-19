from django.core.management.base import BaseCommand
from game.era_loader import get_era_loader


class Command(BaseCommand):
    help = 'Validate era YAML files for consistency and completeness'

    def handle(self, *args, **kwargs):
        try:
            era_loader = get_era_loader()
            eras = era_loader.get_all_eras()

            self.stdout.write(self.style.SUCCESS(f'\n✓ Successfully loaded {len(eras)} era files'))

            # Validate each era
            for era in eras:
                self.stdout.write(f'\n--- Validating {era["name"]} (Order {era["order"]}) ---')

                # Check required fields
                required_fields = ['order', 'name', 'crystal_unlock_cost', 'crafting_cost',
                                 'stat_ranges', 'prompt_description', 'keystone', 'starters']

                for field in required_fields:
                    if field in era:
                        self.stdout.write(self.style.SUCCESS(f'  ✓ {field}'))
                    else:
                        self.stdout.write(self.style.ERROR(f'  ✗ Missing: {field}'))

                # Check stat_ranges
                if 'stat_ranges' in era:
                    ranges = era['stat_ranges']
                    required_ranges = ['cost', 'income_per_second', 'build_time_sec',
                                     'operation_duration_sec', 'retire_payout_coins_pct']
                    for range_name in required_ranges:
                        if range_name in ranges:
                            self.stdout.write(self.style.SUCCESS(f'  ✓ stat_ranges.{range_name}'))
                        else:
                            self.stdout.write(self.style.WARNING(f'  ! Missing stat_range: {range_name}'))

                # Check keystone
                if 'keystone' in era:
                    keystone = era['keystone']
                    if 'recipe_chain' in keystone and len(keystone['recipe_chain']) > 0:
                        self.stdout.write(self.style.SUCCESS(f'  ✓ keystone has {len(keystone["recipe_chain"])} recipe(s)'))

                        # Find the keystone recipe (the one marked is_keystone)
                        keystone_recipe = None
                        for recipe in keystone['recipe_chain']:
                            if recipe.get('is_keystone'):
                                keystone_recipe = recipe
                                break

                        if keystone_recipe:
                            self.stdout.write(self.style.SUCCESS(f'  ✓ Keystone object: {keystone_recipe["output_name"]}'))
                        else:
                            self.stdout.write(self.style.WARNING(f'  ! No recipe marked as keystone'))
                    else:
                        self.stdout.write(self.style.WARNING(f'  ! keystone has no recipe_chain'))

                # Check starters
                if 'starters' in era:
                    starters = era['starters']
                    self.stdout.write(self.style.SUCCESS(f'  ✓ {len(starters)} starter object(s)'))

            # Test predefined recipes loading
            all_recipes = era_loader.get_predefined_recipes()
            self.stdout.write(self.style.SUCCESS(f'\n✓ Total predefined recipes across all eras: {len(all_recipes)}'))

            # Test starter objects loading
            all_starters = era_loader.get_starter_objects()
            self.stdout.write(self.style.SUCCESS(f'✓ Total starter objects across all eras: {len(all_starters)}'))

            # Validate era progression
            self.stdout.write('\n--- Era Progression ---')
            for i, era in enumerate(eras):
                expected_order = i + 1
                if era['order'] == expected_order:
                    self.stdout.write(self.style.SUCCESS(f'  ✓ {era["name"]}: order {era["order"]}'))
                else:
                    self.stdout.write(self.style.ERROR(f'  ✗ {era["name"]}: order {era["order"]} (expected {expected_order})'))

            self.stdout.write(self.style.SUCCESS('\n✓ Validation complete!\n'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\n✗ Validation failed: {str(e)}\n'))
            import traceback
            traceback.print_exc()
