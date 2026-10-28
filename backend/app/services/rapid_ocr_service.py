"""
Servicio RapidOCR (ONNX Runtime)
Motor OCR local de alto rendimiento basado en redes neuronales profundas (DBNet + SVTR).
Ideal para ejecución en servidores VPS y contingencia offline sin dependencias externas del sistema.
"""
import os
import threading
import time
from typing import Optional, List, Dict, Any, Tuple
import numpy as np

from app.utils.logger import app_logger as logger
from app.config import settings
from app.services.google_document_ai_service import (
    OCRToken, OCRLine, OCRPageData, StructuredDocumentAIResult
)
from app.utils.name_cleaner import separar_nombres_pegados_en_linea


class RapidOCRService:
    """
    Servicio que encapsula el motor RapidOCR ONNX Runtime.
    Proporciona extracción de texto plano y generación de layout espacial estructurado (bounding boxes 2D).
    """

    # Solo se lee la parte de la hoja que tiene algo impreso. Con la hoja entera achicada a RAPID_OCR_LADO_MAXIMO,
    # una cédula que ocupa parte de la hoja quedaba tan pequeña que las palabras en negrita se pegaban
    # («SANTIAGOMANUEL»); recortada, esos mismos píxeles son para la cédula y no se busca texto en el blanco
    UMBRAL_TINTA = 210        # gris por debajo del cual un punto cuenta como impreso
    FRACCION_MINIMA = 0.005   # una fila o columna con menos de esto impreso es blanco o polvo
    MARGEN = 0.03             # margen alrededor de lo impreso, en fracción de la hoja
    AREA_MAXIMA = 0.85        # si lo impreso ocupa casi toda la hoja, no vale la pena recortar

    @classmethod
    def zona_con_contenido(cls, img_np: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
        """(x0, y0, x1, y1) de lo impreso en la hoja, o None si no hay nada que recortar."""
        import cv2

        alto, ancho = img_np.shape[:2]
        gris = cv2.cvtColor(img_np, cv2.COLOR_BGR2GRAY) if img_np.ndim == 3 else img_np
        paso = 4
        chica = cv2.resize(gris, (max(1, ancho // paso), max(1, alto // paso)), interpolation=cv2.INTER_AREA)
        tinta = chica < cls.UMBRAL_TINTA
        filas = np.flatnonzero(tinta.mean(axis=1) > cls.FRACCION_MINIMA)
        columnas = np.flatnonzero(tinta.mean(axis=0) > cls.FRACCION_MINIMA)
        if not len(filas) or not len(columnas):
            return None
        margen_x, margen_y = int(ancho * cls.MARGEN), int(alto * cls.MARGEN)
        x0 = max(0, int(columnas[0]) * paso - margen_x)
        x1 = min(ancho, (int(columnas[-1]) + 1) * paso + margen_x)
        y0 = max(0, int(filas[0]) * paso - margen_y)
        y1 = min(alto, (int(filas[-1]) + 1) * paso + margen_y)
        if (x1 - x0) * (y1 - y0) > cls.AREA_MAXIMA * ancho * alto:
            return None
        return x0, y0, x1, y1

    # Lecturas a la vez: RapidOCR usa la CPU, así que más hilos que núcleos solo se estorban. Importa cuando el OCR
    # lee varias páginas en paralelo pensando en Document AI y este se cae a mitad de la ficha
    LECTURAS_A_LA_VEZ = max(1, min(os.cpu_count() or 1, 4))

    def __init__(self):
        self._engine = None
        self._disponible = False
        self._turnos = threading.BoundedSemaphore(self.LECTURAS_A_LA_VEZ)
        self._inicializar()

    def _inicializar(self):
        """Inicializa el motor RapidOCR ONNX en memoria."""
        if not getattr(settings, "RAPID_OCR_ENABLED", True):
            logger.info("[RapidOCR] Deshabilitado por configuración (RAPID_OCR_ENABLED=False)")
            self._disponible = False
            return

        try:
            from rapidocr_onnxruntime import RapidOCR
            self._engine = RapidOCR()
            self._disponible = True
            logger.info("[RapidOCR] Motor neural ONNX Runtime inicializado correctamente")
        except Exception as e:
            logger.warning(f"[RapidOCR] No se pudo inicializar RapidOCR: {e}")
            self._disponible = False

    @property
    def disponible(self) -> bool:
        """Indica si el motor RapidOCR está listo para ser utilizado."""
        return self._disponible and self._engine is not None

    def procesar_imagen(
        self, img_np: np.ndarray, pagina_num: int = 1
    ) -> tuple[str, float, Optional[StructuredDocumentAIResult]]:
        """
        Procesa una imagen con RapidOCR y devuelve:
          - Texto concatenado plano
          - Confianza promedio (0.0 a 100.0)
          - StructuredDocumentAIResult estructurado con coordenadas 2D normalizadas
        """
        if not self.disponible:
            return "", 0.0, None

        inicio = time.time()
        try:
            import cv2

            height, width = img_np.shape[:2]

            # 1. Solo la zona impresa de la hoja (ver zona_con_contenido)
            zona = self.zona_con_contenido(img_np)
            x_ini, y_ini = (zona[0], zona[1]) if zona else (0, 0)
            img_zona = img_np[zona[1]:zona[3], zona[0]:zona[2]] if zona else img_np
            alto_zona, ancho_zona = img_zona.shape[:2]

            # 2. Optimización de resolución: si supera el lado máximo, escalar proporcionalmente
            # (menos píxeles para la detección; ver RAPID_OCR_LADO_MAXIMO en config.py)
            lado_maximo = int(getattr(settings, "RAPID_OCR_LADO_MAXIMO", 1250))
            max_side = max(alto_zona, ancho_zona)
            if max_side > lado_maximo:
                scale = float(lado_maximo) / float(max_side)
                new_w, new_h = max(1, int(round(ancho_zona * scale))), max(1, int(round(alto_zona * scale)))
                img_proc = cv2.resize(img_zona, (new_w, new_h), interpolation=cv2.INTER_AREA)
                escala_x, escala_y = new_w / ancho_zona, new_h / alto_zona
            else:
                img_proc = np.ascontiguousarray(img_zona)
                escala_x = escala_y = 1.0

            # RapidOCR procesa imágenes en formato BGR/RGB numpy array
            with self._turnos:
                results, elapse_list = self._engine(img_proc)
            tiempo_ms = (time.time() - inicio) * 1000

            if not results:
                logger.info(f"[RapidOCR] Página {pagina_num}: No se detectó texto en la imagen ({tiempo_ms:.1f}ms)")
                return "", 0.0, None

            lineas_texto: List[str] = []
            ocr_lines: List[OCRLine] = []
            ocr_tokens: List[OCRToken] = []
            confianzas: List[float] = []

            for item in results:
                # Cada item es: [box_points, text, confidence]
                # box_points: [[x1, y1], [x2, y2], [x3, y3], [x4, y4]]
                box_pts, text, conf = item
                # RapidOCR suele pegar las palabras en negrita: «SEBASTIANMANUEL» sale como «SEBASTIAN MANUEL»
                text_clean = separar_nombres_pegados_en_linea(str(text).strip())
                if not text_clean:
                    continue

                lineas_texto.append(text_clean)
                conf_val = float(conf)
                confianzas.append(conf_val)

                # Bounding box normalizado (0.0 a 1.0) sobre la hoja completa, no sobre el recorte achicado
                xs = [x_ini + pt[0] / escala_x for pt in box_pts]
                ys = [y_ini + pt[1] / escala_y for pt in box_pts]
                min_x, max_x = max(0, min(xs)), min(width, max(xs))
                min_y, max_y = max(0, min(ys)), min(height, max(ys))

                norm_x = min_x / width if width > 0 else 0.0
                norm_y = min_y / height if height > 0 else 0.0
                norm_w = (max_x - min_x) / width if width > 0 else 1.0
                norm_h = (max_y - min_y) / height if height > 0 else 1.0

                # Crear tokens para cada palabra en la línea
                palabras = text_clean.split()
                line_tokens: List[OCRToken] = []
                num_pals = max(1, len(palabras))
                w_pal = norm_w / num_pals

                for idx, pal in enumerate(palabras):
                    pal_x = norm_x + (idx * w_pal)
                    token = OCRToken(
                        text=pal,
                        confidence=conf_val,
                        page_number=pagina_num,
                        x=pal_x,
                        y=norm_y,
                        w=w_pal,
                        h=norm_h,
                    )
                    line_tokens.append(token)
                    ocr_tokens.append(token)

                line_obj = OCRLine(
                    text=text_clean,
                    confidence=conf_val,
                    page_number=pagina_num,
                    x=norm_x,
                    y=norm_y,
                    w=norm_w,
                    h=norm_h,
                    tokens=line_tokens,
                )
                ocr_lines.append(line_obj)

            texto_completo = "\n".join(lineas_texto)
            confianza_promedio = (sum(confianzas) / len(confianzas) * 100.0) if confianzas else 0.0

            page_data = OCRPageData(
                page_number=pagina_num,
                width=float(width),
                height=float(height),
                text=texto_completo,
                lines=ocr_lines,
                tokens=ocr_tokens,
            )

            res_estructurado = StructuredDocumentAIResult(
                text=texto_completo,
                tiempo_ms=tiempo_ms,
                pages=[page_data],
            )

            logger.info(
                f"[RapidOCR] Página {pagina_num}: {len(lineas_texto)} líneas, "
                f"{len(ocr_tokens)} palabras, confianza={confianza_promedio:.1f}%, tiempo={tiempo_ms:.1f}ms"
            )

            return texto_completo, confianza_promedio, res_estructurado

        except Exception as e:
            logger.error(f"[RapidOCR] Error procesando imagen en página {pagina_num}: {e}")
            return "", 0.0, None


# Instancia singleton del servicio
rapid_ocr_service = RapidOCRService()
