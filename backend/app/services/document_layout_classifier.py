"""
Clasificador de Layout Físico para Documentos de Identidad Colombianos.
Determina la estructura espacial exacta del documento (Cédula Amarilla, Cédula Digital, Reverso, Tarjeta de Identidad).
Define la dirección geométrica esperada entre rótulos y valores (VALUE_ABOVE_LABEL vs VALUE_BELOW_LABEL).
"""
import re
from typing import Dict, Any, List, Optional
from app.utils.logger import app_logger as logger


class DocumentLayoutClassifier:
    """
    Clasifica la estructura física de una página escaneada para guiar la extracción 2D.
    """

    def clasificar_layout(self, lines: List[Any], page_num: int = 1) -> Dict[str, Any]:
        """
        Determina el tipo de layout del documento y las direcciones esperadas para los valores.
        """
        if not lines:
            return {
                "layout_type": "UNKNOWN",
                "expected_direction": "VALUE_ABOVE_LABEL",
                "confidence": 0.0,
                "reasons": ["Página sin líneas OCR"]
            }

        texto_completo = " ".join([getattr(l, "text", "") for l in lines]).upper()

        tiene_apellidos = bool(re.search(r"\bAPELLIDOS?\b", texto_completo))
        tiene_nombres = bool(re.search(r"\bNOMBRES?\b", texto_completo))
        tiene_cedula_amarilla_hdr = bool(re.search(r"\bCEDULA\s+DE\s+CIUDADANIA\b|\bREP[UÚ]BLICA\s+DE\s+COLOMBIA\b", texto_completo))
        tiene_reverso_exp = bool(re.search(r"\bFECHA\s+Y\s+LUGAR\s+DE\s+EXPEDIC[I1][OÓ]N\b|\bFECHA\s+EXPEDIC[I1][OÓ]N\b", texto_completo))
        tiene_mrz = bool(re.search(r"I<COL|C<COL|PUBLICA", texto_completo))
        tiene_ti = bool(re.search(r"\bTARJETA\s+DE\s+IDENTIDAD\b|\bTARJETA\s+IDENTIDAD\b", texto_completo))

        # Cédula Amarilla Frente: contiene APELLIDOS, NOMBRES e identificador de cédula de ciudadanía
        if (tiene_apellidos and tiene_nombres) or (tiene_cedula_amarilla_hdr and not tiene_reverso_exp):
            return {
                "layout_type": "CEDULA_AMARILLA_FRENTE",
                "expected_direction": "VALUE_ABOVE_LABEL",
                "confidence": 0.95,
                "reasons": ["Rótulos APELLIDOS/NOMBRES detectados en frente de Cédula Amarilla"]
            }

        # Cédula Reverso: contiene FECHA Y LUGAR DE EXPEDICION o MRZ
        if tiene_reverso_exp or tiene_mrz:
            return {
                "layout_type": "CEDULA_REVERSO",
                "expected_direction": "VALUE_ABOVE_LABEL",
                "confidence": 0.95,
                "reasons": ["Rótulos o MRZ de reverso detectados"]
            }

        # Tarjeta de Identidad
        if tiene_ti:
            return {
                "layout_type": "TARJETA_IDENTIDAD",
                "expected_direction": "VALUE_BELOW_LABEL",
                "confidence": 0.90,
                "reasons": ["Encabezado de Tarjeta de Identidad detectado"]
            }

        # Default fallback
        return {
            "layout_type": "UNKNOWN",
            "expected_direction": "VALUE_ABOVE_LABEL",
            "confidence": 0.50,
            "reasons": ["Layout no determinado con certeza, asumiendo Cédula Amarilla"]
        }


document_layout_classifier = DocumentLayoutClassifier()
