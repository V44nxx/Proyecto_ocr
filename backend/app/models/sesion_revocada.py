"""Modelo SQLAlchemy: sesiones cerradas antes de vencer (su identificador ya no se acepta)"""
from sqlalchemy import Column, String, DateTime
from app.database import Base


class SesionRevocada(Base):
    __tablename__ = "sesiones_revocadas"

    # Identificador de la sesión (jti del token); se guarda hasta que el token habría vencido
    jti = Column(String(64), primary_key=True)
    expira = Column(DateTime(timezone=True), nullable=False, index=True)

    def __repr__(self):
        return f"<SesionRevocada {self.jti}>"
