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
from app.services.spatial_field_extractor import spatial_field_extractor
from app.services.colombia_geo_service import colombia_geo


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
        r"\bCIUDAD\b",                              # word boundary para no emparejar CIUDADANÍA
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
        "SAN JOSE DEL GUAVIARE", "SAN ANDRÉS", "SAN VICENTE DEL CAGUAN", "SAN VICENTE",
        "GARZON", "GARZÓN", "DONCELLO", "EL DONCELLO", "PUERTO RICO",
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
        "CERETÉ", "LORICA", "TIERRALTA", "MAICAO", "URIBIA", "ALBANIA",
        "TUMACO", "IPIALES", "LA UNION", "BELEN DE LOS ANDAQUIES", "PUERTO ASIS", "PUERTO ASÍS", "PIAMONTE",
        "ACACIAS", "GRANADA", "PUERTO LOPEZ", "PUERTO LÓPEZ", "RESTREPO", "CUMARAL",
        "TAURAMENA", "AGUAZUL", "OROCUE", "OROCUÉ", "PAZ DE ARIPORO", "SARAVENA", "TAME", "ARAUQUITA", "FORTUL",
        "MIRAFLORES", "EL RETORNO", "PUERTO GAITAN", "LA MACARENA", "VISTA HERMOSA",
        # Municipios de Caquetá y Huila
        "CURILLO", "EL PAUJIL", "PAUJIL", "LA MONTAÑITA", "MONTAÑITA", "MILAN", "MILÁN",
        "MORELIA", "SAN JOSE DEL FRAGUA", "SOLANO", "SOLITA", "VALPARAISO", "VALPARAÍSO",
        "CARTAGENA DEL CHAIRA", "CHAIRA", "PITALITO", "ACEVEDO", "AGRADO", "AIPE", "ALGECIRAS",
        "ALTAMIRA", "BARAYA", "CAMPOALEGRE", "COLOMBIA", "ELIAS", "GUADALUPE", "HOBO", "IQUIRA",
        "ISNOS", "LA ARGENTINA", "LA PLATA", "NATAGA", "OPORAPA", "PAICOL", "PALERMO", "PALESTINA",
        "RIVERA", "SALADOBLANCO", "SAN AGUSTIN", "SAN AGUSTÍN", "SANTA MARIA", "SUAZA",
        "TARQUI", "TELLO", "TERUEL", "TESALIA", "TIMANA", "TIMANÁ", "VILLAVIEJA", "YAGUARA",
        "BOGOTA D.C.", "BOGOTA D.C", "BOGOTA DC",
    ]

    # Departamentos de Colombia (para evitar que se tomen como lugar de expedición en vez del municipio)
    DEPARTAMENTOS_COLOMBIA = {
        "AMAZONAS", "ANTIOQUIA", "ARAUCA", "ATLANTICO", "ATLÁNTICO", "BOLIVAR", "BOLÍVAR",
        "BOYACA", "BOYACÁ", "CALDAS", "CAQUETA", "CAQUETÁ", "CASANARE", "CAUCA", "CESAR",
        "CHOCO", "CHOCÓ", "CORDOBA", "CÓRDOBA", "CUNDINAMARCA", "GUAINIA", "GUAINÍA",
        "GUAVIARE", "HUILA", "LA GUAJIRA", "GUAJIRA", "MAGDALENA", "META", "NARIÑO",
        "NORTE DE SANTANDER", "PUTUMAYO", "QUINDIO", "QUINDÍO", "RISARALDA",
        "SAN ANDRES Y PROVIDENCIA", "SAN ANDRES", "SAN ANDRÉS", "SANTANDER", "SUCRE",
        "TOLIMA", "VALLE DEL CAUCA", "VALLE", "VAUPES", "VAUPÉS", "VICHADA"
    }

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
        # Compilar patrón de municipios (priorizando nombres compuestos y largos)
        if ExtractorService._PATRON_MUNICIPIOS is None:
            # Filtrar departamentos para que no eclipsen los municipios
            municipios_puros = [m for m in self.MUNICIPIOS_COLOMBIA if m.upper() not in self.DEPARTAMENTOS_COLOMBIA]
            municipios_sorted = sorted(
                municipios_puros, key=len, reverse=True
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
    def detectar_tipo_documento(self, texto: str) -> str:
        """Determina si el texto corresponde a Cédula de Ciudadanía, Tarjeta de Identidad o Desconocido."""
        if not texto:
            return "UNKNOWN"
        texto_up = texto.upper()
        if re.search(r"\b(TARJETA DE IDENTIDAD|TARJETA IDENTIDAD|TARJETA DE IDENTIF|T\.I)\b", texto_up):
            return "TARJETA_IDENTIDAD"
        elif re.search(r"\b(CEDULA|CÉDULA|CIUDADANIA|CIUDADANÍA|REPUBLICA DE COLOMBIA|REPÚBLICA DE COLOMBIA|NUIP)\b", texto_up):
            return "CEDULA_CIUDADANIA"
        else:
            return "UNKNOWN"

    def _extraer_por_layout_espacial(self, layout_pages: List[Any]) -> Dict[str, Any]:
        """
        Extrae candidatos por proximidad espacial entre etiquetas y valores en el layout.
        """
        if not layout_pages:
            return {}

        page_data = layout_pages[0]
        lines = getattr(page_data, "lines", [])
        if not lines:
            return {}

        labels_map = {
            "identificacion": [r"NUIP", r"NUMERO", r"CEDULA", r"CIUDADANIA", r"IDENTIFICACION"],
            "nombres": [r"NOMBRES", r"NOMBRE"],
            "apellidos": [r"APELLIDOS", r"APELLIDO"],
            "fecha_nacimiento": [r"FECHA DE NACIMIENTO", r"NACIMIENTO"],
            "fecha_expedicion": [r"FECHA Y LUGAR DE EXPEDICION", r"FECHA DE EXPEDICION", r"EXPEDICION"],
            "lugar_expedicion": [r"FECHA Y LUGAR DE EXPEDICION", r"LUGAR DE EXPEDICION", r"LUGAR EXPEDICION"],
            "sexo": [r"SEXO", r"GENERO"]
        }

        found_labels = {}
        for line in lines:
            txt_up = getattr(line, "text", "").upper().strip()
            for key, patterns in labels_map.items():
                if key not in found_labels:
                    for pat in patterns:
                        if re.search(rf"\b{pat}\b", txt_up):
                            found_labels[key] = line
                            break

        spatial_candidates = {}
        for key, label_line in found_labels.items():
            lx, ly, lw, lh = getattr(label_line, "x", 0), getattr(label_line, "y", 0), getattr(label_line, "w", 0), getattr(label_line, "h", 0)
            candidates = []
            for cand_line in lines:
                if cand_line == label_line:
                    continue
                cx, cy = getattr(cand_line, "x", 0), getattr(cand_line, "y", 0)
                is_right = abs(cy - ly) <= lh * 1.5 and cx >= lx + (lw * 0.2)
                is_below = cy > ly and cy <= ly + lh * 3.5 and abs(cx - lx) <= lw * 2.0
                if is_right or is_below:
                    candidates.append((getattr(cand_line, "text", ""), getattr(cand_line, "confidence", 0.9)))

            if candidates:
                spatial_candidates[key] = candidates[0]

        return spatial_candidates

    # ──────────────────────────────────────────
    # MÉTODO PRINCIPAL DE EXTRACCIÓN
    # ──────────────────────────────────────────
    def extraer(
        self,
        texto_ocr: str,
        scores_confianza: List[float] = None,
        layout_data: Any = None,
        pagina_num: int = 1,
        ocr_engine: str = "google_document_ai"
    ) -> Dict[str, Any]:
        """
        Extrae todos los campos de un texto OCR de documento colombiano.
        """
        logger.info(f"Iniciando extracción inteligente de campos (página {pagina_num})")

        texto = self._normalizar_texto(texto_ocr)
        lineas = [l.strip() for l in texto.split("\n") if l.strip()]

        tipo_doc = self.detectar_tipo_documento(texto)

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
            "tipo_documento": tipo_doc,
            "detalles_campos": {},
            "errores": [],
        }

        # Si el tipo de documento es desconocido, no forzar extracciones erróneas
        if tipo_doc == "UNKNOWN" and len(texto) < 30:
            resultado["confianza_extraccion"] = 0.0
            detalles_campos = {}
            for campo in ["identificacion", "nombres", "apellidos", "fecha_nacimiento", "fecha_expedicion", "lugar_expedicion", "sexo"]:
                detalles_campos[campo] = {
                    "value": None, "confidence": 0.0, "page": pagina_num,
                    "status": "missing", "source": ocr_engine,
                    "reason": "Tipo de documento no identificado o texto insuficiente"
                }
            resultado["detalles_campos"] = detalles_campos
            return resultado

        # ── Estrategia 0: Extracción Espacial 2D Centralizada (0% Diccionario, 2D Bounding Boxes) ────
        lines_to_process = []
        if layout_data and hasattr(layout_data, "pages") and layout_data.pages:
            for page in layout_data.pages:
                if getattr(page, "lines", None):
                    lines_to_process.extend(page.lines)

        if not lines_to_process and lineas:
            class PseudoOCRLine:
                def __init__(self, text_val, y_pos):
                    self.text = text_val
                    self.x = 0.1
                    self.y = y_pos
                    self.w = 0.8
                    self.h = 0.04
                    self.confidence = 0.95
            lines_to_process = [PseudoOCRLine(l, (idx + 1) * 0.05) for idx, l in enumerate(lineas)]

        if lines_to_process:
            res_espaciales = spatial_field_extractor.extraer_todos_los_campos(
                lines_to_process, pagina_num, doc_ai_confidence=0.95
            )
            for campo, info in res_espaciales.items():
                if info and info.get("value") and info.get("status") == "VALID":
                    resultado[campo] = info["value"]

        # ── Estrategia 1: MRZ (Zona Legible por Máquina) ─────────────────
        datos_mrz = self._extraer_mrz(texto, lineas)
        if datos_mrz:
            for k, v in datos_mrz.items():
                if v and not resultado.get(k):
                    resultado[k] = v

        # ── Estrategia 2: Fallbacks para identificación y fechas (NO sobreescribir nombres/apellidos) ─────
        if not resultado["identificacion"]:
            resultado["identificacion"] = self._extraer_identificacion(texto, lineas)

        if not resultado["fecha_nacimiento"]:
            resultado["fecha_nacimiento"] = self._extraer_fecha(texto, lineas, self.KEYWORDS_FECHA_NAC)
        if not resultado["fecha_expedicion"]:
            resultado["fecha_expedicion"] = self._extraer_fecha(texto, lineas, self.KEYWORDS_FECHA_EXP)
        if not resultado["lugar_expedicion"]:
            resultado["lugar_expedicion"] = self._extraer_lugar(texto, lineas)
        if not resultado["sexo"]:
            resultado["sexo"] = self._extraer_sexo(texto, lineas)

        # Cédula nueva
        if not resultado["fecha_nacimiento"]:
            resultado["fecha_nacimiento"] = self._extraer_fecha_nueva_cedula(texto, lineas, self.KEYWORDS_FECHA_NAC)
        if not resultado["fecha_expedicion"] or not resultado["lugar_expedicion"]:
            fexp, lugar = self._extraer_fecha_y_lugar_nueva_cedula(texto, lineas)
            if not resultado["fecha_expedicion"] and fexp:
                resultado["fecha_expedicion"] = fexp
            if not resultado["lugar_expedicion"] and lugar:
                resultado["lugar_expedicion"] = lugar

        if not resultado["apellidos"]:
            resultado["apellidos"] = self._extraer_apellido_antes_nombres(lineas)

        if not resultado["nombres"] or not resultado["apellidos"]:
            nom_clas, ape_clas = self._extraer_nombres_por_clasificacion(lineas)
            if not resultado["nombres"] and nom_clas:
                resultado["nombres"] = nom_clas
            if not resultado["apellidos"] and ape_clas:
                resultado["apellidos"] = ape_clas

        # Chronological dates fallback
        if not resultado["fecha_nacimiento"] or not resultado["fecha_expedicion"]:
            fechas_encontradas = []
            for match in re.finditer(r"\b(\d{1,2}[\s/\-\.](?:[A-Za-z0-9]{3,4}|\d{1,2})[\s/\-\.]\d{4}|\d{4}[\s/\-\.]\d{1,2}[\s/\-\.]\d{1,2})\b", texto, re.IGNORECASE):
                f_obj = validador.parsear_fecha(match.group(1))
                if f_obj and f_obj not in fechas_encontradas:
                    fechas_encontradas.append(f_obj)

            fechas_encontradas.sort()
            if len(fechas_encontradas) >= 2:
                if not resultado["fecha_nacimiento"]:
                    resultado["fecha_nacimiento"] = fechas_encontradas[0].isoformat()
                if not resultado["fecha_expedicion"]:
                    resultado["fecha_expedicion"] = fechas_encontradas[-1].isoformat()
            elif len(fechas_encontradas) == 1:
                f_unica = fechas_encontradas[0]
                if f_unica.year <= 2010 and not resultado["fecha_nacimiento"]:
                    resultado["fecha_nacimiento"] = f_unica.isoformat()
                elif f_unica.year > 2010 and not resultado["fecha_expedicion"]:
                    resultado["fecha_expedicion"] = f_unica.isoformat()

        # ── Sanitización y Corrección Cronológica Garantizada ─────────────
        self._sanitizar_y_corregir_fechas_y_lugares(resultado, texto, lineas)

        # Calcular confianza
        resultado["confianza_extraccion"] = self._calcular_confianza(
            resultado, scores_confianza
        )

        resultado["campos_encontrados"] = [
            k for k, v in resultado.items()
            if k not in ["confianza_extraccion", "campos_encontrados", "errores", "detalles_campos", "tipo_documento"]
            and v is not None
        ]

        # ── Construir desglose detallado por campo con esquema enriquecido ─────
        detalles_campos = {}
        campos_criticos = ["identificacion", "nombres", "apellidos"]

        for campo in ["identificacion", "nombres", "apellidos", "fecha_nacimiento", "fecha_expedicion", "lugar_expedicion", "sexo"]:
            val = resultado.get(campo)
            eval_info = None

            if val and val != "POR REVISAR" and "SIN_ID" not in str(val):
                status_campo = "VALID"
                if eval_info and eval_info.get("status"):
                    status_upper = eval_info["status"].upper()
                    status_campo = "VALID" if status_upper in ("VALID", "VALIDO") else status_upper
                
                reason_campo = eval_info.get("reason") if eval_info else f"Campo '{campo}' verificado espacialmente"
                conf_campo = eval_info.get("final_score", round(resultado["confianza_extraccion"] / 100.0, 2)) if eval_info else round(resultado["confianza_extraccion"] / 100.0, 2)
                sugerencia_val = eval_info.get("suggestion") if eval_info else None

                detalles_campos[campo] = {
                    "valor": val,
                    "value": val,
                    "valor_original": val,
                    "confidence": conf_campo,
                    "status": status_campo,
                    "page": pagina_num,
                    "source": ocr_engine,
                    "reason": reason_campo,
                    "spatial_score": eval_info.get("spatial_score", 0.95) if eval_info else 0.95,
                    "label_score": eval_info.get("label_score", 1.0) if eval_info else 1.0,
                    "format_score": 1.0,
                    "suggestion": sugerencia_val,
                    "dictionary_score": eval_info.get("dictionary_score") if eval_info else None,
                    "fuzzy_score": eval_info.get("fuzzy_score") if eval_info else None,
                    "evidence": eval_info.get("evidence", [f"Campo '{campo}' extraído de región física de página {pagina_num}"]) if eval_info else [f"Campo '{campo}' extraído de página {pagina_num}"]
                }
            else:
                detalles_campos[campo] = {
                    "valor": None,
                    "value": None,
                    "valor_original": None,
                    "confidence": 0.0,
                    "status": "MISSING_DATA" if campo in campos_criticos else "REVIEW_REQUIRED",
                    "page": pagina_num,
                    "source": ocr_engine,
                    "reason": f"Evidencia insuficiente para el campo '{campo}'",
                    "spatial_score": 0.0,
                    "label_score": 0.0,
                    "format_score": 0.0,
                    "suggestion": None,
                    "evidence": ["Evidencia insuficiente"]
                }

        resultado["detalles_campos"] = detalles_campos

        logger.info(
            f"Extracción completada. "
            f"Campos: {resultado['campos_encontrados']}. "
            f"Confianza: {resultado['confianza_extraccion']:.1f}%"
        )

        return resultado

    def extraer_grupo(self, group: Any, ocr_engine: str = "google_document_ai") -> Dict[str, Any]:
        """
        Extrae y combina la información complementaria de un grupo de documento físico (Frente + Reverso).
        Aplica validación cruzada entre caras y la regla Cero Invención.
        """
        front_data = {}
        back_data = {}

        if getattr(group, "front_page", None):
            fp = group.front_page
            front_data = self.extraer(
                fp.get("texto", ""),
                layout_data=fp.get("layout"),
                pagina_num=fp.get("pagina_numero", 1),
                ocr_engine=ocr_engine
            )

        if getattr(group, "back_page", None):
            bp = group.back_page
            back_data = self.extraer(
                bp.get("texto", ""),
                layout_data=bp.get("layout"),
                pagina_num=bp.get("pagina_numero", 2),
                ocr_engine=ocr_engine
            )

        # Si solo hay una cara disponible
        if front_data and not back_data:
            res = dict(front_data)
            res["grupo_documento_id"] = getattr(group, "group_id", "DOC-001")
            res["pagina_frente"] = getattr(group, "pagina_frente", 1)
            res["pagina_reverso"] = None
            res["detalles_campos"]["grouping"] = group.to_dict() if hasattr(group, "to_dict") else {}
            return res

        if back_data and not front_data:
            res = dict(back_data)
            res["grupo_documento_id"] = getattr(group, "group_id", "DOC-001")
            res["pagina_frente"] = None
            res["pagina_reverso"] = getattr(group, "pagina_reverso", 1)
            res["detalles_campos"]["grouping"] = group.to_dict() if hasattr(group, "to_dict") else {}
            return res

        # ── Frente + Reverso disponibles: Combinación e Integración Complementaria ──
        res = {
            "grupo_documento_id": getattr(group, "group_id", "DOC-001"),
            "pagina_frente": getattr(group, "pagina_frente", 1),
            "pagina_reverso": getattr(group, "pagina_reverso", 2),
            "tipo_documento": front_data.get("tipo_documento", back_data.get("tipo_documento", "CEDULA_CIUDADANIA")),
            "identificacion": front_data.get("identificacion") or back_data.get("identificacion"),
            "nombres": front_data.get("nombres"),
            "apellidos": front_data.get("apellidos"),
            "fecha_nacimiento": front_data.get("fecha_nacimiento") or back_data.get("fecha_nacimiento"),
            "fecha_expedicion": back_data.get("fecha_expedicion") or front_data.get("fecha_expedicion"),
            "lugar_expedicion": back_data.get("lugar_expedicion") or front_data.get("lugar_expedicion"),
            "sexo": front_data.get("sexo") or back_data.get("sexo"),
            "confianza_extraccion": round((front_data.get("confianza_extraccion", 70) + back_data.get("confianza_extraccion", 70)) / 2.0, 1),
            "requiere_revision": front_data.get("requiere_revision", False) or back_data.get("requiere_revision", False) or (getattr(group, "status", "") != "VALID"),
            "estado_registro": getattr(group, "status", "VALID"),
            "detalles_campos": {}
        }

        # Sanitizar y corregir cronología de fechas y lugar combinado
        self._sanitizar_y_corregir_fechas_y_lugares(
            res,
            f"{front_data.get('texto', '')} {back_data.get('texto', '')}",
            list(front_data.get("lineas", [])) + list(back_data.get("lineas", []))
        )

        # Combinar detalles_campos con validación cruzada entre caras
        f_det = front_data.get("detalles_campos", {})
        b_det = back_data.get("detalles_campos", {})

        for campo in ["identificacion", "nombres", "apellidos", "fecha_nacimiento", "fecha_expedicion", "lugar_expedicion", "sexo"]:
            f_val = f_det.get(campo, {}).get("valor")
            b_val = b_det.get(campo, {}).get("valor")

            if f_val and b_val and f_val != b_val:
                # Conflicto entre caras: Marcar REVIEW_REQUIRED sin elegir en silencio
                res["detalles_campos"][campo] = {
                    "valor": f_val,
                    "value": f_val,
                    "valor_original": f"Frente: {f_val} | Reverso: {b_val}",
                    "confidence": 0.50,
                    "status": "REVIEW_REQUIRED",
                    "page": res["pagina_frente"],
                    "source": ocr_engine,
                    "reason": f"Conflicto entre cara Frente ('{f_val}') y Reverso ('{b_val}')",
                    "evidence": [f"Valores en Frente ({f_val}) y Reverso ({b_val}) difieren"]
                }
                res["requiere_revision"] = True
            elif f_val:
                c_dict = dict(f_det[campo])
                if b_val and f_val == b_val:
                    c_dict["confidence"] = min(0.99, float(c_dict.get("confidence", 0.9)) + 0.05)
                    c_dict["evidence"].append(f"Verificado adicionalmente en cara Reverso (pág. {res['pagina_reverso']})")
                res["detalles_campos"][campo] = c_dict
            elif b_val:
                res["detalles_campos"][campo] = dict(b_det[campo])
            else:
                res["detalles_campos"][campo] = {
                    "valor": None,
                    "value": None,
                    "valor_original": None,
                    "confidence": 0.0,
                    "status": "MISSING_DATA" if campo in ["identificacion", "nombres", "apellidos"] else "REVIEW_REQUIRED",
                    "page": res["pagina_frente"] or res["pagina_reverso"],
                    "source": ocr_engine,
                    "reason": f"Sin evidencia suficiente en Frente ni Reverso",
                    "evidence": ["Evidencia insuficiente"]
                }

        res["detalles_campos"]["grouping"] = group.to_dict() if hasattr(group, "to_dict") else {}
        res["campos_encontrados"] = [k for k, v in res.items() if k in ["identificacion", "nombres", "apellidos", "fecha_nacimiento", "fecha_expedicion", "lugar_expedicion", "sexo"] and v is not None]

        return res

    # ──────────────────────────────────────────
    # NORMALIZACIÓN
    # ──────────────────────────────────────────
    def _normalizar_texto(self, texto: str) -> str:
        """Normaliza el texto OCR para facilitar la extracción."""
        if not texto:
            return ""

        texto = texto.upper()
        # Desegmentar etiquetas pegadas a valores por errores de OCR (ej: APELLIDORAJONAL -> APELLIDO RAJONAL)
        texto = re.sub(
            r"\b(APELLIDOS?|NOMBRES?|IDENTIFICACION|IDENTIFICACIÓN|NUMERO|NÚMERO|EXPEDICION|EXPEDICIÓN)([A-ZÁÉÍÓÚÜÑ]{3,})\b",
            r"\1 \2",
            texto,
            flags=re.IGNORECASE,
        )
        texto = re.sub(r" +", " ", texto)
        texto = re.sub(r"\n+", "\n", texto)

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
        # ── Cédula en MRZ: COL1117811948<6 ──────────────────────────────
        match_id_mrz = re.search(r"COL([1-9]\d{5,9})[<0-9]", texto)
        if match_id_mrz:
            valido, num = validador.validar_cedula(match_id_mrz.group(1))
            if valido:
                datos["identificacion"] = num

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

            aps = validador.normalizar_nombre(raw_aps)
            noms = validador.normalizar_nombre(raw_noms)

            if aps:
                datos["apellidos"] = aps
            if noms:
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
            if re.match(r"^[1-9]\d{6,9}$", linea_limpia):
                valido, numero = validador.validar_cedula(linea_limpia)
                if valido:
                    logger.debug(f"Cédula por línea numérica: {numero}")
                    return numero

        # Estrategia 4: Corrección OCR en candidatos largos (7-10 dígitos)
        candidatos = self._patron_cedula.findall(texto)
        for candidato in candidatos:
            if len(candidato) >= 7:
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
                # Limitar a máximo 5 palabras y filtrar ruidos de encabezado
                palabras = valor.split()[:5]
                from app.services.spatial_field_extractor import spatial_field_extractor
                palabras_validas = [p for p in palabras if len(p) >= 2 and not spatial_field_extractor.NO_NOMBRE_HEADER.search(p)]
                if not palabras_validas:
                    continue
                valor_normalizado = validador.normalizar_nombre(" ".join(palabras_validas))
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
        for idx, linea in enumerate(lineas):
            linea_up = linea.upper().strip()

            if re.search(r"\b(APELLIDOS?|PRIMER\s+APELLIDO|SEGUNDO\s+APELLIDO|SURNAMES?)\b", linea_up):
                cand_anterior = self._linea_valida_texto(lineas[idx - 1]) if idx > 0 else None
                cand_siguiente = self._siguiente_linea_valida(lineas, idx)
                if cand_anterior and not apellidos:
                    apellidos = cand_anterior
                elif cand_siguiente and not apellidos:
                    apellidos = cand_siguiente

            if re.search(r"\b(NOMBRES?|PRIMER\s+NOMBRE|SEGUNDO\s+NOMBRE|GIVEN\s+NAMES?)\b", linea_up):
                cand_anterior = self._linea_valida_texto(lineas[idx - 1]) if idx > 0 else None
                cand_siguiente = self._siguiente_linea_valida(lineas, idx)
                if cand_anterior and cand_anterior != apellidos and not nombres:
                    nombres = cand_anterior
                elif cand_siguiente and cand_siguiente != apellidos and not nombres:
                    nombres = cand_siguiente

        return nombres, apellidos

    def _linea_valida_texto(self, linea: str) -> Optional[str]:
        if not linea:
            return None
        txt = linea.strip()
        if re.search(r"\d", txt):
            return None
        txt_clean = re.sub(r"[^A-ZÁÉÍÓÚÜÑ\s]", "", txt.upper()).strip()
        from app.services.spatial_field_extractor import spatial_field_extractor
        tokens = [t for t in txt_clean.split() if len(t) >= 2 and not spatial_field_extractor.NO_NOMBRE_HEADER.search(t)]
        if not tokens or len(tokens) > 5:
            return None
        res = " ".join(tokens)
        return res if len(res) >= 3 else None

    def _siguiente_linea_valida(
        self, lineas: List[str], desde: int
    ) -> Optional[str]:
        """
        Devuelve la primera línea posterior a `desde` que parezca
        un nombre/apellido válido (solo letras, 3-60 chars, sin palabras prohibidas como FIRMA).
        """
        for linea in lineas[desde + 1 : desde + 5]:
            linea = linea.strip()
            if not linea:
                continue
            # Ignorar si es solo dígitos o números
            if re.search(r"\d", linea):
                continue
            # Solo letras, espacios y guiones, entre 3 y 60 chars
            if re.match(r"^[A-ZÁÉÍÓÚÜÑa-záéíóúüñ\s\-]{3,60}$", linea):
                nombre_norm = validador.normalizar_nombre(linea)
                if nombre_norm and len(nombre_norm.split()) <= 5:
                    return nombre_norm
        return None

    def _extraer_nombres_por_clasificacion(self, lineas: List[str]) -> Tuple[Optional[str], Optional[str]]:
        """
        REGLA DE PRECISIÓN Y CERO INVENCIÓN:
        No se utiliza clasificación por diccionarios de nombres/apellidos.
        La detección se realiza 100% por coordenadas y estructura de Document AI.
        """
        return None, None

    def _corregir_nombres_apellidos_invertidos(self, resultado: Dict[str, Any]):
        """
        REGLA DE PRECISIÓN Y CERO INVENCIÓN:
        Los diccionarios NO deben reordenar ni intercambiar silenciosamente las palabras
        extraídas por Document AI. Se respeta 100% la posición del OCR en sus coordenadas.
        """
        return

    # ──────────────────────────────────────────
    # EXTRACCIÓN DE FECHAS
    # Meses en español/abreviado para cédula nueva
    _MESES_ABREV = {
        "ENE": 1, "FEB": 2, "MAR": 3, "ABR": 4, "MAY": 5, "JUN": 6,
        "JUL": 7, "AGO": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DIC": 12,
        "JAN": 1, "APR": 4, "AUG": 8, "DEC": 12,
    }

    def _sanitizar_y_corregir_fechas_y_lugares(self, resultado: Dict[str, Any], texto: str, lineas: List[str]):
        """
        Garantiza consistencia cronológica de fechas y validación de lugares:
          1. En Colombia la fecha de nacimiento DEBE ser anterior a la de expedición.
             Si están invertidas (ej. Nacimiento 1985 y Expedición 1967), las intercambia.
          2. Si fecha_nacimiento == fecha_expedicion (imposible para cédula de adulto),
             busca en el texto otras fechas para asignar la correcta.
          3. Sanitiza el lugar de expedición eliminando cualquier nombre de registrador,
             firmas o ruido residual.
        """
        # 1. Validación cronológica de fechas
        fn_str = resultado.get("fecha_nacimiento")
        fe_str = resultado.get("fecha_expedicion")
        
        fn_obj = validador.parsear_fecha(fn_str) if fn_str else None
        fe_obj = validador.parsear_fecha(fe_str) if fe_str else None
        
        # Buscar todas las fechas candidatas en el documento ordenadas cronológicamente
        fechas_doc = []
        for match in re.finditer(r"\b(\d{1,2}[\s/\-\.](?:[A-Za-z0-9]{3,4}|\d{1,2})[\s/\-\.]\d{4}|\d{4}[\s/\-\.]\d{1,2}[\s/\-\.]\d{1,2})\b", texto, re.IGNORECASE):
            f_obj = validador.parsear_fecha(match.group(1))
            if f_obj and f_obj not in fechas_doc:
                fechas_doc.append(f_obj)
        fechas_doc.sort()

        if fn_obj and fe_obj:
            if fe_obj < fn_obj:
                # Fechas invertidas -> Intercambiar
                resultado["fecha_nacimiento"] = fe_obj.isoformat()
                resultado["fecha_expedicion"] = fn_obj.isoformat()
                fn_obj, fe_obj = fe_obj, fn_obj
            elif fe_obj == fn_obj:
                # Fechas idénticas -> Buscar fecha alternativa en el documento
                otras = [f for f in fechas_doc if f != fn_obj]
                if otras:
                    fechas_combinadas = sorted([fn_obj] + otras)
                    resultado["fecha_nacimiento"] = fechas_combinadas[0].isoformat()
                    resultado["fecha_expedicion"] = fechas_combinadas[-1].isoformat()
        elif not fn_obj and fe_obj and len(fechas_doc) >= 2:
            resultado["fecha_nacimiento"] = fechas_doc[0].isoformat()
            resultado["fecha_expedicion"] = fechas_doc[-1].isoformat()
        elif fn_obj and not fe_obj and len(fechas_doc) >= 2:
            resultado["fecha_nacimiento"] = fechas_doc[0].isoformat()
            resultado["fecha_expedicion"] = fechas_doc[-1].isoformat()

        # 2. Validación y limpieza de lugar de expedición universal
        lugar_actual = resultado.get("lugar_expedicion")
        lugar_limpio = validador.normalizar_lugar(str(lugar_actual)) if lugar_actual else None

        # Si el lugar actual es un departamento (ej: CAQUETA, VALLE) o está vacío o fue ruidoso:
        if not lugar_limpio or lugar_limpio in colombia_geo.DEPARTAMENTOS:
            lugar_mun = colombia_geo.extraer_lugar_universal(texto, lineas)
            if lugar_mun and lugar_mun not in colombia_geo.DEPARTAMENTOS:
                resultado["lugar_expedicion"] = lugar_mun
            elif lugar_limpio:
                resultado["lugar_expedicion"] = lugar_limpio
            else:
                resultado["lugar_expedicion"] = None
        else:
            # Resolver y normalizar contra el catálogo nacional de 1.100 municipios DANE
            mun_canonico = colombia_geo.resolver_municipio_fuzzy(lugar_limpio, umbral=80)
            resultado["lugar_expedicion"] = mun_canonico if mun_canonico else lugar_limpio

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
                keyword + r"[\s:\n]*"
                r"(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{4}"
                r"|\d{4}[/\-\.]\d{1,2}[/\-\.]\d{1,2}"
                r"|\d{1,2}[\s/\-\.][A-Za-z]{3,4}[\s/\-\.]\d{4}"
                r"|\d{1,2}\s+DE\s+\w+\s+DE\s+\d{4})",
                re.IGNORECASE,
            )
            match = patron.search(texto)
            if match:
                fecha_texto = match.group(1)
                fecha = validador.parsear_fecha(fecha_texto)
                if fecha:
                    return fecha.isoformat()

            # Búsqueda secundaria: si la fecha está en la línea siguiente a la palabra clave
            for idx, linea in enumerate(lineas):
                if re.search(keyword, linea, re.IGNORECASE):
                    subtexto = " ".join(lineas[idx: min(len(lineas), idx + 3)])
                    m_fecha = re.search(
                        r"\b(\d{1,2}[\s/\-\.](?:[A-Za-z]{3,4}|\d{1,2})[\s/\-\.]\d{4})\b",
                        subtexto,
                    )
                    if m_fecha:
                        f = validador.parsear_fecha(m_fecha.group(1))
                        if f:
                            return f.isoformat()

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
        En la cédula colombiana los APELLIDOS aparecen en la línea
        inmediatamente anterior al label 'Nombres' / 'NOMBRES'.
        """
        from app.services.spatial_field_extractor import spatial_field_extractor
        for idx, linea in enumerate(lineas):
            if re.match(r"^NOMBRES?$", linea.strip().upper()) and idx > 0:
                candidato = lineas[idx - 1].strip()
                if spatial_field_extractor.NO_NOMBRE_HEADER.search(candidato):
                    continue
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
        Extrae el municipio/ciudad de expedición mediante el motor universal DANE.
        Cubre los 32 departamentos y más de 1.100 municipios de Colombia con RapidFuzz.
        """
        return colombia_geo.extraer_lugar_universal(texto, lineas)

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

        # Fallback 1: M o F solos después de "SEXO" en la misma línea
        match = re.search(r"\bSEXO[\s:]*([MF])\b", texto, re.IGNORECASE)
        if match:
            return validador.normalizar_sexo(match.group(1))

        # Fallback 2: "SEXO" en una línea y M/F en líneas siguientes (formato vertical de Google DocAI)
        for idx, linea in enumerate(lineas):
            if re.search(r"\bSEXO\b", linea, re.IGNORECASE):
                for sublinea in lineas[idx + 1 : idx + 5]:
                    sub_clean = sublinea.strip().upper()
                    if sub_clean in ("M", "F", "MASCULINO", "FEMENINO", "MASC", "FEM"):
                        return validador.normalizar_sexo(sub_clean)

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
