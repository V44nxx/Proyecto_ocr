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
        1. Si la página i es FRENTE y la página i+1 es REVERSO (o UNKNOWN contiguo) → Se unifican en 1 solo grupo.
        2. Si la cédula ya fue vista en cualquier página previa → Se fusiona sin crear duplicado.
        3. En PDFs multipágina, un reverso o página desconocida huérfana NUNCA crea una persona extra si no tiene un documento independiente real.
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

            # Caso 1: Última página del documento
            if i == total_pags - 1:
                # Si su ID ya pertenece a un grupo existente → fusionar
                if id_actual and id_actual in ids_vistos:
                    grp_existente = next((g for g in grupos if g.group_id == ids_vistos[id_actual]), None)
                    if grp_existente:
                        grp_existente.other_pages.append(p_actual)
                        break

                # Si es un reverso huérfano sin ID en un PDF multipágina → descartar para no crear persona fantasma
                if total_pags > 1 and "BACK" in cara_actual and not id_actual:
                    logger.info(f"[DocumentPairingService] Página final {p_actual.get('pagina_numero')} descartada (reverso sin ID)")
                    break

                grp = DocumentGroup(f"DOC-{counter:03d}")
                if "BACK" in cara_actual:
                    grp.back_page = p_actual
                else:
                    grp.front_page = p_actual
                grp.tipo_documento = p_actual.get("tipo_documento", "CEDULA_CIUDADANIA")
                grp.numero_identificacion = id_actual
                grp.grouping_confidence = 0.90
                grp.reasons = ["Documento de una sola página"]
                grp.status = "VALID" if (id_actual and "UNKNOWN" not in str(grp.tipo_documento)) else "REVIEW_REQUIRED"
                if id_actual:
                    ids_vistos[id_actual] = grp.group_id
                grupos.append(grp)
                counter += 1
                break

            # Caso 2: Hay una página siguiente p_siguiente (i + 1)
            p_siguiente = paginas[i + 1]
            cara_sig = p_siguiente.get("cara", "UNKNOWN")
            raw_id_sig = p_siguiente.get("numero_identificacion")
            id_sig = validador.limpiar_identificacion(raw_id_sig)

            # ¿Son Frente y Reverso consecutivos de la misma persona?
            mismo_id = bool(id_actual and id_sig and id_actual == id_sig)
            ids_contradictorios = bool(id_actual and id_sig and id_actual != id_sig)

            # Se unen en 1 solo grupo si:
            # a) Tienen el mismo ID explícito
            # b) p_actual es Frente (o 2 caras) y p_siguiente es Reverso / Desconocido, SIN IDs contradictorios
            es_par_consecutivo = (
                mismo_id or
                (
                    ("FRONT" in cara_actual or cara_actual == "CEDULA_AMBOS_LADOS") and
                    ("BACK" in cara_sig or cara_sig == "UNKNOWN") and
                    not ids_contradictorios
                )
            )

            if es_par_consecutivo:
                id_unificado = id_actual or id_sig
                # Si el ID ya existe en un grupo previo → fusionar
                if id_unificado and id_unificado in ids_vistos:
                    grp_existente = next((g for g in grupos if g.group_id == ids_vistos[id_unificado]), None)
                    if grp_existente:
                        grp_existente.other_pages.extend([p_actual, p_siguiente])
                        i += 2
                        continue

                grp = DocumentGroup(f"DOC-{counter:03d}")
                grp.front_page = p_actual
                grp.back_page = p_siguiente
                grp.tipo_documento = p_actual.get("tipo_documento", "CEDULA_CIUDADANIA")
                grp.numero_identificacion = id_unificado
                grp.grouping_confidence = 0.98 if mismo_id else 0.92
                grp.reasons = [f"Frente (Pág {p_actual.get('pagina_numero')}) + Reverso (Pág {p_siguiente.get('pagina_numero')}) consecutivos unificados"]
                grp.status = "VALID" if (id_unificado and "UNKNOWN" not in str(grp.tipo_documento)) else "REVIEW_REQUIRED"
                if id_unificado:
                    ids_vistos[id_unificado] = grp.group_id
                grupos.append(grp)
                counter += 1
                i += 2  # Consumir ambas páginas (Frente + Reverso)
                continue

            # Caso 3: Página individual (1 página = 1 persona)
            if id_actual and id_actual in ids_vistos:
                grp_existente = next((g for g in grupos if g.group_id == ids_vistos[id_actual]), None)
                if grp_existente:
                    grp_existente.other_pages.append(p_actual)
                    i += 1
                    continue

            # Si es un reverso huérfano sin ID en un PDF multipágina → descartar
            if total_pags > 1 and "BACK" in cara_actual and not id_actual:
                logger.info(f"[DocumentPairingService] Reverso Pág {p_actual.get('pagina_numero')} sin ID descartado")
                i += 1
                continue

            grp = DocumentGroup(f"DOC-{counter:03d}")
            if "BACK" in cara_actual:
                grp.back_page = p_actual
            else:
                grp.front_page = p_actual
            grp.tipo_documento = p_actual.get("tipo_documento", "CEDULA_CIUDADANIA")
            grp.numero_identificacion = id_actual
            grp.grouping_confidence = 0.90
            grp.reasons = ["Cédula en una sola página"]
            grp.status = "VALID" if (id_actual and "UNKNOWN" not in str(grp.tipo_documento)) else "REVIEW_REQUIRED"
            if id_actual:
                ids_vistos[id_actual] = grp.group_id
            grupos.append(grp)
            counter += 1
            i += 1

        logger.info(
            f"[DocumentPairingService] {len(paginas_clasificadas)} página(s) → "
            f"{len(grupos)} grupo(s) de persona(s) unificada(s). "
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
