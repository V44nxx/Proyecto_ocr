"""Datos inventados para las pruebas de punta a punta, de carga y de seguridad.

Nunca usar contra la base de producción: crea usuarios y fichas de prueba.
Uso (desde backend/, con una base de pruebas vacía):
    DATABASE_URL=postgresql://postgres@127.0.0.1:5544/e2e PYTHONPATH=. python ../pruebas/semilla.py <carpeta>
Crea: admin, ana y beto (contraseña ClavePrueba2026!), una ficha con PDF sintético de 2 páginas para ana,
5 personas, una comparación con diferencias para ana y otra ficha para beto.
Deja los ids en <carpeta>/semilla_ids.json (los usan las demás pruebas).
"""
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "postgresql://postgres@127.0.0.1:5544/e2e")
os.environ["DEBUG"] = "false"
os.environ["GOOGLE_DOCUMENT_AI_ENABLED"] = "false"
os.environ["RAPID_OCR_ENABLED"] = "false"
os.environ.setdefault("ADMIN_EMAIL", "")

import fitz
from app.database import SessionLocal, _hash_password, create_tables
from app.models import Usuario, Documento, Persona, Comparacion
from app.models.diferencia import Diferencia

CLAVE = "ClavePrueba2026!"
salida = Path(sys.argv[1])
salida.mkdir(parents=True, exist_ok=True)
create_tables()


def pdf_sintetico(nombre, cedula, titular):
    ruta = salida / nombre
    doc = fitz.open()
    for titulo, color in (("FRENTE - CEDULA DE PRUEBA", (0.85, 0.9, 1)), ("REVERSO - CEDULA DE PRUEBA", (1, 0.95, 0.85))):
        pag = doc.new_page(width=600, height=380)
        pag.draw_rect(pag.rect, color=None, fill=color)
        pag.insert_text((40, 80), "REPUBLICA DE COLOMBIA", fontsize=22)
        pag.insert_text((40, 140), titulo, fontsize=20)
        pag.insert_text((40, 200), f"NUMERO {cedula}", fontsize=18)
        pag.insert_text((40, 250), f"{titular} (DATOS INVENTADOS)", fontsize=16)
    doc.save(ruta)
    return ruta


db = SessionLocal()


def usuario(email, nombre, rol="usuario"):
    u = Usuario(email=email, nombre=nombre, password_hash=_hash_password(CLAVE), rol=rol)
    db.add(u)
    db.commit()
    return u


admin = usuario("admin@example.com", "Admin Pruebas", "admin")
ana = usuario("ana@example.com", "Ana Pruebas")
beto = usuario("beto@example.com", "Beto Pruebas")

pdf_ana = pdf_sintetico("3300001.pdf", "1.000.000.401", "ZULY ANDREA PEREZ")
ficha_ana = Documento(usuario_id=ana.id, nombre_archivo="3300001.pdf", nombre_original="3300001.pdf", total_paginas=2,
                      estado="completado", ruta_archivo=str(pdf_ana))
pdf_beto = pdf_sintetico("3300002.pdf", "1.000.000.501", "CARLOS ÑUSTES")
ficha_beto = Documento(usuario_id=beto.id, nombre_archivo="3300002.pdf", nombre_original="3300002.pdf", total_paginas=2,
                       estado="completado", ruta_archivo=str(pdf_beto))
db.add_all([ficha_ana, ficha_beto])
db.commit()

personas_ana = []
for i, (nombres, apellidos) in enumerate([("ZULY ANDREA", "PEREZ"), ("ÁNGELA", "MORA"), ("CARLOS", "ÑUSTES"),
                                           ("BEATRIZ", "LOPEZ"), ("ADRIANA", "ZAPATA")]):
    p = Persona(usuario_id=ana.id, documento_id=ficha_ana.id, numero_identificacion=f"1000000{401 + i}",
                nombres=nombres, apellidos=apellidos, nombre_completo=f"{nombres} {apellidos}",
                tipo_documento="CEDULA_CIUDADANIA", motor_ocr="google_document_ai", estado_registro="VALID",
                requiere_revision=False, confianza_extraccion=95, grupo_documento_id=f"G-{i}",
                pagina_frente=1, pagina_reverso=2)
    db.add(p)
    personas_ana.append(p)
p_beto = Persona(usuario_id=beto.id, documento_id=ficha_beto.id, numero_identificacion="1000000501",
                 nombres="CARLOS", apellidos="ÑUSTES", nombre_completo="CARLOS ÑUSTES", tipo_documento="CEDULA_CIUDADANIA",
                 motor_ocr="google_document_ai", estado_registro="VALID", requiere_revision=False,
                 confianza_extraccion=95, grupo_documento_id="G-B", pagina_frente=1, pagina_reverso=2)
db.add(p_beto)
db.commit()

comp_ana = Comparacion(usuario_id=ana.id, nombre_archivo="planilla_ana.xlsx", nombre_original="planilla_ana.xlsx",
                       estado="completado", total_registros_excel=5, total_registros_bd=5, total_diferentes=1)
db.add(comp_ana)
db.commit()
db.add(Diferencia(comparacion_id=comp_ana.id, numero_identificacion="1000000402", campo="nombres",
                  valor_bd="ÁNGELA", valor_excel="ANGELA MARIA", tipo_diferencia="diferente"))
db.commit()

# Cuenta con listas más largas que una página: 650 personas en una ficha, 105 fichas y 150 diferencias
# (antes las pantallas mostraban como máximo 300 personas, 100 fichas y 100 diferencias)
lote = usuario("lote@example.com", "Lote Pruebas")
fichas_lote = [Documento(usuario_id=lote.id, nombre_archivo=f"31{i:05d}.pdf", nombre_original=f"31{i:05d}.pdf",
                         total_paginas=2, estado="completado") for i in range(105)]
db.add_all(fichas_lote)
db.commit()
db.add_all([Persona(usuario_id=lote.id, documento_id=fichas_lote[0].id, numero_identificacion=f"1100{i:06d}",
                    nombres="PRUEBA", apellidos=f"LOTE {i:03d}", nombre_completo=f"PRUEBA LOTE {i:03d}",
                    tipo_documento="CEDULA_CIUDADANIA", motor_ocr="google_document_ai", estado_registro="VALID",
                    requiere_revision=False, confianza_extraccion=95, grupo_documento_id=f"L-{i}",
                    pagina_frente=1, pagina_reverso=2) for i in range(650)])
comp_lote = Comparacion(usuario_id=lote.id, nombre_archivo="planilla_lote.xlsx", nombre_original="planilla_lote.xlsx",
                        estado="completado", total_registros_excel=650, total_registros_bd=650, total_diferentes=150)
db.add(comp_lote)
db.commit()
db.add_all([Diferencia(comparacion_id=comp_lote.id, numero_identificacion=f"1100{i:06d}", campo="nombres",
                       valor_bd="PRUEBA", valor_excel="PRUEBA DOS", tipo_diferencia="diferente") for i in range(150)])
db.commit()

ids = {
    "clave": CLAVE,
    "ficha_lote": str(fichas_lote[0].id), "comparacion_lote": str(comp_lote.id),
    "ficha_ana": str(ficha_ana.id), "ficha_beto": str(ficha_beto.id),
    "persona_ana": str(personas_ana[0].id), "persona_beto": str(p_beto.id),
    "comparacion_ana": str(comp_ana.id),
}
(salida / "semilla_ids.json").write_text(json.dumps(ids), encoding="utf-8")
print(json.dumps(ids))
db.close()
