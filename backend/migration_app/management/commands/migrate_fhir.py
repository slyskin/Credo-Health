"""
Runs the migration: fetch Patients (and each Patient's Observations) from
the FHIR sandbox, transform them, and persist them into our internal schema.

Usage:
    python manage.py migrate_fhir
    python manage.py migrate_fhir --limit 25

A --limit flag is provided because the public sandbox holds far more
patients than are useful to pull down for a demo/exercise run; omit it to
attempt migrating everything available.

Design notes (see Plan.md for the full production version of this):
  - Each resource is saved independently via update_or_create, so the
    command is safe to re-run — it converges rather than duplicating rows.
  - A failure on one patient or observation is logged and skipped rather
    than aborting the whole run, since one bad record shouldn't block the
    other 49,999.
"""
import logging

from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_date, parse_datetime

from migration_app.fhir_client import FhirClient, FhirRequestError
from migration_app.models import Observation, Patient
from migration_app.transform import (
    patient_id_from_reference,
    transform_observation,
    transform_patient,
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Migrate Patient and Observation resources from the FHIR sandbox."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Maximum number of patients to migrate (default: no limit).",
        )

    def handle(self, *args, **options):
        limit = options["limit"]
        client = FhirClient()

        stats = {
            "patients_seen": 0,
            "patients_saved": 0,
            "patients_failed": 0,
            "observations_saved": 0,
            "observations_failed": 0,
        }

        for fhir_patient in client.iter_patients():
            if limit is not None and stats["patients_seen"] >= limit:
                break
            stats["patients_seen"] += 1

            patient = self._save_patient(fhir_patient, stats)
            if patient is None:
                continue

            self._migrate_observations_for_patient(client, patient, stats)

        self.stdout.write(self.style.SUCCESS(self._summary(stats)))

    def _save_patient(self, fhir_patient: dict, stats: dict):
        try:
            fields = transform_patient(fhir_patient)
            source_id = fields.pop("source_id")
            birth_date = fields.pop("birth_date")
            patient, _created = Patient.objects.update_or_create(
                source_id=source_id,
                defaults={
                    **fields,
                    "birth_date": parse_date(birth_date) if birth_date else None,
                },
            )
            stats["patients_saved"] += 1
            return patient
        except Exception:
            stats["patients_failed"] += 1
            logger.exception(
                "Failed to migrate patient %s", fhir_patient.get("id", "<unknown>")
            )
            return None

    def _migrate_observations_for_patient(self, client, patient, stats):
        try:
            observations = list(client.iter_observations_for_patient(patient.source_id))
        except FhirRequestError:
            logger.exception(
                "Failed to fetch observations for patient %s", patient.source_id
            )
            return

        for fhir_observation in observations:
            try:
                fields = transform_observation(fhir_observation, patient.source_id)
                source_id = fields.pop("source_id")
                fields.pop("patient_source_id")
                effective_date = fields.pop("effective_date")

                # Subject reference should match the patient we fetched
                # these for; if it doesn't (e.g. a malformed reference),
                # fall back to resolving it explicitly rather than
                # assuming.
                subject_ref = fhir_observation.get("subject", {}).get("reference", "")
                resolved_patient_id = patient_id_from_reference(subject_ref)
                if resolved_patient_id and resolved_patient_id != patient.source_id:
                    logger.warning(
                        "Observation %s subject reference %s did not match "
                        "expected patient %s; skipping.",
                        source_id, subject_ref, patient.source_id,
                    )
                    stats["observations_failed"] += 1
                    continue

                Observation.objects.update_or_create(
                    source_id=source_id,
                    defaults={
                        **fields,
                        "patient": patient,
                        "effective_date": (
                            parse_datetime(effective_date) if effective_date else None
                        ),
                    },
                )
                stats["observations_saved"] += 1
            except Exception:
                stats["observations_failed"] += 1
                logger.exception(
                    "Failed to migrate observation %s",
                    fhir_observation.get("id", "<unknown>"),
                )

    @staticmethod
    def _summary(stats: dict) -> str:
        return (
            "Migration complete. "
            f"Patients: {stats['patients_saved']} saved, {stats['patients_failed']} failed "
            f"(of {stats['patients_seen']} seen). "
            f"Observations: {stats['observations_saved']} saved, "
            f"{stats['observations_failed']} failed."
        )
