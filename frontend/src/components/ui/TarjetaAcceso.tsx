import Link from "next/link";
import LogoKondID from "@/components/ui/LogoKondID";

/** Tarjeta centrada con el logo, para las pantallas de acceso que no requieren sesión. */
export default function TarjetaAcceso({
  titulo,
  descripcion,
  children,
}: {
  titulo: string;
  descripcion?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen login-bg text-slate-900 dark:text-slate-100 flex items-center justify-center px-4 py-10">
      <div className="w-full max-w-md">
        <div className="flex justify-center mb-6">
          <Link href="/" aria-label="Ir al inicio de sesión">
            <LogoKondID className="h-9" />
          </Link>
        </div>
        <div className="apple-card rounded-2xl sm:rounded-3xl p-6 sm:p-7">
          <h1 className="text-xl font-semibold tracking-[-0.02em] text-slate-900 dark:text-white">{titulo}</h1>
          {descripcion && (
            <p className="text-xs text-slate-500 dark:text-[#86868B] mt-1 leading-relaxed">{descripcion}</p>
          )}
          <div className="mt-5">{children}</div>
        </div>
        <p className="text-center mt-5">
          <Link href="/" className="text-xs font-medium text-[#0071E3] dark:text-[#4C9BFF] hover:underline">
            Volver al inicio de sesión
          </Link>
        </p>
      </div>
    </div>
  );
}
