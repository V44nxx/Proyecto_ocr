"use client";

import { useEffect } from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("[Global Fatal Error]", error);
  }, [error]);

  return (
    <html lang="es">
      <body className="min-h-screen bg-[#080E1A] text-white flex items-center justify-center p-6 antialiased">
        <div className="max-w-md w-full p-8 text-center rounded-2xl border border-red-500/20 bg-[#0F172A] shadow-2xl">
          <div className="w-16 h-16 rounded-2xl bg-red-500/10 border border-red-500/30 flex items-center justify-center mx-auto mb-4 text-red-400">
            <AlertTriangle className="w-8 h-8" />
          </div>
          <h2 className="text-xl font-bold mb-2">Error de Aplicación</h2>
          <p className="text-slate-400 text-sm mb-6">
            {error.message || "Se produjo un error crítico en el navegador."}
          </p>

          <button
            onClick={() => reset()}
            className="w-full py-2.5 px-4 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-medium text-sm flex items-center justify-center gap-2 transition-all shadow-lg shadow-blue-500/25"
          >
            <RefreshCw className="w-4 h-4" />
            Recargar Aplicación
          </button>
        </div>
      </body>
    </html>
  );
}
