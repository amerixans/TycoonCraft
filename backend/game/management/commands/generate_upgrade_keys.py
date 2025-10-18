from django.core.management.base import BaseCommand
from game.models import UpgradeKey
import random
import string


class Command(BaseCommand):
    help = 'Generate 1000 upgrade keys if they do not already exist'

    def handle(self, *args, **options):
        # Check if keys already exist
        existing_count = UpgradeKey.objects.count()
        
        if existing_count >= 1000:
            self.stdout.write(self.style.SUCCESS(f'Keys already exist ({existing_count} keys). Skipping generation.'))
            return
        
        # Generate keys to reach 1000 total
        keys_to_generate = 1000 - existing_count
        self.stdout.write(f'Generating {keys_to_generate} upgrade keys...')
        
        generated = 0
        for i in range(keys_to_generate):
            # Generate 64 character alphanumeric string
            random_part = ''.join(random.choices(string.ascii_letters + string.digits, k=50))
            key = f"tycooncraftkey-{random_part}"
            
            # Create the key if it doesn't exist (in case of collisions)
            _, created = UpgradeKey.objects.get_or_create(key=key)
            if created:
                generated += 1
        
        self.stdout.write(self.style.SUCCESS(f'Successfully generated {generated} upgrade keys.'))
        self.stdout.write(self.style.SUCCESS(f'Total keys in database: {UpgradeKey.objects.count()}'))
        
        # Save keys to a file
        import os
        from django.conf import settings
        
        keys_file = os.path.join(settings.BASE_DIR, 'upgrade_keys.txt')
        with open(keys_file, 'w') as f:
            f.write('# TycoonCraft Upgrade Keys\n')
            f.write('# These keys can be redeemed to upgrade to Pro status (500 daily API calls)\n')
            f.write(f'# Generated: {UpgradeKey.objects.count()} keys\n\n')
            
            for key_obj in UpgradeKey.objects.filter(is_redeemed=False):
                f.write(f'{key_obj.key}\n')
        
        self.stdout.write(self.style.SUCCESS(f'Keys saved to: {keys_file}'))
