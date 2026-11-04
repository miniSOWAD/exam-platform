'use client';

import { ChangeEvent, useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { ArrowLeft, Camera, CheckCircle2, ImagePlus, Trash2, UploadCloud, UserRound } from 'lucide-react';
import { api, isUnauthorizedError } from '@/lib/api';

type User = { id: string; email: string; full_name: string; role: string; avatar_url?: string | null };
const MAX_PHOTO_BYTES = 300 * 1024;

export default function ProfilePage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    api<User>('/auth/me').then((data) => { if (active) setUser(data); }).catch((error: unknown) => {
      if (!active) return;
      if (isUnauthorizedError(error)) router.replace('/login?next=%2Fdashboard%2Fprofile');
      else setError(error instanceof Error ? error.message : 'Could not load your profile.');
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [router]);

  useEffect(() => {
    if (!file) { setPreview(user?.avatar_url || ''); return; }
    const objectUrl = URL.createObjectURL(file);
    setPreview(objectUrl);
    return () => URL.revokeObjectURL(objectUrl);
  }, [file, user?.avatar_url]);

  function choosePhoto(event: ChangeEvent<HTMLInputElement>) {
    const selected = event.target.files?.[0] || null;
    event.target.value = '';
    setError(''); setMessage('');
    if (!selected) return;
    if (!['image/jpeg', 'image/png', 'image/webp', 'image/jpg'].includes(selected.type)) {
      setError('Choose a JPG, PNG or WebP image.'); return;
    }
    if (selected.size > MAX_PHOTO_BYTES) {
      setError('The photo is larger than 300 KB. Please resize it and try again.'); return;
    }
    setFile(selected);
  }

  async function uploadPhoto() {
    if (!file) return;
    setBusy(true); setError(''); setMessage('');
    try {
      const form = new FormData(); form.append('file', file);
      const updated = await api<User>('/users/me/avatar', { method: 'POST', body: form });
      setUser(updated); setFile(null); setMessage('Your profile photo has been uploaded.');
      window.dispatchEvent(new Event('examflow:auth-changed'));
    } catch (err) { setError(err instanceof Error ? err.message : 'Could not upload your photo.'); }
    finally { setBusy(false); }
  }

  async function removePhoto() {
    setBusy(true); setError(''); setMessage('');
    try {
      const updated = await api<User>('/users/me/avatar', { method: 'DELETE' });
      setUser(updated); setFile(null); setMessage('Your profile photo has been removed.');
      window.dispatchEvent(new Event('examflow:auth-changed'));
    } catch (err) { setError(err instanceof Error ? err.message : 'Could not remove your photo.'); }
    finally { setBusy(false); }
  }

  if (loading) return <main className="container-shell py-20">Loading your profile…</main>;
  if (!user) return <main className="container-shell py-20"><p role="alert" className="text-sm text-red-700">{error || 'Your profile could not be loaded.'}</p></main>;

  return <main className="container-shell max-w-4xl py-10">
    <Link href="/dashboard" className="inline-flex items-center gap-2 text-sm font-bold text-slate-500 hover:text-brand"><ArrowLeft size={16}/> Back to dashboard</Link>
    <div className="mt-6"><p className="text-xs font-black tracking-[.18em] text-teal-700">YOUR ACCOUNT</p><h1 className="mt-2 text-3xl font-bold">Profile and photo</h1><p className="mt-2 text-sm leading-6 text-slate-500">Manage the photo shown beside your name in ExamFlow. Your account photo is separate from the permanent site-owner introduction.</p></div>
    {error && <p role="alert" className="mt-5 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</p>}
    {message && <p role="status" className="mt-5 rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800"><CheckCircle2 className="mr-2 inline" size={16}/>{message}</p>}
    <section className="card mt-7 grid gap-7 p-6 md:grid-cols-[220px_1fr] md:p-8">
      <div className="flex flex-col items-center text-center">
        <div className="grid h-40 w-40 place-items-center overflow-hidden rounded-[2rem] border-4 border-white bg-gradient-to-br from-[#dceef5] to-[#e2f4ed] text-4xl font-black text-[#527d8a] shadow-lg">
          {preview ? <img src={preview} alt="Profile preview" className="h-full w-full object-cover"/> : <span>{user.full_name.split(/\s+/).map((part) => part[0]).slice(0, 2).join('').toUpperCase()}</span>}
        </div>
        <span className="mt-4 inline-flex items-center gap-2 rounded-full bg-teal-50 px-3 py-1.5 text-xs font-bold capitalize text-teal-800"><UserRound size={13}/>{user.role}</span>
      </div>
      <div>
        <h2 className="text-xl font-bold text-slate-900">{user.full_name}</h2>
        <p className="mt-1 text-sm text-slate-500">{user.email}</p>
        <div className="mt-6 rounded-2xl border border-dashed border-teal-200 bg-teal-50/50 p-5">
          <div className="flex items-center gap-2 text-sm font-bold text-slate-800"><ImagePlus size={17} className="text-teal-700"/> Upload a profile photo</div>
          <p className="mt-2 text-xs leading-5 text-slate-500">JPG, PNG or WebP. Maximum file size: <strong>300 KB</strong>. Your image is stored securely in Cloudinary and delivered in an optimized format.</p>
          <label className="mt-4 inline-flex cursor-pointer items-center gap-2 rounded-xl border border-teal-200 bg-white px-4 py-2.5 text-sm font-bold text-teal-800 hover:bg-teal-50"><Camera size={16}/> Choose photo<input type="file" accept="image/jpeg,image/png,image/webp" className="sr-only" onChange={choosePhoto}/></label>
          {file && <p className="mt-3 text-xs font-semibold text-slate-600">Selected: {file.name} · {(file.size / 1024).toFixed(1)} KB</p>}
        </div>
        <div className="mt-5 flex flex-wrap gap-2">
          <button type="button" className="btn" disabled={!file || busy} onClick={uploadPhoto}><UploadCloud size={16} className="mr-2"/>{busy ? 'Please wait…' : 'Upload photo'}</button>
          {user.avatar_url && <button type="button" className="inline-flex items-center rounded-xl border border-red-200 bg-white px-4 py-2 text-sm font-bold text-red-700 hover:bg-red-50" disabled={busy} onClick={removePhoto}><Trash2 size={15} className="mr-2"/>Remove photo</button>}
        </div>
      </div>
    </section>
  </main>;
}
