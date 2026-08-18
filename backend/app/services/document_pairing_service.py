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
    """

    def agrupar_paginas(self, paginas_clasificadas: List[Dict[str, Any]]) -> List[DocumentGroup]:
        """
        Toma la lista de páginas procesadas y clasificadas y las agrupa en objetos DocumentGroup.
        """
        if not paginas_clasificadas:
            return []

        grupos: List[DocumentGroup] = []
        paginas_pendientes = list(paginas_clasificadas)
        counter = 1

        # 1. Separar páginas CEDULA_AMBOS_LADOS (2 caras en 1 sola página), FRONT, BACK y UNKNOWN
        both_sides = [p for p in paginas_pendientes if p.get("cara") == "CEDULA_AMBOS_LADOS"]
        fronts = [p for p in paginas_pendientes if "FRONT" in p.get("cara", "") and p not in both_sides]
        backs = [p for p in paginas_pendientes if "BACK" in p.get("cara", "") and p not in both_sides]
        unknowns = [p for p in paginas_pendientes if p.get("cara") == "UNKNOWN" and p not in both_sides]

        # Control de IDs asignados para detectar duplicados
        ids_vistos: Dict[str, str] = {}

        # 2. Procesar páginas de 2 caras simultáneas (CEDULA_AMBOS_LADOS)
        for b_side in both_sides:
            grp = DocumentGroup(f"DOC-{counter:03d}")
            grp.front_page = b_side
            grp.back_page = b_side
            grp.tipo_documento = b_side.get("tipo_documento", "CEDULA_CIUDADANIA")
            grp.numero_identificacion = b_side.get("numero_identificacion")
            grp.grouping_confidence = 0.99
            grp.reasons = ["Documento de 2 caras escaneado en una misma página (Frente + Reverso)"]
            grp.status = "VALID" if grp.numero_identificacion else "REVIEW_REQUIRED"
            grupos.append(grp)
            counter += 1

        # 3. Iterar sobre cada FRONT y buscar su mejor BACK compatible
        # Umbral base: 0.35 (tolerante para PDFs sin MRZ, cédulas amarillas en 2 páginas)
        UMBRAL_MIN_SCORE = 0.35

        # Ordenar f_pages por número de página ascendente
        fronts_ordenados = sorted(list(fronts), key=lambda p: p.get("pagina_numero", 1))

        for f_page in fronts_ordenados:
            p_front = f_page.get("pagina_numero", 1)
            id_front = f_page.get("numero_identificacion")

            grp = DocumentGroup(f"DOC-{counter:03d}")
            grp.front_page = f_page
            grp.tipo_documento = f_page.get("tipo_documento", "CEDULA_CIUDADANIA")
            grp.numero_identificacion = id_front

            best_back = None
            best_score = 0.0
            best_reasons = []

            # Prioridad 1: Buscar si la página siguiente p_front + 1 está en backs
            next_page_back = next((b for b in backs if b.get("pagina_numero") == p_front + 1), None)
            if next_page_back:
                score, reasons = self.evaluar_asociacion(f_page, next_page_back)
                if score >= 0.20:
                    best_back = next_page_back
                    best_score = min(0.99, max(0.85, score + 0.30))
                    best_reasons = reasons + ["Emparejamiento de alta certeza: páginas consecutivas (Pág N -> Pág N+1)"]

            # Prioridad 2: Si no hubo back consecutivo, buscar si la página siguiente p_front + 1 está en unknowns
            if not best_back:
                next_page_unk = next((u for u in unknowns if u.get("pagina_numero") == p_front + 1), None)
                if next_page_unk:
                    best_back = next_page_unk
                    best_score = 0.75
                    best_reasons = [f"Reverso complementario inferido por secuencia consecutiva (Pág {p_front} y {p_front + 1})"]
                    unknowns.remove(next_page_unk)

            # Prioridad 3: Buscar en la lista general de backs por mejor puntuación
            if not best_back:
                for b_page in list(backs):
                    score, reasons = self.evaluar_asociacion(f_page, b_page)
                    p_back = b_page.get("pagina_numero", 2)
                    dist_pag = abs(p_back - p_front)
                    if dist_pag == 1:
                        score = min(0.99, score + 0.25)
                        reasons = reasons + ["Bonus: páginas consecutivas (+0.25)"]
                    if score > best_score and score >= UMBRAL_MIN_SCORE:
                        best_score = score
                        best_back = b_page
                        best_reasons = reasons

            if best_back:
                grp.back_page = best_back
                grp.grouping_confidence = best_score
                grp.reasons = best_reasons
                if best_back in backs:
                    backs.remove(best_back)
            else:
                # Documento de 1 sola página FRONT (ej. escaneo frontal)
                grp.grouping_confidence = f_page.get("confianza", 0.90)
                grp.reasons = ["Documento de una sola cara (FRONT)"]
                grp.status = "VALID" if grp.numero_identificacion else "REVIEW_REQUIRED"

            # Verificar duplicados por número de cédula
            if id_front:
                if id_front in ids_vistos:
                    grp.status = "DUPLICATE_REVIEW_REQUIRED"
                    grp.reasons.append(f"Número de identificación '{id_front}' presente en grupo {ids_vistos[id_front]}")
                else:
                    ids_vistos[id_front] = grp.group_id

            grupos.append(grp)
            counter += 1

        # Pairing optimista: si quedan exactamente 1 FRONT huérfano + 1 BACK huérfano
        grupos_fronts_huerfanos = [g for g in grupos if g.front_page and not g.back_page]
        if len(grupos_fronts_huerfanos) == 1 and len(backs) == 1:
            grp_huerfano = grupos_fronts_huerfanos[0]
            b_solo = backs[0]
            grp_huerfano.back_page = b_solo
            grp_huerfano.grouping_confidence = max(grp_huerfano.grouping_confidence, 0.70)
            grp_huerfano.reasons.append("Pairing optimista: único FRONT + único BACK disponibles en PDF")
            if grp_huerfano.status == "REVIEW_REQUIRED" and grp_huerfano.numero_identificacion:
                grp_huerfano.status = "VALID"
            backs.clear()

        # 3. Procesar BACKs huérfanos que no encontraron FRONT (solo si tienen cédula/MRZ extraíble)
        for b_page in backs:
            id_back = b_page.get("numero_identificacion")
            # Si el reverso tiene una cédula ya vista en un grupo anterior, fusionarlo
            if id_back and id_back in ids_vistos:
                grp_prev = next((g for g in grupos if g.group_id == ids_vistos[id_back]), None)
                if grp_prev and not grp_prev.back_page:
                    grp_prev.back_page = b_page
                    grp_prev.reasons.append(f"Reverso tardío asociado por coincidencia de cédula '{id_back}'")
                    continue

            grp = DocumentGroup(f"DOC-{counter:03d}")
            grp.back_page = b_page
            grp.tipo_documento = b_page.get("tipo_documento", "CEDULA_CIUDADANIA")
            grp.numero_identificacion = id_back
            grp.grouping_confidence = 0.70
            grp.reasons = ["Reverso huérfano (sin frente asociado)"]
            grp.status = "REVIEW_REQUIRED"
            grupos.append(grp)
            counter += 1

        # 4. Procesar UNKNOWNs
        for u_page in unknowns:
            grp = DocumentGroup(f"DOC-{counter:03d}")
            grp.other_pages.append(u_page)
            grp.tipo_documento = "UNKNOWN"
            grp.grouping_confidence = 0.30
            grp.reasons = ["Página no reconocida como documento válido"]
            grp.status = "REVIEW_REQUIRED"
            grupos.append(grp)
            counter += 1

        logger.info(f"[DocumentPairingService] Agrupadas {len(paginas_clasificadas)} páginas en {len(grupos)} grupo(s) de documentos")
        return grupos

    def evaluar_asociacion(self, f_page: Dict[str, Any], b_page: Dict[str, Any]) -> tuple[float, List[str]]:
        """
        Calcula la puntuación de asociación evidencial (0.0 a 1.0) entre una página FRONT y una BACK.
        """
        reasons = []
        score = 0.0

        id_front = f_page.get("numero_identificacion")
        id_back = b_page.get("numero_identificacion")

        # 1. Coincidencia de Número de Cédula (MRZ en Reverso vs Cédula en Frente) -> PESO MUY ALTO
        if id_front and id_back and id_front == id_back:
            score += 0.50
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
