"use client";

import { useState, useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import toast from "react-hot-toast";
import {
  Users, Search, AlertTriangle, CheckCircle,
  Edit3, Save, X, RefreshCw, Trash2, Calendar, MapPin,
  ShieldCheck, UserCheck, FileText, Eye, ChevronLeft, ChevronRight,
  ZoomIn, ZoomOut, RotateCw, ImageOff, Hash, Clock, Cpu
} from "lucide-react";
import Sidebar from "@/components/ui/Sidebar";
import { apiPersonas, apiDocumentos } from "@/lib/api";
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
  const [paginaVistaPrevia, setPaginaVistaPrevia] = useState<number>(1);
  const [imagenCargando, setImagenCargando] = useState(false);
  const [imagenError, setImagenError] = useState(false);
  const [zoom, setZoom] = useState(1);

  const abrirVistaPrevia = (p: Persona) => {
    setPersonaSeleccionada(p);
    const paginaInicial = p.pagina_frente || p.pagina_numero || 1;
    setPaginaVistaPrevia(paginaInicial);
    setImagenCargando(true);
    setImagenError(false);
    setZoom(1);
  };

  const cerrarVistaPrevia = () => {
    setPersonaSeleccionada(null);
    setImagenError(false);
    setZoom(1);
  };

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
                                  onClick={() => abrirVistaPrevia(p)}
                                  title="Ver documento y datos extraídos"
                                  className="p-1.5 rounded-lg text-primary-400 hover:bg-primary-500/10 transition-colors"
                                >
                                  <Eye className="w-4 h-4" />
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

        {/* ─── Modal de Vista Previa PDF + Datos OCR ─── */}
        {personaSeleccionada && (() => {
          const p = personaSeleccionada;
          const estadoStr = p.estado_registro || (p.requiere_revision ? "REVIEW_REQUIRED" : "VALID");
          const docId = p.documento_id ? String(p.documento_id) : null;
          const tieneFrenteYReverso = p.pagina_frente && p.pagina_reverso;

          const campos = [
            { key: "numero_identificacion", label: "Número de Cédula", icono: <Hash className="w-3.5 h-3.5" />, valor: p.numero_identificacion },
            { key: "nombres", label: "Nombres", icono: <UserCheck className="w-3.5 h-3.5" />, valor: p.nombres },
            { key: "apellidos", label: "Apellidos", icono: <UserCheck className="w-3.5 h-3.5" />, valor: p.apellidos },
            { key: "fecha_nacimiento", label: "Fecha de Nacimiento", icono: <Calendar className="w-3.5 h-3.5" />, valor: p.fecha_nacimiento ? String(p.fecha_nacimiento) : null },
            { key: "fecha_expedicion", label: "Fecha de Expedición", icono: <Calendar className="w-3.5 h-3.5" />, valor: p.fecha_expedicion ? String(p.fecha_expedicion) : null },
            { key: "lugar_expedicion", label: "Lugar de Expedición", icono: <MapPin className="w-3.5 h-3.5" />, valor: p.lugar_expedicion },
            { key: "sexo", label: "Sexo", icono: <Users className="w-3.5 h-3.5" />, valor: p.sexo },
          ];

          const getConfianzaCampo = (campoKey: string): number => {
            const detalle = p.detalles_campos?.[campoKey] as any;
            if (detalle?.confidence != null) return Math.round(detalle.confidence * 100);
            return p.confianza_extraccion != null ? Math.round(Number(p.confianza_extraccion)) : 85;
          };

          const getColorConfianza = (conf: number) => {
            if (conf >= 85) return { bar: "from-emerald-500 to-emerald-400", text: "text-emerald-400", badge: "bg-emerald-500/15 border-emerald-500/30 text-emerald-400" };
            if (conf >= 65) return { bar: "from-amber-500 to-yellow-400", text: "text-amber-400", badge: "bg-amber-500/15 border-amber-500/30 text-amber-400" };
            return { bar: "from-rose-500 to-red-400", text: "text-rose-400", badge: "bg-rose-500/15 border-rose-500/30 text-rose-400" };
          };

          return (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/90 backdrop-blur-md animate-fadeIn p-4">
              <div className="bg-slate-900 border border-slate-800/80 rounded-2xl w-full max-w-6xl max-h-[92vh] flex flex-col shadow-2xl overflow-hidden">

                {/* Header del modal */}
                <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800/80 bg-slate-950/60 flex-shrink-0">
                  <div className="flex items-center gap-3">
                    <div className="p-2 rounded-xl bg-primary-500/10 border border-primary-500/20">
                      <FileText className="w-5 h-5 text-primary-400" />
                    </div>
                    <div>
                      <div className="text-xs font-semibold text-primary-400 uppercase tracking-wider">Documento OCR</div>
                      <h2 className="text-lg font-bold text-white">
                        Cédula <span className="font-mono text-primary-300">{p.numero_identificacion}</span>
                        {(p.nombres || p.apellidos) && (
                          <span className="text-slate-400 font-normal text-base ml-2">— {[p.nombres, p.apellidos].filter(Boolean).join(" ")}</span>
                        )}
                      </h2>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {estadoStr === "VALID" ? (
                      <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-semibold">
                        <CheckCircle className="w-3.5 h-3.5" /> VÁLIDO
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-amber-500/10 border border-amber-500/20 text-amber-400 text-xs font-semibold">
                        <AlertTriangle className="w-3.5 h-3.5" /> REVISAR
                      </span>
                    )}
                    <button onClick={cerrarVistaPrevia} className="p-2 rounded-xl text-slate-400 hover:text-white hover:bg-slate-800 transition-colors ml-2">
                      <X className="w-5 h-5" />
                    </button>
                  </div>
                </div>

                {/* Cuerpo split */}
                <div className="flex flex-col lg:flex-row flex-1 min-h-0 overflow-hidden">

                  {/* ─── Panel Izquierdo: Vista previa PDF ─── */}
                  <div className="lg:w-[52%] flex flex-col border-b lg:border-b-0 lg:border-r border-slate-800/60 bg-slate-950/40 min-h-[300px] lg:min-h-0">

                    {/* Barra de controles PDF */}
                    <div className="flex items-center justify-between gap-2 px-4 py-2.5 border-b border-slate-800/60 bg-slate-900/80 flex-shrink-0">
                      <div className="flex items-center gap-1.5">
                        {tieneFrenteYReverso && (
                          <>
                            <button
                              onClick={() => { setPaginaVistaPrevia(p.pagina_frente!); setImagenCargando(true); setImagenError(false); }}
                              className={`px-3 py-1 rounded-lg text-xs font-semibold transition-all ${paginaVistaPrevia === p.pagina_frente ? "bg-primary-500/20 border border-primary-500/40 text-primary-300" : "bg-slate-800 border border-slate-700 text-slate-400 hover:text-white"}`}
                            >
                              Frente (pág. {p.pagina_frente})
                            </button>
                            <button
                              onClick={() => { setPaginaVistaPrevia(p.pagina_reverso!); setImagenCargando(true); setImagenError(false); }}
                              className={`px-3 py-1 rounded-lg text-xs font-semibold transition-all ${paginaVistaPrevia === p.pagina_reverso ? "bg-primary-500/20 border border-primary-500/40 text-primary-300" : "bg-slate-800 border border-slate-700 text-slate-400 hover:text-white"}`}
                            >
                              Reverso (pág. {p.pagina_reverso})
                            </button>
                          </>
                        )}
                        {!tieneFrenteYReverso && (
                          <span className="text-xs text-slate-400">
                            Página <span className="font-mono text-white font-bold">{paginaVistaPrevia}</span>
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-1">
                        <button onClick={() => setZoom(z => Math.max(0.5, z - 0.25))} className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors" title="Alejar">
                          <ZoomOut className="w-3.5 h-3.5" />
                        </button>
                        <span className="text-xs text-slate-500 font-mono w-10 text-center">{Math.round(zoom * 100)}%</span>
                        <button onClick={() => setZoom(z => Math.min(3, z + 0.25))} className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors" title="Acercar">
                          <ZoomIn className="w-3.5 h-3.5" />
                        </button>
                        <button onClick={() => setZoom(1)} className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors" title="Restablecer zoom">
                          <RotateCw className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>

                    {/* Área de imagen */}
                    <div className="flex-1 overflow-auto flex items-start justify-center p-4 min-h-0">
                      {!docId ? (
                        <div className="flex flex-col items-center justify-center gap-3 text-slate-500 h-full">
                          <ImageOff className="w-12 h-12 text-slate-700" />
                          <p className="text-sm font-medium text-slate-400">Sin documento asociado</p>
                          <p className="text-xs text-slate-600 text-center max-w-xs">Esta persona no tiene un documento PDF vinculado en el sistema.</p>
                        </div>
                      ) : imagenError ? (
                        <div className="flex flex-col items-center justify-center gap-3 text-slate-500 h-full">
                          <ImageOff className="w-12 h-12 text-slate-700" />
                          <p className="text-sm font-medium text-slate-400">Archivo no disponible</p>
                          <p className="text-xs text-slate-600 text-center max-w-xs">El archivo PDF original no está disponible en el servidor.</p>
                        </div>
                      ) : (
                        <div className="relative" style={{ transform: `scale(${zoom})`, transformOrigin: "top center", transition: "transform 0.2s ease" }}>
                          {imagenCargando && (
                            <div className="absolute inset-0 flex items-center justify-center bg-slate-900/80 z-10 rounded-xl">
                              <div className="flex flex-col items-center gap-3">
                                <div className="w-8 h-8 border-2 border-slate-700 border-t-primary-400 rounded-full animate-spin" />
                                <span className="text-xs text-slate-400">Cargando página {paginaVistaPrevia}…</span>
                              </div>
                            </div>
                          )}
                          {/* eslint-disable-next-line @next/next/no-img-element */}
                          <img
                            key={`${docId}-${paginaVistaPrevia}`}
                            src={apiDocumentos.paginaPdfUrl(docId, paginaVistaPrevia, 150)}
                            alt={`Página ${paginaVistaPrevia} del documento`}
                            className="rounded-xl shadow-2xl max-w-full border border-slate-700/40"
                            style={{ display: imagenCargando ? "none" : "block" }}
                            onLoad={() => setImagenCargando(false)}
                            onError={() => { setImagenCargando(false); setImagenError(true); }}
                          />
                        </div>
                      )}
                    </div>
                  </div>

                  {/* ─── Panel Derecho: Datos OCR ─── */}
                  <div className="lg:w-[48%] flex flex-col overflow-hidden">

                    {/* Info del documento fuente */}
                    <div className="px-5 py-3 border-b border-slate-800/60 bg-slate-900/60 flex-shrink-0">
                      <div className="grid grid-cols-3 gap-2 text-[11px]">
                        <div className="flex flex-col gap-0.5">
                          <span className="text-slate-500 font-medium uppercase tracking-wider">Documento</span>
                          <span className="text-slate-300 font-mono truncate" title={p.grupo_documento_id || "—"}>
                            {p.grupo_documento_id ? p.grupo_documento_id.slice(0, 12) + "…" : "—"}
                          </span>
                        </div>
                        <div className="flex flex-col gap-0.5">
                          <span className="text-slate-500 font-medium uppercase tracking-wider flex items-center gap-1"><Cpu className="w-3 h-3" /> Motor</span>
                          <span className="text-emerald-400 font-mono">{p.motor_ocr || "doc_ai"}</span>
                        </div>
                        <div className="flex flex-col gap-0.5">
                          <span className="text-slate-500 font-medium uppercase tracking-wider flex items-center gap-1"><Clock className="w-3 h-3" /> Registrado</span>
                          <span className="text-slate-300 font-mono">{p.fecha_registro ? new Date(p.fecha_registro).toLocaleDateString("es-CO") : "—"}</span>
                        </div>
                      </div>
                    </div>

                    {/* Lista de campos con confianza */}
                    <div className="flex-1 overflow-y-auto px-5 py-4 space-y-2.5">
                      <h3 className="text-[11px] font-bold text-slate-400 uppercase tracking-widest mb-3">Datos Extraídos por OCR</h3>

                      {campos.map(({ key, label, icono, valor }) => {
                        const conf = getConfianzaCampo(key);
                        const colores = getColorConfianza(valor ? conf : 0);
                        const detalle = p.detalles_campos?.[key] as any;

                        return (
                          <div key={key} className="rounded-xl bg-slate-950/60 border border-slate-800/70 overflow-hidden hover:border-slate-700 transition-colors">
                            {/* Cabecera del campo */}
                            <div className="flex items-center justify-between px-4 pt-3 pb-1.5">
                              <div className="flex items-center gap-2 text-slate-400">
                                {icono}
                                <span className="text-[11px] font-bold uppercase tracking-wider">{label}</span>
                              </div>
                              <div className={`flex items-center gap-1.5 px-2 py-0.5 rounded-md border text-[10px] font-bold ${valor ? colores.badge : "bg-rose-500/10 border-rose-500/20 text-rose-400"}`}>
                                {valor ? (
                                  <>
                                    <div className="w-1.5 h-1.5 rounded-full bg-current" />
                                    {conf}%
                                  </>
                                ) : (
                                  <>
                                    <AlertTriangle className="w-3 h-3" />
                                    No detectado
                                  </>
                                )}
                              </div>
                            </div>

                            {/* Valor extraído */}
                            <div className="px-4 pb-2">
                              {valor ? (
                                <span className="text-sm font-semibold text-white">{valor}</span>
                              ) : (
                                <span className="text-xs italic text-slate-600">Sin datos — requiere revisión manual</span>
                              )}
                            </div>

                            {/* Barra de confianza */}
                            {valor && (
                              <div className="px-4 pb-3">
                                <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
                                  <div
                                    className={`h-full bg-gradient-to-r ${colores.bar} rounded-full transition-all duration-700`}
                                    style={{ width: `${conf}%` }}
                                  />
                                </div>
                              </div>
                            )}

                            {/* Detalle espacial si existe */}
                            {detalle?.spatial_relation && (
                              <div className="px-4 pb-3 pt-1 border-t border-slate-800/50">
                                <p className="text-[10px] text-slate-500 font-mono">
                                  Relación espacial: <span className="text-primary-400">{detalle.spatial_relation}</span>
                                  {detalle.spatial_score != null && <span className="ml-2 text-slate-600">score {Math.round(detalle.spatial_score * 100)}%</span>}
                                </p>
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>

                    {/* Footer con acciones */}
                    <div className="px-5 py-4 border-t border-slate-800/60 bg-slate-950/60 flex items-center justify-between flex-shrink-0">
                      <button
                        onClick={() => { cerrarVistaPrevia(); iniciarEdicion(p); }}
                        className="flex items-center gap-2 px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700/60 text-slate-200 text-xs font-semibold transition-all"
                      >
                        <Edit3 className="w-3.5 h-3.5" /> Editar Datos
                      </button>
                      <button
                        onClick={cerrarVistaPrevia}
                        className="flex items-center gap-2 px-5 py-2 rounded-xl bg-primary-600/20 hover:bg-primary-600/30 border border-primary-500/30 text-primary-300 text-xs font-semibold transition-all"
                      >
                        <X className="w-3.5 h-3.5" /> Cerrar
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          );
        })()}
      </main>
    </div>
  );
}
