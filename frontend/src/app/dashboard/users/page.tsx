'use client';

import { FormEvent, useCallback, useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  Users, UserPlus, Search, ShieldCheck, GraduationCap, Ban, CheckCircle2,
  ArrowUpCircle, ArrowDownCircle, Trash2, Loader2, RefreshCw,
} from 'lucide-react';
import { api, isUnauthorizedError } from '@/lib/api';

type ManagedUser = {
  id: string; full_name: string; email: string; role: 'student' | 'moderator';
  active: boolean; avatar_url?: string | null; created_at?: string | null;
};
type RoleTab = 'student' | 'moderator';

function dateLabel(value?: string | null) {
  return value ? new Date(value).toLocaleDateString() : '—';
}

export default function UserManagementPage() {
  const router = useRouter();
  const [tab, setTab] = useState<RoleTab>('student');
  const [users, setUsers] = useState<ManagedUser[]>([]);
  const [authorized, setAuthorized] = useState(false);
  const [search, setSearch] = useState('');
  const [includeInactive, setIncludeInactive] = useState(true);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  const loadUsers = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const params = new URLSearchParams({ role: tab, include_inactive: String(includeInactive) });
      if (search.trim()) params.set('search', search.trim());
      const rows = await api<ManagedUser[]>(`/admin/users?${params.toString()}`);
      setUsers(rows);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Could not load users.';
      if (message.includes('Admin only') || message.includes('Permission')) router.replace('/dashboard');
      else setError(message);
    } finally { setLoading(false); }
  }, [tab, search, includeInactive, router]);

  useEffect(() => {
    let active = true;
    api<{ role: string }>('/auth/me').then((user) => {
      if (!active) return;
      if (user.role !== 'admin') router.replace('/dashboard');
      else setAuthorized(true);
    }).catch((error: unknown) => {
      if (!active) return;
      if (isUnauthorizedError(error)) router.replace('/login?next=%2Fdashboard%2Fusers');
      else setError(error instanceof Error ? error.message : 'Could not verify administrator access.');
      setLoading(false);
    });
    return () => { active = false; };
  }, [router]);

  useEffect(() => {
    if (authorized) void loadUsers();
  }, [authorized, loadUsers]);

  const activeCount = useMemo(() => users.filter((user) => user.active).length, [users]);

  async function createUser(event: FormEvent) {
    event.preventDefault();
    setCreating(true); setError(''); setNotice('');
    try {
      await api('/admin/users', { method: 'POST', body: JSON.stringify({
        full_name: fullName.trim(), email: email.trim(), password, role: tab,
      }) });
      setFullName(''); setEmail(''); setPassword('');
      setNotice(`${tab === 'student' ? 'Student' : 'Moderator'} account created successfully.`);
      await loadUsers();
    } catch (err) { setError(err instanceof Error ? err.message : 'Could not create this account.'); }
    finally { setCreating(false); }
  }

  async function updateStatus(target: ManagedUser) {
    setSaving(true); setError(''); setNotice('');
    try {
      await api(`/admin/users/${target.id}/status`, { method: 'PATCH', body: JSON.stringify({ active: !target.active }) });
      setNotice(target.active ? `${target.full_name} has been blocked.` : `${target.full_name} has been unblocked.`);
      await loadUsers();
    } catch (err) { setError(err instanceof Error ? err.message : 'Could not update account status.'); }
    finally { setSaving(false); }
  }

  async function changeRole(target: ManagedUser) {
    const nextRole = target.role === 'student' ? 'moderator' : 'student';
    const action = nextRole === 'moderator' ? 'promote' : 'demote';
    if (!window.confirm(`${action === 'promote' ? 'Promote' : 'Demote'} ${target.full_name} to ${nextRole}? ${nextRole === 'moderator' ? 'The new moderator will have no permissions until you grant them.' : 'Moderator permissions will be removed.'}`)) return;
    setSaving(true); setError(''); setNotice('');
    try {
      await api(`/admin/users/${target.id}/role`, { method: 'PATCH', body: JSON.stringify({ role: nextRole }) });
      setNotice(`${target.full_name} is now a ${nextRole}.`);
      await loadUsers();
    } catch (err) { setError(err instanceof Error ? err.message : 'Could not change user role.'); }
    finally { setSaving(false); }
  }

  async function removeUser(target: ManagedUser) {
    const confirmed = window.confirm(`Permanently remove ${target.full_name} (${target.email})? Their account and personal exam attempts will be deleted. Exams they created will remain under the administrator account.`);
    if (!confirmed) return;
    setSaving(true); setError(''); setNotice('');
    try {
      await api(`/admin/users/${target.id}`, { method: 'DELETE' });
      setNotice(`${target.full_name} was removed.`);
      await loadUsers();
    } catch (err) { setError(err instanceof Error ? err.message : 'Could not remove this account.'); }
    finally { setSaving(false); }
  }

  return <main className="container-shell py-9">
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div><p className="text-xs font-black uppercase tracking-[.18em] text-brand">ADMIN CONTROL PANEL</p><h1 className="mt-2 text-3xl font-black">User management</h1><p className="mt-2 text-slate-500">Create, block, remove and change the roles of students and moderators.</p></div>
      <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm"><span className="text-slate-500">Visible active accounts</span><strong className="ml-2 text-xl">{activeCount}</strong></div>
    </div>

    <div className="mt-7 flex flex-wrap gap-2" role="tablist" aria-label="User roles">
      <button type="button" role="tab" aria-selected={tab === 'student'} onClick={() => setTab('student')} className={`admin-tab ${tab === 'student' ? 'is-active' : ''}`}><GraduationCap size={17}/>Students</button>
      <button type="button" role="tab" aria-selected={tab === 'moderator'} onClick={() => setTab('moderator')} className={`admin-tab ${tab === 'moderator' ? 'is-active' : ''}`}><ShieldCheck size={17}/>Moderators</button>
    </div>

    {error && <p role="alert" className="mt-4 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</p>}
    {notice && <p role="status" className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">{notice}</p>}

    <section className="card mt-5 p-5 md:p-6">
      <div className="mb-4 flex items-center gap-3"><span className="rounded-xl bg-blue-50 p-3 text-brand"><UserPlus size={20}/></span><div><h2 className="text-lg font-black">Create {tab === 'student' ? 'student' : 'moderator'}</h2><p className="text-xs text-slate-500">The account can sign in immediately using the credentials you set.{tab === 'moderator' ? ' New moderators start with no permissions until the admin grants access.' : ''}</p></div></div>
      <form onSubmit={createUser} className="grid gap-3 md:grid-cols-2 xl:grid-cols-[1fr_1fr_1fr_auto]">
        <input className="field" placeholder="Full name" minLength={2} maxLength={160} required value={fullName} onChange={(event) => setFullName(event.target.value)}/>
        <input className="field" type="email" placeholder="Email address" required value={email} onChange={(event) => setEmail(event.target.value)}/>
        <input className="field" type="password" placeholder="Initial password (10+ characters)" minLength={10} maxLength={128} required value={password} onChange={(event) => setPassword(event.target.value)}/>
        <button className="btn" disabled={creating}>{creating ? <><Loader2 className="mr-2 animate-spin" size={16}/>Creating…</> : 'Create account'}</button>
      </form>
    </section>

    <section className="card mt-5 overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 p-4 md:p-5">
        <div><h2 className="font-black">{tab === 'student' ? 'Students' : 'Moderators'}</h2><p className="mt-1 text-xs text-slate-500">{users.length} account(s) found</p></div>
        <button type="button" onClick={() => void loadUsers()} className="rounded-xl border border-slate-200 bg-white p-2.5 text-slate-600 hover:bg-slate-50" aria-label="Refresh users"><RefreshCw size={17}/></button>
      </div>
      <div className="grid gap-3 border-b border-slate-100 p-4 md:grid-cols-[1fr_auto] md:items-center">
        <label className="relative block"><Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16}/><input className="field pl-10" placeholder="Search by name or email" value={search} onChange={(event) => setSearch(event.target.value)}/></label>
        <label className="flex items-center gap-2 text-sm text-slate-600"><input type="checkbox" checked={includeInactive} onChange={(event) => setIncludeInactive(event.target.checked)}/>Show blocked accounts</label>
      </div>
      <div className="divide-y divide-slate-100">
        {loading ? <div className="p-10 text-center text-sm text-slate-500"><Loader2 className="mr-2 inline animate-spin" size={17}/>Loading users…</div> : users.map((target) => <article key={target.id} className="flex flex-col gap-4 p-4 md:flex-row md:items-center md:justify-between md:p-5">
          <div className="flex min-w-0 items-center gap-3">
            <span className="grid h-11 w-11 shrink-0 place-items-center overflow-hidden rounded-2xl bg-blue-50 font-black text-brand">{target.avatar_url ? <img src={target.avatar_url} alt="" className="h-full w-full object-cover"/> : target.full_name.split(/\s+/).slice(0,2).map((part) => part[0]).join('').toUpperCase()}</span>
            <div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><strong className="truncate">{target.full_name}</strong><span className={`rounded-full px-2 py-1 text-[10px] font-bold ${target.active ? 'bg-emerald-50 text-emerald-700' : 'bg-red-50 text-red-700'}`}>{target.active ? 'Active' : 'Blocked'}</span></div><p className="mt-1 break-all text-sm text-slate-500">{target.email}</p><p className="mt-1 text-[11px] text-slate-400">Joined {dateLabel(target.created_at)}</p></div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button type="button" disabled={saving} onClick={() => void updateStatus(target)} className="admin-action-button">{target.active ? <><Ban size={14}/>Block</> : <><CheckCircle2 size={14}/>Unblock</>}</button>
            <button type="button" disabled={saving} onClick={() => void changeRole(target)} className="admin-action-button">{target.role === 'student' ? <><ArrowUpCircle size={14}/>Promote</> : <><ArrowDownCircle size={14}/>Demote</>}</button>
            <button type="button" disabled={saving} onClick={() => void removeUser(target)} className="admin-action-button danger"><Trash2 size={14}/>Remove</button>
          </div>
        </article>)}
        {!loading && users.length === 0 && <div className="p-12 text-center"><Users className="mx-auto text-slate-300" size={28}/><p className="mt-3 font-bold">No {tab === 'student' ? 'students' : 'moderators'} found</p><p className="mt-1 text-sm text-slate-500">Create an account above or change your search.</p></div>}
      </div>
    </section>
  </main>;
}
