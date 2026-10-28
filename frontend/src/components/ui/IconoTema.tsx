import type { ReactNode } from "react";

/**
 * Íconos propios de KondID para modales y avisos, en lugar de íconos genéricos.
 * Todos salen del mismo lenguaje que la marca: la tarjeta de identidad, la huella del logo y las líneas de
 * seguridad (guilloche) de la cédula. Trazo de línea a 1,75 sobre una cuadrícula de 48, con un acento relleno
 * y una insignia que dice la acción (+, −, ✕, ✓, girar).
 */

export type Tema =
  | "crear-usuario"
  | "eliminar-usuario"
  | "clave"
  | "restablecer-clave"
  | "verificacion"
  | "configurar-verificacion"
  | "restablecer-verificacion"
  | "codigos-respaldo"
  | "ficha"
  | "eliminar-ficha"
  | "ficha-existente"
  | "vaciar-personas"
  | "eliminar-personas"
  | "eliminar-persona"
  | "retirar-ficha"
  | "cancelar-proceso"
  | "quitar-enlace"
  | "proceso-ocr"
  | "reconocimiento"
  | "vision"
  | "confianza";

export type Tono = "marca" | "peligro" | "aviso" | "exito";

const TONOS: Record<Tono, { marco: string; trazo: string }> = {
  marca: {
    marco: "bg-[#0336ff]/[0.05] border-[#0336ff]/15 dark:bg-[#5b7cff]/10 dark:border-[#8aa2ff]/20",
    trazo: "text-[#0336ff] dark:text-[#8aa2ff]",
  },
  peligro: {
    marco: "bg-rose-500/[0.06] border-rose-500/20 dark:bg-rose-500/10 dark:border-rose-400/25",
    trazo: "text-rose-600 dark:text-rose-400",
  },
  aviso: {
    marco: "bg-amber-500/[0.07] border-amber-500/25 dark:bg-amber-500/10 dark:border-amber-400/25",
    trazo: "text-amber-600 dark:text-amber-400",
  },
  exito: {
    marco: "bg-emerald-500/[0.06] border-emerald-500/20 dark:bg-emerald-500/10 dark:border-emerald-400/25",
    trazo: "text-emerald-600 dark:text-emerald-400",
  },
};

const TAMANOS = { sm: "w-10 h-10 rounded-xl", md: "w-12 h-12 rounded-2xl", lg: "w-14 h-14 rounded-2xl" };

// ── Piezas comunes ──────────────────────────────────────────────

const Tarjeta = () => (
  <>
    <rect x="5" y="13" width="32" height="23" rx="3.5" fill="currentColor" fillOpacity={0.08} stroke="none" />
    <rect x="5" y="13" width="32" height="23" rx="3.5" />
    <circle cx="14.5" cy="22" r="3.1" />
    <path d="M9.4 31.2c.8-3 2.8-4.5 5.1-4.5s4.3 1.5 5.1 4.5" />
    <path d="M24 20.5h8M24 25h6M24 29.5h7" opacity={0.65} />
  </>
);

const Documento = ({ huella = false }: { huella?: boolean }) => (
  <>
    <path d="M13 6h14l9 9v25a3 3 0 0 1-3 3H13a3 3 0 0 1-3-3V9a3 3 0 0 1 3-3z" fill="currentColor" fillOpacity={0.08} stroke="none" />
    <path d="M13 6h14l9 9v25a3 3 0 0 1-3 3H13a3 3 0 0 1-3-3V9a3 3 0 0 1 3-3z" />
    <path d="M27 6v9h9" />
    {huella ? (
      <>
        <path d="M17.5 29a5.5 5.5 0 0 1 11 0" />
        <path d="M15 30.5a8 8 0 0 1 16 0" opacity={0.55} />
        <path d="M20.5 31a2.5 2.5 0 0 1 5 0v2" />
      </>
    ) : (
      <path d="M15 22h12M15 27h9M15 32h11" opacity={0.65} />
    )}
  </>
);

const Celular = () => (
  <>
    <rect x="13" y="5" width="20" height="38" rx="4" fill="currentColor" fillOpacity={0.08} stroke="none" />
    <rect x="13" y="5" width="20" height="38" rx="4" />
    <path d="M20.5 9.5h5M21 38.5h4" />
  </>
);

const Llave = ({ x = 0, y = 0, s = 1 }: { x?: number; y?: number; s?: number }) => (
  <g transform={`translate(${x} ${y}) scale(${s})`}>
    <circle cx="14" cy="24" r="8.5" fill="currentColor" fillOpacity={0.1} stroke="none" />
    <circle cx="14" cy="24" r="8.5" />
    {/* El ojo de la llave es la huella del logo */}
    <path d="M14 19.4a4.6 4.6 0 0 1 4.6 4.6M9.4 24a4.6 4.6 0 0 0 4.6 4.6" />
    <circle cx="14" cy="24" r="1.2" fill="currentColor" stroke="none" />
    <path d="M22.5 24H42M35 24v5M40 24v4" />
  </g>
);

/** Insignia de la acción, arriba a la derecha (o abajo, con `abajo`) */
const Insignia = ({ children, abajo = false }: { children: ReactNode; abajo?: boolean }) => {
  const cy = abajo ? 36 : 12.5;
  return (
    <g>
      <circle cx="37" cy={cy} r="7.2" fill="currentColor" stroke="none" />
      <g stroke="#fff" strokeWidth={1.9} transform={`translate(0 ${cy - 12.5})`}>
        {children}
      </g>
    </g>
  );
};
const Mas = () => <path d="M37 9v7M33.5 12.5h7" />;
const Menos = () => <path d="M33.5 12.5h7" />;
const Equis = () => <path d="M34.6 10.1l4.8 4.8M39.4 10.1l-4.8 4.8" />;
const Visto = () => <path d="M33.8 12.7l2.2 2.2 4.2-4.5" />;
const Girar = () => (
  <>
    <path d="M40.2 12.5a3.2 3.2 0 1 1-1-2.3" />
    <path d="M39.6 8.3v2.4h-2.4" />
  </>
);

// Esquinas de escáner: el gesto del OCR
const Escaner = () => (
  <path d="M6 15V9a3 3 0 0 1 3-3h6M33 6h6a3 3 0 0 1 3 3v6M42 33v6a3 3 0 0 1-3 3h-6M15 42H9a3 3 0 0 1-3-3v-6" />
);

const DIBUJOS: Record<Tema, ReactNode> = {
  "crear-usuario": (<><Tarjeta /><Insignia><Mas /></Insignia></>),
  "eliminar-usuario": (<><Tarjeta /><Insignia><Menos /></Insignia></>),
  clave: <Llave x={-1.5} y={-2.6} s={1.1} />,
  "restablecer-clave": (<><Llave x={-2} y={4} s={0.92} /><Insignia><Girar /></Insignia></>),
  verificacion: (
    <>
      <Celular />
      <path d="M17.5 21.5h3M21.6 21.5h3M25.7 21.5h3" strokeWidth={2.6} />
      <path d="M17.5 27h11" opacity={0.5} />
      <Insignia abajo><Visto /></Insignia>
    </>
  ),
  "configurar-verificacion": (
    <>
      <Celular />
      <rect x="16.8" y="14" width="5" height="5" rx="1" />
      <rect x="24.2" y="14" width="5" height="5" rx="1" />
      <rect x="16.8" y="21.4" width="5" height="5" rx="1" />
      <path d="M24.2 22h2M28.2 22v2.4M25.2 25.4h4" />
      <Insignia abajo>
        <path d="M37 32.4l3.4 1.3v2.6c0 2-1.4 3.6-3.4 4.3-2-.7-3.4-2.3-3.4-4.3v-2.6z" transform="translate(0 -23.5)" />
      </Insignia>
    </>
  ),
  "restablecer-verificacion": (
    <>
      <Celular />
      <path d="M17.5 21.5h3M21.6 21.5h3M25.7 21.5h3" strokeWidth={2.6} opacity={0.45} />
      <Insignia><Girar /></Insignia>
    </>
  ),
  "codigos-respaldo": (
    <>
      <rect x="8" y="6" width="26" height="34" rx="3" fill="currentColor" fillOpacity={0.08} stroke="none" />
      <rect x="8" y="6" width="26" height="34" rx="3" />
      <path d="M13 13h6M22 13h7M13 19h6M22 19h7M13 25h6M22 25h7M13 31h6M22 31h4" opacity={0.75} />
      <Insignia abajo><Visto /></Insignia>
    </>
  ),
  ficha: <Documento huella />,
  "eliminar-ficha": (<><Documento /><Insignia abajo><Equis /></Insignia></>),
  "ficha-existente": (
    <>
      <path d="M19 4h11l7 7v17" opacity={0.5} />
      <g transform="translate(-4 4)"><Documento /></g>
      <Insignia abajo><Girar /></Insignia>
    </>
  ),
  "vaciar-personas": (
    <>
      {/* Las tarjetas de atrás solo asoman por encima de la del frente */}
      <path d="M12 12.5V9a3 3 0 0 1 3-3h20a3 3 0 0 1 3 3v3.5" opacity={0.4} />
      <path d="M8.5 16.5V13a3 3 0 0 1 3-3h24a3 3 0 0 1 3 3v3.5" opacity={0.7} />
      <g transform="translate(0 4)"><Tarjeta /></g>
      <Insignia><Equis /></Insignia>
    </>
  ),
  "eliminar-personas": (
    <>
      <rect x="5" y="8" width="25" height="15" rx="3" opacity={0.6} />
      <path d="M9.5 15.5l2 2 3.5-3.8" opacity={0.6} />
      <path d="M19 13.5h7M19 18h5" opacity={0.45} />
      <rect x="11" y="25" width="25" height="15" rx="3" fill="currentColor" fillOpacity={0.08} />
      <path d="M15.5 32.5l2 2 3.5-3.8" />
      <path d="M25 30.5h7M25 35h5" opacity={0.65} />
      <Insignia><Menos /></Insignia>
    </>
  ),
  "eliminar-persona": (<><Tarjeta /><Insignia><Menos /></Insignia></>),
  "retirar-ficha": (<><Documento /><Insignia abajo><Menos /></Insignia></>),
  "cancelar-proceso": (
    <>
      <Escaner />
      <path d="M14 15h14M14 20h16" opacity={0.5} />
      <path d="M4 26.5h28" strokeWidth={2.2} />
      <Insignia abajo><Equis /></Insignia>
    </>
  ),
  // Eslabones separados: el enlace deja de estar unido a la cuenta
  "quitar-enlace": (
    <>
      <path d="M21 30l-4.5 4.5a5.7 5.7 0 0 1-8-8L13 22" />
      <path d="M27 18l4.5-4.5a5.7 5.7 0 0 1 8 8L35 26" />
      <path d="M18 16l-3-3M22.5 12.5V8M13.5 21H9M30 32l3 3M25.5 35.5V40M34.5 27H39" opacity={0.6} />
    </>
  ),
  "proceso-ocr": (
    <>
      <Escaner />
      <path d="M14 15h14M14 20h20M14 33h16" opacity={0.5} />
      <path d="M4 26.5h40" strokeWidth={2.2} />
      <path d="M8 26.5h32" strokeWidth={6} opacity={0.12} />
    </>
  ),
  reconocimiento: (<><Escaner /><path d="M14 18h20M14 24h14M14 30h17" /></>),
  vision: (
    <>
      <Escaner />
      <path d="M11 24s4.8-7.5 13-7.5S37 24 37 24s-4.8 7.5-13 7.5S11 24 11 24z" />
      <circle cx="24" cy="24" r="3.4" fill="currentColor" fillOpacity={0.2} />
    </>
  ),
  confianza: (
    <>
      <path d="M8 34a16 16 0 0 1 32 0" />
      <path d="M8 34a16 16 0 0 1 24.3-13.7" strokeWidth={3.2} />
      <path d="M24 34l7.5-9" />
      <circle cx="24" cy="34" r="2" fill="currentColor" stroke="none" />
    </>
  ),
};

function Dibujo({ tema, className, ...resto }: { tema: Tema; className?: string; "data-icono"?: string }) {
  return (
    <svg {...resto} viewBox="0 0 48 48" fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round"
      strokeLinejoin="round" className={className} aria-hidden="true" focusable="false">
      {DIBUJOS[tema]}
    </svg>
  );
}

interface Props {
  tema: Tema;
  /** Sin marco y sin tono, el dibujo toma el color del texto que lo rodea */
  tono?: Tono;
  tamano?: keyof typeof TAMANOS;
  /** Solo el dibujo, sin marco (para usarlo en línea con texto); el tamaño lo da className */
  sinMarco?: boolean;
  className?: string;
}

export default function IconoTema({ tema, tono, tamano = "md", sinMarco = false, className = "" }: Props) {
  if (sinMarco) return <Dibujo tema={tema} className={`${tono ? TONOS[tono].trazo : ""} ${className}`} data-icono={tema} />;
  const t = TONOS[tono ?? "marca"];
  return (
    <span data-icono={tema} className={`relative inline-flex items-center justify-center shrink-0 overflow-hidden border ${TAMANOS[tamano]} ${t.marco} ${t.trazo} ${className}`}>
      {/* Líneas de seguridad de fondo, como en el banner de cada pantalla */}
      <svg className="absolute inset-0 w-full h-full opacity-[0.16]" viewBox="0 0 48 48" preserveAspectRatio="none" aria-hidden="true">
        <path d="M0 36 Q12 28 24 36 T48 36" fill="none" stroke="currentColor" strokeWidth={0.6} />
        <path d="M0 40 Q12 32 24 40 T48 40" fill="none" stroke="currentColor" strokeWidth={0.6} />
        <path d="M0 44 Q12 36 24 44 T48 44" fill="none" stroke="currentColor" strokeWidth={0.6} />
      </svg>
      <Dibujo tema={tema} className="relative w-[72%] h-[72%]" />
    </span>
  );
}
