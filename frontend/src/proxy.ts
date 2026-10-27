import { NextResponse, type NextRequest } from "next/server";

/**
 * Política de contenido (CSP) con un nonce nuevo en cada petición.
 *
 * Solo se ejecutan los scripts que llevan ese nonce (los de Next y el del tema en app/layout.tsx), y lo que ellos
 * carguen ('strict-dynamic'). Un script inyectado en la página (XSS) no lo tiene y el navegador lo bloquea.
 * Antes la política permitía 'unsafe-inline' en los scripts. Los estilos sí siguen con 'unsafe-inline': React usa
 * atributos style, que un nonce no cubre.
 * Las fuentes vienen de Google Fonts (globals.css) y el panel de Seguimiento se incrusta desde Google Apps Script.
 * 'unsafe-eval' solo en desarrollo: React lo usa para depurar.
 */
export function proxy(request: NextRequest) {
  const nonce = btoa(crypto.randomUUID());
  const desarrollo = process.env.NODE_ENV !== "production";
  const politica = [
    "default-src 'self'",
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic'${desarrollo ? " 'unsafe-eval'" : ""}`,
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

  // Next lee el nonce de la cabecera de la petición y se lo pone a sus propios scripts
  const cabeceras = new Headers(request.headers);
  cabeceras.set("x-nonce", nonce);
  cabeceras.set("Content-Security-Policy", politica);
  const respuesta = NextResponse.next({ request: { headers: cabeceras } });
  respuesta.headers.set("Content-Security-Policy", politica);
  return respuesta;
}

export const config = {
  matcher: [
    // Solo las páginas: la API va al backend y los archivos estáticos no ejecutan nada por sí solos
    {
      source: "/((?!api|health|_next/static|_next/image|favicon.ico).*)",
      missing: [
        { type: "header", key: "next-router-prefetch" },
        { type: "header", key: "purpose", value: "prefetch" },
      ],
    },
  ],
};
