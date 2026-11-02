import type { Metadata } from 'next';
import './globals.css';
import Header from '@/components/Header';
import SiteFooter from '@/components/SiteFooter';
import { SiteContentProvider } from '@/components/SiteContentProvider';

async function loadInitialSiteContent() {
  const apiOrigin = process.env.API_INTERNAL_URL;
  if (!apiOrigin) return undefined;
  try {
    const response = await fetch(`${apiOrigin.replace(/\/$/, '')}/api/v1/site/content`, {
      next: { revalidate: 60 },
      signal: AbortSignal.timeout(2500),
    });
    if (!response.ok) return undefined;
    return await response.json();
  } catch {
    return undefined;
  }
}

export async function generateMetadata(): Promise<Metadata> {
  const site = await loadInitialSiteContent();
  const brand = site?.brand_name || 'ExamFlow';
  const description = site?.hero_description || 'A thoughtful online examination platform for Mathematics, Physics, Chemistry and Biology. Create assessments, take live exams and understand academic performance.';
  const subjects = Array.isArray(site?.subjects) ? site.subjects : ['Mathematics', 'Physics', 'Chemistry', 'Biology'];
  return {
    title: { default: `${brand} — Focused Online Exam Preparation`, template: `%s | ${brand}` },
    description, applicationName: brand,
    metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL || 'http://localhost:3000'),
    keywords: ['online examination platform', 'exam preparation', 'MCQ practice', 'student performance', ...subjects],
    openGraph: { title: `${brand} — Prepare with purpose`, description, type: 'website', siteName: brand },
    twitter: { card: 'summary_large_image', title: `${brand} — Prepare with purpose`, description },
    robots: { index: true, follow: true },
  };
}


export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const initialSiteContent = await loadInitialSiteContent();
  return (
    <html lang="en">
      <body>
        <SiteContentProvider initialSiteContent={initialSiteContent}>
          <Header />
          {children}
          <SiteFooter />
        </SiteContentProvider>
      </body>
    </html>
  );
}
