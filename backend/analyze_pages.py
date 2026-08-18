import json
import re

with open("exports/pages_doc_ai.json", "r", encoding="utf-8") as f:
    pages = json.load(f)

output_lines = []

for p in pages:
    output_lines.append(f"\n==================== PAGE {p['page_num']} ====================")
    for l in p["lines"]:
        clean_text = l['text'].encode('ascii', 'replace').decode('ascii')
        output_lines.append(f"L{l['idx']:02d} [y={l['y']:.3f}, x={l['x']:.3f}, w={l['w']:.3f}, h={l['h']:.3f}]: {clean_text}")

with open("exports/pages_analysis.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(output_lines))

print("Wrote analysis to exports/pages_analysis.txt")
