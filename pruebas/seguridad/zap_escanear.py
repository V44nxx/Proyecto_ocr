"""Escaneo de seguridad con OWASP ZAP 2.17 (modo automatización, sin interfaz).

Solo contra servidores de prueba con datos inventados (pruebas/semilla.py), NUNCA contra producción:
el escaneo activo envía ataques reales.

Uso: python zap_escanear.py <etiqueta> <url_api> <url_web> <openapi.json> <semilla_ids.json> <carpeta_reportes>
Variable de entorno ZAP_JAR: ruta a zap-2.17.0.jar (por defecto, la del paquete multiplataforma en ./ZAP_2.17.0).
 - API: importa la definición OpenAPI, agrega peticiones con los ids reales de la semilla y hace escaneo activo
   con la sesión de ana (cabecera Authorization). /api/auth/logout queda fuera: atacarlo revocaría esa sesión
   y el resto del escaneo correría sin ella.
 - Web: araña el frontend y deja el escaneo pasivo (cabeceras, cookies, librerías JS conocidas).
En producción /openapi.json no se publica; se genera desde backend/ con:
    ENVIRONMENT=development python -c "import json; from app.main import app; print(json.dumps(app.openapi()))" > openapi.json
El plan queda en <carpeta_reportes>/zap_plan_<etiqueta>.yaml y los reportes HTML y JSON al lado.
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import httpx

etiqueta, url_api, url_web, openapi, archivo_ids, carpeta = sys.argv[1:7]
IDS = json.loads(Path(archivo_ids).read_text(encoding="utf-8"))
carpeta = Path(carpeta).resolve()
carpeta.mkdir(parents=True, exist_ok=True)
ZAP_JAR = Path(os.environ.get("ZAP_JAR", "ZAP_2.17.0/zap-2.17.0.jar")).resolve()

token = httpx.post(f"{url_api}/api/auth/login",
                   json={"email": "ana@example.com", "password": IDS["clave"]}, timeout=30).json()["access_token"]


def ruta(p):
    return str(Path(p).resolve()).replace("\\", "/")


# Peticiones reales con los ids de la semilla: la importación OpenAPI deja los parámetros de ruta vacíos
f, p, comp = IDS["ficha_ana"], IDS["persona_ana"], IDS["comparacion_ana"]
peticiones = [
    ("GET", f"/api/personas?documento_id={f}", None), ("GET", f"/api/personas/{p}", None),
    ("PUT", f"/api/personas/{p}", '{"lugar_expedicion": "BOGOTA D.C."}'),
    ("GET", "/api/personas/buscar/cedula/1000000401", None), ("GET", f"/api/documentos/{f}", None),
    ("GET", f"/api/documentos/{f}/personas", None), ("GET", f"/api/documentos/{f}/estado", None),
    ("GET", f"/api/documentos/{f}/pagina/1?dpi=130", None), ("GET", f"/api/comparacion/{comp}", None),
    ("GET", f"/api/comparacion/{comp}/diferencias", None), ("GET", f"/api/exportacion/diferencias/{comp}", None),
    ("GET", f"/api/exportacion/xlsx?documento_id={f}", None), ("GET", "/api/seguimiento/config", None),
    ("PUT", "/api/seguimiento/config", '{"url_panel": "https://script.google.com/macros/s/abc123/exec"}'),
    ("GET", "/api/documentos/dashboard/estadisticas", None), ("GET", "/api/auth/me", None),
    ("POST", "/api/auth/olvide-password", '{"email": "ana@example.com"}'),
]
bloque_peticiones = "\n".join(
    f'  - url: "{url_api}{u}"\n    method: {m}'
    + (f"\n    headers: [\"Content-Type: application/json\"]\n    data: '{d}'" if d else "")
    for m, u, d in peticiones
)


plan = f"""
env:
  contexts:
  - name: kondid-api
    urls: ["{url_api}"]
    includePaths: ["{url_api}.*"]
    excludePaths: ["{url_api}/api/auth/logout.*"]
  - name: kondid-web
    urls: ["{url_web}"]
    includePaths: ["{url_web}.*"]
    excludePaths: ["{url_web}/api/.*", "{url_web}/_next/static/.*\\\\.map"]
  parameters:
    failOnError: false
    failOnWarning: false
    progressToStdout: true
jobs:
- type: replacer
  parameters:
    deleteAllRules: true
  rules:
  - description: "Sesion de ana en la API"
    url: "{url_api.replace('.', '[.]')}.*"
    matchType: req_header
    matchString: Authorization
    matchRegex: false
    replacementString: "Bearer {token}"
- type: openapi
  parameters:
    apiFile: "{ruta(openapi)}"
    targetUrl: "{url_api}"
    context: kondid-api
- type: requestor
  requests:
{bloque_peticiones}
- type: spider
  parameters:
    context: kondid-web
    url: "{url_web}"
    maxDuration: 2
- type: passiveScan-wait
  parameters:
    maxDuration: 5
- type: activeScan
  parameters:
    context: kondid-api
    maxScanDurationInMins: 20
    threadPerHost: 4
- type: passiveScan-wait
  parameters:
    maxDuration: 5
- type: report
  parameters:
    template: traditional-html
    reportDir: "{ruta(carpeta)}"
    reportFile: "zap_{etiqueta}"
    reportTitle: "KondID - OWASP ZAP ({etiqueta})"
  risks: [high, medium, low, info]
  confidences: [high, medium, low]
- type: report
  parameters:
    template: traditional-json
    reportDir: "{ruta(carpeta)}"
    reportFile: "zap_{etiqueta}"
  risks: [high, medium, low, info]
  confidences: [high, medium, low]
"""
archivo_plan = carpeta / f"zap_plan_{etiqueta}.yaml"
archivo_plan.write_text(plan, encoding="utf-8")

with tempfile.TemporaryDirectory() as home:
    cmd = ["java", "-Xmx2g", "-jar", str(ZAP_JAR), "-cmd", "-dir", home, "-autorun", str(archivo_plan)]
    print(" ".join(cmd[:6]), "...", flush=True)
    r = subprocess.run(cmd, cwd=str(ZAP_JAR.parent))
print("ZAP terminó con código", r.returncode)
