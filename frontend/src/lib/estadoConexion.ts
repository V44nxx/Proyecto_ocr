/**
 * Estado de la conexión que comparten todas las pantallas: sin internet, conexión lenta y servidor sin responder.
 *
 * Lo alimentan los eventos del navegador (online/offline, navigator.connection) y lib/api.ts, que anota cuánto
 * tarda cada petición y cuáles fallan sin respuesta. components/ui/AvisosSistema.tsx lo muestra como avisos.
 */
import { useSyncExternalStore } from "react";

export interface EstadoConexion {
  sinInternet: boolean;
  lenta: boolean;
  servidorCaido: boolean;
}

// Mediana de las últimas peticiones: por encima de 4 s se avisa; el aviso se quita cuando baja de 1,5 s
const UMBRAL_LENTA_MS = 4000;
const UMBRAL_NORMAL_MS = 1500;
const MUESTRAS = 5;

const INICIAL: EstadoConexion = { sinInternet: false, lenta: false, servidorCaido: false };
let estado: EstadoConexion = INICIAL;
let lentaMedida = false;
let lentaSegunNavegador = false;
const duraciones: number[] = [];
const oyentes = new Set<() => void>();

function cambiar(parcial: Partial<EstadoConexion>) {
  const nuevo = { ...estado, ...parcial };
  if (nuevo.sinInternet === estado.sinInternet && nuevo.lenta === estado.lenta && nuevo.servidorCaido === estado.servidorCaido) {
    return;
  }
  estado = nuevo;
  oyentes.forEach((oyente) => oyente());
}

function actualizarLenta() {
  cambiar({ lenta: lentaMedida || lentaSegunNavegador });
}

export const conexion = {
  obtener: (): EstadoConexion => estado,

  suscribir(oyente: () => void): () => void {
    oyentes.add(oyente);
    return () => oyentes.delete(oyente);
  },

  sinInternet(valor: boolean) {
    cambiar({ sinInternet: valor, ...(valor ? {} : { servidorCaido: false }) });
  },

  /** Llegó una respuesta (con cualquier código): el servidor está vivo. `medir` solo en peticiones livianas. */
  respuesta(milisegundos: number, medir: boolean) {
    if (estado.servidorCaido || estado.sinInternet) cambiar({ servidorCaido: false, sinInternet: false });
    if (!medir) return;
    duraciones.push(milisegundos);
    if (duraciones.length > MUESTRAS) duraciones.shift();
    const ordenadas = [...duraciones].sort((a, b) => a - b);
    const mediana = ordenadas[Math.floor(ordenadas.length / 2)];
    if (duraciones.length >= 3 && mediana > UMBRAL_LENTA_MS) lentaMedida = true;
    else if (mediana < UMBRAL_NORMAL_MS) lentaMedida = false;
    actualizarLenta();
  },

  /** Una petición falló sin respuesta: sin internet si el navegador lo sabe; si no, el servidor no contesta. */
  sinRespuesta() {
    if (typeof navigator !== "undefined" && navigator.onLine === false) cambiar({ sinInternet: true });
    else cambiar({ servidorCaido: true });
  },

  /** El proxy respondió 502, 503 o 504: el servidor se está reiniciando o actualizando. */
  servidorNoDisponible() {
    cambiar({ servidorCaido: true });
  },

  /** Lo que estima el navegador (Chrome y Edge): red 2G o tiempos de ida y vuelta muy altos. */
  redSegunNavegador(lenta: boolean) {
    lentaSegunNavegador = lenta;
    actualizarLenta();
  },
};

export function useConexion(): EstadoConexion {
  return useSyncExternalStore(conexion.suscribir, conexion.obtener, () => INICIAL);
}
