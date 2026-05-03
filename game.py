import random
import discord

from bot import bot
from factions import FACTIONS
from models import GameSession, get_session, set_session, save_state, load_raw_state


async def fetch_member(guild: discord.Guild, user_id: int) -> discord.Member | None:
    member = guild.get_member(user_id)
    if member is None:
        try:
            member = await guild.fetch_member(user_id)
        except (discord.NotFound, discord.HTTPException):
            return None
    return member


def seat_name(session: GameSession, seat: int, member: discord.Member | None) -> str:
    """Returns a display name, appending a seat number when the same user holds multiple seats."""
    uid = session.player_ids[seat]
    base = member.display_name if member else f"<@{uid}>"
    if session.test_mode and session.player_ids.count(uid) > 1:
        return f"{base} (Seat {seat + 1})"
    return base


async def handle_pick(interaction: discord.Interaction, guild_id: int, draft_name: str, faction: str):
    # Lazy import breaks the views <-> game circular dependency
    from views import DraftView

    session = get_session(guild_id, draft_name)
    if not session or session.state != "drafting":
        await interaction.response.send_message("No active draft.", ephemeral=True)
        return

    current_id = session.current_player_id
    is_their_turn = interaction.user.id == current_id
    is_host_testing = session.test_mode and interaction.user.id == session.host_id
    if not is_their_turn and not is_host_testing:
        guild = bot.get_guild(guild_id)
        current = await fetch_member(guild, current_id) if guild else None
        name = current.display_name if current else f"<@{current_id}>"
        await interaction.response.send_message(f"It's **{name}**'s turn!", ephemeral=True)
        return

    current_seat = session.current_index
    session.assignments[current_seat] = faction
    for f in session.current_draw:
        if f != faction:
            session.faction_pool.add(f)
    session.current_draw = []
    session.current_index += 1

    guild = bot.get_guild(guild_id)
    current = await fetch_member(guild, current_id) if guild else None
    display_name = seat_name(session, current_seat, current)

    await interaction.response.edit_message(
        embed=discord.Embed(
            description=f"{FACTIONS[faction]['emoji']} **{display_name}** chose **{faction}**!",
            color=discord.Color.green(),
        ),
        view=None,
    )

    if session.current_player_id is None:
        session.state = "done"
        save_state()
        await show_final_results(interaction.channel, session, guild)
    else:
        save_state()
        await run_next_pick(interaction.channel, session, guild)


async def run_next_pick(channel: discord.abc.Messageable, session: GameSession, guild: discord.Guild):
    # Lazy import breaks the views <-> game circular dependency
    from views import DraftView

    player_id = session.current_player_id
    player = await fetch_member(guild, player_id)
    player_mention = player.mention if player else f"<@{player_id}>"
    player_name = seat_name(session, session.current_index, player)

    available = list(session.faction_pool)
    draw = random.sample(available, min(3, len(available)))
    session.current_draw = draw
    for f in draw:
        session.faction_pool.discard(f)
    save_state()

    faction_lines = "\n".join(
        f"{i + 1}. {FACTIONS[f]['emoji']} **{f}**" for i, f in enumerate(draw)
    )
    desc = f"{player_mention}, choose your faction!\n\n**Your draws:**\n{faction_lines}"

    if session.assignments:
        board_lines = []
        for i, uid in enumerate(session.player_ids):
            if i in session.assignments:
                f = session.assignments[i]
                m = await fetch_member(guild, uid)
                board_lines.append(f"**{seat_name(session, i, m)}** → {FACTIONS[f]['emoji']} **{f}**")
        desc += "\n\n**Assignments so far:**\n" + "\n".join(board_lines)

    desc += "\n\nUse the **Details** buttons to read about a faction before choosing."

    embed = discord.Embed(
        title=f"[{session.name}] {player_name}'s Turn",
        description=desc,
        color=discord.Color.blurple(),
    )
    view = DraftView(session.guild_id, session.name, draw)
    bot.add_view(view)
    await channel.send(embed=embed, view=view)


async def show_final_results(channel: discord.abc.Messageable, session: GameSession, guild: discord.Guild):
    lines = []
    for i, uid in enumerate(session.player_ids):
        f = session.assignments.get(i, "?")
        m = await fetch_member(guild, uid)
        lines.append(f"**{seat_name(session, i, m)}** → {FACTIONS[f]['emoji']} **{f}**")

    embed = discord.Embed(
        title=f"Dune — [{session.name}] Final Faction Assignments",
        description="\n".join(lines),
        color=discord.Color.gold(),
    )
    embed.set_footer(text="May the spice flow. Good luck!")
    await channel.send(embed=embed)


async def load_and_restore():
    from views import DraftView

    for guild_id_str, drafts in load_raw_state().items():
        guild_id = int(guild_id_str)
        for draft_name, session_data in drafts.items():
            session = GameSession.from_dict(guild_id, session_data)
            set_session(session)

            if session.state == "drafting" and session.current_draw:
                bot.add_view(DraftView(guild_id, draft_name, session.current_draw))

                if session.channel_id:
                    channel = bot.get_channel(session.channel_id)
                    if channel:
                        current_id = session.current_player_id
                        guild = bot.get_guild(guild_id)
                        current = await fetch_member(guild, current_id) if guild else None
                        mention = current.mention if current else f"<@{current_id}>"
                        await channel.send(
                            f"The bot restarted — draft **{draft_name}** is still active. "
                            f"It's {mention}'s turn. The selection buttons above are still valid."
                        )
