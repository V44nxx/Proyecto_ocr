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
  Settings,
} from "lucide-react";
import { auth } from "@/lib/auth";
import toast from "react-hot-toast";

interface NavItem {
  href: string;
  icon: React.ReactNode;
  label: string;
}

const navItems: NavItem[] = [
  { href: "/dashboard", icon: <LayoutDashboard className="w-4 h-4" />, label: "Dashboard" },
  { href: "/documentos", icon: <FileText className="w-4 h-4" />, label: "Documentos PDF" },
  { href: "/personas", icon: <Users className="w-4 h-4" />, label: "Personas" },
  { href: "/exportacion", icon: <Download className="w-4 h-4" />, label: "Exportación" },
  { href: "/comparacion", icon: <GitCompare className="w-4 h-4" />, label: "Comparación" },
];

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const [usuario, setUsuario] = useState<{ nombre: string; email: string; rol: string } | null>(null);

  useEffect(() => {
    setUsuario(auth.getUsuario());
  }, []);

  const cerrarSesion = () => {
    auth.cerrarSesion();
    toast.success("Sesión cerrada");
    router.push("/");
  };

  return (
    <aside className="sidebar z-50" suppressHydrationWarning>
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
        {navItems.map((item) => {
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
              {item.label}
            </button>
          );
        })}
      </nav>

      {/* Usuario y logout */}
      <div className="border-t border-white/[0.06] p-4">
        {usuario && (
          <div className="mb-3 px-1">
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
  );
}
