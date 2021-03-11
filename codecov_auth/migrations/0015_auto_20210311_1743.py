# Generated by Django 3.1.6 on 2021-03-11 17:43

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('codecov_auth', '0014_auto_20210218_1341'),
    ]

    operations = [
        migrations.AlterField(
            model_name='owner',
            name='plan',
            field=models.TextField(default='users-free', null=True),
        ),
        migrations.AlterField(
            model_name='owner',
            name='plan_auto_activate',
            field=models.BooleanField(default=True, null=True),
        ),
        migrations.AlterField(
            model_name='owner',
            name='plan_user_count',
            field=models.SmallIntegerField(default=5, null=True),
        ),
    ]
