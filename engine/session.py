import uuid
import asyncio
import random
from datetime import datetime
from itertools import permutations
from typing import Optional
from dataclasses import dataclass, field

from engine.score import distribute_penalty, ranking_points, foul_penalty


@dataclass
class SetState:
    set_number: int
    player_order: list[str]
    current_player_idx: int = 0
    scores: dict[str, int] = field(default_factory=dict)
    scores_finalized: bool = False
    # break tracking: current live turn balls, and completed breaks per player
    current_break: list[str] = field(default_factory=list)
    breaks: dict[str, list[list[str]]] = field(default_factory=dict)
    # chronological event log for this set
    events: list[dict] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.now)
    # undo snapshots (capped at 20)
    _undo_stack: list[dict] = field(default_factory=list)

    def _save_snapshot(self):
        self._undo_stack.append({
            "scores": dict(self.scores),
            "current_break": list(self.current_break),
            "breaks": {p: [list(b) for b in brks] for p, brks in self.breaks.items()},
            "events": list(self.events),
            "current_player_idx": self.current_player_idx,
        })
        if len(self._undo_stack) > 20:
            self._undo_stack.pop(0)

    def can_undo(self) -> bool:
        return bool(self._undo_stack)

    def undo(self) -> bool:
        if not self._undo_stack:
            return False
        snap = self._undo_stack.pop()
        self.scores = snap["scores"]
        self.current_break = snap["current_break"]
        self.breaks = snap["breaks"]
        self.events = snap["events"]
        self.current_player_idx = snap["current_player_idx"]
        return True

    def _next_seq(self) -> int:
        return len(self.events) + 1

    def set_score(self, player: str, score: int):
        self.scores[player] = score

    def current_player(self) -> str:
        return self.player_order[self.current_player_idx]

    def next_player(self):
        """Advance turn, flushing the current break and logging an end_turn event."""
        self._save_snapshot()
        player = self.current_player()
        if self.current_break:
            self.breaks.setdefault(player, []).append(list(self.current_break))
            self.current_break = []
        self.events.append({"seq": self._next_seq(), "type": "end_turn", "player": player})
        self.current_player_idx = (self.current_player_idx + 1) % len(self.player_order)

    def add_score(self, player: str, ball: str):
        """Add a ball to the current player's score, live break, and event log."""
        self._save_snapshot()
        from engine.score import BALL_VALUES
        value = BALL_VALUES[ball]
        self.scores[player] = self.scores.get(player, 0) + value
        self.current_break.append(ball)
        self.events.append({"seq": self._next_seq(), "type": "ball", "player": player, "ball": ball, "value": value})

    def current_break_total(self) -> int:
        from engine.score import BALL_VALUES
        return sum(BALL_VALUES[b] for b in self.current_break)

    def apply_foul(self, fouling_player: str, ball: str, all_players: list[str], intentional: bool = False):
        self._save_snapshot()
        # A foul ends the fouling player's break
        if self.current_break:
            self.breaks.setdefault(fouling_player, []).append(list(self.current_break))
            self.current_break = []
        penalty = foul_penalty(ball)
        if intentional:
            # Full penalty awarded to the player immediately before the fouler in the turn order
            if fouling_player in self.player_order:
                fouler_idx = self.player_order.index(fouling_player)
                prev_player = self.player_order[(fouler_idx - 1) % len(self.player_order)]
                recipients = [prev_player]
            else:
                # Fallback: distribute among all other players if fouler not in order
                recipients = [p for p in all_players if p != fouling_player]
            per_player = penalty
        else:
            per_player = distribute_penalty(ball, len(all_players))
            recipients = [p for p in all_players if p != fouling_player]
        for p in recipients:
            self.scores[p] = self.scores.get(p, 0) + per_player
        self.events.append({
            "seq": self._next_seq(),
            "type": "foul",
            "fouler": fouling_player,
            "ball": ball,
            "penalty": penalty,
            "per_player": per_player,
            "recipients": recipients,
            "intentional": intentional,
        })

    def flush_break(self):
        """Save any in-progress break before the set ends."""
        player = self.current_player()
        if self.current_break:
            self.breaks.setdefault(player, []).append(list(self.current_break))
            self.current_break = []


@dataclass
class SnookerSession:
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    date: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    players: list[str] = field(default_factory=list)
    completed_sets: list[dict] = field(default_factory=list)
    current_set: Optional[SetState] = None
    channel_id: Optional[int] = None
    message_id: Optional[int] = None
    last_completed_set: Optional[dict] = None
    _perm_pool: list[list[int]] = field(default_factory=list)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def init_players(self, players: list[str]):
        self.players = players
        self._perm_pool = self._fresh_permutations()

    def _fresh_permutations(self) -> list[list[int]]:
        perms = [list(p) for p in permutations(range(len(self.players)))]
        random.shuffle(perms)
        return perms

    def _next_order(self) -> list[str]:
        # 2 players: always same order (only one meaningful permutation)
        if len(self.players) <= 2:
            return list(self.players)
        if not self._perm_pool:
            self._perm_pool = self._fresh_permutations()
        indices = self._perm_pool.pop(0)
        return [self.players[i] for i in indices]

    def start_set(self) -> SetState:
        set_number = len(self.completed_sets) + 1
        order = self._next_order()
        self.current_set = SetState(
            set_number=set_number,
            player_order=order,
            scores={p: 0 for p in self.players},
        )
        return self.current_set

    def save_current_set(self) -> dict:
        if not self.current_set:
            return {}
        self.current_set.flush_break()
        rp = ranking_points(self.current_set.scores, self.players)
        ended_at = datetime.now()
        duration_secs = int((ended_at - self.current_set.started_at).total_seconds())
        result = {
            "set_number": self.current_set.set_number,
            "player_order": self.current_set.player_order,
            "scores": dict(self.current_set.scores),
            "ranking_points": rp,
            "breaks": dict(self.current_set.breaks),
            "events": list(self.current_set.events),
            "duration_secs": duration_secs,
        }
        self.completed_sets.append(result)
        self.last_completed_set = result
        self.current_set = None
        return result

    def total_scores(self) -> dict[str, int]:
        """Sum of ranking points from completed sets only."""
        totals = {p: 0 for p in self.players}
        for s in self.completed_sets:
            for p, rp in s.get("ranking_points", {}).items():
                totals[p] = totals.get(p, 0) + rp
        return totals

    def total_raw_scores(self) -> dict[str, int]:
        """Sum of raw snooker scores (points potted) from completed sets — used as tiebreaker."""
        totals = {p: 0 for p in self.players}
        for s in self.completed_sets:
            for p, pts in s.get("scores", {}).items():
                totals[p] = totals.get(p, 0) + pts
        return totals
