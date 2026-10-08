"""
Utilidad para limpieza, sanitización y deduplicación de nombres y apellidos
en documentos de identidad colombianos.
"""
import re
import unicodedata

JUNK_WORDS = {
    "IDENTIDAD", "TARJETA", "CEDULA", "CIUDADANIA", "REPUBLICA", "COLOMBIA", 
    "RETUBEICA", "REPÚBLICA", "NACIONAL", "REGISTRADURIA", "ESTADO", "NUMERO", 
    "NÚMERO", "FIRMA", "HUELLA", "INDICE", "ÍNDICE", "DERECHO", "IZQUIERDO", 
    "DOCUMENTO", "PERSONAL", "REGISTRO", "CIVIL", "EXPEDICION", "EXPEDICIÓN", 
    "LUGAR", "FECHA", "NACIMIENTO", "SEXO", "ESTATURA", "RH", "VIGENCIA", 
    "POSTAL", "CUE", "DR", "CDI", "AAAS", "AAS", "NOMBRES", "APELLIDOS", 
    "NOMBRE", "APELLIDO", "APILLIDOS", "APILLIDO", "APELIDOS", "APELIDO",
    "NOMERES", "NOMERE", "NOMPRES", "NOMBPE", "NOMERO", "TITULAR", "PRIMER", "SEGUNDO", "BLICA", "PUBLICA", 
    "PÚBLICA", "ICADE", "CADE", "MEIA", "DILOM", "COLOM", "COLOMS", "LICA",
    "ELICA", "DILOMBIA", "LOM", "REPUBLI", "NIMEPO", "EDULA", "NIMERO", "NUMEPO",
    "NÚMEPO", "NVYMERO", "NVMERO", "NRO", "CEDLA", "CEDUIA", "CEDUI",
    "CFDULA", "CELDULA", "CIUDADAMA", "CIUDADANLA", "CIUDADANA", "CIUDADANÌA",
    "IDENTIF", "IDENTIFICACI", "IDENTIFICACIONPERSONAL", "REPUBLICADECOLOMBIA",
    "MOUSEES", "FMRMA", "FIRMAS", "FIRMADO", "ANDAQUIES", "CAQUETA",
    "FECHAYLUGARDEEXPEDICION", "LUGARDENACIMIENTG", "INDICEDERECHO", "REGISTRADGRNACIONAL",
    # Variantes OCR de REPUBLICA DE COLOMBIA y firmas espurias
    "NUBLIC", "NUBLICA", "PUBLIC", "RUBLIC", "RUBLICA", "UBLIC", "UBLICA",
    "REUBLICA", "REPUBLIC", "CAPE", "CAFE", "CP", "CADE", "CADES",
    # Ruidos de membretes institucionales, trámites y fotocopias
    "FOTOCOPIA", "PROCESO", "INSCRIPCION", "INSCRIPCIÓN", "MATRICULA", "MATRÍCULA",
    "EMPRENDEDORA", "EMPRENDEDOR", "EMPRENDIMIENTO", "OFICINA", "DEPARTAMENTAL",
    "MUNICIPAL", "SECRETARIA", "SECRETARÍA", "ALCALDIA", "ALCALDÍA", "GOBERNACION", "GOBERNACIÓN",
    "FACILITADO", "FACILITADA", "TECNOLOGICO", "TECNOLÓGICO", "ESTRATEGIA",
    "CAMPESENA", "CAMPESINA", "CAMPESINO", "FULLPOPULAR", "POPULAR", "SENA",
    "AMAZONIA", "AMAZONÍA", "CENTRO", "MUJER", "PROGRAMA", "TITULADA", "COMPLEMENTARIA",
    "CURSO", "FORMACION", "FORMACIÓN", "CONVENIO", "ASOCIACION", "COOPERATIVA",
    "LISTADO", "PARTICIPANTES", "APRENDICES", "APRENDIZ", "INSTRUCTOR", "INSTRUCTORA",
    "FICHA", "FOLIO", "ANEXO", "COPIA", "AUTENTICADA", "NOTARIA",
    # Nombres de ciudades/departamentos que aparecen en membretes institucionales
    # (NOTA: se filtran solo en contexto de ruido, no como nombres de persona)
    "CAQUETA", "CAQUETÁ", "PUTUMAYO", "HUILA", "TOLIMA", "VAUPES", "VAUPÉS",
    "GUAINIA", "GUAINÍA", "GUAVIARE", "ARAUCA", "VICHADA", "CASANARE",
    "FLORENCIACAQUETA", "FLORENCIACAQUETÁ",   # ciudad+dpto fusionados por OCR
    "MEDELLINANTIOQUÍA", "MEDELLÍNANTIOQUÍA", "BOGOTACUNDINAMARCA",
    "EMPRENDEDORA", "EMPRENDEDORAS",
}

# Diccionario canónico de nombres y apellidos comunes colombianos para desegmentación de tokens pegados
NOMBRES_COLOMBIANOS_COMUNES = {
    # Nombres masculinos
    "JUAN", "CARLOS", "LUIS", "JOSE", "JORGE", "MIGUEL", "DAVID", "DANIEL", "ANDRES",
    "ALEJANDRO", "CRISTIAN", "CHRISTIAN", "SEBASTIAN", "CAMILO", "FELIPE", "SANTIAGO",
    "DIEGO", "JULIAN", "JULIO", "MARIO", "MARTIN", "PEDRO", "PABLO", "GABRIEL", "RICARDO",
    "ROBERTO", "FERNANDO", "HECTOR", "OSCAR", "EDGAR", "CESAR", "JAIME", "ALEXANDER",
    "JHON", "JHONATAN", "JHOAN", "EDILMER", "EMERSON", "LEONEL", "HOMERO", "HAROLD",
    "HERNAN", "JAIRO", "JAVIER", "JESUS", "NELSON", "NESTOR", "RAFAEL", "RODRIGO",
    "SERGIO", "VICTOR", "YESID", "FABIAN", "ALVARO", "GERMAN", "MAURICIO", "WILSON",
    "GUSTAVO", "EDWIN", "FREDY", "FREDDY", "ALEXIS", "DUVAN", "BRAYAN", "KEVIN",
    # Nombres femeninos
    "MARIA", "ANA", "ANGI", "ANGIE", "CAROLINA", "PAOLA", "ANDREA", "DIANA", "LINA",
    "LILIANA", "LUZ", "LUCIA", "LUISA", "GLORIA", "PATRICIA", "PAULA", "SANDRA", "SONIA",
    "TATIANA", "VALENTINA", "VALERIA", "VANESSA", "VIVIANA", "YENNY", "YULIETH", "YURY",
    "MARCELA", "MARGARITA", "MARITZA", "MAYRA", "MONICA", "NANCY", "NATALIA", "KATHERINE",
    "LEIDY", "LEYDI", "YURANI", "BERCELIA", "DOLY", "ADRIANA", "CLAUDIA", "CONSTANZA",
    "ESPERANZA", "BLANCA", "MARTHA", "LUDIVIA", "YULIANA", "DANIELA", "CAMILA", "ISABELLA",
    "ISABEL", "SOFIA", "GABRIELA", "ALEJANDRA", "CATALINA", "EVELYN", "JESSICA", "DAYANA",
    "STEFANY", "STEPHANIE", "ELIZABETH", "CARMEN", "ROCIO", "XIMENA", "JIMENA", "INGRID",
    "AURA", "CECILIA", "CLEMENCIA", "NUBIA", "STELLA", "ESTELLA", "YOLANDA", "AMPARO",
    # Apellidos comunes colombianos
    "RODRIGUEZ", "GOMEZ", "GONZALEZ", "MARTINEZ", "GARCIA", "PEREZ", "LOPEZ", "HERNANDEZ",
    "SANCHEZ", "RAMIREZ", "TORRES", "FLORES", "FLOREZ", "DIAZ", "VASQUEZ", "CASTRO",
    "MORALES", "ORTIZ", "SILVA", "ROJAS", "GUTIERREZ", "JIMENEZ", "RUIZ", "ALVAREZ",
    "ROMERO", "MORENO", "MENDOZA", "ALONSO", "CASTILLO", "MEDINA", "VARGAS", "GUZMAN",
    "MUNOZ", "MUÑOZ", "ROCHA", "GUERRERO", "BENITEZ", "CORTES", "SOTO", "CARDONA",
    "OSORIO", "RESTREPO", "JARAMILLO", "DUQUE", "QUINTERO", "LONDONO", "LONDOÑO",
    "BEDOYA", "VILLA", "PECHENE", "CASTAÑO", "AGUDELO", "HENAO", "ZAPATA", "ZULUAGA",
    "RIVERA", "CHAVEZ", "ACUNA", "ACUÑA", "CARRILLO", "BAUTISTA", "PARRA", "SUAREZ",
    "OSPINA", "ESCOBAR", "MEJIA", "OCAMPO", "PINEDA", "TRUJILLO", "MONTOYA", "CEBALLOS",
    "MARIN", "OCHOA", "VALENCIA", "SALAZAR", "TAPIAS", "CIFUENTES", "MONROY", "PATINO",
    "PATIÑO", "CAMACHO", "BARON", "CACERES", "BARRERA", "BUSTOS", "CAMPO", "HURTADO",
    "VELASQUEZ", "MONCADA", "ARBOLEDA", "POSADA", "HIGUITA", "RENDON", "CORREA",
    "PALACIO", "RIOS", "VELEZ", "TABARES", "HERRERA", "BOTACHE", "VALERO", "MURCIA",
    "CORREDOR", "SALAS", "NARANJO", "CALDERON", "AGUIRRE", "ARIAS", "CARDENAS",
    "CABRERA", "CONTRERAS", "DELGADO", "DURAN", "ESPINOSA", "ESTRADA", "FRANCO",
    "GALVIS", "GIRALDO", "HOYOS", "IBARRA", "LOAIZA", "LOZANO", "MERCADO", "MORA",
    "NINO", "NIÑO", "ORDONEZ", "ORDOÑEZ", "OROZCO", "ORTEGA", "PADILLA", "PENA", "PEÑA",
    "PINZON", "PINZÓN", "PUERTA", "RINCON", "RINCÓN", "RIVAS", "ROA", "ROLDAN",
    "SALGADO", "SIERRA", "SOLER", "TRIANA", "URIBE", "VALLEJO", "VEGA", "VERA",
    "VILLAMIZAR", "VILLEGAS", "YEPES", "ZAMBRANO"
}

PATRON_RUIDO_ADMINISTRATIVO = re.compile(
    r"\b(FOTOCOPIA|PROCESO\s+DE\s+INSCRIPCI[OÓ]N|MATR[IÍ]CULA|EMPRENDEDOR[A]?S?|OFICINA\s+DEPARTAMENTAL|"
    r"DEPARTAMENTAL\s+DE\s+LA\s+MUJER|OFICINA.*MUJER|CENTRO\s+TECNOL[OÓ]GICO|ESTRATEGIA\s+CAMPES[EI]N[AO]|FULL\s*POPULAR|"
    r"CAMPES[EI]N[AO]\s*[-–—]?\s*FULL\s*POPULAR|SENA\s+CAQUET[AÁ]?|DOCUMENTO\s+DE\s+IDENTIDAD\s+FACILITADO|"
    r"FACILITADO\s+PARA\s+PROCESO|INSCRIPCI[OÓ]N.*MATR[IÍ]CULA|PARA\s+PROCESO\s+DE|"
    # Patrón ciudad-departamento fusionado por OCR (ej: FLORENCIA-CAQUETÁ, ARMENIA-QUINDÍO)
    r"FLORENCIA[\s\-]?CAQUET[AÁ]?|ARMENIA[\s\-]?QUIND|NEIVA[\s\-]?HUILA|TUNJA[\s\-]?BOYAC|"
    r"MOCOA[\s\-]?PUTUMAYO|LETICIA[\s\-]?AMAZON|MITU[\s\-]?VAUP|YOPAL[\s\-]?CASAR|"
    r"ARAUCA[\s\-]?ARAUCA|INIRIDA[\s\-]?GUAIN|SAN\s+JOSE[\s\-]?GUAVIARE|"
    # Instituciones educativas/gubernamentales
    r"ALCALD[IÍ]A\s+DE|GOBERNACI[OÓ]N\s+DE|SECRETAR[IÍ]A\s+DE|INSTITUTO\s+COLOMBIANO|"
    r"CORPORACI[OÓ]N|MINISTERIO\s+DE|UNIDAD\s+PARA|BIENESTAR\s+FAMILIAR|ICBF)",
    re.IGNORECASE
)

# Patrón de membrete de ficha institucional escrito sobre la hoja, ENCIMA de la fotocopia de la cédula.
# Ejemplo real: 'CC. 30507543 MARITZA GUTIERREZ MORENO' o 'CC 1006506310 LUCIA VARGAS'
# Este texto NO proviene de la cédula física, sino del encabezado de la planilla institucional.
PATRON_MEMBRETE_CC_EXTERNO = re.compile(
    r"^\s*(?:CC|C\.C\.)[\.\s:]+\d{6,10}\s+[A-ZÁÉÍÓÚÜÑ]{2,}(?:\s+[A-ZÁÉÍÓÚÜÑ]{2,}){1,4}\s*$",
    re.IGNORECASE
)

def es_linea_ruido_administrativo(texto: str) -> bool:
    """Detecta si una línea o texto corresponde a membretes de trámite, fotocopias o sellos.
    
    También cubre el patrón 'CC. 30507543 NOMBRE APELLIDO' que aparece como encabezado
    de ficha institucional escrito SOBRE la fotocopia de la cédula (no proviene de la cédula).
    """
    if not texto:
        return False
    if PATRON_RUIDO_ADMINISTRATIVO.search(texto):
        return True
    # Membrete de ficha: 'CC. NNNNNNNN NOMBRE APELLIDO APELLIDO'
    if PATRON_MEMBRETE_CC_EXTERNO.match(texto.strip()):
        return True
    return False


ROMAN_NOISE = {
    "I", "II", "III", "IIII", "IIIII", "IIIIII", "IV", "V", "VI", "VII", 
    "VIII", "IX", "X", "XI", "XII", "XIII", "XIV", "XV", "XVI", "XVII", 
    "XVIII", "XIX", "XX"
}

# Patrón para detectar fechas y meses de expedición/nacimiento deformados por OCR (ej: IOCTI, 10OCT, 21-OCT-2021, 03OCT, OCT2021)
PATRON_FECHA_MES_RUIDO = re.compile(
    r"^(?:[0-9]{1,2}|[IOl!]{1,2})[\s\-]*(?:ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC)[A-Z0-9]*$"
    r"|^(?:ENE|FEB|ABR|AGO|SEP|OCT|NOV|DIC)[0-9]{1,4}$"
    r"|^(?:ENE|FEB|ABR|AGO|SEP|OCT|NOV|DIC)$",
    re.I
)

PALABRAS_ENCABEZADO_CANONICAS = (
    "NUMERO", "CEDULA", "CIUDADANIA", "REPUBLICA", "IDENTIFICACION",
    "PERSONAL", "COLOMBIA", "NACIONAL", "REGISTRADURIA", "APELLIDOS",
    "NOMBRES", "EXPEDICION", "NACIMIENTO", "ESTATURA", "DERECHO", "INDICE", "FIRMA"
)

NOMBRES_LEGITIMOS_EXCEPCION = {
    "HOMERO", "DANIEL", "DIEGO", "ANA", "DOLY", "VARGAS", "VILLA",
    "ORTEGA", "RODRIGUEZ", "EDILMER", "LEONEL", "PEDRO", "JOSE", "MARIA",
    "JULIO", "JULIAN", "JULIA", "MARIO", "MARTIN", "MAYRA"
}

VOCALES_VALIDAS = set("AEIOUÁÉÍÓÚÜY")


def normalizar_str(s: str) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.upper().strip()


def _distancia_levenshtein(s1: str, s2: str) -> int:
    if len(s1) < len(s2):
        return _distancia_levenshtein(s2, s1)
    if len(s2) == 0:
        return len(s1)
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]


def es_token_ruido_difuso(t_alpha: str) -> bool:
    """Detecta si un token es una deformación por OCR de encabezados de cédula (ej: NIMEPO, EDULA)."""
    if not t_alpha or len(t_alpha) < 3:
        return False
    if t_alpha in NOMBRES_LEGITIMOS_EXCEPCION:
        return False
    for can in PALABRAS_ENCABEZADO_CANONICAS:
        max_d = 1 if len(can) <= 5 else 2
        d = _distancia_levenshtein(t_alpha, can)
        if d <= max_d:
            return True
    return False


def es_token_ruido(t_raw: str) -> bool:
    """Detecta si un token individual es ruido de OCR (IIII, números romanos, fechas, siglas, artefactos)."""
    if not t_raw:
        return True
    t_norm = normalizar_str(t_raw)
    t_alpha = re.sub(r"[^A-Z]", "", t_norm)
    if not t_alpha:
        return True
    # Secuencias puras de I (ej: I, II, III, IIII, IIIII...)
    if re.fullmatch(r"I+", t_alpha):
        return True
    # Números romanos o ruidos de líneas verticales
    if t_alpha in ROMAN_NOISE:
        return True
    # Palabras de encabezado y etiquetas de cédula/TI
    if t_alpha in JUNK_WORDS:
        return True
    # Detección de fechas o meses OCR deformados (ej: IOCTI, 10OCT, 21-OCT-2021, 03OCT, OCT2021)
    if PATRON_FECHA_MES_RUIDO.search(t_alpha) or PATRON_FECHA_MES_RUIDO.search(re.sub(r"[^A-Za-z0-9]", "", t_norm)):
        if t_alpha not in NOMBRES_LEGITIMOS_EXCEPCION:
            return True
    # Detección difusa de encabezados distorsionados por OCR (NIMEPO, EDULA, etc.)
    if es_token_ruido_difuso(t_alpha):
        return True
    # Letras solas (excepto la conjunción válida 'Y')
    if len(t_alpha) <= 1 and t_alpha != "Y":
        return True
    # Caracteres repetidos 3 o más veces consecutivas (ej: AAAA, XXXX, ZZZ)
    if re.search(r"(.)\1{2,}", t_alpha):
        return True
    # Palabras de 2 o más letras sin ninguna vocal (ej: CDI, MGR, PR, ST)
    if len(t_alpha) >= 2 and not any(v in VOCALES_VALIDAS for v in t_alpha):
        return True
    return False


SUFIJOS_FONDO_SEGURIDAD = ("LICA", "BLICA", "ELICA", "COLOM", "COLOMS", "DILOM")


def _descomponer_token_pegado(token: str) -> str:
    """
    Descompone un token si está formado por dos o más nombres/apellidos pegados
    (ej: 'BOTACHEVALERO' -> 'BOTACHE VALERO', 'ANGICAROLINA' -> 'ANGI CAROLINA').
    """
    if not token or len(token) < 6:
        return token
    t_clean = re.sub(r"[^A-ZÁÉÍÓÚÜÑ]", "", normalizar_str(token))
    if len(t_clean) < 6:
        return token
    # Si la palabra completa ya es un nombre legítimo conocido en el diccionario, no dividir
    # (ej: VILLAMIZAR no se divide en VILLA + MIZAR)
    if t_clean in NOMBRES_COLOMBIANOS_COMUNES and len(t_clean) <= 10:
        return token

    # Probar puntos de partición i entre 3 y len(t_clean)-2
    for i in range(3, len(t_clean) - 2):
        p1 = t_clean[:i]
        p2 = t_clean[i:]
        if p1 in NOMBRES_COLOMBIANOS_COMUNES and (p2 in NOMBRES_COLOMBIANOS_COMUNES or (len(p2) >= 6 and any(p2[:j] in NOMBRES_COLOMBIANOS_COMUNES and p2[j:] in NOMBRES_COLOMBIANOS_COMUNES for j in range(3, len(p2)-2)))):
            p2_split = _descomponer_token_pegado(p2)
            return f"{p1} {p2_split}"

    return token


def separar_nombres_pegados(texto: str) -> str:
    """
    Separa nombres y apellidos que fueron fusionados sin espacios por el OCR:
    1. CamelCase / PascalCase: 'BotacheValero' -> 'Botache Valero'
    2. Rótulos pegados al valor: 'APELLIDOSBOTACHE' -> 'APELLIDOS BOTACHE'
    3. Nombres pegados en mayúsculas: 'BOTACHEVALERO' -> 'BOTACHE VALERO', 'ANGICAROLINA' -> 'ANGI CAROLINA'
    """
    if not texto:
        return ""
    # 1. Separar transiciones CamelCase (minúscula a mayúscula)
    txt = re.sub(r"([a-záéíóúüñ])([A-ZÁÉÍÓÚÜÑ])", r"\1 \2", str(texto))
    # 2. Separar rótulos de cédula pegados al inicio
    txt = re.sub(r"\b(APELLIDOS?|NOMBRES?|CEDULA|NUMERO|CIUDADANIA)([A-ZÁÉÍÓÚÜÑ]{2,})\b", r"\1 \2", txt, flags=re.I)
    # 3. Separar tokens individuales en mayúsculas
    palabras = txt.split()
    resultado = []
    for p in palabras:
        resultado.append(_descomponer_token_pegado(p))
    return " ".join(resultado)


def limpiar_tokens_ruido(texto: str) -> str:
    if not texto:
        return ""
    # Desegmentar nombres o rótulos pegados sin espacios
    texto = separar_nombres_pegados(str(texto))
    # Reemplazar símbolos, barras, números y caracteres no alfabéticos
    limpio_pre = re.sub(r"[|!/\\\[\]{}()<>=*#+~_^¿?¡,.;:\d]", " ", str(texto))
    toks = limpio_pre.split()
    limpios = []
    for t in toks:
        if es_token_ruido(t):
            continue
        # Limpiar cualquier caracter residual no alfabético del token
        t_clean = re.sub(r"[^A-ZÁÉÍÓÚÜÑa-záéíóúüñ\-]", "", t).strip()
        t_upper = t_clean.upper()
        # Remover sufijos pegados de sellos de fondo (ej: PECHENELICA -> PECHENE)
        for suf in SUFIJOS_FONDO_SEGURIDAD:
            if t_upper.endswith(suf) and len(t_upper) - len(suf) >= 4:
                t_clean = t_clean[:-len(suf)]
                t_upper = t_clean.upper()
                break
        if t_clean and not es_token_ruido(t_clean):
            limpios.append(t_clean)
    # Quitar conectores al final o al inicio que queden huérfanos
    while limpios and limpios[-1].upper() in {"DE", "DEL", "LA", "LAS", "LOS", "Y"}:
        limpios.pop()
    while limpios and limpios[0].upper() in {"DE", "DEL", "LA", "LAS", "LOS", "Y"}:
        limpios.pop(0)
    return " ".join(limpios)


def deduplicar_ngrams(texto: str) -> str:
    """
    Elimina repeticiones consecutivas de n-gramas de palabras (longitud k >= 2).
    Ejemplo: 'VARGAS VILLA VARGAS VILLA' -> 'VARGAS VILLA'.
    Para palabras individuales (k = 1): NUNCA colapsa repeticiones de 2 palabras consecutivas
    (ej: 'RODRIGUEZ RODRIGUEZ' o 'VILLA VILLA'), ya que en Colombia los apellidos paterno y
    materno coinciden legítimamente. Solo deduplica si una palabra se repite 3 o más veces
    consecutivas (ej: 'A A A' -> 'A A').
    """
    words = texto.split()
    if not words:
        return ""
    n = len(words)
    # 1. Deduplicar n-gramas de longitud k >= 2
    for k in range(n // 2, 1, -1):
        for i in range(n - 2 * k + 1):
            if [w.upper() for w in words[i:i + k]] == [w.upper() for w in words[i + k:i + 2 * k]]:
                words = words[:i + k] + words[i + 2 * k:]
                return deduplicar_ngrams(" ".join(words))

    # 2. Para k = 1: solo deduplicar si se repite 3 o más veces consecutivas (OCR loop glitch)
    for i in range(len(words) - 2):
        if words[i].upper() == words[i + 1].upper() == words[i + 2].upper():
            words = words[:i + 2] + words[i + 3:]
            return deduplicar_ngrams(" ".join(words))

    return " ".join(words)


def distancia_levenshtein(s1: str, s2: str) -> int:
    """Calcula la distancia de edición Levenshtein entre dos cadenas."""
    if s1 == s2:
        return 0
    if len(s1) < len(s2):
        return distancia_levenshtein(s2, s1)
    if len(s2) == 0:
        return len(s1)
    prev = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr = [i + 1] * (len(s2) + 1)
        for j, c2 in enumerate(s2):
            curr[j + 1] = prev[j] if c1 == c2 else min(prev[j], prev[j + 1], curr[j]) + 1
        prev = curr
    return prev[len(s2)]


def tokens_similares(t1: str, t2: str) -> bool:
    """Determina si dos palabras o nombres son idénticos o variaciones tipográficas/OCR del mismo."""
    t1 = t1.upper()
    t2 = t2.upper()
    if t1 == t2:
        return True
    if len(t1) < 3 or len(t2) < 3:
        return False
    d = distancia_levenshtein(t1, t2)
    if d <= 1:
        return True
    if d <= 2 and len(t1) >= 4 and len(t2) >= 4 and t1[:3] == t2[:3]:
        return True
    return False


def deduplicar_tokens_nombre(texto: str) -> str:
    """
    Elimina tokens duplicados a lo largo del nombre completo (exactos o con ligeras variaciones OCR),
    preservando repeticiones legítimas consecutivas de apellidos paterno y materno
    (ej: 'RODRIGUEZ RODRIGUEZ' o 'VILLA VILLA'), pero eliminando duplicados no consecutivos
    (ej: 'ANGUIE CAROLINA BOTACHE ANGI CAROLINA' -> 'ANGUIE CAROLINA BOTACHE').
    """
    words = texto.split()
    if not words:
        return ""
    resultado = []
    for w in words:
        w_up = w.upper()
        # Si es idéntico al token inmediatamente anterior, permitir hasta 2 consecutivas
        if resultado and resultado[-1].upper() == w_up:
            consecutivos = 0
            for r in reversed(resultado):
                if r.upper() == w_up:
                    consecutivos += 1
                else:
                    break
            if consecutivos >= 2:
                continue
            resultado.append(w)
            continue

        # Si no es consecutivo, verificar si ya se vio un token idéntico o muy similar antes
        ya_visto = False
        for r in resultado:
            if tokens_similares(r, w):
                ya_visto = True
                break
        if not ya_visto:
            resultado.append(w)

    return " ".join(resultado)


def resolver_nombre_completo(nombres: str, apellidos: str = "", actual: str = None) -> str:
    """
    Unifica nombres y apellidos evitando duplicados accidentales (ej: nombres ya contiene apellidos,
    apellidos repite nombres, o variaciones OCR del mismo nombre) y eliminando ruidos institucionales.
    """
    n_limpio = limpiar_tokens_ruido(nombres or "")
    a_limpio = limpiar_tokens_ruido(apellidos or "")

    toks_n = n_limpio.split()
    toks_a = a_limpio.split()

    if not a_limpio and not n_limpio and actual and actual.strip() and actual != "POR REVISAR":
        res = limpiar_tokens_ruido(actual)
    elif not a_limpio:
        res = n_limpio
    elif not n_limpio:
        res = a_limpio
    else:
        # Verificar si toks_a es un subconjunto (exacto o fuzzy) de toks_n
        a_en_n = [any(tokens_similares(t_a, t_n) for t_n in toks_n) for t_a in toks_a]
        n_en_a = [any(tokens_similares(t_n, t_a) for t_a in toks_a) for t_n in toks_n]

        if all(a_en_n):
            # Todos los apellidos ya están presentes en nombres (ej: nombres="ANGUIE CAROLINA BOTACHE", apellidos="ANGI CAROLINA")
            res = n_limpio
        elif all(n_en_a):
            # Todos los nombres ya están en apellidos
            res = a_limpio
        else:
            # Filtrar de apellidos los tokens que ya están en nombres
            toks_a_filtrados = []
            for t_a in toks_a:
                if any(tokens_similares(t_a, t_n) for t_n in toks_n):
                    continue
                toks_a_filtrados.append(t_a)

            # Filtrar de nombres los tokens de apellidos que se colaron
            toks_n_filtrados = []
            for t_n in toks_n:
                if any(tokens_similares(t_n, t_a) for t_a in toks_a_filtrados):
                    continue
                toks_n_filtrados.append(t_n)

            str_n = " ".join(toks_n_filtrados)
            str_a = " ".join(toks_a_filtrados)
            if str_n and str_a:
                res = f"{str_n} {str_a}".strip()
            elif str_n:
                res = str_n
            elif str_a:
                res = str_a
            else:
                res = n_limpio or a_limpio

    if actual and actual.strip() and actual != "POR REVISAR":
        act_limp = limpiar_tokens_ruido(actual)
        # Solo preferir actual si actual es legítimo (sin palabras de ruido administrativo)
        if not es_linea_ruido_administrativo(actual):
            act_dedup = deduplicar_tokens_nombre(deduplicar_ngrams(act_limp))
            if (not res or res == "POR REVISAR") and len(act_dedup.split()) >= 2:
                res = act_dedup
            elif len(act_dedup.split()) > len(res.split()) and len(act_dedup.split()) >= 2 and (not a_limpio or not n_limpio):
                res = act_dedup

    res = deduplicar_ngrams(res)
    res = deduplicar_tokens_nombre(res)
    res = limpiar_tokens_ruido(res)
    return res.upper().strip() or "POR REVISAR"
