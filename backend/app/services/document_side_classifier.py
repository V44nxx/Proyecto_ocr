"""
Clasificador de Caras de Documentos (Frente / Reverso) para Cédulas y Tarjetas de Identidad Colombianas.
Determina: CEDULA_FRONT, CEDULA_BACK, TARJETA_IDENTIDAD_FRONT, TARJETA_IDENTIDAD_BACK, UNKNOWN.
Utiliza patrones estructurales, etiquetas características, MRZ, zonas de huella/firma y coordenadas normalizadas.
"""
import re
from typing import Dict, Any, List
from app.utils.logger import app_logger as logger


class DocumentSideClassifier:
    """
    Componente especializado para determinar la cara (Frente o Reverso) de una página de documento de identidad.
    """

    PATRONES_FRONT_CEDULA = [
        r"\bREPUBLICA DE COLOMBIA\b", r"\bREPÚBLICA DE COLOMBIA\b",
        r"\bCEDULA DE CIUDADANIA\b", r"\bCÉDULA DE CIUDADANÍA\b",
        r"\bIDENTIFICACION PERSONAL\b", r"\bIDENTIFICACIÓN PERSONAL\b",
        r"\bNOMBRES?\b", r"\bAPELLIDOS?\b",
        r"\bNUIP\b",
        # Patrones de texto OCR fusionado sin espacios (errores comunes de scanner)
        r"REPUBLICADE", r"REPUBLICA\s*DE\s*COLOM", r"REPUPLICADE", r"REPUBLICADECOLOMBIA",
        r"CEDULADECIUDADANIA", r"CEDULA\s*DE\s*CIUDAD", r"CEDUIA",
        r"IDENTIFICACIONPERSONAL", r"IDENTIFICACION\s*PERSONAL",
        r"COLOMBIAIDE", r"COLOMBLA", r"IDENTIFICACIONPERSONAI",
    ]

    PATRONES_BACK_CEDULA = [
        r"\bFECHA Y LUGAR DE EXPEDICION\b", r"\bFECHA DE EXPEDICION\b", r"\bLUGAR DE EXPEDICION\b",
        r"\bLUGAR DE NACIMIENTO\b",
        r"REGISTRADOR\s*NACIONAL", r"REGISTRADURIA\s*NACIONAL",
        r"I\s*C+C*[0O]L[A-Z0-9<]*", r"[0-9]{6}[0-9][MF][0-9]{6}", r"\bP[-<][0-9]{7}\b",
        r"\bINDICE DERECHO\b", r"\bÍNDICE DERECHO\b", r"\bESTATURA\b", r"\bG\.S\.?\s*RH\b",
        r"\bHUELLA\b", r"[A-Z0-9]+-[A-Z0-9]+-[MF]-[0-9]+", r"<{4,}"
    ]

    PATRONES_FRONT_TARJETA = [
        r"\bTARJETA DE IDENTIDAD\b", r"\bTARJETA IDENTIDAD\b",
        r"\bNOMBRES?\b", r"\bAPELLIDOS?\b", r"\bFECHA DE NACIMIENTO\b"
    ]

    PATRONES_BACK_TARJETA = [
        r"\bTARJETA DE IDENTIDAD\b", r"\bFECHA Y LUGAR DE EXPEDICION\b",
        r"\bREGISTRADOR\b", r"\bHUELLA\b"
    ]

    def clasificar_cara(self, texto: str, lines: List[Any] = None) -> Dict[str, Any]:
        """
        Clasifica la cara de la página y devuelve confianza + razones.
        """
        if not texto or len(texto.strip()) < 10:
            return {
                "cara": "UNKNOWN",
                "tipo_documento": "UNKNOWN",
                "confianza": 0.0,
                "reasons": ["Texto nulo o insuficiente"]
            }

        texto_up = texto.upper()
        reasons = []

        # Puntuaciones
        score_front_c = 0
        score_back_c = 0
        score_front_t = 0
        score_back_t = 0

        es_tarjeta = bool(
            re.search(
                r"\bTARJETA\s+(?:DE\s+)?(?:IDENTIDAD|IDENTIF[A-Z]*|IDENTID[A-Z0-9]*|DENTIDAD)\b|"
                r"\bTARJETADEIDENTIDAD\b|\bTARJETADE\s*IDENTIDAD\b|\bTARJETA\s*DEIDENTIDAD\b|"
                r"\bTARJETA\b|"
                r"\bT\.?\s*I\.?\b",
                texto_up
            )
            or (
                re.search(r"\bFECHA\s+DE\s+VENCIMIENTO\b", texto_up)
                and re.search(r"\bLUGAR\s+DE\s+NACIMIENTO\b", texto_up)
                and not re.search(r"I<COL|C<COL", texto_up)
            )
        )
        es_extranjeria = bool(re.search(r"\b(CEDULA\s+DE\s+EXTRANJERIA|CEDULA\s+EXTRANJERIA|EXTRANJERIA|C\.E\b|C\.E\.)\b", texto_up))
        es_pasaporte = bool(re.search(r"\b(PASAPORTE|PASSPORT)\b", texto_up))
        es_cedula_digital = "NUIP" in texto_up and not es_tarjeta

        es_cedula = bool(
            re.search(
                r"\b(CEDULA\s+DE\s+CIUDADAN[IÍ]A|C[EÉ]DULA\s+DE\s+CIUDADAN[IÍ]A|"
                r"C[EÉ]DULA\s+CIUDADAN[IÍ]A|CEDULADECIUDADANIA|"
                r"CEDULA|C[EÉ]DULA|CIUDADAN[IÍ]A|C\.C\.?\b)\b|"
                r"I<COL|C<COL",
                texto_up
            )
        )

        if es_tarjeta and not es_cedula:
            tipo_doc_base = "TARJETA_IDENTIDAD"
        elif es_tarjeta and es_cedula:
            if re.search(r"\bTARJETA\s+(?:DE\s+)?IDENTIDAD\b", texto_up):
                tipo_doc_base = "TARJETA_IDENTIDAD"
            elif re.search(r"\bC[EÉ]DULA\s+(?:DE\s+)?CIUDADAN[IÍ]A\b", texto_up):
                tipo_doc_base = "CEDULA_CIUDADANIA"
            else:
                tipo_doc_base = "TARJETA_IDENTIDAD"
        elif es_extranjeria:
            tipo_doc_base = "CEDULA_EXTRANJERIA"
        elif es_pasaporte:
            tipo_doc_base = "PASAPORTE"
        elif es_cedula:
            tipo_doc_base = "CEDULA_CIUDADANIA"
        else:
            tipo_doc_base = "TARJETA_IDENTIDAD" if es_tarjeta else "CEDULA_CIUDADANIA"

        # 1. Evaluar FRONT Cédula / Tarjeta (exclusivos del anverso)
        for pat in self.PATRONES_FRONT_CEDULA:
            if re.search(pat, texto_up):
                score_front_c += 2
                reasons.append(f"Patrón FRENTE detectado: '{pat}'")

        # 2. Evaluar BACK Cédula / Tarjeta (exclusivos del reverso)
        for pat in self.PATRONES_BACK_CEDULA:
            if re.search(pat, texto_up):
                # En Cédula Digital, Estatura, G.S. y Expedición están en el anverso/frente
                if es_cedula_digital and any(k in pat for k in ["ESTATURA", "G.S.", "EXPEDICION", "NACIMIENTO"]):
                    continue
                score_back_c += 3 if any(k in pat for k in ["C[0O]L", "REGISTRADOR", "INDICE DERECHO", "<{4,}", "[MF]"]) else 2
                reasons.append(f"Patrón REVERSO detectado: '{pat}'")

        # 3. Evaluar Tarjetas específicamente
        if es_tarjeta:
            if re.search(r"\b(NOMBRES?|APELLIDOS?|NUMERO|NUIP|NACIONALIDAD)\b", texto_up):
                score_front_t += 5
            if re.search(r"\b(EXPEDICI[OÓ]N|REGISTRADOR|INDICE\s+DERECHO|ÍNDICE\s+DERECHO|HUELLA|FECHA\s+DE\s+VENCIMIENTO|LUGAR\s+DE\s+NACIMIENTO|FECHA\s+DE\s+NACIMIENTO)\b", texto_up):
                score_back_t += 5

        # Detección estricta de 2 caras en 1 sola página:
        # Requiere marcadores fuertes de FRENTE y marcadores EXCLUSIVOS de REVERSO
        tiene_frente_fuerte = bool(re.search(
            r"\b(REPUBLICA DE COLOMBIA|REPÚBLICA DE COLOMBIA|CEDULA DE CIUDADANIA|CÉDULA DE CIUDADANÍA|"
            r"TARJETA DE IDENTIDAD|TARJETA IDENTIDAD|IDENTIFICACION PERSONAL|IDENTIFICACIÓN PERSONAL|"
            r"APELLIDOS|NOMBRES)\b"
            r"|REPUBLICADE|REPUBLICA\s*DE\s*COLOM|CEDULADECIUDADANIA|CEDULA\s*DE\s*CIUDAD"
            r"|IDENTIFICACIONPERSONAL|IDENTIFICACION\s*PERSONAL|COLOMBLA|COLOMBIAIDE",
            texto_up
        ))

        if es_cedula_digital:
            # En Cédula Digital, ESTATURA y G.S. están en el FRENTE.
            # Los marcadores exclusivos de REVERSO son el MRZ (I CC0L / chevrons) y REGISTRADOR NACIONAL
            tiene_reverso_exclusivo = bool(re.search(
                r"(REGISTRADOR\s*NACIONAL|REGISTRADURIA\s*NACIONAL|INDICE\s*DERECHO|ÍNDICE\s*DERECHO|HUELLA|I\s*C+C*[0O]L|<{4,})",
                texto_up
            ))
        else:
            tiene_reverso_exclusivo = bool(re.search(
                r"\b(REGISTRADOR\s*NACIONAL|REGISTRADURIA\s*NACIONAL|REGISTRADOR|INDICE\s+DERECHO|ÍNDICE\s+DERECHO|HUELLA|ESTATURA|G\.?S\.?\s*RH|ICCOL|"
                r"FECHA\s+Y\s+LUGAR\s+DE\s+EXPEDICI[OÓ]N|LUGAR\s+DE\s+NACIMIENTO|FECHA\s+DE\s+VENCIMIENTO|FECHA\s+DE\s+NACIMIENTO|"
                r"[0-9]\+?\s*RH|\bRH\s+[MF]\b)\b|<{4,}|[A-Z0-9]+-[A-Z0-9]+-[MF]-[0-9]+",
                texto_up
            ))

        if tiene_frente_fuerte and tiene_reverso_exclusivo:
            return {
                "cara": "CEDULA_AMBOS_LADOS",
                "tipo_documento": tipo_doc_base,
                "confianza": 0.99,
                "reasons": reasons + ["Página contiene Frente y Reverso simultáneamente (2 caras en 1 página)"]
            }

        if es_tarjeta:
            if score_back_t > score_front_t:
                return {
                    "cara": "TARJETA_IDENTIDAD_BACK",
                    "tipo_documento": "TARJETA_IDENTIDAD",
                    "confianza": 0.95,
                    "reasons": reasons
                }
            else:
                return {
                    "cara": "TARJETA_IDENTIDAD_FRONT",
                    "tipo_documento": "TARJETA_IDENTIDAD",
                    "confianza": 0.95,
                    "reasons": reasons
                }

        max_score = max(score_front_c, score_back_c)

        if max_score < 2:
            return {
                "cara": "UNKNOWN",
                "tipo_documento": "UNKNOWN",
                "confianza": 0.30,
                "reasons": reasons + ["Sin patrones suficientes para clasificar cara"]
            }

        if score_back_c > score_front_c:
            return {
                "cara": "CEDULA_BACK",
                "tipo_documento": tipo_doc_base,
                "confianza": round(min(0.99, 0.70 + (score_back_c * 0.05)), 2),
                "reasons": reasons
            }
        else:
            return {
                "cara": "CEDULA_FRONT",
                "tipo_documento": tipo_doc_base,
                "confianza": round(min(0.99, 0.70 + (score_front_c * 0.05)), 2),
                "reasons": reasons
            }


document_side_classifier = DocumentSideClassifier()
