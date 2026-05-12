import os
from dotenv import load_dotenv

load_dotenv()

import commands  # noqa: F401 — importing this module registers all slash commands
from bot import bot
from game import load_and_restore


@bot.event
async def on_ready():
    await load_and_restore()
    await bot.tree.sync()
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print("Slash commands synced.")


if __name__ == "__main__":
    bot.run(os.getenv("DISCORD_TOKEN"))
