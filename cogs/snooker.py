from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

import config
from engine.score import BALL_VALUES, BALL_EMOJIS, BALLS, foul_penalty, distribute_penalty
from engine.session import SnookerSession
from db.database import save_session, save_set, end_session

# channel_id -> SnookerSession
active_sessions: dict[int, SnookerSession] = {}


# ---------------------------------------------------------------------------
# Embed builder
# ---------------------------------------------------------------------------

def build_scoreboard_embed(session: SnookerSession) -> discord.Embed:
    cs = session.current_set
    sets_done = len(session.completed_sets)
    set_num = cs.set_number if cs else sets_done

    embed = discord.Embed(title=f"🎱 Snooker Session — {session.date}", color=0x2ECC71)
    embed.set_footer(text=f"Set {set_num} | {sets_done} set(s) completed")

    totals = session.total_scores()
    score_lines = []
    for p in session.players:
        arrow = "▶" if cs and p == cs.current_player() else " "
        score_lines.append(f"{arrow} {p:<12} {totals[p]:>4} pts")
    embed.add_field(
        name="Total Scores",
        value="```\n" + "\n".join(score_lines) + "\n```",
        inline=False,
    )

    if cs:
        set_lines = [f"  {p:<12} {cs.scores.get(p, 0):>4}" for p in cs.player_order]
        embed.add_field(
            name=f"Set {cs.set_number} Scores",
            value="```\n" + "\n".join(set_lines) + "\n```",
            inline=False,
        )
        embed.add_field(name="Current Turn", value=f"**{cs.current_player()}**", inline=True)

    return embed


def build_record_embed(session: SnookerSession) -> discord.Embed:
    cs = session.current_set
    sets_done = len(session.completed_sets)
    set_num = cs.set_number if cs else sets_done

    embed = discord.Embed(
        title=f"📝 Snooker Session — {session.date} (Record Mode)",
        color=0x3498DB,
    )
    embed.set_footer(text=f"Set {set_num} | {sets_done} set(s) completed")

    totals = session.total_scores()
    total_lines = [f"  {p:<12} {totals[p]:>4} pts" for p in session.players]
    embed.add_field(
        name="Total Scores",
        value="```\n" + "\n".join(total_lines) + "\n```",
        inline=False,
    )

    if cs:
        if cs.scores_finalized:
            set_lines = [f"  {p:<12} {cs.scores.get(p, 0):>4}" for p in session.players]
            status = "✅ Scores entered"
        else:
            set_lines = [f"  {p:<12}    —" for p in session.players]
            status = "⏳ Awaiting score entry"
        embed.add_field(
            name=f"Set {cs.set_number} — {status}",
            value="```\n" + "\n".join(set_lines) + "\n```",
            inline=False,
        )

    return embed


# ---------------------------------------------------------------------------

class BallButton(discord.ui.Button):
    def __init__(self, ball: str, session: SnookerSession):
        self._ball = ball
        self._session = session
        row = 0 if ball in ("red", "yellow", "green", "brown", "blue") else 1
        super().__init__(
            label=f"{BALL_EMOJIS[ball]} {ball.capitalize()} ({BALL_VALUES[ball]})",
            style=discord.ButtonStyle.secondary,
            row=row,
        )

    async def callback(self, interaction: discord.Interaction):
        cs = self._session.current_set
        if not cs:
            await interaction.response.defer()
            return
        cs.add_score(cs.current_player(), BALL_VALUES[self._ball])
        await interaction.response.edit_message(
            embed=build_scoreboard_embed(self._session),
            view=ScoreboardView(self._session),
        )


class EndTurnButton(discord.ui.Button):
    def __init__(self, session: SnookerSession):
        self._session = session
        super().__init__(label="End Turn ↩", style=discord.ButtonStyle.primary, row=1)

    async def callback(self, interaction: discord.Interaction):
        cs = self._session.current_set
        if cs:
            cs.next_player()
        await interaction.response.edit_message(
            embed=build_scoreboard_embed(self._session),
            view=ScoreboardView(self._session),
        )


class FoulButton(discord.ui.Button):
    def __init__(self, session: SnookerSession):
        self._session = session
        super().__init__(label="🚫 Foul", style=discord.ButtonStyle.danger, row=2)

    async def callback(self, interaction: discord.Interaction):
        embed = build_scoreboard_embed(self._session)
        embed.add_field(name="Foul — Step 1", value="Who committed the foul?", inline=False)
        await interaction.response.edit_message(embed=embed, view=FoulPlayerSelectView(self._session))


class NewSetButton(discord.ui.Button):
    def __init__(self, session: SnookerSession):
        self._session = session
        super().__init__(label="➡️ New Set", style=discord.ButtonStyle.success, row=2)

    async def callback(self, interaction: discord.Interaction):
        set_data = self._session.save_current_set()
        if set_data:
            await save_set(self._session.session_id, set_data)
        self._session.start_set()
        await interaction.response.edit_message(
            embed=build_scoreboard_embed(self._session),
            view=ScoreboardView(self._session),
        )


class EndSessionButton(discord.ui.Button):
    def __init__(self, session: SnookerSession):
        self._session = session
        super().__init__(label="🏁 End Session", style=discord.ButtonStyle.danger, row=2)

    async def callback(self, interaction: discord.Interaction):
        set_data = self._session.save_current_set()
        if set_data:
            await save_set(self._session.session_id, set_data)
        await end_session(self._session.session_id)

        if self._session.channel_id in active_sessions:
            del active_sessions[self._session.channel_id]

        totals = self._session.total_scores()
        sorted_players = sorted(totals.items(), key=lambda x: x[1], reverse=True)
        medals = ["🥇", "🥈", "🥉"] + ["  "] * 10
        lines = [
            f"{medals[i]} {p:<12} {pts:>4} pts"
            for i, (p, pts) in enumerate(sorted_players)
        ]

        embed = discord.Embed(title=f"🏁 Session Ended — {self._session.date}", color=0xE74C3C)
        embed.add_field(
            name="Final Scores",
            value="```\n" + "\n".join(lines) + "\n```",
            inline=False,
        )
        embed.add_field(name="Sets Played", value=str(len(self._session.completed_sets)), inline=True)
        await interaction.response.edit_message(embed=embed, view=None)


class ScoreboardView(discord.ui.View):
    def __init__(self, session: SnookerSession):
        super().__init__(timeout=None)
        for ball in BALLS:
            self.add_item(BallButton(ball, session))
        self.add_item(EndTurnButton(session))
        self.add_item(FoulButton(session))
        self.add_item(NewSetButton(session))
        self.add_item(EndSessionButton(session))


# ---------------------------------------------------------------------------
# Foul flow views
# ---------------------------------------------------------------------------

class CancelFoulButton(discord.ui.Button):
    def __init__(self, session: SnookerSession, row: int = 1):
        self._session = session
        super().__init__(label="Cancel", style=discord.ButtonStyle.secondary, row=row)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.edit_message(
            embed=build_scoreboard_embed(self._session),
            view=ScoreboardView(self._session),
        )


class FoulPlayerButton(discord.ui.Button):
    def __init__(self, player: str, session: SnookerSession):
        self._player = player
        self._session = session
        super().__init__(label=player, style=discord.ButtonStyle.secondary, row=0)

    async def callback(self, interaction: discord.Interaction):
        embed = build_scoreboard_embed(self._session)
        embed.add_field(
            name="Foul — Step 2",
            value=f"**{self._player}** fouled. On which ball?",
            inline=False,
        )
        await interaction.response.edit_message(
            embed=embed,
            view=FoulBallSelectView(self._session, self._player),
        )


class FoulPlayerSelectView(discord.ui.View):
    def __init__(self, session: SnookerSession):
        super().__init__(timeout=None)
        for p in session.players:
            self.add_item(FoulPlayerButton(p, session))
        self.add_item(CancelFoulButton(session, row=1))


class FoulBallButton(discord.ui.Button):
    def __init__(self, ball: str, session: SnookerSession, fouling_player: str):
        self._ball = ball
        self._session = session
        self._fouling_player = fouling_player
        penalty = foul_penalty(ball)
        row = 0 if ball in ("red", "yellow", "green", "brown", "blue") else 1
        super().__init__(
            label=f"{BALL_EMOJIS[ball]} {ball.capitalize()} ({penalty})",
            style=discord.ButtonStyle.secondary,
            row=row,
        )

    async def callback(self, interaction: discord.Interaction):
        cs = self._session.current_set
        if cs:
            cs.apply_foul(self._fouling_player, self._ball, self._session.players)

        penalty = foul_penalty(self._ball)
        per_player = distribute_penalty(self._ball, len(self._session.players))
        n_remaining = len(self._session.players) - 1

        embed = build_scoreboard_embed(self._session)
        embed.add_field(
            name="✅ Foul Applied",
            value=(
                f"**{self._fouling_player}** fouled on "
                f"{BALL_EMOJIS[self._ball]} {self._ball.capitalize()} (penalty {penalty}). "
                f"+{per_player} pts to each of {n_remaining} other player(s)."
            ),
            inline=False,
        )
        await interaction.response.edit_message(embed=embed, view=ScoreboardView(self._session))


class FoulBallSelectView(discord.ui.View):
    def __init__(self, session: SnookerSession, fouling_player: str):
        super().__init__(timeout=None)
        for ball in BALLS:
            self.add_item(FoulBallButton(ball, session, fouling_player))
        self.add_item(CancelFoulButton(session, row=2))


# ---------------------------------------------------------------------------
# Record mode views
# ---------------------------------------------------------------------------

class EnterScoresButton(discord.ui.Button):
    def __init__(self, session: SnookerSession):
        self._session = session
        super().__init__(label="📝 Enter Scores", style=discord.ButtonStyle.primary, row=0)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(RecordScoreModal(self._session))


class RecordNewSetButton(discord.ui.Button):
    def __init__(self, session: SnookerSession):
        self._session = session
        finalized = bool(session.current_set and session.current_set.scores_finalized)
        super().__init__(
            label="➡️ New Set",
            style=discord.ButtonStyle.success,
            row=0,
            disabled=not finalized,
        )

    async def callback(self, interaction: discord.Interaction):
        set_data = self._session.save_current_set()
        if set_data:
            await save_set(self._session.session_id, set_data)
        self._session.start_set()
        await interaction.response.edit_message(
            embed=build_record_embed(self._session),
            view=RecordScoreboardView(self._session),
        )


class RecordEndSessionButton(discord.ui.Button):
    def __init__(self, session: SnookerSession):
        self._session = session
        super().__init__(label="🏁 End Session", style=discord.ButtonStyle.danger, row=0)

    async def callback(self, interaction: discord.Interaction):
        set_data = self._session.save_current_set()
        if set_data:
            await save_set(self._session.session_id, set_data)
        await end_session(self._session.session_id)

        if self._session.channel_id in active_sessions:
            del active_sessions[self._session.channel_id]

        totals = self._session.total_scores()
        sorted_players = sorted(totals.items(), key=lambda x: x[1], reverse=True)
        medals = ["🥇", "🥈", "🥉"] + ["  "] * 10
        lines = [
            f"{medals[i]} {p:<12} {pts:>4} pts"
            for i, (p, pts) in enumerate(sorted_players)
        ]

        embed = discord.Embed(title=f"🏁 Session Ended — {self._session.date}", color=0xE74C3C)
        embed.add_field(
            name="Final Scores",
            value="```\n" + "\n".join(lines) + "\n```",
            inline=False,
        )
        embed.add_field(name="Sets Played", value=str(len(self._session.completed_sets)), inline=True)
        await interaction.response.edit_message(embed=embed, view=None)


class RecordScoreboardView(discord.ui.View):
    def __init__(self, session: SnookerSession):
        super().__init__(timeout=None)
        self.add_item(EnterScoresButton(session))
        self.add_item(RecordNewSetButton(session))
        self.add_item(RecordEndSessionButton(session))


class RecordScoreModal(discord.ui.Modal):
    def __init__(self, session: SnookerSession):
        cs = session.current_set
        super().__init__(title=f"Set {cs.set_number} — Enter Scores" if cs else "Enter Scores")
        self._session = session
        self._inputs: dict[str, discord.ui.TextInput] = {}
        for player in session.players:
            inp = discord.ui.TextInput(
                label=player,
                placeholder="Enter final score (number)",
                required=True,
                min_length=1,
                max_length=5,
            )
            self._inputs[player] = inp
            self.add_item(inp)

    async def on_submit(self, interaction: discord.Interaction):
        cs = self._session.current_set
        for player, inp in self._inputs.items():
            try:
                score = int(inp.value)
                if score < 0:
                    raise ValueError
                cs.set_score(player, score)
            except ValueError:
                await interaction.response.send_message(
                    f"❌ Invalid score for **{player}**. Please enter a non-negative integer.",
                    ephemeral=True,
                )
                return
        cs.scores_finalized = True
        await interaction.response.edit_message(
            embed=build_record_embed(self._session),
            view=RecordScoreboardView(self._session),
        )


# ---------------------------------------------------------------------------
# Mode selection view
# ---------------------------------------------------------------------------

class FullModeButton(discord.ui.Button):
    def __init__(self, session: SnookerSession):
        self._session = session
        super().__init__(
            label="🎱 Full Mode (ball-by-ball)",
            style=discord.ButtonStyle.primary,
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.edit_message(
            content=None,
            embed=build_scoreboard_embed(self._session),
            view=ScoreboardView(self._session),
        )


class RecordModeButton(discord.ui.Button):
    def __init__(self, session: SnookerSession):
        self._session = session
        super().__init__(
            label="📝 Record Mode (enter totals per set)",
            style=discord.ButtonStyle.secondary,
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.edit_message(
            content=None,
            embed=build_record_embed(self._session),
            view=RecordScoreboardView(self._session),
        )


class ModeSelectView(discord.ui.View):
    def __init__(self, session: SnookerSession):
        super().__init__(timeout=300)
        self.add_item(FullModeButton(session))
        self.add_item(RecordModeButton(session))


# ---------------------------------------------------------------------------
# Player selection view (session start)
# ---------------------------------------------------------------------------

class PlayerToggleButton(discord.ui.Button):
    def __init__(self, player: str, selected: bool, select_view: PlayerSelectView):
        self._player = player
        self._select_view = select_view
        super().__init__(
            label=f"{'✅' if selected else '⬜'} {player}",
            style=discord.ButtonStyle.primary if selected else discord.ButtonStyle.secondary,
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        if self._player in self._select_view.selected:
            self._select_view.selected.discard(self._player)
        else:
            self._select_view.selected.add(self._player)
        self._select_view.rebuild()
        n = len(self._select_view.selected)
        content = (
            "Select players (minimum 2):"
            if n < 2
            else f"**{n} players selected.** Press Start when ready."
        )
        await interaction.response.edit_message(content=content, view=self._select_view)


class StartSessionButton(discord.ui.Button):
    def __init__(self, select_view: PlayerSelectView):
        self._select_view = select_view
        super().__init__(
            label="▶️ Start Session",
            style=discord.ButtonStyle.success,
            row=1,
            disabled=len(select_view.selected) < 2,
        )

    async def callback(self, interaction: discord.Interaction):
        # Preserve config order for selected players
        ordered = [p for p in config.PLAYERS if p in self._select_view.selected]

        session = SnookerSession()
        session.channel_id = interaction.channel_id
        session.init_players(ordered)
        session.start_set()
        active_sessions[interaction.channel_id] = session

        await save_session(session)
        await interaction.response.edit_message(
            content="Choose scoring mode:",
            embed=None,
            view=ModeSelectView(session),
        )


class PlayerSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)
        # Start with all players selected
        self.selected: set[str] = set(config.PLAYERS)
        self.rebuild()

    def rebuild(self):
        self.clear_items()
        for p in config.PLAYERS:
            self.add_item(PlayerToggleButton(p, p in self.selected, self))
        self.add_item(StartSessionButton(self))


# ---------------------------------------------------------------------------
# Cog
# ---------------------------------------------------------------------------

class SnookerCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="snooker", description="Start a new snooker scoreboard session")
    async def snooker(self, interaction: discord.Interaction):
        if interaction.channel_id in active_sessions:
            await interaction.response.send_message(
                "⚠️ A session is already active in this channel. End it first.",
                ephemeral=True,
            )
            return

        view = PlayerSelectView()
        await interaction.response.send_message("Select players (minimum 2):", view=view)


async def setup(bot: commands.Bot):
    await bot.add_cog(SnookerCog(bot))
