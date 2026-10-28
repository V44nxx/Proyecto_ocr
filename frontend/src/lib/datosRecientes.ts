/**
 * Lo último que trajo cada pantalla, para mostrarlo al instante al volver a ella mientras llega lo actual.
 *
 * Con unos 210 ms por viaje al servidor, cada pantalla se quedaba en blanco esperando datos que se habían visto
 * hace un momento. Ahora arranca con la última respuesta y la reemplaza en cuanto llega la nueva.
 * Vive solo en la memoria de la pestaña (nunca en localStorage ni en el disco): se pierde al recargar y se
 * borra al cerrar sesión o al entrar con otra cuenta (ver auth.ts).
 */
import { EVENTO_SESION_CERRADA } from "./paginasPdf";

const recientes = new Map<string, unknown>();

export const datosRecientes = {
  leer<T>(clave: string): T | undefined {
    return recientes.get(clave) as T | undefined;
  },
  guardar<T>(clave: string, valor: T): void {
    recientes.set(clave, valor);
  },
  vaciar(): void {
    recientes.clear();
  },
};

if (typeof window !== "undefined") {
  window.addEventListener(EVENTO_SESION_CERRADA, () => datosRecientes.vaciar());
}
