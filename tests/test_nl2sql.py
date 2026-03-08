"""
Tests para el motor NL2SQL y la UI del Asistente de Datos.

Cobertura:
- Validación de SQL (seguridad, tablas permitidas, patrones prohibidos)
- Limpieza de SQL (markdown, whitespace)  
- Preguntas de ejemplo
- Dataclass NL2SQLResult
- Singleton engine helpers
- Auto-chart fallback
- Schema context integrity
"""

import pytest
import re
from datetime import datetime
from io import StringIO
from unittest.mock import MagicMock, patch, PropertyMock
import pandas as pd
import json

from utils.nl2sql import (
    NL2SQLResult,
    validate_sql_static,
    get_example_questions,
    ALLOWED_TABLES,
    FORBIDDEN_PATTERNS,
    SCHEMA_CONTEXT,
    MAX_ROWS,
    MAX_SQL_LENGTH,
    QUERY_TIMEOUT_SECONDS,
)


# =====================================================================
# Tests de NL2SQLResult
# =====================================================================
class TestNL2SQLResult:
    """Tests para el dataclass NL2SQLResult."""

    def test_default_values(self):
        result = NL2SQLResult(question="test", sql="SELECT 1;")
        assert result.question == "test"
        assert result.sql == "SELECT 1;"
        assert result.dataframe is None
        assert result.interpretation == ""
        assert result.execution_time == 0.0
        assert result.row_count == 0
        assert result.error is None
        assert result.chart_suggestion == ""
        assert isinstance(result.timestamp, datetime)

    def test_success_property_true(self):
        result = NL2SQLResult(question="q", sql="s")
        assert result.success is True

    def test_success_property_false(self):
        result = NL2SQLResult(question="q", sql="s", error="algo falló")
        assert result.success is False

    def test_to_dict(self):
        result = NL2SQLResult(
            question="¿Cuántas facturas?",
            sql="SELECT COUNT(*) FROM cfdi_ventas;",
            interpretation="Hay 500 facturas",
            execution_time=1.5,
            row_count=1,
            chart_suggestion="metric",
        )
        d = result.to_dict()
        assert d["question"] == "¿Cuántas facturas?"
        assert d["sql"] == "SELECT COUNT(*) FROM cfdi_ventas;"
        assert d["interpretation"] == "Hay 500 facturas"
        assert d["execution_time"] == 1.5
        assert d["row_count"] == 1
        assert d["error"] is None
        assert d["chart_suggestion"] == "metric"
        assert "timestamp" in d

    def test_to_dict_with_error(self):
        result = NL2SQLResult(question="q", sql="s", error="timeout")
        d = result.to_dict()
        assert d["error"] == "timeout"

    def test_with_dataframe(self):
        df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
        result = NL2SQLResult(question="q", sql="s", dataframe=df, row_count=2)
        assert result.dataframe is not None
        assert len(result.dataframe) == 2


# =====================================================================
# Tests de validación estática de SQL
# =====================================================================
class TestValidateSQL:
    """Tests para validate_sql_static — corazón de seguridad."""

    # --- Queries válidos ---
    def test_valid_simple_select(self):
        ok, msg = validate_sql_static("SELECT * FROM cfdi_ventas LIMIT 10;")
        assert ok is True
        assert msg == "OK"

    def test_valid_with_join(self):
        sql = (
            "SELECT v.receptor_nombre, SUM(c.importe) "
            "FROM cfdi_ventas v JOIN cfdi_conceptos c ON v.id = c.cfdi_venta_id "
            "GROUP BY v.receptor_nombre LIMIT 10;"
        )
        ok, msg = validate_sql_static(sql)
        assert ok is True

    def test_valid_with_where(self):
        sql = "SELECT total FROM cfdi_ventas WHERE fecha_emision > '2025-01-01' LIMIT 100;"
        ok, msg = validate_sql_static(sql)
        assert ok is True

    def test_valid_with_aggregation(self):
        sql = (
            "SELECT DATE_TRUNC('month', fecha_emision) AS mes, COUNT(*) AS n, SUM(total) AS total "
            "FROM cfdi_ventas GROUP BY mes ORDER BY mes LIMIT 1000;"
        )
        ok, msg = validate_sql_static(sql)
        assert ok is True

    def test_valid_with_subquery(self):
        sql = (
            "SELECT receptor_nombre, total FROM cfdi_ventas "
            "WHERE total > (SELECT AVG(total) FROM cfdi_ventas) LIMIT 50;"
        )
        ok, msg = validate_sql_static(sql)
        assert ok is True

    def test_valid_views(self):
        sql = "SELECT * FROM v_cartera_clientes LIMIT 100;"
        ok, msg = validate_sql_static(sql)
        assert ok is True

    def test_valid_all_allowed_tables(self):
        for table in ALLOWED_TABLES:
            sql = f"SELECT * FROM {table} LIMIT 1;"
            ok, msg = validate_sql_static(sql)
            assert ok is True, f"Tabla {table} debería ser válida pero: {msg}"

    # --- Queries inválidos: DML/DDL ---
    def test_reject_insert(self):
        sql = "INSERT INTO cfdi_ventas (total) VALUES (100);"
        ok, msg = validate_sql_static(sql)
        assert ok is False

    def test_reject_update(self):
        sql = "UPDATE cfdi_ventas SET total = 0;"
        ok, msg = validate_sql_static(sql)
        assert ok is False

    def test_reject_delete(self):
        sql = "DELETE FROM cfdi_ventas;"
        ok, msg = validate_sql_static(sql)
        assert ok is False

    def test_reject_drop(self):
        sql = "DROP TABLE cfdi_ventas;"
        ok, msg = validate_sql_static(sql)
        assert ok is False

    def test_reject_alter(self):
        sql = "ALTER TABLE cfdi_ventas ADD COLUMN hack TEXT;"
        ok, msg = validate_sql_static(sql)
        assert ok is False

    def test_reject_create(self):
        sql = "CREATE TABLE evil (id INT);"
        ok, msg = validate_sql_static(sql)
        assert ok is False

    def test_reject_truncate(self):
        sql = "TRUNCATE cfdi_ventas;"
        ok, msg = validate_sql_static(sql)
        assert ok is False

    # --- Queries inválidos: inyección ---
    def test_reject_multi_statement(self):
        sql = "SELECT 1 FROM cfdi_ventas; DROP TABLE cfdi_ventas;"
        ok, msg = validate_sql_static(sql)
        assert ok is False

    def test_reject_sql_comment_dash(self):
        sql = "SELECT * FROM cfdi_ventas -- DROP TABLE;"
        ok, msg = validate_sql_static(sql)
        assert ok is False

    def test_reject_sql_comment_block(self):
        sql = "SELECT * FROM cfdi_ventas /* evil */ LIMIT 1;"
        ok, msg = validate_sql_static(sql)
        assert ok is False

    # --- Tablas no permitidas ---
    def test_reject_forbidden_table(self):
        sql = "SELECT * FROM pg_catalog LIMIT 1;"
        ok, msg = validate_sql_static(sql)
        assert ok is False

    def test_reject_unknown_table(self):
        sql = "SELECT * FROM usuarios_secretos LIMIT 1;"
        ok, msg = validate_sql_static(sql)
        assert ok is False
        assert "Tabla no permitida" in msg

    def test_reject_information_schema(self):
        sql = "SELECT * FROM information_schema LIMIT 1;"
        ok, msg = validate_sql_static(sql)
        assert ok is False

    # --- Límites ---
    def test_reject_oversized_query(self):
        sql = "SELECT " + "a," * 1000 + "b FROM cfdi_ventas LIMIT 1;"
        ok, msg = validate_sql_static(sql)
        assert ok is False
        assert "excede" in msg.lower()

    def test_reject_overwide_select_query(self):
        columnas = ", ".join(f"c{i}" for i in range(252))
        sql = f"SELECT {columnas} FROM cfdi_ventas LIMIT 1;"
        ok, msg = validate_sql_static(sql)
        assert ok is False
        assert "ancho" in msg.lower()

    # --- Edge cases ---
    def test_case_insensitive_select(self):
        sql = "select * from cfdi_ventas limit 10;"
        ok, msg = validate_sql_static(sql)
        assert ok is True

    def test_whitespace_before_select(self):
        sql = "   SELECT * FROM cfdi_ventas LIMIT 10;"
        ok, msg = validate_sql_static(sql)
        assert ok is True

    def test_empty_string(self):
        ok, msg = validate_sql_static("")
        assert ok is False

    def test_non_select_start(self):
        ok, msg = validate_sql_static("EXPLAIN SELECT * FROM cfdi_ventas;")
        assert ok is False


# =====================================================================
# Tests de preguntas de ejemplo
# =====================================================================
class TestExampleQuestions:
    """Tests para las preguntas de ejemplo."""

    def test_has_categories(self):
        examples = get_example_questions()
        assert len(examples) >= 4

    def test_each_category_has_questions(self):
        examples = get_example_questions()
        for cat in examples:
            assert "category" in cat
            assert "icon" in cat
            assert "questions" in cat
            assert len(cat["questions"]) >= 2

    def test_questions_are_spanish(self):
        examples = get_example_questions()
        for cat in examples:
            for q in cat["questions"]:
                assert isinstance(q, str)
                assert len(q) > 10
                # Mayoría contiene ¿ o palabras en español
                assert any(w in q.lower() for w in [
                    '¿', 'cuánto', 'cuáles', 'cuál', 'qué', 'cómo',
                    'muéstrame', 'compara', 'promedio', 'top', 'ventas',
                    'facturas', 'clientes', 'productos', 'pagos', 'saldo'
                ]), f"Pregunta no parece español: {q}"

    def test_categories_unique(self):
        examples = get_example_questions()
        cats = [e["category"] for e in examples]
        assert len(cats) == len(set(cats))


# =====================================================================
# Tests de constantes y esquema
# =====================================================================
class TestConstants:
    """Tests para constantes y configuración."""

    def test_allowed_tables_not_empty(self):
        assert len(ALLOWED_TABLES) >= 6

    def test_allowed_tables_has_core_tables(self):
        core = ['cfdi_ventas', 'cfdi_conceptos', 'cfdi_pagos', 'empresas', 'clientes_master']
        for table in core:
            assert table in ALLOWED_TABLES

    def test_schema_context_mentions_all_tables(self):
        for table in ALLOWED_TABLES:
            assert table in SCHEMA_CONTEXT, f"Tabla {table} no mencionada en SCHEMA_CONTEXT"

    def test_max_rows_reasonable(self):
        assert 100 <= MAX_ROWS <= 10000

    def test_max_sql_length_reasonable(self):
        assert 500 <= MAX_SQL_LENGTH <= 10000

    def test_timeout_reasonable(self):
        assert 5 <= QUERY_TIMEOUT_SECONDS <= 120

    def test_forbidden_patterns_not_empty(self):
        assert len(FORBIDDEN_PATTERNS) >= 5

    def test_forbidden_patterns_are_valid_regex(self):
        for pattern in FORBIDDEN_PATTERNS:
            try:
                re.compile(pattern)
            except re.error:
                pytest.fail(f"Patrón regex inválido: {pattern}")


# =====================================================================
# Tests del engine (mock)
# =====================================================================
class TestNL2SQLEngineMock:
    """Tests del engine con mocks (sin conexión real a DB/OpenAI)."""

    @patch("utils.nl2sql.OpenAI")
    @patch("utils.nl2sql.psycopg2")
    def test_engine_init(self, mock_pg, mock_openai):
        from utils.nl2sql import NL2SQLEngine
        engine = NL2SQLEngine(
            connection_string="postgresql://test:test@localhost/test",
            api_key="sk-test",
        )
        assert engine.model == "gpt-4o"
        assert engine.max_rows == MAX_ROWS
        assert engine.timeout == QUERY_TIMEOUT_SECONDS
        assert len(engine.history) == 0

    @patch("utils.nl2sql.OpenAI")
    @patch("utils.nl2sql.psycopg2")
    def test_engine_validate_sql(self, mock_pg, mock_openai):
        from utils.nl2sql import NL2SQLEngine
        engine = NL2SQLEngine(
            connection_string="postgresql://test:test@localhost/test",
            api_key="sk-test",
        )
        ok, msg = engine.validate_sql("SELECT * FROM cfdi_ventas LIMIT 10;")
        assert ok is True

        ok, msg = engine.validate_sql("DROP TABLE cfdi_ventas;")
        assert ok is False

    @patch("utils.nl2sql.OpenAI")
    @patch("utils.nl2sql.psycopg2")
    def test_engine_clean_sql(self, mock_pg, mock_openai):
        from utils.nl2sql import NL2SQLEngine
        engine = NL2SQLEngine(
            connection_string="postgresql://test:test@localhost/test",
            api_key="sk-test",
        )

        # Test markdown cleanup
        raw = "```sql\nSELECT * FROM cfdi_ventas LIMIT 10\n```"
        cleaned = engine._clean_sql(raw)
        assert cleaned.startswith("SELECT")
        assert cleaned.endswith(";")
        assert "```" not in cleaned

    @patch("utils.nl2sql.OpenAI")
    @patch("utils.nl2sql.psycopg2")
    def test_engine_build_system_prompt(self, mock_pg, mock_openai):
        from utils.nl2sql import NL2SQLEngine
        engine = NL2SQLEngine(
            connection_string="postgresql://test:test@localhost/test",
            api_key="sk-test",
        )
        prompt = engine._build_system_prompt()
        assert "SELECT" in prompt
        assert "cfdi_ventas" in prompt
        assert str(MAX_ROWS) in prompt

    @patch("utils.nl2sql.OpenAI")
    @patch("utils.nl2sql.psycopg2")
    def test_engine_build_system_prompt_with_empresa(self, mock_pg, mock_openai):
        from utils.nl2sql import NL2SQLEngine
        engine = NL2SQLEngine(
            connection_string="postgresql://test:test@localhost/test",
            api_key="sk-test",
        )
        prompt = engine._build_system_prompt(empresa_id="abc-123")
        assert "abc-123" in prompt
        assert "empresa_id" in prompt

    @patch("utils.nl2sql.OpenAI")
    @patch("utils.nl2sql.psycopg2")
    def test_engine_history(self, mock_pg, mock_openai):
        from utils.nl2sql import NL2SQLEngine
        engine = NL2SQLEngine(
            connection_string="postgresql://test:test@localhost/test",
            api_key="sk-test",
        )
        assert len(engine.get_history()) == 0

        # Simular query en historial
        engine.history.append(
            NL2SQLResult(question="test", sql="SELECT 1;", row_count=1)
        )
        assert len(engine.get_history()) == 1

        engine.clear_history()
        assert len(engine.get_history()) == 0

    @patch("utils.nl2sql.OpenAI")
    @patch("utils.nl2sql.psycopg2")
    def test_ask_with_invalid_sql(self, mock_pg, mock_openai):
        from utils.nl2sql import NL2SQLEngine
        engine = NL2SQLEngine(
            connection_string="postgresql://test:test@localhost/test",
            api_key="sk-test",
        )

        # Mock generate_sql to return invalid SQL
        engine.generate_sql = MagicMock(return_value="DROP TABLE cfdi_ventas;")

        result = engine.ask("borra todo")
        assert result.success is False
        assert "Seguridad" in result.error
        assert len(engine.history) == 1

    @patch("utils.nl2sql.OpenAI")
    @patch("utils.nl2sql.psycopg2")
    def test_ask_with_generate_error(self, mock_pg, mock_openai):
        from utils.nl2sql import NL2SQLEngine
        engine = NL2SQLEngine(
            connection_string="postgresql://test:test@localhost/test",
            api_key="sk-test",
        )

        # Mock generate_sql to raise error
        engine.generate_sql = MagicMock(side_effect=ValueError("API error"))

        result = engine.ask("test question")
        assert result.success is False
        assert "Error generando SQL" in result.error

    @patch("utils.nl2sql.OpenAI")
    @patch("utils.nl2sql.psycopg2")
    def test_ask_success_pipeline(self, mock_pg, mock_openai):
        from utils.nl2sql import NL2SQLEngine
        engine = NL2SQLEngine(
            connection_string="postgresql://test:test@localhost/test",
            api_key="sk-test",
        )

        # Mock each step
        engine.generate_sql = MagicMock(
            return_value="SELECT COUNT(*) AS total FROM cfdi_ventas;"
        )
        engine.execute_query = MagicMock(
            return_value=pd.DataFrame({"total": [500]})
        )
        engine.interpret_results = MagicMock(
            return_value=("Hay 500 facturas en total.", "metric")
        )

        result = engine.ask("¿Cuántas facturas hay?")
        assert result.success is True
        assert result.sql == "SELECT COUNT(*) AS total FROM cfdi_ventas;"
        assert result.row_count == 1
        assert result.interpretation == "Hay 500 facturas en total."
        assert result.chart_suggestion == "metric"
        assert result.execution_time > 0

    @patch("utils.nl2sql.OpenAI")
    @patch("utils.nl2sql.psycopg2")
    def test_ask_formats_month_columns_and_chart_spec(self, mock_pg, mock_openai):
        from utils.nl2sql import NL2SQLEngine
        engine = NL2SQLEngine(
            connection_string="postgresql://test:test@localhost/test",
            api_key="sk-test",
        )

        engine.generate_sql = MagicMock(
            return_value="SELECT DATE_TRUNC('month', fecha_emision) AS mes FROM cfdi_ventas;"
        )
        engine.execute_query = MagicMock(
            return_value=pd.DataFrame({"mes": pd.to_datetime(["2026-01-01", "2026-02-01"])})
        )
        engine.interpret_results = MagicMock(
            return_value=("Serie mensual", "bar", {"x": "mes", "y": "total"})
        )

        result = engine.ask("ventas por mes")

        assert result.success is True
        assert result.dataframe["mes"].tolist() == ["Ene 2026", "Feb 2026"]
        assert result.chart_suggestion == "bar"
        assert result.chart_spec == {"x": "mes", "y": "total"}

    @patch("utils.nl2sql.OpenAI")
    @patch("utils.nl2sql.psycopg2")
    def test_ask_replaces_non_compatible_fallback(self, mock_pg, mock_openai):
        from utils.nl2sql import NL2SQLEngine
        engine = NL2SQLEngine(
            connection_string="postgresql://test:test@localhost/test",
            api_key="sk-test",
        )

        engine.generate_sql = MagicMock(return_value="Mensaje no compatible con esta pregunta")
        engine.execute_query = MagicMock(return_value=pd.DataFrame({"total_facturas": [10]}))
        engine.interpret_results = MagicMock(return_value=("Resumen estadístico", "table"))

        result = engine.ask("algo ambiguo")

        assert result.success is True
        assert "FROM cfdi_ventas" in result.sql
        assert "AVG(total)" in result.sql

    @patch("utils.nl2sql.OpenAI")
    @patch("utils.nl2sql.psycopg2")
    def test_ask_accepts_plain_string_interpretation(self, mock_pg, mock_openai):
        from utils.nl2sql import NL2SQLEngine
        engine = NL2SQLEngine(
            connection_string="postgresql://test:test@localhost/test",
            api_key="sk-test",
        )

        engine.generate_sql = MagicMock(return_value="SELECT COUNT(*) AS total FROM cfdi_ventas;")
        engine.execute_query = MagicMock(return_value=pd.DataFrame({"total": [5]}))
        engine.interpret_results = MagicMock(return_value="Texto simple")

        result = engine.ask("conteo")

        assert result.success is True
        assert result.interpretation == "Texto simple"
        assert result.chart_suggestion == "table"
        assert result.chart_spec == {}


# =====================================================================
# Tests de UI helpers (sin Streamlit real)
# =====================================================================
class TestUIHelpers:
    """Tests para helpers de la UI del asistente."""

    def test_build_result_message_success(self):
        from main.data_assistant import _build_result_message
        result = NL2SQLResult(
            question="test",
            sql="SELECT 1;",
            dataframe=pd.DataFrame({"a": [1]}),
            interpretation="Resultado ok",
            execution_time=0.5,
            row_count=1,
            chart_suggestion="metric",
        )
        msg = _build_result_message(result)
        assert msg["role"] == "assistant"
        assert msg["success"] is True
        assert msg["error"] is None
        assert "dataframe_json" in msg

    def test_build_result_message_error(self):
        from main.data_assistant import _build_result_message
        result = NL2SQLResult(
            question="test",
            sql="DROP TABLE x;",
            error="Seguridad: no permitido",
        )
        msg = _build_result_message(result)
        assert msg["success"] is False
        assert msg["error"] == "Seguridad: no permitido"
        assert "dataframe_json" not in msg

    def test_build_result_message_empty_df(self):
        from main.data_assistant import _build_result_message
        result = NL2SQLResult(
            question="test",
            sql="SELECT 1 WHERE false;",
            dataframe=pd.DataFrame(),
            interpretation="Sin datos",
            row_count=0,
        )
        msg = _build_result_message(result)
        assert msg["success"] is True
        assert "dataframe_json" not in msg  # Empty DF not serialized

    def test_dataframe_json_roundtrip(self):
        from main.data_assistant import _build_result_message
        df = pd.DataFrame({
            "cliente": ["Acme", "Beta", "Gamma"],
            "total": [1000.50, 2500.75, 750.00],
            "facturas": [10, 25, 5],
        })
        result = NL2SQLResult(
            question="top clientes",
            sql="SELECT ...",
            dataframe=df,
            row_count=3,
        )
        msg = _build_result_message(result)
        assert "dataframe_json" in msg

        # Roundtrip
        df_back = pd.read_json(StringIO(msg["dataframe_json"]), orient="split")
        assert len(df_back) == 3
        assert list(df_back.columns) == ["cliente", "total", "facturas"]


# =====================================================================
# Tests de seguridad adicionales
# =====================================================================
class TestSecurityEdgeCases:
    """Tests de seguridad para edge cases."""

    def test_union_injection(self):
        sql = (
            "SELECT * FROM cfdi_ventas UNION SELECT * FROM pg_catalog LIMIT 10;"
        )
        ok, _ = validate_sql_static(sql)
        assert ok is False  # pg_catalog forbidden

    def test_case_mixed_forbidden(self):
        sql = "sElEcT * FROM cfdi_ventas; DrOp TABLE cfdi_ventas;"
        ok, _ = validate_sql_static(sql)
        assert ok is False

    def test_grant_revoke(self):
        ok, _ = validate_sql_static("GRANT ALL ON cfdi_ventas TO public;")
        assert ok is False

        ok, _ = validate_sql_static("REVOKE ALL ON cfdi_ventas FROM public;")
        assert ok is False

    def test_copy_command(self):
        sql = "COPY cfdi_ventas TO '/tmp/evil.csv';"
        ok, _ = validate_sql_static(sql)
        assert ok is False

    def test_exec_command(self):
        sql = "EXEC xp_cmdshell 'whoami';"
        ok, _ = validate_sql_static(sql)
        assert ok is False

    def test_select_into_outfile(self):
        sql = "SELECT * INTO OUTFILE '/tmp/data' FROM cfdi_ventas;"
        ok, _ = validate_sql_static(sql)
        assert ok is False

    def test_valid_complex_query(self):
        sql = (
            "SELECT v.receptor_nombre AS cliente, "
            "COUNT(DISTINCT v.id) AS facturas, "
            "SUM(v.total * v.tipo_cambio) AS total_mxn, "
            "ROUND(AVG(p.dias_credito), 1) AS dias_credito_prom "
            "FROM cfdi_ventas v "
            "LEFT JOIN cfdi_pagos p ON v.uuid_sat = p.cfdi_venta_uuid "
            "WHERE v.fecha_emision >= '2025-01-01' "
            "GROUP BY v.receptor_nombre "
            "ORDER BY total_mxn DESC "
            "LIMIT 20;"
        )
        ok, msg = validate_sql_static(sql)
        assert ok is True, f"Debería ser válido pero: {msg}"
