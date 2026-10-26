"""
Verificación en dos pasos (TOTP) para los administradores (versión 2.12.0).

Un administrador entra con su contraseña y después con un código de 6 dígitos de su app de autenticación.
La primera vez escanea un QR y recibe 10 códigos de respaldo de un solo uso.
Las pruebas marcadas con `requiere_postgres` necesitan TEST_DATABASE_URL.
"""
import time
import uuid

import jwt
import pyotp
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from tests.utilidades_pg import CLAVE_PRUEBA, cabecera, crear_usuario, requiere_postgres

ADMIN = "admin@example.com"


# ── Utilidades del módulo ───────────────────────────────────────────

def test_el_secreto_se_guarda_cifrado():
    from app.utils.doble_factor import cifrar_secreto, descifrar_secreto, generar_secreto
    secreto = generar_secreto()
    cifrado = cifrar_secreto(secreto)
    assert secreto not in cifrado
    assert descifrar_secreto(cifrado) == secreto
    assert descifrar_secreto("no-es-un-cifrado") is None
    assert descifrar_secreto(None) is None


def test_un_codigo_vale_una_sola_vez_y_solo_cerca_de_su_momento():
    from app.utils.doble_factor import generar_secreto, paso_valido
    secreto = generar_secreto()
    totp = pyotp.TOTP(secreto)
    ahora = 1_800_000_000
    paso = ahora // 30
    assert paso_valido(secreto, totp.at(ahora), None, ahora) == paso
    assert paso_valido(secreto, totp.at(ahora - 30), None, ahora) == paso - 1      # el anterior, por desfase del reloj
    assert paso_valido(secreto, totp.at(ahora), paso, ahora) is None               # ya usado
    assert paso_valido(secreto, totp.at(ahora - 30), paso, ahora) is None          # uno más viejo que el último usado
    assert paso_valido(secreto, totp.at(ahora - 90), None, ahora) is None          # vencido
    assert paso_valido(secreto, " 12 34 5x ", None, ahora) is None
    assert paso_valido(secreto, "", None, ahora) is None


def test_codigos_de_respaldo_unicos_guardados_como_hash_y_de_un_solo_uso():
    from app.utils.doble_factor import generar_codigos_respaldo, usar_codigo_respaldo
    planos, hashes = generar_codigos_respaldo()
    assert len(planos) == len(set(planos)) == len(hashes) == 10
    assert all(len(c) == 11 and c[5] == "-" for c in planos)
    assert not any(c in h or c.replace("-", "") in h for c in planos for h in hashes)

    restantes = usar_codigo_respaldo(hashes, planos[3].lower().replace("-", " "))
    assert restantes is not None and len(restantes) == 9
    assert usar_codigo_respaldo(restantes, planos[3]) is None
    assert usar_codigo_respaldo(hashes, "AAAAA-AAAAA") is None
    assert usar_codigo_respaldo(None, planos[0]) is None


def test_el_desafio_no_sirve_como_sesion():
    from app.utils.doble_factor import crear_desafio
    usuario = type("U", (), {"id": uuid.uuid4(), "version_sesion": 0})()
    desafio = crear_desafio(usuario, configurar=False)
    with pytest.raises(jwt.InvalidTokenError):
        jwt.decode(desafio, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    cliente = TestClient(app, raise_server_exceptions=False)
    assert cliente.get("/api/auth/me", headers={"Authorization": f"Bearer {desafio}"}).status_code == 401


def test_el_desafio_vence():
    from app.utils.doble_factor import DESAFIO_MINUTOS, crear_desafio, leer_desafio
    usuario = type("U", (), {"id": uuid.uuid4(), "version_sesion": 0})()
    vigente = crear_desafio(usuario, configurar=True)
    vencido = crear_desafio(usuario, configurar=True, ahora=time.time() - DESAFIO_MINUTOS * 60 - 1)
    assert leer_desafio(vigente)["sub"] == str(usuario.id)
    assert leer_desafio(vencido) is None
    assert leer_desafio("basura") is None


# ── Flujo completo (PostgreSQL) ─────────────────────────────────────

def _login(api, email=ADMIN, clave=CLAVE_PRUEBA):
    return api.post("/api/auth/login", json={"email": email, "password": clave})


def _activar(api, email=ADMIN):
    """Primer ingreso del administrador: contraseña, QR y código. Devuelve (secreto, respuesta de activar)."""
    desafio = _login(api, email).json()["desafio"]
    secreto = api.post("/api/auth/login/2fa/configurar", json={"desafio": desafio}).json()["secreto"]
    r = api.post("/api/auth/login/2fa/activar", json={"desafio": desafio, "codigo": pyotp.TOTP(secreto).now()})
    return secreto, r


def _codigo_siguiente(secreto):
    # El del siguiente paso de 30 s: el actual ya se usó al activar (y el servidor acepta uno de desfase)
    return pyotp.TOTP(secreto).at(time.time() + 30)


@requiere_postgres
def test_el_administrador_no_recibe_sesion_solo_con_la_contrasena(bd, api):
    db = bd.SessionLocal()
    crear_usuario(db, ADMIN, rol="admin", clave=CLAVE_PRUEBA)
    db.close()
    r = _login(api)
    datos = r.json()
    assert r.status_code == 200
    assert datos["requiere_2fa"] is True and datos["configurar_2fa"] is True and datos["desafio"]
    assert not datos.get("access_token") and not datos.get("usuario")
    assert settings.nombre_cookie_sesion not in r.cookies


@requiere_postgres
def test_un_usuario_normal_entra_igual_que_antes(bd, api):
    db = bd.SessionLocal()
    crear_usuario(db, "ana@example.com", clave=CLAVE_PRUEBA)
    db.close()
    r = _login(api, "ana@example.com")
    assert r.status_code == 200 and r.json()["access_token"] and not r.json()["requiere_2fa"]
    assert settings.nombre_cookie_sesion in r.cookies


@requiere_postgres
def test_activar_con_el_qr_da_sesion_y_codigos_de_respaldo(bd, api):
    from app.models.usuario import Usuario
    db = bd.SessionLocal()
    crear_usuario(db, ADMIN, rol="admin", clave=CLAVE_PRUEBA)
    desafio = _login(api).json()["desafio"]
    config = api.post("/api/auth/login/2fa/configurar", json={"desafio": desafio}).json()
    assert config["uri"].startswith("otpauth://totp/KondID:") and f"secret={config['secreto']}" in config["uri"]
    assert config["qr"].startswith("data:image/svg+xml")

    malo = api.post("/api/auth/login/2fa/activar", json={"desafio": desafio, "codigo": "000000"})
    r = api.post("/api/auth/login/2fa/activar", json={"desafio": desafio, "codigo": pyotp.TOTP(config["secreto"]).now()})
    u = db.query(Usuario).filter(Usuario.email == ADMIN).one()
    db.close()

    assert malo.status_code == 400
    assert r.status_code == 200 and r.json()["access_token"] and len(r.json()["codigos_respaldo"]) == 10
    assert r.json()["usuario"]["doble_factor_activo"] is True
    assert settings.nombre_cookie_sesion in r.cookies
    assert u.totp_activo and config["secreto"] not in (u.totp_secreto or "")
    assert api.get("/api/auth/me", headers={"Authorization": f"Bearer {r.json()['access_token']}"}).status_code == 200


@requiere_postgres
def test_con_la_verificacion_activa_no_se_puede_volver_a_configurar_solo_con_la_contrasena(bd, api):
    db = bd.SessionLocal()
    crear_usuario(db, ADMIN, rol="admin", clave=CLAVE_PRUEBA)
    db.close()
    _activar(api)
    datos = _login(api).json()
    assert datos["requiere_2fa"] is True and datos["configurar_2fa"] is False
    r = api.post("/api/auth/login/2fa/configurar", json={"desafio": datos["desafio"]})
    assert r.status_code == 409


@requiere_postgres
def test_segundo_ingreso_con_codigo_y_el_mismo_codigo_no_sirve_dos_veces(bd, api):
    db = bd.SessionLocal()
    crear_usuario(db, ADMIN, rol="admin", clave=CLAVE_PRUEBA)
    db.close()
    secreto, _ = _activar(api)
    codigo = _codigo_siguiente(secreto)

    primero = api.post("/api/auth/login/2fa", json={"desafio": _login(api).json()["desafio"], "codigo": codigo})
    repetido = api.post("/api/auth/login/2fa", json={"desafio": _login(api).json()["desafio"], "codigo": codigo})

    assert primero.status_code == 200 and primero.json()["access_token"]
    assert settings.nombre_cookie_sesion in primero.cookies
    assert repetido.status_code == 400


@requiere_postgres
def test_un_codigo_de_respaldo_sirve_una_vez(bd, api):
    db = bd.SessionLocal()
    crear_usuario(db, ADMIN, rol="admin", clave=CLAVE_PRUEBA)
    db.close()
    _, activacion = _activar(api)
    respaldo = activacion.json()["codigos_respaldo"][0]

    r = api.post("/api/auth/login/2fa", json={"desafio": _login(api).json()["desafio"], "codigo": respaldo})
    otra_vez = api.post("/api/auth/login/2fa", json={"desafio": _login(api).json()["desafio"], "codigo": respaldo})

    assert r.status_code == 200 and r.json()["codigos_respaldo_restantes"] == 9
    assert otra_vez.status_code == 400


@requiere_postgres
def test_cinco_codigos_equivocados_bloquean_la_verificacion(bd, api, auditoria_registrada):
    db = bd.SessionLocal()
    crear_usuario(db, ADMIN, rol="admin", clave=CLAVE_PRUEBA)
    db.close()
    secreto, _ = _activar(api)
    desafio = _login(api).json()["desafio"]
    estados = [api.post("/api/auth/login/2fa", json={"desafio": desafio, "codigo": "000000"}).status_code
               for _ in range(5)]
    correcto = api.post("/api/auth/login/2fa", json={"desafio": desafio, "codigo": _codigo_siguiente(secreto)})
    auditoria = api.get("/api/auth/auditoria", params={"accion": "2fa_fallido"},
                        headers=cabecera(_admin(bd))).json()

    assert estados == [400] * 5
    assert correcto.status_code == 429 and correcto.headers.get("Retry-After")
    assert auditoria["total"] == 5


def _admin(bd):
    from app.models.usuario import Usuario
    db = bd.SessionLocal()
    u = db.query(Usuario).filter(Usuario.email == ADMIN).one()
    db.expunge(u)
    db.close()
    return u


@requiere_postgres
def test_una_sesion_de_administrador_sin_segundo_paso_ya_no_sirve(bd, api):
    """Las sesiones de administrador abiertas antes de esta versión (o creadas solo con la contraseña) se cierran."""
    from app.routers.auth import crear_token_acceso
    db = bd.SessionLocal()
    admin = crear_usuario(db, ADMIN, rol="admin")
    ana = crear_usuario(db, "ana@example.com")
    sin_paso = crear_token_acceso({"sub": str(admin.id), "email": admin.email, "ver": 0})
    usuario_normal = crear_token_acceso({"sub": str(ana.id), "email": ana.email, "ver": 0})
    db.close()

    assert api.get("/api/auth/me", headers={"Authorization": f"Bearer {sin_paso}"}).status_code == 401
    assert api.get("/api/auth/me", headers={"Authorization": f"Bearer {usuario_normal}"}).status_code == 200


@requiere_postgres
def test_cambiar_la_contrasena_invalida_el_desafio(bd, api):
    from app.models.usuario import Usuario
    db = bd.SessionLocal()
    crear_usuario(db, ADMIN, rol="admin", clave=CLAVE_PRUEBA)
    db.close()
    secreto, _ = _activar(api)
    desafio = _login(api).json()["desafio"]
    db = bd.SessionLocal()
    u = db.query(Usuario).filter(Usuario.email == ADMIN).one()
    u.version_sesion += 1
    db.commit()
    db.close()
    r = api.post("/api/auth/login/2fa", json={"desafio": desafio, "codigo": _codigo_siguiente(secreto)})
    assert r.status_code == 401


@requiere_postgres
def test_cambiar_la_contrasena_propia_conserva_el_segundo_paso(bd, api):
    db = bd.SessionLocal()
    crear_usuario(db, ADMIN, rol="admin", clave=CLAVE_PRUEBA)
    db.close()
    _, activacion = _activar(api)
    token = activacion.json()["access_token"]
    r = api.post("/api/auth/cambiar-password", headers={"Authorization": f"Bearer {token}"},
                 json={"password_actual": CLAVE_PRUEBA, "password_nueva": "OtraClaveSegura2026!"})
    assert r.status_code == 200
    assert api.get("/api/auth/users", headers={"Authorization": f"Bearer {r.json()['access_token']}"}).status_code == 200


@requiere_postgres
def test_un_administrador_restablece_la_verificacion_de_otro(bd, api, auditoria_registrada):
    from app.models.usuario import Usuario
    db = bd.SessionLocal()
    jefe = crear_usuario(db, "jefe@example.com", rol="admin")
    crear_usuario(db, ADMIN, rol="admin", clave=CLAVE_PRUEBA)
    ana = crear_usuario(db, "ana@example.com")
    jefe_id, de_jefe, de_ana = jefe.id, cabecera(jefe), cabecera(ana)
    db.close()
    _, activacion = _activar(api)
    sesion_vieja = activacion.json()["access_token"]
    otro = _admin(bd)

    propio = api.post(f"/api/auth/users/{jefe_id}/doble-factor/restablecer", headers=de_jefe)
    sin_permiso = api.post(f"/api/auth/users/{otro.id}/doble-factor/restablecer", headers=de_ana)
    r = api.post(f"/api/auth/users/{otro.id}/doble-factor/restablecer", headers=de_jefe)
    db = bd.SessionLocal()
    u = db.query(Usuario).filter(Usuario.email == ADMIN).one()
    estado = (u.totp_activo, u.totp_secreto, u.totp_codigos_respaldo)
    db.close()

    assert propio.status_code == 400 and sin_permiso.status_code == 403
    assert r.status_code == 200 and estado == (False, None, None)
    assert api.get("/api/auth/me", headers={"Authorization": f"Bearer {sesion_vieja}"}).status_code == 401
    assert _login(api).json()["configurar_2fa"] is True
    lista = api.get("/api/auth/users", headers=de_jefe).json()
    assert {u["email"]: u["doble_factor_activo"] for u in lista}[ADMIN] is False


@requiere_postgres
def test_restablecer_desde_la_consola_del_servidor(bd, api):
    from app.restablecer_doble_factor import restablecer
    db = bd.SessionLocal()
    crear_usuario(db, ADMIN, rol="admin", clave=CLAVE_PRUEBA)
    db.close()
    _activar(api)
    assert restablecer(ADMIN.upper()) is True
    assert restablecer("nadie@example.com") is False
    assert _login(api).json()["configurar_2fa"] is True
