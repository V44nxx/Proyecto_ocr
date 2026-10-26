import { readFileSync } from "node:fs";

/** @type {import('next').NextConfig} */

// Política de contenido obligatoria: el navegador bloquea lo que venga de otro origen.
// Las fuentes vienen de Google Fonts (globals.css) y el panel de Seguimiento se incrusta desde
// Google Apps Script. 'unsafe-eval' solo en desarrollo: el recargado en caliente de Next lo necesita.
const desarrollo = process.env.NODE_ENV !== "production";
const politicaContenido = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline'${desarrollo ? " 'unsafe-eval'" : ""}`,
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
  { key: "Content-Security-Policy", value: politicaContenido },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=(), usb=()" },
  { key: "Cross-Origin-Opener-Policy", value: "same-origin-allow-popups" },
  { key: "Strict-Transport-Security", value: "max-age=31536000" },
];

// La versión del frontend viaja en el código: si no coincide con la del servidor, se avisa que hay una actualización
const { version } = JSON.parse(readFileSync(new URL("./package.json", import.meta.url), "utf-8"));

const nextConfig = {
  output: "standalone",
  poweredByHeader: false,
  env: { NEXT_PUBLIC_APP_VERSION: version },
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
      // Estado y versión del servidor (en producción se consulta directo en api.v44nxx.online)
      { source: "/health", destination: `${backendUrl}/health` },
    ];
  },
};

export default nextConfig;
