import random
import discord

from bot import bot
from factions import FACTIONS
from models import GameSession, game_sessions, save_state, load_raw_state


async def fetch_member(guild: discord.Guild, user_id: int) -> discord.Member | None:
    member = guild.get_member(user_id)
    if member is None:
        try:
            member = await guild.fetch_member(user_id)
        except (discord.NotFound, discord.HTTPException):
            return None
    return member


async def handle_pick(interaction: discord.Interaction, guild_id: int, faction: str):
    # Lazy import breaks the views <-> game circular dependency
    from views import DraftView

    session = game_sessions.get(guild_id)
    if not session or session.state != "drafting":
        await interaction.response.send_message("No active draft.", ephemeral=True)
        return

    current_id = session.current_player_id
    if interaction.user.id != current_id:
        guild = bot.get_guild(guild_id)
        current = await fetch_member(guild, current_id) if guild else None
        name = current.display_name if current else f"<@{current_id}>"
        await interaction.response.send_message(f"It's **{name}**'s turn!", ephemeral=True)
        return

    session.assignments[current_id] = faction
    for f in session.current_draw:
        if f != faction:
            session.faction_pool.add(f)
    session.current_draw = []
    session.current_index += 1

    guild = bot.get_guild(guild_id)
    current = await fetch_member(guild, current_id) if guild else None
    display_name = current.display_name if current else f"<@{current_id}>"

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
    player_name = player.display_name if player else f"<@{player_id}>"

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
        for uid in session.player_ids:
            if uid in session.assignments:
                f = session.assignments[uid]
                m = await fetch_member(guild, uid)
                name = m.display_name if m else f"<@{uid}>"
                board_lines.append(f"**{name}** → {FACTIONS[f]['emoji']} **{f}**")
        desc += "\n\n**Assignments so far:**\n" + "\n".join(board_lines)

    desc += "\n\nUse the **Details** buttons to read about a faction before choosing."

    embed = discord.Embed(
        title=f"{player_name}'s Turn",
        description=desc,
        color=discord.Color.blurple(),
    )
    view = DraftView(session.guild_id, draw)
    bot.add_view(view)
    await channel.send(embed=embed, view=view)


async def show_final_results(channel: discord.abc.Messageable, session: GameSession, guild: discord.Guild):
    lines = []
    for uid in session.player_ids:
        f = session.assignments.get(uid, "?")
        m = await fetch_member(guild, uid)
        name = m.display_name if m else f"<@{uid}>"
        lines.append(f"**{name}** → {FACTIONS[f]['emoji']} **{f}**")

    embed = discord.Embed(
        title="Dune — Final Faction Assignments",
        description="\n".join(lines),
        color=discord.Color.gold(),
    )
    embed.set_footer(text="May the spice flow. Good luck!")
    await channel.send(embed=embed)


async def load_and_restore():
    from views import DraftView

    for guild_id_str, session_data in load_raw_state().items():
        guild_id = int(guild_id_str)
        session = GameSession.from_dict(guild_id, session_data)
        game_sessions[guild_id] = session

        if session.state == "drafting" and session.current_draw:
            bot.add_view(DraftView(guild_id, session.current_draw))

            if session.channel_id:
                channel = bot.get_channel(session.channel_id)
                if channel:
                    current_id = session.current_player_id
                    guild = bot.get_guild(guild_id)
                    current = await fetch_member(guild, current_id) if guild else None
                    mention = current.mention if current else f"<@{current_id}>"
                    await channel.send(
                        f"The bot restarted — the draft is still active. "
                        f"It's {mention}'s turn. The selection buttons above are still valid."
                    )
