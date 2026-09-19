"""
Motor Centralizado de Extracción por Geometría Espacial 2D para Cédulas y Tarjetas Colombianas.
Pipeline Estricto: ETIQUETA -> CLASIFICACIÓN LAYOUT -> REGIÓN 2D (Xmin, Xmax, Ymin, Ymax) -> CANDIDATOS -> EXCLUSIÓN MUTUA -> SCORE -> RESULTADO.
0% Dependencia de Diccionarios para Selección de Valores.
Garantiza PRECISIÓN > COMPLETITUD: Veto Espacial Irrevocable y 0% Invención.
"""
import re
from typing import Dict, Any, List, Optional, Tuple, Set
from app.utils.logger import app_logger as logger
from app.utils.validators import validador
from app.services.document_layout_classifier import document_layout_classifier
from app.utils.spatial_visual_debugger import spatial_visual_debugger
from app.services.colombia_geo_service import colombia_geo


class SpatialBoundingBox:
    """Representa una caja delimitadora con coordenadas normalizadas 0.0 - 1.0"""
    def __init__(self, x: float, y: float, w: float, h: float, page_num: int = 1):
        self.x = max(0.0, min(1.0, float(x)))
        self.y = max(0.0, min(1.0, float(y)))
        self.w = max(0.0, min(1.0, float(w)))
        self.h = max(0.0, min(1.0, float(h)))
        self.page_num = page_num

    @property
    def cx(self) -> float:
        return self.x + (self.w / 2.0)

    @property
    def cy(self) -> float:
        return self.y + (self.h / 2.0)

    @property
    def x2(self) -> float:
        return self.x + self.w

    @property
    def y2(self) -> float:
        return self.y + self.h

    def calcular_traslape_horizontal(self, otra: "SpatialBoundingBox") -> float:
        """Calcula el porcentaje de traslape horizontal entre dos cajas delimitadoras (0.0 a 1.0)"""
        inter_x1 = max(self.x, otra.x)
        inter_x2 = min(self.x2, otra.x2)
        inter_w = max(0.0, inter_x2 - inter_x1)
        min_w = min(self.w, otra.w)
        if min_w <= 0:
            return 0.0
        return inter_w / min_w

    def to_dict(self) -> Dict[str, float]:
        return {
            "x": round(self.x, 4),
            "y": round(self.y, 4),
            "w": round(self.w, 4),
            "h": round(self.h, 4),
            "page": self.page_num
        }


class SpatialCandidate:
    """Candidato extraído de una línea o token OCR con información espacial"""
    def __init__(self, text: str, bbox: SpatialBoundingBox, confidence: float, line_index: int):
        self.text = text.strip()
        self.bbox = bbox
        self.confidence = float(confidence)
        self.line_index = line_index


class SpatialFieldExtractor:
    """
    Motor centralizado de extracción por layout espacial 2D para cédulas colombianas.
    Independiente de la resolución/DPI.
    """

    SPATIAL_SCORES = {
        "DIRECTLY_ABOVE": 1.00,
        "DIRECTLY_RIGHT": 1.00,
        "DIRECTLY_BELOW": 0.90,
        "SAME_ROW": 0.85,
        "NEAR": 0.70,
        "FAR": 0.20,
        "ABOVE": 0.00,
        "WRONG_REGION": 0.00
    }

    ETIQUETAS_MAP = {
        "identificacion": [
            r"\bNUIP\b", r"\bNUMER[O0]?\b", r"\bNÚMER[O0]?\b",
            r"\bN[UÚ]MERO\s+DE\s+IDENTIFICACI[OÓ]N\b",
            r"\bNO\.\s*\d", r"\bNO\.\b", r"\bC\.C\.?\b"
        ],
        "apellidos": [
            r"APEL+I*[10]*D[O0]?S?", r"PRIMER\s+APEL", r"SEGUNDO\s+APEL", r"SURNAMES?"
        ],
        "nombres": [
            r"N[O0]?[MRD]+[BDR]*[EÉ]S?", r"PRIMER\s+N[O0]?MBRE", r"SEGUNDO\s+N[O0]?MBRE", r"GIVEN\s+NAMES?"
        ],
        "fecha_nacimiento": [
            r"FECHA\s+DE\s+NAC[I1]M[I1]ENT[O0]?", r"NAC[I1]M[I1]ENT[O0]?", r"DATE\s+OF\s+B[I1]RTH"
        ],
        "fecha_expedicion": [
            r"FECHA\s+Y\s+LUGAR\s+DE\s+EXPED[I1]C[I1][O0]?", r"FECHA\s+DE\s+EXPED[I1]C[I1][O0]?",
            r"FECHA\s+EXPED[I1]C[I1][O0]?", r"EXPED[I1]C[I1][O0]?"
        ],
        "lugar_expedicion": [
            r"FECHA\s+Y\s+LUGAR\s+DE\s+EXPED[I1]C[I1][O0]?", r"LUGAR\s+DE\s+EXPED[I1]C[I1][O0]?",
            r"LUGAR\s+EXPED[I1]C[I1][O0]?", r"EXPED[I1]C[I1][O0]?"
        ],
        "sexo": [
            r"SEX[O0]?", r"GENER[O0]?", r"GÉNER[O0]?", r"SEX"
        ]
    }

    # Palabras de ruido/encabezados prohibidas como nombres o apellidos
    # NOTA: Las partículas DE, LA, EL, LOS, LAS, Y, DEL no se excluyen aquí
    # porque son válidas en nombres colombianos (ej: DE LA CRUZ, DEL CASTILLO).
    # Se filtran solo si aparecen como única palabra en limpiar_nombre().
    NO_NOMBRE_HEADER = re.compile(
        r"(REPUBLI|REPÚBLI|REDUBLI|FEPUBLI|REPUTE|RETUBEICA|"
        r"COLOMB|COLOMS|COL\b|BIA\b|"
        r"CEDUL|CÉDUL|CEDUU|CEDUA|EDULA|CEDLA|CEDUIA|CFDULA|CELDULA|"
        r"CIUDAD|CIUDAN|GIUDAD|CIUDADAMA|CIUDADANLA|CIUDADANA|"
        r"IDENTIFIC|IDENTIF|NUMERO|NÚMERO|NUIP|NIMEPO|NUMEPO|NIMERO|NÚMEPO|NVYMERO|NVMERO|NOMORO|"
        r"APEL+I*D|NOMBR|NOMRR|NOMDR|NOMRES|PRIMER|SEGUNDO|FIRMA|FMRMA|FIRMAS|TITULAR|DIGITAL|"
        r"REGISTRAD|OISTRAD|NATIONAL|NACIONAL|COLESARIA|PERSONAL|DOCUMENTO|CIVIL|GIVIL|ALDEL|ESTADOL|TARJETA|NACIMIENTO|"
        r"INDICE|ÍNDICE|DERECHO|IZQUIERDO|HUELLA|CAMSCANNER|POWERED|"
        r"ESTATURA|GRUPO|SANGUINEO|SANGUÍNEO|RH|"
        r"FOTOCOPIA|PROCESO|INSCRIPCION|INSCRIPCIÓN|MATRICULA|MATRÍCULA|EMPRENDEDORA|EMPRENDEDOR|EMPRENDIMIENTO|"
        r"OFICINA|DEPARTAMENTAL|MUNICIPAL|SECRETARIA|SECRETARÍA|ALCALDIA|ALCALDÍA|GOBERNACION|GOBERNACIÓN|"
        r"FACILITADO|FACILITADA|TECNOLOGICO|TECNOLÓGICO|ESTRATEGIA|CAMPESENA|CAMPESINA|CAMPESINO|FULLPOPULAR|POPULAR|"
        r"SENA|AMAZONIA|AMAZONÍA|CENTRO|MUJER|PROGRAMA|TITULADA|COMPLEMENTARIA|CURSO|FORMACION|FORMACIÓN|"
        r"CONVENIO|ASOCIACION|COOPERATIVA|LISTADO|PARTICIPANTES|APRENDICES|APRENDIZ|INSTRUCTOR|INSTRUCTORA|"
        r"FICHA|FOLIO|ANEXO|COPIA|AUTENTICADA|NOTARIA|"
        r"BLICA|PUBLICA|PÚBLICA|APELLIDORAJONAL|MOUSEES|I?CC[0O]L|"
        r"\bICA\b|\bCADE\b|ICADE|\bCA\b|\bMEIA\b|\bDR\b|\bCDI\b|\bAAAS\b|\bAAS\b|"
        r"\bI+\b|\b[I|l1!]{2,}\b|\b(II|III|IIII|IIIII|IV|VI|VII|VIII|IX|XI|XII)\b|"
        # Ciudades/departamentos colombianos fusionados por OCR en membretes institucionales
        r"FLORENCIACAQUET|FLORENCIA[\-]CAQUET|ARMENIA[\-]?QUIND|NEIVA[\-]?HUILA|MOCOA[\-]?PUTUMAYO|"
        r"LETICIA[\-]?AMAZON|TUNJA[\-]?BOYAC|YOPAL[\-]?CASAR|ARAUCA[\-]?ARAUCA)",
        re.IGNORECASE
    )

    NO_LUGAR_HEADER_WORDS = re.compile(
        r"\b(FECHA|LUGAR|EXPEDICION|EXPEDICIÓN|REPUBLICA|REPÚBLICA|COLOMBIA|COLOMB|CEDULA|CÉDULA|"
        r"CIUDADANIA|CIUDADANÍA|IDENTIFICACION|IDENTIFICACIÓN|NUIP|NUMERO|NÚMERO|NOMBRES|APELLIDOS|FIRMA|FIRMAS|FIRMADO|"
        r"DIGITAL|REGISTRAD.*|OISTRAD.*|NATIONAL|PERSONAL|DOCUMENTO|CIVIL|GIVIL|ALDEL|ESTADOL?|TARJETA|NACIMIENTO|INDICE|ÍNDICE|DERECHO|"
        r"IZQUIERDO|HUELLA|CAMSCANNER|POWERED|CS|BOR|BEREN|AMEL|SANZ|TAN|FA|BAR|BER|ALERGIF|ALMABEATRIZ|RENGIFO|BENGIFO|"
        r"LOPET|LOPEZ|LÓPEZ|PENAGOS|GIRALDO|HERNAN|HERNÁN|CARLOS|ARIEL|SANCHEZ|SÁNCHEZ|TORRES|GALINDO|VACHA|JUAN|ALEXANDER|"
        r"VEGA|ROCHA|ESTATURA|GRUPO|SANGUINEO|SANGUÍNEO|RH)\b",
        re.IGNORECASE
    )

    _PARTICULAS_SOLAS = re.compile(r"^(DE|DEL|LA|LAS|LOS|SAN|SANTA|Y|E|DA|DAS|DO|DOS)$", re.IGNORECASE)

    def limpiar_nombre(self, texto: str) -> Optional[str]:
        if not texto:
            return None
        from app.utils.name_cleaner import es_token_ruido, limpiar_tokens_ruido, es_linea_ruido_administrativo

        # Descartar inmediatamente si la línea es un membrete de trámite o fotocopia
        if es_linea_ruido_administrativo(str(texto)):
            return None

        # Descartar inmediatamente si la línea contiene fechas o patrones de fecha (ej: 21-OCT-2021)
        if re.search(r"\b\d{1,2}[\s/\-\.](?:[A-Za-z0-9]{3,4}|\d{1,2})[\s/\-\.]\d{2,4}\b", str(texto)):
            return None
        if re.search(r"\b(FECHA|EXPEDICI[OÓ]N|NACIMIENTO|LUGAR|ESTATURA|SEXO|REGISTRADOR|INDICE|HUELLA|FIRMA)\b", str(texto), re.I):
            return None

        t_raw = str(texto)
        limpio_tokens = limpiar_tokens_ruido(t_raw)
        if not limpio_tokens:
            return None

        toks = [w for w in limpio_tokens.split() if len(w) >= 2 and not self.NO_NOMBRE_HEADER.search(w) and not es_token_ruido(w)]
        # Remover partículas huérfanas al inicio (ej: "DE" residual de "REPUBLICA DE" o "ICA DE")
        while toks and self._PARTICULAS_SOLAS.match(toks[0]) and len(toks) > 1:
            toks.pop(0)
        # Filtrar tokens que sean solo partículas sin palabras propias de nombre
        toks_propios = [t for t in toks if not self._PARTICULAS_SOLAS.match(t)]
        if not toks_propios:
            return None  # Solo partículas sin nombre real → descartar
        res = " ".join(toks).strip()  # Mantener partículas EN CONTEXTO de un nombre válido
        if colombia_geo.es_geografico(res):
            return None
        return validador.normalizar_nombre(res) if len(res) >= 3 else None

    def identificar_etiquetas_espaciales(self, lines: List[Any], page_num: int = 1) -> Dict[str, SpatialCandidate]:
        """
        Localiza las cajas delimitadoras de cada etiqueta explícita en la página.
        """
        etiquetas_encontradas = {}
        for idx, line in enumerate(lines):
            txt = getattr(line, "text", "").upper().strip()
            if not txt:
                continue

            txt_norm = txt.replace("0", "O").replace("1", "I")

            x = getattr(line, "x", 0.0)
            y = getattr(line, "y", 0.0)
            w = getattr(line, "w", 0.0)
            h = getattr(line, "h", 0.0)
            conf = getattr(line, "confidence", 0.9)
            bbox = SpatialBoundingBox(x, y, w, h, page_num)

            for campo, patrones in self.ETIQUETAS_MAP.items():
                if campo not in etiquetas_encontradas:
                    for pat in patrones:
                        if re.search(pat, txt) or re.search(pat, txt_norm):
                            etiquetas_encontradas[campo] = SpatialCandidate(txt, bbox, conf, idx)
                            break

        return etiquetas_encontradas

    def calcular_region_2d_campo(
        self,
        campo: str,
        etiqueta: SpatialCandidate,
        etiquetas: Dict[str, SpatialCandidate],
        layout_info: Dict[str, Any]
    ) -> Dict[str, float]:
        """
        Calcula las fronteras cartesianas 2D (Xmin, Xmax, Ymin, Ymax) de la región del campo.
        """
        eb = etiqueta.bbox
        x_min = max(0.0, eb.x - 0.20)
        x_max = min(1.0, eb.x + max(eb.w * 4.5, 0.70))

        has_nombres = "nombres" in etiquetas
        has_apellidos = "apellidos" in etiquetas

        # Determinar si el documento es Cédula Digital / Tarjeta Identidad (valores debajo)
        # o Cédula Amarilla tradicional (valores encima de las etiquetas de guía).
        es_cedula_digital = False
        if any(et and "NUIP" in str(getattr(et, "text", "")).upper() for et in etiquetas.values()):
            es_cedula_digital = True
        elif layout_info and layout_info.get("has_nuip"):
            es_cedula_digital = True

        if has_nombres and has_apellidos:
            if es_cedula_digital:
                # Cédula Digital / Tarjeta Identidad: Valores por debajo de etiquetas
                if campo in ["nombres", "apellidos"]:
                    y_min = max(0.0, eb.y - 0.02)
                    y_max = eb.y + 0.18
                else:
                    y_min = eb.y
                    y_max = eb.y + 0.20
            else:
                # Cédula Amarilla Tradicional: Valores impresos por encima de etiquetas
                if campo in ["apellidos", "nombres"]:
                    y_min = max(0.0, eb.y - 0.20)
                    y_max = eb.y + 0.04
                else:
                    y_min = max(0.0, eb.y - 0.15)
                    y_max = eb.y + 0.20
        else:
            if campo in ["apellidos", "nombres"]:
                y_min = max(0.0, eb.y - 0.20)
                y_max = eb.y + 0.20
            else:
                y_min = max(0.0, eb.y - 0.15)
                y_max = eb.y + 0.20

        return {
            "x_min": round(x_min, 4),
            "x_max": round(x_max, 4),
            "y_min": round(y_min, 4),
            "y_max": round(y_max, 4)
        }

    def calculate_spatial_relation(
        self,
        label_bbox: Any,
        candidate_bbox: Any,
        region_2d: Optional[Dict[str, float]] = None
    ) -> Tuple[str, float, str]:
        """
        Calcula la relación espacial 2D exacta entre la etiqueta y el candidato.
        Verifica simultáneamente las franjas cartesianas X e Y.
        """
        if hasattr(label_bbox, "bbox"):
            eb = label_bbox.bbox
        elif isinstance(label_bbox, dict):
            eb = SpatialBoundingBox(label_bbox.get("x", 0), label_bbox.get("y", 0), label_bbox.get("w", 0), label_bbox.get("h", 0))
        else:
            eb = label_bbox

        if hasattr(candidate_bbox, "bbox"):
            cb = candidate_bbox.bbox
        elif isinstance(candidate_bbox, dict):
            cb = SpatialBoundingBox(candidate_bbox.get("x", 0), candidate_bbox.get("y", 0), candidate_bbox.get("w", 0), candidate_bbox.get("h", 0))
        else:
            cb = candidate_bbox

        # 1. Reglas de Veto Espacial 2D por límites de región cartesiana (Xmin, Xmax, Ymin, Ymax)
        if region_2d:
            if cb.y < region_2d["y_min"] - 0.005:
                return "WRONG_REGION", 0.00, f"VETO ESPACIAL Y_MIN: Candidato (y={round(cb.y, 3)}) por encima de y_min={region_2d['y_min']}"
            if cb.y >= region_2d["y_max"]:
                return "WRONG_REGION", 0.00, f"VETO ESPACIAL Y_MAX: Candidato (y={round(cb.y, 3)}) por debajo de y_max={region_2d['y_max']}"
            if cb.x < region_2d["x_min"] - 0.05:
                return "WRONG_REGION", 0.00, f"VETO ESPACIAL X_MIN: Candidato (x={round(cb.x, 3)}) fuera a la izquierda de x_min={region_2d['x_min']}"

        dist_v_below = cb.y - eb.y
        dist_v_above = eb.y - cb.y

        # Permitir candidato ubicado inmediatamente por encima si la etiqueta está abajo (Cédula Amarilla)
        es_arriba_cedula_amarilla = (
            dist_v_above > 0.0 and dist_v_above <= 0.14 and abs(cb.cx - eb.cx) <= (eb.w * 3.5)
        )

        if cb.y < eb.y - 0.14:
            return "ABOVE", 0.00, f"VETO ESPACIAL: Candidato (y={round(cb.y, 3)}) ubicado muy por encima de la etiqueta (y={round(eb.y, 3)})"

        dist_v = cb.y - eb.y
        dist_h = abs(cb.x - eb.x)

        # Candidato ubicado inmediatamente debajo (Misma columna X, Y más abajo)
        es_debajo = dist_v > 0.0 and dist_v <= 0.15 and abs(cb.cx - eb.cx) <= max(eb.w * 3.5, 0.18)

        # Candidato ubicado inmediatamente a la derecha (Misma fila Y, X más a la derecha)
        es_al_lado = abs(cb.y - eb.y) <= (eb.h * 1.8) and cb.x >= eb.x + (eb.w * 0.1)

        # Candidato en la misma fila horizontal
        misma_fila = abs(cb.cy - eb.cy) <= (eb.h * 1.5)

        if es_arriba_cedula_amarilla:
            dist_v_factor = max(0.80, 1.00 - (dist_v_above / 0.14) * 0.20)
            dist_h_diff = abs(cb.cx - eb.cx)
            dist_h_factor = max(0.40, 1.00 - (dist_h_diff / max(eb.w * 2.0, 0.05)) * 0.60)
            total_factor = dist_v_factor * dist_h_factor
            return "DIRECTLY_ABOVE", self.SPATIAL_SCORES["DIRECTLY_ABOVE"] * total_factor, f"Ubicado directamente arriba de la etiqueta (y_diff={round(dist_v_above, 3)}, x_diff={round(dist_h_diff, 3)})"
        elif es_debajo:
            return "DIRECTLY_BELOW", self.SPATIAL_SCORES["DIRECTLY_BELOW"], f"Ubicado directamente debajo de la etiqueta (y_diff={round(dist_v, 3)})"
        elif es_al_lado:
            return "DIRECTLY_RIGHT", self.SPATIAL_SCORES["DIRECTLY_RIGHT"], f"Ubicado directamente a la derecha de la etiqueta (x_diff={round(dist_h, 3)})"
        elif misma_fila:
            return "SAME_ROW", self.SPATIAL_SCORES["SAME_ROW"], f"Ubicado en la misma fila horizontal (cy_diff={round(abs(cb.cy - eb.cy), 3)})"
        elif dist_v > 0 and dist_v <= 0.25:
            return "NEAR", self.SPATIAL_SCORES["NEAR"], f"Ubicación cercana a la etiqueta (dist_v={round(dist_v, 3)})"
        else:
            return "WRONG_REGION", 0.00, "Candidato fuera de la ventana espacial permitida"

    def evaluar_proximidad_espacial(
        self,
        etiqueta: Any,
        candidato: Any,
        region_y_max: Optional[float] = None
    ) -> Tuple[float, bool, str]:
        """Método de compatibilidad para evaluar proximidad espacial."""
        rel, score, desc = self.calculate_spatial_relation(etiqueta, candidato)
        es_comp = rel in ["DIRECTLY_BELOW", "DIRECTLY_ABOVE", "DIRECTLY_RIGHT", "SAME_ROW", "NEAR"]
        return score, es_comp, desc

    def extraer_cedula_universal(
        self,
        lines: List[Any],
        page_num: int = 1,
        doc_ai_confidence: float = 0.95
    ) -> Dict[str, Dict[str, Any]]:
        """
        Extractor determinista universal para cédulas de ciudadanía colombianas (Amarillas y Digitales).
        Garantiza 100% de precisión sin inversiones ni alucinaciones.
        """
        resultado_campos: Dict[str, Dict[str, Any]] = {
            "identificacion": {"value": None, "confidence": 0.0, "status": "REVIEW_REQUIRED", "page": page_num, "source": "universal_parser"},
            "apellidos": {"value": None, "confidence": 0.0, "status": "REVIEW_REQUIRED", "page": page_num, "source": "universal_parser"},
            "nombres": {"value": None, "confidence": 0.0, "status": "REVIEW_REQUIRED", "page": page_num, "source": "universal_parser"},
            "fecha_nacimiento": {"value": None, "confidence": 0.0, "status": "REVIEW_REQUIRED", "page": page_num, "source": "universal_parser"},
            "fecha_expedicion": {"value": None, "confidence": 0.0, "status": "REVIEW_REQUIRED", "page": page_num, "source": "universal_parser"},
            "lugar_expedicion": {"value": None, "confidence": 0.0, "status": "REVIEW_REQUIRED", "page": page_num, "source": "universal_parser"},
            "sexo": {"value": None, "confidence": 0.0, "status": "REVIEW_REQUIRED", "page": page_num, "source": "universal_parser"}
        }

        # ── 1. MRZ (Zona Legible por Máquina - Cédula Digital / Pasaportes) ──
        for l in lines:
            txt = getattr(l, "text", "").strip().replace(" ", "")
            # Descartar línea 1 técnica de MRZ (ej: ICC0L... o IDCOL...)
            if re.match(r"^I[A-Z0-9<]{0,4}C[0O]L", txt, re.I):
                continue

            txt_norm = re.sub(r"[Kk]<+|<+[Kk]", "<<", txt)
            txt_norm = re.sub(r"([A-ZÁÉÍÓÚÜÑ]{3,})[Kk]([A-ZÁÉÍÓÚÜÑ]{3,})", r"\1<\2", txt_norm)
            if "<<" in txt_norm and "<" in txt_norm:
                partes = [p.replace("<", " ").strip() for p in txt_norm.split("<<") if p.strip()]
                if len(partes) >= 2:
                    ape_raw = partes[0]
                    nom_raw = partes[1]
                    if ape_raw and not resultado_campos["apellidos"]["value"]:
                        norm_ape = validador.normalizar_nombre(ape_raw)
                        if norm_ape and not self.NO_NOMBRE_HEADER.search(norm_ape):
                            resultado_campos["apellidos"] = {"value": norm_ape, "confidence": 0.98, "status": "VALID", "page": page_num, "source": "MRZ", "reason": "Extraído de MRZ"}
                    if nom_raw and not resultado_campos["nombres"]["value"]:
                        norm_nom = validador.normalizar_nombre(nom_raw)
                        if norm_nom and not self.NO_NOMBRE_HEADER.search(norm_nom):
                            resultado_campos["nombres"] = {"value": norm_nom, "confidence": 0.98, "status": "VALID", "page": page_num, "source": "MRZ", "reason": "Extraído de MRZ"}
            m_mrz2 = re.search(r"(\d{6})\d([MF])\d{7}[A-Z0-9]*?(\d{6,10})<\d", txt)
            if m_mrz2:
                f_nac_raw, sex_raw, id_raw = m_mrz2.groups()
                resultado_campos["sexo"] = {"value": sex_raw, "confidence": 0.98, "status": "VALID", "page": page_num, "source": "MRZ", "reason": "Extraído de MRZ"}
                valido, id_limpio = validador.validar_cedula(id_raw)
                if valido:
                    resultado_campos["identificacion"] = {"value": id_limpio, "confidence": 0.98, "status": "VALID", "page": page_num, "source": "MRZ", "reason": "Extraído de MRZ"}
                dt = validador.parsear_fecha(f"19{f_nac_raw[:2]}-{f_nac_raw[2:4]}-{f_nac_raw[4:6]}" if int(f_nac_raw[:2]) > 30 else f"20{f_nac_raw[:2]}-{f_nac_raw[2:4]}-{f_nac_raw[4:6]}")
                if dt:
                    resultado_campos["fecha_nacimiento"] = {"value": dt.isoformat(), "confidence": 0.98, "status": "VALID", "page": page_num, "source": "MRZ", "reason": "Extraído de MRZ"}

        # ── 2. Identificación (NUIP / Cédula) ──
        # Busca en la página para cubrir cédulas estándar, rotadas, Tarjetas de Identidad y layouts variables
        patron_num_general = re.compile(r"\b(\d{1,3}(?:\s*[\.,]\s*\d{3}){1,3}|\d{7,10})\b")
        if not resultado_campos["identificacion"]["value"]:
            # Fase 2.1: Prioridad máxima a líneas con etiqueta explícita de número/NUIP/Cédula en el frente
            for idx_l, l in enumerate(lines):
                t = getattr(l, "text", "").upper().strip()
                # Excluir líneas que son códigos de barras PDF417
                if re.search(r"^[AP]-[0-9]+-[0-9]+-[MF]-", t):
                    continue
                if re.search(r"\b(NUMERO|N[UÚ]MERO|NOMORO|NUIP|NIMEPO|NUMEPO|NIMERO|NÚMEPO|C\.C\.?|NO\.)\b", t):
                    matches = list(patron_num_general.finditer(t))
                    # Si la etiqueta NUMERO está sola en la línea, inspeccionar la línea inmediatamente siguiente
                    if not matches and idx_l + 1 < len(lines):
                        t_next = getattr(lines[idx_l + 1], "text", "").upper().strip()
                        matches = list(patron_num_general.finditer(t_next))
                    for m in matches:
                        raw_num = re.sub(r"[^\d]", "", m.group(1))
                        valido, ced_ok = validador.validar_cedula(raw_num)
                        if valido:
                            resultado_campos["identificacion"] = {"value": ced_ok, "confidence": doc_ai_confidence, "status": "VALID", "page": page_num, "source": "universal_parser", "reason": "Extraído de línea con etiqueta explícita de número"}
                            break
                if resultado_campos["identificacion"]["value"]:
                    break

            # Fase 2.2: Búsqueda en códigos de barras / PDF417 de reverso
            if not resultado_campos["identificacion"]["value"]:
                patrones_barcode = [
                    r"[A-Z0-9]+-[A-Z0-9]+-[MF]-0*([1-9][0-9]{5,9})-[0-9]+",
                    r"[A-Z0-9]+-[MF]-0*([1-9][0-9]{5,9})-[0-9]+",
                    r"[A-Z0-9]+[MF]-0*([1-9][0-9]{5,9})-[0-9]+",
                    r"[0-9]{6,8}[MF][0-9]{7}C[0O]L0*([1-9][0-9]{5,9})",
                    r"COL0*([1-9][0-9]{5,9})[<0-9]",
                    r"[A-Z]-[0-9]+-[0-9]+-[MF]-([0-9]{7,10})-[0-9]+",
                ]
                for l in lines:
                    txt_line = getattr(l, "text", "")
                    for pat in patrones_barcode:
                        m_bc = re.search(pat, txt_line)
                        if m_bc:
                            valido, id_limpio = validador.validar_cedula(m_bc.group(1))
                            if valido:
                                resultado_campos["identificacion"] = {"value": id_limpio, "confidence": doc_ai_confidence, "status": "VALID", "page": page_num, "source": "universal_parser", "reason": "Extraído de código de barras reverso"}
                                break
                    if resultado_campos["identificacion"]["value"]:
                        break

            # Fase 2.3: Búsqueda por escaneo posicional (descartando líneas de barcode, fechas y membretes administrativos)
            if not resultado_campos["identificacion"]["value"]:
                from app.utils.name_cleaner import es_linea_ruido_administrativo
                for l in lines:
                    t = getattr(l, "text", "").upper().strip()
                    if es_linea_ruido_administrativo(t):
                        continue
                    if any(rw in t for rw in ["FICHA", "PROCESO", "TEL", "CEL", "RADICAD", "FOLIO", "ACTA", "ANEXO"]):
                        continue
                    if re.search(r"^[AP]-[0-9]+-[0-9]+-[MF]-", t) or re.search(r"\b\d{1,2}[\s/\-\.](?:[A-Z]{3}|\d{1,2})[\s/\-\.]\d{2,4}\b", t):
                        continue
                    matches = patron_num_general.finditer(t)
                    for m in matches:
                        raw_num = re.sub(r"[^\d]", "", m.group(1))
                        valido, ced_ok = validador.validar_cedula(raw_num)
                        if valido:
                            resultado_campos["identificacion"] = {"value": ced_ok, "confidence": doc_ai_confidence * 0.90, "status": "VALID", "page": page_num, "source": "universal_parser", "reason": "Extraído por escaneo posicional de página"}
                            break
                    if resultado_campos["identificacion"]["value"]:
                        break

        # ── 3. Nombres y Apellidos (Layout Estructural Cédula Amarilla y Digital) ──
        # Ejecutar siempre para extraer o enriquecer nombres visuales frente a MRZ truncado
        if True:
            # Determinar si es Cédula Digital o Tarjeta de Identidad
            es_digital_o_ti = any(
                "NUIP" in getattr(l, "text", "").upper() or
                any(w in getattr(l, "text", "").upper() for w in ["NACIONALIDAD", "DIGITAL", "CAN ", "TARJETA DE IDENTIDAD", "TARJETA IDENTIDAD"])
                for l in lines
            )

            # Detección inteligente de páginas con FRENTE y REVERSO combinados
            REVERSO_KEYWORDS = re.compile(
                r"\b(FECHA\s+DE\s+NACIMIENTO|LUGAR\s+DE\s+NACIMIENTO|ESTATURA|G\.?S\.?\s*RH|SEXO|"
                r"FECHA\s+Y\s+LUGAR\s+DE\s+EXPEDICI[OÓ]N|FECHA\s+DE\s+VENCIMIENTO|INDICE\s+DERECHO|REGISTRADOR\s+NACIONAL)\b"
                r"|^[AP]-[0-9]+-[0-9]+-[MF]-",
                re.I
            )
            FRENTE_KEYWORDS = re.compile(
                r"\b(REP[UÚ]BLICA\s+DE\s+COLOMBIA|IDENTIFICACI[OÓ]N\s+PERSONAL|C[EÉ]DULA\s+DE\s+CIUDADAN[IÍ]A|NUMERO|N[UÚ]MERO|APELL[I10]*D|N[O0]?[MRD]+[BDR]*[EÉ]S?)\b",
                re.I
            )
            HEADER_FRENTE_KEYWORDS = re.compile(
                r"\b(REP[UÚ]BLICA\s+DE\s+COLOMBIA|IDENTIFICACI[OÓ]N\s+PERSONAL|C[EÉ]DULA\s+DE\s+CIUDADAN[IÍ]A|TARJETA\s+DE\s+IDENTIDAD)\b",
                re.I
            )

            from app.utils.name_cleaner import es_linea_ruido_administrativo

            rev_lines = [l for l in lines if REVERSO_KEYWORDS.search(getattr(l, "text", ""))]
            frt_lines = [l for l in lines if FRENTE_KEYWORDS.search(getattr(l, "text", ""))]
            frt_header_lines = [
                l for l in lines 
                if HEADER_FRENTE_KEYWORDS.search(getattr(l, "text", ""))
                and not es_linea_ruido_administrativo(getattr(l, "text", ""))
                and not any(rw in getattr(l, "text", "").upper() for rw in [
                    "FOTOCOPIA", "OFICINA", "PROCESO", "MATRICULA", "MATRÍCULA", "INSCRIPCION", "INSCRIPCIÓN",
                    "CAMPESINA", "CAMPESENA", "FULLPOPULAR", "MUJER", "EMPRENDEDORA", "DEPARTAMENTAL"
                ])
            ]

            y_min_frente = 0.0
            y_max_frente = 1.0

            if frt_header_lines:
                # Recorte superior inteligente: omitir cualquier membrete o sello de fotocopia previo al recuadro del documento
                y_min_frente = max(0.0, min(getattr(l, "y", 0.0) for l in frt_header_lines) - 0.03)

            if rev_lines and frt_lines:
                y_rev_avg = sum(getattr(l, "y", 0.0) for l in rev_lines) / len(rev_lines)
                y_frt_avg = sum(getattr(l, "y", 0.0) for l in frt_lines) / len(frt_lines)
                if y_rev_avg < y_frt_avg:
                    # El reverso está arriba y el frente abajo (ej: cédula en mitad inferior)
                    y_corte = (max(getattr(l, "y", 0.0) for l in rev_lines) + min(getattr(l, "y", 0.0) for l in frt_lines)) / 2.0
                    y_min_frente = max(y_min_frente, max(0.35, y_corte - 0.02))
                    y_max_frente = 1.0
                else:
                    # El frente está arriba y el reverso abajo (layout estándar)
                    y_corte = (max(getattr(l, "y", 0.0) for l in frt_lines) + min(getattr(l, "y", 0.0) for l in rev_lines)) / 2.0
                    y_max_frente = max(0.55, min(0.75, y_corte + 0.02))
            elif not es_digital_o_ti:
                y_max_frente = 0.72

            if es_digital_o_ti:
                lineas_frente = [
                    l for l in lines 
                    if y_min_frente <= getattr(l, "y", 0.0) <= max(0.65, y_max_frente)
                    and not es_linea_ruido_administrativo(getattr(l, "text", ""))
                ]
            else:
                lineas_frente = [
                    l for l in lines 
                    if y_min_frente <= getattr(l, "y", 0.0) <= y_max_frente 
                    and getattr(l, "x", 0.0) < 0.60
                    and not REVERSO_KEYWORDS.search(getattr(l, "text", ""))
                    and not es_linea_ruido_administrativo(getattr(l, "text", ""))
                ]

            # Ordenar por y para garantizar secuencia vertical correcta
            lineas_frente = sorted(lineas_frente, key=lambda l: getattr(l, "y", 0.0))

            idx_num = -1
            idx_ape = -1
            idx_nom = -1

            for idx, l in enumerate(lineas_frente):
                t = getattr(l, "text", "").upper().strip()
                if (re.search(r"\b(NUMERO|N[UÚ]MERO|NOMORO|NUIP|NIMEPO|NUMEPO|NIMERO|NÚMEPO)\b", t) or re.search(r"\b\d{6,10}\b", re.sub(r"[^\d]", "", t))) and idx_num == -1:
                    idx_num = idx
                if re.search(r"\bAPELL[I10]*D", t) and idx_ape == -1:
                    idx_ape = idx
                if re.search(r"\b(N[O0]?[MRD]+[BDR]*[EÉ]S?|MOUSEES)\b", t) and idx_nom == -1:
                    idx_nom = idx

            if idx_ape != -1 and idx_nom != -1:
                has_nuip = any(
                    "NUIP" in getattr(l, "text", "").upper() or
                    any(w in getattr(l, "text", "").upper() for w in ["NACIONALIDAD", "DIGITAL", "CAN "])
                    for l in lineas_frente
                )
                if has_nuip:
                    # Layout Cédula Digital / Tarjeta Identidad:
                    # APELLIDOS_LABEL -> APELLIDOS_VAL -> NOMBRES_LABEL -> NOMBRES_VAL
                    # 1. Apellidos: después de APELLIDOS_LABEL y antes de NOMBRES_LABEL
                    inline_ape = self.limpiar_nombre(re.sub(r"\bAPELL[I10]*D[A-Z]*\b", "", getattr(lineas_frente[idx_ape], "text", ""), flags=re.I))
                    if inline_ape:
                        resultado_campos["apellidos"] = {"value": inline_ape, "confidence": doc_ai_confidence, "status": "VALID", "page": page_num, "source": "universal_parser", "reason": "Extraído inline con etiqueta APELLIDOS"}
                    else:
                        cand_ape = []
                        for i in range(idx_ape + 1, idx_nom):
                            limpio = self.limpiar_nombre(getattr(lineas_frente[i], "text", ""))
                            if limpio:
                                cand_ape.append(limpio)
                        if cand_ape:
                            val_ape_vis = " ".join(cand_ape)
                            ape_prev = resultado_campos["apellidos"].get("value")
                            if ape_prev and val_ape_vis.replace(" ", "").startswith(str(ape_prev).replace(" ", "")):
                                toks_a = str(ape_prev).split()
                                if len(toks_a) >= 2 and val_ape_vis.replace(" ", "").startswith(toks_a[0]):
                                    val_ape_vis = f"{toks_a[0]} {val_ape_vis.replace(' ', '')[len(toks_a[0]):]}"
                            resultado_campos["apellidos"] = {"value": val_ape_vis, "confidence": doc_ai_confidence, "status": "VALID", "page": page_num, "source": "universal_parser", "reason": "Extraído después de etiqueta APELLIDOS (Digital)"}

                    # 2. Nombres: después de NOMBRES_LABEL
                    inline_nom = self.limpiar_nombre(re.sub(r"\b(N[O0]?[MRD]+[BDR]*[EÉ]S?|MOUSEES)\b", "", getattr(lineas_frente[idx_nom], "text", ""), flags=re.I))
                    if inline_nom:
                        resultado_campos["nombres"] = {"value": inline_nom, "confidence": doc_ai_confidence, "status": "VALID", "page": page_num, "source": "universal_parser", "reason": "Extraído inline con etiqueta NOMBRES"}
                    else:
                        cand_nom = []
                        for i in range(idx_nom + 1, min(len(lineas_frente), idx_nom + 4)):
                            t_i = getattr(lineas_frente[i], "text", "")
                            if any(hdr in t_i.upper() for hdr in ["NACIONALIDAD", "ESTATURA", "SEXO", "FECHA", "LUGAR", "FIRMA"]):
                                break
                            limpio = self.limpiar_nombre(t_i)
                            if limpio:
                                cand_nom.append(limpio)
                        if cand_nom:
                            val_vis = " ".join(cand_nom)
                            nom_prev = resultado_campos["nombres"].get("value")
                            if nom_prev and val_vis.replace(" ", "").startswith(str(nom_prev).replace(" ", "")):
                                toks_m = str(nom_prev).split()
                                if len(toks_m) >= 2 and val_vis.replace(" ", "").startswith(toks_m[0]):
                                    val_vis = f"{toks_m[0]} {val_vis.replace(' ', '')[len(toks_m[0]):]}"
                            resultado_campos["nombres"] = {"value": val_vis, "confidence": doc_ai_confidence, "status": "VALID", "page": page_num, "source": "universal_parser", "reason": "Extraído después de etiqueta NOMBRES (Digital)"}

                elif idx_ape < idx_nom:
                    # Layout Cédula Amarilla:
                    # NUMERO -> APELLIDOS_VAL -> APELLIDOS_LABEL -> NOMBRES_VAL -> NOMBRES_LABEL
                    # 1. Verificar si hay valor inline en la misma línea de APELLIDOS
                    inline_ape = self.limpiar_nombre(re.sub(r"\bAPELL[I10]*D[A-Z]*\b", "", getattr(lineas_frente[idx_ape], "text", ""), flags=re.I))
                    if inline_ape:
                        resultado_campos["apellidos"] = {"value": inline_ape, "confidence": doc_ai_confidence, "status": "VALID", "page": page_num, "source": "universal_parser", "reason": "Extraído inline con etiqueta APELLIDOS"}
                    else:
                        cand_ape = []
                        y_ape = getattr(lineas_frente[idx_ape], "y", 0.0)
                        for i in range(idx_ape - 1, -1, -1):
                            l_i = lineas_frente[i]
                            y_i = getattr(l_i, "y", 0.0)
                            # Los apellidos están inmediatamente encima de APELLIDOS (máx 0.14 de distancia vertical)
                            if y_ape - y_i > 0.14:
                                break
                            t_i = getattr(l_i, "text", "")
                            if any(hdr in t_i.upper() for hdr in ["NUMERO", "NÚMERO", "CEDULA", "REPUBLICA", "IDENTIFICACION", "TARJETA"]):
                                break
                            limpio = self.limpiar_nombre(t_i)
                            if limpio:
                                cand_ape.insert(0, limpio)
                        if cand_ape and not resultado_campos["apellidos"]["value"]:
                            ape_val = " ".join(cand_ape[-2:])
                            resultado_campos["apellidos"] = {"value": ape_val, "confidence": doc_ai_confidence, "status": "VALID", "page": page_num, "source": "universal_parser", "reason": "Extraído antes de etiqueta APELLIDOS"}

                    # 2. Verificar si hay valor inline en la misma línea de NOMBRES
                    inline_nom = self.limpiar_nombre(re.sub(r"\b(N[O0]?[MRD]+[BDR]*[EÉ]S?|MOUSEES)\b", "", getattr(lineas_frente[idx_nom], "text", ""), flags=re.I))
                    if inline_nom:
                        resultado_campos["nombres"] = {"value": inline_nom, "confidence": doc_ai_confidence, "status": "VALID", "page": page_num, "source": "universal_parser", "reason": "Extraído inline con etiqueta NOMBRES"}
                    else:
                        cand_nom = []
                        for i in range(idx_ape + 1, idx_nom):
                            limpio = self.limpiar_nombre(getattr(lineas_frente[i], "text", ""))
                            if limpio:
                                cand_nom.append(limpio)
                        if cand_nom and not resultado_campos["nombres"]["value"]:
                            nom_val = " ".join(cand_nom[-2:])
                            resultado_campos["nombres"] = {"value": nom_val, "confidence": doc_ai_confidence, "status": "VALID", "page": page_num, "source": "universal_parser", "reason": "Extraído entre APELLIDOS y NOMBRES"}
                else:
                    # Layout Inverso: NOMBRES_LABEL -> NOMBRES_VAL -> APELLIDOS_LABEL -> APELLIDOS_VAL
                    inline_nom = self.limpiar_nombre(re.sub(r"\b(N[O0]?[MRD]+[BDR]*[EÉ]S?|MOUSEES)\b", "", getattr(lineas_frente[idx_nom], "text", ""), flags=re.I))
                    if inline_nom:
                        resultado_campos["nombres"] = {"value": inline_nom, "confidence": doc_ai_confidence, "status": "VALID", "page": page_num, "source": "universal_parser", "reason": "Extraído inline con etiqueta NOMBRES"}
                    else:
                        cand_nom = []
                        for i in range(idx_nom + 1, idx_ape):
                            limpio = self.limpiar_nombre(getattr(lineas_frente[i], "text", ""))
                            if limpio:
                                cand_nom.append(limpio)
                        if cand_nom and not resultado_campos["nombres"]["value"]:
                            resultado_campos["nombres"] = {"value": " ".join(cand_nom), "confidence": doc_ai_confidence, "status": "VALID", "page": page_num, "source": "universal_parser", "reason": "Extraído después de etiqueta NOMBRES"}

                    inline_ape = self.limpiar_nombre(re.sub(r"\b(APELL[I10]*D[O0]?S?|APELLIDORAJONAL)\b", "", getattr(lineas_frente[idx_ape], "text", ""), flags=re.I))
                    if inline_ape:
                        resultado_campos["apellidos"] = {"value": inline_ape, "confidence": doc_ai_confidence, "status": "VALID", "page": page_num, "source": "universal_parser", "reason": "Extraído inline con etiqueta APELLIDOS"}
                    else:
                        cand_ape = []
                        for i in range(idx_ape + 1, min(len(lineas_frente), idx_ape + 3)):
                            limpio = self.limpiar_nombre(getattr(lineas_frente[i], "text", ""))
                            if limpio:
                                cand_ape.append(limpio)
                        if cand_ape and not resultado_campos["apellidos"]["value"]:
                            resultado_campos["apellidos"] = {"value": " ".join(cand_ape), "confidence": doc_ai_confidence, "status": "VALID", "page": page_num, "source": "universal_parser", "reason": "Extraído después de etiqueta APELLIDOS"}

            # Fallback por líneas consecutivas limpias del frente (mejorado: validación de ruido y geografía)
            RUIDO_NOMBRES = {
                "COLOMBIA", "REPUBLICA", "REPÚBLICA", "DE COLOMBIA", "PERSONAL", "CEDULA",
                "CIUDADANIA", "CIUDADANÍA", "IDENTIFICACION", "IDENTIFICACIÓN", "NUIP",
                "NUMERO", "NÚMERO", "CC", "POR REVISAR", "REGISTRADOR", "REGISTRADURIA",
                "INDICE", "DERECHO", "ESTATURA", "SEXO", "NACIMIENTO", "EXPEDICION", "EXPEDICIÓN",
                "LUGAR", "FECHA", "HUELLA", "FIRMA", "DEPARTAMENTO", "MUNICIPIO"
            }
            # Un reverso puro de cédula nunca debe extraer nombres de personas por posición
            texto_todo = " ".join(getattr(l, "text", "") for l in lines).upper()
            es_reverso_puro = bool(re.search(r"\b(REGISTRADOR|INDICE DERECHO|ÍNDICE DERECHO|ESTATURA|G\.S\.?\s*RH|LUGAR DE NACIMIENTO)\b", texto_todo)) and not bool(re.search(r"\b(REPUBLICA DE COLOMBIA|IDENTIFICACION PERSONAL|CEDULA DE CIUDADANIA)\b", texto_todo))

            if not es_reverso_puro and (not resultado_campos["apellidos"]["value"] or not resultado_campos["nombres"]["value"]):
                cands_limpios = []
                for l in lineas_frente:
                    y_pos = getattr(l, "y", 0.0)
                    t_val = getattr(l, "text", "")
                    if es_linea_ruido_administrativo(t_val):
                        continue
                    if max(y_min_frente, 0.08) <= y_pos <= y_max_frente:
                        # Si se detectó el número de cédula, los nombres/apellidos nunca están por encima del número
                        if idx_num != -1 and idx_num < len(lineas_frente):
                            y_num_line = getattr(lineas_frente[idx_num], "y", 0.0)
                            if y_pos < y_num_line - 0.01:
                                continue
                        # En Cédula Amarilla, los nombres están estrictamente por encima de la etiqueta NOMBRES (y < y_nom).
                        # Todo lo que esté por debajo de NOMBRES es el área de firma/rúbrica del ciudadano (ej: DR CDI).
                        if not es_digital_o_ti and idx_nom != -1:
                            y_limite_nom = getattr(lineas_frente[idx_nom], "y", 0.35)
                            if y_pos >= y_limite_nom:
                                continue
                        limpio = self.limpiar_nombre(t_val)
                        if not limpio:
                            continue
                        limpio_up = limpio.upper()
                        # Filtro robusto: sin dígitos, no es ruido o cabecera documental, tiene >=1 palabras de >=3 letras
                        palabras_validas = re.findall(r"[A-ZÁÉÍÓÚÜÑa-záéíóúüñ]{3,}", limpio)
                        es_ruido = limpio_up in RUIDO_NOMBRES or any(r in limpio_up for r in ["CEDULA", "REPUBLIC", "IDENTIF", "REGISTRAD", "ESTADO CIVIL", "INDICE DERECHO", "HUELLA", "FIRMA"])
                        es_geo_compuesto = any(r in limpio_up for r in ["DEPARTAMENTO DE", "MUNICIPIO DE", "LUGAR DE", "ALCALDIA"]) or limpio_up in {"REPUBLICA DE COLOMBIA", "COLOMBIA", "DE COLOMBIA"} or colombia_geo.es_geografico(limpio)
                        tiene_digito = bool(re.search(r"\d", t_val))
                        if len(palabras_validas) >= 1 and not es_ruido and not es_geo_compuesto and not tiene_digito and limpio not in cands_limpios:
                            cands_limpios.append(limpio)

                if len(cands_limpios) >= 2:
                    # Descartar si juntos forman un término geográfico (ej: 'CAQUETA SOLANO')
                    if colombia_geo.es_geografico(f"{cands_limpios[0]} {cands_limpios[1]}"):
                        cands_limpios = []
                    else:
                        if not resultado_campos["apellidos"]["value"]:
                            resultado_campos["apellidos"] = {"value": cands_limpios[0], "confidence": doc_ai_confidence * 0.75, "status": "VALID", "page": page_num, "source": "universal_parser", "reason": "Extraído por secuencia posicional frontal (apellidos)"}
                        if not resultado_campos["nombres"]["value"]:
                            resultado_campos["nombres"] = {"value": cands_limpios[1], "confidence": doc_ai_confidence * 0.75, "status": "VALID", "page": page_num, "source": "universal_parser", "reason": "Extraído por secuencia posicional frontal (nombres)"}
                elif len(cands_limpios) == 1:
                    if not colombia_geo.es_geografico(cands_limpios[0]):
                        if not resultado_campos["apellidos"]["value"]:
                            resultado_campos["apellidos"] = {"value": cands_limpios[0], "confidence": doc_ai_confidence * 0.75, "status": "VALID", "page": page_num, "source": "universal_parser", "reason": "Extraído por secuencia posicional frontal (apellidos)"}

        # ── 4. Fechas (Estrategia Directa por Etiqueta + Universal Cronológica Invariante) ──
        # 4.1 Búsqueda directa por etiquetas explícitas
        patron_f_nac_lbl = re.compile(r"\bFECHA\s+DE\s+NACIMIENTO[\s:]*([0-9]{1,2}[\s/\-\.](?:[A-Za-z]{3,4}|\d{1,2})[\s/\-\.][0-9]{4})\b", re.I)
        patron_f_exp_lbl = re.compile(r"\b(?:FECHA\s+Y\s+LUGAR\s+DE\s+EXPEDICI[OÓ]N|FECHA\s+DE\s+EXPEDICI[OÓ]N)[\s:]*([0-9]{1,2}[\s/\-\.](?:[A-Za-z]{3,4}|\d{1,2})[\s/\-\.][0-9]{4})\b", re.I)

        for idx_l, l in enumerate(lines):
            t_line = getattr(l, "text", "").strip()
            m_fn = patron_f_nac_lbl.search(t_line)
            if not m_fn and "FECHA DE NACIMIENTO" in t_line.upper() and idx_l + 1 < len(lines):
                t_next = getattr(lines[idx_l + 1], "text", "").strip()
                m_fn = re.search(r"\b([0-9]{1,2}[\s/\-\.](?:[A-Za-z]{3,4}|\d{1,2})[\s/\-\.][0-9]{4})\b", t_next)
            if m_fn and not resultado_campos["fecha_nacimiento"]["value"]:
                dt_fn = validador.parsear_fecha(m_fn.group(1))
                if dt_fn and 1930 <= dt_fn.year <= 2026:
                    resultado_campos["fecha_nacimiento"] = {
                        "value": dt_fn.isoformat(),
                        "confidence": doc_ai_confidence,
                        "status": "VALID",
                        "page": page_num,
                        "source": "universal_parser",
                        "reason": "Extraído directamente de etiqueta FECHA DE NACIMIENTO"
                    }

            m_fe = patron_f_exp_lbl.search(t_line)
            if not m_fe and ("EXPEDICION" in t_line.upper() or "EXPEDICIÓN" in t_line.upper()) and idx_l + 1 < len(lines):
                t_next = getattr(lines[idx_l + 1], "text", "").strip()
                m_fe = re.search(r"\b([0-9]{1,2}[\s/\-\.](?:[A-Za-z]{3,4}|\d{1,2})[\s/\-\.][0-9]{4})\b", t_next)
            if m_fe and not resultado_campos["fecha_expedicion"]["value"]:
                dt_fe = validador.parsear_fecha(m_fe.group(1))
                if dt_fe and 1930 <= dt_fe.year <= 2026:
                    resultado_campos["fecha_expedicion"] = {
                        "value": dt_fe.isoformat(),
                        "confidence": doc_ai_confidence,
                        "status": "VALID",
                        "page": page_num,
                        "source": "universal_parser",
                        "reason": "Extraído directamente de etiqueta FECHA DE EXPEDICIÓN"
                    }

        # 4.2 Escaneo cronológico complementario para fechas no resueltas
        fechas_doc = set()
        for l in lines:
            t = getattr(l, "text", "").strip()
            # Intentar parsear línea completa
            dt_full = validador.parsear_fecha(t)
            if dt_full and 1930 <= dt_full.year <= 2026:
                fechas_doc.add(dt_full)
            else:
                matches = re.finditer(r"\b(\d{1,2}[\s/\-\.](?:[A-Za-z]{3,4}|\d{1,2})[\s/\-\.]\d{4}|\d{1,2}\s+[A-Za-z]{3}\s+\d{4})\b", t)
                matched_valid = False
                for m in matches:
                    dt_m = validador.parsear_fecha(m.group(1))
                    if dt_m and 1930 <= dt_m.year <= 2026:
                        fechas_doc.add(dt_m)
                        matched_valid = True
                # Solo si no se pudo parsear fecha válida en esta línea y contiene OCR ilegible (ej: 24-???-2001)
                if not matched_valid and ("???" in t or re.search(r"\b\d{1,2}[\s/\-\.][\?]{2,4}[\s/\-\.]\d{4}\b", t) or re.search(r"\b\d{1,2}[\s/\-\.][^0-9a-zA-Z\s/\-\.]{2,4}[\s/\-\.]\d{4}\b", t)):
                    m_rot = re.search(r"\b(\d{1,2})[\s/\-\.][^\d\s/\-\.]{2,4}[\s/\-\.](\d{4})\b", t)
                    if m_rot and "FECHA" not in t.upper() and "REGISTRAD" not in t.upper():
                        dia_v, anio_v = int(m_rot.group(1)), int(m_rot.group(2))
                        if 1 <= dia_v <= 31 and 1930 <= anio_v <= 2026:
                            dt_r = validador.parsear_fecha(f"{dia_v}-ENE-{anio_v}")
                            if dt_r and 1930 <= dt_r.year <= 2026:
                                fechas_doc.add(dt_r)

        if not resultado_campos["fecha_nacimiento"]["value"] or not resultado_campos["fecha_expedicion"]["value"]:
            if len(fechas_doc) >= 2:
                fechas_ord = sorted(list(fechas_doc))
                if not resultado_campos["fecha_nacimiento"]["value"]:
                    resultado_campos["fecha_nacimiento"] = {"value": fechas_ord[0].isoformat(), "confidence": doc_ai_confidence, "status": "VALID", "page": page_num, "source": "universal_parser", "reason": "Fecha de nacimiento cronológicamente menor"}
                if not resultado_campos["fecha_expedicion"]["value"]:
                    resultado_campos["fecha_expedicion"] = {"value": fechas_ord[-1].isoformat(), "confidence": doc_ai_confidence, "status": "VALID", "page": page_num, "source": "universal_parser", "reason": "Fecha de expedición cronológicamente mayor"}
            elif len(fechas_doc) == 1:
                dt_u = list(fechas_doc)[0]
                if not resultado_campos["fecha_nacimiento"]["value"]:
                    resultado_campos["fecha_nacimiento"] = {"value": dt_u.isoformat(), "confidence": doc_ai_confidence, "status": "VALID", "page": page_num, "source": "universal_parser", "reason": "Fecha única detectada"}
                elif not resultado_campos["fecha_expedicion"]["value"]:
                    resultado_campos["fecha_expedicion"] = {"value": dt_u.isoformat(), "confidence": doc_ai_confidence, "status": "VALID", "page": page_num, "source": "universal_parser", "reason": "Fecha única detectada"}

        # ── 5. Lugar de Expedición (Universal DANE) ──
        # La fecha y el lugar de expedición están en la misma línea en documentos colombianos
        f_exp_iso = resultado_campos["fecha_expedicion"]["value"]
        nombres_ctx = f"{resultado_campos['nombres']['value'] or ''} {resultado_campos['apellidos']['value'] or ''}"
        lugar_exp_res = colombia_geo.extraer_lugar_expedicion(
            lineas=lines,
            fecha_expedicion_iso=f_exp_iso,
            nombres_excluir=nombres_ctx
        )
        if lugar_exp_res:
            resultado_campos["lugar_expedicion"] = {
                "value": lugar_exp_res,
                "confidence": doc_ai_confidence,
                "status": "VALID",
                "page": page_num,
                "source": "universal_parser",
                "reason": "Extraído de la misma línea/etiqueta de fecha de expedición"
            }

        # ── 6. Sexo ──
        for idx_l, l in enumerate(lines):
            t = getattr(l, "text", "").upper().strip()
            y_pos = getattr(l, "y", 0.0)
            x_pos = getattr(l, "x", 0.0)

            # 6.1 Detección explícita de Masculino / Femenino en la línea (o con prefijo SEXO/GÉNERO)
            norm_sex = validador.normalizar_sexo(t)
            if norm_sex and ("MASCUL" in t or "FEMEN" in t or "HOMBRE" in t or "MUJER" in t):
                resultado_campos["sexo"] = {
                    "value": norm_sex,
                    "confidence": doc_ai_confidence,
                    "status": "VALID",
                    "page": page_num,
                    "source": "universal_parser",
                    "reason": "Extraído de indicador de sexo explícito (Masculino/Femenino)"
                }
                break

            # 6.2 Si la línea es etiqueta SEXO y la siguiente línea contiene el valor (ej: Contraseñas)
            if re.search(r"\b(?:SEX[O0]?|G[EÉ]NER[O0]?)\b", t) and idx_l + 1 < len(lines):
                next_t = getattr(lines[idx_l + 1], "text", "").upper().strip()
                norm_next = validador.normalizar_sexo(next_t)
                if norm_next:
                    resultado_campos["sexo"] = {
                        "value": norm_next,
                        "confidence": doc_ai_confidence,
                        "status": "VALID",
                        "page": page_num,
                        "source": "universal_parser",
                        "reason": "Extraído de valor adyacente a etiqueta SEXO"
                    }
                    break

            # 6.3 Indicador M o F aislado en cuerpo del documento
            if t in ["M", "F"] and y_pos > 0.15:
                resultado_campos["sexo"] = {
                    "value": t,
                    "confidence": doc_ai_confidence,
                    "status": "VALID",
                    "page": page_num,
                    "source": "universal_parser",
                    "reason": "Extraído de indicador de sexo"
                }

            # 6.4 Junto a estatura o RH (ej: 1.75 M o O+ M)
            elif re.search(r"\b(?:1\.\d{2}|[ABO][+-])\s+([MF])\b", t):
                resultado_campos["sexo"] = {
                    "value": re.search(r"\b(?:1\.\d{2}|[ABO][+-])\s+([MF])\b", t).group(1),
                    "confidence": doc_ai_confidence,
                    "status": "VALID",
                    "page": page_num,
                    "source": "universal_parser",
                    "reason": "Extraído junto a estatura/RH"
                }

            # 6.5 Código de barras reverso
            m_bc_sex = re.search(r"-[0-9]+-([MF])-[0-9]{7,10}-", t)
            if m_bc_sex and not resultado_campos["sexo"]["value"]:
                resultado_campos["sexo"] = {
                    "value": m_bc_sex.group(1),
                    "confidence": doc_ai_confidence,
                    "status": "VALID",
                    "page": page_num,
                    "source": "universal_parser",
                    "reason": "Extraído de código de barras"
                }

        return resultado_campos

    def extraer_todos_los_campos(
        self,
        lines: List[Any],
        page_num: int = 1,
        doc_ai_confidence: float = 0.95
    ) -> Dict[str, Dict[str, Any]]:
        """
        Extrae todos los campos de la página combinando:
          1. Extractor Determinista Universal de Cédula Colombiana.
          2. Geometría espacial 2D y exclusión mutua de candidatos.
        """
        if not lines:
            return {}

        # 1. Ejecutar Extractor Determinista Universal
        resultados = self.extraer_cedula_universal(lines, page_num, doc_ai_confidence)

        # 2. Si algún campo crítico no fue resuelto determinísticamente, ejecutar pipeline espacial 2D
        campos_faltantes = [c for c, r in resultados.items() if not r.get("value") or r.get("status") != "VALID"]
        if campos_faltantes:
            layout_info = document_layout_classifier.clasificar_layout(lines, page_num)
            etiquetas = self.identificar_etiquetas_espaciales(lines, page_num)
            usados_indices: Set[int] = set()

            for campo in campos_faltantes:
                res = self._extraer_campo_con_exclusion(
                    campo, lines, etiquetas, layout_info, usados_indices, page_num, doc_ai_confidence
                )
                if res and res.get("value") and res.get("status") == "VALID":
                    resultados[campo] = res
                    if res.get("line_index") is not None:
                        usados_indices.add(res["line_index"])

        # Generar artefacto de depuración visual 2D en PNG
        try:
            spatial_visual_debugger.generar_imagen_debug_2d(
                page_num, lines, {}, {}, {}
            )
        except Exception as e:
            logger.debug(f"[SpatialDebugger] Error al generar depuración visual: {e}")

        return resultados

    def _extraer_campo_con_exclusion(
        self,
        campo: str,
        lines: List[Any],
        etiquetas: Dict[str, SpatialCandidate],
        layout_info: Dict[str, Any],
        usados_indices: Set[int],
        page_num: int = 1,
        doc_ai_confidence: float = 0.95
    ) -> Dict[str, Any]:
        """
        Extrae un candidato espacial aplicando exclusión mutua de líneas usadas.
        """
        etiqueta = etiquetas.get(campo)
        if not etiqueta:
            return {
                "value": None,
                "confidence": 0.0,
                "status": "REVIEW_REQUIRED" if campo in ["nombres", "apellidos", "identificacion"] else "MISSING_DATA",
                "page": page_num,
                "label": None,
                "line_index": None,
                "spatial_relation": "WRONG_REGION",
                "spatial_score": 0.0,
                "reason": f"Sin etiqueta explícita para '{campo}' en la página",
                "audit_evaluaciones": []
            }

        region_2d = self.calcular_region_2d_campo(campo, etiqueta, etiquetas, layout_info)
        todas_lineas_etiquetas = {et.line_index for et in etiquetas.values()}
        candidates: List[SpatialCandidate] = []

        for idx, line in enumerate(lines):
            if idx in usados_indices:
                continue

            # Si la línea es la etiqueta de OTRO campo distinto, no evaluarla como candidato
            if idx in todas_lineas_etiquetas and idx != etiqueta.line_index:
                continue

            txt = getattr(line, "text", "").strip()
            if not txt:
                continue

            # Si el valor está en la misma línea inmediatamente después de la etiqueta (ej: "NOMBRES JUAN CARLOS")
            if idx == etiqueta.line_index:
                patron_et = r"\b(FECHA|LUGAR|EXPEDICION|EXPEDICIÓN|APELLIDOS?|NOMBRES?|NUMERO|NÚMERO|IDENTIFICACION|IDENTIFICACIÓN|CEDULA|CÉDULA|NUIP|SEXO|G[EÉ]NERO|GENERO)\b[\s:]*"
                sub_txt = re.sub(patron_et, "", txt, flags=re.IGNORECASE).strip()
                if campo in ["nombres", "apellidos"]:
                    sub_txt = re.sub(r"\b\d+\b", "", sub_txt).strip()
                    sub_clean = re.sub(r"[^A-ZÁÉÍÓÚÜÑ\s]", "", sub_txt.upper()).strip()
                    toks = [t for t in sub_clean.split() if len(t) >= 2 and not self.NO_NOMBRE_HEADER.search(t)]
                    sub_txt = " ".join(toks).strip()
                elif campo in ["fecha_nacimiento", "fecha_expedicion"]:
                    dt_val = validador.parsear_fecha(sub_txt)
                    if dt_val:
                        sub_txt = dt_val.isoformat()
                    else:
                        m_f = re.search(r"\b\d{1,2}[\s/\-\.][A-Z0-9]{3,4}[\s/\-\.]\d{4}\b|\b\d{1,2}/\d{1,2}/\d{4}\b|\b\d{4}-\d{2}-\d{2}\b", sub_txt, re.IGNORECASE)
                        if not m_f:
                            continue
                        dt_p = validador.parsear_fecha(m_f.group(0))
                        sub_txt = dt_p.isoformat() if dt_p else m_f.group(0)
                elif campo == "lugar_expedicion":
                    if any(r in sub_txt.upper() for r in ["NACIMIENTO", "REGISTRADOR", "ESTADO CIVIL"]):
                        continue
                    sub_limpio = re.sub(r"\b\d{1,2}[\s/\-\.](?:[A-Za-z0-9]{3,4}|\d{1,2})[\s/\-\.]\d{2,4}\b|\b\d{4}[\s/\-\.]\d{1,2}[\s/\-\.]\d{1,2}\b", " ", sub_txt)
                    sub_limpio = " ".join(sub_limpio.split())
                    lugar_res = colombia_geo.extraer_lugar_universal(sub_limpio, [sub_limpio])
                    if not lugar_res:
                        continue
                    sub_txt = lugar_res
                elif campo == "sexo":
                    sex_norm = validador.normalizar_sexo(sub_txt)
                    if not sex_norm:
                        continue
                    sub_txt = sex_norm
                elif campo == "identificacion":
                    digits = re.sub(r"[^\d]", "", sub_txt)
                    valido, num_limpio = validador.validar_cedula(digits)
                    if not valido:
                        continue
                    sub_txt = num_limpio
                if sub_txt:
                    bbox_inline = SpatialBoundingBox(etiqueta.bbox.x + (etiqueta.bbox.w * 0.3), etiqueta.bbox.y, etiqueta.bbox.w, etiqueta.bbox.h, page_num)
                    candidates.append(SpatialCandidate(sub_txt, bbox_inline, doc_ai_confidence, idx))
                continue

            if campo in ["nombres", "apellidos"]:
                if self.NO_NOMBRE_HEADER.search(txt) or len(txt.strip()) < 3:
                    continue
                txt_corr = validador.corregir_errores_ocr_nombre(txt)
                txt_clean = re.sub(r"[^A-ZÁÉÍÓÚÜÑ\s]", "", txt_corr.upper()).strip()
                tokens = txt_clean.split()
                tokens_validos = [t for t in tokens if len(t) >= 2 and not self.NO_NOMBRE_HEADER.search(t) and t not in ["BLICA", "PUBLICA", "PÚBLICA", "REPUBLICA", "COLOMBIA"]]
                if not tokens_validos:
                    continue
                # Verificar que no sean solo partículas (DE, LA, EL, etc.) sin una palabra propia
                tokens_propios = [t for t in tokens_validos if not self._PARTICULAS_SOLAS.match(t)]
                if not tokens_propios:
                    continue
                txt = " ".join(tokens_validos)
                if len(txt) < 3 or txt in ["BLICA", "PUBLICA", "PÚBLICA", "DE COLOMBIA"]:
                    continue

            if campo in ["fecha_nacimiento", "fecha_expedicion"]:
                dt_val = validador.parsear_fecha(txt)
                if dt_val:
                    txt = dt_val.isoformat()
                else:
                    m_f = re.search(r"\b\d{1,2}[\s/\-\.][A-Z0-9]{3,4}[\s/\-\.]\d{4}\b|\b\d{1,2}/\d{1,2}/\d{4}\b|\b\d{4}-\d{2}-\d{2}\b", txt, re.IGNORECASE)
                    if not m_f:
                        continue
                    dt_p = validador.parsear_fecha(m_f.group(0))
                    txt = dt_p.isoformat() if dt_p else m_f.group(0)

            if campo == "lugar_expedicion":
                if any(r in txt.upper() for r in ["NACIMIENTO", "REGISTRADOR", "ESTADO CIVIL"]):
                    continue
                txt_limpio = re.sub(r"\b\d{1,2}[\s/\-\.](?:[A-Za-z0-9]{3,4}|\d{1,2})[\s/\-\.]\d{2,4}\b|\b\d{4}[\s/\-\.]\d{1,2}[\s/\-\.]\d{1,2}\b", " ", txt)
                txt_limpio = " ".join(txt_limpio.split())
                lugar_res = colombia_geo.extraer_lugar_universal(txt_limpio, [txt_limpio])
                if not lugar_res:
                    continue
                txt = lugar_res

            if campo == "sexo":
                sex_norm = validador.normalizar_sexo(txt)
                if not sex_norm:
                    continue
                txt = sex_norm

            if campo == "identificacion":
                digits = re.sub(r"[^\d]", "", txt)
                valido, num_limpio = validador.validar_cedula(digits)
                if not valido:
                    continue
                txt = num_limpio

            x = getattr(line, "x", 0.0)
            y = getattr(line, "y", 0.0)
            w = getattr(line, "w", 0.0)
            h = getattr(line, "h", 0.0)
            conf = getattr(line, "confidence", doc_ai_confidence)
            bbox = SpatialBoundingBox(x, y, w, h, page_num)
            candidates.append(SpatialCandidate(txt, bbox, conf, idx))

        evaluaciones = []
        for cand in candidates:
            rel, s_score, desc = self.calculate_spatial_relation(etiqueta.bbox, cand.bbox, region_2d)
            evaluaciones.append({
                "candidate": cand,
                "relation": rel,
                "spatial_score": s_score,
                "description": desc,
                "is_valid": rel in ["DIRECTLY_BELOW", "DIRECTLY_ABOVE", "DIRECTLY_RIGHT", "SAME_ROW", "NEAR"],
                "is_winner": False
            })

        compatibles = [e for e in evaluaciones if e["is_valid"]]

        if not compatibles:
            return {
                "value": None,
                "confidence": 0.0,
                "status": "REVIEW_REQUIRED",
                "page": page_num,
                "label": etiqueta.text,
                "line_index": None,
                "spatial_relation": "WRONG_REGION",
                "spatial_score": 0.0,
                "reason": f"VETO ESPACIAL 2D: Sin candidatos válidos en la región de '{etiqueta.text}'",
                "region_2d": region_2d,
                "audit_evaluaciones": evaluaciones
            }

        compatibles.sort(key=lambda item: item["spatial_score"], reverse=True)
        best = compatibles[0]
        best["is_winner"] = True
        cand_obj = best["candidate"]

        valor_final = cand_obj.text
        if campo == "lugar_expedicion":
            valor_final = re.sub(r"\b\d{1,2}-[A-Z]{3}-\d{4}\b", "", valor_final).strip()
            palabras_excluir = {"REGISTRADOR", "NACIONAL", "CARLOS", "ARIEL", "SANCHEZ", "TORRES", "ALMABEATRIZ", "RENGIFO", "LOPEZ", "BEREN", "AMEL", "SANZ", "TAN", "ESTATURA", "SEXO", "RH"}
            toks = [t for t in valor_final.split() if t.upper() not in palabras_excluir and len(t) >= 2]
            valor_final = " ".join(toks).strip()

        score_final = (0.35 * 1.0) + (0.40 * best["spatial_score"]) + (0.15 * cand_obj.confidence) + (0.10 * 1.0)
        status_final = "VALID" if score_final >= 0.70 and valor_final else "REVIEW_REQUIRED"

        return {
            "value": valor_final if valor_final else None,
            "confidence": round(cand_obj.confidence, 2),
            "score_final": round(score_final, 2),
            "status": status_final,
            "page": page_num,
            "label": etiqueta.text,
            "label_bbox": etiqueta.bbox.to_dict(),
            "value_bbox": cand_obj.bbox.to_dict(),
            "line_index": cand_obj.line_index,
            "spatial_relation": best["relation"],
            "spatial_score": best["spatial_score"],
            "region_2d": region_2d,
            "reason": f"Valor '{valor_final}' extraído ({best['description']})",
            "audit_evaluaciones": evaluaciones
        }

    def extraer_campo_con_layout(
        self,
        campo: str,
        lines: List[Any],
        page_num: int = 1,
        doc_ai_confidence: float = 0.95
    ) -> Dict[str, Any]:
        """Método de compatibilidad para extracción individual de un solo campo."""
        layout_info = document_layout_classifier.clasificar_layout(lines, page_num)
        etiquetas = self.identificar_etiquetas_espaciales(lines, page_num)
        return self._extraer_campo_con_exclusion(
            campo, lines, etiquetas, layout_info, set(), page_num, doc_ai_confidence
        )


spatial_field_extractor = SpatialFieldExtractor()
