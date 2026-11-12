from django.db import migrations, models

MAX_LENGTH = 150


def split_name(apps, schema_editor):
    """Existing accounts keep their name: the first word becomes the first name, the rest the last."""
    User = apps.get_model('accounts', 'User')
    for user in User.objects.exclude(name='').iterator():
        first, _, last = user.name.strip().partition(' ')
        user.first_name = first[:MAX_LENGTH]
        user.last_name = last.strip()[:MAX_LENGTH]
        user.save(update_fields=['first_name', 'last_name'])


def join_name(apps, schema_editor):
    User = apps.get_model('accounts', 'User')
    for user in User.objects.iterator():
        user.name = f'{user.first_name} {user.last_name}'.strip()[:MAX_LENGTH]
        user.save(update_fields=['name'])


class Migration(migrations.Migration):
    """Replace the single `name` with `first_name` and `last_name`, keeping existing data."""

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='first_name',
            field=models.CharField(blank=True, max_length=150, verbose_name='first name'),
        ),
        migrations.AddField(
            model_name='user',
            name='last_name',
            field=models.CharField(blank=True, max_length=150, verbose_name='last name'),
        ),
        # A default on the old column lets this migration be reversed.
        migrations.AlterField(
            model_name='user',
            name='name',
            field=models.CharField(default='', max_length=150),
        ),
        migrations.RunPython(split_name, join_name),
        migrations.RemoveField(
            model_name='user',
            name='name',
        ),
    ]
