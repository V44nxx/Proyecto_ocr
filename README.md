# 🔍 Sistema OCR - Documentos de Identificación Colombianos

Plataforma empresarial de alta precisión para la extracción automática, clasificación, validación y comparación de documentos de identidad colombianos (Cédula de Ciudadanía tradicional, Cédula Digital, Tarjeta de Identidad). 

Cuenta con arquitectura **Smart Dual OCR** (Google Cloud Document AI + RapidOCR ONNX con fallback a Tesseract), cruce determinístico con planilla oficial Excel, visor interactivo de documentos página por página y módulo de conciliación de discrepancias.

---

## 🏗️ Arquitectura del Sistema

```
┌────────────────────────────────────────────────────────────────────────┐
│                        CLIENTE WEB (Browser)                          │
│                   Next.js 14 + TypeScript + Tailwind                   │
│                        http://localhost:3000                           │
│  • Dashboard de métricas       • Lotes PDF + Planilla oficial Excel   │
│  • Visor de páginas PDF en vivo • Tabla interactiva de personas        │
│  • Módulo de comparación Excel  • Exportación XLSX formateada          │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ HTTP / REST / JWT
┌───────────────────────────────────▼────────────────────────────────────┐
│                    BACKEND FastAPI (Python 3.12)                       │
│                        http://localhost:8000                           │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                     PIPELINE MULTI-MOTOR OCR                     │  │
│  │  1. PyMuPDF (Extracción nativa de texto o renderizado a 200 DPI) │  │
│  │  2. Clasificador de caras: Frente vs Reverso (Side Classifier)   │  │
│  │  3. Google Document AI (Motor neural principal estructurado 2D)  │  │
│  │  4. RapidOCR ONNX Runtime (Rescate y fusión de líneas local)     │  │
│  │  5. Tesseract OCR (Fallback de emergencia o modo offline)        │  │
│  │  6. Extractor Espacial 2D con Cajas Delimitadoras                │  │
│  │  7. Emparejamiento Frente-Reverso (Document Pairing Service)     │  │
│  │  8. Validación DANE (Colombia Geo) + Diccionario de Nombres      │  │
│  │  9. Cruce con Planilla Excel Oficial (Garantía 100% en Nombres)   │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│  • Multi-hilo (ThreadPoolExecutor con hasta 6 workers por lote)        │
│  • Cancelación en caliente de procesos y remoción de archivos          │
│  • Auto-restauración de PDFs desde binario en base de datos            │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ SQLAlchemy 2.0 / PostgreSQL Driver
┌───────────────────────────────────▼────────────────────────────────────┐
│                         PostgreSQL 16                                  │
│                        http://localhost:5432                           │
│   • usuarios        • documentos (con metadatos y respaldo binario)    │
│   • personas        • comparaciones     • diferencias                  │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
┌───────────────────────────────────▼────────────────────────────────────┐
│                     pgAdmin 4 (Administración BD)                      │
│                        http://localhost:5050                           │
└────────────────────────────────────────────────────────────────────────┘
```

---

## ✨ Características Principales

- **Smart Dual OCR Inteligente**:
  - **Google Cloud Document AI**: Reconocimiento de alta precisión con jerarquía de bloques, párrafos, líneas y coordenadas 2D.
  - **RapidOCR ONNX Runtime**: Motor neural local y rápido que rescata líneas o caracteres no capturados por Document AI sin requerir GPU pesada.
  - **Tesseract OCR (pytesseract)**: Motor de contingencia offline.
  - **PyMuPDF Direct**: Bypass de lectura vectorial para PDFs digitales sin pérdida de tiempo ni costo de OCR.
- **Emparejamiento Inteligente Frente y Reverso**: Asocia automáticamente las caras de una misma cédula aunque se encuentren en páginas separadas o consecutivas.
- **Cruce con Planilla Oficial de Excel (.xlsx / .xls)**:
  - Garantiza nombres y apellidos oficiales exactos cotejados por número de cédula.
  - Detección automática de personas registradas en la planilla oficial pero no encontradas en el PDF (marcadas para revisión con alerta visual).
- **Visor Integrado de PDF**: Renderizado dinámico de páginas bajo demanda en formato PNG (`/api/documentos/{id}/pagina/{numero}`) directamente desde el frontend.
- **Resiliencia de Archivos (Auto-restauración)**: Respaldo binario en PostgreSQL (`archivo_binario`) para regenerar PDFs físicos si se reinician contenedores o se pierden volúmenes en Dokploy/Docker.
- **Gestión y Cancelación en Vivo**: Capacidad de abortar un lote en procesamiento y purgar de inmediato registros y archivos temporales.
- **Módulo de Comparación y Conciliación**: Compara datos extraídos contra el Excel, resalta diferencias y permite correcciones inmediatas con un clic.
- **Exportación Profesional a Excel**: Generación de reportes XLSX estilizados con Pandas y OpenPyXL.

---

## ⚡ Inicio Rápido con Docker Compose

### Prerrequisitos
- [Docker Desktop](https://www.docker.com/) instalado y en ejecución.
- Credenciales de Google Cloud Document AI (archivo `credentials/google-document-ai.json`).

### 1. Clonar y configurar entorno

```bash
cd c:\xampp\htdocs\proyecto_ocr

# Crear archivo de variables de entorno desde la plantilla
copy .env.example .env
```

Edita `.env` para ingresar tu configuración de Google Cloud y contraseñas:
```ini
GOOGLE_CLOUD_PROJECT=tu-proyecto-gcp
GOOGLE_DOCUMENT_AI_LOCATION=us
GOOGLE_DOCUMENT_AI_PROCESSOR_ID=tu_processor_id_aqui
GOOGLE_DOCUMENT_AI_ENABLED=true
GOOGLE_APPLICATION_CREDENTIALS=/app/credentials/google-document-ai.json
```

Coloca tu Service Account JSON en la carpeta `credentials/`:
```bash
# credentials/google-document-ai.json
```

### 2. Levantar los contenedores

```bash
docker-compose up -d --build
```

Esto inicia automáticamente:
- **PostgreSQL 16**: puerto `5432`
- **FastAPI Backend**: puerto `8000`
- **Next.js Frontend**: puerto `3000`
- **pgAdmin 4**: puerto `5050`

### 3. Verificar estado

```bash
docker-compose ps
docker-compose logs -f backend
```

### 4. Acceso y Credenciales por Defecto

| Servicio | URL | Credenciales por Defecto |
|:---------|:----|:-------------------------|
| **Frontend Web** | [http://localhost:3000](http://localhost:3000) | `admin@ocr.com` / `Admin123!` |
| **Documentación Swagger** | [http://localhost:8000/docs](http://localhost:8000/docs) | Autenticación con Bearer Token |
| **Health Check API** | [http://localhost:8000/health](http://localhost:8000/health) | Acceso público |
| **pgAdmin 4** | [http://localhost:5050](http://localhost:5050) | `admin@ocr.com` / `admin123` |

---

## 🖥️ Desarrollo Local (Sin Docker)

### Backend (Python 3.12)

```bash
cd backend

# Crear y activar entorno virtual
python -m venv .venv
.venv\Scripts\activate       # Windows PowerShell / CMD
# source .venv/bin/activate  # Linux / macOS

# Instalar dependencias
pip install -r requirements.txt

# Configurar variables de entorno locales
copy ..\.env.example .env
# Ajustar DATABASE_URL=postgresql://ocr_user:ocr_password_2024@localhost:5432/ocr_documentos
# Ajustar GOOGLE_APPLICATION_CREDENTIALS=../credentials/google-document-ai.json

# Ejecutar el servidor de desarrollo
uvicorn app.main:app --reload --port 8000
```

### Frontend (Next.js 14)

```bash
cd frontend

# Instalar dependencias Node
npm install

# Iniciar servidor de desarrollo
npm run dev
# Disponible en http://localhost:3000
```

---

## 📊 Pipeline de Procesamiento OCR

```
                      [ PDF(s) + Planilla Excel Oficial ]
                                       ↓
                [ Validación de formato y límites de carga ]
                                       ↓
         [ Carga y normalización de la planilla oficial Excel (.xlsx) ]
                                       ↓
                 [ PyMuPDF: Detección de texto vectorial nativo ]
                   ├─ ¿Texto nativo limpio? ─→ Extracción directa
                   └─ ¿Documento escaneado? ─→ Renderizado a 200 DPI
                                       ↓
            [ Concurrencia: ThreadPoolExecutor (hasta 6 workers) ]
                                       ↓
                [ Clasificador de Caras (Side Classifier) ]
                   ├─ Frente (Nombres, Apellidos, Cédula)
                   └─ Reverso (Fecha de Nacimiento, Expedición, Lugar, Sexo)
                                       ↓
             [ SMART DUAL OCR: Google Document AI + RapidOCR ]
                ① Google Cloud Document AI: Bloques y líneas espaciales 2D
                ② Si requiere rescate: RapidOCR ONNX complementa líneas
                ③ Fallback: Tesseract OCR (en caso de error de red/servicios)
                                       ↓
              [ Extractor Espacial 2D con Cajas Delimitadoras ]
                • Proximidad de campos (NÚMERO, FECHA, LUGAR, etc.)
                • Corrección de caracteres contextuales
                • Validación DANE de municipios y departamentos
                                       ↓
            [ Emparejamiento de Documentos (Pairing Service) ]
                • Unión de páginas Frente + Reverso de la misma persona
                                       ↓
            [ Cruce Determinístico con la Planilla Oficial Excel ]
                • Nombres y apellidos cotejados por cédula (100% consistencia)
                • Personas en Excel no halladas en PDF → Estado REVIEW_REQUIRED
                                       ↓
           [ Persistencia en PostgreSQL + Respaldo Binario en BD ]
                                       ↓
              [ Ejecución Automática del Módulo de Comparación ]
```

---

## 🔌 Catálogo de Endpoints API

### 🔐 Autenticación y Usuarios (`/api/auth`)
| Método | Endpoint | Descripción |
|:-------|:---------|:------------|
| `POST` | `/api/auth/login` | Iniciar sesión y retornar token JWT |
| `POST` | `/api/auth/login/form` | Login compatible con OAuth2 Password Flow (Swagger UI) |
| `POST` | `/api/auth/register` | Registro de nuevo usuario |
| `GET` | `/api/auth/me` | Obtener perfil del usuario autenticado |
| `GET` | `/api/auth/users` | Listar todos los usuarios (Requiere rol Admin) |
| `DELETE` | `/api/auth/users/{user_id}` | Eliminar cuenta de usuario (Requiere rol Admin) |
| `GET` | `/api/auth/health` | Verificación de estado de base de datos y backend |

### 📄 Documentos (`/api/documentos`)
| Método | Endpoint | Descripción |
|:-------|:---------|:------------|
| `POST` | `/api/documentos/upload` | Carga de lote de PDFs con **Planilla Excel obligatoria** |
| `POST` | `/api/documentos/cancelar` | Cancela procesamiento en curso y elimina archivos/registros |
| `GET` | `/api/documentos` | Listar documentos del usuario actual |
| `GET` | `/api/documentos/{id}` | Obtener detalle y metadatos del documento |
| `GET` | `/api/documentos/{id}/personas` | Listar personas extraídas (con fallback a snapshot histórico) |
| `GET` | `/api/documentos/{id}/estado` | Consulta de progreso y paso actual en tiempo real |
| `DELETE` | `/api/documentos/{id}` | Eliminar documento y sus registros asociados |
| `GET` | `/api/documentos/dashboard/estadisticas` | Métricas agregadas para el Dashboard |
| `GET` | `/api/documentos/{id}/pagina/{numero}` | Visualizar página del PDF renderizada en PNG (soporta query `?token=`) |
| `GET` | `/api/documentos/{id}/debug_espacial` | Reporte de depuración de cajas delimitadoras espaciales |

### 👥 Personas (`/api/personas`)
| Método | Endpoint | Descripción |
|:-------|:---------|:------------|
| `GET` | `/api/personas` | Listado paginado de personas con filtros (`q`, `estado`, `requiere_revision`) |
| `GET` | `/api/personas/{id}` | Detalle completo de una persona |
| `PUT` | `/api/personas/{id}` | Corrección manual de datos de la persona |
| `POST` | `/api/personas/{id}/subir-pdf` | Asignar PDF individual a persona cargada desde Excel |
| `DELETE` | `/api/personas/{id}` | Eliminar persona individual |
| `POST` | `/api/personas/batch-delete` | Eliminación masiva de lista de personas |
| `DELETE` | `/api/personas/vaciar/todas` | Vaciar todas las personas del usuario |
| `GET` | `/api/personas/buscar/cedula/{cedula}` | Búsqueda directa por número de identificación |

### ⚖️ Comparación y Conciliación (`/api/comparacion`)
| Método | Endpoint | Descripción |
|:-------|:---------|:------------|
| `POST` | `/api/comparacion/upload` | Subir archivo Excel para análisis de comparación |
| `POST` | `/api/comparacion/{id}/ejecutar` | Ejecutar comparación de base de datos vs archivo Excel |
| `GET` | `/api/comparacion` | Listar historial de comparaciones |
| `GET` | `/api/comparacion/{id}` | Estadísticas y resultados de una comparación |
| `GET` | `/api/comparacion/{id}/diferencias` | Detalle de discrepancias campo por campo |
| `POST` | `/api/comparacion/{id}/corregir-campo` | Aplicar corrección directa desde el comparador a la base de datos |
| `POST` | `/api/comparacion/{id}/agregar-persona-bd` | Incorporar persona faltante del Excel a la base de datos |
| `GET` | `/api/comparacion/{id}/reporte` | Descarga de informe de comparación en XLSX |

### 📥 Exportación (`/api/exportacion`)
| Método | Endpoint | Descripción |
|:-------|:---------|:------------|
| `GET` | `/api/exportacion/xlsx` | Exportar todas las personas a Excel formateado |
| `POST` | `/api/exportacion/xlsx` | Exportar selección específica de IDs a Excel |
| `GET` | `/api/exportacion/diferencias/{id}` | Exportar reporte de diferencias a Excel |

### 🛠️ Sistema (`/`)
| Método | Endpoint | Descripción |
|:-------|:---------|:------------|
| `GET` | `/` | Información base del API |
| `GET` | `/health` | Chequeo de salud del servicio |
| `GET/POST`| `/api/sistema/migrar-db` | Ejecutar migración idempotente de esquemas de BD |

---

## 📁 Estructura del Repositorio

```
proyecto_ocr/
├── backend/
│   ├── app/
│   │   ├── main.py                          # Entrada principal FastAPI, middlewares y rutas
│   │   ├── config.py                        # Configuración Pydantic Settings y variables .env
│   │   ├── database.py                      # Conexión SQLAlchemy y DDL de base de datos
│   │   ├── models/                          # Modelos ORM (Usuario, Documento, Persona, Comparacion, Diferencia)
│   │   ├── schemas/                         # Esquemas Pydantic de entrada y salida
│   │   ├── routers/                         # Controladores REST (auth, documentos, personas, comparacion, exportacion)
│   │   ├── services/                        # Capa de lógica y orquestación de negocio
│   │   │   ├── ocr_service.py               # Orquestador del pipeline OCR multi-motor
│   │   │   ├── google_document_ai_service.py # Integración con Google Document AI (gRPC/REST)
│   │   │   ├── rapid_ocr_service.py         # Motor neural local RapidOCR ONNX
│   │   │   ├── spatial_field_extractor.py   # Extracción con geometría espacial 2D
│   │   │   ├── document_side_classifier.py  # Clasificador de cara Frente vs Reverso
│   │   │   ├── document_pairing_service.py  # Emparejador de frentes y reversos
│   │   │   ├── excel_lookup_service.py      # Búsqueda y enriquecimiento de nombres desde Excel
│   │   │   ├── comparacion_service.py       # Conciliación y detección de diferencias
│   │   │   ├── colombia_geo_service.py      # Catálogo geográfico y validación DANE
│   │   │   ├── name_dictionary_service.py   # Diccionario de nombres colombianos comunes
│   │   │   └── exportacion_service.py       # Generador de hojas XLSX estilizadas
│   │   └── utils/                           # Procesador OpenCV, logger y validadores
│   ├── requirements.txt                     # Dependencias Python
│   └── Dockerfile                           # Contenedor del backend
├── frontend/
│   ├── src/
│   │   ├── app/                             # Next.js 14 App Router
│   │   │   ├── page.tsx                     # Login y autenticación
│   │   │   ├── dashboard/                   # Métricas generales y accesos rápidos
│   │   │   ├── documentos/                  # Carga de lotes, progreso en vivo y visor PDF
│   │   │   ├── personas/                    # Tabla global, edición, filtros y subida PDF
│   │   │   ├── comparacion/                 # Módulo interactivo de resolución de diferencias
│   │   │   ├── exportacion/                 # Centro de exportación XLSX
│   │   │   └── usuarios/                    # Gestión de usuarios del sistema
│   │   ├── components/                      # Componentes UI reutilizables
│   │   ├── context/                         # Contextos globales (AuthContext)
│   │   ├── lib/                             # Cliente HTTP y utilidades API
│   │   └── types/                           # Definiciones de tipos TypeScript
│   ├── package.json                         # Dependencias Node.js
│   ├── tailwind.config.ts                   # Configuración de estilos Tailwind
│   └── Dockerfile                           # Contenedor del frontend
├── credentials/                             # Carpeta para Service Account de Google Cloud
├── database/
│   └── init.sql                             # DDL inicial de PostgreSQL
├── docker-compose.yml                       # Orquestación de contenedores
├── .env.example                             # Plantilla de variables de entorno
└── README.md                                # Documentación del proyecto
```

---

## 🎯 Comparativa de Motores OCR Implementados

| Criterio | Google Document AI | RapidOCR ONNX | Tesseract OCR |
|:---------|:------------------:|:-------------:|:-------------:|
| **Rol en el Sistema** | **Principal (Nube)** | **Rescate Neural (Local)** | **Fallback de Emergencia** |
| **Precisión en Cédulas** | ⭐⭐⭐⭐⭐ (98%+) | ⭐⭐⭐⭐ (90-95%) | ⭐⭐⭐ (75-85%) |
| **Coordenadas y Layout 2D** | ✅ Bloques, párrafos y palabras | ✅ Cajas delimitadoras | ⚠️ Básico (HOCR) |
| **Velocidad de Inferencia** | Rápida (Cloud API) | Ultra-rápida (CPU local ONNX) | Media |
| **Requerimientos** | Conexión GCP e ID de Procesador | Ninguno (corre en CPU local) | Binario Tesseract instalado |
| **Capacidad de Fusión** | Base principal de texto | Completa líneas omitidas | Usado si ambos fallan |

---

## 🔒 Seguridad y Buenas Prácticas

- **Cifrado de Contraseñas**: Bcrypt con 12 rondas de salting y compatibilidad passlib.
- **Tokens de Acceso**: JWT firmado con algoritmo HMAC-SHA256 y expiración configurable (por defecto 8 horas).
- **Protección de Datos Multitenant**: Consultas aisladas por `usuario_id` en PostgreSQL para que ningún usuario acceda a documentos o registros de otro.
- **Validación Estricta de Archivos**: Filtro de extensiones `.pdf`, `.xlsx`, `.xls` y tamaño máximo controlado por configuración (`MAX_FILE_SIZE_MB`).
- **Respaldo Persistente**: Copia binaria de los PDFs en la base de datos para garantizar disponibilidad del visor incluso si el almacenamiento efímero se reinicia.
