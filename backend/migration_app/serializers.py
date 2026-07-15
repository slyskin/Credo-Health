from rest_framework import serializers

from .models import Observation, Patient


class ObservationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Observation
        fields = [
            "id",
            "source_id",
            "code",
            "display",
            "value",
            "unit",
            "value_type",
            "effective_date",
            "status",
        ]


class PatientListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for the patient list view — no observations,
    since fetching every observation for every patient on a list endpoint
    would be wasteful (and pagination/perf tuning is out of scope here)."""

    observation_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Patient
        fields = [
            "id",
            "source_id",
            "name",
            "birth_date",
            "gender",
            "mrn",
            "observation_count",
        ]


class PatientDetailSerializer(serializers.ModelSerializer):
    observations = ObservationSerializer(many=True, read_only=True)

    class Meta:
        model = Patient
        fields = [
            "id",
            "source_id",
            "name",
            "birth_date",
            "gender",
            "mrn",
            "observations",
        ]
