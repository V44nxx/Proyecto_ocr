"""Modelo SQLAlchemy: configuración del Seguimiento de fichas (panel de Google Apps Script) por usuario"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class SeguimientoConfig(Base):
    __tablename__ = "seguimiento_config"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    usuario_id = Column(
        UUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="CASCADE"),
        nullable=False, unique=True, index=True,
    )
    correo_google = Column(String(255), nullable=True)
    url_panel = Column(String(1000), nullable=False)
    url_hoja = Column(String(1000), nullable=True)
    fecha_creacion = Column(DateTime(timezone=True), default=datetime.utcnow)
    fecha_actualizacion = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<SeguimientoConfig usuario={self.usuario_id}>"
