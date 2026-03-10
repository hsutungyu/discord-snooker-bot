import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
GUILD_ID = int(os.getenv("GUILD_ID")) if os.getenv("GUILD_ID") else None

# Fixed player names — edit these to match your group
PLAYERS = ["Anson", "Desmond", "Justin", "Tung"]

# Minimum break total to trigger a "break alert" message in the channel (full mode only)
BREAK_ALERT_THRESHOLD = 10
