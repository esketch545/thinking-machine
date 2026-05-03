import discord
from discord import app_commands
from typing import Optional

from bot import bot
from models import GameSession, game_sessions, save_state
from game import run_next_pick
from views import FactionPoolSelect


@bot.tree.command(name="newgame", description="Start a new Dune faction draft")
@app_commands.describe(player_count="Solo testing: pre-fill this many seats so one person can run the full draft (1–5)")
async def newgame(interaction: discord.Interaction, player_count: Optional[app_commands.Range[int, 1, 5]] = None):
    gid = interaction.guild_id
    existing = game_sessions.get(gid)
    if existing and existing.state != "done":
        await interaction.response.send_message(
            "A game is already running. Use `/endgame` to cancel it.", ephemeral=True
        )
        return

    session = GameSession(guild_id=gid, host_id=interaction.user.id)

    if player_count is not None:
        session.player_ids = [interaction.user.id] * player_count
        session.test_mode = True

    game_sessions[gid] = session

    test_note = (
        f"\n\n**Solo test mode — {player_count} seat(s) pre-filled.** "
        "Select the faction pool, then use `/startdraft`."
    ) if player_count else ""

    embed = discord.Embed(
        title="New Dune Game",
        description=f"Select which factions to include in the draw pool. You must select at least 3.{test_note}",
        color=discord.Color.blurple(),
    )
    await interaction.response.send_message(embed=embed, view=FactionPoolSelect(session))


@bot.tree.command(name="join", description="Join the current Dune game")
async def join(interaction: discord.Interaction):
    gid = interaction.guild_id
    session = game_sessions.get(gid)

    if not session or session.state == "done":
        await interaction.response.send_message(
            "No active game. Start one with `/newgame`.", ephemeral=True
        )
        return
    if session.test_mode:
        await interaction.response.send_message(
            "This game is in solo test mode — seats are pre-filled. Use `/startdraft` when ready.",
            ephemeral=True,
        )
        return
    if session.state != "joining":
        await interaction.response.send_message(
            "The game is not accepting players right now.", ephemeral=True
        )
        return
    if len(session.player_ids) >= 5:
        await interaction.response.send_message(
            "The game is full (5 players max).", ephemeral=True
        )
        return
    if interaction.user.id in session.player_ids:
        await interaction.response.send_message("You've already joined!", ephemeral=True)
        return

    session.player_ids.append(interaction.user.id)
    save_state()

    guild = interaction.guild
    lines = []
    for i, uid in enumerate(session.player_ids):
        m = guild.get_member(uid)
        name = m.display_name if m else f"<@{uid}>"
        lines.append(f"{i + 1}. {name}")

    embed = discord.Embed(
        title="Player Joined!",
        description=(
            f"**{interaction.user.display_name}** joined.\n\n"
            f"**Players ({len(session.player_ids)}/5):**\n" + "\n".join(lines)
        ),
        color=discord.Color.green(),
    )
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="startdraft", description="Begin the faction draft (host only)")
async def startdraft(interaction: discord.Interaction):
    gid = interaction.guild_id
    session = game_sessions.get(gid)

    if not session:
        await interaction.response.send_message("No active game.", ephemeral=True)
        return
    if interaction.user.id != session.host_id:
        await interaction.response.send_message("Only the host can start the draft.", ephemeral=True)
        return
    if session.state != "joining":
        await interaction.response.send_message("The game is not ready to start.", ephemeral=True)
        return
    if not session.player_ids:
        await interaction.response.send_message("At least 1 player must join before starting.", ephemeral=True)
        return
    if len(session.faction_pool) < 3:
        await interaction.response.send_message("The faction pool needs at least 3 factions.", ephemeral=True)
        return

    session.state = "drafting"
    session.channel_id = interaction.channel_id
    save_state()

    await interaction.response.send_message(
        embed=discord.Embed(
            title="The Draft Begins!",
            description="Faction selection has started. May the best strategist win.",
            color=discord.Color.blurple(),
        )
    )
    await run_next_pick(interaction.channel, session, interaction.guild)


@bot.tree.command(name="endgame", description="Cancel the current game (host only)")
async def endgame(interaction: discord.Interaction):
    gid = interaction.guild_id
    session = game_sessions.get(gid)

    if not session:
        await interaction.response.send_message("No active game to cancel.", ephemeral=True)
        return
    if interaction.user.id != session.host_id:
        await interaction.response.send_message("Only the host can cancel the game.", ephemeral=True)
        return

    del game_sessions[gid]
    save_state()
    await interaction.response.send_message("Game cancelled.")


@bot.tree.command(name="players", description="Show the current player lineup")
async def players_cmd(interaction: discord.Interaction):
    gid = interaction.guild_id
    session = game_sessions.get(gid)

    if not session:
        await interaction.response.send_message("No active game.", ephemeral=True)
        return

    guild = interaction.guild
    if not session.player_ids:
        player_list = "No players yet."
    else:
        lines = []
        for i, uid in enumerate(session.player_ids):
            m = guild.get_member(uid)
            base = m.display_name if m else f"<@{uid}>"
            label = f"{base} (Seat {i + 1})" if session.test_mode and session.player_ids.count(uid) > 1 else base
            lines.append(f"{i + 1}. {label}")
        player_list = "\n".join(lines)

    embed = discord.Embed(
        title="Current Players",
        description=player_list,
        color=discord.Color.blurple(),
    )
    await interaction.response.send_message(embed=embed)
