"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  FileText, Users, GitCompare, AlertTriangle,
  CheckCircle, Clock, TrendingUp, Activity,
  RefreshCw, ChevronRight, ExternalLink, ArrowUpRight
} from "lucide-react";
import Sidebar from "@/components/ui/Sidebar";
import { apiDocumentos, apiPersonas } from "@/lib/api";
import { auth } from "@/lib/auth";
import { formatNombreCompleto, calcularEdad } from "@/lib/formatters";
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
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [cargando, setCargando] = useState(true);

  // Historial de Fichas
  const [documentosHistorial, setDocumentosHistorial] = useState<Documento[]>([]);
  const [cargandoDocs, setCargandoDocs] = useState(true);

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
    <div className="flex min-h-screen bg-[#0b0f19] text-slate-100 font-sans w-full max-w-full overflow-x-hidden">
      <Sidebar />

      <main className="ml-64 flex-1 p-6 lg:p-8 min-w-0 max-w-[calc(100vw-16rem)] overflow-x-hidden">
        {/* Header */}
        <div className="mb-8 page-enter">
          <div className="flex items-center gap-2 mb-1">
            <Activity className="w-5 h-5 text-primary-400" />
            <span className="text-primary-400 text-sm font-medium">Panel de Control</span>
          </div>
          <h1 className="text-3xl font-extrabold text-white tracking-tight">Dashboard</h1>
          <p className="text-slate-400 mt-1 text-sm">
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
                    Haz clic en &quot;Visualizar Personas&quot; para abrir la tabla completa con cédula, nombres, edad, estado y visor de cada persona.
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
                        <th className="py-3.5 px-3 text-center">Páginas</th>
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
                            onClick={() => router.push(`/personas?documento_id=${doc.id}`)}
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
                            <td className="py-3 px-3 text-center font-mono font-bold text-slate-800 dark:text-slate-200">
                              {doc.total_paginas || 1}
                            </td>
                            <td className="py-3 px-3 text-center whitespace-nowrap">
                              {doc.estado === "completado" ? (
                                <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-emerald-50 dark:bg-emerald-500/15 border border-emerald-300 dark:border-emerald-500/30 text-emerald-800 dark:text-emerald-400 text-[10px] font-bold">
                                  <CheckCircle className="w-2.5 h-2.5" /> Completado
                                </span>
                              ) : doc.estado === "procesando" ? (
                                <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-amber-50 dark:bg-yellow-500/15 border border-amber-300 dark:border-yellow-500/30 text-amber-800 dark:text-yellow-400 text-[10px] font-bold animate-pulse">
                                  <Clock className="w-2.5 h-2.5" /> Procesando
                                </span>
                              ) : (
                                <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-rose-50 dark:bg-red-500/15 border border-rose-300 dark:border-red-500/30 text-rose-800 dark:text-red-400 text-[10px] font-bold">
                                  <AlertTriangle className="w-2.5 h-2.5" /> {doc.estado}
                                </span>
                              )}
                            </td>
                            <td className="py-3 px-3 text-center font-mono font-bold text-slate-800 dark:text-slate-200">
                              {doc.confianza_ocr != null ? `${Math.round(doc.confianza_ocr)}%` : "—"}
                            </td>
                            <td className="py-3 px-4 text-right whitespace-nowrap">
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  router.push(`/personas?documento_id=${doc.id}`);
                                }}
                                className="px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all inline-flex items-center gap-1.5 cursor-pointer bg-primary-600 hover:bg-primary-500 text-white shadow-sm shadow-primary-600/30 hover:scale-[1.02] active:scale-98"
                                title="Visualizar personas de este archivo en el módulo de Personas"
                              >
                                <span>Visualizar Personas</span>
                                <ArrowUpRight className="w-3.5 h-3.5" />
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
          </>
        ) : (
          <div className="card text-center py-12">
            <p className="text-slate-400">Error cargando estadísticas</p>
          </div>
        )}
      </main>
    </div>
  );
}
