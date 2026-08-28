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
from app.services.rapid_ocr_service import rapid_ocr_service
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

            self._actualizar_progreso(
                documento_id=documento_id,
                db=db,
                progreso=5,
                paso=f"Iniciando análisis del PDF ({total_paginas} {'página' if total_paginas == 1 else 'páginas'})...",
                pagina_actual=0,
                total_paginas=total_paginas,
            )

            personas_guardadas = []
            confianzas = []
            paginas_clasificadas = []

            # ── Paso 1: Procesar cada página con Document AI y clasificar su cara ──
            for i in range(total_paginas):
                pagina_num = i + 1
                progreso_pct = 10 + int((i / max(total_paginas, 1)) * 60)
                self._actualizar_progreso(
                    documento_id=documento_id,
                    db=db,
                    progreso=progreso_pct,
                    paso=f"Procesando página {pagina_num} de {total_paginas} con OCR...",
                    pagina_actual=pagina_num,
                    total_paginas=total_paginas,
                )

                pagina = doc[i]
                texto_nativo = pagina.get_text("text")

                if self._necesita_ocr_imagen(texto_nativo):
                    logger.info(f"Página {pagina_num}/{total_paginas}: Aplicando OCR de imagen (300 DPI)")
                    pix = pagina.get_pixmap(dpi=300)
                    img_np = self.image_processor._pixmap_to_numpy(pix)
                    texto_pagina, motor_usado, layout_estructurado = self._ocr_imagen(
                        img_np=img_np, pagina_num=pagina_num
                    )
                else:
                    texto_pagina = texto_nativo
                    motor_usado = "texto_nativo_pdf"
                    layout_estructurado = None

                # Clasificar cara (Frente / Reverso)
                from app.services.document_side_classifier import document_side_classifier
                clasif_cara = document_side_classifier.clasificar_cara(
                    texto_pagina,
                    lines=layout_estructurado.pages[0].lines if (layout_estructurado and layout_estructurado.pages) else []
                )

                # Pre-extraer ID si está presente para ayudar a la agrupación
                id_pre = self.parser._extraer_identificacion(texto_pagina, texto_pagina.split("\n"))

                paginas_clasificadas.append({
                    "pagina_numero": pagina_num,
                    "texto": texto_pagina,
                    "layout": layout_estructurado,
                    "motor": motor_usado,
                    "cara": clasif_cara["cara"],
                    "tipo_documento": clasif_cara["tipo_documento"],
                    "confianza": clasif_cara["confianza"],
                    "numero_identificacion": id_pre
                })

            # ── Paso 2: Agrupar páginas en documentos físicos (Frente + Reverso) ──
            self._actualizar_progreso(
                documento_id=documento_id,
                db=db,
                progreso=72,
                paso="Clasificando y agrupando páginas (Frentes y Reversos)...",
                pagina_actual=total_paginas,
                total_paginas=total_paginas,
            )
            from app.services.document_pairing_service import document_pairing_service
            grupos = document_pairing_service.agrupar_paginas(paginas_clasificadas)

            # ── Paso 3: Extraer y guardar personas unificadas por documento ──
            self._actualizar_progreso(
                documento_id=documento_id,
                db=db,
                progreso=85,
                paso=f"Estructurando datos y unificando hojas ({len(grupos)} grupos detectados)...",
                pagina_actual=total_paginas,
                total_paginas=total_paginas,
            )
            personas_guardadas_map: Dict[str, Dict[str, Any]] = {}

            for grp in grupos:
                datos_grupo = self.parser.extraer_grupo(grp, ocr_engine="google_document_ai")
                confianza = datos_grupo.get("confianza_extraccion", 0.0)
                confianzas.append(confianza)

                persona = self._guardar_persona(
                    datos_grupo,
                    texto_ocr=f"Frente Pág {grp.pagina_frente} | Reverso Pág {grp.pagina_reverso}",
                    documento_id=documento_id,
                    db=db,
                    ocr_engine="google_document_ai",
                    pagina_num=grp.pagina_frente or grp.pagina_reverso or 1
                )
                if persona:
                    # Usar número de identificación o ID como clave única para evitar duplicados en la respuesta y contador
                    key = str(persona.get("numero_identificacion") or persona.get("id"))
                    personas_guardadas_map[key] = persona

            doc.close()

            personas_guardadas = list(personas_guardadas_map.values())
            confianza_promedio = (
                sum(confianzas) / len(confianzas) if confianzas else 0.0
            )
            tiempo_ms = int((time.time() - inicio) * 1000)

            self._actualizar_documento_completado(
                documento_id=documento_id,
                total_paginas=total_paginas,
                confianza=confianza_promedio,
                db=db,
                personas_count=len(personas_guardadas),
                tiempo_ms=tiempo_ms,
            )

            resultado["personas_extraidas"] = personas_guardadas
            resultado["confianza_promedio"] = round(confianza_promedio, 2)
            resultado["tiempo_ms"] = tiempo_ms

            logger.info(
                f"OCR finalizado para {documento_id}: "
                f"{len(personas_guardadas)} persona(s) única(s), "
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
                    meta = dict(doc_db.metadatos or {})
                    meta.update({
                        "progreso": 100,
                        "paso": f"Error: {error_msg}",
                    })
                    doc_db.metadatos = meta
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
        Motor OCR de imagen con cascada inteligente de tres niveles:
        Nivel 1 — Google Document AI (Cloud principal con layout estructurado)
        Nivel 2 — RapidOCR ONNX Runtime (Local neural de alta precisión para VPS y offline)
        Nivel 3 — Tesseract 5 (Fallback local tradicional)

        Returns:
            Tupla (texto: str, motor: str, res_estructurado: Optional[StructuredDocumentAIResult])
        """
        # ── Nivel 1: Google Document AI (Cloud) ──────────────────────────
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
                        f"({len(texto)} chars, {len(palabras)} palabras, {res_estructurado.tiempo_ms:.1f}ms)"
                    )
                    return texto, "google_document_ai", res_estructurado
                else:
                    logger.warning(
                        f"[DocAI] Página {pagina_num}: Google Document AI devolvió "
                        f"texto vacío — pasando a RapidOCR"
                    )

            except Exception as e:
                logger.error(
                    f"[DocAI] Página {pagina_num}: Error en Google Document AI "
                    f"({type(e).__name__}: {e}) — pasando a RapidOCR"
                )
        else:
            logger.info(
                f"[OCR] Página {pagina_num}: Google Document AI no disponible "
                f"— ejecutando RapidOCR local"
            )

        # ── Nivel 2: RapidOCR (ONNX Runtime Local) ───────────────────────
        if rapid_ocr_service.disponible:
            try:
                texto_rapid, conf_rapid, res_rapid = rapid_ocr_service.procesar_imagen(img_np, pagina_num=pagina_num)
                if texto_rapid and texto_rapid.strip():
                    logger.info(
                        f"[RapidOCR] Página {pagina_num}: RapidOCR exitoso "
                        f"({len(texto_rapid)} chars, confianza={conf_rapid:.1f}%)"
                    )
                    return texto_rapid, "rapid_ocr", res_rapid
                else:
                    logger.warning(f"[RapidOCR] Página {pagina_num}: RapidOCR devolvió texto vacío — pasando a Tesseract")
            except Exception as e:
                logger.error(f"[RapidOCR] Página {pagina_num}: Error en RapidOCR ({type(e).__name__}: {e}) — pasando a Tesseract")

        # ── Nivel 3: Tesseract 5 (Fallback tradicional) ──────────────────
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

            from app.utils.validators import validador

            raw_id = datos.get("identificacion")
            id_limpio = validador.limpiar_identificacion(raw_id)
            nombres_val = datos.get("nombres")
            apellidos_val = datos.get("apellidos")
            confianza = float(datos.get("confianza_extraccion") or 0.0)

            # Criterio estricto: Una persona válida debe tener Cédula extraída O (Nombres y Apellidos válidos).
            tiene_identificacion = bool(id_limpio and not id_limpio.startswith("SIN_ID"))
            tiene_nombres = bool(nombres_val and str(nombres_val).strip() and nombres_val != "POR REVISAR")
            tiene_apellidos = bool(apellidos_val and str(apellidos_val).strip() and apellidos_val != "POR REVISAR")

            if not tiene_identificacion and not (tiene_nombres and tiene_apellidos):
                logger.info("Omitiendo guardado: la página/grupo no contiene identificación ni nombres válidos (evita personas fantasma)")
                return None

            num_doc = id_limpio if tiene_identificacion else f"SIN_ID_{str(uuid.uuid4())[:8]}"

            doc_exists = (
                db.query(Documento).filter(Documento.id == documento_id).first()
                if documento_id
                else None
            )
            doc_id_val = str(doc_exists.id) if doc_exists else None

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
                or not datos.get("apellidos")
                or not datos.get("identificacion")
                or not (datos.get("fecha_expedicion") or datos.get("fecha_nacimiento"))
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

            from app.services.colombia_geo_service import colombia_geo

            def _es_nombre_invalido(val: Optional[str]) -> bool:
                if not val:
                    return True
                v_up = str(val).strip().upper()
                if v_up in {"POR REVISAR", "BLICA", "PUBLICA", "REPÚBLICA", "REPUBLICA", "COLOMBIA", "DE COLOMBIA", "PERSONAL", "CEDULA", "CIUDADANIA"}:
                    return True
                if v_up in colombia_geo.DEPARTAMENTOS or v_up in colombia_geo.MUNICIPIOS_SET:
                    return True
                return False

            nombres_final = datos.get("nombres") if not _es_nombre_invalido(datos.get("nombres")) else "POR REVISAR"
            apellidos_final = datos.get("apellidos") if not _es_nombre_invalido(datos.get("apellidos")) else "POR REVISAR"

            if not persona:
                persona = Persona(
                    documento_id=doc_id_val,
                    grupo_documento_id=datos.get("grupo_documento_id", "DOC-001"),
                    pagina_frente=datos.get("pagina_frente"),
                    pagina_reverso=datos.get("pagina_reverso"),
                    numero_identificacion=str(num_doc),
                    nombres=nombres_final,
                    apellidos=apellidos_final,
                    fecha_nacimiento=fecha_nac,
                    fecha_expedicion=fecha_exp,
                    lugar_expedicion=datos.get("lugar_expedicion"),
                    sexo=(datos.get("sexo") or "")[:10] if datos.get("sexo") else None,
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
                logger.info(f"Registrada nueva persona: {num_doc} ({persona.nombre_completo()})")
            else:
                # ── UNIFICACIÓN INTELIGENTE DE HOJAS / PÁGINAS ──
                # Si la cédula ya existe (ej. repartida en 2 hojas), no duplicar y fusionar datos faltantes
                logger.info(f"Unificando datos para persona existente ID '{num_doc}'...")
                if doc_id_val:
                    persona.documento_id = doc_id_val

                # Unificar páginas de frente y reverso
                if not persona.pagina_frente and datos.get("pagina_frente"):
                    persona.pagina_frente = datos["pagina_frente"]
                if not persona.pagina_reverso and datos.get("pagina_reverso"):
                    persona.pagina_reverso = datos["pagina_reverso"]
                elif not persona.pagina_reverso and datos.get("pagina_frente") and persona.pagina_frente != datos.get("pagina_frente"):
                    persona.pagina_reverso = datos.get("pagina_frente")

                # Nombres y Apellidos (preservar nombre existente válido y no sobrescribir con departamentos/municipios)
                if _es_nombre_invalido(persona.nombres) and not _es_nombre_invalido(datos.get("nombres")):
                    persona.nombres = datos["nombres"]
                if _es_nombre_invalido(persona.apellidos) and not _es_nombre_invalido(datos.get("apellidos")):
                    persona.apellidos = datos["apellidos"]

                # Fechas y Lugar
                if not persona.fecha_nacimiento and fecha_nac:
                    persona.fecha_nacimiento = fecha_nac
                if not persona.fecha_expedicion and fecha_exp:
                    persona.fecha_expedicion = fecha_exp
                if (not persona.lugar_expedicion or persona.lugar_expedicion in ["COLOMBIA", "REPUBLICA DE COLOMBIA"]) and datos.get("lugar_expedicion"):
                    persona.lugar_expedicion = datos["lugar_expedicion"]
                if not persona.sexo and datos.get("sexo"):
                    persona.sexo = str(datos["sexo"])[:10]

                # Fusión de detalles de campos
                detalles_existentes = dict(persona.detalles_campos or {})
                detalles_nuevos = dict(datos.get("detalles_campos") or {})
                for k, v in detalles_nuevos.items():
                    if k not in detalles_existentes or not detalles_existentes[k].get("valor"):
                        detalles_existentes[k] = v
                persona.detalles_campos = detalles_existentes

                # Unificar texto crudo
                if texto_ocr and texto_ocr not in (persona.texto_ocr_crudo or ""):
                    persona.texto_ocr_crudo = f"{(persona.texto_ocr_crudo or '').strip()}\n---\n{texto_ocr}".strip()[:5000]

                # Ajuste de confianza
                if confianza > float(persona.confianza_extraccion or 0):
                    persona.confianza_extraccion = confianza
                    persona.motor_ocr = ocr_engine

                # Reevaluar si ya no requiere revisión tras la unificación de ambas hojas
                tiene_datos_completos = bool(
                    persona.numero_identificacion
                    and not str(persona.numero_identificacion).startswith("SIN_ID")
                    and persona.nombres and persona.nombres != "POR REVISAR"
                    and persona.apellidos and persona.apellidos != "POR REVISAR"
                    and (persona.fecha_expedicion or persona.fecha_nacimiento)
                    and float(persona.confianza_extraccion or 0) >= (settings.OCR_CONFIDENCE_THRESHOLD * 100)
                )

                if tiene_datos_completos:
                    persona.requiere_revision = False
                    persona.estado_registro = "VALID"
                else:
                    persona.requiere_revision = requiere_revision
                    persona.estado_registro = estado_reg

                persona.fecha_actualizacion = datetime.utcnow()

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
    # ACTUALIZAR ESTADO Y PROGRESO DEL DOCUMENTO
    # ──────────────────────────────────────────
    def _actualizar_progreso(
        self,
        documento_id: str,
        db: Session,
        progreso: int,
        paso: str,
        pagina_actual: int = 0,
        total_paginas: int = 0,
    ):
        """Actualiza el progreso en metadatos para polling en tiempo real desde el frontend."""
        try:
            from app.models.documento import Documento
            doc = db.query(Documento).filter(Documento.id == documento_id).first()
            if doc:
                meta = dict(doc.metadatos or {})
                meta.update({
                    "progreso": progreso,
                    "paso": paso,
                    "pagina_actual": pagina_actual,
                    "total_paginas": total_paginas or doc.total_paginas or 0,
                })
                doc.metadatos = meta
                if total_paginas and not doc.total_paginas:
                    doc.total_paginas = total_paginas
                db.commit()
        except Exception as e:
            logger.warning(f"No se pudo actualizar progreso para {documento_id}: {e}")

    def _actualizar_documento_completado(
        self,
        documento_id: str,
        total_paginas: int,
        confianza: float,
        db: Session,
        personas_count: int = 0,
        tiempo_ms: int = 0,
    ):
        """Marca el documento como completado con confianza promedio real y metadatos de finalización."""
        try:
            from app.models.documento import Documento
            from datetime import datetime

            doc = db.query(Documento).filter(Documento.id == documento_id).first()
            if doc:
                doc.estado = "completado"
                doc.total_paginas = total_paginas
                doc.confianza_ocr = confianza  # confianza real
                doc.tiempo_procesamiento_ms = tiempo_ms or doc.tiempo_procesamiento_ms
                doc.fecha_procesamiento = datetime.utcnow()
                meta = dict(doc.metadatos or {})
                meta.update({
                    "progreso": 100,
                    "paso": f"Extracción completada con éxito ({personas_count} personas encontradas)",
                    "pagina_actual": total_paginas,
                    "total_paginas": total_paginas,
                    "personas_extraidas": personas_count,
                    "tiempo_procesamiento_ms": tiempo_ms,
                })
                doc.metadatos = meta
                db.commit()
        except Exception as e:
            logger.error(f"Error actualizando estado del documento: {e}")


# Instancia única del servicio
ocr_service = OCRService()

