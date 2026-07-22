# Root the Box — Modernization Roadmap

Status: planning. This document sequences the modernization of Root the Box.
Features stay the same throughout — this is about runtime currency, security,
maintainability, and test safety, not new functionality.

**Deployment assumption:** Docker-only. SQLite is acceptable as the runtime DB,
so MySQL / `sql_dialect` branching may be simplified or removed where it reduces
risk (notably during the SQLAlchemy 2.x migration).

**Workflow:** Each numbered item is one `feature/*` branch off `develop`, merged
back with `--no-ff`, small enough to review and ship independently (per Gitflow —
see CONTRIBUTING.md). Effort/risk are rough (S/M/L).

Priority order: **urgent → backend → frontend.**

---

## Running the tests & local dev notes

Post-Phase-0 mechanics (things that are non-obvious and easy to trip on):

**Run the test suite (the reliable way — clean container):**
```bash
docker build -t rtb-test .
docker run --rm --entrypoint sh rtb-test -c \
  "python3 /opt/rtb/rootthebox.py --tests >/dev/null 2>&1; \
   python3 /opt/rtb/rootthebox.py --tests"
```
Why the **two invocations in one container**: the app gates on a config file
existing — with no `files/rootthebox.cfg`, `--tests` writes a *default* config
and `os._exit(1)`s before running anything. The first call creates that default
config (and exits); the second runs the suite against it. Both must run in the
**same** container so the config persists between them. This is exactly what
`.github/workflows/tests.yml` does. `--tests` now runs `pytest` (not nose) with
coverage over `handlers`/`models`/`libs`.

**⚠️ Config-leakage trap:** `docker compose` mounts host `./files` into the
container, so a stale `files/rootthebox.cfg` from a previous run **overrides
test defaults** and produces bogus failures (e.g. `scoreboard_top=3` →
`assert 3 == 25`; `suspend_registration=True` → registration tests fail;
`debug=True` → the cookie-secret prod path is skipped). Always validate in a
**clean container with no `files/` mount** (the `docker run` above), not via
`docker compose`. To reproduce a prod boot locally, ensure `debug = False` in
the cfg.

**Per CLAUDE.md** (assumes a running dev stack, i.e. config already exists):
```bash
docker compose exec webapp python3 /opt/rtb/rootthebox.py --tests
docker compose exec webapp python3 -m nose ...   # <-- STALE: nose is gone, use pytest
```
Single test / class via pytest goes through `--tests` (the runner defines the
Tornado `options` that a bare `pytest` invocation would be missing).

**Cookie secret** now lives in the config as `cookie_secret` (or the
`COOKIE_SECRET` env var); it is generated + persisted once on first non-debug
boot. Don't commit a real one.

**Test DB files** land at `files/<db_name>.db` and are cleaned up by
`teardown_database`; they're gitignored. (A pre-Phase-0 bug left a pile of
strays — fixed.)

**Dependencies (post-1.3)** are managed with **uv**: `pyproject.toml` is the
human-edited spec, `uv.lock` is the resolved, hashed lockfile (both committed).
The Docker image installs them with `uv sync --frozen` into `/opt/rtb/.venv`,
which is placed first on `PATH` so `python3`/`pytest` resolve to the locked
environment. To change a dependency: edit `pyproject.toml`, run `uv lock`, then
rebuild. `setup/requirements.txt` and `setup/depends.sh` were removed. `sqlalchemy`
is held at `>=1.4,<2` and `tornado` at `>=6.4,<7` until items 1.5/1.6.

---

## Test coverage baseline (why the plan is shaped this way)

As of Phase 0: **83 tests, pytest-run** (was nose), 22% coverage over
handlers/models/libs.

**Covered (unit level):**
- Models — `Flag.capture()` for all 5 flag types (static/regex/file/choice/
  datetime), User password/bank_password, GameLevel/Corp/Box fields,
  UserLevelTimer, Scoreboard ranking + pagination, ReviewMode scoring/penalty.
- A handful of handler paths — login/registration/home/about, game-state
  countdown & registration-window timers, `@game_started` decorator, Materials
  lock filtering.

**NOT covered — the risk surface for the SQLAlchemy migration:**
- Core scoring HTTP flow — `TestMissionHandlers` is commented out
  (`tests/testHandlers.py:427`). Flag *matching* is unit-tested; the full
  submit → score → penalty → GameHistory → websocket path is not.
- All admin CRUD (~2,700 lines of `handlers/AdminHandlers/`).
- XML game import/export (`setup/xmlsetup.py`) — round-trip touching nearly
  every model at once.
- Market/banking, botnet, upgrades, pastebin, notifications, file upload.
- EventManager / WebSockets.

**Strategy:** Use the existing suite as smoke coverage for the mechanical phases
(0 and early 1). Before the SQLAlchemy 2.x migration, add a **characterization
test layer** (item 1.4a) that pins current behavior of the untested critical
flows, so the migration can be proven behavior-preserving.

---

## Phase 0 — Urgent: security & EOL  ✅ DONE (branch `feature/phase0-urgent`)

| # | Work | Why | Risk | Effort |
|---|------|-----|------|--------|
| 0.1 | **Fix the CodeQL workflow** — retarget `branches: [master]` → `main`/`develop`; add python+javascript matrix; bump actions v2→v3/v4 | It has never run; free security scanning once fixed | none | S |
| 0.2 | **Bump base image Python 3.8 → 3.12** in `Dockerfile` + `.devcontainer` | 3.8 is EOL (no security patches since Oct 2024) | med — surfaced dep issues (see below) | S–M |
| 0.3 | **Persist the cookie secret** — `cookie_secret` option (config/`COOKIE_SECRET` env); generated once and saved on first prod boot | Every restart logged out all users; broke multi-process runs | low | S |
| 0.4 | **Remove the admin self-update RCE** — dropped `os.system("git pull")` + auto-restart in `AdminGitStatusHandler` / `rootthebox.py` (handler, route, CLI `--update`, template UI, JS all removed) | Admin-token compromise → arbitrary code execution; nonsensical under immutable Docker images | low | S–M |
| 0.5 | **Removed `.travis.yml`**; added `.github/workflows/tests.yml` running the suite (with `--cov`) on PRs | No tests ran in CI; Travis is defunct | none | S |

### Plan changes forced during Phase 0 (Python 3.12 coupling)

Bumping to 3.12 pulled two later items forward because the app literally would
not boot or test otherwise:

- **`enum34` removed from requirements** (part of item 1.1) — it won't install
  on 3.12 and would shadow stdlib `enum`. The code already uses stdlib `enum`,
  so this was vestigial. The rest of the Py2 cleanup remains in 1.1.
- **nose → pytest migration done now** (item **1.2**, pulled into Phase 0) —
  `nose` imports the removed `imp` module and `rootthebox.py` imported `nose`
  at top level, so *the whole app failed to import on 3.12*. Changes: removed
  the top-level `import nose`; `tests()` now provisions the sqlite DB then runs
  `pytest.main` with coverage; added `pytest.ini` (matches the legacy
  `testFoo.py` names); swapped `nose` → `pytest`/`pytest-cov` in requirements.
- **Fixed 3 pre-existing broken/non-hermetic tests** surfaced by the clean run
  (not regressions): `teardown_database` looked in the wrong dir for the sqlite
  file (left a pile of `files/test-*.db`); `TestBox.test_description` asserted a
  stale 1024-ish limit (model allows 4096); the registration tests assumed
  registration was open and email not required (now set explicitly in setUp).

**Result:** clean-container run is green — **83 passed on Python 3.12**,
coverage baseline **22%** across handlers/models/libs.

> Note: 0.4 is a removal, not a rewrite — in-container `git pull` self-update
> doesn't fit an image-based deploy.

---

## Phase 1 — Backend foundations

Ordered so each step de-risks the next. **1.1 → 1.2 → 1.3 → 1.4a precede the
SQLAlchemy migration (1.5).**

| # | Work | Why | Risk | Effort |
|---|------|-----|------|--------|
| 1.1 | **Strip Python 2 compatibility** — drop `future`/`enum34`, the `python_version<'3.0'` pins, `__future__` imports, and `iteritems`/`has_key`/`xrange`/`basestring`/`unicode()` usages | Dead weight; blocks clean tooling; safe on Py3-only | low | M |
| 1.2 | **Migrate `nose` → `pytest`** — port `tests/`, replace `nose.run(...)` in `rootthebox.py`, wire into the 0.5 CI job, enable `pytest --cov` for a real baseline | `nose` is abandoned; unblocks reliable regression testing + coverage measurement for everything below | low | M |
| 1.3 | **Modern packaging + pinned deps** — `pyproject.toml` + lockfile (uv or pip-tools). Pin Tornado. Drop `mysqlclient`/`PyMySQL` given SQLite-only | Reproducible builds; stops silent breaking upgrades; shrinks the SQLAlchemy-2 surface | low | M |
| **1.4a** | **Characterization tests for critical untested flows** (gate before 1.5) — priority by ROI: (1) XML import/export round-trip, (2) flag submission end-to-end (rebuild `TestMissionHandlers`), (3) admin game-object CRUD round-trip, (4) market/banking + scoreboard ranking if used | Pins current behavior so the SQLAlchemy migration is provably behavior-preserving where the existing suite is blind | low | M–L |
| 1.5 | **SQLAlchemy 1.x → 2.x** — the big one. `select()` query API, `Session` semantics, relationship loading. Lean on 1.2 + 1.4a as the safety net | Current major; unblocks long-term Py version support | **high** | **L** |
| 1.6 | **Tornado async cleanup** — replace deprecated `IOLoop.instance()`; decide whether to keep sync handlers (fine at CTF scale) or move hot paths async | Removes deprecation warnings; optional perf | med | M |
| 1.7 | **Adopt `ruff`** (lint + format), retire `.flake8`; add pre-commit + CI check | One tool replaces flake8/black/isort; enforces the PEP8 rules CONTRIBUTING already claims | none | S |

> Dropped: previous item 1.4 (password-hashing library migration). Instances are
> short-lived and password resets are handled manually — not worth the auth risk.
> Bank-password MD5/SHA is an intentional CTF mechanic — left alone.

---

## Phase 2 — Frontend refresh

Biggest surface, lowest urgency. Staged: patch-bump for CVE relief first, then
decide on a real framework migration as a separate initiative.

| # | Work | Why | Risk | Effort |
|---|------|-----|------|--------|
| 2.1 | **Patch-bump vendored libs to final releases** — jQuery 2.2.4 → 3.7.x, jQuery UI, Bootstrap **2.x** → 3.4.1 or 5.x, review Backbone/Underscore | Immediate known-CVE relief, features unchanged | med — jQuery 3 / Bootstrap majors have breaking markup changes | M–L |
| 2.2 | **Introduce a build pipeline** — npm + bundler (Vite/esbuild) instead of committed `.min.js` | Future updates become `npm update`, not manual re-vendoring | med | L |
| 2.3 | **(Optional, separate project) Framework modernization** — evaluate replacing Backbone/jQuery UI patterns. Scope only after 2.1/2.2 | Long-term maintainability; out of scope for "features unchanged" unless desired | high | XL |

---

## Progress log

_(Update as branches land.)_

- [x] 0.1 Fix CodeQL workflow
- [x] 0.2 Python 3.8 → 3.12
- [x] 0.3 Persist cookie secret
- [x] 0.4 Remove admin self-update RCE
- [x] 0.5 Remove Travis; add pytest CI (+coverage)
- [x] 1.2 nose → pytest (+ coverage baseline) — pulled into Phase 0
- [x] 1.1 Strip Python 2 compatibility (branch `feature/phase1.1-strip-py2`) —
      dropped `future`/`past` shims (`from builtins import …`, `from past.builtins
      import basestring`, `from past.utils import old_div`), the two `__future__`
      imports, and the `python_version<'3.0'` requirement pins + `future` dep.
      Replaced `basestring`→`str`, `old_div(a,b)`→`a // b` (int coords) or `a / b`
      (float), and renamed the Py2-named `unicode()` helper in `StringCoding` to
      `_to_unicode` (behavior unchanged). enum34 was already removed in Phase 0.
      Verified: image builds, **83 passed** (unchanged from baseline).
- [x] 1.3 Modern packaging + pinned deps (uv) — added `pyproject.toml` +
      `uv.lock` (hashed); Docker installs via `uv sync --frozen` from the lock;
      pinned tornado `>=6.4,<7` (6.5.7) and held sqlalchemy `>=1.4,<2` (1.4.54);
      dropped `mysqlclient`/`PyMySQL` (SQLite-only) and `setuptools-rust` (build
      tool, not a runtime dep); removed `setup/requirements.txt` +
      `setup/depends.sh`. Verified: image builds, **83 passed**.
- [ ] 1.4a Characterization tests (gate before 1.5)
- [ ] 1.5 SQLAlchemy 1.x → 2.x
- [ ] 1.6 Tornado async cleanup
- [ ] 1.7 Adopt ruff
- [ ] 2.1 Patch-bump vendored frontend libs
- [ ] 2.2 Frontend build pipeline
- [ ] 2.3 (Optional) framework modernization
