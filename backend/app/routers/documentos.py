"""
Router de Documentos
Endpoints: Upload PDF, listar, detalle, eliminar, preview de página
"""
import uuid
import io
import re
import shutil
from pathlib import Path
from typing import List, Optional, Union
from datetime import datetime
import threading
from pydantic import BaseModel

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form, BackgroundTasks, Query, status
from fastapi.responses import StreamingResponse, FileResponse, Response
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.documento import Documento
from app.models.usuario import Usuario
from app.schemas.documento import ERROR_FICHA, DocumentoResponse, PersonaResponse
from app.routers.auth import get_usuario_actual
from app.services import auditoria
from app.services.ocr_service import ocr_service
from app.config import settings
from app.utils.archivos import borrar_archivo_subido, nombre_archivo_seguro, numero_ficha_de, verificar_tamano_archivo
from app.utils.errores import mensaje_error_interno, mensaje_error_visible, nueva_referencia
from app.utils.logger import app_logger as logger, enmascarar_documento, enmascarar_nombre

router = APIRouter(prefix="/api/documentos", tags=["Documentos"])


def _validar_pdf(file: UploadFile):
    """Valida que el archivo sea un PDF válido"""
    fname = (file.filename or "").strip()
    if not fname.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail=f"Solo se aceptan archivos PDF (extensión .pdf). Archivo recibido: '{fname}'"
        )


# ──────────────────────────────────────────
# VERSIONES Y PARTES DE UNA FICHA
# Al subir un PDF de una ficha que ya existe (mismo número en el nombre), el usuario elige:
# - reemplazar: el PDF nuevo pasa a ser la ficha; la versión anterior se retira de la lista.
# - agregar: el PDF es otra parte de la misma ficha; sus personas quedan en la ficha existente.
# ──────────────────────────────────────────
ACCIONES_FICHA = ("reemplazar", "agregar")


def _es_ficha_principal(doc: Documento) -> bool:
    """Ficha que se ve en la lista: no es un PDF individual, ni una parte, ni una versión reemplazada"""
    meta = doc.metadatos if isinstance(doc.metadatos, dict) else {}
    return not (
        meta.get("es_pdf_individual") or meta.get("parte_de_ficha_id") or meta.get("reemplazado_por_id")
        or (doc.nombre_archivo or "").lower().startswith("cedula_")
    )


def _ficha_existente(db: Session, usuario_id, numero: Optional[str]) -> Optional[Documento]:
    """Ficha más reciente del usuario con ese número en el nombre del archivo"""
    if not numero:
        return None
    candidatos = (
        db.query(Documento)
        .filter(
            Documento.usuario_id == usuario_id,
            Documento.estado != "cancelado",
            or_(Documento.visible_en_subida == True, Documento.visible_en_subida.is_(None)),
            Documento.nombre_original.contains(numero),
        )
        .order_by(Documento.fecha_carga.desc())
        .all()
    )
    return next((d for d in candidatos if _es_ficha_principal(d) and numero_ficha_de(d.nombre_original) == numero), None)


def _aplicar_accion_ficha(db: Session, item: dict) -> None:
    """
    Tras el OCR del PDF nuevo, deja una sola ficha en la lista:
    - agregar: sus personas pasan a la ficha existente y el PDF queda como su documento (documento_pdf_id).
    - reemplazar: la versión anterior se retira; quien no aparece en el PDF nuevo no se borra,
      pasa a la ficha nueva para revisión, mostrando todavía su página del PDF anterior.
    """
    from app.models.persona import Persona

    accion, anterior_id, nuevo_id = item.get("accion"), item.get("documento_anterior_id"), item["documento_id"]
    if accion not in ACCIONES_FICHA or not anterior_id:
        return
    nuevo = db.query(Documento).filter(Documento.id == nuevo_id).first()
    anterior = db.query(Documento).filter(Documento.id == anterior_id).first()
    if not nuevo or not anterior or nuevo.estado != "completado":
        # Si el OCR falló, la ficha anterior se queda como estaba
        return

    if accion == "agregar":
        for p in db.query(Persona).filter(Persona.documento_id == nuevo.id).all():
            p.documento_id = anterior.id
            p.documento_pdf_id = nuevo.id
            det = dict(p.detalles_campos or {})
            det.update({"en_pdf": True, "documento_pdf_id": str(nuevo.id), "documento_padre_id": str(anterior.id)})
            p.detalles_campos = det
        logger.info(f"[Ficha] '{nuevo.nombre_original}' agregado como parte de '{anterior.nombre_original}'")
    else:
        motivo = (
            f"No se encontró en la nueva versión del PDF ({nuevo.nombre_original}). Verifique si debe seguir "
            f"en la ficha; se muestra su página de la versión anterior."
        )
        sin_encontrar = db.query(Persona).filter(Persona.documento_id == anterior.id).all()
        for p in sin_encontrar:
            p.documento_id = nuevo.id
            if p.motor_ocr == "excel":
                # Venía solo del Excel (Falta en PDF): no tiene página en ningún PDF
                continue
            if not p.documento_pdf_id:
                p.documento_pdf_id = anterior.id
            det = dict(p.detalles_campos or {})
            det["no_en_nueva_version"] = True
            det["motivos_revision"] = [motivo] + [m for m in (det.get("motivos_revision") or []) if m != motivo]
            p.detalles_campos = det
            p.requiere_revision = True
            if p.estado_registro != "FALLBACK_TESSERACT":
                p.estado_registro = "REVIEW_REQUIRED"
        # Las partes de la versión anterior pasan a ser partes de la nueva
        for parte in db.query(Documento).filter(Documento.usuario_id == anterior.usuario_id).all():
            meta_p = parte.metadatos if isinstance(parte.metadatos, dict) else {}
            if meta_p.get("parte_de_ficha_id") == str(anterior.id):
                parte.metadatos = dict(meta_p, parte_de_ficha_id=str(nuevo.id), documento_padre_id=str(nuevo.id))
        anterior.visible_en_subida = False
        anterior.metadatos = dict(anterior.metadatos or {}, reemplazado_por_id=str(nuevo.id))
        nuevo.metadatos = dict(nuevo.metadatos or {}, reemplaza_a_id=str(anterior.id))
        logger.info(
            f"[Ficha] '{nuevo.nombre_original}' reemplaza a '{anterior.nombre_original}': "
            f"{len(sin_encontrar)} persona(s) no encontradas en la versión nueva quedan para revisión"
        )
    db.commit()


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

    # Ficha donde quedan las personas de cada PDF (la existente si el PDF se agregó como otra parte)
    doc_ids = list(dict.fromkeys(
        item.get("documento_anterior_id") if item.get("accion") == "agregar" and item.get("documento_anterior_id")
        else item["documento_id"]
        for item in items
    ))
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

        if persona_db and str(persona_db.documento_id) not in {str(d) for d in doc_ids}:
            # Una sola persona por cédula: si ya está en otra ficha con sus datos, no se mueve de allí
            logger.info(
                f"[PersonasFaltantesExcel] {enmascarar_documento(id_excel)} ({enmascarar_nombre(nom_excel)}) ya está en otra ficha; no se mueve"
            )
            continue

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
                f"[PersonasFaltantesExcel] Actualizada persona existente {enmascarar_documento(id_excel)} ({enmascarar_nombre(nom_excel)}) como faltante en PDF"
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
                f"[PersonasFaltantesExcel] Creada nueva persona {enmascarar_documento(id_excel)} ({enmascarar_nombre(nom_excel)}) con datos de Excel y alerta 'No se encontró en el PDF'"
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

            # Verificar si el documento fue cancelado o eliminado antes de iniciar OCR
            doc_db = db.query(Documento).filter(Documento.id == doc_id).first()
            if not doc_db or doc_db.estado == "cancelado":
                logger.info(f"[OCR Batch Background] Documento {doc_id} cancelado o removido. Omitiendo OCR.")
                continue

            try:
                logger.info(f"[OCR Batch Background] Procesando PDF: {pdf_path} (Doc ID: {doc_id})")
                ocr_service.procesar_pdf(
                    str(pdf_path),
                    doc_id,
                    db_externa=db,
                    excel_lookup=excel_lookup,
                )
                logger.info(f"[OCR Batch Background] OCR completado para Doc ID: {doc_id}")
                _aplicar_accion_ficha(db, item)
            except Exception as e_ocr:
                logger.error(f"[OCR Batch Background] Error procesando OCR Doc ID {doc_id}: {e_ocr}")

        # ── Verificar si quedan documentos activos del lote antes de continuar ──
        from app.models.comparacion import Comparacion
        docs_activos = db.query(Documento).filter(
            Documento.id.in_([it["documento_id"] for it in items]),
            Documento.estado != "cancelado"
        ).count()
        if docs_activos == 0:
            logger.info("[OCR Batch Background] Todos los documentos del lote fueron cancelados o removidos. Abortando lote.")
            if comparacion_id:
                try:
                    comp_act = db.query(Comparacion).filter(
                        Comparacion.id == comparacion_id,
                        Comparacion.estado == "pendiente"
                    ).first()
                    if comp_act:
                        borrar_archivo_subido(comp_act.ruta_archivo)
                        db.delete(comp_act)
                        db.commit()
                except Exception as e_c:
                    logger.warning(f"[OCR Batch Background] Error limpiando comparacion pendiente: {e_c}")
            return

        # ── Personas de Excel no encontradas en PDF ──
        # Quedan en la ficha como "Falta en PDF" (sin páginas ni PDF asociado), para revisión
        if excel_path:
            try:
                _registrar_personas_excel_faltantes(items=items, excel_path=excel_path, db=db)
            except Exception as e_falt:
                db.rollback()
                logger.error(f"[OCR Batch Background] Error registrando personas de Excel sin PDF: {e_falt}")

        # ── Ejecutar comparación automática si se adjuntó planilla Excel ─
        if comparacion_id and excel_path:
            try:
                from app.services.comparacion_service import comparacion_service
                # Verificar que la comparación no haya sido cancelada
                comp_verif = db.query(Comparacion).filter(
                    Comparacion.id == comparacion_id,
                    Comparacion.estado != "cancelado"
                ).first()
                if comp_verif:
                    logger.info(
                        f"OCR finalizado para todos los {len(items)} documento(s). Iniciando comparación automática: {comparacion_id}"
                    )
                    comparacion_service.ejecutar_comparacion(
                        comparacion_id, excel_path, db
                    )
                    logger.info(f"Comparación automática completada con éxito: {comparacion_id}")
                else:
                    logger.info(f"Comparación {comparacion_id} no encontrada o cancelada. Omitiendo.")
            except Exception as e_cmp:
                logger.error(
                    f"Error en comparación automática {comparacion_id}: {e_cmp}"
                )
    finally:
        db.close()


# ──────────────────────────────────────────
# MODELOS DE CANCELACIÓN Y ESQUEMAS
# ──────────────────────────────────────────
class CancelarSubidaRequest(BaseModel):
    documento_ids: Optional[List[str]] = None
    comparacion_id: Optional[str] = None
    todos_en_proceso: bool = False


# ──────────────────────────────────────────
# ENDPOINTS
# ──────────────────────────────────────────
@router.post(
    "/cancelar",
    summary="Cancelar subida o procesamiento y remover archivos en proceso",
    status_code=200
)
def cancelar_subida_o_procesamiento(
    payload: CancelarSubidaRequest,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_actual),
):
    """
    Cancela de forma inmediata la subida o procesamiento OCR de los documentos seleccionados
    o de todos los documentos en estado 'procesando' o 'pendiente' del usuario.
    Remueve por completo los registros de la base de datos, personas asociadas y archivos en disco.
    """
    from app.models.persona import Persona
    from app.models.comparacion import Comparacion

    # Solo se cancela lo que todavía no terminó: una ficha completada no se borra desde aquí
    estados_cancelables = ["pendiente", "procesando", "error", "cancelado"]
    docs_a_eliminar = []
    if payload.documento_ids:
        ids_validos = []
        for doc_id in payload.documento_ids:
            try:
                ids_validos.append(uuid.UUID(str(doc_id)))
            except ValueError:
                continue
        if ids_validos:
            docs_a_eliminar = db.query(Documento).filter(
                Documento.usuario_id == usuario.id,
                Documento.id.in_(ids_validos),
                Documento.estado.in_(estados_cancelables),
            ).all()

    # Todo lo que está en proceso solo se cancela si se pide de forma explícita
    if payload.todos_en_proceso:
        docs_activos = db.query(Documento).filter(
            Documento.usuario_id == usuario.id,
            Documento.estado.in_(["pendiente", "procesando"])
        ).all()
        existentes_ids = {d.id for d in docs_a_eliminar}
        for d in docs_activos:
            if d.id not in existentes_ids:
                docs_a_eliminar.append(d)

    eliminados_count = 0
    for doc in docs_a_eliminar:
        doc_id = doc.id
        doc_nombre = doc.nombre_original
        ruta = doc.ruta_archivo

        # 1. Intentar marcar estado como cancelado de inmediato por si hilos OCR están verificando
        try:
            doc.estado = "cancelado"
            meta = dict(doc.metadatos or {})
            meta["cancelado"] = True
            meta["paso"] = "Cancelado por el usuario"
            doc.metadatos = meta
            db.flush()
        except Exception as e_flush:
            db.rollback()
            logger.warning(f"[Cancelar] Aviso al marcar cancelado ({e_flush}). Continuando con eliminación directa.")
            doc = db.query(Documento).filter(Documento.id == doc_id).first()
            if not doc:
                continue

        # 2. Eliminar personas asociadas a este documento
        db.query(Persona).filter(
            Persona.documento_id == doc_id,
            Persona.usuario_id == usuario.id
        ).delete(synchronize_session=False)

        # 3. Eliminar archivo físico de disco
        if ruta:
            try:
                borrar_archivo_subido(ruta)
            except Exception as e_f:
                logger.warning(f"No se pudo eliminar archivo físico {ruta}: {e_f}")

        # 4. Eliminar documento de la base de datos
        db.delete(doc)
        eliminados_count += 1
        logger.info(f"[Cancelar] Documento {doc_nombre} (ID: {doc_id}) cancelado y removido permanentemente.")

    # 5. Cancelar y remover comparación asociada si aplica
    if payload.comparacion_id:
        comp = db.query(Comparacion).filter(
            Comparacion.id == payload.comparacion_id,
            Comparacion.usuario_id == usuario.id
        ).first()
        if comp:
            try:
                borrar_archivo_subido(comp.ruta_archivo)
            except Exception:
                pass  # si el archivo no se puede borrar, igual se quita la comparación
            db.delete(comp)
            logger.info(f"[Cancelar] Comparación {payload.comparacion_id} removida.")

    if payload.todos_en_proceso:
        comps_pendientes = db.query(Comparacion).filter(
            Comparacion.usuario_id == usuario.id,
            Comparacion.estado == "pendiente"
        ).all()
        for comp in comps_pendientes:
            try:
                borrar_archivo_subido(comp.ruta_archivo)
            except Exception:
                pass  # si el archivo no se puede borrar, igual se quita la comparación
            db.delete(comp)
            logger.info(f"[Cancelar] Comparación pendiente {comp.id} removida.")

    db.commit()

    return {
        "ok": True,
        "eliminados": eliminados_count,
        "mensaje": f"Se canceló el proceso y se removieron {eliminados_count} documento(s) correctamente."
    }
class FichasExistentesRequest(BaseModel):
    nombres: List[str]


@router.post("/fichas-existentes", summary="Fichas ya subidas con el mismo número que los archivos a subir")
def fichas_existentes(
    datos: FichasExistentesRequest,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_actual),
):
    """Para cada nombre de archivo: su número de ficha y, si ya existe una ficha con ese número, sus datos"""
    if len(datos.nombres) > 100:
        raise HTTPException(status_code=400, detail="Se pueden revisar como máximo 100 archivos a la vez")
    resultado = []
    for nombre in datos.nombres:
        numero = numero_ficha_de(nombre)
        doc = _ficha_existente(db, usuario.id, numero)
        resultado.append({
            "nombre": nombre,
            "numero_ficha": numero,
            "existente": {
                "id": str(doc.id),
                "nombre_original": doc.nombre_original,
                "fecha_carga": doc.fecha_carga.isoformat() if doc.fecha_carga else None,
                "total_personas": doc.total_personas,
            } if doc else None,
        })
    return resultado


def _leer_acciones_ficha(acciones: Optional[str], db: Session, usuario: Usuario) -> dict:
    """{nombre de archivo: (acción, ficha existente)} desde el campo `acciones` (JSON) de la subida"""
    import json
    if not acciones:
        return {}
    try:
        lista = json.loads(acciones)
        assert isinstance(lista, list)
    except Exception:
        raise HTTPException(status_code=400, detail="El campo 'acciones' no es una lista JSON válida")
    resultado = {}
    for a in lista:
        if not isinstance(a, dict) or a.get("accion") not in ACCIONES_FICHA:
            raise HTTPException(status_code=400, detail="Acción de ficha no válida (use 'reemplazar' o 'agregar')")
        try:
            doc_id = uuid.UUID(str(a.get("documento_id")))
        except ValueError:
            raise HTTPException(status_code=400, detail="Ficha existente no válida")
        doc = db.query(Documento).filter(Documento.id == doc_id, Documento.usuario_id == usuario.id).first()
        if not doc or not _es_ficha_principal(doc):
            raise HTTPException(status_code=404, detail="La ficha que se quiere reemplazar o completar no existe")
        resultado[str(a.get("archivo") or "")] = (a["accion"], doc)
    return resultado


@router.post(
    "/upload",
    summary="Subir PDF(s) para procesamiento OCR (planilla Excel opcional)",
    status_code=202
)
def upload_pdf(
    background_tasks: BackgroundTasks,
    files: Optional[List[UploadFile]] = File(default=None, description="Uno o multiples archivos PDF"),
    file: Optional[UploadFile] = File(default=None, description="Archivo PDF individual"),
    excel: Optional[UploadFile] = File(default=None, description="Planilla Excel oficial con nombres (.xlsx/.xls) — Opcional"),
    acciones: Optional[str] = Form(default=None, description="Fichas que ya existen: lista JSON de {archivo, accion (reemplazar|agregar), documento_id}"),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_actual),
):
    """
    Sube uno o multiples PDF junto con la planilla oficial Excel (opcional).
    Si se adjunta el Excel: los nombres y apellidos de cada persona
    se cotejan con la planilla oficial y se ejecuta la comparacion automaticamente.
    Si no se adjunta: los datos se extraen exclusivamente del PDF mediante OCR.
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

    acciones_ficha = _leer_acciones_ficha(acciones, db, usuario)

    # ── Validar todos los archivos antes de guardar nada ──────────────────
    contenidos_pdf: List[bytes] = []
    for pdf_file in archivos_recibidos:
        _validar_pdf(pdf_file)
        contenido_pdf = pdf_file.file.read()
        verificar_tamano_archivo(contenido_pdf, pdf_file.filename)
        contenidos_pdf.append(contenido_pdf)

    excel_content: Optional[bytes] = None
    if excel and excel.filename:
        ext = Path(excel.filename).suffix.lower()
        if ext not in (".xlsx", ".xls"):
            raise HTTPException(
                status_code=400,
                detail=f"El archivo Excel debe tener extensión .xlsx o .xls. Recibido: {ext}"
            )
        excel_content = excel.file.read()
        verificar_tamano_archivo(excel_content, excel.filename)

    # ── Procesar Excel adjunto (si existe) ────────────────────────────────
    comparacion_id: Optional[str] = None
    excel_path_str: Optional[str] = None

    if excel_content is not None:
        nombre_excel = f"comp_{uuid.uuid4()}{ext}"
        ruta_excel = settings.upload_path / nombre_excel
        ruta_excel.write_bytes(excel_content)

        comparacion = Comparacion(
            usuario_id=usuario.id,
            nombre_archivo=nombre_excel,
            nombre_original=excel.filename[:255],
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

    for pdf_file, content in zip(archivos_recibidos, contenidos_pdf):
        # En disco va un nombre saneado (sin carpetas ni caracteres especiales); el original solo se muestra
        nombre_unico = f"{uuid.uuid4()}_{nombre_archivo_seguro(pdf_file.filename, 'ficha.pdf')}"
        ruta_archivo = settings.upload_path / nombre_unico
        ruta_archivo.write_bytes(content)

        accion, ficha_anterior = acciones_ficha.get(pdf_file.filename or "", (None, None))
        documento = Documento(
            usuario_id=usuario.id,
            nombre_archivo=nombre_unico,
            nombre_original=(pdf_file.filename or "ficha.pdf")[:255],
            ruta_archivo=str(ruta_archivo),
            archivo_binario=content,
            tamano_bytes=len(content),
            estado="procesando",
        )
        if accion == "agregar":
            # Una parte no se lista como ficha aparte: sus personas quedan en la ficha existente
            documento.visible_en_subida = False
            documento.metadatos = {"parte_de_ficha_id": str(ficha_anterior.id), "documento_padre_id": str(ficha_anterior.id)}
        db.add(documento)
        db.commit()
        db.refresh(documento)

        items_para_procesar.append({
            "pdf_path": str(ruta_archivo),
            "documento_id": str(documento.id),
            "accion": accion,
            "documento_anterior_id": str(ficha_anterior.id) if ficha_anterior else None,
        })

        logger.info(
            f"PDF guardado y encolado: {pdf_file.filename} (ID: {documento.id})"
        )

        resultados.append({
            "id": str(documento.id),
            # Ficha donde se verán las personas (la existente si el PDF es otra parte de ella)
            "ficha_id": str(ficha_anterior.id) if accion == "agregar" else str(documento.id),
            "accion": accion,
            "nombre_original": documento.nombre_original,
            "estado": "procesando",
            "mensaje": "Archivo recibido. Procesando páginas en segundo plano con Google Document AI.",
        })

    # La planilla queda vinculada a las fichas de este lote: la comparación y el cotejo solo usan estas
    if comparacion_id:
        comparacion.documento_ids = [it["documento_id"] for it in items_para_procesar]
        db.commit()

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
    query = db.query(Documento).filter(Documento.usuario_id == usuario.id)

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
    documento = db.query(Documento).filter(
        Documento.id == documento_id,
        Documento.usuario_id == usuario.id
    ).first()

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
    documento = db.query(Documento).filter(
        Documento.id == documento_id,
        Documento.usuario_id == usuario.id
    ).first()

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
    documento = db.query(Documento).filter(
        Documento.id == documento_id,
        Documento.usuario_id == usuario.id
    ).first()

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
        "mensaje_error": mensaje_error_visible(documento.mensaje_error, ERROR_FICHA),
        "fecha_procesamiento": documento.fecha_procesamiento,
        "metadatos": meta,
    }



@router.delete("/{documento_id}", summary="Eliminar o retirar documento del apartado de subida")
def eliminar_documento(
    documento_id: str,
    permanente: bool = Query(False, description="Si es False (default), solo se retira del apartado de subida preservando el historial y las personas extraídas"),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_actual),
    request: Request = None,
):
    """
    Retira un documento del apartado de subida.
    Preserva el registro histórico en el Dashboard y conserva todas las personas extraídas y sus datos intactos.
    """
    from app.models.persona import Persona

    documento = db.query(Documento).filter(
        Documento.id == documento_id,
        Documento.usuario_id == usuario.id
    ).first()

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
    personas_query = db.query(Persona).filter(
        Persona.documento_id == documento.id,
        Persona.usuario_id == usuario.id
    )
    personas_eliminadas = personas_query.delete(synchronize_session=False)
    if personas_eliminadas:
        logger.info(f"Eliminadas {personas_eliminadas} persona(s) asociadas al documento {documento.nombre_original}")

    # 2. Eliminar archivo físico del PDF y su caché de vistas previas
    try:
        borrar_archivo_subido(documento.ruta_archivo)
    except Exception as e:
        logger.warning(f"No se pudo eliminar archivo físico {documento.ruta_archivo}: {e}")

    try:
        cache_dir = settings.upload_path / "cache_previews"
        if cache_dir.exists():
            for p_file in cache_dir.glob(f"{documento.id}_p*.*"):
                try:
                    p_file.unlink()
                except Exception:
                    pass
    except Exception:
        pass

    # 3. Eliminar el documento de la base de datos
    id_ficha = str(documento.id)
    db.delete(documento)
    db.commit()
    logger.info(f"Documento eliminado permanentemente: {documento.nombre_original} (usuario: {usuario.email})")
    auditoria.registrar("ficha_eliminada", request, usuario=usuario, documento_id=id_ficha, personas=personas_eliminadas)
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

    query_docs = db.query(Documento).filter(Documento.usuario_id == usuario.id)
    query_personas = db.query(Persona).outerjoin(Persona.documento).filter(
        or_(
            Persona.usuario_id == usuario.id,
            Documento.usuario_id == usuario.id,
            Persona.detalles_campos["usuario_id"].astext == str(usuario.id)
        )
    )
    query_comparaciones = db.query(Comparacion).filter(Comparacion.usuario_id == usuario.id)

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


# Resoluciones de la vista previa: 130 y 200 las usa el visor, 150 es la de por defecto
DPI_PERMITIDOS = (130, 150, 200)


@router.get(
    "/{documento_id}/pagina/{numero}",
    summary="Vista previa de página del PDF como imagen optimizada",
    response_class=Response,
)
def preview_pagina_pdf(
    documento_id: str,
    numero: int,
    dpi: int = 150,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_actual),
):
    """
    Renderiza la página `numero` (1-indexed) del PDF asociado al documento
    y la devuelve como imagen JPEG optimizada con caché en disco de alta velocidad.
    Permite al frontend mostrar la vista previa al instante (< 10ms en caché).
    Solo acepta las resoluciones que usa el frontend: cada dpi distinto renderiza y guarda otra imagen.
    La sesión va en la cabecera Authorization (el frontend pide la imagen con fetch): nunca en la dirección,
    que queda en historiales y registros. La imagen es una cédula: el navegador no la guarda en disco.
    """
    if dpi not in DPI_PERMITIDOS:
        raise HTTPException(status_code=400, detail="Resolución no permitida para la vista previa")

    # 1. Validar que el documento pertenece al usuario
    documento = db.query(Documento).filter(
        Documento.id == documento_id,
        Documento.usuario_id == usuario.id
    ).first()

    if not documento:
        raise HTTPException(status_code=404, detail="Documento no encontrado")

    # 2. Verificar caché en disco de alta velocidad
    cache_dir = settings.upload_path / "cache_previews"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"{documento.id}_p{numero}_{dpi}.jpg"
    cabeceras_imagen = {
        "Cache-Control": "private, no-store",
        "Content-Disposition": f'inline; filename="doc_{documento.id}_p{numero}.jpg"',
    }

    if cache_file.exists() and cache_file.stat().st_size > 0:
        return FileResponse(path=str(cache_file), media_type="image/jpeg", headers=cabeceras_imagen)

    # 3. Si no existe en caché, verificar o auto-restaurar archivo PDF
    ruta = documento.obtener_ruta_o_restaurar(db)
    if (not ruta or not ruta.exists()) and not documento.archivo_binario:
        raise HTTPException(
            status_code=404,
            detail=f"Archivo PDF no disponible en el servidor: {documento.nombre_original}"
        )

    # 4. Renderizar con PyMuPDF a JPEG optimizado
    try:
        import pymupdf as fitz  # PyMuPDF
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
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        # JPEG a calidad 85: 90% menos peso que PNG sin pérdida visible de nitidez para texto/cédulas
        jpg_bytes = pix.tobytes("jpeg", jpg_quality=85)
        pdf_doc.close()

        # Guardar en caché de disco de forma atómica para todas las próximas peticiones
        try:
            temp_cache = cache_file.with_suffix(f".tmp_{uuid.uuid4().hex[:6]}")
            temp_cache.write_bytes(jpg_bytes)
            temp_cache.replace(cache_file)
        except Exception as cache_err:
            logger.warning(f"No se pudo guardar preview en caché: {cache_err}")

    except HTTPException:
        raise
    except Exception as e:
        referencia = nueva_referencia()
        logger.opt(exception=e).error(f"{referencia} Error renderizando página {numero} del PDF {documento.id}")
        raise HTTPException(status_code=500, detail=mensaje_error_interno(referencia))

    return Response(
        content=jpg_bytes,
        media_type="image/jpeg",
        headers=cabeceras_imagen,
    )
