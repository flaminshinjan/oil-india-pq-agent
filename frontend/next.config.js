/** @type {import('next').NextConfig} */
const backendUrl =
  process.env.BACKEND_URL ||
  `http://localhost:${process.env.BACKEND_PORT || 8765}`;

const nextConfig = {
  reactStrictMode: true,
  output: 'standalone',
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${backendUrl}/api/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
