import type { ReactNode } from "react";

/**
 * Encabezado de cada pantalla, pensado como el borde de un documento de identidad: un filete del azul
 * de la marca y, de fondo, un guilloche (las líneas finas de seguridad de la cédula) que se dibuja una
 * sola vez al abrir la pantalla. El texto entra con un desplazamiento corto. Con "reducir movimiento"
 * activado no se anima nada (ver .encabezado-pagina en globals.css).
 */

// Guilloche: ondas entrelazadas calculadas una vez (viewBox 640 x 160)
const LINEAS_GUILLOCHE = Array.from({ length: 14 }, (_, i) => {
  const puntos: string[] = [];
  for (let x = 0; x <= 640; x += 8) {
    const y = 80 + 46 * Math.sin(x * 0.021 + i * 0.42) * Math.cos(x * 0.0065 + i * 0.18);
    puntos.push(`${x},${y.toFixed(1)}`);
  }
  return `M${puntos.join(" L")}`;
});

interface Props {
  icono?: ReactNode;
  seccion: string;
  titulo: string;
  descripcion?: ReactNode;
  /** Botones a la derecha (en móvil quedan debajo del título) */
  acciones?: ReactNode;
  /** Contenido extra bajo la descripción, por ejemplo un selector */
  children?: ReactNode;
}

export default function EncabezadoPagina({ icono, seccion, titulo, descripcion, acciones, children }: Props) {
  return (
    <header className="encabezado-pagina relative z-10 rounded-2xl border border-slate-200/90 dark:border-white/8 bg-white dark:bg-[#0e131c] mb-8">
      {/* Decoración en su propia capa recortada: el contenido (p. ej. el selector de fichas) puede desplegarse por fuera */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden rounded-2xl" aria-hidden="true">
        <span className="encabezado-filete absolute inset-y-0 left-0 w-[3px]" />
        <svg
          className="encabezado-guilloche absolute inset-y-0 right-0 h-full w-full sm:w-[62%]"
          viewBox="0 0 640 160"
          preserveAspectRatio="xMaxYMid slice"
          focusable="false"
        >
          {LINEAS_GUILLOCHE.map((d, i) => (
            <path key={i} d={d} pathLength={1} className="encabezado-linea" style={{ animationDelay: `${i * 45}ms` }} />
          ))}
        </svg>
      </div>

      <div className="relative flex flex-col sm:flex-row sm:items-end justify-between gap-5 px-6 py-6 sm:px-8 sm:py-7">
        <div className="min-w-0">
          <p className="encabezado-entra flex items-center gap-2 text-[11px] font-mono font-semibold uppercase tracking-[0.14em] text-[#0336ff] dark:text-[#8aa2ff]">
            {icono && <span className="shrink-0 [&>svg]:w-3.5 [&>svg]:h-3.5">{icono}</span>}
            {seccion}
          </p>
          <h1
            className="encabezado-entra mt-2 text-2xl sm:text-3xl font-semibold tracking-[-0.02em] text-dark-900 dark:text-white"
            style={{ animationDelay: "60ms" }}
          >
            {titulo}
          </h1>
          {descripcion && (
            <p
              className="encabezado-entra mt-1.5 max-w-2xl text-sm leading-relaxed text-slate-500 dark:text-slate-400"
              style={{ animationDelay: "120ms" }}
            >
              {descripcion}
            </p>
          )}
          {children && (
            <div className="encabezado-entra mt-4" style={{ animationDelay: "160ms" }}>
              {children}
            </div>
          )}
        </div>
        {acciones && (
          <div className="encabezado-entra flex flex-wrap items-center gap-2.5 shrink-0" style={{ animationDelay: "160ms" }}>
            {acciones}
          </div>
        )}
      </div>
    </header>
  );
}
