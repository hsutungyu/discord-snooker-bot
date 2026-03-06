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
            INSERT INTO sets (session_id, set_number, player_order, scores, completed_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                session_id,
                set_data["set_number"],
                json.dumps(set_data["player_order"]),
                json.dumps(set_data["scores"]),
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
