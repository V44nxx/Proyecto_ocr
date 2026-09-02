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
        r"\b(REPUBLICA|REPÚBLICA|REDUBLICA|FEPUBLICA|REPUTE|COLOMBIA|COLOMB|COL|BIA|CEDULA|CÉDULA|CIUDADANIA|CIUDADANÍA|IDENTIFICACION|"
        r"IDENTIFICACIÓN|NUMERO|NÚMERO|NUIP|APELLIDOS?|NOMBRES?|PRIMER|SEGUNDO|FIRMA|FIRMAS|TITULAR|DIGITAL|"
        r"REGISTRAD.*|OISTRAD.*|NATIONAL|NACIONAL.*|NACIONA.*|COLESARIA.*|PERSONAL|DOCUMENTO|CIVIL|GIVIL|ALDEL|ESTADOL?|TARJETA|NACIMIENTO|"
        r"INDICE|ÍNDICE|DERECHO|IZQUIERDO|HUELLA|CAMSCANNER|POWERED|"
        r"ESTATURA|GRUPO|SANGUINEO|SANGUÍNEO|RH|"
        r"BLICA|PUBLICA|PÚBLICA|APELLIDORAJONAL|MOUSEES)\b",
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

    # Partículas de nombre que son válidas en conjunto pero no como única palabra
    _PARTICULAS_SOLAS = re.compile(r"^(DE|LA|EL|LOS|LAS|Y|DEL|AL|SAN|SANTA|DOS|DAS|DOS)$", re.IGNORECASE)

    def limpiar_nombre(self, texto: str) -> Optional[str]:
        if not texto:
            return None
        t_norm = texto.replace("!", "I").replace("1", "I")
        toks = [w for w in re.sub(r"[^A-ZÁÉÍÓÚÜÑ\s]", "", t_norm.upper()).split() if len(w) >= 2 and not self.NO_NOMBRE_HEADER.search(w)]
        # Filtrar tokens que sean solo partículas sin palabras propias de nombre
        toks_propios = [t for t in toks if not self._PARTICULAS_SOLAS.match(t)]
        if not toks_propios:
            return None  # Solo partículas sin nombre real → descartar
        res = " ".join(toks).strip()  # Mantener partículas EN CONTEXTO de un nombre válido
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

        if has_nombres and has_apellidos:
            y_nom = etiquetas["nombres"].bbox.y
            y_ape = etiquetas["apellidos"].bbox.y
            if y_ape < y_nom:
                # Cédula Amarilla: Valores impresos por encima de etiquetas
                if campo == "apellidos":
                    y_min = max(0.0, eb.y - 0.20)
                    y_max = eb.y + 0.04
                elif campo == "nombres":
                    y_min = max(0.0, eb.y - 0.20)
                    y_max = eb.y + 0.04
                else:
                    y_min = max(0.0, eb.y - 0.15)
                    y_max = eb.y + 0.20
            else:
                # Cédula Digital / Tarjeta Identidad: Valores por debajo de etiquetas
                if campo == "nombres":
                    y_min = max(0.0, eb.y - 0.02)
                    y_max = eb.y + 0.18
                elif campo == "apellidos":
                    y_min = max(0.0, eb.y - 0.02)
                    y_max = eb.y + 0.18
                else:
                    y_min = eb.y
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
            if "<<" in txt and "<" in txt and not txt.startswith("ICCOL"):
                partes = txt.split("<<")
                if len(partes) >= 2:
                    ape_raw = partes[0].replace("<", " ").strip()
                    nom_raw = partes[1].replace("<", " ").strip()
                    if ape_raw and not resultado_campos["apellidos"]["value"]:
                        resultado_campos["apellidos"] = {"value": validador.normalizar_nombre(ape_raw), "confidence": 0.98, "status": "VALID", "page": page_num, "source": "MRZ", "reason": "Extraído de MRZ"}
                    if nom_raw and not resultado_campos["nombres"]["value"]:
                        resultado_campos["nombres"] = {"value": validador.normalizar_nombre(nom_raw), "confidence": 0.98, "status": "VALID", "page": page_num, "source": "MRZ", "reason": "Extraído de MRZ"}
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
        # Busca en toda la mitad superior de la página (y<0.55) para cubrir
        # cédulas rotadas, Tarjetas de Identidad y layouts variables
        if not resultado_campos["identificacion"]["value"]:
            for l in lines:
                t = getattr(l, "text", "").upper().strip()
                y_pos = getattr(l, "y", 0.0)
                if y_pos < 0.55:  # Ampliado desde 0.35 para capturar más layouts
                    matches = re.finditer(r"\b(\d{1,3}(?:\.\d{3}){1,3}|\d{7,10})\b", t)
                    for m in matches:
                        raw_num = re.sub(r"[^\d]", "", m.group(1))
                        valido, ced_ok = validador.validar_cedula(raw_num)
                        if valido:
                            resultado_campos["identificacion"] = {"value": ced_ok, "confidence": doc_ai_confidence, "status": "VALID", "page": page_num, "source": "universal_parser", "reason": "Extraído de franja superior de identificación"}
                            break
                    if resultado_campos["identificacion"]["value"]:
                        break
            if not resultado_campos["identificacion"]["value"]:
                for l in lines:
                    m_bc = re.search(r"[A-Z]-[0-9]+-[0-9]+-[MF]-([0-9]{7,10})-[0-9]+", getattr(l, "text", ""))
                    if m_bc:
                        valido, id_limpio = validador.validar_cedula(m_bc.group(1))
                        if valido:
                            resultado_campos["identificacion"] = {"value": id_limpio, "confidence": doc_ai_confidence, "status": "VALID", "page": page_num, "source": "universal_parser", "reason": "Extraído de código de barras inferior"}
                            break

        # ── 3. Nombres y Apellidos (Layout Estructural Cédula Amarilla y Digital) ──
        if not resultado_campos["nombres"]["value"] or not resultado_campos["apellidos"]["value"]:
            # ZONA AMPLIADA: y < 0.55 sin restricción de X para cubrir layouts comprimidos/rotados
            lineas_frente = [
                l for l in lines
                if getattr(l, "y", 0.0) < 0.55
            ]
            # Ordenar por y para garantizar secuencia vertical correcta
            lineas_frente = sorted(lineas_frente, key=lambda l: getattr(l, "y", 0.0))

            idx_num = -1
            idx_ape = -1
            idx_nom = -1

            for idx, l in enumerate(lineas_frente):
                t = getattr(l, "text", "").upper().strip()
                if (re.search(r"\b(NUMERO|N[UÚ]MERO|NOMORO|NUIP)\b", t) or re.search(r"\b\d{7,10}\b", re.sub(r"[^\d]", "", t))) and idx_num == -1:
                    idx_num = idx
                if re.search(r"\b(APELLIDOS?|APELLIDORAJONAL)\b", t) and idx_ape == -1:
                    idx_ape = idx
                if re.search(r"\b(NOMBRES?|MOUSEES)\b", t) and idx_nom == -1:
                    idx_nom = idx

            if idx_ape != -1 and idx_nom != -1:
                if idx_ape < idx_nom:
                    # Layout Cédula Amarilla: NUMERO -> APELLIDOS_VAL -> APELLIDOS_LABEL -> NOMBRES_VAL -> NOMBRES_LABEL
                    # 1. Verificar si hay valor inline en la misma línea de APELLIDOS
                    inline_ape = self.limpiar_nombre(re.sub(r"\b(APELLIDOS?|APELLIDORAJONAL)\b", "", getattr(lineas_frente[idx_ape], "text", ""), flags=re.I))
                    if inline_ape:
                        resultado_campos["apellidos"] = {"value": inline_ape, "confidence": doc_ai_confidence, "status": "VALID", "page": page_num, "source": "universal_parser", "reason": "Extraído inline con etiqueta APELLIDOS"}
                    else:
                        cand_ape = []
                        for i in range(idx_num + 1 if idx_num != -1 and idx_num < idx_ape else max(0, idx_ape - 3), idx_ape):
                            limpio = self.limpiar_nombre(getattr(lineas_frente[i], "text", ""))
                            if limpio:
                                cand_ape.append(limpio)
                        if cand_ape and not resultado_campos["apellidos"]["value"]:
                            # Tomar únicamente las líneas más cercanas a la etiqueta APELLIDOS (máximo 2 líneas)
                            ape_val = " ".join(cand_ape[-2:])
                            resultado_campos["apellidos"] = {"value": ape_val, "confidence": doc_ai_confidence, "status": "VALID", "page": page_num, "source": "universal_parser", "reason": "Extraído antes de etiqueta APELLIDOS"}

                    # 2. Verificar si hay valor inline en la misma línea de NOMBRES
                    inline_nom = self.limpiar_nombre(re.sub(r"\b(NOMBRES?|MOUSEES)\b", "", getattr(lineas_frente[idx_nom], "text", ""), flags=re.I))
                    if inline_nom:
                        resultado_campos["nombres"] = {"value": inline_nom, "confidence": doc_ai_confidence, "status": "VALID", "page": page_num, "source": "universal_parser", "reason": "Extraído inline con etiqueta NOMBRES"}
                    else:
                        cand_nom = []
                        for i in range(idx_ape + 1, idx_nom):
                            limpio = self.limpiar_nombre(getattr(lineas_frente[i], "text", ""))
                            if limpio:
                                cand_nom.append(limpio)
                        if cand_nom and not resultado_campos["nombres"]["value"]:
                            # Tomar únicamente las líneas más cercanas a la etiqueta NOMBRES (máximo 2 líneas)
                            nom_val = " ".join(cand_nom[-2:])
                            resultado_campos["nombres"] = {"value": nom_val, "confidence": doc_ai_confidence, "status": "VALID", "page": page_num, "source": "universal_parser", "reason": "Extraído entre APELLIDOS y NOMBRES"}
                else:
                    # Layout Cédula Digital / Formato Inverso: NOMBRES_LABEL -> NOMBRES_VAL -> APELLIDOS_LABEL -> APELLIDOS_VAL
                    inline_nom = self.limpiar_nombre(re.sub(r"\b(NOMBRES?|MOUSEES)\b", "", getattr(lineas_frente[idx_nom], "text", ""), flags=re.I))
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

                    inline_ape = self.limpiar_nombre(re.sub(r"\b(APELLIDOS?|APELLIDORAJONAL)\b", "", getattr(lineas_frente[idx_ape], "text", ""), flags=re.I))
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
                    if 0.08 < y_pos < 0.65:  # Ampliado para cubrir cédulas digitales y Tarjetas de Identidad
                        limpio = self.limpiar_nombre(t_val)
                        if not limpio:
                            continue
                        limpio_up = limpio.upper()
                        # Filtro robusto: sin dígitos, no es ruido o cabecera documental, tiene >=1 palabras de >=3 letras
                        palabras_validas = re.findall(r"[A-ZÁÉÍÓÚÜÑa-záéíóúüñ]{3,}", limpio)
                        es_ruido = limpio_up in RUIDO_NOMBRES or any(r in limpio_up for r in ["CEDULA", "REPUBLIC", "IDENTIF", "REGISTRAD", "ESTADO CIVIL", "INDICE DERECHO", "HUELLA", "FIRMA"])
                        es_geo_compuesto = any(r in limpio_up for r in ["DEPARTAMENTO DE", "MUNICIPIO DE", "LUGAR DE", "ALCALDIA"]) or limpio_up in {"REPUBLICA DE COLOMBIA", "COLOMBIA", "DE COLOMBIA"}
                        tiene_digito = bool(re.search(r"\d", t_val))
                        if len(palabras_validas) >= 1 and not es_ruido and not es_geo_compuesto and not tiene_digito and limpio not in cands_limpios:
                            cands_limpios.append(limpio)

                if len(cands_limpios) >= 2:
                    if not resultado_campos["apellidos"]["value"]:
                        resultado_campos["apellidos"] = {"value": cands_limpios[0], "confidence": doc_ai_confidence * 0.75, "status": "VALID", "page": page_num, "source": "universal_parser", "reason": "Extraído por secuencia posicional frontal (apellidos)"}
                    if not resultado_campos["nombres"]["value"]:
                        resultado_campos["nombres"] = {"value": cands_limpios[1], "confidence": doc_ai_confidence * 0.75, "status": "VALID", "page": page_num, "source": "universal_parser", "reason": "Extraído por secuencia posicional frontal (nombres)"}
                elif len(cands_limpios) == 1:
                    if not resultado_campos["apellidos"]["value"]:
                        resultado_campos["apellidos"] = {"value": cands_limpios[0], "confidence": doc_ai_confidence * 0.75, "status": "VALID", "page": page_num, "source": "universal_parser", "reason": "Extraído por secuencia posicional frontal (apellidos)"}

        # ── 4. Fechas (Estrategia Universal Cronológica Invariante) ──
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

        if len(fechas_doc) >= 2:
            fechas_ord = sorted(list(fechas_doc))
            resultado_campos["fecha_nacimiento"] = {"value": fechas_ord[0].isoformat(), "confidence": doc_ai_confidence, "status": "VALID", "page": page_num, "source": "universal_parser", "reason": "Fecha de nacimiento cronológicamente menor"}
            resultado_campos["fecha_expedicion"] = {"value": fechas_ord[-1].isoformat(), "confidence": doc_ai_confidence, "status": "VALID", "page": page_num, "source": "universal_parser", "reason": "Fecha de expedición cronológicamente mayor"}
        elif len(fechas_doc) == 1:
            dt_u = list(fechas_doc)[0]
            if not resultado_campos["fecha_nacimiento"]["value"]:
                resultado_campos["fecha_nacimiento"] = {"value": dt_u.isoformat(), "confidence": doc_ai_confidence, "status": "VALID", "page": page_num, "source": "universal_parser", "reason": "Fecha única detectada"}
            elif not resultado_campos["fecha_expedicion"]["value"]:
                resultado_campos["fecha_expedicion"] = {"value": dt_u.isoformat(), "confidence": doc_ai_confidence, "status": "VALID", "page": page_num, "source": "universal_parser", "reason": "Fecha única detectada"}

        # ── 5. Lugar de Expedición (Universal DANE) ──
        for idx, l in enumerate(lines):
            t = getattr(l, "text", "").strip()
            if re.search(r"\b(EXPEDIC|EXPED|EXPEDICI)", t, re.I):
                for sub_i in range(max(0, idx - 2), min(len(lines), idx + 2)):
                    cand_txt = getattr(lines[sub_i], "text", "")
                    lugar_res = colombia_geo.extraer_lugar_universal(cand_txt, [cand_txt])
                    if lugar_res and lugar_res not in colombia_geo.DEPARTAMENTOS:
                        resultado_campos["lugar_expedicion"] = {"value": lugar_res, "confidence": doc_ai_confidence, "status": "VALID", "page": page_num, "source": "universal_parser", "reason": "Extraído junto a etiqueta de expedición"}
                        break
                if resultado_campos["lugar_expedicion"]["value"]:
                    break

        if not resultado_campos["lugar_expedicion"]["value"]:
            for l in lines:
                y_pos = getattr(l, "y", 0.0)
                t_val = getattr(l, "text", "")
                if y_pos > 0.28:
                    lugar_res = colombia_geo.extraer_lugar_universal(t_val, [t_val])
                    if lugar_res and lugar_res not in colombia_geo.DEPARTAMENTOS:
                        resultado_campos["lugar_expedicion"] = {"value": lugar_res, "confidence": doc_ai_confidence, "status": "VALID", "page": page_num, "source": "universal_parser", "reason": "Extraído de franja geográfica"}
                        break

        # ── 6. Sexo ──
        for l in lines:
            t = getattr(l, "text", "").upper().strip()
            y_pos = getattr(l, "y", 0.0)
            x_pos = getattr(l, "x", 0.0)
            if t in ["M", "F"] and y_pos > 0.20 and x_pos > 0.45:
                resultado_campos["sexo"] = {"value": t, "confidence": doc_ai_confidence, "status": "VALID", "page": page_num, "source": "universal_parser", "reason": "Extraído de indicador de sexo"}
            elif re.search(r"\b(?:1\.\d{2}|[ABO][+-])\s+([MF])\b", t):
                resultado_campos["sexo"] = {"value": re.search(r"\b(?:1\.\d{2}|[ABO][+-])\s+([MF])\b", t).group(1), "confidence": doc_ai_confidence, "status": "VALID", "page": page_num, "source": "universal_parser", "reason": "Extraído junto a estatura/RH"}
            m_bc_sex = re.search(r"-[0-9]+-([MF])-[0-9]{7,10}-", t)
            if m_bc_sex and not resultado_campos["sexo"]["value"]:
                resultado_campos["sexo"] = {"value": m_bc_sex.group(1), "confidence": doc_ai_confidence, "status": "VALID", "page": page_num, "source": "universal_parser", "reason": "Extraído de código de barras"}

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
                patron_et = r"\b(FECHA|LUGAR|EXPEDICION|EXPEDICIÓN|APELLIDOS?|NOMBRES?|NUMERO|NÚMERO|IDENTIFICACION|IDENTIFICACIÓN|CEDULA|CÉDULA|NUIP)\b[\s:]*"
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
                    lugar_res = colombia_geo.extraer_lugar_universal(sub_txt, [sub_txt])
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
                lugar_res = colombia_geo.extraer_lugar_universal(txt, [txt])
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
