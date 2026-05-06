from io import StringIO

import pandas as pd

from main import data_assistant
from utils.sovereign_profiles import PERFILES, apply_profile_sql_filter
from utils.auth import User, UserRole


def test_get_runtime_credentials_uses_server_side_secrets_for_non_superadmin(monkeypatch):
    user = User("ana", "ana@test.com", "Ana", UserRole.ANALYST, empresa_id="emp-1")

    monkeypatch.setattr(data_assistant, "get_current_user", lambda: user)
    monkeypatch.setattr(data_assistant.st, "session_state", {
        "nl2sql_neon_url": "postgresql://frontend-should-not-be-used",
        "nl2sql_api_key": "frontend-key-should-not-be-used",
        "nl2sql_model": "gpt-4o-mini",
        "passkey_valido": True,
    }, raising=False)
    monkeypatch.setenv("NEON_DATABASE_URL", "postgresql://server-safe-url")
    monkeypatch.setenv("OPENAI_API_KEY", "server-safe-key")

    neon_url, api_key, model = data_assistant._get_runtime_credentials()

    assert neon_url == "postgresql://server-safe-url"
    assert api_key == "server-safe-key"
    assert model == "gpt-4o-mini"


def test_get_runtime_credentials_uses_server_side_secrets_for_tenant_admin(monkeypatch):
    user = User("soluciones", "admin@test.com", "Admin", UserRole.ADMIN, empresa_id="emp-1")

    monkeypatch.setattr(data_assistant, "get_current_user", lambda: user)
    monkeypatch.setattr(data_assistant.st, "session_state", {
        "nl2sql_neon_url": "postgresql://manual-admin-url",
        "nl2sql_api_key": "manual-admin-key",
        "nl2sql_model": "gpt-4o",
        "passkey_valido": True,
    }, raising=False)
    monkeypatch.setenv("NEON_DATABASE_URL", "postgresql://server-safe-url")
    monkeypatch.setenv("OPENAI_API_KEY", "server-safe-key")

    neon_url, api_key, model = data_assistant._get_runtime_credentials()

    assert neon_url == "postgresql://server-safe-url"
    assert api_key == "server-safe-key"
    assert model == "gpt-4o"


def test_get_runtime_credentials_reads_streamlit_secrets_when_env_is_missing(monkeypatch):
    user = User("ana", "ana@test.com", "Ana", UserRole.ANALYST, empresa_id="emp-1")

    monkeypatch.setattr(data_assistant, "get_current_user", lambda: user)
    monkeypatch.setattr(data_assistant.st, "session_state", {
        "nl2sql_model": "gpt-4o-mini",
        "passkey_valido": True,
    }, raising=False)
    monkeypatch.delenv("NEON_DATABASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(data_assistant.st, "secrets", {
        "NEON_DATABASE_URL": "postgresql://secret-safe-url",
        "OPENAI_API_KEY": "secret-safe-key",
    }, raising=False)

    neon_url, api_key, model = data_assistant._get_runtime_credentials()

    assert neon_url == "postgresql://secret-safe-url"
    assert api_key == "secret-safe-key"
    assert model == "gpt-4o-mini"


def test_get_runtime_credentials_reads_nested_streamlit_secrets_aliases(monkeypatch):
    user = User("ana", "ana@test.com", "Ana", UserRole.ANALYST, empresa_id="emp-1")

    monkeypatch.setattr(data_assistant, "get_current_user", lambda: user)
    monkeypatch.setattr(data_assistant.st, "session_state", {
        "nl2sql_model": "gpt-4o-mini",
        "passkey_valido": True,
    }, raising=False)
    monkeypatch.delenv("NEON_DATABASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(data_assistant.st, "secrets", {
        "connections": {
            "neon": {"url": "postgresql://nested-secret-url"},
            "openai": {"api_key": "nested-secret-key"},
        }
    }, raising=False)

    neon_url, api_key, model = data_assistant._get_runtime_credentials()

    assert neon_url == "postgresql://nested-secret-url"
    assert api_key == "nested-secret-key"
    assert model == "gpt-4o-mini"


def test_get_server_credential_details_reports_env_source(monkeypatch):
    monkeypatch.setenv("NEON_DATABASE_URL", "postgresql://env-url")

    value, source = data_assistant._get_server_credential_details("NEON_DATABASE_URL")

    assert value == "postgresql://env-url"
    assert source == "env"


def test_get_server_credential_details_reports_nested_secret_source(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(data_assistant.st, "secrets", {
        "connections": {
            "openai": {"api_key": "nested-secret-key"},
        }
    }, raising=False)

    value, source = data_assistant._get_server_credential_details("OPENAI_API_KEY")

    assert value == "nested-secret-key"
    assert source == "secrets.connections.openai.api_key"


def test_get_runtime_credentials_uses_global_premium_session_api_key(monkeypatch):
    user = User("ana", "ana@test.com", "Ana", UserRole.ANALYST, empresa_id="emp-1")

    monkeypatch.setattr(data_assistant, "get_current_user", lambda: user)
    monkeypatch.setattr(data_assistant.st, "session_state", {
        "nl2sql_model": "gpt-4o-mini",
        "openai_api_key": "session-premium-key",
        "passkey_valido": True,
    }, raising=False)
    monkeypatch.setenv("NEON_DATABASE_URL", "postgresql://server-safe-url")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(data_assistant.st, "secrets", {}, raising=False)

    neon_url, api_key, model = data_assistant._get_runtime_credentials()

    assert neon_url == "postgresql://server-safe-url"
    assert api_key == "session-premium-key"
    assert model == "gpt-4o-mini"


def test_get_runtime_api_key_details_reports_session_source(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(data_assistant.st, "session_state", {
        "openai_api_key": "session-premium-key",
        "passkey_valido": True,
    }, raising=False)
    monkeypatch.setattr(data_assistant.st, "secrets", {}, raising=False)

    value, source = data_assistant._get_runtime_api_key_details()

    assert value == "session-premium-key"
    assert source == "session.openai_api_key"


def test_get_runtime_api_key_details_blocks_access_without_premium_passkey(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "server-safe-key")
    monkeypatch.setattr(data_assistant.st, "session_state", {}, raising=False)

    value, source = data_assistant._get_runtime_api_key_details()

    assert value == ""
    assert source == "premium-locked"


def test_stage_mode_config_segregates_future_features():
    current_stage_modes, second_stage_options = data_assistant._get_stage_mode_config()

    assert current_stage_modes == ["💬 Chat", "🧭 Guiado"]
    assert [option["label"] for option in second_stage_options] == [
        "🛠️ SQL Playground",
        "🗄️ Esquema",
        "🕰️ Historial",
        "💰 ROI",
    ]


def test_rentabilidad_profile_is_blocked_until_cost_inputs_exist():
    profile = PERFILES["rentabilidad"]

    assert profile["enabled"] is False
    assert "costos" in profile["blocked_reason"].lower()


def test_conciliacion_profile_is_blocked_until_reconciliation_tables_exist():
    profile = PERFILES["conciliacion"]

    assert profile["enabled"] is False
    assert "reconciliación" in profile["blocked_reason"].lower() or "reconciliacion" in profile["blocked_reason"].lower()


def test_apply_profile_sql_filter_ignores_within_group_clauses():
    sql = (
        "SELECT COUNT(*) AS total_facturas, "
        "ROUND(PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY total * COALESCE(tipo_cambio, 1))::numeric, 2) AS percentil_25 "
        "FROM cfdi_ventas WHERE fecha_emision >= '2024-01-01' AND fecha_emision < '2026-04-01' LIMIT 1000;"
    )

    updated_sql = apply_profile_sql_filter(sql, PERFILES["resumen_ejecutivo"])

    assert "WITHIN GROUP (ORDER BY total * COALESCE(tipo_cambio, 1))" in updated_sql
    assert "WITHIN GROUP (AND" not in updated_sql
    assert "tipo_comprobante = 'I'" in updated_sql
    assert "metodo_pago IN ('PUE', 'PPD')" in updated_sql


def test_apply_profile_sql_filter_injects_sales_scope_inside_concept_subquery():
    sql = (
        "SELECT COUNT(*) AS total_conceptos, "
        "ROUND(AVG(valor_unitario), 2) AS precio_promedio "
        "FROM cfdi_conceptos "
        "WHERE cfdi_venta_id IN ("
        "SELECT id FROM cfdi_ventas "
        "WHERE fecha_emision >= '2024-01-01' AND fecha_emision < '2026-04-01'"
        ") LIMIT 1000;"
    )

    updated_sql = apply_profile_sql_filter(sql, PERFILES["resumen_ejecutivo"])

    assert "FROM cfdi_conceptos" in updated_sql
    assert "FROM cfdi_ventas WHERE fecha_emision >= '2024-01-01' AND fecha_emision < '2026-04-01' AND tipo_comprobante = 'I' AND metodo_pago IN ('PUE', 'PPD')" in updated_sql
    assert "FROM cfdi_conceptos WHERE cfdi_venta_id IN" in updated_sql
    assert ";)" not in updated_sql


def test_sidebar_examples_keep_advanced_questions_visible_but_blocked():
    examples = data_assistant._get_sidebar_examples_config()
    questions = {
        question["text"]: question
        for category in examples
        for question in category["questions"]
    }

    assert questions["¿Cuánto se facturó en total el mes pasado?"]["enabled"] is True
    assert questions["Segmentación RFM de clientes"]["enabled"] is False
    assert "RFM" in questions["Segmentación RFM de clientes"]["blocked_reason"]


def test_chat_guidance_lists_separate_active_and_future_questions():
    active_questions, future_questions = data_assistant._get_chat_guidance_lists()

    assert "¿Cuánto se facturó en total el mes pasado?" in active_questions
    assert "Segmentación RFM de clientes" in future_questions


def test_build_numeric_column_config_formats_money_with_thousand_separators():
    df = pd.DataFrame({
        "ventas": [500145.74],
        "promedio_movil_3m": [427108.42],
        "ventas_mes": [412618.80],
        "acumulado": [10116520.69],
        "registros": [27],
    })

    col_config = data_assistant._build_numeric_column_config(df)

    assert col_config["ventas"]["type_config"]["format"] == "$%,.2f"
    assert col_config["promedio_movil_3m"]["type_config"]["format"] == "$%,.2f"
    assert col_config["ventas_mes"]["type_config"]["format"] == "$%,.2f"
    assert col_config["acumulado"]["type_config"]["format"] == "$%,.2f"
    assert col_config["registros"]["type_config"]["format"] == "%,.0f"


def test_format_numeric_display_dataframe_renders_visible_thousand_separators():
    df = pd.DataFrame({
        "mes": ["Ene 2024"],
        "ventas": [500145.74],
        "promedio_movil_3m": [427108.42],
        "registros": [27],
    })

    formatted_df = data_assistant._format_numeric_display_dataframe(df)

    assert formatted_df.loc[0, "mes"] == "Ene 2024"
    assert formatted_df.loc[0, "ventas"] == "$500,145.74"
    assert formatted_df.loc[0, "promedio_movil_3m"] == "$427,108.42"
    assert formatted_df.loc[0, "registros"] == "27"


def test_append_chat_message_caps_session_history(monkeypatch):
    monkeypatch.setattr(data_assistant.st, "session_state", {"nl2sql_messages": []}, raising=False)

    for idx in range(data_assistant.MAX_CHAT_MESSAGES + 5):
        data_assistant._append_chat_message({"role": "user", "content": f"q{idx}"})

    stored = data_assistant.st.session_state["nl2sql_messages"]
    assert len(stored) == data_assistant.MAX_CHAT_MESSAGES
    assert stored[0]["content"] == "q5"


def test_build_result_message_truncates_large_dataframe():
    result = data_assistant.NL2SQLResult(
        question="top clientes",
        sql="SELECT 1",
        dataframe=pd.DataFrame({"valor": range(data_assistant.MAX_SESSION_RESULT_ROWS + 25)}),
        row_count=data_assistant.MAX_SESSION_RESULT_ROWS + 25,
    )

    msg = data_assistant._build_result_message(result, "top clientes")

    assert msg["dataframe_truncated"] is True
    df = pd.read_json(StringIO(msg["dataframe_json"]), orient="split")
    assert len(df) == data_assistant.MAX_SESSION_RESULT_ROWS
