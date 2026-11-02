import type { NextConfig } from 'next';
const backend = process.env.API_INTERNAL_URL;
const nextConfig: NextConfig = {
  poweredByHeader: false,
  output: 'standalone',
  compress: true,
  images: { formats: ['image/avif', 'image/webp'], remotePatterns: [] },
  async rewrites() { return backend ? [{ source: '/api/v1/:path*', destination: `${backend}/api/v1/:path*` }] : []; },
  async headers() { return [{ source: '/:path*', headers: [{ key: 'X-Content-Type-Options', value: 'nosniff' }, { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' }, { key: 'X-Frame-Options', value: 'DENY' }] }]; }
};
export default nextConfig;
