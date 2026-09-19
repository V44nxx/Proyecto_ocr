"""Modelo SQLAlchemy: Documento"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, BigInteger, DateTime, Numeric, Text, ForeignKey, Boolean, LargeBinary
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship, deferred
from app.database import Base


class Documento(Base):
    __tablename__ = "documentos"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    usuario_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True)
    nombre_archivo = Column(String(500), nullable=False)
    nombre_original = Column(String(500), nullable=False)
    ruta_archivo = Column(String(1000), nullable=True)
    tamano_bytes = Column(BigInteger, nullable=True)
    total_paginas = Column(Integer, default=0)
    estado = Column(String(50), default="pendiente")   # pendiente|procesando|completado|error|revision
    confianza_ocr = Column(Numeric(5, 2), nullable=True)
    mensaje_error = Column(Text, nullable=True)
    tiempo_procesamiento_ms = Column(Integer, nullable=True)
    fecha_carga = Column(DateTime(timezone=True), default=datetime.utcnow)
    fecha_procesamiento = Column(DateTime(timezone=True), nullable=True)
    metadatos = Column(JSONB, default=dict)
    visible_en_subida = Column(Boolean, default=True, nullable=False)
    # Respaldo persistente en BD para evitar pérdida de vista previa tras reinicios o nuevos commits
    archivo_binario = deferred(Column(LargeBinary, nullable=True))

    # Relaciones
    usuario = relationship("Usuario", back_populates="documentos")
    personas = relationship("Persona", back_populates="documento", cascade="all, delete-orphan", foreign_keys="[Persona.documento_id]")

    @property
    def total_personas(self) -> int:
        """Retorna el total de personas en BD o el histórico de metadatos"""
        if self.personas:
            return len(self.personas)
        if self.metadatos and isinstance(self.metadatos, dict):
            if self.metadatos.get("personas_extraidas_datos"):
                return len(self.metadatos["personas_extraidas_datos"])
            return int(self.metadatos.get("personas_extraidas", 0))
        return 0

    def obtener_ruta_o_restaurar(self, db_session=None):
        """
        Retorna la ruta Path del archivo PDF en disco. Si no existe físicamente (ej. tras
        reinicio o despliegue de contenedor en Dokploy), lo restaura automáticamente
        desde archivo_binario almacenado en la base de datos PostgreSQL.
        """
        from pathlib import Path
        from app.config import settings
        import logging
        _log = logging.getLogger(__name__)

        ruta = Path(self.ruta_archivo) if self.ruta_archivo else None
        if ruta and ruta.exists() and ruta.is_file():
            return ruta

        if self.archivo_binario:
            try:
                if not ruta:
                    nombre = self.nombre_archivo or f"{self.id}.pdf"
                    ruta = settings.upload_path / nombre
                ruta.parent.mkdir(parents=True, exist_ok=True)
                ruta.write_bytes(self.archivo_binario)
                self.ruta_archivo = str(ruta)
                if db_session:
                    try:
                        db_session.commit()
                    except Exception:
                        pass
                _log.info(f"PDF auto-restaurado en disco desde PostgreSQL: {ruta}")
                return ruta
            except Exception as e:
                _log.warning(f"No se pudo restaurar archivo binario de documento {self.id}: {e}")
                return None
        return None

    def __repr__(self):
        return f"<Documento {self.nombre_original} [{self.estado}]>"
