import type { Metadata } from "next";

// El enlace lleva el token en la URL: que no viaje como Referer ni se indexe
export const metadata: Metadata = {
  title: "Restablecer contraseña | KondID",
  referrer: "no-referrer",
  robots: { index: false, follow: false },
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
