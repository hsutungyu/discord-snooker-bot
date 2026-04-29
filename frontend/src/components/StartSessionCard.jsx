export function StartSessionCard({ players, selectedPlayers, onTogglePlayer, mode, onModeChange, onStart, onRefresh }) {
  return (
    <section className="rounded-2xl border border-[#1e3a1e] bg-[#122012] p-6 shadow-lg">
      <h2 className="mb-4 text-xl font-bold text-[#d4a017]">Start Session</h2>

      <div className="mb-4 grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-4">
        {players.map((player) => (
          <label
            key={player}
            className={`flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 transition-colors ${
              selectedPlayers.includes(player)
                ? 'border-[#d4a017] bg-[#1a3a1a] text-[#d4a017]'
                : 'border-[#1e3a1e] bg-[#0d1a0d] text-[#a3b8a3] hover:border-[#d4a017]/50'
            }`}
          >
            <input
              type="checkbox"
              className="accent-[#d4a017]"
              checked={selectedPlayers.includes(player)}
              onChange={() => onTogglePlayer(player)}
            />
            <span className="font-medium">{player}</span>
          </label>
        ))}
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <select
          value={mode}
          onChange={(e) => onModeChange(e.target.value)}
          className="rounded-lg border border-[#1e3a1e] bg-[#0d1a0d] px-3 py-2 text-[#f0ede4] focus:border-[#d4a017] focus:outline-none"
        >
          <option value="full">Full Mode</option>
          <option value="record">Record Mode</option>
        </select>
        <button
          type="button"
          onClick={onStart}
          className="rounded-lg bg-[#d4a017] px-5 py-2 font-semibold text-[#0d1a0d] transition-colors hover:bg-[#e8bb3a] active:bg-[#b8891a]"
        >
          🎱 Start Session
        </button>
        <button
          type="button"
          onClick={onRefresh}
          className="rounded-lg border border-[#1e3a1e] bg-[#0d1a0d] px-4 py-2 text-[#a3b8a3] transition-colors hover:border-[#d4a017]/50 hover:text-[#f0ede4]"
        >
          ↻ Refresh
        </button>
      </div>
    </section>
  )
}
