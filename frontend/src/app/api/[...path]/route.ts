import { NextRequest, NextResponse } from "next/server";
import http from "http";
import https from "https";
import { URL } from "url";

// Candidatos de backend
const getBackendCandidates = (): string[] => {
  const envUrl = process.env.INTERNAL_BACKEND_URL;
  const candidates: string[] = [];

  if (envUrl && envUrl.trim().length > 0) {
    candidates.push(envUrl.trim().replace(/\/$/, ""));
  }

  // IP directa del VPS en puerto 8000 (verificado y activo)
  candidates.push("http://187.77.62.85:8000");
  candidates.push("http://ocr-proyecto-fastapi-d5qhym:8000");
  candidates.push("http://tasks.ocr-proyecto-fastapi-d5qhym:8000");
  candidates.push("http://172.17.0.1:8000");

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
        timeout: 15000, // 15 segundos timeout
      };

      const req = client.request(reqOptions, (res) => {
        const chunks: Buffer[] = [];
        res.on("data", (chunk) => chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk)));
        res.on("end", () => {
          const responseData = Buffer.concat(chunks);
          const resHeaders: Record<string, string> = {};
          for (const [k, v] of Object.entries(res.headers)) {
            if (v && k !== "transfer-encoding" && k !== "content-encoding") {
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
    if (k !== "host" && k !== "connection" && k !== "content-length" && k !== "transfer-encoding") {
      reqHeaders[key] = value;
    }
  });

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

  for (const backendBase of candidates) {
    const targetUrl = `${backendBase}/api/${path}${searchParams}`;

    try {
      const result = await doHttpRequest(targetUrl, method, reqHeaders, bodyBuffer);

      const isNoBody = result.status === 204 || result.status === 304;
      const responseBody = isNoBody ? null : result.data;

      return new NextResponse(responseBody as any, {
        status: result.status,
        statusText: result.statusText,
        headers: result.headers,
      });
    } catch (err: any) {
      lastError = err;
      console.warn(`[Proxy Fallback] ${targetUrl} no disponible: ${err?.message || err}. Probando siguiente...`);
    }
  }

  console.error(`[Next.js API Route Proxy Fatal] Error para ${method} /api/${path}:`, lastError);
  return NextResponse.json(
    {
      detail: `No se pudo conectar con el backend FastAPI en (${candidates.join(", ")}). Error: ${lastError?.message || "Servicio no alcanzable"}`,
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
