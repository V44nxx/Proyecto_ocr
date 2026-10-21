"""
Datos cruzados entre fichas de un mismo usuario:
- sin planilla adjunta, el OCR no coteja con la planilla de otra ficha
- la comparación automática solo mira las personas de las fichas subidas con la planilla
- dos titulares distintos con la misma cédula leída no se funden en una sola persona
- la subida vincula la planilla con las fichas del lote
"""
import pandas as pd

from app.models.comparacion import Comparacion
from app.models.persona import Persona
from tests.utilidades_pg import cabecera, crear_ficha, crear_persona, crear_usuario, pdf_de_prueba, requiere_postgres


def _planilla(ruta, filas):
    pd.DataFrame([{"Cedula": c, "Nombre completo": n} for c, n in filas]).to_excel(ruta, index=False)
    return ruta


def _comparacion(db, usuario, ruta, fichas):
    comp = Comparacion(usuario_id=usuario.id, nombre_archivo=ruta.name, nombre_original=ruta.name,
                       ruta_archivo=str(ruta), estado="pendiente",
                       documento_ids=[str(f.id) for f in fichas] if fichas is not None else None)
    db.add(comp)
    db.commit()
    return comp


def _guardar(db, ficha, cedula, nombres, apellidos):
    from app.services.ocr_service import ocr_service
    return ocr_service._guardar_persona(
        datos={"identificacion": cedula, "nombres": nombres, "apellidos": apellidos,
               "nombre_completo": f"{nombres} {apellidos}", "confianza_extraccion": 95.0,
               "tipo_documento": "CEDULA_CIUDADANIA", "pagina_frente": 1, "grupo_documento_id": "G-1",
               "fecha_nacimiento": "1990-01-01", "fecha_expedicion": "2008-01-01"},
        texto_ocr=f"{cedula} {nombres} {apellidos}", documento_id=str(ficha.id), db=db,
        ocr_engine="google_document_ai", pagina_num=1,
    )


# ── Planilla de otra ficha ──────────────────────────────────────────

@requiere_postgres
def test_sin_planilla_adjunta_no_usa_la_planilla_de_otra_ficha(bd, tmp_path):
    db = bd.SessionLocal()
    ana = crear_usuario(db, "ana@example.com")
    ficha_vieja = crear_ficha(db, ana, "3000001.pdf")
    ficha_nueva = crear_ficha(db, ana, "3000002.pdf")
    # En la planilla de la ficha vieja, esa cédula es de otra persona
    _comparacion(db, ana, _planilla(tmp_path / "vieja.xlsx", [("1000000101", "MARTA LUCIA GOMEZ")]), [ficha_vieja])

    res = _guardar(db, ficha_nueva, "1000000101", "CARLOS ANDRES", "RUIZ PINEDA")
    db.close()

    assert "CARLOS" in res["nombre_completo"]
    assert "MARTA" not in res["nombre_completo"]


@requiere_postgres
def test_sin_lookup_usa_la_planilla_subida_con_su_propia_ficha(bd, tmp_path):
    db = bd.SessionLocal()
    ana = crear_usuario(db, "ana@example.com")
    ficha = crear_ficha(db, ana, "3000001.pdf")
    _comparacion(db, ana, _planilla(tmp_path / "propia.xlsx", [("1000000102", "MARTA LUCIA GOMEZ RAMIREZ")]), [ficha])

    res = _guardar(db, ficha, "1000000102", "MARTA", "GOMEZ RAMIREZ")
    persona = db.query(Persona).filter(Persona.numero_identificacion == "1000000102").one()
    db.close()

    assert res["nombre_completo"] == "MARTA LUCIA GOMEZ RAMIREZ"
    assert persona.detalles_campos["nombre_completo"]["source"] == "excel_oficial"


# ── Comparación limitada a las fichas de la planilla ────────────────

@requiere_postgres
def test_comparacion_automatica_no_toca_personas_de_otras_fichas(bd, tmp_path):
    from app.services.comparacion_service import comparacion_service

    db = bd.SessionLocal()
    ana = crear_usuario(db, "ana@example.com")
    ficha_a = crear_ficha(db, ana, "3000001.pdf")
    ficha_b = crear_ficha(db, ana, "3000002.pdf")
    crear_persona(db, ana, ficha_a, "1000000201", "JUAN CARLOS", "PEREZ LOPEZ")
    otra = crear_persona(db, ana, ficha_b, "1000000999", "LUISA FERNANDA", "MORA DIAZ")
    # La planilla de la ficha A trae a alguien con el mismo nombre que la persona de la ficha B y otra cédula
    ruta = _planilla(tmp_path / "a.xlsx", [("1000000201", "JUAN CARLOS PEREZ LOPEZ"),
                                           ("1000000888", "LUISA FERNANDA MORA DIAZ")])
    comp = _comparacion(db, ana, ruta, [ficha_a])

    id_ficha_b = ficha_b.id
    comparacion_service.ejecutar_comparacion(str(comp.id), str(ruta), db)
    db.refresh(otra)
    db.refresh(comp)
    cedula, ficha_de_otra, total_bd = otra.numero_identificacion, otra.documento_id, comp.total_registros_bd
    db.close()

    assert cedula == "1000000999"
    assert ficha_de_otra == id_ficha_b
    assert total_bd == 1


@requiere_postgres
def test_planilla_suelta_sigue_comparando_con_todas_las_fichas(bd, tmp_path):
    from app.services.comparacion_service import comparacion_service

    db = bd.SessionLocal()
    ana = crear_usuario(db, "ana@example.com")
    crear_persona(db, ana, crear_ficha(db, ana, "3000001.pdf"), "1000000201", "JUAN CARLOS", "PEREZ LOPEZ")
    crear_persona(db, ana, crear_ficha(db, ana, "3000002.pdf"), "1000000301", "LUISA FERNANDA", "MORA DIAZ")
    ruta = _planilla(tmp_path / "suelta.xlsx", [("1000000201", "JUAN CARLOS PEREZ LOPEZ")])
    comp = _comparacion(db, ana, ruta, None)

    comparacion_service.ejecutar_comparacion(str(comp.id), str(ruta), db)
    db.refresh(comp)
    db.close()

    assert comp.total_registros_bd == 2


# ── Misma cédula leída para dos titulares ───────────────────────────

@requiere_postgres
def test_misma_cedula_con_otro_titular_no_funde_a_dos_personas(bd):
    db = bd.SessionLocal()
    ana = crear_usuario(db, "ana@example.com")
    ficha = crear_ficha(db, ana, "3000001.pdf")

    _guardar(db, ficha, "1000000401", "ANA MARIA", "TORRES SILVA")
    _guardar(db, ficha, "1000000401", "PEDRO LUIS", "CASTRO VEGA")
    personas = db.query(Persona).filter(Persona.documento_id == ficha.id).all()
    db.close()

    assert len(personas) == 2
    ana_maria = next(p for p in personas if "ANA" in p.nombre_completo)
    pedro = next(p for p in personas if "PEDRO" in p.nombre_completo)
    assert ana_maria.numero_identificacion == "1000000401"
    assert pedro.numero_identificacion == ""
    assert pedro.requiere_revision is True
    assert pedro.detalles_campos["numero_identificacion_leido_ocr"] == "1000000401"
    assert any("Cédula repetida" in m for m in pedro.detalles_campos["motivos_revision"])


@requiere_postgres
def test_misma_cedula_y_nombre_parecido_se_unen_como_antes(bd):
    db = bd.SessionLocal()
    ana = crear_usuario(db, "ana@example.com")
    ficha = crear_ficha(db, ana, "3000001.pdf")

    _guardar(db, ficha, "1000000402", "ANA MARIA", "TORRES SILVA")
    _guardar(db, ficha, "1000000402", "ANA", "TORRES SILVA")
    personas = db.query(Persona).filter(Persona.documento_id == ficha.id).all()
    db.close()

    assert len(personas) == 1
    assert personas[0].numero_identificacion == "1000000402"


# ── La subida vincula la planilla con sus fichas ────────────────────

@requiere_postgres
def test_subida_con_planilla_guarda_las_fichas_del_lote(bd, api, tmp_path, monkeypatch):
    import app.routers.documentos as rutas_documentos
    monkeypatch.setattr(rutas_documentos, "_procesar_batch_ocr_y_comparacion", lambda *a, **k: None)

    db = bd.SessionLocal()
    ana = crear_usuario(db, "ana@example.com")
    pdf = pdf_de_prueba(tmp_path / "3000001.pdf")
    xlsx = _planilla(tmp_path / "planilla.xlsx", [("1000000501", "JUAN PEREZ")])

    with open(pdf, "rb") as f_pdf, open(xlsx, "rb") as f_xlsx:
        r = api.post("/api/documentos/upload", headers=cabecera(ana), files=[
            ("files", ("3000001.pdf", f_pdf.read(), "application/pdf")),
            ("excel", ("planilla.xlsx", f_xlsx.read(),
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")),
        ])
    assert r.status_code == 202, r.text
    comp = db.query(Comparacion).filter(Comparacion.id == r.json()["comparacion_id"]).one()
    db.close()

    assert comp.documento_ids == [d["id"] for d in r.json()["documentos"]]


# ── Persona que pasa de un PDF a otro ───────────────────────────────

@requiere_postgres
def test_persona_que_pasa_a_otro_pdf_toma_las_paginas_del_pdf_nuevo(bd):
    """
    La misma ficha subida dos veces (con y sin la carta de portada) corre las páginas.
    La persona se reutiliza (la cédula es única por usuario), pero sus páginas deben ser las del PDF nuevo:
    antes conservaba las del PDF anterior y el visor mostraba la cédula de otra persona.
    """
    db = bd.SessionLocal()
    ana = crear_usuario(db, "ana@example.com")
    con_carta = crear_ficha(db, ana, "3492408 con carta.pdf", paginas=20)
    sin_carta = crear_ficha(db, ana, "3492408.pdf", paginas=19)
    crear_persona(db, ana, con_carta, "1006459309", "ADRIANA ALEJANDRA", "ZAPATA CUELLAR",
                  pagina_frente=2, pagina_reverso=None, detalles_campos={"paginas": [2]})

    _guardar(db, sin_carta, "1006459309", "ADRIANA ALEJANDRA", "ZAPATA CUELLAR")
    p = db.query(Persona).filter(Persona.numero_identificacion == "1006459309").one()
    datos = (p.documento_id, p.pagina_frente, (p.detalles_campos or {}).get("paginas"))
    id_sin_carta = sin_carta.id
    db.close()

    assert datos[0] == id_sin_carta
    assert datos[1] == 1
    assert datos[2] in (None, [1])


# ── Volver a subir una ficha sobre un registro dañado ───────────────

@requiere_postgres
def test_resubir_con_planilla_corrige_el_registro_danado(bd, tmp_path):
    """Si el Excel confirma la nueva lectura, se corrige el registro guardado en vez de separarlo."""
    db = bd.SessionLocal()
    ana = crear_usuario(db, "ana@example.com")
    vieja = crear_ficha(db, ana, "3492408 con carta.pdf")
    nueva = crear_ficha(db, ana, "3492408.pdf")
    crear_persona(db, ana, vieja, "1077847851", "LUIS ANGEL", "LOZADA OLAYA")
    _comparacion(db, ana, _planilla(tmp_path / "p.xlsx", [("1077847851", "MAYRA YERITZA TOQUICA CASALLAS")]), [nueva])

    _guardar(db, nueva, "1077847851", "MAYRA YERITZA", "TOQUICA CASALLAS")
    personas = [(p.numero_identificacion, p.nombre_completo, p.documento_id) for p in db.query(Persona).all()]
    id_nueva = nueva.id
    db.close()

    assert personas == [("1077847851", "MAYRA YERITZA TOQUICA CASALLAS", id_nueva)]


@requiere_postgres
def test_resubir_sin_planilla_no_decide_cual_nombre_es_el_correcto(bd):
    """Sin Excel no se sabe cuál lectura es la buena: se conservan las dos y la nueva queda para revisión."""
    db = bd.SessionLocal()
    ana = crear_usuario(db, "ana@example.com")
    vieja = crear_ficha(db, ana, "3492408 con carta.pdf")
    nueva = crear_ficha(db, ana, "3492408.pdf")
    crear_persona(db, ana, vieja, "1077847851", "LUIS ANGEL", "LOZADA OLAYA")

    _guardar(db, nueva, "1077847851", "MAYRA YERITZA", "TOQUICA CASALLAS")
    personas = {p.nombre_completo: (p.numero_identificacion, p.requiere_revision) for p in db.query(Persona).all()}
    db.close()

    assert personas["LUIS ANGEL LOZADA OLAYA"][0] == "1077847851"
    assert personas["MAYRA YERITZA TOQUICA CASALLAS"] == ("", True)


# ── Volver a subir: reescribe sin duplicar ──────────────────────────

def _guardar_datos(db, ficha, **datos):
    from app.services.ocr_service import ocr_service
    base = {"confianza_extraccion": 95.0, "tipo_documento": "CEDULA_CIUDADANIA", "pagina_frente": 1, "grupo_documento_id": "G-1"}
    return ocr_service._guardar_persona(datos=dict(base, **datos), texto_ocr="", documento_id=str(ficha.id), db=db,
                                        ocr_engine="google_document_ai", pagina_num=datos.get("pagina_frente", 1))


@requiere_postgres
def test_volver_a_subir_reescribe_los_datos_y_conserva_lo_corregido_a_mano(bd):
    from datetime import date
    db = bd.SessionLocal()
    ana = crear_usuario(db, "ana@example.com")
    vieja = crear_ficha(db, ana, "3492408.pdf")
    nueva = crear_ficha(db, ana, "3492408 (2).pdf")
    crear_persona(db, ana, vieja, "1006459309", "ADRIANA", "ZAPATA", nombre_completo="ADRIANA ZAPATA C",
                  fecha_nacimiento=date(1999, 1, 1), lugar_expedicion="BOGOTA",
                  sexo="F", campos_revisados=["sexo"])

    _guardar_datos(db, nueva, identificacion="1006459309", nombres="ADRIANA ALEJANDRA", apellidos="ZAPATA CUELLAR",
                   nombre_completo="ADRIANA ALEJANDRA ZAPATA CUELLAR", fecha_nacimiento="2001-02-22",
                   lugar_expedicion="EL DONCELLO", sexo="M", pagina_frente=3)
    personas = db.query(Persona).all()
    p = personas[0]
    datos = (len(personas), p.documento_id, p.nombre_completo, p.fecha_nacimiento, p.lugar_expedicion, p.sexo, p.pagina_frente)
    id_nueva = nueva.id
    db.close()

    assert datos == (1, id_nueva, "ADRIANA ALEJANDRA ZAPATA CUELLAR", date(2001, 2, 22), "EL DONCELLO", "F", 3)


@requiere_postgres
def test_volver_a_subir_no_duplica_a_las_personas_sin_cedula(bd):
    db = bd.SessionLocal()
    ana = crear_usuario(db, "ana@example.com")
    vieja = crear_ficha(db, ana, "3492408.pdf")
    nueva = crear_ficha(db, ana, "3492408 (2).pdf")
    for ficha in (vieja, nueva):
        _guardar_datos(db, ficha, identificacion=None, nombres="LUISA FERNANDA", apellidos="MORA DIAZ",
                       nombre_completo="LUISA FERNANDA MORA DIAZ")
    personas = [(p.numero_identificacion, p.documento_id) for p in db.query(Persona).all()]
    id_nueva = nueva.id
    db.close()

    assert personas == [("", id_nueva)]
