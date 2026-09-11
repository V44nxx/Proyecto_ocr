import axios, { type AxiosProgressEvent } from "axios";
import { auth } from "./auth";
import type {
  Usuario,
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

  register: (
    data: { email: string; password: string; nombre?: string; rol?: string } | string,
    nombreOrPassword?: string,
    password?: string
  ) => {
    if (typeof data === "object") {
      return apiClient.post<Usuario>("/api/auth/register", {
        email: data.email.trim(),
        password: data.password,
        nombre: data.nombre?.trim() || data.email.split("@")[0].replace(".", " "),
        rol: data.rol || "usuario",
      });
    }
    return apiClient.post<Usuario>("/api/auth/register", {
      email: data.trim(),
      nombre: nombreOrPassword?.trim() || data.split("@")[0],
      password: password,
      rol: "usuario",
    });
  },

  getUsuarios: () => apiClient.get<Usuario[]>("/api/auth/users"),

  eliminarUsuario: (userId: string) => apiClient.delete<{ message: string }>(`/api/auth/users/${userId}`),

  perfil: () => apiClient.get<Usuario>("/api/auth/me"),
};

// ──────────────────────────────────────────
// DOCUMENTOS
// ──────────────────────────────────────────
export const apiDocumentos = {
  upload: (
    files: File[],
    onUploadProgress?: (progressEvent: AxiosProgressEvent) => void,
    excelFile?: File | null,
  ) => {
    const formData = new FormData();
    files.forEach((file) => {
      formData.append("files", file, file.name);
    });
    if (excelFile) {
      formData.append("excel", excelFile, excelFile.name);
    }
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
    documento_id?: string;
  }) => apiClient.get<Persona[] | PaginatedResponse<Persona>>("/api/personas", { params }),

  detalle: (id: string) =>
    apiClient.get<Persona>(`/api/personas/${id}`),

  actualizar: (id: string, datos: PersonaUpdate) =>
    apiClient.put<Persona>(`/api/personas/${id}`, datos),

  eliminar: (id: string) =>
    apiClient.delete(`/api/personas/${id}`),

  buscarCedula: (cedula: string) =>
    apiClient.get<Persona>(`/api/personas/buscar/cedula/${cedula}`),

  subirPdfCedula: (personaId: string, file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return apiClient.post<Persona>(`/api/personas/${personaId}/subir-pdf`, formData);
  },
};

// ──────────────────────────────────────────
// EXPORTACIÓN
// ──────────────────────────────────────────
export interface DescargarXlsxOptions {
  requiereRevision?: boolean;
  documentoId?: string;
  personaIds?: string[];
  nombreArchivo?: string;
}

export const apiExportacion = {
  descargarXlsx: async (opciones?: DescargarXlsxOptions | boolean) => {
    const opts: DescargarXlsxOptions =
      typeof opciones === "boolean"
        ? { requiereRevision: opciones }
        : opciones || {};

    let response;
    if (opts.personaIds && opts.personaIds.length > 0) {
      response = await apiClient.post(
        "/api/exportacion/xlsx",
        {
          requiere_revision: opts.requiereRevision,
          documento_id: opts.documentoId,
          persona_ids: opts.personaIds,
        },
        { responseType: "blob" }
      );
    } else {
      const params: Record<string, any> = {};
      if (opts.requiereRevision !== undefined) {
        params.requiere_revision = opts.requiereRevision;
      }
      if (opts.documentoId) {
        params.documento_id = opts.documentoId;
      }
      response = await apiClient.get("/api/exportacion/xlsx", {
        params,
        responseType: "blob",
      });
    }

    let nombreFinal = opts.nombreArchivo;
    if (!nombreFinal) {
      const disposition = response.headers?.["content-disposition"];
      if (disposition && typeof disposition === "string") {
        const match = disposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
        if (match && match[1]) {
          nombreFinal = match[1].replace(/['"]/g, "").trim();
        }
      }
    }
    if (!nombreFinal) {
      nombreFinal = `personas_ocr_${new Date().toISOString().slice(0, 10)}.xlsx`;
    }

    const url = window.URL.createObjectURL(new Blob([response.data]));
    const link = document.createElement("a");
    link.href = url;
    link.setAttribute("download", nombreFinal);
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

  agregarPersonaBd: (
    comparacionId: string,
    data: { numero_identificacion: string; nombre_completo?: string }
  ) =>
    apiClient.post<{ mensaje: string; persona_id: string; numero_identificacion: string; nombre_completo?: string }>(
      `/api/comparacion/${comparacionId}/agregar-persona-bd`,
      data
    ),
};

export default apiClient;
