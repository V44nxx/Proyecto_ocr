"""Cuánto tarda en verse el contenido al cambiar de módulo, con la latencia de producción (210 ms).

Mide desde el clic en el menú hasta que la pantalla nueva está dibujada (su menú marca el módulo) y ya no
tiene esqueletos de carga. Necesita el entorno de punta a punta de docs/PRUEBAS.md (frontend en 3000).
Uso: python pruebas/rendimiento/medir_navegacion.py <semilla_ids.json> <carpeta_salida> <etiqueta>
"""
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

IDS = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
S = Path(sys.argv[2])
S.mkdir(parents=True, exist_ok=True)
ETIQUETA = sys.argv[3]
FRONT = "http://127.0.0.1:3000"
MODULOS = [("Documentos PDF", "/documentos"), ("Personas", "/personas"), ("Exportación", "/exportacion"),
           ("Comparación", "/comparacion"), ("Seguimiento de fichas", "/seguimiento"), ("Dashboard", "/dashboard")]

LISTA = """(ruta) => location.pathname === ruta
    && document.querySelector(`aside a[aria-current="page"][href="${ruta}"]`)
    && !document.querySelector('main .animate-pulse, main .skeleton')"""

with sync_playwright() as p:
    nav = p.chromium.launch(channel="chrome", headless=True)
    ctx = nav.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    cdp = ctx.new_cdp_session(page)
    cdp.send("Network.enable")
    cdp.send("Network.emulateNetworkConditions",
             {"offline": False, "latency": 210, "downloadThroughput": 2_500_000, "uploadThroughput": 1_000_000})
    page.goto(FRONT + "/")
    page.fill("#email", "ana@example.com")
    page.fill("#password", IDS["clave"])
    page.click("button[type=submit]")
    page.wait_for_url("**/dashboard", timeout=30000)
    page.wait_for_function(LISTA, arg="/dashboard", timeout=30000)
    page.wait_for_timeout(1500)

    resultados = []
    for vuelta in ("primera visita", "segunda visita"):
        for nombre, ruta in MODULOS:
            enlace = page.locator("aside").get_by_text(nombre, exact=True).first
            enlace.evaluate("e => e.addEventListener('click', () => { window.__t0 = performance.now(); }, { once: true })")
            enlace.click()
            page.wait_for_function(LISTA, arg=ruta, timeout=30000, polling="raf")
            ms = page.evaluate("performance.now() - window.__t0")
            resultados.append({"vuelta": vuelta, "modulo": nombre, "ms": round(ms)})
            page.wait_for_timeout(1200)
    nav.close()

print(f"== {ETIQUETA}: hasta ver el contenido")
for vuelta in ("primera visita", "segunda visita"):
    filas = [r for r in resultados if r["vuelta"] == vuelta]
    print(f"  {vuelta}: promedio {sum(r['ms'] for r in filas) / len(filas):.0f} ms")
    for r in filas:
        print(f"    {r['modulo']:<22} {r['ms']:>5} ms")
(S / f"contenido_{ETIQUETA}.json").write_text(json.dumps(resultados, ensure_ascii=False, indent=1), encoding="utf-8")
