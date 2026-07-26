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
  order.py       Hardcoded playing-order tables + PlayerMapping (SNOOKER-3)
  session.py     SnookerSession + SetState, player_mapping + break rotation, break/event/undo state
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

### Player Order (SNOOKER-3, full mode only)

- At session start the backend picks a random player↔letter bijection
  over A/B/C/D, a random `break_order` permutation, and a random start
  index into the hardcoded order table (2p: `[AB]`; 3p: `[ABC, ACB]`;
  4p: `[ABCD, ABDC, ACBD, ACDB, ADBC, ADCB]`).
- Each new set rotates the current hardcoded order so the next
  break-order player is first. Adjacent sets never share the same
  first player.
- Record mode uses `list(self.players)` — no rotation.

### Ranking + Tiebreak

- Set ranking points: 1st gets N−1 down to last gets 0.
- Ties share the higher rank’s points.
- Session standings sort by total ranking points, then total raw score.

### Break Tracking

- `current_break` accumulates live balls.
- Break is flushed on end-turn/foul/set end.
- Break celebration is raised when break total ≥ `BREAK_ALERT_THRESHOLD` (SNOOKER-1).
  Message is built by `engine.session.build_break_celebration_message`
  (🎉 + 🥳 + "Break celebration!"), shared by the FastAPI backend, the
  Discord notification bot, and the legacy Discord cog.

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
