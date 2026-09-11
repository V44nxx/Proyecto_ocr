"use client";

import { useState } from "react";
import { X, Mail, Lock, User, Eye, EyeOff, ShieldCheck, UserCheck, AlertCircle, CheckCircle } from "lucide-react";
import { apiAuth, getErrorMessage } from "@/lib/api";
import type { Usuario } from "@/types";
import toast from "react-hot-toast";

interface ModalCrearUsuarioProps {
  isOpen: boolean;
  onClose: () => void;
  onUsuarioCreado?: (nuevoUsuario: Usuario) => void;
}

export default function ModalCrearUsuario({
  isOpen,
  onClose,
  onUsuarioCreado,
}: ModalCrearUsuarioProps) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [nombre, setNombre] = useState("");
  const [rol, setRol] = useState<"usuario" | "admin">("usuario");
  const [mostrarPassword, setMostrarPassword] = useState(false);
  const [guardando, setGuardando] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    const emailLimpio = email.trim().toLowerCase();
    if (!emailLimpio) {
      toast.error("Por favor ingresa un correo electrónico");
      return;
    }

    if (!password || password.length < 8) {
      toast.error("La contraseña debe tener al menos 8 caracteres");
      return;
    }

    setGuardando(true);
    try {
      const { data } = await apiAuth.register({
        email: emailLimpio,
        password,
        nombre: nombre.trim() || undefined,
        rol,
      });

      toast.success(`Usuario ${emailLimpio} creado con éxito. Ya puede iniciar sesión.`);
      
      // Limpiar formulario
      setEmail("");
      setPassword("");
      setNombre("");
      setRol("usuario");
      setMostrarPassword(false);

      if (onUsuarioCreado) {
        onUsuarioCreado(data);
      }
      onClose();
    } catch (err: unknown) {
      const msg = getErrorMessage(err, "No se pudo registrar el usuario");
      toast.error(msg);
    } finally {
      setGuardando(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-md animate-fade-in">
      <div 
        className="w-full max-w-lg bg-dark-900 border border-white/10 rounded-2xl shadow-2xl shadow-primary-950/40 overflow-hidden animate-slide-up"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-5 border-b border-white/[0.08] bg-dark-800/60">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-primary-500/20 border border-primary-500/30 flex items-center justify-center text-primary-400">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-white">Crear Nuevo Usuario</h2>
              <p className="text-xs text-slate-400">
                Registra credenciales para habilitar acceso al login general
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            disabled={guardando}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/10 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-6 space-y-5">
          {/* Email */}
          <div>
            <label className="input-label" htmlFor="nuevo-usuario-email">
              Correo Electrónico <span className="text-rose-400">*</span>
            </label>
            <div className="relative">
              <Mail className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
              <input
                id="nuevo-usuario-email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="ejemplo@correo.com"
                className="input-field pl-10 text-sm"
                disabled={guardando}
                autoFocus
              />
            </div>
            <p className="text-[11px] text-slate-500 mt-1">
              Este correo se usará para iniciar sesión en la pantalla de acceso.
            </p>
          </div>

          {/* Contraseña */}
          <div>
            <label className="input-label" htmlFor="nuevo-usuario-pass">
              Contraseña de Acceso <span className="text-rose-400">*</span>
            </label>
            <div className="relative">
              <Lock className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
              <input
                id="nuevo-usuario-pass"
                type={mostrarPassword ? "text" : "password"}
                required
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Mínimo 8 caracteres"
                className="input-field pl-10 pr-10 text-sm"
                disabled={guardando}
              />
              <button
                type="button"
                onClick={() => setMostrarPassword(!mostrarPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 transition-colors"
                tabIndex={-1}
              >
                {mostrarPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
            <div className="flex items-center gap-1.5 text-[11px] text-slate-500 mt-1">
              <AlertCircle className="w-3 h-3 text-primary-400" />
              <span>Debe contener al menos 8 caracteres para máxima seguridad.</span>
            </div>
          </div>

          {/* Nombre completo (opcional) */}
          <div>
            <label className="input-label" htmlFor="nuevo-usuario-nombre">
              Nombre Completo <span className="text-slate-500 font-normal">(Opcional)</span>
            </label>
            <div className="relative">
              <User className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
              <input
                id="nuevo-usuario-nombre"
                type="text"
                value={nombre}
                onChange={(e) => setNombre(e.target.value)}
                placeholder="Ej. Carlos Rodríguez"
                className="input-field pl-10 text-sm"
                disabled={guardando}
              />
            </div>
            <p className="text-[11px] text-slate-500 mt-1">
              Si se omite, se generará automáticamente a partir del correo.
            </p>
          </div>

          {/* Rol del Usuario */}
          <div>
            <label className="input-label mb-2">Rol y Nivel de Acceso</label>
            <div className="grid grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => setRol("usuario")}
                className={`p-3.5 rounded-xl border text-left transition-all ${
                  rol === "usuario"
                    ? "bg-primary-500/15 border-primary-500/50 text-white shadow-lg shadow-primary-950/20"
                    : "bg-dark-800/40 border-white/[0.08] text-slate-400 hover:border-white/20"
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-bold flex items-center gap-1.5">
                    <UserCheck className="w-4 h-4 text-primary-400" />
                    Operador / Usuario
                  </span>
                  {rol === "usuario" && <CheckCircle className="w-3.5 h-3.5 text-primary-400" />}
                </div>
                <p className="text-[11px] text-slate-400 leading-tight">
                  Procesar OCR, auditar personas y exportar reportes.
                </p>
              </button>

              <button
                type="button"
                onClick={() => setRol("admin")}
                className={`p-3.5 rounded-xl border text-left transition-all ${
                  rol === "admin"
                    ? "bg-purple-500/15 border-purple-500/50 text-white shadow-lg shadow-purple-950/20"
                    : "bg-dark-800/40 border-white/[0.08] text-slate-400 hover:border-white/20"
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-bold flex items-center gap-1.5 text-purple-300">
                    <ShieldCheck className="w-4 h-4 text-purple-400" />
                    Administrador
                  </span>
                  {rol === "admin" && <CheckCircle className="w-3.5 h-3.5 text-purple-400" />}
                </div>
                <p className="text-[11px] text-slate-400 leading-tight">
                  Acceso completo, configuración y creación de usuarios.
                </p>
              </button>
            </div>
          </div>

          {/* Footer botones */}
          <div className="flex items-center justify-end gap-3 pt-4 border-t border-white/[0.08]">
            <button
              type="button"
              onClick={onClose}
              disabled={guardando}
              className="btn-secondary text-sm py-2.5 px-4"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={guardando}
              className="btn-primary text-sm py-2.5 px-5"
            >
              {guardando ? (
                <>
                  <div className="spinner w-4 h-4" />
                  Creando usuario...
                </>
              ) : (
                <>
                  <ShieldCheck className="w-4 h-4" />
                  Crear Usuario
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
