"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import toast from "react-hot-toast";
import {
  FileText,
  Lock,
  Mail,
  Eye,
  EyeOff,
  ShieldCheck,
  ArrowRight,
  Sun,
  Moon,
  Fingerprint,
  CheckCircle2,
  ScanLine,
} from "lucide-react";
import { apiAuth, CLAVE_AVISO_LOGIN, getErrorMessage } from "@/lib/api";
import { auth } from "@/lib/auth";
import { useTheme } from "@/context/ThemeContext";
import LogoKondID from "@/components/ui/LogoKondID";
import VerificacionDosPasos from "@/components/ui/VerificacionDosPasos";
import type { LoginResponse, Usuario } from "@/types";
import IconoTema from "@/components/ui/IconoTema";
import FondoLogin from "@/components/ui/FondoLogin";

export default function LoginPage() {
  const router = useRouter();
  const { theme, toggleTheme } = useTheme();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mostrarPass, setMostrarPass] = useState(false);
  const [cargando, setCargando] = useState(false);
  const [ocultarDatosID, setOcultarDatosID] = useState(false);
  // Administradores: después de la contraseña, el código de la app (o vincularla la primera vez)
  const [segundoPaso, setSegundoPaso] = useState<{ desafio: string; configurar: boolean } | null>(null);
  // Avisos de esta pantalla: la sesión anterior se cerró, el navegador bloquea las cookies, Bloq Mayús activado
  const [sesionCerrada, setSesionCerrada] = useState(false);
  const [cookiesBloqueadas, setCookiesBloqueadas] = useState(false);
  const [mayusculas, setMayusculas] = useState(false);

  useEffect(() => {
    try {
      if (sessionStorage.getItem(CLAVE_AVISO_LOGIN)) {
        sessionStorage.removeItem(CLAVE_AVISO_LOGIN);
        setSesionCerrada(true);
      }
    } catch {}
    setCookiesBloqueadas(!navigator.cookieEnabled);
  }, []);

  const revisarMayusculas = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (typeof e.getModifierState === "function") setMayusculas(e.getModifierState("CapsLock"));
  };

  const entrar = (data: LoginResponse) => {
    const usuario = data.usuario as Usuario;
    auth.guardarSesion({ usuario, access_token: data.access_token });
    toast.success(`Bienvenido, ${usuario.nombre}`);
    window.location.href = "/dashboard";
  };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) {
      toast.error("Por favor completa todos los campos requeridos");
      return;
    }

    setCargando(true);
    try {
      const { data } = await apiAuth.login(email, password);
      if (data.requiere_2fa && data.desafio) {
        setPassword("");
        setSegundoPaso({ desafio: data.desafio, configurar: data.configurar_2fa });
        return;
      }
      entrar(data);
    } catch (err: unknown) {
      const error = err as {
        response?: { data?: { detail?: string }; status?: number };
        message?: string;
      };
      // Un solo aviso que se reemplaza en cada intento: así el último (por ejemplo, el de esperar) queda a la vista
      if (!error.response || (error.response.status ?? 0) >= 502) {
        toast.error(getErrorMessage(err), { id: "login-error" });
      } else {
        const mensaje = error.response?.data?.detail || "Credenciales incorrectas";
        toast.error(typeof mensaje === "string" ? mensaje : "Error de autenticación", { id: "login-error" });
      }
    } finally {
      setCargando(false);
    }
  };

  return (
    <div className={`h-screen max-h-screen min-h-screen login-bg isolate text-slate-900 dark:text-slate-100 flex flex-col justify-between overflow-y-auto ${segundoPaso ? "" : "lg:overflow-hidden"} selection:bg-[#0071E3]/20 selection:text-white`}>
      <FondoLogin />

      {/* ── BARRA SUPERIOR (Chrome translúcido compacto estilo Apple) ── */}
      <header className="w-full shrink-0 border-b border-black/4 dark:border-white/6 backdrop-blur-md bg-white/40 dark:bg-[#070A0F]/50 sticky top-0 z-30 transition-colors">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-12 flex items-center justify-between">
          {/* Marca / Logotipo */}
          <div className="flex items-center gap-2.5">
            <LogoKondID className="h-6" />
            <span className="hidden sm:inline-block text-[11px] text-slate-400 dark:text-slate-500 font-normal">
              / Document Intelligence
            </span>
          </div>

          {/* Telemetría & Acciones */}
          <div className="flex items-center gap-2 sm:gap-3">
            {/* Estado del motor OCR */}
            <div className="hidden sm:inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-slate-100/80 dark:bg-white/4 border border-slate-200/80 dark:border-white/[0.07] text-slate-600 dark:text-slate-400">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
              <span>Motor OCR • Operativo</span>
            </div>

            {/* Alternador de tema modo Claro / Oscuro */}
            <button
              type="button"
              onClick={toggleTheme}
              title={`Cambiar a modo ${theme === "dark" ? "claro" : "oscuro"}`}
              className="inline-flex items-center justify-center w-7 h-7 rounded-full bg-slate-100 dark:bg-white/6 border border-slate-200/80 dark:border-white/8 text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white active:scale-95 transition-all cursor-pointer"
            >
              {theme === "dark" ? (
                <Sun className="w-3.5 h-3.5 text-amber-400" />
              ) : (
                <Moon className="w-3.5 h-3.5 text-slate-600" />
              )}
            </button>
          </div>
        </div>
      </header>

      {/* ── CUERPO PRINCIPAL (Ajustado verticalmente para eliminar scroll en pantallas de escritorio) ── */}
      <main className="max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-3 sm:py-5 flex-1 flex items-center justify-center min-h-0">
        <div className="w-full grid grid-cols-1 lg:grid-cols-12 gap-6 lg:gap-10 items-center">
          
          {/* ── COLUMNA IZQUIERDA: Presentación e Inspección de Identidad (Showcase Compacto) ── */}
          <div className="lg:col-span-7 flex flex-col justify-center space-y-3.5 lg:pr-2">
            
            {/* Tagline y Títulos en SF Pro Typography */}
            <div className="space-y-1.5">
              <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-slate-100 dark:bg-white/5 border border-slate-200 dark:border-white/8 text-slate-600 dark:text-slate-300 w-fit">
                <IconoTema tema="reconocimiento" sinMarco className="w-3.5 h-3.5 text-[#0071E3]" />
                <span>Reconocimiento Óptico Especializado</span>
              </div>
              <h1 className="text-2xl sm:text-3xl lg:text-[34px] font-semibold tracking-[-0.03em] leading-tight sm:leading-9 text-slate-950 dark:text-white">
                Inteligencia documental para documentos colombianos.
              </h1>
              <p className="text-xs sm:text-sm text-slate-600 dark:text-[#86868B] max-w-xl font-normal leading-relaxed sm:leading-5">
                Extracción estructurada de Cédulas de Ciudadanía, Extranjería y Tarjetas de Identidad mediante visión por computador y análisis espacial confidencial.
              </p>
            </div>

            {/* Simulación de Documento de Identidad Digital (Tarjeta Policarbonato Apple Glass Proporcional) */}
            <div className="relative rounded-2xl apple-card-subtle p-4 sm:p-5 overflow-hidden border border-slate-200/90 dark:border-white/10 shadow-xs">
              {/* Línea de escaneo láser sutil sin estridencias */}
              <div className="pointer-events-none absolute left-0 right-0 h-[2px] bg-linear-to-r from-transparent via-[#0071E3]/80 to-transparent animate-apple-scan shadow-xs" />

              {/* Cabecera del Documento */}
              <div className="flex items-start justify-between border-b border-black/6 dark:border-white/8 pb-2.5 mb-3">
                <div className="flex items-center gap-2">
                  <div className="w-6 h-6 rounded-md bg-[#0071E3]/10 dark:bg-[#0071E3]/20 text-[#0071E3] flex items-center justify-center">
                    <ScanLine className="w-3.5 h-3.5" />
                  </div>
                  <div>
                    <p className="text-[9px] font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500">
                      REPÚBLICA DE COLOMBIA
                    </p>
                    <p className="text-xs font-semibold text-slate-900 dark:text-slate-200">
                      CÉDULA DE CIUDADANÍA DIGITAL
                    </p>
                  </div>
                </div>

                {/* Botón de privacidad para datos de prueba */}
                <button
                  type="button"
                  onClick={() => setOcultarDatosID(!ocultarDatosID)}
                  className="text-[10px] text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200 flex items-center gap-1 transition-colors cursor-pointer"
                  title="Alternar privacidad del documento"
                >
                  <Eye className="w-3 h-3" />
                  <span>{ocultarDatosID ? "Mostrar demo" : "Ocultar"}</span>
                </button>
              </div>

              {/* Cuerpo del Documento: Foto + Campos Extraídos */}
              <div className="grid grid-cols-1 sm:grid-cols-12 gap-3 items-center">
                {/* Silueta de Foto Documento */}
                <div className="sm:col-span-4 flex flex-col items-center justify-center p-2.5 rounded-xl bg-slate-100/70 dark:bg-white/3 border border-slate-200/80 dark:border-white/6 text-center">
                  <div className="w-12 h-14 rounded-md bg-slate-200 dark:bg-white/8 flex items-center justify-center text-slate-400 dark:text-slate-500 mb-1">
                    <Fingerprint className="w-7 h-7 stroke-[1.5]" />
                  </div>
                  <span className="text-[8px] uppercase tracking-wider font-mono text-slate-400 dark:text-slate-500">
                    BIOMETRÍA / CHIP
                  </span>
                </div>

                {/* Campos de Extracción OCR */}
                <div className="sm:col-span-8 space-y-1.5">
                  <div className="grid grid-cols-2 gap-1.5">
                    <div className="p-1.5 rounded-lg bg-slate-100/60 dark:bg-white/2 border border-slate-200/50 dark:border-white/4">
                      <span className="text-[8px] font-medium uppercase tracking-wider text-slate-400 dark:text-slate-500 block">
                        Número de Documento (NUIP)
                      </span>
                      <span className="text-[11px] font-mono font-semibold text-slate-900 dark:text-slate-100">
                        {ocultarDatosID ? "1.082.***.***" : "1.082.942.315"}
                      </span>
                    </div>

                    <div className="p-1.5 rounded-lg bg-slate-100/60 dark:bg-white/2 border border-slate-200/50 dark:border-white/4">
                      <span className="text-[8px] font-medium uppercase tracking-wider text-slate-400 dark:text-slate-500 block">
                        Grupo Sanguíneo (RH)
                      </span>
                      <span className="text-[11px] font-mono font-semibold text-slate-900 dark:text-slate-100">
                        O POSITIVO (O+)
                      </span>
                    </div>
                  </div>

                  <div className="p-1.5 rounded-lg bg-slate-100/60 dark:bg-white/2 border border-slate-200/50 dark:border-white/4">
                    <span className="text-[8px] font-medium uppercase tracking-wider text-slate-400 dark:text-slate-500 block">
                      Apellidos y Nombres
                    </span>
                    <span className="text-[11px] font-mono font-semibold text-slate-900 dark:text-slate-100 truncate block">
                      {ocultarDatosID ? "RAMÍREZ CORTÉS ••••••" : "RAMÍREZ CORTÉS JORGE LUIS"}
                    </span>
                  </div>

                  {/* Insignia de Confianza de Inferencia */}
                  <div className="flex items-center justify-between pt-0.5">
                    <div className="flex items-center gap-1">
                      <CheckCircle2 className="w-3 h-3 text-emerald-500" />
                      <span className="text-[10px] text-slate-600 dark:text-slate-400">
                        Validación de formato y estructura
                      </span>
                    </div>
                    <span className="inline-flex items-center text-[9px] font-mono px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
                      99.8% Precisión
                    </span>
                  </div>
                </div>
              </div>
            </div>

            {/* Tres pilares compactos de ingeniería */}
            <div className="grid grid-cols-3 gap-2 pt-0.5">
              <div className="p-2.5 rounded-xl bg-slate-100/40 dark:bg-white/2 border border-slate-200/60 dark:border-white/5">
                <div className="flex items-center gap-1.5 mb-0.5">
                  <ShieldCheck className="w-3.5 h-3.5 text-[#0071E3]" />
                  <span className="text-[11px] font-medium text-slate-900 dark:text-slate-200">
                    Privacidad Total
                  </span>
                </div>
                <p className="text-[10px] text-slate-500 dark:text-[#86868B] leading-tight">
                  Procesamiento en memoria volátil sin persistencia externa.
                </p>
              </div>

              <div className="p-2.5 rounded-xl bg-slate-100/40 dark:bg-white/2 border border-slate-200/60 dark:border-white/5">
                <div className="flex items-center gap-1.5 mb-0.5">
                  <IconoTema tema="vision" sinMarco className="w-4 h-4 text-[#0071E3]" />
                  <span className="text-[11px] font-medium text-slate-900 dark:text-slate-200">
                    Visión Inteligente
                  </span>
                </div>
                <p className="text-[10px] text-slate-500 dark:text-[#86868B] leading-tight">
                  Detección espacial adaptada a tipografías colombianas.
                </p>
              </div>

              <div className="p-2.5 rounded-xl bg-slate-100/40 dark:bg-white/2 border border-slate-200/60 dark:border-white/5">
                <div className="flex items-center gap-1.5 mb-0.5">
                  <FileText className="w-3.5 h-3.5 text-[#0071E3]" />
                  <span className="text-[11px] font-medium text-slate-900 dark:text-slate-200">
                    Exportación FIPS
                  </span>
                </div>
                <p className="text-[10px] text-slate-500 dark:text-[#86868B] leading-tight">
                  Salida estructurada en JSON y Excel con auditoría.
                </p>
              </div>
            </div>
          </div>

          {/* ── COLUMNA DERECHA: Módulo de Acceso y Autenticación (Apple Card Compacta) ── */}
          <div className="lg:col-span-5 w-full max-w-md mx-auto lg:max-w-none">
            <div className="apple-card rounded-2xl sm:rounded-3xl p-5 sm:p-7 relative">
              {segundoPaso ? (
                <VerificacionDosPasos
                  desafio={segundoPaso.desafio}
                  configurar={segundoPaso.configurar}
                  onListo={entrar}
                  onVolver={() => setSegundoPaso(null)}
                />
              ) : (
              <>
              {/* Cabecera del Formulario */}
              <div className="mb-5">
                <div className="flex items-center justify-between mb-3">
                  <div className="w-9 h-9 rounded-xl bg-slate-100 dark:bg-white/6 border border-slate-200/80 dark:border-white/10 flex items-center justify-center text-slate-800 dark:text-white shadow-xs">
                    <Lock className="w-4 h-4" />
                  </div>
                  <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-slate-100 dark:bg-white/5 border border-slate-200/80 dark:border-white/8 text-slate-500 dark:text-slate-400">
                    Acceso Seguro
                  </span>
                </div>

                <h2 className="text-xl sm:text-2xl font-semibold tracking-[-0.02em] text-slate-900 dark:text-white">
                  Iniciar Sesión
                </h2>
                <p className="text-xs text-slate-500 dark:text-[#86868B] mt-0.5 font-normal">
                  Ingresa tus credenciales autorizadas para acceder a la consola.
                </p>
              </div>

              {(sesionCerrada || cookiesBloqueadas) && (
                <div role="status" className="mb-4 space-y-1.5 rounded-xl border border-amber-200 dark:border-amber-500/30 bg-amber-50 dark:bg-amber-500/10 px-3 py-2.5 text-[11px] leading-snug text-amber-900 dark:text-amber-200">
                  {sesionCerrada && (
                    <p>
                      <strong>Tu sesión se cerró.</strong> Venció, cambiaste la contraseña o se cerró desde otro equipo.
                      Vuelve a iniciar sesión.
                    </p>
                  )}
                  {cookiesBloqueadas && (
                    <p>
                      <strong>Tu navegador está bloqueando las cookies.</strong> KondID las necesita para mantener tu
                      sesión: permítelas para este sitio.
                    </p>
                  )}
                </div>
              )}

              {/* Formulario */}
              <form onSubmit={handleLogin} className="space-y-3.5">
                {/* Campo Correo */}
                <div>
                  <label
                    htmlFor="email"
                    className="block text-[11px] font-medium text-slate-700 dark:text-slate-300 mb-1"
                  >
                    Correo electrónico
                  </label>
                  <div className="relative">
                    <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400 dark:text-slate-500 pointer-events-none" />
                    <input
                      id="email"
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="usuario@entidad.gov.co"
                      className="w-full bg-slate-50/80 dark:bg-white/4 border border-slate-200/90 dark:border-white/8 rounded-xl pl-9 pr-3 py-2 text-xs sm:text-sm text-slate-900 dark:text-white placeholder-slate-400 dark:placeholder-slate-500 focus:outline-hidden focus:border-[#0071E3] focus:ring-2 focus:ring-[#0071E3]/20 transition-all"
                      autoComplete="email"
                      disabled={cargando}
                    />
                  </div>
                </div>

                {/* Campo Contraseña */}
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label
                      htmlFor="password"
                      className="block text-[11px] font-medium text-slate-700 dark:text-slate-300"
                    >
                      Contraseña
                    </label>
                    {mayusculas ? (
                      <span role="status" className="text-[10px] font-semibold text-amber-600 dark:text-amber-400">
                        Bloq Mayús está activado
                      </span>
                    ) : (
                      <span className="text-[10px] text-slate-400 dark:text-slate-500">
                        Sensible a mayúsculas
                      </span>
                    )}
                  </div>
                  <div className="relative">
                    <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400 dark:text-slate-500 pointer-events-none" />
                    <input
                      id="password"
                      type={mostrarPass ? "text" : "password"}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      onKeyDown={revisarMayusculas}
                      onKeyUp={revisarMayusculas}
                      onBlur={() => setMayusculas(false)}
                      placeholder="••••••••••••"
                      className="w-full bg-slate-50/80 dark:bg-white/4 border border-slate-200/90 dark:border-white/8 rounded-xl pl-9 pr-10 py-2 text-xs sm:text-sm text-slate-900 dark:text-white placeholder-slate-400 dark:placeholder-slate-500 focus:outline-hidden focus:border-[#0071E3] focus:ring-2 focus:ring-[#0071E3]/20 transition-all font-mono"
                      autoComplete="current-password"
                      disabled={cargando}
                    />
                    <button
                      type="button"
                      onClick={() => setMostrarPass(!mostrarPass)}
                      className="absolute right-2.5 top-1/2 -translate-y-1/2 p-1 text-slate-400 hover:text-slate-700 dark:text-slate-500 dark:hover:text-slate-200 transition-colors cursor-pointer rounded-lg active:scale-95"
                      title={mostrarPass ? "Ocultar contraseña" : "Ver contraseña"}
                    >
                      {mostrarPass ? (
                        <EyeOff className="w-3.5 h-3.5" />
                      ) : (
                        <Eye className="w-3.5 h-3.5" />
                      )}
                    </button>
                  </div>
                  <div className="flex justify-end mt-1.5">
                    <Link
                      href="/olvide-contrasena"
                      className="text-[11px] font-medium text-[#0071E3] hover:text-[#0077ED] dark:text-[#4C9BFF] hover:underline"
                    >
                      ¿Olvidaste tu contraseña?
                    </Link>
                  </div>
                </div>

                {/* Botón Principal (Apple System Blue Button) */}
                <button
                  type="submit"
                  disabled={cargando}
                  className="w-full mt-1 bg-[#0071E3] hover:bg-[#0077ED] active:scale-[0.98] text-white font-medium py-2.5 px-4 rounded-xl text-xs sm:text-sm transition-all duration-150 flex items-center justify-center gap-2 shadow-xs disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
                >
                  {cargando ? (
                    <>
                      {/* Apple-style smooth spinner */}
                      <svg
                        className="animate-spin -ml-1 mr-2 h-4 w-4 text-white"
                        xmlns="http://www.w3.org/2000/svg"
                        fill="none"
                        viewBox="0 0 24 24"
                      >
                        <circle
                          className="opacity-25"
                          cx="12"
                          cy="12"
                          r="10"
                          stroke="currentColor"
                          strokeWidth="3"
                        />
                        <path
                          className="opacity-75"
                          fill="currentColor"
                          d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                        />
                      </svg>
                      <span>Verificando credenciales...</span>
                    </>
                  ) : (
                    <>
                      <span>Ingresar al Sistema</span>
                      <ArrowRight className="w-4 h-4 stroke-2" />
                    </>
                  )}
                </button>
                <p className="text-[10px] leading-snug text-center text-slate-400 dark:text-slate-500">
                  Al ingresar se guarda una cookie solo para mantener tu sesión. No usamos cookies de seguimiento.
                </p>
              </form>
              </>
              )}

              {/* Pie de Seguridad y Cumplimiento Normativo */}
              <div className="mt-5 pt-3 border-t border-black/4 dark:border-white/6 flex items-center justify-between text-[10px] text-slate-400 dark:text-slate-500">
                <div className="flex items-center gap-1.5">
                  <ShieldCheck className="w-3.5 h-3.5 text-emerald-500" />
                  <span>Cifrado TLS 1.3 de extremo a extremo</span>
                </div>
                <span className="font-mono text-[9px]">Ley 1581 / Habeas Data</span>
              </div>
            </div>
          </div>

        </div>
      </main>

      {/* ── PIE DE PÁGINA (Footer Compacto y Discreto) ── */}
      <footer className="w-full shrink-0 border-t border-black/4 dark:border-white/5 py-2.5 transition-colors">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-1 text-[11px] text-slate-400 dark:text-[#86868B]">
          <p>© {new Date().getFullYear()} KondID Systems. Todos los derechos reservados.</p>
          <div className="flex items-center gap-3">
            <span>Servidor Seguro</span>
            <span>•</span>
            <span>Motor OCR Colombiano</span>
            <span>•</span>
            <span>Políticas de Privacidad</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
