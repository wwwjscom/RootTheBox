# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

Root the Box is a real-time CTF (Capture the Flag) scoring engine built on Python 3 + Tornado. Admins create game levels, corporations, boxes, and flags; players submit flags to earn points. Real-time updates are delivered over WebSockets.

## Running Locally

The recommended dev environment is Docker Compose, which handles memcached (required for sessions) automatically:

```bash
# First run — builds image, runs migrations, bootstraps DB
docker compose up --build

# Subsequent runs
docker compose up

# Run tests inside the container (correct SQLAlchemy version)
docker compose exec webapp python3 /opt/rtb/rootthebox.py --tests

# Run a single test class
docker compose exec webapp python3 -m nose tests/testModels.py:TestReviewMode
```

Default admin credentials (created by bootstrap): `admin` / `rootthebox`

The `docker-compose.yml` volume-mounts `handlers/`, `models/`, `templates/`, `static/`, and `tests/` so edits on the host are reflected immediately. `DEBUG=True` is set in the compose env, which disables Tornado's template cache and uses a fixed cookie secret — do not use in production.

**Do not run tests with the host Python** — SQLAlchemy 2.x is installed there but the app requires 1.x. Always run tests inside the container.

## Database & Migrations

- SQLite is used for local/Docker dev; MySQL in production (set via `sql_dialect` config).
- Schema migrations use Alembic. Migration files live in `alembic/versions/`.
- Migrations run automatically on every startup via `update_db()` in `handlers/__init__.py`.
- When adding a column to a model, also create an Alembic migration. Use the pattern in `alembic/versions/d3b1c5f8a901_add_level_submission_timer.py` as a template — it guards against running twice with `_table_has_column()`.
- Set `down_revision` to the most recent file in `alembic/versions/` before yours.

## Architecture

### Request Flow

```
rootthebox.py --start
  → handlers/__init__.py: update_db() runs migrations, then start_server() starts Tornado
  → URL dispatch table in handlers/__init__.py maps regex → Handler class
  → Handler.get()/post() → reads DB via SQLAlchemy models → renders Jinja2-style Tornado template
```

### Handlers

- **`handlers/BaseHandlers.py`** — `BaseHandler` (extends `RequestHandler`) and `BaseWebSocketHandler`. All handlers inherit from one of these. Sessions are stored in memcached via `MemcachedSession`; `get_current_user()` reads from the session.
- **`handlers/AdminHandlers/`** — Admin-only handlers split into game management (`AdminGameHandlers`, `AdminGameObjectHandlers`) and user/lock management (`AdminUserHandlers`). The `AdminLockHandler` pattern (toggle endpoints at `/admin/lock/<action>`) is the convention for boolean state flips on game objects.
- **`handlers/MissionsHandler.py`** — Core player-facing logic: box views, flag submission, scoring, penalties.
- **`handlers/__init__.py`** — URL routing table, `app` object (the Tornado `Application`), `update_db()`, `start_server()`.

### Models

All models extend `DatabaseObject` from `models/BaseModels.py`, which provides `by_id()`, `by_uuid()`, `all()`, and `uuid` auto-generation. Primary keys (`id`) are never exposed to clients — always use `uuid`.

Key domain objects: `GameLevel` → `Corporation` → `Box` → `Flag`. A `Team` captures `Flag`s and accumulates score via `GameHistory` records. `Penalty` tracks wrong submissions per team per flag.

### Security Decorators (`libs/SecurityDecorators.py`)

Applied to handler methods:
- `@authenticated` — requires a valid session
- `@game_started` — requires the game to be running
- `@authorized(permission)` — requires a specific admin permission
- `@dangerous` — marks model query methods that do unscoped lookups (by id/uuid without team scoping); these should only be called from admin handlers

### Real-time Events

`libs/EventManager.py` is a singleton that pushes score updates, flag captures, and notifications to connected clients over WebSockets. Call `self.event_manager.flag_capture(user, flag, reward)` (and similar methods) from handlers after DB writes, not before.

### Templates

Tornado's template engine is used (similar to Jinja2 but not identical). Templates inherit from `templates/main.html` using `{% extends %}` and `{% block %}`. The `{% block modals %}` block renders **outside** `<body>` in `main.html` — content placed there becomes a direct child of `<body>` before the `<div class="container-fluid animated fadeIn">` wrapper, which matters for `position: fixed` CSS elements (the animation on that div breaks fixed positioning for children inside it).

### Admin Toggle Pattern

When adding a boolean toggle to a game object (e.g., `locked`, `review_mode`):
1. Add the column + property to the model with type coercion in the setter.
2. Add an Alembic migration.
3. Add a `<action>_<object>()` method to `AdminLockHandler` in `AdminUserHandlers.py`.
4. Register the action string in the URL regex in `handlers/__init__.py`.
5. Add a hidden form + JS click handler in the relevant admin template.

## Coding Standards (from CONTRIBUTING.md)

- PEP8 style; functions ≤ ~20 lines; cyclomatic complexity ≤ 8.
- GET requests must never alter state. POST requests must include a CSRF token (`{% raw xsrf_form_html() %}` in templates).
- Never use raw SQL — always SQLAlchemy. Never expose `id`; use `uuid`.
- Never use `{% raw %}` in templates with user-controlled data.
- Use single quotes `'` in Python but use `&#x27;` (not `'`) inside HTML template attributes to prevent contextual encoding issues.
- WebSocket handlers must implement `check_origin` (provided by `BaseWebSocketHandler`).
