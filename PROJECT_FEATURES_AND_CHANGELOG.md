# AutoETL: Features and Change History

A single reference for everything built in this project, from the first commit to the analytics dashboard, in the order it happened. For setup and run instructions see `README.md`; for contributor conventions see `AGENTS.md`.

- **Approach:** local-first development. No Docker, Celery or Redis yet.
- **Stack:** FastAPI, SQLAlchemy 2, PostgreSQL, Alembic, pandas, React 19 + Vite + TypeScript, Recharts.
- **Tests:** 62 backend tests passing (`venv\Scripts\python.exe -m pytest`).
- **Repository:** https://github.com/antimaYAD/AutoETL (branch `main`).
- **Commit status:** only the initial Phase 1 commit is pushed. Everything from section 4 onward (the `/sample` endpoint, transformation-page fixes and the analytics dashboard) is **uncommitted**. Commit it when ready.

---

## 1. Product flow

```
Upload -> Ingest and validate -> Profile -> Detect issues -> Recommend transformations
   -> Preview -> Apply (creates a new version) -> Preview clean data -> Download
   -> Auto Analytics dashboard (KPIs, charts, insights, forecast) -> Export
```

Core principle: recommendations are suggestions; **deterministic, allow-listed Python** does the work. Originals are never overwritten, and every transformation creates a new immutable version.

---

## 2. Feature inventory

### 2.1 Backend

| Area | What it does | Where |
|---|---|---|
| Authentication | Register, login (JWT), current user; bcrypt password hashing | `app/api/auth.py`, `app/core/security.py`, `app/core/deps.py` |
| Datasets | Upload CSV/XLSX, list, get, delete, download any version | `app/api/datasets.py` |
| Ingestion | Extension check, size limit, empty-file check, parse validation, checksum | `app/services/ingestion_service.py` |
| Storage | Local filesystem, sanitised filenames, path-traversal guard, versioned paths | `app/services/storage_service.py` |
| Ownership | Every dataset and version lookup is scoped to the current user | `app/services/dataset_access.py` |
| Profiling | Row/column counts, inferred types, nulls, uniques, min/max/mean/median, category frequencies | `app/services/profiler_service.py` |
| Issue detection | Missing values, whitespace, duplicates, case inconsistency, invalid emails, currency symbols, mixed numeric formats; quality score | `app/services/issue_service.py` |
| Transformation engine | Strategy + allow-list registry; each op supports detect, preview, apply, validate | `app/etl/` |
| Preview / apply | Preview shows before/after samples and rows affected; apply writes a **new version** | `app/api/transformations.py`, `app/services/execution_service.py` |
| Data sample | First N rows of any version (max 100) with NaN serialised as `null` | `GET /datasets/{id}/sample` |
| Auto analytics | Data prep, domain detection, KPIs, charts, anomalies, forecast, insights | `app/services/analytics_service.py`, `app/api/analytics.py` |
| Migrations | Alembic with an initial schema migration | `alembic/` |

**Transformation registry (12 ops):** `trim_whitespace`, `lowercase_text`, `uppercase_text`, `titlecase_text`, `normalize_email`, `normalize_phone`, `parse_date`, `normalize_numeric`, `fill_null`, `drop_null_rows`, `remove_duplicates`, `normalize_category`.

**API endpoints** (prefix `/api/v1`):

| Method | Path | Purpose |
|---|---|---|
| POST | `/auth/register` | Create account |
| POST | `/auth/login` | Get JWT |
| GET | `/auth/me` | Current user |
| POST | `/datasets/upload` | Upload CSV/XLSX |
| GET | `/datasets` | List own datasets |
| GET | `/datasets/{id}` | Dataset with versions |
| DELETE | `/datasets/{id}` | Delete dataset and its files |
| GET | `/datasets/{id}/sample` | Data preview of a version |
| GET | `/datasets/{id}/versions/{vid}/download` | Download a version |
| POST/GET | `/datasets/{id}/profile` | Run / fetch profile |
| POST | `/datasets/{id}/analyze` | Run issue detection |
| GET | `/datasets/{id}/issues` | Fetch issues |
| POST | `/datasets/{id}/preview` | Preview transformations |
| POST | `/datasets/{id}/transform` | Apply transformations (new version) |
| GET | `/datasets/{id}/analytics` | Full analytics payload |

### 2.2 Frontend (`frontend/`)

| Page | Route | Highlights |
|---|---|---|
| Login / Register | `/login`, `/register` | JWT stored in localStorage; Axios interceptor attaches it |
| Dashboard | `/` | Drag-and-drop upload; dataset list |
| Dataset analysis | `/datasets/:id` | Profile stats, issues table, version selector, recommended-transformation chips, **Analytics** and **Review Transformations** buttons |
| Transformations | `/datasets/:id/transform` | One transformation per row (checkbox list), column input, fill-value input for Fill nulls, preview, apply |
| Results | `/datasets/:id/results/:versionId` | Quality score, before/after row counts, applied steps, **data preview table**, download, link to analytics |
| Analytics | `/datasets/:id/analytics` | The dashboard described in section 2.3 |

Route guard, auth context and a shared design system (`index.css`) sit underneath all pages.

### 2.3 Auto Analytics dashboard

Based on `data_analysis_kpi_prediction_framework.md`. Everything is deterministic (no LLM calls).

**Data preparation** (in memory only; the stored dataset is never changed, and the page lists what was done):
- Detects report-style files with a title row and promotes the real header row.
- Removes repeated header rows inside the data.
- Drops completely empty columns.
- Converts text numbers (commas, currency symbols, percentages, bracketed negatives).
- Converts Excel serial dates and text dates.
- Names an unlabeled numeric column when it equals `A × B` of two other columns (for example `Total Sale Amount = Quantity × Unit Sale price`).

**Understanding the data:**
- Domain detection across 13 domains, with a confidence score, falling back to `general`.
- Column roles: date, id, measure, dimension, other.
- Schema-aware column picking for revenue, cost, quantity, order and customer. Unit-price and cost columns are never mistaken for revenue.

**KPIs** (only computed when the needed columns exist):
- Revenue, units, orders, average order value, customers, revenue per customer.
- Gross profit, margin %, loss-making rows.
- Date range, latest-period growth, average per period, best period, top-10 concentration.
- Data-quality KPIs: records, completeness, missing %, duplicate %, columns.

**Charts:**
- **Time:** trend with a 3-period average, revenue vs cost vs profit, margin %, transactions per period, weekday pattern, and actual-vs-forecast with an 80% range.
- **Rankings and mix:** top-N horizontal bars, pareto, donut charts.
- **Distributions and relationships:** clipped histograms, scatter, correlation heatmap, missing-values chart.
- Every chart has axis titles, compact tick numbers, readable labels and tooltips with full values and % share.

**Analysis and insights:**
- Anomalies use IQR, reported as mild (1.5×) and extreme (3×) with example values.
- The forecast is a linear trend with R², a confidence label and an 80% band. An incomplete final period is excluded.
- Insights are split into observed facts, statistical relationships, predictions and recommended actions. Correlations carry a "not causation" note.
- Also included: a numeric statistics table, a category breakdown, and a "blank revenue can be derived" finding.

**Exports:**
- Per chart: PNG and CSV.
- Whole dashboard: PNG.
- KPIs: CSV.
- Full analysis: JSON.

---

## 3. Data-safety and quality rules in place

- Originals are never overwritten; every apply creates a new `DatasetVersion`.
- Only allow-listed transformations run; no `eval` or `exec` of user input.
- Filenames are sanitised, path traversal is blocked, and size and extension are validated.
- Checksums are stored per version.
- All access is owner-scoped; other users' datasets return 404.
- Stack traces are not exposed to clients.
- `.env`, `frontend/.env`, `storage/` and `venv/` are git-ignored, and `.env.example` holds placeholders only.

---

## 4. Change history (start to end)

### Phase 1: Backend foundation
1. Replaced the empty project and mis-encoded `requirement.txt` with a UTF-8 `requirements.txt`.
2. Built the layered FastAPI app (router, service, model) with config, database session and JWT security.
3. Added models: `User`, `Dataset`, `DatasetVersion`.
4. Added the storage service, ingestion validation, the profiler and the issue detector.
5. Built the transformation framework and 12 transformations, plus the preview and apply endpoints.
6. Set up Alembic and hand-wrote the initial migration (`0001_initial_schema.py`).
7. Added `db/setup_local_postgres.sql` for local database provisioning.
8. Built the test suite: transformation unit tests, profiler and issue tests, and API tests on an isolated in-memory SQLite database (46 tests).
9. Wrote `README.md` and `AGENTS.md`.

Fixes during this phase:
- Shared ownership helper (`dataset_access.py`) replaced a stale duplicate.
- Services now read settings per call (not at import) so tests can override them.
- Added the missing exact-duplicate row to the sales fixture.
- Handled pandas `None`/`NaN` behaviour and the pandas 3 `object` dtype warnings.
- Replaced deprecated `datetime.utcnow`.
- `DATABASE_URL` is now assembled from `DB_*` parts with proper URL-encoding.

Security note: `.env.example` was overwritten twice with real-looking cloud credentials that did not come from the project. It was reverted to placeholders each time and never committed.

### Phase 1b: Database
10. Connected to the configured PostgreSQL instance and ran `alembic upgrade head`.
11. Smoke-tested end to end: register, login, upload, profile, analyze, preview, transform.

### Phase 1c: Frontend MVP
12. Scaffolded React + Vite + TypeScript inside `frontend/`.
13. Added the API layer, auth context, protected routes and all MVP pages.
14. Added the version download endpoint and Vite CORS origins to the backend.

### Phase 1d: Polish and troubleshooting
15. Visual redesign: gradients, shadows, Inter font, glass navbar, styled auth cards and dropzone.
16. Fixed a frontend/backend port mismatch (`8010` vs `8000`) by correcting `VITE_API_URL` and restarting Vite.
17. Freed ports 8000 and 5173 when stale processes blocked them.
18. Pushed the initial commit to GitHub after verifying no secrets were staged.

### Phase 1e: Transformation workflow improvements
19. Transformations page turned into a one-per-row checklist.
20. Added issue-to-transformation recommendations (`recommendations.ts`), shown on the dataset page after analysis.
21. Recommendations shown as compact deduplicated chips, one per operation.
22. Both "Review Transformations" buttons pass recommended operations, which are pre-checked on the transform page.
23. The recommended-operation URL parameter now carries operation and column as JSON, so column names containing colons (such as `Unnamed: 4`) cannot break parsing.

### Phase 1f: Fixes from real use
24. **Everything became `0` after apply.** `fill_null` ran on all columns with a default of `0`. Added a fill-value input, and recommendations now pass the affected column instead of `*`.
25. **Data preview before download.** Added `GET /datasets/{id}/sample` and a preview table on the Results page.
26. **Preview failed with 404 / 500.** Two causes: a stale backend without the new route (run with `--reload`), and NaN values breaking JSON serialisation. The sample is now cast to `object` before `None` replaces NaN.

### Phase 2: Auto Analytics
27. **v1 analytics.** Domain detection, KPIs, charts, IQR anomalies, linear forecast, insights, the dashboard page, and PNG export.
28. **v2 rebuild after real-data review** (a Tally-style Sales Register with 21k rows):
    - Root cause of missing axes: axes were wrapped in a React Fragment, which Recharts 2 with React 19 silently drops. Axes, grid and tooltip are now direct children.
    - Root cause of shallow results: the analysis ran on raw data. Added the full data-preparation stage.
    - Smarter column picking, partial-period exclusion, concentration, loss-making rows, weekday analysis and blank-revenue derivation.
    - Added charts: trend with average, revenue/cost/profit, margin, transactions, weekday, pareto, donuts and clipped histograms.
    - Added a statistics table, category breakdown and anomaly detail.
    - Added exports: per-chart PNG and CSV, KPI CSV, JSON.
29. **Verification.** All 19 charts from the real file were server-rendered and checked for axes, grid and titles. 62 backend tests pass, including report-style input, partial periods and axis-label contracts. Two bugs were caught and fixed by the tests: the small-dataset scatter crash and IDs being over-detected.

---

## 5. Known limitations and next steps

- **Async jobs:** everything runs synchronously; Celery and Redis are deferred.
- **Not yet built:** Docker deployment, S3/MinIO storage, multi-tenant RBAC, a transformation planner with an approval workflow, dedicated job/audit tables, AI/LLM semantic layer.
- **Analytics gaps:** no ML models (classification, clustering, ARIMA/Prophet); domain KPI packs beyond sales/finance-style measures (HR attrition, inventory turnover, marketing ROAS); funnel and cohort charts; PDF/HTML report export.
- **Forecast:** a simple linear trend, so treat it as directional.
- **Maintenance:**
  - Passlib logs a harmless `bcrypt.__about__` warning.
  - Starlette's `TestClient` shows an httpx deprecation warning.
  - Recharts 2.x is flagged deprecated upstream; consider moving to v3.
  - Production needs a `SECRET_KEY` validation rule.
- **Operational reminder:** run the API with `--reload` during development so new routes are picked up:
  `uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload`
