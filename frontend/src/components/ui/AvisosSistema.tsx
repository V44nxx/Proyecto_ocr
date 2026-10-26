"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { usePathname } from "next/navigation";
import toast from "react-hot-toast";
import { Clock, RefreshCw, ServerOff, WifiLow, WifiOff, X } from "lucide-react";
import { apiSistema } from "@/lib/api";
import { auth } from "@/lib/auth";
import { conexion, useConexion } from "@/lib/estadoConexion";

/**
 * Avisos generales, en todas las pantallas:
 *  - sin conexión a internet, servidor sin responder (se reintenta solo) y conexión lenta;
 *  - versión distinta entre esta pestaña y el servidor (hay una actualización a medio instalar);
 *  - la sesión vence en pocos minutos.
 */

type Tono = "critico" | "advertencia" | "info";

interface Aviso {
  id: string;
  tono: Tono;
  icono: React.ReactNode;
  titulo: string;
  texto: string;
  accion?: { texto: string; onClick: () => void };
  cerrable?: boolean;
}

const TONOS: Record<Tono, string> = {
  critico:
    "bg-rose-50/95 text-rose-900 border-rose-200 dark:bg-[#2a0f14]/95 dark:text-rose-100 dark:border-rose-500/30",
  advertencia:
    "bg-amber-50/95 text-amber-900 border-amber-200 dark:bg-[#2a1f0a]/95 dark:text-amber-100 dark:border-amber-500/30",
  info: "bg-white/95 text-slate-800 border-slate-200 dark:bg-[#0f1726]/95 dark:text-slate-100 dark:border-[#0071E3]/40",
};

const REVISAR_SERVIDOR_MS = 15_000;
const REVISAR_VERSION_MS = 5 * 60_000;
const AVISAR_SESION_ANTES_MS = 5 * 60_000;
const VERSION_LOCAL = process.env.NEXT_PUBLIC_APP_VERSION || "";

/** -1, 0 o 1 según qué versión (MAJOR.MINOR.PATCH) es mayor */
function compararVersiones(a: string, b: string): number {
  const pa = a.split(".").map(Number);
  const pb = b.split(".").map(Number);
  for (let i = 0; i < 3; i++) {
    if ((pa[i] || 0) !== (pb[i] || 0)) return (pa[i] || 0) > (pb[i] || 0) ? 1 : -1;
  }
  return 0;
}

/** La red según el navegador (Chrome, Edge y Android; Safari y Firefox no la informan) */
function redLentaSegunNavegador(): boolean {
  const red = (navigator as Navigator & { connection?: { effectiveType?: string; rtt?: number } }).connection;
  if (!red) return false;
  return red.effectiveType === "slow-2g" || red.effectiveType === "2g" || (typeof red.rtt === "number" && red.rtt >= 1500);
}

export default function AvisosSistema() {
  const pathname = usePathname();
  const estado = useConexion();
  const [versionServidor, setVersionServidor] = useState<string | null>(null);
  const [minutosSesion, setMinutosSesion] = useState<number | null>(null);
  const [cerrados, setCerrados] = useState<Set<string>>(new Set());
  const anterior = useRef(estado);

  const cerrar = (id: string) => setCerrados((prev) => new Set(prev).add(id));

  const revisarServidor = useCallback(async () => {
    try {
      const { data } = await apiSistema.salud();
      if (data?.version) setVersionServidor(data.version);
    } catch {
      // El interceptor de la API ya anotó si fue falta de internet o el servidor
    }
  }, []);

  // Internet y calidad de la red, según el navegador
  useEffect(() => {
    conexion.sinInternet(!navigator.onLine);
    conexion.redSegunNavegador(redLentaSegunNavegador());
    const alDesconectar = () => conexion.sinInternet(true);
    const alConectar = () => {
      conexion.sinInternet(false);
      void revisarServidor();
    };
    const red = (navigator as Navigator & { connection?: EventTarget }).connection;
    const alCambiarRed = () => conexion.redSegunNavegador(redLentaSegunNavegador());
    window.addEventListener("offline", alDesconectar);
    window.addEventListener("online", alConectar);
    red?.addEventListener?.("change", alCambiarRed);
    return () => {
      window.removeEventListener("offline", alDesconectar);
      window.removeEventListener("online", alConectar);
      red?.removeEventListener?.("change", alCambiarRed);
    };
  }, [revisarServidor]);

  // Cuando algo se arregla, se dice una vez
  useEffect(() => {
    const antes = anterior.current;
    if (antes.sinInternet && !estado.sinInternet) toast.success("Volvió la conexión a internet", { id: "aviso-internet" });
    else if (antes.servidorCaido && !estado.servidorCaido) toast.success("El servidor de KondID volvió a responder", { id: "aviso-servidor" });
    if (!antes.lenta && estado.lenta) setCerrados((prev) => { const s = new Set(prev); s.delete("lenta"); return s; });
    anterior.current = estado;
  }, [estado]);

  // Servidor sin responder: se revisa solo cada 15 segundos hasta que vuelva
  useEffect(() => {
    if (!estado.servidorCaido || estado.sinInternet) return;
    const intervalo = setInterval(revisarServidor, REVISAR_SERVIDOR_MS);
    return () => clearInterval(intervalo);
  }, [estado.servidorCaido, estado.sinInternet, revisarServidor]);

  // Versión del servidor: al abrir, cada 5 minutos y al volver a la pestaña
  useEffect(() => {
    if (!VERSION_LOCAL) return;
    const primera = setTimeout(revisarServidor, 3000);
    const intervalo = setInterval(revisarServidor, REVISAR_VERSION_MS);
    const alVolver = () => { if (document.visibilityState === "visible") void revisarServidor(); };
    document.addEventListener("visibilitychange", alVolver);
    return () => {
      clearTimeout(primera);
      clearInterval(intervalo);
      document.removeEventListener("visibilitychange", alVolver);
    };
  }, [revisarServidor]);

  // Sesión por vencer (solo dentro del panel)
  useEffect(() => {
    const revisar = () => {
      const vence = auth.isAuthenticated() ? auth.vencimiento() : null;
      const restante = vence ? vence - Date.now() : null;
      setMinutosSesion(restante !== null && restante > 0 && restante <= AVISAR_SESION_ANTES_MS
        ? Math.max(1, Math.ceil(restante / 60_000)) : null);
    };
    revisar();
    const intervalo = setInterval(revisar, 30_000);
    return () => clearInterval(intervalo);
  }, [pathname]);

  const avisos: Aviso[] = [];
  if (estado.sinInternet) {
    avisos.push({
      id: "internet", tono: "critico", icono: <WifiOff className="w-4 h-4" />,
      titulo: "Sin conexión a internet",
      texto: "Revisa tu Wi-Fi o tus datos móviles. Lo que hagas ahora no se guardará hasta que vuelva la conexión.",
    });
  } else if (estado.servidorCaido) {
    avisos.push({
      id: "servidor", tono: "critico", icono: <ServerOff className="w-4 h-4" />,
      titulo: "El servidor de KondID no responde",
      texto: "Puede estar actualizándose. Se revisa solo cada 15 segundos; espera antes de volver a subir o guardar.",
      accion: { texto: "Reintentar", onClick: () => void revisarServidor() },
    });
  } else if (estado.lenta && !cerrados.has("lenta")) {
    avisos.push({
      id: "lenta", tono: "advertencia", icono: <WifiLow className="w-4 h-4" />,
      titulo: "Conexión lenta",
      texto: "Las pantallas y las subidas pueden tardar más de lo normal. Sube pocos archivos a la vez y no cierres la pestaña mientras suben.",
      cerrable: true,
    });
  }
  if (versionServidor && VERSION_LOCAL && versionServidor !== VERSION_LOCAL && !cerrados.has(`version-${versionServidor}`)) {
    const servidorMasNuevo = compararVersiones(versionServidor, VERSION_LOCAL) > 0;
    avisos.push({
      id: `version-${versionServidor}`, tono: "info", icono: <RefreshCw className="w-4 h-4" />,
      titulo: servidorMasNuevo ? `Hay una versión nueva de KondID (${versionServidor})` : "KondID se está actualizando",
      texto: servidorMasNuevo
        ? "Recarga la página para usarla. Si estás editando algo, guárdalo primero."
        : `Se está instalando la versión ${VERSION_LOCAL}: algunas funciones pueden fallar unos minutos. Si algo no responde, recarga la página.`,
      accion: { texto: "Recargar", onClick: () => window.location.reload() },
      cerrable: true,
    });
  }
  if (minutosSesion !== null && pathname !== "/" && !cerrados.has("sesion")) {
    avisos.push({
      id: "sesion", tono: "advertencia", icono: <Clock className="w-4 h-4" />,
      titulo: `Tu sesión vence en ${minutosSesion} ${minutosSesion === 1 ? "minuto" : "minutos"}`,
      texto: "Guarda lo que estés editando: después tendrás que volver a iniciar sesión.",
      cerrable: true,
    });
  }

  if (avisos.length === 0) return null;

  return (
    <div className="fixed top-3 left-1/2 -translate-x-1/2 z-[10000] w-[calc(100%-2rem)] max-w-xl space-y-2 pointer-events-none">
      {avisos.map((aviso) => (
        <div
          key={aviso.id}
          role={aviso.tono === "critico" ? "alert" : "status"}
          data-aviso={aviso.id.split("-")[0]}
          className={`pointer-events-auto flex items-start gap-3 px-4 py-3 rounded-2xl border shadow-lg backdrop-blur-md ${TONOS[aviso.tono]}`}
        >
          <span className="mt-0.5 shrink-0">{aviso.icono}</span>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold leading-snug">{aviso.titulo}</p>
            <p className="text-xs mt-0.5 leading-relaxed opacity-90">{aviso.texto}</p>
          </div>
          {aviso.accion && (
            <button
              type="button"
              onClick={aviso.accion.onClick}
              className="shrink-0 self-center text-xs font-semibold px-2.5 py-1.5 rounded-lg border border-black/10 dark:border-white/15 hover:bg-black/5 dark:hover:bg-white/10 transition-colors cursor-pointer"
            >
              {aviso.accion.texto}
            </button>
          )}
          {aviso.cerrable && (
            <button
              type="button"
              onClick={() => cerrar(aviso.id)}
              aria-label="Cerrar aviso"
              className="shrink-0 p-1 rounded-lg opacity-70 hover:opacity-100 hover:bg-black/5 dark:hover:bg-white/10 transition cursor-pointer"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      ))}
    </div>
  );
}
