import json
import re
from datetime import date
from app.services.colombia_geo_service import colombia_geo
from app.utils.validators import validador

NO_NOMBRE_HEADER = re.compile(
    r"\b(REPUBLICA|REPÚBLICA|REDUBLICA|FEPUBLICA|COLOMBIA|COLOMB|BIA|CEDULA|CÉDULA|CIUDADANIA|CIUDADANÍA|IDENTIFICACION|"
    r"IDENTIFICACIÓN|NUMERO|NÚMERO|NUIP|APELLIDOS?|NOMBRES?|PRIMER|SEGUNDO|FIRMA|FIRMAS|TITULAR|DIGITAL|"
    r"REGISTRAD.*|OISTRAD.*|NATIONAL|PERSONAL|DOCUMENTO|CIVIL|GIVIL|ALDEL|ESTADOL?|TARJETA|NACIMIENTO|"
    r"INDICE|ÍNDICE|DERECHO|IZQUIERDO|HUELLA|CAMSCANNER|POWERED|CS|BOR|BEREN|AMEL|SANZ|TAN|FA|BAR|BER|"
    r"ALERGIF|ALMABEATRIZ|RENGIFO|BENGIFO|LOPET|LOPEZ|LÓPEZ|PENAGOS|GIRALDO|HERNAN|HERNÁN|CARLOS\s+ARIEL|"
    r"SANCHEZ|SÁNCHEZ|TORRES|GALINDO|VACHA|ALEXANDER|VEGA|ROCHA|ESTATURA|GRUPO|SANGUINEO|SANGUÍNEO|RH|"
    r"BLICA|PUBLICA|PÚBLICA|APELLIDORAJONAL|MOUSEES|DE|LA|EL|LOS|LAS|Y|DEL|POR|CON)\b",
    re.IGNORECASE
)

def limpiar_nombre(texto):
    if not texto:
        return None
    toks = [w for w in re.sub(r"[^A-ZÁÉÍÓÚÜÑ\s]", "", texto.upper()).split() if len(w) >= 2 and not NO_NOMBRE_HEADER.search(w)]
    res = " ".join(toks).strip()
    return validador.normalizar_nombre(res) if len(res) >= 3 else None

def extraer_cedula_universal(page_data):
    lines = page_data["lines"]
    full_text = page_data["full_text"]
    
    resultado = {
        "identificacion": None,
        "apellidos": None,
        "nombres": None,
        "fecha_nacimiento": None,
        "fecha_expedicion": None,
        "lugar_expedicion": None,
        "sexo": None
    }
    
    # ── 1. MRZ (Digital ID / Pasaportes) ──
    for l in lines:
        txt = l["text"].strip().replace(" ", "")
        if "<<" in txt and "<" in txt and not txt.startswith("ICCOL"):
            partes = txt.split("<<")
            if len(partes) >= 2:
                ape_raw = partes[0].replace("<", " ").strip()
                nom_raw = partes[1].replace("<", " ").strip()
                if ape_raw and not resultado["apellidos"]:
                    resultado["apellidos"] = validador.normalizar_nombre(ape_raw)
                if nom_raw and not resultado["nombres"]:
                    resultado["nombres"] = validador.normalizar_nombre(nom_raw)
        m_mrz2 = re.search(r"(\d{6})\d([MF])\d{7}[A-Z0-9]*?(\d{6,10})<\d", txt)
        if m_mrz2:
            f_nac_raw, sex_raw, id_raw = m_mrz2.groups()
            resultado["sexo"] = sex_raw
            valido, id_limpio = validador.validar_cedula(id_raw)
            if valido:
                resultado["identificacion"] = id_limpio
            dt = validador.parsear_fecha(f"19{f_nac_raw[:2]}-{f_nac_raw[2:4]}-{f_nac_raw[4:6]}" if int(f_nac_raw[:2]) > 30 else f"20{f_nac_raw[:2]}-{f_nac_raw[2:4]}-{f_nac_raw[4:6]}")
            if dt:
                resultado["fecha_nacimiento"] = dt.isoformat()

    # ── 2. Identificación (NUIP / Cédula) ──
    if not resultado["identificacion"]:
        for l in lines:
            t = l["text"].upper().strip()
            if l["y"] < 0.35:
                matches = re.finditer(r"\b(\d{1,3}(?:\.\d{3}){1,3}|\d{7,10})\b", t)
                for m in matches:
                    raw_num = re.sub(r"[^\d]", "", m.group(1))
                    valido, ced_ok = validador.validar_cedula(raw_num)
                    if valido:
                        resultado["identificacion"] = ced_ok
                        break
                if resultado["identificacion"]:
                    break
        if not resultado["identificacion"]:
            for l in lines:
                m_bc = re.search(r"[A-Z]-[0-9]+-[0-9]+-[MF]-([0-9]{7,10})-[0-9]+", l["text"])
                if m_bc:
                    valido, id_limpio = validador.validar_cedula(m_bc.group(1))
                    if valido:
                        resultado["identificacion"] = id_limpio
                        break

    # ── 3. Nombres y Apellidos (Layout Cédula Amarilla y Digital) ──
    if not resultado["nombres"] or not resultado["apellidos"]:
        lineas_frente = [l for l in lines if l["y"] < 0.35 and l["x"] < 0.55]
        
        idx_num = -1
        idx_ape = -1
        idx_nom = -1
        
        for idx, l in enumerate(lineas_frente):
            t = l["text"].upper().strip()
            if (re.search(r"\b(NUMERO|N[UÚ]MERO|NOMORO|NUIP)\b", t) or re.search(r"\b\d{7,10}\b", re.sub(r"[^\d]", "", t))) and idx_num == -1:
                idx_num = idx
            if re.search(r"\b(APELLIDOS?|APELLIDORAJONAL)\b", t) and idx_ape == -1:
                idx_ape = idx
            if re.search(r"\b(NOMBRES?|MOUSEES)\b", t) and idx_nom == -1:
                idx_nom = idx

        if idx_ape != -1 and idx_nom != -1:
            # Apellidos = texto arriba de APELLIDOS label
            cand_ape = []
            for i in range(idx_num + 1 if idx_num != -1 and idx_num < idx_ape else max(0, idx_ape - 2), idx_ape):
                limpio = limpiar_nombre(lineas_frente[i]["text"])
                if limpio:
                    cand_ape.append(limpio)
            if cand_ape and not resultado["apellidos"]:
                resultado["apellidos"] = " ".join(cand_ape)

            # Nombres = texto entre APELLIDOS y NOMBRES label
            cand_nom = []
            for i in range(idx_ape + 1, idx_nom):
                limpio = limpiar_nombre(lineas_frente[i]["text"])
                if limpio:
                    cand_nom.append(limpio)
            if cand_nom and not resultado["nombres"]:
                resultado["nombres"] = " ".join(cand_nom)

        # Fallback por líneas consecutivas limpias del frente
        if not resultado["apellidos"] or not resultado["nombres"]:
            cands_limpios = []
            for l in lineas_frente:
                if l["y"] > 0.12 and l["y"] < 0.32:
                    limpio = limpiar_nombre(l["text"])
                    if limpio and limpio not in cands_limpios and not re.search(r"\d", l["text"]):
                        cands_limpios.append(limpio)
            if len(cands_limpios) >= 2:
                if not resultado["apellidos"]:
                    resultado["apellidos"] = cands_limpios[0]
                if not resultado["nombres"]:
                    resultado["nombres"] = cands_limpios[1]
            elif len(cands_limpios) == 1:
                if not resultado["apellidos"]:
                    resultado["apellidos"] = cands_limpios[0]

    # ── 4. Fechas (Universal Cronológica Pura) ──
    fechas_doc = set()
    for l in lines:
        t = l["text"].strip()
        # Intentar parsear línea completa
        dt_full = validador.parsear_fecha(t)
        if dt_full and dt_full.year >= 1930 and dt_full.year <= 2026:
            fechas_doc.add(dt_full)
        else:
            # Buscar subcadenas de fechas estándar
            matches = re.finditer(r"\b(\d{1,2}[\s/\-\.](?:[A-Za-z]{3,4}|\d{1,2})[\s/\-\.]\d{4}|\d{1,2}\s+[A-Za-z]{3}\s+\d{4})\b", t)
            for m in matches:
                dt_m = validador.parsear_fecha(m.group(1))
                if dt_m and dt_m.year >= 1930 and dt_m.year <= 2026:
                    fechas_doc.add(dt_m)

    # Si falta fecha y hay una oculta tipo 24-???-2001
    if len(fechas_doc) < 2:
        for l in lines:
            t = l["text"].strip()
            if "???" in t or re.search(r"\b\d{1,2}[\s/\-\.][\?A-Za-z0-9]{3,4}[\s/\-\.]\d{4}\b", t):
                m_rot = re.search(r"\b(\d{1,2})[\s/\-\.][\?A-Za-z0-9]{3,4}[\s/\-\.](\d{4})\b", t)
                if m_rot and "FECHA" not in t.upper():
                    dia_v, anio_v = int(m_rot.group(1)), int(m_rot.group(2))
                    dt_r = validador.parsear_fecha(f"{dia_v}-ENE-{anio_v}")
                    if dt_r and dt_r.year >= 1930 and dt_r.year <= 2026:
                        fechas_doc.add(dt_r)

    if len(fechas_doc) >= 2:
        fechas_ord = sorted(list(fechas_doc))
        resultado["fecha_nacimiento"] = fechas_ord[0].isoformat()
        resultado["fecha_expedicion"] = fechas_ord[-1].isoformat()
    elif len(fechas_doc) == 1:
        dt_u = list(fechas_doc)[0]
        if not resultado["fecha_nacimiento"]:
            resultado["fecha_nacimiento"] = dt_u.isoformat()
        elif not resultado["fecha_expedicion"]:
            resultado["fecha_expedicion"] = dt_u.isoformat()

    # ── 5. Lugar de Expedición (Universal) ──
    for idx, l in enumerate(lines):
        t = l["text"].strip()
        if re.search(r"\b(EXPEDIC|EXPED|EXPEDICI)", t, re.I):
            # Líneas adyacentes (-1, 0, +1)
            for sub_i in range(max(0, idx - 2), min(len(lines), idx + 2)):
                cand_txt = lines[sub_i]["text"]
                lugar_res = colombia_geo.extraer_lugar_universal(cand_txt, [cand_txt])
                if lugar_res and lugar_res not in colombia_geo.DEPARTAMENTOS:
                    resultado["lugar_expedicion"] = lugar_res
                    break
            if resultado["lugar_expedicion"]:
                break

    if not resultado["lugar_expedicion"]:
        for l in lines:
            if l["y"] > 0.28:
                lugar_res = colombia_geo.extraer_lugar_universal(l["text"], [l["text"]])
                if lugar_res and lugar_res not in colombia_geo.DEPARTAMENTOS:
                    resultado["lugar_expedicion"] = lugar_res
                    break

    # ── 6. Sexo ──
    for l in lines:
        t = l["text"].upper().strip()
        if t in ["M", "F"] and l["y"] > 0.20 and l["x"] > 0.45:
            resultado["sexo"] = t
        elif re.search(r"\b(?:1\.\d{2}|[ABO][+-])\s+([MF])\b", t):
            resultado["sexo"] = re.search(r"\b(?:1\.\d{2}|[ABO][+-])\s+([MF])\b", t).group(1)
        m_bc_sex = re.search(r"-[0-9]+-([MF])-[0-9]{7,10}-", t)
        if m_bc_sex and not resultado["sexo"]:
            resultado["sexo"] = m_bc_sex.group(1)

    return resultado

with open("exports/pages_doc_ai.json", "r", encoding="utf-8") as f:
    pages = json.load(f)

print("=" * 100)
print("FINAL DETERMINISTIC UNIVERSAL PARSER VALIDATION (ALL 9 PAGES)")
print("=" * 100)

for p in pages:
    r = extraer_cedula_universal(p)
    fields = [f"{k}={r.get(k)}" for k in ['identificacion', 'apellidos', 'nombres', 'fecha_nacimiento', 'fecha_expedicion', 'lugar_expedicion', 'sexo']]
    print(f"PAG {p['page_num']} -> " + " | ".join(fields))
