# Copilot Instructions

## Tech Stack

- **Python 3.11+** with **discord.py 2.x** (slash commands via `app_commands`, UI via `discord.ui`)
- **SQLite** via `aiosqlite` for async persistence
- **python-dotenv** for env config

## Running the Bot

```bash
pip install -r requirements.txt
cp .env.example .env   # add DISCORD_TOKEN
python bot.py
```

Edit `config.py` to set the 4 fixed player names before running.

## Project Structure

```
bot.py           # entry point: loads extension, syncs slash commands
config.py        # DISCORD_TOKEN + fixed PLAYERS list
engine/
  score.py       # pure logic: BALL_VALUES, foul_penalty, distribute_penalty
  session.py     # SnookerSession + SetState dataclasses, permutation cycling
db/
  database.py    # aiosqlite: init_db, save_session, save_set, end_session
cogs/
  snooker.py     # all Discord UI: Views, Buttons, /snooker command
data/            # SQLite DB file (git-ignored)
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

## Architecture

- **Discord interaction layer** (`cogs/snooker.py`): slash command `/snooker` to start; all subsequent interaction via button Views. Active sessions stored in `active_sessions: dict[channel_id, SnookerSession]` (in-memory; lost on restart).
- **View hierarchy**: `PlayerSelectView` → `ScoreboardView` ↔ `FoulPlayerSelectView` → `FoulBallSelectView`. All views call `interaction.response.edit_message()` to update in place.
- **Session state** (`engine/session.py`): `SnookerSession` holds players, completed sets, current `SetState`, and the permutation pool. `SetState` holds per-player scores and current player index for one set.
- **Persistence** (`db/database.py`): sessions and sets saved to SQLite. Sets are saved on "New Set" and "End Session"; session is marked ended on "End Session".
- **Score engine** (`engine/score.py`): stateless pure functions. No Discord dependencies.

## Key Conventions

- Player order permutations for a session should be pre-generated and cycled through; generate the next cycle when the current one is exhausted.
- Penalty distribution uses **ceiling division**: `math.ceil(foul_penalty(ball) / remaining_player_count)` per remaining player. `foul_penalty` = `max(4, ball_value)`.
- A "set" is fully saved before starting the next one; in-progress set state lives in `SnookerSession.current_set`.
- The 4 players are fixed (configured in `config.py`, not dynamic registration).
- All Discord Views are constructed fresh on each button press and passed to `edit_message` — no view mutation between interactions.
- `ScoreboardView` button layout: Row 0 = red/yellow/green/brown/blue, Row 1 = pink/black/End Turn, Row 2 = Foul/New Set/End Session.
