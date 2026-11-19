'use client';
import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { api, isUnauthorizedError } from '@/lib/api';
import type { LeaderboardRow } from '@/lib/leaderboards';
import StudentLeaderboardTable from '@/components/StudentLeaderboardTable';

export default function Leaderboard() {
  const { id } = useParams<{ id: string }>();
  const [rows, setRows] = useState<LeaderboardRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [needsLogin, setNeedsLogin] = useState(false);
  useEffect(() => {
    let active = true; setLoading(true); setRows([]); setError(''); setNeedsLogin(false);
    api<LeaderboardRow[]>(`/exams/${encodeURIComponent(id)}/leaderboard`).then((data) => { if (active) setRows(data); })
      .catch((err) => { if (active) { setNeedsLogin(isUnauthorizedError(err)); setError(err instanceof Error ? err.message : 'Could not load leaderboard.'); } })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [id]);
  return <main className="container-shell py-12">
    <Link href="/leaderboard" className="text-sm font-bold text-brand">← All leaderboards</Link>
    <h1 className="mt-4 text-3xl font-black">Examination leaderboard</h1>
    <p className="mt-2 text-slate-500">Results ranked by acquired score, with accuracy for each student.</p>
    {needsLogin ? <Link className="btn mt-5" href={`/login?next=${encodeURIComponent(`/leaderboard/${id}`)}`}>Sign in to view rankings</Link> : <StudentLeaderboardTable rows={rows} loading={loading} error={error}/>}
  </main>;
}
