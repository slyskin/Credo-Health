# Migration Plan: Legacy FHIR System → Internal Service

## Overall Approach

The migration is a **batch ETL job**, not a live sync, so the priorities are: don't hammer the source API, make progress resumable, and make every step observable.

**Extraction**

- Page through `Patient` resources using FHIR's `_count` + `next` bundle links rather than offset pagination — offsets drift if records change mid-migration, `next` links don't.
- For each patient, fetch their `Observation`s via `Observation?patient=<id>&_count=100`, again following `next` links.
- Alternatively, if the server supports it, use `$export` (FHIR Bulk Data Access) to get NDJSON dumps of all Patients and Observations in one async job — far more efficient than one-request-per-patient at 50k scale. I'd check the source system's capabilities first before committing to per-patient fetching, since 50k patients × N observations could mean millions of requests otherwise.

**Reliability / API limits**

- Rate limiting: a token-bucket limiter sized to the source API's documented (or empirically discovered) limits, with concurrency capped (e.g. 5–10 workers) rather than firing all requests at once.
- Retry with exponential backoff + jitter on 429/5xx/timeouts; a small number of permanent failures should be logged and skipped, not block the whole run.
- Idempotency: track migration state per-resource (`pending` / `done` / `failed`) in a `migration_runs` table keyed by source ID, so a restarted job resumes instead of re-processing everything.
- Chunking: process patients in batches (e.g. 500 at a time), committing to the local DB per batch, so a crash loses at most one batch of progress.

**Observability**

- Structured logs per batch: counts fetched/transformed/written/failed, elapsed time, current rate.
- A simple progress table or dashboard: `X / 50,000 patients migrated`, error rate, estimated time remaining.
- Every failure logged with the source resource ID and the raw error, so it can be triaged in bulk after the run rather than in real time.

## Data Mapping

FHIR resources are deeply nested and code-driven; the internal model should flatten them to what the application actually needs.

**Patient → internal `Patient`**
- `id` ← `Patient.id` (kept as `source_id` to preserve traceability)
- `name` ← concatenation of `Patient.name[0].given` + `family` (prefer `official` use if present)
- `birth_date` ← `Patient.birthDate`
- `gender` ← `Patient.gender`
- `mrn` ← the `identifier` entry whose `system` matches the known MRN system, if present

**Observation → internal `Observation`**
- `id` ← `Observation.id`
- `patient_id` ← parsed from `Observation.subject.reference` (`Patient/<id>`)
- `code` / `display` ← `Observation.code.coding[0].code` / `.display` (prefer a LOINC-system coding if multiple are present)
- `value` — FHIR observations are polymorphic (`valueQuantity`, `valueString`, `valueCodeableConcept`, etc.); normalize into a single `value` + `unit` + `value_type` field so the internal model doesn't need to branch on FHIR's type system downstream
- `effective_date` ← `effectiveDateTime` (fall back to `effectivePeriod.start` if range-based)
- `status` ← `Observation.status` (only migrate `final`/`amended`, flag others for review)

Anything not mapped is intentionally dropped for this internal model but the raw FHIR JSON is kept in a `raw_source` column for a period post-migration, so nothing is destructively lost if a mapping turns out to be wrong.

## Validation

- **Count reconciliation**: total Patients/Observations fetched from source vs. rows written locally should match, accounting for any explicitly skipped/invalid records (which are itemized, not just subtracted silently).
- **Spot-check sampling**: randomly sample ~100 migrated patients per run, re-fetch the source record, and diff the mapped fields against what's stored — catches subtle transformation bugs that count-matching wouldn't.
- **Schema/invariant checks**: no orphaned observations (every `patient_id` must resolve), no null required fields, dates parse and fall in a sane range.
- **Checksum/hash comparison** for high-value fields (e.g. hash of birthdate+name+MRN) to catch silent corruption without storing PHI in logs.
- A migration is only marked "complete" after both count reconciliation and spot-check pass a threshold — not just after the job finishes running.

## Safety (PHI Handling)

This exercise uses synthetic data, but in a real migration:

- **Encrypt in transit and at rest** — TLS to the source API, encrypted local storage/DB for the target.
- **No PHI in logs** — logs should reference resource IDs, not names/DOBs/MRNs; any sampled diffs for validation should be redacted before being written anywhere outside the secure environment.
- **Least-privilege access** — the migration job runs with a scoped service credential to the source system, not a shared admin account, and access is time-boxed to the migration window.
- **Audit trail** — record who ran the migration, when, and what was touched, satisfying HIPAA's audit-control requirements.
- **Data minimization** — only migrate fields the new system actually needs; don't carry forward FHIR extensions/fields with no defined use just because they're available.
- **De-identification for non-prod** — any use of this data for testing/staging should go through a de-identification step first, not use production PHI directly (which is exactly why this exercise uses a synthetic sandbox).

## Rollback

- Each migration run gets a unique `run_id`; every row written during that run is tagged with it.
- If a run needs to be rolled back: `DELETE FROM patients WHERE run_id = ?` (cascading to observations), restoring the target DB to its pre-run state. This is why writes should be additive/tagged rather than in-place updates to existing data during the initial migration.
- For partial failures mid-run: since progress is tracked per-resource, a failed run can be resumed rather than rolled back and restarted — only if a fix invalidates already-migrated data does a full rollback + rerun make sense.
- Before rollback, snapshot the error log so the root cause investigation isn't lost when the bad data is deleted.
- For very large migrations, consider writing to a staging table/schema first and only "promoting" to the live table after validation passes — this makes rollback a no-op (just don't promote) rather than a destructive delete.
