-- ============================================================
-- SISTEMA OCR - DOCUMENTOS COLOMBIANOS
-- Script de inicialización de base de datos PostgreSQL
-- ============================================================

-- Extensiones
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- Para búsqueda por similitud

-- ============================================================
-- TABLA: usuarios
-- ============================================================
CREATE TABLE IF NOT EXISTS usuarios (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    nombre VARCHAR(200) NOT NULL,
    rol VARCHAR(50) DEFAULT 'usuario' CHECK (rol IN ('admin', 'usuario')),
    activo BOOLEAN DEFAULT TRUE,
    fecha_creacion TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    fecha_actualizacion TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    ultimo_login TIMESTAMP WITH TIME ZONE
);

COMMENT ON TABLE usuarios IS 'Usuarios del sistema con control de acceso';

-- ============================================================
-- TABLA: documentos
-- ============================================================
CREATE TABLE IF NOT EXISTS documentos (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    usuario_id UUID REFERENCES usuarios(id) ON DELETE SET NULL,
    nombre_archivo VARCHAR(500) NOT NULL,
    nombre_original VARCHAR(500) NOT NULL,
    ruta_archivo VARCHAR(1000),
    tamano_bytes BIGINT,
    total_paginas INTEGER DEFAULT 0,
    estado VARCHAR(50) DEFAULT 'pendiente' 
        CHECK (estado IN ('pendiente', 'procesando', 'completado', 'error', 'revision')),
    confianza_ocr DECIMAL(5,2),           -- Porcentaje promedio de confianza 0-100
    mensaje_error TEXT,
    tiempo_procesamiento_ms INTEGER,
    fecha_carga TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    fecha_procesamiento TIMESTAMP WITH TIME ZONE,
    metadatos JSONB DEFAULT '{}'::jsonb   -- Datos adicionales del PDF
);

CREATE INDEX idx_documentos_usuario_id ON documentos(usuario_id);
CREATE INDEX idx_documentos_estado ON documentos(estado);
CREATE INDEX idx_documentos_fecha_carga ON documentos(fecha_carga DESC);

COMMENT ON TABLE documentos IS 'Documentos PDF subidos al sistema';

-- ============================================================
-- TABLA: personas
-- ============================================================
CREATE TABLE IF NOT EXISTS personas (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    documento_id UUID REFERENCES documentos(id) ON DELETE SET NULL,
    numero_identificacion VARCHAR(20) UNIQUE NOT NULL,
    nombres VARCHAR(200),
    apellidos VARCHAR(200),
    fecha_nacimiento DATE,
    fecha_expedicion DATE,
    lugar_expedicion VARCHAR(200),
    sexo VARCHAR(10) CHECK (sexo IN ('M', 'F', 'MASCULINO', 'FEMENINO', NULL)),
    -- Control de calidad de extracción
    confianza_extraccion DECIMAL(5,2),    -- 0-100
    requiere_revision BOOLEAN DEFAULT FALSE,
    campos_revisados JSONB DEFAULT '[]'::jsonb,
    -- Datos crudos del OCR para auditoría
    texto_ocr_crudo TEXT,
    -- Timestamps
    fecha_registro TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    fecha_actualizacion TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_personas_identificacion ON personas(numero_identificacion);
CREATE INDEX idx_personas_documento_id ON personas(documento_id);
CREATE INDEX idx_personas_nombres ON personas USING gin(nombres gin_trgm_ops);
CREATE INDEX idx_personas_apellidos ON personas USING gin(apellidos gin_trgm_ops);
CREATE INDEX idx_personas_requiere_revision ON personas(requiere_revision) WHERE requiere_revision = TRUE;

COMMENT ON TABLE personas IS 'Información personal extraída por OCR de los documentos';

-- ============================================================
-- TABLA: comparaciones
-- ============================================================
CREATE TABLE IF NOT EXISTS comparaciones (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    usuario_id UUID REFERENCES usuarios(id) ON DELETE SET NULL,
    nombre_archivo VARCHAR(500) NOT NULL,
    nombre_original VARCHAR(500) NOT NULL,
    ruta_archivo VARCHAR(1000),
    -- Estadísticas de comparación
    total_registros_bd INTEGER DEFAULT 0,
    total_registros_excel INTEGER DEFAULT 0,
    total_coincidentes INTEGER DEFAULT 0,
    total_diferentes INTEGER DEFAULT 0,
    total_faltantes_bd INTEGER DEFAULT 0,   -- Están en Excel pero no en BD
    total_nuevos_bd INTEGER DEFAULT 0,       -- Están en BD pero no en Excel
    -- Estado
    estado VARCHAR(50) DEFAULT 'pendiente'
        CHECK (estado IN ('pendiente', 'procesando', 'completado', 'error')),
    mensaje_error TEXT,
    -- Timestamps
    fecha_carga TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    fecha_ejecucion TIMESTAMP WITH TIME ZONE,
    tiempo_procesamiento_ms INTEGER
);

CREATE INDEX idx_comparaciones_usuario_id ON comparaciones(usuario_id);
CREATE INDEX idx_comparaciones_fecha ON comparaciones(fecha_carga DESC);

COMMENT ON TABLE comparaciones IS 'Procesos de comparación entre BD y archivos Excel externos';

-- ============================================================
-- TABLA: diferencias
-- ============================================================
CREATE TABLE IF NOT EXISTS diferencias (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    comparacion_id UUID NOT NULL REFERENCES comparaciones(id) ON DELETE CASCADE,
    numero_identificacion VARCHAR(20) NOT NULL,
    campo VARCHAR(100),                   -- Campo donde hay diferencia
    valor_bd TEXT,                        -- Valor en base de datos
    valor_excel TEXT,                     -- Valor en archivo Excel
    tipo_diferencia VARCHAR(20) NOT NULL
        CHECK (tipo_diferencia IN ('igual', 'diferente', 'faltante_bd', 'nuevo_bd')),
    fecha_registro TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_diferencias_comparacion_id ON diferencias(comparacion_id);
CREATE INDEX idx_diferencias_identificacion ON diferencias(numero_identificacion);
CREATE INDEX idx_diferencias_tipo ON diferencias(tipo_diferencia);

COMMENT ON TABLE diferencias IS 'Detalle de inconsistencias encontradas en comparaciones';

-- ============================================================
-- FUNCIÓN: Actualizar timestamp automáticamente
-- ============================================================
CREATE OR REPLACE FUNCTION actualizar_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.fecha_actualizacion = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers para actualización automática
CREATE TRIGGER trigger_usuarios_timestamp
    BEFORE UPDATE ON usuarios
    FOR EACH ROW EXECUTE FUNCTION actualizar_timestamp();

CREATE TRIGGER trigger_personas_timestamp
    BEFORE UPDATE ON personas
    FOR EACH ROW EXECUTE FUNCTION actualizar_timestamp();

-- ============================================================
-- DATOS INICIALES: Usuario administrador
-- ============================================================
-- Contraseña: Admin123! (hash bcrypt generado)
INSERT INTO usuarios (email, password_hash, nombre, rol) 
VALUES (
    'admin@ocr.com',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj4J/8eSiGHi',
    'Administrador Sistema',
    'admin'
) ON CONFLICT (email) DO NOTHING;

-- ============================================================
-- VISTA: Resumen de documentos con personas
-- ============================================================
CREATE OR REPLACE VIEW vista_resumen_documentos AS
SELECT 
    d.id,
    d.nombre_original,
    d.estado,
    d.confianza_ocr,
    d.fecha_carga,
    d.fecha_procesamiento,
    u.nombre AS usuario_nombre,
    u.email AS usuario_email,
    COUNT(p.id) AS total_personas,
    SUM(CASE WHEN p.requiere_revision THEN 1 ELSE 0 END) AS personas_en_revision
FROM documentos d
LEFT JOIN usuarios u ON d.usuario_id = u.id
LEFT JOIN personas p ON p.documento_id = d.id
GROUP BY d.id, u.id;

-- ============================================================
-- VISTA: Estadísticas del dashboard
-- ============================================================
CREATE OR REPLACE VIEW vista_estadisticas AS
SELECT
    (SELECT COUNT(*) FROM documentos) AS total_documentos,
    (SELECT COUNT(*) FROM documentos WHERE estado = 'completado') AS documentos_completados,
    (SELECT COUNT(*) FROM documentos WHERE estado = 'error') AS documentos_con_error,
    (SELECT COUNT(*) FROM personas) AS total_personas,
    (SELECT COUNT(*) FROM personas WHERE requiere_revision = TRUE) AS personas_revision,
    (SELECT COUNT(*) FROM comparaciones) AS total_comparaciones,
    (SELECT COALESCE(AVG(confianza_ocr), 0) FROM documentos WHERE confianza_ocr IS NOT NULL) AS confianza_promedio;
