# Generated by Django 3.2.20 on 2023-10-10 11:27

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('task_processor', '0009_add_recurring_task_run_first_run_at'),
    ]

    operations = [
        migrations.AddField(
            model_name='task',
            name='priority',
            field=models.PositiveSmallIntegerField(default=None),
        ),
    ]
