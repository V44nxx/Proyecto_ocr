"""
Servicio Google Cloud Document AI
Encapsula toda la comunicación con la API de Google Document AI.

Responsabilidades:
  - Recibir bytes de PDF o imagen
  - Enviar al procesador configurado en Google Cloud
  - Devolver el texto OCR extraído como string plano
  - Manejar errores con logging descriptivo
  - Nunca imprimir ni registrar credenciales

Configuración requerida (variables de entorno):
  GOOGLE_CLOUD_PROJECT            → ID del proyecto GCP (ej: ocr-sena)
  GOOGLE_DOCUMENT_AI_LOCATION     → Región del procesador (ej: us)
  GOOGLE_DOCUMENT_AI_PROCESSOR_ID → ID del procesador (ej: abc123def456789a)
  GOOGLE_APPLICATION_CREDENTIALS  → Ruta al JSON de Service Account
"""
import os
import time
from typing import Optional, Tuple

from dataclasses import dataclass, field
from typing import Optional, Tuple, List, Dict, Any

from app.utils.logger import logger
from app.config import settings


@dataclass
class OCRToken:
    text: str
    confidence: float
    page_number: int
    x: float
    y: float
    w: float
    h: float


@dataclass
class OCRLine:
    text: str
    confidence: float
    page_number: int
    x: float
    y: float
    w: float
    h: float
    tokens: List[OCRToken] = field(default_factory=list)


@dataclass
class OCRPageData:
    page_number: int
    width: float
    height: float
    text: str
    lines: List[OCRLine] = field(default_factory=list)
    tokens: List[OCRToken] = field(default_factory=list)


@dataclass
class StructuredDocumentAIResult:
    text: str
    tiempo_ms: float
    pages: List[OCRPageData] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "tiempo_ms": self.tiempo_ms,
            "pages": [
                {
                    "page_number": p.page_number,
                    "width": p.width,
                    "height": p.height,
                    "text": p.text,
                    "lines": [
                        {
                            "text": l.text,
                            "confidence": l.confidence,
                            "page_number": l.page_number,
                            "x": l.x, "y": l.y, "w": l.w, "h": l.h,
                            "tokens": [
                                {
                                    "text": t.text,
                                    "confidence": t.confidence,
                                    "page_number": t.page_number,
                                    "x": t.x, "y": t.y, "w": t.w, "h": t.h
                                }
                                for t in l.tokens
                            ]
                        }
                        for l in p.lines
                    ]
                }
                for p in self.pages
            ]
        }


class GoogleDocumentAIService:
    """
    Cliente del servicio Google Cloud Document AI.

    Usa las credenciales configuradas mediante la variable de entorno
    GOOGLE_APPLICATION_CREDENTIALS. El SDK de Google las carga
    automáticamente — nunca se manipulan en este código.
    """

    def __init__(self):
        self._client = None
        self._processor_name = None
        self._disponible = False
        self._inicializar()

    def _inicializar(self) -> None:
        """
        Inicializa el cliente de Document AI si la configuración está completa.
        Registra el estado de inicialización sin imprimir credenciales.
        """
        # Verificar que la integración está habilitada
        if not settings.GOOGLE_DOCUMENT_AI_ENABLED:
            logger.info("[DocAI] Google Document AI deshabilitado (GOOGLE_DOCUMENT_AI_ENABLED=False)")
            return

        # Verificar variables obligatorias
        if not settings.GOOGLE_DOCUMENT_AI_PROCESSOR_ID:
            logger.warning(
                "[DocAI] GOOGLE_DOCUMENT_AI_PROCESSOR_ID no configurado. "
                "Google Document AI no estará disponible. Se usará Tesseract."
            )
            return

        if not settings.GOOGLE_APPLICATION_CREDENTIALS:
            logger.warning(
                "[DocAI] GOOGLE_APPLICATION_CREDENTIALS no configurado. "
                "Google Document AI no estará disponible. Se usará Tesseract."
            )
            return

        # Verificar que el archivo de credenciales existe (o crearlo desde env var si no existe)
        creds_path = settings.GOOGLE_APPLICATION_CREDENTIALS or "/app/credentials/google-document-ai.json"
        if not os.path.exists(creds_path):
            # Probar rutas relativas comunes
            cand1 = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", creds_path))
            cand2 = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "credentials", "google-document-ai.json"))
            cand3 = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "credentials", "google-document-ai.json"))
            if os.path.exists(cand1):
                creds_path = cand1
            elif os.path.exists(cand2):
                creds_path = cand2
            elif os.path.exists(cand3):
                creds_path = cand3
            else:
                # Si el archivo no existe en el contenedor, crearlo dinámicamente desde GOOGLE_CREDENTIALS_JSON o GOOGLE_CREDENTIALS_BASE64
                raw_json = getattr(settings, "GOOGLE_CREDENTIALS_JSON", None) or os.getenv("GOOGLE_CREDENTIALS_JSON")
                b64_json = getattr(settings, "GOOGLE_CREDENTIALS_BASE64", None) or os.getenv("GOOGLE_CREDENTIALS_BASE64")

                target_path = creds_path if os.path.isabs(creds_path) else os.path.abspath(creds_path)
                written = False

                if raw_json and raw_json.strip():
                    try:
                        os.makedirs(os.path.dirname(target_path), exist_ok=True)
                        with open(target_path, "w", encoding="utf-8") as f:
                            f.write(raw_json.strip())
                        creds_path = target_path
                        written = True
                        logger.info(f"[DocAI] Archivo de credenciales generado dinámicamente en '{creds_path}' desde GOOGLE_CREDENTIALS_JSON")
                    except Exception as err:
                        logger.error(f"[DocAI] Error al escribir credenciales desde GOOGLE_CREDENTIALS_JSON: {err}")
                elif b64_json and b64_json.strip():
                    try:
                        import base64
                        decoded = base64.b64decode(b64_json.strip()).decode("utf-8")
                        os.makedirs(os.path.dirname(target_path), exist_ok=True)
                        with open(target_path, "w", encoding="utf-8") as f:
                            f.write(decoded)
                        creds_path = target_path
                        written = True
                        logger.info(f"[DocAI] Archivo de credenciales generado dinámicamente en '{creds_path}' desde GOOGLE_CREDENTIALS_BASE64")
                    except Exception as err:
                        logger.error(f"[DocAI] Error al escribir credenciales desde GOOGLE_CREDENTIALS_BASE64: {err}")

                if not written and not os.path.exists(creds_path):
                    logger.warning(
                        f"[DocAI] Archivo de credenciales no encontrado en la ruta configurada ({creds_path}). "
                        f"Google Document AI no estará disponible. Se usará Tesseract."
                    )
                    return

        creds_path = os.path.abspath(creds_path)

        try:
            from google.cloud import documentai

            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = creds_path

            self._processor_name = (
                f"projects/{settings.GOOGLE_CLOUD_PROJECT}"
                f"/locations/{settings.GOOGLE_DOCUMENT_AI_LOCATION}"
                f"/processors/{settings.GOOGLE_DOCUMENT_AI_PROCESSOR_ID}"
            )

            endpoint = f"{settings.GOOGLE_DOCUMENT_AI_LOCATION}-documentai.googleapis.com"
            self._client = documentai.DocumentProcessorServiceClient(
                client_options={"api_endpoint": endpoint}
            )

            self._disponible = True
            logger.info(
                f"[DocAI] Google Document AI inicializado correctamente. "
                f"Proyecto: {settings.GOOGLE_CLOUD_PROJECT} | "
                f"Región: {settings.GOOGLE_DOCUMENT_AI_LOCATION}"
            )

        except ImportError:
            logger.error(
                "[DocAI] Librería 'google-cloud-documentai' no instalada. "
                "Ejecuta: pip install google-cloud-documentai"
            )
        except Exception as e:
            logger.error(f"[DocAI] Error al inicializar cliente: {type(e).__name__}: {e}")

    @property
    def disponible(self) -> bool:
        """Indica si el servicio está correctamente configurado y listo para usarse."""
        return self._disponible

    def _text_from_anchor(self, text_anchor, full_text: str) -> str:
        if not text_anchor or not text_anchor.text_segments:
            return ""
        parts = []
        for segment in text_anchor.text_segments:
            start = int(segment.start_index) if segment.start_index else 0
            end = int(segment.end_index)
            parts.append(full_text[start:end])
        return "".join(parts).strip()

    def _poly_to_box(self, bounding_poly) -> Tuple[float, float, float, float]:
        if not bounding_poly or not bounding_poly.normalized_vertices:
            return 0.0, 0.0, 0.0, 0.0
        vertices = bounding_poly.normalized_vertices
        xs = [v.x for v in vertices if hasattr(v, "x")]
        ys = [v.y for v in vertices if hasattr(v, "y")]
        if not xs or not ys:
            return 0.0, 0.0, 0.0, 0.0
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        return round(min_x, 4), round(min_y, 4), round(max_x - min_x, 4), round(max_y - min_y, 4)

    def procesar_documento_estructurado(
        self,
        contenido: bytes,
        mime_type: str = "application/pdf",
        pagina_num_base: int = 1,
    ) -> StructuredDocumentAIResult:
        """
        Envía documento a Document AI y retorna resultado rico con layout de tokens y líneas.
        """
        if not self._disponible:
            raise RuntimeError("Google Document AI no está disponible.")

        from google.cloud import documentai

        inicio = time.time()
        logger.info(f"[DocAI] Enviando documento estructurado ({len(contenido)} bytes, {mime_type})")

        documento_raw = documentai.RawDocument(
            content=contenido,
            mime_type=mime_type,
        )

        request = documentai.ProcessRequest(
            name=self._processor_name,
            raw_document=documento_raw,
        )

        result = self._client.process_document(request=request)
        doc = result.document
        full_text = doc.text if doc.text else ""

        paginas_estructuradas: List[OCRPageData] = []

        for p_idx, page in enumerate(doc.pages):
            num_pag = page.page_number if hasattr(page, "page_number") and page.page_number else (pagina_num_base + p_idx)
            w = page.dimension.width if hasattr(page, "dimension") and page.dimension else 1.0
            h = page.dimension.height if hasattr(page, "dimension") and page.dimension else 1.0

            lines_list: List[OCRLine] = []
            tokens_list: List[OCRToken] = []

            # Parsear líneas
            if hasattr(page, "lines"):
                for line in page.lines:
                    txt = self._text_from_anchor(line.layout.text_anchor, full_text)
                    if not txt:
                        continue
                    conf = float(line.layout.confidence) if hasattr(line.layout, "confidence") and line.layout.confidence else 0.90
                    bx, by, bw, bh = self._poly_to_box(line.layout.bounding_poly)
                    line_tokens: List[OCRToken] = []

                    # Parsear tokens dentro de la línea
                    if hasattr(line, "tokens"):
                        for tok in line.tokens:
                            t_txt = self._text_from_anchor(tok.layout.text_anchor, full_text)
                            t_conf = float(tok.layout.confidence) if hasattr(tok.layout, "confidence") and tok.layout.confidence else conf
                            tx, ty, tw, th = self._poly_to_box(tok.layout.bounding_poly)
                            t_obj = OCRToken(text=t_txt, confidence=t_conf, page_number=num_pag, x=tx, y=ty, w=tw, h=th)
                            line_tokens.append(t_obj)
                            tokens_list.append(t_obj)

                    lines_list.append(OCRLine(
                        text=txt, confidence=conf, page_number=num_pag,
                        x=bx, y=by, w=bw, h=bh, tokens=line_tokens
                    ))

            # Si la página no entregó líneas explícitas pero sí tokens
            if not lines_list and hasattr(page, "tokens"):
                for tok in page.tokens:
                    t_txt = self._text_from_anchor(tok.layout.text_anchor, full_text)
                    if not t_txt:
                        continue
                    t_conf = float(tok.layout.confidence) if hasattr(tok.layout, "confidence") and tok.layout.confidence else 0.90
                    tx, ty, tw, th = self._poly_to_box(tok.layout.bounding_poly)
                    t_obj = OCRToken(text=t_txt, confidence=t_conf, page_number=num_pag, x=tx, y=ty, w=tw, h=th)
                    tokens_list.append(t_obj)

            paginas_estructuradas.append(OCRPageData(
                page_number=num_pag, width=w, height=h, text=full_text,
                lines=lines_list, tokens=tokens_list
            ))

        tiempo_ms = round((time.time() - inicio) * 1000, 1)
        logger.info(f"[DocAI] Layout estructurado procesado ({len(paginas_estructuradas)} páginas, {len(full_text)} chars, {tiempo_ms}ms)")

        return StructuredDocumentAIResult(text=full_text, tiempo_ms=tiempo_ms, pages=paginas_estructuradas)

    def procesar_documento(
        self,
        contenido: bytes,
        mime_type: str = "application/pdf",
    ) -> Tuple[str, float]:
        """
        Devuelve (texto_plano, tiempo_ms) manteniendo compatibilidad hacia atrás.
        """
        res = self.procesar_documento_estructurado(contenido, mime_type=mime_type)
        return res.text, res.tiempo_ms

    def procesar_pagina_pdf(
        self,
        pdf_bytes: bytes,
    ) -> Tuple[str, float]:
        return self.procesar_documento(pdf_bytes, mime_type="application/pdf")

    def procesar_imagen(
        self,
        imagen_bytes: bytes,
        mime_type: str = "image/jpeg",
    ) -> Tuple[str, float]:
        return self.procesar_documento(imagen_bytes, mime_type=mime_type)


# Instancia única del servicio (singleton)
google_document_ai_service = GoogleDocumentAIService()
