"use client";

import { useEffect } from "react";
import { AlertTriangle, RefreshCw, Home } from "lucide-react";
import Link from "next/link";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("[Next.js App Error]", error);
  }, [error]);

  return (
    <div className="min-h-screen bg-dark-900 text-white flex items-center justify-center p-6">
      <div className="max-w-md w-full card p-8 text-center border border-red-500/20 bg-dark-800/80 backdrop-blur-xl">
        <div className="w-16 h-16 rounded-2xl bg-red-500/10 border border-red-500/30 flex items-center justify-center mx-auto mb-4 text-red-400">
          <AlertTriangle className="w-8 h-8" />
        </div>
        <h2 className="text-xl font-bold mb-2">Algo salió mal</h2>
        <p className="text-slate-400 text-sm mb-4">
          {error.message || "Ocurrió un error inesperado al renderizar la vista."}
        </p>

        {error.digest && (
          <div className="bg-dark-900 p-2.5 rounded-lg text-xs font-mono text-slate-500 mb-6 truncate">
            Digest: {error.digest}
          </div>
        )}

        <div className="flex gap-3 justify-center">
          <button
            onClick={() => reset()}
            className="btn-primary text-sm py-2 px-4 flex items-center gap-2"
          >
            <RefreshCw className="w-4 h-4" />
            Reintentar
          </button>
          <Link
            href="/dashboard"
            className="btn-secondary text-sm py-2 px-4 flex items-center gap-2"
          >
            <Home className="w-4 h-4" />
            Ir al Inicio
          </Link>
        </div>
      </div>
    </div>
  );
}
