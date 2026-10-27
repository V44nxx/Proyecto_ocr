"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Check, ChevronDown, FolderOpen, Search } from "lucide-react";
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
  const [busqueda, setBusqueda] = useState("");
  const contenedorRef = useRef<HTMLDivElement>(null);
  const botonRef = useRef<HTMLButtonElement>(null);
  const busquedaRef = useRef<HTMLInputElement>(null);

  const fichas = useMemo(
    () => [...documentos].sort((a, b) => (b.fecha_carga || "").localeCompare(a.fecha_carga || "")),
    [documentos]
  );
  const actual = fichas.find((d) => d.id === valor);
  const resumenTodas = `${fichas.length} ${fichas.length === 1 ? "ficha" : "fichas"}`;

  const q = busqueda.trim().toLowerCase();
  const visibles = q
    ? fichas.filter((d) => nombreFicha(d).toLowerCase().includes(q) || (d.nombre_original || "").toLowerCase().includes(q))
    : fichas;

  useEffect(() => {
    if (!abierto) return;
    busquedaRef.current?.focus();
    const alClicFuera = (e: MouseEvent) => {
      if (contenedorRef.current && !contenedorRef.current.contains(e.target as Node)) setAbierto(false);
    };
    const alTeclear = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setAbierto(false);
        botonRef.current?.focus();
      }
    };
    document.addEventListener("mousedown", alClicFuera);
    document.addEventListener("keydown", alTeclear);
    return () => {
      document.removeEventListener("mousedown", alClicFuera);
      document.removeEventListener("keydown", alTeclear);
    };
  }, [abierto]);

  const elegir = (id: string) => {
    setAbierto(false);
    setBusqueda("");
    botonRef.current?.focus();
    if (id !== valor) onCambiar(id);
  };

  const claseOpcion = (activa: boolean) =>
    `w-full flex items-start gap-2.5 px-3 py-2.5 rounded-xl text-left transition-colors cursor-pointer ${
      activa ? "bg-blue-50 dark:bg-[#0071E3]/15" : "hover:bg-slate-100 dark:hover:bg-white/6"
    }`;

  return (
    <div ref={contenedorRef} className="relative w-full sm:w-[420px]">
      <span id="etiqueta-ficha" className="block text-[10px] font-bold tracking-widest text-slate-500 dark:text-slate-400 uppercase mb-1.5">
        Ficha
      </span>
      <button
        ref={botonRef}
        type="button"
        aria-labelledby="etiqueta-ficha"
        aria-haspopup="true"
        aria-expanded={abierto}
        aria-controls="lista-fichas"
        onClick={() => setAbierto((v) => !v)}
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
        <ChevronDown className={`w-4 h-4 text-slate-400 shrink-0 transition-transform ${abierto ? "rotate-180" : ""}`} />
      </button>

      {abierto && (
        <div
          id="lista-fichas"
          className="absolute left-0 right-0 top-full mt-2 z-30 p-2 rounded-2xl bg-white dark:bg-[#121620] border border-slate-200 dark:border-white/10 shadow-xl animate-in fade-in duration-150"
        >
          <label htmlFor="buscar-ficha" className="sr-only">Buscar ficha</label>
          <div className="relative mb-2">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
            <input
              id="buscar-ficha"
              ref={busquedaRef}
              type="text"
              value={busqueda}
              onChange={(e) => setBusqueda(e.target.value)}
              placeholder="Buscar ficha por número o nombre"
              className="w-full pl-9 pr-3 py-2 bg-slate-50 dark:bg-white/4 border border-slate-200 dark:border-white/8 rounded-xl text-xs text-slate-900 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500 focus:outline-hidden focus:border-[#0071E3] focus:ring-1 focus:ring-[#0071E3]/20"
            />
          </div>
          <ul className="max-h-80 overflow-y-auto overscroll-contain space-y-0.5">
            <li>
              <button
                type="button"
                onClick={() => elegir(TODAS_LAS_FICHAS)}
                aria-current={valor === TODAS_LAS_FICHAS ? "true" : undefined}
                className={claseOpcion(valor === TODAS_LAS_FICHAS)}
              >
                <span className="flex-1 min-w-0">
                  <span className="block text-xs font-semibold text-slate-900 dark:text-white">Todas las fichas</span>
                  <span className="block text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">{resumenTodas}</span>
                </span>
                {valor === TODAS_LAS_FICHAS && <Check className="w-4 h-4 text-[#0071E3] dark:text-[#3894FF] shrink-0 mt-0.5" />}
              </button>
            </li>
            {visibles.map((d) => (
              <li key={d.id}>
                <button
                  type="button"
                  onClick={() => elegir(d.id)}
                  aria-current={d.id === valor ? "true" : undefined}
                  className={claseOpcion(d.id === valor)}
                >
                  <span className="flex-1 min-w-0">
                    <span className="block text-xs font-semibold text-slate-900 dark:text-white wrap-break-word">{nombreFicha(d)}</span>
                    <span className="block text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">{detalleFicha(d)}</span>
                  </span>
                  {ESTADOS_EN_CURSO[d.estado] && (
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-50 dark:bg-amber-500/15 text-amber-700 dark:text-amber-300 border border-amber-200 dark:border-amber-500/30 shrink-0">
                      {ESTADOS_EN_CURSO[d.estado]}
                    </span>
                  )}
                  {d.id === valor && <Check className="w-4 h-4 text-[#0071E3] dark:text-[#3894FF] shrink-0 mt-0.5" />}
                </button>
              </li>
            ))}
            {visibles.length === 0 && (
              <li className="px-3 py-6 text-center text-xs text-slate-500 dark:text-slate-400">
                Ninguna ficha coincide con &quot;{busqueda}&quot;.
              </li>
            )}
          </ul>
        </div>
      )}
    </div>
  );
}
