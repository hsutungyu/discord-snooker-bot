from __future__ import annotations

import logging
import traceback

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

import config
from engine.score import BALL_VALUES, BALL_EMOJIS, BALLS, foul_penalty, distribute_penalty
from engine.session import SnookerSession
from db.database import save_session, save_set, end_session, delete_session, get_completed_sessions, create_debt, get_debts, mark_debt_paid, mark_debt_paid_by_date, transfer_debt

log = logging.getLogger(__name__)

# channel_id -> SnookerSession
active_sessions: dict[int, SnookerSession] = {}


class BaseView(discord.ui.View):
    """All views extend this to ensure errors are logged to the console."""

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item) -> None:
        log.exception("Unhandled error in %s (item=%s): %s", type(self).__name__, type(item).__name__, error)
        msg = "An unexpected error occurred."
        try:
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Embed builder
# ---------------------------------------------------------------------------

def _format_events_grouped(events: list[dict]) -> list[str]:
    """
    Format a list of set events into display lines, grouping consecutive
    ball events for the same player into one line (turn summary).
    Fouls are each their own line. end_turn events are always omitted.
    """
    lines = []
    i = 0
    while i < len(events):
        ev = events[i]
        if ev["type"] == "ball":
            # Collect all consecutive balls for this player
            player = ev["player"]
            balls = []
            start_seq = ev["seq"]
            while i < len(events) and events[i]["type"] == "ball" and events[i]["player"] == player:
                balls.append(events[i]["ball"])
                i += 1
            end_seq = events[i - 1]["seq"]
            total = sum(BALL_VALUES[b] for b in balls)
            balls_str = " ".join(BALL_EMOJIS[b] for b in balls)
            seq_label = f"{start_seq}" if start_seq == end_seq else f"{start_seq}-{end_seq}"
            lines.append(f"{seq_label:>5}. {player:<12} {balls_str} (+{total})")
        elif ev["type"] == "foul":
            recipients = ", ".join(ev["recipients"])
            intent_tag = " [intentional]" if ev.get("intentional") else ""
            per_player_str = (
                f"+{ev['per_player']} ea → {recipients}"
                if not ev.get("intentional") and len(ev["recipients"]) > 1
                else f"+{ev['per_player']} → {recipients}"
            )
            lines.append(
                f"{ev['seq']:>5}. 🚫 {ev['fouler']:<11} {BALL_EMOJIS[ev['ball']]} "
                f"{ev['ball'].capitalize()} (pen {ev['penalty']}, {per_player_str}{intent_tag})"
            )
            i += 1
        elif ev["type"] == "end_turn":
            i += 1  # always skip — turn boundaries are implicit from ball/foul grouping
        else:
            lines.append(f"{ev['seq']:>5}. {ev}")
            i += 1
    return lines


def _fmt_duration(secs: int) -> str:
    m, s = divmod(secs, 60)
    return f"{m}m {s:02d}s"


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
        score_lines.append(f"{arrow} {p:<12} {totals[p]:>3} rp")
    embed.add_field(
        name=f"Ranking Points ({sets_done} set{'s' if sets_done != 1 else ''} done)",
        value="```\n" + "\n".join(score_lines) + "\n```",
        inline=False,
    )

    # Last completed set: show raw scores + ranking points + break history
    if session.last_completed_set:
        lcs = session.last_completed_set
        rp = lcs.get("ranking_points", {})
        last_lines = [
            f"  {p:<12} {lcs['scores'].get(p, 0):>4} pts  +{rp.get(p, 0)} rp"
            for p in session.players
        ]
        dur = lcs.get("duration_secs")
        if dur is not None:
            last_lines.append(f"  ⏱ Duration: {_fmt_duration(dur)}")
        breaks = lcs.get("breaks", {})
        if breaks:
            last_lines.append("")
            for p, player_breaks in breaks.items():
                for brk in player_breaks:
                    total = sum(BALL_VALUES[b] for b in brk)
                    balls_str = " ".join(BALL_EMOJIS[b] for b in brk)
                    last_lines.append(f"  {p}: {balls_str} ({total})")
        embed.add_field(
            name=f"Set {lcs['set_number']} Results",
            value="```\n" + "\n".join(last_lines) + "\n```",
            inline=False,
        )

    if cs:
        set_lines = [f"  {p:<12} {cs.scores.get(p, 0):>4}" for p in cs.player_order]
        embed.add_field(
            name=f"Set {cs.set_number} (in progress)",
            value="```\n" + "\n".join(set_lines) + "\n```",
            inline=False,
        )
        current = cs.current_player()
        turn_val = f"**{current}**"
        if cs.current_break:
            total = cs.current_break_total()
            balls_str = " ".join(BALL_EMOJIS[b] for b in cs.current_break)
            turn_val += f"\nBreak: {balls_str} ({total})"
        embed.add_field(name="Current Turn", value=turn_val, inline=True)

        # Live event feed — last 10 grouped lines
        if cs.events:
            feed_lines = _format_events_grouped(cs.events)
            if len(feed_lines) > 10:
                feed_lines = [f"… ({len(feed_lines) - 10} earlier)"] + feed_lines[-10:]
            embed.add_field(
                name="📋 Set Log",
                value="```\n" + "\n".join(feed_lines) + "\n```",
                inline=False,
            )

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
    total_lines = [f"  {p:<12} {totals[p]:>3} rp" for p in session.players]
    embed.add_field(
        name=f"Ranking Points ({sets_done} set{'s' if sets_done != 1 else ''} done)",
        value="```\n" + "\n".join(total_lines) + "\n```",
        inline=False,
    )

    # Last completed set results
    if session.last_completed_set:
        lcs = session.last_completed_set
        rp = lcs.get("ranking_points", {})
        last_lines = [
            f"  {p:<12} {lcs['scores'].get(p, 0):>4} pts  +{rp.get(p, 0)} rp"
            for p in session.players
        ]
        embed.add_field(
            name=f"Set {lcs['set_number']} Results",
            value="```\n" + "\n".join(last_lines) + "\n```",
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
        await interaction.response.defer()
        cs = self._session.current_set
        if not cs:
            return
        async with self._session._lock:
            cs.add_score(cs.current_player(), self._ball)
            embed = build_scoreboard_embed(self._session)
            view = ScoreboardView(self._session)
        await interaction.edit_original_response(embed=embed, view=view)


class EndTurnButton(discord.ui.Button):
    def __init__(self, session: SnookerSession):
        self._session = session
        super().__init__(label="End Turn ↩", style=discord.ButtonStyle.primary, row=1)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        alert_msg = None
        async with self._session._lock:
            cs = self._session.current_set
            if cs:
                prev_player = cs.current_player()
                prev_break = list(cs.current_break)
                cs.next_player()
                if prev_break:
                    total = sum(BALL_VALUES[b] for b in prev_break)
                    if total >= config.BREAK_ALERT_THRESHOLD:
                        balls_str = " ".join(BALL_EMOJIS[b] for b in prev_break)
                        alert_msg = (
                            f"🎯 **Break alert!** **{prev_player}** scored a break of **{total}**!\n"
                            f"{balls_str}"
                        )
            embed = build_scoreboard_embed(self._session)
            view = ScoreboardView(self._session)
        await interaction.edit_original_response(embed=embed, view=view)
        if alert_msg:
            await interaction.followup.send(alert_msg)


class FoulButton(discord.ui.Button):
    def __init__(self, session: SnookerSession):
        self._session = session
        super().__init__(label="🚫 Foul", style=discord.ButtonStyle.danger, row=2)

    async def callback(self, interaction: discord.Interaction):
        scoreboard_message = interaction.message
        await interaction.response.send_message(
            "🚫 Select foul details:",
            view=FoulSelectView(self._session, scoreboard_message=scoreboard_message),
            ephemeral=True,
        )


class NewSetButton(discord.ui.Button):
    def __init__(self, session: SnookerSession):
        self._session = session
        super().__init__(label="➡️ New Set", style=discord.ButtonStyle.success, row=2)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        async with self._session._lock:
            set_data = self._session.save_current_set()
            if set_data:
                await save_set(self._session.session_id, set_data)
            self._session.start_set()
            embed = build_scoreboard_embed(self._session)
            view = ScoreboardView(self._session)
        await interaction.edit_original_response(embed=embed, view=view)


class EndSessionButton(discord.ui.Button):
    def __init__(self, session: SnookerSession):
        self._session = session
        super().__init__(label="🏁 End Session", style=discord.ButtonStyle.danger, row=2)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        async with self._session._lock:
            embed = build_scoreboard_embed(self._session)
            embed.add_field(name="⚠️ End Session?", value="Are you sure you want to end the session?", inline=False)
            view = ConfirmEndSessionView(self._session, mode="full")
        await interaction.edit_original_response(embed=embed, view=view)


class UndoButton(discord.ui.Button):
    def __init__(self, session: SnookerSession):
        self._session = session
        cs = session.current_set
        super().__init__(
            label="↩ Undo",
            style=discord.ButtonStyle.secondary,
            row=2,
            disabled=not (cs and cs.can_undo()),
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        async with self._session._lock:
            cs = self._session.current_set
            if cs:
                cs.undo()
            embed = build_scoreboard_embed(self._session)
            view = ScoreboardView(self._session)
        await interaction.edit_original_response(embed=embed, view=view)


class BallSummaryButton(discord.ui.Button):
    def __init__(self, session: SnookerSession):
        self._session = session
        super().__init__(label="📊 Summary", style=discord.ButtonStyle.secondary, row=2)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        async with self._session._lock:
            cs = self._session.current_set
            if not cs:
                await interaction.followup.send("No set is currently in progress.", ephemeral=True)
                return

            # Count balls per player from the event log
            ball_counts: dict[str, dict[str, int]] = {
                p: {b: 0 for b in BALLS} for p in self._session.players
            }
            for ev in cs.events:
                if ev["type"] == "ball":
                    ball_counts[ev["player"]][ev["ball"]] += 1

            # Build a line per player showing non-zero ball counts
            lines = []
            for p in cs.player_order:
                counts = ball_counts[p]
                parts = [
                    f"{BALL_EMOJIS[b]}×{counts[b]}"
                    for b in BALLS
                    if counts[b] > 0
                ]
                balls_str = "  ".join(parts) if parts else "—"
                lines.append(f"{p:<12} {balls_str}  (+{cs.scores.get(p, 0)} pts)")

            embed = discord.Embed(
                title=f"📊 Set {cs.set_number} — Ball Summary",
                color=0x2ECC71,
            )
            embed.add_field(
                name="Balls potted this set",
                value="\n".join(lines),
                inline=False,
            )
        await interaction.followup.send(embed=embed, ephemeral=True)


class ScoreboardView(BaseView):
    def __init__(self, session: SnookerSession):
        super().__init__(timeout=None)
        for ball in BALLS:
            self.add_item(BallButton(ball, session))
        self.add_item(EndTurnButton(session))
        self.add_item(FoulButton(session))
        self.add_item(NewSetButton(session))
        self.add_item(EndSessionButton(session))
        self.add_item(UndoButton(session))
        self.add_item(BallSummaryButton(session))


# ---------------------------------------------------------------------------
# End session confirmation view (shared by full and record mode)
# ---------------------------------------------------------------------------

class ConfirmEndSessionView(BaseView):
    """Shows Confirm / Cancel before actually ending the session."""

    def __init__(self, session: SnookerSession, mode: str = "full"):
        super().__init__(timeout=None)
        self._session = session
        self._mode = mode  # "full" or "record"

        confirm = discord.ui.Button(label="✅ Yes, end session", style=discord.ButtonStyle.danger, row=0)
        confirm.callback = self._on_confirm
        self.add_item(confirm)

        cancel = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.secondary, row=0)
        cancel.callback = self._on_cancel
        self.add_item(cancel)

    async def _on_confirm(self, interaction: discord.Interaction):
        await interaction.response.defer()
        async with self._session._lock:
            if self._mode == "full":
                cs = self._session.current_set
                if cs and any(v > 0 for v in cs.scores.values()):
                    set_data = self._session.save_current_set()
                    if set_data:
                        await save_set(self._session.session_id, set_data)
                else:
                    self._session.current_set = None
            else:  # record mode
                cs = self._session.current_set
                if cs and cs.scores_finalized:
                    set_data = self._session.save_current_set()
                    if set_data:
                        await save_set(self._session.session_id, set_data)
                else:
                    self._session.current_set = None

            if self._session.channel_id in active_sessions:
                del active_sessions[self._session.channel_id]

            if not self._session.completed_sets:
                await delete_session(self._session.session_id)
                embed = discord.Embed(
                    title="Session Discarded",
                    description="No scores were recorded. The session has been discarded.",
                    color=0x95A5A6,
                )
                await interaction.edit_original_response(embed=embed, view=None)
                return

            await end_session(self._session.session_id)
            embed, _ = await _build_end_embed(self._session)
        await interaction.edit_original_response(embed=embed, view=None)

    async def _on_cancel(self, interaction: discord.Interaction):
        await interaction.response.defer()
        async with self._session._lock:
            if self._mode == "full":
                embed = build_scoreboard_embed(self._session)
                view = ScoreboardView(self._session)
            else:
                embed = build_record_embed(self._session)
                view = RecordScoreboardView(self._session)
        await interaction.edit_original_response(embed=embed, view=view)


# ---------------------------------------------------------------------------
# Foul flow — ephemeral select view
# ---------------------------------------------------------------------------

class _PlayerSelect(discord.ui.Select):
    def __init__(self, players: list[str]):
        options = [discord.SelectOption(label=p, value=p) for p in players]
        super().__init__(placeholder="Select fouling player…", options=options, row=0)

    async def callback(self, interaction: discord.Interaction):
        self.view.selected_player = self.values[0]
        self.view._refresh_confirm()
        await interaction.response.edit_message(view=self.view)


class _BallSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label=f"{BALL_EMOJIS[b]} {b.capitalize()} ({BALL_VALUES[b]})",
                value=b,
            )
            for b in BALLS
        ]
        super().__init__(placeholder="Select ball fouled on…", options=options, row=1)

    async def callback(self, interaction: discord.Interaction):
        self.view.selected_ball = self.values[0]
        self.view._refresh_confirm()
        await interaction.response.edit_message(view=self.view)


class _FoulTypeSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label="Unintentional",
                value="unintentional",
                description="Penalty shared among remaining players",
            ),
            discord.SelectOption(
                label="Intentional",
                value="intentional",
                description="Full penalty to the player before the fouler",
            ),
        ]
        super().__init__(placeholder="Select foul type…", options=options, row=2)

    async def callback(self, interaction: discord.Interaction):
        self.view.selected_foul_type = self.values[0]
        self.view._refresh_confirm()
        await interaction.response.edit_message(view=self.view)


class FoulSelectView(BaseView):
    """Ephemeral view with dropdowns for recording a foul. The bot is contacted once
    per dropdown selection (to refresh the view state) and once on Confirm."""

    def __init__(self, session: SnookerSession, scoreboard_message: discord.Message | None = None):
        super().__init__(timeout=120)
        self._session = session
        self._scoreboard_message = scoreboard_message

        self.selected_player: str | None = None
        self.selected_ball: str | None = None
        self.selected_foul_type: str | None = None

        self.confirm_button = discord.ui.Button(
            label="✅ Confirm Foul",
            style=discord.ButtonStyle.danger,
            disabled=True,
            row=3,
        )
        self.confirm_button.callback = self._on_confirm

        cancel_button = discord.ui.Button(
            label="✖ Cancel",
            style=discord.ButtonStyle.secondary,
            row=3,
        )
        cancel_button.callback = self._on_cancel

        self.add_item(_PlayerSelect(session.players))
        self.add_item(_BallSelect())
        self.add_item(_FoulTypeSelect())
        self.add_item(self.confirm_button)
        self.add_item(cancel_button)

    def _refresh_confirm(self):
        self.confirm_button.disabled = not (
            self.selected_player and self.selected_ball and self.selected_foul_type
        )

    async def _on_confirm(self, interaction: discord.Interaction):
        fouling_player = self.selected_player
        ball = self.selected_ball
        intentional = self.selected_foul_type == "intentional"

        await interaction.response.defer()
        async with self._session._lock:
            cs = self._session.current_set
            if cs:
                cs.apply_foul(fouling_player, ball, self._session.players, intentional=intentional)
            penalty = foul_penalty(ball)
            scoreboard_embed = build_scoreboard_embed(self._session)
            # Read computed recipients and per_player from the event just logged
            last_event = cs.events[-1] if cs and cs.events else {}
            per_player = last_event.get("per_player", penalty)
            recipients = last_event.get("recipients", [])
            if intentional:
                prev_player = recipients[0] if recipients else ""
                foul_summary = (
                    f"**{fouling_player}** intentionally fouled on "
                    f"{BALL_EMOJIS[ball]} {ball.capitalize()} (penalty {penalty}). "
                    f"+{per_player} pts to **{prev_player}**."
                )
                field_name = "✅ Intentional Foul Applied"
            else:
                n_remaining = len(recipients)
                foul_summary = (
                    f"**{fouling_player}** fouled on "
                    f"{BALL_EMOJIS[ball]} {ball.capitalize()} (penalty {penalty}). "
                    f"+{per_player} pts to each of {n_remaining} other player(s)."
                )
                field_name = "✅ Foul Applied"
            scoreboard_embed.add_field(name=field_name, value=foul_summary, inline=False)
            scoreboard_view = ScoreboardView(self._session)
        # Update the shared scoreboard message visible to everyone in the channel
        if self._scoreboard_message:
            try:
                await self._scoreboard_message.edit(embed=scoreboard_embed, view=scoreboard_view)
            except discord.HTTPException as exc:
                log.warning("Could not update scoreboard message after foul: %s", exc)
        await interaction.edit_original_response(content=f"✅ {field_name}: {foul_summary}", view=None)

    async def _on_cancel(self, interaction: discord.Interaction):
        await interaction.response.edit_message(content="❌ Foul entry cancelled.", view=None)


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
        await interaction.response.defer()
        async with self._session._lock:
            embed = build_record_embed(self._session)
            embed.add_field(name="⚠️ End Session?", value="Are you sure you want to end the session?", inline=False)
            view = ConfirmEndSessionView(self._session, mode="record")
        await interaction.edit_original_response(embed=embed, view=view)


class RecordScoreboardView(BaseView):
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


class ModeSelectView(BaseView):
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


class PlayerSelectView(BaseView):
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
# Session end helper (shared by Full + Record mode)
# ---------------------------------------------------------------------------

async def _build_end_embed(session: SnookerSession):
    """Build the session-ended embed, record the debt, return (embed, debt_line)."""
    totals = session.total_scores()
    raw_totals = session.total_raw_scores()
    sorted_players = sorted(
        session.players,
        key=lambda p: (totals.get(p, 0), raw_totals.get(p, 0)),
        reverse=True,
    )
    medals = ["🥇", "🥈", "🥉"] + ["  "] * 10
    lines = [
        f"{medals[i]} {p:<12} {totals.get(p, 0):>3} rp"
        for i, p in enumerate(sorted_players)
    ]

    creditor = sorted_players[0]
    debtor = sorted_players[-1]
    debt_line = ""
    if len(session.players) >= 2 and creditor != debtor:
        await create_debt(session.session_id, session.date, debtor, creditor)
        debt_line = f"🧋 **{debtor}** owes a bubble tea to **{creditor}**"

    embed = discord.Embed(title=f"🏁 Session Ended — {session.date}", color=0xE74C3C)
    embed.add_field(
        name="Final Standings",
        value="```\n" + "\n".join(lines) + "\n```",
        inline=False,
    )
    embed.add_field(name="Sets Played", value=str(len(session.completed_sets)), inline=True)
    if debt_line:
        embed.add_field(name="🧋 Bubble Tea Debt", value=debt_line, inline=False)
    return embed, debt_line


# ---------------------------------------------------------------------------
# History view
# ---------------------------------------------------------------------------

_EMBED_LIMIT = 5900  # conservative safety margin below Discord's 6000-char cap


def _embed_len(embed: discord.Embed) -> int:
    total = len(embed.title or "") + len(embed.description or "")
    if embed.footer and embed.footer.text:
        total += len(embed.footer.text)
    for f in embed.fields:
        total += len(f.name) + len(f.value)
    return total


def _safe_add_field(embed: discord.Embed, name: str, value: str) -> bool:
    """Add a field only if it keeps the embed within the 6000-char limit.
    Returns True if added, False if skipped."""
    if _embed_len(embed) + len(name) + len(value) > _EMBED_LIMIT:
        return False
    embed.add_field(name=name, value=value, inline=False)
    return True

def build_history_embed(sessions: list[dict], page: int, set_page: int = 0) -> discord.Embed:
    if not sessions:
        return discord.Embed(
            title="📜 Session History",
            description="No completed sessions yet.",
            color=0x95A5A6,
        )

    session = sessions[page]
    total_pages = len(sessions)
    players = session["players"]
    totals = session["ranking_totals"]
    sets = session["sets"]
    total_sets = len(sets)

    # Clamp set_page to valid range
    set_page = max(0, min(set_page, total_sets - 1)) if total_sets else 0

    embed = discord.Embed(
        title=f"📜 Session — {session['date']}",
        color=0x9B59B6,
    )
    set_indicator = f"  |  Set {set_page + 1} of {total_sets}" if total_sets else ""
    embed.set_footer(text=f"Session {page + 1} of {total_pages}  |  {total_sets} set(s) played{set_indicator}")

    # Final standings
    score_totals = session.get("score_totals", {})
    sorted_players = sorted(
        players,
        key=lambda p: (totals.get(p, 0), score_totals.get(p, 0)),
        reverse=True,
    )
    medals = ["🥇", "🥈", "🥉"] + ["  "] * 10
    standing_lines = [
        f"{medals[i]} {p:<12} {totals.get(p, 0):>3} rp"
        for i, p in enumerate(sorted_players)
    ]
    embed.add_field(
        name="🏆 Final Standings",
        value="```\n" + "\n".join(standing_lines) + "\n```",
        inline=False,
    )

    # All-sets score summary (scores + breaks per set, all sets)
    if sets:
        set_lines = []
        for s in sets:
            scores = s.get("scores", {})
            order = s.get("player_order") or players
            parts = "  ".join(f"{p} {scores.get(p, 0)}" for p in order)
            dur = s.get("duration_secs")
            dur_str = f"  ⏱{_fmt_duration(dur)}" if dur is not None else ""
            marker = " ◀" if s["set_number"] == set_page + 1 else ""
            set_lines.append(f"Set {s['set_number']:>2}: {parts}{dur_str}{marker}")
            breaks = s.get("breaks", {})
            if breaks:
                for p, player_breaks in breaks.items():
                    totals_str = " → ".join(
                        f"{''.join(BALL_EMOJIS[b] for b in brk)} ({sum(BALL_VALUES[b] for b in brk)})"
                        for brk in player_breaks
                    )
                    set_lines.append(f"         {p}: {totals_str}")
        # Split into ≤1016-char chunks (8 chars reserved for ``` wrapper)
        MAX_CONTENT = 1016
        chunks: list[str] = []
        current = ""
        for line in set_lines:
            candidate = (current + "\n" + line) if current else line
            if len(candidate) > MAX_CONTENT:
                if current:
                    chunks.append(current)
                current = line
            else:
                current = candidate
        if current:
            chunks.append(current)
        for idx, chunk in enumerate(chunks):
            added = _safe_add_field(
                embed,
                "Set Results" if idx == 0 else "Set Results (cont.)",
                "```\n" + chunk + "\n```",
            )
            if not added:
                break

        # Event log for the currently selected set only
        if total_sets:
            s = sets[set_page]
            events = s.get("events") or []
            scores = s.get("scores") or {}
            if events and sum(scores.values()) > 0:
                event_lines = _format_events_grouped(events)
                value = "\n".join(event_lines)
                if len(value) > 990:
                    value = value[:990] + "\n…"
                _safe_add_field(
                    embed,
                    f"📋 Set {s['set_number']} Log",
                    "```\n" + value + "\n```",
                )

    return embed


class HistoryPrevButton(discord.ui.Button):
    def __init__(self, page: int, total: int, set_page: int):
        self._page = page
        self._set_page = set_page
        super().__init__(
            label="◀ Newer",
            style=discord.ButtonStyle.secondary,
            disabled=page == 0,
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        new_page = self._page - 1
        sessions = await get_completed_sessions()
        await interaction.edit_original_response(
            embed=build_history_embed(sessions, new_page, 0),
            view=HistoryView(new_page, len(sessions), 0, len(sessions[new_page]["sets"])),
        )


class HistoryNextButton(discord.ui.Button):
    def __init__(self, page: int, total: int, set_page: int):
        self._page = page
        self._set_page = set_page
        super().__init__(
            label="Older ▶",
            style=discord.ButtonStyle.secondary,
            disabled=page >= total - 1,
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        new_page = self._page + 1
        sessions = await get_completed_sessions()
        await interaction.edit_original_response(
            embed=build_history_embed(sessions, new_page, 0),
            view=HistoryView(new_page, len(sessions), 0, len(sessions[new_page]["sets"])),
        )


class HistorySetPrevButton(discord.ui.Button):
    def __init__(self, page: int, total_sessions: int, set_page: int, total_sets: int):
        self._page = page
        self._total_sessions = total_sessions
        self._set_page = set_page
        super().__init__(
            label="◀ Prev Set",
            style=discord.ButtonStyle.primary,
            disabled=set_page == 0,
            row=1,
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        new_set_page = self._set_page - 1
        sessions = await get_completed_sessions()
        await interaction.edit_original_response(
            embed=build_history_embed(sessions, self._page, new_set_page),
            view=HistoryView(self._page, self._total_sessions, new_set_page, len(sessions[self._page]["sets"])),
        )


class HistorySetNextButton(discord.ui.Button):
    def __init__(self, page: int, total_sessions: int, set_page: int, total_sets: int):
        self._page = page
        self._total_sessions = total_sessions
        self._set_page = set_page
        self._total_sets = total_sets
        super().__init__(
            label="Next Set ▶",
            style=discord.ButtonStyle.primary,
            disabled=set_page >= total_sets - 1,
            row=1,
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        new_set_page = self._set_page + 1
        sessions = await get_completed_sessions()
        await interaction.edit_original_response(
            embed=build_history_embed(sessions, self._page, new_set_page),
            view=HistoryView(self._page, self._total_sessions, new_set_page, len(sessions[self._page]["sets"])),
        )


class HistoryView(BaseView):
    def __init__(self, page: int = 0, total_sessions: int = 0, set_page: int = 0, total_sets: int = 0):
        super().__init__(timeout=None)
        self.add_item(HistoryPrevButton(page, total_sessions, set_page))
        self.add_item(HistoryNextButton(page, total_sessions, set_page))
        if total_sets > 1:
            self.add_item(HistorySetPrevButton(page, total_sessions, set_page, total_sets))
            self.add_item(HistorySetNextButton(page, total_sessions, set_page, total_sets))



# ---------------------------------------------------------------------------
# Debt view
# ---------------------------------------------------------------------------

def find_transferable_chains(debts: list[dict]) -> list[tuple[dict, dict]]:
    """Return pairs (debt1, debt2) of unpaid debts where debt1.creditor == debt2.debtor.

    Each pair represents a transferable chain: debt1 is A→B and debt2 is B→C,
    so B can transfer by replacing both with a new debt A→C.
    Self-referential results (where A == C) are excluded.
    """
    unpaid = [d for d in debts if not d["paid"]]
    chains = []
    for d1 in unpaid:
        for d2 in unpaid:
            if (
                d1["id"] != d2["id"]
                and d1["creditor"] == d2["debtor"]
                and d1["debtor"] != d2["creditor"]  # exclude circular debts
            ):
                chains.append((d1, d2))
    return chains


def build_debt_embed(debts: list[dict]) -> discord.Embed:
    embed = discord.Embed(title="🧋 Bubble Tea Debts", color=0xF39C12)
    if not debts:
        embed.description = "No debts recorded yet. Play some snooker first!"
        return embed

    unpaid = [d for d in debts if not d["paid"]]
    paid = [d for d in debts if d["paid"]]

    if unpaid:
        lines = [
            f"#{d['id']}  {d['session_date']}  {d['debtor']:<12} → {d['creditor']}"
            for d in unpaid
        ]
        embed.add_field(
            name=f"⏳ Outstanding ({len(unpaid)})",
            value="```\n" + "\n".join(lines) + "\n```",
            inline=False,
        )
    else:
        embed.add_field(name="⏳ Outstanding", value="All debts are settled! 🎉", inline=False)

    if paid:
        lines = [
            f"#{d['id']}  {d['session_date']}  {d['debtor']:<12} → {d['creditor']}  ✅"
            for d in paid[-5:]  # show last 5 paid
        ]
        embed.add_field(
            name=f"✅ Recently Paid",
            value="```\n" + "\n".join(lines) + "\n```",
            inline=False,
        )

    chains = find_transferable_chains(debts)
    if chains:
        chain_lines = [
            f"#{d1['id']}+#{d2['id']}  {d1['debtor']} → {d1['creditor']} → {d2['creditor']}"
            for d1, d2 in chains
        ]
        embed.add_field(
            name=f"🔄 Transferable Chains ({len(chains)})",
            value="```\n" + "\n".join(chain_lines) + "\n```",
            inline=False,
        )

    return embed


class MarkPaidButton(discord.ui.Button):
    def __init__(self, debt: dict, row: int):
        self._debt_id = debt["id"]
        super().__init__(
            label=f"✅ #{debt['id']} {debt['debtor']} → {debt['creditor']} ({debt['session_date']})",
            style=discord.ButtonStyle.success,
            row=row,
        )

    async def callback(self, interaction: discord.Interaction):
        await mark_debt_paid(self._debt_id)
        debts = await get_debts()
        embed = build_debt_embed(debts)
        unpaid = [d for d in debts if not d["paid"]]
        chains = find_transferable_chains(debts)
        if unpaid:
            await interaction.response.edit_message(embed=embed, view=DebtView(unpaid, chains))
        else:
            await interaction.response.edit_message(embed=embed, view=None)


class TransferChainSelect(discord.ui.Select):
    def __init__(self, chains: list[tuple[dict, dict]]):
        options = [
            discord.SelectOption(
                label=f"#{d1['id']} {d1['debtor'][:10]}→{d1['creditor'][:10]} + #{d2['id']} {d2['debtor'][:10]}→{d2['creditor'][:10]}",
                value=f"{d1['id']},{d2['id']}",
                description=f"Result: {d1['debtor']} owes {d2['creditor']}",
            )
            for d1, d2 in chains
        ]
        super().__init__(
            placeholder="Select a debt chain to transfer…",
            options=options,
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        self.view.selected_chain = self.values[0]
        self.view.confirm_button.disabled = False
        await interaction.response.edit_message(view=self.view)


class ConfirmTransferButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="✅ Confirm Transfer",
            style=discord.ButtonStyle.success,
            disabled=True,
            row=1,
        )

    async def callback(self, interaction: discord.Interaction):
        debt1_id, debt2_id = map(int, self.view.selected_chain.split(","))
        try:
            await transfer_debt(debt1_id, debt2_id)
        except ValueError as exc:
            await interaction.response.send_message(
                f"⚠️ Transfer failed: {exc}", ephemeral=True
            )
            return
        debts = await get_debts()
        embed = build_debt_embed(debts)
        unpaid = [d for d in debts if not d["paid"]]
        chains = find_transferable_chains(debts)
        if unpaid:
            await interaction.response.edit_message(embed=embed, view=DebtView(unpaid, chains))
        else:
            await interaction.response.edit_message(embed=embed, view=None)


class CancelTransferButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="✖ Cancel",
            style=discord.ButtonStyle.secondary,
            row=1,
        )

    async def callback(self, interaction: discord.Interaction):
        debts = await get_debts()
        embed = build_debt_embed(debts)
        unpaid = [d for d in debts if not d["paid"]]
        chains = find_transferable_chains(debts)
        if unpaid:
            await interaction.response.edit_message(embed=embed, view=DebtView(unpaid, chains))
        else:
            await interaction.response.edit_message(embed=embed, view=None)


class TransferDebtView(BaseView):
    def __init__(self, chains: list[tuple[dict, dict]]):
        super().__init__(timeout=120)
        self.selected_chain: str | None = None
        self.confirm_button = ConfirmTransferButton()
        self.add_item(TransferChainSelect(chains))
        self.add_item(self.confirm_button)
        self.add_item(CancelTransferButton())


class TransferDebtButton(discord.ui.Button):
    def __init__(self, chains: list[tuple[dict, dict]], row: int):
        self._chains = chains
        super().__init__(
            label="🔄 Transfer Debt",
            style=discord.ButtonStyle.primary,
            row=row,
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.edit_message(
            content="Select a debt chain to transfer transitively:",
            embed=None,
            view=TransferDebtView(self._chains),
        )


class DebtView(BaseView):
    def __init__(self, unpaid_debts: list[dict], chains: list[tuple[dict, dict]] | None = None):
        super().__init__(timeout=120)
        chains = chains or []
        # Reserve row 4 for the transfer button when chains exist; otherwise show up to 5 debts.
        max_paid_buttons = 4 if chains else 5
        for i, debt in enumerate(unpaid_debts[:max_paid_buttons]):
            self.add_item(MarkPaidButton(debt, row=i))
        if chains:
            self.add_item(TransferDebtButton(chains, row=4))


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

    @app_commands.command(name="history", description="View historical snooker session scores")
    async def history(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)
        sessions = await get_completed_sessions()
        embed = build_history_embed(sessions, 0, 0)
        if sessions:
            total_sets = len(sessions[0]["sets"])
            await interaction.followup.send(embed=embed, view=HistoryView(0, len(sessions), 0, total_sets))
        else:
            await interaction.followup.send(embed=embed)

    @app_commands.command(name="debt", description="View debts, or mark a session's debt as paid")
    @app_commands.describe(session_date="Date of the session to mark as paid (YYYY-MM-DD)")
    async def debt(self, interaction: discord.Interaction, session_date: str = None):
        await interaction.response.defer(ephemeral=False)

        if session_date is not None:
            updated = await mark_debt_paid_by_date(session_date)
            if updated:
                await interaction.followup.send(
                    f"✅ Debt for **{session_date}** marked as paid!"
                )
            else:
                await interaction.followup.send(
                    f"⚠️ No outstanding debt found for **{session_date}**.",
                    ephemeral=True,
                )
            return

        debts = await get_debts()
        embed = build_debt_embed(debts)
        unpaid = [d for d in debts if not d["paid"]]
        chains = find_transferable_chains(debts)
        if unpaid:
            await interaction.followup.send(embed=embed, view=DebtView(unpaid, chains))
        else:
            await interaction.followup.send(embed=embed)


    @app_commands.command(name="sync", description="Trigger a GitHub → Gitea mirror sync")
    async def sync(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)

        if not config.GITEA_TOKEN:
            await interaction.followup.send(
                "⚠️ `GITEA_TOKEN` is not configured. Set it in the bot's environment.",
                ephemeral=True,
            )
            return

        url = f"{config.GITEA_URL.rstrip('/')}/api/v1/repos/{config.GITEA_MIRROR_REPO}/mirror-sync"
        headers = {
            "Authorization": f"token {config.GITEA_TOKEN}",
            "Content-Type": "application/json",
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers) as resp:
                    if resp.status == 200:
                        await interaction.followup.send(
                            f"✅ Mirror sync triggered for `{config.GITEA_MIRROR_REPO}`."
                        )
                    else:
                        body = await resp.text()
                        await interaction.followup.send(
                            f"⚠️ Gitea returned HTTP {resp.status}:\n```{body[:300]}```",
                            ephemeral=True,
                        )
        except Exception as e:
            log.error("Failed to trigger Gitea mirror sync: %s", e)
            await interaction.followup.send(
                f"❌ Failed to reach Gitea: `{e}`",
                ephemeral=True,
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(SnookerCog(bot))

