from django.test import TestCase
from django.urls import reverse

from migration_app.models import Observation, Patient


class PatientListApiTests(TestCase):
    def setUp(self):
        self.patient = Patient.objects.create(
            source_id="p1", name="Jane Doe", gender="female", raw_source={}
        )
        Observation.objects.create(
            source_id="o1",
            patient=self.patient,
            code="8867-4",
            display="Heart rate",
            value="72",
            unit="beats/min",
            value_type="quantity",
            raw_source={},
        )

    def test_list_returns_migrated_patients(self):
        response = self.client.get(reverse("patient-list"))

        self.assertEqual(response.status_code, 200)
        names = [p["name"] for p in response.json()["results"]]
        self.assertIn("Jane Doe", names)

    def test_list_includes_observation_count_not_full_observations(self):
        response = self.client.get(reverse("patient-list"))

        patient_row = response.json()["results"][0]
        self.assertEqual(patient_row["observation_count"], 1)
        self.assertNotIn("observations", patient_row)


class PatientDetailApiTests(TestCase):
    def setUp(self):
        self.patient = Patient.objects.create(
            source_id="p2", name="John Smith", gender="male", raw_source={}
        )
        Observation.objects.create(
            source_id="o2",
            patient=self.patient,
            code="2339-0",
            display="Glucose",
            value="98",
            unit="mg/dL",
            value_type="quantity",
            raw_source={},
        )

    def test_detail_includes_nested_observations(self):
        response = self.client.get(
            reverse("patient-detail", kwargs={"pk": self.patient.pk})
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["name"], "John Smith")
        self.assertEqual(len(body["observations"]), 1)
        self.assertEqual(body["observations"][0]["display"], "Glucose")

    def test_detail_404_for_unknown_patient(self):
        response = self.client.get(reverse("patient-detail", kwargs={"pk": 99999}))

        self.assertEqual(response.status_code, 404)
