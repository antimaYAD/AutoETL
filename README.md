# AutoETL — Phase 1 (Local Development)

A generic ETL platform: upload a messy CSV/XLSX dataset, profile it, detect
data-quality issues, preview and apply deterministic transformations, and
download a clean, versioned result. See `AutoETL_Project_Specification.md`
for the full product vision; this phase covers auth, upload/storage,
profiling, issue detection and the transformation engine (no AI layer,
planner/approval workflow, or async jobs yet — see `AGENTS.md`).

## Prerequisites

- Python 3.13 (already used to create `venv/`)
- PostgreSQL 17 running locally

## 1. Set up PostgreSQL

Create the `autoetl` database and role once:

```powershell
& "C:\Program Files\PostgreSQL\17\bin\psql.exe" -U postgres -h localhost -f db\setup_local_postgres.sql
```

This prompts for your postgres superuser password. Edit the password in
`db/setup_local_postgres.sql` first if you don't want the default, and make
sure `.env`'s `DATABASE_URL` uses the same value.

## 2. Configure environment

```powershell
Copy-Item .env.example .env
# edit .env: set a real SECRET_KEY (see the comment in the file) and confirm DATABASE_URL
```

## 3. Install dependencies (already done once, rerun after pulling changes)

```powershell
venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 4. Run migrations

```powershell
venv\Scripts\python.exe -m alembic upgrade head
```

## 5. Run the API

```powershell
venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Swagger UI: http://127.0.0.1:8000/docs

## 6. Run tests

```powershell
venv\Scripts\python.exe -m pytest
```

Unit tests (profiler/issue-detector/transformations) run on plain
DataFrames; API tests run against an isolated in-memory SQLite database via
dependency override — neither touches your real local PostgreSQL database.

## Typical flow (via Swagger UI or curl)

1. `POST /api/v1/auth/register`, then `POST /api/v1/auth/login` for a token.
2. `POST /api/v1/datasets/upload` (multipart file) with `Authorization: Bearer <token>`.
3. `POST /api/v1/datasets/{id}/profile` and `POST /api/v1/datasets/{id}/analyze`.
4. `POST /api/v1/datasets/{id}/preview` with a transformation plan to see a
   before/after sample.
5. `POST /api/v1/datasets/{id}/transform` to apply it — this creates a new,
   immutable `DatasetVersion` (the original is never overwritten).
