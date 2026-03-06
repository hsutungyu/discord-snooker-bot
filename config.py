import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

# Fixed player names — edit these to match your group
PLAYERS = ["Anson", "Desmond", "Justin", "Tung"]
