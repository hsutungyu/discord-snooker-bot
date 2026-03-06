import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

# Fixed player names — edit these to match your group
PLAYERS = ["Alice", "Bob", "Charlie", "Dave"]
