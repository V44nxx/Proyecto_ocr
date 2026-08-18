import { NextRequest, NextResponse } from "next/server";
import http from "http";
import https from "https";
import { URL } from "url";

// Memoria caché del backend activo: una vez descubierto, todas las peticiones van directo sin latencia
let cachedWorkingBackend: string | null = null;

const getBackendCandidates = (): string[] => {
  const candidates: string[] = [];

  // Si ya sabemos qué backend funciona, ponerlo de primerísimo
  if (cachedWorkingBackend) {
    candidates.push(cachedWorkingBackend);
  }

  // 1. Variable de entorno explícita (Dokploy)
  const envUrl = process.env.INTERNAL_BACKEND_URL || process.env.BACKEND_URL;
  if (envUrl && envUrl.trim().length > 0) {
    candidates.push(envUrl.trim().replace(/\/$/, ""));
  }

  // 2. Nombres Docker Swarm canónicos en la red dokploy-network
  candidates.push("http://ocr-proyecto-fastapi-d5qhym:8000");
  candidates.push("http://fastapi:8000");
  candidates.push("http://ocr-proyecto-fastapi:8000");

  // 3. Fallbacks locales
  candidates.push("http://127.0.0.1:8000");
  candidates.push("http://localhost:8000");

  return Array.from(new Set(candidates));
};

function doHttpRequest(
  targetUrlStr: string,
  method: string,
  headers: Record<string, string>,
  bodyBuffer?: Buffer,
  timeoutMs: number = 120000
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
        timeout: timeoutMs,
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
        req.destroy(new Error(`Timeout (${timeoutMs}ms) hacia ${targetUrlStr}`));
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
      reqHeaders[k] = value;
    }
  });

  // Forzar respuesta sin comprimir para evitar binario corrupto
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

  const candidateErrors: Record<string, string> = {};

  for (let i = 0; i < candidates.length; i++) {
    const backendBase = candidates[i];
    const targetUrl = `${backendBase}/api/${path}${searchParams}`;
    triedUrls.push(targetUrl);

    // Si es el backend ya cacheado, permitir timeout completo (120s para subidas, 30s para GET)
    // Si estamos descubriendo candidatos, usar 3s para descartar IPs/DNS caídos velozmente
    const isCached = cachedWorkingBackend === backendBase;
    const isOnlyOne = candidates.length === 1;
    const timeoutMs = (isCached || isOnlyOne || hasBody) ? 120000 : 3000;

    try {
      const result = await doHttpRequest(targetUrl, method, reqHeaders, bodyBuffer, timeoutMs);

      // Guardar el backend que funcionó para futuras peticiones instantáneas
      cachedWorkingBackend = backendBase;

      const isNoBody = result.status === 204 || result.status === 304;
      const responseBody = isNoBody ? null : result.data;

      return new NextResponse(responseBody as any, {
        status: result.status,
        statusText: result.statusText,
        headers: result.headers,
      });
    } catch (err: any) {
      lastError = err;
      const errMsg = err?.message || String(err);
      candidateErrors[targetUrl] = errMsg;

      if (cachedWorkingBackend === backendBase) {
        cachedWorkingBackend = null; // Invalidar caché si falló
      }
      console.warn(`[Proxy Miss] ${targetUrl}: ${errMsg}`);
    }
  }

  console.error(`[Proxy Fatal] ${method} /api/${path} — probados:`, candidateErrors);

  return NextResponse.json(
    {
      detail: `No se pudo conectar con el backend. Error: ${lastError?.message || "Servicio no alcanzable"}.`,
      diagnostic: {
        method,
        path: `/api/${path}`,
        candidates_tested: candidateErrors,
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
