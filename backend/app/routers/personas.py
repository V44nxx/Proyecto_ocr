"""
Router de Personas
Endpoints: Listar, detalle, actualizar (corrección manual), eliminar
"""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.persona import Persona
from app.models.documento import Documento
from app.models.usuario import Usuario
from app.schemas.documento import PersonaResponse, PersonaUpdate
from app.routers.auth import get_usuario_actual
from app.utils.logger import app_logger as logger

router = APIRouter(prefix="/api/personas", tags=["Personas"])


def _filtrar_persona_por_usuario(query, usuario: Usuario):
    """Filtra la consulta de personas para que cada usuario solo vea sus propios registros estrictamente"""
    from app.models.documento import Documento
    from sqlalchemy import or_
    return query.outerjoin(Persona.documento).filter(
        or_(
            Persona.usuario_id == usuario.id,
            Documento.usuario_id == usuario.id,
            Persona.detalles_campos["usuario_id"].astext == str(usuario.id)
        )
    )



import os
import re
from typing import Dict, Tuple, Set

_CACHE_IDS_EXCEL: Dict[str, Tuple[float, Set[str]]] = {}


def _extraer_ids_de_archivo_excel(ruta_archivo: str) -> Set[str]:
    """Extrae con precisión matemática el conjunto de cédulas/identificaciones de un archivo Excel físico"""
    if not ruta_archivo or not os.path.exists(ruta_archivo):
        return set()

    try:
        mtime = os.path.getmtime(ruta_archivo)
        if ruta_archivo in _CACHE_IDS_EXCEL:
            cached_mtime, cached_ids = _CACHE_IDS_EXCEL[ruta_archivo]
            if cached_mtime == mtime:
                return cached_ids

        ids_encontrados: Set[str] = set()

        # 1. Intentar con comparacion_service.cargar_excel (soporta multi-hoja, encabezados con offset y limpieza id)
        try:
            from app.services.comparacion_service import comparacion_service
            df = comparacion_service.cargar_excel(ruta_archivo)
            if df is not None and "numero_identificacion" in df.columns:
                for val in df["numero_identificacion"].dropna():
                    s = str(val).strip()
                    limpio = re.sub(r"[^\d]", "", s)
                    if limpio and len(limpio) >= 5:
                        ids_encontrados.add(limpio)
                    if s and len(s) >= 5:
                        ids_encontrados.add(s)
        except Exception as e_comp:
            logger.warning(f"Fallback a excel_lookup_service para {ruta_archivo}: {e_comp}")

        # 2. Si quedó vacío, intentar con excel_lookup_service
        if not ids_encontrados:
            try:
                from app.services.excel_lookup_service import excel_lookup_service
                lookup = excel_lookup_service.cargar_lookup(ruta_archivo)
                for k in lookup.keys():
                    s = str(k).strip()
                    limpio = re.sub(r"[^\d]", "", s)
                    if limpio and len(limpio) >= 5:
                        ids_encontrados.add(limpio)
                    if s and len(s) >= 5:
                        ids_encontrados.add(s)
            except Exception as e_look:
                logger.warning(f"Error en excel_lookup_service para {ruta_archivo}: {e_look}")

        _CACHE_IDS_EXCEL[ruta_archivo] = (mtime, ids_encontrados)
        logger.info(f"[ExcelIDs] Archivo '{os.path.basename(ruta_archivo)}': {len(ids_encontrados)} identificaciones cargadas")
        return ids_encontrados
    except Exception as e:
        logger.error(f"Error extrayendo IDs de Excel '{ruta_archivo}': {e}")
        return set()


def _obtener_ids_en_excel(db: Session, usuario_id) -> tuple[Set[str], bool]:
    """
    Obtiene el conjunto de números de identificación presentes en las planillas Excel
    de comparación del usuario con máxima confiabilidad leyendo directamente los archivos.
    """
    try:
        from app.models.comparacion import Comparacion
        from app.models.diferencia import Diferencia

        # 1. Buscar comparaciones del usuario
        comp_query = (
            db.query(Comparacion)
            .filter(Comparacion.usuario_id == usuario_id)
            .order_by(Comparacion.fecha_carga.desc())
        )
        comparaciones = comp_query.all()
        if not comparaciones:
            return set(), False

        ids_totales: Set[str] = set()
        hay_archivo = False

        # 2. Extraer los IDs directamente de los archivos Excel físicos o restaurados
        for comp in comparaciones:
            ruta = comp.obtener_ruta_o_restaurar(db)
            if ruta and ruta.exists():
                ids_archivo = _extraer_ids_de_archivo_excel(str(ruta))
                if ids_archivo:
                    ids_totales.update(ids_archivo)
                    hay_archivo = True

        if hay_archivo:
            return ids_totales, True

        # 3. Fallback si el archivo físico y el binario no existieran (ej. subidas históricas previas a persistencia):
        # A. En la tabla Diferencia, los registros en Excel son 'faltante_bd' y 'diferente'.
        comp_ids = [c.id for c in comparaciones]
        rows = (
            db.query(Diferencia.numero_identificacion)
            .filter(
                Diferencia.comparacion_id.in_(comp_ids),
                Diferencia.tipo_diferencia.in_(["faltante_bd", "diferente", "igual"])
            )
            .distinct()
            .all()
        )
        fallback_ids = set()
        for r in rows:
            if r[0]:
                s = str(r[0]).strip()
                limpio = re.sub(r"[^\d]", "", s)
                if limpio:
                    fallback_ids.add(limpio)
                fallback_ids.add(s)

        # B. Identificar quiénes NO estaban en Excel según la comparación (tipo_diferencia = 'nuevo_bd')
        rows_sobrantes = (
            db.query(Diferencia.numero_identificacion)
            .filter(
                Diferencia.comparacion_id.in_(comp_ids),
                Diferencia.tipo_diferencia == "nuevo_bd"
            )
            .distinct()
            .all()
        )
        ids_sobrantes = set()
        for r in rows_sobrantes:
            if r[0]:
                s = str(r[0]).strip()
                ids_sobrantes.add(s)
                limp = re.sub(r"[^\d]", "", s)
                if limp:
                    ids_sobrantes.add(limp)

        # C. Reconstruir a partir de personas del usuario: los que NO están en ids_sobrantes (estaban en Excel coincidentes)
        # o que tienen evidencia directa de Excel
        from app.models.persona import Persona
        p_query = db.query(Persona)
        if usuario_id:
            p_query = p_query.filter(Persona.usuario_id == usuario_id)
        personas_bd = p_query.all()

        for p in personas_bd:
            num = str(p.numero_identificacion or "").strip()
            num_limp = re.sub(r"[^\d]", "", num)
            det = p.detalles_campos or {}
            es_excel = (
                p.motor_ocr == "excel"
                or bool(det.get("discrepancia_excel"))
                or det.get("origen") == "excel_no_encontrado_en_pdf"
                or (isinstance(det.get("nombre_completo"), dict) and det["nombre_completo"].get("source") == "excel_oficial")
                or (isinstance(det.get("numero_identificacion"), dict) and det["numero_identificacion"].get("source") == "excel_oficial")
                or (num and num not in ids_sobrantes and num_limp not in ids_sobrantes)
            )
            if es_excel:
                if num:
                    fallback_ids.add(num)
                if num_limp:
                    fallback_ids.add(num_limp)

        return fallback_ids, bool(comparaciones)

    except Exception as e:
        logger.error(f"Error determinando presencia en Excel: {e}")
        return set(), False


def _enriquecer_persona_response(p: Persona, ids_en_excel: Set[str], hay_excel: bool) -> PersonaResponse:
    """
    Enriquece PersonaResponse con flags 100% precisos de presencia en PDF y en Excel,
    y asegura que si hay discrepancia registrada con la planilla oficial de Excel o
    inconsistencia legal de documento vs edad, se refleje fielmente.
    """
    from app.utils.validators import validador

    r = PersonaResponse.model_validate(p)
    if r.numero_identificacion and r.numero_identificacion.startswith("SIN_ID"):
        r.numero_identificacion = ""

    detalles = dict(p.detalles_campos or {})

    # Asignar documento PDF individual si existe
    r.documento_pdf_id = getattr(p, "documento_pdf_id", None) or detalles.get("documento_pdf_id")
    if getattr(p, "documento_pdf", None):
        r.nombre_documento_pdf = p.documento_pdf.nombre_original
    elif detalles.get("nombre_documento_pdf"):
        r.nombre_documento_pdf = detalles.get("nombre_documento_pdf")

    # Evaluar presencia real en el documento PDF
    if detalles.get("en_pdf") is True or r.documento_pdf_id is not None:
        r.en_pdf = True
    elif detalles.get("en_pdf") is False or p.motor_ocr == "excel":
        r.en_pdf = False
        r.requiere_revision = True
        if not r.estado_registro or r.estado_registro == "VALID":
            r.estado_registro = "REVIEW_REQUIRED"
    else:
        r.en_pdf = p.documento_id is not None

    disc_excel = detalles.get("discrepancia_excel")
    if isinstance(disc_excel, dict) and disc_excel.get("nombre_excel"):
        nom_ex_ofic = disc_excel["nombre_excel"].strip()
        if nom_ex_ofic:
            r.nombre_completo = nom_ex_ofic

    # Evaluación de mayoría de edad vs tipo de documento
    edad_val = p.edad or validador.calcular_edad(p.fecha_nacimiento)
    tipo_norm = str(p.tipo_documento or "").upper().strip()

    # Si en el texto OCR crudo se evidencia que es Tarjeta de Identidad, rectificar la clasificación
    texto_ocr = str(p.texto_ocr_crudo or "").upper()
    es_tarjeta_en_texto = bool(
        re.search(
            r"\bTARJETA\s+(?:DE\s+)?(?:IDENTIDAD|IDENTIF[A-Z]*|IDENTID[A-Z0-9]*|DENTIDAD)\b|"
            r"\bTARJETADEIDENTIDAD\b|\bTARJETADE\s*IDENTIDAD\b|\bTARJETA\s*DEIDENTIDAD\b|"
            r"\bTARJETA\b|\bT\.?\s*I\.?\b",
            texto_ocr
        )
        or (
            re.search(r"\bFECHA\s+DE\s+VENCIMIENTO\b", texto_ocr)
            and re.search(r"\bLUGAR\s+DE\s+NACIMIENTO\b", texto_ocr)
            and not re.search(r"I<COL|C<COL", texto_ocr)
        )
    )
    if es_tarjeta_en_texto and not re.search(r"\bCEDULA\s+DE\s+CIUDADAN[IÍ]A\b", texto_ocr):
        tipo_norm = "TARJETA_IDENTIDAD"
        r.tipo_documento = "TARJETA_IDENTIDAD"
        if p.tipo_documento != "TARJETA_IDENTIDAD":
            p.tipo_documento = "TARJETA_IDENTIDAD"

    es_ti = "TARJETA" in tipo_norm or tipo_norm in ("TARJETA_IDENTIDAD", "TI", "TARJETA DE IDENTIDAD", "TARJETA IDENTIDAD")
    es_cc = (("CEDULA" in tipo_norm or "CÉDULA" in tipo_norm or tipo_norm in ("CEDULA_CIUDADANIA", "CC", "CEDULA DE CIUDADANIA")) and not es_ti)

    if edad_val is not None:
        if edad_val >= 18 and es_ti:
            disc_doc_edad = {
                "tipo": "MAYOR_CON_TI",
                "edad": edad_val,
                "tipo_documento": p.tipo_documento or "TARJETA_IDENTIDAD",
                "motivo": (
                    f"Archivo no válido ya que la persona es mayor de edad ({edad_val} años) "
                    f"y presenta archivo de Tarjeta de Identidad que solo corresponde a menores de edad."
                )
            }
            detalles["discrepancia_documento_edad"] = disc_doc_edad
            r.requiere_revision = True
            if not r.estado_registro or r.estado_registro == "VALID":
                r.estado_registro = "REVIEW_REQUIRED"
            mots = list(detalles.get("motivos_revision") or [])
            if disc_doc_edad["motivo"] not in mots:
                mots.append(disc_doc_edad["motivo"])
                detalles["motivos_revision"] = mots
            r.detalles_campos = detalles
        elif edad_val < 18 and es_cc:
            disc_doc_edad = {
                "tipo": "MENOR_CON_CC",
                "edad": edad_val,
                "tipo_documento": p.tipo_documento or "CEDULA_CIUDADANIA",
                "motivo": (
                    f"Archivo no válido ya que la persona es menor de edad ({edad_val} años) "
                    f"y presenta archivo de Cédula de Ciudadanía que solo corresponde a mayores de 18 años."
                )
            }
            detalles["discrepancia_documento_edad"] = disc_doc_edad
            r.requiere_revision = True
            if not r.estado_registro or r.estado_registro == "VALID":
                r.estado_registro = "REVIEW_REQUIRED"
            mots = list(detalles.get("motivos_revision") or [])
            if disc_doc_edad["motivo"] not in mots:
                mots.append(disc_doc_edad["motivo"])
                detalles["motivos_revision"] = mots
            r.detalles_campos = detalles

    # Comprobar si la persona tiene evidencia inequívoca de pertenecer a la planilla oficial de Excel
    evidencia_excel = (
        p.motor_ocr == "excel"
        or bool(disc_excel)
        or detalles.get("origen") == "excel_no_encontrado_en_pdf"
        or (isinstance(detalles.get("nombre_completo"), dict) and detalles["nombre_completo"].get("source") == "excel_oficial")
        or (isinstance(detalles.get("numero_identificacion"), dict) and detalles["numero_identificacion"].get("source") == "excel_oficial")
        or (isinstance(detalles.get("nombres"), dict) and detalles["nombres"].get("source") == "excel_oficial")
    )

    if evidencia_excel:
        r.en_excel = True
    elif hay_excel:
        id_crudo = str(p.numero_identificacion or "").strip()
        id_limpio = re.sub(r"[^\d]", "", id_crudo)

        esta_en_excel = bool(
            (id_limpio and id_limpio in ids_en_excel) or
            (id_crudo and id_crudo in ids_en_excel)
        )
        r.en_excel = esta_en_excel
    else:
        # No se ha subido ninguna planilla Excel para contrastar
        r.en_excel = None

    return r


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
    """Lista las personas registradas asociadas al usuario (o todas si es admin)"""
    query = db.query(Persona).options(joinedload(Persona.documento))
    query = _filtrar_persona_por_usuario(query, usuario)

    if documento_id and isinstance(documento_id, str):
        query = query.filter(
            (Persona.documento_id == documento_id) |
            (Persona.documento_pdf_id == documento_id)
        )

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

    if buscar and isinstance(buscar, str):
        buscar_upper = f"%{buscar.upper()}%"
        query = query.filter(
            Persona.numero_identificacion.ilike(f"%{buscar}%") |
            Persona.nombre_completo.ilike(buscar_upper) |
            Persona.nombres.ilike(buscar_upper) |
            Persona.apellidos.ilike(buscar_upper)
        )

    personas = query.order_by(Persona.fecha_registro.desc()).offset(skip).limit(limit).all()

    ids_en_excel, hay_excel = _obtener_ids_en_excel(db, usuario.id)

    # Auto-corrección oportuna si alguna persona de BD no coincide con Excel por ID pero sí por nombre
    if hay_excel and ids_en_excel and personas:
        try:
            from app.models.comparacion import Comparacion
            from app.services.excel_lookup_service import excel_lookup_service
            comp_obj = db.query(Comparacion).filter(
                Comparacion.usuario_id == usuario.id,
            ).order_by(Comparacion.fecha_carga.desc()).first()
            if not comp_obj:
                comp_obj = db.query(Comparacion).filter(
                    Comparacion.usuario_id.is_(None),
                ).order_by(Comparacion.fecha_carga.desc()).first()

            if comp_obj:
                ruta_comp_obj = comp_obj.obtener_ruta_o_restaurar(db)
                if ruta_comp_obj and ruta_comp_obj.exists():
                    lookup_excel = excel_lookup_service.cargar_lookup(str(ruta_comp_obj))
                if lookup_excel:
                    hubo_cambios = False
                    for p in personas:
                        id_crudo = str(p.numero_identificacion or "").strip()
                        id_limp = re.sub(r"[^\d]", "", id_crudo)
                        # Si no figura en Excel y tiene documento PDF
                        if (id_limp not in ids_en_excel) and (id_crudo not in ids_en_excel) and p.documento_id:
                            nom_p = str(p.nombre_completo or f"{p.nombres or ''} {p.apellidos or ''}").strip()
                            if nom_p and "POR REVISAR" not in nom_p:
                                match = excel_lookup_service.buscar_por_nombre(nom_p, lookup_excel, id_ocr_candidato=id_limp)
                                if match:
                                    id_ofic, reg_ofic = match
                                    from app.services.comparacion_service import comparacion_service
                                    from app.utils.validators import validador
                                    es_ced_valida_ocr = bool(id_limp and validador.validar_cedula(id_limp)[0])
                                    dist_id = comparacion_service._distancia_levenshtein(str(id_ofic), str(id_limp or "")) if id_limp else 99
                                    debe_corregir = (not es_ced_valida_ocr) or (dist_id <= 2)

                                    if debe_corregir:
                                        logger.info(f"[Personas] Auto-corrigiendo en BD por coincidencia de nombre '{nom_p}': '{p.numero_identificacion}' -> '{id_ofic}'")
                                        detalles = dict(p.detalles_campos or {})
                                        detalles["numero_identificacion_original_ocr"] = p.numero_identificacion
                                        detalles["origen_identificacion"] = "corregido_desde_excel"
                                        detalles["numero_identificacion"] = {
                                            "valor": id_ofic,
                                            "value": id_ofic,
                                            "confidence": 1.0,
                                            "status": "VALID",
                                            "source": "excel_oficial",
                                            "reason": f"Cédula corregida automáticamente desde la planilla oficial Excel (OCR leyó: {p.numero_identificacion})"
                                        }
                                        nom_ex_ofic = reg_ofic.get("nombre_completo") or f"{reg_ofic.get('nombres', '')} {reg_ofic.get('apellidos', '')}".strip()
                                        if nom_ex_ofic:
                                            p.nombre_completo = nom_ex_ofic
                                        p.numero_identificacion = id_ofic
                                        p.detalles_campos = detalles
                                        p.fecha_actualizacion = datetime.utcnow()
                                        ids_en_excel.add(id_ofic)
                                        hubo_cambios = True

                    if hubo_cambios:
                        db.commit()
        except Exception as e_heal:
            logger.warning(f"[Personas] Error en auto-corrección oportuna: {e_heal}")

    return [_enriquecer_persona_response(p, ids_en_excel, hay_excel) for p in personas]


@router.get("/{persona_id}", response_model=PersonaResponse, summary="Detalle de persona")
def obtener_persona(
    persona_id: str,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_actual),
):
    """Obtiene el detalle completo de una persona"""
    query = db.query(Persona).options(joinedload(Persona.documento)).filter(Persona.id == persona_id)
    persona = _filtrar_persona_por_usuario(query, usuario).first()
    if not persona:
        raise HTTPException(status_code=404, detail="Persona no encontrada")
    ids_en_excel, hay_excel = _obtener_ids_en_excel(db, usuario.id)
    return _enriquecer_persona_response(persona, ids_en_excel, hay_excel)


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
    query = db.query(Persona).filter(Persona.id == persona_id)
    persona = _filtrar_persona_por_usuario(query, usuario).first()
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
            tipo_documento=persona.tipo_documento,
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
    ids_en_excel, hay_excel = _obtener_ids_en_excel(db, usuario.id)
    return _enriquecer_persona_response(persona, ids_en_excel, hay_excel)


@router.post("/batch-delete", summary="Eliminar múltiples personas")
def eliminar_multiples_personas(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_actual),
):
    """Elimina en lote una lista de personas seleccionadas por ID"""
    ids = payload.get("ids", [])
    if not ids:
        return {"eliminadas": 0}

    # Filtrar que las personas pertenezcan al usuario
    query = db.query(Persona.id).filter(Persona.id.in_(ids))
    persona_ids = [row[0] for row in _filtrar_persona_por_usuario(query, usuario).all()]

    if not persona_ids:
        return {"eliminadas": 0}

    eliminadas = db.query(Persona).filter(Persona.id.in_(persona_ids)).delete(synchronize_session=False)
    db.commit()
    logger.info(f"{eliminadas} personas eliminadas en lote por usuario {usuario.id}")
    return {"eliminadas": eliminadas}


@router.delete("/vaciar/todas", summary="Vaciar tabla de personas")
def vaciar_tabla_personas(
    documento_id: Optional[str] = None,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_actual),
):
    """Elimina todas las personas del usuario (o solo las de un documento específico si se especifica documento_id)"""
    query = db.query(Persona.id)
    if documento_id and documento_id != "todos":
        query = query.filter(Persona.documento_id == documento_id)

    persona_ids = [row[0] for row in _filtrar_persona_por_usuario(query, usuario).all()]
    if not persona_ids:
        return {"eliminadas": 0, "mensaje": "No hay registros para eliminar"}

    eliminadas = db.query(Persona).filter(Persona.id.in_(persona_ids)).delete(synchronize_session=False)
    db.commit()
    logger.info(f"Tabla de personas vaciada: {eliminadas} personas eliminadas por usuario {usuario.id}")
    return {"eliminadas": eliminadas, "mensaje": f"{eliminadas} registros eliminados exitosamente"}


@router.delete("/{persona_id}", status_code=204, summary="Eliminar persona")
def eliminar_persona(
    persona_id: str,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_actual),
):
    """Elimina un registro de persona"""
    query = db.query(Persona).filter(Persona.id == persona_id)
    persona = _filtrar_persona_por_usuario(query, usuario).first()
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
    query = db.query(Persona).options(joinedload(Persona.documento)).filter(
        Persona.numero_identificacion == cedula.strip()
    )
    persona = _filtrar_persona_por_usuario(query, usuario).first()

    if not persona:
        raise HTTPException(status_code=404, detail=f"No se encontró persona con cédula {cedula}")

    ids_en_excel, hay_excel = _obtener_ids_en_excel(db, usuario.id)
    return _enriquecer_persona_response(persona, ids_en_excel, hay_excel)


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
    from app.services.ocr_service import ocr_service
    from app.utils.validators import validador

    query = db.query(Persona).options(joinedload(Persona.documento)).filter(Persona.id == persona_id)
    persona = _filtrar_persona_por_usuario(query, usuario).first()
    if not persona:
        raise HTTPException(status_code=404, detail="Persona no encontrada")

    extension = Path(file.filename).suffix.lower()
    if extension != ".pdf":
        raise HTTPException(
            status_code=400,
            detail=f"Solo se aceptan archivos PDF. Recibido: {extension}"
        )

    # Determinar documento padre (lote original al que pertenece la persona)
    doc_padre_id = persona.documento_id
    if persona.detalles_campos and isinstance(persona.detalles_campos, dict):
        if persona.detalles_campos.get("documento_padre_id"):
            doc_padre_id = persona.detalles_campos.get("documento_padre_id")
    elif persona.documento and persona.documento.metadatos and isinstance(persona.documento.metadatos, dict):
        if persona.documento.metadatos.get("documento_padre_id"):
            doc_padre_id = persona.documento.metadatos.get("documento_padre_id")

    # Guardar archivo PDF en la carpeta de subidas
    nombre_guardado = f"cedula_{persona.numero_identificacion}_{uuid.uuid4().hex[:8]}.pdf"
    ruta_guardada = settings.upload_path / nombre_guardado
    content = await file.read()
    ruta_guardada.write_bytes(content)

    # Crear registro de documento individual
    doc = Documento(
        usuario_id=usuario.id,
        nombre_archivo=nombre_guardado,
        nombre_original=file.filename,
        ruta_archivo=str(ruta_guardada),
        archivo_binario=content,
        estado="procesando",
        tamano_bytes=len(content),
        visible_en_subida=False,
        metadatos={
            "es_pdf_individual": True,
            "persona_id": str(persona.id),
            "documento_padre_id": str(doc_padre_id) if doc_padre_id else None,
        }
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

            # Unificar detalles (con seguridad para valores que son listas o None)
            det_existente = dict(persona.detalles_campos or {})
            det_otro = dict(otra.detalles_campos or {})
            for k, v in det_otro.items():
                existing = det_existente.get(k)
                # Solo sobreescribir si no existe o si el campo existente es un dict sin "valor"
                if existing is None or (isinstance(existing, dict) and not existing.get("valor")):
                    det_existente[k] = v
            persona.detalles_campos = det_existente

            # Eliminar la persona duplicada que creó el OCR
            db.delete(otra)

        # Asociar explícitamente el documento y usuario a la persona:
        # El documento principal (documento_id) se mantiene como el lote original (ej: cedulas nuevas.pdf)
        # para que la persona permanezca en la lista de ese archivo. El PDF individual se asocia a documento_pdf_id.
        if doc_padre_id and str(doc_padre_id) != str(doc.id):
            persona.documento_id = doc_padre_id
            persona.documento_pdf_id = doc.id
        else:
            persona.documento_id = doc.id
            persona.documento_pdf_id = doc.id
        persona.usuario_id = usuario.id

        # Asegurar página inicial para previsualización
        if not persona.pagina_frente:
            persona.pagina_frente = 1
        if not persona.motor_ocr or persona.motor_ocr == "excel":
            persona.motor_ocr = "google_document_ai"

        # Reevaluar completitud
        det = dict(persona.detalles_campos or {})
        det["en_pdf"] = True
        det["documento_pdf_id"] = str(doc.id)
        det["nombre_documento_pdf"] = file.filename
        if doc_padre_id:
            det["documento_padre_id"] = str(doc_padre_id)
        det.pop("motivo_no_en_pdf", None)
        if det.get("origen") == "excel_no_encontrado_en_pdf":
            det["origen"] = "excel_con_pdf_individual"

        # Quitar motivos de no encontrado en PDF o pendiente de PDF
        motivos_anteriores = det.get("motivos_revision") or []
        if isinstance(motivos_anteriores, list):
            motivos_anteriores = [
                m for m in motivos_anteriores
                if "pendiente de cargar documento" not in m
                and "No se encontró en el PDF" not in m
                and "no fue detectada en el documento PDF" not in m
            ]
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
            tipo_documento=persona.tipo_documento,
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
        ids_en_excel, hay_excel = _obtener_ids_en_excel(db, usuario.id)
        return _enriquecer_persona_response(persona, ids_en_excel, hay_excel)

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

