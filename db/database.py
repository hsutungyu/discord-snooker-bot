import json
import aiosqlite
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "snooker.db"


async def init_db():
    DB_PATH.parent.mkdir(exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                date TEXT NOT NULL,
                players TEXT NOT NULL,
                started_at TEXT NOT NULL,
                ended_at TEXT,
                channel_id INTEGER,
                message_id INTEGER
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS sets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                set_number INTEGER NOT NULL,
                player_order TEXT NOT NULL,
                scores TEXT NOT NULL,
                completed_at TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            )
        """)
        # Migration: add ranking_points column if it doesn't exist yet
        try:
            await db.execute("ALTER TABLE sets ADD COLUMN ranking_points TEXT")
        except Exception:
            pass  # column already exists
        await db.commit()


async def save_session(session) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT OR REPLACE INTO sessions
                (id, date, players, started_at, channel_id, message_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                session.session_id,
                session.date,
                json.dumps(session.players),
                datetime.now().isoformat(),
                session.channel_id,
                session.message_id,
            ),
        )
        await db.commit()


async def save_set(session_id: str, set_data: dict) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO sets (session_id, set_number, player_order, scores, ranking_points, completed_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                set_data["set_number"],
                json.dumps(set_data["player_order"]),
                json.dumps(set_data["scores"]),
                json.dumps(set_data.get("ranking_points", {})),
                datetime.now().isoformat(),
            ),
        )
        await db.commit()


async def end_session(session_id: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE sessions SET ended_at = ? WHERE id = ?",
            (datetime.now().isoformat(), session_id),
        )
        await db.commit()


async def get_completed_sessions() -> list[dict]:
    """Return all completed sessions with per-set details, newest first."""
    from engine.score import ranking_points as compute_rp

    if not DB_PATH.exists():
        return []

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        async with db.execute(
            "SELECT * FROM sessions WHERE ended_at IS NOT NULL ORDER BY ended_at DESC"
        ) as cursor:
            session_rows = await cursor.fetchall()

        result = []
        for row in session_rows:
            session = dict(row)
            session["players"] = json.loads(session["players"])

            async with db.execute(
                "SELECT * FROM sets WHERE session_id = ? ORDER BY set_number",
                (session["id"],),
            ) as cursor:
                set_rows = await cursor.fetchall()

            sets = []
            ranking_totals: dict[str, int] = {p: 0 for p in session["players"]}
            for set_row in set_rows:
                s = dict(set_row)
                s["scores"] = json.loads(s["scores"])
                s["player_order"] = json.loads(s["player_order"])
                rp_raw = s.get("ranking_points")
                if rp_raw:
                    s["ranking_points"] = json.loads(rp_raw)
                else:
                    # Legacy rows without ranking_points: derive from scores
                    s["ranking_points"] = compute_rp(s["scores"], session["players"])
                for p, rp in s["ranking_points"].items():
                    ranking_totals[p] = ranking_totals.get(p, 0) + rp
                sets.append(s)

            session["sets"] = sets
            session["ranking_totals"] = ranking_totals
            result.append(session)

        return result
