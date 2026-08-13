"""
Servicio especializado de análisis de Nombres y Apellidos para Cédulas Colombianas.
Maneja diccionarios separadamente, n-gramas compuestos, scoring evidencial ponderado,
detección de duplicados, corrección fuzzy ponderada y conservación de palabras desconocidas.
"""
import json
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Set
from rapidfuzz import fuzz, process

from app.utils.logger import app_logger as logger


class NameDictionaryService:
    """
    Servicio de evidencia probabilística de nombres y apellidos.
    NO impone listas blancas ni reglas absolutas: proporciona evidencia y puntuaciones ponderadas.
    """

    # Configuración de pesos centralizada (Suma = 1.00)
    PESOS_SCORING = {
        "etiqueta_explicita": 0.40,
        "posicion_espacial": 0.30,
        "confianza_doc_ai": 0.15,
        "coincidencia_diccionario": 0.10,
        "similitud_fuzzy": 0.05,
    }

    # Umbrales de decisión
    UMBRAL_ALTO_VALIDO = 0.75
    UMBRAL_BAJO_MISSING = 0.30
    MARGEN_DIFERENCIA_AMBIGÜEDAD = 0.08

    def __init__(self, data_dir: Optional[Path] = None):
        if data_dir is None:
            # Buscar backend/app/data/dictionaries
            base = Path(__file__).resolve().parent.parent / "data" / "dictionaries"
        else:
            base = data_dir
        
        self.base_dir = base
        self.nombres: Set[str] = set()
        self.nombres_compuestos: List[str] = []
        self.nombres_variantes: Dict[str, List[str]] = {}
        
        self.apellidos: Set[str] = set()
        self.apellidos_compuestos: List[str] = []
        self.apellidos_variantes: Dict[str, List[str]] = {}
        
        self.errores_ocr_nombres: Dict[str, str] = {}
        self.errores_ocr_apellidos: Dict[str, str] = {}

        self._cargar_diccionarios()

    def _cargar_diccionarios(self):
        """Carga de archivos JSON categorizados por separado"""
        try:
            # Nombres
            f_nom = self.base_dir / "nombres" / "nombres_frecuentes.json"
            if f_nom.exists():
                with open(f_nom, "r", encoding="utf-8") as f:
                    self.nombres = set(json.load(f).get("nombres", []))
            
            f_nom_comp = self.base_dir / "nombres" / "nombres_compuestos.json"
            if f_nom_comp.exists():
                with open(f_nom_comp, "r", encoding="utf-8") as f:
                    self.nombres_compuestos = json.load(f).get("compuestos", [])

            f_nom_var = self.base_dir / "nombres" / "nombres_variantes.json"
            if f_nom_var.exists():
                with open(f_nom_var, "r", encoding="utf-8") as f:
                    self.nombres_variantes = json.load(f).get("variantes", {})

            # Apellidos
            f_ape = self.base_dir / "apellidos" / "apellidos_colombianos.json"
            if f_ape.exists():
                with open(f_ape, "r", encoding="utf-8") as f:
                    self.apellidos = set(json.load(f).get("apellidos", []))

            f_ape_comp = self.base_dir / "apellidos" / "apellidos_compuestos.json"
            if f_ape_comp.exists():
                with open(f_ape_comp, "r", encoding="utf-8") as f:
                    self.apellidos_compuestos = json.load(f).get("compuestos", [])

            f_ape_var = self.base_dir / "apellidos" / "apellidos_variantes.json"
            if f_ape_var.exists():
                with open(f_ape_var, "r", encoding="utf-8") as f:
                    self.apellidos_variantes = json.load(f).get("variantes", {})

            # OCR
            f_ocr_nom = self.base_dir / "ocr" / "errores_nombres.json"
            if f_ocr_nom.exists():
                with open(f_ocr_nom, "r", encoding="utf-8") as f:
                    self.errores_ocr_nombres = json.load(f).get("errores", {})

            f_ocr_ape = self.base_dir / "ocr" / "errores_apellidos.json"
            if f_ocr_ape.exists():
                with open(f_ocr_ape, "r", encoding="utf-8") as f:
                    self.errores_ocr_apellidos = json.load(f).get("errores", {})

            logger.info(
                f"[NameDictionaryService] Cargados {len(self.nombres)} nombres, "
                f"{len(self.apellidos)} apellidos y {len(self.nombres_compuestos)} compuestos."
            )
        except Exception as e:
            logger.warning(f"[NameDictionaryService] Advertencia al cargar diccionarios: {e}")

    def normalizar_para_comparacion(self, texto: str) -> str:
        """
        Normaliza a mayúsculas sin tildes ni caracteres extraños para comparación interna,
        reemplazando dígitos OCR comunes dentro de palabras y preservando el texto original.
        """
        if not texto:
            return ""
        s = texto.strip().upper()
        # Reemplazar dígitos OCR típicos en palabras
        s = re.sub(r"(?<=[A-Z])0(?=[A-Z]|$)", "O", s)
        s = re.sub(r"(?<=[A-Z])1(?=[A-Z]|$)", "I", s)
        s = re.sub(r"(?<=[A-Z])2(?=[A-Z]|$)", "Z", s)
        s = re.sub(r"(?<=[A-Z])4(?=[A-Z]|$)", "A", s)
        s = re.sub(r"(?<=[A-Z])5(?=[A-Z]|$)", "S", s)

        s = re.sub(r"[ÁÀÄÂ]", "A", s)
        s = re.sub(r"[ÉÈËÊ]", "E", s)
        s = re.sub(r"[ÍÌÏÎ]", "I", s)
        s = re.sub(r"[ÓÒÖÔ]", "O", s)
        s = re.sub(r"[ÚÙÜÛ]", "U", s)
        s = re.sub(r"[^A-ZÑ\s]", "", s)
        s = re.sub(r"\s+", " ", s)
        return s.strip()

    def evaluar_palabra(self, palabra_raw: str) -> Dict[str, Any]:
        """
        Proporciona evidencia probabilística para una palabra individual.
        NO decide si es nombre o apellido; retorna puntuaciones de evidencia y coincidencias.
        """
        palabra_norm = self.normalizar_para_comparacion(palabra_raw)
        if not palabra_norm:
            return {
                "text": palabra_raw,
                "nombre_score": 0.0,
                "apellido_score": 0.0,
                "dictionary_match": False,
                "fuzzy_match": False,
                "matched_value": None,
                "evidence": ["empty_string"]
            }

        evidencias = []
        nombre_score = 0.0
        apellido_score = 0.0
        matched_val = palabra_norm
        is_fuzzy = False

        # 1. Búsqueda directa en errores OCR conocidos
        if palabra_norm in self.errores_ocr_nombres or palabra_raw in self.errores_ocr_nombres:
            matched_val = self.errores_ocr_nombres.get(palabra_norm) or self.errores_ocr_nombres.get(palabra_raw)
            nombre_score = 0.95
            evidencias.append(f"ocr_error_map_name -> {matched_val}")
        if palabra_norm in self.errores_ocr_apellidos or palabra_raw in self.errores_ocr_apellidos:
            matched_val = self.errores_ocr_apellidos.get(palabra_norm) or self.errores_ocr_apellidos.get(palabra_raw)
            apellido_score = 0.95
            evidencias.append(f"ocr_error_map_surname -> {matched_val}")

        # 2. Búsqueda exacta en Diccionario Nombres
        if palabra_norm in self.nombres:
            nombre_score = max(nombre_score, 0.95)
            evidencias.append("dictionary_exact_name")
        
        # 3. Búsqueda exacta en Diccionario Apellidos
        if palabra_norm in self.apellidos:
            apellido_score = max(apellido_score, 0.95)
            evidencias.append("dictionary_exact_surname")

        # 4. Fuzzy Matching con RapidFuzz si no hubo coincidencia exacta
        if nombre_score == 0.0 and self.nombres:
            best_nom, score_nom, _ = process.extractOne(palabra_norm, self.nombres, scorer=fuzz.ratio) or (None, 0, None)
            if score_nom >= 80:
                nombre_score = score_nom / 100.0 * 0.85
                matched_val = best_nom
                is_fuzzy = True
                evidencias.append(f"fuzzy_name_match ({best_nom} {score_nom}%)")

        if apellido_score == 0.0 and self.apellidos:
            best_ape, score_ape, _ = process.extractOne(palabra_norm, self.apellidos, scorer=fuzz.ratio) or (None, 0, None)
            if score_ape >= 80:
                apellido_score = score_ape / 100.0 * 0.85
                matched_val = best_ape
                is_fuzzy = True
                evidencias.append(f"fuzzy_surname_match ({best_ape} {score_ape}%)")

        dict_match = (nombre_score >= 0.8 or apellido_score >= 0.8)

        return {
            "text": palabra_raw,
            "normalized_text": palabra_norm,
            "nombre_score": round(nombre_score, 2),
            "apellido_score": round(apellido_score, 2),
            "dictionary_match": dict_match,
            "fuzzy_match": is_fuzzy,
            "matched_value": matched_val,
            "evidence": evidencias
        }

    def detectar_duplicados(self, palabras: List[str]) -> Tuple[List[str], Optional[Dict[str, Any]]]:
        """
        Detecta palabras duplicadas consecutivas (ej. "PEDRO PEDRO JOSE") o repetidas.
        No elimina automáticamente si no hay certeza; retorna estructura de reporte.
        """
        if not palabras:
            return palabras, None

        palabras_norm = [self.normalizar_para_comparacion(p) for p in palabras]
        duplicado_hallado = False
        razon = ""
        palabras_limpias = []
        vistas = set()

        for idx, (p_orig, p_norm) in enumerate(zip(palabras, palabras_norm)):
            if p_norm in vistas:
                duplicado_hallado = True
                razon = f"Palabra duplicada detectada: '{p_orig}'"
            else:
                vistas.add(p_norm)
                palabras_limpias.append(p_orig)

        if duplicado_hallado:
            info_duplicado = {
                "duplicate_detected": True,
                "reason": razon,
                "confidence": 0.85,
                "original_words": palabras,
                "deduplicated_words": palabras_limpias
            }
            return palabras, info_duplicado

        return palabras, None

    def analizar_candidatos_campo(
        self,
        palabras: List[str],
        campo_destino: str,  # "nombres" o "apellidos"
        etiqueta_presente: bool,
        distancia_espacial_px: float,
        doc_ai_confidence: float,
        es_posicion_correcta: bool = True
    ) -> Dict[str, Any]:
        """
        Evalúa combinaciones n-gramas (1 a 4 palabras) mediante el sistema de scoring evidencial ponderado.
        Le da máxima prioridad al layout espacial sobre los diccionarios.
        """
        if not palabras:
            return {
                "value": None,
                "final_score": 0.0,
                "status": "missing_data",
                "reason": "No se encontraron palabras candidatas",
                "evidence": ["no_words_found"],
                "selected_candidate": None,
                "rejected_candidates": []
            }

        # Detección de duplicados
        _, info_duplicado = self.detectar_duplicados(palabras)
        evidencias_base = []
        if info_duplicado and info_duplicado.get("duplicate_detected"):
            evidencias_base.append(f"duplicate_warning: {info_duplicado['reason']}")

        # Generar n-gramas candidatos (combinaciones continuas de 1 a 4 palabras)
        candidatos = []
        n = len(palabras)
        for length in range(1, min(n + 1, 5)):
            for start in range(n - length + 1):
                grupo = palabras[start : start + length]
                cand_str = " ".join(grupo)
                candidatos.append(cand_str)

        resultados_candidatos = []

        for cand in candidatos:
            cand_norm = self.normalizar_para_comparacion(cand)
            palabras_cand = cand_norm.split()
            
            # Evaluación por palabras individuales
            evals = [self.evaluar_palabra(p) for p in palabras_cand]
            
            avg_nombre_score = sum(e["nombre_score"] for e in evals) / len(evals) if evals else 0.0
            avg_apellido_score = sum(e["apellido_score"] for e in evals) / len(evals) if evals else 0.0

            # Verificación de compuestos explícitos en JSON
            if campo_destino == "nombres" and cand_norm in self.nombres_compuestos:
                avg_nombre_score = 1.0
            elif campo_destino == "apellidos" and cand_norm in self.apellidos_compuestos:
                avg_apellido_score = 1.0

            # 1. Etiqueta explícita score (40%)
            score_etiqueta = 1.0 if etiqueta_presente else 0.4

            # 2. Posición espacial score (30%)
            if es_posicion_correcta:
                score_espacial = 1.0 if distancia_espacial_px <= 40 else 0.8
            else:
                score_espacial = 0.2

            # 3. Document AI confidence score (15%)
            score_doc_ai = max(0.0, min(1.0, doc_ai_confidence))

            # 4. Diccionario score (10%)
            score_dict = avg_nombre_score if campo_destino == "nombres" else avg_apellido_score

            # 5. Fuzzy score (5%)
            has_fuzzy = any(e.get("fuzzy_match") for e in evals)
            score_fuzzy = 0.9 if has_fuzzy else (1.0 if score_dict >= 0.8 else 0.5)

            # Bonus por cobertura de n-gramas completos cuando todas las palabras son válidas
            length_bonus = 0.03 * (len(palabras_cand) - 1) if (score_dict >= 0.7 or score_espacial >= 0.9) else 0.0

            # Cálculo de Puntuación Final Ponderada
            final_score = (
                score_etiqueta * self.PESOS_SCORING["etiqueta_explicita"] +
                score_espacial * self.PESOS_SCORING["posicion_espacial"] +
                score_doc_ai * self.PESOS_SCORING["confianza_doc_ai"] +
                score_dict * self.PESOS_SCORING["coincidencia_diccionario"] +
                score_fuzzy * self.PESOS_SCORING["similitud_fuzzy"] +
                length_bonus
            )

            # Recopilación de evidencias
            evidencias_cand = list(evidencias_base)
            if etiqueta_presente:
                evidencias_cand.append(f"✓ Encontrado debajo de etiqueta {campo_destino.upper()}")
            if es_posicion_correcta:
                evidencias_cand.append(f"✓ Distancia espacial adecuada ({round(distancia_espacial_px)}px)")
            if score_doc_ai >= 0.85:
                evidencias_cand.append(f"✓ Document AI confidence alto ({round(score_doc_ai * 100)}%)")
            if score_dict >= 0.8:
                evidencias_cand.append("✓ Coincidencia en diccionario")
            else:
                evidencias_cand.append("ℹ Palabra no registrada en diccionario (aceptada por evidencia espacial)")
            if len(palabras_cand) > 1:
                evidencias_cand.append("✓ Nombre/Apellido compuesto detectado")

            resultados_candidatos.append({
                "candidate": cand,
                "normalized": cand_norm,
                "final_score": round(final_score, 4),
                "spatial_score": round(score_espacial, 2),
                "dictionary_score": round(score_dict, 2),
                "fuzzy_score": round(score_fuzzy, 2),
                "nombre_score": round(avg_nombre_score, 2),
                "apellido_score": round(avg_apellido_score, 2),
                "evidence": evidencias_cand
            })

        # Ordenar candidatos por final_score descendente
        resultados_candidatos.sort(key=lambda x: x["final_score"], reverse=True)

        if not resultados_candidatos:
            return {
                "value": None,
                "final_score": 0.0,
                "status": "review_required",
                "reason": "Sin candidatos válidos evaluados",
                "evidence": ["no_valid_candidates"]
            }

        top = resultados_candidatos[0]
        segundo = resultados_candidatos[1] if len(resultados_candidatos) > 1 else None

        # Evaluación de Reglas de Seguridad (PRECISIÓN > COMPLETITUD)
        status = "valid"
        reason = "Evaluación evidencial exitosa"

        # Conflicto / Ambigüedad por margen cercano entre los mejores candidatos
        if segundo and (top["final_score"] - segundo["final_score"]) < self.MARGEN_DIFERENCIA_AMBIGÜEDAD and top["final_score"] < 0.85:
            status = "review_required"
            reason = f"Ambigüedad entre candidatos '{top['candidate']}' ({round(top['final_score']*100)}%) y '{segundo['candidate']}' ({round(segundo['final_score']*100)}%)"
            top["evidence"].append("⚠️ Ambigüedad detectada entre candidatos cercanos")

        # Conflicto entre Diccionario Nombres y Apellidos
        if top["nombre_score"] >= 0.8 and top["apellido_score"] >= 0.8 and top["spatial_score"] < 0.9:
            status = "review_required"
            reason = f"Palabra '{top['candidate']}' presente en ambos diccionarios con ambigüedad espacial"
            top["evidence"].append("⚠️ Palabra válida como nombre y apellido simultáneamente")

        # Puntuación final insuficiente
        if top["final_score"] < self.UMBRAL_BAJO_MISSING:
            status = "missing_data"
            reason = f"Evidencia insuficiente para {campo_destino} (Score: {round(top['final_score']*100)}%)"
        elif top["final_score"] < self.UMBRAL_ALTO_VALIDO and status == "valid":
            status = "review_required"
            reason = f"Score medio ({round(top['final_score']*100)}%) - Requiere revisión"

        return {
            "value": top["candidate"],
            "final_score": top["final_score"],
            "status": status,
            "reason": reason,
            "spatial_score": top["spatial_score"],
            "dictionary_score": top["dictionary_score"],
            "fuzzy_score": top["fuzzy_score"],
            "nombre_score": top["nombre_score"],
            "apellido_score": top["apellido_score"],
            "evidence": top["evidence"],
            "selected_candidate": top["candidate"],
            "rejected_candidates": [c["candidate"] for c in resultados_candidatos[1:]]
        }


name_dictionary_service = NameDictionaryService()
