# Generated manually for Safe Public User ID Redesign (phase 1: additive nullable columns)

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0007_user_must_change_password'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='member_number',
            field=models.PositiveBigIntegerField(
                blank=True,
                db_index=True,
                help_text='Immutable global serial. Never reused.',
                null=True,
                unique=True,
            ),
        ),
        migrations.AddField(
            model_name='user',
            name='member_id',
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text='Immutable public id MPH######.',
                max_length=24,
                null=True,
                unique=True,
            ),
        ),
        migrations.AddField(
            model_name='user',
            name='display_code',
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text='Role-prefix + member_number (prefix updates on role change).',
                max_length=24,
                null=True,
                unique=True,
            ),
        ),
        migrations.CreateModel(
            name='MemberNumberSequence',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('key', models.CharField(default='global', max_length=32, unique=True)),
                ('next_value', models.PositiveBigIntegerField(default=1)),
            ],
            options={
                'db_table': 'member_number_sequences',
            },
        ),
    ]
