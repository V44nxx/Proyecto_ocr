# Changelog

Todos los cambios relevantes de **KondID OCR** (sistema OCR para documentos de identidad colombianos) se documentan en este archivo.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y las versiones usan el esquema `MAJOR.MINOR.PATCH` de [Semantic Versioning](https://semver.org/lang/es/).

## Cómo se reconstruyeron las versiones

El repositorio no tenía etiquetas de versión, así que las versiones 1.0.0 a 2.1.0 se asignaron de forma retroactiva a partir del historial de git:

- **1.0.0** es el commit inicial (12-ago-2026), donde se fijó `APP_VERSION = "1.0.0"`.
- Desde ahí, **cada semana de trabajo (lunes a domingo) es una versión**: sube MINOR si la semana trae funcionalidades nuevas y PATCH si solo trae correcciones.
- **2.0.0** marca el relanzamiento como **KondID OCR v2.0** (semana del 5 al 11 de octubre de 2026), que es como ya lo nombran la documentación y la interfaz.
- La fecha de cada versión es la de su último commit. Cada entrada reproduce el mensaje del commit y enlaza a él.

## Cómo registrar cambios nuevos

1. Anota cada cambio en **[Sin publicar]**, en la categoría que corresponda, en el mismo commit que lo introduce.
2. Cada push a `main` se despliega en producción, así que cada push con cambios en la app se publica como versión: PATCH si solo trae correcciones y MINOR si trae funcionalidades nuevas.
3. Al publicar, cambia ese título por el número de versión y la fecha, deja un [Sin publicar] vacío arriba y crea la etiqueta (`git tag vX.Y.Z`).
4. Mantén `APP_VERSION` (`backend/app/config.py`) y `version` (`frontend/package.json` y `package-lock.json`) con el mismo número.

## [Sin publicar]

## [2.3.0] - 2026-10-14

**Resumen**

- El OCR ya no recorta nombres femeninos (JULIANA quedaba como JULIAN) ni borra nombres parecidos a un encabezado (ROMERO, INDIRA). Los que ya estaban dañados se recuperan desde la planilla Excel o se marcan para revisión.
- Al abrir una persona, su documento se muestra a la izquierda del panel, sin botones ni ventanas extra.
- La tabla de Personas queda en orden alfabético.

### Agregado

- En pantallas de 1024 px o más, el documento de la persona aparece en el espacio libre a la izquierda del panel. Usa el mismo visor: se arrastra, tiene zoom y permite pasar del frente al reverso. Al elegir otra persona, el visor cambia a su documento, y al cerrar el panel se cierra también el documento.

### Cambiado

- La tabla de Personas se ordena por nombre completo, de la A a la Z. Las tildes no alteran el orden y la Ñ va después de la N.
- El botón "Abrir página" solo aparece en pantallas pequeñas, donde no cabe el documento al lado del panel.
- El visor se vuelve a ajustar cuando cambia el tamaño de la ventana.

### Corregido

- El limpiador de nombres quitaba la vocal final de nombres como ANGELA, JULIANA, MANUELA, ISABELA, RAFAELA o MARTINA, que quedaban como ANGEL, JULIAN, MANUEL, etc. También borraba nombres y apellidos que se parecen a un encabezado de la cédula, como ROMERO (por NUMERO) o INDIRA (por INDICE). Esto pasaba al leer las cédulas y en cada reinicio del servidor.
- Reparación única de los nombres ya dañados:
  - si la persona está en una planilla Excel de su usuario y su nombre es justo la versión recortada del nombre de la planilla, se recupera el de la planilla;
  - si no, a las mujeres con un nombre masculino que pudo quedar recortado (ANGEL, JULIAN, MANUEL…) se les marca "Por revisar" con el motivo, para confirmarlas contra la cédula;
  - la marca se quita al corregir el nombre o al aprobar a la persona;
  - los nombres corregidos a mano no se tocan.

## [2.2.1] - 2026-10-14

**Resumen**

- Correcciones de integridad de datos: los reinicios del servidor ya no cambian personas de ficha ni deshacen nombres corregidos a mano, y el OCR deja de perder personas.
- Comparación, exportación y cancelación vuelven a funcionar en los casos que fallaban.

### Cambiado

- Eliminar un usuario elimina también sus fichas, personas y comparaciones, con sus archivos. Antes quedaban sin dueño y, en los siguientes reinicios, pasaban a la cuenta del administrador. El aviso de confirmación lo explica.
- "Cancelar subida" (en Documentos y en el aviso flotante) cancela solo los documentos de esa subida y no otros procesos en curso. Una ficha que ya terminó no se borra desde "Cancelar".
- Al editar el nombre completo de una persona, sus nombres y apellidos quedan coherentes con el nuevo valor.

### Corregido

- Al arrancar, el servidor movía las personas de las fichas de 1 o 2 páginas a la ficha grande más reciente y ocultaba la ficha original. Ahora solo devuelve a su ficha las personas de un PDF individual subido con "Subir PDF".
- Al arrancar, el servidor rehacía el nombre completo desde nombres y apellidos y deshacía las correcciones manuales.
- El reporte de una comparación incluye solo las personas de quien la hizo.
- La comparación fallaba cuando encontraba a una persona por nombre con otra cédula. Ahora corrige la cédula y, si la persona ya existía como registro creado desde la planilla, conserva el registro leído del PDF.
- Si la comparación falla, ya no deja guardados cambios a medias.
- Al marcar una discrepancia de nombre, la comparación ya no modifica personas de otras cuentas.
- El OCR perdía los datos al volver a encontrar una persona que ya estaba en revisión.
- Solo se guardaba una persona sin cédula por cuenta; ahora se guardan todas.
- "Corregir" una fecha desde Comparación respondía con error 500. Ahora guarda la fecha, y una fecha inválida responde 400.
- Exportar con el filtro "Menores (< 14)" respondía con error 500.
- El OCR quitaba el primer dígito a las cédulas pegadas a su etiqueta ("NUIP1098…" se leía como "NUIPI098…").
- Con una contraseña incorrecta, la página de inicio de sesión se recargaba y no mostraba el error.

## [2.2.0] - 2026-10-14

**Resumen**

- Panel de la persona más claro: arriba el nombre completo en un solo campo, el tipo de documento y el número; el resto de los datos queda en "Ver más".
- Selector de fichas en Personas, visor del documento que se arrastra con el cursor y scroll solo dentro del panel abierto.

### Agregado

- Selector de fichas en Personas: lista todas las fichas subidas, las más recientes primero, con su fecha, páginas y personas, un buscador y la opción "Todas las fichas". La ficha elegida queda en el enlace (`?documento_id=`).
- Botón "Ver más datos" en el panel de la persona con la fecha de nacimiento y la edad, el sexo y la fecha y el lugar de expedición.
- Visor del documento: se arrastra con el cursor, hace zoom con la rueda (centrado en el cursor) y con botones, se ajusta con doble clic y se maneja con las flechas del teclado; Escape lo cierra. Al acercar, la página se carga a 200 dpi para que se lea nítida.
- El formulario de edición incluye sexo, fecha de expedición y lugar de expedición.

### Cambiado

- El panel de la persona es más ancho (720 px en pantallas grandes y pantalla completa en el celular) y los nombres largos bajan de línea en vez de cortarse.
- Nombres y apellidos ya no se muestran ni se editan por separado: el panel y el formulario usan el nombre completo.
- Con el panel o un modal abierto solo se desplaza su contenido; la página de fondo queda quieta.

### Corregido

- El panel mostraba porcentajes de confianza fijos (99 %, 95 %, 98 % y 97 %) que no salían de los datos; ahora muestra la confianza real del OCR.
- Al acercar el documento, la parte de arriba y la izquierda de la página quedaban fuera de alcance.
- Soltar un arrastre encima del fondo oscuro ya no cierra el visor.
- Contraste y soporte de modo claro y oscuro en Personas y Exportación.

### Mantenimiento

- El selector de fichas, el visor del documento y el bloqueo de scroll pasan a componentes propios (`components/personas/` y `hooks/useBloquearScroll.ts`), y la página de Personas queda 112 líneas más corta.

## [2.1.1] - 2026-10-13

**Resumen**

- Endurecimiento de seguridad: crear usuarios y ejecutar migraciones exige administrador, las subidas respetan el límite de tamaño y el administrador inicial se configura con variables de entorno.
- Se agrega este changelog y la versión de la app queda alineada con él.

### Cambiado

- El administrador inicial se crea al arrancar con `ADMIN_EMAIL` y `ADMIN_PASSWORD`, solo si ese correo no existe; nunca modifica usuarios existentes ni sus contraseñas, y rechaza correos con los que no se podría iniciar sesión. **En una instalación nueva hay que definir esas dos variables** para tener un administrador.
- Las subidas validan todos los archivos (extensión y tamaño) antes de guardar cualquiera; si uno falla, no queda ningún documento a medias en estado "procesando".
- `APP_VERSION` (`backend/app/config.py`) y `version` (`frontend/package.json` y `package-lock.json`) quedan alineados con este changelog.

### Corregido

- El listado de personas de un documento del historial ya no falla con error 500 cuando solo queda el snapshot guardado del documento (faltaba importar `re`).

### Seguridad

- `POST /api/auth/register` exige una sesión de administrador.
- `/api/sistema/migrar-db` exige una sesión de administrador.
- Las subidas de PDF y Excel respetan `MAX_FILE_SIZE_MB` (50 MB por defecto, el mismo límite que anuncia la pantalla de Documentos) y responden 413 si se supera.
- Se quitan del código y de `database/init.sql` las credenciales fijas de administrador, y el backend deja de restablecer contraseñas al arrancar.

### Documentación

- Se agrega este `CHANGELOG.md` con el historial de versiones 1.0.0 a 2.1.0 reconstruido desde git.
- El README y `.env.example` documentan `ADMIN_EMAIL` y `ADMIN_PASSWORD`.

### Mantenimiento

- Tests de seguridad de la API en `backend/tests/test_seguridad_api.py`.

## [2.1.0] - 2026-10-13

**Resumen**

- El Excel vuelve a ser opcional al subir PDFs.
- Rediseño de la tabla de personas, con barra de estadísticas interactiva y panel lateral de detalles.
- Vista previa más rápida: caché en disco, JPEG y prefetch.
- Exportación reorganizada y mejor desegmentación de apellidos.

### Cambiado

- **ui:** Optimizar distribucion de exportacion con configuracion superior y tabla de ancho completo ([`f502707`](https://github.com/V44nxx/Proyecto_ocr/commit/f5027078d6d109df22fea8104866cc3b7dd41e8a))
- **personas:** Rediseñar tabla, barra de estadísticas interactiva y panel lateral de detalles ([`4e430a4`](https://github.com/V44nxx/Proyecto_ocr/commit/4e430a4dcd0570fbba2c3a3e017bf7649e63e8a2))
- **documentos:** Permitir subida y procesamiento de PDF sin requerir planilla Excel obligatoria ([`14b7d5e`](https://github.com/V44nxx/Proyecto_ocr/commit/14b7d5e2334ee099ed6e75d5c2df513a6e67354d))

### Rendimiento

- **preview:** Optimizar carga de vista previa con cache en disco, JPEG y prefetch ([`77c679c`](https://github.com/V44nxx/Proyecto_ocr/commit/77c679c7d2d87d2410d5264b5dee423f3399c8b3))

### Corregido

- **exportacion:** Alinear buscador y botones de accion en una sola fila ([`b7b2361`](https://github.com/V44nxx/Proyecto_ocr/commit/b7b23614cbab7e9c34af7e85830d7acf4a1bd7ef))
- **ocr:** Mejorar desegmentacion de apellidos, descarte de TFTOLIB y limpieza de letras residuales de sexo ([`9afaa4d`](https://github.com/V44nxx/Proyecto_ocr/commit/9afaa4dda36d0a3b750747be7f249efef7dda425))

### Mantenimiento

- Eliminar archivos temporales de esquemas y diagramas drawio ([`7f68d73`](https://github.com/V44nxx/Proyecto_ocr/commit/7f68d7327f65019668b62fa57fe0b85ace63f262))

## [2.0.0] - 2026-10-09

**Resumen**

- Relanzamiento como **KondID OCR v2.0**: rediseño con principios de Apple Design en dashboard, sidebar, documentos, exportación, usuarios y login, y documentación integral del sistema.
- Soporte para certificados de antecedentes de varias hojas.
- Google Document AI vuelve a ser el motor primario, con RapidOCR de respaldo automático, y hay un fast-path para PDFs con texto nativo.
- Muchas correcciones en la extracción de nombres (nombres pegados, firmas manuscritas, cédula amarilla, datos externos al documento).

### Agregado

- Soporte para certificado de antecedentes multi-hoja y alerta global de personas faltantes en PDF/Excel ([`9f5e104`](https://github.com/V44nxx/Proyecto_ocr/commit/9f5e1043a69874df6a8f3336194e11f1495cc01c))

### Cambiado

- **dashboard:** Rediseño con principios de Apple Design e integración de skill apple-design ([`92990a7`](https://github.com/V44nxx/Proyecto_ocr/commit/92990a74266bfa1277b942fbabf336d6e85015d8))
- **ui:** Rediseño del sidebar lateral con principios de Apple Design y materiales translúcidos ([`5aa2c46`](https://github.com/V44nxx/Proyecto_ocr/commit/5aa2c46b5fb534eb7b4fd7dd471411cbf71dede3))
- **design:** Aplicar sistema de diseno Apple a documentos, exportacion y usuarios con tokens globales ([`b663488`](https://github.com/V44nxx/Proyecto_ocr/commit/b66348804f1bf8f607ca8127d63ed3bdd6a71b10))
- **auth:** Rediseñar y reorganizar login con principios Apple Design sin colores neon ([`5d1dca5`](https://github.com/V44nxx/Proyecto_ocr/commit/5d1dca57b4762baf73efd42477fd0aef4f22a4dc))

### Rendimiento

- Fast-path para PDFs nativos (antecedentes/reversos), adaptabilidad CPU y diagnostico de motores ([`1c16962`](https://github.com/V44nxx/Proyecto_ocr/commit/1c16962ee68392393162ceeeb5bc7811c72b5939))
- **ocr:** Reactivar google document ai como motor primario con fallback automatico a rapidocr ([`d64fd49`](https://github.com/V44nxx/Proyecto_ocr/commit/d64fd490e30bdae0b99c9b345d4152ef838ef3a8))

### Corregido

- **personas:** Ajustar tabla al espacio disponible con table-fixed, truncamiento inteligente y diseno Apple ([`63f4015`](https://github.com/V44nxx/Proyecto_ocr/commit/63f4015f4546306033f920b2b52fe31f67c682f9))
- **ui:** Corregir contraste y color de fondo en select y option para modo oscuro ([`9ed824f`](https://github.com/V44nxx/Proyecto_ocr/commit/9ed824fcca95d481746e24369f70a578d68f8fa6))
- **auth:** Ajustar login sin menciones a paddle, sin credenciales dev y sin scroll vertical ([`0791322`](https://github.com/V44nxx/Proyecto_ocr/commit/079132209c2530432f50ca6eaa972f665f20e522))
- **ocr:** Corregir extraccion de nombres pegados, vetar ruido NUBLIC/CAPE y unificar layout de cedula ([`d50de50`](https://github.com/V44nxx/Proyecto_ocr/commit/d50de5000e5a1549de056606508f152a42e617b1))
- **ocr:** Rescatar nombres en cabecera y evitar duplicados de nombres por variaciones OCR ([`1f6eb95`](https://github.com/V44nxx/Proyecto_ocr/commit/1f6eb953597514bc52a9ea8ba69ade8719d9ba49))
- Permitir estado 'cancelado' en DB y optimizar renderizado paralelo de páginas PDF ([`f76b069`](https://github.com/V44nxx/Proyecto_ocr/commit/f76b0699ebf7c5ea093d775534e0da58af837db1))
- **ocr:** Acelerar Fast-Path DocAI, limpiar alucinaciones y desegmentar nombres pegados ([`7df50c8`](https://github.com/V44nxx/Proyecto_ocr/commit/7df50c8106f96fe9bddc873821557e469ef83e08))
- Aislar estrictamente cedula fisica de cabeceras externas y priorizar nombre de excel en discrepancias manteniendo alerta ([`32071d7`](https://github.com/V44nxx/Proyecto_ocr/commit/32071d79a4633dafc0683bbaf1c2462523ba5c40))
- **personas:** Evitar asociar previsualizacion de pdf a registros excel no encontrados y optimizar rapidocr primario con clahe ([`cfd7608`](https://github.com/V44nxx/Proyecto_ocr/commit/cfd7608e90ac5bd426da1d4db73ddea5521982f0))
- **ocr:** Resolver extraccion precisa de nombres/apellidos en cedula amarilla, eliminar distorsiones CLAHE y bloquear etiquetas corruptas tipo Apellixis ([`ceebe37`](https://github.com/V44nxx/Proyecto_ocr/commit/ceebe37b458befc1415cb4d6d610b38180ad7973))
- **ocr:** Optimizar extraccion y lectura de nombres con Google Document AI ([`821db63`](https://github.com/V44nxx/Proyecto_ocr/commit/821db6319a9fb2e2c91982441e093a2dc084698a))
- **ocr:** Mejorar extraccion de nombres, filtrado de firmas manuscritas y cotejo con excel ([`9bba5c9`](https://github.com/V44nxx/Proyecto_ocr/commit/9bba5c9f06cb40a1a0eefddd4f6171ef21394ec1))
- **ocr:** Filtrar datos externos al documento y corregir coincidencia y enriquecimiento de nombres ([`891f982`](https://github.com/V44nxx/Proyecto_ocr/commit/891f9821d3587b58b95ee8dbe80b801d11c8c865))
- **antecedentes:** Agrupar certificados multipagina evitando duplicados y registros sin titular ([`0aa89e2`](https://github.com/V44nxx/Proyecto_ocr/commit/0aa89e21cd86739e557f122751a81d7729313119))

### Documentación

- Actualizar README, agregar diagrama de flujo Draw.io, branding KondID y depuracion de archivos de prueba ([`98a70ce`](https://github.com/V44nxx/Proyecto_ocr/commit/98a70ce1111d923b45e458fda82be2563ffce98e))
- Anadir documentacion integral del sistema (ficha tecnica, especificaciones, estimacion economica, manual tecnico y usuario) ([`551a113`](https://github.com/V44nxx/Proyecto_ocr/commit/551a1136c2b9be3c572258f61de0734d45862542))

## [1.8.0] - 2026-09-29

**Resumen**

- Validación exhaustiva bidireccional entre OCR y Excel para evitar cruces de identidades.
- Selección con un clic del nombre correcto en discrepancias; la revisión sigue activa hasta aprobar.
- La exportación a XLSX agrega tipo de documento y hallazgos del cruce PDF/Excel.

### Agregado

- **personas:** Seleccion interactiva con un clic de nombre en discrepancias manteniendo revision activa hasta aprobacion ([`6f6ee87`](https://github.com/V44nxx/Proyecto_ocr/commit/6f6ee874065cc772f007f7f34e86e3897cf41496))
- **export:** Agregar columnas de tipo de documento y hallazgos de cruce PDF/Excel al exportar a XLSX ([`4941d9a`](https://github.com/V44nxx/Proyecto_ocr/commit/4941d9aa3616957fd66189d3a5edc10d1b99a173))

### Corregido

- **ocr-excel:** Validacion exhaustiva bidireccional entre OCR y Excel para evitar cruce de identidades y nombres ([`10af7aa`](https://github.com/V44nxx/Proyecto_ocr/commit/10af7aad14676e26187ad12c92497431fca5d552))
- **ui:** Mejora contraste de cédula en modo oscuro y oculta alertas al validar ([`66bf6f6`](https://github.com/V44nxx/Proyecto_ocr/commit/66bf6f69c8d9a08a76f1c5dfa324c143e11f18de))
- Sincronizar estado a VALID y limpiar discrepancias al aprobar y validar persona ([`edecc91`](https://github.com/V44nxx/Proyecto_ocr/commit/edecc91a1dc5a101e5a5f5f174a870253bb9b239))
- **ocr:** Aislar cedula fisica ignorando datos externos de fotocopia y extraer fecha de nacimiento en reverso amarillo ([`8453177`](https://github.com/V44nxx/Proyecto_ocr/commit/845317795608d774543d51a0fa50f7e32746351f))
- **ocr:** Descartar membrete de ficha CC. NUMERO NOMBRE para evitar duplicacion de personas por texto externo a la cedula ([`4106589`](https://github.com/V44nxx/Proyecto_ocr/commit/410658978296be1a8da9a2fe40f83b5d7ab3271b))

## [1.7.0] - 2026-09-23

**Resumen**

- Soporte multiformato de documentos (CC, TI, CE, PPT, CT, PAS) y Smart Dual OCR, con badges unificados en tablas, exportación y dashboard.

### Agregado

- Soporte multiformato de documentos (CC, TI, CE, PPT, CT, PAS) y Smart Dual OCR ([`d3d98a7`](https://github.com/V44nxx/Proyecto_ocr/commit/d3d98a7920023a6c2ed8cba92cce7f1cd453b49a))

### Cambiado

- **frontend:** Unificar badges de tipos de documentos (CC, TI, CE, PPT, CT, PAS) en tablas de personas, exportacion y dashboard ([`ef92d9a`](https://github.com/V44nxx/Proyecto_ocr/commit/ef92d9ab42f6fff5cac8c61d772b6ad8eb10364a))

### Corregido

- Importar `or_` de sqlalchemy a nivel de modulo en router de documentos ([`04929a3`](https://github.com/V44nxx/Proyecto_ocr/commit/04929a38f6eec966e11d37154abc0678f1ecde8b))
- Corregir error 422 al guardar edicion de persona permitiendo campos de fecha vacios ([`021ed39`](https://github.com/V44nxx/Proyecto_ocr/commit/021ed39c3f8d0a92ef4615b5441155768d988c1c))

## [1.6.0] - 2026-09-19

**Resumen**

- Aislamiento de documentos, personas y comparaciones por usuario.
- Columna Fuente PDF/Excel, alertas de personas faltantes y autocorrección del número de identificación desde el Excel.
- Modo claro y oscuro, alerta de menores de 14 años, historial de fichas en el dashboard y sidebar colapsable.
- Validación de nombres entre cédula y Excel, registro de personas del Excel que no aparecen en el PDF, cancelación de subidas y restauración de PDFs y Excel desde la BD tras un despliegue.

### Agregado

- Conteo contextual por archivo PDF y enfoque en datos esenciales (ID, nombre, fecha nacimiento, edad) ([`98a1274`](https://github.com/V44nxx/Proyecto_ocr/commit/98a1274b775a2d698cf49a37a233711a148410b7))
- **personas:** Columna Fuente PDF/Excel reemplaza Confianza - muestra origen de cada persona en tabla ([`645d4bc`](https://github.com/V44nxx/Proyecto_ocr/commit/645d4bcb0be1f76dd5aec644a56f0b7fd39755b7))
- Alertas visuales en Estado para personas faltantes en PDF o Excel ([`11ae4a3`](https://github.com/V44nxx/Proyecto_ocr/commit/11ae4a3ae8f9785385d86b93f2369f67945e19de))
- Auto-correccion automatica de numero de identificacion desde Excel cuando el OCR tiene discrepancias ([`7c67639`](https://github.com/V44nxx/Proyecto_ocr/commit/7c676393957ace37a6796ec462dff57c65469104))
- Alerta menores de 14 anos, modo claro y oscuro, historial de fichas en dashboard y conteo por archivo ([`de1ddd2`](https://github.com/V44nxx/Proyecto_ocr/commit/de1ddd20e138a53546e6c1c5dd023287530d2b1e))
- Preservar historial de fichas en dashboard y personas extraidas al quitar documentos del apartado de subida ([`cc99595`](https://github.com/V44nxx/Proyecto_ocr/commit/cc99595d440ac8ba9bae46d395a0625e750c3c67))
- Correccion de modo claro con mayor contraste, erradicacion de ruido IIII/III y validacion estricta de nombres ([`6a79b7a`](https://github.com/V44nxx/Proyecto_ocr/commit/6a79b7a25f47d9275799cfedcaa9e8dc5319a68b))
- Contraste oscuro para alertas y badges CC/TI y tabla independiente de personas en historial ([`8080816`](https://github.com/V44nxx/Proyecto_ocr/commit/8080816aa4bc360959ae825d515f013d93907f84))
- Boton para vaciar tabla de personas y seleccion multiple para eliminacion en lote ([`c9be5c9`](https://github.com/V44nxx/Proyecto_ocr/commit/c9be5c915ea95f09c3f83b9a1dd48393d4e2542f))
- Persistencia historica de personas por ficha, exportacion por estado y resaltado en rojo para menores de edad ([`1555648`](https://github.com/V44nxx/Proyecto_ocr/commit/15556484e2e0e282b4260a3dabb7a58988deb09e))
- Boton para eliminar ficha del historial con modal de confirmacion ([`d4891e2`](https://github.com/V44nxx/Proyecto_ocr/commit/d4891e211e164a531b960cd0edea734df1b71f86))
- Implementar sidebar colapsable a modo icono, eliminar scroll lateral y sincronizar márgenes de contenido ([`37578fc`](https://github.com/V44nxx/Proyecto_ocr/commit/37578fc706a775dcde776ab6275dbaf4ecb4d639))
- Validacion global de nombres Cedula vs Excel con prioridad en cedula fisica y marcado en REVISAR ([`1da3afb`](https://github.com/V44nxx/Proyecto_ocr/commit/1da3afb6a8fadb56a51e4f00f54877b4f9fbae70))
- Conservar nombre de Excel, enviar a revisar con motivo explicativo interno ante discrepancia, y eliminar badge ancho para evitar scroll ([`33341d0`](https://github.com/V44nxx/Proyecto_ocr/commit/33341d038e290a9d2ed91e7915eb30ffca22cd39))
- Eliminar ruido administrativo OCR, mejorar precision extraccion y validacion edad-documento ([`8e7a576`](https://github.com/V44nxx/Proyecto_ocr/commit/8e7a5768463d2107f006530821159565b4c7d2c4))
- Persistir progreso OCR en localStorage y banner global de proceso activo ([`44d054c`](https://github.com/V44nxx/Proyecto_ocr/commit/44d054c20554e41dad9ff4e3ade0c965e1605d26))
- Registrar personas de Excel no encontradas en PDF con alerta de revision ([`82e4711`](https://github.com/V44nxx/Proyecto_ocr/commit/82e4711381a5cb9de3239c8372fbd3574f87aa7c))
- Boton para cancelar subida y remover archivos en proceso ([`f714401`](https://github.com/V44nxx/Proyecto_ocr/commit/f7144017cc53086f0f0357eb51d70d7bd8326f4f))

### Cambiado

- Remover tabla inline en dashboard, enlazar visualizar a modulo personas y refinar contraste y elegancia en modo claro ([`227c6b1`](https://github.com/V44nxx/Proyecto_ocr/commit/227c6b1fbacc49d2bbf47c841cda763b66adcf3e))

### Corregido

- **personas:** Eliminar scroll horizontal, mostrar fecha nacimiento en tabla y detalles expandidos ([`49c9bb3`](https://github.com/V44nxx/Proyecto_ocr/commit/49c9bb3056a4e8c9b9e4530109b8d7d372a411a4))
- **personas:** Tabla con Pag+Confianza visibles, F.Nacimiento solo en detalle expandido ([`608d33e`](https://github.com/V44nxx/Proyecto_ocr/commit/608d33ee0b1fcf5cfd1524a7d6de3441c0d38ab7))
- **documentos:** Eliminar personas en cascada al borrar documento evita datos huerfanos entre usuarios ([`450aab2`](https://github.com/V44nxx/Proyecto_ocr/commit/450aab254eacaf93f217d16b32255e4889293f12))
- Extraccion confiable y exacta de cedulas del archivo Excel para Fuente y Estado ([`ec1433e`](https://github.com/V44nxx/Proyecto_ocr/commit/ec1433ed754293ee8ffa70eb6f363d1ec18bb1ff))
- **ui:** Alinear nombre con documento, nombre en una sola linea y badge No Excel horizontal ([`2ae507b`](https://github.com/V44nxx/Proyecto_ocr/commit/2ae507bb708ad2d0a7f647ae98aef58a6e259c48))
- **ui:** Eliminar scroll lateral en detalle de persona y alinear nombre a la izquierda ([`6776624`](https://github.com/V44nxx/Proyecto_ocr/commit/6776624ecc6878f677af2b65cfd40fda22d6b039))
- **ui:** Corregir perdida de foco al escribir en los inputs de edicion ([`efe6def`](https://github.com/V44nxx/Proyecto_ocr/commit/efe6def95a5d7c040073673f8abc7a25a2a6666f))
- Organizacion de botones superiores y solucion definitiva a duplicacion de alertas en tabla de personas ([`75bf902`](https://github.com/V44nxx/Proyecto_ocr/commit/75bf902a9f89477fba4a32eaa3459d420c45f8fc))
- Quitar contador de paginas del historial y mejorar animacion radial de tema claro/oscuro ([`a4fd731`](https://github.com/V44nxx/Proyecto_ocr/commit/a4fd731fa92363b561f17b087f48a54e97778243))
- Eliminar flasheo en animacion de tema inicializando clip-path en 0px y normalizando blend mode ([`6c38216`](https://github.com/V44nxx/Proyecto_ocr/commit/6c382165aa74b9c52891b1a0e29ecb2427ed39d6))
- Eliminar parpadeo final de transicion con flushSync y fill forwards en animacion radial ([`14fea6a`](https://github.com/V44nxx/Proyecto_ocr/commit/14fea6a1b40f5b0f92cc031319845ce8ff049cd7))
- Resaltar en rojo menores solo si son < 14 anos, mejorar contraste tipografico en documentos y usar iconos minimalistas en toggle de tema ([`21fe3f9`](https://github.com/V44nxx/Proyecto_ocr/commit/21fe3f93e0f266ca54a800319792cfe3fe0d19b5))
- Reemplazar emojis por iconos minimalistas en modal de ficha, centrar boton ver detalles y renombrar colapsar a subir ([`e6f6a30`](https://github.com/V44nxx/Proyecto_ocr/commit/e6f6a30d4282fe5e620ea69051a092e47f0e5d74))
- Reemplazar emoji de personas en historial, reparar estructura desplegable de ver mas detalles y suavizar colores a matices sobrios ([`33e950d`](https://github.com/V44nxx/Proyecto_ocr/commit/33e950d4e29bc9340a5a33f994b475322fb439f5))
- Corregir desbordamiento badge OK, matices edad/pdf/excel y extraccion OCR independiente de excel ([`e33cf72`](https://github.com/V44nxx/Proyecto_ocr/commit/e33cf720587781e080c1996e4fb0aec03c28d547))
- Permitir apellidos repetidos legitimos sin invalidar y validar contra cedula ([`b1dc8e1`](https://github.com/V44nxx/Proyecto_ocr/commit/b1dc8e1eb9a44d81b2c9ca8e6b437a9fba82a24d))
- **dashboard:** Dejar solo el icono de ojo en historial para evitar scroll horizontal ([`67971e4`](https://github.com/V44nxx/Proyecto_ocr/commit/67971e4d6fff08d4302f027cb1216b7d930a0078))
- **personas:** Eliminar parpadeo y cambio forzado de filtro al cargar tabla de personas ([`6369621`](https://github.com/V44nxx/Proyecto_ocr/commit/6369621841445790421af81307456ff44df2a820))
- **ocr:** Unificar en `nombre_completo`, eliminar conflictos redundantes y filtrar ruidos de cabecera como NIMEPO EDULA ([`5ff2c5b`](https://github.com/V44nxx/Proyecto_ocr/commit/5ff2c5b7a9242228b2ca9879d60f22fc9b23ba6d))
- **ocr:** Aislar reverso en nombres, corregir extraccion cedula en barcode y preservar apellidos dobles en excel ([`7313ce7`](https://github.com/V44nxx/Proyecto_ocr/commit/7313ce7121d75fd95a6886a08928ca78c689002d))
- **personas:** Preservar apellidos dobles en frontend formatNombreCompleto y asegurar adopcion de nombre oficial excel ([`afa8796`](https://github.com/V44nxx/Proyecto_ocr/commit/afa87969b72e3b1c9b412c65e59ae5bc94ea2119))
- **personas:** Ajustar métrica falta pdf/excel para no mezclar personas con discrepancia de nombre que si estan en excel ([`3566da6`](https://github.com/V44nxx/Proyecto_ocr/commit/3566da69de569678cd495724f49f2eaca39be063))
- Detectar tipo de documento desde el OCR real, no asumir cedula cuando es desconocido ([`d51dc1c`](https://github.com/V44nxx/Proyecto_ocr/commit/d51dc1c2fa3bbe0731c024d2050639640f72709c))
- Corregir encoding UTF-8 de BannerProcesoActivo.tsx para Docker build ([`d086a79`](https://github.com/V44nxx/Proyecto_ocr/commit/d086a799f78634696972189176e2ab61a11870cd))
- Filtrar ruido geografico fusionado por OCR (FLORENCIA-CAQUETA) y mejorar extraccion de ID con espacios ([`59fbef0`](https://github.com/V44nxx/Proyecto_ocr/commit/59fbef08eed0a41057c85e0b751b026d4035636b))
- **geo:** Agregar deteccion universal de municipios y departamentos fusionados por OCR en `es_geografico` ([`f7cc79e`](https://github.com/V44nxx/Proyecto_ocr/commit/f7cc79e668554d61902046306780d5784fe15b32))
- Corregir clasificacion de Tarjeta de Identidad para personas de 18 años y activar alerta de mayoria de edad ([`7c3359d`](https://github.com/V44nxx/Proyecto_ocr/commit/7c3359d54c2cb2bf77ccc11bf96b698058a75795))
- **ocr:** Regla cero descarte, limpiar letras externas de fotocopias y dejar ID en blanco para edicion ([`942c3bd`](https://github.com/V44nxx/Proyecto_ocr/commit/942c3bde64e920fca3ee0248d96192907537ce77))
- **ocr:** Forzar OCR de imagen en fotocopias con membrete, filtrar ruido administrativo y soportar variantes OCR de etiquetas ([`dde0b91`](https://github.com/V44nxx/Proyecto_ocr/commit/dde0b913111d1bc759a8fa0e3d19a57b05842903))
- **persistence:** Auto-restaurar pdfs y excels desde bd y corregir estado `en_excel` tras despliegues ([`5eb328f`](https://github.com/V44nxx/Proyecto_ocr/commit/5eb328f073be3196f8cdebe90c5eb8df5814436b))
- Resolver bloqueo en subida por esquema DB y reorganizar controles de progreso, tiempo y cancelacion ([`1096f50`](https://github.com/V44nxx/Proyecto_ocr/commit/1096f5052b4572cf1da8e0c4a8d1d2c2de686b9d))
- Mantener persona en lote padre y vista previa activa al subir PDF individual ([`6d9cdb7`](https://github.com/V44nxx/Proyecto_ocr/commit/6d9cdb7607ee92baa27923dd76291161f7ec4ffa))

### Seguridad

- **security:** Aislamiento por BD de documentos, personas y comparaciones por `usuario_id` ([`498c838`](https://github.com/V44nxx/Proyecto_ocr/commit/498c838c613acaabe65947c906c29189b76691fe))
- Aislamiento total de documentos y personas por usuario y eliminacion segura ([`4475da6`](https://github.com/V44nxx/Proyecto_ocr/commit/4475da6e925c60dafd3a75de6a239ce8879cee20))
- **multi-tenant:** Aislamiento estricto de documentos, personas y estadisticas por usuario ([`5913563`](https://github.com/V44nxx/Proyecto_ocr/commit/59135636ac72cf010ea2e1dd5dd2e85321b6c3c6))

## [1.5.0] - 2026-09-11

**Resumen**

- Subida combinada de PDF + Excel con comparación automática.
- ⚠️ **Cambio incompatible:** el Excel pasa a ser obligatorio en `POST /api/documentos/upload` (vuelve a ser opcional en 2.1.0).
- Campo único `nombre_completo`, migraciones automáticas al arrancar y manejador global de excepciones.
- Exportación por documento PDF y selección múltiple, cálculo de edad y panel de administración de usuarios.

### Agregado

- Subida combinada PDF+Excel con comparacion automatica ([`54be0aa`](https://github.com/V44nxx/Proyecto_ocr/commit/54be0aadf5cbedf8ec6381cae797fa8054fefe3c))
- **exportacion:** Permitir exportar personas por documento PDF y seleccion multiple ([`2ff69ab`](https://github.com/V44nxx/Proyecto_ocr/commit/2ff69ab1813eebda2efa9b1a430ae281c698619d))
- **personas, exportacion:** Calcular y mostrar edad basada en fecha de nacimiento ([`f654ce3`](https://github.com/V44nxx/Proyecto_ocr/commit/f654ce33056e48cf176a509fedeb47290a2cacc6))
- Carga y auditoria automatica de planilla Excel en Comparacion al iniciar OCR ([`19d1778`](https://github.com/V44nxx/Proyecto_ocr/commit/19d1778f24f9b00593e9b51ac1eaa61b70463205))
- Auto-scroll hacia tarjeta de progreso al presionar Iniciar OCR en Documentos ([`0069cf2`](https://github.com/V44nxx/Proyecto_ocr/commit/0069cf24b102262b9ff1c38a23560174749860de))
- Redirigir a tabla de personas al finalizar procesamiento OCR ([`b1c0fa7`](https://github.com/V44nxx/Proyecto_ocr/commit/b1c0fa737fc4f6218419974f60d7cc52c7fde480))
- **admin:** Agregar panel y modal de creacion y gestion de usuarios para administradores ([`f15cd21`](https://github.com/V44nxx/Proyecto_ocr/commit/f15cd21f4583c9a998f6ea9ae17331ba36cc4e6f))

### Cambiado

- Excel obligatorio para OCR — nombres/apellidos desde planilla oficial ([`e96d85e`](https://github.com/V44nxx/Proyecto_ocr/commit/e96d85e91174b56bcb75665f97fe7e89a134b3d3))
- Unificar campo `nombre_completo` y acelerar pipeline OCR con concurrencia y optimizaciones ([`7a05c7c`](https://github.com/V44nxx/Proyecto_ocr/commit/7a05c7c0005590437dfee4eb11c832e9351a7916))
- **personas:** Rediseño de edicion integrada con visor de documento y tarjetas compactas ([`68479f2`](https://github.com/V44nxx/Proyecto_ocr/commit/68479f2a24d91ba6e8e4e6741a4d7a360d9417f7))
- **ocr:** Unificar evaluacion a `nombre_completo`, priorizar extraccion desde Excel oficial y eliminar alertas falsas de apellidos ([`1a3ca5e`](https://github.com/V44nxx/Proyecto_ocr/commit/1a3ca5e661b01d6b3d7248bf0fe0e128a47c0a0a))

### Corregido

- **db:** Ejecutar migraciones de esquema automáticas en startup y agregar global exception handler con CORS ([`8948efd`](https://github.com/V44nxx/Proyecto_ocr/commit/8948efdcfc117d4246ccf46a348e7ab45e4e3c5d))
- Saneamiento y deduplicacion robusta de nombres y apellidos eliminando repeticiones y ruido institucional ([`95fd8f0`](https://github.com/V44nxx/Proyecto_ocr/commit/95fd8f086d867e0b9462fb53862e21c114544f28))
- **ocr:** Corregir evaluacion de `requiere_revision` para no penalizar registros validos ni ausencias en excel complementario ([`eb59235`](https://github.com/V44nxx/Proyecto_ocr/commit/eb59235f04aa0184f7ded37b93d96fc68814e471))
- **ocr:** Correccion filtro solo revision, validacion estricta de completitud y extraccion de sexo en contrasenas ([`82956f2`](https://github.com/V44nxx/Proyecto_ocr/commit/82956f2934f0c18a6416b616a8c483a4bba2f54e))
- **ocr:** Resolver extraccion de homoglifos griegos, suprimir ruido de firmas DR CDI y actualizar registro ([`6f0de04`](https://github.com/V44nxx/Proyecto_ocr/commit/6f0de04898a6c6f2b7447604b9fd920cc0707d1e))
- **ocr:** Extraer lugar de expedicion basado en la misma linea de la fecha de expedicion ([`1a5c0f7`](https://github.com/V44nxx/Proyecto_ocr/commit/1a5c0f7d7aea211bf8986b8845eeece72557ad60))
- **comparacion:** Remover sufijo de estado en nombres y reconciliar personas por nombre ante diferencias de id ([`e0cc194`](https://github.com/V44nxx/Proyecto_ocr/commit/e0cc194e8fe5853a6f00d1bca69d2cf374ef4429))
- **ui:** Mover documento PDF al panel de detalle de la persona y quitar columna de la tabla para evitar scroll horizontal ([`fce74ee`](https://github.com/V44nxx/Proyecto_ocr/commit/fce74ee6b1018a6ff996a48470a2aa609ed44731))
- **ocr, comparacion, personas:** Retener nombre OCR ante Excel sin nombre, agregar persona faltante a BD y subir PDF cedula ([`32068d9`](https://github.com/V44nxx/Proyecto_ocr/commit/32068d9453619769edcf2499ac9b58f06f01fa71))
- Quitar botones PDF/aprobar de tabla, arreglar visibilidad PDFs entre usuarios y mejorar panel detalles ([`c0440ef`](https://github.com/V44nxx/Proyecto_ocr/commit/c0440ef30b7933e9d5b31ecf2a03a1f530dd8f0f))
- Corregir error `tipo_documento` en subir-pdf y dejar solo boton eliminar en tabla personas ([`02ec000`](https://github.com/V44nxx/Proyecto_ocr/commit/02ec000e6c2fe64dded4a27f05408ffe72ded021))
- Corregir 'list object has no attribute get' al unificar `detalles_campos` en subir-pdf ([`666e54d`](https://github.com/V44nxx/Proyecto_ocr/commit/666e54db357b8e8ed95e83eedecf08931a99817f))

### Seguridad

- **auth:** Ocultar credenciales por defecto en login y registrar usuario admin Emerson ([`43a373e`](https://github.com/V44nxx/Proyecto_ocr/commit/43a373e56b4c0facd3d481defcd1ec6d7cb66d5e))

## [1.4.0] - 2026-09-03

**Resumen**

- Emparejamiento global bipartito (algoritmo húngaro + RapidFuzz) para contar con exactitud las personas.
- Reporte de comparación multihoja con OpenPyXL y corrección directa de campos en la BD.
- Progreso de subida en MB y porcentaje.

### Agregado

- Emparejamiento global bipartito (Algoritmo Hungaro + RapidFuzz) y guardia cero huerfanos para conteo exacto de personas ([`38f93cf`](https://github.com/V44nxx/Proyecto_ocr/commit/38f93cf5f7a326aa5beb934135fc96f18f26165e))
- Mostrar progreso dinámico en tiempo real (MB y porcentaje) durante la subida del PDF para evitar sensación de congelamiento ([`67b1469`](https://github.com/V44nxx/Proyecto_ocr/commit/67b1469dbb30564b2a69924ba1d0a8a4670df4b3))
- **comparacion:** Reporte profesional multi-hoja con OpenPyXL y correccion directa de campos en BD ([`4983db4`](https://github.com/V44nxx/Proyecto_ocr/commit/4983db4ea0f7554138ffc34baa08fa68a58d2d21))

### Corregido

- Mejoras globales OCR para reducir datos vacios en tabla de personas ([`96660c5`](https://github.com/V44nxx/Proyecto_ocr/commit/96660c5f94b57a87bfc056e7cb1af12086a6cc6f))
- Eliminar duplicados en tabla de personas (24 -> 19 personas) ([`17fba7a`](https://github.com/V44nxx/Proyecto_ocr/commit/17fba7ac623bf4d063d45f2d1dc6c518b21d3601))
- Resolver bloqueo de subida de PDF apuntando directamente al backend HTTPS https://api.v44nxx.online con soporte CORS y bcrypt directo ([`27e7cef`](https://github.com/V44nxx/Proyecto_ocr/commit/27e7cefd4bc02c2c2f8da647353b7944e6a5ee4e))
- **ocr:** Solucionar emparejamiento de reversos colombianos, extraccion limpia de nombres y desegmentacion de MRZ ([`eb1b81f`](https://github.com/V44nxx/Proyecto_ocr/commit/eb1b81fc8f70dfc951fb734549c6f218924a60c0))
- **ocr:** Resolver nombres en cedula amarilla bloqueando artefactos de holograma y delimitando columna izquierda ([`45ce787`](https://github.com/V44nxx/Proyecto_ocr/commit/45ce7874d96d56b1e2617368090ba3376dbdb235))
- **ocr:** Veto exacto de tokens holograficos aislados y remocion de particulas huerfanas iniciales ([`95cf8fc`](https://github.com/V44nxx/Proyecto_ocr/commit/95cf8fcf35e8cc78eda863fea88b5e7c78d7b667))
- **ocr:** Restaurar apellidos legitimos (Rengifo, Torres, Sanchez) y evitar falso lugar de expedicion en cedula digital ([`688696d`](https://github.com/V44nxx/Proyecto_ocr/commit/688696d1e8f184db344afd7d5cddc52fa83ccecc))
- **comparacion:** Limpieza visual de datos en tabla y hojas dedicadas en Excel para oficial y base de datos ([`7ff94b7`](https://github.com/V44nxx/Proyecto_ocr/commit/7ff94b753384ea48e150eb2de79472d533eb6b45))
- **schemas:** Expose `ruta_archivo` and `nombre_archivo` in ComparacionResponse ([`03c68dd`](https://github.com/V44nxx/Proyecto_ocr/commit/03c68ddb648c8e0e12b8a21ac0009e665115c0a0))
- **comparacion:** Reconstruccion de `excel_map` desde base de datos cuando el archivo fisico no existe ([`8c43733`](https://github.com/V44nxx/Proyecto_ocr/commit/8c437333d7c3a3120db43638ac0ddd022ee0c6b0))

### Mantenimiento

- Add diagnostic inspection for comparison file on production ([`fe25200`](https://github.com/V44nxx/Proyecto_ocr/commit/fe25200bd3699a8ebd56653960e354dcbc44239a))
- Remove diagnostic fields now that excel reconstruction is verified ([`4ea5c31`](https://github.com/V44nxx/Proyecto_ocr/commit/4ea5c314cfe8446fdc84375bb6accac737551775))

## [1.3.0] - 2026-08-28

**Resumen**

- Vista previa del PDF junto a los datos OCR en la tabla de personas.
- Progreso en vivo del OCR y de la subida, con tiempo estimado.
- RapidOCR (ONNX Runtime) como motor local y modo dual Document AI + RapidOCR.
- Detección de Tarjeta de Identidad frente a Cédula, cédula amarilla anterior al 2000 y planillas SENA multihoja en Comparación.
- Las subidas pasan por rewrites nativos de Next.js en lugar del route handler.

### Agregado

- Vista previa PDF + datos OCR lado a lado en tabla de personas ([`e91d82a`](https://github.com/V44nxx/Proyecto_ocr/commit/e91d82a42ffe88b5c0fa0d121c8367a466444b75))
- Tabla personas con acordeon inline y doble barra de busqueda ([`2a0019f`](https://github.com/V44nxx/Proyecto_ocr/commit/2a0019fd6484d5609850d2c2f08befe1ab0674c4))
- Agregar barra de progreso OCR en vivo y redisenar boton de procesamiento ([`8e9f6fa`](https://github.com/V44nxx/Proyecto_ocr/commit/8e9f6fafc0c149b54aac4fc085f864da64f21421))
- Mostrar progreso de subida de archivo y calculo de tiempo estimado ([`3342f29`](https://github.com/V44nxx/Proyecto_ocr/commit/3342f29ac7760375815afd36f3628bf8f8554b85))
- Mostrar tiempo total de extraccion y redireccion automatica a personas ([`0760952`](https://github.com/V44nxx/Proyecto_ocr/commit/07609520f22475502a00319be32dd19449816d59))
- Unificar cedulas en multiples hojas por numero de identidad sin generar duplicados ([`86c5f70`](https://github.com/V44nxx/Proyecto_ocr/commit/86c5f701a72513be4a1f6a415181cf627f4a1318))
- Integrar RapidOCR ONNX Runtime como motor neural local para VPS y contingencia ([`005bc0e`](https://github.com/V44nxx/Proyecto_ocr/commit/005bc0eb436c4b96a89391f0faed030658a357e8))
- Agregar tarjetas de estadisticas y conteo total de personas en tabla ([`0677bc7`](https://github.com/V44nxx/Proyecto_ocr/commit/0677bc70b8092e91d734ea935bddba6554a3e016))
- Soporte nativo para cedula amarilla colombiana (pre-2000) - extraccion de nombres sin etiquetas APELLIDOS/NOMBRES ([`78ea4ca`](https://github.com/V44nxx/Proyecto_ocr/commit/78ea4ca8ba9f57d31d9bf0c20eb748eb18bd42a9))
- Modo dual OCR - Google Document AI + RapidOCR corren simultaneamente y fusionan texto por campo para maxima cobertura ([`03044e4`](https://github.com/V44nxx/Proyecto_ocr/commit/03044e4239045cd71509af597e118a0d9fb28b0e))
- Soporte nativo para planillas SENA en comparacion - lectura multi-hoja (Inscritos Primera/Segunda Opcion), extraccion de CC-[número omitido] y matching inteligente de columna Nombre completa ([`4803985`](https://github.com/V44nxx/Proyecto_ocr/commit/48039855fc1383d1957fead216539a6b4d25e24f))
- Deteccion automatica y clasificacion de Tarjeta de Identidad (TI) vs Cedula de Ciudadania (CC) con badges visuales en la tabla y panel de detalles ([`067d0bc`](https://github.com/V44nxx/Proyecto_ocr/commit/067d0bceaa2eb4cdd7112b10375bc6cb554b920e))

### Cambiado

- Restaurar procesamiento secuencial simple y configuracion anterior estable (pre-semaforo) ([`7b2b72c`](https://github.com/V44nxx/Proyecto_ocr/commit/7b2b72c66ae4919c92cbc865aef1e983c2d63ba5))

### Rendimiento

- Paralelismo controlado de paginas (3 workers) y concurrencia dual DocAI + RapidOCR para acelerar procesamiento 3x ([`43d75e5`](https://github.com/V44nxx/Proyecto_ocr/commit/43d75e5066a03ea1276ebfc09a87eb1a15486f5d))
- Auto-escalado en RapidOCR y renderizado a 200 DPI para acelerar inferencia y eliminar congelamiento de progreso ([`abc6e2d`](https://github.com/V44nxx/Proyecto_ocr/commit/abc6e2df120408cbd81b2c6d6a708297dd0cb3e7))

### Corregido

- Endpoint preview PDF usa Request para aceptar token por query param ([`44f8a10`](https://github.com/V44nxx/Proyecto_ocr/commit/44f8a100c4a60da4079f749a9e269aaaab4052a6))
- Apuntar getBaseUrl directamente a https://api.v44nxx.online en produccion para carga directa de PDF y endpoints ([`9d2d43a`](https://github.com/V44nxx/Proyecto_ocr/commit/9d2d43a6aaebf2ee4d60445adc134d74a1863ecb))
- Quitar filtro secundario con # y mantener buscador unico en tabla personas ([`831724d`](https://github.com/V44nxx/Proyecto_ocr/commit/831724d9d851f87fa5239a1b03b7624bf1003359))
- Agregar dependencia faltante rapidfuzz en requirements.txt ([`f19395a`](https://github.com/V44nxx/Proyecto_ocr/commit/f19395ac4b35fb99dc35592201470077cc8c8b7b))
- Corregir extraccion de nombres del reverso de cedula (municipios, departamentos y patrones de reverso filtrados) ([`439468e`](https://github.com/V44nxx/Proyecto_ocr/commit/439468e27dfed6b088851097bcca0e23dfd904f5))
- Anti-duplicados en agrupacion de cedulas - frente+reverso consecutivos siempre se unen, reversos huerfanos sin ID descartados en PDF multipagina ([`7c1f46b`](https://github.com/V44nxx/Proyecto_ocr/commit/7c1f46b738767695d0d3622f40a46f8e74e29bfb))
- Extraccion de nombres y apellidos robusta con fallbacks por contexto/keywords y scan libre para evitar registros sin revisar ([`feb257e`](https://github.com/V44nxx/Proyecto_ocr/commit/feb257ed960d5cdf925d0f25ae80cbac7486ca99))
- Deteccion inteligente de encabezados en Excel, mapeo universal de columnas y normalizacion de identificaciones y fechas para modulo de comparacion ([`58f5e4a`](https://github.com/V44nxx/Proyecto_ocr/commit/58f5e4a98bd0baaff035b4156cae55a2ec4fbd1c))
- Agrupacion de cedulas de 2 paginas infalible - unificacion de frentes y reversos consecutivos (elimina duplicados 34->31 personas) ([`0048614`](https://github.com/V44nxx/Proyecto_ocr/commit/00486145e7cd730addf98c5a954f0a2d588f3e26))
- Robustecer manejo de errores de red (Network Error / Timeout), elevar timeout de subida a 5 minutos y asegurar boundary automatico en FormData ([`2220b85`](https://github.com/V44nxx/Proyecto_ocr/commit/2220b8590ddf4d90b253ccd2e5341a0fface9fcf))
- Solucionar error de red en subida conectando directo por el proxy interno de Next.js (elimina dependencia de subdominio externo y problemas de DNS/CORS) ([`0eaa78f`](https://github.com/V44nxx/Proyecto_ocr/commit/0eaa78f09d8fafa47d79ee455b65212bda28f896))
- Autodeteccion paralela en proxy Next.js (50ms) para conectar inmediatamente al backend de Dokploy y evitar bloqueos en subidas ([`8880085`](https://github.com/V44nxx/Proyecto_ocr/commit/8880085d0c19b9189d501c029a278bf160334ccf))
- Solucionar bloqueo de subida de PDFs reemplazando route handler en memoria por rewrites nativos con streaming TCP directo a FastAPI ([`5ebd9be`](https://github.com/V44nxx/Proyecto_ocr/commit/5ebd9be71a97eb0a2ce5f745c587bcbb1fb55478))
- Evitar que apellidos/nombres homonimos de municipios se marquen 'POR REVISAR' y corregir resolucion de conflicto en `extraer_grupo` ([`a6b3105`](https://github.com/V44nxx/Proyecto_ocr/commit/a6b3105fb0739d3036e699806274f239bbba47ce))

## [1.2.0] - 2026-08-18

**Resumen**

- Conexión frontend–backend en producción (Dokploy): proxy de Next.js con varios candidatos de backend y soporte HTTPS.
- `ColombiaGeoService` con los municipios del DANE; el lugar de expedición prioriza el municipio sobre el departamento.
- Login más robusto (bcrypt/passlib) y endpoint de diagnóstico `/api/auth/health`.
- Frontend: páginas de error (`error.tsx`, `global-error.tsx`) y lectura segura de errores 422.

### Agregado

- Implementar proxy dinamico en tiempo de ejecucion via Next.js Route Handler /api/[...path] apuntando al servicio Docker ocr-proyecto-fastapi-d5qhym:8000 ([`4c714cc`](https://github.com/V44nxx/Proyecto_ocr/commit/4c714ccb7787bf0ca497418efa991400d1d6ebe6))
- Agregar soporte HTTPS nativo y https://api.v44nxx.online como candidato prioritario en el proxy Next.js ([`608044e`](https://github.com/V44nxx/Proyecto_ocr/commit/608044ec4176e68bd0afa09022093a29a4870de3))
- Priorizar la extraccion de la ciudad/municipio de expedicion (ej: Florencia, Cali) sobre departamentos genericos (Caqueta, Valle) ([`b6f47d9`](https://github.com/V44nxx/Proyecto_ocr/commit/b6f47d97b9d4158f41515357e486fa46d7c00e0f))
- Implementar ColombiaGeoService universal con los 1.100+ municipios DANE y desambiguacion nacional Municipio vs Departamento ([`041dfe3`](https://github.com/V44nxx/Proyecto_ocr/commit/041dfe325315b95456a62f93af6af7b532afb96c))
- **frontend:** Add error.tsx and global-error.tsx boundaries to catch and recover from client exceptions ([`3bb03ee`](https://github.com/V44nxx/Proyecto_ocr/commit/3bb03eef835398c6fd4bc54a949e088c8cb1cfa3))

### Rendimiento

- **proxy:** Add in-memory backend caching and fast discovery (3s) to eliminate hanging/loading skeletons ([`4c1d232`](https://github.com/V44nxx/Proyecto_ocr/commit/4c1d232cce622451b4a44f9fc1d84fdd30bccc58))

### Corregido

- Reconstruir auth.py con `router/oauth2_scheme/logger` faltantes y limpiar api.ts para proxy HTTPS correcto ([`d5a49f5`](https://github.com/V44nxx/Proyecto_ocr/commit/d5a49f58a9fcbd9d1664a59505c2fcbe364aa434))
- Simplificar arquitectura de conexion frontend-backend con proxy relativo Next.js y `INTERNAL_BACKEND_URL` claro ([`8975464`](https://github.com/V44nxx/Proyecto_ocr/commit/8975464b359dbaaa4ceb4afa81782af0b9cd526e))
- Eliminar passlib, usar bcrypt directo para resolver AttributeError `__about__` e incompatibilidad bcrypt 4.x ([`f518a63`](https://github.com/V44nxx/Proyecto_ocr/commit/f518a63fbd2777dff3167dede1d20f6405303503))
- Corregir headers en proxy route.ts para subidas multipart y agregar auto-actualizacion en tiempo real en la tabla de personas ([`d67028a`](https://github.com/V44nxx/Proyecto_ocr/commit/d67028ab9c445373bfca32b075102a3355f06efa))
- Corregir respuesta HTTP 204 No Content en proxy Next.js y permitir eliminacion de documentos con privilegios de administrador ([`4067ea0`](https://github.com/V44nxx/Proyecto_ocr/commit/4067ea08af8bcbd5dd5399c6890e00e0c225b310))
- Configurar DNS ipv4first en Node.js y multiples candidatos de conexion en proxy route.ts para Docker Swarm ([`e2fce55`](https://github.com/V44nxx/Proyecto_ocr/commit/e2fce55cd74abc3a9cef4f5a1c1dd28020bbf179))
- Reemplazar fetch por http.request nativo con dns.lookup family:4 forzado para resolver servicios de Docker Swarm en Alpine ([`86fdec0`](https://github.com/V44nxx/Proyecto_ocr/commit/86fdec06fa3a5398fff8d82b27a337167eb1d9f6))
- Agregar http://187.77.62.85:8000 como candidato prioritario verificado en proxy route.ts ([`e6ebc69`](https://github.com/V44nxx/Proyecto_ocr/commit/e6ebc69aeb7fd5ea62b17f3c16be08baded60f9d))
- Eliminar custom lookup callback mismatch y ajustar timeout a 15s en route.ts para respuesta instantanea en login ([`9764a98`](https://github.com/V44nxx/Proyecto_ocr/commit/9764a98a9b0e95d187ba7b7a2356d351999a5792))
- Forzar accept-encoding identity en proxy route.ts para evitar que FastAPI envie gzip comprimido y el navegador lo reciba como texto plano binario ([`2f57af8`](https://github.com/V44nxx/Proyecto_ocr/commit/2f57af85ea8dec98a5bb11c4c0463769c74e185e))
- Robustecer sincronizacion y filtros de la tabla de personas con toast de confirmacion ([`ffea0bf`](https://github.com/V44nxx/Proyecto_ocr/commit/ffea0bfeda507732f0688eeb76f363ae2143aeec))
- Corregir validacion cronologica de fechas (nacimiento/expedicion) y excluir firmas de registradores y ruido en lugar de expedicion ([`9b29807`](https://github.com/V44nxx/Proyecto_ocr/commit/9b298078e4dbae4c9adb500255407ff0095e026d))
- Excluir variaciones de OCR de del Estado Civil (Aldel Givil, Estadol Civil) del campo lugar de expedicion ([`ec52386`](https://github.com/V44nxx/Proyecto_ocr/commit/ec523861a69ebbbedbbab1a3640fa9f838e93d33))
- Depurar `normalizar_lugar` para remover prefijos MA DE NACIMIENTO, fechas y meses, garantizando la extraccion exacta del municipio ([`cc0e503`](https://github.com/V44nxx/Proyecto_ocr/commit/cc0e503f9649a09f25f2a8da666959b3700fb461))
- Corregir extraccion de nombres/apellidos en cedulas amarillas y digitales, extraccion exacta de `fecha_expedicion` y lugar para los 9 casos del documento ([`ef23311`](https://github.com/V44nxx/Proyecto_ocr/commit/ef23311bfccc0cc4a57d2d469518e5c476076c46))
- Blindar extractor espacial con validacion geografica DANE estricta, resolver nombres de cédula amarilla y aliases canonicos de municipios ([`0115688`](https://github.com/V44nxx/Proyecto_ocr/commit/01156887ed920d71960386a61b7703e2e210f5e3))
- Asegurar extraccion 100% completa en `extraer_grupo` con combinacion robusta de caras y rescate posicional ([`8055bbb`](https://github.com/V44nxx/Proyecto_ocr/commit/8055bbbf8f6f7957ae96f71f4fcf996350a2e769))
- Corregir region 2d para nombres/apellidos en cedula amarilla, vincular FECHA Y LUGAR DE EXPEDICION a `lugar_expedicion` y eliminar dependencias circulares ([`9ab8353`](https://github.com/V44nxx/Proyecto_ocr/commit/9ab8353f9414bc0021ae8e9e7d03291515d63826))
- **ocr:** Universal colombian ID extraction with structural line parsing, chronological dates and canonical DANE geocoding ([`07db165`](https://github.com/V44nxx/Proyecto_ocr/commit/07db16598499f0c441037d03a7d402d6ab8f3b27))
- **ocr:** Robust global extraction — fix names zone, 2-page cedula pairing, back-only group, classifier threshold ([`a7a25df`](https://github.com/V44nxx/Proyecto_ocr/commit/a7a25dfd6409d8a1813ed0f0f932d23c824072d2))
- **frontend:** Fix PDF dropzone — remove restrictive MIME accept, validate by extension in onDrop, add onDropRejected feedback ([`9fb132b`](https://github.com/V44nxx/Proyecto_ocr/commit/9fb132bc79d4466c5e07ef895bc5f56565603319))
- **frontend:** Add Next.js rewrites for `/api/*` proxy to backend + fix multipart Content-Type ([`f0a34fe`](https://github.com/V44nxx/Proyecto_ocr/commit/f0a34fe4f679115e3248c7286bb26ea21101ecf3))
- **frontend:** Revert rewrites — proxy already handled by app/api/[...path]/route.ts ([`ebfa7a7`](https://github.com/V44nxx/Proyecto_ocr/commit/ebfa7a75ea74d70ad9541975b3e44c48bc83b826))
- **auth:** Robust bcrypt verification + add /api/auth/health endpoint for diagnostics ([`1ccf4cf`](https://github.com/V44nxx/Proyecto_ocr/commit/1ccf4cfb7bfbae8d04a613d37c83cccf65bf4f1f))
- **auth:** Definitive login fix — use passlib as primary bcrypt engine with direct bcrypt fallback, consistent hash/verify across auth+database ([`b2083b8`](https://github.com/V44nxx/Proyecto_ocr/commit/b2083b8e93be45051c10a59f03830f9a4760d590))
- **proxy:** Expand backend candidates with Dokploy name variants + `BACKEND_URL` env support ([`81fa5d8`](https://github.com/V44nxx/Proyecto_ocr/commit/81fa5d8f79e944b1c53f46f67622cd3df9251321))
- **proxy:** Reduce candidate timeout to 5s, improve error diagnostics with debug info ([`288fd26`](https://github.com/V44nxx/Proyecto_ocr/commit/288fd2651488a47f631330837eaef5496a6fdd72))
- **proxy:** Add FastAPI/lowercase service name variants for Dokploy Docker DNS ([`8eda95f`](https://github.com/V44nxx/Proyecto_ocr/commit/8eda95f216116f13136f679f0c7a6719303c1e63))
- **proxy:** Add host.docker.internal and Docker gateway 172.17.0.1 as additional backend fallbacks ([`fa6297f`](https://github.com/V44nxx/Proyecto_ocr/commit/fa6297f8444f3df77fda47094187e97ec96b61db))
- **proxy:** Add FastAPI actual IPs (10.0.1.189, 172.16.1.20) as direct fallback candidates ([`6c94425`](https://github.com/V44nxx/Proyecto_ocr/commit/6c94425064e071f3fea23c1bd036703c6e7b87f1))
- **frontend:** Make documentos page resilient to invalid dates, non-array responses and safe dropzone types ([`af27a5b`](https://github.com/V44nxx/Proyecto_ocr/commit/af27a5bf803aca4b6d3ef5fdf460e98af262641a))
- **frontend:** Add getErrorMessage helper to parse Pydantic 422 error objects safely and prevent React Error #31 + adjust proxy upload timeout to 120s ([`ba7592f`](https://github.com/V44nxx/Proyecto_ocr/commit/ba7592fa75bc97b1b9533697f8c1f79ad18addb8))
- **upload:** Make upload endpoint accept both files and file parameters with dual FormData compatibility and normalized headers ([`ba07053`](https://github.com/V44nxx/Proyecto_ocr/commit/ba07053c3ed73bf35e9ed078643b23f9c6c1c9d9))
- **backend:** Add missing Optional import in documentos.py to resolve uvicorn startup crash ([`ba1345f`](https://github.com/V44nxx/Proyecto_ocr/commit/ba1345fe3078e40265b0e9c830eb7d429e9571d0))
- **upload:** Allow all PDF naming/MIME variants smoothly and deduplicate dropped files ([`65365c4`](https://github.com/V44nxx/Proyecto_ocr/commit/65365c40d344b7a5a34bfc8d3b5930cccb36e5b2))
- **upload:** Strip static Content-Type header on FormData so browser attaches multipart boundary correctly ([`b0a8dc0`](https://github.com/V44nxx/Proyecto_ocr/commit/b0a8dc067e962ab91dc3fbdf634c70e71999ec95))
- **pairing:** Accurate sequential page grouping for 2-page IDs and eliminate phantom persona creation ([`82d63a6`](https://github.com/V44nxx/Proyecto_ocr/commit/82d63a653279d01cecbeb2114f2daafcba3e9f07))
- **extractor:** Expand background watermark noise filters in apellidos/nombres ([`6b3dccc`](https://github.com/V44nxx/Proyecto_ocr/commit/6b3dccc3f967f0139fafc5e83629663b567ce974))
- **spatial:** Eliminate watermark noise in apellidos by filtering headers and limiting candidate window ([`85a98fb`](https://github.com/V44nxx/Proyecto_ocr/commit/85a98fbeb9588455f235e38c29be809e44fa5e64))

### Mantenimiento

- Confirmar configuracion de proxy Next.js con `INTERNAL_BACKEND_URL` para Docker Swarm ([`bb5d5a6`](https://github.com/V44nxx/Proyecto_ocr/commit/bb5d5a6585899c6b5bb562b188e521826a62e906))
- Add debugging and test utility scripts ([`4365b12`](https://github.com/V44nxx/Proyecto_ocr/commit/4365b128def70d28c664f5ce7c906db4c1ea194a))
- **proxy:** Output exact error per candidate in 502 response for instant network diagnosis ([`2165a0e`](https://github.com/V44nxx/Proyecto_ocr/commit/2165a0eff70fe2cef4e98adb3d50c770a4ee5ea9))
- Clean git untracked files, update gitignore, and add `analyze_pdf` tool ([`313b069`](https://github.com/V44nxx/Proyecto_ocr/commit/313b069e91c9da567086402e3dd64c6499078e2f))

## [1.1.0] - 2026-08-16

**Resumen**

- Google Document AI como motor OCR principal, con Tesseract de respaldo.
- Reingeniería del pipeline de extracción: layout espacial de Document AI, `SpatialFieldExtractor`, `DocumentDetector`, `DocumentRegionDetector`, clasificación de caras y agrupación de páginas de un mismo documento.
- Soporte de cédula amarilla y cédula digital en la extracción espacial.
- Preparación del despliegue: Dockerfile multietapa, credenciales de Google por variable de entorno, creación automática de tablas y del admin inicial, y proxy `/api` en Next.js.

### Agregado

- Integrar Google Document AI como OCR principal con fallback Tesseract ([`230084c`](https://github.com/V44nxx/Proyecto_ocr/commit/230084c56c2dc033093a48e5b3a9354c4582fe2d))
- Optimización integral del extractor de cédulas (MRZ COL, lista negra de marcas de agua, municipios prioritarios y omisión de páginas vacías) ([`59ec744`](https://github.com/V44nxx/Proyecto_ocr/commit/59ec74482bfc0563c73be0c0897bb4f17a54d1b2))
- Solución definitiva para extracción de cédulas (parseo DD-MMM-YYYY, agrupación cronológica de fechas, desegmentación OCR y clasificación unificada de nombres) ([`52d3429`](https://github.com/V44nxx/Proyecto_ocr/commit/52d3429a324e737599ec8acffebda5fdfe0a7e67))
- Reingeniería del pipeline OCR con layout de Document AI, validación por campo, trazabilidad por página y exportación de errores ([`82d775d`](https://github.com/V44nxx/Proyecto_ocr/commit/82d775d4f733a6114f863b7d03c5297730f2ef47))
- Integración de layout espacial de Document AI, validación por campo, trazabilidad por página, insignias de estado y exportación de errores ([`1746ff8`](https://github.com/V44nxx/Proyecto_ocr/commit/1746ff8fb40d09cde81eada959f9e0873fb254c9))
- Integración del NameDictionaryService con scoring evidencial ponderado, n-gramas compuestos y explicabilidad en frontend ([`6c20f1f`](https://github.com/V44nxx/Proyecto_ocr/commit/6c20f1fdf4390157294dee7a48eaee9708f8820a))
- Reingeniería final del sistema OCR con SpatialFieldExtractor, Veto Espacial, independización del diccionario y prueba controlada de 3 cédulas ([`56a79e7`](https://github.com/V44nxx/Proyecto_ocr/commit/56a79e74b43b5a000273dc55be2ee5485ef8f0f3))
- Reingeniería definitiva del pipeline OCR con DocumentDetector, DocumentRegionDetector, recorte de perspectiva, cero invención y test suite de 20 escenarios ([`eeb2727`](https://github.com/V44nxx/Proyecto_ocr/commit/eeb272751ea80cec9452075d8df9c4a040b1b3b1))
- Clasificación de caras (DocumentSideClassifier) y agrupación evidencial de documentos de múltiples páginas (DocumentPairingService) ([`b1df671`](https://github.com/V44nxx/Proyecto_ocr/commit/b1df671afdd072818564a415297470471ed97204))
- Reingeniería crítica de extracción espacial determinista de nombres y apellidos (0% diccionario, veto espacial estricto, debug visual) ([`62009c4`](https://github.com/V44nxx/Proyecto_ocr/commit/62009c4704d5efbcdf8ab078c68d0b4db45ef976))
- Extracción espacial 2D completa con regiones dinámicas X/Y, clasificación de layout, exclusión mutua de tokens y depuración visual ([`d0ceeaa`](https://github.com/V44nxx/Proyecto_ocr/commit/d0ceeaa9becb6bcb8bdcd11535a0e226b0096eff))
- Soporte para credenciales Google Document AI via env var `GOOGLE_CREDENTIALS_JSON` o `GOOGLE_CREDENTIALS_BASE64` en produccion ([`f701194`](https://github.com/V44nxx/Proyecto_ocr/commit/f701194b7e9b863de9b5732f7c45f32a2f423092))
- Soporte mejorado para Docker Secrets y resolucion dinamica de credenciales Google Document AI ([`5cd87b5`](https://github.com/V44nxx/Proyecto_ocr/commit/5cd87b55d8e81ecbc1c9ec80369e91ca0530bfd2))

### Corregido

- Mejorar extracción de `lugar_expedicion` y sexo para layout vertical de Google DocAI y MRZ ([`67e4b6e`](https://github.com/V44nxx/Proyecto_ocr/commit/67e4b6e143c9103e3175c8b20528c048d1bcf349))
- Redirigir a /dashboard usando window.location.href en login ([`375e5d5`](https://github.com/V44nxx/Proyecto_ocr/commit/375e5d5efce933b78e3c4cf3cc30cbdf9c5173e4))
- Ignorar palabras de etiqueta/firma (FIRMA, TITULAR, FECHA Y LUGAR) en extracción de nombres y municipios ([`ed9b120`](https://github.com/V44nxx/Proyecto_ocr/commit/ed9b12058324196a55222c3b576b318e798a1266))
- Procesar OCR en segundo plano (BackgroundTasks) para evitar timeout HTTP en PDFs grandes (42+ págs) ([`d7fb0f9`](https://github.com/V44nxx/Proyecto_ocr/commit/d7fb0f91e426f3ef325b0a823362a9cbf540de9f))
- Filtrar marcas de agua CamScanner, encabezados y omitir registros vacíos `SIN_ID` ([`66dc96d`](https://github.com/V44nxx/Proyecto_ocr/commit/66dc96d2bd1daa901ac6e21bf15312da3864368a))
- Depuración final de nombres/apellidos (límite de 3 palabras, eliminación de duplicados cruzados) y patrón de fecha MMM DD YYYY ([`e7be269`](https://github.com/V44nxx/Proyecto_ocr/commit/e7be26979f25b6ed630f47291ed8271eda7d187f))
- Compatibilidad de clave valor/value y assertion de `test_spatial_field_extractor` ([`eefb664`](https://github.com/V44nxx/Proyecto_ocr/commit/eefb6643ffa06dbe20665474ffab226d3d5c5bb8))
- Extracción espacial 100% basada en coordenadas Document AI con veto estricto de encabezados y eliminación de diccionarios ([`73df5ea`](https://github.com/V44nxx/Proyecto_ocr/commit/73df5eaac0dfa9b942a4d902bd540521c6aed593))
- Soporte para layout físico real de Cédula Amarilla (`DIRECTLY_ABOVE`) y acotamiento estricto de Lugar de Expedición ([`3628e99`](https://github.com/V44nxx/Proyecto_ocr/commit/3628e9939c53ac586beea6930c451b3d9510ff5e))
- Acotamiento espacial universal de regiones entre etiquetas para Cédula Amarilla y Cédula Digital ([`9a3b31e`](https://github.com/V44nxx/Proyecto_ocr/commit/9a3b31e5278eb85452317e5e6d3160f18a0fee6e))
- Validación estricta de fecha en expedición, veto de holograma y clasificación `CEDULA_AMBOS_LADOS` para páginas de 2 caras ([`7104533`](https://github.com/V44nxx/Proyecto_ocr/commit/7104533ea154756fa474bf3609120a759c89f852))
- Depuración de fallback por contexto, filtrado de ruido de holograma en regex y solución para 2 caras por página ([`e87ebc4`](https://github.com/V44nxx/Proyecto_ocr/commit/e87ebc462335abda855b9e1c27b87f982b83f8ff))
- Preservación de preposición DE en municipios compuestos y corrección de score espacial `DIRECTLY_ABOVE` ([`04c1040`](https://github.com/V44nxx/Proyecto_ocr/commit/04c1040d435e8e36b62556ab5d090ebf09051127))
- Sanitización estricta de longitud de campos DB y validación de cédula/sexo en candidatos espaciales ([`8caf660`](https://github.com/V44nxx/Proyecto_ocr/commit/8caf660c5acdd1e67e688733303e450062482321))
- Rango estricto de cédula (7-10 dígitos) e inspección de los 5 campos requeridos estándar ([`fbd3ed8`](https://github.com/V44nxx/Proyecto_ocr/commit/fbd3ed8307a52de21c8f770d44589ec802b1325e))
- Validación universal de fechas (nacimiento/expedición) y municipios sin números ni ruido ([`32ff0fe`](https://github.com/V44nxx/Proyecto_ocr/commit/32ff0febcea30ab0cab25fe591bc16deb92e7825))
- **ocr:** Solucion global universal para nombres y apellidos con tolerancia a marcas de agua y firmas en cedula colombiana ([`014a852`](https://github.com/V44nxx/Proyecto_ocr/commit/014a852fc2a5690f09ff11429345585ccdb98289))
- **ocr:** Implementar correccion automatica de sustituciones OCR tipicas (!/1/|/]/0/5 por I/O/S) en nombres y apellidos ([`f5d09f5`](https://github.com/V44nxx/Proyecto_ocr/commit/f5d09f534bcd4bf8fc9a545e653cf26ac8d8e85c))
- **ocr:** Solucion definitiva universal para la extraccion de `lugar_expedicion` eliminando interferencias de rotulos y firmas ([`afc66c2`](https://github.com/V44nxx/Proyecto_ocr/commit/afc66c2e2ce377d4e9763ed782f5617002d10812))
- **ocr:** Recalibrar puntaje espacial horizontal y refinar filtro `NO_NOMBRE_HEADER` ([`3b0b01b`](https://github.com/V44nxx/Proyecto_ocr/commit/3b0b01b9d4742dcce746b9aea01968386ee20b48))
- **docker:** Agregar Dockerfile multi-etapa en raiz y optimizar variables para VPS ([`d07a2b8`](https://github.com/V44nxx/Proyecto_ocr/commit/d07a2b8455e85485cb6b785d5ecc2978bf0f02fe))
- **frontend:** Sincronizar package-lock.json con package.json para npm ci ([`770f8c7`](https://github.com/V44nxx/Proyecto_ocr/commit/770f8c7e1f5c6684aec6c08fc0637c7d4afd195d))
- **frontend:** Corregir tipos de API y resolver errores de compilacion en Next.js build ([`0e763c1`](https://github.com/V44nxx/Proyecto_ocr/commit/0e763c166fed894dad92ea119952759b3c5ccc9d))
- **docker:** Garantizar la existencia del directorio public durante la construccion en Dockerfile ([`ef00b74`](https://github.com/V44nxx/Proyecto_ocr/commit/ef00b74cc2b3ffeb2535653fe8d4ae2b00181cee))
- Reemplazar libgl1-mesa-glx por libgl1 en Dockerfiles para compatibilidad Debian ([`52ce43e`](https://github.com/V44nxx/Proyecto_ocr/commit/52ce43ee2ac31ba06e15f345f80fdd23baa89398))
- Garantizar creacion automatica de tablas y usuario admin inicial (admin@ocr.com) al arrancar backend en produccion ([`c344fb4`](https://github.com/V44nxx/Proyecto_ocr/commit/c344fb4cd77f28331bfaf30552039b60037b88f0))
- Reparar automaticamente hash de contrasena invalido para admin@ocr.com al iniciar servidor ([`c9f4cd1`](https://github.com/V44nxx/Proyecto_ocr/commit/c9f4cd13e6162b57889a82d2305c782e874ee98b))
- Migrar verificacion de password a Passlib CryptContext y forzar reseteo garantizado de admin@ocr.com en arranque ([`816379b`](https://github.com/V44nxx/Proyecto_ocr/commit/816379bb69c9b7f9be907bae515b9b93b937753b))
- Resolver dinamicamente URL de API en cliente Next.js y habilitar CORS universal (`allow_origin_regex`) en backend ([`723cb25`](https://github.com/V44nxx/Proyecto_ocr/commit/723cb257a114e1db71ac6aa9e9730131fb6dd0a1))
- Implementar proxy rewrites en Next.js para `/api/*` eliminando errores de Mixed Content HTTP/HTTPS y CORS ([`fdf4610`](https://github.com/V44nxx/Proyecto_ocr/commit/fdf4610ab33c28d0e9f3423389745b03ef1fb7ce))

## [1.0.0] - 2026-08-12

**Resumen**

- Primera versión: plataforma full stack con FastAPI, Next.js, PostgreSQL y Docker.

### Agregado

- Initial commit: Proyecto OCR full stack (FastAPI + Next.js + Docker) ([`772447e`](https://github.com/V44nxx/Proyecto_ocr/commit/772447e30d779a5844191bc053e115467c66fae2))

[Sin publicar]: https://github.com/V44nxx/Proyecto_ocr/compare/v2.3.0...main
[2.3.0]: https://github.com/V44nxx/Proyecto_ocr/compare/v2.2.1...v2.3.0
[2.2.1]: https://github.com/V44nxx/Proyecto_ocr/compare/v2.2.0...v2.2.1
[2.2.0]: https://github.com/V44nxx/Proyecto_ocr/compare/v2.1.1...v2.2.0
[2.1.1]: https://github.com/V44nxx/Proyecto_ocr/compare/9afaa4dda36d0a3b750747be7f249efef7dda425...v2.1.1
[2.1.0]: https://github.com/V44nxx/Proyecto_ocr/compare/0aa89e21cd86739e557f122751a81d7729313119...9afaa4dda36d0a3b750747be7f249efef7dda425
[2.0.0]: https://github.com/V44nxx/Proyecto_ocr/compare/410658978296be1a8da9a2fe40f83b5d7ab3271b...0aa89e21cd86739e557f122751a81d7729313119
[1.8.0]: https://github.com/V44nxx/Proyecto_ocr/compare/021ed39c3f8d0a92ef4615b5441155768d988c1c...410658978296be1a8da9a2fe40f83b5d7ab3271b
[1.7.0]: https://github.com/V44nxx/Proyecto_ocr/compare/6d9cdb7607ee92baa27923dd76291161f7ec4ffa...021ed39c3f8d0a92ef4615b5441155768d988c1c
[1.6.0]: https://github.com/V44nxx/Proyecto_ocr/compare/666e54db357b8e8ed95e83eedecf08931a99817f...6d9cdb7607ee92baa27923dd76291161f7ec4ffa
[1.5.0]: https://github.com/V44nxx/Proyecto_ocr/compare/4ea5c314cfe8446fdc84375bb6accac737551775...666e54db357b8e8ed95e83eedecf08931a99817f
[1.4.0]: https://github.com/V44nxx/Proyecto_ocr/compare/a6b3105fb0739d3036e699806274f239bbba47ce...4ea5c314cfe8446fdc84375bb6accac737551775
[1.3.0]: https://github.com/V44nxx/Proyecto_ocr/compare/313b069e91c9da567086402e3dd64c6499078e2f...a6b3105fb0739d3036e699806274f239bbba47ce
[1.2.0]: https://github.com/V44nxx/Proyecto_ocr/compare/fdf4610ab33c28d0e9f3423389745b03ef1fb7ce...313b069e91c9da567086402e3dd64c6499078e2f
[1.1.0]: https://github.com/V44nxx/Proyecto_ocr/compare/772447e30d779a5844191bc053e115467c66fae2...fdf4610ab33c28d0e9f3423389745b03ef1fb7ce
[1.0.0]: https://github.com/V44nxx/Proyecto_ocr/commit/772447e30d779a5844191bc053e115467c66fae2
