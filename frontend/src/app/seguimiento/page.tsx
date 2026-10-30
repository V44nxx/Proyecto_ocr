"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ClipboardList,
  ExternalLink,
  FileSpreadsheet,
  Link2,
  Mail,
  RefreshCw,
  Settings,
  Trash2,
} from "lucide-react";
import Sidebar from "@/components/ui/Sidebar";
import EncabezadoPagina from "@/components/ui/EncabezadoPagina";
import { useSidebar } from "@/context/SidebarContext";
import { apiSeguimiento, getErrorMessage } from "@/lib/api";
import { auth } from "@/lib/auth";
import { useTheme } from "@/context/ThemeContext";
import { conTema, conUsuario, urlHojaSeguimiento, urlPanelSeguimiento } from "@/lib/urlsSeguimiento";
import type { SeguimientoConfig } from "@/types";
import toast from "react-hot-toast";
import { confirmar } from "@/lib/confirmar";

const TARJETA =
  "rounded-2xl bg-white/80 dark:bg-[#121620]/60 backdrop-blur-xl border border-slate-200/80 dark:border-white/8 shadow-[0_2px_12px_rgba(0,0,0,0.03)] dark:shadow-[0_4px_24px_rgba(0,0,0,0.25)]";
const CAJA = "p-3.5 rounded-xl bg-slate-50/70 dark:bg-white/3 border border-slate-200/70 dark:border-white/6 min-w-0";
const ETIQUETA = "block text-[11px] font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-1.5";
const CAMPO =
  "w-full bg-slate-50/80 dark:bg-white/4 border border-slate-200/80 dark:border-white/8 rounded-xl px-3.5 py-2.5 text-sm text-slate-900 dark:text-white placeholder:text-slate-400 dark:placeholder:text-slate-500 focus:outline-hidden focus:ring-2 focus:ring-[#0071E3]/20 focus:border-[#0071E3] transition-all";
const BOTON_SECUNDARIO =
  "px-4 py-2 rounded-xl text-xs font-semibold bg-white/80 dark:bg-white/6 hover:bg-slate-100 dark:hover:bg-white/10 text-slate-700 dark:text-slate-200 border border-slate-200/80 dark:border-white/8 transition-all shadow-xs disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer flex items-center gap-2";
const BOTON_PRIMARIO =
  "px-4 py-2 rounded-xl text-xs font-semibold bg-[#0071E3] hover:bg-[#0077ED] text-white transition-all shadow-xs shadow-[#0071E3]/20 disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer flex items-center gap-2";

const PASOS = [
  {
    titulo: "Pega el script",
    texto:
      "En la hoja «FORMACIONES COMPLEMENTARIAS GRUPOS» abre Extensiones → Apps Script y pega Codigo.gs e Index.html (carpeta apps-script/seguimiento-fichas del proyecto).",
  },
  { titulo: "Configúralo", texto: "Ejecuta la función «configurar» una vez: crea la clave del enlace y la actualización automática." },
  {
    titulo: "Publica el panel",
    texto:
      "Implementar → Nueva implementación → Aplicación web, ejecutar como «Yo» y acceso «Cualquier persona». Copia la URL (termina en /exec), agrégale ?k= y la clave, y pégala aquí.",
  },
];

export default function SeguimientoPage() {
  const router = useRouter();
  const { collapsed } = useSidebar();
  const [config, setConfig] = useState<SeguimientoConfig | null>(null);
  const [cargando, setCargando] = useState(true);
  const [editando, setEditando] = useState(false);
  const [guardando, setGuardando] = useState(false);
  const [recarga, setRecarga] = useState(0);
  const [nombreUsuario, setNombreUsuario] = useState("");
  // Solo se pintan enlaces de Apps Script y Google Sheets (lib/urlsSeguimiento.ts); el panel recibe quién está
  // conectado para anotarlo en su historial de cambios
  const panelSeguro = conUsuario(urlPanelSeguimiento(config?.url_panel), nombreUsuario);
  // El panel incrustado se pinta con el tema de KondID (al cambiarlo, el panel se vuelve a cargar)
  const { theme } = useTheme();
  const panelIncrustado = conTema(panelSeguro, theme);
  const hojaSegura = urlHojaSeguimiento(config?.url_hoja);

  const [urlPanel, setUrlPanel] = useState("");
  const [correo, setCorreo] = useState("");
  const [urlHoja, setUrlHoja] = useState("");

  useEffect(() => {
    if (!auth.isAuthenticated()) {
      router.push("/");
      return;
    }
    setNombreUsuario(auth.getUsuario()?.nombre || "");
    cargarConfig();
  }, []);

  const cargarConfig = async () => {
    setCargando(true);
    try {
      const res = await apiSeguimiento.obtenerConfig();
      setConfig(res.data);
      setEditando(!res.data);
    } catch (err: unknown) {
      toast.error(getErrorMessage(err, "No se pudo cargar la configuración del seguimiento"));
    } finally {
      setCargando(false);
    }
  };

  const abrirFormulario = () => {
    setUrlPanel(config?.url_panel || "");
    setCorreo(config?.correo_google || "");
    setUrlHoja(config?.url_hoja || "");
    setEditando(true);
  };

  const guardar = async (e: React.FormEvent) => {
    e.preventDefault();
    setGuardando(true);
    try {
      const res = await apiSeguimiento.guardarConfig({
        url_panel: urlPanel.trim(),
        correo_google: correo.trim(),
        url_hoja: urlHoja.trim(),
      });
      setConfig(res.data);
      setEditando(false);
      toast.success("Configuración guardada");
    } catch (err: unknown) {
      toast.error(getErrorMessage(err, "No se pudo guardar la configuración"));
    } finally {
      setGuardando(false);
    }
  };

  const quitar = async () => {
    if (!(await confirmar({ titulo: "¿Quitar el enlace del panel?", mensaje: "El panel de seguimiento deja de verse en tu cuenta. Puedes volver a agregarlo cuando quieras.",
      confirmar: "Quitar enlace", tema: "quitar-enlace", tono: "aviso" }))) return;
    try {
      await apiSeguimiento.eliminarConfig();
      setConfig(null);
      setUrlPanel("");
      setCorreo("");
      setUrlHoja("");
      toast.success("Configuración eliminada");
    } catch (err: unknown) {
      toast.error(getErrorMessage(err, "No se pudo eliminar la configuración"));
    }
  };

  const actualizado = config?.fecha_actualizacion
    ? new Date(config.fecha_actualizacion).toLocaleDateString("es-CO", { day: "numeric", month: "short", year: "numeric" })
    : null;

  return (
    <div className="flex min-h-screen">
      <Sidebar />

      <main
        className={`flex-1 min-w-0 p-4 sm:p-6 lg:p-8 transition-all duration-300 flex flex-col ${
          collapsed ? "ml-16 sm:ml-20" : "ml-64 sm:ml-72"
        }`}
      >
        <EncabezadoPagina
          icono={<ClipboardList />}
          seccion="Google Apps Script"
          titulo="Seguimiento de fichas"
          descripcion="Panel conectado a tu Google Drive, guardado en tu cuenta de KondID."
          acciones={
            config && !editando ? (
              <>
                <button onClick={() => setRecarga((n) => n + 1)} className={BOTON_SECUNDARIO} title="Recargar panel">
                  <RefreshCw className="w-3.5 h-3.5" />
                  <span>Recargar</span>
                </button>
                <a href={panelSeguro} target="_blank" rel="noopener noreferrer" className={BOTON_SECUNDARIO}>
                  <ExternalLink className="w-3.5 h-3.5" />
                  <span>Abrir en pestaña nueva</span>
                </a>
                <button onClick={abrirFormulario} className={BOTON_PRIMARIO}>
                  <Settings className="w-3.5 h-3.5" />
                  <span>Configurar</span>
                </button>
              </>
            ) : undefined
          }
        />

        {/* ─── Resumen de la conexión ─── */}
        {!cargando && (
          <div className={`${TARJETA} mb-6 p-4 sm:p-5`}>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div className={CAJA}>
                <span className="text-xs text-slate-500 dark:text-slate-400 font-medium block">Estado</span>
                <div className="mt-1.5 flex items-center gap-2 text-base font-bold text-slate-900 dark:text-white">
                  <span className={`w-2 h-2 rounded-full ${config ? "bg-emerald-500" : "bg-amber-500"}`} />
                  {config ? "Conectado" : "Sin conectar"}
                </div>
                <span className="text-[11px] text-slate-400 dark:text-slate-500 block mt-0.5">
                  {actualizado ? `Actualizado el ${actualizado}` : "Completa el formulario para empezar"}
                </span>
              </div>

              <div className={CAJA}>
                <span className="text-xs text-slate-500 dark:text-slate-400 font-medium flex items-center gap-1.5">
                  <Mail className="w-3.5 h-3.5" /> Cuenta de Google
                </span>
                <div className="mt-1.5 text-sm font-semibold text-slate-900 dark:text-white truncate" title={config?.correo_google || ""}>
                  {config?.correo_google || "Sin registrar"}
                </div>
                <span className="text-[11px] text-slate-400 dark:text-slate-500 block mt-0.5">Dueña de la hoja de seguimiento</span>
              </div>

              <div className={CAJA}>
                <span className="text-xs text-slate-500 dark:text-slate-400 font-medium flex items-center gap-1.5">
                  <FileSpreadsheet className="w-3.5 h-3.5" /> Hoja de cálculo
                </span>
                {hojaSegura ? (
                  <a
                    href={hojaSegura}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="mt-1.5 text-sm font-semibold text-[#0071E3] hover:underline inline-flex items-center gap-1"
                  >
                    Formaciones complementarias <ExternalLink className="w-3 h-3" />
                  </a>
                ) : (
                  <div className="mt-1.5 text-sm font-semibold text-slate-900 dark:text-white">Sin enlace</div>
                )}
                <span className="text-[11px] text-slate-400 dark:text-slate-500 block mt-0.5">Google Sheets</span>
              </div>
            </div>
          </div>
        )}

        {cargando ? (
          <div className="py-16 text-center text-slate-500">
            <div className="spinner mx-auto mb-3" />
            <p className="text-xs">Cargando seguimiento de fichas...</p>
          </div>
        ) : editando ? (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
            {/* ─── Formulario ─── */}
            <form onSubmit={guardar} className={`${TARJETA} lg:col-span-2`}>
              <div className="p-5 sm:p-6 border-b border-slate-200/80 dark:border-white/6">
                <h2 className="text-sm font-bold text-slate-900 dark:text-white tracking-wide">Conectar tu panel de seguimiento</h2>
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                  Se guarda solo en tu usuario. Cada persona que inicie sesión puede conectar su propio panel.
                </p>
              </div>

              <div className="p-5 sm:p-6 space-y-5">
                <div>
                  <label htmlFor="url-panel" className={ETIQUETA}>
                    Enlace del panel (aplicación web) <span className="text-red-500">*</span>
                  </label>
                  <div className="relative">
                    <Link2 className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                    <input
                      id="url-panel"
                      type="url"
                      required
                      value={urlPanel}
                      onChange={(e) => setUrlPanel(e.target.value)}
                      placeholder="https://script.google.com/macros/s/.../exec?k=..."
                      className={`${CAMPO} pl-10`}
                    />
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                  <div>
                    <label htmlFor="correo-google" className={ETIQUETA}>
                      Correo de Google <span className="normal-case font-normal tracking-normal text-slate-400">(opcional)</span>
                    </label>
                    <div className="relative">
                      <Mail className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                      <input
                        id="correo-google"
                        type="email"
                        value={correo}
                        onChange={(e) => setCorreo(e.target.value)}
                        placeholder="tucorreo@gmail.com"
                        className={`${CAMPO} pl-10`}
                      />
                    </div>
                  </div>

                  <div>
                    <label htmlFor="url-hoja" className={ETIQUETA}>
                      Hoja de cálculo <span className="normal-case font-normal tracking-normal text-slate-400">(opcional)</span>
                    </label>
                    <div className="relative">
                      <FileSpreadsheet className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                      <input
                        id="url-hoja"
                        type="url"
                        value={urlHoja}
                        onChange={(e) => setUrlHoja(e.target.value)}
                        placeholder="https://docs.google.com/spreadsheets/d/..."
                        className={`${CAMPO} pl-10`}
                      />
                    </div>
                  </div>
                </div>

                <p className="text-[11px] text-slate-400 dark:text-slate-500">
                  El correo es la cuenta con la que creaste la hoja. KondID nunca pide ni guarda tu contraseña de Google.
                </p>
              </div>

              <div className="px-5 sm:px-6 py-4 border-t border-slate-200/80 dark:border-white/6 flex flex-wrap items-center gap-2.5">
                {config && (
                  <button type="button" onClick={quitar} className={`${BOTON_SECUNDARIO} text-red-600 dark:text-red-400`}>
                    <Trash2 className="w-3.5 h-3.5" />
                    <span>Quitar conexión</span>
                  </button>
                )}
                <div className="flex items-center gap-2.5 ml-auto">
                  {config && (
                    <button type="button" onClick={() => setEditando(false)} className={BOTON_SECUNDARIO}>
                      Cancelar
                    </button>
                  )}
                  <button type="submit" disabled={guardando || !urlPanel.trim()} className={BOTON_PRIMARIO}>
                    {guardando ? "Guardando..." : "Guardar conexión"}
                  </button>
                </div>
              </div>
            </form>

            {/* ─── Cómo conectarlo ─── */}
            <div className={`${TARJETA} p-5 sm:p-6`}>
              <h2 className="text-sm font-bold text-slate-900 dark:text-white tracking-wide mb-4">Cómo obtener el enlace</h2>
              <ol className="space-y-4">
                {PASOS.map((paso, i) => (
                  <li key={paso.titulo} className="flex gap-3">
                    <span className="w-6 h-6 shrink-0 rounded-full flex items-center justify-center text-[11px] font-bold font-mono bg-[#0071E3]/10 text-[#0071E3] border border-[#0071E3]/20">
                      {i + 1}
                    </span>
                    <div className="min-w-0">
                      <p className="text-xs font-semibold text-slate-900 dark:text-white">{paso.titulo}</p>
                      <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5 leading-relaxed">{paso.texto}</p>
                    </div>
                  </li>
                ))}
              </ol>
            </div>
          </div>
        ) : config ? (
          <div className="flex-1 flex flex-col min-h-0">
            <div className={`${TARJETA} flex-1 min-h-[70vh] overflow-hidden`}>
              <iframe
                key={recarga}
                src={panelIncrustado}
                title="Seguimiento de fichas"
                className="w-full h-full min-h-[70vh] border-0 bg-[#f5f6f8] dark:bg-[#0b0e14]"
                sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-popups-to-escape-sandbox allow-downloads allow-top-navigation-by-user-activation"
              />
            </div>
            <p className="text-[11px] text-slate-400 dark:text-slate-500 mt-2">
              ¿El panel sale en blanco o pide iniciar sesión con Google? Usa «Abrir en pestaña nueva».
            </p>
          </div>
        ) : null}
      </main>
    </div>
  );
}
