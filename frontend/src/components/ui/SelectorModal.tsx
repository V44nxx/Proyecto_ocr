"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Check, ChevronsUpDown, Search, X } from "lucide-react";
import IconoTema, { type Tema, type Tono } from "@/components/ui/IconoTema";

/**
 * Reemplaza a <select> en las listas largas: un botón muestra la opción elegida y al tocarlo se abre una
 * ventana con buscador y las opciones agrupadas en tarjetas. Teclado: flechas para moverse, Enter para
 * elegir y Esc para cerrar; el foco vuelve al botón.
 * VentanaSelector es la ventana sola, para usarla con otro botón (por ejemplo, el selector de fichas).
 */

export interface OpcionSelector {
  valor: string;
  etiqueta: string;
  descripcion?: string;
  grupo?: string;
  /** Texto corto a la derecha (por ejemplo, cuántas personas tiene una ficha) */
  insignia?: string | number;
  /** Punto de color antes de la etiqueta (clase de Tailwind, p. ej. "bg-amber-500") */
  color?: string;
}

interface VentanaProps {
  id: string;
  abierto: boolean;
  onCerrar: () => void;
  titulo: string;
  descripcion?: string;
  valor: string;
  opciones: OpcionSelector[];
  onElegir: (valor: string) => void;
  tema?: Tema;
  tono?: Tono;
  textoBusqueda?: string;
}

export function VentanaSelector({ id, abierto, onCerrar, titulo, descripcion, valor, opciones, onElegir,
  tema = "reconocimiento", tono = "marca", textoBusqueda = "Buscar…" }: VentanaProps) {
  const [busqueda, setBusqueda] = useState("");
  const [activo, setActivo] = useState(0);
  const lista = useRef<HTMLDivElement>(null);
  const buscador = useRef<HTMLInputElement>(null);
  const buscable = opciones.length > 8;

  const visibles = useMemo(() => {
    const texto = busqueda.trim().toLowerCase();
    return texto ? opciones.filter((o) => `${o.etiqueta} ${o.descripcion ?? ""}`.toLowerCase().includes(texto)) : opciones;
  }, [busqueda, opciones]);

  const grupos = useMemo(() => {
    const mapa = new Map<string, OpcionSelector[]>();
    for (const o of visibles) {
      const g = o.grupo ?? "";
      mapa.set(g, [...(mapa.get(g) ?? []), o]);
    }
    return [...mapa.entries()];
  }, [visibles]);

  const cerrar = () => {
    setBusqueda("");
    onCerrar();
  };

  const elegir = (o: OpcionSelector) => {
    onElegir(o.valor);
    cerrar();
  };

  useEffect(() => {
    if (!abierto) return;
    const i = Math.max(0, opciones.findIndex((o) => o.valor === valor));
    setActivo(i);
    // Con buscador, el foco va al buscador; sin él, a la opción elegida
    requestAnimationFrame(() => {
      if (buscable) buscador.current?.focus();
      else lista.current?.querySelectorAll<HTMLButtonElement>("[role=option]")[i]?.focus();
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [abierto]);

  if (!abierto) return null;

  const mover = (paso: number) => {
    if (!visibles.length) return;
    const i = (activo + paso + visibles.length) % visibles.length;
    setActivo(i);
    lista.current?.querySelectorAll<HTMLButtonElement>("[role=option]")[i]?.focus();
  };

  const alTeclear = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") { e.preventDefault(); cerrar(); }
    else if (e.key === "ArrowDown") { e.preventDefault(); mover(1); }
    else if (e.key === "ArrowUp") { e.preventDefault(); mover(-1); }
    else if (e.key === "Enter" && document.activeElement === buscador.current && visibles[activo]) {
      e.preventDefault();
      elegir(visibles[activo]);
    }
  };

  let indice = -1;
  // En el <body>: dentro de una tarjeta con backdrop-filter, un fixed queda encerrado en ella y se recorta
  return createPortal(
    <div
      className="fixed inset-0 z-[70] flex items-start sm:items-center justify-center p-4 pt-[12vh] sm:pt-4 bg-black/50 backdrop-blur-sm animate-fade-in"
      onMouseDown={(e) => { if (e.target === e.currentTarget) cerrar(); }}
      onKeyDown={alTeclear}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={`${id}-titulo`}
        className="w-full max-w-lg max-h-[76vh] flex flex-col rounded-2xl border border-slate-200 dark:border-white/10 bg-white dark:bg-[#10151f] shadow-2xl overflow-hidden"
      >
        <div className="flex items-start gap-3.5 px-5 pt-5 pb-4">
          <IconoTema tema={tema} tono={tono} tamano="sm" />
          <div className="flex-1 min-w-0">
            <h2 id={`${id}-titulo`} className="text-base font-semibold text-slate-900 dark:text-white">{titulo}</h2>
            {descripcion && <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">{descripcion}</p>}
          </div>
          <button type="button" onClick={cerrar} aria-label="Cerrar"
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-white/8 cursor-pointer">
            <X className="w-4 h-4" />
          </button>
        </div>

        {buscable && (
          <div className="px-5 pb-3">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400" />
              <input
                ref={buscador}
                value={busqueda}
                onChange={(e) => { setBusqueda(e.target.value); setActivo(0); }}
                placeholder={textoBusqueda}
                aria-label={`Buscar en ${titulo.toLowerCase()}`}
                className="w-full bg-slate-100/80 dark:bg-white/4 border border-slate-200/80 dark:border-white/8 rounded-xl pl-9 pr-3 py-2 text-xs text-slate-900 dark:text-white focus:outline-hidden focus:ring-2 focus:ring-[#0071E3]/20 focus:border-[#0071E3]"
              />
            </div>
          </div>
        )}

        <div ref={lista} role="listbox" aria-label={titulo} className="flex-1 overflow-y-auto overscroll-contain px-5 pb-5 space-y-4">
          {grupos.length === 0 && (
            <p className="py-8 text-center text-xs text-slate-500 dark:text-slate-400">Nada coincide con «{busqueda}».</p>
          )}
          {grupos.map(([grupo, items]) => (
            <div key={grupo || "sin-grupo"}>
              {grupo && (
                <p className="mb-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400 dark:text-slate-500">{grupo}</p>
              )}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
                {items.map((o) => {
                  indice += 1;
                  const i = indice;
                  const seleccionada = o.valor === valor;
                  return (
                    <button
                      key={o.valor}
                      type="button"
                      role="option"
                      aria-selected={seleccionada}
                      tabIndex={i === activo ? 0 : -1}
                      onClick={() => elegir(o)}
                      onFocus={() => setActivo(i)}
                      className={`flex items-start gap-2.5 rounded-xl border px-3 py-2.5 text-left transition-colors cursor-pointer focus:outline-hidden focus-visible:ring-2 focus-visible:ring-[#0071E3]/40 ${
                        seleccionada
                          ? "border-[#0071E3]/40 bg-[#0071E3]/[0.07] dark:bg-[#0071E3]/15"
                          : "border-slate-200/80 dark:border-white/8 hover:border-slate-300 dark:hover:border-white/15 hover:bg-slate-50 dark:hover:bg-white/4"
                      }`}
                    >
                      {o.color && <span className={`mt-1.5 w-1.5 h-1.5 rounded-full shrink-0 ${o.color}`} />}
                      <span className="flex-1 min-w-0">
                        <span className="block text-xs font-medium text-slate-800 dark:text-slate-100 leading-snug wrap-break-word">{o.etiqueta}</span>
                        {o.descripcion && <span className="block mt-0.5 text-[11px] text-slate-500 dark:text-slate-400 leading-snug">{o.descripcion}</span>}
                      </span>
                      {o.insignia !== undefined && (
                        <span className="shrink-0 mt-0.5 text-[10px] font-mono text-slate-400">{o.insignia}</span>
                      )}
                      {seleccionada && <Check className="w-3.5 h-3.5 shrink-0 mt-0.5 text-[#0071E3] dark:text-[#4C9BFF]" />}
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>,
    document.body
  );
}

interface Props {
  /** Se pone en el botón: las pruebas y las etiquetas <label htmlFor> lo usan */
  id: string;
  titulo: string;
  descripcion?: string;
  valor: string;
  opciones: OpcionSelector[];
  onCambiar: (valor: string) => void;
  tema?: Tema;
  tono?: Tono;
  /** Clases del botón (ancho, tamaño de letra) */
  className?: string;
}

export default function SelectorModal({ id, titulo, descripcion, valor, opciones, onCambiar, tema, tono, className = "" }: Props) {
  const [abierto, setAbierto] = useState(false);
  const boton = useRef<HTMLButtonElement>(null);
  const elegida = opciones.find((o) => o.valor === valor);

  return (
    <>
      <button
        ref={boton}
        id={id}
        type="button"
        onClick={() => setAbierto(true)}
        aria-haspopup="dialog"
        aria-expanded={abierto}
        className={`group inline-flex items-center justify-between gap-2.5 bg-slate-100/80 dark:bg-white/4 border border-slate-200/80 dark:border-white/8 rounded-xl px-3 py-2 text-xs text-left text-slate-900 dark:text-white hover:border-slate-300 dark:hover:border-white/15 focus:outline-hidden focus:ring-2 focus:ring-[#0071E3]/20 focus:border-[#0071E3] transition-colors cursor-pointer ${className}`}
      >
        <span className="flex items-center gap-2 min-w-0">
          {elegida?.color && <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${elegida.color}`} />}
          <span className="truncate font-medium">{elegida?.etiqueta ?? "Elegir…"}</span>
          {elegida?.insignia !== undefined && (
            <span className="shrink-0 text-[10px] font-mono text-slate-400">{elegida.insignia}</span>
          )}
        </span>
        <ChevronsUpDown className="w-3.5 h-3.5 shrink-0 text-slate-400 group-hover:text-slate-600 dark:group-hover:text-slate-200" />
      </button>
      <VentanaSelector
        id={id}
        abierto={abierto}
        onCerrar={() => { setAbierto(false); boton.current?.focus(); }}
        titulo={titulo}
        descripcion={descripcion}
        valor={valor}
        opciones={opciones}
        onElegir={onCambiar}
        tema={tema}
        tono={tono}
      />
    </>
  );
}
