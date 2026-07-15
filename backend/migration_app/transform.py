"""
Pure, side-effect-free functions that map raw FHIR R4 JSON resources into
the internal schema used by our models.

Kept separate from models.py and the fetch/save logic so mapping decisions
can be unit tested against sample FHIR payloads without touching a database
or a network connection.
"""
from datetime import date, datetime
from typing import Any, Optional

# Prefer LOINC-coded entries when a resource has multiple codings for the
# same concept, since LOINC is the most broadly useful coding system for
# observations.
LOINC_SYSTEM = "http://loinc.org"


def _first_official_or_first(names: list[dict]) -> Optional[dict]:
    if not names:
        return None
    for n in names:
        if n.get("use") == "official":
            return n
    return names[0]


def patient_display_name(fhir_patient: dict) -> str:
    name_entry = _first_official_or_first(fhir_patient.get("name", []))
    if not name_entry:
        return ""
    given = " ".join(name_entry.get("given", []))
    family = name_entry.get("family", "")
    return " ".join(part for part in [given, family] if part).strip()


def patient_mrn(fhir_patient: dict) -> str:
    """
    Pull the identifier that looks like a Medical Record Number.
    HAPI's synthetic data doesn't consistently label identifier systems,
    so this falls back to the first identifier if no MRN-like system is
    found, rather than dropping identifying info entirely.
    """
    identifiers = fhir_patient.get("identifier", [])
    if not identifiers:
        return ""
    for ident in identifiers:
        type_codings = ident.get("type", {}).get("coding", [])
        if any(c.get("code") == "MR" for c in type_codings):
            return ident.get("value", "")
    return identifiers[0].get("value", "")


def transform_patient(fhir_patient: dict) -> dict:
    """Map a FHIR Patient resource into the internal Patient field dict."""
    return {
        "source_id": fhir_patient["id"],
        "name": patient_display_name(fhir_patient),
        "birth_date": fhir_patient.get("birthDate") or None,
        "gender": fhir_patient.get("gender", ""),
        "mrn": patient_mrn(fhir_patient),
        "raw_source": fhir_patient,
    }


def _preferred_coding(codeable_concept: dict) -> dict:
    codings = codeable_concept.get("coding", [])
    if not codings:
        return {}
    for coding in codings:
        if coding.get("system") == LOINC_SYSTEM:
            return coding
    return codings[0]


def _extract_value(fhir_observation: dict) -> tuple[str, str, str]:
    """Returns (value, unit, value_type) normalized from whichever
    value[x] field is present on the observation."""
    if "valueQuantity" in fhir_observation:
        vq = fhir_observation["valueQuantity"]
        value = str(vq.get("value", ""))
        unit = vq.get("unit", "") or vq.get("code", "")
        return value, unit, "quantity"

    if "valueString" in fhir_observation:
        return fhir_observation["valueString"], "", "string"

    if "valueBoolean" in fhir_observation:
        return str(fhir_observation["valueBoolean"]), "", "boolean"

    if "valueCodeableConcept" in fhir_observation:
        coding = _preferred_coding(fhir_observation["valueCodeableConcept"])
        display = coding.get("display") or fhir_observation["valueCodeableConcept"].get("text", "")
        return display, "", "codeable_concept"

    return "", "", "unknown"


def _extract_effective_date(fhir_observation: dict) -> Optional[str]:
    if "effectiveDateTime" in fhir_observation:
        return fhir_observation["effectiveDateTime"]
    period = fhir_observation.get("effectivePeriod")
    if period and period.get("start"):
        return period["start"]
    return None


def transform_observation(fhir_observation: dict, patient_source_id: str) -> dict:
    """Map a FHIR Observation resource into the internal Observation field dict."""
    code_concept = fhir_observation.get("code", {})
    coding = _preferred_coding(code_concept)
    value, unit, value_type = _extract_value(fhir_observation)

    return {
        "source_id": fhir_observation["id"],
        "patient_source_id": patient_source_id,
        "code": coding.get("code", ""),
        "display": coding.get("display") or code_concept.get("text", ""),
        "value": value,
        "unit": unit,
        "value_type": value_type,
        "effective_date": _extract_effective_date(fhir_observation),
        "status": fhir_observation.get("status", ""),
        "raw_source": fhir_observation,
    }


def patient_id_from_reference(reference: str) -> Optional[str]:
    """'Patient/123' -> '123'. Returns None if the reference doesn't match
    the expected shape (e.g. a contained or absolute-URL reference)."""
    if not reference:
        return None
    parts = reference.split("/")
    if len(parts) == 2 and parts[0] == "Patient":
        return parts[1]
    return None
