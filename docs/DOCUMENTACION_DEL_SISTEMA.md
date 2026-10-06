# 📑 DOCUMENTACIÓN INTEGRAL DEL SISTEMA KONDID OCR v2.0
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
| **Versión Actual** | 2.0.0 (Release Estable - Smart Dual OCR) |
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
│                 Next.js 14.2 (App Router) + TypeScript 5               │
│             TailwindCSS 3.4 (Apple Design System: Frosted Glass)       │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ HTTP / REST / Bearer JWT
┌───────────────────────────────────▼────────────────────────────────────┐
│                    CAPA LÓGICA / BACKEND (FastAPI)                     │
│  • Enrutadores REST Asíncronos       • Middlewares CORS & Auth JWT     │
│  • ThreadPoolExecutor Multi-hilo     • Orquestador Smart Dual OCR      │
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
2. **Evaluación de Vectorialidad:** PyMuPDF analiza si el documento contiene texto vectorial nativo embebido. De ser así, se extrae en modo *ultra-rápido bypass*; de lo contrario, se rasteriza a 200 DPI optimizados.
3. **Clasificación de Caras (Side Classifier):** Clasifica cada página como cara *Frente* (contiene nombres, apellidos, cédula) o *Reverso* (contiene fecha de nacimiento, expedición, lugar, sexo).
4. **Smart Dual OCR:**
   - *Motor Principal:* **Google Cloud Document AI** (extracción neural con jerarquía de bloques y coordenadas cartesianas normalizadas).
   - *Rescate Neural Local:* **RapidOCR ONNX Runtime** en CPU para capturar líneas o caracteres desvanecidos sin costo de GPU.
   - *Fallback de Contingencia:* **Tesseract OCR** en caso de pérdida de conexión externa.
5. **Extracción Espacial 2D con Cajas Delimitadoras:** Análisis de proximidad geométrica respecto a los rótulos ancla colombianos (`"NOMBRES"`, `"APELLIDOS"`, `"NUMERO"`, `"FECHA DE NACIMIENTO"`).
6. **Validación Geográfica y Fonética:** Cotejo con la base de datos de municipios DANE y diccionario de nombres colombianos comunes para resolver ambigüedades.
7. **Emparejamiento Frente-Reverso:** Asocia correlativamente frentes y reversos según posición de páginas o consistencia de número de cédula.
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
│   │   ├── app/                     # Rutas Next.js 14 App Router
│   │   │   ├── dashboard/           # Métricas del sistema
│   │   │   ├── documentos/          # Carga de lotes y visor PDF
│   │   │   ├── personas/            # Tabla de registros y acordeón
│   │   │   ├── comparacion/         # Discrepancias
│   │   │   └── exportacion/         # Descarga XLSX
│   │   ├── components/ui/           # Sidebar, botones, modales
│   │   └── lib/api.ts               # Cliente Axios configurado con interceptores
│   ├── package.json
│   └── Dockerfile                   # Imagen frontend (Node.js 20-alpine)
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
DATABASE_URL=postgresql://ocr_user:ocr_password_2024@ocr_postgres:5432/ocr_documentos

# Seguridad
SECRET_KEY=clave_secreta_jwt_muy_segura_de_produccion_2024
ACCESS_TOKEN_EXPIRE_MINUTES=480

# Google Cloud Document AI
GOOGLE_CLOUD_PROJECT=tu-proyecto-gcp
GOOGLE_DOCUMENT_AI_LOCATION=us
GOOGLE_DOCUMENT_AI_PROCESSOR_ID=tu_processor_id
GOOGLE_DOCUMENT_AI_ENABLED=true
GOOGLE_APPLICATION_CREDENTIALS=/app/credentials/google-document-ai.json

# Parámetros del Motor OCR
OCR_ENGINE=smart_dual
OCR_CONCURRENCY_WORKERS=6
OCR_DPI=200
```

### 4.4. Rutas Críticas de la API REST

* **`POST /api/auth/login`**: Autenticación con email y contraseña, retorna Bearer Token JWT.
* **`POST /api/documentos/upload`**: Carga multipart de lote de archivos PDF (`archivos`) junto con la planilla obligatoria (`archivo_excel`).
* **`GET /api/documentos/{id}/pagina/{numero}`**: Retorna la imagen rasterizada en PNG de una página específica del PDF (con autenticación por header o query `?token=`).
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

### 5.7. Menú Lateral y Configuración
* **Colapso del Menú:** Haga clic en el ícono superior del sidebar para ocultar o expandir el menú lateral.
* **Selector de Tema:** Interruptor para alternar instantáneamente entre **Modo Oscuro** (Dark Mode con diseño Apple) y **Modo Claro** (Light Mode).
* **Cerrar Sesión:** Ubicado en la parte inferior para finalizar la sesión de trabajo de forma segura.
