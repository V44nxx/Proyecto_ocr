"""
Router de Personas
Endpoints: Listar, detalle, actualizar (corrección manual), eliminar
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.persona import Persona
from app.models.usuario import Usuario
from app.schemas.documento import PersonaResponse, PersonaUpdate
from app.routers.auth import get_usuario_actual
from app.utils.logger import app_logger as logger

router = APIRouter(prefix="/api/personas", tags=["Personas"])


@router.get("", response_model=List[PersonaResponse], summary="Listar personas")
def listar_personas(
    skip: int = 0,
    limit: int = 100,
    requiere_revision: Optional[bool] = Query(None),
    buscar: Optional[str] = Query(None, description="Buscar por nombre, apellido o cédula"),
    documento_id: Optional[str] = Query(None, description="Filtrar por ID de documento PDF"),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_actual),
):
    """Lista todas las personas registradas con filtros opcionales"""
    query = db.query(Persona).options(joinedload(Persona.documento))

    if documento_id:
        query = query.filter(Persona.documento_id == documento_id)

    if requiere_revision is True:
        query = query.filter(
            (Persona.requiere_revision == True) |
            (Persona.estado_registro.in_(["REVIEW_REQUIRED", "FALLBACK_TESSERACT"])) |
            (Persona.estado_registro != "VALID")
        )
    elif requiere_revision is False:
        query = query.filter(
            (Persona.requiere_revision == False) &
            ((Persona.estado_registro == "VALID") | (Persona.estado_registro.is_(None)))
        )

    if buscar:
        buscar_upper = f"%{buscar.upper()}%"
        query = query.filter(
            Persona.numero_identificacion.ilike(f"%{buscar}%") |
            Persona.nombre_completo.ilike(buscar_upper) |
            Persona.nombres.ilike(buscar_upper) |
            Persona.apellidos.ilike(buscar_upper)
        )

    personas = query.order_by(Persona.fecha_registro.desc()).offset(skip).limit(limit).all()
    return [PersonaResponse.model_validate(p) for p in personas]


@router.get("/{persona_id}", response_model=PersonaResponse, summary="Detalle de persona")
def obtener_persona(
    persona_id: str,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_actual),
):
    """Obtiene el detalle completo de una persona"""
    persona = db.query(Persona).options(joinedload(Persona.documento)).filter(Persona.id == persona_id).first()
    if not persona:
        raise HTTPException(status_code=404, detail="Persona no encontrada")
    return PersonaResponse.model_validate(persona)


@router.put("/{persona_id}", response_model=PersonaResponse, summary="Corregir datos de persona")
def actualizar_persona(
    persona_id: str,
    datos: PersonaUpdate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_actual),
):
    """
    Permite corrección manual de datos extraídos por OCR.
    Registra qué campos fueron revisados manualmente.
    """
    persona = db.query(Persona).filter(Persona.id == persona_id).first()
    if not persona:
        raise HTTPException(status_code=404, detail="Persona no encontrada")

    campos_revisados = list(persona.campos_revisados or [])
    campos_actualizados = []

    # Actualizar solo los campos enviados
    if datos.numero_identificacion is not None:
        persona.numero_identificacion = str(datos.numero_identificacion).strip()
        if "numero_identificacion" not in campos_revisados:
            campos_revisados.append("numero_identificacion")
        campos_actualizados.append("numero_identificacion")

    if datos.tipo_documento is not None:
        persona.tipo_documento = str(datos.tipo_documento).strip()
        campos_actualizados.append("tipo_documento")

    if datos.nombre_completo is not None:
        persona.nombre_completo = datos.nombre_completo.upper()
        if "nombre_completo" not in campos_revisados:
            campos_revisados.append("nombre_completo")
        campos_actualizados.append("nombre_completo")

    if datos.nombres is not None:
        persona.nombres = datos.nombres.upper()
        if "nombres" not in campos_revisados:
            campos_revisados.append("nombres")
        campos_actualizados.append("nombres")

    if datos.apellidos is not None:
        persona.apellidos = datos.apellidos.upper()
        if "apellidos" not in campos_revisados:
            campos_revisados.append("apellidos")
        campos_actualizados.append("apellidos")

    if datos.fecha_nacimiento is not None:
        persona.fecha_nacimiento = datos.fecha_nacimiento
        campos_actualizados.append("fecha_nacimiento")

    if datos.fecha_expedicion is not None:
        persona.fecha_expedicion = datos.fecha_expedicion
        campos_actualizados.append("fecha_expedicion")

    if datos.lugar_expedicion is not None:
        persona.lugar_expedicion = datos.lugar_expedicion.upper()
        campos_actualizados.append("lugar_expedicion")

    if datos.sexo is not None:
        persona.sexo = datos.sexo.upper()
        campos_actualizados.append("sexo")

    from app.utils.validators import validador
    from datetime import datetime

    if datos.requiere_revision is not None:
        persona.requiere_revision = datos.requiere_revision
        det = dict(persona.detalles_campos or {})
        if not datos.requiere_revision:
            persona.estado_registro = "VALID"
            det.pop("motivos_revision", None)
        else:
            persona.estado_registro = "REVIEW_REQUIRED"
        persona.detalles_campos = det
    else:
        # Reevaluar si con los datos guardados ya no requiere revisión
        tiene_datos, motivos_rev = validador.evaluar_persona_completa(
            numero_identificacion=persona.numero_identificacion,
            nombres=persona.nombres,
            apellidos=persona.apellidos,
            nombre_completo=persona.nombre_completo,
            fecha_nacimiento=persona.fecha_nacimiento,
            fecha_expedicion=persona.fecha_expedicion,
            lugar_expedicion=persona.lugar_expedicion,
            sexo=persona.sexo,
            confianza=float(persona.confianza_extraccion or 0),
            detalles_campos=persona.detalles_campos,
            motor_ocr=persona.motor_ocr,
        )
        det = dict(persona.detalles_campos or {})
        if tiene_datos:
            persona.requiere_revision = False
            persona.estado_registro = "VALID"
            det.pop("motivos_revision", None)
        else:
            persona.requiere_revision = True
            persona.estado_registro = "REVIEW_REQUIRED"
            det["motivos_revision"] = motivos_rev
        persona.detalles_campos = det

    persona.campos_revisados = campos_revisados
    persona.fecha_actualizacion = datetime.utcnow()
    db.commit()
    db.refresh(persona)

    logger.info(f"Persona {persona.numero_identificacion} actualizada. Campos: {campos_actualizados}")
    return PersonaResponse.model_validate(persona)


@router.delete("/{persona_id}", status_code=204, summary="Eliminar persona")
def eliminar_persona(
    persona_id: str,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_actual),
):
    """Elimina un registro de persona"""
    persona = db.query(Persona).filter(Persona.id == persona_id).first()
    if not persona:
        raise HTTPException(status_code=404, detail="Persona no encontrada")

    db.delete(persona)
    db.commit()
    logger.info(f"Persona eliminada: {persona.numero_identificacion}")


@router.get("/buscar/cedula/{cedula}", response_model=PersonaResponse, summary="Buscar por cédula")
def buscar_por_cedula(
    cedula: str,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_actual),
):
    """Busca una persona por número de identificación exacto"""
    persona = db.query(Persona).options(joinedload(Persona.documento)).filter(
        Persona.numero_identificacion == cedula.strip()
    ).first()

    if not persona:
        raise HTTPException(status_code=404, detail=f"No se encontró persona con cédula {cedula}")

    return PersonaResponse.model_validate(persona)


@router.post("/{persona_id}/subir-pdf", response_model=PersonaResponse, summary="Subir PDF de la cédula para una persona")
async def subir_pdf_persona(
    persona_id: str,
    file: UploadFile = File(..., description="Archivo PDF de la cédula de ciudadanía"),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_actual),
):
    """
    Recibe un archivo PDF de la cédula para una persona específica.
    Ejecuta el proceso de OCR, unifica y completa los datos de la persona
    (fechas, lugar de expedición, sexo, nombres/apellidos, fotos/páginas de la cédula)
    y reevalúa el estado de revisión.
    """
    import uuid
    from datetime import datetime
    from pathlib import Path
    from app.config import settings
    from app.models.documento import Documento
    from app.services.ocr_service import ocr_service
    from app.utils.validators import validador

    persona = db.query(Persona).options(joinedload(Persona.documento)).filter(Persona.id == persona_id).first()
    if not persona:
        raise HTTPException(status_code=404, detail="Persona no encontrada")

    extension = Path(file.filename).suffix.lower()
    if extension != ".pdf":
        raise HTTPException(
            status_code=400,
            detail=f"Solo se aceptan archivos PDF. Recibido: {extension}"
        )

    # Guardar archivo PDF en la carpeta de subidas
    nombre_guardado = f"cedula_{persona.numero_identificacion}_{uuid.uuid4().hex[:8]}.pdf"
    ruta_guardada = settings.upload_path / nombre_guardado
    content = await file.read()
    ruta_guardada.write_bytes(content)

    # Crear registro de documento
    doc = Documento(
        usuario_id=usuario.id,
        nombre_archivo=nombre_guardado,
        nombre_original=file.filename,
        ruta_archivo=str(ruta_guardada),
        estado="procesando",
        tamano_bytes=len(content),
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    try:
        # Ejecutar OCR usando la misma sesión de BD
        ocr_service.procesar_pdf(str(ruta_guardada), str(doc.id), db_externa=db)

        # Si el OCR creó un nuevo registro de persona porque detectó otro ID o SIN_ID,
        # unificar sus datos en nuestra persona objetivo y eliminar el registro temporal
        otras_personas = (
            db.query(Persona)
            .filter(Persona.documento_id == str(doc.id), Persona.id != persona.id)
            .all()
        )
        for otra in otras_personas:
            if otra.fecha_nacimiento and not persona.fecha_nacimiento:
                persona.fecha_nacimiento = otra.fecha_nacimiento
            if otra.fecha_expedicion and not persona.fecha_expedicion:
                persona.fecha_expedicion = otra.fecha_expedicion
            if otra.lugar_expedicion and (not persona.lugar_expedicion or persona.lugar_expedicion in ["COLOMBIA", "REPUBLICA DE COLOMBIA"]):
                persona.lugar_expedicion = otra.lugar_expedicion
            if otra.sexo and not persona.sexo:
                persona.sexo = otra.sexo
            if otra.pagina_frente and not persona.pagina_frente:
                persona.pagina_frente = otra.pagina_frente
            if otra.pagina_reverso and not persona.pagina_reverso:
                persona.pagina_reverso = otra.pagina_reverso
            if otra.nombres and (not persona.nombres or persona.nombres == "POR REVISAR"):
                persona.nombres = otra.nombres
            if otra.apellidos and (not persona.apellidos or persona.apellidos == "POR REVISAR"):
                persona.apellidos = otra.apellidos
            if otra.nombre_completo and (not persona.nombre_completo or persona.nombre_completo == "POR REVISAR"):
                persona.nombre_completo = otra.nombre_completo
            if (otra.confianza_extraccion or 0) > (persona.confianza_extraccion or 0):
                persona.confianza_extraccion = otra.confianza_extraccion
                persona.motor_ocr = otra.motor_ocr

            # Unificar detalles
            det_existente = dict(persona.detalles_campos or {})
            det_otro = dict(otra.detalles_campos or {})
            for k, v in det_otro.items():
                if k not in det_existente or not det_existente[k].get("valor"):
                    det_existente[k] = v
            persona.detalles_campos = det_existente

            # Eliminar la persona duplicada que creó el OCR
            db.delete(otra)

        # Asociar explícitamente el documento a la persona
        persona.documento_id = str(doc.id)

        # Reevaluar completitud
        det = dict(persona.detalles_campos or {})
        # Quitar motivo de "Registro creado desde Excel (pendiente de cargar documento PDF)"
        motivos_anteriores = det.get("motivos_revision") or []
        if isinstance(motivos_anteriores, list):
            motivos_anteriores = [m for m in motivos_anteriores if "pendiente de cargar documento" not in m]
            det["motivos_revision"] = motivos_anteriores

        tiene_datos, motivos_rev = validador.evaluar_persona_completa(
            numero_identificacion=persona.numero_identificacion,
            nombres=persona.nombres,
            apellidos=persona.apellidos,
            nombre_completo=persona.nombre_completo,
            fecha_nacimiento=persona.fecha_nacimiento,
            fecha_expedicion=persona.fecha_expedicion,
            lugar_expedicion=persona.lugar_expedicion,
            sexo=persona.sexo,
            confianza=float(persona.confianza_extraccion or 0),
            detalles_campos=det,
            motor_ocr=persona.motor_ocr,
        )

        if tiene_datos:
            persona.requiere_revision = False
            persona.estado_registro = "VALID"
            det.pop("motivos_revision", None)
        else:
            persona.requiere_revision = True
            persona.estado_registro = "REVIEW_REQUIRED"
            det["motivos_revision"] = motivos_rev
        persona.detalles_campos = det
        persona.fecha_actualizacion = datetime.utcnow()

        doc.estado = "completado"
        db.commit()
        db.refresh(persona)
        logger.info(f"PDF procesado para persona {persona.numero_identificacion} (ID: {persona.id}). Estado: {persona.estado_registro}")
        return PersonaResponse.model_validate(persona)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error procesando PDF para persona {persona.id}: {e}")
        doc.estado = "error"
        doc.mensaje_error = str(e)
        db.commit()
        raise HTTPException(
            status_code=500,
            detail=f"Error al procesar el archivo PDF con OCR: {str(e)}"
        )

