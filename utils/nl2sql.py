"""
Motor NL2SQL — Consultas en Lenguaje Natural sobre Base de Datos CFDI.

Convierte preguntas en español a SQL seguro, ejecuta contra Neon PostgreSQL,
y devuelve resultados interpretados con IA.

Características:
- Traducción NL → SQL con GPT-4o
- Validación de seguridad (solo SELECT, sin DDL/DML)
- Límite de filas y timeout de ejecución
- Interpretación inteligente de resultados
- Caché de esquema para reducir tokens
- Historial de consultas

Autor: Fradma Dashboard Team
Fecha: Febrero 2026
"""

import json
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

import pandas as pd

try:
    import psycopg2
    from psycopg2 import sql as pg_sql
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

from utils.logger import configurar_logger

logger = configurar_logger("nl2sql", nivel="INFO")

# =====================================================================
# Constantes de seguridad
# =====================================================================
MAX_ROWS = 1000
QUERY_TIMEOUT_SECONDS = 30
MAX_SQL_LENGTH = 2000

# Patrones SQL peligrosos (case-insensitive)
FORBIDDEN_PATTERNS = [
    r'\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|GRANT|REVOKE)\b',
    r'\b(EXEC|EXECUTE|CALL)\b',
    r'\b(pg_catalog|information_schema|pg_stat)\b',
    r';\s*(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE)',  # Inyección multi-statement
    r'--',  # Comentarios SQL (posible inyección)
    r'/\*',  # Comentarios de bloque
    r'\bINTO\s+OUTFILE\b',
    r'\bLOAD\s+DATA\b',
    r'\bCOPY\b',
]

# Tablas permitidas
ALLOWED_TABLES = [
    'empresas',
    'cfdi_ventas',
    'cfdi_conceptos',
    'cfdi_pagos',
    'clientes_master',
    'benchmarks_industria',
    'v_cartera_clientes',
    'v_ventas_linea_mes',
]


# =====================================================================
# Dataclasses
# =====================================================================
@dataclass
class NL2SQLResult:
    """Resultado de una consulta en lenguaje natural."""
    question: str
    sql: str
    dataframe: Optional[pd.DataFrame] = None
    interpretation: str = ""
    execution_time: float = 0.0
    row_count: int = 0
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    chart_suggestion: str = ""  # bar, hbar, line, area, pie, donut, scatter, treemap, funnel, waterfall, stacked_bar, grouped_bar, metric, table
    chart_spec: dict = field(default_factory=dict)  # Especificación detallada de la gráfica

    @property
    def success(self) -> bool:
        return self.error is None

    def to_dict(self) -> Dict:
        return {
            "question": self.question,
            "sql": self.sql,
            "interpretation": self.interpretation,
            "execution_time": self.execution_time,
            "row_count": self.row_count,
            "error": self.error,
            "timestamp": self.timestamp.isoformat(),
            "chart_suggestion": self.chart_suggestion,
            "chart_spec": self.chart_spec,
        }


# =====================================================================
# Esquema de la base de datos (contexto para GPT)
# =====================================================================
SCHEMA_CONTEXT = """
## Base de Datos: Fradma Dashboard — CFDIs México (PostgreSQL / Neon)

### Tabla: empresas
Registro de clientes/empresas que usan Fradma.
- id (UUID PK)
- razon_social (VARCHAR 255)
- rfc (VARCHAR 13, UNIQUE)
- email, telefono
- plan (VARCHAR 50): 'essential', 'business', 'enterprise'
- industria (VARCHAR 100): 'distribucion_ferreteria', 'manufactura_plasticos', etc.
- tamaño_empresa (VARCHAR 20): '10-50', '50-200', '200-500'
- status (VARCHAR 20): 'activo', 'suspendido', 'cancelado'
- fecha_registro, created_at, updated_at (TIMESTAMP)

### Tabla: cfdi_ventas
Facturas electrónicas (CFDI 4.0) emitidas. Es la tabla principal de ventas.
- id (UUID PK)
- empresa_id (UUID FK → empresas)
- uuid_sat (VARCHAR 36, UNIQUE) — UUID del timbre fiscal del SAT
- serie, folio (VARCHAR)
- fecha_emision (TIMESTAMP) — Fecha de la factura
- fecha_timbrado (TIMESTAMP)
- emisor_rfc (VARCHAR 13), emisor_nombre (VARCHAR 255), emisor_regimen_fiscal
- receptor_rfc (VARCHAR 13), receptor_nombre (VARCHAR 255) — El cliente final
- receptor_uso_cfdi, receptor_domicilio_fiscal, receptor_regimen_fiscal
- subtotal (DECIMAL 15,2)
- descuento (DECIMAL 15,2)
- impuestos (DECIMAL 15,2)
- total (DECIMAL 15,2) — Monto total de la factura
- moneda (VARCHAR 3): 'MXN', 'USD', 'EUR'
- tipo_cambio (DECIMAL 10,4)
- tipo_comprobante (VARCHAR 1): 'I'=Ingreso, 'E'=Egreso
- metodo_pago (VARCHAR 3): 'PUE' (pago en una sola exhibición), 'PPD' (pago en parcialidades/diferido)
- forma_pago (VARCHAR 2): '01'=Efectivo, '03'=Transferencia, '04'=Tarjeta crédito, '99'=Por definir
- lugar_expedicion (VARCHAR 5) — Código postal
- linea_negocio (VARCHAR 100) — Clasificado por IA
- vendedor_asignado (VARCHAR 100)
- es_exportacion (BOOLEAN)
- created_at, updated_at (TIMESTAMP)

### Tabla: cfdi_conceptos
Líneas de productos/servicios dentro de cada factura CFDI.
- id (UUID PK)
- cfdi_venta_id (UUID FK → cfdi_ventas)
- clave_prod_serv (VARCHAR 8) — Clave SAT del producto
- no_identificacion (VARCHAR 100) — SKU o código interno
- descripcion (TEXT) — Descripción del producto/servicio
- cantidad (DECIMAL 15,4)
- clave_unidad (VARCHAR 3), unidad (VARCHAR 20): 'Pieza', 'Kilo', etc.
- valor_unitario (DECIMAL 15,4)
- importe (DECIMAL 15,2)
- descuento (DECIMAL 15,2)
- categoria (VARCHAR 100) — Clasificado por IA

### Tabla: cfdi_pagos
Complementos de pago — tracking de cobranza y pagos recibidos.
- id (UUID PK)
- empresa_id (UUID FK → empresas)
- uuid_complemento (VARCHAR 36, UNIQUE)
- cfdi_venta_uuid (VARCHAR 36, FK → cfdi_ventas.uuid_sat)
- serie, folio (VARCHAR)
- fecha_pago (TIMESTAMP)
- forma_pago (VARCHAR 2)
- moneda (VARCHAR 3), tipo_cambio (DECIMAL 10,4)
- monto_pagado (DECIMAL 15,2)
- saldo_anterior (DECIMAL 15,2)
- saldo_insoluto (DECIMAL 15,2) — Si > 0, aún hay deuda
- num_parcialidad (INTEGER)
- dias_credito (INTEGER) — fecha_pago - fecha_emision de la factura

### Tabla: clientes_master
Catálogo maestro de clientes (deduplicado, enriquecido).
- id (UUID PK)
- empresa_id (UUID FK → empresas)
- rfc (VARCHAR 13), razon_social (VARCHAR 255), nombre_comercial
- email, telefono, domicilio_fiscal
- tipo_cliente (VARCHAR 50): 'distribuidor', 'minorista', 'mayorista', 'gobierno'
- industria (VARCHAR 100), segmento (VARCHAR 50): 'A', 'B', 'C'
- total_ventas_historico (DECIMAL 15,2)
- total_facturas (INTEGER)
- dias_credito_promedio (INTEGER)
- score_crediticio (DECIMAL 5,2): 0-100
- fecha_primera_venta, fecha_ultima_venta (TIMESTAMP)
- is_activo (BOOLEAN)

### Tabla: benchmarks_industria
Métricas agregadas y anonimizadas para comparación sectorial.
- industria, tamaño_empresa, pais
- metrica (VARCHAR 50): 'dso_promedio', 'score_cxc_promedio', etc.
- valor (DECIMAL 10,2), unidad
- n_empresas, percentil_25, percentil_50, percentil_75
- periodo (DATE)

### Vista: v_cartera_clientes
Resumen de Cuentas por Cobrar por cliente.
- empresa_id, receptor_rfc, receptor_nombre
- num_facturas, total_adeudado, saldo_pendiente
- dias_credito_promedio, fecha_ultima_factura

### Vista: v_ventas_linea_mes
Ventas agrupadas por línea de negocio y mes.
- empresa_id, linea_negocio, mes
- num_facturas, total_ventas_mxn, total_ventas_normalizado

### Relaciones clave:
- empresas.id → cfdi_ventas.empresa_id (1:N)
- cfdi_ventas.id → cfdi_conceptos.cfdi_venta_id (1:N)
- cfdi_ventas.uuid_sat → cfdi_pagos.cfdi_venta_uuid (1:N)
- empresas.id → clientes_master.empresa_id (1:N)
- empresas.id → cfdi_pagos.empresa_id (1:N)

### Convenciones:
- Montos en MXN por defecto. Para USD/EUR, multiplicar por tipo_cambio.
- metodo_pago='PPD' indica venta a crédito (relevante para CxC).
- tipo_comprobante='I' es ingreso (venta), 'E' es egreso (nota de crédito).
- fecha_emision es la fecha de facturación.
- receptor_nombre es el nombre del cliente final.

### IMPORTANTE — Terminología compras vs ventas:
- Esta base contiene las VENTAS (facturas emitidas por la empresa).
- Cuando el usuario pregunta "qué empresa compró más/menos" se refiere al RECEPTOR (cliente).
- "Compras de una empresa" = facturas donde esa empresa es receptor_nombre/receptor_rfc.
- "Ventas a un cliente" = lo mismo: CFDIs donde el cliente es el receptor.
- SIEMPRE busca en cfdi_ventas usando receptor_nombre o receptor_rfc para identificar clientes.
- NUNCA respondas que no hay datos sin antes intentar una consulta sobre cfdi_ventas.
- Si la pregunta menciona un mes (ej. "enero"), usa EXTRACT(MONTH FROM fecha_emision) = N.
- Si no se especifica año, asume el año actual: EXTRACT(YEAR FROM fecha_emision) = EXTRACT(YEAR FROM CURRENT_DATE).
"""


# =====================================================================
# Preguntas de ejemplo
# =====================================================================
EXAMPLE_QUESTIONS = [
    {
        "category": "Ventas",
        "icon": "💰",
        "questions": [
            "¿Cuánto se facturó en total el mes pasado?",
            "¿Cuáles son los 10 clientes con mayor facturación?",
            "¿Cuál es el promedio de facturación mensual?",
            "Muéstrame las ventas por línea de negocio",
            "¿Cuántas facturas se emitieron por mes este año?",
            "¿Cuál es el ticket promedio por factura?",
        ]
    },
    {
        "category": "Clientes",
        "icon": "👥",
        "questions": [
            "¿Cuántos clientes activos tenemos?",
            "¿Qué clientes no han comprado en los últimos 3 meses?",
            "¿Cuál es el top 5 de clientes por volumen de compra?",
            "¿Qué porcentaje de ventas representan los 10 principales clientes?",
        ]
    },
    {
        "category": "Cobranza",
        "icon": "💳",
        "questions": [
            "¿Cuánto es el saldo pendiente de cobro total?",
            "¿Cuáles son los clientes con mayor antigüedad de deuda?",
            "¿Cuál es el promedio de días de crédito?",
            "Muéstrame los pagos recibidos este mes",
        ]
    },
    {
        "category": "Productos",
        "icon": "📦",
        "questions": [
            "¿Cuáles son los 10 productos más vendidos?",
            "¿Cuáles productos tienen mayor variación de precio?",
            "¿Qué categorías de productos generan más ingresos?",
            "¿Cuál es el precio promedio por categoría?",
        ]
    },
    {
        "category": "Tendencias",
        "icon": "📈",
        "questions": [
            "¿Cómo ha evolucionado la facturación mensual este año?",
            "¿Qué meses tienen mayor facturación históricamente?",
            "Compara las ventas de este trimestre vs el anterior",
            "¿Cuál es la tendencia de nuevos clientes por mes?",
        ]
    },
    {
        "category": "Estadísticas",
        "icon": "📐",
        "questions": [
            "¿Cuál es la media y mediana de facturación?",
            "Dame el resumen estadístico completo de ventas",
            "¿Cuál es la desviación estándar del monto por cliente?",
            "Estadísticas de precios unitarios de productos",
            "¿Cuáles son los percentiles 25, 50 y 75 de facturación?",
            "¿Cuál es la moda de forma de pago?",
        ]
    },
    {
        "category": "Crecimiento",
        "icon": "🚀",
        "questions": [
            "Crecimiento de ventas mes a mes (MoM)",
            "Ventas acumuladas por mes este año",
            "Promedio móvil de 3 meses de facturación",
            "¿Cuáles clientes compran cada vez menos?",
        ]
    },
    {
        "category": "Segmentación",
        "icon": "🎯",
        "questions": [
            "Clasificación ABC de clientes (Pareto 80/20)",
            "Segmentación RFM de clientes",
            "Ranking de clientes por facturación",
            "Concentración de clientes (riesgo)",
        ]
    },
    {
        "category": "Riesgo & Anomalías",
        "icon": "⚠️",
        "questions": [
            "Detectar facturas anómalas (outliers)",
            "¿Cuál es el riesgo de concentración de clientes?",
            "¿Cuál es el DSO y tasa de cobro de los últimos 3 meses?",
            "¿Cuántas facturas PPD siguen sin pago?",
        ]
    },
]


# =====================================================================
# Motor NL2SQL
# =====================================================================
class NL2SQLEngine:
    """
    Motor de consultas en lenguaje natural sobre base de datos CFDI.
    
    Pipeline:
    1. Pregunta en español → GPT genera SQL
    2. Validación de seguridad del SQL
    3. Ejecución contra PostgreSQL con timeout y límite
    4. Interpretación de resultados con GPT
    5. Sugerencia de tipo de gráfica
    """

    def __init__(
        self,
        connection_string: str,
        api_key: str,
        model: str = "gpt-4o",
        max_rows: int = MAX_ROWS,
        timeout: int = QUERY_TIMEOUT_SECONDS,
    ):
        """
        Inicializa el motor NL2SQL.

        Args:
            connection_string: URL de conexión PostgreSQL/Neon
            api_key: API key de OpenAI
            model: Modelo a usar (gpt-4o recomendado para SQL preciso)
            max_rows: Máximo de filas a retornar
            timeout: Timeout de ejecución en segundos
        """
        if not PSYCOPG2_AVAILABLE:
            raise ImportError("psycopg2 no está instalado. Ejecuta: pip install psycopg2-binary")
        if not OPENAI_AVAILABLE:
            raise ImportError("openai no está instalado. Ejecuta: pip install openai")

        self.connection_string = connection_string
        self.api_key = api_key
        self.model = model
        self.max_rows = max_rows
        self.timeout = timeout
        self.client = OpenAI(api_key=api_key)
        self.history: List[NL2SQLResult] = []

        logger.info(f"NL2SQLEngine inicializado con modelo {model}")

    # -----------------------------------------------------------------
    # 1. Generación de SQL
    # -----------------------------------------------------------------
    def generate_sql(self, question: str, empresa_id: Optional[str] = None) -> str:
        """
        Genera SQL a partir de una pregunta en lenguaje natural.

        Args:
            question: Pregunta en español
            empresa_id: UUID de empresa para filtrar (opcional)

        Returns:
            Query SQL generado
        """
        system_prompt = self._build_system_prompt(empresa_id)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": question},
                ],
                temperature=0.0,  # Determinístico para SQL
                max_tokens=800,
            )

            raw_sql = response.choices[0].message.content.strip()

            # Limpiar el SQL (remover markdown code blocks si existen)
            sql = self._clean_sql(raw_sql)

            try:
                logger.info(f"SQL generado: {sql[:100]}...")
            except UnicodeEncodeError:
                logger.info("SQL generado (contiene caracteres especiales)")
            return sql

        except UnicodeEncodeError as e:
            raise ValueError(f"Error de codificación: {e}")
        except Exception as e:
            try:
                logger.error(f"Error generando SQL: {e}")
            except UnicodeEncodeError:
                logger.error("Error generando SQL (detalles no imprimibles)")
            raise ValueError(f"Error al generar SQL: {e}")

    def _build_system_prompt(self, empresa_id: Optional[str] = None) -> str:
        """Construye el system prompt para generación de SQL."""
        empresa_filter = ""
        if empresa_id:
            empresa_filter = f"""
IMPORTANTE: Filtra SIEMPRE por empresa_id = '{empresa_id}' en las tablas que tengan empresa_id.
"""

        return f"""Eres un experto en SQL PostgreSQL para un sistema de facturación electrónica CFDI de México.

Tu ÚNICA tarea es generar una consulta SQL SELECT válida a partir de la pregunta del usuario.

REGLAS ESTRICTAS:
1. Solo genera UNA sentencia SELECT. NUNCA INSERT, UPDATE, DELETE, DROP, ALTER, CREATE.
2. Siempre incluye LIMIT {self.max_rows} para evitar resultados excesivos.
3. Usa alias descriptivos en español para las columnas del resultado.
4. Formatea montos con 2 decimales.
5. Para montos multi-moneda, normaliza a MXN: total * tipo_cambio.
6. Ordena resultados de forma lógica (generalmente por monto DESC o fecha DESC).
7. Usa DATE_TRUNC para agrupaciones por periodo.
8. Para porcentajes, calcula con ROUND(x * 100.0 / total, 2).
9. Responde SOLO con la consulta SQL, sin explicación ni markdown. NO uses emojis ni caracteres especiales.
10. SIEMPRE intenta generar una consulta SQL válida. NUNCA generes el fallback de "Pregunta no compatible". Si la pregunta es genérica (ej: "qué gráficas me ofreces", "qué estadísticas tienes", "qué puedes hacer", "muéstrame análisis"), genera un resumen estadístico completo de cfdi_ventas con COUNT, AVG, MIN, MAX, STDDEV, PERCENTILE_CONT(0.25), PERCENTILE_CONT(0.5), PERCENTILE_CONT(0.75) sobre el campo total. Si la pregunta es sobre capacidades o ayuda, genera igualmente ese resumen estadístico como demostración.
11. Cuando pregunten por "empresas", "clientes" o "quién compró", busca en receptor_nombre de cfdi_ventas.
12. Para meses por nombre (enero=1, febrero=2, ... diciembre=12), usa EXTRACT(MONTH FROM fecha_emision).
13. Para estadísticas usa funciones de PostgreSQL: AVG() para promedio/media, PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY col) para mediana, STDDEV() o STDDEV_POP() para desviación estándar, VARIANCE() para varianza, MIN() y MAX() para rango, MODE() WITHIN GROUP (ORDER BY col) para moda.
14. Cuando pidan "estadísticas", "resumen estadístico" o "análisis estadístico", genera una consulta que incluya COUNT, AVG, MIN, MAX, STDDEV y PERCENTILE_CONT(0.5) del campo numérico relevante.
15. Para percentiles usa PERCENTILE_CONT(0.25/0.50/0.75) WITHIN GROUP (ORDER BY columna).
16. Redondea resultados estadísticos con ROUND(valor, 2).

REGLAS AVANZADAS DE ANALYTICS:
17. TIME INTELLIGENCE: Para comparaciones periodo a periodo usa LAG() OVER (ORDER BY periodo). Para crecimiento: ROUND((actual - anterior) * 100.0 / NULLIF(anterior, 0), 2) AS crecimiento_pct. Para acumulados usa SUM() OVER (ORDER BY mes ROWS UNBOUNDED PRECEDING). Para promedios móviles usa AVG() OVER (ORDER BY mes ROWS BETWEEN 2 PRECEDING AND CURRENT ROW).
18. WINDOW FUNCTIONS: Usa ROW_NUMBER(), RANK(), DENSE_RANK() para rankings. Usa LAG()/LEAD() para comparar con periodo anterior/siguiente. Usa NTILE(4) para cuartiles de clientes. Usa SUM() OVER (PARTITION BY ... ORDER BY ...) para running totals por grupo.
19. ANÁLISIS ABC / PARETO: Para clasificar clientes A/B/C por facturación, calcula el % acumulado con SUM(total) OVER (ORDER BY total DESC) / SUM(total) OVER (). Clientes A = hasta 80% acumulado, B = 80-95%, C = resto. Usa CASE WHEN para asignar categoría.
20. SEGMENTACIÓN RFM: Recency = dias desde última compra (CURRENT_DATE - MAX(fecha_emision)). Frequency = COUNT de facturas. Monetary = SUM(total). Usa NTILE(5) para puntuar cada dimensión 1-5. Score RFM = R*100 + F*10 + M.
21. DETECCIÓN DE ANOMALÍAS: Para outliers usa Z-score: (valor - AVG(valor) OVER()) / NULLIF(STDDEV(valor) OVER(), 0). Valores con |z| > 2 son anomalías. También detecta facturas inusualmente altas/bajas respecto al promedio del cliente.
22. CASH FLOW / COBRANZA: Para proyección usa cfdi_pagos. DSO (Days Sales Outstanding) = SUM(saldo_insoluto) / (SUM(total vendido) / dias_periodo). Tasa de cobro = SUM(monto_pagado) / SUM(total facturado). Antigüedad = CURRENT_DATE - fecha_emision para facturas PPD sin pago completo.
23. CONCENTRACIÓN: Para riesgo de concentración calcula % que representa cada cliente del total. Índice Herfindahl = SUM(share^2). Si un cliente > 30% = alerta alta, > 15% = media.
24. CRECIMIENTO: Para tasas de crecimiento MoM/YoY, compara periodos con LAG. CAGR = POWER(ultimo/primero, 1.0/n_periodos) - 1. Velocidad = pendiente de la regresión lineal.
{empresa_filter}

{SCHEMA_CONTEXT}

EJEMPLOS:
Pregunta: ¿Cuánto se facturó este mes?
SQL: SELECT SUM(total) AS total_facturado, moneda FROM cfdi_ventas WHERE DATE_TRUNC('month', fecha_emision) = DATE_TRUNC('month', CURRENT_DATE) GROUP BY moneda LIMIT {self.max_rows};

Pregunta: Top 5 clientes por facturación
SQL: SELECT receptor_nombre AS cliente, COUNT(*) AS num_facturas, SUM(total * tipo_cambio) AS total_mxn FROM cfdi_ventas GROUP BY receptor_nombre ORDER BY total_mxn DESC LIMIT 5;

Pregunta: Ventas mensuales de este año
SQL: SELECT DATE_TRUNC('month', fecha_emision) AS mes, COUNT(*) AS facturas, SUM(total * tipo_cambio) AS total_mxn FROM cfdi_ventas WHERE EXTRACT(YEAR FROM fecha_emision) = EXTRACT(YEAR FROM CURRENT_DATE) GROUP BY mes ORDER BY mes LIMIT {self.max_rows};

Pregunta: ¿Cuál empresa compró menos en enero?
SQL: SELECT receptor_nombre AS cliente, COUNT(*) AS num_facturas, SUM(total) AS total_comprado FROM cfdi_ventas WHERE EXTRACT(MONTH FROM fecha_emision) = 1 AND EXTRACT(YEAR FROM fecha_emision) = EXTRACT(YEAR FROM CURRENT_DATE) GROUP BY receptor_nombre ORDER BY total_comprado ASC LIMIT 1;

Pregunta: ¿Cuánto le vendimos a DISTRIBUIDORA FESA?
SQL: SELECT receptor_nombre AS cliente, COUNT(*) AS facturas, SUM(total) AS total_vendido, MIN(fecha_emision) AS primera_compra, MAX(fecha_emision) AS ultima_compra FROM cfdi_ventas WHERE UPPER(receptor_nombre) LIKE '%FESA%' GROUP BY receptor_nombre LIMIT {self.max_rows};

Pregunta: ¿Cuántos clientes diferentes compraron este mes?
SQL: SELECT COUNT(DISTINCT receptor_rfc) AS clientes_unicos FROM cfdi_ventas WHERE DATE_TRUNC('month', fecha_emision) = DATE_TRUNC('month', CURRENT_DATE) LIMIT {self.max_rows};

Pregunta: ¿Cuál es la media y mediana de facturación?
SQL: SELECT ROUND(AVG(total), 2) AS media, ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY total)::numeric, 2) AS mediana, COUNT(*) AS num_facturas FROM cfdi_ventas LIMIT {self.max_rows};

Pregunta: Estadísticas de facturación (promedio, desviación estándar, mínimo, máximo)
SQL: SELECT COUNT(*) AS total_facturas, ROUND(AVG(total), 2) AS promedio, ROUND(STDDEV(total), 2) AS desviacion_estandar, ROUND(MIN(total), 2) AS minimo, ROUND(MAX(total), 2) AS maximo, ROUND(PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY total)::numeric, 2) AS percentil_25, ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY total)::numeric, 2) AS mediana, ROUND(PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY total)::numeric, 2) AS percentil_75 FROM cfdi_ventas LIMIT {self.max_rows};

Pregunta: ¿Cuál es la desviación estándar del monto por cliente?
SQL: SELECT receptor_nombre AS cliente, COUNT(*) AS facturas, ROUND(AVG(total), 2) AS promedio, ROUND(STDDEV(total), 2) AS desviacion_estandar, ROUND(MIN(total), 2) AS minimo, ROUND(MAX(total), 2) AS maximo FROM cfdi_ventas GROUP BY receptor_nombre HAVING COUNT(*) > 1 ORDER BY desviacion_estandar DESC NULLS LAST LIMIT {self.max_rows};

Pregunta: ¿Cuál es la moda de forma de pago?
SQL: SELECT forma_pago, COUNT(*) AS frecuencia FROM cfdi_ventas GROUP BY forma_pago ORDER BY frecuencia DESC LIMIT 1;

Pregunta: Dame el resumen estadístico de precios unitarios de productos
SQL: SELECT COUNT(*) AS total_conceptos, ROUND(AVG(valor_unitario), 2) AS precio_promedio, ROUND(STDDEV(valor_unitario), 2) AS desviacion_estandar, ROUND(MIN(valor_unitario), 2) AS precio_minimo, ROUND(MAX(valor_unitario), 2) AS precio_maximo, ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY valor_unitario)::numeric, 2) AS precio_mediana FROM cfdi_conceptos LIMIT {self.max_rows};

Pregunta: Crecimiento de ventas mes a mes (MoM)
SQL: WITH ventas_mes AS (SELECT DATE_TRUNC('month', fecha_emision) AS mes, SUM(total * tipo_cambio) AS total_mxn FROM cfdi_ventas GROUP BY mes ORDER BY mes) SELECT mes, ROUND(total_mxn, 2) AS ventas, ROUND(LAG(total_mxn) OVER (ORDER BY mes), 2) AS mes_anterior, ROUND((total_mxn - LAG(total_mxn) OVER (ORDER BY mes)) * 100.0 / NULLIF(LAG(total_mxn) OVER (ORDER BY mes), 0), 2) AS crecimiento_pct FROM ventas_mes LIMIT {self.max_rows};

Pregunta: Ventas acumuladas por mes este año
SQL: SELECT DATE_TRUNC('month', fecha_emision) AS mes, SUM(total * tipo_cambio) AS ventas_mes, SUM(SUM(total * tipo_cambio)) OVER (ORDER BY DATE_TRUNC('month', fecha_emision) ROWS UNBOUNDED PRECEDING) AS acumulado FROM cfdi_ventas WHERE EXTRACT(YEAR FROM fecha_emision) = EXTRACT(YEAR FROM CURRENT_DATE) GROUP BY mes ORDER BY mes LIMIT {self.max_rows};

Pregunta: Promedio móvil de 3 meses de facturación
SQL: WITH ventas_mes AS (SELECT DATE_TRUNC('month', fecha_emision) AS mes, SUM(total * tipo_cambio) AS total_mxn FROM cfdi_ventas GROUP BY mes ORDER BY mes) SELECT mes, ROUND(total_mxn, 2) AS ventas, ROUND(AVG(total_mxn) OVER (ORDER BY mes ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 2) AS promedio_movil_3m FROM ventas_mes LIMIT {self.max_rows};

Pregunta: Ranking de clientes por facturación
SQL: SELECT receptor_nombre AS cliente, SUM(total * tipo_cambio) AS total_mxn, RANK() OVER (ORDER BY SUM(total * tipo_cambio) DESC) AS ranking, COUNT(*) AS facturas FROM cfdi_ventas GROUP BY receptor_nombre ORDER BY ranking LIMIT {self.max_rows};

Pregunta: Clasificación ABC de clientes (Pareto)
SQL: WITH clientes AS (SELECT receptor_nombre AS cliente, SUM(total * tipo_cambio) AS total_mxn FROM cfdi_ventas GROUP BY receptor_nombre), acumulado AS (SELECT cliente, total_mxn, SUM(total_mxn) OVER (ORDER BY total_mxn DESC) AS acum, SUM(total_mxn) OVER () AS gran_total FROM clientes) SELECT cliente, ROUND(total_mxn, 2) AS total_mxn, ROUND(acum * 100.0 / gran_total, 2) AS pct_acumulado, CASE WHEN acum * 100.0 / gran_total <= 80 THEN 'A' WHEN acum * 100.0 / gran_total <= 95 THEN 'B' ELSE 'C' END AS clasificacion_abc FROM acumulado ORDER BY total_mxn DESC LIMIT {self.max_rows};

Pregunta: Segmentación RFM de clientes
SQL: WITH rfm AS (SELECT receptor_nombre AS cliente, (CURRENT_DATE - MAX(fecha_emision::date)) AS recencia_dias, COUNT(*) AS frecuencia, ROUND(SUM(total * tipo_cambio), 2) AS monetario FROM cfdi_ventas GROUP BY receptor_nombre), scored AS (SELECT cliente, recencia_dias, frecuencia, monetario, NTILE(5) OVER (ORDER BY recencia_dias DESC) AS r_score, NTILE(5) OVER (ORDER BY frecuencia ASC) AS f_score, NTILE(5) OVER (ORDER BY monetario ASC) AS m_score FROM rfm) SELECT cliente, recencia_dias, frecuencia, monetario, r_score, f_score, m_score, (r_score * 100 + f_score * 10 + m_score) AS rfm_score, CASE WHEN r_score >= 4 AND f_score >= 4 AND m_score >= 4 THEN 'Champions' WHEN r_score >= 3 AND f_score >= 3 THEN 'Leales' WHEN r_score >= 4 AND f_score <= 2 THEN 'Nuevos' WHEN r_score <= 2 AND f_score >= 3 THEN 'En Riesgo' WHEN r_score <= 2 AND f_score <= 2 THEN 'Hibernando' ELSE 'Potenciales' END AS segmento FROM scored ORDER BY rfm_score DESC LIMIT {self.max_rows};

Pregunta: Detectar facturas anómalas (outliers)
SQL: WITH stats AS (SELECT AVG(total) AS media, STDDEV(total) AS desv FROM cfdi_ventas) SELECT v.receptor_nombre AS cliente, v.folio, v.fecha_emision, ROUND(v.total, 2) AS monto, ROUND((v.total - s.media) / NULLIF(s.desv, 0), 2) AS z_score, CASE WHEN ABS((v.total - s.media) / NULLIF(s.desv, 0)) > 3 THEN 'Anomalia Alta' WHEN ABS((v.total - s.media) / NULLIF(s.desv, 0)) > 2 THEN 'Anomalia Media' ELSE 'Normal' END AS clasificacion FROM cfdi_ventas v, stats s WHERE ABS((v.total - s.media) / NULLIF(s.desv, 0)) > 2 ORDER BY z_score DESC LIMIT {self.max_rows};

Pregunta: Concentración de clientes (riesgo)
SQL: WITH totales AS (SELECT receptor_nombre AS cliente, SUM(total * tipo_cambio) AS total_mxn FROM cfdi_ventas GROUP BY receptor_nombre) SELECT cliente, ROUND(total_mxn, 2) AS total_mxn, ROUND(total_mxn * 100.0 / SUM(total_mxn) OVER (), 2) AS pct_del_total, CASE WHEN total_mxn * 100.0 / SUM(total_mxn) OVER () > 30 THEN 'CRITICO' WHEN total_mxn * 100.0 / SUM(total_mxn) OVER () > 15 THEN 'ALTO' WHEN total_mxn * 100.0 / SUM(total_mxn) OVER () > 5 THEN 'MEDIO' ELSE 'BAJO' END AS nivel_riesgo FROM totales ORDER BY total_mxn DESC LIMIT {self.max_rows};

Pregunta: DSO y tasa de cobro
SQL: WITH facturado AS (SELECT SUM(total * tipo_cambio) AS total_facturado, COUNT(*) AS n_facturas FROM cfdi_ventas WHERE fecha_emision >= DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '3 months'), cobrado AS (SELECT COALESCE(SUM(monto_pagado), 0) AS total_cobrado FROM cfdi_pagos WHERE fecha_pago >= DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '3 months'), pendiente AS (SELECT COALESCE(SUM(saldo_insoluto), 0) AS saldo_pendiente FROM cfdi_pagos WHERE saldo_insoluto > 0) SELECT ROUND(f.total_facturado, 2) AS facturado_3m, ROUND(c.total_cobrado, 2) AS cobrado_3m, ROUND(c.total_cobrado * 100.0 / NULLIF(f.total_facturado, 0), 2) AS tasa_cobro_pct, ROUND(p.saldo_pendiente, 2) AS saldo_pendiente, ROUND(p.saldo_pendiente / NULLIF(f.total_facturado / 90.0, 0), 1) AS dso_dias FROM facturado f, cobrado c, pendiente p LIMIT 1;

Pregunta: ¿Cuáles clientes compran cada vez menos? (tendencia negativa)
SQL: WITH por_trimestre AS (SELECT receptor_nombre AS cliente, DATE_TRUNC('quarter', fecha_emision) AS trimestre, SUM(total * tipo_cambio) AS total_mxn FROM cfdi_ventas GROUP BY receptor_nombre, trimestre), con_tendencia AS (SELECT cliente, trimestre, total_mxn, LAG(total_mxn) OVER (PARTITION BY cliente ORDER BY trimestre) AS trimestre_anterior FROM por_trimestre) SELECT cliente, trimestre, ROUND(total_mxn, 2) AS ventas_actual, ROUND(trimestre_anterior, 2) AS ventas_anterior, ROUND((total_mxn - trimestre_anterior) * 100.0 / NULLIF(trimestre_anterior, 0), 2) AS cambio_pct FROM con_tendencia WHERE trimestre_anterior IS NOT NULL AND total_mxn < trimestre_anterior ORDER BY cambio_pct ASC LIMIT {self.max_rows};
"""

    def _clean_sql(self, raw: str) -> str:
        """Limpia el SQL de markdown code blocks y whitespace."""
        # Remover ```sql ... ```
        sql = re.sub(r'```(?:sql)?\s*', '', raw)
        sql = re.sub(r'```\s*$', '', sql)
        sql = sql.strip()

        # Remover punto y coma extra al final
        sql = sql.rstrip(';') + ';'

        return sql

    # -----------------------------------------------------------------
    # 2. Validación de seguridad
    # -----------------------------------------------------------------
    def validate_sql(self, sql: str) -> Tuple[bool, str]:
        """
        Valida que el SQL sea seguro para ejecución.

        Args:
            sql: Query SQL a validar

        Returns:
            Tupla (es_valido, mensaje_error)
        """
        # Check largo
        if len(sql) > MAX_SQL_LENGTH:
            return False, f"Query excede el límite de {MAX_SQL_LENGTH} caracteres"

        # Debe empezar con SELECT (case-insensitive)
        if not re.match(r'^\s*SELECT\b', sql, re.IGNORECASE):
            return False, "Solo se permiten consultas SELECT"

        # Check patrones prohibidos
        for pattern in FORBIDDEN_PATTERNS:
            if re.search(pattern, sql, re.IGNORECASE):
                return False, f"Patrón SQL no permitido detectado: {pattern}"

        # Verificar que no contenga múltiples statements
        # (split por ; y filtrar vacíos)
        statements = [s.strip() for s in sql.split(';') if s.strip()]
        if len(statements) > 1:
            return False, "Solo se permite una sentencia SQL"

        # Verificar tablas referenciadas
        # Excluir FROM dentro de EXTRACT(...FROM...) y DATE_TRUNC
        # Primero, remover contenido de funciones EXTRACT para evitar falsos positivos
        sql_cleaned = re.sub(r'EXTRACT\s*\([^)]+\)', '', sql, flags=re.IGNORECASE)
        tables_in_query = re.findall(
            r'\bFROM\s+(\w+)|\bJOIN\s+(\w+)',
            sql_cleaned,
            re.IGNORECASE
        )
        for match_groups in tables_in_query:
            for table in match_groups:
                if table and table.lower() not in ALLOWED_TABLES:
                    return False, f"Tabla no permitida: {table}"

        return True, "OK"

    # -----------------------------------------------------------------
    # 3. Ejecución de query
    # -----------------------------------------------------------------
    def execute_query(self, sql: str) -> pd.DataFrame:
        """
        Ejecuta una query SQL contra la base de datos.

        Args:
            sql: Query SQL validado

        Returns:
            DataFrame con los resultados

        Raises:
            RuntimeError: Si hay error de conexión o ejecución
        """
        conn = None
        try:
            conn = psycopg2.connect(self.connection_string)

            # Establecer readonly y timeout via SQL (compatible con Neon pooler)
            cursor = conn.cursor()
            cursor.execute("SET default_transaction_read_only = true;")
            cursor.execute(f"SET statement_timeout = '{self.timeout * 1000}ms';")
            cursor.close()

            # Ejecutar query
            df = pd.read_sql_query(sql, conn)

            # Aplicar límite de filas
            if len(df) > self.max_rows:
                df = df.head(self.max_rows)
                logger.warning(f"Resultados truncados a {self.max_rows} filas")

            # Convertir Decimal a float para compatibilidad con Streamlit
            for col in df.columns:
                if df[col].dtype == object:
                    try:
                        df[col] = df[col].apply(
                            lambda x: float(x) if isinstance(x, Decimal) else x
                        )
                    except (ValueError, TypeError):
                        pass

            logger.info(f"Query ejecutado: {len(df)} filas retornadas")
            return df

        except psycopg2.errors.QueryCanceled:
            raise RuntimeError(
                f"La consulta excedió el tiempo límite de {self.timeout}s. "
                "Intenta una pregunta más específica."
            )
        except psycopg2.Error as e:
            logger.error(f"Error PostgreSQL: {e}")
            raise RuntimeError(f"Error en base de datos: {e}")
        finally:
            if conn:
                conn.close()

    # -----------------------------------------------------------------
    # 4. Interpretación de resultados
    # -----------------------------------------------------------------
    def interpret_results(
        self,
        question: str,
        sql: str,
        df: pd.DataFrame
    ) -> Tuple[str, str, dict]:
        """
        Genera una interpretación en lenguaje natural de los resultados.

        Args:
            question: Pregunta original
            sql: SQL ejecutado
            df: DataFrame con resultados

        Returns:
            Tupla (interpretación, tipo_gráfica, chart_spec_dict)
        """
        if df.empty:
            return "No se encontraron datos para esta consulta.", "table", {}

        # Preparar resumen de datos (max 20 filas para el prompt)
        sample = df.head(20).to_string(index=False)
        row_count = len(df)
        col_info = ", ".join([f"{col} ({df[col].dtype})" for col in df.columns])

        prompt = f"""Analiza los resultados de esta consulta y proporciona una interpretación concisa y profesional EN ESPAÑOL.

PREGUNTA ORIGINAL: {question}

SQL EJECUTADO: {sql}

COLUMNAS: {col_info}
FILAS TOTALES: {row_count}

DATOS (primeras filas):
{sample}

INSTRUCCIONES:
1. Responde la pregunta del usuario de forma directa y clara.
2. Destaca los hallazgos más importantes.
3. Si hay montos, formatéalos con $ y separadores de miles.
4. Si hay tendencias, menciónalas.
5. Máximo 3-4 oraciones concisas.
6. NO repitas la pregunta ni el SQL.

AL FINAL, genera una especificación de gráfica en formato JSON en una sola línea.
La línea DEBE comenzar exactamente con CHART_SPEC: seguido del JSON.

Tipos de gráfica disponibles:
- bar: barras verticales (ranking, comparaciones)
- hbar: barras horizontales (ranking con nombres largos)
- stacked_bar: barras apiladas (composición por categoría)
- grouped_bar: barras agrupadas (comparar grupos lado a lado)
- line: línea temporal (tendencias, evolución)
- area: área rellena (tendencias acumulativas)
- pie: pastel (distribución porcentual, max 8 categorías)
- donut: dona (como pie pero más moderno)
- scatter: dispersión (correlación entre 2 valores)
- treemap: mapa de árbol (jerarquías, proporciones)
- funnel: embudo (procesos secuenciales)
- waterfall: cascada (contribuciones positivas/negativas)
- metric: tarjeta de KPI (1 sola fila con valor clave)
- stats_summary: dashboard estadístico (cuando hay media, mediana, desviación, percentiles)
- box: diagrama de caja (distribución con outliers)
- histogram: histograma (distribución de frecuencias)
- gauge: velocímetro (indicador con rangos)
- heatmap: mapa de calor (2 dimensiones categóricas + valor)
- table: tabla con formato (cuando no aplica gráfica)

PARA ESTADÍSTICAS: Cuando la consulta devuelve media, mediana, desviación estándar, percentiles, usa stats_summary. Cuando devuelve datos por grupo con estadísticas (ej. promedio por cliente), también usa stats_summary.

Campos del JSON:
- type: tipo de gráfica (obligatorio)
- x: nombre exacto de columna para eje X (obligatorio para bar/line/area/scatter)
- y: nombre exacto de columna para eje Y/valores (obligatorio para bar/line/area/scatter)
- color: columna para agrupar por color (opcional)
- title: título descriptivo corto en español (obligatorio)
- sort: "asc" o "desc" para ordenar datos (opcional)
- top_n: número máximo de elementos a mostrar (opcional, default 30)

EJEMPLO de línea final:
CHART_SPEC: {{"type": "hbar", "x": "cliente", "y": "total_mxn", "title": "Top clientes por facturación", "sort": "desc", "top_n": 10}}

Si el usuario pidió explícitamente un tipo de gráfica (ej: "muéstrame un pie chart", "hazme una gráfica de barras"), USA ESE TIPO.
"""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",  # Más económico para interpretación
                messages=[
                    {
                        "role": "system",
                        "content": "Eres un analista de datos experto en facturación "
                                   "y cuentas por cobrar B2B en México. Responde en español."
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=500,
            )

            text = response.choices[0].message.content.strip()

            # Extraer CHART_SPEC JSON
            chart_type = "table"
            chart_spec = {}
            spec_match = re.search(r'CHART_SPEC:\s*(\{.*\})', text)
            if spec_match:
                try:
                    chart_spec = json.loads(spec_match.group(1))
                    chart_type = chart_spec.get("type", "table")
                except (json.JSONDecodeError, ValueError):
                    chart_type = "table"
                text = re.sub(r'\n?CHART_SPEC:\s*\{.*\}', '', text).strip()
            else:
                # Fallback: buscar CHART_TYPE legacy
                chart_match = re.search(r'CHART_TYPE:\s*(\w+)', text)
                if chart_match:
                    chart_type = chart_match.group(1).lower()
                    text = re.sub(r'\n?CHART_TYPE:\s*\w+', '', text).strip()

            return text, chart_type, chart_spec

        except Exception as e:
            logger.error(f"Error interpretando resultados: {e}")
            return f"Se obtuvieron {row_count} resultados.", "table", {}

    # -----------------------------------------------------------------
    # 5. Pipeline completo: ask()
    # -----------------------------------------------------------------
    def ask(
        self,
        question: str,
        empresa_id: Optional[str] = None
    ) -> NL2SQLResult:
        """
        Pipeline completo: pregunta → SQL → ejecución → interpretación.

        Args:
            question: Pregunta en lenguaje natural (español)
            empresa_id: UUID de empresa para filtrar (opcional)

        Returns:
            NL2SQLResult con todos los datos
        """
        start_time = time.time()
        result = NL2SQLResult(question=question, sql="")

        try:
            # Paso 1: Generar SQL
            sql = self.generate_sql(question, empresa_id)
            result.sql = sql

            # Paso 2: Validar seguridad
            is_valid, error_msg = self.validate_sql(sql)
            if not is_valid:
                result.error = f"🛡️ Seguridad: {error_msg}"
                result.execution_time = time.time() - start_time
                self.history.append(result)
                return result

            # Paso 3: Ejecutar query
            df = self.execute_query(sql)
            result.dataframe = df
            result.row_count = len(df)

            # Paso 4: Interpretar resultados
            interpretation, chart_type, chart_spec = self.interpret_results(question, sql, df)
            result.interpretation = interpretation
            result.chart_suggestion = chart_type
            result.chart_spec = chart_spec

        except ValueError as e:
            result.error = f"❌ Error generando SQL: {e}"
        except RuntimeError as e:
            result.error = f"⚠️ Error de ejecución: {e}"
        except Exception as e:
            result.error = f"❌ Error inesperado: {e}"
            logger.exception(f"Error en pipeline ask(): {e}")

        result.execution_time = time.time() - start_time
        self.history.append(result)

        return result

    # -----------------------------------------------------------------
    # Utilidades
    # -----------------------------------------------------------------
    def get_history(self) -> List[NL2SQLResult]:
        """Retorna el historial de consultas."""
        return list(reversed(self.history))

    def clear_history(self):
        """Limpia el historial de consultas."""
        self.history.clear()

    def test_connection(self) -> Tuple[bool, str]:
        """
        Prueba la conexión a la base de datos.

        Returns:
            Tupla (éxito, mensaje)
        """
        conn = None
        try:
            conn = psycopg2.connect(self.connection_string)
            cursor = conn.cursor()
            cursor.execute("SELECT version();")
            version = cursor.fetchone()[0]
            cursor.close()
            return True, f"Conectado: {version[:60]}"
        except Exception as e:
            return False, f"Error: {e}"
        finally:
            if conn:
                conn.close()

    def get_table_counts(self) -> Dict[str, int]:
        """
        Obtiene el conteo de registros por tabla.

        Returns:
            Diccionario tabla → conteo
        """
        conn = None
        counts = {}
        try:
            conn = psycopg2.connect(self.connection_string)
            cursor = conn.cursor()
            cursor.execute("SET default_transaction_read_only = true;")

            for table in ALLOWED_TABLES:
                if table.startswith('v_'):
                    continue  # Las vistas pueden ser costosas
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {table};")
                    counts[table] = cursor.fetchone()[0]
                except Exception:
                    counts[table] = -1  # Tabla puede no existir

            cursor.close()
            return counts
        except Exception as e:
            logger.error(f"Error obteniendo conteos: {e}")
            return {}
        finally:
            if conn:
                conn.close()

    def get_date_range(self) -> Optional[Tuple[str, str]]:
        """
        Obtiene el rango de fechas de los datos.

        Returns:
            Tupla (fecha_min, fecha_max) o None
        """
        conn = None
        try:
            conn = psycopg2.connect(self.connection_string)
            cursor = conn.cursor()
            cursor.execute("SET default_transaction_read_only = true;")
            cursor.execute(
                "SELECT MIN(fecha_emision)::date, MAX(fecha_emision)::date "
                "FROM cfdi_ventas;"
            )
            row = cursor.fetchone()
            cursor.close()
            if row and row[0]:
                return str(row[0]), str(row[1])
            return None
        except Exception:
            return None
        finally:
            if conn:
                conn.close()


# =====================================================================
# Helper de validación (sin conexión a DB, útil para tests)
# =====================================================================
def validate_sql_static(sql: str) -> Tuple[bool, str]:
    """
    Validación estática de SQL sin necesidad de instanciar el engine.

    Args:
        sql: Query SQL a validar

    Returns:
        Tupla (es_valido, mensaje_error)
    """
    if len(sql) > MAX_SQL_LENGTH:
        return False, f"Query excede el límite de {MAX_SQL_LENGTH} caracteres"

    if not re.match(r'^\s*SELECT\b', sql, re.IGNORECASE):
        return False, "Solo se permiten consultas SELECT"

    for pattern in FORBIDDEN_PATTERNS:
        if re.search(pattern, sql, re.IGNORECASE):
            return False, f"Patrón SQL no permitido: {pattern}"

    statements = [s.strip() for s in sql.split(';') if s.strip()]
    if len(statements) > 1:
        return False, "Solo se permite una sentencia SQL"

    # Remover EXTRACT(...) para evitar falsos positivos con FROM dentro de funciones
    sql_cleaned = re.sub(r'EXTRACT\s*\([^)]+\)', '', sql, flags=re.IGNORECASE)
    tables_in_query = re.findall(
        r'\bFROM\s+(\w+)|\bJOIN\s+(\w+)',
        sql_cleaned,
        re.IGNORECASE
    )
    for match_groups in tables_in_query:
        for table in match_groups:
            if table and table.lower() not in ALLOWED_TABLES:
                return False, f"Tabla no permitida: {table}"

    return True, "OK"


def get_example_questions() -> List[Dict]:
    """Retorna las preguntas de ejemplo organizadas por categoría."""
    return EXAMPLE_QUESTIONS
