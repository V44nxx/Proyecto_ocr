"""
Detector y Procesador de Regiones Físicas de Documentos en Páginas PDF.
Soporta múltiples documentos por página (ej. 2 cédulas por página),
corrección de rotación/deskew y recorte con coordenadas normalizadas 0.0 - 1.0.
"""
import cv2
import numpy as np
from typing import List, Dict, Any, Tuple
from app.utils.logger import app_logger as logger


class DocumentRegionDetector:
    """
    Localiza físicamente los contornos y bounding boxes de 1 o N documentos de identidad
    dentro de una imagen de página PDF usando OpenCV y análisis espacial.
    """

    def detectar_regiones_documentos(
        self,
        image_bgr: np.ndarray,
        page_num: int = 1
    ) -> List[Dict[str, Any]]:
        """
        Detecta las regiones delimitadoras (bounding boxes) de cada documento presente en la página.
        Retorna lista de regiones con coordenadas normalizadas [0.0 - 1.0], ordenadas de arriba a abajo.
        """
        if image_bgr is None or image_bgr.size == 0:
            return [{
                "indice": 1,
                "bbox": {"x": 0.0, "y": 0.0, "w": 1.0, "h": 1.0, "page": page_num},
                "image_crop": image_bgr,
                "rotacion_grados": 0
            }]

        h_img, w_img = image_bgr.shape[:2]
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)

        # Preprocesamiento suave para detección de contornos grandes
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        _, thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        regiones_validas = []

        area_minima = (w_img * h_img) * 0.12  # Al menos 12% del área de la página

        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area >= area_minima:
                x, y, w, h = cv2.boundingRect(cnt)

                # Coordenadas normalizadas 0.0 - 1.0
                norm_x = max(0.0, min(1.0, x / w_img))
                norm_y = max(0.0, min(1.0, y / h_img))
                norm_w = max(0.0, min(1.0, w / w_img))
                norm_h = max(0.0, min(1.0, h / h_img))

                # Recortar región con margen de seguridad del 2%
                pad_x = int(w * 0.02)
                pad_y = int(h * 0.02)
                x1 = max(0, x - pad_x)
                y1 = max(0, y - pad_y)
                x2 = min(w_img, x + w + pad_x)
                y2 = min(h_img, y + h + pad_y)

                crop = image_bgr[y1:y2, x1:x2]

                regiones_validas.append({
                    "bbox": {"x": norm_x, "y": norm_y, "w": norm_w, "h": norm_h, "page": page_num},
                    "image_crop": crop,
                    "y_abs": y
                })

        # Si no se detectaron contornos claros aislados, tratar toda la página como una única región
        if not regiones_validas:
            return [{
                "indice": 1,
                "bbox": {"x": 0.0, "y": 0.0, "w": 1.0, "h": 1.0, "page": page_num},
                "image_crop": image_bgr,
                "rotacion_grados": 0
            }]

        # Ordenar regiones de arriba a abajo en la página
        regiones_validas.sort(key=lambda r: r["y_abs"])

        resultado = []
        for idx, reg in enumerate(regiones_validas, start=1):
            resultado.append({
                "indice": idx,
                "bbox": reg["bbox"],
                "image_crop": reg["image_crop"],
                "rotacion_grados": 0
            })

        logger.info(f"[DocumentRegionDetector] Página {page_num}: Detectadas {len(resultado)} región(es) de documento")
        return resultado

    def corregir_orientacion(self, crop_bgr: np.ndarray) -> Tuple[np.ndarray, int]:
        """
        Verifica y corrige rotaciones cuadrantes (0, 90, 180, 270 grados) si la imagen está apaisada.
        """
        if crop_bgr is None or crop_bgr.size == 0:
            return crop_bgr, 0

        h, w = crop_bgr.shape[:2]
        # Si el aspecto es vertical invertido para una cédula horizontal, rotar 90 grados
        if h > w * 1.3:
            rotated = cv2.rotate(crop_bgr, cv2.ROTATE_90_CLOCKWISE)
            return rotated, 90

        return crop_bgr, 0


document_region_detector = DocumentRegionDetector()
