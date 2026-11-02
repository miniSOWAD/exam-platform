'use client';

import { FormEvent, useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft, CalendarClock, Clock3, PlusCircle, Save } from 'lucide-react';
import { api } from '@/lib/api';

type Exam = { id: string; title: string; subject: string; status: string; duration_seconds: number; scheduled_start_at?: string | null; scheduled_end_at?: string | null; time_extension_seconds?: number };
type User = { role: string };
function toLocal(value?: string | null) {
  if (!value) return '';
  const date = new Date(value);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth()+1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}
function toIso(value: string) { return value ? new Date(value).toISOString() : null; }

export default function ExamSchedulePage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [exam, setExam] = useState<Exam | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [startAt, setStartAt] = useState('');
  const [endAt, setEndAt] = useState('');
  const [minutes, setMinutes] = useState('10');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [extending, setExtending] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  useEffect(() => { let active = true; Promise.all([api<User>('/auth/me'), api<Exam>(`/exams/${id}`)]).then(([currentUser,currentExam]) => { if (!active) return; if (currentUser.role === 'student') { router.replace('/dashboard'); return; } setUser(currentUser); setExam(currentExam); setStartAt(toLocal(currentExam.scheduled_start_at)); setEndAt(toLocal(currentExam.scheduled_end_at)); }).catch(() => router.replace('/login')).finally(() => { if (active) setLoading(false); }); return () => { active = false; }; }, [id, router]);

  async function saveSchedule(event: FormEvent) {
    event.preventDefault(); setSaving(true); setError(''); setMessage('');
    try {
      const updated = await api<Exam>(`/exams/${id}/schedule`, { method: 'PATCH', body: JSON.stringify({ scheduled_start_at: toIso(startAt), scheduled_end_at: toIso(endAt) }) });
      setExam(updated); setMessage('Exam schedule updated successfully.');
    } catch (err) { setError(err instanceof Error ? err.message : 'Could not update schedule.'); }
    finally { setSaving(false); }
  }
  async function extendTime() {
    setExtending(true); setError(''); setMessage('');
    try {
      const updated = await api<Exam>(`/exams/${id}/extend-time`, { method: 'POST', body: JSON.stringify({ minutes: Number(minutes) }) });
      setExam(updated); setEndAt(toLocal(updated.scheduled_end_at)); setMessage(`Added ${minutes} minutes. The updated duration is now ${Math.round(updated.duration_seconds/60)} minutes.`);
    } catch (err) { setError(err instanceof Error ? err.message : 'Could not extend examination time.'); }
    finally { setExtending(false); }
  }

  if (loading || !user || !exam) return <main className="container-shell py-20">Loading examination timing…</main>;
  const canSchedule = ['draft','published'].includes(exam.status);
  const canExtend = ['published','live','paused'].includes(exam.status);
  return <main className="container-shell py-9">
    <Link href="/dashboard" className="inline-flex items-center gap-2 text-sm font-bold text-slate-500 hover:text-brand"><ArrowLeft size={16}/> Back to dashboard</Link>
    <div className="mt-6"><p className="text-xs font-black tracking-[.18em] text-teal-700">EXAM CONTROL</p><h1 className="mt-2 text-3xl font-bold">Schedule & timing</h1><p className="mt-2 text-slate-500">{exam.title} · {exam.subject}</p></div>
    {error && <p role="alert" className="mt-5 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</p>}
    {message && <p role="status" className="mt-5 rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">{message}</p>}
    <div className="mt-7 grid gap-5 lg:grid-cols-2">
      <section className="card p-6"><div className="mb-5 flex items-center gap-3"><CalendarClock className="text-teal-700"/><div><h2 className="text-xl font-bold">Exam schedule</h2><p className="text-xs text-slate-500">Set or change when an upcoming exam is scheduled.</p></div></div>
        <form onSubmit={saveSchedule} className="space-y-4">
          <label className="block text-sm font-semibold text-slate-700">Scheduled start<input className="field mt-2 font-normal" type="datetime-local" value={startAt} disabled={!canSchedule} onChange={(e)=>setStartAt(e.target.value)}/></label>
          <label className="block text-sm font-semibold text-slate-700">Scheduled end (optional)<input className="field mt-2 font-normal" type="datetime-local" value={endAt} disabled={!canSchedule} onChange={(e)=>setEndAt(e.target.value)}/></label>
          {!canSchedule && <p className="text-xs text-amber-700">This exam is already {exam.status}. Its start schedule is locked; use time extension for live or paused exams.</p>}
          <button className="btn" disabled={!canSchedule || saving}>{saving ? 'Saving schedule…' : <><Save className="mr-2" size={16}/>Save schedule</>}</button>
        </form>
      </section>
      <section className="card p-6"><div className="mb-5 flex items-center gap-3"><Clock3 className="text-teal-700"/><div><h2 className="text-xl font-bold">Extend examination time</h2><p className="text-xs text-slate-500">Add time to an upcoming, live or paused examination.</p></div></div>
        <div className="grid grid-cols-2 gap-3"><div className="rounded-xl bg-slate-50 p-4"><span className="text-xs text-slate-500">Current duration</span><strong className="mt-1 block text-2xl">{Math.round(exam.duration_seconds/60)} min</strong></div><div className="rounded-xl bg-slate-50 p-4"><span className="text-xs text-slate-500">Time added so far</span><strong className="mt-1 block text-2xl">{Math.round((exam.time_extension_seconds || 0)/60)} min</strong></div></div>
        <label className="mt-5 block text-sm font-semibold text-slate-700">Additional minutes<input className="field mt-2 max-w-xs font-normal" type="number" min="1" max="1440" value={minutes} onChange={(e)=>setMinutes(e.target.value)}/></label>
        <button type="button" className="btn mt-4" disabled={!canExtend || extending || Number(minutes)<1} onClick={extendTime}>{extending ? 'Extending…' : <><PlusCircle className="mr-2" size={16}/>Extend exam time</>}</button>
        <p className="mt-4 text-xs leading-6 text-slate-500">For a running or paused exam, the server timer is updated and active attempts receive the extra time at their next timer sync. If an end date is set, it is extended by the same amount.</p>
      </section>
    </div>
  </main>;
}
