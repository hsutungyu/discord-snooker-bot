import asyncio
import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

import config
from db.database import init_db

load_dotenv()

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash command(s)")
    except Exception as e:
        print(f"Failed to sync commands: {e}")


async def main():
    if not config.DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set in .env")
    await init_db(config.DATABASE_URL)
    async with bot:
        await bot.load_extension("cogs.snooker")
        await bot.start(config.DISCORD_TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
