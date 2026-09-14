"""
Script para revalidar registros de personas en la base de datos
bajo la regla de datos esenciales (Número de identificación, Nombre completo y Fecha de nacimiento/Edad).
"""
import os
import sys

from app.database import SessionLocal
from app.models.persona import Persona
from app.utils.validators import validador
from app.utils.logger import app_logger as logger

def revalidar_base_datos():
    db = SessionLocal()
    try:
        personas = db.query(Persona).all()
        logger.info(f"Iniciando revalidación de {len(personas)} personas en la base de datos...")

        actualizados = 0
        validados = 0

        for p in personas:
            detalles = dict(p.detalles_campos or {})
            
            tiene_datos_completos, motivos = validador.evaluar_persona_completa(
                numero_identificacion=p.numero_identificacion,
                nombres=p.nombres,
                apellidos=p.apellidos,
                nombre_completo=p.nombre_completo,
                fecha_nacimiento=p.fecha_nacimiento,
                fecha_expedicion=p.fecha_expedicion,
                lugar_expedicion=p.lugar_expedicion,
                sexo=p.sexo,
                confianza=float(p.confianza_extraccion or 100),
                detalles_campos=detalles,
                motor_ocr=p.motor_ocr,
            )

            cambio = False

            if tiene_datos_completos:
                if p.requiere_revision or p.estado_registro != "VALID":
                    p.requiere_revision = False
                    p.estado_registro = "VALID"
                    detalles.pop("motivos_revision", None)
                    p.detalles_campos = detalles
                    cambio = True
                    validados += 1
            else:
                # Filtrar motivos que mencionen expedicion o sexo
                motivos_filtrados = [
                    m for m in motivos 
                    if not any(k in m.lower() for k in ["expedici", "sexo", "lugar"])
                ]
                if len(motivos_filtrados) == 0:
                    p.requiere_revision = False
                    p.estado_registro = "VALID"
                    detalles.pop("motivos_revision", None)
                    p.detalles_campos = detalles
                    cambio = True
                    validados += 1
                elif detalles.get("motivos_revision") != motivos_filtrados:
                    detalles["motivos_revision"] = motivos_filtrados
                    p.detalles_campos = detalles
                    cambio = True

            if cambio:
                actualizados += 1

        db.commit()
        logger.info(f"Revalidación completada: {actualizados} personas actualizadas ({validados} promovidas a VÁLIDO).")
        print(f"OK: {actualizados} registros actualizados, {validados} marcados como válidos.")
    except Exception as e:
        db.rollback()
        logger.error(f"Error durante revalidación: {e}")
        print(f"ERROR: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    revalidar_base_datos()
