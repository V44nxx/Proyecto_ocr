"use client";

import { useState, useEffect, useRef } from "react";
import { usePathname, useRouter } from "next/navigation";
import toast from "react-hot-toast";
import {
  Users, Search, AlertTriangle, CheckCircle,
  Edit3, Save, X, RefreshCw, Trash2, Calendar, MapPin,
  UserCheck, FileText, Eye, EyeOff,
  ZoomIn, ZoomOut, RotateCw, ImageOff, Hash, Clock, Cpu,
  ChevronDown, ChevronUp
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

  // Acordeón: solo una fila expandida a la vez
  const [expandidoId, setExpandidoId] = useState<string | null>(null);
  const [paginaPrevia, setPaginaPrevia] = useState<number>(1);
  const [imgCargando, setImgCargando] = useState(false);
  const [imgError, setImgError] = useState(false);
  const [zoom, setZoom] = useState(1);

  useEffect(() => {
    if (!auth.isAuthenticated()) { router.push("/"); return; }
    cargarPersonas(true);
    const interval = setInterval(() => cargarPersonas(false), 4000);
    return () => clearInterval(interval);
  }, [pathname, soloRevision]);

  const cargarPersonas = async (mostrarSpinner = false, revOnly?: boolean) => {
    if (mostrarSpinner) setCargando(true);
    try {
      const { data } = await apiPersonas.listar({
        limit: 100,
        requiere_revision: (revOnly ?? soloRevision) || undefined,
        buscar: buscar || undefined,
      });
      const items = Array.isArray(data) ? data : ((data as any)?.items || []);
      setPersonas(items);
      if (mostrarSpinner) toast.success(`${items.length} persona(s) sincronizada(s)`);
    } catch (err) {
      console.error("Error al cargar personas:", err);
      if (mostrarSpinner) toast.error("Error al cargar la lista de personas");
    } finally {
      if (mostrarSpinner) setCargando(false);
    }
  };

  const toggleExpandir = (p: Persona) => {
    if (expandidoId === p.id) {
      setExpandidoId(null);
    } else {
      setExpandidoId(p.id);
      const paginaInicial = p.pagina_frente || p.pagina_numero || 1;
      setPaginaPrevia(paginaInicial);
      setImgCargando(true);
      setImgError(false);
      setZoom(1);
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
      if (expandidoId === id) setExpandidoId(null);
      cargarPersonas(true);
    } catch {
      toast.error("Error al eliminar registro");
    }
  };

  // Filtrado local por cédula, nombres o apellidos
  const personasFiltradas = (personas || []).filter((p) => {
    if (!p) return false;
    if (!buscar) return true;
    const q = buscar.toLowerCase().trim().replace(/[.\s]/g, "");
    const cedula = String(p.numero_identificacion || "").replace(/[.\s]/g, "");
    return (
      cedula.includes(q) ||
      String(p.nombres || "").toLowerCase().includes(q) ||
      String(p.apellidos || "").toLowerCase().includes(q)
    );
  });

  // ─── Panel de detalle inline (acordeón) ───────────────────────────────────
  const PanelDetalle = ({ p }: { p: Persona }) => {
    const docId = p.documento_id ? String(p.documento_id) : null;
    const tieneDosLados = !!(p.pagina_frente && p.pagina_reverso);

    const campos = [
      { key: "numero_identificacion", label: "Número de Cédula", icono: <Hash className="w-3 h-3" />, valor: p.numero_identificacion },
      { key: "nombres", label: "Nombres", icono: <UserCheck className="w-3 h-3" />, valor: p.nombres },
      { key: "apellidos", label: "Apellidos", icono: <UserCheck className="w-3 h-3" />, valor: p.apellidos },
      { key: "fecha_nacimiento", label: "F. Nacimiento", icono: <Calendar className="w-3 h-3" />, valor: p.fecha_nacimiento ? String(p.fecha_nacimiento) : null },
      { key: "fecha_expedicion", label: "F. Expedición", icono: <Calendar className="w-3 h-3" />, valor: p.fecha_expedicion ? String(p.fecha_expedicion) : null },
      { key: "lugar_expedicion", label: "Lugar Expedición", icono: <MapPin className="w-3 h-3" />, valor: p.lugar_expedicion },
      { key: "sexo", label: "Sexo", icono: <Users className="w-3 h-3" />, valor: p.sexo },
    ];

    const conf = (key: string): number => {
      const d = p.detalles_campos?.[key] as any;
      if (d?.confidence != null) return Math.round(d.confidence * 100);
      return p.confianza_extraccion != null ? Math.round(Number(p.confianza_extraccion)) : 85;
    };

    const color = (c: number) => {
      if (c >= 85) return { bar: "from-emerald-500 to-emerald-400", badge: "bg-emerald-500/15 border-emerald-500/30 text-emerald-400" };
      if (c >= 65) return { bar: "from-amber-500 to-yellow-400", badge: "bg-amber-500/15 border-amber-500/30 text-amber-400" };
      return { bar: "from-rose-500 to-red-400", badge: "bg-rose-500/15 border-rose-500/30 text-rose-400" };
    };

    return (
      <div className="flex flex-col lg:flex-row gap-0 bg-slate-950/70 border-t border-slate-800/60">

        {/* ── Panel izquierdo: PDF ── */}
        <div className="lg:w-[48%] flex flex-col border-b lg:border-b-0 lg:border-r border-slate-800/50 min-h-[280px]">
          {/* Toolbar PDF */}
          <div className="flex items-center justify-between px-4 py-2 bg-slate-900/70 border-b border-slate-800/40">
            <div className="flex items-center gap-1.5">
              <FileText className="w-3.5 h-3.5 text-primary-400" />
              <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Vista PDF</span>
              {tieneDosLados && (
                <div className="flex items-center gap-1 ml-2">
                  <button
                    onClick={() => { setPaginaPrevia(p.pagina_frente!); setImgCargando(true); setImgError(false); }}
                    className={`px-2 py-0.5 rounded text-[10px] font-bold transition-all ${paginaPrevia === p.pagina_frente ? "bg-primary-500/25 border border-primary-500/40 text-primary-300" : "bg-slate-800 border border-slate-700 text-slate-400 hover:text-white"}`}
                  >
                    Frente
                  </button>
                  <button
                    onClick={() => { setPaginaPrevia(p.pagina_reverso!); setImgCargando(true); setImgError(false); }}
                    className={`px-2 py-0.5 rounded text-[10px] font-bold transition-all ${paginaPrevia === p.pagina_reverso ? "bg-primary-500/25 border border-primary-500/40 text-primary-300" : "bg-slate-800 border border-slate-700 text-slate-400 hover:text-white"}`}
                  >
                    Reverso
                  </button>
                </div>
              )}
              {!tieneDosLados && (
                <span className="text-[10px] text-slate-600 ml-1">pág. {paginaPrevia}</span>
              )}
            </div>
            <div className="flex items-center gap-0.5">
              <button onClick={() => setZoom(z => Math.max(0.5, z - 0.25))} className="p-1 rounded text-slate-500 hover:text-white hover:bg-slate-800 transition-colors" title="Alejar"><ZoomOut className="w-3 h-3" /></button>
              <span className="text-[10px] font-mono text-slate-500 w-8 text-center">{Math.round(zoom * 100)}%</span>
              <button onClick={() => setZoom(z => Math.min(2.5, z + 0.25))} className="p-1 rounded text-slate-500 hover:text-white hover:bg-slate-800 transition-colors" title="Acercar"><ZoomIn className="w-3 h-3" /></button>
              <button onClick={() => setZoom(1)} className="p-1 rounded text-slate-500 hover:text-white hover:bg-slate-800 transition-colors" title="Restablecer"><RotateCw className="w-3 h-3" /></button>
            </div>
          </div>

          {/* Imagen */}
          <div className="flex-1 overflow-auto flex items-start justify-center p-3 bg-slate-950/50 min-h-[240px]">
            {!docId ? (
              <div className="flex flex-col items-center justify-center gap-2 h-full w-full py-8">
                <ImageOff className="w-8 h-8 text-slate-700" />
                <p className="text-xs text-slate-500">Sin documento PDF asociado</p>
              </div>
            ) : imgError ? (
              <div className="flex flex-col items-center justify-center gap-2 h-full w-full py-8">
                <ImageOff className="w-8 h-8 text-slate-700" />
                <p className="text-xs text-slate-500">Archivo PDF no disponible en el servidor</p>
              </div>
            ) : (
              <div style={{ transform: `scale(${zoom})`, transformOrigin: "top center", transition: "transform 0.2s ease" }}>
                {imgCargando && (
                  <div className="flex flex-col items-center gap-2 py-12 w-48">
                    <div className="w-6 h-6 border-2 border-slate-700 border-t-primary-400 rounded-full animate-spin" />
                    <span className="text-[11px] text-slate-500">Cargando página {paginaPrevia}…</span>
                  </div>
                )}
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  key={`${docId}-${paginaPrevia}`}
                  src={apiDocumentos.paginaPdfUrl(docId, paginaPrevia, 130)}
                  alt={`Página ${paginaPrevia}`}
                  className="rounded-lg shadow-xl max-w-full border border-slate-700/30"
                  style={{ display: imgCargando ? "none" : "block" }}
                  onLoad={() => setImgCargando(false)}
                  onError={() => { setImgCargando(false); setImgError(true); }}
                />
              </div>
            )}
          </div>
        </div>

        {/* ── Panel derecho: Datos OCR ── */}
        <div className="lg:w-[52%] flex flex-col">
          {/* Meta info */}
          <div className="px-4 py-2 border-b border-slate-800/40 bg-slate-900/50">
            <div className="flex items-center gap-4 text-[10px]">
              <span className="flex items-center gap-1 text-slate-500"><Cpu className="w-3 h-3" /> <span className="text-emerald-400 font-mono">{p.motor_ocr || "google_document_ai"}</span></span>
              <span className="flex items-center gap-1 text-slate-500"><Clock className="w-3 h-3" /> <span className="text-slate-400">{p.fecha_registro ? new Date(p.fecha_registro).toLocaleDateString("es-CO") : "—"}</span></span>
              {p.grupo_documento_id && <span className="font-mono text-slate-600 truncate max-w-[120px]">{p.grupo_documento_id.slice(0, 14)}…</span>}
            </div>
          </div>

          {/* Campos */}
          <div className="flex-1 overflow-y-auto p-3 grid grid-cols-1 sm:grid-cols-2 gap-2">
            {campos.map(({ key, label, icono, valor }) => {
              const c = conf(key);
              const col = color(valor ? c : 0);
              return (
                <div key={key} className="rounded-lg bg-slate-900/60 border border-slate-800/60 overflow-hidden hover:border-slate-700/80 transition-colors">
                  <div className="flex items-center justify-between px-3 pt-2 pb-1">
                    <div className="flex items-center gap-1.5 text-slate-500">
                      {icono}
                      <span className="text-[10px] font-bold uppercase tracking-wider">{label}</span>
                    </div>
                    <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold border ${valor ? col.badge : "bg-rose-500/10 border-rose-500/20 text-rose-400"}`}>
                      {valor ? `${c}%` : "N/D"}
                    </span>
                  </div>
                  <div className="px-3 pb-1.5">
                    {valor
                      ? <span className="text-xs font-semibold text-white">{valor}</span>
                      : <span className="text-[11px] italic text-slate-600">No detectado</span>
                    }
                  </div>
                  {valor && (
                    <div className="px-3 pb-2">
                      <div className="h-1 bg-slate-800 rounded-full overflow-hidden">
                        <div className={`h-full bg-gradient-to-r ${col.bar} rounded-full transition-all duration-700`} style={{ width: `${c}%` }} />
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {/* Acciones */}
          <div className="px-4 py-3 border-t border-slate-800/40 bg-slate-900/50 flex items-center gap-2">
            <button
              onClick={() => { setExpandidoId(null); iniciarEdicion(p); }}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700/60 text-slate-200 text-xs font-semibold transition-all"
            >
              <Edit3 className="w-3.5 h-3.5" /> Editar
            </button>
            <button
              onClick={() => setExpandidoId(null)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800/50 hover:bg-slate-800 border border-slate-700/40 text-slate-400 text-xs font-medium transition-all ml-auto"
            >
              <ChevronUp className="w-3.5 h-3.5" /> Colapsar
            </button>
          </div>
        </div>
      </div>
    );
  };

  // ─── Render ───────────────────────────────────────────────────────────────
  return (
    <div className="flex min-h-screen bg-[#0b0f19] text-slate-100 font-sans">
      <Sidebar />

      <main className="ml-64 flex-1 p-8 overflow-x-hidden">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
          <div>
            <div className="flex items-center gap-2 mb-1.5">
              <span className="p-1.5 rounded-lg bg-primary-500/10 border border-primary-500/20 text-primary-400">
                <Users className="w-4 h-4" />
              </span>
              <span className="text-xs font-semibold text-primary-400 uppercase tracking-wider">Base de Datos OCR</span>
            </div>
            <h1 className="text-3xl font-extrabold text-white tracking-tight">Personas Registradas</h1>
            <p className="text-slate-400 text-sm mt-1">
              Haz clic en el ícono <Eye className="inline w-3.5 h-3.5 text-primary-400 mx-1" /> para expandir el documento y los datos OCR de cada persona.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span className="px-4 py-2 rounded-xl bg-gradient-to-r from-primary-500/20 to-blue-500/20 border border-primary-500/30 text-sm font-semibold text-primary-300 shadow-lg shadow-primary-500/5">
              Total: <strong className="text-white font-extrabold text-base ml-1">{personas.length}</strong> {personas.length === 1 ? "persona" : "personas"}
            </span>
          </div>
        </div>

        {/* Tarjetas de Estadísticas / Conteo Rápido */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
          {/* Card 1: Total General */}
          <div className="bg-slate-900/80 border border-slate-800/80 rounded-2xl p-4 flex items-center justify-between backdrop-blur-md shadow-lg">
            <div>
              <p className="text-xs font-medium text-slate-400 uppercase tracking-wider">Total en Tabla</p>
              <div className="flex items-baseline gap-2 mt-1">
                <span className="text-2xl font-black text-white">{personas.length}</span>
                <span className="text-xs text-slate-500">registradas</span>
              </div>
            </div>
            <div className="w-12 h-12 rounded-xl bg-primary-500/15 border border-primary-500/30 flex items-center justify-center text-primary-400">
              <Users className="w-6 h-6" />
            </div>
          </div>

          {/* Card 2: Válidas */}
          <div className="bg-slate-900/80 border border-slate-800/80 rounded-2xl p-4 flex items-center justify-between backdrop-blur-md shadow-lg">
            <div>
              <p className="text-xs font-medium text-emerald-400/90 uppercase tracking-wider">Registros Válidos</p>
              <div className="flex items-baseline gap-2 mt-1">
                <span className="text-2xl font-black text-emerald-400">{personas.filter(p => !p.requiere_revision).length}</span>
                <span className="text-xs text-slate-500">completas</span>
              </div>
            </div>
            <div className="w-12 h-12 rounded-xl bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center text-emerald-400">
              <CheckCircle className="w-6 h-6" />
            </div>
          </div>

          {/* Card 3: Por Revisar */}
          <div className="bg-slate-900/80 border border-slate-800/80 rounded-2xl p-4 flex items-center justify-between backdrop-blur-md shadow-lg">
            <div>
              <p className="text-xs font-medium text-amber-400/90 uppercase tracking-wider">Por Revisar</p>
              <div className="flex items-baseline gap-2 mt-1">
                <span className="text-2xl font-black text-amber-400">{personas.filter(p => p.requiere_revision).length}</span>
                <span className="text-xs text-slate-500">incompletas</span>
              </div>
            </div>
            <div className="w-12 h-12 rounded-xl bg-amber-500/15 border border-amber-500/30 flex items-center justify-center text-amber-400">
              <AlertTriangle className="w-6 h-6" />
            </div>
          </div>
        </div>

        {/* Barra de Búsqueda y Filtros */}
        <div className="grid grid-cols-1 md:grid-cols-12 gap-4 mb-6">
          {/* Búsqueda unificada por cédula, nombres o apellidos */}
          <div className="md:col-span-8 relative">
            <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <input
              id="buscar-persona"
              type="text"
              inputMode="search"
              value={buscar}
              onChange={(e) => setBuscar(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && cargarPersonas(true)}
              placeholder="Buscar por número de cédula, nombres o apellidos..."
              className="w-full pl-10 pr-10 py-2.5 bg-slate-900/90 border border-slate-800 rounded-xl text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-primary-500/60 focus:ring-1 focus:ring-primary-500/50 transition-all shadow-sm font-mono sm:font-sans"
            />
            {buscar && (
              <button
                onClick={() => { setBuscar(""); cargarPersonas(true); }}
                className="absolute right-3 top-1/2 -translate-y-1/2 p-0.5 rounded text-slate-500 hover:text-white transition-colors"
                title="Limpiar búsqueda"
              >
                <X className="w-4 h-4" />
              </button>
            )}
          </div>

          <div className="md:col-span-3 flex items-center">
            <label className="flex items-center gap-2 cursor-pointer w-full py-2.5 px-3 bg-slate-900/90 border border-slate-800 rounded-xl hover:bg-slate-800/50 transition-colors">
              <input
                type="checkbox"
                checked={soloRevision}
                onChange={(e) => setSoloRevision(e.target.checked)}
                className="w-4 h-4 rounded border-slate-700 bg-slate-800 text-primary-500 focus:ring-primary-500/40"
              />
              <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
              <span className="text-xs font-medium text-slate-300">Solo revisión</span>
            </label>
          </div>

          <div className="md:col-span-1 flex justify-end">
            <button
              onClick={() => cargarPersonas(true)}
              className="w-full flex items-center justify-center gap-1.5 px-3 py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700/60 rounded-xl text-xs font-semibold transition-all"
              title="Recargar datos"
            >
              <RefreshCw className="w-3.5 h-3.5 text-primary-400" />
            </button>
          </div>
        </div>

        {/* Tabla */}
        <div className="bg-slate-900/80 border border-slate-800/80 rounded-2xl shadow-xl overflow-hidden backdrop-blur-md">
          {cargando ? (
            <div className="p-8 space-y-3">
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
                {buscar ? `Sin resultados para "${buscar}"` : "No hay personas registradas."}
              </p>
              {buscar && (
                <button onClick={() => setBuscar("")} className="mt-3 text-xs text-primary-400 hover:underline">
                  Limpiar búsqueda
                </button>
              )}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-slate-800/80 bg-slate-950/50 text-[11px] font-bold text-slate-400 uppercase tracking-wider">
                    <th className="py-3 px-3 w-10"></th>
                    <th className="py-3 px-4">Cédula</th>
                    <th className="py-3 px-4">Nombre Completo</th>
                    <th className="py-3 px-3 text-center">Pág.</th>
                    <th className="py-3 px-4 text-center">Confianza</th>
                    <th className="py-3 px-4 text-center">Estado</th>
                    <th className="py-3 px-4 text-right">Acciones</th>
                  </tr>
                </thead>

                <tbody>
                  {personasFiltradas.map((p) => {
                    const estadoStr = p.estado_registro || (p.requiere_revision ? "REVIEW_REQUIRED" : "VALID");
                    const isExpandida = expandidoId === p.id;
                    const nombreCompleto = [p.nombres, p.apellidos].filter(Boolean).join(" ");

                    return (
                      <>
                        {/* ── Fila principal ── */}
                        <tr
                          key={p.id}
                          className={`border-b border-slate-800/30 transition-colors cursor-pointer ${isExpandida ? "bg-slate-800/40 border-primary-500/20" : "hover:bg-slate-800/20"}`}
                          onClick={() => { if (editando !== p.id) toggleExpandir(p); }}
                        >
                          {editando === p.id ? (
                            <>
                              {/* Fila en modo edición */}
                              <td className="py-2 px-3">
                                <div className="w-7 h-7 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center text-slate-500">
                                  <Edit3 className="w-3.5 h-3.5" />
                                </div>
                              </td>
                              <td className="py-2 px-4 font-mono text-primary-400 font-bold text-sm whitespace-nowrap">
                                {p.numero_identificacion}
                              </td>
                              <td className="py-2 px-4" colSpan={2}>
                                <div className="flex gap-2">
                                  <input
                                    className="bg-slate-950 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-primary-500 w-32"
                                    placeholder="Nombres"
                                    value={editForm.nombres || ""}
                                    onChange={(e) => setEditForm({ ...editForm, nombres: e.target.value })}
                                    onClick={(e) => e.stopPropagation()}
                                  />
                                  <input
                                    className="bg-slate-950 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-primary-500 w-32"
                                    placeholder="Apellidos"
                                    value={editForm.apellidos || ""}
                                    onChange={(e) => setEditForm({ ...editForm, apellidos: e.target.value })}
                                    onClick={(e) => e.stopPropagation()}
                                  />
                                  <input
                                    className="bg-slate-950 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-primary-500 w-28"
                                    placeholder="F.Nac YYYY-MM-DD"
                                    value={editForm.fecha_nacimiento || ""}
                                    onChange={(e) => setEditForm({ ...editForm, fecha_nacimiento: e.target.value })}
                                    onClick={(e) => e.stopPropagation()}
                                  />
                                  <input
                                    className="bg-slate-950 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-primary-500 w-28"
                                    placeholder="F.Exp YYYY-MM-DD"
                                    value={editForm.fecha_expedicion || ""}
                                    onChange={(e) => setEditForm({ ...editForm, fecha_expedicion: e.target.value })}
                                    onClick={(e) => e.stopPropagation()}
                                  />
                                  <input
                                    className="bg-slate-950 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-primary-500 w-32"
                                    placeholder="Lugar Exp."
                                    value={editForm.lugar_expedicion || ""}
                                    onChange={(e) => setEditForm({ ...editForm, lugar_expedicion: e.target.value })}
                                    onClick={(e) => e.stopPropagation()}
                                  />
                                  <select
                                    className="bg-slate-950 border border-slate-700 rounded-lg px-2 py-1.5 text-xs text-white focus:outline-none focus:border-primary-500 w-24"
                                    value={editForm.sexo || ""}
                                    onChange={(e) => setEditForm({ ...editForm, sexo: e.target.value })}
                                    onClick={(e) => e.stopPropagation()}
                                  >
                                    <option value="">Sexo</option>
                                    <option value="MASCULINO">MASCULINO</option>
                                    <option value="FEMENINO">FEMENINO</option>
                                  </select>
                                </div>
                              </td>
                              <td colSpan={2} />
                              <td className="py-2 px-4 text-right whitespace-nowrap" onClick={(e) => e.stopPropagation()}>
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
                              {/* Fila normal — toggle expandir */}
                              <td className="py-3 px-3">
                                <div className={`w-7 h-7 rounded-full flex items-center justify-center transition-all ${isExpandida ? "bg-primary-500/20 border border-primary-500/40 text-primary-300" : "bg-slate-800/60 border border-slate-700/50 text-slate-400"}`}>
                                  {isExpandida ? <ChevronUp className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                                </div>
                              </td>

                              {/* Cédula destacada */}
                              <td className="py-3 px-4 whitespace-nowrap">
                                <span className="font-mono text-primary-300 font-bold text-sm tracking-wide">
                                  {p.numero_identificacion}
                                </span>
                              </td>

                              {/* Nombre completo */}
                              <td className="py-3 px-4 whitespace-nowrap">
                                {nombreCompleto ? (
                                  <div>
                                    <div className="text-sm font-semibold text-slate-100">{p.nombres}</div>
                                    <div className="text-xs text-slate-400 font-medium">{p.apellidos}</div>
                                  </div>
                                ) : (
                                  <span className="text-slate-600 italic text-xs">Sin nombre</span>
                                )}
                              </td>

                              {/* Página */}
                              <td className="py-3 px-3 text-center">
                                <span className="text-[11px] font-mono text-slate-500">
                                  {p.pagina_frente ? `${p.pagina_frente}${p.pagina_reverso ? `/${p.pagina_reverso}` : ""}` : (p.pagina_numero || 1)}
                                </span>
                              </td>

                              {/* Confianza */}
                              <td className="py-3 px-4 text-center">
                                {p.confianza_extraccion != null ? (
                                  <div className="flex items-center justify-center gap-1.5">
                                    <div className="w-10 h-1.5 bg-slate-800 rounded-full overflow-hidden">
                                      <div className="h-full bg-gradient-to-r from-blue-500 to-emerald-400 rounded-full" style={{ width: `${p.confianza_extraccion}%` }} />
                                    </div>
                                    <span className="text-xs text-slate-400">{Math.round(Number(p.confianza_extraccion))}%</span>
                                  </div>
                                ) : <span className="text-slate-600 text-xs">—</span>}
                              </td>

                              {/* Estado */}
                              <td className="py-3 px-4 text-center">
                                {estadoStr === "VALID" ? (
                                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-[10px] font-bold">
                                    <CheckCircle className="w-2.5 h-2.5" /> VÁLIDO
                                  </span>
                                ) : estadoStr === "FALLBACK_TESSERACT" ? (
                                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-amber-500/20 border border-amber-500/30 text-amber-300 text-[10px] font-bold">
                                    <AlertTriangle className="w-2.5 h-2.5" /> TESSERACT
                                  </span>
                                ) : (
                                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-amber-500/10 border border-amber-500/20 text-amber-400 text-[10px] font-bold">
                                    <AlertTriangle className="w-2.5 h-2.5" /> REVISAR
                                  </span>
                                )}
                              </td>

                              {/* Acciones */}
                              <td className="py-3 px-4 text-right whitespace-nowrap" onClick={(e) => e.stopPropagation()}>
                                <div className="flex items-center justify-end gap-1">
                                  <button onClick={() => iniciarEdicion(p)} title="Editar" className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors">
                                    <Edit3 className="w-3.5 h-3.5" />
                                  </button>
                                  <button onClick={() => eliminar(p.id, p.numero_identificacion)} title="Eliminar" className="p-1.5 rounded-lg text-slate-400 hover:text-rose-400 hover:bg-slate-800 transition-colors">
                                    <Trash2 className="w-3.5 h-3.5" />
                                  </button>
                                </div>
                              </td>
                            </>
                          )}
                        </tr>

                        {/* ── Fila expandida (acordeón) ── */}
                        {isExpandida && editando !== p.id && (
                          <tr key={`${p.id}-detalle`} className="border-b border-slate-800/40">
                            <td colSpan={7} className="p-0">
                              <div className="border-t border-primary-500/20 animate-slideDown">
                                <PanelDetalle p={p} />
                              </div>
                            </td>
                          </tr>
                        )}
                      </>
                    );
                  })}
                </tbody>
              </table>

              {/* Pie de Tabla con Conteo Detallado */}
              <div className="flex flex-col sm:flex-row items-center justify-between px-6 py-4 bg-slate-950/70 border-t border-slate-800/80 text-xs text-slate-400 gap-2">
                <div className="flex items-center gap-2">
                  <div className="p-1 rounded bg-primary-500/10 text-primary-400">
                    <Users className="w-4 h-4" />
                  </div>
                  <span>
                    Total en la tabla: <strong className="text-white font-bold text-sm">{personasFiltradas.length}</strong> {personasFiltradas.length === 1 ? "persona" : "personas"}
                    {buscar && (
                      <span className="text-slate-500 ml-1">
                        (filtradas de un total de <strong className="text-slate-300 font-semibold">{personas.length}</strong>)
                      </span>
                    )}
                  </span>
                </div>
                <div className="flex items-center gap-4 text-[11px] text-slate-500">
                  <span className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                    <strong className="text-slate-300 font-semibold">{personas.filter(p => !p.requiere_revision).length}</strong> Válidas
                  </span>
                  <span className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-amber-400" />
                    <strong className="text-slate-300 font-semibold">{personas.filter(p => p.requiere_revision).length}</strong> Por revisar
                  </span>
                </div>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
