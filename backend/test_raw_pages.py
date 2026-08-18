import fitz
import cv2
from app.services.google_document_ai_service import google_document_ai_service
from app.utils.image_processor import image_processor

pdf_path = r"C:\Users\USUARIO\.gemini\antigravity-ide\brain\8df96967-4c7a-492a-9e72-483a96a3ea4c\.user_uploaded\media_1787002925512.pdf"
doc = fitz.open(pdf_path)

for i in [0, 1, 3, 4, 5, 6, 7]:
    page = doc[i]
    pix = page.get_pixmap(dpi=300)
    img_np = image_processor._pixmap_to_numpy(pix)
    _, img_encoded = cv2.imencode(".png", img_np)
    res_est = google_document_ai_service.procesar_documento_estructurado(img_encoded.tobytes(), mime_type="image/png", pagina_num_base=i + 1)
    print(f"======================== PAGE {i+1} RAW LINES ========================")
    for idx, l in enumerate(res_est.pages[0].lines):
        print(f"L{idx:02d} [y={l.y:.3f}, x={l.x:.3f}, w={l.w:.3f}, h={l.h:.3f}]: {repr(l.text)}")
