import math

BALL_VALUES: dict[str, int] = {
    "red": 1,
    "yellow": 2,
    "green": 3,
    "brown": 4,
    "blue": 5,
    "pink": 6,
    "black": 7,
}

BALL_EMOJIS: dict[str, str] = {
    "red": "🔴",
    "yellow": "🟡",
    "green": "🟢",
    "brown": "🟤",
    "blue": "🔵",
    "pink": "🩷",
    "black": "⚫",
}

BALLS = list(BALL_VALUES.keys())


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
