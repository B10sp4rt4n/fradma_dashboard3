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
try:
    from utils.sovereign_periods import build_prompt_context as _sp_build_prompt
except ImportError:
    _sp_build_prompt = None

try:
    from utils.sovereign_profiles import (
        build_sovereign_profile_context as _sp_profile_ctx,
        apply_profile_sql_filter as _apply_profile_filter,
    )
except ImportError:
    _sp_profile_ctx = None
    _apply_profile_filter = None

logger = configurar_logger("nl2sql", nivel="INFO")

# =====================================================================
# Constantes de seguridad
# =====================================================================
MAX_ROWS = 1000
QUERY_TIMEOUT_SECONDS = 30
MAX_SQL_LENGTH = 8000

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
# Helpers de formato
# =====================================================================
def _normalize_highlights(text: str) -> str:
    """Convierte highlights de GPT a formato nativo Streamlit :color[**texto**].

    Usa la sintaxis :green[**$monto**] y :blue[**número**] que Streamlit
    renderiza correctamente dentro de st.chat_message (a diferencia de HTML
    <span> que se escapa en el contexto de chat).
    """
    # --- Paso 0: deshacer markdown bold/italic previo ---
    text = re.sub(r'\*{1,3}(\$[\d,]+(?:\.\d{1,2})?)\*{1,3}', r'\1', text)
    text = re.sub(r'\*{1,3}([\d,]+(?:\.\d{1,2})?(?:\s*%)?(?:\s+\w+)?)\*{1,3}', r'\1', text)
    text = re.sub(r'(?<!\w)_([^_]+)_(?!\w)', r'\1', text)
    # Limpiar asteriscos sueltos residuales
    text = re.sub(r'\*{2,}', '', text)

    # --- Paso 1: backticks → contenido limpio ---
    text = re.sub(r'`([^`]+)`', r'\1', text)

    # --- Paso 2: proteger :color[] existentes con tokens ---
    _tokens: list = []
    def _protect(m):
        _tokens.append(m.group(0))
        return f'\x00TK{len(_tokens) - 1}\x00'
    text = re.sub(r':\w+\[.*?\]', _protect, text)

    # --- Paso 3: aplicar formato :color[**texto**] de Streamlit ---
    # 3a) Montos: $1,234.56 → :green[**$1,234.56**]
    text = re.sub(
        r'(\$[\d,]+(?:\.\d{1,2})?)',
        r':green[**\1**]',
        text
    )

    # 3b) Porcentajes: 85.2% → :blue[**85.2%**]
    text = re.sub(
        r'(\b[\d,]+(?:\.\d{1,2})?\s*%)',
        r':blue[**\1**]',
        text
    )

    # 3c) Números + unidad: "17 facturas" → :blue[**17 facturas**]
    text = re.sub(
        r'(\b\d[\d,]*(?:\.\d{1,2})?\s+(?:facturas?|productos?|clientes?|días|meses|registros|conceptos|pagos|ventas|total))',
        r':blue[**\1**]',
        text
    )

    # 3d) Números grandes sueltos (1,234+) → :blue[**1,234**]
    text = re.sub(
        r'(?<!\$)(\b\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?)\b',
        r':blue[**\1**]',
        text
    )

    # --- Paso 4: restaurar tokens protegidos ---
    for i, token in enumerate(_tokens):
        text = text.replace(f'\x00TK{i}\x00', token)

    return text


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
- metodo_pago='PPD' indica venta a crédito (relevante para CxC). Requiere complemento de pago.
- metodo_pago='PUE' indica pago de contado (la factura YA está pagada, NO necesita complemento).
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
- **CRÍTICO — TABLA empresas**: La tabla `empresas` es un catálogo INTERNO de tenants (clientes de la plataforma Fradma). NUNCA la uses para analizar clientes de negocio, nuevos clientes, tendencias de clientes, concentración de clientes ni ningún análisis de ventas. Para CUALQUIER pregunta sobre "clientes" (nuevos, activos, inactivos, top clientes, tendencia por mes, etc.) usa SIEMPRE `cfdi_ventas.receptor_rfc` y `cfdi_ventas.receptor_nombre`. Por ejemplo, "nuevos clientes por mes" = primer mes en que aparece cada `receptor_rfc` en `cfdi_ventas`.
- Ejemplo correcto para "tendencia de nuevos clientes por mes": WITH primera_compra AS (SELECT receptor_rfc, MIN(DATE_TRUNC('month', fecha_emision)) AS mes_primera_compra FROM cfdi_ventas WHERE empresa_id = '{empresa_id}' AND tipo_comprobante = 'I' GROUP BY receptor_rfc) SELECT mes_primera_compra AS mes, COUNT(*) AS nuevos_clientes FROM primera_compra GROUP BY mes ORDER BY mes DESC LIMIT 24;
- Si la pregunta menciona un mes (ej. "enero"), usa EXTRACT(MONTH FROM fecha_emision) = N.
- Si el usuario especifica un año explícito (ej. "2025", "enero 2025"), usa SIEMPRE ese año literal: EXTRACT(YEAR FROM fecha_emision) = 2025. NUNCA combines EXTRACT(YEAR FROM CURRENT_DATE) con un año literal — eso genera condiciones contradictorias y 0 resultados.
- Si el usuario pide un RANGO de meses con año (ej. "enero a diciembre 2025", "reporte 2025"), usa filtro por rango de fechas: fecha_emision >= '2025-01-01' AND fecha_emision < '2026-01-01'. NO uses EXTRACT(MONTH) para rangos.
- Si no se especifica año, infiere el año más lógico: si el mes pedido es menor o igual al mes actual, usa el año actual; si el mes pedido es mayor al mes actual (mes aún no ha llegado en este año), usa el año anterior (EXTRACT(YEAR FROM CURRENT_DATE) - 1). Por ejemplo, en marzo de 2026, noviembre corresponde a 2025.
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
            "¿Cuáles facturas están totalmente pagadas?",
            "Facturas parcialmente pagadas con saldo pendiente",
            "¿Qué facturas no tienen complemento de pago?",
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
    def _normalize_question_dates(self, question: str) -> str:
        """Usa la IA para normalizar expresiones de fecha abreviadas/compactas.

        Convierte variantes como 'feb26', 'abr25 a nov25', 'febraur 26' a su
        forma canónica 'febrero 2026', 'abril 2025 a noviembre 2025', etc.
        Modelos pequeños como gpt-4o-mini son suficientes — la tarea es trivial.
        Devuelve la pregunta original si la IA falla o no hay cambio.
        """
        _prompt = (
            "Eres un normalizador de fechas en español. Reescribe ÚNICAMENTE las "
            "expresiones de fecha/mes/año de la oración del usuario, expandiéndolas "
            "a su forma completa (nombre de mes completo + año de 4 dígitos). "
            "No cambies nada más de la oración. No expliques nada. Devuelve solo la "
            "oración reescrita.\n\n"
            "Ejemplos:\n"
            "- 'feb26 a nov26' → 'febrero 2026 a noviembre 2026'\n"
            "- 'abr25 a nov 25' → 'abril 2025 a noviembre 2025'\n"
            "- 'ventas ene24 a dic24' → 'ventas enero 2024 a diciembre 2024'\n"
            "- 'febraur26' → 'febrero 2026'\n"
            "- 'ventas de 2025' → 'ventas de 2025'\n"
        )
        try:
            resp = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": _prompt},
                    {"role": "user", "content": question},
                ],
                temperature=0.0,
                max_tokens=150,
            )
            normalized = resp.choices[0].message.content.strip()
            if normalized and normalized != question:
                logger.info(f"Fecha normalizada por IA: '{question}' → '{normalized}'")
            return normalized or question
        except Exception:
            return question

    def generate_sql(self, question: str, empresa_id: Optional[str] = None,
                       sovereign_context: str = "",
                       periodo_soberano: Optional[dict] = None) -> str:
        """
        Genera SQL a partir de una pregunta en lenguaje natural.

        Args:
            question: Pregunta en español
            empresa_id: UUID de empresa para filtrar (opcional)
            sovereign_context: Contexto temporal soberano pre-inyectado
            periodo_soberano: Dict con desde/hasta_excl del slider soberano.
                              Si se provee, se usa como filtro determinista y
                              se omite _ensure_month_filter.

        Returns:
            Query SQL generado
        """
        # Normalizar expresiones de fecha abreviadas/compactas con IA
        # (ej: 'feb26 a nov26' → 'febrero 2026 a noviembre 2026')
        question = self._normalize_question_dates(question)

        system_prompt = self._build_system_prompt(empresa_id, sovereign_context=sovereign_context)

        # ── Cuando hay período soberano, forzar al modelo a usar fechas exactas ──
        # Inyectamos instrucción en el mensaje del usuario para que el modelo
        # NUNCA genere EXTRACT(MONTH/YEAR) y use siempre fecha_emision >= / <
        user_message = question
        if periodo_soberano:
            _desde = periodo_soberano.get("desde", "")
            _hasta = periodo_soberano.get("hasta_excl", "")
            user_message = (
                f"[FILTRO OBLIGATORIO: fecha_emision >= '{_desde}' AND fecha_emision < '{_hasta}'. "
                f"NUNCA uses EXTRACT(MONTH FROM fecha_emision) ni EXTRACT(YEAR FROM fecha_emision). "
                f"Usa SIEMPRE el rango de fechas exacto indicado.]\n\n{question}"
            )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.0,  # Determinístico para SQL
                max_tokens=800,
            )

            raw_sql = response.choices[0].message.content.strip()

            # Limpiar el SQL (remover markdown code blocks si existen)
            sql = self._clean_sql(raw_sql)

            # ── Filtro de fecha: soberano tiene prioridad absoluta ──────────
            # _apply_sovereign_filter actúa como red de seguridad aunque el modelo
            # ya debería haber usado el rango correcto por la instrucción de arriba
            if periodo_soberano:
                sql = self._apply_sovereign_filter(sql, periodo_soberano)
            else:
                # Garantizar que si se mencionó un mes, el filtro esté en el SQL
                sql = self._ensure_month_filter(question, sql)

            # ── Filtro de perfil soberano (tipo comprobante + método pago) ─
            # Se aplica siempre que haya un perfil activo, como segunda red de seguridad
            _active_profile = getattr(self, "_active_sovereign_profile", None)
            if _active_profile and _apply_profile_filter:
                sql = _apply_profile_filter(sql, _active_profile)

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

    def _build_system_prompt(self, empresa_id: Optional[str] = None, sovereign_context: str = "") -> str:
        """Construye el system prompt para generación de SQL."""
        empresa_filter = ""
        if empresa_id:
            empresa_filter = f"""
IMPORTANTE: Filtra SIEMPRE por empresa_id = '{empresa_id}' en las tablas que tengan empresa_id.
"""

        return f"""{sovereign_context}Eres un experto en SQL PostgreSQL para un sistema de facturación electrónica CFDI de México.

Tu ÚNICA tarea es generar una consulta SQL SELECT válida a partir de la pregunta del usuario.

REGLAS ESTRICTAS:
1. Solo genera UNA sentencia SELECT. NUNCA INSERT, UPDATE, DELETE, DROP, ALTER, CREATE.
2. Siempre incluye LIMIT {self.max_rows} para evitar resultados excesivos.
3. Usa alias descriptivos en español para las columnas del resultado.
4. Formatea montos con 2 decimales.
5. Para montos multi-moneda, normaliza a MXN: total * COALESCE(tipo_cambio, 1).
6. Ordena resultados de forma lógica (generalmente por monto DESC o fecha DESC).
7. Usa DATE_TRUNC para agrupaciones por periodo.
8. Para porcentajes, calcula con ROUND(x * 100.0 / total, 2).
9. Responde SOLO con la consulta SQL, sin explicación ni markdown. NO uses emojis ni caracteres especiales.
10. SIEMPRE intenta generar una consulta SQL válida. NUNCA generes el fallback de "Pregunta no compatible". Si la pregunta es genérica (ej: "qué gráficas me ofreces", "qué estadísticas tienes", "qué puedes hacer", "muéstrame análisis"), genera un resumen estadístico completo de cfdi_ventas con COUNT, AVG, MIN, MAX, STDDEV, PERCENTILE_CONT(0.25), PERCENTILE_CONT(0.5), PERCENTILE_CONT(0.75) sobre el campo total. Si la pregunta es sobre capacidades o ayuda, genera igualmente ese resumen estadístico como demostración.
11. Cuando pregunten por "empresas", "clientes" o "quién compró", busca en receptor_nombre de cfdi_ventas.
12. Para filtros de fecha USA SIEMPRE fecha_emision >= 'YYYY-MM-DD' AND fecha_emision < 'YYYY-MM-DD'. NUNCA uses EXTRACT(MONTH FROM fecha_emision) ni EXTRACT(YEAR FROM fecha_emision) para filtrar rangos. EXTRACT solo se permite en el SELECT para agrupar (ej: DATE_TRUNC('month', fecha_emision)).
  Mapeo de mes a número (solo para referencia interna): enero/ene=1, febrero/feb=2, marzo/mar=3, abril/abr=4, mayo/may=5, junio/jun=6, julio/jul=7, agosto/ago=8, septiembre/sep/sept=9, octubre/oct=10, noviembre/nov=11, diciembre/dic=12.

**PATRÓN OBLIGATORIO — Porcentaje de ventas mes a mes:**
Cuando el usuario pida "porcentaje de ventas mes a mes" o "distribución mensual" o "pay/pie por mes", usa EXACTAMENTE este patrón:
```sql
WITH ventas_mes AS (
  SELECT DATE_TRUNC('month', fecha_emision) AS mes,
         SUM(total * COALESCE(tipo_cambio, 1)) AS total_mxn
  FROM cfdi_ventas
  WHERE empresa_id = '<empresa_id>'
    AND fecha_emision >= 'FECHA_INICIO' AND fecha_emision < 'FECHA_FIN'
  GROUP BY 1
)
SELECT mes,
       ROUND(total_mxn::numeric, 2) AS ventas,
       ROUND(total_mxn * 100.0 / SUM(total_mxn) OVER (), 2) AS porcentaje
FROM ventas_mes
ORDER BY mes;
```
NUNCA pongas ORDER BY dentro de la CTE ventas_mes (PostgreSQL no lo permite en CTEs con window functions). El ORDER BY va solo en el SELECT final.
13. Para estadísticas usa funciones de PostgreSQL: AVG() para promedio/media, PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY col) para mediana, STDDEV() o STDDEV_POP() para desviación estándar, VARIANCE() para varianza, MIN() y MAX() para rango, MODE() WITHIN GROUP (ORDER BY col) para moda.
14. Cuando pidan "estadísticas", "resumen estadístico" o "análisis estadístico", genera una consulta que incluya COUNT, AVG, MIN, MAX, STDDEV y PERCENTILE_CONT(0.5) del campo numérico relevante.
15. Para percentiles usa PERCENTILE_CONT(0.25/0.50/0.75) WITHIN GROUP (ORDER BY columna).
16. Redondea resultados estadísticos con ROUND(valor, 2).
**CRÍTICO PERCENTILE_CONT**: NUNCA uses PERCENTILE_CONT() o MODE() con OVER(). Son "ordered-set aggregates" y PostgreSQL NO soporta OVER() con ellos. Si necesitas percentiles junto con window functions, usa una CTE: primero calcula el percentil global con GROUP BY, luego haz JOIN o usa la CTE en el SELECT principal. Ejemplo correcto: WITH stats AS (SELECT ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY total)::numeric, 2) AS mediana FROM cfdi_ventas) SELECT v.*, s.mediana FROM cfdi_ventas v CROSS JOIN stats s;

**CRÍTICO CROSS JOIN CON AGREGADOS**: Cuando hagas CROSS JOIN (o FROM a, b) entre una CTE de detalle y una CTE de total, NUNCA uses la columna del total directamente junto con un agregado. Usa MAX() o MIN() para "aplanar" el escalar. INCORRECTO: `SELECT SUM(a.val) / b.total FROM a, b` → ERROR PostgreSQL. CORRECTO: `SELECT SUM(a.val) / MAX(b.total) FROM a, b`. Alternativa aún mejor: usa subquery escalar: `SELECT SUM(a.val) / (SELECT total FROM totales) FROM detalle_cte a`.

REGLAS AVANZADAS DE ANALYTICS:
17. TIME INTELLIGENCE: Para comparaciones periodo a periodo usa LAG() OVER (ORDER BY periodo). Para crecimiento: ROUND((actual - anterior) * 100.0 / NULLIF(anterior, 0), 2) AS crecimiento_pct. Para acumulados usa SUM() OVER (ORDER BY mes ROWS UNBOUNDED PRECEDING). Para promedios móviles usa AVG() OVER (ORDER BY mes ROWS BETWEEN 2 PRECEDING AND CURRENT ROW).
18. WINDOW FUNCTIONS: Usa ROW_NUMBER(), RANK(), DENSE_RANK() para rankings. Usa LAG()/LEAD() para comparar con periodo anterior/siguiente. Usa NTILE(4) para cuartiles de clientes. Usa SUM() OVER (PARTITION BY ... ORDER BY ...) para running totals por grupo.
**CRÍTICO**: NUNCA combines GROUP BY con window functions en el mismo SELECT. Cuando necesites ambos, usa una CTE (WITH clause): primero agrupa los datos en el WITH, luego aplica window functions en el SELECT principal. Ejemplo: WITH datos_agregados AS (SELECT mes, SUM(total) AS total FROM tabla GROUP BY mes) SELECT mes, total, LAG(total) OVER (ORDER BY mes) FROM datos_agregados;
19. ANÁLISIS ABC / PARETO: Para clasificar clientes A/B/C por facturación, calcula el % acumulado con SUM(total) OVER (ORDER BY total DESC) / SUM(total) OVER (). Clientes A = hasta 80% acumulado, B = 80-95%, C = resto. Usa CASE WHEN para asignar categoría.
20. SEGMENTACIÓN RFM: Recency = dias desde última compra (CURRENT_DATE - MAX(fecha_emision)). Frequency = COUNT de facturas. Monetary = SUM(total). Usa NTILE(5) para puntuar cada dimensión 1-5. Score RFM = R*100 + F*10 + M.
21. DETECCIÓN DE ANOMALÍAS: Para outliers usa Z-score: (valor - AVG(valor) OVER()) / NULLIF(STDDEV(valor) OVER(), 0). Valores con |z| > 2 son anomalías. También detecta facturas inusualmente altas/bajas respecto al promedio del cliente.
22. CASH FLOW / COBRANZA: Para proyección usa cfdi_pagos. DSO (Days Sales Outstanding) = SUM(saldo_insoluto) / (SUM(total vendido) / dias_periodo). Tasa de cobro = SUM(monto_pagado) / SUM(total facturado). Antigüedad = CURRENT_DATE - fecha_emision para facturas PPD sin pago completo.
23. CONCENTRACIÓN: Para riesgo de concentración calcula % que representa cada cliente del total. Índice Herfindahl = SUM(share^2). Si un cliente > 30% = alerta alta, > 15% = media.
24. CRECIMIENTO: Para tasas de crecimiento MoM/YoY, compara periodos con LAG. CAGR = POWER(ultimo/primero, 1.0/n_periodos) - 1. Velocidad = pendiente de la regresión lineal.
25. REPORTES CON GRÁFICAS: CRÍTICO — Cuando el usuario pide "reporte con graficos", "reporte ejecutivo", "reporte CFO", "dame un reporte", "informe ejecutivo" o cualquier variante de reporte/informe, NUNCA generes una sola fila agregada. SIEMPRE genera desglose con múltiples filas para que se puedan visualizar en gráficas. Por ejemplo:
  - "reporte ejecutivo enero 2026" → desglose por DÍA o por CLIENTE (múltiples filas)
  - "reporte CFO con graficos" → top clientes con su facturación (múltiples filas) 
  - "dame un reporte de ventas" → desglose diario o por cliente
  Usa GROUP BY con la dimensión más relevante (fecha/día, cliente, producto, concepto) para generar MÚLTIPLES filas graficables. Si no es claro, desglosar por receptor_nombre (cliente) con COUNT y SUM ordenado DESC.

26. FACTURA vs COMPLEMENTO DE PAGO — **CRÍTICO ANTI-DUPLICACIÓN**: 
  - cfdi_ventas = FACTURAS (tipo_comprobante='I') = monto a COBRAR (origen de la venta)
  - cfdi_pagos = COMPLEMENTOS DE PAGO = pagos RECIBIDOS que se relacionan con facturas vía cfdi_pagos.cfdi_venta_uuid → cfdi_ventas.uuid_sat
  - **NUNCA sumes facturas + complementos** → esto duplica los montos. Son EVENTOS DISTINTOS: uno registra la venta, el otro el pago.
  - Para CARTERA (cuentas por cobrar): usa cfdi_ventas LEFT JOIN cfdi_pagos y calcula saldo_insoluto de cfdi_pagos o (total - COALESCE(monto_pagado, 0)).
  - Para FACTURACIÓN total: suma SOLO cfdi_ventas.total (NO incluyas cfdi_pagos).
  - Para COBRANZA total: suma SOLO cfdi_pagos.monto_pagado (NO incluyas cfdi_ventas).
  - Para ANÁLISIS de flujo: separa en CTEs: WITH facturado AS (...cfdi_ventas...), cobrado AS (...cfdi_pagos...) SELECT ...
  - El campo cfdi_pagos.saldo_insoluto indica lo que FALTA POR COBRAR de la factura relacionada.
  - Facturas con metodo_pago='PPD' (pago diferido) requieren matching con cfdi_pagos para saber qué está pagado.

28. PUE vs PPD — **CRÍTICO PARA CONSULTAS DE FACTURAS PAGADAS/NO PAGADAS**:
  - metodo_pago='PUE' (Pago en Una Exhibición) = la factura FUE PAGADA al momento de la venta. NO necesita complemento de pago. Es pago de contado.
  - metodo_pago='PPD' (Pago en Parcialidades o Diferido) = la factura es a CRÉDITO. Necesita complemento(s) de pago para demostrar cobro.
  
  Por lo tanto:
  - "FACTURAS PAGADAS" = metodo_pago='PUE' (todas son pagadas por definición) + metodo_pago='PPD' que tengan complemento con saldo_insoluto <= 0.01
  - "FACTURAS NO PAGADAS" = SOLO metodo_pago='PPD' sin complemento (las PUE NUNCA son "no pagadas")
  - "FACTURAS PARCIALMENTE PAGADAS" = SOLO metodo_pago='PPD' con complemento pero saldo_insoluto > 0
  
  QUERY PATTERNS:
  - Pagadas: WHERE v.metodo_pago = 'PUE' OR (v.metodo_pago = 'PPD' AND p.uuid_complemento IS NOT NULL AND saldo_insoluto <= 0.01)
  - No pagadas: WHERE v.metodo_pago = 'PPD' AND p.uuid_complemento IS NULL
  - Parciales: WHERE v.metodo_pago = 'PPD' AND p.uuid_complemento IS NOT NULL AND saldo_insoluto > 0.01

27. CONCILIACIÓN DE DATOS INCOMPLETOS — **CRÍTICO PARA BASES DE DATOS PARCIALES**:
  La base de datos puede estar en proceso de carga y NO tener todos los registros. Esto genera dos escenarios:
  
  **A) COMPLEMENTOS HUÉRFANOS** (hay pago pero NO factura):
  - Si existe cfdi_pagos.cfdi_venta_uuid pero NO existe en cfdi_ventas.uuid_sat → complemento huérfano
  - **NEVER incluir estos complementos en análisis de cobranza/ventas** → datos no confiables
  - Query pattern: INNER JOIN en lugar de LEFT JOIN para excluirlos automáticamente
  - Para detectarlos: SELECT p.* FROM cfdi_pagos p LEFT JOIN cfdi_ventas v ON p.cfdi_venta_uuid = v.uuid_sat WHERE v.uuid_sat IS NULL
  
  **B) FACTURAS SIN COMPLEMENTO** (hay factura pero NO pago):
  - Si existe cfdi_ventas pero NO tiene cfdi_pagos relacionado → puede significar DOS cosas:
    1. **Realmente está pendiente de cobro** (no se ha pagado)
    2. **Ya se pagó pero el complemento no está cargado aún** en la BD
  - **NO asumir que está 100% pendiente** → marcar como "Pendiente de conciliar"
  - En reportes de cartera, agregar columna: tiene_complemento (BOOLEAN) para distinguir
  - Query pattern: LEFT JOIN y validar si p.uuid_complemento IS NULL para marcar como no_conciliado
  
  **REGLAS APLICADAS**:
  - Para VENTAS TOTALES: usa SOLO cfdi_ventas (la factura es la fuente de verdad)
  - Para COBRANZA REAL: usa cfdi_pagos INNER JOIN cfdi_ventas (solo pagos con factura válida)
  - Para CARTERA: usa cfdi_ventas LEFT JOIN cfdi_pagos con flag de conciliación
  - Para AUDITORÍA: identifica huérfanos con LEFT JOIN ... WHERE IS NULL en ambas direcciones
  - Para FACTURAS PAGADAS: incluir PUE (siempre pagadas) + PPD con complemento y saldo_insoluto <= 0.01
  - Para FACTURAS SIN PAGAR: SOLO PPD sin complemento (LEFT JOIN WHERE p.uuid_complemento IS NULL AND v.metodo_pago = 'PPD')
  - Para FACTURAS PARCIALMENTE PAGADAS: PPD con complemento pero SUM(monto_pagado) < total
{empresa_filter}

{SCHEMA_CONTEXT}

REGLA CRÍTICA — KPIs vs Estadísticas:
- "kpis", "kpis comerciales", "indicadores", "dashboard", "resumen ejecutivo", "métricas de negocio" → genera UNA CTE con múltiples indicadores de negocio en FILAS separadas (kpi_nombre, valor, unidad). NUNCA generes estadísticas (AVG, STDDEV, percentiles) para estas preguntas.
- "estadísticas", "resumen estadístico", "distribución" → genera AVG, STDDEV, percentiles como columnas en 1 fila.

EJEMPLOS:
Pregunta: dame kpis comerciales
SQL: WITH mes_activo AS (SELECT DATE_TRUNC('month', MAX(fecha_emision)) AS mes_ref FROM cfdi_ventas), ventas_mes AS (SELECT COUNT(*) AS facturas_mes, ROUND(SUM(total * COALESCE(tipo_cambio, 1)), 2) AS facturacion_mes, COUNT(DISTINCT receptor_rfc) AS clientes_activos_mes FROM cfdi_ventas CROSS JOIN mes_activo WHERE DATE_TRUNC('month', fecha_emision) = mes_activo.mes_ref), ventas_mes_ant AS (SELECT ROUND(SUM(total * COALESCE(tipo_cambio, 1)), 2) AS facturacion_mes_ant FROM cfdi_ventas CROSS JOIN mes_activo WHERE DATE_TRUNC('month', fecha_emision) = mes_activo.mes_ref - INTERVAL '1 month'), ventas_anio AS (SELECT ROUND(SUM(total * COALESCE(tipo_cambio, 1)), 2) AS facturacion_anio, COUNT(DISTINCT receptor_rfc) AS clientes_totales FROM cfdi_ventas CROSS JOIN mes_activo WHERE EXTRACT(YEAR FROM fecha_emision) = EXTRACT(YEAR FROM mes_activo.mes_ref)) SELECT 'Facturación del mes' AS kpi, vm.facturacion_mes::text AS valor, 'MXN' AS unidad FROM ventas_mes vm UNION ALL SELECT 'Facturas emitidas (mes)', vm.facturas_mes::text, 'facturas' FROM ventas_mes vm UNION ALL SELECT 'Clientes activos (mes)', vm.clientes_activos_mes::text, 'clientes' FROM ventas_mes vm UNION ALL SELECT 'Facturación acumulada (año)', va.facturacion_anio::text, 'MXN' FROM ventas_anio va UNION ALL SELECT 'Clientes únicos (año)', va.clientes_totales::text, 'clientes' FROM ventas_anio va UNION ALL SELECT 'Ticket promedio (mes)', ROUND(vm.facturacion_mes / NULLIF(vm.facturas_mes, 0), 2)::text, 'MXN/factura' FROM ventas_mes vm UNION ALL SELECT 'Crecimiento vs mes anterior', ROUND((vm.facturacion_mes - vma.facturacion_mes_ant) * 100.0 / NULLIF(vma.facturacion_mes_ant, 0), 1)::text, '%' FROM ventas_mes vm, ventas_mes_ant vma;

Pregunta: kpis de ventas
SQL: WITH mes_activo AS (SELECT DATE_TRUNC('month', MAX(fecha_emision)) AS mes_ref FROM cfdi_ventas), ventas_mes AS (SELECT COUNT(*) AS facturas_mes, ROUND(SUM(total * COALESCE(tipo_cambio, 1)), 2) AS facturacion_mes, COUNT(DISTINCT receptor_rfc) AS clientes_activos_mes FROM cfdi_ventas CROSS JOIN mes_activo WHERE DATE_TRUNC('month', fecha_emision) = mes_activo.mes_ref), ventas_mes_ant AS (SELECT ROUND(SUM(total * COALESCE(tipo_cambio, 1)), 2) AS facturacion_mes_ant FROM cfdi_ventas CROSS JOIN mes_activo WHERE DATE_TRUNC('month', fecha_emision) = mes_activo.mes_ref - INTERVAL '1 month'), ventas_anio AS (SELECT ROUND(SUM(total * COALESCE(tipo_cambio, 1)), 2) AS facturacion_anio, COUNT(DISTINCT receptor_rfc) AS clientes_totales FROM cfdi_ventas CROSS JOIN mes_activo WHERE EXTRACT(YEAR FROM fecha_emision) = EXTRACT(YEAR FROM mes_activo.mes_ref)) SELECT 'Facturación del mes' AS kpi, vm.facturacion_mes::text AS valor, 'MXN' AS unidad FROM ventas_mes vm UNION ALL SELECT 'Facturas emitidas (mes)', vm.facturas_mes::text, 'facturas' FROM ventas_mes vm UNION ALL SELECT 'Clientes activos (mes)', vm.clientes_activos_mes::text, 'clientes' FROM ventas_mes vm UNION ALL SELECT 'Facturación acumulada (año)', va.facturacion_anio::text, 'MXN' FROM ventas_anio va UNION ALL SELECT 'Clientes únicos (año)', va.clientes_totales::text, 'clientes' FROM ventas_anio va UNION ALL SELECT 'Ticket promedio (mes)', ROUND(vm.facturacion_mes / NULLIF(vm.facturas_mes, 0), 2)::text, 'MXN/factura' FROM ventas_mes vm UNION ALL SELECT 'Crecimiento vs mes anterior', ROUND((vm.facturacion_mes - vma.facturacion_mes_ant) * 100.0 / NULLIF(vma.facturacion_mes_ant, 0), 1)::text, '%' FROM ventas_mes vm, ventas_mes_ant vma;

Pregunta: ¿Cuánto se facturó este mes?
SQL: SELECT SUM(total) AS total_facturado, moneda FROM cfdi_ventas WHERE DATE_TRUNC('month', fecha_emision) = DATE_TRUNC('month', CURRENT_DATE) GROUP BY moneda LIMIT {self.max_rows};

Pregunta: Top 5 clientes por facturación
SQL: SELECT receptor_nombre AS cliente, COUNT(*) AS num_facturas, SUM(total * COALESCE(tipo_cambio, 1)) AS total_mxn FROM cfdi_ventas WHERE tipo_comprobante = 'I' AND total > 0 GROUP BY receptor_nombre ORDER BY total_mxn DESC LIMIT 5;

Pregunta: Ventas mensuales de este año
SQL: SELECT DATE_TRUNC('month', fecha_emision) AS mes, COUNT(*) AS facturas, SUM(total * COALESCE(tipo_cambio, 1)) AS total_mxn FROM cfdi_ventas WHERE tipo_comprobante = 'I' AND total > 0 AND EXTRACT(YEAR FROM fecha_emision) = EXTRACT(YEAR FROM CURRENT_DATE) GROUP BY mes ORDER BY mes LIMIT {self.max_rows};

Pregunta: Facturación en el tiempo / por mes / mensual / histórica
SQL: SELECT DATE_TRUNC('month', fecha_emision) AS mes, COUNT(*) AS num_facturas, ROUND(SUM(total * COALESCE(tipo_cambio, 1)), 2) AS facturacion_total FROM cfdi_ventas WHERE tipo_comprobante = 'I' AND total > 0 GROUP BY mes ORDER BY mes LIMIT {self.max_rows};

Pregunta: Muestra facturación en el tiempo a manera de gráfico de barras
SQL: SELECT DATE_TRUNC('month', fecha_emision) AS mes, COUNT(*) AS num_facturas, ROUND(SUM(total * COALESCE(tipo_cambio, 1)), 2) AS facturacion_total FROM cfdi_ventas WHERE tipo_comprobante = 'I' AND total > 0 GROUP BY mes ORDER BY mes LIMIT {self.max_rows};

Pregunta: ¿Cuál empresa compró menos en enero?
SQL: SELECT receptor_nombre AS cliente, COUNT(*) AS num_facturas, SUM(total) AS total_comprado FROM cfdi_ventas WHERE EXTRACT(MONTH FROM fecha_emision) = 1 AND EXTRACT(YEAR FROM fecha_emision) = EXTRACT(YEAR FROM CURRENT_DATE) GROUP BY receptor_nombre ORDER BY total_comprado ASC LIMIT 1;

Pregunta: pay de noviembre
SQL: SELECT receptor_nombre AS cliente, COUNT(*) AS facturas, ROUND(SUM(total * COALESCE(tipo_cambio, 1)), 2) AS total FROM cfdi_ventas WHERE EXTRACT(MONTH FROM fecha_emision) = 11 AND EXTRACT(YEAR FROM fecha_emision) = EXTRACT(YEAR FROM CURRENT_DATE) GROUP BY receptor_nombre ORDER BY total DESC LIMIT 15;

Pregunta: gráfica de pie de noviembre
SQL: SELECT receptor_nombre AS cliente, COUNT(*) AS facturas, ROUND(SUM(total * COALESCE(tipo_cambio, 1)), 2) AS total FROM cfdi_ventas WHERE EXTRACT(MONTH FROM fecha_emision) = 11 AND EXTRACT(YEAR FROM fecha_emision) = EXTRACT(YEAR FROM CURRENT_DATE) GROUP BY receptor_nombre ORDER BY total DESC LIMIT 15;

Pregunta: dona de ventas en oct
SQL: SELECT receptor_nombre AS cliente, ROUND(SUM(total * COALESCE(tipo_cambio, 1)), 2) AS ventas FROM cfdi_ventas WHERE EXTRACT(MONTH FROM fecha_emision) = 10 AND EXTRACT(YEAR FROM fecha_emision) = EXTRACT(YEAR FROM CURRENT_DATE) GROUP BY receptor_nombre ORDER BY ventas DESC LIMIT 15;

Pregunta: pastel de clientes de dic
SQL: SELECT receptor_nombre AS cliente, ROUND(SUM(total * COALESCE(tipo_cambio, 1)), 2) AS ventas FROM cfdi_ventas WHERE EXTRACT(MONTH FROM fecha_emision) = 12 AND EXTRACT(YEAR FROM fecha_emision) = EXTRACT(YEAR FROM CURRENT_DATE) GROUP BY receptor_nombre ORDER BY ventas DESC LIMIT 15;

Pregunta: ventas de nov
SQL: SELECT receptor_nombre AS cliente, COUNT(*) AS facturas, ROUND(SUM(total * COALESCE(tipo_cambio, 1)), 2) AS total_vendido FROM cfdi_ventas WHERE EXTRACT(MONTH FROM fecha_emision) = 11 AND EXTRACT(YEAR FROM fecha_emision) = EXTRACT(YEAR FROM CURRENT_DATE) GROUP BY receptor_nombre ORDER BY total_vendido DESC LIMIT {self.max_rows};

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
SQL: WITH ventas_mes AS (SELECT DATE_TRUNC('month', fecha_emision) AS mes, SUM(total * COALESCE(tipo_cambio, 1)) AS total_mxn FROM cfdi_ventas GROUP BY mes ORDER BY mes) SELECT mes, ROUND(total_mxn, 2) AS ventas, ROUND(LAG(total_mxn) OVER (ORDER BY mes), 2) AS mes_anterior, ROUND((total_mxn - LAG(total_mxn) OVER (ORDER BY mes)) * 100.0 / NULLIF(LAG(total_mxn) OVER (ORDER BY mes), 0), 2) AS crecimiento_pct FROM ventas_mes LIMIT {self.max_rows};

Pregunta: Reporte ejecutivo mensual con todas las estadísticas y crecimiento
SQL: WITH ventas_mes AS (SELECT DATE_TRUNC('month', fecha_emision) AS mes, COUNT(*) AS num_facturas, ROUND(SUM(total * COALESCE(tipo_cambio, 1)), 2) AS facturacion_total, ROUND(AVG(total * COALESCE(tipo_cambio, 1)), 2) AS promedio_factura, ROUND(STDDEV(total * COALESCE(tipo_cambio, 1)), 2) AS desviacion_estandar, ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY total * COALESCE(tipo_cambio, 1))::numeric, 2) AS mediana_factura FROM cfdi_ventas GROUP BY mes ORDER BY mes) SELECT mes, num_facturas, facturacion_total, promedio_factura, desviacion_estandar, mediana_factura, ROUND(SUM(facturacion_total) OVER (ORDER BY mes ROWS UNBOUNDED PRECEDING), 2) AS acumulado_ventas, ROUND((facturacion_total - LAG(facturacion_total) OVER (ORDER BY mes)) * 100.0 / NULLIF(LAG(facturacion_total) OVER (ORDER BY mes), 0), 2) AS crecimiento_mensual_pct FROM ventas_mes LIMIT {self.max_rows};

Pregunta: Ventas acumuladas por mes este año
SQL: SELECT DATE_TRUNC('month', fecha_emision) AS mes, SUM(total * COALESCE(tipo_cambio, 1)) AS ventas_mes, SUM(SUM(total * COALESCE(tipo_cambio, 1))) OVER (ORDER BY DATE_TRUNC('month', fecha_emision) ROWS UNBOUNDED PRECEDING) AS acumulado FROM cfdi_ventas WHERE EXTRACT(YEAR FROM fecha_emision) = EXTRACT(YEAR FROM CURRENT_DATE) GROUP BY mes ORDER BY mes LIMIT {self.max_rows};

Pregunta: Promedio móvil de 3 meses de facturación
SQL: WITH ventas_mes AS (SELECT DATE_TRUNC('month', fecha_emision) AS mes, SUM(total * COALESCE(tipo_cambio, 1)) AS total_mxn FROM cfdi_ventas GROUP BY mes ORDER BY mes) SELECT mes, ROUND(total_mxn, 2) AS ventas, ROUND(AVG(total_mxn) OVER (ORDER BY mes ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 2) AS promedio_movil_3m FROM ventas_mes LIMIT {self.max_rows};

Pregunta: Ranking de clientes por facturación
SQL: SELECT receptor_nombre AS cliente, SUM(total * COALESCE(tipo_cambio, 1)) AS total_mxn, RANK() OVER (ORDER BY SUM(total * COALESCE(tipo_cambio, 1)) DESC) AS ranking, COUNT(*) AS facturas FROM cfdi_ventas WHERE tipo_comprobante = 'I' AND total > 0 GROUP BY receptor_nombre ORDER BY ranking LIMIT {self.max_rows};

Pregunta: Clasificación ABC de clientes (Pareto)
SQL: WITH clientes AS (SELECT receptor_nombre AS cliente, SUM(total * COALESCE(tipo_cambio, 1)) AS total_mxn FROM cfdi_ventas WHERE tipo_comprobante = 'I' AND total > 0 GROUP BY receptor_nombre), acumulado AS (SELECT cliente, total_mxn, SUM(total_mxn) OVER (ORDER BY total_mxn DESC) AS acum, SUM(total_mxn) OVER () AS gran_total FROM clientes) SELECT cliente, ROUND(total_mxn, 2) AS total_mxn, ROUND(acum * 100.0 / gran_total, 2) AS pct_acumulado, CASE WHEN acum * 100.0 / gran_total <= 80 THEN 'A' WHEN acum * 100.0 / gran_total <= 95 THEN 'B' ELSE 'C' END AS clasificacion_abc FROM acumulado ORDER BY total_mxn DESC LIMIT {self.max_rows};

Pregunta: Segmentación RFM de clientes
SQL: WITH rfm AS (SELECT receptor_nombre AS cliente, (CURRENT_DATE - MAX(fecha_emision::date)) AS recencia_dias, COUNT(*) AS frecuencia, ROUND(SUM(total * COALESCE(tipo_cambio, 1)), 2) AS monetario FROM cfdi_ventas WHERE tipo_comprobante = 'I' AND total > 0 GROUP BY receptor_nombre), scored AS (SELECT cliente, recencia_dias, frecuencia, monetario, NTILE(5) OVER (ORDER BY recencia_dias DESC) AS r_score, NTILE(5) OVER (ORDER BY frecuencia ASC) AS f_score, NTILE(5) OVER (ORDER BY monetario ASC) AS m_score FROM rfm) SELECT cliente, recencia_dias, frecuencia, monetario, r_score, f_score, m_score, (r_score * 100 + f_score * 10 + m_score) AS rfm_score, CASE WHEN r_score >= 4 AND f_score >= 4 AND m_score >= 4 THEN 'Champions' WHEN r_score >= 3 AND f_score >= 3 THEN 'Leales' WHEN r_score >= 4 AND f_score <= 2 THEN 'Nuevos' WHEN r_score <= 2 AND f_score >= 3 THEN 'En Riesgo' WHEN r_score <= 2 AND f_score <= 2 THEN 'Hibernando' ELSE 'Potenciales' END AS segmento FROM scored ORDER BY rfm_score DESC LIMIT {self.max_rows};

Pregunta: Detectar facturas anómalas (outliers)
SQL: WITH stats AS (SELECT AVG(total) AS media, STDDEV(total) AS desv FROM cfdi_ventas) SELECT v.receptor_nombre AS cliente, v.folio, v.fecha_emision, ROUND(v.total, 2) AS monto, ROUND((v.total - s.media) / NULLIF(s.desv, 0), 2) AS z_score, CASE WHEN ABS((v.total - s.media) / NULLIF(s.desv, 0)) > 3 THEN 'Anomalia Alta' WHEN ABS((v.total - s.media) / NULLIF(s.desv, 0)) > 2 THEN 'Anomalia Media' ELSE 'Normal' END AS clasificacion FROM cfdi_ventas v, stats s WHERE ABS((v.total - s.media) / NULLIF(s.desv, 0)) > 2 ORDER BY z_score DESC LIMIT {self.max_rows};

Pregunta: Concentración de clientes (riesgo)
SQL: WITH totales AS (SELECT receptor_nombre AS cliente, SUM(total * COALESCE(tipo_cambio, 1)) AS total_mxn FROM cfdi_ventas WHERE tipo_comprobante = 'I' AND total > 0 GROUP BY receptor_nombre) SELECT cliente, ROUND(total_mxn, 2) AS total_mxn, ROUND(total_mxn * 100.0 / SUM(total_mxn) OVER (), 2) AS pct_del_total, CASE WHEN total_mxn * 100.0 / SUM(total_mxn) OVER () > 30 THEN 'CRITICO' WHEN total_mxn * 100.0 / SUM(total_mxn) OVER () > 15 THEN 'ALTO' WHEN total_mxn * 100.0 / SUM(total_mxn) OVER () > 5 THEN 'MEDIO' ELSE 'BAJO' END AS nivel_riesgo FROM totales ORDER BY total_mxn DESC LIMIT {self.max_rows};

Pregunta: DSO y tasa de cobro
SQL: WITH facturado AS (SELECT SUM(total * COALESCE(tipo_cambio, 1)) AS total_facturado, COUNT(*) AS n_facturas FROM cfdi_ventas WHERE fecha_emision >= DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '3 months'), cobrado AS (SELECT COALESCE(SUM(monto_pagado), 0) AS total_cobrado FROM cfdi_pagos WHERE fecha_pago >= DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '3 months'), pendiente AS (SELECT COALESCE(SUM(saldo_insoluto), 0) AS saldo_pendiente FROM cfdi_pagos WHERE saldo_insoluto > 0) SELECT ROUND(f.total_facturado, 2) AS facturado_3m, ROUND(c.total_cobrado, 2) AS cobrado_3m, ROUND(c.total_cobrado * 100.0 / NULLIF(f.total_facturado, 0), 2) AS tasa_cobro_pct, ROUND(p.saldo_pendiente, 2) AS saldo_pendiente, ROUND(p.saldo_pendiente / NULLIF(f.total_facturado / 90.0, 0), 1) AS dso_dias FROM facturado f, cobrado c, pendiente p LIMIT 1;

Pregunta: Cartera de clientes con estado de conciliación
SQL: SELECT v.receptor_nombre AS cliente, COUNT(DISTINCT v.uuid_sat) AS num_facturas, ROUND(SUM(v.total * v.tipo_cambio), 2) AS total_facturado, ROUND(COALESCE(SUM(p.monto_pagado), 0), 2) AS total_cobrado, ROUND(SUM(v.total * v.tipo_cambio) - COALESCE(SUM(p.monto_pagado), 0), 2) AS saldo_pendiente, COUNT(p.uuid_complemento) AS facturas_con_complemento, COUNT(DISTINCT v.uuid_sat) - COUNT(p.uuid_complemento) AS facturas_sin_conciliar, CASE WHEN COUNT(p.uuid_complemento) = 0 THEN 'Sin complementos' WHEN COUNT(p.uuid_complemento) < COUNT(DISTINCT v.uuid_sat) THEN 'Conciliación parcial' ELSE 'Conciliado' END AS estado_conciliacion FROM cfdi_ventas v LEFT JOIN cfdi_pagos p ON v.uuid_sat = p.cfdi_venta_uuid WHERE v.metodo_pago = 'PPD' GROUP BY v.receptor_nombre HAVING SUM(v.total * v.tipo_cambio) - COALESCE(SUM(p.monto_pagado), 0) > 0 ORDER BY saldo_pendiente DESC LIMIT {self.max_rows};

Pregunta: Detectar complementos huérfanos (sin factura relacionada)
SQL: SELECT p.uuid_complemento, p.fecha_pago, p.cfdi_venta_uuid AS uuid_factura_referida, ROUND(p.monto_pagado, 2) AS monto, 'COMPLEMENTO HUERFANO - Factura no encontrada en BD' AS alerta FROM cfdi_pagos p LEFT JOIN cfdi_ventas v ON p.cfdi_venta_uuid = v.uuid_sat WHERE v.uuid_sat IS NULL ORDER BY p.fecha_pago DESC LIMIT {self.max_rows};

Pregunta: Facturas pendientes de conciliar (sin complemento)
SQL: SELECT v.receptor_nombre AS cliente, v.folio, v.fecha_emision, ROUND(v.total, 2) AS monto_original, CURRENT_DATE - v.fecha_emision::date AS dias_transcurridos, CASE WHEN p.uuid_complemento IS NULL AND v.metodo_pago = 'PPD' THEN 'PENDIENTE DE CONCILIAR - Puede estar pagado sin complemento registrado' WHEN p.saldo_insoluto > 0 THEN 'PARCIALMENTE PAGADO' ELSE 'OK' END AS estado FROM cfdi_ventas v LEFT JOIN cfdi_pagos p ON v.uuid_sat = p.cfdi_venta_uuid WHERE v.metodo_pago = 'PPD' AND p.uuid_complemento IS NULL ORDER BY dias_transcurridos DESC LIMIT {self.max_rows};

Pregunta: Cobranza real (solo pagos con factura válida)
SQL: SELECT DATE_TRUNC('month', p.fecha_pago) AS mes, COUNT(DISTINCT p.uuid_complemento) AS num_complementos, COUNT(DISTINCT p.cfdi_venta_uuid) AS facturas_cobradas, ROUND(SUM(p.monto_pagado), 2) AS total_cobrado FROM cfdi_pagos p INNER JOIN cfdi_ventas v ON p.cfdi_venta_uuid = v.uuid_sat GROUP BY mes ORDER BY mes DESC LIMIT {self.max_rows};

Pregunta: Auditoría de integridad factura-complemento
SQL: WITH huerfanos_pago AS (SELECT COUNT(*) AS complementos_sin_factura, COALESCE(SUM(monto_pagado), 0) AS monto_sin_factura FROM cfdi_pagos p LEFT JOIN cfdi_ventas v ON p.cfdi_venta_uuid = v.uuid_sat WHERE v.uuid_sat IS NULL), facturas_sin_pago AS (SELECT COUNT(*) AS facturas_sin_complemento, COALESCE(SUM(total), 0) AS monto_sin_complemento FROM cfdi_ventas v LEFT JOIN cfdi_pagos p ON v.uuid_sat = p.cfdi_venta_uuid WHERE v.metodo_pago = 'PPD' AND p.uuid_complemento IS NULL), totales AS (SELECT COUNT(*) AS total_facturas FROM cfdi_ventas UNION ALL SELECT COUNT(*) FROM cfdi_pagos) SELECT ROUND(hp.monto_sin_factura, 2) AS monto_complementos_huerfanos, hp.complementos_sin_factura, ROUND(fs.monto_sin_complemento, 2) AS monto_facturas_sin_conciliar, fs.facturas_sin_complemento, ROUND((hp.complementos_sin_factura + fs.facturas_sin_complemento) * 100.0 / NULLIF((SELECT SUM(total_facturas) FROM totales), 0), 2) AS pct_registros_sin_conciliar FROM huerfanos_pago hp, facturas_sin_pago fs LIMIT {self.max_rows};

Pregunta: Facturas pagadas
SQL: SELECT v.receptor_nombre AS cliente, v.folio, v.serie, v.fecha_emision, ROUND(v.total, 2) AS monto_factura, v.metodo_pago, v.forma_pago, CASE WHEN v.metodo_pago = 'PUE' THEN 'PAGADA (Contado/PUE)' WHEN v.metodo_pago = 'PPD' AND p.uuid_complemento IS NOT NULL AND COALESCE(p.saldo_insoluto, v.total - COALESCE(p.monto_pagado, 0)) <= 0.01 THEN 'PAGADA (Crédito con complemento)' WHEN v.metodo_pago = 'PPD' AND p.uuid_complemento IS NOT NULL THEN 'PAGO PARCIAL' ELSE 'PENDIENTE/SIN CONCILIAR' END AS estado_pago, COALESCE(ROUND(p.monto_pagado, 2), CASE WHEN v.metodo_pago = 'PUE' THEN v.total ELSE 0 END) AS monto_pagado, p.fecha_pago FROM cfdi_ventas v LEFT JOIN cfdi_pagos p ON v.uuid_sat = p.cfdi_venta_uuid WHERE v.metodo_pago = 'PUE' OR (v.metodo_pago = 'PPD' AND p.uuid_complemento IS NOT NULL) ORDER BY v.fecha_emision DESC LIMIT {self.max_rows};

Pregunta: Facturas totalmente pagadas (saldo cero)
SQL: SELECT v.receptor_nombre AS cliente, v.folio, v.serie, v.fecha_emision, ROUND(v.total, 2) AS monto_factura, v.metodo_pago, CASE WHEN v.metodo_pago = 'PUE' THEN 'Contado' ELSE 'Crédito liquidado' END AS tipo_pago, CASE WHEN v.metodo_pago = 'PUE' THEN v.fecha_emision ELSE p.fecha_pago END AS fecha_pago FROM cfdi_ventas v LEFT JOIN cfdi_pagos p ON v.uuid_sat = p.cfdi_venta_uuid WHERE v.metodo_pago = 'PUE' OR (v.metodo_pago = 'PPD' AND p.uuid_complemento IS NOT NULL AND COALESCE(p.saldo_insoluto, 0) <= 0.01) ORDER BY v.fecha_emision DESC LIMIT {self.max_rows};

Pregunta: Facturas parcialmente pagadas (con saldo pendiente)
SQL: SELECT v.receptor_nombre AS cliente, v.folio, v.serie, v.fecha_emision, ROUND(v.total, 2) AS monto_original, ROUND(COALESCE(SUM(p.monto_pagado), 0), 2) AS pagado, ROUND(v.total - COALESCE(SUM(p.monto_pagado), 0), 2) AS saldo_pendiente, ROUND((COALESCE(SUM(p.monto_pagado), 0) * 100.0 / v.total), 1) AS pct_pagado, COUNT(p.uuid_complemento) AS num_parcialidades, MAX(p.fecha_pago) AS ultimo_pago FROM cfdi_ventas v LEFT JOIN cfdi_pagos p ON v.uuid_sat = p.cfdi_venta_uuid WHERE v.metodo_pago = 'PPD' GROUP BY v.receptor_nombre, v.folio, v.serie, v.fecha_emision, v.total HAVING COALESCE(SUM(p.monto_pagado), 0) > 0 AND v.total - COALESCE(SUM(p.monto_pagado), 0) > 0.01 ORDER BY saldo_pendiente DESC LIMIT {self.max_rows};

Pregunta: Facturas sin pagar (pendientes de cobro)
SQL: SELECT v.receptor_nombre AS cliente, v.folio, v.serie, v.fecha_emision, ROUND(v.total, 2) AS monto, v.metodo_pago, CURRENT_DATE - v.fecha_emision::date AS dias_vencidos, CASE WHEN v.metodo_pago = 'PPD' AND p.uuid_complemento IS NULL THEN 'PPD - Sin complemento (posiblemente pendiente o sin conciliar)' ELSE 'Revisar' END AS estado FROM cfdi_ventas v LEFT JOIN cfdi_pagos p ON v.uuid_sat = p.cfdi_venta_uuid WHERE v.metodo_pago = 'PPD' AND p.uuid_complemento IS NULL ORDER BY dias_vencidos DESC LIMIT {self.max_rows};

Pregunta: Resumen de estado de pagos
SQL: SELECT estado_pago, COUNT(*) AS num_facturas, ROUND(SUM(monto), 2) AS monto_total FROM (SELECT v.uuid_sat, v.total AS monto, CASE WHEN v.metodo_pago = 'PUE' THEN 'Pagadas (PUE contado)' WHEN v.metodo_pago = 'PPD' AND p.uuid_complemento IS NOT NULL AND COALESCE(p.saldo_insoluto, v.total - COALESCE(p.monto_pagado, 0)) <= 0.01 THEN 'Pagadas (PPD con complemento)' WHEN v.metodo_pago = 'PPD' AND p.uuid_complemento IS NOT NULL AND COALESCE(p.monto_pagado, 0) > 0 THEN 'Parcialmente pagadas (PPD)' WHEN v.metodo_pago = 'PPD' AND p.uuid_complemento IS NULL THEN 'Sin complemento (PPD pendiente/sin conciliar)' ELSE 'Otros' END AS estado_pago FROM cfdi_ventas v LEFT JOIN cfdi_pagos p ON v.uuid_sat = p.cfdi_venta_uuid) sub GROUP BY estado_pago ORDER BY num_facturas DESC LIMIT {self.max_rows};

Pregunta: Dame PPD diferenciales por color / PPD por cliente diferenciadas / Facturas PPD por estado
SQL: SELECT v.receptor_nombre AS cliente, CASE WHEN p.uuid_complemento IS NOT NULL AND COALESCE(p.saldo_insoluto, v.total - COALESCE(p.monto_pagado, 0)) <= 0.01 THEN 'Pagadas (PPD con complemento)' WHEN p.uuid_complemento IS NOT NULL AND COALESCE(p.monto_pagado, 0) > 0 THEN 'Parcialmente pagadas' WHEN p.uuid_complemento IS NULL THEN 'Sin pagar (PPD sin complemento)' ELSE 'Por revisar' END AS estado_pago, COUNT(*) AS num_facturas, ROUND(SUM(v.total), 2) AS monto_total, ROUND(SUM(v.total) * 100.0 / SUM(SUM(v.total)) OVER (), 2) AS porcentaje FROM cfdi_ventas v LEFT JOIN cfdi_pagos p ON v.uuid_sat = p.cfdi_venta_uuid WHERE v.metodo_pago = 'PPD' GROUP BY v.receptor_nombre, estado_pago ORDER BY estado_pago, monto_total DESC LIMIT {self.max_rows};

Pregunta: PPD sin pagar por cliente con porcentajes / Clientes con facturas PPD pendientes
SQL: SELECT v.receptor_nombre AS cliente, COUNT(*) AS num_facturas, ROUND(SUM(v.total), 2) AS monto_pendiente, ROUND(SUM(v.total) * 100.0 / SUM(SUM(v.total)) OVER (), 2) AS porcentaje, MIN(v.fecha_emision) AS primera_factura, MAX(v.fecha_emision) AS ultima_factura, ROUND(AVG(CURRENT_DATE - v.fecha_emision::date), 0) AS dias_promedio_mora FROM cfdi_ventas v LEFT JOIN cfdi_pagos p ON v.uuid_sat = p.cfdi_venta_uuid WHERE v.metodo_pago = 'PPD' AND p.uuid_complemento IS NULL GROUP BY v.receptor_nombre ORDER BY monto_pendiente DESC LIMIT {self.max_rows};

Pregunta: PPD pagadas por cliente con porcentajes
SQL: SELECT v.receptor_nombre AS cliente, COUNT(*) AS num_facturas, ROUND(SUM(v.total), 2) AS monto_pagado, ROUND(SUM(v.total) * 100.0 / SUM(SUM(v.total)) OVER (), 2) AS porcentaje, MIN(v.fecha_emision) AS primera_factura, MAX(p.fecha_pago) AS ultimo_pago FROM cfdi_ventas v INNER JOIN cfdi_pagos p ON v.uuid_sat = p.cfdi_venta_uuid WHERE v.metodo_pago = 'PPD' AND p.uuid_complemento IS NOT NULL AND COALESCE(p.saldo_insoluto, v.total - COALESCE(p.monto_pagado, 0)) <= 0.01 GROUP BY v.receptor_nombre ORDER BY monto_pagado DESC LIMIT {self.max_rows};

Pregunta: PPD parcialmente pagadas por cliente con porcentajes
SQL: SELECT v.receptor_nombre AS cliente, COUNT(DISTINCT v.uuid_sat) AS num_facturas, ROUND(SUM(v.total), 2) AS monto_original, ROUND(SUM(COALESCE(p.monto_pagado, 0)), 2) AS monto_pagado, ROUND(SUM(v.total - COALESCE(p.monto_pagado, 0)), 2) AS saldo_pendiente, ROUND((SUM(v.total - COALESCE(p.monto_pagado, 0))) * 100.0 / SUM(SUM(v.total - COALESCE(p.monto_pagado, 0))) OVER (), 2) AS porcentaje_pendiente, ROUND(SUM(COALESCE(p.monto_pagado, 0)) * 100.0 / SUM(v.total), 1) AS pct_pagado FROM cfdi_ventas v LEFT JOIN cfdi_pagos p ON v.uuid_sat = p.cfdi_venta_uuid WHERE v.metodo_pago = 'PPD' AND p.uuid_complemento IS NOT NULL AND v.total - COALESCE(p.monto_pagado, 0) > 0.01 GROUP BY v.receptor_nombre HAVING COUNT(p.uuid_complemento) > 0 ORDER BY saldo_pendiente DESC LIMIT {self.max_rows};

Pregunta: Reporte de PPD por empresa / Facturas PPD por cliente / PPD desglosadas por empresa
SQL: SELECT v.receptor_nombre AS cliente, COUNT(*) AS num_facturas, ROUND(SUM(v.total), 2) AS monto_total_ppd, ROUND(SUM(v.total) * 100.0 / SUM(SUM(v.total)) OVER (), 1) AS porcentaje, SUM(CASE WHEN p.uuid_complemento IS NOT NULL AND COALESCE(p.saldo_insoluto, v.total - COALESCE(p.monto_pagado, 0)) <= 0.01 THEN 1 ELSE 0 END) AS facturas_pagadas, SUM(CASE WHEN p.uuid_complemento IS NOT NULL AND COALESCE(p.monto_pagado, 0) > 0 AND COALESCE(p.saldo_insoluto, v.total - COALESCE(p.monto_pagado, 0)) > 0.01 THEN 1 ELSE 0 END) AS facturas_parciales, SUM(CASE WHEN p.uuid_complemento IS NULL THEN 1 ELSE 0 END) AS facturas_pendientes FROM cfdi_ventas v LEFT JOIN cfdi_pagos p ON v.uuid_sat = p.cfdi_venta_uuid WHERE v.metodo_pago = 'PPD' GROUP BY v.receptor_nombre ORDER BY monto_total_ppd DESC LIMIT {self.max_rows};

Pregunta: Reporte ejecutivo de PPD con graficos / Análisis completo de facturas PPD
SQL: WITH resumen_por_estado AS (SELECT CASE WHEN p.uuid_complemento IS NOT NULL AND COALESCE(p.saldo_insoluto, v.total - COALESCE(p.monto_pagado, 0)) <= 0.01 THEN 'Pagadas' WHEN p.uuid_complemento IS NOT NULL AND COALESCE(p.monto_pagado, 0) > 0 THEN 'Parcialmente pagadas' WHEN p.uuid_complemento IS NULL THEN 'Sin pagar' ELSE 'Otros' END AS estado_pago, v.receptor_nombre AS cliente, v.total FROM cfdi_ventas v LEFT JOIN cfdi_pagos p ON v.uuid_sat = p.cfdi_venta_uuid WHERE v.metodo_pago = 'PPD'), por_cliente_estado AS (SELECT cliente, estado_pago, COUNT(*) AS num_facturas, ROUND(SUM(total), 2) AS monto, ROUND(SUM(total) * 100.0 / SUM(SUM(total)) OVER (PARTITION BY estado_pago), 1) AS pct_del_estado FROM resumen_por_estado GROUP BY cliente, estado_pago) SELECT cliente, estado_pago, num_facturas, monto, pct_del_estado FROM por_cliente_estado ORDER BY estado_pago, monto DESC LIMIT {self.max_rows};

Pregunta: ¿Cuáles clientes compran cada vez menos? (tendencia negativa)
SQL: WITH por_trimestre AS (SELECT receptor_nombre AS cliente, DATE_TRUNC('quarter', fecha_emision) AS trimestre, SUM(total * COALESCE(tipo_cambio, 1)) AS total_mxn FROM cfdi_ventas GROUP BY receptor_nombre, trimestre), con_tendencia AS (SELECT cliente, trimestre, total_mxn, LAG(total_mxn) OVER (PARTITION BY cliente ORDER BY trimestre) AS trimestre_anterior FROM por_trimestre) SELECT cliente, trimestre, ROUND(total_mxn, 2) AS ventas_actual, ROUND(trimestre_anterior, 2) AS ventas_anterior, ROUND((total_mxn - trimestre_anterior) * 100.0 / NULLIF(trimestre_anterior, 0), 2) AS cambio_pct FROM con_tendencia WHERE trimestre_anterior IS NOT NULL AND total_mxn < trimestre_anterior ORDER BY cambio_pct ASC LIMIT {self.max_rows};
"""

    def _clean_sql(self, raw: str) -> str:
        """Limpia el SQL de markdown code blocks, whitespace y patrones inválidos."""
        # Remover ```sql ... ```
        sql = re.sub(r'```(?:sql)?\s*', '', raw)
        sql = re.sub(r'```\s*$', '', sql)
        sql = sql.strip()

        # Normalizar operadores Unicode que el modelo puede generar
        sql = sql.replace("≥", ">=").replace("≤", "<=").replace("≠", "<>")

        # --- FIX: PERCENTILE_CONT/MODE con OVER() no es válido en PostgreSQL ---
        # Detectar: PERCENTILE_CONT(...) WITHIN GROUP (...) OVER (...)
        # Esto es un "ordered-set aggregate" y no soporta window functions
        pattern_invalid_percentile = re.compile(
            r'ROUND\s*\(\s*'
            r'(PERCENTILE_CONT\s*\([^)]+\)\s*WITHIN\s+GROUP\s*\([^)]+\))'
            r'(\s*::numeric)?'
            r'\s*,\s*\d+\s*\)'
            r'\s*OVER\s*\([^)]*\)',
            re.IGNORECASE
        )
        if pattern_invalid_percentile.search(sql):
            logger.warning("⚠️ Detectado PERCENTILE_CONT con OVER() — removiendo OVER clause")
            sql = pattern_invalid_percentile.sub(
                lambda m: f"ROUND({m.group(1)}::numeric, 2)",
                sql
            )
        
        # Caso sin ROUND wrapper
        pattern_invalid_percentile2 = re.compile(
            r'(PERCENTILE_CONT\s*\([^)]+\)\s*WITHIN\s+GROUP\s*\([^)]+\))'
            r'\s*OVER\s*\([^)]*\)',
            re.IGNORECASE
        )
        if pattern_invalid_percentile2.search(sql):
            logger.warning("⚠️ Detectado PERCENTILE_CONT con OVER() (sin ROUND) — removiendo OVER clause")
            sql = pattern_invalid_percentile2.sub(r'\1', sql)

        # --- FIX: total * tipo_cambio sin COALESCE → NULL cuando tipo_cambio es NULL ---
        sql = re.sub(
            r'\btotal\s*\*\s*tipo_cambio\b(?!\s*,\s*1\s*\))',
            'total * COALESCE(tipo_cambio, 1)',
            sql,
            flags=re.IGNORECASE,
        )

        # Remover punto y coma extra al final
        sql = sql.rstrip(';') + ';'

        return sql

    # Mapeo completo de nombres de meses en español → número
    _MONTH_MAP: dict = {
        'enero': 1, 'ene': 1,
        'febrero': 2, 'feb': 2,
        'marzo': 3, 'mar': 3,
        'abril': 4, 'abr': 4,
        'mayo': 5, 'may': 5,
        'junio': 6, 'jun': 6,
        'julio': 7, 'jul': 7,
        'agosto': 8, 'ago': 8,
        'septiembre': 9, 'sep': 9, 'sept': 9,
        'octubre': 10, 'oct': 10,
        'noviembre': 11, 'nov': 11,
        'diciembre': 12, 'dic': 12,
    }

    def _detect_month(self, question: str) -> Optional[int]:
        """Detecta si la pregunta menciona un mes y retorna su número (1-12)."""
        q = question.lower()
        # Buscar nombres completos primero (más largos = más específicos)
        for name in sorted(self._MONTH_MAP, key=len, reverse=True):
            if re.search(rf'\b{name}\b', q):
                return self._MONTH_MAP[name]
        return None

    def _detect_explicit_year(self, question: str) -> Optional[int]:
        """Detecta si la pregunta menciona un año explícito (ej. '2025')."""
        m = re.search(r'\b(20[2-3]\d)\b', question)
        return int(m.group(1)) if m else None

    @staticmethod
    def _normalize_year(y: str) -> int:
        """Convierte año de 2 o 4 dígitos a entero de 4 dígitos. '25' → 2025, '2025' → 2025."""
        n = int(y)
        return 2000 + n if n < 100 else n

    def _detect_date_range(self, question: str) -> Optional[tuple]:
        """Detecta rangos de meses como 'ene a dic 2025', 'abr 25 a nov 25'.
        Acepta años de 2 dígitos ('25' → 2025) o 4 dígitos ('2025').
        La pregunta ya llega normalizada por _normalize_question_dates.
        """
        q = question.lower()
        _yr = r'(20[2-3]\d|\d{2})'  # año 2-digit o 4-digit
        # Patrón 1: "enero a diciembre 2025" o "abril a nov 25" (año al final, mismo para ambos)
        pattern1 = rf'(\w+)\s+(?:a|al|hasta|-)\s+(\w+)\s+{_yr}(?!\d)'
        # Patrón 2: "enero 2025 a dic 2025" o "abr 25 a nov 25" (año tras cada mes)
        pattern2 = rf'(\w+)\s+{_yr}(?!\d)\s+(?:a|al|hasta|-)\s+(\w+)\s+{_yr}(?!\d)'

        m2 = re.search(pattern2, q)
        if m2:
            start_name, y1_raw, end_name, y2_raw = m2.group(1), m2.group(2), m2.group(3), m2.group(4)
            start_month = self._MONTH_MAP.get(start_name)
            end_month = self._MONTH_MAP.get(end_name)
            if start_month and end_month:
                return (self._normalize_year(y1_raw), start_month,
                        self._normalize_year(y2_raw), end_month)

        m1 = re.search(pattern1, q)
        if m1:
            start_name, end_name, yr_raw = m1.group(1), m1.group(2), m1.group(3)
            start_month = self._MONTH_MAP.get(start_name)
            end_month = self._MONTH_MAP.get(end_name)
            if start_month and end_month:
                year = self._normalize_year(yr_raw)
                return (year, start_month, year, end_month)

        return None

    def _apply_sovereign_filter(self, sql: str, periodo_soberano: dict) -> str:
        """Reemplaza cualquier filtro de fecha en el SQL por el rango soberano exacto.

        El período soberano viene del slider de la UI y provee fechas absolutas
        (desde, hasta_excl), eliminando cualquier ambigüedad de parseo NL.
        Detecta la tabla principal para usar la columna de fecha correcta:
          - cfdi_ventas  → fecha_emision
          - cfdi_pagos   → fecha_pago
          - otras        → no inyecta filtro de fecha (evita errores de columna)
        """
        desde = periodo_soberano.get("desde")       # "YYYY-MM-DD"
        hasta_excl = periodo_soberano.get("hasta_excl")  # "YYYY-MM-DD"
        if not desde or not hasta_excl:
            return sql

        # ── Normalizar operadores Unicode que el modelo pueda generar ───────
        # ≥ → >=   ≤ → <=
        sql = sql.replace("≥", ">=").replace("≤", "<=")

        # ── Detectar columna de fecha según tabla principal ─────────────────
        sql_upper = sql.upper()
        if "CFDI_PAGOS" in sql_upper and "CFDI_VENTAS" not in sql_upper:
            fecha_col = "fecha_pago"
        elif "CFDI_VENTAS" in sql_upper:
            fecha_col = "fecha_emision"
        else:
            # Tabla desconocida — normalizar operadores y salir sin inyectar
            logger.info("_apply_sovereign_filter: tabla no reconocida, omitiendo inyección de fecha")
            return sql

        range_clause = f"{fecha_col} >= '{desde}' AND {fecha_col} < '{hasta_excl}'"

        # ── Limpiar EXTRACT generados por el modelo ──────────────────────────
        for _ in range(4):
            sql = re.sub(
                r'\s*AND\s+EXTRACT\s*\(\s*(?:MONTH|YEAR)\s+FROM\s+' + fecha_col + r'\s*\)\s*=\s*(?:EXTRACT\s*\([^)]*\)(?:\s*-\s*\d+)?|\d+)',
                '', sql, flags=re.IGNORECASE
            )
            sql = re.sub(
                r'EXTRACT\s*\(\s*(?:MONTH|YEAR)\s+FROM\s+' + fecha_col + r'\s*\)\s*=\s*(?:EXTRACT\s*\([^)]*\)(?:\s*-\s*\d+)?|\d+)\s*AND\s*',
                '', sql, flags=re.IGNORECASE
            )
            sql = re.sub(
                r'EXTRACT\s*\(\s*(?:MONTH|YEAR)\s+FROM\s+' + fecha_col + r'\s*\)\s*=\s*(?:EXTRACT\s*\([^)]*\)(?:\s*-\s*\d+)?|\d+)',
                '', sql, flags=re.IGNORECASE
            )

        # ── Eliminar filtros de fecha del modelo (ambas columnas por seguridad)
        for col in ("fecha_emision", "fecha_pago", "p\\.fecha_pago", "p\\.fecha_emision"):
            sql = re.sub(
                col + r'\s*(?:>=|<=|>|<|=)\s*\'[^\']+\'\s*(?:AND\s*' + col + r'\s*(?:>=|<=|>|<|=)\s*\'[^\']+\')?',
                '', sql, flags=re.IGNORECASE
            )
            sql = re.sub(
                col + r'\s+BETWEEN\s+\'[^\']+\'\s+AND\s+\'[^\']+\'',
                '', sql, flags=re.IGNORECASE
            )

        # ── Reparar WHERE vacío/malformado resultante de la limpieza ─────────
        sql = re.sub(r'WHERE\s+(GROUP|ORDER|LIMIT|HAVING)', r'\1', sql, flags=re.IGNORECASE)
        sql = re.sub(r'WHERE\s+AND\b', 'WHERE', sql, flags=re.IGNORECASE)
        sql = re.sub(r'WHERE\s*;', ';', sql, flags=re.IGNORECASE)
        sql = re.sub(r'\bAND\s+AND\b', 'AND', sql, flags=re.IGNORECASE)
        sql = re.sub(r'\s+AND\s+(GROUP|ORDER|LIMIT|HAVING)\b', r' \1', sql, flags=re.IGNORECASE)

        # ── Inyectar rango soberano ───────────────────────────────────────────
        sql_upper = sql.upper()
        if 'WHERE' in sql_upper:
            idx = sql_upper.index('WHERE') + len('WHERE')
            sql = sql[:idx] + f' {range_clause} AND' + sql[idx:]
        elif 'GROUP BY' in sql_upper:
            idx = sql_upper.index('GROUP BY')
            sql = sql[:idx] + f'WHERE {range_clause} ' + sql[idx:]
        elif 'ORDER BY' in sql_upper:
            idx = sql_upper.index('ORDER BY')
            sql = sql[:idx] + f'WHERE {range_clause} ' + sql[idx:]
        elif 'LIMIT' in sql_upper:
            idx = sql_upper.index('LIMIT')
            sql = sql[:idx] + f'WHERE {range_clause} ' + sql[idx:]
        else:
            sql = sql.rstrip(';') + f' WHERE {range_clause};'

        logger.info(f"Filtro soberano inyectado: {desde} → {hasta_excl}")
        return sql

    def _ensure_month_filter(self, question: str, sql: str) -> str:
        """Si la pregunta menciona un mes pero el SQL no lo filtra, inyecta el WHERE.
        
        Maneja:
        - Año explícito ("enero 2025") → usa el año literal
        - Rangos de meses ("enero a diciembre 2025") → usa fecha_emision >= / <
        - Contradicciones EXTRACT(YEAR FROM CURRENT_DATE) con año literal → las elimina
        """
        from datetime import date as _date

        explicit_year = self._detect_explicit_year(question)
        date_range = self._detect_date_range(question)

        # --- Caso 1: Rango de meses con año ("enero a diciembre 2025" o "ene 2024 a feb 2026") ---
        if date_range:
            # Siempre 4 valores: (year_inicio, mes_inicio, year_fin, mes_fin)
            year_start, start_month, year_end, end_month = date_range
            start_date = f"{year_start}-{start_month:02d}-01"
            if end_month == 12:
                end_date = f"{year_end + 1}-01-01"
            else:
                end_date = f"{year_end}-{end_month + 1:02d}-01"
            range_clause = f"fecha_emision >= '{start_date}' AND fecha_emision < '{end_date}'"

            # Remover todas las condiciones EXTRACT(MONTH/YEAR FROM fecha_emision) = ...
            # Cubrir patrones: AND EXTRACT(...) = val, EXTRACT(...) = val AND, standalone
            for _ in range(4):  # Varias pasadas para limpiar combinaciones
                sql = re.sub(
                    r'\s*AND\s+EXTRACT\s*\(\s*(?:MONTH|YEAR)\s+FROM\s+fecha_emision\s*\)\s*=\s*(?:EXTRACT\s*\([^)]*\)(?:\s*-\s*\d+)?|\d+)',
                    '', sql, flags=re.IGNORECASE
                )
                sql = re.sub(
                    r'EXTRACT\s*\(\s*(?:MONTH|YEAR)\s+FROM\s+fecha_emision\s*\)\s*=\s*(?:EXTRACT\s*\([^)]*\)(?:\s*-\s*\d+)?|\d+)\s*AND\s*',
                    '', sql, flags=re.IGNORECASE
                )
                sql = re.sub(
                    r'EXTRACT\s*\(\s*(?:MONTH|YEAR)\s+FROM\s+fecha_emision\s*\)\s*=\s*(?:EXTRACT\s*\([^)]*\)(?:\s*-\s*\d+)?|\d+)',
                    '', sql, flags=re.IGNORECASE
                )
            # Limpiar WHERE vacío o malformado
            sql = re.sub(r'WHERE\s+(GROUP|ORDER|LIMIT|HAVING)', r'\1', sql, flags=re.IGNORECASE)
            sql = re.sub(r'WHERE\s+AND\b', 'WHERE', sql, flags=re.IGNORECASE)
            sql = re.sub(r'WHERE\s*;', ';', sql, flags=re.IGNORECASE)
            sql = re.sub(r'\s+AND\s+(GROUP|ORDER|LIMIT|HAVING)\b', r' \1', sql, flags=re.IGNORECASE)

            sql_upper = sql.upper()
            if 'WHERE' in sql_upper:
                idx = sql_upper.index('WHERE') + len('WHERE')
                sql = sql[:idx] + f' {range_clause} AND' + sql[idx:]
            elif 'GROUP BY' in sql_upper:
                idx = sql_upper.index('GROUP BY')
                sql = sql[:idx] + f'WHERE {range_clause} ' + sql[idx:]
            elif 'ORDER BY' in sql_upper:
                idx = sql_upper.index('ORDER BY')
                sql = sql[:idx] + f'WHERE {range_clause} ' + sql[idx:]
            elif 'LIMIT' in sql_upper:
                idx = sql_upper.index('LIMIT')
                sql = sql[:idx] + f'WHERE {range_clause} ' + sql[idx:]

            logger.info(f"Filtro de rango inyectado: {start_date} a {end_date} ('{question}')")
            return sql

        # --- Caso 2: Mes individual ---
        month_num = self._detect_month(question)
        if month_num is None:
            # Sin mes detectado, pero si hay año explícito, corregir contradicciones
            if explicit_year:
                sql = self._fix_year_contradictions(sql, explicit_year)
            return sql

        current_month = _date.today().month

        # Determinar la expresión de año correcta
        if explicit_year:
            year_expr = str(explicit_year)
        elif month_num > current_month:
            year_expr = "EXTRACT(YEAR FROM CURRENT_DATE) - 1"
        else:
            year_expr = "EXTRACT(YEAR FROM CURRENT_DATE)"

        # Si hay año explícito, limpiar contradicciones con CURRENT_DATE
        if explicit_year:
            sql = self._fix_year_contradictions(sql, explicit_year)

        # Si el SQL ya filtra por mes, corregir el año si es necesario
        if re.search(r'EXTRACT\s*\(\s*MONTH', sql, re.IGNORECASE):
            if explicit_year:
                # Reemplazar EXTRACT(YEAR FROM CURRENT_DATE) por el año literal
                sql = re.sub(
                    r'EXTRACT\s*\(\s*YEAR\s+FROM\s+CURRENT_DATE\s*\)',
                    str(explicit_year),
                    sql,
                    flags=re.IGNORECASE,
                )
            elif month_num > current_month:
                sql = re.sub(
                    r'EXTRACT\s*\(\s*YEAR\s+FROM\s+CURRENT_DATE\s*\)',
                    f'({year_expr})',
                    sql,
                    flags=re.IGNORECASE,
                )
            return sql

        month_clause = (
            f"EXTRACT(MONTH FROM fecha_emision) = {month_num} "
            f"AND EXTRACT(YEAR FROM fecha_emision) = {year_expr}"
        )

        sql_upper = sql.upper()
        if 'WHERE' in sql_upper:
            idx = sql_upper.index('WHERE') + len('WHERE')
            sql = sql[:idx] + f' {month_clause} AND' + sql[idx:]
        elif 'GROUP BY' in sql_upper:
            idx = sql_upper.index('GROUP BY')
            sql = sql[:idx] + f'WHERE {month_clause} ' + sql[idx:]
        elif 'ORDER BY' in sql_upper:
            idx = sql_upper.index('ORDER BY')
            sql = sql[:idx] + f'WHERE {month_clause} ' + sql[idx:]
        elif 'LIMIT' in sql_upper:
            idx = sql_upper.index('LIMIT')
            sql = sql[:idx] + f'WHERE {month_clause} ' + sql[idx:]

        logger.info(f"Filtro de mes inyectado: MONTH={month_num}, YEAR={year_expr} ('{question}')")
        return sql

    def _fix_year_contradictions(self, sql: str, explicit_year: int) -> str:
        """Elimina condiciones contradictorias de año en SQL.
        
        Si GPT genera tanto EXTRACT(YEAR)=EXTRACT(YEAR FROM CURRENT_DATE) como
        EXTRACT(YEAR)=2025, elimina la de CURRENT_DATE y mantiene la literal.
        """
        # Detectar si hay un año literal en la query
        has_literal_year = re.search(
            r'EXTRACT\s*\(\s*YEAR\s+FROM\s+fecha_emision\s*\)\s*=\s*' + str(explicit_year),
            sql, re.IGNORECASE
        )
        has_current_date_year = re.search(
            r'EXTRACT\s*\(\s*YEAR\s+FROM\s+fecha_emision\s*\)\s*=\s*EXTRACT\s*\(\s*YEAR\s+FROM\s+CURRENT_DATE\s*\)',
            sql, re.IGNORECASE
        )

        if has_literal_year and has_current_date_year:
            # Remover la condición con CURRENT_DATE (la literal es correcta)
            sql = re.sub(
                r'\s*AND\s+EXTRACT\s*\(\s*YEAR\s+FROM\s+fecha_emision\s*\)\s*=\s*EXTRACT\s*\(\s*YEAR\s+FROM\s+CURRENT_DATE\s*\)',
                '', sql, flags=re.IGNORECASE
            )
            sql = re.sub(
                r'EXTRACT\s*\(\s*YEAR\s+FROM\s+fecha_emision\s*\)\s*=\s*EXTRACT\s*\(\s*YEAR\s+FROM\s+CURRENT_DATE\s*\)\s*AND\s*',
                '', sql, flags=re.IGNORECASE
            )
            logger.info(f"Contradicción de año eliminada: manteniendo {explicit_year}")
        elif has_current_date_year and not has_literal_year:
            # Solo hay CURRENT_DATE → reemplazar por el año explícito
            sql = re.sub(
                r'EXTRACT\s*\(\s*YEAR\s+FROM\s+CURRENT_DATE\s*\)',
                str(explicit_year),
                sql, flags=re.IGNORECASE
            )
            logger.info(f"Año CURRENT_DATE reemplazado por {explicit_year}")

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

        # Rechazar consultas patológicamente anchas aunque no excedan el largo.
        select_match = re.search(r'^\s*SELECT\s+(.*?)\bFROM\b', sql, re.IGNORECASE | re.DOTALL)
        if select_match and select_match.group(1).count(',') > 250:
            return False, "Query excede el ancho máximo permitido"

        # Debe empezar con SELECT o WITH (CTEs) (case-insensitive)
        if not re.match(r'^\s*(SELECT|WITH)\b', sql, re.IGNORECASE):
            return False, "Solo se permiten consultas SELECT"
        
        # Si empieza con WITH, verificar que contenga SELECT y no sea un CTE malicioso
        if re.match(r'^\s*WITH\b', sql, re.IGNORECASE):
            if not re.search(r'\bSELECT\b', sql, re.IGNORECASE):
                return False, "Las consultas WITH deben contener SELECT"

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
        
        # Extraer nombres de CTEs para no rechazarlos como tablas no permitidas
        cte_names = set(
            name.lower() for name in re.findall(r'\b(\w+)\s+AS\s*\(', sql_cleaned, re.IGNORECASE)
        )
        
        tables_in_query = re.findall(
            r'\bFROM\s+(\w+)|\bJOIN\s+(\w+)',
            sql_cleaned,
            re.IGNORECASE
        )
        allowed = set(ALLOWED_TABLES) | cte_names
        for match_groups in tables_in_query:
            for table in match_groups:
                if table and table.lower() not in allowed:
                    return False, f"Tabla no permitida: {table}"

        return True, "OK"

    # -----------------------------------------------------------------
    # 2b. Auto-corrección de patrones SQL problemáticos
    # -----------------------------------------------------------------
    def _fix_sql(self, sql: str, error_msg: str = "") -> str:
        """
        Aplica correcciones automáticas a patrones SQL que causan errores
        comunes en PostgreSQL (GROUP BY / aggregate function).

        Estrategia 1: si viene el mensaje de error, extrae la columna problemática
        directamente (ej: column "tv.total_mxn" must appear in GROUP BY...)
        y la envuelve en MAX() en todo el SQL.

        Estrategia 2: regex genérico que busca divisiones de la forma
        `/ alias.col` no protegidas por una función de agregado.
        """
        import re
        fixed = sql

        # Estrategia 1: extraer columna del mensaje de error
        if error_msg:
            # PostgreSQL reporta: column "tv.total_mxn" must appear in the GROUP BY...
            m = re.search(r'column "([\w\.]+)" must appear in the GROUP BY', error_msg)
            if m:
                bad_col = m.group(1)  # ej: "tv.total_mxn"
                # Reemplazar todas las ocurrencias no dentro de una función de agregado
                # Patrón: bad_col que NO esté precedido por MAX(, MIN(, SUM(, COUNT(, AVG(
                escaped = re.escape(bad_col)
                fixed = re.sub(
                    r'(?<!MAX\()(?<!MIN\()(?<!SUM\()(?<!AVG\()(?<!COUNT\()\b' + escaped + r'\b',
                    f'MAX({bad_col})',
                    fixed
                )
                if fixed != sql:
                    logger.info(f"_fix_sql: envolví '{bad_col}' en MAX() basado en error")
                    return fixed

        # Estrategia 2: regex — busca `/ alias.col` sin protección de agregado
        pattern = r'(?<![\w])(/\s*)(?!MAX\(|MIN\(|SUM\(|COUNT\(|AVG\()([a-zA-Z_]\w*\.[a-zA-Z_]\w*)'
        def wrap_div(m):
            return f'{m.group(1)}MAX({m.group(2)})'
        fixed2 = re.sub(pattern, wrap_div, fixed)
        if fixed2 != fixed:
            logger.info("_fix_sql: envolví columnas escalares en divisiones con MAX()")
        return fixed2

    # -----------------------------------------------------------------
    # 2c. Detección de uso incorrecto de tabla `empresas`
    # -----------------------------------------------------------------
    def _uses_empresas_for_clients(self, sql: str) -> bool:
        """
        Detecta si el SQL generado usa la tabla `empresas` para analizar
        clientes de negocio (use-case incorrecto). La tabla `empresas` es
        un catálogo de tenants, no de clientes comerciales.

        Señales de uso incorrecto:
        - FROM empresas con columnas propias de análisis de clientes
          (fecha_registro, nuevos_clientes, empresa_id [como filtro de tenant],
           COUNT(DISTINCT id) sin join a cfdi_ventas, etc.)
        """
        import re
        sql_lower = sql.lower()
        if 'from empresas' not in sql_lower:
            return False
        # Si también usa cfdi_ventas, probablemente es un JOIN legítimo de permisos
        if 'cfdi_ventas' in sql_lower:
            return False
        # Señales de análisis de clientes sobre la tabla empresas
        client_signals = [
            'nuevos_clientes', 'fecha_registro', 'count(distinct id)',
            'clientes_nuevos', 'nuevo_cliente',
        ]
        return any(sig in sql_lower for sig in client_signals)

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
3. Máximo 3-4 oraciones concisas.
4. NO repitas la pregunta ni el SQL.

REGLAS DE FORMATO (cumplir TODAS de forma estricta):
- TODOS los valores monetarios SIEMPRE con signo **$** y separadores de miles: **$41,991.30**
- TODOS los valores numéricos no monetarios en negrita: **17 facturas**, **3.5%**
- Porcentajes SIEMPRE con negrita: **85.2%**
- NUNCA uses backticks (`) para resaltar valores ni texto. Solo usa **negrita** con doble asterisco.
- NUNCA mezcles formatos: NO hagas `$41,991.30` ni `17 facturas`. Siempre **$41,991.30** y **17 facturas**.
- Para enfatizar frases importantes, usa _cursiva_ con guiones bajos simples, NUNCA backticks.
- Si hay tendencias, menciónalas.
- Sé consistente: si el primer monto lleva $, TODOS deben llevar $.

AL FINAL, genera una especificación de gráfica en formato JSON en una sola línea.
La línea DEBE comenzar exactamente con CHART_SPEC: seguido del JSON.

**OBLIGATORIO**: SIEMPRE genera un CHART_SPEC. NUNCA omitas esta línea. Si no estás seguro del tipo, usa "bar" o "table", pero SIEMPRE incluye CHART_SPEC.

**REGLA ABSOLUTA PARA GRÁFICOS CIRCULARES:**
- Usuario menciona "pay", "pastel", "pie" → **type="pie"** (100% de las veces)
- Usuario menciona "dona", "donut" → **type="donut"** (100% de las veces)
- NO uses "table" ni "bar" cuando el usuario pide explícitamente un gráfico circular

**EJEMPLOS OBLIGATORIOS DE DETECCIÓN (COPIAR EXACTAMENTE):**

Pregunta: "dame un grafico de pay"
→ CHART_SPEC: {{"type": "pie", "x": "[columna_categoria]", "y": "[columna_valor]", "title": "Distribución"}}

Pregunta: "dame un grafico de dona"
→ CHART_SPEC: {{"type": "donut", "x": "[columna_categoria]", "y": "[columna_valor]", "title": "Distribución"}}

Pregunta: "muestra las ventas por cliente en dona"
→ CHART_SPEC: {{"type": "donut", "x": "cliente", "y": "ventas", "title": "Ventas por cliente"}}

Pregunta: "grafico de pastel de formas de pago"
→ CHART_SPEC: {{"type": "pie", "x": "forma_pago", "y": "total", "title": "Formas de pago"}}

Pregunta: "distribución de facturación por producto"
→ CHART_SPEC: {{"type": "donut", "x": "producto", "y": "facturacion", "title": "Distribución de facturación por producto"}}

Pregunta: "ventas por mes" (CON tiempo)
→ CHART_SPEC: {{"type": "bar", "x": "mes", "y": "ventas", "title": "Ventas por mes"}}

Tipos de gráfica disponibles:
- bar: barras verticales (IDEAL para series temporales: mes a mes, año a año, evolución, tendencias)
- hbar: barras horizontales (ranking con nombres largos)
- pareto: gráfico de Pareto (barras descendentes + línea de % acumulado superpuesta, IDEAL para análisis 80/20, ABC, clasificación de clientes)
- line: línea temporal (alternativa para tendencias suaves)
- area: área rellena (tendencias acumulativas)
- stacked_bar: barras apiladas (composición por categoría)
- grouped_bar: barras agrupadas (comparar grupos lado a lado)
- **donut: dona/donut (PRIORITARIO para distribuciones, proporciones, composiciones, % por categoría - MÁS MODERNO que pie)**
- pie: pastel (distribución porcentual, max 8 categorías - usar solo si usuario especifica "pie" o "pastel")
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

REGLAS PARA SELECCIONAR TIPO DE GRÁFICA (ORDEN DE PRIORIDAD):

**PRIORIDAD 1 - DETECCIÓN EXPLÍCITA DEL USUARIO:**
- Si el usuario dice "dona", "donut", "gráfico de dona", "en dona", "tipo dona", "como dona", "hazlo dona" → **SIEMPRE type="donut"** (NO uses "bar" ni "pie")
- Si el usuario dice "pay", "pastel", "pie chart", "gráfico de pastel" → **type="pie"**
- Si el usuario dice "pareto", "80/20", "ABC", "análisis ABC" → **type="pareto"**
- Si el usuario dice "barras", "bar chart", "gráfico de barras" → **type="bar"** o **type="hbar"**

**PRIORIDAD 2 - TIPO DE DATOS:**
- Si es distribución/proporción/composición SIN temporalidad (ej: "ventas por cliente", "distribución por producto", "proporción de conceptos") → **type="donut"**
- Si la consulta tiene fechas/periodos (mes, trimestre, año) en el eje X → usa "bar" o "line" (preferir bar para datos mensuales/trimestrales)
- Para "facturación en el tiempo", "ventas por mes", "evolución", "histórico" → usa "bar" con x=periodo, y=monto
- Si hay columna DATE, TIMESTAMP o con nombre mes/periodo/fecha → es temporal, usa "bar" o "line"
- Para rankings de nombres largos (clientes, productos) → usa "hbar" (PERO si el usuario pidió vertical, usa "bar" con orientation: "v")

**IMPORTANTE**: 
- Distribuciones categóricas (clientes, productos, conceptos) sin tiempo → **donut**
- Evoluciones temporales (meses, años) → **bar** o **line**
- Rankings con nombres largos → **hbar**

REGLAS PARA ORIENTACIÓN (CUANDO EL USUARIO LA ESPECIFICA):
- **CRÍTICO**: Si el usuario dice "vertical", "verticales", "verticalmente", "barras verticales", "de forma vertical", "en vertical", "hacia arriba" → usa type="bar" (NO "hbar") y **OBLIGATORIAMENTE** incluye "orientation": "v" en el CHART_SPEC
- Si el usuario dice "horizontal", "horizontales", "horizontalmente", "barras horizontales", "de izquierda a derecha" → puedes usar type="hbar" O type="bar" con "orientation": "h" en el CHART_SPEC
- Si el usuario NO especifica orientación → NO incluyas el campo "orientation" (se decidirá automáticamente)
- **IMPORTANTE**: Si el usuario especifica "vertical" o "verticales", NUNCA uses type="hbar", usa type="bar" con orientation="v"
- Series temporales SIEMPRE se quedan verticales por defecto (no agregues orientation a menos que el usuario lo pida explícitamente)

PARA ESTADÍSTICAS: Cuando la consulta devuelve media, mediana, desviación estándar, percentiles, usa stats_summary. Cuando devuelve datos por grupo con estadísticas (ej. promedio por cliente), también usa stats_summary.

**REPORTES DE AUDITORÍA Y ANÁLISIS TEMPORAL:**
- Si el usuario pide "reporte", "auditoría", "análisis por día/periodo", "resumen diario/mensual"
- Y la consulta devuelve datos por fecha/día/periodo con métricas (totales, promedios, counts)
- → Usa **type="line"** para series temporales o **type="bar"** para comparaciones periódicas
- El eje X debe ser la columna temporal (dia, fecha, periodo, mes)
- El eje Y debe ser la métrica principal (total_mxn, num_facturas, promedio)
- **IMPORTANTE**: Para reportes de auditoría con múltiples métricas estadísticas (promedio, desviación, percentiles), genera DOS gráficas:
  1. CHART_SPEC principal con type="line" para la serie temporal del total o métrica principal
  2. Menciona en interpretación que hay estadísticas detalladas disponibles en la tabla

DETECCIÓN DE CONSULTAS TEMPORALES:
- Si hay columna "mes", "periodo", "fecha", "dia", "trimestre", "año" o tipo DATE/TIMESTAMP → es serie temporal
- Para series temporales SIEMPRE usa type="bar" o type="line" (preferir line para auditorías y análisis de tendencias)
- El eje X debe ser la columna temporal, el eje Y el valor numérico (facturación, ventas, count, etc.)

PALABRAS CLAVE QUE INDICAN GRÁFICO DE BARRAS:
- Usuario dice: "gráfico de barras", "bar chart", "a manera de barras", "en barras", "muestra en barras"
- Usuario dice: "facturación en el tiempo", "ventas por mes", "histórico", "evolución"
- → En todos estos casos usa type="bar"

PALABRAS CLAVE QUE INDICAN GRÁFICO PARETO:
- Usuario dice: "pareto", "80/20", "ABC", "clasificación ABC", "análisis ABC", "curva de pareto"
- → En todos estos casos usa type="pareto"
- El eje X debe ser la columna categórica (ej: cliente, producto)
- El eje Y debe ser el valor numérico (ej: total_mxn, facturación)
- Si hay columna de % acumulado (pct_acumulado), se usará automáticamente
- Si hay columna de clasificación ABC (clasificacion_abc), se coloreará por categoría

PALABRAS CLAVE QUE INDICAN GRÁFICO DE DONA (DONUT) - MÁXIMA PRIORIDAD:
- Usuario dice: "dona", "donut", "gráfico de dona", "gráfica de dona", "en dona", "tipo dona", "como dona", "hazlo dona", "hazlo en dona"
- Usuario dice: "gráfico circular con agujero", "gráfico anular", "ring chart"
- Usuario pregunta por distribución/proporción categórica SIN tiempo: "distribución por cliente", "proporción por producto", "ventas por concepto"
- → En TODOS estos casos usa **type="donut"** (NUNCA uses "bar" ni "pie")
- El campo x (names) debe ser la columna categórica (ej: cliente, producto, concepto)
- El campo y (values) debe ser el valor numérico (ej: total_mxn, cantidad, porcentaje)
- Máximo 15 categorías (se limita automáticamente en el código)
- **CRÍTICO**: SIEMPRE que el usuario mencione "dona" o "donut" en CUALQUIER parte de su pregunta, usa type="donut" (NO "pie", NO "bar", NO "hbar")

PALABRAS CLAVE QUE INDICAN GRÁFICO DE PAY/PASTEL (PIE) - ALTA PRIORIDAD:
- Usuario dice: "pay", "pastel", "gráfico de pay", "gráfica de pastel", "pie chart", "en pastel", "tipo pastel", "grafico pay", "de pay"
- Usuario dice: "gráfico circular", "gráfico de torta", "torta"
- → En TODOS estos casos usa **type="pie"** (NO "table", NO "bar")
- El campo x (names) debe ser la columna categórica
- El campo y (values) debe ser el valor numérico
- Máximo 15 categorías
- **CRÍTICO**: Si el usuario menciona "pay", "pastel" o "pie" en su pregunta, SIEMPRE genera CHART_SPEC con type="pie"

Campos del JSON:
- type: tipo de gráfica (obligatorio)
- x: nombre exacto de columna para eje X (obligatorio para bar/line/area/scatter)
- y: nombre exacto de columna para eje Y/valores (obligatorio para bar/line/area/scatter)
- color: columna para agrupar por color (opcional)
- title: título descriptivo corto en español (obligatorio)
- sort: "asc" o "desc" para ordenar datos (opcional)
- top_n: número máximo de elementos a mostrar (opcional, default 30)
- orientation: "h" o "horizontal" para barras horizontales, "v" o "vertical" para barras verticales (opcional, solo para bar/stacked_bar/grouped_bar; si no se especifica, se decide automáticamente)

EJEMPLO de línea final:
CHART_SPEC: {{"type": "hbar", "x": "cliente", "y": "total_mxn", "title": "Top clientes por facturación", "sort": "desc", "top_n": 10}}

EJEMPLO con orientación vertical especificada:
CHART_SPEC: {{"type": "bar", "x": "producto", "y": "ventas", "title": "Ventas por producto", "orientation": "v", "sort": "desc", "top_n": 15}}

EJEMPLO con gráfico de dona (distribución):
CHART_SPEC: {{"type": "donut", "x": "concepto", "y": "total_mxn", "title": "Distribución de ventas por concepto", "sort": "desc", "top_n": 10}}

EJEMPLO con gráfico de pastel:
CHART_SPEC: {{"type": "pie", "x": "categoria", "y": "cantidad", "title": "Composición de productos", "top_n": 8}}

EJEMPLOS DE CÓMO DETECTAR ORIENTACIÓN EN LA PREGUNTA DEL USUARIO:
- "muestra esto vertical" → type="bar", **incluye "orientation": "v"**
- "hazlo vertical" → type="bar", **incluye "orientation": "v"**
- "en vertical" → type="bar", **incluye "orientation": "v"**
- "barras verticales" → type="bar", **incluye "orientation": "v"**
- "de forma vertical" → type="bar", **incluye "orientation": "v"**
- "verticales" (cualquier mención) → type="bar", **incluye "orientation": "v"**
- "hacia arriba" → type="bar", **incluye "orientation": "v"**
- "horizontal" → type puede ser "bar" u "hbar", orientation="h"
- "barras horizontales" → type="hbar" o type="bar" con orientation="h"

**IMPORTANTE**: Busca activamente las palabras "vertical", "verticales", "verticalmente" en la pregunta del usuario. Si las encuentras, ES OBLIGATORIO incluir "orientation": "v" en el CHART_SPEC.

EJEMPLOS DE CÓMO DETECTAR TIPO DE GRÁFICO EN LA PREGUNTA DEL USUARIO:

**GRÁFICOS CIRCULARES (PRIORIDAD MÁXIMA):**
- "pay", "de pay", "grafico pay", "gráfico de pay", "dame un pay", "hazme un pay" → **type="pie"** (SIEMPRE)
- "pastel", "pie chart", "gráfico de pastel", "en pastel", "tipo pastel" → **type="pie"** (SIEMPRE)
- "dona", "donut", "gráfico de dona", "en dona", "hazlo en dona", "tipo dona" → **type="donut"** (SIEMPRE)
- **NUNCA uses "table" ni "bar" cuando el usuario pide explícitamente pay/pastel/pie/dona/donut**

**OTROS GRÁFICOS:**
- "distribución de ventas por cliente", "proporción por producto" (sin tiempo ni mención de tipo) → **type="donut"**
- "ventas por mes", "facturación en el tiempo", "evolución mensual" (CON tiempo) → **type="bar"** (NO donut)
- "barras", "bar chart", "gráfico de barras" → **type="bar"** o **type="hbar"**
- "pareto", "80/20", "análisis ABC" → **type="pareto"**
- "línea", "line chart", "evolución temporal" → **type="line"**

**REGLA DE ORO**: 
- Usuario menciona "dona"/"donut" → **type="donut"** SIEMPRE
- Distribución categórica sin tiempo → **type="donut"**
- Evolución temporal (meses/años) → **type="bar"** o **type="line"**

**CRÍTICO**: Si el usuario menciona "dona" o "donut" en cualquier parte de su pregunta, SIEMPRE usa type="donut". No uses "pie", "bar" ni "hbar" en estos casos.

Si el usuario pidió explícitamente un tipo de gráfica (ej: "muéstrame un pie chart", "hazme una gráfica de barras", "hazlo en dona"), USA ESE TIPO.
Si el usuario pidió explícitamente una orientación (ej: "vertical", "horizontal", "hazlo vertical", "en vertical"), incluye el campo "orientation" y ajusta el "type" según las reglas.
"""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",  # Más económico para interpretación
                messages=[
                    {
                        "role": "system",
                        "content": "Eres un analista de datos experto en facturación "
                                   "y cuentas por cobrar B2B en México. Responde en español. "
                                   "FORMATO OBLIGATORIO: usa **negrita** (doble asterisco) para "
                                   "cifras y montos (ej: **$41,991.30**, **17 facturas**). "
                                   "NUNCA uses backticks (`) para resaltar texto o valores. "
                                   "Usa _cursiva_ para énfasis en frases. "
                                   "CRÍTICO PARA CHART_SPEC: "
                                   "- Si usuario dice 'pay', 'pastel', 'pie', 'gráfico de pay' → type='pie' "
                                   "- Si usuario dice 'dona', 'donut', 'gráfico de dona' → type='donut' "
                                   "- SIEMPRE genera CHART_SPEC (nunca lo omitas) "
                                   "- Formato: CHART_SPEC: {{\"type\": \"pie\", \"x\": \"columna\", \"y\": \"valor\", \"title\": \"Título\"}}"
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=700,
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
                    logger.info(f"📋 CHART_SPEC generado por IA: {chart_spec}")
                except (json.JSONDecodeError, ValueError):
                    chart_type = "table"
                text = re.sub(r'\n?CHART_SPEC:\s*\{.*\}', '', text).strip()
            else:
                # Log cuando no se encuentra CHART_SPEC
                logger.warning(f"⚠️ No se encontró CHART_SPEC en la respuesta de la IA. Pregunta: {question}")
                
                # Fallback inteligente: detectar tipo de gráfico por palabras clave en la pregunta
                q_lower = question.lower()
                if any(word in q_lower for word in ['pay', 'pastel', 'pie chart', 'gráfico de pay', 'grafico pay']):
                    chart_type = "pie"
                    logger.info(f"🔄 Fallback: Detectado 'pie' por palabras clave en pregunta")
                elif any(word in q_lower for word in ['dona', 'donut', 'gráfico de dona', 'grafico dona']):
                    chart_type = "donut"
                    logger.info(f"🔄 Fallback: Detectado 'donut' por palabras clave en pregunta")
                else:
                    # Fallback: buscar CHART_TYPE legacy
                    chart_match = re.search(r'CHART_TYPE:\s*(\w+)', text)
                    if chart_match:
                        chart_type = chart_match.group(1).lower()
                    text = re.sub(r'\n?CHART_TYPE:\s*\w+', '', text).strip()

            # --- POST-VALIDACIÓN: Detectar intención explícita del usuario ---
            question_lower = question.lower()
            
            # 0. Detectar orientación explícita del usuario
            vertical_keywords = ['vertical', 'verticales', 'verticalmente', 'barras verticales', 
                               'de forma vertical', 'en vertical', 'hacia arriba']
            horizontal_keywords = ['horizontal', 'horizontales', 'horizontalmente', 'barras horizontales',
                                  'de forma horizontal', 'en horizontal']
            
            user_wants_vertical = any(kw in question_lower for kw in vertical_keywords)
            user_wants_horizontal = any(kw in question_lower for kw in horizontal_keywords)
            
            if user_wants_vertical:
                logger.info(f"🔍 Detectado pedido de orientación VERTICAL en pregunta: {question}")
                # Forzar type="bar" y orientation="v"
                chart_type = "bar"
                if chart_spec and "type" in chart_spec:
                    chart_spec["type"] = "bar"
                if chart_spec:
                    chart_spec["orientation"] = "v"
                else:
                    chart_spec = {"type": "bar", "orientation": "v"}
                logger.info(f"✅ Forzando orientation='v' en chart_spec: {chart_spec}")
            elif user_wants_horizontal:
                logger.info(f"🔍 Detectado pedido de orientación HORIZONTAL en pregunta: {question}")
                if chart_spec:
                    chart_spec["orientation"] = "h"
            
            # 1. Usuario pidió explícitamente gráfico de barras
            bar_keywords = ['gráfico de barras', 'grafico de barras', 'bar chart', 
                           'a manera de barras', 'en barras', 'muestra en barras',
                           'hazme un gráfico de barras', 'mostrar en barras']
            
            # 1a. Detectar intención explícita de PIE/DONUT (MÁXIMA PRIORIDAD)
            pie_keywords = ['pay', 'pastel', 'pie chart', 'gráfico de pay', 'grafico de pay',
                           'gráfica de pay', 'de pay', 'tipo pay', 'en pastel', 
                           'gráfico de pastel', 'grafico de pastel']
            donut_keywords = ['dona', 'donut', 'gráfico de dona', 'grafico de dona',
                             'gráfica de dona', 'tipo dona', 'en dona', 'hazlo dona',
                             'como dona']
            
            user_wants_pie = any(kw in question_lower for kw in pie_keywords)
            user_wants_donut = any(kw in question_lower for kw in donut_keywords)
            
            if user_wants_pie:
                logger.info(f"🔍 Detectado pedido de PIE explícito en pregunta: {question}")
                chart_type = "pie"
                # Auto-detectar columnas si no están especificadas
                if not chart_spec or "x" not in chart_spec:
                    cat_cols = df.select_dtypes(include=['object']).columns.tolist()
                    num_cols = df.select_dtypes(include=['int64', 'float64', 'int32', 'float32']).columns.tolist()
                    chart_spec = {
                        "type": "pie",
                        "x": cat_cols[0] if cat_cols else df.columns[0],
                        "y": num_cols[0] if num_cols else df.columns[-1],
                        "title": "Distribución"
                    }
                else:
                    chart_spec["type"] = "pie"
                logger.info(f"✅ Forzando type='pie' en chart_spec: {chart_spec}")
                    
            elif user_wants_donut:
                logger.info(f"🔍 Detectado pedido de DONUT explícito en pregunta: {question}")
                chart_type = "donut"
                # Auto-detectar columnas si no están especificadas
                if not chart_spec or "x" not in chart_spec:
                    cat_cols = df.select_dtypes(include=['object']).columns.tolist()
                    num_cols = df.select_dtypes(include=['int64', 'float64', 'int32', 'float32']).columns.tolist()
                    chart_spec = {
                        "type": "donut",
                        "x": cat_cols[0] if cat_cols else df.columns[0],
                        "y": num_cols[0] if num_cols else df.columns[-1],
                        "title": "Distribución"
                    }
                else:
                    chart_spec["type"] = "donut"
                logger.info(f"✅ Forzando type='donut' en chart_spec: {chart_spec}")
            
            # 1b. Detectar intención de Pareto/ABC
            pareto_keywords = ['pareto', '80/20', 'clasificación abc', 'clasificacion abc',
                              'análisis abc', 'analisis abc', 'curva de pareto',
                              'abc de clientes', 'abc de productos', 'regla 80']
            user_wants_pareto = any(kw in question_lower for kw in pareto_keywords)
            
            if user_wants_pareto:
                logger.info(f"🔍 Detectado pedido de PARETO en pregunta: {question}")
                chart_type = "pareto"
                if chart_spec:
                    chart_spec["type"] = "pareto"
                else:
                    chart_spec = {"type": "pareto"}
            
            # 1c. Detectar reportes de auditoría/análisis temporal y reportes ejecutivos
            report_keywords = ['reporte', 'report', 'auditoría', 'auditoria', 'análisis por día', 
                              'analisis por dia', 'resumen diario', 'resumen mensual',
                              'análisis temporal', 'evolución', 'tendencia',
                              'reporte ejecutivo', 'report ejecutivo', 'executive report',
                              'dame un reporte', 'genera un reporte', 'muestra un reporte',
                              'reporte de', 'informe de', 'informe ejecutivo']
            temporal_cols = [col for col in df.columns if any(
                time_word in str(col).lower() 
                for time_word in ['dia', 'fecha', 'date', 'mes', 'periodo', 'trimestre', 'año', 'year']
            )]
            cat_cols = df.select_dtypes(include=['object']).columns.tolist()
            num_cols = df.select_dtypes(include=['int64', 'float64', 'int32', 'float32']).columns.tolist()
            
            user_wants_report = any(kw in question_lower for kw in report_keywords)
            has_temporal_data = len(temporal_cols) > 0 and len(num_cols) > 0
            has_categorical_data = len(cat_cols) > 0 and len(num_cols) > 0
            
            # Si pide reporte y NO se generó gráfica automáticamente
            if user_wants_report and chart_type in ("table", "stats_summary"):
                if has_temporal_data:
                    # Reporte temporal → gráfica de línea/barras
                    logger.info(f"🔍 Detectado REPORTE temporal en pregunta: {question}")
                    
                    # Encontrar columna de valor principal
                    value_col = None
                    for col in num_cols:
                        if any(kw in col.lower() for kw in ['total', 'monto', 'facturacion', 'importe', 'suma', 'ventas']):
                            value_col = col
                            break
                    if not value_col:
                        value_col = num_cols[0]
                    
                    chart_type = "line"
                    chart_spec = {
                        "type": "line",
                        "x": temporal_cols[0],
                        "y": value_col,
                        "title": f"Evolución de {value_col.replace('_', ' ').title()}",
                    }
                    logger.info(f"✅ Generando gráfica temporal para reporte: {chart_spec}")
                    
                elif has_categorical_data and len(df) > 1:
                    # Reporte categórico → gráfica de barras/donut
                    logger.info(f"🔍 Detectado REPORTE categórico en pregunta: {question}")
                    
                    # Decidir entre bar/hbar/donut según cantidad de filas
                    n_rows = len(df)
                    x_col = cat_cols[0]
                    
                    # Encontrar columna de valor
                    value_col = None
                    for col in num_cols:
                        if any(kw in col.lower() for kw in ['total', 'monto', 'facturacion', 'importe', 'suma', 'ventas']):
                            value_col = col
                            break
                    if not value_col:
                        value_col = num_cols[0]
                    
                    # Si son pocos elementos (≤8), usar donut; si son más, usar hbar
                    if n_rows <= 8:
                        chart_type = "donut"
                        chart_spec = {
                            "type": "donut",
                            "x": x_col,
                            "y": value_col,
                            "title": f"Distribución por {x_col.replace('_', ' ').title()}",
                            "sort": "desc"
                        }
                    else:
                        chart_type = "hbar"
                        chart_spec = {
                            "type": "hbar",
                            "x": x_col,
                            "y": value_col,
                            "title": f"Ranking por {x_col.replace('_', ' ').title()}",
                            "sort": "desc",
                            "top_n": 15
                        }
                    logger.info(f"✅ Generando gráfica categórica para reporte: {chart_spec}")
            
            elif any(kw in question_lower for kw in bar_keywords):
                chart_type = "bar"
                if "type" in chart_spec:
                    chart_spec["type"] = "bar"
            
            # 2. Detectar consultas temporales (facturación en el tiempo, por mes, etc.)
            temporal_keywords = ['en el tiempo', 'por mes', 'mensual', 'mensualmente',
                                'históric', 'evolución', 'tendencia', 'a lo largo',
                                'por periodo', 'por trimestre', 'por año', 'temporal']
            has_temporal_intent = any(kw in question_lower for kw in temporal_keywords)
            
            # Detectar si el dataframe tiene columnas temporales
            temporal_cols = [col for col in df.columns if any(
                time_word in str(col).lower() 
                for time_word in ['mes', 'fecha', 'periodo', 'trimestre', 'año', 'year', 'month', 'date', 'time']
            )]
            has_temporal_cols = len(temporal_cols) > 0
            
            # Si es temporal y no se especificó tipo, usar bar
            if (has_temporal_intent or has_temporal_cols) and chart_type in ("table", "metric"):
                chart_type = "bar"
                if not chart_spec or "type" not in chart_spec:
                    # Auto-detectar columnas para el gráfico temporal
                    num_cols = df.select_dtypes(include=['int64', 'float64', 'int32', 'float32']).columns.tolist()
                    time_col = temporal_cols[0] if temporal_cols else df.columns[0]
                    value_col = num_cols[-1] if num_cols else df.columns[-1]
                    
                    chart_spec = {
                        "type": "bar",
                        "x": time_col,
                        "y": value_col,
                        "title": f"Evolución de {value_col.replace('_', ' ').title()}",
                        "sort": None  # Mantener orden cronológico
                    }

            # --- Post-proceso: normalizar highlights inconsistentes ---
            text = _normalize_highlights(text)

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
        empresa_id: Optional[str] = None,
        periodo_soberano: Optional[dict] = None,
        sovereign_index: Optional[dict] = None,
        sovereign_profile: Optional[dict] = None,
    ) -> NL2SQLResult:
        """
        Pipeline completo: pregunta → SQL → ejecución → interpretación.

        Args:
            question: Pregunta en lenguaje natural (español)
            empresa_id: UUID de empresa para filtrar (opcional)
            periodo_soberano: Dict con desde/hasta/hasta_excl/granularidad del slider soberano
            sovereign_index: Índice completo de períodos del dataset
            sovereign_profile: Perfil soberano activo (de sovereign_profiles.PERFILES)

        Returns:
            NL2SQLResult con todos los datos
        """
        start_time = time.time()
        result = NL2SQLResult(question=question, sql="")

        # Construir contexto soberano de perfil (semántico)
        _profile_ctx = ""
        if sovereign_profile and _sp_profile_ctx:
            try:
                _profile_ctx = _sp_profile_ctx(sovereign_profile)
            except Exception:
                _profile_ctx = ""

        # Construir contexto soberano temporal
        _sovereign_ctx = _profile_ctx
        if periodo_soberano and _sp_build_prompt:
            try:
                _sovereign_ctx = _profile_ctx + _sp_build_prompt(periodo_soberano, sovereign_index or {})
            except Exception:
                _sovereign_ctx = _profile_ctx

        # Guardar perfil activo en el engine para que generate_sql lo use como filtro post-generación
        self._active_sovereign_profile = sovereign_profile

        try:
            # Paso 1: Generar SQL
            sql = self.generate_sql(question, empresa_id,
                                    sovereign_context=_sovereign_ctx,
                                    periodo_soberano=periodo_soberano or None)

            # Paso 1b: Detectar uso incorrecto de tabla `empresas` para clientes
            # Si se detecta, regenerar con instrucción explícita de corrección
            if self._uses_empresas_for_clients(sql):
                logger.warning("SQL usa 'empresas' para análisis de clientes — regenerando con corrección explícita")
                corrected_question = (
                    "CORRECCIÓN CRÍTICA: El SQL anterior usó la tabla `empresas` incorrectamente. "
                    "La tabla `empresas` es un catálogo interno de tenants, NUNCA úsala para análisis de clientes. "
                    "Para cualquier análisis de clientes, usa EXCLUSIVAMENTE `cfdi_ventas.receptor_rfc` y "
                    "`cfdi_ventas.receptor_nombre`. "
                    f"Pregunta original: {question}"
                )
                sql = self.generate_sql(corrected_question, empresa_id)

            # Interceptar fallback inútil: si GPT generó el mensaje de "no compatible",
            # reemplazar con un resumen estadístico real
            if "no compatible" in sql.lower() or "no disponible" in sql.lower() or ("mensaje" in sql.lower() and "select" in sql.lower() and "from" not in sql.lower().replace("from cfdi", "")):
                sql = (
                    f"SELECT COUNT(*) AS total_facturas, "
                    f"ROUND(AVG(total), 2) AS promedio, "
                    f"ROUND(STDDEV(total), 2) AS desviacion_estandar, "
                    f"ROUND(MIN(total), 2) AS minimo, "
                    f"ROUND(MAX(total), 2) AS maximo, "
                    f"ROUND(PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY total)::numeric, 2) AS percentil_25, "
                    f"ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY total)::numeric, 2) AS mediana, "
                    f"ROUND(PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY total)::numeric, 2) AS percentil_75 "
                    f"FROM cfdi_ventas LIMIT {self.max_rows};"
                )

            result.sql = sql

            # Paso 2: Validar seguridad
            is_valid, error_msg = self.validate_sql(sql)
            if not is_valid:
                result.error = f"🛡️ Seguridad: {error_msg}"
                result.execution_time = time.time() - start_time
                self.history.append(result)
                return result

            # Paso 3: Ejecutar query (con retry auto-fix si falla GROUP BY)
            try:
                df = self.execute_query(sql)
            except RuntimeError as exec_err:
                err_str = str(exec_err)
                if "GROUP BY" in err_str or "aggregate function" in err_str:
                    logger.warning(f"Error GROUP BY detectado, intentando auto-fix: {err_str[:120]}")
                    fixed_sql = self._fix_sql(sql, error_msg=err_str)
                    if fixed_sql != sql:
                        result.sql = fixed_sql
                        sql = fixed_sql
                        df = self.execute_query(sql)  # si falla de nuevo, propaga
                    else:
                        raise
                else:
                    raise

            # Post-procesar columnas de fecha truncadas a mes (DATE_TRUNC)
            # para mostrar etiquetas legibles como "Ene 2026" en vez de timestamps
            _MESES_ES = {
                1: 'Ene', 2: 'Feb', 3: 'Mar', 4: 'Abr', 5: 'May', 6: 'Jun',
                7: 'Jul', 8: 'Ago', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dic',
            }
            for col in df.columns:
                if col.lower() in ('mes', 'month', 'periodo', 'period'):
                    if pd.api.types.is_datetime64_any_dtype(df[col]):
                        df[col] = df[col].dt.month.map(_MESES_ES) + ' ' + df[col].dt.year.astype(str)
                    else:
                        try:
                            dt_col = pd.to_datetime(df[col], errors='coerce')
                            if dt_col.notna().all():
                                df[col] = dt_col.dt.month.map(_MESES_ES) + ' ' + dt_col.dt.year.astype(str)
                        except Exception:
                            pass

            result.dataframe = df
            result.row_count = len(df)

            # Paso 4: Interpretar resultados
            interpretation_result = self.interpret_results(question, sql, df)
            if isinstance(interpretation_result, tuple):
                if len(interpretation_result) == 3:
                    interpretation, chart_type, chart_spec = interpretation_result
                elif len(interpretation_result) == 2:
                    interpretation, chart_type = interpretation_result
                    chart_spec = {}
                elif len(interpretation_result) == 1:
                    interpretation = interpretation_result[0]
                    chart_type = "table"
                    chart_spec = {}
                else:
                    raise ValueError("interpret_results devolvió una tupla vacía")
            else:
                interpretation = str(interpretation_result)
                chart_type = "table"
                chart_spec = {}
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

    select_match = re.search(r'^\s*SELECT\s+(.*?)\bFROM\b', sql, re.IGNORECASE | re.DOTALL)
    if select_match and select_match.group(1).count(',') > 250:
        return False, "Query excede el ancho máximo permitido"

    if not re.match(r'^\s*(SELECT|WITH)\b', sql, re.IGNORECASE):
        return False, "Solo se permiten consultas SELECT"

    # Si empieza con WITH, verificar que contenga SELECT
    if re.match(r'^\s*WITH\b', sql, re.IGNORECASE):
        if not re.search(r'\bSELECT\b', sql, re.IGNORECASE):
            return False, "Las consultas WITH deben contener SELECT"

    for pattern in FORBIDDEN_PATTERNS:
        if re.search(pattern, sql, re.IGNORECASE):
            return False, f"Patrón SQL no permitido: {pattern}"

    statements = [s.strip() for s in sql.split(';') if s.strip()]
    if len(statements) > 1:
        return False, "Solo se permite una sentencia SQL"

    # Remover EXTRACT(...) para evitar falsos positivos con FROM dentro de funciones
    sql_cleaned = re.sub(r'EXTRACT\s*\([^)]+\)', '', sql, flags=re.IGNORECASE)
    
    # Extraer nombres de CTEs para no rechazarlos como tablas no permitidas
    cte_names = set(
        name.lower() for name in re.findall(r'\b(\w+)\s+AS\s*\(', sql_cleaned, re.IGNORECASE)
    )
    
    tables_in_query = re.findall(
        r'\bFROM\s+(\w+)|\bJOIN\s+(\w+)',
        sql_cleaned,
        re.IGNORECASE
    )
    allowed = set(ALLOWED_TABLES) | cte_names
    for match_groups in tables_in_query:
        for table in match_groups:
            if table and table.lower() not in allowed:
                return False, f"Tabla no permitida: {table}"

    return True, "OK"


def get_example_questions() -> List[Dict]:
    """Retorna las preguntas de ejemplo organizadas por categoría."""
    return EXAMPLE_QUESTIONS
