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

export const auth = {
  guardarSesion(data: TokenResponse): void {
    if (typeof window !== "undefined") {
      // Limpiar cualquier residuo de sesión previa de otro usuario
      localStorage.removeItem("ultimo_documento_id");
      localStorage.removeItem("nuevo_archivo_enviado");
      localStorage.removeItem("ocr_docs_en_proceso");
      localStorage.removeItem("ocr_fase_actual");
      sessionStorage.clear();

      localStorage.removeItem(TOKEN_KEY_ANTERIOR);
      localStorage.setItem(USER_KEY, JSON.stringify(data.usuario));
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
