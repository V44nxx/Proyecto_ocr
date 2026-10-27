"use client";

import { useState } from "react";
import { KeyRound, X } from "lucide-react";
import toast from "react-hot-toast";
import CampoPassword from "@/components/ui/CampoPassword";
import { apiAuth, getErrorMessage } from "@/lib/api";
import { auth } from "@/lib/auth";
import { validarPasswordNueva } from "@/lib/password";
import type { Usuario } from "@/types";

interface ModalCambiarPasswordProps {
  isOpen: boolean;
  onClose: () => void;
  /** Si se pasa, el administrador restablece la contraseña de ese usuario; si no, se cambia la propia. */
  usuarioObjetivo?: Usuario | null;
}

export default function ModalCambiarPassword({ isOpen, onClose, usuarioObjetivo }: ModalCambiarPasswordProps) {
  const [actual, setActual] = useState("");
  const [nueva, setNueva] = useState("");
  const [confirmacion, setConfirmacion] = useState("");
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;
  const esAdmin = !!usuarioObjetivo;

  const limpiarYCerrar = () => {
    setActual("");
    setNueva("");
    setConfirmacion("");
    setError(null);
    onClose();
  };
  const cerrar = () => {
    if (!guardando) limpiarYCerrar();
  };

  const guardar = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!esAdmin && !actual) {
      setError("Escribe tu contraseña actual.");
      return;
    }
    const problema = validarPasswordNueva(nueva, confirmacion);
    if (problema) {
      setError(problema);
      return;
    }
    setGuardando(true);
    setError(null);
    try {
      if (usuarioObjetivo) {
        const { data } = await apiAuth.restablecerPasswordUsuario(usuarioObjetivo.id, nueva);
        toast.success(data.message);
      } else {
        const { data } = await apiAuth.cambiarPassword(actual, nueva); // el backend deja esta sesión con una cookie nueva
        auth.anotarVencimiento(data.access_token);
        toast.success("Contraseña cambiada. Se cerraron tus otras sesiones.");
      }
      setGuardando(false);
      limpiarYCerrar();
    } catch (err: unknown) {
      setError(getErrorMessage(err, "No se pudo cambiar la contraseña."));
      setGuardando(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-xs animate-fade-in"
      onClick={cerrar}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="titulo-cambiar-password"
        className="w-full max-w-md bg-dark-900 border border-white/10 rounded-2xl shadow-2xl overflow-hidden animate-slide-up"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/8">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-[#0071E3]/15 border border-[#0071E3]/30 flex items-center justify-center text-[#0071E3]">
              <KeyRound className="w-4 h-4" />
            </div>
            <div>
              <h2 id="titulo-cambiar-password" className="text-base font-bold text-white">
                {esAdmin ? "Restablecer contraseña" : "Cambiar contraseña"}
              </h2>
              <p className="text-xs text-slate-400">
                {esAdmin ? usuarioObjetivo?.email : "Se cerrarán tus sesiones en otros equipos."}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={cerrar}
            disabled={guardando}
            aria-label="Cerrar"
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/10 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={guardar} className="p-6 space-y-4" noValidate>
          {!esAdmin && (
            <CampoPassword
              id="password-actual"
              etiqueta="Contraseña actual"
              valor={actual}
              onChange={setActual}
              autoComplete="current-password"
              disabled={guardando}
              autoFocus
            />
          )}
          <CampoPassword
            id="password-nueva"
            etiqueta="Contraseña nueva"
            valor={nueva}
            onChange={setNueva}
            autoComplete="new-password"
            placeholder="Mínimo 8 caracteres"
            disabled={guardando}
            autoFocus={esAdmin}
          />
          <CampoPassword
            id="password-confirmacion"
            etiqueta="Repite la contraseña nueva"
            valor={confirmacion}
            onChange={setConfirmacion}
            autoComplete="new-password"
            disabled={guardando}
          />
          {esAdmin && (
            <p className="text-[11px] text-slate-400 leading-relaxed">
              Las sesiones abiertas de este usuario se cerrarán. Comunícale la contraseña nueva por un medio seguro.
            </p>
          )}
          {error && (
            <p role="alert" className="text-xs font-medium text-rose-600 dark:text-rose-400">
              {error}
            </p>
          )}
          <div className="flex items-center justify-end gap-3 pt-1">
            <button type="button" onClick={cerrar} disabled={guardando} className="btn-secondary text-sm py-2 px-4">
              Cancelar
            </button>
            <button type="submit" disabled={guardando} className="btn-primary text-sm py-2 px-4">
              {guardando ? "Guardando..." : esAdmin ? "Restablecer" : "Cambiar contraseña"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
