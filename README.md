# 🎱 Snooker Web App (React + FastAPI)

This project rewrites the original Discord bot into a web application:

- **Frontend:** React (Vite)
- **Backend:** FastAPI
- **Database:** PostgreSQL (`snooker` schema via `asyncpg`)

All core game features from the bot are implemented in the web app:

- Full Mode (ball-by-ball scoring)
- Record Mode (set total entry)
- 2–4 player sessions with fixed player pool (`config.PLAYERS`)
- Deterministic full-mode player order driven by hardcoded tables
  (SNOOKER-3); see "Full-Mode Player Order" below
- Foul handling (intentional/unintentional) with correct penalty distribution
- Break tracking + threshold alerts (🎉 break celebration at `BREAK_ALERT_THRESHOLD`, SNOOKER-1)
- Event log for each set (`ball`, `foul`, `end_turn`)
- Undo (up to 20 snapshots)
- Set saving, new set flow, end-session flow
- Ranking points + raw-score tiebreaker
- Full history browsing (sessions/sets/events/breaks/durations)
- Bubble tea debt creation, mark-as-paid, and chain transfer
- GitHub → Gitea mirror sync trigger

---

## Project Structure

```text
backend/
  main.py          FastAPI API for sessions, scoring, history, debts, mirror sync
engine/
  score.py         Pure scoring rules
  session.py       Session/set state and logic
db/
  database.py      PostgreSQL persistence
frontend/
  src/App.jsx      React UI for all gameplay/history/debt flows
  src/App.css
web.py             FastAPI runner (uvicorn)
config.py          Env config, fixed players, break alert threshold
```

---

## Full Mode Score Input Flow

In the active set view (full mode), score entry is now:

1. Click the player name
2. Click the ball
3. Click **Submit**

The frontend will auto-advance turn order in the background before posting the ball if the selected player is not currently up, so break history remains grouped by consecutive scoring entries.

> Caveat: Event logs can contain extra auto-generated `end_turn` events due to this assisted input flow, so use break history and scores as the primary source of truth.

## Full-Mode Player Order (SNOOKER-3)

When a full-mode session begins, the backend picks three random
parameters and persists them for the life of the session:

1. A random bijection between participating players and the letters
   `A`/`B`/`C`/`D` (only as many letters as there are players).
2. A random `break_order` permutation of those letters — this drives
   which player *breaks first* on each set.
3. A random starting index into the hardcoded playing-order table
   below.

For each new set the backend reads the next hardcoded order (cycling
through the table), translates letters to real players via the
bijection, and then rotates so the player assigned to
`break_order[set_count % n]` is first. This guarantees no two
adjacent sets share the same first player while still cycling
deterministically through the hardcoded orders themselves.

Hardcoded tables (from SNOOKER-3):

| Players | Orders (in cycle) |
| --- | --- |
| 2 | `AB` |
| 3 | `ABC`, `ACB` |
| 4 | `ABCD`, `ABDC`, `ACBD`, `ACDB`, `ADBC`, `ADCB` |

> Note: 2-player sessions have only one hardcoded order. Break-order
> rotation alone produces AB / BA alternation between sets.
>
> Note: 3-player sessions cycle through the literal `[ABC, ACB]`
> pair from the ticket. Break rotation still applies on top — the
> third set's first player will not match the first set's.

Record mode ignores the ordering scheme; players enter final scores
directly, so the order column simply mirrors `config.PLAYERS`.

Any full-mode session that was active *before* this change was loaded
without a `player_mapping` and is silently dropped on the next
backend start (historical sets in the DB are preserved). A one-time
toast in the UI informs the user to start a fresh session.

---

## Setup

### 1) Database

Create schema once:

```sql
CREATE SCHEMA snooker;
```

### 2) Environment

```bash
cp .env.example .env
```

Set at least:

```env
DATABASE_URL=postgresql://user:password@host:5432/dbname
FRONTEND_ORIGINS=http://localhost:5173
```

Optional mirror sync settings:

```env
GITEA_URL=https://git.19371928.xyz
GITEA_TOKEN=...
GITEA_MIRROR_REPO=automation/discord-snooker-bot-github-mirror
```

Edit `config.py` for fixed player names and break alert threshold.

### 3) Backend

```bash
pip install -r requirements.txt
python web.py
```

Backend runs on `http://localhost:8000`.

### 4) Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs on `http://localhost:5173` and calls `http://localhost:8000/api` by default.

To override backend URL:

```bash
VITE_API_BASE=http://localhost:8000/api npm run dev
```

---

## API Overview

Key endpoints:

- `GET /api/meta`
- `POST /api/sessions`
- `GET /api/sessions/active`
- `POST /api/sessions/{id}/ball`
- `POST /api/sessions/{id}/end-turn`
- `POST /api/sessions/{id}/foul`
- `POST /api/sessions/{id}/undo`
- `POST /api/sessions/{id}/record-scores`
- `POST /api/sessions/{id}/new-set`
- `POST /api/sessions/{id}/end`
- `GET /api/history`
- `GET /api/debts`
- `POST /api/debts/{id}/pay`
- `POST /api/debts/pay-by-date`
- `POST /api/debts/transfer`
- `POST /api/mirror-sync`
