"""Modelo SQLAlchemy: Diferencia"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class Diferencia(Base):
    __tablename__ = "diferencias"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    comparacion_id = Column(UUID(as_uuid=True), ForeignKey("comparaciones.id", ondelete="CASCADE"), nullable=False)
    numero_identificacion = Column(String(20), nullable=False, index=True)
    campo = Column(String(100), nullable=True)
    valor_bd = Column(Text, nullable=True)
    valor_excel = Column(Text, nullable=True)
    tipo_diferencia = Column(String(20), nullable=False)  # igual|diferente|faltante_bd|nuevo_bd
    fecha_registro = Column(DateTime(timezone=True), default=datetime.utcnow)

    # Relaciones
    comparacion = relationship("Comparacion", back_populates="diferencias")

    def __repr__(self):
        return f"<Diferencia {self.numero_identificacion} - {self.campo}: {self.tipo_diferencia}>"
