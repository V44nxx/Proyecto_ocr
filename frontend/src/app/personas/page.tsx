"use client";

import { useState, useEffect, useRef, Fragment, Suspense } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import toast from "react-hot-toast";
import {
  Users, Search, AlertTriangle, AlertCircle, CheckCircle,
  Edit3, Save, X, RefreshCw, Trash2, Calendar, MapPin,
  UserCheck, FileText, Eye, Hash, Clock, Cpu,
  Download, CheckSquare, Square, UploadCloud, FileSpreadsheet, Check,
  ChevronDown, ChevronRight, Copy, ExternalLink, ShieldCheck, FileCheck2
} from "lucide-react";
import Sidebar from "@/components/ui/Sidebar";
import SelectorFicha, { TODAS_LAS_FICHAS } from "@/components/personas/SelectorFicha";
import VisorDocumento from "@/components/personas/VisorDocumento";
import { useSidebar } from "@/context/SidebarContext";
import { useBloquearScroll } from "@/hooks/useBloquearScroll";
import { apiPersonas, apiDocumentos, apiExportacion, getErrorMessage } from "@/lib/api";
import { auth } from "@/lib/auth";
import { formatNombreCompleto, calcularEdad, verificarInconsistenciaDocumentoEdad, getTipoDocInfo } from "@/lib/formatters";
import type { Persona, PersonaUpdate, Documento } from "@/types";

// ─── Helpers de Clasificación ──────────────────────────────────────────────
const personaFaltaEnPdf = (p: Persona): boolean => {
  if (!p) return false;
  if (p.en_pdf === false) return true;
  if (!p.documento_id && !p.documento_pdf_id) return true;
  const det = p.detalles_campos as any;
  if (det && det.en_pdf === false) return true;
  if (det && det.origen === "excel_no_encontrado_en_pdf") return true;
  return false;
};

const personaFaltaEnExcel = (p: Persona): boolean => {
  if (!p) return false;
  if (p.en_excel === false) return true;
  const det = p.detalles_campos as any;
  if (det && det.en_excel === false) return true;
  return false;
};

const personaTieneDiscrepanciaFaltante = (p: Persona): boolean => {
  if (!p) return false;
  const faltaPdf = personaFaltaEnPdf(p);
  const faltaExcel = personaFaltaEnExcel(p);
  const discExcel = p.discrepancia_excel || (p.detalles_campos as any)?.discrepancia_excel;
  const tieneDiscExcel = Boolean(discExcel && !discExcel.aprobado_manual && !discExcel.ignorado);
  return faltaPdf || faltaExcel || tieneDiscExcel;
};

const esPersonaValidada = (p: Persona): boolean => {
  if (!p) return false;
  if ((p.detalles_campos as any)?.aprobado_manual === true || (p.detalles_campos as any)?.validado_manual === true) {
    return true;
  }
  if (personaFaltaEnPdf(p) || personaFaltaEnExcel(p)) {
    return false;
  }
  return Boolean(
    p.requiere_revision === false ||
    p.estado_registro === "VALID"
  );
};

const esPersonaEnRevision = (p: Persona): boolean => {
  if (!p) return false;
  if (esPersonaValidada(p)) return false;
  if (personaFaltaEnPdf(p) || personaFaltaEnExcel(p)) return true;
  const edad = p.edad ?? calcularEdad(p.fecha_nacimiento);
  const inc = verificarInconsistenciaDocumentoEdad(p.tipo_documento, p.fecha_nacimiento, edad);
  const discDocEdad = (p.detalles_campos as any)?.discrepancia_documento_edad;
  const discDocEdadAprobada = discDocEdad && (discDocEdad.aprobado_manual || discDocEdad.ignorado);
  const discExcel = p.discrepancia_excel || (p.detalles_campos as any)?.discrepancia_excel;
  const discExcelAprobada = discExcel && (discExcel.aprobado_manual || discExcel.ignorado);

  return Boolean(
    p.requiere_revision || 
    (p.estado_registro && p.estado_registro !== "VALID") || 
    (!discDocEdadAprobada && inc.esInvalido) || 
    (!discDocEdadAprobada && discDocEdad) ||
    (!discExcelAprobada && discExcel)
  );
};

const formatearCedulaPuntos = (val: string | number | undefined | null): string => {
  if (!val) return "—";
  const str = String(val).trim();
  if (str.startsWith("SIN_ID")) return "Sin doc.";
  const soloDigitos = str.replace(/\D/g, "");
  if (soloDigitos.length >= 4) {
    return soloDigitos.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  }
  return str;
};

const formatearFechaCO = (val: string | undefined | null): string => {
  if (!val) return "—";
  const str = String(val).trim();
  const partes = str.split(/[-/]/);
  if (partes.length === 3) {
    if (partes[0].length === 4) {
      return `${partes[2]}/${partes[1]}/${partes[0]}`;
    }
  }
  return str;
};

const textoSexo = (val: string | undefined | null): string => {
  const v = (val || "").trim().toUpperCase();
  if (v.startsWith("F")) return "Femenino";
  if (v.startsWith("M")) return "Masculino";
  return v || "Sin dato";
};

const getMotivoExplicacion = (p: Persona): string => {
  if (personaFaltaEnExcel(p)) {
    return "La cédula se leyó bien en el PDF, pero no está en la planilla Excel cargada.";
  }
  if (personaFaltaEnPdf(p)) {
    return "La persona está registrada en la planilla Excel, pero no se encontró su cédula en el PDF.";
  }
  const discExcel = p.discrepancia_excel || (p.detalles_campos as any)?.discrepancia_excel;
  if (discExcel && !discExcel.aprobado_manual) {
    if (discExcel.campo === "apellidos" || discExcel.motivo?.toLowerCase().includes("apellido")) {
      return "El segundo apellido es distinto entre el PDF y el Excel.";
    }
    return discExcel.motivo || "Existen diferencias entre los datos leídos del PDF y la planilla Excel.";
  }
  const edad = p.edad ?? calcularEdad(p.fecha_nacimiento);
  const inc = verificarInconsistenciaDocumentoEdad(p.tipo_documento, p.fecha_nacimiento, edad);
  if (inc.esInvalido) {
    return inc.motivo || "Inconsistencia detectada entre el tipo de documento y la edad calculada.";
  }
  const confGeneral = p.confianza_extraccion != null ? Number(p.confianza_extraccion) : 90;
  if (confGeneral < 70) {
    return "La fecha de nacimiento se leyó con baja confianza. Confírmala contra la imagen.";
  }
  const motivosRev = (p.detalles_campos as any)?.motivos_revision;
  if (Array.isArray(motivosRev) && motivosRev.length > 0) {
    return motivosRev[0];
  }
  if (esPersonaValidada(p)) {
    return "Todos los datos han sido validados exitosamente y coinciden con los registros.";
  }
  return "Uno o más datos esenciales requieren verificación.";
};

const getEstadoConfig = (p: Persona) => {
  if (personaFaltaEnExcel(p)) {
    return {
      key: "falta_excel",
      label: "Falta en Excel",
      colorHex: "#ec4899",
      badgeClass: "text-[#ec4899] font-medium",
      iconType: "square",
    };
  }
  if (personaFaltaEnPdf(p)) {
    return {
      key: "falta_pdf",
      label: "Falta en PDF",
      colorHex: "#c084fc",
      badgeClass: "text-[#d8b4fe] font-medium",
      iconType: "outline_square",
    };
  }
  if (esPersonaValidada(p)) {
    return {
      key: "valido",
      label: "Válido",
      colorHex: "#34d399",
      badgeClass: "text-[#34d399] font-medium",
      iconType: "dot",
    };
  }
  return {
    key: "revision",
    label: "Por revisar",
    colorHex: "#fbbf24",
    badgeClass: "text-[#fbbf24] font-medium",
    iconType: "triangle",
  };
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
  
  type FiltroEstado = "todos" | "validas" | "revision" | "falta_excel" | "falta_pdf" | "discrepancia" | "menores";
  const [filtroEstado, setFiltroEstado] = useState<FiltroEstado>("todos");

  // Persona seleccionada para el Drawer Lateral
  const [personaSeleccionadaId, setPersonaSeleccionadaId] = useState<string | null>(null);
  const [verMasDatos, setVerMasDatos] = useState(false);

  // Edición
  const [editando, setEditando] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<PersonaUpdate>({});
  // El formulario tiene un solo campo de nombre: si se edita, nombres pasa a ser el nombre completo y apellidos queda vacío
  const [nombreEditado, setNombreEditado] = useState(false);

  // Estadísticas
  const [stats, setStats] = useState({
    total: 0,
    validas: 0,
    revision: 0,
    discrepancia: 0,
    faltaPdf: 0,
    faltaExcel: 0,
    menores: 0,
  });

  // Modales
  const [modalVaciarAbierto, setModalVaciarAbierto] = useState(false);
  const [modalEliminarSeleccionadosAbierto, setModalEliminarSeleccionadosAbierto] = useState(false);
  const [eliminandoEnLote, setEliminandoEnLote] = useState(false);

  // Modal de Vista Previa de Documento PDF
  const [modalPdfAbierto, setModalPdfAbierto] = useState(false);
  const [personaPdfModal, setPersonaPdfModal] = useState<Persona | null>(null);
  const [paginaPreviaModal, setPaginaPreviaModal] = useState<number>(1);

  // Subida de PDF individual para persona
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

      const verTodosManual = typeof window !== "undefined" && sessionStorage.getItem("ver_todos_los_archivos") === "true";
      if (verTodosManual) {
        setFiltroDocumento("todos");
        setDocumentosCargados(true);
        return;
      }

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
      const validasCount = items.filter(esPersonaValidada).length;
      const revCount = items.filter((p: Persona) => !esPersonaValidada(p) && esPersonaEnRevision(p)).length;
      const faltaPdfCount = items.filter(personaFaltaEnPdf).length;
      const faltaExcelCount = items.filter(personaFaltaEnExcel).length;
      const discCount = items.filter(personaTieneDiscrepanciaFaltante).length;
      const menoresCount = items.filter((p: Persona) => {
        const ed = p.edad ?? calcularEdad(p.fecha_nacimiento);
        return ed !== null && ed < 14;
      }).length;

      setStats({
        total: tot,
        revision: revCount,
        validas: validasCount,
        discrepancia: discCount,
        faltaPdf: faltaPdfCount,
        faltaExcel: faltaExcelCount,
        menores: menoresCount,
      });

      if (!docIdFiltro && tot > 0) {
        setTotalPersonasGlobal(tot);
      }

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

  const personaActiva = personas.find((p) => p.id === personaSeleccionadaId) || null;

  // Con el panel o un modal abierto solo se desplaza su contenido, no la página de fondo
  useBloquearScroll(Boolean(personaActiva) || modalVaciarAbierto || modalEliminarSeleccionadosAbierto);

  const abrirDetalleDrawer = (p: Persona) => {
    setPersonaSeleccionadaId(p.id);
    setEditando(null);
    setVerMasDatos(false);
    precargarPaginaPersona(p);
  };

  const cerrarDetalleDrawer = () => {
    setPersonaSeleccionadaId(null);
    setEditando(null);
    setVerMasDatos(false);
  };

  const seleccionarFicha = (id: string) => {
    setFiltroDocumento(id);
    setPersonaSeleccionadaId(null);
    setSeleccionados(new Set());
    if (typeof window !== "undefined") {
      if (id === TODAS_LAS_FICHAS) {
        sessionStorage.setItem("ver_todos_los_archivos", "true");
      } else {
        sessionStorage.removeItem("ver_todos_los_archivos");
        localStorage.setItem("ultimo_documento_id", id);
      }
    }
    router.replace(id === TODAS_LAS_FICHAS ? pathname : `${pathname}?documento_id=${encodeURIComponent(id)}`, { scroll: false });
  };

  const precargarPaginaPersona = (p: Persona) => {
    const docId = p.documento_pdf_id || p.documento_id;
    if (!docId) return;
    const pagsList = (p.detalles_campos as any)?.paginas;
    const pag = (Array.isArray(pagsList) && pagsList.length > 0 ? pagsList[0] : null) || p.pagina_frente || p.pagina_numero || 1;
    if (pag) {
      const img = new Image();
      img.src = apiDocumentos.paginaPdfUrl(String(docId), pag, 130);
    }
  };

  const abrirModalPdf = (p: Persona) => {
    setPersonaPdfModal(p);
    const pagsList = (p.detalles_campos as any)?.paginas;
    const pagInicial = (Array.isArray(pagsList) && pagsList.length > 0 ? pagsList[0] : null) || p.pagina_frente || p.pagina_numero || 1;
    setPaginaPreviaModal(pagInicial);
    setModalPdfAbierto(true);
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
        `¡PDF individual vinculado y datos extraídos exitosamente para ${personaActualizada.numero_identificacion}!`,
        { id: toastId }
      );

      await cargarPersonas(false);
      setPersonaSeleccionadaId(personaActualizada.id);
    } catch (err: unknown) {
      const msg = getErrorMessage(err, "Error al procesar el PDF de la cédula");
      toast.error(msg, { id: toastId });
    } finally {
      setSubiendoPdfId(null);
      setPersonaParaPdf(null);
    }
  };

  const iniciarEdicion = (p: Persona) => {
    setEditando(p.id);
    setNombreEditado(false);
    const nomCompleto = formatNombreCompleto(p);
    const numIdLimpio = p.numero_identificacion?.startsWith("SIN_ID") ? "" : (p.numero_identificacion || "");
    setEditForm({
      numero_identificacion: numIdLimpio,
      tipo_documento: p.tipo_documento || "CEDULA_CIUDADANIA",
      nombre_completo: nomCompleto,
      nombres: p.nombres || "",
      apellidos: p.apellidos || "",
      fecha_nacimiento: p.fecha_nacimiento ? String(p.fecha_nacimiento) : "",
      fecha_expedicion: p.fecha_expedicion ? String(p.fecha_expedicion) : "",
      lugar_expedicion: p.lugar_expedicion || "",
      sexo: textoSexo(p.sexo) === "Femenino" ? "F" : textoSexo(p.sexo) === "Masculino" ? "M" : p.sexo || "",
      requiere_revision: undefined,
    });
  };

  const guardarEdicion = async (id: string, forzarAprobado = false) => {
    try {
      const payload: PersonaUpdate = {
        ...editForm,
        numero_identificacion: editForm.numero_identificacion?.trim() || undefined,
        nombre_completo: editForm.nombre_completo?.trim() || undefined,
        nombres: nombreEditado ? editForm.nombre_completo?.trim() || undefined : undefined,
        apellidos: nombreEditado && editForm.nombre_completo?.trim() ? "" : undefined,
        fecha_nacimiento: editForm.fecha_nacimiento?.trim() || undefined,
        fecha_expedicion: editForm.fecha_expedicion?.trim() || undefined,
        lugar_expedicion: editForm.lugar_expedicion?.trim() || undefined,
        sexo: editForm.sexo?.trim() || undefined,
        ...(forzarAprobado ? { requiere_revision: false, estado_registro: "VALID" } : {}),
      };
      await apiPersonas.actualizar(id, payload);
      toast.success(forzarAprobado ? "Datos guardados y persona validada" : "Datos actualizados correctamente", { id: "guardar-persona" });
      setEditando(null);
      cargarPersonas(true);
    } catch (err: unknown) {
      const msg = getErrorMessage(err, "Error guardando cambios");
      toast.error(msg, { id: "guardar-persona" });
    }
  };

  const eliminar = async (id: string, cedula: string) => {
    if (!confirm(`¿Desea eliminar el registro de la persona con cédula ${cedula}?`)) return;
    try {
      await apiPersonas.eliminar(id);
      toast.success("Registro eliminado", { id: "eliminar-persona" });
      if (personaSeleccionadaId === id) setPersonaSeleccionadaId(null);
      cargarPersonas(true);
    } catch {
      toast.error("Error al eliminar registro", { id: "eliminar-persona" });
    }
  };

  const aprobarRevision = async (id: string, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    try {
      setPersonas((prev) =>
        prev.map((item) => {
          if (item.id === id) {
            const det = { ...(item.detalles_campos as any || {}) };
            delete det.motivos_revision;
            det.aprobado_manual = true;
            det.validado_manual = true;
            if (det.discrepancia_excel) {
              det.discrepancia_excel = { ...det.discrepancia_excel, aprobado_manual: true };
            }
            if (det.discrepancia_documento_edad) {
              det.discrepancia_documento_edad = { ...det.discrepancia_documento_edad, aprobado_manual: true };
            }
            return {
              ...item,
              requiere_revision: false,
              estado_registro: "VALID",
              detalles_campos: det,
              discrepancia_excel: item.discrepancia_excel
                ? { ...(item.discrepancia_excel as any), aprobado_manual: true }
                : item.discrepancia_excel,
            };
          }
          return item;
        })
      );
      await apiPersonas.actualizar(id, { requiere_revision: false, estado_registro: "VALID" });
      toast.success("Persona verificada y aprobada como válida", { id: `aprobar-${id}` });
      await cargarPersonas(false);
    } catch {
      toast.error("Error al aprobar persona", { id: `aprobar-${id}` });
    }
  };

  const copiarAlPortapapeles = (texto: string, etiqueta = "Cédula", e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    if (typeof navigator !== "undefined" && navigator.clipboard) {
      navigator.clipboard.writeText(texto);
      toast.success(`${etiqueta} copiada: ${texto}`, { id: `copy-${texto}` });
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
      if (personaSeleccionadaId && seleccionados.has(personaSeleccionadaId)) setPersonaSeleccionadaId(null);
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
      setPersonaSeleccionadaId(null);
      setModalVaciarAbierto(false);
      cargarPersonas(true);
    } catch (err: unknown) {
      const msg = getErrorMessage(err, "Error al vaciar la tabla de personas");
      toast.error(msg, { id: toastId });
    } finally {
      setEliminandoEnLote(false);
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

  const exportarSeleccion = async () => {
    if (seleccionados.size === 0) return;
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

  // Filtrado de Personas
  const personasFiltradas = (personas || []).filter((p) => {
    if (!p) return false;
    const estaVal = esPersonaValidada(p);
    const esRev = esPersonaEnRevision(p);

    if (filtroEstado === "validas") {
      if (!estaVal) return false;
    } else if (filtroEstado === "revision") {
      if (estaVal || !esRev) return false;
    } else if (filtroEstado === "falta_excel") {
      if (!personaFaltaEnExcel(p)) return false;
    } else if (filtroEstado === "falta_pdf") {
      if (!personaFaltaEnPdf(p)) return false;
    } else if (filtroEstado === "discrepancia") {
      if (!personaTieneDiscrepanciaFaltante(p)) return false;
    } else if (filtroEstado === "menores") {
      const ed = p.edad ?? calcularEdad(p.fecha_nacimiento);
      if (ed === null || ed >= 14) return false;
    }

    if (!buscar) return true;
    const q = buscar.toLowerCase().trim().replace(/[.\s]/g, "");
    const cedula = String(p.numero_identificacion || "").replace(/[.\s]/g, "");
    const nom = formatNombreCompleto(p).toLowerCase();
    return cedula.includes(q) || nom.includes(q);
  });

  // Lista de personas pendientes de resolver
  const personasPorResolver = (personas || []).filter((p) => {
    return personaFaltaEnExcel(p) || personaFaltaEnPdf(p) || (!esPersonaValidada(p) && esPersonaEnRevision(p));
  });

  // Porcentajes para la barra superior
  const totalBase = stats.total > 0 ? stats.total : personas.length;
  const pctValidas = totalBase > 0 ? Math.round((stats.validas / totalBase) * 100) : 0;
  const pctRevision = totalBase > 0 ? Math.round((stats.revision / totalBase) * 100) : 0;
  const pctFaltaExcel = totalBase > 0 ? Math.round((stats.faltaExcel / totalBase) * 100) : 0;
  const pctFaltaPdf = totalBase > 0 ? Math.round((stats.faltaPdf / totalBase) * 100) : 0;

  // Selección múltiple
  const toggleSeleccionarTodas = () => {
    const todosVisibles = personasFiltradas.length > 0 && personasFiltradas.every((p) => seleccionados.has(p.id));
    if (todosVisibles) {
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

  const toggleSeleccionFila = (id: string, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    setSeleccionados((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  return (
    <div className="flex min-h-screen bg-[#F5F5F7] dark:bg-[#0A0D14] text-slate-900 dark:text-slate-100 font-sans w-full max-w-full overflow-x-hidden transition-colors duration-200">
      <Sidebar />
      <main
        className={`flex-1 min-w-0 p-4 sm:p-6 lg:p-8 transition-all duration-300 ${
          collapsed ? "ml-16 sm:ml-20" : "ml-64 sm:ml-72"
        }`}
      >
        {/* ─── Encabezado Principal ─── */}
        <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 mb-6">
          <div className="min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-[10px] font-bold tracking-widest text-slate-500 dark:text-slate-400 uppercase">
                KONDID · BASE DE DATOS OCR
              </span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 dark:text-white tracking-tight">
              Personas registradas
            </h1>
            <div className="mt-4">
              <SelectorFicha documentos={documentos} valor={filtroDocumento} onCambiar={seleccionarFicha} />
            </div>
          </div>

          <div className="flex items-center gap-2.5 shrink-0 self-start sm:self-end">
            <button
              onClick={() => setModalVaciarAbierto(true)}
              disabled={personas.length === 0}
              className="px-4 py-2 rounded-xl text-xs font-semibold bg-white/80 dark:bg-white/[0.06] hover:bg-slate-100 dark:hover:bg-white/[0.1] text-slate-700 dark:text-slate-200 border border-slate-200/80 dark:border-white/[0.08] transition-all shadow-sm disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
              title="Vaciar todos los registros de la tabla"
            >
              Vaciar tabla
            </button>
            <button
              onClick={exportarVistaActual}
              disabled={exportando || personas.length === 0}
              className="px-4 py-2 rounded-xl text-xs font-semibold bg-[#0071E3] hover:bg-[#0077ED] text-white transition-all shadow-sm shadow-[#0071E3]/20 disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer flex items-center gap-2"
              title="Exportar registros a archivo Excel (.xlsx)"
            >
              <Download className="w-3.5 h-3.5" />
              <span>Exportar a Excel</span>
            </button>
          </div>
        </div>

        {/* ─── Barra de Estadísticas Proporcional + Cajas Interactivas ─── */}
        <div className="mb-8 p-4 sm:p-5 rounded-2xl bg-white/80 dark:bg-[#121620]/60 backdrop-blur-xl border border-slate-200/80 dark:border-white/[0.08] shadow-[0_2px_12px_rgba(0,0,0,0.03)] dark:shadow-[0_4px_24px_rgba(0,0,0,0.25)]">
          {/* Barra segmentada con proporciones reales */}
          <div className="w-full h-3 rounded-full bg-slate-200/80 dark:bg-white/[0.08] overflow-hidden flex mb-5 p-0.5 gap-1">
            {stats.validas > 0 && (
              <div
                onClick={() => setFiltroEstado("validas")}
                style={{ width: `${Math.max(4, pctValidas)}%` }}
                className="h-full bg-[#34d399] rounded-full cursor-pointer hover:brightness-110 transition-all"
                title={`Válidos: ${stats.validas} (${pctValidas}%) - Clic para filtrar`}
              />
            )}
            {stats.revision > 0 && (
              <div
                onClick={() => setFiltroEstado("revision")}
                style={{ width: `${Math.max(4, pctRevision)}%` }}
                className="h-full bg-[#f59e0b] rounded-full cursor-pointer hover:brightness-110 transition-all"
                title={`Por revisar: ${stats.revision} (${pctRevision}%) - Clic para filtrar`}
              />
            )}
            {stats.faltaExcel > 0 && (
              <div
                onClick={() => setFiltroEstado("falta_excel")}
                style={{ width: `${Math.max(4, pctFaltaExcel)}%` }}
                className="h-full bg-[#ec4899] rounded-full cursor-pointer hover:brightness-110 transition-all"
                title={`Falta en Excel: ${stats.faltaExcel} (${pctFaltaExcel}%) - Clic para filtrar`}
              />
            )}
            {stats.faltaPdf > 0 && (
              <div
                onClick={() => setFiltroEstado("falta_pdf")}
                style={{ width: `${Math.max(4, pctFaltaPdf)}%` }}
                className="h-full bg-[repeating-linear-gradient(45deg,#d946ef,#d946ef_4px,#a855f7_4px,#a855f7_8px)] rounded-full cursor-pointer hover:brightness-110 transition-all"
                title={`Falta en PDF: ${stats.faltaPdf} (${pctFaltaPdf}%) - Clic para filtrar`}
              />
            )}
          </div>

          {/* 5 Cajas Interactivas */}
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
            {/* 1. Todos */}
            <button
              type="button"
              onClick={() => setFiltroEstado("todos")}
              className={`p-3.5 rounded-xl text-left transition-all cursor-pointer ${
                filtroEstado === "todos"
                  ? "bg-indigo-50/80 dark:bg-white/[0.1] border-2 border-indigo-500 shadow-sm"
                  : "bg-slate-50/70 dark:bg-white/[0.03] hover:bg-slate-100/70 dark:hover:bg-white/[0.06] border border-slate-200/70 dark:border-white/[0.06]"
              }`}
            >
              <span className="text-xs text-slate-500 dark:text-slate-400 font-medium block">Todos</span>
              <div className="text-2xl sm:text-3xl font-extrabold text-slate-900 dark:text-white mt-1 tracking-tight font-mono">
                {totalBase}
              </div>
              <span className="text-[11px] text-slate-400 dark:text-slate-500 block mt-0.5">
                {filtroDocumento !== "todos" ? "en este archivo" : "en el sistema"}
              </span>
            </button>

            {/* 2. Válido */}
            <button
              type="button"
              onClick={() => setFiltroEstado("validas")}
              className={`p-3.5 rounded-xl text-left transition-all cursor-pointer ${
                filtroEstado === "validas"
                  ? "bg-emerald-50/80 dark:bg-white/[0.1] border-2 border-emerald-500 shadow-sm"
                  : "bg-slate-50/70 dark:bg-white/[0.03] hover:bg-slate-100/70 dark:hover:bg-white/[0.06] border border-slate-200/70 dark:border-white/[0.06]"
              }`}
            >
              <span className="text-xs text-emerald-600 dark:text-emerald-400 font-medium flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-emerald-500"></span> Válido
              </span>
              <div className="text-2xl sm:text-3xl font-extrabold text-slate-900 dark:text-white mt-1 tracking-tight font-mono">
                {stats.validas}
              </div>
              <span className="text-[11px] text-slate-400 dark:text-slate-500 block mt-0.5 font-mono">{pctValidas}%</span>
            </button>

            {/* 3. Por revisar */}
            <button
              type="button"
              onClick={() => setFiltroEstado("revision")}
              className={`p-3.5 rounded-xl text-left transition-all cursor-pointer ${
                filtroEstado === "revision"
                  ? "bg-amber-50/80 dark:bg-white/[0.1] border-2 border-amber-500 shadow-sm"
                  : "bg-slate-50/70 dark:bg-white/[0.03] hover:bg-slate-100/70 dark:hover:bg-white/[0.06] border border-slate-200/70 dark:border-white/[0.06]"
              }`}
            >
              <span className="text-xs text-amber-600 dark:text-amber-400 font-medium flex items-center gap-1.5">
                <span>▲</span> Por revisar
              </span>
              <div className="text-2xl sm:text-3xl font-extrabold text-slate-900 dark:text-white mt-1 tracking-tight font-mono">
                {stats.revision}
              </div>
              <span className="text-[11px] text-slate-400 dark:text-slate-500 block mt-0.5 font-mono">{pctRevision}%</span>
            </button>

            {/* 4. Falta en Excel */}
            <button
              type="button"
              onClick={() => setFiltroEstado("falta_excel")}
              className={`p-3.5 rounded-xl text-left transition-all cursor-pointer ${
                filtroEstado === "falta_excel"
                  ? "bg-pink-50/80 dark:bg-white/[0.1] border-2 border-pink-500 shadow-sm"
                  : "bg-slate-50/70 dark:bg-white/[0.03] hover:bg-slate-100/70 dark:hover:bg-white/[0.06] border border-slate-200/70 dark:border-white/[0.06]"
              }`}
            >
              <span className="text-xs text-pink-600 dark:text-pink-400 font-medium flex items-center gap-1.5">
                <span>■</span> Falta en Excel
              </span>
              <div className="text-2xl sm:text-3xl font-extrabold text-slate-900 dark:text-white mt-1 tracking-tight font-mono">
                {stats.faltaExcel}
              </div>
              <span className="text-[11px] text-slate-400 dark:text-slate-500 block mt-0.5 font-mono">{pctFaltaExcel}%</span>
            </button>

            {/* 5. Falta en PDF */}
            <button
              type="button"
              onClick={() => setFiltroEstado("falta_pdf")}
              className={`p-3.5 rounded-xl text-left transition-all cursor-pointer ${
                filtroEstado === "falta_pdf"
                  ? "bg-purple-50/80 dark:bg-white/[0.1] border-2 border-purple-500 shadow-sm"
                  : "bg-slate-50/70 dark:bg-white/[0.03] hover:bg-slate-100/70 dark:hover:bg-white/[0.06] border border-slate-200/70 dark:border-white/[0.06]"
              }`}
            >
              <span className="text-xs text-purple-600 dark:text-purple-300 font-medium flex items-center gap-1.5">
                <span className="inline-block w-2.5 h-2.5 border border-purple-500 dark:border-purple-300"></span> Falta en PDF
              </span>
              <div className="text-2xl sm:text-3xl font-extrabold text-slate-900 dark:text-white mt-1 tracking-tight font-mono">
                {stats.faltaPdf}
              </div>
              <span className="text-[11px] text-slate-400 dark:text-slate-500 block mt-0.5 font-mono">{pctFaltaPdf}%</span>
            </button>
          </div>
        </div>

        {/* ─── Sección "Por resolver" (Si existen registros pendientes) ─── */}
        {personasPorResolver.length > 0 && (
          <div className="mb-8">
            <div className="flex items-center gap-2 mb-3.5">
              <h2 className="text-sm font-bold text-slate-900 dark:text-white tracking-wide">Por resolver</h2>
              <span className="px-2 py-0.5 rounded-full text-xs font-bold bg-slate-200/70 dark:bg-white/[0.06] text-slate-700 dark:text-slate-300 border border-slate-300/60 dark:border-white/[0.08] font-mono">
                {personasPorResolver.length}
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {personasPorResolver.slice(0, 6).map((p) => {
                const cfg = getEstadoConfig(p);
                const motivo = getMotivoExplicacion(p);
                const numPuntos = formatearCedulaPuntos(p.numero_identificacion);
                const pag = p.pagina_frente || p.pagina_numero || (Array.isArray((p.detalles_campos as any)?.paginas) ? (p.detalles_campos as any).paginas[0] : null);

                return (
                  <div
                    key={`resolver-${p.id}`}
                    className="p-4 rounded-2xl bg-white/80 dark:bg-[#121620]/70 backdrop-blur-xl border border-slate-200/80 dark:border-white/[0.08] flex flex-col justify-between hover:border-slate-300 dark:hover:border-white/[0.16] transition-all shadow-[0_2px_8px_rgba(0,0,0,0.03)] dark:shadow-sm"
                  >
                    <div>
                      {/* Cabecera de la tarjeta */}
                      <div className="flex items-center justify-between text-xs mb-2">
                        <span className={`flex items-center gap-1.5 text-xs font-semibold ${cfg.badgeClass}`}>
                          {cfg.iconType === "square" && <span>■</span>}
                          {cfg.iconType === "triangle" && <span>▲</span>}
                          {cfg.iconType === "outline_square" && <span className="inline-block w-2 h-2 border border-purple-400"></span>}
                          <span>{cfg.label}</span>
                        </span>
                        <span className="text-slate-400 dark:text-slate-500 text-[11px] font-mono">
                          {pag ? `pág. ${pag}` : "pág. —"}
                        </span>
                      </div>

                      {/* Nombre y Documento */}
                      <h3 className="text-sm font-bold text-slate-900 dark:text-white tracking-tight truncate" title={formatNombreCompleto(p)}>
                        {formatNombreCompleto(p)}
                      </h3>
                      <p className="text-xs font-mono text-slate-500 dark:text-slate-400 mt-0.5">
                        {numPuntos}
                      </p>

                      {/* Mensaje descriptivo */}
                      <p className="text-xs text-slate-600 dark:text-slate-300/90 mt-2.5 leading-relaxed bg-slate-50/80 dark:bg-white/[0.03] p-2.5 rounded-xl border border-slate-200/70 dark:border-white/[0.06]">
                        {motivo}
                      </p>

                      {/* Comparativa breve */}
                      <div className="mt-2.5 text-[11px] font-mono space-y-1 text-slate-600 dark:text-slate-400">
                        {personaFaltaEnExcel(p) ? (
                          <>
                            <div className="flex justify-between">
                              <span className="text-slate-400 dark:text-slate-500">PDF</span>
                              <span className="text-slate-700 dark:text-slate-300">{pag ? `Página ${pag}` : "Presente"}</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-slate-400 dark:text-slate-500">EXCEL</span>
                              <span className="text-pink-600 dark:text-pink-400 font-semibold">Sin registro</span>
                            </div>
                          </>
                        ) : personaFaltaEnPdf(p) ? (
                          <>
                            <div className="flex justify-between">
                              <span className="text-slate-400 dark:text-slate-500">PDF</span>
                              <span className="text-purple-600 dark:text-purple-300 font-semibold">Sin registro</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-slate-400 dark:text-slate-500">EXCEL</span>
                              <span className="text-slate-700 dark:text-slate-300">Presente en planilla</span>
                            </div>
                          </>
                        ) : (
                          <div className="flex justify-between">
                            <span className="text-slate-400 dark:text-slate-500">LEÍDO</span>
                            <span className="text-amber-600 dark:text-amber-300 font-semibold">
                              {formatearFechaCO(p.fecha_nacimiento) !== "—" ? `${formatearFechaCO(p.fecha_nacimiento)} · ` : ""}
                              {p.confianza_extraccion != null ? `${Math.round(Number(p.confianza_extraccion))}% confianza` : "Por verificar"}
                            </span>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Botones de acción rápida */}
                    <div className="flex items-center gap-2 mt-4 pt-3 border-t border-slate-200/80 dark:border-white/[0.08]">
                      <button
                        type="button"
                        onClick={() => abrirDetalleDrawer(p)}
                        className="flex-1 py-1.5 px-2.5 rounded-xl text-xs font-semibold bg-slate-100 hover:bg-slate-200/80 dark:bg-white/[0.06] dark:hover:bg-white/[0.1] text-slate-700 dark:text-slate-200 border border-slate-200 dark:border-white/[0.08] transition-all text-center cursor-pointer"
                      >
                        Ver detalle
                      </button>
                      {personaFaltaEnExcel(p) ? (
                        <button
                          type="button"
                          onClick={(e) => copiarAlPortapapeles(p.numero_identificacion || "", "Cédula", e)}
                          className="py-1.5 px-3 rounded-xl text-xs font-semibold bg-slate-100 hover:bg-slate-200/80 dark:bg-white/[0.06] dark:hover:bg-white/[0.1] text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-white/[0.08] transition-all flex items-center gap-1.5 cursor-pointer"
                          title="Copiar número de documento"
                        >
                          <Copy className="w-3 h-3" />
                          <span>Copiar cédula</span>
                        </button>
                      ) : (
                        <button
                          type="button"
                          onClick={(e) => aprobarRevision(p.id, e)}
                          className="py-1.5 px-3 rounded-xl text-xs font-semibold bg-emerald-50 hover:bg-emerald-100 dark:bg-emerald-500/10 dark:hover:bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-500/30 transition-all flex items-center gap-1.5 cursor-pointer"
                          title="Marcar registro como válido"
                        >
                          <Check className="w-3 h-3" />
                          <span>Marcar válido</span>
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* ─── Barra de Selección Múltiple ─── */}
        {seleccionados.size > 0 && (
          <div className="mb-4 p-3 bg-white dark:bg-[#121620] border border-[#0071E3]/40 rounded-2xl shadow-lg flex flex-wrap items-center justify-between gap-3 animate-in fade-in duration-200">
            <div className="flex items-center gap-2.5">
              <span className="p-1.5 rounded-lg bg-blue-50 dark:bg-[#0071E3]/20 text-[#0071E3] dark:text-[#3894FF]">
                <CheckSquare className="w-4 h-4" />
              </span>
              <span className="text-xs font-semibold text-slate-900 dark:text-white">
                {seleccionados.size} {seleccionados.size === 1 ? "persona seleccionada" : "personas seleccionadas"}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setModalEliminarSeleccionadosAbierto(true)}
                disabled={eliminandoEnLote}
                className="px-3 py-1.5 rounded-xl text-xs font-semibold bg-rose-50 hover:bg-rose-100 dark:bg-rose-600/20 dark:hover:bg-rose-600/30 text-rose-700 dark:text-rose-300 border border-rose-200 dark:border-rose-500/30 flex items-center gap-1.5 cursor-pointer"
              >
                <Trash2 className="w-3.5 h-3.5" />
                <span>Eliminar ({seleccionados.size})</span>
              </button>
              <button
                onClick={exportarSeleccion}
                disabled={exportando}
                className="px-3 py-1.5 rounded-xl text-xs font-semibold bg-[#0071E3] hover:bg-[#0077ED] text-white flex items-center gap-1.5 cursor-pointer shadow-sm shadow-[#0071E3]/20"
              >
                <Download className="w-3.5 h-3.5" />
                <span>Exportar selección (.xlsx)</span>
              </button>
              <button
                onClick={() => setSeleccionados(new Set())}
                className="px-3 py-1.5 rounded-xl text-xs font-semibold bg-slate-100 hover:bg-slate-200 dark:bg-white/[0.06] dark:hover:bg-white/[0.1] text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-white/[0.08] cursor-pointer"
              >
                Limpiar
              </button>
            </div>
          </div>
        )}

        {/* ─── Contenedor de la Tabla Principal (Image 1) ─── */}
        <div className="rounded-2xl bg-white/80 dark:bg-[#121620]/60 backdrop-blur-xl border border-slate-200/80 dark:border-white/[0.08] shadow-[0_2px_12px_rgba(0,0,0,0.03)] dark:shadow-[0_4px_24px_rgba(0,0,0,0.25)] overflow-hidden">
          {/* Barra superior de la tabla */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 border-b border-slate-200/80 dark:border-white/[0.08]">
            <div className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400 font-medium">
              <span>
                Mostrando <strong className="text-slate-900 dark:text-white font-bold">{personasFiltradas.length}</strong> de{" "}
                <strong className="text-slate-900 dark:text-white font-bold">{personas.length}</strong> personas
              </span>
              {filtroEstado !== "todos" && (
                <button
                  type="button"
                  onClick={() => setFiltroEstado("todos")}
                  className="text-xs text-[#0071E3] dark:text-[#3894FF] hover:underline ml-1 cursor-pointer font-semibold"
                >
                  (Limpiar filtro de estado)
                </button>
              )}
            </div>

            {/* Buscador */}
            <div className="relative w-full sm:w-72">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 dark:text-slate-500 pointer-events-none" />
              <input
                type="text"
                value={buscar}
                onChange={(e) => setBuscar(e.target.value)}
                placeholder="Buscar por cédula o nombre"
                className="w-full pl-9 pr-8 py-1.5 bg-slate-50 dark:bg-white/[0.04] border border-slate-200 dark:border-white/[0.08] rounded-xl text-xs text-slate-900 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500 focus:outline-none focus:border-[#0071E3] focus:ring-1 focus:ring-[#0071E3]/20 transition-all"
              />
              {buscar && (
                <button
                  onClick={() => setBuscar("")}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-700 dark:hover:text-white"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
          </div>

          {/* Tabla */}
          <div className="w-full overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-slate-200/80 dark:border-white/[0.08] text-[11px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider select-none bg-slate-50/70 dark:bg-white/[0.02]">
                  <th className="py-3 px-3 w-10 text-center">
                    <input
                      type="checkbox"
                      checked={personasFiltradas.length > 0 && personasFiltradas.every((p) => seleccionados.has(p.id))}
                      onChange={toggleSeleccionarTodas}
                      className="rounded border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-[#0071E3] focus:ring-[#0071E3] cursor-pointer"
                    />
                  </th>
                  <th className="py-3 px-3">DOCUMENTO</th>
                  <th className="py-3 px-3">NOMBRE COMPLETO</th>
                  <th className="py-3 px-3 text-center">EDAD</th>
                  <th className="py-3 px-3 text-center">PÁG.</th>
                  <th className="py-3 px-3 text-center">FUENTE</th>
                  <th className="py-3 px-3">ESTADO</th>
                  <th className="py-3 px-3 w-8"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200/70 dark:divide-white/[0.04] text-xs">
                {cargando ? (
                  Array(6).fill(0).map((_, i) => (
                    <tr key={`skel-${i}`}>
                      <td colSpan={8} className="py-4 px-4">
                        <div className="h-6 bg-slate-200/60 dark:bg-slate-800/40 rounded animate-pulse" />
                      </td>
                    </tr>
                  ))
                ) : personasFiltradas.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="text-center py-16 px-4">
                      <div className="w-12 h-12 mx-auto mb-3 rounded-2xl bg-slate-100 dark:bg-slate-800/50 flex items-center justify-center text-slate-400">
                        <Users className="w-6 h-6" />
                      </div>
                      <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-200">No se encontraron personas</h3>
                      <p className="text-slate-500 text-xs mt-1">
                        {buscar ? `Sin resultados para "${buscar}"` : "No hay registros disponibles."}
                      </p>
                    </td>
                  </tr>
                ) : (
                  personasFiltradas.map((p) => {
                    const cfg = getEstadoConfig(p);
                    const isSeleccionada = seleccionados.has(p.id);
                    const isFilaActiva = personaSeleccionadaId === p.id;
                    const nombreCompleto = formatNombreCompleto(p);
                    const edadRow = p.edad ?? calcularEdad(p.fecha_nacimiento);
                    const tipoInfo = getTipoDocInfo(p.tipo_documento);
                    const pag = p.pagina_frente || p.pagina_numero || (Array.isArray((p.detalles_campos as any)?.paginas) ? (p.detalles_campos as any).paginas[0] : null);
                    const numPuntos = formatearCedulaPuntos(p.numero_identificacion);

                    // Indicadores de Fuente PDF y Excel
                    const tienePdf = !personaFaltaEnPdf(p);
                    const tieneExcel = !personaFaltaEnExcel(p);

                    return (
                      <tr
                        key={p.id}
                        onClick={() => abrirDetalleDrawer(p)}
                        className={`group transition-colors cursor-pointer ${
                          isFilaActiva
                            ? "bg-slate-100 dark:bg-white/[0.08]"
                            : isSeleccionada
                            ? "bg-blue-50/70 dark:bg-blue-500/[0.08]"
                            : "hover:bg-slate-50 dark:hover:bg-white/[0.03]"
                        }`}
                      >
                        {/* Checkbox */}
                        <td className="py-3 px-3 text-center" onClick={(e) => toggleSeleccionFila(p.id, e)}>
                          <input
                            type="checkbox"
                            checked={isSeleccionada}
                            onChange={() => {}}
                            className="rounded border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-[#0071E3] focus:ring-[#0071E3] cursor-pointer"
                          />
                        </td>

                        {/* Documento con CC badge */}
                        <td className="py-3 px-3">
                          <div className="flex items-center gap-2">
                            <span className="px-1.5 py-0.5 rounded text-[10px] font-mono font-bold bg-slate-100 dark:bg-white/[0.06] text-slate-600 dark:text-slate-300 border border-slate-200/80 dark:border-white/[0.08] shrink-0">
                              {tipoInfo.codigo || "CC"}
                            </span>
                            <span className="font-mono text-slate-900 dark:text-white font-medium tracking-wide">
                              {numPuntos}
                            </span>
                          </div>
                        </td>

                        {/* Nombre completo */}
                        <td className="py-3 px-3 font-semibold text-slate-900 dark:text-slate-100">
                          {nombreCompleto || <span className="text-slate-400 italic">Sin nombre</span>}
                        </td>

                        {/* Edad */}
                        <td className="py-3 px-3 text-center font-mono text-slate-600 dark:text-slate-300">
                          {edadRow !== null ? edadRow : "—"}
                        </td>

                        {/* Página */}
                        <td className="py-3 px-3 text-center font-mono text-slate-500 dark:text-slate-400">
                          {pag ?? "—"}
                        </td>

                        {/* Fuente: PDF / XLS */}
                        <td className="py-3 px-3 text-center">
                          <div className="inline-flex items-center gap-1">
                            <span
                              className={`px-1.5 py-0.5 rounded text-[10px] font-mono font-semibold border ${
                                tienePdf
                                  ? "bg-slate-100 dark:bg-white/[0.06] text-slate-700 dark:text-slate-300 border-slate-200 dark:border-white/[0.08]"
                                  : "bg-slate-50 dark:bg-white/[0.02] text-slate-400 dark:text-slate-600 border border-slate-200/60 dark:border-white/[0.04] line-through opacity-60"
                              }`}
                              title={tienePdf ? "Presente en PDF" : "Falta en PDF"}
                            >
                              PDF
                            </span>
                            <span
                              className={`px-1.5 py-0.5 rounded text-[10px] font-mono font-semibold border ${
                                tieneExcel
                                  ? "bg-slate-100 dark:bg-white/[0.06] text-slate-700 dark:text-slate-300 border-slate-200 dark:border-white/[0.08]"
                                  : "bg-slate-50 dark:bg-white/[0.02] text-slate-400 dark:text-slate-600 border border-slate-200/60 dark:border-white/[0.04] line-through opacity-60"
                              }`}
                              title={tieneExcel ? "Presente en Excel" : "Falta en Excel"}
                            >
                              XLS
                            </span>
                          </div>
                        </td>

                        {/* Estado */}
                        <td className="py-3 px-3">
                          <div className={`flex items-center gap-1.5 text-xs font-semibold ${cfg.badgeClass}`}>
                            {cfg.iconType === "square" && <span>■</span>}
                            {cfg.iconType === "triangle" && <span>▲</span>}
                            {cfg.iconType === "dot" && <span>●</span>}
                            {cfg.iconType === "outline_square" && <span className="inline-block w-2.5 h-2.5 border border-purple-400"></span>}
                            <span>{cfg.label}</span>
                          </div>
                        </td>

                        {/* Chevron */}
                        <td className="py-3 px-3 text-right">
                          <ChevronRight className="w-4 h-4 text-slate-400 group-hover:text-slate-600 dark:group-hover:text-slate-300 transition-colors" />
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* ─── Drawer Lateral de Detalles de Persona (Images 2 & 3) ─── */}
        {personaActiva && (
          <>
            {/* Backdrop */}
            <div
              className="fixed inset-0 bg-black/60 z-40 backdrop-blur-sm animate-in fade-in duration-200"
              onClick={cerrarDetalleDrawer}
            />

            {/* Panel Slide-Over */}
            <div className="fixed inset-y-0 right-0 z-50 w-full md:max-w-[640px] lg:max-w-[720px] bg-white dark:bg-[#0e1320] border-l border-slate-200 dark:border-slate-800 shadow-2xl flex flex-col justify-between overflow-hidden animate-in slide-in-from-right duration-200">
              {/* Header del Drawer */}
              <div className="p-5 border-b border-slate-200/80 dark:border-slate-800/80 flex items-start justify-between gap-3">
                <div className="space-y-1 min-w-0">
                  <span className="text-[10px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-widest block">
                    PERSONA
                  </span>
                  <h2 className="text-xl font-extrabold text-slate-900 dark:text-white tracking-tight break-words">
                    {formatNombreCompleto(personaActiva)}
                  </h2>
                  <p className="text-xs text-slate-500 dark:text-slate-400 font-mono">
                    {getTipoDocInfo(personaActiva.tipo_documento).codigo || "CC"} ·{" "}
                    {formatearCedulaPuntos(personaActiva.numero_identificacion)} ·{" "}
                    {personaActiva.pagina_frente || personaActiva.pagina_numero ? `página ${personaActiva.pagina_frente || personaActiva.pagina_numero}` : "sin página"}
                  </p>
                  <div className="pt-1">
                    <span className={`inline-flex items-center gap-1.5 text-xs font-semibold ${getEstadoConfig(personaActiva).badgeClass}`}>
                      {getEstadoConfig(personaActiva).iconType === "square" && <span>■</span>}
                      {getEstadoConfig(personaActiva).iconType === "triangle" && <span>▲</span>}
                      {getEstadoConfig(personaActiva).iconType === "dot" && <span>●</span>}
                      {getEstadoConfig(personaActiva).iconType === "outline_square" && <span className="inline-block w-2.5 h-2.5 border border-purple-400"></span>}
                      <span>{getEstadoConfig(personaActiva).label}</span>
                    </span>
                  </div>
                </div>

                <button
                  type="button"
                  onClick={cerrarDetalleDrawer}
                  className="p-1.5 rounded-xl bg-slate-100 hover:bg-slate-200 dark:bg-slate-800/80 dark:hover:bg-slate-700 text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white transition-colors cursor-pointer"
                  title="Cerrar detalles"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              {/* Contenido scrolleable del Drawer */}
              <div className="flex-1 overflow-y-auto overscroll-contain p-5 space-y-4">
                {/* Cuadro de llamada/explicación */}
                <div className="p-3.5 rounded-xl bg-blue-50/70 dark:bg-[#161a2b] border border-blue-200/80 dark:border-indigo-500/30 text-xs text-blue-950 dark:text-slate-200 leading-relaxed shadow-sm">
                  {getMotivoExplicacion(personaActiva)}
                </div>

                {/* Si está en modo edición, mostrar el formulario integrado */}
                {editando === personaActiva.id ? (
                  <div className="p-4 rounded-2xl bg-slate-50 dark:bg-[#121624] border border-[#0071E3]/40 space-y-3">
                    <h4 className="text-xs font-bold text-[#0071E3] dark:text-indigo-400 uppercase tracking-wider flex items-center gap-1.5">
                      <Edit3 className="w-3.5 h-3.5" /> Editar datos de la persona
                    </h4>
                    <div>
                      <label className="block text-[10px] font-bold text-slate-500 dark:text-slate-400 uppercase mb-1">Número de Documento</label>
                      <input
                        type="text"
                        value={editForm.numero_identificacion || ""}
                        onChange={(e) => setEditForm(prev => ({ ...prev, numero_identificacion: e.target.value }))}
                        className="w-full bg-white dark:bg-[#181d2e] border border-slate-200 dark:border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-900 dark:text-white font-mono"
                      />
                    </div>
                    <div>
                      <label className="block text-[10px] font-bold text-slate-500 dark:text-slate-400 uppercase mb-1">Nombre Completo</label>
                      <input
                        type="text"
                        value={editForm.nombre_completo || ""}
                        onChange={(e) => {
                          setNombreEditado(true);
                          setEditForm(prev => ({ ...prev, nombre_completo: e.target.value }));
                        }}
                        className="w-full bg-white dark:bg-[#181d2e] border border-slate-200 dark:border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-900 dark:text-white uppercase"
                      />
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                      <div>
                        <label className="block text-[10px] font-bold text-slate-500 dark:text-slate-400 uppercase mb-1">Fecha de Nacimiento (AAAA-MM-DD)</label>
                        <input
                          type="text"
                          value={editForm.fecha_nacimiento || ""}
                          onChange={(e) => setEditForm(prev => ({ ...prev, fecha_nacimiento: e.target.value }))}
                          className="w-full bg-white dark:bg-[#181d2e] border border-slate-200 dark:border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-900 dark:text-white font-mono"
                        />
                      </div>
                      <div>
                        <label htmlFor="editar-sexo" className="block text-[10px] font-bold text-slate-500 dark:text-slate-400 uppercase mb-1">Sexo</label>
                        <select
                          id="editar-sexo"
                          value={editForm.sexo || ""}
                          onChange={(e) => setEditForm(prev => ({ ...prev, sexo: e.target.value }))}
                          className="w-full bg-white dark:bg-[#181d2e] border border-slate-200 dark:border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-900 dark:text-white"
                        >
                          <option value="">Sin dato</option>
                          <option value="F">Femenino</option>
                          <option value="M">Masculino</option>
                        </select>
                      </div>
                      <div>
                        <label htmlFor="editar-fecha-expedicion" className="block text-[10px] font-bold text-slate-500 dark:text-slate-400 uppercase mb-1">Fecha de Expedición (AAAA-MM-DD)</label>
                        <input
                          id="editar-fecha-expedicion"
                          type="text"
                          value={editForm.fecha_expedicion || ""}
                          onChange={(e) => setEditForm(prev => ({ ...prev, fecha_expedicion: e.target.value }))}
                          className="w-full bg-white dark:bg-[#181d2e] border border-slate-200 dark:border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-900 dark:text-white font-mono"
                        />
                      </div>
                      <div>
                        <label htmlFor="editar-lugar-expedicion" className="block text-[10px] font-bold text-slate-500 dark:text-slate-400 uppercase mb-1">Lugar de Expedición</label>
                        <input
                          id="editar-lugar-expedicion"
                          type="text"
                          value={editForm.lugar_expedicion || ""}
                          onChange={(e) => setEditForm(prev => ({ ...prev, lugar_expedicion: e.target.value }))}
                          className="w-full bg-white dark:bg-[#181d2e] border border-slate-200 dark:border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-900 dark:text-white uppercase"
                        />
                      </div>
                    </div>
                    <div className="flex items-center justify-end gap-2 pt-2">
                      <button
                        type="button"
                        onClick={() => setEditando(null)}
                        className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300"
                      >
                        Cancelar
                      </button>
                      <button
                        type="button"
                        onClick={() => guardarEdicion(personaActiva.id)}
                        className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-[#0071E3] hover:bg-[#0077ED] text-white flex items-center gap-1.5"
                      >
                        <Save className="w-3.5 h-3.5" />
                        <span>Guardar cambios</span>
                      </button>
                    </div>
                  </div>
                ) : (
                  <>
                    {/* Datos principales del documento + "Ver más" */}
                    {(() => {
                      const tipoDoc = getTipoDocInfo(personaActiva.tipo_documento);
                      const edadActiva = personaActiva.edad ?? calcularEdad(personaActiva.fecha_nacimiento);
                      const masDatos: [string, string][] = [
                        [
                          "Fecha de nacimiento",
                          personaActiva.fecha_nacimiento
                            ? `${formatearFechaCO(personaActiva.fecha_nacimiento)}${edadActiva !== null ? ` · ${edadActiva} años` : ""}`
                            : "Sin dato",
                        ],
                        ["Sexo", textoSexo(personaActiva.sexo)],
                        ["Fecha de expedición", personaActiva.fecha_expedicion ? formatearFechaCO(personaActiva.fecha_expedicion) : "Sin dato"],
                        ["Lugar de expedición", personaActiva.lugar_expedicion || "Sin dato"],
                      ];
                      return (
                        <div className="rounded-2xl bg-slate-50 dark:bg-[#141826] border border-slate-200 dark:border-slate-800 p-4 shadow-sm space-y-4">
                          <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
                            <h3 className="text-[10px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-widest">
                              Datos del documento
                            </h3>
                            {personaActiva.confianza_extraccion != null && !personaFaltaEnPdf(personaActiva) && (
                              <span className="text-[11px] text-slate-500 dark:text-slate-400 font-mono">
                                Confianza del OCR: {Math.round(Number(personaActiva.confianza_extraccion))}%
                              </span>
                            )}
                          </div>

                          <div className="flex gap-4 items-start">
                            {/* Silueta / Foto Cédula */}
                            <div aria-hidden="true" className="w-20 h-24 rounded-xl bg-slate-200/80 dark:bg-[#20273a] border border-slate-300 dark:border-slate-700/60 flex items-center justify-center shrink-0">
                              <div className="w-11 h-11 rounded-full bg-slate-300 dark:bg-slate-600/50 flex items-center justify-center">
                                <Users className="w-5 h-5 text-slate-500 dark:text-slate-400" />
                              </div>
                            </div>

                            <dl className="flex-1 min-w-0 space-y-3">
                              <div>
                                <dt className="text-[10px] font-bold tracking-wider text-slate-500 dark:text-slate-400 uppercase">Nombre completo</dt>
                                <dd className="text-base font-bold text-slate-900 dark:text-white uppercase break-words leading-snug mt-0.5">
                                  {formatNombreCompleto(personaActiva) || "Sin nombre"}
                                </dd>
                              </div>
                              <div className="flex flex-wrap gap-x-8 gap-y-3">
                                <div>
                                  <dt className="text-[10px] font-bold tracking-wider text-slate-500 dark:text-slate-400 uppercase">Tipo de documento</dt>
                                  <dd className="text-sm font-semibold text-slate-900 dark:text-white mt-0.5">
                                    {tipoDoc.label}
                                    {tipoDoc.codigo && tipoDoc.codigo !== "?" && (
                                      <span className="font-mono text-slate-500 dark:text-slate-400"> ({tipoDoc.codigo})</span>
                                    )}
                                  </dd>
                                </div>
                                <div>
                                  <dt className="text-[10px] font-bold tracking-wider text-slate-500 dark:text-slate-400 uppercase">Número</dt>
                                  <dd className="font-mono text-sm font-bold text-slate-900 dark:text-white tracking-wider mt-0.5">
                                    {formatearCedulaPuntos(personaActiva.numero_identificacion)}
                                  </dd>
                                </div>
                              </div>
                            </dl>
                          </div>

                          <button
                            type="button"
                            onClick={() => setVerMasDatos((v) => !v)}
                            aria-expanded={verMasDatos}
                            aria-controls="mas-datos-persona"
                            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold bg-white hover:bg-slate-100 dark:bg-white/[0.06] dark:hover:bg-white/[0.1] text-[#0071E3] dark:text-[#3894FF] border border-slate-200 dark:border-white/[0.08] transition-colors cursor-pointer"
                          >
                            <span>{verMasDatos ? "Ver menos" : "Ver más datos"}</span>
                            <ChevronDown className={`w-3.5 h-3.5 transition-transform ${verMasDatos ? "rotate-180" : ""}`} />
                          </button>

                          {verMasDatos && (
                            <dl
                              id="mas-datos-persona"
                              className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-3 pt-3 border-t border-dashed border-slate-200 dark:border-slate-700"
                            >
                              {masDatos.map(([etiqueta, valor]) => (
                                <div key={etiqueta}>
                                  <dt className="text-[10px] font-bold tracking-wider text-slate-500 dark:text-slate-400 uppercase">{etiqueta}</dt>
                                  <dd className="text-sm font-semibold text-slate-900 dark:text-white break-words mt-0.5">{valor}</dd>
                                </div>
                              ))}
                            </dl>
                          )}
                        </div>
                      );
                    })()}

                    {/* Tabla de Comparativa: LECTURA DEL PDF vs PLANILLA EXCEL (Image 3) */}
                    <div className="rounded-xl bg-slate-50 dark:bg-[#141826] border border-slate-200 dark:border-slate-800 p-3.5 space-y-2.5">
                      <div className="grid grid-cols-12 text-[10px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider pb-1.5 border-b border-slate-200 dark:border-slate-800/80">
                        <div className="col-span-4"></div>
                        <div className="col-span-4 text-center">LECTURA DEL PDF</div>
                        <div className="col-span-4 text-center">PLANILLA EXCEL</div>
                      </div>

                      {/* Fila DOCUMENTO */}
                      <div className="grid grid-cols-12 text-xs items-center py-1">
                        <div className="col-span-4 text-[10px] font-bold text-slate-500 dark:text-slate-400 uppercase">DOCUMENTO</div>
                        <div className="col-span-4 text-center font-mono text-slate-900 dark:text-white text-xs break-words">
                          {formatearCedulaPuntos(personaActiva.numero_identificacion)}
                        </div>
                        <div className="col-span-4 text-center flex items-center justify-center gap-1 font-mono text-xs">
                          {personaFaltaEnExcel(personaActiva) ? (
                            <span className="text-pink-600 dark:text-pink-400 flex items-center gap-1 font-semibold">
                              Sin registro <X className="w-3 h-3 text-pink-500" />
                            </span>
                          ) : (
                            <span className="text-emerald-600 dark:text-emerald-400 flex items-center gap-1 font-semibold">
                              {formatearCedulaPuntos(personaActiva.numero_identificacion)}{" "}
                              <Check className="w-3 h-3 text-emerald-500" />
                            </span>
                          )}
                        </div>
                      </div>

                      {/* Fila NOMBRE */}
                      <div className="grid grid-cols-12 text-xs items-center py-1">
                        <div className="col-span-4 text-[10px] font-bold text-slate-500 dark:text-slate-400 uppercase">NOMBRE</div>
                        <div className="col-span-4 text-center text-slate-900 dark:text-white text-xs break-words uppercase font-medium">
                          {formatNombreCompleto(personaActiva)}
                        </div>
                        <div className="col-span-4 text-center flex items-center justify-center gap-1 text-xs">
                          {personaFaltaEnExcel(personaActiva) ? (
                            <span className="text-pink-600 dark:text-pink-400 flex items-center gap-1 font-semibold">
                              Sin registro <X className="w-3 h-3 text-pink-500" />
                            </span>
                          ) : (
                            <span className="text-emerald-600 dark:text-emerald-400 flex items-center justify-center gap-1 break-words uppercase font-medium">
                              {formatNombreCompleto(personaActiva)}{" "}
                              <Check className="w-3 h-3 text-emerald-500 shrink-0" />
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  </>
                )}
              </div>

              {/* Barra de Acciones del Drawer (Bottom Bar) */}
              <div className="p-4 bg-white dark:bg-[#111624] border-t border-slate-200 dark:border-slate-800 flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  {/* Botón Abrir Página X (Visor PDF Modal) */}
                  <button
                    type="button"
                    onClick={() => abrirModalPdf(personaActiva)}
                    className="px-3.5 py-2 rounded-xl text-xs font-semibold bg-[#0071E3] hover:bg-[#0077ED] text-white flex items-center gap-1.5 transition-all shadow-sm cursor-pointer"
                    title="Ver página del PDF escaneado"
                  >
                    <FileText className="w-3.5 h-3.5" />
                    <span>
                      {personaActiva.pagina_frente || personaActiva.pagina_numero
                        ? `Abrir página ${personaActiva.pagina_frente || personaActiva.pagina_numero}`
                        : "Abrir documento"}
                    </span>
                  </button>

                  {/* Marcar válido si está en revisión */}
                  {!esPersonaValidada(personaActiva) && (
                    <button
                      type="button"
                      onClick={(e) => aprobarRevision(personaActiva.id, e)}
                      className="px-3.5 py-2 rounded-xl text-xs font-semibold bg-emerald-50 hover:bg-emerald-100 dark:bg-emerald-600/20 dark:hover:bg-emerald-600/30 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-500/30 flex items-center gap-1.5 transition-all cursor-pointer"
                      title="Aprobar y marcar como válido"
                    >
                      <Check className="w-3.5 h-3.5" />
                      <span>Marcar válido</span>
                    </button>
                  )}
                </div>

                <div className="flex items-center gap-1.5">
                  <button
                    type="button"
                    onClick={() => iniciarEdicion(personaActiva)}
                    className="p-2 rounded-xl bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 transition-colors cursor-pointer"
                    title="Editar datos"
                  >
                    <Edit3 className="w-4 h-4" />
                  </button>
                  <button
                    type="button"
                    onClick={() => eliminar(personaActiva.id, personaActiva.numero_identificacion)}
                    className="p-2 rounded-xl bg-rose-50 hover:bg-rose-100 dark:bg-rose-600/20 dark:hover:bg-rose-600/30 text-rose-600 dark:text-rose-400 border border-rose-200 dark:border-rose-500/30 transition-colors cursor-pointer"
                    title="Eliminar persona"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </div>
          </>
        )}

        {/* ─── Modal de Vista Previa Rápida del PDF (Optimizado) ─── */}
        {modalPdfAbierto && personaPdfModal && (
          <VisorDocumento
            persona={personaPdfModal}
            paginaInicial={paginaPreviaModal}
            onCerrar={() => setModalPdfAbierto(false)}
            onSubirPdf={abrirSubirPdf}
          />
        )}

        {/* ─── Modal Confirmar Vaciar Tabla ─── */}
        {modalVaciarAbierto && (
          <div
            className="fixed inset-0 z-50 bg-black/70 backdrop-blur-md flex items-center justify-center p-4 animate-in fade-in duration-200"
            onClick={() => !eliminandoEnLote && setModalVaciarAbierto(false)}
          >
            <div
              className="bg-white dark:bg-[#111624] border border-slate-200 dark:border-slate-800 rounded-3xl shadow-2xl w-full max-w-md p-6 overflow-hidden animate-in zoom-in-95 duration-200"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="w-14 h-14 rounded-2xl bg-rose-50 dark:bg-rose-500/20 border border-rose-200 dark:border-rose-500/30 flex items-center justify-center text-rose-500 dark:text-rose-400 mx-auto mb-4">
                <Trash2 className="w-7 h-7" />
              </div>
              <h3 className="text-xl font-bold text-slate-900 dark:text-white text-center">¿Vaciar tabla de personas?</h3>
              <p className="text-xs text-slate-500 dark:text-slate-400 text-center mt-2 leading-relaxed">
                Estás a punto de eliminar permanentemente todos los registros (<span className="text-rose-600 dark:text-rose-400 font-bold">{stats.total} personas</span>).
              </p>
              <div className="flex items-center justify-end gap-3 mt-6">
                <button
                  type="button"
                  onClick={() => setModalVaciarAbierto(false)}
                  disabled={eliminandoEnLote}
                  className="px-4 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 text-xs font-bold cursor-pointer"
                >
                  Cancelar
                </button>
                <button
                  type="button"
                  onClick={ejecutarVaciarTabla}
                  disabled={eliminandoEnLote}
                  className="px-4 py-2 rounded-xl bg-rose-600 hover:bg-rose-700 text-white text-xs font-bold shadow-lg shadow-rose-600/30 flex items-center gap-2 cursor-pointer"
                >
                  {eliminandoEnLote ? "Vaciando..." : "Sí, vaciar tabla"}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* ─── Modal Confirmar Eliminar Seleccionados ─── */}
        {modalEliminarSeleccionadosAbierto && (
          <div
            className="fixed inset-0 z-50 bg-black/70 backdrop-blur-md flex items-center justify-center p-4 animate-in fade-in duration-200"
            onClick={() => !eliminandoEnLote && setModalEliminarSeleccionadosAbierto(false)}
          >
            <div
              className="bg-white dark:bg-[#111624] border border-slate-200 dark:border-slate-800 rounded-3xl shadow-2xl w-full max-w-md p-6 overflow-hidden animate-in zoom-in-95 duration-200"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="w-14 h-14 rounded-2xl bg-rose-50 dark:bg-rose-500/20 border border-rose-200 dark:border-rose-500/30 flex items-center justify-center text-rose-500 dark:text-rose-400 mx-auto mb-4">
                <Trash2 className="w-7 h-7" />
              </div>
              <h3 className="text-xl font-bold text-slate-900 dark:text-white text-center">¿Eliminar seleccionados?</h3>
              <p className="text-xs text-slate-500 dark:text-slate-400 text-center mt-2 leading-relaxed">
                Vas a eliminar <strong className="text-rose-600 dark:text-rose-400 font-bold">{seleccionados.size} personas</strong> definitivamente.
              </p>
              <div className="flex items-center justify-end gap-3 mt-6">
                <button
                  type="button"
                  onClick={() => setModalEliminarSeleccionadosAbierto(false)}
                  disabled={eliminandoEnLote}
                  className="px-4 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 text-xs font-bold cursor-pointer"
                >
                  Cancelar
                </button>
                <button
                  type="button"
                  onClick={ejecutarEliminarSeleccionados}
                  disabled={eliminandoEnLote}
                  className="px-4 py-2 rounded-xl bg-rose-600 hover:bg-rose-700 text-white text-xs font-bold shadow-lg shadow-rose-600/30 flex items-center gap-2 cursor-pointer"
                >
                  {eliminandoEnLote ? "Eliminando..." : "Sí, eliminar seleccionados"}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Input oculto para subir PDF de la cédula individual */}
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
        <div className="flex min-h-screen bg-[#F5F5F7] dark:bg-[#0A0D14] text-slate-900 dark:text-slate-100 items-center justify-center">
          <div className="flex flex-col items-center gap-3">
            <div className="w-8 h-8 border-2 border-[#0071E3] border-t-transparent rounded-full animate-spin" />
            <p className="text-xs text-slate-500 dark:text-slate-400 font-medium">Cargando módulo de personas...</p>
          </div>
        </div>
      }
    >
      <PersonasContent />
    </Suspense>
  );
}
