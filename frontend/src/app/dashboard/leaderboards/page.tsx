'use client';

import { FormEvent, useCallback, useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  Trophy, Plus, RefreshCw, Trash2, Loader2, Medal, UserRound, ClipboardList,
} from 'lucide-react';
import { api, isUnauthorizedError } from '@/lib/api';

type Scope = 'exam' | 'paper' | 'subject';
type Exam = { id: string; title: string; subject: string; paper?: string | null; status: string; question_count: number };
type LeaderboardRow = {
  id: string; entry_id?: string | null; manual_entry_id?: string | null; student_id?: string | null;
  student: string; email?: string; student_identifier?: string; score: number; max_score?: number | null;
  accuracy?: number | null; correct_count: number; answered_count: number; total_questions: number; exam_count: number;
  source: 'attempt' | 'manual' | 'combined'; rank: number; submitted_at?: string | null;
};
type LeaderboardResponse = { scope: Scope; total: number; rows: LeaderboardRow[] };

const scopeLabels: Record<Scope, string> = { exam: 'By Exam', paper: 'By Paper', subject: 'By Subject' };

export default function LeaderboardManagementPage() {
  const router = useRouter();
  const [authorized, setAuthorized] = useState(false);
  const [scope, setScope] = useState<Scope>('exam');
  const [exams, setExams] = useState<Exam[]>([]);
  const [examId, setExamId] = useState('');
  const [paper, setPaper] = useState<'1st Paper' | '2nd Paper'>('1st Paper');
  const [subject, setSubject] = useState('');
  const [rows, setRows] = useState<LeaderboardRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [showAdd, setShowAdd] = useState(false);
  const [saving, setSaving] = useState(false);
  const [displayName, setDisplayName] = useState('');
  const [studentIdentifier, setStudentIdentifier] = useState('');
  const [score, setScore] = useState('');
  const [maxScore, setMaxScore] = useState('');
  const [entryExamId, setEntryExamId] = useState('');
  const [entryPaper, setEntryPaper] = useState<'1st Paper' | '2nd Paper'>('1st Paper');
  const [entrySubject, setEntrySubject] = useState('');

  const subjects = useMemo(() => Array.from(new Set(exams.map((exam) => exam.subject.trim()).filter(Boolean))).sort((a, b) => a.localeCompare(b)), [exams]);

  useEffect(() => {
    let active = true;
    async function initialize() {
      try {
        const currentUser = await api<{ role: string }>('/auth/me');
        if (!active) return;
        if (currentUser.role !== 'admin') { router.replace('/dashboard'); return; }
        setAuthorized(true);
        try {
          const examRows = await api<Exam[]>('/exams');
          if (!active) return;
          setExams(examRows);
          const first = examRows[0]?.id || '';
          setExamId(first); setEntryExamId(first);
          const firstSubject = examRows.find((exam) => exam.subject)?.subject || '';
          setSubject(firstSubject); setEntrySubject(firstSubject);
        } catch (error) {
          if (!active) return;
          if (isUnauthorizedError(error)) router.replace('/login?next=%2Fdashboard%2Fleaderboards');
          else setError(error instanceof Error ? error.message : 'Could not load examination filters.');
        }
      } catch (error) {
        if (!active) return;
        if (isUnauthorizedError(error)) router.replace('/login?next=%2Fdashboard%2Fleaderboards');
        else setError(error instanceof Error ? error.message : 'Could not verify administrator access.');
      }
    }
    void initialize();
    return () => { active = false; };
  }, [router]);

  const loadRows = useCallback(async () => {
    if (scope === 'exam' && !examId) { setRows([]); return; }
    if (scope === 'subject' && !subject.trim()) { setRows([]); return; }
    setLoading(true); setError('');
    try {
      const params = new URLSearchParams({ scope });
      if (scope === 'exam') params.set('exam_id', examId);
      if (scope === 'paper') { params.set('paper', paper); if (subject.trim()) params.set('subject', subject.trim()); }
      if (scope === 'subject') params.set('subject', subject.trim());
      const result = await api<LeaderboardResponse>(`/admin/leaderboards?${params.toString()}`);
      setRows(result.rows || []);
    } catch (err) { setError(err instanceof Error ? err.message : 'Could not load leaderboard.'); }
    finally { setLoading(false); }
  }, [scope, examId, paper, subject]);

  useEffect(() => { if (authorized) void loadRows(); }, [authorized, loadRows]);

  useEffect(() => {
    if (scope === 'exam' && examId) setEntryExamId(examId);
    if (scope === 'paper') { setEntryPaper(paper); setEntrySubject(subject || ''); }
    if (scope === 'subject' && subject) setEntrySubject(subject);
  }, [scope, examId, paper, subject]);

  function resetAddForm() {
    setDisplayName(''); setStudentIdentifier(''); setScore(''); setMaxScore('');
    setEntryExamId(examId || exams[0]?.id || ''); setEntryPaper(paper); setEntrySubject(scope === 'paper' ? '' : (subject || subjects[0] || ''));
  }

  async function addEntry(event: FormEvent) {
    event.preventDefault();
    setSaving(true); setError(''); setNotice('');
    try {
      const payload: Record<string, unknown> = {
        scope, display_name: displayName.trim(), student_identifier: studentIdentifier.trim() || null,
        score: Number(score), max_score: maxScore.trim() ? Number(maxScore) : null,
      };
      if (scope === 'exam') payload.exam_id = entryExamId;
      if (scope === 'paper') { payload.paper = entryPaper; payload.subject = entrySubject.trim() || null; }
      if (scope === 'subject') payload.subject = entrySubject.trim();
      await api('/admin/leaderboards/entries', { method: 'POST', body: JSON.stringify(payload) });
      setNotice(`${displayName.trim()} was added to the ${scopeLabels[scope].toLowerCase()} leaderboard.`);
      setShowAdd(false); resetAddForm(); await loadRows();
    } catch (err) { setError(err instanceof Error ? err.message : 'Could not add leaderboard entry.'); }
    finally { setSaving(false); }
  }

  async function removeRow(row: LeaderboardRow) {
    const label = row.student || 'this entry';
    if (!window.confirm(`Remove ${label} from this ${scopeLabels[scope].toLowerCase()} leaderboard? ${row.student_id ? 'This will hide the student from this leaderboard without deleting their exam attempt.' : 'This will delete the manual leaderboard entry.'}`)) return;
    setSaving(true); setError(''); setNotice('');
    try {
      const payload: Record<string, unknown> = { scope };
      if (scope === 'exam') payload.exam_id = examId;
      if (scope === 'paper') { payload.paper = paper; payload.subject = subject.trim() || null; }
      if (scope === 'subject') payload.subject = subject.trim();
      if (row.student_id) payload.student_id = row.student_id;
      else payload.entry_id = row.entry_id || row.id.replace(/^manual:/, '');
      await api('/admin/leaderboards/remove', { method: 'POST', body: JSON.stringify(payload) });
      setNotice(`${label} was removed from this leaderboard.`);
      await loadRows();
    } catch (err) { setError(err instanceof Error ? err.message : 'Could not remove this leaderboard entry.'); }
    finally { setSaving(false); }
  }

  const selectedExam = exams.find((exam) => exam.id === examId);

  return <main className="container-shell py-9">
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div><p className="text-xs font-black uppercase tracking-[.18em] text-brand">ADMIN CONTROL PANEL</p><h1 className="mt-2 text-3xl font-black">Leaderboard management</h1><p className="mt-2 text-slate-500">Manage manual records and automatically ranked student exam performance.</p></div>
      <button type="button" onClick={() => { setShowAdd((open) => !open); setError(''); resetAddForm(); }} className="btn"><Plus className="mr-2" size={17}/>{showAdd ? 'Close form' : 'Add to leaderboard'}</button>
    </div>

    <div className="mt-7 flex flex-wrap gap-2" role="tablist" aria-label="Leaderboard category">
      {(['exam', 'paper', 'subject'] as Scope[]).map((value) => <button key={value} type="button" role="tab" aria-selected={scope === value} onClick={() => { setScope(value); if (value === 'paper') setSubject(''); else if (value === 'subject' && !subject) setSubject(subjects[0] || ''); setError(''); setNotice(''); }} className={`admin-tab ${scope === value ? 'is-active' : ''}`}><Trophy size={16}/>{scopeLabels[value]}</button>)}
    </div>

    {showAdd && <section className="card mt-5 p-5 md:p-6">
      <div className="mb-4 flex items-center gap-3"><span className="rounded-xl bg-indigo-50 p-3 text-indigo-700"><Medal size={20}/></span><div><h2 className="text-lg font-black">Add a leaderboard record</h2><p className="text-xs text-slate-500">The entry is placed automatically according to its acquired score.</p></div></div>
      <form onSubmit={addEntry} className="space-y-4">
        <div className="grid gap-3 md:grid-cols-2">
          <label className="block text-sm font-semibold">Name<input className="field mt-2 font-normal" required minLength={2} maxLength={160} value={displayName} onChange={(event) => setDisplayName(event.target.value)} placeholder="Student name"/></label>
          <label className="block text-sm font-semibold">Student email / profile / username <span className="font-normal text-slate-400">(optional)</span><input className="field mt-2 font-normal" value={studentIdentifier} onChange={(event) => setStudentIdentifier(event.target.value)} placeholder="Optional student identifier"/></label>
          {scope === 'exam' && <label className="block text-sm font-semibold md:col-span-2">Examination<select className="field mt-2 font-normal" required value={entryExamId} onChange={(event) => setEntryExamId(event.target.value)}><option value="">Choose an examination</option>{exams.map((exam) => <option key={exam.id} value={exam.id}>{exam.title} · {exam.subject}</option>)}</select></label>}
          {scope === 'paper' && <>
            <label className="block text-sm font-semibold">Paper<select className="field mt-2 font-normal" value={entryPaper} onChange={(event) => setEntryPaper(event.target.value as typeof entryPaper)}><option>1st Paper</option><option>2nd Paper</option></select></label>
            <label className="block text-sm font-semibold">Subject <span className="font-normal text-slate-400">(optional filter)</span><input className="field mt-2 font-normal" list="leaderboard-subject-options" value={entrySubject} onChange={(event) => setEntrySubject(event.target.value)} placeholder="All subjects"/><datalist id="leaderboard-subject-options">{subjects.map((item) => <option key={item} value={item}/>)}</datalist></label>
          </>}
          {scope === 'subject' && <label className="block text-sm font-semibold md:col-span-2">Subject<input className="field mt-2 font-normal" list="leaderboard-subject-options" required value={entrySubject} onChange={(event) => setEntrySubject(event.target.value)} placeholder="e.g. Biology"/><datalist id="leaderboard-subject-options">{subjects.map((item) => <option key={item} value={item}/>)}</datalist></label>}
          <label className="block text-sm font-semibold">Acquired score<input className="field mt-2 font-normal" type="number" min="0" step="0.01" required value={score} onChange={(event) => setScore(event.target.value)} placeholder="Required"/></label>
          <label className="block text-sm font-semibold">Maximum score <span className="font-normal text-slate-400">(optional, for accuracy)</span><input className="field mt-2 font-normal" type="number" min="0.01" step="0.01" value={maxScore} onChange={(event) => setMaxScore(event.target.value)} placeholder="e.g. 100"/></label>
        </div>
        <div className="flex flex-wrap justify-end gap-2 border-t border-slate-100 pt-4"><button type="button" className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-bold" onClick={() => { setShowAdd(false); resetAddForm(); }}>Cancel</button><button className="btn" disabled={saving || !displayName.trim() || !score.trim() || (scope === 'exam' && !entryExamId) || (scope === 'subject' && !entrySubject.trim())}>{saving ? <><Loader2 className="mr-2 animate-spin" size={16}/>Adding…</> : 'Add record'}</button></div>
      </form>
    </section>}

    {error && <p role="alert" className="mt-4 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</p>}
    {notice && <p role="status" className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">{notice}</p>}

    <section className="card mt-5 overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 p-4 md:p-5">
        <div><h2 className="font-black">{scopeLabels[scope]} rankings</h2><p className="mt-1 text-xs text-slate-500">Live rankings are calculated from submitted attempts and combined with admin-entered records.</p></div>
        <button type="button" onClick={() => void loadRows()} disabled={loading} className="rounded-xl border border-slate-200 bg-white p-2.5 text-slate-600 hover:bg-slate-50" aria-label="Refresh leaderboard"><RefreshCw size={17}/></button>
      </div>
      <div className="grid gap-3 border-b border-slate-100 bg-slate-50/60 p-4 md:grid-cols-2">
        {scope === 'exam' && <label className="block text-sm font-semibold">Choose examination<select className="field mt-2 bg-white font-normal" value={examId} onChange={(event) => setExamId(event.target.value)}><option value="">Choose an examination</option>{exams.map((exam) => <option key={exam.id} value={exam.id}>{exam.title} · {exam.subject}</option>)}</select></label>}
        {scope === 'paper' && <>
          <label className="block text-sm font-semibold">Choose paper<select className="field mt-2 bg-white font-normal" value={paper} onChange={(event) => setPaper(event.target.value as typeof paper)}><option>1st Paper</option><option>2nd Paper</option></select></label>
          <label className="block text-sm font-semibold">Subject filter <span className="font-normal text-slate-400">(optional)</span><input className="field mt-2 bg-white font-normal" list="leaderboard-subject-filter-options" value={subject} onChange={(event) => setSubject(event.target.value)} placeholder="All subjects"/><datalist id="leaderboard-subject-filter-options">{subjects.map((item) => <option key={item} value={item}/>)}</datalist></label>
        </>}
        {scope === 'subject' && <label className="block text-sm font-semibold">Choose subject<input className="field mt-2 bg-white font-normal" list="leaderboard-subject-filter-options" value={subject} onChange={(event) => setSubject(event.target.value)} placeholder="Enter or choose a subject"/><datalist id="leaderboard-subject-filter-options">{subjects.map((item) => <option key={item} value={item}/>)}</datalist></label>}
        {scope === 'exam' && selectedExam && <p className="self-end pb-3 text-xs text-slate-500">{selectedExam.question_count} questions · {selectedExam.status.replace('_', ' ')}</p>}
        {scope === 'paper' && !subject && <p className="self-end pb-3 text-xs text-slate-500">All subjects are combined for this paper type.</p>}
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-[760px] w-full text-left text-sm">
          <thead className="bg-white text-[11px] uppercase tracking-wide text-slate-500"><tr><th className="px-4 py-3">Rank</th><th className="px-4 py-3">Student</th><th className="px-4 py-3 text-right">Score</th><th className="px-4 py-3 text-right">Accuracy</th><th className="px-4 py-3">Source</th><th className="px-4 py-3 text-right">Action</th></tr></thead>
          <tbody className="divide-y divide-slate-100">
            {loading ? <tr><td colSpan={6} className="p-10 text-center text-slate-500"><Loader2 className="mr-2 inline animate-spin" size={17}/>Calculating rankings…</td></tr> : rows.map((row) => <tr key={row.id} className="hover:bg-slate-50/70">
              <td className="px-4 py-4"><span className={`grid h-8 w-8 place-items-center rounded-xl text-xs font-black ${row.rank === 1 ? 'bg-amber-100 text-amber-800' : row.rank === 2 ? 'bg-slate-100 text-slate-700' : row.rank === 3 ? 'bg-orange-100 text-orange-800' : 'bg-slate-50 text-slate-500'}`}>#{row.rank}</span></td>
              <td className="px-4 py-4"><div className="flex items-center gap-2"><span className="grid h-8 w-8 place-items-center rounded-full bg-blue-50 text-brand"><UserRound size={15}/></span><div><strong>{row.student}</strong><p className="mt-0.5 text-xs text-slate-500">{row.email || row.student_identifier || (row.source === 'attempt' ? 'Registered student' : 'Manual record')}</p></div></div></td>
              <td className="px-4 py-4 text-right font-bold tabular-nums">{row.score.toLocaleString()}<span className="ml-1 text-xs font-normal text-slate-400">{row.max_score ? `/ ${row.max_score.toLocaleString()}` : ''}</span></td>
              <td className="px-4 py-4 text-right font-semibold tabular-nums">{row.accuracy === null || row.accuracy === undefined ? '—' : `${row.accuracy.toFixed(1)}%`}</td>
              <td className="px-4 py-4"><span className={`rounded-full px-2.5 py-1 text-[10px] font-bold ${row.source === 'attempt' ? 'bg-emerald-50 text-emerald-700' : row.source === 'combined' ? 'bg-indigo-50 text-indigo-700' : 'bg-amber-50 text-amber-700'}`}>{row.source === 'attempt' ? 'Exam attempt' : row.source === 'combined' ? 'Attempt + manual' : 'Admin entry'}</span>{row.answered_count > 0 && <p className="mt-1 text-[10px] text-slate-400">{row.correct_count}/{row.total_questions} correct · {row.answered_count} answered · {row.exam_count} exam(s)</p>}</td>
              <td className="px-4 py-4 text-right"><button type="button" disabled={saving} onClick={() => void removeRow(row)} className="admin-action-button danger"><Trash2 size={14}/>Remove</button></td>
            </tr>)}
            {!loading && rows.length === 0 && <tr><td colSpan={6} className="p-12 text-center"><ClipboardList className="mx-auto text-slate-300" size={28}/><p className="mt-3 font-bold">No leaderboard entries yet</p><p className="mt-1 text-sm text-slate-500">Submitted attempts and manually added records will appear here.</p></td></tr>}
          </tbody>
        </table>
      </div>
      <div className="border-t border-slate-100 bg-slate-50/50 px-4 py-3 text-xs text-slate-500">{rows.length} ranked name(s). Ranking is ordered by acquired score, then accuracy.</div>
    </section>
  </main>;
}
