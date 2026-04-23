# Copilot Instructions

## Tech Stack

- **Backend:** Python 3.11+, FastAPI, asyncpg, python-dotenv
- **Frontend:** React (Vite)
- **Database:** PostgreSQL (`snooker` schema)

## Running the App

```bash
pip install -r requirements.txt
cp .env.example .env
python web.py
```

```bash
cd frontend
npm install
npm run dev
```

Edit `config.py` to set fixed player names and `BREAK_ALERT_THRESHOLD`.

## Project Structure

```text
backend/
  main.py        FastAPI endpoints (sessions, scoring, history, debts, mirror sync)
engine/
  score.py       BALL_VALUES, foul_penalty, distribute_penalty, ranking_points
  session.py     SnookerSession + SetState, permutation cycling, break/event/undo state
db/
  database.py    asyncpg pool + persistence for sessions/sets/debts
frontend/
  src/App.jsx    Main web UI covering full mode, record mode, history, debts
  src/App.css
web.py           Uvicorn runner for FastAPI
config.py        env + fixed PLAYERS + BREAK_ALERT_THRESHOLD + mirror-sync config
```

## Domain Rules

### Scoring Modes

- **2 players:** standard snooker penalty behavior.
- **3–4 players:** foul penalty is shared among non-fouling players via ceiling division.

### Player Order

- For 3–4 players, set order uses shuffled permutations with no repeats until permutation pool is exhausted.

### Ranking + Tiebreak

- Set ranking points: 1st gets N−1 down to last gets 0.
- Ties share the higher rank’s points.
- Session standings sort by total ranking points, then total raw score.

### Break Tracking

- `current_break` accumulates live balls.
- Break is flushed on end-turn/foul/set end.
- Break alert is raised when break total ≥ `BREAK_ALERT_THRESHOLD`.

### Event Log

- Every mutating action appends a set event (`ball`, `foul`, `end_turn`) with sequence numbers.

### Undo

- `SetState` snapshots mutable state before add-score, foul, and end-turn.
- Undo restores the latest snapshot, capped at 20.

## Architecture Notes

- Active sessions are in-memory in backend (`session_id -> LiveSession`) and guarded by per-session `asyncio.Lock`.
- Completed sessions/sets/debts are persisted in PostgreSQL.
- Frontend uses REST APIs only; no Discord interactions.
- `/api/mirror-sync` triggers GitHub→Gitea mirror sync using configured token.

## Agent Session Checklist

1. Commit modified files with a clear message.
2. Push via `report_progress` tool.
3. Update `README.md` for user-facing setup/behavior changes.
4. Update this file when architecture/rules/conventions change.
