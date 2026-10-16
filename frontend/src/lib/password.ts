/** Mismas reglas que el backend para una contraseña nueva. Devuelve el error o null. */
export function validarPasswordNueva(nueva: string, confirmacion: string): string | null {
  if (nueva.length < 8) return "La contraseña debe tener al menos 8 caracteres.";
  if (new TextEncoder().encode(nueva).length > 72) return "La contraseña no puede tener más de 72 caracteres.";
  if (nueva !== confirmacion) return "Las contraseñas no coinciden.";
  return null;
}
