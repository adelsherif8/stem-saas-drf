# Stem SaaS, ported to Django REST Framework

A port of the auth and projects/jobs API from my FastAPI project
Stem SaaS (an audio stem-separation backend) to **Django 6.1 +
Django REST Framework 3.18**, on Postgres.

The point of this repo is to show the same API built the Django way: same data
model, same rules, same status codes where it makes sense, with notes on what
changed and why.

| | |
|---|---|
| Framework | Django 6.1.3, djangorestframework 3.18.3 |
| Auth | djangorestframework-simplejwt 5.5.1 (access + refresh JWTs) |
| Filtering | django-filter 26.2 + DRF search/ordering |
| API docs | drf-spectacular 0.30.0 (OpenAPI 3, Swagger UI, ReDoc) |
| Database | Postgres 17 (psycopg 3.3.9); SQLite fallback for zero-setup local runs |
| Tests | pytest 9.2 + pytest-django 4.14: 74 test cases |
| Python | 3.13 (works on 3.12+) |

---

## Endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/auth/register` | Create an account |
| POST | `/auth/login` | Email + password -> `{access, refresh}` |
| POST | `/auth/refresh` | Refresh token -> new access token (refresh rotates) |
| GET | `/auth/me` | Current user |
| GET | `/projects` | Your projects: paginated, filterable, searchable, sortable |
| POST | `/projects` | Upload a song (multipart) -> project + queued job |
| GET | `/projects/{id}` | One project (with its latest job) |
| PATCH | `/projects/{id}` | Rename |
| DELETE | `/projects/{id}` | Delete project and its jobs |
| GET | `/projects/quota` | Usage this month vs. plan limit |
| GET | `/jobs` | Your jobs (`?status=`, `?project=`) |
| GET | `/jobs/{id}` | Job status + progress |
| GET | `/jobs/{id}/stems` | Produced stems (409 until the job is completed) |
| GET | `/docs`, `/redoc`, `/schema` | Swagger UI, ReDoc, raw OpenAPI schema |
| GET | `/health` | DB check |

### Query parameters on `GET /projects`

| Param | Example | Notes |
|---|---|---|
| `page`, `page_size` | `?page=2&page_size=50` | default 20, max 100 |
| `name` | `?name=demo` | case-insensitive contains |
| `created_after`, `created_before` | `?created_after=2026-11-01T00:00:00Z` | ISO 8601 |
| `job_status` | `?job_status=completed` | projects with at least one job in that state |
| `search` | `?search=mix.wav` | searches `name` and `original_filename` |
| `ordering` | `?ordering=name`, `?ordering=-created_at` | `created_at`, `name`, `id` |

Invalid filter values (for example `?job_status=exploded`) return 400 with the
field name, not an empty list.

---

## How to run

### Docker (Postgres + API)

```bash
docker compose up --build
# API on http://localhost:8000, Swagger UI on http://localhost:8000/docs
```

The API container runs `migrate` on start, then gunicorn.

### Local

```bash
python3.13 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt

# Option A: Postgres
docker compose up -d db
export DATABASE_URL=postgres://stem:stem@localhost:5432/stemsaas

# Option B: no DATABASE_URL -> SQLite file (db.sqlite3)

.venv/bin/python manage.py migrate
.venv/bin/python manage.py runserver
```

### Tests

```bash
.venv/bin/pytest -q                       # uses DATABASE_URL if set, else SQLite
DATABASE_URL=postgres://... .venv/bin/pytest -q
```

pytest-django creates and drops its own `test_<name>` database, so it never
touches your dev data. The suite was run on both Postgres 17 and SQLite (74
passed on each). CI (`.github/workflows/ci.yml`) runs Django's system
checks, a missing-migration check, OpenAPI schema validation and the tests
against a Postgres 17 service container.

### curl walkthrough

```bash
curl -X POST localhost:8000/auth/register -H 'Content-Type: application/json' \
  -d '{"email":"me@example.com","password":"Str0ng-pass-phrase"}'

TOKEN=$(curl -s -X POST localhost:8000/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"me@example.com","password":"Str0ng-pass-phrase"}' | jq -r .access)

curl -X POST localhost:8000/projects -H "Authorization: Bearer $TOKEN" -F 'file=@song.mp3'
curl "localhost:8000/projects?search=song&ordering=-created_at" -H "Authorization: Bearer $TOKEN"
curl localhost:8000/projects/quota -H "Authorization: Bearer $TOKEN"
```

---

## FastAPI -> Django mapping

| Concern | FastAPI original | Django port | Why |
|---|---|---|---|
| Models | SQLAlchemy models in `app/models.py` | Django models in `accounts/models.py`, `studio/models.py` | Table names kept (`users`, `projects`, `jobs`) via `db_table`. |
| Migrations | Alembic (`migrations/versions/`) | Django migrations (`*/migrations/`) | Generated from the models; CI fails if a model change has no migration. |
| Request/response schemas | Pydantic (`app/schemas.py`) | DRF serializers | Serializers do validation and output shape in one class. `UserSerializer` and `JobSerializer` return the same fields as `UserOut` / `JobOut`. |
| Routing | `APIRouter` per file | `ViewSet`s + `DefaultRouter` | One viewset gives list/retrieve/update/delete; extra endpoints (`quota`, `stems`) are `@action`s. Trailing slashes off to keep the original URLs. |
| Dependencies | `Depends(get_db)`, `Depends(require(...))` | Request-scoped ORM + `permission_classes` | Django manages the DB connection per request; auth and permissions are declared on the view. |
| Password hashing | bcrypt directly | Django's hasher (PBKDF2 by default) | Built in, with upgrade-on-login when the hasher changes. Tests switch to MD5 for speed. |
| JWT | PyJWT, one 24h access token, `sub` = email | simplejwt: 60 min access + 7 day rotating refresh, `user_id` claim | Short access tokens plus refresh is the safer default and comes free with simplejwt. |
| Login body | OAuth2 password form (`username=...&password=...`) | JSON `{"email", "password"}` | simplejwt's default. The original used the form for Swagger's "Authorize" button; drf-spectacular gives a bearer-token Authorize button instead. |
| Login errors | 401 "Incorrect email or password" | 401 "No active account found with the given credentials" | simplejwt's message; same status, and it also refuses inactive users. |
| Password rules | none (any string) | Django password validators (min 8, not common, not all digits) | Free hardening; tests cover it. |
| Duplicate email | 400 "Email already registered" | 400 `{"email": ["Email already registered"]}` | Same status and message, in DRF's per-field error format. Checked case-insensitively, emails stored lowercase. |
| Tenancy / access | Workspace membership + roles (`X-Workspace-ID`), RBAC matrix, Postgres RLS | Owner-only: every project/job belongs to one user | See "not ported". Scoping is done in `get_queryset()`, plus an `IsOwner` object permission as a second check. |
| Other users' ids | 404 for jobs in another workspace | 404 for another user's project or job | Same rule: ids cannot be probed. A test asserts the 404 body for someone else's project equals the one for a missing id. |
| Upload validation | Extension check in the route, 400 | `ProjectUploadSerializer.validate_file`: extension, empty file, max size; 400 | Validation moved into the serializer, plus two checks the original didn't have. |
| Quota | `billing.can_create` on the workspace, 402 | `studio.services.can_create` on the user, 402 | Same rule (free = 3 projects per calendar month, pro = unlimited), same status code. |
| `stems` column | JSON string in a `Text` column | `JSONField` (`jsonb` on Postgres) | Native JSON type, no manual `json.loads`. |
| Job not finished | 409 on `/jobs/{id}/stems` | 409 | Same. |
| Pagination | none (lists returned everything) | `PageNumberPagination` (`count`, `next`, `previous`, `results`) | Added: a list endpoint without paging doesn't scale. |
| Filtering | `?action=` on the audit log only | django-filter + search + ordering on projects and jobs | Added. |
| Rename / delete project | not in the original | `PATCH` / `DELETE /projects/{id}` | Added to make projects a full CRUD resource. `PUT` is disabled on purpose; only `name` is writable. |
| Rate limiting | none | `ScopedRateThrottle` on register/login/refresh (20/min default) | Basic brute-force protection on auth endpoints. |
| API docs | FastAPI's built-in `/docs` | drf-spectacular `/docs`, `/redoc`, `/schema` | Schema is validated in CI with `--fail-on-warn`. |
| Config | pydantic-settings | `os.environ` + `dj-database-url` in `config/settings.py` | Django-standard; same env var names where they overlap (`DATABASE_URL`, `JWT_SECRET`, `STORAGE_DIR`, `FREE_TIER_MONTHLY_LIMIT`). |
| Server | uvicorn | gunicorn (WSGI) | Nothing here is async, so plain WSGI is enough. |

---

## Ported vs. not ported

**Ported**

- Email + password registration, login, current user (JWT), plus token refresh.
- `Project` and `Job` models with the same fields (minus `workspace_id`,
  `original_path` is now a Django `FileField`).
- Song upload creating a project and a `queued` job, with file-type validation.
- Project list and quota; job status; stem listing with the 409-until-completed rule.
- Free/pro tier quota with the 402 response.
- "Other people's ids look missing" (404) isolation rule.

**Not ported**

- **Workspaces, memberships, roles (RBAC), ownership transfer.** The Django port
  is single-owner: `tier` moved from the personal workspace onto the user, and
  access is "you see only what you own". Porting workspaces would mean a
  `Membership` model and a role-checking permission class in place of `IsOwner`.
- **API keys** (scoped, hashed, rotatable) and **audit log**.
- **Postgres row-level security** (migration `0003_postgres_rls`).
- **Celery worker and stem separation.** Uploads create a `queued` job, and
  `studio.services.enqueue_separation()` is the empty hook where
  `separate_stems.delay()` would go. Jobs never move past `queued` here; tests
  set `completed`/`failed` directly to exercise the stems endpoint and filters.
- **Stem download** (`GET /jobs/{id}/stems/{name}`), since nothing produces files.
- **Billing** (mock Stripe checkout/webhook) and **Google/GitHub OAuth login**.

---

## Tests

74 test cases (56 test functions, some parametrized) in `tests/`:

| File | Cases | Covers |
|---|---|---|
| `test_auth.py` | 18 | register (shape, hashing, email normalisation, duplicate, invalid fields, weak passwords), login success/failure, inactive user, `/me` with/without/garbage token, refresh flow, access token rejected as refresh |
| `test_permissions.py` | 18 | 401 on every protected endpoint when anonymous, list isolation, 404 on another user's project (get/patch/delete) and job, 404 body identical to a missing id, per-user quota, `IsOwner` unit test, `owner` in payload ignored |
| `test_projects.py` | 29 | upload (+ custom name), bad extension / empty / oversized / missing file, retrieve, rename + validation, read-only fields, `PUT` 405, delete cascades jobs, quota + 402 + month boundary + pro unlimited, pagination, page size cap, out-of-range page, name/date/job-status filters, search, ordering, invalid filter 400 |
| `test_jobs.py` | 5 | job shape, stems 409 then 200, jobs are read-only, status/project filters |
| `test_schema_health.py` | 4 | OpenAPI schema lists every endpoint with bearer auth, Swagger UI, health, auth throttling returns 429 |

---

## Layout

```
config/          settings, root URLs (docs, health)
accounts/        User model, register/login/refresh/me
studio/          Project + Job models, serializers, viewsets, filters,
                 pagination, IsOwner permission, quota service
tests/           pytest-django suite
```
