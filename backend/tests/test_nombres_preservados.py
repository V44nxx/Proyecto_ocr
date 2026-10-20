"""
El limpiador de nombres no debe recortar ni borrar nombres reales, y debe seguir quitando el ruido del OCR.
"""
import pytest

from app.utils.name_cleaner import limpiar_tokens_ruido, remover_letras_residuales_fin_palabra


@pytest.mark.parametrize("nombre", [
    "ANGELA", "MANUELA", "JULIANA", "ISABELA", "RAFAELA", "MIGUELA", "MARTINA", "GABRIELA", "DANIELA",
    "ROMERO", "INDIRA", "ANGELA MARIA ROMERO", "JULIANA ISABELA PEREZ", "GEIDY DAYANA ROJAS TARAZONA",
])
def test_no_recorta_ni_borra_nombres_reales(nombre):
    assert limpiar_tokens_ruido(nombre) == nombre


@pytest.mark.parametrize("ruido, esperado", [
    ("LOSADAM", "LOSADA"),
    ("GOMEZM", "GOMEZ"),
    ("PEREZF", "PEREZ"),
])
def test_sigue_quitando_la_letra_del_sexo_pegada(ruido, esperado):
    assert remover_letras_residuales_fin_palabra(ruido) == esperado


def test_sigue_descartando_encabezados_deformados():
    assert limpiar_tokens_ruido("NUMERO CEDULA TFTOLIB") == ""


# ── Reparación de nombres dañados por el limpiador anterior ─────────

from datetime import date  # noqa: E402

import pandas as pd  # noqa: E402

from app.models.comparacion import Comparacion  # noqa: E402
from app.models.persona import Persona  # noqa: E402
from app.utils.nombres_recortados import nombre_recuperado, sospecha_de_recorte  # noqa: E402
from tests.test_regresiones_2_2_1 import _ficha, _persona, _usuario  # noqa: E402
from tests.utilidades_pg import requiere_postgres  # noqa: E402


@pytest.mark.parametrize("actual, oficial, esperado", [
    ("ANGEL MARIA", "ANGELA MARIA ROMERO", "ANGELA MARIA ROMERO"),
    ("JULIAN PEREZ", "JULIANA PEREZ", "JULIANA PEREZ"),
    ("MANUEL ROJAS", "MANUELA INDIRA ROJAS", "MANUELA INDIRA ROJAS"),
    ("JULIANA PEREZ", "JULIANA PEREZ", None),               # nada que recuperar
    ("JUAN PEREZ", "JUAN CARLOS PEREZ", None),              # diferencia que no es del error
    ("PEDRO GOMEZ", "ANGELA MARIA ROMERO", None),           # otra persona
    ("PEREZ JULIAN", "JULIANA PEREZ", None),                # otro orden: no se adivina
])
def test_nombre_recuperado_solo_repara_el_dano_del_limpiador(actual, oficial, esperado):
    assert nombre_recuperado(actual, oficial) == esperado


@pytest.mark.parametrize("nombre, sexo, esperado", [
    ("JULIAN ANDREA PEREZ", "F", "JULIAN"),
    ("ANGEL MARIA ROJAS", "FEMENINO", "ANGEL"),
    ("JULIAN PEREZ", "M", None),
    ("JULIAN PEREZ", None, None),
    ("GABRIELA PEREZ", "F", None),
])
def test_sospecha_de_recorte(nombre, sexo, esperado):
    assert sospecha_de_recorte(nombre, sexo) == esperado


@requiere_postgres
def test_arranque_repara_nombres_recortados(bd, tmp_path):
    db = bd.SessionLocal()
    u = _usuario(db, "a@example.com")
    f = _ficha(db, u, "3300001.pdf", 6)
    con_excel = _persona(db, u, f, "1000000701", "ANGEL MARIA", None, nombre_completo="ANGEL MARIA", sexo="F",
                         fecha_nacimiento=date(1990, 1, 1))
    sin_excel = _persona(db, u, f, "1000000702", "JULIAN", "PEREZ", sexo="F", fecha_nacimiento=date(1990, 1, 1))
    hombre = _persona(db, u, f, "1000000703", "JULIAN", "PEREZ", sexo="M", fecha_nacimiento=date(1990, 1, 1))
    excel = tmp_path / "planilla.xlsx"
    pd.DataFrame([{"Cedula": "1000000701", "Nombre completo": "ANGELA MARIA ROMERO"}]).to_excel(excel, index=False)
    db.add(Comparacion(usuario_id=u.id, nombre_archivo="p.xlsx", nombre_original="p.xlsx", ruta_archivo=str(excel),
                       estado="completado"))
    db.commit()
    ids = (con_excel.id, sin_excel.id, hombre.id)
    db.close()

    bd.create_tables()
    bd.create_tables()  # una segunda vez no cambia nada más

    db = bd.SessionLocal()
    recuperada, marcada, intacto = (db.get(Persona, i) for i in ids)
    assert recuperada.nombre_completo == "ANGELA MARIA ROMERO"
    assert marcada.nombre_completo == "JULIAN PEREZ"
    assert marcada.requiere_revision is True
    assert any("JULIANA" in m for m in marcada.detalles_campos["motivos_revision"])
    assert intacto.nombre_completo == "JULIAN PEREZ"
    assert "posible_nombre_recortado" not in intacto.detalles_campos

    # Al aprobarla, la marca se quita y no vuelve en el siguiente arranque
    det = dict(marcada.detalles_campos)
    det["aprobado_manual"] = True
    marcada.detalles_campos = det
    db.commit()
    db.close()
    bd.create_tables()
    db = bd.SessionLocal()
    assert "posible_nombre_recortado" not in db.get(Persona, ids[1]).detalles_campos
    db.close()


@requiere_postgres
def test_marca_guarda_el_motivo_aunque_sea_la_unica_persona(bd):
    db = bd.SessionLocal()
    u = _usuario(db, "b@example.com")
    p = _persona(db, u, _ficha(db, u, "3300002.pdf", 2), "1000000704", "JULIAN ANDREA", "PEREZ", sexo="F",
                 fecha_nacimiento=date(1995, 3, 3))
    pid = p.id
    db.close()

    bd.create_tables()

    db = bd.SessionLocal()
    persona = db.get(Persona, pid)
    assert persona.requiere_revision is True
    assert any("JULIANA" in m for m in persona.detalles_campos["motivos_revision"])
    db.close()
