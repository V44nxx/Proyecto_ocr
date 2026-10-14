"use client";

import { useState, useEffect, useMemo } from "react";
import { useRouter } from "next/navigation";
import toast from "react-hot-toast";
import {
  Download, FileSpreadsheet, Users, Filter,
  CheckCircle, AlertTriangle, RefreshCw, FileText, CheckSquare, Square,
  Search, X
} from "lucide-react";
import Sidebar from "@/components/ui/Sidebar";
import { useSidebar } from "@/context/SidebarContext";
import { apiExportacion, apiPersonas, apiDocumentos } from "@/lib/api";
import { auth } from "@/lib/auth";
import { formatNombreCompleto, calcularEdad, verificarInconsistenciaDocumentoEdad, getTipoDocInfo } from "@/lib/formatters";
import type { Persona, Documento } from "@/types";

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

export default function ExportacionPage() {
  const router = useRouter();
  const { collapsed } = useSidebar();
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [documentos, setDocumentos] = useState<Documento[]>([]);
  const [documentoSeleccionado, setDocumentoSeleccionado] = useState<string>("todos");
  const [cargando, setCargando] = useState(true);
  const [exportando, setExportando] = useState(false);
  const [filtroRevision, setFiltroRevision] = useState<"todos" | "revision" | "ok" | "menores">("todos");
  const [busqueda, setBusqueda] = useState<string>("");
  const [seleccionados, setSeleccionados] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (!auth.isAuthenticated()) { router.push("/"); return; }
    cargarDatos();
  }, []);

  const cargarDatos = async () => {
    setCargando(true);
    try {
      const [resPersonas, resDocs] = await Promise.all([
        apiPersonas.listar({ limit: 500 }),
        apiDocumentos.listar({ limit: 100 }).catch(() => ({ data: [] })),
      ]);

      const personasItems = Array.isArray(resPersonas.data)
        ? resPersonas.data
        : ((resPersonas.data as any)?.items || []);
      setPersonas(personasItems);

      const docsItems = Array.isArray(resDocs.data) ? resDocs.data : [];
      setDocumentos(docsItems);

      // Por defecto, seleccionar todas las personas cargadas
      setSeleccionados(new Set(personasItems.map((p: Persona) => p.id)));
    } catch {
      toast.error("Error cargando datos para exportación");
    } finally {
      setCargando(false);
    }
  };

  // Filtrar personas según documento, estado de revisión o menores, y búsqueda
  const personasFiltradas = useMemo(() => {
    const term = busqueda.trim().toLowerCase();
    return personas.filter((p) => {
      // Filtro por documento
      if (documentoSeleccionado !== "todos" && p.documento_id !== documentoSeleccionado) {
        return false;
      }
      // Filtro por revisión o menores
      const esRev = esPersonaEnRevision(p);
      const edadNum = p.edad ?? (p.fecha_nacimiento ? calcularEdad(p.fecha_nacimiento) : null);
      const esMenor = edadNum !== null && edadNum < 14;

      if (filtroRevision === "revision" && !esRev) return false;
      if (filtroRevision === "ok" && esRev) return false;
      if (filtroRevision === "menores" && !esMenor) return false;

      // Filtro por término de búsqueda (cédula, nombre o PDF)
      if (term) {
        const nom = formatNombreCompleto(p).toLowerCase();
        const num = (p.numero_identificacion || "").toLowerCase();
        const docName = (p.nombre_documento || "").toLowerCase();
        if (!nom.includes(term) && !num.includes(term) && !docName.includes(term)) {
          return false;
        }
      }

      return true;
    });
  }, [personas, documentoSeleccionado, filtroRevision, busqueda]);

  // Al cambiar filtros de documento o revisión, seleccionar por defecto las personas visibles
  useEffect(() => {
    setSeleccionados(new Set(personasFiltradas.map((p) => p.id)));
  }, [documentoSeleccionado, filtroRevision]);

  // Manejadores de selección
  const toggleSeleccionarTodo = () => {
    const todosVisiblesSeleccionados = personasFiltradas.every((p) => seleccionados.has(p.id));
    if (todosVisiblesSeleccionados) {
      // Deseleccionar todas las personas visibles
      setSeleccionados((prev) => {
        const next = new Set(prev);
        personasFiltradas.forEach((p) => next.delete(p.id));
        return next;
      });
    } else {
      // Seleccionar todas las personas visibles
      setSeleccionados((prev) => {
        const next = new Set(prev);
        personasFiltradas.forEach((p) => next.add(p.id));
        return next;
      });
    }
  };

  const togglePersona = (id: string) => {
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

  const exportarXlsx = async () => {
    if (seleccionados.size === 0) {
      toast.error("Selecciona al menos una persona para exportar");
      return;
    }

    setExportando(true);
    try {
      let requiereRevision: boolean | undefined;
      if (filtroRevision === "revision") requiereRevision = true;
      else if (filtroRevision === "ok") requiereRevision = false;
      const soloMenores = filtroRevision === "menores" ? true : undefined;

      const docId = documentoSeleccionado !== "todos" ? documentoSeleccionado : undefined;

      // Si se seleccionó un subconjunto específico de personas visibles, o personas de un PDF
      const todosFueronSeleccionados = personasFiltradas.length > 0 &&
        personasFiltradas.length === seleccionados.size &&
        personasFiltradas.every((p) => seleccionados.has(p.id));

      await apiExportacion.descargarXlsx({
        requiereRevision,
        soloMenores,
        documentoId: docId,
        personaIds: todosFueronSeleccionados && !docId ? undefined : Array.from(seleccionados),
      });

      toast.success("Archivo Excel descargado correctamente");
    } catch {
      toast.error("Error generando exportación");
    } finally {
      setExportando(false);
    }
  };

  const stats = {
    total: personas.length,
    ok: personas.filter((p) => !esPersonaEnRevision(p)).length,
    revision: personas.filter(esPersonaEnRevision).length,
    menores: personas.filter((p) => {
      const ed = p.edad ?? (p.fecha_nacimiento ? calcularEdad(p.fecha_nacimiento) : null);
      return ed !== null && ed < 14;
    }).length,
    completas: personas.filter(
      (p) => (p.nombre_completo || (p.nombres && p.apellidos)) && p.fecha_nacimiento && p.fecha_expedicion
    ).length,
  };

  // Conteo de personas por documento
  const personasPorDoc = useMemo(() => {
    const mapa: Record<string, number> = {};
    personas.forEach((p) => {
      if (p.documento_id) {
        mapa[p.documento_id] = (mapa[p.documento_id] || 0) + 1;
      }
    });
    return mapa;
  }, [personas]);

  // Nombre del documento actualmente seleccionado
  const docActual = documentos.find((d) => d.id === documentoSeleccionado);
  const seleccionadosVisiblesCount = personasFiltradas.filter((p) => seleccionados.has(p.id)).length;
  const todosVisiblesSeleccionados = personasFiltradas.length > 0 && seleccionadosVisiblesCount === personasFiltradas.length;

  return (
    <div className="flex min-h-screen bg-[#F5F5F7] dark:bg-[#0A0D14] text-slate-900 dark:text-slate-100 font-sans w-full max-w-full overflow-x-hidden transition-colors duration-200">
      <Sidebar />
      <main className={`${collapsed ? "ml-20" : "ml-64"} transition-all duration-300 ease-in-out flex-1 p-8 overflow-x-hidden min-w-0`}>
        {/* Header */}
        <div className="mb-8 page-enter">
          <div className="flex items-center gap-2 mb-1">
            <span className="p-1.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-600 dark:text-emerald-400">
              <Download className="w-4 h-4" />
            </span>
            <span className="text-emerald-600 dark:text-emerald-400 text-xs font-semibold uppercase tracking-wider">Exportación</span>
          </div>
          <h1 className="text-3xl font-extrabold text-slate-900 dark:text-white tracking-tight">Exportación a Excel</h1>
          <p className="text-slate-500 dark:text-slate-400 mt-1 text-sm">
            Filtra por documento PDF, selecciona personas específicas y genera reportes .xlsx profesionales
          </p>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8 page-enter">
          {[
            { label: "Total Personas", value: stats.total, color: "text-slate-900 dark:text-white" },
            { label: "Validadas OK", value: stats.ok, color: "text-emerald-600 dark:text-emerald-400" },
            { label: "En Revisión", value: stats.revision, color: "text-amber-600 dark:text-amber-400" },
            { label: "Fichas Completas", value: stats.completas, color: "text-slate-900 dark:text-slate-200" },
          ].map((s) => (
            <div key={s.label} className="relative rounded-2xl bg-white/70 dark:bg-[#121620]/60 backdrop-blur-xl border border-slate-200/80 dark:border-white/[0.08] shadow-[0_2px_12px_rgba(0,0,0,0.03)] p-5 text-center overflow-hidden">
              <div className="absolute inset-x-0 top-0 h-[1px] bg-gradient-to-r from-transparent via-slate-300/40 dark:via-white/10 to-transparent pointer-events-none" />
              <p className={`text-2xl font-bold tracking-[-0.04em] ${s.color}`}>{s.value}</p>
              <p className="text-[11px] font-medium uppercase tracking-wider text-slate-500 dark:text-slate-400 mt-1">{s.label}</p>
            </div>
          ))}
        </div>

        {/* Panel Superior: Configuración de Exportación (A lo largo de la página - Full Width) */}
        <div className="relative rounded-2xl bg-white/70 dark:bg-[#121620]/60 backdrop-blur-xl border border-slate-200/80 dark:border-white/[0.08] shadow-[0_2px_12px_rgba(0,0,0,0.03)] p-6 mb-6 overflow-hidden page-enter">
          <div className="absolute inset-x-0 top-0 h-[1px] bg-gradient-to-r from-transparent via-emerald-500/25 to-transparent pointer-events-none" />

          {/* Header del bloque */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6 pb-4 border-b border-slate-200/80 dark:border-white/[0.06]">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
                <FileSpreadsheet className="w-5 h-5" />
              </div>
              <div>
                <h2 className="text-base font-semibold text-slate-900 dark:text-white flex items-center gap-2">
                  Configurar Exportación
                </h2>
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                  Filtra por archivo PDF, selecciona el estado de validación y genera tu reporte oficial .xlsx
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2 bg-slate-100 dark:bg-white/[0.04] border border-slate-200/80 dark:border-white/[0.06] rounded-xl px-3 py-1.5 self-start sm:self-auto">
              <span className="text-[11px] text-slate-500 dark:text-slate-400 font-medium">Seleccionadas:</span>
              <span className="text-xs font-mono font-bold text-emerald-600 dark:text-emerald-400">
                {seleccionadosVisiblesCount} / {personasFiltradas.length}
              </span>
            </div>
          </div>

          {/* Controles distribuidos horizontalmente */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-end">
            {/* Columna 1: Documento PDF de Origen (4 columnas) */}
            <div className="lg:col-span-4 flex flex-col justify-between">
              <div>
                <label className="block text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-2 flex items-center gap-2">
                  <FileText className="w-3.5 h-3.5 text-emerald-500" />
                  Documento PDF de Origen
                </label>
                <div className="relative">
                  <select
                    value={documentoSeleccionado}
                    onChange={(e) => setDocumentoSeleccionado(e.target.value)}
                    className="w-full bg-white dark:bg-[#121620] [&>option]:bg-white dark:[&>option]:bg-[#121620] [&>option]:text-slate-900 dark:[&>option]:text-slate-100 border border-slate-200/80 dark:border-white/[0.08] rounded-xl px-3.5 py-2.5 text-xs text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-[#0071E3]/20 focus:border-[#0071E3] transition-all font-medium cursor-pointer"
                  >
                    <option value="todos">
                      Todos los documentos PDF ({personas.length} personas)
                    </option>
                    {documentos.map((doc) => {
                      const count = personasPorDoc[doc.id] || 0;
                      return (
                        <option key={doc.id} value={doc.id}>
                          {doc.nombre_original} ({count} personas)
                        </option>
                      );
                    })}
                  </select>
                </div>
              </div>

              {documentoSeleccionado !== "todos" && docActual ? (
                <div className="mt-2.5 p-2 rounded-xl bg-slate-100 dark:bg-white/[0.04] border border-slate-200/80 dark:border-white/[0.06] text-xs text-slate-700 dark:text-slate-300 flex items-center justify-between">
                  <span className="truncate max-w-[220px] font-mono text-[11px]" title={docActual.nombre_original}>
                    {docActual.nombre_original}
                  </span>
                  <span className="font-semibold text-emerald-600 dark:text-emerald-400 text-[11px] shrink-0 ml-2">
                    {personasPorDoc[docActual.id] || 0} personas
                  </span>
                </div>
              ) : (
                <div className="mt-2.5 text-[11px] text-slate-500 dark:text-slate-400 flex items-center gap-1.5">
                  <span className="truncate">Todos los PDFs incluidos ({personas.length} personas en total)</span>
                </div>
              )}
            </div>

            {/* Columna 2: Filtro por Estado (5 columnas) */}
            <div className="lg:col-span-5">
              <label className="block text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-2 flex items-center gap-2">
                <Filter className="w-3.5 h-3.5 text-emerald-500" />
                Filtrar por Estado
              </label>
              <div className="grid grid-cols-2 gap-2">
                {[
                  {
                    value: "todos",
                    label: "Todos los registros",
                    icon: <Users className="w-3.5 h-3.5" />,
                    count: personas.length,
                    iconColor: "text-slate-400",
                  },
                  {
                    value: "ok",
                    label: "Validados OK",
                    icon: <CheckCircle className="w-3.5 h-3.5" />,
                    count: stats.ok,
                    iconColor: "text-emerald-500",
                  },
                  {
                    value: "revision",
                    label: "En revisión",
                    icon: <AlertTriangle className="w-3.5 h-3.5" />,
                    count: stats.revision,
                    iconColor: "text-amber-500",
                  },
                  {
                    value: "menores",
                    label: "Menores (< 14)",
                    icon: <AlertTriangle className="w-3.5 h-3.5" />,
                    count: stats.menores,
                    iconColor: "text-rose-500",
                  },
                ].map((opt) => {
                  const isActive = filtroRevision === opt.value;
                  return (
                    <button
                      key={opt.value}
                      type="button"
                      onClick={() => setFiltroRevision(opt.value as typeof filtroRevision)}
                      className={`flex items-center justify-between p-2.5 rounded-xl border text-left transition-all cursor-pointer ${
                        isActive
                          ? "border-[#0071E3] bg-[#0071E3]/15 text-white shadow-sm ring-1 ring-[#0071E3]/30"
                          : "border-slate-200/80 dark:border-white/[0.06] hover:bg-slate-100/60 dark:hover:bg-white/[0.03] bg-slate-50/50 dark:bg-white/[0.015] text-slate-700 dark:text-slate-300"
                      }`}
                    >
                      <div className="flex items-center gap-2 min-w-0">
                        <span className={`shrink-0 ${isActive ? "text-[#0071E3] dark:text-blue-400" : opt.iconColor}`}>
                          {opt.icon}
                        </span>
                        <span className={`text-xs font-semibold truncate ${isActive ? "text-slate-900 dark:text-white" : "text-slate-700 dark:text-slate-300"}`}>
                          {opt.label}
                        </span>
                      </div>
                      <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded-md shrink-0 ml-1.5 font-bold ${
                        isActive
                          ? "bg-[#0071E3] text-white"
                          : "bg-slate-200 dark:bg-white/[0.06] text-slate-700 dark:text-slate-300"
                      }`}>
                        {opt.count}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Columna 3: Descarga y Resumen de Acción (3 columnas) */}
            <div className="lg:col-span-3 flex flex-col justify-between">
              <label className="block text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-2 flex items-center justify-between">
                <span>Acción de Exportación</span>
                <span className="text-[10px] font-mono font-bold text-emerald-500 bg-emerald-500/10 px-1.5 py-0.5 rounded">
                  .XLSX
                </span>
              </label>
              <button
                onClick={exportarXlsx}
                disabled={exportando || seleccionadosVisiblesCount === 0}
                className="w-full py-2.5 px-4 rounded-xl bg-[#0071E3] hover:bg-[#0077ED] active:scale-[0.98] text-white text-xs font-semibold flex items-center justify-center gap-2 transition-all shadow-md shadow-blue-500/20 disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer h-[42px]"
              >
                {exportando ? (
                  <>
                    <div className="w-3.5 h-3.5 border-2 border-white/20 border-t-white rounded-full animate-spin" />
                    <span>Generando Excel...</span>
                  </>
                ) : (
                  <>
                    <Download className="w-4 h-4" />
                    <span>Descargar Excel ({seleccionadosVisiblesCount})</span>
                  </>
                )}
              </button>
              <div className="mt-2.5 text-[11px] text-slate-500 dark:text-slate-400 text-center">
                {seleccionadosVisiblesCount === 0 ? (
                  <span className="text-amber-500">Selecciona al menos una persona</span>
                ) : (
                  <span>{seleccionadosVisiblesCount} personas seleccionadas para reporte</span>
                )}
              </div>
            </div>
          </div>

          {/* Banner de alerta de menores integrado */}
          <div className="mt-5 p-3 rounded-xl bg-amber-500/10 border border-amber-500/20 text-xs text-amber-800 dark:text-amber-300 flex items-center gap-2.5">
            <AlertTriangle className="w-4 h-4 text-amber-500 shrink-0" />
            <span className="text-[11px] leading-tight">
              <strong>Alerta de menores (&lt; 14 años):</strong> Cualquier persona menor de 14 años será automáticamente resaltada con fila y celda de edad en el reporte oficial descargado.
            </span>
          </div>
        </div>

        {/* Panel Inferior: Tabla de Vista Previa y Selección (A lo largo de toda la página - Full Width) */}
        <div className="relative rounded-2xl bg-white/70 dark:bg-[#121620]/60 backdrop-blur-xl border border-slate-200/80 dark:border-white/[0.08] shadow-[0_2px_12px_rgba(0,0,0,0.03)] p-6 overflow-hidden page-enter">
          <div className="absolute inset-x-0 top-0 h-[1px] bg-gradient-to-r from-transparent via-slate-300/40 dark:via-white/10 to-transparent pointer-events-none" />

          {/* Header de la Tabla: Título, Filtro de Búsqueda y Botones de Acción */}
          <div className="flex flex-col xl:flex-row xl:items-center justify-between gap-4 mb-5 pb-4 border-b border-slate-200/80 dark:border-white/[0.06]">
            <div className="min-w-0">
              <div className="flex items-center gap-2.5">
                <h2 className="text-base font-semibold text-slate-900 dark:text-white flex items-center gap-2">
                  <span>Vista Previa y Selección</span>
                </h2>
                <span className="text-xs px-2.5 py-0.5 rounded-full bg-slate-100 dark:bg-white/[0.06] text-slate-600 dark:text-slate-300 font-mono font-medium border border-slate-200/60 dark:border-white/[0.06]">
                  {personasFiltradas.length} {personasFiltradas.length === 1 ? "registro" : "registros"}
                </span>
              </div>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                Marca o desmarca personas específicas para personalizar tu exportación ({seleccionadosVisiblesCount} seleccionadas actualmente)
              </p>
            </div>

            {/* Toolbar derecha en una sola línea horizontal */}
            <div className="flex items-center gap-2 shrink-0 flex-nowrap self-start xl:self-auto w-full sm:w-auto">
              {/* Buscador interactivo */}
              <div className="relative flex-1 sm:w-60 md:w-64 min-w-[170px]">
                <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
                <input
                  type="text"
                  value={busqueda}
                  onChange={(e) => setBusqueda(e.target.value)}
                  placeholder="Buscar cédula, nombre o PDF..."
                  className="w-full bg-white dark:bg-[#121620] border border-slate-200/80 dark:border-white/[0.08] rounded-xl pl-8 pr-7 py-2 text-xs text-slate-900 dark:text-white placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-[#0071E3]/20 focus:border-[#0071E3] transition-all h-[36px]"
                />
                {busqueda && (
                  <button
                    onClick={() => setBusqueda("")}
                    className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 dark:hover:text-white p-0.5 cursor-pointer"
                    title="Limpiar búsqueda"
                  >
                    <X className="w-3 h-3" />
                  </button>
                )}
              </div>

              {/* Botón Seleccionar / Deseleccionar */}
              <button
                onClick={toggleSeleccionarTodo}
                className="btn-secondary text-xs px-3 flex items-center gap-1.5 border border-slate-200/80 dark:border-white/[0.08] hover:bg-slate-100 dark:hover:bg-white/[0.05] rounded-xl transition-all cursor-pointer text-slate-700 dark:text-slate-200 shrink-0 whitespace-nowrap h-[36px]"
                title="Alternar selección de visibles"
              >
                {todosVisiblesSeleccionados ? (
                  <>
                    <Square className="w-3.5 h-3.5 text-slate-400" />
                    <span>Deseleccionar</span>
                  </>
                ) : (
                  <>
                    <CheckSquare className="w-3.5 h-3.5 text-[#0071E3]" />
                    <span>Seleccionar todos</span>
                  </>
                )}
              </button>

              {/* Botón Refrescar */}
              <button
                onClick={cargarDatos}
                className="btn-secondary text-xs p-2 flex items-center justify-center border border-slate-200/80 dark:border-white/[0.08] hover:bg-slate-100 dark:hover:bg-white/[0.05] rounded-xl transition-all cursor-pointer text-slate-700 dark:text-slate-200 shrink-0 w-[36px] h-[36px]"
                title="Actualizar datos"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${cargando ? "animate-spin text-emerald-400" : ""}`} />
              </button>
            </div>
          </div>

          {/* Contenido de la Tabla */}
          {cargando ? (
            <div className="space-y-2.5 py-4">
              {Array(6).fill(0).map((_, i) => (
                <div key={i} className="h-11 rounded-xl bg-slate-100 dark:bg-white/[0.03] animate-pulse" />
              ))}
            </div>
          ) : personasFiltradas.length === 0 ? (
            <div className="text-center py-16 px-4">
              <Users className="w-10 h-10 mx-auto mb-2 text-slate-400" />
              <p className="text-slate-700 dark:text-slate-300 text-sm font-semibold">No se encontraron personas</p>
              <p className="text-slate-500 text-xs mt-1">
                {busqueda ? `No hay resultados para "${busqueda}". Prueba otro término.` : "Cambia el documento o filtro de revisión seleccionado."}
              </p>
              {busqueda && (
                <button
                  onClick={() => setBusqueda("")}
                  className="mt-3 text-xs text-[#0071E3] hover:underline cursor-pointer"
                >
                  Limpiar búsqueda
                </button>
              )}
            </div>
          ) : (
            <div className="overflow-x-auto max-h-[600px] overflow-y-auto pr-1">
              <table className="table-base text-xs w-full">
                <thead className="sticky top-0 bg-white/95 dark:bg-[#121620]/95 backdrop-blur z-10 border-b border-slate-200 dark:border-white/[0.08]">
                  <tr>
                    <th className="w-12 text-center py-3">
                      <input
                        type="checkbox"
                        checked={todosVisiblesSeleccionados}
                        onChange={toggleSeleccionarTodo}
                        className="rounded border-slate-700 bg-slate-800 text-[#0071E3] focus:ring-[#0071E3]/40 cursor-pointer"
                      />
                    </th>
                    <th className="py-3">Documento</th>
                    <th className="py-3">Nombre Completo</th>
                    <th className="py-3">F. Nacimiento</th>
                    <th className="py-3">Edad</th>
                    <th className="py-3">Documento PDF de Origen</th>
                    <th className="py-3 text-center">Estado</th>
                  </tr>
                </thead>
                <tbody>
                  {personasFiltradas.map((p) => {
                    const isSelected = seleccionados.has(p.id);
                    const nomCompleto = formatNombreCompleto(p);
                    const esRev = esPersonaEnRevision(p);
                    const docInfo = getTipoDocInfo(p.tipo_documento);
                    const edadNum = p.edad ?? (p.fecha_nacimiento ? calcularEdad(p.fecha_nacimiento) : null);
                    const esMenor = edadNum !== null && edadNum < 14;

                    return (
                      <tr
                        key={p.id}
                        onClick={() => togglePersona(p.id)}
                        className={`cursor-pointer transition-colors ${
                          isSelected
                            ? "bg-[#0071E3]/[0.08] hover:bg-[#0071E3]/[0.12]"
                            : "hover:bg-slate-800/30 opacity-60"
                        }`}
                      >
                        <td className="text-center py-3" onClick={(e) => e.stopPropagation()}>
                          <input
                            type="checkbox"
                            checked={isSelected}
                            onChange={() => togglePersona(p.id)}
                            className="rounded border-slate-700 bg-slate-800 text-[#0071E3] focus:ring-[#0071E3]/40 cursor-pointer"
                          />
                        </td>
                        <td className="whitespace-nowrap py-3">
                          <div className="flex items-center gap-2 flex-nowrap">
                            <span className={`px-1.5 py-0.5 rounded text-[10px] border font-mono tracking-wider shrink-0 ${docInfo.badge}`} title={docInfo.label}>
                              {docInfo.codigo}
                            </span>
                            <span className="font-mono text-emerald-400 font-bold">
                              {p.numero_identificacion}
                            </span>
                          </div>
                        </td>
                        <td className="font-medium text-slate-900 dark:text-slate-100 py-3">
                          {nomCompleto || "—"}
                        </td>
                        <td className="text-slate-600 dark:text-slate-300 font-mono text-[11px] whitespace-nowrap py-3">
                          {p.fecha_nacimiento ? String(p.fecha_nacimiento) : "—"}
                        </td>
                        <td className="font-mono text-[11px] whitespace-nowrap py-3">
                          {esMenor ? (
                            <span className="px-2 py-0.5 rounded-full bg-rose-500/15 border border-rose-500/30 text-rose-400 font-bold text-[10px] inline-flex items-center gap-1">
                              <AlertTriangle className="w-2.5 h-2.5 text-rose-400" />
                              {edadNum} años (Menor)
                            </span>
                          ) : edadNum !== null ? (
                            <span className="text-slate-600 dark:text-slate-300">{edadNum} años</span>
                          ) : (
                            <span className="text-slate-400">—</span>
                          )}
                        </td>
                        <td className="text-slate-600 dark:text-slate-300 font-mono text-[11px] py-3 max-w-[280px] truncate" title={p.nombre_documento || "—"}>
                          <div className="flex items-center gap-1.5 truncate">
                            <FileText className="w-3 h-3 text-slate-400 shrink-0" />
                            <span className="truncate">{p.nombre_documento || "—"}</span>
                          </div>
                        </td>
                        <td className="text-center py-3">
                          {esRev ? (
                            <span className="badge badge-warning text-[10px]">Revisión</span>
                          ) : (
                            <span className="badge badge-success text-[10px]">OK</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          {/* Footer resumen de la tabla */}
          <div className="mt-4 pt-3 border-t border-slate-200/80 dark:border-white/[0.06] flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
            <span>
              Mostrando <strong className="text-slate-900 dark:text-white">{personasFiltradas.length}</strong> de <strong className="text-slate-900 dark:text-white">{personas.length}</strong> personas
            </span>
            <span>
              <strong className="text-emerald-500 font-mono">{seleccionadosVisiblesCount}</strong> seleccionadas para el reporte
            </span>
          </div>
        </div>
      </main>
    </div>
  );
}
