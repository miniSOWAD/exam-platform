'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import {
  Activity, ArrowRight, ArrowUpRight, Award, BookOpen, CalendarDays,
  ChevronRight, Clock3, FileText, FlaskConical, GraduationCap, Layers3, LockKeyhole,
  Medal, Radio, ShieldCheck, Sparkles, Trophy, UserRound, Zap
} from 'lucide-react';
import { api } from '@/lib/api';

type User = { id: string; email: string; full_name: string; role: string };
type Exam = {
  id: string; title: string; subject: string; chapter?: string | null; set_name?: string | null;
  status: string; duration_seconds: number; question_count: number; scheduled_start_at?: string | null; scheduled_end_at?: string | null;
};
type LeaderboardRow = { rank: number; student: string; score: number };
type SiteProfile = { owner_name:string; owner_role:string; owner_bio:string; owner_education:string; owner_department:string; owner_institution:string; owner_location:string; owner_photo_url:string; owner_email:string; owner_social_links:Record<string,string>; announcement:string; hero_eyebrow:string; hero_title:string; hero_highlight:string; hero_description:string };

const subjects = [
  { name: 'Mathematics', short: 'Math', note: 'Build problem-solving confidence', icon: Layers3, tone: 'subject-blue' },
  { name: 'Physics', short: 'Physics', note: 'Understand concepts and laws', icon: Activity, tone: 'subject-mint' },
  { name: 'Chemistry', short: 'Chemistry', note: 'Practice reactions and principles', icon: FlaskConical, tone: 'subject-lilac' },
  { name: 'Biology', short: 'Biology', note: 'Strengthen concepts and recall', icon: GraduationCap, tone: 'subject-peach' },
];

const features = [
  { icon: FileText, title: 'Build better assessments', description: 'Create question sets, configure marks and organize exams by subject, chapter and set.', label: 'Exam builder', tone: 'feature-blue' },
  { icon: Radio, title: 'Manage live examinations', description: 'Start, pause and resume exams with a server-controlled timer and reliable answer saving.', label: 'Live control', tone: 'feature-mint' },
  { icon: Trophy, title: 'Understand every result', description: 'Review scores, compare published rankings and follow performance across attempts.', label: 'Performance', tone: 'feature-lilac' },
];

function initials(name?: string) {
  if (!name) return 'EF';
  return name.trim().split(/\s+/).slice(0, 2).map((part) => part[0]).join('').toUpperCase();
}

function statusLabel(status: string) {
  if (status === 'live') return 'Live now';
  if (status === 'paused') return 'Temporarily paused';
  return 'Upcoming';
}

export default function HomeExperience() {
  const [user, setUser] = useState<User | null>(null);
  const [siteProfile, setSiteProfile] = useState<SiteProfile | null>(null);
  const [exams, setExams] = useState<Exam[]>([]);
  const [loading, setLoading] = useState(true);
  const [examError, setExamError] = useState('');
  const [today, setToday] = useState<Date | null>(null);
  const [leaderboardExamId, setLeaderboardExamId] = useState('');
  const [leaderboard, setLeaderboard] = useState<LeaderboardRow[]>([]);
  const [leaderboardLoading, setLeaderboardLoading] = useState(false);
  const [leaderboardError, setLeaderboardError] = useState('');

  useEffect(() => {
    setToday(new Date());
    let active = true;
    api<SiteProfile>('/site-profile').then((profile) => { if (active) setSiteProfile(profile); }).catch(() => {});
    async function loadWorkspace() {
      try {
        const publicExams = await api<Exam[]>('/public/exams');
        if (active) setExams(publicExams);
      } catch (error) {
        if (active) setExamError(error instanceof Error ? error.message : 'Examinations could not be loaded.');
      }
      try {
        const currentUser = await api<User>('/auth/me');
        if (!active) return;
        setUser(currentUser);
        const availableExams = await api<Exam[]>('/exams');
        if (active) setExams(availableExams);
      } catch {
        if (active) setUser(null);
      } finally {
        if (active) setLoading(false);
      }
    }
    loadWorkspace();
    return () => { active = false; };
  }, []);

  const visibleExams = useMemo(() => exams
    .filter((exam) => ['live', 'paused', 'published'].includes(exam.status))
    .sort((a, b) => {
      const priority = (status: string) => status === 'live' ? 0 : status === 'paused' ? 1 : 2;
      return priority(a.status) - priority(b.status);
    }).slice(0, 4), [exams]);

  const publishedExams = useMemo(() => exams.filter((exam) => exam.status === 'results_published'), [exams]);

  useEffect(() => {
    if (!user || publishedExams.length === 0) {
      setLeaderboard([]);
      setLeaderboardExamId('');
      return;
    }
    if (!leaderboardExamId || !publishedExams.some((exam) => exam.id === leaderboardExamId)) {
      setLeaderboardExamId(publishedExams[0].id);
    }
  }, [user, publishedExams, leaderboardExamId]);

  useEffect(() => {
    if (!user || !leaderboardExamId) return;
    let active = true;
    setLeaderboardLoading(true);
    setLeaderboardError('');
    api<LeaderboardRow[]>(`/exams/${leaderboardExamId}/leaderboard`)
      .then((rows) => { if (active) setLeaderboard(rows); })
      .catch((error) => { if (active) { setLeaderboard([]); setLeaderboardError(error instanceof Error ? error.message : 'Leaderboard is unavailable.'); } })
      .finally(() => { if (active) setLeaderboardLoading(false); });
    return () => { active = false; };
  }, [user, leaderboardExamId]);

  const calendarCells = useMemo(() => {
    if (!today) return [] as (number | null)[];
    const year = today.getFullYear();
    const month = today.getMonth();
    const firstDay = new Date(year, month, 1).getDay();
    const days = new Date(year, month + 1, 0).getDate();
    return [...Array.from({ length: firstDay }, () => null), ...Array.from({ length: days }, (_, index) => index + 1)];
  }, [today]);

  const monthLabel = today ? today.toLocaleDateString('en-US', { month: 'long', year: 'numeric' }) : 'Academic calendar';
  const isToday = (day: number | null) => Boolean(today && day === today.getDate());
  const scheduledDays = useMemo(() => new Set(exams.filter((exam) => exam.scheduled_start_at).map((exam) => { const d = new Date(exam.scheduled_start_at as string); return `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`; })), [exams]);
  const hasExamOnDay = (day:number|null) => Boolean(today && day && scheduledDays.has(`${today.getFullYear()}-${today.getMonth()}-${day}`));
  const scheduledExams = useMemo(() => exams.filter((exam) => exam.scheduled_start_at).sort((a,b)=>new Date(a.scheduled_start_at as string).getTime()-new Date(b.scheduled_start_at as string).getTime()).slice(0,3), [exams]);

  return (
    <main className="academic-page">
      <div className="academic-shell">
        <div className="home-grid">
          <aside className="profile-rail">
            <section className="profile-card academic-card owner-profile-card">
              <div className="profile-card-topline"><span>ABOUT THE OWNER</span><span className="profile-shield"><ShieldCheck size={16} /></span></div>
              <div className="profile-avatar-wrap">
                {siteProfile?.owner_photo_url ? <img className="profile-avatar owner-photo" src={siteProfile.owner_photo_url} alt={siteProfile.owner_name || 'ExamFlow owner'} /> : <div className="profile-avatar">{initials(siteProfile?.owner_name || 'Md Mahruf Alam')}</div>}
              </div>
              <p className="profile-kicker">SITE OWNER · TUTOR · EXAMINER</p>
              <h2 className="profile-name">{siteProfile?.owner_name || 'Md Mahruf Alam'}</h2>
              <p className="profile-role">{siteProfile?.owner_role || 'Owner · Tutor · Examiner'}</p>
              <p className="profile-intro owner-bio">{siteProfile?.owner_bio || 'I created ExamFlow to make exam preparation, assessment and performance tracking more organized and accessible.'}</p>
              <div className="profile-details owner-details">
                {siteProfile?.owner_education && <div><span>Education</span><strong>{siteProfile.owner_education}</strong></div>}
                {siteProfile?.owner_department && <div><span>Department</span><strong>{siteProfile.owner_department}</strong></div>}
                {siteProfile?.owner_institution && <div><span>Institution</span><strong>{siteProfile.owner_institution}</strong></div>}
                {siteProfile?.owner_location && <div><span>Location</span><strong>{siteProfile.owner_location}</strong></div>}
              </div>
              {siteProfile?.owner_email && <a className="profile-action" href={`mailto:${siteProfile.owner_email}`}>Contact the owner <ArrowUpRight size={15} /></a>}
              {siteProfile?.owner_social_links && Object.entries(siteProfile.owner_social_links).filter(([,url])=>Boolean(url)).length > 0 && <div className="owner-social-links">{Object.entries(siteProfile.owner_social_links).filter(([,url])=>Boolean(url)).map(([label,url])=><a key={label} href={url} target="_blank" rel="noreferrer">{label}</a>)}</div>}
            </section>

            <section className="rail-subject-card academic-card" id="subjects">
              <div className="section-heading compact-heading"><div><span className="eyebrow">STUDY AREAS</span><h3>Explore subjects</h3></div><BookOpen size={19} /></div>
              <div className="rail-subject-list">
                {subjects.map(({ name, icon: Icon, tone }) => (
                  <div className="rail-subject-row" key={name}><span className={`mini-subject-icon ${tone}`}><Icon size={16} /></span><span>{name}</span><ChevronRight size={15} className="rail-chevron" /></div>
                ))}
              </div>
              <p className="rail-note">Four core areas. One focused place to prepare.</p>
            </section>

            <section className="rail-note-card">
              <Sparkles size={17} />
              <p><strong>Small steps add up.</strong><span>Practice consistently and use every result as a guide for what to learn next.</span></p>
            </section>
          </aside>

          <section className="hero-panel academic-card">
            <div className="hero-copy">
              <span className="hero-eyebrow"><span className="eyebrow-dot" /> {siteProfile?.hero_eyebrow || 'EXAMINATION PREPARATION, REIMAGINED'}</span>
              <h1>{siteProfile?.hero_title || 'Prepare with purpose.'} <em>{siteProfile?.hero_highlight || 'Perform with confidence.'}</em></h1>
              <p className="hero-description">{siteProfile?.hero_description || 'A thoughtful workspace for creating exams, practicing what matters and understanding every result across Mathematics, Physics, Chemistry and Biology.'}</p>
              <div className="hero-subjects" aria-label="Supported subjects">
                {subjects.map(({ short, tone }) => <span className={`hero-subject-chip ${tone}`} key={short}>{short}</span>)}
              </div>
              <div className="hero-actions">
                <Link href={user ? '/dashboard' : '/register'} className="primary-action">{user ? 'Go to my workspace' : 'Create student account'} <ArrowRight size={17} /></Link>
                <Link href={user ? '/dashboard' : '/login'} className="secondary-action">{user ? 'View examinations' : 'Sign in'}</Link>
              </div>
              <div className="hero-trust"><ShieldCheck size={16} /><span>Role-based access</span><i /> <span>Server-side scoring</span><i /> <span>PDF question import</span></div>
            </div>
            <div className="hero-visual" aria-label="ExamFlow study overview illustration">
              <div className="visual-topline"><span>YOUR PREPARATION, ORGANIZED</span><span className="visual-live"><span /> Focus mode</span></div>
              <div className="visual-main">
                <div className="visual-copy"><span className="visual-label">A clearer way to prepare</span><strong>Learn. Practice.<br />Improve.</strong><p>Make each attempt count.</p></div>
                <div className="visual-orbit orbit-one" /><div className="visual-orbit orbit-two" />
                <div className="visual-mark"><BookOpen size={30} strokeWidth={1.5} /></div>
              </div>
              <div className="visual-bottom"><span><b>04</b> core subjects</span><span><b>04</b> question formats</span><span><b>01</b> focused workspace</span></div>
            </div>
            <div className="hero-decor hero-decor-one" /><div className="hero-decor hero-decor-two" />
          </section>

          <aside className="upcoming-panel academic-card">
            <div className="section-heading"><div><span className="eyebrow">TAKE THE NEXT STEP</span><h2>Live & upcoming exams</h2></div><span className="heading-icon"><Radio size={18} /></span></div>
            <p className="section-subtitle">Find an assessment and check your preparation.</p>
            {loading ? <div className="skeleton-list"><span /><span /><span /></div> : visibleExams.length ? (
              <div className="exam-list">
                {visibleExams.map((exam) => (
                  <article className="exam-list-item" key={exam.id}>
                    <div className="exam-item-top"><span className="exam-subject">{exam.subject || 'General'}</span><span className={`exam-status status-${exam.status}`}>{exam.status === 'live' && <i />}{statusLabel(exam.status)}</span></div>
                    <h3>{exam.title}</h3>
                    <p className="exam-meta">{[exam.chapter, exam.set_name].filter(Boolean).join(' · ') || `${exam.question_count} questions`} </p>
                    <div className="exam-item-bottom"><span><Clock3 size={13} /> {Math.round(exam.duration_seconds / 60)} min</span><Link href={user ? `/exams/${exam.id}` : `/login?next=/exams/${exam.id}`}>{user && exam.status === 'live' ? 'Enter exam' : user ? 'View details' : 'Sign in to join'} <ArrowUpRight size={13} /></Link></div>
                  </article>
                ))}
              </div>
            ) : (
              <div className="empty-state"><span className="empty-icon"><CalendarDays size={20} /></span><strong>No upcoming exams yet</strong><p>{examError || 'When an examination is published or started, it will appear in this space.'}</p></div>
            )}
            <Link href={user ? '/dashboard' : '/register'} className="panel-footer-link">{user ? 'View all examinations' : 'Sign in to participate'} <ArrowUpRight size={15} /></Link>
          </aside>

          <section className="calendar-panel academic-card" id="calendar">
            <div className="section-heading"><div><span className="eyebrow">PLAN YOUR PREPARATION</span><h2>University exam calendar</h2></div><span className="heading-icon"><CalendarDays size={18} /></span></div>
            <p className="section-subtitle">Keep your academic schedule in view and make room for consistent practice.</p>
            <div className="calendar-content">
              <div className="mini-calendar">
                <div className="calendar-month"><strong>{monthLabel}</strong><span>MONTH VIEW</span></div>
                <div className="calendar-weekdays">{['S', 'M', 'T', 'W', 'T', 'F', 'S'].map((day, index) => <span key={`${day}-${index}`}>{day}</span>)}</div>
                <div className="calendar-days">{calendarCells.map((day, index) => day ? <span key={`${day}-${index}`} className={`${isToday(day) ? 'calendar-today' : ''} ${hasExamOnDay(day) ? 'calendar-event-day' : ''}`}>{day}</span> : <i key={`blank-${index}`} />)}</div>
                <div className="calendar-legend"><span><i /> Today</span><span><i className="legend-event" /> Exam dates</span></div>
              </div>
              <div className="calendar-message">
                <span className="calendar-message-icon"><GraduationCap size={21} /></span>
                <div><strong>{scheduledExams.length ? 'Upcoming scheduled examinations' : 'Your academic schedule starts here'}</strong><p>{scheduledExams.length ? 'Dates set by the ExamFlow administrator.' : 'Scheduled public examinations will appear here.'}</p></div>
                {scheduledExams.length > 0 && <div className="calendar-event-list">{scheduledExams.map(exam=><div key={exam.id}><span>{new Date(exam.scheduled_start_at as string).toLocaleDateString('en-US',{day:'numeric',month:'short'})}</span><strong>{exam.title}</strong></div>)}</div>}
                <Link href={user ? '/dashboard' : '/login'} className="text-action">{user ? 'Open workspace' : 'Sign in'} <ArrowRight size={14} /></Link>
              </div>
            </div>
          </section>

          <section className="leaderboard-panel academic-card" id="leaderboard">
            <div className="section-heading"><div><span className="eyebrow">CELEBRATE PROGRESS</span><h2>Leaderboard</h2></div><span className="heading-icon"><Trophy size={18} /></span></div>
            <p className="section-subtitle">See how students performed in published examinations.</p>
            {!user ? (
              <div className="empty-state compact-empty"><span className="empty-icon"><Trophy size={20} /></span><strong>Results worth celebrating</strong><p>Sign in to explore published exam rankings.</p><Link href="/login" className="text-action">Sign in to view <ArrowRight size={14} /></Link></div>
            ) : publishedExams.length === 0 ? (
              <div className="empty-state compact-empty"><span className="empty-icon"><Medal size={20} /></span><strong>No published rankings yet</strong><p>Once results are published, the top performers will appear here.</p></div>
            ) : (
              <>
                <label className="leaderboard-select-label" htmlFor="leaderboard-exam">Choose examination</label>
                <select id="leaderboard-exam" className="leaderboard-select" value={leaderboardExamId} onChange={(event) => setLeaderboardExamId(event.target.value)}>{publishedExams.map((exam) => <option key={exam.id} value={exam.id}>{exam.title}</option>)}</select>
                {leaderboardLoading ? <div className="skeleton-list"><span /><span /><span /></div> : leaderboard.length ? (
                  <div className="leaderboard-list">{leaderboard.slice(0, 5).map((row) => <div className="leaderboard-row" key={`${row.rank}-${row.student}`}><span className={`rank-medal rank-${row.rank}`}>{row.rank === 1 ? <Trophy size={15} /> : row.rank === 2 ? <Medal size={15} /> : row.rank === 3 ? <Award size={15} /> : row.rank}</span><span className="leaderboard-student">{row.student}</span><strong>{row.score}</strong></div>)}</div>
                ) : <p className="leaderboard-empty">{leaderboardError || 'No scores are available for this examination yet.'}</p>}
                {leaderboardExamId && <Link href={`/leaderboard/${leaderboardExamId}`} className="panel-footer-link">View full leaderboard <ArrowUpRight size={15} /></Link>}
              </>
            )}
          </section>
        </div>

        <section className="features-section">
          <div className="features-intro"><div><span className="eyebrow">EVERYTHING IN ONE PLACE</span><h2>Tools for the full examination journey.</h2></div><p>From the first question to the final result, keep every part of your learning and assessment workflow connected.</p></div>
          <div className="feature-grid">
            {features.map(({ icon: Icon, title, description, label, tone }) => <article className="feature-card academic-card" key={title}><span className={`feature-icon ${tone}`}><Icon size={20} /></span><span className="feature-label">{label}</span><h3>{title}</h3><p>{description}</p><Link href={user ? '/dashboard' : '/register'} aria-label={`Explore ${title}`}>Explore feature <ArrowUpRight size={15} /></Link></article>)}
          </div>
        </section>

        <section className="closing-banner">
          <div className="closing-icon"><Zap size={22} /></div>
          <div><span className="eyebrow">MAKE YOUR NEXT ATTEMPT COUNT</span><h2>A little more clarity. A lot more confidence.</h2><p>Build a steady practice routine and turn every assessment into a useful next step.</p></div>
          <Link href={user ? '/dashboard' : '/register'}>{user ? 'Open workspace' : 'Get started'} <ArrowRight size={16} /></Link>
        </section>
      </div>
    </main>
  );
}
