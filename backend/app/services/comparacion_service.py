"""
Servicio de comparación entre BD y archivos Excel externos.
Usa Pandas para el análisis de diferencias.
"""
import pandas as pd
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List
from sqlalchemy.orm import Session

from app.utils.logger import app_logger as logger
from app.utils.validators import validador


class ComparacionService:
    """
    Compara registros de la BD con un archivo Excel externo.
    
    Claves de comparación: numero_identificacion
    Campos comparados: nombres, apellidos, fecha_nacimiento, 
                       fecha_expedicion, lugar_expedicion, sexo
    
    Tipos de diferencias:
    - igual: mismo ID, mismos datos
    - diferente: mismo ID, datos distintos en algún campo
    - faltante_bd: está en Excel pero no en BD
    - nuevo_bd: está en BD pero no en Excel
    """

    CAMPOS_COMPARACION = [
        "nombres",
        "apellidos",
        "fecha_nacimiento",
        "fecha_expedicion",
        "lugar_expedicion",
        "sexo",
    ]

    MAPEO_COLUMNAS_EXCEL = {
        # Nombres posibles en el Excel → nombre interno
        "identificacion": "numero_identificacion",
        "numero_identificacion": "numero_identificacion",
        "cedula": "numero_identificacion",
        "cc": "numero_identificacion",
        "documento": "numero_identificacion",
        "nombre": "nombres",
        "nombres": "nombres",
        "primer_nombre": "nombres",
        "apellido": "apellidos",
        "apellidos": "apellidos",
        "fecha_nacimiento": "fecha_nacimiento",
        "nacimiento": "fecha_nacimiento",
        "fecha_expedicion": "fecha_expedicion",
        "expedicion": "fecha_expedicion",
        "lugar_expedicion": "lugar_expedicion",
        "lugar": "lugar_expedicion",
        "ciudad": "lugar_expedicion",
        "sexo": "sexo",
        "genero": "sexo",
    }

    def cargar_excel(self, filepath: str) -> pd.DataFrame:
        """
        Carga y normaliza un archivo Excel externo.
        Maneja múltiples formatos de columnas.
        """
        logger.info(f"Cargando Excel externo: {filepath}")
        
        try:
            # Leer Excel
            df = pd.read_excel(filepath, dtype=str)
            
            # Normalizar nombres de columnas
            df.columns = [
                col.lower()
                .strip()
                .replace(" ", "_")
                .replace("é", "e")
                .replace("í", "i")
                .replace("ó", "o")
                .replace("á", "a")
                .replace("ú", "u")
                .replace("ñ", "n")
                for col in df.columns
            ]
            
            # Renombrar columnas según mapeo
            renombres = {
                col: self.MAPEO_COLUMNAS_EXCEL[col]
                for col in df.columns
                if col in self.MAPEO_COLUMNAS_EXCEL
            }
            df = df.rename(columns=renombres)
            
            # Verificar que existe columna de identificación
            if "numero_identificacion" not in df.columns:
                raise ValueError(
                    "El archivo Excel no tiene columna de identificación. "
                    "Se esperan columnas: identificacion, cedula, cc, o numero_identificacion"
                )
            
            # Limpiar y validar identificaciones
            df["numero_identificacion"] = df["numero_identificacion"].astype(str).str.strip()
            df = df[df["numero_identificacion"].str.match(r"^\d{6,12}$")]
            
            # Normalizar campos de texto
            for campo in ["nombres", "apellidos", "lugar_expedicion", "sexo"]:
                if campo in df.columns:
                    df[campo] = df[campo].astype(str).str.strip().str.upper()
                    df[campo] = df[campo].replace("NAN", "")
            
            logger.info(f"Excel cargado: {len(df)} registros válidos")
            return df
            
        except Exception as e:
            logger.error(f"Error cargando Excel: {e}")
            raise

    def ejecutar_comparacion(
        self,
        comparacion_id: str,
        excel_path: str,
        db: Session
    ) -> Dict[str, Any]:
        """
        Ejecuta la comparación entre BD y Excel.
        Guarda el detalle de diferencias en la BD.
        """
        inicio = time.time()
        logger.info(f"Ejecutando comparación {comparacion_id}")

        from app.models.comparacion import Comparacion
        from app.models.diferencia import Diferencia
        from app.models.persona import Persona

        resultado = {
            "total_registros_bd": 0,
            "total_registros_excel": 0,
            "total_coincidentes": 0,
            "total_diferentes": 0,
            "total_faltantes_bd": 0,
            "total_nuevos_bd": 0,
            "diferencias": [],
        }

        try:
            # 1. Cargar datos de BD
            personas_bd = db.query(Persona).all()
            df_bd = pd.DataFrame([{
                "numero_identificacion": p.numero_identificacion,
                "nombres": (p.nombres or "").upper(),
                "apellidos": (p.apellidos or "").upper(),
                "fecha_nacimiento": p.fecha_nacimiento.isoformat() if p.fecha_nacimiento else "",
                "fecha_expedicion": p.fecha_expedicion.isoformat() if p.fecha_expedicion else "",
                "lugar_expedicion": (p.lugar_expedicion or "").upper(),
                "sexo": (p.sexo or "").upper(),
            } for p in personas_bd])

            resultado["total_registros_bd"] = len(df_bd)

            # 2. Cargar Excel
            df_excel = self.cargar_excel(excel_path)
            resultado["total_registros_excel"] = len(df_excel)

            # 3. Registros en Excel pero no en BD (faltantes en BD)
            diferencias_a_guardar = []

            if len(df_bd) > 0:
                ids_bd = set(df_bd["numero_identificacion"].tolist())
                ids_excel = set(df_excel["numero_identificacion"].tolist())

                ids_faltantes = ids_excel - ids_bd      # En Excel, no en BD
                ids_nuevos = ids_bd - ids_excel          # En BD, no en Excel
                ids_comunes = ids_bd & ids_excel         # En ambos

                resultado["total_faltantes_bd"] = len(ids_faltantes)
                resultado["total_nuevos_bd"] = len(ids_nuevos)

                # Diferencias en registros faltantes
                for id_faltante in ids_faltantes:
                    row_excel = df_excel[df_excel["numero_identificacion"] == id_faltante].iloc[0]
                    diferencias_a_guardar.append(Diferencia(
                        comparacion_id=comparacion_id,
                        numero_identificacion=id_faltante,
                        campo="registro_completo",
                        valor_bd=None,
                        valor_excel=str(row_excel.to_dict()),
                        tipo_diferencia="faltante_bd",
                    ))

                # Registros nuevos en BD
                for id_nuevo in ids_nuevos:
                    row_bd = df_bd[df_bd["numero_identificacion"] == id_nuevo].iloc[0]
                    diferencias_a_guardar.append(Diferencia(
                        comparacion_id=comparacion_id,
                        numero_identificacion=id_nuevo,
                        campo="registro_completo",
                        valor_bd=str(row_bd.to_dict()),
                        valor_excel=None,
                        tipo_diferencia="nuevo_bd",
                    ))

                # Comparar campos de registros comunes
                total_iguales = 0
                total_diferentes = 0

                for id_comun in ids_comunes:
                    row_bd = df_bd[df_bd["numero_identificacion"] == id_comun].iloc[0]
                    row_excel = df_excel[df_excel["numero_identificacion"] == id_comun].iloc[0]

                    tiene_diferencias = False
                    for campo in self.CAMPOS_COMPARACION:
                        val_bd = str(row_bd.get(campo, "")).strip().upper()
                        val_excel = str(row_excel.get(campo, "")).strip().upper()

                        if val_bd != val_excel and not (val_bd == "" and val_excel == "NAN"):
                            tiene_diferencias = True
                            diferencias_a_guardar.append(Diferencia(
                                comparacion_id=comparacion_id,
                                numero_identificacion=id_comun,
                                campo=campo,
                                valor_bd=val_bd or None,
                                valor_excel=val_excel if val_excel != "NAN" else None,
                                tipo_diferencia="diferente",
                            ))

                    if tiene_diferencias:
                        total_diferentes += 1
                    else:
                        total_iguales += 1

                resultado["total_coincidentes"] = total_iguales
                resultado["total_diferentes"] = total_diferentes

            else:
                # BD vacía: todo el Excel son registros faltantes
                resultado["total_faltantes_bd"] = len(df_excel)
                for _, row in df_excel.iterrows():
                    diferencias_a_guardar.append(Diferencia(
                        comparacion_id=comparacion_id,
                        numero_identificacion=row["numero_identificacion"],
                        campo="registro_completo",
                        valor_bd=None,
                        valor_excel=str(row.to_dict()),
                        tipo_diferencia="faltante_bd",
                    ))

            # 4. Guardar diferencias en BD (por lotes)
            BATCH_SIZE = 500
            for i in range(0, len(diferencias_a_guardar), BATCH_SIZE):
                lote = diferencias_a_guardar[i:i + BATCH_SIZE]
                db.add_all(lote)
                db.commit()

            # 5. Actualizar comparación
            tiempo_ms = int((time.time() - inicio) * 1000)
            comparacion = db.query(Comparacion).filter(Comparacion.id == comparacion_id).first()
            if comparacion:
                comparacion.total_registros_bd = resultado["total_registros_bd"]
                comparacion.total_registros_excel = resultado["total_registros_excel"]
                comparacion.total_coincidentes = resultado["total_coincidentes"]
                comparacion.total_diferentes = resultado["total_diferentes"]
                comparacion.total_faltantes_bd = resultado["total_faltantes_bd"]
                comparacion.total_nuevos_bd = resultado["total_nuevos_bd"]
                comparacion.estado = "completado"
                comparacion.fecha_ejecucion = datetime.utcnow()
                comparacion.tiempo_procesamiento_ms = tiempo_ms
                db.commit()

            logger.info(
                f"Comparación completada en {tiempo_ms}ms. "
                f"Iguales: {resultado['total_coincidentes']}, "
                f"Diferentes: {resultado['total_diferentes']}, "
                f"Faltantes: {resultado['total_faltantes_bd']}, "
                f"Nuevos: {resultado['total_nuevos_bd']}"
            )

            return resultado

        except Exception as e:
            logger.error(f"Error en comparación: {e}")
            try:
                comparacion = db.query(Comparacion).filter(Comparacion.id == comparacion_id).first()
                if comparacion:
                    comparacion.estado = "error"
                    comparacion.mensaje_error = str(e)[:500]
                    db.commit()
            except Exception:
                pass
            raise

    def generar_reporte_xlsx(self, comparacion_id: str, db: Session) -> str:
        """Genera un archivo XLSX con el reporte de diferencias"""
        from app.models.comparacion import Comparacion
        from app.models.diferencia import Diferencia
        from app.config import settings

        comparacion = db.query(Comparacion).filter(Comparacion.id == comparacion_id).first()
        if not comparacion:
            raise ValueError("Comparación no encontrada")

        diferencias = db.query(Diferencia).filter(
            Diferencia.comparacion_id == comparacion_id
        ).all()

        # DataFrame de diferencias
        datos = [{
            "Identificación": d.numero_identificacion,
            "Campo": d.campo,
            "Valor BD": d.valor_bd or "",
            "Valor Excel": d.valor_excel or "",
            "Tipo": d.tipo_diferencia,
        } for d in diferencias]

        df = pd.DataFrame(datos)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        nombre = f"reporte_comparacion_{timestamp}.xlsx"
        ruta = settings.export_path / nombre

        with pd.ExcelWriter(str(ruta), engine="openpyxl") as writer:
            # Hoja de resumen
            resumen_data = {
                "Métrica": [
                    "Archivo Excel",
                    "Fecha Comparación",
                    "Total BD",
                    "Total Excel",
                    "Coincidentes",
                    "Diferentes",
                    "Faltantes en BD",
                    "Nuevos en BD",
                ],
                "Valor": [
                    comparacion.nombre_original,
                    comparacion.fecha_ejecucion.strftime("%d/%m/%Y %H:%M") if comparacion.fecha_ejecucion else "",
                    comparacion.total_registros_bd,
                    comparacion.total_registros_excel,
                    comparacion.total_coincidentes,
                    comparacion.total_diferentes,
                    comparacion.total_faltantes_bd,
                    comparacion.total_nuevos_bd,
                ],
            }
            pd.DataFrame(resumen_data).to_excel(writer, sheet_name="Resumen", index=False)

            # Hoja de diferencias
            if not df.empty:
                df.to_excel(writer, sheet_name="Diferencias", index=False)

                # Hoja por tipo
                for tipo in ["diferente", "faltante_bd", "nuevo_bd"]:
                    df_tipo = df[df["Tipo"] == tipo]
                    if not df_tipo.empty:
                        nombres_hoja = {
                            "diferente": "Campos Diferentes",
                            "faltante_bd": "Faltantes en BD",
                            "nuevo_bd": "Nuevos en BD",
                        }
                        df_tipo.to_excel(
                            writer,
                            sheet_name=nombres_hoja[tipo],
                            index=False
                        )

        logger.info(f"Reporte generado: {ruta}")
        return str(ruta)


comparacion_service = ComparacionService()
