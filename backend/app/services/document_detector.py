"""
Clasificador Multiseñal de Documentos de Identidad Colombiana.
Clasifica: CEDULA_CIUDADANIA, TARJETA_IDENTIDAD, UNKNOWN, NO_DOCUMENT.
Utiliza señales textuales, estructurales, densidad visual y relaciones espaciales.
"""
import re
from typing import Dict, Any, List
from app.utils.logger import app_logger as logger


class DocumentDetector:
    """
    Componente independiente para determinar con alta precisión si una región o página
    contiene una Cédula de Ciudadanía, Tarjeta de Identidad, otro documento o ninguno.
    """

    PATRONES_CEDULA = [
        r"\bREPUBLICA DE COLOMBIA\b", r"\bREPÚBLICA DE COLOMBIA\b",
        r"\bCEDULA DE CIUDADANIA\b", r"\bCÉDULA DE CIUDADANÍA\b",
        r"\bIDENTIFICACION PERSONAL\b", r"\bIDENTIFICACIÓN PERSONAL\b",
        r"\bNUIP\b"
    ]

    PATRONES_TARJETA = [
        r"\bTARJETA DE IDENTIDAD\b", r"\bTARJETA IDENTIDAD\b",
        r"\bTARJETA DE IDENTIF\b", r"\bT\.I\b"
    ]

    PATRONES_ETIQUETAS_CEDULA = [
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
        puntuacion_cedula = 0
        puntuacion_tarjeta = 0

        # 1. Señales de Encabezado Principal
        for pat in self.PATRONES_TARJETA:
            if re.search(pat, texto_up):
                puntuacion_tarjeta += 3
                evidencias.append(f"Etiqueta de Tarjeta de Identidad hallada: '{pat}'")

        for pat in self.PATRONES_CEDULA:
            if re.search(pat, texto_up):
                puntuacion_cedula += 2
                evidencias.append(f"Etiqueta de Cédula hallada: '{pat}'")

        # 2. Señales de Estructura de Campos Característicos
        etiquetas_halladas = 0
        for pat in self.PATRONES_ETIQUETAS_CEDULA:
            if re.search(pat, texto_up):
                etiquetas_halladas += 1

        if etiquetas_halladas >= 3:
            puntuacion_cedula += 3
            evidencias.append(f"Estructura característica colombiana hallada ({etiquetas_halladas} campos claves)")

        # 3. Presencia de número de identificación
        if re.search(r"\b(NUMERO|NÚMERO|NUIP|CEDULA|CÉDULA)\s*[\.:]*\s*[1-9][0-9\.\s]{5,12}\b", texto_up):
            puntuacion_cedula += 2
            evidencias.append("Número de identificación detectado")

        # Evaluación Final de Clasificación
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


document_detector = DocumentDetector()
