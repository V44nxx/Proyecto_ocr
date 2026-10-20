"""Modelo SQLAlchemy: registro de auditoría (quién hizo qué, cuándo y desde dónde)"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.database import Base


class RegistroAuditoria(Base):
    __tablename__ = "auditoria"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    fecha = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    # Sin llave foránea: el registro se conserva (con el id) aunque se elimine el usuario
    usuario_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    email = Column(String(255), nullable=True)
    accion = Column(String(60), nullable=False, index=True)
    ip = Column(String(64), nullable=True)
    detalle = Column(JSONB, nullable=True)

    def __repr__(self):
        return f"<RegistroAuditoria {self.accion} {self.email}>"
