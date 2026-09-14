"use client";

import { useState, useEffect, useRef, Fragment } from "react";
import { usePathname, useRouter } from "next/navigation";
import toast from "react-hot-toast";
import {
  Users, Search, AlertTriangle, AlertCircle, CheckCircle,
  Edit3, Save, X, RefreshCw, Trash2, Calendar, MapPin,
  UserCheck, FileText, Eye, EyeOff,
  ZoomIn, ZoomOut, RotateCw, ImageOff, Hash, Clock, Cpu,
  ChevronDown, ChevronUp, Download, CheckSquare, Square, UploadCloud, FileSpreadsheet
} from "lucide-react";
import Sidebar from "@/components/ui/Sidebar";
import { apiPersonas, apiDocumentos, apiExportacion, getErrorMessage } from "@/lib/api";
import { auth } from "@/lib/auth";
import { formatNombreCompleto, calcularEdad } from "@/lib/formatters";
import type { Persona, PersonaUpdate, Documento } from "@/types";

const getTipoDocInfo = (tipo?: string | null) => {
  const t = (tipo || "CEDULA_CIUDADANIA").toUpperCase();
  if (t.includes("CONTRA") || t.includes("COMPROBANTE") || t === "CT") {
    return {
      codigo: "CT",
      label: "Contraseña",
      badge: "bg-teal-500/20 border-teal-500/40 text-teal-300 font-bold",
      pill: "bg-teal-500/20 text-teal-300 border-teal-500/40",
    };
  }
  if (t.includes("TARJETA") || t === "TI") {
    return {
      codigo: "TI",
      label: "Tarjeta de Identidad",
      badge: "bg-purple-500/20 border-purple-500/40 text-purple-300 font-bold",
      pill: "bg-purple-500/20 text-purple-300 border-purple-500/40",
    };
  }
  if (t.includes("EXTRANJERIA") || t === "CE") {
    return {
      codigo: "CE",
      label: "Cédula Extranjería",
      badge: "bg-amber-500/20 border-amber-500/40 text-amber-300 font-bold",
      pill: "bg-amber-500/20 text-amber-300 border-amber-500/40",
    };
  }
  if (t.includes("PASAPORTE") || t === "PAS") {
    return {
      codigo: "PAS",
      label: "Pasaporte",
      badge: "bg-emerald-500/20 border-emerald-500/40 text-emerald-300 font-bold",
      pill: "bg-emerald-500/20 text-emerald-300 border-emerald-500/40",
    };
  }
  return {
    codigo: "CC",
    label: "Cédula de Ciudadanía",
    badge: "bg-sky-500/20 border-sky-500/40 text-sky-300 font-bold",
    pill: "bg-sky-500/20 text-sky-300 border-sky-500/40",
  };
};

export default function PersonasPage() {
  const router = useRouter();
  const pathname = usePathname();
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [documentos, setDocumentos] = useState<Documento[]>([]);
  const [filtroDocumento, setFiltroDocumento] = useState<string>("todos");
  const [seleccionados, setSeleccionados] = useState<Set<string>>(new Set());
  const [exportando, setExportando] = useState(false);
  const [cargando, setCargando] = useState(true);
  const [buscar, setBuscar] = useState("");
  type FiltroEstado = "todos" | "validas" | "revision" | "discrepancia" | "falta_pdf" | "falta_excel";
  const [filtroEstado, setFiltroEstado] = useState<FiltroEstado>("todos");
  const soloRevision = filtroEstado === "revision";
  const [editando, setEditando] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<PersonaUpdate>({});
  const [stats, setStats] = useState({
    total: 0,
    validas: 0,
    revision: 0,
    discrepancia: 0,
    faltaPdf: 0,
    faltaExcel: 0,
  });

  // Acordeón: solo una fila expandida a la vez
  const [expandidoId, setExpandidoId] = useState<string | null>(null);
  const [paginaPrevia, setPaginaPrevia] = useState<number>(1);
  const [imgCargando, setImgCargando] = useState(false);
  const [imgError, setImgError] = useState(false);
  const [zoom, setZoom] = useState(1);
  const [subiendoPdfId, setSubiendoPdfId] = useState<string | null>(null);
  const [personaParaPdf, setPersonaParaPdf] = useState<Persona | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!auth.isAuthenticated()) { router.push("/"); return; }
    cargarDocumentos();
    cargarPersonas(true);
    const interval = setInterval(() => cargarPersonas(false), 4000);
    return () => clearInterval(interval);
  }, [pathname, filtroDocumento]);

  const cargarDocumentos = async () => {
    try {
      const res = await apiDocumentos.listar({ limit: 100 });
      setDocumentos(Array.isArray(res.data) ? res.data : []);
    } catch {
      // Ignorar
    }
  };

  const cargarPersonas = async (mostrarSpinner = false) => {
    if (mostrarSpinner) setCargando(true);
    try {
      const docIdFiltro = filtroDocumento !== "todos" ? filtroDocumento : undefined;
      const [resPersonas, resStats] = await Promise.all([
        apiPersonas.listar({
          limit: 300,
          buscar: buscar || undefined,
          documento_id: docIdFiltro,
        }),
        apiDocumentos.estadisticas(docIdFiltro).catch(() => null),
      ]);

      const items: Persona[] = Array.isArray(resPersonas.data) ? resPersonas.data : (((resPersonas.data as any)?.items) || []);
      setPersonas(items);

      const tot = docIdFiltro ? (resStats?.data?.total_personas ?? items.length) : (resStats?.data?.total_personas || items.length);
      const revCount = items.filter((p: Persona) => p.requiere_revision || (p.estado_registro && p.estado_registro !== "VALID")).length;
      const faltaPdfCount = items.filter((p: Persona) => !p.documento_id || p.en_pdf === false).length;
      const faltaExcelCount = items.filter((p: Persona) => p.en_excel === false).length;
      const discCount = items.filter((p: Persona) => (!p.documento_id || p.en_pdf === false) || p.en_excel === false).length;
      const valCount = items.filter((p: Persona) => !p.requiere_revision && (!p.estado_registro || p.estado_registro === "VALID") && p.documento_id && p.en_excel !== false).length;

      setStats({
        total: tot,
        revision: revCount,
        validas: valCount,
        discrepancia: discCount,
        faltaPdf: faltaPdfCount,
        faltaExcel: faltaExcelCount,
      });

      if (mostrarSpinner) toast.success(`${items.length} persona(s) sincronizada(s)`);
    } catch (err) {
      console.error("Error al cargar personas:", err);
      if (mostrarSpinner) toast.error("Error al cargar la lista de personas");
    } finally {
      if (mostrarSpinner) setCargando(false);
    }
  };

  const abrirSubirPdf = (p: Persona) => {
    setPersonaParaPdf(p);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
      fileInputRef.current.click();
    }
  };

  const manejarArchivoPdf = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !personaParaPdf) return;

    if (!file.name.toLowerCase().endsWith(".pdf")) {
      toast.error("Solo se permiten archivos en formato PDF.");
      return;
    }

    const targetPersona = personaParaPdf;
    setSubiendoPdfId(targetPersona.id);
    const toastId = toast.loading(`Procesando PDF con OCR para ${targetPersona.numero_identificacion}...`);

    try {
      const res = await apiPersonas.subirPdfCedula(targetPersona.id, file);
      const personaActualizada = res.data;
      setPersonas((prev) =>
        prev.map((p) => (p.id === personaActualizada.id ? personaActualizada : p))
      );
      toast.success(
        `¡Datos extraídos exitosamente para ${personaActualizada.numero_identificacion}!`,
        { id: toastId }
      );

      if (expandidoId === targetPersona.id) {
        setPaginaPrevia(personaActualizada.pagina_frente || 1);
        setImgCargando(true);
        setImgError(false);
      }
    } catch (err: unknown) {
      const msg = getErrorMessage(err, "Error al procesar el PDF de la cédula");
      toast.error(msg, { id: toastId });
    } finally {
      setSubiendoPdfId(null);
      setPersonaParaPdf(null);
    }
  };

  const toggleExpandir = (p: Persona) => {
    if (expandidoId === p.id) {
      setExpandidoId(null);
      setEditando(null);
    } else {
      setExpandidoId(p.id);
      setEditando(null);
      const paginaInicial = p.pagina_frente || p.pagina_numero || 1;
      setPaginaPrevia(paginaInicial);
      setImgCargando(true);
      setImgError(false);
      setZoom(1);
    }
  };

  const iniciarEdicion = (p: Persona) => {
    setEditando(p.id);
    if (expandidoId !== p.id) {
      setExpandidoId(p.id);
      const paginaInicial = p.pagina_frente || p.pagina_numero || 1;
      setPaginaPrevia(paginaInicial);
      setImgCargando(true);
      setImgError(false);
      setZoom(1);
    }
    const nomCompleto = formatNombreCompleto(p);
    setEditForm({
      numero_identificacion: p.numero_identificacion || "",
      tipo_documento: p.tipo_documento || "CEDULA_CIUDADANIA",
      nombre_completo: nomCompleto,
      nombres: p.nombres || "",
      apellidos: p.apellidos || "",
      fecha_nacimiento: p.fecha_nacimiento ? String(p.fecha_nacimiento) : "",
      requiere_revision: undefined,
    });
  };

  const guardarEdicion = async (id: string, forzarAprobado = false) => {
    try {
      const payload: PersonaUpdate = {
        ...editForm,
        ...(forzarAprobado ? { requiere_revision: false } : {}),
      };
      await apiPersonas.actualizar(id, payload);
      toast.success(forzarAprobado ? "Datos guardados y persona validada" : "Datos actualizados correctamente");
      setEditando(null);
      cargarPersonas(true);
    } catch {
      toast.error("Error guardando cambios");
    }
  };

  const eliminar = async (id: string, cedula: string) => {
    if (!confirm(`¿Desea eliminar el registro de la persona con cédula ${cedula}?`)) return;
    try {
      await apiPersonas.eliminar(id);
      toast.success("Registro eliminado");
      if (expandidoId === id) setExpandidoId(null);
      cargarPersonas(true);
    } catch {
      toast.error("Error al eliminar registro");
    }
  };

  const aprobarRevision = async (id: string, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    try {
      await apiPersonas.actualizar(id, { requiere_revision: false });
      toast.success("Persona aprobada como válida");
      cargarPersonas(true);
    } catch {
      toast.error("Error al aprobar persona");
    }
  };

  // Filtrado local por estado y cédula / nombre
  const personasFiltradas = (personas || []).filter((p) => {
    if (!p) return false;
    if (filtroEstado === "revision") {
      const esRev = Boolean(p.requiere_revision || (p.estado_registro && p.estado_registro !== "VALID"));
      if (!esRev) return false;
    } else if (filtroEstado === "validas") {
      const esRev = Boolean(p.requiere_revision || (p.estado_registro && p.estado_registro !== "VALID"));
      const faltaPdf = !p.documento_id || p.en_pdf === false;
      const faltaExcel = p.en_excel === false;
      if (esRev || faltaPdf || faltaExcel) return false;
    } else if (filtroEstado === "discrepancia") {
      const faltaPdf = !p.documento_id || p.en_pdf === false;
      const faltaExcel = p.en_excel === false;
      if (!faltaPdf && !faltaExcel) return false;
    } else if (filtroEstado === "falta_pdf") {
      const faltaPdf = !p.documento_id || p.en_pdf === false;
      if (!faltaPdf) return false;
    } else if (filtroEstado === "falta_excel") {
      const faltaExcel = p.en_excel === false;
      if (!faltaExcel) return false;
    }

    if (!buscar) return true;
    const q = buscar.toLowerCase().trim().replace(/[.\s]/g, "");
    const cedula = String(p.numero_identificacion || "").replace(/[.\s]/g, "");
    const nom = formatNombreCompleto(p).toLowerCase();
    return (
      cedula.includes(q) ||
      nom.includes(q)
    );
  });

  // Manejo de selección múltiple
  const toggleSeleccionarTodasVisibles = () => {
    const todosVisiblesSeleccionados =
      personasFiltradas.length > 0 &&
      personasFiltradas.every((p) => seleccionados.has(p.id));

    if (todosVisiblesSeleccionados) {
      setSeleccionados((prev) => {
        const next = new Set(prev);
        personasFiltradas.forEach((p) => next.delete(p.id));
        return next;
      });
    } else {
      setSeleccionados((prev) => {
        const next = new Set(prev);
        personasFiltradas.forEach((p) => next.add(p.id));
        return next;
      });
    }
  };

  const toggleSeleccionPersona = (id: string) => {
    setSeleccionados((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const exportarSeleccion = async () => {
    if (seleccionados.size === 0) {
      toast.error("Selecciona al menos una persona para exportar");
      return;
    }
    setExportando(true);
    try {
      const docId = filtroDocumento !== "todos" ? filtroDocumento : undefined;
      await apiExportacion.descargarXlsx({
        documentoId: docId,
        personaIds: Array.from(seleccionados),
        requiereRevision: soloRevision ? true : undefined,
      });
      toast.success(`${seleccionados.size} persona(s) exportada(s) a Excel`);
    } catch {
      toast.error("Error al exportar personas a Excel");
    } finally {
      setExportando(false);
    }
  };

  const exportarVistaActual = async () => {
    setExportando(true);
    try {
      const docId = filtroDocumento !== "todos" ? filtroDocumento : undefined;
      await apiExportacion.descargarXlsx({
        documentoId: docId,
        requiereRevision: soloRevision ? true : undefined,
      });
      toast.success("Archivo Excel descargado correctamente");
    } catch {
      toast.error("Error al exportar a Excel");
    } finally {
      setExportando(false);
    }
  };

  // ─── Panel de detalle inline (acordeón) ───────────────────────────────────
  const renderPanelDetalle = (p: Persona) => {
    const docId = p.documento_id ? String(p.documento_id) : null;
    const tieneDosLados = !!(p.pagina_frente && p.pagina_reverso);
    const estaEditando = editando === p.id;

    const nomCompleto = formatNombreCompleto(p);
    const edadCalculada = p.edad ?? calcularEdad(p.fecha_nacimiento);
    const campos = [
      { key: "numero_identificacion", label: "Número de Identidad", icono: <Hash className="w-3.5 h-3.5" />, valor: p.numero_identificacion },
      { key: "nombre_completo", label: "Nombre Completo", icono: <UserCheck className="w-3.5 h-3.5" />, valor: nomCompleto },
      {
        key: "fecha_nacimiento",
        label: "Fecha de Nacimiento",
        icono: <Calendar className="w-3.5 h-3.5" />,
        valor: p.fecha_nacimiento ? String(p.fecha_nacimiento) : null
      },
      {
        key: "edad",
        label: "Edad Calculada",
        icono: <Clock className="w-3.5 h-3.5" />,
        valor: edadCalculada !== null ? `${edadCalculada} años cumplidos` : null
      },
    ];

    const conf = (key: string): number => {
      const d = p.detalles_campos?.[key] as any;
      if (d?.confidence != null) return Math.round(d.confidence * 100);
      return p.confianza_extraccion != null ? Math.round(Number(p.confianza_extraccion)) : 85;
    };

    const color = (c: number) => {
      if (c >= 85) return { bar: "from-emerald-500 to-emerald-400", badge: "bg-emerald-500/15 border-emerald-500/30 text-emerald-400" };
      if (c >= 65) return { bar: "from-amber-500 to-yellow-400", badge: "bg-amber-500/15 border-amber-500/30 text-amber-400" };
      return { bar: "from-rose-500 to-red-400", badge: "bg-rose-500/15 border-rose-500/30 text-rose-400" };
    };

    return (
      <div className="flex flex-col lg:flex-row gap-0 bg-slate-950/70 border-t border-slate-800/60 w-full min-w-0 overflow-hidden">

        {/* ── Panel izquierdo: PDF / Documento ── */}
        <div className="lg:w-[44%] w-full flex flex-col border-b lg:border-b-0 lg:border-r border-slate-800/50 min-h-[300px] min-w-0 overflow-hidden">
          {/* Toolbar PDF */}
          <div className="flex items-center justify-between px-3 py-1.5 bg-slate-900/70 border-b border-slate-800/40 min-w-0 gap-1">
            <div className="flex items-center gap-1.5 min-w-0">
              <FileText className="w-3.5 h-3.5 text-primary-400 shrink-0" />
              <span className="text-[11px] font-semibold text-slate-300 uppercase tracking-wider shrink-0">Vista Documento</span>
              {p.nombre_documento && (
                <span className="text-[10px] font-mono text-slate-300 truncate max-w-[130px] bg-slate-800 px-1.5 py-0.5 rounded border border-slate-700 ml-1 shrink" title={`Archivo origen: ${p.nombre_documento}`}>
                  {p.nombre_documento}
                </span>
              )}
              {tieneDosLados && (
                <div className="flex items-center gap-1 ml-1.5 shrink-0">
                  <button
                    onClick={() => { setPaginaPrevia(p.pagina_frente!); setImgCargando(true); setImgError(false); }}
                    className={`px-2 py-0.5 rounded text-[10px] font-bold transition-all ${paginaPrevia === p.pagina_frente ? "bg-primary-500/25 border border-primary-500/40 text-primary-300" : "bg-slate-800 border border-slate-700 text-slate-400 hover:text-white"}`}
                  >
                    Frente
                  </button>
                  <button
                    onClick={() => { setPaginaPrevia(p.pagina_reverso!); setImgCargando(true); setImgError(false); }}
                    className={`px-2 py-0.5 rounded text-[10px] font-bold transition-all ${paginaPrevia === p.pagina_reverso ? "bg-primary-500/25 border border-primary-500/40 text-primary-300" : "bg-slate-800 border border-slate-700 text-slate-400 hover:text-white"}`}
                  >
                    Reverso
                  </button>
                </div>
              )}
              {!tieneDosLados && (
                <span className="text-[10px] text-slate-500 ml-1 shrink-0">pág. {paginaPrevia}</span>
              )}
            </div>
            <div className="flex items-center gap-0.5 shrink-0">
              <button onClick={() => setZoom(z => Math.max(0.5, z - 0.25))} className="p-1 rounded text-slate-500 hover:text-white hover:bg-slate-800 transition-colors" title="Alejar"><ZoomOut className="w-3 h-3" /></button>
              <span className="text-[10px] font-mono text-slate-400 w-8 text-center">{Math.round(zoom * 100)}%</span>
              <button onClick={() => setZoom(z => Math.min(2.5, z + 0.25))} className="p-1 rounded text-slate-500 hover:text-white hover:bg-slate-800 transition-colors" title="Acercar"><ZoomIn className="w-3 h-3" /></button>
              <button onClick={() => setZoom(1)} className="p-1 rounded text-slate-500 hover:text-white hover:bg-slate-800 transition-colors" title="Restablecer"><RotateCw className="w-3 h-3" /></button>
            </div>
          </div>

          {/* Imagen */}
          <div className="flex-1 overflow-auto flex items-start justify-center p-3 bg-slate-950/50 min-h-[260px] max-h-[480px]">
            {!docId ? (
              <div className="flex flex-col items-center justify-center gap-3 h-full w-full py-8 text-center">
                <ImageOff className="w-8 h-8 text-slate-700" />
                <p className="text-xs text-slate-500">Sin documento PDF asociado</p>
                <button
                  onClick={() => abrirSubirPdf(p)}
                  disabled={subiendoPdfId === p.id}
                  className="px-3 py-1.5 rounded-lg bg-primary-600/20 hover:bg-primary-600/30 text-primary-300 border border-primary-500/40 text-xs font-semibold flex items-center gap-1.5 transition-all"
                  title="Subir documento PDF de la cédula para extraer datos automáticamente"
                >
                  {subiendoPdfId === p.id ? (
                    <div className="spinner w-3.5 h-3.5" />
                  ) : (
                    <UploadCloud className="w-3.5 h-3.5 text-primary-400" />
                  )}
                  Subir PDF de Cédula
                </button>
              </div>
            ) : imgError ? (
              <div className="flex flex-col items-center justify-center gap-3 h-full w-full py-8 text-center">
                <ImageOff className="w-8 h-8 text-slate-700" />
                <p className="text-xs text-slate-500">PDF no disponible para vista previa</p>
                <button
                  onClick={() => abrirSubirPdf(p)}
                  disabled={subiendoPdfId === p.id}
                  className="px-3 py-1.5 rounded-lg bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-300 border border-indigo-500/40 text-xs font-semibold flex items-center gap-1.5 transition-all"
                  title="Subir nuevo PDF de la cédula"
                >
                  {subiendoPdfId === p.id ? (
                    <div className="spinner w-3.5 h-3.5" />
                  ) : (
                    <UploadCloud className="w-3.5 h-3.5 text-indigo-400" />
                  )}
                  Subir nuevo PDF
                </button>
              </div>
            ) : (
              <div style={{ transform: `scale(${zoom})`, transformOrigin: "top center", transition: "transform 0.2s ease" }}>
                {imgCargando && (
                  <div className="flex flex-col items-center gap-2 py-12 w-48">
                    <div className="w-6 h-6 border-2 border-slate-700 border-t-primary-400 rounded-full animate-spin" />
                    <span className="text-[11px] text-slate-500">Cargando página {paginaPrevia}…</span>
                  </div>
                )}
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  key={`${docId}-${paginaPrevia}`}
                  src={apiDocumentos.paginaPdfUrl(docId, paginaPrevia, 130)}
                  alt={`Página ${paginaPrevia}`}
                  className="rounded-lg shadow-xl max-w-full border border-slate-700/30"
                  style={{ display: imgCargando ? "none" : "block" }}
                  onLoad={() => setImgCargando(false)}
                  onError={() => { setImgCargando(false); setImgError(true); }}
                />
              </div>
            )}
          </div>
        </div>

        {/* ── Panel derecho: Datos OCR o Modo Edición ── */}
        <div className="lg:w-[56%] w-full flex flex-col justify-between min-w-0 overflow-hidden">
          <div>
            {/* Meta info */}
            <div className="px-3 py-2 border-b border-slate-800/40 bg-slate-900/50 flex items-center justify-between flex-wrap gap-1.5 min-w-0">
              <div className="flex items-center gap-2 text-[10px] flex-wrap min-w-0">
                <span className={`px-2 py-0.5 rounded text-[10px] border font-bold shrink-0 ${getTipoDocInfo(p.tipo_documento).pill}`}>
                  {getTipoDocInfo(p.tipo_documento).label} ({getTipoDocInfo(p.tipo_documento).codigo})
                </span>
                {p.nombre_documento && (
                  <span className="flex items-center gap-1 text-slate-300 font-mono text-[10px] bg-primary-500/10 border border-primary-500/30 px-2 py-0.5 rounded max-w-[180px] shrink" title={`Archivo PDF origen: ${p.nombre_documento}`}>
                    <FileText className="w-3 h-3 text-primary-400 shrink-0" />
                    <span className="text-primary-400 font-semibold shrink-0">PDF:</span>
                    <span className="truncate">{p.nombre_documento}</span>
                  </span>
                )}
                <span className="flex items-center gap-1 text-slate-500 shrink-0"><Cpu className="w-3 h-3" /> <span className="text-emerald-400 font-mono">{p.motor_ocr || "google_document_ai"}</span></span>
                <span className="flex items-center gap-1 text-slate-500 shrink-0"><Clock className="w-3 h-3" /> <span className="text-slate-400">{p.fecha_registro ? new Date(p.fecha_registro).toLocaleDateString("es-CO") : "—"}</span></span>
                {edadCalculada !== null && (
                  <span className="flex items-center gap-1 text-amber-300 font-mono text-[10px] bg-amber-500/10 border border-amber-500/30 px-2 py-0.5 rounded font-semibold shrink-0" title={`Edad: ${edadCalculada} años cumplidos`}>
                    <span> {edadCalculada} años</span>
                  </span>
                )}
              </div>
              {estaEditando ? (
                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/40 flex items-center gap-1 shrink-0">
                  <Edit3 className="w-3 h-3" /> Modo Edición
                </span>
              ) : (
                p.grupo_documento_id && <span className="font-mono text-[10px] text-slate-600 truncate max-w-[90px] shrink-0">{p.grupo_documento_id}</span>
              )}
            </div>

            {/* Alerta: Falta en Planilla Excel */}
            {p.en_excel === false && (
              <div className="m-2.5 p-2.5 rounded-xl bg-purple-500/10 border border-purple-500/30 text-purple-300 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <FileSpreadsheet className="w-4 h-4 text-purple-400 shrink-0" />
                  <span className="text-xs font-bold uppercase tracking-wider text-purple-400">
                    Alerta: No se encuentra en la Planilla Excel
                  </span>
                </div>
                <p className="text-xs text-purple-200/90 ml-6 break-words">
                  El número de identificación <strong className="font-mono text-white">{p.numero_identificacion}</strong> no figura en la planilla oficial de Excel cargada para comparación.
                </p>
              </div>
            )}

            {/* Alerta: Sin Documento PDF */}
            {(!p.documento_id || p.en_pdf === false) && (
              <div className="m-2.5 p-2.5 rounded-xl bg-sky-500/10 border border-sky-500/30 text-sky-300 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <FileText className="w-4 h-4 text-sky-400 shrink-0" />
                  <span className="text-xs font-bold uppercase tracking-wider text-sky-400">
                    Alerta: Sin Documento PDF Asociado
                  </span>
                </div>
                <p className="text-xs text-sky-200/90 ml-6 break-words">
                  Este registro fue creado manualmente o desde Excel y no cuenta con un archivo PDF vinculado. Puede subirlo con el botón &quot;Subir PDF Cédula&quot;.
                </p>
              </div>
            )}

            {/* Motivos de Revisión / Alerta para Asistente */}
            {Boolean(p.requiere_revision || (p.estado_registro && p.estado_registro !== "VALID")) && (() => {
              const rawMotivos: string[] = Array.isArray((p.detalles_campos as any)?.motivos_revision)
                ? (p.detalles_campos as any).motivos_revision
                : [];
              const motivosFiltrados = rawMotivos.filter((m: string) => {
                const ml = m.toLowerCase();
                return !ml.includes("expedici") && !ml.includes("sexo") && !ml.includes("lugar");
              });
              if (motivosFiltrados.length === 0 && !p.requiere_revision) return null;
              return (
                <div className="m-2.5 p-2.5 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-300 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
                    <span className="text-xs font-bold uppercase tracking-wider text-amber-400">
                      Pendiente de Revisión por Asistente
                    </span>
                  </div>
                  {motivosFiltrados.length > 0 ? (
                    <ul className="text-xs space-y-1 ml-6 list-disc text-amber-200/90 font-medium">
                      {motivosFiltrados.map((m: string, i: number) => (
                        <li key={i}>{m}</li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-xs text-amber-200/90 ml-6 break-words">
                      Uno o más datos esenciales (número de identificación, nombre o fecha de nacimiento) requieren verificación.
                    </p>
                  )}
                </div>
              );
            })()}

            {/* Contenido: Si está editando muestra el formulario integrado; si no, las tarjetas compactas */}
            {estaEditando ? (
              <div className="p-3 space-y-2.5 min-w-0">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 min-w-0">
                  {/* Tipo de Documento */}
                  <div>
                    <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">
                      Tipo de Documento
                    </label>
                    <select
                      value={editForm.tipo_documento || "CEDULA_CIUDADANIA"}
                      onChange={(e) => setEditForm(prev => ({ ...prev, tipo_documento: e.target.value }))}
                      className="w-full bg-slate-900 border border-slate-700/80 rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-primary-500 transition-colors"
                    >
                      <option value="CEDULA_CIUDADANIA">Cédula de Ciudadanía (CC)</option>
                      <option value="TARJETA_IDENTIDAD">Tarjeta de Identidad (TI)</option>
                      <option value="CEDULA_EXTRANJERIA">Cédula de Extranjería (CE)</option>
                      <option value="CONTRASENA">Contraseña / Trámite (CT)</option>
                      <option value="PASAPORTE">Pasaporte (PAS)</option>
                    </select>
                  </div>

                  {/* Número de Cédula */}
                  <div>
                    <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">
                      Número de Identificación
                    </label>
                    <div className="relative">
                      <Hash className="w-3.5 h-3.5 text-slate-500 absolute left-2.5 top-2" />
                      <input
                        type="text"
                        value={editForm.numero_identificacion || ""}
                        onChange={(e) => setEditForm(prev => ({ ...prev, numero_identificacion: e.target.value }))}
                        placeholder="Ej: 1117513499"
                        className="w-full bg-slate-900 border border-slate-700/80 rounded-lg pl-8 pr-3 py-1.5 text-xs font-mono font-bold text-primary-300 focus:outline-none focus:border-primary-500 transition-colors"
                      />
                    </div>
                  </div>

                  {/* Nombre Completo */}
                  <div className="sm:col-span-2">
                    <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">
                      Nombre Completo (Nombres y Apellidos)
                    </label>
                    <input
                      type="text"
                      value={editForm.nombre_completo || ""}
                      onChange={(e) => {
                        const val = e.target.value;
                        setEditForm(prev => ({
                          ...prev,
                          nombre_completo: val,
                          nombres: val,
                          apellidos: ""
                        }));
                      }}
                      placeholder="Ej: VALENCIA VILLEGAS ANTONIO"
                      className="w-full bg-slate-900 border border-slate-700/80 rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-primary-500 transition-colors uppercase font-medium"
                    />
                  </div>

                  {/* Fecha de Nacimiento */}
                  <div>
                    <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">
                      Fecha de Nacimiento (AAAA-MM-DD)
                    </label>
                    <div className="relative">
                      <Calendar className="w-3.5 h-3.5 text-slate-500 absolute left-2.5 top-2" />
                      <input
                        type="text"
                        value={editForm.fecha_nacimiento || ""}
                        onChange={(e) => setEditForm(prev => ({ ...prev, fecha_nacimiento: e.target.value }))}
                        placeholder="AAAA-MM-DD"
                        className="w-full bg-slate-900 border border-slate-700/80 rounded-lg pl-8 pr-3 py-1.5 text-xs text-white focus:outline-none focus:border-primary-500 transition-colors font-mono"
                      />
                    </div>
                  </div>

                  {/* Edad calculada automática */}
                  <div>
                    <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">
                      Edad Calculada
                    </label>
                    <div className="flex items-center gap-2 bg-slate-900/60 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-300">
                      <Clock className="w-3.5 h-3.5 text-amber-400" />
                      {editForm.fecha_nacimiento && calcularEdad(editForm.fecha_nacimiento) !== null ? (
                        <span className="font-bold text-amber-300 font-mono">
                          {calcularEdad(editForm.fecha_nacimiento)} años cumplidos
                        </span>
                      ) : (
                        <span className="text-slate-500 italic text-[11px]">
                          {editForm.fecha_nacimiento ? "Fecha no válida" : "Ingrese fecha para calcular"}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              /* Vista de Tarjetas (Compactas con content-start para evitar que se alarguen) */
              <div className="p-2.5 space-y-2 min-w-0">
                {p.nombre_documento && (
                  <div className="px-2.5 py-1.5 rounded-lg bg-slate-900/80 border border-slate-800 flex items-center justify-between text-xs min-w-0">
                    <div className="flex items-center gap-1.5 min-w-0 flex-1">
                      <FileText className="w-3.5 h-3.5 text-primary-400 shrink-0" />
                      <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider shrink-0">Documento PDF:</span>
                      <span className="font-mono text-xs text-slate-200 truncate" title={p.nombre_documento}>{p.nombre_documento}</span>
                    </div>
                    <span className="text-[10px] font-mono text-slate-500 shrink-0 ml-2">
                      {p.pagina_frente ? `Pág. ${p.pagina_frente}${p.pagina_reverso ? ` / ${p.pagina_reverso}` : ""}` : ""}
                    </span>
                  </div>
                )}
                <div className="grid grid-cols-2 gap-2 content-start min-w-0">
                  {campos.map(({ key, label, icono, valor }) => {
                    const c = conf(key);
                    const col = color(valor ? c : 0);
                    return (
                      <div key={key} className="rounded-lg bg-slate-900/60 border border-slate-800/60 p-2 hover:border-slate-700/80 transition-colors flex flex-col justify-between min-h-[58px] min-w-0 overflow-hidden">
                        <div className="flex items-center justify-between min-w-0">
                          <div className="flex items-center gap-1 text-slate-500 min-w-0">
                            {icono}
                            <span className="text-[10px] font-bold uppercase tracking-wider truncate">{label}</span>
                          </div>
                          <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold border shrink-0 ${valor ? col.badge : "bg-rose-500/10 border-rose-500/20 text-rose-400"}`}>
                            {valor ? `${c}%` : "N/D"}
                          </span>
                        </div>
                        <div className="my-0.5 min-w-0">
                          {valor
                            ? (
                              <div className="min-w-0">
                                <span className="text-xs font-semibold text-white truncate block font-mono" title={valor}>{valor}</span>
                                {key === "numero_identificacion" && (p.detalles_campos as any)?.numero_identificacion_original_ocr && (
                                  <span className="text-[9px] text-emerald-400 font-medium flex items-center gap-1 mt-0.5 truncate" title={`Corregido desde planilla oficial Excel (OCR leyó: ${(p.detalles_campos as any).numero_identificacion_original_ocr})`}>
                                    <CheckCircle className="w-2.5 h-2.5 shrink-0" />
                                    <span className="truncate">Corregido de {(p.detalles_campos as any).numero_identificacion_original_ocr}</span>
                                  </span>
                                )}
                              </div>
                            )
                            : <span className="text-[11px] italic text-rose-400/80 font-medium block truncate">No detectado por OCR</span>
                          }
                        </div>
                        {valor ? (
                          <div className="h-1 bg-slate-800 rounded-full overflow-hidden">
                            <div className={`h-full bg-gradient-to-r ${col.bar} rounded-full transition-all duration-700`} style={{ width: `${c}%` }} />
                          </div>
                        ) : (
                          <div className="h-1 bg-rose-950/30 rounded-full overflow-hidden">
                            <div className="h-full bg-rose-500/40 rounded-full w-full" />
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>

          {/* Acciones del Panel */}
          <div className="px-3 py-2 border-t border-slate-800/40 bg-slate-900/50 flex flex-wrap items-center justify-between gap-1.5 mt-auto min-w-0">
            {estaEditando ? (
              <div className="flex flex-wrap items-center justify-between gap-1.5 w-full">
                <div className="flex items-center gap-1.5 flex-wrap">
                  <button
                    onClick={() => guardarEdicion(p.id, false)}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary-600 hover:bg-primary-500 text-white text-xs font-semibold shadow-lg shadow-primary-500/20 transition-all shrink-0"
                  >
                    <Save className="w-3.5 h-3.5" /> Guardar Cambios
                  </button>
                  {Boolean(p.requiere_revision || (p.estado_registro && p.estado_registro !== "VALID")) && (
                    <button
                      onClick={() => guardarEdicion(p.id, true)}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-500/20 hover:bg-emerald-500/30 border border-emerald-500/40 text-emerald-300 text-xs font-semibold transition-all shrink-0"
                      title="Guardar datos y aprobar directamente"
                    >
                      <CheckCircle className="w-3.5 h-3.5" /> Guardar y Aprobar
                    </button>
                  )}
                </div>
                <button
                  onClick={() => setEditando(null)}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 text-xs font-semibold transition-all shrink-0 ml-auto"
                >
                  <X className="w-3.5 h-3.5" /> Cancelar
                </button>
              </div>
            ) : (
              <div className="flex flex-wrap items-center justify-between gap-1.5 w-full">
                <div className="flex flex-wrap items-center gap-1.5">
                  <button
                    onClick={() => iniciarEdicion(p)}
                    className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-primary-600/20 hover:bg-primary-600/30 border border-primary-500/40 text-primary-300 text-xs font-semibold transition-all shrink-0"
                  >
                    <Edit3 className="w-3.5 h-3.5" /> Editar Datos
                  </button>
                  <button
                    onClick={() => abrirSubirPdf(p)}
                    disabled={subiendoPdfId === p.id}
                    className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-indigo-500/20 hover:bg-indigo-500/30 border border-indigo-500/40 text-indigo-300 text-xs font-semibold transition-all shrink-0"
                    title="Subir documento PDF de la cédula para extraer datos automáticamente con OCR"
                  >
                    {subiendoPdfId === p.id ? (
                      <div className="spinner w-3.5 h-3.5" />
                    ) : (
                      <UploadCloud className="w-3.5 h-3.5 text-indigo-400" />
                    )}
                    Subir PDF Cédula
                  </button>
                  {Boolean(p.requiere_revision || (p.estado_registro && p.estado_registro !== "VALID")) && (
                    <button
                      onClick={(e) => aprobarRevision(p.id, e)}
                      className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-emerald-500/20 hover:bg-emerald-500/30 border border-emerald-500/40 text-emerald-300 text-xs font-semibold transition-all shrink-0"
                      title="Aprobar datos y marcar como válido"
                    >
                      <CheckCircle className="w-3.5 h-3.5" /> Aprobar y Validar
                    </button>
                  )}
                </div>
                <button
                  onClick={() => setExpandidoId(null)}
                  className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-slate-800/50 hover:bg-slate-800 border border-slate-700/40 text-slate-400 text-xs font-medium transition-all shrink-0 ml-auto"
                >
                  <ChevronUp className="w-3.5 h-3.5" /> Colapsar
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    );
  };

  // ─── Render ───────────────────────────────────────────────────────────────
  return (
    <div className="flex min-h-screen bg-[#0b0f19] text-slate-100 font-sans w-full max-w-full overflow-x-hidden">
      <Sidebar />

      <main className="ml-64 flex-1 min-w-0 p-4 lg:p-6 overflow-x-hidden max-w-[calc(100vw-16rem)]">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
          <div>
            <div className="flex items-center gap-2 mb-1.5">
              <span className="p-1.5 rounded-lg bg-primary-500/10 border border-primary-500/20 text-primary-400">
                <Users className="w-4 h-4" />
              </span>
              <span className="text-xs font-semibold text-primary-400 uppercase tracking-wider">Base de Datos OCR</span>
            </div>
            <h1 className="text-3xl font-extrabold text-white tracking-tight">Personas Registradas</h1>
            <p className="text-slate-400 text-sm mt-1">
              Haz clic en el ícono <Eye className="inline w-3.5 h-3.5 text-primary-400 mx-1" /> para expandir el documento y los datos OCR de cada persona.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={exportarVistaActual}
              disabled={exportando || personas.length === 0}
              className="flex items-center gap-2 px-3.5 py-2 rounded-xl bg-emerald-500/15 hover:bg-emerald-500/25 border border-emerald-500/30 text-xs font-bold text-emerald-300 transition-all shadow-lg shadow-emerald-500/5 disabled:opacity-50 cursor-pointer"
              title="Exportar registros a Excel (.xlsx)"
            >
              <Download className="w-3.5 h-3.5 text-emerald-400" />
              <span>Exportar a Excel</span>
            </button>
            <span className="px-4 py-2 rounded-xl bg-gradient-to-r from-primary-500/20 to-blue-500/20 border border-primary-500/30 text-sm font-semibold text-primary-300 shadow-lg shadow-primary-500/5">
              {filtroDocumento !== "todos" ? "Total archivo:" : "Total:"} <strong className="text-white font-extrabold text-base ml-1">{stats.total}</strong> {stats.total === 1 ? "persona" : "personas"}
            </span>
          </div>
        </div>

        {/* Tarjetas de Estadísticas / Conteo Rápido Interactivas (4 estados) */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          {/* Card 1: Total General o por Archivo */}
          <div
            onClick={() => setFiltroEstado("todos")}
            className={`cursor-pointer bg-slate-900/80 border rounded-2xl p-4 flex items-center justify-between backdrop-blur-md shadow-lg transition-all ${filtroEstado === "todos" ? "border-primary-500/60 ring-2 ring-primary-500/30 bg-primary-500/10" : "border-slate-800/80 hover:border-slate-700"}`}
            title={filtroDocumento !== "todos" ? "Mostrar todas las personas de este archivo" : "Mostrar todas las personas registradas"}
          >
            <div>
              <p className="text-xs font-medium text-slate-400 uppercase tracking-wider">
                {filtroDocumento !== "todos" ? "Total Archivo" : "Total Registradas"}
              </p>
              <div className="flex items-baseline gap-2 mt-1">
                <span className="text-2xl font-black text-white">{stats.total}</span>
                <span className="text-xs text-slate-500">
                  {filtroDocumento !== "todos" ? "en archivo" : "en sistema"}
                </span>
              </div>
            </div>
            <div className="w-12 h-12 rounded-xl bg-primary-500/15 border border-primary-500/30 flex items-center justify-center text-primary-400">
              <Users className="w-6 h-6" />
            </div>
          </div>

          {/* Card 2: Válidas */}
          <div
            onClick={() => setFiltroEstado(filtroEstado === "validas" ? "todos" : "validas")}
            className={`cursor-pointer bg-slate-900/80 border rounded-2xl p-4 flex items-center justify-between backdrop-blur-md shadow-lg transition-all ${filtroEstado === "validas" ? "border-emerald-500/70 ring-2 ring-emerald-500/40 bg-emerald-500/10" : "border-slate-800/80 hover:border-emerald-500/40"}`}
            title="Clic para ver solo personas con datos válidos y presentes"
          >
            <div>
              <div className="flex items-center gap-1.5">
                <p className="text-xs font-medium text-emerald-400/90 uppercase tracking-wider">Válidos</p>
                {filtroEstado === "validas" && (
                  <span className="px-1.5 py-0.2 rounded text-[9px] font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">
                    Activo
                  </span>
                )}
              </div>
              <div className="flex items-baseline gap-2 mt-1">
                <span className="text-2xl font-black text-emerald-400">{stats.validas}</span>
                <span className="text-xs text-slate-500">completos</span>
              </div>
            </div>
            <div className="w-12 h-12 rounded-xl bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center text-emerald-400">
              <CheckCircle className="w-6 h-6" />
            </div>
          </div>

          {/* Card 3: Por Revisar */}
          <div
            onClick={() => setFiltroEstado(filtroEstado === "revision" ? "todos" : "revision")}
            className={`cursor-pointer bg-slate-900/80 border rounded-2xl p-4 flex items-center justify-between backdrop-blur-md shadow-lg transition-all ${filtroEstado === "revision" ? "border-amber-500/70 ring-2 ring-amber-500/40 bg-amber-500/10" : "border-slate-800/80 hover:border-amber-500/40"}`}
            title="Clic para ver personas con datos incompletos pendientes de revisión"
          >
            <div>
              <div className="flex items-center gap-1.5">
                <p className="text-xs font-medium text-amber-400/90 uppercase tracking-wider">Por Revisar</p>
                {filtroEstado === "revision" && (
                  <span className="px-1.5 py-0.2 rounded text-[9px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/40 animate-pulse">
                    Activo
                  </span>
                )}
              </div>
              <div className="flex items-baseline gap-2 mt-1">
                <span className="text-2xl font-black text-amber-400">{stats.revision}</span>
                <span className="text-xs text-slate-500">incompletos</span>
              </div>
            </div>
            <div className="w-12 h-12 rounded-xl bg-amber-500/15 border border-amber-500/30 flex items-center justify-center text-amber-400">
              <AlertTriangle className="w-6 h-6" />
            </div>
          </div>

          {/* Card 4: Falta en PDF o Excel */}
          <div
            onClick={() => setFiltroEstado(filtroEstado === "discrepancia" ? "todos" : "discrepancia")}
            className={`cursor-pointer bg-slate-900/80 border rounded-2xl p-4 flex items-center justify-between backdrop-blur-md shadow-lg transition-all ${filtroEstado === "discrepancia" || filtroEstado === "falta_pdf" || filtroEstado === "falta_excel" ? "border-purple-500/70 ring-2 ring-purple-500/40 bg-purple-500/10" : "border-slate-800/80 hover:border-purple-500/40"}`}
            title="Clic para ver personas que faltan en PDF o en la planilla Excel"
          >
            <div>
              <div className="flex items-center gap-1.5">
                <p className="text-xs font-medium text-purple-400/90 uppercase tracking-wider">Falta PDF / Excel</p>
                {(filtroEstado === "discrepancia" || filtroEstado === "falta_pdf" || filtroEstado === "falta_excel") && (
                  <span className="px-1.5 py-0.2 rounded text-[9px] font-bold bg-purple-500/20 text-purple-300 border border-purple-500/40 animate-pulse">
                    Activo
                  </span>
                )}
              </div>
              <div className="flex items-baseline gap-2 mt-1">
                <span className="text-2xl font-black text-purple-400">{stats.discrepancia}</span>
                <span className="text-xs text-slate-500">faltantes</span>
              </div>
            </div>
            <div className="w-12 h-12 rounded-xl bg-purple-500/15 border border-purple-500/30 flex items-center justify-center text-purple-400">
              <AlertCircle className="w-6 h-6" />
            </div>
          </div>
        </div>

        {/* Barra de Búsqueda y Filtros */}
        <div className="grid grid-cols-1 md:grid-cols-12 gap-3 mb-6">
          {/* Búsqueda unificada por cédula, nombres o apellidos */}
          <div className="md:col-span-5 relative">
            <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <input
              id="buscar-persona"
              type="text"
              inputMode="search"
              value={buscar}
              onChange={(e) => setBuscar(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && cargarPersonas(true)}
              placeholder="Buscar por número de cédula o nombre y apellidos..."
              className="w-full pl-10 pr-10 py-2.5 bg-slate-900/90 border border-slate-800 rounded-xl text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-primary-500/60 focus:ring-1 focus:ring-primary-500/50 transition-all shadow-sm font-mono sm:font-sans"
            />
            {buscar && (
              <button
                onClick={() => { setBuscar(""); cargarPersonas(true); }}
                className="absolute right-3 top-1/2 -translate-y-1/2 p-0.5 rounded text-slate-500 hover:text-white transition-colors"
                title="Limpiar búsqueda"
              >
                <X className="w-4 h-4" />
              </button>
            )}
          </div>

          {/* Selector de Documento PDF */}
          <div className="md:col-span-3 relative">
            <FileText className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-primary-400 pointer-events-none" />
            <select
              value={filtroDocumento}
              onChange={(e) => {
                setFiltroDocumento(e.target.value);
                setSeleccionados(new Set());
              }}
              className="w-full pl-9 pr-3 py-2.5 bg-slate-900/90 border border-slate-800 rounded-xl text-xs text-slate-200 focus:outline-none focus:border-primary-500/60 font-medium truncate cursor-pointer shadow-sm"
              title="Filtrar por archivo PDF de origen"
            >
              <option value="todos">📄 Todos los PDFs ({documentos.length})</option>
              {documentos.map((d) => (
                <option key={d.id} value={d.id}>
                  📄 {d.nombre_original}
                </option>
              ))}
            </select>
          </div>

          {/* Selector de Estado */}
          <div className="md:col-span-3 relative">
            <select
              value={filtroEstado}
              onChange={(e) => setFiltroEstado(e.target.value as FiltroEstado)}
              className={`w-full py-2.5 px-3 bg-slate-900/90 border rounded-xl text-xs font-medium cursor-pointer shadow-sm transition-all ${
                filtroEstado === "revision"
                  ? "border-amber-500/60 text-amber-300 bg-amber-500/10"
                  : filtroEstado === "validas"
                  ? "border-emerald-500/60 text-emerald-300 bg-emerald-500/10"
                  : filtroEstado === "discrepancia" || filtroEstado === "falta_pdf" || filtroEstado === "falta_excel"
                  ? "border-purple-500/60 text-purple-300 bg-purple-500/10"
                  : "border-slate-800 text-slate-200"
              }`}
              title="Filtrar por estado del registro"
            >
              <option value="todos">📋 Todos los estados ({stats.total})</option>
              <option value="validas">✅ Solo Válidos ({stats.validas})</option>
              <option value="revision">⚠️ Por Revisar ({stats.revision})</option>
              <option value="discrepancia">🟣 Falta PDF o Excel ({stats.discrepancia})</option>
              <option value="falta_pdf">📄 Solo Falta en PDF ({stats.faltaPdf})</option>
              <option value="falta_excel">📊 Solo Falta en Excel ({stats.faltaExcel})</option>
            </select>
          </div>

          {/* Recargar */}
          <div className="md:col-span-1 flex justify-end">
            <button
              onClick={() => cargarPersonas(true)}
              className="w-full flex items-center justify-center gap-1.5 px-3 py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700/60 rounded-xl text-xs font-semibold transition-all"
              title="Recargar datos"
            >
              <RefreshCw className="w-3.5 h-3.5 text-primary-400" />
            </button>
          </div>
        </div>

        {/* Barra Flotante de Selección y Exportación Múltiple */}
        {seleccionados.size > 0 && (
          <div className="mb-4 p-3.5 bg-gradient-to-r from-primary-950/90 via-slate-900 to-primary-950/90 border border-primary-500/40 rounded-2xl shadow-xl flex flex-wrap items-center justify-between gap-3 animate-in fade-in duration-200">
            <div className="flex items-center gap-2.5">
              <span className="p-1.5 rounded-lg bg-primary-500/20 text-primary-300">
                <CheckSquare className="w-4 h-4" />
              </span>
              <span className="text-sm font-bold text-white">
                {seleccionados.size} {seleccionados.size === 1 ? "persona seleccionada" : "personas seleccionadas"}
              </span>
              {filtroDocumento !== "todos" && (
                <span className="text-xs text-primary-300/80 bg-primary-500/10 px-2 py-0.5 rounded border border-primary-500/20 font-medium">
                  Filtro PDF activo
                </span>
              )}
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={exportarSeleccion}
                disabled={exportando}
                className="btn-primary text-xs py-2 px-4 flex items-center gap-2 shadow-lg shadow-primary-500/20 font-bold"
              >
                {exportando ? (
                  <>
                    <div className="spinner w-3.5 h-3.5" />
                    <span>Generando Excel...</span>
                  </>
                ) : (
                  <>
                    <Download className="w-3.5 h-3.5" />
                    <span>Exportar selección (.xlsx)</span>
                  </>
                )}
              </button>

              <button
                onClick={() => setSeleccionados(new Set())}
                className="px-3 py-2 bg-slate-800/80 hover:bg-slate-700 text-slate-300 rounded-xl text-xs font-semibold border border-slate-700/60 transition-colors"
              >
                Limpiar selección
              </button>
            </div>
          </div>
        )}

        {/* Tabla */}
        <div className="bg-slate-900/80 border border-slate-800/80 rounded-2xl shadow-xl overflow-hidden backdrop-blur-md">
          {cargando ? (
            <div className="p-8 space-y-3">
              {Array(6).fill(0).map((_, i) => (
                <div key={i} className="h-12 bg-slate-800/40 animate-pulse rounded-xl" />
              ))}
            </div>
          ) : personasFiltradas.length === 0 ? (
            <div className="text-center py-20 px-4">
              <div className="w-14 h-14 mx-auto mb-4 rounded-2xl bg-slate-800/60 border border-slate-700/50 flex items-center justify-center text-slate-500">
                <Users className="w-7 h-7" />
              </div>
              <h3 className="text-lg font-semibold text-slate-300">No se encontraron registros</h3>
              <p className="text-slate-500 text-xs mt-1 max-w-sm mx-auto">
                {buscar ? `Sin resultados para "${buscar}"` : "No hay personas registradas."}
              </p>
              {buscar && (
                <button onClick={() => setBuscar("")} className="mt-3 text-xs text-primary-400 hover:underline">
                  Limpiar búsqueda
                </button>
              )}
            </div>
          ) : (
            <div className="overflow-x-auto w-full">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-slate-800/80 bg-slate-950/50 text-[11px] font-bold text-slate-400 uppercase tracking-wider">
                    <th className="py-3 px-2 w-8 text-center">
                      <input
                        type="checkbox"
                        checked={personasFiltradas.length > 0 && personasFiltradas.every((p) => seleccionados.has(p.id))}
                        onChange={toggleSeleccionarTodasVisibles}
                        className="rounded border-slate-700 bg-slate-800 text-primary-500 focus:ring-primary-500/40 cursor-pointer"
                        title="Seleccionar / Deseleccionar todas las personas mostradas"
                      />
                    </th>
                    <th className="py-3 px-1 w-7 text-center"></th>
                    <th className="py-3 px-2 w-32 whitespace-nowrap">Documento / ID</th>
                    <th className="py-3 px-2 whitespace-nowrap">Nombre Completo</th>
                    <th className="py-3 px-1 w-16 text-center whitespace-nowrap">Edad</th>
                    <th className="py-3 px-1 w-12 text-center whitespace-nowrap">Pág.</th>
                    <th className="py-3 px-2 w-28 text-center whitespace-nowrap">Fuente</th>
                    <th className="py-3 px-2 w-28 text-center whitespace-nowrap">Estado</th>
                    <th className="py-3 px-2 w-10 text-center whitespace-nowrap">Acciones</th>
                  </tr>
                </thead>

                <tbody>
                  {personasFiltradas.map((p) => {
                    const estadoStr = p.estado_registro || (p.requiere_revision ? "REVIEW_REQUIRED" : "VALID");
                    const isExpandida = expandidoId === p.id;
                    const isSeleccionada = seleccionados.has(p.id);
                    const nombreCompleto = formatNombreCompleto(p);
                    const edadRow = p.edad ?? calcularEdad(p.fecha_nacimiento);
                    const tipoInfo = getTipoDocInfo(p.tipo_documento);

                    return (
                      <Fragment key={p.id}>
                        {/* ── Fila principal ── */}
                        <tr
                          className={`border-b border-slate-800/30 transition-colors cursor-pointer ${isExpandida
                              ? "bg-slate-800/40 border-primary-500/20"
                              : isSeleccionada
                                ? "bg-primary-500/10 hover:bg-primary-500/15"
                                : "hover:bg-slate-800/20"
                            }`}
                          onClick={() => toggleExpandir(p)}
                        >
                          {/* Checkbox de selección */}
                          <td className="py-3 px-2 w-8 text-center" onClick={(e) => e.stopPropagation()}>
                            <input
                              type="checkbox"
                              checked={isSeleccionada}
                              onChange={() => toggleSeleccionPersona(p.id)}
                              className="rounded border-slate-700 bg-slate-800 text-primary-500 focus:ring-primary-500/40 cursor-pointer"
                            />
                          </td>

                          {/* Toggle expandir */}
                          <td className="py-3 px-1 w-7 text-center">
                            <div className={`w-6 h-6 mx-auto rounded-full flex items-center justify-center transition-all ${isExpandida ? "bg-primary-500/20 border border-primary-500/40 text-primary-300" : "bg-slate-800/60 border border-slate-700/50 text-slate-400"}`}>
                              {isExpandida ? <ChevronUp className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                            </div>
                          </td>

                          {/* Documento e ID con Badge - Compacto y pegado al nombre */}
                          <td className="py-3 px-2 w-32 whitespace-nowrap">
                            <div className="flex items-center gap-1.5 flex-nowrap">
                              <span className={`px-1.5 py-0.5 rounded text-[10px] border font-mono tracking-wider shrink-0 ${tipoInfo.badge}`} title={tipoInfo.label}>
                                {tipoInfo.codigo}
                              </span>
                              <span className="font-mono text-primary-300 font-bold text-sm tracking-wide shrink-0">
                                {p.numero_identificacion}
                              </span>
                              {(p.detalles_campos as any)?.numero_identificacion_original_ocr && (
                                <span className="text-[9px] bg-emerald-500/15 border border-emerald-500/30 text-emerald-300 px-1.5 py-0.5 rounded font-medium flex items-center gap-1 shrink-0 whitespace-nowrap" title={`Número auto-corregido desde planilla Excel oficial (OCR leyó: ${(p.detalles_campos as any).numero_identificacion_original_ocr})`}>
                                  <CheckCircle className="w-2.5 h-2.5" /> Auto-corregido
                                </span>
                              )}
                            </div>
                          </td>

                          {/* Nombre completo */}
                          <td className="py-3 px-2 whitespace-nowrap">
                            {nombreCompleto ? (
                              <span className="text-sm font-semibold text-slate-100 whitespace-nowrap" title={nombreCompleto}>
                                {nombreCompleto}
                              </span>
                            ) : (
                              <span className="text-slate-600 italic text-xs whitespace-nowrap">Sin nombre</span>
                            )}
                          </td>

                          {/* Edad */}
                          <td className="py-3 px-1 w-16 text-center whitespace-nowrap">
                            {edadRow !== null ? (
                              <span className="text-[11px] font-mono px-1.5 py-0.5 rounded-full bg-amber-500/15 border border-amber-500/30 text-amber-300 font-bold whitespace-nowrap">
                                {edadRow} años
                              </span>
                            ) : (
                              <span className="text-slate-600 text-xs">—</span>
                            )}
                          </td>

                          {/* Página */}
                          <td className="py-3 px-1 w-12 text-center whitespace-nowrap">
                            <span className="text-[11px] font-mono text-slate-500 whitespace-nowrap">
                              {p.pagina_frente ? `${p.pagina_frente}${p.pagina_reverso ? `/${p.pagina_reverso}` : ""}` : (p.pagina_numero || "—")}
                            </span>
                          </td>

                          {/* Fuente: PDF y/o Excel */}
                          <td className="py-3 px-2 w-28 text-center whitespace-nowrap">
                            <div className="inline-flex items-center justify-center gap-1 whitespace-nowrap">
                              {/* PDF badge */}
                              {p.documento_id ? (
                                <span
                                  className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-bold bg-blue-500/15 border border-blue-500/30 text-blue-300 whitespace-nowrap shrink-0"
                                  title="Extraído de documento PDF por OCR"
                                >
                                  <FileText className="w-2.5 h-2.5 shrink-0" /> PDF
                                </span>
                              ) : (
                                <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-bold bg-slate-800 border border-slate-700/60 text-slate-500 whitespace-nowrap shrink-0" title="Sin documento PDF asociado">
                                  <FileText className="w-2.5 h-2.5 shrink-0" /> Sin PDF
                                </span>
                              )}
                              {/* Excel badge */}
                              {p.en_excel === true ? (
                                <span
                                  className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-bold bg-emerald-500/15 border border-emerald-500/30 text-emerald-300 whitespace-nowrap shrink-0"
                                  title="Encontrado en planilla Excel comparada"
                                >
                                  <FileSpreadsheet className="w-2.5 h-2.5 shrink-0" /> Excel
                                </span>
                              ) : p.en_excel === false ? (
                                <span
                                  className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-bold bg-rose-500/15 border border-rose-500/30 text-rose-300 whitespace-nowrap shrink-0"
                                  title="No encontrado en ninguna planilla Excel"
                                >
                                  <FileSpreadsheet className="w-2.5 h-2.5 shrink-0" /> No Excel
                                </span>
                              ) : null}
                            </div>
                          </td>

                          {/* Estado: Alertas VÁLIDO, REVISAR, NO EN PDF, NO EN EXCEL */}
                          <td className="py-3 px-2 w-28 text-center whitespace-nowrap">
                            <div className="inline-flex flex-col items-center justify-center gap-1 whitespace-nowrap">
                              {/* Alerta: Falta en PDF */}
                              {(!p.documento_id || p.en_pdf === false) && (
                                <span
                                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-sky-500/15 border border-sky-500/30 text-sky-300 text-[10px] font-bold whitespace-nowrap shadow-sm shadow-sky-500/10"
                                  title="No tiene documento PDF de cédula asociado"
                                >
                                  <FileText className="w-2.5 h-2.5" /> NO EN PDF
                                </span>
                              )}

                              {/* Alerta: Falta en Excel */}
                              {p.en_excel === false && (
                                <span
                                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-purple-500/15 border border-purple-500/30 text-purple-300 text-[10px] font-bold whitespace-nowrap shadow-sm shadow-purple-500/10"
                                  title="No encontrado en la planilla Excel comparada"
                                >
                                  <FileSpreadsheet className="w-2.5 h-2.5" /> NO EN EXCEL
                                </span>
                              )}

                              {/* Estado de validación de datos */}
                              {p.requiere_revision || (p.estado_registro && p.estado_registro !== "VALID") ? (
                                <span
                                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-amber-500/10 border border-amber-500/20 text-amber-400 text-[10px] font-bold whitespace-nowrap shadow-sm shadow-amber-500/10"
                                  title="Requiere revisión manual de datos incompletos"
                                >
                                  <AlertTriangle className="w-2.5 h-2.5" /> REVISAR
                                </span>
                              ) : p.documento_id && p.en_excel !== false ? (
                                <span
                                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-[10px] font-bold whitespace-nowrap shadow-sm shadow-emerald-500/10"
                                  title="Registro completo y verificado"
                                >
                                  <CheckCircle className="w-2.5 h-2.5" /> VÁLIDO
                                </span>
                              ) : null}
                            </div>
                          </td>

                          {/* Acciones — solo eliminar */}
                          <td className="py-3 px-2 w-10 text-center whitespace-nowrap" onClick={(e) => e.stopPropagation()}>
                            <button onClick={() => eliminar(p.id, p.numero_identificacion)} title="Eliminar" className="p-1.5 rounded-lg text-slate-400 hover:text-rose-400 hover:bg-slate-800 transition-colors">
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </td>
                        </tr>

                        {/* ── Fila expandida (acordeón con visor PDF + tarjetas/edición) ── */}
                        {isExpandida && (
                          <tr key={`${p.id}-detalle`} className="border-b border-slate-800/40">
                            <td colSpan={9} className="p-0">
                              <div className="border-t border-primary-500/20 animate-slideDown w-full min-w-0 overflow-hidden" onClick={(e) => e.stopPropagation()}>
                                {renderPanelDetalle(p)}
                              </div>
                            </td>
                          </tr>
                        )}
                      </Fragment>
                    );
                  })}
                </tbody>
              </table>

              {/* Pie de Tabla con Conteo Detallado */}
              <div className="flex flex-col sm:flex-row items-center justify-between px-6 py-4 bg-slate-950/70 border-t border-slate-800/80 text-xs text-slate-400 gap-2">
                <div className="flex items-center gap-2">
                  <div className="p-1 rounded bg-primary-500/10 text-primary-400">
                    <Users className="w-4 h-4" />
                  </div>
                  <span>
                    Total en la tabla: <strong className="text-white font-bold text-sm">{personasFiltradas.length}</strong> {personasFiltradas.length === 1 ? "persona" : "personas"}
                    {buscar && (
                      <span className="text-slate-500 ml-1">
                        (filtradas de un total de <strong className="text-slate-300 font-semibold">{personas.length}</strong>)
                      </span>
                    )}
                  </span>
                </div>
                <div className="flex items-center gap-4 text-[11px] text-slate-500">
                  <span className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                    <strong className="text-slate-300 font-semibold">{stats.validas}</strong> Válidas
                  </span>
                  <span className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-amber-400" />
                    <strong className="text-slate-300 font-semibold">{stats.revision}</strong> Por revisar
                  </span>
                  <span className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-purple-400" />
                    <strong className="text-slate-300 font-semibold">{stats.discrepancia}</strong> Falta PDF/Excel
                  </span>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Input oculto para subir PDF de la cédula para una persona */}
        <input
          type="file"
          ref={fileInputRef}
          onChange={manejarArchivoPdf}
          accept="application/pdf,.pdf"
          className="hidden"
        />
      </main>
    </div>
  );
}
