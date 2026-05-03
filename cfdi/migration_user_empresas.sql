-- =====================================================================
-- Migración: Tabla user_empresas (many-to-many usuario ↔ empresa)
-- Versión: 1.1
-- Fecha: 24 marzo 2026
-- Ejecutar UNA VEZ en Neon PostgreSQL
-- =====================================================================

-- 1. Crear tabla de relación N:N
CREATE TABLE IF NOT EXISTS user_empresas (
    username    VARCHAR(50) NOT NULL REFERENCES users(username) ON DELETE CASCADE,
    empresa_id  UUID        NOT NULL REFERENCES empresas(id)    ON DELETE CASCADE,
    role        VARCHAR(20) NOT NULL DEFAULT 'viewer',  -- rol dentro de ESTE tenant
    granted_by  VARCHAR(50),
    granted_at  TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (username, empresa_id)
);

CREATE INDEX IF NOT EXISTS idx_ue_username  ON user_empresas(username);
CREATE INDEX IF NOT EXISTS idx_ue_empresa   ON user_empresas(empresa_id);

-- 2. Poblar con las relaciones ya existentes en users.empresa_id
INSERT INTO user_empresas (username, empresa_id, role, granted_by)
SELECT u.username, u.empresa_id, u.role, 'migration'
FROM   users u
WHERE  u.empresa_id IS NOT NULL
ON CONFLICT (username, empresa_id) DO NOTHING;

-- 3. Verificación rápida
SELECT
    u.username,
    e.rfc,
    e.razon_social,
    ue.role
FROM user_empresas ue
JOIN users    u ON u.username  = ue.username
JOIN empresas e ON e.id        = ue.empresa_id
ORDER BY e.rfc, u.username;
