/**
 * Estado de la sesión en el navegador.
 *
 * El token viaja solo en una cookie HttpOnly que pone el backend: ningún script lo puede leer.
 * Aquí solo se guarda el usuario (nombre, rol) para pintar la interfaz; si la cookie ya no sirve,
 * el backend responde 401 y lib/api.ts cierra la sesión local.
 */

import { TokenResponse, Usuario } from "@/types";

const USER_KEY = "ocr_user";
// Las versiones anteriores a la 2.8.0 guardaban el token aquí; se borra al entrar o salir
const TOKEN_KEY_ANTERIOR = "ocr_access_token";
// Solo la hora en que vence la sesión (para avisar antes), nunca el token
const VENCE_KEY = "ocr_sesion_vence";

/** Hora de vencimiento (ms) que trae el token. El token no se guarda: solo se lee su campo exp. */
function venceDelToken(token?: string | null): number | null {
  try {
    const carga = token?.split(".")[1];
    if (!carga) return null;
    const datos = JSON.parse(atob(carga.replace(/-/g, "+").replace(/_/g, "/")));
    return typeof datos.exp === "number" ? datos.exp * 1000 : null;
  } catch {
    return null;
  }
}

export const auth = {
  /** Una sesión nueva o renovada (al cambiar la contraseña): anota cuándo vence */
  anotarVencimiento(token?: string | null): void {
    if (typeof window === "undefined") return;
    const vence = venceDelToken(token);
    if (vence) localStorage.setItem(VENCE_KEY, String(vence));
  },

  vencimiento(): number | null {
    if (typeof window === "undefined") return null;
    const valor = Number(localStorage.getItem(VENCE_KEY));
    return Number.isFinite(valor) && valor > 0 ? valor : null;
  },

  guardarSesion(data: Pick<TokenResponse, "usuario"> & { access_token?: string | null }): void {
    if (typeof window !== "undefined") {
      // Limpiar cualquier residuo de sesión previa de otro usuario
      localStorage.removeItem("ultimo_documento_id");
      localStorage.removeItem("nuevo_archivo_enviado");
      localStorage.removeItem("ocr_docs_en_proceso");
      localStorage.removeItem("ocr_fase_actual");
      sessionStorage.clear();
      // Lo que quedó en memoria de la cuenta anterior (vistas previas, datos recientes) se suelta
      window.dispatchEvent(new Event("kondid:sesion-cerrada"));

      localStorage.removeItem(TOKEN_KEY_ANTERIOR);
      localStorage.setItem(USER_KEY, JSON.stringify(data.usuario));
      localStorage.removeItem(VENCE_KEY);
      this.anotarVencimiento(data.access_token);
    }
  },

  getUsuario(): Usuario | null {
    if (typeof window !== "undefined") {
      const data = localStorage.getItem(USER_KEY);
      if (data) {
        try {
          return JSON.parse(data) as Usuario;
        } catch {
          return null;
        }
      }
    }
    return null;
  },

  isAuthenticated(): boolean {
    return !!this.getUsuario();
  },

  cerrarSesion(): void {
    if (typeof window !== "undefined") {
      localStorage.removeItem(TOKEN_KEY_ANTERIOR);
      localStorage.removeItem(USER_KEY);
      localStorage.removeItem(VENCE_KEY);
      localStorage.removeItem("ultimo_documento_id");
      localStorage.removeItem("nuevo_archivo_enviado");
      localStorage.removeItem("ocr_docs_en_proceso");
      localStorage.removeItem("ocr_fase_actual");
      sessionStorage.clear();
      // Las vistas previas de documentos que quedaron en memoria se liberan (ver lib/paginasPdf.ts)
      window.dispatchEvent(new Event("kondid:sesion-cerrada"));
    }
  },
};
