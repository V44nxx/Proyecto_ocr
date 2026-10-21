"""
Recuperar la contraseña por correo, cambiarla desde la app y restablecerla como admin.
Cualquier cambio de contraseña cierra las sesiones abiertas con la clave anterior.
"""
import re
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.models.usuario import Usuario
from app.routers.auth import crear_hash_password
from tests.utilidades_pg import requiere_postgres


@pytest.fixture
def cliente(bd, monkeypatch):
    from app.main import app
    from app.services import correo_service

    enviados = []
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(settings, "SMTP_USER", "kondid@example.com")
    monkeypatch.setattr(settings, "FRONTEND_URL", "https://app.example.com/")
    monkeypatch.setattr(correo_service, "enviar_correo",
                        lambda destinatario, asunto, texto, html: enviados.append(
                            {"para": destinatario, "asunto": asunto, "texto": texto, "html": html}) or True)
    c = TestClient(app)
    c.enviados = enviados
    return c


def _crear(bd, email, password, rol="usuario"):
    db = bd.SessionLocal()
    u = Usuario(email=email, nombre="Ana Prueba", password_hash=crear_hash_password(password), rol=rol)
    db.add(u)
    db.commit()
    uid = u.id
    db.close()
    return uid


def _login(cliente, email, password):
    r = cliente.post("/api/auth/login", json={"email": email, "password": password})
    return r.json()["access_token"] if r.status_code == 200 else None


def _me(cliente, token):
    return cliente.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code


def _token_del_correo(correo):
    m = re.search(r"https://app\.example\.com/restablecer-contrasena\?token=([\w-]+)", correo["texto"])
    assert m, correo["texto"]
    return m.group(1)


@requiere_postgres
def test_sin_correo_configurado_responde_503(cliente, bd, monkeypatch):
    monkeypatch.setattr(settings, "SMTP_HOST", None)
    r = cliente.post("/api/auth/olvide-password", json={"email": "ana@example.com"})
    assert r.status_code == 503


@requiere_postgres
def test_recuperar_por_correo_de_punta_a_punta(cliente, bd):
    uid = _crear(bd, "ana@example.com", "ClaveVieja2026")
    sesion_vieja = _login(cliente, "ana@example.com", "ClaveVieja2026")
    assert _me(cliente, sesion_vieja) == 200

    r = cliente.post("/api/auth/olvide-password", json={"email": "ANA@example.com"})
    assert r.status_code == 200
    assert len(cliente.enviados) == 1
    correo = cliente.enviados[0]
    assert correo["para"] == "ana@example.com"
    token = _token_del_correo(correo)
    assert token in correo["html"]

    db = bd.SessionLocal()
    u = db.get(Usuario, uid)
    assert u.reset_token_hash and u.reset_token_hash != token  # solo se guarda el hash
    db.close()

    r = cliente.post("/api/auth/restablecer-password", json={"token": token, "password_nueva": "ClaveNueva2026"})
    assert r.status_code == 200
    assert _me(cliente, sesion_vieja) == 401            # la sesión abierta con la clave vieja se cierra
    assert _login(cliente, "ana@example.com", "ClaveVieja2026") is None
    assert _me(cliente, _login(cliente, "ana@example.com", "ClaveNueva2026")) == 200

    r = cliente.post("/api/auth/restablecer-password", json={"token": token, "password_nueva": "OtraClave2026"})
    assert r.status_code == 400                          # el enlace sirve una sola vez


@requiere_postgres
def test_correo_inexistente_responde_igual_y_no_envia(cliente, bd):
    _crear(bd, "ana@example.com", "ClaveVieja2026")
    existe = cliente.post("/api/auth/olvide-password", json={"email": "ana@example.com"})
    no_existe = cliente.post("/api/auth/olvide-password", json={"email": "nadie@example.com"})
    assert existe.status_code == no_existe.status_code == 200
    assert existe.json() == no_existe.json()
    assert [c["para"] for c in cliente.enviados] == ["ana@example.com"]
    # El mismo mensaje para los dos aclara que a un correo sin cuenta no le llega nada
    assert "Si no está registrado, no se envía nada" in no_existe.json()["message"]


@requiere_postgres
def test_no_reenvia_antes_de_2_minutos(cliente, bd):
    uid = _crear(bd, "ana@example.com", "ClaveVieja2026")
    cliente.post("/api/auth/olvide-password", json={"email": "ana@example.com"})
    cliente.post("/api/auth/olvide-password", json={"email": "ana@example.com"})
    assert len(cliente.enviados) == 1

    db = bd.SessionLocal()
    u = db.get(Usuario, uid)
    u.reset_token_expira = u.reset_token_expira - timedelta(minutes=3)
    db.commit()
    db.close()
    cliente.post("/api/auth/olvide-password", json={"email": "ana@example.com"})
    assert len(cliente.enviados) == 2
    # El enlace nuevo reemplaza al anterior
    viejo, nuevo = (_token_del_correo(c) for c in cliente.enviados)
    assert cliente.post("/api/auth/restablecer-password",
                        json={"token": viejo, "password_nueva": "ClaveNueva2026"}).status_code == 400
    assert cliente.post("/api/auth/restablecer-password",
                        json={"token": nuevo, "password_nueva": "ClaveNueva2026"}).status_code == 200


@requiere_postgres
def test_enlace_vencido_no_sirve(cliente, bd):
    uid = _crear(bd, "ana@example.com", "ClaveVieja2026")
    cliente.post("/api/auth/olvide-password", json={"email": "ana@example.com"})
    token = _token_del_correo(cliente.enviados[0])
    db = bd.SessionLocal()
    db.get(Usuario, uid).reset_token_expira = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()
    db.close()
    r = cliente.post("/api/auth/restablecer-password", json={"token": token, "password_nueva": "ClaveNueva2026"})
    assert r.status_code == 400
    assert _login(cliente, "ana@example.com", "ClaveVieja2026")


@requiere_postgres
def test_contrasena_nueva_muy_corta(cliente, bd):
    _crear(bd, "ana@example.com", "ClaveVieja2026")
    cliente.post("/api/auth/olvide-password", json={"email": "ana@example.com"})
    token = _token_del_correo(cliente.enviados[0])
    r = cliente.post("/api/auth/restablecer-password", json={"token": token, "password_nueva": "corta"})
    assert r.status_code == 422


@requiere_postgres
def test_cambiar_password_propia(cliente, bd):
    _crear(bd, "ana@example.com", "ClaveVieja2026")
    sesion = _login(cliente, "ana@example.com", "ClaveVieja2026")
    otra_sesion = _login(cliente, "ana@example.com", "ClaveVieja2026")
    cab = {"Authorization": f"Bearer {sesion}"}

    r = cliente.post("/api/auth/cambiar-password", headers=cab,
                     json={"password_actual": "Equivocada1", "password_nueva": "ClaveNueva2026"})
    assert r.status_code == 400  # 400 y no 401, para que el frontend no cierre la sesión
    r = cliente.post("/api/auth/cambiar-password", headers=cab,
                     json={"password_actual": "ClaveVieja2026", "password_nueva": "ClaveVieja2026"})
    assert r.status_code == 400

    r = cliente.post("/api/auth/cambiar-password", headers=cab,
                     json={"password_actual": "ClaveVieja2026", "password_nueva": "ClaveNueva2026"})
    assert r.status_code == 200
    assert _me(cliente, r.json()["access_token"]) == 200   # esta sesión sigue con el token nuevo
    assert _me(cliente, otra_sesion) == 401                 # las demás se cierran
    assert _login(cliente, "ana@example.com", "ClaveNueva2026")


@requiere_postgres
def test_admin_restablece_la_de_otro_usuario(cliente, bd):
    _crear(bd, "admin@example.com", "ClaveAdmin2026", rol="admin")
    uid = _crear(bd, "ana@example.com", "ClaveVieja2026")
    admin = {"Authorization": f"Bearer {_login(cliente, 'admin@example.com', 'ClaveAdmin2026')}"}
    sesion_ana = _login(cliente, "ana@example.com", "ClaveVieja2026")

    r = cliente.post(f"/api/auth/users/{uid}/password", headers={"Authorization": f"Bearer {sesion_ana}"},
                     json={"password_nueva": "ClaveNueva2026"})
    assert r.status_code == 403

    r = cliente.post(f"/api/auth/users/{uid}/password", headers=admin, json={"password_nueva": "ClaveNueva2026"})
    assert r.status_code == 200
    assert _me(cliente, sesion_ana) == 401
    assert _login(cliente, "ana@example.com", "ClaveNueva2026")

    db = bd.SessionLocal()
    admin_id = db.query(Usuario).filter(Usuario.email == "admin@example.com").one().id
    db.close()
    r = cliente.post(f"/api/auth/users/{admin_id}/password", headers=admin, json={"password_nueva": "OtraClave2026"})
    assert r.status_code == 400


def test_correo_de_recuperacion_escapa_el_nombre(monkeypatch):
    from app.services import correo_service

    capturado = {}
    monkeypatch.setattr(correo_service, "enviar_correo",
                        lambda d, a, texto, html: capturado.update(texto=texto, html=html) or True)
    correo_service.enviar_correo_recuperacion("a@example.com", "<b>Ana</b>", "https://x/restablecer?token=abc", 30)
    assert "&lt;b&gt;Ana&lt;/b&gt;" in capturado["html"]
    assert "30 minutos" in capturado["texto"]


@requiere_postgres
def test_sesiones_de_antes_del_cambio_siguen_sirviendo(cliente, bd):
    """Los tokens emitidos antes de esta versión no traen 'ver': valen mientras no se cambie la contraseña."""
    import jwt

    uid = _crear(bd, "ana@example.com", "ClaveVieja2026")
    viejo = jwt.encode({"sub": str(uid), "email": "ana@example.com",
                        "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
                       settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    assert _me(cliente, viejo) == 200
    cab = {"Authorization": f"Bearer {viejo}"}
    r = cliente.post("/api/auth/cambiar-password", headers=cab,
                     json={"password_actual": "ClaveVieja2026", "password_nueva": "ClaveNueva2026"})
    assert r.status_code == 200
    assert _me(cliente, viejo) == 401


@requiere_postgres
def test_en_produccion_sin_frontend_url_no_envia_enlaces_rotos(cliente, bd, monkeypatch):
    _crear(bd, "ana@example.com", "ClaveVieja2026")
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "FRONTEND_URL", "http://localhost:3000")
    r = cliente.post("/api/auth/olvide-password", json={"email": "ana@example.com"})
    assert r.status_code == 503
    assert cliente.enviados == []
