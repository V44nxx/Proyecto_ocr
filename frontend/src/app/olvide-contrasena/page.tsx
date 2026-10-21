"use client";

import { useState } from "react";
import { Mail, MailCheck } from "lucide-react";
import TarjetaAcceso from "@/components/ui/TarjetaAcceso";
import { apiAuth, getErrorMessage } from "@/lib/api";

export default function OlvideContrasenaPage() {
  const [email, setEmail] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [confirmacion, setConfirmacion] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const enviar = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim()) {
      setError("Escribe el correo con el que inicias sesión.");
      return;
    }
    setEnviando(true);
    setError(null);
    try {
      const { data } = await apiAuth.olvidePassword(email);
      setConfirmacion(data.message);
    } catch (err: unknown) {
      setError(getErrorMessage(err, "No se pudo enviar el enlace. Intenta de nuevo."));
    } finally {
      setEnviando(false);
    }
  };

  if (confirmacion) {
    return (
      <TarjetaAcceso titulo="Revisa tu correo">
        <div className="flex items-start gap-3 rounded-xl border border-emerald-500/20 bg-emerald-500/10 p-3.5">
          <MailCheck className="w-5 h-5 shrink-0 text-emerald-600 dark:text-emerald-400" />
          <p className="text-xs leading-relaxed text-slate-700 dark:text-slate-200">{confirmacion}</p>
        </div>
        <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-4 leading-relaxed">
          ¿No te llega? Verifica que sea el correo con el que te registró el administrador y revisa la carpeta de
          spam. El enlace sirve una sola vez y vence en 30 minutos; puedes pedir otro en 2 minutos.
        </p>
      </TarjetaAcceso>
    );
  }

  return (
    <TarjetaAcceso
      titulo="¿Olvidaste tu contraseña?"
      descripcion="Escribe el correo de tu cuenta y te enviaremos un enlace para elegir una contraseña nueva."
    >
      <form onSubmit={enviar} className="space-y-4" noValidate>
        <div>
          <label className="input-label" htmlFor="olvide-email">
            Correo electrónico
          </label>
          <div className="relative">
            <Mail className="absolute left-3.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400 pointer-events-none" />
            <input
              id="olvide-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
              placeholder="tu@correo.com"
              disabled={enviando}
              autoFocus
              className="input-field pl-9"
            />
          </div>
        </div>
        {error && (
          <p role="alert" className="text-xs font-medium text-rose-600 dark:text-rose-400">
            {error}
          </p>
        )}
        <button type="submit" disabled={enviando} className="btn-primary w-full py-2.5">
          {enviando ? "Enviando..." : "Enviar enlace"}
        </button>
      </form>
    </TarjetaAcceso>
  );
}
