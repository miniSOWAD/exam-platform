import type { LeaderboardRow } from '@/lib/leaderboards';

export default function StudentLeaderboardTable({ rows, loading, error }: { rows: LeaderboardRow[]; loading: boolean; error: string }) {
  return <div className="card mt-7 overflow-x-auto" aria-live="polite">
    <table className="w-full text-left text-sm">
      <thead className="bg-slate-50 text-xs font-bold uppercase text-slate-500"><tr><th className="px-3 py-4 sm:px-5">Rank</th><th className="px-3 py-4 sm:px-5">Student</th><th className="px-3 py-4 text-right sm:px-5">Score</th><th className="px-3 py-4 text-right sm:px-5">Accuracy</th></tr></thead>
      <tbody className="divide-y divide-slate-100">
        {loading || error || !rows.length ? <tr><td colSpan={4} className="p-8 text-center text-slate-500">{loading ? 'Loading rankings…' : error || 'No rankings are available for this selection yet.'}</td></tr> : rows.map((row) => <tr key={row.rank}><td className="px-3 py-4 sm:px-5">#{row.rank}</td><td className="break-words px-3 py-4 font-semibold sm:px-5">{row.student}</td><td className="whitespace-nowrap px-3 py-4 text-right font-bold sm:px-5">{row.score}{row.max_score != null && <small className="ml-1 font-normal text-slate-500">/ {row.max_score}</small>}</td><td className="px-3 py-4 text-right font-semibold sm:px-5">{row.accuracy == null ? '—' : `${row.accuracy.toFixed(1)}%`}</td></tr>)}
      </tbody>
    </table>
  </div>;
}
