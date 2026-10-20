"""Pasos de inicio_sesion.feature"""
from pytest_bdd import given, parsers, scenarios, then, when

from tests.utilidades_pg import crear_usuario, requiere_postgres

pytestmark = requiere_postgres
scenarios("inicio_sesion.feature")


@given(parsers.parse('que existe el usuario "{correo}" con la contraseña "{clave}"'))
def existe_el_usuario(bd, correo, clave):
    db = bd.SessionLocal()
    crear_usuario(db, correo, clave=clave)
    db.close()


@given(parsers.parse('que alguien intentó entrar 5 veces a "{correo}" con contraseñas equivocadas'))
def cinco_intentos_fallidos(api, correo):
    for i in range(5):
        assert api.post("/api/auth/login", json={"email": correo, "password": f"mala-{i}"}).status_code == 401


@when(parsers.parse('inicia sesión con "{correo}" y "{clave}"'))
def inicia_sesion(api, contexto, correo, clave):
    contexto["respuesta"] = api.post("/api/auth/login", json={"email": correo, "password": clave})


@then("entra al sistema")
def entra(api, contexto):
    r = contexto["respuesta"]
    assert r.status_code == 200
    token = r.json()["access_token"]
    assert api.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 200


@then("no entra al sistema")
def no_entra(contexto):
    assert contexto["respuesta"].status_code in (401, 422)


@then(parsers.parse('el sistema responde "{mensaje}"'))
def responde(contexto, mensaje):
    assert contexto["respuesta"].status_code == 401
    assert contexto["respuesta"].json()["detail"] == mensaje


@then("el sistema pide esperar antes de intentar de nuevo")
def pide_esperar(contexto):
    r = contexto["respuesta"]
    assert r.status_code == 429
    assert int(r.headers["retry-after"]) > 0
    assert "Espera" in r.json()["detail"]
