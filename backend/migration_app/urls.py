from django.urls import path

from .views import PatientDetailView, PatientListView

urlpatterns = [
    path("patients/", PatientListView.as_view(), name="patient-list"),
    path("patients/<int:pk>/", PatientDetailView.as_view(), name="patient-detail"),
]
