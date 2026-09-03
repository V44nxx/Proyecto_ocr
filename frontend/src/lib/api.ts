import axios, { type AxiosProgressEvent } from "axios";
import { auth } from "./auth";
import type {
  TokenResponse,
  Documento,
  DocumentoEstadoResponse,
  Persona,
  PersonaUpdate,
  PaginatedResponse,
  Comparacion,
  Diferencia,
  DashboardStats,
} from "@/types";

/**
 * Extrae de forma segura un mensaje legible como string de cualquier error de API,
 * evitando pasar objetos o arrays de Pydantic/FastAPI directamente a React (Minified React Error #31)
 */
export function getErrorMessage(err: unknown, defaultMsg: string = "Ocurrió un error inesperado"): string {
  if (!err) return defaultMsg;
  if (typeof err === "string") return err;

  const anyErr = err as any;
  const data = anyErr?.response?.data;

  if (data) {
    if (typeof data === "string") return data;
    if (typeof data.detail === "string") return data.detail;
    if (Array.isArray(data.detail)) {
      const messages = data.detail.map((d: any) => {
        if (typeof d === "string") return d;
        if (d?.msg) {
          const loc = Array.isArray(d.loc) ? d.loc.filter((l: any) => l !== "body").join(".") : "";
          return loc ? `${loc}: ${d.msg}` : d.msg;
        }
        return JSON.stringify(d);
      });
      return messages.filter(Boolean).join("; ") || defaultMsg;
    }
    if (data.message && typeof data.message === "string") return data.message;
    if (data.error && typeof data.error === "string") return data.error;
  }

  if (anyErr.message && typeof anyErr.message === "string") {
    if (anyErr.message.toLowerCase().includes("network error")) {
      return "Error de red: No se pudo conectar con el servidor (el servicio de backend podría estar reiniciándose o actualizándose en Dokploy). Por favor reintenta en unos segundos.";
    }
    if (anyErr.message.toLowerCase().includes("timeout")) {
      return "Tiempo de espera agotado al transferir el archivo. Por favor reintenta la subida.";
    }
    return anyErr.message;
  }

  return defaultMsg;
}

function getBaseUrl(): string {
  // En el navegador:
  if (typeof window !== "undefined") {
    // Si estamos en el dominio de producción v44nxx.online (ej: proyectooocr.v44nxx.online)
    if (window.location.hostname.endsWith("v44nxx.online")) {
      return "https://api.v44nxx.online";
    }
    if (process.env.NEXT_PUBLIC_API_URL && !process.env.NEXT_PUBLIC_API_URL.includes("localhost")) {
      return process.env.NEXT_PUBLIC_API_URL.replace(/\/$/, "");
    }
    return "";
  }
  // Server-side o SSR: usar variable de entorno o fallback a https://api.v44nxx.online
  return process.env.INTERNAL_BACKEND_URL || process.env.BACKEND_URL || process.env.NEXT_PUBLIC_API_URL || "https://api.v44nxx.online";
}

const apiClient = axios.create({
  baseURL: getBaseUrl(),
  timeout: 300000, // 5 minutos para subidas y OCR
});

// Interceptor: agregar token JWT y gestionar Content-Type para FormData
apiClient.interceptors.request.use((config) => {
  const token = auth.getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }

  // Si enviamos FormData, eliminar cualquier Content-Type manual para que Axios y el navegador
  // generen el multipart/form-data con el delimitador boundary exacto
  if (typeof FormData !== "undefined" && config.data instanceof FormData) {
    if (config.headers) {
      delete config.headers["Content-Type"];
      delete config.headers["content-type"];
    }
  } else if (!config.headers["Content-Type"] && !config.headers["content-type"]) {
    config.headers["Content-Type"] = "application/json";
  }

  return config;
});

// Interceptor: manejar errores de autenticación (401)
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
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
  upload: (
    files: File[],
    onUploadProgress?: (progressEvent: AxiosProgressEvent) => void
  ) => {
    const formData = new FormData();
    files.forEach((file) => {
      formData.append("files", file, file.name);
    });
    return apiClient.post("/api/documentos/upload", formData, {
      onUploadProgress,
    });
  },

  listar: (params?: { skip?: number; limit?: number; estado?: string }) =>
    apiClient.get<Documento[]>("/api/documentos", { params }),

  detalle: (id: string) =>
    apiClient.get<Documento>(`/api/documentos/${id}`),

  estado: (id: string) =>
    apiClient.get<DocumentoEstadoResponse>(`/api/documentos/${id}/estado`),

  eliminar: (id: string) =>
    apiClient.delete(`/api/documentos/${id}`),

  estadisticas: () =>
    apiClient.get<DashboardStats>("/api/documentos/dashboard/estadisticas"),

  /**
   * Construye la URL para la imagen de preview de una página del PDF.
   * Incluye el token JWT como query param para autenticación en <img src>.
   */
  paginaPdfUrl: (documentoId: string, pagina: number, dpi: number = 150): string => {
    const base = getBaseUrl();
    const token = auth.getToken();
    const params = new URLSearchParams({ dpi: String(dpi) });
    if (token) params.set("token", token);
    return `${base}/api/documentos/${documentoId}/pagina/${pagina}?${params.toString()}`;
  },
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
      formData
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
    link.setAttribute("download", `reporte_auditoria_${nombre.replace(/\.[^/.]+$/, "")}.xlsx`);
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  },

  corregirCampo: (comparacionId: string, data: { numero_identificacion: string; campo: string; nuevo_valor: string }) =>
    apiClient.post(`/api/comparacion/${comparacionId}/corregir-campo`, data),
};

export default apiClient;
