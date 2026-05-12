import os
import discord
from discord.ui import View, Button, Select

from factions import FACTIONS
from models import GameSession, save_state

_PDF_DIR = os.path.join(os.path.dirname(__file__), "pdfs")
_RULES_PDF = os.path.join(_PDF_DIR, "rules.pdf")
_ERRATA_PDF = os.path.join(_PDF_DIR, "errata.pdf")


class PickButton(Button):
    def __init__(self, guild_id: int, draft_name: str, faction: str):
        super().__init__(
            label=f"Choose {faction}",
            emoji=FACTIONS[faction]["emoji"],
            style=discord.ButtonStyle.primary,
            custom_id=f"pick::{guild_id}::{draft_name}::{faction}",
            row=0,
        )
        self.guild_id = guild_id
        self.draft_name = draft_name
        self.faction_name = faction

    async def callback(self, interaction: discord.Interaction):
        # Lazy import breaks the views <-> game circular dependency
        from game import handle_pick
        await handle_pick(interaction, self.guild_id, self.draft_name, self.faction_name)


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

        files = []
        if os.path.exists(_ERRATA_PDF):
            files.append(discord.File(_ERRATA_PDF, filename="DuneErrata.pdf"))
        if os.path.exists(_RULES_PDF):
            files.append(discord.File(_RULES_PDF, filename="DuneRules.pdf"))

        try:
            await interaction.response.send_message(embed=embed, files=files, ephemeral=True)
        except discord.HTTPException:
            # Rules PDF likely exceeded the server's file size limit — send without it
            files_small = [f for f in files if f.filename != "DuneRules.pdf"]
            embed.set_footer(text="Full rules PDF is too large to attach on this server.")
            await interaction.response.send_message(embed=embed, files=files_small, ephemeral=True)


class DraftView(View):
    """Persistent view (timeout=None) shown to each player during their pick turn."""

    def __init__(self, guild_id: int, draft_name: str, draw: list[str]):
        super().__init__(timeout=None)
        for faction in draw:
            self.add_item(PickButton(guild_id, draft_name, faction))
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
                default=True,
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
        if interaction.user.id != self.session.host_id:
            await interaction.response.send_message(
                "Only the host can select factions for this draft.", ephemeral=True
            )
            return

        self.session.faction_pool = set(self.select.values)
        save_state()

        pool_lines = "\n".join(
            f"• {FACTIONS[f]['emoji']} **{f}**"
            for f in FACTIONS
            if f in self.session.faction_pool
        )
        embed = discord.Embed(
            title=f"Faction Pool Updated — **{self.session.name}**",
            description=f"**Factions in pool:**\n{pool_lines}\n\nPlayers can join with `/joindraft name:{self.session.name}`.",
            color=discord.Color.green(),
        )
        await interaction.response.edit_message(embed=embed, view=None)

