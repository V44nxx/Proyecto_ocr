import { NextRequest, NextResponse } from "next/server";

// Lista de candidatos de resolución dentro de Docker Swarm / Dokploy
const getBackendCandidates = (): string[] => {
  const envUrl = process.env.INTERNAL_BACKEND_URL;
  const candidates: string[] = [];

  if (envUrl && envUrl.trim().length > 0) {
    candidates.push(envUrl.trim().replace(/\/$/, ""));
  }

  // Nombre de servicio en Docker Swarm (VIP)
  candidates.push("http://ocr-proyecto-fastapi-d5qhym:8000");
  // Nombre de tarea directa en Docker Swarm (DNS de réplicas directas)
  candidates.push("http://tasks.ocr-proyecto-fastapi-d5qhym:8000");
  // Fallback local
  candidates.push("http://127.0.0.1:8000");

  return Array.from(new Set(candidates));
};

async function handleProxy(
  req: NextRequest,
  { params }: { params: { path: string[] } }
) {
  const path = params.path ? params.path.join("/") : "";
  const searchParams = req.nextUrl.search || "";
  const candidates = getBackendCandidates();

  const headers = new Headers();
  req.headers.forEach((value, key) => {
    const k = key.toLowerCase();
    // No reenviar host, connection ni content-length para que fetch calcule la longitud exacta del payload
    if (k !== "host" && k !== "connection" && k !== "content-length" && k !== "transfer-encoding") {
      headers.set(key, value);
    }
  });

  const method = req.method;
  const hasBody = method !== "GET" && method !== "HEAD";

  let body: ArrayBuffer | undefined = undefined;
  if (hasBody) {
    try {
      body = await req.arrayBuffer();
    } catch {
      body = undefined;
    }
  }

  let lastError: any = null;

  for (const backendBase of candidates) {
    const targetUrl = `${backendBase}/api/${path}${searchParams}`;

    try {
      const backendResponse = await fetch(targetUrl, {
        method,
        headers,
        body,
        cache: "no-store",
      });

      const responseHeaders = new Headers();
      backendResponse.headers.forEach((value, key) => {
        const k = key.toLowerCase();
        if (k !== "transfer-encoding" && k !== "content-encoding") {
          responseHeaders.set(key, value);
        }
      });

      // En respuestas 204 No Content o 304 Not Modified, el body DEBE ser null
      const isNoBodyStatus = backendResponse.status === 204 || backendResponse.status === 304;
      const responseData = isNoBodyStatus ? null : await backendResponse.arrayBuffer();

      return new NextResponse(responseData, {
        status: backendResponse.status,
        statusText: backendResponse.statusText,
        headers: responseHeaders,
      });
    } catch (err: any) {
      lastError = err;
      console.warn(`[Proxy Fallback] Falló conexión con ${targetUrl} (${err?.message || err}). Intentando siguiente candidato...`);
    }
  }

  console.error(`[Next.js API Route Proxy Fatal] No se pudo conectar a ningún backend para ${method} /api/${path}:`, lastError);
  return NextResponse.json(
    {
      detail: `No se pudo conectar con el backend FastAPI en ninguno de los candidatos (${candidates.join(", ")}). Error: ${lastError?.message || "Servicio no alcanzable"}`,
    },
    { status: 502 }
  );
}

export const GET = handleProxy;
export const POST = handleProxy;
export const PUT = handleProxy;
export const DELETE = handleProxy;
export const PATCH = handleProxy;
export const HEAD = handleProxy;
export const OPTIONS = handleProxy;
