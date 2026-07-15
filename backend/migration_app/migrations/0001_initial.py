from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Patient",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("source_id", models.CharField(max_length=64, unique=True)),
                ("name", models.CharField(blank=True, default="", max_length=255)),
                ("birth_date", models.DateField(blank=True, null=True)),
                ("gender", models.CharField(blank=True, default="", max_length=32)),
                ("mrn", models.CharField(blank=True, default="", max_length=64)),
                ("raw_source", models.JSONField()),
                ("migrated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name="Observation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("source_id", models.CharField(max_length=64, unique=True)),
                ("code", models.CharField(blank=True, default="", max_length=64)),
                ("display", models.CharField(blank=True, default="", max_length=255)),
                ("value", models.CharField(blank=True, default="", max_length=255)),
                ("unit", models.CharField(blank=True, default="", max_length=64)),
                (
                    "value_type",
                    models.CharField(
                        choices=[
                            ("quantity", "Quantity"),
                            ("string", "String"),
                            ("codeable_concept", "Codeable Concept"),
                            ("boolean", "Boolean"),
                            ("unknown", "Unknown"),
                        ],
                        default="unknown",
                        max_length=32,
                    ),
                ),
                ("effective_date", models.DateTimeField(blank=True, null=True)),
                ("status", models.CharField(blank=True, default="", max_length=32)),
                ("raw_source", models.JSONField()),
                ("migrated_at", models.DateTimeField(auto_now=True)),
                (
                    "patient",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="observations",
                        to="migration_app.patient",
                    ),
                ),
            ],
            options={
                "ordering": ["-effective_date"],
            },
        ),
    ]
