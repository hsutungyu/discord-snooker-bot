export function MirrorSyncCard({ onSync }) {
  return (
    <section className="rounded-2xl border border-[#1e3a1e] bg-[#122012] p-6 shadow-lg">
      <h2 className="mb-3 text-xl font-bold text-[#d4a017]">Mirror Sync</h2>
      <p className="mb-4 text-sm text-[#a3b8a3]">Trigger a GitHub → Gitea repository mirror sync.</p>
      <button
        type="button"
        onClick={onSync}
        className="rounded-lg border border-[#1e3a1e] bg-[#0d1a0d] px-5 py-2 text-[#f0ede4] transition-colors hover:border-[#d4a017]/50 hover:text-[#d4a017]"
      >
        🔄 Trigger Mirror Sync
      </button>
    </section>
  )
}
