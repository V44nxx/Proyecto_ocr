/**
 * Enlaces del Seguimiento de fichas. El backend ya solo guarda aplicaciones web de Apps Script y hojas de
 * Google Sheets; como segunda capa, el frontend tampoco pone en un enlace o en el iframe nada que no lo sea
 * (por ejemplo un javascript: o un dominio parecido). Mismas reglas que _validar_url en routers/seguimiento.py.
 */
function urlPermitida(valor: string | null | undefined, host: string, prefijos: string[]): string | undefined {
  if (!valor) return undefined;
  try {
    const url = new URL(valor);
    if (url.protocol === "https:" && url.hostname === host && prefijos.some((p) => url.pathname.startsWith(p))) {
      return url.href;
    }
  } catch {
    // no es una URL
  }
  return undefined;
}

export const urlPanelSeguimiento = (valor?: string | null) =>
  urlPermitida(valor, "script.google.com", ["/macros/s/", "/a/macros/"]);

export const urlHojaSeguimiento = (valor?: string | null) => urlPermitida(valor, "docs.google.com", ["/spreadsheets/"]);

/**
 * Agrega al enlace del panel el nombre de quien tiene la sesión abierta en KondID (&u=...). El panel lo anota en su
 * historial de «Cambios» como autor de lo que se guarde desde KondID.
 */
export function conUsuario(url: string | undefined, nombre?: string | null): string | undefined {
  if (!url || !nombre) return url;
  const conNombre = new URL(url);
  conNombre.searchParams.set("u", nombre);
  return conNombre.href;
}
