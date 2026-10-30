# Pruebas de KondID

Cómo se prueba KondID, dónde está cada tipo de prueba y cómo se ejecuta. Todas las pruebas usan **datos inventados** y bases de datos desechables; ninguna se corre contra producción.

## Estrategia (cuadrantes de pruebas ágiles)

| Cuadrante | Propósito | En KondID |
|---|---|---|
| **Q1**: apoyan al equipo, cara a la tecnología (automáticas) | Que cada pieza haga lo que debe | Pruebas unitarias y de componentes con pytest (`backend/tests/`) |
| **Q2**: apoyan al equipo, cara al negocio | Que el sistema cumpla las historias de usuario | Escenarios BDD en Gherkin (`backend/tests/bdd/*.feature`) y pruebas funcionales de la API |
| **Q3**: critican el producto, cara al negocio (manuales) | Que sea usable y aceptable para quien lo usa | Pruebas de interfaz de punta a punta (`pruebas/e2e/`), sesiones exploratorias y aceptación con los usuarios |
| **Q4**: critican el producto, cara a la tecnología (herramientas) | Rendimiento, carga y seguridad | JMeter (`pruebas/carga/`), OWASP ZAP y batería de seguridad (`pruebas/seguridad/`), pip-audit, npm audit y Bandit |

Las funciones nuevas y los arreglos se hacen con **TDD**: primero la prueba que falla con el código actual (rojo), después el cambio mínimo que la hace pasar (verde) y al final la limpieza (refactorización) con toda la suite en verde.

## 1. Unitarias, de integración y BDD (backend)

```bash
cd backend
pip install -r requirements-dev.txt
python -m pytest -q
```

- Sin base de datos, las pruebas que necesitan PostgreSQL se omiten.
- Para correrlas todas, apunta `TEST_DATABASE_URL` a una base **de pruebas vacía**. Cada prueba borra y recrea el esquema `public`:

```bash
TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:5544/pruebas python -m pytest -q
```

- Los escenarios BDD están en español (`# language: es`) en `tests/bdd/*.feature`. Los pasos en Python están en `tests/bdd/test_*.py`. Para correr solo esos escenarios: `python -m pytest tests/bdd -v`.
- Las ayudas comunes de las pruebas con base de datos (crear usuarios, fichas, personas, tokens) están en `tests/utilidades_pg.py`.

## 2. Entorno de prueba de punta a punta

Las pruebas de interfaz, carga y seguridad necesitan la aplicación corriendo con datos inventados:

1. Una base PostgreSQL desechable, por ejemplo con `initdb` en una carpeta temporal y `pg_ctl -o "-p 5544"`, y dentro una base `e2e`.
2. La semilla de datos inventados (usuarios admin, ana y beto; fichas con PDF sintético; personas y una comparación):

   ```bash
   cd backend
   DATABASE_URL=postgresql://postgres@127.0.0.1:5544/e2e PYTHONPATH=. python ../pruebas/semilla.py /tmp/kondid_e2e
   ```

3. El SMTP de captura, que guarda los correos como `.eml` en vez de enviarlos: `python pruebas/smtp_captura.py /tmp/kondid_correos 2525`.
4. El backend configurado como producción, pero contra la base de prueba:

   ```bash
   DATABASE_URL=postgresql://postgres@127.0.0.1:5544/e2e ENVIRONMENT=production SECRET_KEY=<una clave de pruebas larga> \
   SMTP_HOST=127.0.0.1 SMTP_PORT=2525 SMTP_TLS=false SMTP_USER=kondid@example.com FRONTEND_URL=https://kondid-pruebas.example \
   GOOGLE_DOCUMENT_AI_ENABLED=false RAPID_OCR_ENABLED=false uvicorn app.main:app --host 127.0.0.1 --port 8000
   ```

5. El frontend compilado contra ese backend: `INTERNAL_BACKEND_URL=http://127.0.0.1:8000 npm run build && npx next start -p 3000`.

Los límites de intentos se cuentan en la base (tabla `intentos_limitados`): antes de cada tanda de pruebas, vuelve a sembrar la base para empezar sin bloqueos.

## 3. Interfaz de punta a punta (Playwright)

```bash
pip install playwright
KONDID_IDS=/tmp/kondid_e2e/semilla_ids.json KONDID_CORREOS=/tmp/kondid_correos \
python pruebas/e2e/interfaz.py /tmp/kondid_resultados
```

Usa el Chrome instalado (`channel="chrome"`). Son 39 casos (`CP-UI-01` a `CP-UI-39`):

- **Recorrido:** el inicio de sesión, Personas y el visor de documentos, la exportación, el cambio y la recuperación de contraseña, la verificación en dos pasos, la auditoría y el cierre de sesión.
- **Sesión:** que viaje en una cookie `HttpOnly` y `SameSite=Strict`, y que tras cerrar sesión el servidor la rechace.
- **Interfaz:**
  - el logo lleva al Dashboard;
  - los selectores en ventana y el diálogo de confirmación propio;
  - un solo aviso al cambiar el tema varias veces;
  - los avisos de conexión, servidor, versión y sesión.
  - el panel de Seguimiento incrustado conserva su clave y recibe el nombre del usuario conectado.
- **Datos recientes:**
  - con la red a 1,5 s por viaje, la lista de Personas aparece al instante al volver;
  - después de cerrar sesión, volver atrás no la deja ver.
- **Sin errores:** ningún error de JavaScript, las pantallas llevan la política de contenido (CSP) y ninguna la viola.

Deja `e2e.json` y capturas en la carpeta de resultados.

## 4. Seguridad

| Prueba | Herramienta | Cómo |
|---|---|---|
| Pruebas automáticas de seguridad | pytest | `tests/test_seguridad_*.py`, `tests/bdd/aislamiento_de_cuentas.feature` (corren con la suite) |
| Batería de caja negra (control de acceso, errores, cabeceras, CORS, cookie de sesión, cierre de sesión, CSRF, inyección, fuerza bruta, robustez) | `pruebas/seguridad/dast_api.py` | `python pruebas/seguridad/dast_api.py http://127.0.0.1:8000 /tmp/kondid_e2e/semilla_ids.json resultado.json` |
| Escaneo dinámico (pasivo y activo) | OWASP ZAP 2.17 | `python pruebas/seguridad/zap_escanear.py <etiqueta> <url_api> <url_web> openapi.json semilla_ids.json <carpeta>` (arma el plan con la sesión y los ids reales; detalles en el archivo) |
| Dependencias con avisos conocidos | pip-audit, npm audit | `pip-audit -r backend/requirements.txt` · `npm audit --omit=dev` |
| Dependencias (segunda opinión; detecta avisos que pip-audit no tiene, como los de PyMuPDF) | Snyk Open Source, OSV-Scanner | `snyk test --file=frontend/package-lock.json` · `snyk test --file=backend/requirements.txt --package-manager=pip --command=<python del venv>` (requiere `snyk auth` y pip en el venv) · `osv-scanner scan source --lockfile=backend/requirements.txt --lockfile=frontend/package-lock.json` |
| Análisis estático | Bandit | `bandit -r backend/app -ll` |
| Análisis de código (flujo de datos) | CodeQL (GitHub Advanced Security), Snyk Code, Semgrep | CodeQL corre solo en GitHub Actions (`.github/workflows/codeql.yml`, pestaña Security) · `snyk code test` (sube el código a Snyk) · `semgrep scan --metrics=off --config p/owasp-top-ten --config p/python --config p/typescript --config p/react --config p/nextjs --config p/dockerfile` |
| Secretos en el código y en todo el historial de git | Gitleaks | `gitleaks git . --redact` |
| Dockerfiles, configuración y dependencias en un solo paso | Trivy | `trivy fs . --scanners vuln,secret,misconfig --skip-dirs backend/.venv --skip-dirs frontend/node_modules` |

Cada herramienta ve cosas distintas: en la revisión de la 2.9.0, PyMuPDF solo lo marcaron Snyk y Trivy, los registros con tokens salieron de revisar a mano los hallazgos de Gitleaks y la condición de carrera del Seguimiento, de un error 500 durante ZAP. Revisa también los falsos positivos conocidos: rutas que llegan por línea de comandos en `pruebas/`, contraseñas inventadas en `tests/` y el enlace de descarga `blob:` de `lib/api.ts`.

## 5. Carga y estrés (JMeter)

```bash
jmeter -n -t pruebas/carga/kondid_api.jmx -Jhost=127.0.0.1 -Jport=8000 -Jusuario=ana@example.com \
  -Jclave='ClavePrueba2026!' -Jficha=<ficha_ana de semilla_ids.json> -Jhilos=20 -Jrampa=20 -Jduracion=90 \
  -l resultados.jtl -e -o reporte_html
```

- Cada hilo es un operador que inicia sesión una vez y repite: lista de personas, estadísticas, vista previa y perfil, con pausas de 0,3 a 0,8 s.
- `-Jhilos` sube la cantidad de operadores simultáneos: 20 es carga normal y de 100 en adelante es estrés.
- `-Jlimite_ms` (por defecto 2000) es el tiempo máximo aceptado por respuesta.
- El reporte HTML queda en `reporte_html/index.html`.

## 6. Rendimiento y OCR

**Navegación.** Mide cuánto tarda en verse el contenido al cambiar de módulo, con la latencia de producción simulada (210 ms por viaje). Usa el entorno de la sección 2:

```bash
python pruebas/rendimiento/medir_navegacion.py /tmp/kondid_e2e/semilla_ids.json /tmp/kondid_rendimiento etiqueta
```

**OCR.** `pruebas/ocr/ficha_sintetica.py` dibuja una ficha escaneada inventada: cada persona es una cédula de frente y reverso, con números y nombres al azar. `medir_ocr.py` la procesa y cuenta cuántos campos salen bien. Necesita la base de la sección 2:

```bash
cd backend
DATABASE_URL=postgresql://postgres@127.0.0.1:5544/e2e GOOGLE_DOCUMENT_AI_ENABLED=false PYTHONPATH=.   python ../pruebas/ocr/medir_ocr.py rapid 10 /tmp/kondid_ocr 2     # RapidOCR de verdad
DATABASE_URL=postgresql://postgres@127.0.0.1:5544/e2e GOOGLE_DOCUMENT_AI_ENABLED=false PYTHONPATH=.   python ../pruebas/ocr/medir_ocr.py docai 10 /tmp/kondid_ocr 2     # Document AI simulado, 1,5 s por página
```

- El último número fija los núcleos, para imitar el VPS de producción (2).
- El modo `docai` mide cuántas páginas se leen a la vez, no la calidad de Google.
- Repite las dos mediciones antes y después de cambiar el OCR. Valores de la 2.17.0 con 10 personas: RapidOCR 96 % de los campos a 2,2 s por página; Document AI simulado, 9,7 s en total.

## 7. Regresión automática (GitHub Actions)

`.github/workflows/pruebas.yml` corre en cada push y pull request:

- **Backend**: toda la suite con un PostgreSQL de servicio (unitarias, integración y BDD). Falla si la cobertura baja del 80 %.
- **Frontend**: revisión de tipos y compilación de producción.
- **Panel de Seguimiento (Apps Script)**: `node --test apps-script/seguimiento-fichas/pruebas/*.test.js`. Carga `Codigo.gs` con imitaciones de Google Sheets sobre la estructura real del libro, con los datos personales reemplazados. Se corre igual en local, con Node 24 o más reciente.
- **Seguridad**: pip-audit, Bandit y npm audit de las dependencias de producción.

El workflow no despliega nada: Dokploy sigue desplegando desde `main`.

## Criterios de entrada y salida de una versión

- **Entrada:** el cambio tiene pruebas nuevas que fallan con el código anterior.
- **Salida:**
  - la suite completa pasa con PostgreSQL, con cobertura de 80 % o más, también en una copia limpia del repositorio (`git archive`). Una prueba puede pasar solo porque encuentra un archivo que quedó de una corrida anterior;
  - la batería de seguridad (`dast_api.py`) pasa;
  - el frontend compila;
  - la prueba de punta a punta pasa;
  - el CHANGELOG y la versión están al día;
  - después del despliegue, `/health` muestra la versión nueva.
