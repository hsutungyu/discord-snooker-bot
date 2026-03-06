# 🎱 Discord Snooker Bot

A Discord bot that acts as a digital scoreboard for snooker sessions. Designed for a fixed group of up to 4 players, it handles scoring, foul distribution, and player order — all through Discord's button UI with no manual score entry.

## Features

- **2-player mode** — standard snooker rules (fouls go directly to the opponent)
- **3–4 player mode** — players take individual turns; foul penalties are split equally among non-fouling players (rounded up)
- **Smart player order** — turn order is shuffled each set and never repeats a permutation until all have been used
- **Foul flow** — select who fouled and on which ball; points are distributed automatically
- **Persistent scores** — every set and session is saved to a local SQLite database
- **Fully button-driven** — no text commands needed after starting a session

## Screenshots

```
🎱 Snooker Session — 2024-03-06
────────────────────────────────
Total Scores
  ▶ Alice         47 pts   ← current turn
    Bob           32 pts
    Charlie       18 pts

Set 2 Scores
    Alice         12
    Bob            8
    Charlie        5

Current Turn: Alice
────────────────────────────────
[🔴 Red(1)] [🟡 Yellow(2)] [🟢 Green(3)] [🟤 Brown(4)] [🔵 Blue(5)]
[🩷 Pink(6)] [⚫ Black(7)] [End Turn ↩]
[🚫 Foul]   [➡️ New Set]  [🏁 End Session]
```

## Setup

### 1. Create a Discord bot

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications) and create a new application.
2. Under **Bot**, enable the **Message Content Intent** (not strictly required but recommended).
3. Under **OAuth2 → URL Generator**, select scopes: `bot` + `applications.commands`. Under Bot Permissions, select `Send Messages` and `Read Message History`.
4. Copy your **Bot Token**.

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure

```bash
cp .env.example .env
```

Edit `.env` and set your bot token:

```
DISCORD_TOKEN=your_bot_token_here
```

Edit `config.py` to set the real names of your 4 players:

```python
PLAYERS = ["Alice", "Bob", "Charlie", "Dave"]
```

### 4. Run

```bash
python bot.py
```

The bot will print `Logged in as ...` and sync slash commands on startup. Slash commands may take up to an hour to appear globally; for instant availability during testing, [register them to a specific guild](https://discordpy.readthedocs.io/en/stable/interactions/api.html#discord.app_commands.CommandTree.sync).

## Usage

### Starting a session

Use the slash command in any channel the bot has access to:

```
/snooker
```

The bot posts a player selection message. Toggle players in or out (all 4 are selected by default), then press **▶️ Start Session**.

### Scoring

The scoreboard shows the **current player's turn** highlighted with `▶`. Press any ball button to add that ball's points to the current player:

| Button | Points |
|--------|--------|
| 🔴 Red | 1 |
| 🟡 Yellow | 2 |
| 🟢 Green | 3 |
| 🟤 Brown | 4 |
| 🔵 Blue | 5 |
| 🩷 Pink | 6 |
| ⚫ Black | 7 |

Press **End Turn ↩** when the current player's break ends to pass to the next player.

### Recording a foul

1. Press **🚫 Foul**
2. Select the player who committed the foul
3. Select the ball that was fouled on

The penalty (`max(4, ball value)`) is automatically distributed among the remaining players using ceiling division. For example, a black foul (7 pts) with 3 players awards `⌈7/2⌉ = 4 pts` to each of the 2 non-fouling players.

### Managing sets

- **➡️ New Set** — saves the current set scores and starts a new set with a freshly shuffled player order
- **🏁 End Session** — saves the final set, records the session to the database, and displays the final leaderboard

### Player order (3–4 players)

Each set uses a different permutation of the player order. The bot cycles through all possible permutations before repeating any, ensuring fair variety across sets.

## Data

Session and set scores are persisted to `data/snooker.db` (SQLite). The file is created automatically on first run.

```
sessions  — session id, date, players, start/end timestamps
sets      — set scores, player order, completion time, linked to session
```

## Project Structure

```
bot.py          Entry point
config.py       Bot token + player names
engine/
  score.py      Ball values, foul penalty, distribution logic
  session.py    Session + set state, permutation cycling
db/
  database.py   SQLite persistence (aiosqlite)
cogs/
  snooker.py    All Discord UI: Views, Buttons, /snooker command
data/           SQLite database file (auto-created, git-ignored)
```
