/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  swcMinify: true,
  images: {
    unoptimized: true, // For static export if needed
  },
  eslint: {
    // Run ESLint on production builds
    ignoreDuringBuilds: false,
  },
  experimental: {
    // Optimize for production
    optimizePackageImports: ['lucide-react'],
  },
  // Allow the same Next.js dev server to be opened from either hostname
  // (localhost or 127.0.0.1) without emitting "Cross origin request detected"
  // warnings, which surface as failed asset loads in the browser console.
  allowedDevOrigins: ['localhost', '127.0.0.1'],
  async rewrites() {
    const backendUrl = process.env.BACKEND_URL || 'http://13.222.170.87';
    return [
      {
        source: '/backend-api/:path*',
        destination: `${backendUrl}/:path*`,
      },
    ];
  },
};

export default nextConfig;
