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
from typing import Optional, Tuple, List, Dict, Any
from app.utils.logger import app_logger as logger


class ValidadorColombia:
    """Validadores específicos para documentos de identificación colombianos."""

    # Diccionario de homóglifos (caracteres griegos/cirílicos visualmente idénticos a letras latinas)
    HOMOGLYPHS = str.maketrans({
        # Letras griegas a latinas
        'Α': 'A', 'Β': 'B', 'Ε': 'E', 'Ζ': 'Z', 'Η': 'H', 'Ι': 'I', 'Κ': 'K', 'Μ': 'M',
        'Ν': 'N', 'Ο': 'O', 'Ρ': 'P', 'Τ': 'T', 'Υ': 'Y', 'Χ': 'X',
        'α': 'a', 'β': 'b', 'ε': 'e', 'ι': 'i', 'κ': 'k', 'ν': 'n', 'ο': 'o', 'ρ': 'p', 'τ': 't', 'υ': 'y', 'χ': 'x',
        # Letras cirílicas a latinas
        'А': 'A', 'В': 'B', 'Е': 'E', 'К': 'K', 'М': 'M', 'Н': 'H', 'О': 'O', 'Р': 'P',
        'С': 'C', 'Т': 'T', 'Х': 'X',
        'а': 'a', 'е': 'e', 'о': 'o', 'р': 'p', 'с': 'c', 'у': 'y', 'х': 'x',
    })

    # Palabras que no son nombres de persona válidos (etiquetas/artefactos de cédula, marcas de agua, membretes)
    _PALABRAS_NO_NOMBRE = re.compile(
        r"\b(FIRMA|FIRMAS|TITULAR|HUELLA|DERECHO|IZQUIERDO|INDICE|ÍNDICE|REPUBLICA|REPÚBLICA|REPUBL|REPUBLI|PUBLICA|PÚBLICA|BLICA|"
        r"COLOMBIA|CEDULA|CÉDULA|CIUDADANIA|CIUDADANÍA|IDENTIFICACION|IDENTIFICACIÓN|NUIP|"
        r"NUMERO|NÚMERO|NOMBRES|APELLIDOS|NOMBRE|APELLIDO|LUGAR|EXPEDICION|EXPEDICIÓN|EXPIRACION|EXPIRACIÓN|"
        r"NACIMIENTO|FECHA|SEXO|ESTATURA|NACIONALIDAD|REGISTRADOR|REGISTRADORA|REGISTRADURIA|REGISTRAD|GERENTE|MINISTERIO|"
        r"CAMSCANNER|POWERED|SCANNER|CS|PANENZ|BAILS|DANCING|ARCHIV|DOC|DOCUMENTO|REGISTRO|CIVIL|"
        r"ALMABEATRIZ|SCANNED|WITH|PERSONAL|NACIONAL|NACIONA|DR|CDI|AAAS|AAS|"
        r"FOTOCOPIA|PROCESO|INSCRIPCION|INSCRIPCIÓN|MATRICULA|MATRÍCULA|EMPRENDEDORA|EMPRENDEDOR|EMPRENDIMIENTO|"
        r"OFICINA|DEPARTAMENTAL|MUNICIPAL|SECRETARIA|SECRETARÍA|ALCALDIA|ALCALDÍA|GOBERNACION|GOBERNACIÓN|"
        r"FACILITADO|FACILITADA|TECNOLOGICO|TECNOLÓGICO|ESTRATEGIA|CAMPESENA|CAMPESINA|CAMPESINO|FULLPOPULAR|POPULAR|"
        r"SENA|AMAZONIA|AMAZONÍA|CENTRO|MUJER|PROGRAMA|TITULADA|COMPLEMENTARIA|CURSO|FORMACION|FORMACIÓN|"
        r"CONVENIO|ASOCIACION|COOPERATIVA|LISTADO|PARTICIPANTES|APRENDICES|APRENDIZ|INSTRUCTOR|INSTRUCTORA|"
        r"FICHA|FOLIO|ANEXO|COPIA|AUTENTICADA|NOTARIA|"
        r"I+|[I|l1!]{2,}|II|III|IIII|IIIII|IV|VI|VII|VIII|IX|XI|XII)\b",
        re.IGNORECASE,
    )

    # Palabras que no son nombres de lugar válidos (aparecen en encabezados, labels, firmas y registradores)
    _PALABRAS_NO_LUGAR = re.compile(
        r"\b(REPUBLICA|REPÚBLICA|COLOMBIA|CIUDADANA|CIUDADANIA|CIUDADANÍA|IDENTIFICACION|IDENTIFICACIÓN|"
        r"TARJETA|CEDULA|CÉDULA|NUIP|PERSONAL|NACIONAL|FECHA|EXPEDICION|EXPEDICIÓN|EXPIRACION|EXPIRACIÓN|"
        r"LUGAR|Y|INDICE|ÍNDICE|DERECHO|IZQUIERDO|HUELLA|FIRMA|FIRMAS|REGISTRADOR|REGISTRADORA|REGISTRADURIA|"
        r"PANENZ|BAILS|DANCING|DEPARTAMENTO|MUNICIPIO|OFICINA|PROVINCIA|ESTADO|ESTADOL|CIVIL|GIVIL|ALDEL|DIRECTOR|SECRETARIO|"
        r"FOTOCOPIA|PROCESO|INSCRIPCION|INSCRIPCIÓN|MATRICULA|MATRÍCULA|EMPRENDEDORA|EMPRENDEDOR|SENA|CAMPESINA|FULLPOPULAR|"
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
        # Traducir homóglifos griegos/cirílicos generados por motores OCR
        txt = str(texto).translate(cls.HOMOGLYPHS).upper()
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
        """
        if not texto:
            return None

        # Corregir sustituciones OCR habituales (ej. SAB! -> SABI, homóglifos griegos)
        texto = cls.corregir_errores_ocr_nombre(texto)

        # Solo letras y espacios (incluyendo caracteres latinos)
        texto = re.sub(r"[^A-ZÁÉÍÓÚÜÑa-záéíóúüñ\s\-]", "", texto)
        # Normalizar espacios
        texto = " ".join(texto.split())
        texto = texto.upper()

        if not texto:
            return None

        # Filtrar palabras que son artefactos o etiquetas de la cédula (ej: FIRMA, TITULAR, DR, CDI)
        palabras_filtradas = []
        for p in texto.split():
            if cls._PALABRAS_NO_NOMBRE.match(p) or len(p) <= 1:
                continue
            # Si p es un fragmento de una palabra ya admitida, ignorar
            if any(p in ya for ya in palabras_filtradas):
                continue
            # Si una palabra ya admitida es un fragmento de p, reemplazarla por la palabra más completa (ej: NTONI -> ANTONIO)
            reemplazada = False
            for idx_ya, ya in enumerate(palabras_filtradas):
                if ya in p and len(p) > len(ya):
                    palabras_filtradas[idx_ya] = p
                    reemplazada = True
                    break
            if not reemplazada:
                palabras_filtradas.append(p)

        if not palabras_filtradas:
            return None

        # Limitar a máximo 5 palabras
        resultado = " ".join(palabras_filtradas[:5])

        # Mínimo 3 caracteres y no ser solo palabras genéricas de enlace
        if len(resultado) < 3 or resultado in ("DE", "DEL", "CA DE", "LA", "EL", "LOS", "LAS"):
            return None

        return resultado

    @classmethod
    def validar_nombre_estricto(cls, texto: Optional[str]) -> Tuple[bool, str]:
        """
        Validación estricta de nombres y apellidos en documentos colombianos:
          - No nulo ni 'POR REVISAR'
          - Mínimo 2 palabras (nombre + apellido)
          - Longitud total >= 5 caracteres
          - Sin palabras institucionales (COLOMBIA, REPUBLICA, REGISTRADURIA...)
          - Sin números, símbolos ni caracteres no alfabéticos
          - Sin secuencias de I (I, II, III, IIII...) ni números romanos
          - Sin caracteres repetidos anómalos (ej: XXXX, ZZZ)
          - Cada palabra debe tener al menos una vocal y >= 2 caracteres (salvo 'Y')
        """
        if not texto or not str(texto).strip() or str(texto).strip() == "POR REVISAR":
            return False, "Nombre ausente o no reconocido por el OCR"

        raw = str(texto).strip()

        # 1. Palabras institucionales de documentos
        if cls._PALABRAS_NO_NOMBRE.search(raw) or any(r in raw.upper() for r in ["COLOMBIA", "REPUBLICA", "REGISTRADURIA", "RETUBEICA", "IDENTIDAD", "TARJETA", "CEDULA", "CIUDADANIA"]):
            return False, f"El nombre contiene etiquetas de documento o palabras institucionales ('{raw}')"

        # 2. Números o símbolos no permitidos
        if re.search(r"[\d|!_#$*@~^<>=/\\\[\]{}¿?¡;:]", raw):
            return False, f"El nombre contiene dígitos o caracteres especiales no permitidos ('{raw}')"

        # 3. Caracteres repetidos de forma anómala (3 o más veces consecutivas)
        if re.search(r"(.)\1{2,}", raw):
            return False, f"El nombre contiene repeticiones anómalas de caracteres ('{raw}')"

        # 4. Secuencias de I o números romanos
        if re.search(r"\b(I+|[I|l1!]{2,}|II|III|IIII|IIIII|IV|VI|VII|VIII|IX|XI|XII|XIII)\b", raw.upper()):
            return False, f"El nombre contiene secuencias de I o números romanos no válidos ('{raw}')"

        # 5. Cantidad de palabras
        palabras = raw.split()
        if len(palabras) < 2:
            return False, f"Nombre incompleto: solo contiene {len(palabras)} palabra ('{raw}'), se requieren nombres y apellidos"

        # 6. Validación por cada palabra individual
        vocales = set("AEIOUÁÉÍÓÚÜY")
        for p in palabras:
            p_clean = re.sub(r"[^A-ZÁÉÍÓÚÜÑa-záéíóúüñ\-]", "", p)
            if len(p_clean) <= 1 and p_clean.upper() != "Y":
                return False, f"El nombre contiene iniciales o letras sueltas ('{p}')"
            if len(p_clean) >= 2 and not any(v in vocales for v in p_clean.upper()):
                return False, f"El nombre contiene una palabra sin vocales ('{p}')"

        if len(raw) < 5:
            return False, f"Nombre excesivamente corto ('{raw}')"

        return True, ""

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

        txt = re.sub(r"^(?:SEXO|G[EÉ]NERO|SEX)\s*:?\s*", "", str(texto).strip(), flags=re.IGNORECASE).strip().upper()

        if txt in ("M", "MASCULINO", "HOMBRE", "MALE", "MASC") or txt.startswith("MASC"):
            return "M"
        if txt in ("F", "FEMENINO", "MUJER", "FEMALE", "FEM") or txt.startswith("FEM"):
            return "F"

        m = re.search(r"\b(MASCULINO|FEMENINO|HOMBRE|MUJER)\b", str(texto).upper())
        if m:
            val = m.group(1)
            return "M" if val in ("MASCULINO", "HOMBRE") else "F"

        m_mf = re.search(r"\b([MF])\b", txt)
        if m_mf:
            return m_mf.group(1)

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

    # ──────────────────────────────────────────
    # EVALUACIÓN DE COMPLETITUD Y REVISIÓN
    # ──────────────────────────────────────────
    @classmethod
    def calcular_edad(cls, fecha_nacimiento: Any) -> Optional[int]:
        """Calcula la edad exacta en años cumplidos basado en la fecha de nacimiento."""
        if not fecha_nacimiento:
            return None
        try:
            from datetime import date, datetime
            fn = None
            if isinstance(fecha_nacimiento, datetime):
                fn = fecha_nacimiento.date()
            elif isinstance(fecha_nacimiento, date):
                fn = fecha_nacimiento
            elif isinstance(fecha_nacimiento, str):
                s = fecha_nacimiento.strip()
                if not s:
                    return None
                if "-" in s:
                    parts = s.split("-")
                    if len(parts) >= 3:
                        fn = date(int(parts[0]), int(parts[1]), int(parts[2]))
                elif "/" in s:
                    parts = s.split("/")
                    if len(parts) >= 3:
                        if len(parts[0]) == 4:
                            fn = date(int(parts[0]), int(parts[1]), int(parts[2]))
                        else:
                            fn = date(int(parts[2]), int(parts[1]), int(parts[0]))
            if fn:
                hoy = date.today()
                return hoy.year - fn.year - ((hoy.month, hoy.day) < (fn.month, fn.day))
        except Exception:
            pass
        return None

    # ──────────────────────────────────────────
    @classmethod
    def evaluar_persona_completa(
        cls,
        numero_identificacion: Optional[str] = None,
        nombres: Optional[str] = None,
        apellidos: Optional[str] = None,
        nombre_completo: Optional[str] = None,
        fecha_nacimiento: Optional[Any] = None,
        fecha_expedicion: Optional[Any] = None,
        lugar_expedicion: Optional[str] = None,
        sexo: Optional[str] = None,
        confianza: float = 100.0,
        detalles_campos: Optional[Dict[str, Any]] = None,
        motor_ocr: Optional[str] = None,
        tipo_documento: Optional[str] = None,
    ) -> Tuple[bool, List[str]]:
        """
        Evalúa de forma estricta si una persona tiene todos sus datos reconocidos
        satisfactoriamente por el OCR. Si falta cualquier dato o hay ruido/conflicto,
        retorna (False, [motivos]) para que sea revisado por un asistente.
        """
        motivos: List[str] = []

        # 1. Identificación
        id_limpio = cls.limpiar_identificacion(str(numero_identificacion or ""))
        if not id_limpio or id_limpio.startswith("SIN_ID"):
            motivos.append("Número de identificación no reconocido o ausente")
        else:
            valida, msg_ced = cls.validar_cedula(id_limpio)
            if not valida:
                motivos.append(f"Número de identificación dudoso ({id_limpio}): {msg_ced}")

        # 2. Nombre Completo Unificado (Criterio Estricto)
        nom_c_str = str(nombre_completo or "").strip()
        if not nom_c_str or nom_c_str == "POR REVISAR":
            partes = []
            if nombres and str(nombres).strip() != "POR REVISAR":
                partes.append(str(nombres).strip())
            if apellidos and str(apellidos).strip() != "POR REVISAR":
                partes.append(str(apellidos).strip())
            nom_c_str = " ".join(partes).strip()

        nom_c_norm = cls.normalizar_nombre(nom_c_str) if nom_c_str else None
        if not nom_c_norm or nom_c_norm == "POR REVISAR":
            motivos.append("Nombre completo no reconocido o ausente")
        else:
            valido_nom, mot_nom = cls.validar_nombre_estricto(nom_c_norm)
            if not valido_nom:
                motivos.append(mot_nom)

        # 3. Fecha de nacimiento y correspondencia legal con el tipo de documento
        if not fecha_nacimiento:
            motivos.append("Fecha de nacimiento no reconocida por OCR")
        else:
            tipo_doc_eval = tipo_documento
            if not tipo_doc_eval and detalles_campos and isinstance(detalles_campos, dict):
                td = detalles_campos.get("tipo_documento")
                if isinstance(td, dict):
                    tipo_doc_eval = td.get("valor") or td.get("value")
                elif isinstance(td, str):
                    tipo_doc_eval = td

            edad = cls.calcular_edad(fecha_nacimiento)
            tipo_norm = str(tipo_doc_eval or "").upper().strip()
            es_ti = tipo_norm in ("TARJETA_IDENTIDAD", "TI")
            es_cc = tipo_norm in ("CEDULA_CIUDADANIA", "CC")

            if edad is not None:
                if edad >= 18 and es_ti:
                    mot_doc_edad = (
                        f"Archivo no válido: La persona es mayor de edad ({edad} años) y presenta "
                        f"Tarjeta de Identidad, la cual solo corresponde a menores de edad. "
                        f"Debe presentar Cédula de Ciudadanía o Contraseña."
                    )
                    motivos.append(mot_doc_edad)
                    if detalles_campos is not None and isinstance(detalles_campos, dict):
                        detalles_campos["discrepancia_documento_edad"] = {
                            "tipo": "MAYOR_CON_TI",
                            "edad": edad,
                            "tipo_documento": tipo_doc_eval or "TARJETA_IDENTIDAD",
                            "motivo": (
                                f"Archivo no válido ya que la persona es mayor de edad ({edad} años) "
                                f"y presenta archivo de Tarjeta de Identidad que solo corresponde a menores de edad."
                            )
                        }
                elif edad < 18 and es_cc:
                    mot_doc_edad = (
                        f"Archivo no válido: La persona es menor de edad ({edad} años) y presenta "
                        f"Cédula de Ciudadanía, la cual solo corresponde a personas mayores de 18 años. "
                        f"Debe presentar Tarjeta de Identidad."
                    )
                    motivos.append(mot_doc_edad)
                    if detalles_campos is not None and isinstance(detalles_campos, dict):
                        detalles_campos["discrepancia_documento_edad"] = {
                            "tipo": "MENOR_CON_CC",
                            "edad": edad,
                            "tipo_documento": tipo_doc_eval or "CEDULA_CIUDADANIA",
                            "motivo": (
                                f"Archivo no válido ya que la persona es menor de edad ({edad} años) "
                                f"y presenta archivo de Cédula de Ciudadanía que solo corresponde a mayores de 18 años."
                            )
                        }
                else:
                    if detalles_campos is not None and isinstance(detalles_campos, dict):
                        detalles_campos.pop("discrepancia_documento_edad", None)

        # NOTA: Los campos secundarios (fecha_expedicion, lugar_expedicion, sexo)
        # ya no son requeridos ni obligatorios para marcar a una persona como válida.
        # Si están ausentes o ilegibles en el OCR, NO generan motivo de revisión.

        # 4. Confianza general
        try:
            conf_num = float(confianza or 0)
            if conf_num < 70.0:
                motivos.append(f"Confianza general OCR baja ({conf_num:.1f}%)")
        except (ValueError, TypeError):
            pass

        # 5. Conflictos o estatus de campos primarios esenciales
        # El único campo relevante de identidad es nombre_completo; nombres y apellidos se ignoran para no fragmentar ni duplicar alertas
        CAMPOS_IGNORAR_REVISION = {
            "grouping", "motivos_revision", "fecha_expedicion", "lugar_expedicion", "sexo",
            "tipo_documento", "discrepancia_excel", "discrepancia_documento_edad", "nombres", "apellidos"
        }
        if detalles_campos and isinstance(detalles_campos, dict):
            # Discrepancia crítica explícita entre Cédula física y Planilla Excel
            mot_disc = ""
            if "discrepancia_excel" in detalles_campos:
                disc = detalles_campos["discrepancia_excel"]
                if isinstance(disc, dict):
                    nom_c = disc.get("nombre_cedula", "")
                    nom_e = disc.get("nombre_excel", "")
                    mot_disc = disc.get("motivo") or f"Discrepancia en Nombre Completo: La Cédula física en PDF indica '{nom_c}' pero la Planilla Excel indica '{nom_e}'"
                else:
                    mot_disc = str(disc)
                if mot_disc not in motivos:
                    motivos.append(mot_disc)

            for campo, info in detalles_campos.items():
                if campo in CAMPOS_IGNORAR_REVISION:
                    continue
                if isinstance(info, dict):
                    st = info.get("status")
                    if st in ("MISSING", "MISSING_DATA"):
                        mot = f"Campo '{campo}' marcado como faltante en el documento"
                        if mot not in motivos:
                            motivos.append(mot)
                    elif st in ("REVIEW_REQUIRED", "CONFLICT", "INVALID"):
                        reason = info.get("reason") or "requiere revisión manual"
                        # Si ya se agregó la discrepancia_excel, no repetir el mismo motivo en nombre_completo
                        if mot_disc and campo == "nombre_completo" and (reason in mot_disc or mot_disc in reason):
                            continue
                        mot = f"Conflicto en campo '{campo}': {reason}"
                        if mot not in motivos:
                            motivos.append(mot)

        # 6. Fallback de OCR secundario
        if motor_ocr == "tesseract_fallback":
            motivos.append("Procesado con motor fallback secundario (Tesseract)")

        es_completo = (len(motivos) == 0)
        return es_completo, motivos


validador = ValidadorColombia()
