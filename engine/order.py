"""
Pure player-order logic for full-mode sets.

Implements SNOOKER-3 ("Player order refactor"). At session start we pick:

1. a random bijection between the participating players and the letters A,
   B, C, D (filling only as many letters as there are players);
2. a random ``break_order`` — a permutation of the same letters — that
   decides which player breaks (i.e. plays first) on each set;
3. a random ``order_seq_start`` index into the hardcoded playing-order
   table for that player count (see ``HARD_CODED_ORDERS``).

For each new set we read the next hardcoded order (cycling through the
table), translate the letters to real players via the bijection, and then
rotate so that the player assigned to ``break_order[set_count % n]`` is
first. This guarantees two adjacent sets always differ in who breaks
first, while still cycling deterministically through the hardcoded orders
themselves.

This module has no database or network dependencies and is the single
source of truth for the order algorithm — the session layer and the
backend simply persist and forward the ``PlayerMapping`` it produces.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Iterable

# ---------------------------------------------------------------------------
# Hardcoded playing-order tables from SNOOKER-3.
#
# Each entry is a tuple of letter labels (A/B/C/D). For a session with
# fewer than four players we only use the first ``len(players)`` letters.
# The lists as written are the literal spec:
#
#   * 2 players: [AB]
#   * 3 players: [ABC, ACB]
#   * 4 players: [ABCD, ABDC, ACBD, ACDB, ADBC, ADCB]
#
# Note: for 3 and 4 players every listed order begins with "A". This is
# intentional — the break player for the raw order is always A. Rotation
# (see ``build_set_order``) moves A out of position 1 to satisfy the
# current break-order slot.
# ---------------------------------------------------------------------------
HARD_CODED_ORDERS: dict[int, tuple[tuple[str, ...], ...]] = {
    2: (("A", "B"),),
    3: (
        ("A", "B", "C"),
        ("A", "C", "B"),
    ),
    4: (
        ("A", "B", "C", "D"),
        ("A", "B", "D", "C"),
        ("A", "C", "B", "D"),
        ("A", "C", "D", "B"),
        ("A", "D", "B", "C"),
        ("A", "D", "C", "B"),
    ),
}

# Letters used as bijection keys. The slice [:n] picks the first ``n``
# letters for an n-player session.
LETTERS: tuple[str, ...] = ("A", "B", "C", "D")


@dataclass
class PlayerMapping:
    """A session's stable player↔letter bijection plus order schedule.

    A single ``PlayerMapping`` is created at full-mode session start and
    mutated in place as sets complete (``set_count`` increment). The
    bijection ``letter_to_player`` and the ``break_order`` / starting
    sequence offset are picked randomly once and then held constant for
    the life of the session.
    """

    letter_to_player: dict[str, str]
    break_order: list[str]
    order_seq_start: int
    set_count: int = 0

    def players(self) -> list[str]:
        """Return the participating players in letter order (A first)."""
        n = len(self.letter_to_player)
        return [self.letter_to_player[LETTERS[i]] for i in range(n)]

    @property
    def n(self) -> int:
        return len(self.letter_to_player)


def new_random_mapping(
    players: list[str], rng: random.Random | None = None
) -> PlayerMapping:
    """Build a fresh random mapping for ``players``.

    - Random bijection of ``players`` onto the first ``len(players)``
      letters (``A`` for a 2-player session, ``A/B/C`` for 3, all four
      for 4).
    - ``break_order`` — a random permutation of the same letter set; this
      is the *slot* order, not an initial order. Each successive set
      takes the next break-order player as its first player.
    - ``order_seq_start`` — a random index into the hardcoded order table
      for the player count, so different sessions start on different
      hardcoded orders.
    """
    rng = rng or random.Random()
    n = len(players)
    if n < 2 or n > 4:
        raise ValueError(f"Player count must be 2..4, got {n}")
    if len(set(players)) != n:
        raise ValueError("Players must be unique")

    letters = list(LETTERS[:n])
    shuffled_players = list(players)
    rng.shuffle(shuffled_players)
    letter_to_player = dict(zip(letters, shuffled_players))

    # `break_order` holds letters (not players) — it indexes the slot
    # assignment by letter, which is then translated to a real player
    # via ``letter_to_player``.
    break_order = list(letters)
    rng.shuffle(break_order)

    order_seq_start = rng.randrange(len(HARD_CODED_ORDERS[n]))

    return PlayerMapping(
        letter_to_player=letter_to_player,
        break_order=break_order,
        order_seq_start=order_seq_start,
        set_count=0,
    )


def _rotate_to_first(seq: list[str], first: str) -> list[str]:
    """Return a copy of ``seq`` rotated so that ``first`` is at index 0.

    ``first`` is assumed to appear exactly once in ``seq``. If it doesn't
    (defensive guard), the original order is returned unchanged.
    """
    if not seq or first not in seq:
        return list(seq)
    idx = seq.index(first)
    if idx == 0:
        return list(seq)
    return list(seq[idx:]) + list(seq[:idx])


def build_set_order(mapping: PlayerMapping) -> list[str]:
    """Compute the ``player_order`` for the next set.

    Steps:

    1. Pick a hardcoded letter-order via
       ``HARD_CODED_ORDERS[n][(order_seq_start + set_count) % len(table)]``.
       For n == 2 the table has length 1, so the modulo is a no-op and
       rotation alone produces the alternation.
    2. Translate letters to real players via ``letter_to_player``.
    3. Rotate so that the player mapped to
       ``break_order[set_count % n]`` is first.
    4. Increment ``set_count``.
    """
    n = mapping.n
    table = HARD_CODED_ORDERS[n]
    idx = (mapping.order_seq_start + mapping.set_count) % len(table)
    letters = table[idx]
    player_seq = [mapping.letter_to_player[L] for L in letters]

    break_letter = mapping.break_order[mapping.set_count % n]
    break_player = mapping.letter_to_player[break_letter]
    rotated = _rotate_to_first(player_seq, break_player)

    mapping.set_count += 1
    return rotated


def _letters_for(players: Iterable[str], mapping: PlayerMapping) -> dict[str, str]:
    """Helper for tests: invert ``letter_to_player``."""
    return {player: letter for letter, player in mapping.letter_to_player.items()}
