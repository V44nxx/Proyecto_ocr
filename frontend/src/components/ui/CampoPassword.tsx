"use client";

import { useState } from "react";
import { Eye, EyeOff, Lock } from "lucide-react";

interface CampoPasswordProps {
  id: string;
  etiqueta: string;
  valor: string;
  onChange: (valor: string) => void;
  autoComplete: "current-password" | "new-password";
  placeholder?: string;
  disabled?: boolean;
  autoFocus?: boolean;
}

/** Campo de contraseña con botón para mostrarla u ocultarla y aviso de Bloq Mayús activado. */
export default function CampoPassword({
  id,
  etiqueta,
  valor,
  onChange,
  autoComplete,
  placeholder,
  disabled,
  autoFocus,
}: CampoPasswordProps) {
  const [visible, setVisible] = useState(false);
  const [mayusculas, setMayusculas] = useState(false);
  const revisarMayusculas = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (typeof e.getModifierState === "function") setMayusculas(e.getModifierState("CapsLock"));
  };
  return (
    <div>
      <label className="input-label" htmlFor={id}>
        {etiqueta}
      </label>
      <div className="relative">
        <Lock className="absolute left-3.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400 pointer-events-none" />
        <input
          id={id}
          type={visible ? "text" : "password"}
          value={valor}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={revisarMayusculas}
          onKeyUp={revisarMayusculas}
          onBlur={() => setMayusculas(false)}
          autoComplete={autoComplete}
          placeholder={placeholder}
          disabled={disabled}
          autoFocus={autoFocus}
          className="input-field pl-9 pr-10"
        />
        <button
          type="button"
          onClick={() => setVisible(!visible)}
          tabIndex={-1}
          title={visible ? "Ocultar contraseña" : "Ver contraseña"}
          aria-label={visible ? "Ocultar contraseña" : "Ver contraseña"}
          className="absolute right-2.5 top-1/2 -translate-y-1/2 p-1 text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 transition-colors cursor-pointer rounded-lg"
        >
          {visible ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
        </button>
      </div>
      {mayusculas && (
        <p role="status" className="mt-1 text-[11px] font-semibold text-amber-600 dark:text-amber-400">
          Bloq Mayús está activado
        </p>
      )}
    </div>
  );
}
