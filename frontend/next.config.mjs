/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  // El proxy de /api/* está implementado en src/app/api/[...path]/route.ts
  // No se necesitan rewrites aquí — el App Router los maneja directamente
};

export default nextConfig;
