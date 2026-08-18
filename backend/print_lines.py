import json

with open("exports/pages_doc_ai.json", "r", encoding="utf-8") as f:
    pages = json.load(f)

for p in pages:
    print(f"\n==================== PAGE {p['page_num']} ====================")
    for l in p["lines"]:
        print(f"L{l['idx']:02d} [y={l['y']:.3f}, x={l['x']:.3f}, w={l['w']:.3f}, h={l['h']:.3f}]: {repr(l['text'])}")
