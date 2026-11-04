'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { api } from '@/lib/api';

type Row = { rank: number; student: string; score: number; max_score?: number | null; accuracy?: number | null };

export default function Leaderboard() {
  const { id } = useParams<{ id: string }>();
  const [rows, setRows] = useState<Row[]>([]);
  const [error, setError] = useState('');
  useEffect(() => {
    let active = true;
    api<Row[]>(`/exams/${id}/leaderboard`).then((result) => { if (active) setRows(result); }).catch((err) => { if (active) setError(err instanceof Error ? err.message : 'Could not load leaderboard.'); });
    return () => { active = false; };
  }, [id]);
  return <main className="container-shell py-12">
    <h1 className="text-3xl font-black">Examination leaderboard</h1>
    <p className="mt-2 text-slate-500">Published results ranked by acquired score, with accuracy for each student.</p>
    <div className="card mt-7 overflow-hidden">
      <div className="grid grid-cols-[70px_minmax(0,1fr)_120px_120px] bg-slate-50 px-5 py-4 text-xs font-bold uppercase text-slate-500"><span>Rank</span><span>Student</span><span className="text-right">Score</span><span className="text-right">Accuracy</span></div>
      {rows.map((row) => <div key={row.rank} className="grid grid-cols-[70px_minmax(0,1fr)_120px_120px] items-center border-t border-slate-100 px-5 py-4 text-sm"><span>#{row.rank}</span><span className="font-semibold">{row.student}</span><span className="text-right font-bold">{row.score}{row.max_score ? <small className="ml-1 font-normal text-slate-400">/ {row.max_score}</small> : null}</span><span className="text-right font-semibold">{row.accuracy === null || row.accuracy === undefined ? '—' : `${row.accuracy.toFixed(1)}%`}</span></div>)}
      {!rows.length && <p className="p-8 text-center text-sm text-slate-500">{error || 'No published results yet.'}</p>}
    </div>
  </main>;
}
