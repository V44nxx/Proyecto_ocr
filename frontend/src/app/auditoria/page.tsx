"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { History, RefreshCw, Search, ShieldAlert, ChevronLeft, ChevronRight } from "lucide-react";
import Sidebar from "@/components/ui/Sidebar";
import EncabezadoPagina from "@/components/ui/EncabezadoPagina";
import { useSidebar } from "@/context/SidebarContext";
import { apiAuth, getErrorMessage } from "@/lib/api";
import { auth } from "@/lib/auth";
import SelectorModal, { type OpcionSelector } from "@/components/ui/SelectorModal";
import type { RegistroAuditoria } from "@/types";
import toast from "react-hot-toast";

const POR_PAGINA = 50;

type Tipo = "alerta" | "datos" | "cuenta" | "sesion";

const ACCIONES: Record<string, { etiqueta: string; tipo: Tipo }> = {
  login_exitoso: { etiqueta: "Inicio de sesión", tipo: "sesion" },
  login_fallido: { etiqueta: "Inicio de sesión fallido", tipo: "alerta" },
  logout: { etiqueta: "Cierre de sesión", tipo: "sesion" },
  login_bloqueado: { etiqueta: "Bloqueo por intentos", tipo: "alerta" },
  "2fa_fallido": { etiqueta: "Código de verificación equivocado", tipo: "alerta" },
  "2fa_activado": { etiqueta: "Verificación en dos pasos activada", tipo: "cuenta" },
  "2fa_restablecido_admin": { etiqueta: "Verificación restablecida por el administrador", tipo: "cuenta" },
  "2fa_restablecido_consola": { etiqueta: "Verificación restablecida desde el servidor", tipo: "cuenta" },
  acceso_denegado: { etiqueta: "Acceso denegado", tipo: "alerta" },
  enlace_recuperacion_invalido: { etiqueta: "Enlace de recuperación inválido", tipo: "alerta" },
  cambio_contrasena_fallido: { etiqueta: "Cambio de contraseña fallido", tipo: "alerta" },
  usuario_creado: { etiqueta: "Usuario creado", tipo: "cuenta" },
  usuario_eliminado: { etiqueta: "Usuario eliminado", tipo: "cuenta" },
  contrasena_cambiada: { etiqueta: "Contraseña cambiada", tipo: "cuenta" },
  contrasena_restablecida_admin: { etiqueta: "Contraseña restablecida por el administrador", tipo: "cuenta" },
  recuperacion_solicitada: { etiqueta: "Recuperación de contraseña solicitada", tipo: "cuenta" },
  contrasena_restablecida_correo: { etiqueta: "Contraseña restablecida por correo", tipo: "cuenta" },
  exportacion_personas: { etiqueta: "Exportación de personas", tipo: "datos" },
  exportacion_diferencias: { etiqueta: "Exportación de diferencias", tipo: "datos" },
  exportacion_reporte_comparacion: { etiqueta: "Reporte de comparación", tipo: "datos" },
  persona_editada: { etiqueta: "Persona editada", tipo: "datos" },
  persona_eliminada: { etiqueta: "Persona eliminada", tipo: "datos" },
  personas_eliminadas: { etiqueta: "Personas eliminadas", tipo: "datos" },
  ficha_eliminada: { etiqueta: "Ficha eliminada", tipo: "datos" },
};

const CLASES_TIPO: Record<Tipo, string> = {
  alerta: "bg-amber-500/10 text-amber-700 dark:text-amber-400 border-amber-500/20",
  datos: "bg-[#0071E3]/10 text-[#0071E3] dark:text-blue-400 border-[#0071E3]/20",
  cuenta: "bg-slate-100 dark:bg-white/6 text-slate-700 dark:text-slate-300 border-slate-200/80 dark:border-white/8",
  sesion: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-500/20",
};

// Filtro por acción: agrupadas por tipo, con el color de su etiqueta en la tabla
const GRUPOS_TIPO: Record<Tipo, { nombre: string; color: string }> = {
  sesion: { nombre: "Sesiones", color: "bg-emerald-500" },
  alerta: { nombre: "Alertas de seguridad", color: "bg-amber-500" },
  cuenta: { nombre: "Cuentas y contraseñas", color: "bg-slate-400" },
  datos: { nombre: "Datos personales", color: "bg-[#0071E3]" },
};
const ORDEN_TIPOS: Tipo[] = ["sesion", "alerta", "cuenta", "datos"];
const OPCIONES_ACCION: OpcionSelector[] = [
  { valor: "", etiqueta: "Todas las acciones", descripcion: "Sin filtrar" },
  ...ORDEN_TIPOS.flatMap((tipo) =>
    Object.entries(ACCIONES)
      .filter(([, a]) => a.tipo === tipo)
      .map(([valor, a]) => ({ valor, etiqueta: a.etiqueta, grupo: GRUPOS_TIPO[tipo].nombre, color: GRUPOS_TIPO[tipo].color }))
  ),
];

const NOMBRES_DETALLE: Record<string, string> = {
  campos: "Campos",
  cantidad: "Cantidad",
  modo: "Modo",
  persona_id: "Persona",
  documento_id: "Ficha",
  comparacion_id: "Comparación",
  ruta: "Ruta",
  usuario_creado: "Usuario",
  rol: "Rol",
  usuario_eliminado: "Usuario",
  usuario_eliminado_id: "Id",
  fichas: "Fichas",
  personas: "Personas",
  usuario_afectado: "Usuario",
  cuenta_existe: "Cuenta existe",
  filtros: "Filtros",
  personas_seleccionadas: "Seleccionadas",
};

function textoValor(valor: unknown): string {
  if (typeof valor === "boolean") return valor ? "sí" : "no";
  if (Array.isArray(valor)) return valor.join(", ");
  if (valor && typeof valor === "object") {
    const partes = Object.entries(valor as Record<string, unknown>).map(([k, v]) => `${k}: ${textoValor(v)}`);
    return partes.length ? partes.join(", ") : "ninguno";
  }
  const texto = String(valor);
  // Los ids completos no aportan en la tabla: basta con el comienzo para buscarlos
  return /^[0-9a-f]{8}-[0-9a-f-]{27}$/i.test(texto) ? `${texto.slice(0, 8)}…` : texto;
}

function textoDetalle(detalle: RegistroAuditoria["detalle"]): string {
  if (!detalle) return "—";
  return Object.entries(detalle)
    .map(([clave, valor]) => `${NOMBRES_DETALLE[clave] ?? clave}: ${textoValor(valor)}`)
    .join(" · ");
}

export default function AuditoriaPage() {
  const router = useRouter();
  const { collapsed } = useSidebar();
  const [registros, setRegistros] = useState<RegistroAuditoria[]>([]);
  const [total, setTotal] = useState(0);
  const [desde, setDesde] = useState(0);
  const [accion, setAccion] = useState("");
  const [email, setEmail] = useState("");
  const [emailAplicado, setEmailAplicado] = useState("");
  const [cargando, setCargando] = useState(true);
  const [permitido, setPermitido] = useState(false);

  useEffect(() => {
    if (!auth.isAuthenticated()) {
      router.push("/");
      return;
    }
    if (auth.getUsuario()?.rol !== "admin") {
      toast.error("Acceso restringido a administradores");
      router.push("/dashboard");
      return;
    }
    setPermitido(true);
  }, [router]);

  const cargar = useCallback(async () => {
    setCargando(true);
    try {
      const res = await apiAuth.auditoria({
        limite: POR_PAGINA,
        desde,
        accion: accion || undefined,
        email: emailAplicado || undefined,
      });
      setRegistros(res.data.registros);
      setTotal(res.data.total);
    } catch (err: unknown) {
      toast.error(getErrorMessage(err, "No se pudo cargar la auditoría"));
    } finally {
      setCargando(false);
    }
  }, [desde, accion, emailAplicado]);

  useEffect(() => {
    if (permitido) cargar();
  }, [permitido, cargar]);

  const filtrarPorCorreo = (e: React.FormEvent) => {
    e.preventDefault();
    setDesde(0);
    setEmailAplicado(email.trim());
  };

  const hasta = Math.min(desde + registros.length, total);

  return (
    <div className="flex min-h-screen">
      <Sidebar />

      <main className={`${collapsed ? "ml-20" : "ml-64"} transition-all duration-300 ease-in-out flex-1 p-8 min-w-0`}>
        <EncabezadoPagina
          icono={<History />}
          seccion="Control de acceso"
          titulo="Auditoría"
          descripcion="Quién hizo qué y cuándo: inicios de sesión, cambios de contraseña, exportaciones y eliminaciones."
          acciones={
            <button onClick={cargar} disabled={cargando} className="btn-secondary text-sm py-2.5 px-4" title="Recargar">
              <RefreshCw className={`w-4 h-4 ${cargando ? "animate-spin text-primary-400" : ""}`} />
              <span>Actualizar</span>
            </button>
          }
        />

        <div className="relative rounded-2xl bg-white/70 dark:bg-[#121620]/60 backdrop-blur-xl border border-slate-200/80 dark:border-white/8 shadow-[0_2px_12px_rgba(0,0,0,0.03)] p-6 overflow-hidden">
          <div className="absolute inset-x-0 top-0 h-px bg-linear-to-r from-transparent via-slate-300/40 dark:via-white/10 to-transparent pointer-events-none" />

          <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 mb-6">
            <div>
              <h2 className="text-base font-semibold text-slate-900 dark:text-white">Registro de actividad</h2>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                Se conserva un año. No guarda contraseñas, cédulas ni nombres de las personas.
              </p>
            </div>

            <div className="flex flex-col sm:flex-row gap-3">
              <SelectorModal
                id="filtro-accion"
                titulo="Filtrar por acción"
                descripcion="Muestra solo un tipo de registro de la auditoría."
                tema="reconocimiento"
                valor={accion}
                opciones={OPCIONES_ACCION}
                onCambiar={(valor) => {
                  setDesde(0);
                  setAccion(valor);
                }}
                className="w-full sm:w-64"
              />

              <form onSubmit={filtrarPorCorreo} className="relative w-full sm:w-72">
                <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400" />
                <input
                  type="email"
                  placeholder="Filtrar por correo y Enter"
                  aria-label="Filtrar por correo"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full bg-slate-100/80 dark:bg-white/4 border border-slate-200/80 dark:border-white/8 rounded-xl pl-9 pr-3.5 py-2 text-xs text-slate-900 dark:text-white focus:outline-hidden focus:ring-2 focus:ring-[#0071E3]/20 focus:border-[#0071E3] transition-all"
                />
              </form>
            </div>
          </div>

          {cargando && registros.length === 0 ? (
            <div className="py-16 text-center text-slate-500">
              <div className="spinner mx-auto mb-3" />
              <p className="text-xs">Cargando registros...</p>
            </div>
          ) : registros.length === 0 ? (
            <div className="py-16 text-center">
              <ShieldAlert className="w-10 h-10 text-slate-400 mx-auto mb-2 opacity-50" />
              <p className="text-slate-700 dark:text-slate-300 font-medium text-sm">No hay registros</p>
              <p className="text-slate-500 text-xs mt-1">
                {accion || emailAplicado ? "Prueba con otros filtros" : "Las acciones aparecerán aquí a medida que ocurran"}
              </p>
            </div>
          ) : (
            <>
              <div className="table-container">
                <table className="table-base">
                  <thead>
                    <tr>
                      <th>Fecha</th>
                      <th>Usuario</th>
                      <th>Acción</th>
                      <th>IP</th>
                      <th>Detalle</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-white/4 [&>tr:last-child]:border-b-0">
                    {registros.map((r, i) => {
                      const info = ACCIONES[r.accion] ?? { etiqueta: r.accion, tipo: "cuenta" as Tipo };
                      return (
                        <tr key={`${r.fecha}-${i}`} className="hover:bg-slate-50/60 dark:hover:bg-white/2 transition-colors">
                          <td className="px-4 py-3 text-xs text-slate-500 dark:text-slate-400 whitespace-nowrap">
                            {new Date(r.fecha).toLocaleString("es-CO", {
                              year: "numeric",
                              month: "short",
                              day: "numeric",
                              hour: "2-digit",
                              minute: "2-digit",
                              second: "2-digit",
                            })}
                          </td>
                          <td className="px-4 py-3 text-xs text-slate-700 dark:text-slate-300">{r.email || "—"}</td>
                          <td className="px-4 py-3">
                            <span className={`inline-flex px-2 py-0.5 rounded-full text-[10px] font-medium border whitespace-nowrap ${CLASES_TIPO[info.tipo]}`}>
                              {info.etiqueta}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-xs font-mono text-slate-500 dark:text-slate-400">{r.ip || "—"}</td>
                          <td className="px-4 py-3 text-xs text-slate-500 dark:text-slate-400 wrap-break-word max-w-md">
                            {textoDetalle(r.detalle)}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              <div className="flex items-center justify-between mt-4 text-xs text-slate-500 dark:text-slate-400">
                <span>
                  {desde + 1}–{hasta} de {total}
                </span>
                <div className="flex gap-2">
                  <button
                    onClick={() => setDesde(Math.max(0, desde - POR_PAGINA))}
                    disabled={desde === 0 || cargando}
                    className="btn-secondary text-xs py-1.5 px-3"
                    aria-label="Página anterior"
                  >
                    <ChevronLeft className="w-3.5 h-3.5" />
                    <span>Anterior</span>
                  </button>
                  <button
                    onClick={() => setDesde(desde + POR_PAGINA)}
                    disabled={hasta >= total || cargando}
                    className="btn-secondary text-xs py-1.5 px-3"
                    aria-label="Página siguiente"
                  >
                    <span>Siguiente</span>
                    <ChevronRight className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            </>
          )}
        </div>
      </main>
    </div>
  );
}
