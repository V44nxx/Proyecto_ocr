"""
Script de diagnóstico para guardar el texto crudo y la extracción de las primeras 5 páginas.
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

with open("backend/diag_output.txt", "w", encoding="utf-8") as out:
    out.write(f"Abierto PDF: {len(doc)} páginas\n\n")

    for i in range(5):
        pagina = doc[i]
        pix = pagina.get_pixmap(dpi=300)
        img_np = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        if pix.n == 3:
            img_np = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)

        success, img_encoded = cv2.imencode(".png", img_np)
        img_bytes = img_encoded.tobytes()

        texto_docai, _ = google_document_ai_service.procesar_imagen(img_bytes, mime_type="image/png")
        datos = extractor_service.extraer(texto_docai)

        out.write(f"=== PÁGINA {i+1} ===\n")
        out.write(f"Cédula: {datos.get('identificacion')}\n")
        out.write(f"Nombres: {datos.get('nombres')}\n")
        out.write(f"Apellidos: {datos.get('apellidos')}\n")
        out.write(f"F. Nacimiento: {datos.get('fecha_nacimiento')}\n")
        out.write(f"F. Expedición: {datos.get('fecha_expedicion')}\n")
        out.write(f"Lugar Expedición: {datos.get('lugar_expedicion')}\n")
        out.write(f"Sexo: {datos.get('sexo')}\n")
        out.write(f"Confianza: {datos.get('confianza_extraccion')}%\n")
        out.write(f"--- TEXTO CRUDO GOOGLE DOC AI ---\n{texto_docai}\n")
        out.write("=" * 80 + "\n\n")
        out.flush()

print("Diagnóstico completado en backend/diag_output.txt")
