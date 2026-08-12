"""Paquete de modelos SQLAlchemy"""
from app.models.usuario import Usuario
from app.models.documento import Documento
from app.models.persona import Persona
from app.models.comparacion import Comparacion
from app.models.diferencia import Diferencia

__all__ = ["Usuario", "Documento", "Persona", "Comparacion", "Diferencia"]
