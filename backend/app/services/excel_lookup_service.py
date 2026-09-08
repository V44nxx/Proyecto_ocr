"""
ExcelLookupService
Carga una planilla Excel oficial en memoria como diccionario de consulta rapida.
Se usa durante el OCR para obtener el nombre/apellido oficial de cada persona
identificada por su numero de cedula/TI/contrasena.
"""
import re
import pandas as pd
from pathlib import Path
from typing import Dict, Optional, Any
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


excel_lookup_service = ExcelLookupService()
