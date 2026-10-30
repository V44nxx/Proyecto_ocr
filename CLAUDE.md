# KondID OCR: reglas para trabajar en este repositorio

KondID lee fichas de documentos de identidad con OCR y las compara con las planillas del SENA. Los datos son de personas reales, entre ellas menores de edad.

Partes del sistema:

- Backend: FastAPI y PostgreSQL, en `backend/`.
- Frontend: Next.js 16, en `frontend/`.
- Panel de Seguimiento: Google Apps Script, en `apps-script/`.

**Cada push a `main` se publica en producción** (Dokploy despliega desde `main`) y lo usa una funcionaria a diario.

## Versiones: lo más importante

Las versiones las numera y publica **una sola persona: Manuel (Manuel151025)**. El objetivo es que nunca se repita un número ni choquen dos ramas.

- **Si trabajas en una rama** (por ejemplo `claude/...`) o para alguien que no es Manuel:
  - **no cambies el número de versión** y **no crees una sección numerada en el CHANGELOG**;
  - anota tus cambios en `## [Sin publicar]` de `CHANGELOG.md`;
  - deja `APP_VERSION`, `package.json` y `package-lock.json` como están;
  - quien integre la rama le asigna el número.
- **Al publicar** (solo quien publica):
  1. `git fetch` y revisa la última versión en `CHANGELOG.md` y en las etiquetas (`git tag --sort=-v:refname | head -1`). El número nuevo sale de ahí, **nunca de la rama**.
  2. Versionado semántico `MAJOR.MINOR.PATCH`: MINOR si trae algo nuevo, PATCH si solo trae correcciones.
  3. El mismo número en cuatro lugares:
     - `backend/app/config.py` (`APP_VERSION`);
     - `frontend/package.json` (`version`);
     - las **dos** líneas raíz de `frontend/package-lock.json`;
     - el título del CHANGELOG, `## [X.Y.Z] - AAAA-MM-DD`, con un `## [Sin publicar]` vacío arriba.
  4. Commit con el número entre paréntesis, por ejemplo `fix: listas completas por paginas (2.17.2)`.
  5. Etiqueta anotada `vX.Y.Z` y `git push --atomic origin main vX.Y.Z`.
  6. Revisa que `https://api.v44nxx.online/health` muestre la versión nueva y que el CI quede en verde.

## Formato del CHANGELOG

[Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/), en español.

- Cada versión empieza con un **Resumen** de 2 o 3 viñetas.
- Luego van las secciones que apliquen: `Agregado`, `Cambiado`, `Corregido`, `Seguridad` y `Pruebas`.
- Si hay cifras de pruebas, se escriben con su antes y después (por ejemplo, «Backend de 579 a 584 pruebas»).
- Las fallas de seguridad se mencionan **sin detalles que sirvan para aprovecharlas**.

## Antes de publicar: todo debe pasar

Los detalles están en `docs/PRUEBAS.md`.

- **Backend:** `python -m pytest -q --cov=app --cov-fail-under=80` desde `backend/`, con `TEST_DATABASE_URL` apuntando a un PostgreSQL de pruebas.
  - Córrelo en una copia limpia del repositorio, porque una prueba puede pasar solo por un archivo que quedó de antes.
- **Frontend:** `npx tsc --noEmit` y `npm run build`.
- **Panel de Seguimiento:** `node --test apps-script/seguimiento-fichas/pruebas/*.test.js`.
- **Interfaz y seguridad:** `pruebas/e2e/interfaz.py` y `pruebas/seguridad/dast_api.py`, contra una instalación **local**.
- **Pruebas primero:** cada corrección o función nueva lleva una prueba que falla con el código anterior.

## Reglas que no se rompen

- **Nunca hagas commit ni push sin que la persona lo apruebe.** Nunca uses `git push --force`.
- **Nunca pruebes contra producción** (`proyectoocr.v44nxx.online`, `api.v44nxx.online`). Una consulta a `/health` sí se permite.
- **Solo datos inventados en pruebas, ejemplos y capturas.**
  - Nunca uses fichas, nombres, cédulas o teléfonos reales.
  - Los correos de ejemplo van con `@example.com`.
  - Si una prueba se basa en un archivo real, reemplaza los datos personales y conserva el formato.
- **Nada de secretos en el repositorio** (`.env`, claves, credenciales de Google).
- **No describas fallas abiertas en archivos del repositorio**: es público. Para eso existe `SECURITY.md`.
- **Los registros (logs) no llevan datos personales.** Usa las funciones `enmascarar_*`.
- **Commits** con el formato `tipo(área): descripción` en español (`feat`, `fix`, `test`, `docs`).
- **Panel de Apps Script:**
  - No se publica con Dokploy. Hay que pegarlo en Google como dice `apps-script/seguimiento-fichas/LEEME.md`.
  - Si lo cambias, avisa que hay que actualizarlo allá.
