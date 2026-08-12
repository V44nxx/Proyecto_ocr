"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import toast from "react-hot-toast";
import { FileText, Lock, Mail, Eye, EyeOff, Shield, Cpu } from "lucide-react";
import { apiAuth } from "@/lib/api";
import { auth } from "@/lib/auth";
import type { TokenResponse } from "@/types";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mostrarPass, setMostrarPass] = useState(false);
  const [cargando, setCargando] = useState(false);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) {
      toast.error("Completa todos los campos");
      return;
    }

    setCargando(true);
    try {
      const { data } = await apiAuth.login(email, password);
      auth.guardarSesion(data as TokenResponse);
      toast.success(`Bienvenido, ${(data as TokenResponse).usuario.nombre}`);
      window.location.href = "/dashboard";
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      const mensaje = error.response?.data?.detail || "Credenciales incorrectas";
      toast.error(typeof mensaje === "string" ? mensaje : "Error de autenticación");
    } finally {
      setCargando(false);
    }
  };

  return (
    <div className="min-h-screen login-bg flex items-center justify-center p-4">
      {/* Decoración de fondo */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-primary-600/5 rounded-full blur-3xl" />
        <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-primary-800/5 rounded-full blur-3xl" />
      </div>

      <div className="w-full max-w-md relative">
        {/* Logo y título */}
        <div className="text-center mb-8 animate-fade-in">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-primary-600/20 border border-primary-500/30 mb-4"
               style={{ boxShadow: "0 0 30px rgba(59,130,246,0.3)" }}>
            <Cpu className="w-8 h-8 text-primary-400" />
          </div>
          <h1 className="text-3xl font-bold text-white mb-1">Sistema OCR</h1>
          <p className="text-slate-400 text-sm">
            Documentos de Identificación Colombianos
          </p>
        </div>

        {/* Tarjeta de login */}
        <div className="card-glass rounded-2xl p-8 animate-slide-up">
          <div className="flex items-center gap-2 mb-6">
            <Shield className="w-4 h-4 text-primary-400" />
            <span className="text-sm text-slate-400">Acceso seguro al sistema</span>
          </div>

          <form onSubmit={handleLogin} className="space-y-5">
            {/* Email */}
            <div>
              <label className="input-label" htmlFor="email">
                Correo electrónico
              </label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                <input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="admin@ocr.com"
                  className="input-field pl-10"
                  autoComplete="email"
                  disabled={cargando}
                />
              </div>
            </div>

            {/* Contraseña */}
            <div>
              <label className="input-label" htmlFor="password">
                Contraseña
              </label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                <input
                  id="password"
                  type={mostrarPass ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="input-field pl-10 pr-10"
                  autoComplete="current-password"
                  disabled={cargando}
                />
                <button
                  type="button"
                  onClick={() => setMostrarPass(!mostrarPass)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 transition-colors"
                >
                  {mostrarPass ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            {/* Submit */}
            <button
              type="submit"
              disabled={cargando}
              className="btn-primary w-full mt-6"
            >
              {cargando ? (
                <>
                  <div className="spinner" />
                  Iniciando sesión...
                </>
              ) : (
                <>
                  <Shield className="w-4 h-4" />
                  Iniciar Sesión
                </>
              )}
            </button>
          </form>

          {/* Credenciales por defecto */}
          <div className="mt-6 p-4 rounded-xl bg-primary-500/5 border border-primary-500/15">
            <p className="text-xs text-slate-500 mb-2 font-medium">
              Credenciales por defecto:
            </p>
            <div className="flex flex-col gap-1">
              <button
                onClick={() => { setEmail("admin@ocr.com"); setPassword("Admin123!"); }}
                className="text-left text-xs text-primary-400 hover:text-primary-300 transition-colors"
              >
                📧 admin@ocr.com | 🔑 Admin123!
              </button>
            </div>
          </div>
        </div>

        {/* Features */}
        <div className="mt-8 grid grid-cols-3 gap-3 animate-fade-in">
          {[
            { icon: <FileText className="w-4 h-4" />, text: "OCR Avanzado" },
            { icon: <Cpu className="w-4 h-4" />, text: "PaddleOCR" },
            { icon: <Shield className="w-4 h-4" />, text: "Seguro y Rápido" },
          ].map((item, i) => (
            <div
              key={i}
              className="flex flex-col items-center gap-2 p-3 rounded-xl bg-white/[0.03] border border-white/[0.06] text-center"
            >
              <span className="text-primary-400">{item.icon}</span>
              <span className="text-xs text-slate-500">{item.text}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
