import type { Metadata } from 'next';
import './globals.css';
import Header from '@/components/Header';

export const metadata: Metadata = {
  title: { default: 'ExamFlow — Focused Online Exam Preparation', template: '%s | ExamFlow' },
  description: 'A thoughtful online examination platform for Mathematics, Physics, Chemistry and Biology. Create assessments, take live exams and understand academic performance.',
  applicationName: 'ExamFlow',
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL || 'http://localhost:3000'),
  keywords: ['online examination platform', 'exam preparation', 'MCQ practice', 'Mathematics exam', 'Physics exam', 'Chemistry exam', 'Biology exam', 'student performance'],
  openGraph: { title: 'ExamFlow — Prepare with purpose', description: 'Create exams, practice across core subjects and understand every result.', type: 'website', siteName: 'ExamFlow' },
  twitter: { card: 'summary_large_image', title: 'ExamFlow — Prepare with purpose', description: 'A focused workspace for online exams and academic progress.' },
  robots: { index: true, follow: true },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Header />
        {children}
        <footer className="border-t border-[#dce8e8] bg-[#fffdfa] py-7 text-center text-xs text-[#8292a0]">
          © {new Date().getFullYear()} ExamFlow. Built for focused learning and fair assessment.
        </footer>
      </body>
    </html>
  );
}
