import discord
from discord.ext import commands
from discord.ui import View, Button, Select
import random
import os
import json
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
STATE_FILE = "game_state.json"

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ─── Faction Data ────────────────────────────────────────────────────────────

FACTIONS = {
    # --- Base game ---
    "Atreides": {
        "description": "House Atreides controls spice harvesting on Arrakis. They leverage prescience and noble leadership to outmaneuver enemies.",
        "color": 0x3498DB,
        "emoji": "🦅",
        "pdf_url": "PLACEHOLDER — replace with your PDF link",
        "expansion": False,
    },
    "Harkonnen": {
        "description": "House Harkonnen rules through treachery and brute force. They may hold more Treachery Cards than any other faction.",
        "color": 0x992222,
        "emoji": "☠️",
        "pdf_url": "PLACEHOLDER — replace with your PDF link",
        "expansion": False,
    },
    "Fremen": {
        "description": "The native Fremen of Arrakis are fearsome desert warriors. They ignore sandworms and thrive in desert territories.",
        "color": 0xD4A017,
        "emoji": "🏜️",
        "pdf_url": "PLACEHOLDER — replace with your PDF link",
        "expansion": False,
    },
    "Bene Gesserit": {
        "description": "The Bene Gesserit manipulate factions from the shadows using the Weirding Way and a prediction of the final victor.",
        "color": 0x8E44AD,
        "emoji": "🔮",
        "pdf_url": "PLACEHOLDER — replace with your PDF link",
        "expansion": False,
    },
    "Spacing Guild": {
        "description": "The Spacing Guild controls all interplanetary travel. They collect fees for every shipment and can block battles.",
        "color": 0xE67E22,
        "emoji": "🚀",
        "pdf_url": "PLACEHOLDER — replace with your PDF link",
        "expansion": False,
    },
    "Emperor": {
        "description": "The Emperor commands the elite Sardaukar troops. Other factions must pay him when they hire his forces.",
        "color": 0xF1C40F,
        "emoji": "👑",
        "pdf_url": "PLACEHOLDER — replace with your PDF link",
        "expansion": False,
    },
    # --- Ixians & Tleilaxu expansion ---
    "Ixians": {
        "description": "The Ixians are masters of technology. They control a hidden stronghold underground and can manipulate treachery cards.",
        "color": 0x1ABC9C,
        "emoji": "⚙️",
        "pdf_url": "PLACEHOLDER — replace with your PDF link",
        "expansion": True,
    },
    "Tleilaxu": {
        "description": "The Tleilaxu harvest spice from the bodies of the fallen and revive forces cheaply as gholas. Death is their resource.",
        "color": 0x2C3E50,
        "emoji": "🧬",
        "pdf_url": "PLACEHOLDER — replace with your PDF link",
        "expansion": True,
    },
    # --- CHOAM & Richese expansion ---
    "CHOAM": {
        "description": "The Combine Honnete Ober Advancer Mercantiles controls interplanetary commerce. They profit from the spice economy itself.",
        "color": 0x27AE60,
        "emoji": "💰",
        "pdf_url": "PLACEHOLDER — replace with your PDF link",
        "expansion": True,
    },
    "Richese": {
        "description": "House Richese rivals the Ixians in technology. They can produce cheap technology devices instead of drawing treachery cards.",
        "color": 0x95A5A6,
        "emoji": "🏭",
        "pdf_url": "PLACEHOLDER — replace with your PDF link",
        "expansion": True,
    },
    # --- Ecaz & Moritani expansion ---
    "Ecaz": {
        "description": "House Ecaz is a noble house of folio sculptors. They can form powerful alliances and gain unique combat advantages.",
        "color": 0x16A085,
        "emoji": "🌿",
        "pdf_url": "PLACEHOLDER — replace with your PDF link",
        "expansion": True,
    },
    "Moritani": {
        "description": "House Moritani are masters of assassination and terror. They can poison enemy leaders and sow chaos across the board.",
        "color": 0x7F8C8D,
        "emoji": "🗡️",
        "pdf_url": "PLACEHOLDER — replace with your PDF link",
        "expansion": True,
    },
}

# ─── Game State ──────────────────────────────────────────────────────────────

class GameSession:
    def __init__(self, guild_id: int, host_id: int):
        self.guild_id = guild_id
        self.host_id = host_id
        self.player_ids: list[int] = []       # user IDs in join order
        self.faction_pool: set[str] = set()
        self.assignments: dict[int, str] = {} # user_id -> faction name
        self.current_index: int = 0
        self.current_draw: list[str] = []
        self.state: str = "setup"             # setup | joining | drafting | done
        self.channel_id: int | None = None

    @property
    def current_player_id(self) -> int | None:
        if self.current_index < len(self.player_ids):
            return self.player_ids[self.current_index]
        return None

    def to_dict(self) -> dict:
        return {
            "host_id": self.host_id,
            "player_ids": self.player_ids,
            "faction_pool": list(self.faction_pool),
            "assignments": {str(k): v for k, v in self.assignments.items()},
            "current_index": self.current_index,
            "current_draw": self.current_draw,
            "state": self.state,
            "channel_id": self.channel_id,
        }

    @classmethod
    def from_dict(cls, guild_id: int, data: dict) -> "GameSession":
        s = cls(guild_id=guild_id, host_id=data["host_id"])
        s.player_ids = data["player_ids"]
        s.faction_pool = set(data["faction_pool"])
        s.assignments = {int(k): v for k, v in data["assignments"].items()}
        s.current_index = data["current_index"]
        s.current_draw = data["current_draw"]
        s.state = data["state"]
        s.channel_id = data.get("channel_id")
        return s


game_sessions: dict[int, GameSession] = {}


def save_state():
    data = {
        str(gid): s.to_dict()
        for gid, s in game_sessions.items()
        if s.state != "done"
    }
    with open(STATE_FILE, "w") as f:
        json.dump(data, f, indent=2)


async def fetch_member(guild: discord.Guild, user_id: int) -> discord.Member | None:
    member = guild.get_member(user_id)
    if member is None:
        try:
            member = await guild.fetch_member(user_id)
        except (discord.NotFound, discord.HTTPException):
            return None
    return member

# ─── Persistent Buttons & Views ──────────────────────────────────────────────
# timeout=None + stable custom_ids means buttons survive bot restarts.
# custom_id for pick buttons includes guild_id so state lookups are unambiguous.

class PickButton(Button):
    def __init__(self, guild_id: int, faction: str):
        super().__init__(
            label=f"Choose {faction}",
            emoji=FACTIONS[faction]["emoji"],
            style=discord.ButtonStyle.primary,
            custom_id=f"pick::{guild_id}::{faction}",
            row=0,
        )
        self.guild_id = guild_id
        self.faction_name = faction

    async def callback(self, interaction: discord.Interaction):
        await handle_pick(interaction, self.guild_id, self.faction_name)


class DetailsButton(Button):
    def __init__(self, faction: str):
        super().__init__(
            label=f"Details: {faction}",
            style=discord.ButtonStyle.secondary,
            custom_id=f"details::{faction}",
            row=1,
        )
        self.faction_name = faction

    async def callback(self, interaction: discord.Interaction):
        data = FACTIONS[self.faction_name]
        embed = discord.Embed(
            title=f"{data['emoji']} {self.faction_name}",
            description=data["description"],
            color=discord.Color(data["color"]),
        )
        embed.add_field(name="Rules PDF", value=data["pdf_url"])
        await interaction.response.send_message(embed=embed, ephemeral=True)


class DraftView(View):
    def __init__(self, guild_id: int, draw: list[str]):
        super().__init__(timeout=None)
        for faction in draw:
            self.add_item(PickButton(guild_id, faction))
        for faction in draw:
            self.add_item(DetailsButton(faction))


class FactionPoolSelect(View):
    def __init__(self, session: GameSession):
        super().__init__(timeout=120)
        self.session = session

        options = [
            discord.SelectOption(
                label=name,
                value=name,
                emoji=data["emoji"],
                description=data["description"][:97] + "..." if len(data["description"]) > 100 else data["description"],
            )
            for name, data in FACTIONS.items()
        ]
        self.select = Select(
            placeholder="Choose factions for the pool (min 3)...",
            min_values=3,
            max_values=len(FACTIONS),
            options=options,
        )
        self.select.callback = self.on_select
        self.add_item(self.select)

    async def on_select(self, interaction: discord.Interaction):
        self.session.faction_pool = set(self.select.values)
        self.session.state = "joining"
        save_state()

        pool_lines = "\n".join(
            f"• {FACTIONS[f]['emoji']} **{f}**"
            for f in FACTIONS
            if f in self.session.faction_pool
        )
        embed = discord.Embed(
            title="Faction Pool Set",
            description=f"**Available factions:**\n{pool_lines}\n\nPlayers can now use `/join` to enter the game.",
            color=discord.Color.green(),
        )
        await interaction.response.edit_message(embed=embed, view=None)

    async def on_timeout(self):
        session = self.session
        if game_sessions.get(session.guild_id) is session and session.state == "setup":
            del game_sessions[session.guild_id]
            save_state()

# ─── Game Helpers ─────────────────────────────────────────────────────────────

async def handle_pick(interaction: discord.Interaction, guild_id: int, faction: str):
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

# ─── Commands ─────────────────────────────────────────────────────────────────

@bot.tree.command(name="newgame", description="Start a new Dune faction draft")
async def newgame(interaction: discord.Interaction):
    gid = interaction.guild_id
    existing = game_sessions.get(gid)
    if existing and existing.state != "done":
        await interaction.response.send_message(
            "A game is already running. Use `/endgame` to cancel it.", ephemeral=True
        )
        return

    session = GameSession(guild_id=gid, host_id=interaction.user.id)
    game_sessions[gid] = session

    embed = discord.Embed(
        title="New Dune Game",
        description="Select which factions to include in the draw pool. You must select at least 3.",
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
        description=f"**{interaction.user.display_name}** joined.\n\n**Players ({len(session.player_ids)}/5):**\n" + "\n".join(lines),
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
            name = m.display_name if m else f"<@{uid}>"
            lines.append(f"{i + 1}. {name}")
        player_list = "\n".join(lines)

    embed = discord.Embed(
        title="Current Players",
        description=player_list,
        color=discord.Color.blurple(),
    )
    await interaction.response.send_message(embed=embed)

# ─── Startup & Recovery ───────────────────────────────────────────────────────

async def load_and_restore():
    if not os.path.exists(STATE_FILE):
        return

    with open(STATE_FILE) as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            return

    for guild_id_str, session_data in data.items():
        guild_id = int(guild_id_str)
        session = GameSession.from_dict(guild_id, session_data)
        game_sessions[guild_id] = session

        if session.state == "drafting" and session.current_draw:
            # Re-register the persistent view so existing buttons work again
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


@bot.event
async def on_ready():
    await load_and_restore()
    await bot.tree.sync()
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print("Slash commands synced.")


if __name__ == "__main__":
    bot.run(TOKEN)
