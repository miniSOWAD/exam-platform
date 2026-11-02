'use client';
import { useSiteContent } from '@/components/SiteContentProvider';
export default function SiteFooter() {
  const { site } = useSiteContent();
  return <footer className="site-footer">© {new Date().getFullYear()} {site.brand_name}. {site.footer_text}</footer>;
}
