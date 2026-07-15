from django.test import SimpleTestCase

from migration_app.transform import (
    patient_id_from_reference,
    transform_observation,
    transform_patient,
)


class TransformPatientTests(SimpleTestCase):
    def test_maps_core_fields(self):
        fhir_patient = {
            "resourceType": "Patient",
            "id": "abc-123",
            "name": [{"use": "official", "given": ["Jane"], "family": "Doe"}],
            "birthDate": "1990-05-01",
            "gender": "female",
            "identifier": [
                {"type": {"coding": [{"code": "MR"}]}, "value": "MRN-999"}
            ],
        }

        result = transform_patient(fhir_patient)

        self.assertEqual(result["source_id"], "abc-123")
        self.assertEqual(result["name"], "Jane Doe")
        self.assertEqual(result["birth_date"], "1990-05-01")
        self.assertEqual(result["gender"], "female")
        self.assertEqual(result["mrn"], "MRN-999")

    def test_missing_optional_fields_do_not_raise(self):
        # Synthetic sandbox data is inconsistent; a patient with no name,
        # birthDate, or identifiers should still migrate rather than error.
        fhir_patient = {"resourceType": "Patient", "id": "no-name-1"}

        result = transform_patient(fhir_patient)

        self.assertEqual(result["source_id"], "no-name-1")
        self.assertEqual(result["name"], "")
        self.assertIsNone(result["birth_date"])
        self.assertEqual(result["mrn"], "")

    def test_prefers_official_name_over_other_uses(self):
        fhir_patient = {
            "id": "p1",
            "name": [
                {"use": "old", "given": ["Nickname"], "family": "Person"},
                {"use": "official", "given": ["Real"], "family": "Name"},
            ],
        }

        result = transform_patient(fhir_patient)

        self.assertEqual(result["name"], "Real Name")


class TransformObservationTests(SimpleTestCase):
    def test_maps_quantity_value(self):
        fhir_observation = {
            "id": "obs-1",
            "status": "final",
            "code": {
                "coding": [
                    {"system": "http://loinc.org", "code": "8867-4", "display": "Heart rate"}
                ]
            },
            "valueQuantity": {"value": 72, "unit": "beats/min"},
            "effectiveDateTime": "2024-01-15T10:00:00Z",
            "subject": {"reference": "Patient/abc-123"},
        }

        result = transform_observation(fhir_observation, patient_source_id="abc-123")

        self.assertEqual(result["code"], "8867-4")
        self.assertEqual(result["display"], "Heart rate")
        self.assertEqual(result["value"], "72")
        self.assertEqual(result["unit"], "beats/min")
        self.assertEqual(result["value_type"], "quantity")
        self.assertEqual(result["status"], "final")

    def test_maps_string_value(self):
        fhir_observation = {
            "id": "obs-2",
            "code": {"coding": [{"code": "note", "display": "Clinical note"}]},
            "valueString": "Patient reports feeling well.",
        }

        result = transform_observation(fhir_observation, patient_source_id="p1")

        self.assertEqual(result["value"], "Patient reports feeling well.")
        self.assertEqual(result["value_type"], "string")

    def test_falls_back_to_effective_period_start(self):
        fhir_observation = {
            "id": "obs-3",
            "code": {"coding": [{"code": "x"}]},
            "effectivePeriod": {"start": "2023-06-01T00:00:00Z", "end": "2023-06-02T00:00:00Z"},
        }

        result = transform_observation(fhir_observation, patient_source_id="p1")

        self.assertEqual(result["effective_date"], "2023-06-01T00:00:00Z")

    def test_unrecognized_value_type_does_not_raise(self):
        fhir_observation = {"id": "obs-4", "code": {"coding": [{"code": "x"}]}}

        result = transform_observation(fhir_observation, patient_source_id="p1")

        self.assertEqual(result["value"], "")
        self.assertEqual(result["value_type"], "unknown")


class PatientIdFromReferenceTests(SimpleTestCase):
    def test_parses_simple_reference(self):
        self.assertEqual(patient_id_from_reference("Patient/123"), "123")

    def test_returns_none_for_unexpected_shape(self):
        self.assertIsNone(patient_id_from_reference("urn:uuid:abc"))
        self.assertIsNone(patient_id_from_reference(""))
