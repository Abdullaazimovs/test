# Users API

A production-ready **user management** service: registration, JWT
authentication, email/SMS verification, role-based access control and automatic
cleanup of stale accounts. Built as a **modular monolith** with FastAPI and
fully asynchronous SQLAlchemy.

---

## Table of contents

- [Features](#features)
- [Tech stack](#tech-stack)
- [Architecture](#architecture)
- [Project structure](#project-structure)
- [Quick start (Docker)](#quick-start-docker)
- [Local development (no Docker)](#local-development-no-docker)
- [Configuration](#configuration)
- [API reference](#api-reference)
- [Verification flow](#verification-flow)
- [Automatic cleanup (Celery)](#automatic-cleanup-celery)
- [Database migrations](#database-migrations)
- [Tests](#tests)
- [Deliberate simplifications & next steps](#deliberate-simplifications--next-steps)

---

## Features

- **Registration** with unique-email enforcement; new accounts start *unverified*.
- **JWT authentication** with separate, typed **access** and **refresh** tokens.
- **Verification** via a code delivered through a pluggable sender (console in
  dev, ready for email/SMS in prod). `POST /auth/verify` flips the account to
  *verified*.
- **Automatic cleanup**: accounts left unverified for more than 2 days are
  deleted by a scheduled Celery task.
- **Roles** (`user` / `admin`) with dependency-based access control.
- **User management** endpoints: `/me`, `/users`, `/users/{id}` (GET/PATCH/DELETE).
- **OpenAPI / Swagger UI** with English `summary` + `description` on every route.
- **Containerized** (Dockerfile + docker-compose) and **migration-driven** (Alembic).

## Tech stack

| Concern        | Choice                                   |
|----------------|------------------------------------------|
| Web framework  | FastAPI (async)                          |
| ORM            | SQLAlchemy 2.0 (async)                    |
| Database       | PostgreSQL (prod) / SQLite (dev & tests) |
| Auth           | PyJWT + bcrypt                           |
| Background jobs| Celery + Redis (worker & beat)           |
| Migrations     | Alembic (async env)                      |
| Tests          | pytest + pytest-asyncio + httpx          |

## Architecture

The service is a **modular monolith**: one deployable, internally split into
self-contained feature modules. Each module owns its models, schemas, data
access, business logic and routes, so a module can later be extracted into its
own service with minimal churn.

Each request flows through clear layers:

```
HTTP request
   │
   ▼
Router (app/modules/<m>/router.py)      ← HTTP shape, status codes, OpenAPI docs
   │   depends on
   ▼
Dependencies (auth/dependencies.py)     ← authN/authZ, wires services
   │
   ▼
Service (…/service.py)                  ← business rules, raises domain errors
   │
   ▼
Repository (…/repository.py)            ← all SQLAlchemy queries live here
   │
   ▼
Model (…/models.py) ── async session ── PostgreSQL / SQLite
```

**Why these boundaries?**

- **Router ≠ business logic.** Routers only translate HTTP ↔ Python. This keeps
  endpoints thin and the OpenAPI docs honest.
- **Service raises framework-agnostic `AppError`s** (`core/exceptions.py`),
  mapped to JSON by a single handler in `app/main.py`. The business layer never
  imports `HTTPException`, so it is trivially unit-testable and reusable from
  Celery tasks or a future CLI.
- **Repository isolates persistence.** Swapping or optimizing queries never
  touches business code, and services can be tested against a fake repository.
- **Cross-cutting concerns** (config, security, database, exceptions) live in
  `app/core` and are shared by every module.

## Project structure

```
app/
├── main.py                 # App factory, lifespan, exception handlers, routers
├── bootstrap.py            # Dev schema creation + first-admin seeding
├── core/                   # Cross-cutting infrastructure
│   ├── config.py           # Pydantic settings (env-driven)
│   ├── database.py         # Async engine + session dependency
│   ├── security.py         # Password hashing + JWT create/decode
│   └── exceptions.py       # Domain errors + HTTP handler
├── db/
│   └── base.py             # Declarative Base + timestamp mixin
├── modules/
│   ├── auth/               # Registration, login, refresh, verification
│   │   ├── router.py  schemas.py  service.py  dependencies.py  verification.py
│   └── users/              # User model + management endpoints
│       ├── router.py  schemas.py  service.py  repository.py  models.py
└── tasks/                  # Celery app + scheduled cleanup
    ├── celery_app.py  cleanup.py
migrations/                 # Alembic (async env + initial migration)
tests/                      # pytest suite (in-memory SQLite)
Dockerfile  docker-compose.yml  docker-entrypoint.sh
```

## Quick start (Docker)

Requirements: Docker + Docker Compose.

```bash
cp .env.example .env          # adjust JWT_SECRET_KEY for anything real
docker compose up --build
```

This starts five containers: **api**, **db** (PostgreSQL), **redis**,
**worker** (Celery) and **beat** (Celery scheduler). The API service waits for
the database, applies migrations, then serves on:

- Swagger UI → http://localhost:8000/docs
- ReDoc      → http://localhost:8000/redoc
- Health     → http://localhost:8000/health

A first admin (`admin@example.com` / `Admin12345!` from `.env`) is seeded on
startup so you can immediately exercise the admin-only routes.

## Local development (no Docker)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Uses SQLite by default (see app/core/config.py) — no DB server needed.
uvicorn app.main:app --reload
```

In `dev` the app auto-creates the schema and prints verification codes to the
console. Celery is optional locally; run it only to exercise the cleanup task:

```bash
celery -A app.tasks.celery_app.celery_app worker -l info   # in one terminal
celery -A app.tasks.celery_app.celery_app beat   -l info   # in another
```

## Configuration

All settings come from environment variables / `.env` (see `.env.example`).
Key ones:

| Variable                       | Default                  | Purpose                                   |
|--------------------------------|--------------------------|-------------------------------------------|
| `ENVIRONMENT`                  | `dev`                    | `dev` prints codes & auto-creates schema  |
| `DATABASE_URL`                 | SQLite file              | Async SQLAlchemy URL                      |
| `JWT_SECRET_KEY`               | —                        | **Change in production**                  |
| `ACCESS_TOKEN_EXPIRE_MINUTES`  | `15`                     | Access-token lifetime                     |
| `REFRESH_TOKEN_EXPIRE_DAYS`    | `7`                      | Refresh-token lifetime                    |
| `VERIFICATION_CODE_TTL_MINUTES`| `60`                     | Verification-code validity                |
| `UNVERIFIED_ACCOUNT_TTL_HOURS` | `48`                     | Purge threshold (2 days)                  |
| `CELERY_BROKER_URL`            | Redis                    | Celery broker                             |
| `FIRST_ADMIN_EMAIL/PASSWORD`   | —                        | Optional seeded admin                     |

## API reference

Base path: `/api/v1`. All endpoints are documented in Swagger UI with English
summaries and descriptions.

### Authentication

| Method | Path             | Auth | Description                                   |
|--------|------------------|------|-----------------------------------------------|
| POST   | `/auth/signup`   | —    | Register a user (returns the unverified user) |
| POST   | `/auth/login`    | —    | Obtain access + refresh tokens                |
| POST   | `/auth/refresh`  | —    | Exchange a refresh token for a new access one |
| POST   | `/auth/verify`   | —    | Confirm an account with its verification code |

### Users

| Method | Path               | Auth          | Description                          |
|--------|--------------------|---------------|--------------------------------------|
| GET    | `/me`              | user          | Current authenticated user           |
| GET    | `/users`           | **admin**     | Paginated list of users              |
| GET    | `/users/{id}`      | **admin**     | Fetch a user by id                   |
| PATCH  | `/users/{id}`      | self or admin | Partial update (privileged fields admin-only) |
| DELETE | `/users/{id}`      | **admin**     | Delete a user                        |

Authenticate in Swagger via the **Authorize** button (paste the access token),
or send `Authorization: Bearer <access_token>`.

### Example: end-to-end with curl

```bash
# 1. Register (code is printed to the API console)
curl -X POST localhost:8000/api/v1/auth/signup \
  -H 'Content-Type: application/json' \
  -d '{"email":"jane@example.com","password":"Password123","first_name":"Jane"}'

# 2. Verify using the code from the console
curl -X POST localhost:8000/api/v1/auth/verify \
  -H 'Content-Type: application/json' \
  -d '{"email":"jane@example.com","code":"123456"}'

# 3. Login
curl -X POST localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"jane@example.com","password":"Password123"}'

# 4. Call a protected route
curl localhost:8000/api/v1/me -H "Authorization: Bearer <access_token>"
```

## Verification flow

1. `POST /auth/signup` creates the user `is_verified=false`, generates a
   6-digit code with a TTL, and dispatches it through the configured
   `VerificationSender`.
2. In `dev` the `ConsoleVerificationSender` prints the code to stdout. The
   sender is an abstract strategy (`app/modules/auth/verification.py`), so an
   `EmailVerificationSender` (SES/SendGrid) or `SmsVerificationSender` (Twilio)
   can be dropped in without touching the auth service.
3. `POST /auth/verify` checks the code and its expiry, then sets
   `is_verified=true` and clears the code.

## Automatic cleanup (Celery)

Accounts that remain unverified beyond `UNVERIFIED_ACCOUNT_TTL_HOURS` (48h = 2
days) are deleted automatically.

- **Task**: `app/tasks/cleanup.py → purge_unverified_accounts`.
- **Schedule**: Celery **beat** triggers it hourly (`crontab(minute=0)`).
- **Logic**: a single bulk `DELETE … WHERE is_verified = false AND created_at <
  now() - ttl`, executed via the async repository.

The Celery worker is synchronous, so the task bridges into async with
`asyncio.run` and a short-lived engine, keeping its connection pool isolated
from the API's. Run `worker` (executes tasks) and `beat` (schedules them) — both
are provided as Compose services.

## Database migrations

Alembic drives the schema in production (an initial migration ships in
`migrations/versions/`). The Compose API service runs `alembic upgrade head`
on startup.

```bash
alembic upgrade head                          # apply migrations
alembic revision --autogenerate -m "message"  # create a new migration
```

In `dev`, the app additionally calls `Base.metadata.create_all` on startup for
zero-config SQLite runs; production relies on migrations only.

## Tests

```bash
pytest
```

The suite (in-memory SQLite, no external services) covers signup, duplicate
detection, login, refresh, the verification flow, authentication guards and the
full role-based authorization matrix for the user-management endpoints.

## Deliberate simplifications & next steps

These shortcuts keep the project focused; each is marked with a comment in code
and is how I would extend it given more time:

- **Verification stored on the user row.** Fine for one active code; a dedicated
  `verification_tokens` table would add an audit trail, support email **and**
  SMS simultaneously, and allow resend/rate-limiting.
- **Refresh tokens are stateless (no rotation/revocation).** Production should
  rotate refresh tokens and maintain a denylist (or store token ids in Redis) so
  logout and compromise handling work; `/auth/login` is the place to issue
  rotated tokens.
- **Console verification sender.** Real email/SMS providers plug into the
  existing `VerificationSender` strategy and should send via Celery so the
  request isn't blocked on a third-party API.
- **No rate limiting / lockout.** Login and verify endpoints should be rate
  limited (e.g. slowapi / a Redis token bucket) to resist brute force and user
  enumeration.
- **bcrypt 72-byte limit** is handled by capping password length in the schema;
  an alternative is pre-hashing with SHA-256 before bcrypt.
- **Hard deletes.** Cleanup and `DELETE /users/{id}` remove rows; a soft-delete
  (`deleted_at`) would preserve history and referential safety in a larger system.
```
# test
