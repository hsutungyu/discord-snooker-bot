"""Lightweight Discord notification client for the Snooker web backend.

This module owns a single ``discord.Client`` instance (no slash commands).
It posts/updates scoreboard embeds in a configured channel whenever the
backend mutates session state, and sends break-celebration messages when
a break meets or exceeds ``config.BREAK_ALERT_THRESHOLD``.

All public functions are safe no-ops when the bot is unconfigured or not
yet connected—callers do not need to guard against ``None``.
"""
from __future__ import annotations

import logging
from typing import Optional

import discord

import config
from engine.score import BALL_VALUES, BALL_EMOJIS

log = logging.getLogger(__name__)

_bot: Optional[discord.Client] = None


# ---------------------------------------------------------------------------
# Bot lifecycle
# ---------------------------------------------------------------------------

def get_bot() -> Optional[discord.Client]:
    return _bot


def create_bot() -> discord.Client:
    """Instantiate and configure the Discord notification client."""
    global _bot
    intents = discord.Intents.default()
    _bot = discord.Client(intents=intents)

    @_bot.event
    async def on_ready():
        log.info(
            "Discord notification bot ready: %s (ID: %s)",
            _bot.user,
            _bot.user.id,
        )

    return _bot


# ---------------------------------------------------------------------------
# Embed helpers
# ---------------------------------------------------------------------------

def _fmt_duration(secs: int) -> str:
    m, s = divmod(secs, 60)
    return f"{m}m {s:02d}s"


def _format_recent_events(events: list[dict], max_lines: int = 10) -> tuple[list[str], bool]:
    """Return (lines, has_earlier) for the most recent grouped event lines."""
    lines_rev: list[str] = []
    i = len(events) - 1
    while i >= 0 and len(lines_rev) < max_lines:
        ev = events[i]
        if ev["type"] == "ball":
            player = ev["player"]
            balls_rev: list[str] = []
            end_seq = ev["seq"]
            start_seq = end_seq
            while i >= 0 and events[i]["type"] == "ball" and events[i]["player"] == player:
                balls_rev.append(events[i]["ball"])
                start_seq = events[i]["seq"]
                i -= 1
            balls = list(reversed(balls_rev))
            total = sum(BALL_VALUES[b] for b in balls)
            balls_str = " ".join(BALL_EMOJIS[b] for b in balls)
            seq_label = f"{start_seq}" if start_seq == end_seq else f"{start_seq}-{end_seq}"
            lines_rev.append(f"{seq_label:>5}. {player:<12} {balls_str} (+{total})")
        elif ev["type"] == "foul":
            recipients = ", ".join(ev["recipients"])
            intent_tag = " [intentional]" if ev.get("intentional") else ""
            per_player_str = (
                f"+{ev['per_player']} ea → {recipients}"
                if not ev.get("intentional") and len(ev["recipients"]) > 1
                else f"+{ev['per_player']} → {recipients}"
            )
            lines_rev.append(
                f"{ev['seq']:>5}. 🚫 {ev['fouler']:<11} {BALL_EMOJIS[ev['ball']]} "
                f"{ev['ball'].capitalize()} (pen {ev['penalty']}, {per_player_str}{intent_tag})"
            )
            i -= 1
        elif ev["type"] == "end_turn":
            i -= 1
        else:
            lines_rev.append(f"{ev['seq']:>5}. {ev}")
            i -= 1
    return list(reversed(lines_rev)), i >= 0


def build_scoreboard_embed(session) -> discord.Embed:
    """Build a Discord embed showing the current session state."""
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

        if cs.events:
            feed_lines, has_earlier = _format_recent_events(cs.events, max_lines=10)
            if has_earlier:
                feed_lines = ["… (earlier)"] + feed_lines
            embed.add_field(
                name="📋 Set Log",
                value="```\n" + "\n".join(feed_lines) + "\n```",
                inline=False,
            )

    return embed


def build_session_ended_embed(session, standings: list[dict], debt: str) -> discord.Embed:
    """Build a Discord embed for a completed session."""
    medals = ["🥇", "🥈", "🥉"] + ["  "] * 10
    lines = [
        f"{medals[i]} {s['player']:<12} {s['ranking_points']:>3} rp"
        for i, s in enumerate(standings)
    ]
    embed = discord.Embed(title=f"🏁 Session Ended — {session.date}", color=0xE74C3C)
    embed.add_field(
        name="Final Standings",
        value="```\n" + "\n".join(lines) + "\n```",
        inline=False,
    )
    if debt:
        embed.add_field(name="Bubble Tea Debt", value=f"🧋 {debt}", inline=False)
    embed.set_footer(text=f"{len(session.completed_sets)} set(s) played")
    return embed


# ---------------------------------------------------------------------------
# Public notification functions
# ---------------------------------------------------------------------------

async def post_scoreboard(session, channel_id: int) -> Optional[int]:
    """Post or update the live scoreboard embed.

    Returns the Discord message ID of the (possibly new) scoreboard message,
    or ``None`` if the bot is not ready or the send fails.
    """
    if _bot is None or not _bot.is_ready():
        return None
    channel = _bot.get_channel(channel_id)
    if channel is None:
        log.warning("Discord channel %d not found or bot lacks access", channel_id)
        return None

    embed = build_scoreboard_embed(session)

    if session.message_id:
        try:
            msg = await channel.fetch_message(session.message_id)
            await msg.edit(embed=embed)
            return session.message_id
        except discord.NotFound:
            log.info(
                "Scoreboard message %d gone; posting a new one", session.message_id
            )
        except discord.HTTPException as exc:
            log.warning("Failed to edit scoreboard message: %s", exc)
            return None

    try:
        msg = await channel.send(embed=embed)
        return msg.id
    except discord.HTTPException as exc:
        log.warning("Failed to send scoreboard message: %s", exc)
        return None


async def post_break_celebration(
    channel_id: int, message: Optional[str]
) -> None:
    """Send a prebuilt break-celebration message to the channel.

    The message string is built by ``engine.session.build_break_celebration_message``
    so the FastAPI backend, Discord notifier, and legacy Discord cog
    share one source of truth for the celebration copy. ``message=None``
    is a no-op (defensive: callers should already gate on the threshold).
    """
    if not message:
        return
    if _bot is None or not _bot.is_ready():
        return
    channel = _bot.get_channel(channel_id)
    if channel is None:
        return
    try:
        await channel.send(message)
    except discord.HTTPException as exc:
        log.warning("Failed to send break celebration: %s", exc)


async def post_session_ended(
    channel_id: int,
    message_id: Optional[int],
    session,
    standings: list[dict],
    debt: str,
) -> None:
    """Edit the live scoreboard message (or send a new one) with the final results."""
    if _bot is None or not _bot.is_ready():
        return
    channel = _bot.get_channel(channel_id)
    if channel is None:
        return

    embed = build_session_ended_embed(session, standings, debt)

    if message_id:
        try:
            msg = await channel.fetch_message(message_id)
            await msg.edit(embed=embed)
            return
        except discord.NotFound:
            pass
        except discord.HTTPException as exc:
            log.warning("Failed to edit session-ended message: %s", exc)
            return

    try:
        await channel.send(embed=embed)
    except discord.HTTPException as exc:
        log.warning("Failed to send session-ended message: %s", exc)
