"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { CheckCircle2 } from "lucide-react";
import TarjetaAcceso from "@/components/ui/TarjetaAcceso";
import CampoPassword from "@/components/ui/CampoPassword";
import { apiAuth, getErrorMessage } from "@/lib/api";
import { auth } from "@/lib/auth";
import { validarPasswordNueva } from "@/lib/password";

function RestablecerContenido() {
  const token = useSearchParams().get("token") || "";
  const [nueva, setNueva] = useState("");
  const [confirmacion, setConfirmacion] = useState("");
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [listo, setListo] = useState(false);

  if (!token) {
    return (
      <TarjetaAcceso titulo="Enlace incompleto" descripcion="Este enlace no trae el código de recuperación.">
        <Link href="/olvide-contrasena" className="btn-primary w-full py-2.5">
          Pedir un enlace nuevo
        </Link>
      </TarjetaAcceso>
    );
  }

  if (listo) {
    return (
      <TarjetaAcceso titulo="Contraseña actualizada">
        <div className="flex items-start gap-3 rounded-xl border border-emerald-500/20 bg-emerald-500/10 p-3.5 mb-4">
          <CheckCircle2 className="w-5 h-5 shrink-0 text-emerald-600 dark:text-emerald-400" />
          <p className="text-xs leading-relaxed text-slate-700 dark:text-slate-200">
            Tu contraseña se cambió y se cerraron las sesiones que tenías abiertas. Ya puedes entrar con la nueva.
          </p>
        </div>
        <Link href="/" className="btn-primary w-full py-2.5">
          Iniciar sesión
        </Link>
      </TarjetaAcceso>
    );
  }

  const guardar = async (e: React.FormEvent) => {
    e.preventDefault();
    const problema = validarPasswordNueva(nueva, confirmacion);
    if (problema) {
      setError(problema);
      return;
    }
    setGuardando(true);
    setError(null);
    try {
      await apiAuth.restablecerPassword(token, nueva);
      auth.cerrarSesion(); // cualquier sesión guardada en este navegador ya no sirve
      setListo(true);
    } catch (err: unknown) {
      setError(getErrorMessage(err, "No se pudo cambiar la contraseña. Intenta de nuevo."));
    } finally {
      setGuardando(false);
    }
  };

  return (
    <TarjetaAcceso titulo="Elige una contraseña nueva" descripcion="Usa al menos 8 caracteres.">
      <form onSubmit={guardar} className="space-y-4" noValidate>
        <CampoPassword
          id="restablecer-nueva"
          etiqueta="Contraseña nueva"
          valor={nueva}
          onChange={setNueva}
          autoComplete="new-password"
          disabled={guardando}
          autoFocus
        />
        <CampoPassword
          id="restablecer-confirmacion"
          etiqueta="Repite la contraseña nueva"
          valor={confirmacion}
          onChange={setConfirmacion}
          autoComplete="new-password"
          disabled={guardando}
        />
        {error && (
          <p role="alert" className="text-xs font-medium text-rose-600 dark:text-rose-400">
            {error}{" "}
            {error.includes("venció") && (
              <Link href="/olvide-contrasena" className="underline">
                Pedir otro enlace
              </Link>
            )}
          </p>
        )}
        <button type="submit" disabled={guardando} className="btn-primary w-full py-2.5">
          {guardando ? "Guardando..." : "Guardar contraseña"}
        </button>
      </form>
    </TarjetaAcceso>
  );
}

export default function RestablecerContrasenaPage() {
  return (
    <Suspense fallback={null}>
      <RestablecerContenido />
    </Suspense>
  );
}
