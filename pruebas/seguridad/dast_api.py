"""Pruebas de seguridad de caja negra contra un backend de KondID en marcha (datos de pruebas/semilla.py).

Solo contra un servidor de pruebas, nunca contra producción: crea usuarios, sube archivos y fuerza bloqueos.
Uso: python dast_api.py <url_base> <semilla_ids.json> <salida.json>
Opcional: CARPETA_SUBIDAS=<UPLOAD_DIR del backend> para revisar en disco dónde quedó el archivo de SEG-24.
El backend debe correr con ENVIRONMENT=production (SEG-04) y recién iniciado (los límites viven en memoria).
Cada caso imprime PASA/FALLA con lo obtenido; el JSON queda como evidencia para el informe.
"""
import base64
import json
import os
import sys
import time

import httpx

BASE = sys.argv[1].rstrip("/")
IDS = json.load(open(sys.argv[2], encoding="utf-8"))
SALIDA = sys.argv[3]
CLAVE = IDS["clave"]
ORIGEN_AJENO = "https://sitio-ajeno.example"

c = httpx.Client(base_url=BASE, timeout=30)
resultados = []


def caso(cid, nombre, categoria, esperado):
    def deco(fn):
        try:
            ok, obtenido = fn()
        except Exception as e:  # una excepción del script cuenta como falla y queda anotada
            ok, obtenido = False, f"excepción en la prueba: {type(e).__name__}: {e}"
        resultados.append({"id": cid, "nombre": nombre, "categoria": categoria, "esperado": esperado,
                           "obtenido": obtenido, "resultado": "PASA" if ok else "FALLA"})
        print(f"{'PASA ' if ok else 'FALLA'} {cid} {nombre}\n       {obtenido}")
        return fn
    return deco


def login(email):
    """Inicia sesión y devuelve (token, cabecera Set-Cookie). No deja la cookie en el cliente:
    los casos sin sesión deben ir de verdad sin sesión."""
    r = c.post("/api/auth/login", json={"email": email, "password": CLAVE})
    r.raise_for_status()
    c.cookies.clear()
    return r.json()["access_token"], r.headers.get("set-cookie", "")


def token(email):
    return login(email)[0]


def cookie_de(set_cookie):
    """'nombre=valor' para mandarla a mano (una cookie Secure no viaja sola por http local)."""
    return set_cookie.split(";", 1)[0]


def h(tok):
    return {"Authorization": f"Bearer {tok}"}


TOK_ANA = token("ana@example.com")
TOK_BETO = token("beto@example.com")
TOK_ADMIN = token("admin@example.com")


@caso("SEG-01", "Un usuario no descarga el reporte de diferencias de otra cuenta", "A01 Control de acceso",
      "404 para el usuario ajeno")
def _():
    r = c.get(f"/api/exportacion/diferencias/{IDS['comparacion_ana']}", headers=h(TOK_BETO))
    return r.status_code == 404, f"HTTP {r.status_code}, {len(r.content)} bytes, {r.headers.get('content-type')}"


@caso("SEG-02", "El dueño sí descarga su reporte de diferencias", "A01 Control de acceso", "200 con un .xlsx")
def _():
    r = c.get(f"/api/exportacion/diferencias/{IDS['comparacion_ana']}", headers=h(TOK_ANA))
    return r.status_code == 200 and r.content[:2] == b"PK", f"HTTP {r.status_code}, {len(r.content)} bytes"


@caso("SEG-03", "Un error interno no muestra detalles del servidor", "A05 Configuración / A09 Errores",
      "500 genérico con referencia, sin SQL ni trazas")
def _():
    r = c.get("/api/exportacion/diferencias/no-es-un-uuid", headers=h(TOK_ANA))
    cuerpo = r.text
    filtra = any(s in cuerpo for s in ("psycopg2", "SELECT", "sqlalchemy", "Traceback", "invalid input syntax"))
    return (not filtra and r.status_code in (400, 404, 422, 500)), f"HTTP {r.status_code}: {cuerpo[:160]}"


@caso("SEG-04", "La documentación interactiva no está publicada en producción", "A05 Configuración",
      "404 en /docs, /redoc y /openapi.json")
def _():
    codigos = {p: c.get(p).status_code for p in ("/docs", "/redoc", "/openapi.json")}
    return all(v == 404 for v in codigos.values()), str(codigos)


@caso("SEG-05", "La vista previa no acepta el token en la dirección", "A07 Autenticación / A02 Exposición",
      "401 con ?token= y sin cabecera")
def _():
    r = c.get(f"/api/documentos/{IDS['ficha_ana']}/pagina/1", params={"dpi": 130, "token": TOK_ANA})
    return r.status_code == 401, f"HTTP {r.status_code}"


@caso("SEG-06", "La vista previa con cabecera funciona y no se guarda en cachés compartidas", "A02 Exposición de datos",
      "200 image/jpeg con Cache-Control private y no-store")
def _():
    r = c.get(f"/api/documentos/{IDS['ficha_ana']}/pagina/1", params={"dpi": 130}, headers=h(TOK_ANA))
    cc = r.headers.get("cache-control", "")
    return (r.status_code == 200 and "private" in cc and "no-store" in cc), f"HTTP {r.status_code}, Cache-Control: {cc!r}"


@caso("SEG-07", "Un usuario no ve la vista previa de la ficha de otra cuenta", "A01 Control de acceso", "404")
def _():
    r = c.get(f"/api/documentos/{IDS['ficha_ana']}/pagina/1", params={"dpi": 130}, headers=h(TOK_BETO))
    return r.status_code == 404, f"HTTP {r.status_code}"


@caso("SEG-08", "Las respuestas de la API llevan cabeceras de seguridad", "A05 Configuración",
      "nosniff, X-Frame-Options DENY, Referrer-Policy y CSP frame-ancestors 'none'")
def _():
    r = c.get("/api/auth/me", headers=h(TOK_ANA))
    hs = r.headers
    faltan = [n for n, ok in (
        ("X-Content-Type-Options", hs.get("x-content-type-options") == "nosniff"),
        ("X-Frame-Options", hs.get("x-frame-options") == "DENY"),
        ("Referrer-Policy", bool(hs.get("referrer-policy"))),
        ("CSP frame-ancestors", "frame-ancestors 'none'" in hs.get("content-security-policy", "")),
    ) if not ok]
    return not faltan, "faltan: " + ", ".join(faltan) if faltan else "todas presentes"


@caso("SEG-09", "Los datos personales de la API no quedan en cachés", "A02 Exposición de datos", "Cache-Control no-store")
def _():
    r = c.get("/api/personas", headers=h(TOK_ANA))
    cc = r.headers.get("cache-control", "")
    return "no-store" in cc, f"Cache-Control: {cc!r}"


@caso("SEG-10", "CORS no autoriza a un sitio ajeno", "A05 Configuración", "sin Access-Control-Allow-Origin para el origen ajeno")
def _():
    r = c.options("/api/auth/login", headers={"Origin": ORIGEN_AJENO, "Access-Control-Request-Method": "POST",
                                              "Access-Control-Request-Headers": "content-type"})
    acao = r.headers.get("access-control-allow-origin")
    return acao not in (ORIGEN_AJENO, "*"), f"HTTP {r.status_code}, Allow-Origin: {acao!r}, Allow-Credentials: {r.headers.get('access-control-allow-credentials')!r}"


@caso("SEG-11", "CORS sí autoriza al frontend oficial", "A05 Configuración", "Allow-Origin igual al frontend")
def _():
    origen = "https://proyectoocr.v44nxx.online"
    r = c.options("/api/auth/login", headers={"Origin": origen, "Access-Control-Request-Method": "POST",
                                              "Access-Control-Request-Headers": "content-type"})
    return r.headers.get("access-control-allow-origin") == origen, f"HTTP {r.status_code}, Allow-Origin: {r.headers.get('access-control-allow-origin')!r}"


@caso("SEG-12", "Todas las rutas protegidas piden sesión", "A01 Control de acceso", "401 sin token en todas")
def _():
    rutas = ["/api/auth/me", "/api/auth/users", "/api/documentos", "/api/personas", "/api/comparacion",
             "/api/documentos/dashboard/estadisticas", "/api/seguimiento/config",
             f"/api/exportacion/diferencias/{IDS['comparacion_ana']}", "/api/exportacion/xlsx"]
    malas = {p: s for p in rutas if (s := c.get(p).status_code) != 401}
    return not malas, f"{len(rutas)} rutas revisadas; distintas de 401: {malas or 'ninguna'}"


@caso("SEG-13", "Un usuario normal no entra a las rutas de administrador", "A01 Control de acceso", "403")
def _():
    codigos = {
        "GET /api/auth/users": c.get("/api/auth/users", headers=h(TOK_ANA)).status_code,
        "POST /api/auth/register": c.post("/api/auth/register", headers=h(TOK_ANA),
                                          json={"email": "x@example.com", "password": "ClaveLarga123", "rol": "admin"}).status_code,
        "POST /api/sistema/migrar-db": c.post("/api/sistema/migrar-db", headers=h(TOK_ANA)).status_code,
    }
    return all(v == 403 for v in codigos.values()), str(codigos)


@caso("SEG-14", "Un token alterado o sin firma no sirve", "A07 Autenticación", "401")
def _():
    cab, cuerpo, firma = TOK_ANA.split(".")
    carga = json.loads(base64.urlsafe_b64decode(cuerpo + "=="))
    carga["sub"] = carga["sub"][:-1] + ("0" if carga["sub"][-1] != "0" else "1")
    cuerpo_alt = base64.urlsafe_b64encode(json.dumps(carga).encode()).decode().rstrip("=")
    sin_firma = base64.urlsafe_b64encode(b'{"alg":"none","typ":"JWT"}').decode().rstrip("=") + "." + cuerpo + "."
    codigos = [c.get("/api/auth/me", headers=h(f"{cab}.{cuerpo_alt}.{firma}")).status_code,
               c.get("/api/auth/me", headers=h(sin_firma)).status_code]
    return codigos == [401, 401], f"alterado: {codigos[0]}, alg=none: {codigos[1]}"


@caso("SEG-15", "Inyección SQL en el inicio de sesión no entra", "A03 Inyección", "401 o 422, nunca 200 ni 500")
def _():
    codigos = [c.post("/api/auth/login", json={"email": e, "password": p}).status_code for e, p in (
        ("admin@example.com' OR '1'='1", "x"), ("admin@example.com", "' OR '1'='1"), ("admin@example.com--", "x"))]
    return all(s in (401, 422, 429) for s in codigos), str(codigos)


@caso("SEG-16", "Inyección SQL en la búsqueda por cédula no filtra datos", "A03 Inyección", "404, sin datos de otros")
def _():
    r = c.get("/api/personas/buscar/cedula/1' OR '1'='1", headers=h(TOK_BETO))
    return r.status_code == 404, f"HTTP {r.status_code}"


@caso("SEG-17", "Un usuario no encuentra por cédula a una persona de otra cuenta", "A01 Control de acceso", "404")
def _():
    r = c.get("/api/personas/buscar/cedula/1000000401", headers=h(TOK_BETO))
    return r.status_code == 404, f"HTTP {r.status_code}"


@caso("SEG-18", "Un usuario no lee ni edita una persona de otra cuenta", "A01 Control de acceso", "404 al leer y al editar")
def _():
    a = c.get(f"/api/personas/{IDS['persona_ana']}", headers=h(TOK_BETO)).status_code
    b = c.put(f"/api/personas/{IDS['persona_ana']}", headers=h(TOK_BETO), json={"nombres": "HACKEADO"}).status_code
    return (a, b) == (404, 404), f"leer: {a}, editar: {b}"


@caso("SEG-19", "Subir sin sesión se rechaza antes de recibir el archivo", "A04 Diseño / disponibilidad", "401")
def _():
    r = c.post("/api/documentos/upload", files={"file": ("a.pdf", b"%PDF-1.4" + b"0" * 1000, "application/pdf")})
    return r.status_code == 401, f"HTTP {r.status_code}"


@caso("SEG-20", "Un cuerpo enorme se corta con 413", "A04 Diseño / disponibilidad", "413")
def _():
    r = c.post("/api/auth/login", content=b"{" + b" " * (3 * 1024 * 1024) + b"}",
               headers={"Content-Type": "application/json"})
    return r.status_code == 413, f"HTTP {r.status_code}"


@caso("SEG-21", "El enlace del Seguimiento solo acepta Apps Script", "A03 Inyección / A10 SSRF",
      "422 para javascript:, http y otros dominios")
def _():
    codigos = [c.put("/api/seguimiento/config", headers=h(TOK_ANA), json={"url_panel": u}).status_code for u in (
        "javascript:alert(1)", "http://script.google.com/macros/s/x/exec",
        "https://script.google.com.evil.example/macros/s/x/exec", "https://evil.example/macros/s/x/exec",
        "https://script.google.com@evil.example/macros/s/x/exec")]
    return all(s == 422 for s in codigos), str(codigos)


@caso("SEG-22", "La recuperación de contraseña no revela qué correos existen", "A07 Autenticación",
      "misma respuesta para un correo que existe y otro que no")
def _():
    a = c.post("/api/auth/olvide-password", json={"email": "ana@example.com"})
    b = c.post("/api/auth/olvide-password", json={"email": "nadie@example.com"})
    return (a.status_code, a.text) == (b.status_code, b.text), f"existe: {a.status_code}, no existe: {b.status_code}, textos iguales: {a.text == b.text}"


@caso("SEG-23", "Contraseñas débiles o muy comunes se rechazan al crear usuarios", "A07 Autenticación",
      "422 para 'password', '12345678' y 'kondid2026'")
def _():
    codigos = [c.post("/api/auth/register", headers=h(TOK_ADMIN),
                      json={"email": f"debil{i}@example.com", "password": p, "rol": "usuario"}).status_code
               for i, p in enumerate(("password", "12345678", "kondid2026"))]
    return all(s == 422 for s in codigos), str(codigos)


@caso("SEG-24", "El nombre del archivo subido no puede salir de la carpeta de subidas", "A01 / A03 Recorrido de rutas",
      "202 y el archivo queda dentro de la carpeta de subidas")
def _():
    from pathlib import Path
    pdf = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"
    r = c.post("/api/documentos/upload", headers=h(TOK_BETO),
               files={"file": ("../../../fuera.pdf", pdf, "application/pdf")})
    if not os.environ.get("CARPETA_SUBIDAS"):
        return r.status_code == 202, f"HTTP {r.status_code} (sin CARPETA_SUBIDAS no se revisa el disco)"
    subidas = Path(os.environ["CARPETA_SUBIDAS"]).resolve()
    afuera = [p for nivel in (subidas.parent, subidas.parent.parent, subidas.parent.parent.parent)
              for p in nivel.glob("fuera.pdf")]
    for p in afuera:
        p.unlink()
    adentro = list(subidas.glob("*fuera.pdf"))
    return (r.status_code == 202 and not afuera and adentro), (
        f"HTTP {r.status_code}; dentro de subidas: {[p.name for p in adentro]}; escrito afuera: {[str(p) for p in afuera]}")


@caso("SEG-26", "Robustez: ids con formato inválido no producen errores 500", "A04 Diseño / A05 Errores",
      "4xx en todas las rutas, sin texto de la base de datos")
def _():
    malos = ["no-es-uuid", "..%5C..%5Cwin.ini", "www.ejemplo.com", "%3C%21--x--%3E"]
    rutas = [f"/api/personas/{m}" for m in malos] + [f"/api/documentos/{m}" for m in malos] + [
        "/api/personas?documento_id=no-es-uuid", "/api/exportacion/xlsx?documento_id=no-es-uuid",
        "/api/documentos/dashboard/estadisticas?documento_id=no-es-uuid", "/api/comparacion/no-es-uuid"]
    malas = {}
    for ruta in rutas:
        r = c.get(ruta, headers=h(TOK_ANA))
        if r.status_code >= 500 or "psycopg2" in r.text or "invalid input syntax" in r.text:
            malas[ruta] = r.status_code
    return not malas, f"{len(rutas)} rutas; con 500 o texto SQL: {malas or 'ninguna'}"


@caso("SEG-27", "La cookie de sesión no la leen los scripts ni viaja a otros sitios", "A07 Autenticación / A02 Exposición",
      "HttpOnly, Secure, SameSite=Strict, Path=/ y prefijo __Host- (sin Domain)")
def _():
    _, galleta = login("ana@example.com")
    atributos = [a.strip().lower() for a in galleta.split(";")]
    faltan = [n for n, ok in (
        ("__Host-", galleta.startswith("__Host-")),
        ("HttpOnly", "httponly" in atributos),
        ("Secure", "secure" in atributos),
        ("SameSite=Strict", "samesite=strict" in atributos),
        ("Path=/", "path=/" in atributos),
        ("sin Domain", not any(a.startswith("domain=") for a in atributos)),
    ) if not ok]
    return not faltan, "faltan: " + ", ".join(faltan) if faltan else "; ".join(a for a in galleta.split("; ")[1:])


@caso("SEG-28", "Cerrar sesión invalida esa sesión en el servidor", "A07 Autenticación",
      "200 al cerrar y 401 después con el mismo token; las otras sesiones siguen")
def _():
    tok, _ = login("ana@example.com")
    antes = c.get("/api/auth/me", headers=h(tok)).status_code
    salir = c.post("/api/auth/logout", headers=h(tok)).status_code
    despues = c.get("/api/auth/me", headers=h(tok)).status_code
    otra = c.get("/api/auth/me", headers=h(TOK_ANA)).status_code
    return (antes, salir, despues, otra) == (200, 200, 401, 200), f"antes: {antes}, cerrar: {salir}, después: {despues}, otra sesión: {otra}"


@caso("SEG-29", "Un sitio ajeno no puede cambiar datos usando la cookie del usuario (CSRF)", "A01 Control de acceso",
      "403 con la cookie y un Origin ajeno; nada cambia")
def _():
    _, galleta = login("ana@example.com")
    r = c.put("/api/seguimiento/config", json={"url_panel": "https://script.google.com/macros/s/ajeno/exec"},
              headers={"Cookie": cookie_de(galleta), "Origin": ORIGEN_AJENO})
    actual = c.get("/api/seguimiento/config", headers=h(TOK_ANA)).json() or {}
    return r.status_code == 403 and "ajeno" not in str(actual.get("url_panel")), f"HTTP {r.status_code}: {r.text[:80]}"


@caso("SEG-30", "La cookie sí sirve desde el frontend oficial", "A07 Autenticación", "200 con la cookie y el Origin del frontend")
def _():
    _, galleta = login("ana@example.com")
    r = c.put("/api/seguimiento/config", json={"url_panel": "https://script.google.com/macros/s/oficial/exec"},
              headers={"Cookie": cookie_de(galleta), "Origin": "https://proyectoocr.v44nxx.online"})
    return r.status_code == 200, f"HTTP {r.status_code}"


# Debe ir al final: llena el límite de intentos de beto
@caso("SEG-25", "Fuerza bruta: el sexto intento fallido seguido queda bloqueado", "A07 Autenticación", "429 con Retry-After")
def _():
    codigos = [c.post("/api/auth/login", json={"email": "beto@example.com", "password": f"mala{i}"}).status_code for i in range(6)]
    ultimo = c.post("/api/auth/login", json={"email": "beto@example.com", "password": "mala"})
    return codigos[:5] == [401] * 5 and codigos[5] == 429 and ultimo.headers.get("retry-after"), f"{codigos}, Retry-After: {ultimo.headers.get('retry-after')}"


total = len(resultados)
pasan = sum(r["resultado"] == "PASA" for r in resultados)
print(f"\n{pasan}/{total} pasan")
json.dump({"base": BASE, "fecha": time.strftime("%Y-%m-%d %H:%M"), "pasan": pasan, "total": total,
           "casos": resultados}, open(SALIDA, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
