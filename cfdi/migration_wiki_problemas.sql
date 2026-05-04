-- ============================================================
-- Wiki de Problemas Resueltos — schema wiki
-- Motor: PostgreSQL 17 (Neon), fulltext español
-- ============================================================

CREATE SCHEMA IF NOT EXISTS wiki;

-- Tabla principal de problemas
CREATE TABLE IF NOT EXISTS wiki.problema (
    id          SERIAL PRIMARY KEY,
    codigo      VARCHAR(20) UNIQUE NOT NULL,          -- #001, #002...
    titulo      TEXT NOT NULL,
    modulo      TEXT,                                  -- archivo fuente
    sintoma     TEXT,                                  -- qué veía el usuario
    causa_raiz  TEXT,                                  -- por qué pasaba
    solucion    TEXT,                                  -- cómo se resolvió
    intentos    JSONB DEFAULT '[]'::jsonb,             -- [{intento, por_que_fallo}]
    leccion     TEXT,                                  -- aprendizaje clave
    tags        TEXT[] DEFAULT '{}',                   -- ['streamlit','dtype','sort']
    resuelto    BOOLEAN DEFAULT TRUE,
    fecha       DATE DEFAULT CURRENT_DATE,
    creado_en   TIMESTAMPTZ DEFAULT NOW(),
    -- columna fulltext combinada (se actualiza por trigger)
    fts         TSVECTOR
);

-- Función que regenera el vector fulltext
CREATE OR REPLACE FUNCTION wiki.problema_fts_update()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.fts :=
        setweight(to_tsvector('spanish', COALESCE(NEW.titulo, '')),    'A') ||
        setweight(to_tsvector('spanish', COALESCE(NEW.sintoma, '')),   'B') ||
        setweight(to_tsvector('spanish', COALESCE(NEW.causa_raiz, '')), 'C') ||
        setweight(to_tsvector('spanish', COALESCE(NEW.solucion, '')),  'C') ||
        setweight(to_tsvector('spanish', COALESCE(NEW.leccion, '')),   'D') ||
        setweight(to_tsvector('simple',  COALESCE(array_to_string(NEW.tags, ' '), '')), 'A');
    RETURN NEW;
END;
$$;

-- Trigger para INSERT y UPDATE
DROP TRIGGER IF EXISTS trg_problema_fts ON wiki.problema;
CREATE TRIGGER trg_problema_fts
    BEFORE INSERT OR UPDATE ON wiki.problema
    FOR EACH ROW EXECUTE FUNCTION wiki.problema_fts_update();

-- Índice GIN para búsqueda fulltext rápida
CREATE INDEX IF NOT EXISTS idx_problema_fts   ON wiki.problema USING GIN(fts);
CREATE INDEX IF NOT EXISTS idx_problema_tags  ON wiki.problema USING GIN(tags);
CREATE INDEX IF NOT EXISTS idx_problema_modulo ON wiki.problema(modulo);
CREATE INDEX IF NOT EXISTS idx_problema_fecha  ON wiki.problema(fecha DESC);
