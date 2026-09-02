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
        Agrupa páginas clasificadas en DocumentGroups (un grupo = un documento físico real = una persona).

        Garantías:
        1. CEDULA_AMBOS_LADOS → Siempre grupo independiente (ya contiene ambas caras en 1 página).
        2. CEDULA_FRONT seguido de CEDULA_BACK/UNKNOWN consecutivo → Unifican en 1 solo grupo.
        3. Si el ID ya fue visto → Fusionar sin crear duplicado.
        4. Segunda pasada: reconciliar grupos huérfanos (BACK sin FRONT, o FRONT sin BACK) con
           grupos existentes por coincidencia de ID.
        """
        if not paginas_clasificadas:
            return []

        from app.utils.validators import validador

        # Ordenar páginas estrictamente por número de página (1..N)
        paginas = sorted(paginas_clasificadas, key=lambda p: p.get("pagina_numero", 1))
        total_pags = len(paginas)

        grupos: List[DocumentGroup] = []
        ids_vistos: Dict[str, str] = {}  # id_limpio -> group_id
        counter = 1

        i = 0
        while i < total_pags:
            p_actual = paginas[i]
            cara_actual = p_actual.get("cara", "UNKNOWN")
            raw_id_actual = p_actual.get("numero_identificacion")
            id_actual = validador.limpiar_identificacion(raw_id_actual)

            # ── Si el ID ya existe en un grupo previo → fusionar sin crear duplicado ──
            if id_actual and id_actual in ids_vistos:
                grp_existente = next((g for g in grupos if g.group_id == ids_vistos[id_actual]), None)
                if grp_existente:
                    if "BACK" in cara_actual and not grp_existente.back_page:
                        grp_existente.back_page = p_actual
                        grp_existente.reasons.append(f"Reverso pág {p_actual.get('pagina_numero')} fusionado por ID coincidente")
                    elif ("FRONT" in cara_actual or cara_actual == "CEDULA_AMBOS_LADOS") and not grp_existente.front_page:
                        grp_existente.front_page = p_actual
                        grp_existente.reasons.append(f"Frente pág {p_actual.get('pagina_numero')} fusionado por ID coincidente")
                    else:
                        grp_existente.other_pages.append(p_actual)
                    i += 1
                    continue

            # ── CEDULA_AMBOS_LADOS → Siempre grupo independiente (NO intentar parear con siguiente) ──
            if cara_actual == "CEDULA_AMBOS_LADOS":
                grp = DocumentGroup(f"DOC-{counter:03d}")
                grp.front_page = p_actual  # Representa ambas caras
                grp.tipo_documento = p_actual.get("tipo_documento", "CEDULA_CIUDADANIA")
                grp.numero_identificacion = id_actual
                grp.grouping_confidence = 0.99
                grp.reasons = [f"Página {p_actual.get('pagina_numero')} contiene ambas caras (AMBOS_LADOS)"]
                grp.status = "VALID" if id_actual else "REVIEW_REQUIRED"
                if id_actual:
                    ids_vistos[id_actual] = grp.group_id
                grupos.append(grp)
                counter += 1
                i += 1
                continue

            # ── CEDULA_BACK sin ID: descartar si es reverso huérfano sin identificación ──
            if total_pags > 1 and "BACK" in cara_actual and not id_actual:
                logger.info(f"[DocumentPairingService] Reverso Pág {p_actual.get('pagina_numero')} sin ID descartado")
                i += 1
                continue

            # ── Para páginas FRONT: intentar emparejar con la siguiente BACK/UNKNOWN ──
            if i < total_pags - 1 and ("FRONT" in cara_actual):
                p_siguiente = paginas[i + 1]
                cara_sig = p_siguiente.get("cara", "UNKNOWN")
                raw_id_sig = p_siguiente.get("numero_identificacion")
                id_sig = validador.limpiar_identificacion(raw_id_sig)

                mismo_id = bool(id_actual and id_sig and id_actual == id_sig)
                ids_contradictorios = bool(id_actual and id_sig and id_actual != id_sig)

                # Emparejar si: mismo ID, o el siguiente es BACK/UNKNOWN sin IDs contradictorios
                es_par_consecutivo = (
                    mismo_id or
                    (
                        ("BACK" in cara_sig or cara_sig == "UNKNOWN") and
                        not ids_contradictorios
                    )
                )

                if es_par_consecutivo:
                    id_unificado = id_actual or id_sig
                    grp = DocumentGroup(f"DOC-{counter:03d}")
                    grp.front_page = p_actual
                    grp.back_page = p_siguiente
                    grp.tipo_documento = p_actual.get("tipo_documento", "CEDULA_CIUDADANIA")
                    grp.numero_identificacion = id_unificado
                    grp.grouping_confidence = 0.98 if mismo_id else 0.92
                    grp.reasons = [f"Frente (Pág {p_actual.get('pagina_numero')}) + Reverso (Pág {p_siguiente.get('pagina_numero')}) consecutivos"]
                    grp.status = "VALID" if (id_unificado and "UNKNOWN" not in str(grp.tipo_documento)) else "REVIEW_REQUIRED"
                    if id_unificado:
                        ids_vistos[id_unificado] = grp.group_id
                    grupos.append(grp)
                    counter += 1
                    i += 2
                    continue

            # ── Página individual (1 página = 1 persona) ──
            grp = DocumentGroup(f"DOC-{counter:03d}")
            if "BACK" in cara_actual:
                grp.back_page = p_actual
            else:
                grp.front_page = p_actual
            grp.tipo_documento = p_actual.get("tipo_documento", "CEDULA_CIUDADANIA")
            grp.numero_identificacion = id_actual
            grp.grouping_confidence = 0.90
            grp.reasons = [f"Pág {p_actual.get('pagina_numero')} — documento individual ({cara_actual})"]
            grp.status = "VALID" if (id_actual and "UNKNOWN" not in str(grp.tipo_documento)) else "REVIEW_REQUIRED"
            if id_actual:
                ids_vistos[id_actual] = grp.group_id
            grupos.append(grp)
            counter += 1
            i += 1

        # ── SEGUNDA PASADA: Reconciliar grupos huérfanos (BACK sin FRONT, FRONT sin BACK) ──
        # Busca grupos con solo reverso o solo frente y los fusiona con el grupo del mismo ID
        grupos_huerfanos = [g for g in grupos if (g.back_page and not g.front_page) or (g.front_page and not g.back_page and g.front_page.get("cara") not in ["CEDULA_AMBOS_LADOS", "UNKNOWN"])]

        for h_grp in grupos_huerfanos:
            h_id = h_grp.numero_identificacion
            if not h_id:
                continue

            # Buscar grupo COMPLEMENTARIO (si el huérfano es BACK, buscar FRONT, y viceversa)
            es_back_huerfano = bool(h_grp.back_page and not h_grp.front_page)

            for otro_grp in grupos:
                if otro_grp.group_id == h_grp.group_id:
                    continue
                otro_id = otro_grp.numero_identificacion
                if not otro_id or otro_id != h_id:
                    continue

                # Encontrado grupo complementario con mismo ID
                if es_back_huerfano and otro_grp.front_page and not otro_grp.back_page:
                    otro_grp.back_page = h_grp.back_page
                    otro_grp.reasons.append(f"Reverso fusionado desde {h_grp.group_id} por ID coincidente")
                    otro_grp.grouping_confidence = min(0.99, otro_grp.grouping_confidence + 0.05)
                    grupos.remove(h_grp)
                    logger.info(f"[DocumentPairingService] Fusión 2ª pasada: {h_grp.group_id} (BACK) → {otro_grp.group_id} por ID {h_id}")
                    break
                elif not es_back_huerfano and otro_grp.back_page and not otro_grp.front_page:
                    otro_grp.front_page = h_grp.front_page
                    otro_grp.reasons.append(f"Frente fusionado desde {h_grp.group_id} por ID coincidente")
                    otro_grp.grouping_confidence = min(0.99, otro_grp.grouping_confidence + 0.05)
                    grupos.remove(h_grp)
                    logger.info(f"[DocumentPairingService] Fusión 2ª pasada: {h_grp.group_id} (FRONT) → {otro_grp.group_id} por ID {h_id}")
                    break

        logger.info(
            f"[DocumentPairingService] {len(paginas_clasificadas)} pagina(s) -> "
            f"{len(grupos)} grupo(s) de persona(s) unificada(s). "
            f"IDs unicos: {list(ids_vistos.keys())}"
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
