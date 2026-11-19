'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Trophy, RefreshCw } from 'lucide-react';
import { api, isUnauthorizedError } from '@/lib/api';
import type { LeaderboardCatalog, LeaderboardRow, LeaderboardScope } from '@/lib/leaderboards';
import StudentLeaderboardTable from '@/components/StudentLeaderboardTable';

const labels: Record<LeaderboardScope, string> = { exam: 'By Exam', paper: 'By Paper', subject: 'By Subject' };
export default function LeaderboardsPage() {
  const [catalog, setCatalog] = useState<LeaderboardCatalog | null>(null);
  const [scope, setScope] = useState<LeaderboardScope>('exam');
  const [examId, setExamId] = useState('');
  const [paper, setPaper] = useState('');
  const [subject, setSubject] = useState('');
  const [paperSubject, setPaperSubject] = useState('');
  const [rows, setRows] = useState<LeaderboardRow[]>([]);
  const [catalogLoading, setCatalogLoading] = useState(true);
  const [loading, setLoading] = useState(false);
  const [catalogError, setCatalogError] = useState('');
  const [error, setError] = useState('');
  const [needsLogin, setNeedsLogin] = useState(false);
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    let active = true;
    setCatalogLoading(true); setCatalogError(''); setNeedsLogin(false);
    api<LeaderboardCatalog>('/leaderboards/catalog').then((data) => {
      if (!active) return;
      setCatalog(data);
      setExamId((old) => data.exams.some((exam) => exam.id === old) ? old : data.exams[0]?.id || '');
      setPaper((old) => data.papers.includes(old) ? old : data.papers[0] || '');
      setSubject((old) => data.subjects.includes(old) ? old : data.subjects[0] || '');
      setPaperSubject((old) => data.subjects.includes(old) ? old : '');
      setScope((old) => old === 'exam' && !data.exams.length ? data.papers.length ? 'paper' : data.subjects.length ? 'subject' : 'exam' : old);
    }).catch((err) => { if (active) { setCatalog(null); setNeedsLogin(isUnauthorizedError(err)); setCatalogError(err instanceof Error ? err.message : 'Could not load leaderboards.'); } })
      .finally(() => { if (active) setCatalogLoading(false); });
    return () => { active = false; };
  }, [revision]);
  const params = new URLSearchParams({ scope });
  if (scope === 'exam' && examId) params.set('exam_id', examId);
  if (scope === 'paper' && paper) { params.set('paper', paper); if (paperSubject) params.set('subject', paperSubject); }
  if (scope === 'subject' && subject) params.set('subject', subject);
  const query = params.toString();
  const hasSelection = scope === 'exam' ? !!examId : scope === 'paper' ? !!paper : !!subject;
  useEffect(() => {
    setRows([]); setError('');
    if (!catalog || catalogLoading || !hasSelection) { setLoading(false); return; }
    let active = true; setLoading(true);
    api<LeaderboardRow[]>(`/leaderboards?${query}`).then((data) => { if (active) setRows(data); })
      .catch((err) => { if (active) { setNeedsLogin(isUnauthorizedError(err)); setError(err instanceof Error ? err.message : 'Could not load rankings.'); } })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [catalog, catalogLoading, query, hasSelection]);
  return <main className="container-shell py-12">
    <div className="flex flex-wrap items-center justify-between gap-4"><div><p className="text-xs font-black uppercase tracking-[.18em] text-brand">CELEBRATE PROGRESS</p><h1 className="mt-2 text-3xl font-black">Leaderboard</h1><p className="mt-2 text-slate-500">Explore student rankings by examination, paper or subject.</p></div><button type="button" className="btn" disabled={catalogLoading} onClick={() => setRevision((n) => n + 1)}><RefreshCw size={16} className="mr-2"/>Refresh</button></div>
    {needsLogin ? <div className="card mt-7 p-8 text-center"><p>Sign in to view student rankings.</p><Link href="/login?next=%2Fleaderboard" className="btn mt-4">Sign in</Link></div> : catalogLoading ? <p className="mt-7 text-slate-500">Loading leaderboards…</p> : catalogError ? <p className="card mt-7 p-6 text-red-700" role="alert">{catalogError}</p> : catalog && <>
      <div className="mt-7 flex flex-wrap gap-2" aria-label="Ranking category">{(Object.keys(labels) as LeaderboardScope[]).map((item) => <button key={item} type="button" aria-pressed={scope === item} onClick={() => setScope(item)} className={`flex items-center gap-2 rounded-xl border px-4 py-2 text-sm font-bold ${scope === item ? 'border-indigo-200 bg-indigo-50 text-brand' : 'border-slate-200 bg-white text-slate-600'}`}><Trophy size={16}/>{labels[item]}</button>)}</div>
      <div className="card mt-5 grid gap-4 p-5 md:grid-cols-2">
        {scope === 'exam' && <label className="block text-sm font-semibold">Choose examination<select className="field mt-2" value={examId} onChange={(e) => setExamId(e.target.value)}>{!catalog.exams.length && <option value="">No examinations with rankings</option>}{catalog.exams.map((exam) => <option key={exam.id} value={exam.id}>{exam.title}</option>)}</select></label>}
        {scope === 'paper' && <><label className="block text-sm font-semibold">Choose paper<select className="field mt-2" value={paper} onChange={(e) => setPaper(e.target.value)}>{!catalog.papers.length && <option value="">No paper rankings</option>}{catalog.papers.map((item) => <option key={item}>{item}</option>)}</select></label><label className="block text-sm font-semibold">Subject filter<select className="field mt-2" value={paperSubject} onChange={(e) => setPaperSubject(e.target.value)}><option value="">All subjects</option>{catalog.subjects.map((item) => <option key={item}>{item}</option>)}</select></label></>}
        {scope === 'subject' && <label className="block text-sm font-semibold">Choose subject<select className="field mt-2" value={subject} onChange={(e) => setSubject(e.target.value)}>{!catalog.subjects.length && <option value="">No subject rankings</option>}{catalog.subjects.map((item) => <option key={item}>{item}</option>)}</select></label>}
      </div>
      <StudentLeaderboardTable rows={rows} loading={loading} error={error}/>
      <p className="mt-4 text-xs text-slate-500">Ranked by acquired score, then accuracy. A dash means accuracy or maximum score is unavailable.</p>
    </>}
  </main>;
}
