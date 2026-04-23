# 🎱 Snooker Web App (React + FastAPI)

This project rewrites the original Discord bot into a web application:

- **Frontend:** React (Vite)
- **Backend:** FastAPI
- **Database:** PostgreSQL (`snooker` schema via `asyncpg`)

All core game features from the bot are implemented in the web app:

- Full Mode (ball-by-ball scoring)
- Record Mode (set total entry)
- 2–4 player sessions with fixed player pool (`config.PLAYERS`)
- Non-repeating shuffled player-order permutations for 3–4 players
- Foul handling (intentional/unintentional) with correct penalty distribution
- Break tracking + threshold alerts
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

