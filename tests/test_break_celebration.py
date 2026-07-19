"""Tests for the SNOOKER-1 break-celebration message helper.

Single source of truth for the celebration copy used by the FastAPI
backend, the Discord notification bot, and the legacy Discord cog.
The Discord side is exercised separately in bot/integration tests; here
we only cover the message builder.
"""

import pytest

from engine.score import BALL_EMOJIS
from engine.session import build_break_celebration_message


THRESHOLD = 10


def _balls(*names: str) -> list[str]:
    return list(names)


# ---------------------------------------------------------------------------
# Below threshold → no message (suppress noise)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("total", [0, 1, 5, 9])
def test_below_threshold_returns_none(total):
    assert build_break_celebration_message(
        "Anson", total, _balls("red", "black"), THRESHOLD,
    ) is None


# ---------------------------------------------------------------------------
# At/above threshold → celebration message
# ---------------------------------------------------------------------------

def test_at_threshold_emits_celebration_message():
    msg = build_break_celebration_message(
        "Anson", 10, _balls("red", "black", "red", "red", "black", "black", "red"), THRESHOLD,
    )
    assert msg is not None
    assert "🎉" in msg
    assert "🥳" in msg
    assert "Break celebration" in msg
    assert "Anson" in msg
    assert "**10**" in msg


def test_above_threshold_emits_celebration_message():
    msg = build_break_celebration_message(
        "Desmond", 27, _balls("black", "pink", "blue", "brown"), THRESHOLD,
    )
    assert msg is not None
    assert "Desmond" in msg
    assert "**27**" in msg


def test_message_includes_all_ball_emojis_in_order():
    balls = _balls("red", "yellow", "green", "brown", "blue")
    msg = build_break_celebration_message(
        "Justin", sum(__import__("engine.score", fromlist=["BALL_VALUES"]).BALL_VALUES[b] for b in balls),
        balls, THRESHOLD,
    )
    assert msg is not None
    # Ball emojis appear in input order, space-joined, after the header line.
    expected = " ".join(BALL_EMOJIS[b] for b in balls)
    assert msg.rstrip().endswith(expected)


def test_threshold_is_respected_when_changed():
    """The helper takes threshold as a parameter so callers can override it
    (e.g. for tests or alternate scoring systems)."""
    # total = 8 < 12 → no message at threshold=12
    assert build_break_celebration_message(
        "Tung", 8, _balls("black", "black"), threshold=12,
    ) is None
    # same 8 points IS celebrated at threshold=8
    assert build_break_celebration_message(
        "Tung", 8, _balls("black", "black"), threshold=8,
    ) is not None


def test_empty_ball_list_still_produces_celebration():
    """A player could theoretically finish with no potted balls (e.g. all
    fouls); the celebration should still announce the total."""
    msg = build_break_celebration_message("Anson", 10, [], THRESHOLD)
    assert msg is not None
    assert "Anson" in msg
    assert "**10**" in msg