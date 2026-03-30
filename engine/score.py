import math

BALL_VALUES: dict[str, int] = {
    "white": 0,
    "red": 1,
    "yellow": 2,
    "green": 3,
    "brown": 4,
    "blue": 5,
    "pink": 6,
    "black": 7,
}

BALL_EMOJIS: dict[str, str] = {
    "white": "⚪",
    "red": "🔴",
    "yellow": "🟡",
    "green": "🟢",
    "brown": "🟤",
    "blue": "🔵",
    "pink": "🩷",
    "black": "⚫",
}

# Coloured balls used for scoring buttons (white/cue ball is never potted for points)
BALLS = ["red", "yellow", "green", "brown", "blue", "pink", "black"]

# All balls available as foul options, including the white/cue ball
FOUL_BALLS = ["white"] + BALLS


def foul_penalty(ball: str) -> int:
    """Minimum 4 points, or the ball's value if higher."""
    return max(4, BALL_VALUES[ball])


def distribute_penalty(ball: str, total_players: int) -> int:
    """Points awarded to each non-fouling player (ceiling division)."""
    penalty = foul_penalty(ball)
    remaining = total_players - 1
    if remaining <= 0:
        return 0
    return math.ceil(penalty / remaining)


def ranking_points(scores: dict[str, int], players: list[str]) -> dict[str, int]:
    """
    Convert set scores into ranking points.
    N players → 1st gets N-1 pts, last gets 0 pt (N-1, N-2, …, 0).
    Tied players receive the higher rank's points; subsequent ranks are skipped
    (standard competition / Olympic ranking).
    """
    n = len(players)
    sorted_players = sorted(players, key=lambda p: scores.get(p, 0), reverse=True)
    result: dict[str, int] = {}
    rank = 1
    i = 0
    while i < n:
        tied_score = scores.get(sorted_players[i], 0)
        j = i + 1
        while j < n and scores.get(sorted_players[j], 0) == tied_score:
            j += 1
        pts = n - rank
        for k in range(i, j):
            result[sorted_players[k]] = pts
        rank += (j - i)
        i = j
    return result
