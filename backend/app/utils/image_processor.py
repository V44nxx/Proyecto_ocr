"""
Procesamiento de imágenes con OpenCV para optimizar OCR
Pipeline: PDF → Imagen → Preprocesamiento → OCR

CAMBIOS v2 (optimización precisión):
  - FIX CRÍTICO: eliminado _denoise duplicado (bug: medianBlur en imagen 3D
    causaba "assertion _src0.dims() <= 2"). Ahora existe UNA sola definición.
  - Pipeline garantiza imagen 2D uint8 en CADA paso.
  - Validación de tipo en preprocess() — acepta list, ndarray o lanza TypeError.
  - CLAHE: clipLimit 2.0→3.0, tileGridSize 8×8→6×6 (más contraste local).
  - Threshold: blockSize 11→15, C 2→8 (texto más nítido en fondos irregulares).
  - NUEVO: _morphology_cleanup() post-binarización elimina ruido residual.
  - preprocess() devuelve imagen 2D — Tesseract no necesita COLOR_GRAY2BGR.
"""
import cv2
import numpy as np
from pathlib import Path
from typing import List, Tuple
import fitz  # PyMuPDF
from app.utils.logger import app_logger as logger
from app.config import settings


class ImageProcessor:
    """
    Pipeline de preprocesamiento de imágenes para OCR óptimo.
    Aplica técnicas de visión computacional para mejorar la precisión
    del reconocimiento de texto en cédulas colombianas.
    """

    def __init__(self):
        self.dpi = settings.IMAGE_DPI
        self.min_width = settings.IMAGE_MIN_WIDTH

    # ──────────────────────────────────────────
    # CONVERSIÓN PDF → IMÁGENES
    # ──────────────────────────────────────────
    def _pixmap_to_numpy(self, pixmap) -> np.ndarray:
        """Convierte un pixmap de PyMuPDF a un numpy array BGR."""
        img = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(
            pixmap.height, pixmap.width, pixmap.n
        )
        if pixmap.n == 4:
            img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
        elif pixmap.n == 1:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        elif pixmap.n == 3:
            img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        return img

    pixmap_to_numpy = _pixmap_to_numpy

    def pdf_to_images(self, pdf_path: str) -> Tuple[List[np.ndarray], int]:
        """
        Convierte un PDF a lista de imágenes numpy array.
        Usa PyMuPDF (fitz) para renderizado de alta calidad.

        Returns:
            Tupla (lista_de_imagenes, total_paginas)
        """
        logger.info(f"Convirtiendo PDF a imágenes: {pdf_path}")
        images = []

        try:
            doc = fitz.open(pdf_path)
            total_paginas = len(doc)
            logger.info(f"PDF con {total_paginas} páginas detectadas")

            zoom = self.dpi / 72  # 72 DPI es el estándar de fitz
            matrix = fitz.Matrix(zoom, zoom)

            for page_num in range(total_paginas):
                page = doc.load_page(page_num)
                pixmap = page.get_pixmap(matrix=matrix, alpha=False)

                img = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(
                    pixmap.height, pixmap.width, pixmap.n
                )

                if pixmap.n == 3:
                    img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
                elif pixmap.n == 4:
                    img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
                elif pixmap.n == 1:
                    img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

                images.append(img)
                logger.debug(f"Página {page_num + 1}/{total_paginas} convertida: {img.shape}")

            doc.close()
            return images, total_paginas

        except Exception as e:
            logger.error(f"Error convirtiendo PDF: {e}")
            raise

    # ──────────────────────────────────────────
    # PIPELINE DE PREPROCESAMIENTO
    # ──────────────────────────────────────────
    def preprocess(self, image) -> np.ndarray:
        """
        Pipeline completo de preprocesamiento para OCR sobre cédulas colombianas.

        Acepta:
          - np.ndarray BGR (3 canales)
          - np.ndarray grises (2D)
          - Primer elemento de una lista (salvaguarda si se pasa image[i] mal)

        Devuelve:
          - np.ndarray 2D uint8 listo para pytesseract.image_to_string()
            Tesseract trabaja con escala de grises o binario puro — no BGR.

        Pasos:
          1. Validar tipo y garantizar np.ndarray
          2. Convertir a escala de grises (2D uint8)
          3. Resize si ancho < min_width
          4. Denoise (medianBlur — única definición)
          5. Deskew (corrección de inclinación)
          6. CLAHE (contraste local adaptativo mejorado)
          7. Umbralización adaptativa (blockSize y C ajustados)
          8. Morphology cleanup (elimina ruido residual)
        """
        # ── PASO 0: validar tipo ───────────────────────────────────────────
        if isinstance(image, list):
            if len(image) == 0:
                raise ValueError("preprocess() recibió lista vacía")
            image = image[0]

        if not isinstance(image, np.ndarray):
            raise TypeError(
                f"preprocess() requiere np.ndarray, recibió {type(image).__name__}"
            )

        # ── PASO 1: Escala de grises ───────────────────────────────────────
        img = self._to_grayscale(image)

        # ── PASO 2: Resize ────────────────────────────────────────────────
        img = self._resize_if_needed(img)

        # ── PASO 3: Denoise ───────────────────────────────────────────────
        img = self._denoise(img)

        # ── PASO 4: Deskew ────────────────────────────────────────────────
        img = self._deskew(img)

        # ── PASO 5: CLAHE ─────────────────────────────────────────────────
        img = self._enhance_contrast(img)

        # ── PASO 6: Umbralización adaptativa ──────────────────────────────
        img = self._adaptive_threshold(img)

        # ── PASO 7: Morphology cleanup ────────────────────────────────────
        img = self._morphology_cleanup(img)

        logger.debug(f"Pipeline completado: shape={img.shape}, dtype={img.dtype}")
        return img  # 2D uint8 — directo a Tesseract

    # ──────────────────────────────────────────
    # PASOS INDIVIDUALES DEL PIPELINE
    # ──────────────────────────────────────────
    def _to_grayscale(self, image: np.ndarray) -> np.ndarray:
        """
        Convierte cualquier imagen a numpy 2D uint8 en escala de grises.
        Maneja: BGR (3ch), BGRA (4ch), ya gris (2D), shape (H,W,1).
        """
        img = np.asarray(image, dtype=np.uint8)
        img = np.squeeze(img)  # elimina dims extra: (H,W,1) → (H,W)

        if img.ndim == 3:
            ch = img.shape[2]
            if ch == 4:
                img = cv2.cvtColor(img, cv2.COLOR_BGRA2GRAY)
            elif ch == 3:
                img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            else:
                img = img[:, :, 0]

        return img.astype(np.uint8)

    def _resize_if_needed(self, image: np.ndarray) -> np.ndarray:
        """Redimensiona si el ancho es menor al mínimo recomendado."""
        h, w = image.shape[:2]
        if w < self.min_width:
            scale = self.min_width / w
            new_w = int(w * scale)
            new_h = int(h * scale)
            image = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
            logger.debug(f"Imagen redimensionada: {w}×{h} → {new_w}×{new_h}")
        return image

    def _denoise(self, image: np.ndarray) -> np.ndarray:
        """
        Eliminación de ruido con filtro de mediana (imagen 2D).

        FIX: método duplicado eliminado. Esta es la ÚNICA definición.
        La versión anterior tenía dos _denoise; Python usaba la última
        que no garantizaba 2D → error "medianBlur assertion _src0.dims() <= 2".
        """
        if image.ndim != 2:
            image = self._to_grayscale(image)
        return cv2.medianBlur(image, 3)

    def _deskew(self, image: np.ndarray) -> np.ndarray:
        """
        Corrección de inclinación con minAreaRect sobre píxeles activos.
        Solo corrige si el ángulo detectado supera 0.5°.
        """
        try:
            _, binary = cv2.threshold(
                image, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
            )
            coords = np.column_stack(np.where(binary > 0))

            if len(coords) < 10:
                return image

            angle = cv2.minAreaRect(coords)[-1]

            if angle < -45:
                angle = -(90 + angle)
            else:
                angle = -angle

            if abs(angle) > 0.5:
                h, w = image.shape[:2]
                center = (w // 2, h // 2)
                M = cv2.getRotationMatrix2D(center, angle, 1.0)
                image = cv2.warpAffine(
                    image, M, (w, h),
                    flags=cv2.INTER_CUBIC,
                    borderMode=cv2.BORDER_REPLICATE,
                )
                logger.debug(f"Inclinación corregida: {angle:.2f}°")

        except Exception as e:
            logger.warning(f"No se pudo corregir inclinación: {e}")

        return image

    def _enhance_contrast(self, image: np.ndarray) -> np.ndarray:
        """
        CLAHE optimizado para cédulas colombianas.
        clipLimit=3.0 (v1: 2.0) — más contraste en texto tenue/sellos.
        tileGridSize=(6,6) (v1: 8×8) — adaptación más local al fondo.
        """
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(6, 6))
        return clahe.apply(image)

    def _adaptive_threshold(self, image: np.ndarray) -> np.ndarray:
        """
        Umbralización adaptativa gaussiana optimizada.
        blockSize=15 (v1: 11) — ventana mayor evita binarizar artefactos.
        C=8 (v1: 2) — offset mayor produce texto más nítido en fondos no uniformes.
        """
        return cv2.adaptiveThreshold(
            image,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            blockSize=15,
            C=8,
        )

    def _morphology_cleanup(self, image: np.ndarray) -> np.ndarray:
        """
        NUEVO: Morphology Opening post-binarización.
        Erosión seguida de dilatación con kernel 2×2 elimina píxeles aislados
        y manchas de escáner sin dañar trazos de letras.
        """
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        return cv2.morphologyEx(image, cv2.MORPH_OPEN, kernel)

    def save_debug_image(self, image: np.ndarray, filename: str):
        """Guardar imagen preprocesada para depuración visual."""
        debug_dir = Path("./uploads/debug")
        debug_dir.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(debug_dir / filename), image)


# Instancia global del procesador
image_processor = ImageProcessor()
