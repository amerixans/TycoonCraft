# Generated migration to make retire_at field nullable

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='placedobject',
            name='retire_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
