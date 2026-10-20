/**
 * Auth utilities: JWT storage y gestión de sesión
 */

import { TokenResponse, Usuario } from "@/types";

const TOKEN_KEY = "ocr_access_token";
const USER_KEY = "ocr_user";

export const auth = {
  guardarSesion(data: TokenResponse): void {
    if (typeof window !== "undefined") {
      // Limpiar cualquier residuo de sesión previa de otro usuario
      localStorage.removeItem("ultimo_documento_id");
      localStorage.removeItem("nuevo_archivo_enviado");
      localStorage.removeItem("ocr_docs_en_proceso");
      localStorage.removeItem("ocr_fase_actual");
      sessionStorage.clear();

      localStorage.setItem(TOKEN_KEY, data.access_token);
      localStorage.setItem(USER_KEY, JSON.stringify(data.usuario));
    }
  },

  /** Reemplaza solo el token (por ejemplo, al cambiar la contraseña) sin limpiar el resto de la sesión. */
  actualizarToken(token: string): void {
    if (typeof window !== "undefined") {
      localStorage.setItem(TOKEN_KEY, token);
    }
  },

  getToken(): string | null {
    if (typeof window !== "undefined") {
      return localStorage.getItem(TOKEN_KEY);
    }
    return null;
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
    return !!this.getToken();
  },

  cerrarSesion(): void {
    if (typeof window !== "undefined") {
      localStorage.removeItem(TOKEN_KEY);
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
