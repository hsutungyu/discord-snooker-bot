import asyncio
import logging
import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

import config
from db.database import init_db

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    try:
        synced = await bot.tree.sync()
        log.info("Synced %d slash command(s)", len(synced))
    except Exception as e:
        log.exception("Failed to sync commands: %s", e)


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: Exception):
    log.exception("Unhandled app command error in /%s: %s",
                  interaction.command.name if interaction.command else "?", error)
    msg = "An unexpected error occurred."
    try:
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
    except Exception:
        pass


async def main():
    if not config.DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set in .env")
    await init_db(config.DATABASE_URL)
    async with bot:
        await bot.load_extension("cogs.snooker")
        await bot.start(config.DISCORD_TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
