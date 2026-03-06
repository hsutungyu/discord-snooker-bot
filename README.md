# 🎱 Discord Snooker Bot

A Discord bot that acts as a digital scoreboard for snooker sessions. Designed for a fixed group of up to 4 players, it handles scoring, foul distribution, player order, and ranking — all through Discord's button UI with no manual score entry.

## Features

- **Two scoring modes** — Full Mode (ball-by-ball in real time) or Record Mode (enter totals at the end of each set)
- **2-player mode** — standard snooker rules (fouls go directly to the opponent)
- **3–4 player mode** — players take individual turns; foul penalties are split equally among non-fouling players (rounded up)
- **Smart player order** — turn order is shuffled each set and never repeats a permutation until all have been used
- **Per-set ranking points** — at the end of each set, players are ranked by score: 1st gets N pts, last gets 1 pt (N = number of players); ties share the higher rank
- **Foul flow** — select who fouled and on which ball; points distributed automatically
- **Session history** — `/history` command to browse all past sessions with standings and per-set breakdowns
- **Bubble tea debt tracking** — last-place player owes a bubble tea to the winner; `/debt` command to view and settle debts
- **PostgreSQL persistence** — all sessions, sets, and debts stored in a remote PostgreSQL database
- **Fully button-driven** — no text commands needed after starting a session

## Screenshots

```
🎱 Snooker Session — 2024-03-06
────────────────────────────────
Ranking Points (1 set done)
  ▶ Alice          3 rp   ← current turn
    Bob            2 rp
    Charlie        1 rp

Set 1 Results
    Alice    80 pts  +3 rp
    Bob      55 pts  +2 rp
    Charlie  30 pts  +1 rp

Set 2 (in progress)
    Alice     12
    Bob        8
    Charlie    5

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

### 2. Set up PostgreSQL

Create a `snooker` schema on your PostgreSQL database. The bot will create all tables automatically on first run:

```sql
CREATE SCHEMA snooker;
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure

```bash
cp .env.example .env
```

Edit `.env`:

```
DISCORD_TOKEN=your_bot_token_here
DATABASE_URL=postgresql://user:password@host:5432/dbname
```

Edit `config.py` to set the real names of your 4 players:

```python
PLAYERS = ["Alice", "Bob", "Charlie", "Dave"]
```

### 5. Run

```bash
python bot.py
```

The bot will print `Logged in as ...` and sync slash commands on startup. Slash commands may take up to an hour to appear globally; for instant availability during testing, [register them to a specific guild](https://discordpy.readthedocs.io/en/stable/interactions/api.html#discord.app_commands.CommandTree.sync).

## Docker

The image is hosted on the project's Gitea container registry at `git.19371928.xyz`.

### Build and push

Use the included PowerShell script to build and push to the registry:

```powershell
.\build-and-push.ps1
```

By default this tags the image as `latest`. You can pass an explicit tag:

```powershell
.\build-and-push.ps1 -Tag 1.2.3
```

You will be prompted for your Gitea credentials if you are not already logged in (`docker login git.19371928.xyz`).

The full image reference is:

```
git.19371928.xyz/automation/discord-snooker:<tag>
```

### Run locally from the registry

```bash
docker pull git.19371928.xyz/automation/discord-snooker:latest
docker run --env-file .env git.19371928.xyz/automation/discord-snooker:latest
```

## Kubernetes

Create a secret with your credentials, then deploy with a single-replica `Deployment`. Discord bots must not run more than one replica at a time.

```bash
kubectl create secret generic snooker-bot-secret \
  --from-literal=DISCORD_TOKEN=your_token \
  --from-literal=DATABASE_URL=postgresql://user:password@host:5432/dbname
```

Example `Deployment` snippet:

```yaml
spec:
  replicas: 1
  template:
    spec:
      containers:
        - name: snooker-bot
          image: git.19371928.xyz/automation/discord-snooker:latest
          envFrom:
            - secretRef:
                name: snooker-bot-secret
```

## Usage

### Starting a session

```
/snooker
```

Toggle players in or out (all 4 selected by default), press **▶️ Start Session**, then choose a scoring mode:

- **🎱 Full Mode** — press ball buttons in real time as each ball is potted
- **📝 Record Mode** — press **📝 Enter Scores** at the end of each set to type in each player's final score

### Scoring (Full Mode)

The scoreboard shows the **current player's turn** highlighted with `▶`. Press any ball button to add points:

| Button | Points |
|--------|--------|
| 🔴 Red | 1 |
| 🟡 Yellow | 2 |
| 🟢 Green | 3 |
| 🟤 Brown | 4 |
| 🔵 Blue | 5 |
| 🩷 Pink | 6 |
| ⚫ Black | 7 |

Press **End Turn ↩** to pass to the next player.

### Recording a foul (Full Mode)

1. Press **🚫 Foul**
2. Select the player who committed the foul
3. Select the ball that was fouled on

The penalty (`max(4, ball value)`) is distributed among the remaining players using ceiling division. For example, a black foul (7 pts) with 3 players awards `⌈7/2⌉ = 4 pts` to each of the 2 non-fouling players.

### Ranking points

At the end of each set, players are awarded ranking points based on their score:

| Finish | Ranking Points (4 players) |
|--------|--------------------------|
| 1st | 4 rp |
| 2nd | 3 rp |
| 3rd | 2 rp |
| 4th | 1 rp |

Tied players both receive the higher rank's points. The session leaderboard shows cumulative ranking points across all completed sets.

### Managing sets

- **➡️ New Set** — saves the current set and starts a new one with a freshly shuffled player order
- **🏁 End Session** — saves the final set and displays the overall leaderboard

### Viewing history

```
/history
```

Browse all completed sessions using the **◀ Newer / Older ▶** buttons. Each page shows the final standings and a per-set ranking point breakdown.

### Bubble tea debts

```
/debt
```

At the end of every session, the last-place player owes a bubble tea to the first-place player. The `/debt` command shows all outstanding and recently paid debts. Press **✅ Mark as Paid** to settle a debt.

## Data

All data is stored in the `snooker` schema of your PostgreSQL database.

```
snooker.sessions  — session id, date, players, start/end timestamps
snooker.sets      — set scores, ranking points, player order, per session
snooker.debts     — bubble tea debts, paid status, per session
```

## Project Structure

```
bot.py          Entry point
config.py       Bot token, database URL, player names
engine/
  score.py      Ball values, foul penalty, ranking_points logic
  session.py    Session + set state, permutation cycling
db/
  database.py   PostgreSQL persistence (asyncpg connection pool)
cogs/
  snooker.py    All Discord UI: Views, Buttons, /snooker, /history, /debt
Dockerfile      Multi-stage build (builder + lean runtime)
.dockerignore
```

