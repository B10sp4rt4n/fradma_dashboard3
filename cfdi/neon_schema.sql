-- =====================================================================
-- Schema de Base de Datos Neon PostgreSQL para Fradma Dashboard
-- Versión: 1.0
-- Fecha: 26 febrero 2026
-- =====================================================================

-- Extensiones necesarias
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm"; -- Para búsqueda full-text

-- =====================================================================
-- TABLA: empresas
-- Registro de clientes de Fradma
-- =====================================================================
CREATE TABLE empresas (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    razon_social VARCHAR(255) NOT NULL,
    rfc VARCHAR(13) UNIQUE NOT NULL,
    email VARCHAR(255),
    telefono VARCHAR(20),
    
    -- Metadata
    plan VARCHAR(50) DEFAULT 'essential', -- essential, business, enterprise
    fecha_registro TIMESTAMP DEFAULT NOW(),
    status VARCHAR(20) DEFAULT 'activo', -- activo, suspendido, cancelado
    
    -- Clasificación para benchmarks
    industria VARCHAR(100), -- distribucion_ferreteria, manufactura_plasticos, etc.
    tamaño_empresa VARCHAR(20), -- 10-50, 50-200, 200-500
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Índices
CREATE INDEX idx_empresas_rfc ON empresas(rfc);
CREATE INDEX idx_empresas_industria ON empresas(industria);


-- =====================================================================
-- TABLA: cfdi_ventas
-- CFDIs de venta emitidos por la empresa cliente
-- =====================================================================
CREATE TABLE cfdi_ventas (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    empresa_id UUID NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    
    -- Identificadores oficiales
    uuid_sat VARCHAR(36) UNIQUE NOT NULL, -- UUID del timbre fiscal
    serie VARCHAR(25),
    folio VARCHAR(40),
    
    -- Fechas
    fecha_emision TIMESTAMP NOT NULL,
    fecha_timbrado TIMESTAMP NOT NULL,
    
    -- Emisor (el cliente de Fradma)
    emisor_rfc VARCHAR(13) NOT NULL,
    emisor_nombre VARCHAR(255),
    emisor_regimen_fiscal VARCHAR(3),
    
    -- Receptor (el cliente del cliente - end customer)
    receptor_rfc VARCHAR(13) NOT NULL,
    receptor_nombre VARCHAR(255),
    receptor_uso_cfdi VARCHAR(4), -- G03, S01, etc.
    receptor_domicilio_fiscal VARCHAR(5),
    receptor_regimen_fiscal VARCHAR(3),
    
    -- Montos
    subtotal DECIMAL(15,2) NOT NULL,
    descuento DECIMAL(15,2) DEFAULT 0,
    impuestos DECIMAL(15,2) DEFAULT 0,
    total DECIMAL(15,2) NOT NULL,
    
    -- Moneda y tipo de cambio
    moneda VARCHAR(3) DEFAULT 'MXN', -- MXN, USD, EUR
    tipo_cambio DECIMAL(10,4) DEFAULT 1.0000,
    
    -- Metadata fiscal
    tipo_comprobante VARCHAR(1) DEFAULT 'I', -- I=Ingreso, E=Egreso, etc.
    metodo_pago VARCHAR(3), -- PUE, PPD
    forma_pago VARCHAR(2), -- 01=Efectivo, 03=Transferencia, etc.
    lugar_expedicion VARCHAR(5),
    
    -- Enriquecimiento automático (calculado post-ingesta)
    linea_negocio VARCHAR(100), -- Clasificado por IA
    vendedor_asignado VARCHAR(100), -- Extraído de notas o manual
    es_exportacion BOOLEAN DEFAULT FALSE,
    
    -- Almacenamiento XML completo para auditoría
    xml_original TEXT,

    -- Estatus fiscal del CFDI
    estatus VARCHAR(20) DEFAULT 'vigente' CHECK (estatus IN ('vigente', 'cancelado')),

    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Índices de performance
CREATE INDEX idx_cfdi_ventas_empresa ON cfdi_ventas(empresa_id);
CREATE INDEX idx_cfdi_ventas_uuid ON cfdi_ventas(uuid_sat);
CREATE INDEX idx_cfdi_ventas_fecha_emision ON cfdi_ventas(fecha_emision DESC);
CREATE INDEX idx_cfdi_ventas_receptor ON cfdi_ventas(receptor_rfc);
CREATE INDEX idx_cfdi_ventas_linea ON cfdi_ventas(linea_negocio);
CREATE INDEX idx_cfdi_ventas_metodo_pago ON cfdi_ventas(metodo_pago);


-- =====================================================================
-- TABLA: cfdi_conceptos
-- Líneas de productos/servicios dentro de cada CFDI
-- =====================================================================
CREATE TABLE cfdi_conceptos (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    cfdi_venta_id UUID NOT NULL REFERENCES cfdi_ventas(id) ON DELETE CASCADE,
    
    -- Identificación del producto/servicio
    clave_prod_serv VARCHAR(8) NOT NULL, -- Clave SAT
    no_identificacion VARCHAR(100), -- SKU o código interno
    descripcion TEXT NOT NULL,
    
    -- Cantidades y unidades
    cantidad DECIMAL(15,4) NOT NULL,
    clave_unidad VARCHAR(3), -- H87, E48, etc.
    unidad VARCHAR(20), -- Pieza, Kilo, etc.
    
    -- Precios
    valor_unitario DECIMAL(15,4) NOT NULL,
    importe DECIMAL(15,2) NOT NULL,
    descuento DECIMAL(15,2) DEFAULT 0,
    
    -- Impuestos
    objeto_imp VARCHAR(2) DEFAULT '02', -- 01=No objeto, 02=Sí objeto, etc.
    
    -- Enriquecimiento
    categoria VARCHAR(100), -- Clasificado por IA
    
    created_at TIMESTAMP DEFAULT NOW()
);

-- Índices
CREATE INDEX idx_conceptos_cfdi ON cfdi_conceptos(cfdi_venta_id);
CREATE INDEX idx_conceptos_clave ON cfdi_conceptos(clave_prod_serv);
CREATE INDEX idx_conceptos_categoria ON cfdi_conceptos(categoria);


-- =====================================================================
-- =====================================================================
-- TABLA: cfdi_pagos
-- Complementos de pago (tracking de cobranza)
-- 
-- IMPORTANTE - CONCILIACIÓN DE DATOS:
-- Esta tabla registra los PAGOS recibidos que se relacionan con facturas.
-- Escenarios posibles durante la carga de datos:
-- 
-- 1. COMPLEMENTO HUÉRFANO (hay pago pero NO factura en BD):
--    - cfdi_venta_uuid apunta a un UUID que no existe en cfdi_ventas
--    - Causa: La factura aún no se ha cargado en la BD
--    - Acción: NO incluir en análisis de cobranza (usar INNER JOIN)
--    - Detectar con: LEFT JOIN cfdi_ventas WHERE cfdi_ventas.uuid_sat IS NULL
--
-- 2. FACTURA SIN COMPLEMENTO (hay factura pero NO pago registrado):
--    - Factura existe pero no tiene cfdi_pagos relacionado
--    - Causa A: Realmente está pendiente de cobro
--    - Causa B: Ya se pagó pero el complemento no está cargado aún
--    - Acción: Marcar como "Pendiente de conciliar" (no asumir impago)
--    - Flag: estado_conciliacion en v_cartera_clientes
--
-- REGLA CRÍTICA: NUNCA sumar cfdi_ventas.total + cfdi_pagos.monto_pagado
-- Son eventos distintos: factura = origen de venta, pago = cobranza recibida
-- =====================================================================
CREATE TABLE cfdi_pagos (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    empresa_id UUID NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    
    -- Identificación del complemento
    uuid_complemento VARCHAR(36) UNIQUE NOT NULL,
    
    -- Relación con factura original
    cfdi_venta_uuid VARCHAR(36) REFERENCES cfdi_ventas(uuid_sat),
    serie VARCHAR(25),
    folio VARCHAR(40),
    
    -- Detalle del pago
    fecha_pago TIMESTAMP NOT NULL,
    forma_pago VARCHAR(2), -- 01=Efectivo, 03=Transferencia, etc.
    moneda VARCHAR(3) DEFAULT 'MXN',
    tipo_cambio DECIMAL(10,4) DEFAULT 1.0000,
    monto_pagado DECIMAL(15,2) NOT NULL,
    
    -- Saldos
    saldo_anterior DECIMAL(15,2),
    saldo_insoluto DECIMAL(15,2),
    num_parcialidad INTEGER DEFAULT 1,
    
    -- Métricas calculadas
    dias_credito INTEGER, -- fecha_pago - fecha_emision_factura
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Índices
CREATE INDEX idx_pagos_empresa ON cfdi_pagos(empresa_id);
CREATE INDEX idx_pagos_uuid ON cfdi_pagos(uuid_complemento);
CREATE INDEX idx_pagos_venta ON cfdi_pagos(cfdi_venta_uuid);
CREATE INDEX idx_pagos_fecha ON cfdi_pagos(fecha_pago DESC);


-- =====================================================================
-- TABLA: clientes_master
-- Catálogo maestro de clientes (deduplicado y enriquecido)
-- =====================================================================
CREATE TABLE clientes_master (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    empresa_id UUID NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    
    -- Identificación
    rfc VARCHAR(13) NOT NULL,
    razon_social VARCHAR(255) NOT NULL,
    nombre_comercial VARCHAR(255),
    
    -- Datos de contacto
    email VARCHAR(255),
    telefono VARCHAR(20),
    domicilio_fiscal VARCHAR(5),
    
    -- Clasificación
    tipo_cliente VARCHAR(50), -- distribuidor, minorista, mayorista, gobierno
    industria VARCHAR(100),
    segmento VARCHAR(50), -- A, B, C (por volumen)
    
    -- Métricas agregadas (recalculadas periódicamente)
    total_ventas_historico DECIMAL(15,2) DEFAULT 0,
    total_facturas INTEGER DEFAULT 0,
    dias_credito_promedio INTEGER,
    score_crediticio DECIMAL(5,2), -- 0-100
    
    -- Metadata
    fecha_primera_venta TIMESTAMP,
    fecha_ultima_venta TIMESTAMP,
    is_activo BOOLEAN DEFAULT TRUE,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(empresa_id, rfc)
);

-- Índices
CREATE INDEX idx_clientes_empresa ON clientes_master(empresa_id);
CREATE INDEX idx_clientes_rfc ON clientes_master(rfc);
CREATE INDEX idx_clientes_segmento ON clientes_master(segmento);


-- =====================================================================
-- TABLA: benchmarks_industria
-- Métricas agregadas y anonimizadas para comparación sectorial
-- =====================================================================
CREATE TABLE benchmarks_industria (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Segmentación
    industria VARCHAR(100) NOT NULL, -- distribucion_ferreteria, etc.
    tamaño_empresa VARCHAR(20) NOT NULL, -- 10-50, 50-200
    pais VARCHAR(2) DEFAULT 'MX',
    
    -- Métrica
    metrica VARCHAR(50) NOT NULL, -- dso_promedio, score_cxc_promedio, etc.
    valor DECIMAL(10,2) NOT NULL,
    unidad VARCHAR(20), -- dias, porcentaje, pesos
    
    -- Estadísticas
    n_empresas INTEGER NOT NULL, -- Cuántas empresas contribuyen (para confiabilidad)
    percentil_25 DECIMAL(10,2),
    percentil_50 DECIMAL(10,2), -- mediana
    percentil_75 DECIMAL(10,2),
    
    -- Periodo
    periodo DATE NOT NULL, -- Mes de cálculo: 2026-02-01
    
    created_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(industria, tamaño_empresa, metrica, periodo)
);

-- Índices
CREATE INDEX idx_benchmarks_industria ON benchmarks_industria(industria, tamaño_empresa);
CREATE INDEX idx_benchmarks_metrica ON benchmarks_industria(metrica);
CREATE INDEX idx_benchmarks_periodo ON benchmarks_industria(periodo DESC);


-- =====================================================================
-- FUNCIONES Y TRIGGERS
-- =====================================================================

-- Trigger para actualizar updated_at automáticamente
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_empresas_updated_at BEFORE UPDATE ON empresas
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_cfdi_ventas_updated_at BEFORE UPDATE ON cfdi_ventas
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_cfdi_pagos_updated_at BEFORE UPDATE ON cfdi_pagos
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_clientes_master_updated_at BEFORE UPDATE ON clientes_master
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();


-- =====================================================================
-- VISTAS ÚTILES
-- =====================================================================

-- Vista: Resumen de cartera por cliente (CxC) con flags de conciliación
-- IMPORTANTE: Esta vista maneja el caso donde la BD tiene datos incompletos:
-- - Facturas sin complemento pueden estar realmente pendientes O ya pagadas sin complemento registrado
-- - Complementos huérfanos (sin factura) se excluyen automáticamente con LEFT JOIN
CREATE OR REPLACE VIEW v_cartera_clientes AS
SELECT 
    v.empresa_id,
    v.receptor_rfc,
    v.receptor_nombre,
    COUNT(DISTINCT v.uuid_sat) AS num_facturas,
    SUM(v.total * v.tipo_cambio) AS total_facturado,
    COALESCE(SUM(p.monto_pagado), 0) AS total_cobrado,
    SUM(v.total * v.tipo_cambio) - COALESCE(SUM(p.monto_pagado), 0) AS saldo_pendiente,
    
    -- Flags de conciliación
    COUNT(p.uuid_complemento) AS facturas_con_complemento,
    COUNT(DISTINCT v.uuid_sat) - COUNT(p.uuid_complemento) AS facturas_sin_conciliar,
    CASE 
        WHEN COUNT(p.uuid_complemento) = 0 THEN 'sin_complementos'
        WHEN COUNT(p.uuid_complemento) < COUNT(DISTINCT v.uuid_sat) THEN 'conciliacion_parcial'
        ELSE 'conciliado'
    END AS estado_conciliacion,
    
    -- Métricas de tiempo
    AVG(COALESCE(p.dias_credito, EXTRACT(DAY FROM NOW() - v.fecha_emision))) AS dias_credito_promedio,
    MAX(v.fecha_emision) AS fecha_ultima_factura
FROM cfdi_ventas v
LEFT JOIN cfdi_pagos p ON v.uuid_sat = p.cfdi_venta_uuid
WHERE v.metodo_pago = 'PPD' -- Pago en parcialidades o diferido
GROUP BY v.empresa_id, v.receptor_rfc, v.receptor_nombre;


-- Vista: Ventas por línea de negocio y mes
CREATE OR REPLACE VIEW v_ventas_linea_mes AS
SELECT 
    empresa_id,
    linea_negocio,
    DATE_TRUNC('month', fecha_emision) as mes,
    COUNT(*) as num_facturas,
    SUM(total) as total_ventas_mxn,
    SUM(CASE WHEN moneda = 'USD' THEN total * tipo_cambio ELSE total END) as total_ventas_normalizado
FROM cfdi_ventas
GROUP BY empresa_id, linea_negocio, DATE_TRUNC('month', fecha_emision);


-- =====================================================================
-- DATOS DE EJEMPLO (solo para testing)
-- =====================================================================

-- Insertar empresa de prueba
-- INSERT INTO empresas (razon_social, rfc, industria, tamaño_empresa)
-- VALUES ('Fradma Test SA de CV', 'FRA260226ABC', 'distribucion_ferreteria', '50-200');
