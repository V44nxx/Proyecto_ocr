"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
  LayoutDashboard,
  FileText,
  Users,
  Download,
  GitCompare,
  LogOut,
  Cpu,
  ShieldCheck,
  UserPlus,
  Sun,
  Moon,
  PanelLeftClose,
  PanelLeftOpen,
} from "lucide-react";
import { auth } from "@/lib/auth";
import toast from "react-hot-toast";
import ModalCrearUsuario from "@/components/ui/ModalCrearUsuario";
import { useTheme } from "@/context/ThemeContext";
import { useSidebar } from "@/context/SidebarContext";

interface NavItem {
  href: string;
  icon: React.ReactNode;
  label: string;
  adminOnly?: boolean;
}

const navItems: NavItem[] = [
  { href: "/dashboard", icon: <LayoutDashboard className="w-4 h-4" />, label: "Dashboard" },
  { href: "/documentos", icon: <FileText className="w-4 h-4" />, label: "Documentos PDF" },
  { href: "/personas", icon: <Users className="w-4 h-4" />, label: "Personas" },
  { href: "/exportacion", icon: <Download className="w-4 h-4" />, label: "Exportación" },
  { href: "/comparacion", icon: <GitCompare className="w-4 h-4" />, label: "Comparación" },
  { href: "/usuarios", icon: <ShieldCheck className="w-4 h-4" />, label: "Usuarios", adminOnly: true },
];

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { theme, toggleTheme } = useTheme();
  const { collapsed, toggleSidebar } = useSidebar();
  const [usuario, setUsuario] = useState<{ nombre: string; email: string; rol: string } | null>(null);
  const [modalUsuarioAbierto, setModalUsuarioAbierto] = useState(false);

  useEffect(() => {
    setUsuario(auth.getUsuario());
  }, []);

  const cerrarSesion = () => {
    auth.cerrarSesion();
    toast.success("Sesión cerrada");
    router.push("/");
  };

  const toggleThemeWithToast = (e: React.MouseEvent) => {
    const targetTheme = theme === "dark" ? "light" : "dark";
    toggleTheme(e);
    setTimeout(() => {
      toast(targetTheme === "light" ? "Modo Claro activado" : "Modo Oscuro activado", {
        duration: 2000,
        icon: targetTheme === "light" ? (
          <Sun className="w-4 h-4 text-amber-500 shrink-0" />
        ) : (
          <Moon className="w-4 h-4 text-blue-400 shrink-0" />
        ),
        className: "text-xs font-semibold !rounded-xl !border !border-slate-300 dark:!border-slate-700 !shadow-md",
      });
    }, 520);
  };

  const obtenerIniciales = (nombre?: string) => {
    if (!nombre) return "U";
    const partes = nombre.trim().split(" ");
    if (partes.length >= 2 && partes[0] && partes[1]) {
      return (partes[0][0] + partes[1][0]).toUpperCase();
    }
    return nombre.slice(0, 2).toUpperCase();
  };

  const itemsVisibles = navItems.filter(
    (item) => !item.adminOnly || usuario?.rol === "admin"
  );

  return (
    <>
      <aside
        className={`sidebar z-40 border-r border-slate-200 dark:border-white/[0.06] overflow-x-hidden ${
          collapsed ? "collapsed" : "expanded"
        }`}
        suppressHydrationWarning
      >
        {/* ── Logo & Toggle ─────────────────────────────────────── */}
        {!collapsed ? (
          <div className="px-4 py-4 border-b border-slate-200 dark:border-white/[0.06] flex items-center justify-between min-w-0">
            <div className="flex items-center gap-3 min-w-0">
              <div
                className="w-9 h-9 rounded-xl bg-primary-500/10 dark:bg-primary-600/20 border border-primary-500/30 flex items-center justify-center text-primary-600 dark:text-primary-400 shrink-0"
                style={{ boxShadow: "0 0 15px rgba(59,130,246,0.2)" }}
              >
                <Cpu className="w-4 h-4" />
              </div>
              <div className="min-w-0">
                <span className="text-sm font-bold text-slate-900 dark:text-white block truncate">
                  Sistema OCR
                </span>
                <span className="text-[10px] text-slate-500 dark:text-slate-400 block truncate">
                  Documentos CO
                </span>
              </div>
            </div>
            <button
              onClick={toggleSidebar}
              title="Ocultar menú lateral"
              aria-label="Ocultar menú lateral"
              className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors shrink-0 cursor-pointer"
            >
              <PanelLeftClose className="w-4 h-4" />
            </button>
          </div>
        ) : (
          <div className="py-4 border-b border-slate-200 dark:border-white/[0.06] flex flex-col items-center gap-2">
            <div
              className="w-9 h-9 rounded-xl bg-primary-500/10 dark:bg-primary-600/20 border border-primary-500/30 flex items-center justify-center text-primary-600 dark:text-primary-400 shrink-0"
              title="Sistema OCR - Documentos CO"
              style={{ boxShadow: "0 0 15px rgba(59,130,246,0.2)" }}
            >
              <Cpu className="w-4 h-4" />
            </div>
            <button
              onClick={toggleSidebar}
              title="Expandir menú lateral"
              aria-label="Expandir menú lateral"
              className="p-1.5 rounded-lg text-slate-400 hover:text-primary-600 dark:hover:text-white hover:bg-primary-50 dark:hover:bg-slate-800 transition-colors flex items-center justify-center cursor-pointer"
            >
              <PanelLeftOpen className="w-4 h-4" />
            </button>
          </div>
        )}

        {/* ── Navegación ────────────────────────────────────────── */}
        {!collapsed ? (
          <nav className="flex-1 py-4 px-3 space-y-1 overflow-y-auto overflow-x-hidden">
            <p className="px-2 mb-2 text-[10px] font-bold text-slate-400 dark:text-slate-600 uppercase tracking-widest truncate">
              Módulos
            </p>
            {itemsVisibles.map((item) => {
              const isActive = pathname === item.href;
              return (
                <button
                  key={item.href}
                  onClick={() => router.push(item.href)}
                  className={`sidebar-item ${isActive ? "active" : ""}`}
                  title={item.label}
                >
                  <span
                    className={`shrink-0 ${
                      isActive
                        ? "text-primary-600 dark:text-primary-400"
                        : "text-slate-400 dark:text-slate-500"
                    }`}
                  >
                    {item.icon}
                  </span>
                  <span className="flex-1 text-left truncate">{item.label}</span>
                  {item.adminOnly && (
                    <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-600 dark:text-purple-300 border border-purple-500/30 shrink-0">
                      Admin
                    </span>
                  )}
                </button>
              );
            })}

            {/* Botón rápido para agregar usuario si es admin */}
            {usuario?.rol === "admin" && (
              <div className="pt-3">
                <button
                  onClick={() => setModalUsuarioAbierto(true)}
                  className="w-full flex items-center justify-center gap-2 px-3 py-2.5 rounded-xl text-xs font-semibold bg-gradient-to-r from-primary-600 to-blue-700 hover:from-primary-500 hover:to-blue-600 text-white shadow-lg shadow-primary-950/20 border border-primary-400/30 transition-all hover:scale-[1.01] active:scale-98 cursor-pointer"
                  title="Agregar nuevo usuario al sistema"
                >
                  <UserPlus className="w-3.5 h-3.5 shrink-0" />
                  <span className="truncate">+ Agregar Usuario</span>
                </button>
              </div>
            )}
          </nav>
        ) : (
          <nav className="flex-1 py-4 px-2 space-y-2 overflow-y-auto overflow-x-hidden flex flex-col items-center">
            {itemsVisibles.map((item) => {
              const isActive = pathname === item.href;
              return (
                <button
                  key={item.href}
                  onClick={() => router.push(item.href)}
                  className={`relative w-11 h-11 rounded-xl flex items-center justify-center transition-all duration-200 cursor-pointer ${
                    isActive
                      ? "bg-primary-500/15 text-primary-600 dark:text-primary-400 border border-primary-500/30 shadow-sm"
                      : "text-slate-600 dark:text-slate-400 hover:text-slate-950 dark:hover:text-white hover:bg-slate-200/70 dark:hover:bg-slate-800/80"
                  }`}
                  title={item.label}
                  aria-label={item.label}
                >
                  <span className="shrink-0">{item.icon}</span>
                  {item.adminOnly && (
                    <span
                      className="absolute top-2 right-2 w-2 h-2 rounded-full bg-purple-500 ring-2 ring-slate-900"
                      title="Módulo exclusivo para Administradores"
                    />
                  )}
                </button>
              );
            })}

            {/* Botón rápido para agregar usuario (colapsado) */}
            {usuario?.rol === "admin" && (
              <div className="pt-2">
                <button
                  onClick={() => setModalUsuarioAbierto(true)}
                  className="w-11 h-11 mx-auto flex items-center justify-center rounded-xl bg-gradient-to-r from-primary-600 to-blue-700 hover:from-primary-500 hover:to-blue-600 text-white shadow-md border border-primary-400/30 transition-all hover:scale-105 active:scale-95 cursor-pointer"
                  title="Agregar nuevo usuario"
                  aria-label="Agregar nuevo usuario"
                >
                  <UserPlus className="w-4 h-4" />
                </button>
              </div>
            )}
          </nav>
        )}

        {/* ── Footer: Tema, Usuario y Logout ───────────────────── */}
        {!collapsed ? (
          <div className="border-t border-slate-200 dark:border-white/[0.06] p-3 space-y-3">
            {/* Selector de Modo Claro / Oscuro */}
            <div className="flex items-center justify-between px-3 py-2 rounded-xl bg-slate-100 dark:bg-slate-900/60 border border-slate-200 dark:border-white/[0.08]">
              <div className="flex items-center gap-2 min-w-0">
                {theme === "dark" ? (
                  <Moon className="w-4 h-4 text-blue-400 shrink-0" />
                ) : (
                  <Sun className="w-4 h-4 text-amber-500 shrink-0" />
                )}
                <span className="text-xs font-semibold text-slate-700 dark:text-slate-300 truncate">
                  {theme === "dark" ? "Modo Oscuro" : "Modo Claro"}
                </span>
              </div>
              <button
                type="button"
                onClick={toggleThemeWithToast}
                title={theme === "dark" ? "Cambiar a Modo Claro" : "Cambiar a Modo Oscuro"}
                aria-label={theme === "dark" ? "Cambiar a Modo Claro" : "Cambiar a Modo Oscuro"}
                className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${
                  theme === "dark" ? "bg-primary-600" : "bg-amber-400"
                }`}
              >
                <span
                  className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow-md ring-0 transition duration-200 ease-in-out ${
                    theme === "dark" ? "translate-x-0" : "translate-x-4"
                  }`}
                />
              </button>
            </div>

            {/* Datos del usuario */}
            {usuario && (
              <div className="px-1 min-w-0">
                <p className="text-xs font-bold text-slate-900 dark:text-white truncate">
                  {usuario.nombre}
                </p>
                <p className="text-[11px] text-slate-500 truncate">{usuario.email}</p>
                <span
                  className={`badge mt-1.5 ${
                    usuario.rol === "admin"
                      ? "badge-info"
                      : "bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700"
                  }`}
                >
                  {usuario.rol}
                </span>
              </div>
            )}

            {/* Logout */}
            <button
              onClick={cerrarSesion}
              className="btn-secondary w-full text-sm py-2 cursor-pointer flex items-center justify-center gap-2"
            >
              <LogOut className="w-4 h-4 shrink-0" />
              <span className="truncate">Cerrar Sesión</span>
            </button>
          </div>
        ) : (
          <div className="border-t border-slate-200 dark:border-white/[0.06] py-3 px-2 space-y-3 flex flex-col items-center">
            {/* Toggle de Modo compacto */}
            <button
              type="button"
              onClick={toggleThemeWithToast}
              title={theme === "dark" ? "Cambiar a Modo Claro" : "Cambiar a Modo Oscuro"}
              aria-label={theme === "dark" ? "Cambiar a Modo Claro" : "Cambiar a Modo Oscuro"}
              className="w-10 h-10 rounded-xl flex items-center justify-center bg-slate-100 dark:bg-slate-900/60 border border-slate-200 dark:border-white/[0.08] hover:bg-slate-200 dark:hover:bg-slate-800 transition-colors cursor-pointer"
            >
              {theme === "dark" ? (
                <Moon className="w-4 h-4 text-blue-400" />
              ) : (
                <Sun className="w-4 h-4 text-amber-500" />
              )}
            </button>

            {/* Avatar del usuario con iniciales y tooltip */}
            {usuario && (
              <div
                className="w-10 h-10 rounded-full bg-primary-500/10 dark:bg-primary-600/20 border border-primary-500/30 flex items-center justify-center text-primary-600 dark:text-primary-400 font-bold text-xs shadow-sm cursor-default select-none"
                title={`${usuario.nombre} (${usuario.email}) - Rol: ${usuario.rol}`}
              >
                {obtenerIniciales(usuario.nombre)}
              </div>
            )}

            {/* Botón Logout compacto */}
            <button
              onClick={cerrarSesion}
              title="Cerrar Sesión"
              aria-label="Cerrar Sesión"
              className="w-10 h-10 rounded-xl flex items-center justify-center text-slate-500 dark:text-slate-400 hover:text-red-600 dark:hover:text-red-400 hover:bg-red-50 dark:hover:bg-red-500/10 border border-transparent hover:border-red-500/20 transition-all cursor-pointer"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        )}
      </aside>

      {/* Modal para crear nuevo usuario */}
      <ModalCrearUsuario
        isOpen={modalUsuarioAbierto}
        onClose={() => setModalUsuarioAbierto(false)}
        onUsuarioCreado={() => {
          if (pathname === "/usuarios") {
            window.location.reload();
          }
        }}
      />
    </>
  );
}
