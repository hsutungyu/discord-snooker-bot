from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

import aiohttp
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import config
from db.database import (
    create_debt,
    delete_session,
    end_session,
    get_completed_sessions,
    get_debts,
    init_db,
    mark_debt_paid,
    mark_debt_paid_by_date,
    save_session,
    save_set,
    transfer_debt,
)
from engine.score import BALLS, BALL_EMOJIS, BALL_VALUES, foul_penalty
from engine.session import SnookerSession

log = logging.getLogger(__name__)


@dataclass
class LiveSession:
    session: SnookerSession
    mode: Literal["full", "record"]


active_sessions: dict[str, LiveSession] = {}


class CreateSessionRequest(BaseModel):
    players: list[str] = Field(min_length=2, max_length=4)
    mode: Literal["full", "record"]


class BallRequest(BaseModel):
    ball: str


class FoulRequest(BaseModel):
    fouling_player: str
    ball: str
    intentional: bool = False


class RecordScoresRequest(BaseModel):
    scores: dict[str, int]


class PayByDateRequest(BaseModel):
    session_date: str


class TransferDebtRequest(BaseModel):
    debt1_id: int
    debt2_id: int


app = FastAPI(title="Snooker Web API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup() -> None:
    if not config.DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set in .env")
    await init_db(config.DATABASE_URL)


def _validate_ball(ball: str) -> None:
    if ball not in BALL_VALUES:
        raise HTTPException(status_code=400, detail=f"Invalid ball: {ball}")


def _get_live_session(session_id: str) -> LiveSession:
    live = active_sessions.get(session_id)
    if not live:
        raise HTTPException(status_code=404, detail="Active session not found")
    return live


def _ranking_standings(session: SnookerSession) -> list[dict]:
    rp_totals = session.total_scores()
    raw_totals = session.total_raw_scores()
    sorted_players = sorted(
        session.players,
        key=lambda p: (rp_totals.get(p, 0), raw_totals.get(p, 0)),
        reverse=True,
    )
    return [
        {
            "player": player,
            "ranking_points": rp_totals.get(player, 0),
            "raw_total": raw_totals.get(player, 0),
        }
        for player in sorted_players
    ]


def _serialize_session(live: LiveSession) -> dict:
    session = live.session
    cs = session.current_set
    last_set = session.last_completed_set

    payload = {
        "session_id": session.session_id,
        "date": session.date,
        "mode": live.mode,
        "players": session.players,
        "completed_sets": len(session.completed_sets),
        "standings": _ranking_standings(session),
        "last_completed_set": last_set,
        "current_set": None,
    }
    if cs:
        payload["current_set"] = {
            "set_number": cs.set_number,
            "player_order": cs.player_order,
            "current_player": cs.current_player(),
            "current_player_idx": cs.current_player_idx,
            "scores": cs.scores,
            "current_break": cs.current_break,
            "current_break_total": cs.current_break_total(),
            "breaks": cs.breaks,
            "events": cs.events,
            "scores_finalized": cs.scores_finalized,
            "can_undo": cs.can_undo(),
        }
    return payload


async def _end_live_session(live: LiveSession) -> dict:
    session = live.session
    mode = live.mode
    async with session._lock:
        cs = session.current_set
        if mode == "full":
            if cs and any(v > 0 for v in cs.scores.values()):
                set_data = session.save_current_set()
                if set_data:
                    await save_set(session.session_id, set_data)
            else:
                session.current_set = None
        else:
            if cs and cs.scores_finalized:
                set_data = session.save_current_set()
                if set_data:
                    await save_set(session.session_id, set_data)
            else:
                session.current_set = None

        active_sessions.pop(session.session_id, None)

        if not session.completed_sets:
            await delete_session(session.session_id)
            return {
                "discarded": True,
                "message": "No scores were recorded. The session has been discarded.",
            }

        await end_session(session.session_id)

        standings = _ranking_standings(session)
        creditor = standings[0]["player"]
        debtor = standings[-1]["player"]
        debt_line = ""
        if len(session.players) >= 2 and creditor != debtor:
            await create_debt(session.session_id, session.date, debtor, creditor)
            debt_line = f"{debtor} owes a bubble tea to {creditor}"

        return {
            "discarded": False,
            "standings": standings,
            "sets_played": len(session.completed_sets),
            "debt": debt_line,
        }


def _find_transferable_chains(debts: list[dict]) -> list[dict]:
    unpaid = [d for d in debts if not d["paid"]]
    chains = []
    for d1 in unpaid:
        for d2 in unpaid:
            if (
                d1["id"] != d2["id"]
                and d1["creditor"] == d2["debtor"]
                and d1["debtor"] != d2["creditor"]
            ):
                chains.append(
                    {
                        "debt1_id": d1["id"],
                        "debt2_id": d2["id"],
                        "path": f"{d1['debtor']} -> {d1['creditor']} -> {d2['creditor']}",
                    }
                )
    return chains


@app.get("/api/meta")
async def get_meta() -> dict:
    return {
        "players": config.PLAYERS,
        "break_alert_threshold": config.BREAK_ALERT_THRESHOLD,
        "balls": [
            {"name": b, "value": BALL_VALUES[b], "emoji": BALL_EMOJIS[b]}
            for b in BALLS
        ],
    }


@app.post("/api/sessions")
async def create_session(req: CreateSessionRequest) -> dict:
    selected = [p for p in config.PLAYERS if p in req.players]
    if len(selected) != len(set(req.players)) or len(selected) < 2:
        raise HTTPException(status_code=400, detail="Players must be unique and from configured list")

    session = SnookerSession()
    session.init_players(selected)
    session.start_set()
    await save_session(session)

    live = LiveSession(session=session, mode=req.mode)
    active_sessions[session.session_id] = live
    return _serialize_session(live)


@app.get("/api/sessions/active")
async def get_active_sessions() -> dict:
    return {"sessions": [_serialize_session(s) for s in active_sessions.values()]}


@app.get("/api/sessions/{session_id}")
async def get_active_session(session_id: str) -> dict:
    return _serialize_session(_get_live_session(session_id))


@app.post("/api/sessions/{session_id}/ball")
async def add_ball(session_id: str, req: BallRequest) -> dict:
    _validate_ball(req.ball)
    live = _get_live_session(session_id)
    if live.mode != "full":
        raise HTTPException(status_code=400, detail="Ball actions are only available in full mode")

    session = live.session
    async with session._lock:
        cs = session.current_set
        if not cs:
            raise HTTPException(status_code=400, detail="No current set")
        cs.add_score(cs.current_player(), req.ball)
    return _serialize_session(live)


@app.post("/api/sessions/{session_id}/end-turn")
async def end_turn(session_id: str) -> dict:
    live = _get_live_session(session_id)
    if live.mode != "full":
        raise HTTPException(status_code=400, detail="End-turn is only available in full mode")

    session = live.session
    alert = None
    async with session._lock:
        cs = session.current_set
        if not cs:
            raise HTTPException(status_code=400, detail="No current set")
        prev_player = cs.current_player()
        prev_break = list(cs.current_break)
        cs.next_player()
        if prev_break:
            total = sum(BALL_VALUES[b] for b in prev_break)
            if total >= config.BREAK_ALERT_THRESHOLD:
                alert = {
                    "player": prev_player,
                    "total": total,
                    "balls": prev_break,
                }

    payload = _serialize_session(live)
    payload["break_alert"] = alert
    return payload


@app.post("/api/sessions/{session_id}/foul")
async def apply_foul(session_id: str, req: FoulRequest) -> dict:
    _validate_ball(req.ball)
    live = _get_live_session(session_id)
    if live.mode != "full":
        raise HTTPException(status_code=400, detail="Foul is only available in full mode")

    session = live.session
    async with session._lock:
        if req.fouling_player not in session.players:
            raise HTTPException(status_code=400, detail="Fouling player must be in this session")
        cs = session.current_set
        if not cs:
            raise HTTPException(status_code=400, detail="No current set")
        cs.apply_foul(req.fouling_player, req.ball, session.players, intentional=req.intentional)
        last_event = cs.events[-1] if cs.events else {}

    payload = _serialize_session(live)
    payload["foul_summary"] = {
        "penalty": foul_penalty(req.ball),
        "per_player": last_event.get("per_player"),
        "recipients": last_event.get("recipients", []),
        "intentional": req.intentional,
    }
    return payload


@app.post("/api/sessions/{session_id}/undo")
async def undo_action(session_id: str) -> dict:
    live = _get_live_session(session_id)
    session = live.session
    async with session._lock:
        cs = session.current_set
        if not cs or not cs.undo():
            raise HTTPException(status_code=400, detail="Nothing to undo")
    return _serialize_session(live)


@app.post("/api/sessions/{session_id}/record-scores")
async def record_scores(session_id: str, req: RecordScoresRequest) -> dict:
    live = _get_live_session(session_id)
    if live.mode != "record":
        raise HTTPException(status_code=400, detail="Record scores is only available in record mode")

    session = live.session
    async with session._lock:
        cs = session.current_set
        if not cs:
            raise HTTPException(status_code=400, detail="No current set")
        for player in session.players:
            if player not in req.scores:
                raise HTTPException(status_code=400, detail=f"Missing score for {player}")
            score = req.scores[player]
            if score < 0:
                raise HTTPException(status_code=400, detail=f"Invalid score for {player}")
            cs.set_score(player, score)
        cs.scores_finalized = True
    return _serialize_session(live)


@app.post("/api/sessions/{session_id}/new-set")
async def start_new_set(session_id: str) -> dict:
    live = _get_live_session(session_id)
    session = live.session
    async with session._lock:
        if live.mode == "record":
            cs = session.current_set
            if not cs or not cs.scores_finalized:
                raise HTTPException(status_code=400, detail="Record mode requires finalized set scores")

        set_data = session.save_current_set()
        if set_data:
            await save_set(session.session_id, set_data)
        session.start_set()
    return _serialize_session(live)


@app.post("/api/sessions/{session_id}/end")
async def end_active_session(session_id: str) -> dict:
    live = _get_live_session(session_id)
    return await _end_live_session(live)


@app.get("/api/history")
async def get_history() -> dict:
    sessions = await get_completed_sessions()
    return {"sessions": sessions}


@app.get("/api/debts")
async def list_debts() -> dict:
    debts = await get_debts()
    return {
        "debts": debts,
        "transferable_chains": _find_transferable_chains(debts),
    }


@app.post("/api/debts/{debt_id}/pay")
async def pay_debt(debt_id: int) -> dict:
    await mark_debt_paid(debt_id)
    debts = await get_debts()
    return {
        "debts": debts,
        "transferable_chains": _find_transferable_chains(debts),
    }


@app.post("/api/debts/pay-by-date")
async def pay_debt_by_date(req: PayByDateRequest) -> dict:
    updated = await mark_debt_paid_by_date(req.session_date)
    if not updated:
        raise HTTPException(status_code=404, detail="No outstanding debt found for the session date")
    debts = await get_debts()
    return {
        "debts": debts,
        "transferable_chains": _find_transferable_chains(debts),
    }


@app.post("/api/debts/transfer")
async def transfer_debt_chain(req: TransferDebtRequest) -> dict:
    try:
        await transfer_debt(req.debt1_id, req.debt2_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    debts = await get_debts()
    return {
        "debts": debts,
        "transferable_chains": _find_transferable_chains(debts),
    }


@app.post("/api/mirror-sync")
async def mirror_sync() -> dict:
    if not config.GITEA_TOKEN:
        raise HTTPException(status_code=400, detail="GITEA_TOKEN is not configured")

    url = f"{config.GITEA_URL.rstrip('/')}/api/v1/repos/{config.GITEA_MIRROR_REPO}/mirror-sync"
    headers = {
        "Authorization": f"token {config.GITEA_TOKEN}",
        "Content-Type": "application/json",
    }

    try:
        async with aiohttp.ClientSession() as client:
            async with client.post(url, headers=headers) as resp:
                if resp.status == 200:
                    return {"ok": True, "message": f"Mirror sync triggered for {config.GITEA_MIRROR_REPO}"}
                body = await resp.text()
                raise HTTPException(status_code=resp.status, detail=body[:500])
    except HTTPException:
        raise
    except Exception as exc:
        log.exception("Failed to trigger mirror sync")
        raise HTTPException(status_code=500, detail=f"Failed to reach Gitea: {exc}") from exc
