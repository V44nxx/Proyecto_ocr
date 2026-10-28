"use client";

/**
 * Reemplaza a <select> cuando hay pocas opciones (por ejemplo, el sexo): todas a la vista como botones,
 * con semántica de grupo de radios para lectores de pantalla y flechas del teclado.
 */

interface Opcion {
  valor: string;
  etiqueta: string;
}

interface Props {
  id?: string;
  etiqueta: string;
  valor: string;
  opciones: Opcion[];
  onCambiar: (valor: string) => void;
  className?: string;
}

export default function OpcionesSegmentadas({ id, etiqueta, valor, opciones, onCambiar, className = "" }: Props) {
  const alTeclear = (e: React.KeyboardEvent<HTMLButtonElement>, i: number) => {
    const paso = e.key === "ArrowRight" || e.key === "ArrowDown" ? 1 : e.key === "ArrowLeft" || e.key === "ArrowUp" ? -1 : 0;
    if (!paso) return;
    e.preventDefault();
    const siguiente = opciones[(i + paso + opciones.length) % opciones.length];
    onCambiar(siguiente.valor);
    (e.currentTarget.parentElement?.children[(i + paso + opciones.length) % opciones.length] as HTMLElement)?.focus();
  };

  return (
    <div id={id} role="radiogroup" aria-label={etiqueta}
      className={`flex flex-wrap gap-1 p-1 rounded-lg bg-slate-100 dark:bg-white/4 border border-slate-200 dark:border-white/8 ${className}`}>
      {opciones.map((o, i) => {
        const activa = o.valor === valor;
        return (
          <button
            key={o.valor || "vacio"}
            type="button"
            role="radio"
            aria-checked={activa}
            tabIndex={activa || (!valor && i === 0) ? 0 : -1}
            onClick={() => onCambiar(o.valor)}
            onKeyDown={(e) => alTeclear(e, i)}
            className={`flex-1 min-w-fit px-2.5 py-1 rounded-md text-[11px] font-medium whitespace-nowrap transition-colors cursor-pointer focus:outline-hidden focus-visible:ring-2 focus-visible:ring-[#0071E3]/40 ${
              activa
                ? "bg-white dark:bg-[#1b2232] text-[#0071E3] dark:text-[#4C9BFF] shadow-xs border border-slate-200 dark:border-white/10"
                : "text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200 border border-transparent"
            }`}
          >
            {o.etiqueta}
          </button>
        );
      })}
    </div>
  );
}
