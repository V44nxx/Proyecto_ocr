"""Envío de correos por SMTP (recuperación de contraseña), con un servidor SMTP falso: no sale nada a la red."""
import pytest

from app.config import settings
from app.services import correo_service


class SmtpFalso:
    """Registra lo que haría el servidor SMTP."""
    creados = []

    def __init__(self, host, puerto, timeout=None, context=None):
        self.host, self.puerto, self.con_ssl = host, puerto, context is not None
        self.tls = self.usuario = self.clave = None
        self.mensajes = []
        SmtpFalso.creados.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def starttls(self, context=None):
        self.tls = True

    def login(self, usuario, clave):
        self.usuario, self.clave = usuario, clave

    def send_message(self, msg):
        self.mensajes.append(msg)


@pytest.fixture
def smtp(monkeypatch):
    SmtpFalso.creados = []
    monkeypatch.setattr(correo_service.smtplib, "SMTP", SmtpFalso)
    monkeypatch.setattr(correo_service.smtplib, "SMTP_SSL", SmtpFalso)
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.gmail.com")
    monkeypatch.setattr(settings, "SMTP_USER", "kondid@example.com")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "abcd efgh ijkl mnop")
    monkeypatch.setattr(settings, "SMTP_REMITENTE", None)
    monkeypatch.setattr(settings, "SMTP_TLS", True)
    return SmtpFalso


def test_sin_configuracion_no_intenta_enviar(smtp, monkeypatch):
    monkeypatch.setattr(settings, "SMTP_HOST", None)
    assert correo_service.enviar_correo("ana@example.com", "Asunto", "texto", "<p>html</p>") is False
    assert smtp.creados == []


def test_con_el_puerto_587_usa_starttls_y_la_clave_de_aplicacion_sin_espacios(smtp, monkeypatch):
    monkeypatch.setattr(settings, "SMTP_PORT", 587)
    assert correo_service.enviar_correo("ana@example.com", "Asunto", "texto", "<p>html</p>") is True
    servidor = smtp.creados[0]
    assert (servidor.puerto, servidor.con_ssl, servidor.tls) == (587, False, True)
    assert (servidor.usuario, servidor.clave) == ("kondid@example.com", "abcdefghijklmnop")
    assert servidor.mensajes[0]["To"] == "ana@example.com"


def test_con_el_puerto_465_usa_ssl_directo(smtp, monkeypatch):
    monkeypatch.setattr(settings, "SMTP_PORT", 465)
    assert correo_service.enviar_correo("ana@example.com", "Asunto", "texto", "<p>html</p>") is True
    servidor = smtp.creados[0]
    assert servidor.con_ssl is True and servidor.tls is None


def test_si_el_servidor_falla_devuelve_false_sin_romper(smtp, monkeypatch):
    def servidor_caido(*args, **kwargs):
        raise OSError("conexión rechazada")
    monkeypatch.setattr(settings, "SMTP_PORT", 587)
    monkeypatch.setattr(correo_service.smtplib, "SMTP", servidor_caido)
    assert correo_service.enviar_correo("ana@example.com", "Asunto", "texto", "<p>html</p>") is False


def test_el_correo_de_recuperacion_lleva_el_enlace_y_escapa_el_nombre(smtp, monkeypatch):
    monkeypatch.setattr(settings, "SMTP_PORT", 587)
    enlace = "https://app.example.com/restablecer-contrasena?token=abc"
    assert correo_service.enviar_correo_recuperacion("ana@example.com", "<b>Ana</b>", enlace, 30) is True
    msg = smtp.creados[0].mensajes[0]
    html = msg.get_body(preferencelist=("html",)).get_content()
    texto = msg.get_body(preferencelist=("plain",)).get_content()
    assert enlace in texto and "30 minutos" in texto
    assert "&lt;b&gt;Ana&lt;/b&gt;" in html and "<b>Ana</b>" not in html
