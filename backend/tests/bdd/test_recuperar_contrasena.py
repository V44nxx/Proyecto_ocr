"""Pasos de recuperar_contrasena.feature"""
import re

from pytest_bdd import given, parsers, scenarios, then, when

from app.config import settings
from tests.utilidades_pg import crear_usuario, requiere_postgres

pytestmark = requiere_postgres
scenarios("recuperar_contrasena.feature")


def _login(api, correo, clave):
    return api.post("/api/auth/login", json={"email": correo, "password": clave})


def _pedir_enlace(api, contexto, correo):
    contexto["correos_antes"] = len(contexto["enviados"])
    contexto["respuesta"] = api.post("/api/auth/olvide-password", json={"email": correo})
    contexto["correos_despues"] = len(contexto["enviados"])


def _token_del_ultimo_correo(contexto):
    enlace = re.search(r"https://kondid\.example\.com/restablecer-contrasena\?token=([\w-]+)",
                       contexto["enviados"][-1]["texto"])
    assert enlace, contexto["enviados"][-1]["texto"]
    return enlace.group(1)


def _restablecer(api, contexto, clave):
    contexto["respuesta"] = api.post("/api/auth/restablecer-password",
                                     json={"token": contexto["token"], "password_nueva": clave})


# ── Antecedentes ────────────────────────────────────────────────────

@given(parsers.parse('que existe la usuaria "{correo}" con la contraseña "{clave}"'))
def existe_la_usuaria(bd, contexto, correo, clave):
    db = bd.SessionLocal()
    crear_usuario(db, correo, clave=clave)
    db.close()
    contexto.update(correo=correo, clave_vieja=clave)


@given("el envío de correos está configurado")
def correo_configurado(monkeypatch, contexto):
    from app.services import correo_service
    enviados = []
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(settings, "SMTP_USER", "kondid@example.com")
    monkeypatch.setattr(settings, "FRONTEND_URL", "https://kondid.example.com")
    monkeypatch.setattr(correo_service, "enviar_correo",
                        lambda destinatario, asunto, texto, html: enviados.append(
                            {"para": destinatario, "asunto": asunto, "texto": texto}) or True)
    contexto["enviados"] = enviados


# ── Dado ────────────────────────────────────────────────────────────

@given("que la usuaria tiene una sesión abierta con la contraseña vieja")
def sesion_abierta(api, contexto):
    r = _login(api, contexto["correo"], contexto["clave_vieja"])
    assert r.status_code == 200
    contexto["sesion_vieja"] = r.json()["access_token"]


@given("que la usuaria pidió un enlace de recuperación")
def pidio_un_enlace(api, contexto):
    _pedir_enlace(api, contexto, contexto["correo"])
    contexto["token"] = _token_del_ultimo_correo(contexto)


@given("que la usuaria ya cambió la contraseña con un enlace")
def ya_uso_el_enlace(api, contexto):
    pidio_un_enlace(api, contexto)
    _restablecer(api, contexto, "Primera-Clave-Nueva-1")
    assert contexto["respuesta"].status_code == 200


# ── Cuando ──────────────────────────────────────────────────────────

@when(parsers.parse('pide un enlace de recuperación para "{correo}"'))
def pide_un_enlace(api, contexto, correo):
    _pedir_enlace(api, contexto, correo)


@when(parsers.parse('abre el enlace y escribe la contraseña nueva "{clave}"'))
def usa_el_enlace(api, contexto, clave):
    _restablecer(api, contexto, clave)


@when(parsers.parse('abre el mismo enlace y escribe la contraseña nueva "{clave}"'))
def usa_el_mismo_enlace(api, contexto, clave):
    _restablecer(api, contexto, clave)


# ── Entonces ────────────────────────────────────────────────────────

@then("recibe un correo con un enlace para restablecer la contraseña")
def recibe_el_correo(contexto):
    assert contexto["respuesta"].status_code == 200
    assert [c["para"] for c in contexto["enviados"]] == [contexto["correo"]]
    contexto["token"] = _token_del_ultimo_correo(contexto)


@then(parsers.parse('puede entrar con la contraseña "{clave}"'))
def puede_entrar(api, contexto, clave):
    assert _login(api, contexto["correo"], clave).status_code == 200


@then(parsers.parse('ya no puede entrar con la contraseña "{clave}"'))
def ya_no_puede_entrar(api, contexto, clave):
    assert _login(api, contexto["correo"], clave).status_code == 401


@then("la sesión que tenía abierta se cierra")
def sesion_cerrada(api, contexto):
    r = api.get("/api/auth/me", headers={"Authorization": f"Bearer {contexto['sesion_vieja']}"})
    assert r.status_code == 401


@then("el sistema responde que el enlace no es válido o ya venció")
def enlace_invalido(contexto):
    r = contexto["respuesta"]
    assert r.status_code == 400
    assert "no es válido o ya venció" in r.json()["detail"]


@then("la respuesta es la misma que para un correo registrado")
def misma_respuesta(api, contexto):
    otra = api.post("/api/auth/olvide-password", json={"email": contexto["correo"]})
    assert (contexto["respuesta"].status_code, contexto["respuesta"].json()) == (otra.status_code, otra.json())


@then("no se envía ningún correo")
def ningun_correo(contexto):
    assert contexto["correos_despues"] == contexto["correos_antes"]


@then("el sistema rechaza la contraseña por ser muy común")
def rechaza_contrasena_comun(contexto):
    r = contexto["respuesta"]
    assert r.status_code == 422
    assert "muy común" in r.text
