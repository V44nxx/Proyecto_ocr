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
            pags.append(self.front_page["pagina_numero"])
        if self.back_page:
            pags.append(self.back_page["pagina_numero"])
        for p in self.other_pages:
            pags.append(p["pagina_numero"])
        return sorted(pags)

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
    Detecta automáticamente cuando una cédula está repartida en múltiples hojas y
    las unifica basándose en el número de identidad para prevenir duplicados.
    """

    def agrupar_paginas(self, paginas_clasificadas: List[Dict[str, Any]]) -> List[DocumentGroup]:
        """
        Agrupa páginas clasificadas en DocumentGroups (un grupo = un documento físico real).

        Reglas de agrupación (en orden de prioridad):
        1. Si una página tiene AMBOS LADOS (Frente + Reverso en la misma imagen) → 1 grupo, 1 persona.
        2. Si FRENTE y REVERSO tienen el mismo número de cédula → unificar en 1 grupo (sin importar posición).
        3. Si un FRENTE va seguido inmediatamente de un REVERSO (páginas consecutivas) → 1 grupo.
        4. Si queda un único FRONT huérfano y un único BACK disponible → emparejar de forma optimista.
        5. Un reverso huérfano SIN frente asociado NO crea una persona nueva si no tiene ID ni nombres.
        6. NUNCA se duplica si la cédula ya fue vista en un grupo anterior.
        """
        if not paginas_clasificadas:
            return []

        from app.utils.validators import validador

        grupos: List[DocumentGroup] = []
        counter = 1

        # Separar por tipo de cara
        both_sides = [p for p in paginas_clasificadas if p.get("cara") == "CEDULA_AMBOS_LADOS"]
        fronts = [p for p in paginas_clasificadas if "FRONT" in p.get("cara", "") and p not in both_sides]
        backs = [p for p in paginas_clasificadas if "BACK" in p.get("cara", "") and p not in both_sides]
        unknowns = [p for p in paginas_clasificadas if p.get("cara") == "UNKNOWN" and p not in both_sides]

        # Registro de IDs ya asignados a grupos (id_limpio → group_id)
        ids_vistos: Dict[str, str] = {}

        # ── Paso 1: CEDULA_AMBOS_LADOS (frente y reverso en la misma página) ──────────────────
        for b_side in both_sides:
            raw_id = b_side.get("numero_identificacion")
            id_clean = validador.limpiar_identificacion(raw_id)

            if id_clean and id_clean in ids_vistos:
                # Ya existe un grupo con esta cédula: fusionar
                grp_existente = next((g for g in grupos if g.group_id == ids_vistos[id_clean]), None)
                if grp_existente:
                    grp_existente.other_pages.append(b_side)
                    grp_existente.reasons.append(f"Página de 2 caras adicional unificada por ID '{id_clean}'")
                    continue

            grp = DocumentGroup(f"DOC-{counter:03d}")
            grp.front_page = b_side
            grp.back_page = b_side
            grp.tipo_documento = b_side.get("tipo_documento", "CEDULA_CIUDADANIA")
            grp.numero_identificacion = id_clean or raw_id
            grp.grouping_confidence = 0.99
            grp.reasons = ["Ambas caras escaneadas en la misma página"]
            grp.status = "VALID" if grp.numero_identificacion else "REVIEW_REQUIRED"

            if id_clean:
                ids_vistos[id_clean] = grp.group_id

            grupos.append(grp)
            counter += 1

        # ── Paso 2: Emparejar FRONTs con BACKs ────────────────────────────────────────────────
        fronts_ordenados = sorted(fronts, key=lambda p: p.get("pagina_numero", 1))
        backs_disponibles = list(backs)  # copia mutable para ir consumiendo

        for f_page in fronts_ordenados:
            p_front = f_page.get("pagina_numero", 1)
            raw_id_front = f_page.get("numero_identificacion")
            id_front = validador.limpiar_identificacion(raw_id_front)

            # ¿Ya existe un grupo con este ID? → fusionar en lugar de crear uno nuevo
            if id_front and id_front in ids_vistos:
                grp_existente = next((g for g in grupos if g.group_id == ids_vistos[id_front]), None)
                if grp_existente:
                    if not grp_existente.front_page:
                        grp_existente.front_page = f_page
                    elif grp_existente.front_page.get("pagina_numero") != p_front:
                        grp_existente.other_pages.append(f_page)
                    grp_existente.reasons.append(f"Frente (Pág {p_front}) unificado por ID '{id_front}'")
                    continue

            grp = DocumentGroup(f"DOC-{counter:03d}")
            grp.front_page = f_page
            grp.tipo_documento = f_page.get("tipo_documento", "CEDULA_CIUDADANIA")
            grp.numero_identificacion = id_front or raw_id_front

            best_back: Optional[Dict[str, Any]] = None
            best_score = 0.0
            best_reasons: List[str] = []

            # Prioridad A: Coincidencia exacta de ID en cualquier reverso disponible
            if id_front:
                for b_page in list(backs_disponibles):
                    b_id = validador.limpiar_identificacion(b_page.get("numero_identificacion"))
                    if b_id and b_id == id_front:
                        best_back = b_page
                        best_score = 0.99
                        best_reasons = [f"ID idéntico en Frente y Reverso: '{id_front}'"]
                        break

            # Prioridad B: REVERSO inmediatamente consecutivo (página siguiente)
            # Esta regla es la más importante para cédulas sin MRZ / sin ID en reverso
            if not best_back:
                pagina_siguiente = p_front + 1
                back_consecutivo = next(
                    (b for b in backs_disponibles if b.get("pagina_numero") == pagina_siguiente),
                    None
                )
                if back_consecutivo:
                    b_id = validador.limpiar_identificacion(back_consecutivo.get("numero_identificacion"))
                    # Si el reverso tiene un ID diferente al frente → NO emparejar (pertenece a otra cédula)
                    ids_en_conflicto = bool(id_front and b_id and id_front != b_id)
                    if not ids_en_conflicto:
                        best_back = back_consecutivo
                        best_score = 0.92
                        best_reasons = [f"Reverso inmediatamente consecutivo (Pág {p_front}→{pagina_siguiente})"]

            # Prioridad C: Buscar UNKNOWN en la página siguiente como reverso complementario
            if not best_back:
                pagina_siguiente = p_front + 1
                unk_consecutivo = next(
                    (u for u in unknowns if u.get("pagina_numero") == pagina_siguiente),
                    None
                )
                if unk_consecutivo:
                    best_back = unk_consecutivo
                    best_score = 0.75
                    best_reasons = [f"Página siguiente de tipo desconocido asignada como Reverso (Pág {pagina_siguiente})"]
                    unknowns.remove(unk_consecutivo)

            # Prioridad D: Búsqueda global por puntuación (último recurso)
            if not best_back:
                for b_page in list(backs_disponibles):
                    score, reasons = self.evaluar_asociacion(f_page, b_page)
                    p_back = b_page.get("pagina_numero", 2)
                    if abs(p_back - p_front) == 1:
                        score = min(0.99, score + 0.20)
                        reasons = reasons + ["Bonus: páginas contiguas (+0.20)"]
                    if score > best_score and score >= 0.35:
                        best_score = score
                        best_back = b_page
                        best_reasons = reasons

            if best_back:
                grp.back_page = best_back
                grp.grouping_confidence = best_score
                grp.reasons = best_reasons
                # Tomar el ID del reverso si el frente no lo tenía
                if not grp.numero_identificacion:
                    b_id = validador.limpiar_identificacion(best_back.get("numero_identificacion"))
                    if b_id:
                        grp.numero_identificacion = b_id
                if best_back in backs_disponibles:
                    backs_disponibles.remove(best_back)
                grp.status = "VALID" if grp.numero_identificacion else "REVIEW_REQUIRED"
            else:
                grp.grouping_confidence = f_page.get("confianza", 0.90)
                grp.reasons = ["Cédula de una sola cara (solo Frente disponible)"]
                grp.status = "VALID" if grp.numero_identificacion else "REVIEW_REQUIRED"

            if id_front:
                ids_vistos[id_front] = grp.group_id
            if grp.numero_identificacion and grp.numero_identificacion not in ids_vistos:
                ids_vistos[grp.numero_identificacion] = grp.group_id

            grupos.append(grp)
            counter += 1

        # ── Paso 3: Pairing optimista — 1 FRONT huérfano + 1 BACK huérfano ─────────────────────
        grupos_sin_back = [g for g in grupos if g.front_page and not g.back_page]
        if len(grupos_sin_back) == 1 and len(backs_disponibles) == 1:
            grp_huerfano = grupos_sin_back[0]
            b_solo = backs_disponibles[0]
            # Solo emparejar si no hay conflicto de ID
            b_id = validador.limpiar_identificacion(b_solo.get("numero_identificacion"))
            id_g = grp_huerfano.numero_identificacion
            if not (id_g and b_id and id_g != b_id):
                grp_huerfano.back_page = b_solo
                grp_huerfano.grouping_confidence = max(grp_huerfano.grouping_confidence, 0.70)
                grp_huerfano.reasons.append("Pairing optimista: único Frente + único Reverso disponibles")
                if not grp_huerfano.numero_identificacion and b_id:
                    grp_huerfano.numero_identificacion = b_id
                    ids_vistos[b_id] = grp_huerfano.group_id
                if grp_huerfano.numero_identificacion:
                    grp_huerfano.status = "VALID"
                backs_disponibles.clear()

        # ── Paso 4: BACKs huérfanos ────────────────────────────────────────────────────────────
        for b_page in backs_disponibles:
            raw_id_back = b_page.get("numero_identificacion")
            id_back = validador.limpiar_identificacion(raw_id_back)

            # Si el ID ya fue visto en otro grupo → fusionar (no crear duplicado)
            if id_back and id_back in ids_vistos:
                grp_prev = next((g for g in grupos if g.group_id == ids_vistos[id_back]), None)
                if grp_prev:
                    if not grp_prev.back_page:
                        grp_prev.back_page = b_page
                    else:
                        grp_prev.other_pages.append(b_page)
                    grp_prev.reasons.append(f"Reverso (Pág {b_page.get('pagina_numero')}) unificado por ID '{id_back}'")
                    continue

            # REGLA ANTI-DUPLICADOS: Un reverso huérfano sin ID y sin frente NO crea persona nueva,
            # a menos que sea la única página del PDF (para no dejar el procesamiento en blanco).
            es_unica_pagina = len(paginas_clasificadas) == 1
            if id_back or es_unica_pagina:
                grp = DocumentGroup(f"DOC-{counter:03d}")
                grp.back_page = b_page
                grp.tipo_documento = b_page.get("tipo_documento", "CEDULA_CIUDADANIA")
                grp.numero_identificacion = id_back
                grp.grouping_confidence = 0.70
                grp.reasons = ["Reverso huérfano con ID propio (Frente no encontrado en el PDF)"]
                grp.status = "REVIEW_REQUIRED"
                if id_back:
                    ids_vistos[id_back] = grp.group_id
                grupos.append(grp)
                counter += 1
            else:
                # Reverso sin ID ni frente en PDF de múltiples páginas → descartado para no generar personas fantasma
                logger.info(
                    f"[DocumentPairingService] Reverso Pág {b_page.get('pagina_numero')} "
                    f"descartado: sin ID y sin frente asociado (evita duplicado fantasma)"
                )

        # ── Paso 5: UNKNOWNs ──────────────────────────────────────────────────────────────────
        for u_page in unknowns:
            raw_id_unk = u_page.get("numero_identificacion")
            id_unk = validador.limpiar_identificacion(raw_id_unk)

            if id_unk and id_unk in ids_vistos:
                grp_prev = next((g for g in grupos if g.group_id == ids_vistos[id_unk]), None)
                if grp_prev:
                    grp_prev.other_pages.append(u_page)
                    grp_prev.reasons.append(f"Página adicional (Pág {u_page.get('pagina_numero')}) fusionada por ID '{id_unk}'")
                    continue

            # Crear grupo UNKNOWN si:
            #  a) tiene ID propio, o
            #  b) es la única página del PDF (así el extractor puede intentar extraer algo)
            es_unica_pagina = len(paginas_clasificadas) == 1
            if id_unk or es_unica_pagina:
                grp = DocumentGroup(f"DOC-{counter:03d}")
                grp.other_pages.append(u_page)
                grp.tipo_documento = u_page.get("tipo_documento", "UNKNOWN")
                grp.numero_identificacion = id_unk
                grp.grouping_confidence = 0.30
                grp.reasons = ["Página no reconocida como documento válido"]
                grp.status = "REVIEW_REQUIRED"
                if id_unk:
                    ids_vistos[id_unk] = grp.group_id
                grupos.append(grp)
                counter += 1
            else:
                logger.info(
                    f"[DocumentPairingService] Página UNKNOWN Pág {u_page.get('pagina_numero')} "
                    f"descartada (PDF de múltiples páginas, sin ID reconocido)"
                )

        logger.info(
            f"[DocumentPairingService] {len(paginas_clasificadas)} página(s) → "
            f"{len(grupos)} grupo(s) de documento(s). "
            f"IDs únicos: {list(ids_vistos.keys())}"
        )
        return grupos

    def evaluar_asociacion(self, f_page: Dict[str, Any], b_page: Dict[str, Any]) -> tuple[float, List[str]]:
        """
        Calcula la puntuación de asociación evidencial (0.0 a 1.0) entre una página FRONT y una BACK.
        """
        from app.utils.validators import validador

        reasons = []
        score = 0.0

        id_front = validador.limpiar_identificacion(f_page.get("numero_identificacion"))
        id_back = validador.limpiar_identificacion(b_page.get("numero_identificacion"))

        # 1. Coincidencia de Número de Cédula (MRZ en Reverso vs Cédula en Frente) -> PESO MUY ALTO
        if id_front and id_back and id_front == id_back:
            score += 0.55
            reasons.append(f"Coincidencia exacta de número de identificación '{id_front}' (MRZ/Front)")
        elif id_front and id_back and id_front != id_back:
            # Conflicto directo de ID
            return 0.10, [f"Conflicto de número de identificación: Front '{id_front}' vs Back '{id_back}'"]

        # 2. Mismo tipo de documento -> PESO ALTO
        tipo_f = f_page.get("tipo_documento", "CEDULA_CIUDADANIA")
        tipo_b = b_page.get("tipo_documento", "CEDULA_CIUDADANIA")
        if tipo_f == tipo_b:
            score += 0.25
            reasons.append(f"Mismo tipo de documento '{tipo_f}'")

        # 3. Secuencia FRONT seguida de BACK
        p_front = f_page.get("pagina_numero", 1)
        p_back = b_page.get("pagina_numero", 2)
        dist_pag = p_back - p_front

        if dist_pag == 1:
            score += 0.15
            reasons.append("Secuencia de páginas consecutivas (Front -> Back)")
        elif dist_pag > 1:
            score += max(0.05, 0.15 - (dist_pag * 0.02))
            reasons.append(f"Proximidad de páginas ({p_front} y {p_back})")

        # 4. Proximidad física general
        if abs(dist_pag) <= 2:
            score += 0.10
            reasons.append("Proximidad física dentro del PDF")

        return min(0.99, score), reasons


document_pairing_service = DocumentPairingService()
