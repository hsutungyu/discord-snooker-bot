import json
import asyncpg
from datetime import datetime
from typing import Optional

_pool: Optional[asyncpg.Pool] = None

SCHEMA = "snooker"


async def _init_conn(conn: asyncpg.Connection) -> None:
    """Register JSONB codec so Python dicts/lists are handled automatically."""
    await conn.set_type_codec(
        "jsonb",
        encoder=json.dumps,
        decoder=json.loads,
        schema="pg_catalog",
    )


async def init_db(dsn: str) -> None:
    global _pool
    _pool = await asyncpg.create_pool(dsn, init=_init_conn)
    async with _pool.acquire() as conn:
        await conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {SCHEMA}.sessions (
                id TEXT PRIMARY KEY,
                date TEXT NOT NULL,
                players JSONB NOT NULL,
                started_at TEXT NOT NULL,
                ended_at TEXT,
                channel_id BIGINT,
                message_id BIGINT
            )
        """)
        await conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {SCHEMA}.sets (
                id SERIAL PRIMARY KEY,
                session_id TEXT NOT NULL REFERENCES {SCHEMA}.sessions(id),
                set_number INTEGER NOT NULL,
                player_order JSONB NOT NULL,
                scores JSONB NOT NULL,
                ranking_points JSONB,
                completed_at TEXT NOT NULL
            )
        """)
        await conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {SCHEMA}.debts (
                id SERIAL PRIMARY KEY,
                session_id TEXT NOT NULL REFERENCES {SCHEMA}.sessions(id),
                session_date TEXT NOT NULL,
                debtor TEXT NOT NULL,
                creditor TEXT NOT NULL,
                paid BOOLEAN NOT NULL DEFAULT FALSE,
                paid_at TEXT
            )
        """)


async def save_session(session) -> None:
    async with _pool.acquire() as conn:
        await conn.execute(
            f"""
            INSERT INTO {SCHEMA}.sessions
                (id, date, players, started_at, channel_id, message_id)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (id) DO UPDATE SET
                players = EXCLUDED.players,
                channel_id = EXCLUDED.channel_id,
                message_id = EXCLUDED.message_id
            """,
            session.session_id,
            session.date,
            session.players,
            datetime.now().isoformat(),
            session.channel_id,
            session.message_id,
        )


async def save_set(session_id: str, set_data: dict) -> None:
    async with _pool.acquire() as conn:
        await conn.execute(
            f"""
            INSERT INTO {SCHEMA}.sets
                (session_id, set_number, player_order, scores, ranking_points, completed_at)
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            session_id,
            set_data["set_number"],
            set_data["player_order"],
            set_data["scores"],
            set_data.get("ranking_points", {}),
            datetime.now().isoformat(),
        )


async def end_session(session_id: str) -> None:
    async with _pool.acquire() as conn:
        await conn.execute(
            f"UPDATE {SCHEMA}.sessions SET ended_at = $1 WHERE id = $2",
            datetime.now().isoformat(),
            session_id,
        )


async def get_completed_sessions() -> list[dict]:
    """Return all completed sessions with per-set details, newest first."""
    from engine.score import ranking_points as compute_rp

    async with _pool.acquire() as conn:
        session_rows = await conn.fetch(
            f"SELECT * FROM {SCHEMA}.sessions WHERE ended_at IS NOT NULL ORDER BY ended_at DESC"
        )

        result = []
        for row in session_rows:
            session = dict(row)

            set_rows = await conn.fetch(
                f"SELECT * FROM {SCHEMA}.sets WHERE session_id = $1 ORDER BY set_number",
                session["id"],
            )

            sets = []
            ranking_totals: dict[str, int] = {p: 0 for p in session["players"]}
            for set_row in set_rows:
                s = dict(set_row)
                rp = s.get("ranking_points") or {}
                if not rp:
                    rp = compute_rp(s["scores"], session["players"])
                s["ranking_points"] = rp
                for p, pts in rp.items():
                    ranking_totals[p] = ranking_totals.get(p, 0) + pts
                sets.append(s)

            session["sets"] = sets
            session["ranking_totals"] = ranking_totals
            result.append(session)

        return result


async def create_debt(session_id: str, session_date: str, debtor: str, creditor: str) -> None:
    async with _pool.acquire() as conn:
        await conn.execute(
            f"""
            INSERT INTO {SCHEMA}.debts (session_id, session_date, debtor, creditor, paid)
            VALUES ($1, $2, $3, $4, FALSE)
            """,
            session_id,
            session_date,
            debtor,
            creditor,
        )


async def get_debts() -> list[dict]:
    """Return all debts, unpaid first then paid, newest first within each group."""
    async with _pool.acquire() as conn:
        rows = await conn.fetch(
            f"SELECT * FROM {SCHEMA}.debts ORDER BY paid ASC, id DESC"
        )
        return [dict(r) for r in rows]


async def mark_debt_paid(debt_id: int) -> None:
    async with _pool.acquire() as conn:
        await conn.execute(
            f"UPDATE {SCHEMA}.debts SET paid = TRUE, paid_at = $1 WHERE id = $2",
            datetime.now().isoformat(),
            debt_id,
        )
