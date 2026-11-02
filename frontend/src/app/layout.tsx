import type { Metadata } from 'next';
import './globals.css';
import Header from '@/components/Header';
export const metadata: Metadata = { title: { default: 'ExamFlow — Online Examination Platform', template: '%s | ExamFlow' }, description: 'Create examinations, manage students, run live tests and track academic performance.', metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL || 'http://localhost:3000'), openGraph: { title: 'ExamFlow', description: 'A modern online examination platform', type: 'website' }, robots: { index: true, follow: true } };
export default function RootLayout({children}:{children:React.ReactNode}) { return <html lang="en"><body><Header/>{children}<footer className="mt-20 border-t border-slate-200 bg-white py-8 text-center text-sm text-slate-500">© {new Date().getFullYear()} ExamFlow. Built for focused learning.</footer></body></html>; }
