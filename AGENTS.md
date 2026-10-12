# AutoETL — Project Notes

## Commands

- Install deps: `venv\Scripts\python.exe -m pip install -r requirements.txt`
- Run dev server: `venv\Scripts\python.exe -m uvicorn app.main:app --reload`
- Run tests: `venv\Scripts\python.exe -m pytest`
- Create a migration: `venv\Scripts\python.exe -m alembic revision --autogenerate -m "message"`
- Apply migrations: `venv\Scripts\python.exe -m alembic upgrade head`
- Frontend (React + Vite + TS, lives in `frontend/`): `cd frontend && npm install && npx vite` — dev server on port 3000 (set in `vite.config.ts`), talks to the API via `VITE_API_URL` in `frontend/.env` (default http://127.0.0.1:8000).

## Phase 1 scope (current)

Implemented: JWT auth, dataset upload to local filesystem storage
(`app/services/storage_service.py`), generic data profiler
(`app/services/profiler_service.py`), generic issue detector
(`app/services/issue_service.py`), and a Strategy+Registry transformation
engine (`app/etl/`) with detect/preview/apply/validate for ~12 transformations,
exposed via `/preview` and `/transform`. Everything runs synchronously in the
request cycle. Also implemented: version download endpoint
(`GET /datasets/{id}/versions/{vid}/download`).

Frontend (in `frontend/`): React 19 + Vite + TypeScript SPA covering the
full MVP flow — register/login, upload (drag & drop), dataset list,
profile/issue dashboard, transformation review with preview + apply, and
results page with download. JWT is stored in localStorage and attached via
an axios interceptor (`frontend/src/api/client.ts`).

Deferred to a later phase (do not assume these exist):
- Transformation Planner (confidence-based auto/approve decisions) and the
  approval-workflow UI described in the spec.
- Dedicated `etl_jobs` / `transformation_runs` / `validation_results` tables
  and job-state machine (`QUEUED -> ... -> COMPLETED`). For now, profiling
  and issue results are stored as JSON columns directly on `DatasetVersion`.
- Celery + Redis async jobs. Redis has no clean native-Windows story without
  Docker, so `app/workers/tasks.py` contains synchronous wrapper functions
  with Celery-task-shaped signatures, ready to be decorated later.
- AI/LLM semantic layer, S3/MinIO storage, Docker, multi-tenant RBAC.

## Conventions

- Never overwrite a `DatasetVersion`'s file; transformations always create a
  new version (spec section 13 — versioning & audit).
- All transformation operations must go through the allowlist in
  `app/etl/registry.py`. Never `eval`/`exec` AI or user input.
- Services should fetch `get_settings()` inside functions, not at module
  import time — needed so tests can override settings (e.g. `STORAGE_DIR`)
  via env vars/monkeypatch.
- `app/services/dataset_access.py` holds the shared "does this user own this
  dataset/version" lookup — reuse it rather than duplicating ownership checks.

## Security note

A `.env`/`.env.example` write in this session was unexpectedly overwritten
with what looked like a real AWS RDS hostname and password by something in
this environment (possibly an editor snippet/hook). Both files were reverted
to safe placeholders. If you have a hook or snippet that auto-fills `.env`
files, make sure it isn't leaking real credentials from another project into
new ones.
