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

from app.utils.logger import logger
from app.config import settings


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

        # Verificar que el archivo de credenciales existe
        creds_path = settings.GOOGLE_APPLICATION_CREDENTIALS
        if not os.path.exists(creds_path):
            logger.warning(
                f"[DocAI] Archivo de credenciales no encontrado en la ruta configurada. "
                f"Google Document AI no estará disponible. Se usará Tesseract."
                # NOTA: no se imprime la ruta completa para no exponer paths sensibles en todos los entornos
            )
            return

        try:
            # Importar el SDK de Google — se importa aquí para que la app
            # arranque correctamente incluso si la librería no está instalada
            from google.cloud import documentai

            # Establecer la variable de entorno para el SDK si aún no está establecida
            # (el SDK de Google la lee automáticamente de GOOGLE_APPLICATION_CREDENTIALS)
            os.environ.setdefault(
                "GOOGLE_APPLICATION_CREDENTIALS",
                creds_path
            )

            # Construir el nombre completo del procesador
            self._processor_name = (
                f"projects/{settings.GOOGLE_CLOUD_PROJECT}"
                f"/locations/{settings.GOOGLE_DOCUMENT_AI_LOCATION}"
                f"/processors/{settings.GOOGLE_DOCUMENT_AI_PROCESSOR_ID}"
            )

            # Crear el cliente con el endpoint regional correcto
            endpoint = f"{settings.GOOGLE_DOCUMENT_AI_LOCATION}-documentai.googleapis.com"
            self._client = documentai.DocumentProcessorServiceClient(
                client_options={"api_endpoint": endpoint}
            )

            self._disponible = True
            logger.info(
                f"[DocAI] Google Document AI inicializado correctamente. "
                f"Proyecto: {settings.GOOGLE_CLOUD_PROJECT} | "
                f"Región: {settings.GOOGLE_DOCUMENT_AI_LOCATION}"
                # El Processor ID NO se registra para no exponer IDs en logs de producción
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

    def procesar_documento(
        self,
        contenido: bytes,
        mime_type: str = "application/pdf",
    ) -> Tuple[str, float]:
        """
        Envía un documento a Google Document AI y devuelve el texto extraído.

        Args:
            contenido:  Bytes del PDF o imagen (JPG/PNG).
            mime_type:  MIME type del contenido (por defecto application/pdf).
                        Para imágenes usar 'image/jpeg' o 'image/png'.

        Returns:
            Tupla (texto_extraido, tiempo_ms).
            - texto_extraido: string con el texto OCR completo.
            - tiempo_ms: tiempo de procesamiento en milisegundos.

        Raises:
            RuntimeError: si el servicio no está disponible.
            Exception:    si la API devuelve un error (el llamador debe capturarlo).
        """
        if not self._disponible:
            raise RuntimeError(
                "Google Document AI no está disponible. "
                "Verifica GOOGLE_DOCUMENT_AI_PROCESSOR_ID y GOOGLE_APPLICATION_CREDENTIALS."
            )

        from google.cloud import documentai

        inicio = time.time()
        logger.info(f"[DocAI] Enviando documento a Google Document AI ({len(contenido)} bytes, {mime_type})")

        # Construir el documento de entrada
        documento_raw = documentai.RawDocument(
            content=contenido,
            mime_type=mime_type,
        )

        # Construir la solicitud de procesamiento
        request = documentai.ProcessRequest(
            name=self._processor_name,
            raw_document=documento_raw,
        )

        # Llamar a la API
        result = self._client.process_document(request=request)
        documento = result.document

        # Extraer el texto plano del resultado
        texto = documento.text if documento.text else ""

        tiempo_ms = round((time.time() - inicio) * 1000, 1)
        chars = len(texto)
        logger.info(
            f"[DocAI] Procesamiento completado en {tiempo_ms}ms — "
            f"{chars} caracteres extraídos"
        )

        return texto, tiempo_ms

    def procesar_pagina_pdf(
        self,
        pdf_bytes: bytes,
    ) -> Tuple[str, float]:
        """
        Atajo para procesar un PDF completo.

        Args:
            pdf_bytes: Bytes del archivo PDF.

        Returns:
            Tupla (texto_extraido, tiempo_ms).
        """
        return self.procesar_documento(pdf_bytes, mime_type="application/pdf")

    def procesar_imagen(
        self,
        imagen_bytes: bytes,
        mime_type: str = "image/jpeg",
    ) -> Tuple[str, float]:
        """
        Atajo para procesar una imagen (JPG o PNG).

        Args:
            imagen_bytes: Bytes de la imagen.
            mime_type:    'image/jpeg' o 'image/png'.

        Returns:
            Tupla (texto_extraido, tiempo_ms).
        """
        return self.procesar_documento(imagen_bytes, mime_type=mime_type)


# Instancia única del servicio (singleton)
# La inicialización ocurre al importar el módulo, registrando el estado una sola vez.
google_document_ai_service = GoogleDocumentAIService()
