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
        tiene_ti = bool(re.search(r"\bTARJETA\s*(?:DE\s*)?IDENTIDAD\b|\bTARJETADEIDENTIDAD\b|\bTARJETA\b|\bT\.I\b", texto_completo))

        # 1. Permiso por Protección Temporal (PPT): Rótulos arriba, valores abajo
        tiene_ppt = bool(re.search(
            r"\bPERMISO\s+POR\s+PROTECCI[OÓ]N\s+TEMPORAL\b|\bPPT\b|\bMIGRACI[OÓ]N\s+COLOMBIA\b|\bVISIBLES\b",
            texto_completo
        ))
        if tiene_ppt:
            return {
                "layout_type": "PPT",
                "expected_direction": "VALUE_BELOW_LABEL",
                "confidence": 0.95,
                "reasons": ["Rótulos o señales de PPT (Permiso por Protección Temporal) detectados"]
            }

        # 2. Cédula de Extranjería: Rótulos arriba, valores abajo
        tiene_ce = bool(re.search(
            r"\bC[EÉ]DULA\s+DE\s+EXTRANJER[IÍ]A\b|\bCEDULA\s+DE\s+EXTRANJERIA\b|\bEXTRANJER[IÍ]A\b",
            texto_completo
        ))
        if tiene_ce:
            return {
                "layout_type": "CEDULA_EXTRANJERIA",
                "expected_direction": "VALUE_BELOW_LABEL",
                "confidence": 0.95,
                "reasons": ["Rótulos o señales de Cédula de Extranjería detectados"]
            }

        # 3. Contraseña (Comprobante en trámite): Rótulos arriba, valores abajo
        tiene_contrasena = bool(re.search(
            r"\bCOMPROBANTE\s+DE\s+DOCUMENTO\b|\bEN\s+TR[AÁ]MITE\b|\bCONTRASE[NÑ]A\b",
            texto_completo
        ))
        if tiene_contrasena:
            return {
                "layout_type": "CONTRASEÑA",
                "expected_direction": "VALUE_BELOW_LABEL",
                "confidence": 0.95,
                "reasons": ["Rótulos de Contraseña / Comprobante en trámite detectados"]
            }

        # 4. Pasaporte: Rótulos arriba, valores abajo
        tiene_pasaporte = bool(re.search(
            r"\bPASAPORTE\b|\bPASSPORT\b",
            texto_completo
        ))
        if tiene_pasaporte:
            return {
                "layout_type": "PASAPORTE",
                "expected_direction": "VALUE_BELOW_LABEL",
                "confidence": 0.95,
                "reasons": ["Rótulos de Pasaporte detectados"]
            }

        # 5. Cédula Digital (Policarbonato): Rótulos arriba, valores abajo
        tiene_cedula_digital = bool(re.search(
            r"\bC[EÉ]DULA\s+DIGITAL\b",
            texto_completo
        ))
        if tiene_cedula_digital:
            return {
                "layout_type": "CEDULA_DIGITAL",
                "expected_direction": "VALUE_BELOW_LABEL",
                "confidence": 0.95,
                "reasons": ["Rótulos de Cédula Digital detectados"]
            }

        # 6. Tarjeta de Identidad: evaluar antes de Cédula Amarilla
        if tiene_ti:
            return {
                "layout_type": "TARJETA_IDENTIDAD",
                "expected_direction": "VALUE_ABOVE_LABEL",
                "confidence": 0.95,
                "reasons": ["Encabezado o señales de Tarjeta de Identidad detectadas"]
            }

        # 7. Cédula Amarilla Frente: contiene APELLIDOS, NOMBRES e identificador de cédula de ciudadanía
        if (tiene_apellidos and tiene_nombres) or (tiene_cedula_amarilla_hdr and not tiene_reverso_exp):
            return {
                "layout_type": "CEDULA_AMARILLA_FRENTE",
                "expected_direction": "VALUE_ABOVE_LABEL",
                "confidence": 0.95,
                "reasons": ["Rótulos APELLIDOS/NOMBRES detectados en frente de Cédula Amarilla"]
            }

        # 8. Cédula Reverso: contiene FECHA Y LUGAR DE EXPEDICION o MRZ
        if tiene_reverso_exp or tiene_mrz:
            return {
                "layout_type": "CEDULA_REVERSO",
                "expected_direction": "VALUE_ABOVE_LABEL",
                "confidence": 0.95,
                "reasons": ["Rótulos o MRZ de reverso detectados"]
            }

        # Default fallback
        return {
            "layout_type": "UNKNOWN",
            "expected_direction": "VALUE_ABOVE_LABEL",
            "confidence": 0.50,
            "reasons": ["Layout no determinado con certeza, asumiendo Cédula Amarilla"]
        }


document_layout_classifier = DocumentLayoutClassifier()
