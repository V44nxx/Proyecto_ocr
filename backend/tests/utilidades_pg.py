"""
Ayudas para las pruebas que necesitan PostgreSQL real.

Se ejecutan solo si TEST_DATABASE_URL apunta a una base de pruebas desechable: el fixture `bd`
(en conftest.py) borra y recrea el esquema `public` en cada prueba.
"""
import os
import uuid

import pytest

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
requiere_postgres = pytest.mark.skipif(not TEST_DATABASE_URL, reason="Define TEST_DATABASE_URL para correr estos tests")

CLAVE_PRUEBA = "ClavePrueba2026!"


def crear_usuario(db, email, rol="usuario", clave=None):
    """Usuario con contraseña real si se pide `clave` (bcrypt es lento: solo cuando la prueba inicia sesión)."""
    from app.models.usuario import Usuario
    from app.routers.auth import crear_hash_password
    u = Usuario(email=email, nombre=email.split("@")[0].title(),
                password_hash=crear_hash_password(clave) if clave else "x", rol=rol)
    db.add(u)
    db.commit()
    return u


def token_de(usuario):
    """Sesión completa: para un administrador, como si ya hubiera pasado la verificación en dos pasos."""
    from app.routers.auth import crear_token_acceso
    return crear_token_acceso({"sub": str(usuario.id), "email": usuario.email, "ver": usuario.version_sesion or 0,
                               "mfa": True})


def cabecera(usuario):
    return {"Authorization": f"Bearer {token_de(usuario)}"}


def crear_ficha(db, usuario, nombre="3000001.pdf", paginas=2, **extra):
    from app.models.documento import Documento
    d = Documento(usuario_id=usuario.id, nombre_archivo=extra.pop("nombre_archivo", f"{uuid.uuid4()}_{nombre}"),
                  nombre_original=nombre, total_paginas=paginas, estado=extra.pop("estado", "completado"), **extra)
    db.add(d)
    db.commit()
    return d


def crear_persona(db, usuario, ficha, cedula, nombres, apellidos, **extra):
    from app.models.persona import Persona
    p = Persona(usuario_id=usuario.id, documento_id=ficha.id if ficha else None, numero_identificacion=cedula,
                nombres=nombres, apellidos=apellidos, nombre_completo=extra.pop("nombre_completo", f"{nombres} {apellidos}"),
                motor_ocr=extra.pop("motor_ocr", "google_document_ai"), estado_registro="VALID",
                requiere_revision=False, confianza_extraccion=95, grupo_documento_id=extra.pop("grupo_documento_id", "G-1"),
                **extra)
    db.add(p)
    db.commit()
    return p


def pdf_de_prueba(ruta, paginas=2):
    """PDF pequeño con texto inventado, para la vista previa."""
    import pymupdf as fitz
    doc = fitz.open()
    for i in range(paginas):
        pag = doc.new_page(width=300, height=190)
        pag.insert_text((20, 60), f"PAGINA {i + 1} - DATOS INVENTADOS", fontsize=12)
    doc.save(ruta)
    doc.close()
    return ruta
