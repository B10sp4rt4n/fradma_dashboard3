from __future__ import annotations

from collections import Counter
from typing import Any, Optional

try:
    import psycopg2
    PSYCOPG2_AVAILABLE = True
except ImportError:  # pragma: no cover
    PSYCOPG2_AVAILABLE = False


def record_session_guided_usage(session_state: dict[str, Any], *, domain_key: str, case_key: str) -> None:
    """Registra uso de caso guiado en session_state para analytics local."""
    events = session_state.setdefault("guided_usage_events", [])
    events.append({"domain_key": domain_key, "case_key": case_key})
    session_state["guided_usage_events"] = events[-200:]


def get_session_guided_usage_summary(session_state: dict[str, Any]) -> dict[str, Any]:
    """Resume el uso por dominio y caso para renderizar en UI."""
    events = session_state.get("guided_usage_events", [])
    case_counter: Counter[str] = Counter()
    domain_counter: Counter[str] = Counter()

    for event in events:
        case_counter[str(event.get("case_key", ""))] += 1
        domain_counter[str(event.get("domain_key", ""))] += 1

    return {
        "events": len(events),
        "top_cases": case_counter.most_common(5),
        "top_domains": domain_counter.most_common(5),
    }


def record_db_guided_usage(
    connection_string: str,
    *,
    domain_key: str,
    case_key: str,
    success: bool,
    execution_time_sec: Optional[float] = None,
    row_count: Optional[int] = None,
    empresa_id: Optional[str] = None,
    user_email: Optional[str] = None,
    source: str = "streamlit",
) -> None:
    """Persiste evento de uso de caso guiado en BD (best effort)."""
    if not PSYCOPG2_AVAILABLE:
        return
    if not connection_string:
        return

    with psycopg2.connect(connection_string) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO guided_case_usage_events (
                    empresa_id, user_email, domain_key, case_key, success,
                    execution_time_sec, row_count, source
                )
                VALUES (
                    NULLIF(%s, '')::uuid, %s, %s, %s, %s, %s, %s, %s
                )
                """,
                (
                    empresa_id or "",
                    (user_email or "")[:255] or None,
                    domain_key,
                    case_key,
                    bool(success),
                    float(execution_time_sec) if execution_time_sec is not None else None,
                    int(row_count) if row_count is not None else None,
                    source,
                ),
            )


def get_db_guided_usage_summary(
    connection_string: str,
    *,
    empresa_id: Optional[str] = None,
    days: int = 30,
) -> dict[str, Any]:
    """Obtiene métricas agregadas de adopción guiada desde BD."""
    if not PSYCOPG2_AVAILABLE or not connection_string:
        return {
            "events": 0,
            "success_rate": 0.0,
            "avg_execution_time": 0.0,
            "top_cases": [],
            "top_domains": [],
        }

    where_parts = ["created_at >= NOW() - (%s || ' days')::interval"]
    params: list[Any] = [int(max(days, 1))]
    if empresa_id:
        where_parts.append("empresa_id = %s::uuid")
        params.append(empresa_id)
    where_sql = " AND ".join(where_parts)

    with psycopg2.connect(connection_string) as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT
                    COUNT(*) AS events,
                    COALESCE(AVG(CASE WHEN success THEN 1.0 ELSE 0.0 END), 0.0) AS success_rate,
                    COALESCE(AVG(execution_time_sec), 0.0) AS avg_execution_time
                FROM guided_case_usage_events
                WHERE {where_sql}
                """,
                tuple(params),
            )
            events, success_rate, avg_execution_time = cur.fetchone()

            cur.execute(
                f"""
                SELECT case_key, COUNT(*) AS uses
                FROM guided_case_usage_events
                WHERE {where_sql}
                GROUP BY case_key
                ORDER BY uses DESC
                LIMIT 5
                """,
                tuple(params),
            )
            top_cases = [(str(case_key), int(uses)) for case_key, uses in cur.fetchall()]

            cur.execute(
                f"""
                SELECT domain_key, COUNT(*) AS uses
                FROM guided_case_usage_events
                WHERE {where_sql}
                GROUP BY domain_key
                ORDER BY uses DESC
                LIMIT 5
                """,
                tuple(params),
            )
            top_domains = [(str(domain_key), int(uses)) for domain_key, uses in cur.fetchall()]

    return {
        "events": int(events or 0),
        "success_rate": float(success_rate or 0.0),
        "avg_execution_time": float(avg_execution_time or 0.0),
        "top_cases": top_cases,
        "top_domains": top_domains,
    }


def get_db_guided_usage_timeseries(
    connection_string: str,
    *,
    empresa_id: Optional[str] = None,
    days: int = 30,
) -> list[dict[str, Any]]:
    """Obtiene serie diaria de adopción guiada para dashboard."""
    if not PSYCOPG2_AVAILABLE or not connection_string:
        return []

    where_parts = ["created_at >= NOW() - (%s || ' days')::interval"]
    params: list[Any] = [int(max(days, 1))]
    if empresa_id:
        where_parts.append("empresa_id = %s::uuid")
        params.append(empresa_id)
    where_sql = " AND ".join(where_parts)

    with psycopg2.connect(connection_string) as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT
                    DATE_TRUNC('day', created_at)::date AS day,
                    COUNT(*) AS events,
                    COALESCE(AVG(CASE WHEN success THEN 1.0 ELSE 0.0 END), 0.0) AS success_rate,
                    COALESCE(AVG(execution_time_sec), 0.0) AS avg_execution_time
                FROM guided_case_usage_events
                WHERE {where_sql}
                GROUP BY day
                ORDER BY day ASC
                """,
                tuple(params),
            )
            rows = cur.fetchall()

    return [
        {
            "day": str(day),
            "events": int(events or 0),
            "success_rate": float(success_rate or 0.0),
            "avg_execution_time": float(avg_execution_time or 0.0),
        }
        for day, events, success_rate, avg_execution_time in rows
    ]
