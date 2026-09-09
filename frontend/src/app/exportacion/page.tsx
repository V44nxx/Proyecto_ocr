"use client";

import { useState, useEffect, useMemo } from "react";
import { useRouter } from "next/navigation";
import toast from "react-hot-toast";
import {
  Download, FileSpreadsheet, Users, Filter,
  CheckCircle, AlertTriangle, RefreshCw, FileText, CheckSquare, Square,
} from "lucide-react";
import Sidebar from "@/components/ui/Sidebar";
import { apiExportacion, apiPersonas, apiDocumentos } from "@/lib/api";
import { auth } from "@/lib/auth";
import { formatNombreCompleto } from "@/lib/formatters";
import type { Persona, Documento } from "@/types";

export default function ExportacionPage() {
  const router = useRouter();
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [documentos, setDocumentos] = useState<Documento[]>([]);
  const [documentoSeleccionado, setDocumentoSeleccionado] = useState<string>("todos");
  const [cargando, setCargando] = useState(true);
  const [exportando, setExportando] = useState(false);
  const [filtroRevision, setFiltroRevision] = useState<"todos" | "revision" | "ok">("todos");
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

  // Filtrar personas según documento y estado de revisión
  const personasFiltradas = useMemo(() => {
    return personas.filter((p) => {
      // Filtro por documento
      if (documentoSeleccionado !== "todos" && p.documento_id !== documentoSeleccionado) {
        return false;
      }
      // Filtro por revisión
      const esRev = p.requiere_revision || (p.estado_registro && p.estado_registro !== "VALID");
      if (filtroRevision === "revision" && !esRev) return false;
      if (filtroRevision === "ok" && esRev) return false;

      return true;
    });
  }, [personas, documentoSeleccionado, filtroRevision]);

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

      const docId = documentoSeleccionado !== "todos" ? documentoSeleccionado : undefined;

      // Si se seleccionó un subconjunto específico de personas visibles, o personas de un PDF
      const todosFueronSeleccionados = personasFiltradas.length > 0 &&
        personasFiltradas.length === seleccionados.size &&
        personasFiltradas.every((p) => seleccionados.has(p.id));

      await apiExportacion.descargarXlsx({
        requiereRevision,
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
    ok: personas.filter((p) => !p.requiere_revision && (!p.estado_registro || p.estado_registro === "VALID")).length,
    revision: personas.filter((p) => p.requiere_revision || (p.estado_registro && p.estado_registro !== "VALID")).length,
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
    <div className="flex min-h-screen bg-[#0b0f19] text-slate-100 font-sans">
      <Sidebar />
      <main className="ml-64 flex-1 p-8 overflow-x-hidden">
        {/* Header */}
        <div className="mb-8 page-enter">
          <div className="flex items-center gap-2 mb-1">
            <span className="p-1.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
              <Download className="w-4 h-4" />
            </span>
            <span className="text-emerald-400 text-xs font-semibold uppercase tracking-wider">Exportación</span>
          </div>
          <h1 className="text-3xl font-extrabold text-white tracking-tight">Exportación a Excel</h1>
          <p className="text-slate-400 mt-1 text-sm">
            Filtra por documento PDF, selecciona personas específicas y genera reportes .xlsx profesionales
          </p>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8 page-enter">
          {[
            { label: "Total Personas", value: stats.total, color: "text-blue-400", border: "border-blue-500/20" },
            { label: "Validadas OK", value: stats.ok, color: "text-emerald-400", border: "border-emerald-500/20" },
            { label: "En Revisión", value: stats.revision, color: "text-amber-400", border: "border-amber-500/20" },
            { label: "Fichas Completas", value: stats.completas, color: "text-purple-400", border: "border-purple-500/20" },
          ].map((s) => (
            <div key={s.label} className={`card text-center bg-slate-900/80 border ${s.border} backdrop-blur-md`}>
              <p className={`text-3xl font-black ${s.color}`}>{s.value}</p>
              <p className="text-slate-400 text-xs mt-1 font-medium">{s.label}</p>
            </div>
          ))}
        </div>

        {/* Panel principal */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 page-enter">
          {/* Columna Izquierda: Configuración de Exportación */}
          <div className="lg:col-span-5 space-y-6">
            <div className="card bg-slate-900/80 border border-slate-800/80 backdrop-blur-md">
              <h2 className="text-lg font-bold text-white mb-5 flex items-center gap-2">
                <FileSpreadsheet className="w-5 h-5 text-emerald-400" />
                Configurar Exportación
              </h2>

              {/* Selector de Documento PDF */}
              <div className="mb-6">
                <label className="block text-xs font-bold text-slate-300 uppercase tracking-wider mb-2 flex items-center gap-2">
                  <FileText className="w-4 h-4 text-primary-400" />
                  Documento PDF de Origen
                </label>
                <div className="relative">
                  <select
                    value={documentoSeleccionado}
                    onChange={(e) => setDocumentoSeleccionado(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-700/80 rounded-xl px-3.5 py-2.5 text-sm text-white focus:outline-none focus:border-primary-500/70 transition-colors shadow-inner font-medium"
                  >
                    <option value="todos">
                      📄 Todos los documentos PDF ({personas.length} personas)
                    </option>
                    {documentos.map((doc) => {
                      const count = personasPorDoc[doc.id] || 0;
                      return (
                        <option key={doc.id} value={doc.id}>
                          📄 {doc.nombre_original} ({count} personas)
                        </option>
                      );
                    })}
                  </select>
                </div>
                {documentoSeleccionado !== "todos" && docActual && (
                  <div className="mt-2.5 p-2.5 rounded-xl bg-primary-500/10 border border-primary-500/20 text-xs text-primary-300 flex items-center justify-between">
                    <span className="truncate max-w-[240px] font-mono text-[11px]">
                      {docActual.nombre_original}
                    </span>
                    <span className="font-bold text-primary-200">
                      {personasPorDoc[docActual.id] || 0} personas
                    </span>
                  </div>
                )}
              </div>

              {/* Filtro por Estado de Revisión */}
              <div className="mb-6">
                <label className="block text-xs font-bold text-slate-300 uppercase tracking-wider mb-2 flex items-center gap-2">
                  <Filter className="w-4 h-4 text-slate-400" />
                  Filtrar por Estado
                </label>
                <div className="space-y-2">
                  {[
                    {
                      value: "todos",
                      label: "Todos los registros",
                      icon: <Users className="w-4 h-4 text-blue-400" />,
                      count: personas.length,
                    },
                    {
                      value: "ok",
                      label: "Solo validados OK",
                      icon: <CheckCircle className="w-4 h-4 text-emerald-400" />,
                      count: stats.ok,
                    },
                    {
                      value: "revision",
                      label: "Solo en revisión",
                      icon: <AlertTriangle className="w-4 h-4 text-amber-400" />,
                      count: stats.revision,
                    },
                  ].map((opt) => (
                    <label
                      key={opt.value}
                      className={`flex items-center justify-between p-3 rounded-xl border cursor-pointer transition-all ${
                        filtroRevision === opt.value
                          ? "border-primary-500/60 bg-primary-500/10 ring-1 ring-primary-500/30"
                          : "border-slate-800/80 hover:border-slate-700 bg-slate-950/60"
                      }`}
                    >
                      <div className="flex items-center gap-3">
                        <input
                          type="radio"
                          name="filtro"
                          value={opt.value}
                          checked={filtroRevision === opt.value}
                          onChange={() => setFiltroRevision(opt.value as typeof filtroRevision)}
                          className="accent-primary-500"
                        />
                        {opt.icon}
                        <span className="text-sm font-medium text-slate-200">{opt.label}</span>
                      </div>
                      <span className="badge badge-neutral text-xs font-mono">{opt.count}</span>
                    </label>
                  ))}
                </div>
              </div>

              {/* Resumen de Selección y Botón de Descarga */}
              <div className="pt-4 border-t border-slate-800/80">
                <div className="flex items-center justify-between text-xs text-slate-400 mb-3 font-medium">
                  <span>Personas seleccionadas:</span>
                  <span className="text-white font-mono font-bold text-sm">
                    {seleccionadosVisiblesCount} de {personasFiltradas.length}
                  </span>
                </div>

                <button
                  onClick={exportarXlsx}
                  disabled={exportando || seleccionadosVisiblesCount === 0}
                  className="btn-primary w-full py-3 flex items-center justify-center gap-2 text-sm font-bold shadow-lg shadow-primary-500/20 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {exportando ? (
                    <>
                      <div className="spinner w-4 h-4" />
                      <span>Generando Excel...</span>
                    </>
                  ) : (
                    <>
                      <Download className="w-4 h-4" />
                      <span>
                        {documentoSeleccionado !== "todos" && docActual
                          ? `Descargar Excel (${seleccionadosVisiblesCount})`
                          : `Descargar Excel (${seleccionadosVisiblesCount})`}
                      </span>
                    </>
                  )}
                </button>

                {personasFiltradas.length === 0 && (
                  <p className="text-center text-slate-500 text-xs mt-3">
                    No hay registros con los filtros seleccionados
                  </p>
                )}
              </div>
            </div>
          </div>

          {/* Columna Derecha: Vista Previa y Selección Fina */}
          <div className="lg:col-span-7">
            <div className="card bg-slate-900/80 border border-slate-800/80 backdrop-blur-md">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4 pb-3 border-b border-slate-800/80">
                <div>
                  <h2 className="text-lg font-bold text-white flex items-center gap-2">
                    <span>Vista Previa y Selección</span>
                    <span className="text-xs px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 font-mono">
                      {personasFiltradas.length}
                    </span>
                  </h2>
                  <p className="text-xs text-slate-400 mt-0.5">
                    Marca o desmarca personas específicas para personalizar tu exportación
                  </p>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={toggleSeleccionarTodo}
                    className="btn-secondary text-xs py-1.5 px-3 flex items-center gap-1.5"
                    title="Alternar selección de todos"
                  >
                    {todosVisiblesSeleccionados ? (
                      <>
                        <Square className="w-3.5 h-3.5 text-slate-400" />
                        <span>Deseleccionar</span>
                      </>
                    ) : (
                      <>
                        <CheckSquare className="w-3.5 h-3.5 text-primary-400" />
                        <span>Seleccionar todos</span>
                      </>
                    )}
                  </button>

                  <button
                    onClick={cargarDatos}
                    className="btn-secondary text-xs py-1.5 px-2.5"
                    title="Actualizar datos"
                  >
                    <RefreshCw className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>

              {cargando ? (
                <div className="space-y-2 py-4">
                  {Array(6).fill(0).map((_, i) => (
                    <div key={i} className="skeleton h-11 rounded-xl bg-slate-800/40" />
                  ))}
                </div>
              ) : personasFiltradas.length === 0 ? (
                <div className="text-center py-16 px-4">
                  <Users className="w-10 h-10 mx-auto mb-2 text-slate-600" />
                  <p className="text-slate-400 text-sm font-semibold">No se encontraron personas</p>
                  <p className="text-slate-600 text-xs mt-1">
                    Cambia el documento o filtro de revisión seleccionado.
                  </p>
                </div>
              ) : (
                <div className="overflow-x-auto max-h-[520px] overflow-y-auto pr-1">
                  <table className="table-base text-xs w-full">
                    <thead className="sticky top-0 bg-slate-950/90 backdrop-blur z-10">
                      <tr>
                        <th className="w-10 text-center py-2.5">
                          <input
                            type="checkbox"
                            checked={todosVisiblesSeleccionados}
                            onChange={toggleSeleccionarTodo}
                            className="rounded border-slate-700 bg-slate-800 text-primary-500 focus:ring-primary-500/40 cursor-pointer"
                          />
                        </th>
                        <th>Cédula</th>
                        <th>Nombre y Apellidos</th>
                        <th>Documento PDF</th>
                        <th>Estado</th>
                      </tr>
                    </thead>
                    <tbody>
                      {personasFiltradas.map((p) => {
                        const isSelected = seleccionados.has(p.id);
                        const nomCompleto = formatNombreCompleto(p);
                        const esRev = p.requiere_revision || (p.estado_registro && p.estado_registro !== "VALID");

                        return (
                          <tr
                            key={p.id}
                            onClick={() => togglePersona(p.id)}
                            className={`cursor-pointer transition-colors ${
                              isSelected
                                ? "bg-primary-500/10 hover:bg-primary-500/15"
                                : "hover:bg-slate-800/30 opacity-60"
                            }`}
                          >
                            <td className="text-center py-2.5" onClick={(e) => e.stopPropagation()}>
                              <input
                                type="checkbox"
                                checked={isSelected}
                                onChange={() => togglePersona(p.id)}
                                className="rounded border-slate-700 bg-slate-800 text-primary-500 focus:ring-primary-500/40 cursor-pointer"
                              />
                            </td>
                            <td className="font-mono text-primary-300 font-bold">
                              {p.numero_identificacion}
                            </td>
                            <td className="font-medium text-slate-200">
                              {nomCompleto || "—"}
                            </td>
                            <td className="text-slate-400 font-mono text-[11px] max-w-[150px] truncate" title={p.nombre_documento || "—"}>
                              {p.nombre_documento || "—"}
                            </td>
                            <td>
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
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
