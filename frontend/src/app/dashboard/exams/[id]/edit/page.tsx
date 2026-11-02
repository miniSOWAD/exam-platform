'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { api } from '@/lib/api';
import { ArrowLeft, Save, Loader2, AlertTriangle } from 'lucide-react';

type Option = { id?: string; key?: string; text: string };
type Question = {
  id: string; kind: 'mcq' | 'multiple_mcq' | 'true_false' | 'short_answer'; prompt: string;
  options: Option[]; answer_key: Record<string, unknown>; marks: number; negative_marks: number; position: number;
};
type Exam = { id: string; title: string; subject: string; status: string };

export default function EditExamQuestionsPage() {
  const { id } = useParams<{ id: string }>();
  const [exam, setExam] = useState<Exam | null>(null);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<string | null>(null);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  useEffect(() => {
    Promise.all([api<Exam>(`/exams/${id}`), api<Question[]>(`/exams/${id}/questions/manage`)]).then(([e, q]) => {
      setExam(e); setQuestions(q);
    }).catch((err) => setError(err instanceof Error ? err.message : 'Could not load questions.')).finally(() => setLoading(false));
  }, [id]);

  function patchQuestion(index: number, patch: Partial<Question>) {
    setQuestions((current) => current.map((q, i) => i === index ? { ...q, ...patch } : q));
  }
  function optionId(option: Option, index: number) { return String(option.id || option.key || index); }
  function setCorrect(index: number, key: string, multiple: boolean) {
    const q = questions[index];
    const current = Array.isArray(q.answer_key.selected_option_ids) ? q.answer_key.selected_option_ids as string[] : [];
    const selected = multiple ? (current.includes(key) ? current.filter((x) => x !== key) : [...current, key]) : [key];
    patchQuestion(index, { answer_key: { ...q.answer_key, selected_option_ids: selected } });
  }
  function addOption(index: number) {
    const q = questions[index];
    patchQuestion(index, { options: [...q.options, { id: `new-${q.options.length}-${Date.now()}`, text: '' }] });
  }
  function removeOption(index: number, optionIndex: number) {
    const q = questions[index];
    patchQuestion(index, { options: q.options.filter((_, i) => i !== optionIndex) });
  }
  async function saveQuestion(q: Question) {
    setSaving(q.id); setError(''); setMessage('');
    try {
      await api(`/exams/${id}/questions/${q.id}`, { method: 'PATCH', body: JSON.stringify({
        kind: q.kind, prompt: q.prompt, options: q.options, answer_key: q.answer_key,
        marks: q.marks, negative_marks: q.negative_marks, position: q.position,
      }) });
      setMessage(`Question ${q.position + 1} saved.`);
    } catch (err) { setError(err instanceof Error ? err.message : 'Could not save question.'); }
    finally { setSaving(null); }
  }

  if (loading) return <main className="container-shell py-20">Loading question editor…</main>;
  return <main className="container-shell py-9">
    <Link href="/dashboard" className="inline-flex items-center gap-2 text-sm font-bold text-slate-500 hover:text-brand"><ArrowLeft size={16}/> Back to dashboard</Link>
    <div className="mt-6"><p className="text-sm font-bold uppercase tracking-wider text-brand">Question management</p><h1 className="mt-2 text-3xl font-black">{exam?.title || 'Edit examination'}</h1><p className="mt-2 text-slate-500">Correct OCR mistakes, update options and enter answer keys. Questions lock once an attempt begins.</p></div>
    {exam && <div className="mt-4 flex flex-wrap items-center gap-3 text-sm"><span className="rounded-full bg-slate-100 px-3 py-1 font-bold">{exam.subject}</span><span className="rounded-full bg-slate-100 px-3 py-1 font-bold capitalize">{exam.status}</span></div>}
    {error && <p role="alert" className="mt-4 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</p>}
    {message && <p className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">{message}</p>}
    <div className="mt-6 space-y-4">{questions.map((q, index) => <section key={q.id} className="card p-5">
      <div className="flex flex-wrap items-center justify-between gap-3"><h2 className="font-black">Question {index + 1}</h2><button className="btn" disabled={saving === q.id} onClick={() => saveQuestion(q)}>{saving === q.id ? <><Loader2 className="mr-2 animate-spin" size={16}/>Saving</> : <><Save className="mr-2" size={16}/>Save question</>}</button></div>
      <label className="mt-4 block text-sm font-bold">Question text<textarea className="field mt-2 min-h-24 font-normal" value={q.prompt} onChange={(e) => patchQuestion(index, { prompt: e.target.value })}/></label>
      <label className="mt-3 block max-w-xs text-sm font-bold">Question type<select className="field mt-2 font-normal" value={q.kind} onChange={(e) => patchQuestion(index, { kind: e.target.value as Question['kind'] })}><option value="mcq">Single-correct MCQ</option><option value="multiple_mcq">Multiple-correct MCQ</option><option value="true_false">True / False</option><option value="short_answer">Short answer</option></select></label>
      {q.kind !== 'short_answer' && q.kind !== 'true_false' && <><div className="mt-4 grid gap-3 md:grid-cols-2">{q.options.map((o, oi) => <div key={optionId(o, oi)} className="rounded-xl border border-slate-100 p-3"><div className="flex items-center justify-between text-sm font-bold"><span>Option {String.fromCharCode(65 + oi)}</span>{q.kind === 'mcq' ? <label className="flex items-center gap-1 text-xs text-emerald-700"><input type="radio" name={`answer-${q.id}`} checked={Array.isArray(q.answer_key.selected_option_ids) && (q.answer_key.selected_option_ids as string[]).includes(optionId(o, oi))} onChange={() => setCorrect(index, optionId(o, oi), false)}/>Correct</label> : <label className="flex items-center gap-1 text-xs text-emerald-700"><input type="checkbox" checked={Array.isArray(q.answer_key.selected_option_ids) && (q.answer_key.selected_option_ids as string[]).includes(optionId(o, oi))} onChange={() => setCorrect(index, optionId(o, oi), true)}/>Correct</label>}</div><textarea className="field mt-2 min-h-14" value={o.text} onChange={(e) => patchQuestion(index, { options: q.options.map((item, j) => j === oi ? { ...item, text: e.target.value } : item) })}/><button type="button" className="mt-1 text-xs font-semibold text-red-600" onClick={() => removeOption(index, oi)}>Remove option</button></div>)}</div><button type="button" className="mt-3 rounded-lg border border-slate-200 px-3 py-2 text-xs font-bold text-slate-600" onClick={() => addOption(index)}>+ Add option</button></>}
      {q.kind === 'true_false' && <label className="mt-4 block max-w-xs text-sm font-bold">Correct answer<select className="field mt-2 font-normal" value={q.answer_key.value === true ? 'true' : q.answer_key.value === false ? 'false' : ''} onChange={(e) => patchQuestion(index, { answer_key: { ...q.answer_key, value: e.target.value === '' ? null : e.target.value === 'true' } })}><option value="">Not set</option><option value="true">True</option><option value="false">False</option></select></label>}
      {q.kind === 'short_answer' && <label className="mt-4 block text-sm font-bold">Accepted answers (comma separated)<input className="field mt-2 font-normal" value={Array.isArray(q.answer_key.accepted_answers) ? (q.answer_key.accepted_answers as string[]).join(', ') : ''} onChange={(e) => patchQuestion(index, { answer_key: { ...q.answer_key, accepted_answers: e.target.value.split(',').map((x) => x.trim()).filter(Boolean) } })}/></label>}
      <div className="mt-4 flex flex-wrap items-end gap-3"><label className="text-sm font-bold">Marks<input className="field mt-1 w-28 font-normal" type="number" min="0" step="0.25" value={q.marks} onChange={(e) => patchQuestion(index, { marks: Number(e.target.value) })}/></label><label className="text-sm font-bold">Negative marks<input className="field mt-1 w-28 font-normal" type="number" min="0" step="0.25" value={q.negative_marks} onChange={(e) => patchQuestion(index, { negative_marks: Number(e.target.value) })}/></label>{!q.answer_key || Object.keys(q.answer_key).length === 0 ? <span className="text-xs font-semibold text-amber-700"><AlertTriangle className="mr-1 inline" size={14}/>Answer key not set</span> : null}</div>
    </section>)}</div>
  </main>;
}
