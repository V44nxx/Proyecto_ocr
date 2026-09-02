"""
Servicio de Agrupación Inteligente de Páginas (DocumentPairingService).
Reconstruye el documento físico (Frente + Reverso) a partir de múltiples evidencias ponderadas:
coincidencia de ID (MRZ vs NUIP), tipo documental, secuencia FRONT-BACK y proximidad.
"""
from typing import List, Dict, Any, Optional
from app.utils.logger import app_logger as logger


class DocumentGroup:
    """Representa un documento físico reconstruido a partir de 1 o más páginas/caras"""
    def __init__(self, group_id: str):
        self.group_id = group_id
        self.front_page: Optional[Dict[str, Any]] = None
        self.back_page: Optional[Dict[str, Any]] = None
        self.other_pages: List[Dict[str, Any]] = []
        self.grouping_confidence: float = 1.0
        self.reasons: List[str] = []
        self.status: str = "VALID"
        self.numero_identificacion: Optional[str] = None
        self.tipo_documento: str = "CEDULA_CIUDADANIA"

    @property
    def pages(self) -> List[int]:
        pags = []
        if self.front_page:
            pags.append(self.front_page["pagina_numero"] if isinstance(self.front_page, dict) else int(self.front_page))
        if self.back_page:
            pags.append(self.back_page["pagina_numero"] if isinstance(self.back_page, dict) else int(self.back_page))
        for p in self.other_pages:
            pags.append(p["pagina_numero"] if isinstance(p, dict) else int(p))
        return sorted(list(set(pags)))

    @property
    def pagina_frente(self) -> Optional[int]:
        return self.front_page["pagina_numero"] if self.front_page else None

    @property
    def pagina_reverso(self) -> Optional[int]:
        return self.back_page["pagina_numero"] if self.back_page else None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "group_id": self.group_id,
            "confidence": round(self.grouping_confidence, 2),
            "pages": self.pages,
            "pagina_frente": self.pagina_frente,
            "pagina_reverso": self.pagina_reverso,
            "tipo_documento": self.tipo_documento,
            "status": self.status,
            "reasons": self.reasons
        }


class DocumentPairingService:
    """
    Servicio de agrupación evidencial ponderada para documentos de múltiples páginas.
    Implementa Emparejamiento Global Bipartito (Algoritmo Húngaro / Linear Sum Assignment)
    y RapidFuzz para reconciliar frentes y reversos de forma matemática y eliminar duplicados.
    """

    def evaluar_asociacion(self, f_page: Dict[str, Any], b_page: Dict[str, Any]) -> tuple[float, List[str]]:
        """
        Calcula la puntuación de asociación evidencial (0.0 a 1.0) entre una página FRONT y una BACK.
        Tolera errores de 1 dígito en OCR y evalúa proximidad física y tipo documental.
        """
        from app.utils.validators import validador
        from rapidfuzz import fuzz

        reasons = []
        score = 0.0

        id_front = validador.limpiar_identificacion(f_page.get("numero_identificacion"))
        id_back = validador.limpiar_identificacion(b_page.get("numero_identificacion"))

        # 1. Validación de Tipo de Documento
        tipo_f = f_page.get("tipo_documento", "CEDULA_CIUDADANIA")
        tipo_b = b_page.get("tipo_documento", "CEDULA_CIUDADANIA")
        if tipo_f != "UNKNOWN" and tipo_b != "UNKNOWN" and tipo_f != tipo_b:
            # Tipos contradictorios (ej: Cédula vs Tarjeta de Identidad)
            return 0.10, [f"Conflicto de tipo documental: Front '{tipo_f}' vs Back '{tipo_b}'"]
        elif tipo_f == tipo_b and tipo_f != "UNKNOWN":
            score += 0.20
            reasons.append(f"Mismo tipo de documento '{tipo_f}'")

        # 2. Coincidencia de Número de Cédula (con tolerancia difusa para errores de OCR)
        if id_front and id_back:
            if id_front == id_back:
                score += 0.60
                reasons.append(f"Coincidencia exacta de número de identificación '{id_front}'")
            else:
                sim = fuzz.ratio(str(id_front), str(id_back))
                es_subcadena = (str(id_front) in str(id_back)) or (str(id_back) in str(id_front))
                len_min = min(len(str(id_front)), len(str(id_back)))

                if sim >= 88 or (es_subcadena and len_min >= 6):
                    # Error tipográfico común de OCR (1 dígito confundido o recortado)
                    score += 0.50
                    reasons.append(f"Coincidencia difusa de cédula ({sim}% similitud: '{id_front}' vs '{id_back}')")
                elif len_min >= 6 and sim < 75:
                    # Cédulas claramente diferentes de longitud completa
                    return 0.10, [f"Conflicto de número de identificación: Front '{id_front}' vs Back '{id_back}'"]
                else:
                    score += 0.10
        elif id_front and not id_back:
            # Back sin ID detectado (muy común en reverso de cédula amarilla con código de barras degradado)
            score += 0.25
            reasons.append("Reverso sin ID (asociación por proximidad y contexto)")
        elif not id_front and id_back:
            score += 0.20

        # 3. Proximidad de Páginas y Secuencia FRONT -> BACK
        p_front = f_page.get("pagina_numero", 1)
        p_back = b_page.get("pagina_numero", 2)
        dist_pag = p_back - p_front

        if dist_pag == 1:
            score += 0.20
            reasons.append("Secuencia de páginas consecutivas (Front -> Back)")
        elif dist_pag > 1:
            bonus = max(0.02, 0.15 - ((dist_pag - 1) * 0.02))
            score += bonus
            reasons.append(f"Proximidad de páginas ({p_front} y {p_back})")
        elif dist_pag == -1:
            # Reverso antes de Frente (PDF escaneado al revés)
            score += 0.10
            reasons.append("Secuencia invertida inmediata (Back -> Front)")
        else:
            score -= 0.05

        return min(0.99, max(0.0, score)), reasons

    def agrupar_paginas(self, paginas_clasificadas: List[Dict[str, Any]]) -> List[DocumentGroup]:
        """
        Agrupa páginas clasificadas en DocumentGroups mediante Emparejamiento Global Bipartito.
        Garantiza que un lote con N frentes produzca como máximo N personas físicas en la tabla.
        """
        if not paginas_clasificadas:
            return []

        from app.utils.validators import validador
        import numpy as np

        paginas = sorted(paginas_clasificadas, key=lambda p: p.get("pagina_numero", 1))
        total_pags = len(paginas)

        # Caso especial: 1 sola página
        if total_pags == 1:
            p = paginas[0]
            grp = DocumentGroup("DOC-001")
            cara = p.get("cara", "UNKNOWN")
            if "BACK" in cara:
                grp.back_page = p
            else:
                grp.front_page = p
            grp.tipo_documento = p.get("tipo_documento", "CEDULA_CIUDADANIA")
            grp.numero_identificacion = validador.limpiar_identificacion(p.get("numero_identificacion"))
            grp.grouping_confidence = 0.95 if grp.numero_identificacion else 0.40
            grp.status = "VALID" if (grp.numero_identificacion and "UNKNOWN" not in str(grp.tipo_documento)) else "REVIEW_REQUIRED"
            grp.reasons = ["Documento de una sola página"]
            return [grp]

        # ── Paso 1: Clasificar páginas en categorías de emparejamiento ──
        standalone_pages = []
        front_candidates = []
        back_candidates = []

        for p in paginas:
            cara = p.get("cara", "UNKNOWN")
            if cara == "CEDULA_AMBOS_LADOS":
                standalone_pages.append(p)
            elif "BACK" in cara:
                back_candidates.append(p)
            elif "FRONT" in cara:
                front_candidates.append(p)
            else:
                # UNKNOWN: Si tiene número de cédula y parece frente, tratarlo como Front; sino como Back
                if p.get("numero_identificacion"):
                    front_candidates.append(p)
                else:
                    back_candidates.append(p)

        # ── Paso 2: Matriz de Costo y Emparejamiento Bipartito Global (Hungarian Algorithm) ──
        grupos: List[DocumentGroup] = []
        counter = 1
        used_back_indices = set()
        used_front_indices = set()

        if front_candidates and back_candidates:
            n_f = len(front_candidates)
            n_b = len(back_candidates)
            cost_matrix = np.ones((n_f, n_b), dtype=float)
            affinity_matrix = np.zeros((n_f, n_b), dtype=float)
            reasons_matrix = [[[] for _ in range(n_b)] for _ in range(n_f)]

            for f_idx, f_p in enumerate(front_candidates):
                for b_idx, b_p in enumerate(back_candidates):
                    aff, reasons = self.evaluar_asociacion(f_p, b_p)
                    affinity_matrix[f_idx, b_idx] = aff
                    cost_matrix[f_idx, b_idx] = max(0.0, 1.0 - aff)
                    reasons_matrix[f_idx][b_idx] = reasons

            # Ejecutar Algoritmo Húngaro (Linear Sum Assignment)
            try:
                from scipy.optimize import linear_sum_assignment
                row_ind, col_ind = linear_sum_assignment(cost_matrix)
                pares_optimos = list(zip(row_ind, col_ind))
            except Exception as e:
                # Fallback voraz en Python puro si scipy fallara
                logger.warning(f"[DocumentPairingService] Fallback voraz para asignación: {e}")
                pares_optimos = []
                f_libres = set(range(n_f))
                b_libres = set(range(n_b))
                while f_libres and b_libres:
                    mejor_aff = -1.0
                    mejor_par = (-1, -1)
                    for f_i in f_libres:
                        for b_i in b_libres:
                            if affinity_matrix[f_i, b_i] > mejor_aff:
                                mejor_aff = affinity_matrix[f_i, b_i]
                                mejor_par = (f_i, b_i)
                    if mejor_aff >= 0.40:
                        pares_optimos.append(mejor_par)
                        f_libres.remove(mejor_par[0])
                        b_libres.remove(mejor_par[1])
                    else:
                        break

            # Crear grupos para los pares óptimos emparejados con umbral mínimo de afinidad
            UMBRAL_EMPAREJAMIENTO = 0.40
            for f_idx, b_idx in pares_optimos:
                aff = affinity_matrix[f_idx, b_idx]
                if aff >= UMBRAL_EMPAREJAMIENTO:
                    f_p = front_candidates[f_idx]
                    b_p = back_candidates[b_idx]
                    id_f = validador.limpiar_identificacion(f_p.get("numero_identificacion"))
                    id_b = validador.limpiar_identificacion(b_p.get("numero_identificacion"))
                    id_unificado = id_f or id_b

                    grp = DocumentGroup(f"DOC-{counter:03d}")
                    grp.front_page = f_p
                    grp.back_page = b_p
                    grp.tipo_documento = f_p.get("tipo_documento", "CEDULA_CIUDADANIA")
                    grp.numero_identificacion = id_unificado
                    grp.grouping_confidence = round(aff, 2)
                    grp.reasons = reasons_matrix[f_idx][b_idx] or [f"Frente (Pág {f_p.get('pagina_numero')}) + Reverso (Pág {b_p.get('pagina_numero')}) emparejados globalmente"]
                    grp.status = "VALID" if (id_unificado and "UNKNOWN" not in str(grp.tipo_documento)) else "REVIEW_REQUIRED"

                    grupos.append(grp)
                    counter += 1
                    used_front_indices.add(f_idx)
                    used_back_indices.add(b_idx)

        # ── Paso 3: Frentes no emparejados (documentos de solo frente) ──
        for f_idx, f_p in enumerate(front_candidates):
            if f_idx not in used_front_indices:
                id_f = validador.limpiar_identificacion(f_p.get("numero_identificacion"))
                grp = DocumentGroup(f"DOC-{counter:03d}")
                grp.front_page = f_p
                grp.tipo_documento = f_p.get("tipo_documento", "CEDULA_CIUDADANIA")
                grp.numero_identificacion = id_f
                grp.grouping_confidence = 0.90 if id_f else 0.40
                grp.reasons = [f"Pág {f_p.get('pagina_numero')} — frente sin reverso"]
                grp.status = "VALID" if (id_f and "UNKNOWN" not in str(grp.tipo_documento)) else "REVIEW_REQUIRED"
                grupos.append(grp)
                counter += 1

        # ── Paso 4: Páginas Standalone (CEDULA_AMBOS_LADOS) ──
        for s_p in standalone_pages:
            id_s = validador.limpiar_identificacion(s_p.get("numero_identificacion"))
            grp = DocumentGroup(f"DOC-{counter:03d}")
            grp.front_page = s_p
            grp.tipo_documento = s_p.get("tipo_documento", "CEDULA_CIUDADANIA")
            grp.numero_identificacion = id_s
            grp.grouping_confidence = 0.99
            grp.reasons = [f"Pág {s_p.get('pagina_numero')} contiene ambas caras (AMBOS_LADOS)"]
            grp.status = "VALID" if id_s else "REVIEW_REQUIRED"
            grupos.append(grp)
            counter += 1

        # ── Paso 5: Reconciliación de Reversos Huérfanos (Regla Cero Huérfanos) ──
        # Los reversos no emparejados se intentan fusionar con grupos del mismo ID
        for b_idx, b_p in enumerate(back_candidates):
            if b_idx not in used_back_indices:
                id_b = validador.limpiar_identificacion(b_p.get("numero_identificacion"))
                fusionado = False
                if id_b:
                    for g in grupos:
                        if g.numero_identificacion == id_b:
                            if not g.back_page:
                                g.back_page = b_p
                                g.reasons.append(f"Reverso pág {b_p.get('pagina_numero')} asociado por ID coincidente")
                            else:
                                g.other_pages.append(b_p)
                            fusionado = True
                            logger.info(f"[DocumentPairingService] Reverso huérfano pág {b_p.get('pagina_numero')} fusionado a {g.group_id}")
                            break
                if not fusionado:
                    # En un lote multipágina, un reverso huérfano sin frente NO se promueve a ciudadano extra
                    logger.info(f"[DocumentPairingService] Reverso huérfano pág {b_p.get('pagina_numero')} (ID: {id_b or 'sin_id'}) descartado para evitar persona fantasma")

        # ── Paso 6: Deduplicación Final de Grupos por ID idéntico ──
        grupos_unicos_map: Dict[str, DocumentGroup] = {}
        grupos_sin_id: List[DocumentGroup] = []

        for g in grupos:
            id_val = g.numero_identificacion
            if id_val:
                if id_val not in grupos_unicos_map:
                    grupos_unicos_map[id_val] = g
                else:
                    existente = grupos_unicos_map[id_val]
                    # Fusionar caras faltantes
                    if not existente.front_page and g.front_page:
                        existente.front_page = g.front_page
                    elif g.front_page and g.front_page != existente.front_page:
                        existente.other_pages.append(g.front_page)
                    if not existente.back_page and g.back_page:
                        existente.back_page = g.back_page
                    elif g.back_page and g.back_page != existente.back_page:
                        existente.other_pages.append(g.back_page)
                    existente.other_pages.extend(g.other_pages)
                    existente.reasons.append(f"Páginas fusionadas por ID duplicado '{id_val}'")
            else:
                grupos_sin_id.append(g)

        grupos_finales = list(grupos_unicos_map.values()) + grupos_sin_id

        # Reordenar por primera página física y renumerar IDs
        grupos_finales.sort(key=lambda g: g.pages[0] if g.pages else 999)
        for idx, g in enumerate(grupos_finales):
            g.group_id = f"DOC-{idx+1:03d}"

        logger.info(
            f"[DocumentPairingService] {total_pags} página(s) -> "
            f"{len(grupos_finales)} grupo(s) de persona(s) física(s) únicas. "
            f"IDs: {[g.numero_identificacion for g in grupos_finales if g.numero_identificacion]}"
        )
        return grupos_finales


document_pairing_service = DocumentPairingService()
