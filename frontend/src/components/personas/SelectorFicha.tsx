"use client";

import { useMemo, useRef, useState } from "react";
import { ChevronsUpDown, FolderOpen } from "lucide-react";
import { VentanaSelector, type OpcionSelector } from "@/components/ui/SelectorModal";
import type { Documento } from "@/types";

export const TODAS_LAS_FICHAS = "todos";

const ESTADOS_EN_CURSO: Record<string, string> = {
  pendiente: "En cola",
  procesando: "Procesando",
  error: "Con error",
};

/** Cada PDF subido es una ficha: "3021457.pdf" se muestra como "Ficha 3021457". */
export function nombreFicha(doc: Documento): string {
  const base = (doc.nombre_original || "").replace(/\.pdf$/i, "").trim();
  if (!base) return "Ficha sin nombre";
  return /^\d+$/.test(base) ? `Ficha ${base}` : base;
}

function detalleFicha(doc: Documento): string {
  const partes: string[] = [];
  if (doc.fecha_carga) {
    const fecha = new Date(doc.fecha_carga);
    if (!Number.isNaN(fecha.getTime())) partes.push(`Subida el ${fecha.toLocaleDateString("es-CO")}`);
  }
  if (doc.total_paginas) partes.push(`${doc.total_paginas} ${doc.total_paginas === 1 ? "página" : "páginas"}`);
  if (doc.total_personas != null) partes.push(`${doc.total_personas} ${doc.total_personas === 1 ? "persona" : "personas"}`);
  return partes.join(" · ");
}

interface SelectorFichaProps {
  documentos: Documento[];
  /** Id del documento elegido, o TODAS_LAS_FICHAS */
  valor: string;
  onCambiar: (documentoId: string) => void;
}

export default function SelectorFicha({ documentos, valor, onCambiar }: SelectorFichaProps) {
  const [abierto, setAbierto] = useState(false);
  const botonRef = useRef<HTMLButtonElement>(null);

  const fichas = useMemo(
    () => [...documentos].sort((a, b) => (b.fecha_carga || "").localeCompare(a.fecha_carga || "")),
    [documentos]
  );
  const actual = fichas.find((d) => d.id === valor);
  const resumenTodas = `${fichas.length} ${fichas.length === 1 ? "ficha" : "fichas"}`;

  // Las fichas se eligen en una ventana con buscador (components/ui/SelectorModal.tsx), no en una lista desplegable
  const opciones: OpcionSelector[] = useMemo(
    () => [
      { valor: TODAS_LAS_FICHAS, etiqueta: "Todas las fichas", descripcion: resumenTodas },
      ...fichas.map((d) => ({
        valor: d.id,
        etiqueta: nombreFicha(d),
        descripcion: detalleFicha(d),
        insignia: ESTADOS_EN_CURSO[d.estado],
        color: ESTADOS_EN_CURSO[d.estado] ? "bg-amber-500" : undefined,
      })),
    ],
    [fichas, resumenTodas]
  );

  return (
    <div className="relative w-full sm:w-[420px]">
      <span id="etiqueta-ficha" className="block text-[10px] font-bold tracking-widest text-slate-500 dark:text-slate-400 uppercase mb-1.5">
        Ficha
      </span>
      <button
        ref={botonRef}
        type="button"
        aria-labelledby="etiqueta-ficha"
        aria-haspopup="dialog"
        aria-expanded={abierto}
        onClick={() => setAbierto(true)}
        disabled={fichas.length === 0}
        className="w-full flex items-center gap-3 px-3.5 py-2.5 rounded-xl bg-white/80 dark:bg-white/6 hover:bg-slate-50 dark:hover:bg-white/10 border border-slate-200/80 dark:border-white/8 shadow-xs text-left transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
      >
        <FolderOpen className="w-5 h-5 text-[#0071E3] dark:text-[#3894FF] shrink-0" />
        <span className="flex-1 min-w-0">
          <span className="block text-sm font-bold text-slate-900 dark:text-white wrap-break-word">
            {fichas.length === 0 ? "Todavía no hay fichas" : actual ? nombreFicha(actual) : "Todas las fichas"}
          </span>
          <span className="block text-[11px] text-slate-500 dark:text-slate-400">
            {actual ? detalleFicha(actual) : resumenTodas}
          </span>
        </span>
        <ChevronsUpDown className="w-4 h-4 text-slate-400 shrink-0" />
      </button>

      <VentanaSelector
        id="selector-ficha"
        abierto={abierto}
        onCerrar={() => { setAbierto(false); botonRef.current?.focus(); }}
        titulo="Elegir ficha"
        descripcion="Cada PDF subido es una ficha. Ve las personas de una o de todas."
        tema="ficha"
        valor={actual ? actual.id : TODAS_LAS_FICHAS}
        opciones={opciones}
        onElegir={(id) => { if (id !== valor) onCambiar(id); }}
        textoBusqueda="Buscar ficha por número o nombre"
      />
    </div>
  );
}
