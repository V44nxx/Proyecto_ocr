import { Persona } from "@/types";

const JUNK_WORDS = new Set([
  "IDENTIDAD", "TARJETA", "CEDULA", "CIUDADANIA", "REPUBLICA", "COLOMBIA", 
  "RETUBEICA", "REPÚBLICA", "NACIONAL", "REGISTRADURIA", "ESTADO", "NUMERO", 
  "FIRMA", "HUELLA", "INDICE", "DERECHO", "IZQUIERDO", "DOCUMENTO", "PERSONAL", 
  "REGISTRO", "CIVIL", "EXPEDICION", "LUGAR", "FECHA", "NACIMIENTO", "SEXO", 
  "ESTATURA", "RH", "VIGENCIA", "POSTAL", "CUE", "III", "DR", "CDI", "AAAS"
]);

/**
 * Deduplica repeticiones consecutivas de frases o n-gramas de palabras
 * Ej: "EDWAR FABIAN ESCALANTE LOPEZ ESCALANTE LOPEZ" -> "EDWAR FABIAN ESCALANTE LOPEZ"
 * Ej: "AYALA CASTRO AYALA CASTRO" -> "AYALA CASTRO"
 */
function deduplicarNgrams(words: string[]): string[] {
  const n = words.length;
  for (let k = Math.floor(n / 2); k >= 1; k--) {
    for (let i = 0; i <= n - 2 * k; i++) {
      const slice1 = words.slice(i, i + k).map((w) => w.toUpperCase()).join(" ");
      const slice2 = words.slice(i + k, i + 2 * k).map((w) => w.toUpperCase()).join(" ");
      if (slice1 === slice2) {
        const nextWords = [...words.slice(0, i + k), ...words.slice(i + 2 * k)];
        return deduplicarNgrams(nextWords);
      }
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
