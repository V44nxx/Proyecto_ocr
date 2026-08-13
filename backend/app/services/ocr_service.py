"""
Servicio OCR Principal — Documentos de Identidad Colombianos
Estrategia v3: PyMuPDF → (texto nativo) → si escaneado →
               Google Document AI (principal) → ExtractorService → PostgreSQL
               Si Google Document AI falla → Tesseract (fallback)

CAMBIOS v2 (optimización precisión):
  - FIX: doble sesión de BD eliminado — se usa db_externa si se provee.
  - FIX: confianza hardcodeada 95.0 → confianza real de ExtractorService.
  - FIX: ExtractorService.extraer() integrado en el flujo principal.
  - NUEVO: Tesseract con oem=3, psm=6 + fallback psm=4 si confianza baja.
  - NUEVO: texto_ocr_crudo guardado en Persona para auditoría.
  - NUEVO: umbral de PDF escaneado mejorado (palabras útiles, no solo chars).
  - NUEVO: marca requiere_revision con confianza real (< settings.threshold).

CAMBIOS v3 (Google Document AI):
  - NUEVO: _ocr_imagen() orquesta Google Document AI → fallback Tesseract.
  - NUEVO: log del motor OCR utilizado en cada página.
  - NUEVO: campo ocr_engine en resultado (opcional, no rompe frontend).
  - NUEVO: compatibilidad con imagen en bytes para Google Document AI.
"""
import os
import time
import re
import fitz  # PyMuPDF
from pathlib import Path
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.utils.logger import logger
from app.utils.image_processor import image_processor
from app.services.extractor_service import extractor_service
from app.services.google_document_ai_service import google_document_ai_service
from app.config import settings


class OCRService:

    def __init__(self):
        self.image_processor = image_processor
        self.parser = extractor_service

    # ──────────────────────────────────────────
    # MÉTODO PRINCIPAL
    # ──────────────────────────────────────────
    def procesar_pdf(
        self,
        ruta_pdf: str,
        documento_id: str,
        db_externa: Session = None,
    ) -> Dict[str, Any]:
        """
        Procesa un PDF de 1 o múltiples páginas.

        FIX sesión BD: si se provee db_externa, la usa directamente y NO
        la cierra al finalizar (el llamador es responsable). Solo crea una
        sesión interna cuando db_externa es None.
        """
        from app.database import SessionLocal

        # ── Sesión de BD ──────────────────────────────────────────────────
        _owns_session = db_externa is None
        db = SessionLocal() if _owns_session else db_externa

        inicio = time.time()
        logger.info(f"Iniciando OCR para documento {documento_id}: {ruta_pdf}")

        resultado = {
            "documento_id": documento_id,
            "total_paginas": 0,
            "personas_extraidas": [],
            "confianza_promedio": 0.0,
            "tiempo_ms": 0,
            "errores": [],
        }

        try:
            if not os.path.exists(ruta_pdf):
                raise FileNotFoundError(f"No existe el archivo: {ruta_pdf}")

            doc = fitz.open(ruta_pdf)
            total_paginas = len(doc)
            resultado["total_paginas"] = total_paginas
            logger.info(f"PDF abierto: {total_paginas} páginas")

            personas_guardadas = []
            confianzas = []

            for i in range(total_paginas):
                pagina = doc[i]

                # ── Extraer texto nativo ──────────────────────────────────
                texto_nativo = pagina.get_text("text")

                # ── Decidir si necesitamos OCR de imagen ──────────────────
                if self._necesita_ocr_imagen(texto_nativo):
                    logger.info(
                        f"Página {i+1}/{total_paginas}: "
                        f"PDF escaneado — aplicando OCR de imagen (300 DPI)"
                    )
                    pix = pagina.get_pixmap(dpi=300)
                    img_np = self.image_processor._pixmap_to_numpy(pix)
                    texto_pagina, motor_usado, layout_estructurado = self._ocr_imagen(
                        img_np=img_np, pagina_num=i + 1
                    )
                else:
                    texto_pagina = texto_nativo
                    motor_usado = "texto_nativo_pdf"
                    layout_estructurado = None

                logger.info(
                    f"Página {i+1}: {len(texto_pagina)} chars extraídos "
                    f"[motor: {motor_usado}]"
                )

                # ── Extracción estructurada de campos con layout ──────────
                datos_extraidos = self.parser.extraer(
                    texto_pagina,
                    layout_data=layout_estructurado,
                    pagina_num=i + 1,
                    ocr_engine=motor_usado
                )

                confianza = datos_extraidos.get("confianza_extraccion", 0.0)
                confianzas.append(confianza)

                # Guardar persona en BD con metadatos completos y trazabilidad de página
                persona = self._guardar_persona(
                    datos_extraidos, texto_pagina, documento_id, db,
                    ocr_engine=motor_usado, pagina_num=i + 1
                )
                if persona:
                    personas_guardadas.append(persona)

            doc.close()

            confianza_promedio = (
                sum(confianzas) / len(confianzas) if confianzas else 0.0
            )
            tiempo_ms = int((time.time() - inicio) * 1000)

            self._actualizar_documento_completado(
                documento_id, total_paginas, confianza_promedio, db
            )

            resultado["personas_extraidas"] = personas_guardadas
            resultado["confianza_promedio"] = round(confianza_promedio, 2)
            resultado["tiempo_ms"] = tiempo_ms

            logger.info(
                f"OCR finalizado para {documento_id}: "
                f"{len(personas_guardadas)} personas, "
                f"confianza promedio={confianza_promedio:.1f}%"
            )

        except Exception as e:
            import traceback
            tiempo_ms = int((time.time() - inicio) * 1000)
            error_msg = f"{type(e).__name__}: {str(e)}"
            tb_str = traceback.format_exc()
            logger.error(f"Error en OCR: {error_msg}\n{tb_str}")
            resultado["errores"].append(error_msg)
            resultado["tiempo_ms"] = tiempo_ms

            try:
                from app.models.documento import Documento
                doc_db = db.query(Documento).filter(Documento.id == documento_id).first()
                if doc_db:
                    doc_db.estado = "error"
                    doc_db.mensaje_error = f"{error_msg}\n{tb_str[-500:]}"
                    db.commit()
            except Exception:
                pass

        finally:
            # Solo cerrar si somos los dueños de la sesión
            if _owns_session:
                db.close()

        return resultado

    # ──────────────────────────────────────────
    # DETECCIÓN DE PDF ESCANEADO
    # ──────────────────────────────────────────
    def _necesita_ocr_imagen(self, texto: str) -> bool:
        """
        Determina si una página necesita OCR de imagen.

        FIX: umbral anterior (< 15 chars) era demasiado permisivo.
        Un PDF con solo el encabezado 'COLOMBIA' incrustado pasaba
        el umbral pero sin datos útiles.

        Ahora busca palabras alfanuméricas de ≥ 3 caracteres.
        Si hay menos de 5 palabras útiles o menos de 50 chars,
        se considera página escaneada.
        """
        if not texto or not texto.strip():
            return True
        texto_limpio = re.sub(r"\s+", " ", texto.strip())
        palabras_validas = re.findall(r"[A-Za-záéíóúüñÁÉÍÓÚÜÑ0-9]{3,}", texto_limpio)
        return len(palabras_validas) < 5 or len(texto_limpio) < 50

    # ──────────────────────────────────────────
    # OCR DE IMAGEN — GOOGLE DOCUMENT AI + FALLBACK TESSERACT
    # ──────────────────────────────────────────
    def _ocr_imagen(
        self, img_np, pagina_num: int = 0
    ) -> tuple:
        """
        Motor OCR de imagen con dos niveles:

        Nivel 1 — Google Document AI (principal):
          - Convierte la imagen numpy a bytes PNG
          - Envía a la API de Google Document AI
          - Devuelve texto + nombre del motor 'google_document_ai'

        Nivel 2 — Tesseract (fallback):
          - Se activa si Google Document AI falla, devuelve texto vacío
            o si GOOGLE_DOCUMENT_AI_ENABLED=False
          - Aplica preprocesamiento OpenCV antes de Tesseract
          - Devuelve texto + nombre del motor 'tesseract_fallback'

        Returns:
            Tupla (texto: str, motor: str)
        """
    def _ocr_imagen(
        self, img_np, pagina_num: int = 0
    ) -> tuple:
        """
        Motor OCR de imagen con dos niveles:
        Nivel 1 — Google Document AI (principal con layout estructurado)
        Nivel 2 — Tesseract (fallback etiquetado)

        Returns:
            Tupla (texto: str, motor: str, res_estructurado: Optional[StructuredDocumentAIResult])
        """
        # ── Nivel 1: Google Document AI ──────────────────────────────────
        if google_document_ai_service.disponible:
            try:
                import cv2
                success, img_encoded = cv2.imencode(".png", img_np)
                if not success:
                    raise ValueError("No se pudo codificar la imagen a PNG")
                img_bytes = img_encoded.tobytes()

                res_estructurado = google_document_ai_service.procesar_documento_estructurado(
                    img_bytes, mime_type="image/png", pagina_num_base=pagina_num
                )
                texto = res_estructurado.text

                if texto and texto.strip():
                    palabras = re.findall(r"[A-Za-záéíóúñÁÉÍÓÚÑ]{3,}", texto)
                    logger.info(
                        f"[DocAI] Página {pagina_num}: Google Document AI exitoso "
                        f"({len(texto)} chars, {len(palabras)} palabras, {res_estructurado.tiempo_ms}ms)"
                    )
                    return texto, "google_document_ai", res_estructurado
                else:
                    logger.warning(
                        f"[DocAI] Página {pagina_num}: Google Document AI devolvió "
                        f"texto vacío — usando Tesseract como fallback"
                    )

            except Exception as e:
                logger.error(
                    f"[DocAI] Página {pagina_num}: Error en Google Document AI "
                    f"({type(e).__name__}: {e}) — usando Tesseract como fallback"
                )
        else:
            logger.info(
                f"[DocAI] Página {pagina_num}: Google Document AI no disponible "
                f"— usando Tesseract directamente"
            )

        # ── Nivel 2: Tesseract (fallback) ────────────────────────────────
        img_procesada = self.image_processor.preprocess(img_np)
        texto = self._ocr_con_tesseract(img_procesada, pagina_num=pagina_num)
        return texto, "tesseract_fallback", None

    # ──────────────────────────────────────────
    # OCR CON TESSERACT — CONFIGURACIÓN ÓPTIMA
    # (se mantiene como fallback y para uso directo)
    # ──────────────────────────────────────────
    def _ocr_con_tesseract(
        self, img_procesada, pagina_num: int = 0
    ) -> str:
        """
        OCR con Tesseract 5 optimizado para cédulas colombianas.
        """
        try:
            import pytesseract

            tess_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
            if os.path.exists(tess_path):
                pytesseract.pytesseract.tesseract_cmd = tess_path

            config_psm6 = "--oem 3 --psm 6"

            texto = pytesseract.image_to_string(
                img_procesada, lang="spa", config=config_psm6
            )

            palabras = re.findall(r"[A-Za-záéíóúñÁÉÍÓÚÑ]{3,}", texto)
            if len(palabras) < 4:
                logger.warning(
                    f"Tesseract página {pagina_num}: PSM 6 produjo texto reducido "
                    f"({len(palabras)} palabras), intentando PSM 11 (texto disperso)"
                )
                texto_fallback = pytesseract.image_to_string(
                    img_procesada, lang="spa", config="--oem 3 --psm 11"
                )
                palabras_fb = re.findall(r"[A-Za-záéíóúñÁÉÍÓÚÑ]{3,}", texto_fallback)
                if len(palabras_fb) > len(palabras):
                    texto = texto_fallback

            logger.debug(f"Tesseract (página {pagina_num}): {len(texto)} chars")
            return texto

        except Exception as e:
            logger.error(f"Error en Tesseract (página {pagina_num}): {e}")
            return ""

    # ──────────────────────────────────────────
    # GUARDAR PERSONA EN BD
    # ──────────────────────────────────────────
    def _guardar_persona(
        self,
        datos: Dict[str, Any],
        texto_ocr: str,
        documento_id: str,
        db: Session,
        ocr_engine: str = "desconocido",
        pagina_num: int = 1,
    ) -> Optional[Dict[str, Any]]:
        """
        Guarda o actualiza la persona en la BD.
        """
        try:
            from app.models.persona import Persona
            from app.models.documento import Documento
            from datetime import datetime
            import uuid

            raw_id = datos.get("identificacion")
            nombres_val = datos.get("nombres")
            apellidos_val = datos.get("apellidos")
            confianza = float(datos.get("confianza_extraccion") or 0.0)

            if not raw_id and not nombres_val and not apellidos_val and confianza < 25.0:
                logger.info("Página sin datos de identificación ni nombres — omitiendo registro vacío")
                return None

            num_doc = raw_id or f"SIN_ID_{str(uuid.uuid4())[:8]}"

            doc_exists = (
                db.query(Documento).filter(Documento.id == documento_id).first()
                if documento_id
                else None
            )
            doc_id_val = str(doc_exists.id) if doc_exists else None

            from app.utils.validators import validador

            fecha_nac = None
            if datos.get("fecha_nacimiento"):
                fecha_nac = validador.parsear_fecha(datos["fecha_nacimiento"])

            fecha_exp = None
            if datos.get("fecha_expedicion"):
                fecha_exp = validador.parsear_fecha(datos["fecha_expedicion"])

            # ── Determinar estado del registro y si requiere revisión manual ─
            umbral_confianza = settings.OCR_CONFIDENCE_THRESHOLD * 100
            requiere_revision = (
                confianza < umbral_confianza
                or not datos.get("nombres")
                or not datos.get("identificacion")
                or "SIN_ID" in str(num_doc)
            )

            if ocr_engine == "tesseract_fallback":
                estado_reg = "FALLBACK_TESSERACT"
            elif requiere_revision:
                estado_reg = "REVIEW_REQUIRED"
            else:
                estado_reg = "VALID"

            persona = (
                db.query(Persona)
                .filter(Persona.numero_identificacion == str(num_doc))
                .first()
            )

            if not persona:
                persona = Persona(
                    documento_id=doc_id_val,
                    numero_identificacion=str(num_doc),
                    nombres=datos.get("nombres") or "POR REVISAR",
                    apellidos=datos.get("apellidos") or "POR REVISAR",
                    fecha_nacimiento=fecha_nac,
                    fecha_expedicion=fecha_exp,
                    lugar_expedicion=datos.get("lugar_expedicion"),
                    sexo=datos.get("sexo"),
                    pagina_numero=pagina_num,
                    tipo_documento=datos.get("tipo_documento", "CEDULA_CIUDADANIA"),
                    estado_registro=estado_reg,
                    motor_ocr=ocr_engine,
                    confianza_extraccion=confianza,
                    requiere_revision=requiere_revision,
                    detalles_campos=datos.get("detalles_campos"),
                    texto_ocr_crudo=(texto_ocr or "")[:5000],
                )
                db.add(persona)
            else:
                if doc_id_val:
                    persona.documento_id = doc_id_val
                if datos.get("nombres") and datos["nombres"] != "POR REVISAR":
                    persona.nombres = datos["nombres"]
                if datos.get("apellidos") and datos["apellidos"] != "POR REVISAR":
                    persona.apellidos = datos["apellidos"]
                if fecha_nac:
                    persona.fecha_nacimiento = fecha_nac
                if fecha_exp:
                    persona.fecha_expedicion = fecha_exp
                if datos.get("lugar_expedicion"):
                    persona.lugar_expedicion = datos["lugar_expedicion"]
                if datos.get("sexo"):
                    persona.sexo = datos["sexo"]
                persona.pagina_numero = pagina_num
                persona.tipo_documento = datos.get("tipo_documento", persona.tipo_documento)
                persona.detalles_campos = datos.get("detalles_campos", persona.detalles_campos)

                if confianza > float(persona.confianza_extraccion or 0):
                    persona.confianza_extraccion = confianza
                    persona.requiere_revision = requiere_revision
                    persona.estado_registro = estado_reg
                    persona.motor_ocr = ocr_engine
                if texto_ocr:
                    persona.texto_ocr_crudo = texto_ocr[:5000]

            db.commit()
            db.refresh(persona)

            return {
                "id": str(persona.id),
                "numero_identificacion": persona.numero_identificacion,
                "nombres": persona.nombres,
                "apellidos": persona.apellidos,
                "confianza_extraccion": float(persona.confianza_extraccion or 0),
                "requiere_revision": persona.requiere_revision,
                "pagina_numero": persona.pagina_numero,
                "tipo_documento": persona.tipo_documento,
                "estado_registro": persona.estado_registro,
                "motor_ocr": persona.motor_ocr,
                "detalles_campos": persona.detalles_campos,
            }

        except Exception as e:
            logger.error(f"Error guardando persona en BD: {e}")
            db.rollback()
            return None

    # ──────────────────────────────────────────
    # ACTUALIZAR ESTADO DEL DOCUMENTO
    # ──────────────────────────────────────────
    def _actualizar_documento_completado(
        self,
        documento_id: str,
        total_paginas: int,
        confianza: float,
        db: Session,
    ):
        """Marca el documento como completado con confianza promedio real."""
        try:
            from app.models.documento import Documento
            from datetime import datetime

            doc = db.query(Documento).filter(Documento.id == documento_id).first()
            if doc:
                doc.estado = "completado"
                doc.total_paginas = total_paginas
                doc.confianza_ocr = confianza  # ahora es la confianza real
                doc.fecha_procesamiento = datetime.utcnow()
                db.commit()
        except Exception as e:
            logger.error(f"Error actualizando estado del documento: {e}")


# Instancia única del servicio
ocr_service = OCRService()
