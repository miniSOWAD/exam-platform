'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { ArrowUpRight, FlaskConical, LayoutDashboard, LogOut, UserRound } from 'lucide-react';
import { api } from '@/lib/api';
import { useSiteContent } from '@/components/SiteContentProvider';

type User = { id: string; email: string; full_name: string; role: string; avatar_url?: string | null };

function initials(name: string) {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  return (parts.length > 1 ? [parts[0], parts[parts.length - 1]] : parts).map((part) => part[0]).join('').toUpperCase() || 'U';
}

export default function Header() {
  const [user, setUser] = useState<User | null>(null);
  const { site } = useSiteContent();
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    let active = true;
    const loadUser = () => api<User>('/auth/me').then((data) => { if (active) setUser(data); }).catch(() => { if (active) setUser(null); });
    void loadUser();
    const handleAuthChange = () => { void loadUser(); };
    window.addEventListener('examflow:auth-changed', handleAuthChange);
    return () => { active = false; window.removeEventListener('examflow:auth-changed', handleAuthChange); };
  }, []);

  async function signOut() {
    try { await api('/auth/logout', { method: 'POST' }); } finally {
      setUser(null);
      setMenuOpen(false);
      window.location.href = '/';
    }
  }

  return (
    <header className="site-header">
      <div className="header-ribbon">
        <div className="header-inner flex items-center justify-between gap-4">
          <span className="flex items-center gap-2"><FlaskConical size={13} /> {site.ribbon_text}</span>
          <span className="hidden sm:inline">{site.ribbon_right_text}</span>
        </div>
      </div>
      <div className="header-main">
        <div className="header-inner flex h-[68px] items-center justify-between gap-4">
          <Link href="/" className="brand-lockup" aria-label={`${site.brand_name} home`}>
            <span className="brand-mark">{(site.brand_name || 'E').charAt(0).toUpperCase()}</span>
            <span className="brand-name">{site.brand_name || 'ExamFlow'}</span>
          </Link>
          <nav className="hidden items-center gap-7 text-sm font-semibold md:flex" aria-label="Main navigation">
            <Link href="/" className="nav-link">Home</Link>
            <a href="/#subjects" className="nav-link">Subjects</a>
            <a href="/#calendar" className="nav-link">Calendar</a>
            <a href="/#leaderboard" className="nav-link">Leaderboard</a>
          </nav>
          <div className="flex items-center gap-2 sm:gap-3">
            {user ? (
              <div className="header-user-menu">
                <button type="button" className="header-profile-button" aria-label="Open account menu" aria-expanded={menuOpen} onClick={() => setMenuOpen((open) => !open)}>
                  <span className="header-profile-avatar">{user.avatar_url ? <img src={user.avatar_url} alt="" /> : initials(user.full_name) || <UserRound size={17} />}</span>
                  <span className="hidden sm:inline">{user.full_name.split(' ')[0]}</span>
                </button>
                {menuOpen && <div className="header-profile-popover">
                  <div className="header-popover-user"><strong>{user.full_name}</strong><span>{user.role}</span></div>
                  <Link href="/dashboard" onClick={() => setMenuOpen(false)}><LayoutDashboard size={15}/> My dashboard</Link>
                  <Link href="/dashboard/profile" onClick={() => setMenuOpen(false)}><UserRound size={15}/> My profile</Link>
                  {user.role === 'admin' && <Link href="/dashboard/site-content" onClick={() => setMenuOpen(false)}>Edit website content</Link>}
                  <button type="button" onClick={signOut}><LogOut size={15}/> Sign out</button>
                </div>}
              </div>
            ) : <>
              <Link href="/login" className="header-signin">Sign in</Link>
              <Link href="/register" className="header-cta">Get started <ArrowUpRight size={15} /></Link>
            </>}
          </div>
        </div>
      </div>
    </header>
  );
}
