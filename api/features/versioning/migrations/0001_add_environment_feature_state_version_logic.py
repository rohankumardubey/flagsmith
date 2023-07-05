# Generated by Django 3.2.19 on 2023-07-05 13:11

from django.db import migrations, models
import django.db.models.deletion
import django_lifecycle.mixins


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('features', '0059_fix_feature_type'),
        ('environments', '0033_add_environment_feature_state_version_logic'),
    ]

    operations = [
        migrations.CreateModel(
            name='EnvironmentFeatureVersion',
            fields=[
                ('sha', models.CharField(max_length=64, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('published', models.BooleanField(default=False)),
                ('live_from', models.DateTimeField(null=True)),
                ('environment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='environments.environment')),
                ('feature', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='features.feature')),
            ],
            bases=(django_lifecycle.mixins.LifecycleModelMixin, models.Model),
        ),
        migrations.AddIndex(
            model_name='environmentfeatureversion',
            index=models.Index(fields=['environment', 'feature'], name='feature_ver_environ_707fb9_idx'),
        ),
    ]
