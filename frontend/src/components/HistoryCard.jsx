function formatDuration(seconds) {
  if (typeof seconds !== 'number') return '—'
  const minutes = Math.floor(seconds / 60)
  const secs = seconds % 60
  return `${minutes}m ${secs.toString().padStart(2, '0')}s`
}

export function HistoryCard({
  history,
  historySessionIndex,
  historySetIndex,
  onSelectSession,
  onSelectSet,
  onRefresh,
  balls,
}) {
  const currentHistorySession = history[historySessionIndex]
  const currentHistorySet = currentHistorySession?.sets?.[historySetIndex]

  return (
    <section className="rounded-2xl border border-[#1e3a1e] bg-[#122012] p-6 shadow-lg">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-xl font-bold text-[#d4a017]">History</h2>
        <button
          type="button"
          onClick={onRefresh}
          className="rounded-lg border border-[#1e3a1e] bg-[#0d1a0d] px-4 py-2 text-sm text-[#a3b8a3] transition-colors hover:border-[#d4a017]/50 hover:text-[#f0ede4]"
        >
          ↻ Refresh
        </button>
      </div>

      <div className="mb-4 flex flex-wrap gap-3">
        <select
          value={historySessionIndex}
          onChange={(e) => onSelectSession(Number(e.target.value))}
          className="flex-1 rounded-lg border border-[#1e3a1e] bg-[#0d1a0d] px-3 py-2 text-[#f0ede4] focus:border-[#d4a017] focus:outline-none"
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
            onChange={(e) => onSelectSet(Number(e.target.value))}
            className="rounded-lg border border-[#1e3a1e] bg-[#0d1a0d] px-3 py-2 text-[#f0ede4] focus:border-[#d4a017] focus:outline-none"
          >
            {currentHistorySession.sets.map((setItem, index) => (
              <option key={setItem.id ?? `${setItem.session_id}-${setItem.set_number}`} value={index}>
                Set {setItem.set_number}
              </option>
            ))}
          </select>
        )}
      </div>

      {!currentHistorySession && (
        <p className="italic text-[#a3b8a3]">No completed sessions yet.</p>
      )}

      {currentHistorySession && (
        <>
          <div className="mb-5">
            <h3 className="mb-2 text-sm font-semibold uppercase tracking-wider text-[#a3b8a3]">
              Final Standings — {currentHistorySession.date}
            </h3>
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr className="border-b border-[#1e3a1e]">
                  <th className="px-3 py-2 text-left text-[#a3b8a3]">Player</th>
                  <th className="px-3 py-2 text-right text-[#a3b8a3]">Ranking Pts</th>
                  <th className="px-3 py-2 text-right text-[#a3b8a3]">Raw Score</th>
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
                  .map((player, idx) => (
                    <tr key={player} className="border-b border-[#1e3a1e]/50 last:border-0 hover:bg-[#1a3a1a]/30">
                      <td className="px-3 py-2 font-medium text-[#f0ede4]">
                        {idx === 0 && <span className="mr-1">🏆</span>}{player}
                      </td>
                      <td className="px-3 py-2 text-right font-bold text-[#d4a017]">
                        {currentHistorySession.ranking_totals[player] ?? 0}
                      </td>
                      <td className="px-3 py-2 text-right text-[#f0ede4]">
                        {currentHistorySession.score_totals[player] ?? 0}
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>

          {currentHistorySet && (
            <div className="rounded-lg border border-[#1e3a1e] bg-[#0d1a0d] p-4">
              <h3 className="mb-3 font-semibold text-[#d4a017]">
                Set {currentHistorySet.set_number}
                <span className="ml-2 text-sm font-normal text-[#a3b8a3]">
                  ({formatDuration(currentHistorySet.duration_secs)})
                </span>
              </h3>
              <ul className="mb-4 space-y-1 text-sm">
                {(currentHistorySet.player_order ?? currentHistorySession.players).map((player) => (
                  <li key={player} className="flex gap-2">
                    <span className="font-medium text-[#f0ede4]">{player}:</span>
                    <span className="text-[#a3b8a3]">
                      {currentHistorySet.scores[player] ?? 0} pts,{' '}
                      <span className="text-[#d4a017]">+{currentHistorySet.ranking_points?.[player] ?? 0} rp</span>
                    </span>
                  </li>
                ))}
              </ul>

              <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-[#a3b8a3]">Break History</h4>
              <ul className="mb-4 space-y-1 text-sm">
                {Object.entries(currentHistorySet.breaks ?? {}).map(([player, breaks]) => (
                  <li key={player} className="flex gap-2">
                    <span className="font-medium text-[#f0ede4]">{player}:</span>
                    <span className="text-[#a3b8a3]">
                      {breaks
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
                ))}
              </ul>

              <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-[#a3b8a3]">Event Log</h4>
              <ol className="max-h-48 space-y-0.5 overflow-y-auto rounded border border-[#1e3a1e] bg-[#122012] p-2 text-xs text-[#a3b8a3]">
                {(currentHistorySet.events ?? []).map((event) => (
                  <li key={event.seq} className="border-b border-[#1e3a1e]/30 py-0.5 last:border-0">
                    <span className="mr-2 text-[#d4a017]/50">#{event.seq}</span>
                    {event.type === 'ball' && `${event.player} potted ${event.ball} (+${event.value})`}
                    {event.type === 'end_turn' && `${event.player} ended turn`}
                    {event.type === 'foul' &&
                      `${event.fouler} foul on ${event.ball} — penalty ${event.penalty}, +${event.per_player} to ${event.recipients.join(', ')}${event.intentional ? ' (intentional)' : ''}`}
                  </li>
                ))}
                {(currentHistorySet.events ?? []).length === 0 && (
                  <li className="italic text-[#1e3a1e]">No events.</li>
                )}
              </ol>
            </div>
          )}
        </>
      )}
    </section>
  )
}
