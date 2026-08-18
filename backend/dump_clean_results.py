import json
import warnings
warnings.filterwarnings("ignore")
from app.services.extractor_service import extractor_service
from app.services.document_pairing_service import DocumentGroup

with open("exports/pages_doc_ai.json", "r", encoding="utf-8") as f:
    pages_data = json.load(f)

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

rows = []
for p in pages_data:
    p_num = p["page_num"]
    grp = DocumentGroup(f"DOC-{p_num:03d}")
    layout_obj = DummyLayout(p["lines"])
    p_info = {"pagina_numero": p_num, "texto": p["full_text"], "layout": layout_obj}
    grp.front_page = p_info
    grp.back_page = p_info
    res = extractor_service.extraer_grupo(grp, ocr_engine="google_document_ai")
    rows.append((
        p_num,
        res.get("identificacion"),
        res.get("apellidos"),
        res.get("nombres"),
        res.get("fecha_nacimiento"),
        res.get("fecha_expedicion"),
        res.get("lugar_expedicion"),
        res.get("sexo"),
        res.get("confianza_extraccion")
    ))

with open("exports/final_results_clean.txt", "w", encoding="utf-8") as f:
    f.write("=" * 125 + "\n")
    f.write(f"| {'PAG':<3} | {'CEDULA':<12} | {'APELLIDOS':<22} | {'NOMBRES':<22} | {'F. NAC':<10} | {'F. EXP':<10} | {'LUGAR EXP':<20} | {'S':<2} | {'CONF':<5} |\n")
    f.write("=" * 125 + "\n")
    for r in rows:
        f.write(f"| {r[0]:<3} | {str(r[1]):<12} | {str(r[2]):<22} | {str(r[3]):<22} | {str(r[4]):<10} | {str(r[5]):<10} | {str(r[6]):<20} | {str(r[7]):<2} | {str(r[8]):<5} |\n")
    f.write("=" * 125 + "\n")

print("Saved cleanly to exports/final_results_clean.txt")
