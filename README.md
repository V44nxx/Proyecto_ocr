# 🔍 Sistema OCR - Documentos de Identificación Colombianos

Plataforma profesional para extracción automática de información desde documentos PDF usando **PaddleOCR**, con almacenamiento en PostgreSQL, exportación Excel y módulo de comparación de datos.

---

## 🏗️ Arquitectura

```
┌─────────────────────────────────────────────────────┐
│                   CLIENTE (Browser)                  │
│              Next.js 14 + TypeScript                 │
│                   localhost:3000                      │
└────────────────────┬────────────────────────────────┘
                     │ HTTP/REST
┌────────────────────▼────────────────────────────────┐
│              FastAPI Backend (Python 3.12)           │
│         PaddleOCR · OpenCV · Pandas · JWT            │
│                   localhost:8000                      │
└────────────────────┬────────────────────────────────┘
                     │ SQLAlchemy
┌────────────────────▼────────────────────────────────┐
│               PostgreSQL 16                          │
│   usuarios · documentos · personas                   │
│   comparaciones · diferencias                        │
│                   localhost:5432                      │
└─────────────────────────────────────────────────────┘
```

---

## ⚡ Inicio Rápido (Docker Compose)

### Prerrequisitos
- Docker Desktop instalado y corriendo
- Git

### 1. Clonar y configurar

```bash
cd c:\xampp\htdocs\proyecto_ocr

# Copiar configuración de entorno
copy .env.example .env

# Editar .env si necesitas cambiar contraseñas (opcional)
notepad .env
```

### 2. Levantar todo el sistema

```bash
docker-compose up -d
```

Esto levanta automáticamente:
- **PostgreSQL** en puerto `5432` (con la BD inicializada)
- **Backend FastAPI** en puerto `8000`
- **Frontend Next.js** en puerto `3000`
- **pgAdmin** en puerto `5050`

### 3. Verificar que todo funciona

```bash
# Ver logs
docker-compose logs -f

# Ver estado de contenedores
docker-compose ps
```

### 4. Acceder al sistema

| Servicio | URL | Credenciales |
|---------|-----|-------------|
| **Frontend** | http://localhost:3000 | admin@ocr.com / Admin123! |
| **API Docs (Swagger)** | http://localhost:8000/docs | — |
| **pgAdmin** | http://localhost:5050 | admin@ocr.com / admin123 |

---

## 🖥️ Desarrollo Local (Sin Docker)

### Backend

```bash
cd backend

# Crear entorno virtual
python -m venv venv
venv\Scripts\activate          # Windows

# Instalar dependencias
pip install -r requirements.txt

# Configurar variables de entorno
copy ..\\.env.example .env
# Editar DATABASE_URL para apuntar a tu PostgreSQL local

# Iniciar servidor
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend

# Instalar dependencias
npm install

# Configurar
copy ..\\.env.example .env.local
# NEXT_PUBLIC_API_URL=http://localhost:8000

# Iniciar servidor de desarrollo
npm run dev
```

---

## 📊 Flujo de Procesamiento OCR

```
PDF subido
    ↓
Validación (tamaño, formato)
    ↓
PyMuPDF → Imagen(es) a 300 DPI
    ↓
Pipeline OpenCV:
  ① Escala de grises
  ② Corrección de inclinación (deskew)
  ③ Eliminación de ruido (fastNlMeansDenoising)
  ④ Contraste CLAHE
  ⑤ Umbralización adaptativa
    ↓
PaddleOCR (lang=es, angle_cls=True)
    ↓
Texto crudo + coordenadas + scores
    ↓
Extractor Inteligente:
  ① Normalización de texto
  ② Corrección errores OCR (O→0, l→1, B→8)
  ③ Regex para cédula (6-12 dígitos)
  ④ Detección por contexto (palabras clave)
  ⑤ Validación de campos
    ↓
Score de confianza global
    ↓
Si confianza < 70% → marcar para revisión
    ↓
Guardar en PostgreSQL
```

---

## 🔌 API Endpoints

### Autenticación
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/api/auth/login` | Login, retorna JWT |
| POST | `/api/auth/register` | Registrar usuario |
| GET | `/api/auth/me` | Perfil actual |

### Documentos
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/api/documentos/upload` | Subir PDF(s) |
| GET | `/api/documentos` | Listar documentos |
| GET | `/api/documentos/{id}` | Detalle |
| GET | `/api/documentos/{id}/estado` | Estado OCR en tiempo real |
| DELETE | `/api/documentos/{id}` | Eliminar |
| GET | `/api/documentos/dashboard/estadisticas` | Stats del dashboard |

### Personas
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/api/personas` | Listar con filtros |
| GET | `/api/personas/{id}` | Detalle |
| PUT | `/api/personas/{id}` | Corrección manual |
| DELETE | `/api/personas/{id}` | Eliminar |
| GET | `/api/personas/buscar/cedula/{cedula}` | Buscar por cédula |

### Exportación
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/api/exportacion/xlsx` | Descargar XLSX formateado |

### Comparación
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/api/comparacion/upload` | Subir Excel externo |
| POST | `/api/comparacion/{id}/ejecutar` | Ejecutar comparación |
| GET | `/api/comparacion` | Historial |
| GET | `/api/comparacion/{id}` | Detalle y estadísticas |
| GET | `/api/comparacion/{id}/diferencias` | Diferencias por tipo |
| GET | `/api/comparacion/{id}/reporte` | Descargar reporte XLSX |

---

## 📁 Estructura del Proyecto

```
proyecto_ocr/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI entry point
│   │   ├── config.py            # Configuración global
│   │   ├── database.py          # SQLAlchemy setup
│   │   ├── models/              # ORM models
│   │   ├── schemas/             # Pydantic schemas
│   │   ├── routers/             # Endpoints FastAPI
│   │   ├── services/            # Lógica de negocio
│   │   └── utils/               # Utilidades
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── app/                 # Pages (Next.js App Router)
│   │   ├── components/          # Componentes reutilizables
│   │   ├── lib/                 # API client + Auth
│   │   └── types/               # TypeScript types
│   ├── tailwind.config.ts
│   └── Dockerfile
├── database/
│   └── init.sql                 # Scripts de inicialización
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## 🎯 Por qué PaddleOCR

| Motor | Precisión | Español | Velocidad | Documentos escaneados |
|-------|-----------|---------|-----------|----------------------|
| **PaddleOCR** | ⭐⭐⭐⭐⭐ | ✅ | ⭐⭐⭐⭐ | ✅ Excelente |
| EasyOCR | ⭐⭐⭐⭐ | ✅ | ⭐⭐⭐ | ✅ Bueno |
| Tesseract | ⭐⭐⭐ | ✅ | ⭐⭐⭐⭐⭐ | ⚠️ Básico |

PaddleOCR usa modelos de deep learning (DB para detección + SVTR_LCNet para reconocimiento) con soporte de detección de orientación, superando a los alternativas en documentos de baja calidad.

---

## 🛠️ Comandos Útiles

```bash
# Reiniciar solo el backend
docker-compose restart backend

# Ver logs del backend
docker-compose logs -f backend

# Reconstruir después de cambios en código
docker-compose up -d --build backend

# Conectar a PostgreSQL
docker exec -it ocr_postgres psql -U ocr_user -d ocr_documentos

# Detener todo
docker-compose down

# Detener y eliminar datos (CUIDADO)
docker-compose down -v
```

---

## 🔒 Seguridad

- Autenticación JWT con expiración de 8 horas
- Contraseñas hasheadas con bcrypt (12 rounds)
- CORS configurado para origenes permitidos
- Validación de tipos de archivo en uploads
- Validación de tamaño máximo de archivos
- Usuarios con roles (admin/usuario)

---

## 📈 Precisión Objetivo: >95%

La precisión se logra mediante:
1. **300 DPI** en conversión PDF→imagen
2. **Pipeline OpenCV**: deskew + denoise + CLAHE + threshold
3. **PaddleOCR** con modo de detección lento (mayor precisión)
4. **Extracción inteligente**: múltiples estrategias de detección
5. **Corrección de errores OCR**: O→0, l→1, B→8, S→5
6. **Revisión manual**: registros con confianza <70% marcados automáticamente
