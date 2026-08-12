"""Modelo SQLAlchemy: Comparacion"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class Comparacion(Base):
    __tablename__ = "comparaciones"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    usuario_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True)
    nombre_archivo = Column(String(500), nullable=False)
    nombre_original = Column(String(500), nullable=False)
    ruta_archivo = Column(String(1000), nullable=True)

    # Estadísticas
    total_registros_bd = Column(Integer, default=0)
    total_registros_excel = Column(Integer, default=0)
    total_coincidentes = Column(Integer, default=0)
    total_diferentes = Column(Integer, default=0)
    total_faltantes_bd = Column(Integer, default=0)
    total_nuevos_bd = Column(Integer, default=0)

    # Estado
    estado = Column(String(50), default="pendiente")
    mensaje_error = Column(Text, nullable=True)

    # Timestamps
    fecha_carga = Column(DateTime(timezone=True), default=datetime.utcnow)
    fecha_ejecucion = Column(DateTime(timezone=True), nullable=True)
    tiempo_procesamiento_ms = Column(Integer, nullable=True)

    # Relaciones
    usuario = relationship("Usuario", back_populates="comparaciones")
    diferencias = relationship("Diferencia", back_populates="comparacion", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Comparacion {self.nombre_original} [{self.estado}]>"
