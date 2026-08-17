/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  async rewrites() {
    // INTERNAL_BACKEND_URL: nombre del servicio Docker interno (ej: http://ocr-proyecto-fastapi-d5qhym:8000)
    // NEXT_PUBLIC_API_URL: URL pública del backend (ej: http://187.77.62.85:8000)
    const backendUrl =
      process.env.INTERNAL_BACKEND_URL ||
      process.env.NEXT_PUBLIC_API_URL ||
      "http://127.0.0.1:8000";
    return [
      {
        source: "/api/:path*",
        destination: `${backendUrl.replace(/\/$/, "")}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
