"use client";

import { useState, useCallback, useEffect } from "react";
import { useDropzone, type FileRejection } from "react-dropzone";
import toast from "react-hot-toast";
import {
  Upload, FileText, CheckCircle, AlertTriangle,
  Clock, Trash2, RefreshCw, Eye,
} from "lucide-react";
import Sidebar from "@/components/ui/Sidebar";
import { apiDocumentos, getErrorMessage } from "@/lib/api";
import { auth } from "@/lib/auth";
import { useRouter } from "next/navigation";
import type { Documento } from "@/types";

const ESTADO_CONFIG: Record<string, { label: string; clase: string; icon: React.ReactNode }> = {
  pendiente: { label: "Pendiente", clase: "badge-neutral", icon: <Clock className="w-3 h-3" /> },
  procesando: { label: "Procesando", clase: "badge-warning", icon: <RefreshCw className="w-3 h-3 animate-spin" /> },
  completado: { label: "Completado", clase: "badge-success", icon: <CheckCircle className="w-3 h-3" /> },
  error: { label: "Error", clase: "badge-danger", icon: <AlertTriangle className="w-3 h-3" /> },
  revision: { label: "En Revisión", clase: "badge-warning", icon: <Eye className="w-3 h-3" /> },
};

export default function DocumentosPage() {
  const router = useRouter();
  const [documentos, setDocumentos] = useState<Documento[]>([]);
  const [subiendo, setSubiendo] = useState(false);
  const [archivosSeleccionados, setArchivosSeleccionados] = useState<File[]>([]);
  const [cargando, setCargando] = useState(true);

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
    const interval = setInterval(cargarDocumentos, 5000);
    return () => clearInterval(interval);
  }, [router]);

  const onDrop = useCallback((acceptedFiles: File[]) => {
    const pdfs = acceptedFiles.filter((f) => {
      const ext = f.name?.toLowerCase() || "";
      const type = f.type?.toLowerCase() || "";
      return ext.endsWith(".pdf") || type.includes("pdf") || type === "";
    });
    if (pdfs.length !== acceptedFiles.length) {
      toast.error("Solo se aceptan archivos PDF");
    }
    if (pdfs.length > 0) {
      setArchivosSeleccionados((prev) => [...prev, ...pdfs]);
    }
  }, []);

  const onDropRejected = useCallback((fileRejections: FileRejection[]) => {
    if (fileRejections && fileRejections.length > 0) {
      const nombres = fileRejections.map(r => r.file?.name || "archivo").join(", ");
      toast.error(`Archivo(s) rechazado(s): ${nombres}. Solo se aceptan PDF.`);
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    onDropRejected,
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
    try {
      await apiDocumentos.upload(archivosSeleccionados);
      toast.success("PDF(s) subidos con éxito. Procesando con Google Document AI...");
      setArchivosSeleccionados([]);
      cargarDocumentos();
      setTimeout(() => {
        router.push("/personas");
      }, 1500);
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

  const getConfianzaDisplay = (conf: number | null | undefined) => {
    if (conf == null || isNaN(Number(conf))) return null;
    const num = Number(conf);
    const pct = num > 1 ? num : num * 100;
    return Math.min(100, Math.max(0, Math.round(pct)));
  };

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="ml-64 flex-1 p-8">
        <div className="mb-8 page-enter">
          <div className="flex items-center gap-2 mb-1">
            <FileText className="w-5 h-5 text-primary-400" />
            <span className="text-primary-400 text-sm font-medium">Procesamiento</span>
          </div>
          <h1 className="text-3xl font-bold text-white">Documentos PDF</h1>
          <p className="text-slate-400 mt-1">Sube documentos para extracción automática con OCR</p>
        </div>

        {/* Zona de carga */}
        <div className="card mb-6 page-enter">
          <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <Upload className="w-4 h-4 text-primary-400" />
            Cargar Documentos
          </h2>

          <div
            {...getRootProps()}
            className={`dropzone ${isDragActive ? "active" : ""}`}
          >
            <input {...getInputProps()} />
            <div className="w-16 h-16 rounded-2xl bg-primary-500/10 border border-primary-500/20 flex items-center justify-center">
              <Upload className="w-8 h-8 text-primary-400" />
            </div>
            <div>
              <p className="text-white font-semibold">
                {isDragActive ? "Suelta los archivos aquí" : "Arrastra PDFs o haz clic para seleccionar"}
              </p>
              <p className="text-slate-500 text-sm mt-1">
                PDF · Máximo 50MB por archivo · Múltiples archivos permitidos
              </p>
            </div>
          </div>

          {/* Archivos seleccionados */}
          {archivosSeleccionados.length > 0 && (
            <div className="mt-4 space-y-2">
              <p className="text-sm text-slate-400">{archivosSeleccionados.length} archivo(s) listo(s):</p>
              {archivosSeleccionados.map((f, i) => (
                <div key={i} className="flex items-center justify-between p-3 bg-dark-800 rounded-xl border border-white/[0.06]">
                  <div className="flex items-center gap-2">
                    <FileText className="w-4 h-4 text-primary-400" />
                    <span className="text-sm text-slate-300">{f.name}</span>
                    <span className="text-xs text-slate-500">{formatSize(f.size)}</span>
                  </div>
                  <button
                    onClick={() => setArchivosSeleccionados((prev) => prev.filter((_, j) => j !== i))}
                    className="text-slate-500 hover:text-red-400 transition-colors"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              ))}
              <button
                onClick={subirArchivos}
                disabled={subiendo}
                className="btn-primary mt-3"
              >
                {subiendo ? <><div className="spinner" />Procesando OCR...</> : <><Upload className="w-4 h-4" />Iniciar Procesamiento OCR</>}
              </button>
            </div>
          )}
        </div>

        {/* Tabla de documentos */}
        <div className="card page-enter">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-white">Historial de Documentos</h2>
            <button onClick={cargarDocumentos} className="btn-secondary text-sm py-2 px-4">
              <RefreshCw className="w-3 h-3" />
              Actualizar
            </button>
          </div>

          {cargando ? (
            <div className="space-y-3">
              {Array(5).fill(0).map((_, i) => (
                <div key={i} className="skeleton h-12 rounded-xl" />
              ))}
            </div>
          ) : !documentos || documentos.length === 0 ? (
            <div className="text-center py-16">
              <FileText className="w-12 h-12 text-slate-600 mx-auto mb-3" />
              <p className="text-slate-400">No hay documentos cargados aún</p>
              <p className="text-slate-600 text-sm mt-1">Sube un PDF para comenzar</p>
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
                    <th>Fecha</th>
                    <th>Acciones</th>
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
                          <div className="flex items-center gap-2">
                            <FileText className="w-4 h-4 text-primary-400 flex-shrink-0" />
                            <span className="font-medium text-white truncate max-w-[200px]">
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
                        <td>{doc.total_paginas || "-"}</td>
                        <td>
                          {confPct !== null ? (
                            <div className="flex items-center gap-2">
                              <div className="progress-bar w-16">
                                <div
                                  className="progress-fill"
                                  style={{ width: `${confPct}%` }}
                                />
                              </div>
                              <span className="text-xs text-slate-400">{confPct}%</span>
                            </div>
                          ) : "-"}
                        </td>
                        <td>
                          {doc.tiempo_procesamiento_ms
                            ? `${(doc.tiempo_procesamiento_ms / 1000).toFixed(1)}s`
                            : "-"}
                        </td>
                        <td className="text-slate-400 text-xs">
                          {formatDate(doc.fecha_carga)}
                        </td>
                        <td>
                          <button
                            onClick={() => eliminarDocumento(doc.id, doc.nombre_original)}
                            className="text-slate-500 hover:text-red-400 transition-colors p-1"
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
