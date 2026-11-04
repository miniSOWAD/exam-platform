'use client';

import { useState, type FormEvent } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { api } from '@/lib/api';

export default function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const router = useRouter();

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      await api('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) });
      window.dispatchEvent(new Event('examflow:auth-changed'));
      const requested = new URLSearchParams(window.location.search).get('next');
      const destination = requested && requested.startsWith('/') && !requested.startsWith('//')
        ? requested
        : '/dashboard';
      router.replace(destination);
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to sign in');
    } finally {
      setBusy(false);
    }
  }

  return <main className="container-shell grid min-h-[70vh] place-items-center py-14">
    <form onSubmit={submit} className="card w-full max-w-md p-8">
      <p className="text-xs font-bold uppercase tracking-widest text-brand">Welcome back</p>
      <h1 className="mt-2 text-3xl font-black">Sign in</h1>
      <p className="mt-2 text-sm text-slate-500">Access your examination workspace.</p>
      <label className="mt-7 block text-sm font-bold">Email<input className="field mt-2" type="email" autoComplete="username" required value={email} onChange={(event) => setEmail(event.target.value)}/></label>
      <label className="mt-4 block text-sm font-bold">Password<input className="field mt-2" type="password" autoComplete="current-password" required value={password} onChange={(event) => setPassword(event.target.value)}/></label>
      {error && <p role="alert" className="mt-4 text-sm text-red-600">{error}</p>}
      <button disabled={busy} className="btn mt-6 w-full">{busy ? 'Signing in…' : 'Sign in'}</button>
      <p className="mt-5 text-center text-sm text-slate-500">New here? <Link className="font-bold text-brand" href="/register">Create an account</Link></p>
    </form>
  </main>;
}
