"use client";

import { useState, useCallback, useEffect } from "react";
import { useDropzone } from "react-dropzone";
import { useRouter } from "next/navigation";
import toast from "react-hot-toast";
import {
  GitCompare, Upload, FileSpreadsheet, Download,
  CheckCircle, AlertTriangle, RefreshCw, BarChart3,
  Plus, Minus, Equal,
} from "lucide-react";
import Sidebar from "@/components/ui/Sidebar";
import { apiComparacion } from "@/lib/api";
import { auth } from "@/lib/auth";
import type { Comparacion, Diferencia } from "@/types";

const TIPO_CONFIG = {
  diferente: { label: "Campo diferente", clase: "badge-warning", icon: <AlertTriangle className="w-3 h-3" /> },
  faltante_bd: { label: "Faltante en BD", clase: "badge-danger", icon: <Minus className="w-3 h-3" /> },
  nuevo_bd: { label: "Nuevo en BD", clase: "badge-success", icon: <Plus className="w-3 h-3" /> },
  igual: { label: "Igual", clase: "badge-success", icon: <Equal className="w-3 h-3" /> },
};

export default function ComparacionPage() {
  const router = useRouter();
  const [comparaciones, setComparaciones] = useState<Comparacion[]>([]);
  const [comparacionActiva, setComparacionActiva] = useState<Comparacion | null>(null);
  const [diferencias, setDiferencias] = useState<Diferencia[]>([]);
  const [filtroDif, setFiltroDif] = useState<string>("todos");
  const [subiendo, setSubiendo] = useState(false);
  const [cargando, setCargando] = useState(true);
  const [descargando, setDescargando] = useState(false);

  useEffect(() => {
    if (!auth.isAuthenticated()) { router.push("/"); return; }
    cargarComparaciones();
  }, []);

  const cargarComparaciones = async () => {
    try {
      const { data } = await apiComparacion.listar();
      setComparaciones(data);
    } catch { } finally { setCargando(false); }
  };

  const verDiferencias = async (comp: Comparacion) => {
    setComparacionActiva(comp);
    try {
      const { data } = await apiComparacion.diferencias(comp.id);
      setDiferencias(data);
    } catch { toast.error("Error cargando diferencias"); }
  };

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    const file = acceptedFiles[0];
    if (!file) return;

    const ext = file.name.split(".").pop()?.toLowerCase();
    if (!["xlsx", "xls"].includes(ext || "")) {
      toast.error("Solo se aceptan archivos .xlsx o .xls");
      return;
    }

    setSubiendo(true);
    try {
      const { data } = await apiComparacion.uploadExcel(file, true);
      toast.success(`Comparación iniciada: ${file.name}`);
      cargarComparaciones();

      // Polling hasta que complete
      const polling = setInterval(async () => {
        try {
          const { data: updated } = await apiComparacion.detalle(data.id);
          if (updated.estado === "completado" || updated.estado === "error") {
            clearInterval(polling);
            cargarComparaciones();
            if (updated.estado === "completado") {
              toast.success("Comparación completada");
              setComparacionActiva(updated);
              const { data: difs } = await apiComparacion.diferencias(updated.id);
              setDiferencias(difs);
            } else {
              toast.error("Error en la comparación");
            }
          }
        } catch { clearInterval(polling); }
      }, 3000);
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      toast.error(error.response?.data?.detail || "Error subiendo archivo");
    } finally { setSubiendo(false); }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
      "application/vnd.ms-excel": [".xls"],
    },
    multiple: false,
  });

  const descargarReporte = async () => {
    if (!comparacionActiva) return;
    setDescargando(true);
    try {
      await apiComparacion.descargarReporte(comparacionActiva.id, comparacionActiva.nombre_original);
      toast.success("Reporte descargado");
    } catch { toast.error("Error descargando reporte"); }
    finally { setDescargando(false); }
  };

  const difFiltradas = filtroDif === "todos"
    ? diferencias
    : diferencias.filter((d) => d.tipo_diferencia === filtroDif);

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="ml-64 flex-1 p-8">
        <div className="mb-8 page-enter">
          <div className="flex items-center gap-2 mb-1">
            <GitCompare className="w-5 h-5 text-primary-400" />
            <span className="text-primary-400 text-sm font-medium">Análisis</span>
          </div>
          <h1 className="text-3xl font-bold text-white">Comparación de Datos</h1>
          <p className="text-slate-400 mt-1">
            Compara registros de la BD con archivos Excel externos
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Panel izquierdo */}
          <div className="space-y-6">
            {/* Upload */}
            <div className="card page-enter">
              <h2 className="text-base font-semibold text-white mb-4 flex items-center gap-2">
                <Upload className="w-4 h-4 text-primary-400" />
                Cargar Excel Externo
              </h2>
              <div
                {...getRootProps()}
                className={`dropzone py-8 ${isDragActive ? "active" : ""} ${subiendo ? "pointer-events-none opacity-50" : ""}`}
              >
                <input {...getInputProps()} />
                {subiendo ? (
                  <div className="spinner" />
                ) : (
                  <FileSpreadsheet className="w-10 h-10 text-green-400" />
                )}
                <p className="text-sm text-slate-300 text-center">
                  {subiendo ? "Procesando comparación..." :
                   isDragActive ? "Suelta el archivo" :
                   "Arrastra un .xlsx o haz clic"}
                </p>
                <p className="text-xs text-slate-600">XLSX · XLS</p>
              </div>
              <p className="text-xs text-slate-500 mt-3">
                El Excel debe tener columna: <code className="text-primary-400">identificacion</code> (o cedula, cc)
              </p>
            </div>

            {/* Historial */}
            <div className="card page-enter">
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-base font-semibold text-white">Historial</h2>
                <button onClick={cargarComparaciones} className="text-slate-500 hover:text-primary-400 transition-colors">
                  <RefreshCw className="w-4 h-4" />
                </button>
              </div>
              {cargando ? (
                <div className="space-y-2">
                  {Array(4).fill(0).map((_, i) => <div key={i} className="skeleton h-14 rounded-xl" />)}
                </div>
              ) : comparaciones.length === 0 ? (
                <p className="text-slate-500 text-sm text-center py-4">Sin comparaciones aún</p>
              ) : (
                <div className="space-y-2 max-h-80 overflow-y-auto pr-1">
                  {comparaciones.map((c) => (
                    <button
                      key={c.id}
                      onClick={() => verDiferencias(c)}
                      className={`w-full text-left p-3 rounded-xl border transition-all duration-200 ${
                        comparacionActiva?.id === c.id
                          ? "border-primary-500 bg-primary-500/10"
                          : "border-white/[0.06] hover:border-white/15 bg-dark-800"
                      }`}
                    >
                      <p className="text-sm text-white font-medium truncate">{c.nombre_original}</p>
                      <div className="flex items-center gap-2 mt-1">
                        <span className={`badge text-[10px] ${c.estado === "completado" ? "badge-success" : c.estado === "error" ? "badge-danger" : "badge-warning"}`}>
                          {c.estado}
                        </span>
                        {c.estado === "completado" && (
                          <span className="text-[10px] text-slate-500">
                            {c.total_diferentes} diferencias
                          </span>
                        )}
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Panel derecho - Resultados */}
          <div className="lg:col-span-2 space-y-6">
            {comparacionActiva && comparacionActiva.estado === "completado" ? (
              <>
                {/* Stats de comparación */}
                <div className="card page-enter">
                  <div className="flex items-center justify-between mb-4">
                    <h2 className="text-base font-semibold text-white flex items-center gap-2">
                      <BarChart3 className="w-4 h-4 text-primary-400" />
                      Resultados: {comparacionActiva.nombre_original}
                    </h2>
                    <button
                      onClick={descargarReporte}
                      disabled={descargando}
                      className="btn-success text-sm py-2 px-4"
                    >
                      {descargando ? <div className="spinner" /> : <Download className="w-4 h-4" />}
                      Reporte Excel
                    </button>
                  </div>

                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    {[
                      { label: "Total BD", value: comparacionActiva.total_registros_bd, color: "text-blue-400" },
                      { label: "Total Excel", value: comparacionActiva.total_registros_excel, color: "text-slate-300" },
                      { label: "Coincidentes", value: comparacionActiva.total_coincidentes, color: "text-green-400" },
                      { label: "Diferentes", value: comparacionActiva.total_diferentes, color: "text-yellow-400" },
                      { label: "Faltantes BD", value: comparacionActiva.total_faltantes_bd, color: "text-red-400" },
                      { label: "Nuevos BD", value: comparacionActiva.total_nuevos_bd, color: "text-purple-400" },
                    ].map((s) => (
                      <div key={s.label} className="bg-dark-800 rounded-xl p-3 text-center border border-white/[0.05]">
                        <p className={`text-2xl font-bold ${s.color}`}>{s.value}</p>
                        <p className="text-slate-500 text-xs mt-0.5">{s.label}</p>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Tabla de diferencias */}
                <div className="card page-enter">
                  <div className="flex flex-wrap items-center gap-3 mb-4">
                    <h3 className="text-base font-semibold text-white">Detalle de Diferencias</h3>
                    <div className="flex gap-2 ml-auto">
                      {["todos", "diferente", "faltante_bd", "nuevo_bd"].map((tipo) => (
                        <button
                          key={tipo}
                          onClick={() => setFiltroDif(tipo)}
                          className={`text-xs px-3 py-1.5 rounded-lg border transition-all ${
                            filtroDif === tipo
                              ? "bg-primary-500 border-primary-500 text-white"
                              : "border-white/10 text-slate-400 hover:border-white/20"
                          }`}
                        >
                          {tipo === "todos" ? "Todos" :
                           tipo === "diferente" ? "Diferentes" :
                           tipo === "faltante_bd" ? "Faltantes" : "Nuevos"}
                        </button>
                      ))}
                    </div>
                  </div>

                  {difFiltradas.length === 0 ? (
                    <div className="text-center py-8">
                      <CheckCircle className="w-10 h-10 text-green-400 mx-auto mb-2" />
                      <p className="text-slate-400">No hay diferencias en este filtro</p>
                    </div>
                  ) : (
                    <div className="table-container max-h-96 overflow-y-auto">
                      <table className="table-base text-xs">
                        <thead className="sticky top-0">
                          <tr>
                            <th>Identificación</th>
                            <th>Campo</th>
                            <th>Valor en BD</th>
                            <th>Valor en Excel</th>
                            <th>Tipo</th>
                          </tr>
                        </thead>
                        <tbody>
                          {difFiltradas.slice(0, 200).map((d) => {
                            const cfg = TIPO_CONFIG[d.tipo_diferencia as keyof typeof TIPO_CONFIG];
                            return (
                              <tr key={d.id}>
                                <td className="font-mono text-primary-400">{d.numero_identificacion}</td>
                                <td className="text-slate-400">{d.campo || "—"}</td>
                                <td className="max-w-[150px] truncate">{d.valor_bd || <span className="text-slate-600">vacío</span>}</td>
                                <td className="max-w-[150px] truncate">{d.valor_excel || <span className="text-slate-600">vacío</span>}</td>
                                <td>
                                  <span className={`badge ${cfg?.clase || "badge-neutral"} flex items-center gap-1 w-fit`}>
                                    {cfg?.icon}
                                    {cfg?.label}
                                  </span>
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                      {difFiltradas.length > 200 && (
                        <p className="text-center text-slate-500 text-xs py-3">
                          Mostrando 200 de {difFiltradas.length}. Descarga el reporte para ver todos.
                        </p>
                      )}
                    </div>
                  )}
                </div>
              </>
            ) : (
              <div className="card flex flex-col items-center justify-center py-24 text-center page-enter">
                <GitCompare className="w-16 h-16 text-slate-700 mb-4" />
                <h3 className="text-white font-semibold text-lg mb-2">Sin comparación activa</h3>
                <p className="text-slate-400 text-sm max-w-xs">
                  Sube un archivo Excel externo para comparar con los datos de la base de datos
                </p>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
