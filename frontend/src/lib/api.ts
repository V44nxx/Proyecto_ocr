/**
 * Cliente Axios para comunicación con el backend FastAPI
 */

import axios, { AxiosError } from "axios";
import { auth } from "./auth";
import type {
  TokenResponse,
  Documento,
  Persona,
  PersonaUpdate,
  PaginatedResponse,
  Comparacion,
  Diferencia,
  DashboardStats,
} from "@/types";

const getBaseUrl = (): string => {
  if (typeof window !== "undefined") {
    const envUrl = process.env.NEXT_PUBLIC_API_URL;
    if (envUrl && !envUrl.includes("localhost") && !envUrl.includes("127.0.0.1")) {
      return envUrl;
    }
    const hostname = window.location.hostname;
    if (hostname !== "localhost" && hostname !== "127.0.0.1") {
      return `${window.location.protocol}//${hostname}:8000`;
    }
  }
  return process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
};

const BASE_URL = getBaseUrl();

const apiClient = axios.create({
  baseURL: BASE_URL,
  timeout: 120000, // 2 minutos para OCR
  headers: {
    "Content-Type": "application/json",
  },
});

// Interceptor: agregar token JWT
apiClient.interceptors.request.use((config) => {
  const token = auth.getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Interceptor: manejar errores de autenticación
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      auth.cerrarSesion();
      if (typeof window !== "undefined") {
        window.location.href = "/";
      }
    }
    return Promise.reject(error);
  }
);

// ──────────────────────────────────────────
// AUTH
// ──────────────────────────────────────────
export const apiAuth = {
  login: (email: string, password: string) =>
    apiClient.post<TokenResponse>("/api/auth/login", { email, password }),

  register: (email: string, nombre: string, password: string) =>
    apiClient.post("/api/auth/register", { email, nombre, password }),

  perfil: () => apiClient.get("/api/auth/me"),
};

// ──────────────────────────────────────────
// DOCUMENTOS
// ──────────────────────────────────────────
export const apiDocumentos = {
  upload: (files: File[]) => {
    const formData = new FormData();
    files.forEach((file) => formData.append("files", file));
    return apiClient.post("/api/documentos/upload", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
  },

  listar: (params?: { skip?: number; limit?: number; estado?: string }) =>
    apiClient.get<Documento[]>("/api/documentos", { params }),

  detalle: (id: string) =>
    apiClient.get<Documento>(`/api/documentos/${id}`),

  estado: (id: string) =>
    apiClient.get(`/api/documentos/${id}/estado`),

  eliminar: (id: string) =>
    apiClient.delete(`/api/documentos/${id}`),

  estadisticas: () =>
    apiClient.get<DashboardStats>("/api/documentos/dashboard/estadisticas"),
};

// ──────────────────────────────────────────
// PERSONAS
// ──────────────────────────────────────────
export const apiPersonas = {
  listar: (params?: {
    skip?: number;
    limit?: number;
    requiere_revision?: boolean;
    buscar?: string;
  }) => apiClient.get<Persona[] | PaginatedResponse<Persona>>("/api/personas", { params }),

  detalle: (id: string) =>
    apiClient.get<Persona>(`/api/personas/${id}`),

  actualizar: (id: string, datos: PersonaUpdate) =>
    apiClient.put<Persona>(`/api/personas/${id}`, datos),

  eliminar: (id: string) =>
    apiClient.delete(`/api/personas/${id}`),

  buscarCedula: (cedula: string) =>
    apiClient.get<Persona>(`/api/personas/buscar/cedula/${cedula}`),
};

// ──────────────────────────────────────────
// EXPORTACIÓN
// ──────────────────────────────────────────
export const apiExportacion = {
  descargarXlsx: async (requiereRevision?: boolean) => {
    const params = requiereRevision !== undefined ? { requiere_revision: requiereRevision } : {};
    const response = await apiClient.get("/api/exportacion/xlsx", {
      params,
      responseType: "blob",
    });

    // Trigger descarga en browser
    const url = window.URL.createObjectURL(new Blob([response.data]));
    const link = document.createElement("a");
    link.href = url;
    const nombre = `personas_ocr_${new Date().toISOString().slice(0, 10)}.xlsx`;
    link.setAttribute("download", nombre);
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  },
};

// ──────────────────────────────────────────
// COMPARACIÓN
// ──────────────────────────────────────────
export const apiComparacion = {
  uploadExcel: (file: File, ejecutar: boolean = true) => {
    const formData = new FormData();
    formData.append("file", file);
    return apiClient.post<Comparacion>(
      `/api/comparacion/upload?ejecutar=${ejecutar}`,
      formData,
      { headers: { "Content-Type": "multipart/form-data" } }
    );
  },

  ejecutar: (id: string) =>
    apiClient.post(`/api/comparacion/${id}/ejecutar`),

  listar: () =>
    apiClient.get<Comparacion[]>("/api/comparacion"),

  detalle: (id: string) =>
    apiClient.get<Comparacion>(`/api/comparacion/${id}`),

  diferencias: (id: string, tipo?: string) =>
    apiClient.get<Diferencia[]>(`/api/comparacion/${id}/diferencias`, {
      params: tipo ? { tipo } : {},
    }),

  descargarReporte: async (id: string, nombre: string) => {
    const response = await apiClient.get(`/api/comparacion/${id}/reporte`, {
      responseType: "blob",
    });
    const url = window.URL.createObjectURL(new Blob([response.data]));
    const link = document.createElement("a");
    link.href = url;
    link.setAttribute("download", `reporte_${nombre}.xlsx`);
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  },
};

export default apiClient;
