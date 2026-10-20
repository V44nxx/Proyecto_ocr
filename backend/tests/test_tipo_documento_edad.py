"""
Al editar a mano el tipo de documento: la Tarjeta de Identidad es solo para menores de 18 años
y la Cédula de Ciudadanía solo para mayores. Si el cambio no cuadra con la edad, no se guarda.
"""
from datetime import date, timedelta

import pytest
from fastapi import HTTPException

from app.models.persona import Persona
from app.routers.personas import _aviso_cambio_tipo_documento, actualizar_persona
from app.schemas.documento import PersonaUpdate
from tests.test_regresiones_2_2_1 import _ficha, _persona, _usuario
from tests.utilidades_pg import requiere_postgres


def _cumple(anios: int) -> date:
    """Fecha de nacimiento de alguien que cumple `anios` hoy."""
    hoy = date.today()
    try:
        return hoy.replace(year=hoy.year - anios)
    except ValueError:  # 29 de febrero
        return hoy.replace(year=hoy.year - anios, day=28)


@pytest.mark.parametrize("tipo, nacimiento, bloquea", [
    ("TARJETA_IDENTIDAD", _cumple(25), True),
    ("TARJETA_IDENTIDAD", _cumple(18), True),                       # cumple 18 hoy: ya es mayor
    ("TARJETA_IDENTIDAD", _cumple(18) + timedelta(days=1), False),  # le falta un día
    ("TARJETA_IDENTIDAD", _cumple(15), False),
    ("TI", _cumple(30), True),
    ("CEDULA_CIUDADANIA", _cumple(15), True),
    ("CEDULA_CIUDADANIA", _cumple(18) + timedelta(days=1), True),
    ("CEDULA_CIUDADANIA", _cumple(18), False),
    ("CC", _cumple(10), True),
    ("CEDULA_EXTRANJERIA", _cumple(15), False),
    ("CONTRASEÑA", _cumple(15), False),
    ("PPT", _cumple(15), False),
    ("PASAPORTE", _cumple(15), False),
    ("TARJETA_IDENTIDAD", None, False),                             # sin fecha no se puede saber
])
def test_aviso_cambio_tipo_documento(tipo, nacimiento, bloquea):
    aviso = _aviso_cambio_tipo_documento(tipo, nacimiento)
    assert (aviso is not None) == bloquea
    if aviso:
        assert "años" in aviso


def test_aviso_dice_la_edad_y_el_motivo():
    assert _aviso_cambio_tipo_documento("TARJETA_IDENTIDAD", _cumple(25)) == (
        "No se puede cambiar a Tarjeta de Identidad: la persona tiene 25 años "
        "y la tarjeta de identidad es solo para menores de 18 años."
    )
    assert _aviso_cambio_tipo_documento("CEDULA_CIUDADANIA", _cumple(15)) == (
        "No se puede cambiar a Cédula de Ciudadanía: la persona tiene 15 años "
        "y la cédula de ciudadanía es solo para mayores de 18 años."
    )


def _preparar(bd, tipo, nacimiento, **extra):
    db = bd.SessionLocal()
    u = _usuario(db, "a@example.com")
    p = _persona(db, u, _ficha(db, u, "3400001.pdf", 2), "1000000801", "ANA", "PEREZ",
                 tipo_documento=tipo, fecha_nacimiento=nacimiento, **extra)
    return db, u, p.id


@requiere_postgres
def test_no_deja_cambiar_a_tarjeta_a_un_mayor_de_edad(bd):
    db, u, pid = _preparar(bd, "CEDULA_CIUDADANIA", _cumple(25))
    with pytest.raises(HTTPException) as exc:
        actualizar_persona(str(pid), PersonaUpdate(tipo_documento="TARJETA_IDENTIDAD", nombre_completo="ANA MARIA PEREZ"),
                           db, u)
    assert exc.value.status_code == 400
    assert "25 años" in exc.value.detail
    db.close()

    db = bd.SessionLocal()
    p = db.get(Persona, pid)
    assert p.tipo_documento == "CEDULA_CIUDADANIA"
    assert p.nombre_completo == "ANA PEREZ"  # no se guarda nada del cambio rechazado
    db.close()


@requiere_postgres
def test_no_deja_cambiar_a_cedula_a_un_menor_de_edad(bd):
    db, u, pid = _preparar(bd, "TARJETA_IDENTIDAD", _cumple(15))
    with pytest.raises(HTTPException) as exc:
        actualizar_persona(str(pid), PersonaUpdate(tipo_documento="CEDULA_CIUDADANIA"), db, u)
    assert exc.value.status_code == 400
    assert "15 años" in exc.value.detail
    db.close()


@requiere_postgres
def test_cambio_valido_se_guarda_tambien_en_el_detalle(bd):
    db, u, pid = _preparar(bd, "CEDULA_CIUDADANIA", _cumple(15),
                           detalles_campos={"tipo_documento": {"valor": "CEDULA_CIUDADANIA", "confianza": 90}})
    actualizar_persona(str(pid), PersonaUpdate(tipo_documento="TARJETA_IDENTIDAD"), db, u)
    db.close()

    db = bd.SessionLocal()
    p = db.get(Persona, pid)
    assert p.tipo_documento == "TARJETA_IDENTIDAD"
    assert p.detalles_campos["tipo_documento"]["valor"] == "TARJETA_IDENTIDAD"
    assert p.detalles_campos["tipo_documento"]["corregido_manual"] is True
    assert "tipo_documento" in p.campos_revisados
    db.close()


@requiere_postgres
def test_usa_la_fecha_de_nacimiento_editada_en_el_mismo_cambio(bd):
    db, u, pid = _preparar(bd, "CEDULA_CIUDADANIA", _cumple(25))
    actualizar_persona(str(pid), PersonaUpdate(tipo_documento="TARJETA_IDENTIDAD", fecha_nacimiento=_cumple(12)), db, u)
    db.close()

    db = bd.SessionLocal()
    assert db.get(Persona, pid).tipo_documento == "TARJETA_IDENTIDAD"
    db.close()


@requiere_postgres
def test_solo_valida_cuando_cambia_el_tipo(bd):
    # Una persona que ya llegó con tarjeta siendo mayor (la marca el OCR) se puede seguir editando
    db, u, pid = _preparar(bd, "TARJETA_IDENTIDAD", _cumple(25))
    actualizar_persona(str(pid), PersonaUpdate(tipo_documento="TARJETA_IDENTIDAD", nombre_completo="ANA MARIA PEREZ"),
                       db, u)
    db.close()

    db = bd.SessionLocal()
    p = db.get(Persona, pid)
    assert p.nombre_completo == "ANA MARIA PEREZ"
    assert p.tipo_documento == "TARJETA_IDENTIDAD"
    db.close()
