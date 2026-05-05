import discord
from discord import app_commands
from typing import Optional

from bot import bot
from factions import FACTIONS
from models import GameSession, game_sessions, get_session, set_session, delete_session, save_state
from game import run_next_pick
from views import FactionPoolSelect


def _normalise(name: str) -> str:
    return name.strip().lower()


async def _active_drafts_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    drafts = game_sessions.get(interaction.guild_id, {})
    return [
        app_commands.Choice(name=name, value=name)
        for name, session in drafts.items()
        if session.state != "done" and current.lower() in name
    ][:25]


@bot.tree.command(name="newdraft", description="Start a new Dune faction draft")
@app_commands.describe(
    name="A short name for this draft (e.g. friday-night)",
    player_count="Solo testing: pre-fill this many seats so one person can run the full draft (1–5)",
)
async def newdraft(
    interaction: discord.Interaction,
    name: str,
    player_count: Optional[app_commands.Range[int, 1, 5]] = None,
):
    gid = interaction.guild_id
    draft_name = _normalise(name)

    if "::" in draft_name:
        await interaction.response.send_message("Draft name cannot contain `::`.", ephemeral=True)
        return

    existing = get_session(gid, draft_name)
    if existing and existing.state != "done":
        await interaction.response.send_message(
            f"A draft named **{draft_name}** is already running. Use `/enddraft` to cancel it.",
            ephemeral=True,
        )
        return

    session = GameSession(guild_id=gid, name=draft_name, host_id=interaction.user.id)
    session.faction_pool = set(FACTIONS.keys())  # all factions selected by default
    session.state = "joining"                     # immediately open for players to join

    if player_count is not None:
        session.player_ids = [interaction.user.id] * player_count
        session.test_mode = True

    set_session(session)
    save_state()

    test_note = (
        f"\n\n**Solo test mode — {player_count} seat(s) pre-filled.**"
    ) if player_count else ""

    embed = discord.Embed(
        title=f"Draft Created — {draft_name}",
        description=(
            f"The draft is open! Players can join with `/joindraft name:{draft_name}`.\n\n"
            f"All factions are in the pool by default. Use the selector below to remove any before starting.{test_note}"
        ),
        color=discord.Color.green(),
    )
    await interaction.response.send_message(embed=embed, view=FactionPoolSelect(session))


@bot.tree.command(name="joindraft", description="Join a Dune draft")
@app_commands.describe(name="Name of the draft to join")
@app_commands.autocomplete(name=_active_drafts_autocomplete)
async def joindraft(interaction: discord.Interaction, name: str):
    gid = interaction.guild_id
    draft_name = _normalise(name)
    session = get_session(gid, draft_name)

    if not session or session.state == "done":
        await interaction.response.send_message(
            f"No active draft named **{draft_name}**. Start one with `/newdraft`.", ephemeral=True
        )
        return
    if session.test_mode:
        await interaction.response.send_message(
            "This draft is in solo test mode — seats are pre-filled. Use `/startdraft` when ready.",
            ephemeral=True,
        )
        return
    if session.state == "drafting":
        await interaction.response.send_message(
            f"Draft **{draft_name}** has already started — the pick sequence is underway and no new players can join.",
            ephemeral=True,
        )
        return
    if session.state != "joining":
        await interaction.response.send_message(
            f"Draft **{draft_name}** is not accepting players right now.", ephemeral=True
        )
        return
    if len(session.player_ids) >= 5:
        await interaction.response.send_message(
            "This draft is full (5 players max).", ephemeral=True
        )
        return
    if interaction.user.id in session.player_ids:
        await interaction.response.send_message("You've already joined this draft!", ephemeral=True)
        return

    session.player_ids.append(interaction.user.id)
    save_state()

    guild = interaction.guild
    lines = []
    for i, uid in enumerate(session.player_ids):
        m = guild.get_member(uid)
        lines.append(f"{i + 1}. {m.display_name if m else f'<@{uid}>'}")

    embed = discord.Embed(
        title=f"[{draft_name}] Player Joined!",
        description=(
            f"**{interaction.user.display_name}** joined.\n\n"
            f"**Players ({len(session.player_ids)}/5):**\n" + "\n".join(lines)
        ),
        color=discord.Color.green(),
    )
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="startdraft", description="Begin a faction draft (host only)")
@app_commands.describe(name="Name of the draft to start")
@app_commands.autocomplete(name=_active_drafts_autocomplete)
async def startdraft(interaction: discord.Interaction, name: str):
    gid = interaction.guild_id
    draft_name = _normalise(name)
    session = get_session(gid, draft_name)

    if not session:
        await interaction.response.send_message(f"No draft named **{draft_name}**.", ephemeral=True)
        return
    if interaction.user.id != session.host_id:
        await interaction.response.send_message("Only the host can start the draft.", ephemeral=True)
        return
    if session.state == "drafting":
        await interaction.response.send_message(
            f"Draft **{draft_name}** is already in progress.", ephemeral=True
        )
        return
    if session.state == "done":
        await interaction.response.send_message(
            f"Draft **{draft_name}** has already completed.", ephemeral=True
        )
        return

    blockers = []
    if not session.player_ids:
        blockers.append("• At least 1 player must join with `/joindraft`")
    if len(session.faction_pool) < 3:
        blockers.append(f"• At least 3 factions must be in the pool (currently {len(session.faction_pool)})")

    if blockers:
        await interaction.response.send_message(
            f"Draft **{draft_name}** can't start yet:\n" + "\n".join(blockers),
            ephemeral=True,
        )
        return

    session.state = "drafting"
    session.channel_id = interaction.channel_id
    save_state()

    await interaction.response.send_message(
        embed=discord.Embed(
            title=f"Draft [{draft_name}] Begins!",
            description="Faction selection has started. May the best strategist win.",
            color=discord.Color.blurple(),
        )
    )
    await run_next_pick(interaction.channel, session, interaction.guild)


@bot.tree.command(name="enddraft", description="Cancel a draft (host only)")
@app_commands.describe(name="Name of the draft to cancel")
@app_commands.autocomplete(name=_active_drafts_autocomplete)
async def enddraft(interaction: discord.Interaction, name: str):
    gid = interaction.guild_id
    draft_name = _normalise(name)
    session = get_session(gid, draft_name)

    if not session:
        await interaction.response.send_message(f"No draft named **{draft_name}**.", ephemeral=True)
        return
    if session.state == "done":
        await interaction.response.send_message(
            f"Draft **{draft_name}** has already completed and cannot be cancelled.", ephemeral=True
        )
        return
    if interaction.user.id != session.host_id:
        await interaction.response.send_message("Only the host can cancel the draft.", ephemeral=True)
        return

    delete_session(gid, draft_name)
    save_state()
    await interaction.response.send_message(f"Draft **{draft_name}** cancelled.")


@bot.tree.command(name="draftplayers", description="Show the player lineup for a draft")
@app_commands.describe(name="Name of the draft")
@app_commands.autocomplete(name=_active_drafts_autocomplete)
async def draftplayers(interaction: discord.Interaction, name: str):
    gid = interaction.guild_id
    draft_name = _normalise(name)
    session = get_session(gid, draft_name)

    if not session:
        await interaction.response.send_message(f"No draft named **{draft_name}**.", ephemeral=True)
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
        title=f"[{draft_name}] Players",
        description=player_list,
        color=discord.Color.blurple(),
    )
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="listdrafts", description="Show all active drafts in this server")
async def listdrafts(interaction: discord.Interaction):
    drafts = game_sessions.get(interaction.guild_id, {})
    active = {n: s for n, s in drafts.items() if s.state != "done"}

    if not active:
        await interaction.response.send_message("No active drafts in this server.", ephemeral=True)
        return

    guild = interaction.guild
    state_label = {"setup": "⏳ setting up", "joining": "🟢 open", "drafting": "🎲 in progress"}
    lines = []
    for draft_name, session in active.items():
        host = guild.get_member(session.host_id)
        host_name = host.display_name if host else f"<@{session.host_id}>"
        lines.append(
            f"**{draft_name}** — {state_label.get(session.state, session.state)} "
            f"· {len(session.player_ids)} player(s) · host: {host_name}"
        )

    embed = discord.Embed(
        title="Active Drafts",
        description="\n".join(lines),
        color=discord.Color.blurple(),
    )
    await interaction.response.send_message(embed=embed)
