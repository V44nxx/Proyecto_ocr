"""
Reparación de nombres dañados por el limpiador de nombres anterior a la versión 2.3.0.

Ese limpiador quitaba la vocal final de nombres como ANGELA, JULIANA o MANUELA (quedaban ANGEL, JULIAN,
MANUEL) y borraba nombres o apellidos parecidos a un encabezado de la cédula (ROMERO por NUMERO, INDIRA
por INDICE). Esta reparación corre una sola vez por persona:
  1. Si la persona está en una planilla Excel de su usuario y su nombre es justo una versión dañada del
     nombre de la planilla, se recupera el nombre de la planilla.
  2. Si no, a las mujeres con un nombre masculino que el limpiador pudo haber recortado se les marca
     "Por revisar" para que se confirme contra la cédula.
"""
import re
import unicodedata
from typing import Dict, Optional

from app.utils.name_cleaner import NOMBRES_COLOMBIANOS_COMUNES, PALABRAS_ENCABEZADO_CANONICAS, _distancia_levenshtein

MARCA_REVISADO = "revision_nombre_recortado"
CAMPO_SOSPECHA = "posible_nombre_recortado"

# Solo los que el limpiador anterior recortaba: el masculino estaba en su lista de nombres y el femenino no.
# Fija: era la lista de ese momento. Calcularla con la actual la cambiaba cada vez que se agregaban nombres
# (con JULIANA y ANGELA en el diccionario dejaban de revisarse JULIAN y ANGEL)
MASCULINOS_RECORTABLES = frozenset({
    "ANGEL", "CRISTIAN", "FABIAN", "JULIAN", "MANUEL", "MARTIN", "MIGUEL", "RAFAEL", "SEBASTIAN",
})


def _norm(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", str(texto or ""))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", texto.upper()).strip()


def _parece_encabezado(token: str) -> bool:
    """Palabras que el limpiador anterior borraba por parecerse a un encabezado (ROMERO ~ NUMERO)"""
    return any(
        _distancia_levenshtein(token, can) <= (1 if len(can) <= 5 else 2)
        for can in PALABRAS_ENCABEZADO_CANONICAS
    )


def _es_recorte(actual: str, oficial: str) -> bool:
    """El token actual es el oficial sin su vocal final, como lo dejaba el limpiador anterior"""
    return (
        len(oficial) >= 5
        and oficial[-1] in "AEIOU"
        and actual == oficial[:-1]
        and actual in NOMBRES_COLOMBIANOS_COMUNES
    )


def nombre_recuperado(actual: Optional[str], oficial: Optional[str]) -> Optional[str]:
    """
    Devuelve el nombre de la planilla si el nombre actual es exactamente una versión dañada de él
    (vocales finales recortadas o palabras parecidas a encabezados borradas, en el mismo orden).
    Devuelve None si no hay nada que recuperar o si la diferencia es de otro tipo.
    """
    t_act = _norm(actual).split()
    t_ofi = _norm(oficial).split()
    if not t_act or not t_ofi or t_act == t_ofi:
        return None

    i = 0
    for tok in t_act:
        while i < len(t_ofi) and tok != t_ofi[i] and not _es_recorte(tok, t_ofi[i]):
            if not _parece_encabezado(t_ofi[i]):
                return None
            i += 1
        if i == len(t_ofi):
            return None
        i += 1
    if any(not _parece_encabezado(t) for t in t_ofi[i:]):
        return None
    return " ".join(t_ofi)


def sospecha_de_recorte(nombre: Optional[str], sexo: Optional[str]) -> Optional[str]:
    """Para una mujer, devuelve el primer nombre masculino que el limpiador anterior pudo haber recortado"""
    if _norm(sexo) not in ("F", "FEMENINO"):
        return None
    for tok in _norm(nombre).split():
        if tok in MASCULINOS_RECORTABLES:
            return tok
    return None


def detalle_sospecha(token: str) -> Dict[str, str]:
    return {
        "valor": token,
        "sugerencia": f"{token}A",
        "status": "REVIEW_REQUIRED",
        "source": "revision_2_3_0",
        "reason": (
            f"El nombre '{token}' pudo quedar recortado por el OCR (¿{token}A?). "
            "Confírmalo contra la cédula y corrígelo si hace falta."
        ),
    }
