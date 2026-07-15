from django.db.models import Count
from rest_framework.generics import ListAPIView, RetrieveAPIView

from .models import Patient
from .serializers import PatientDetailSerializer, PatientListSerializer


class PatientListView(ListAPIView):
    """GET /api/patients/ — list migrated patients."""

    serializer_class = PatientListSerializer

    def get_queryset(self):
        return Patient.objects.annotate(
            observation_count=Count("observations")
        ).order_by("name")


class PatientDetailView(RetrieveAPIView):
    """GET /api/patients/<id>/ — a single patient with their observations."""

    serializer_class = PatientDetailSerializer
    queryset = Patient.objects.prefetch_related("observations")
