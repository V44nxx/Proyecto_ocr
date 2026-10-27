# Panel de Seguimiento de fichas (Google Apps Script)

Es el panel que KondID muestra en **Seguimiento de fichas**. Lee y edita la hoja **FORMACIONES COMPLEMENTARIAS GRUPOS** directamente en Google Sheets, sin copias intermedias: lo que se guarda en el panel queda en la hoja, y lo que se escribe en la hoja aparece en el panel en menos de 15 segundos.

| Archivo | Qué es |
|---|---|
| `Codigo.gs` | Servidor: lee las pestañas, guarda los cambios y controla el acceso |
| `Index.html` | El panel: lista, filtros y formulario de seguimiento |
| `appsscript.json` | Manifiesto opcional (zona horaria de Bogotá y publicación como aplicación web) |
| `pruebas/` | Pruebas de `Codigo.gs` con la estructura real del libro (datos personales reemplazados) |

## Qué lee

Las pestañas **REGULADA**, **PV**, **CAMPESENA** y **TECNOACADEMIA**. La copia oculta «TECNOACADEMIA » (con espacio al final) se ignora.

- Las columnas se buscan **por su título**, no por su letra. Se puede insertar, mover o quitar columnas sin tocar el script, siempre que los títulos sigan iguales (no importan las mayúsculas, las tildes ni los espacios).
- Un registro es una fila con programa, requerimiento, ficha o instructor. Así también salen las solicitudes nuevas que aún no tienen programa.
- En REGULADA cada registro ocupa 3 filas combinadas: se lee y se escribe en la primera.

## Etapas y alertas

Cada registro muestra su **etapa** según la fecha de hoy y sus fechas de inicio y fin:

| Etapa | Cuándo |
|---|---|
| Inicia hoy | La fecha de inicio es hoy |
| Por iniciar | Empieza en 7 días o menos |
| Programada | Empieza en más de 7 días |
| En ejecución | Ya empezó y faltan más de 3 días para terminar |
| Por finalizar | Termina en 3 días o menos |
| Finalizada | La fecha de fin ya pasó |
| Fechas inválidas | La fecha de fin es anterior a la de inicio |
| Fecha faltante o ilegible | Falta una fecha o está mal escrita (por ejemplo «8/10/0206») |

También muestra estas **alertas**:

- **Ficha sin crear / sin código**: el registro no tiene número de ficha.
- **Sin instructor**: el registro no tiene instructor asignado.
- **Cruce de instructor**: el mismo instructor tiene dos formaciones, no finalizadas, cuyas fechas se solapan. El detalle dice con cuál se cruza.
- **Datos distintos entre pestañas**: la misma ficha aparece en dos pestañas con otras fechas u otro instructor.

La lista se ordena con lo más urgente arriba. Los recuadros de arriba (Por iniciar, En ejecución, Por finalizar, Con alertas) filtran la lista al hacer clic.

Esta lógica antes estaba en `Motor.gs`. Ahora está dentro de `Codigo.gs`, así que **no hay que pegar `Motor.gs`**. Si se pega, sus funciones chocan con las de `Codigo.gs` y el panel deja de funcionar.

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

1. **La hoja debe estar en formato Google Sheets.** Si subiste el `.xlsx` a Drive, ábrelo y usa *Archivo → Guardar como hoja de cálculo de Google*, o en una hoja nueva usa *Archivo → Importar → Subir → Reemplazar hoja de cálculo*. Apps Script no funciona sobre un `.xlsx` ni en Excel de escritorio.
2. En esa hoja abre **Extensiones → Apps Script**.
3. Reemplaza el contenido de `Código.gs` con el de `Codigo.gs`.
4. Crea un archivo HTML llamado exactamente **`Index`** (*+ → HTML*) y pega el contenido de `Index.html`. Guarda (Ctrl + S).
5. Vuelve a la hoja y **recárgala (F5)**. Junto a «Ayuda» aparece el menú **Seguimiento de fichas**.
6. Elige **Seguimiento de fichas → Configurar (primera vez)** y acepta los permisos. Si Google dice que la app no está verificada: *Configuración avanzada → Ir a … (no seguro) → Permitir*. Vuelve a elegir la opción si los permisos interrumpieron la primera vez.
7. Desde ya, **Seguimiento de fichas → Abrir panel** muestra el panel encima de la hoja.
8. Para KondID hay que publicarlo. En Apps Script: **Implementar → Nueva implementación → Aplicación web**:
   - Ejecutar como: **Yo**
   - Quién tiene acceso: **Cualquier persona**
9. Copia la URL de **Implementar → Gestionar implementaciones** (termina en `/exec`) y pégale al final el `?k=...` que muestra **Seguimiento de fichas → Ver enlace para KondID** en la hoja. Usa siempre la URL de «Gestionar implementaciones»: es la única que seguro corresponde a la implementación activa.
10. En KondID, en **Seguimiento de fichas → Configurar**, pega ese enlace.

| Opción del menú | Qué hace |
|---|---|
| Abrir panel | Abre el panel en una ventana encima de la hoja |
| Ver enlace para KondID | Muestra la clave (`?k=...`) y cómo armar el enlace para KondID |
| Configurar (primera vez) | Crea la clave y la actualización automática |
| Cambiar la clave del enlace | Crea una clave nueva (pide confirmación); el enlace viejo deja de funcionar |

> ⚠️ La clave es lo único que protege el panel, porque se publica para «Cualquier persona» (KondID lo muestra incrustado). No compartas la URL con la clave. Si se filtra, usa **Cambiar la clave del enlace** y actualiza el enlace en KondID.

## Actualizar el panel

Después de cambiar `Codigo.gs` o `Index.html`: **Implementar → Gestionar implementaciones → ✏️ → Versión: Nueva versión → Implementar**. La URL no cambia, así que no hay que tocar nada en KondID.

## Pruebas

```bash
node --test apps-script/seguimiento-fichas/pruebas/*.test.js
```

Corren en CI (job «Panel de Seguimiento (Apps Script)»). Con `LIBRO=/ruta/exportacion.json` se prueban sobre otra exportación del libro.
