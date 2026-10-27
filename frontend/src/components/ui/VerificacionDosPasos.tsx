"use client";

import { useEffect, useRef, useState } from "react";
import toast from "react-hot-toast";
import { ArrowLeft, ArrowRight, Copy, Download, KeyRound, ShieldCheck, Smartphone } from "lucide-react";
import { apiAuth, getErrorMessage } from "@/lib/api";
import type { ConfigurarDobleFactor, LoginResponse } from "@/types";

interface VerificacionDosPasosProps {
  desafio: string;
  /** El administrador todavía no vinculó su app: se muestra el QR antes de pedir el código */
  configurar: boolean;
  /** La sesión quedó abierta (la cookie ya la puso el backend) */
  onListo: (data: LoginResponse) => void;
  /** Volver al correo y la contraseña; `vencido` si el desafío ya no sirve */
  onVolver: (vencido?: boolean) => void;
}

type Etapa = "configurar" | "codigo" | "respaldo";

const claseCampo =
  "w-full bg-slate-50/80 dark:bg-white/4 border border-slate-200/90 dark:border-white/8 rounded-xl px-3 py-2.5 text-center text-base sm:text-lg tracking-[0.35em] font-mono text-slate-900 dark:text-white placeholder-slate-300 dark:placeholder-slate-600 focus:outline-hidden focus:border-[#0071E3] focus:ring-2 focus:ring-[#0071E3]/20 transition-all";
const claseBoton =
  "w-full bg-[#0071E3] hover:bg-[#0077ED] active:scale-[0.98] text-white font-medium py-2.5 px-4 rounded-xl text-xs sm:text-sm transition-all duration-150 flex items-center justify-center gap-2 shadow-xs disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer";
const clasePaso =
  "shrink-0 w-5 h-5 rounded-full bg-slate-100 dark:bg-white/6 border border-slate-200/80 dark:border-white/10 text-[10px] font-semibold text-slate-600 dark:text-slate-300 flex items-center justify-center";
const claseEnlace =
  "text-[11px] font-medium text-[#0071E3] hover:text-[#0077ED] dark:text-[#4C9BFF] hover:underline cursor-pointer";

/** La clave en grupos de 4 para copiarla a mano sin perderse */
const agrupar = (secreto: string) => secreto.match(/.{1,4}/g)?.join(" ") ?? secreto;

export default function VerificacionDosPasos({ desafio, configurar, onListo, onVolver }: VerificacionDosPasosProps) {
  const [etapa, setEtapa] = useState<Etapa>(configurar ? "configurar" : "codigo");
  const [datosQr, setDatosQr] = useState<ConfigurarDobleFactor | null>(null);
  const [codigo, setCodigo] = useState("");
  const [usarRespaldo, setUsarRespaldo] = useState(false);
  const [cargando, setCargando] = useState(false);
  const [sesion, setSesion] = useState<LoginResponse | null>(null);
  const [guardados, setGuardados] = useState(false);
  // Tras un código rechazado se explica la causa más común: la hora del celular corrida
  const [codigoRechazado, setCodigoRechazado] = useState(false);
  const campo = useRef<HTMLInputElement>(null);

  const manejarError = (err: unknown) => {
    const estado = (err as { response?: { status?: number } })?.response?.status;
    if (estado === 401) {
      toast.error(getErrorMessage(err, "La verificación venció. Inicia sesión de nuevo."), { id: "login-error" });
      onVolver(true);
      return;
    }
    if (estado === 400) setCodigoRechazado(true);
    toast.error(getErrorMessage(err, "No se pudo verificar el código"), { id: "login-error" });
    setCodigo("");
    campo.current?.focus();
  };

  useEffect(() => {
    if (!configurar) return;
    apiAuth
      .configurarDobleFactor(desafio)
      .then(({ data }) => setDatosQr(data))
      .catch(manejarError);
    // Solo al abrir: cada llamada genera una clave nueva
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [desafio, configurar]);

  const enviar = async (valor: string) => {
    if (cargando) return;
    setCargando(true);
    try {
      if (etapa === "configurar") {
        const { data } = await apiAuth.activarDobleFactor(desafio, valor);
        setSesion(data);
        setEtapa("respaldo");
      } else {
        const { data } = await apiAuth.loginDobleFactor(desafio, valor);
        const restantes = data.codigos_respaldo_restantes;
        if (restantes != null) {
          toast(
            restantes <= 2
              ? `Te quedan ${restantes} códigos de respaldo. Pide a otro administrador que restablezca tu verificación para tener nuevos.`
              : `Entraste con un código de respaldo. Te quedan ${restantes}.`,
            { duration: 8000 }
          );
        }
        onListo(data);
      }
    } catch (err) {
      manejarError(err);
    } finally {
      setCargando(false);
    }
  };

  const cambiarCodigo = (texto: string) => {
    if (usarRespaldo) {
      setCodigo(texto.toUpperCase().replace(/[^A-Z0-9-]/g, "").slice(0, 11));
      return;
    }
    const digitos = texto.replace(/\D/g, "").slice(0, 6);
    setCodigo(digitos);
    if (digitos.length === 6) void enviar(digitos); // los 6 dígitos completos: no hace falta pulsar el botón
  };

  const enviarFormulario = (e: React.FormEvent) => {
    e.preventDefault();
    const completo = usarRespaldo ? codigo.replace(/-/g, "").length === 10 : codigo.length === 6;
    if (!completo) {
      toast.error(usarRespaldo ? "El código de respaldo tiene 10 caracteres." : "Escribe los 6 dígitos.", {
        id: "login-error",
      });
      return;
    }
    void enviar(codigo);
  };

  const textoCodigos = () =>
    [
      "KondID — códigos de respaldo de la verificación en dos pasos",
      "Cada código sirve una sola vez. Guárdalos donde solo tú tengas acceso.",
      "",
      ...(sesion?.codigos_respaldo ?? []),
      "",
    ].join("\n");

  const copiarTexto = async (texto: string, aviso: string) => {
    try {
      await navigator.clipboard.writeText(texto);
      toast.success(aviso);
    } catch {
      toast.error("No se pudo copiar. Selecciona el texto y cópialo a mano.");
    }
  };

  const descargarCodigos = () => {
    const url = URL.createObjectURL(new Blob([textoCodigos()], { type: "text/plain;charset=utf-8" }));
    const enlace = document.createElement("a");
    enlace.href = url;
    enlace.download = "kondid-codigos-respaldo.txt";
    enlace.click();
    URL.revokeObjectURL(url);
  };

  const encabezado = (icono: React.ReactNode, etiqueta: string, titulo: string, texto: string) => (
    <div className="mb-4">
      <div className="flex items-center justify-between mb-3">
        <div className="w-9 h-9 rounded-xl bg-[#0071E3]/10 dark:bg-[#0071E3]/20 border border-[#0071E3]/15 flex items-center justify-center text-[#0071E3] dark:text-[#4C9BFF] shadow-xs">
          {icono}
        </div>
        <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-slate-100 dark:bg-white/5 border border-slate-200/80 dark:border-white/8 text-slate-500 dark:text-slate-400">
          {etiqueta}
        </span>
      </div>
      <h2 className="text-xl sm:text-2xl font-semibold tracking-[-0.02em] text-slate-900 dark:text-white">{titulo}</h2>
      <p className="text-xs text-slate-500 dark:text-[#86868B] mt-1 font-normal leading-relaxed">{texto}</p>
    </div>
  );

  const campoCodigo = (
    <input
      ref={campo}
      id="codigo-verificacion"
      aria-label={usarRespaldo ? "Código de respaldo" : "Código de 6 dígitos"}
      value={codigo}
      onChange={(e) => cambiarCodigo(e.target.value)}
      inputMode={usarRespaldo ? "text" : "numeric"}
      autoComplete="one-time-code"
      placeholder={usarRespaldo ? "XXXXX-XXXXX" : "000000"}
      className={claseCampo}
      disabled={cargando}
      autoFocus
    />
  );

  const ayudaCodigo = codigoRechazado && !usarRespaldo && (
    <p role="status" className="mt-2 text-[11px] leading-snug text-amber-700 dark:text-amber-300">
      ¿No funciona? Revisa que la hora de tu celular esté en automático (Ajustes › Fecha y hora) y escribe el código
      que se ve en este momento en la app, antes de que cambie.
    </p>
  );

  if (etapa === "respaldo") {
    const codigos = sesion?.codigos_respaldo ?? [];
    return (
      <div>
        {encabezado(
          <KeyRound className="w-4 h-4" />,
          "Último paso",
          "Guarda tus códigos de respaldo",
          "Si pierdes el celular, entra con uno de estos códigos en lugar del de la app. Cada uno sirve una sola vez y no se vuelven a mostrar."
        )}
        <ol className="grid grid-cols-2 gap-1.5 p-3 rounded-xl bg-slate-50/80 dark:bg-white/3 border border-slate-200/80 dark:border-white/[0.07]">
          {codigos.map((c) => (
            <li key={c} className="font-mono text-[13px] tracking-wider text-slate-900 dark:text-slate-100 text-center py-0.5">
              {c}
            </li>
          ))}
        </ol>
        <div className="grid grid-cols-2 gap-2 mt-2.5">
          <button
            type="button"
            onClick={() => copiarTexto(codigos.join("\n"), "Códigos copiados")}
            className="inline-flex items-center justify-center gap-1.5 py-2 rounded-xl text-xs font-medium border border-slate-200/90 dark:border-white/10 text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-white/5 transition-colors cursor-pointer"
          >
            <Copy className="w-3.5 h-3.5" /> Copiar
          </button>
          <button
            type="button"
            onClick={descargarCodigos}
            className="inline-flex items-center justify-center gap-1.5 py-2 rounded-xl text-xs font-medium border border-slate-200/90 dark:border-white/10 text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-white/5 transition-colors cursor-pointer"
          >
            <Download className="w-3.5 h-3.5" /> Descargar .txt
          </button>
        </div>
        <label className="flex items-start gap-2 mt-3.5 text-xs text-slate-600 dark:text-slate-300 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={guardados}
            onChange={(e) => setGuardados(e.target.checked)}
            className="mt-0.5 accent-[#0071E3]"
          />
          <span>Los guardé en un lugar seguro (un gestor de contraseñas o papel guardado).</span>
        </label>
        <button type="button" disabled={!guardados} onClick={() => sesion && onListo(sesion)} className={`${claseBoton} mt-3`}>
          <span>Entrar al panel</span>
          <ArrowRight className="w-4 h-4 stroke-2" />
        </button>
      </div>
    );
  }

  if (etapa === "configurar") {
    return (
      <form onSubmit={enviarFormulario}>
        {encabezado(
          <ShieldCheck className="w-4 h-4" />,
          "Configuración única",
          "Protege tu cuenta de administrador",
          "Las cuentas de administrador entran con la contraseña y un código que cambia cada 30 segundos en tu celular."
        )}
        <ol className="space-y-3 text-xs text-slate-700 dark:text-slate-300">
          <li className="flex gap-2.5">
            <span className={clasePaso}>1</span>
            <span className="leading-relaxed">
              Instala en tu celular una app de autenticación: Google Authenticator, Microsoft Authenticator o Authy.
            </span>
          </li>
          <li className="flex gap-2.5">
            <span className={clasePaso}>2</span>
            <div className="flex-1 min-w-0">
              <p className="leading-relaxed">Abre la app, agrega una cuenta y escanea este código.</p>
              <div className="mt-2 flex items-center gap-3">
                <div className="shrink-0 w-[132px] h-[132px] rounded-xl bg-white border border-slate-200 dark:border-white/10 flex items-center justify-center overflow-hidden">
                  {datosQr ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={datosQr.qr} alt="Código QR para vincular la app de autenticación" className="w-full h-full" />
                  ) : (
                    <Smartphone className="w-6 h-6 text-slate-300 animate-pulse" />
                  )}
                </div>
                <div className="min-w-0 text-[11px] text-slate-500 dark:text-[#86868B] leading-snug">
                  <p>¿No puedes escanearlo? Escribe esta clave en la app:</p>
                  <p
                    data-clave-2fa={datosQr?.secreto ?? ""}
                    className="mt-1 font-mono text-[11px] text-slate-900 dark:text-slate-100 break-normal select-all"
                  >
                    {datosQr ? agrupar(datosQr.secreto) : "…"}
                  </p>
                  {datosQr && (
                    <button
                      type="button"
                      onClick={() => copiarTexto(datosQr.secreto, "Clave copiada")}
                      className={`${claseEnlace} mt-1 inline-flex items-center gap-1`}
                    >
                      <Copy className="w-3 h-3" /> Copiar clave
                    </button>
                  )}
                </div>
              </div>
            </div>
          </li>
          <li className="flex gap-2.5">
            <span className={clasePaso}>3</span>
            <div className="flex-1 min-w-0">
              <p className="leading-relaxed mb-1.5">Escribe el código de 6 dígitos que muestra la app.</p>
              {campoCodigo}
              {ayudaCodigo}
            </div>
          </li>
        </ol>
        <button type="submit" disabled={cargando || !datosQr} className={`${claseBoton} mt-4`}>
          <span>{cargando ? "Verificando…" : "Activar y entrar"}</span>
          {!cargando && <ArrowRight className="w-4 h-4 stroke-2" />}
        </button>
        <button type="button" onClick={() => onVolver()} className={`${claseEnlace} mt-3 inline-flex items-center gap-1`}>
          <ArrowLeft className="w-3 h-3" /> Volver
        </button>
      </form>
    );
  }

  return (
    <form onSubmit={enviarFormulario}>
      {encabezado(
        <Smartphone className="w-4 h-4" />,
        "Paso 2 de 2",
        "Verificación en dos pasos",
        usarRespaldo
          ? "Escribe uno de tus códigos de respaldo. Cada uno sirve una sola vez."
          : "Escribe el código de 6 dígitos que muestra tu app de autenticación."
      )}
      {campoCodigo}
      {ayudaCodigo}
      <button type="submit" disabled={cargando} className={`${claseBoton} mt-3`}>
        <span>{cargando ? "Verificando…" : "Verificar"}</span>
        {!cargando && <ArrowRight className="w-4 h-4 stroke-2" />}
      </button>
      <div className="flex items-center justify-between mt-3">
        <button type="button" onClick={() => onVolver()} className={`${claseEnlace} inline-flex items-center gap-1`}>
          <ArrowLeft className="w-3 h-3" /> Volver
        </button>
        <button
          type="button"
          onClick={() => {
            setUsarRespaldo(!usarRespaldo);
            setCodigo("");
            campo.current?.focus();
          }}
          className={claseEnlace}
        >
          {usarRespaldo ? "Usar el código de la app" : "¿Sin celular? Usa un código de respaldo"}
        </button>
      </div>
    </form>
  );
}
