"use client";

import { useState, useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import toast from "react-hot-toast";
import {
  Users, Search, AlertTriangle, CheckCircle,
  Edit3, Save, X, RefreshCw, Trash2, Calendar, MapPin, ShieldCheck, UserCheck
} from "lucide-react";
import Sidebar from "@/components/ui/Sidebar";
import { apiPersonas } from "@/lib/api";
import { auth } from "@/lib/auth";
import type { Persona, PersonaUpdate } from "@/types";

export default function PersonasPage() {
  const router = useRouter();
  const pathname = usePathname();
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [cargando, setCargando] = useState(true);
  const [buscar, setBuscar] = useState("");
  const [soloRevision, setSoloRevision] = useState(false);
  const [editando, setEditando] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<PersonaUpdate>({});

  useEffect(() => {
    if (!auth.isAuthenticated()) { router.push("/"); return; }
    // Carga inmediata de la lista de personas desde el servidor
    cargarPersonas(true);

    // Polling automático cada 4 segundos para detectar nuevas personas procesadas en segundo plano
    const interval = setInterval(() => {
      cargarPersonas(false);
    }, 4000);

    return () => clearInterval(interval);
  }, [pathname, soloRevision]);

  const cargarPersonas = async (mostrarSpinner: boolean = false, revOnly?: boolean) => {
    if (mostrarSpinner) setCargando(true);
    try {
      const { data } = await apiPersonas.listar({
        limit: 100,
        requiere_revision: (revOnly ?? soloRevision) || undefined,
        buscar: buscar || undefined,
      });
      const items = Array.isArray(data) ? data : ((data as any)?.items || []);
      setPersonas(items);
      if (mostrarSpinner) {
        toast.success(`${items.length} persona(s) sincronizada(s)`);
      }
    } catch (err) { 
      console.error("Error al cargar personas:", err);
      if (mostrarSpinner) toast.error("Error al cargar la lista de personas"); 
    } finally { 
      if (mostrarSpinner) setCargando(false); 
    }
  };

  const iniciarEdicion = (p: Persona) => {
    setEditando(p.id);
    setEditForm({
      nombres: p.nombres || "",
      apellidos: p.apellidos || "",
      fecha_nacimiento: p.fecha_nacimiento || "",
      fecha_expedicion: p.fecha_expedicion || "",
      lugar_expedicion: p.lugar_expedicion || "",
      sexo: p.sexo || "",
      requiere_revision: p.requiere_revision,
    });
  };

  const guardarEdicion = async (id: string) => {
    try {
      await apiPersonas.actualizar(id, editForm);
      toast.success("Datos actualizados correctamente");
      setEditando(null);
      cargarPersonas(true);
    } catch { 
      toast.error("Error guardando cambios"); 
    }
  };

  const eliminar = async (id: string, cedula: string) => {
    if (!confirm(`¿Desea eliminar el registro de la persona con cédula ${cedula}?`)) return;
    try {
      await apiPersonas.eliminar(id);
      toast.success("Registro eliminado");
      cargarPersonas(true);
    } catch { 
      toast.error("Error al eliminar registro"); 
    }
  };

  const personasFiltradas = (personas || []).filter((p) => {
    if (!p) return false;
    if (!buscar) return true;
    const q = buscar.toLowerCase().trim().replace(/[\.\s]/g, ""); // normalizar puntos/espacios
    const cedula = String(p.numero_identificacion || "").replace(/[\.\s]/g, "");
    return (
      cedula.includes(q) ||
      String(p.nombres || "").toLowerCase().includes(q) ||
      String(p.apellidos || "").toLowerCase().includes(q)
    );
  });

  const [personaSeleccionada, setPersonaSeleccionada] = useState<Persona | null>(null);

  return (
    <div className="flex min-h-screen bg-[#0b0f19] text-slate-100 font-sans">
      <Sidebar />
      
      <main className="ml-64 flex-1 p-8 overflow-x-hidden">
        {/* Header Principal */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-8">
          <div>
            <div className="flex items-center gap-2 mb-1.5">
              <span className="p-1.5 rounded-lg bg-primary-500/10 border border-primary-500/20 text-primary-400">
                <Users className="w-4 h-4" />
              </span>
              <span className="text-xs font-semibold text-primary-400 uppercase tracking-wider">Base de Datos OCR</span>
            </div>
            <h1 className="text-3xl font-extrabold text-white tracking-tight">Personas Registradas</h1>
            <p className="text-slate-400 text-sm mt-1">
              Registro completo con layout espacial, trazabilidad por página e inspección detallada por campo.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <span className="px-3.5 py-1.5 rounded-full bg-slate-800/80 border border-slate-700/50 text-xs font-medium text-slate-300">
              <strong className="text-white font-bold">{personasFiltradas.length}</strong> Registros Encontrados
            </span>
          </div>
        </div>

        {/* Barra de Filtros y Controles */}
        <div className="grid grid-cols-1 md:grid-cols-12 gap-4 mb-6">
          <div className="md:col-span-6 relative">
            <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <input
              type="text"
              value={buscar}
              onChange={(e) => setBuscar(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && cargarPersonas(true)}
              placeholder="Buscar por número de cédula, nombres o apellidos..."
              className="w-full pl-10 pr-4 py-2.5 bg-slate-900/90 border border-slate-800 rounded-xl text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-primary-500/50 focus:ring-1 focus:ring-primary-500/50 transition-all shadow-sm"
            />
          </div>

          <div className="md:col-span-4 flex items-center">
            <label className="flex items-center gap-2.5 cursor-pointer w-full py-2.5 px-4 bg-slate-900/90 border border-slate-800 rounded-xl hover:bg-slate-800/50 transition-colors">
              <input
                type="checkbox"
                checked={soloRevision}
                onChange={(e) => setSoloRevision(e.target.checked)}
                className="w-4 h-4 rounded border-slate-700 bg-slate-800 text-primary-500 focus:ring-primary-500/40"
              />
              <AlertTriangle className="w-4 h-4 text-amber-400" />
              <span className="text-xs font-medium text-slate-300">Filtrar solo registros en revisión</span>
            </label>
          </div>

          <div className="md:col-span-2 flex justify-end">
            <button 
              onClick={() => cargarPersonas(true)} 
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700/60 rounded-xl text-xs font-semibold transition-all shadow-sm active:scale-[0.98]"
            >
              <RefreshCw className="w-3.5 h-3.5 text-primary-400" />
              Actualizar
            </button>
          </div>
        </div>

        {/* Tabla Elegante y Responsiva */}
        <div className="bg-slate-900/80 border border-slate-800/80 rounded-2xl shadow-xl overflow-hidden backdrop-blur-md">
          {cargando ? (
            <div className="p-8 space-y-4">
              {Array(6).fill(0).map((_, i) => (
                <div key={i} className="h-12 bg-slate-800/40 animate-pulse rounded-xl" />
              ))}
            </div>
          ) : personasFiltradas.length === 0 ? (
            <div className="text-center py-20 px-4">
              <div className="w-14 h-14 mx-auto mb-4 rounded-2xl bg-slate-800/60 border border-slate-700/50 flex items-center justify-center text-slate-500">
                <Users className="w-7 h-7" />
              </div>
              <h3 className="text-lg font-semibold text-slate-300">No se encontraron registros</h3>
              <p className="text-slate-500 text-xs mt-1 max-w-sm mx-auto">
                No hay personas registradas o ninguna coincide con el criterio de búsqueda.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-slate-800/80 bg-slate-950/50 text-[11px] font-bold text-slate-400 uppercase tracking-wider">
                    <th className="py-4 px-3 text-center">Pág.</th>
                    <th className="py-4 px-5">Cédula</th>
                    <th className="py-4 px-5">Nombres</th>
                    <th className="py-4 px-5">Apellidos</th>
                    <th className="py-4 px-4">F. Nacimiento</th>
                    <th className="py-4 px-4">F. Expedición</th>
                    <th className="py-4 px-4">Lugar Expedición</th>
                    <th className="py-4 px-3 text-center">Sexo</th>
                    <th className="py-4 px-4 text-center">Confianza</th>
                    <th className="py-4 px-4 text-center">Estado</th>
                    <th className="py-4 px-5 text-right">Acciones</th>
                  </tr>
                </thead>

                <tbody className="divide-y divide-slate-800/40 text-xs font-normal">
                  {personasFiltradas.map((p) => {
                    const estadoStr = p.estado_registro || (p.requiere_revision ? "REVIEW_REQUIRED" : "VALID");
                    return (
                      <tr key={p.id} className="hover:bg-slate-800/30 transition-colors">
                        {editando === p.id ? (
                          <>
                            <td className="py-3 px-3 text-center text-slate-500">{p.pagina_numero || 1}</td>
                            <td className="py-3 px-5 font-mono text-primary-400 font-bold whitespace-nowrap">
                              {p.numero_identificacion}
                            </td>
                            <td className="py-3 px-3">
                              <input
                                className="w-full bg-slate-950 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-primary-500"
                                value={editForm.nombres || ""}
                                onChange={(e) => setEditForm({ ...editForm, nombres: e.target.value })}
                              />
                            </td>
                            <td className="py-3 px-3">
                              <input
                                className="w-full bg-slate-950 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-primary-500"
                                value={editForm.apellidos || ""}
                                onChange={(e) => setEditForm({ ...editForm, apellidos: e.target.value })}
                              />
                            </td>
                            <td className="py-3 px-3">
                              <input
                                type="text"
                                placeholder="YYYY-MM-DD"
                                className="w-full bg-slate-950 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-primary-500"
                                value={editForm.fecha_nacimiento || ""}
                                onChange={(e) => setEditForm({ ...editForm, fecha_nacimiento: e.target.value })}
                              />
                            </td>
                            <td className="py-3 px-3">
                              <input
                                type="text"
                                placeholder="YYYY-MM-DD"
                                className="w-full bg-slate-950 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-primary-500"
                                value={editForm.fecha_expedicion || ""}
                                onChange={(e) => setEditForm({ ...editForm, fecha_expedicion: e.target.value })}
                              />
                            </td>
                            <td className="py-3 px-3">
                              <input
                                className="w-full bg-slate-950 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-primary-500"
                                value={editForm.lugar_expedicion || ""}
                                onChange={(e) => setEditForm({ ...editForm, lugar_expedicion: e.target.value })}
                              />
                            </td>
                            <td className="py-3 px-3">
                              <select
                                className="w-full bg-slate-950 border border-slate-700 rounded-lg px-2 py-1.5 text-xs text-white focus:outline-none focus:border-primary-500"
                                value={editForm.sexo || ""}
                                onChange={(e) => setEditForm({ ...editForm, sexo: e.target.value })}
                              >
                                <option value="">-</option>
                                <option value="MASCULINO">MASCULINO</option>
                                <option value="FEMENINO">FEMENINO</option>
                              </select>
                            </td>
                            <td colSpan={2} className="text-center text-slate-500">—</td>
                            <td className="py-3 px-5 text-right whitespace-nowrap">
                              <div className="flex items-center justify-end gap-1.5">
                                <button onClick={() => guardarEdicion(p.id)} className="p-1.5 rounded-lg bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 hover:bg-emerald-500/30 transition-colors">
                                  <Save className="w-4 h-4" />
                                </button>
                                <button onClick={() => setEditando(null)} className="p-1.5 rounded-lg bg-rose-500/20 text-rose-400 border border-rose-500/30 hover:bg-rose-500/30 transition-colors">
                                  <X className="w-4 h-4" />
                                </button>
                              </div>
                            </td>
                          </>
                        ) : (
                          <>
                            <td className="py-4 px-3 text-center whitespace-nowrap font-mono text-slate-400 text-[11px]">
                              Pág. {p.pagina_numero || 1}
                            </td>

                            <td className="py-4 px-5 font-mono text-primary-400 font-bold whitespace-nowrap">
                              {p.numero_identificacion}
                            </td>

                            <td className="py-4 px-5 font-semibold text-slate-100 whitespace-nowrap">
                              {p.nombres || <span className="text-slate-600 font-normal italic">Sin especificar</span>}
                            </td>

                            <td className="py-4 px-5 font-semibold text-slate-100 whitespace-nowrap">
                              {p.apellidos || <span className="text-slate-600 font-normal italic">Sin especificar</span>}
                            </td>

                            <td className="py-4 px-4 text-slate-300 whitespace-nowrap">
                              {p.fecha_nacimiento ? (
                                <span className="flex items-center gap-1.5 text-xs">
                                  <Calendar className="w-3.5 h-3.5 text-slate-500" />
                                  {p.fecha_nacimiento}
                                </span>
                              ) : (
                                <span className="text-slate-600">—</span>
                              )}
                            </td>

                            <td className="py-4 px-4 text-slate-300 whitespace-nowrap">
                              {p.fecha_expedicion ? (
                                <span className="flex items-center gap-1.5 text-xs">
                                  <Calendar className="w-3.5 h-3.5 text-slate-500" />
                                  {p.fecha_expedicion}
                                </span>
                              ) : (
                                <span className="text-slate-600">—</span>
                              )}
                            </td>

                            <td className="py-4 px-4 text-slate-300 max-w-[160px] truncate" title={p.lugar_expedicion || undefined}>
                              {p.lugar_expedicion ? (
                                <span className="flex items-center gap-1.5 text-xs truncate">
                                  <MapPin className="w-3.5 h-3.5 text-slate-500 flex-shrink-0" />
                                  <span className="truncate">{p.lugar_expedicion}</span>
                                </span>
                              ) : (
                                <span className="text-slate-600">—</span>
                              )}
                            </td>

                            <td className="py-4 px-3 text-center whitespace-nowrap">
                              {p.sexo ? (
                                <span className={`inline-block px-2.5 py-0.5 text-[11px] font-semibold rounded-full ${
                                  p.sexo.toUpperCase().includes("MASCULINO") || p.sexo === "M"
                                    ? "bg-blue-500/10 text-blue-400 border border-blue-500/20"
                                    : "bg-pink-500/10 text-pink-400 border border-pink-500/20"
                                }`}>
                                  {p.sexo.toUpperCase().includes("MASCULINO") || p.sexo === "M" ? "MASCULINO" : "FEMENINO"}
                                </span>
                              ) : (
                                <span className="text-slate-600">—</span>
                              )}
                            </td>

                            <td className="py-4 px-4 text-center whitespace-nowrap">
                              {p.confianza_extraccion != null ? (
                                <div className="flex items-center justify-center gap-2">
                                  <div className="w-12 h-1.5 bg-slate-800 rounded-full overflow-hidden">
                                    <div
                                      className="h-full bg-gradient-to-r from-blue-500 to-emerald-400 rounded-full"
                                      style={{ width: `${p.confianza_extraccion}%` }}
                                    />
                                  </div>
                                  <span className="text-xs font-medium text-slate-400">
                                    {Math.round(Number(p.confianza_extraccion))}%
                                  </span>
                                </div>
                              ) : (
                                <span className="text-slate-600">—</span>
                              )}
                            </td>

                            <td className="py-4 px-4 text-center whitespace-nowrap">
                              {estadoStr === "VALID" ? (
                                <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-[11px] font-semibold">
                                  <CheckCircle className="w-3 h-3" /> VÁLIDO
                                </span>
                              ) : estadoStr === "FALLBACK_TESSERACT" ? (
                                <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-amber-500/20 border border-amber-500/40 text-amber-300 text-[11px] font-semibold">
                                  <AlertTriangle className="w-3 h-3" /> TESSERACT
                                </span>
                              ) : estadoStr === "MISSING_DATA" ? (
                                <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-orange-500/10 border border-orange-500/20 text-orange-400 text-[11px] font-semibold">
                                  <AlertTriangle className="w-3 h-3" /> FALTANTES
                                </span>
                              ) : (
                                <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-amber-500/10 border border-amber-500/20 text-amber-400 text-[11px] font-semibold">
                                  <AlertTriangle className="w-3 h-3" /> REVISAR
                                </span>
                              )}
                            </td>

                            <td className="py-4 px-5 text-right whitespace-nowrap">
                              <div className="flex items-center justify-end gap-2">
                                <button
                                  onClick={() => setPersonaSeleccionada(p)}
                                  title="Inspeccionar detalle por campo"
                                  className="p-1.5 rounded-lg text-primary-400 hover:bg-primary-500/10 transition-colors"
                                >
                                  <ShieldCheck className="w-4 h-4" />
                                </button>
                                <button
                                  onClick={() => iniciarEdicion(p)}
                                  title="Editar datos"
                                  className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
                                >
                                  <Edit3 className="w-4 h-4" />
                                </button>
                                <button
                                  onClick={() => eliminar(p.id, p.numero_identificacion)}
                                  title="Eliminar registro"
                                  className="p-1.5 rounded-lg text-slate-400 hover:text-rose-400 hover:bg-slate-800 transition-colors"
                                >
                                  <Trash2 className="w-4 h-4" />
                                </button>
                              </div>
                            </td>
                          </>
                        )}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Modal de Inspección Detallada por Campo */}
        {personaSeleccionada && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-fadeIn">
            <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-xl w-full p-6 shadow-2xl space-y-6">
              <div className="flex items-center justify-between border-b border-slate-800 pb-4">
                <div>
                  <div className="flex items-center gap-2 text-xs font-semibold text-primary-400 uppercase tracking-wider">
                    <UserCheck className="w-4 h-4" /> Inspección Espacial por Campo
                  </div>
                  <h2 className="text-xl font-bold text-white mt-1">
                    Cédula {personaSeleccionada.numero_identificacion}
                  </h2>
                </div>
                <button
                  onClick={() => setPersonaSeleccionada(null)}
                  className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              <div className="grid grid-cols-3 gap-3 text-xs">
                <div className="p-3 bg-slate-950/60 rounded-xl border border-slate-800">
                  <span className="text-slate-400 block mb-1">Grupo Documento</span>
                  <span className="font-mono text-primary-400 font-bold">{personaSeleccionada.grupo_documento_id || "DOC-001"}</span>
                </div>
                <div className="p-3 bg-slate-950/60 rounded-xl border border-slate-800">
                  <span className="text-slate-400 block mb-1">Páginas (F / R)</span>
                  <span className="font-mono text-white font-bold">
                    Frente: {personaSeleccionada.pagina_frente || personaSeleccionada.pagina_numero || 1} | Rev: {personaSeleccionada.pagina_reverso || "-"}
                  </span>
                </div>
                <div className="p-3 bg-slate-950/60 rounded-xl border border-slate-800">
                  <span className="text-slate-400 block mb-1">Motor OCR</span>
                  <span className="font-mono text-emerald-400 font-bold">{personaSeleccionada.motor_ocr || "google_document_ai"}</span>
                </div>
              </div>

              {/* Evidencias de Agrupación del Documento */}
              {personaSeleccionada.detalles_campos?.grouping?.reasons && (
                <div className="p-3 rounded-xl bg-slate-950/80 border border-primary-500/30 text-xs space-y-1">
                  <span className="text-primary-400 font-bold uppercase text-[10px]">✓ Evidencias de Agrupación de Documento:</span>
                  <ul className="list-disc list-inside text-slate-300 space-y-0.5 text-[11px]">
                    {personaSeleccionada.detalles_campos.grouping.reasons.map((r: string, idx: number) => (
                      <li key={idx}>{r}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Desglose por campo */}
              <div className="space-y-3 max-h-72 overflow-y-auto pr-1">
                <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider">Desglose de Confianza por Campo</h3>
                {["identificacion", "nombres", "apellidos", "fecha_nacimiento", "fecha_expedicion", "lugar_expedicion", "sexo"].map((campoKey) => {
                  const detalle = personaSeleccionada.detalles_campos?.[campoKey] as any;
                  const val = (personaSeleccionada as any)[campoKey] || detalle?.value || null;
                  const confPct = Math.round((detalle?.confidence || (personaSeleccionada.confianza_extraccion ? Number(personaSeleccionada.confianza_extraccion) / 100 : 0.85)) * 100);
                  const status = val ? "valid" : "review_required";

                  return (
                    <div key={campoKey} className="p-3 rounded-xl bg-slate-950/50 border border-slate-800/80 space-y-2">
                      <div className="flex items-center justify-between">
                        <div>
                          <span className="text-[11px] font-bold text-slate-400 uppercase">{campoKey.replace("_", " ")}</span>
                          <div className="text-xs font-semibold text-slate-100 mt-0.5">
                            {val || <span className="text-amber-400 italic">No detectado</span>}
                          </div>
                        </div>

                        <div className="flex items-center gap-3">
                          <span className={`px-2 py-0.5 text-[10px] font-bold rounded-md ${
                            status === "valid" ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30" : "bg-amber-500/20 text-amber-400 border border-amber-500/30"
                          }`}>
                            {status === "valid" ? `${confPct}% VALID` : "REVISAR"}
                          </span>
                        </div>
                      </div>

                      {/* Sección de Explicabilidad Evidencial y Geometría Espacial */}
                      {detalle?.spatial_relation && (
                        <div className="pt-2 border-t border-slate-800/60 text-[11px] space-y-1 bg-slate-900/60 p-2 rounded-lg mt-2">
                          <div className="flex items-center justify-between text-[10px] text-primary-400 font-bold uppercase">
                            <span>Geometría Espacial ({detalle.spatial_relation})</span>
                            <span>Score: {Math.round((detalle.spatial_score || 1.0) * 100)}%</span>
                          </div>
                          <p className="text-slate-300 text-[11px] font-medium">{detalle.reason || "Validado espacialmente"}</p>
                          {detalle.label_bbox && (
                            <div className="text-[10px] text-slate-500 font-mono flex gap-3">
                              <span>Label BBox: x:{detalle.label_bbox.x}, y:{detalle.label_bbox.y}</span>
                              {detalle.value_bbox && <span>Valor BBox: x:{detalle.value_bbox.x}, y:{detalle.value_bbox.y}</span>}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>

              <div className="pt-2 flex justify-end">
                <button
                  onClick={() => setPersonaSeleccionada(null)}
                  className="px-5 py-2.5 bg-slate-800 hover:bg-slate-700 text-white font-medium text-xs rounded-xl transition-all"
                >
                  Cerrar Inspección
                </button>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
