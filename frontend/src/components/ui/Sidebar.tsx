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
        className: "text-xs font-medium !rounded-2xl !border !border-slate-200 dark:!border-white/[0.08] !bg-white/90 dark:!bg-[#121620]/90 !backdrop-blur-xl !shadow-lg",
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
        className={`sidebar z-40 border-r border-slate-200/80 dark:border-white/[0.08] overflow-x-hidden ${
          collapsed ? "collapsed" : "expanded"
        }`}
        suppressHydrationWarning
      >
        {/* Línea especular sutil en la arista superior */}
        <div className="absolute inset-x-0 top-0 h-[1px] bg-gradient-to-r from-transparent via-slate-300/40 dark:via-white/10 to-transparent pointer-events-none" />

        {/* ── Logo & Toggle ─────────────────────────────────────── */}
        {!collapsed ? (
          <div className="px-4 py-4 border-b border-slate-200/70 dark:border-white/[0.06] flex items-center justify-between min-w-0">
            <div className="flex items-center gap-3 min-w-0">
              <div className="w-8 h-8 rounded-xl bg-slate-900 dark:bg-white text-white dark:text-slate-900 flex items-center justify-center font-bold shadow-sm shrink-0">
                <Cpu className="w-4 h-4" />
              </div>
              <div className="min-w-0">
                <span className="text-sm font-semibold text-slate-900 dark:text-white block truncate tracking-tight">
                  KondID
                </span>
                <span className="text-[10px] text-slate-400 dark:text-slate-400 font-medium block truncate">
                  Motor OCR • v2.0
                </span>
              </div>
            </div>
            <button
              onClick={toggleSidebar}
              title="Ocultar menú lateral"
              aria-label="Ocultar menú lateral"
              className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 dark:hover:text-white hover:bg-slate-200/50 dark:hover:bg-white/[0.08] transition-all shrink-0 cursor-pointer active:scale-[0.95]"
            >
              <PanelLeftClose className="w-4 h-4" />
            </button>
          </div>
        ) : (
          <div className="py-4 border-b border-slate-200/70 dark:border-white/[0.06] flex flex-col items-center gap-2.5">
            <div
              className="w-8 h-8 rounded-xl bg-slate-900 dark:bg-white text-white dark:text-slate-900 flex items-center justify-center font-bold shadow-sm shrink-0"
              title="KondID - Motor OCR"
            >
              <Cpu className="w-4 h-4" />
            </div>
            <button
              onClick={toggleSidebar}
              title="Expandir menú lateral"
              aria-label="Expandir menú lateral"
              className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 dark:hover:text-white hover:bg-slate-200/50 dark:hover:bg-white/[0.08] transition-all flex items-center justify-center cursor-pointer active:scale-[0.95]"
            >
              <PanelLeftOpen className="w-4 h-4" />
            </button>
          </div>
        )}

        {/* ── Navegación ────────────────────────────────────────── */}
        {!collapsed ? (
          <nav className="flex-1 py-4 px-3 space-y-1 overflow-y-auto overflow-x-hidden">
            <p className="px-3 mb-2 text-[10px] font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-wider truncate">
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
                    className={`shrink-0 transition-colors ${
                      isActive
                        ? "text-[#0071E3] dark:text-[#409CFF]"
                        : "text-slate-400 dark:text-slate-400 group-hover:text-slate-600 dark:group-hover:text-slate-200"
                    }`}
                  >
                    {item.icon}
                  </span>
                  <span className="flex-1 text-left truncate">{item.label}</span>
                  {item.adminOnly && (
                    <span className="text-[9px] font-medium px-1.5 py-0.5 rounded-full bg-slate-200/70 dark:bg-white/[0.08] text-slate-600 dark:text-slate-400 border border-slate-300/50 dark:border-white/[0.06] shrink-0">
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
                  className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-xl text-xs font-medium bg-slate-100/80 hover:bg-slate-200/80 dark:bg-white/[0.05] dark:hover:bg-white/[0.09] text-slate-700 dark:text-slate-200 border border-slate-200/80 dark:border-white/[0.06] transition-all active:scale-[0.98] cursor-pointer"
                  title="Agregar nuevo usuario al sistema"
                >
                  <UserPlus className="w-3.5 h-3.5 text-slate-500 dark:text-slate-400 shrink-0" />
                  <span className="truncate">Agregar Usuario</span>
                </button>
              </div>
            )}
          </nav>
        ) : (
          <nav className="flex-1 py-4 px-2 space-y-1.5 overflow-y-auto overflow-x-hidden flex flex-col items-center">
            {itemsVisibles.map((item) => {
              const isActive = pathname === item.href;
              return (
                <button
                  key={item.href}
                  onClick={() => router.push(item.href)}
                  className={`relative w-10 h-10 rounded-xl flex items-center justify-center transition-all duration-150 cursor-pointer active:scale-[0.95] ${
                    isActive
                      ? "bg-[#0071E3]/12 text-[#0071E3] dark:text-[#409CFF] border border-[#0071E3]/20"
                      : "text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white hover:bg-slate-200/50 dark:hover:bg-white/[0.06]"
                  }`}
                  title={item.label}
                  aria-label={item.label}
                >
                  <span className="shrink-0">{item.icon}</span>
                  {item.adminOnly && (
                    <span
                      className="absolute top-1.5 right-1.5 w-1.5 h-1.5 rounded-full bg-slate-400 dark:bg-slate-300"
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
                  className="w-10 h-10 mx-auto flex items-center justify-center rounded-xl bg-slate-100/80 hover:bg-slate-200/80 dark:bg-white/[0.05] dark:hover:bg-white/[0.09] text-slate-700 dark:text-slate-200 border border-slate-200/80 dark:border-white/[0.06] transition-all active:scale-[0.95] cursor-pointer"
                  title="Agregar nuevo usuario"
                  aria-label="Agregar nuevo usuario"
                >
                  <UserPlus className="w-4 h-4 text-slate-500 dark:text-slate-400" />
                </button>
              </div>
            )}
          </nav>
        )}

        {/* ── Footer: Tema, Usuario y Logout ───────────────────── */}
        {!collapsed ? (
          <div className="border-t border-slate-200/70 dark:border-white/[0.06] p-3 space-y-2.5">
            {/* Selector de Modo Claro / Oscuro estilo Apple Switch */}
            <div className="flex items-center justify-between px-3 py-2 rounded-xl bg-slate-200/50 dark:bg-white/[0.04] border border-slate-200/60 dark:border-white/[0.06]">
              <div className="flex items-center gap-2 min-w-0">
                {theme === "dark" ? (
                  <Moon className="w-3.5 h-3.5 text-slate-300 shrink-0" />
                ) : (
                  <Sun className="w-3.5 h-3.5 text-amber-500 shrink-0" />
                )}
                <span className="text-xs font-medium text-slate-700 dark:text-slate-300 truncate">
                  {theme === "dark" ? "Modo Oscuro" : "Modo Claro"}
                </span>
              </div>
              <button
                type="button"
                onClick={toggleThemeWithToast}
                title={theme === "dark" ? "Cambiar a Modo Claro" : "Cambiar a Modo Oscuro"}
                aria-label={theme === "dark" ? "Cambiar a Modo Claro" : "Cambiar a Modo Oscuro"}
                className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full p-0.5 transition-colors duration-200 ease-in-out focus:outline-none ${
                  theme === "dark" ? "bg-[#0071E3]" : "bg-slate-300"
                }`}
              >
                <span
                  className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow-sm transition duration-200 ease-in-out ${
                    theme === "dark" ? "translate-x-4" : "translate-x-0"
                  }`}
                />
              </button>
            </div>

            {/* Ficha de Usuario elegante */}
            {usuario && (
              <div className="p-2.5 rounded-xl bg-white/60 dark:bg-white/[0.03] border border-slate-200/70 dark:border-white/[0.06] flex items-center gap-2.5 min-w-0">
                <div className="w-8 h-8 rounded-full bg-slate-200 dark:bg-white/[0.1] text-slate-700 dark:text-slate-200 font-semibold text-xs flex items-center justify-center shrink-0 border border-slate-300/40 dark:border-white/[0.08]">
                  {obtenerIniciales(usuario.nombre)}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-1">
                    <p className="text-xs font-semibold text-slate-900 dark:text-white truncate">
                      {usuario.nombre}
                    </p>
                    <span className="text-[9px] font-medium tracking-wide uppercase px-1.5 py-0.5 rounded-md bg-slate-100 dark:bg-white/[0.06] text-slate-500 dark:text-slate-400 shrink-0">
                      {usuario.rol}
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-400 dark:text-slate-500 truncate">{usuario.email}</p>
                </div>
              </div>
            )}

            {/* Botón Logout */}
            <button
              onClick={cerrarSesion}
              className="w-full flex items-center justify-center gap-2 py-2 px-3 rounded-xl text-xs font-medium text-slate-600 dark:text-slate-400 hover:text-[#FF3B30] dark:hover:text-[#FF453A] hover:bg-rose-500/10 transition-all cursor-pointer active:scale-[0.98]"
            >
              <LogOut className="w-3.5 h-3.5 shrink-0" />
              <span className="truncate">Cerrar Sesión</span>
            </button>
          </div>
        ) : (
          <div className="border-t border-slate-200/70 dark:border-white/[0.06] py-3 px-2 space-y-2 flex flex-col items-center">
            {/* Toggle de Modo compacto */}
            <button
              type="button"
              onClick={toggleThemeWithToast}
              title={theme === "dark" ? "Cambiar a Modo Claro" : "Cambiar a Modo Oscuro"}
              aria-label={theme === "dark" ? "Cambiar a Modo Claro" : "Cambiar a Modo Oscuro"}
              className="w-9 h-9 rounded-xl flex items-center justify-center bg-slate-100/80 dark:bg-white/[0.04] border border-slate-200/80 dark:border-white/[0.06] hover:bg-slate-200/70 dark:hover:bg-white/[0.08] transition-all cursor-pointer active:scale-[0.95]"
            >
              {theme === "dark" ? (
                <Moon className="w-4 h-4 text-slate-300" />
              ) : (
                <Sun className="w-4 h-4 text-amber-500" />
              )}
            </button>

            {/* Avatar del usuario con iniciales y tooltip */}
            {usuario && (
              <div
                className="w-9 h-9 rounded-full bg-slate-200 dark:bg-white/[0.1] text-slate-700 dark:text-slate-200 font-semibold text-xs flex items-center justify-center border border-slate-300/40 dark:border-white/[0.08] cursor-default select-none"
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
              className="w-9 h-9 rounded-xl flex items-center justify-center text-slate-400 hover:text-[#FF3B30] dark:hover:text-[#FF453A] hover:bg-rose-500/10 transition-all cursor-pointer active:scale-[0.95]"
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
