/**
 * Avisos que se repiten en varias pantallas.
 */
import toast from "react-hot-toast";

/** Lo que trae cualquier Excel de personas o de diferencias que se descarga */
export const AVISO_DATOS_PERSONALES =
  "el Excel trae cédulas, nombres y fechas de nacimiento, y puede incluir menores de edad. Guárdalo solo en equipos de confianza, no lo compartas por chats ni correos abiertos y bórralo cuando ya no lo necesites.";

/** Después de descargar un Excel con datos de personas */
export function avisarDescargaDatosPersonales(titulo: string, id?: string): void {
  toast.success(`${titulo}. Tiene datos personales: guárdalo en un lugar seguro y no lo compartas.`, {
    id,
    duration: 7000,
  });
}
