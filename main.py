import os
from dotenv import load_dotenv

load_dotenv()

import discord
import commands  # noqa: F401 — importing this module registers all slash commands
from bot import bot
from game import load_and_restore


TEST_GUILD_ID = 0  # TODO: replace with your server ID

@bot.event
async def on_ready():
    await load_and_restore()
    if TEST_GUILD_ID:
        guild = discord.Object(id=TEST_GUILD_ID)
        bot.tree.copy_global_to(guild=guild)
        await bot.tree.sync(guild=guild)
    else:
        await bot.tree.sync()
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print("Slash commands synced.")


if __name__ == "__main__":
    bot.run(os.getenv("DISCORD_TOKEN"))
