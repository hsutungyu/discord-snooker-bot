import { useEffect, useMemo, useState } from 'react'
import './App.css'

const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000/api'

async function api(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) },
    ...options,
  })

  if (!response.ok) {
    const text = await response.text()
    throw new Error(text || `Request failed: ${response.status}`)
  }

  const text = await response.text()
  return text ? JSON.parse(text) : null
}

function formatDuration(seconds) {
  if (typeof seconds !== 'number') return '—'
  const minutes = Math.floor(seconds / 60)
  const secs = seconds % 60
  return `${minutes}m ${secs.toString().padStart(2, '0')}s`
}

function App() {
  const [meta, setMeta] = useState({ players: [], balls: [], break_alert_threshold: 10 })
  const [sessions, setSessions] = useState([])
  const [sessionId, setSessionId] = useState('')
  const [mode, setMode] = useState('full')
  const [selectedPlayers, setSelectedPlayers] = useState([])
  const [foulForm, setFoulForm] = useState({ fouling_player: '', ball: 'red', intentional: false })
  const [recordScores, setRecordScores] = useState({})
  const [history, setHistory] = useState([])
  const [historySessionIndex, setHistorySessionIndex] = useState(0)
  const [historySetIndex, setHistorySetIndex] = useState(0)
  const [debts, setDebts] = useState([])
  const [transferableChains, setTransferableChains] = useState([])
  const [selectedChain, setSelectedChain] = useState('')
  const [payDate, setPayDate] = useState('')
  const [notice, setNotice] = useState('')
  const [error, setError] = useState('')

  const currentSession = useMemo(
    () => sessions.find((session) => session.session_id === sessionId) ?? null,
    [sessions, sessionId],
  )

  const currentSet = currentSession?.current_set ?? null

  const currentHistorySession = history[historySessionIndex]
  const currentHistorySet = currentHistorySession?.sets?.[historySetIndex]

  useEffect(() => {
    void refreshAll()
  }, [])

  useEffect(() => {
    if (meta.players.length > 0 && selectedPlayers.length === 0) {
      setSelectedPlayers(meta.players)
      setFoulForm((old) => ({ ...old, fouling_player: meta.players[0] ?? '' }))
    }
  }, [meta.players, selectedPlayers.length])

  useEffect(() => {
    if (!currentSet || currentSession?.mode !== 'record') {
      return
    }
    setRecordScores(currentSet.scores ?? {})
  }, [currentSession?.mode, currentSet])

  useEffect(() => {
    if (!currentSession) {
      return
    }
    setFoulForm((old) => ({
      ...old,
      fouling_player: old.fouling_player || currentSession.players[0] || '',
    }))
  }, [currentSession])

  async function refreshAll() {
    await Promise.all([refreshMeta(), refreshSessions(), refreshHistory(), refreshDebts()])
  }

  async function refreshMeta() {
    try {
      const data = await api('/meta')
      setMeta(data)
      setError('')
    } catch (err) {
      setError(String(err))
    }
  }

  async function refreshSessions() {
    try {
      const data = await api('/sessions/active')
      const active = data.sessions ?? []
      setSessions(active)

      if (!active.some((session) => session.session_id === sessionId)) {
        setSessionId(active[0]?.session_id ?? '')
      }
      setError('')
    } catch (err) {
      setError(String(err))
    }
  }

  async function refreshHistory() {
    try {
      const data = await api('/history')
      const newHistory = data.sessions ?? []
      setHistory(newHistory)
      if (historySessionIndex >= newHistory.length) {
        setHistorySessionIndex(0)
        setHistorySetIndex(0)
      }
      setError('')
    } catch (err) {
      setError(String(err))
    }
  }

  async function refreshDebts() {
    try {
      const data = await api('/debts')
      setDebts(data.debts ?? [])
      setTransferableChains(data.transferable_chains ?? [])
      setSelectedChain('')
      setError('')
    } catch (err) {
      setError(String(err))
    }
  }

  async function createSession() {
    try {
      if (selectedPlayers.length < 2) {
        throw new Error('Select at least 2 players')
      }
      const data = await api('/sessions', {
        method: 'POST',
        body: JSON.stringify({ players: selectedPlayers, mode }),
      })
      setSessions((old) => [...old, data])
      setSessionId(data.session_id)
      setNotice(`Session ${data.session_id} started in ${mode} mode.`)
      setError('')
    } catch (err) {
      setError(String(err))
    }
  }

  async function mutateSession(path, body) {
    if (!currentSession) return
    try {
      const data = await api(`/sessions/${currentSession.session_id}${path}`, {
        method: 'POST',
        ...(body ? { body: JSON.stringify(body) } : {}),
      })

      if (path === '/end') {
        setNotice(data.discarded ? data.message : `Session ended. ${data.debt || ''}`)
        await refreshSessions()
        await Promise.all([refreshHistory(), refreshDebts()])
      } else {
        setSessions((old) =>
          old.map((session) =>
            session.session_id === currentSession.session_id ? data : session,
          ),
        )

        if (data.break_alert) {
          const alertBalls = data.break_alert.balls
            .map((ball) => meta.balls.find((item) => item.name === ball)?.emoji ?? ball)
            .join(' ')
          setNotice(
            `Break alert: ${data.break_alert.player} made ${data.break_alert.total} (${alertBalls})`,
          )
        } else {
          setNotice('Action completed.')
        }
      }
      setError('')
    } catch (err) {
      setError(String(err))
    }
  }

  async function saveRecordScores() {
    if (!currentSession) return
    const normalized = Object.fromEntries(
      currentSession.players.map((player) => [player, Number(recordScores[player] ?? 0)]),
    )
    await mutateSession('/record-scores', { scores: normalized })
  }

  async function payDebt(id) {
    try {
      const data = await api(`/debts/${id}/pay`, { method: 'POST' })
      setDebts(data.debts ?? [])
      setTransferableChains(data.transferable_chains ?? [])
      setNotice(`Debt #${id} marked as paid.`)
      setError('')
    } catch (err) {
      setError(String(err))
    }
  }

  async function payDebtByDate() {
    try {
      const data = await api('/debts/pay-by-date', {
        method: 'POST',
        body: JSON.stringify({ session_date: payDate }),
      })
      setDebts(data.debts ?? [])
      setTransferableChains(data.transferable_chains ?? [])
      setNotice(`Debt for ${payDate} marked as paid.`)
      setPayDate('')
      setError('')
    } catch (err) {
      setError(String(err))
    }
  }

  async function transferDebt() {
    if (!selectedChain) return
    const [debt1, debt2] = selectedChain.split(',').map(Number)
    try {
      const data = await api('/debts/transfer', {
        method: 'POST',
        body: JSON.stringify({ debt1_id: debt1, debt2_id: debt2 }),
      })
      setDebts(data.debts ?? [])
      setTransferableChains(data.transferable_chains ?? [])
      setSelectedChain('')
      setNotice(`Transferred debt chain #${debt1} + #${debt2}.`)
      setError('')
    } catch (err) {
      setError(String(err))
    }
  }

  async function triggerMirrorSync() {
    try {
      const data = await api('/mirror-sync', { method: 'POST' })
      setNotice(data.message)
      setError('')
    } catch (err) {
      setError(String(err))
    }
  }

  return (
    <main className="container">
      <h1>🎱 Snooker Scoreboard Web</h1>
      <p className="subtitle">
        Full rewrite of the Discord bot: FastAPI backend + React frontend.
      </p>

      {notice && <p className="notice success">{notice}</p>}
      {error && <p className="notice error">{error}</p>}

      <section className="card">
        <h2>Start Session</h2>
        <div className="player-grid">
          {meta.players.map((player) => (
            <label key={player} className="toggle">
              <input
                type="checkbox"
                checked={selectedPlayers.includes(player)}
                onChange={() => {
                  setSelectedPlayers((old) =>
                    old.includes(player)
                      ? old.filter((name) => name !== player)
                      : [...old, player],
                  )
                }}
              />
              {player}
            </label>
          ))}
        </div>
        <div className="actions">
          <select value={mode} onChange={(event) => setMode(event.target.value)}>
            <option value="full">Full Mode</option>
            <option value="record">Record Mode</option>
          </select>
          <button type="button" onClick={createSession}>
            Start Session
          </button>
          <button type="button" onClick={refreshSessions}>
            Refresh
          </button>
        </div>
      </section>

      <section className="card">
        <h2>Active Session</h2>
        <div className="actions">
          <select value={sessionId} onChange={(event) => setSessionId(event.target.value)}>
            <option value="">Select session</option>
            {sessions.map((session) => (
              <option key={session.session_id} value={session.session_id}>
                {session.date} — {session.mode} — {session.players.join(', ')}
              </option>
            ))}
          </select>
        </div>

        {currentSession && (
          <>
            <h3>Standings</h3>
            <table>
              <thead>
                <tr>
                  <th>Player</th>
                  <th>Ranking Points</th>
                  <th>Raw Score</th>
                </tr>
              </thead>
              <tbody>
                {currentSession.standings.map((line) => (
                  <tr key={line.player}>
                    <td>{line.player}</td>
                    <td>{line.ranking_points}</td>
                    <td>{line.raw_total}</td>
                  </tr>
                ))}
              </tbody>
            </table>

            {currentSet && (
              <>
                <h3>Set {currentSet.set_number}</h3>
                <p>
                  Current Player: <strong>{currentSet.current_player}</strong>
                </p>
                <p>
                  Current Break:{' '}
                  {currentSet.current_break.length
                    ? `${currentSet.current_break
                        .map((ball) => meta.balls.find((item) => item.name === ball)?.emoji ?? ball)
                        .join(' ')} (${currentSet.current_break_total})`
                    : '—'}
                </p>

                <table>
                  <thead>
                    <tr>
                      <th>Player</th>
                      <th>Score</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(currentSet.player_order ?? currentSession.players).map((player) => (
                      <tr key={player}>
                        <td>{player}</td>
                        <td>{currentSet.scores[player] ?? 0}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>

                {currentSession.mode === 'full' ? (
                  <>
                    <h3>Full Mode Controls</h3>
                    <div className="ball-grid">
                      {meta.balls.map((ball) => (
                        <button
                          key={ball.name}
                          type="button"
                          onClick={() => mutateSession('/ball', { ball: ball.name })}
                        >
                          {ball.emoji} {ball.name} ({ball.value})
                        </button>
                      ))}
                    </div>

                    <div className="actions">
                      <button type="button" onClick={() => mutateSession('/end-turn')}>
                        End Turn
                      </button>
                      <button
                        type="button"
                        disabled={!currentSet.can_undo}
                        onClick={() => mutateSession('/undo')}
                      >
                        Undo
                      </button>
                      <button type="button" onClick={() => mutateSession('/new-set')}>
                        New Set
                      </button>
                      <button type="button" className="danger" onClick={() => mutateSession('/end')}>
                        End Session
                      </button>
                    </div>

                    <div className="actions wrap">
                      <select
                        value={foulForm.fouling_player}
                        onChange={(event) =>
                          setFoulForm((old) => ({ ...old, fouling_player: event.target.value }))
                        }
                      >
                        {currentSession.players.map((player) => (
                          <option key={player} value={player}>
                            {player}
                          </option>
                        ))}
                      </select>
                      <select
                        value={foulForm.ball}
                        onChange={(event) =>
                          setFoulForm((old) => ({ ...old, ball: event.target.value }))
                        }
                      >
                        {meta.balls.map((ball) => (
                          <option key={ball.name} value={ball.name}>
                            {ball.emoji} {ball.name}
                          </option>
                        ))}
                      </select>
                      <label>
                        <input
                          type="checkbox"
                          checked={foulForm.intentional}
                          onChange={(event) =>
                            setFoulForm((old) => ({ ...old, intentional: event.target.checked }))
                          }
                        />
                        Intentional
                      </label>
                      <button type="button" onClick={() => mutateSession('/foul', foulForm)}>
                        Apply Foul
                      </button>
                    </div>
                  </>
                ) : (
                  <>
                    <h3>Record Mode Controls</h3>
                    <div className="record-grid">
                      {currentSession.players.map((player) => (
                        <label key={player}>
                          {player}
                          <input
                            type="number"
                            min="0"
                            value={recordScores[player] ?? 0}
                            onChange={(event) =>
                              setRecordScores((old) => ({ ...old, [player]: event.target.value }))
                            }
                          />
                        </label>
                      ))}
                    </div>
                    <div className="actions">
                      <button type="button" onClick={saveRecordScores}>
                        Save Scores
                      </button>
                      <button type="button" onClick={() => mutateSession('/new-set')}>
                        New Set
                      </button>
                      <button type="button" className="danger" onClick={() => mutateSession('/end')}>
                        End Session
                      </button>
                    </div>
                  </>
                )}

                <h3>Break History</h3>
                <ul>
                  {currentSession.players.map((player) => {
                    const playerBreaks = currentSet.breaks?.[player] ?? []
                    if (playerBreaks.length === 0) {
                      return (
                        <li key={player}>
                          {player}: —
                        </li>
                      )
                    }
                    return (
                      <li key={player}>
                        {player}:{' '}
                        {playerBreaks
                          .map((breakBalls) => {
                            const balls = breakBalls
                              .map((ball) => meta.balls.find((item) => item.name === ball)?.emoji ?? ball)
                              .join('')
                            const total = breakBalls.reduce(
                              (sum, ball) => sum + (meta.balls.find((item) => item.name === ball)?.value ?? 0),
                              0,
                            )
                            return `${balls} (${total})`
                          })
                          .join(' | ')}
                      </li>
                    )
                  })}
                </ul>

                <h3>Event Log</h3>
                <ol className="events">
                  {(currentSet.events ?? []).map((event) => (
                    <li key={event.seq}>
                      {event.type === 'ball' && `${event.player} potted ${event.ball} (+${event.value})`}
                      {event.type === 'end_turn' && `${event.player} ended turn`}
                      {event.type === 'foul' &&
                        `${event.fouler} foul on ${event.ball} (pen ${event.penalty}, +${event.per_player} -> ${event.recipients.join(', ')})${event.intentional ? ' intentional' : ''}`}
                    </li>
                  ))}
                </ol>
              </>
            )}
          </>
        )}
      </section>

      <section className="card">
        <h2>History</h2>
        <div className="actions wrap">
          <button type="button" onClick={refreshHistory}>
            Refresh History
          </button>
          <select
            value={historySessionIndex}
            onChange={(event) => {
              setHistorySessionIndex(Number(event.target.value))
              setHistorySetIndex(0)
            }}
          >
            {history.map((session, index) => (
              <option key={`${session.id}-${session.date}`} value={index}>
                {session.date} ({session.players.join(', ')})
              </option>
            ))}
          </select>
          {currentHistorySession && (
            <select
              value={historySetIndex}
              onChange={(event) => setHistorySetIndex(Number(event.target.value))}
            >
              {currentHistorySession.sets.map((setItem, index) => (
                <option key={setItem.id ?? `${setItem.session_id}-${setItem.set_number}`} value={index}>
                  Set {setItem.set_number}
                </option>
              ))}
            </select>
          )}
        </div>

        {!currentHistorySession && <p>No completed sessions yet.</p>}

        {currentHistorySession && (
          <>
            <h3>Final Standings ({currentHistorySession.date})</h3>
            <table>
              <thead>
                <tr>
                  <th>Player</th>
                  <th>Ranking Points</th>
                  <th>Raw Score</th>
                </tr>
              </thead>
              <tbody>
                {currentHistorySession.players
                  .slice()
                  .sort(
                    (a, b) =>
                      (currentHistorySession.ranking_totals[b] ?? 0) -
                        (currentHistorySession.ranking_totals[a] ?? 0) ||
                      (currentHistorySession.score_totals[b] ?? 0) -
                        (currentHistorySession.score_totals[a] ?? 0),
                  )
                  .map((player) => (
                    <tr key={player}>
                      <td>{player}</td>
                      <td>{currentHistorySession.ranking_totals[player] ?? 0}</td>
                      <td>{currentHistorySession.score_totals[player] ?? 0}</td>
                    </tr>
                  ))}
              </tbody>
            </table>

            {currentHistorySet && (
              <>
                <h3>
                  Set {currentHistorySet.set_number} (Duration: {formatDuration(currentHistorySet.duration_secs)})
                </h3>
                <ul>
                  {(currentHistorySet.player_order ?? currentHistorySession.players).map((player) => (
                    <li key={player}>
                      {player}: {currentHistorySet.scores[player] ?? 0} pts, +
                      {currentHistorySet.ranking_points?.[player] ?? 0} rp
                    </li>
                  ))}
                </ul>
                <h4>Break History</h4>
                <ul>
                  {Object.entries(currentHistorySet.breaks ?? {}).map(([player, breaks]) => (
                    <li key={player}>
                      {player}:{' '}
                      {breaks
                        .map((breakBalls) => {
                          const balls = breakBalls
                            .map((ball) => meta.balls.find((item) => item.name === ball)?.emoji ?? ball)
                            .join('')
                          const total = breakBalls.reduce(
                            (sum, ball) => sum + (meta.balls.find((item) => item.name === ball)?.value ?? 0),
                            0,
                          )
                          return `${balls} (${total})`
                        })
                        .join(' | ')}
                    </li>
                  ))}
                </ul>
                <h4>Event Log</h4>
                <ol className="events">
                  {(currentHistorySet.events ?? []).map((event) => (
                    <li key={event.seq}>
                      {event.type === 'ball' && `${event.player} potted ${event.ball} (+${event.value})`}
                      {event.type === 'end_turn' && `${event.player} ended turn`}
                      {event.type === 'foul' &&
                        `${event.fouler} foul on ${event.ball} (pen ${event.penalty}, +${event.per_player} -> ${event.recipients.join(', ')})${event.intentional ? ' intentional' : ''}`}
                    </li>
                  ))}
                </ol>
              </>
            )}
          </>
        )}
      </section>

      <section className="card">
        <h2>Bubble Tea Debts</h2>
        <div className="actions wrap">
          <button type="button" onClick={refreshDebts}>
            Refresh Debts
          </button>
          <input
            type="text"
            value={payDate}
            placeholder="YYYY-MM-DD"
            onChange={(event) => setPayDate(event.target.value)}
          />
          <button type="button" onClick={payDebtByDate}>
            Mark Date as Paid
          </button>
        </div>

        <h3>Outstanding</h3>
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Date</th>
              <th>Debtor</th>
              <th>Creditor</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {debts
              .filter((debt) => !debt.paid)
              .map((debt) => (
                <tr key={debt.id}>
                  <td>{debt.id}</td>
                  <td>{debt.session_date}</td>
                  <td>{debt.debtor}</td>
                  <td>{debt.creditor}</td>
                  <td>
                    <button type="button" onClick={() => payDebt(debt.id)}>
                      Mark Paid
                    </button>
                  </td>
                </tr>
              ))}
          </tbody>
        </table>

        <h3>Transfer Debt Chain</h3>
        <div className="actions wrap">
          <select value={selectedChain} onChange={(event) => setSelectedChain(event.target.value)}>
            <option value="">Select chain</option>
            {transferableChains.map((chain) => (
              <option key={`${chain.debt1_id}-${chain.debt2_id}`} value={`${chain.debt1_id},${chain.debt2_id}`}>
                #{chain.debt1_id} + #{chain.debt2_id} ({chain.path})
              </option>
            ))}
          </select>
          <button type="button" onClick={transferDebt} disabled={!selectedChain}>
            Transfer
          </button>
        </div>

        <h3>Recently Paid</h3>
        <ul>
          {debts
            .filter((debt) => debt.paid)
            .slice(0, 10)
            .map((debt) => (
              <li key={debt.id}>
                #{debt.id} {debt.session_date} {debt.debtor} → {debt.creditor} ✅
              </li>
            ))}
        </ul>
      </section>

      <section className="card">
        <h2>Mirror Sync</h2>
        <button type="button" onClick={triggerMirrorSync}>
          Trigger GitHub → Gitea Mirror Sync
        </button>
      </section>
    </main>
  )
}

export default App
