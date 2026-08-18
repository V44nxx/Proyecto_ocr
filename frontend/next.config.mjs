/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",

  // Proxy /api/* al backend FastAPI en producción.
  // En Docker/Dokploy: BACKEND_URL = INTERNAL_BACKEND_URL (red interna Docker)
  // En desarrollo local: fallback a localhost:8000
  async rewrites() {
    const backendUrl =
      process.env.INTERNAL_BACKEND_URL ||
      process.env.BACKEND_URL ||
      process.env.NEXT_PUBLIC_API_URL ||
      "http://localhost:8000";

    console.log(`[next.config] Proxy /api/* → ${backendUrl}`);

    return [
      {
        source: "/api/:path*",
        destination: `${backendUrl}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
