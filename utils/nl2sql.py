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
    chart_suggestion: str = ""  # bar, line, pie, table, metric

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

            logger.info(f"SQL generado: {sql[:100]}...")
            return sql

        except Exception as e:
            logger.error(f"Error generando SQL: {e}")
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
9. Responde SOLO con la consulta SQL, sin explicación ni markdown.
10. Si la pregunta no puede responderse con los datos disponibles, genera: SELECT 'Pregunta no compatible con los datos disponibles' AS mensaje;
{empresa_filter}

{SCHEMA_CONTEXT}

EJEMPLOS:
Pregunta: ¿Cuánto se facturó este mes?
SQL: SELECT SUM(total) AS total_facturado, moneda FROM cfdi_ventas WHERE DATE_TRUNC('month', fecha_emision) = DATE_TRUNC('month', CURRENT_DATE) GROUP BY moneda LIMIT {self.max_rows};

Pregunta: Top 5 clientes por facturación
SQL: SELECT receptor_nombre AS cliente, COUNT(*) AS num_facturas, SUM(total * tipo_cambio) AS total_mxn FROM cfdi_ventas GROUP BY receptor_nombre ORDER BY total_mxn DESC LIMIT 5;

Pregunta: Ventas mensuales de este año
SQL: SELECT DATE_TRUNC('month', fecha_emision) AS mes, COUNT(*) AS facturas, SUM(total * tipo_cambio) AS total_mxn FROM cfdi_ventas WHERE EXTRACT(YEAR FROM fecha_emision) = EXTRACT(YEAR FROM CURRENT_DATE) GROUP BY mes ORDER BY mes LIMIT {self.max_rows};
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
        tables_in_query = re.findall(
            r'\bFROM\s+(\w+)|\bJOIN\s+(\w+)',
            sql,
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
    ) -> Tuple[str, str]:
        """
        Genera una interpretación en lenguaje natural de los resultados.

        Args:
            question: Pregunta original
            sql: SQL ejecutado
            df: DataFrame con resultados

        Returns:
            Tupla (interpretación, sugerencia_de_gráfica)
        """
        if df.empty:
            return "No se encontraron datos para esta consulta.", "table"

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

Además, en la ÚLTIMA línea, indica el tipo de gráfica más apropiada para estos datos.
Usa exactamente uno de estos valores: bar, line, pie, table, metric, scatter
Formato de la última línea: CHART_TYPE: <tipo>
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

            # Extraer tipo de gráfica
            chart_type = "table"
            chart_match = re.search(r'CHART_TYPE:\s*(\w+)', text)
            if chart_match:
                chart_type = chart_match.group(1).lower()
                text = re.sub(r'\n?CHART_TYPE:\s*\w+', '', text).strip()

            return text, chart_type

        except Exception as e:
            logger.error(f"Error interpretando resultados: {e}")
            return f"Se obtuvieron {row_count} resultados.", "table"

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
            interpretation, chart_type = self.interpret_results(question, sql, df)
            result.interpretation = interpretation
            result.chart_suggestion = chart_type

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

    tables_in_query = re.findall(
        r'\bFROM\s+(\w+)|\bJOIN\s+(\w+)',
        sql,
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
