/** @type {import('next').NextConfig} */

// Política de contenido: por ahora en modo "solo reporte" (el navegador avisa en la consola lo que
// bloquearía, sin bloquearlo). Cuando se confirme en producción que no hay avisos, pasarla a
// Content-Security-Policy. Las fuentes vienen de Google Fonts (globals.css) y el panel de
// Seguimiento se incrusta desde Google Apps Script.
const politicaContenido = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline'",
  "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
  "img-src 'self' data: blob:",
  "font-src 'self' data: https://fonts.gstatic.com",
  "connect-src 'self' https://api.v44nxx.online",
  "frame-src https://script.google.com https://*.googleusercontent.com https://accounts.google.com https://docs.google.com",
  "frame-ancestors 'none'",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
].join("; ");

const cabecerasSeguridad = [
  { key: "Content-Security-Policy-Report-Only", value: politicaContenido },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=(), usb=()" },
  { key: "Cross-Origin-Opener-Policy", value: "same-origin-allow-popups" },
  { key: "Strict-Transport-Security", value: "max-age=31536000" },
];

const nextConfig = {
  output: "standalone",
  poweredByHeader: false,
  // Las imágenes son <img> normales: el optimizador de Next no se usa y así no queda expuesto
  images: { unoptimized: true },
  async headers() {
    return [{ source: "/:path*", headers: cabecerasSeguridad }];
  },
  async rewrites() {
    const backendUrl =
      process.env.INTERNAL_BACKEND_URL ||
      process.env.BACKEND_URL ||
      "https://api.v44nxx.online";
    return [
      {
        source: "/api/:path*",
        destination: `${backendUrl}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
