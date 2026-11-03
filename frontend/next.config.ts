import type { NextConfig } from 'next';

// Normalize the origin once. A trailing slash in API_INTERNAL_URL must not create
// a double slash in the upstream path (https://host//api/v1/...).
const backend = (process.env.API_INTERNAL_URL || '').trim().replace(/\/+$/, '');

const nextConfig: NextConfig = {
  poweredByHeader: false,
  output: 'standalone',
  compress: true,
  images: { formats: ['image/avif', 'image/webp'], remotePatterns: [] },
  async rewrites() {
    if (!backend) return [];
    return [{ source: '/api/v1/:path*', destination: `${backend}/api/v1/:path*` }];
  },
  async headers() {
    return [{ source: '/:path*', headers: [
      { key: 'X-Content-Type-Options', value: 'nosniff' },
      { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
      { key: 'X-Frame-Options', value: 'DENY' },
    ] }];
  },
};

export default nextConfig;
