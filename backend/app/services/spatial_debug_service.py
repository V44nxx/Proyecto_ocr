"""
Servicio de Depuración Visual Espacial (SpatialDebugService).
Genera los rectángulos y estados de cajas delimitadoras (LABEL, CANDIDATE, ACCEPTED, REJECTED)
para inspección visual y auditoría de decisiones geométricas.
"""
from typing import Dict, Any, List
from app.services.spatial_field_extractor import spatial_field_extractor, SpatialBoundingBox


class SpatialDebugService:
    """
    Servicio para inspección y trazabilidad visual de coordenadas y decisiones espaciales.
    """

    def generar_reporte_debug(self, lines: List[Any], page_num: int = 1) -> Dict[str, Any]:
        """
        Analiza las líneas de una página y devuelve las cajas clasificadas por tipo y color.
        """
        if not lines:
            return {"page": page_num, "boxes": []}

        etiquetas = spatial_field_extractor.identificar_etiquetas_espaciales(lines, page_num)
        boxes = []

        # 1. Registrar cajas de Etiquetas (Color Azul / LABEL)
        for campo, et_cand in etiquetas.items():
            boxes.append({
                "type": "LABEL",
                "field": campo,
                "text": et_cand.text,
                "bbox": et_cand.bbox.to_dict(),
                "status": "DETECTED",
                "color": "#3B82F6",  # Azul
                "reason": f"Etiqueta del campo '{campo}'"
            })

        # 2. Registrar decisiones para cada campo de interés
        campos_evaluar = ["identificacion", "apellidos", "nombres", "fecha_nacimiento", "fecha_expedicion", "lugar_expedicion", "sexo"]

        for campo in campos_evaluar:
            res_campo = spatial_field_extractor.extraer_campo_con_layout(campo, lines, page_num)

            if res_campo.get("value") and res_campo.get("value_bbox"):
                boxes.append({
                    "type": "ACCEPTED",
                    "field": campo,
                    "text": res_campo["value"],
                    "bbox": res_campo["value_bbox"],
                    "status": res_campo.get("status", "VALID"),
                    "color": "#10B981",  # Verde
                    "spatial_relation": res_campo.get("spatial_relation"),
                    "spatial_score": res_campo.get("spatial_score"),
                    "reason": res_campo.get("reason", "Candidato aceptado por geometría espacial")
                })

        # 3. Registrar candidatos descartados por Veto Espacial o Ruido (Color Rojo / REJECTED)
        for idx, line in enumerate(lines):
            txt = getattr(line, "text", "").strip()
            if not txt:
                continue

            x = getattr(line, "x", 0.0)
            y = getattr(line, "y", 0.0)
            w = getattr(line, "w", 0.0)
            h = getattr(line, "h", 0.0)
            bbox = SpatialBoundingBox(x, y, w, h, page_num)

            # Verificar si ya fue registrado como LABEL o ACCEPTED
            registrado = any(
                b["bbox"]["x"] == round(bbox.x, 4) and b["bbox"]["y"] == round(bbox.y, 4)
                for b in boxes
            )

            if not registrado:
                # Determinar si fue vetado por ruido o fuera de región
                es_ruido = bool(spatial_field_extractor.NO_NOMBRE_HEADER.search(txt))
                boxes.append({
                    "type": "REJECTED",
                    "field": "desconocido",
                    "text": txt,
                    "bbox": bbox.to_dict(),
                    "status": "REJECTED",
                    "color": "#EF4444" if es_ruido else "#F59E0B",  # Rojo si es ruido, Naranja si está fuera de región
                    "reason": "VETO ESPACIAL: Encabezado/ruido detectado" if es_ruido else "Fuera de región de campo"
                })

        return {
            "page": page_num,
            "total_boxes": len(boxes),
            "boxes": boxes
        }


spatial_debug_service = SpatialDebugService()
