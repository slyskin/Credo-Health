# Credo Health — FHIR Migration Exercise

Pulls `Patient` and `Observation` resources from the public HAPI FHIR R4
sandbox (`https://hapi.fhir.org/baseR4`), transforms them into a simplified
internal schema, stores them in SQLite, and exposes them through a small
REST API + Vue frontend.

See [`Plan.md`](./Plan.md) for the write-up of how this would be approached
at ~50,000-patient scale in production.

## Backend setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # .venv\Scripts\activate on Windows
pip install -r requirements.txt

python manage.py migrate          # creates db.sqlite3 with the internal schema
python manage.py migrate_fhir --limit 25   # pulls 25 patients + their observations from the sandbox
python manage.py test             # runs the backend test suite
python manage.py runserver        # serves the API at http://localhost:8000
```

`migrate_fhir` is idempotent — safe to re-run. Omit `--limit` to attempt
pulling everything the sandbox has, though for a quick demo a small limit
is recommended (the public sandbox is large and shared).

### API

| Endpoint | Description |
|---|---|
| `GET /api/patients/` | List migrated patients (name, DOB, gender, observation count) |
| `GET /api/patients/<id>/` | A single patient with their full observation list |

## Frontend setup

```bash
cd frontend
npm install
npm run dev   # serves at http://localhost:5173
```

The frontend expects the backend to be running at `http://localhost:8000`.
Start the backend first.

## What's here

- **`backend/migration_app/fhir_client.py`** — HTTP client for the FHIR sandbox. Follows
  pagination (`next` links) and retries transient failures (429/5xx/timeouts)
  with exponential backoff; fails fast on non-retryable errors (4xx) instead
  of wasting retry budget.
- **`backend/migration_app/transform.py`** — pure functions mapping raw FHIR JSON into
  the internal schema. Kept free of DB/network code specifically so it's easy
  to unit test against sample payloads.
- **`backend/migration_app/management/commands/migrate_fhir.py`** — orchestrates the
  fetch → transform → save pipeline. A failure on one patient or observation
  is logged and skipped rather than aborting the whole run.
- **`backend/migration_app/models.py`** — internal schema. Keeps the raw FHIR JSON
  alongside the flattened fields (`raw_source`) so a mapping decision can be
  revisited later without re-fetching from the source.
- **`backend/migration_app/views.py` / `serializers.py` / `urls.py`** — the REST API.
- **`backend/migration_app/tests/`** — `test_transform.py` covers the FHIR → internal
  mapping logic (including edge cases like missing fields and unrecognized
  value types); `test_api.py` covers the two endpoints against rows created
  directly in the test DB (no live network calls in tests).
- **`frontend/`** — a small Vue 3 + Vite app: a patient list, click-through to
  that patient's observations, with basic loading/error states.

## Design decisions / tradeoffs

- **Per-patient Observation fetching**, not FHIR Bulk `$export`. The public
  HAPI sandbox's support for bulk export wasn't something I wanted to assume
  without verifying against the live server under time constraints, so I went
  with the more universally-supported per-resource search. Plan.md calls out
  `$export` as the better approach for the real 50k-record migration if the
  source system supports it.
- **`update_or_create` keyed on `source_id`** rather than a staging-table +
  promote pattern (which Plan.md describes for the production version) —
  simpler for a small demo run, though it means a partial failure can't be
  cleanly rolled back with a single delete the way a staged approach could.
- **No pagination on the `/api/patients/` endpoint's page size beyond DRF's
  default** — explicitly out of scope per the brief.
- **CORS** is handled with a tiny hand-written dev-only middleware rather
  than adding `django-cors-headers` as a dependency, since this never needs
  to run anywhere but localhost for this exercise.

## What I'd do next with more time

- Add a `--dry-run` flag to `migrate_fhir` to preview counts without writing.
- Add the count-reconciliation and spot-check validation steps described in
  Plan.md as an actual `validate_migration` management command.
- Verify and, if supported, switch to FHIR Bulk Data `$export` for the
  Patient/Observation pull — much better fit at real scale than per-patient
  search requests.
- Add pagination controls and a search/filter box to the patient list in the
  frontend.
- Add a Django admin registration for `Patient`/`Observation` for easier
  manual inspection during development.

## AI use

I used Claude to help scaffold the Django project structure (models, FHIR
client, management command, DRF views/serializers), the Vue frontend, and
this README, and to think through the FHIR → internal schema mapping
(particularly the polymorphic `value[x]` handling on `Observation`). I
reviewed, adjusted, and can explain every part of the resulting code —
notably the retry/backoff logic in `fhir_client.py`, the per-resource error
isolation in `migrate_fhir.py`, and the mapping edge cases covered in
`tests/test_transform.py`.
