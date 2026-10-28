"use client";

import { useEffect, useRef, useSyncExternalStore } from "react";
import { createPortal } from "react-dom";
import IconoTema from "@/components/ui/IconoTema";
import { dialogoConfirmacion } from "@/lib/confirmar";

/**
 * Diálogo de confirmación de toda la app (lo abre confirmar() de lib/confirmar.ts). El foco empieza en
 * «Cancelar»: en las acciones que borran algo, un Enter apurado no confirma. Esc también cancela.
 */
export default function DialogoConfirmacion() {
  const pregunta = useSyncExternalStore(dialogoConfirmacion.suscribir, dialogoConfirmacion.obtener, () => null);
  const cancelarRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!pregunta) return;
    const anterior = document.activeElement as HTMLElement | null;
    requestAnimationFrame(() => cancelarRef.current?.focus());
    const alTeclear = (e: KeyboardEvent) => {
      if (e.key === "Escape") dialogoConfirmacion.responder(false);
    };
    document.addEventListener("keydown", alTeclear);
    return () => {
      document.removeEventListener("keydown", alTeclear);
      anterior?.focus?.();
    };
  }, [pregunta]);

  if (!pregunta) return null;
  const peligro = pregunta.tono === "peligro";

  return createPortal(
    <div
      className="fixed inset-0 z-[80] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in"
      onMouseDown={(e) => { if (e.target === e.currentTarget) dialogoConfirmacion.responder(false); }}
    >
      <div
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="confirmacion-titulo"
        aria-describedby={pregunta.mensaje ? "confirmacion-mensaje" : undefined}
        className="w-full max-w-md rounded-2xl border border-slate-200 dark:border-white/10 bg-white dark:bg-[#10151f] shadow-2xl p-6"
      >
        <div className="flex justify-center mb-4">
          <IconoTema tema={pregunta.tema ?? "reconocimiento"} tono={pregunta.tono ?? "marca"} tamano="lg" />
        </div>
        <h2 id="confirmacion-titulo" className="text-lg font-semibold text-center text-slate-900 dark:text-white">
          {pregunta.titulo}
        </h2>
        {pregunta.mensaje && (
          <p id="confirmacion-mensaje" className="mt-2 text-sm text-center leading-relaxed text-slate-500 dark:text-slate-400 whitespace-pre-line">
            {pregunta.mensaje}
          </p>
        )}
        <div className="mt-6 flex items-center justify-end gap-3">
          <button
            ref={cancelarRef}
            type="button"
            onClick={() => dialogoConfirmacion.responder(false)}
            className="px-4 py-2 rounded-xl text-sm font-medium bg-slate-100 hover:bg-slate-200 dark:bg-white/6 dark:hover:bg-white/10 text-slate-700 dark:text-slate-200 border border-slate-200 dark:border-white/8 cursor-pointer focus:outline-hidden focus-visible:ring-2 focus-visible:ring-[#0071E3]/40"
          >
            {pregunta.cancelar ?? "Cancelar"}
          </button>
          <button
            type="button"
            onClick={() => dialogoConfirmacion.responder(true)}
            className={`px-4 py-2 rounded-xl text-sm font-semibold text-white cursor-pointer focus:outline-hidden focus-visible:ring-2 ${
              peligro ? "bg-rose-600 hover:bg-rose-500 focus-visible:ring-rose-400/50" : "bg-[#0071E3] hover:bg-[#0077ED] focus-visible:ring-[#0071E3]/40"
            }`}
          >
            {pregunta.confirmar ?? "Confirmar"}
          </button>
        </div>
      </div>
    </div>,
    document.body
  );
}
