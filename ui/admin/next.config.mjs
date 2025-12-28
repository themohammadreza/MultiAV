const apiProxyTarget = process.env.API_PROXY_TARGET || process.env.NEXT_PUBLIC_API_PROXY_TARGET;

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  reactStrictMode: true,
  experimental: {
    typedRoutes: true
  },
  async rewrites() {
    if (!apiProxyTarget) return [];

    const normalized = apiProxyTarget.replace(/\/$/, '');

    return [
      {
        source: '/api/:path*',
        destination: `${normalized}/api/:path*`
      }
    ];
  }
};

export default nextConfig;
