# 📑 DOCUMENTACIÓN INTEGRAL DEL SISTEMA KONDID OCR
> **Plataforma Empresarial de Extracción, Clasificación y Conciliación Inteligente de Documentos de Identidad Colombianos**

---

## ÍNDICE GENERAL
1. [Ficha Técnica del Software](#1-ficha-técnica-del-software)
2. [Especificaciones Técnicas del Software](#2-especificaciones-técnicas-del-software)
3. [Estimación Económica y Financiera](#3-estimación-económica-y-financiera)
4. [Manual Técnico](#4-manual-técnico)
5. [Manual de Usuario](#5-manual-de-usuario)

---

# 1. FICHA TÉCNICA DEL SOFTWARE

| Parámetro | Detalle Técnico |
| :--- | :--- |
| **Nombre del Producto** | KondID - Motor OCR Inteligente |
| **Versión Actual** | 2.17.0 (los cambios de cada versión están en el [CHANGELOG](../CHANGELOG.md)) |
| **Tipo de Aplicación** | Sistema Web Empresarial Distribuido (SaaS / On-Premise) |
| **Arquitectura de Software** | Cliente-Servidor desacoplado (SPA Next.js + REST API FastAPI) |
| **Modelo de Licenciamiento** | Propietario / Privado Empresarial |
| **Área de Aplicación** | Digitalización masiva, auditoría documental, verificación de identidad y conciliación de censos/planillas |
| **Tipos de Documento Soportados** | Cédula de Ciudadanía Colombiana (Amarilla con hologramas, Cédula Digital preprensa/policarbonato), Tarjeta de Identidad, Cédula de Extranjería, PPT y Contraseñas |
| **Formatos de Entrada Soportados** | Documentos PDF (multipágina, escaneados, monocromáticos o a color), Planillas Excel (.xlsx, .xls) |
| **Formatos de Salida / Reportes** | XLSX formateado con estilos corporativos, JSON estructurado vía API REST, renderizado de imágenes PNG para auditoría |

### Requerimientos de Hardware y Software

#### Servidor de Producción (Recomendado para 50.000+ páginas/mes)
* **Procesador (CPU):** 4 a 8 Núcleos vCPU (x86_64 o ARM64)
* **Memoria RAM:** 8 GB mínimo (16 GB recomendado para soporte de concurrencia ONNX/OpenCV)
* **Almacenamiento:** 80 GB SSD NVMe (Espacio para base de datos PostgreSQL, volúmenes de PDFs y respaldos binarios)
* **Sistema Operativo:** Ubuntu Server 22.04 LTS / Debian 12 / RHEL 9 (con Docker Engine 24+ y Docker Compose v2)
* **Conectividad:** Conexión a Internet con ancho de banda mínimo de 50 Mbps y latencia menor a 120 ms hacia endpoints de Google Cloud.

#### Servidor Mínimo (Entorno de Pruebas o Bajo Volumen)
* **Procesador (CPU):** 2 Núcleos vCPU
* **Memoria RAM:** 4 GB
* **Almacenamiento:** 30 GB SSD

#### Estación de Trabajo del Cliente (Usuario Final)
* **Navegador Web:** Google Chrome (v110+), Brave Browser (v1.50+), Microsoft Edge (v110+), Mozilla Firefox (v115+), Safari (v16+)
* **Resolución de Pantalla:** Mínimo 1280 x 720 px (Recomendado 1920 x 1080 px para visualización cómoda del visor interactivo dividido)
* **Memoria RAM Cliente:** 4 GB mínimo.

---

# 2. ESPECIFICACIONES TÉCNICAS DEL SOFTWARE

### 2.1. Arquitectura del Sistema
El sistema se compone de tres capas principales orquestadas mediante contenedores Docker:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        CAPA DE PRESENTACIÓN                            │
│              Next.js 16.4 (App Router) + React 19 + TypeScript 5       │
│        Tailwind CSS 4.3 · Política de contenido (CSP) con nonce        │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ HTTP / REST / sesión en cookie HttpOnly
┌───────────────────────────────────▼────────────────────────────────────┐
│                    CAPA LÓGICA / BACKEND (FastAPI)                     │
│  • Enrutadores REST Asíncronos       • Middlewares CORS & Auth JWT     │
│  • Páginas en paralelo (hilos)       • OCR en cascada (3 motores)      │
│  • Extractor Espacial 2D             • Servicio de Emparejamiento      │
│  • Conciliador de Planillas Excel    • Generador de Reportes XLSX      │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ SQLAlchemy 2.0 / asyncpg
┌───────────────────────────────────▼────────────────────────────────────┐
│                       CAPA DE DATOS (PostgreSQL 16)                    │
│   • Extensiones: uuid-ossp, pg_trgm (búsqueda difusa de nombres)       │
│   • Tablas: usuarios, documentos, personas, comparaciones, diferencias │
│   • Almacenamiento binario persistente de PDFs para auto-restauración  │
└────────────────────────────────────────────────────────────────────────┘
```

### 2.2. Pipeline de Procesamiento OCR (9 Fases)
1. **Recepción e Ingesta:** Carga asíncrona del lote de PDFs junto con la planilla oficial de cotejo (.xlsx). Se valida tipo MIME, cabeceras mágicas y límite de tamaño.
2. **Evaluación de Vectorialidad:** PyMuPDF revisa si cada página ya trae texto (PDF digital). Si lo trae, se usa ese texto sin OCR; si es escaneada, se convierte en imagen a 300 DPI. Las páginas se leen en paralelo: 4 a la vez con Document AI (casi todo el tiempo es esperar a Google); con RapidOCR, una por núcleo (entre 2 y 4).
3. **OCR en cascada**, página por página (el texto de un motor no se mezcla con el de otro):
   - *Motor Principal:* **Google Cloud Document AI** (texto, líneas y coordenadas normalizadas). Si Google responde que se pasó el límite de solicitudes, se espera 1, 2 y 4 s y se reintenta.
   - *Respaldo local:* **RapidOCR ONNX Runtime** en CPU, cuando Document AI no está configurado, no hay conexión, falla o devuelve muy poco texto. Lee solo la zona impresa de la hoja (achicada a 1250 px de lado) y separa los nombres que lee pegados.
   - *Último recurso:* **Tesseract OCR**, si los dos anteriores fallan.
4. **Clasificación de Caras (Side Classifier):** Clasifica cada página como cara *Frente* (contiene nombres, apellidos, cédula) o *Reverso* (contiene fecha de nacimiento, expedición, lugar, sexo), o como certificado o documento de soporte.
5. **Emparejamiento Frente-Reverso:** Asocia correlativamente frentes y reversos según posición de páginas o consistencia de número de cédula.
6. **Extracción Espacial 2D con Cajas Delimitadoras:** Análisis de proximidad geométrica respecto a los rótulos ancla colombianos (`"NOMBRES"`, `"APELLIDOS"`, `"NUMERO"`, `"FECHA DE NACIMIENTO"`).
7. **Validación Geográfica y Fonética:** Cotejo con la base de datos de municipios DANE y diccionario de nombres colombianos comunes para resolver ambigüedades.
8. **Cruce Determinístico con Planilla Excel:** Los nombres y apellidos extraídos son cotejados con la planilla oficial. Si hay discrepancia, se prioriza el dato oficial y se registra la alerta para revisión asistida.
9. **Persistencia Transaccional y Respaldo:** Inserción en PostgreSQL, almacenamiento de copia binaria de la ficha para auto-restauración y generación automática de métricas de consistencia.

---

# 3. ESTIMACIÓN ECONÓMICA Y FINANCIERA

Esta estimación presenta el análisis de costos para el desarrollo, despliegue, infraestructura y operación del sistema KondID OCR v2.0.

### 3.1. Costos de Desarrollo de Software (Inversión Inicial - CAPEX)
Basado en una estimación por horas-hombre con metodología ágil (duración estimada de 16 semanas):

| Rol Profesional | Horas Estimadas | Tarifa / Hora (USD) | Subtotal (USD) |
| :--- | :---: | :---: | :---: |
| **Arquitecto de Software / Tech Lead** | 160 h | $35 USD | $5,600 USD |
| **Ingeniero Backend (FastAPI / Computer Vision / OCR)** | 280 h | $28 USD | $7,840 USD |
| **Ingeniero Frontend (Next.js / TypeScript / UI)** | 220 h | $25 USD | $5,500 USD |
| **Especialista en QA, Seguridad y Validación DANE** | 120 h | $18 USD | $2,160 USD |
| **Ingeniero DevOps (Docker, CI/CD, Dokploy, Cloud)** | 100 h | $30 USD | $3,000 USD |
| **TOTAL ESTIMADO DE DESARROLLO** | **880 h** | — | **$24,100 USD** |

*(Equivalente aproximado en pesos colombianos: ~$96,400,000 COP a TRM 4,000).*

---

### 3.2. Costos de Infraestructura y Servidores (Mensual / Anual)

| Componente | Especificaciones | Costo Mensual (USD) | Costo Anual (USD) |
| :--- | :--- | :---: | :---: |
| **VPS Cloud Dedicado (Hetzner / DigitalOcean / AWS)** | 4 vCPU, 8 GB RAM, 80 GB NVMe, Tráfico 20 TB | $25.00 USD | $300.00 USD |
| **Base de Datos PostgreSQL** | Instancia administrada o contenedor optimizado | $15.00 USD | $180.00 USD |
| **Dominio y Certificados SSL** | Dominio propio + SSL Let's Encrypt / Cloudflare | $1.25 USD | $15.00 USD |
| **Backups Automáticos S3 / Almacenamiento Frío** | 100 GB de respaldos cifrados semanales | $3.00 USD | $36.00 USD |
| **SUBTOTAL INFRAESTRUCTURA** | — | **$44.25 USD** | **$531.00 USD** |

---

### 3.3. Costos Operativos de Motores OCR (Google Document AI + RapidOCR)

El motor cuenta con la ventaja de que **RapidOCR ONNX corre 100% en la CPU local a $0.00 USD de costo de API**.  
Para el motor neural en la nube (Google Cloud Document AI), la tarifa es de aproximadamente **$1.50 USD por cada 1.000 páginas**:

| Escenario de Volumen Mensual | Páginas Procesadas | Google Document AI | RapidOCR (Local) | Costo Mensual OCR |
| :--- | :---: | :---: | :---: | :---: |
| **Bajo (Muestra / Pruebas)** | 2,000 páginas | $3.00 USD | $0.00 USD | **$3.00 USD** |
| **Medio (Operación Estándar)** | 10,000 páginas | $15.00 USD | $0.00 USD | **$15.00 USD** |
| **Alto (Censo Empresarial)** | 50,000 páginas | $75.00 USD | $0.00 USD | **$75.00 USD** |
| **Masivo (Picos de Auditoría)**| 100,000 páginas | $150.00 USD | $0.00 USD | **$150.00 USD** |

---

### 3.4. Costos de Mantenimiento y Soporte Técnico (OPEX)
* **Mantenimiento Preventivo y Correctivo (SLA 8x5):** $250.00 USD / mes ($3,000.00 USD / año).
* **Actualización de Librerías y Parches de Seguridad:** Incluido en la póliza de soporte.

---

### 3.5. Retorno de Inversión (ROI) vs. Digitación Manual Tradicional

| Concepto | Proceso Manual Tradicional | KondID OCR v2.0 |
| :--- | :--- | :--- |
| **Tiempo por Cédula (Frente + Reverso)** | 2.5 a 4.0 minutos por persona | **1.5 a 3.0 segundos** (automatizado) |
| **Capacidad de 1 Operador en 8 Horas** | 120 a 160 cédulas / día | **4,000 a 8,000 cédulas / día** |
| **Tasa de Error Humano en Nombres/Cédula** | 4.5% - 8.0% | **Menor al 0.5%** (gracias al cruce Excel) |
| **Costo por Cédula Procesada** | ~$0.25 USD ($1,000 COP) | **~$0.003 USD ($12 COP)** |
| **Ahorro Estimado Operativo** | Base de comparación | **> 95% de ahorro en costos directos** |

---

# 4. MANUAL TÉCNICO

### 4.1. Estructura de Directorios del Código Fuente

```
proyecto_ocr/
├── backend/
│   ├── app/
│   │   ├── main.py                  # Servidor FastAPI y registro de routers
│   │   ├── config.py                # Pydantic Settings (.env)
│   │   ├── database.py              # Sesión SQLAlchemy y engine PostgreSQL
│   │   ├── models/                  # Entidades: Usuario, Documento, Persona, etc.
│   │   ├── schemas/                 # Esquemas Pydantic de validación
│   │   ├── routers/                 # Endpoints REST (auth, documentos, personas...)
│   │   └── services/
│   │       ├── ocr_service.py       # Pipeline maestro
│   │       ├── google_document_ai_service.py # Conector GCP Document AI
│   │       ├── rapid_ocr_service.py # Conector ONNX Runtime
│   │       ├── spatial_field_extractor.py # Geometría 2D
│   │       └── comparacion_service.py     # Conciliación con Excel
│   ├── requirements.txt             # Dependencias Python
│   └── Dockerfile                   # Imagen backend (Python 3.12-slim)
├── frontend/
│   ├── src/
│   │   ├── app/                     # Rutas Next.js 16 App Router
│   │   │   ├── dashboard/           # Métricas del sistema
│   │   │   ├── documentos/          # Carga de lotes y visor PDF
│   │   │   ├── personas/            # Tabla de registros y acordeón
│   │   │   ├── comparacion/         # Discrepancias
│   │   │   ├── exportacion/         # Descarga XLSX
│   │   │   ├── seguimiento/         # Panel de seguimiento de fichas (Google Apps Script)
│   │   │   ├── usuarios/            # Gestión de usuarios (administrador)
│   │   │   └── auditoria/           # Registro de auditoría (administrador)
│   │   ├── components/ui/           # Sidebar, modales, selectores en ventana, íconos propios
│   │   ├── lib/api.ts               # Cliente Axios configurado con interceptores
│   │   ├── lib/datosRecientes.ts    # Datos de la última visita a cada pantalla (solo en memoria)
│   │   └── proxy.ts                 # Política de contenido (CSP) con un nonce por petición
│   ├── package.json
│   └── Dockerfile                   # Imagen frontend (Node.js 24-alpine)
├── database/init.sql                # Script DDL inicial
├── credentials/                     # Credenciales JSON de Google Cloud
└── docker-compose.yml               # Orquestador multi-contenedor
```

### 4.2. Despliegue con Docker Compose
1. **Configurar archivo de entorno:**
   ```bash
   cp .env.example .env
   ```
2. **Colocar credencial de Google Cloud:**
   Ubicar el archivo de Service Account en: `credentials/google-document-ai.json`.
3. **Iniciar los servicios:**
   ```bash
   docker-compose up -d --build
   ```
4. **Verificación de Contenedores:**
   ```bash
   docker-compose ps
   ```
   Deben estar activos los servicios: `ocr_postgres` (5432), `ocr_backend` (8000) y `ocr_frontend` (3000).

### 4.3. Variables de Entorno Fundamentales (.env)
```ini
# Base de Datos
DATABASE_URL=postgresql://ocr_user:<tu_contraseña>@ocr_postgres:5432/ocr_documentos

# Seguridad
# Genera una propia: python -c "import secrets; print(secrets.token_urlsafe(64))"
SECRET_KEY=<tu_clave_secreta>
ACCESS_TOKEN_EXPIRE_MINUTES=480

# Google Cloud Document AI
GOOGLE_CLOUD_PROJECT=tu-proyecto-gcp
GOOGLE_DOCUMENT_AI_LOCATION=us
GOOGLE_DOCUMENT_AI_PROCESSOR_ID=tu_processor_id
GOOGLE_DOCUMENT_AI_ENABLED=true
GOOGLE_APPLICATION_CREDENTIALS=/app/credentials/google-document-ai.json

# Motores OCR
GOOGLE_DOCUMENT_AI_TIMEOUT=60      # segundos por página antes de pasar a RapidOCR
RAPID_OCR_ENABLED=true
RAPID_OCR_LADO_MAXIMO=1250         # lado mayor (px) de la zona impresa que lee RapidOCR

# Sesión y correo
# COOKIE_SECURE=                   # por defecto Secure en production
SMTP_HOST=smtp.gmail.com           # sin SMTP_HOST no hay recuperación de contraseña
FRONTEND_URL=http://localhost:3000 # para el enlace del correo; obligatoria en producción
```

La lista completa, con una explicación de cada variable, está en `.env.example`. Cuántas páginas se leen a la vez no se configura: depende del motor y de los núcleos del servidor.

### 4.4. Rutas Críticas de la API REST

* **`POST /api/auth/login`**: Autenticación con email y contraseña. Pone la cookie de sesión (`HttpOnly`, `SameSite=Strict`); a un administrador le devuelve primero el desafío de la verificación en dos pasos (`/api/auth/login/2fa`).
* **`POST /api/documentos/upload`**: Carga multipart de lote de archivos PDF (`archivos`) junto con la planilla obligatoria (`archivo_excel`).
* **`GET /api/documentos/{id}/pagina/{numero}`**: Retorna la imagen JPEG de una página específica del PDF. La sesión va en la cookie (nunca en la dirección) y la respuesta no se guarda en caché.
* **`GET /api/personas`**: Listado paginado de personas con filtros avanzados (`buscar`, `filtro_estado`, `documento_id`).
* **`PUT /api/personas/{id}`**: Modificación directa de campos corregidos manualmente.
* **`GET /api/exportacion/xlsx`**: Generación y descarga al vuelo del archivo Excel oficial con formatos, colores y metadatos.

---

# 5. MANUAL DE USUARIO

### 5.1. Acceso a la Plataforma
1. Abra su navegador web (Chrome, Brave, Edge, Firefox).
2. Ingrese a la URL asignada del sistema (ej: `http://localhost:3000` o su dominio público).
3. Ingrese su correo electrónico y contraseña registrados.
4. Presione **Iniciar Sesión**.
5. **Administradores:** después de la contraseña se pide el código de 6 dígitos de la app de autenticación (Google Authenticator, Microsoft Authenticator u otra). La primera vez se vincula la app con un código QR y se entregan 10 códigos de respaldo de un solo uso.
6. Si olvidó la contraseña, use **¿Olvidaste tu contraseña?**: llega un enlace al correo para crear una nueva.

### 5.2. Módulo de Dashboard
* **Tarjetas de Estadísticas:** Muestra en tiempo real el total de documentos procesados, personas extraídas, registros validados y registros pendientes de revisión.
* **Historial Reciente:** Lista las últimas fichas procesadas con estado de avance.
* **Acceso Rápido:** Botones directos para subir nuevos lotes o exportar a Excel.

### 5.3. Módulo de Carga de Documentos (Documentos PDF)
1. Ingrese al módulo **Documentos PDF** desde el menú lateral.
2. En la zona de carga arrastre o seleccione los archivos PDF que contienen las cédulas.
3. **Planilla Oficial Excel (Obligatoria):** Seleccione el archivo `.xlsx` de referencia que contiene la lista oficial de los participantes.
4. Haga clic en **Iniciar Procesamiento**.
5. Se mostrará una barra de avance dinámica que indica:
   - Número de página actual en proceso.
   - Cantidad de personas extraídas en tiempo real.
   - Botón de **Cancelar Proceso** en caso de requerir abortar la carga.

### 5.4. Módulo de Personas (Base de Datos OCR)
* **Buscador Universal:** Permite filtrar instantáneamente por número de cédula o por nombres/apellidos.
* **Filtros Rápidos:**
  - *Todos los registros*: Visualiza la totalidad de la base de datos.
  - *Por Revisar*: Muestra únicamente registros que presentan advertencias (ej: menor de 14 años, o datos no encontrados en la planilla).
  - *Válidos*: Muestra los registros completos y confirmados.
  - *Falta en PDF / Excel*: Permite ubicar personas que están en la planilla Excel pero no se encontró su cédula en el PDF.
* **Visor Interactivo Dividido (Al hacer clic en cualquier fila):**
  - **Lado Izquierdo (Visor Documento):** Permite ver la foto real de la cédula del PDF original, hacer zoom (acercar/alejar) y alternar entre la cara **Frente** y **Reverso**.
  - **Lado Derecho (Datos Extraídos):** Muestra los valores de cédula, nombres, fecha de nacimiento, edad calculada, sexo y lugar de expedición con porcentaje de confianza de extracción.
  - **Acción "Editar Datos":** Permite modificar cualquier dato en caso de enmienda manual.
  - **Acción "Aprobar y Validar":** Confirma el registro y retira la alerta de revisión.
  - **Acción "Subir PDF Cédula":** Si una persona fue cargada desde el Excel pero no tenía cédula en el lote PDF, este botón permite adjuntarle su documento individual directamente.

### 5.5. Módulo de Comparación y Discrepancias
* Permite cargar planillas adicionales de auditoría para verificar inconsistencias históricas entre la base de datos y archivos externos.
* Resalta campo a campo cualquier discordancia (por ejemplo, si el nombre en el Excel tiene un apellido invertido respecto a la cédula física).
* Proporciona un botón directo para aplicar el valor del Excel o el valor del OCR con un solo clic.

### 5.6. Módulo de Exportación
1. Ingrese a **Exportación**.
2. Puede elegir descargar:
   - Todas las personas registradas en el sistema.
   - Filtrar por un archivo PDF específico.
   - O exportar únicamente las personas previamente seleccionadas con las casillas de verificación.
3. Presione **Descargar Excel (.xlsx)**. El sistema generará una hoja de cálculo profesional con columnas ordenadas, tipos de datos validados y códigos de color según el estado.

### 5.7. Seguimiento de Fichas
* Muestra dentro de KondID el panel de seguimiento publicado con Google Apps Script. Cada usuario guarda el enlace de su panel con **Configurar** y puede quitarlo cuando quiera.
* El código del panel está en `apps-script/seguimiento-fichas/`, junto con su `LEEME.md`, que explica la instalación, las etapas, las alertas y el historial de cambios. El panel lee y edita la hoja «FORMACIONES COMPLEMENTARIAS GRUPOS» y tiene tres vistas: calendario, lista y cambios.
* El enlace lleva una clave (`?k=...`); sin ella el panel no muestra nada. KondID agrega el nombre de quien tiene la sesión abierta (`&u=...`) para que el historial diga quién guardó cada cambio.

### 5.8. Usuarios y Auditoría (solo administradores)
* **Usuarios:** crear usuarios, eliminarlos, restablecer su contraseña y restablecer la verificación en dos pasos de un administrador que perdió el celular y los códigos de respaldo.
* **Auditoría:** quién inició sesión, exportó, editó o eliminó datos, y desde qué IP. Se filtra por acción en una ventana con las acciones agrupadas. No guarda contraseñas ni datos de las personas.

### 5.9. Menú Lateral, Avisos y Configuración
* **Logo:** lleva al Dashboard desde cualquier pantalla.
* **Colapso del Menú:** Haga clic en el ícono superior del sidebar para ocultar o expandir el menú lateral.
* **Selector de Tema:** Interruptor para alternar entre **Modo Oscuro** y **Modo Claro**. Con cambios seguidos solo queda el aviso del último.
* **Listas de opciones:** fichas, tipo de documento y filtros se eligen en una ventana con buscador; las confirmaciones (eliminar, cancelar) usan un diálogo propio con el foco en «Cancelar».
* **Avisos del sistema:** sin internet, conexión lenta, servidor que no responde, versión nueva, sesión cerrada desde otro lado y descargas con datos personales.
* **Cambiar contraseña** y **Cerrar Sesión:** en la parte inferior del menú. Cerrar sesión invalida la sesión en el servidor y borra de la pestaña los datos que se habían mostrado.

