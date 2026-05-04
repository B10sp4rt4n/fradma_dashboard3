-- =====================================================================
-- Migración: Catálogo guiado de consultas (Asistente sin NL)
-- Versión: 1.0
-- Fecha: 4 mayo 2026
-- =====================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS guided_catalog_versions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    version VARCHAR(32) NOT NULL,
    source VARCHAR(20) NOT NULL DEFAULT 'json',
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (version)
);

CREATE TABLE IF NOT EXISTS guided_catalog_domains (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    version_id UUID NOT NULL REFERENCES guided_catalog_versions(id) ON DELETE CASCADE,
    domain_key VARCHAR(64) NOT NULL,
    label VARCHAR(128) NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (version_id, domain_key)
);

CREATE TABLE IF NOT EXISTS guided_catalog_cases (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    version_id UUID NOT NULL REFERENCES guided_catalog_versions(id) ON DELETE CASCADE,
    domain_key VARCHAR(64) NOT NULL,
    case_key VARCHAR(128) NOT NULL,
    label VARCHAR(160) NOT NULL,
    description TEXT,
    sql_template_id VARCHAR(128) NOT NULL,
    default_chart VARCHAR(32) NOT NULL DEFAULT 'table',
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    tables_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    filters_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    groupings_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (version_id, case_key)
);

CREATE INDEX IF NOT EXISTS idx_gcv_active ON guided_catalog_versions(is_active);
CREATE INDEX IF NOT EXISTS idx_gcd_version ON guided_catalog_domains(version_id, sort_order);
CREATE INDEX IF NOT EXISTS idx_gcc_version ON guided_catalog_cases(version_id, domain_key, sort_order);

-- Regla: solo una versión activa a la vez.
CREATE UNIQUE INDEX IF NOT EXISTS uq_guided_catalog_single_active
ON guided_catalog_versions ((is_active))
WHERE is_active = TRUE;
