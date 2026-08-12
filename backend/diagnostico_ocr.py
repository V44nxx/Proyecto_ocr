"""
DIAGNÓSTICO OCR — Ejecutar con:
  python diagnostico_ocr.py
Analiza el último PDF subido y muestra exactamente qué texto produce el pipeline.
"""
import os, sys, re, glob
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault("DATABASE_URL", "")

import fitz  # PyMuPDF
import cv2
import numpy as np
import pytesseract

# ── Configurar Tesseract ──────────────────────────────────────────────────────
tess_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
if os.path.exists(tess_path):
    pytesseract.pytesseract.tesseract_cmd = tess_path
print(f"Tesseract: {pytesseract.get_tesseract_version()}")
print(f"Idiomas: {pytesseract.get_languages()}")
print("=" * 70)

# ── Encontrar PDF más reciente ────────────────────────────────────────────────
uploads_dir = os.path.join(os.path.dirname(__file__), "uploads")
pdfs = sorted(glob.glob(os.path.join(uploads_dir, "*.pdf")), key=os.path.getmtime)

if not pdfs:
    print("❌ No hay PDFs en uploads/. Sube un PDF primero.")
    sys.exit(1)

pdf_path = pdfs[-1]
print(f"📄 PDF analizado: {os.path.basename(pdf_path)}")
print(f"   Tamaño: {os.path.getsize(pdf_path):,} bytes")
print("=" * 70)

doc = fitz.open(pdf_path)
print(f"📑 Total páginas: {len(doc)}")
print()

MAX_PAGINAS = 5  # analizar máximo 5 páginas para no tardar demasiado
for i in range(min(len(doc), MAX_PAGINAS)):
    pagina = doc[i]
    print(f"{'─'*70}")
    print(f"PÁGINA {i+1}/{len(doc)}")

    # ── 1. Texto nativo de PyMuPDF ────────────────────────────────────────
    texto_nativo = pagina.get_text("text").strip()
    palabras_nativas = re.findall(r"[A-Za-záéíóúñÁÉÍÓÚÑ]{3,}", texto_nativo)
    print(f"\n[1] TEXTO NATIVO PyMuPDF ({len(texto_nativo)} chars, {len(palabras_nativas)} palabras útiles):")
    if texto_nativo:
        print(texto_nativo[:600])
    else:
        print("  (vacío — página escaneada, se usará OCR de imagen)")

    # ── 2. Renderizar a imagen ────────────────────────────────────────────
    pix = pagina.get_pixmap(dpi=300)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    if pix.n == 4:
        img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
    elif pix.n == 1:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    elif pix.n == 3:
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    print(f"\n[2] IMAGEN renderizada: {img.shape[1]}x{img.shape[0]}px")

    # ── 3. Tesseract sin preprocesamiento ────────────────────────────────
    t_raw = pytesseract.image_to_string(gray, lang="spa", config="--oem 3 --psm 6")
    palabras_raw = re.findall(r"[A-Za-záéíóúñÁÉÍÓÚÑ]{3,}", t_raw)
    print(f"\n[3] TESSERACT crudo (--psm 6, sin preprocesamiento) — {len(palabras_raw)} palabras:")
    print(t_raw[:600] if t_raw.strip() else "  (vacío)")

    # ── 4. Tesseract con umbralización OTSU ─────────────────────────────
    _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    t_otsu = pytesseract.image_to_string(otsu, lang="spa", config="--oem 3 --psm 6")
    palabras_otsu = re.findall(r"[A-Za-záéíóúñÁÉÍÓÚÑ]{3,}", t_otsu)
    print(f"\n[4] TESSERACT con OTSU — {len(palabras_otsu)} palabras:")
    print(t_otsu[:600] if t_otsu.strip() else "  (vacío)")

    # ── 5. Tesseract con psm 11 (texto disperso) ────────────────────────
    t_psm11 = pytesseract.image_to_string(gray, lang="spa", config="--oem 3 --psm 11")
    palabras_psm11 = re.findall(r"[A-Za-záéíóúñÁÉÍÓÚÑ]{3,}", t_psm11)
    print(f"\n[5] TESSERACT --psm 11 (texto disperso) — {len(palabras_psm11)} palabras:")
    print(t_psm11[:400] if t_psm11.strip() else "  (vacío)")

    # ── Ganador ──────────────────────────────────────────────────────────
    mejor = max(
        [("nativo", len(palabras_nativas)), ("psm6_raw", len(palabras_raw)),
         ("otsu", len(palabras_otsu)), ("psm11", len(palabras_psm11))],
        key=lambda x: x[1]
    )
    print(f"\n✅ MEJOR RESULTADO: [{mejor[0]}] con {mejor[1]} palabras útiles")

    if i == 0:
        print()
        print("=" * 70)
        print("RECOMENDACIÓN para ocr_service.py:")
        if len(palabras_nativas) > 5:
            print("  → El PDF tiene texto nativo. NO se necesita OCR de imagen.")
            print("    _necesita_ocr_imagen() devuelve False correctamente.")
        elif len(palabras_otsu) > len(palabras_raw):
            print("  → Usar OTSU mejora el resultado. Agregar al pipeline.")
        elif len(palabras_psm11) > len(palabras_raw):
            print("  → Usar --psm 11 mejora el resultado para este layout.")
        else:
            print("  → El resultado ya es óptimo con --psm 6.")
        print("=" * 70)

doc.close()
print("\n✅ Diagnóstico completado.")
