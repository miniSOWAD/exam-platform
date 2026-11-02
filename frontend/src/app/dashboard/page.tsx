'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { api } from '@/lib/api';
import { LogOut, BookOpen, Users, Clock3, Plus, FileUp, Globe2, CalendarClock, Play, Pause, RotateCcw, Square } from 'lucide-react';

type User = { id: string; email: string; full_name: string; role: string };
type Exam = { id: string; title: string; subject: string; chapter?: string | null; set_name?: string | null; status: string; duration_seconds: number; question_count: number; scheduled_start_at?: string | null; scheduled_end_at?: string | null; time_extension_seconds?: number };
function dateLabel(value?: string | null) { return value ? new Date(value).toLocaleString() : 'Not scheduled'; }

export default function Dashboard() {
  const [user, setUser] = useState<User | null>(null);
  const [exams, setExams] = useState<Exam[]>([]);
  const [error, setError] = useState('');
  const [title, setTitle] = useState('');
  const [subject, setSubject] = useState('General');
  const [duration, setDuration] = useState('60');
  const [creating, setCreating] = useState(false);
  const router = useRouter();

  async function refreshExams() { setExams(await api<Exam[]>('/exams')); }
  useEffect(() => { let active = true; Promise.all([api<User>('/auth/me'), api<Exam[]>('/exams')]).then(([u,e]) => { if (active) { setUser(u); setExams(e); } }).catch(() => router.replace('/login')); return () => { active = false; }; }, [router]);
  async function logout() { await api('/auth/logout', { method: 'POST' }); router.replace('/'); }
  async function controlExam(id: string, action: string) { setError(''); try { await api(`/exams/${id}/control/${action}`, { method: 'POST' }); await refreshExams(); } catch (err) { setError(err instanceof Error ? err.message : 'Could not update examination status.'); } }
  async function publishExam(id: string) { setError(''); try { await api(`/exams/${id}/publish`, { method: 'POST' }); await refreshExams(); } catch (err) { setError(err instanceof Error ? err.message : 'Could not publish exam'); } }
  async function createExam(event: React.FormEvent) {
    event.preventDefault(); setCreating(true); setError('');
    try { await api('/exams', { method: 'POST', body: JSON.stringify({ title, subject, duration_seconds: Number(duration)*60, description: '', access_mode: 'all_students', max_attempts: 1, pass_marks: 0 }) }); setTitle(''); await refreshExams(); }
    catch (err) { setError(err instanceof Error ? err.message : 'Could not create exam'); }
    finally { setCreating(false); }
  }
  if (!user) return <main className="container-shell py-20">Loading workspace…</main>;

  return <main className="container-shell py-10">
    <div className="flex flex-wrap items-center justify-between gap-4"><div><p className="text-sm font-bold text-brand">{user.role.toUpperCase()} WORKSPACE</p><h1 className="mt-1 text-3xl font-black">Welcome, {user.full_name}</h1><p className="mt-2 text-slate-500">Manage examinations, schedules and student progress.</p></div><div className="flex flex-wrap gap-2">{user.role === 'admin' && <Link href="/dashboard/site-content" className="rounded-xl border border-teal-100 bg-teal-50 px-4 py-2 text-sm font-bold text-teal-800"><Globe2 className="mr-2 inline" size={16}/>Manage website</Link>}<button onClick={logout} className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-bold"><LogOut className="mr-2 inline" size={16}/>Sign out</button></div></div>
    <div className="mt-8 grid gap-4 md:grid-cols-3"><div className="card p-5"><BookOpen className="text-brand"/><p className="mt-4 text-sm text-slate-500">Available exams</p><p className="text-3xl font-black">{exams.length}</p></div><div className="card p-5"><Users className="text-brand"/><p className="mt-4 text-sm text-slate-500">Your account</p><p className="text-xl font-black capitalize">{user.role}</p></div><div className="card p-5"><Clock3 className="text-brand"/><p className="mt-4 text-sm text-slate-500">Exam access</p><p className="text-xl font-black">{user.role==='student'?'Assigned exams':'Management'}</p></div></div>
    <div className="mt-10 flex flex-wrap items-center justify-between gap-3"><h2 className="text-xl font-black">Examinations</h2>{user.role!=='student'&&<div className="flex gap-2"><Link className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-bold" href="/dashboard/import"><FileUp className="mr-2 inline" size={16}/>Import PDF</Link><Link className="btn" href="#create"><Plus size={17} className="mr-2"/>Create exam</Link></div>}</div>
    {error&&<p role="alert" className="mt-4 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</p>}
    {user.role!=='student'&&<form onSubmit={createExam} id="create" className="card mt-5 grid gap-3 p-5 md:grid-cols-[2fr_1fr_1fr_auto]"><input className="field" placeholder="Exam title" required value={title} onChange={e=>setTitle(e.target.value)}/><input className="field" placeholder="Subject" value={subject} onChange={e=>setSubject(e.target.value)}/><input className="field" type="number" min="1" max="1440" value={duration} onChange={e=>setDuration(e.target.value)}/><button className="btn" disabled={creating}>{creating?'Creating…':'Create'}</button></form>}
    <div className="mt-4 grid gap-4 md:grid-cols-2">{exams.map((exam)=><article key={exam.id} className="card p-5"><div className="flex justify-between gap-3"><span className="text-xs font-bold uppercase tracking-wider text-brand">{exam.subject}</span><span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-bold capitalize">{exam.status.replace('_',' ')}</span></div><h3 className="mt-3 text-lg font-extrabold">{exam.title}</h3><p className="mt-2 text-sm text-slate-500">{exam.chapter ? `${exam.chapter} · ` : ''}{exam.set_name ? `${exam.set_name} · ` : ''}{exam.question_count} questions · {Math.round(exam.duration_seconds/60)} minutes</p>
      {exam.scheduled_start_at && <p className="mt-2 text-xs text-slate-500"><CalendarClock className="mr-1 inline" size={13}/>Starts: {dateLabel(exam.scheduled_start_at)}</p>}
      <div className="mt-5 flex flex-wrap items-center gap-x-4 gap-y-3"><Link href={`/exams/${exam.id}`} className="text-sm font-bold text-brand">Open exam →</Link>{user.role!=='student'&&<><Link href={`/dashboard/exams/${exam.id}/edit`} className="text-sm font-bold text-slate-700">Edit questions</Link><Link href={`/dashboard/exams/${exam.id}/schedule`} className="text-sm font-bold text-teal-700">Schedule & timing</Link>{exam.status==='draft'&&<button onClick={()=>publishExam(exam.id)} className="text-sm font-bold text-emerald-700">Publish exam</button>}{exam.status==='published'&&<button onClick={()=>controlExam(exam.id,'start')} className="text-sm font-bold text-emerald-700"><Play className="mr-1 inline" size={13}/>Start</button>}{exam.status==='live'&&<button onClick={()=>controlExam(exam.id,'pause')} className="text-sm font-bold text-amber-700"><Pause className="mr-1 inline" size={13}/>Pause</button>}{exam.status==='paused'&&<button onClick={()=>controlExam(exam.id,'resume')} className="text-sm font-bold text-emerald-700"><RotateCcw className="mr-1 inline" size={13}/>Resume</button>}{['live','paused'].includes(exam.status)&&<button onClick={()=>controlExam(exam.id,'end')} className="text-sm font-bold text-red-700"><Square className="mr-1 inline" size={12}/>End</button>}</>}</div>
    </article>)}</div>
    {exams.length===0&&<div className="card mt-4 p-10 text-center text-slate-500">No examinations are available yet.</div>}
  </main>;
}
