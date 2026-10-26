"""
Restablece la verificación en dos pasos de una cuenta desde el servidor, para cuando ningún administrador
puede entrar (perdió el celular y los códigos de respaldo, o se cambió SECRET_KEY).

Uso, dentro del contenedor del backend:  python -m app.restablecer_doble_factor correo@ejemplo.com
"""
import sys

from sqlalchemy import func


def restablecer(email: str) -> bool:
    from app import database
    from app.models.usuario import Usuario
    from app.routers.auth import desvincular_doble_factor
    from app.services import auditoria

    db = database.SessionLocal()
    try:
        usuario = db.query(Usuario).filter(func.lower(Usuario.email) == email.strip().lower()).first()
        if not usuario:
            return False
        desvincular_doble_factor(usuario)
        db.commit()
        auditoria.registrar("2fa_restablecido_consola", usuario=usuario)
        return True
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__.strip())
        sys.exit(2)
    if restablecer(sys.argv[1]):
        print(f"Listo: {sys.argv[1]} vinculará su app de nuevo al iniciar sesión. Sus sesiones abiertas se cerraron.")
    else:
        print(f"No existe una cuenta con el correo {sys.argv[1]}.")
        sys.exit(1)
