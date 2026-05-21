import { useEffect, useMemo, useState } from 'react'
import './App.css'
import { StartSessionCard } from './components/StartSessionCard'
import { ActiveSessionCard } from './components/ActiveSessionCard'
import { HistoryCard } from './components/HistoryCard'
import { DebtsCard } from './components/DebtsCard'
import { MirrorSyncCard } from './components/MirrorSyncCard'

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

const TABS = [
  { id: 'session', label: '🎱 Current Session' },
  { id: 'history', label: '📋 History' },
  { id: 'debt', label: '🧋 Bubble Tea Debt' },
  { id: 'sync', label: '🔄 Sync' },
]

function App() {
  const [activeTab, setActiveTab] = useState('session')
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
  const [isSubmittingBall, setIsSubmittingBall] = useState(false)

  const currentSession = useMemo(
    () => sessions.find((session) => session.session_id === sessionId) ?? null,
    [sessions, sessionId],
  )

  const currentSet = currentSession?.current_set ?? null

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
          setNotice(formatBreakAlert(data.break_alert))
        } else {
          setNotice('Action completed.')
        }
      }
      setError('')
    } catch (err) {
      setError(String(err))
    }
  }

  function formatBreakAlert(alert) {
    const alertBalls = alert.balls
      .map((ball) => meta.balls.find((item) => item.name === ball)?.emoji ?? ball)
      .join(' ')
    return `Break alert: ${alert.player} made ${alert.total} (${alertBalls})`
  }

  async function submitBallForPlayer(player, ball) {
    if (!currentSession?.current_set) return
    setIsSubmittingBall(true)
    try {
      const currentSetState = currentSession.current_set
      const playerOrder = currentSetState.player_order ?? currentSession.players
      if (!playerOrder.includes(player)) {
        throw new Error(`Player ${player} is not in the active player rotation`)
      }

      const sessionPath = `/sessions/${currentSession.session_id}`
      let payload = { current_set: currentSetState }
      let turns = 0
      let pendingAlert = null
      const maxTurns = playerOrder.length

      while (payload.current_set?.current_player !== player && turns < maxTurns) {
        const activePlayer = payload.current_set?.current_player
        if (activePlayer && !playerOrder.includes(activePlayer)) {
          throw new Error(`Current player ${activePlayer} is not in the active player rotation`)
        }
        payload = await api(`${sessionPath}/end-turn`, { method: 'POST' })
        if (payload.break_alert) {
          pendingAlert = payload.break_alert
        }
        turns += 1
      }

      if (payload.current_set?.current_player !== player) {
        throw new Error(
          `Unable to rotate to ${player} after ${maxTurns} end-turn actions. Please refresh and try again.`,
        )
      }

      payload = await api(`${sessionPath}/ball`, {
        method: 'POST',
        body: JSON.stringify({ ball }),
      })

      setSessions((old) =>
        old.map((session) =>
          session.session_id === currentSession.session_id ? payload : session,
        ),
      )
      setNotice(pendingAlert ? formatBreakAlert(pendingAlert) : `Scored ${ball} for ${player}.`)
      setError('')
    } catch (err) {
      setError(String(err))
    } finally {
      setIsSubmittingBall(false)
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
    <main className="mx-auto max-w-5xl px-4 py-8">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-4xl font-bold text-[#d4a017]">🎱 Snooker Scoreboard</h1>
        <p className="mt-1 text-[#a3b8a3]">FastAPI backend · React frontend</p>
      </div>

      {/* Tab bar */}
      <div className="mb-6 flex gap-2 border-b border-[#1e3a1e]">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={[
              'px-4 py-2 text-sm font-medium rounded-t-lg transition-colors',
              activeTab === tab.id
                ? 'bg-[#122012] text-[#d4a017] border border-b-0 border-[#1e3a1e]'
                : 'text-[#a3b8a3] hover:text-[#d4a017] hover:bg-[#1a2e1a]',
            ].join(' ')}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Notices */}
      {notice && (
        <div className="mb-4 rounded-lg border border-green-700 bg-green-950/60 px-4 py-3 text-green-300">
          {notice}
        </div>
      )}
      {error && (
        <div className="mb-4 whitespace-pre-wrap rounded-lg border border-red-700 bg-red-950/60 px-4 py-3 text-red-300">
          {error}
        </div>
      )}

      <div className="space-y-6">
        {activeTab === 'session' && (
          <>
            <StartSessionCard
              players={meta.players}
              selectedPlayers={selectedPlayers}
              onTogglePlayer={(player) =>
                setSelectedPlayers((old) =>
                  old.includes(player) ? old.filter((n) => n !== player) : [...old, player],
                )
              }
              mode={mode}
              onModeChange={setMode}
              onStart={createSession}
              onRefresh={refreshSessions}
            />

            <ActiveSessionCard
              sessions={sessions}
              sessionId={sessionId}
              onSelectSession={setSessionId}
              currentSession={currentSession}
              currentSet={currentSet}
              balls={meta.balls}
              foulForm={foulForm}
              onFoulFormChange={setFoulForm}
              recordScores={recordScores}
              onRecordScoreChange={(player, value) => setRecordScores((old) => ({ ...old, [player]: value }))}
              onSubmitBall={submitBallForPlayer}
              onEndTurn={() => mutateSession('/end-turn')}
              onUndo={() => mutateSession('/undo')}
              onNewSet={() => mutateSession('/new-set')}
              onEnd={() => mutateSession('/end')}
              onFoul={() => mutateSession('/foul', foulForm)}
              onSaveRecordScores={saveRecordScores}
              isSubmittingBall={isSubmittingBall}
            />
          </>
        )}

        {activeTab === 'history' && (
          <HistoryCard
            history={history}
            historySessionIndex={historySessionIndex}
            historySetIndex={historySetIndex}
            onSelectSession={(idx) => {
              setHistorySessionIndex(idx)
              setHistorySetIndex(0)
            }}
            onSelectSet={setHistorySetIndex}
            onRefresh={refreshHistory}
            balls={meta.balls}
          />
        )}

        {activeTab === 'debt' && (
          <DebtsCard
            debts={debts}
            transferableChains={transferableChains}
            selectedChain={selectedChain}
            payDate={payDate}
            onPayDate={setPayDate}
            onPayDebtByDate={payDebtByDate}
            onSelectChain={setSelectedChain}
            onTransferDebt={transferDebt}
            onPayDebt={payDebt}
            onRefresh={refreshDebts}
          />
        )}

        {activeTab === 'sync' && (
          <MirrorSyncCard onSync={triggerMirrorSync} />
        )}
      </div>
    </main>
  )
}

export default App
