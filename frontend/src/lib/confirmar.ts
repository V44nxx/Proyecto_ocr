/**
 * Confirmaciones con el diálogo propio de KondID (components/ui/DialogoConfirmacion.tsx) en lugar de
 * window.confirm: `if (!(await confirmar({ titulo, mensaje, tema, tono }))) return;`
 */
import type { Tema, Tono } from "@/components/ui/IconoTema";

export interface OpcionesConfirmacion {
  titulo: string;
  mensaje?: string;
  /** Texto del botón que confirma (por defecto, «Confirmar») */
  confirmar?: string;
  cancelar?: string;
  tema?: Tema;
  /** "peligro" pinta el botón en rojo */
  tono?: Tono;
}

interface Pendiente extends OpcionesConfirmacion {
  responder: (si: boolean) => void;
}

let pendiente: Pendiente | null = null;
const oyentes = new Set<() => void>();

export const dialogoConfirmacion = {
  obtener: () => pendiente,
  suscribir(oyente: () => void) {
    oyentes.add(oyente);
    return () => oyentes.delete(oyente);
  },
  responder(si: boolean) {
    const actual = pendiente;
    pendiente = null;
    oyentes.forEach((o) => o());
    actual?.responder(si);
  },
};

export function confirmar(opciones: OpcionesConfirmacion): Promise<boolean> {
  // Si ya había una pregunta abierta, se responde «no» antes de mostrar la nueva
  pendiente?.responder(false);
  return new Promise((resolver) => {
    pendiente = { ...opciones, responder: resolver };
    oyentes.forEach((o) => o());
  });
}
