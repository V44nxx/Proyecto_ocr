"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { useDropzone } from "react-dropzone";
import { useRouter } from "next/navigation";
import toast from "react-hot-toast";
import {
  GitCompare, Upload, FileSpreadsheet, Download,
  CheckCircle, AlertTriangle, RefreshCw, BarChart3,
  Plus, Minus, Equal, Search, UserPlus,
} from "lucide-react";

import Sidebar from "@/components/ui/Sidebar";
import { apiComparacion, getErrorMessage } from "@/lib/api";
import { auth } from "@/lib/auth";
import type { Comparacion, Diferencia } from "@/types";

const TIPO_CONFIG = {
  diferente: { label: "Campo diferente", clase: "badge-warning", icon: <AlertTriangle className="w-3 h-3" /> },
  faltante_bd: { label: "Faltante en BD", clase: "badge-danger", icon: <Minus className="w-3 h-3" /> },
  nuevo_bd: { label: "Nuevo en BD", clase: "badge-success", icon: <Plus className="w-3 h-3" /> },
  igual: { label: "Igual", clase: "badge-success", icon: <Equal className="w-3 h-3" /> },
};

// Helper para limpiar y formatear datos de personas y evitar mostrar diccionarios JSON o sufijos de estado en la tabla
function limpiarValorTexto(val: string | null | undefined): string {
  if (!val) return "";
  let s = String(val).trim();
  // Quitar cualquier sufijo residual de estado como ' · Preinscrito', ' - Preinscrito', ' · Inscrito'
  s = s.replace(/\s*[·\-\–]\s*(Preinscrito|Inscrito|Matriculado|Cancelado)\b/gi, "").trim();

  if (s.startsWith("{") && s.endsWith("}")) {
    try {
      const jsonStr = s
        .replace(/'/g, '"')
        .replace(/None/g, "null")
        .replace(/True/g, "true")
        .replace(/False/g, "false");
      const obj = JSON.parse(jsonStr);
      const nc = obj.nombre_completo || `${obj.nombres || obj.nombre || ""} ${obj.apellidos || obj.apellido || ""}`.trim();
      if (nc) return String(nc).replace(/\s*[·\-\–]\s*(Preinscrito|Inscrito|Matriculado|Cancelado)\b/gi, "").trim();
    } catch {
      const mNomComp = s.match(/['"]nombre_completo['"]\s*:\s*['"]([^'"]+)['"]/i);
      if (mNomComp) return mNomComp[1].replace(/\s*[·\-\–]\s*(Preinscrito|Inscrito|Matriculado|Cancelado)\b/gi, "").trim();
      const mNom = s.match(/['"]nombres?['"]\s*:\s*['"]([^'"]+)['"]/i);
      const mApe = s.match(/['"]apellidos?['"]\s*:\s*['"]([^'"]+)['"]/i);
      const nom = mNom ? mNom[1] : "";
      const ape = mApe ? mApe[1] : "";
      const res = `${nom} ${ape}`.trim();
      if (res) return res.replace(/\s*[·\-\–]\s*(Preinscrito|Inscrito|Matriculado|Cancelado)\b/gi, "").trim();
    }
  }
  return s;
}

function limpiarEtiquetaCampo(campo: string | null | undefined, tipo: string): string {
  if (!campo || campo === "registro_completo" || campo === "persona_faltante" || campo === "persona_sobrante") {
    if (tipo === "faltante_bd") return "No encontrada en PDF";
    if (tipo === "nuevo_bd") return "No en Planilla (Sobrante)";
    return "Registro Completo";
  }
  if (campo === "nombre_completo") return "Nombre y Apellidos";
  if (campo === "numero_identificacion") return "Número de Cédula/ID";
  return campo.replace(/_/g, " ");
}

export default function ComparacionPage() {

  const router = useRouter();
  const [comparaciones, setComparaciones] = useState<Comparacion[]>([]);
  const [comparacionActiva, setComparacionActiva] = useState<Comparacion | null>(null);
  const [diferencias, setDiferencias] = useState<Diferencia[]>([]);
  const [filtroDif, setFiltroDif] = useState<string>("todos");
  const [busqueda, setBusqueda] = useState<string>("");
  const [subiendo, setSubiendo] = useState(false);
  const [cargando, setCargando] = useState(true);
  const [descargando, setDescargando] = useState(false);
  const [corrigiendoId, setCorrigiendoId] = useState<string | null>(null);
  const [agregandoId, setAgregandoId] = useState<string | null>(null);
  const pollingRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, []);

  useEffect(() => {
    if (!auth.isAuthenticated()) { router.push("/"); return; }
    const idParam = typeof window !== "undefined"
      ? new URLSearchParams(window.location.search).get("id")
      : null;
    cargarComparaciones(idParam || undefined);
  }, []);

  const iniciarPolling = (comp: Comparacion) => {
    if (pollingRef.current) clearInterval(pollingRef.current);

    pollingRef.current = setInterval(async () => {
      try {
        const { data: updated } = await apiComparacion.detalle(comp.id);
        setComparacionActiva(updated);
        setComparaciones((prev) =>
          prev.map((c) => (c.id === updated.id ? updated : c))
        );

        if (updated.estado === "completado" || updated.estado === "error") {
          if (pollingRef.current) clearInterval(pollingRef.current);
          if (updated.estado === "completado") {
            toast.success("¡Comparación completada con éxito!");
            try {
              const { data: difs } = await apiComparacion.diferencias(updated.id);
              setDiferencias(difs);
            } catch {
              toast.error("Error cargando diferencias");
            }
          } else {
            toast.error(updated.mensaje_error || "Error en la comparación");
          }
        }
      } catch {
        // Reintentar en siguiente ciclo
      }
    }, 1500);
  };

  const verDiferencias = async (comp: Comparacion) => {
    if (pollingRef.current) clearInterval(pollingRef.current);
    setComparacionActiva(comp);
    if (comp.estado === "completado") {
      try {
        const { data } = await apiComparacion.diferencias(comp.id);
        setDiferencias(data);
      } catch {
        toast.error("Error cargando diferencias");
      }
    } else if (comp.estado === "procesando" || comp.estado === "pendiente") {
      setDiferencias([]);
      iniciarPolling(comp);
    }
  };

  const cargarComparaciones = async (idASeleccionar?: string) => {
    try {
      const { data } = await apiComparacion.listar();
      setComparaciones(data);

      if (data && data.length > 0) {
        const objetivo = (idASeleccionar ? data.find((c) => c.id === idASeleccionar) : null)
          || (comparacionActiva ? data.find((c) => c.id === comparacionActiva.id) : null)
          || data[0];

        if (objetivo) {
          verDiferencias(objetivo);
        }
      }
    } catch {
    } finally {
      setCargando(false);
    }
  };

  const aplicarCorreccion = async (d: Diferencia) => {
    if (!comparacionActiva || !d.valor_excel || !d.campo) return;
    setCorrigiendoId(d.id);
    try {
      await apiComparacion.corregirCampo(comparacionActiva.id, {
        numero_identificacion: d.numero_identificacion,
        campo: d.campo,
        nuevo_valor: d.valor_excel,
      });
      toast.success(`Campo '${d.campo}' actualizado a '${d.valor_excel}' en BD`);

      // Actualizar estado local
      setDiferencias((prev) =>
        prev.map((item) =>
          item.id === d.id
            ? { ...item, valor_bd: d.valor_excel, tipo_diferencia: "igual" }
            : item
        )
      );

      // Actualizar conteos
      setComparacionActiva((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          total_diferentes: Math.max(0, prev.total_diferentes - 1),
          total_coincidentes: prev.total_coincidentes + 1,
        };
      });
    } catch (err: unknown) {
      toast.error(getErrorMessage(err, "Error al actualizar campo"));
    } finally {
      setCorrigiendoId(null);
    }
  };

  const agregarPersonaABd = async (d: Diferencia) => {
    if (!comparacionActiva) return;
    setAgregandoId(d.id);
    try {
      const nombreLimpio = limpiarValorTexto(d.valor_excel);
      await apiComparacion.agregarPersonaBd(comparacionActiva.id, {
        numero_identificacion: d.numero_identificacion,
        nombre_completo: nombreLimpio || undefined,
      });
      toast.success(
        `Persona ${d.numero_identificacion} agregada a la BD. Ahora puedes subir su cédula en Personas.`
      );

      // Actualizar estado local
      setDiferencias((prev) =>
        prev.map((item) =>
          item.id === d.id
            ? { ...item, valor_bd: nombreLimpio || item.numero_identificacion, tipo_diferencia: "igual" }
            : item
        )
      );

      // Actualizar conteos
      setComparacionActiva((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          total_faltantes_bd: Math.max(0, (prev.total_faltantes_bd || 1) - 1),
          total_coincidentes: (prev.total_coincidentes || 0) + 1,
        };
      });
    } catch (err: unknown) {
      toast.error(getErrorMessage(err, "Error al agregar persona a la BD"));
    } finally {
      setAgregandoId(null);
    }
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
      setComparaciones((prev) => [data, ...prev.filter((c) => c.id !== data.id)]);
      verDiferencias(data);
    } catch (err: unknown) {
      toast.error(getErrorMessage(err, "Error subiendo archivo"));
    } finally {
      setSubiendo(false);
    }
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

  const cantDif = diferencias.filter((d) => d.tipo_diferencia === "diferente").length;
  const cantFal = diferencias.filter((d) => d.tipo_diferencia === "faltante_bd").length;
  const cantNue = diferencias.filter((d) => d.tipo_diferencia === "nuevo_bd").length;

  const difFiltradas = diferencias
    .filter((d) => filtroDif === "todos" || d.tipo_diferencia === filtroDif)
    .filter((d) => {
      if (!busqueda) return true;
      const q = busqueda.toLowerCase();
      return (
        d.numero_identificacion.toLowerCase().includes(q) ||
        (d.campo && d.campo.toLowerCase().includes(q)) ||
        (d.valor_bd && d.valor_bd.toLowerCase().includes(q)) ||
        (d.valor_excel && d.valor_excel.toLowerCase().includes(q))
      );
    });

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="ml-64 flex-1 p-8">
        <div className="mb-8 page-enter">
          <div className="flex items-center gap-2 mb-1">
            <GitCompare className="w-5 h-5 text-primary-400" />
            <span className="text-primary-400 text-sm font-medium">Análisis y Auditoría</span>
          </div>
          <h1 className="text-3xl font-bold text-white">Comparación de Datos</h1>
          <p className="text-slate-400 mt-1">
            Coteja los registros extraídos por OCR con planillas oficiales (SENA/SGC), audita discrepancias y descarga el reporte consolidado.
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Panel izquierdo */}
          <div className="space-y-6">
            {/* Upload */}
            <div className="card page-enter">
              <h2 className="text-base font-semibold text-white mb-3 flex items-center gap-2">
                <Upload className="w-4 h-4 text-primary-400" />
                Cargar Planilla Oficial (Excel)
              </h2>
              <div className="mb-4 p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/25 text-emerald-300 text-xs flex items-start gap-2.5">
                <CheckCircle className="w-4 h-4 flex-shrink-0 mt-0.5 text-emerald-400" />
                <span className="leading-relaxed">
                  <strong>Carga automática:</strong> Las planillas subidas al presionar <em>Iniciar OCR</em> en <strong>Documentos</strong> se cotejan aquí automáticamente sin tener que volver a subirlas.
                </span>
              </div>
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
                  {subiendo ? "Procesando cotejo de datos..." :
                   isDragActive ? "Suelta el archivo" :
                   "Arrastra un .xlsx/.xls o haz clic"}
                </p>
                <p className="text-xs text-slate-600">XLSX · XLS</p>
              </div>
              <p className="text-xs text-slate-500 mt-3">
                Detecta automáticamente columnas como: <code className="text-primary-400">identificacion</code>, <code className="text-primary-400">nombre</code>, <code className="text-primary-400">apellido</code>, etc.
              </p>
            </div>

            {/* Historial */}
            <div className="card page-enter">
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-base font-semibold text-white">Historial de Comparaciones</h2>
                <button onClick={() => cargarComparaciones()} className="text-slate-500 hover:text-primary-400 transition-colors" title="Actualizar historial">
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
                            {c.total_diferentes} difs · {c.total_coincidentes} OK
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
                  <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
                    <div>
                      <h2 className="text-base font-semibold text-white flex items-center gap-2">
                        <BarChart3 className="w-4 h-4 text-primary-400" />
                        Resultados: {comparacionActiva.nombre_original}
                      </h2>
                      <p className="text-xs text-slate-400 mt-0.5">
                        Auditoría automática de calidad de extracción vs planilla oficial
                      </p>
                    </div>
                    <button
                      onClick={descargarReporte}
                      disabled={descargando}
                      className="btn-success text-xs py-2 px-3.5 flex items-center gap-2 shadow-lg shadow-green-500/10 hover:shadow-green-500/20 transition-all"
                      title="Descargar reporte completo en formato Excel con 5 hojas"
                    >
                      {descargando ? <div className="spinner w-4 h-4" /> : <Download className="w-4 h-4" />}
                      <span>Descargar Auditoría XLSX</span>
                    </button>
                  </div>

                  <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-2.5">
                    {[
                      { label: "Total BD (OCR)", value: comparacionActiva.total_registros_bd, color: "text-blue-400" },
                      { label: "Total Excel", value: comparacionActiva.total_registros_excel, color: "text-slate-300" },
                      { label: "Coincidentes", value: comparacionActiva.total_coincidentes, color: "text-green-400" },
                      { label: "Con Diferencias", value: comparacionActiva.total_diferentes, color: "text-yellow-400" },
                      { label: "Faltantes en BD", value: comparacionActiva.total_faltantes_bd, color: "text-red-400" },
                      { label: "Sobrantes en BD", value: comparacionActiva.total_nuevos_bd, color: "text-purple-400" },
                    ].map((s) => (
                      <div key={s.label} className="bg-dark-800 rounded-xl p-2.5 text-center border border-white/[0.05]">
                        <p className={`text-xl font-bold ${s.color}`}>{s.value}</p>
                        <p className="text-slate-500 text-[11px] mt-0.5 leading-tight">{s.label}</p>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Tabla de diferencias */}
                <div className="card page-enter">
                  <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
                    <div className="flex flex-wrap items-center gap-2">
                      {[
                        { id: "todos", label: "Todos", count: diferencias.length },
                        { id: "diferente", label: "Diferencias", count: cantDif },
                        { id: "faltante_bd", label: "Faltantes en BD", count: cantFal },
                        { id: "nuevo_bd", label: "Sobrantes en BD", count: cantNue },
                      ].map((tab) => (
                        <button
                          key={tab.id}
                          onClick={() => setFiltroDif(tab.id)}
                          className={`text-xs px-3 py-1.5 rounded-lg border transition-all flex items-center gap-1.5 ${
                            filtroDif === tab.id
                              ? "bg-primary-500 border-primary-500 text-white font-medium"
                              : "border-white/10 text-slate-400 hover:border-white/20"
                          }`}
                        >
                          <span>{tab.label}</span>
                          <span className={`text-[10px] px-1.5 py-0.2 rounded-full ${
                            filtroDif === tab.id ? "bg-white/20 text-white" : "bg-white/5 text-slate-400"
                          }`}>
                            {tab.count}
                          </span>
                        </button>
                      ))}
                    </div>

                    <div className="relative w-full sm:w-56">
                      <input
                        type="text"
                        placeholder="Buscar por cédula o dato..."
                        value={busqueda}
                        onChange={(e) => setBusqueda(e.target.value)}
                        className="input-base text-xs py-1.5 pl-8 pr-3 w-full"
                      />
                      <Search className="w-3.5 h-3.5 text-slate-500 absolute left-2.5 top-1/2 -translate-y-1/2" />
                    </div>
                  </div>

                  {difFiltradas.length === 0 ? (
                    <div className="text-center py-10">
                      <CheckCircle className="w-10 h-10 text-green-400 mx-auto mb-2 opacity-80" />
                      <p className="text-slate-300 font-medium text-sm">Sin registros en este filtro</p>
                      <p className="text-slate-500 text-xs mt-0.5">Todos los datos comparados concuerdan o no hay coincidencias con la búsqueda.</p>
                    </div>
                  ) : (
                    <div className="table-container max-h-[460px] overflow-y-auto">
                      <table className="table-base text-xs">
                        <thead className="sticky top-0 z-10">
                          <tr>
                            <th>Identificación</th>
                            <th>Campo</th>
                            <th>Valor en BD (OCR)</th>
                            <th>Valor Oficial (Excel)</th>
                            <th>Tipo</th>
                            <th className="text-center">Acción</th>
                          </tr>
                        </thead>
                        <tbody>
                          {difFiltradas.slice(0, 200).map((d) => {
                            const cfg = TIPO_CONFIG[d.tipo_diferencia as keyof typeof TIPO_CONFIG];
                            const esDiferente = d.tipo_diferencia === "diferente";
                            const esFaltante = d.tipo_diferencia === "faltante_bd";
                            const esSobrante = d.tipo_diferencia === "nuevo_bd";

                            const valBdLimpio = limpiarValorTexto(d.valor_bd);
                            const valExLimpio = limpiarValorTexto(d.valor_excel);
                            const etiquetaCampo = limpiarEtiquetaCampo(d.campo, d.tipo_diferencia);

                            return (
                              <tr key={d.id} className="hover:bg-white/[0.02] transition-colors">
                                <td className="font-mono text-primary-400 font-medium text-xs">{d.numero_identificacion}</td>
                                <td>
                                  {esFaltante ? (
                                    <span className="badge badge-danger text-[10px] whitespace-nowrap">Faltante en PDF</span>
                                  ) : esSobrante ? (
                                    <span className="badge badge-primary text-[10px] whitespace-nowrap">No en Planilla</span>
                                  ) : (
                                    <span className="text-slate-300 font-medium capitalize text-xs">{etiquetaCampo}</span>
                                  )}
                                </td>
                                <td className="max-w-[220px]">
                                  {esFaltante ? (
                                    <span className="text-slate-500 italic text-[11px]">No detectada en PDF</span>
                                  ) : valBdLimpio ? (
                                    <span className={esDiferente ? "text-yellow-300 bg-yellow-500/10 px-2 py-0.5 rounded border border-yellow-500/20 inline-block font-mono text-[11px]" : "text-slate-200 font-medium text-xs"}>
                                      {valBdLimpio}
                                    </span>
                                  ) : (
                                    <span className="text-slate-600 italic text-[11px]">vacío / no registrado</span>
                                  )}
                                </td>
                                <td className="max-w-[220px]">
                                  {esSobrante ? (
                                    <span className="text-slate-500 italic text-[11px]">No figura en archivo Excel</span>
                                  ) : valExLimpio ? (
                                    <span className={esDiferente ? "text-green-300 bg-green-500/10 px-2 py-0.5 rounded border border-green-500/20 inline-block font-mono text-[11px]" : "text-slate-200 font-medium text-xs"}>
                                      {valExLimpio}
                                    </span>
                                  ) : (
                                    <span className="text-slate-600 italic text-[11px]">vacío / no registrado</span>
                                  )}
                                </td>
                                <td>
                                  <span className={`badge ${cfg?.clase || "badge-neutral"} flex items-center gap-1 w-fit text-[10px]`}>
                                    {cfg?.icon}
                                    {cfg?.label}
                                  </span>
                                </td>
                                <td className="text-center">
                                  {esDiferente && d.valor_excel && d.campo !== "registro_completo" ? (
                                    <button
                                      onClick={() => aplicarCorreccion(d)}
                                      disabled={corrigiendoId === d.id}
                                      className="btn-sm bg-primary-600/20 hover:bg-primary-600/30 text-primary-300 border border-primary-500/30 text-[11px] py-1 px-2.5 rounded-lg flex items-center gap-1 mx-auto transition-all whitespace-nowrap"
                                      title="Actualizar valor en la base de datos con el valor del Excel"
                                    >
                                      {corrigiendoId === d.id ? (
                                        <div className="spinner w-3 h-3" />
                                      ) : (
                                        <CheckCircle className="w-3 h-3 text-primary-400" />
                                      )}
                                      Corregir en BD
                                    </button>
                                  ) : d.tipo_diferencia === "igual" ? (
                                    <span className="text-green-400 text-[11px] font-medium flex items-center justify-center gap-1">
                                      <CheckCircle className="w-3.5 h-3.5" /> {esFaltante ? "Agregado a BD" : "Corregido"}
                                    </span>
                                  ) : esFaltante ? (
                                    <button
                                      onClick={() => agregarPersonaABd(d)}
                                      disabled={agregandoId === d.id}
                                      className="btn-sm bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-300 border border-emerald-500/40 text-[11px] py-1 px-2.5 rounded-lg flex items-center gap-1 mx-auto transition-all whitespace-nowrap"
                                      title="Agregar persona a la Base de Datos para luego subir su cédula"
                                    >
                                      {agregandoId === d.id ? (
                                        <div className="spinner w-3 h-3" />
                                      ) : (
                                        <UserPlus className="w-3 h-3 text-emerald-400" />
                                      )}
                                      + Agregar a BD
                                    </button>
                                  ) : esSobrante ? (
                                    <span className="text-blue-400/80 text-[10px] italic">Documento anexo</span>
                                  ) : (
                                    <span className="text-slate-600 text-[11px]">—</span>
                                  )}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                      {difFiltradas.length > 200 && (
                        <p className="text-center text-slate-500 text-xs py-3">
                          Mostrando 200 de {difFiltradas.length}. Descarga el reporte para ver la auditoría completa.
                        </p>
                      )}
                    </div>
                  )}
                </div>
              </>
            ) : comparacionActiva && (comparacionActiva.estado === "procesando" || comparacionActiva.estado === "pendiente") ? (
              <div className="card flex flex-col items-center justify-center py-20 text-center page-enter border border-primary-500/30 bg-dark-900/60 shadow-xl">
                <div className="relative mb-6">
                  <div className="w-20 h-20 rounded-3xl bg-primary-500/10 border border-primary-500/30 flex items-center justify-center shadow-lg shadow-primary-500/20">
                    <RefreshCw className="w-9 h-9 text-primary-400 animate-spin" />
                  </div>
                  <div className="absolute -bottom-1 -right-1 w-6 h-6 rounded-full bg-blue-500 border-2 border-dark-900 flex items-center justify-center">
                    <FileSpreadsheet className="w-3.5 h-3.5 text-white" />
                  </div>
                </div>
                <h3 className="text-white font-bold text-xl mb-2">
                  Auditoría y Comparación en Proceso
                </h3>
                <p className="text-slate-300 text-sm max-w-md mb-2 font-medium">
                  Cotejando registros con la planilla oficial:
                </p>
                <div className="px-3.5 py-1.5 rounded-lg bg-dark-800 border border-white/10 text-primary-300 font-mono text-xs mb-5 max-w-sm truncate">
                  📄 {comparacionActiva.nombre_original}
                </div>
                <p className="text-slate-400 text-xs max-w-md mb-6 leading-relaxed">
                  El sistema está cruzando los números de documento, nombres y datos del OCR contra la planilla de referencia. Esta vista se actualizará automáticamente en unos segundos.
                </p>
                <div className="inline-flex items-center gap-2.5 px-4 py-2 rounded-full bg-primary-500/15 border border-primary-500/30 text-primary-300 text-xs font-semibold animate-pulse">
                  <span className="w-2 h-2 rounded-full bg-primary-400 animate-ping" />
                  <span>Procesando auditoría en tiempo real...</span>
                </div>
              </div>
            ) : comparacionActiva && comparacionActiva.estado === "error" ? (
              <div className="card flex flex-col items-center justify-center py-20 text-center page-enter border border-red-500/30">
                <AlertTriangle className="w-14 h-14 text-red-400 mb-3" />
                <h3 className="text-white font-bold text-lg mb-1">Error en la Comparación</h3>
                <p className="text-red-300/90 text-xs max-w-md mb-4 font-mono">
                  {comparacionActiva.mensaje_error || "Ocurrió un problema durante el procesamiento de la planilla."}
                </p>
                <button
                  onClick={() => verDiferencias(comparacionActiva)}
                  className="btn-secondary text-xs py-2 px-4 flex items-center gap-2"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                  <span>Reintentar</span>
                </button>
              </div>
            ) : (
              <div className="card flex flex-col items-center justify-center py-24 text-center page-enter">
                <GitCompare className="w-16 h-16 text-slate-700 mb-4" />
                <h3 className="text-white font-semibold text-lg mb-2">Sin comparaciones registradas</h3>
                <p className="text-slate-400 text-sm max-w-xs">
                  Sube una planilla Excel oficial aquí o inicia el OCR con planilla en el módulo de Documentos.
                </p>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}

