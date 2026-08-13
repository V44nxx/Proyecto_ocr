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
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  usuario: Usuario;
}

export interface Documento {
  id: string;
  nombre_original: string;
  estado: "pendiente" | "procesando" | "completado" | "error" | "revision";
  total_paginas: number;
  confianza_ocr: number | null;
  mensaje_error: string | null;
  tiempo_procesamiento_ms: number | null;
  fecha_carga: string;
  fecha_procesamiento: string | null;
}

export interface Persona {
  id: string;
  documento_id: string | null;
  pagina_numero?: number | null;
  tipo_documento?: string | null;
  estado_registro?: string | null;
  motor_ocr?: string | null;
  numero_identificacion: string;
  nombres: string | null;
  apellidos: string | null;
  fecha_nacimiento: string | null;
  fecha_expedicion: string | null;
  lugar_expedicion: string | null;
  sexo: string | null;
  confianza_extraccion: number | null;
  requiere_revision: boolean;
  detalles_campos?: Record<string, { value: string | null; confidence: number; page: number; status: string; source: string; reason: string | null }> | null;
  fecha_registro: string;
  fecha_actualizacion: string;
}

export interface PersonaUpdate {
  nombres?: string;
  apellidos?: string;
  fecha_nacimiento?: string;
  fecha_expedicion?: string;
  lugar_expedicion?: string;
  sexo?: string;
  requiere_revision?: boolean;
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

export interface ApiError {
  detail: string | { msg: string; type: string }[];
}
