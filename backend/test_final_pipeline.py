import json
from loguru import logger
logger.remove()

from app.services.extractor_service import extractor_service
from app.services.document_pairing_service import DocumentGroup

with open("exports/pages_doc_ai.json", "r", encoding="utf-8") as f:
    pages_data = json.load(f)

print("=" * 125)
print(f"| {'PAG':<3} | {'CEDULA':<12} | {'APELLIDOS':<22} | {'NOMBRES':<22} | {'F. NAC':<10} | {'F. EXP':<10} | {'LUGAR EXP':<20} | {'S':<2} | {'CONF':<5} |")
print("=" * 125)

class DummyLayout:
    def __init__(self, lines_data):
        class DummyLine:
            def __init__(self, d):
                self.text = d["text"]
                self.x = d["x"]
                self.y = d["y"]
                self.w = d["w"]
                self.h = d["h"]
                self.confidence = d["confidence"]
        class DummyPage:
            def __init__(self, l_list):
                self.lines = [DummyLine(ld) for ld in l_list]
        self.pages = [DummyPage(lines_data)]

for p in pages_data:
    grp = DocumentGroup(f"DOC-{p['page_num']:03d}")
    layout_obj = DummyLayout(p["lines"])
    p_info = {"pagina_numero": p["page_num"], "texto": p["full_text"], "layout": layout_obj}
    grp.front_page = p_info
    grp.back_page = p_info
    
    res = extractor_service.extraer_grupo(grp, ocr_engine="google_document_ai")
    
    print(f"| {p['page_num']:<3} | {str(res.get('identificacion')):<12} | {str(res.get('apellidos')):<22} | {str(res.get('nombres')):<22} | {str(res.get('fecha_nacimiento')):<10} | {str(res.get('fecha_expedicion')):<10} | {str(res.get('lugar_expedicion')):<20} | {str(res.get('sexo')):<2} | {str(res.get('confianza_extraccion')):<5} |")

print("=" * 125)
