"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ClipboardList,
  ExternalLink,
  FileSpreadsheet,
  Mail,
  RefreshCw,
  Settings,
  Trash2,
  Info,
} from "lucide-react";
import Sidebar from "@/components/ui/Sidebar";
import { useSidebar } from "@/context/SidebarContext";
import { apiSeguimiento, getErrorMessage } from "@/lib/api";
import { auth } from "@/lib/auth";
import type { SeguimientoConfig } from "@/types";
import toast from "react-hot-toast";

const TARJETA =
  "relative rounded-2xl bg-white/70 dark:bg-[#121620]/60 backdrop-blur-xl border border-slate-200/80 dark:border-white/[0.08] shadow-[0_2px_12px_rgba(0,0,0,0.03)] overflow-hidden";
const CAMPO =
  "w-full bg-slate-100/80 dark:bg-white/[0.04] border border-slate-200/80 dark:border-white/[0.08] rounded-xl px-3.5 py-2.5 text-sm text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-[#0071E3]/20 focus:border-[#0071E3] transition-all";

export default function SeguimientoPage() {
  const router = useRouter();
  const { collapsed } = useSidebar();
  const [config, setConfig] = useState<SeguimientoConfig | null>(null);
  const [cargando, setCargando] = useState(true);
  const [editando, setEditando] = useState(false);
  const [guardando, setGuardando] = useState(false);
  const [recarga, setRecarga] = useState(0);

  const [urlPanel, setUrlPanel] = useState("");
  const [correo, setCorreo] = useState("");
  const [urlHoja, setUrlHoja] = useState("");

  useEffect(() => {
    if (!auth.isAuthenticated()) {
      router.push("/");
      return;
    }
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
    if (!window.confirm("¿Quitar el enlace del panel de seguimiento de tu cuenta?")) return;
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

  return (
    <div className="flex min-h-screen">
      <Sidebar />

      <main className={`${collapsed ? "ml-20" : "ml-64"} transition-all duration-300 ease-in-out flex-1 p-8 min-w-0 flex flex-col`}>
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6 page-enter">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <ClipboardList className="w-5 h-5 text-primary-400" />
              <span className="text-primary-400 text-sm font-medium">Google Apps Script</span>
            </div>
            <h1 className="text-3xl font-bold text-white">Seguimiento de fichas</h1>
            <p className="text-slate-400 mt-1 text-sm">
              Panel de seguimiento conectado a tu Google Drive, guardado en tu cuenta de KondID.
            </p>
          </div>

          {config && !editando && (
            <div className="flex flex-wrap items-center gap-3">
              {config.correo_google && (
                <span className="inline-flex items-center gap-1.5 text-xs text-slate-500 dark:text-slate-400 px-3 py-2 rounded-xl bg-slate-100/80 dark:bg-white/[0.04] border border-slate-200/80 dark:border-white/[0.08]">
                  <Mail className="w-3.5 h-3.5" />
                  {config.correo_google}
                </span>
              )}
              <button onClick={() => setRecarga((n) => n + 1)} className="btn-secondary text-sm py-2.5 px-4" title="Recargar panel">
                <RefreshCw className="w-4 h-4" />
                <span>Recargar</span>
              </button>
              <a href={config.url_panel} target="_blank" rel="noopener noreferrer" className="btn-secondary text-sm py-2.5 px-4">
                <ExternalLink className="w-4 h-4" />
                <span>Abrir en pestaña nueva</span>
              </a>
              {config.url_hoja && (
                <a href={config.url_hoja} target="_blank" rel="noopener noreferrer" className="btn-secondary text-sm py-2.5 px-4">
                  <FileSpreadsheet className="w-4 h-4" />
                  <span>Abrir hoja</span>
                </a>
              )}
              <button onClick={abrirFormulario} className="btn-primary text-sm py-2.5 px-4">
                <Settings className="w-4 h-4" />
                <span>Configurar</span>
              </button>
            </div>
          )}
        </div>

        {cargando ? (
          <div className="py-16 text-center text-slate-500">
            <div className="spinner mx-auto mb-3" />
            <p className="text-xs">Cargando seguimiento de fichas...</p>
          </div>
        ) : editando ? (
          <div className={`${TARJETA} p-6 max-w-2xl`}>
            <div className="absolute inset-x-0 top-0 h-[1px] bg-gradient-to-r from-transparent via-slate-300/40 dark:via-white/10 to-transparent pointer-events-none" />
            <h2 className="text-base font-semibold text-slate-900 dark:text-white">Conectar tu panel de seguimiento</h2>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5 mb-5">
              Se guarda solo en tu usuario. Cada persona que inicie sesión puede conectar su propio panel.
            </p>

            <form onSubmit={guardar} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-600 dark:text-slate-300 mb-1.5">
                  Correo de Google <span className="text-slate-400 font-normal">(opcional)</span>
                </label>
                <input
                  type="email"
                  value={correo}
                  onChange={(e) => setCorreo(e.target.value)}
                  placeholder="tucorreo@gmail.com"
                  className={CAMPO}
                />
                <p className="text-[11px] text-slate-400 mt-1">
                  La cuenta con la que creaste la hoja «BD Seguimiento de Fichas». KondID nunca pide ni guarda tu contraseña de Google.
                </p>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-600 dark:text-slate-300 mb-1.5">
                  Enlace del panel (aplicación web) <span className="text-red-400">*</span>
                </label>
                <input
                  type="url"
                  required
                  value={urlPanel}
                  onChange={(e) => setUrlPanel(e.target.value)}
                  placeholder="https://script.google.com/macros/s/.../exec"
                  className={CAMPO}
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-600 dark:text-slate-300 mb-1.5">
                  Enlace de la hoja de cálculo <span className="text-slate-400 font-normal">(opcional)</span>
                </label>
                <input
                  type="url"
                  value={urlHoja}
                  onChange={(e) => setUrlHoja(e.target.value)}
                  placeholder="https://docs.google.com/spreadsheets/d/..."
                  className={CAMPO}
                />
              </div>

              <div className="flex items-start gap-2 text-xs text-slate-500 dark:text-slate-400 rounded-xl bg-slate-100/80 dark:bg-white/[0.04] border border-slate-200/80 dark:border-white/[0.08] p-3">
                <Info className="w-4 h-4 shrink-0 mt-0.5 text-primary-400" />
                <span>
                  En Apps Script: <b>Implementar → Gestionar implementaciones</b> y copia la <b>URL de la aplicación web</b> (termina en <code>/exec</code>).
                </span>
              </div>

              <div className="flex flex-wrap items-center gap-3 pt-1">
                <button type="submit" disabled={guardando} className="btn-primary text-sm py-2.5 px-5">
                  {guardando ? "Guardando..." : "Guardar"}
                </button>
                {config && (
                  <>
                    <button type="button" onClick={() => setEditando(false)} className="btn-secondary text-sm py-2.5 px-4">
                      Cancelar
                    </button>
                    <button type="button" onClick={quitar} className="btn-secondary text-sm py-2.5 px-4 text-red-500 ml-auto">
                      <Trash2 className="w-4 h-4" />
                      <span>Quitar conexión</span>
                    </button>
                  </>
                )}
              </div>
            </form>
          </div>
        ) : config ? (
          <div className="flex-1 flex flex-col min-h-0">
            <div className={`${TARJETA} flex-1 min-h-[70vh]`}>
              <iframe
                key={recarga}
                src={config.url_panel}
                title="Seguimiento de fichas"
                className="w-full h-full min-h-[70vh] border-0 bg-white"
                sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-popups-to-escape-sandbox allow-downloads allow-top-navigation-by-user-activation"
              />
            </div>
            <p className="text-[11px] text-slate-400 mt-2">
              ¿El panel sale en blanco o pide iniciar sesión con Google? Usa «Abrir en pestaña nueva».
            </p>
          </div>
        ) : null}
      </main>
    </div>
  );
}
