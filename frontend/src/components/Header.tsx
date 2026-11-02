'use client';

import Link from 'next/link';
import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { ArrowUpRight, FlaskConical, LayoutDashboard, LogOut, UserRound, ChevronDown, ShieldCheck } from 'lucide-react';
import { api } from '@/lib/api';

type User = { id:string; email:string; full_name:string; role:string };
type SiteInfo = { announcement?:string };
function initials(name:string) { return name.trim().split(/\s+/).slice(0,2).map(x=>x[0]).join('').toUpperCase() || 'U'; }

export default function Header() {
  const [user,setUser]=useState<User|null>(null);
  const [announcement,setAnnouncement]=useState('A calmer space for focused exam preparation');
  const [open,setOpen]=useState(false);
  const menuRef=useRef<HTMLDivElement>(null);
  const router=useRouter();
  useEffect(()=>{let active=true;const loadUser=()=>api<User>('/auth/me').then(u=>{if(active)setUser(u)}).catch(()=>{if(active)setUser(null)});loadUser();api<SiteInfo>('/site-profile').then(p=>{if(active&&p.announcement)setAnnouncement(p.announcement)}).catch(()=>{});window.addEventListener('examflow:auth-changed',loadUser);return()=>{active=false;window.removeEventListener('examflow:auth-changed',loadUser)}},[]);
  useEffect(()=>{function outside(event:MouseEvent){if(menuRef.current&&!menuRef.current.contains(event.target as Node))setOpen(false)};document.addEventListener('mousedown',outside);return()=>document.removeEventListener('mousedown',outside)},[]);
  async function signOut(){try{await api('/auth/logout',{method:'POST'})}finally{setUser(null);setOpen(false);router.refresh();router.push('/')}}
  return (
    <header className="site-header">
      <div className="header-ribbon"><div className="header-inner flex items-center justify-between gap-4"><span className="flex items-center gap-2"><FlaskConical size={13} /> {announcement}</span><span className="hidden sm:inline">Mathematics · Physics · Chemistry · Biology</span></div></div>
      <div className="header-main"><div className="header-inner flex h-[68px] items-center justify-between gap-4">
        <Link href="/" className="brand-lockup" aria-label="ExamFlow home"><span className="brand-mark">E</span><span className="brand-name">ExamFlow</span></Link>
        <nav className="hidden items-center gap-7 text-sm font-semibold md:flex" aria-label="Main navigation"><Link href="/" className="nav-link">Home</Link><a href="/#subjects" className="nav-link">Subjects</a><a href="/#calendar" className="nav-link">Calendar</a><a href="/#leaderboard" className="nav-link">Leaderboard</a></nav>
        <div className="flex items-center gap-2 sm:gap-3">
          {user ? <div className="account-menu" ref={menuRef}><button className="account-trigger" onClick={()=>setOpen(v=>!v)} aria-expanded={open} aria-label="Open account menu"><span className="account-avatar">{initials(user.full_name)}</span><span className="account-name">{user.full_name.split(' ')[0]}</span><ChevronDown size={14}/></button>{open&&<div className="account-dropdown"><div className="account-dropdown-user"><strong>{user.full_name}</strong><span>{user.email}</span><small>{user.role}</small></div><Link href="/dashboard" onClick={()=>setOpen(false)}><LayoutDashboard size={15}/> Dashboard</Link>{user.role==='admin'&&<Link href="/dashboard/site-profile" onClick={()=>setOpen(false)}><ShieldCheck size={15}/> Site content</Link>}<button onClick={signOut}><LogOut size={15}/> Sign out</button></div>}</div> : <><Link href="/login" className="header-signin">Sign in</Link><Link href="/register" className="header-cta">Get started <ArrowUpRight size={15} /></Link></>}
        </div>
      </div></div>
    </header>
  );
}
