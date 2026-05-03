from io import StringIO

import pandas as pd

from main import data_assistant
from utils.auth import User, UserRole


def test_get_runtime_credentials_uses_server_side_secrets_for_non_superadmin(monkeypatch):
    user = User("ana", "ana@test.com", "Ana", UserRole.ANALYST, empresa_id="emp-1")

    monkeypatch.setattr(data_assistant, "get_current_user", lambda: user)
    monkeypatch.setattr(data_assistant.st, "session_state", {
        "nl2sql_neon_url": "postgresql://frontend-should-not-be-used",
        "nl2sql_api_key": "frontend-key-should-not-be-used",
        "nl2sql_model": "gpt-4o-mini",
    }, raising=False)
    monkeypatch.setenv("NEON_DATABASE_URL", "postgresql://server-safe-url")
    monkeypatch.setenv("OPENAI_API_KEY", "server-safe-key")

    neon_url, api_key, model = data_assistant._get_runtime_credentials()

    assert neon_url == "postgresql://server-safe-url"
    assert api_key == "server-safe-key"
    assert model == "gpt-4o-mini"


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
