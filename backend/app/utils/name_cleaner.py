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
    "NOMBRE", "APELLIDO", "TITULAR", "PRIMER", "SEGUNDO", "BLICA", "PUBLICA", 
    "PÚBLICA", "ICADE", "CADE", "MEIA", "DILOM", "COLOM", "COLOMS", "LICA",
    "ELICA", "DILOMBIA", "LOM", "REPUBLI"
}

ROMAN_NOISE = {
    "I", "II", "III", "IIII", "IIIII", "IIIIII", "IV", "V", "VI", "VII", 
    "VIII", "IX", "X", "XI", "XII", "XIII", "XIV", "XV", "XVI", "XVII", 
    "XVIII", "XIX", "XX"
}

VOCALES_VALIDAS = set("AEIOUÁÉÍÓÚÜY")


def normalizar_str(s: str) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.upper().strip()


def es_token_ruido(t_raw: str) -> bool:
    """Detecta si un token individual es ruido de OCR (IIII, números romanos, siglas, artefactos)."""
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


def limpiar_tokens_ruido(texto: str) -> str:
    if not texto:
        return ""
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
    """Elimina repeticiones consecutivas de n-gramas de palabras (ej: 'A B C B C' -> 'A B C')"""
    words = texto.split()
    if not words:
        return ""
    n = len(words)
    # Intentar secuencias repetidas de longitud k desde n//2 hasta 1
    for k in range(n // 2, 0, -1):
        for i in range(n - 2 * k + 1):
            if [w.upper() for w in words[i:i + k]] == [w.upper() for w in words[i + k:i + 2 * k]]:
                words = words[:i + k] + words[i + 2 * k:]
                return deduplicar_ngrams(" ".join(words))
    return " ".join(words)


def resolver_nombre_completo(nombres: str, apellidos: str = "", actual: str = None) -> str:
    """
    Unifica nombres y apellidos evitando duplicados accidentales (ej: nombres ya contiene apellidos)
    y eliminando ruidos institucionales (IDENTIDAD, CUE, RETUBEICA, etc.).
    """
    # Si ya viene un actual explícito y limpio, intentar deduplicarlo
    if actual and actual.strip() and actual != "POR REVISAR":
        act_limpio = limpiar_tokens_ruido(actual)
        act_dedup = deduplicar_ngrams(act_limpio)
        if len(act_dedup.split()) >= 2:
            # Si actual tiene al menos 2 palabras y no es idéntico a una sola palabra repetida
            pass

    n_limpio = limpiar_tokens_ruido(nombres or "")
    a_limpio = limpiar_tokens_ruido(apellidos or "")

    n_norm = normalizar_str(n_limpio)
    a_norm = normalizar_str(a_limpio)

    toks_n = n_norm.split()
    toks_a = a_norm.split()

    if not a_limpio and not n_limpio and actual and actual.strip() and actual != "POR REVISAR":
        res = limpiar_tokens_ruido(actual)
    elif not a_limpio:
        res = n_limpio
    elif not n_limpio:
        res = a_limpio
    elif n_norm.endswith(a_norm):
        res = n_limpio
    elif n_norm.replace(" ", "").endswith(a_norm.replace(" ", "")):
        res = n_limpio
    elif set(toks_a).issubset(set(toks_n)):
        res = n_limpio
    elif set(toks_n).issubset(set(toks_a)):
        res = a_limpio
    else:
        res = f"{n_limpio} {a_limpio}".strip()

    if actual and actual.strip() and actual != "POR REVISAR":
        act_limp = limpiar_tokens_ruido(actual)
        # Si actual tiene más palabras válidas que lo combinado, preferir actual
        if len(act_limp.split()) > len(res.split()) and len(act_limp.split()) >= 2:
            res = act_limp

    res = deduplicar_ngrams(res)
    res = limpiar_tokens_ruido(res)
    return res.upper().strip() or "POR REVISAR"
