# Copilot Instructions

## Tech Stack

- **Python 3.11+** with **discord.py 2.x** (slash commands via `app_commands`, UI via `discord.ui`)
- **PostgreSQL** via `asyncpg` for async persistence
- **python-dotenv** for env config

## Running the Bot

```bash
pip install -r requirements.txt
cp .env.example .env   # add DISCORD_TOKEN and DATABASE_URL
python bot.py
```

Edit `config.py` to set the 4 fixed player names before running.

## Project Structure

```
bot.py           # entry point: loads extension, syncs slash commands
config.py        # DISCORD_TOKEN, DATABASE_URL, fixed PLAYERS list
engine/
  score.py       # pure logic: BALL_VALUES, foul_penalty, distribute_penalty, ranking_points
  session.py     # SnookerSession + SetState dataclasses, permutation cycling, total_raw_scores
db/
  database.py    # asyncpg pool: init_db, save_session, save_set, end_session, get_completed_sessions
cogs/
  snooker.py     # all Discord UI: Views, Buttons, /snooker, /history, /debt commands
deploy.yaml      # Kubernetes Deployment manifest (namespace: automation)
build-and-push.ps1 / .sh  # build + push image; auto-updates deploy.yaml with new tag
```

## Project Overview

A Discord bot that acts as a digital scoreboard for snooker sessions among 4 fixed players. Players interact entirely through Discord slash commands and button UI — no text-based score input.

## Domain Rules

### Scoring Modes

- **2 players**: Standard snooker rules.
- **3–4 players**: Each player takes turns individually. When a foul is committed, the penalty points are **shared equally among the remaining (non-fouling) players**, rounded **up** to the nearest integer per player.

### Player Order (3–4 players)

- Order is **shuffled per set** and must **not repeat** a previously used permutation until all permutations are exhausted.
- Example for 3 players (A, B, C): use ABC, CBA, ACB before repeating any order.

### Session Lifecycle

1. Bot activated via Discord slash command → opens a session tagged with the current date.
2. User selects number of players for this session (2–4).
3. Sets are played one at a time. Each set shows per-player ball buttons to increment scores.
4. Foul flow: user selects the fouling player and the ball — penalty points distributed to remaining players.
5. User can **start a new set** (saves current set) or **end the session** when done.
6. Session data (time, per-set scores) is **persisted**.

### Ranking Points & Tiebreaker

- At the end of each set, players are awarded ranking points: 1st gets N rp, last gets 1 rp (N = player count). Tied scores share the higher rank's points.
- At session end, players are sorted by **total ranking points**. If two players are tied on ranking points, the **total raw score (points potted) across all sets** is used as a tiebreaker.
- This tiebreaker applies to both the live end-of-session embed and the `/history` view.

## Architecture

- **Discord interaction layer** (`cogs/snooker.py`): slash command `/snooker` to start; all subsequent interaction via button Views. Active sessions stored in `active_sessions: dict[channel_id, SnookerSession]` (in-memory; lost on restart).
- **View hierarchy**: `PlayerSelectView` → `ScoreboardView` ↔ `FoulPlayerSelectView` → `FoulBallSelectView`. All views call `interaction.response.edit_message()` to update in place.
- **Session state** (`engine/session.py`): `SnookerSession` holds players, completed sets, current `SetState`, and the permutation pool. `SetState` holds per-player scores and current player index for one set. `total_raw_scores()` sums raw points potted across all completed sets.
- **Persistence** (`db/database.py`): sessions and sets saved to PostgreSQL (`snooker` schema). Sets are saved on "New Set" and "End Session"; session is marked ended on "End Session". `get_completed_sessions()` returns `ranking_totals` and `score_totals` per player.
- **Score engine** (`engine/score.py`): stateless pure functions. No Discord dependencies.

## Key Conventions

- Player order permutations for a session should be pre-generated and cycled through; generate the next cycle when the current one is exhausted.
- Penalty distribution uses **ceiling division**: `math.ceil(foul_penalty(ball) / remaining_player_count)` per remaining player. `foul_penalty` = `max(4, ball_value)`.
- A "set" is fully saved before starting the next one; in-progress set state lives in `SnookerSession.current_set`.
- The 4 players are fixed (configured in `config.py`, not dynamic registration).
- All Discord Views are constructed fresh on each button press and passed to `edit_message` — no view mutation between interactions.
- `ScoreboardView` button layout: Row 0 = red/yellow/green/brown/blue, Row 1 = pink/black/End Turn, Row 2 = Foul/New Set/End Session.
- History per-set breakdown shows **raw scores in playing order** (not ranking points).

## Deployment

- Docker image hosted at `git.19371928.xyz/automation/discord-snooker:<tag>`.
- Build scripts (`build-and-push.ps1` / `build-and-push.sh`) default to a UTC timestamp tag (`yyyyMMdd-HHmmss`) and automatically update the `image:` field in `deploy.yaml` after a successful push.
- Kubernetes `deploy.yaml` targets namespace `automation`. Requires secrets `discord-snooker-secret` (DISCORD_TOKEN, DATABASE_URL) and `gitea-registry-secret` (registry pull credentials).
- Always run `kubectl apply -f deploy.yaml` after building to roll out the new image.

## Agent Session Checklist

At the end of every agent session:
1. **Commit** all modified files with a descriptive message.
2. **Push** to `origin main` (`git -c credential.helper=manager push origin main`).
3. **Update `README.md`** if any user-facing behaviour, setup steps, or deployment instructions changed.
4. **Update this file** (`copilot-instructions.md`) if architecture, conventions, or domain rules changed.
