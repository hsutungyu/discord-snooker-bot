# 🎱 Discord Snooker Bot

A Discord bot that acts as a digital scoreboard for snooker sessions. Designed for a fixed group of up to 4 players, it handles scoring, foul distribution, player order, ranking, and break tracking — all through Discord's button/select UI with no manual score entry.

## Features

- **Two scoring modes** — Full Mode (ball-by-ball in real time) or Record Mode (enter totals at the end of each set)
- **2-player mode** — standard snooker rules (fouls go directly to the opponent)
- **3–4 player mode** — players take individual turns; foul penalties are split equally among non-fouling players (rounded up)
- **Smart player order** — turn order is shuffled each set and never repeats a permutation until all have been used
- **Per-set ranking points** — 1st gets N−1 pts down to last getting 0 pts (N = number of players); ties share the higher rank. **Tied ranking points at session end are broken by total raw score across all sets.**
- **Single-step foul input** — select fouling player and ball in one view with dropdowns, then confirm
- **Break tracking** — current live break shown in real time; completed breaks recorded per player per set
- **Break alerts** — bot sends a channel message when a break reaches the configured threshold (default: 10)
- **Set event log** — every ball, foul, and end-turn recorded chronologically (like a football live tracker); shown as a live feed on the scoreboard and full log in `/history`
- **Set duration** — time taken to finish each set tracked and displayed
- **Undo** — undo any ball, foul, or end-turn action (up to 20 steps per set)
- **End session confirmation** — confirmation prompt before ending a session to prevent misclicks
- **Multi-user safe** — per-session asyncio lock + deferred responses prevent "interaction failed" when two users operate the bot simultaneously
- **Session history** — `/history` command to browse all past sessions with standings, per-set breakdowns, break history, event logs, and durations
- **Bubble tea debt tracking** — last-place player owes a bubble tea to the winner; `/debt` command to view and settle debts
- **PostgreSQL persistence** — all sessions, sets, breaks, events, and debts stored in a remote PostgreSQL database
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
    ⏱ Duration: 14m 22s
    Alice: 🔴 🔴 🩷 🔵 (14)

Set 2 (in progress)
    Alice     12
    Bob        8
    Charlie    5

Current Turn: Alice
Break: 🔴 🩷 (7)

📋 Set Log
  1. Alice        🔴 Red (+1)
  2. Alice        🩷 Pink (+6)
  3. ↩ End turn   (Alice)
  4. 🚫 Bob        foul on 🔵 Blue (pen 5, +3 ea → Alice, Charlie)
────────────────────────────────
[🔴 Red(1)] [🟡 Yellow(2)] [🟢 Green(3)] [🟤 Brown(4)] [🔵 Blue(5)]
[🩷 Pink(6)] [⚫ Black(7)] [End Turn ↩]
[🚫 Foul]   [➡️ New Set]  [🏁 End Session]  [↩ Undo]
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
GUILD_ID=your_discord_server_id
```

> **Getting your Guild ID:** Enable Developer Mode in Discord (Settings → Advanced → Developer Mode), then right-click your server icon and select **Copy Server ID**.

> **Why `GUILD_ID`?** Slash commands registered to a specific guild are available instantly to all members. Without it, commands sync globally and can take up to an hour to appear.

Edit `config.py` to set the real names of your 4 players and optionally the break alert threshold:

```python
PLAYERS = ["Alice", "Bob", "Charlie", "Dave"]
BREAK_ALERT_THRESHOLD = 10  # minimum break total to trigger a channel alert
```

### 5. Run

```bash
python bot.py
```

The bot will print `Logged in as ...` and sync slash commands on startup.

## Docker

The image is hosted on the project's Gitea container registry at `git.19371928.xyz`.

### Build and push

Use the included script to build and push to the registry.

**PowerShell (Windows):**
```powershell
.\build-and-push.ps1            # tag: latest
.\build-and-push.ps1 -Tag 1.2.3 # tag: 1.2.3 + latest
```

**Bash (Linux/macOS):**
```bash
chmod +x build-and-push.sh
./build-and-push.sh             # tag: latest
./build-and-push.sh 1.2.3       # tag: 1.2.3 + latest
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

A ready-to-use `deploy.yaml` manifest is included. It deploys a single-replica `Deployment` to the `automation` namespace using the Gitea registry image. Discord bots must not run more than one replica at a time.

**1. Create the credentials secret:**

```bash
kubectl create secret generic discord-snooker-secret \
  --namespace automation \
  --from-literal=DISCORD_TOKEN=your_token \
  --from-literal=DATABASE_URL=postgresql://user:password@host:5432/dbname \
  --from-literal=GUILD_ID=your_discord_server_id
```

**2. Create the registry pull secret:**

```bash
kubectl create secret docker-registry gitea-registry-secret \
  --namespace automation \
  --docker-server=git.19371928.xyz \
  --docker-username=your_username \
  --docker-password=your_password
```

**3. Apply the manifest:**

```bash
kubectl apply -f deploy.yaml
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

Press **End Turn ↩** to pass to the next player. The current live break (balls potted this turn and total) is shown under **Current Turn**.

If the break total meets or exceeds `BREAK_ALERT_THRESHOLD`, the bot sends a break alert message in the channel showing the player, total, and balls in order.

### Recording a foul (Full Mode)

Press **🚫 Foul** — a single view appears with two dropdowns:
1. Select the player who committed the foul
2. Select the ball that was fouled on

Then press **✅ Apply Foul** to confirm. The penalty (`max(4, ball value)`) is distributed among the remaining players using ceiling division.

### Undo

Press **↩ Undo** to reverse the last action (ball pot, foul, or end-turn). Up to 20 steps can be undone within a set.

### Ranking points

At the end of each set, players are awarded ranking points:

| Finish | Ranking Points (4 players) |
|--------|--------------------------|
| 1st | 3 rp |
| 2nd | 2 rp |
| 3rd | 1 rp |
| 4th | 0 rp |

Tied players both receive the higher rank's points. If two players finish a session with equal total ranking points, the player with the higher total raw score (points potted across all sets) is ranked higher.

### Managing sets

- **➡️ New Set** — saves the current set (with scores, breaks, event log, and duration) and starts a new one
- **🏁 End Session** — prompts for confirmation, then saves the final set and displays the overall leaderboard

### Viewing history

```
/history
```

Browse all completed sessions using the **◀ Newer / Older ▶** buttons. Each page shows final standings, per-set score breakdowns with durations and break history, and the full chronological event log per set.

### Bubble tea debts

```
/debt
```

At the end of every session, the last-place player owes a bubble tea to the first-place player. The `/debt` command shows all outstanding and recently paid debts. Press **✅ Mark as Paid** to settle a debt.

## Data

All data is stored in the `snooker` schema of your PostgreSQL database.

```
snooker.sessions  — session id, date, players, start/end timestamps
snooker.sets      — scores, ranking points, player order, break history,
                    event log, set duration — per session
snooker.debts     — bubble tea debts, paid status, per session
```

## Project Structure

```
bot.py          Entry point
config.py       Bot token, database URL, player names, BREAK_ALERT_THRESHOLD
engine/
  score.py      Ball values, foul penalty, ranking_points logic
  session.py    SnookerSession + SetState: permutation cycling, break tracking,
                event log, undo stack, set duration, per-session asyncio lock
db/
  database.py   PostgreSQL persistence (asyncpg connection pool)
cogs/
  snooker.py    All Discord UI: Views, Buttons, Selects, /snooker, /history, /debt
deploy.yaml     Kubernetes Deployment manifest (namespace: automation)
Dockerfile      Multi-stage build (builder + lean runtime)
.dockerignore
```
