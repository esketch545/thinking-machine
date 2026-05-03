import discord
from discord.ui import View, Button, Select

from factions import FACTIONS
from models import GameSession, game_sessions, save_state


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
        # Lazy import breaks the views <-> game circular dependency
        from game import handle_pick
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
    """Persistent view (timeout=None) shown to each player during their pick turn."""

    def __init__(self, guild_id: int, draw: list[str]):
        super().__init__(timeout=None)
        for faction in draw:
            self.add_item(PickButton(guild_id, faction))
        for faction in draw:
            self.add_item(DetailsButton(faction))


class FactionPoolSelect(View):
    """One-time view shown to the host to choose which factions enter the draw pool."""

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
