"""
ExcelLookupService
Carga una planilla Excel oficial en memoria como diccionario de consulta rapida.
Se usa durante el OCR para obtener el nombre/apellido oficial de cada persona
identificada por su numero de cedula/TI/contrasena.
"""
import re
import pandas as pd
from pathlib import Path
from typing import Dict, Optional, Any, Tuple
from app.utils.logger import app_logger as logger


_MAPEO_COLUMNAS = {
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

    # Nombre completo directo
    "nombre_completo": "nombre_completo",
    "nombres_completos": "nombre_completo",
    "nombre_y_apellidos": "nombre_completo",
    "nombres_y_apellidos": "nombre_completo",
    "nombre_y_apellido": "nombre_completo",
    "apellidos_y_nombres": "nombre_completo",
    "apellido_y_nombre": "nombre_completo",
    "aprendiz": "nombre_completo",
    "estudiante": "nombre_completo",
    "funcionario": "nombre_completo",
    "titular": "nombre_completo",

    # Nombres
    "nombre": "nombres",
    "nombres": "nombres",
    "primer_nombre": "primer_nombre",
    "segundo_nombre": "segundo_nombre",

    # Apellidos
    "apellido": "apellidos",
    "apellidos": "apellidos",
    "primer_apellido": "primer_apellido",
    "segundo_apellido": "segundo_apellido",
}


def _normalizar_col(col: Any) -> str:
    s = str(col).lower().strip()
    for k, v in {"a": "a", "e": "e", "i": "i", "o": "o", "u": "u", "u": "u", "n": "n"}.items():
        pass
    for orig, rep in [("a","a"),("e","e"),("i","i"),("o","o"),("u","u"),("u","u"),("n","n"),
                      (".",""),("-"," "),("/"," "),("\\"," "),("_"," "),("°",""),("#","")]:
        s = s.replace(orig, rep)
    s = re.sub(r"\s+", "_", s).strip("_")
    return s


def _normalizar_col2(col: Any) -> str:
    """Normaliza nombre de columna: minusculas, sin tildes, sin separadores."""
    import unicodedata
    s = str(col).lower().strip()
    # Quitar tildes via NFD
    s = ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
    # Reemplazar separadores
    s = re.sub(r"[.\-/\\\s°#]+", "_", s).strip("_")
    return s


def _limpiar_id(val: Any) -> str:
    if val is None:
        return ""
    s = str(val).strip()
    if s.lower() in ("nan", "none", "null", ""):
        return ""
    if s.endswith(".0"):
        s = s[:-2]
    s = re.sub(r"[^\d]", "", s)
    return s


def _limpiar_texto(val: Any) -> str:
    if val is None:
        return ""
    s = str(val).strip().upper()
    if s in ("NAN", "NONE", "NULL", ""):
        return ""
    return re.sub(r"\s+", " ", s).strip()


def _procesar_hoja(df_raw: pd.DataFrame, filepath: str, sheet_name: str) -> Optional[pd.DataFrame]:
    if df_raw is None or df_raw.empty:
        return None

    df = df_raw
    cols_norm = [_normalizar_col2(c) for c in df_raw.columns]
    tiene_id = any(_MAPEO_COLUMNAS.get(c) == "numero_identificacion" for c in cols_norm)

    if not tiene_id and len(df_raw) > 0:
        for r_idx in range(min(15, len(df_raw))):
            fila_valores = [_normalizar_col2(v) for v in df_raw.iloc[r_idx].dropna()]
            if any(_MAPEO_COLUMNAS.get(v) == "numero_identificacion" for v in fila_valores):
                df = pd.read_excel(filepath, sheet_name=sheet_name, header=r_idx + 1, dtype=str)
                logger.info(f"[ExcelLookup] Hoja '{sheet_name}': encabezado en fila {r_idx + 1}")
                break

    df.columns = [_normalizar_col2(c) for c in df.columns]
    renombres = {c: _MAPEO_COLUMNAS[c] for c in df.columns if c in _MAPEO_COLUMNAS}
    df = df.rename(columns=renombres)

    if "numero_identificacion" not in df.columns:
        return None

    if "primer_nombre" in df.columns:
        p = df["primer_nombre"].fillna("").astype(str).str.strip()
        s_col = df["segundo_nombre"].fillna("").astype(str).str.strip() if "segundo_nombre" in df.columns else pd.Series([""] * len(df))
        combined = (p + " " + s_col).str.strip()
        if "nombres" not in df.columns or df["nombres"].isna().all():
            df["nombres"] = combined

    if "primer_apellido" in df.columns:
        p = df["primer_apellido"].fillna("").astype(str).str.strip()
        s_col = df["segundo_apellido"].fillna("").astype(str).str.strip() if "segundo_apellido" in df.columns else pd.Series([""] * len(df))
        combined = (p + " " + s_col).str.strip()
        if "apellidos" not in df.columns or df["apellidos"].isna().all():
            df["apellidos"] = combined

    # Unificar en un único campo nombre_completo
    if "nombre_completo" not in df.columns or df["nombre_completo"].isna().all():
        noms = df["nombres"].fillna("").astype(str).str.strip() if "nombres" in df.columns else pd.Series([""] * len(df))
        apes = df["apellidos"].fillna("").astype(str).str.strip() if "apellidos" in df.columns else pd.Series([""] * len(df))
        df["nombre_completo"] = (noms + " " + apes).str.strip()

    df["numero_identificacion"] = df["numero_identificacion"].apply(_limpiar_id)
    df = df[df["numero_identificacion"].str.len() >= 5]

    for campo in ["nombre_completo", "nombres", "apellidos"]:
        if campo in df.columns:
            df[campo] = df[campo].fillna("").astype(str).apply(_limpiar_texto)

    return df


class ExcelLookupService:
    """
    Servicio de consulta rapida de nombres por numero de identificacion.
    Carga el Excel en memoria como diccionario para busqueda O(1).
    """

    def cargar_lookup(self, filepath: str) -> Dict[str, Dict[str, str]]:
        """
        Carga el Excel y devuelve un diccionario:
            { "1005123456": {"nombre_completo": "JUAN CARLOS LOPEZ GOMEZ", "nombres": "...", "apellidos": "..."}, ... }
        Si hay error devuelve {} para no bloquear el OCR.
        """
        lookup: Dict[str, Dict[str, str]] = {}
        try:
            excel_file = pd.ExcelFile(filepath)
            dfs_validos = []

            for sheet_name in excel_file.sheet_names:
                try:
                    df_raw = pd.read_excel(filepath, sheet_name=sheet_name, dtype=str)
                    df = _procesar_hoja(df_raw, filepath, sheet_name)
                    if df is not None and not df.empty:
                        dfs_validos.append(df)
                        logger.info(f"[ExcelLookup] Hoja '{sheet_name}': {len(df)} registros")
                except Exception as e_sheet:
                    logger.warning(f"[ExcelLookup] No se pudo procesar hoja '{sheet_name}': {e_sheet}")

            if not dfs_validos:
                logger.warning(f"[ExcelLookup] No se encontraron hojas validas en {filepath}")
                return {}

            df_total = pd.concat(dfs_validos, ignore_index=True)
            df_total = df_total.drop_duplicates(subset=["numero_identificacion"], keep="first")

            nc_col = "nombre_completo" if "nombre_completo" in df_total.columns else None
            nombres_col = "nombres" if "nombres" in df_total.columns else None
            apellidos_col = "apellidos" if "apellidos" in df_total.columns else None

            for _, row in df_total.iterrows():
                num_id = str(row["numero_identificacion"]).strip()
                if not num_id or len(num_id) < 5:
                    continue
                entry: Dict[str, str] = {}
                nom_comp = _limpiar_texto(row.get(nc_col, "")) if nc_col else ""
                nom_part = _limpiar_texto(row.get(nombres_col, "")) if nombres_col else ""
                ape_part = _limpiar_texto(row.get(apellidos_col, "")) if apellidos_col else ""

                if not nom_comp and (nom_part or ape_part):
                    nom_comp = f"{nom_part} {ape_part}".strip()

                entry["nombre_completo"] = nom_comp
                entry["nombres"] = nom_part or nom_comp
                entry["apellidos"] = ape_part
                lookup[num_id] = entry

            logger.info(f"[ExcelLookup] {len(lookup)} registros cargados de {Path(filepath).name}")
        except Exception as e:
            logger.error(f"[ExcelLookup] Error cargando lookup de {filepath}: {e}")

        return lookup

    def buscar(self, numero_id: str, lookup: Dict[str, Dict[str, str]]) -> Optional[Dict[str, str]]:
        """
        Busca un numero de identificacion en el lookup.
        Devuelve {"nombres": ..., "apellidos": ...} o None si no encontrado.
        """
        if not numero_id or not lookup:
            return None
        id_limpio = _limpiar_id(numero_id)
        return lookup.get(id_limpio)

    def buscar_por_nombre(
        self,
        nombre: str,
        lookup: Dict[str, Dict[str, str]],
        id_ocr_candidato: Optional[str] = None
    ) -> Optional[Tuple[str, Dict[str, str]]]:
        """
        Busca por coincidencia de nombre completo oficial en el lookup.
        Devuelve (numero_identificacion, entry) o None si no coincide.
        Si hay múltiples candidatos con nombres similares, desempata usando
        la similitud con el número de identificación detectado por OCR.
        """
        if not nombre or not lookup:
            return None

        nom_clean = _limpiar_texto(nombre)
        PALABRAS_IGNORAR = {
            "REPUBLICA", "COLOMBIA", "DE", "DEL", "LA", "LAS", "LOS", "EL", "Y", "E",
            "CEDULA", "CIUDADANIA", "TARJETA", "IDENTIDAD", "PERSONAL", "NACIONAL",
            "REGISTRADURIA", "ESTADO", "CIVIL", "NUMERO", "NO", "DOC", "DOCUMENTO",
            "POR", "REVISAR"
        }
        palabras_utiles = [p for p in re.findall(r"[A-Z0-9]+", nom_clean) if p not in PALABRAS_IGNORAR and len(p) > 1]
        if len(palabras_utiles) < 2:
            return None

        from app.services.comparacion_service import comparacion_service

        candidatos = []
        for num_id, entry in lookup.items():
            nom_comp_excel = entry.get("nombre_completo", "")
            if nom_comp_excel and comparacion_service._son_nombres_equivalentes(
                nombres_bd=nom_clean, apellidos_bd="", nombres_excel=nom_comp_excel, apellidos_excel=""
            ):
                candidatos.append((num_id, entry))

        if not candidatos:
            return None

        if len(candidatos) == 1:
            return candidatos[0]

        # Desempate entre múltiples coincidencias de nombre:
        if id_ocr_candidato:
            id_limp = _limpiar_id(id_ocr_candidato)
            def score_candidato(item):
                cand_id = item[0]
                # Prefijo común
                prefijo = 0
                for a, b in zip(cand_id, id_limp):
                    if a == b:
                        prefijo += 1
                    else:
                        break
                # Dígitos en común en cualquier posición
                dist = comparacion_service._distancia_levenshtein(cand_id, id_limp)
                return (prefijo, -dist)

            candidatos.sort(key=score_candidato, reverse=True)
            return candidatos[0]

        return candidatos[0]

    def verificar_exhaustiva_ocr_excel(
        self,
        id_ocr: Optional[str],
        nombre_ocr: Optional[str],
        nombres_ocr: Optional[str] = None,
        apellidos_ocr: Optional[str] = None,
        lookup: Optional[Dict[str, Dict[str, str]]] = None,
        texto_ocr: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Verificación exhaustiva bidireccional entre la información extraída por OCR
        del documento físico y la planilla oficial de Excel.

        Reglas estrictas de validación:
        1. Valida si la cédula extraída por OCR está en Excel.
        2. Si la cédula está en Excel, valida si el nombre del documento físico coincide
           con el nombre registrado en Excel para esa cédula (en ambos lados).
        3. Si la cédula pertenece a OTRA persona en Excel, NUNCA sobreescribe el nombre
           del documento con el de Excel. Busca si el titular real existe en Excel con otro ID.
           Si se confirma por texto del documento o distancia <= 2, auto-corrige el ID al oficial.
           Si no, genera una alerta crítica de discrepancia y marca para revisión.
        4. Si la cédula no está en Excel pero el nombre sí, solo auto-corrige la cédula si
           la distancia es leve (<= 2) o la cédula de Excel figura en el texto del documento.
           Si es un homónimo con cédula completamente diferente, conserva la cédula física del OCR.
        """
        from app.utils.validators import validador
        from app.services.comparacion_service import comparacion_service
        from app.utils.name_cleaner import resolver_nombre_completo

        id_limpio = _limpiar_id(id_ocr) if id_ocr else ""
        tiene_id_ocr = bool(id_limpio and not id_limpio.startswith("SIN_ID") and len(id_limpio) >= 5)

        nom_crudo = resolver_nombre_completo(
            nombres=nombres_ocr or "",
            apellidos=apellidos_ocr or "",
            actual=nombre_ocr or ""
        ).strip()
        nom_doc = _limpiar_texto(nom_crudo)

        def _es_invalido(val: str) -> bool:
            if not val or len(val) < 3 or val == "POR REVISAR":
                return True
            from app.services.spatial_field_extractor import spatial_field_extractor
            from app.services.colombia_geo_service import colombia_geo
            if colombia_geo.es_geografico(val):
                return True
            palabras = val.split()
            if len(palabras) < 2 and len(val) < 6:
                return True
            return False

        tiene_nom_doc = not _es_invalido(nom_doc)

        # Si no hay lookup cargado, respetar fielmente los datos del documento OCR
        if not lookup:
            return {
                "id_final": id_limpio if tiene_id_ocr else "",
                "nombre_final": nom_doc if tiene_nom_doc else (nombre_ocr or "POR REVISAR"),
                "nombres_final": nombres_ocr or (nom_doc if tiene_nom_doc else "POR REVISAR"),
                "apellidos_final": apellidos_ocr or "",
                "id_original_ocr": None,
                "encontrado_en_excel": False,
                "fuente_identificacion": "ocr_directo",
                "fuente_nombre": "cedula_fisica",
                "estado_registro": "VALID" if (tiene_id_ocr and tiene_nom_doc) else "REVIEW_REQUIRED",
                "requiere_revision": not (tiene_id_ocr and tiene_nom_doc),
                "discrepancia_excel": None,
                "motivo": "Documento procesado por OCR (sin planilla Excel para cotejar)."
            }

        # ── CASO A: El número extraído por OCR figura en Excel ──
        reg_id_excel = lookup.get(id_limpio) if tiene_id_ocr else None
        if reg_id_excel:
            nom_excel_para_id = reg_id_excel.get("nombre_completo", "").strip()

            if tiene_nom_doc:
                coinciden = comparacion_service._son_nombres_equivalentes(
                    nombres_bd=nom_doc,
                    apellidos_bd="",
                    nombres_excel=nom_excel_para_id,
                    apellidos_excel=""
                )
                if coinciden:
                    # ── A.1: CORRESPONDENCIA TOTAL (Cédula y Nombre verificados en ambos lados) ──
                    return {
                        "id_final": id_limpio,
                        "nombre_final": nom_excel_para_id or nom_doc,
                        "nombres_final": reg_id_excel.get("nombres") or nom_excel_para_id,
                        "apellidos_final": reg_id_excel.get("apellidos") or "",
                        "id_original_ocr": None,
                        "encontrado_en_excel": True,
                        "fuente_identificacion": "ocr_verificado_excel",
                        "fuente_nombre": "excel_oficial",
                        "estado_registro": "VALID",
                        "requiere_revision": False,
                        "discrepancia_excel": None,
                        "motivo": f"Verificación exhaustiva exitosa: Cédula {id_limpio} y Nombre corresponden en ambos lados."
                    }
                else:
                    # ── A.2: DISCREPANCIA CRÍTICA: La cédula pertenece a otra persona en Excel ──
                    # NUNCA sobreescribir el nombre del titular con el de la cédula equivocada
                    match_nom = self.buscar_por_nombre(nom_doc, lookup, id_ocr_candidato=id_limpio)
                    if match_nom:
                        id_excel_titular, reg_nom = match_nom
                        dist_id = comparacion_service._distancia_levenshtein(str(id_excel_titular), str(id_limpio))
                        id_en_texto = bool(texto_ocr and str(id_excel_titular) in re.sub(r"[^\d]", "", texto_ocr))

                        if dist_id <= 2 or id_en_texto:
                            # Se detectó que el número OCR tenía un error menor de lectura, pero el titular es real
                            return {
                                "id_final": id_excel_titular,
                                "nombre_final": reg_nom.get("nombre_completo") or nom_doc,
                                "nombres_final": reg_nom.get("nombres") or "",
                                "apellidos_final": reg_nom.get("apellidos") or "",
                                "id_original_ocr": id_limpio,
                                "encontrado_en_excel": True,
                                "fuente_identificacion": "corregido_desde_excel",
                                "fuente_nombre": "excel_oficial",
                                "estado_registro": "VALID",
                                "requiere_revision": False,
                                "discrepancia_excel": None,
                                "motivo": f"Cédula auto-corregida: OCR leyó '{id_limpio}' (asociada en Excel a '{nom_excel_para_id}'), pero el documento pertenece a '{nom_doc}' cuya cédula oficial es {id_excel_titular} confirmada en el documento."
                            }
                        else:
                            mot_disc = (
                                f"Discrepancia crítica: La cédula '{id_limpio}' leída por OCR pertenece a '{nom_excel_para_id}' en Excel, "
                                f"pero el documento físico indica '{nom_doc}' (quien figura en Excel con cédula {id_excel_titular}). "
                                f"Se conserva el nombre físico del documento."
                            )
                            return {
                                "id_final": id_limpio,
                                "nombre_final": nom_doc,
                                "nombres_final": nombres_ocr or nom_doc,
                                "apellidos_final": apellidos_ocr or "",
                                "id_original_ocr": None,
                                "encontrado_en_excel": False,
                                "fuente_identificacion": "ocr_con_discrepancia",
                                "fuente_nombre": "cedula_fisica",
                                "estado_registro": "REVIEW_REQUIRED",
                                "requiere_revision": True,
                                "discrepancia_excel": {
                                    "tipo": "conflicto_id_vs_nombre",
                                    "id_ocr": id_limpio,
                                    "nombre_cedula": nom_doc,
                                    "nombre_excel_para_id": nom_excel_para_id,
                                    "id_excel_para_nombre": id_excel_titular,
                                    "motivo": mot_disc
                                },
                                "motivo": mot_disc
                            }
                    else:
                        mot_disc = (
                            f"Inconsistencia de titular: La cédula extraída ({id_limpio}) pertenece en la planilla oficial a "
                            f"'{nom_excel_para_id}', pero el documento escaneado pertenece a '{nom_doc}'. "
                            f"Se conserva el nombre físico del documento para evitar datos erróneos."
                        )
                        return {
                            "id_final": id_limpio,
                            "nombre_final": nom_doc,
                            "nombres_final": nombres_ocr or nom_doc,
                            "apellidos_final": apellidos_ocr or "",
                            "id_original_ocr": None,
                            "encontrado_en_excel": False,
                            "fuente_identificacion": "ocr_con_discrepancia",
                            "fuente_nombre": "cedula_fisica",
                            "estado_registro": "REVIEW_REQUIRED",
                            "requiere_revision": True,
                            "discrepancia_excel": {
                                "tipo": "id_pertenece_a_otro",
                                "id_ocr": id_limpio,
                                "nombre_cedula": nom_doc,
                                "nombre_excel_para_id": nom_excel_para_id,
                                "motivo": mot_disc
                            },
                            "motivo": mot_disc
                        }
            else:
                # OCR no pudo leer el nombre pero la cédula sí existe en Excel
                return {
                    "id_final": id_limpio,
                    "nombre_final": nom_excel_para_id,
                    "nombres_final": reg_id_excel.get("nombres") or nom_excel_para_id,
                    "apellidos_final": reg_id_excel.get("apellidos") or "",
                    "id_original_ocr": None,
                    "encontrado_en_excel": True,
                    "fuente_identificacion": "ocr_verificado_excel",
                    "fuente_nombre": "excel_oficial",
                    "estado_registro": "VALID",
                    "requiere_revision": False,
                    "discrepancia_excel": None,
                    "motivo": f"Cédula {id_limpio} verificada en Excel. Nombre oficial asignado desde la planilla."
                }

        # ── CASO B: La cédula extraída por OCR NO figura directamente en Excel ──
        if tiene_nom_doc:
            match_nom = self.buscar_por_nombre(nom_doc, lookup, id_ocr_candidato=id_limpio)
            if match_nom:
                id_excel_titular, reg_nom = match_nom
                nom_excel = reg_nom.get("nombre_completo", "")

                dist_id = comparacion_service._distancia_levenshtein(str(id_excel_titular), str(id_limpio)) if tiene_id_ocr else 99
                id_en_texto = bool(texto_ocr and str(id_excel_titular) in re.sub(r"[^\d]", "", texto_ocr))
                es_ced_valida_ocr = bool(tiene_id_ocr and validador.validar_cedula(id_limpio)[0])

                # Auto-corrección estricta: solo si hay evidencia física de que la cédula de Excel corresponde a esta persona
                debe_corregir = (dist_id <= 2) or id_en_texto or (not es_ced_valida_ocr and (dist_id <= 4 or id_en_texto or not tiene_id_ocr))

                if debe_corregir:
                    return {
                        "id_final": id_excel_titular,
                        "nombre_final": nom_excel or nom_doc,
                        "nombres_final": reg_nom.get("nombres") or nom_excel,
                        "apellidos_final": reg_nom.get("apellidos") or "",
                        "id_original_ocr": id_limpio if tiene_id_ocr else None,
                        "encontrado_en_excel": True,
                        "fuente_identificacion": "corregido_desde_excel",
                        "fuente_nombre": "excel_oficial",
                        "estado_registro": "VALID",
                        "requiere_revision": False,
                        "discrepancia_excel": None,
                        "motivo": f"Cédula oficial {id_excel_titular} verificada y asignada desde Excel por coincidencia de nombre '{nom_doc}'."
                    }
                else:
                    mot_disc = (
                        f"Posible homónimo o cédula diferente: El nombre coincide con '{nom_excel}' en Excel (Cédula: {id_excel_titular}), "
                        f"pero el documento físico presenta la cédula '{id_limpio}'. No se sobrescribió para evitar un error de asignación."
                    )
                    return {
                        "id_final": id_limpio,
                        "nombre_final": nom_doc,
                        "nombres_final": nombres_ocr or nom_doc,
                        "apellidos_final": apellidos_ocr or "",
                        "id_original_ocr": None,
                        "encontrado_en_excel": False,
                        "fuente_identificacion": "ocr_directo",
                        "fuente_nombre": "cedula_fisica",
                        "estado_registro": "REVIEW_REQUIRED",
                        "requiere_revision": True,
                        "discrepancia_excel": {
                            "tipo": "nombre_en_excel_pero_id_diferente",
                            "id_ocr": id_limpio,
                            "nombre_cedula": nom_doc,
                            "id_excel_homonimo": id_excel_titular,
                            "nombre_excel": nom_excel,
                            "motivo": mot_disc
                        },
                        "motivo": mot_disc
                    }

        # ── CASO C: Ni la cédula ni el nombre figuran en Excel ──
        return {
            "id_final": id_limpio if tiene_id_ocr else "",
            "nombre_final": nom_doc if tiene_nom_doc else (nombre_ocr or "POR REVISAR"),
            "nombres_final": nombres_ocr or (nom_doc if tiene_nom_doc else "POR REVISAR"),
            "apellidos_final": apellidos_ocr or "",
            "id_original_ocr": None,
            "encontrado_en_excel": False,
            "fuente_identificacion": "ocr_directo",
            "fuente_nombre": "cedula_fisica",
            "estado_registro": "VALID" if (tiene_id_ocr and tiene_nom_doc) else "REVIEW_REQUIRED",
            "requiere_revision": not (tiene_id_ocr and tiene_nom_doc),
            "discrepancia_excel": None,
            "motivo": "Documento procesado por OCR (no figura en la planilla oficial de Excel)."
        }


excel_lookup_service = ExcelLookupService()
