"""
Sesión en cookie segura (versión 2.8.0).

La sesión viaja en una cookie HttpOnly (ningún script la puede leer), SameSite=Strict y, en producción,
Secure con el prefijo __Host-. Cerrar sesión revoca esa sesión en el servidor. Una petición que cambia datos
con la cookie y viene de un origen ajeno se rechaza (CSRF). La cabecera Authorization sigue funcionando
para clientes que no son el navegador (scripts, JMeter, ZAP).
"""
import uuid
from http.cookies import SimpleCookie

import jwt
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from tests.utilidades_pg import CLAVE_PRUEBA, crear_usuario, requiere_postgres

FRONTEND = "https://proyectoocr.v44nxx.online"
AJENO = "https://sitio-ajeno.example"
URL_PANEL = "https://script.google.com/macros/s/abc123/exec"


def _cookie(respuesta, nombre):
    """Atributos de la cookie `nombre` en el Set-Cookie de la respuesta (en minúsculas)."""
    for cabecera in respuesta.headers.get_list("set-cookie"):
        c = SimpleCookie()
        c.load(cabecera)
        if nombre in c:
            m = c[nombre]
            return {"valor": m.value, **{k.lower(): v for k, v in m.items() if v}, "crudo": cabecera.lower()}
    return None


def _login(cliente, email="ana@example.com", clave=CLAVE_PRUEBA):
    return cliente.post("/api/auth/login", json={"email": email, "password": clave})


@pytest.fixture
def cliente(bd):
    c = TestClient(app, raise_server_exceptions=False)
    yield c
    app.dependency_overrides.clear()


@pytest.fixture
def ana(bd):
    db = bd.SessionLocal()
    u = crear_usuario(db, "ana@example.com", clave=CLAVE_PRUEBA)
    db.close()
    return u


# ── La cookie ───────────────────────────────────────────────────────

@requiere_postgres
def test_iniciar_sesion_entrega_una_cookie_httponly_y_samesite_strict(cliente, ana):
    r = _login(cliente)
    assert r.status_code == 200
    cookie = _cookie(r, "kondid_sesion")
    assert cookie is not None
    assert "httponly" in cookie["crudo"]
    assert "samesite=strict" in cookie["crudo"]
    assert cookie["path"] == "/"
    assert int(cookie["max-age"]) == settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    # Fuera de producción (http local) no puede ser Secure, o el navegador no la guardaría
    assert "secure" not in cookie["crudo"]


@requiere_postgres
def test_en_produccion_la_cookie_es_secure_y_con_prefijo_host(cliente, ana, monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    r = _login(cliente)
    cookie = _cookie(r, "__Host-kondid_sesion")
    assert cookie is not None
    assert "secure" in cookie["crudo"]
    assert "domain" not in cookie  # __Host- exige que no tenga dominio


@requiere_postgres
def test_la_sesion_funciona_solo_con_la_cookie(cliente, ana):
    _login(cliente)  # el cliente guarda la cookie como un navegador
    r = cliente.get("/api/auth/me")
    assert r.status_code == 200
    assert r.json()["email"] == "ana@example.com"


@requiere_postgres
def test_la_cabecera_authorization_sigue_funcionando(cliente, ana):
    token = _login(cliente).json()["access_token"]
    cliente.cookies.clear()
    assert cliente.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 200


def test_los_tokens_nuevos_traen_un_identificador_de_sesion():
    from app.routers.auth import crear_token_acceso
    a = jwt.decode(crear_token_acceso({"sub": str(uuid.uuid4())}), settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    b = jwt.decode(crear_token_acceso({"sub": str(uuid.uuid4())}), settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    assert a["jti"] and b["jti"] and a["jti"] != b["jti"]


# ── Cerrar sesión ───────────────────────────────────────────────────

@requiere_postgres
def test_cerrar_sesion_la_invalida_en_el_servidor_y_borra_la_cookie(cliente, ana):
    token = _login(cliente).json()["access_token"]
    r = cliente.post("/api/auth/logout", headers={"Origin": "http://localhost:3000"})
    assert r.status_code == 200
    borrada = _cookie(r, "kondid_sesion")
    assert borrada is not None and int(borrada["max-age"]) == 0
    # El mismo token, aunque alguien lo hubiera copiado, ya no sirve
    cliente.cookies.clear()
    assert cliente.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401
    cliente.cookies.set("kondid_sesion", token)
    assert cliente.get("/api/auth/me").status_code == 401


@requiere_postgres
def test_cerrar_sesion_no_cierra_las_de_otros_equipos(bd, ana):
    equipo_1 = TestClient(app)
    equipo_2 = TestClient(app)
    _login(equipo_1)
    _login(equipo_2)
    equipo_1.post("/api/auth/logout")
    assert equipo_1.get("/api/auth/me").status_code == 401
    assert equipo_2.get("/api/auth/me").status_code == 200


@requiere_postgres
def test_cerrar_sesion_sin_sesion_responde_bien(cliente):
    assert cliente.post("/api/auth/logout").status_code == 200


@requiere_postgres
def test_cerrar_sesion_queda_en_la_auditoria(cliente, ana, bd):
    from app.models.auditoria import RegistroAuditoria
    _login(cliente)
    cliente.post("/api/auth/logout")
    db = bd.SessionLocal()
    acciones = [r.accion for r in db.query(RegistroAuditoria).all()]
    db.close()
    assert "logout" in acciones


# ── CSRF: peticiones con la cookie desde otro sitio ─────────────────

@requiere_postgres
def test_cambiar_datos_con_la_cookie_desde_otro_origen_se_rechaza(cliente, ana):
    _login(cliente)
    r = cliente.put("/api/seguimiento/config", json={"url_panel": URL_PANEL}, headers={"Origin": AJENO})
    assert r.status_code == 403


@requiere_postgres
@pytest.mark.parametrize("origen", [FRONTEND, "http://localhost:3000", None])
def test_cambiar_datos_con_la_cookie_desde_el_frontend_funciona(cliente, ana, origen):
    _login(cliente)
    cabeceras = {"Origin": origen} if origen else {}
    r = cliente.put("/api/seguimiento/config", json={"url_panel": URL_PANEL}, headers=cabeceras)
    assert r.status_code == 200


@requiere_postgres
def test_cambiar_datos_detras_del_proxy_del_frontend_funciona(cliente, ana):
    # Next reenvía /api/* al backend: el origen es el del frontend y X-Forwarded-Host también
    _login(cliente)
    r = cliente.put("/api/seguimiento/config", json={"url_panel": URL_PANEL},
                    headers={"Origin": "https://kondid.otro-dominio.example", "X-Forwarded-Host": "kondid.otro-dominio.example"})
    assert r.status_code == 200


@requiere_postgres
def test_leer_datos_desde_otro_origen_no_se_bloquea_aqui(cliente, ana):
    # Leer no cambia nada; el navegador igual no deja que el sitio ajeno vea la respuesta (CORS)
    _login(cliente)
    assert cliente.get("/api/auth/me", headers={"Origin": AJENO}).status_code == 200


@requiere_postgres
def test_con_la_cabecera_authorization_no_aplica_la_revision_de_origen(cliente, ana):
    # Un sitio ajeno no puede poner esa cabecera con la sesión de otro: no hay riesgo de CSRF
    token = _login(cliente).json()["access_token"]
    cliente.cookies.clear()
    r = cliente.put("/api/seguimiento/config", json={"url_panel": URL_PANEL},
                    headers={"Authorization": f"Bearer {token}", "Origin": AJENO})
    assert r.status_code == 200


# ── Cambiar contraseña y subidas ────────────────────────────────────

@requiere_postgres
def test_cambiar_la_contrasena_renueva_la_cookie(cliente, ana):
    _login(cliente)
    r = cliente.post("/api/auth/cambiar-password",
                     json={"password_actual": CLAVE_PRUEBA, "password_nueva": "Rio-Verde-Tarde-7"})
    assert r.status_code == 200
    assert _cookie(r, "kondid_sesion") is not None
    assert cliente.get("/api/auth/me").status_code == 200  # sigue con la cookie nueva


def test_las_subidas_aceptan_la_sesion_en_la_cookie():
    from app.routers.auth import crear_token_acceso
    from app.utils import limite_peticiones
    token = crear_token_acceso({"sub": str(uuid.uuid4()), "ver": 0})
    assert limite_peticiones._sesion_valida({b"cookie": f"otra=1; kondid_sesion={token}".encode()})
    assert limite_peticiones._sesion_valida({b"authorization": f"Bearer {token}".encode()})
    assert not limite_peticiones._sesion_valida({b"cookie": b"kondid_sesion=basura"})
    assert not limite_peticiones._sesion_valida({})


# ── CORS con credenciales ───────────────────────────────────────────

def test_cors_permite_credenciales_solo_al_frontend():
    c = TestClient(app)
    preflight = {"Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"}
    propio = c.options("/api/auth/login", headers={"Origin": FRONTEND, **preflight})
    ajeno = c.options("/api/auth/login", headers={"Origin": AJENO, **preflight})
    assert propio.headers["access-control-allow-origin"] == FRONTEND
    assert propio.headers["access-control-allow-credentials"] == "true"
    assert ajeno.headers.get("access-control-allow-origin") is None
