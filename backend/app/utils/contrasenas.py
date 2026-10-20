"""
Política de contraseñas (NIST SP 800-63B): largo mínimo, tope de bcrypt y rechazo de contraseñas
comunes o armadas con palabras del contexto (el nombre de la app, "admin", "colombia"...).
No se exigen mezclas de mayúsculas y símbolos: una frase larga es más segura y más fácil de recordar.
"""
import re
import unicodedata

LARGO_MINIMO = 8
BYTES_MAXIMO = 72  # bcrypt ignora lo que pase de 72 bytes

# Contraseñas más usadas (listas públicas de filtraciones), en minúsculas
COMUNES = {
    "123456", "1234567", "12345678", "123456789", "1234567890", "0123456789", "987654321", "111111", "11111111",
    "000000", "00000000", "121212", "123123", "123123123", "112233", "654321", "666666", "7777777", "88888888",
    "99999999", "123321", "1q2w3e4r", "1q2w3e4r5t", "1qaz2wsx", "zaq12wsx", "qwerty", "qwerty123", "qwertyuiop",
    "asdfghjkl", "asdf1234", "zxcvbnm", "azerty", "password", "password1", "password123", "passw0rd", "p@ssw0rd",
    "iloveyou", "princess", "sunshine", "football", "baseball", "monkey", "dragon", "letmein", "welcome",
    "welcome1", "master", "shadow", "superman", "batman", "trustno1", "abc123", "abcd1234", "abcdef", "abcdefgh",
    "a1b2c3d4", "secret", "changeme", "default", "guest", "login", "user", "usuario", "usuario1", "admin",
    "administrador", "root", "toor", "contrasena", "contrasena1", "contrasena123", "clave",
    "clave123", "micontrasena", "teamo", "teamo123", "tequiero", "mariposa", "estrella", "corazon", "princesa",
    "colombia", "colombia1", "bogota", "medellin", "america", "millonarios", "nacional", "santafe", "sena",
    "senasofia", "documentos", "cedula", "kondid", "ocr", "sistema", "prueba", "prueba123", "test", "test123",
}

# Palabras que, con números o símbolos alrededor, siguen siendo fáciles de adivinar en este sistema
PALABRAS_DEL_CONTEXTO = {
    "password", "passw0rd", "contrasena", "clave", "admin", "administrador", "usuario", "user", "kondid",
    "ocr", "sena", "colombia", "qwerty", "abc", "abcd", "test", "prueba", "cedula", "documento", "documentos",
}


def _normalizar(texto: str) -> str:
    """Minúsculas y sin tildes (contraseña → contrasena)."""
    sin_tildes = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in sin_tildes if not unicodedata.combining(c))


def problema_contrasena(clave: str) -> str | None:
    """Devuelve el motivo por el que la contraseña no sirve, o None si sirve."""
    if len(clave) < LARGO_MINIMO:
        return f"La contraseña debe tener al menos {LARGO_MINIMO} caracteres"
    if len(clave.encode("utf-8")) > BYTES_MAXIMO:
        return f"La contraseña no puede tener más de {BYTES_MAXIMO} caracteres"
    normal = _normalizar(clave)
    base = re.sub(r"[^a-zñ]", "", normal)  # sin números ni símbolos: Kondid2026! → kondid
    if normal in COMUNES or base in PALABRAS_DEL_CONTEXTO or not base and len(set(normal)) <= 3:
        return "Esa contraseña es muy común o fácil de adivinar; usa una frase o una combinación menos predecible"
    if normal.isdigit() and (normal in "01234567890123456789" or normal in "98765432109876543210"):
        return "Esa contraseña es una secuencia de números; usa una frase o una combinación menos predecible"
    return None


def validar_contrasena(clave: str) -> str:
    """Validador para Pydantic: lanza ValueError con el motivo."""
    motivo = problema_contrasena(clave)
    if motivo:
        raise ValueError(motivo)
    return clave
