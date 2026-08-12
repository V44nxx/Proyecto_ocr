/**
 * Auth utilities: JWT storage y gestión de sesión
 */

import { TokenResponse, Usuario } from "@/types";

const TOKEN_KEY = "ocr_access_token";
const USER_KEY = "ocr_user";

export const auth = {
  guardarSesion(data: TokenResponse): void {
    if (typeof window !== "undefined") {
      localStorage.setItem(TOKEN_KEY, data.access_token);
      localStorage.setItem(USER_KEY, JSON.stringify(data.usuario));
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
    }
  },
};
