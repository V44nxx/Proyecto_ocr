# Panel de Seguimiento de fichas (Google Apps Script)

Es el panel que KondID muestra en **Seguimiento de fichas**. Lee y edita la hoja **FORMACIONES COMPLEMENTARIAS GRUPOS** directamente en Google Sheets, sin copias intermedias: lo que se guarda en el panel queda en la hoja, y lo que se escribe en la hoja aparece en el panel en menos de 15 segundos.

| Archivo | Qué es |
|---|---|
| `Codigo.gs` | Servidor: lee las pestañas, guarda los cambios y controla el acceso |
| `Index.html` | El panel: lista, filtros y formulario de seguimiento |
| `appsscript.json` | Manifiesto (zona horaria de Bogotá y publicación como aplicación web) |
| `pruebas/` | Pruebas de `Codigo.gs` con la estructura real del libro (datos personales reemplazados) |

## Qué lee

Las pestañas **REGULADA**, **PV**, **CAMPESENA** y **TECNOACADEMIA**. La copia oculta «TECNOACADEMIA » (con espacio al final) se ignora.

- Las columnas se buscan **por su título**, no por su letra. Se puede insertar, mover o quitar columnas sin tocar el script, siempre que los títulos sigan iguales (no importan las mayúsculas, las tildes ni los espacios).
- Un registro es una fila con programa, requerimiento, ficha o instructor. Así también salen las solicitudes nuevas que aún no tienen programa.
- En REGULADA cada registro ocupa 3 filas combinadas: se lee y se escribe en la primera.

## Qué se edita desde el panel

Solo las columnas de seguimiento que existan en cada pestaña:

| Campo | REGULADA | PV | CAMPESENA | TECNOACADEMIA |
|---|:-:|:-:|:-:|:-:|
| Programación ficha | ✓ | | | |
| Estado de la ficha | ✓ | | | |
| Estado de los aprendices | ✓ | | | |
| Fecha de publicación | ✓ | | | ✓ |
| N° de inscritos / matriculados | ✓ | | | ✓ |
| Certificación | ✓ | | | ✓ |
| No aprobados u otra novedad | ✓ | | | ✓ |
| Observaciones | ✓ | ✓ | ✓ | ✓ |

Para que PV o CAMPESENA tengan más campos, basta con agregar en esa pestaña una columna con el mismo título (por ejemplo «ESTADO DE LA FICHA»). El panel la toma sola.

Los datos de la programación (empresa, instructor, fechas...) se muestran pero no se editan desde el panel.

## Cómo se mantiene al día

- Cada edición de la hoja, hecha a mano o desde el panel, sube un número de versión.
- El panel pregunta por ese número cada 15 segundos (solo mientras la pestaña está visible) y vuelve a leer la hoja cuando cambió. Las filas que cambiaron se resaltan.
- Si dos personas editan el mismo campo a la vez, el segundo cambio **no pisa** al primero: el panel muestra lo que dice ahora la hoja y pide confirmar.
- Si se insertan o borran filas mientras alguien tiene un registro abierto, el panel no escribe en la fila equivocada: pide volver a abrirlo.
- Cada cambio hecho desde el panel queda en la pestaña oculta **BITACORA_PANEL** (fecha, pestaña, fila, ficha, campo, antes y después).

## Instalación

1. **La hoja debe estar en formato Google Sheets.** Si subiste el `.xlsx` a Drive, ábrelo y usa *Archivo → Guardar como hoja de cálculo de Google*. Apps Script no funciona sobre un `.xlsx`.
2. En esa hoja abre **Extensiones → Apps Script**.
3. Reemplaza el contenido de `Código.gs` con el de `Codigo.gs`.
4. Crea un archivo HTML llamado exactamente **`Index`** (*+ → HTML*) y pega el contenido de `Index.html`.
5. En *Configuración del proyecto*, activa «Mostrar el archivo de manifiesto appsscript.json en el editor» y reemplaza su contenido con el de `appsscript.json`.
6. Elige la función **`configurar`** y dale *Ejecutar*. Acepta los permisos. En el *Registro de ejecución* aparece la clave: `?k=...`.
7. **Implementar → Nueva implementación → Aplicación web**:
   - Ejecutar como: **Yo**
   - Quién tiene acceso: **Cualquier persona**
8. Copia la URL de la aplicación web (termina en `/exec`) y pégale al final el `?k=...` del paso 6.
9. En KondID, en **Seguimiento de fichas → Configurar**, pega esa URL completa.

> ⚠️ La clave es lo único que protege el panel, porque se publica para «Cualquier persona» (KondID lo muestra incrustado). No compartas la URL con la clave. Si se filtra, ejecuta **`cambiarClave`** y actualiza el enlace en KondID.

## Actualizar el panel

Después de cambiar `Codigo.gs` o `Index.html`: **Implementar → Gestionar implementaciones → ✏️ → Versión: Nueva versión → Implementar**. La URL no cambia, así que no hay que tocar nada en KondID.

## Pruebas

```bash
node --test apps-script/seguimiento-fichas/pruebas/*.test.js
```

Corren en CI (job «Panel de Seguimiento (Apps Script)»). Con `LIBRO=/ruta/exportacion.json` se prueban sobre otra exportación del libro.
