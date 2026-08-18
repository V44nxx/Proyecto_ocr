import { NextRequest, NextResponse } from "next/server";
import http from "http";
import https from "https";
import { URL } from "url";

// Candidatos de backend dentro y fuera de Docker Swarm / Dokploy
const getBackendCandidates = (): string[] => {
  const candidates: string[] = [];

  // 1. Variable de entorno explícita — CONFIGURA ESTO EN DOKPLOY → Frontend → Environment:
  //    INTERNAL_BACKEND_URL=http://10.0.1.189:8000
  const envUrl = process.env.INTERNAL_BACKEND_URL || process.env.BACKEND_URL;
  if (envUrl && envUrl.trim().length > 0) {
    candidates.push(envUrl.trim().replace(/\/$/, ""));
  }

  // 2. Nombres Docker Swarm del servicio FastAPI (requieren estar en la misma red overlay)
  const serviceNames = [
    "ocr-proyecto-fastapi-d5qhym",   // nombre Docker Swarm del servicio FastAPI
    "fastapi",                         // nombre del servicio en Dokploy UI (minúsculas)
    "FastAPI",                         // nombre con mayúscula
    "ocr-proyecto-fastapi",            // sin sufijo hash
    "backend",
  ];
  for (const name of serviceNames) {
    candidates.push(`http://${name}:8000`);
  }

  // 3. IPs conocidas del contenedor FastAPI en la red overlay de Docker Swarm
  //    Nota: estas IPs cambian si el contenedor se reinicia — usar INTERNAL_BACKEND_URL es más fiable
  candidates.push("http://10.0.1.189:8000");   // IP actual del FastAPI (red 10.0.1.x)
  candidates.push("http://172.16.1.20:8000");   // IP alternativa del FastAPI

  // 4. host.docker.internal y gateway Docker
  candidates.push("http://host.docker.internal:8000");
  candidates.push("http://172.17.0.1:8000");

  // 5. Fallback localhost
  candidates.push("http://127.0.0.1:8000");

  return Array.from(new Set(candidates));
};

function doHttpRequest(
  targetUrlStr: string,
  method: string,
  headers: Record<string, string>,
  bodyBuffer?: Buffer
): Promise<{ status: number; statusText: string; headers: Record<string, string>; data: Buffer }> {
  return new Promise((resolve, reject) => {
    try {
      const targetUrl = new URL(targetUrlStr);
      const isHttps = targetUrl.protocol === "https:";
      const client = isHttps ? https : http;

      const reqOptions: http.RequestOptions = {
        hostname: targetUrl.hostname,
        port: targetUrl.port ? parseInt(targetUrl.port, 10) : (isHttps ? 443 : 80),
        path: `${targetUrl.pathname}${targetUrl.search}`,
        method: method,
        headers: headers,
        ...(isHttps ? { rejectUnauthorized: false } : {}),
        timeout: 5000,  // 5s por candidato — fallar rápido si DNS no resuelve
      };

      const req = client.request(reqOptions, (res) => {
        const chunks: Buffer[] = [];
        res.on("data", (chunk) => chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk)));
        res.on("end", () => {
          const responseData = Buffer.concat(chunks);
          const resHeaders: Record<string, string> = {};
          for (const [k, v] of Object.entries(res.headers)) {
            const kl = k.toLowerCase();
            if (v && kl !== "transfer-encoding" && kl !== "content-encoding") {
              resHeaders[k] = Array.isArray(v) ? v.join(", ") : v;
            }
          }
          resolve({
            status: res.statusCode || 200,
            statusText: res.statusMessage || "OK",
            headers: resHeaders,
            data: responseData,
          });
        });
      });

      req.on("error", (err) => {
        reject(err);
      });

      req.on("timeout", () => {
        req.destroy(new Error(`Timeout de conexión hacia ${targetUrlStr}`));
      });

      if (bodyBuffer && bodyBuffer.length > 0) {
        req.write(bodyBuffer);
      }
      req.end();
    } catch (e) {
      reject(e);
    }
  });
}

async function handleProxy(
  req: NextRequest,
  { params }: { params: { path: string[] } }
) {
  const path = params.path ? params.path.join("/") : "";
  const searchParams = req.nextUrl.search || "";
  const candidates = getBackendCandidates();

  const reqHeaders: Record<string, string> = {};
  req.headers.forEach((value, key) => {
    const k = key.toLowerCase();
    if (k !== "host" && k !== "connection" && k !== "content-length" && k !== "transfer-encoding" && k !== "accept-encoding") {
      reqHeaders[key] = value;
    }
  });

  // Forzar respuesta sin comprimir para evitar doble compresión o binario corrupto
  reqHeaders["accept-encoding"] = "identity";

  const method = req.method;
  const hasBody = method !== "GET" && method !== "HEAD";

  let bodyBuffer: Buffer | undefined = undefined;
  if (hasBody) {
    try {
      const arrayBuffer = await req.arrayBuffer();
      bodyBuffer = Buffer.from(arrayBuffer);
      reqHeaders["content-length"] = bodyBuffer.length.toString();
    } catch {
      bodyBuffer = undefined;
    }
  }

  let lastError: any = null;
  const triedUrls: string[] = [];

  for (const backendBase of candidates) {
    const targetUrl = `${backendBase}/api/${path}${searchParams}`;
    triedUrls.push(targetUrl);

    try {
      const result = await doHttpRequest(targetUrl, method, reqHeaders, bodyBuffer);

      // Éxito — loguear qué candidato funcionó
      console.log(`[Proxy OK] ${method} ${targetUrl} → ${result.status}`);

      const isNoBody = result.status === 204 || result.status === 304;
      const responseBody = isNoBody ? null : result.data;

      return new NextResponse(responseBody as any, {
        status: result.status,
        statusText: result.statusText,
        headers: result.headers,
      });
    } catch (err: any) {
      lastError = err;
      console.warn(`[Proxy Miss] ${targetUrl}: ${err?.message || err}`);
    }
  }

  // Diagnóstico completo en el error
  console.error(`[Proxy Fatal] ${method} /api/${path} — probados: ${triedUrls.join(", ")} — último error: ${lastError?.message}`);

  return NextResponse.json(
    {
      detail: `No se pudo conectar con el backend. URLs probadas: ${triedUrls.slice(0, 3).join(", ")}. Error: ${lastError?.message || "Servicio no alcanzable"}. SOLUCIÓN: Verifica que los servicios FastAPI y Frontend estén en la misma red Docker en Dokploy, y que INTERNAL_BACKEND_URL esté correctamente configurado.`,
      debug: {
        internal_backend_url: process.env.INTERNAL_BACKEND_URL || "(no configurado)",
        candidates_tried: triedUrls.length,
        last_error: lastError?.message,
      },
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
