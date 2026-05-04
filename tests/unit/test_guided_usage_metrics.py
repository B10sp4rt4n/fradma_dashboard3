from utils.guided_usage_metrics import (
    record_session_guided_usage,
    get_session_guided_usage_summary,
    get_db_guided_usage_summary,
    get_db_guided_usage_timeseries,
)


def test_record_session_guided_usage_and_summary():
    state = {}

    record_session_guided_usage(state, domain_key="ventas", case_key="ventas_top_clientes")
    record_session_guided_usage(state, domain_key="ventas", case_key="ventas_top_clientes")
    record_session_guided_usage(state, domain_key="fiscal", case_key="fiscal_resumen_ingresos")

    summary = get_session_guided_usage_summary(state)

    assert summary["events"] == 3
    assert summary["top_cases"][0] == ("ventas_top_clientes", 2)
    assert summary["top_domains"][0] == ("ventas", 2)


def test_session_guided_usage_keeps_recent_200_events():
    state = {}
    for idx in range(250):
        record_session_guided_usage(state, domain_key="ventas", case_key=f"c{idx}")

    summary = get_session_guided_usage_summary(state)
    assert summary["events"] == 200


def test_get_db_guided_usage_summary_without_connection_returns_empty():
    summary = get_db_guided_usage_summary("", empresa_id=None, days=30)
    assert summary["events"] == 0
    assert summary["top_cases"] == []
    assert summary["top_domains"] == []


def test_get_db_guided_usage_timeseries_without_connection_returns_empty():
    series = get_db_guided_usage_timeseries("", empresa_id=None, days=30)
    assert series == []
