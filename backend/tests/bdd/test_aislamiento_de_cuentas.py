"""Pasos de aislamiento_de_cuentas.feature"""
from pytest_bdd import given, parsers, scenarios, then, when

from app.models.comparacion import Comparacion
from app.models.diferencia import Diferencia
from tests.utilidades_pg import (
    cabecera, crear_ficha, crear_persona, crear_usuario, pdf_de_prueba, requiere_postgres,
)

pytestmark = requiere_postgres
scenarios("aislamiento_de_cuentas.feature")


def _usuario_por_correo(bd, correo):
    from app.models.usuario import Usuario
    db = bd.SessionLocal()
    try:
        return db.query(Usuario).filter(Usuario.email == correo).one()
    finally:
        db.close()


@given(parsers.parse('que la operadora "{correo}" tiene una ficha con la persona de cédula "{cedula}"'))
def ficha_de_ana(bd, contexto, tmp_path, correo, cedula):
    db = bd.SessionLocal()
    ana = crear_usuario(db, correo)
    ficha = crear_ficha(db, ana, ruta_archivo=str(pdf_de_prueba(tmp_path / "ficha.pdf")))
    persona = crear_persona(db, ana, ficha, cedula, "ANGELA", "MORA", pagina_frente=1, pagina_reverso=2)
    contexto.update(ana_id=ana.id, ficha_id=ficha.id, persona_id=persona.id, cedula=cedula)
    db.close()


@given("tiene una comparación con diferencias")
def comparacion_de_ana(bd, contexto):
    db = bd.SessionLocal()
    comp = Comparacion(usuario_id=contexto["ana_id"], nombre_archivo="p.xlsx", nombre_original="p.xlsx",
                       estado="completado")
    db.add(comp)
    db.commit()
    db.add(Diferencia(comparacion_id=comp.id, numero_identificacion=contexto["cedula"], campo="nombres",
                      valor_bd="ANGELA", valor_excel="ANGELA MARIA", tipo_diferencia="diferente"))
    db.commit()
    contexto["comparacion_id"] = comp.id
    db.close()


@given(parsers.parse('existe otro operador "{correo}"'))
def otro_operador(bd, correo):
    db = bd.SessionLocal()
    crear_usuario(db, correo)
    db.close()


@when(parsers.parse('"{correo}" pide el reporte de diferencias de Ana'))
def pide_reporte(api, bd, contexto, correo):
    contexto["respuesta"] = api.get(f"/api/exportacion/diferencias/{contexto['comparacion_id']}",
                                    headers=cabecera(_usuario_por_correo(bd, correo)))


@when(parsers.parse('"{correo}" pide la página 1 de la ficha de Ana'))
def pide_pagina(api, bd, contexto, correo):
    contexto["respuesta"] = api.get(f"/api/documentos/{contexto['ficha_id']}/pagina/1", params={"dpi": 130},
                                    headers=cabecera(_usuario_por_correo(bd, correo)))


@when(parsers.parse('"{correo}" busca la cédula "{cedula}"'))
def busca_cedula(api, bd, contexto, correo, cedula):
    contexto["respuesta"] = api.get(f"/api/personas/buscar/cedula/{cedula}",
                                    headers=cabecera(_usuario_por_correo(bd, correo)))


@when(parsers.parse('"{correo}" intenta cambiar el nombre de la persona de Ana'))
def edita_persona(api, bd, contexto, correo):
    contexto["respuesta"] = api.put(f"/api/personas/{contexto['persona_id']}", json={"nombres": "CAMBIADO"},
                                    headers=cabecera(_usuario_por_correo(bd, correo)))


@then("recibe un archivo de Excel")
def recibe_excel(contexto):
    r = contexto["respuesta"]
    assert r.status_code == 200
    assert r.content[:2] == b"PK"
