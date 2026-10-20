"""
Límites de intentos (login, recuperación y cambio de contraseña), validación del inicio de sesión
y límites que se aplican antes de leer el cuerpo de las peticiones.
"""
import re

import pytest
from fastapi.testclient import TestClient
import jwt

from app.config import settings
from app.models.usuario import Usuario
from app.routers import auth as auth_router
from app.routers.auth import crear_hash_password, crear_token_acceso
from app.utils import limitador as limitador_mod
from app.utils import limite_peticiones
from app.utils.limitador import Limitador
from tests.utilidades_pg import requiere_postgres


# ── Limitador ───────────────────────────────────────────────────────

def test_limitador_bloquea_al_llegar_al_maximo_y_se_libera_con_la_ventana(monkeypatch):
    reloj = [1000.0]
    monkeypatch.setattr(limitador_mod.time, "monotonic", lambda: reloj[0])
    lim = Limitador(3, 60)
    for _ in range(3):
        assert lim.espera("a") == 0
        lim.registrar("a")
    assert lim.espera("a") == 60
    assert lim.espera("b") == 0          # cada clave lleva su cuenta
    reloj[0] += 30
    assert lim.espera("a") == 30
    reloj[0] += 31                       # el primer intento ya salió de la ventana
    assert lim.espera("a") == 0
    lim.reiniciar("a")
    assert lim.espera("a") == 0


def test_mensaje_de_espera_en_minutos():
    assert limitador_mod.mensaje_espera(30) == "Demasiados intentos fallidos. Espera 1 minuto e intenta de nuevo."
    assert limitador_mod.mensaje_espera(840).startswith("Demasiados intentos fallidos. Espera 14 minutos")


# ── Middleware: token y tamaño antes de leer el cuerpo ─────────────

@pytest.fixture
def cliente_sin_bd():
    from app.main import app
    return TestClient(app)


def _token_firmado():
    return crear_token_acceso({"sub": "00000000-0000-0000-0000-000000000001", "email": "x@example.com", "ver": 0})


@pytest.mark.parametrize("ruta", ["/api/documentos/upload", "/api/comparacion/upload",
                                  "/api/personas/00000000-0000-0000-0000-000000000001/subir-pdf"])
def test_subida_sin_token_se_rechaza_sin_leer_el_archivo(cliente_sin_bd, ruta):
    r = cliente_sin_bd.post(ruta, files={"file": ("a.pdf", b"%PDF-1.4 " + b"0" * 5000, "application/pdf")})
    assert r.status_code == 401
    r = cliente_sin_bd.post(ruta, headers={"Authorization": "Bearer token-falso"},
                            files={"file": ("a.pdf", b"%PDF-1.4", "application/pdf")})
    assert r.status_code == 401


def test_subida_mas_grande_que_el_tope_responde_413(cliente_sin_bd, monkeypatch):
    monkeypatch.setattr(settings, "MAX_SUBIDA_TOTAL_MB", 1)
    r = cliente_sin_bd.post("/api/documentos/upload", headers={"Authorization": f"Bearer {_token_firmado()}"},
                            files={"files": ("a.pdf", b"0" * (1024 * 1024 + 10), "application/pdf")})
    assert r.status_code == 413
    assert "1 MB" in r.json()["detail"]


def test_peticion_comun_mas_grande_que_el_tope_responde_413(cliente_sin_bd, monkeypatch):
    monkeypatch.setattr(limite_peticiones, "LIMITE_GENERAL_BYTES", 1000)
    r = cliente_sin_bd.post("/api/auth/login", json={"email": "a@example.com", "password": "x" * 2000})
    assert r.status_code == 413


def test_cuerpo_sin_content_length_tambien_se_corta(cliente_sin_bd, monkeypatch):
    monkeypatch.setattr(limite_peticiones, "LIMITE_GENERAL_BYTES", 1000)

    def trozos():
        for _ in range(10):
            yield b"x" * 500

    r = cliente_sin_bd.post("/api/auth/login", content=trozos(), headers={"Content-Type": "application/json"})
    assert r.status_code in (400, 413)   # se deja de leer en cuanto pasa el tope


def test_la_ruta_de_login_por_formulario_ya_no_existe(cliente_sin_bd):
    r = cliente_sin_bd.post("/api/auth/login/form", data={"username": "a@example.com", "password": "x"})
    assert r.status_code in (404, 405)


# ── Login, recuperación y cambio de contraseña (con base de datos) ─

@pytest.fixture
def cliente(bd, monkeypatch):
    from app.main import app
    from app.services import correo_service

    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(settings, "SMTP_USER", "kondid@example.com")
    monkeypatch.setattr(settings, "FRONTEND_URL", "https://app.example.com")
    enviados = []
    monkeypatch.setattr(correo_service, "enviar_correo", lambda d, a, texto, html: enviados.append(texto) or True)
    c = TestClient(app)
    c.enviados = enviados
    return c


def _crear(bd, email, password, rol="usuario"):
    db = bd.SessionLocal()
    u = Usuario(email=email, nombre="Prueba", password_hash=crear_hash_password(password), rol=rol)
    db.add(u)
    db.commit()
    uid = u.id
    db.close()
    return uid


def _login(cliente, email, password, ip="203.0.113.10"):
    return cliente.post("/api/auth/login", json={"email": email, "password": password},
                        headers={"X-Forwarded-For": ip})


@requiere_postgres
def test_login_compara_el_correo_exacto(cliente, bd):
    _crear(bd, "ana@example.com", "ClaveAna2026")
    assert _login(cliente, "%@example.com", "ClaveAna2026").status_code == 401
    assert _login(cliente, "an_@example.com", "ClaveAna2026").status_code == 401
    assert _login(cliente, "ANA@Example.com", "ClaveAna2026").status_code == 200


@requiere_postgres
def test_correo_inexistente_tambien_verifica_una_contrasena(cliente, bd, monkeypatch):
    llamadas = []
    original = auth_router.verificar_password
    monkeypatch.setattr(auth_router, "verificar_password", lambda p, h: llamadas.append(h) or original(p, h))
    assert _login(cliente, "nadie@example.com", "Cualquiera2026").status_code == 401
    assert len(llamadas) == 1 and llamadas[0].startswith("$2")   # contra el hash señuelo


@requiere_postgres
def test_cinco_fallos_bloquean_el_correo_aunque_luego_acierte(cliente, bd):
    _crear(bd, "ana@example.com", "ClaveAna2026")
    for _ in range(5):
        assert _login(cliente, "ana@example.com", "Equivocada1").status_code == 401
    r = _login(cliente, "ana@example.com", "ClaveAna2026")
    assert r.status_code == 429
    assert int(r.headers["Retry-After"]) > 0
    assert re.search(r"Espera \d+ minutos?", r.json()["detail"])
    # Otra cuenta desde la misma IP sigue pudiendo entrar
    _crear(bd, "luis@example.com", "ClaveLuis2026")
    assert _login(cliente, "luis@example.com", "ClaveLuis2026").status_code == 200


@requiere_postgres
def test_un_acierto_reinicia_la_cuenta_de_fallos(cliente, bd):
    _crear(bd, "ana@example.com", "ClaveAna2026")
    for _ in range(4):
        _login(cliente, "ana@example.com", "Equivocada1")
    assert _login(cliente, "ana@example.com", "ClaveAna2026").status_code == 200
    for _ in range(4):
        assert _login(cliente, "ana@example.com", "Equivocada1").status_code == 401
    assert _login(cliente, "ana@example.com", "ClaveAna2026").status_code == 200


@requiere_postgres
def test_veinte_fallos_desde_una_ip_la_bloquean(cliente, bd):
    _crear(bd, "ana@example.com", "ClaveAna2026")
    for i in range(20):
        assert _login(cliente, f"prueba{i}@example.com", "Equivocada1", ip="198.51.100.7").status_code == 401
    assert _login(cliente, "ana@example.com", "ClaveAna2026", ip="198.51.100.7").status_code == 429
    assert _login(cliente, "ana@example.com", "ClaveAna2026", ip="198.51.100.8").status_code == 200


@requiere_postgres
def test_pedidos_de_recuperacion_limitados_por_ip(cliente, bd):
    for i in range(5):
        r = cliente.post("/api/auth/olvide-password", json={"email": f"x{i}@example.com"},
                         headers={"X-Forwarded-For": "198.51.100.9"})
        assert r.status_code == 200
    r = cliente.post("/api/auth/olvide-password", json={"email": "x9@example.com"},
                     headers={"X-Forwarded-For": "198.51.100.9"})
    assert r.status_code == 429
    assert "Demasiadas solicitudes de recuperación" in r.json()["detail"]


@requiere_postgres
def test_enlaces_invalidos_limitados_por_ip(cliente, bd):
    cab = {"X-Forwarded-For": "198.51.100.10"}
    for i in range(10):
        r = cliente.post("/api/auth/restablecer-password", json={"token": f"falso{i}", "password_nueva": "ClaveNueva2026"},
                         headers=cab)
        assert r.status_code == 400
    r = cliente.post("/api/auth/restablecer-password", json={"token": "otro", "password_nueva": "ClaveNueva2026"},
                     headers=cab)
    assert r.status_code == 429


@requiere_postgres
def test_cambiar_password_limita_la_contrasena_actual_equivocada(cliente, bd):
    _crear(bd, "ana@example.com", "ClaveAna2026")
    token = _login(cliente, "ana@example.com", "ClaveAna2026").json()["access_token"]
    cab = {"Authorization": f"Bearer {token}"}
    for _ in range(5):
        r = cliente.post("/api/auth/cambiar-password", headers=cab,
                         json={"password_actual": "Equivocada1", "password_nueva": "ClaveNueva2026"})
        assert r.status_code == 400
    r = cliente.post("/api/auth/cambiar-password", headers=cab,
                     json={"password_actual": "ClaveAna2026", "password_nueva": "ClaveNueva2026"})
    assert r.status_code == 429


@requiere_postgres
def test_subida_con_sesion_valida_llega_a_la_ruta(cliente, bd):
    _crear(bd, "ana@example.com", "ClaveAna2026")
    token = _login(cliente, "ana@example.com", "ClaveAna2026").json()["access_token"]
    r = cliente.post("/api/comparacion/upload", headers={"Authorization": f"Bearer {token}"},
                     files={"file": ("planilla.txt", b"no es excel", "text/plain")})
    assert r.status_code == 400   # la rechaza la ruta (extensión), no el middleware


@requiere_postgres
def test_vista_previa_solo_acepta_las_resoluciones_del_visor(cliente, bd):
    _crear(bd, "ana@example.com", "ClaveAna2026")
    token = _login(cliente, "ana@example.com", "ClaveAna2026").json()["access_token"]
    r = cliente.get("/api/documentos/00000000-0000-0000-0000-000000000001/pagina/1?dpi=9999",
                    headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 400
    r = cliente.get("/api/documentos/00000000-0000-0000-0000-000000000001/pagina/1?dpi=130",
                    headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 404   # resolución válida: sigue y no encuentra el documento


def test_token_de_otra_clave_no_pasa_el_middleware():
    falso = jwt.encode({"sub": "x"}, "otra-clave", algorithm="HS256")
    assert not limite_peticiones._token_valido(f"Bearer {falso}".encode())
    assert limite_peticiones._token_valido(f"Bearer {_token_firmado()}".encode())


def test_middleware_no_lee_el_cuerpo_ni_llama_a_la_ruta_sin_token():
    import asyncio

    llamadas, lecturas, enviados = [], [], []

    async def ruta(scope, receive, send):
        llamadas.append(scope["path"])

    async def receive():
        lecturas.append(1)
        return {"type": "http.request", "body": b"0" * 1024, "more_body": True}

    async def send(mensaje):
        enviados.append(mensaje)

    scope = {"type": "http", "method": "POST", "path": "/api/documentos/upload",
             "headers": [(b"content-length", b"999999999")]}
    asyncio.run(limite_peticiones.LimitePeticionesMiddleware(ruta)(scope, receive, send))
    assert llamadas == [] and lecturas == []
    assert enviados[0]["status"] == 401
