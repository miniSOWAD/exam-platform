'use client';

import { FormEvent, useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { api } from '@/lib/api';
import {
  LogOut, BookOpen, Users, Clock3, Plus, FileUp, Globe2, CalendarClock,
  Play, Pause, RotateCcw, Square, FileCheck2, FileText, X, Loader2,
  AlertTriangle, CheckCircle2, Upload,
} from 'lucide-react';

type User = { id: string; email: string; full_name: string; role: string };
type Exam = {
  id: string; title: string; subject: string; chapter?: string | null; set_name?: string | null;
  status: string; duration_seconds: number; question_count: number;
  scheduled_start_at?: string | null; scheduled_end_at?: string | null; time_extension_seconds?: number;
};
type AnswerPreviewRow = {
  question_number: number;
  option_labels: string[];
  option_indices: number[];
  status: 'ready' | 'out_of_range' | 'invalid_option' | 'conflict' | 'unsupported_question_type' | string;
  reason?: string | null;
  current_option_labels: string[];
};
type AnswerPreview = {
  filename: string;
  source_type: 'pdf' | 'txt';
  ocr_used: boolean;
  ocr_engine: string;
  pages: number;
  question_count: number;
  detected_count: number;
  ready_count: number;
  answers: AnswerPreviewRow[];
  missing_question_numbers: number[];
};
type AnswerApplyResult = {
  applied_count: number;
  updated_question_numbers: number[];
  unanswered_question_numbers: number[];
  message: string;
};

function dateLabel(value?: string | null) { return value ? new Date(value).toLocaleString() : 'Not scheduled'; }
function statusLabel(status: string) {
  if (status === 'ready') return 'Ready';
  if (status === 'out_of_range') return 'Question not found';
  if (status === 'invalid_option') return 'Invalid option';
  if (status === 'conflict') return 'Conflicting answers';
  if (status === 'unsupported_question_type') return 'Not an MCQ';
  return status;
}

export default function Dashboard() {
  const [user, setUser] = useState<User | null>(null);
  const [exams, setExams] = useState<Exam[]>([]);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [title, setTitle] = useState('');
  const [subject, setSubject] = useState('General');
  const [duration, setDuration] = useState('60');
  const [creating, setCreating] = useState(false);
  const [answerExam, setAnswerExam] = useState<Exam | null>(null);
  const [answerFile, setAnswerFile] = useState<File | null>(null);
  const [answerPreview, setAnswerPreview] = useState<AnswerPreview | null>(null);
  const [answerError, setAnswerError] = useState('');
  const [answerBusy, setAnswerBusy] = useState(false);
  const [answerApplying, setAnswerApplying] = useState(false);
  const router = useRouter();

  async function refreshExams() { setExams(await api<Exam[]>('/exams')); }
  useEffect(() => {
    let active = true;
    Promise.all([api<User>('/auth/me'), api<Exam[]>('/exams')])
      .then(([u, e]) => { if (active) { setUser(u); setExams(e); } })
      .catch(() => router.replace('/login'));
    return () => { active = false; };
  }, [router]);

  async function logout() { await api('/auth/logout', { method: 'POST' }); router.replace('/'); }
  async function controlExam(id: string, action: string) {
    setError(''); setNotice('');
    try { await api(`/exams/${id}/control/${action}`, { method: 'POST' }); await refreshExams(); }
    catch (err) { setError(err instanceof Error ? err.message : 'Could not update examination status.'); }
  }
  async function publishExam(id: string) {
    setError(''); setNotice('');
    try { await api(`/exams/${id}/publish`, { method: 'POST' }); await refreshExams(); }
    catch (err) { setError(err instanceof Error ? err.message : 'Could not publish exam'); }
  }
  async function createExam(event: FormEvent) {
    event.preventDefault(); setCreating(true); setError(''); setNotice('');
    try {
      await api('/exams', { method: 'POST', body: JSON.stringify({
        title, subject, duration_seconds: Number(duration) * 60, description: '',
        access_mode: 'all_students', max_attempts: 1, pass_marks: 0,
      }) });
      setTitle(''); await refreshExams();
    } catch (err) { setError(err instanceof Error ? err.message : 'Could not create exam'); }
    finally { setCreating(false); }
  }

  function openAnswerImporter(exam: Exam) {
    setAnswerExam(exam); setAnswerFile(null); setAnswerPreview(null); setAnswerError('');
    setError(''); setNotice('');
  }
  function closeAnswerImporter() {
    if (answerBusy || answerApplying) return;
    setAnswerExam(null); setAnswerFile(null); setAnswerPreview(null); setAnswerError('');
  }
  async function previewAnswerKey(event: FormEvent) {
    event.preventDefault();
    if (!answerExam || !answerFile) { setAnswerError('Choose a PDF or TXT answer-key file first.'); return; }
    setAnswerBusy(true); setAnswerError(''); setAnswerPreview(null);
    try {
      const form = new FormData();
      form.append('file', answerFile);
      const result = await api<AnswerPreview>(`/exams/${answerExam.id}/answer-key/preview`, {
        method: 'POST', body: form,
      });
      setAnswerPreview(result);
    } catch (err) {
      setAnswerError(err instanceof Error ? err.message : 'Could not read the answer-key file.');
    } finally { setAnswerBusy(false); }
  }
  async function applyAnswerKey() {
    if (!answerExam || !answerPreview) return;
    const ready = answerPreview.answers.filter((item) => item.status === 'ready');
    if (!ready.length) { setAnswerError('There are no valid answers to apply.'); return; }
    setAnswerApplying(true); setAnswerError('');
    try {
      const result = await api<AnswerApplyResult>(`/exams/${answerExam.id}/answer-key/apply`, {
        method: 'POST',
        body: JSON.stringify({ answers: ready.map(({ question_number, option_indices }) => ({ question_number, option_indices })) }),
      });
      await refreshExams();
      const remaining = result.unanswered_question_numbers.length;
      setNotice(remaining
        ? `Imported ${result.applied_count} answer(s) into “${answerExam.title}”. ${remaining} question(s) still need answers.`
        : `Successfully imported all ${result.applied_count} answer(s) into “${answerExam.title}”.`);
      setAnswerExam(null); setAnswerFile(null); setAnswerPreview(null);
    } catch (err) {
      setAnswerError(err instanceof Error ? err.message : 'Could not apply the answer key.');
    } finally { setAnswerApplying(false); }
  }

  if (!user) return <main className="container-shell py-20">Loading workspace…</main>;

  return <>
    <main className="container-shell py-10">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div><p className="text-sm font-bold text-brand">{user.role.toUpperCase()} WORKSPACE</p><h1 className="mt-1 text-3xl font-black">Welcome, {user.full_name}</h1><p className="mt-2 text-slate-500">Manage examinations, schedules and student progress.</p></div>
        <div className="flex flex-wrap gap-2">
          {user.role === 'admin' && <Link href="/dashboard/site-content" className="rounded-xl border border-teal-100 bg-teal-50 px-4 py-2 text-sm font-bold text-teal-800"><Globe2 className="mr-2 inline" size={16}/>Manage website</Link>}
          <button onClick={logout} className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-bold"><LogOut className="mr-2 inline" size={16}/>Sign out</button>
        </div>
      </div>

      <div className="mt-8 grid gap-4 md:grid-cols-3">
        <div className="card p-5"><BookOpen className="text-brand"/><p className="mt-4 text-sm text-slate-500">Available exams</p><p className="text-3xl font-black">{exams.length}</p></div>
        <div className="card p-5"><Users className="text-brand"/><p className="mt-4 text-sm text-slate-500">Your account</p><p className="text-xl font-black capitalize">{user.role}</p></div>
        <div className="card p-5"><Clock3 className="text-brand"/><p className="mt-4 text-sm text-slate-500">Exam access</p><p className="text-xl font-black">{user.role === 'student' ? 'Assigned exams' : 'Management'}</p></div>
      </div>

      <div className="mt-10 flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-xl font-black">Examinations</h2>
        {user.role !== 'student' && <div className="flex gap-2"><Link className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-bold" href="/dashboard/import"><FileUp className="mr-2 inline" size={16}/>Import PDF</Link><Link className="btn" href="#create"><Plus size={17} className="mr-2"/>Create exam</Link></div>}
      </div>
      {error && <p role="alert" className="mt-4 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</p>}
      {notice && <p role="status" className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">{notice}</p>}

      {user.role !== 'student' && <form onSubmit={createExam} id="create" className="card mt-5 grid gap-3 p-5 md:grid-cols-[2fr_1fr_1fr_auto]">
        <input className="field" placeholder="Exam title" required value={title} onChange={(e) => setTitle(e.target.value)}/>
        <input className="field" placeholder="Subject" value={subject} onChange={(e) => setSubject(e.target.value)}/>
        <input className="field" type="number" min="1" max="1440" value={duration} onChange={(e) => setDuration(e.target.value)}/>
        <button className="btn" disabled={creating}>{creating ? 'Creating…' : 'Create'}</button>
      </form>}

      <div className="mt-4 grid gap-4 md:grid-cols-2">
        {exams.map((exam) => <article key={exam.id} className="card p-5">
          <div className="flex justify-between gap-3"><span className="text-xs font-bold uppercase tracking-wider text-brand">{exam.subject}</span><span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-bold capitalize">{exam.status.replace('_', ' ')}</span></div>
          <h3 className="mt-3 text-lg font-extrabold">{exam.title}</h3>
          <p className="mt-2 text-sm text-slate-500">{exam.chapter ? `${exam.chapter} · ` : ''}{exam.set_name ? `${exam.set_name} · ` : ''}{exam.question_count} questions · {Math.round(exam.duration_seconds / 60)} minutes</p>
          {exam.scheduled_start_at && <p className="mt-2 text-xs text-slate-500"><CalendarClock className="mr-1 inline" size={13}/>Starts: {dateLabel(exam.scheduled_start_at)}</p>}
          <div className="mt-5 flex flex-wrap items-center gap-x-4 gap-y-3">
            <Link href={`/exams/${exam.id}`} className="text-sm font-bold text-brand">Open exam →</Link>
            {user.role !== 'student' && <>
              <Link href={`/dashboard/exams/${exam.id}/edit`} className="text-sm font-bold text-slate-700">Edit questions</Link>
              <button type="button" onClick={() => openAnswerImporter(exam)} disabled={['live', 'paused', 'ended', 'results_published', 'archived'].includes(exam.status)} title={['live', 'paused', 'ended', 'results_published', 'archived'].includes(exam.status) ? 'Answer keys are locked after an exam starts.' : 'Upload a numbered PDF or TXT answer key'} className="inline-flex items-center gap-1 text-sm font-bold text-indigo-700 hover:text-indigo-900 disabled:cursor-not-allowed disabled:opacity-40"><FileCheck2 size={15}/>Add Answers / Modify Answers</button>
              <Link href={`/dashboard/exams/${exam.id}/schedule`} className="text-sm font-bold text-teal-700">Schedule & timing</Link>
              {exam.status === 'draft' && <button onClick={() => publishExam(exam.id)} className="text-sm font-bold text-emerald-700">Publish exam</button>}
              {exam.status === 'published' && <button onClick={() => controlExam(exam.id, 'start')} className="text-sm font-bold text-emerald-700"><Play className="mr-1 inline" size={13}/>Start</button>}
              {exam.status === 'live' && <button onClick={() => controlExam(exam.id, 'pause')} className="text-sm font-bold text-amber-700"><Pause className="mr-1 inline" size={13}/>Pause</button>}
              {exam.status === 'paused' && <button onClick={() => controlExam(exam.id, 'resume')} className="text-sm font-bold text-emerald-700"><RotateCcw className="mr-1 inline" size={13}/>Resume</button>}
              {['live', 'paused'].includes(exam.status) && <button onClick={() => controlExam(exam.id, 'end')} className="text-sm font-bold text-red-700"><Square className="mr-1 inline" size={12}/>End</button>}
            </>}
          </div>
        </article>)}
      </div>
      {exams.length === 0 && <div className="card mt-4 p-10 text-center text-slate-500">No examinations are available yet.</div>}
    </main>

    {answerExam && <div className="fixed inset-0 z-[100] flex items-center justify-center overflow-y-auto bg-slate-950/50 p-4" onMouseDown={(event) => { if (event.target === event.currentTarget) closeAnswerImporter(); }}>
      <section role="dialog" aria-modal="true" aria-labelledby="answer-import-title" className="my-auto max-h-[92vh] w-full max-w-3xl overflow-y-auto rounded-2xl border border-slate-200 bg-white p-5 shadow-2xl sm:p-7">
        <div className="flex items-start justify-between gap-4">
          <div><p className="text-xs font-bold uppercase tracking-wider text-brand">Bulk answer-key import</p><h2 id="answer-import-title" className="mt-1 text-xl font-black">Add Answers / Modify Answers</h2><p className="mt-1 text-sm text-slate-500">{answerExam.title}</p></div>
          <button type="button" aria-label="Close" onClick={closeAnswerImporter} disabled={answerBusy || answerApplying} className="rounded-lg p-2 text-slate-500 hover:bg-slate-100 disabled:opacity-40"><X size={20}/></button>
        </div>

        <div className="mt-5 rounded-xl border border-blue-100 bg-blue-50 p-4 text-sm text-blue-900">
          <p className="font-bold"><FileText className="mr-2 inline" size={16}/>Upload an answer-only PDF or TXT file</p>
          <p className="mt-2">Use question serials followed by the correct option, for example:</p>
          <div className="mt-2 rounded-lg bg-white px-3 py-2 font-mono text-sm">১.ক ২.খ ৩.গ ৪.ঘ</div>
          <p className="mt-1 text-xs text-blue-800">You can also write one answer per line, such as 1) A, 2) B. Bengali and English digits and option labels are supported. Serial numbers follow the current question order in this examination.</p>
        </div>

        <form onSubmit={previewAnswerKey} className="mt-5 space-y-3">
          <label className="block text-sm font-bold">Choose answer-key file
            <input type="file" accept=".pdf,.txt,application/pdf,text/plain" className="field mt-2 block w-full cursor-pointer font-normal file:mr-3 file:rounded-lg file:border-0 file:bg-slate-100 file:px-3 file:py-2 file:text-sm file:font-bold" onChange={(event) => { setAnswerFile(event.target.files?.[0] || null); setAnswerPreview(null); setAnswerError(''); }}/>
          </label>
          {answerFile && <p className="text-xs text-slate-500">Selected: {answerFile.name} · {(answerFile.size / 1024).toFixed(1)} KB</p>}
          <button type="submit" className="btn" disabled={!answerFile || answerBusy || answerApplying}>{answerBusy ? <><Loader2 className="mr-2 inline animate-spin" size={16}/>Reading answer key…</> : <><Upload className="mr-2 inline" size={16}/>Preview answers</>}</button>
        </form>

        {answerError && <p role="alert" className="mt-4 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700"><AlertTriangle className="mr-2 inline" size={15}/>{answerError}</p>}

        {answerPreview && <div className="mt-5 space-y-4">
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="rounded-xl bg-slate-50 p-3"><p className="text-xs text-slate-500">Detected entries</p><p className="text-2xl font-black">{answerPreview.detected_count}</p></div>
            <div className="rounded-xl bg-emerald-50 p-3"><p className="text-xs text-emerald-700">Ready to apply</p><p className="text-2xl font-black text-emerald-800">{answerPreview.ready_count}</p></div>
            <div className="rounded-xl bg-slate-50 p-3"><p className="text-xs text-slate-500">Exam questions</p><p className="text-2xl font-black">{answerPreview.question_count}</p></div>
          </div>
          <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500"><span>Source: {answerPreview.source_type.toUpperCase()}</span><span>·</span><span>{answerPreview.ocr_used ? `OCR used (${answerPreview.ocr_engine})` : 'Embedded text / plain text (no OCR)'}</span>{answerPreview.pages > 0 && <><span>·</span><span>{answerPreview.pages} page(s)</span></>}</div>
          {answerPreview.ocr_used && <p className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800">OCR was used. Please verify the detected option labels before applying.</p>}
          <div className="overflow-hidden rounded-xl border border-slate-200">
            <div className="flex items-center justify-between bg-slate-50 px-3 py-2"><p className="text-sm font-bold">Detected answers</p><p className="text-xs text-slate-500">Question → answer</p></div>
            <div className="max-h-64 overflow-y-auto divide-y divide-slate-100">
              {answerPreview.answers.map((item) => <div key={item.question_number} className="flex items-center justify-between gap-3 px-3 py-2 text-sm">
                <span className="font-semibold">Question {item.question_number}</span>
                {item.current_option_labels.length > 0 && <span className="text-xs text-slate-500">Current: {item.current_option_labels.join(' / ')}</span>}
                <span className="ml-auto font-bold">{item.option_labels.join(' / ')}</span>
                <span className={`min-w-28 text-right text-xs font-semibold ${item.status === 'ready' ? 'text-emerald-700' : 'text-red-700'}`}>{item.status === 'ready' ? <><CheckCircle2 className="mr-1 inline" size={13}/>{statusLabel(item.status)}</> : statusLabel(item.status)}</span>
              </div>)}
            </div>
          </div>
          {answerPreview.missing_question_numbers.length > 0 && <p className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900"><strong>Not included in this file:</strong> {answerPreview.missing_question_numbers.join(', ')}. Existing answers for these questions will remain unchanged.</p>}
          {answerPreview.answers.some((item) => item.status !== 'ready') && <p className="rounded-lg border border-red-200 bg-red-50 p-3 text-xs text-red-800">Some entries cannot be applied. They will be skipped; only entries marked Ready will be imported.</p>}
          <div className="rounded-lg border border-slate-200 p-3 text-xs text-slate-600">Importing will replace existing answer selections only for matched questions. Question text, options, marks and exam settings will not change.</div>
          <div className="flex flex-wrap justify-end gap-2 border-t border-slate-100 pt-4">
            <button type="button" className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-bold text-slate-700" onClick={() => { setAnswerPreview(null); setAnswerError(''); }} disabled={answerApplying}>Choose another file</button>
            <button type="button" className="btn" onClick={applyAnswerKey} disabled={!answerPreview.ready_count || answerApplying}>{answerApplying ? <><Loader2 className="mr-2 inline animate-spin" size={16}/>Applying answers…</> : `Apply ${answerPreview.ready_count} answer(s)`}</button>
          </div>
        </div>}
      </section>
    </div>}
  </>;
}
