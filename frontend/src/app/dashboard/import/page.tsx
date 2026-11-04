'use client';

import { useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { api } from '@/lib/api';
import { ArrowLeft, FileUp, Loader2, CheckCircle2, AlertTriangle, BookOpen, Clock3, ListChecks, Trash2 } from 'lucide-react';

type Option = { key: string; text: string };
type ImportedQuestion = {
  number: number;
  kind: 'mcq' | 'multiple_mcq' | 'true_false' | 'short_answer';
  prompt: string;
  options: Option[];
  answer_key: Record<string, unknown>;
  marks: number;
  negative_marks: number;
  confidence: number;
  needs_review: boolean;
  answer_key_missing: boolean;
  warnings: string[];
  included?: boolean;
};
type Preview = {
  filename: string;
  pages: number;
  ocr_used: boolean;
  ocr_engine?: string;
  metadata: {
    subject: string | null;
    chapter: string | null;
    exam_title: string | null;
    set_name: string | null;
    declared_question_count: number | null;
    duration_minutes: number | null;
    total_marks: number | null;
  };
  questions: ImportedQuestion[];
  question_count_detected: number;
  warnings: string[];
  extraction_note: string;
};

export default function ImportExamPage() {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [busy, setBusy] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [title, setTitle] = useState('');
  const [subject, setSubject] = useState('');
  const [chapter, setChapter] = useState('');
  const [setName, setSetName] = useState('');
  const [duration, setDuration] = useState('60');
  const [accessMode, setAccessMode] = useState<'all_students' | 'selected_students'>('all_students');
  const [maxAttempts, setMaxAttempts] = useState('1');
  const [publishImmediately, setPublishImmediately] = useState(false);
  const [questions, setQuestions] = useState<ImportedQuestion[]>([]);

  const includedCount = useMemo(() => questions.filter((q) => q.included !== false).length, [questions]);

  async function extract() {
    if (!file) return;
    setBusy(true); setError(''); setPreview(null); setQuestions([]);
    try {
      const form = new FormData();
      form.append('file', file);
      const result = await api<Preview>('/imports/pdf/preview', { method: 'POST', body: form });
      setPreview(result);
      setSubject(result.metadata.subject || 'General');
      setChapter(result.metadata.chapter || '');
      setSetName(result.metadata.set_name || '');
      setDuration(String(result.metadata.duration_minutes || 60));
      const generatedTitle = [result.metadata.exam_title, result.metadata.subject, result.metadata.chapter, result.metadata.set_name].filter(Boolean).join(' — ');
      setTitle(generatedTitle || file.name.replace(/\.pdf$/i, ''));
      setQuestions(result.questions.map((q) => ({ ...q, included: true })));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not extract this PDF.');
    } finally { setBusy(false); }
  }

  function updateQuestion(index: number, patch: Partial<ImportedQuestion>) {
    setQuestions((current) => current.map((q, i) => i === index ? { ...q, ...patch } : q));
  }
  function updateOption(qIndex: number, oIndex: number, text: string) {
    setQuestions((current) => current.map((q, i) => i === qIndex ? { ...q, options: q.options.map((o, j) => j === oIndex ? { ...o, text } : o) } : q));
  }
  function addOption(qIndex: number) {
    setQuestions((current) => current.map((q, i) => i === qIndex && q.options.length < 6 ? { ...q, options: [...q.options, { key: String.fromCharCode(65 + q.options.length), text: '' }] } : q));
  }
  function removeOption(qIndex: number, oIndex: number) {
    setQuestions((current) => current.map((q, i) => i === qIndex ? { ...q, options: q.options.filter((_, j) => j !== oIndex).map((o, j) => ({ ...o, key: String.fromCharCode(65 + j) })) } : q));
  }
  function setCorrectOption(qIndex: number, optionKey: string, multiple: boolean) {
    const question = questions[qIndex];
    const current = Array.isArray(question.answer_key.selected_option_ids) ? question.answer_key.selected_option_ids as string[] : [];
    const selected = multiple ? (current.includes(optionKey) ? current.filter((x) => x !== optionKey) : [...current, optionKey]) : [optionKey];
    updateQuestion(qIndex, { answer_key: { ...question.answer_key, selected_option_ids: selected } });
  }

  async function createExam() {
    if (!preview) return;
    const selected = questions.filter((q) => q.included !== false);
    if (!selected.length) { setError('Select at least one question.'); return; }
    if (selected.some((q) => !q.prompt.trim())) { setError('Every included question needs question text.'); return; }
    setSaving(true); setError('');
    try {
      await api<{ id: string }>('/imports/pdf/create-exam', {
        method: 'POST',
        body: JSON.stringify({
          title, subject, chapter: chapter || null, set_name: setName || null,
          duration_minutes: Number(duration), declared_question_count: preview.metadata.declared_question_count,
          access_mode: accessMode, max_attempts: Number(maxAttempts), publish_immediately: publishImmediately, source_file_name: preview.filename,
          questions: selected.map(({ number, kind, prompt, options, answer_key, marks, negative_marks }) => ({ number, kind, prompt, options, answer_key, marks, negative_marks })),
        }),
      });
      router.push('/dashboard');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not create the examination.');
    } finally { setSaving(false); }
  }

  return <main className="container-shell py-9">
    <Link href="/dashboard" className="inline-flex items-center gap-2 text-sm font-bold text-slate-500 hover:text-brand"><ArrowLeft size={16}/> Back to dashboard</Link>
    <div className="mt-6 max-w-4xl"><p className="text-sm font-bold uppercase tracking-wider text-brand">PDF exam builder</p><h1 className="mt-2 text-3xl font-black tracking-tight">Turn a question paper into an exam</h1><p className="mt-3 text-slate-600">Upload a PDF. ExamFlow will identify the subject, chapter, set, duration and question blocks, then let you review and correct everything before saving.</p></div>

    <section className="card mt-7 p-5 md:p-7">
      <div className="flex items-start gap-3"><div className="rounded-xl bg-blue-50 p-3 text-brand"><FileUp size={22}/></div><div><h2 className="font-extrabold">1. Upload your PDF</h2><p className="mt-1 text-sm text-slate-500">PDF only · Maximum 15 MB · Up to 30 pages</p></div></div>
      <div className="mt-5 flex flex-col gap-3 sm:flex-row"><input type="file" accept="application/pdf,.pdf" className="field flex-1" onChange={(e) => { setFile(e.target.files?.[0] || null); setPreview(null); setQuestions([]); setError(''); }}/><button className="btn min-w-36" disabled={!file || busy} onClick={extract}>{busy ? <><Loader2 className="mr-2 animate-spin" size={17}/>Extracting</> : 'Extract questions'}</button></div>
      {file && <p className="mt-2 text-xs text-slate-500">Selected: {file.name} · {(file.size / 1024 / 1024).toFixed(2)} MB</p>}
      {error && <p role="alert" className="mt-4 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</p>}
    </section>

    {preview && <>
      <section className="card mt-6 p-5 md:p-7">
        <div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-xl font-black">2. Review detected exam information</h2><p className="mt-1 text-sm text-slate-500">{preview.filename} · {preview.pages} pages · {preview.ocr_used ? `OCR used${preview.ocr_engine ? ` · ${preview.ocr_engine}` : ''}` : 'Embedded text extracted'}</p></div><span className="rounded-full bg-emerald-50 px-3 py-1.5 text-xs font-bold text-emerald-700"><CheckCircle2 className="mr-1 inline" size={14}/>{preview.question_count_detected} questions detected</span></div>
        {preview.warnings.length > 0 && <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-4"><p className="font-bold text-amber-900"><AlertTriangle className="mr-2 inline" size={16}/>Review required</p><ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-amber-900">{preview.warnings.map((w, i) => <li key={i}>{w}</li>)}</ul></div>}
        <div className="mt-5 grid gap-4 md:grid-cols-2">
          <label className="text-sm font-bold">Exam title<input className="field mt-2 font-normal" value={title} onChange={(e) => setTitle(e.target.value)}/></label>
          <label className="text-sm font-bold">Subject / paper<input className="field mt-2 font-normal" value={subject} onChange={(e) => setSubject(e.target.value)}/></label>
          <label className="text-sm font-bold">Chapter<input className="field mt-2 font-normal" value={chapter} onChange={(e) => setChapter(e.target.value)}/></label>
          <label className="text-sm font-bold">Set<input className="field mt-2 font-normal" value={setName} onChange={(e) => setSetName(e.target.value)}/></label>
          <label className="text-sm font-bold">Duration (minutes)<input className="field mt-2 font-normal" type="number" min="1" max="1440" value={duration} onChange={(e) => setDuration(e.target.value)}/></label>
          <label className="text-sm font-bold">Maximum attempts<input className="field mt-2 font-normal" type="number" min="1" max="20" value={maxAttempts} onChange={(e) => setMaxAttempts(e.target.value)}/></label>
          <label className="text-sm font-bold">Participation access<select className="field mt-2 font-normal" value={accessMode} onChange={(e) => setAccessMode(e.target.value as typeof accessMode)}><option value="all_students">All registered students</option><option value="selected_students">Selected students only</option></select></label>
          <label className="flex items-center gap-3 rounded-xl border border-slate-200 p-3 text-sm"><input type="checkbox" checked={publishImmediately} onChange={(e) => setPublishImmediately(e.target.checked)}/><span><strong>Publish immediately</strong><span className="block text-xs font-normal text-slate-500">Requires a correct answer key for every question.</span></span></label>
          <div className="flex items-end gap-3 rounded-xl bg-slate-50 p-3 text-sm"><BookOpen className="text-brand"/><span>{preview.metadata.declared_question_count ?? 'Not stated'} questions declared in PDF</span><Clock3 className="ml-auto text-brand"/><span>{preview.metadata.duration_minutes ?? '—'} min detected</span></div>
        </div>
      </section>

      <section className="card mt-6 p-5 md:p-7">
        <div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-xl font-black">3. Review and edit questions</h2><p className="mt-1 text-sm text-slate-500">Correct extraction mistakes, remove unwanted questions and check options.</p></div><span className="rounded-full bg-slate-100 px-3 py-1.5 text-xs font-bold text-slate-700"><ListChecks className="mr-1 inline" size={14}/>{includedCount} / {questions.length} included</span></div>
        <div className="mt-4 rounded-xl border border-blue-100 bg-blue-50 p-3 text-sm text-blue-900">{preview.extraction_note} No correct answers are guessed. Set the correct options or accepted answers here. If any answer key is missing, the examination remains a draft and cannot be published until the keys are completed.</div>
        <div className="mt-4 space-y-3">{questions.map((q, index) => <details key={`${q.number}-${index}`} className={`rounded-xl border ${q.included === false ? 'border-slate-200 bg-slate-50 opacity-60' : 'border-slate-200 bg-white'}`} open={index < 2}>
          <summary className="flex cursor-pointer list-none flex-wrap items-center gap-3 p-4"><input type="checkbox" checked={q.included !== false} onChange={(e) => updateQuestion(index, { included: e.target.checked })} onClick={(e) => e.stopPropagation()} aria-label={`Include question ${q.number}`}/><span className="font-extrabold">Question {q.number}</span><span className="rounded-full bg-slate-100 px-2 py-1 text-xs text-slate-600">{q.options.length} options</span><span className={`ml-auto text-xs font-bold ${q.confidence < 0.7 ? 'text-amber-700' : 'text-emerald-700'}`}>{Math.round(q.confidence * 100)}% structure score</span></summary>
          <div className="space-y-3 border-t border-slate-100 p-4"><label className="block text-sm font-bold">Question text<textarea className="field mt-2 min-h-24 font-normal" value={q.prompt} onChange={(e) => updateQuestion(index, { prompt: e.target.value })}/></label>
            <div className="grid gap-3 md:grid-cols-2">{q.options.map((option, optionIndex) => <div key={option.key} className="rounded-lg border border-slate-100 p-3 text-sm font-bold"><div className="flex items-center gap-2"><span>Option {option.key}</span>{q.kind === 'multiple_mcq' ? <label className="ml-auto flex items-center gap-1 text-xs font-medium text-emerald-700"><input type="checkbox" checked={Array.isArray(q.answer_key.selected_option_ids) && (q.answer_key.selected_option_ids as string[]).includes(option.key)} onChange={() => setCorrectOption(index, option.key, true)}/>Correct</label> : q.kind === 'mcq' ? <label className="ml-auto flex items-center gap-1 text-xs font-medium text-emerald-700"><input type="radio" name={`correct-${q.number}`} checked={Array.isArray(q.answer_key.selected_option_ids) && (q.answer_key.selected_option_ids as string[]).includes(option.key)} onChange={() => setCorrectOption(index, option.key, false)}/>Correct</label> : null}</div><textarea className="field mt-2 min-h-14 font-normal" value={option.text} onChange={(e) => updateOption(index, optionIndex, e.target.value)}/><button type="button" className="mt-1 text-xs font-semibold text-red-600" onClick={() => removeOption(index, optionIndex)}>Remove option</button></div>)}</div>
            {q.options.length < 6 && <button type="button" className="rounded-lg border border-slate-200 px-3 py-2 text-xs font-bold text-slate-600" onClick={() => addOption(index)}>+ Add option</button>}
            {q.kind === 'true_false' && <label className="block max-w-xs text-sm font-bold">Correct answer<select className="field mt-1 font-normal" value={q.answer_key.value === true ? 'true' : q.answer_key.value === false ? 'false' : ''} onChange={(e) => updateQuestion(index, { answer_key: { ...q.answer_key, value: e.target.value === '' ? null : e.target.value === 'true' } })}><option value="">Not set</option><option value="true">True</option><option value="false">False</option></select></label>}
            {q.kind === 'short_answer' && <label className="block text-sm font-bold">Accepted answers (comma separated)<input className="field mt-1 font-normal" value={Array.isArray(q.answer_key.accepted_answers) ? (q.answer_key.accepted_answers as string[]).join(', ') : ''} onChange={(e) => updateQuestion(index, { answer_key: { ...q.answer_key, accepted_answers: e.target.value.split(',').map((x) => x.trim()).filter(Boolean) } })}/></label>}
            {q.warnings.length > 0 && <p className="text-xs text-amber-700">{q.warnings.join(' ')}</p>}
            <div className="flex flex-wrap items-center gap-3"><label className="text-sm text-slate-600">Question type<select className="field mt-1" value={q.kind} onChange={(e) => updateQuestion(index, { kind: e.target.value as ImportedQuestion['kind'] })}><option value="mcq">Single-correct MCQ</option><option value="multiple_mcq">Multiple-correct MCQ</option><option value="true_false">True / False</option><option value="short_answer">Short answer</option></select></label><label className="text-sm text-slate-600">Marks<input className="field mt-1 w-24" type="number" min="0" step="0.25" value={q.marks} onChange={(e) => updateQuestion(index, { marks: Number(e.target.value) })}/></label><label className="text-sm text-slate-600">Negative marks<input className="field mt-1 w-24" type="number" min="0" step="0.25" value={q.negative_marks} onChange={(e) => updateQuestion(index, { negative_marks: Number(e.target.value) })}/></label><button type="button" className="ml-auto inline-flex items-center gap-1 text-sm font-bold text-red-600" onClick={() => updateQuestion(index, { included: false })}><Trash2 size={15}/>Exclude</button></div>
          </div>
        </details>)}</div>
      </section>
      <div className="sticky bottom-3 z-10 mt-6 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white/95 p-4 shadow-xl backdrop-blur"><div><p className="font-extrabold">Ready to create?</p><p className="text-xs text-slate-500">{includedCount} reviewed questions · answer keys remain unset</p></div><button className="btn min-w-48" disabled={saving || !includedCount || !title.trim() || !subject.trim()} onClick={createExam}>{saving ? <><Loader2 className="mr-2 animate-spin" size={17}/>Creating exam</> : 'Create examination'}</button></div>
    </>}
  </main>;
}
