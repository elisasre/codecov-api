# Generated by Django 4.1.7 on 2023-06-20 17:14

from django.db import migrations

import core.models


class Migration(migrations.Migration):

    dependencies = [
        ("codecov_auth", "0029_ownerprofile_terms_agreement_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="owner",
            name="trial_end_date",
            field=core.models.DateTimeWithoutTZField(null=True),
        ),
        migrations.AddField(
            model_name="owner",
            name="trial_start_date",
            field=core.models.DateTimeWithoutTZField(null=True),
        ),
    ]