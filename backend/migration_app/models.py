from django.db import models


class Patient(models.Model):
    """
    Simplified internal representation of a FHIR Patient resource.

    Only the fields the application actually needs are kept. The raw
    FHIR JSON is retained for a period post-migration so nothing is lost
    if a mapping decision turns out to need revisiting.
    """

    source_id = models.CharField(
        max_length=64,
        unique=True,
        help_text="The Patient.id on the source FHIR server.",
    )
    name = models.CharField(max_length=255, blank=True, default="")
    birth_date = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=32, blank=True, default="")
    mrn = models.CharField(max_length=64, blank=True, default="")

    raw_source = models.JSONField(
        help_text="The original FHIR Patient resource, kept for traceability."
    )

    migrated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Patient({self.source_id}, {self.name!r})"


class Observation(models.Model):
    """
    Simplified internal representation of a FHIR Observation resource.

    FHIR observation values are polymorphic (valueQuantity, valueString,
    valueCodeableConcept, ...). They're normalized here into a single
    (value, unit, value_type) triple so downstream code never has to
    branch on FHIR's type system.
    """

    class ValueType(models.TextChoices):
        QUANTITY = "quantity", "Quantity"
        STRING = "string", "String"
        CODEABLE_CONCEPT = "codeable_concept", "Codeable Concept"
        BOOLEAN = "boolean", "Boolean"
        UNKNOWN = "unknown", "Unknown"

    source_id = models.CharField(max_length=64, unique=True)
    patient = models.ForeignKey(
        Patient, related_name="observations", on_delete=models.CASCADE
    )

    code = models.CharField(max_length=64, blank=True, default="")
    display = models.CharField(max_length=255, blank=True, default="")

    value = models.CharField(max_length=255, blank=True, default="")
    unit = models.CharField(max_length=64, blank=True, default="")
    value_type = models.CharField(
        max_length=32, choices=ValueType.choices, default=ValueType.UNKNOWN
    )

    effective_date = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=32, blank=True, default="")

    raw_source = models.JSONField()

    migrated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-effective_date"]

    def __str__(self):
        return f"Observation({self.source_id}, {self.code})"
