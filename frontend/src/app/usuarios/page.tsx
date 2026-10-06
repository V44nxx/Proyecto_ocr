"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ShieldCheck,
  UserPlus,
  Users,
  Search,
  Trash2,
  RefreshCw,
  Mail,
  Calendar,
  Shield,
  UserCheck,
  AlertTriangle,
} from "lucide-react";
import Sidebar from "@/components/ui/Sidebar";
import { useSidebar } from "@/context/SidebarContext";
import ModalCrearUsuario from "@/components/ui/ModalCrearUsuario";
import { apiAuth, getErrorMessage } from "@/lib/api";
import { auth } from "@/lib/auth";
import type { Usuario } from "@/types";
import toast from "react-hot-toast";

export default function UsuariosPage() {
  const router = useRouter();
  const { collapsed } = useSidebar();
  const [usuarios, setUsuarios] = useState<Usuario[]>([]);
  const [cargando, setCargando] = useState(true);
  const [busqueda, setBusqueda] = useState("");
  const [modalAbierto, setModalAbierto] = useState(false);
  const [usuarioAEliminar, setUsuarioAEliminar] = useState<Usuario | null>(null);
  const [eliminando, setEliminando] = useState(false);
  const [usuarioActual, setUsuarioActual] = useState<Usuario | null>(null);

  useEffect(() => {
    if (!auth.isAuthenticated()) {
      router.push("/");
      return;
    }

    const uActual = auth.getUsuario();
    setUsuarioActual(uActual);

    if (uActual && uActual.rol !== "admin") {
      toast.error("Acceso restringido a administradores");
      router.push("/dashboard");
      return;
    }

    cargarUsuarios();
  }, []);

  const cargarUsuarios = async () => {
    setCargando(true);
    try {
      const res = await apiAuth.getUsuarios();
      setUsuarios(res.data);
    } catch (err: unknown) {
      console.warn("No se pudo obtener lista de usuarios desde API:", err);
      // Fallback elegante en caso de sincronización inicial
      const uActual = auth.getUsuario();
      if (uActual) {
        setUsuarios([uActual]);
      }
    } finally {
      setCargando(false);
    }
  };

  const confirmarEliminar = async () => {
    if (!usuarioAEliminar) return;

    if (usuarioActual && usuarioActual.id === usuarioAEliminar.id) {
      toast.error("No puedes eliminar tu propia cuenta");
      setUsuarioAEliminar(null);
      return;
    }

    setEliminando(true);
    try {
      await apiAuth.eliminarUsuario(usuarioAEliminar.id);
      toast.success(`Usuario ${usuarioAEliminar.email} eliminado`);
      setUsuarios((prev) => prev.filter((u) => u.id !== usuarioAEliminar.id));
      setUsuarioAEliminar(null);
    } catch (err: unknown) {
      const msg = getErrorMessage(err, "No se pudo eliminar el usuario");
      toast.error(msg);
    } finally {
      setEliminando(false);
    }
  };

  const usuariosFiltrados = usuarios.filter((u) => {
    const term = busqueda.toLowerCase().trim();
    if (!term) return true;
    return (
      u.email.toLowerCase().includes(term) ||
      (u.nombre && u.nombre.toLowerCase().includes(term)) ||
      u.rol.toLowerCase().includes(term)
    );
  });

  const totalAdmins = usuarios.filter((u) => u.rol === "admin").length;
  const totalOperadores = usuarios.filter((u) => u.rol === "usuario").length;

  return (
    <div className="flex min-h-screen">
      <Sidebar />

      <main className={`${collapsed ? "ml-20" : "ml-64"} transition-all duration-300 ease-in-out flex-1 p-8 min-w-0`}>
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-8 page-enter">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <ShieldCheck className="w-5 h-5 text-primary-400" />
              <span className="text-primary-400 text-sm font-medium">Control de Acceso</span>
            </div>
            <h1 className="text-3xl font-bold text-white">Gestión de Usuarios</h1>
            <p className="text-slate-400 mt-1 text-sm">
              Crea credenciales con correo y contraseña para habilitar el acceso al login general.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={cargarUsuarios}
              disabled={cargando}
              className="btn-secondary text-sm py-2.5 px-4"
              title="Recargar usuarios"
            >
              <RefreshCw className={`w-4 h-4 ${cargando ? "animate-spin text-primary-400" : ""}`} />
              <span>Actualizar</span>
            </button>

            <button
              onClick={() => setModalAbierto(true)}
              className="btn-primary text-sm py-2.5 px-5 shadow-lg shadow-primary-950/40"
            >
              <UserPlus className="w-4 h-4" />
              <span>+ Nuevo Usuario</span>
            </button>
          </div>
        </div>

        {/* Tarjetas de Resumen */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5 mb-8">
          <div className="relative rounded-2xl bg-white/70 dark:bg-[#121620]/60 backdrop-blur-xl border border-slate-200/80 dark:border-white/[0.08] shadow-[0_2px_12px_rgba(0,0,0,0.03)] p-5 overflow-hidden">
            <div className="absolute inset-x-0 top-0 h-[1px] bg-gradient-to-r from-transparent via-slate-300/40 dark:via-white/10 to-transparent pointer-events-none" />
            <div className="flex items-start justify-between">
              <div>
                <p className="text-[11px] font-medium uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-1">Total de Usuarios</p>
                <p className="text-2xl font-bold tracking-[-0.04em] text-slate-900 dark:text-white">{usuarios.length}</p>
                <p className="text-xs text-slate-400 mt-1">Cuentas con acceso al sistema</p>
              </div>
              <div className="w-9 h-9 rounded-xl flex items-center justify-center bg-slate-100 dark:bg-white/[0.06] text-slate-700 dark:text-slate-300 border border-slate-200/80 dark:border-white/[0.08]">
                <Users className="w-4 h-4" />
              </div>
            </div>
          </div>

          <div className="relative rounded-2xl bg-white/70 dark:bg-[#121620]/60 backdrop-blur-xl border border-slate-200/80 dark:border-white/[0.08] shadow-[0_2px_12px_rgba(0,0,0,0.03)] p-5 overflow-hidden">
            <div className="absolute inset-x-0 top-0 h-[1px] bg-gradient-to-r from-transparent via-slate-300/40 dark:via-white/10 to-transparent pointer-events-none" />
            <div className="flex items-start justify-between">
              <div>
                <p className="text-[11px] font-medium uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-1">Administradores</p>
                <p className="text-2xl font-bold tracking-[-0.04em] text-slate-900 dark:text-white">{totalAdmins}</p>
                <p className="text-xs text-slate-400 mt-1">Control total del sistema</p>
              </div>
              <div className="w-9 h-9 rounded-xl flex items-center justify-center bg-slate-100 dark:bg-white/[0.06] text-slate-700 dark:text-slate-300 border border-slate-200/80 dark:border-white/[0.08]">
                <Shield className="w-4 h-4" />
              </div>
            </div>
          </div>

          <div className="relative rounded-2xl bg-white/70 dark:bg-[#121620]/60 backdrop-blur-xl border border-slate-200/80 dark:border-white/[0.08] shadow-[0_2px_12px_rgba(0,0,0,0.03)] p-5 overflow-hidden">
            <div className="absolute inset-x-0 top-0 h-[1px] bg-gradient-to-r from-transparent via-slate-300/40 dark:via-white/10 to-transparent pointer-events-none" />
            <div className="flex items-start justify-between">
              <div>
                <p className="text-[11px] font-medium uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-1">Operadores / Estándar</p>
                <p className="text-2xl font-bold tracking-[-0.04em] text-emerald-600 dark:text-emerald-400">{totalOperadores}</p>
                <p className="text-xs text-slate-400 mt-1">Subida y procesamiento OCR</p>
              </div>
              <div className="w-9 h-9 rounded-xl flex items-center justify-center bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
                <UserCheck className="w-4 h-4" />
              </div>
            </div>
          </div>
        </div>

        {/* Tabla y Filtros */}
        <div className="relative rounded-2xl bg-white/70 dark:bg-[#121620]/60 backdrop-blur-xl border border-slate-200/80 dark:border-white/[0.08] shadow-[0_2px_12px_rgba(0,0,0,0.03)] p-6 overflow-hidden">
          <div className="absolute inset-x-0 top-0 h-[1px] bg-gradient-to-r from-transparent via-slate-300/40 dark:via-white/10 to-transparent pointer-events-none" />
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
            <div>
              <h2 className="text-base font-semibold text-slate-900 dark:text-white">Usuarios del Sistema</h2>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                Cuentas registradas para autenticación en KondID
              </p>
            </div>

            <div className="relative w-full sm:w-72">
              <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400" />
              <input
                type="text"
                placeholder="Buscar por correo o nombre..."
                value={busqueda}
                onChange={(e) => setBusqueda(e.target.value)}
                className="w-full bg-slate-100/80 dark:bg-white/[0.04] border border-slate-200/80 dark:border-white/[0.08] rounded-xl pl-9 pr-3.5 py-2 text-xs text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-[#0071E3]/20 focus:border-[#0071E3] transition-all"
              />
            </div>
          </div>

          {cargando ? (
            <div className="py-16 text-center text-slate-500">
              <div className="spinner mx-auto mb-3" />
              <p className="text-xs">Cargando lista de usuarios...</p>
            </div>
          ) : usuariosFiltrados.length === 0 ? (
            <div className="py-16 text-center">
              <Users className="w-10 h-10 text-slate-400 mx-auto mb-2 opacity-50" />
              <p className="text-slate-700 dark:text-slate-300 font-medium text-sm">No se encontraron usuarios</p>
              <p className="text-slate-500 text-xs mt-1">
                {busqueda ? "Intenta con otro término de búsqueda" : "Agrega el primer usuario"}
              </p>
              <button
                onClick={() => setModalAbierto(true)}
                className="btn-primary text-xs py-2 px-4 mx-auto mt-4 inline-flex active:scale-[0.98]"
              >
                <UserPlus className="w-3.5 h-3.5" />
                <span>Agregar Usuario</span>
              </button>
            </div>
          ) : (
            <div className="table-container">
              <table className="table-base">
                <thead>
                  <tr>
                    <th>Usuario</th>
                    <th>Correo Electrónico</th>
                    <th>Rol</th>
                    <th>Estado</th>
                    <th>Fecha de Registro</th>
                    <th className="text-right">Acciones</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-white/[0.04]">
                  {usuariosFiltrados.map((u) => {
                    const esActual = usuarioActual?.id === u.id;
                    const esAdmin = u.rol === "admin";
                    const iniciales = (u.nombre || u.email)
                      .split(" ")
                      .map((p) => p[0])
                      .join("")
                      .toUpperCase()
                      .slice(0, 2);

                    return (
                      <tr key={u.id} className="hover:bg-slate-50/60 dark:hover:bg-white/[0.02] transition-colors">
                        {/* Avatar y Nombre */}
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-3">
                            <div className="w-8 h-8 rounded-full bg-slate-200 dark:bg-white/[0.08] text-slate-700 dark:text-slate-200 flex items-center justify-center text-xs font-semibold shrink-0">
                              {iniciales}
                            </div>
                            <div>
                              <p className="text-xs font-semibold text-slate-900 dark:text-white flex items-center gap-1.5">
                                {u.nombre || u.email.split("@")[0]}
                                {esActual && (
                                  <span className="text-[9px] px-1.5 py-0.2 rounded-full bg-[#0071E3]/10 text-[#0071E3] font-medium">
                                    Tú
                                  </span>
                                )}
                              </p>
                              <span className="text-[11px] text-slate-400 block sm:hidden">
                                {u.email}
                              </span>
                            </div>
                          </div>
                        </td>

                        {/* Email */}
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-1.5 text-xs text-slate-600 dark:text-slate-300">
                            <Mail className="w-3.5 h-3.5 text-slate-400" />
                            <span>{u.email}</span>
                          </div>
                        </td>

                        {/* Rol */}
                        <td className="px-4 py-3">
                          {esAdmin ? (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-slate-100 dark:bg-white/[0.06] text-slate-700 dark:text-slate-300 border border-slate-200/80 dark:border-white/[0.08]">
                              <Shield className="w-3 h-3 text-slate-400" />
                              Administrador
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-[#0071E3]/10 text-[#0071E3] dark:text-blue-400 border border-[#0071E3]/20">
                              <UserCheck className="w-3 h-3 text-[#0071E3]" />
                              Operador
                            </span>
                          )}
                        </td>

                        {/* Estado */}
                        <td className="px-4 py-3">
                          <span className="inline-flex items-center gap-1.5 text-xs text-emerald-600 dark:text-emerald-400 font-medium">
                            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                            Activo
                          </span>
                        </td>

                        {/* Fecha */}
                        <td className="px-4 py-3.5 text-xs text-slate-400">
                          <div className="flex items-center gap-1.5">
                            <Calendar className="w-3.5 h-3.5 text-slate-500" />
                            <span>
                              {u.fecha_creacion
                                ? new Date(u.fecha_creacion).toLocaleDateString("es-CO", {
                                    year: "numeric",
                                    month: "short",
                                    day: "numeric",
                                  })
                                : "N/D"}
                            </span>
                          </div>
                        </td>

                        {/* Acciones */}
                        <td className="px-4 py-3.5 text-right">
                          {!esActual && (
                            <button
                              onClick={() => setUsuarioAEliminar(u)}
                              className="p-1.5 text-slate-500 hover:text-rose-400 hover:bg-rose-500/10 rounded-lg transition-colors"
                              title="Eliminar usuario"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </main>

      {/* Modal Crear Usuario */}
      <ModalCrearUsuario
        isOpen={modalAbierto}
        onClose={() => setModalAbierto(false)}
        onUsuarioCreado={(nuevo) => {
          setUsuarios((prev) => [nuevo, ...prev]);
        }}
      />

      {/* Modal Confirmación de Eliminación */}
      {usuarioAEliminar && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-fade-in">
          <div className="w-full max-w-md bg-dark-900 border border-white/10 rounded-2xl p-6 shadow-2xl">
            <div className="w-12 h-12 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400 flex items-center justify-center mx-auto mb-4">
              <AlertTriangle className="w-6 h-6" />
            </div>
            <h3 className="text-lg font-bold text-white text-center mb-2">
              ¿Eliminar usuario?
            </h3>
            <p className="text-sm text-slate-400 text-center mb-6">
              ¿Estás seguro de que deseas revocar el acceso a{" "}
              <strong className="text-white">{usuarioAEliminar.email}</strong>? El usuario ya no
              podrá iniciar sesión en el sistema.
            </p>
            <div className="flex items-center justify-end gap-3">
              <button
                type="button"
                onClick={() => setUsuarioAEliminar(null)}
                disabled={eliminando}
                className="btn-secondary text-sm py-2 px-4"
              >
                Cancelar
              </button>
              <button
                type="button"
                onClick={confirmarEliminar}
                disabled={eliminando}
                className="btn-danger text-sm py-2 px-4 flex items-center gap-2"
              >
                {eliminando ? "Eliminando..." : "Sí, eliminar acceso"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
