"""
Envío de correos por SMTP (Gmail con contraseña de aplicación u otro proveedor).
Solo se usa para la recuperación de contraseña.
"""
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr
from html import escape

from app.config import settings
from app.utils.logger import app_logger as logger


def correo_configurado() -> bool:
    return bool(settings.SMTP_HOST and (settings.SMTP_REMITENTE or settings.SMTP_USER))


def enviar_correo(destinatario: str, asunto: str, texto: str, html: str) -> bool:
    """Envía un correo con versión de texto y HTML. Devuelve False (y lo registra) si falla."""
    if not correo_configurado():
        logger.warning("Correo no configurado (falta SMTP_HOST o el remitente); no se envió el mensaje")
        return False

    remitente = settings.SMTP_REMITENTE or settings.SMTP_USER
    msg = EmailMessage()
    msg["Subject"] = asunto
    msg["From"] = formataddr(("KondID", remitente))
    msg["To"] = destinatario
    msg.set_content(texto)
    msg.add_alternative(html, subtype="html")

    password = settings.SMTP_PASSWORD or ""
    if (settings.SMTP_HOST or "").lower() == "smtp.gmail.com":
        password = password.replace(" ", "")  # Google muestra la contraseña de aplicación en grupos de 4

    try:
        contexto = ssl.create_default_context()
        if settings.SMTP_PORT == 465:
            servidor = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20, context=contexto)
        else:
            servidor = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20)
        with servidor:
            if settings.SMTP_PORT != 465 and settings.SMTP_TLS:
                servidor.starttls(context=contexto)
            if settings.SMTP_USER and password:
                servidor.login(settings.SMTP_USER, password)
            servidor.send_message(msg)
        return True
    except Exception as e:
        logger.error(f"No se pudo enviar el correo '{asunto}': {type(e).__name__}: {e}")
        return False


def enviar_correo_recuperacion(destinatario: str, nombre: str, enlace: str, minutos: int) -> bool:
    asunto = "Restablece tu contraseña de KondID"
    texto = (
        f"Hola {nombre},\n\n"
        f"Recibimos una solicitud para restablecer la contraseña de tu cuenta de KondID.\n"
        f"Abre este enlace para elegir una nueva (sirve una sola vez y vence en {minutos} minutos):\n\n"
        f"{enlace}\n\n"
        f"Si no fuiste tú, ignora este correo: tu contraseña no cambia.\n"
    )
    nombre_html, enlace_html = escape(nombre), escape(enlace, quote=True)
    html = f"""\
<div style="font-family:Arial,Helvetica,sans-serif;max-width:480px;margin:0 auto;color:#0f172a">
  <p style="font-size:20px;font-weight:bold;margin:0 0 16px">Kond<span style="color:#2559fb">ID</span></p>
  <p>Hola {nombre_html},</p>
  <p>Recibimos una solicitud para restablecer la contraseña de tu cuenta de KondID.</p>
  <p style="margin:24px 0">
    <a href="{enlace_html}" style="background:#0071e3;color:#ffffff;text-decoration:none;padding:12px 20px;border-radius:8px;font-weight:bold">Elegir una contraseña nueva</a>
  </p>
  <p style="font-size:13px;color:#475569">El enlace sirve una sola vez y vence en {minutos} minutos.
  Si el botón no funciona, copia esta dirección en el navegador:<br><span style="word-break:break-all">{enlace_html}</span></p>
  <p style="font-size:13px;color:#475569">Si no fuiste tú, ignora este correo: tu contraseña no cambia.</p>
</div>"""
    return enviar_correo(destinatario, asunto, texto, html)
