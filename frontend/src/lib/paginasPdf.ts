/**
 * Vista previa de las páginas de un PDF.
 *
 * La imagen se pide con fetch y la sesión en la cabecera Authorization (nunca en la dirección, que queda
 * en el historial y en los registros del servidor). Se guarda solo en memoria mientras la pestaña está
 * abierta: el servidor la marca como no-store para que una cédula no quede en el disco del navegador.
 */
import { useEffect, useState } from "react";
import { apiDocumentos } from "./api";

export const EVENTO_SESION_CERRADA = "kondid:sesion-cerrada";

const LIMITE_EN_MEMORIA = 40;
const paginas = new Map<string, Promise<string>>();

function liberar(promesa: Promise<string>) {
  promesa.then((url) => URL.revokeObjectURL(url)).catch(() => undefined);
}

/** URL local (blob:) de la página; varias peticiones de la misma página comparten la descarga. */
export function obtenerPaginaPdf(documentoId: string, pagina: number, dpi: number): Promise<string> {
  const clave = `${documentoId}:${pagina}:${dpi}`;
  const existente = paginas.get(clave);
  if (existente) {
    // Se vuelve a insertar para que quede como la más reciente
    paginas.delete(clave);
    paginas.set(clave, existente);
    return existente;
  }

  const promesa = apiDocumentos.paginaPdf(documentoId, pagina, dpi).then((r) => URL.createObjectURL(r.data));
  paginas.set(clave, promesa);
  promesa.catch(() => {
    if (paginas.get(clave) === promesa) paginas.delete(clave);
  });

  while (paginas.size > LIMITE_EN_MEMORIA) {
    const masVieja = paginas.keys().next().value;
    if (masVieja === undefined) break;
    const vieja = paginas.get(masVieja);
    paginas.delete(masVieja);
    if (vieja) liberar(vieja);
  }
  return promesa;
}

/** Pide la página por adelantado (por ejemplo, al pasar el cursor por una persona). */
export function precargarPaginaPdf(documentoId: string, pagina: number, dpi: number): void {
  obtenerPaginaPdf(documentoId, pagina, dpi).catch(() => undefined);
}

export function limpiarPaginasPdf(): void {
  paginas.forEach(liberar);
  paginas.clear();
}

if (typeof window !== "undefined") {
  window.addEventListener(EVENTO_SESION_CERRADA, limpiarPaginasPdf);
}

/** Estado de una página para mostrarla en un <img>: src cuando llega, error si no se pudo traer. */
export function usePaginaPdf(documentoId: string | null | undefined, pagina: number, dpi: number, activo = true) {
  const [estado, setEstado] = useState<{ src: string | null; error: boolean }>({ src: null, error: false });

  useEffect(() => {
    if (!documentoId || !activo) {
      setEstado({ src: null, error: false });
      return;
    }
    let vigente = true;
    setEstado({ src: null, error: false });
    obtenerPaginaPdf(documentoId, pagina, dpi)
      .then((src) => {
        if (vigente) setEstado({ src, error: false });
      })
      .catch(() => {
        if (vigente) setEstado({ src: null, error: true });
      });
    return () => {
      vigente = false;
    };
  }, [documentoId, pagina, dpi, activo]);

  return estado;
}
