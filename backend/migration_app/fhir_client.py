"""
Small client for the public HAPI FHIR R4 sandbox.

Responsible only for HTTP concerns: pagination and retry/backoff. Mapping
FHIR JSON into our internal schema lives in transform.py, and persistence
lives in the migrate_fhir management command, so each piece can be tested
independently.
"""
import logging
import time
from typing import Iterator, Optional

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class FhirRequestError(Exception):
    """Raised when a FHIR request fails after all retries are exhausted."""


class FhirClient:
    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url or settings.FHIR_BASE_URL
        self.session = requests.Session()

    def _get_with_retry(self, url: str, params: Optional[dict] = None) -> dict:
        max_retries = settings.FHIR_MAX_RETRIES
        backoff_base = settings.FHIR_BACKOFF_BASE_SECONDS

        last_exc = None
        for attempt in range(max_retries + 1):
            try:
                response = self.session.get(
                    url,
                    params=params,
                    headers={"Accept": "application/fhir+json"},
                    timeout=settings.FHIR_REQUEST_TIMEOUT_SECONDS,
                )
            except requests.RequestException as exc:
                last_exc = exc
                logger.warning(
                    "FHIR request error (attempt %d/%d) for %s: %s",
                    attempt + 1, max_retries + 1, url, exc,
                )
            else:
                if response.status_code == 200:
                    return response.json()
                if response.status_code not in RETRYABLE_STATUS_CODES:
                    # Non-retryable (e.g. 400/404) — fail fast, don't waste
                    # retry budget on a request that will never succeed.
                    raise FhirRequestError(
                        f"Non-retryable status {response.status_code} for {url}: "
                        f"{response.text[:500]}"
                    )
                last_exc = FhirRequestError(
                    f"Retryable status {response.status_code} for {url}"
                )
                logger.warning(
                    "FHIR request failed (attempt %d/%d) for %s: status %d",
                    attempt + 1, max_retries + 1, url, response.status_code,
                )

            if attempt < max_retries:
                sleep_seconds = backoff_base * (2 ** attempt)
                time.sleep(sleep_seconds)

        raise FhirRequestError(
            f"Exhausted {max_retries} retries for {url}"
        ) from last_exc

    def _iter_bundle_pages(self, url: str, params: dict) -> Iterator[dict]:
        """Follows a FHIR search Bundle's 'next' link until exhausted,
        yielding each resource entry along the way."""
        next_url, next_params = url, params
        while next_url:
            bundle = self._get_with_retry(next_url, next_params)
            for entry in bundle.get("entry", []):
                resource = entry.get("resource")
                if resource:
                    yield resource

            next_url = None
            next_params = None
            for link in bundle.get("link", []):
                if link.get("relation") == "next":
                    next_url = link["url"]
                    # The 'next' link already contains its own query
                    # string, so no extra params should be applied here.

    def iter_patients(self, count: Optional[int] = None) -> Iterator[dict]:
        """Yields raw FHIR Patient resources, paging through the sandbox."""
        page_size = count or settings.FHIR_PAGE_SIZE
        url = f"{self.base_url}/Patient"
        yield from self._iter_bundle_pages(url, {"_count": page_size})

    def iter_observations_for_patient(self, patient_source_id: str) -> Iterator[dict]:
        """Yields raw FHIR Observation resources for a single patient."""
        url = f"{self.base_url}/Observation"
        params = {"patient": patient_source_id, "_count": settings.FHIR_PAGE_SIZE}
        yield from self._iter_bundle_pages(url, params)
