"""Modelo SQLAlchemy: Usuario"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    nombre = Column(String(200), nullable=False)
    rol = Column(String(50), default="usuario")
    activo = Column(Boolean, default=True)
    fecha_creacion = Column(DateTime(timezone=True), default=datetime.utcnow)
    fecha_actualizacion = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    ultimo_login = Column(DateTime(timezone=True), nullable=True)

    # Relaciones
    documentos = relationship("Documento", back_populates="usuario", lazy="dynamic")
    comparaciones = relationship("Comparacion", back_populates="usuario", lazy="dynamic")

    def __repr__(self):
        return f"<Usuario {self.email} [{self.rol}]>"
