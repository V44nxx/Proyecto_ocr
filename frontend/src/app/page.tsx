"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import toast from "react-hot-toast";
import {
  FileText,
  Lock,
  Mail,
  Eye,
  EyeOff,
  ShieldCheck,
  Cpu,
  Sparkles,
  ArrowRight,
  Sun,
  Moon,
  Fingerprint,
  CheckCircle2,
  ScanLine,
} from "lucide-react";
import { apiAuth } from "@/lib/api";
import { auth } from "@/lib/auth";
import { useTheme } from "@/context/ThemeContext";
import type { TokenResponse } from "@/types";

export default function LoginPage() {
  const router = useRouter();
  const { theme, toggleTheme } = useTheme();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mostrarPass, setMostrarPass] = useState(false);
  const [cargando, setCargando] = useState(false);
  const [ocultarDatosID, setOcultarDatosID] = useState(false);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) {
      toast.error("Por favor completa todos los campos requeridos");
      return;
    }

    setCargando(true);
    try {
      const { data } = await apiAuth.login(email, password);
      auth.guardarSesion(data as TokenResponse);
      toast.success(`Bienvenido, ${(data as TokenResponse).usuario.nombre}`);
      window.location.href = "/dashboard";
    } catch (err: unknown) {
      const error = err as {
        response?: { data?: { detail?: string }; status?: number };
        message?: string;
      };
      if (!error.response) {
        toast.error(`Error de conexión con la API (${error.message || "Servidor no responde"})`);
      } else {
        const mensaje = error.response?.data?.detail || "Credenciales incorrectas";
        toast.error(typeof mensaje === "string" ? mensaje : "Error de autenticación");
      }
    } finally {
      setCargando(false);
    }
  };

  const aplicarCredencialesDemo = () => {
    setEmail("admin@ocr.com");
    setPassword("Admin123!");
    toast.success("Credenciales demo cargadas", { duration: 2000 });
  };

  return (
    <div className="min-h-screen login-bg text-slate-900 dark:text-slate-100 flex flex-col justify-between selection:bg-[#0071E3]/20 selection:text-white">
      {/* ── BARRA SUPERIOR (Chrome translúcido estilo Apple) ── */}
      <header className="w-full border-b border-black/[0.04] dark:border-white/[0.06] backdrop-blur-md bg-white/40 dark:bg-[#070A0F]/50 sticky top-0 z-30 transition-colors">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-14 flex items-center justify-between">
          {/* Marca / Logotipo */}
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-xl bg-slate-900 dark:bg-white text-white dark:text-slate-950 flex items-center justify-center font-semibold text-xs tracking-tight shadow-sm">
              <Fingerprint className="w-4 h-4 stroke-[2.2]" />
            </div>
            <div className="flex items-center gap-2">
              <span className="font-semibold tracking-tight text-sm text-slate-900 dark:text-white">
                KondID
              </span>
              <span className="hidden sm:inline-block text-[11px] text-slate-400 dark:text-slate-500 font-normal">
                / Document Intelligence
              </span>
            </div>
          </div>

          {/* Telemetría & Acciones */}
          <div className="flex items-center gap-2.5 sm:gap-3">
            {/* Estado del motor OCR */}
            <div className="hidden sm:inline-flex items-center gap-2 px-3 py-1 rounded-full text-[11px] font-medium bg-slate-100/80 dark:bg-white/[0.04] border border-slate-200/80 dark:border-white/[0.07] text-slate-600 dark:text-slate-400">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
              <span>PaddleOCR v2.8 • Operativo</span>
            </div>

            {/* Alternador de tema modo Claro / Oscuro */}
            <button
              type="button"
              onClick={toggleTheme}
              title={`Cambiar a modo ${theme === "dark" ? "claro" : "oscuro"}`}
              className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-slate-100 dark:bg-white/[0.06] border border-slate-200/80 dark:border-white/[0.08] text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white active:scale-95 transition-all cursor-pointer"
            >
              {theme === "dark" ? (
                <Sun className="w-4 h-4 text-amber-400" />
              ) : (
                <Moon className="w-4 h-4 text-slate-600" />
              )}
            </button>
          </div>
        </div>
      </header>

      {/* ── CUERPO PRINCIPAL (Split View: Showcase + Módulo de Acceso) ── */}
      <main className="max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 sm:py-12 lg:py-16 flex-1 flex items-center justify-center">
        <div className="w-full grid grid-cols-1 lg:grid-cols-12 gap-8 lg:gap-14 items-center">
          
          {/* ── COLUMNA IZQUIERDA: Presentación e Inspección de Identidad (Showcase) ── */}
          <div className="lg:col-span-7 flex flex-col justify-center space-y-6 lg:pr-4">
            
            {/* Tagline y Títulos en SF Pro Typography */}
            <div className="space-y-3">
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-medium bg-slate-100 dark:bg-white/[0.05] border border-slate-200 dark:border-white/[0.08] text-slate-600 dark:text-slate-300 w-fit">
                <Sparkles className="w-3.5 h-3.5 text-[#0071E3]" />
                <span>Reconocimiento Óptico Especializado</span>
              </div>
              <h1 className="text-3xl sm:text-4xl lg:text-[40px] font-semibold tracking-[-0.03em] leading-[1.15] text-slate-950 dark:text-white">
                Inteligencia documental para documentos colombianos.
              </h1>
              <p className="text-sm sm:text-base text-slate-600 dark:text-[#86868B] max-w-xl font-normal leading-relaxed">
                Extracción estructurada de Cédulas de Ciudadanía, Extranjería y Tarjetas de Identidad mediante redes neuronales profundas con procesamiento confidencial.
              </p>
            </div>

            {/* Simulación de Documento de Identidad Digital (Tarjeta Policarbonato Apple Glass) */}
            <div className="relative rounded-2xl apple-card-subtle p-5 sm:p-6 overflow-hidden border border-slate-200/90 dark:border-white/[0.1] shadow-sm">
              {/* Línea de escaneo láser sutil sin estridencias */}
              <div className="pointer-events-none absolute left-0 right-0 h-[2px] bg-gradient-to-r from-transparent via-[#0071E3]/80 to-transparent animate-apple-scan shadow-sm" />

              {/* Cabecera del Documento */}
              <div className="flex items-start justify-between border-b border-black/[0.06] dark:border-white/[0.08] pb-3 mb-4">
                <div className="flex items-center gap-2.5">
                  <div className="w-7 h-7 rounded-lg bg-[#0071E3]/10 dark:bg-[#0071E3]/20 text-[#0071E3] flex items-center justify-center">
                    <ScanLine className="w-4 h-4" />
                  </div>
                  <div>
                    <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500">
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
                  className="text-[11px] text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200 flex items-center gap-1.5 transition-colors cursor-pointer"
                  title="Alternar privacidad del documento"
                >
                  <Eye className="w-3.5 h-3.5" />
                  <span className="hidden sm:inline">{ocultarDatosID ? "Mostrar demo" : "Ocultar"}</span>
                </button>
              </div>

              {/* Cuerpo del Documento: Foto + Campos Extraídos */}
              <div className="grid grid-cols-1 sm:grid-cols-12 gap-4 items-center">
                {/* Silueta de Foto Documento */}
                <div className="sm:col-span-4 flex flex-col items-center justify-center p-3 rounded-xl bg-slate-100/70 dark:bg-white/[0.03] border border-slate-200/80 dark:border-white/[0.06] text-center">
                  <div className="w-14 h-16 rounded-lg bg-slate-200 dark:bg-white/[0.08] flex items-center justify-center text-slate-400 dark:text-slate-500 mb-1.5">
                    <Fingerprint className="w-8 h-8 stroke-[1.5]" />
                  </div>
                  <span className="text-[9px] uppercase tracking-wider font-mono text-slate-400 dark:text-slate-500">
                    FOTO / BIOMETRÍA
                  </span>
                </div>

                {/* Campos de Extracción OCR */}
                <div className="sm:col-span-8 space-y-2">
                  <div className="grid grid-cols-2 gap-2">
                    <div className="p-2 rounded-lg bg-slate-100/60 dark:bg-white/[0.02] border border-slate-200/50 dark:border-white/[0.04]">
                      <span className="text-[9px] font-medium uppercase tracking-wider text-slate-400 dark:text-slate-500 block">
                        Número de Documento (NUIP)
                      </span>
                      <span className="text-xs font-mono font-semibold text-slate-900 dark:text-slate-100">
                        {ocultarDatosID ? "1.082.***.***" : "1.082.942.315"}
                      </span>
                    </div>

                    <div className="p-2 rounded-lg bg-slate-100/60 dark:bg-white/[0.02] border border-slate-200/50 dark:border-white/[0.04]">
                      <span className="text-[9px] font-medium uppercase tracking-wider text-slate-400 dark:text-slate-500 block">
                        Grupo Sanguíneo (RH)
                      </span>
                      <span className="text-xs font-mono font-semibold text-slate-900 dark:text-slate-100">
                        O POSITIVO (O+)
                      </span>
                    </div>
                  </div>

                  <div className="p-2 rounded-lg bg-slate-100/60 dark:bg-white/[0.02] border border-slate-200/50 dark:border-white/[0.04]">
                    <span className="text-[9px] font-medium uppercase tracking-wider text-slate-400 dark:text-slate-500 block">
                      Apellidos y Nombres
                    </span>
                    <span className="text-xs font-mono font-semibold text-slate-900 dark:text-slate-100 truncate block">
                      {ocultarDatosID ? "RAMÍREZ CORTÉS ••••••" : "RAMÍREZ CORTÉS JORGE LUIS"}
                    </span>
                  </div>

                  {/* Insignia de Confianza de Inferencia */}
                  <div className="flex items-center justify-between pt-1">
                    <div className="flex items-center gap-1.5">
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
                      <span className="text-[11px] text-slate-600 dark:text-slate-400">
                        Validación automática de checksum
                      </span>
                    </div>
                    <span className="inline-flex items-center text-[10px] font-mono px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
                      99.8% Confianza
                    </span>
                  </div>
                </div>
              </div>
            </div>

            {/* Tres pilares de diseño e ingeniería */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-1">
              <div className="p-3 rounded-xl bg-slate-100/40 dark:bg-white/[0.02] border border-slate-200/60 dark:border-white/[0.05]">
                <div className="flex items-center gap-2 mb-1">
                  <ShieldCheck className="w-4 h-4 text-[#0071E3]" />
                  <span className="text-xs font-medium text-slate-900 dark:text-slate-200">
                    Privacidad Total
                  </span>
                </div>
                <p className="text-[11px] text-slate-500 dark:text-[#86868B] leading-snug">
                  Procesamiento en memoria volátil sin persistencia no autorizada.
                </p>
              </div>

              <div className="p-3 rounded-xl bg-slate-100/40 dark:bg-white/[0.02] border border-slate-200/60 dark:border-white/[0.05]">
                <div className="flex items-center gap-2 mb-1">
                  <Cpu className="w-4 h-4 text-[#0071E3]" />
                  <span className="text-xs font-medium text-slate-900 dark:text-slate-200">
                    Motor PaddleOCR
                  </span>
                </div>
                <p className="text-[11px] text-slate-500 dark:text-[#86868B] leading-snug">
                  Inferencia neural entrenada para tipografías y microtextos.
                </p>
              </div>

              <div className="p-3 rounded-xl bg-slate-100/40 dark:bg-white/[0.02] border border-slate-200/60 dark:border-white/[0.05]">
                <div className="flex items-center gap-2 mb-1">
                  <FileText className="w-4 h-4 text-[#0071E3]" />
                  <span className="text-xs font-medium text-slate-900 dark:text-slate-200">
                    Exportación FIPS
                  </span>
                </div>
                <p className="text-[11px] text-slate-500 dark:text-[#86868B] leading-snug">
                  Salida estructurada en JSON y Excel con trazabilidad de auditoría.
                </p>
              </div>
            </div>
          </div>

          {/* ── COLUMNA DERECHA: Módulo de Acceso y Autenticación (Apple Card) ── */}
          <div className="lg:col-span-5 w-full max-w-md mx-auto lg:max-w-none">
            <div className="apple-card rounded-3xl p-6 sm:p-8 relative">
              {/* Cabecera del Formulario */}
              <div className="mb-6">
                <div className="flex items-center justify-between mb-4">
                  <div className="w-10 h-10 rounded-2xl bg-slate-100 dark:bg-white/[0.06] border border-slate-200/80 dark:border-white/[0.1] flex items-center justify-center text-slate-800 dark:text-white shadow-sm">
                    <Lock className="w-4 h-4" />
                  </div>
                  <span className="text-[11px] font-medium px-2.5 py-1 rounded-full bg-slate-100 dark:bg-white/[0.05] border border-slate-200/80 dark:border-white/[0.08] text-slate-500 dark:text-slate-400">
                    Acceso Seguro
                  </span>
                </div>

                <h2 className="text-xl sm:text-2xl font-semibold tracking-[-0.02em] text-slate-900 dark:text-white">
                  Iniciar Sesión
                </h2>
                <p className="text-xs sm:text-sm text-slate-500 dark:text-[#86868B] mt-1 font-normal">
                  Ingresa tus credenciales institucionales para acceder a la consola.
                </p>
              </div>

              {/* Formulario */}
              <form onSubmit={handleLogin} className="space-y-4">
                {/* Campo Correo */}
                <div>
                  <label
                    htmlFor="email"
                    className="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-1.5"
                  >
                    Correo electrónico
                  </label>
                  <div className="relative">
                    <Mail className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 dark:text-slate-500 pointer-events-none" />
                    <input
                      id="email"
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="usuario@entidad.gov.co"
                      className="w-full bg-slate-50/80 dark:bg-white/[0.04] border border-slate-200/90 dark:border-white/[0.08] rounded-xl pl-10 pr-3.5 py-2.5 text-xs sm:text-sm text-slate-900 dark:text-white placeholder-slate-400 dark:placeholder-slate-500 focus:outline-none focus:border-[#0071E3] focus:ring-2 focus:ring-[#0071E3]/20 transition-all"
                      autoComplete="email"
                      disabled={cargando}
                    />
                  </div>
                </div>

                {/* Campo Contraseña */}
                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <label
                      htmlFor="password"
                      className="block text-xs font-medium text-slate-700 dark:text-slate-300"
                    >
                      Contraseña
                    </label>
                    <span className="text-[11px] text-slate-400 dark:text-slate-500">
                      Sensible a mayúsculas
                    </span>
                  </div>
                  <div className="relative">
                    <Lock className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 dark:text-slate-500 pointer-events-none" />
                    <input
                      id="password"
                      type={mostrarPass ? "text" : "password"}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="••••••••••••"
                      className="w-full bg-slate-50/80 dark:bg-white/[0.04] border border-slate-200/90 dark:border-white/[0.08] rounded-xl pl-10 pr-11 py-2.5 text-xs sm:text-sm text-slate-900 dark:text-white placeholder-slate-400 dark:placeholder-slate-500 focus:outline-none focus:border-[#0071E3] focus:ring-2 focus:ring-[#0071E3]/20 transition-all font-mono"
                      autoComplete="current-password"
                      disabled={cargando}
                    />
                    <button
                      type="button"
                      onClick={() => setMostrarPass(!mostrarPass)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 p-1 text-slate-400 hover:text-slate-700 dark:text-slate-500 dark:hover:text-slate-200 transition-colors cursor-pointer rounded-lg active:scale-95"
                      title={mostrarPass ? "Ocultar contraseña" : "Ver contraseña"}
                    >
                      {mostrarPass ? (
                        <EyeOff className="w-4 h-4" />
                      ) : (
                        <Eye className="w-4 h-4" />
                      )}
                    </button>
                  </div>
                </div>

                {/* Atajo Conveniente: Credenciales de Prueba */}
                <div className="pt-1">
                  <button
                    type="button"
                    onClick={aplicarCredencialesDemo}
                    className="w-full text-left p-2.5 rounded-xl bg-slate-100/60 dark:bg-white/[0.03] hover:bg-slate-100 dark:hover:bg-white/[0.06] border border-slate-200/70 dark:border-white/[0.05] transition-all flex items-center justify-between group cursor-pointer"
                  >
                    <div className="flex items-center gap-2">
                      <div className="w-5 h-5 rounded-md bg-[#0071E3]/10 text-[#0071E3] flex items-center justify-center text-[10px] font-semibold">
                        i
                      </div>
                      <div className="text-[11px] leading-tight">
                        <span className="font-medium text-slate-700 dark:text-slate-300 block">
                          Credenciales de desarrollo
                        </span>
                        <span className="text-slate-400 dark:text-slate-500">
                          admin@ocr.com / Admin123!
                        </span>
                      </div>
                    </div>
                    <span className="text-[10px] text-[#0071E3] font-medium opacity-80 group-hover:opacity-100 flex items-center gap-0.5">
                      Cargar <ArrowRight className="w-3 h-3 group-hover:translate-x-0.5 transition-transform" />
                    </span>
                  </button>
                </div>

                {/* Botón Principal (Apple System Blue Button) */}
                <button
                  type="submit"
                  disabled={cargando}
                  className="w-full mt-2 bg-[#0071E3] hover:bg-[#0077ED] active:scale-[0.98] text-white font-medium py-2.5 px-4 rounded-xl text-xs sm:text-sm transition-all duration-150 flex items-center justify-center gap-2 shadow-sm disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
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
                      <ArrowRight className="w-4 h-4 stroke-[2]" />
                    </>
                  )}
                </button>
              </form>

              {/* Pie de Seguridad y Cumplimiento Normativo */}
              <div className="mt-6 pt-4 border-t border-black/[0.04] dark:border-white/[0.06] flex items-center justify-between text-[11px] text-slate-400 dark:text-slate-500">
                <div className="flex items-center gap-1.5">
                  <ShieldCheck className="w-3.5 h-3.5 text-emerald-500" />
                  <span>Cifrado TLS 1.3 de extremo a extremo</span>
                </div>
                <span className="font-mono text-[10px]">Ley 1581 / Habeas Data</span>
              </div>
            </div>
          </div>

        </div>
      </main>

      {/* ── PIE DE PÁGINA (Footer Discreto y Concreto) ── */}
      <footer className="w-full border-t border-black/[0.04] dark:border-white/[0.05] py-4 transition-colors">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-2 text-[11px] text-slate-400 dark:text-[#86868B]">
          <p>© {new Date().getFullYear()} KondID Systems. Todos los derechos reservados.</p>
          <div className="flex items-center gap-4">
            <span>Servidor Seguro</span>
            <span>•</span>
            <span>OCR Colombian Engine v2.4</span>
            <span>•</span>
            <span>Políticas de Privacidad</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
