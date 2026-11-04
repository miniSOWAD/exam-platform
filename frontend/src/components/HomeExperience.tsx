'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import {
  Activity, ArrowRight, ArrowUpRight, Award, BookOpen, CalendarDays,
  Clock3, FileText, FlaskConical, GraduationCap, Layers3, Linkedin,
  Mail, Medal, Radio, ShieldCheck, Trophy, Zap, Github, Instagram, Facebook, Youtube
} from 'lucide-react';
import { api } from '@/lib/api';
import { useSiteContent } from '@/components/SiteContentProvider';

type User = { id: string; email: string; full_name: string; role: string };
type Exam = {
  id: string; title: string; subject: string; chapter?: string | null; set_name?: string | null;
  status: string; duration_seconds: number; question_count: number; scheduled_start_at?: string | null;
  scheduled_end_at?: string | null;
};
type LeaderboardRow = { rank: number; student: string; score: number; accuracy?: number | null };
const subjectTones = ['subject-blue', 'subject-mint', 'subject-lilac', 'subject-peach'];
const featureIcons = [FileText, Radio, Trophy];
const featureTones = ['feature-blue', 'feature-mint', 'feature-lilac'];

function initials(name?: string) { const parts = name?.trim().split(/\s+/).filter(Boolean) || []; return (parts.length > 1 ? [parts[0], parts[parts.length - 1]] : parts).map((part) => part[0]).join('').toUpperCase() || 'MA'; }
function statusLabel(status: string) { if (status === 'live') return 'Live now'; if (status === 'paused') return 'Temporarily paused'; return 'Upcoming'; }
function formatDate(value?: string | null) { return value ? new Date(value).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }) : ''; }

export default function HomeExperience() {
  const { site } = useSiteContent();
  const [user, setUser] = useState<User | null>(null);
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
    api<User>('/auth/me').then(async (currentUser) => {
      if (!active) return;
      setUser(currentUser);
      try { const rows = await api<Exam[]>('/exams'); if (active) setExams(rows); }
      catch (error) { if (active) setExamError(error instanceof Error ? error.message : 'Examinations could not be loaded.'); }
    }).catch(async () => {
      if (!active) return;
      setUser(null);
      try { const rows = await api<Exam[]>('/public/exams'); if (active) setExams(rows); }
      catch (error) { if (active) setExamError(error instanceof Error ? error.message : 'Examinations could not be loaded.'); }
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  const visibleExams = useMemo(() => exams.filter((exam) => ['live', 'paused', 'published'].includes(exam.status)).sort((a, b) => {
    const priority = (status: string) => status === 'live' ? 0 : status === 'paused' ? 1 : 2;
    if (priority(a.status) !== priority(b.status)) return priority(a.status) - priority(b.status);
    return (a.scheduled_start_at ? new Date(a.scheduled_start_at).getTime() : Infinity) - (b.scheduled_start_at ? new Date(b.scheduled_start_at).getTime() : Infinity);
  }).slice(0, 4), [exams]);
  const publishedExams = useMemo(() => exams.filter((exam) => exam.status === 'results_published'), [exams]);
  const nextScheduledExam = useMemo(() => exams.filter((exam) => exam.scheduled_start_at && ['published', 'live', 'paused'].includes(exam.status)).sort((a,b) => new Date(a.scheduled_start_at!).getTime() - new Date(b.scheduled_start_at!).getTime())[0], [exams]);

  useEffect(() => {
    if (!user || publishedExams.length === 0) { setLeaderboard([]); setLeaderboardExamId(''); return; }
    if (!leaderboardExamId || !publishedExams.some((exam) => exam.id === leaderboardExamId)) setLeaderboardExamId(publishedExams[0].id);
  }, [user, publishedExams, leaderboardExamId]);
  useEffect(() => {
    if (!user || !leaderboardExamId) return;
    let active = true; setLeaderboardLoading(true); setLeaderboardError('');
    api<LeaderboardRow[]>(`/exams/${leaderboardExamId}/leaderboard`).then((rows) => { if (active) setLeaderboard(rows); })
      .catch((error) => { if (active) { setLeaderboard([]); setLeaderboardError(error instanceof Error ? error.message : 'Leaderboard is unavailable.'); } })
      .finally(() => { if (active) setLeaderboardLoading(false); });
    return () => { active = false; };
  }, [user, leaderboardExamId]);

  const calendarCells = useMemo(() => {
    if (!today) return [] as (number | null)[];
    const firstDay = new Date(today.getFullYear(), today.getMonth(), 1).getDay();
    const days = new Date(today.getFullYear(), today.getMonth() + 1, 0).getDate();
    return [...Array.from({ length: firstDay }, () => null), ...Array.from({ length: days }, (_, index) => index + 1)];
  }, [today]);
  const scheduledDays = useMemo(() => new Set(exams.filter((exam) => exam.scheduled_start_at).map((exam) => {
    const date = new Date(exam.scheduled_start_at!);
    return today && date.getFullYear() === today.getFullYear() && date.getMonth() === today.getMonth() ? date.getDate() : -1;
  })), [exams, today]);
  const monthLabel = today ? today.toLocaleDateString('en-US', { month: 'long', year: 'numeric' }) : 'Academic calendar';
  const social = site.owner_social_links || {};
  const socialItems = [
    { key: 'linkedin', label: 'LinkedIn', icon: Linkedin }, { key: 'facebook', label: 'Facebook', icon: Facebook },
    { key: 'instagram', label: 'Instagram', icon: Instagram }, { key: 'youtube', label: 'YouTube', icon: Youtube }, { key: 'github', label: 'GitHub', icon: Github }
  ].filter((item) => social[item.key]);

  return (
    <main className="academic-page">
      <div className="academic-shell">
        <div className="home-grid">
          <aside className="profile-rail" id="owner">
            <section className="profile-card owner-profile-card academic-card">
              <div className="profile-card-topline"><span>THE PERSON BEHIND {site.brand_name.toUpperCase()}</span><span className="profile-shield"><ShieldCheck size={16} /></span></div>
              <div className="profile-avatar-wrap">
                <div className="profile-avatar owner-avatar">{site.owner_avatar_url ? <img src={site.owner_avatar_url} alt={`${site.owner_name} profile`} /> : initials(site.owner_name)}</div>
                <span className="avatar-status" aria-label="Site owner profile" />
              </div>
              <p className="profile-kicker">{site.owner_profile_kicker}</p>
              <h2 className="profile-name">{site.owner_name}</h2>
              <p className="profile-role">{site.owner_role}</p>
              <p className="owner-bio">{site.owner_bio}</p>
              {(site.owner_education || site.owner_institution) && <div className="profile-details owner-details">
                {site.owner_education && <div><span>Education</span><strong>{site.owner_education}</strong></div>}
                {site.owner_institution && <div><span>Institution</span><strong>{site.owner_institution}</strong></div>}
              </div>}
              {site.owner_email && <a href={`mailto:${site.owner_email}`} className="profile-action">Email the owner <Mail size={14} /></a>}
              {site.owner_phone && <a href={`tel:${site.owner_phone}`} className="owner-website-link">Call {site.owner_phone}</a>}
              {site.owner_website && <a href={site.owner_website} target="_blank" rel="noreferrer" className="owner-website-link">Personal website <ArrowUpRight size={13}/></a>}
              {socialItems.length > 0 && <div className="owner-socials" aria-label="Owner social profiles">{socialItems.map(({key,label,icon:Icon}) => <a key={key} href={social[key]} target="_blank" rel="noreferrer" aria-label={label} title={label}><Icon size={15}/></a>)}</div>}
            </section>
            <section className="owner-expertise-card academic-card">
              <div className="section-heading compact-heading"><div><span className="eyebrow">TEACHING & EXAMINATION</span><h3>{site.owner_expertise_heading}</h3></div><GraduationCap size={19}/></div>
              <div className="owner-expertise-list">{(site.owner_expertise || []).map((item,index)=><span key={`${item}-${index}`}>{item}</span>)}</div>
              <p className="rail-note">A focused academic space guided by its owner, tutor and examiner.</p>
            </section>
          </aside>

          <section className="hero-panel academic-card">
            <div className="hero-copy">
              <span className="hero-eyebrow"><span className="eyebrow-dot" /> {site.hero_eyebrow}</span>
              <h1>{site.hero_title} <em>{site.hero_highlight}</em></h1>
              <p className="hero-description">{site.hero_description}</p>
              <div className="hero-subjects" id="subjects" aria-label="Supported subjects">{(site.subjects || []).map((subject,index)=><span className={`hero-subject-chip ${subjectTones[index % subjectTones.length]}`} key={`${subject}-${index}`}>{subject}</span>)}</div>
              <div className="hero-actions"><Link href={user ? '/dashboard' : '/register'} className="primary-action">{user ? 'Go to my workspace' : site.hero_primary_cta} <ArrowRight size={17} /></Link><Link href={user ? '/dashboard' : '/login'} className="secondary-action">{user ? 'View examinations' : site.hero_secondary_cta}</Link></div>
              <div className="hero-trust"><ShieldCheck size={16} /><span>Role-based access</span><i /> <span>Server-side scoring</span><i /> <span>PDF question import</span></div>
            </div>
            <div className="hero-visual" aria-label="ExamFlow study overview illustration"><div className="visual-topline"><span>YOUR PREPARATION, ORGANIZED</span><span className="visual-live"><span /> Focus mode</span></div><div className="visual-main"><div className="visual-copy"><span className="visual-label">A clearer way to prepare</span><strong>Learn. Practice.<br />Improve.</strong><p>Make each attempt count.</p></div><div className="visual-orbit orbit-one" /><div className="visual-orbit orbit-two" /><div className="visual-mark"><BookOpen size={30} strokeWidth={1.5} /></div></div><div className="visual-bottom"><span><b>{String(site.subjects.length).padStart(2,'0')}</b> core subjects</span><span><b>04</b> question formats</span><span><b>01</b> focused workspace</span></div></div>
            <div className="hero-decor hero-decor-one" /><div className="hero-decor hero-decor-two" />
          </section>

          <aside className="upcoming-panel academic-card">
            <div className="section-heading"><div><span className="eyebrow">TAKE THE NEXT STEP</span><h2>{site.upcoming_title}</h2></div><span className="heading-icon"><Radio size={18} /></span></div>
            <p className="section-subtitle">{site.upcoming_subtitle}</p>
            {loading ? <div className="skeleton-list"><span/><span/><span/></div> : visibleExams.length ? <div className="exam-list">{visibleExams.map((exam)=><article className="exam-list-item" key={exam.id}><div className="exam-item-top"><span className="exam-subject">{exam.subject || 'General'}</span><span className={`exam-status status-${exam.status}`}>{exam.status==='live'&&<i/>}{statusLabel(exam.status)}</span></div><h3>{exam.title}</h3><p className="exam-meta">{[exam.chapter,exam.set_name].filter(Boolean).join(' · ') || `${exam.question_count} questions`}</p>{exam.scheduled_start_at&&<p className="exam-schedule-meta"><CalendarDays size={12}/>{formatDate(exam.scheduled_start_at)}</p>}<div className="exam-item-bottom"><span><Clock3 size={13}/> {Math.round(exam.duration_seconds/60)} min</span><Link href={user ? `/exams/${exam.id}` : '/login'}>{exam.status==='live'?'Enter exam':user?'View details':'Sign in to participate'} <ArrowUpRight size={13}/></Link></div></article>)}</div> : <div className="empty-state"><span className="empty-icon"><CalendarDays size={20}/></span><strong>No upcoming exams yet</strong><p>{examError || 'Published and scheduled examinations will appear here.'}</p></div>}
            <Link href={user ? '/dashboard' : '/register'} className="panel-footer-link">{user ? 'View all examinations' : 'Join ExamFlow'} <ArrowUpRight size={15}/></Link>
          </aside>

          <section className="calendar-panel academic-card" id="calendar"><div className="section-heading"><div><span className="eyebrow">PLAN YOUR PREPARATION</span><h2>{site.calendar_title}</h2></div><span className="heading-icon"><CalendarDays size={18}/></span></div><p className="section-subtitle">{site.calendar_subtitle}</p><div className="calendar-content"><div className="mini-calendar"><div className="calendar-month"><strong>{monthLabel}</strong><span>MONTH VIEW</span></div><div className="calendar-weekdays">{['S','M','T','W','T','F','S'].map((day,index)=><span key={`${day}-${index}`}>{day}</span>)}</div><div className="calendar-days">{calendarCells.map((day,index)=>day?<span key={`${day}-${index}`} className={`${today&&day===today.getDate()?'calendar-today':''} ${scheduledDays.has(day)?'calendar-exam-day':''}`} title={scheduledDays.has(day)?'Scheduled examination':''}>{day}</span>:<i key={`blank-${index}`}/>)}</div><div className="calendar-legend"><span><i/> Today</span><span><i className="legend-event"/> Exam dates</span></div></div><div className="calendar-message"><span className="calendar-message-icon"><GraduationCap size={21}/></span><div><strong>{nextScheduledExam ? nextScheduledExam.title : 'Your academic schedule starts here'}</strong><p>{nextScheduledExam?.scheduled_start_at ? `Scheduled for ${formatDate(nextScheduledExam.scheduled_start_at)}. Exam dates are managed by the site administrator.` : 'Exam dates will appear here when the administrator schedules upcoming examinations.'}</p></div><Link href={user?'/dashboard':'/login'} className="text-action">{user?'Open workspace':'Sign in'} <ArrowRight size={14}/></Link></div></div></section>

          <section className="leaderboard-panel academic-card" id="leaderboard"><div className="section-heading"><div><span className="eyebrow">CELEBRATE PROGRESS</span><h2>{site.leaderboard_title}</h2></div><span className="heading-icon"><Trophy size={18}/></span></div><p className="section-subtitle">{site.leaderboard_subtitle}</p>{!user?<div className="empty-state compact-empty"><span className="empty-icon"><Trophy size={20}/></span><strong>Results worth celebrating</strong><p>Sign in to explore published exam rankings.</p><Link href="/login" className="text-action">Sign in to view <ArrowRight size={14}/></Link></div>:publishedExams.length===0?<div className="empty-state compact-empty"><span className="empty-icon"><Medal size={20}/></span><strong>No published rankings yet</strong><p>Once results are published, the top performers will appear here.</p></div>:<><label className="leaderboard-select-label" htmlFor="leaderboard-exam">Choose examination</label><select id="leaderboard-exam" className="leaderboard-select" value={leaderboardExamId} onChange={(event)=>setLeaderboardExamId(event.target.value)}>{publishedExams.map((exam)=><option key={exam.id} value={exam.id}>{exam.title}</option>)}</select>{leaderboardLoading?<div className="skeleton-list"><span/><span/><span/></div>:leaderboard.length?<div className="leaderboard-list">{leaderboard.slice(0,5).map((row)=><div className="leaderboard-row" key={`${row.rank}-${row.student}`}><span className={`rank-medal rank-${row.rank}`}>{row.rank===1?<Trophy size={15}/>:row.rank===2?<Medal size={15}/>:row.rank===3?<Award size={15}/>:row.rank}</span><span className="leaderboard-student">{row.student}</span><span className="leaderboard-score"><strong>{row.score}</strong><small>{row.accuracy === null || row.accuracy === undefined ? "" : `${row.accuracy.toFixed(1)}% accuracy`}</small></span></div>)}</div>:<p className="leaderboard-empty">{leaderboardError||'No scores are available for this examination yet.'}</p>}{leaderboardExamId&&<Link href={`/leaderboard/${leaderboardExamId}`} className="panel-footer-link">View full leaderboard <ArrowUpRight size={15}/></Link>}</>}</section>
        </div>

        <section className="features-section"><div className="features-intro"><div><span className="eyebrow">EVERYTHING IN ONE PLACE</span><h2>{site.features_title}</h2></div><p>{site.features_subtitle}</p></div><div className="feature-grid">{(site.feature_cards || []).map((feature,index)=>{const Icon=featureIcons[index%featureIcons.length];return <article className="feature-card academic-card" key={`${feature.title}-${index}`}><span className={`feature-icon ${featureTones[index%featureTones.length]}`}><Icon size={20}/></span><span className="feature-label">{feature.label}</span><h3>{feature.title}</h3><p>{feature.description}</p><Link href={user?'/dashboard':'/register'} aria-label={`Explore ${feature.title}`}>Explore feature <ArrowUpRight size={15}/></Link></article>;})}</div></section>
        <section className="closing-banner"><div className="closing-icon"><Zap size={22}/></div><div><span className="eyebrow">MAKE YOUR NEXT ATTEMPT COUNT</span><h2>A little more clarity. A lot more confidence.</h2><p>Build a steady practice routine and turn every assessment into a useful next step.</p></div><Link href={user?'/dashboard':'/register'}>{user?'Open workspace':'Get started'} <ArrowRight size={16}/></Link></section>
      </div>
    </main>
  );
}
