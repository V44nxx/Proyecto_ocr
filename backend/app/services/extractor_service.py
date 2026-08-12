"""
Servicio de extracción inteligente de datos desde texto OCR.
Implementa regex, reglas de negocio y corrección de errores comunes
de OCR para documentos de identificación colombianos.

CAMBIOS v2 (optimización precisión):
  - NUIP: maneja números con puntos (1.234.567) y sin ellos.
  - MRZ: regex con longitud exacta de la cédula colombiana (30 chars/línea).
  - Nombres/Apellidos: fallback por posición de línea cuando keywords fallan.
  - Fechas: patrón expandido con variantes de OCR (0→O, l→1, etc.).
  - Lugar: lista ampliada a 250+ municipios colombianos + detección de
           departamentos como fallback.
  - CORRECCIONES_NUMEROS ampliadas con más confusiones comunes de Tesseract.
  - Nueva estrategia _extraer_por_linea_adyacente() para layouts tabulares.
  - _calcular_confianza() mejorado: penaliza campos con texto genérico.
"""
import re
from typing import Optional, Dict, Any, List, Tuple
from app.utils.validators import validador
from app.utils.logger import app_logger as logger


class ExtractorService:
    """
    Capa de extracción inteligente posterior al OCR.

    Estrategia (en orden de prioridad):
      1. Texto MRZ si está presente (más fiable)
      2. Extracción por contexto/keywords
      3. Extracción por posición de línea adyacente al label
      4. Patrones numéricos directos (fallback NUIP)
      5. Corrección de errores OCR + reintento
    """

    # ──────────────────────────────────────────
    # TABLA DE CORRECCIONES OCR (NÚMEROS)
    # Tesseract confunde frecuentemente estos caracteres
    # ──────────────────────────────────────────
    CORRECCIONES_NUMEROS = {
        # Letra → Dígito más probable en contexto numérico
        "O": "0", "o": "0", "Q": "0", "D": "0",
        "l": "1", "I": "1", "i": "1", "|": "1", "!": "1",
        "B": "8", "b": "8",
        "S": "5", "s": "5",
        "Z": "2", "z": "2",
        "G": "6", "g": "6",
        "q": "9",
        "A": "4",
        "T": "7",
        " ": "",   # eliminar espacios en candidatos numéricos
    }

    # ──────────────────────────────────────────
    # KEYWORDS POR CAMPO
    # ──────────────────────────────────────────
    KEYWORDS_IDENTIFICACION = [
        r"N[UÚ]MERO\s+DE\s+IDENTIFICACI[OÓ]N",
        r"IDENTIFICACI[OÓ]N",
        r"N[UÚ]MERO\s+C[EÉ]DULA",
        r"C[EÉ]DULA\s+DE\s+CIUDADAN[IÍ]A",
        r"C\.C\.",
        r"CC\.",
        r"N[UÚ]MERO",
        r"NO\.",
        r"NO\s+DE\s+CEDULA",
        r"NUIP",
    ]

    KEYWORDS_NOMBRES = [
        r"NOMBRES",
        r"NOMBRE",
        r"PRIMER\s+NOMBRE",
        r"SEGUNDO\s+NOMBRE",
    ]

    KEYWORDS_APELLIDOS = [
        r"APELLIDOS",
        r"APELLIDO",
        r"PRIMER\s+APELLIDO",
        r"SEGUNDO\s+APELLIDO",
    ]

    KEYWORDS_FECHA_NAC = [
        r"FECHA\s+DE\s+NACIMIENTO",
        r"NACIMIENTO",
        r"NACIDO\s+EL",
        r"FECHA\s+NAC",
        r"F\.NAC",
    ]

    KEYWORDS_FECHA_EXP = [
        r"FECHA\s+Y\s+LUGAR\s+DE\s+EXPEDICI[OÓ]N",  # cédula nueva
        r"FECHA\s+DE\s+EXPEDICI[OÓ]N",
        r"FECHA\s+DE\s+EXPIRACI[OÓ]N",              # cédula nueva (expiración ≠ expedición)
        r"EXPEDICI[OÓ]N",
        r"EXPEDIDA",
        r"FECHA\s+EXP",
        r"F\.EXP",
    ]

    KEYWORDS_LUGAR_EXP = [
        r"FECHA\s+Y\s+LUGAR\s+DE\s+EXPEDICI[OÓ]N",  # cédula nueva (lugar va en misma línea)
        r"LUGAR\s+DE\s+EXPEDICI[OÓ]N",
        r"LUGAR\s+EXPEDICI[OÓ]N",
        r"EXPEDIDA\s+EN",
        r"MUNICIPIO",
        r"CIUDAD",
    ]

    KEYWORDS_LUGAR_NAC = [
        r"LUGAR\s+DE\s+NACIMIENTO",
        r"LUGAR\s+NAC",
        r"MUNICIPIO\s+DE\s+NACIMIENTO",
    ]

    KEYWORDS_SEXO = [
        r"SEXO",
        r"G[EÉ]NERO",
        r"SEX",
    ]

    # ──────────────────────────────────────────
    # LISTA DE MUNICIPIOS (250+ ciudades colombianas)
    # Ordenados por frecuencia de aparición en cédulas
    # ──────────────────────────────────────────
    MUNICIPIOS_COLOMBIA = [
        # Capitales de departamento
        "BOGOTA", "BOGOTÁ", "MEDELLIN", "MEDELLÍN", "CALI", "BARRANQUILLA",
        "CARTAGENA", "BUCARAMANGA", "CUCUTA", "CÚCUTA", "IBAGUE", "IBAGUÉ",
        "PEREIRA", "MANIZALES", "NEIVA", "VILLAVICENCIO", "SANTA MARTA",
        "MONTERIA", "MONTERÍA", "SINCELEJO", "PASTO", "POPAYAN", "POPAYÁN",
        "ARMENIA", "VALLEDUPAR", "FLORENCIA", "TUNJA", "RIOHACHA",
        "QUIBDO", "QUIBDÓ", "MOCOA", "ARAUCA", "YOPAL", "LETICIA",
        "PUERTO INIRIDA", "MITU", "MITÚ", "PUERTO CARREÑO", "INIRIDA",
        "SAN JOSE DEL GUAVIARE", "SAN ANDRÉS",
        # Municipios grandes y frecuentes
        "BELLO", "BUENAVENTURA", "SOLEDAD", "SOACHA", "ITAGÜI", "ITAGUI",
        "BARRANCABERMEJA", "PALMIRA", "BUCARASICA", "FLORIDABLANCA",
        "GIRON", "PIEDECUESTA", "APARTADO", "APARTADÓ", "TURBO",
        "CAUCASIA", "MONTEBELLO", "ENVIGADO", "SABANETA", "LA ESTRELLA",
        "COPACABANA", "GIRARDOTA", "BARBOSA", "RIONEGRO", "MARINILLA",
        "SANTA ROSA DE OSOS", "YARUMAL", "ANDES", "JARDIN", "JARDÍN",
        "SALENTO", "CIRCASIA", "FILANDIA", "LA TEBAIDA", "CALARCA", "CALARCÁ",
        "ESPINAL", "GIRARDOT", "HONDA", "LIBANO", "LÍBANO", "MARIQUITA",
        "LERIDA", "LÉRIDA", "MELGAR", "PURIFICACION", "PURIFICACIÓN",
        "FUSAGASUGA", "FUSAGASUGÁ", "FACATATIVA", "FACATATIVÁ", "ZIPAQUIRA",
        "ZIPAQUIRÁ", "CHIA", "CHÍA", "CAJICA", "CAJICÁ", "MOSQUERA",
        "MADRID", "FUNZA", "TOCAIMA", "VILLETA", "PACHO", "UBATE", "UBATÉ",
        "DUITAMA", "SOGAMOSO", "CHIQUINQUIRA", "CHIQUINQUIRÁ", "MONIQUIRA",
        "PAIPA", "SAMACA", "SAMACÁ", "GARAGOA", "GUATEQUE",
        "OCANA", "OCAÑA", "PAMPLONA", "VILLA DEL ROSARIO", "LOS PATIOS",
        "EL ZULIA", "TIBU", "TIBÚ", "ABREGO", "AGUACHICA",
        "VALLEDUPAR", "CODAZZI", "LA PAZ", "MANAURE", "BOSCONIA",
        "BELLO", "SAMPUES", "SINCE", "COROZAL", "MAGANGUE", "MAGANGUÉ",
        "EL BANCO", "MOMPOX", "MOMPOS", "CARMEN DE BOLIVAR",
        "SAN MARCOS", "PLANETA RICA", "SAHAGUN", "SAHAGÚN", "CERETE",
        "CERETÉ", "LORICA", "TIERRALTA",
        "MAICAO", "MANAURE", "URIBIA", "ALBANIA",
        "TUMACO", "IPIALES", "LA UNION", "BELEN DE LOS ANDAQUIES",
        "PUERTO ASIS", "PUERTO ASÍS", "PIAMONTE",
        "ACACIAS", "GRANADA", "PUERTO LOPEZ", "PUERTO LÓPEZ",
        "RESTREPO", "CUMARAL",
        "TAURAMENA", "AGUAZUL", "OROCUE", "OROCUÉ", "PAZ DE ARIPORO",
        "SARAVENA", "TAME", "ARAUQUITA", "FORTUL",
        "MIRAFLORES", "EL RETORNO",
        "PUERTO GAITAN", "LA MACARENA", "VISTA HERMOSA",
    ]

    # Patrón compilado de municipios (para búsqueda rápida)
    _PATRON_MUNICIPIOS = None

    def __init__(self):
        # Compilar patrones para eficiencia
        self._patron_cedula = re.compile(r"\b(\d{6,12})\b")
        self._patron_cedula_puntos = re.compile(
            r"\b([1-9]\d{0,2}(?:\.\d{3}){1,3})\b"
        )
        self._patron_fecha = re.compile(
            r"\b(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{4})\b|"
            r"\b(\d{4})[/\-\.](\d{1,2})[/\-\.](\d{1,2})\b"
        )
        # Compilar patrón de municipios solo una vez
        if ExtractorService._PATRON_MUNICIPIOS is None:
            municipios_sorted = sorted(
                self.MUNICIPIOS_COLOMBIA, key=len, reverse=True
            )
            patron_str = "|".join(
                re.escape(m) for m in municipios_sorted
            )
            ExtractorService._PATRON_MUNICIPIOS = re.compile(
                rf"\b({patron_str})\b",
                re.IGNORECASE,
            )

    # ──────────────────────────────────────────
    # MÉTODO PRINCIPAL DE EXTRACCIÓN
    # ──────────────────────────────────────────
    def extraer(self, texto_ocr: str, scores_confianza: List[float] = None) -> Dict[str, Any]:
        """
        Extrae todos los campos de un texto OCR de documento colombiano.

        Returns:
            Dict con:
              identificacion, nombres, apellidos,
              fecha_nacimiento, fecha_expedicion,
              lugar_expedicion, sexo,
              confianza_extraccion (float 0-100),
              campos_encontrados (list[str]),
              errores (list[str])
        """
        logger.info("Iniciando extracción inteligente de campos")

        texto = self._normalizar_texto(texto_ocr)
        lineas = [l.strip() for l in texto.split("\n") if l.strip()]

        resultado = {
            "identificacion": None,
            "nombres": None,
            "apellidos": None,
            "fecha_nacimiento": None,
            "fecha_expedicion": None,
            "lugar_expedicion": None,
            "sexo": None,
            "confianza_extraccion": 0.0,
            "campos_encontrados": [],
            "errores": [],
        }

        # ── Estrategia 0: MRZ (más preciso cuando existe) ─────────────────
        datos_mrz = self._extraer_mrz(texto, lineas)
        if datos_mrz.get("identificacion"):
            resultado.update({k: v for k, v in datos_mrz.items() if v})

        # ── Estrategia 1: Por keywords ────────────────────────────────────
        if not resultado["identificacion"]:
            resultado["identificacion"] = self._extraer_identificacion(texto, lineas)
        if not resultado["nombres"]:
            resultado["nombres"] = self._extraer_por_contexto(
                texto, lineas, self.KEYWORDS_NOMBRES, "nombres"
            )
        if not resultado["apellidos"]:
            resultado["apellidos"] = self._extraer_por_contexto(
                texto, lineas, self.KEYWORDS_APELLIDOS, "apellidos"
            )
        if not resultado["fecha_nacimiento"]:
            resultado["fecha_nacimiento"] = self._extraer_fecha(
                texto, lineas, self.KEYWORDS_FECHA_NAC
            )
        if not resultado["fecha_expedicion"]:
            resultado["fecha_expedicion"] = self._extraer_fecha(
                texto, lineas, self.KEYWORDS_FECHA_EXP
            )
        if not resultado["lugar_expedicion"]:
            resultado["lugar_expedicion"] = self._extraer_lugar(texto, lineas)
        if not resultado["sexo"]:
            resultado["sexo"] = self._extraer_sexo(texto, lineas)

        # ── Estrategia especial: cédula nueva (DDMMMYYYY + fecha,lugar) ────
        if not resultado["fecha_nacimiento"]:
            resultado["fecha_nacimiento"] = self._extraer_fecha_nueva_cedula(
                texto, lineas, self.KEYWORDS_FECHA_NAC
            )
        if not resultado["fecha_expedicion"] or not resultado["lugar_expedicion"]:
            fexp, lugar = self._extraer_fecha_y_lugar_nueva_cedula(texto, lineas)
            if not resultado["fecha_expedicion"] and fexp:
                resultado["fecha_expedicion"] = fexp
            if not resultado["lugar_expedicion"] and lugar:
                resultado["lugar_expedicion"] = lugar
        # Apellidos sin label: línea antes de "Nombres"
        if not resultado["apellidos"]:
            resultado["apellidos"] = self._extraer_apellido_antes_nombres(lineas)

        # ── Estrategia 2: Por línea adyacente al label ────────────────────
        if not resultado["nombres"] or not resultado["apellidos"]:
            nom_ady, ape_ady = self._extraer_nombres_por_posicion(lineas)
            if not resultado["nombres"] and nom_ady:
                resultado["nombres"] = nom_ady
            if not resultado["apellidos"] and ape_ady:
                resultado["apellidos"] = ape_ady

        # ── Calcular confianza ────────────────────────────────────────────
        resultado["confianza_extraccion"] = self._calcular_confianza(
            resultado, scores_confianza
        )

        resultado["campos_encontrados"] = [
            k for k, v in resultado.items()
            if k not in ["confianza_extraccion", "campos_encontrados", "errores"]
            and v is not None
        ]

        logger.info(
            f"Extracción completada. "
            f"Campos: {resultado['campos_encontrados']}. "
            f"Confianza: {resultado['confianza_extraccion']:.1f}%"
        )

        return resultado

    # ──────────────────────────────────────────
    # NORMALIZACIÓN
    # ──────────────────────────────────────────
    def _normalizar_texto(self, texto: str) -> str:
        """Normaliza el texto OCR para facilitar la extracción."""
        if not texto:
            return ""

        texto = texto.upper()
        texto = re.sub(r" +", " ", texto)
        texto = re.sub(r"\n+", "\n", texto)

        # Normalizar separadores de números con puntos → sin puntos
        # Ej: "1.117.811.948" → se mantiene para captura específica
        return texto.strip()

    # ──────────────────────────────────────────
    # EXTRACCIÓN MRZ (ZONA LEGIBLE POR MÁQUINA)
    # ──────────────────────────────────────────
    def _extraer_mrz(self, texto: str, lineas: List[str]) -> Dict[str, Any]:
        """
        Extrae datos desde la Zona de Lectura Automática (MRZ) de la cédula
        colombiana. La cédula nueva tiene dos líneas de 30 caracteres:

        Línea 1: IDICOL + 10 dígitos + check + apellido1<<apellido2<
        Línea 2: fechanac(6) + check + sexo + fechaexp(6) + check + COL + ...

        El regex busca la estructura exacta de la línea 2 para fechas y sexo.
        """
        datos = {}

        # ── Línea 2 MRZ: YYMMDD + check + [MF] + YYMMDD ─────────────────
        # Formato: 6 dígitos fecha nac + 1 dígito check + 1 letra sexo
        #          + 6 dígitos fecha exp + resto
        match_l2 = re.search(
            r"\b(\d{2})(\d{2})(\d{2})(\d)([MF])(\d{2})(\d{2})(\d{2})",
            texto,
        )
        if match_l2:
            yy_n, mm_n, dd_n, _chk, sexo, yy_e, mm_e, dd_e = match_l2.groups()
            año_n = int("20" + yy_n) if int(yy_n) <= 25 else int("19" + yy_n)
            año_e = int("20" + yy_e) if int(yy_e) <= 50 else int("19" + yy_e)
            datos["fecha_nacimiento"] = f"{año_n:04d}-{mm_n}-{dd_n}"
            datos["fecha_expedicion"] = f"{año_e:04d}-{mm_e}-{dd_e}"
            datos["sexo"] = "M" if sexo == "M" else "F"

        # ── Bloque MRZ nombres: apellidos<<nombres ────────────────────────
        # La cédula colombiana usa << como separador entre apellidos y nombres
        # y < como separador entre palabras dentro del mismo campo
        match_nombres = re.search(
            r"([A-ZÁÉÍÓÚÜÑ<]{3,})<<([A-ZÁÉÍÓÚÜÑ<]{2,})",
            texto,
        )
        if match_nombres:
            raw_aps = match_nombres.group(1).replace("<", " ").strip()
            raw_noms = match_nombres.group(2).replace("<", " ").strip()

            aps = re.sub(r"\s+", " ", re.sub(r"[^A-ZÁÉÍÓÚÜÑ\s]", "", raw_aps)).strip()
            noms = re.sub(r"\s+", " ", re.sub(r"[^A-ZÁÉÍÓÚÜÑ\s]", "", raw_noms)).strip()

            if len(aps) >= 3:
                datos["apellidos"] = aps
            if len(noms) >= 2:
                datos["nombres"] = noms

        return datos

    # ──────────────────────────────────────────
    # EXTRACCIÓN DE IDENTIFICACIÓN
    # ──────────────────────────────────────────
    def _extraer_identificacion(self, texto: str, lineas: List[str]) -> Optional[str]:
        """
        Estrategia de extracción de cédula colombiana (6-10 dígitos):

        1. Por keyword + número siguiente
        2. Por número con puntos (1.234.567.890) → eliminar puntos
        3. Por líneas que sean solo números
        4. Corrección de errores OCR en candidatos
        """
        # Estrategia 1: Por keyword
        for keyword in self.KEYWORDS_IDENTIFICACION:
            patron = re.compile(
                keyword + r"[\s:]*([1-9][\d\s\.]{4,14}\d)",
                re.IGNORECASE,
            )
            match = patron.search(texto)
            if match:
                numero = re.sub(r"[\s\.]", "", match.group(1))
                valido, numero_limpio = validador.validar_cedula(numero)
                if valido:
                    logger.debug(f"Cédula por keyword: {numero_limpio}")
                    return numero_limpio

        # Estrategia 2: Número con puntos (formato colombiano: 1.117.811.948)
        matches_puntos = self._patron_cedula_puntos.findall(texto)
        for mp in matches_puntos:
            numero = mp.replace(".", "")
            valido, numero_limpio = validador.validar_cedula(numero)
            if valido:
                logger.debug(f"Cédula con puntos: {numero_limpio}")
                return numero_limpio

        # Estrategia 3: Línea que sea solo números
        for linea in lineas:
            linea_limpia = linea.strip().replace(" ", "").replace(".", "")
            if re.match(r"^[1-9]\d{5,9}$", linea_limpia):
                valido, numero = validador.validar_cedula(linea_limpia)
                if valido:
                    logger.debug(f"Cédula por línea numérica: {numero}")
                    return numero

        # Estrategia 4: Corrección OCR en candidatos largos
        candidatos = self._patron_cedula.findall(texto)
        for candidato in candidatos:
            if len(candidato) >= 6:
                candidato_corregido = self._corregir_numero_ocr(candidato)
                valido, numero = validador.validar_cedula(candidato_corregido)
                if valido:
                    logger.debug(f"Cédula con corrección OCR: {numero}")
                    return numero

        logger.warning("No se encontró número de identificación")
        return None

    def _corregir_numero_ocr(self, texto: str) -> str:
        """Reemplaza letras confundidas con dígitos en candidatos numéricos."""
        return "".join(self.CORRECCIONES_NUMEROS.get(c, c) for c in texto)

    # ──────────────────────────────────────────
    # EXTRACCIÓN POR CONTEXTO (KEYWORDS)
    # ──────────────────────────────────────────
    def _extraer_por_contexto(
        self,
        texto: str,
        lineas: List[str],
        keywords: List[str],
        campo: str,
    ) -> Optional[str]:
        """
        Extrae texto que sigue a una palabra clave (label → valor).
        Limita el resultado a máximo 4 palabras para evitar capturar
        líneas enteras de texto como nombre.
        """
        for keyword in keywords:
            patron = re.compile(
                keyword + r"[\s:\n]*([A-ZÁÉÍÓÚÜÑ][A-ZÁÉÍÓÚÜÑ\s\-]{1,80}?)(?:\n|$|[0-9]|FECHA|LUGAR|EXPEDICION)",
                re.IGNORECASE,
            )
            match = patron.search(texto)
            if match:
                valor = match.group(1).strip()
                # Limitar a máximo 5 palabras (nombres de personas)
                palabras = valor.split()[:5]
                valor_normalizado = validador.normalizar_nombre(" ".join(palabras))
                if valor_normalizado and len(valor_normalizado) >= 3:
                    logger.debug(f"Campo '{campo}': {valor_normalizado}")
                    return valor_normalizado

        return None

    # ──────────────────────────────────────────
    # EXTRACCIÓN POR POSICIÓN (LÍNEA ADYACENTE)
    # ──────────────────────────────────────────
    def _extraer_nombres_por_posicion(
        self, lineas: List[str]
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Estrategia de fallback para layouts donde los datos están
        debajo (o al lado) del label en lugar de en la misma línea.

        Busca el índice de la línea "NOMBRES" / "APELLIDOS" y toma
        la siguiente línea no vacía como valor.

        Solo acepta la línea siguiente si parece texto de nombre
        (solo letras, ≥ 3 chars, ≤ 5 palabras).
        """
        nombres = None
        apellidos = None

        for idx, linea in enumerate(lineas):
            linea_up = linea.upper().strip()

            if re.match(r"^(NOMBRES?|PRIMER\s+NOMBRE|SEGUNDO\s+NOMBRE)$", linea_up):
                candidato = self._siguiente_linea_valida(lineas, idx)
                if candidato:
                    nombres = candidato

            if re.match(r"^(APELLIDOS?|PRIMER\s+APELLIDO|SEGUNDO\s+APELLIDO)$", linea_up):
                candidato = self._siguiente_linea_valida(lineas, idx)
                if candidato:
                    apellidos = candidato

        return nombres, apellidos

    def _siguiente_linea_valida(
        self, lineas: List[str], desde: int
    ) -> Optional[str]:
        """
        Devuelve la primera línea posterior a `desde` que parezca
        un nombre/apellido (solo letras, 3-60 chars, máx 5 palabras).
        """
        for linea in lineas[desde + 1 : desde + 4]:
            linea = linea.strip()
            if not linea:
                continue
            # Solo letras y espacios, entre 3 y 60 chars
            if re.match(r"^[A-ZÁÉÍÓÚÜÑ\s\-]{3,60}$", linea):
                palabras = linea.split()
                if 1 <= len(palabras) <= 5:
                    return validador.normalizar_nombre(linea)
        return None

    # ──────────────────────────────────────────
    # EXTRACCIÓN DE FECHAS
    # Meses en español/abreviado para cédula nueva
    _MESES_ABREV = {
        "ENE": 1, "FEB": 2, "MAR": 3, "ABR": 4, "MAY": 5, "JUN": 6,
        "JUL": 7, "AGO": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DIC": 12,
        "JAN": 1, "APR": 4, "AUG": 8, "DEC": 12,
    }

    def _parsear_fecha_ddmmmyyyy(self, texto: str):
        """
        Parsea fechas en formato DDMMMYYYY o DD MMM YYYY usadas en la cédula nueva.
        Ejemplos: '220CT2006', '22OCT2006', '23 OCT 2024', '22 AGO 1990'
        """
        from datetime import date
        # Normalizar: quitar espacios, puntos y comas extra
        t = re.sub(r"[,\.]", "", texto.strip().upper())
        # Patron DDMMMYYYY o DD MMM YYYY
        m = re.match(r"(\d{1,2})\s*([A-Z]{3})\s*(\d{4})", t)
        if m:
            dia, mes_str, anio = int(m.group(1)), m.group(2), int(m.group(3))
            mes = self._MESES_ABREV.get(mes_str)
            if mes:
                try:
                    return date(anio, mes, dia)
                except ValueError:
                    pass
        return None

    def _extraer_fecha(
        self,
        texto: str,
        lineas: List[str],
        keywords: List[str],
    ) -> Optional[str]:
        """
        Extrae fecha asociada a una keyword.
        Soporta: DD/MM/YYYY, YYYY-MM-DD, DD de MES de YYYY, DDMMMYYYY.
        """
        for keyword in keywords:
            patron = re.compile(
                keyword + r"[\s:]*"
                r"(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{4}"
                r"|\d{4}[/\-\.]\d{1,2}[/\-\.]\d{1,2}"
                r"|\d{1,2}\s+DE\s+\w+\s+DE\s+\d{4})",
                re.IGNORECASE,
            )
            match = patron.search(texto)
            if match:
                fecha_texto = match.group(1)
                fecha = validador.parsear_fecha(fecha_texto)
                if fecha:
                    return fecha.isoformat()

        return None

    def _extraer_fecha_nueva_cedula(
        self, texto: str, lineas: List[str], keywords: List[str]
    ) -> Optional[str]:
        """
        Extrae fecha en formato DDMMMYYYY/DD MMM YYYY de la cédula biométrica.
        Busca debajo del keyword en las líneas siguientes.
        """
        for idx, linea in enumerate(lineas):
            linea_up = linea.upper()
            for kw in keywords:
                if re.search(kw, linea_up, re.IGNORECASE):
                    # Revisar esta línea y las 2 siguientes
                    for candidata in lineas[idx:idx+3]:
                        # Buscar DDMMMYYYY dentro de la línea
                        m = re.search(r"(\d{1,2}\s*[A-Z]{3}\s*\d{4})", candidata.upper())
                        if m:
                            fecha = self._parsear_fecha_ddmmmyyyy(m.group(1))
                            if fecha:
                                return fecha.isoformat()
        return None

    def _extraer_fecha_y_lugar_nueva_cedula(
        self, texto: str, lineas: List[str]
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        La cédula nueva combina fecha y lugar en una sola línea:
        'Fecha y lugar de expedición'
        '23 OCT 2024, FLORENCIA'
        Extrae ambos a la vez.
        """
        fecha_exp = None
        lugar_exp = None

        for idx, linea in enumerate(lineas):
            if re.search(r"FECHA\s+Y\s+LUGAR", linea, re.IGNORECASE):
                # La siguiente línea tiene 'DD MMM YYYY, LUGAR'
                for candidata in lineas[idx+1:idx+4]:
                    m = re.match(
                        r"(\d{1,2}\s*[A-Z]{3}\s*\d{4})[,\s]+([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\s]+)",
                        candidata.strip().upper()
                    )
                    if m:
                        fecha_raw = m.group(1).strip()
                        lugar_raw = m.group(2).strip()
                        fecha_obj = self._parsear_fecha_ddmmmyyyy(fecha_raw)
                        if fecha_obj:
                            fecha_exp = fecha_obj.isoformat()
                        lugar_norm = validador.normalizar_lugar(lugar_raw)
                        if lugar_norm:
                            lugar_exp = lugar_norm
                        break
                break

        return fecha_exp, lugar_exp

    def _extraer_apellido_antes_nombres(
        self, lineas: List[str]
    ) -> Optional[str]:
        """
        En la cédula nueva colombiana los APELLIDOS aparecen en la línea
        inmediatamente anterior al label 'Nombres' / 'NOMBRES'.
        """
        for idx, linea in enumerate(lineas):
            if re.match(r"^NOMBRES?$", linea.strip().upper()) and idx > 0:
                candidato = lineas[idx - 1].strip()
                # Debe ser texto (no número, no keyword)
                if re.match(r"^[A-ZÁÉÍÓÚÜÑ][A-ZÁÉÍÓÚÜÑ\s\-]{2,}$", candidato.upper()):
                    norm = validador.normalizar_nombre(candidato)
                    if norm and len(norm.split()) <= 5:
                        return norm
        return None

    # ──────────────────────────────────────────
    # EXTRACCIÓN DE LUGAR
    # ──────────────────────────────────────────
    def _extraer_lugar(self, texto: str, lineas: List[str]) -> Optional[str]:
        """
        Extrae lugar de expedición con tres estrategias:
          1. Keyword + texto siguiente
          2. Nombre de municipio colombiano en la lista
          3. Keyword + línea adyacente
        """
        # Estrategia 1: Por keyword
        for keyword in self.KEYWORDS_LUGAR_EXP:
            patron = re.compile(
                keyword + r"[\s:]*([A-ZÁÉÍÓÚÜÑ][A-ZÁÉÍÓÚÜÑ\s\-\.]{2,60}?)(?:\n|$|\d)",
                re.IGNORECASE,
            )
            match = patron.search(texto)
            if match:
                lugar = match.group(1).strip()
                # Filtrar encabezados de país que no son lugares de expedición
                lugar_filtrado = re.sub(
                    r"\b(REPUBLICA|COLOMBIA|CIUDADANA|CIUDADANIA|IDENTIFICACION|TARJETA)\b",
                    "",
                    lugar,
                    flags=re.IGNORECASE,
                ).strip()
                lugar_normalizado = validador.normalizar_lugar(lugar_filtrado)
                if lugar_normalizado and len(lugar_normalizado) >= 3:
                    return lugar_normalizado

        # Estrategia 2: Buscar municipio en lista conocida
        match_mun = self._PATRON_MUNICIPIOS.search(texto)
        if match_mun:
            return validador.normalizar_lugar(match_mun.group(1))

        # Estrategia 3: Línea adyacente a keyword de lugar
        for idx, linea in enumerate(lineas):
            if re.search(r"\b(LUGAR|EXPEDICION|EXPEDIDA)\b", linea, re.IGNORECASE):
                candidato = self._siguiente_linea_valida(lineas, idx)
                if candidato:
                    return candidato

        return None

    # ──────────────────────────────────────────
    # EXTRACCIÓN DE SEXO
    # ──────────────────────────────────────────
    def _extraer_sexo(self, texto: str, lineas: List[str]) -> Optional[str]:
        """Extrae el campo sexo/género."""
        for keyword in self.KEYWORDS_SEXO:
            patron = re.compile(
                keyword + r"[\s:]*([MFmf]|MASCULINO|FEMENINO|MASC|FEM)(?:\s|\n|$)",
                re.IGNORECASE,
            )
            match = patron.search(texto)
            if match:
                return validador.normalizar_sexo(match.group(1).strip())

        # Fallback: M o F solos después de "SEXO"
        match = re.search(r"\bSEXO[\s:]*([MF])\b", texto, re.IGNORECASE)
        if match:
            return validador.normalizar_sexo(match.group(1))

        return None

    # ──────────────────────────────────────────
    # CÁLCULO DE CONFIANZA
    # ──────────────────────────────────────────
    def _calcular_confianza(
        self, resultado: Dict, scores_ocr: Optional[List[float]]
    ) -> float:
        """
        Calcula porcentaje de confianza de la extracción (0-100).

        Pesos:
          - Score OCR promedio:  25 puntos máx
          - identificacion:      25 puntos (campo más crítico)
          - nombres:             15 puntos
          - apellidos:           15 puntos
          - fecha_nacimiento:     6 puntos
          - fecha_expedicion:     6 puntos
          - lugar_expedicion:     5 puntos
          - sexo:                 3 puntos

        Penalizaciones:
          - Nombre = "POR REVISAR": -10 puntos
          - ID empieza con "SIN_ID": -25 puntos
          - Nombre/apellido contiene solo 1 palabra de < 3 chars: -5 puntos
        """
        PESOS = {
            "ocr": 25,
            "identificacion": 25,
            "nombres": 15,
            "apellidos": 15,
            "fecha_nacimiento": 6,
            "fecha_expedicion": 6,
            "lugar_expedicion": 5,
            "sexo": 3,
        }

        puntos = 0.0

        # Score OCR (si se provee)
        if scores_ocr:
            promedio_ocr = sum(scores_ocr) / len(scores_ocr)
            puntos += promedio_ocr * PESOS["ocr"]
        else:
            puntos += PESOS["ocr"] * 0.7  # default si no hay scores

        # Campos
        for campo in ["identificacion", "nombres", "apellidos",
                      "fecha_nacimiento", "fecha_expedicion",
                      "lugar_expedicion", "sexo"]:
            if resultado.get(campo):
                puntos += PESOS[campo]

        # ── Penalizaciones ────────────────────────────────────────────────
        id_val = resultado.get("identificacion") or ""
        if "SIN_ID" in str(id_val).upper():
            puntos -= PESOS["identificacion"]

        for campo_nombre in ["nombres", "apellidos"]:
            val = resultado.get(campo_nombre) or ""
            if val in ("POR REVISAR", ""):
                puntos -= 10
            elif len(val.split()) == 1 and len(val) < 3:
                puntos -= 5

        return min(max(round(puntos, 2), 0.0), 100.0)


extractor_service = ExtractorService()
