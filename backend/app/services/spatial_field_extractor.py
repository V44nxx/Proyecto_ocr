"""
Extractor Centralizado de Campos basado en Geometría y Layout Espacial.
Maneja coordenadas normalizadas (0.0 - 1.0) independientes de la resolución/DPI,
aplica la Regla de Veto Espacial y la Fórmula Centralizada de Scoring.
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

    # Definición de patrones de etiquetas esperadas
    ETIQUETAS_MAP = {
        "identificacion": [r"\bNUIP\b", r"\bNUMERO\b", r"\bNÚMERO\b", r"\bCEDULA\b", r"\bCÉDULA\b", r"\bIDENTIFICACION\b", r"\bIDENTIFICACIÓN\b"],
        "nombres": [r"\bNOMBRES?\b", r"\bPRIMER\s+NOMBRE\b", r"\bSEGUNDO\s+NOMBRE\b", r"\bGIVEN\s+NAMES?\b"],
        "apellidos": [r"\bAPELLIDOS?\b", r"\bPRIMER\s+APELLIDO\b", r"\bSEGUNDO\s+APELLIDO\b", r"\bSURNAMES?\b"],
        "fecha_nacimiento": [r"\bFECHA\s+DE\s+NACIMIENTO\b", r"\bNACIMIENTO\b", r"\bDATE\s+OF\s+BIRTH\b"],
        "fecha_expedicion": [r"\bFECHA\s+Y\s+LUGAR\s+DE\s+EXPEDICION\b", r"\bFECHA\s+DE\s+EXPEDICION\b", r"\bFECHA\s+EXPEDICION\b", r"\bEXPEDICIÓN\b"],
        "lugar_expedicion": [r"\bLUGAR\s+DE\s+EXPEDICION\b", r"\bLUGAR\s+EXPEDICION\b", r"\bMUNICIPIO\b"],
        "sexo": [r"\bSEXO\b", r"\bGENERO\b", r"\bGÉNERO\b", r"\bSEX\b"]
    }

    def __init__(self):
        pass

    def identificar_etiquetas_espaciales(self, lines: List[Any], page_num: int = 1) -> Dict[str, SpatialCandidate]:
        """
        Localiza las cajas delimitadoras de cada etiqueta explícita en la página.
        """
        etiquetas_encontradas = {}
        for idx, line in enumerate(lines):
            txt = getattr(line, "text", "").upper().strip()
            if not txt:
                continue

            x = getattr(line, "x", 0.0)
            y = getattr(line, "y", 0.0)
            w = getattr(line, "w", 0.0)
            h = getattr(line, "h", 0.0)
            conf = getattr(line, "confidence", 0.9)
            bbox = SpatialBoundingBox(x, y, w, h, page_num)

            for campo, patrones in self.ETIQUETAS_MAP.items():
                if campo not in etiquetas_encontradas:
                    for pat in patrones:
                        if re.search(pat, txt):
                            etiquetas_encontradas[campo] = SpatialCandidate(txt, bbox, conf, idx)
                            break

        return etiquetas_encontradas

    def evaluar_proximidad_espacial(
        self,
        etiqueta: SpatialCandidate,
        candidato: SpatialCandidate
    ) -> Tuple[float, bool, str]:
        """
        Calcula la puntuación espacial (0.0 - 1.0) y aplica la Regla de Veto Espacial.
        Retorna: (spatial_score, es_compatible, razon_evidencia)
        """
        eb = etiqueta.bbox
        cb = candidato.bbox

        # 1. Distancia vertical normalizada respecto al alto de línea
        dist_v = cb.y - eb.y
        dist_h = abs(cb.x - eb.x)

        # Regla de Veto: Si el candidato está arriba de la etiqueta (dist_v < -0.02) con diferencia significativa
        if cb.y < eb.y - 0.03:
            return 0.1, False, f"VETO ESPACIAL: Candidato ubicado por encima de la etiqueta {etiqueta.text}"

        # Candidato ubicado al lado derecho (Misma línea horizontal: dist_v pequeña)
        es_al_lado = abs(cb.y - eb.y) <= (eb.h * 1.8) and cb.x >= eb.x + (eb.w * 0.1)

        # Candidato ubicado inmediatamente debajo (Debajo en Y, solapamiento o alineado en X)
        es_debajo = dist_v > 0.0 and dist_v <= (eb.h * 4.5) and abs(cb.cx - eb.cx) <= (eb.w * 2.5)

        if es_al_lado:
            score = 1.0 if dist_h <= (eb.w * 2.0) else 0.85
            return score, True, f"Ubicado a la derecha de la etiqueta ({round(dist_h, 3)} rel)"
        elif es_debajo:
            score = 1.0 if dist_v <= (eb.h * 2.5) else 0.80
            return score, True, f"Ubicado inmediatamente debajo de la etiqueta ({round(dist_v, 3)} rel)"
        else:
            # Distancia lejana
            return 0.3, False, "Distancia espacial lejana respecto a la etiqueta"

    def extraer_campo_con_layout(
        self,
        campo: str,
        lines: List[Any],
        page_num: int = 1,
        doc_ai_confidence: float = 0.95
    ) -> Optional[Dict[str, Any]]:
        """
        Extrae un candidato espacial para un campo aplicando la regla de Veto Espacial
        y la Fórmula Centralizada de Scoring (Precisión > Completitud).
        """
        if not lines:
            return None

        etiquetas = self.identificar_etiquetas_espaciales(lines, page_num)
        etiqueta = etiquetas.get(campo)

        candidates: List[SpatialCandidate] = []
        for idx, line in enumerate(lines):
            txt = getattr(line, "text", "").strip()
            if not txt or (etiqueta and idx == etiqueta.line_index):
                continue
            x = getattr(line, "x", 0.0)
            y = getattr(line, "y", 0.0)
            w = getattr(line, "w", 0.0)
            h = getattr(line, "h", 0.0)
            conf = getattr(line, "confidence", doc_ai_confidence)
            bbox = SpatialBoundingBox(x, y, w, h, page_num)
            candidates.append(SpatialCandidate(txt, bbox, conf, idx))

        if not candidates:
            return None

        if not etiqueta:
            # Sin etiqueta explícita encontrada: Se asigna score_etiqueta = 0.4 y score_espacial = 0.5
            top_cand = candidates[0]
            return {
                "value": top_cand.text,
                "confidence": round(top_cand.confidence, 2),
                "spatial_score": 0.5,
                "label_score": 0.4,
                "bbox": top_cand.bbox.to_dict(),
                "evidence": ["Sin etiqueta explícita en página"],
                "spatial_veto": False
            }

        # Evaluar todos los candidatos contra la etiqueta
        evaluaciones = []
        for cand in candidates:
            s_score, es_comp, razon = self.evaluar_proximidad_espacial(etiqueta, cand)
            evaluaciones.append({
                "candidate": cand,
                "spatial_score": s_score,
                "is_compatible": es_comp,
                "reason": razon
            })

        # Filtrar candidatos compatibles según Veto Espacial
        compatibles = [e for e in evaluaciones if e["is_compatible"]]

        if not compatibles:
            # Aplicar VETO ESPACIAL: Ningún candidato está en la región correcta
            logger.warning(f"[SpatialVeto] Campo '{campo}': Ningún candidato respetó la región espacial de '{etiqueta.text}'")
            return {
                "value": None,
                "confidence": 0.0,
                "spatial_score": 0.1,
                "label_score": 1.0,
                "bbox": etiqueta.bbox.to_dict(),
                "evidence": ["VETO ESPACIAL: Candidatos fuera de la región del campo"],
                "spatial_veto": True
            }

        # Seleccionar el mejor candidato compatible por proximidad
        compatibles.sort(key=lambda item: item["spatial_score"], reverse=True)
        best = compatibles[0]
        cand_obj = best["candidate"]

        return {
            "value": cand_obj.text,
            "confidence": round(cand_obj.confidence, 2),
            "spatial_score": best["spatial_score"],
            "label_score": 1.0,
            "bbox": cand_obj.bbox.to_dict(),
            "evidence": [best["reason"]],
            "spatial_veto": False
        }


spatial_field_extractor = SpatialFieldExtractor()
