import re
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


def _get_session_for_channel(guild_id: int, channel_id: int) -> "GameSession | None":
    for session in game_sessions.get(guild_id, {}).values():
        if session.draft_channel_id == channel_id:
            return session
    return None


def _resolve_draft_name(
    guild_id: int, channel_id: int, name: str | None
) -> tuple[str | None, str | None]:
    """Returns (draft_name, error). If error is set, send it and return early."""
    if name is None:
        session = _get_session_for_channel(guild_id, channel_id)
        if not session:
            return None, "Specify a draft name, or run this command from inside a draft channel."
        return session.name, None
    draft_name = _normalise(name)
    channel_session = _get_session_for_channel(guild_id, channel_id)
    if channel_session and channel_session.name != draft_name:
        return None, (
            f"You're in the **{channel_session.name}** draft channel — "
            f"you can only run commands for that draft here."
        )
    return draft_name, None


async def _active_drafts_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    gid = interaction.guild_id
    channel_session = _get_session_for_channel(gid, interaction.channel_id)
    if channel_session and channel_session.state != "done":
        return [app_commands.Choice(name=channel_session.name, value=channel_session.name)]
    drafts = game_sessions.get(gid, {})
    return [
        app_commands.Choice(name=name, value=name)
        for name, session in drafts.items()
        if session.state != "done" and current.lower() in name
    ][:25]


async def _all_drafts_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    gid = interaction.guild_id
    channel_session = _get_session_for_channel(gid, interaction.channel_id)
    if channel_session:
        return [app_commands.Choice(name=channel_session.name, value=channel_session.name)]
    drafts = game_sessions.get(gid, {})
    return [
        app_commands.Choice(name=name, value=name)
        for name in drafts
        if current.lower() in name
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
            f"A draft named **{draft_name}** is already running. Use `/canceldraft` to cancel it.",
            ephemeral=True,
        )
        return

    session = GameSession(guild_id=gid, name=draft_name, host_id=interaction.user.id)
    session.faction_pool = set(FACTIONS.keys())  # all factions selected by default
    session.state = "joining"                     # immediately open for players to join

    if player_count is not None:
        session.player_ids = [interaction.user.id] * player_count
        session.test_mode = True

    # Create a dedicated thread for this draft
    thread_name = "draft-" + re.sub(r"[^a-z0-9_-]", "-", draft_name.replace(" ", "-"))
    draft_thread = None
    await interaction.response.defer(ephemeral=True)
    try:
        # Threads must be created on a TextChannel; if we're already inside a thread, use its parent
        parent = interaction.channel
        if isinstance(parent, discord.Thread):
            parent = parent.parent
        if isinstance(parent, discord.TextChannel):
            draft_thread = await parent.create_thread(
                name=thread_name,
                type=discord.ChannelType.public_thread,
                auto_archive_duration=10080,  # 7 days
            )
            session.draft_channel_id = draft_thread.id
    except discord.Forbidden:
        pass  # bot lacks Create Public Threads — fall back to current channel

    set_session(session)
    save_state()

    test_note = (
        f"\n\n**Solo test mode — {player_count} seat(s) pre-filled.**"
    ) if player_count else ""

    embed = discord.Embed(
        title=f"Draft Created — {draft_name}",
        description=(
            f"The draft is open! Players must join from this thread using `/joindraft` — first come, first served.\n\n"
            f"All factions are in the pool by default. Use the selector below to remove any before starting.{test_note}"
        ),
        color=discord.Color.green(),
    )

    target = draft_thread or interaction.channel
    await target.send(embed=embed, view=FactionPoolSelect(session))

    if draft_thread:
        await interaction.followup.send(
            f"Draft **{draft_name}** created! Head to {draft_thread.mention} to set up factions and track picks.",
            ephemeral=True,
        )
    else:
        await interaction.followup.send(
            "Draft created (couldn't create a thread — missing Create Public Threads permission).",
            ephemeral=True,
        )


@bot.tree.command(name="joindraft", description="Join a Dune draft")
@app_commands.describe(name="Draft to join (omit if running from inside the draft channel)")
@app_commands.autocomplete(name=_active_drafts_autocomplete)
async def joindraft(interaction: discord.Interaction, name: Optional[str] = None):
    gid = interaction.guild_id
    draft_name, err = _resolve_draft_name(gid, interaction.channel_id, name)
    if err:
        await interaction.response.send_message(err, ephemeral=True)
        return
    session = get_session(gid, draft_name)

    if not session or session.state == "done":
        await interaction.response.send_message(
            f"No active draft named **{draft_name}**. Start one with `/newdraft`.", ephemeral=True
        )
        return
    if session.draft_channel_id and interaction.channel_id != session.draft_channel_id:
        draft_channel = bot.get_channel(session.draft_channel_id)
        mention = draft_channel.mention if draft_channel else f"the draft channel"
        await interaction.response.send_message(
            f"You must be in {mention} to join this draft — first come, first served.",
            ephemeral=True,
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
@app_commands.describe(name="Draft to start (omit if running from inside the draft channel)")
@app_commands.autocomplete(name=_active_drafts_autocomplete)
async def startdraft(interaction: discord.Interaction, name: Optional[str] = None):
    gid = interaction.guild_id
    draft_name, err = _resolve_draft_name(gid, interaction.channel_id, name)
    if err:
        await interaction.response.send_message(err, ephemeral=True)
        return
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
    pick_channel = bot.get_channel(session.draft_channel_id) if session.draft_channel_id else interaction.channel
    session.channel_id = pick_channel.id
    save_state()

    await interaction.response.send_message(
        embed=discord.Embed(
            title=f"Draft [{draft_name}] Begins!",
            description="Faction selection has started. May the best strategist win.",
            color=discord.Color.blurple(),
        )
    )
    await run_next_pick(pick_channel, session, interaction.guild)


@bot.tree.command(name="canceldraft", description="Cancel a draft and delete its channel (host only)")
@app_commands.describe(name="Draft to cancel (omit if running from inside the draft channel)")
@app_commands.autocomplete(name=_active_drafts_autocomplete)
async def canceldraft(interaction: discord.Interaction, name: Optional[str] = None):
    gid = interaction.guild_id
    draft_name, err = _resolve_draft_name(gid, interaction.channel_id, name)
    if err:
        await interaction.response.send_message(err, ephemeral=True)
        return
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

    draft_channel_id = session.draft_channel_id
    delete_session(gid, draft_name)
    save_state()

    await interaction.response.send_message(f"Draft **{draft_name}** cancelled.")

    if draft_channel_id:
        channel = bot.get_channel(draft_channel_id)
        if channel:
            try:
                await channel.delete(reason=f"Draft '{draft_name}' cancelled by host")
            except (discord.Forbidden, discord.NotFound):
                pass


@bot.tree.command(name="draftplayers", description="Show the player lineup for a draft")
@app_commands.describe(name="Draft to inspect (omit if running from inside the draft channel)")
@app_commands.autocomplete(name=_active_drafts_autocomplete)
async def draftplayers(interaction: discord.Interaction, name: Optional[str] = None):
    gid = interaction.guild_id
    draft_name, err = _resolve_draft_name(gid, interaction.channel_id, name)
    if err:
        await interaction.response.send_message(err, ephemeral=True)
        return
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


@bot.tree.command(name="renamedraft", description="Rename a draft and its channel (host only, before picks start)")
@app_commands.describe(
    new_name="The new name for this draft",
    name="Draft to rename (omit if running from inside the draft channel)",
)
@app_commands.autocomplete(name=_active_drafts_autocomplete)
async def renamedraft(interaction: discord.Interaction, new_name: str, name: Optional[str] = None):
    gid = interaction.guild_id
    draft_name, err = _resolve_draft_name(gid, interaction.channel_id, name)
    if err:
        await interaction.response.send_message(err, ephemeral=True)
        return
    session = get_session(gid, draft_name)

    if not session:
        await interaction.response.send_message(f"No draft named **{draft_name}**.", ephemeral=True)
        return
    if interaction.user.id != session.host_id:
        await interaction.response.send_message("Only the host can rename the draft.", ephemeral=True)
        return
    if session.state != "joining":
        await interaction.response.send_message(
            "Drafts can only be renamed before picks start.", ephemeral=True
        )
        return

    new_draft_name = _normalise(new_name)
    if "::" in new_draft_name:
        await interaction.response.send_message("Draft name cannot contain `::`.", ephemeral=True)
        return
    if new_draft_name == draft_name:
        await interaction.response.send_message("That's already the name.", ephemeral=True)
        return
    existing = get_session(gid, new_draft_name)
    if existing and existing.state != "done":
        await interaction.response.send_message(
            f"A draft named **{new_draft_name}** is already running.", ephemeral=True
        )
        return

    await interaction.response.defer(ephemeral=True)

    delete_session(gid, draft_name)
    session.name = new_draft_name
    set_session(session)

    if session.draft_channel_id:
        channel = bot.get_channel(session.draft_channel_id)
        if channel:
            new_channel_name = "draft-" + re.sub(r"[^a-z0-9_-]", "-", new_draft_name.replace(" ", "-"))
            try:
                await channel.edit(
                    name=new_channel_name,
                    reason=f"Draft renamed from '{draft_name}' to '{new_draft_name}'",
                )
            except discord.Forbidden:
                pass

    save_state()
    await interaction.followup.send(
        f"Draft renamed from **{draft_name}** to **{new_draft_name}**.", ephemeral=True
    )


@bot.tree.command(name="cleanupdraft", description="Delete a draft's dedicated channel after it's done")
@app_commands.describe(name="Draft whose channel to delete (omit if running from inside the draft channel)")
@app_commands.autocomplete(name=_all_drafts_autocomplete)
async def cleanupdraft(interaction: discord.Interaction, name: Optional[str] = None):
    gid = interaction.guild_id
    draft_name, err = _resolve_draft_name(gid, interaction.channel_id, name)

    if err:
        # Session may be gone post-restart but channel still exists — delete it directly
        ch = interaction.channel
        if isinstance(ch, discord.Thread) and ch.name.startswith("draft-"):
            await interaction.response.send_message(
                "No active session for this channel — deleting orphaned draft channel.", ephemeral=True
            )
            try:
                await ch.delete(reason="Orphaned draft channel cleaned up")
            except (discord.Forbidden, discord.NotFound):
                pass
            return
        await interaction.response.send_message(err, ephemeral=True)
        return

    session = get_session(gid, draft_name)

    if not session:
        # Session gone post-restart; if we're in the channel, just delete it
        ch = interaction.channel
        if isinstance(ch, discord.Thread) and ch.name.startswith("draft-"):
            await interaction.response.send_message(
                "Session no longer active — deleting orphaned draft channel.", ephemeral=True
            )
            try:
                await ch.delete(reason=f"Orphaned draft channel for '{draft_name}' cleaned up")
            except (discord.Forbidden, discord.NotFound):
                pass
            return
        await interaction.response.send_message(f"No draft named **{draft_name}** found.", ephemeral=True)
        return

    if interaction.user.id != session.host_id:
        await interaction.response.send_message("Only the host can clean up this draft.", ephemeral=True)
        return

    if not session.draft_channel_id:
        await interaction.response.send_message("This draft has no dedicated channel.", ephemeral=True)
        return

    channel = bot.get_channel(session.draft_channel_id)
    if not channel:
        session.draft_channel_id = None
        save_state()
        await interaction.response.send_message("Draft channel was already deleted.", ephemeral=True)
        return

    session.draft_channel_id = None
    save_state()
    await interaction.response.send_message(
        f"Deleting draft channel for **{draft_name}**.", ephemeral=True
    )
    try:
        await channel.delete(reason=f"Draft '{draft_name}' channel cleaned up by host")
    except (discord.Forbidden, discord.NotFound):
        pass


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
