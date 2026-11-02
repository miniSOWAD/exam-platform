'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { api } from '@/lib/api';

type Exam = { id: string; title: string; description: string; status: string; duration_seconds: number; subject: string; scheduled_start_at?: string | null; scheduled_end_at?: string | null };
type Question = { id: string; kind: string; prompt: string; options: { id: string; text: string }[]; marks: number; position: number };
type AttemptSnapshot = { id: string; status: string; exam_status: string; answers: { question_id: string; answer: Record<string, any> }[]; remaining_seconds: number; duration_seconds: number };

export default function ExamPage() {
  const { id } = useParams<{ id: string }>();
  const search = useSearchParams();
  const attemptId = search.get('attempt');
  const [exam, setExam] = useState<Exam | null>(null);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [answers, setAnswers] = useState<Record<string, any>>({});
  const [index, setIndex] = useState(0);
  const [remaining, setRemaining] = useState(0);
  const [examStatus, setExamStatus] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const router = useRouter();

  useEffect(() => { api<Exam>(`/exams/${id}`).then(setExam).catch((e) => setError(e.message)); }, [id]);

  async function syncAttempt() {
    if (!attemptId) return;
    const snapshot = await api<AttemptSnapshot>(`/attempts/${attemptId}`);
    setRemaining(snapshot.remaining_seconds || 0);
    setExamStatus(snapshot.exam_status || '');
    return snapshot;
  }

  useEffect(() => {
    if (!attemptId) return;
    let active = true;
    Promise.all([api<Question[]>(`/attempts/${attemptId}/questions`), api<AttemptSnapshot>(`/attempts/${attemptId}`)])
      .then(([loadedQuestions, snapshot]) => {
        if (!active) return;
        setQuestions(loadedQuestions);
        setAnswers(Object.fromEntries((snapshot.answers || []).map((item) => [item.question_id, item.answer])));
        setRemaining(snapshot.remaining_seconds || 0);
        setExamStatus(snapshot.exam_status || '');
      }).catch((e) => { if (active) setError(e.message); });
    return () => { active = false; };
  }, [attemptId]);

  useEffect(() => {
    if (!attemptId) return;
    const poll = window.setInterval(() => { syncAttempt().catch((e) => setError(e.message)); }, 15000);
    return () => window.clearInterval(poll);
  }, [attemptId]);

  useEffect(() => {
    if (!attemptId || remaining <= 0 || examStatus !== 'live') return;
    const timer = window.setInterval(() => setRemaining((value) => Math.max(0, value - 1)), 1000);
    return () => window.clearInterval(timer);
  }, [attemptId, remaining > 0, examStatus]);

  async function save(question: Question, value: any) {
    setAnswers((old) => ({ ...old, [question.id]: value }));
    try { await api(`/attempts/${attemptId}/answers/${question.id}`, { method: 'PUT', body: JSON.stringify({ answer: value }) }); }
    catch (e) { setError(e instanceof Error ? e.message : 'Answer could not be saved'); }
  }
  async function submit() {
    if (!attemptId) return; setBusy(true);
    try { await api(`/attempts/${attemptId}/submit`, { method: 'POST' }); router.push('/dashboard'); }
    catch (e) { setError(e instanceof Error ? e.message : 'Submission failed'); }
    finally { setBusy(false); }
  }
  async function start() {
    try { const attempt = await api<{ attempt_id: string }>(`/exams/${id}/attempts`, { method: 'POST' }); router.replace(`/exams/${id}?attempt=${attempt.attempt_id}`); }
    catch (e) { setError(e instanceof Error ? e.message : 'Unable to start'); }
  }

  if (attemptId) {
    const question = questions[index];
    const paused = examStatus === 'paused';
    const ended = ['ended','results_published','archived'].includes(examStatus);
    return <main className="container-shell py-8">
      <div className="flex flex-wrap items-center justify-between gap-4"><div><p className="text-xs font-bold uppercase text-brand">Live examination</p><h1 className="text-2xl font-black">{exam?.title || 'Examination'}</h1><p className="mt-1 text-xs text-slate-500">{paused ? 'The administrator has paused this examination. Your remaining time is preserved.' : ended ? 'This examination has ended.' : 'Your answers are saved as you work.'}</p></div><div className="rounded-xl bg-ink px-4 py-3 text-lg font-black text-white">{Math.floor(remaining/60)}:{String(remaining%60).padStart(2,'0')}</div></div>
      {error && <p role="alert" className="mt-4 text-sm text-red-600">{error}</p>}
      {paused && <p className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">Exam paused. The timer will resume when the administrator resumes the examination.</p>}
      {ended && <p className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">The administrator has ended this examination. You can no longer change answers.</p>}
      {question ? <div className="card mt-6 p-6"><div className="flex justify-between text-sm text-slate-500"><span>Question {index+1} of {questions.length}</span><span>{question.marks} marks</span></div><h2 className="mt-5 text-xl font-bold leading-8">{question.prompt}</h2><div className="mt-6 space-y-3">{question.kind==='short_answer' ? <textarea className="field min-h-28" disabled={paused||ended||remaining<=0} value={answers[question.id]?.text||''} onChange={(e)=>save(question,{text:e.target.value})}/> : question.kind==='true_false' ? ['True','False'].map((value,i)=><label key={value} className={`flex cursor-pointer items-center gap-3 rounded-xl border p-4 ${paused||ended?'opacity-60':''}`}><input type="radio" name={question.id} disabled={paused||ended||remaining<=0} checked={answers[question.id]?.value===(i===0)} onChange={()=>save(question,{value:i===0})}/>{value}</label>) : (question.options||[]).map((option,i)=><label key={option.id||i} className={`flex cursor-pointer items-center gap-3 rounded-xl border p-4 ${paused||ended?'opacity-60':''}`}><input type={question.kind==='multiple_mcq'?'checkbox':'radio'} name={question.id} disabled={paused||ended||remaining<=0} checked={question.kind==='multiple_mcq'?(answers[question.id]?.selected_option_ids||[]).includes(option.id):answers[question.id]?.selected_option_ids?.[0]===option.id} onChange={(e)=>{if(question.kind==='multiple_mcq'){const old=answers[question.id]?.selected_option_ids||[];save(question,{selected_option_ids:e.target.checked?[...old,option.id]:old.filter((x:string)=>x!==option.id)});}else save(question,{selected_option_ids:[option.id]});}}/><span>{option.text}</span></label>)}</div><div className="mt-8 flex flex-wrap justify-between gap-3"><button className="rounded-xl border px-4 py-2 font-bold" disabled={index===0} onClick={()=>setIndex((i)=>i-1)}>Previous</button><div className="flex gap-2"><button className="rounded-xl border px-4 py-2 font-bold" onClick={submit} disabled={busy||paused||ended}>{busy?'Submitting…':'Submit exam'}</button><button className="btn" disabled={index===questions.length-1} onClick={()=>setIndex((i)=>i+1)}>Next</button></div></div></div> : <p className="mt-8">Loading questions…</p>}
    </main>;
  }

  return <main className="container-shell py-12">{exam ? <div className="card mx-auto max-w-2xl p-8"><p className="text-xs font-bold uppercase tracking-widest text-brand">{exam.subject}</p><h1 className="mt-3 text-3xl font-black">{exam.title}</h1><p className="mt-4 leading-7 text-slate-600">{exam.description}</p><div className="mt-6 flex flex-wrap gap-5 text-sm text-slate-500"><span>{Math.round(exam.duration_seconds/60)} minutes</span><span className="capitalize">{exam.status}</span>{exam.scheduled_start_at&&<span>Scheduled: {new Date(exam.scheduled_start_at).toLocaleString()}</span>}</div>{exam.status==='live'&&<button className="btn mt-8" onClick={start}>Start examination</button>}{error&&<p className="mt-4 text-sm text-red-600">{error}</p>}</div>:<p>{error||'Loading…'}</p>}</main>;
}
