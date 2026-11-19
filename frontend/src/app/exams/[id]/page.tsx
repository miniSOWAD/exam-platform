'use client';

import { ChangeEvent, FormEvent, useEffect, useMemo, useState } from 'react';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { api } from '@/lib/api';
import {
  CalendarClock, CheckCircle2, Eye, EyeOff, Loader2, LockKeyhole, Pause,
  Play, ShieldCheck, Square, Timer, UnlockKeyhole, Users, X,
} from 'lucide-react';

type Exam = {
  id: string; title: string; description: string; status: string; duration_seconds: number;
  subject: string; scheduled_start_at?: string | null; scheduled_end_at?: string | null;
  scheduled_resume_at?: string | null; question_count?: number;
  answers_public?: boolean; hide_participant_answers?: boolean;
  can_manage_answer_visibility?: boolean; can_view_answer_sheet?: boolean;
};
type User = { id: string; email: string; full_name: string; role: string };
type Question = {
  id: string; kind: string; prompt: string; options: { id: string; text: string }[];
  marks: number; position: number; answer_key?: Record<string, any>;
};
type AttemptSnapshot = {
  id: string; status: string; exam_status: string;
  answers: { question_id: string; answer: Record<string, any> }[];
  visited_question_ids?: string[];
  remaining_seconds: number; duration_seconds: number; is_admin_attempt?: boolean;
  timer_active?: boolean; scheduled_resume_at?: string | null;
  score?: number | null; max_score?: number | null; can_view_answers?: boolean;
};
type AnswerGrant = { student_id: string; full_name: string; email: string; granted_at?: string | null };
type ParticipantResult = { score: number | null; max_score: number | null; submitted_at?: string | null };

function toLocalDateTime(value?: string | null) {
  const date = value ? new Date(value) : new Date(Date.now() + 60 * 60 * 1000);
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 16);
}

function isAnswered(question: Question, answer: Record<string, any> | undefined) {
  if (!answer) return false;
  if (question.kind === 'short_answer') return Boolean(String(answer.text || '').trim());
  if (question.kind === 'true_false') return typeof answer.value === 'boolean';
  return Array.isArray(answer.selected_option_ids) && answer.selected_option_ids.length > 0;
}

export default function ExamPage() {
  const { id } = useParams<{ id: string }>();
  const search = useSearchParams();
  const attemptId = search.get('attempt');
  const answerSheetMode = search.get('answers') === '1' && !attemptId;
  const [exam, setExam] = useState<Exam | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [answers, setAnswers] = useState<Record<string, any>>({});
  const [visitedQuestionIds, setVisitedQuestionIds] = useState<string[]>([]);
  const [index, setIndex] = useState(0);
  const [remaining, setRemaining] = useState(0);
  const [examStatus, setExamStatus] = useState('');
  const [attemptStatus, setAttemptStatus] = useState('in_progress');
  const [timerActive, setTimerActive] = useState(false);
  const [isAdminAttempt, setIsAdminAttempt] = useState(false);
  const [canViewAnswers, setCanViewAnswers] = useState(false);
  const [answerSheetResult, setAnswerSheetResult] = useState<ParticipantResult | null>(null);
  const [attemptScore, setAttemptScore] = useState<number | null>(null);
  const [attemptMaxScore, setAttemptMaxScore] = useState<number | null>(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [adminBusy, setAdminBusy] = useState(false);
  const [showTimerEditor, setShowTimerEditor] = useState(false);
  const [timerMinutes, setTimerMinutes] = useState('60');
  const [showScheduleEditor, setShowScheduleEditor] = useState(false);
  const [scheduledStart, setScheduledStart] = useState('');
  const [answerGrants, setAnswerGrants] = useState<AnswerGrant[]>([]);
  const [answerGrantEmail, setAnswerGrantEmail] = useState('');
  const [answerGrantBusy, setAnswerGrantBusy] = useState(false);
  const [answerGrantError, setAnswerGrantError] = useState('');
  const [answerGrantNotice, setAnswerGrantNotice] = useState('');
  const router = useRouter();

  const isAdmin = user?.role === 'admin';
  const isModerator = user?.role === 'moderator';
  const isStaff = isAdmin || isModerator;
  const activeQuestion = questions[index];
  const paused = examStatus === 'paused';
  const ended = ['ended', 'results_published', 'archived'].includes(examStatus);
  const attemptSubmitted = attemptStatus === 'submitted';
  const revealAnswerKeys = canViewAnswers || isStaff || answerSheetMode;
  const canEdit = !answerSheetMode && (isAdminAttempt ? !attemptSubmitted : !paused && !ended && remaining > 0 && !attemptSubmitted);
  const timerLabel = timerActive ? `${Math.floor(remaining / 60)}:${String(remaining % 60).padStart(2, '0')}` : isAdminAttempt ? 'Preview' : '—:—';
  const answeredCount = questions.filter((question) => isAnswered(question, answers[question.id])).length;
  const visitedSet = useMemo(() => new Set(visitedQuestionIds), [visitedQuestionIds]);
  const visitedUnansweredCount = questions.filter((question) => visitedSet.has(question.id) && !isAnswered(question, answers[question.id])).length;
  const notVisitedCount = Math.max(0, questions.length - questions.filter((question) => visitedSet.has(question.id)).length);
  const correctIds = useMemo(() => new Set((activeQuestion?.answer_key?.selected_option_ids || []).map(String)), [activeQuestion]);

  async function loadExam() {
    const row = await api<Exam>(`/exams/${id}`);
    setExam(row);
    setExamStatus(row.status);
    return row;
  }

  async function loadAnswerGrants() {
    if (!exam?.can_manage_answer_visibility) return;
    try {
      const rows = await api<AnswerGrant[]>(`/exams/${id}/answer-access`);
      setAnswerGrants(rows || []);
    } catch (e) {
      setAnswerGrantError(e instanceof Error ? e.message : 'Could not load answer permissions.');
    }
  }

  useEffect(() => {
    let active = true;
    Promise.all([api<Exam>(`/exams/${id}`), api<User>('/auth/me')])
      .then(([loadedExam, currentUser]) => {
        if (!active) return;
        setExam(loadedExam); setExamStatus(loadedExam.status); setUser(currentUser);
        setTimerMinutes(String(Math.max(1, Math.round(loadedExam.duration_seconds / 60))));
      })
      .catch((e) => { if (active) setError(e instanceof Error ? e.message : 'Could not load the examination.'); });
    return () => { active = false; };
  }, [id]);

  useEffect(() => {
    if (exam?.can_manage_answer_visibility) void loadAnswerGrants();
  }, [exam?.can_manage_answer_visibility, id]);

  async function syncAttempt() {
    if (!attemptId) return;
    const snapshot = await api<AttemptSnapshot>(`/attempts/${attemptId}`);
    setRemaining(snapshot.remaining_seconds || 0);
    setExamStatus(snapshot.exam_status || '');
    setAttemptStatus(snapshot.status || 'in_progress');
    setTimerActive(Boolean(snapshot.timer_active));
    setIsAdminAttempt(Boolean(snapshot.is_admin_attempt));
    setVisitedQuestionIds(snapshot.visited_question_ids || []);
    setCanViewAnswers(Boolean(snapshot.can_view_answers));
    setAttemptScore(snapshot.score ?? null);
    setAttemptMaxScore(snapshot.max_score ?? null);
    if (snapshot.scheduled_resume_at && exam) setExam({ ...exam, scheduled_resume_at: snapshot.scheduled_resume_at, status: snapshot.exam_status });
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
        setVisitedQuestionIds(snapshot.visited_question_ids || []);
        setRemaining(snapshot.remaining_seconds || 0);
        setExamStatus(snapshot.exam_status || '');
        setAttemptStatus(snapshot.status || 'in_progress');
        setTimerActive(Boolean(snapshot.timer_active));
        setIsAdminAttempt(Boolean(snapshot.is_admin_attempt));
        setCanViewAnswers(Boolean(snapshot.can_view_answers));
        setAttemptScore(snapshot.score ?? null);
        setAttemptMaxScore(snapshot.max_score ?? null);
      }).catch((e) => { if (active) setError(e.message); });
    return () => { active = false; };
  }, [attemptId]);

  useEffect(() => {
    if (!attemptId || !canViewAnswers) return;
    let active = true;
    api<Question[]>(`/attempts/${attemptId}/questions`)
      .then((rows) => { if (active) setQuestions(rows); })
      .catch((e) => { if (active) setError(e instanceof Error ? e.message : 'Could not load the answer key.'); });
    return () => { active = false; };
  }, [attemptId, canViewAnswers, examStatus]);

  useEffect(() => {
    if (!answerSheetMode) return;
    let active = true;
    api<{ questions: Question[]; can_view_answers: boolean; participant_result?: ParticipantResult }>(`/exams/${id}/answer-sheet`)
      .then((result) => {
        if (!active) return;
        setQuestions(result.questions || []);
        setCanViewAnswers(Boolean(result.can_view_answers));
        setAnswerSheetResult(result.participant_result || null);
      })
      .catch((e) => { if (active) setError(e instanceof Error ? e.message : 'The answer sheet is unavailable.'); });
    return () => { active = false; };
  }, [id, answerSheetMode]);

  useEffect(() => {
    if (!attemptId) return;
    const poll = window.setInterval(() => {
      syncAttempt().catch((e) => setError(e.message));
      loadExam().catch(() => undefined);
    }, 10000);
    return () => window.clearInterval(poll);
  }, [attemptId]);

  useEffect(() => {
    if (attemptId) return;
    const poll = window.setInterval(() => {
      api<Exam>(`/exams/${id}`).then((row) => { setExam(row); setExamStatus(row.status); }).catch(() => undefined);
    }, 10000);
    return () => window.clearInterval(poll);
  }, [id, attemptId]);

  useEffect(() => {
    if (!attemptId || !activeQuestion || attemptStatus !== 'in_progress') return;
    api<{ visited_question_ids: string[] }>(`/attempts/${attemptId}/visit/${activeQuestion.id}`, { method: 'POST' })
      .then((result) => setVisitedQuestionIds(result.visited_question_ids || []))
      .catch((e) => setError(e instanceof Error ? e.message : 'Could not update question navigation.'));
  }, [attemptId, activeQuestion?.id, attemptStatus]);

  useEffect(() => {
    if (!attemptId || remaining <= 0 || examStatus !== 'live' || !timerActive) return;
    const timer = window.setInterval(() => setRemaining((value) => Math.max(0, value - 1)), 1000);
    return () => window.clearInterval(timer);
  }, [attemptId, remaining > 0, examStatus, timerActive]);

  async function save(question: Question, value: any) {
    const previous = answers[question.id];
    setAnswers((old) => ({ ...old, [question.id]: value }));
    setVisitedQuestionIds((old) => old.includes(question.id) ? old : [...old, question.id]);
    try {
      await api(`/attempts/${attemptId}/answers/${question.id}`, { method: 'PUT', body: JSON.stringify({ answer: value }) });
    } catch (e) {
      setAnswers((old) => {
        const next = { ...old };
        if (previous === undefined) delete next[question.id]; else next[question.id] = previous;
        return next;
      });
      setError(e instanceof Error ? e.message : 'Answer could not be saved');
    }
  }

  async function submit() {
    if (!attemptId) return;
    setBusy(true); setError(''); setNotice('');
    try {
      const result = await api<{ score?: number; max_score?: number; status: string }>(`/attempts/${attemptId}/submit`, { method: 'POST' });
      setAttemptStatus(result.status);
      setAttemptScore(result.score ?? null);
      setAttemptMaxScore(result.max_score ?? null);
      setNotice(ended ? `Attempt submitted. Score: ${result.score ?? 0}.` : 'Your answers have been submitted. The score and answer sheet will be available after the examination ends.');
      await syncAttempt();
    } catch (e) { setError(e instanceof Error ? e.message : 'Submission failed'); }
    finally { setBusy(false); }
  }

  async function startParticipantAttempt() {
    setBusy(true); setError('');
    try {
      const attempt = await api<{ attempt_id: string }>(`/exams/${id}/attempts`, { method: 'POST' });
      router.replace(`/exams/${id}?attempt=${attempt.attempt_id}`);
    } catch (e) { setError(e instanceof Error ? e.message : 'Unable to start'); }
    finally { setBusy(false); }
  }

  async function startAdminAttempt() {
    setBusy(true); setError(''); setNotice('');
    try {
      const attempt = await api<{ attempt_id: string }>(`/exams/${id}/admin-attempts`, { method: 'POST' });
      router.replace(`/exams/${id}?attempt=${attempt.attempt_id}`);
    } catch (e) { setError(e instanceof Error ? e.message : 'Unable to open administrator exam mode'); }
    finally { setBusy(false); }
  }

  async function controlExam(action: 'force-start' | 'pause' | 'resume' | 'stop') {
    if (!isAdmin) return;
    if (action === 'stop' && !window.confirm('Stop this examination for all students now? Active participant attempts will be submitted automatically.')) return;
    setAdminBusy(true); setError(''); setNotice('');
    try {
      const result = await api<Exam>(`/exams/${id}/control/${action}`, { method: 'POST' });
      setExam((old) => old ? { ...old, ...result } : result); setExamStatus(result.status);
      await syncAttempt();
      setNotice(action === 'stop' ? 'Examination stopped. Participant attempts have been finalized.' : action === 'pause' ? 'Examination paused for all students.' : action === 'resume' ? 'Examination resumed.' : 'Examination started immediately.');
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not control examination'); }
    finally { setAdminBusy(false); }
  }

  async function updateDuration(event: FormEvent) {
    event.preventDefault();
    const value = Number(timerMinutes);
    if (!Number.isInteger(value) || value < 1 || value > 1440) { setError('Duration must be between 1 and 1440 minutes.'); return; }
    if (exam && value < Math.round(exam.duration_seconds / 60) && ['live', 'paused'].includes(examStatus)) {
      if (!window.confirm('Reducing the duration can immediately expire some students’ attempts. Continue?')) return;
    }
    setAdminBusy(true); setError(''); setNotice('');
    try {
      const result = await api<Exam>(`/exams/${id}/duration`, { method: 'PATCH', body: JSON.stringify({ duration_minutes: value }) });
      setExam((old) => old ? { ...old, ...result } : result); setShowTimerEditor(false); await syncAttempt();
      setNotice(`Total examination duration updated to ${value} minutes.`);
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not update duration'); }
    finally { setAdminBusy(false); }
  }

  async function updateSchedule(event: FormEvent) {
    event.preventDefault();
    const endedRun = ['ended', 'results_published'].includes(examStatus);
    if (!scheduledStart && !endedRun) { setError('Choose a new date and time.'); return; }
    const startAt = scheduledStart ? new Date(scheduledStart) : null;
    if (startAt && Number.isNaN(startAt.getTime())) { setError('The selected date and time is invalid.'); return; }
    if (endedRun && !startAt && !window.confirm('Start this ended examination immediately as a new run? Previous attempts and scores will be preserved.')) return;
    if (startAt && startAt.getTime() <= Date.now() && ['live', 'paused'].includes(examStatus)) {
      if (!window.confirm('The selected time is now or in the past. The examination will resume immediately. Continue?')) return;
    }
    if (startAt && startAt.getTime() <= Date.now() && endedRun) {
      if (!window.confirm('The selected time is now or in the past. The examination will restart immediately as a new run. Previous attempts will be preserved. Continue?')) return;
    }
    setAdminBusy(true); setError(''); setNotice('');
    try {
      const result = await api<Exam & { message?: string }>(`/exams/${id}/schedule`, {
        method: 'PATCH', body: JSON.stringify({ scheduled_start_at: startAt ? startAt.toISOString() : null }),
      });
      setExam((old) => old ? { ...old, ...result } : result); setExamStatus(result.status); setShowScheduleEditor(false); await syncAttempt();
      setNotice(result.message || (endedRun ? 'A new examination run has been created.' : 'Examination schedule updated.'));
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not change examination schedule'); }
    finally { setAdminBusy(false); }
  }

  async function updateAnswerVisibility(payload: { answers_public?: boolean; hide_participant_answers?: boolean }) {
    if (!exam?.can_manage_answer_visibility) return;
    setAnswerGrantBusy(true); setAnswerGrantError(''); setAnswerGrantNotice('');
    try {
      const result = await api<{ answers_public: boolean; hide_participant_answers: boolean; message: string }>(`/exams/${id}/answer-visibility`, {
        method: 'PATCH', body: JSON.stringify(payload),
      });
      setExam((old) => old ? { ...old, ...result } : old);
      setAnswerGrantNotice(result.message);
    } catch (e) { setAnswerGrantError(e instanceof Error ? e.message : 'Could not update answer visibility.'); }
    finally { setAnswerGrantBusy(false); }
  }

  async function grantAnswerAccess(event: FormEvent) {
    event.preventDefault();
    if (!answerGrantEmail.trim()) return;
    setAnswerGrantBusy(true); setAnswerGrantError(''); setAnswerGrantNotice('');
    try {
      const result = await api<{ full_name: string; email: string }>(`/exams/${id}/answer-access`, {
        method: 'POST', body: JSON.stringify({ student_email: answerGrantEmail.trim() }),
      });
      setAnswerGrantEmail('');
      setAnswerGrantNotice(`Answer-sheet access granted to ${result.full_name} (${result.email}).`);
      await loadAnswerGrants();
    } catch (e) { setAnswerGrantError(e instanceof Error ? e.message : 'Could not grant answer-sheet access.'); }
    finally { setAnswerGrantBusy(false); }
  }

  async function revokeAnswerAccess(studentId: string, studentName: string) {
    if (!window.confirm(`Revoke answer-sheet access for ${studentName}?`)) return;
    setAnswerGrantBusy(true); setAnswerGrantError(''); setAnswerGrantNotice('');
    try {
      await api(`/exams/${id}/answer-access/${studentId}`, { method: 'DELETE' });
      setAnswerGrantNotice(`Answer-sheet access revoked for ${studentName}.`);
      await loadAnswerGrants();
    } catch (e) { setAnswerGrantError(e instanceof Error ? e.message : 'Could not revoke answer-sheet access.'); }
    finally { setAnswerGrantBusy(false); }
  }

  const answerVisibilityManager = exam?.can_manage_answer_visibility ? <section className="card p-4">
    <div className="flex items-center gap-2"><ShieldCheck size={18} className="text-violet-700"/><h2 className="font-black">Answer-sheet access</h2></div>
    <p className="mt-1 text-xs leading-5 text-slate-500">Only administrators and moderators with results permission can change these settings. Students can see answers only after the exam ends.</p>
    <div className="mt-3 space-y-2">
      <button type="button" disabled={!ended || answerGrantBusy} onClick={() => void updateAnswerVisibility({ hide_participant_answers: true })} className="flex w-full items-center justify-center gap-2 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm font-bold text-amber-900 disabled:opacity-40"><EyeOff size={15}/>Hide answers from participants</button>
      <button type="button" disabled={!ended || answerGrantBusy} onClick={() => void updateAnswerVisibility({ hide_participant_answers: false, answers_public: false })} className="flex w-full items-center justify-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm font-bold text-emerald-900 disabled:opacity-40"><Eye size={15}/>Show answers to participants</button>
      <button type="button" disabled={!ended || answerGrantBusy} onClick={() => void updateAnswerVisibility({ answers_public: true })} className="flex w-full items-center justify-center gap-2 rounded-xl border border-blue-200 bg-blue-50 px-3 py-2 text-sm font-bold text-blue-900 disabled:opacity-40"><UnlockKeyhole size={15}/>Make answers public to all students</button>
      {exam.answers_public && <button type="button" disabled={answerGrantBusy} onClick={() => void updateAnswerVisibility({ answers_public: false })} className="flex w-full items-center justify-center gap-2 rounded-xl border border-slate-200 px-3 py-2 text-sm font-bold text-slate-700 disabled:opacity-40"><LockKeyhole size={15}/>Stop public access</button>}
    </div>
    <div className="mt-3 rounded-lg bg-slate-50 p-3 text-xs text-slate-600">
      Current setting: <strong>{exam.answers_public ? 'Public to all students' : exam.hide_participant_answers ? 'Hidden from participants (individual grants still work)' : 'Visible to participants who submitted'}</strong>
    </div>
    <form onSubmit={grantAnswerAccess} className="mt-4 space-y-2">
      <label className="block text-xs font-bold text-slate-700">Permit an individual student by email</label>
      <input type="email" required className="field" placeholder="student@example.com" value={answerGrantEmail} onChange={(event: ChangeEvent<HTMLInputElement>) => setAnswerGrantEmail(event.target.value)}/>
      <button className="btn w-full" disabled={!ended || answerGrantBusy || !answerGrantEmail.trim()}>{answerGrantBusy ? <Loader2 size={15} className="mr-2 inline animate-spin"/> : <Users size={15} className="mr-2 inline"/>}Grant answer access</button>
    </form>
    {answerGrants.length > 0 && <div className="mt-4 border-t border-slate-100 pt-3"><p className="mb-2 text-xs font-black uppercase tracking-wide text-slate-500">Individual permissions</p><div className="space-y-2">{answerGrants.map((grant) => <div key={grant.student_id} className="flex items-center justify-between gap-2 text-xs"><div className="min-w-0"><p className="truncate font-bold">{grant.full_name}</p><p className="truncate text-slate-500">{grant.email}</p></div><button type="button" disabled={answerGrantBusy} onClick={() => void revokeAnswerAccess(grant.student_id, grant.full_name)} className="shrink-0 rounded-lg border border-red-200 px-2 py-1 font-bold text-red-700">Revoke</button></div>)}</div></div>}
    {answerGrantError && <p role="alert" className="mt-3 text-xs text-red-700">{answerGrantError}</p>}
    {answerGrantNotice && <p role="status" className="mt-3 text-xs text-emerald-700">{answerGrantNotice}</p>}
  </section> : null;

  if (attemptId || answerSheetMode) {
    const adminMode = isAdmin && isAdminAttempt;
    const participantMode = !isStaff && !answerSheetMode;
    const navigation = <aside className="space-y-4 lg:sticky lg:top-24 lg:self-start">
      <section className="card p-4">
        <div className="flex items-center justify-between gap-2"><h2 className="font-black">Question navigation</h2><span className="text-xs text-slate-500">{questions.length} total</span></div>
        <div className="mt-3 grid grid-cols-5 gap-2 sm:grid-cols-7 lg:grid-cols-5">
          {questions.map((question, questionIndex) => {
            const answered = isAnswered(question, answers[question.id]);
            const visited = visitedSet.has(question.id);
            const stateClass = answered
              ? 'border-emerald-500 bg-emerald-500 text-white hover:bg-emerald-600'
              : visited
                ? 'border-amber-300 bg-amber-100 text-amber-900 hover:bg-amber-200'
                : 'border-slate-200 bg-slate-100 text-slate-600 hover:bg-slate-200';
            return <button key={question.id} type="button" onClick={() => setIndex(questionIndex)} aria-label={`Go to question ${questionIndex + 1}`} aria-current={index === questionIndex ? 'step' : undefined}
              className={`grid aspect-square place-items-center rounded-lg border text-sm font-black transition ${stateClass} ${index === questionIndex ? 'ring-2 ring-blue-600 ring-offset-2' : ''}`}>
              {questionIndex + 1}
            </button>;
          })}
        </div>
        <div className="mt-4 space-y-2 border-t border-slate-100 pt-3 text-xs">
          <div className="flex items-center justify-between"><span className="flex items-center gap-2"><i className="h-3 w-3 rounded-sm bg-emerald-500"/>Visited & answered</span><strong>{answeredCount}</strong></div>
          <div className="flex items-center justify-between"><span className="flex items-center gap-2"><i className="h-3 w-3 rounded-sm bg-amber-200"/>Visited, unanswered</span><strong>{visitedUnansweredCount}</strong></div>
          <div className="flex items-center justify-between"><span className="flex items-center gap-2"><i className="h-3 w-3 rounded-sm bg-slate-200"/>Not visited</span><strong>{notVisitedCount}</strong></div>
        </div>
        {participantMode && <p className="mt-3 text-[11px] leading-4 text-slate-500">Green means an answer is saved. Yellow means you opened the question but have not saved an answer. Grey means you have not visited it.</p>}
        {answerSheetMode && <p className="mt-3 text-[11px] text-slate-500">Read-only answer-sheet review.</p>}
      </section>
      {answerVisibilityManager}
    </aside>;

    return <main className={`container-shell py-8 ${adminMode ? 'pb-40' : 'pb-10'}`}>
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="min-w-0"><p className="text-xs font-bold uppercase text-brand">{answerSheetMode ? 'Answer sheet' : adminMode ? 'Administrator exam mode' : isModerator ? 'Moderator examination mode' : 'Live examination'}</p><h1 className="mt-1 text-2xl font-black">{exam?.title || 'Examination'}</h1><p className="mt-1 text-xs text-slate-500">{adminMode ? 'Correct answers are visible. Your preview attempt is excluded from student rankings.' : isModerator ? 'Moderator view: correct answers are visible.' : answerSheetMode ? 'You have read-only access to this answer sheet.' : paused ? 'The administrator has paused this examination. Your remaining time is preserved.' : ended ? 'This examination has ended.' : 'Your answers are saved as you work.'}</p></div>
        {!answerSheetMode && <div className="rounded-xl bg-ink px-4 py-3 text-lg font-black text-white">{timerLabel}</div>}
      </div>
      {adminMode && <div className="mt-4 flex flex-wrap items-center gap-2 rounded-xl border border-violet-200 bg-violet-50 p-3 text-sm text-violet-900"><ShieldCheck size={18}/> Administrator preview · correct answers shown · excluded from student rankings</div>}
      {isModerator && attemptId && <div className="mt-4 flex items-center gap-2 rounded-xl border border-blue-200 bg-blue-50 p-3 text-sm text-blue-900"><ShieldCheck size={18}/> Moderator view · correct answers shown · student leaderboard is unaffected</div>}
      {paused && <p className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">Exam paused. Participant timers are frozen. Your remaining time is preserved.</p>}
      {ended && <p className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">This examination has ended. {revealAnswerKeys ? 'The answer sheet is available below.' : 'The examiner has hidden the answer sheet or has not granted access.'}</p>}
      {participantMode && ended && attemptSubmitted && <div className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 p-4"><p className="text-sm font-black text-emerald-900">Your examination result</p><p className="mt-1 text-2xl font-black text-emerald-900">{attemptScore ?? 0}{attemptMaxScore !== null ? ` / ${attemptMaxScore}` : ''}</p><p className="mt-1 text-xs text-emerald-800">{revealAnswerKeys ? 'Correct answers are shown with your result.' : 'Your score is available, but the examiner has hidden the answers.'}</p></div>}
      {answerSheetMode && answerSheetResult && <div className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 p-4"><p className="text-sm font-black text-emerald-900">Your examination result</p><p className="mt-1 text-2xl font-black text-emerald-900">{answerSheetResult.score ?? 0}{answerSheetResult.max_score !== null ? ` / ${answerSheetResult.max_score}` : ''}</p><p className="mt-1 text-xs text-emerald-800">Your submitted score is shown with the answer sheet.</p></div>}
      {notice && <p role="status" className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">{notice}</p>}
      {error && <p role="alert" className="mt-4 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</p>}

      <div className="mt-6 grid grid-cols-1 items-start gap-5 lg:grid-cols-[minmax(0,1fr)_290px]">
        <section>
          {activeQuestion ? <div className="card p-6">
            <div className="flex justify-between text-sm text-slate-500"><span>Question {index + 1} of {questions.length}</span><span>{activeQuestion.marks} marks</span></div>
            <h2 className="mt-5 text-xl font-bold leading-8">{activeQuestion.prompt}</h2>
            <div className="mt-6 space-y-3">
              {activeQuestion.kind === 'short_answer' ? <>
                <textarea className="field min-h-28" disabled={!canEdit} value={answers[activeQuestion.id]?.text || ''} onChange={(e: ChangeEvent<HTMLTextAreaElement>) => void save(activeQuestion, { text: e.target.value })}/>
                {revealAnswerKeys && <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-900"><strong>Accepted answers:</strong> {(activeQuestion.answer_key?.accepted_answers || []).join(' · ') || 'No answer key set'}</div>}
              </> : activeQuestion.kind === 'true_false' ? ['True', 'False'].map((value, i) => {
                const correct = revealAnswerKeys && activeQuestion.answer_key?.value === (i === 0);
                return <label key={value} className={`flex cursor-pointer items-center gap-3 rounded-xl border p-4 ${correct ? 'border-emerald-400 bg-emerald-50' : 'border-slate-200'} ${!canEdit ? 'opacity-80' : ''}`}><input type="radio" name={activeQuestion.id} disabled={!canEdit} checked={answers[activeQuestion.id]?.value === (i === 0)} onChange={() => void save(activeQuestion, { value: i === 0 })}/><span className="flex-1">{value}</span>{correct && <span className="text-xs font-bold text-emerald-700">✓ Correct answer</span>}</label>;
              }) : (activeQuestion.options || []).map((option, i) => {
                const correct = revealAnswerKeys && correctIds.has(String(option.id));
                return <label key={option.id || i} className={`flex cursor-pointer items-center gap-3 rounded-xl border p-4 ${correct ? 'border-emerald-400 bg-emerald-50' : 'border-slate-200'} ${!canEdit ? 'opacity-80' : ''}`}><input type={activeQuestion.kind === 'multiple_mcq' ? 'checkbox' : 'radio'} name={activeQuestion.id} disabled={!canEdit} checked={activeQuestion.kind === 'multiple_mcq' ? (answers[activeQuestion.id]?.selected_option_ids || []).includes(option.id) : answers[activeQuestion.id]?.selected_option_ids?.[0] === option.id} onChange={(e: ChangeEvent<HTMLInputElement>) => { if (activeQuestion.kind === 'multiple_mcq') { const old = answers[activeQuestion.id]?.selected_option_ids || []; void save(activeQuestion, { selected_option_ids: e.target.checked ? [...old, option.id] : old.filter((x: string) => x !== option.id) }); } else { void save(activeQuestion, { selected_option_ids: [option.id] }); } }}/><span className="flex-1">{option.text}</span>{correct && <span className="whitespace-nowrap text-xs font-bold text-emerald-700">✓ Correct answer</span>}</label>;
              })}
            </div>
            {revealAnswerKeys && (!activeQuestion.answer_key || Object.keys(activeQuestion.answer_key).length === 0) && <p className="mt-3 text-xs text-amber-700">No answer key is set for this question.</p>}
            <div className="mt-8 flex flex-wrap justify-between gap-3">
              <button className="rounded-xl border px-4 py-2 font-bold" disabled={index === 0} onClick={() => setIndex((i) => i - 1)}>Previous</button>
              <div className="flex gap-2"><button className="rounded-xl border px-4 py-2 font-bold" onClick={() => void submit()} disabled={!attemptId || busy || attemptSubmitted || answerSheetMode}>{attemptSubmitted ? 'Submitted' : busy ? 'Submitting…' : adminMode ? 'Finish admin attempt' : 'Submit exam'}</button><button className="btn" disabled={index === questions.length - 1} onClick={() => setIndex((i) => i + 1)}>Next</button></div>
            </div>
          </div> : <p className="card p-8 text-center text-slate-500">{error || 'Loading questions…'}</p>}
        </section>
        {navigation}
      </div>

      {adminMode && <>
        <div className="fixed inset-x-0 bottom-0 z-[90] border-t border-slate-200 bg-white/95 p-3 shadow-[0_-8px_30px_rgba(15,23,42,0.10)] backdrop-blur">
          <div className="container-shell flex flex-wrap items-center justify-between gap-3">
            <div className="min-w-32"><p className="text-xs font-black uppercase tracking-wide text-violet-700">Admin controls</p><p className="text-xs text-slate-500">Exam status: <strong className="capitalize">{examStatus.replace('_', ' ')}</strong></p></div>
            <div className="flex flex-wrap items-center gap-2">
              {examStatus === 'live' ? <button type="button" className="rounded-xl border border-amber-300 bg-amber-50 px-3 py-2 text-sm font-bold text-amber-900 disabled:opacity-50" disabled={adminBusy} onClick={() => void controlExam('pause')}><Pause size={15} className="mr-1 inline"/>Pause exam</button> : examStatus === 'paused' ? <button type="button" className="rounded-xl border border-emerald-300 bg-emerald-50 px-3 py-2 text-sm font-bold text-emerald-900 disabled:opacity-50" disabled={adminBusy} onClick={() => void controlExam('resume')}><Play size={15} className="mr-1 inline"/>Resume now</button> : ['draft', 'published', 'ended', 'results_published'].includes(examStatus) ? <button type="button" className="rounded-xl border border-emerald-300 bg-emerald-50 px-3 py-2 text-sm font-bold text-emerald-900 disabled:opacity-50" disabled={adminBusy} onClick={() => void controlExam('force-start')}><Play size={15} className="mr-1 inline"/>{['ended', 'results_published'].includes(examStatus) ? 'Start new run now' : 'Start now'}</button> : <span className="rounded-xl bg-slate-100 px-3 py-2 text-xs font-semibold text-slate-500">Exam ended</span>}
              <button type="button" className="rounded-xl border border-slate-200 px-3 py-2 text-sm font-bold disabled:opacity-50" disabled={adminBusy || ended} onClick={() => { setTimerMinutes(String(Math.max(1, Math.round((exam?.duration_seconds || 3600) / 60)))); setShowTimerEditor(true); }}><Timer size={15} className="mr-1 inline"/>Update timer</button>
              <button type="button" className="rounded-xl border border-slate-200 px-3 py-2 text-sm font-bold disabled:opacity-50" disabled={adminBusy || examStatus === 'archived'} onClick={() => { setScheduledStart(['ended', 'results_published'].includes(examStatus) ? '' : toLocalDateTime(exam?.scheduled_resume_at || exam?.scheduled_start_at)); setShowScheduleEditor(true); }}><CalendarClock size={15} className="mr-1 inline"/>{['ended', 'results_published'].includes(examStatus) ? 'Schedule new run' : 'Change schedule'}</button>
              <button type="button" className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm font-bold text-red-700 disabled:opacity-50" disabled={adminBusy || ended} onClick={() => void controlExam('stop')}><Square size={14} className="mr-1 inline"/>Stop exam</button>
            </div>
          </div>
        </div>

        {showTimerEditor && <div className="fixed inset-0 z-[120] flex items-center justify-center bg-slate-950/50 p-4"><section role="dialog" aria-modal="true" className="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl"><div className="flex items-center justify-between"><h2 className="text-xl font-black">Update exam timer</h2><button onClick={() => setShowTimerEditor(false)} disabled={adminBusy}><X size={20}/></button></div><p className="mt-2 text-sm text-slate-500">Set the new total duration. This can increase or reduce the time for active participant attempts.</p><form onSubmit={updateDuration} className="mt-5 space-y-4"><label className="block text-sm font-bold">Duration in minutes<input type="number" min="1" max="1440" required className="field mt-2" value={timerMinutes} onChange={(e: ChangeEvent<HTMLInputElement>) => setTimerMinutes(e.target.value)}/></label><div className="flex justify-end gap-2"><button type="button" className="rounded-xl border px-4 py-2 text-sm font-bold" onClick={() => setShowTimerEditor(false)} disabled={adminBusy}>Cancel</button><button className="btn" disabled={adminBusy}>{adminBusy ? <Loader2 className="mr-2 inline animate-spin" size={15}/> : null}Save timer</button></div></form></section></div>}

        {showScheduleEditor && <div className="fixed inset-0 z-[120] flex items-center justify-center bg-slate-950/50 p-4"><section role="dialog" aria-modal="true" className="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl"><div className="flex items-center justify-between"><h2 className="text-xl font-black">Change exam schedule</h2><button onClick={() => setShowScheduleEditor(false)} disabled={adminBusy}><X size={20}/></button></div><p className="mt-2 text-sm text-slate-500">{['ended', 'results_published'].includes(examStatus) ? 'Scheduling an ended exam creates a new run. Previous attempts remain in history. Leave the date blank to start immediately.' : 'If the exam is live, it will pause immediately and automatically resume at the selected date and time. Participant timers are preserved.'}</p><form onSubmit={updateSchedule} className="mt-5 space-y-4"><label className="block text-sm font-bold">{['ended', 'results_published'].includes(examStatus) ? 'New run start date and time (leave blank to start now)' : 'New start / resume date and time'}<input type="datetime-local" required={!['ended', 'results_published'].includes(examStatus)} className="field mt-2" value={scheduledStart} onChange={(e: ChangeEvent<HTMLInputElement>) => setScheduledStart(e.target.value)}/></label><div className="flex justify-end gap-2"><button type="button" className="rounded-xl border px-4 py-2 text-sm font-bold" onClick={() => setShowScheduleEditor(false)} disabled={adminBusy}>Cancel</button><button className="btn" disabled={adminBusy}>{adminBusy ? <Loader2 className="mr-2 inline animate-spin" size={15}/> : null}{['ended', 'results_published'].includes(examStatus) ? 'Schedule new run' : 'Save schedule'}</button></div></form></section></div>}
      </>}
    </main>;
  }

  return <main className="container-shell py-12">{exam ? <div className="card mx-auto max-w-3xl p-8"><p className="text-xs font-bold uppercase tracking-widest text-brand">{exam.subject}</p><h1 className="mt-3 text-3xl font-black">{exam.title}</h1><p className="mt-4 leading-7 text-slate-600">{exam.description}</p><div className="mt-6 flex flex-wrap gap-5 text-sm text-slate-500"><span>{Math.round(exam.duration_seconds / 60)} minutes</span><span className="capitalize">{exam.status}</span>{exam.scheduled_start_at && <span>Scheduled: {new Date(exam.scheduled_start_at).toLocaleString()}</span>}</div>
    {isAdmin ? <div className="mt-8 space-y-3"><div className="rounded-xl border border-violet-200 bg-violet-50 p-4 text-sm text-violet-900"><strong><ShieldCheck className="mr-2 inline" size={17}/>Administrator access</strong><p className="mt-1">You can enter any non-archived exam, view correct answers and control the live examination.</p></div><button className="btn w-full" onClick={() => void startAdminAttempt()} disabled={busy}>{busy ? <Loader2 className="mr-2 inline animate-spin" size={16}/> : null}Enter exam with answers</button><div className="grid gap-2 sm:grid-cols-2"><button className="rounded-xl border border-emerald-300 bg-emerald-50 px-4 py-3 text-sm font-bold text-emerald-900" onClick={() => void controlExam('force-start')} disabled={adminBusy || exam.status === 'live'}><Play size={15} className="mr-1 inline"/>{['ended', 'results_published'].includes(exam.status) ? 'Start new run now' : 'Start for students now'}</button><button className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-bold text-red-700" onClick={() => void controlExam('stop')} disabled={adminBusy || ended}><Square size={14} className="mr-1 inline"/>Stop examination</button></div></div> : exam.status === 'live' && (user?.role === 'student' || isModerator) ? <button className="btn mt-8 w-full" onClick={() => void startParticipantAttempt()} disabled={busy}>{busy ? 'Starting…' : isModerator ? 'Enter as moderator (answers visible)' : 'Start examination'}</button> : null}
    {exam.can_view_answer_sheet && ended && <button className="mt-3 w-full rounded-xl border border-emerald-300 bg-emerald-50 px-4 py-3 font-bold text-emerald-900" onClick={() => router.push(`/exams/${id}?answers=1`)}><Eye size={16} className="mr-2 inline"/>View answer sheet</button>}
    {error && <p role="alert" className="mt-4 text-sm text-red-600">{error}</p>}{notice && <p role="status" className="mt-4 text-sm text-emerald-700">{notice}</p>}
    {answerVisibilityManager && <div className="mt-6">{answerVisibilityManager}</div>}
    </div> : <p>{error || 'Loading…'}</p>}</main>;
}
