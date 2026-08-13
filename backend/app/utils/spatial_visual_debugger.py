"""
Herramienta de Depuración Visual 2D para Extracción Espacial OCR.
Dibuja y genera imágenes PNG anotadas con las regiones 2D, cajas de etiquetas, candidatos aceptados y rechazados.
Colores:
  - AZUL: Etiquetas detectadas (LABEL)
  - VERDE: Candidatos ACEPTADOS (ACCEPTED)
  - ROJO: Candidatos RECHAZADOS / VETADOS (REJECTED / WRONG_REGION)
  - NARANJA: Franjas y Regiones 2D calculadas (REGION_2D)
"""
import os
from typing import Dict, Any, List, Optional
from app.utils.logger import app_logger as logger

try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


class SpatialVisualDebugger:
    """Generador de artefactos visuales de depuración espacial 2D."""

    def __init__(self, output_dir: str = "exports/debug_visual"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def generar_imagen_debug_2d(
        self,
        page_num: int,
        lines: List[Any],
        etiquetas: Dict[str, Any],
        evaluaciones_por_campo: Dict[str, List[Dict[str, Any]]],
        regiones_2d: Dict[str, Dict[str, float]],
        image_path: Optional[str] = None,
        image_width: int = 1000,
        image_height: int = 1400
    ) -> Optional[str]:
        """
        Genera un PNG de la página anotando las regiones, etiquetas y candidatos.
        """
        if not PIL_AVAILABLE:
            logger.warning("[SpatialVisualDebugger] Pillow no está instalado, omitiendo debug visual")
            return None

        try:
            if image_path and os.path.exists(image_path):
                img = Image.open(image_path).convert("RGB")
                w_img, h_img = img.size
            else:
                w_img, h_img = image_width, image_height
                img = Image.new("RGB", (w_img, h_img), color=(245, 247, 250))

            draw = ImageDraw.Draw(img)

            # 1. Dibujar Regiones 2D Calculadas (Naranja traslúcido/punteado)
            for campo, reg in regiones_2d.items():
                x1 = int(reg.get("x_min", 0.0) * w_img)
                y1 = int(reg.get("y_min", 0.0) * h_img)
                x2 = int(reg.get("x_max", 1.0) * w_img)
                y2 = int(reg.get("y_max", 1.0) * h_img)
                draw.rectangle([x1, y1, x2, y2], outline=(255, 140, 0), width=3)
                draw.text((x1 + 5, y1 + 5), f"REGION 2D: {campo.upper()}", fill=(255, 140, 0))

            # 2. Dibujar Etiquetas (AZUL)
            for campo, et_obj in etiquetas.items():
                if hasattr(et_obj, "bbox"):
                    b = et_obj.bbox
                    x1, y1 = int(b.x * w_img), int(b.y * h_img)
                    x2, y2 = int((b.x + b.w) * w_img), int((b.y + b.h) * h_img)
                    draw.rectangle([x1, y1, x2, y2], outline=(0, 102, 204), width=3)
                    draw.text((x1, max(0, y1 - 15)), f"LABEL: {campo.upper()}", fill=(0, 102, 204))

            # 3. Dibujar Candidatos Aceptados (VERDE) y Rechazados (ROJO)
            for campo, evals in evaluaciones_por_campo.items():
                for ev in evals:
                    cand = ev.get("candidate")
                    if not cand:
                        continue
                    b = cand.bbox
                    x1, y1 = int(b.x * w_img), int(b.y * h_img)
                    x2, y2 = int((b.x + b.w) * w_img), int((b.y + b.h) * h_img)

                    is_winner = ev.get("is_winner", False)
                    is_valid = ev.get("is_valid", False)

                    if is_winner:
                        color = (0, 180, 80)  # Verde brillante
                        prefix = f"ACCEPTED [{campo.upper()}]"
                    elif is_valid:
                        color = (200, 160, 0)  # Amarillo/Dorado
                        prefix = "COMPATIBLE"
                    else:
                        color = (220, 50, 50)  # Rojo
                        prefix = f"REJECTED: {ev.get('relation', 'WRONG')}"

                    draw.rectangle([x1, y1, x2, y2], outline=color, width=2)
                    label_txt = f"{prefix}: {cand.text[:20]} (sc={round(ev.get('spatial_score', 0), 2)})"
                    draw.text((x1, max(0, y1 - 12)), label_txt, fill=color)

            filename = f"page_{page_num}_debug_2d.png"
            output_filepath = os.path.join(self.output_dir, filename)
            img.save(output_filepath)
            logger.info(f"[SpatialVisualDebugger] Artefacto visual de depuración generado: {output_filepath}")
            return output_filepath

        except Exception as e:
            logger.error(f"[SpatialVisualDebugger] Error al generar imagen de depuración: {str(e)}")
            return None


spatial_visual_debugger = SpatialVisualDebugger()
