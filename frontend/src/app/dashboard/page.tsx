"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  FileText, Users, GitCompare, AlertTriangle,
  CheckCircle, Clock, TrendingUp, Activity,
} from "lucide-react";
import Sidebar from "@/components/ui/Sidebar";
import { apiDocumentos } from "@/lib/api";
import { auth } from "@/lib/auth";
import type { DashboardStats } from "@/types";

function StatCard({
  title,
  value,
  icon,
  color,
  subtitle,
}: {
  title: string;
  value: number | string;
  icon: React.ReactNode;
  color: string;
  subtitle?: string;
}) {
  return (
    <div className="stats-card group">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-slate-400 text-sm mb-1">{title}</p>
          <p className="text-4xl font-bold text-white">
            {typeof value === "number" ? value.toLocaleString() : value}
          </p>
          {subtitle && <p className="text-xs text-slate-500 mt-1">{subtitle}</p>}
        </div>
        <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${color} transition-transform group-hover:scale-110`}>
          {icon}
        </div>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const router = useRouter();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [cargando, setCargando] = useState(true);

  useEffect(() => {
    if (!auth.isAuthenticated()) {
      router.push("/");
      return;
    }
    cargarEstadisticas();

    const intervalo = setInterval(cargarEstadisticas, 15000);
    return () => clearInterval(intervalo);
  }, []);

  const cargarEstadisticas = async () => {
    try {
      const { data } = await apiDocumentos.estadisticas();
      setStats(data);
    } catch (err) {
      console.error("Error cargando estadísticas:", err);
    } finally {
      setCargando(false);
    }
  };

  return (
    <div className="flex min-h-screen">
      <Sidebar />

      <main className="ml-64 flex-1 p-8">
        {/* Header */}
        <div className="mb-8 page-enter">
          <div className="flex items-center gap-2 mb-1">
            <Activity className="w-5 h-5 text-primary-400" />
            <span className="text-primary-400 text-sm font-medium">Panel de Control</span>
          </div>
          <h1 className="text-3xl font-bold text-white">Dashboard</h1>
          <p className="text-slate-400 mt-1">
            Resumen del sistema OCR en tiempo real
          </p>
        </div>

        {/* Stats Grid */}
        {cargando ? (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6 mb-8">
            {Array(7).fill(0).map((_, i) => (
              <div key={i} className="card skeleton h-32 rounded-2xl" />
            ))}
          </div>
        ) : stats ? (
          <>
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6 mb-8 page-enter">
              <StatCard
                title="Total Documentos"
                value={stats.total_documentos}
                icon={<FileText className="w-6 h-6 text-blue-400" />}
                color="bg-blue-500/10 border border-blue-500/20"
                subtitle="PDFs subidos al sistema"
              />
              <StatCard
                title="Completados"
                value={stats.documentos_completados}
                icon={<CheckCircle className="w-6 h-6 text-green-400" />}
                color="bg-green-500/10 border border-green-500/20"
                subtitle="OCR exitoso"
              />
              <StatCard
                title="En Proceso"
                value={stats.documentos_procesando}
                icon={<Clock className="w-6 h-6 text-yellow-400" />}
                color="bg-yellow-500/10 border border-yellow-500/20"
                subtitle="Procesando ahora"
              />
              <StatCard
                title="Con Error"
                value={stats.documentos_con_error}
                icon={<AlertTriangle className="w-6 h-6 text-red-400" />}
                color="bg-red-500/10 border border-red-500/20"
                subtitle="Requieren atención"
              />
              <StatCard
                title="Total Personas"
                value={stats.total_personas}
                icon={<Users className="w-6 h-6 text-purple-400" />}
                color="bg-purple-500/10 border border-purple-500/20"
                subtitle="Registros en BD"
              />
              <StatCard
                title="En Revisión"
                value={stats.personas_en_revision}
                icon={<AlertTriangle className="w-6 h-6 text-orange-400" />}
                color="bg-orange-500/10 border border-orange-500/20"
                subtitle="Confianza baja"
              />
              <StatCard
                title="Comparaciones"
                value={stats.total_comparaciones}
                icon={<GitCompare className="w-6 h-6 text-cyan-400" />}
                color="bg-cyan-500/10 border border-cyan-500/20"
                subtitle="Análisis realizados"
              />
              {stats.total_documentos > 0 && (
                <StatCard
                  title="Tasa de Éxito"
                  value={`${Math.round((stats.documentos_completados / stats.total_documentos) * 100)}%`}
                  icon={<TrendingUp className="w-6 h-6 text-emerald-400" />}
                  color="bg-emerald-500/10 border border-emerald-500/20"
                  subtitle="Documentos procesados OK"
                />
              )}
            </div>

            {/* Accesos rápidos */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 page-enter">
              {[
                {
                  title: "Subir documentos",
                  desc: "Cargar PDFs para procesamiento OCR",
                  href: "/documentos",
                  color: "from-blue-600/20 to-blue-800/10",
                  border: "border-blue-500/20",
                  icon: <FileText className="w-8 h-8 text-blue-400" />,
                },
                {
                  title: "Ver personas",
                  desc: "Revisar y corregir datos extraídos",
                  href: "/personas",
                  color: "from-purple-600/20 to-purple-800/10",
                  border: "border-purple-500/20",
                  icon: <Users className="w-8 h-8 text-purple-400" />,
                },
                {
                  title: "Comparar datos",
                  desc: "Cargar Excel externo y comparar",
                  href: "/comparacion",
                  color: "from-cyan-600/20 to-cyan-800/10",
                  border: "border-cyan-500/20",
                  icon: <GitCompare className="w-8 h-8 text-cyan-400" />,
                },
              ].map((item) => (
                <button
                  key={item.href}
                  onClick={() => router.push(item.href)}
                  className={`card text-left bg-gradient-to-br ${item.color} border ${item.border} hover:scale-[1.02] transition-transform duration-200`}
                >
                  <div className="mb-3">{item.icon}</div>
                  <h3 className="text-white font-semibold mb-1">{item.title}</h3>
                  <p className="text-slate-400 text-sm">{item.desc}</p>
                </button>
              ))}
            </div>
          </>
        ) : (
          <div className="card text-center py-12">
            <p className="text-slate-400">Error cargando estadísticas</p>
          </div>
        )}
      </main>
    </div>
  );
}
