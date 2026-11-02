'use client';

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { api } from '@/lib/api';

export type FeatureCardContent = { label: string; title: string; description: string };
export type SiteContent = {
  brand_name: string; ribbon_text: string; ribbon_right_text: string; hero_eyebrow: string;
  hero_title: string; hero_highlight: string; hero_description: string; hero_primary_cta: string; hero_secondary_cta: string;
  upcoming_title: string; upcoming_subtitle: string; calendar_title: string; calendar_subtitle: string;
  leaderboard_title: string; leaderboard_subtitle: string; features_title: string; features_subtitle: string;
  owner_profile_kicker: string; owner_expertise_heading: string; owner_name: string; owner_role: string; owner_bio: string;
  owner_education: string; owner_institution: string; owner_expertise: string[]; owner_avatar_url: string;
  owner_email: string; owner_phone: string; owner_website: string; owner_social_links: Record<string, string>;
  subjects: string[]; feature_cards: FeatureCardContent[]; footer_text: string;
};

export const defaultSiteContent: SiteContent = {
  brand_name: 'ExamFlow', ribbon_text: 'A calmer space for focused exam preparation', ribbon_right_text: 'Mathematics · Physics · Chemistry · Biology',
  hero_eyebrow: 'EXAMINATION PREPARATION, REIMAGINED', hero_title: 'Prepare with purpose.', hero_highlight: 'Perform with confidence.',
  hero_description: 'A thoughtful workspace for creating exams, practicing what matters and understanding every result across Mathematics, Physics, Chemistry and Biology.',
  hero_primary_cta: 'Create student account', hero_secondary_cta: 'Sign in',
  upcoming_title: 'Live & upcoming exams', upcoming_subtitle: 'Find an assessment and check your preparation.',
  calendar_title: 'University exam calendar', calendar_subtitle: 'Keep your academic schedule in view and make room for consistent practice.',
  leaderboard_title: 'Leaderboard', leaderboard_subtitle: 'See how students performed in published examinations.',
  features_title: 'Tools for the full examination journey.', features_subtitle: 'From the first question to the final result, keep every part of your learning and assessment workflow connected.',
  owner_profile_kicker: 'SITE OWNER', owner_expertise_heading: 'Areas of expertise',
  owner_name: 'Md Mahruf Alam', owner_role: 'Site Owner · Tutor & Examiner',
  owner_bio: 'I am Md Mahruf Alam, the owner of ExamFlow. I help learners prepare through structured examinations, tutoring and clear performance feedback.',
  owner_education: '', owner_institution: '', owner_expertise: ['Mathematics', 'Physics', 'Chemistry', 'Biology'], owner_avatar_url: '',
  owner_email: '', owner_phone: '', owner_website: '', owner_social_links: {},
  subjects: ['Mathematics', 'Physics', 'Chemistry', 'Biology'],
  feature_cards: [
    { label: 'Exam builder', title: 'Build better assessments', description: 'Create question sets, configure marks and organize exams by subject, chapter and set.' },
    { label: 'Live control', title: 'Manage live examinations', description: 'Start, pause and resume exams with a server-controlled timer and reliable answer saving.' },
    { label: 'Performance', title: 'Understand every result', description: 'Review scores, compare published rankings and follow performance across attempts.' }
  ],
  footer_text: 'Built for focused learning and fair assessment.'
};

type SiteContentContextValue = { site: SiteContent; refreshSiteContent: () => Promise<void> };
const SiteContentContext = createContext<SiteContentContextValue | null>(null);

export function SiteContentProvider({ children, initialSiteContent }: { children: ReactNode; initialSiteContent?: Partial<SiteContent> }) {
  const [site, setSite] = useState<SiteContent>({ ...defaultSiteContent, ...initialSiteContent });
  const refreshSiteContent = useCallback(async () => {
    try {
      const content = await api<Partial<SiteContent>>('/site/content');
      setSite({ ...defaultSiteContent, ...content });
    } catch { /* Keep the lightweight static defaults if the API is temporarily unavailable. */ }
  }, []);
  useEffect(() => { if (!initialSiteContent || Object.keys(initialSiteContent).length === 0) void refreshSiteContent(); }, [initialSiteContent, refreshSiteContent]);
  const value = useMemo(() => ({ site, refreshSiteContent }), [site, refreshSiteContent]);
  return <SiteContentContext.Provider value={value}>{children}</SiteContentContext.Provider>;
}

export function useSiteContent() {
  const context = useContext(SiteContentContext);
  if (!context) throw new Error('useSiteContent must be used inside SiteContentProvider');
  return context;
}
