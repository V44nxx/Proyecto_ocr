"""
Validadores para datos extraídos de documentos colombianos.

CAMBIOS v2 (optimización precisión):
  - validar_cedula: rango Colombia real es 6-10 dígitos (no 12).
    Cédulas colombianas: 6 dígitos (mínimo), 10 dígitos (máximo actual).
  - parsear_fecha: soporte nativo para YYYY-MM-DD que viene del MRZ,
    y para variantes textuales con errores OCR (ENER0 → ENERO, etc.).
  - normalizar_nombre: limita salida a máximo 5 palabras para evitar
    capturar párrafos enteros como nombre.
  - normalizar_lugar: filtra palabras genéricas (COLOMBIA, REPUBLICA...).
"""
import re
from datetime import date, datetime
from typing import Optional, Tuple
from app.utils.logger import app_logger as logger


class ValidadorColombia:
    """Validadores específicos para documentos de identificación colombianos."""

    # Palabras que no son nombres de persona válidos (etiquetas/artefactos de cédula, marcas de agua, registradores)
    _PALABRAS_NO_NOMBRE = re.compile(
        r"\b(FIRMA|FIRMAS|TITULAR|HUELLA|DERECHO|IZQUIERDO|INDICE|ÍNDICE|REPUBLICA|REPÚBLICA|REPUBL|"
        r"COLOMBIA|CEDULA|CÉDULA|CIUDADANIA|CIUDADANÍA|IDENTIFICACION|IDENTIFICACIÓN|NUIP|"
        r"NUMERO|NÚMERO|NOMBRES|APELLIDOS|NOMBRE|APELLIDO|LUGAR|EXPEDICION|EXPEDICIÓN|EXPIRACION|EXPIRACIÓN|"
        r"NACIMIENTO|FECHA|SEXO|ESTATURA|NACIONALIDAD|REGISTRADOR|REGISTRADORA|REGISTRADURIA|GERENTE|MINISTERIO|"
        r"CAMSCANNER|POWERED|SCANNER|CS|PANENZ|BAILS|DANCING|ARCHIV|DOC|DOCUMENTO|REGISTRO|CIVIL|"
        r"ALMABEATRIZ|RENGIFO|GALINDO|VEGA|SÁNCHEZ|SANCHEZ|TORRES|SCANNED|WITH|PERSONAL|NACIONAL)\b",
        re.IGNORECASE,
    )

    # Palabras que no son nombres de lugar válidos (aparecen en encabezados, labels, firmas y registradores)
    _PALABRAS_NO_LUGAR = re.compile(
        r"\b(REPUBLICA|REPÚBLICA|COLOMBIA|CIUDADANA|CIUDADANIA|CIUDADANÍA|IDENTIFICACION|IDENTIFICACIÓN|"
        r"TARJETA|CEDULA|CÉDULA|NUIP|PERSONAL|NACIONAL|FECHA|EXPEDICION|EXPEDICIÓN|EXPIRACION|EXPIRACIÓN|"
        r"LUGAR|Y|INDICE|ÍNDICE|DERECHO|IZQUIERDO|HUELLA|FIRMA|FIRMAS|REGISTRADOR|REGISTRADORA|REGISTRADURIA|"
        r"PANENZ|BAILS|DANCING|DEPARTAMENTO|MUNICIPIO|OFICINA|PROVINCIA|ESTADO|ESTADOL|CIVIL|GIVIL|ALDEL|DIRECTOR|SECRETARIO|"
        r"ALERGIF|ALMABEATRIZ|RENGIFO|BENGIFO|LOPET|LOPEZ|LÓPEZ|PENAGOS|GIRALDO|HERNAN|HERNÁN|CARLOS|ARIEL|"
        r"SANCHEZ|SÁNCHEZ|TORRES|GALINDO|VACHA|JUAN|ALEXANDER|VEGA|ROCHA|ESTATURA|GRUPO|SANGUINEO|SANGUÍNEO|RH|"
        r"NACIMIENTO|NACIDO|MA|ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC|ENERO|FEBRERO|MARZO|ABRIL|MAYO|JUNIO|JULIO|AGOSTO|SEPTIEMBRE|OCTUBRE|NOVIEMBRE|DICIEMBRE)\b",
        re.IGNORECASE,
    )

    # ──────────────────────────────────────────
    # IDENTIFICACIÓN
    # ──────────────────────────────────────────
    @staticmethod
    def limpiar_identificacion(numero: str) -> str:
        """
        Limpia y normaliza el número de identificación para comparaciones y consultas en BD.
        Elimina prefijos como 'CC', 'NUIP', 'No.', puntos, comas, espacios y guiones.
        """
        if not numero:
            return ""
        txt = str(numero).strip()
        txt = re.sub(r"^(C\.?C\.?|NUIP|NO\.?|N[UÚ]MERO|CEDULA|C[EÉ]DULA)\s*:?", "", txt, flags=re.IGNORECASE)
        txt = txt.replace(" ", "").replace(".", "").replace(",", "").replace("-", "").replace("_", "")
        m = re.search(r"\d{6,10}", txt)
        if m:
            return m.group(0)
        return txt.strip()

    @staticmethod
    def validar_cedula(numero: str) -> Tuple[bool, str]:
        """
        Valida número de cédula colombiana.

        FIX: rango real en Colombia es 6-10 dígitos (no 12).
        Las cédulas colombianas van de 6 dígitos (antiguas de pequeños
        municipios) a 10 dígitos (actuales). 11-12 dígitos son
        probablemente errores OCR que concatenaron dos campos.

        Reglas:
          - Solo dígitos después de limpieza
          - Longitud: 6-10 dígitos
          - Primer dígito ≠ 0
        """
        if not numero:
            return False, "Número vacío"

        numero_limpio = (
            str(numero).strip()
            .replace(" ", "")
            .replace(".", "")
            .replace(",", "")
            .replace("-", "")
        )

        if not numero_limpio.isdigit():
            return False, f"Contiene no-dígitos: '{numero_limpio}'"

        if numero_limpio.startswith("0"):
            return False, "Comienza con cero"

        longitud = len(numero_limpio)
        if longitud < 7:
            return False, f"Muy corto ({longitud} dígitos) — ignora seriales sueltos de 6 dígitos"
        if longitud > 10:
            return False, f"Muy largo ({longitud} dígitos) — probable concatenación"

        return True, numero_limpio

    # ──────────────────────────────────────────
    # NOMBRES Y APELLIDOS
    # ──────────────────────────────────────────
    @classmethod
    def corregir_errores_ocr_nombre(cls, texto: str) -> str:
        """Corrije errores tipográficos típicos de OCR en nombres y apellidos."""
        if not texto:
            return ""
        txt = str(texto).upper()
        # Trailing ! / 1 / | / ] en palabras (ej. SAB! -> SABI)
        txt = re.sub(r"([A-ZÁÉÍÓÚÜÑ]{2,})[!1|\]]", r"\1I", txt)
        # 0 o 1 intercalados en palabras (ej. G0MEZ -> GOMEZ, MART1NEZ -> MARTINEZ)
        txt = re.sub(r"([A-ZÁÉÍÓÚÜÑ]+)0([A-ZÁÉÍÓÚÜÑ]+)", r"\1O\2", txt)
        txt = re.sub(r"([A-ZÁÉÍÓÚÜÑ]+)1([A-ZÁÉÍÓÚÜÑ]+)", r"\1I\2", txt)
        # 0 o 5 al final de palabras (ej. CASTILL0 -> CASTILLO, VARGA5 -> VARGAS)
        txt = re.sub(r"([A-ZÁÉÍÓÚÜÑ]{2,})0\b", r"\1O", txt)
        txt = re.sub(r"([A-ZÁÉÍÓÚÜÑ]{2,})5\b", r"\1S", txt)
        return txt

    @classmethod
    def normalizar_nombre(cls, texto: str) -> Optional[str]:
        """
        Normaliza nombres y apellidos:
          - Solo letras, espacios, tildes y ñ
          - Mayúsculas
          - Elimina espacios múltiples
          - Limita a 5 palabras (evita capturar párrafos)

        FIX: sin límite de palabras, el regex anterior capturaba
        frases enteras del documento como nombre.
        """
        if not texto:
            return None

        # Corregir sustituciones OCR habituales (ej. SAB! -> SABI)
        texto = cls.corregir_errores_ocr_nombre(texto)

        # Solo letras y espacios (incluyendo caracteres latinos)
        texto = re.sub(r"[^A-ZÁÉÍÓÚÜÑa-záéíóúüñ\s\-]", "", texto)
        # Normalizar espacios
        texto = " ".join(texto.split())
        texto = texto.upper()

        if not texto:
            return None

        # Filtrar palabras que son artefactos o etiquetas de la cédula (ej: FIRMA, TITULAR)
        palabras_filtradas = [
            p for p in texto.split()
            if not cls._PALABRAS_NO_NOMBRE.match(p) and len(p) > 1
        ]

        if not palabras_filtradas:
            return None

        # Limitar a máximo 5 palabras
        resultado = " ".join(palabras_filtradas[:5])

        # Mínimo 3 caracteres y no ser solo palabras genéricas de enlace
        if len(resultado) < 3 or resultado in ("DE", "DEL", "CA DE", "LA", "EL", "LOS", "LAS"):
            return None

        return resultado

    # ──────────────────────────────────────────
    # FECHAS
    # ──────────────────────────────────────────
    @staticmethod
    def parsear_fecha(texto: str) -> Optional[date]:
        """
        Parsea fechas en múltiples formatos colombianos:
          - DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY
          - YYYY-MM-DD (formato ISO, output del MRZ)
          - DD de NOMBRE_MES de YYYY (con variantes OCR en el nombre del mes)

        FIX: el parser anterior asumía siempre DD/MM/YYYY y fallaba
        en silencio con YYYY-MM-DD del MRZ (ponía el año como día).
        """
        if not texto:
            return None

        texto = str(texto).strip()

        # ── Formato YYYY-MM-DD (ISO / MRZ) ───────────────────────────────
        match_iso = re.match(r"^(\d{4})[/\-\.](\d{1,2})[/\-\.](\d{1,2})$", texto)
        if match_iso:
            anio, mes, dia = match_iso.groups()
            try:
                return date(int(anio), int(mes), int(dia))
            except ValueError:
                pass

        # ── Formato DD/MM/YYYY ────────────────────────────────────────────
        match_dmy = re.match(r"^(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{4})$", texto)
        if match_dmy:
            dia, mes, anio = match_dmy.groups()
            try:
                return date(int(anio), int(mes), int(dia))
            except ValueError:
                pass

        # ── Formato DD-MMM-YYYY (ej. 05-MAY-1987, 26-JUN-2007, 05/MAY/1987) ──
        MESES = {
            "ENERO": 1, "FEBRERO": 2, "MARZO": 3, "ABRIL": 4,
            "MAYO": 5, "JUNIO": 6, "JULIO": 7, "AGOSTO": 8,
            "SEPTIEMBRE": 9, "OCTUBRE": 10, "NOVIEMBRE": 11, "DICIEMBRE": 12,
            # Abreviaturas
            "ENE": 1, "FEB": 2, "MAR": 3, "ABR": 4, "MAY": 5, "JUN": 6,
            "JUL": 7, "AGO": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DIC": 12,
            "JAN": 1, "APR": 4, "AUG": 8, "DEC": 12,
            # Variantes OCR frecuentes
            "ENER0": 1, "FEBRER0": 2, "MARZ0": 3, "ABR1L": 4,
            "AGOST0": 8, "SEPTIEMBRE": 9, "0CTUBRE": 10, "NOVIEMBRE": 11,
            "DICIEMBRE": 12,
        }

        match_dmy_abrev = re.search(
            r"\b(\d{1,2})[\s/\-\.]([A-Z]{3,4})[\s/\-\.](\d{4})\b",
            texto.upper(),
        )
        if match_dmy_abrev:
            dia_t, mes_t, anio_t = match_dmy_abrev.groups()
            mes_num = MESES.get(mes_t.upper())
            if mes_num:
                try:
                    return date(int(anio_t), mes_num, int(dia_t))
                except ValueError:
                    pass

        # ── Formato DDMMMYYYY sin separador (ej. 22OCT2006) ─────────────────
        match_unseparated = re.search(
            r"\b(\d{1,2})([A-Z]{3,4})(\d{4})\b",
            texto.upper(),
        )
        if match_unseparated:
            dia_t, mes_t, anio_t = match_unseparated.groups()
            mes_num = MESES.get(mes_t.upper())
            if mes_num:
                try:
                    return date(int(anio_t), mes_num, int(dia_t))
                except ValueError:
                    pass

        # ── Formato MMM DD YYYY (ej. NOV 07 1987, NOV-08-2005) ─────────────
        match_mdy_abrev = re.search(
            r"\b([A-Z]{3,4})[\s/\-\.](\d{1,2})[\s/\-\.](\d{4})\b",
            texto.upper(),
        )
        if match_mdy_abrev:
            mes_t, dia_t, anio_t = match_mdy_abrev.groups()
            mes_num = MESES.get(mes_t.upper())
            if mes_num:
                try:
                    return date(int(anio_t), mes_num, int(dia_t))
                except ValueError:
                    pass

        # ── Formato textual: "15 de enero de 2020" ───────────────────────
        match_texto = re.search(
            r"(\d{1,2})\s+DE\s+([A-Z0-9ÁÉÍÓÚ]+)\s+DE\s+(\d{4})",
            texto.upper(),
        )
        if match_texto:
            dia_t, mes_texto, anio_t = match_texto.groups()
            mes_num = MESES.get(mes_texto.upper())
            if mes_num:
                try:
                    return date(int(anio_t), mes_num, int(dia_t))
                except ValueError:
                    pass

        # ── Intentar parsear como datetime (último recurso) ───────────────
        for fmt in ["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y"]:
            try:
                return datetime.strptime(texto.strip(), fmt).date()
            except ValueError:
                continue

        logger.warning(f"No se pudo parsear fecha: '{texto}'")
        return None

    # ──────────────────────────────────────────
    # SEXO
    # ──────────────────────────────────────────
    @staticmethod
    def normalizar_sexo(texto: str) -> Optional[str]:
        """Normaliza el campo sexo a 'M' o 'F'."""
        if not texto:
            return None

        texto_up = texto.upper().strip()

        if texto_up in ("M", "MASCULINO", "HOMBRE", "MALE", "MASC"):
            return "M"
        if texto_up in ("F", "FEMENINO", "MUJER", "FEMALE", "FEM"):
            return "F"

        return None

    @classmethod
    def normalizar_lugar(cls, texto: str) -> Optional[str]:
        """
        Normaliza lugar de expedición:
          - Extrae el municipio exacto si viene en formato 'MUNICIPIO (DEPARTAMENTO)'
          - Elimina prefijos de etiquetas residuales (ej: 'MA DE NACIMIENTO CARTAGO' -> 'CARTAGO')
          - Elimina palabras genéricas (COLOMBIA, REPÚBLICA, REGISTRADOR, etc.)
          - Limpia ruido de OCR
          - Mínimo 3 caracteres alfabéticos
        """
        if not texto:
            return None

        txt = str(texto).strip()

        # 1. Si viene con paréntesis "MUNICIPIO (DEPTO)", tomar el municipio
        m_par = re.search(r"([A-ZÁÉÍÓÚÜÑa-záéíóúüñ\s]{3,30})\s*\(\s*([A-ZÁÉÍÓÚÜÑa-záéíóúüñ\s]{3,30})\s*\)", txt)
        if m_par:
            txt = m_par.group(1).strip()

        # 2. Eliminar palabras de encabezado, etiquetas y registradores
        txt = cls._PALABRAS_NO_LUGAR.sub(" ", txt)

        # 3. Solo letras y espacios
        txt = re.sub(r"[^A-ZÁÉÍÓÚÜÑa-záéíóúüñ\s]", " ", txt)
        txt = re.sub(r"\s+", " ", txt).strip().upper()

        # 4. Eliminar prefijos residuales cortos como "MA ", "DE ", "DEL ", "EN "
        txt = re.sub(r"^(?:MA\s+|DE\s+|DEL\s+|EN\s+|LA\s+|EL\s+|Y\s+)+", "", txt).strip()

        # Validar que tenga al menos una palabra de 3 o más letras reales
        palabras_reales = [w for w in txt.split() if len(w) >= 3]
        if not palabras_reales:
            return None

        texto_limpio = " ".join(txt.split())

        if len(texto_limpio) < 3 or texto_limpio in (
            "DE", "Y DE", "NACIONAL", "PERSONAL", "DE EXPIRACION", "DE EXPIRACIÓN", 
            "INDICE DERECHO", "INDICE IZQUIERDO", "ESTADO CIVIL", "MA DE"
        ):
            return None

        return texto_limpio


validador = ValidadorColombia()
