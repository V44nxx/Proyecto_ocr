"""Tiempo y aciertos del OCR sobre una ficha inventada (ficha_sintetica.py). Nunca contra producción.

Modos:
  rapid   RapidOCR de verdad, en esta máquina
  docai   Document AI simulado: cada página tarda SEGUNDOS_DOCAI y devuelve el texto exacto de la cara
          (mide cuántas páginas se leen a la vez, no la calidad de Google)
Uso, desde backend/ y con DATABASE_URL apuntando a la base de prueba sembrada con pruebas/semilla.py:
  PYTHONPATH=. python ../pruebas/ocr/medir_ocr.py <modo> <personas> <carpeta_salida> [nucleos]
`nucleos` fija os.cpu_count() para imitar el VPS de producción (2). Deja la ficha y el detalle por persona
en la carpeta de salida y borra de la base lo que creó.
"""
import json
import os
import sys
import time
import uuid
from pathlib import Path

S = Path(__file__).parent
sys.path.insert(0, str(S))
MODO, PERSONAS, SALIDA = sys.argv[1], int(sys.argv[2]), Path(sys.argv[3])
NUCLEOS = int(sys.argv[4]) if len(sys.argv) > 4 else 2
SEGUNDOS_DOCAI = 1.5

os.cpu_count = lambda: NUCLEOS

import ficha_sintetica  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models import Documento, Persona, Usuario  # noqa: E402
from app.services import ocr_service as modulo_ocr  # noqa: E402
from app.services.google_document_ai_service import StructuredDocumentAIResult  # noqa: E402

ruta = SALIDA / f"ficha_{PERSONAS}.pdf"
gente = ficha_sintetica.generar(ruta, PERSONAS)

docai = modulo_ocr.google_document_ai_service
if MODO == "docai":
    caras = {}
    for i, p in enumerate(gente):
        caras[2 * i + 1] = ficha_sintetica.texto_de_pagina(p, "frente")
        caras[2 * i + 2] = ficha_sintetica.texto_de_pagina(p, "reverso")

    def falso(contenido, mime_type="image/jpeg", pagina_num_base=1):
        time.sleep(SEGUNDOS_DOCAI)
        return StructuredDocumentAIResult(text=caras[pagina_num_base], tiempo_ms=SEGUNDOS_DOCAI * 1000, pages=[])

    docai._disponible = True
    docai.en_linea = lambda: True
    docai.procesar_documento_estructurado = falso
else:
    docai._disponible = False

db = SessionLocal()
usuario = db.query(Usuario).filter(Usuario.email == "ana@example.com").first()
documento = Documento(id=uuid.uuid4(), usuario_id=usuario.id, nombre_archivo=ruta.name, nombre_original=ruta.name,
                      ruta_archivo=str(ruta), estado="procesando", metadatos={})
db.add(documento)
db.commit()

inicio = time.perf_counter()
resultado = modulo_ocr.ocr_service.procesar_pdf(str(ruta), str(documento.id), db_externa=db)
segundos = time.perf_counter() - inicio

leidas = {str(p.numero_identificacion): p for p in db.query(Persona).filter(Persona.documento_id == documento.id)}
campos = ("numero_identificacion", "nombres", "apellidos", "fecha_nacimiento", "sexo")
aciertos = {c: 0 for c in campos}
for p in gente:
    leida = leidas.get(p["numero_identificacion"])
    if not leida:
        continue
    for c in campos:
        valor = getattr(leida, c, None)
        valor = valor.isoformat() if hasattr(valor, "isoformat") else (str(valor).strip().upper() if valor else "")
        aciertos[c] += valor == p[c]
total = sum(aciertos.values())
detalle = []
for leida in leidas.values():
    detalle.append({c: (getattr(leida, c).isoformat() if hasattr(getattr(leida, c, None), "isoformat") else getattr(leida, c, None)) for c in campos})
(SALIDA / f"detalle_{MODO}.json").write_text(json.dumps({"esperado": [{c: p[c] for c in campos} for p in gente], "leido": detalle}, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps({
    "modo": MODO, "personas": PERSONAS, "paginas": resultado["total_paginas"], "nucleos": NUCLEOS,
    "segundos": round(segundos, 2), "por_pagina": round(segundos / max(resultado["total_paginas"], 1), 2),
    "personas_leidas": len(leidas), "aciertos": aciertos,
    "aciertos_pct": round(100 * total / (len(campos) * PERSONAS), 1), "errores": resultado["errores"],
}, ensure_ascii=False))
db.query(Persona).filter(Persona.documento_id == documento.id).delete()
db.query(Documento).filter(Documento.id == documento.id).delete()
db.commit()
db.close()
