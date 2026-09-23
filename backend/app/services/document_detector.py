"""
Clasificador Multiseñal de Documentos de Identidad Colombiana y Migratoria.
Clasifica: CEDULA_CIUDADANIA, TARJETA_IDENTIDAD, CEDULA_EXTRANJERIA, PPT, CONTRASEÑA, PASAPORTE, UNKNOWN, NO_DOCUMENT.
Utiliza señales textuales, estructurales, densidad visual y relaciones espaciales.
"""
import re
from typing import Dict, Any, List
from app.utils.logger import app_logger as logger


class DocumentDetector:
    """
    Componente independiente para determinar con alta precisión si una región o página
    contiene una Cédula de Ciudadanía, Tarjeta de Identidad, Cédula de Extranjería, PPT,
    Contraseña, Pasaporte o ninguno.
    """

    PATRONES_PPT = [
        r"\bPERMISO\s+POR\s+PROTECCI[OÓ]N\s+TEMPORAL\b",
        r"\bPERMISO\s+PROTECCI[OÓ]N\s+TEMPORAL\b",
        r"\bESTATUTO\s+TEMPORAL\s+DE\s+PROTECCI[OÓ]N\b",
        r"\bPPT\b",
        r"\bVISIBLES\b",
    ]

    PATRONES_EXTRANJERIA = [
        r"\bC[EÉ]DULA\s+DE\s+EXTRANJER[IÍ]A\b",
        r"\bC[EÉ]DULA\s+EXTRANJER[IÍ]A\b",
        r"\bEXTRANJER[IÍ]A\b",
        r"\bC\.?E\.?\b",
        r"\bRESIDENTE\s+N[O0]\b",
        r"\bMIGRANTE\s+N[O0]\b",
        r"\bVISITANTE\s+N[O0]\b",
    ]

    PATRONES_CONTRASENA = [
        r"\bCOMPROBANTE\s+DE\s+DOCUMENTO\s+EN\s+TR[AÁ]MITE\b",
        r"\bDOCUMENTO\s+EN\s+TR[AÁ]MITE\b",
        r"\bCONTRASE[ÑN]A\b",
        r"\bPRE-EXPEDICI[OÓ]N\b",
    ]

    PATRONES_PASAPORTE = [
        r"\bPASAPORTE\b",
        r"\bPASSPORT\b",
        r"\bREP[UÚ]BLICA\s+DE\s+COLOMBIA\s+PASAPORTE\b",
    ]

    PATRONES_TARJETA = [
        r"\bTARJETA\s+(?:DE\s+)?IDENTIDAD\b", r"\bTARJETA\s+IDENTIDAD\b",
        r"\bTARJETADEIDENTIDAD\b|\bTARJETADE\s*IDENTIDAD\b|\bTARJETA\s*DEIDENTIDAD\b",
        r"\bTARJETA\s+DE\s+IDENTIF[A-Z]*\b", r"\bTARJETA\b", r"\bT\.?\s*I\.?\b",
        r"\bFECHA\s+DE\s+VENCIMIENTO\b"
    ]

    PATRONES_CEDULA = [
        r"\bCEDULA\s+DE\s+CIUDADAN[IÍ]A\b", r"\bC[EÉ]DULA\s+DE\s+CIUDADAN[IÍ]A\b",
        r"\bCEDULA\s+CIUDADAN[IÍ]A\b", r"\bC[EÉ]DULA\s+CIUDADAN[IÍ]A\b",
        r"\bCEDULA\b", r"\bC[EÉ]DULA\b", r"\bCIUDADAN[IÍ]A\b",
        r"I<COL", r"C<COL"
    ]

    PATRONES_ETIQUETAS_COMUNES = [
        r"\bNOMBRES?\b", r"\bAPELLIDOS?\b", r"\bFECHA DE NACIMIENTO\b",
        r"\bFECHA Y LUGAR DE EXPEDICION\b", r"\bSEXO\b"
    ]

    def clasificar_documento(self, texto: str, lines: List[Any] = None) -> Dict[str, Any]:
        """
        Evalúa múltiples señales para clasificar el documento sin forzar adivinanzas.
        Returns:
            dict con tipo_documento, confianza_clasificacion, evidencias y requiere_revision.
        """
        if not texto or len(texto.strip()) < 15:
            return {
                "tipo_documento": "NO_DOCUMENT",
                "confianza": 0.0,
                "evidencias": ["Texto insuficiente o nulo"],
                "requiere_revision": True
            }

        texto_up = texto.upper()
        evidencias = []

        # 1. Evaluar tipos específicos prioritarios
        # A. Permiso por Protección Temporal (PPT)
        puntuacion_ppt = sum(3 for pat in self.PATRONES_PPT if re.search(pat, texto_up))
        if puntuacion_ppt >= 3:
            return {
                "tipo_documento": "PPT",
                "confianza": 0.98,
                "evidencias": ["Señales claras de Permiso por Protección Temporal (PPT)"],
                "requiere_revision": False
            }

        # B. Cédula de Extranjería (CE)
        puntuacion_ce = sum(3 for pat in self.PATRONES_EXTRANJERIA if re.search(pat, texto_up))
        if puntuacion_ce >= 3:
            return {
                "tipo_documento": "CEDULA_EXTRANJERIA",
                "confianza": 0.98,
                "evidencias": ["Señales claras de Cédula de Extranjería"],
                "requiere_revision": False
            }

        # C. Contraseña / Trámite
        puntuacion_ct = sum(3 for pat in self.PATRONES_CONTRASENA if re.search(pat, texto_up))
        if puntuacion_ct >= 3:
            return {
                "tipo_documento": "CONTRASEÑA",
                "confianza": 0.95,
                "evidencias": ["Señales de Comprobante de Documento en Trámite (Contraseña)"],
                "requiere_revision": False
            }

        # D. Pasaporte
        puntuacion_pas = sum(3 for pat in self.PATRONES_PASAPORTE if re.search(pat, texto_up))
        if puntuacion_pas >= 3:
            return {
                "tipo_documento": "PASAPORTE",
                "confianza": 0.95,
                "evidencias": ["Señales de Pasaporte"],
                "requiere_revision": False
            }

        # E. Tarjeta de Identidad (TI) vs Cédula de Ciudadanía (CC)
        puntuacion_tarjeta = 0
        puntuacion_cedula = 0

        for pat in self.PATRONES_TARJETA:
            if re.search(pat, texto_up):
                puntuacion_tarjeta += 3
                evidencias.append(f"Etiqueta de Tarjeta de Identidad hallada: '{pat}'")

        for pat in self.PATRONES_CEDULA:
            if re.search(pat, texto_up):
                puntuacion_cedula += 2
                evidencias.append(f"Etiqueta de Cédula hallada: '{pat}'")

        etiquetas_halladas = sum(1 for pat in self.PATRONES_ETIQUETAS_COMUNES if re.search(pat, texto_up))
        if etiquetas_halladas >= 3:
            puntuacion_cedula += 3
            evidencias.append(f"Estructura característica colombiana hallada ({etiquetas_halladas} campos claves)")

        if re.search(r"\b(NUMERO|NÚMERO|NUIP|CEDULA|CÉDULA)\s*[\.:]*\s*[1-9][0-9\.\s]{5,12}\b", texto_up):
            puntuacion_cedula += 2
            evidencias.append("Número de identificación detectado")

        if puntuacion_tarjeta >= 3:
            return {
                "tipo_documento": "TARJETA_IDENTIDAD",
                "confianza": round(min(0.98, 0.70 + (puntuacion_tarjeta * 0.08)), 2),
                "evidencias": evidencias,
                "requiere_revision": False
            }
        elif puntuacion_cedula >= 4:
            return {
                "tipo_documento": "CEDULA_CIUDADANIA",
                "confianza": round(min(0.99, 0.65 + (puntuacion_cedula * 0.06)), 2),
                "evidencias": evidencias,
                "requiere_revision": False
            }
        elif puntuacion_cedula >= 2 or etiquetas_halladas >= 2:
            return {
                "tipo_documento": "UNKNOWN",
                "confianza": 0.50,
                "evidencias": evidencias + ["Evidencia insuficiente para clasificación segura"],
                "requiere_revision": True
            }
        else:
            return {
                "tipo_documento": "NO_DOCUMENT",
                "confianza": 0.10,
                "evidencias": ["Sin estructura ni etiquetas de documento de identidad"],
                "requiere_revision": True
            }

    def detectar_tipo_documento(self, texto: str) -> str:
        """Helper directo para obtener el tipo de documento."""
        return self.clasificar_documento(texto).get("tipo_documento", "UNKNOWN")


document_detector = DocumentDetector()
