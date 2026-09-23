import { Persona } from "@/types";

const JUNK_WORDS = new Set([
  "IDENTIDAD", "TARJETA", "CEDULA", "CIUDADANIA", "REPUBLICA", "COLOMBIA", 
  "RETUBEICA", "REPÚBLICA", "NACIONAL", "REGISTRADURIA", "ESTADO", "NUMERO", 
  "FIRMA", "HUELLA", "INDICE", "DERECHO", "IZQUIERDO", "DOCUMENTO", "PERSONAL", 
  "REGISTRO", "CIVIL", "EXPEDICION", "LUGAR", "FECHA", "NACIMIENTO", "SEXO", 
  "ESTATURA", "RH", "VIGENCIA", "POSTAL", "CUE", "III", "DR", "CDI", "AAAS",
  "EXTRANJERIA", "EXTRANJERÍA", "RESIDENTE", "TEMPORAL", "PROTECCION", "PROTECCIÓN",
  "PPT", "VISIBLES", "MIGRACION", "MIGRACIÓN", "PASAPORTE", "PASSPORT", "CONTRASEÑA",
  "VEN", "ECU", "PER", "BOL", "CHL", "ARG", "BRA", "MEX", "USA", "ESP", "COL"
]);

/**
 * Deduplica repeticiones consecutivas de frases o n-gramas de palabras
 * Ej: "EDWAR FABIAN ESCALANTE LOPEZ ESCALANTE LOPEZ" -> "EDWAR FABIAN ESCALANTE LOPEZ"
 * Para palabras individuales (k = 1): NUNCA colapsa repeticiones de 2 palabras consecutivas
 * (ej: "VILLA VILLA" o "RODRIGUEZ RODRIGUEZ") ya que son apellidos legítimos comunes.
 * Solo deduplica si se repite 3 o más veces consecutivas por error de loop OCR.
 */
function deduplicarNgrams(words: string[]): string[] {
  const n = words.length;
  // 1. Deduplicar n-gramas de longitud k >= 2 (frases completas)
  for (let k = Math.floor(n / 2); k >= 2; k--) {
    for (let i = 0; i <= n - 2 * k; i++) {
      const slice1 = words.slice(i, i + k).map((w) => w.toUpperCase()).join(" ");
      const slice2 = words.slice(i + k, i + 2 * k).map((w) => w.toUpperCase()).join(" ");
      if (slice1 === slice2) {
        const nextWords = [...words.slice(0, i + k), ...words.slice(i + 2 * k)];
        return deduplicarNgrams(nextWords);
      }
    }
  }

  // 2. Para k = 1: solo deduplicar si se repite 3 o más veces consecutivas (OCR loop glitch)
  for (let i = 0; i <= words.length - 3; i++) {
    if (words[i].toUpperCase() === words[i + 1].toUpperCase() && words[i + 1].toUpperCase() === words[i + 2].toUpperCase()) {
      const nextWords = [...words.slice(0, i + 2), ...words.slice(i + 3)];
      return deduplicarNgrams(nextWords);
    }
  }

  return words;
}

/**
 * Formatea y limpia el nombre completo de una persona, eliminando duplicados
 * accidentales (nombres repetidos en apellidos) y ruidos institucionales (IDENTIDAD, CUE, etc.).
 */
export function formatNombreCompleto(p: Partial<Persona> | null | undefined): string {
  if (!p) return "";

  const nom = (p.nombres || "").trim();
  const ape = (p.apellidos || "").trim();
  const full = (p.nombre_completo || "").trim();

  // Si ya tiene un nombre_completo explícito
  let candidate = full;
  if (!candidate || candidate === "POR REVISAR") {
    if (nom && ape) {
      const nomUpper = nom.toUpperCase();
      const apeUpper = ape.toUpperCase();
      // Si el apellido ya está contenido dentro del nombre
      if (nomUpper.endsWith(apeUpper) || nomUpper.replace(/\s+/g, "").endsWith(apeUpper.replace(/\s+/g, ""))) {
        candidate = nom;
      } else {
        candidate = `${nom} ${ape}`;
      }
    } else {
      candidate = nom || ape || "";
    }
  }

  if (!candidate) return "";

  // Filtrar tokens de basura institucional
  let words = candidate.split(/\s+/).filter((w) => {
    const clean = w.toUpperCase().replace(/[^A-ZÁÉÍÓÚÑ]/g, "");
    return !JUNK_WORDS.has(clean) && clean.length > 0;
  });

  // Quitar conectores sueltos al final o al inicio
  while (words.length > 0 && ["DE", "DEL", "LA", "LAS", "LOS", "Y"].includes(words[words.length - 1].toUpperCase())) {
    words.pop();
  }
  while (words.length > 0 && ["DE", "DEL", "LA", "LAS", "LOS", "III"].includes(words[0].toUpperCase())) {
    words.shift();
  }

  // Deduplicar repeticiones de frases
  words = deduplicarNgrams(words);

  return words.join(" ").trim();
}

/**
 * Calcula la edad exacta en años cumplidos a partir de una fecha de nacimiento.
 * Acepta strings en formato ISO (YYYY-MM-DD), formato latino (DD/MM/YYYY) o instancias Date.
 */
export function calcularEdad(fechaNacimiento: string | Date | null | undefined): number | null {
  if (!fechaNacimiento) return null;
  let anio: number, mes: number, dia: number;

  if (fechaNacimiento instanceof Date) {
    if (isNaN(fechaNacimiento.getTime())) return null;
    anio = fechaNacimiento.getFullYear();
    mes = fechaNacimiento.getMonth() + 1;
    dia = fechaNacimiento.getDate();
  } else {
    const s = String(fechaNacimiento).trim();
    if (!s) return null;
    if (s.includes("-")) {
      const parts = s.split("-");
      if (parts.length >= 3) {
        anio = parseInt(parts[0], 10);
        mes = parseInt(parts[1], 10);
        dia = parseInt(parts[2], 10);
      } else {
        return null;
      }
    } else if (s.includes("/")) {
      const parts = s.split("/");
      if (parts.length >= 3) {
        if (parts[0].length === 4) {
          anio = parseInt(parts[0], 10);
          mes = parseInt(parts[1], 10);
          dia = parseInt(parts[2], 10);
        } else {
          dia = parseInt(parts[0], 10);
          mes = parseInt(parts[1], 10);
          anio = parseInt(parts[2], 10);
        }
      } else {
        return null;
      }
    } else {
      const d = new Date(s);
      if (isNaN(d.getTime())) return null;
      anio = d.getFullYear();
      mes = d.getMonth() + 1;
      dia = d.getDate();
    }
  }

  if (!anio || !mes || !dia || isNaN(anio) || isNaN(mes) || isNaN(dia)) return null;

  const hoy = new Date();
  const hoyAnio = hoy.getFullYear();
  const hoyMes = hoy.getMonth() + 1;
  const hoyDia = hoy.getDate();

  let edad = hoyAnio - anio;
  if (hoyMes < mes || (hoyMes === mes && hoyDia < dia)) {
    edad--;
  }

  return edad >= 0 && edad <= 125 ? edad : null;
}

export interface InconsistenciaDocumentoEdad {
  esInvalido: boolean;
  tipo?: "MAYOR_CON_TI" | "MENOR_CON_CC";
  edad: number | null;
  motivo?: string;
}

/**
 * Valida la correspondencia legal entre la edad calculada y el tipo de documento presentado.
 * En Colombia:
 * - Menores de 18 años: Tarjeta de Identidad (TI)
 * - Mayores de 18 años (>= 18 años): Cédula de Ciudadanía (CC) o Contraseña (CT)
 * Si una persona mayor de 18 años presenta Tarjeta de Identidad, el archivo no es válido.
 */
export function verificarInconsistenciaDocumentoEdad(
  tipoDocumento: string | null | undefined,
  fechaNacimiento: string | Date | null | undefined,
  edadPrecalculada?: number | null
): InconsistenciaDocumentoEdad {
  const edad = edadPrecalculada !== undefined && edadPrecalculada !== null
    ? edadPrecalculada
    : calcularEdad(fechaNacimiento);

  if (edad === null) return { esInvalido: false, edad: null };

  const tipo = (tipoDocumento || "").toUpperCase().trim();
  const esCE = tipo.includes("EXTRANJER") || tipo === "CE";
  const esPPT = tipo.includes("PPT") || tipo.includes("TEMPORAL");
  const esTI = (tipo.includes("TARJETA") || tipo === "TI") && !esCE && !esPPT;
  const esCC = (tipo.includes("CEDULA") || tipo.includes("CÉDULA") || tipo === "CC") && !esTI && !esCE && !esPPT;

  if (edad >= 18 && esTI) {
    return {
      esInvalido: true,
      tipo: "MAYOR_CON_TI",
      edad,
      motivo: `Archivo no válido ya que la persona es mayor de edad (${edad} años) y presenta archivo de Tarjeta de Identidad que solo corresponde a menores de edad.`
    };
  }

  if (edad < 18 && esCC) {
    return {
      esInvalido: true,
      tipo: "MENOR_CON_CC",
      edad,
      motivo: `Archivo no válido ya que la persona es menor de edad (${edad} años) y presenta archivo de Cédula de Ciudadanía que solo corresponde a mayores de 18 años.`
    };
  }

  return { esInvalido: false, edad };
}

export interface TipoDocInfo {
  codigo: string;
  label: string;
  badge: string;
  pill: string;
}

/**
 * Retorna metadatos visuales y códigos para todos los tipos de documentos soportados:
 * CC, TI, CE, PPT, CT (Contraseña), PAS (Pasaporte)
 */
export function getTipoDocInfo(tipo?: string | null): TipoDocInfo {
  const t = (tipo || "").toUpperCase().trim();
  if (!t || t === "UNKNOWN") {
    return {
      codigo: "?",
      label: "Por verificar",
      badge: "bg-gray-100 dark:bg-gray-800/60 border border-gray-400 dark:border-gray-600 text-gray-700 dark:text-gray-300 font-bold shadow-sm",
      pill: "bg-gray-100 dark:bg-gray-800/60 text-gray-700 dark:text-gray-300 border border-gray-400 dark:border-gray-600 font-semibold shadow-sm",
    };
  }
  if (t.includes("PPT") || t.includes("TEMPORAL") || t.includes("PROTECCION") || t.includes("PROTECCIÓN")) {
    return {
      codigo: "PPT",
      label: "Permiso Protección Temporal",
      badge: "bg-cyan-100 dark:bg-cyan-950/40 border border-cyan-400 dark:border-cyan-800 text-cyan-900 dark:text-cyan-300 font-bold shadow-sm",
      pill: "bg-cyan-100 dark:bg-cyan-950/40 text-cyan-900 dark:text-cyan-300 border border-cyan-400 dark:border-cyan-800 font-semibold shadow-sm",
    };
  }
  if (t.includes("CONTRA") || t.includes("COMPROBANTE") || t === "CT") {
    return {
      codigo: "CT",
      label: "Contraseña",
      badge: "bg-teal-100 dark:bg-teal-950/40 border border-teal-400 dark:border-teal-800 text-teal-900 dark:text-teal-300 font-bold shadow-sm",
      pill: "bg-teal-100 dark:bg-teal-950/40 text-teal-900 dark:text-teal-300 border border-teal-400 dark:border-teal-800 font-semibold shadow-sm",
    };
  }
  if (t.includes("TARJETA") || t === "TI") {
    return {
      codigo: "TI",
      label: "Tarjeta de Identidad",
      badge: "bg-purple-100 dark:bg-purple-950/40 border border-purple-400 dark:border-purple-800 text-purple-900 dark:text-purple-300 font-bold shadow-sm",
      pill: "bg-purple-100 dark:bg-purple-950/40 text-purple-900 dark:text-purple-300 border border-purple-400 dark:border-purple-800 font-semibold shadow-sm",
    };
  }
  if (t.includes("EXTRANJERIA") || t === "CE" || t.includes("RESIDENTE")) {
    return {
      codigo: "CE",
      label: "Cédula Extranjería",
      badge: "bg-amber-100 dark:bg-amber-950/40 border border-amber-400 dark:border-amber-800 text-amber-900 dark:text-amber-300 font-bold shadow-sm",
      pill: "bg-amber-100 dark:bg-amber-950/40 text-amber-900 dark:text-amber-300 border border-amber-400 dark:border-amber-800 font-semibold shadow-sm",
    };
  }
  if (t.includes("PASAPORTE") || t === "PAS" || t.includes("PASSPORT")) {
    return {
      codigo: "PAS",
      label: "Pasaporte",
      badge: "bg-emerald-100 dark:bg-emerald-950/40 border border-emerald-400 dark:border-emerald-800 text-emerald-900 dark:text-emerald-300 font-bold shadow-sm",
      pill: "bg-emerald-100 dark:bg-emerald-950/40 text-emerald-900 dark:text-emerald-300 border border-emerald-400 dark:border-emerald-800 font-semibold shadow-sm",
    };
  }
  return {
    codigo: "CC",
    label: "Cédula de Ciudadanía",
    badge: "bg-blue-100 dark:bg-blue-900/60 border border-blue-400 dark:border-blue-700 text-blue-900 dark:text-blue-100 font-bold shadow-sm",
    pill: "bg-blue-100 dark:bg-blue-900/60 text-blue-900 dark:text-blue-100 border border-blue-400 dark:border-blue-700 font-semibold shadow-sm",
  };
}

