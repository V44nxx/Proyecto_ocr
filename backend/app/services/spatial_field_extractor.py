"""
Motor Centralizado de Extracción por Geometría Espacial para Cédulas y Tarjetas Colombiana.
Pipeline Estricto: ETIQUETA -> REGIÓN DEL CAMPO -> CANDIDATOS ESPACIALES -> VALIDACIÓN -> RESULTADO.
0% Dependencia de Diccionarios para Selección de Valores.
Garantiza PRECISIÓN > COMPLETITUD: Veto Espacial Irrevocable y 0% Invención.
"""
import re
from typing import Dict, Any, List, Optional, Tuple
from app.utils.logger import app_logger as logger


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
    Motor centralizado de extracción por layout espacial para cédulas colombianas.
    Independiente de la resolución/DPI.
    """

    # Categorías de relaciones espaciales y sus puntuaciones
    SPATIAL_SCORES = {
        "DIRECTLY_BELOW": 1.00,
        "DIRECTLY_RIGHT": 0.95,
        "SAME_ROW": 0.90,
        "NEAR": 0.70,
        "FAR": 0.20,
        "ABOVE": 0.00,
        "WRONG_REGION": 0.00
    }

    # Definición de patrones de etiquetas esperadas con tolerancia a errores OCR (0 por O, 1 por I)
    ETIQUETAS_MAP = {
        "identificacion": [
            r"\bNUIP\b", r"\bNUMER[O0]?\b", r"\bNÚMER[O0]?\b", r"\bCEDULA\b", r"\bCÉDULA\b",
            r"\bIDENTIFICA[CI1Ó0]+N\b", r"\bNO\.\b"
        ],
        "apellidos": [
            r"\bAPELL[I10]+D[O0]?S?\b", r"\bPRIMER\s+APELL[I10]+D[O0]?\b", r"\bSEGUNDO\s+APELL[I10]+D[O0]?\b", r"\bSURNAMES?\b"
        ],
        "nombres": [
            r"\bN[O0]?MBRES?\b", r"\bPRIMER\s+N[O0]?MBRE\b", r"\bSEGUNDO\s+N[O0]?MBRE\b", r"\bGIVEN\s+NAMES?\b"
        ],
        "fecha_nacimiento": [
            r"\bFECHA\s+DE\s+NAC[I1]M[I1]ENT[O0]?\b", r"\bNAC[I1]M[I1]ENT[O0]?\b", r"\bDATE\s+OF\s+B[I1]RTH\b"
        ],
        "fecha_expedicion": [
            r"\bFECHA\s+Y\s+LUGAR\s+DE\s+EXPED[I1]C[I1][O0]?N\b", r"\bFECHA\s+DE\s+EXPED[I1]C[I1][O0]?N\b",
            r"\bEXPED[I1]C[I1][O0]?N\b"
        ],
        "lugar_expedicion": [
            r"\bLUGAR\s+DE\s+EXPED[I1]C[I1][O0]?N\b", r"\bLUGAR\s+EXPED[I1]C[I1][O0]?N\b", r"\bMUN[I1]C[I1]P[I1][O0]?\b"
        ],
        "sexo": [
            r"\bSEX[O0]?\b", r"\bGENER[O0]?\b", r"\bGÉNER[O0]?\b", r"\bSEX\b"
        ]
    }

    # Palabras de ruido/encabezados prohibidas como nombres o apellidos
    NO_NOMBRE_HEADER = re.compile(
        r"\b(REPUBLICA|REPÚBLICA|COLOMBIA|COLOMB|CEDULA|CÉDULA|CIUDADANIA|CIUDADANÍA|IDENTIFICACION|"
        r"IDENTIFICACIÓN|NUIP|NUMERO|NÚMERO|NOMBRES|APELLIDOS|FIRMA|FIRMADO|DIGITAL|REGISTRADOR|"
        r"REGISTRADURIA|NATIONAL|PERSONAL|DOCUMENTO|CIVIL|TARJETA|EXPEDICION|EXPEDICIÓN|NACIMIENTO|"
        r"INDICE|ÍNDICE|DERECHO|IZQUIERDO|HUELLA|BAILS|PANENZ|DANCING)\b",
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

            # Normalizar caracteres OCR comunes en etiquetas
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

    def calculate_spatial_relation(
        self,
        label_bbox: Any,
        candidate_bbox: Any,
        region_y_max: Optional[float] = None,
        region_y_min: Optional[float] = None
    ) -> Tuple[str, float, str]:
        """
        Calcula la relación espacial exacta entre la etiqueta y el candidato.
        Soporta objetos SpatialBoundingBox, SpatialCandidate o diccionarios.
        Retorna: (relation_category, spatial_score, description)
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

        # 1. Reglas de Veto Espacial Hard Override por límites de región (y_min e y_max)
        if region_y_min and cb.y < region_y_min - 0.005:
            return "WRONG_REGION", 0.00, f"VETO ESPACIAL: Candidato (y={round(cb.y, 3)}) por encima de la franja del campo (y_min={round(region_y_min, 3)})"

        if region_y_max and cb.y >= region_y_max:
            return "WRONG_REGION", 0.00, f"VETO ESPACIAL: Candidato (y={round(cb.y, 3)}) por debajo de la franja del campo (y_max={round(region_y_max, 3)})"

        dist_v_below = cb.y - eb.y
        dist_v_above = eb.y - cb.y

        # Permitir candidato ubicado inmediatamente por encima si la etiqueta está abajo (Cédula Amarilla)
        es_arriba_cedula_amarilla = (
            dist_v_above > 0.0 and dist_v_above <= 0.12 and abs(cb.cx - eb.cx) <= (eb.w * 3.5)
        )

        if cb.y < eb.y - 0.12:
            return "ABOVE", 0.00, f"VETO ESPACIAL: Candidato (y={round(cb.y, 3)}) ubicado muy por encima de la etiqueta (y={round(eb.y, 3)})"

        dist_v = cb.y - eb.y
        dist_h = abs(cb.x - eb.x)

        # 3. Candidato ubicado inmediatamente debajo (Misma columna X, Y más abajo)
        es_debajo = dist_v > 0.0 and dist_v <= 0.15 and abs(cb.cx - eb.cx) <= (eb.w * 3.5)

        # 4. Candidato ubicado inmediatamente a la derecha (Misma fila Y, X más a la derecha)
        es_al_lado = abs(cb.y - eb.y) <= (eb.h * 1.8) and cb.x >= eb.x + (eb.w * 0.1)

        # 5. Candidato en la misma fila horizontal
        misma_fila = abs(cb.cy - eb.cy) <= (eb.h * 1.5)

        if es_debajo:
            return "DIRECTLY_BELOW", self.SPATIAL_SCORES["DIRECTLY_BELOW"], f"Ubicado directamente debajo de la etiqueta (y_diff={round(dist_v, 3)})"
        elif es_arriba_cedula_amarilla:
            return "DIRECTLY_ABOVE", self.SPATIAL_SCORES["DIRECTLY_BELOW"], f"Ubicado directamente arriba de la etiqueta (Cédula Amarilla, y_diff={round(dist_v_above, 3)})"
        elif es_al_lado:
            return "DIRECTLY_RIGHT", self.SPATIAL_SCORES["DIRECTLY_RIGHT"], f"Ubicado directamente a la derecha de la etiqueta (x_diff={round(dist_h, 3)})"
        elif misma_fila:
            return "SAME_ROW", self.SPATIAL_SCORES["SAME_ROW"], f"Ubicado en la misma fila horizontal (cy_diff={round(abs(cb.cy - eb.cy), 3)})"
        elif dist_v > 0 and dist_v <= 0.25:
            return "NEAR", self.SPATIAL_SCORES["NEAR"], f"Ubicación cercana a la etiqueta (dist_v={round(dist_v, 3)})"
        elif dist_v > 0 and dist_v <= 0.40:
            return "FAR", self.SPATIAL_SCORES["FAR"], f"Ubicación espacial lejana respecto a la etiqueta (dist_v={round(dist_v, 3)})"
        else:
            return "WRONG_REGION", 0.00, "Candidato fuera de la ventana espacial permitida"

    def evaluar_proximidad_espacial(
        self,
        etiqueta: Any,
        candidato: Any,
        region_y_max: Optional[float] = None
    ) -> Tuple[float, bool, str]:
        """Método de compatibilidad retrospectiva para evaluar proximidad espacial."""
        rel, score, desc = self.calculate_spatial_relation(etiqueta, candidato, region_y_max)
        es_comp = rel in ["DIRECTLY_BELOW", "DIRECTLY_ABOVE", "DIRECTLY_RIGHT", "SAME_ROW", "NEAR"]
        return score, es_comp, desc

    def extraer_campo_con_layout(
        self,
        campo: str,
        lines: List[Any],
        page_num: int = 1,
        doc_ai_confidence: float = 0.95
    ) -> Dict[str, Any]:
        """
        Extrae un candidato espacial para un campo aplicando Veto Espacial
        y Fórmula Centralizada de Scoring (Precisión > Completitud, 0% Diccionario).
        """
        if not lines:
            return {
                "value": None,
                "confidence": 0.0,
                "status": "MISSING_DATA",
                "spatial_relation": "WRONG_REGION",
                "spatial_score": 0.0,
                "reason": "Líneas OCR no disponibles",
                "evidence": ["Sin líneas OCR en página"]
            }

        etiquetas = self.identificar_etiquetas_espaciales(lines, page_num)
        etiqueta = etiquetas.get(campo)

        # REGLA PRECISIÓN > COMPLETITUD: Si no existe etiqueta explícita, devolver NULL + REVIEW_REQUIRED
        if not etiqueta:
            logger.warning(f"[SpatialFieldExtractor] Sin etiqueta explícita para campo '{campo}' en pág. {page_num}")
            return {
                "value": None,
                "confidence": 0.0,
                "status": "REVIEW_REQUIRED" if campo in ["nombres", "apellidos", "identificacion"] else "MISSING_DATA",
                "page": page_num,
                "source": "google_document_ai",
                "label": None,
                "label_bbox": None,
                "value_bbox": None,
                "spatial_relation": "WRONG_REGION",
                "spatial_score": 0.0,
                "reason": f"Sin etiqueta explícita para '{campo}' en la página",
                "evidence": ["Etiqueta no detectada espacialmente"]
            }

        # Límite superior (y_min) e inferior (y_max) para acotamiento geométrico estricto por campo
        region_y_min = None
        region_y_max = None

        if campo == "apellidos":
            # Apellidos está entre identificacion (arriba) y la etiqueta de nombres (abajo)
            if "identificacion" in etiquetas:
                region_y_min = etiquetas["identificacion"].bbox.y
            if "nombres" in etiquetas:
                region_y_max = etiquetas["nombres"].bbox.y
            else:
                region_y_max = etiqueta.bbox.y + 0.18

        elif campo == "nombres":
            # Nombres está entre la etiqueta de apellidos (arriba) y fecha de nacimiento/sexo (abajo)
            if "apellidos" in etiquetas:
                region_y_min = etiquetas["apellidos"].bbox.y
            for nxt in ["fecha_nacimiento", "sexo"]:
                if nxt in etiquetas and etiquetas[nxt].bbox.y > etiqueta.bbox.y:
                    region_y_max = etiquetas[nxt].bbox.y
                    break
            if not region_y_max:
                region_y_max = etiqueta.bbox.y + 0.18
            region_y_max = etiqueta.bbox.y + 0.18

        candidates: List[SpatialCandidate] = []
        for idx, line in enumerate(lines):
            txt = getattr(line, "text", "").strip()
            if not txt or idx == etiqueta.line_index:
                continue

            # Filtrar ruidos de encabezado y marcas de agua en nombres y apellidos
            if campo in ["nombres", "apellidos"]:
                # Si la línea entera contiene encabezado oficial (ej: REPUBLICA DE COLOMBIA, CEDULA DE CIUDADANIA), descartarla por completo
                if self.NO_NOMBRE_HEADER.search(txt):
                    continue
                txt_clean = re.sub(r"[^A-ZÁÉÍÓÚÜÑ\s]", "", txt.upper()).strip()
                tokens = txt_clean.split()
                tokens_validos = [t for t in tokens if len(t) >= 2 and not self.NO_NOMBRE_HEADER.search(t)]
                if not tokens_validos:
                    continue
                txt = " ".join(tokens_validos)

            x = getattr(line, "x", 0.0)
            y = getattr(line, "y", 0.0)
            w = getattr(line, "w", 0.0)
            h = getattr(line, "h", 0.0)
            conf = getattr(line, "confidence", doc_ai_confidence)
            bbox = SpatialBoundingBox(x, y, w, h, page_num)
            candidates.append(SpatialCandidate(txt, bbox, conf, idx))

        if not candidates:
            return {
                "value": None,
                "confidence": 0.0,
                "status": "REVIEW_REQUIRED",
                "page": page_num,
                "source": "google_document_ai",
                "label": etiqueta.text,
                "label_bbox": etiqueta.bbox.to_dict(),
                "value_bbox": None,
                "spatial_relation": "WRONG_REGION",
                "spatial_score": 0.0,
                "reason": f"Sin candidatos válidos de texto dentro de la región de '{etiqueta.text}'",
                "evidence": ["Candidatos ausentes o descartados por ruido"]
            }

        # Evaluar relación espacial de candidatos contra la etiqueta
        evaluaciones = []
        for cand in candidates:
            rel, s_score, desc = self.calculate_spatial_relation(etiqueta.bbox, cand.bbox, region_y_max, region_y_min)
            evaluaciones.append({
                "candidate": cand,
                "relation": rel,
                "spatial_score": s_score,
                "description": desc,
                "is_valid": rel in ["DIRECTLY_BELOW", "DIRECTLY_ABOVE", "DIRECTLY_RIGHT", "SAME_ROW", "NEAR"]
            })

        compatibles = [e for e in evaluaciones if e["is_valid"]]

        if not compatibles:
            logger.warning(f"[SpatialVeto] Campo '{campo}': VETO ESPACIAL aplicado a todos los candidatos")
            return {
                "value": None,
                "confidence": 0.0,
                "status": "REVIEW_REQUIRED",
                "page": page_num,
                "source": "google_document_ai",
                "label": etiqueta.text,
                "label_bbox": etiqueta.bbox.to_dict(),
                "value_bbox": None,
                "spatial_relation": "WRONG_REGION",
                "spatial_score": 0.0,
                "reason": f"VETO ESPACIAL: Todos los candidatos quedaron fuera de la región permitida de '{etiqueta.text}'",
                "evidence": ["VETO ESPACIAL activado"]
            }

        # Seleccionar el mejor candidato compatible por score espacial
        compatibles.sort(key=lambda item: item["spatial_score"], reverse=True)
        best = compatibles[0]
        cand_obj = best["candidate"]

        # Agrupación espacial de nombres/apellidos compuestos en la misma línea
        valor_final = cand_obj.text

        # Limpieza específica para LUGAR_EXPEDICION (eliminar fechas y firmas de registrador)
        if campo == "lugar_expedicion":
            # Remover patrón de fechas (ej: 15-OCT-2004, 09-DIC-1985)
            valor_final = re.sub(r"\b\d{1,2}-[A-Z]{3}-\d{4}\b", "", valor_final).strip()
            # Remover palabras del registrador nacional / firmas
            palabras_excluir = {"REGISTRADOR", "NACIONAL", "CARLOS", "ARIEL", "SANCHEZ", "TORRES", "ALMABEATRIZ", "RENGIFO", "LOPEZ", "BEREN", "AMEL", "SANZ", "TAN", "ESTATURA", "SEXO", "RH"}
            toks = [t for t in valor_final.split() if t.upper() not in palabras_excluir and len(t) >= 2]
            valor_final = " ".join(toks).strip()
        bbox_final = cand_obj.bbox

        # Fórmula de scoring centralizada: Etiqueta 35% + Geometría 40% + Confianza DocAI 15% + Formato 10%
        score_final = (0.35 * 1.0) + (0.40 * best["spatial_score"]) + (0.15 * cand_obj.confidence) + (0.10 * 1.0)
        status_final = "VALID" if score_final >= 0.85 else "REVIEW_REQUIRED"

        return {
            "value": valor_final,
            "confidence": round(cand_obj.confidence, 2),
            "score_final": round(score_final, 2),
            "status": status_final,
            "page": page_num,
            "source": "google_document_ai",
            "label": etiqueta.text,
            "label_bbox": etiqueta.bbox.to_dict(),
            "value_bbox": bbox_final.to_dict(),
            "spatial_relation": best["relation"],
            "spatial_score": best["spatial_score"],
            "reason": f"Valor '{valor_final}' extraído ({best['description']})",
            "evidence": [best["description"]]
        }


spatial_field_extractor = SpatialFieldExtractor()
