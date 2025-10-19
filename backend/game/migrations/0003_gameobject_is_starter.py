# Generated migration for is_starter field

from django.db import migrations, models


def mark_starter_objects(apps, schema_editor):
    """Mark the predefined starter objects with is_starter=True."""
    GameObject = apps.get_model('game', 'GameObject')

    # List of starter object names for each era
    starter_names = [
        # Hunter-Gatherer starters
        'Rock', 'Stick', 'Water', 'Dry Grass',
        # Agriculture starters
        'Seed', 'Clay', 'Wood', 'Fiber',
        # Metallurgy starters
        'Ore', 'Charcoal', 'Clay Crucible', 'Bellows',
        # Steam & Industry starters
        'Iron', 'Steam', 'Gear', 'Magnet',
        # Electric Age starters
        'Copper', 'Wire', 'Silicon', 'Battery',
        # Computing starters
        'Circuit', 'Code', 'Memory', 'Laser',
        # Futurism starters
        'Superconductor', 'Assembler', 'Magnetic Coil', 'Energy Cell',
        # Interstellar starters
        'Orbital Telescope', 'Quantum Lab', 'Satellite Bus', 'Thruster',
        # Arcana starters
        'Crystal', 'Mana', 'Rune', 'Chalk Circle',
        # Beyond starters
        'Quantum Core', 'Archive', 'Dataset', 'Simulator',
    ]

    # Update all matching objects
    GameObject.objects.filter(object_name__in=starter_names).update(is_starter=True)


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0002_make_retire_at_nullable'),
    ]

    operations = [
        migrations.AddField(
            model_name='gameobject',
            name='is_starter',
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(mark_starter_objects, reverse_code=migrations.RunPython.noop),
    ]
