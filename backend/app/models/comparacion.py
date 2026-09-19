"""Modelo SQLAlchemy: Comparacion"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Text, ForeignKey, LargeBinary
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, deferred
from app.database import Base


class Comparacion(Base):
    __tablename__ = "comparaciones"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    usuario_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True)
    nombre_archivo = Column(String(500), nullable=False)
    nombre_original = Column(String(500), nullable=False)
    ruta_archivo = Column(String(1000), nullable=True)
    # Respaldo persistente de la planilla Excel en BD para evitar pérdida de datos tras reinicio/commit
    archivo_binario = deferred(Column(LargeBinary, nullable=True))

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

    def obtener_ruta_o_restaurar(self, db_session=None):
        """
        Retorna la ruta Path del archivo Excel en disco. Si no existe físicamente (ej. tras
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
                    nombre = self.nombre_archivo or f"comp_{self.id}.xlsx"
                    ruta = settings.upload_path / nombre
                ruta.parent.mkdir(parents=True, exist_ok=True)
                ruta.write_bytes(self.archivo_binario)
                self.ruta_archivo = str(ruta)
                if db_session:
                    try:
                        db_session.commit()
                    except Exception:
                        pass
                _log.info(f"Excel auto-restaurado en disco desde PostgreSQL: {ruta}")
                return ruta
            except Exception as e:
                _log.warning(f"No se pudo restaurar archivo binario de comparación {self.id}: {e}")
                return None
        return None

    def __repr__(self):
        return f"<Comparacion {self.nombre_original} [{self.estado}]>"
