"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { FileText, ImageOff, Maximize2, ZoomIn, ZoomOut, X } from "lucide-react";
import { usePaginaPdf } from "@/lib/paginasPdf";
import { formatNombreCompleto } from "@/lib/formatters";
import { useBloquearScroll } from "@/hooks/useBloquearScroll";
import type { Persona } from "@/types";

// La página se pide primero a 130 dpi (rápida, misma caché que la precarga del panel)
// y a 200 dpi cuando se acerca lo suficiente como para que se note la diferencia.
const DPI_BASE = 130;
const DPI_ALTA = 200;
const ESCALA_ALTA_RESOLUCION = 1.4;
const MARGEN_AJUSTE = 24;
const MARGEN_VISIBLE = 80;
const PASO_TECLADO = 60;

interface Vista {
  x: number;
  y: number;
  escala: number;
}

interface Tamano {
  w: number;
  h: number;
}

function limitarVista(v: Vista, base: Tamano, ancho: number, alto: number): Vista {
  const w = base.w * v.escala;
  const h = base.h * v.escala;
  return {
    escala: v.escala,
    x: Math.min(ancho - MARGEN_VISIBLE, Math.max(MARGEN_VISIBLE - w, v.x)),
    y: Math.min(alto - MARGEN_VISIBLE, Math.max(MARGEN_VISIBLE - h, v.y)),
  };
}

interface VisorDocumentoProps {
  persona: Persona;
  paginaInicial: number;
  onCerrar: () => void;
  onSubirPdf: (persona: Persona) => void;
  /** true: se muestra dentro de la página (junto al panel de la persona) en vez de como modal */
  incrustado?: boolean;
}

export default function VisorDocumento({ persona, paginaInicial, onCerrar, onSubirPdf, incrustado = false }: VisorDocumentoProps) {
  useBloquearScroll(!incrustado);

  // Quien está en el Excel pero no en el PDF no tiene página en el PDF de la ficha
  const sinPdf = persona.en_pdf === false && !persona.documento_pdf_id;
  const docId = sinPdf ? null : persona.documento_pdf_id || persona.documento_id;
  const [pagina, setPagina] = useState(paginaInicial);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(false);
  const [base, setBase] = useState<Tamano | null>(null);
  const [vista, setVista] = useState<Vista>({ x: 0, y: 0, escala: 1 });
  const [escalaAjuste, setEscalaAjuste] = useState(1);
  const [animar, setAnimar] = useState(false);
  const [arrastrando, setArrastrando] = useState(false);
  const [altaResolucion, setAltaResolucion] = useState<"no" | "cargando" | "lista">("no");
  const paginaBase = usePaginaPdf(docId ? String(docId) : null, pagina, DPI_BASE);
  const paginaAlta = usePaginaPdf(docId ? String(docId) : null, pagina, DPI_ALTA, altaResolucion !== "no");

  const escenarioRef = useRef<HTMLDivElement>(null);
  const arrastreRef = useRef<{ px: number; py: number; x: number; y: number } | null>(null);
  const cierrePendienteRef = useRef(false);

  const escalaMin = escalaAjuste * 0.5;
  const escalaMax = escalaAjuste * 8;

  const ajustar = useCallback(
    (conAnimacion: boolean) => {
      const esc = escenarioRef.current;
      if (!esc || !base) return;
      const ancho = esc.clientWidth;
      const alto = esc.clientHeight;
      const escala = Math.max(0.05, Math.min((ancho - 2 * MARGEN_AJUSTE) / base.w, (alto - 2 * MARGEN_AJUSTE) / base.h));
      setAnimar(conAnimacion);
      setEscalaAjuste(escala);
      setVista({ escala, x: (ancho - base.w * escala) / 2, y: (alto - base.h * escala) / 2 });
    },
    [base]
  );

  const zoomEn = useCallback(
    (cx: number, cy: number, factor: number, conAnimacion: boolean) => {
      const esc = escenarioRef.current;
      if (!esc || !base) return;
      setAnimar(conAnimacion);
      setVista((v) => {
        const escala = Math.min(escalaMax, Math.max(escalaMin, v.escala * factor));
        const r = escala / v.escala;
        return limitarVista({ escala, x: cx - (cx - v.x) * r, y: cy - (cy - v.y) * r }, base, esc.clientWidth, esc.clientHeight);
      });
    },
    [base, escalaMin, escalaMax]
  );

  const zoomCentro = (factor: number) => {
    const esc = escenarioRef.current;
    if (esc) zoomEn(esc.clientWidth / 2, esc.clientHeight / 2, factor, true);
  };

  const mover = (dx: number, dy: number) => {
    const esc = escenarioRef.current;
    if (!esc || !base) return;
    setAnimar(true);
    setVista((v) => limitarVista({ ...v, x: v.x + dx, y: v.y + dy }, base, esc.clientWidth, esc.clientHeight));
  };

  // Al cargar una página nueva, ajustarla al espacio disponible
  useEffect(() => {
    if (base) ajustar(false);
  }, [base, ajustar]);

  // Si no se pudo traer la imagen (sin conexión, archivo no disponible), mostrar el aviso
  useEffect(() => {
    if (paginaBase.error) {
      setCargando(false);
      setError(true);
    }
  }, [paginaBase.error]);

  // Si cambia el tamaño del espacio (ventana o panel), volver a ajustar la página
  useEffect(() => {
    const esc = escenarioRef.current;
    if (!esc || !base || typeof ResizeObserver === "undefined") return;
    let primera = true;
    const observador = new ResizeObserver(() => {
      if (primera) {
        primera = false;
        return;
      }
      ajustar(false);
    });
    observador.observe(esc);
    return () => observador.disconnect();
  }, [base, ajustar]);

  // Pedir la página en alta resolución cuando cada píxel de la imagen base ya ocupa más de un píxel real de la pantalla
  useEffect(() => {
    const densidad = window.devicePixelRatio || 1;
    if (base && altaResolucion === "no" && vista.escala * densidad >= ESCALA_ALTA_RESOLUCION) setAltaResolucion("cargando");
  }, [base, altaResolucion, vista.escala]);

  // La rueda se escucha a mano para poder evitar que la página de fondo haga scroll
  useEffect(() => {
    const esc = escenarioRef.current;
    if (!esc) return;
    const alRodar = (e: WheelEvent) => {
      e.preventDefault();
      const rect = esc.getBoundingClientRect();
      zoomEn(e.clientX - rect.left, e.clientY - rect.top, Math.exp(-e.deltaY * 0.0015), false);
    };
    esc.addEventListener("wheel", alRodar, { passive: false });
    return () => esc.removeEventListener("wheel", alRodar);
  }, [zoomEn]);

  useEffect(() => {
    // Incrustado junto al panel, Escape no cierra nada (se podría estar editando la persona)
    if (incrustado) return;
    const alTeclear = (e: KeyboardEvent) => {
      if (e.key === "Escape") onCerrar();
    };
    document.addEventListener("keydown", alTeclear);
    return () => document.removeEventListener("keydown", alTeclear);
  }, [onCerrar, incrustado]);

  const cambiarPagina = (nueva: number) => {
    if (nueva === pagina) return;
    setPagina(nueva);
    setCargando(true);
    setError(false);
    setBase(null);
    setAltaResolucion("no");
  };

  const alBajarPuntero = (e: React.PointerEvent<HTMLDivElement>) => {
    if (e.button !== 0 || !base) return;
    e.currentTarget.setPointerCapture(e.pointerId);
    arrastreRef.current = { px: e.clientX, py: e.clientY, x: vista.x, y: vista.y };
    setAnimar(false);
    setArrastrando(true);
  };

  const alMoverPuntero = (e: React.PointerEvent<HTMLDivElement>) => {
    const a = arrastreRef.current;
    const esc = escenarioRef.current;
    if (!a || !esc || !base) return;
    setVista((v) =>
      limitarVista({ ...v, x: a.x + e.clientX - a.px, y: a.y + e.clientY - a.py }, base, esc.clientWidth, esc.clientHeight)
    );
  };

  const terminarArrastre = () => {
    arrastreRef.current = null;
    setArrastrando(false);
  };

  const alTeclearEscenario = (e: React.KeyboardEvent<HTMLDivElement>) => {
    const desplazamientos: Record<string, [number, number]> = {
      ArrowLeft: [PASO_TECLADO, 0],
      ArrowRight: [-PASO_TECLADO, 0],
      ArrowUp: [0, PASO_TECLADO],
      ArrowDown: [0, -PASO_TECLADO],
    };
    const d = desplazamientos[e.key];
    if (d) {
      e.preventDefault();
      mover(d[0], d[1]);
    } else if (e.key === "+" || e.key === "=") {
      e.preventDefault();
      zoomCentro(1.25);
    } else if (e.key === "-") {
      e.preventDefault();
      zoomCentro(0.8);
    } else if (e.key === "0") {
      e.preventDefault();
      ajustar(true);
    }
  };

  const porcentaje = Math.round((vista.escala / escalaAjuste) * 100);
  const tieneDosCaras = Boolean(persona.pagina_frente && persona.pagina_reverso);
  const transicion = animar && !arrastrando ? "transform 150ms ease-out" : "none";

  const claseBotonIcono =
    "p-1.5 rounded-lg text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white hover:bg-slate-200 dark:hover:bg-slate-800 disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer";

  const tarjeta = (
    <div
      role={incrustado ? "region" : "dialog"}
      aria-modal={incrustado ? undefined : true}
      aria-label={`Documento de ${formatNombreCompleto(persona)}, página ${pagina}`}
      className={`bg-white dark:bg-[#111624] border border-slate-200 dark:border-slate-800 rounded-3xl shadow-2xl flex flex-col overflow-hidden ${
        incrustado ? "w-full h-full animate-in fade-in duration-200" : "w-full max-w-5xl h-[90vh] animate-in zoom-in-95 duration-200"
      }`}
    >
      {/* Encabezado */}
      <div className="flex flex-wrap items-center justify-between gap-2 px-5 py-3.5 border-b border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-[#141928]">
        <div className="flex items-center gap-2 min-w-0">
          <FileText className="w-4 h-4 text-[#0071E3] dark:text-indigo-400 shrink-0" />
          <span className="text-xs font-bold text-slate-900 dark:text-white wrap-break-word">
            {incrustado ? "Documento" : `Vista previa: ${formatNombreCompleto(persona)}`} (pág. {pagina})
          </span>
        </div>

        <div className="flex items-center gap-1">
          {docId && (
            <>
              <button type="button" onClick={() => zoomCentro(0.8)} disabled={!base} className={claseBotonIcono} aria-label="Alejar" title="Alejar">
                <ZoomOut className="w-4 h-4" />
              </button>
              <span className="text-[11px] font-mono text-slate-600 dark:text-slate-400 w-12 text-center" aria-live="polite">
                {base ? `${porcentaje}%` : "—"}
              </span>
              <button type="button" onClick={() => zoomCentro(1.25)} disabled={!base} className={claseBotonIcono} aria-label="Acercar" title="Acercar">
                <ZoomIn className="w-4 h-4" />
              </button>
              <button type="button" onClick={() => ajustar(true)} disabled={!base} className={claseBotonIcono} aria-label="Ajustar a la pantalla" title="Ajustar a la pantalla (doble clic)">
                <Maximize2 className="w-4 h-4" />
              </button>
            </>
          )}
          {!incrustado && (
            <button
              type="button"
              onClick={onCerrar}
              className="p-1.5 ml-2 rounded-xl bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white cursor-pointer"
              aria-label="Cerrar vista previa"
              title="Cerrar (Esc)"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      {/* Área de la página */}
      {!docId ? (
        <div className="flex-1 flex items-center justify-center bg-slate-900 p-6">
          <div className="text-center py-12">
            <ImageOff className="w-10 h-10 text-slate-600 mx-auto mb-2" />
            <p className="text-xs text-slate-400">Esta persona no tiene documento PDF asociado.</p>
            <button
              type="button"
              onClick={() => {
                if (!incrustado) onCerrar();
                onSubirPdf(persona);
              }}
              className="mt-3 px-3 py-1.5 rounded-xl bg-[#0071E3] hover:bg-[#0077ED] text-xs text-white cursor-pointer"
            >
              Subir PDF individual de cédula
            </button>
          </div>
        </div>
      ) : (
        <div
          ref={escenarioRef}
          role="region"
          tabIndex={0}
          aria-label={`Página ${pagina}. Arrástrala para moverla; las flechas la desplazan, más y menos cambian el zoom y cero la ajusta.`}
          onPointerDown={alBajarPuntero}
          onPointerMove={alMoverPuntero}
          onPointerUp={terminarArrastre}
          onPointerCancel={terminarArrastre}
          onLostPointerCapture={terminarArrastre}
          onDoubleClick={() => ajustar(true)}
          onKeyDown={alTeclearEscenario}
          className={`relative flex-1 min-h-0 overflow-hidden bg-slate-900 touch-none select-none focus:outline-hidden focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[#0071E3] ${
            arrastrando ? "cursor-grabbing" : "cursor-grab"
          }`}
        >
          <div
            className="absolute left-0 top-0"
            style={{
              width: base ? base.w : undefined,
              height: base ? base.h : undefined,
              transform: `translate(${vista.x}px, ${vista.y}px) scale(${vista.escala})`,
              transformOrigin: "0 0",
              transition: transicion,
              visibility: base ? "visible" : "hidden",
            }}
          >
            {paginaBase.src && (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                key={`base-${pagina}`}
                src={paginaBase.src}
                alt={`Página ${pagina} del documento`}
                draggable={false}
                onDragStart={(e) => e.preventDefault()}
                onLoad={(e) => {
                  const img = e.currentTarget;
                  setCargando(false);
                  setBase({ w: img.naturalWidth, h: img.naturalHeight });
                }}
                onError={() => {
                  setCargando(false);
                  setError(true);
                }}
                className="block w-full h-full rounded-xs shadow-2xl"
              />
            )}
            {altaResolucion !== "no" && paginaAlta.src && (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                key={`alta-${pagina}`}
                src={paginaAlta.src}
                alt=""
                aria-hidden="true"
                draggable={false}
                onDragStart={(e) => e.preventDefault()}
                onLoad={() => setAltaResolucion("lista")}
                className="absolute inset-0 w-full h-full rounded-xs transition-opacity duration-200"
                style={{ opacity: altaResolucion === "lista" ? 1 : 0 }}
              />
            )}
          </div>

          {cargando && (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 pointer-events-none">
              <div className="w-6 h-6 border-2 border-[#0071E3] border-t-transparent rounded-full animate-spin" />
              <span className="text-xs text-slate-400">Cargando página {pagina}...</span>
            </div>
          )}

          {error && (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 p-6 text-center">
              <ImageOff className="w-10 h-10 text-slate-600" />
              <p className="text-xs text-slate-400">No se pudo cargar la página {pagina}. Revisa tu conexión y vuelve a abrirla.</p>
            </div>
          )}

          {base && !error && (
            <p className="absolute left-3 bottom-3 flex flex-wrap gap-x-3 gap-y-1 px-3 py-1.5 rounded-xl bg-black/60 text-[11px] text-slate-200 pointer-events-none">
              <span>Arrastra para mover</span>
              <span>Rueda para acercar</span>
              <span>Doble clic para ajustar</span>
            </p>
          )}
        </div>
      )}

      {/* Frente y reverso */}
      {docId && tieneDosCaras && (
        <div className="p-3 border-t border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-[#141928] flex items-center justify-center gap-2">
          {[
            { etiqueta: "Frente", numero: persona.pagina_frente! },
            { etiqueta: "Reverso", numero: persona.pagina_reverso! },
          ].map(({ etiqueta, numero }) => (
            <button
              key={etiqueta}
              type="button"
              onClick={() => cambiarPagina(numero)}
              aria-pressed={pagina === numero}
              className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all cursor-pointer ${
                pagina === numero
                  ? "bg-[#0071E3] text-white"
                  : "bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
              }`}
            >
              {etiqueta} (pág. {numero})
            </button>
          ))}
        </div>
      )}
    </div>
  );

  if (incrustado) return tarjeta;

  return (
    <div
      className="fixed inset-0 z-50 bg-black/70 backdrop-blur-md flex items-center justify-center p-3 sm:p-6 animate-in fade-in duration-200"
      onPointerDown={(e) => {
        cierrePendienteRef.current = e.target === e.currentTarget;
      }}
      onClick={(e) => {
        if (cierrePendienteRef.current && e.target === e.currentTarget) onCerrar();
        cierrePendienteRef.current = false;
      }}
    >
      {tarjeta}
    </div>
  );
}
