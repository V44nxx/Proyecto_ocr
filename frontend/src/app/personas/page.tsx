"use client";

import { useState, useEffect, useRef, Fragment, Suspense } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import toast from "react-hot-toast";
import {
  Users, Search, AlertTriangle, AlertCircle, CheckCircle,
  Edit3, Save, X, RefreshCw, Trash2, Calendar, MapPin,
  UserCheck, FileText, Eye, EyeOff,
  ZoomIn, ZoomOut, RotateCw, ImageOff, Hash, Clock, Cpu,
  ChevronDown, ChevronUp, Download, CheckSquare, Square, UploadCloud, FileSpreadsheet, Check
} from "lucide-react";
import Sidebar from "@/components/ui/Sidebar";
import { useSidebar } from "@/context/SidebarContext";
import { apiPersonas, apiDocumentos, apiExportacion, getErrorMessage } from "@/lib/api";
import { auth } from "@/lib/auth";
import { formatNombreCompleto, calcularEdad, verificarInconsistenciaDocumentoEdad } from "@/lib/formatters";
import type { Persona, PersonaUpdate, Documento } from "@/types";

const getTipoDocInfo = (tipo?: string | null) => {
  const t = (tipo || "").toUpperCase().trim();
  if (!t || t === "UNKNOWN") {
    return {
      codigo: "?",
      label: "Por verificar",
      badge: "bg-gray-50 dark:bg-gray-800/60 border border-gray-300 dark:border-gray-600 text-gray-500 dark:text-gray-400 font-bold shadow-sm",
      pill: "bg-gray-50 dark:bg-gray-800/60 text-gray-500 dark:text-gray-400 border border-gray-300 dark:border-gray-600 font-semibold shadow-sm",
    };
  }
  if (t.includes("CONTRA") || t.includes("COMPROBANTE") || t === "CT") {
    return {
      codigo: "CT",
      label: "Contraseña",
      badge: "bg-teal-50 dark:bg-teal-950/40 border border-teal-300 dark:border-teal-800/50 text-teal-800 dark:text-teal-300 font-bold shadow-sm",
      pill: "bg-teal-50 dark:bg-teal-950/40 text-teal-800 dark:text-teal-300 border border-teal-300 dark:border-teal-800/50 font-semibold shadow-sm",
    };
  }
  if (t.includes("TARJETA") || t === "TI") {
    return {
      codigo: "TI",
      label: "Tarjeta de Identidad",
      badge: "bg-purple-50 dark:bg-purple-950/40 border border-purple-300 dark:border-purple-800/50 text-purple-800 dark:text-purple-300 font-bold shadow-sm",
      pill: "bg-purple-50 dark:bg-purple-950/40 text-purple-800 dark:text-purple-300 border border-purple-300 dark:border-purple-800/50 font-semibold shadow-sm",
    };
  }
  if (t.includes("EXTRANJERIA") || t === "CE") {
    return {
      codigo: "CE",
      label: "Cédula Extranjería",
      badge: "bg-amber-50 dark:bg-amber-950/40 border border-amber-300 dark:border-amber-800/50 text-amber-800 dark:text-amber-300 font-bold shadow-sm",
      pill: "bg-amber-50 dark:bg-amber-950/40 text-amber-800 dark:text-amber-300 border border-amber-300 dark:border-amber-800/50 font-semibold shadow-sm",
    };
  }
  if (t.includes("PASAPORTE") || t === "PAS") {
    return {
      codigo: "PAS",
      label: "Pasaporte",
      badge: "bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-300 dark:border-emerald-800/50 text-emerald-800 dark:text-emerald-300 font-bold shadow-sm",
      pill: "bg-emerald-50 dark:bg-emerald-950/40 text-emerald-800 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-800/50 font-semibold shadow-sm",
    };
  }
  return {
    codigo: "CC",
    label: "Cédula de Ciudadanía",
    badge: "bg-blue-50 dark:bg-blue-950/40 border border-blue-300 dark:border-blue-800/50 text-blue-800 dark:text-blue-300 font-bold shadow-sm",
    pill: "bg-blue-50 dark:bg-blue-950/40 text-blue-800 dark:text-blue-300 border border-blue-300 dark:border-blue-800/50 font-semibold shadow-sm",
  };
};

const esPersonaEnRevision = (p: Persona) => {
  const edad = p.edad ?? calcularEdad(p.fecha_nacimiento);
  const inc = verificarInconsistenciaDocumentoEdad(p.tipo_documento, p.fecha_nacimiento, edad);
  return Boolean(
    p.requiere_revision || 
    (p.estado_registro && p.estado_registro !== "VALID") || 
    inc.esInvalido || 
    (p.detalles_campos as any)?.discrepancia_documento_edad
  );
};

function PersonasContent() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const { collapsed } = useSidebar();
  const docParam = searchParams.get("documento_id");

  const [personas, setPersonas] = useState<Persona[]>([]);
  const [documentos, setDocumentos] = useState<Documento[]>([]);
  const [totalPersonasGlobal, setTotalPersonasGlobal] = useState<number | null>(null);
  const [filtroDocumento, setFiltroDocumento] = useState<string>(docParam || "todos");
  const [documentosCargados, setDocumentosCargados] = useState(false);
  const [seleccionados, setSeleccionados] = useState<Set<string>>(new Set());
  const [exportando, setExportando] = useState(false);
  const [cargando, setCargando] = useState(true);
  const [buscar, setBuscar] = useState("");
  type FiltroEstado = "todos" | "validas" | "revision" | "discrepancia" | "falta_pdf" | "falta_excel" | "menores";
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
    menores: 0,
  });

  // Modales de eliminación masiva y vaciado de tabla
  const [modalVaciarAbierto, setModalVaciarAbierto] = useState(false);
  const [modalEliminarSeleccionadosAbierto, setModalEliminarSeleccionadosAbierto] = useState(false);
  const [eliminandoEnLote, setEliminandoEnLote] = useState(false);

  // Acordeón: solo una fila expandida a la vez
  const [expandidoId, setExpandidoId] = useState<string | null>(null);
  // Control de campos secundarios (fecha exp, lugar exp, género)
  const [detallesExpandidos, setDetallesExpandidos] = useState<Set<string>>(new Set());
  const toggleDetallesExtra = (id: string) => {
    setDetallesExpandidos((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

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
  }, [pathname]);

  useEffect(() => {
    if (!auth.isAuthenticated() || !documentosCargados) return;
    cargarPersonas(true);
    const interval = setInterval(() => cargarPersonas(false), 4000);
    return () => clearInterval(interval);
  }, [pathname, filtroDocumento, documentosCargados]);

  useEffect(() => {
    const docQuery = searchParams.get("documento_id");
    if (docQuery && docQuery !== filtroDocumento) {
      setFiltroDocumento(docQuery);
      if (typeof window !== "undefined") {
        sessionStorage.removeItem("ver_todos_los_archivos");
        localStorage.setItem("ultimo_documento_id", docQuery);
      }
    }
  }, [searchParams]);

  const cargarDocumentos = async () => {
    try {
      const [resDocs, resStatsGlobal] = await Promise.all([
        apiDocumentos.listar({ limit: 100 }),
        apiDocumentos.estadisticas().catch(() => null),
      ]);
      const docs: Documento[] = Array.isArray(resDocs.data) ? resDocs.data : [];
      setDocumentos(docs);

      if (resStatsGlobal?.data?.total_personas != null) {
        setTotalPersonasGlobal(resStatsGlobal.data.total_personas);
      }

      // Prioridad 1: si hay ?documento_id=... en la URL
      const docQuery = searchParams.get("documento_id");
      if (docQuery && docs.some((d) => d.id === docQuery)) {
        setFiltroDocumento(docQuery);
        if (typeof window !== "undefined") {
          sessionStorage.removeItem("ver_todos_los_archivos");
          localStorage.setItem("ultimo_documento_id", docQuery);
        }
        setDocumentosCargados(true);
        return;
      }

      // Prioridad 2: si se acaba de enviar/subir un archivo nuevo
      const nuevoEnviado = typeof window !== "undefined" && localStorage.getItem("nuevo_archivo_enviado") === "true";
      if (nuevoEnviado) {
        if (typeof window !== "undefined") {
          localStorage.removeItem("nuevo_archivo_enviado");
          sessionStorage.removeItem("ver_todos_los_archivos");
        }
        const ultimoId = typeof window !== "undefined" ? localStorage.getItem("ultimo_documento_id") : null;
        const targetDoc = (ultimoId && docs.find((d) => d.id === ultimoId)) || docs[0];
        if (targetDoc) {
          setFiltroDocumento(targetDoc.id);
          if (typeof window !== "undefined") {
            localStorage.setItem("ultimo_documento_id", targetDoc.id);
          }
          setDocumentosCargados(true);
          return;
        }
      }

      // Prioridad 3: si el usuario eligió explícitamente "ver todos los archivos"
      const verTodosManual = typeof window !== "undefined" && sessionStorage.getItem("ver_todos_los_archivos") === "true";
      if (verTodosManual) {
        setFiltroDocumento("todos");
        setDocumentosCargados(true);
        return;
      }

      // Por defecto: mostrar SOLO el último archivo enviado (el más reciente en el sistema)
      const ultimoId = typeof window !== "undefined" ? localStorage.getItem("ultimo_documento_id") : null;
      const targetDoc = (ultimoId && docs.find((d) => d.id === ultimoId)) || docs[0];
      if (targetDoc) {
        setFiltroDocumento(targetDoc.id);
        if (typeof window !== "undefined") {
          localStorage.setItem("ultimo_documento_id", targetDoc.id);
        }
      } else {
        setFiltroDocumento("todos");
      }
      setDocumentosCargados(true);
    } catch {
      setDocumentosCargados(true);
    }
  };

  const recargarManual = async () => {
    setCargando(true);
    await cargarPersonas(true, true);
  };

  const cargarPersonas = async (mostrarSpinner = false, esManual = false) => {
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
      const revCount = items.filter(esPersonaEnRevision).length;
      const faltaPdfCount = items.filter((p: Persona) => !p.documento_id || p.en_pdf === false).length;
      const faltaExcelCount = items.filter((p: Persona) => p.en_excel === false).length;
      const discCount = items.filter((p: Persona) => (!p.documento_id || p.en_pdf === false) || p.en_excel === false).length;
      const valCount = items.filter((p: Persona) => !esPersonaEnRevision(p) && p.documento_id && p.en_excel !== false).length;
      const menoresCount = items.filter((p: Persona) => {
        const ed = p.edad ?? calcularEdad(p.fecha_nacimiento);
        return ed !== null && ed < 14;
      }).length;

      setStats({
        total: tot,
        revision: revCount,
        validas: valCount,
        discrepancia: discCount,
        faltaPdf: faltaPdfCount,
        faltaExcel: faltaExcelCount,
        menores: menoresCount,
      });

      if (!docIdFiltro && tot > 0) {
        setTotalPersonasGlobal(tot);
      }

      // Solo mostrar notificación si el usuario ejecutó la recarga manualmente
      if (esManual) {
        toast.success(`${items.length} persona(s) sincronizada(s)`, { id: "personas-sync" });
      }
    } catch (err) {
      console.error("Error al cargar personas:", err);
      if (esManual) {
        toast.error("Error al cargar la lista de personas", { id: "personas-sync" });
      }
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
      fecha_expedicion: p.fecha_expedicion ? String(p.fecha_expedicion) : "",
      lugar_expedicion: p.lugar_expedicion || "",
      sexo: p.sexo || "",
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
      toast.success(forzarAprobado ? "Datos guardados y persona validada" : "Datos actualizados correctamente", { id: "guardar-persona" });
      setEditando(null);
      cargarPersonas(true);
    } catch {
      toast.error("Error guardando cambios", { id: "guardar-persona" });
    }
  };

  const eliminar = async (id: string, cedula: string) => {
    if (!confirm(`¿Desea eliminar el registro de la persona con cédula ${cedula}?`)) return;
    try {
      await apiPersonas.eliminar(id);
      toast.success("Registro eliminado", { id: "eliminar-persona" });
      if (expandidoId === id) setExpandidoId(null);
      cargarPersonas(true);
    } catch {
      toast.error("Error al eliminar registro", { id: "eliminar-persona" });
    }
  };

  const ejecutarEliminarSeleccionados = async () => {
    if (seleccionados.size === 0) return;
    setEliminandoEnLote(true);
    const toastId = toast.loading(`Eliminando ${seleccionados.size} registros...`);
    try {
      const res = await apiPersonas.eliminarMultiples(Array.from(seleccionados));
      const cant = res.data.eliminadas || seleccionados.size;
      toast.success(`Se eliminaron ${cant} personas exitosamente`, { id: toastId });
      setSeleccionados(new Set());
      setModalEliminarSeleccionadosAbierto(false);
      if (expandidoId && seleccionados.has(expandidoId)) setExpandidoId(null);
      cargarPersonas(true);
    } catch (err: unknown) {
      const msg = getErrorMessage(err, "Error al eliminar personas seleccionadas");
      toast.error(msg, { id: toastId });
    } finally {
      setEliminandoEnLote(false);
    }
  };

  const ejecutarVaciarTabla = async () => {
    setEliminandoEnLote(true);
    const docId = filtroDocumento !== "todos" ? filtroDocumento : undefined;
    const toastId = toast.loading("Vaciando tabla de personas...");
    try {
      const res = await apiPersonas.vaciarTodas({ documento_id: docId });
      const cant = res.data.eliminadas;
      toast.success(`Tabla vaciada: ${cant} personas eliminadas`, { id: toastId });
      setSeleccionados(new Set());
      setExpandidoId(null);
      setModalVaciarAbierto(false);
      cargarPersonas(true);
    } catch (err: unknown) {
      const msg = getErrorMessage(err, "Error al vaciar la tabla de personas");
      toast.error(msg, { id: toastId });
    } finally {
      setEliminandoEnLote(false);
    }
  };

  const aprobarRevision = async (id: string, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    try {
      await apiPersonas.actualizar(id, { requiere_revision: false });
      toast.success("Persona aprobada como válida", { id: `aprobar-${id}` });
      cargarPersonas(true);
    } catch {
      toast.error("Error al aprobar persona", { id: `aprobar-${id}` });
    }
  };

  // Filtrado local por estado y cédula / nombre
  const personasFiltradas = (personas || []).filter((p) => {
    if (!p) return false;
    const esRev = esPersonaEnRevision(p);
    if (filtroEstado === "revision") {
      if (!esRev) return false;
    } else if (filtroEstado === "validas") {
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
    } else if (filtroEstado === "menores") {
      const ed = p.edad ?? calcularEdad(p.fecha_nacimiento);
      if (ed === null || ed >= 14) return false;
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
      toast.error("Selecciona al menos una persona para exportar", { id: "export-seleccion" });
      return;
    }
    setExportando(true);
    try {
      const docId = filtroDocumento !== "todos" ? filtroDocumento : undefined;
      await apiExportacion.descargarXlsx({
        documentoId: docId,
        personaIds: Array.from(seleccionados),
      });
      toast.success(`${seleccionados.size} persona(s) exportada(s) a Excel`, { id: "export-seleccion" });
    } catch {
      toast.error("Error al exportar personas a Excel", { id: "export-seleccion" });
    } finally {
      setExportando(false);
    }
  };

  const exportarVistaActual = async () => {
    if (personasFiltradas.length === 0) {
      toast.error("No hay personas para exportar en la vista actual", { id: "export-excel" });
      return;
    }
    setExportando(true);
    try {
      const docId = filtroDocumento !== "todos" ? filtroDocumento : undefined;
      await apiExportacion.descargarXlsx({
        documentoId: docId,
        personaIds: personasFiltradas.map((p) => p.id),
      });
      toast.success(`${personasFiltradas.length} persona(s) exportada(s) a Excel`, { id: "export-excel" });
    } catch {
      toast.error("Error al exportar a Excel", { id: "export-excel" });
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
    const esMenor14Detalle = edadCalculada !== null && edadCalculada < 14;

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
        valor: edadCalculada !== null ? `${edadCalculada} años cumplidos` : null,
        esMenor: esMenor14Detalle,
      },
    ];

    const camposSecundarios = [
      {
        key: "fecha_expedicion",
        label: "Fecha de Expedición",
        icono: <Calendar className="w-3.5 h-3.5" />,
        valor: p.fecha_expedicion ? String(p.fecha_expedicion) : null
      },
      {
        key: "lugar_expedicion",
        label: "Lugar de Expedición",
        icono: <MapPin className="w-3.5 h-3.5" />,
        valor: p.lugar_expedicion || null
      },
      {
        key: "sexo",
        label: "Género / Sexo",
        icono: <Users className="w-3.5 h-3.5" />,
        valor: p.sexo || null
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
        <div className="lg:w-[44%] w-full flex flex-col border-b lg:border-b-0 lg:border-r border-slate-300 dark:border-slate-800/50 min-h-[300px] min-w-0 overflow-hidden">
          {/* Toolbar PDF */}
          <div className="flex items-center justify-between px-3 py-1.5 bg-slate-100 dark:bg-slate-900/70 border-b border-slate-300 dark:border-slate-800/40 min-w-0 gap-1">
            <div className="flex items-center gap-1.5 min-w-0">
              <FileText className="w-3.5 h-3.5 text-primary-500 dark:text-primary-400 shrink-0" />
              <span className="text-[11px] font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider shrink-0">Vista Documento</span>
              {p.nombre_documento && (
                <span className="text-[10px] font-mono text-slate-700 dark:text-slate-300 truncate max-w-[130px] bg-slate-200 dark:bg-slate-800 px-1.5 py-0.5 rounded border border-slate-300 dark:border-slate-700 ml-1 shrink shadow-sm" title={`Archivo origen: ${p.nombre_documento}`}>
                  {p.nombre_documento}
                </span>
              )}
              {tieneDosLados && (
                <div className="flex items-center gap-1 ml-1.5 shrink-0">
                  <button
                    onClick={() => { setPaginaPrevia(p.pagina_frente!); setImgCargando(true); setImgError(false); }}
                    className={`px-2 py-0.5 rounded text-[10px] font-bold transition-all ${paginaPrevia === p.pagina_frente ? "bg-primary-500/25 border border-primary-500/40 text-primary-600 dark:text-primary-300" : "bg-slate-200 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"}`}
                  >
                    Frente
                  </button>
                  <button
                    onClick={() => { setPaginaPrevia(p.pagina_reverso!); setImgCargando(true); setImgError(false); }}
                    className={`px-2 py-0.5 rounded text-[10px] font-bold transition-all ${paginaPrevia === p.pagina_reverso ? "bg-primary-500/25 border border-primary-500/40 text-primary-600 dark:text-primary-300" : "bg-slate-200 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"}`}
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
              <button onClick={() => setZoom(z => Math.max(0.5, z - 0.25))} className="p-1 rounded text-slate-500 hover:text-slate-900 dark:hover:text-white hover:bg-slate-200 dark:hover:bg-slate-800 transition-colors" title="Alejar"><ZoomOut className="w-3 h-3" /></button>
              <span className="text-[10px] font-mono text-slate-600 dark:text-slate-400 w-8 text-center">{Math.round(zoom * 100)}%</span>
              <button onClick={() => setZoom(z => Math.min(2.5, z + 0.25))} className="p-1 rounded text-slate-500 hover:text-slate-900 dark:hover:text-white hover:bg-slate-200 dark:hover:bg-slate-800 transition-colors" title="Acercar"><ZoomIn className="w-3 h-3" /></button>
              <button onClick={() => setZoom(1)} className="p-1 rounded text-slate-500 hover:text-slate-900 dark:hover:text-white hover:bg-slate-200 dark:hover:bg-slate-800 transition-colors" title="Restablecer"><RotateCw className="w-3 h-3" /></button>
            </div>
          </div>

          {/* Imagen */}
          <div className="flex-1 overflow-auto flex items-start justify-center p-3 bg-slate-200/50 dark:bg-slate-950/50 min-h-[260px] max-h-[480px]">
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
            <div className="px-3 py-2 border-b border-slate-300 dark:border-slate-800/40 bg-slate-100 dark:bg-slate-900/50 flex items-center justify-between flex-wrap gap-1.5 min-w-0">
              <div className="flex items-center gap-2 text-[10px] flex-wrap min-w-0">
                <span className={`px-2 py-0.5 rounded text-[10px] border font-bold shrink-0 ${getTipoDocInfo(p.tipo_documento).pill}`}>
                  {getTipoDocInfo(p.tipo_documento).label} ({getTipoDocInfo(p.tipo_documento).codigo})
                </span>
                {p.nombre_documento && (
                  <span className="flex items-center gap-1 text-slate-800 dark:text-slate-300 font-mono text-[10px] bg-blue-100 dark:bg-primary-500/10 border border-blue-300 dark:border-primary-500/30 px-2 py-0.5 rounded max-w-[180px] shrink shadow-sm" title={`Archivo PDF origen: ${p.nombre_documento}`}>
                    <FileText className="w-3 h-3 text-blue-700 dark:text-primary-400 shrink-0" />
                    <span className="text-blue-800 dark:text-primary-400 font-bold shrink-0">PDF:</span>
                    <span className="truncate">{p.nombre_documento}</span>
                  </span>
                )}
                <span className="flex items-center gap-1 text-slate-600 dark:text-slate-500 shrink-0"><Cpu className="w-3 h-3" /> <span className="text-emerald-700 dark:text-emerald-400 font-mono font-semibold">{p.motor_ocr || "google_document_ai"}</span></span>
                <span className="flex items-center gap-1 text-slate-600 dark:text-slate-500 shrink-0"><Clock className="w-3 h-3" /> <span className="text-slate-700 dark:text-slate-400 font-medium">{p.fecha_registro ? new Date(p.fecha_registro).toLocaleDateString("es-CO") : "—"}</span></span>
                {edadCalculada !== null && (() => {
                  const inc = verificarInconsistenciaDocumentoEdad(p.tipo_documento, p.fecha_nacimiento, edadCalculada);
                  return (
                    <span className={`flex items-center gap-1 font-mono text-[10px] px-2 py-0.5 rounded font-bold shrink-0 border shadow-sm ${
                      inc.esInvalido
                        ? "bg-rose-100 dark:bg-rose-500/20 border-rose-400 dark:border-rose-500/40 text-rose-800 dark:text-rose-300 font-extrabold animate-pulse"
                        : esMenor14Detalle
                          ? "bg-rose-100 dark:bg-rose-500/20 border-rose-400 dark:border-rose-500/40 text-rose-800 dark:text-rose-300 font-extrabold animate-pulse"
                          : "bg-amber-100 dark:bg-amber-500/10 border-amber-300 dark:border-amber-500/30 text-amber-900 dark:text-amber-300"
                    }`} title={inc.esInvalido ? inc.motivo : `Edad: ${edadCalculada} años cumplidos`}>
                      <span>{inc.esInvalido ? `⚠️ ${edadCalculada} años (${inc.tipo === "MAYOR_CON_TI" ? "Mayor con TI" : "Menor con CC"})` : esMenor14Detalle ? `⚠️ MENOR: ${edadCalculada} años` : `${edadCalculada} años`}</span>
                    </span>
                  );
                })()}
              </div>
              {estaEditando ? (
                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/40 flex items-center gap-1 shrink-0">
                  <Edit3 className="w-3 h-3" /> Modo Edición
                </span>
              ) : (
                p.grupo_documento_id && <span className="font-mono text-[10px] text-slate-600 truncate max-w-[90px] shrink-0">{p.grupo_documento_id}</span>
              )}
            </div>

            {/* Alerta Destacada en Rojo: Menor de 14 Años */}
            {esMenor14Detalle && (
              <div className="m-2.5 p-3 rounded-xl bg-rose-50 dark:bg-rose-500/15 border-2 border-rose-400 dark:border-rose-500/50 text-rose-950 dark:text-rose-200 shadow-md animate-pulse min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <AlertTriangle className="w-4 h-4 text-rose-600 dark:text-rose-400 shrink-0" />
                  <span className="text-xs font-black uppercase tracking-wider text-rose-800 dark:text-rose-300">
                    ALERTA: PERSONA MENOR DE 14 AÑOS ({edadCalculada} AÑOS)
                  </span>
                </div>
                <p className="text-xs text-rose-900 dark:text-rose-100 ml-6 break-words font-medium">
                  Esta persona tiene <strong className="text-rose-950 dark:text-white font-bold underline">{edadCalculada} años cumplidos</strong> según su fecha de nacimiento registrada (<strong className="font-mono text-rose-950 dark:text-white">{p.fecha_nacimiento || "sin fecha"}</strong>).
                </p>
              </div>
            )}

            {/* Alerta Destacada: Archivo No Válido por Inconsistencia Documento vs Mayoría/Minoría de Edad */}
            {(() => {
              const edadVal = p.edad ?? calcularEdad(p.fecha_nacimiento);
              const discDocEdad = (p.detalles_campos as any)?.discrepancia_documento_edad;
              const inconsistencia = verificarInconsistenciaDocumentoEdad(p.tipo_documento, p.fecha_nacimiento, edadVal);

              if (!discDocEdad && !inconsistencia.esInvalido) return null;

              const esMayor = discDocEdad?.tipo === "MAYOR_CON_TI" || inconsistencia.tipo === "MAYOR_CON_TI" || (edadVal !== null && edadVal >= 18);
              const edadMostrar = discDocEdad?.edad ?? inconsistencia.edad ?? edadVal;
              const docInfo = getTipoDocInfo(p.tipo_documento);

              return (
                <div className="m-2.5 p-3.5 rounded-xl bg-rose-50 dark:bg-rose-950/40 border-2 border-rose-500 dark:border-rose-500/70 text-rose-950 dark:text-rose-100 shadow-md min-w-0">
                  <div className="flex items-center gap-2 mb-1.5">
                    <AlertTriangle className="w-5 h-5 text-rose-600 dark:text-rose-400 shrink-0" />
                    <span className="text-xs font-black uppercase tracking-wider text-rose-900 dark:text-rose-200">
                      {esMayor
                        ? "Archivo No Válido: Persona Mayor de Edad con Tarjeta de Identidad"
                        : "Archivo No Válido: Persona Menor de Edad con Cédula de Ciudadanía"}
                    </span>
                  </div>
                  <p className="text-xs text-rose-950 dark:text-rose-100 ml-7 mb-2.5 font-medium leading-relaxed">
                    {esMayor
                      ? `El archivo presentado no es válido ya que la persona es mayor de edad (${edadMostrar !== null ? `${edadMostrar} años` : "18+ años"}) y presenta un archivo de Tarjeta de Identidad que solo corresponde a menores de edad. Cuando la persona cumple 18 años debe presentar Cédula de Ciudadanía o Contraseña vigente.`
                      : `El archivo presentado no es válido ya que la persona es menor de edad (${edadMostrar !== null ? `${edadMostrar} años` : "< 18 años"}) y presenta Cédula de Ciudadanía, documento exclusivo de personas mayores de edad. Debe presentar Tarjeta de Identidad.`}
                  </p>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 ml-7 text-xs">
                    <div className="p-2.5 rounded-lg bg-white/90 dark:bg-slate-900/80 border border-blue-400 dark:border-blue-600/50 shadow-sm">
                      <div className="text-[10px] uppercase font-bold text-blue-800 dark:text-blue-400 flex items-center gap-1">
                        <Clock className="w-3 h-3 text-blue-600 dark:text-blue-400" /> Condición Legal y Edad Calculada
                      </div>
                      <div className="font-extrabold text-slate-900 dark:text-white text-sm mt-0.5">
                        {edadMostrar !== null ? `${edadMostrar} años cumplidos` : "Edad no determinada"} — {esMayor ? "Mayor de Edad (≥ 18 años)" : "Menor de Edad (< 18 años)"}
                      </div>
                      <div className="text-[11px] text-slate-600 dark:text-slate-400 mt-1 font-medium">
                        {esMayor ? "Documento legal requerido: Cédula de Ciudadanía (CC) o Contraseña" : "Documento legal requerido: Tarjeta de Identidad (TI)"}
                      </div>
                    </div>
                    <div className="p-2.5 rounded-lg bg-white/90 dark:bg-slate-900/80 border border-rose-400 dark:border-rose-600/50 shadow-sm">
                      <div className="text-[10px] uppercase font-bold text-rose-800 dark:text-rose-400 flex items-center gap-1">
                        <FileText className="w-3 h-3 text-rose-600 dark:text-rose-400" /> Documento Presentado en PDF
                      </div>
                      <div className="font-extrabold text-rose-950 dark:text-rose-200 text-sm mt-0.5">
                        {docInfo.label} ({docInfo.codigo}) — No Admisible
                      </div>
                      <div className="text-[11px] text-rose-800 dark:text-rose-300 mt-1 font-semibold">
                        {esMayor ? "Incompatible: Tarjeta de Identidad solo es válida hasta los 17 años" : "Incompatible: Cédula de Ciudadanía reservada para mayores de edad"}
                      </div>
                    </div>
                  </div>
                </div>
              );
            })()}

            {/* Alerta Destacada: Discrepancia Crítica de Nombre entre Cédula Física y Planilla Excel */}
            {Boolean((p.detalles_campos as any)?.discrepancia_excel) && (() => {
              const disc = (p.detalles_campos as any).discrepancia_excel;
              const nombreCedula = typeof disc === "object" ? disc.nombre_cedula : "";
              const nombreExcel = typeof disc === "object" ? disc.nombre_excel : "";
              return (
                <div className="m-2.5 p-3.5 rounded-xl bg-amber-50 dark:bg-amber-950/40 border-2 border-amber-500 dark:border-amber-500/70 text-amber-950 dark:text-amber-100 shadow-md min-w-0">
                  <div className="flex items-center gap-2 mb-1.5">
                    <AlertTriangle className="w-5 h-5 text-amber-600 dark:text-amber-400 shrink-0" />
                    <span className="text-xs font-black uppercase tracking-wider text-amber-900 dark:text-amber-200">
                      Discrepancia de Nombre: Cédula Física (PDF) vs Planilla Excel
                    </span>
                  </div>
                  <p className="text-xs text-amber-950 dark:text-amber-100 ml-7 mb-2.5 font-medium leading-relaxed">
                    El nombre extraído de la cédula física del PDF difiere del registrado en la planilla oficial de Excel. Se ha conservado prioritariamente el nombre de la planilla oficial de Excel y se requiere revisión obligatoria para validar inconsistencias.
                  </p>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 ml-7 text-xs">
                    <div className="p-2.5 rounded-lg bg-white/90 dark:bg-slate-900/80 border border-blue-400 dark:border-blue-600/50 shadow-sm">
                      <div className="text-[10px] uppercase font-bold text-blue-800 dark:text-blue-400 flex items-center gap-1">
                        <FileSpreadsheet className="w-3 h-3 text-blue-600 dark:text-blue-400" /> Nombre Oficial en Planilla Excel (Conservado)
                      </div>
                      <div className="font-extrabold text-slate-900 dark:text-white text-sm mt-0.5">{nombreExcel || p.nombre_completo}</div>
                    </div>
                    <div className="p-2.5 rounded-lg bg-white/90 dark:bg-slate-900/80 border border-amber-400 dark:border-amber-600/50 shadow-sm">
                      <div className="text-[10px] uppercase font-bold text-amber-800 dark:text-amber-400 flex items-center gap-1">
                        <FileText className="w-3 h-3 text-amber-600 dark:text-amber-400" /> Nombre detectado en Cédula Física (PDF)
                      </div>
                      <div className="font-extrabold text-amber-950 dark:text-amber-200 text-sm mt-0.5">{nombreCedula || "Diferente en PDF"}</div>
                    </div>
                  </div>
                </div>
              );
            })()}

            {/* Alerta: Falta en Planilla Excel */}
            {p.en_excel === false && (
              <div className="m-2.5 p-3.5 rounded-xl bg-purple-100/90 dark:bg-purple-950/60 border-2 border-purple-600 dark:border-purple-500 text-purple-950 dark:text-purple-100 min-w-0 shadow-sm">
                <div className="flex items-center gap-2 mb-1.5">
                  <FileSpreadsheet className="w-4 h-4 text-purple-900 dark:text-purple-300 shrink-0" />
                  <span className="text-xs font-black uppercase tracking-wider text-purple-950 dark:text-purple-200">
                    Alerta: No se encuentra en la Planilla Excel
                  </span>
                </div>
                <p className="text-xs text-purple-950 dark:text-purple-100 ml-6 break-words font-semibold leading-relaxed">
                  El número de identificación <strong className="font-mono text-purple-950 dark:text-white font-black bg-purple-300/80 dark:bg-purple-900 px-2 py-0.5 rounded border border-purple-500 dark:border-purple-600">{p.numero_identificacion}</strong> no figura en la planilla oficial de Excel cargada para comparación.
                </p>
              </div>
            )}

            {/* Alerta: Sin Documento PDF */}
            {(!p.documento_id || p.en_pdf === false) && (
              <div className="m-2.5 p-3.5 rounded-xl bg-sky-100/90 dark:bg-sky-950/60 border-2 border-sky-600 dark:border-sky-500 text-sky-950 dark:text-sky-100 min-w-0 shadow-sm">
                <div className="flex items-center gap-2 mb-1.5">
                  <FileText className="w-4 h-4 text-sky-900 dark:text-sky-300 shrink-0" />
                  <span className="text-xs font-black uppercase tracking-wider text-sky-950 dark:text-sky-200">
                    Alerta: Sin Documento PDF Asociado
                  </span>
                </div>
                <p className="text-xs text-sky-950 dark:text-sky-100 ml-6 break-words font-semibold leading-relaxed">
                  Este registro fue creado manualmente o desde Excel y no cuenta con un archivo PDF vinculado. Puede subirlo con el botón &quot;Subir PDF Cédula&quot;.
                </p>
              </div>
            )}

            {/* Motivos de Revisión / Alerta para Asistente */}
            {Boolean(esPersonaEnRevision(p)) && (() => {
              const rawMotivos: string[] = Array.isArray((p.detalles_campos as any)?.motivos_revision)
                ? (p.detalles_campos as any).motivos_revision
                : [];
              const tieneDiscrepanciaSuperior = Boolean((p.detalles_campos as any)?.discrepancia_excel);
              const tieneDiscrepanciaDocEdad = Boolean((p.detalles_campos as any)?.discrepancia_documento_edad) || verificarInconsistenciaDocumentoEdad(p.tipo_documento, p.fecha_nacimiento, edadCalculada).esInvalido;
              const motivosFiltrados = rawMotivos.filter((m: string) => {
                const ml = m.toLowerCase();
                if (ml.includes("expedici") || ml.includes("sexo") || ml.includes("lugar") || ml.includes("genero")) return false;
                if (ml.includes("campo 'nombres'") || ml.includes("campo 'apellidos'")) return false;
                // Si la tarjeta destacada de discrepancia ya se muestra arriba, no duplicar en las viñetas inferiores
                if (tieneDiscrepanciaSuperior && (ml.includes("discrepancia") || ml.includes("campo 'nombre_completo'"))) return false;
                if (tieneDiscrepanciaDocEdad && (ml.includes("mayor de edad") || ml.includes("menor de edad") || ml.includes("tarjeta de identidad"))) return false;
                return true;
              });
              if (motivosFiltrados.length === 0 && (!p.requiere_revision || tieneDiscrepanciaSuperior || tieneDiscrepanciaDocEdad)) return null;
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

                  {/* Campos adicionales desplegables en modo edición */}
                  <div className="sm:col-span-2 pt-2 border-t border-slate-800/80">
                    <button
                      type="button"
                      onClick={() => toggleDetallesExtra(p.id)}
                      className="flex items-center gap-1.5 text-xs text-primary-400 hover:text-primary-300 font-semibold mb-2 transition-colors cursor-pointer"
                    >
                      {detallesExpandidos.has(p.id) ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                      <span>{detallesExpandidos.has(p.id) ? "Ocultar datos adicionales" : "Editar datos adicionales (Fecha/Lugar Expedición, Género)"}</span>
                    </button>

                    {detallesExpandidos.has(p.id) && (
                      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5 p-2.5 bg-slate-950/60 rounded-xl border border-slate-800/80 animate-in fade-in duration-200">
                        <div>
                          <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">
                            Fecha de Expedición
                          </label>
                          <input
                            type="text"
                            value={editForm.fecha_expedicion || ""}
                            onChange={(e) => setEditForm(prev => ({ ...prev, fecha_expedicion: e.target.value }))}
                            placeholder="AAAA-MM-DD"
                            className="w-full bg-slate-900 border border-slate-700/80 rounded-lg px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-primary-500 transition-colors font-mono"
                          />
                        </div>

                        <div>
                          <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">
                            Lugar de Expedición
                          </label>
                          <input
                            type="text"
                            value={editForm.lugar_expedicion || ""}
                            onChange={(e) => setEditForm(prev => ({ ...prev, lugar_expedicion: e.target.value }))}
                            placeholder="Ej: BOGOTA D.C."
                            className="w-full bg-slate-900 border border-slate-700/80 rounded-lg px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-primary-500 transition-colors uppercase"
                          />
                        </div>

                        <div>
                          <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">
                            Género / Sexo
                          </label>
                          <select
                            value={editForm.sexo || ""}
                            onChange={(e) => setEditForm(prev => ({ ...prev, sexo: e.target.value }))}
                            className="w-full bg-slate-900 border border-slate-700/80 rounded-lg px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-primary-500 transition-colors"
                          >
                            <option value="">No especificado</option>
                            <option value="M">MASCULINO (M)</option>
                            <option value="F">FEMENINO (F)</option>
                          </select>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ) : (
              /* Vista de Tarjetas (Compactas con content-start para evitar que se alarguen) */
              <div className="p-2.5 space-y-2.5 min-w-0">
                {p.nombre_documento && (
                  <div className="px-2.5 py-1.5 rounded-lg bg-slate-100 dark:bg-slate-900/80 border border-slate-300 dark:border-slate-800 flex items-center justify-between text-xs min-w-0 shadow-sm">
                    <div className="flex items-center gap-1.5 min-w-0 flex-1">
                      <FileText className="w-3.5 h-3.5 text-primary-500 dark:text-primary-400 shrink-0" />
                      <span className="text-[10px] font-bold text-slate-700 dark:text-slate-400 uppercase tracking-wider shrink-0">Documento PDF:</span>
                      <span className="font-mono text-xs text-slate-800 dark:text-slate-200 truncate" title={p.nombre_documento}>{p.nombre_documento}</span>
                    </div>
                    <span className="text-[10px] font-mono text-slate-600 dark:text-slate-500 shrink-0 ml-2">
                      {p.pagina_frente ? `Pág. ${p.pagina_frente}${p.pagina_reverso ? ` / ${p.pagina_reverso}` : ""}` : ""}
                    </span>
                  </div>
                )}
                <div className="grid grid-cols-2 gap-2 content-start min-w-0">
                  {campos.map(({ key, label, icono, valor, esMenor }) => {
                    const c = conf(key);
                    const col = color(valor ? c : 0);
                    return (
                      <div key={key} className={`rounded-lg p-2 transition-colors flex flex-col justify-between min-h-[58px] min-w-0 overflow-hidden shadow-sm ${
                        esMenor
                          ? "bg-rose-50 dark:bg-rose-950/20 border border-rose-300 dark:border-rose-500/40"
                          : "bg-white dark:bg-slate-900/60 border border-slate-300 dark:border-slate-800/60 hover:border-slate-400 dark:hover:border-slate-700/80"
                      }`}>
                        <div className="flex items-center justify-between min-w-0">
                          <div className={`flex items-center gap-1 min-w-0 ${esMenor ? "text-rose-600 dark:text-rose-400 font-semibold" : "text-slate-600 dark:text-slate-500"}`}>
                            {icono}
                            <span className="text-[10px] font-bold uppercase tracking-wider truncate">{label}</span>
                          </div>
                          <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold border shrink-0 ${
                            esMenor
                              ? "bg-rose-100 dark:bg-rose-500/20 border-rose-300 dark:border-rose-500/40 text-rose-700 dark:text-rose-300 font-extrabold"
                              : valor ? col.badge : "bg-rose-50 dark:bg-rose-500/10 border-rose-200 dark:border-rose-500/20 text-rose-600 dark:text-rose-400"
                          }`}>
                            {esMenor ? "MENOR" : valor ? `${c}%` : "N/D"}
                          </span>
                        </div>
                        <div className="my-0.5 min-w-0">
                          {valor
                            ? (
                              <div className="min-w-0">
                                <span className={`text-xs font-semibold truncate block font-mono ${esMenor ? "text-rose-600 dark:text-rose-300 font-bold" : "text-slate-900 dark:text-white"}`} title={valor}>
                                  {valor}
                                </span>
                                {key === "numero_identificacion" && (p.detalles_campos as any)?.numero_identificacion_original_ocr && (
                                  <span className="text-[9px] text-emerald-600 dark:text-emerald-400 font-medium flex items-center gap-1 mt-0.5 truncate" title={`Corregido desde planilla oficial Excel (OCR leyó: ${(p.detalles_campos as any).numero_identificacion_original_ocr})`}>
                                    <CheckCircle className="w-2.5 h-2.5 shrink-0" />
                                    <span className="truncate">Corregido de {(p.detalles_campos as any).numero_identificacion_original_ocr}</span>
                                  </span>
                                )}
                              </div>
                            )
                            : <span className="text-[11px] italic text-rose-500 dark:text-rose-400/80 font-medium block truncate">No detectado por OCR</span>
                          }
                        </div>
                        {valor ? (
                          <div className="h-1 bg-slate-200 dark:bg-slate-800 rounded-full overflow-hidden">
                            <div className={`h-full bg-gradient-to-r ${esMenor ? "from-rose-500 to-red-400" : col.bar} rounded-full transition-all duration-700`} style={{ width: `${c}%` }} />
                          </div>
                        ) : (
                          <div className="h-1 bg-rose-200 dark:bg-rose-950/30 rounded-full overflow-hidden">
                            <div className="h-full bg-rose-500/40 rounded-full w-full" />
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>

                {/* Botón Ver Más Detalles (Expedición, Género) — Sin alertas de revisión */}
                <div className="pt-2 w-full">
                  <div className="flex justify-center">
                    <button
                      type="button"
                      onClick={() => toggleDetallesExtra(p.id)}
                      className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 dark:bg-slate-800/80 dark:hover:bg-slate-800 border border-slate-300 dark:border-slate-700/60 text-xs font-semibold text-slate-700 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white transition-all shadow-sm cursor-pointer"
                    >
                      {detallesExpandidos.has(p.id) ? (
                        <>
                          <ChevronUp className="w-3.5 h-3.5 text-primary-500 dark:text-primary-400" />
                          <span>Ocultar datos adicionales</span>
                        </>
                      ) : (
                        <>
                          <ChevronDown className="w-3.5 h-3.5 text-primary-500 dark:text-primary-400" />
                          <span>Ver más detalles (Fecha/Lugar Expedición, Género)</span>
                        </>
                      )}
                    </button>
                  </div>

                  {detallesExpandidos.has(p.id) && (
                    <div className="w-full mt-3 p-3 rounded-xl bg-slate-100/80 dark:bg-slate-900/70 border border-slate-300 dark:border-slate-800 space-y-2.5 animate-in fade-in duration-200 shadow-sm">
                      <div className="flex items-center justify-between">
                        <span className="text-[10px] font-bold text-slate-700 dark:text-slate-400 uppercase tracking-wider">
                          Datos Adicionales
                        </span>
                        <span className="text-[9px] text-slate-500 italic">
                          Opcionales • No generan motivo de revisión
                        </span>
                      </div>
                      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
                        {camposSecundarios.map(({ key, label, icono, valor }) => (
                          <div
                            key={key}
                            className="rounded-lg bg-white dark:bg-slate-950/60 border border-slate-300 dark:border-slate-800/80 p-2.5 flex flex-col justify-between min-h-[58px] min-w-0 shadow-sm"
                          >
                            <div className="flex items-center justify-between gap-1.5 min-w-0">
                              <div className="flex items-center gap-1 text-slate-600 dark:text-slate-400 text-[10px] font-bold uppercase tracking-wider min-w-0 flex-1">
                                {icono}
                                <span className="truncate" title={label}>{label}</span>
                              </div>
                              <span className={`px-1.5 py-0.5 rounded text-[8.5px] font-semibold shrink-0 border inline-flex items-center gap-0.5 ${
                                valor
                                  ? "bg-emerald-500/10 dark:bg-emerald-500/15 border-emerald-500/30 text-emerald-700 dark:text-emerald-400"
                                  : "bg-slate-100 dark:bg-slate-800/80 border-slate-300 dark:border-slate-700/60 text-slate-500 dark:text-slate-400"
                              }`}>
                                {valor ? (
                                  <>
                                    <Check className="w-2.5 h-2.5 shrink-0" />
                                    <span>OK</span>
                                  </>
                                ) : (
                                  "Opcional"
                                )}
                              </span>
                            </div>
                            <div className="mt-1 min-w-0">
                              {valor ? (
                                <span className="text-xs font-semibold text-slate-900 dark:text-slate-200 font-mono block truncate" title={valor}>
                                  {valor}
                                </span>
                              ) : (
                                <span className="text-[11px] text-slate-500 italic block">
                                  No registrado
                                </span>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
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
                  className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-slate-800/50 hover:bg-slate-800 border border-slate-700/40 text-slate-400 hover:text-white text-xs font-medium transition-all shrink-0 ml-auto cursor-pointer"
                  title="Subir y ocultar panel de detalles"
                >
                  <ChevronUp className="w-3.5 h-3.5" /> Subir
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
    <div className="flex min-h-screen bg-slate-50 dark:bg-[#0b0f19] text-slate-900 dark:text-slate-100 font-sans w-full max-w-full overflow-x-hidden">
      <Sidebar />

      <main className={`${collapsed ? "ml-20 max-w-[calc(100vw-5rem)]" : "ml-64 max-w-[calc(100vw-16rem)]"} transition-all duration-300 ease-in-out flex-1 min-w-0 p-4 lg:p-6 overflow-x-hidden`}>
        {/* Header Superior Organizado */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
          <div>
            <div className="flex items-center gap-2 mb-1.5 flex-wrap">
              <span className="p-1.5 rounded-lg bg-primary-500/10 border border-primary-500/20 text-primary-600 dark:text-primary-400">
                <Users className="w-4 h-4" />
              </span>
              <span className="text-xs font-semibold text-primary-600 dark:text-primary-400 uppercase tracking-wider">Base de Datos OCR</span>
              {filtroDocumento !== "todos" ? (
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-[11px] px-2.5 py-0.5 rounded-full bg-primary-50 dark:bg-primary-500/10 border border-primary-200 dark:border-primary-500/30 text-primary-900 dark:text-primary-300 font-medium flex items-center gap-1.5 shadow-sm">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 inline-block animate-pulse"></span>
                    <span className="text-slate-600 dark:text-slate-400">Archivo:</span>
                    <span className="font-bold text-slate-900 dark:text-white truncate max-w-[220px]" title={documentos.find((d) => d.id === filtroDocumento)?.nombre_original || "Archivo"}>
                      {documentos.find((d) => d.id === filtroDocumento)?.nombre_original || "Ficha seleccionada"}
                    </span>
                    <span className="text-slate-600 dark:text-slate-400 font-mono">({stats.total} {stats.total === 1 ? "persona" : "personas"})</span>
                  </span>
                  <button
                    type="button"
                    onClick={() => {
                      setFiltroDocumento("todos");
                      setSeleccionados(new Set());
                      if (typeof window !== "undefined") {
                        sessionStorage.setItem("ver_todos_los_archivos", "true");
                      }
                    }}
                    className="text-[11px] px-2.5 py-0.5 rounded-full bg-slate-200 hover:bg-slate-300 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 font-semibold transition-colors cursor-pointer border border-slate-300 dark:border-slate-700 shadow-sm flex items-center gap-1"
                    title="Ver todas las personas de todos los archivos"
                  >
                    <span>🌐 Ver todos los archivos</span>
                    {totalPersonasGlobal ? <span className="font-mono text-[10px] text-slate-500 dark:text-slate-400">({totalPersonasGlobal})</span> : null}
                  </button>
                </div>
              ) : (
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-[11px] px-2.5 py-0.5 rounded-full bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-300 dark:border-emerald-500/30 text-emerald-900 dark:text-emerald-300 font-medium flex items-center gap-1.5 shadow-sm">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 inline-block"></span>
                    <span className="font-bold text-slate-900 dark:text-white">Mostrando todos los archivos</span>
                    <span className="text-slate-600 dark:text-slate-400 font-mono">({stats.total} personas en total)</span>
                  </span>
                  {documentos.length > 0 && (
                    <button
                      type="button"
                      onClick={() => {
                        const primerDoc = documentos[0];
                        if (primerDoc) {
                          setFiltroDocumento(primerDoc.id);
                          setSeleccionados(new Set());
                          if (typeof window !== "undefined") {
                            sessionStorage.removeItem("ver_todos_los_archivos");
                            localStorage.setItem("ultimo_documento_id", primerDoc.id);
                          }
                        }
                      }}
                      className="text-[11px] px-2.5 py-0.5 rounded-full bg-primary-50 hover:bg-primary-100 dark:bg-primary-500/10 dark:hover:bg-primary-500/20 text-primary-700 dark:text-primary-300 font-semibold transition-colors cursor-pointer border border-primary-200 dark:border-primary-500/30 shadow-sm flex items-center gap-1"
                      title="Ver solo el último archivo enviado"
                    >
                      <span>★ Ver último archivo enviado</span>
                    </button>
                  )}
                </div>
              )}
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 dark:text-white tracking-tight">Personas Registradas</h1>
            <p className="text-slate-600 dark:text-slate-400 text-sm mt-1">
              Haz clic en el ícono <Eye className="inline w-3.5 h-3.5 text-primary-600 dark:text-primary-400 mx-1" /> para expandir el documento y los datos OCR de cada persona.
            </p>
          </div>

          {/* Botones de acción organizados (alineados y con etiquetas completas) */}
          <div className="flex items-center gap-2.5 shrink-0 self-start sm:self-center">
            <button
              onClick={exportarVistaActual}
              disabled={exportando || personas.length === 0}
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold transition-all shadow-md shadow-emerald-950/30 border border-emerald-500/40 disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer whitespace-nowrap"
              title="Exportar registros mostrados a Excel (.xlsx)"
            >
              <Download className="w-4 h-4 shrink-0 text-white" />
              <span>Exportar a Excel</span>
            </button>
            <button
              onClick={() => setModalVaciarAbierto(true)}
              disabled={personas.length === 0}
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-rose-50 dark:bg-rose-500/10 hover:bg-rose-100 dark:hover:bg-rose-500/20 border border-rose-300 dark:border-rose-500/30 text-rose-700 dark:text-rose-400 text-xs font-bold transition-all shadow-sm disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer whitespace-nowrap"
              title={filtroDocumento !== "todos" ? "Vaciar personas de este archivo" : "Vaciar todas las personas de la tabla"}
            >
              <Trash2 className="w-4 h-4 shrink-0 text-rose-600 dark:text-rose-400" />
              <span>Vaciar Tabla</span>
            </button>
          </div>
        </div>

        {/* Tarjetas de Estadísticas / Conteo Rápido Interactivas (5 estados) */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3.5 mb-6">
          {/* Card 1: Total por Archivo o General */}
          <div
            onClick={() => setFiltroEstado("todos")}
            className={`cursor-pointer bg-white dark:bg-slate-900/80 border rounded-2xl p-4 flex items-center justify-between backdrop-blur-md shadow-sm dark:shadow-lg transition-all ${
              filtroEstado === "todos"
                ? "border-primary-500/60 ring-2 ring-primary-500/30 bg-primary-50/60 dark:bg-primary-500/10"
                : "border-slate-200 dark:border-slate-800/80 hover:border-slate-400 dark:hover:border-slate-700"
            }`}
            title={filtroDocumento !== "todos" ? "Mostrar todas las personas de este archivo" : "Mostrar todas las personas registradas"}
          >
            <div>
              <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                {filtroDocumento !== "todos" ? "Total Archivo" : "Total Registradas"}
              </p>
              <div className="flex items-baseline gap-2 mt-1">
                <span className="text-2xl font-black text-slate-900 dark:text-white">{stats.total}</span>
                <span className="text-xs text-slate-500 dark:text-slate-400">
                  {filtroDocumento !== "todos" ? "en archivo" : "en sistema"}
                </span>
              </div>
            </div>
            <div className="w-11 h-11 rounded-xl bg-primary-50 dark:bg-primary-500/15 border border-primary-200 dark:border-primary-500/30 flex items-center justify-center text-primary-600 dark:text-primary-400">
              <Users className="w-5 h-5" />
            </div>
          </div>

          {/* Card 2: Válidas */}
          <div
            onClick={() => setFiltroEstado("validas")}
            className={`cursor-pointer bg-white dark:bg-slate-900/80 border rounded-2xl p-4 flex items-center justify-between backdrop-blur-md shadow-sm dark:shadow-lg transition-all ${
              filtroEstado === "validas"
                ? "border-emerald-500/70 ring-2 ring-emerald-500/40 bg-emerald-50/60 dark:bg-emerald-500/10"
                : "border-slate-200 dark:border-slate-800/80 hover:border-emerald-500/40"
            }`}
            title="Clic para ver solo personas con datos válidos y presentes"
          >
            <div>
              <div className="flex items-center gap-1.5">
                <p className="text-xs font-semibold text-emerald-700 dark:text-emerald-400/90 uppercase tracking-wider">Válidos</p>
                {filtroEstado === "validas" && (
                  <span className="px-1.5 py-0.2 rounded text-[9px] font-bold bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 border border-emerald-500/40">
                    Activo
                  </span>
                )}
              </div>
              <div className="flex items-baseline gap-2 mt-1">
                <span className="text-2xl font-black text-emerald-600 dark:text-emerald-400">{stats.validas}</span>
                <span className="text-xs text-slate-500 dark:text-slate-400">completos</span>
              </div>
            </div>
            <div className="w-11 h-11 rounded-xl bg-emerald-50 dark:bg-emerald-500/15 border border-emerald-200 dark:border-emerald-500/30 flex items-center justify-center text-emerald-600 dark:text-emerald-400">
              <CheckCircle className="w-5 h-5" />
            </div>
          </div>

          {/* Card 3: Por Revisar */}
          <div
            onClick={() => setFiltroEstado("revision")}
            className={`cursor-pointer bg-white dark:bg-slate-900/80 border rounded-2xl p-4 flex items-center justify-between backdrop-blur-md shadow-sm dark:shadow-lg transition-all ${
              filtroEstado === "revision"
                ? "border-amber-500/70 ring-2 ring-amber-500/40 bg-amber-50/60 dark:bg-amber-500/10"
                : "border-slate-200 dark:border-slate-800/80 hover:border-amber-500/40"
            }`}
            title="Clic para ver personas con datos incompletos pendientes de revisión"
          >
            <div>
              <div className="flex items-center gap-1.5">
                <p className="text-xs font-semibold text-amber-700 dark:text-amber-400/90 uppercase tracking-wider">Por Revisar</p>
                {filtroEstado === "revision" && (
                  <span className="px-1.5 py-0.2 rounded text-[9px] font-bold bg-amber-500/20 text-amber-700 dark:text-amber-300 border border-amber-500/40 animate-pulse">
                    Activo
                  </span>
                )}
              </div>
              <div className="flex items-baseline gap-2 mt-1">
                <span className="text-2xl font-black text-amber-600 dark:text-amber-400">{stats.revision}</span>
                <span className="text-xs text-slate-500 dark:text-slate-400">incompletos</span>
              </div>
            </div>
            <div className="w-11 h-11 rounded-xl bg-amber-50 dark:bg-amber-500/15 border border-amber-200 dark:border-amber-500/30 flex items-center justify-center text-amber-600 dark:text-amber-400">
              <AlertTriangle className="w-5 h-5" />
            </div>
          </div>

          {/* Card 4: Menores de 14 Años */}
          <div
            onClick={() => setFiltroEstado("menores")}
            className={`cursor-pointer bg-white dark:bg-slate-900/80 border rounded-2xl p-4 flex items-center justify-between backdrop-blur-md shadow-sm dark:shadow-lg transition-all ${
              filtroEstado === "menores"
                ? "border-rose-500/70 ring-2 ring-rose-500/40 bg-rose-50/60 dark:bg-rose-500/10"
                : "border-slate-200 dark:border-slate-800/80 hover:border-rose-500/40"
            }`}
            title="Clic para ver personas menores de 14 años detectadas"
          >
            <div>
              <div className="flex items-center gap-1.5">
                <p className="text-xs font-semibold text-rose-700 dark:text-rose-400/90 uppercase tracking-wider">Menores (&lt; 14)</p>
                {filtroEstado === "menores" && (
                  <span className="px-1.5 py-0.2 rounded text-[9px] font-bold bg-rose-500/20 text-rose-700 dark:text-rose-300 border border-rose-500/40 animate-pulse">
                    Activo
                  </span>
                )}
              </div>
              <div className="flex items-baseline gap-2 mt-1">
                <span className="text-2xl font-black text-rose-600 dark:text-rose-400">{stats.menores}</span>
                <span className="text-xs text-slate-500 dark:text-slate-400">detectados</span>
              </div>
            </div>
            <div className="w-11 h-11 rounded-xl bg-rose-50 dark:bg-rose-500/15 border border-rose-200 dark:border-rose-500/30 flex items-center justify-center text-rose-600 dark:text-rose-400">
              <AlertTriangle className="w-5 h-5" />
            </div>
          </div>

          {/* Card 5: Falta en PDF o Excel */}
          <div
            onClick={() => setFiltroEstado("discrepancia")}
            className={`cursor-pointer bg-white dark:bg-slate-900/80 border rounded-2xl p-4 flex items-center justify-between backdrop-blur-md shadow-sm dark:shadow-lg transition-all ${
              filtroEstado === "discrepancia" || filtroEstado === "falta_pdf" || filtroEstado === "falta_excel"
                ? "border-purple-500/70 ring-2 ring-purple-500/40 bg-purple-50/60 dark:bg-purple-500/10"
                : "border-slate-200 dark:border-slate-800/80 hover:border-purple-500/40"
            }`}
            title="Clic para ver personas que faltan en PDF o en la planilla Excel"
          >
            <div>
              <div className="flex items-center gap-1.5">
                <p className="text-xs font-semibold text-purple-700 dark:text-purple-400/90 uppercase tracking-wider">Falta PDF / Excel</p>
                {(filtroEstado === "discrepancia" || filtroEstado === "falta_pdf" || filtroEstado === "falta_excel") && (
                  <span className="px-1.5 py-0.2 rounded text-[9px] font-bold bg-purple-500/20 text-purple-700 dark:text-purple-300 border border-purple-500/40 animate-pulse">
                    Activo
                  </span>
                )}
              </div>
              <div className="flex items-baseline gap-2 mt-1">
                <span className="text-2xl font-black text-purple-600 dark:text-purple-400">{stats.discrepancia}</span>
                <span className="text-xs text-slate-500 dark:text-slate-400">faltantes</span>
              </div>
            </div>
            <div className="w-11 h-11 rounded-xl bg-purple-50 dark:bg-purple-500/15 border border-purple-200 dark:border-purple-500/30 flex items-center justify-center text-purple-600 dark:text-purple-400">
              <AlertCircle className="w-5 h-5" />
            </div>
          </div>
        </div>

        {/* Barra de Búsqueda y Filtros */}
        <div className="grid grid-cols-1 md:grid-cols-12 gap-3 mb-6">
          {/* Búsqueda unificada por cédula, nombres o apellidos */}
          <div className="md:col-span-5 relative">
            <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500 dark:text-slate-400" />
            <input
              id="buscar-persona"
              type="text"
              inputMode="search"
              value={buscar}
              onChange={(e) => setBuscar(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && cargarPersonas(true)}
              placeholder="Buscar por número de cédula o nombre y apellidos..."
              className="w-full pl-10 pr-10 py-2.5 bg-white dark:bg-slate-900/90 border border-slate-300 dark:border-slate-800 rounded-xl text-sm text-slate-900 dark:text-slate-200 placeholder-slate-400 dark:placeholder-slate-500 focus:outline-none focus:border-primary-500 focus:ring-1 focus:ring-primary-500/50 transition-all shadow-sm font-mono sm:font-sans"
            />
            {buscar && (
              <button
                onClick={() => { setBuscar(""); cargarPersonas(true); }}
                className="absolute right-3 top-1/2 -translate-y-1/2 p-0.5 rounded text-slate-500 hover:text-slate-800 dark:hover:text-white transition-colors"
                title="Limpiar búsqueda"
              >
                <X className="w-4 h-4" />
              </button>
            )}
          </div>

          {/* Selector de Documento PDF */}
          <div className="md:col-span-3 relative">
            <FileText className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-primary-600 dark:text-primary-400 pointer-events-none" />
            <select
              value={filtroDocumento}
              onChange={(e) => {
                const val = e.target.value;
                setFiltroDocumento(val);
                setSeleccionados(new Set());
                if (typeof window !== "undefined") {
                  if (val === "todos") {
                    sessionStorage.setItem("ver_todos_los_archivos", "true");
                  } else {
                    sessionStorage.removeItem("ver_todos_los_archivos");
                    localStorage.setItem("ultimo_documento_id", val);
                  }
                }
              }}
              className="w-full pl-9 pr-3 py-2.5 bg-white dark:bg-slate-900/90 border border-slate-300 dark:border-slate-800 rounded-xl text-xs text-slate-900 dark:text-slate-200 focus:outline-none focus:border-primary-500 font-semibold truncate cursor-pointer shadow-sm"
              title="Filtrar por archivo PDF de origen"
            >
              <option value="todos">
                🌐 Ver todos los archivos ({documentos.length} PDFs{totalPersonasGlobal ? ` - Total: ${totalPersonasGlobal} personas` : ""})
              </option>
              {documentos.map((d, index) => (
                <option key={d.id} value={d.id}>
                  📄 {d.nombre_original} {index === 0 ? "★ (Último archivo enviado)" : ""}
                </option>
              ))}
            </select>
          </div>

          {/* Selector de Estado */}
          <div className="md:col-span-3 relative">
            <select
              value={filtroEstado}
              onChange={(e) => setFiltroEstado(e.target.value as FiltroEstado)}
              className={`w-full py-2.5 px-3 border rounded-xl text-xs font-semibold cursor-pointer shadow-sm transition-all ${
                filtroEstado === "revision"
                  ? "border-amber-500 text-amber-900 dark:text-amber-300 bg-amber-50 dark:bg-amber-500/10"
                  : filtroEstado === "validas"
                  ? "border-emerald-500 text-emerald-900 dark:text-emerald-300 bg-emerald-50 dark:bg-emerald-500/10"
                  : filtroEstado === "menores"
                  ? "border-rose-500 text-rose-900 dark:text-rose-300 bg-rose-50 dark:bg-rose-500/10"
                  : filtroEstado === "discrepancia" || filtroEstado === "falta_pdf" || filtroEstado === "falta_excel"
                  ? "border-purple-500 text-purple-900 dark:text-purple-300 bg-purple-50 dark:bg-purple-500/10"
                  : "bg-white dark:bg-slate-900/90 border-slate-300 dark:border-slate-800 text-slate-900 dark:text-slate-200"
              }`}
              title="Filtrar por estado del registro"
            >
              <option value="todos">📋 Todos los estados ({stats.total})</option>
              <option value="validas">✅ Solo Válidos ({stats.validas})</option>
              <option value="revision">⚠️ Por Revisar ({stats.revision})</option>
              <option value="menores">🚨 Menores de 14 Años ({stats.menores})</option>
              <option value="discrepancia">🟣 Falta PDF o Excel ({stats.discrepancia})</option>
              <option value="falta_pdf">📄 Solo Falta en PDF ({stats.faltaPdf})</option>
              <option value="falta_excel">📊 Solo Falta en Excel ({stats.faltaExcel})</option>
            </select>
          </div>

          {/* Recargar */}
          <div className="md:col-span-1 flex justify-end">
            <button
              onClick={recargarManual}
              className="w-full flex items-center justify-center gap-1.5 px-3 py-2.5 bg-white dark:bg-slate-800 hover:bg-slate-100 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 border border-slate-300 dark:border-slate-700/60 rounded-xl text-xs font-semibold transition-all shadow-sm cursor-pointer"
              title="Recargar datos manualmente"
            >
              <RefreshCw className={`w-3.5 h-3.5 text-primary-600 dark:text-primary-400 ${cargando ? "animate-spin" : ""}`} />
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

            <div className="flex items-center gap-2 flex-wrap">
              <button
                onClick={() => setModalEliminarSeleccionadosAbierto(true)}
                disabled={eliminandoEnLote}
                className="px-3.5 py-2 bg-rose-600 hover:bg-rose-500 text-white rounded-xl text-xs font-black transition-all shadow-md shadow-rose-600/30 flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
              >
                <Trash2 className="w-3.5 h-3.5" />
                <span>Eliminar seleccionados ({seleccionados.size})</span>
              </button>

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
                className="px-3 py-2 bg-slate-800/80 hover:bg-slate-700 text-slate-300 rounded-xl text-xs font-semibold border border-slate-700/60 transition-colors cursor-pointer"
              >
                Limpiar selección
              </button>
            </div>
          </div>
        )}

        {/* Barra de estado de la tabla */}
        <div className="flex items-center justify-between mb-3 px-1 flex-wrap gap-2 text-xs">
          <div className="flex items-center gap-2 flex-wrap text-slate-600 dark:text-slate-400 font-medium">
            <span>
              Mostrando <strong className="text-slate-900 dark:text-white font-bold">{personasFiltradas.length}</strong> de <strong className="text-slate-900 dark:text-white font-bold">{stats.total}</strong> personas
            </span>
            {filtroDocumento !== "todos" ? (
              <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md bg-primary-500/10 text-primary-700 dark:text-primary-300 border border-primary-500/20 font-semibold">
                <FileText className="w-3 h-3 text-primary-500" />
                Archivo: {documentos.find(d => d.id === filtroDocumento)?.nombre_original || "Ficha seleccionada"}
                <button
                  type="button"
                  onClick={() => {
                    setFiltroDocumento("todos");
                    setSeleccionados(new Set());
                    if (typeof window !== "undefined") {
                      sessionStorage.setItem("ver_todos_los_archivos", "true");
                    }
                  }}
                  className="ml-1 underline hover:text-primary-900 dark:hover:text-primary-200 cursor-pointer font-bold"
                  title="Ver todas las personas registradas en todos los archivos"
                >
                  (Ver todos los archivos{totalPersonasGlobal ? `: ${totalPersonasGlobal} personas` : ""})
                </button>
              </span>
            ) : (
              <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border border-emerald-500/20 font-semibold">
                🌐 Todos los archivos activos ({documentos.length} PDFs)
              </span>
            )}
          </div>
        </div>

        {/* Tabla */}
        <div className="bg-white dark:bg-slate-900/80 border border-slate-200 dark:border-slate-800/80 rounded-2xl shadow-md dark:shadow-xl overflow-hidden backdrop-blur-md">
          {cargando ? (
            <div className="p-8 space-y-3">
              {Array(6).fill(0).map((_, i) => (
                <div key={i} className="h-12 bg-slate-100 dark:bg-slate-800/40 animate-pulse rounded-xl" />
              ))}
            </div>
          ) : personasFiltradas.length === 0 ? (
            <div className="text-center py-20 px-4">
              <div className="w-14 h-14 mx-auto mb-4 rounded-2xl bg-slate-100 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700/50 flex items-center justify-center text-slate-500">
                <Users className="w-7 h-7" />
              </div>
              <h3 className="text-lg font-semibold text-slate-800 dark:text-slate-300">No se encontraron registros</h3>
              <p className="text-slate-500 text-xs mt-1 max-w-sm mx-auto">
                {buscar ? `Sin resultados para "${buscar}"` : "No hay personas registradas."}
              </p>
              {buscar && (
                <button onClick={() => setBuscar("")} className="mt-3 text-xs text-primary-600 dark:text-primary-400 hover:underline">
                  Limpiar búsqueda
                </button>
              )}
            </div>
          ) : (
            <div className="overflow-x-auto w-full">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-slate-200 dark:border-slate-800/80 bg-slate-100 dark:bg-slate-950/50 text-[11px] font-bold text-slate-700 dark:text-slate-400 uppercase tracking-wider">
                    <th className="py-3 px-2 w-8 text-center">
                      <input
                        type="checkbox"
                        checked={personasFiltradas.length > 0 && personasFiltradas.every((p) => seleccionados.has(p.id))}
                        onChange={toggleSeleccionarTodasVisibles}
                        className="rounded border-slate-400 dark:border-slate-700 bg-white dark:bg-slate-800 text-primary-600 focus:ring-primary-500/40 cursor-pointer"
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
                    const esMenor14 = edadRow !== null && edadRow < 14;
                    const tipoInfo = getTipoDocInfo(p.tipo_documento);

                    return (
                      <Fragment key={p.id}>
                        {/* ── Fila principal ── */}
                        <tr
                          className={`border-b border-slate-200 dark:border-slate-800/30 transition-colors cursor-pointer ${isExpandida
                              ? "bg-blue-50/70 dark:bg-slate-800/40 border-primary-500/30"
                              : isSeleccionada
                                ? "bg-primary-50 dark:bg-primary-500/10 hover:bg-primary-100 dark:hover:bg-primary-500/15"
                                : "hover:bg-slate-50 dark:hover:bg-slate-800/20"
                            }`}
                          onClick={() => toggleExpandir(p)}
                        >
                          {/* Checkbox de selección */}
                          <td className="py-3 px-2 w-8 text-center" onClick={(e) => e.stopPropagation()}>
                            <input
                              type="checkbox"
                              checked={isSeleccionada}
                              onChange={() => toggleSeleccionPersona(p.id)}
                              className="rounded border-slate-400 dark:border-slate-700 bg-white dark:bg-slate-800 text-primary-600 focus:ring-primary-500/40 cursor-pointer"
                            />
                          </td>

                          {/* Toggle expandir */}
                          <td className="py-3 px-1 w-7 text-center">
                            <div className={`w-6 h-6 mx-auto rounded-full flex items-center justify-center transition-all ${isExpandida ? "bg-primary-100 dark:bg-primary-500/20 border border-primary-400 dark:border-primary-500/40 text-primary-700 dark:text-primary-300" : "bg-slate-100 dark:bg-slate-800/60 border border-slate-300 dark:border-slate-700/50 text-slate-600 dark:text-slate-400"}`}>
                              {isExpandida ? <ChevronUp className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                            </div>
                          </td>

                          {/* Documento e ID con Badge - Compacto y pegado al nombre */}
                          <td className="py-3 px-2 w-32 whitespace-nowrap">
                            <div className="flex items-center gap-1.5 flex-nowrap">
                              <span className={`px-1.5 py-0.5 rounded text-[10px] border font-mono tracking-wider shrink-0 ${tipoInfo.badge}`} title={tipoInfo.label}>
                                {tipoInfo.codigo}
                              </span>
                              <span className="font-mono text-blue-900 dark:text-primary-300 font-extrabold text-sm tracking-wide shrink-0">
                                {p.numero_identificacion}
                              </span>
                              {(p.detalles_campos as any)?.numero_identificacion_original_ocr && (
                                <span className="text-[9px] bg-emerald-100 dark:bg-emerald-500/15 border border-emerald-400 dark:border-emerald-500/30 text-emerald-900 dark:text-emerald-300 px-1.5 py-0.5 rounded font-bold flex items-center gap-1 shrink-0 whitespace-nowrap" title={`Número auto-corregido desde planilla Excel oficial (OCR leyó: ${(p.detalles_campos as any).numero_identificacion_original_ocr})`}>
                                  <CheckCircle className="w-2.5 h-2.5" /> Auto-corregido
                                </span>
                              )}
                            </div>
                          </td>

                          {/* Nombre completo */}
                          <td className="py-3 px-2 whitespace-nowrap">
                            {nombreCompleto ? (
                              <span className="text-sm font-semibold text-slate-900 dark:text-slate-100 whitespace-nowrap" title={nombreCompleto}>
                                {nombreCompleto}
                              </span>
                            ) : (
                              <span className="text-slate-400 italic text-xs whitespace-nowrap">Sin nombre</span>
                            )}
                          </td>

                          {/* Edad */}
                          <td className="py-3 px-1 w-16 text-center whitespace-nowrap">
                            {edadRow !== null ? (() => {
                              const inc = verificarInconsistenciaDocumentoEdad(p.tipo_documento, p.fecha_nacimiento, edadRow);
                              if (inc.esInvalido) {
                                return (
                                  <span className="text-[10px] font-mono px-2 py-0.5 rounded-md bg-rose-50 dark:bg-rose-950/50 border border-rose-400 dark:border-rose-700 text-rose-800 dark:text-rose-300 font-bold whitespace-nowrap shadow-sm animate-pulse" title={inc.motivo}>
                                    ⚠️ {edadRow} años
                                  </span>
                                );
                              }
                              return esMenor14 ? (
                                <span className="text-[10px] font-mono px-2 py-0.5 rounded-md bg-rose-50 dark:bg-rose-950/50 border border-rose-300 dark:border-rose-800/60 text-rose-800 dark:text-rose-300 font-bold whitespace-nowrap shadow-sm" title={`Persona menor de 14 años (${edadRow} años)`}>
                                  {edadRow} años
                                </span>
                              ) : (
                                <span className="text-[11px] font-mono px-2 py-0.5 rounded-md bg-amber-500/10 dark:bg-amber-500/15 border border-amber-500/25 dark:border-amber-400/25 text-amber-800 dark:text-amber-300 font-medium whitespace-nowrap shadow-sm">
                                  {edadRow} años
                                </span>
                              );
                            })() : (
                              <span className="text-slate-400 text-xs">—</span>
                            )}
                          </td>

                          {/* Página */}
                          <td className="py-3 px-1 w-12 text-center whitespace-nowrap">
                            <span className="text-[11px] font-mono text-slate-700 dark:text-slate-400 font-semibold whitespace-nowrap">
                              {p.pagina_frente ? `${p.pagina_frente}${p.pagina_reverso ? `/${p.pagina_reverso}` : ""}` : (p.pagina_numero || "—")}
                            </span>
                          </td>

                          {/* Fuente: PDF y/o Excel */}
                          <td className="py-3 px-2 w-28 text-center whitespace-nowrap">
                            <div className="inline-flex items-center justify-center gap-1 whitespace-nowrap">
                              {/* PDF badge */}
                              {p.documento_id ? (
                                <span
                                  className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-rose-500/10 dark:bg-rose-500/15 border border-rose-500/25 dark:border-rose-400/25 text-rose-700 dark:text-rose-300 whitespace-nowrap shrink-0 shadow-sm"
                                  title="Extraído de documento PDF por OCR"
                                >
                                  <FileText className="w-2.5 h-2.5 shrink-0 text-rose-600 dark:text-rose-400" /> PDF
                                </span>
                              ) : (
                                <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-slate-100 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-800 text-slate-400 whitespace-nowrap shrink-0" title="Sin documento PDF asociado">
                                  <FileText className="w-2.5 h-2.5 shrink-0" /> Sin PDF
                                </span>
                              )}
                              {/* Excel badge */}
                              {p.en_excel === true ? (
                                <span
                                  className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-emerald-500/10 dark:bg-emerald-500/15 border border-emerald-500/25 dark:border-emerald-400/25 text-emerald-700 dark:text-emerald-300 whitespace-nowrap shrink-0 shadow-sm"
                                  title="Encontrado en planilla Excel comparada"
                                >
                                  <FileSpreadsheet className="w-2.5 h-2.5 shrink-0 text-emerald-600 dark:text-emerald-400" /> Excel
                                </span>
                              ) : p.en_excel === false ? (
                                <span
                                  className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-rose-500/10 dark:bg-rose-500/15 border border-rose-500/25 dark:border-rose-400/25 text-rose-700 dark:text-rose-300 whitespace-nowrap shrink-0 shadow-sm"
                                  title="No encontrado en ninguna planilla Excel"
                                >
                                  <FileSpreadsheet className="w-2.5 h-2.5 shrink-0 text-rose-600 dark:text-rose-400" /> No Excel
                                </span>
                              ) : null}
                            </div>
                          </td>

                          {/* Estado: Alertas VÁLIDO, REVISAR, MENOR (< 14), NO EN PDF, NO EN EXCEL */}
                          <td className="py-3 px-2 w-28 text-center whitespace-nowrap">
                            <div className="inline-flex flex-col items-center justify-center gap-1 whitespace-nowrap">
                              {/* Alerta: Menor de 14 años */}
                              {esMenor14 && (
                                <span
                                  className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-rose-50 dark:bg-rose-950/40 border border-rose-300 dark:border-rose-800/50 text-rose-800 dark:text-rose-300 text-[10px] font-medium whitespace-nowrap shadow-sm"
                                  title={`Alerta: Persona menor de 14 años detectada (${edadRow} años cumplidos)`}
                                >
                                  <AlertTriangle className="w-2.5 h-2.5 text-rose-600 dark:text-rose-400 shrink-0" /> MENOR (&lt; 14)
                                </span>
                              )}

                              {/* Alerta: Falta en PDF */}
                              {(!p.documento_id || p.en_pdf === false) && (
                                <span
                                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-slate-100 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-700 dark:text-slate-300 text-[10px] font-medium whitespace-nowrap shadow-sm"
                                  title="No tiene documento PDF de cédula asociado"
                                >
                                  <FileText className="w-2.5 h-2.5" /> NO EN PDF
                                </span>
                              )}

                              {/* Alerta: Falta en Excel */}
                              {p.en_excel === false && (
                                <span
                                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-purple-50 dark:bg-purple-950/40 border border-purple-300 dark:border-purple-800/50 text-purple-800 dark:text-purple-300 text-[10px] font-medium whitespace-nowrap shadow-sm"
                                  title="No encontrado en la planilla Excel comparada"
                                >
                                  <FileSpreadsheet className="w-2.5 h-2.5" /> NO EN EXCEL
                                </span>
                              )}

                              {/* Estado de validación de datos: REVISAR o VÁLIDO */}
                              {(() => {
                                const esRevRow = esPersonaEnRevision(p);
                                const inc = verificarInconsistenciaDocumentoEdad(p.tipo_documento, p.fecha_nacimiento, edadRow);
                                const discDocEdad = (p.detalles_campos as any)?.discrepancia_documento_edad;
                                const tooltipMotivo = discDocEdad?.motivo || inc.motivo || (p.detalles_campos as any)?.discrepancia_excel?.motivo || "Requiere revisión manual de datos";

                                if (esRevRow) {
                                  return (
                                    <span
                                      className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-amber-50 dark:bg-amber-950/40 border border-amber-300 dark:border-amber-800/50 text-amber-800 dark:text-amber-300 text-[10px] font-semibold whitespace-nowrap shadow-sm"
                                      title={tooltipMotivo}
                                    >
                                      <AlertTriangle className="w-2.5 h-2.5 text-amber-600 dark:text-amber-400" /> REVISAR
                                    </span>
                                  );
                                } else if (p.documento_id && p.en_excel !== false) {
                                  return (
                                    <span
                                      className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-300 dark:border-emerald-800/50 text-emerald-800 dark:text-emerald-300 text-[10px] font-medium whitespace-nowrap shadow-sm"
                                      title="Registro completo y verificado"
                                    >
                                      <CheckCircle className="w-2.5 h-2.5 text-emerald-600 dark:text-emerald-400" /> VÁLIDO
                                    </span>
                                  );
                                }
                                return null;
                              })()}
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
                <div className="flex items-center gap-4 text-[11px] text-slate-500 flex-wrap">
                  <span className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                    <strong className="text-slate-300 font-semibold">{stats.validas}</strong> Válidas
                  </span>
                  <span className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-amber-400" />
                    <strong className="text-slate-300 font-semibold">{stats.revision}</strong> Por revisar
                  </span>
                  <span className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-rose-400 animate-pulse" />
                    <strong className="text-rose-300 font-semibold">{stats.menores}</strong> Menores (&lt; 14)
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

        {/* Modal Confirmar Vaciar Tabla */}
        {modalVaciarAbierto && (
          <div
            className="fixed inset-0 z-50 bg-slate-950/75 backdrop-blur-md flex items-center justify-center p-4 animate-in fade-in duration-200"
            onClick={() => !eliminandoEnLote && setModalVaciarAbierto(false)}
          >
            <div
              className="bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-800 rounded-3xl shadow-2xl w-full max-w-md p-6 overflow-hidden animate-in zoom-in-95 duration-200"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="w-14 h-14 rounded-2xl bg-rose-100 dark:bg-rose-500/20 border-2 border-rose-500/40 flex items-center justify-center text-rose-600 dark:text-rose-400 mx-auto mb-4">
                <Trash2 className="w-7 h-7" />
              </div>

              <h3 className="text-xl font-black text-slate-900 dark:text-white text-center">
                ¿Vaciar tabla de personas?
              </h3>

              <p className="text-xs text-slate-600 dark:text-slate-400 text-center mt-2 leading-relaxed">
                {filtroDocumento !== "todos" ? (
                  <>
                    Estás a punto de eliminar permanentemente todas las personas del archivo{" "}
                    <strong className="text-slate-900 dark:text-white">
                      {documentos.find((d) => d.id === filtroDocumento)?.nombre_original || "seleccionado"}
                    </strong>{" "}
                    (<span className="font-bold text-rose-600 dark:text-rose-400">{stats.total} registros</span>).
                  </>
                ) : (
                  <>
                    Estás a punto de eliminar permanentemente{" "}
                    <strong className="text-rose-600 dark:text-rose-400 font-bold">{stats.total} registros</strong>{" "}
                    de la tabla de personas.
                  </>
                )}
              </p>

              <div className="p-3 my-4 rounded-xl bg-amber-50 dark:bg-amber-950/40 border border-amber-300 dark:border-amber-700 text-amber-900 dark:text-amber-200 text-xs font-semibold flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-amber-600 dark:text-amber-400 shrink-0" />
                <span>Esta acción no se puede deshacer. Todos los datos asociados se borrarán permanentemente.</span>
              </div>

              <div className="flex items-center justify-end gap-3 mt-5">
                <button
                  type="button"
                  onClick={() => setModalVaciarAbierto(false)}
                  disabled={eliminandoEnLote}
                  className="px-4 py-2.5 rounded-xl bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 text-xs font-bold transition-all cursor-pointer disabled:opacity-50"
                >
                  Cancelar
                </button>
                <button
                  type="button"
                  onClick={ejecutarVaciarTabla}
                  disabled={eliminandoEnLote}
                  className="px-5 py-2.5 rounded-xl bg-rose-600 hover:bg-rose-700 text-white text-xs font-black transition-all cursor-pointer shadow-lg shadow-rose-600/30 flex items-center gap-2 disabled:opacity-50"
                >
                  {eliminandoEnLote ? (
                    <>
                      <div className="spinner w-3.5 h-3.5 border-white" />
                      <span>Vaciando tabla...</span>
                    </>
                  ) : (
                    <>
                      <Trash2 className="w-3.5 h-3.5" />
                      <span>Sí, vaciar tabla</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Modal Confirmar Eliminar Seleccionados */}
        {modalEliminarSeleccionadosAbierto && (
          <div
            className="fixed inset-0 z-50 bg-slate-950/75 backdrop-blur-md flex items-center justify-center p-4 animate-in fade-in duration-200"
            onClick={() => !eliminandoEnLote && setModalEliminarSeleccionadosAbierto(false)}
          >
            <div
              className="bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-800 rounded-3xl shadow-2xl w-full max-w-md p-6 overflow-hidden animate-in zoom-in-95 duration-200"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="w-14 h-14 rounded-2xl bg-rose-100 dark:bg-rose-500/20 border-2 border-rose-500/40 flex items-center justify-center text-rose-600 dark:text-rose-400 mx-auto mb-4">
                <Trash2 className="w-7 h-7" />
              </div>

              <h3 className="text-xl font-black text-slate-900 dark:text-white text-center">
                ¿Eliminar personas seleccionadas?
              </h3>

              <p className="text-xs text-slate-600 dark:text-slate-400 text-center mt-2 leading-relaxed">
                Has seleccionado{" "}
                <strong className="text-rose-600 dark:text-rose-400 font-bold">{seleccionados.size} {seleccionados.size === 1 ? "persona" : "personas"}</strong>.
                ¿Deseas eliminarlas definitivamente de la tabla de personas?
              </p>

              <div className="p-3 my-4 rounded-xl bg-amber-50 dark:bg-amber-950/40 border border-amber-300 dark:border-amber-700 text-amber-900 dark:text-amber-200 text-xs font-semibold flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-amber-600 dark:text-amber-400 shrink-0" />
                <span>Esta acción eliminará estos registros de forma permanente.</span>
              </div>

              <div className="flex items-center justify-end gap-3 mt-5">
                <button
                  type="button"
                  onClick={() => setModalEliminarSeleccionadosAbierto(false)}
                  disabled={eliminandoEnLote}
                  className="px-4 py-2.5 rounded-xl bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 text-xs font-bold transition-all cursor-pointer disabled:opacity-50"
                >
                  Cancelar
                </button>
                <button
                  type="button"
                  onClick={ejecutarEliminarSeleccionados}
                  disabled={eliminandoEnLote}
                  className="px-5 py-2.5 rounded-xl bg-rose-600 hover:bg-rose-700 text-white text-xs font-black transition-all cursor-pointer shadow-lg shadow-rose-600/30 flex items-center gap-2 disabled:opacity-50"
                >
                  {eliminandoEnLote ? (
                    <>
                      <div className="spinner w-3.5 h-3.5 border-white" />
                      <span>Eliminando...</span>
                    </>
                  ) : (
                    <>
                      <Trash2 className="w-3.5 h-3.5" />
                      <span>Sí, eliminar seleccionados</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        )}
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

export default function PersonasPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen bg-[#0b0f19] text-slate-100 items-center justify-center">
          <div className="flex flex-col items-center gap-3">
            <div className="w-8 h-8 border-2 border-primary-500 border-t-transparent rounded-full animate-spin" />
            <p className="text-xs text-slate-400 font-medium">Cargando módulo de personas...</p>
          </div>
        </div>
      }
    >
      <PersonasContent />
    </Suspense>
  );
}
