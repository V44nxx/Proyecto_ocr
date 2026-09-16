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
} from "lucide-react";
import { auth } from "@/lib/auth";
import toast from "react-hot-toast";
import ModalCrearUsuario from "@/components/ui/ModalCrearUsuario";
import { useTheme } from "@/context/ThemeContext";

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

  const itemsVisibles = navItems.filter(
    (item) => !item.adminOnly || usuario?.rol === "admin"
  );

  return (
    <>
      <aside className="sidebar z-40" suppressHydrationWarning>
        {/* Logo */}
        <div className="px-4 py-5 border-b border-white/[0.06]">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-primary-600/20 border border-primary-500/30 flex items-center justify-center"
                 style={{ boxShadow: "0 0 15px rgba(59,130,246,0.3)" }}>
              <Cpu className="w-4 h-4 text-primary-400" />
            </div>
            <div>
              <span className="text-sm font-bold text-white block">Sistema OCR</span>
              <span className="text-[10px] text-slate-500">Documentos CO</span>
            </div>
          </div>
        </div>

        {/* Navegación */}
        <nav className="flex-1 py-4 space-y-1 overflow-y-auto">
          <p className="px-4 mb-2 text-[10px] font-semibold text-slate-600 uppercase tracking-widest">
            Módulos
          </p>
          {itemsVisibles.map((item) => {
            const isActive = pathname === item.href;
            return (
              <button
                key={item.href}
                onClick={() => router.push(item.href)}
                className={`sidebar-item w-full ${isActive ? "active" : ""}`}
              >
                <span className={isActive ? "text-primary-400" : "text-slate-500"}>
                  {item.icon}
                </span>
                <span className="flex-1 text-left">{item.label}</span>
                {item.adminOnly && (
                  <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-300 border border-purple-500/30">
                    Admin
                  </span>
                )}
              </button>
            );
          })}

          {/* Botón rápido para agregar usuario si es admin */}
          {usuario?.rol === "admin" && (
            <div className="pt-4 px-3">
              <button
                onClick={() => setModalUsuarioAbierto(true)}
                className="w-full flex items-center justify-center gap-2 px-3 py-2.5 rounded-xl text-xs font-semibold bg-gradient-to-r from-primary-600 to-blue-700 hover:from-primary-500 hover:to-blue-600 text-white shadow-lg shadow-primary-950/40 border border-primary-400/30 transition-all hover:scale-[1.02] active:scale-98"
                title="Agregar nuevo usuario al sistema"
              >
                <UserPlus className="w-3.5 h-3.5" />
                <span>+ Agregar Usuario</span>
              </button>
            </div>
          )}
        </nav>

        {/* Tema, Usuario y logout */}
        <div className="border-t border-white/[0.06] p-4 space-y-3">
          {/* Selector de Modo Claro / Oscuro */}
          <div className="flex items-center justify-between px-3 py-2 rounded-xl bg-slate-900/60 border border-white/[0.08]">
            <div className="flex items-center gap-2">
              {theme === "dark" ? (
                <Moon className="w-4 h-4 text-blue-400" />
              ) : (
                <Sun className="w-4 h-4 text-amber-500" />
              )}
              <span className="text-xs font-semibold text-slate-300">
                {theme === "dark" ? "Modo Oscuro" : "Modo Claro"}
              </span>
            </div>
            <button
              type="button"
              onClick={() => {
                toggleTheme();
                toast.success(theme === "dark" ? "Modo Claro activado" : "Modo Oscuro activado", {
                  duration: 2000,
                  icon: theme === "dark" ? "☀️" : "🌙",
                });
              }}
              title={theme === "dark" ? "Cambiar a Modo Claro" : "Cambiar a Modo Oscuro"}
              className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${
                theme === "dark" ? "bg-primary-600" : "bg-amber-500"
              }`}
            >
              <span
                className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow-lg ring-0 transition duration-200 ease-in-out ${
                  theme === "dark" ? "translate-x-0" : "translate-x-4"
                }`}
              />
            </button>
          </div>

          {usuario && (
            <div className="px-1">
              <p className="text-xs font-semibold text-white truncate">{usuario.nombre}</p>
              <p className="text-[11px] text-slate-500 truncate">{usuario.email}</p>
              <span className={`badge mt-1 ${usuario.rol === "admin" ? "badge-info" : "badge-neutral"}`}>
                {usuario.rol}
              </span>
            </div>
          )}
          <button onClick={cerrarSesion} className="btn-secondary w-full text-sm py-2">
            <LogOut className="w-4 h-4" />
            Cerrar Sesión
          </button>
        </div>
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
