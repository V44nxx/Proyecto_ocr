import { useEffect } from "react";

// Contador compartido: el scroll solo se libera cuando se cierra el último panel o modal abierto
let bloqueosActivos = 0;
let estiloOriginal: { overflow: string; paddingRight: string } | null = null;

/**
 * Bloquea el scroll de la página mientras `activo` sea true, para que solo
 * se desplace el panel o modal abierto. Compensa el ancho de la barra de
 * scroll para que el contenido de fondo no salte.
 */
export function useBloquearScroll(activo: boolean): void {
  useEffect(() => {
    if (!activo) return;
    const { body, documentElement } = document;

    if (bloqueosActivos === 0) {
      estiloOriginal = { overflow: body.style.overflow, paddingRight: body.style.paddingRight };
      const anchoBarra = window.innerWidth - documentElement.clientWidth;
      body.style.overflow = "hidden";
      if (anchoBarra > 0) body.style.paddingRight = `${anchoBarra}px`;
    }
    bloqueosActivos += 1;

    return () => {
      bloqueosActivos -= 1;
      if (bloqueosActivos === 0 && estiloOriginal) {
        body.style.overflow = estiloOriginal.overflow;
        body.style.paddingRight = estiloOriginal.paddingRight;
        estiloOriginal = null;
      }
    };
  }, [activo]);
}
