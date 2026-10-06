"use client";

import { useEffect, useState, Fragment } from "react";
import { useRouter } from "next/navigation";
import {
  FileText, Users, GitCompare, AlertTriangle,
  CheckCircle, Clock, TrendingUp, Activity,
  RefreshCw, ChevronRight, ExternalLink, ArrowUpRight,
  X, Search, Eye, ChevronUp, ChevronDown, Download, Trash2, Zap
} from "lucide-react";
import toast from "react-hot-toast";
import Sidebar from "@/components/ui/Sidebar";
import { useSidebar } from "@/context/SidebarContext";
import { apiDocumentos, apiPersonas, apiExportacion } from "@/lib/api";
import { auth } from "@/lib/auth";
import { formatNombreCompleto, calcularEdad, getTipoDocInfo } from "@/lib/formatters";
import type { DashboardStats, Documento, Persona } from "@/types";

function StatCard({
  title,
  value,
  icon,
  subtitle,
}: {
  title: string;
  value: number | string;
  icon: React.ReactNode;
  color?: string;
  subtitle?: string;
}) {
  return (
    <div className="relative rounded-2xl p-5 bg-white/70 dark:bg-[#121620]/60 backdrop-blur-xl border border-slate-200/80 dark:border-white/[0.08] shadow-[0_2px_12px_rgba(0,0,0,0.03)] dark:shadow-[0_4px_24px_rgba(0,0,0,0.25)] transition-all duration-200 hover:border-slate-300 dark:hover:border-white/[0.16] hover:shadow-md group active:scale-[0.99] overflow-hidden">
      {/* Reflejo sutil superior (light-catching top edge) */}
      <div className="absolute inset-x-0 top-0 h-[1px] bg-gradient-to-r from-transparent via-slate-300/40 dark:via-white/10 to-transparent pointer-events-none" />

      <div className="flex items-start justify-between gap-3 mb-3">
        <span className="text-xs font-medium text-slate-500 dark:text-slate-400 tracking-tight">
          {title}
        </span>
        <div className="w-8 h-8 rounded-xl bg-slate-100 dark:bg-white/[0.05] border border-slate-200/60 dark:border-white/[0.08] flex items-center justify-center text-slate-600 dark:text-slate-300 transition-transform duration-200 group-hover:scale-105 shrink-0">
          {icon}
        </div>
      </div>

      <div className="space-y-1">
        <div className="text-3xl lg:text-[34px] font-semibold text-slate-900 dark:text-slate-50 tracking-[-0.04em] leading-none">
          {typeof value === "number" ? value.toLocaleString() : value}
        </div>
        {subtitle && (
          <p className="text-[11px] text-slate-400 dark:text-slate-400/90 font-normal mt-1.5">
            {subtitle}
          </p>
        )}
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const router = useRouter();
  const { collapsed } = useSidebar();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [cargando, setCargando] = useState(true);

  // Historial de Fichas
  const [documentosHistorial, setDocumentosHistorial] = useState<Documento[]>([]);
  const [cargandoDocs, setCargandoDocs] = useState(true);

  // Modal de Personas de Ficha (Tabla Separada / Independiente)
  const [docSeleccionadoModal, setDocSeleccionadoModal] = useState<Documento | null>(null);
  const [personasFicha, setPersonasFicha] = useState<Persona[]>([]);
  const [cargandoPersonasFicha, setCargandoPersonasFicha] = useState(false);
  const [busquedaModal, setBusquedaModal] = useState("");
  const [personaDetalleId, setPersonaDetalleId] = useState<string | null>(null);
  const [exportandoModal, setExportandoModal] = useState(false);

  const abrirPersonasFicha = async (doc: Documento) => {
    setDocSeleccionadoModal(doc);
    setPersonasFicha([]);
    setPersonaDetalleId(null);
    setBusquedaModal("");
    setCargandoPersonasFicha(true);
    try {
      // Usar endpoint dedicado que garantiza fallback a metadatos históricos si la tabla fue vaciada
      const res = await apiDocumentos.obtenerPersonas(doc.id);
      const items = Array.isArray(res.data) ? res.data : [];
      setPersonasFicha(items);
    } catch (err) {
      console.error("Error al cargar personas de la ficha:", err);
      try {
        const res2 = await apiPersonas.listar({ documento_id: doc.id, limit: 200 });
        const items2 = Array.isArray(res2.data) ? res2.data : (res2.data as any).items || [];
        setPersonasFicha(items2);
      } catch {
        setPersonasFicha([]);
      }
    } finally {
      setCargandoPersonasFicha(false);
    }
  };

  const exportarFichaModal = async () => {
    if (!docSeleccionadoModal) return;
    setExportandoModal(true);
    try {
      const nombreLimpio = docSeleccionadoModal.nombre_original.replace(/\.[^/.]+$/, "");
      await apiExportacion.descargarXlsx({
        documentoId: docSeleccionadoModal.id,
        nombreArchivo: `personas_${nombreLimpio}.xlsx`,
      });
    } catch (err) {
      console.error("Error al exportar ficha:", err);
    } finally {
      setExportandoModal(false);
    }
  };

  // Estado para modal de confirmación de eliminación de ficha
  const [fichaAEliminar, setFichaAEliminar] = useState<Documento | null>(null);
  const [eliminandoFicha, setEliminandoFicha] = useState(false);

  const confirmarEliminarFicha = async () => {
    if (!fichaAEliminar) return;
    setEliminandoFicha(true);
    const toastId = toast.loading(`Eliminando ficha ${fichaAEliminar.nombre_original}...`);
    try {
      await apiDocumentos.eliminar(fichaAEliminar.id, true);
      toast.success(`Ficha eliminada del historial`, { id: toastId });
      setDocumentosHistorial((prev) => prev.filter((d) => d.id !== fichaAEliminar.id));
      if (docSeleccionadoModal?.id === fichaAEliminar.id) {
        setDocSeleccionadoModal(null);
      }
      setFichaAEliminar(null);
      const resStats = await apiDocumentos.estadisticas().catch(() => null);
      if (resStats?.data) setStats(resStats.data);
    } catch (err) {
      console.error("Error al eliminar ficha del historial:", err);
      toast.error("Error al eliminar la ficha del historial", { id: toastId });
    } finally {
      setEliminandoFicha(false);
    }
  };

  useEffect(() => {
    if (!auth.isAuthenticated()) {
      router.push("/");
      return;
    }
    cargarDatos();

    const intervalo = setInterval(cargarDatos, 15000);
    return () => clearInterval(intervalo);
  }, []);

  const cargarDatos = async () => {
    try {
      const [resStats, resDocs] = await Promise.all([
        apiDocumentos.estadisticas().catch(() => null),
        apiDocumentos.listar({ limit: 30 }).catch(() => null),
      ]);
      if (resStats?.data) setStats(resStats.data);
      const docs = Array.isArray(resDocs?.data) ? resDocs.data : [];
      setDocumentosHistorial(docs);
    } catch (err) {
      console.error("Error cargando datos del dashboard:", err);
    } finally {
      setCargando(false);
      setCargandoDocs(false);
    }
  };

  return (
    <div className="flex min-h-screen bg-[#F5F5F7] dark:bg-[#0A0D14] text-slate-900 dark:text-slate-100 font-sans w-full max-w-full overflow-x-hidden transition-colors duration-200">
      <Sidebar />

      <main className={`${collapsed ? "ml-20 max-w-[calc(100vw-5rem)]" : "ml-64 max-w-[calc(100vw-16rem)]"} transition-all duration-300 ease-out flex-1 p-6 lg:p-10 min-w-0 overflow-x-hidden`}>
        {/* Header al estilo Apple (limpio, tipografía con optical sizing, sin estridencias) */}
        <div className="mb-8 page-enter flex flex-col sm:flex-row sm:items-end justify-between gap-4">
          <div>
            <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full bg-slate-200/60 dark:bg-white/[0.06] border border-slate-300/50 dark:border-white/[0.08] backdrop-blur-md mb-3">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              <span className="text-[11px] font-medium text-slate-700 dark:text-slate-300 tracking-tight">KondID Engine • Activo</span>
            </div>
            <h1 className="text-3xl lg:text-4xl font-semibold text-slate-900 dark:text-white tracking-[-0.03em] leading-tight">
              KondID
            </h1>
            <p className="text-slate-500 dark:text-slate-400 mt-1 text-sm font-normal max-w-xl">
              Plataforma de extracción, auditoría y conciliación de documentos de identidad colombianos.
            </p>
          </div>

          <div className="flex items-center gap-2.5 shrink-0">
            <button
              onClick={cargarDatos}
              className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-white/80 dark:bg-white/[0.06] hover:bg-slate-100 dark:hover:bg-white/[0.1] text-slate-700 dark:text-slate-200 border border-slate-200/80 dark:border-white/[0.08] text-xs font-medium transition-all duration-150 active:scale-[0.98] cursor-pointer shadow-sm backdrop-blur-md"
              title="Recargar datos"
            >
              <RefreshCw className="w-3.5 h-3.5 text-slate-500 dark:text-slate-400" />
              <span>Actualizar</span>
            </button>
            <button
              onClick={() => router.push("/documentos")}
              className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-[#0071E3] hover:bg-[#0077ED] text-white text-xs font-medium transition-all duration-150 active:scale-[0.98] cursor-pointer shadow-sm shadow-[#0071E3]/20"
            >
              <span>Subir Lote</span>
              <ArrowUpRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {/* Stats Grid - Métrica limpia inspirada en Apple (sin neones ni colores fosforescentes) */}
        {cargando ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4 mb-8">
            {Array(7).fill(0).map((_, i) => (
              <div key={i} className="h-28 rounded-2xl bg-slate-200/50 dark:bg-white/[0.03] animate-pulse border border-slate-200/40 dark:border-white/[0.05]" />
            ))}
          </div>
        ) : stats ? (
          <>
            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4 mb-8 page-enter">
              <StatCard
                title="Total Documentos"
                value={stats.total_documentos}
                icon={<FileText className="w-4 h-4" />}
                subtitle="PDFs cargados al sistema"
              />
              <StatCard
                title="Completados"
                value={stats.documentos_completados}
                icon={<CheckCircle className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />}
                subtitle="Extracción OCR exitosa"
              />
              <StatCard
                title="En Proceso"
                value={stats.documentos_procesando}
                icon={<Clock className="w-4 h-4 text-amber-600 dark:text-amber-400" />}
                subtitle="Procesando en segundo plano"
              />
              <StatCard
                title="Con Error"
                value={stats.documentos_con_error}
                icon={<AlertTriangle className="w-4 h-4 text-rose-600 dark:text-rose-400" />}
                subtitle="Requieren verificación"
              />
              <StatCard
                title="Total Personas"
                value={stats.total_personas}
                icon={<Users className="w-4 h-4 text-[#0071E3] dark:text-[#3894FF]" />}
                subtitle="Identificaciones en BD"
              />
              <StatCard
                title="En Revisión"
                value={stats.personas_en_revision}
                icon={<AlertTriangle className="w-4 h-4 text-amber-600 dark:text-amber-400" />}
                subtitle="Calidad < 70% o discrepancias"
              />
              <StatCard
                title="Comparaciones"
                value={stats.total_comparaciones}
                icon={<GitCompare className="w-4 h-4 text-slate-600 dark:text-slate-300" />}
                subtitle="Auditorías contra planilla"
              />
              {stats.total_documentos > 0 && (
                <StatCard
                  title="Tasa de Éxito"
                  value={`${Math.round((stats.documentos_completados / stats.total_documentos) * 100)}%`}
                  icon={<TrendingUp className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />}
                  subtitle="Eficacia del pipeline OCR"
                />
              )}
            </div>

            {/* Accesos rápidos - Tarjetas con material translúcido y microinteracciones de Apple */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8 page-enter">
              {[
                {
                  title: "Subir documentos",
                  desc: "Cargar PDFs con planilla Excel oficial",
                  href: "/documentos",
                  icon: <FileText className="w-5 h-5 text-slate-700 dark:text-slate-200" />,
                  tag: "Lote PDF",
                },
                {
                  title: "Base de Personas",
                  desc: "Explorar registros, visor y corrección manual",
                  href: "/personas",
                  icon: <Users className="w-5 h-5 text-slate-700 dark:text-slate-200" />,
                  tag: "Directorio",
                },
                {
                  title: "Conciliación Excel",
                  desc: "Auditar diferencias campo a campo con 1 clic",
                  href: "/comparacion",
                  icon: <GitCompare className="w-5 h-5 text-slate-700 dark:text-slate-200" />,
                  tag: "Auditoría",
                },
              ].map((item) => (
                <button
                  key={item.href}
                  onClick={() => router.push(item.href)}
                  className="relative p-5 rounded-2xl bg-white/70 dark:bg-[#121620]/60 backdrop-blur-xl border border-slate-200/80 dark:border-white/[0.08] hover:border-slate-300 dark:hover:border-white/[0.18] shadow-[0_2px_12px_rgba(0,0,0,0.03)] dark:shadow-[0_4px_24px_rgba(0,0,0,0.25)] hover:shadow-md transition-all duration-200 cursor-pointer text-left group active:scale-[0.98] overflow-hidden"
                >
                  <div className="absolute inset-x-0 top-0 h-[1px] bg-gradient-to-r from-transparent via-slate-300/40 dark:via-white/10 to-transparent pointer-events-none" />
                  <div className="flex items-center justify-between mb-3.5">
                    <div className="w-9 h-9 rounded-xl bg-slate-100 dark:bg-white/[0.06] border border-slate-200/60 dark:border-white/[0.08] flex items-center justify-center transition-transform duration-200 group-hover:scale-105">
                      {item.icon}
                    </div>
                    <span className="text-[10px] font-medium tracking-wide uppercase px-2 py-0.5 rounded-full bg-slate-100 dark:bg-white/[0.05] text-slate-500 dark:text-slate-400 border border-slate-200/60 dark:border-white/[0.06]">
                      {item.tag}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="font-semibold text-sm text-slate-900 dark:text-white tracking-tight">
                        {item.title}
                      </h3>
                      <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                        {item.desc}
                      </p>
                    </div>
                    <ChevronRight className="w-4 h-4 text-slate-400 dark:text-slate-500 group-hover:translate-x-1 group-hover:text-slate-900 dark:group-hover:text-white transition-all duration-200 shrink-0 ml-2" />
                  </div>
                </button>
              ))}
            </div>

            {/* ── HISTORIAL DE FICHAS / DOCUMENTOS ── */}
            <div className="relative rounded-2xl bg-white/70 dark:bg-[#121620]/60 backdrop-blur-xl border border-slate-200/80 dark:border-white/[0.08] shadow-[0_2px_12px_rgba(0,0,0,0.03)] dark:shadow-[0_4px_24px_rgba(0,0,0,0.25)] overflow-hidden mb-8 page-enter">
              <div className="absolute inset-x-0 top-0 h-[1px] bg-gradient-to-r from-transparent via-slate-300/40 dark:via-white/10 to-transparent pointer-events-none" />

              <div className="p-5 border-b border-slate-200/70 dark:border-white/[0.06] flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-slate-50/50 dark:bg-white/[0.02]">
                <div>
                  <div className="flex items-center gap-2.5">
                    <div className="w-8 h-8 rounded-xl bg-slate-100 dark:bg-white/[0.06] border border-slate-200/60 dark:border-white/[0.08] flex items-center justify-center text-slate-700 dark:text-slate-300">
                      <FileText className="w-4 h-4" />
                    </div>
                    <div>
                      <h2 className="text-base font-semibold text-slate-900 dark:text-white tracking-tight">
                        Historial de Fichas Subidas
                      </h2>
                      <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                        Selecciona cualquier fila para inspeccionar las personas extraídas y su estado de validación.
                      </p>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={cargarDatos}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-100/80 hover:bg-slate-200/80 dark:bg-white/[0.06] dark:hover:bg-white/[0.1] text-slate-700 dark:text-slate-200 border border-slate-200/60 dark:border-white/[0.08] text-xs font-medium transition-all cursor-pointer active:scale-[0.97]"
                    title="Recargar historial de fichas"
                  >
                    <RefreshCw className="w-3.5 h-3.5 text-slate-500 dark:text-slate-400" />
                    <span>Actualizar</span>
                  </button>
                  <button
                    onClick={() => router.push("/documentos")}
                    className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-[#0071E3] hover:bg-[#0077ED] text-white text-xs font-medium transition-all cursor-pointer shadow-sm active:scale-[0.97]"
                  >
                    <span>Subir Ficha</span>
                    <ArrowUpRight className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>

              {/* Listado / Tabla de Fichas */}
              {cargandoDocs ? (
                <div className="p-6 space-y-3">
                  {Array(4).fill(0).map((_, i) => (
                    <div key={i} className="h-12 bg-slate-100 dark:bg-white/[0.03] animate-pulse rounded-xl" />
                  ))}
                </div>
              ) : documentosHistorial.length === 0 ? (
                <div className="text-center py-14 px-4">
                  <div className="w-12 h-12 rounded-2xl bg-slate-100 dark:bg-white/[0.04] border border-slate-200/60 dark:border-white/[0.06] flex items-center justify-center mx-auto mb-3 text-slate-400">
                    <FileText className="w-5 h-5" />
                  </div>
                  <p className="text-sm font-semibold text-slate-800 dark:text-slate-200">No hay fichas registradas</p>
                  <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">Sube tu primer lote de archivos PDF en el módulo de documentos para iniciar el procesamiento OCR.</p>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse">
                    <thead>
                      <tr className="border-b border-slate-200/70 dark:border-white/[0.06] bg-slate-50/40 dark:bg-white/[0.015] text-[11px] font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                        <th className="py-3 px-4">Ficha / Documento PDF</th>
                        <th className="py-3 px-3 text-center">Fecha de Carga</th>
                        <th className="py-3 px-3 text-center">Personas</th>
                        <th className="py-3 px-3 text-center">Estado</th>
                        <th className="py-3 px-3 text-center">Confianza</th>
                        <th className="py-3 px-4 text-right">Acción</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-white/[0.04] text-xs">
                      {documentosHistorial.map((doc) => {
                        return (
                          <tr
                            key={doc.id}
                            onClick={() => abrirPersonasFicha(doc)}
                            className="transition-colors cursor-pointer hover:bg-slate-50/80 dark:hover:bg-white/[0.03] text-slate-800 dark:text-slate-200 group"
                          >
                            <td className="py-3 px-4">
                              <div className="flex items-center gap-3 min-w-0">
                                <div className="w-8 h-8 rounded-lg bg-slate-100 dark:bg-white/[0.06] border border-slate-200/60 dark:border-white/[0.08] flex items-center justify-center text-slate-600 dark:text-slate-300 shrink-0">
                                  <FileText className="w-4 h-4" />
                                </div>
                                <div className="min-w-0">
                                  <span className="font-medium block truncate max-w-[320px] text-slate-900 dark:text-slate-100 group-hover:text-[#0071E3] dark:group-hover:text-blue-400 transition-colors" title={doc.nombre_original}>
                                    {doc.nombre_original}
                                  </span>
                                  <span className="text-[10px] text-slate-400 font-mono">
                                    ID: {doc.id.slice(0, 8)}…
                                  </span>
                                </div>
                              </div>
                            </td>
                            <td className="py-3 px-3 text-center text-slate-500 dark:text-slate-400 whitespace-nowrap text-[11px]">
                              {doc.fecha_carga ? new Date(doc.fecha_carga).toLocaleDateString("es-CO", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" }) : "—"}
                            </td>
                            <td className="py-3 px-3 text-center whitespace-nowrap">
                              <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-slate-100 dark:bg-white/[0.05] border border-slate-200/60 dark:border-white/[0.08] font-mono text-[11px] font-medium text-slate-700 dark:text-slate-300">
                                <Users className="w-3 h-3 text-slate-400 shrink-0" />
                                <span>{doc.total_personas ?? 0}</span>
                              </span>
                            </td>
                            <td className="py-3 px-3 text-center whitespace-nowrap">
                              {doc.estado === "completado" ? (
                                <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-600 dark:text-emerald-400 text-[10px] font-medium">
                                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" /> Completado
                                </span>
                              ) : doc.estado === "procesando" ? (
                                <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-amber-500/10 border border-amber-500/20 text-amber-600 dark:text-amber-400 text-[10px] font-medium">
                                  <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse" /> Procesando
                                </span>
                              ) : (
                                <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-rose-500/10 border border-rose-500/20 text-rose-600 dark:text-rose-400 text-[10px] font-medium">
                                  <span className="w-1.5 h-1.5 rounded-full bg-rose-500" /> {doc.estado}
                                </span>
                              )}
                            </td>
                            <td className="py-3 px-3 text-center font-mono text-xs font-medium text-slate-700 dark:text-slate-300">
                              {doc.confianza_ocr != null ? `${Math.round(doc.confianza_ocr)}%` : "—"}
                            </td>
                            <td className="py-3 px-4 text-right whitespace-nowrap">
                              <div className="flex items-center justify-end gap-1">
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    abrirPersonasFicha(doc);
                                  }}
                                  className="p-1.5 rounded-lg text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-white/[0.08] transition-all cursor-pointer active:scale-[0.95]"
                                  title="Visualizar personas de este archivo"
                                >
                                  <Eye className="w-4 h-4" />
                                </button>
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    setFichaAEliminar(doc);
                                  }}
                                  className="p-1.5 rounded-lg text-slate-400 hover:text-rose-600 dark:hover:text-rose-400 hover:bg-rose-500/10 transition-all cursor-pointer active:scale-[0.95]"
                                  title="Eliminar esta ficha del historial"
                                >
                                  <Trash2 className="w-3.5 h-3.5" />
                                </button>
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </>
        ) : (
          <div className="card text-center py-12">
            <p className="text-slate-400">Error cargando estadísticas</p>
          </div>
        )}
      </main>

      {/* ── MODAL: TABLA DISTINTA E INDEPENDIENTE DE PERSONAS DE LA FICHA ── */}
      {docSeleccionadoModal && (
        <div
          className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xl flex items-center justify-center p-3 sm:p-6 animate-in fade-in duration-200"
          onClick={() => setDocSeleccionadoModal(null)}
        >
          <div
            className="relative bg-white/95 dark:bg-[#121620]/95 backdrop-blur-2xl border border-slate-200/80 dark:border-white/[0.1] rounded-3xl shadow-[0_25px_60px_-15px_rgba(0,0,0,0.35)] w-full max-w-5xl max-h-[90vh] flex flex-col overflow-hidden animate-in zoom-in-95 duration-200"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="absolute inset-x-0 top-0 h-[1px] bg-gradient-to-r from-transparent via-slate-300/40 dark:via-white/15 to-transparent pointer-events-none" />

            {/* Modal Header */}
            <div className="p-5 border-b border-slate-200/70 dark:border-white/[0.06] bg-slate-50/50 dark:bg-white/[0.02] flex items-start justify-between gap-4">
              <div className="min-w-0">
                <div className="flex items-center gap-2.5 flex-wrap mb-1.5">
                  <div className="w-9 h-9 rounded-xl bg-slate-100 dark:bg-white/[0.06] border border-slate-200/60 dark:border-white/[0.08] flex items-center justify-center text-slate-700 dark:text-slate-300 shrink-0">
                    <FileText className="w-4 h-4" />
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] uppercase font-medium tracking-wider text-slate-500 dark:text-slate-400 bg-slate-100 dark:bg-white/[0.05] px-2 py-0.5 rounded-full border border-slate-200/60 dark:border-white/[0.06]">
                        Ficha seleccionada
                      </span>
                    </div>
                    <h3 className="text-base font-semibold text-slate-900 dark:text-white truncate max-w-[500px] mt-0.5" title={docSeleccionadoModal.nombre_original}>
                      {docSeleccionadoModal.nombre_original}
                    </h3>
                  </div>
                </div>

                <div className="flex items-center gap-2.5 text-xs text-slate-500 dark:text-slate-400 flex-wrap mt-2.5">
                  <span className="bg-slate-100 dark:bg-white/[0.04] px-2.5 py-1 rounded-lg border border-slate-200/60 dark:border-white/[0.06] font-mono text-[11px] text-slate-700 dark:text-slate-300 inline-flex items-center gap-1.5">
                    <Zap className="w-3 h-3 text-amber-500 shrink-0" />
                    <span>Confianza: {docSeleccionadoModal.confianza_ocr != null ? `${Math.round(docSeleccionadoModal.confianza_ocr)}%` : "—"}</span>
                  </span>
                  <span className="bg-slate-100 dark:bg-white/[0.04] px-2.5 py-1 rounded-lg border border-slate-200/60 dark:border-white/[0.06] font-medium text-[11px] text-slate-700 dark:text-slate-300 inline-flex items-center gap-1.5">
                    <Users className="w-3 h-3 text-slate-400 shrink-0" />
                    <span>{personasFicha.length} {personasFicha.length === 1 ? "persona encontrada" : "personas encontradas"}</span>
                  </span>
                  <span className="text-[11px] text-slate-400">
                    Cargado: {docSeleccionadoModal.fecha_carga ? new Date(docSeleccionadoModal.fecha_carga).toLocaleDateString("es-CO", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" }) : "—"}
                  </span>
                </div>
              </div>

              {/* Botones de acción del Modal */}
              <div className="flex items-center gap-2 shrink-0">
                <button
                  onClick={exportarFichaModal}
                  disabled={exportandoModal || personasFicha.length === 0}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-100/90 hover:bg-slate-200/90 dark:bg-white/[0.06] dark:hover:bg-white/[0.1] text-slate-700 dark:text-slate-200 border border-slate-200/60 dark:border-white/[0.08] text-xs font-medium transition-all cursor-pointer active:scale-[0.97] disabled:opacity-40"
                  title="Exportar la lista de personas de esta ficha a Excel"
                >
                  <Download className="w-3.5 h-3.5" />
                  <span>{exportandoModal ? "Exportando..." : "Exportar"}</span>
                </button>
                <button
                  onClick={() => setFichaAEliminar(docSeleccionadoModal)}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-rose-600 dark:text-rose-400 hover:bg-rose-500/10 border border-rose-500/20 text-xs font-medium transition-all cursor-pointer active:scale-[0.97]"
                  title="Eliminar esta ficha del historial"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                  <span>Eliminar</span>
                </button>
                <button
                  onClick={() => setDocSeleccionadoModal(null)}
                  className="p-1.5 rounded-xl text-slate-400 hover:text-slate-700 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-white/[0.08] transition-colors cursor-pointer shrink-0"
                  title="Cerrar ventana"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            </div>

            {/* Aviso explicativo y buscador local */}
            <div className="px-5 py-2.5 bg-slate-50/70 dark:bg-white/[0.015] border-b border-slate-200/70 dark:border-white/[0.06] text-xs flex items-center justify-between gap-3 flex-wrap">
              <span className="flex items-center gap-1.5 text-slate-500 dark:text-slate-400 text-[11px]">
                <CheckCircle className="w-3.5 h-3.5 text-emerald-500 shrink-0" />
                Registros exclusivos extraídos de este archivo en particular.
              </span>
              <div className="relative min-w-[240px]">
                <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
                <input
                  type="text"
                  placeholder="Buscar por cédula o nombre..."
                  value={busquedaModal}
                  onChange={(e) => setBusquedaModal(e.target.value)}
                  className="w-full pl-8 pr-3 py-1.5 text-xs bg-white dark:bg-white/[0.04] border border-slate-200/80 dark:border-white/[0.08] rounded-xl text-slate-900 dark:text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-[#0071E3]/20 focus:border-[#0071E3] transition-all"
                />
              </div>
            </div>

            {/* Modal Body: Tabla de Personas */}
            <div className="overflow-y-auto flex-1 p-5 min-h-[250px] max-h-[58vh]">
              {cargandoPersonasFicha ? (
                <div className="space-y-3 py-6">
                  {Array(4).fill(0).map((_, i) => (
                    <div key={i} className="h-12 bg-slate-100 dark:bg-white/[0.03] animate-pulse rounded-xl" />
                  ))}
                </div>
              ) : personasFicha.filter((p) => {
                if (!busquedaModal) return true;
                const q = busquedaModal.toLowerCase().trim().replace(/[.\s]/g, "");
                const cedula = String(p.numero_identificacion || "").replace(/[.\s]/g, "");
                const nom = formatNombreCompleto(p).toLowerCase();
                return cedula.includes(q) || nom.includes(q);
              }).length === 0 ? (
                <div className="text-center py-16">
                  <div className="w-10 h-10 rounded-xl bg-slate-100 dark:bg-white/[0.04] border border-slate-200/60 dark:border-white/[0.06] flex items-center justify-center mx-auto mb-2 text-slate-400">
                    <Users className="w-5 h-5" />
                  </div>
                  <p className="text-sm font-semibold text-slate-800 dark:text-slate-200">
                    {busquedaModal ? `Sin resultados para "${busquedaModal}"` : "No se registraron personas para esta ficha"}
                  </p>
                  <p className="text-xs text-slate-500 mt-0.5">
                    El documento puede estar en procesamiento o no contener cédulas legibles.
                  </p>
                </div>
              ) : (
                <div className="overflow-x-auto rounded-xl border border-slate-200/80 dark:border-white/[0.08]">
                  <table className="w-full text-left border-collapse">
                    <thead>
                      <tr className="border-b border-slate-200/80 dark:border-white/[0.08] bg-slate-50/60 dark:bg-white/[0.02] text-[11px] font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                        <th className="py-2.5 px-3 w-10 text-center">#</th>
                        <th className="py-2.5 px-3 whitespace-nowrap">Documento / Cédula</th>
                        <th className="py-2.5 px-3 whitespace-nowrap">Nombre Completo</th>
                        <th className="py-2.5 px-3 text-center whitespace-nowrap">Edad</th>
                        <th className="py-2.5 px-3 text-center whitespace-nowrap">Página</th>
                        <th className="py-2.5 px-3 text-center whitespace-nowrap">Estado OCR</th>
                        <th className="py-2.5 px-3 text-right whitespace-nowrap">Detalles</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-white/[0.04] text-xs">
                      {personasFicha
                        .filter((p) => {
                          if (!busquedaModal) return true;
                          const q = busquedaModal.toLowerCase().trim().replace(/[.\s]/g, "");
                          const cedula = String(p.numero_identificacion || "").replace(/[.\s]/g, "");
                          const nom = formatNombreCompleto(p).toLowerCase();
                          return cedula.includes(q) || nom.includes(q);
                        })
                        .map((p, idx) => {
                          const nombre = formatNombreCompleto(p);
                          const edad = p.edad ?? calcularEdad(p.fecha_nacimiento);
                          const esMenor14 = edad !== null && edad < 14;
                          const tipoInfo = getTipoDocInfo(p.tipo_documento);
                          const isExpanded = personaDetalleId === p.id;

                          return (
                            <Fragment key={p.id}>
                              <tr
                                onClick={() => setPersonaDetalleId(isExpanded ? null : p.id)}
                                className={`transition-colors cursor-pointer hover:bg-slate-50/80 dark:hover:bg-white/[0.03] ${
                                  isExpanded ? "bg-slate-100/50 dark:bg-white/[0.04]" : ""
                                }`}
                              >
                                <td className="py-2.5 px-3 text-center text-slate-400 font-mono text-[11px]">
                                  {idx + 1}
                                </td>
                                <td className="py-2.5 px-3 whitespace-nowrap">
                                  <div className="flex items-center gap-1.5 flex-nowrap">
                                    <span className="px-1.5 py-0.5 rounded text-[10px] bg-slate-100 dark:bg-white/[0.06] border border-slate-200/60 dark:border-white/[0.08] text-slate-600 dark:text-slate-300 font-mono tracking-wider shrink-0">
                                      {tipoInfo.codigo}
                                    </span>
                                    <span className="font-mono text-slate-900 dark:text-white font-semibold text-xs tracking-wide">
                                      {p.numero_identificacion}
                                    </span>
                                  </div>
                                </td>
                                <td className="py-2.5 px-3 whitespace-nowrap">
                                  <span className="font-medium text-slate-900 dark:text-slate-100 text-xs">
                                    {nombre || "Sin nombre extraído"}
                                  </span>
                                </td>
                                <td className="py-2.5 px-3 text-center whitespace-nowrap">
                                  {edad !== null ? (
                                    esMenor14 ? (
                                      <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-rose-500/10 border border-rose-500/20 text-rose-600 dark:text-rose-400 font-medium whitespace-nowrap">
                                        {edad} años (MENOR)
                                      </span>
                                    ) : (
                                      <span className="text-[11px] font-mono text-slate-600 dark:text-slate-300">
                                        {edad} años
                                      </span>
                                    )
                                  ) : (
                                    <span className="text-slate-400 text-xs">—</span>
                                  )}
                                </td>
                                <td className="py-2.5 px-3 text-center font-mono text-xs text-slate-600 dark:text-slate-300">
                                  {p.pagina_frente ? `${p.pagina_frente}${p.pagina_reverso ? `/${p.pagina_reverso}` : ""}` : (p.pagina_numero || "1")}
                                </td>
                                <td className="py-2.5 px-3 text-center whitespace-nowrap">
                                  {p.requiere_revision || (p.estado_registro && p.estado_registro !== "VALID") || Boolean((p.detalles_campos as any)?.discrepancia_documento_edad) ? (
                                    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-amber-500/10 border border-amber-500/20 text-amber-600 dark:text-amber-400 text-[10px] font-medium" title={(p.detalles_campos as any)?.discrepancia_documento_edad?.motivo || "Requiere verificación de datos OCR"}>
                                      <AlertTriangle className="w-2.5 h-2.5 text-amber-500" /> REVISAR
                                    </span>
                                  ) : (
                                    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-600 dark:text-emerald-400 text-[10px] font-medium">
                                      <CheckCircle className="w-2.5 h-2.5 text-emerald-500" /> VÁLIDO
                                    </span>
                                  )}
                                </td>
                                <td className="py-2.5 px-3 text-right whitespace-nowrap">
                                  <button
                                    type="button"
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      setPersonaDetalleId(isExpanded ? null : p.id);
                                    }}
                                    className="px-2.5 py-1 rounded-lg text-xs font-medium bg-slate-100 dark:bg-white/[0.06] hover:bg-slate-200 dark:hover:bg-white/[0.1] text-slate-700 dark:text-slate-300 border border-slate-200/60 dark:border-white/[0.08] transition-all inline-flex items-center gap-1 cursor-pointer active:scale-[0.95]"
                                  >
                                    <span>{isExpanded ? "Ocultar" : "Detalles"}</span>
                                    {isExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                                  </button>
                                </td>
                              </tr>

                              {/* Fila desplegable de detalles completos de la persona */}
                              {isExpanded && (
                                <tr className="bg-slate-50/70 dark:bg-white/[0.02] border-b border-slate-200/60 dark:border-white/[0.06]">
                                  <td colSpan={7} className="p-4">
                                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 bg-white dark:bg-[#151922] p-4 rounded-xl border border-slate-200/60 dark:border-white/[0.06]">
                                      <div>
                                        <p className="text-[10px] uppercase font-medium text-slate-400">Fecha de Nacimiento</p>
                                        <p className="font-mono text-xs font-semibold text-slate-900 dark:text-slate-100 mt-0.5">
                                          {p.fecha_nacimiento || "No extraída"}
                                        </p>
                                      </div>
                                      <div>
                                        <p className="text-[10px] uppercase font-medium text-slate-400">Fecha de Expedición</p>
                                        <p className="font-mono text-xs font-semibold text-slate-900 dark:text-slate-100 mt-0.5">
                                          {p.fecha_expedicion || "No extraída"}
                                        </p>
                                      </div>
                                      <div>
                                        <p className="text-[10px] uppercase font-medium text-slate-400">Lugar de Expedición</p>
                                        <p className="text-xs font-semibold text-slate-900 dark:text-slate-100 mt-0.5">
                                          {p.lugar_expedicion || "No extraído"}
                                        </p>
                                      </div>
                                      <div>
                                        <p className="text-[10px] uppercase font-medium text-slate-400">Género / Sexo</p>
                                        <p className="text-xs font-semibold text-slate-900 dark:text-slate-100 mt-0.5">
                                          {p.sexo || (p.detalles_campos as any)?.genero || "No extraído"}
                                        </p>
                                      </div>

                                      {/* Nombre desglosado */}
                                      <div className="sm:col-span-2 lg:col-span-4 pt-2.5 border-t border-slate-100 dark:border-white/[0.06] flex items-center gap-4 flex-wrap text-xs">
                                        <span className="text-slate-500 text-[11px]">
                                          <strong className="text-slate-700 dark:text-slate-300 font-medium">Apellidos:</strong> {p.apellidos || (p.detalles_campos as any)?.primer_apellido || "—"}
                                        </span>
                                        <span className="text-slate-500 text-[11px]">
                                          <strong className="text-slate-700 dark:text-slate-300 font-medium">Nombres:</strong> {p.nombres || (p.detalles_campos as any)?.primer_nombre || "—"}
                                        </span>
                                        {(p.requiere_revision || Boolean((p.detalles_campos as any)?.discrepancia_documento_edad)) && (
                                          <span className="text-amber-600 dark:text-amber-400 text-[11px] bg-amber-500/10 px-2 py-0.5 rounded-full border border-amber-500/20 font-medium inline-flex items-center gap-1.5">
                                            <AlertTriangle className="w-3 h-3 text-amber-500 shrink-0" />
                                            <span>{(p.detalles_campos as any)?.discrepancia_documento_edad?.motivo || "Requiere verificación de datos OCR"}</span>
                                          </span>
                                        )}
                                      </div>
                                    </div>
                                  </td>
                                </tr>
                              )}
                            </Fragment>
                          );
                        })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            {/* Modal Footer */}
            <div className="p-4 border-t border-slate-200/70 dark:border-white/[0.06] bg-slate-50/50 dark:bg-white/[0.02] flex items-center justify-between gap-3 flex-wrap">
              <div className="text-xs text-slate-500 dark:text-slate-400">
                Mostrando <strong className="text-slate-900 dark:text-white font-semibold">
                  {personasFicha.filter((p) => {
                    if (!busquedaModal) return true;
                    const q = busquedaModal.toLowerCase().trim().replace(/[.\s]/g, "");
                    const cedula = String(p.numero_identificacion || "").replace(/[.\s]/g, "");
                    const nom = formatNombreCompleto(p).toLowerCase();
                    return cedula.includes(q) || nom.includes(q);
                  }).length}
                </strong> de <strong className="text-slate-900 dark:text-white font-semibold">{personasFicha.length}</strong> personas
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => {
                    if (docSeleccionadoModal?.id) {
                      if (typeof window !== "undefined") {
                        localStorage.setItem("ultimo_documento_id", docSeleccionadoModal.id);
                        sessionStorage.removeItem("ver_todos_los_archivos");
                      }
                      router.push(`/personas?documento_id=${docSeleccionadoModal.id}`);
                    }
                  }}
                  className="px-3.5 py-1.5 rounded-xl bg-[#0071E3] hover:bg-[#0077ED] text-white text-xs font-medium transition-all cursor-pointer shadow-sm flex items-center gap-1.5 active:scale-[0.97]"
                >
                  <Users className="w-3.5 h-3.5" />
                  <span>Ver en Directorio</span>
                </button>
                <button
                  onClick={() => setDocSeleccionadoModal(null)}
                  className="px-3.5 py-1.5 rounded-xl bg-slate-100 hover:bg-slate-200 dark:bg-white/[0.06] dark:hover:bg-white/[0.1] text-slate-700 dark:text-slate-200 border border-slate-200/60 dark:border-white/[0.08] text-xs font-medium transition-all cursor-pointer active:scale-[0.97]"
                >
                  Cerrar
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── MODAL: CONFIRMACIÓN PARA ELIMINAR FICHA DEL HISTORIAL ── */}
      {fichaAEliminar && (
        <div
          className="fixed inset-0 z-[60] bg-black/60 backdrop-blur-xl flex items-center justify-center p-4 animate-in fade-in duration-200"
          onClick={() => !eliminandoFicha && setFichaAEliminar(null)}
        >
          <div
            className="relative bg-white/95 dark:bg-[#151922]/95 backdrop-blur-2xl border border-slate-200/80 dark:border-white/[0.1] rounded-3xl p-6 max-w-md w-full shadow-[0_25px_50px_-12px_rgba(0,0,0,0.35)] animate-in zoom-in-95 duration-200"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="absolute inset-x-0 top-0 h-[1px] bg-gradient-to-r from-transparent via-slate-300/40 dark:via-white/15 to-transparent pointer-events-none" />

            <div className="flex items-center gap-3.5 mb-4">
              <div className="w-10 h-10 rounded-2xl bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-500/20 flex items-center justify-center shrink-0">
                <Trash2 className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-base font-semibold text-slate-900 dark:text-white tracking-tight">
                  ¿Eliminar ficha del historial?
                </h3>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  Esta acción es irreversible
                </p>
              </div>
            </div>

            <p className="text-xs text-slate-600 dark:text-slate-300 mb-2">
              Se eliminará del historial el siguiente documento y sus registros:
            </p>
            <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-white/[0.03] border border-slate-200/70 dark:border-white/[0.06] text-xs font-mono text-slate-900 dark:text-slate-100 mb-4 break-all">
              <div className="font-semibold flex items-center gap-2">
                <FileText className="w-4 h-4 text-slate-400 shrink-0" />
                <span className="truncate">{fichaAEliminar.nombre_original}</span>
              </div>
              <div className="text-[11px] text-slate-500 dark:text-slate-400 mt-1.5 flex items-center gap-3">
                <span>{fichaAEliminar.total_personas ?? 0} personas asociadas</span>
              </div>
            </div>

            <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-700 dark:text-rose-300 text-xs font-medium mb-5">
              Se eliminará el archivo PDF procesado y todas las personas asociadas de la base de datos de manera definitiva.
            </div>

            <div className="flex items-center justify-end gap-2.5">
              <button
                onClick={() => setFichaAEliminar(null)}
                disabled={eliminandoFicha}
                className="px-3.5 py-2 rounded-xl text-xs font-medium text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-white/[0.06] border border-slate-200/60 dark:border-white/[0.08] transition-all cursor-pointer disabled:opacity-40 active:scale-[0.97]"
              >
                Cancelar
              </button>
              <button
                onClick={confirmarEliminarFicha}
                disabled={eliminandoFicha}
                className="px-4 py-2 rounded-xl text-xs font-medium text-white bg-[#FF3B30] hover:bg-[#E0342A] transition-all cursor-pointer shadow-sm flex items-center gap-2 disabled:opacity-40 active:scale-[0.97]"
              >
                {eliminandoFicha ? (
                  <>
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                    <span>Eliminando...</span>
                  </>
                ) : (
                  <>
                    <Trash2 className="w-3.5 h-3.5" />
                    <span>Eliminar Ficha</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
