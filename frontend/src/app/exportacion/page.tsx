"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import toast from "react-hot-toast";
import {
  Download, FileSpreadsheet, Users, Filter,
  CheckCircle, AlertTriangle, RefreshCw,
} from "lucide-react";
import Sidebar from "@/components/ui/Sidebar";
import { apiExportacion, apiPersonas } from "@/lib/api";
import { auth } from "@/lib/auth";
import type { Persona } from "@/types";

export default function ExportacionPage() {
  const router = useRouter();
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [cargando, setCargando] = useState(true);
  const [exportando, setExportando] = useState(false);
  const [filtroRevision, setFiltroRevision] = useState<"todos" | "revision" | "ok">("todos");

  useEffect(() => {
    if (!auth.isAuthenticated()) { router.push("/"); return; }
    cargarPersonas();
  }, []);

  const cargarPersonas = async () => {
    setCargando(true);
    try {
      const { data } = await apiPersonas.listar({ limit: 500 });
      setPersonas(Array.isArray(data) ? data : (data.items || []));
    } catch { toast.error("Error cargando datos"); }
    finally { setCargando(false); }
  };

  const exportarXlsx = async () => {
    setExportando(true);
    try {
      let requiereRevision: boolean | undefined;
      if (filtroRevision === "revision") requiereRevision = true;
      else if (filtroRevision === "ok") requiereRevision = false;

      await apiExportacion.descargarXlsx(requiereRevision);
      toast.success("Archivo Excel descargado correctamente");
    } catch { toast.error("Error generando exportación"); }
    finally { setExportando(false); }
  };

  const stats = {
    total: personas.length,
    ok: personas.filter((p) => !p.requiere_revision).length,
    revision: personas.filter((p) => p.requiere_revision).length,
    completas: personas.filter(
      (p) => p.nombres && p.apellidos && p.fecha_nacimiento && p.fecha_expedicion
    ).length,
  };

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="ml-64 flex-1 p-8">
        <div className="mb-8 page-enter">
          <div className="flex items-center gap-2 mb-1">
            <Download className="w-5 h-5 text-primary-400" />
            <span className="text-primary-400 text-sm font-medium">Exportar</span>
          </div>
          <h1 className="text-3xl font-bold text-white">Exportación Excel</h1>
          <p className="text-slate-400 mt-1">
            Genera archivos XLSX con los registros de personas
          </p>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8 page-enter">
          {[
            { label: "Total Personas", value: stats.total, color: "text-blue-400" },
            { label: "Validadas OK", value: stats.ok, color: "text-green-400" },
            { label: "En Revisión", value: stats.revision, color: "text-yellow-400" },
            { label: "Fichas Completas", value: stats.completas, color: "text-purple-400" },
          ].map((s) => (
            <div key={s.label} className="card text-center">
              <p className={`text-3xl font-bold ${s.color}`}>{s.value}</p>
              <p className="text-slate-400 text-sm mt-1">{s.label}</p>
            </div>
          ))}
        </div>

        {/* Panel de exportación */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 page-enter">
          <div className="card">
            <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <FileSpreadsheet className="w-5 h-5 text-green-400" />
              Configurar Exportación
            </h2>

            <div className="mb-6">
              <label className="input-label flex items-center gap-2">
                <Filter className="w-4 h-4" />
                Filtrar registros
              </label>
              <div className="space-y-2 mt-2">
                {[
                  { value: "todos", label: "Todos los registros", icon: <Users className="w-4 h-4 text-blue-400" />, count: stats.total },
                  { value: "ok", label: "Solo validados OK", icon: <CheckCircle className="w-4 h-4 text-green-400" />, count: stats.ok },
                  { value: "revision", label: "Solo en revisión", icon: <AlertTriangle className="w-4 h-4 text-yellow-400" />, count: stats.revision },
                ].map((opt) => (
                  <label
                    key={opt.value}
                    className={`flex items-center justify-between p-3 rounded-xl border cursor-pointer transition-all ${
                      filtroRevision === opt.value
                        ? "border-primary-500 bg-primary-500/10"
                        : "border-white/[0.06] hover:border-white/15 bg-dark-800"
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
                      <span className="text-sm text-slate-300">{opt.label}</span>
                    </div>
                    <span className="badge badge-neutral">{opt.count}</span>
                  </label>
                ))}
              </div>
            </div>

            <button
              onClick={exportarXlsx}
              disabled={exportando || personas.length === 0}
              className="btn-primary w-full"
            >
              {exportando ? (
                <><div className="spinner" />Generando Excel...</>
              ) : (
                <><Download className="w-4 h-4" />Descargar Excel (.xlsx)</>
              )}
            </button>

            {personas.length === 0 && (
              <p className="text-center text-slate-500 text-sm mt-3">
                No hay personas registradas para exportar
              </p>
            )}
          </div>

          {/* Vista previa */}
          <div className="card">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-white">Vista Previa</h2>
              <button onClick={cargarPersonas} className="btn-secondary text-xs py-1.5 px-3">
                <RefreshCw className="w-3 h-3" />
                Actualizar
              </button>
            </div>

            {cargando ? (
              <div className="space-y-2">
                {Array(5).fill(0).map((_, i) => <div key={i} className="skeleton h-10 rounded-lg" />)}
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="table-base text-xs">
                  <thead>
                    <tr>
                      <th>Cédula</th>
                      <th>Nombres</th>
                      <th>Apellidos</th>
                      <th>Estado</th>
                    </tr>
                  </thead>
                  <tbody>
                    {personas.slice(0, 8).map((p) => (
                      <tr key={p.id}>
                        <td className="font-mono text-primary-400">{p.numero_identificacion}</td>
                        <td>{p.nombres || "—"}</td>
                        <td>{p.apellidos || "—"}</td>
                        <td>
                          {p.requiere_revision ? (
                            <span className="badge badge-warning">Revisión</span>
                          ) : (
                            <span className="badge badge-success">OK</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {personas.length > 8 && (
                  <p className="text-center text-slate-500 text-xs mt-3">
                    + {personas.length - 8} registros más en el archivo exportado
                  </p>
                )}
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
