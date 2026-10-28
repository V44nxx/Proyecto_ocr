"""Validaciones de archivos subidos"""
import re
from pathlib import Path

from fastapi import HTTPException

from app.config import settings

LARGO_MAXIMO_NOMBRE = 150


def verificar_tamano_archivo(contenido: bytes, nombre: str) -> None:
    """Rechaza con 413 los archivos que superan MAX_FILE_SIZE_MB"""
    if len(contenido) > settings.max_file_size_bytes:
        raise HTTPException(
            status_code=413,
            detail=(
                f"El archivo '{nombre}' pesa {len(contenido) / (1024 * 1024):.1f} MB "
                f"y el máximo permitido es {settings.MAX_FILE_SIZE_MB} MB"
            ),
        )


def nombre_archivo_seguro(nombre: str | None, por_defecto: str = "archivo") -> str:
    """
    Nombre para guardar en disco a partir del que manda el navegador: sin carpetas (ni / ni \\), sin
    caracteres que Windows o Linux interpreten, sin puntos al inicio y con un largo máximo.
    Conserva letras con tilde, espacios, paréntesis y la extensión.
    """
    base = re.split(r"[\\/]", nombre or "")[-1]
    base = re.sub(r"[\x00-\x1f<>:\"|?*]", "_", base).strip().lstrip(".").strip()
    if not base:
        return por_defecto
    if len(base) > LARGO_MAXIMO_NOMBRE:
        raiz, punto, extension = base.rpartition(".")
        if punto and 0 < len(extension) <= 10:
            base = raiz[: LARGO_MAXIMO_NOMBRE - len(extension) - 1] + "." + extension
        else:
            base = base[:LARGO_MAXIMO_NOMBRE]
    return base


def borrar_archivo_subido(ruta: str | None) -> bool:
    """
    Borra un archivo guardado por la aplicación. La ruta sale de la base de datos: solo se borra si queda
    dentro de la carpeta de subidas, así una ruta alterada no puede borrar nada fuera de ella.
    """
    if not ruta:
        return False
    archivo = Path(ruta).resolve()
    if not archivo.is_relative_to(settings.upload_path.resolve()) or not archivo.is_file():
        return False
    archivo.unlink()
    return True


def numero_ficha_de(nombre: str | None) -> str | None:
    """
    Número de ficha (7 dígitos) en el nombre del archivo: "DOCUMENTOS FICHA 3100001.pdf" -> "3100001".
    None si no trae ninguno o trae varios distintos (no se puede saber a qué ficha corresponde).
    """
    numeros = set(re.findall(r"(?<!\d)(\d{7})(?!\d)", nombre or ""))
    return numeros.pop() if len(numeros) == 1 else None
