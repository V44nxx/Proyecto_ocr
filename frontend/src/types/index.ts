/**
 * Tipos globales del Sistema OCR
 */

export interface Usuario {
  id: string;
  email: string;
  nombre: string;
  rol: "admin" | "usuario";
  activo: boolean;
  fecha_creacion: string;
  /** Verificación en dos pasos vinculada (obligatoria para los administradores) */
  doble_factor_activo?: boolean;
}

/** Ficha ya subida con el mismo número que un archivo que se va a subir */
export interface FichaExistenteInfo {
  nombre: string;
  numero_ficha: string | null;
  existente: { id: string; nombre_original: string; fecha_carga: string | null; total_personas: number } | null;
}

/** Qué hacer con un PDF de una ficha que ya existe */
export interface AccionFicha {
  archivo: string;
  accion: "reemplazar" | "agregar";
  documento_id: string;
}

export interface SeguimientoConfig {
  url_panel: string;
  correo_google: string | null;
  url_hoja: string | null;
  fecha_actualizacion: string | null;
}

export interface RegistroAuditoria {
  fecha: string;
  email: string | null;
  accion: string;
  ip: string | null;
  detalle: Record<string, unknown> | null;
}

export interface RegistrosAuditoria {
  total: number;
  registros: RegistroAuditoria[];
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  usuario: Usuario;
}

/**
 * Respuesta del inicio de sesión: la sesión, o (administradores) el paso siguiente con su desafío.
 * `codigos_respaldo` llega solo al activar la verificación; `codigos_respaldo_restantes`, al entrar con uno.
 */
export interface LoginResponse {
  access_token?: string | null;
  token_type: string;
  usuario?: Usuario | null;
  requiere_2fa: boolean;
  configurar_2fa: boolean;
  desafio?: string | null;
  codigos_respaldo?: string[] | null;
  codigos_respaldo_restantes?: number | null;
}

/** Datos para vincular la app de autenticación: QR (imagen data:) y la clave para escribirla a mano */
export interface ConfigurarDobleFactor {
  secreto: string;
  uri: string;
  qr: string;
}

export interface Documento {
  id: string;
  nombre_original: string;
  estado: "pendiente" | "procesando" | "completado" | "error" | "revision";
  total_paginas: number;
  total_personas?: number;
  confianza_ocr: number | null;
  mensaje_error: string | null;
  tiempo_procesamiento_ms: number | null;
  fecha_carga: string;
  fecha_procesamiento: string | null;
  metadatos?: Record<string, any>;
}

export interface DocumentoEstadoResponse {
  id: string;
  nombre_original?: string;
  estado: "pendiente" | "procesando" | "completado" | "error" | "revision";
  progreso: number;
  paso: string;
  total_paginas: number;
  pagina_actual: number;
  personas_count: number;
  confianza_ocr: number | null;
  tiempo_procesamiento_ms: number | null;
  mensaje_error: string | null;
  fecha_procesamiento: string | null;
  metadatos?: Record<string, any>;
}


export interface Persona {
  id: string;
  documento_id: string | null;
  documento_pdf_id?: string | null;
  nombre_documento?: string | null;
  nombre_documento_pdf?: string | null;
  grupo_documento_id?: string | null;
  pagina_frente?: number | null;
  pagina_reverso?: number | null;
  pagina_numero?: number | null;
  tipo_documento?: string | null;
  estado_registro?: string | null;
  motor_ocr?: string | null;
  numero_identificacion: string;
  nombre_completo: string | null;
  nombres?: string | null;
  apellidos?: string | null;
  fecha_nacimiento: string | null;
  edad?: number | null;
  fecha_expedicion: string | null;
  lugar_expedicion: string | null;
  sexo: string | null;
  confianza_extraccion: number | null;
  requiere_revision: boolean;
  detalles_campos?: Record<string, any> | null;
  fecha_registro: string;
  fecha_actualizacion?: string;
  /** True si la persona aparece en alguna planilla Excel comparada */
  en_excel?: boolean | null;
  /** True si la persona tiene documento PDF asociado */
  en_pdf?: boolean | null;
  /** Objeto de discrepancia estructurada si hay conflicto entre el documento físico y Excel */
  discrepancia_excel?: Record<string, any> | null;
}

export interface PersonaUpdate {
  numero_identificacion?: string;
  tipo_documento?: string;
  nombre_completo?: string;
  nombres?: string;
  apellidos?: string;
  fecha_nacimiento?: string;
  fecha_expedicion?: string;
  lugar_expedicion?: string;
  sexo?: string;
  requiere_revision?: boolean;
  estado_registro?: string;
}

export interface Comparacion {
  id: string;
  nombre_original: string;
  estado: "pendiente" | "procesando" | "completado" | "error";
  total_registros_bd: number;
  total_registros_excel: number;
  total_coincidentes: number;
  total_diferentes: number;
  total_faltantes_bd: number;
  total_nuevos_bd: number;
  fecha_carga: string;
  fecha_ejecucion: string | null;
  tiempo_procesamiento_ms: number | null;
  mensaje_error?: string | null;
}

export interface Diferencia {
  id: string;
  numero_identificacion: string;
  campo: string | null;
  valor_bd: string | null;
  valor_excel: string | null;
  tipo_diferencia: "igual" | "diferente" | "faltante_bd" | "nuevo_bd";
}

export interface DashboardStats {
  total_documentos: number;
  documentos_completados: number;
  documentos_procesando: number;
  documentos_con_error: number;
  total_personas: number;
  personas_en_revision: number;
  total_comparaciones: number;
}

export interface PaginatedResponse<T> {
  items: T[];
  total?: number;
}

export interface ApiError {
  detail: string | { msg: string; type: string }[];
}
