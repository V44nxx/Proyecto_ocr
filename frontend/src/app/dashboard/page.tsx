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

  // Historial de Fichas y Personas
  const [documentosHistorial, setDocumentosHistorial] = useState<Documento[]>([]);
  const [cargandoDocs, setCargandoDocs] = useState(true);
  const [docSeleccionado, setDocSeleccionado] = useState<Documento | null>(null);
  const [personasDoc, setPersonasDoc] = useState<Persona[]>([]);
  const [cargandoPersonasDoc, setCargandoPersonasDoc] = useState(false);

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

      // Si no hay documento seleccionado pero hay documentos en el historial, seleccionar el primero por defecto
      if (!docSeleccionado && docs.length > 0) {
        seleccionarDocumento(docs[0]);
      }
    } catch (err) {
      console.error("Error cargando datos del dashboard:", err);
    } finally {
      setCargando(false);
      setCargandoDocs(false);
    }
  };

  const seleccionarDocumento = async (doc: Documento) => {
    setDocSeleccionado(doc);
    setCargandoPersonasDoc(true);
    try {
      const res = await apiPersonas.listar({ documento_id: doc.id, limit: 150 });
      const items = Array.isArray(res.data) ? res.data : (((res.data as any)?.items) || []);
      setPersonasDoc(items);
    } catch (err) {
      console.error("Error cargando personas de la ficha:", err);
      setPersonasDoc([]);
    } finally {
      setCargandoPersonasDoc(false);
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
            <div className="bg-slate-900/80 border border-slate-800/80 rounded-2xl shadow-xl overflow-hidden backdrop-blur-md mb-8 page-enter">
              <div className="p-5 border-b border-slate-800/60 flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-slate-950/40">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="p-1.5 rounded-lg bg-blue-500/10 border border-blue-500/20 text-blue-400">
                      <FileText className="w-4 h-4" />
                    </span>
                    <h2 className="text-lg font-bold text-white tracking-tight">
                      Historial de Fichas Subidas
                    </h2>
                  </div>
                  <p className="text-xs text-slate-400 mt-1">
                    Selecciona cualquier ficha para desplegar la tabla de personas que pertenecen exclusivamente a ese documento.
                  </p>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={cargarDatos}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700/60 text-xs font-semibold transition-all cursor-pointer"
                    title="Recargar historial de fichas"
                  >
                    <RefreshCw className="w-3.5 h-3.5 text-primary-400" />
                    <span>Actualizar</span>
                  </button>
                  <button
                    onClick={() => router.push("/documentos")}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-primary-600/20 hover:bg-primary-600/30 text-primary-300 border border-primary-500/40 text-xs font-bold transition-all cursor-pointer"
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
                    <div key={i} className="h-12 bg-slate-800/40 animate-pulse rounded-xl" />
                  ))}
                </div>
              ) : documentosHistorial.length === 0 ? (
                <div className="text-center py-12 px-4">
                  <FileText className="w-10 h-10 text-slate-600 mx-auto mb-2" />
                  <p className="text-sm font-semibold text-slate-300">No hay fichas registradas</p>
                  <p className="text-xs text-slate-500 mt-0.5">Sube tu primer archivo PDF en el módulo de documentos para comenzar.</p>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse">
                    <thead>
                      <tr className="border-b border-slate-800/80 bg-slate-950/50 text-[11px] font-bold text-slate-400 uppercase tracking-wider">
                        <th className="py-3 px-4">Ficha / Documento PDF</th>
                        <th className="py-3 px-3 text-center">Fecha de Carga</th>
                        <th className="py-3 px-3 text-center">Páginas</th>
                        <th className="py-3 px-3 text-center">Estado</th>
                        <th className="py-3 px-3 text-center">Confianza</th>
                        <th className="py-3 px-4 text-right">Personas de esta Ficha</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/30 text-xs">
                      {documentosHistorial.map((doc) => {
                        const isSelected = docSeleccionado?.id === doc.id;
                        return (
                          <tr
                            key={doc.id}
                            onClick={() => seleccionarDocumento(doc)}
                            className={`transition-colors cursor-pointer ${
                              isSelected
                                ? "bg-primary-500/15 border-l-4 border-l-primary-500 text-white font-medium"
                                : "hover:bg-slate-800/30 text-slate-200"
                            }`}
                          >
                            <td className="py-3 px-4">
                              <div className="flex items-center gap-2.5 min-w-0">
                                <div className={`p-2 rounded-lg shrink-0 ${isSelected ? "bg-primary-500/20 text-primary-300" : "bg-slate-800 text-slate-400"}`}>
                                  <FileText className="w-4 h-4" />
                                </div>
                                <div className="min-w-0">
                                  <span className="font-semibold block truncate max-w-[280px]" title={doc.nombre_original}>
                                    {doc.nombre_original}
                                  </span>
                                  <span className="text-[10px] text-slate-500 font-mono">
                                    ID: {doc.id.slice(0, 8)}…
                                  </span>
                                </div>
                              </div>
                            </td>
                            <td className="py-3 px-3 text-center text-slate-400 whitespace-nowrap text-[11px]">
                              {doc.fecha_carga ? new Date(doc.fecha_carga).toLocaleDateString("es-CO", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" }) : "—"}
                            </td>
                            <td className="py-3 px-3 text-center font-mono">
                              {doc.total_paginas || 1}
                            </td>
                            <td className="py-3 px-3 text-center whitespace-nowrap">
                              {doc.estado === "completado" ? (
                                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-500/15 border border-emerald-500/30 text-emerald-400 text-[10px] font-bold">
                                  <CheckCircle className="w-2.5 h-2.5" /> Completado
                                </span>
                              ) : doc.estado === "procesando" ? (
                                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-yellow-500/15 border border-yellow-500/30 text-yellow-400 text-[10px] font-bold animate-pulse">
                                  <Clock className="w-2.5 h-2.5" /> Procesando
                                </span>
                              ) : (
                                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-red-500/15 border border-red-500/30 text-red-400 text-[10px] font-bold">
                                  <AlertTriangle className="w-2.5 h-2.5" /> {doc.estado}
                                </span>
                              )}
                            </td>
                            <td className="py-3 px-3 text-center font-mono text-slate-300">
                              {doc.confianza_ocr != null ? `${Math.round(doc.confianza_ocr)}%` : "—"}
                            </td>
                            <td className="py-3 px-4 text-right whitespace-nowrap">
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  seleccionarDocumento(doc);
                                }}
                                className={`px-2.5 py-1.5 rounded-lg text-xs font-semibold transition-all inline-flex items-center gap-1 cursor-pointer ${
                                  isSelected
                                    ? "bg-primary-600 text-white shadow-md shadow-primary-500/20"
                                    : "bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700/60"
                                }`}
                              >
                                <span>{isSelected ? "Visualizando" : "Ver Personas"}</span>
                                <ChevronRight className="w-3.5 h-3.5" />
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

            {/* ── TABLA DE PERSONAS DEL DOCUMENTO SELECCIONADO ── */}
            {docSeleccionado && (
              <div id="personas-ficha" className="bg-slate-900/90 border-2 border-primary-500/40 rounded-2xl shadow-2xl overflow-hidden backdrop-blur-md mb-8 page-enter">
                <div className="p-5 border-b border-slate-800/60 flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-gradient-to-r from-primary-950/60 via-slate-900 to-primary-950/60">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="p-1.5 rounded-lg bg-primary-500/20 text-primary-300 border border-primary-500/30">
                        <Users className="w-4 h-4" />
                      </span>
                      <h3 className="text-base font-extrabold text-white">
                        Personas de la Ficha: <span className="text-primary-300 font-mono">{docSeleccionado.nombre_original}</span>
                      </h3>
                    </div>
                    <p className="text-xs text-slate-400 mt-1">
                      Tabla de personas que pertenecen unicamente a este documento seleccionado.
                    </p>
                  </div>

                  <div className="flex items-center gap-2">
                    <span className="px-3 py-1.5 rounded-xl bg-primary-500/15 border border-primary-500/30 text-xs font-bold text-primary-300">
                      Total en ficha: <strong className="text-white ml-1">{personasDoc.length}</strong> {personasDoc.length === 1 ? "persona" : "personas"}
                    </span>
                    <button
                      onClick={() => router.push(`/personas?documento_id=${docSeleccionado.id}`)}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-emerald-500/15 hover:bg-emerald-500/25 border border-emerald-500/30 text-emerald-300 text-xs font-bold transition-all shadow-sm cursor-pointer"
                      title="Abrir este documento con visor de páginas en el módulo de personas"
                    >
                      <span>Abrir en Módulo Personas</span>
                      <ExternalLink className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>

                {cargandoPersonasDoc ? (
                  <div className="p-8 text-center">
                    <div className="w-7 h-7 border-2 border-primary-500 border-t-transparent rounded-full animate-spin mx-auto mb-2" />
                    <p className="text-xs text-slate-400">Cargando personas de la ficha…</p>
                  </div>
                ) : personasDoc.length === 0 ? (
                  <div className="text-center py-12 px-4">
                    <Users className="w-8 h-8 text-slate-600 mx-auto mb-2" />
                    <p className="text-sm font-semibold text-slate-300">No hay personas registradas en esta ficha</p>
                    <p className="text-xs text-slate-500 mt-0.5">El documento aún no ha terminado de procesar o no se detectaron cédulas en sus páginas.</p>
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-left border-collapse">
                      <thead>
                        <tr className="border-b border-slate-800/80 bg-slate-950/60 text-[11px] font-bold text-slate-400 uppercase tracking-wider">
                          <th className="py-3 px-4">Documento / ID</th>
                          <th className="py-3 px-4">Nombre Completo</th>
                          <th className="py-3 px-3 text-center">Fecha Nacimiento</th>
                          <th className="py-3 px-3 text-center">Edad</th>
                          <th className="py-3 px-3 text-center">Página</th>
                          <th className="py-3 px-4 text-center">Estado y Alertas</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800/30 text-xs">
                        {personasDoc.map((p) => {
                          const nom = formatNombreCompleto(p);
                          const edad = p.edad ?? calcularEdad(p.fecha_nacimiento);
                          const esMenor14 = edad !== null && edad < 14;

                          return (
                            <tr key={p.id} className="hover:bg-slate-800/30 transition-colors">
                              <td className="py-3 px-4 font-mono font-bold text-primary-300 whitespace-nowrap">
                                {p.numero_identificacion}
                              </td>
                              <td className="py-3 px-4 font-semibold text-slate-100 whitespace-nowrap">
                                {nom || <span className="text-slate-500 italic">Sin nombre</span>}
                              </td>
                              <td className="py-3 px-3 text-center font-mono text-slate-300 whitespace-nowrap">
                                {p.fecha_nacimiento ? String(p.fecha_nacimiento) : "—"}
                              </td>
                              <td className="py-3 px-3 text-center whitespace-nowrap">
                                {edad !== null ? (
                                  esMenor14 ? (
                                    <span className="inline-block text-[11px] font-mono px-2 py-0.5 rounded-full bg-rose-500/20 border border-rose-500/50 text-rose-300 font-black shadow-sm shadow-rose-500/20 animate-pulse" title={`Alerta: Menor de 14 años (${edad} años cumplidos)`}>
                                      {edad} años
                                    </span>
                                  ) : (
                                    <span className="inline-block text-[11px] font-mono px-2 py-0.5 rounded-full bg-amber-500/15 border border-amber-500/30 text-amber-300 font-bold">
                                      {edad} años
                                    </span>
                                  )
                                ) : (
                                  <span className="text-slate-600 text-xs">—</span>
                                )}
                              </td>
                              <td className="py-3 px-3 text-center font-mono text-slate-400 whitespace-nowrap">
                                {p.pagina_frente ? `Pág. ${p.pagina_frente}` : (p.pagina_numero || "—")}
                              </td>
                              <td className="py-3 px-4 text-center whitespace-nowrap">
                                <div className="inline-flex items-center justify-center gap-1.5 flex-wrap">
                                  {/* Alerta roja para menores de 14 años */}
                                  {esMenor14 && (
                                    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-rose-500/25 border border-rose-500/50 text-rose-300 text-[10px] font-black shadow-sm shadow-rose-500/20 animate-pulse">
                                      <AlertTriangle className="w-2.5 h-2.5 text-rose-400" /> MENOR (&lt; 14)
                                    </span>
                                  )}
                                  {p.requiere_revision || (p.estado_registro && p.estado_registro !== "VALID") ? (
                                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-amber-500/15 border border-amber-500/30 text-amber-300 text-[10px] font-bold">
                                      <AlertTriangle className="w-2.5 h-2.5" /> REVISAR
                                    </span>
                                  ) : (
                                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-500/15 border border-emerald-500/30 text-emerald-400 text-[10px] font-bold">
                                      <CheckCircle className="w-2.5 h-2.5" /> VÁLIDO
                                    </span>
                                  )}
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
            )}
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
