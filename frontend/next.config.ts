import type { NextConfig } from 'next';

// Keep the browser and auth cookie on one origin. The external rewrite proxies
// requests server-side, preserving the HttpOnly access_token cookie.
const DEFAULT_API_ORIGIN = 'https://examflow-api.fastapicloud.dev';
const configuredBackend = process.env.API_INTERNAL_URL?.trim()
  || process.env.EXAMFLOW_API_ORIGIN?.trim()
  || DEFAULT_API_ORIGIN;
const backend = configuredBackend.replace(/\/+$/, '').replace(/\/api\/v1$/i, '') || DEFAULT_API_ORIGIN;

const nextConfig: NextConfig = {
  poweredByHeader: false,
  output: 'standalone',
  compress: true,
  images: { formats: ['image/avif', 'image/webp'], remotePatterns: [] },
  async rewrites() {
    return [{ source: '/api/v1/:path*', destination: `${backend}/api/v1/:path*` }];
  },
  async headers() {
    return [{
      source: '/:path*',
      headers: [
        { key: 'X-Content-Type-Options', value: 'nosniff' },
        { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
        { key: 'X-Frame-Options', value: 'DENY' },
      ],
    }];
  },
};

export default nextConfig;
