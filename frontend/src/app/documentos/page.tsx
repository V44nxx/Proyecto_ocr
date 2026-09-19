"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { useDropzone, type FileRejection } from "react-dropzone";
import toast from "react-hot-toast";
import axios from "axios";
import {
  Upload, FileText, CheckCircle, AlertTriangle,
  Clock, Trash2, RefreshCw, Eye, Sparkles,
  ArrowRight, Users, CheckCircle2, ChevronRight,
  Layers, Timer, X, AlertCircle, Cpu, FileCheck2,
  Hourglass, ArrowUpCircle, Check, FileSpreadsheet,
  BarChart2, PlusCircle, XCircle
} from "lucide-react";
import Sidebar from "@/components/ui/Sidebar";
import { useSidebar } from "@/context/SidebarContext";
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
  const { collapsed } = useSidebar();
  const [documentos, setDocumentos] = useState<Documento[]>([]);
  const [subiendo, setSubiendo] = useState(false);
  const [archivosSeleccionados, setArchivosSeleccionados] = useState<File[]>([]);
  const [excelSeleccionado, setExcelSeleccionado] = useState<File | null>(null);
  const [comparacionId, setComparacionId] = useState<string | null>(null);
  const [comparacionEnProgreso, setComparacionEnProgreso] = useState(false);
  const [cargando, setCargando] = useState(true);

  // ─── Constante para persistencia de progreso en localStorage ───────────────
  const LS_DOCS_EN_PROCESO = "ocr_docs_en_proceso";
  const LS_FASE_ACTUAL = "ocr_fase_actual";

  // Cargar estado previo de localStorage (si el usuario navegó y vuelve)
  const _leerEstadoPersistido = (): { docs: DocTracking[]; fase: string } => {
    if (typeof window === "undefined") return { docs: [], fase: "inactivo" };
    try {
      const rawDocs = localStorage.getItem(LS_DOCS_EN_PROCESO);
      const rawFase = localStorage.getItem(LS_FASE_ACTUAL);
      const docs: DocTracking[] = rawDocs ? JSON.parse(rawDocs) : [];
      const fase = rawFase || "inactivo";
      // Solo restaurar si hay docs en proceso real (procesando/pendiente)
      const tieneActivos = docs.some((d) => d.estado === "procesando" || d.estado === "pendiente");
      if (!tieneActivos) return { docs: [], fase: "inactivo" };
      return { docs, fase };
    } catch {
      return { docs: [], fase: "inactivo" };
    }
  };

  const estadoPersistido = typeof window !== "undefined" ? _leerEstadoPersistido() : { docs: [], fase: "inactivo" };

  // Estado para el seguimiento de subida y extracción OCR en vivo
  const [docsEnProceso, setDocsEnProceso] = useState<DocTracking[]>(estadoPersistido.docs);
  const [mostrandoProgreso, setMostrandoProgreso] = useState(estadoPersistido.docs.length > 0);
  const [faseActual, setFaseActual] = useState<"inactivo" | "subiendo" | "procesando" | "completado" | "error">(
    (estadoPersistido.fase as any) || "inactivo"
  );
  const [progresoSubida, setProgresoSubida] = useState(0);
  const [bytesSubidos, setBytesSubidos] = useState(0);
  const [bytesTotales, setBytesTotales] = useState(0);
  const [tiempoTranscurrido, setTiempoTranscurrido] = useState(0);
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const uploadStartTimeRef = useRef<number>(0);
  const panelProgresoRef = useRef<HTMLDivElement | null>(null);
  const [cancelando, setCancelando] = useState(false);
  const uploadAbortControllerRef = useRef<AbortController | null>(null);

  // Redirección automática a la tabla de personas al finalizar
  const [cuentaAtrasRedireccion, setCuentaAtrasRedireccion] = useState<number | null>(null);
  const canceladoRedireccionRef = useRef<boolean>(false);
  const redireccionIniciadaRef = useRef<boolean>(false);

  // Persistir docsEnProceso y faseActual en localStorage siempre que cambien
  useEffect(() => {
    if (typeof window === "undefined") return;
    const tieneActivos = docsEnProceso.some((d) => d.estado === "procesando" || d.estado === "pendiente");
    if (tieneActivos) {
      localStorage.setItem(LS_DOCS_EN_PROCESO, JSON.stringify(docsEnProceso));
      localStorage.setItem(LS_FASE_ACTUAL, faseActual);
    } else {
      // Limpiar si ya no hay nada activo
      localStorage.removeItem(LS_DOCS_EN_PROCESO);
      localStorage.removeItem(LS_FASE_ACTUAL);
    }
  }, [docsEnProceso, faseActual]);

  const cargarDocumentos = async () => {
    try {
      const res = await apiDocumentos.listar({ limit: 50, solo_subida: true });
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

  // Cronómetro durante procesamiento o subida activa
  useEffect(() => {
    const hayActivos =
      faseActual === "subiendo" ||
      docsEnProceso.some((d) => d.estado === "procesando" || d.estado === "pendiente");

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
  }, [faseActual, docsEnProceso]);

  // Polling de estado detallado de extracción OCR
  useEffect(() => {
    if (faseActual === "subiendo") return;

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
        if (updates.every((u) => u.estado === "completado" || u.estado === "error")) {
          setFaseActual("completado");
        }
        if (updates.some((u) => u.estado === "completado" || u.estado === "error")) {
          cargarDocumentos();
        }
      }
    }, 1200);

    return () => clearInterval(interval);
  }, [faseActual, docsEnProceso]);

  // Auto-scroll hacia la parte superior (tarjeta de progreso) al iniciar la subida o procesamiento
  useEffect(() => {
    if (mostrandoProgreso && (faseActual === "subiendo" || faseActual === "procesando")) {
      if (typeof window !== "undefined") {
        window.scrollTo({ top: 0, behavior: "smooth" });
      }
      setTimeout(() => {
        panelProgresoRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      }, 50);
    }
  }, [mostrandoProgreso, faseActual]);

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

  // Suma de tiempo real de procesamiento
  const tiempoTotalBackendMs = docsEnProceso.reduce((acc, d) => acc + (d.tiempo_procesamiento_ms || 0), 0);
  const tiempoProcesamientoTexto = tiempoTotalBackendMs > 0
    ? `${(tiempoTotalBackendMs / 1000).toFixed(1)}s`
    : `${tiempoTranscurrido}s`;

  // Efecto de redirección automática una vez finalizada la extracción
  useEffect(() => {
    if (procesoFinalizado && docsCompletadosCount > 0 && !canceladoRedireccionRef.current) {
      if (!redireccionIniciadaRef.current) {
        redireccionIniciadaRef.current = true;
        setCuentaAtrasRedireccion(3); // Iniciar cuenta regresiva de 3 segundos
      }
    }
  }, [procesoFinalizado, docsCompletadosCount]);

  // Manejador del temporizador de redirección: siempre redirige a /personas
  useEffect(() => {
    if (cuentaAtrasRedireccion === null) return;

    if (cuentaAtrasRedireccion <= 0) {
      const docCompletado = docsEnProceso.find((d) => d.estado === "completado") || docsEnProceso[0];
      if (docCompletado?.id) {
        if (typeof window !== "undefined") {
          localStorage.setItem("ultimo_documento_id", docCompletado.id);
          localStorage.setItem("nuevo_archivo_enviado", "true");
        }
        router.push(`/personas?documento_id=${docCompletado.id}`);
      } else {
        router.push("/personas");
      }
      return;
    }

    const timer = setTimeout(() => {
      setCuentaAtrasRedireccion((prev) => (prev !== null && prev > 0 ? prev - 1 : null));
    }, 1000);

    return () => clearTimeout(timer);
  }, [cuentaAtrasRedireccion, router]);

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

    if (!excelSeleccionado) {
      toast.error("La planilla Excel oficial es obligatoria para poder extraer los nombres correctamente.");
      return;
    }

    uploadAbortControllerRef.current = new AbortController();
    setSubiendo(true);
    setFaseActual("subiendo");
    setProgresoSubida(0);
    setTiempoTranscurrido(0);
    setCuentaAtrasRedireccion(null);
    canceladoRedireccionRef.current = false;
    redireccionIniciadaRef.current = false;
    uploadStartTimeRef.current = Date.now();
    setComparacionId(null);
    setComparacionEnProgreso(false);

    const totalBytes = archivosSeleccionados.reduce((acc, f) => acc + f.size, 0);
    setBytesTotales(totalBytes);
    setBytesSubidos(0);

    // Inicializar seguimiento visual inmediatamente
    const initialTracking: DocTracking[] = archivosSeleccionados.map((f, i) => ({
      id: `prep-${i}`,
      nombre: f.name,
      estado: "procesando",
      progreso: 5,
      paso: "Transfiriendo archivo al servidor...",
      total_paginas: 0,
      pagina_actual: 0,
      personas_count: 0,
      confianza_ocr: null,
    }));

    setDocsEnProceso(initialTracking);
    setMostrandoProgreso(true);

    // Scroll automático suave hacia arriba donde se muestra la tarjeta de progreso en vivo
    if (typeof window !== "undefined") {
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
    setTimeout(() => {
      panelProgresoRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 50);

    try {
      const res = await apiDocumentos.upload(
        archivosSeleccionados,
        (progressEvent) => {
          if (progressEvent.total) {
            const pct = Math.min(100, Math.round((progressEvent.loaded * 100) / progressEvent.total));
            setProgresoSubida(pct);
            setBytesSubidos(progressEvent.loaded);
            setBytesTotales(progressEvent.total);
            setDocsEnProceso((prev) =>
              prev.map((d) => ({
                ...d,
                progreso: Math.max(5, Math.min(99, Math.round(pct * 0.9))),
                paso: `Transfiriendo archivo al servidor (${formatSize(progressEvent.loaded)} de ${formatSize(progressEvent.total)} - ${pct}%)...`,
              }))
            );
          }
        },
        excelSeleccionado,
        uploadAbortControllerRef.current.signal
      );

      setFaseActual("procesando");
      const docsResp = res.data?.documentos || [];

      // Registrar el ID del nuevo archivo enviado para que la tabla de Personas lo muestre automáticamente
      if (docsResp.length > 0 && typeof window !== "undefined") {
        localStorage.setItem("ultimo_documento_id", docsResp[0].id);
        localStorage.setItem("nuevo_archivo_enviado", "true");
      }

      // Si se adjuntó Excel y el backend devolvió comparacion_id
      if (res.data?.comparacion_id) {
        setComparacionId(res.data.comparacion_id);
        setComparacionEnProgreso(true);
        toast.success("📊 Excel adjunto recibido. La comparación iniciará al terminar el OCR.");
      }

      const trackingEncolado: DocTracking[] = (docsResp.length > 0
        ? docsResp
        : archivosSeleccionados.map((f, i) => ({
            id: `doc-${i}`,
            nombre_original: f.name,
            estado: "procesando",
          }))
      ).map((d: any) => ({
        id: d.id,
        nombre: d.nombre_original || d.nombre || "Documento PDF",
        estado: (d.estado as any) || "procesando",
        progreso: 12,
        paso: "Iniciando lectura y OCR con Google Document AI...",
        total_paginas: 0,
        pagina_actual: 0,
        personas_count: 0,
        confianza_ocr: null,
      }));

      setDocsEnProceso(trackingEncolado);
      setArchivosSeleccionados([]);
      setExcelSeleccionado(null);
      cargarDocumentos();

      toast.success("Documento(s) recibido(s). Iniciando extracción OCR...");
    } catch (err: unknown) {
      if (axios.isCancel(err) || (err as any)?.name === "CanceledError" || (err as any)?.name === "AbortError") {
        return;
      }
      setFaseActual("error");
      toast.error(getErrorMessage(err, "Error subiendo archivos"));
    } finally {
      setSubiendo(false);
      uploadAbortControllerRef.current = null;
    }
  };

  const cancelarSubidaOProceso = async () => {
    const esSubiendo = faseActual === "subiendo";
    const mensajeConfirm = esSubiendo
      ? "¿Deseas cancelar la subida de los archivos?\n\nLa transferencia se detendrá inmediatamente y no se procesará ningún documento."
      : "¿Deseas cancelar el procesamiento de los documentos?\n\nLos archivos y sus datos serán removidos por completo del sistema y no quedarán en proceso.";

    if (!window.confirm(mensajeConfirm)) return;

    setCancelando(true);
    try {
      // 1. Abortar transferencia de red si aún está en subida
      if (uploadAbortControllerRef.current) {
        uploadAbortControllerRef.current.abort();
        uploadAbortControllerRef.current = null;
      }

      // 2. Extraer IDs de documentos para cancelar en backend
      const idsValidos = docsEnProceso
        .map((d) => d.id)
        .filter((id) => id && !id.startsWith("prep-") && !id.startsWith("doc-"));

      await apiDocumentos.cancelar({
        documento_ids: idsValidos.length > 0 ? idsValidos : undefined,
        comparacion_id: comparacionId,
        todos_en_proceso: true,
      });

      // 3. Limpiar estado local y storage
      setSubiendo(false);
      setFaseActual("inactivo");
      setMostrandoProgreso(false);
      setDocsEnProceso([]);
      setProgresoSubida(0);
      setBytesSubidos(0);
      setBytesTotales(0);
      setTiempoTranscurrido(0);
      setComparacionId(null);
      setComparacionEnProgreso(false);
      setCuentaAtrasRedireccion(null);
      canceladoRedireccionRef.current = true;

      if (typeof window !== "undefined") {
        localStorage.removeItem(LS_DOCS_EN_PROCESO);
        localStorage.removeItem(LS_FASE_ACTUAL);
        localStorage.removeItem("ultimo_documento_id");
      }

      toast.success("Subida cancelada y archivos en proceso removidos.");
      await cargarDocumentos();
    } catch (err) {
      toast.error(getErrorMessage(err, "Error al cancelar la subida"));
    } finally {
      setCancelando(false);
    }
  };

  const cancelarDocumentoIndividual = async (id: string, nombre: string) => {
    if (!window.confirm(`¿Cancelar el proceso de "${nombre}" y removerlo por completo del sistema?`)) return;
    try {
      await apiDocumentos.cancelar({ documento_ids: [id] });
      toast.success(`Proceso cancelado. "${nombre}" fue removido.`);

      // Removerlo también de docsEnProceso si estuviera en la tarjeta
      setDocsEnProceso((prev) => {
        const nuevos = prev.filter((d) => d.id !== id);
        if (nuevos.length === 0) {
          setMostrandoProgreso(false);
          setFaseActual("inactivo");
          if (typeof window !== "undefined") {
            localStorage.removeItem(LS_DOCS_EN_PROCESO);
            localStorage.removeItem(LS_FASE_ACTUAL);
          }
        }
        return nuevos;
      });

      cargarDocumentos();
    } catch (err) {
      toast.error(getErrorMessage(err, "Error al cancelar el documento"));
    }
  };

  const eliminarDocumento = async (id: string, nombre: string) => {
    if (!confirm(`¿Quitar "${nombre}" del apartado de subida?\n\nNota: Su historial de ficha y personas asociadas seguirán disponibles en el Dashboard.`)) return;
    try {
      await apiDocumentos.eliminar(id);
      toast.success("Documento quitado del apartado de subida. Su historial y personas siguen disponibles en el Dashboard.");
      cargarDocumentos();
    } catch (err: unknown) {
      toast.error(getErrorMessage(err, "Error quitando documento"));
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

  // Estimación dinámica del tiempo restante
  const calcularTiempoEstimado = (): string => {
    if (procesoFinalizado) {
      return "0s (Completado)";
    }

    if (faseActual === "subiendo") {
      if (progresoSubida <= 0) return "Calculando...";
      const segundosSubiendo = Math.max(0.4, (Date.now() - uploadStartTimeRef.current) / 1000);
      const velocidad = bytesSubidos / segundosSubiendo; // bytes / sec
      if (velocidad > 0 && bytesTotales > bytesSubidos) {
        const segRestantes = Math.max(1, Math.ceil((bytesTotales - bytesSubidos) / velocidad));
        return `~${segRestantes}s (subida)`;
      }
      return "~1s";
    }

    if (faseActual === "procesando" || docsEnProceso.some((d) => d.estado === "procesando" || d.estado === "pendiente")) {
      if (tiempoTranscurrido < 2 && progresoGlobal < 15) {
        const estPaginas = totalPaginasProcesadas > 0 ? totalPaginasProcesadas : Math.max(1, totalDocsTracking) * 2;
        const estSegundos = Math.max(4, Math.round(estPaginas * 2.5));
        return `~${estSegundos}s`;
      }

      if (progresoGlobal > 0 && progresoGlobal < 100) {
        const progresoRestante = 100 - progresoGlobal;
        const segundosPorPunto = Math.max(0.1, (tiempoTranscurrido + 1) / Math.max(progresoGlobal, 10));
        const estSegundos = Math.max(1, Math.round(progresoRestante * segundosPorPunto));
        return `~${estSegundos}s`;
      }

      return "~3s";
    }

    return "-";
  };

  return (
    <div className="flex min-h-screen bg-dark-950 text-slate-100">
      <Sidebar />
      <main className={`${collapsed ? "ml-20" : "ml-64"} transition-all duration-300 ease-in-out flex-1 p-8 max-w-7xl min-w-0`}>
        {/* Encabezado */}
        <div className="mb-8 page-enter">
          <div className="flex items-center gap-2 mb-1">
            <FileText className="w-5 h-5 text-primary-400" />
            <span className="text-primary-400 text-sm font-medium">Procesamiento de Documentos</span>
          </div>
          <h1 className="text-3xl font-bold text-white tracking-tight">Documentos PDF</h1>
          <p className="text-slate-400 mt-1">
            Sube la planilla Excel oficial y el PDF para extraer datos de identidad con OCR
          </p>
        </div>

        {/* ─────────────────────────────────────────────────────────────
            MODAL / TARJETA DE PROGRESO DE SUBIDA Y EXTRACCIÓN OCR EN VIVO
           ───────────────────────────────────────────────────────────── */}
        {mostrandoProgreso && docsEnProceso.length > 0 && (
          <div
            ref={panelProgresoRef}
            id="panel-progreso-ocr"
            className="mb-8 p-6 sm:p-7 rounded-2xl bg-dark-900/95 border border-primary-500/30 shadow-2xl shadow-primary-950/40 relative overflow-hidden backdrop-blur-xl animate-in fade-in zoom-in-95 duration-300 scroll-mt-6"
          >
            {/* Resplandor ambiental de fondo */}
            <div className="absolute -right-20 -top-20 w-72 h-72 bg-primary-500/10 rounded-full blur-3xl pointer-events-none" />
            <div className="absolute -left-20 -bottom-20 w-72 h-72 bg-blue-600/10 rounded-full blur-3xl pointer-events-none" />

            {/* Cabecera del Progreso */}
            <div className="flex items-start justify-between gap-4 pb-4 border-b border-white/[0.08] relative z-10">
              <div className="flex items-center gap-3">
                <div className={`w-11 h-11 rounded-xl flex items-center justify-center ${
                  procesoFinalizado
                    ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                    : faseActual === "subiendo"
                    ? "bg-blue-500/20 text-blue-400 border border-blue-500/30 animate-pulse"
                    : "bg-primary-500/20 text-primary-400 border border-primary-500/30 animate-pulse"
                }`}>
                  {procesoFinalizado ? (
                    <CheckCircle2 className="w-6 h-6" />
                  ) : faseActual === "subiendo" ? (
                    <ArrowUpCircle className="w-6 h-6 animate-bounce" />
                  ) : (
                    <Cpu className="w-6 h-6" />
                  )}
                </div>
                <div>
                  <div className="flex items-center gap-2.5">
                    <h3 className="text-lg font-bold text-white">
                      {procesoFinalizado
                        ? `¡Extracción Completada en ${tiempoProcesamientoTexto}!`
                        : faseActual === "subiendo"
                        ? "Subiendo Documento al Servidor..."
                        : "Extrayendo Datos del Documento PDF..."}
                    </h3>
                    <span className={`badge ${
                      procesoFinalizado
                        ? "badge-success"
                        : faseActual === "subiendo"
                        ? "badge-info"
                        : "badge-warning"
                    } text-xs px-2.5 py-0.5`}>
                      {procesoFinalizado
                        ? "Finalizado"
                        : faseActual === "subiendo"
                        ? "Transfiriendo"
                        : "En progreso"}
                    </span>
                  </div>
                  <p className="text-sm text-slate-400 mt-0.5">
                    {procesoFinalizado
                      ? `Se estructuraron ${totalPersonasDetectadas} personas y se guardaron en la base de datos.`
                      : faseActual === "subiendo"
                      ? "Transfiriendo archivo con cifrado seguro al motor de procesamiento..."
                      : "Google Document AI y el motor OCR están leyendo y agrupando los datos."}
                  </p>
                </div>
              </div>

              {/* Indicadores de Cronómetro y Tiempo Estimado */}
              <div className="flex items-center gap-2 sm:gap-3">
                <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-100 dark:bg-dark-800/80 border border-slate-300 dark:border-white/[0.08] text-xs font-mono text-slate-700 dark:text-slate-300 shadow-sm">
                  <Timer className="w-3.5 h-3.5 text-primary-500 dark:text-primary-400" />
                  <span>
                    {procesoFinalizado ? "Tiempo total:" : "Transcurrido:"}{" "}
                    <strong className="text-slate-900 dark:text-white">
                      {procesoFinalizado ? tiempoProcesamientoTexto : formatTimer(tiempoTranscurrido)}
                    </strong>
                  </span>
                </div>

                {!procesoFinalizado && (
                  <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-primary-500/10 border border-primary-500/20 text-xs font-mono text-primary-300">
                    <Hourglass className="w-3.5 h-3.5 text-primary-400" />
                    <span>Estimado: <strong className="text-white">{calcularTiempoEstimado()}</strong></span>
                  </div>
                )}

                {!procesoFinalizado && (
                  <button
                    type="button"
                    onClick={cancelarSubidaOProceso}
                    disabled={cancelando}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-rose-500/15 hover:bg-rose-500/25 text-rose-300 hover:text-rose-200 border border-rose-500/30 text-xs font-semibold transition-all shadow-sm cursor-pointer disabled:opacity-50"
                    title="Cancelar subida y remover archivos del sistema"
                  >
                    <XCircle className="w-4 h-4 text-rose-400" />
                    <span>{cancelando ? "Cancelando..." : "Cancelar subida"}</span>
                  </button>
                )}

                <button
                  onClick={() => {
                    canceladoRedireccionRef.current = true;
                    setCuentaAtrasRedireccion(null);
                    setMostrandoProgreso(false);
                  }}
                  className="text-slate-400 hover:text-white p-1.5 rounded-lg hover:bg-dark-800 transition-colors"
                  title="Minimizar panel de progreso"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>

            {/* Banner de Comparación Automática en Progreso */}
            {comparacionEnProgreso && !procesoFinalizado && (
              <div className="mt-4 p-3.5 bg-blue-500/10 border border-blue-500/30 rounded-xl flex items-center gap-3 text-sm text-blue-200 relative z-10 animate-in fade-in duration-300">
                <div className="w-8 h-8 rounded-lg bg-blue-500/20 border border-blue-500/30 flex items-center justify-center flex-shrink-0">
                  <FileSpreadsheet className="w-4 h-4 text-blue-400" />
                </div>
                <div>
                  <p className="font-semibold text-blue-100 text-xs">Planilla cargada para Comparación automática</p>
                  <p className="text-xs text-blue-300 mt-0.5">Al terminar el OCR, la planilla se cotejará automáticamente en el módulo de Comparación.</p>
                </div>
                <div className="ml-auto flex-shrink-0">
                  <div className="flex gap-1">
                    {[0,1,2].map(i => (
                      <div key={i} className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-bounce" style={{animationDelay: `${i * 0.15}s`}} />
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* Banner de Proceso Finalizado con Redirección a la Tabla de Personas */}
            {procesoFinalizado && (
              <div className="mt-4 p-3.5 bg-emerald-500/15 border border-emerald-500/30 rounded-xl flex flex-col sm:flex-row items-center justify-between gap-3 text-xs sm:text-sm text-emerald-200 relative z-10 animate-in fade-in duration-300">
                <div className="flex items-center gap-3">
                  {cuentaAtrasRedireccion !== null ? (
                    <div className="w-8 h-8 rounded-full bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center font-bold text-emerald-400 font-mono text-xs flex-shrink-0 animate-pulse">
                      {cuentaAtrasRedireccion}
                    </div>
                  ) : (
                    <div className="w-8 h-8 rounded-lg bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center font-bold text-emerald-400 flex-shrink-0">
                      <CheckCircle2 className="w-4 h-4" />
                    </div>
                  )}
                  <div>
                    <span className="font-semibold text-white">
                      Extracción completada. {totalPersonasDetectadas} persona(s) listas en el sistema.
                    </span>
                    <p className="text-xs text-emerald-300/90 mt-0.5">
                      {cuentaAtrasRedireccion !== null ? (
                        <>Redirigiendo a la tabla de personas en <strong>{cuentaAtrasRedireccion}s</strong>...</>
                      ) : (
                        <>Las personas ya están registradas en la tabla.</>
                      )}
                      {comparacionId && (
                        <span className="text-indigo-300 ml-1.5 font-medium">· Planilla cargada en Comparación.</span>
                      )}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2 w-full sm:w-auto justify-end flex-shrink-0">
                  {cuentaAtrasRedireccion !== null && (
                    <button
                      onClick={() => {
                        canceladoRedireccionRef.current = true;
                        setCuentaAtrasRedireccion(null);
                      }}
                      className="text-xs text-slate-300 hover:text-white underline px-2 py-1"
                    >
                      Permanecer aquí
                    </button>
                  )}
                  <button
                    onClick={() => {
                      const docCompletado = docsEnProceso.find((d) => d.estado === "completado") || docsEnProceso[0];
                      router.push(docCompletado?.id ? `/personas?documento_id=${docCompletado.id}` : "/personas");
                    }}
                    className="text-xs bg-emerald-500 hover:bg-emerald-400 text-dark-950 font-bold px-3.5 py-1.5 rounded-lg transition-all flex items-center gap-1 shadow-md hover:shadow-emerald-500/30 cursor-pointer"
                  >
                    <span>Ir a Personas</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                  {comparacionId && (
                    <button
                      onClick={() => router.push(`/comparacion?id=${comparacionId}`)}
                      className="text-xs bg-indigo-600 hover:bg-indigo-500 text-white font-bold px-3 py-1.5 rounded-lg transition-all flex items-center gap-1.5 shadow-md shadow-indigo-500/25"
                      title="Ver auditoría en el módulo de Comparación"
                    >
                      <BarChart2 className="w-3.5 h-3.5" />
                      <span>Ver Comparación</span>
                    </button>
                  )}
                </div>
              </div>
            )}

            {/* Barra de Progreso Principal (Subida o Extracción) */}
            <div className="mt-6 space-y-2 relative z-10">
              <div className="flex items-center justify-between text-sm">
                <span className="font-semibold text-slate-200 flex items-center gap-2">
                  <span>
                    {faseActual === "subiendo"
                      ? "Progreso de Subida de Archivo"
                      : "Progreso de Extracción OCR"}
                  </span>
                  <span className="text-xs text-primary-400 font-mono">
                    ({faseActual === "subiendo" ? progresoSubida : progresoGlobal}%)
                  </span>
                </span>
                <span className="text-xs text-slate-400">
                  {faseActual === "subiendo"
                    ? `${formatSize(bytesSubidos)} de ${formatSize(bytesTotales)}`
                    : `${docsCompletadosCount} de ${totalDocsTracking} documento(s) procesados`}
                </span>
              </div>

              <div className="w-full h-3.5 bg-slate-200 dark:bg-dark-800 rounded-full overflow-hidden p-0.5 border border-slate-300 dark:border-white/[0.08] relative shadow-inner">
                <div
                  className={`h-full rounded-full transition-all duration-300 ease-out relative ${
                    procesoFinalizado
                      ? "bg-gradient-to-r from-emerald-500 to-teal-400 shadow-lg shadow-emerald-500/30"
                      : faseActual === "subiendo"
                      ? "bg-gradient-to-r from-blue-600 to-cyan-400 shadow-lg shadow-blue-500/30"
                      : "bg-gradient-to-r from-primary-600 via-blue-500 to-primary-400 shadow-lg shadow-primary-500/30"
                  }`}
                  style={{
                    width: `${Math.min(
                      100,
                      Math.max(5, faseActual === "subiendo" ? progresoSubida : progresoGlobal)
                    )}%`,
                  }}
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
                progresoSubida >= 100 || faseActual === "procesando" || procesoFinalizado
                  ? "bg-emerald-50 dark:bg-emerald-500/10 border-emerald-300 dark:border-emerald-500/30 text-emerald-950 dark:text-emerald-300"
                  : faseActual === "subiendo"
                  ? "bg-blue-50 dark:bg-blue-500/10 border-blue-300 dark:border-blue-500/30 text-blue-950 dark:text-blue-300 animate-pulse"
                  : "bg-slate-100 dark:bg-dark-800/40 border-slate-300 dark:border-white/[0.04] text-slate-800 dark:text-slate-400"
              }`}>
                <div className="flex items-center gap-2 font-bold text-xs mb-1 text-slate-900 dark:text-white">
                  <span className="w-4 h-4 rounded-full bg-primary-600 dark:bg-primary-500/20 text-white dark:text-primary-400 flex items-center justify-center text-[10px] font-bold">1</span>
                  Carga del PDF
                </div>
                <p className="text-[11px] text-slate-700 dark:text-slate-300 font-medium">
                  {progresoSubida >= 100 ? "Subida completada" : `${progresoSubida}% cargado`}
                </p>
              </div>

              <div className={`p-3 rounded-xl border transition-all ${
                progresoGlobal >= 40
                  ? "bg-primary-50 dark:bg-primary-500/10 border-primary-300 dark:border-primary-500/30 text-primary-950 dark:text-primary-300"
                  : "bg-slate-100 dark:bg-dark-800/40 border-slate-300 dark:border-white/[0.04] text-slate-800 dark:text-slate-400"
              }`}>
                <div className="flex items-center gap-2 font-bold text-xs mb-1 text-slate-900 dark:text-white">
                  <span className="w-4 h-4 rounded-full bg-primary-600 dark:bg-primary-500/20 text-white dark:text-primary-400 flex items-center justify-center text-[10px] font-bold">2</span>
                  Reconocimiento OCR
                </div>
                <p className="text-[11px] text-slate-700 dark:text-slate-300 font-medium">Google Document AI</p>
              </div>

              <div className={`p-3 rounded-xl border transition-all ${
                progresoGlobal >= 75
                  ? "bg-primary-50 dark:bg-primary-500/10 border-primary-300 dark:border-primary-500/30 text-primary-950 dark:text-primary-300"
                  : "bg-slate-100 dark:bg-dark-800/40 border-slate-300 dark:border-white/[0.04] text-slate-800 dark:text-slate-400"
              }`}>
                <div className="flex items-center gap-2 font-bold text-xs mb-1 text-slate-900 dark:text-white">
                  <span className="w-4 h-4 rounded-full bg-primary-600 dark:bg-primary-500/20 text-white dark:text-primary-400 flex items-center justify-center text-[10px] font-bold">3</span>
                  Emparejamiento
                </div>
                <p className="text-[11px] text-slate-700 dark:text-slate-300 font-medium">Frente y Reverso</p>
              </div>

              <div className={`p-3 rounded-xl border transition-all ${
                progresoGlobal >= 100
                  ? "bg-emerald-50 dark:bg-emerald-500/10 border-emerald-300 dark:border-emerald-500/30 text-emerald-950 dark:text-emerald-300"
                  : progresoGlobal >= 85
                  ? "bg-primary-50 dark:bg-primary-500/10 border-primary-300 dark:border-primary-500/30 text-primary-950 dark:text-primary-300"
                  : "bg-slate-100 dark:bg-dark-800/40 border-slate-300 dark:border-white/[0.04] text-slate-800 dark:text-slate-400"
              }`}>
                <div className="flex items-center gap-2 font-bold text-xs mb-1 text-slate-900 dark:text-white">
                  <span className={`w-4 h-4 rounded-full ${progresoGlobal >= 100 ? "bg-emerald-600 dark:bg-emerald-500/20 text-white dark:text-emerald-400" : "bg-primary-600 dark:bg-primary-500/20 text-white dark:text-primary-400"} flex items-center justify-center text-[10px] font-bold`}>4</span>
                  Extracción Personas
                </div>
                <p className="text-[11px] text-slate-700 dark:text-slate-300 font-medium">Estructuración y guardado</p>
              </div>
            </div>

            {/* Detalle por Documento Individual */}
            <div className="mt-5 space-y-2.5 relative z-10">
              {docsEnProceso.map((doc) => (
                <div
                  key={doc.id}
                  className="p-3.5 bg-slate-50 dark:bg-dark-800/70 border border-slate-300 dark:border-white/[0.06] rounded-xl flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-sm"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <FileText className="w-5 h-5 text-primary-500 dark:text-primary-400 flex-shrink-0" />
                    <div className="min-w-0">
                      <p className="text-sm font-bold text-slate-900 dark:text-white truncate max-w-sm sm:max-w-md">
                        {doc.nombre}
                      </p>
                      <p className="text-xs text-slate-700 dark:text-slate-300 font-medium flex items-center gap-1.5 mt-0.5">
                        {doc.estado === "procesando" && (
                          <RefreshCw className="w-3 h-3 text-yellow-600 dark:text-yellow-400 animate-spin flex-shrink-0" />
                        )}
                        {doc.estado === "completado" && (
                          <CheckCircle2 className="w-3 h-3 text-emerald-600 dark:text-emerald-400 flex-shrink-0" />
                        )}
                        {doc.estado === "error" && (
                          <AlertCircle className="w-3 h-3 text-red-600 dark:text-red-400 flex-shrink-0" />
                        )}
                        <span className="font-semibold text-slate-800 dark:text-slate-200">{doc.paso}</span>
                        {doc.total_paginas > 0 && (
                          <span className="text-slate-600 dark:text-slate-400 font-medium">
                            • {doc.pagina_actual > 0 ? `Pág. ${doc.pagina_actual}/${doc.total_paginas}` : `${doc.total_paginas} págs`}
                          </span>
                        )}
                        {doc.tiempo_procesamiento_ms && (
                          <span className="text-primary-700 dark:text-primary-400 font-mono font-bold">
                            • {(doc.tiempo_procesamiento_ms / 1000).toFixed(1)}s
                          </span>
                        )}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-3 self-end sm:self-center flex-shrink-0">
                    {doc.personas_count > 0 && (
                      <span className="badge badge-info text-xs flex items-center gap-1 font-bold">
                        <Users className="w-3 h-3" />
                        {doc.personas_count} persona(s)
                      </span>
                    )}
                    {doc.confianza_ocr !== null && (
                      <span className="badge badge-success text-xs font-mono font-bold">
                        {getConfianzaDisplay(doc.confianza_ocr)}% conf.
                      </span>
                    )}
                    <span className="text-xs font-mono font-bold text-primary-700 dark:text-primary-400 w-10 text-right">
                      {faseActual === "subiendo" ? `${progresoSubida}%` : `${doc.progreso}%`}
                    </span>
                  </div>
                </div>
              ))}
            </div>

            {/* Resumen Final y Botones de Acción */}
            {procesoFinalizado && (
              <div className="mt-6 pt-5 border-t border-white/[0.08] flex flex-col md:flex-row items-center justify-between gap-4 relative z-10 animate-in fade-in duration-300">
                <div className="flex flex-wrap items-center gap-4 text-xs text-slate-300">
                  <div className="flex items-center gap-1.5 bg-primary-500/10 px-2.5 py-1 rounded-lg border border-primary-500/20">
                    <Timer className="w-4 h-4 text-primary-400" />
                    <span>Tiempo total de extracción: <strong className="text-white text-sm font-mono">{tiempoProcesamientoTexto}</strong></span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <Users className="w-4 h-4 text-emerald-400" />
                    <span>Personas extraídas: <strong className="text-white text-sm">{totalPersonasDetectadas}</strong></span>
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
                      canceladoRedireccionRef.current = true;
                      setCuentaAtrasRedireccion(null);
                      setMostrandoProgreso(false);
                      cargarDocumentos();
                    }}
                    className="btn-secondary text-sm py-2.5 px-4 flex-1 md:flex-initial"
                  >
                    Ver Historial de Documentos
                  </button>
                  <button
                    onClick={() => {
                      const docCompletado = docsEnProceso.find((d) => d.estado === "completado") || docsEnProceso[0];
                      if (docCompletado?.id && typeof window !== "undefined") {
                        localStorage.setItem("ultimo_documento_id", docCompletado.id);
                        localStorage.setItem("nuevo_archivo_enviado", "true");
                      }
                      router.push(docCompletado?.id ? `/personas?documento_id=${docCompletado.id}` : "/personas");
                    }}
                    className="btn-primary text-sm py-2.5 px-5 flex-1 md:flex-initial flex items-center justify-center gap-2 shadow-lg shadow-primary-500/25 cursor-pointer"
                  >
                    <Users className="w-4 h-4" />
                    <span>Ver Personas Extraídas</span>
                    <ArrowRight className="w-4 h-4" />
                  </button>
                  {comparacionId && (
                    <button
                      onClick={() => router.push(`/comparacion?id=${comparacionId}`)}
                      className="text-sm py-2.5 px-5 flex-1 md:flex-initial flex items-center justify-center gap-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-semibold shadow-lg shadow-indigo-500/25 transition-all"
                    >
                      <BarChart2 className="w-4 h-4" />
                      <span>Ver Comparación</span>
                      <ArrowRight className="w-4 h-4" />
                    </button>
                  )}
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
            <h2 className="text-lg font-bold text-slate-900 dark:text-white flex items-center gap-2">
              <Upload className="w-4 h-4 text-primary-600 dark:text-primary-400" />
              Cargar Documentos PDF
            </h2>
            <span className="text-xs text-slate-600 dark:text-slate-400 font-semibold">Formato admitido: PDF (Cédulas colombianas)</span>
          </div>

          {/* ── PASO 1: PLANILLA EXCEL OFICIAL (OBLIGATORIO) ────────────────── */}
          <div className={`mb-6 p-4 rounded-xl border-2 transition-all ${
            excelSeleccionado
              ? "border-emerald-600/70 dark:border-emerald-500/50 bg-emerald-50 dark:bg-emerald-500/[0.06]"
              : "border-dashed border-amber-600/50 dark:border-amber-500/40 bg-amber-50 dark:bg-amber-500/[0.04]"
          }`}>
            <div className="flex items-center gap-2 mb-2">
              <div className="w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0 bg-amber-600 dark:bg-amber-500 text-white dark:text-dark-950">
                1
              </div>
              <FileSpreadsheet className="w-4 h-4 text-emerald-700 dark:text-emerald-400" />
              <h3 className="text-sm font-bold text-slate-900 dark:text-white">Planilla Excel Oficial</h3>
              <span className="text-[10px] font-extrabold text-amber-950 dark:text-amber-300 bg-amber-100 dark:bg-amber-500/20 border border-amber-400 dark:border-amber-500/40 px-2 py-0.5 rounded-full">OBLIGATORIO</span>
            </div>
            <p className="text-xs text-slate-700 dark:text-slate-300 font-medium mb-3 ml-8">
              Los nombres y apellidos de las personas se extraerán de esta planilla usando el número de cédula/TI como referencia.
            </p>

            {excelSeleccionado ? (
              <div className="ml-8 flex items-center justify-between p-3.5 bg-emerald-100/90 dark:bg-emerald-500/15 border-2 border-emerald-500/50 dark:border-emerald-500/30 rounded-xl shadow-sm">
                <div className="flex items-center gap-3 min-w-0">
                  <div className="w-9 h-9 rounded-lg bg-emerald-200/80 dark:bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center flex-shrink-0">
                    <FileSpreadsheet className="w-5 h-5 text-emerald-800 dark:text-emerald-300" />
                  </div>
                  <div className="min-w-0">
                    <span className="text-sm font-bold text-slate-900 dark:text-emerald-200 truncate block tracking-tight">{excelSeleccionado.name}</span>
                    <span className="text-xs text-emerald-900 dark:text-slate-400 font-mono font-semibold">{formatSize(excelSeleccionado.size)} · Planilla oficial lista ✓</span>
                  </div>
                </div>
                <button
                  onClick={() => setExcelSeleccionado(null)}
                  disabled={subiendo}
                  className="text-slate-700 dark:text-slate-400 hover:text-red-700 dark:hover:text-red-400 transition-colors p-1.5 rounded-lg hover:bg-emerald-200/60 dark:hover:bg-dark-700 flex-shrink-0 cursor-pointer"
                  title="Cambiar Excel"
                >
                  <X className="w-4 h-4 text-slate-700 dark:text-slate-400" />
                </button>
              </div>
            ) : (
              <label className="ml-8 flex items-center gap-3 p-3.5 bg-dark-800/60 border border-dashed border-amber-500/30 rounded-xl cursor-pointer hover:border-amber-500/60 hover:bg-dark-800 transition-all group">
                <input
                  type="file"
                  accept=".xlsx,.xls"
                  className="hidden"
                  disabled={subiendo}
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (!f) return;
                    const ext = f.name.split(".").pop()?.toLowerCase();
                    if (!ext || !["xlsx", "xls"].includes(ext)) {
                      toast.error("Solo se aceptan archivos .xlsx o .xls");
                      return;
                    }
                    setExcelSeleccionado(f);
                    toast.success(`✅ Planilla oficial cargada: ${f.name}`);
                  }}
                />
                <div className="w-9 h-9 rounded-lg bg-amber-500/10 border border-amber-500/20 flex items-center justify-center flex-shrink-0 group-hover:bg-amber-500/20 transition-colors">
                  <PlusCircle className="w-5 h-5 text-amber-400" />
                </div>
                <div>
                  <p className="text-sm font-bold text-amber-950 dark:text-amber-300 group-hover:text-amber-900 dark:group-hover:text-amber-200 transition-colors">
                    Haz clic para seleccionar la planilla Excel
                  </p>
                  <p className="text-xs text-slate-700 dark:text-slate-400 font-medium mt-0.5">.xlsx · .xls · Requerido para extracción correcta de nombres</p>
                </div>
              </label>
            )}
          </div>

          {/* ── PASO 2: PDF(s) ───────────────────────────────────────── */}
          <div className="flex items-center gap-2 mb-3">
            <div className="w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0 bg-primary-600 dark:bg-primary-500 text-white dark:text-dark-950">
              2
            </div>
            <Upload className="w-4 h-4 text-primary-600 dark:text-primary-400" />
            <h3 className="text-sm font-bold text-slate-900 dark:text-white">Documentos PDF (Cédulas)</h3>
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

              {/* ── Sección Excel adjunto opcional ── ELIMINADA: ahora Excel es Paso 1 ── */}

              {/* Barra de Acciones del Botón OCR */}
              <div className="mt-6 pt-5 border-t border-white/[0.08] flex flex-col sm:flex-row items-center justify-between gap-4">
                <div className="text-xs text-slate-400 flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-primary-400 flex-shrink-0" />
                  <span>
                    {excelSeleccionado
                      ? "Planilla lista: los nombres oficiales se integran al OCR y se carga automáticamente en Comparación."
                      : (
                        <span className="text-amber-400 font-medium">
                          ⚠️ Selecciona primero la planilla Excel oficial (Paso 1) para continuar.
                        </span>
                      )}
                  </span>
                </div>

                <button
                  onClick={subirArchivos}
                  disabled={subiendo || !excelSeleccionado}
                  className={`w-full sm:w-auto py-3.5 px-8 text-base font-semibold rounded-xl flex items-center justify-center gap-3 shadow-lg transition-all transform ${
                    excelSeleccionado && !subiendo
                      ? "btn-primary hover:shadow-primary-500/40 hover:-translate-y-0.5 shadow-primary-500/25"
                      : "bg-dark-700 text-slate-500 border border-white/[0.06] cursor-not-allowed"
                  }`}
                >
                  {subiendo ? (
                    <>
                      <div className="spinner" />
                      <span>
                        {faseActual === "subiendo"
                          ? `Subiendo (${progresoSubida}%)...`
                          : "Iniciando OCR..."}
                      </span>
                    </>
                  ) : (
                    <>
                      <Sparkles className="w-5 h-5 text-blue-200" />
                      <span>{excelSeleccionado ? "Iniciar OCR + Comparación" : "Selecciona el Excel primero"}</span>
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
                          {doc.estado === "procesando" || doc.estado === "pendiente" ? (
                            <button
                              onClick={() => cancelarDocumentoIndividual(doc.id, doc.nombre_original)}
                              className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-rose-500/15 hover:bg-rose-500/25 text-rose-300 hover:text-rose-200 border border-rose-500/30 text-xs font-medium transition-all shadow-sm"
                              title="Cancelar procesamiento y remover archivo por completo"
                            >
                              <XCircle className="w-3.5 h-3.5 text-rose-400" />
                              <span>Cancelar</span>
                            </button>
                          ) : (
                            <button
                              onClick={() => eliminarDocumento(doc.id, doc.nombre_original)}
                              className="text-slate-500 hover:text-red-400 transition-colors p-2 rounded-lg hover:bg-dark-800"
                              title="Eliminar documento"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          )}
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
