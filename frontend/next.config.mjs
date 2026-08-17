/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  async rewrites() {
    // En el servidor Next.js (SSR/proxy), usa la URL interna Docker para reenviar /api/*
    // Esta variable DEBE estar configurada en Dokploy como Environment Variable del Frontend:
    //   INTERNAL_BACKEND_URL = http://<nombre-servicio-backend-dokploy>:8000
    //   Ejemplo: INTERNAL_BACKEND_URL = http://ocr-proyecto-fastapi-d5qhym:8000
    //
    // NEXT_PUBLIC_API_URL es baked en el bundle del cliente — se configura como Build ARG en Dokploy
    const backendUrl =
      process.env.INTERNAL_BACKEND_URL ||
      "http://localhost:8000";

    console.log(`[Next.js proxy] /api/* → ${backendUrl}`);

    return [
      {
        source: "/api/:path*",
        destination: `${backendUrl.replace(/\/$/, "")}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
