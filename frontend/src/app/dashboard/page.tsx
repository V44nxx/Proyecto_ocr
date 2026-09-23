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
  color,
  subtitle,
}: {
  title: string;
  value: number | string;
  icon: React.ReactNode;
  color: string;
  subtitle?: string;
}) {
  return (
    <div className="stats-card group">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-slate-400 text-sm mb-1">{title}</p>
          <p className="text-4xl font-bold text-white">
            {typeof value === "number" ? value.toLocaleString() : value}
          </p>
          {subtitle && <p className="text-xs text-slate-500 mt-1">{subtitle}</p>}
        </div>
        <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${color} transition-transform group-hover:scale-110`}>
          {icon}
        </div>
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
    <div className="flex min-h-screen bg-slate-50 dark:bg-[#0b0f19] text-slate-900 dark:text-slate-100 font-sans w-full max-w-full overflow-x-hidden">
      <Sidebar />

      <main className={`${collapsed ? "ml-20 max-w-[calc(100vw-5rem)]" : "ml-64 max-w-[calc(100vw-16rem)]"} transition-all duration-300 ease-in-out flex-1 p-6 lg:p-8 min-w-0 overflow-x-hidden`}>
        {/* Header */}
        <div className="mb-8 page-enter">
          <div className="flex items-center gap-2 mb-1">
            <Activity className="w-5 h-5 text-primary-600 dark:text-primary-400" />
            <span className="text-primary-700 dark:text-primary-400 text-sm font-semibold">Panel de Control</span>
          </div>
          <h1 className="text-3xl font-extrabold text-slate-900 dark:text-white tracking-tight">Dashboard</h1>
          <p className="text-slate-600 dark:text-slate-400 mt-1 text-sm">
            Resumen en tiempo real del sistema OCR e historial interactivo de fichas procesadas
          </p>
        </div>

        {/* Stats Grid */}
        {cargando ? (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6 mb-8">
            {Array(7).fill(0).map((_, i) => (
              <div key={i} className="card skeleton h-32 rounded-2xl" />
            ))}
          </div>
        ) : stats ? (
          <>
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4 mb-8 page-enter">
              <StatCard
                title="Total Documentos"
                value={stats.total_documentos}
                icon={<FileText className="w-6 h-6 text-blue-400" />}
                color="bg-blue-500/10 border border-blue-500/20"
                subtitle="PDFs subidos al sistema"
              />
              <StatCard
                title="Completados"
                value={stats.documentos_completados}
                icon={<CheckCircle className="w-6 h-6 text-green-400" />}
                color="bg-green-500/10 border border-green-500/20"
                subtitle="OCR exitoso"
              />
              <StatCard
                title="En Proceso"
                value={stats.documentos_procesando}
                icon={<Clock className="w-6 h-6 text-yellow-400" />}
                color="bg-yellow-500/10 border border-yellow-500/20"
                subtitle="Procesando ahora"
              />
              <StatCard
                title="Con Error"
                value={stats.documentos_con_error}
                icon={<AlertTriangle className="w-6 h-6 text-red-400" />}
                color="bg-red-500/10 border border-red-500/20"
                subtitle="Requieren atención"
              />
              <StatCard
                title="Total Personas"
                value={stats.total_personas}
                icon={<Users className="w-6 h-6 text-purple-400" />}
                color="bg-purple-500/10 border border-purple-500/20"
                subtitle="Registros en BD"
              />
              <StatCard
                title="En Revisión"
                value={stats.personas_en_revision}
                icon={<AlertTriangle className="w-6 h-6 text-orange-400" />}
                color="bg-orange-500/10 border border-orange-500/20"
                subtitle="Confianza baja"
              />
              <StatCard
                title="Comparaciones"
                value={stats.total_comparaciones}
                icon={<GitCompare className="w-6 h-6 text-cyan-400" />}
                color="bg-cyan-500/10 border border-cyan-500/20"
                subtitle="Análisis realizados"
              />
              {stats.total_documentos > 0 && (
                <StatCard
                  title="Tasa de Éxito"
                  value={`${Math.round((stats.documentos_completados / stats.total_documentos) * 100)}%`}
                  icon={<TrendingUp className="w-6 h-6 text-emerald-400" />}
                  color="bg-emerald-500/10 border border-emerald-500/20"
                  subtitle="Documentos procesados OK"
                />
              )}
            </div>

            {/* Accesos rápidos */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8 page-enter">
              {[
                {
                  title: "Subir documentos",
                  desc: "Cargar PDFs para procesamiento OCR",
                  href: "/documentos",
                  color: "from-blue-600/20 to-blue-800/10",
                  border: "border-blue-500/20",
                  icon: <FileText className="w-7 h-7 text-blue-400" />,
                },
                {
                  title: "Ver personas",
                  desc: "Revisar y corregir datos extraídos",
                  href: "/personas",
                  color: "from-purple-600/20 to-purple-800/10",
                  border: "border-purple-500/20",
                  icon: <Users className="w-7 h-7 text-purple-400" />,
                },
                {
                  title: "Comparar datos",
                  desc: "Cargar Excel externo y contrastar",
                  href: "/comparacion",
                  color: "from-cyan-600/20 to-cyan-800/10",
                  border: "border-cyan-500/20",
                  icon: <GitCompare className="w-7 h-7 text-cyan-400" />,
                },
              ].map((item) => (
                <button
                  key={item.href}
                  onClick={() => router.push(item.href)}
                  className={`card text-left bg-gradient-to-br ${item.color} border ${item.border} hover:scale-[1.01] transition-all duration-200 cursor-pointer p-5`}
                >
                  <div className="mb-2.5">{item.icon}</div>
                  <h3 className="text-white font-bold text-base mb-0.5">{item.title}</h3>
                  <p className="text-slate-400 text-xs">{item.desc}</p>
                </button>
              ))}
            </div>

            {/* ── HISTORIAL DE FICHAS / DOCUMENTOS ── */}
            <div className="card-glass border border-slate-200 dark:border-slate-800/80 rounded-2xl shadow-sm dark:shadow-xl overflow-hidden mb-8 page-enter">
              <div className="p-5 border-b border-slate-200 dark:border-slate-800/60 flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-slate-50/80 dark:bg-slate-950/40">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="p-1.5 rounded-lg bg-blue-500/10 border border-blue-500/20 text-blue-600 dark:text-blue-400">
                      <FileText className="w-4 h-4" />
                    </span>
                    <h2 className="text-lg font-bold text-slate-900 dark:text-white tracking-tight">
                      Historial de Fichas Subidas
                    </h2>
                  </div>
                  <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                    Haz clic en el ícono del ojo para abrir la tabla completa con cédula, nombres, edad, estado y visor de cada persona.
                  </p>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={cargarDatos}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-white dark:bg-slate-800 hover:bg-slate-100 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700/60 text-xs font-semibold transition-all cursor-pointer shadow-sm"
                    title="Recargar historial de fichas"
                  >
                    <RefreshCw className="w-3.5 h-3.5 text-primary-500 dark:text-primary-400" />
                    <span>Actualizar</span>
                  </button>
                  <button
                    onClick={() => router.push("/documentos")}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-primary-600 hover:bg-primary-500 text-white text-xs font-bold transition-all cursor-pointer shadow-sm shadow-primary-600/30"
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
                    <div key={i} className="h-12 bg-slate-100 dark:bg-slate-800/40 animate-pulse rounded-xl" />
                  ))}
                </div>
              ) : documentosHistorial.length === 0 ? (
                <div className="text-center py-12 px-4">
                  <FileText className="w-10 h-10 text-slate-400 dark:text-slate-600 mx-auto mb-2" />
                  <p className="text-sm font-semibold text-slate-700 dark:text-slate-300">No hay fichas registradas</p>
                  <p className="text-xs text-slate-500 mt-0.5">Sube tu primer archivo PDF en el módulo de documentos para comenzar.</p>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse">
                    <thead>
                      <tr className="border-b border-slate-200 dark:border-slate-800/80 bg-slate-50 dark:bg-slate-950/50 text-[11px] font-bold text-slate-600 dark:text-slate-400 uppercase tracking-wider">
                        <th className="py-3.5 px-4">Ficha / Documento PDF</th>
                        <th className="py-3.5 px-3 text-center">Fecha de Carga</th>
                        <th className="py-3.5 px-3 text-center">Personas</th>
                        <th className="py-3.5 px-3 text-center">Estado</th>
                        <th className="py-3.5 px-3 text-center">Confianza</th>
                        <th className="py-3.5 px-4 text-right">Acción</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-200 dark:divide-slate-800/30 text-xs">
                      {documentosHistorial.map((doc) => {
                        return (
                          <tr
                            key={doc.id}
                            onClick={() => abrirPersonasFicha(doc)}
                            className="transition-colors cursor-pointer hover:bg-primary-50/50 dark:hover:bg-slate-800/30 text-slate-800 dark:text-slate-200"
                          >
                            <td className="py-3 px-4">
                              <div className="flex items-center gap-2.5 min-w-0">
                                <div className="p-2 rounded-lg shrink-0 bg-blue-50 dark:bg-slate-800 text-blue-600 dark:text-slate-400 border border-blue-200/60 dark:border-transparent">
                                  <FileText className="w-4 h-4" />
                                </div>
                                <div className="min-w-0">
                                  <span className="font-semibold block truncate max-w-[320px] text-slate-900 dark:text-slate-100 hover:text-primary-600 transition-colors" title={doc.nombre_original}>
                                    {doc.nombre_original}
                                  </span>
                                  <span className="text-[10px] text-slate-500 font-mono">
                                    ID: {doc.id.slice(0, 8)}…
                                  </span>
                                </div>
                              </div>
                            </td>
                            <td className="py-3 px-3 text-center text-slate-600 dark:text-slate-400 whitespace-nowrap text-[11px] font-medium">
                              {doc.fecha_carga ? new Date(doc.fecha_carga).toLocaleDateString("es-CO", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" }) : "—"}
                            </td>
                            <td className="py-3 px-3 text-center whitespace-nowrap">
                              <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-purple-100/80 dark:bg-purple-950/30 border border-purple-300 dark:border-purple-800/50 font-mono font-bold text-[11px] text-purple-900 dark:text-purple-300">
                                <Users className="w-3 h-3 text-purple-600 dark:text-purple-400 shrink-0" />
                                <span>{doc.total_personas ?? 0}</span>
                              </span>
                            </td>
                            <td className="py-3 px-3 text-center whitespace-nowrap">
                              {doc.estado === "completado" ? (
                                <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-emerald-100/80 dark:bg-emerald-950/30 border border-emerald-300 dark:border-emerald-800/40 text-emerald-900 dark:text-emerald-400 text-[10px] font-semibold">
                                  <CheckCircle className="w-2.5 h-2.5 text-emerald-600 dark:text-emerald-400" /> Completado
                                </span>
                              ) : doc.estado === "procesando" ? (
                                <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-amber-100/80 dark:bg-amber-950/30 border border-amber-300 dark:border-amber-800/40 text-amber-900 dark:text-amber-400 text-[10px] font-semibold animate-pulse">
                                  <Clock className="w-2.5 h-2.5 text-amber-600 dark:text-amber-400" /> Procesando
                                </span>
                              ) : (
                                <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-rose-100/80 dark:bg-rose-950/30 border border-rose-300 dark:border-rose-800/40 text-rose-900 dark:text-rose-400 text-[10px] font-semibold">
                                  <AlertTriangle className="w-2.5 h-2.5 text-rose-600 dark:text-rose-400" /> {doc.estado}
                                </span>
                              )}
                            </td>
                            <td className="py-3 px-3 text-center font-mono font-bold text-slate-800 dark:text-slate-200">
                              {doc.confianza_ocr != null ? `${Math.round(doc.confianza_ocr)}%` : "—"}
                            </td>
                            <td className="py-3 px-4 text-right whitespace-nowrap">
                              <div className="flex items-center justify-end gap-1.5">
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    abrirPersonasFicha(doc);
                                  }}
                                  className="p-1.5 rounded-xl text-xs font-semibold transition-all inline-flex items-center justify-center cursor-pointer bg-slate-100 dark:bg-slate-800/90 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-800 dark:text-slate-200 border border-slate-300 dark:border-slate-700 shadow-sm hover:border-primary-500/50 active:scale-95"
                                  title="Visualizar personas de este archivo"
                                >
                                  <Eye className="w-4 h-4 text-primary-600 dark:text-primary-400" />
                                </button>
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    setFichaAEliminar(doc);
                                  }}
                                  className="p-1.5 rounded-xl text-rose-600 hover:text-rose-700 dark:text-rose-400 dark:hover:text-rose-300 hover:bg-rose-100 dark:hover:bg-rose-950/50 border border-rose-200/80 dark:border-rose-900/50 transition-all inline-flex items-center justify-center cursor-pointer shadow-sm active:scale-95"
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
          className="fixed inset-0 z-50 bg-slate-950/75 backdrop-blur-md flex items-center justify-center p-3 sm:p-6 animate-in fade-in duration-200"
          onClick={() => setDocSeleccionadoModal(null)}
        >
          <div
            className="bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-800 rounded-3xl shadow-2xl w-full max-w-5xl max-h-[92vh] flex flex-col overflow-hidden animate-in zoom-in-95 duration-200"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div className="p-5 border-b border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950/60 flex items-start justify-between gap-4">
              <div className="min-w-0">
                <div className="flex items-center gap-2 flex-wrap mb-1">
                  <span className="p-2 rounded-xl bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300 border border-blue-300 dark:border-blue-700/60">
                    <FileText className="w-5 h-5" />
                  </span>
                  <div>
                    <span className="text-[10px] uppercase font-black tracking-wider text-primary-700 dark:text-primary-400 bg-primary-50 dark:bg-primary-500/10 px-2 py-0.5 rounded-md border border-primary-300 dark:border-primary-500/20">
                      Tabla Independiente de Ficha
                    </span>
                    <h3 className="text-xl font-bold text-slate-900 dark:text-white truncate max-w-[500px]" title={docSeleccionadoModal.nombre_original}>
                      {docSeleccionadoModal.nombre_original}
                    </h3>
                  </div>
                </div>

                <div className="flex items-center gap-3 text-xs text-slate-600 dark:text-slate-400 flex-wrap mt-2">
                  <span className="bg-slate-100 dark:bg-slate-800/80 px-2.5 py-1 rounded-lg border border-slate-200 dark:border-slate-700 font-mono text-[11px] text-slate-700 dark:text-slate-300 inline-flex items-center gap-1.5 shadow-sm">
                    <Zap className="w-3.5 h-3.5 text-amber-500 shrink-0" />
                    <span>Confianza: {docSeleccionadoModal.confianza_ocr != null ? `${Math.round(docSeleccionadoModal.confianza_ocr)}%` : "—"}</span>
                  </span>
                  <span className="bg-blue-50 dark:bg-blue-950/40 px-2.5 py-1 rounded-lg border border-blue-200 dark:border-blue-800 font-bold text-[11px] text-blue-900 dark:text-blue-300 inline-flex items-center gap-1.5 shadow-sm">
                    <Users className="w-3.5 h-3.5 text-blue-600 dark:text-blue-400 shrink-0" />
                    <span>{personasFicha.length} {personasFicha.length === 1 ? "persona encontrada" : "personas encontradas"}</span>
                  </span>
                  <span className="text-[11px] text-slate-500">
                    Cargado: {docSeleccionadoModal.fecha_carga ? new Date(docSeleccionadoModal.fecha_carga).toLocaleDateString("es-CO", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" }) : "—"}
                  </span>
                </div>
              </div>

              {/* Botones de acción del Modal */}
              <div className="flex items-center gap-2 shrink-0">
                <button
                  onClick={exportarFichaModal}
                  disabled={exportandoModal || personasFicha.length === 0}
                  className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-xs font-bold transition-all cursor-pointer shadow-sm shadow-emerald-600/30 active:scale-95"
                  title="Exportar la lista de personas de esta ficha a Excel"
                >
                  <Download className="w-4 h-4" />
                  <span>{exportandoModal ? "Exportando..." : "Exportar Ficha"}</span>
                </button>
                <button
                  onClick={() => setFichaAEliminar(docSeleccionadoModal)}
                  className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-rose-50 hover:bg-rose-600 text-rose-700 dark:text-rose-300 hover:text-white dark:bg-rose-950/40 dark:hover:bg-rose-600 border border-rose-200 dark:border-rose-900/60 text-xs font-bold transition-all cursor-pointer shadow-sm active:scale-95"
                  title="Eliminar esta ficha del historial"
                >
                  <Trash2 className="w-4 h-4" />
                  <span>Eliminar Ficha</span>
                </button>
                <button
                  onClick={() => setDocSeleccionadoModal(null)}
                  className="p-2 rounded-xl text-slate-500 hover:text-slate-900 dark:hover:text-white bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors cursor-pointer shrink-0"
                  title="Cerrar ventana"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>

            {/* Aviso explicativo y buscador local */}
            <div className="px-5 py-2.5 bg-blue-50/80 dark:bg-blue-950/30 border-b border-blue-200 dark:border-blue-900/40 text-blue-950 dark:text-blue-200 text-xs flex items-center justify-between gap-3 flex-wrap">
              <span className="flex items-center gap-1.5 font-medium">
                <CheckCircle className="w-4 h-4 text-blue-600 dark:text-blue-400 shrink-0" />
                Esta tabla muestra única y exclusivamente las personas pertenecientes a este archivo sin alterar ni mezclar la tabla general de personas.
              </span>
              <div className="relative min-w-[240px]">
                <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none" />
                <input
                  type="text"
                  placeholder="Buscar por cédula o nombre..."
                  value={busquedaModal}
                  onChange={(e) => setBusquedaModal(e.target.value)}
                  className="w-full pl-8 pr-3 py-1 text-xs bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white focus:outline-none focus:border-primary-500"
                />
              </div>
            </div>

            {/* Modal Body: Tabla de Personas */}
            <div className="overflow-y-auto flex-1 p-5 min-h-[250px] max-h-[60vh]">
              {cargandoPersonasFicha ? (
                <div className="space-y-3 py-6">
                  {Array(4).fill(0).map((_, i) => (
                    <div key={i} className="h-12 bg-slate-100 dark:bg-slate-800/40 animate-pulse rounded-xl" />
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
                  <Users className="w-10 h-10 text-slate-400 mx-auto mb-2" />
                  <p className="text-sm font-semibold text-slate-800 dark:text-slate-200">
                    {busquedaModal ? `Sin resultados para "${busquedaModal}"` : "No se registraron personas para esta ficha"}
                  </p>
                  <p className="text-xs text-slate-500 mt-0.5">
                    El documento puede estar en procesamiento o no contener cédulas legibles.
                  </p>
                </div>
              ) : (
                <div className="overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-800">
                  <table className="w-full text-left border-collapse">
                    <thead>
                      <tr className="border-b border-slate-200 dark:border-slate-800 bg-slate-100 dark:bg-slate-950/60 text-[11px] font-bold text-slate-700 dark:text-slate-400 uppercase tracking-wider">
                        <th className="py-3 px-3 w-10 text-center">#</th>
                        <th className="py-3 px-3 whitespace-nowrap">Documento / Cédula</th>
                        <th className="py-3 px-3 whitespace-nowrap">Nombre Completo</th>
                        <th className="py-3 px-3 text-center whitespace-nowrap">Edad</th>
                        <th className="py-3 px-3 text-center whitespace-nowrap">Página</th>
                        <th className="py-3 px-3 text-center whitespace-nowrap">Estado OCR</th>
                        <th className="py-3 px-3 text-right whitespace-nowrap">Detalles</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-200 dark:divide-slate-800/40 text-xs">
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
                                className={`transition-colors cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/30 ${
                                  isExpanded ? "bg-blue-50/70 dark:bg-slate-800/40" : ""
                                }`}
                              >
                                <td className="py-3 px-3 text-center text-slate-500 font-mono text-[11px]">
                                  {idx + 1}
                                </td>
                                <td className="py-3 px-3 whitespace-nowrap">
                                  <div className="flex items-center gap-1.5 flex-nowrap">
                                    <span className={`px-1.5 py-0.5 rounded text-[10px] border font-mono tracking-wider shrink-0 ${tipoInfo.badge}`}>
                                      {tipoInfo.codigo}
                                    </span>
                                    <span className="font-mono text-blue-900 dark:text-primary-300 font-black text-sm tracking-wide">
                                      {p.numero_identificacion}
                                    </span>
                                  </div>
                                </td>
                                <td className="py-3 px-3 whitespace-nowrap">
                                  <span className="font-semibold text-slate-900 dark:text-slate-100 text-sm">
                                    {nombre || "Sin nombre extraído"}
                                  </span>
                                </td>
                                <td className="py-3 px-3 text-center whitespace-nowrap">
                                  {edad !== null ? (
                                    esMenor14 ? (
                                      <span className="text-[10px] font-mono px-2 py-0.5 rounded-md bg-rose-50 dark:bg-rose-950/50 border border-rose-300 dark:border-rose-800/60 text-rose-800 dark:text-rose-300 font-bold whitespace-nowrap shadow-sm">
                                        {edad} años (MENOR)
                                      </span>
                                    ) : (
                                      <span className="text-[11px] font-mono px-2 py-0.5 rounded-md bg-amber-500/10 dark:bg-amber-500/15 border border-amber-500/25 dark:border-amber-400/25 text-amber-800 dark:text-amber-300 font-medium whitespace-nowrap shadow-sm">
                                        {edad} años
                                      </span>
                                    )
                                  ) : (
                                    <span className="text-slate-400 text-xs">—</span>
                                  )}
                                </td>
                                <td className="py-3 px-3 text-center font-mono font-bold text-slate-700 dark:text-slate-300">
                                  {p.pagina_frente ? `${p.pagina_frente}${p.pagina_reverso ? `/${p.pagina_reverso}` : ""}` : (p.pagina_numero || "1")}
                                </td>
                                <td className="py-3 px-3 text-center whitespace-nowrap">
                                  {p.requiere_revision || (p.estado_registro && p.estado_registro !== "VALID") || Boolean((p.detalles_campos as any)?.discrepancia_documento_edad) ? (
                                    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-amber-50 dark:bg-amber-950/40 border border-amber-300 dark:border-amber-800/50 text-amber-800 dark:text-amber-300 text-[10px] font-medium shadow-sm" title={(p.detalles_campos as any)?.discrepancia_documento_edad?.motivo || "Requiere verificación de datos OCR"}>
                                      <AlertTriangle className="w-2.5 h-2.5 text-amber-600 dark:text-amber-400" /> REVISAR
                                    </span>
                                  ) : (
                                    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-300 dark:border-emerald-800/50 text-emerald-800 dark:text-emerald-300 text-[10px] font-medium shadow-sm">
                                      <CheckCircle className="w-2.5 h-2.5 text-emerald-600 dark:text-emerald-400" /> VÁLIDO
                                    </span>
                                  )}
                                </td>
                                <td className="py-3 px-3 text-right whitespace-nowrap">
                                  <button
                                    type="button"
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      setPersonaDetalleId(isExpanded ? null : p.id);
                                    }}
                                    className="px-2.5 py-1 rounded-lg text-xs font-semibold bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 border border-slate-300 dark:border-slate-700 transition-colors inline-flex items-center gap-1 cursor-pointer"
                                  >
                                    <span>{isExpanded ? "Ocultar" : "Detalles"}</span>
                                    {isExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                                  </button>
                                </td>
                              </tr>

                              {/* Fila desplegable de detalles completos de la persona */}
                              {isExpanded && (
                                <tr className="bg-slate-50/90 dark:bg-slate-950/70 border-b border-slate-200 dark:border-slate-800">
                                  <td colSpan={7} className="p-4">
                                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 bg-white dark:bg-slate-900 p-4 rounded-xl border border-slate-200 dark:border-slate-800">
                                      <div>
                                        <p className="text-[10px] uppercase font-bold text-slate-500">Fecha de Nacimiento</p>
                                        <p className="font-mono text-xs font-bold text-slate-900 dark:text-slate-100 mt-0.5">
                                          {p.fecha_nacimiento || "No extraída"}
                                        </p>
                                      </div>
                                      <div>
                                        <p className="text-[10px] uppercase font-bold text-slate-500">Fecha de Expedición</p>
                                        <p className="font-mono text-xs font-bold text-slate-900 dark:text-slate-100 mt-0.5">
                                          {p.fecha_expedicion || "No extraída"}
                                        </p>
                                      </div>
                                      <div>
                                        <p className="text-[10px] uppercase font-bold text-slate-500">Lugar de Expedición</p>
                                        <p className="text-xs font-bold text-slate-900 dark:text-slate-100 mt-0.5">
                                          {p.lugar_expedicion || "No extraído"}
                                        </p>
                                      </div>
                                      <div>
                                        <p className="text-[10px] uppercase font-bold text-slate-500">Género / Sexo</p>
                                        <p className="text-xs font-bold text-slate-900 dark:text-slate-100 mt-0.5">
                                          {p.sexo || (p.detalles_campos as any)?.genero || "No extraído"}
                                        </p>
                                      </div>

                                      {/* Nombre desglosado */}
                                      <div className="sm:col-span-2 lg:col-span-4 pt-2 border-t border-slate-100 dark:border-slate-800 flex items-center gap-4 flex-wrap text-xs">
                                        <span className="text-slate-500 text-[11px]">
                                          <strong className="text-slate-700 dark:text-slate-300">Apellidos:</strong> {p.apellidos || (p.detalles_campos as any)?.primer_apellido || "—"}
                                        </span>
                                        <span className="text-slate-500 text-[11px]">
                                          <strong className="text-slate-700 dark:text-slate-300">Nombres:</strong> {p.nombres || (p.detalles_campos as any)?.primer_nombre || "—"}
                                        </span>
                                        {(p.requiere_revision || Boolean((p.detalles_campos as any)?.discrepancia_documento_edad)) && (
                                          <span className="text-amber-800 dark:text-amber-300 text-[11px] bg-amber-50 dark:bg-amber-950/40 px-2 py-0.5 rounded border border-amber-300 dark:border-amber-700 font-medium inline-flex items-center gap-1.5">
                                            <AlertTriangle className="w-3.5 h-3.5 text-amber-600 dark:text-amber-400 shrink-0" />
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
            <div className="p-4 border-t border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950/60 flex items-center justify-between gap-3 flex-wrap">
              <div className="text-xs text-slate-600 dark:text-slate-400">
                Mostrando <strong className="text-slate-900 dark:text-white">
                  {personasFicha.filter((p) => {
                    if (!busquedaModal) return true;
                    const q = busquedaModal.toLowerCase().trim().replace(/[.\s]/g, "");
                    const cedula = String(p.numero_identificacion || "").replace(/[.\s]/g, "");
                    const nom = formatNombreCompleto(p).toLowerCase();
                    return cedula.includes(q) || nom.includes(q);
                  }).length}
                </strong> de <strong className="text-slate-900 dark:text-white">{personasFicha.length}</strong> personas de esta ficha
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
                  className="px-3.5 py-2 rounded-xl bg-primary-600 hover:bg-primary-500 text-white text-xs font-bold transition-all cursor-pointer shadow-sm flex items-center gap-1.5"
                >
                  <Users className="w-3.5 h-3.5" />
                  <span>Ver en Módulo Personas</span>
                </button>
                <button
                  onClick={() => setDocSeleccionadoModal(null)}
                  className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-white dark:bg-slate-700 dark:hover:bg-slate-600 text-xs font-bold transition-all cursor-pointer shadow-sm"
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
          className="fixed inset-0 z-[60] bg-slate-950/80 backdrop-blur-md flex items-center justify-center p-4 animate-in fade-in duration-200"
          onClick={() => !eliminandoFicha && setFichaAEliminar(null)}
        >
          <div
            className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-3xl p-6 max-w-md w-full shadow-2xl animate-in zoom-in-95 duration-200"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center gap-3 mb-4">
              <div className="p-3 rounded-2xl bg-rose-100 dark:bg-rose-500/20 text-rose-600 dark:text-rose-400 border border-rose-200 dark:border-rose-500/30 shrink-0">
                <Trash2 className="w-6 h-6" />
              </div>
              <div>
                <h3 className="text-lg font-bold text-slate-900 dark:text-white">
                  ¿Eliminar ficha del historial?
                </h3>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  Esta acción no se puede deshacer
                </p>
              </div>
            </div>

            <p className="text-xs text-slate-600 dark:text-slate-300 mb-2">
              Estás a punto de eliminar del historial el siguiente documento:
            </p>
            <div className="p-3 rounded-xl bg-slate-100 dark:bg-slate-950/70 border border-slate-200 dark:border-slate-800 text-xs font-mono text-slate-900 dark:text-slate-100 mb-4 break-all">
              <div className="font-bold flex items-center gap-2">
                <FileText className="w-4 h-4 text-primary-500 shrink-0" />
                <span className="truncate">{fichaAEliminar.nombre_original}</span>
              </div>
              <div className="text-[11px] text-slate-500 mt-1.5 flex items-center gap-3">
                <span>👥 {fichaAEliminar.total_personas ?? 0} personas asociadas</span>
              </div>
            </div>

            <p className="text-xs text-rose-700 dark:text-rose-300 font-medium mb-5 bg-rose-50 dark:bg-rose-950/30 p-3 rounded-xl border border-rose-200 dark:border-rose-900/40">
              ⚠️ Se eliminará el registro del historial, el archivo físico del PDF y todas las personas asociadas a esta ficha de forma permanente.
            </p>

            <div className="flex items-center justify-end gap-2.5">
              <button
                onClick={() => setFichaAEliminar(null)}
                disabled={eliminandoFicha}
                className="px-4 py-2 rounded-xl text-xs font-bold text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 border border-slate-200 dark:border-slate-700 transition-colors cursor-pointer disabled:opacity-50"
              >
                Cancelar
              </button>
              <button
                onClick={confirmarEliminarFicha}
                disabled={eliminandoFicha}
                className="px-4 py-2 rounded-xl text-xs font-bold text-white bg-rose-600 hover:bg-rose-500 transition-all cursor-pointer shadow-sm shadow-rose-600/30 flex items-center gap-2 disabled:opacity-50 active:scale-95"
              >
                {eliminandoFicha ? (
                  <>
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                    <span>Eliminando...</span>
                  </>
                ) : (
                  <>
                    <Trash2 className="w-3.5 h-3.5" />
                    <span>Sí, eliminar ficha</span>
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
