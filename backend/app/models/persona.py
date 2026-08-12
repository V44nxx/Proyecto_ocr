"""Modelo SQLAlchemy: Persona"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Date, DateTime, Numeric, Boolean, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.database import Base


class Persona(Base):
    __tablename__ = "personas"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    documento_id = Column(UUID(as_uuid=True), ForeignKey("documentos.id", ondelete="SET NULL"), nullable=True)

    # Datos extraídos
    numero_identificacion = Column(String(20), unique=True, nullable=False, index=True)
    nombres = Column(String(200), nullable=True)
    apellidos = Column(String(200), nullable=True)
    fecha_nacimiento = Column(Date, nullable=True)
    fecha_expedicion = Column(Date, nullable=True)
    lugar_expedicion = Column(String(200), nullable=True)
    sexo = Column(String(10), nullable=True)

    # Control de calidad
    confianza_extraccion = Column(Numeric(5, 2), nullable=True)
    requiere_revision = Column(Boolean, default=False)
    campos_revisados = Column(JSONB, default=list)
    texto_ocr_crudo = Column(Text, nullable=True)

    # Timestamps
    fecha_registro = Column(DateTime(timezone=True), default=datetime.utcnow)
    fecha_actualizacion = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relaciones
    documento = relationship("Documento", back_populates="personas")

    def nombre_completo(self) -> str:
        partes = []
        if self.nombres:
            partes.append(self.nombres)
        if self.apellidos:
            partes.append(self.apellidos)
        return " ".join(partes)

    def __repr__(self):
        return f"<Persona {self.numero_identificacion} - {self.nombre_completo()}>"
