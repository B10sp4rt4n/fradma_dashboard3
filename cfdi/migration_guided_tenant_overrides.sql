-- =====================================================================
-- Migracion: Rollout por tenant para catalogo guiado
-- Version: 1.0
-- Fecha: 4 mayo 2026
-- =====================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS guided_catalog_tenant_overrides (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    empresa_id UUID NOT NULL,
    domain_key VARCHAR(64) NOT NULL DEFAULT '*',
    case_key VARCHAR(128) NOT NULL DEFAULT '*',
    enabled BOOLEAN NOT NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (empresa_id, domain_key, case_key)
);

CREATE INDEX IF NOT EXISTS idx_gcto_empresa ON guided_catalog_tenant_overrides(empresa_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_gcto_domain_case ON guided_catalog_tenant_overrides(domain_key, case_key, updated_at DESC);
