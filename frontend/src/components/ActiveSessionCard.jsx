import { useEffect, useState } from 'react'

const BALL_COLORS = {
  red: 'bg-red-600 text-white hover:bg-red-500 border-red-700',
  yellow: 'bg-yellow-400 text-black hover:bg-yellow-300 border-yellow-500',
  green: 'bg-green-600 text-white hover:bg-green-500 border-green-700',
  brown: 'bg-amber-800 text-white hover:bg-amber-700 border-amber-900',
  blue: 'bg-blue-600 text-white hover:bg-blue-500 border-blue-700',
  pink: 'bg-pink-400 text-black hover:bg-pink-300 border-pink-500',
  black: 'bg-gray-900 text-white hover:bg-gray-800 border-gray-700 ring-1 ring-[#1e3a1e]',
  white: 'bg-white text-black hover:bg-gray-100 border-gray-300',
}

function BallButton({ ball, onBall, isSelected }) {
  const colorClass = BALL_COLORS[ball.name] ?? 'bg-[#1a3a1a] text-[#f0ede4] hover:bg-[#1e4a1e] border-[#1e3a1e]'
  return (
    <button
      type="button"
      onClick={() => onBall(ball.name)}
      className={`flex items-center justify-center gap-1.5 rounded-lg border px-3 py-2.5 font-semibold transition-colors ${colorClass} ${isSelected ? 'ring-2 ring-[#d4a017] ring-offset-2 ring-offset-[#122012]' : ''}`}
    >
      <span>{ball.emoji}</span>
      <span className="capitalize">{ball.name}</span>
      <span className="text-xs opacity-75">+{ball.value}</span>
    </button>
  )
}

function ScoreTable({ players, scores }) {
  return (
    <table className="w-full border-collapse text-sm">
      <thead>
        <tr className="border-b border-[#1e3a1e]">
          <th className="px-3 py-2 text-left text-[#a3b8a3]">Player</th>
          <th className="px-3 py-2 text-right text-[#a3b8a3]">Score</th>
        </tr>
      </thead>
      <tbody>
        {players.map((player) => (
          <tr key={player} className="border-b border-[#1e3a1e]/50 last:border-0 hover:bg-[#1a3a1a]/30">
            <td className="px-3 py-2 font-medium text-[#f0ede4]">{player}</td>
            <td className="px-3 py-2 text-right font-bold text-[#d4a017]">{scores[player] ?? 0}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function EventLog({ events }) {
  function describeEvent(event) {
    if (event.type === 'ball') return `${event.player} potted ${event.ball} (+${event.value})`
    if (event.type === 'end_turn') return `${event.player} ended turn`
    if (event.type === 'foul')
      return `${event.fouler} foul on ${event.ball} — penalty ${event.penalty}, +${event.per_player} to ${event.recipients.join(', ')}${event.intentional ? ' (intentional)' : ''}`
    return JSON.stringify(event)
  }

  return (
    <ol className="max-h-56 space-y-0.5 overflow-y-auto rounded-lg border border-[#1e3a1e] bg-[#0d1a0d] p-3 text-xs text-[#a3b8a3]">
      {events.map((event) => (
        <li key={event.seq} className="border-b border-[#1e3a1e]/30 py-0.5 last:border-0">
          <span className="mr-2 text-[#d4a017]/50">#{event.seq}</span>
          {describeEvent(event)}
        </li>
      ))}
      {events.length === 0 && <li className="italic text-[#1e3a1e]">No events yet.</li>}
    </ol>
  )
}

function ConfirmBar({ label, onConfirm, onCancel }) {
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-lg border border-yellow-700 bg-yellow-950/40 px-3 py-2 text-sm text-yellow-300">
      <span>Confirm {label}?</span>
      <button
        type="button"
        onClick={onConfirm}
        className="rounded-lg border border-yellow-600 bg-yellow-900/60 px-3 py-1 font-semibold text-yellow-200 transition-colors hover:bg-yellow-800/60"
      >
        Yes, confirm
      </button>
      <button
        type="button"
        onClick={onCancel}
        className="rounded-lg border border-[#1e3a1e] bg-[#0d1a0d] px-3 py-1 text-[#a3b8a3] transition-colors hover:text-[#f0ede4]"
      >
        Cancel
      </button>
    </div>
  )
}

export function ActiveSessionCard({
  sessions,
  sessionId,
  onSelectSession,
  currentSession,
  currentSet,
  balls,
  foulForm,
  onFoulFormChange,
  recordScores,
  onRecordScoreChange,
  onSubmitBall,
  onEndTurn,
  onUndo,
  onNewSet,
  onEnd,
  onFoul,
  onSaveRecordScores,
  isSubmittingBall,
}) {
  const [confirmPending, setConfirmPending] = useState(null)
  const [selectedPlayer, setSelectedPlayer] = useState('')
  const [selectedBall, setSelectedBall] = useState('')

  useEffect(() => {
    if (!currentSet) {
      setSelectedPlayer('')
      setSelectedBall('')
      return
    }

    setSelectedPlayer(currentSet.current_player)
    setSelectedBall('')
  }, [currentSet?.set_number, currentSet?.current_player, currentSession?.session_id])

  function requestConfirm(action) {
    setConfirmPending(action)
  }

  function handleConfirm() {
    const action = confirmPending
    setConfirmPending(null)
    if (action === 'new-set') onNewSet()
    else if (action === 'end') onEnd()
  }

  function handleCancel() {
    setConfirmPending(null)
  }

  const submitTarget = `${selectedBall || 'selected ball'} for ${selectedPlayer || 'player'}`
  const submitButtonText = isSubmittingBall ? 'Submitting…' : `✅ Submit ${submitTarget}`

  return (
    <section className="rounded-2xl border border-[#1e3a1e] bg-[#122012] p-6 shadow-lg">
      <h2 className="mb-4 text-xl font-bold text-[#d4a017]">Active Session</h2>

      <select
        value={sessionId}
        onChange={(e) => onSelectSession(e.target.value)}
        className="mb-4 w-full rounded-lg border border-[#1e3a1e] bg-[#0d1a0d] px-3 py-2 text-[#f0ede4] focus:border-[#d4a017] focus:outline-none"
      >
        <option value="">Select session…</option>
        {sessions.map((session) => (
          <option key={session.session_id} value={session.session_id}>
            {session.date} — {session.mode} — {session.players.join(', ')}
          </option>
        ))}
      </select>

      {!currentSession && (
        <p className="italic text-[#a3b8a3]">No session selected.</p>
      )}

      {currentSession && (
        <>
          {/* Standings */}
          <div className="mb-5">
            <h3 className="mb-2 text-sm font-semibold uppercase tracking-wider text-[#a3b8a3]">Standings</h3>
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr className="border-b border-[#1e3a1e]">
                  <th className="px-3 py-2 text-left text-[#a3b8a3]">Player</th>
                  <th className="px-3 py-2 text-right text-[#a3b8a3]">Ranking Pts</th>
                  <th className="px-3 py-2 text-right text-[#a3b8a3]">Raw Score</th>
                </tr>
              </thead>
              <tbody>
                {currentSession.standings.map((line, idx) => (
                  <tr key={line.player} className="border-b border-[#1e3a1e]/50 last:border-0 hover:bg-[#1a3a1a]/30">
                    <td className="px-3 py-2 font-medium text-[#f0ede4]">
                      {idx === 0 && <span className="mr-1">🏆</span>}{line.player}
                    </td>
                    <td className="px-3 py-2 text-right font-bold text-[#d4a017]">{line.ranking_points}</td>
                    <td className="px-3 py-2 text-right text-[#f0ede4]">{line.raw_total}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {currentSet && (
            <>
              {/* Set header */}
              <div className="mb-4 flex flex-wrap items-center gap-4 rounded-lg border border-[#1e3a1e] bg-[#0d1a0d] p-3">
                <div>
                  <span className="text-xs text-[#a3b8a3]">Set</span>
                  <span className="ml-1 text-lg font-bold text-[#d4a017]">#{currentSet.set_number}</span>
                </div>
                <div>
                  <span className="text-xs text-[#a3b8a3]">Up now: </span>
                  <span className="font-semibold text-[#f0ede4]">{currentSet.current_player}</span>
                </div>
                <div>
                  <span className="text-xs text-[#a3b8a3]">Break: </span>
                  <span className="font-semibold text-[#d4a017]">
                    {currentSet.current_break.length
                      ? `${currentSet.current_break
                          .map((b) => balls.find((x) => x.name === b)?.emoji ?? b)
                          .join(' ')} (${currentSet.current_break_total})`
                      : '—'}
                  </span>
                </div>
              </div>

              {/* Per-set scores */}
              <div className="mb-4">
                <h3 className="mb-2 text-sm font-semibold uppercase tracking-wider text-[#a3b8a3]">Set Scores</h3>
                <ScoreTable
                  players={currentSet.player_order ?? currentSession.players}
                  scores={currentSet.scores}
                />
              </div>

              {currentSession.mode === 'full' ? (
                <>
                  {/* Guided score input */}
                  <div className="mb-4">
                    <h3 className="mb-2 text-sm font-semibold uppercase tracking-wider text-[#a3b8a3]">Score Entry</h3>
                    <p className="mb-2 text-xs text-[#a3b8a3]">1) Choose player 2) Choose ball 3) Submit score</p>
                    <div className="mb-3 flex flex-wrap gap-2">
                      {(currentSet.player_order ?? currentSession.players).map((player) => (
                        <button
                          key={player}
                          type="button"
                          onClick={() => setSelectedPlayer(player)}
                          className={`rounded-lg border px-3 py-1.5 text-sm font-semibold transition-colors ${
                            selectedPlayer === player
                              ? 'border-[#d4a017] bg-[#d4a017]/10 text-[#d4a017]'
                              : 'border-[#1e3a1e] bg-[#0d1a0d] text-[#f0ede4] hover:border-[#d4a017]/50'
                          }`}
                        >
                          {player}
                        </button>
                      ))}
                    </div>
                    <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-4">
                      {balls.map((ball) => (
                        <BallButton
                          key={ball.name}
                          ball={ball}
                          onBall={setSelectedBall}
                          isSelected={selectedBall === ball.name}
                        />
                      ))}
                    </div>
                    <button
                      type="button"
                      disabled={!selectedPlayer || !selectedBall || isSubmittingBall}
                      onClick={() => onSubmitBall(selectedPlayer, selectedBall)}
                      className="mt-3 w-full rounded-lg border border-[#2a5a2a] bg-[#122012] px-4 py-3 text-base font-semibold text-[#f0ede4] transition-colors hover:border-[#d4a017]/60 hover:text-[#d4a017] disabled:cursor-not-allowed disabled:opacity-40"
                    >
                      {submitButtonText}
                    </button>
                  </div>

                  {/* Action buttons */}
                  <div className="mb-4 space-y-2">
                    {/* Primary row: most-used actions */}
                    <div className="flex gap-2">
                      <button
                        type="button"
                        onClick={onEndTurn}
                        className="flex-1 rounded-lg border border-[#2a5a2a] bg-[#122012] px-4 py-3 text-base font-semibold text-[#f0ede4] transition-colors hover:border-[#d4a017]/60 hover:text-[#d4a017]"
                      >
                        ⏭ End Turn
                      </button>
                      <button
                        type="button"
                        onClick={onUndo}
                        disabled={!currentSet.can_undo}
                        className="flex-1 rounded-lg border border-[#2a5a2a] bg-[#122012] px-4 py-3 text-base font-semibold text-[#f0ede4] transition-colors hover:border-[#d4a017]/60 hover:text-[#d4a017] disabled:cursor-not-allowed disabled:opacity-40"
                      >
                        ↩ Undo
                      </button>
                    </div>
                    {/* Secondary row: set/session management */}
                    <div className="flex gap-2">
                      <button
                        type="button"
                        onClick={() => requestConfirm('new-set')}
                        className="flex-1 rounded-lg border border-[#1e3a1e] bg-[#0d1a0d] px-4 py-2 text-sm text-[#f0ede4] transition-colors hover:border-[#d4a017]/50 hover:text-[#d4a017]"
                      >
                        ➕ New Set
                      </button>
                      <button
                        type="button"
                        onClick={() => requestConfirm('end')}
                        className="flex-1 rounded-lg border border-red-900 bg-red-950/30 px-4 py-2 text-sm font-semibold text-red-400 transition-colors hover:bg-red-900/50 hover:text-red-300"
                      >
                        🏁 End Session
                      </button>
                    </div>
                  </div>
                  {confirmPending && (
                    <div className="mb-4">
                      <ConfirmBar
                        label={confirmPending === 'new-set' ? 'new set' : 'end session'}
                        onConfirm={handleConfirm}
                        onCancel={handleCancel}
                      />
                    </div>
                  )}

                  {/* Foul form */}
                  <div className="rounded-lg border border-[#1e3a1e] bg-[#0d1a0d] p-3">
                    <h3 className="mb-2 text-sm font-semibold uppercase tracking-wider text-[#a3b8a3]">Apply Foul</h3>
                    <div className="flex flex-wrap items-center gap-2">
                      <select
                        value={foulForm.fouling_player}
                        onChange={(e) => onFoulFormChange({ ...foulForm, fouling_player: e.target.value })}
                        className="rounded-lg border border-[#1e3a1e] bg-[#122012] px-3 py-2 text-[#f0ede4] focus:border-[#d4a017] focus:outline-none"
                      >
                        {currentSession.players.map((player) => (
                          <option key={player} value={player}>{player}</option>
                        ))}
                      </select>
                      <select
                        value={foulForm.ball}
                        onChange={(e) => onFoulFormChange({ ...foulForm, ball: e.target.value })}
                        className="rounded-lg border border-[#1e3a1e] bg-[#122012] px-3 py-2 text-[#f0ede4] focus:border-[#d4a017] focus:outline-none"
                      >
                        {balls.map((ball) => (
                          <option key={ball.name} value={ball.name}>{ball.emoji} {ball.name}</option>
                        ))}
                      </select>
                      <label className="flex cursor-pointer items-center gap-2 text-sm text-[#a3b8a3]">
                        <input
                          type="checkbox"
                          className="accent-[#d4a017]"
                          checked={foulForm.intentional}
                          onChange={(e) => onFoulFormChange({ ...foulForm, intentional: e.target.checked })}
                        />
                        Intentional
                      </label>
                      <button
                        type="button"
                        onClick={onFoul}
                        className="rounded-lg border border-red-800 bg-red-950/50 px-4 py-2 text-sm font-semibold text-red-400 transition-colors hover:bg-red-900/50 hover:text-red-300"
                      >
                        Apply Foul
                      </button>
                    </div>
                  </div>
                </>
              ) : (
                <>
                  {/* Record mode */}
                  <div className="mb-4">
                    <h3 className="mb-2 text-sm font-semibold uppercase tracking-wider text-[#a3b8a3]">Record Scores</h3>
                    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                      {currentSession.players.map((player) => (
                        <label key={player} className="flex flex-col gap-1">
                          <span className="text-sm font-medium text-[#a3b8a3]">{player}</span>
                          <input
                            type="number"
                            min="0"
                            value={recordScores[player] ?? 0}
                            onChange={(e) => onRecordScoreChange(player, e.target.value)}
                            className="rounded-lg border border-[#1e3a1e] bg-[#0d1a0d] px-3 py-2 text-[#f0ede4] focus:border-[#d4a017] focus:outline-none"
                          />
                        </label>
                      ))}
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      onClick={onSaveRecordScores}
                      className="rounded-lg bg-[#d4a017] px-5 py-2 font-semibold text-[#0d1a0d] transition-colors hover:bg-[#e8bb3a]"
                    >
                      💾 Save Scores
                    </button>
                    <button
                      type="button"
                      onClick={() => requestConfirm('new-set')}
                      className="rounded-lg border border-[#1e3a1e] bg-[#0d1a0d] px-4 py-2 text-[#f0ede4] transition-colors hover:border-[#d4a017]/50 hover:text-[#d4a017]"
                    >
                      ➕ New Set
                    </button>
                    <button
                      type="button"
                      onClick={() => requestConfirm('end')}
                      className="rounded-lg border border-red-800 bg-red-950/50 px-4 py-2 font-semibold text-red-400 transition-colors hover:bg-red-900/50 hover:text-red-300"
                    >
                      🏁 End Session
                    </button>
                  </div>
                  {confirmPending && (
                    <div className="mt-3">
                      <ConfirmBar
                        label={confirmPending === 'new-set' ? 'new set' : 'end session'}
                        onConfirm={handleConfirm}
                        onCancel={handleCancel}
                      />
                    </div>
                  )}
                </>
              )}

              {/* Break History */}
              <div className="mt-5">
                <h3 className="mb-2 text-sm font-semibold uppercase tracking-wider text-[#a3b8a3]">Break History</h3>
                <ul className="space-y-1 text-sm">
                  {currentSession.players.map((player) => {
                    const playerBreaks = currentSet.breaks?.[player] ?? []
                    return (
                      <li key={player} className="flex gap-2">
                        <span className="font-medium text-[#f0ede4]">{player}:</span>
                        <span className="text-[#a3b8a3]">
                          {playerBreaks.length === 0
                            ? '—'
                            : playerBreaks
                                .map((breakBalls) => {
                                  const emojis = breakBalls
                                    .map((b) => balls.find((x) => x.name === b)?.emoji ?? b)
                                    .join('')
                                  const total = breakBalls.reduce(
                                    (sum, b) => sum + (balls.find((x) => x.name === b)?.value ?? 0),
                                    0,
                                  )
                                  return `${emojis} (${total})`
                                })
                                .join(' | ')}
                        </span>
                      </li>
                    )
                  })}
                </ul>
              </div>

              {/* Event Log */}
              <div className="mt-5">
                <h3 className="mb-2 text-sm font-semibold uppercase tracking-wider text-[#a3b8a3]">Event Log</h3>
                <EventLog events={currentSet.events ?? []} />
              </div>
            </>
          )}
        </>
      )}
    </section>
  )
}
