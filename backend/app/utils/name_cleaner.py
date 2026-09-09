"""
Utilidad para limpieza, sanitización y deduplicación de nombres y apellidos
en documentos de identidad colombianos.
"""
import re
import unicodedata

JUNK_WORDS = {
    "IDENTIDAD", "TARJETA", "CEDULA", "CIUDADANIA", "REPUBLICA", "COLOMBIA", 
    "RETUBEICA", "REPUBLICA", "REPÚBLICA", "NACIONAL", "REGISTRADURIA", 
    "ESTADO", "NUMERO", "FIRMA", "HUELLA", "INDICE", "DERECHO", "IZQUIERDO", 
    "DOCUMENTO", "PERSONAL", "REGISTRO", "CIVIL", "EXPEDICION", "LUGAR", 
    "FECHA", "NACIMIENTO", "SEXO", "ESTATURA", "RH", "VIGENCIA", "POSTAL", 
    "CUE", "III", "DR", "CDI", "AAAS", "AAS"
}


def normalizar_str(s: str) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.upper().strip()


def limpiar_tokens_ruido(texto: str) -> str:
    if not texto:
        return ""
    toks = texto.split()
    limpios = []
    for t in toks:
        t_norm = normalizar_str(t)
        t_norm = re.sub(r"[^A-Z]", "", t_norm)
        if t_norm in JUNK_WORDS:
            continue
        if len(t_norm) <= 1 and t_norm not in {"Y"}:
            continue
        limpios.append(t)
    # Quitar conectores al final o al inicio
    while limpios and limpios[-1].upper() in {"DE", "DEL", "LA", "LAS", "LOS", "Y"}:
        limpios.pop()
    while limpios and limpios[0].upper() in {"DE", "DEL", "LA", "LAS", "LOS", "III"}:
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

    if not a_limpio:
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

    res = deduplicar_ngrams(res)
    res = limpiar_tokens_ruido(res)
    return res.upper().strip() or "POR REVISAR"
