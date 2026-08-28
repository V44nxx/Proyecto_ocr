"""
Servicio de comparación entre BD y archivos Excel externos.
Usa Pandas para el análisis de diferencias.
"""
import pandas as pd
import re
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
        # Identificación
        "identificacion": "numero_identificacion",
        "numero_identificacion": "numero_identificacion",
        "numero_de_identificacion": "numero_identificacion",
        "num_identificacion": "numero_identificacion",
        "nro_identificacion": "numero_identificacion",
        "cedula": "numero_identificacion",
        "cedula_de_ciudadania": "numero_identificacion",
        "cc": "numero_identificacion",
        "c_c": "numero_identificacion",
        "documento": "numero_identificacion",
        "numero_documento": "numero_identificacion",
        "numero_de_documento": "numero_identificacion",
        "num_documento": "numero_identificacion",
        "no_documento": "numero_identificacion",
        "nro_documento": "numero_identificacion",
        "documento_de_identidad": "numero_identificacion",
        "documento_identidad": "numero_identificacion",
        "doc": "numero_identificacion",
        "nuip": "numero_identificacion",
        "ti": "numero_identificacion",
        "tarjeta_identidad": "numero_identificacion",
        "id": "numero_identificacion",

        # Nombres
        "nombre": "nombres",
        "nombres": "nombres",
        "primer_nombre": "primer_nombre",
        "segundo_nombre": "segundo_nombre",
        "nombre_completo": "nombres",

        # Apellidos
        "apellido": "apellidos",
        "apellidos": "apellidos",
        "primer_apellido": "primer_apellido",
        "segundo_apellido": "segundo_apellido",

        # Fechas
        "fecha_nacimiento": "fecha_nacimiento",
        "fecha_de_nacimiento": "fecha_nacimiento",
        "f_nacimiento": "fecha_nacimiento",
        "f_nac": "fecha_nacimiento",
        "nacimiento": "fecha_nacimiento",

        "fecha_expedicion": "fecha_expedicion",
        "fecha_de_expedicion": "fecha_expedicion",
        "f_expedicion": "fecha_expedicion",
        "f_exp": "fecha_expedicion",
        "expedicion": "fecha_expedicion",

        # Lugar
        "lugar_expedicion": "lugar_expedicion",
        "lugar_de_expedicion": "lugar_expedicion",
        "lugar": "lugar_expedicion",
        "ciudad_expedicion": "lugar_expedicion",
        "ciudad_de_expedicion": "lugar_expedicion",
        "municipio_expedicion": "lugar_expedicion",
        "municipio_de_expedicion": "lugar_expedicion",
        "ciudad": "lugar_expedicion",
        "municipio": "lugar_expedicion",

        # Sexo / Género
        "sexo": "sexo",
        "genero": "sexo",
        "sex": "sexo",
    }

    def _normalizar_nombre_columna(self, col: Any) -> str:
        """Normaliza un nombre de columna: minúsculas, sin tildes, sin signos."""
        s = str(col).lower().strip()
        repl = {
            "á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ü": "u", "ñ": "n",
            ".": "", "-": " ", "/": " ", "\\": " ", "_": " ", "°": "", "#": ""
        }
        for k, v in repl.items():
            s = s.replace(k, v)
        s = re.sub(r"\s+", "_", s).strip("_")
        return s

    def _limpiar_numero_id(self, val: Any) -> str:
        """Limpia número de identificación: quita puntos, comas, espacios y decimales .0 de Excel."""
        if val is None or pd.isna(val):
            return ""
        s = str(val).strip()
        if s.endswith(".0"):
            s = s[:-2]
        s = re.sub(r"[^\d]", "", s)
        return s

    def cargar_excel(self, filepath: str) -> pd.DataFrame:
        """
        Carga y normaliza un archivo Excel externo con detección inteligente de encabezados
        y mapeo flexible de columnas.
        """
        logger.info(f"Cargando Excel externo: {filepath}")

        try:
            # 1. Leer Excel preliminar
            df = pd.read_excel(filepath, dtype=str)

            # 2. Detección inteligente de fila de encabezados si hay títulos arriba
            header_row_idx = None
            cols_norm = [self._normalizar_nombre_columna(c) for c in df.columns]

            # Verificar si ya tiene columna de identificación en fila 0
            tiene_id = any(c in self.MAPEO_COLUMNAS_EXCEL and self.MAPEO_COLUMNAS_EXCEL[c] == "numero_identificacion" for c in cols_norm)

            if not tiene_id and len(df) > 0:
                # Buscar en las primeras 10 filas cuál fila tiene los nombres de columnas
                for r_idx in range(min(10, len(df))):
                    fila_valores = [self._normalizar_nombre_columna(v) for v in df.iloc[r_idx].dropna()]
                    if any(v in self.MAPEO_COLUMNAS_EXCEL and self.MAPEO_COLUMNAS_EXCEL[v] == "numero_identificacion" for v in fila_valores):
                        header_row_idx = r_idx + 1  # +1 porque fila 0 de iloc es fila 1 de Excel
                        break

                if header_row_idx is not None:
                    logger.info(f"Encabezados de Excel detectados en la fila {header_row_idx}")
                    df = pd.read_excel(filepath, header=header_row_idx, dtype=str)

            # 3. Normalizar nombres de columnas del DataFrame
            df.columns = [self._normalizar_nombre_columna(col) for col in df.columns]

            # 4. Renombrar columnas según mapeo flexible
            renombres = {
                col: self.MAPEO_COLUMNAS_EXCEL[col]
                for col in df.columns
                if col in self.MAPEO_COLUMNAS_EXCEL
            }
            df = df.rename(columns=renombres)

            # 5. Combinar primer_nombre y segundo_nombre si vienen separados
            if "primer_nombre" in df.columns:
                p_nom = df["primer_nombre"].fillna("").astype(str).str.strip()
                s_nom = df["segundo_nombre"].fillna("").astype(str).str.strip() if "segundo_nombre" in df.columns else ""
                noms_combinados = (p_nom + " " + s_nom).str.strip()
                if "nombres" not in df.columns or df["nombres"].isna().all():
                    df["nombres"] = noms_combinados

            # 6. Combinar primer_apellido y segundo_apellido si vienen separados
            if "primer_apellido" in df.columns:
                p_ape = df["primer_apellido"].fillna("").astype(str).str.strip()
                s_ape = df["segundo_apellido"].fillna("").astype(str).str.strip() if "segundo_apellido" in df.columns else ""
                apes_combinados = (p_ape + " " + s_ape).str.strip()
                if "apellidos" not in df.columns or df["apellidos"].isna().all():
                    df["apellidos"] = apes_combinados

            # 7. Verificar que existe columna de identificación
            if "numero_identificacion" not in df.columns:
                cols_encontradas = ", ".join(list(df.columns)[:8])
                raise ValueError(
                    f"No se encontró columna de identificación en el Excel. "
                    f"Columnas detectadas: [{cols_encontradas}]. "
                    f"Se esperan columnas como: Cédula, Documento, Identificación, CC o No. Documento."
                )

            # 8. Limpiar y validar identificaciones (eliminar puntos, comas, .0)
            df["numero_identificacion"] = df["numero_identificacion"].apply(self._limpiar_numero_id)
            df = df[df["numero_identificacion"].str.len() >= 5]

            # 9. Normalizar campos de texto
            for campo in ["nombres", "apellidos", "lugar_expedicion", "sexo"]:
                if campo in df.columns:
                    df[campo] = df[campo].fillna("").astype(str).str.strip().str.upper()
                    df[campo] = df[campo].replace({"NAN": "", "NONE": "", "NULL": ""})

            logger.info(f"Excel cargado y normalizado exitosamente: {len(df)} registros válidos")
            return df

        except Exception as e:
            logger.error(f"Error cargando Excel: {e}")
            raise

    def _normalizar_para_comparacion(self, val: Any, campo: str = "") -> str:
        """
        Normaliza un valor para comparación exacta sin falsos positivos por tildes,
        espacios o formatos de fecha alternativos.
        """
        if val is None or pd.isna(val):
            return ""
        s = str(val).strip().upper()
        if s in ("NAN", "NONE", "NULL", "NAT"):
            return ""

        # Si es un campo de fecha, comparar por fecha parseada
        if "fecha" in campo or re.match(r"^\d{1,4}[/\-\.]\d{1,2}[/\-\.]\d{1,4}", s):
            f_obj = validador.parsear_fecha(s)
            if f_obj:
                return f_obj.isoformat()

        # Quitar tildes
        repl = {"Á": "A", "É": "E", "Í": "I", "Ó": "O", "Ú": "U", "Ü": "U"}
        for k, v in repl.items():
            s = s.replace(k, v)
        s = re.sub(r"\s+", " ", s).strip()
        return s

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
        import uuid as uuid_pkg
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
                "numero_identificacion": self._limpiar_numero_id(p.numero_identificacion),
                "nombres": p.nombres or "",
                "apellidos": p.apellidos or "",
                "fecha_nacimiento": p.fecha_nacimiento.isoformat() if p.fecha_nacimiento else "",
                "fecha_expedicion": p.fecha_expedicion.isoformat() if p.fecha_expedicion else "",
                "lugar_expedicion": p.lugar_expedicion or "",
                "sexo": p.sexo or "",
                "pagina_numero": p.pagina_numero or 1,
                "confianza_extraccion": float(p.confianza_extraccion or 0.0),
                "estado_registro": p.estado_registro or "VALID",
            } for p in personas_bd])

            # Filtrar registros vacíos de BD
            if len(df_bd) > 0:
                df_bd = df_bd[df_bd["numero_identificacion"].str.len() >= 5]

            resultado["total_registros_bd"] = len(df_bd)

            # 2. Cargar Excel externo
            df_excel = self.cargar_excel(excel_path)
            resultado["total_registros_excel"] = len(df_excel)

            # 3. Analizar diferencias
            diferencias_a_guardar = []
            comp_uuid = uuid_pkg.UUID(str(comparacion_id))

            if len(df_bd) > 0:
                ids_bd = set(df_bd["numero_identificacion"].tolist())
                ids_excel = set(df_excel["numero_identificacion"].tolist())

                ids_faltantes = ids_excel - ids_bd      # En Excel, no en BD
                ids_nuevos = ids_bd - ids_excel          # En BD, no en Excel
                ids_comunes = ids_bd & ids_excel         # En ambos

                resultado["total_faltantes_bd"] = len(ids_faltantes)
                resultado["total_nuevos_bd"] = len(ids_nuevos)

                # Diferencias en registros faltantes en BD
                for id_faltante in ids_faltantes:
                    row_excel = df_excel[df_excel["numero_identificacion"] == id_faltante].iloc[0]
                    diferencias_a_guardar.append(Diferencia(
                        comparacion_id=comp_uuid,
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
                        comparacion_id=comp_uuid,
                        numero_identificacion=id_nuevo,
                        campo="registro_completo",
                        valor_bd=str(row_bd.to_dict()),
                        valor_excel=None,
                        tipo_diferencia="nuevo_bd",
                    ))

                # Comparar campos de registros comunes con normalización
                total_iguales = 0
                total_diferentes = 0

                for id_comun in ids_comunes:
                    row_bd = df_bd[df_bd["numero_identificacion"] == id_comun].iloc[0]
                    row_excel = df_excel[df_excel["numero_identificacion"] == id_comun].iloc[0]

                    tiene_diferencias = False
                    for campo in self.CAMPOS_COMPARACION:
                        if campo in row_excel:
                            val_bd_norm = self._normalizar_para_comparacion(row_bd.get(campo), campo=campo)
                            val_excel_norm = self._normalizar_para_comparacion(row_excel.get(campo), campo=campo)

                            if val_bd_norm != val_excel_norm:
                                tiene_diferencias = True
                                diferencias_a_guardar.append(Diferencia(
                                    comparacion_id=comp_uuid,
                                    numero_identificacion=id_comun,
                                    campo=campo,
                                    valor_bd=str(row_bd.get(campo) or "") or None,
                                    valor_excel=str(row_excel.get(campo) or "") or None,
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
                        comparacion_id=comp_uuid,
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
            comparacion = db.query(Comparacion).filter(Comparacion.id == comp_uuid).first()
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
