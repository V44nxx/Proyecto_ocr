"""
Router de Documentos
Endpoints: Upload PDF, listar, detalle, eliminar, preview de página
"""
import uuid
import io
import shutil
from pathlib import Path
from typing import List, Optional, Union
from datetime import datetime
import threading

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, BackgroundTasks, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.documento import Documento
from app.models.usuario import Usuario
from app.schemas.documento import DocumentoResponse, PersonaResponse
from app.routers.auth import get_usuario_actual, get_usuario_desde_token_o_query
from app.services.ocr_service import ocr_service
from app.config import settings
from app.utils.logger import app_logger as logger

router = APIRouter(prefix="/api/documentos", tags=["Documentos"])


def _validar_pdf(file: UploadFile):
    """Valida que el archivo sea un PDF válido"""
    fname = (file.filename or "").strip()
    if not fname.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail=f"Solo se aceptan archivos PDF (extensión .pdf). Archivo recibido: '{fname}'"
        )


def _registrar_personas_excel_faltantes(
    items: List[dict],
    excel_path: str,
    db: Session,
):
    """
    Identifica las personas que se encuentran en la planilla oficial de Excel
    pero que no aparecieron en ninguno de los PDFs procesados en este lote.
    Inserta o actualiza dichos registros en la base de datos con los datos de la
    planilla, marcándolos en estado de revisión y con la alerta de que no se encontraron en el PDF.
    """
    from decimal import Decimal
    from app.models.persona import Persona
    from app.models.documento import Documento
    from app.services.comparacion_service import comparacion_service
    from app.utils.validators import validador

    if not items or not excel_path or not Path(excel_path).exists():
        return

    doc_ids = [item["documento_id"] for item in items]
    doc_principal = db.query(Documento).filter(Documento.id == doc_ids[0]).first()
    if not doc_principal:
        return
    doc_principal_id = doc_principal.id
    usuario_id = doc_principal.usuario_id

    # 1. Cargar todas las personas de la planilla Excel
    try:
        df_excel = comparacion_service.cargar_excel(excel_path)
    except Exception as e:
        logger.warning(f"[PersonasFaltantesExcel] No se pudo leer Excel {excel_path}: {e}")
        return

    if df_excel is None or df_excel.empty or "numero_identificacion" not in df_excel.columns:
        return

    # 2. Obtener las personas que SÍ fueron detectadas/guardadas en los PDFs de este lote
    personas_lote = db.query(Persona).filter(Persona.documento_id.in_(doc_ids)).all()
    ids_detectados_ocr = {
        comparacion_service._limpiar_numero_id(p.numero_identificacion)
        for p in personas_lote
        if p.numero_identificacion
    }
    nombres_detectados_ocr = [
        (p.nombre_completo or f"{p.nombres or ''} {p.apellidos or ''}").strip()
        for p in personas_lote
    ]

    personas_agregadas = 0

    # 3. Iterar registros del Excel y cotejar
    for _, row in df_excel.iterrows():
        id_excel = comparacion_service._limpiar_numero_id(row.get("numero_identificacion"))
        if not id_excel or len(id_excel) < 5:
            continue

        if id_excel in ids_detectados_ocr:
            continue

        nom_excel = str(row.get("nombre_completo") or "").strip()
        if not nom_excel:
            nom_p = str(row.get("nombres") or "").strip()
            ape_p = str(row.get("apellidos") or "").strip()
            nom_excel = f"{nom_p} {ape_p}".strip()

        coincide_por_nombre = False
        if nom_excel and len(nom_excel) >= 4:
            for nom_ocr in nombres_detectados_ocr:
                if nom_ocr and comparacion_service._son_nombres_equivalentes(
                    nombres_bd=nom_ocr,
                    apellidos_bd="",
                    nombres_excel=nom_excel,
                    apellidos_excel=""
                ):
                    coincide_por_nombre = True
                    break

        if coincide_por_nombre:
            continue

        # Esta persona ESTÁ en el Excel pero NO en el PDF.
        nombres_val = str(row.get("nombres") or "").strip() or nom_excel
        apellidos_val = str(row.get("apellidos") or "").strip()
        lugar_exp = str(row.get("lugar_expedicion") or "").strip() or None
        sexo_raw = str(row.get("sexo") or "").strip()
        sexo_val = validador.normalizar_sexo(sexo_raw) if sexo_raw else None

        fecha_nac = None
        if row.get("fecha_nacimiento"):
            fecha_nac = validador.parsear_fecha(str(row["fecha_nacimiento"]))

        fecha_exp = None
        if row.get("fecha_expedicion"):
            fecha_exp = validador.parsear_fecha(str(row["fecha_expedicion"]))

        tipo_doc_raw = str(row.get("tipo_documento") or "").strip().upper()
        if tipo_doc_raw:
            tipo_doc = tipo_doc_raw
        elif fecha_nac:
            edad = validador.calcular_edad(fecha_nac)
            tipo_doc = "TARJETA_IDENTIDAD" if (edad is not None and edad < 18) else "CEDULA_CIUDADANIA"
        else:
            tipo_doc = "CEDULA_CIUDADANIA"

        motivo_alerta = (
            "No se encontró en el PDF: Esta persona figura en la planilla oficial de Excel "
            "pero no fue detectada en el documento PDF adjunto."
        )

        detalles_payload = {
            "en_pdf": False,
            "origen": "excel_no_encontrado_en_pdf",
            "motivo_no_en_pdf": "No se encontró en el PDF",
            "motivos_revision": [motivo_alerta],
            "numero_identificacion": {
                "valor": id_excel,
                "confidence": 1.0,
                "status": "VALID",
                "source": "excel_oficial",
            },
            "nombre_completo": {
                "valor": nom_excel,
                "confidence": 1.0,
                "status": "VALID",
                "source": "excel_oficial",
            },
        }
        if nombres_val:
            detalles_payload["nombres"] = {"valor": nombres_val, "status": "VALID", "source": "excel_oficial"}
        if apellidos_val:
            detalles_payload["apellidos"] = {"valor": apellidos_val, "status": "VALID", "source": "excel_oficial"}
        if fecha_nac:
            detalles_payload["fecha_nacimiento"] = {"valor": fecha_nac.isoformat(), "status": "VALID", "source": "excel_oficial"}
        if fecha_exp:
            detalles_payload["fecha_expedicion"] = {"valor": fecha_exp.isoformat(), "status": "VALID", "source": "excel_oficial"}
        if lugar_exp:
            detalles_payload["lugar_expedicion"] = {"valor": lugar_exp, "status": "VALID", "source": "excel_oficial"}
        if sexo_val:
            detalles_payload["sexo"] = {"valor": sexo_val, "status": "VALID", "source": "excel_oficial"}

        query_p = db.query(Persona).filter(Persona.numero_identificacion == id_excel)
        if usuario_id:
            query_p = query_p.filter(Persona.usuario_id == usuario_id)
        persona_db = query_p.first()

        if persona_db:
            persona_db.documento_id = doc_principal_id
            persona_db.nombre_completo = nom_excel
            persona_db.nombres = nombres_val
            persona_db.apellidos = apellidos_val
            if fecha_nac:
                persona_db.fecha_nacimiento = fecha_nac
            if fecha_exp:
                persona_db.fecha_expedicion = fecha_exp
            if lugar_exp:
                persona_db.lugar_expedicion = lugar_exp
            if sexo_val:
                persona_db.sexo = sexo_val
            persona_db.tipo_documento = tipo_doc
            persona_db.requiere_revision = True
            persona_db.estado_registro = "REVIEW_REQUIRED"
            persona_db.motor_ocr = "excel"
            persona_db.pagina_frente = None
            persona_db.pagina_reverso = None
            persona_db.pagina_numero = None
            persona_db.detalles_campos = detalles_payload
            persona_db.texto_ocr_crudo = "[Registro cargado desde planilla Excel - No encontrado en PDF]"
            logger.info(
                f"[PersonasFaltantesExcel] Actualizada persona existente {id_excel} ({nom_excel}) como faltante en PDF"
            )
        else:
            import uuid as uuid_pkg
            ahora = datetime.utcnow()
            nueva_p = Persona(
                id=uuid_pkg.uuid4(),
                documento_id=doc_principal_id,
                usuario_id=usuario_id,
                grupo_documento_id="EXCEL-SIN-PDF",
                pagina_frente=None,
                pagina_reverso=None,
                pagina_numero=None,
                numero_identificacion=id_excel,
                nombre_completo=nom_excel,
                nombres=nombres_val,
                apellidos=apellidos_val,
                fecha_nacimiento=fecha_nac,
                fecha_expedicion=fecha_exp,
                lugar_expedicion=lugar_exp,
                sexo=sexo_val,
                tipo_documento=tipo_doc,
                estado_registro="REVIEW_REQUIRED",
                motor_ocr="excel",
                confianza_extraccion=Decimal("100.00"),
                requiere_revision=True,
                detalles_campos=detalles_payload,
                texto_ocr_crudo="[Registro cargado desde planilla Excel - No encontrado en PDF]",
                fecha_registro=ahora,
                fecha_actualizacion=ahora,
            )
            db.add(nueva_p)
            logger.info(
                f"[PersonasFaltantesExcel] Creada nueva persona {id_excel} ({nom_excel}) con datos de Excel y alerta 'No se encontró en el PDF'"
            )

        personas_agregadas += 1

    db.commit()

    if personas_agregadas > 0:
        personas_todas = db.query(Persona).filter(Persona.documento_id == doc_principal_id).all()
        snapshot_personas = []
        for p in personas_todas:
            snapshot_personas.append({
                "id": str(p.id),
                "documento_id": str(doc_principal_id),
                "nombre_documento": doc_principal.nombre_original,
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

        meta = dict(doc_principal.metadatos or {})
        meta.update({
            "personas_extraidas": len(snapshot_personas),
            "personas_extraidas_datos": snapshot_personas,
            "paso": f"Extracción completada con éxito ({len(snapshot_personas)} personas totales)",
        })
        doc_principal.metadatos = meta
        db.commit()
        logger.info(
            f"[PersonasFaltantesExcel] {personas_agregadas} persona(s) de Excel sin PDF registradas. Total documento: {len(snapshot_personas)}"
        )


def _procesar_batch_ocr_y_comparacion(
    items: List[dict],
    comparacion_id: Optional[str] = None,
    excel_path: Optional[str] = None,
):
    """
    Tarea en segundo plano que procesa el OCR de un lote de documentos secuencialmente.
    - Carga la planilla Excel para enriquecer nombres oficiales de las personas durante OCR.
    - Procesa cada documento PDF del lote.
    - Registra personas que estén en el Excel pero no en el PDF marcándolas para revisión.
    - Al finalizar el OCR de todos los documentos del lote, ejecuta la comparacion automatica
      en el módulo de Comparación una sola vez con todos los datos consolidados.
    """
    from app.database import SessionLocal
    from app.services.excel_lookup_service import excel_lookup_service
    from app.services.ocr_service import ocr_service

    db = SessionLocal()
    try:
        # ── Cargar lookup de nombres desde Excel (si existe) ──────────────
        excel_lookup = None
        if excel_path:
            try:
                excel_lookup = excel_lookup_service.cargar_lookup(excel_path)
                logger.info(
                    f"[OCR Batch Background] Lookup cargado: {len(excel_lookup)} registros "
                    f"para enriquecer nombres durante OCR."
                )
            except Exception as e_lookup:
                logger.error(f"[OCR Batch Background] Error cargando lookup Excel: {e_lookup}")
                excel_lookup = None

        # ── Procesar cada PDF del lote con OCR ───────────────────────────
        for item in items:
            pdf_path = item["pdf_path"]
            doc_id = item["documento_id"]
            try:
                logger.info(f"[OCR Batch Background] Procesando PDF: {pdf_path} (Doc ID: {doc_id})")
                ocr_service.procesar_pdf(
                    str(pdf_path),
                    doc_id,
                    db_externa=db,
                    excel_lookup=excel_lookup,
                )
                logger.info(f"[OCR Batch Background] OCR completado para Doc ID: {doc_id}")
            except Exception as e_ocr:
                logger.error(f"[OCR Batch Background] Error procesando OCR Doc ID {doc_id}: {e_ocr}")

        # ── Registrar personas en Excel que NO están en los PDFs del lote ──
        if excel_path and items:
            try:
                logger.info(f"[OCR Batch Background] Verificando personas de Excel no encontradas en PDF...")
                _registrar_personas_excel_faltantes(
                    items=items,
                    excel_path=excel_path,
                    db=db,
                )
            except Exception as e_falt:
                logger.error(f"[OCR Batch Background] Error registrando personas faltantes de Excel: {e_falt}")

        # ── Ejecutar comparación automática si se adjuntó planilla Excel ─
        if comparacion_id and excel_path:
            try:
                from app.services.comparacion_service import comparacion_service
                logger.info(
                    f"OCR finalizado para todos los {len(items)} documento(s). Iniciando comparación automática: {comparacion_id}"
                )
                comparacion_service.ejecutar_comparacion(
                    comparacion_id, excel_path, db
                )
                logger.info(f"Comparación automática completada con éxito: {comparacion_id}")
            except Exception as e_cmp:
                logger.error(
                    f"Error en comparación automática {comparacion_id}: {e_cmp}"
                )
    finally:
        db.close()


# ──────────────────────────────────────────
# ENDPOINTS
# ──────────────────────────────────────────
@router.post(
    "/upload",
    summary="Subir PDF(s) para procesamiento OCR con planilla oficial Excel",
    status_code=202
)
async def upload_pdf(
    background_tasks: BackgroundTasks,
    files: Optional[List[UploadFile]] = File(default=None, description="Uno o multiples archivos PDF"),
    file: Optional[UploadFile] = File(default=None, description="Archivo PDF individual"),
    excel: UploadFile = File(..., description="Planilla Excel oficial con nombres (.xlsx/.xls) — OBLIGATORIO"),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_actual),
):
    """
    Sube uno o multiples PDF junto con la planilla oficial Excel.
    El Excel es OBLIGATORIO: los nombres y apellidos de cada persona
    se toman de la planilla oficial buscando por numero de identificacion.
    Los demas datos (fechas, lugar, genero) se extraen del PDF via OCR.
    Al terminar el OCR, la comparacion se ejecuta automaticamente.
    """
    from app.models.comparacion import Comparacion
    from app.config import settings as cfg

    archivos_recibidos: List[UploadFile] = []
    if files:
        archivos_recibidos.extend([f for f in files if f and f.filename])
    if file and file.filename:
        archivos_recibidos.append(file)

    if not archivos_recibidos:
        raise HTTPException(status_code=400, detail="No se enviaron archivos PDF válidos")

    # ── Procesar Excel adjunto (si existe) ────────────────────────────────
    comparacion_id: Optional[str] = None
    excel_path_str: Optional[str] = None

    if excel and excel.filename:
        ext = Path(excel.filename).suffix.lower()
        if ext not in (".xlsx", ".xls"):
            raise HTTPException(
                status_code=400,
                detail=f"El archivo Excel debe tener extensión .xlsx o .xls. Recibido: {ext}"
            )
        excel_content = await excel.read()
        nombre_excel = f"comp_{uuid.uuid4()}{ext}"
        ruta_excel = settings.upload_path / nombre_excel
        ruta_excel.write_bytes(excel_content)

        comparacion = Comparacion(
            usuario_id=usuario.id,
            nombre_archivo=nombre_excel,
            nombre_original=excel.filename,
            ruta_archivo=str(ruta_excel),
            archivo_binario=excel_content,
            estado="pendiente",
        )
        db.add(comparacion)
        db.commit()
        db.refresh(comparacion)

        comparacion_id = str(comparacion.id)
        excel_path_str = str(ruta_excel)
        logger.info(
            f"Excel adjunto guardado para comparación automática: {excel.filename} (Comparacion ID: {comparacion_id})"
        )

    # ── Procesar cada PDF ─────────────────────────────────────────────────
    resultados = []
    items_para_procesar = []

    for pdf_file in archivos_recibidos:
        _validar_pdf(pdf_file)

        nombre_unico = f"{uuid.uuid4()}_{pdf_file.filename}"
        ruta_archivo = settings.upload_path / nombre_unico

        content = await pdf_file.read()
        ruta_archivo.write_bytes(content)

        documento = Documento(
            usuario_id=usuario.id,
            nombre_archivo=nombre_unico,
            nombre_original=pdf_file.filename,
            ruta_archivo=str(ruta_archivo),
            archivo_binario=content,
            tamano_bytes=len(content),
            estado="procesando",
        )
        db.add(documento)
        db.commit()
        db.refresh(documento)

        items_para_procesar.append({
            "pdf_path": str(ruta_archivo),
            "documento_id": str(documento.id),
        })

        logger.info(
            f"PDF guardado y encolado: {pdf_file.filename} (ID: {documento.id})"
        )

        resultados.append({
            "id": str(documento.id),
            "nombre_original": documento.nombre_original,
            "estado": "procesando",
            "mensaje": "Archivo recibido. Procesando páginas en segundo plano con Google Document AI.",
        })

    # Encolar procesamiento en batch para todos los PDFs
    background_tasks.add_task(
        _procesar_batch_ocr_y_comparacion,
        items_para_procesar,
        comparacion_id,
        excel_path_str,
    )

    logger.info(
        f"Lote de {len(items_para_procesar)} PDF(s) encolado para procesamiento OCR"
        + (f" y comparación automática en Comparación ({comparacion_id})" if comparacion_id else "")
    )

    return {
        "total": len(resultados),
        "documentos": resultados,
        "comparacion_id": comparacion_id,
        "comparacion_automatica": comparacion_id is not None,
    }


@router.get("", response_model=List[DocumentoResponse], summary="Listar documentos")
def listar_documentos(
    skip: int = 0,
    limit: int = 50,
    estado: str = None,
    solo_subida: bool = False,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_actual),
):
    """Lista los documentos propios del usuario actual (o todos si es admin)"""
    from sqlalchemy import or_

    query = db.query(Documento)
    if getattr(usuario, "rol", None) != "admin":
        query = query.filter(or_(Documento.usuario_id == usuario.id, Documento.usuario_id.is_(None)))

    if solo_subida:
        query = query.filter(or_(Documento.visible_en_subida == True, Documento.visible_en_subida.is_(None)))

    if estado:
        query = query.filter(Documento.estado == estado)

    documentos = query.order_by(Documento.fecha_carga.desc()).offset(skip).limit(limit).all()
    return [DocumentoResponse.model_validate(d) for d in documentos]


@router.get("/{documento_id}", response_model=DocumentoResponse, summary="Detalle de documento")
def obtener_documento(
    documento_id: str,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_actual),
):
    """Obtiene el detalle de un documento específico propio"""
    from sqlalchemy import or_
    query = db.query(Documento).filter(Documento.id == documento_id)
    if getattr(usuario, "rol", None) != "admin":
        query = query.filter(or_(Documento.usuario_id == usuario.id, Documento.usuario_id.is_(None)))
    documento = query.first()

    if not documento:
        raise HTTPException(status_code=404, detail="Documento no encontrado")

    return DocumentoResponse.model_validate(documento)


@router.get("/{documento_id}/personas", response_model=List[PersonaResponse], summary="Listar personas de un documento específico")
def listar_personas_documento(
    documento_id: str,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_actual),
):
    """
    Obtiene la lista de personas pertenecientes a este documento.
    Si las personas fueron eliminadas de la vista activa de la base de datos,
    utiliza el snapshot histórico inmutable guardado en metadatos para que
    el historial de archivos NUNCA aparezca sin personas.
    """
    from sqlalchemy import or_
    from app.models.persona import Persona
    from app.routers.personas import _obtener_ids_en_excel, _enriquecer_persona_response
    import re

    query = db.query(Documento).filter(Documento.id == documento_id)
    if getattr(usuario, "rol", None) != "admin":
        query = query.filter(or_(Documento.usuario_id == usuario.id, Documento.usuario_id.is_(None)))
    documento = query.first()

    if not documento:
        raise HTTPException(status_code=404, detail="Documento no encontrado")

    ids_en_excel, hay_excel = _obtener_ids_en_excel(db, usuario.id)

    # 1. Consultar personas activas en la BD vinculadas a este documento
    personas_db = db.query(Persona).filter(Persona.documento_id == documento.id).all()

    if personas_db and len(personas_db) > 0:
        return [_enriquecer_persona_response(p, ids_en_excel, hay_excel) for p in personas_db]

    # 2. Si la tabla activa no tiene personas (ej. se limpió la tabla o se desasoció),
    # recurrir al snapshot guardado en metadatos del documento
    meta = documento.metadatos or {}
    snapshot = meta.get("personas_extraidas_datos", [])
    if snapshot:
        resultado = []
        for s in snapshot:
            id_crudo = str(s.get("numero_identificacion") or "").strip()
            id_limpio = re.sub(r"[^\d]", "", id_crudo)
            en_excel = None
            if hay_excel:
                en_excel = bool(
                    (id_limpio and id_limpio in ids_en_excel) or
                    (id_crudo and id_crudo in ids_en_excel)
                )

            p_data = dict(s)
            det_s = dict(s.get("detalles_campos") or {})
            if det_s.get("en_pdf") is False or s.get("motor_ocr") == "excel":
                p_data["en_pdf"] = False
                p_data["requiere_revision"] = True
                if not p_data.get("estado_registro") or p_data.get("estado_registro") == "VALID":
                    p_data["estado_registro"] = "REVIEW_REQUIRED"
            else:
                p_data["en_pdf"] = True
            p_data["en_excel"] = en_excel
            if "fecha_registro" not in p_data or not p_data["fecha_registro"]:
                p_data["fecha_registro"] = documento.fecha_carga
            if "fecha_actualizacion" not in p_data or not p_data["fecha_actualizacion"]:
                p_data["fecha_actualizacion"] = documento.fecha_carga
            resultado.append(PersonaResponse.model_validate(p_data))
        return resultado

    return []


@router.get("/{documento_id}/estado", summary="Estado de procesamiento OCR")
def estado_documento(
    documento_id: str,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_actual),
):
    """Consulta el estado actual del procesamiento OCR de un documento propio"""
    from sqlalchemy import or_
    query = db.query(Documento).filter(Documento.id == documento_id)
    if getattr(usuario, "rol", None) != "admin":
        query = query.filter(or_(Documento.usuario_id == usuario.id, Documento.usuario_id.is_(None)))
    documento = query.first()

    if not documento:
        raise HTTPException(status_code=404, detail="Documento no encontrado")

    meta = documento.metadatos or {}
    progreso = meta.get("progreso")
    if progreso is None:
        if documento.estado == "completado":
            progreso = 100
        elif documento.estado == "procesando":
            progreso = 25
        elif documento.estado == "error":
            progreso = 100
        else:
            progreso = 0

    paso = meta.get("paso")
    if not paso:
        if documento.estado == "completado":
            paso = "Procesamiento completado"
        elif documento.estado == "procesando":
            paso = "Procesando documento con OCR..."
        elif documento.estado == "error":
            paso = "Error durante el procesamiento"
        else:
            paso = "Pendiente en cola"

    personas_count = len(documento.personas) if documento.personas else meta.get("personas_extraidas", 0)

    return {
        "id": str(documento.id),
        "nombre_original": documento.nombre_original,
        "estado": documento.estado,
        "progreso": progreso,
        "paso": paso,
        "total_paginas": documento.total_paginas or meta.get("total_paginas", 0),
        "pagina_actual": meta.get("pagina_actual", 0),
        "personas_count": personas_count,
        "confianza_ocr": float(documento.confianza_ocr) if documento.confianza_ocr else None,
        "tiempo_procesamiento_ms": documento.tiempo_procesamiento_ms,
        "mensaje_error": documento.mensaje_error,
        "fecha_procesamiento": documento.fecha_procesamiento,
        "metadatos": meta,
    }



@router.delete("/{documento_id}", summary="Eliminar o retirar documento del apartado de subida")
def eliminar_documento(
    documento_id: str,
    permanente: bool = Query(False, description="Si es False (default), solo se retira del apartado de subida preservando el historial y las personas extraídas"),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_actual),
):
    """
    Retira un documento del apartado de subida.
    Preserva el registro histórico en el Dashboard y conserva todas las personas extraídas y sus datos intactos.
    """
    from app.models.persona import Persona

    from sqlalchemy import or_
    query = db.query(Documento).filter(Documento.id == documento_id)
    if getattr(usuario, "rol", None) != "admin":
        query = query.filter(or_(Documento.usuario_id == usuario.id, Documento.usuario_id.is_(None)))
    documento = query.first()

    if not documento:
        raise HTTPException(status_code=404, detail="Documento no encontrado o no pertenece a su cuenta")

    if not permanente:
        # Retirar únicamente de la vista del apartado de subida
        documento.visible_en_subida = False
        meta = dict(documento.metadatos or {})
        meta["oculto_en_subida"] = True
        documento.metadatos = meta
        db.commit()
        logger.info(f"Documento retirado del apartado de subida (preservado en historial y personas): {documento.nombre_original}")
        return {
            "ok": True,
            "mensaje": "Documento retirado del apartado de subida. Su historial y personas asociadas continúan preservados en el sistema.",
            "documento_id": str(documento.id)
        }

    # 1. Si es eliminación permanente explícita: eliminar personas asociadas
    personas_query = db.query(Persona).filter(Persona.documento_id == documento.id)
    if getattr(usuario, "rol", None) != "admin":
        personas_query = personas_query.filter(
            (Persona.usuario_id == usuario.id) | (Persona.usuario_id.is_(None))
        )
    personas_eliminadas = personas_query.delete(synchronize_session=False)
    if personas_eliminadas:
        logger.info(f"Eliminadas {personas_eliminadas} persona(s) asociadas al documento {documento.nombre_original}")

    # 2. Eliminar archivo físico del PDF
    try:
        if documento.ruta_archivo and Path(documento.ruta_archivo).exists():
            Path(documento.ruta_archivo).unlink()
    except Exception as e:
        logger.warning(f"No se pudo eliminar archivo físico {documento.ruta_archivo}: {e}")

    # 3. Eliminar el documento de la base de datos
    db.delete(documento)
    db.commit()
    logger.info(f"Documento eliminado permanentemente: {documento.nombre_original} (usuario: {usuario.email})")
    return {"ok": True, "mensaje": f"Ficha '{documento.nombre_original}' eliminada del historial permanentemente"}


@router.get("/dashboard/estadisticas", summary="Estadísticas del dashboard")
def estadisticas_dashboard(
    documento_id: Optional[str] = Query(None, description="Filtrar estadísticas por ID de documento PDF específico"),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_actual),
):
    """Retorna estadísticas para el dashboard principal o para un documento específico"""
    from app.models.persona import Persona
    from app.models.comparacion import Comparacion
    from sqlalchemy import or_

    query_docs = db.query(Documento)
    query_personas = db.query(Persona).outerjoin(Persona.documento)
    query_comparaciones = db.query(Comparacion)

    if getattr(usuario, "rol", None) != "admin":
        query_docs = query_docs.filter(or_(Documento.usuario_id == usuario.id, Documento.usuario_id.is_(None)))
        query_personas = query_personas.filter(
            or_(
                Persona.usuario_id == usuario.id,
                Documento.usuario_id == usuario.id,
                Persona.detalles_campos["usuario_id"].astext == str(usuario.id)
            )
        )
        query_comparaciones = query_comparaciones.filter(or_(Comparacion.usuario_id == usuario.id, Comparacion.usuario_id.is_(None)))

    total_docs = query_docs.count()
    completados = query_docs.filter(Documento.estado == "completado").count()
    en_proceso = query_docs.filter(Documento.estado == "procesando").count()
    errores = query_docs.filter(Documento.estado == "error").count()

    query_revision = query_personas.filter(
        (Persona.requiere_revision == True) |
        (Persona.estado_registro.in_(["REVIEW_REQUIRED", "FALLBACK_TESSERACT"])) |
        (Persona.estado_registro != "VALID")
    )

    if documento_id and documento_id.strip() and documento_id != "todos":
        query_personas = query_personas.filter(Persona.documento_id == documento_id)
        query_revision = query_revision.filter(Persona.documento_id == documento_id)

    total_personas = query_personas.count()
    revision = query_revision.count()
    total_comparaciones = query_comparaciones.count()

    return {
        "total_documentos": total_docs,
        "documentos_completados": completados,
        "documentos_procesando": en_proceso,
        "documentos_con_error": errores,
        "total_personas": total_personas,
        "personas_en_revision": revision,
        "total_comparaciones": total_comparaciones,
    }


@router.get("/{documento_id}/debug_espacial", summary="Trazabilidad y cajas delimitadoras espaciales")
def debug_espacial_documento(
    documento_id: str,
    pagina: int = 1,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_actual),
):
    """Devuelve las cajas delimitadoras (LABEL, CANDIDATE, ACCEPTED, REJECTED) para depuración visual"""
    documento = db.query(Documento).filter(
        Documento.id == documento_id,
        Documento.usuario_id == usuario.id
    ).first()
    if not documento:
        raise HTTPException(status_code=404, detail="Documento no encontrado")

    from app.services.spatial_debug_service import spatial_debug_service
    # Para depuración visual, retornar reporte espacial de la página solicitada
    return spatial_debug_service.generar_reporte_debug(lines=[], page_num=pagina)


@router.get(
    "/{documento_id}/pagina/{numero}",
    summary="Vista previa de página del PDF como imagen",
    response_class=StreamingResponse,
)
def preview_pagina_pdf(
    documento_id: str,
    numero: int,
    request: Request,
    dpi: int = 150,
    token: Optional[str] = None,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_desde_token_o_query),
):
    """
    Renderiza la página `numero` (1-indexed) del PDF asociado al documento
    y la devuelve como imagen PNG. Permite al frontend mostrar una vista
    previa de la página exacta donde se detectó la persona.
    """
    from sqlalchemy import or_
    query = db.query(Documento).filter(Documento.id == documento_id)
    if getattr(usuario, "rol", None) != "admin":
        query = query.filter(or_(Documento.usuario_id == usuario.id, Documento.usuario_id.is_(None)))
    documento = query.first()

    if not documento:
        raise HTTPException(status_code=404, detail="Documento no encontrado")

    # 2. Verificar que el archivo existe en disco o auto-restaurarlo desde PostgreSQL
    ruta = documento.obtener_ruta_o_restaurar(db)
    if (not ruta or not ruta.exists()) and not documento.archivo_binario:
        raise HTTPException(
            status_code=404,
            detail=f"Archivo PDF no disponible en el servidor: {documento.nombre_original}"
        )

    # 3. Renderizar con PyMuPDF (abriendo desde archivo o directamente desde stream binario)
    try:
        import fitz  # PyMuPDF
        if ruta and ruta.exists():
            pdf_doc = fitz.open(str(ruta))
        elif documento.archivo_binario:
            pdf_doc = fitz.open(stream=documento.archivo_binario, filetype="pdf")
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Archivo PDF no disponible en el servidor: {documento.nombre_original}"
            )
        total_paginas = len(pdf_doc)

        # Convertir a 0-indexed y validar rango
        idx = numero - 1
        if idx < 0 or idx >= total_paginas:
            pdf_doc.close()
            raise HTTPException(
                status_code=400,
                detail=f"Página {numero} fuera de rango. El documento tiene {total_paginas} página(s)."
            )

        page = pdf_doc[idx]
        # Calcular zoom para el DPI solicitado (base PDF = 72 DPI)
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        png_bytes = pix.tobytes("png")
        pdf_doc.close()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error renderizando página {numero} del PDF {documento_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error al renderizar la página del PDF: {str(e)}")

    return StreamingResponse(
        io.BytesIO(png_bytes),
        media_type="image/png",
        headers={
            "Cache-Control": "public, max-age=3600",
            "Content-Disposition": f'inline; filename="doc_{documento_id}_p{numero}.png"',
        },
    )
