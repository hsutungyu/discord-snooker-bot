import uuid
import random
from datetime import datetime
from itertools import permutations
from typing import Optional
from dataclasses import dataclass, field

from engine.score import distribute_penalty, ranking_points


@dataclass
class SetState:
    set_number: int
    player_order: list[str]
    current_player_idx: int = 0
    scores: dict[str, int] = field(default_factory=dict)
    scores_finalized: bool = False

    def set_score(self, player: str, score: int):
        self.scores[player] = score

    def current_player(self) -> str:
        return self.player_order[self.current_player_idx]

    def next_player(self):
        self.current_player_idx = (self.current_player_idx + 1) % len(self.player_order)

    def add_score(self, player: str, points: int):
        self.scores[player] = self.scores.get(player, 0) + points

    def apply_foul(self, fouling_player: str, ball: str, all_players: list[str]):
        per_player = distribute_penalty(ball, len(all_players))
        for p in all_players:
            if p != fouling_player:
                self.scores[p] = self.scores.get(p, 0) + per_player


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
        rp = ranking_points(self.current_set.scores, self.players)
        result = {
            "set_number": self.current_set.set_number,
            "player_order": self.current_set.player_order,
            "scores": dict(self.current_set.scores),
            "ranking_points": rp,
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
