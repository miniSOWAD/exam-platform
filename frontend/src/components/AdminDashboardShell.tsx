'use client';

import { ReactNode, useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import {
  LayoutDashboard, Users, Trophy, Globe2, LogOut, ShieldCheck, Menu, X, RefreshCw,
} from 'lucide-react';
import { api, isUnauthorizedError } from '@/lib/api';

type AdminUser = { id: string; full_name: string; role: string };

const navigation = [
  { href: '/dashboard', label: 'Admin workspace', icon: LayoutDashboard, match: (path: string) => path === '/dashboard' || (path.startsWith('/dashboard/') && !path.startsWith('/dashboard/users') && !path.startsWith('/dashboard/leaderboards') && !path.startsWith('/dashboard/site-content')) },
  { href: '/dashboard/users', label: 'User management', icon: Users, match: (path: string) => path.startsWith('/dashboard/users') },
  { href: '/dashboard/leaderboards', label: 'Leaderboard management', icon: Trophy, match: (path: string) => path.startsWith('/dashboard/leaderboards') },
  { href: '/dashboard/site-content', label: 'Manage website', icon: Globe2, match: (path: string) => path.startsWith('/dashboard/site-content') },
];

export default function AdminDashboardShell({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AdminUser | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [authError, setAuthError] = useState('');
  const [mobileOpen, setMobileOpen] = useState(false);
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    let active = true;
    api<AdminUser>('/auth/me')
      .then((current) => { if (active) setUser(current); })
      .catch((error: unknown) => {
        if (!active) return;
        if (isUnauthorizedError(error)) {
          const next = pathname || '/dashboard';
          router.replace(`/login?next=${encodeURIComponent(next)}`);
        } else {
          setAuthError(error instanceof Error ? error.message : 'Could not verify your ExamFlow session.');
        }
      })
      .finally(() => { if (active) setLoaded(true); });
    return () => { active = false; };
  }, [pathname, router]);

  useEffect(() => { setMobileOpen(false); }, [pathname]);

  async function signOut() {
    try { await api('/auth/logout', { method: 'POST' }); }
    finally {
      window.dispatchEvent(new Event('examflow:auth-changed'));
      router.replace('/');
      router.refresh();
    }
  }

  if (!loaded) return <main className="container-shell py-20 text-sm text-slate-500">Checking your ExamFlow session…</main>;

  if (authError) return <main className="container-shell max-w-2xl py-20">
    <section className="card p-6">
      <h1 className="text-xl font-black text-slate-900">Could not connect to your workspace</h1>
      <p role="alert" className="mt-3 text-sm leading-6 text-red-700">{authError}</p>
      <p className="mt-2 text-sm leading-6 text-slate-500">Your account has not been signed out. Check the API connection and retry.</p>
      <button type="button" className="btn mt-5" onClick={() => window.location.reload()}><RefreshCw size={16} className="mr-2"/>Retry</button>
    </section>
  </main>;

  // Students and moderators keep their normal dashboard/profile experience.
  if (!user || user.role !== 'admin') return <>{children}</>;

  const sidebar = (
    <>
      <div className="admin-sidebar-heading">
        <span className="admin-sidebar-mark"><ShieldCheck size={19}/></span>
        <div><strong>Admin control</strong><span>ExamFlow management</span></div>
      </div>
      <div className="admin-sidebar-user">
        <span className="admin-sidebar-avatar">{user.full_name.split(/\s+/).slice(0, 2).map((part) => part[0]).join('').toUpperCase()}</span>
        <div><strong>{user.full_name}</strong><span>Administrator</span></div>
      </div>
      <nav className="admin-sidebar-nav" aria-label="Admin dashboard">
        <p className="admin-sidebar-label">CONTROL PANEL</p>
        {navigation.map((item) => {
          const Icon = item.icon;
          const active = item.match(pathname);
          return <Link key={item.href} href={item.href} aria-current={active ? 'page' : undefined} className={`admin-sidebar-link ${active ? 'is-active' : ''}`}>
            <Icon size={18}/><span>{item.label}</span>
          </Link>;
        })}
      </nav>
      <div className="admin-sidebar-bottom">
        <button type="button" className="admin-sidebar-signout" onClick={signOut}><LogOut size={17}/>Sign out</button>
        <p>ExamFlow · Admin workspace</p>
      </div>
    </>
  );

  return <div className="admin-dashboard-layout">
    <aside className="admin-sidebar">{sidebar}</aside>
    <div className="admin-mobile-bar">
      <span><ShieldCheck size={17}/> Admin control panel</span>
      <button type="button" onClick={() => setMobileOpen((open) => !open)} aria-label={mobileOpen ? 'Close admin navigation' : 'Open admin navigation'}>
        {mobileOpen ? <X size={20}/> : <Menu size={20}/>}
      </button>
    </div>
    {mobileOpen && <div className="admin-mobile-drawer" onMouseDown={(event) => { if (event.target === event.currentTarget) setMobileOpen(false); }}><div className="admin-mobile-drawer-panel"><button type="button" className="admin-mobile-close" onClick={() => setMobileOpen(false)}><X size={16}/>Close navigation</button><div className="admin-sidebar">{sidebar}</div></div></div>}
    <div className="admin-dashboard-main">{children}</div>
  </div>;
}
