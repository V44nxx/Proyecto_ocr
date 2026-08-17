import { NextRequest, NextResponse } from "next/server";

// Fallback por defecto: nombre del servicio Docker Swarm en Dokploy
const DEFAULT_BACKEND = "http://ocr-proyecto-fastapi-d5qhym:8000";

const getTargetBackend = (): string => {
  const envUrl = process.env.INTERNAL_BACKEND_URL;
  if (envUrl && envUrl.trim().length > 0) {
    return envUrl.trim();
  }
  return DEFAULT_BACKEND;
};

async function handleProxy(
  req: NextRequest,
  { params }: { params: { path: string[] } }
) {
  const backendBase = getTargetBackend().replace(/\/$/, "");
  const path = params.path ? params.path.join("/") : "";
  const searchParams = req.nextUrl.search || "";
  const targetUrl = `${backendBase}/api/${path}${searchParams}`;

  const headers = new Headers();
  req.headers.forEach((value, key) => {
    // No reenviar host del frontend al backend para evitar discrepancias
    if (key.toLowerCase() !== "host" && key.toLowerCase() !== "connection") {
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

  try {
    const backendResponse = await fetch(targetUrl, {
      method,
      headers,
      body,
      cache: "no-store",
    });

    const responseHeaders = new Headers();
    backendResponse.headers.forEach((value, key) => {
      // Ignorar transfer-encoding para evitar conflictos con Next.js Response
      if (key.toLowerCase() !== "transfer-encoding" && key.toLowerCase() !== "content-encoding") {
        responseHeaders.set(key, value);
      }
    });

    const responseData = await backendResponse.arrayBuffer();

    return new NextResponse(responseData, {
      status: backendResponse.status,
      statusText: backendResponse.statusText,
      headers: responseHeaders,
    });
  } catch (error: any) {
    console.error(`[Next.js API Route Proxy Error] ${method} ${targetUrl}:`, error?.message || error);
    return NextResponse.json(
      {
        detail: `No se pudo conectar con el servicio FastAPI backend en (${targetUrl}). Error: ${error?.message || "Servicio no alcanzable"}`,
      },
      { status: 502 }
    );
  }
}

export const GET = handleProxy;
export const POST = handleProxy;
export const PUT = handleProxy;
export const DELETE = handleProxy;
export const PATCH = handleProxy;
export const HEAD = handleProxy;
export const OPTIONS = handleProxy;
