import sys
import os
import fitz

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, 'backend')
from app.services.ocr_service import ocr_service
from app.services.document_side_classifier import document_side_classifier
from app.services.document_pairing_service import document_pairing_service
from app.services.extractor_service import extractor_service

pdf_path = sys.argv[1] if len(sys.argv) > 1 else 'C:/Users/USUARIO/.gemini/antigravity-ide/brain/8df96967-4c7a-492a-9e72-483a96a3ea4c/.user_uploaded/media_1787002925512.pdf'

if not os.path.exists(pdf_path):
    import glob
    candidates = glob.glob('backend/uploads/*3574135*.pdf')
    if candidates:
        pdf_path = candidates[0]

print(f"=== ANALIZANDO OCR DE IMAGENES: {pdf_path} ===")
doc = fitz.open(pdf_path)
total_paginas = len(doc)
print(f"Total Paginas en PDF: {total_paginas}\n")

paginas_clasificadas = []

for i in range(total_paginas):
    page = doc[i]
    texto_nativo = page.get_text("text")
    
    if ocr_service._necesita_ocr_imagen(texto_nativo):
        pix = page.get_pixmap(dpi=300)
        img_np = ocr_service.image_processor._pixmap_to_numpy(pix)
        texto_pagina, motor_usado, layout_estructurado = ocr_service._ocr_imagen(
            img_np=img_np, pagina_num=i + 1
        )
    else:
        texto_pagina = texto_nativo
        motor_usado = "texto_nativo_pdf"
        layout_estructurado = None
        
    lines = layout_estructurado.pages[0].lines if (layout_estructurado and layout_estructurado.pages) else []
    res_cara = document_side_classifier.clasificar_cara(texto_pagina, lines=lines)
    id_pre = extractor_service._extraer_identificacion(texto_pagina, texto_pagina.splitlines())
    extracted = extractor_service.extraer(texto_pagina, layout_data=layout_estructurado, pagina_num=i+1)
    
    info = {
        "pagina_numero": i + 1,
        "texto": texto_pagina,
        "layout": layout_estructurado,
        "motor": motor_usado,
        "cara": res_cara["cara"],
        "tipo_documento": res_cara["tipo_documento"],
        "confianza": res_cara["confianza"],
        "numero_identificacion": id_pre,
        "nombres": extracted.get("nombres"),
        "apellidos": extracted.get("apellidos"),
        "identificacion": extracted.get("identificacion"),
        "fecha_nacimiento": extracted.get("fecha_nacimiento"),
        "fecha_expedicion": extracted.get("fecha_expedicion"),
        "lugar_expedicion": extracted.get("lugar_expedicion"),
        "sexo": extracted.get("sexo")
    }
    paginas_clasificadas.append(info)
    print(f"============================================================")
    print(f"PAGINA {i+1}/{total_paginas} (Motor: {motor_usado})")
    print(f"  Clasificación Cara: {info['cara']} (confianza: {info['confianza']})")
    print(f"  Identificación: {info['identificacion']}")
    print(f"  Nombres: {info['nombres']} | Apellidos: {info['apellidos']}")
    print(f"  Nacimiento: {info['fecha_nacimiento']} | Expedición: {info['fecha_expedicion']} | Lugar: {info['lugar_expedicion']}")
    print(f"  Texto detectado ({len(texto_pagina.splitlines())} líneas):")
    for l in [line.strip() for line in texto_pagina.splitlines() if line.strip()][:10]:
        safe_l = l.encode('ascii', errors='replace').decode('ascii')
        print(f"    > {safe_l}")
    print()

grupos = document_pairing_service.agrupar_paginas(paginas_clasificadas)

print(f"\n=======================================================")
print(f"=== RESULTADO DE AGRUPACIÓN FÍSICA: {len(grupos)} PERSONAS/GRUPOS ===")
print(f"=======================================================")
personas_finales = []
for g in grupos:
    res = extractor_service.extraer_grupo(g)
    es_persona_valida = bool(res.get("identificacion") or (res.get("nombres") and res.get("apellidos")))
    status_str = "VALIDA" if es_persona_valida else "OMITIDA (PAGINA NO-IDENTIDAD / HUERFANA)"
    print(f"\n[GRUPO {g.group_id}] -> {status_str}")
    print(f"  Páginas físicas agrupadas: {g.pages} (Frente: Pág {g.pagina_frente}, Reverso: Pág {g.pagina_reverso})")
    print(f"  Razones: {g.reasons}")
    print(f"  -> Cédula / NUIP: {res.get('identificacion')}")
    print(f"  -> Nombres:       {res.get('nombres')}")
    print(f"  -> Apellidos:     {res.get('apellidos')}")
    print(f"  -> Nacimiento:    {res.get('fecha_nacimiento')}")
    print(f"  -> Expedición:    {res.get('fecha_expedicion')}")
    print(f"  -> Lugar Exp:     {res.get('lugar_expedicion')}")
    print(f"  -> Sexo:          {res.get('sexo')}")
    print(f"  -> Confianza Extr:{res.get('confianza_extraccion')}%")
    print(f"  -> Requiere Rev:  {res.get('requiere_revision')}")
    if es_persona_valida:
        personas_finales.append(res)

print(f"\n=======================================================")
print(f"TOTAL PERSONAS REALES ENCONTRADAS EN ESTE PDF: {len(personas_finales)}")
print(f"=======================================================")
for idx, p in enumerate(personas_finales, 1):
    print(f"{idx}. CC {p.get('identificacion')} - {p.get('nombres')} {p.get('apellidos')} (Nac: {p.get('fecha_nacimiento')}, Exp: {p.get('fecha_expedicion')}, Lugar: {p.get('lugar_expedicion')})")
