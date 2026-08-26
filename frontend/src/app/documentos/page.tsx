"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { useDropzone, type FileRejection } from "react-dropzone";
import toast from "react-hot-toast";
import {
  Upload, FileText, CheckCircle, AlertTriangle,
  Clock, Trash2, RefreshCw, Eye, Sparkles,
  ArrowRight, Users, CheckCircle2, ChevronRight,
  Layers, Timer, X, AlertCircle, Cpu, FileCheck2
} from "lucide-react";
import Sidebar from "@/components/ui/Sidebar";
import { apiDocumentos, getErrorMessage } from "@/lib/api";
import { auth } from "@/lib/auth";
import { useRouter } from "next/navigation";
import type { Documento, DocumentoEstadoResponse } from "@/types";

const ESTADO_CONFIG: Record<string, { label: string; clase: string; icon: React.ReactNode }> = {
  pendiente: { label: "Pendiente", clase: "badge-neutral", icon: <Clock className="w-3 h-3" /> },
  procesando: { label: "Procesando", clase: "badge-warning", icon: <RefreshCw className="w-3 h-3 animate-spin" /> },
  completado: { label: "Completado", clase: "badge-success", icon: <CheckCircle className="w-3 h-3" /> },
  error: { label: "Error", clase: "badge-danger", icon: <AlertTriangle className="w-3 h-3" /> },
  revision: { label: "En Revisión", clase: "badge-warning", icon: <Eye className="w-3 h-3" /> },
};

interface DocTracking {
  id: string;
  nombre: string;
  estado: "pendiente" | "procesando" | "completado" | "error" | "revision";
  progreso: number;
  paso: string;
  total_paginas: number;
  pagina_actual: number;
  personas_count: number;
  confianza_ocr: number | null;
  tiempo_procesamiento_ms?: number | null;
  mensaje_error?: string | null;
}

export default function DocumentosPage() {
  const router = useRouter();
  const [documentos, setDocumentos] = useState<Documento[]>([]);
  const [subiendo, setSubiendo] = useState(false);
  const [archivosSeleccionados, setArchivosSeleccionados] = useState<File[]>([]);
  const [cargando, setCargando] = useState(true);

  // Estado para el seguimiento de extracción OCR en vivo
  const [docsEnProceso, setDocsEnProceso] = useState<DocTracking[]>([]);
  const [mostrandoProgreso, setMostrandoProgreso] = useState(false);
  const [tiempoTranscurrido, setTiempoTranscurrido] = useState(0);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  const cargarDocumentos = async () => {
    try {
      const res = await apiDocumentos.listar({ limit: 50 });
      if (Array.isArray(res?.data)) {
        setDocumentos(res.data);
      } else if (res?.data && Array.isArray((res.data as any).documentos)) {
        setDocumentos((res.data as any).documentos);
      } else {
        setDocumentos([]);
      }
    } catch (err) {
      console.error("Error al cargar documentos:", err);
    } finally {
      setCargando(false);
    }
  };

  useEffect(() => {
    if (!auth.isAuthenticated()) {
      router.push("/");
      return;
    }
    cargarDocumentos();
    const interval = setInterval(cargarDocumentos, 6000);
    return () => clearInterval(interval);
  }, [router]);

  // Cronómetro durante procesamiento activo
  useEffect(() => {
    const hayActivos = docsEnProceso.some(
      (d) => d.estado === "procesando" || d.estado === "pendiente"
    );

    if (hayActivos) {
      if (!timerRef.current) {
        timerRef.current = setInterval(() => {
          setTiempoTranscurrido((t) => t + 1);
        }, 1000);
      }
    } else {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    }

    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [docsEnProceso]);

  // Polling de estado detallado de extracción OCR
  useEffect(() => {
    const docsPendientes = docsEnProceso.filter(
      (d) => d.estado === "procesando" || d.estado === "pendiente"
    );

    if (docsPendientes.length === 0) return;

    const interval = setInterval(async () => {
      let huboCambios = false;

      const updates = await Promise.all(
        docsEnProceso.map(async (doc) => {
          if (doc.estado === "completado" || doc.estado === "error") {
            return doc;
          }

          try {
            const res = await apiDocumentos.estado(doc.id);
            const data: DocumentoEstadoResponse = res.data;

            huboCambios = true;
            return {
              ...doc,
              nombre: data.nombre_original || doc.nombre,
              estado: data.estado,
              progreso: data.progreso ?? doc.progreso,
              paso: data.paso || doc.paso,
              total_paginas: data.total_paginas ?? doc.total_paginas,
              pagina_actual: data.pagina_actual ?? doc.pagina_actual,
              personas_count: data.personas_count ?? doc.personas_count,
              confianza_ocr: data.confianza_ocr ?? doc.confianza_ocr,
              tiempo_procesamiento_ms: data.tiempo_procesamiento_ms,
              mensaje_error: data.mensaje_error,
            };
          } catch {
            return doc;
          }
        })
      );

      if (huboCambios) {
        setDocsEnProceso(updates);
        // Si alguno terminó, refrescar tabla de fondo
        if (updates.some((u) => u.estado === "completado" || u.estado === "error")) {
          cargarDocumentos();
        }
      }
    }, 1200);

    return () => clearInterval(interval);
  }, [docsEnProceso]);

  const onDrop = useCallback((acceptedFiles: File[]) => {
    if (!acceptedFiles || acceptedFiles.length === 0) return;
    const pdfs = acceptedFiles.filter((f) => {
      const name = (f?.name || "").trim().toLowerCase();
      const type = (f?.type || "").trim().toLowerCase();
      return name.endsWith(".pdf") || type.includes("pdf") || type.includes("octet-stream") || !name.includes(".");
    });
    if (pdfs.length === 0) {
      toast.error("Solo se aceptan archivos en formato PDF (.pdf)");
      return;
    }
    if (pdfs.length !== acceptedFiles.length) {
      toast.error("Se ignoraron los archivos que no tienen extensión .pdf");
    }
    setArchivosSeleccionados((prev) => {
      const existingKeys = new Set(prev.map(p => `${p.name}_${p.size}`));
      const newUnique = pdfs.filter(p => !existingKeys.has(`${p.name}_${p.size}`));
      return [...prev, ...newUnique];
    });
  }, []);

  const onDropRejected = useCallback((fileRejections: FileRejection[]) => {
    if (fileRejections && fileRejections.length > 0) {
      const nombres = fileRejections.map(r => r.file?.name || "archivo").join(", ");
      toast.error(`No se pudo seleccionar: ${nombres}. Asegúrate de que sea un archivo PDF.`);
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    onDropRejected,
    accept: {
      "application/pdf": [".pdf"],
    },
    multiple: true,
    noClick: false,
    noKeyboard: false,
  });

  const subirArchivos = async () => {
    if (archivosSeleccionados.length === 0) {
      toast.error("Selecciona al menos un PDF");
      return;
    }

    setSubiendo(true);
    setTiempoTranscurrido(0);

    try {
      const res = await apiDocumentos.upload(archivosSeleccionados);
      const docsResp = res.data?.documentos || [];

      const initialTracking: DocTracking[] = (docsResp.length > 0
        ? docsResp
        : archivosSeleccionados.map((f, i) => ({
            id: `temp-${i}`,
            nombre_original: f.name,
            estado: "procesando",
          }))
      ).map((d: any) => ({
        id: d.id,
        nombre: d.nombre_original || d.nombre || "Documento PDF",
        estado: (d.estado as any) || "procesando",
        progreso: 8,
        paso: "Iniciando lectura y OCR con Google Document AI...",
        total_paginas: 0,
        pagina_actual: 0,
        personas_count: 0,
        confianza_ocr: null,
      }));

      setDocsEnProceso(initialTracking);
      setMostrandoProgreso(true);
      setArchivosSeleccionados([]);
      cargarDocumentos();

      toast.success("Documento(s) encolado(s) para extracción OCR");
    } catch (err: unknown) {
      toast.error(getErrorMessage(err, "Error subiendo archivos"));
    } finally {
      setSubiendo(false);
    }
  };

  const eliminarDocumento = async (id: string, nombre: string) => {
    if (!confirm(`¿Eliminar "${nombre}"?`)) return;
    try {
      await apiDocumentos.eliminar(id);
      toast.success("Documento eliminado");
      cargarDocumentos();
    } catch (err: unknown) {
      toast.error(getErrorMessage(err, "Error eliminando documento"));
    }
  };

  const formatSize = (bytes: number | null | undefined) => {
    if (!bytes || isNaN(bytes)) return "-";
    return bytes > 1024 * 1024
      ? `${(bytes / 1024 / 1024).toFixed(1)} MB`
      : `${(bytes / 1024).toFixed(0)} KB`;
  };

  const formatDate = (dateStr: string | null | undefined) => {
    if (!dateStr) return "-";
    try {
      const d = new Date(dateStr);
      return isNaN(d.getTime()) ? "-" : d.toLocaleString("es-CO");
    } catch {
      return "-";
    }
  };

  const formatTimer = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}s`;
  };

  const getConfianzaDisplay = (conf: number | null | undefined) => {
    if (conf == null || isNaN(Number(conf))) return null;
    const num = Number(conf);
    const pct = num > 1 ? num : num * 100;
    return Math.min(100, Math.max(0, Math.round(pct)));
  };

  // Métricas calculadas para la barra de progreso global
  const totalDocsTracking = docsEnProceso.length;
  const docsCompletadosCount = docsEnProceso.filter((d) => d.estado === "completado").length;
  const docsErrorCount = docsEnProceso.filter((d) => d.estado === "error").length;
  const totalPersonasDetectadas = docsEnProceso.reduce((acc, d) => acc + (d.personas_count || 0), 0);
  const totalPaginasProcesadas = docsEnProceso.reduce((acc, d) => acc + (d.total_paginas || 0), 0);

  const progresoGlobal = totalDocsTracking > 0
    ? Math.round(docsEnProceso.reduce((acc, d) => acc + (d.progreso || 0), 0) / totalDocsTracking)
    : 0;

  const procesoFinalizado = totalDocsTracking > 0 &&
    docsEnProceso.every((d) => d.estado === "completado" || d.estado === "error");

  return (
    <div className="flex min-h-screen bg-dark-950 text-slate-100">
      <Sidebar />
      <main className="ml-64 flex-1 p-8 max-w-7xl">
        {/* Encabezado */}
        <div className="mb-8 page-enter">
          <div className="flex items-center gap-2 mb-1">
            <FileText className="w-5 h-5 text-primary-400" />
            <span className="text-primary-400 text-sm font-medium">Procesamiento de Documentos</span>
          </div>
          <h1 className="text-3xl font-bold text-white tracking-tight">Documentos PDF</h1>
          <p className="text-slate-400 mt-1">
            Sube documentos de identidad para extracción automática y precisa con OCR
          </p>
        </div>

        {/* ─────────────────────────────────────────────────────────────
            MODAL / TARJETA DE PROGRESO DE EXTRACCIÓN OCR EN VIVO
           ───────────────────────────────────────────────────────────── */}
        {mostrandoProgreso && docsEnProceso.length > 0 && (
          <div className="mb-8 p-6 sm:p-7 rounded-2xl bg-dark-900/95 border border-primary-500/30 shadow-2xl shadow-primary-950/40 relative overflow-hidden backdrop-blur-xl animate-in fade-in zoom-in-95 duration-300">
            {/* Resplandor ambiental de fondo */}
            <div className="absolute -right-20 -top-20 w-72 h-72 bg-primary-500/10 rounded-full blur-3xl pointer-events-none" />
            <div className="absolute -left-20 -bottom-20 w-72 h-72 bg-blue-600/10 rounded-full blur-3xl pointer-events-none" />

            {/* Cabecera del Progreso */}
            <div className="flex items-start justify-between gap-4 pb-4 border-b border-white/[0.08] relative z-10">
              <div className="flex items-center gap-3">
                <div className={`w-11 h-11 rounded-xl flex items-center justify-center ${
                  procesoFinalizado
                    ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                    : "bg-primary-500/20 text-primary-400 border border-primary-500/30 animate-pulse"
                }`}>
                  {procesoFinalizado ? (
                    <CheckCircle2 className="w-6 h-6" />
                  ) : (
                    <Cpu className="w-6 h-6" />
                  )}
                </div>
                <div>
                  <div className="flex items-center gap-2.5">
                    <h3 className="text-lg font-bold text-white">
                      {procesoFinalizado
                        ? "¡Extracción de Datos Completada!"
                        : "Extrayendo Datos del Documento PDF..."}
                    </h3>
                    <span className={`badge ${procesoFinalizado ? "badge-success" : "badge-warning"} text-xs px-2.5 py-0.5`}>
                      {procesoFinalizado ? "Finalizado" : "En progreso"}
                    </span>
                  </div>
                  <p className="text-sm text-slate-400 mt-0.5">
                    {procesoFinalizado
                      ? "La información ha sido estructurada y guardada en el sistema."
                      : "Google Document AI y el motor OCR están leyendo los datos de identidad."}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-3">
                <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-dark-800/80 border border-white/[0.08] text-xs font-mono text-slate-300">
                  <Timer className="w-3.5 h-3.5 text-primary-400" />
                  <span>Tiempo: {formatTimer(tiempoTranscurrido)}</span>
                </div>
                <button
                  onClick={() => setMostrandoProgreso(false)}
                  className="text-slate-400 hover:text-white p-1.5 rounded-lg hover:bg-dark-800 transition-colors"
                  title="Minimizar panel de progreso"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>

            {/* Barra de Progreso Principal */}
            <div className="mt-6 space-y-2 relative z-10">
              <div className="flex items-center justify-between text-sm">
                <span className="font-semibold text-slate-200 flex items-center gap-2">
                  <span>Progreso de Extracción</span>
                  <span className="text-xs text-primary-400 font-mono">({progresoGlobal}%)</span>
                </span>
                <span className="text-xs text-slate-400">
                  {docsCompletadosCount} de {totalDocsTracking} documento(s) procesados
                </span>
              </div>

              <div className="w-full h-3 bg-dark-800 rounded-full overflow-hidden p-0.5 border border-white/[0.08] relative">
                <div
                  className={`h-full rounded-full transition-all duration-500 ease-out relative ${
                    procesoFinalizado
                      ? "bg-gradient-to-r from-emerald-500 to-teal-400 shadow-lg shadow-emerald-500/30"
                      : "bg-gradient-to-r from-primary-600 via-blue-500 to-primary-400 shadow-lg shadow-primary-500/30"
                  }`}
                  style={{ width: `${Math.min(100, Math.max(5, progresoGlobal))}%` }}
                >
                  {!procesoFinalizado && (
                    <div className="absolute inset-0 bg-white/20 animate-[shimmer_2s_infinite] bg-[linear-gradient(90deg,transparent,rgba(255,255,255,0.4),transparent)]" />
                  )}
                </div>
              </div>
            </div>

            {/* Línea de Etapas del Proceso */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-6 pt-2 relative z-10">
              <div className={`p-3 rounded-xl border transition-all ${
                progresoGlobal >= 10
                  ? "bg-primary-500/10 border-primary-500/30 text-primary-300"
                  : "bg-dark-800/40 border-white/[0.04] text-slate-500"
              }`}>
                <div className="flex items-center gap-2 font-medium text-xs mb-1">
                  <span className="w-4 h-4 rounded-full bg-primary-500/20 text-primary-400 flex items-center justify-center text-[10px] font-bold">1</span>
                  Lectura de PDF
                </div>
                <p className="text-[11px] text-slate-400">Carga y conteo de páginas</p>
              </div>

              <div className={`p-3 rounded-xl border transition-all ${
                progresoGlobal >= 40
                  ? "bg-primary-500/10 border-primary-500/30 text-primary-300"
                  : "bg-dark-800/40 border-white/[0.04] text-slate-500"
              }`}>
                <div className="flex items-center gap-2 font-medium text-xs mb-1">
                  <span className="w-4 h-4 rounded-full bg-primary-500/20 text-primary-400 flex items-center justify-center text-[10px] font-bold">2</span>
                  Reconocimiento OCR
                </div>
                <p className="text-[11px] text-slate-400">Google Document AI</p>
              </div>

              <div className={`p-3 rounded-xl border transition-all ${
                progresoGlobal >= 75
                  ? "bg-primary-500/10 border-primary-500/30 text-primary-300"
                  : "bg-dark-800/40 border-white/[0.04] text-slate-500"
              }`}>
                <div className="flex items-center gap-2 font-medium text-xs mb-1">
                  <span className="w-4 h-4 rounded-full bg-primary-500/20 text-primary-400 flex items-center justify-center text-[10px] font-bold">3</span>
                  Emparejamiento
                </div>
                <p className="text-[11px] text-slate-400">Frente y Reverso de cédula</p>
              </div>

              <div className={`p-3 rounded-xl border transition-all ${
                progresoGlobal >= 100
                  ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-300"
                  : progresoGlobal >= 85
                  ? "bg-primary-500/10 border-primary-500/30 text-primary-300"
                  : "bg-dark-800/40 border-white/[0.04] text-slate-500"
              }`}>
                <div className="flex items-center gap-2 font-medium text-xs mb-1">
                  <span className={`w-4 h-4 rounded-full ${progresoGlobal >= 100 ? "bg-emerald-500/20 text-emerald-400" : "bg-primary-500/20 text-primary-400"} flex items-center justify-center text-[10px] font-bold`}>4</span>
                  Extracción Personas
                </div>
                <p className="text-[11px] text-slate-400">Estructuración y guardado</p>
              </div>
            </div>

            {/* Detalle por Documento Individual */}
            <div className="mt-5 space-y-2.5 relative z-10">
              {docsEnProceso.map((doc) => (
                <div
                  key={doc.id}
                  className="p-3.5 bg-dark-800/70 border border-white/[0.06] rounded-xl flex flex-col sm:flex-row sm:items-center justify-between gap-3"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <FileText className="w-5 h-5 text-primary-400 flex-shrink-0" />
                    <div className="min-w-0">
                      <p className="text-sm font-semibold text-white truncate max-w-sm sm:max-w-md">
                        {doc.nombre}
                      </p>
                      <p className="text-xs text-slate-400 flex items-center gap-1.5 mt-0.5">
                        {doc.estado === "procesando" && (
                          <RefreshCw className="w-3 h-3 text-yellow-400 animate-spin flex-shrink-0" />
                        )}
                        {doc.estado === "completado" && (
                          <CheckCircle2 className="w-3 h-3 text-emerald-400 flex-shrink-0" />
                        )}
                        {doc.estado === "error" && (
                          <AlertCircle className="w-3 h-3 text-red-400 flex-shrink-0" />
                        )}
                        <span>{doc.paso}</span>
                        {doc.total_paginas > 0 && (
                          <span className="text-slate-500">
                            • {doc.pagina_actual > 0 ? `Pág. ${doc.pagina_actual}/${doc.total_paginas}` : `${doc.total_paginas} págs`}
                          </span>
                        )}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-3 self-end sm:self-center flex-shrink-0">
                    {doc.personas_count > 0 && (
                      <span className="badge badge-info text-xs flex items-center gap-1">
                        <Users className="w-3 h-3" />
                        {doc.personas_count} persona(s)
                      </span>
                    )}
                    {doc.confianza_ocr !== null && (
                      <span className="badge badge-success text-xs font-mono">
                        {getConfianzaDisplay(doc.confianza_ocr)}% conf.
                      </span>
                    )}
                    <span className="text-xs font-mono font-bold text-primary-400 w-10 text-right">
                      {doc.progreso}%
                    </span>
                  </div>
                </div>
              ))}
            </div>

            {/* Resumen Final y Botones de Acción */}
            {procesoFinalizado && (
              <div className="mt-6 pt-5 border-t border-white/[0.08] flex flex-col md:flex-row items-center justify-between gap-4 relative z-10 animate-in fade-in duration-300">
                <div className="flex flex-wrap items-center gap-4 text-xs text-slate-300">
                  <div className="flex items-center gap-1.5">
                    <Users className="w-4 h-4 text-emerald-400" />
                    <span>Total personas extraídas: <strong className="text-white text-sm">{totalPersonasDetectadas}</strong></span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <Layers className="w-4 h-4 text-primary-400" />
                    <span>Páginas procesadas: <strong className="text-white text-sm">{totalPaginasProcesadas}</strong></span>
                  </div>
                  {docsErrorCount > 0 && (
                    <div className="flex items-center gap-1.5 text-red-400">
                      <AlertTriangle className="w-4 h-4" />
                      <span>{docsErrorCount} con error</span>
                    </div>
                  )}
                </div>

                <div className="flex items-center gap-3 w-full md:w-auto">
                  <button
                    onClick={() => {
                      setMostrandoProgreso(false);
                      cargarDocumentos();
                    }}
                    className="btn-secondary text-sm py-2.5 px-4 flex-1 md:flex-initial"
                  >
                    Ver Historial de Documentos
                  </button>
                  <button
                    onClick={() => router.push("/personas")}
                    className="btn-primary text-sm py-2.5 px-5 flex-1 md:flex-initial flex items-center justify-center gap-2 shadow-lg shadow-primary-500/25"
                  >
                    <Users className="w-4 h-4" />
                    <span>Ver Personas Extraídas</span>
                    <ArrowRight className="w-4 h-4" />
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ─────────────────────────────────────────────────────────────
            ZONA DE CARGA DE DOCUMENTOS
           ───────────────────────────────────────────────────────────── */}
        <div className="card mb-8 page-enter">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-white flex items-center gap-2">
              <Upload className="w-4 h-4 text-primary-400" />
              Cargar Documentos PDF
            </h2>
            <span className="text-xs text-slate-400">Formato admitido: PDF (Cédulas colombianas)</span>
          </div>

          <div
            {...getRootProps()}
            className={`dropzone ${isDragActive ? "active" : ""}`}
          >
            <input {...getInputProps()} />
            <div className="w-16 h-16 rounded-2xl bg-primary-500/10 border border-primary-500/20 flex items-center justify-center transition-transform group-hover:scale-105">
              <Upload className="w-8 h-8 text-primary-400" />
            </div>
            <div>
              <p className="text-white font-semibold text-base">
                {isDragActive ? "Suelta los archivos aquí" : "Arrastra PDFs o haz clic para seleccionar"}
              </p>
              <p className="text-slate-500 text-sm mt-1">
                PDF · Hasta 50MB por archivo · Soporta documentos de múltiples páginas y frentes/reversos
              </p>
            </div>
          </div>

          {/* ─────────────────────────────────────────────────────────────
              SECCIÓN DE ARCHIVOS SELECCIONADOS Y BOTÓN DE INICIO REDISEÑADO
             ───────────────────────────────────────────────────────────── */}
          {archivosSeleccionados.length > 0 && (
            <div className="mt-6 pt-5 border-t border-white/[0.08]">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <FileCheck2 className="w-4 h-4 text-primary-400" />
                  <h3 className="text-sm font-semibold text-slate-200">
                    Archivos listos para procesar
                  </h3>
                  <span className="badge badge-info text-xs">
                    {archivosSeleccionados.length} PDF(s)
                  </span>
                </div>
                <button
                  onClick={() => setArchivosSeleccionados([])}
                  disabled={subiendo}
                  className="text-xs text-slate-400 hover:text-red-400 transition-colors flex items-center gap-1"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                  Quitar todos
                </button>
              </div>

              {/* Lista de archivos seleccionados */}
              <div className="space-y-2 max-h-56 overflow-y-auto pr-1">
                {archivosSeleccionados.map((f, i) => (
                  <div
                    key={i}
                    className="flex items-center justify-between p-3.5 bg-dark-800/80 hover:bg-dark-800 rounded-xl border border-white/[0.06] transition-all"
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <div className="w-8 h-8 rounded-lg bg-primary-500/10 border border-primary-500/20 flex items-center justify-center flex-shrink-0">
                        <FileText className="w-4 h-4 text-primary-400" />
                      </div>
                      <div className="min-w-0">
                        <span className="text-sm font-medium text-slate-200 truncate block">
                          {f.name}
                        </span>
                        <span className="text-xs text-slate-500 font-mono">
                          {formatSize(f.size)}
                        </span>
                      </div>
                    </div>
                    <button
                      onClick={() =>
                        setArchivosSeleccionados((prev) => prev.filter((_, j) => j !== i))
                      }
                      disabled={subiendo}
                      className="text-slate-500 hover:text-red-400 transition-colors p-1.5 rounded-lg hover:bg-dark-700 flex-shrink-0"
                      title="Eliminar archivo"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                ))}
              </div>

              {/* Barra de Acciones del Botón OCR (Espaciado amplio y diseño premium) */}
              <div className="mt-6 pt-5 border-t border-white/[0.08] flex flex-col sm:flex-row items-center justify-between gap-4">
                <div className="text-xs text-slate-400 flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-primary-400 flex-shrink-0" />
                  <span>
                    La extracción procesará automáticamente caras de cédula y estructurará los registros.
                  </span>
                </div>

                <button
                  onClick={subirArchivos}
                  disabled={subiendo}
                  className="btn-primary w-full sm:w-auto py-3.5 px-8 text-base font-semibold rounded-xl flex items-center justify-center gap-3 shadow-lg shadow-primary-500/25 hover:shadow-primary-500/40 transition-all transform hover:-translate-y-0.5"
                >
                  {subiendo ? (
                    <>
                      <div className="spinner" />
                      <span>Iniciando OCR...</span>
                    </>
                  ) : (
                    <>
                      <Sparkles className="w-5 h-5 text-blue-200" />
                      <span>Iniciar Procesamiento OCR</span>
                      <ChevronRight className="w-4 h-4 opacity-70" />
                    </>
                  )}
                </button>
              </div>
            </div>
          )}
        </div>

        {/* ─────────────────────────────────────────────────────────────
            HISTORIAL DE DOCUMENTOS (TABLA)
           ───────────────────────────────────────────────────────────── */}
        <div className="card page-enter">
          <div className="flex items-center justify-between mb-5">
            <div>
              <h2 className="text-lg font-semibold text-white">Historial de Documentos</h2>
              <p className="text-xs text-slate-400 mt-0.5">Listado de PDFs cargados y procesados previamente</p>
            </div>
            <button
              onClick={cargarDocumentos}
              disabled={cargando}
              className="btn-secondary text-sm py-2 px-4 flex items-center gap-2"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${cargando ? "animate-spin" : ""}`} />
              <span>Actualizar</span>
            </button>
          </div>

          {cargando ? (
            <div className="space-y-3">
              {Array(5).fill(0).map((_, i) => (
                <div key={i} className="skeleton h-14 rounded-xl" />
              ))}
            </div>
          ) : !documentos || documentos.length === 0 ? (
            <div className="text-center py-16">
              <FileText className="w-12 h-12 text-slate-600 mx-auto mb-3" />
              <p className="text-slate-400 font-medium">No hay documentos cargados aún</p>
              <p className="text-slate-600 text-sm mt-1">Sube un PDF para comenzar la extracción OCR</p>
            </div>
          ) : (
            <div className="table-container">
              <table className="table-base">
                <thead>
                  <tr>
                    <th>Documento</th>
                    <th>Estado</th>
                    <th>Páginas</th>
                    <th>Confianza OCR</th>
                    <th>Tiempo</th>
                    <th>Fecha Carga</th>
                    <th className="text-right">Acciones</th>
                  </tr>
                </thead>
                <tbody>
                  {documentos.map((doc) => {
                    const estadoKey = String(doc.estado || "pendiente").toLowerCase();
                    const cfg = ESTADO_CONFIG[estadoKey] || ESTADO_CONFIG.pendiente;
                    const confPct = getConfianzaDisplay(doc.confianza_ocr);

                    return (
                      <tr key={doc.id}>
                        <td>
                          <div className="flex items-center gap-2.5">
                            <div className="w-7 h-7 rounded-lg bg-primary-500/10 flex items-center justify-center flex-shrink-0">
                              <FileText className="w-4 h-4 text-primary-400" />
                            </div>
                            <span className="font-medium text-white truncate max-w-[220px]">
                              {doc.nombre_original}
                            </span>
                          </div>
                        </td>
                        <td>
                          <div className="flex flex-col gap-1">
                            <span className={`badge ${cfg.clase} flex items-center gap-1 w-fit`}>
                              {cfg.icon}
                              {cfg.label}
                            </span>
                            {doc.mensaje_error && (
                              <p className="text-[11px] text-red-400 bg-red-500/10 p-1.5 rounded border border-red-500/20 max-w-xs font-mono whitespace-pre-wrap">
                                ⚠️ {doc.mensaje_error}
                              </p>
                            )}
                          </div>
                        </td>
                        <td>
                          <span className="font-mono text-slate-300">
                            {doc.total_paginas || "-"}
                          </span>
                        </td>
                        <td>
                          {confPct !== null ? (
                            <div className="flex items-center gap-2">
                              <div className="progress-bar w-16">
                                <div
                                  className="progress-fill"
                                  style={{ width: `${confPct}%` }}
                                />
                              </div>
                              <span className="text-xs font-mono text-slate-300">{confPct}%</span>
                            </div>
                          ) : (
                            <span className="text-slate-500 text-xs">-</span>
                          )}
                        </td>
                        <td className="font-mono text-xs text-slate-400">
                          {doc.tiempo_procesamiento_ms
                            ? `${(doc.tiempo_procesamiento_ms / 1000).toFixed(1)}s`
                            : "-"}
                        </td>
                        <td className="text-slate-400 text-xs">
                          {formatDate(doc.fecha_carga)}
                        </td>
                        <td className="text-right">
                          <button
                            onClick={() => eliminarDocumento(doc.id, doc.nombre_original)}
                            className="text-slate-500 hover:text-red-400 transition-colors p-2 rounded-lg hover:bg-dark-800"
                            title="Eliminar documento"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
