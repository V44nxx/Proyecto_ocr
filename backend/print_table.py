import json
import sys
from loguru import logger
logger.remove()

from test_deterministic_parser import extraer_cedula_universal

with open("exports/pages_doc_ai.json", "r", encoding="utf-8") as f:
    pages = json.load(f)

print("=" * 120)
print(f"| {'PAG':<3} | {'CEDULA':<12} | {'APELLIDOS':<22} | {'NOMBRES':<22} | {'F. NAC':<10} | {'F. EXP':<10} | {'LUGAR EXP':<20} | {'S':<2} |")
print("=" * 120)

for p in pages:
    r = extraer_cedula_universal(p)
    print(f"| {p['page_num']:<3} | {str(r['identificacion']):<12} | {str(r['apellidos']):<22} | {str(r['nombres']):<22} | {str(r['fecha_nacimiento']):<10} | {str(r['fecha_expedicion']):<10} | {str(r['lugar_expedicion']):<20} | {str(r['sexo']):<2} |")

print("=" * 120)
