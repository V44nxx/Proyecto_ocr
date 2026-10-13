-- ==============================================================================
-- SISTEMA OCR DOCUMENTAL - DIAGRAMA RELACIONAL DE BASE DE DATOS (drawDB)
-- Motor: PostgreSQL
-- Para importar en drawDB:
-- 1. Ve a https://drawdb.app
-- 2. Haz clic en "Import" en la barra superior o menú
-- 3. Selecciona "Import SQL" (o dialecto PostgreSQL)
-- 4. Pega este contenido completo y confirma
-- ==============================================================================

-- 1. TABLA: usuarios
CREATE TABLE usuarios (
    id UUID PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    nombre VARCHAR(200) NOT NULL,
    rol VARCHAR(50) DEFAULT 'usuario',
    activo BOOLEAN DEFAULT TRUE,
    fecha_creacion TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    fecha_actualizacion TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    ultimo_login TIMESTAMP WITH TIME ZONE
);

-- 2. TABLA: documentos
CREATE TABLE documentos (
    id UUID PRIMARY KEY,
    usuario_id UUID,
    nombre_archivo VARCHAR(500) NOT NULL,
    nombre_original VARCHAR(500) NOT NULL,
    ruta_archivo VARCHAR(1000),
    tamano_bytes BIGINT,
    total_paginas INTEGER DEFAULT 0,
    estado VARCHAR(50) DEFAULT 'pendiente',
    confianza_ocr NUMERIC(5, 2),
    mensaje_error TEXT,
    tiempo_procesamiento_ms INTEGER,
    fecha_carga TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    fecha_procesamiento TIMESTAMP WITH TIME ZONE,
    metadatos JSONB DEFAULT '{}',
    visible_en_subida BOOLEAN DEFAULT TRUE,
    archivo_binario BYTEA,
    CONSTRAINT fk_documentos_usuario
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
        ON DELETE SET NULL
);

-- 3. TABLA: personas
CREATE TABLE personas (
    id UUID PRIMARY KEY,
    documento_id UUID,
    documento_pdf_id UUID,
    usuario_id UUID,
    numero_identificacion VARCHAR(20) NOT NULL,
    nombre_completo VARCHAR(400),
    nombres VARCHAR(200),
    apellidos VARCHAR(200),
    fecha_nacimiento DATE,
    fecha_expedicion DATE,
    lugar_expedicion VARCHAR(200),
    sexo VARCHAR(10),
    grupo_documento_id VARCHAR(100),
    pagina_frente INTEGER,
    pagina_reverso INTEGER,
    pagina_numero INTEGER,
    tipo_documento VARCHAR(50) DEFAULT 'CEDULA_CIUDADANIA',
    estado_registro VARCHAR(30) DEFAULT 'VALID',
    motor_ocr VARCHAR(50) DEFAULT 'google_document_ai',
    confianza_extraccion NUMERIC(5, 2),
    requiere_revision BOOLEAN DEFAULT FALSE,
    campos_revisados JSONB DEFAULT '[]',
    detalles_campos JSONB,
    texto_ocr_crudo TEXT,
    fecha_registro TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    fecha_actualizacion TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_personas_documento
        FOREIGN KEY (documento_id) REFERENCES documentos(id)
        ON DELETE SET NULL,
    CONSTRAINT fk_personas_documento_pdf
        FOREIGN KEY (documento_pdf_id) REFERENCES documentos(id)
        ON DELETE SET NULL,
    CONSTRAINT fk_personas_usuario
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
        ON DELETE CASCADE
);

-- 4. TABLA: comparaciones
CREATE TABLE comparaciones (
    id UUID PRIMARY KEY,
    usuario_id UUID,
    nombre_archivo VARCHAR(500) NOT NULL,
    nombre_original VARCHAR(500) NOT NULL,
    ruta_archivo VARCHAR(1000),
    archivo_binario BYTEA,
    total_registros_bd INTEGER DEFAULT 0,
    total_registros_excel INTEGER DEFAULT 0,
    total_coincidentes INTEGER DEFAULT 0,
    total_diferentes INTEGER DEFAULT 0,
    total_faltantes_bd INTEGER DEFAULT 0,
    total_nuevos_bd INTEGER DEFAULT 0,
    estado VARCHAR(50) DEFAULT 'pendiente',
    mensaje_error TEXT,
    fecha_carga TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    fecha_ejecucion TIMESTAMP WITH TIME ZONE,
    tiempo_procesamiento_ms INTEGER,
    CONSTRAINT fk_comparaciones_usuario
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
        ON DELETE SET NULL
);

-- 5. TABLA: diferencias
CREATE TABLE diferencias (
    id UUID PRIMARY KEY,
    comparacion_id UUID NOT NULL,
    numero_identificacion VARCHAR(20) NOT NULL,
    campo VARCHAR(100),
    valor_bd TEXT,
    valor_excel TEXT,
    tipo_diferencia VARCHAR(20) NOT NULL,
    fecha_registro TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_diferencias_comparacion
        FOREIGN KEY (comparacion_id) REFERENCES comparaciones(id)
        ON DELETE CASCADE
);

-- ÍNDICES PRINCIPALES
CREATE INDEX ix_usuarios_email ON usuarios (email);
CREATE INDEX ix_documentos_usuario_id ON documentos (usuario_id);
CREATE INDEX ix_documentos_estado ON documentos (estado);
CREATE INDEX ix_personas_documento_id ON personas (documento_id);
CREATE INDEX ix_personas_usuario_id ON personas (usuario_id);
CREATE INDEX ix_personas_numero_identificacion ON personas (numero_identificacion);
CREATE INDEX ix_personas_nombre_completo ON personas (nombre_completo);
CREATE INDEX ix_comparaciones_usuario_id ON comparaciones (usuario_id);
CREATE INDEX ix_diferencias_comparacion_id ON diferencias (comparacion_id);
CREATE INDEX ix_diferencias_numero_identificacion ON diferencias (numero_identificacion);
