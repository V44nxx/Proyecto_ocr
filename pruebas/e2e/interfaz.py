"""Pruebas funcionales de la interfaz (Playwright + Chrome instalado) contra un frontend y backend de prueba.

Solo con datos inventados (pruebas/semilla.py), nunca contra producción.
Uso: python interfaz.py <carpeta_salida>
Variables de entorno:
  KONDID_IDS       semilla_ids.json que dejó semilla.py (obligatoria)
  KONDID_CORREOS   carpeta donde smtp_captura.py guarda los .eml (obligatoria)
  KONDID_EXPORTS   EXPORT_DIR del backend, para revisar que no queden Excel (opcional)
  KONDID_FRONT     por defecto http://127.0.0.1:3000
  KONDID_API       por defecto http://127.0.0.1:8000
Requiere el backend recién iniciado sobre la base recién sembrada y con SMTP_HOST apuntando al SMTP de captura.
Cada caso queda en <salida>/e2e.json con su resultado; las capturas en <salida>/capturas.
"""
import email
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from email import policy
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

SALIDA = Path(sys.argv[1])
CAPTURAS = SALIDA / "capturas"
CAPTURAS.mkdir(parents=True, exist_ok=True)
CORREOS = Path(os.environ["KONDID_CORREOS"])
EXPORTS = Path(os.environ["KONDID_EXPORTS"]) if os.environ.get("KONDID_EXPORTS") else None
IDS = json.loads(Path(os.environ["KONDID_IDS"]).read_text(encoding="utf-8"))
CLAVE = IDS["clave"]
FRONT = os.environ.get("KONDID_FRONT", "http://127.0.0.1:3000").rstrip("/")
API = os.environ.get("KONDID_API", "http://127.0.0.1:8000").rstrip("/")
NOMBRES_COOKIE = {"__Host-kondid_sesion", "kondid_sesion"}
casos = []


def caso(cid, nombre, ok, detalle=""):
    casos.append({"id": cid, "nombre": nombre, "resultado": "PASA" if ok else "FALLA", "obtenido": str(detalle)})
    print(("PASA  " if ok else "FALLA ") + f"{cid} {nombre}  {detalle}")


def api_put_json(ruta, token, cuerpo):
    req = urllib.request.Request(API + ruta, data=json.dumps(cuerpo).encode(), method="PUT",
                                 headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        return r.status


def api_get_estado(ruta, token):
    req = urllib.request.Request(API + ruta, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


def cookie_sesion(ctx):
    return next((c for c in ctx.cookies() if c["name"] in NOMBRES_COOKIE), None)


def login(page, correo, clave, esperar_dashboard=True):
    page.goto(FRONT + "/")
    page.evaluate("localStorage.clear()")
    page.context.clear_cookies()
    page.goto(FRONT + "/")
    page.fill("#email", correo)
    page.fill("#password", clave)
    page.click("button[type=submit]")
    if esperar_dashboard:
        page.wait_for_url("**/dashboard", timeout=15000)


with sync_playwright() as p:
    nav = p.chromium.launch(channel="chrome", headless=True)
    ctx = nav.new_context(viewport={"width": 1440, "height": 900}, accept_downloads=True)
    page = ctx.new_page()
    errores_js, avisos_csp, peticiones_pagina, respuestas_pagina = [], [], [], []
    page.on("pageerror", lambda e: errores_js.append(str(e)))
    page.on("console", lambda m: avisos_csp.append(m.text) if "Content Security Policy" in m.text else None)
    page.on("request", lambda r: peticiones_pagina.append(r) if "/pagina/" in r.url else None)
    page.on("response", lambda r: respuestas_pagina.append(r) if "/pagina/" in r.url else None)

    # ── Inicio de sesión ────────────────────────────────────────────
    login(page, "ana@example.com", "ClaveEquivocada1", esperar_dashboard=False)
    aviso = page.get_by_text("Credenciales incorrectas")
    expect(aviso).to_be_visible(timeout=10000)
    caso("CP-UI-01", "Contraseña equivocada: muestra el error y no entra",
         "/dashboard" not in page.url and aviso.count() > 0, aviso.first.inner_text())
    page.screenshot(path=str(CAPTURAS / "01_login_error.png"))

    login(page, "ana@example.com", CLAVE)
    caso("CP-UI-02", "Credenciales correctas: entra al panel", "/dashboard" in page.url, page.url)
    galleta = cookie_sesion(ctx)
    token_ana = galleta["value"] if galleta else None
    caso("CP-UI-19", "La sesión viaja en una cookie HttpOnly y SameSite=Strict, fuera del alcance de los scripts",
         bool(galleta) and galleta["httpOnly"] and galleta["sameSite"] == "Strict"
         and page.evaluate("localStorage.getItem('ocr_access_token')") is None
         and galleta["name"] not in page.evaluate("document.cookie"),
         {k: galleta[k] for k in ("name", "httpOnly", "sameSite", "secure")} if galleta else "sin cookie")

    # ── Personas y visor ────────────────────────────────────────────
    page.goto(f"{FRONT}/personas?documento_id={IDS['ficha_ana']}")
    filas = page.locator("tbody tr")
    expect(filas.first).to_contain_text("ADRIANA", timeout=15000)
    caso("CP-UI-03", "Personas: muestra las 5 personas de la ficha en orden A-Z", filas.count() == 5,
         [t.strip() for t in page.locator("tbody tr td:nth-child(3)").all_inner_texts()])

    boton_orden = page.get_by_title("Ordenar alfabéticamente por nombre", exact=False)
    boton_orden.click()
    expect(filas.first).to_contain_text("ZULY", timeout=5000)
    page.reload()
    expect(filas.first).to_contain_text("ZULY", timeout=15000)
    caso("CP-UI-18", "Personas: ordena de la Z a la A y recuerda el orden al volver", True, filas.first.inner_text().split(chr(10))[0][:40])
    boton_orden.click()
    expect(filas.first).to_contain_text("ADRIANA", timeout=5000)

    page.locator("tbody tr", has_text="BEATRIZ LOPEZ").click()
    visor = page.locator("[role=region][aria-label^='Documento de']")
    expect(visor).to_be_visible(timeout=10000)
    imagen = visor.locator("img").first
    expect(imagen).to_be_visible(timeout=15000)
    page.wait_for_timeout(800)
    src = imagen.get_attribute("src") or ""
    page.screenshot(path=str(CAPTURAS / "02_visor_documento.png"))
    caso("CP-UI-04", "Visor: la página del documento se muestra (imagen en memoria, blob:)", src.startswith("blob:"), src[:30])

    con_token_en_url = [r.url for r in peticiones_pagina if "token=" in r.url]
    sin_cookie = [r.url for r in peticiones_pagina if galleta["name"] not in r.all_headers().get("cookie", "")]
    caso("CP-UI-05", "Visor: la imagen se pide con la cookie de sesión, nunca con el token en la dirección",
         peticiones_pagina and not con_token_en_url and not sin_cookie,
         f"{len(peticiones_pagina)} peticiones; con token en URL: {len(con_token_en_url)}; sin cookie: {len(sin_cookie)}")
    cache = {r.headers.get("cache-control") for r in respuestas_pagina}
    caso("CP-UI-06", "Visor: el navegador no guarda la imagen de la cédula en disco", cache == {"private, no-store"}, cache)

    visor.get_by_role("button", name="Reverso (pág. 2)").click()
    expect(visor.get_by_text("Documento (pág. 2)")).to_be_visible(timeout=5000)
    expect(visor.locator("img").first).to_be_visible(timeout=10000)
    caso("CP-UI-07", "Visor: cambia al reverso", True, "pág. 2 visible")

    # ── Recorrido por las pantallas (errores JS y política de contenido) ───
    api_put_json("/api/seguimiento/config", token_ana, {"url_panel": "https://script.google.com/macros/s/abc123/exec"})
    politicas = set()
    for ruta in ("/dashboard", "/documentos", "/personas", "/exportacion", "/comparacion", "/seguimiento"):
        respuesta = page.goto(FRONT + ruta)
        politicas.add("content-security-policy" in respuesta.headers)
        page.wait_for_timeout(2500)
    page.screenshot(path=str(CAPTURAS / "03_seguimiento.png"))
    caso("CP-UI-08", "Recorrido por las 6 pantallas del usuario sin errores de JavaScript", not errores_js, errores_js[:2])
    caso("CP-UI-09", "Las pantallas llevan la política de contenido obligatoria y ninguna la viola",
         politicas == {True} and not avisos_csp, avisos_csp[:2] or "CSP en las 6 pantallas, sin avisos")

    # ── Exportación ─────────────────────────────────────────────────
    page.goto(FRONT + "/exportacion")
    boton = page.get_by_role("button", name=re.compile(r"Descargar Excel \(\d+\)"))
    expect(boton).to_be_enabled(timeout=15000)
    with page.expect_download(timeout=30000) as descarga:
        boton.click()
    archivo = descarga.value
    ruta_local = SALIDA / "descarga.xlsx"
    archivo.save_as(str(ruta_local))
    time.sleep(1)
    quedan = list(EXPORTS.glob("*.xlsx")) if EXPORTS and EXPORTS.exists() else []
    caso("CP-UI-10", "Exportación: descarga el Excel y el servidor no se queda con la copia",
         ruta_local.read_bytes()[:2] == b"PK" and not quedan, f"{archivo.suggested_filename}; en el servidor: {len(quedan)}")

    # ── Política de contraseñas en la interfaz ──────────────────────
    page.goto(FRONT + "/dashboard")
    page.get_by_role("button", name="Cambiar contraseña").first.click()
    page.fill("#password-actual", CLAVE)
    page.fill("#password-nueva", "Kondid2026!")
    page.fill("#password-confirmacion", "Kondid2026!")
    page.locator("form").get_by_role("button", name="Cambiar contraseña").click()
    alerta = page.locator("p[role=alert]")
    expect(alerta).to_contain_text("muy común", timeout=10000)
    texto = alerta.inner_text()
    page.screenshot(path=str(CAPTURAS / "04_contrasena_comun.png"))
    caso("CP-UI-11", "Contraseña común: se rechaza con un mensaje claro", "Value error" not in texto and "password" not in texto, texto)
    page.keyboard.press("Escape")

    # ── Auditoría ───────────────────────────────────────────────────
    menu = page.locator("aside").get_by_text("Auditoría")
    page.goto(FRONT + "/auditoria")
    page.wait_for_url("**/dashboard", timeout=10000)
    caso("CP-UI-12", "Un usuario normal no ve la Auditoría ni puede entrar", menu.count() == 0 and "/dashboard" in page.url, page.url)

    login(page, "admin@example.com", CLAVE)
    page.locator("aside").get_by_text("Auditoría").click()
    page.wait_for_url("**/auditoria", timeout=10000)
    expect(page.locator("tbody tr").first).to_be_visible(timeout=10000)
    acciones = page.locator("tbody tr td:nth-child(3)").all_inner_texts()
    page.screenshot(path=str(CAPTURAS / "05_auditoria.png"))
    caso("CP-UI-13", "El administrador ve la Auditoría con los intentos fallidos y exportaciones",
         {"Inicio de sesión fallido", "Inicio de sesión", "Exportación de personas"} <= set(acciones), sorted(set(acciones)))
    page.select_option("#filtro-accion", "login_fallido")
    page.wait_for_timeout(1500)
    filtradas = set(page.locator("tbody tr td:nth-child(3)").all_inner_texts())
    caso("CP-UI-14", "Auditoría: el filtro por acción muestra solo esa acción", filtradas == {"Inicio de sesión fallido"}, filtradas)

    # ── Recuperar la contraseña por correo (escenario BDD de la guía) ──
    # Por nombre y fecha: el SMTP de captura reinicia su contador y puede reutilizar nombres
    antes = {(f.name, f.stat().st_mtime_ns) for f in CORREOS.glob("*.eml")}
    page.goto(FRONT + "/")
    page.evaluate("localStorage.clear()")
    page.context.clear_cookies()
    page.goto(FRONT + "/")
    page.get_by_role("link", name="¿Olvidaste tu contraseña?").click()
    page.wait_for_url("**/olvide-contrasena")
    page.fill("#olvide-email", "beto@example.com")
    page.get_by_role("button", name="Enviar enlace").click()
    expect(page.get_by_text("Revisa tu correo")).to_be_visible(timeout=10000)
    page.wait_for_timeout(2000)
    nuevos = sorted((f for f in CORREOS.glob("*.eml") if (f.name, f.stat().st_mtime_ns) not in antes), key=lambda f: f.stat().st_mtime_ns)
    mensaje = email.message_from_bytes(nuevos[-1].read_bytes(), policy=policy.default) if nuevos else None
    token = None
    if mensaje:
        cuerpo = mensaje.get_body(preferencelist=("plain",)).get_content()
        token = re.search(r"restablecer-contrasena\?token=([\w-]+)", cuerpo).group(1)
    page.goto(f"{FRONT}/restablecer-contrasena?token={token}")
    page.fill("#restablecer-nueva", "Beto-nueva-clave-27")
    page.fill("#restablecer-confirmacion", "Beto-nueva-clave-27")
    page.get_by_role("button", name="Guardar contraseña").click()
    expect(page.get_by_text("Contraseña actualizada")).to_be_visible(timeout=10000)
    login(page, "beto@example.com", CLAVE, esperar_dashboard=False)
    page.wait_for_timeout(2000)
    vieja_no_entra = "/dashboard" not in page.url
    login(page, "beto@example.com", "Beto-nueva-clave-27")
    caso("CP-UI-15", "Recuperar contraseña: correo, enlace, clave nueva; la vieja ya no entra",
         bool(mensaje) and vieja_no_entra and "/dashboard" in page.url, f"correos nuevos: {len(nuevos)}")

    # ── Cerrar sesión ───────────────────────────────────────────────
    token_beto = cookie_sesion(ctx)["value"]
    vigente_antes = api_get_estado("/api/auth/me", token_beto)
    page.locator("aside").get_by_role("button", name="Cerrar Sesión").first.click()
    page.wait_for_url(FRONT + "/", timeout=10000)
    page.wait_for_timeout(1000)
    despues = api_get_estado("/api/auth/me", token_beto)
    caso("CP-UI-16", "Cerrar sesión borra la cookie y el servidor deja de aceptar esa sesión",
         vigente_antes == 200 and cookie_sesion(ctx) is None and page.evaluate("localStorage.getItem('ocr_user')") is None
         and despues == 401, f"antes: {vigente_antes}; después: {despues}")

    caso("CP-UI-17", "Sin errores de JavaScript en todo el recorrido", not errores_js, errores_js[:2])
    nav.close()

pasan = sum(c["resultado"] == "PASA" for c in casos)
print(f"\n{pasan}/{len(casos)} pasan")
json.dump({"fecha": time.strftime("%Y-%m-%d %H:%M"), "pasan": pasan, "total": len(casos), "casos": casos},
          open(SALIDA / "e2e.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
sys.exit(0 if pasan == len(casos) else 1)
