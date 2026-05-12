# README-SOO.md

Personal notes on running this environment locally and in production.

## Docker Environments

Two Docker Compose configurations are provided. Production is the default.

### Production

```bash
docker compose up --build   # first run
docker compose up           # subsequent runs
```

- No source code mounts — runs from the built image only
- Debug mode off — cookie secret is randomly generated on each start
- Memcached is internal only (not exposed to the host)
- Containers restart automatically unless explicitly stopped

### Development

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build   # first run
docker compose -f docker-compose.yml -f docker-compose.dev.yml up           # subsequent runs
```

Differences from production:
- Source directories (`handlers/`, `models/`, `templates/`, `static/`, `tests/`) are volume-mounted from the host — edits are reflected immediately without a rebuild
- `DEBUG=True` — disables template caching and uses a fixed cookie secret so sessions survive server restarts
- `AUTORELOAD_SOURCE=True` — Tornado restarts automatically when Python files change
- Memcached port `11211` is exposed to the host for debugging

### Running Tests

Tests must be run inside the container (the host Python has SQLAlchemy 2.x, but the app requires 1.x):

```bash
# Full test suite
docker compose exec webapp python3 /opt/rtb/rootthebox.py --tests

# Single test class
docker compose exec webapp python3 -m nose tests/testModels.py:TestReviewMode
```

Default admin credentials (set during first-run bootstrap): `admin` / `rootthebox`

---

## Custom Features

### Per-Level Submission Timer

Admins can set a time limit (in minutes) on any game level. When a player first navigates to a box within a timed level, they are shown a confirmation screen before the timer starts. Once started the timer is immutable — it cannot be paused or reset — and is tracked per-user (not per-team), so each player has their own independent countdown. When the timer expires the player can still view box content but flag submission buttons are disabled.

Configure it from **Admin → Game Levels → Edit** on any level. Set the timer to `0` to disable it.

### Per-Level Review Mode

Admins can toggle any level into review mode, which allows flags to be submitted and captured normally but suppresses all scoring: flag point awards, box completion bonuses, level completion rewards, and wrong-answer penalties are all disabled while review mode is active.

This is useful for testing a level's flags and difficulty before a competition without polluting the scoreboard.

Toggle it from **Admin → Game Levels** using the **Enable/Disable Review Mode** button on any level. When active:
- A yellow **Review Mode** badge appears on the level in the admin Game Levels and Game Objects views, with a tooltip explaining the behaviour.
- An orange border and alert banner are shown to players on the box page.

### Top-X Public Scoreboard

Admins can limit the public scoreboard to show only the top N teams, hiding lower-ranked players from view. This is useful during competitions to avoid demoralizing struggling teams.

Configure it from **Admin → Configuration → Scoreboard Top N**. Set to `0` (default) to show all teams.

When active:
- Non-admin players visiting `/scoreboard` see only the top N teams and the heading reads **Top N Scoreboard**.
- Admins visiting `/scoreboard` always see the full scoreboard regardless of this setting.

### Projector Scoreboard

A clean, nav-free scoreboard designed for display on a projector or second screen. It shows only the top-N teams (using the **Scoreboard Top N** setting; defaults to 10 if not configured), with a dark background and no navigation chrome.

Access it from **Scoreboard → Projector** in the admin nav (opens in a new tab), or navigate directly to `/scoreboard/projector`. Admin login required.

The projector view uses the same live WebSocket updates and rank-change animations as the main scoreboard.
