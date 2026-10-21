/**
 * Divide un nombre completo en nombres y apellidos para mostrarlo por partes cuando la persona no tiene
 * los apellidos guardados por separado. Solo para mostrar: no cambia los datos ni lo que se exporta.
 *
 * KondID guarda el nombre completo como "NOMBRES APELLIDOS" (JAIME DUBAN CARVAJAL SALINAS).
 * - Las partículas (DE, DEL, LA, SAN...) van pegadas a la palabra que sigue: MARIA DEL PILAR, GOMEZ DE LA HOZ.
 * - Con 4 partes o más, las dos últimas son los apellidos.
 * - Con 3 partes, si la segunda es un nombre frecuente son dos nombres y un apellido (ZULY ANDREA PEREZ);
 *   si no, un nombre y dos apellidos, lo más común en Colombia (JUAN PEREZ GOMEZ).
 */

const PARTICULAS = new Set(["DE", "DEL", "LA", "LAS", "LOS", "SAN", "Y"]);

// Los mismos de backend/app/data/dictionaries/nombres/nombres_frecuentes.json (en mayúsculas y sin tildes)
const NOMBRES_FRECUENTES = new Set([
  "ADRIANA", "ALBERTO", "ALEJANDRO", "ALFONSO", "ALVARO", "ANA", "ANDREA", "ANDRES", "ANGEL", "ANGELICA",
  "ANTONIO", "ARMANDO", "BEATRIZ", "CAMILA", "CAMILO", "CARLOS", "CAROLINA", "CATALINA", "CESAR", "CLAUDIA",
  "CRISTIAN", "CRUZ", "DANIELA", "DAVID", "DERLY", "DIANA", "DIEGO", "DURY", "EDGAR", "EDWIN", "ELENA",
  "ESPERANZA", "ESTEBAN", "EVER", "FABIAN", "FERNANDO", "FREDY", "GABRIEL", "GABRIELA", "GERMAN", "GLORIA",
  "GONZALO", "GUILERMO", "GUSTAVO", "HAROLD", "HECTOR", "HENRY", "HUGO", "INDIRA", "ISABELLA", "IVAN", "JAIME",
  "JEFFERSON", "JESSICA", "JHON", "JIMENA", "JOHN", "JORGE", "JOSE", "JUAN", "JULIAN", "LADY", "LAURA", "LEIDY",
  "LEONARDO", "LEONEL", "LILIANA", "LUIS", "LUZ", "MANUEL", "MARCELA", "MARIA", "MARIO", "MARTHA", "MAURICIO",
  "MIGUEL", "MONICA", "NATALIA", "ORLANDO", "OSCAR", "PAOLA", "PATRICIA", "PAULA", "PEDRO", "RAFAEL", "RAMON",
  "RICARDO", "ROBERTO", "RODRIGO", "RUBEN", "SANDRA", "SANTIAGO", "SEBASTIAN", "SOFIA", "STEPHANIE", "VALENTINA",
  "VANESSA", "VICTOR", "VIVIANA", "WALTER", "WILSON", "XIMENA", "YERLIS", "YESID", "YOLANDA", "YUDY", "YULEIDY",
  "YULIETH", "YURANI", "YURI",
]);

const sinTildes = (texto: string) => texto.normalize("NFD").replace(/[̀-ͯ]/g, "").toUpperCase();

/** Palabras del nombre, con cada partícula pegada a la palabra que la sigue. */
function partesDelNombre(completo: string): string[] {
  const partes: string[] = [];
  let pendientes: string[] = [];
  for (const palabra of completo.trim().split(/\s+/).filter(Boolean)) {
    if (PARTICULAS.has(sinTildes(palabra))) {
      pendientes.push(palabra);
      continue;
    }
    partes.push([...pendientes, palabra].join(" "));
    pendientes = [];
  }
  if (pendientes.length) {
    if (partes.length) partes[partes.length - 1] += " " + pendientes.join(" ");
    else partes.push(pendientes.join(" "));
  }
  return partes;
}

export function dividirNombreCompleto(completo?: string | null): { nombres: string; apellidos: string } {
  const partes = partesDelNombre(completo || "");
  if (partes.length <= 1) return { nombres: partes.join(" "), apellidos: "" };

  let cuantosNombres = partes.length - 2;
  if (partes.length === 2) cuantosNombres = 1;
  else if (partes.length === 3) cuantosNombres = NOMBRES_FRECUENTES.has(sinTildes(partes[1])) ? 2 : 1;

  return {
    nombres: partes.slice(0, cuantosNombres).join(" "),
    apellidos: partes.slice(cuantosNombres).join(" "),
  };
}
