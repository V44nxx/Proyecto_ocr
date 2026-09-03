"""
Router de Comparación
Endpoints: Upload Excel, ejecutar comparación, reporte
"""
import uuid
import threading
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.comparacion import Comparacion
from app.models.diferencia import Diferencia
from app.models.usuario import Usuario
from app.schemas.comparacion import ComparacionResponse, DiferenciaResponse, ReporteComparacion
from app.routers.auth import get_usuario_actual
from app.services.comparacion_service import comparacion_service
from app.config import settings
from app.utils.logger import app_logger as logger

router = APIRouter(prefix="/api/comparacion", tags=["Comparación"])


def _ejecutar_comparacion_background(comparacion_id: str, excel_path: str):
    """Ejecuta comparación en hilo de fondo"""
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        comparacion_service.ejecutar_comparacion(comparacion_id, excel_path, db)
    except Exception as e:
        logger.error(f"Error en comparación background: {e}")
    finally:
        db.close()


@router.post("/upload", response_model=ComparacionResponse, status_code=202, summary="Subir Excel para comparar")
async def upload_excel_comparacion(
    file: UploadFile = File(..., description="Archivo Excel (.xlsx o .xls)"),
    ejecutar: bool = True,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_actual),
):
    """
    Sube un archivo Excel externo y opcionalmente inicia la comparación.
    Si ejecutar=True, la comparación corre en segundo plano.
    """
    # Validar extensión
    extension = Path(file.filename).suffix.lower()
    if extension not in settings.ALLOWED_EXCEL_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Solo se aceptan archivos .xlsx o .xls. Recibido: {extension}"
        )

    # Guardar archivo
    nombre_unico = f"comp_{uuid.uuid4()}{extension}"
    ruta_archivo = settings.upload_path / nombre_unico
    content = await file.read()
    ruta_archivo.write_bytes(content)

    # Crear registro de comparación
    comparacion = Comparacion(
        usuario_id=usuario.id,
        nombre_archivo=nombre_unico,
        nombre_original=file.filename,
        ruta_archivo=str(ruta_archivo),
        estado="pendiente" if not ejecutar else "procesando",
    )
    db.add(comparacion)
    db.commit()
    db.refresh(comparacion)

    if ejecutar:
        hilo = threading.Thread(
            target=_ejecutar_comparacion_background,
            args=(str(comparacion.id), str(ruta_archivo)),
            daemon=True
        )
        hilo.start()
        logger.info(f"Comparación iniciada en background: {comparacion.id}")

    return ComparacionResponse.model_validate(comparacion)


@router.post("/{comparacion_id}/ejecutar", summary="Ejecutar comparación")
def ejecutar_comparacion(
    comparacion_id: str,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_actual),
):
    """Ejecuta manualmente una comparación pendiente"""
    comparacion = db.query(Comparacion).filter(Comparacion.id == comparacion_id).first()
    if not comparacion:
        raise HTTPException(status_code=404, detail="Comparación no encontrada")

    if comparacion.estado == "procesando":
        raise HTTPException(status_code=409, detail="La comparación ya está en proceso")

    comparacion.estado = "procesando"
    db.commit()

    hilo = threading.Thread(
        target=_ejecutar_comparacion_background,
        args=(str(comparacion.id), comparacion.ruta_archivo),
        daemon=True
    )
    hilo.start()

    return {"mensaje": "Comparación iniciada", "id": comparacion_id}


@router.get("", response_model=List[ComparacionResponse], summary="Listar comparaciones")
def listar_comparaciones(
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_actual),
):
    """Lista el historial de comparaciones del usuario"""
    comparaciones = (
        db.query(Comparacion)
        .filter(Comparacion.usuario_id == usuario.id)
        .order_by(Comparacion.fecha_carga.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [ComparacionResponse.model_validate(c) for c in comparaciones]


@router.get("/{comparacion_id}", response_model=ComparacionResponse, summary="Detalle comparación")
def obtener_comparacion(
    comparacion_id: str,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_actual),
):
    """Obtiene el detalle y estadísticas de una comparación"""
    comparacion = db.query(Comparacion).filter(Comparacion.id == comparacion_id).first()
    if not comparacion:
        raise HTTPException(status_code=404, detail="Comparación no encontrada")

    res = ComparacionResponse.model_validate(comparacion)
    try:
        p_check = Path(comparacion.ruta_archivo) if comparacion.ruta_archivo else None
        res.archivo_existe = (p_check.exists() if p_check else False)
        up_dir = settings.upload_path
        res.archivos_en_uploads = [f.name for f in up_dir.glob("comp_*")] if up_dir.exists() else []
        if res.archivo_existe and p_check:
            try:
                df_test = comparacion_service.cargar_excel(str(p_check))
                res.error_carga_excel = f"OK: {len(df_test)} filas"
            except Exception as e_test:
                res.error_carga_excel = f"Error al cargar: {e_test}"
        else:
            res.error_carga_excel = f"Archivo no encontrado en {p_check}"
    except Exception as e_diag:
        res.error_carga_excel = f"Diag error: {e_diag}"

    return res


@router.get("/{comparacion_id}/diferencias", response_model=List[DiferenciaResponse], summary="Diferencias encontradas")
def obtener_diferencias(
    comparacion_id: str,
    tipo: str = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_actual),
):
    """Lista las diferencias encontradas en una comparación"""
    query = db.query(Diferencia).filter(Diferencia.comparacion_id == comparacion_id)

    if tipo:
        query = query.filter(Diferencia.tipo_diferencia == tipo)

    diferencias = query.offset(skip).limit(limit).all()
    return [DiferenciaResponse.model_validate(d) for d in diferencias]


@router.get("/{comparacion_id}/reporte", summary="Descargar reporte Excel")
def descargar_reporte(
    comparacion_id: str,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_actual),
):
    """Genera y descarga el reporte detallado de diferencias en XLSX"""
    comparacion = db.query(Comparacion).filter(Comparacion.id == comparacion_id).first()
    if not comparacion:
        raise HTTPException(status_code=404, detail="Comparación no encontrada")

    if comparacion.estado != "completado":
        raise HTTPException(
            status_code=409,
            detail=f"La comparación aún no está completada. Estado: {comparacion.estado}"
        )

    ruta_reporte = comparacion_service.generar_reporte_xlsx(comparacion_id, db)

    return FileResponse(
        path=ruta_reporte,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=Path(ruta_reporte).name,
        headers={"Content-Disposition": f"attachment; filename={Path(ruta_reporte).name}"}
    )


from pydantic import BaseModel
from datetime import datetime
from app.utils.validators import validador


class CorregirCampoRequest(BaseModel):
    numero_identificacion: str
    campo: str
    nuevo_valor: str


@router.post("/{comparacion_id}/corregir-campo", summary="Corregir campo en BD desde la comparación")
def corregir_campo_desde_comparacion(
    comparacion_id: str,
    datos: CorregirCampoRequest,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_actual),
):
    """
    Aplica una corrección directa a una persona en la BD desde la vista de comparación.
    Actualiza la persona, marca la diferencia como resuelta y actualiza los contadores.
    """
    from app.models.persona import Persona
    from app.models.diferencia import Diferencia

    num_id = datos.numero_identificacion.strip()
    persona = db.query(Persona).filter(Persona.numero_identificacion == num_id).first()
    if not persona:
        raise HTTPException(status_code=404, detail=f"Persona con identificación {num_id} no encontrada en la BD")

    campo = datos.campo.strip().lower()
    campos_validos = ["nombres", "apellidos", "fecha_nacimiento", "fecha_expedicion", "lugar_expedicion", "sexo"]
    if campo not in campos_validos:
        raise HTTPException(status_code=400, detail=f"Campo '{campo}' no es válido para actualización")

    valor_a_guardar = datos.nuevo_valor.strip()
    if campo in ["fecha_nacimiento", "fecha_expedicion"]:
        if valor_a_guardar:
            fecha_dt = validador.parsear_fecha(valor_a_guardar)
            setattr(persona, campo, fecha_dt.date() if fecha_dt else None)
        else:
            setattr(persona, campo, None)
    else:
        setattr(persona, campo, valor_a_guardar if valor_a_guardar else None)

    # Marcar campo en campos_revisados
    revisados = list(persona.campos_revisados or [])
    if campo not in revisados:
        revisados.append(campo)
    persona.campos_revisados = revisados
    persona.fecha_actualizacion = datetime.utcnow()

    # Actualizar la diferencia en la comparación
    diferencia = db.query(Diferencia).filter(
        Diferencia.comparacion_id == comparacion_id,
        Diferencia.numero_identificacion == num_id,
        Diferencia.campo == campo
    ).first()

    if diferencia:
        diferencia.valor_bd = str(getattr(persona, campo) or "")
        diferencia.tipo_diferencia = "igual"

    # Recalcular métricas de la comparación
    comparacion = db.query(Comparacion).filter(Comparacion.id == comparacion_id).first()
    if comparacion:
        ids_con_dif = db.query(Diferencia.numero_identificacion).filter(
            Diferencia.comparacion_id == comparacion_id,
            Diferencia.tipo_diferencia == "diferente"
        ).distinct().count()
        comparacion.total_diferentes = ids_con_dif
        comparacion.total_coincidentes = max(0, (comparacion.total_registros_excel or 0) - (comparacion.total_faltantes_bd or 0) - ids_con_dif)

    db.commit()
    db.refresh(persona)

    return {
        "mensaje": f"Campo '{campo}' actualizado exitosamente a '{valor_a_guardar}'",
        "persona_id": str(persona.id),
        "numero_identificacion": persona.numero_identificacion,
        "campo": campo,
        "nuevo_valor": str(getattr(persona, campo) or ""),
    }

