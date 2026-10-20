"""
Endurecimiento de seguridad de la API (versión 2.7.0).

Cubre los patrones aplicados: autorización por dueño en cada recurso, manejo de errores sin detalles
internos, configuración segura por defecto, cabeceras de seguridad, CORS por lista, sesión solo por
cabecera, nombres de archivo saneados, política de contraseñas y registro de auditoría.
Las pruebas marcadas con `requiere_postgres` necesitan TEST_DATABASE_URL.
"""
import inspect
import io
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import openpyxl
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import Settings, settings
from app.database import get_db
from app.main import app
from app.models.comparacion import Comparacion
from app.models.diferencia import Diferencia
from app.routers.auth import get_usuario_actual
from tests.utilidades_pg import (
    CLAVE_PRUEBA, cabecera, crear_ficha, crear_persona, crear_usuario, pdf_de_prueba, requiere_postgres,
)

FRONTEND_OFICIAL = "https://proyectoocr.v44nxx.online"
ORIGEN_AJENO = "https://sitio-ajeno.example"


def _usuario(rol="usuario"):
    return SimpleNamespace(id=uuid.uuid4(), rol=rol, activo=True, email=f"{rol}@example.com", version_sesion=0)


@pytest.fixture
def cliente():
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


def _comparacion_con_diferencia(db, dueno, cedula="1000000402"):
    comp = Comparacion(usuario_id=dueno.id, nombre_archivo="p.xlsx", nombre_original="p.xlsx", estado="completado")
    db.add(comp)
    db.commit()
    db.add(Diferencia(comparacion_id=comp.id, numero_identificacion=cedula, campo="nombres",
                      valor_bd="ANGELA", valor_excel="ANGELA MARIA", tipo_diferencia="diferente"))
    db.commit()
    return comp


# ── Autorización por dueño ──────────────────────────────────────────

@requiere_postgres
def test_reporte_de_diferencias_solo_lo_descarga_su_dueno(bd, api):
    db = bd.SessionLocal()
    ana = crear_usuario(db, "ana@example.com")
    beto = crear_usuario(db, "beto@example.com")
    comp = _comparacion_con_diferencia(db, ana)

    ajeno = api.get(f"/api/exportacion/diferencias/{comp.id}", headers=cabecera(beto))
    propio = api.get(f"/api/exportacion/diferencias/{comp.id}", headers=cabecera(ana))
    db.close()

    assert ajeno.status_code == 404
    assert propio.status_code == 200
    assert propio.content[:2] == b"PK"


@requiere_postgres
def test_reporte_de_diferencias_con_id_invalido_responde_404(bd, api):
    db = bd.SessionLocal()
    ana = crear_usuario(db, "ana@example.com")
    r = api.get("/api/exportacion/diferencias/no-es-un-uuid", headers=cabecera(ana))
    db.close()
    assert r.status_code == 404


@requiere_postgres
def test_reporte_de_diferencias_no_mezcla_personas_de_otra_cuenta(bd):
    from app.services.exportacion_service import exportacion_service
    db = bd.SessionLocal()
    ana = crear_usuario(db, "ana@example.com")
    beto = crear_usuario(db, "beto@example.com")
    # La misma cédula en las dos cuentas: el reporte de ana debe usar la página de su propia persona
    crear_persona(db, beto, crear_ficha(db, beto), "1000000402", "OTRA", "PERSONA", pagina_frente=7)
    crear_persona(db, ana, crear_ficha(db, ana), "1000000402", "ANGELA", "MORA", pagina_frente=2)
    comp = _comparacion_con_diferencia(db, ana)

    ruta = exportacion_service.exportar_reporte_diferencias(db, str(comp.id), usuario_id=ana.id)
    db.close()

    hoja = openpyxl.load_workbook(ruta).active
    encabezados = [c.value for c in hoja[1]]
    fila = [c.value for c in hoja[2]]
    assert fila[encabezados.index("Página Frente")] == 2


# ── Manejo de errores ───────────────────────────────────────────────

def test_error_interno_no_muestra_detalles_y_da_una_referencia(cliente):
    def falla():
        raise RuntimeError("detalle secreto: SELECT * FROM usuarios")

    app.dependency_overrides[get_usuario_actual] = falla
    r = cliente.get("/api/auth/me", headers={"Origin": FRONTEND_OFICIAL})

    assert r.status_code == 500
    assert "secreto" not in r.text and "SELECT" not in r.text
    assert r.json()["referencia"].startswith("ERR-")
    assert r.json()["referencia"] in r.json()["detail"]
    # El navegador del frontend oficial debe poder leer el error
    assert r.headers.get("access-control-allow-origin") == FRONTEND_OFICIAL


@requiere_postgres
@pytest.mark.parametrize("ruta", [
    "/api/personas/no-es-un-uuid", "/api/documentos/no-es-un-uuid", "/api/comparacion/no-es-un-uuid",
    "/api/personas?documento_id=no-es-un-uuid", "/api/exportacion/xlsx?documento_id=no-es-un-uuid",
    "/api/documentos/dashboard/estadisticas?documento_id=no-es-un-uuid",
])
def test_ids_con_formato_invalido_no_producen_errores_500(bd, api, ruta):
    db = bd.SessionLocal()
    ana = crear_usuario(db, "ana@example.com")
    r = api.get(ruta, headers=cabecera(ana))
    db.close()
    assert 400 <= r.status_code < 500
    assert "psycopg2" not in r.text and "invalid input syntax" not in r.text


def test_error_interno_no_autoriza_a_un_origen_ajeno(cliente):
    def falla():
        raise RuntimeError("falla")

    app.dependency_overrides[get_usuario_actual] = falla
    r = cliente.get("/api/auth/me", headers={"Origin": ORIGEN_AJENO})
    assert r.status_code == 500
    assert r.headers.get("access-control-allow-origin") not in (ORIGEN_AJENO, "*")


# ── Configuración segura por defecto ────────────────────────────────

def test_debug_apagado_por_defecto(monkeypatch):
    monkeypatch.delenv("DEBUG", raising=False)
    assert Settings(_env_file=None).DEBUG is False


@pytest.mark.parametrize("entorno, publicada", [("production", False), ("PRODUCTION", False),
                                                 ("development", True), ("pruebas", True)])
def test_documentacion_interactiva_solo_fuera_de_produccion(entorno, publicada):
    from app.main import rutas_documentacion
    rutas = rutas_documentacion(Settings(_env_file=None, ENVIRONMENT=entorno))
    assert (rutas["docs_url"] is not None) is publicada
    assert (rutas["redoc_url"] is not None) is publicada
    assert (rutas["openapi_url"] is not None) is publicada


# ── Cabeceras de seguridad y caché ──────────────────────────────────

def test_respuestas_llevan_cabeceras_de_seguridad(cliente):
    r = cliente.get("/health")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["referrer-policy"] == "no-referrer"
    assert "frame-ancestors 'none'" in r.headers["content-security-policy"]


def test_respuestas_de_la_api_no_se_guardan_en_cache(cliente):
    app.dependency_overrides[get_usuario_actual] = lambda: SimpleNamespace(
        id=uuid.uuid4(), email="ana@example.com", nombre="Ana", rol="usuario", activo=True,
        fecha_creacion="2026-10-19T00:00:00")
    r = cliente.get("/api/auth/me")
    assert r.status_code == 200
    assert "no-store" in r.headers["cache-control"]


def test_hsts_solo_en_produccion(cliente, monkeypatch):
    assert "strict-transport-security" not in cliente.get("/health").headers
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    assert cliente.get("/health").headers["strict-transport-security"].startswith("max-age=")


# ── CORS ────────────────────────────────────────────────────────────

def _preflight(cliente, origen):
    return cliente.options("/api/auth/login", headers={
        "Origin": origen, "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"})


def test_cors_no_autoriza_a_un_origen_ajeno(cliente):
    r = _preflight(cliente, ORIGEN_AJENO)
    assert r.headers.get("access-control-allow-origin") not in (ORIGEN_AJENO, "*")


@pytest.mark.parametrize("origen", [FRONTEND_OFICIAL, "http://localhost:3000", "http://127.0.0.1:3000"])
def test_cors_autoriza_al_frontend(cliente, origen):
    r = _preflight(cliente, origen)
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == origen
    # La sesión viaja en la cabecera Authorization, no en cookies
    assert "access-control-allow-credentials" not in r.headers


@pytest.mark.parametrize("origen", ["https://v44nxx.online.sitio-ajeno.example", "http://proyectoocr.v44nxx.online",
                                    "https://proyectoocrv44nxx.online"])
def test_cors_no_se_engana_con_dominios_parecidos(cliente, origen):
    r = _preflight(cliente, origen)
    assert r.headers.get("access-control-allow-origin") != origen


# ── Vista previa: sesión solo por cabecera ──────────────────────────

@requiere_postgres
def test_vista_previa_no_acepta_el_token_en_la_direccion(bd, api, tmp_path):
    from tests.utilidades_pg import token_de
    db = bd.SessionLocal()
    ana = crear_usuario(db, "ana@example.com")
    ficha = crear_ficha(db, ana, ruta_archivo=str(pdf_de_prueba(tmp_path / "f.pdf")))
    url = f"/api/documentos/{ficha.id}/pagina/1"

    con_token_en_url = api.get(url, params={"dpi": 130, "token": token_de(ana)})
    con_cabecera = api.get(url, params={"dpi": 130}, headers=cabecera(ana))
    db.close()

    assert con_token_en_url.status_code == 401
    assert con_cabecera.status_code == 200
    assert con_cabecera.headers["content-type"] == "image/jpeg"
    assert "private" in con_cabecera.headers["cache-control"]
    assert "no-store" in con_cabecera.headers["cache-control"]


@requiere_postgres
def test_vista_previa_desde_cache_tampoco_se_guarda_en_el_navegador(bd, api, tmp_path):
    db = bd.SessionLocal()
    ana = crear_usuario(db, "ana@example.com")
    ficha = crear_ficha(db, ana, ruta_archivo=str(pdf_de_prueba(tmp_path / "f.pdf")))
    url = f"/api/documentos/{ficha.id}/pagina/2"
    api.get(url, params={"dpi": 130}, headers=cabecera(ana))
    segunda = api.get(url, params={"dpi": 130}, headers=cabecera(ana))  # sale de la caché en disco
    db.close()
    assert segunda.status_code == 200
    assert "no-store" in segunda.headers["cache-control"]


# ── Nombres de archivo ──────────────────────────────────────────────

@pytest.mark.parametrize("original, esperado", [
    ("ficha.pdf", "ficha.pdf"),
    ("../../../fuera.pdf", "fuera.pdf"),
    ("..\\..\\fuera.pdf", "fuera.pdf"),
    ("/etc/passwd", "passwd"),
    ("C:\\Windows\\win.ini", "win.ini"),
    ("Cédula Ñandú (1).pdf", "Cédula Ñandú (1).pdf"),
    ("a<b>c:d|e?.pdf", "a_b_c_d_e_.pdf"),
    ("..", "archivo"),
    ("", "archivo"),
    (None, "archivo"),
])
def test_nombre_de_archivo_seguro(original, esperado):
    from app.utils.archivos import nombre_archivo_seguro
    assert nombre_archivo_seguro(original) == esperado


def test_nombre_de_archivo_seguro_limita_el_largo():
    from app.utils.archivos import nombre_archivo_seguro
    nombre = nombre_archivo_seguro("x" * 400 + ".pdf")
    assert len(nombre) <= 150
    assert nombre.endswith(".pdf")


@pytest.fixture
def subidas(monkeypatch, tmp_path):
    carpeta = tmp_path / "uploads"
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(carpeta))
    return carpeta


def test_subida_con_nombre_peligroso_queda_dentro_de_la_carpeta(subidas, monkeypatch):
    from app.routers.auth import crear_token_acceso
    db = MagicMock()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_usuario_actual] = lambda: _usuario()
    monkeypatch.setattr("app.routers.documentos._procesar_batch_ocr_y_comparacion", MagicMock())
    token = crear_token_acceso({"sub": str(uuid.uuid4()), "ver": 0})
    cliente = TestClient(app, headers={"Authorization": f"Bearer {token}"})

    r = cliente.post("/api/documentos/upload",
                     files=[("files", ("../../../../fuera.pdf", b"%PDF-1.4 x", "application/pdf"))])
    app.dependency_overrides.clear()

    assert r.status_code == 202
    guardado = db.add.call_args_list[0][0][0]
    assert "/" not in guardado.nombre_archivo and "\\" not in guardado.nombre_archivo
    assert ".." not in guardado.nombre_archivo
    assert guardado.nombre_archivo.endswith("_fuera.pdf")
    assert [p.name for p in subidas.iterdir()] == [guardado.nombre_archivo]
    assert not list(subidas.parent.rglob("fuera.pdf"))


# ── Disponibilidad ──────────────────────────────────────────────────

def test_subir_pdf_de_persona_no_bloquea_el_servidor():
    # El OCR es síncrono: la ruta debe ser `def` para que FastAPI la corra en un hilo aparte
    from app.routers.personas import subir_pdf_persona
    assert not inspect.iscoroutinefunction(subir_pdf_persona)


# ── Política de contraseñas ─────────────────────────────────────────

@pytest.mark.parametrize("clave", ["password", "12345678", "123456789", "qwertyuiop", "Contraseña1",
                                   "kondid2026", "KondID2026!", "admin1234", "colombia2026"])
def test_contrasenas_comunes_se_rechazan(clave):
    from app.schemas.usuario import RestablecerPasswordAdminRequest, UsuarioCreate
    with pytest.raises(ValidationError):
        UsuarioCreate(email="nuevo@example.com", password=clave)
    with pytest.raises(ValidationError):
        RestablecerPasswordAdminRequest(password_nueva=clave)


@pytest.mark.parametrize("clave", ["ClaveSegura123", CLAVE_PRUEBA, "río-verde-tarde-7", "Ñandú en la sabana"])
def test_contrasenas_razonables_se_aceptan(clave):
    from app.schemas.usuario import RestablecerPasswordAdminRequest, UsuarioCreate
    UsuarioCreate(email="nuevo@example.com", password=clave)
    RestablecerPasswordAdminRequest(password_nueva=clave)


def test_crear_usuario_tambien_limita_los_72_bytes():
    from app.schemas.usuario import UsuarioCreate
    with pytest.raises(ValidationError):
        UsuarioCreate(email="nuevo@example.com", password="ñ" * 40)


# ── Datos personales en los registros ───────────────────────────────

@pytest.mark.parametrize("valor, esperado", [("1000000401", "******0401"), ("123", "***"), ("", ""), (None, "")])
def test_enmascarar_documento(valor, esperado):
    from app.utils.logger import enmascarar_documento
    assert enmascarar_documento(valor) == esperado


# ── Auditoría ───────────────────────────────────────────────────────

@requiere_postgres
def test_inicios_de_sesion_quedan_en_la_auditoria(bd, api):
    from app.models.auditoria import RegistroAuditoria
    db = bd.SessionLocal()
    crear_usuario(db, "ana@example.com", clave=CLAVE_PRUEBA)
    api.post("/api/auth/login", json={"email": "ana@example.com", "password": "equivocada"})
    api.post("/api/auth/login", json={"email": "ana@example.com", "password": CLAVE_PRUEBA})

    registros = db.query(RegistroAuditoria).order_by(RegistroAuditoria.fecha).all()
    db.close()
    assert [(r.accion, r.email) for r in registros] == [
        ("login_fallido", "ana@example.com"), ("login_exitoso", "ana@example.com")]
    assert all(r.ip for r in registros)
    # Nunca se guarda la contraseña intentada
    assert all("equivocada" not in str(r.detalle) for r in registros)


@requiere_postgres
def test_descargar_un_reporte_queda_en_la_auditoria(bd, api):
    from app.models.auditoria import RegistroAuditoria
    db = bd.SessionLocal()
    ana = crear_usuario(db, "ana@example.com")
    comp = _comparacion_con_diferencia(db, ana)
    api.get(f"/api/exportacion/diferencias/{comp.id}", headers=cabecera(ana))
    registro = db.query(RegistroAuditoria).filter(RegistroAuditoria.accion == "exportacion_diferencias").one()
    db.close()
    assert registro.usuario_id == ana.id
    assert registro.detalle["comparacion_id"] == str(comp.id)


@requiere_postgres
def test_solo_el_administrador_consulta_la_auditoria(bd, api):
    db = bd.SessionLocal()
    admin = crear_usuario(db, "admin@example.com", rol="admin")
    ana = crear_usuario(db, "ana@example.com", clave=CLAVE_PRUEBA)
    api.post("/api/auth/login", json={"email": "ana@example.com", "password": CLAVE_PRUEBA})

    normal = api.get("/api/auth/auditoria", headers=cabecera(ana))
    respuesta = api.get("/api/auth/auditoria", headers=cabecera(admin))
    db.close()

    assert normal.status_code == 403
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["total"] >= 2  # el login de ana y el acceso denegado
    acciones = [r["accion"] for r in cuerpo["registros"]]
    assert acciones[0] == "acceso_denegado"  # lo más reciente primero
    assert "login_exitoso" in acciones


def test_un_fallo_al_auditar_no_tumba_la_accion(monkeypatch):
    from app.services import auditoria

    class SesionRota:
        def add(self, _):
            raise RuntimeError("la tabla no existe")

        def rollback(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr(auditoria, "_guardar", auditoria._guardar_en_base)
    monkeypatch.setattr("app.database.SessionLocal", SesionRota)
    auditoria.registrar("login_exitoso", email="ana@example.com")  # no debe lanzar


def test_registro_de_auditoria_no_guarda_datos_sensibles(auditoria_registrada):
    from app.services import auditoria
    auditoria.registrar("persona_editada", usuario=_usuario(), persona_id="p1", campos=["nombres"],
                        password="no", token="no")
    registro = auditoria_registrada[0]
    assert registro["accion"] == "persona_editada"
    assert registro["detalle"] == {"persona_id": "p1", "campos": ["nombres"]}
