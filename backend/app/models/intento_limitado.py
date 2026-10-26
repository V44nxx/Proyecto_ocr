"""Modelo SQLAlchemy: intentos que cuentan para un límite (login fallido, código equivocado, etc.)"""
from sqlalchemy import BigInteger, Column, DateTime, Index, String
from app.database import Base


class IntentoLimitado(Base):
    __tablename__ = "intentos_limitados"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    limitador = Column(String(40), nullable=False)
    # Hash SHA-256 del correo, la IP o el usuario: para contar no hace falta guardar el dato
    clave = Column(String(64), nullable=False)
    momento = Column(DateTime(timezone=True), nullable=False, index=True)

    __table_args__ = (Index("ix_intentos_limitados_busqueda", "limitador", "clave", "momento"),)

    def __repr__(self):
        return f"<IntentoLimitado {self.limitador} {self.momento}>"
