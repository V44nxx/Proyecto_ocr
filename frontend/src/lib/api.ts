import axios, { type AxiosProgressEvent, type InternalAxiosRequestConfig } from "axios";
import { auth } from "./auth";
import { conexion } from "./estadoConexion";
import type {
  Usuario,
  TokenResponse,
  LoginResponse,
  ConfigurarDobleFactor,
  Documento,
  DocumentoEstadoResponse,
  Persona,
  PersonaUpdate,
  PaginatedResponse,
  Comparacion,
  Diferencia,
  DashboardStats,
  SeguimientoConfig,
  RegistrosAuditoria,
  FichaExistenteInfo,
  AccionFicha,
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
  const estado: number | undefined = anyErr?.response?.status;

  // El proxy responde con una página HTML (no con JSON) cuando el servidor no está o el archivo es enorme
  if (estado === 502 || estado === 503 || estado === 504) return MENSAJE_SERVIDOR_ACTUALIZANDO;
  if (estado === 413 && typeof data !== "object") return "El archivo es demasiado grande para subirlo.";

  if (data) {
    if (typeof data === "string") return data.trimStart().startsWith("<") ? defaultMsg : data;
    if (typeof data.detail === "string") return data.detail;
    if (Array.isArray(data.detail)) {
      const messages = data.detail.map((d: any) => {
        if (typeof d === "string") return d;
        if (d?.msg) {
          // Los validadores propios del backend ya escriben una frase completa: se muestra tal cual
          if (d.type === "value_error") return String(d.msg).replace(/^Value error, /, "");
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
      if (typeof navigator !== "undefined" && navigator.onLine === false) return MENSAJE_SIN_INTERNET;
      return MENSAJE_SERVIDOR_SIN_RESPUESTA;
    }
    if (anyErr.message.toLowerCase().includes("timeout")) {
      return "La operación tardó demasiado y se canceló. Si tu conexión está lenta, prueba con menos archivos a la vez o desde una red más estable.";
    }
    return anyErr.message;
  }

  return defaultMsg;
}

export const MENSAJE_SIN_INTERNET = "Sin conexión a internet. Revisa tu Wi-Fi o tus datos móviles y vuelve a intentarlo.";
export const MENSAJE_SERVIDOR_SIN_RESPUESTA =
  "No se pudo conectar con el servidor de KondID. Si tu internet funciona, puede estar actualizándose: intenta de nuevo en unos minutos.";
export const MENSAJE_SERVIDOR_ACTUALIZANDO =
  "El servidor de KondID se está reiniciando o actualizando. Intenta de nuevo en unos minutos.";

/** Aviso que muestra la pantalla de inicio de sesión al llegar (lo deja quien cierra la sesión) */
export const CLAVE_AVISO_LOGIN = "kondid_aviso_login";

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
  withCredentials: true, // la sesión viaja en la cookie HttpOnly que pone el backend
});

// Interceptor: gestionar Content-Type para FormData
apiClient.interceptors.request.use((config) => {
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

  (config as ConfigMedida).inicioMs = Date.now();
  return config;
});

type ConfigMedida = InternalAxiosRequestConfig & { inicioMs?: number };

// La página se recarga al ir al inicio, así que esto vuelve a false sola
let saliendoPorSesionCerrada = false;

/** Cuánto tardó la petición, y si sirve para medir la conexión: las subidas y descargas tardan por su tamaño */
function medicion(config?: ConfigMedida): [number, boolean] {
  const ms = config?.inicioMs ? Date.now() - config.inicioMs : 0;
  const pesada = (typeof FormData !== "undefined" && config?.data instanceof FormData) || config?.responseType === "blob";
  return [ms, !!config?.inicioMs && !pesada];
}

// Interceptor: estado de la conexión y errores de autenticación (401)
apiClient.interceptors.response.use(
  (response) => {
    conexion.respuesta(...medicion(response.config));
    return response;
  },
  (error) => {
    const estado = error.response?.status;
    if (axios.isCancel(error)) {
      // Cancelada por la propia pantalla: no dice nada de la conexión
    } else if (estado === 502 || estado === 503 || estado === 504) {
      conexion.servidorNoDisponible();
    } else if (error.response) {
      conexion.respuesta(...medicion(error.config));
    } else if (error.code !== "ECONNABORTED") {
      conexion.sinRespuesta();
    }

    // En el login un 401 significa credenciales incorrectas: se muestra el error sin recargar la página.
    // Una pantalla hace varias peticiones a la vez: solo la primera respuesta 401 cierra la sesión y deja el aviso
    // (las siguientes volverían a limpiar sessionStorage y lo borrarían)
    const url = String(error.config?.url || "");
    const esLogin = url.includes("/api/auth/login") || url.includes("/api/auth/logout");
    if (estado === 401 && !esLogin && !saliendoPorSesionCerrada) {
      saliendoPorSesionCerrada = true;
      const habiaSesion = auth.isAuthenticated();
      auth.cerrarSesion();
      if (typeof window !== "undefined") {
        if (habiaSesion) {
          try { sessionStorage.setItem(CLAVE_AVISO_LOGIN, "sesion_cerrada"); } catch {}
        }
        window.location.href = "/";
      }
    }
    return Promise.reject(error);
  }
);

// Las listas largas se piden por páginas (el servidor entrega hasta 1000 por vez) y aquí se juntan todas.
// Antes cada pantalla pedía una sola página y lo que pasaba de 300 personas o 100 diferencias no se veía
const TAMANO_PAGINA = 500;
const MAXIMO_PAGINAS = 100;

async function todasLasPaginas<T>(
  pedir: (skip: number, limit: number) => Promise<{ data: T[] | PaginatedResponse<T> }>
): Promise<{ data: T[] }> {
  const todos: T[] = [];
  for (let n = 0; n < MAXIMO_PAGINAS; n++) {
    const { data } = await pedir(n * TAMANO_PAGINA, TAMANO_PAGINA);
    const pagina = Array.isArray(data) ? data : data?.items ?? [];
    todos.push(...pagina);
    if (pagina.length < TAMANO_PAGINA) break;
  }
  return { data: todos };
}

// ──────────────────────────────────────────
// AUTH
// ──────────────────────────────────────────
export const apiAuth = {
  login: (email: string, password: string) =>
    apiClient.post<LoginResponse>("/api/auth/login", { email, password }),

  /** Segundo paso de un administrador: código de la app o uno de respaldo. */
  loginDobleFactor: (desafio: string, codigo: string) =>
    apiClient.post<LoginResponse>("/api/auth/login/2fa", { desafio, codigo }),

  /** Primer ingreso de un administrador: genera el QR para vincular la app de autenticación. */
  configurarDobleFactor: (desafio: string) =>
    apiClient.post<ConfigurarDobleFactor>("/api/auth/login/2fa/configurar", { desafio }),

  /** Confirma con el primer código; la respuesta trae los códigos de respaldo (se muestran una sola vez). */
  activarDobleFactor: (desafio: string, codigo: string) =>
    apiClient.post<LoginResponse>("/api/auth/login/2fa/activar", { desafio, codigo }),

  /** Cierra la sesión en el servidor: la cookie se borra y ese token deja de servir aunque alguien lo tenga. */
  logout: () => apiClient.post<{ message: string }>("/api/auth/logout"),

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

  /** Envía el enlace de recuperación; la respuesta es la misma exista o no el correo. */
  olvidePassword: (email: string) =>
    apiClient.post<{ message: string }>("/api/auth/olvide-password", { email: email.trim() }),

  restablecerPassword: (token: string, passwordNueva: string) =>
    apiClient.post<{ message: string }>("/api/auth/restablecer-password", { token, password_nueva: passwordNueva }),

  /** Las demás sesiones se cierran; esta sigue abierta con la cookie nueva que pone el backend. */
  cambiarPassword: (passwordActual: string, passwordNueva: string) =>
    apiClient.post<TokenResponse>("/api/auth/cambiar-password", {
      password_actual: passwordActual,
      password_nueva: passwordNueva,
    }),

  restablecerPasswordUsuario: (userId: string, passwordNueva: string) =>
    apiClient.post<{ message: string }>(`/api/auth/users/${userId}/password`, { password_nueva: passwordNueva }),

  /** Desvincula la app de autenticación de otro usuario y cierra sus sesiones (solo administrador). */
  restablecerDobleFactorUsuario: (userId: string) =>
    apiClient.post<{ message: string }>(`/api/auth/users/${userId}/doble-factor/restablecer`),

  /** Registro de auditoría (solo administrador), lo más reciente primero. */
  auditoria: (params: { limite?: number; desde?: number; accion?: string; email?: string } = {}) =>
    apiClient.get<RegistrosAuditoria>("/api/auth/auditoria", { params }),
};

// ──────────────────────────────────────────
// DOCUMENTOS
// ──────────────────────────────────────────
export const apiDocumentos = {
  upload: (
    files: File[],
    onUploadProgress?: (progressEvent: AxiosProgressEvent) => void,
    excelFile?: File | null,
    signal?: AbortSignal,
    acciones?: AccionFicha[],
  ) => {
    const formData = new FormData();
    files.forEach((file) => {
      formData.append("files", file, file.name);
    });
    if (excelFile) {
      formData.append("excel", excelFile, excelFile.name);
    }
    if (acciones && acciones.length > 0) {
      formData.append("acciones", JSON.stringify(acciones));
    }
    return apiClient.post("/api/documentos/upload", formData, {
      onUploadProgress,
      signal,
    });
  },

  fichasExistentes: (nombres: string[]) =>
    apiClient.post<FichaExistenteInfo[]>("/api/documentos/fichas-existentes", { nombres }),

  cancelar: (datos: {
    documento_ids?: string[];
    comparacion_id?: string | null;
    todos_en_proceso?: boolean;
  }) =>
    apiClient.post<{ ok: boolean; eliminados: number; mensaje: string }>(
      "/api/documentos/cancelar",
      datos
    ),

  listar: (params?: { skip?: number; limit?: number; estado?: string; solo_subida?: boolean }) =>
    apiClient.get<Documento[]>("/api/documentos", { params }),

  /** Todas las fichas, página por página */
  listarTodos: (params?: { estado?: string; solo_subida?: boolean }) =>
    todasLasPaginas<Documento>((skip, limit) =>
      apiClient.get<Documento[]>("/api/documentos", { params: { ...params, skip, limit } })),

  detalle: (id: string) =>
    apiClient.get<Documento>(`/api/documentos/${id}`),

  estado: (id: string) =>
    apiClient.get<DocumentoEstadoResponse>(`/api/documentos/${id}/estado`),

  eliminar: (id: string, permanente: boolean = false) =>
    apiClient.delete(`/api/documentos/${id}`, { params: { permanente } }),

  estadisticas: (documentoId?: string) =>
    apiClient.get<DashboardStats>("/api/documentos/dashboard/estadisticas", {
      params: documentoId && documentoId !== "todos" ? { documento_id: documentoId } : undefined,
    }),

  /**
   * Obtiene las personas de un documento específico (con fallback al snapshot histórico si fue vaciada)
   */
  obtenerPersonas: (documentoId: string) =>
    apiClient.get<Persona[]>(`/api/documentos/${documentoId}/personas`),

  /**
   * Imagen de una página del PDF. Se pide con la sesión en la cabecera (no en la dirección);
   * para mostrarla, usar usePaginaPdf de "@/lib/paginasPdf".
   */
  paginaPdf: (documentoId: string, pagina: number, dpi: number = 150) =>
    apiClient.get<Blob>(`/api/documentos/${documentoId}/pagina/${pagina}`, {
      params: { dpi },
      responseType: "blob",
    }),
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

  /** Todas las personas que cumplen el filtro, página por página */
  listarTodas: (params?: { requiere_revision?: boolean; buscar?: string; documento_id?: string }) =>
    todasLasPaginas<Persona>((skip, limit) =>
      apiClient.get<Persona[] | PaginatedResponse<Persona>>("/api/personas", { params: { ...params, skip, limit } })),

  detalle: (id: string) =>
    apiClient.get<Persona>(`/api/personas/${id}`),

  actualizar: (id: string, datos: PersonaUpdate) =>
    apiClient.put<Persona>(`/api/personas/${id}`, datos),

  eliminar: (id: string) =>
    apiClient.delete(`/api/personas/${id}`),

  eliminarMultiples: (ids: string[]) =>
    apiClient.post<{ eliminadas: number }>("/api/personas/batch-delete", { ids }),

  vaciarTodas: (params?: { documento_id?: string }) =>
    apiClient.delete<{ eliminadas: number; mensaje: string }>("/api/personas/vaciar/todas", { params }),

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
  soloMenores?: boolean;
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
          solo_menores: opts.soloMenores,
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
      if (opts.soloMenores !== undefined) {
        params.solo_menores = opts.soloMenores;
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

  /** Todo el historial, página por página */
  listar: () =>
    todasLasPaginas<Comparacion>((skip, limit) =>
      apiClient.get<Comparacion[]>("/api/comparacion", { params: { skip, limit } })),

  detalle: (id: string) =>
    apiClient.get<Comparacion>(`/api/comparacion/${id}`),

  /** Todas las diferencias, página por página */
  diferencias: (id: string, tipo?: string) =>
    todasLasPaginas<Diferencia>((skip, limit) =>
      apiClient.get<Diferencia[]>(`/api/comparacion/${id}/diferencias`, {
        params: { ...(tipo ? { tipo } : {}), skip, limit },
      })),

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

// ──────────────────────────────────────────
// SEGUIMIENTO DE FICHAS
// ──────────────────────────────────────────
export const apiSeguimiento = {
  obtenerConfig: () => apiClient.get<SeguimientoConfig | null>("/api/seguimiento/config"),

  guardarConfig: (data: { url_panel: string; correo_google?: string; url_hoja?: string }) =>
    apiClient.put<SeguimientoConfig>("/api/seguimiento/config", data),

  eliminarConfig: () => apiClient.delete<{ message: string }>("/api/seguimiento/config"),
};

// ──────────────────────────────────────────
// SISTEMA
// ──────────────────────────────────────────
export const apiSistema = {
  /** Estado y versión del servidor (no necesita sesión). */
  salud: () => apiClient.get<{ status: string; version: string }>("/health", { timeout: 15000 }),
};

export default apiClient;
