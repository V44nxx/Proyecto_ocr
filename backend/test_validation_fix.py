"""
Prueba final de validación para las 15 primeras páginas con todos los fixes aplicados.
"""
import sys
import os
sys.path.insert(0, 'backend')

import fitz
import cv2
import numpy as np
from app.services.google_document_ai_service import google_document_ai_service
from app.services.extractor_service import extractor_service

pdf_path = "backend/uploads/632f542f-51fa-4652-8e2f-c55931891d62_DOCUMENTACION PARTICIPANTES 3574135.pdf"
doc = fitz.open(pdf_path)

print(f"Abierto PDF: {len(doc)} páginas. Procesando 10 páginas con los nuevos algoritmos:\n")

for i in range(10):
    pagina = doc[i]
    pix = pagina.get_pixmap(dpi=300)
    img_np = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    if pix.n == 3:
        img_np = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)

    success, img_encoded = cv2.imencode(".png", img_np)
    img_bytes = img_encoded.tobytes()

    texto_docai, _ = google_document_ai_service.procesar_imagen(img_bytes, mime_type="image/png")
    datos = extractor_service.extraer(texto_docai)

    print(f"=== PÁGINA {i+1} ===")
    print(f"  Cédula: {datos.get('identificacion')}")
    print(f"  Nombres: {datos.get('nombres')}")
    print(f"  Apellidos: {datos.get('apellidos')}")
    print(f"  F. Nacimiento: {datos.get('fecha_nacimiento')}")
    print(f"  F. Expedición: {datos.get('fecha_expedicion')}")
    print(f"  Lugar Expedición: {datos.get('lugar_expedicion')}")
    print(f"  Sexo: {datos.get('sexo')}")
    print(f"  Confianza: {datos.get('confianza_extraccion')}%")
    print("-" * 60)
