# Generated by Django 5.1.4 on 2025-01-03 09:25

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('food_items', '0001_initial'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='category',
            options={'verbose_name_plural': 'Categories'},
        ),
    ]