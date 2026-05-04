-- =====================================================================
-- Migracion: Metricas de uso para casos guiados
-- Version: 1.0
-- Fecha: 4 mayo 2026
-- =====================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS guided_case_usage_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    empresa_id UUID NULL,
    user_email VARCHAR(255) NULL,
    domain_key VARCHAR(64) NOT NULL,
    case_key VARCHAR(128) NOT NULL,
    success BOOLEAN NOT NULL DEFAULT TRUE,
    execution_time_sec NUMERIC(12, 4) NULL,
    row_count INTEGER NULL,
    source VARCHAR(32) NOT NULL DEFAULT 'streamlit'
);

CREATE INDEX IF NOT EXISTS idx_guided_usage_created_at ON guided_case_usage_events(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_guided_usage_case ON guided_case_usage_events(case_key, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_guided_usage_domain ON guided_case_usage_events(domain_key, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_guided_usage_empresa ON guided_case_usage_events(empresa_id, created_at DESC);
