import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

# Fixed player names — edit these to match your group
PLAYERS = ["Anson", "Desmond", "Justin", "Tung"]
