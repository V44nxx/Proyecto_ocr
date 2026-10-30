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
import base64
import email
import hashlib
import hmac
import json
import os
import re
import struct
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from email import policy
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, expect, sync_playwright

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


def codigo_totp(secreto, momento=None):
    """Código de 6 dígitos (RFC 6238) de la clave que muestra la pantalla de configuración."""
    clave = base64.b32decode(secreto + "=" * (-len(secreto) % 8))
    resumen = hmac.new(clave, struct.pack(">Q", int((time.time() if momento is None else momento) // 30)),
                       hashlib.sha1).digest()
    corte = resumen[-1] & 0x0F
    return f"{(struct.unpack('>I', resumen[corte:corte + 4])[0] & 0x7FFFFFFF) % 1_000_000:06d}"


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

    # Confirmación propia (no la caja del navegador): eliminar y arrepentirse no borra nada
    page.get_by_title("Eliminar persona").click()
    dialogo = page.get_by_role("alertdialog", name="¿Eliminar a esta persona?")
    expect(dialogo).to_be_visible(timeout=5000)
    page.wait_for_timeout(500)
    page.screenshot(path=str(CAPTURAS / "16_confirmacion_propia.png"))
    enfocado_cancelar = page.evaluate("document.activeElement && document.activeElement.innerText") == "Cancelar"
    page.keyboard.press("Escape")
    expect(dialogo).to_be_hidden(timeout=5000)
    caso("CP-UI-33", "Eliminar una persona pide confirmación en el diálogo propio; Cancelar queda enfocado y Esc no borra",
         enfocado_cancelar and page.locator("tbody tr", has_text="BEATRIZ LOPEZ").count() == 1,
         f"foco en Cancelar: {enfocado_cancelar}")

    # ── Recorrido por las pantallas (errores JS y política de contenido) ───
    api_put_json("/api/seguimiento/config", token_ana, {"url_panel": "https://script.google.com/macros/s/abc123/exec?k=clave0123"})
    politicas, nonces = set(), set()
    for ruta in ("/dashboard", "/documentos", "/personas", "/exportacion", "/comparacion", "/seguimiento"):
        respuesta = page.goto(FRONT + ruta)
        csp = respuesta.headers.get("content-security-policy", "")
        scripts = next((d for d in csp.split(";") if d.strip().startswith("script-src")), "")
        politicas.add(bool(csp) and "'unsafe-inline'" not in scripts and "'nonce-" in scripts)
        nonces.add(re.search(r"'nonce-([^']+)'", scripts).group(1) if "'nonce-" in scripts else "")
        page.wait_for_timeout(2500)
    page.screenshot(path=str(CAPTURAS / "03_seguimiento.png"))
    # El panel de Apps Script recibe su clave y el nombre de quien tiene la sesión abierta, para su historial de cambios
    enlace_panel = urllib.parse.urlsplit(page.locator("iframe").first.get_attribute("src") or "")
    datos_enlace = urllib.parse.parse_qs(enlace_panel.query)
    caso("CP-UI-39", "Seguimiento: el panel incrustado conserva su clave y recibe el nombre del usuario conectado",
         enlace_panel.netloc == "script.google.com" and datos_enlace == {"k": ["clave0123"], "u": ["Ana Pruebas"]},
         f"{enlace_panel.netloc} {datos_enlace}")
    caso("CP-UI-08", "Recorrido por las 6 pantallas del usuario sin errores de JavaScript", not errores_js, errores_js[:2])
    caso("CP-UI-09", "Política de contenido en las 6 pantallas: scripts solo con un nonce nuevo en cada carga, sin violaciones",
         politicas == {True} and len(nonces) == 6 and not avisos_csp,
         avisos_csp[:2] or f"CSP con nonce en las 6 pantallas ({len(nonces)} nonces distintos), sin avisos")

    # El logo del menú lleva al Dashboard (estamos en Seguimiento)
    page.locator("aside").get_by_role("link", name="KondID: ir al Dashboard").click()
    page.wait_for_url("**/dashboard", timeout=10000)
    caso("CP-UI-31", "El logo del menú lleva al Dashboard", "/dashboard" in page.url, page.url)

    # Cambiar el tema varias veces seguidas deja un solo aviso, el del último cambio (oscuro → claro → oscuro → claro)
    interruptor = page.locator("aside").get_by_role("button", name=re.compile(r"Cambiar a Modo (Claro|Oscuro)"))
    for _ in range(3):
        interruptor.click()
        page.wait_for_timeout(150)
    page.wait_for_timeout(1300)
    avisos_tema = page.get_by_text(re.compile(r"^Modo (Claro|Oscuro) activado$"))
    textos_tema = [avisos_tema.nth(i).inner_text() for i in range(avisos_tema.count()) if avisos_tema.nth(i).is_visible()]
    caso("CP-UI-34", "Cambiar el tema seguido deja un solo aviso, el del último cambio",
         textos_tema == ["Modo Claro activado"], textos_tema)
    interruptor.click()
    expect(avisos_tema).to_have_count(0, timeout=6000)

    # ── Datos recientes en memoria ──────────────────────────────────
    # Con la red a 1,5 s por viaje, la lista de Personas tiene que verse antes de que pueda llegar del servidor
    lateral = page.locator("aside")
    lateral.get_by_text("Personas", exact=True).first.click()
    expect(page.locator("tbody tr").first).to_contain_text("ADRIANA", timeout=15000)
    lateral.get_by_text("Dashboard", exact=True).first.click()
    page.wait_for_url("**/dashboard", timeout=10000)
    page.wait_for_timeout(1000)
    red = ctx.new_cdp_session(page)
    red.send("Network.enable")
    red.send("Network.emulateNetworkConditions",
             {"offline": False, "latency": 1500, "downloadThroughput": -1, "uploadThroughput": -1})
    lateral.get_by_text("Personas", exact=True).first.click()
    page.wait_for_url("**/personas*", timeout=15000)
    try:
        page.wait_for_function("""() => {
            const fila = document.querySelector('tbody tr');
            return fila && fila.innerText.includes('ADRIANA') && !document.querySelector('main .animate-pulse');
        }""", timeout=700)
        al_instante = True
    except PlaywrightTimeoutError:
        al_instante = False
    red.send("Network.emulateNetworkConditions",
             {"offline": False, "latency": 0, "downloadThroughput": -1, "uploadThroughput": -1})
    caso("CP-UI-35", "Al volver a Personas, la lista de la visita anterior se ve al instante mientras llega la actual",
         al_instante, "lista visible antes de 0,7 s con la red a 1,5 s por viaje")

    # Al cerrar sesión la memoria se vacía: volver atrás a Personas no muestra la lista ni un instante
    page.wait_for_timeout(2000)
    lateral.get_by_role("button", name="Cerrar Sesión").first.click()
    page.wait_for_url(FRONT + "/", timeout=10000)
    page.evaluate("""() => {
        window.__filasVistas = 0;
        new MutationObserver(() => {
            if ([...document.querySelectorAll('tbody tr')].some((f) => f.innerText.includes('ADRIANA'))) window.__filasVistas++;
        }).observe(document.body, { childList: true, subtree: true, characterData: true });
    }""")
    page.go_back()
    page.wait_for_url(FRONT + "/", timeout=15000)
    page.wait_for_timeout(1500)
    filas_vistas = page.evaluate("window.__filasVistas")
    caso("CP-UI-36", "Tras cerrar sesión, volver atrás a Personas no deja ver la lista guardada en memoria",
         filas_vistas == 0, f"veces que apareció la lista: {filas_vistas}")
    login(page, "ana@example.com", CLAVE)

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
    aviso_descarga = page.get_by_text("Tiene datos personales")
    expect(aviso_descarga).to_be_visible(timeout=10000)
    callout = page.get_by_text("Datos personales:", exact=True)
    caso("CP-UI-24", "Exportación: avisa que el Excel trae datos personales, antes y después de descargarlo",
         callout.is_visible() and aviso_descarga.is_visible(), aviso_descarga.inner_text()[:80])

    # ── Avisos de conexión ──────────────────────────────────────────
    page.goto(FRONT + "/dashboard")
    expect(page.get_by_role("button", name=re.compile("Actualizar")).first).to_be_visible(timeout=15000)
    ctx.set_offline(True)
    aviso_internet = page.locator("[data-aviso=internet]")
    expect(aviso_internet).to_be_visible(timeout=10000)
    page.screenshot(path=str(CAPTURAS / "09_aviso_sin_internet.png"))
    texto_internet = aviso_internet.inner_text()
    ctx.set_offline(False)
    expect(aviso_internet).to_be_hidden(timeout=10000)
    expect(page.get_by_text("Volvió la conexión a internet")).to_be_visible(timeout=10000)
    caso("CP-UI-25", "Sin internet: aviso fijo mientras dura, y aviso de que volvió",
         "Sin conexión a internet" in texto_internet, texto_internet.replace(chr(10), " | ")[:90])

    page.route("**/api/**", lambda ruta: ruta.abort())
    page.route("**/health", lambda ruta: ruta.abort())
    page.get_by_role("button", name=re.compile("Actualizar")).first.click()
    aviso_servidor = page.locator("[data-aviso=servidor]")
    expect(aviso_servidor).to_be_visible(timeout=15000)
    page.screenshot(path=str(CAPTURAS / "10_aviso_servidor.png"))
    page.unroute_all()
    expect(aviso_servidor).to_be_hidden(timeout=25000)   # se revisa solo cada 15 segundos
    caso("CP-UI-26", "Servidor sin responder: aviso con reintento automático, y se quita cuando vuelve", True,
         "aviso visible y luego oculto")

    cdp = ctx.new_cdp_session(page)
    cdp.send("Network.enable")
    cdp.send("Network.emulateNetworkConditions",
             {"offline": False, "latency": 4500, "downloadThroughput": -1, "uploadThroughput": -1})
    aviso_lenta = page.locator("[data-aviso=lenta]")
    for _ in range(4):
        if aviso_lenta.is_visible():
            break
        page.get_by_role("button", name=re.compile("Actualizar")).first.click()
        page.wait_for_timeout(9000)
    expect(aviso_lenta).to_be_visible(timeout=30000)
    page.screenshot(path=str(CAPTURAS / "11_aviso_conexion_lenta.png"))
    cdp.send("Network.emulateNetworkConditions",
             {"offline": False, "latency": 0, "downloadThroughput": -1, "uploadThroughput": -1})
    for _ in range(4):                 # con respuestas rápidas otra vez, el aviso se quita solo
        if aviso_lenta.is_hidden():
            break
        page.get_by_role("button", name=re.compile("Actualizar")).first.click()
        page.wait_for_timeout(2000)
    expect(aviso_lenta).to_be_hidden(timeout=15000)
    caso("CP-UI-27", "Conexión lenta: avisa que puede tardar, y se quita cuando la conexión mejora", True,
         "visible con 4,5 s de latencia y oculto al normalizarse")

    page.route("**/health", lambda ruta: ruta.fulfill(status=200, content_type="application/json",
                                                       body='{"status":"ok","version":"99.0.0"}'))
    page.reload()
    aviso_version = page.locator("[data-aviso=version]")
    expect(aviso_version).to_be_visible(timeout=15000)
    page.screenshot(path=str(CAPTURAS / "12_aviso_version_nueva.png"))
    texto_version = aviso_version.inner_text()
    page.unroute_all()
    caso("CP-UI-28", "Versión nueva en el servidor: avisa y ofrece recargar",
         "99.0.0" in texto_version and aviso_version.get_by_role("button", name="Recargar").is_visible(),
         texto_version.replace(chr(10), " | ")[:90])

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

    # ── Sesión cerrada desde otro lado y Bloq Mayús ─────────────────
    token_actual = cookie_sesion(ctx)["value"]
    urllib.request.urlopen(urllib.request.Request(API + "/api/auth/logout", method="POST",
                                                  headers={"Authorization": f"Bearer {token_actual}"}))
    page.goto(FRONT + "/personas")
    page.wait_for_url(FRONT + "/", timeout=15000)
    aviso_sesion = page.get_by_text("Tu sesión se cerró.")
    expect(aviso_sesion).to_be_visible(timeout=10000)
    page.screenshot(path=str(CAPTURAS / "13_aviso_sesion_cerrada.png"))
    caso("CP-UI-29", "Sesión cerrada desde otro lado: lleva al inicio y explica por qué", True, page.url)

    page.locator("#password").dispatch_event("keydown", {"key": "A", "modifierCapsLock": True})
    aviso_mayus = page.get_by_text("Bloq Mayús está activado")
    expect(aviso_mayus).to_be_visible(timeout=5000)
    page.locator("#password").dispatch_event("keyup", {"key": "A", "modifierCapsLock": False})
    expect(aviso_mayus).to_be_hidden(timeout=5000)
    caso("CP-UI-30", "Inicio de sesión: avisa cuando Bloq Mayús está activado", True, "aparece y se quita")

    # ── Verificación en dos pasos del administrador ─────────────────
    login(page, "admin@example.com", CLAVE, esperar_dashboard=False)
    expect(page.get_by_text("Protege tu cuenta de administrador")).to_be_visible(timeout=10000)
    clave_app = page.locator("[data-clave-2fa]")
    expect(page.get_by_alt_text("Código QR para vincular la app de autenticación")).to_be_visible(timeout=10000)
    expect(clave_app).not_to_have_attribute("data-clave-2fa", "", timeout=10000)
    secreto = clave_app.get_attribute("data-clave-2fa")
    page.screenshot(path=str(CAPTURAS / "06_2fa_vincular_app.png"))
    caso("CP-UI-20", "Administrador: con la contraseña sola no entra; ve el QR para vincular su app",
         "/dashboard" not in page.url and cookie_sesion(ctx) is None and len(secreto) >= 16,
         f"clave de {len(secreto)} caracteres; cookie: {cookie_sesion(ctx) is not None}")

    page.fill("#codigo-verificacion", codigo_totp(secreto))   # con los 6 dígitos se envía solo
    expect(page.get_by_text("Guarda tus códigos de respaldo")).to_be_visible(timeout=10000)
    codigos = page.locator("ol li").count()
    entrar = page.get_by_role("button", name="Entrar al panel")
    bloqueado = entrar.is_disabled()
    page.screenshot(path=str(CAPTURAS / "07_2fa_codigos_respaldo.png"))
    page.get_by_label(re.compile("Los guardé en un lugar seguro")).check()
    entrar.click()
    page.wait_for_url("**/dashboard", timeout=15000)
    caso("CP-UI-21", "Activar: el código de la app abre la sesión y muestra 10 códigos de respaldo",
         codigos == 10 and bloqueado and cookie_sesion(ctx) is not None,
         f"códigos: {codigos}; botón bloqueado hasta confirmar: {bloqueado}")

    login(page, "admin@example.com", CLAVE, esperar_dashboard=False)
    expect(page.get_by_text("Verificación en dos pasos", exact=True)).to_be_visible(timeout=10000)
    page.fill("#codigo-verificacion", "000000")
    error_codigo = page.get_by_text("El código no es correcto")
    expect(error_codigo).to_be_visible(timeout=10000)
    ayuda_hora = page.get_by_text("hora de tu celular", exact=False)
    expect(ayuda_hora).to_be_visible(timeout=5000)
    page.screenshot(path=str(CAPTURAS / "08_2fa_codigo_equivocado.png"))
    page.fill("#codigo-verificacion", codigo_totp(secreto, time.time() + 30))   # el actual ya se usó al activar
    page.wait_for_url("**/dashboard", timeout=15000)
    caso("CP-UI-22", "Siguiente ingreso: un código equivocado no entra y el de la app sí", True, "error mostrado y luego panel")

    page.goto(FRONT + "/usuarios")
    fila_admin = page.locator("tbody tr", has_text="admin@example.com")
    expect(fila_admin).to_contain_text("Activa", timeout=10000)
    caso("CP-UI-23", "Usuarios: muestra la verificación en dos pasos del administrador como activa",
         "Activa" in fila_admin.inner_text(), fila_admin.inner_text().replace(chr(10), " | ")[:90])
    sin_boton_menu = page.locator("aside").get_by_text("Agregar Usuario").count() == 0
    page.get_by_role("button", name="+ Nuevo Usuario").click()
    expect(page.get_by_text("Crear Nuevo Usuario")).to_be_visible(timeout=5000)
    page.screenshot(path=str(CAPTURAS / "15_modal_crear_usuario.png"))
    page.keyboard.press("Escape")
    page.get_by_role("button", name="Cancelar").click() if page.get_by_role("button", name="Cancelar").count() else None

    # En modo claro, el rol elegido se lee: antes quedaba en blanco sobre celeste
    page.evaluate("localStorage.setItem('ocr_theme', 'light')")
    page.reload()
    page.get_by_role("button", name="+ Nuevo Usuario").click()
    rol_elegido = page.get_by_role("button", name=re.compile("^Operador"))
    expect(rol_elegido).to_be_visible(timeout=5000)
    page.wait_for_timeout(400)
    # Tailwind 4 entrega los colores en oklch(): se pasan a RGB dibujándolos en un canvas
    luz_texto = page.evaluate("""(boton) => {
        const lienzo = document.createElement('canvas').getContext('2d');
        lienzo.fillStyle = getComputedStyle(boton).color;
        lienzo.fillRect(0, 0, 1, 1);
        const [r, g, b] = lienzo.getImageData(0, 0, 1, 1).data;
        return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255;
    }""", rol_elegido.element_handle())
    caso("CP-UI-37", "Crear usuario en modo claro: el rol elegido se lee (texto oscuro, no blanco)",
         luz_texto < 0.4, f"luminancia del texto: {luz_texto:.2f}")
    page.keyboard.press("Escape")
    page.evaluate("localStorage.setItem('ocr_theme', 'dark')")
    page.reload()
    caso("CP-UI-32", "Usuarios: se crea desde el módulo; el menú lateral ya no tiene «Agregar Usuario»",
         sin_boton_menu, f"botón en el menú: {not sin_boton_menu}")

    page.locator("aside").get_by_text("Auditoría").click()
    page.wait_for_url("**/auditoria", timeout=10000)
    expect(page.locator("tbody tr").first).to_be_visible(timeout=10000)
    acciones = page.locator("tbody tr td:nth-child(3)").all_inner_texts()
    page.screenshot(path=str(CAPTURAS / "05_auditoria.png"))
    caso("CP-UI-13", "El administrador ve la Auditoría con los intentos fallidos, exportaciones y la verificación",
         {"Inicio de sesión fallido", "Inicio de sesión", "Exportación de personas", "Verificación en dos pasos activada",
          "Código de verificación equivocado"} <= set(acciones), sorted(set(acciones)))
    # El filtro se elige en una ventana (no en una lista desplegable): se abre, se busca y se toca la opción
    page.click("#filtro-accion")
    ventana = page.get_by_role("dialog", name="Filtrar por acción")
    expect(ventana).to_be_visible(timeout=5000)
    ventana.get_by_role("textbox").fill("fallido")
    page.screenshot(path=str(CAPTURAS / "14_selector_en_ventana.png"))
    ventana.get_by_role("option", name="Inicio de sesión fallido").click()
    expect(ventana).to_be_hidden(timeout=5000)
    page.wait_for_timeout(1500)
    filtradas = set(page.locator("tbody tr td:nth-child(3)").all_inner_texts())
    caso("CP-UI-14", "Auditoría: el filtro por acción muestra solo esa acción", filtradas == {"Inicio de sesión fallido"}, filtradas)

    # ── Listas largas: no se cortan (cuenta con 650 personas, 105 fichas y 150 diferencias) ──
    login(page, "lote@example.com", CLAVE)
    page.goto(f"{FRONT}/personas?documento_id={IDS['ficha_lote']}")
    # Esperar que se vean confirma cada lista completa (si se cortara, el número sería otro)
    expect(page.locator("text=/Mostrando\\s*650\\s*de\\s*650/").last).to_be_visible(timeout=30000)
    page.locator("button[aria-labelledby='etiqueta-ficha']").click()
    ventana_fichas = page.get_by_role("dialog", name="Elegir ficha")
    expect(ventana_fichas).to_be_visible(timeout=5000)
    opciones_fichas = ventana_fichas.get_by_role("option").count()
    page.keyboard.press("Escape")
    page.goto(f"{FRONT}/exportacion")
    boton_excel = page.get_by_role("button", name="Descargar Excel (650)")
    expect(boton_excel).to_be_enabled(timeout=30000)
    page.goto(f"{FRONT}/comparacion?id={IDS['comparacion_lote']}")
    expect(page.get_by_role("button", name=re.compile(r"^Todos\s*150$"))).to_be_visible(timeout=30000)
    caso("CP-UI-38", "Listas largas completas: 650 personas, 105 fichas en la ventana, 650 al exportar y 150 diferencias",
         opciones_fichas == 106, f"opciones en la ventana de fichas: {opciones_fichas} (105 + Todas)")

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
