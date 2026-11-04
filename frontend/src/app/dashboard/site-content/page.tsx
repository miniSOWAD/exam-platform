'use client';

import { ChangeEvent, FormEvent, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft, CheckCircle2, Globe2, ImagePlus, Save, ShieldCheck, UserRound } from 'lucide-react';
import { api, isUnauthorizedError } from '@/lib/api';
import { useSiteContent } from '@/components/SiteContentProvider';

type FeatureCard = { label: string; title: string; description: string };
type SiteContent = {
  brand_name: string; ribbon_text: string; ribbon_right_text: string; hero_eyebrow: string;
  hero_title: string; hero_highlight: string; hero_description: string; hero_primary_cta: string; hero_secondary_cta: string;
  upcoming_title: string; upcoming_subtitle: string; calendar_title: string; calendar_subtitle: string;
  leaderboard_title: string; leaderboard_subtitle: string; features_title: string; features_subtitle: string;
  owner_profile_kicker: string; owner_expertise_heading: string; owner_name: string; owner_role: string; owner_bio: string; owner_education: string; owner_institution: string;
  owner_expertise: string[]; owner_avatar_url: string; owner_email: string; owner_phone: string; owner_website: string;
  owner_social_links: Record<string, string>; subjects: string[]; feature_cards: FeatureCard[]; footer_text: string;
};
type User = { id: string; full_name: string; role: string };

const defaults: SiteContent = {
  brand_name: 'ExamFlow', ribbon_text: 'A calmer space for focused exam preparation', ribbon_right_text: 'Mathematics · Physics · Chemistry · Biology',
  hero_eyebrow: 'EXAMINATION PREPARATION, REIMAGINED', hero_title: 'Prepare with purpose.', hero_highlight: 'Perform with confidence.',
  hero_description: 'A thoughtful workspace for creating exams, practicing what matters and understanding every result across Mathematics, Physics, Chemistry and Biology.',
  hero_primary_cta: 'Create student account', hero_secondary_cta: 'Sign in',
  upcoming_title: 'Live & upcoming exams', upcoming_subtitle: 'Find an assessment and check your preparation.',
  calendar_title: 'University exam calendar', calendar_subtitle: 'Keep your academic schedule in view and make room for consistent practice.',
  leaderboard_title: 'Leaderboard', leaderboard_subtitle: 'See how students performed in published examinations.',
  features_title: 'Tools for the full examination journey.', features_subtitle: 'From the first question to the final result, keep every part of your learning and assessment workflow connected.',
  owner_profile_kicker: 'SITE OWNER', owner_expertise_heading: 'Areas of expertise',
  owner_name: 'Md Mahruf Alam', owner_role: 'Site Owner · Tutor & Examiner', owner_bio: 'I am Md Mahruf Alam, the owner of ExamFlow. I help learners prepare through structured examinations, tutoring and clear performance feedback.',
  owner_education: '', owner_institution: '', owner_expertise: ['Mathematics', 'Physics', 'Chemistry', 'Biology'], owner_avatar_url: '', owner_email: '', owner_phone: '', owner_website: '',
  owner_social_links: {}, subjects: ['Mathematics', 'Physics', 'Chemistry', 'Biology'], feature_cards: [
    { label: 'Exam builder', title: 'Build better assessments', description: 'Create question sets, configure marks and organize exams by subject, chapter and set.' },
    { label: 'Live control', title: 'Manage live examinations', description: 'Start, pause and resume exams with a server-controlled timer and reliable answer saving.' },
    { label: 'Performance', title: 'Understand every result', description: 'Review scores, compare published rankings and follow performance across attempts.' }
  ], footer_text: 'Built for focused learning and fair assessment.'
};

function Field({ label, value, onChange, placeholder, type = 'text' }: { label: string; value: string; onChange: (value: string) => void; placeholder?: string; type?: string }) {
  return <label className="block text-sm font-semibold text-slate-700">{label}<input className="field mt-2 font-normal" type={type} value={value} placeholder={placeholder} onChange={(event) => onChange(event.target.value)} /></label>;
}

export default function SiteContentPage() {
  const router = useRouter();
  const { refreshSiteContent } = useSiteContent();
  const [site, setSite] = useState<SiteContent>(defaults);
  const [subjectsText, setSubjectsText] = useState('Mathematics\nPhysics\nChemistry\nBiology');
  const [expertiseText, setExpertiseText] = useState('Mathematics\nPhysics\nChemistry\nBiology');
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [ownerPhotoUploading, setOwnerPhotoUploading] = useState(false);
  const [ownerPhotoMessage, setOwnerPhotoMessage] = useState('');
  const [ownerPhotoError, setOwnerPhotoError] = useState('');

  useEffect(() => {
    let active = true;
    Promise.all([api<User>('/auth/me'), api<SiteContent>('/site/content')]).then(([current, content]) => {
      if (!active) return;
      if (current.role !== 'admin') { router.replace('/dashboard'); return; }
      setUser(current); setSite({ ...defaults, ...content });
      setSubjectsText((content.subjects || []).join('\n'));
      setExpertiseText((content.owner_expertise || []).join('\n'));
    }).catch((error: unknown) => {
      if (!active) return;
      if (isUnauthorizedError(error)) router.replace('/login?next=%2Fdashboard%2Fsite-content');
      else setError(error instanceof Error ? error.message : 'Could not load website settings.');
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [router]);

  function patch<K extends keyof SiteContent>(key: K, value: SiteContent[K]) { setSite((current) => ({ ...current, [key]: value })); }
  function patchFeature(index: number, key: keyof FeatureCard, value: string) {
    const cards = [...site.feature_cards];
    cards[index] = { ...cards[index], [key]: value };
    patch('feature_cards', cards);
  }
  function addFeature() { patch('feature_cards', [...site.feature_cards, { label: 'New feature', title: 'New homepage feature', description: 'Describe this ExamFlow feature for visitors.' }]); }
  function removeFeature(index: number) { patch('feature_cards', site.feature_cards.filter((_, cardIndex) => cardIndex !== index)); }

  async function uploadOwnerPhoto(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = '';
    setOwnerPhotoError(''); setOwnerPhotoMessage('');
    if (!file) return;
    if (!['image/jpeg', 'image/png', 'image/webp', 'image/jpg'].includes(file.type)) {
      setOwnerPhotoError('Choose a JPG, PNG or WebP image.'); return;
    }
    if (file.size > 300 * 1024) {
      setOwnerPhotoError('The owner photo must be 300 KB or smaller.'); return;
    }
    setOwnerPhotoUploading(true);
    try {
      const form = new FormData(); form.append('file', file);
      const result = await api<{ owner_avatar_url: string }>('/site/content/owner-avatar', { method: 'POST', body: form });
      patch('owner_avatar_url', result.owner_avatar_url);
      await refreshSiteContent();
      setOwnerPhotoMessage('Owner photo uploaded to Cloudinary. Save the rest of your website changes when ready.');
    } catch (err) {
      setOwnerPhotoError(err instanceof Error ? err.message : 'Could not upload the owner photo.');
    } finally { setOwnerPhotoUploading(false); }
  }

  async function save(event: FormEvent) {
    event.preventDefault(); setSaving(true); setError(''); setMessage('');
    const subjects = subjectsText.split('\n').map((x) => x.trim()).filter(Boolean).slice(0, 20);
    const owner_expertise = expertiseText.split('\n').map((x) => x.trim()).filter(Boolean).slice(0, 20);
    try {
      const updated = await api<SiteContent>('/site/content', { method: 'PUT', body: JSON.stringify({ ...site, subjects, owner_expertise }) });
      setSite({ ...defaults, ...updated }); setSubjectsText((updated.subjects || []).join('\n')); setExpertiseText((updated.owner_expertise || []).join('\n'));
      await refreshSiteContent();
      setMessage('Website content saved. The public homepage will now show these updates.');
    } catch (err) { setError(err instanceof Error ? err.message : 'Could not save website content.'); }
    finally { setSaving(false); }
  }

  if (loading) return <main className="container-shell py-20">Loading website editor…</main>;
  if (!user) return <main className="container-shell py-20"><p role="alert" className="text-sm text-red-700">{error || 'Website settings could not be loaded.'}</p></main>;

  return <main className="container-shell py-9">
    <Link href="/dashboard" className="inline-flex items-center gap-2 text-sm font-bold text-slate-500 hover:text-brand"><ArrowLeft size={16}/> Back to dashboard</Link>
    <div className="mt-6 flex flex-wrap items-end justify-between gap-4"><div><p className="text-xs font-black tracking-[.18em] text-teal-700">ADMIN · PUBLIC WEBSITE</p><h1 className="mt-2 text-3xl font-bold">Website content manager</h1><p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">Manage the site identity, homepage introduction and the public profile of Md Mahruf Alam. This profile belongs to the site owner, not to the signed-in student.</p></div><span className="rounded-full bg-emerald-50 px-3 py-2 text-xs font-bold text-emerald-700"><ShieldCheck className="mr-1 inline" size={14}/> Admin only</span></div>
    {error && <p role="alert" className="mt-5 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</p>}
    {message && <p role="status" className="mt-5 rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800"><CheckCircle2 className="mr-2 inline" size={16}/>{message}</p>}
    <form onSubmit={save} className="mt-7 space-y-6">
      <section className="card p-6"><div className="mb-5 flex items-center gap-3"><Globe2 className="text-teal-700"/><div><h2 className="text-xl font-bold">Site identity and homepage</h2><p className="text-xs text-slate-500">Branding, top ribbon and main introduction.</p></div></div>
        <div className="grid gap-4 md:grid-cols-2"><Field label="Site / brand name" value={site.brand_name} onChange={(v)=>patch('brand_name',v)}/><Field label="Top ribbon message" value={site.ribbon_text} onChange={(v)=>patch('ribbon_text',v)}/><Field label="Top ribbon right text" value={site.ribbon_right_text} onChange={(v)=>patch('ribbon_right_text',v)}/><Field label="Hero eyebrow" value={site.hero_eyebrow} onChange={(v)=>patch('hero_eyebrow',v)}/><Field label="Main headline" value={site.hero_title} onChange={(v)=>patch('hero_title',v)}/><Field label="Highlighted headline" value={site.hero_highlight} onChange={(v)=>patch('hero_highlight',v)}/></div>
        <label className="mt-4 block text-sm font-semibold text-slate-700">Homepage introduction<textarea className="field mt-2 min-h-28 font-normal" value={site.hero_description} onChange={(e)=>patch('hero_description',e.target.value)}/></label>
        <div className="mt-4 grid gap-4 md:grid-cols-2"><Field label="Primary button label" value={site.hero_primary_cta} onChange={(v)=>patch('hero_primary_cta',v)}/><Field label="Secondary button label" value={site.hero_secondary_cta} onChange={(v)=>patch('hero_secondary_cta',v)}/></div>
      </section>
      <section className="card p-6"><div className="mb-5 flex items-center gap-3"><UserRound className="text-teal-700"/><div><h2 className="text-xl font-bold">Site owner profile</h2><p className="text-xs text-slate-500">This is the permanent owner introduction shown in the left profile rail.</p></div></div>
        <div className="grid gap-4 md:grid-cols-2"><Field label="Owner profile section label" value={site.owner_profile_kicker} onChange={(v)=>patch('owner_profile_kicker',v)}/><Field label="Expertise section heading" value={site.owner_expertise_heading} onChange={(v)=>patch('owner_expertise_heading',v)}/><Field label="Owner name" value={site.owner_name} onChange={(v)=>patch('owner_name',v)}/><Field label="Owner designation" value={site.owner_role} onChange={(v)=>patch('owner_role',v)}/><Field label="Education / qualification" value={site.owner_education} onChange={(v)=>patch('owner_education',v)}/><Field label="Institution" value={site.owner_institution} onChange={(v)=>patch('owner_institution',v)}/><div className="space-y-2"><Field label="Profile image URL" type="url" placeholder="https://..." value={site.owner_avatar_url} onChange={(v)=>patch('owner_avatar_url',v)}/><div className="flex flex-wrap items-center gap-3">{site.owner_avatar_url && <img src={site.owner_avatar_url} alt="Owner profile preview" className="h-14 w-14 rounded-2xl border border-slate-200 object-cover"/>}<label className="inline-flex cursor-pointer items-center gap-2 rounded-xl border border-teal-200 bg-teal-50 px-3 py-2 text-xs font-bold text-teal-800"><ImagePlus size={14}/>{ownerPhotoUploading ? 'Uploading…' : 'Upload owner photo'}<input type="file" accept="image/jpeg,image/png,image/webp" className="sr-only" disabled={ownerPhotoUploading} onChange={uploadOwnerPhoto}/></label><span className="text-[11px] text-slate-400">JPG, PNG or WebP · 300 KB maximum</span></div>{ownerPhotoError && <p role="alert" className="text-xs text-red-600">{ownerPhotoError}</p>}{ownerPhotoMessage && <p role="status" className="text-xs text-emerald-700">{ownerPhotoMessage}</p>}</div><Field label="Public contact email" type="email" value={site.owner_email} onChange={(v)=>patch('owner_email',v)}/><Field label="Public contact phone" type="tel" value={site.owner_phone} onChange={(v)=>patch('owner_phone',v)}/><Field label="Website URL" type="url" value={site.owner_website} onChange={(v)=>patch('owner_website',v)}/></div>
        <label className="mt-4 block text-sm font-semibold text-slate-700">Owner introduction / biography<textarea className="field mt-2 min-h-32 font-normal" value={site.owner_bio} onChange={(e)=>patch('owner_bio',e.target.value)}/></label>
        <label className="mt-4 block text-sm font-semibold text-slate-700">Teaching and examination expertise <span className="font-normal text-slate-400">(one per line)</span><textarea className="field mt-2 min-h-24 font-normal" value={expertiseText} onChange={(e)=>setExpertiseText(e.target.value)}/></label>
        <div className="mt-4 grid gap-4 md:grid-cols-2">{(['linkedin','facebook','instagram','youtube','github'] as const).map((key)=><div key={key}><Field label={`${key[0].toUpperCase()}${key.slice(1)} profile URL`} type="url" value={site.owner_social_links?.[key] || ''} onChange={(v)=>patch('owner_social_links',{...site.owner_social_links,[key]:v})}/></div>)}</div>
      </section>
      <section className="card p-6"><div className="mb-5 flex items-center gap-3"><ImagePlus className="text-teal-700"/><div><h2 className="text-xl font-bold">Homepage sections and features</h2><p className="text-xs text-slate-500">Control the subject labels, section headings, descriptions and feature cards.</p></div></div>
        <div className="grid gap-4 md:grid-cols-2">
          <Field label="Upcoming exams heading" value={site.upcoming_title} onChange={(v)=>patch('upcoming_title',v)}/>
          <Field label="Calendar heading" value={site.calendar_title} onChange={(v)=>patch('calendar_title',v)}/>
          <Field label="Leaderboard heading" value={site.leaderboard_title} onChange={(v)=>patch('leaderboard_title',v)}/>
          <Field label="Features heading" value={site.features_title} onChange={(v)=>patch('features_title',v)}/>
        </div>
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <label className="block text-sm font-semibold text-slate-700">Upcoming exams description<textarea className="field mt-2 min-h-20 font-normal" value={site.upcoming_subtitle} onChange={(e)=>patch('upcoming_subtitle',e.target.value)}/></label>
          <label className="block text-sm font-semibold text-slate-700">Calendar description<textarea className="field mt-2 min-h-20 font-normal" value={site.calendar_subtitle} onChange={(e)=>patch('calendar_subtitle',e.target.value)}/></label>
          <label className="block text-sm font-semibold text-slate-700">Leaderboard description<textarea className="field mt-2 min-h-20 font-normal" value={site.leaderboard_subtitle} onChange={(e)=>patch('leaderboard_subtitle',e.target.value)}/></label>
          <label className="block text-sm font-semibold text-slate-700">Features description<textarea className="field mt-2 min-h-20 font-normal" value={site.features_subtitle} onChange={(e)=>patch('features_subtitle',e.target.value)}/></label>
        </div>
        <label className="block text-sm font-semibold text-slate-700">Subjects shown on the homepage <span className="font-normal text-slate-400">(one per line)</span><textarea className="field mt-2 min-h-24 font-normal" value={subjectsText} onChange={(e)=>setSubjectsText(e.target.value)}/></label>
        <div className="mt-5 space-y-4">{site.feature_cards.map((card,index)=><div key={index} className="rounded-2xl border border-slate-100 bg-slate-50/70 p-4"><div className="mb-3 flex items-center justify-between"><p className="text-xs font-black uppercase tracking-wider text-teal-700">Feature card {index+1}</p><button type="button" onClick={()=>removeFeature(index)} className="text-xs font-bold text-red-600">Remove card</button></div><div className="grid gap-3 md:grid-cols-2"><Field label="Small label" value={card.label || ''} onChange={(v)=>patchFeature(index,'label',v)}/><Field label="Card title" value={card.title || ''} onChange={(v)=>patchFeature(index,'title',v)}/></div><label className="mt-3 block text-sm font-semibold text-slate-700">Description<textarea className="field mt-2 min-h-20 font-normal" value={card.description || ''} onChange={(e)=>patchFeature(index,'description',e.target.value)}/></label></div>)}</div>
        <button type="button" onClick={addFeature} className="mt-4 rounded-xl border border-teal-200 bg-teal-50 px-4 py-2 text-sm font-bold text-teal-800">+ Add homepage feature card</button>
      </section>
      <section className="card p-6"><h2 className="text-xl font-bold">Footer</h2><Field label="Footer message" value={site.footer_text} onChange={(v)=>patch('footer_text',v)}/></section>
      <div className="sticky bottom-4 flex justify-end"><button className="btn shadow-lg" disabled={saving}>{saving ? 'Saving website…' : <><Save className="mr-2" size={16}/>Save all website changes</>}</button></div>
    </form>
  </main>;
}
