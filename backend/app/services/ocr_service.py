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
        excel_lookup: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Procesa un PDF de 1 o múltiples páginas.

        FIX sesión BD: si se provee db_externa, la usa directamente y NO
        la cierra al finalizar (el llamador es responsable). Solo crea una
        sesión interna cuando db_externa es None.

        excel_lookup: diccionario {numero_id: {nombres, apellidos}} cargado
        desde la planilla oficial. Cuando se provee, los nombres/apellidos
        se toman de ahi en lugar del OCR.
        """
        from app.database import SessionLocal

        # ── Sesión de BD ──────────────────────────────────────────────────
        _owns_session = db_externa is None
        db = SessionLocal() if _owns_session else db_externa

        # ── Auto-resolución de lookup Excel si no fue provisto explícitamente ──
        if excel_lookup is None:
            try:
                from app.services.excel_lookup_service import excel_lookup_service
                from app.models.comparacion import Comparacion
                from app.models.documento import Documento

                doc_obj = db.query(Documento).filter(Documento.id == documento_id).first()
                if doc_obj and doc_obj.usuario_id:
                    comp = (
                        db.query(Comparacion)
                        .filter(
                            Comparacion.usuario_id == doc_obj.usuario_id,
                            Comparacion.ruta_archivo.isnot(None)
                        )
                        .order_by(Comparacion.fecha_carga.desc())
                        .first()
                    )
                    if comp:
                        ruta_comp = comp.obtener_ruta_o_restaurar(db)
                        if ruta_comp and ruta_comp.exists():
                            excel_lookup = excel_lookup_service.cargar_lookup(str(ruta_comp))
                            logger.info(
                                f"[OCR] Lookup Excel cargado para usuario {doc_obj.usuario_id} desde '{comp.nombre_original}' ({len(excel_lookup)} personas)"
                            )
            except Exception as e_auto:
                logger.warning(f"[OCR] No se pudo cargar Excel automático: {e_auto}")

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
            from app.models.documento import Documento
            doc_inicial = db.query(Documento).filter(Documento.id == documento_id).first()
            if not doc_inicial or doc_inicial.estado == "cancelado":
                logger.info(f"[OCR] Documento {documento_id} cancelado o no encontrado antes de iniciar. Abortando OCR.")
                return resultado

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

            # ── Paso 1: Preparar páginas y procesar en paralelo con ThreadPoolExecutor ──
            from concurrent.futures import ThreadPoolExecutor, as_completed

            doc.close()

            def _procesar_una_pagina(p_num: int):
                doc_local = fitz.open(ruta_pdf)
                try:
                    pag = doc_local[p_num - 1]
                    txt_nat = pag.get_text("text")
                    nec_ocr = self._necesita_ocr_imagen(txt_nat, pag=pag)
                    if nec_ocr:
                        # 200 DPI: resolución óptima para OCR documental, 56% más ligero y 2.5x más rápido que 300 DPI
                        pix = pag.get_pixmap(dpi=200)
                        img_arr = self.image_processor._pixmap_to_numpy(pix)
                        del pix
                        txt_pag, motor, layout = self._ocr_imagen(img_np=img_arr, pagina_num=p_num)
                        del img_arr
                    else:
                        txt_pag = txt_nat
                        motor = "texto_nativo_pdf"
                        layout = None
                finally:
                    doc_local.close()

                from app.services.document_side_classifier import document_side_classifier
                clasif = document_side_classifier.clasificar_cara(
                    txt_pag,
                    lines=layout.pages[0].lines if (layout and layout.pages) else []
                )
                id_pre = self.parser._extraer_identificacion(txt_pag, txt_pag.split("\n"))
                return {
                    "pagina_numero": p_num,
                    "texto": txt_pag,
                    "layout": layout,
                    "motor": motor,
                    "cara": clasif["cara"],
                    "tipo_documento": clasif["tipo_documento"],
                    "confianza": clasif["confianza"],
                    "numero_identificacion": id_pre
                }

            # Procesamiento concurrente de páginas (hasta 6 workers en paralelo)
            max_workers = min(6, total_paginas) if total_paginas > 0 else 1
            resultados_desordenados = []
            paginas_procesadas = 0

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futuros = {executor.submit(_procesar_una_pagina, p_num): p_num for p_num in range(1, total_paginas + 1)}
                for futuro in as_completed(futuros):
                    paginas_procesadas += 1
                    progreso_pct = 10 + int((paginas_procesadas / max(total_paginas, 1)) * 60)
                    self._actualizar_progreso(
                        documento_id=documento_id,
                        db=db,
                        progreso=progreso_pct,
                        paso=f"Procesando páginas con OCR ({paginas_procesadas}/{total_paginas})...",
                        pagina_actual=paginas_procesadas,
                        total_paginas=total_paginas,
                    )
                    resultados_desordenados.append(futuro.result())

            # Reordenar en orden estricto de página
            paginas_clasificadas = sorted(resultados_desordenados, key=lambda x: x["pagina_numero"])

            # ── Verificar si fue cancelado durante el OCR de páginas ───────────
            doc_en_proceso = db.query(Documento).filter(Documento.id == documento_id).first()
            if not doc_en_proceso or doc_en_proceso.estado == "cancelado":
                logger.info(f"[OCR] Documento {documento_id} cancelado o removido durante OCR de páginas. Deteniendo.")
                if not doc.is_closed:
                    doc.close()
                return resultado

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
                # ── Resolver motor representativo real del grupo (Trazabilidad precisa) ──
                motores_grp = set()
                if grp.front_page and grp.front_page.get("motor"):
                    motores_grp.add(grp.front_page["motor"])
                if grp.back_page and grp.back_page.get("motor"):
                    motores_grp.add(grp.back_page["motor"])
                for op in getattr(grp, "other_pages", []):
                    if op and op.get("motor"):
                        motores_grp.add(op["motor"])

                if "google_document_ai+rapid_ocr" in motores_grp:
                    motor_real = "google_document_ai+rapid_ocr"
                elif "rapid_ocr" in motores_grp and "google_document_ai" in motores_grp:
                    motor_real = "google_document_ai+rapid_ocr"
                elif "rapid_ocr" in motores_grp:
                    motor_real = "rapid_ocr"
                elif "google_document_ai" in motores_grp:
                    motor_real = "google_document_ai"
                elif "tesseract_fallback" in motores_grp:
                    motor_real = "tesseract_fallback"
                elif "texto_nativo_pdf" in motores_grp:
                    motor_real = "texto_nativo_pdf"
                else:
                    motor_real = "google_document_ai"

                datos_grupo = self.parser.extraer_grupo(grp, ocr_engine=motor_real)
                confianza = datos_grupo.get("confianza_extraccion", 0.0)
                confianzas.append(confianza)

                persona = self._guardar_persona(
                    datos_grupo,
                    texto_ocr=f"Frente Pag {grp.pagina_frente} | Reverso Pag {grp.pagina_reverso}",
                    documento_id=documento_id,
                    db=db,
                    ocr_engine=motor_real,
                    pagina_num=grp.pagina_frente or grp.pagina_reverso or 1,
                    excel_lookup=excel_lookup,
                )
                if persona:
                    # Usar ID único de la persona para garantizar que todas las personas del documento se conserven
                    key = str(persona.get("id"))
                    personas_guardadas_map[key] = persona

            if not doc.is_closed:
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
                if doc_db and doc_db.estado != "cancelado":
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
    def _necesita_ocr_imagen(self, texto: str, pag=None) -> bool:
        """
        Determina si una página necesita OCR de imagen.

        En fotocopias escaneadas o digitalizadas (Word/Canva/PDF editor):
        - El encabezado o pie de página suele ser texto nativo (membretes de trámite, fotocopia, etc.).
        - La cédula física en sí es una IMAGEN escaneada incrustada en la página.

        Reglas estrictas:
        1. Si la página contiene imágenes incrustadas (fotos de cédulas en fotocopias),
           SE DEBE forzar OCR de imagen a menos que el texto nativo ya contenga una cédula completa
           (número válido Y nombres de ciudadano que no sean solo membrete).
        2. Si todo el texto nativo es membrete administrativo/trámite, forzar OCR.
        3. Si el texto nativo no contiene un número de identificación válido (6-10 dígitos), forzar OCR.
        4. Si no tiene etiquetas clave de cédula, forzar OCR.
        """
        if not texto or not texto.strip():
            return True

        from app.utils.name_cleaner import es_linea_ruido_administrativo
        from app.utils.validators import validador

        lineas_no_vacias = [l.strip() for l in texto.splitlines() if l.strip()]

        # 1. Si todo el texto nativo corresponde a membretes administrativos o fotocopias
        if lineas_no_vacias and all(es_linea_ruido_administrativo(l) for l in lineas_no_vacias):
            logger.info("[OCR] Todo el texto nativo es membrete administrativo/fotocopia -> Forzando OCR de imagen")
            return True

        # 2. Si hay imágenes incrustadas en la página (cédulas escaneadas en fotocopias)
        if pag is not None:
            try:
                imgs = pag.get_images()
                if imgs and len(imgs) > 0:
                    # En fotocopias de cédula, la imagen contiene los datos del ciudadano
                    if not re.search(r"\b(APELLIDOS?|NOMBRES?|NUIP)\b", texto, re.I):
                        logger.info(f"[OCR] Página con {len(imgs)} imagen(es) incrustada(s) -> Forzando OCR de imagen")
                        return True
            except Exception:
                pass

        # 3. Verificar si el texto nativo contiene un número de cédula válido (6 a 10 dígitos)
        patron_id = re.compile(r"\b([1-9]\d{0,2}(?:\s*[\.,]\s*\d{3}){1,3}|[1-9]\d{5,9})\b")
        tiene_id_valido = False
        for m in patron_id.finditer(texto):
            clean_num = re.sub(r"[^\d]", "", m.group(1))
            valido, _ = validador.validar_cedula(clean_num)
            if valido:
                tiene_id_valido = True
                break

        if not tiene_id_valido:
            logger.info("[OCR] Texto nativo no contiene número de identificación válido -> Forzando OCR de imagen")
            return True

        # 4. Longitud mínima y keywords
        texto_limpio = re.sub(r"\s+", " ", texto.strip())
        palabras_validas = re.findall(r"[A-Za-záéíóúüñÁÉÍÓÚÜÑ]{3,}", texto_limpio)
        if len(palabras_validas) < 5 or len(texto_limpio) < 50:
            return True

        # 5. Keywords estructurales obligatorias de cédula
        KEYWORDS_CEDULA = re.compile(
            r"\b(NUIP|APELLIDOS?|NOMBRES?|CEDULA\s+DE\s+CIUDADAN|TARJETA\s+DE\s+IDENTIDAD)\b",
            re.IGNORECASE
        )
        if not KEYWORDS_CEDULA.search(texto_limpio):
            logger.info("[OCR] Texto nativo sin keywords estructurales de cédula — forzando OCR de imagen")
            return True

        return False

    def _es_extraccion_docai_completa(
        self, texto_docai: str, res_docai: Any, pagina_num: int = 0
    ) -> tuple[bool, str]:
        """
        Evalúa si la extracción de Google Document AI es estructuralmente completa y confiable.
        Si es completa, el Fast-Path retorna de inmediato evitando el cómputo de RapidOCR en CPU.
        Si es incompleta o dudosa, retorna False con la razón para activar el rescate de RapidOCR.
        """
        if not texto_docai or not res_docai:
            return False, "Texto o resultado nulo"

        texto_limpio = texto_docai.strip()
        palabras = re.findall(r"[A-Za-záéíóúüñÁÉÍÓÚÜÑ]{3,}", texto_limpio)

        # 1. Volumen mínimo de texto
        if len(texto_limpio) < 40 or len(palabras) < 5:
            return False, f"Volumen insuficiente ({len(texto_limpio)} chars, {len(palabras)} palabras)"

        # 2. Confianza media de líneas de layout si están disponibles
        docai_lines = []
        if getattr(res_docai, "pages", None) and len(res_docai.pages) > 0:
            docai_lines = getattr(res_docai.pages[0], "lines", [])

        if docai_lines:
            confidencias = [float(getattr(l, "confidence", 1.0)) for l in docai_lines if hasattr(l, "confidence")]
            if confidencias:
                conf_prom = sum(confidencias) / len(confidencias)
                if conf_prom < 0.75:
                    return False, f"Confianza promedio de líneas baja ({conf_prom * 100:.1f}% < 75%)"

        # 3. Detección de cara y marcadores estructurales
        from app.services.document_side_classifier import document_side_classifier
        clasif = document_side_classifier.clasificar_cara(
            texto_limpio,
            lines=docai_lines
        )
        cara = clasif.get("cara", "UNKNOWN")
        conf_cara = clasif.get("confianza", 0.0)

        # 4. Verificación de número de identificación
        lineas_docai = [l.strip() for l in texto_limpio.split("\n") if l.strip()]
        id_encontrado = self.parser._extraer_identificacion(texto_limpio, lineas_docai)

        if id_encontrado:
            tiene_nombres = bool(re.search(r"\b(NOMBRES?|APELLIDOS?)\b", texto_limpio, re.I))
            if tiene_nombres or conf_cara >= 0.65 or len(palabras) >= 8:
                return True, f"Cédula {id_encontrado} detectada con estructura sólida"

        # Si no tiene ID pero es un Reverso de Cédula o Tarjeta bien identificado
        if cara in ("CEDULA_BACK", "TARJETA_IDENTIDAD_BACK") and conf_cara >= 0.70:
            return True, f"Cara {cara} identificada con alta confianza ({conf_cara * 100:.1f}%)"

        return False, "Sin número de identificación ni cara reconocible con alta confianza"

    # ──────────────────────────────────────────
    # OCR DE IMAGEN — MODO DUAL (DocAI + RapidOCR) + FALLBACK TESSERACT
    # ──────────────────────────────────────────
    def _ocr_imagen(
        self, img_np, pagina_num: int = 0
    ) -> tuple:
        """
        Motor OCR de imagen con modo DUAL activo (DocAI + RapidOCR):

        Modo DUAL INTELIGENTE (Smart Dual OCR - Opción A):
          1. Google Document AI → texto principal + layout 2D estructurado
          2. Evaluación de estructura y calidad (Smart Fast-Path):
             - Si la cédula/reverso es completo y legible -> retorna inmediatamente sin tocar RapidOCR.
             - Si faltan datos, cédula o la confianza es baja -> activa RapidOCR al rescate.
          3. Fusión de textos  → líneas de RapidOCR que DocAI no capturó se agregan
             al texto final, garantizando máxima cobertura de campos
          Motor reportado: 'google_document_ai+rapid_ocr' (si ambos fusionados)

        Modo SOLO DocAI (si Fast-Path completo o RapidOCR no disponible):
          Motor reportado: 'google_document_ai'

        Modo SOLO RapidOCR (si DocAI falla o no disponible):
          Motor reportado: 'rapid_ocr'

        Fallback TESSERACT (si todos los anteriores fallan):
          Motor reportado: 'tesseract_fallback'

        Returns:
            Tupla (texto: str, motor: str, res_estructurado: Optional[StructuredDocumentAIResult])
        """
        import cv2
        from app.services.google_document_ai_service import StructuredDocumentAIResult

        texto_docai: str = ""
        res_docai = None

        # ── Paso 1: Google Document AI (Smart Fast-Path) ───────────────────
        if google_document_ai_service.disponible:
            try:
                # JPEG calidad 90: compresión ultrarrápida (~10ms vs 200ms PNG) y peso reducido 70%
                success, img_encoded = cv2.imencode(".jpg", img_np, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
                if not success:
                    raise ValueError("No se pudo codificar la imagen a JPEG")
                img_bytes = img_encoded.tobytes()

                res_docai = google_document_ai_service.procesar_documento_estructurado(
                    img_bytes, mime_type="image/jpeg", pagina_num_base=pagina_num
                )
                texto_docai = res_docai.text or ""

                if texto_docai.strip():
                    palabras = re.findall(r"[A-Za-záéíóúñÁÉÍÓÚÑ]{3,}", texto_docai)
                    logger.info(
                        f"[DocAI] Página {pagina_num}: OK "
                        f"({len(texto_docai)} chars, {len(palabras)} palabras, {res_docai.tiempo_ms:.1f}ms)"
                    )
                    # FAST-PATH INTELIGENTE (Opción A):
                    # Solo retorna inmediatamente si la estructura y confianza son completas
                    es_completo, motivo = self._es_extraccion_docai_completa(texto_docai, res_docai, pagina_num)
                    if es_completo:
                        logger.info(
                            f"[SmartDualOCR] Página {pagina_num}: Fast-Path activo ({motivo}) -> Retorno directo DocAI"
                        )
                        return texto_docai, "google_document_ai", res_docai
                    else:
                        logger.info(
                            f"[SmartDualOCR] Página {pagina_num}: DocAI requiere rescate ({motivo}) -> Activando RapidOCR..."
                        )
                else:
                    logger.warning(f"[DocAI] Página {pagina_num}: texto vacío")
                    res_docai = None

            except Exception as e:
                logger.error(f"[DocAI] Página {pagina_num}: Error ({type(e).__name__}: {e})")
                res_docai = None
        else:
            logger.info(f"[OCR] Página {pagina_num}: Google Document AI no disponible")

        # ── Paso 2: RapidOCR — corre SIEMPRE (no solo como fallback) ─────
        texto_rapid: str = ""
        res_rapid = None

        if rapid_ocr_service.disponible:
            try:
                texto_rapid, conf_rapid, res_rapid = rapid_ocr_service.procesar_imagen(
                    img_np, pagina_num=pagina_num
                )
                texto_rapid = texto_rapid or ""
                if texto_rapid.strip():
                    logger.info(
                        f"[RapidOCR] Página {pagina_num}: OK "
                        f"({len(texto_rapid)} chars, confianza={conf_rapid:.1f}%)"
                    )
                else:
                    logger.warning(f"[RapidOCR] Página {pagina_num}: texto vacío")
                    texto_rapid = ""
                    res_rapid = None
            except Exception as e:
                logger.error(f"[RapidOCR] Página {pagina_num}: Error ({type(e).__name__}: {e})")
                texto_rapid = ""
                res_rapid = None
        else:
            logger.info(f"[RapidOCR] Página {pagina_num}: motor no disponible")

        # ── Paso 3: Fusión inteligente de resultados ─────────────────────
        # Caso A: Ambos motores tienen texto → fusionar
        if texto_docai.strip() and texto_rapid.strip():
            texto_fusionado, lineas_nuevas = self._fusionar_texto_dual(texto_docai, texto_rapid)
            motor = "google_document_ai+rapid_ocr"
            # Actualizar el texto en el resultado estructurado de DocAI (mantiene su layout superior)
            if lineas_nuevas > 0:
                logger.info(
                    f"[DualOCR] Página {pagina_num}: Fusión exitosa — "
                    f"{lineas_nuevas} línea(s) nueva(s) de RapidOCR añadidas al texto de DocAI"
                )
                # Crear copia del resultado con texto enriquecido manteniendo las páginas/layout de DocAI
                res_final = StructuredDocumentAIResult(
                    text=texto_fusionado,
                    tiempo_ms=res_docai.tiempo_ms,
                    pages=res_docai.pages,
                )
            else:
                logger.info(f"[DualOCR] Página {pagina_num}: Ambos motores coincidentes — sin líneas adicionales")
                res_final = res_docai
            
            # FIX: Si DocAI tiene layout con 0 líneas pero RapidOCR si tiene bounding boxes,
            # usar el layout de RapidOCR como fuente espacial principal
            docai_lines = []
            if res_final.pages:
                docai_lines = getattr(res_final.pages[0], "lines", [])
            rapid_lines = []
            if res_rapid and res_rapid.pages:
                rapid_lines = getattr(res_rapid.pages[0], "lines", [])
            if len(docai_lines) == 0 and len(rapid_lines) > 0:
                logger.info(
                    f"[DualOCR] Página {pagina_num}: Layout DocAI vacío — usando layout de RapidOCR "
                    f"({len(rapid_lines)} líneas)"
                )
                res_final = StructuredDocumentAIResult(
                    text=texto_fusionado,
                    tiempo_ms=res_final.tiempo_ms,
                    pages=res_rapid.pages,
                )
            return texto_fusionado, motor, res_final

        # Caso B: Solo DocAI tiene texto
        if texto_docai.strip():
            return texto_docai, "google_document_ai", res_docai

        # Caso C: Solo RapidOCR tiene texto (DocAI falló)
        if texto_rapid.strip():
            logger.info(f"[RapidOCR] Página {pagina_num}: Usando RapidOCR como motor principal (DocAI sin resultado)")
            return texto_rapid, "rapid_ocr", res_rapid

        # ── Paso 4: Tesseract (último fallback si ambos fallaron) ─────────
        logger.warning(f"[Tesseract] Página {pagina_num}: Todos los motores principales fallaron, usando Tesseract")
        img_procesada = self.image_processor.preprocess(img_np)
        texto_tess = self._ocr_con_tesseract(img_procesada, pagina_num=pagina_num)
        return texto_tess, "tesseract_fallback", None

    def _fusionar_texto_dual(self, texto_principal: str, texto_secundario: str) -> tuple[str, int]:
        """
        Fusiona dos textos OCR usando el principal como base y añadiendo
        líneas únicas del secundario que no hayan sido capturadas.

        Usa rapidfuzz para detectar líneas similares (umbral 82%) evitando duplicados.
        Ignora líneas de menos de 3 caracteres.

        Returns:
            (texto_fusionado: str, cantidad_lineas_nuevas: int)
        """
        from rapidfuzz import fuzz

        lineas_base = [l.strip() for l in texto_principal.split("\n") if l.strip()]
        lineas_secundarias = [l.strip() for l in texto_secundario.split("\n") if len(l.strip()) >= 3]

        lineas_nuevas: list[str] = []
        for linea in lineas_secundarias:
            linea_up = linea.upper()
            # Verificar si ya existe una línea similar en el texto base
            ya_existe = any(
                fuzz.ratio(linea_up, lb.upper()) >= 82
                for lb in lineas_base
                if lb.strip()
            )
            if not ya_existe:
                lineas_nuevas.append(linea)

        if lineas_nuevas:
            texto_fusionado = texto_principal.rstrip() + "\n" + "\n".join(lineas_nuevas)
        else:
            texto_fusionado = texto_principal

        return texto_fusionado, len(lineas_nuevas)


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
        excel_lookup: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Guarda o actualiza la persona en la BD.
        Si excel_lookup esta disponible, los nombres y apellidos se toman
        de la planilla oficial usando el numero de identificacion como clave.
        """
        try:
            from app.models.persona import Persona
            from app.models.documento import Documento
            from datetime import datetime
            import uuid

            from app.utils.validators import validador
            from app.services.colombia_geo_service import colombia_geo

            def _es_nombre_invalido(val: Optional[str]) -> bool:
                if not val:
                    return True
                from app.utils.name_cleaner import es_linea_ruido_administrativo, es_token_ruido
                if es_linea_ruido_administrativo(str(val)):
                    return True
                v_up = str(val).strip().upper()
                if v_up in {
                    "POR REVISAR", "BLICA", "PUBLICA", "REPÚBLICA", "REPUBLICA", "COLOMBIA", "DE COLOMBIA",
                    "PERSONAL", "CEDULA", "CIUDADANIA", "DOCUMENTO", "IDENTIFICACION", "TARJETA",
                    "TARJETA DE IDENTIDAD", "CEDULA DE CIUDADANIA", "NUBLIC", "NUBLICA", "RUBLIC", "RUBLICA",
                    "UBLIC", "UBLICA", "CAPE", "CAFE", "CP"
                }:
                    return True
                if any(hdr in v_up for hdr in [
                    "CIUDAD", "CIUDADA", "CEDU", "COLOM", "REPUBLI", "REPÚBLI", "NUBLI", "RUBLI",
                    "REGISTRAD", "ESTADO CIVIL", "INDICE", "FIRMA", "PERSONAL", "IDENTIFIC", "CAMSCANNER",
                    "FOTOCOPIA", "PROCESO", "INSCRIPCION", "INSCRIPCIÓN", "MATRICULA", "MATRÍCULA", "EMPRENDEDORA", "EMPRENDEDOR", "SENA", "CAMPESINA", "FULLPOPULAR"
                ]):
                    return True
                if all(es_token_ruido(tok) for tok in v_up.split()):
                    return True
                if colombia_geo.es_geografico(v_up):
                    return True
                return False

            raw_id = datos.get("identificacion")
            id_limpio = validador.limpiar_identificacion(raw_id)
            nombres_val = datos.get("nombres")
            apellidos_val = datos.get("apellidos")
            confianza = float(datos.get("confianza_extraccion") or 0.0)

            # Criterio estricto de Entidad Ciudadana:
            # Una nueva persona se crea si tiene identificación válida O (nombres y apellidos reales).
            # Se descartan reversos huérfanos que no tienen cara frontal ni nombres, y topónimos como CAQUETA SOLANO.
            tiene_identificacion = bool(id_limpio and not id_limpio.startswith("SIN_ID"))
            tiene_nombres = bool(nombres_val and str(nombres_val).strip() and not _es_nombre_invalido(nombres_val))
            tiene_apellidos = bool(apellidos_val and str(apellidos_val).strip() and not _es_nombre_invalido(apellidos_val))
            es_reverso_huerfano = bool(datos.get("pagina_reverso") and not datos.get("pagina_frente") and not (tiene_nombres or tiene_apellidos))

            # Si no hay identificación detectada, dejar en blanco ("") en lugar de un código artificial SIN_ID_...
            # para que el usuario pueda editar el campo limpiamente en la interfaz.
            num_doc = id_limpio if tiene_identificacion else ""

            doc_exists = (
                db.query(Documento).filter(Documento.id == documento_id).first()
                if documento_id
                else None
            )
            doc_id_val = str(doc_exists.id) if doc_exists else None
            doc_usuario_id = doc_exists.usuario_id if doc_exists else None

            # Verificar si ya existe en BD para unificar (solo si tiene identificación válida; nunca unificar por cadena vacía)
            persona_existente = None
            if tiene_identificacion and num_doc:
                query_existente = db.query(Persona).filter(Persona.numero_identificacion == str(num_doc))
                if doc_usuario_id:
                    query_existente = query_existente.filter(Persona.usuario_id == doc_usuario_id)
                persona_existente = query_existente.first()

            # Si es un reverso huérfano sin nombres y no existe en BD, omitir para no crear persona fantasma
            if es_reverso_huerfano and not persona_existente:
                logger.info(f"Omitiendo guardado: página/grupo {datos.get('grupo_documento_id')} es reverso huérfano sin nombres (evita personas fantasma)")
                return None

            # REGLA CERO DESCARTE: Si una página/grupo no logró extraer identificación ni nombres limpios,
            # NUNCA se descarta para garantizar que todas las personas del documento se guarden en la base de datos.
            # Se guarda con número vacío ("") y estado REVIEW_REQUIRED para que el usuario pueda editarla fácilmente.

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
                or not num_doc
                or "SIN_ID" in str(num_doc)
            )

            if ocr_engine == "tesseract_fallback":
                estado_reg = "FALLBACK_TESSERACT"
            elif requiere_revision:
                estado_reg = "REVIEW_REQUIRED"
            else:
                estado_reg = "VALID"

            persona = None
            if tiene_identificacion and num_doc:
                query_persona = db.query(Persona).filter(Persona.numero_identificacion == str(num_doc))
                if doc_usuario_id:
                    query_persona = query_persona.filter(Persona.usuario_id == doc_usuario_id)
                persona = query_persona.first()

            nombres_final = datos.get("nombres") if not _es_nombre_invalido(datos.get("nombres")) else "POR REVISAR"
            apellidos_final = datos.get("apellidos") if not _es_nombre_invalido(datos.get("apellidos")) else "POR REVISAR"

            # ── Enriquecimiento con planilla oficial Excel ──────────────────────
            from app.utils.name_cleaner import resolver_nombre_completo
            from app.services.comparacion_service import comparacion_service

            # Nombre que el OCR leyó directamente de la cédula física
            nom_ocr_cedula = resolver_nombre_completo(
                nombres=nombres_final if nombres_final != "POR REVISAR" else "",
                apellidos=apellidos_final if apellidos_final != "POR REVISAR" else "",
                actual=datos.get("nombre_completo") or ""
            ).strip()

            fuente_nombre = "ocr"
            encontrado_en_excel = False
            nombre_completo_final = None
            discrepancia_nombre_excel = None

            if not excel_lookup:
                try:
                    from app.services.excel_lookup_service import excel_lookup_service
                    from app.models.comparacion import Comparacion
                    comp_q = db.query(Comparacion).filter(Comparacion.ruta_archivo.isnot(None))
                    if doc_usuario_id:
                        comp = comp_q.filter(Comparacion.usuario_id == doc_usuario_id).order_by(Comparacion.fecha_carga.desc()).first()
                    else:
                        comp = None
                    if comp:
                        ruta_comp = comp.obtener_ruta_o_restaurar(db)
                        if ruta_comp and ruta_comp.exists():
                            excel_lookup = excel_lookup_service.cargar_lookup(str(ruta_comp))
                except Exception as e_lk:
                    logger.warning(f"[ExcelLookup] No se pudo cargar planilla para OCR: {e_lk}")

            # ── Verificación exhaustiva bidireccional OCR vs Excel ──
            from app.services.excel_lookup_service import excel_lookup_service
            id_original_ocr = str(num_doc) if num_doc else ""

            verif = excel_lookup_service.verificar_exhaustiva_ocr_excel(
                id_ocr=num_doc,
                nombre_ocr=nom_ocr_cedula,
                nombres_ocr=nombres_final if nombres_final != "POR REVISAR" else "",
                apellidos_ocr=apellidos_final if apellidos_final != "POR REVISAR" else "",
                lookup=excel_lookup,
                texto_ocr=texto_ocr
            )

            encontrado_en_excel = verif["encontrado_en_excel"]
            fuente_nombre = verif["fuente_nombre"]
            nombre_completo_final = verif["nombre_final"]
            nombres_final = verif["nombres_final"]
            apellidos_final = verif["apellidos_final"]
            discrepancia_nombre_excel = verif["discrepancia_excel"]
            id_corregido = verif["id_final"]
            if verif.get("id_original_ocr"):
                id_original_ocr = verif["id_original_ocr"]

            # Si hubo auto-corrección de identificación justificada y verificada
            if id_corregido and str(id_corregido) != str(num_doc) and verif["fuente_identificacion"] == "corregido_desde_excel":
                logger.info(
                    f"[ExcelLookup] Auto-corrigiendo identificación por validación exhaustiva: "
                    f"OCR='{num_doc}' -> Corregido a '{id_corregido}' desde planilla oficial Excel"
                )
                id_anterior = num_doc
                num_doc = id_corregido
                id_limpio = id_corregido
                datos["identificacion"] = id_corregido

                query_existente = db.query(Persona).filter(Persona.numero_identificacion == id_corregido)
                if doc_usuario_id:
                    query_existente = query_existente.filter(Persona.usuario_id == doc_usuario_id)
                persona_oficial = query_existente.first()

                if persona:
                    if persona_oficial and persona_oficial.id != persona.id:
                        logger.info(f"[ExcelLookup] Fusionando registro erróneo '{id_anterior}' con registro existente '{id_corregido}'")
                        db.delete(persona)
                        persona = persona_oficial
                    else:
                        persona.numero_identificacion = id_corregido
                elif persona_oficial:
                    persona = persona_oficial

            # Limpieza complementaria si el nombre proviene del documento físico
            if fuente_nombre == "cedula_fisica" and nombres_final and nombres_final != "POR REVISAR":
                from app.services.spatial_field_extractor import spatial_field_extractor
                toks = [w for w in nombres_final.split() if not spatial_field_extractor.NO_NOMBRE_HEADER.search(w)]
                while toks and toks[0].upper() in {"DE", "DEL", "LA", "LAS", "LOS", "SAN", "SANTA"} and len(toks) > 1:
                    toks.pop(0)
                nombres_final = " ".join(toks).strip() or "POR REVISAR"

                if apellidos_final and apellidos_final != "POR REVISAR":
                    toks_a = [w for w in apellidos_final.split() if not spatial_field_extractor.NO_NOMBRE_HEADER.search(w)]
                    while toks_a and toks_a[0].upper() in {"DE", "DEL", "LA", "LAS", "LOS", "SAN", "SANTA"} and len(toks_a) > 1:
                        toks_a.pop(0)
                    apellidos_final = " ".join(toks_a).strip() or "POR REVISAR"

                if not nombre_completo_final or nombre_completo_final == "POR REVISAR":
                    from app.utils.name_cleaner import resolver_nombre_completo
                    nombre_completo_final = resolver_nombre_completo(
                        nombres=nombres_final if nombres_final != "POR REVISAR" else "",
                        apellidos=apellidos_final if apellidos_final != "POR REVISAR" else "",
                        actual=nom_ocr_cedula
                    )

            # ── Evaluación definitiva de completitud y validez ──
            detalles_payload = dict(datos.get("detalles_campos") or {})

            if id_original_ocr and str(num_doc) != id_original_ocr:
                detalles_payload["numero_identificacion_original_ocr"] = id_original_ocr
                detalles_payload["origen_identificacion"] = "corregido_desde_excel"
                detalles_payload["numero_identificacion"] = {
                    "valor": str(num_doc),
                    "value": str(num_doc),
                    "confidence": 1.0,
                    "status": "VALID",
                    "source": "excel_oficial",
                    "reason": f"Cédula corregida automáticamente desde la planilla oficial Excel (OCR leyó: {id_original_ocr})"
                }

            if discrepancia_nombre_excel:
                detalles_payload["discrepancia_excel"] = discrepancia_nombre_excel
                detalles_payload["nombre_completo"] = {
                    "valor": nombre_completo_final,
                    "value": nombre_completo_final,
                    "confidence": round(confianza / 100.0, 2),
                    "status": "REVIEW_REQUIRED",
                    "source": "cedula_fisica",
                    "reason": discrepancia_nombre_excel["motivo"]
                }
            elif encontrado_en_excel and nombre_completo_final:
                detalles_payload["nombre_completo"] = {
                    "valor": nombre_completo_final,
                    "value": nombre_completo_final,
                    "confidence": 1.0,
                    "status": "VALID",
                    "source": "excel_oficial",
                    "reason": "Nombre oficial extraído de la planilla Excel"
                }
                if "nombres" in detalles_payload and isinstance(detalles_payload["nombres"], dict):
                    detalles_payload["nombres"]["status"] = "VALID"
                if "apellidos" in detalles_payload and isinstance(detalles_payload["apellidos"], dict):
                    detalles_payload["apellidos"]["status"] = "VALID"
            elif nombre_completo_final and nombre_completo_final != "POR REVISAR":
                es_val_nom, mot_val_nom = validador.validar_nombre_estricto(nombre_completo_final)
                detalles_payload["nombre_completo"] = {
                    "valor": nombre_completo_final,
                    "value": nombre_completo_final,
                    "confidence": round(confianza / 100.0, 2),
                    "status": "VALID" if es_val_nom else "REVIEW_REQUIRED",
                    "source": ocr_engine,
                    "reason": "Nombre completo extraído y consolidado" if es_val_nom else mot_val_nom
                }
                if not es_val_nom:
                    if "nombres" in detalles_payload and isinstance(detalles_payload["nombres"], dict):
                        detalles_payload["nombres"]["status"] = "REVIEW_REQUIRED"
                    if "apellidos" in detalles_payload and isinstance(detalles_payload["apellidos"], dict):
                        detalles_payload["apellidos"]["status"] = "REVIEW_REQUIRED"
                else:
                    if "nombres" in detalles_payload and isinstance(detalles_payload["nombres"], dict):
                        detalles_payload["nombres"]["status"] = "VALID"
                    if "apellidos" in detalles_payload and isinstance(detalles_payload["apellidos"], dict):
                        detalles_payload["apellidos"]["status"] = "VALID"
            tiene_datos_completos, motivos_rev = validador.evaluar_persona_completa(
                numero_identificacion=str(num_doc),
                nombres=nombres_final,
                apellidos=apellidos_final,
                nombre_completo=nombre_completo_final,
                fecha_nacimiento=fecha_nac,
                fecha_expedicion=fecha_exp,
                lugar_expedicion=datos.get("lugar_expedicion"),
                sexo=(datos.get("sexo") or "")[:10] if datos.get("sexo") else None,
                confianza=confianza,
                detalles_campos=detalles_payload,
                motor_ocr=ocr_engine,
                tipo_documento=datos.get("tipo_documento") or "UNKNOWN",
            )

            requiere_revision = not tiene_datos_completos or bool(discrepancia_nombre_excel) or bool(detalles_payload.get("discrepancia_documento_edad"))
            if ocr_engine == "tesseract_fallback":
                estado_reg = "FALLBACK_TESSERACT"
            elif not requiere_revision:
                estado_reg = "VALID"
            else:
                estado_reg = "REVIEW_REQUIRED"

            if motivos_rev:
                detalles_payload["motivos_revision"] = list(motivos_rev)
                if discrepancia_nombre_excel and discrepancia_nombre_excel.get("motivo") not in detalles_payload["motivos_revision"]:
                    detalles_payload["motivos_revision"].insert(0, discrepancia_nombre_excel["motivo"])
            elif discrepancia_nombre_excel:
                detalles_payload["motivos_revision"] = [discrepancia_nombre_excel["motivo"]]

            if not persona:
                persona = Persona(
                    documento_id=doc_id_val,
                    usuario_id=doc_usuario_id,
                    grupo_documento_id=datos.get("grupo_documento_id", "DOC-001"),
                    pagina_frente=datos.get("pagina_frente"),
                    pagina_reverso=datos.get("pagina_reverso"),
                    numero_identificacion=str(num_doc),
                    nombre_completo=nombre_completo_final,
                    nombres=nombres_final,
                    apellidos=apellidos_final,
                    fecha_nacimiento=fecha_nac,
                    fecha_expedicion=fecha_exp,
                    lugar_expedicion=datos.get("lugar_expedicion"),
                    sexo=(datos.get("sexo") or "")[:10] if datos.get("sexo") else None,
                    pagina_numero=pagina_num,
                    tipo_documento=datos.get("tipo_documento") or "UNKNOWN",
                    estado_registro=estado_reg,
                    motor_ocr=ocr_engine,
                    confianza_extraccion=confianza,
                    requiere_revision=requiere_revision,
                    detalles_campos=detalles_payload,
                    texto_ocr_crudo=(texto_ocr or "")[:5000],
                )
                db.add(persona)
                logger.info(f"Registrada nueva persona: {num_doc} ({persona.nombre_completo}) [Estado: {estado_reg}] (Revisión: {requiere_revision})")
            else:
                # ── UNIFICACIÓN INTELIGENTE DE HOJAS / PÁGINAS ──
                # Si la cédula ya existe (ej. repartida en 2 hojas), no duplicar y fusionar datos faltantes
                logger.info(f"Unificando datos para persona existente ID '{num_doc}'...")
                if doc_id_val:
                    persona.documento_id = doc_id_val
                if doc_usuario_id and not persona.usuario_id:
                    persona.usuario_id = doc_usuario_id
                if str(persona.numero_identificacion) != str(num_doc):
                    persona.numero_identificacion = str(num_doc)

                # Unificar páginas de frente y reverso
                if not persona.pagina_frente and datos.get("pagina_frente"):
                    persona.pagina_frente = datos["pagina_frente"]
                if not persona.pagina_reverso and datos.get("pagina_reverso"):
                    persona.pagina_reverso = datos["pagina_reverso"]
                elif not persona.pagina_reverso and datos.get("pagina_frente") and persona.pagina_frente != datos.get("pagina_frente"):
                    persona.pagina_reverso = datos.get("pagina_frente")

                # Nombre Completo, Nombres y Apellidos
                if discrepancia_nombre_excel:
                    persona.nombre_completo = nombre_completo_final
                    persona.nombres = nombres_final
                    persona.apellidos = apellidos_final
                elif fuente_nombre == "excel_oficial" and nombre_completo_final:
                    persona.nombre_completo = nombre_completo_final
                    persona.nombres = nombres_final
                    persona.apellidos = apellidos_final
                elif (not persona.nombre_completo or persona.nombre_completo == "POR REVISAR") and nombre_completo_final != "POR REVISAR":
                    persona.nombre_completo = nombre_completo_final
                    if nombres_final and nombres_final != "POR REVISAR":
                        persona.nombres = nombres_final
                    if apellidos_final and apellidos_final != "POR REVISAR":
                        persona.apellidos = apellidos_final
                elif nombre_completo_final and nombre_completo_final != "POR REVISAR":
                    # Si el registro en BD contiene duplicaciones o si nombre_completo_final es una versión deduplicada y válida
                    from app.utils.name_cleaner import deduplicar_tokens_nombre, deduplicar_ngrams
                    nom_bd_dedup = deduplicar_tokens_nombre(deduplicar_ngrams(persona.nombre_completo or ""))
                    if nom_bd_dedup != (persona.nombre_completo or "") or (persona.nombre_completo != nombre_completo_final and len(nombre_completo_final.split()) >= 2):
                        persona.nombre_completo = nombre_completo_final
                        if nombres_final and nombres_final != "POR REVISAR":
                            persona.nombres = nombres_final
                        if apellidos_final and apellidos_final != "POR REVISAR":
                            persona.apellidos = apellidos_final

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

                # Resolver tipo_documento usando prioridad: TI > CC > UNKNOWN
                # Nunca dejar que CEDULA_CIUDADANIA sobrescriba TARJETA_IDENTIDAD
                from app.services.document_pairing_service import _resolver_tipo_documento as _res_tipo
                nuevo_tipo = datos.get("tipo_documento") or "UNKNOWN"
                actual_tipo = persona.tipo_documento or "UNKNOWN"
                tipo_resuelto = _res_tipo(actual_tipo, nuevo_tipo)
                if tipo_resuelto and tipo_resuelto != "UNKNOWN":
                    persona.tipo_documento = tipo_resuelto
                if not persona.sexo and datos.get("sexo"):
                    persona.sexo = str(datos["sexo"])[:10]

                # Fusión de detalles de campos
                detalles_existentes = dict(persona.detalles_campos or {})
                detalles_nuevos = dict(datos.get("detalles_campos") or {})
                for k, v in detalles_nuevos.items():
                    if k not in detalles_existentes or not detalles_existentes[k].get("valor"):
                        detalles_existentes[k] = v
                if discrepancia_nombre_excel:
                    detalles_existentes["discrepancia_excel"] = discrepancia_nombre_excel
                persona.detalles_campos = detalles_existentes

                # Unificar texto crudo
                if texto_ocr and texto_ocr not in (persona.texto_ocr_crudo or ""):
                    persona.texto_ocr_crudo = f"{(persona.texto_ocr_crudo or '').strip()}\n---\n{texto_ocr}".strip()[:5000]

                # Ajuste de confianza
                if confianza > float(persona.confianza_extraccion or 0):
                    persona.confianza_extraccion = confianza
                    persona.motor_ocr = ocr_engine

                # Reevaluar si ya no requiere revisión tras la unificación de ambas hojas
                detalles_existentes = dict(persona.detalles_campos or {})
                tiene_datos_completos, motivos_rev = validador.evaluar_persona_completa(
                    numero_identificacion=persona.numero_identificacion,
                    nombres=persona.nombres,
                    apellidos=persona.apellidos,
                    nombre_completo=persona.nombre_completo,
                    fecha_nacimiento=persona.fecha_nacimiento,
                    fecha_expedicion=persona.fecha_expedicion,
                    lugar_expedicion=persona.lugar_expedicion,
                    sexo=persona.sexo,
                    confianza=float(persona.confianza_extraccion or 0),
                    detalles_campos=detalles_existentes,
                    motor_ocr=persona.motor_ocr,
                    tipo_documento=persona.tipo_documento,
                )

                if tiene_datos_completos and not discrepancia_nombre_excel and "discrepancia_excel" not in detalles_existentes and "discrepancia_documento_edad" not in detalles_existentes:
                    persona.requiere_revision = False
                    persona.estado_registro = "VALID"
                    detalles_existentes.pop("motivos_revision", None)
                else:
                    persona.requiere_revision = True
                    persona.estado_registro = "FALLBACK_TESSERACT" if persona.motor_ocr == "tesseract_fallback" else "REVIEW_REQUIRED"
                    if motivos_rev:
                        detalles_existentes["motivos_revision"] = motivos_rev
                    elif discrepancia_nombre_excel:
                        detalles_existentes["motivos_revision"] = [discrepancia_nombre_excel["motivo"]]

                persona.detalles_campos = detalles_existentes
                persona.fecha_actualizacion = datetime.utcnow()

            db.commit()
            db.refresh(persona)

            return {
                "id": str(persona.id),
                "numero_identificacion": persona.numero_identificacion,
                "nombre_completo": persona.nombre_completo,
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
            if doc and doc.estado != "cancelado":
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
            if doc and doc.estado != "cancelado":
                from app.models.persona import Persona
                personas_db = db.query(Persona).filter(Persona.documento_id == doc.id).all()
                snapshot_personas = []
                for p in personas_db:
                    snapshot_personas.append({
                        "id": str(p.id),
                        "documento_id": str(doc.id),
                        "nombre_documento": doc.nombre_original,
                        "numero_identificacion": p.numero_identificacion,
                        "nombre_completo": p.nombre_completo,
                        "nombres": p.nombres,
                        "apellidos": p.apellidos,
                        "fecha_nacimiento": p.fecha_nacimiento.isoformat() if p.fecha_nacimiento else None,
                        "edad": p.edad,
                        "fecha_expedicion": p.fecha_expedicion.isoformat() if p.fecha_expedicion else None,
                        "lugar_expedicion": p.lugar_expedicion,
                        "sexo": p.sexo,
                        "tipo_documento": p.tipo_documento or "UNKNOWN",
                        "estado_registro": p.estado_registro or "VALID",
                        "confianza_extraccion": float(p.confianza_extraccion or 0),
                        "requiere_revision": bool(p.requiere_revision),
                        "pagina_frente": p.pagina_frente,
                        "pagina_reverso": p.pagina_reverso,
                        "pagina_numero": p.pagina_numero,
                        "motor_ocr": p.motor_ocr,
                        "detalles_campos": p.detalles_campos,
                    })

                doc.estado = "completado"
                doc.total_paginas = total_paginas
                doc.confianza_ocr = confianza  # confianza real
                doc.tiempo_procesamiento_ms = tiempo_ms or doc.tiempo_procesamiento_ms
                doc.fecha_procesamiento = datetime.utcnow()
                meta = dict(doc.metadatos or {})
                meta.update({
                    "progreso": 100,
                    "paso": f"Extracción completada con éxito ({len(snapshot_personas) or personas_count} personas encontradas)",
                    "pagina_actual": total_paginas,
                    "total_paginas": total_paginas,
                    "personas_extraidas": len(snapshot_personas) or personas_count,
                    "personas_extraidas_datos": snapshot_personas,
                    "tiempo_procesamiento_ms": tiempo_ms,
                })
                doc.metadatos = meta
                db.commit()
                logger.info(f"[OCR] Documento {doc.id} completado con {len(snapshot_personas)} personas en snapshot histórico")
        except Exception as e:
            logger.error(f"Error actualizando estado del documento: {e}")


# Instancia única del servicio
ocr_service = OCRService()

