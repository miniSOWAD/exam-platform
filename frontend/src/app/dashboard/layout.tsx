import type { Metadata } from 'next';
import AdminDashboardShell from '@/components/AdminDashboardShell';

export const metadata: Metadata = { title: 'Dashboard', robots: { index: false, follow: false } };

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return <AdminDashboardShell>{children}</AdminDashboardShell>;
}
