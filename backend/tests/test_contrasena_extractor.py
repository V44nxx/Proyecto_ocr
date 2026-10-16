"""
Pruebas unitarias para el extractor especializado de Contraseñas (Comprobantes en trámite).
"""
import pytest
from app.services.extractor_service import extractor_service

TEXTO_CONTRASEÑA_YURELI = """
REGISTRADURIA NACIONAL DEL ESTADO CIVIL
CONTRASEÑA
DUPLICADO TI
1.117.967.915

APELLIDOS / NOMBRES:
MOSQUERA CHANTRE
YURELI

FECHA Y LUGAR DE NACIMIENTO:
08-ENE-2008
CARTAGENA DEL CHAIRA - CAQUETA

FECHA DE EXPEDICION:
08-JUN-2017

SEXO:
FEMENINO

LUGAR DE PREPARACION:
CARTAGENA DEL CHAIRA - CARTAGENA DE CHAIRA

OFICINA DE ENTREGA:
CARTAGENA DEL CHAIRA - CARTAGENA DE CHAIRA

• Escanee el código para verificar su autenticidad
• El titular tendrá un plazo máximo de
  (1) año para reclamar el documento
  a partir de la fecha de producción.

ESTE COMPROBANTE ES
VALIDO HASTA EL 15-NOV-2024
8511748832 15-MAY-2024
"""


def test_extractor_contrasena_yureli():
    res = extractor_service.extraer(TEXTO_CONTRASEÑA_YURELI, ocr_engine="test_docai")

    assert res["tipo_documento"] == "CONTRASEÑA"
    assert res["identificacion"] == "1117967915"
    assert res["nombres"] == "YURELI"
    assert res["apellidos"] == "MOSQUERA CHANTRE"
    assert res["nombre_completo"] == "YURELI MOSQUERA CHANTRE"
    assert res["fecha_nacimiento"] == "2008-01-08"
    assert res["fecha_expedicion"] == "2017-06-08"
    # Verificar que NO tomó la fecha de vigencia del comprobante (15-NOV-2024)
    assert res["fecha_expedicion"] != "2024-11-15"
    assert res["sexo"] == "F"
    assert "CARTAGENA DEL CHAIRA" in res["lugar_expedicion"]
    assert res["requiere_revision"] is False
    assert res["estado_registro"] == "VALID"
    assert res["detalles_campos"]["subtipo_tramite"] == "TARJETA_IDENTIDAD"
    assert res["detalles_campos"]["fecha_vencimiento_tramite"] == "2024-11-15"


def test_extractor_contrasena_cedula_adulto():
    texto_cc = """
    REGISTRADURIA NACIONAL DEL ESTADO CIVIL
    COMPROBANTE DE DOCUMENTO EN TRÁMITE
    CONTRASEÑA
    DUPLICADO CC
    1.085.321.456

    APELLIDOS / NOMBRES:
    RODRIGUEZ PEREZ
    CARLOS ANDRES

    FECHA Y LUGAR DE NACIMIENTO:
    14-MAY-1995
    PASTO - NARIÑO

    FECHA DE EXPEDICION:
    20-MAY-2013

    SEXO:
    MASCULINO

    LUGAR DE PREPARACION:
    PASTO - NARIÑO

    ESTE COMPROBANTE ES VALIDO HASTA EL 30-DIC-2025
    """
    res = extractor_service.extraer(texto_cc, ocr_engine="test_docai")

    assert res["tipo_documento"] == "CONTRASEÑA"
    assert res["identificacion"] == "1085321456"
    assert res["nombres"] == "CARLOS ANDRES"
    assert res["apellidos"] == "RODRIGUEZ PEREZ"
    assert res["nombre_completo"] == "CARLOS ANDRES RODRIGUEZ PEREZ"
    assert res["fecha_nacimiento"] == "1995-05-14"
    assert res["fecha_expedicion"] == "2013-05-20"
    assert res["fecha_expedicion"] != "2025-12-30"
    assert res["sexo"] == "M"
    assert res["requiere_revision"] is False
    assert res["detalles_campos"]["subtipo_tramite"] == "CEDULA_CIUDADANIA"
