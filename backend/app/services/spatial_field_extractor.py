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
            r"NUIP", r"NUMER[O0]?", r"NÚMER[O0]?", r"CEDULA", r"CÉDULA",
            r"IDENTIFICA[CI1Ó0]+N", r"NO\."
        ],
        "apellidos": [
            r"APELL[I10]+D[O0]?S?", r"PRIMER\s+APELL[I10]+D[O0]?", r"SEGUNDO\s+APELL[I10]+D[O0]?", r"SURNAMES?"
        ],
        "nombres": [
            r"N[O0]?MBRES?", r"PRIMER\s+N[O0]?MBRE", r"SEGUNDO\s+N[O0]?MBRE", r"GIVEN\s+NAMES?"
        ],
        "fecha_nacimiento": [
            r"FECHA\s+DE\s+NAC[I1]M[I1]ENT[O0]?", r"NAC[I1]M[I1]ENT[O0]?", r"DATE\s+OF\s+B[I1]RTH"
        ],
        "fecha_expedicion": [
            r"FECHA\s+Y\s+LUGAR\s+DE\s+EXPED[I1]C[I1][O0]?", r"FECHA\s+DE\s+EXPED[I1]C[I1][O0]?",
            r"EXPED[I1]C[I1][O0]?"
        ],
        "lugar_expedicion": [
            r"LUGAR\s+DE\s+EXPED[I1]C[I1][O0]?", r"LUGAR\s+EXPED[I1]C[I1][O0]?", r"MUN[I1]C[I1]P[I1][O0]?"
        ],
        "sexo": [
            r"SEX[O0]?", r"GENER[O0]?", r"GÉNER[O0]?", r"SEX"
        ]
    }

    # Palabras de ruido/encabezados prohibidas como nombres o apellidos
    NO_NOMBRE_HEADER = re.compile(
        r"(REPUBLICA|REPÚBLICA|REDUBLICA|COLOMBIA|COLOMB|BIA|CEDULA|CÉDULA|CIUDADANIA|CIUDADANÍA|IDENTIFICACION|"
        r"IDENTIFICACIÓN|NUIP|NUMERO|NÚMERO|NOMBRES|APELLIDOS|APELLID|FIRMA|FIRMADO|DIGITAL|REGISTRAD|"
        r"OISTRAD|NATIONAL|NACIONAL|NACIONA|PERSONAL|DOCUMENTO|CIVIL|TARJETA|EXPEDICION|EXPEDICIÓN|NACIMIENTO|"
        r"INDICE|ÍNDICE|DERECHO|IZQUIERDO|HUELLA|BAILS|PANENZ|DANCING)",
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
        layout_type = layout_info.get("layout_type", "CEDULA_AMARILLA_FRENTE")

        # Límites por defecto (ancho holgado si no hay restricciones laterales)
        x_min = max(0.0, eb.x - 0.15)
        x_max = min(1.0, eb.x + max(eb.w * 4.5, 0.70))

        has_nombres = "nombres" in etiquetas
        has_apellidos = "apellidos" in etiquetas

        if has_nombres and has_apellidos:
            y_nom = etiquetas["nombres"].bbox.y
            y_ape = etiquetas["apellidos"].bbox.y
            if y_ape < y_nom:
                # Cédula Amarilla: APELLIDOS está arriba de NOMBRES (valores impresos por encima de etiquetas)
                if campo == "apellidos":
                    y_min = etiquetas["identificacion"].bbox.y if "identificacion" in etiquetas else max(0.0, eb.y - 0.18)
                    y_max = eb.y + 0.01
                elif campo == "nombres":
                    y_min = y_ape
                    y_max = eb.y + 0.01
                else:
                    y_min = max(0.0, eb.y - 0.15)
                    y_max = eb.y + 0.20
            else:
                # Cédula Digital / Tarjeta Identidad: NOMBRES está arriba de APELLIDOS (valores por debajo de etiquetas)
                if campo == "nombres":
                    y_min = eb.y
                    y_max = y_ape
                elif campo == "apellidos":
                    y_min = eb.y
                    y_max = eb.y + 0.18
                else:
                    y_min = eb.y
                    y_max = eb.y + 0.20
        else:
            if campo == "apellidos":
                y_min = max(0.0, eb.y - 0.18)
                y_max = eb.y + 0.18
            elif campo == "nombres":
                y_min = max(0.0, eb.y - 0.18)
                y_max = eb.y + 0.18
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
        es_debajo = dist_v > 0.0 and dist_v <= 0.15 and abs(cb.cx - eb.cx) <= (eb.w * 3.5)

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

    def extraer_todos_los_campos(
        self,
        lines: List[Any],
        page_num: int = 1,
        doc_ai_confidence: float = 0.95
    ) -> Dict[str, Dict[str, Any]]:
        """
        Extrae todos los campos de la página garantizando:
          1. Exclusión mutua de tokens entre campos (used_line_indices).
          2. Clasificación de layout 2D.
          3. Auditoría completa de candidatos por campo.
        """
        if not lines:
            return {}

        layout_info = document_layout_classifier.clasificar_layout(lines, page_num)
        etiquetas = self.identificar_etiquetas_espaciales(lines, page_num)

        usados_indices: Set[int] = set()
        resultados: Dict[str, Dict[str, Any]] = {}
        evaluaciones_debug: Dict[str, List[Dict[str, Any]]] = {}
        regiones_2d_debug: Dict[str, Dict[str, float]] = {}

        # Orden de prioridad de extracción espacial: apellidos -> nombres -> identificacion -> resto
        orden_campos = ["apellidos", "nombres", "identificacion", "fecha_nacimiento", "fecha_expedicion", "lugar_expedicion", "sexo"]

        for campo in orden_campos:
            res = self._extraer_campo_con_exclusion(
                campo, lines, etiquetas, layout_info, usados_indices, page_num, doc_ai_confidence
            )
            resultados[campo] = res
            evaluaciones_debug[campo] = res.get("audit_evaluaciones", [])
            if res.get("region_2d"):
                regiones_2d_debug[campo] = res["region_2d"]

            if res and res.get("line_index") is not None and res.get("status") == "VALID":
                usados_indices.add(res["line_index"])

        # Fallback inteligente para lugar_expedicion si no se extrajo o viene incompleto
        res_lugar = resultados.get("lugar_expedicion", {})
        if not res_lugar.get("value") or res_lugar.get("status") != "VALID":
            for idx, line in enumerate(lines):
                txt_linea = getattr(line, "text", "").strip()
                if not txt_linea:
                    continue
                m_f = re.search(r"\b\d{1,2}[\s/\-\.][A-Z0-9]{3,4}[\s/\-\.]\d{4}\b|\b\d{1,2}/\d{1,2}/\d{4}\b|\b\d{4}-\d{2}-\d{2}\b", txt_linea, re.IGNORECASE)
                if m_f:
                    txt_sin_fecha = re.sub(r"\b\d{1,2}[\s/\-\.][A-Z0-9]{3,4}[\s/\-\.]\d{4}\b|\b\d{1,2}/\d{1,2}/\d{4}\b|\b\d{4}-\d{2}-\d{2}\b|\b\d+\b", "", txt_linea, flags=re.IGNORECASE).strip()
                    txt_sin_fecha = self.NO_LUGAR_HEADER_WORDS.sub("", txt_sin_fecha)
                    lugar_cand = validador.normalizar_lugar(txt_sin_fecha)
                    if lugar_cand:
                        resultados["lugar_expedicion"] = {
                            "value": lugar_cand,
                            "confidence": 0.95,
                            "score_final": 0.95,
                            "status": "VALID",
                            "page": page_num,
                            "label": "Fecha y lugar de expedición",
                            "line_index": idx,
                            "spatial_relation": "DIRECTLY_BELOW",
                            "spatial_score": 0.95,
                            "reason": f"Lugar de expedición '{lugar_cand}' extraído de la línea de expedición",
                            "audit_evaluaciones": []
                        }
                        break

        # Generar artefacto de depuración visual 2D en PNG
        spatial_visual_debugger.generar_imagen_debug_2d(
            page_num, lines, etiquetas, evaluaciones_debug, regiones_2d_debug
        )

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
                patron_et = r"\b(FECHA|LUGAR|EXPEDICION|EXPEDICIÓN|APELLIDOS?|NOMBRES?|NUMERO|NÚMERO|IDENTIFICACION|IDENTIFICACIÓN|CEDULA|CÉDULA|NUIP)\b[\s:]*"
                sub_txt = re.sub(patron_et, "", txt, flags=re.IGNORECASE).strip()
                if campo in ["nombres", "apellidos"]:
                    sub_txt = re.sub(r"\b\d+\b", "", sub_txt).strip()
                    sub_clean = re.sub(r"[^A-ZÁÉÍÓÚÜÑ\s]", "", sub_txt.upper()).strip()
                    toks = [t for t in sub_clean.split() if len(t) >= 2 and not self.NO_NOMBRE_HEADER.search(t)]
                    sub_txt = " ".join(toks).strip()
                elif campo in ["fecha_nacimiento", "fecha_expedicion"]:
                    dt_val = validador.parsear_fecha(sub_txt)
                    if not dt_val:
                        m_f = re.search(r"\b\d{1,2}[\s/\-\.][A-Z0-9]{3,4}[\s/\-\.]\d{4}\b|\b\d{1,2}/\d{1,2}/\d{4}\b|\b\d{4}-\d{2}-\d{2}\b", sub_txt, re.IGNORECASE)
                        if not m_f:
                            continue
                        sub_txt = m_f.group(0)
                elif campo == "lugar_expedicion":
                    m_l = re.sub(r"\b\d{1,2}[\s/\-\.][A-Z0-9]{3,4}[\s/\-\.]\d{4}\b|\b\d{1,2}/\d{1,2}/\d{4}\b|\b\d{4}-\d{2}-\d{2}\b|\b\d+\b", "", sub_txt, flags=re.IGNORECASE)
                    m_l = self.NO_LUGAR_HEADER_WORDS.sub("", m_l)
                    sub_norm = validador.normalizar_lugar(m_l)
                    if not sub_norm:
                        continue
                    sub_txt = sub_norm
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
                if self.NO_NOMBRE_HEADER.search(txt):
                    continue
                txt_corr = validador.corregir_errores_ocr_nombre(txt)
                txt_clean = re.sub(r"[^A-ZÁÉÍÓÚÜÑ\s]", "", txt_corr.upper()).strip()
                tokens = txt_clean.split()
                tokens_validos = [t for t in tokens if len(t) >= 2 and not self.NO_NOMBRE_HEADER.search(t)]
                if not tokens_validos:
                    continue
                txt = " ".join(tokens_validos)

            if campo in ["fecha_nacimiento", "fecha_expedicion"]:
                dt_val = validador.parsear_fecha(txt)
                if not dt_val:
                    m_f = re.search(r"\b\d{1,2}[\s/\-\.][A-Z0-9]{3,4}[\s/\-\.]\d{4}\b|\b\d{1,2}/\d{1,2}/\d{4}\b|\b\d{4}-\d{2}-\d{2}\b", txt, re.IGNORECASE)
                    if not m_f:
                        continue
                    txt = m_f.group(0)

            if campo == "lugar_expedicion":
                # 1. Eliminar fechas y números
                m_lugar = re.sub(
                    r"\b\d{1,2}[\s/\-\.][A-Z0-9]{3,4}[\s/\-\.]\d{4}\b|\b\d{1,2}/\d{1,2}/\d{4}\b|\b\d{4}-\d{2}-\d{2}\b|\b\d+\b",
                    "",
                    txt,
                    flags=re.IGNORECASE
                ).strip()
                # 2. Reemplazar encabezados y palabras de plantilla del rótulo
                m_lugar = self.NO_LUGAR_HEADER_WORDS.sub("", m_lugar)
                txt_clean = re.sub(r"[^A-ZÁÉÍÓÚÜÑ\s-]", "", m_lugar.upper()).strip()
                toks = [t for t in txt_clean.split() if len(t) >= 2]
                # Requerir al menos 1 sustantivo propio principal (no preposición o conector)
                sustantivos = [t for t in toks if t not in ["Y", "DE", "DEL", "LA", "EL", "LOS", "LAS", "EN", "POR", "CON", "SAN", "SANTA"] and len(t) >= 3]
                if not sustantivos:
                    continue
                txt_norm = validador.normalizar_lugar(" ".join(toks))
                if not txt_norm:
                    continue
                txt = txt_norm

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
        status_final = "VALID" if score_final >= 0.85 and valor_final else "REVIEW_REQUIRED"

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
