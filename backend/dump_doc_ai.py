import fitz
import cv2
import json
from app.services.google_document_ai_service import google_document_ai_service
from app.utils.image_processor import image_processor

pdf_path = r"C:\Users\USUARIO\.gemini\antigravity-ide\brain\8df96967-4c7a-492a-9e72-483a96a3ea4c\.user_uploaded\media_1787002925512.pdf"
doc = fitz.open(pdf_path)

all_pages_data = []

for i in range(len(doc)):
    page = doc[i]
    pix = page.get_pixmap(dpi=300)
    img_np = image_processor._pixmap_to_numpy(pix)
    _, img_encoded = cv2.imencode(".png", img_np)
    res_est = google_document_ai_service.procesar_documento_estructurado(img_encoded.tobytes(), mime_type="image/png", pagina_num_base=i + 1)
    page_lines = []
    if res_est.pages:
        for idx, l in enumerate(res_est.pages[0].lines):
            page_lines.append({
                "idx": idx,
                "text": l.text,
                "x": round(l.x, 4),
                "y": round(l.y, 4),
                "w": round(l.w, 4),
                "h": round(l.h, 4),
                "confidence": round(l.confidence, 4)
            })
    all_pages_data.append({
        "page_num": i + 1,
        "full_text": res_est.text,
        "lines": page_lines
    })

with open("exports/pages_doc_ai.json", "w", encoding="utf-8") as f:
    json.dump(all_pages_data, f, ensure_ascii=False, indent=2)

print("Dumped all 9 pages Document AI data to exports/pages_doc_ai.json successfully.")
