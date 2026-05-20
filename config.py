import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
GUILD_ID = int(os.getenv("GUILD_ID")) if os.getenv("GUILD_ID") else None
FRONTEND_ORIGINS = [
    origin.strip()
    for origin in os.getenv("FRONTEND_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]

# Gitea mirror sync — used by /sync command
GITEA_URL = os.getenv("GITEA_URL", "https://git.19371928.xyz")
GITEA_TOKEN = os.getenv("GITEA_TOKEN")                       # API token with repo write scope
GITEA_MIRROR_REPO = os.getenv(
    "GITEA_MIRROR_REPO", "automation/discord-snooker-bot-github-mirror"
)

# Fixed player names — edit these to match your group
PLAYERS = ["Anson", "Desmond", "Justin", "Tung"]

# Minimum break total to trigger a "break alert" message in the channel (full mode only)
BREAK_ALERT_THRESHOLD = 10
