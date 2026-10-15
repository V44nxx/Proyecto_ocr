import { useEffect, useState } from "react";

/** Devuelve si la media query se cumple; en el primer render (y en el servidor) devuelve false. */
export function useMediaQuery(consulta: string): boolean {
  const [cumple, setCumple] = useState(false);

  useEffect(() => {
    const mql = window.matchMedia(consulta);
    const actualizar = () => setCumple(mql.matches);
    actualizar();
    mql.addEventListener("change", actualizar);
    return () => mql.removeEventListener("change", actualizar);
  }, [consulta]);

  return cumple;
}
