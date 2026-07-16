"""Session-level integration test: start_set uses the SNOOKER-3 order logic."""

import pytest

from engine.session import SnookerSession


def _session_with(players, *, mode="full", player_mapping=None):
    s = SnookerSession(mode=mode)
    s.init_players(players)
    # Override the random mapping with a deterministic one so the test
    # is hermetic — the spec'd rotation logic is independently covered by
    # test_order.py.
    if player_mapping is not None:
        s.player_mapping = player_mapping
    return s


def test_start_set_uses_player_mapping_in_full_mode():
    from engine.order import PlayerMapping

    mapping = PlayerMapping(
        letter_to_player={"A": "A", "B": "B", "C": "C"},
        break_order=["A", "B", "C"],
        order_seq_start=0,
        set_count=0,
    )
    s = _session_with(["A", "B", "C"], mode="full", player_mapping=mapping)
    cs = s.start_set()
    # break_order[0] == "A" → A is first. The hardcoded 3-player table
    # starts with ABC and rotating so A is first is a no-op.
    assert cs.player_order == ["A", "B", "C"]


def test_start_set_rotates_for_break_player_in_full_mode():
    from engine.order import PlayerMapping

    mapping = PlayerMapping(
        letter_to_player={"A": "A", "B": "B", "C": "C"},
        break_order=["B", "A", "C"],
        order_seq_start=0,
        set_count=0,
    )
    s = _session_with(["A", "B", "C"], mode="full", player_mapping=mapping)
    cs = s.start_set()
    # Hardcoded order ABC rotated so B (originally at index 1) is first
    # yields BCA.
    assert cs.player_order == ["B", "C", "A"]


def test_start_set_uses_players_order_in_record_mode():
    """Record mode ignores the deterministic ordering — users enter
    final scores directly, so any rotation would only confuse the UI."""
    from engine.order import PlayerMapping

    mapping = PlayerMapping(
        letter_to_player={"A": "B", "B": "A", "C": "C"},
        break_order=["A", "B", "C"],
        order_seq_start=0,
        set_count=0,
    )
    s = _session_with(["A", "B", "C"], mode="record", player_mapping=mapping)
    cs = s.start_set()
    assert cs.player_order == ["A", "B", "C"]


def test_completed_set_count_advances_mapping_for_next_set():
    from engine.order import PlayerMapping

    mapping = PlayerMapping(
        letter_to_player={"A": "A", "B": "B", "C": "C", "D": "D"},
        break_order=["A", "B", "C", "D"],
        order_seq_start=0,
        set_count=0,
    )
    s = _session_with(["A", "B", "C", "D"], mode="full", player_mapping=mapping)
    s.start_set()
    s.save_current_set()
    before = mapping.set_count
    s.start_set()
    assert mapping.set_count == before + 1
