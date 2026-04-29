export function DebtsCard({
  debts,
  transferableChains,
  selectedChain,
  payDate,
  onPayDate,
  onPayDebtByDate,
  onSelectChain,
  onTransferDebt,
  onPayDebt,
  onRefresh,
}) {
  const outstanding = debts.filter((d) => !d.paid)
  const recentlyPaid = debts.filter((d) => d.paid).slice(0, 10)

  return (
    <section className="rounded-2xl border border-[#1e3a1e] bg-[#122012] p-6 shadow-lg">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-xl font-bold text-[#d4a017]">🧋 Bubble Tea Debts</h2>
        <button
          type="button"
          onClick={onRefresh}
          className="rounded-lg border border-[#1e3a1e] bg-[#0d1a0d] px-4 py-2 text-sm text-[#a3b8a3] transition-colors hover:border-[#d4a017]/50 hover:text-[#f0ede4]"
        >
          ↻ Refresh
        </button>
      </div>

      {/* Pay by date */}
      <div className="mb-5 flex flex-wrap items-center gap-2 rounded-lg border border-[#1e3a1e] bg-[#0d1a0d] p-3">
        <span className="text-sm text-[#a3b8a3]">Pay all debts for date:</span>
        <input
          type="text"
          value={payDate}
          placeholder="YYYY-MM-DD"
          onChange={(e) => onPayDate(e.target.value)}
          className="rounded-lg border border-[#1e3a1e] bg-[#122012] px-3 py-2 text-sm text-[#f0ede4] placeholder-[#1e3a1e] focus:border-[#d4a017] focus:outline-none"
        />
        <button
          type="button"
          onClick={onPayDebtByDate}
          className="rounded-lg bg-[#d4a017] px-4 py-2 text-sm font-semibold text-[#0d1a0d] transition-colors hover:bg-[#e8bb3a]"
        >
          Mark Date Paid
        </button>
      </div>

      {/* Outstanding debts table */}
      <div className="mb-5">
        <h3 className="mb-2 text-sm font-semibold uppercase tracking-wider text-[#a3b8a3]">Outstanding</h3>
        {outstanding.length === 0 ? (
          <p className="italic text-[#a3b8a3]">No outstanding debts. 🎉</p>
        ) : (
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="border-b border-[#1e3a1e]">
                <th className="px-3 py-2 text-left text-[#a3b8a3]">#</th>
                <th className="px-3 py-2 text-left text-[#a3b8a3]">Date</th>
                <th className="px-3 py-2 text-left text-[#a3b8a3]">Debtor</th>
                <th className="px-3 py-2 text-left text-[#a3b8a3]">Creditor</th>
                <th className="px-3 py-2 text-left text-[#a3b8a3]">Action</th>
              </tr>
            </thead>
            <tbody>
              {outstanding.map((debt) => (
                <tr key={debt.id} className="border-b border-[#1e3a1e]/50 last:border-0 hover:bg-[#1a3a1a]/30">
                  <td className="px-3 py-2 text-[#a3b8a3]">{debt.id}</td>
                  <td className="px-3 py-2 text-[#f0ede4]">{debt.session_date}</td>
                  <td className="px-3 py-2 font-medium text-red-400">{debt.debtor}</td>
                  <td className="px-3 py-2 font-medium text-[#d4a017]">{debt.creditor}</td>
                  <td className="px-3 py-2">
                    <button
                      type="button"
                      onClick={() => onPayDebt(debt.id)}
                      className="rounded-lg bg-[#d4a017] px-3 py-1 text-xs font-semibold text-[#0d1a0d] transition-colors hover:bg-[#e8bb3a]"
                    >
                      Mark Paid
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Transfer debt chain */}
      {transferableChains.length > 0 && (
        <div className="mb-5 rounded-lg border border-[#1e3a1e] bg-[#0d1a0d] p-3">
          <h3 className="mb-2 text-sm font-semibold uppercase tracking-wider text-[#a3b8a3]">Transfer Debt Chain</h3>
          <div className="flex flex-wrap gap-2">
            <select
              value={selectedChain}
              onChange={(e) => onSelectChain(e.target.value)}
              className="flex-1 rounded-lg border border-[#1e3a1e] bg-[#122012] px-3 py-2 text-[#f0ede4] focus:border-[#d4a017] focus:outline-none"
            >
              <option value="">Select chain…</option>
              {transferableChains.map((chain) => (
                <option key={`${chain.debt1_id}-${chain.debt2_id}`} value={`${chain.debt1_id},${chain.debt2_id}`}>
                  #{chain.debt1_id} + #{chain.debt2_id} ({chain.path})
                </option>
              ))}
            </select>
            <button
              type="button"
              onClick={onTransferDebt}
              disabled={!selectedChain}
              className="rounded-lg bg-[#d4a017] px-4 py-2 text-sm font-semibold text-[#0d1a0d] transition-colors hover:bg-[#e8bb3a] disabled:cursor-not-allowed disabled:opacity-40"
            >
              Transfer
            </button>
          </div>
        </div>
      )}

      {/* Recently paid */}
      {recentlyPaid.length > 0 && (
        <div>
          <h3 className="mb-2 text-sm font-semibold uppercase tracking-wider text-[#a3b8a3]">Recently Paid</h3>
          <ul className="space-y-1 text-sm text-[#a3b8a3]">
            {recentlyPaid.map((debt) => (
              <li key={debt.id}>
                <span className="text-[#a3b8a3]/50">#{debt.id}</span>{' '}
                {debt.session_date}{' '}
                <span className="text-[#f0ede4]">{debt.debtor}</span>
                {' → '}
                <span className="text-[#d4a017]">{debt.creditor}</span>
                {' ✅'}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}
