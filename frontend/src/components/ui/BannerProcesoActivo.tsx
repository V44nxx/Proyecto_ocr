"use client";

import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import { Loader2, ArrowRight, X, Cpu, XCircle } from "lucide-react";
import toast from "react-hot-toast";
import { apiDocumentos } from "@/lib/api";

interface DocTracking {
  id: string;
  nombre: string;
  estado: string;
  progreso: number;
  paso: string;
  personas_count: number;
}

const LS_DOCS_EN_PROCESO = "ocr_docs_en_proceso";

export default function BannerProcesoActivo() {
  const router = useRouter();
  const pathname = usePathname();
  const [docs, setDocs] = useState<DocTracking[]>([]);
  const [visible, setVisible] = useState(false);
  const [descartado, setDescartado] = useState(false);

  const esPageDocumentos = pathname === "/documentos";

  const leerEstado = () => {
    if (typeof window === "undefined") return;
    try {
      const rawDocs = localStorage.getItem(LS_DOCS_EN_PROCESO);
      if (!rawDocs) { setDocs([]); setVisible(false); return; }
      const parsed: DocTracking[] = JSON.parse(rawDocs);
      const activos = parsed.filter((d) => d.estado === "procesando" || d.estado === "pendiente");
      if (activos.length > 0 && !descartado && !esPageDocumentos) {
        setDocs(activos);
        setVisible(true);
      } else {
        setDocs([]);
        setVisible(false);
      }
    } catch { setDocs([]); setVisible(false); }
  };

  useEffect(() => {
    leerEstado();
    const interval = setInterval(leerEstado, 2000);
    return () => clearInterval(interval);
  }, [pathname, descartado, esPageDocumentos]);

  useEffect(() => {
    if (esPageDocumentos) setDescartado(false);
  }, [esPageDocumentos]);

  if (!visible || docs.length === 0) return null;

  const progresoPromedio = Math.round(
    docs.reduce((acc, d) => acc + (d.progreso || 0), 0) / docs.length
  );
  const nombresRaw = docs.map((d) => d.nombre).join(", ");
  const nombresArchivos = nombresRaw.length > 60 ? nombresRaw.slice(0, 60) + "..." : nombresRaw;

  return (
    <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-[9999] w-[calc(100%-2rem)] max-w-2xl">
      <div className="relative flex items-center gap-3 px-4 py-3 rounded-2xl border shadow-2xl
        bg-gradient-to-r from-blue-600/95 to-indigo-700/95 border-blue-400/40 backdrop-blur-md text-white">
        <div className="flex-shrink-0 w-9 h-9 rounded-xl bg-white/15 flex items-center justify-center">
          <Cpu className="w-5 h-5 text-white animate-pulse" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <Loader2 className="w-3.5 h-3.5 animate-spin text-blue-200 flex-shrink-0" />
            <p className="text-sm font-semibold text-white truncate">
              OCR en proceso — {docs.length} {docs.length === 1 ? "archivo" : "archivos"}
            </p>
            <span className="ml-auto flex-shrink-0 text-xs font-bold text-blue-100 bg-white/15 px-2 py-0.5 rounded-full">
              {progresoPromedio}%
            </span>
          </div>
          <p className="text-xs text-blue-100 truncate">{nombresArchivos}</p>
          <div className="mt-1.5 h-1 rounded-full bg-white/20 overflow-hidden">
            <div className="h-full rounded-full bg-white/70 transition-all duration-500"
              style={{ width: `${progresoPromedio}%` }} />
          </div>
        </div>
        <button onClick={() => router.push("/documentos")}
          className="flex-shrink-0 flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold bg-white/20 hover:bg-white/30 transition-colors border border-white/20">
          Ver progreso
          <ArrowRight className="w-3.5 h-3.5" />
        </button>
        <button
          onClick={async () => {
            if (!window.confirm("¿Deseas cancelar la subida y procesamiento de los documentos?\n\nLos archivos serán removidos por completo del sistema.")) return;
            try {
              const ids = docs.map((d) => d.id).filter((id) => !id.startsWith("prep-") && !id.startsWith("doc-"));
              await apiDocumentos.cancelar({
                documento_ids: ids.length > 0 ? ids : undefined,
                todos_en_proceso: true,
              });
              if (typeof window !== "undefined") {
                localStorage.removeItem(LS_DOCS_EN_PROCESO);
                localStorage.removeItem("ocr_fase_actual");
                localStorage.removeItem("ultimo_documento_id");
              }
              setDocs([]);
              setVisible(false);
              toast.success("Subida cancelada y archivos removidos.");
            } catch {
              toast.error("No se pudo cancelar el proceso.");
            }
          }}
          className="flex-shrink-0 flex items-center gap-1 px-2.5 py-1.5 rounded-xl text-xs font-semibold bg-rose-500/30 hover:bg-rose-500/40 text-rose-100 transition-colors border border-rose-400/40"
          title="Cancelar proceso y remover archivos"
        >
          <XCircle className="w-3.5 h-3.5 text-rose-300" />
          <span>Cancelar</span>
        </button>
        <button onClick={() => setDescartado(true)}
          className="flex-shrink-0 p-1.5 rounded-lg hover:bg-white/20 transition-colors"
          title="Ocultar (el proceso continua en segundo plano)">
          <X className="w-4 h-4 text-white/70" />
        </button>
      </div>
    </div>
  );
}
