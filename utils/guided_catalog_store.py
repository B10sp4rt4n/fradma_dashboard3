from __future__ import annotations

import json
import copy
from pathlib import Path
from typing import Any, Optional

try:
    import psycopg2
    from psycopg2.extras import Json
    PSYCOPG2_AVAILABLE = True
except ImportError:  # pragma: no cover
    PSYCOPG2_AVAILABLE = False

CATALOG_PATH = Path(__file__).resolve().parents[1] / "config" / "guided_query_catalog.json"


def load_catalog_from_json(path: Optional[str] = None) -> dict[str, Any]:
    """Carga el catálogo guiado desde JSON local."""
    p = Path(path) if path else CATALOG_PATH
    with p.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    validate_catalog(data)
    return data


def validate_catalog(catalog: dict[str, Any]) -> None:
    """Validación mínima de estructura para uso runtime."""
    if not isinstance(catalog, dict):
        raise ValueError("Catalogo inválido: raiz debe ser objeto JSON")
    domains = catalog.get("domains")
    if not isinstance(domains, list) or not domains:
        raise ValueError("Catalogo inválido: domains debe ser lista no vacia")

    total_cases = 0
    for domain in domains:
        if "id" not in domain or "cases" not in domain:
            raise ValueError("Catalogo inválido: cada dominio requiere id y cases")
        if not isinstance(domain["cases"], list):
            raise ValueError("Catalogo inválido: cases debe ser lista")
        total_cases += len(domain["cases"])

    if total_cases == 0:
        raise ValueError("Catalogo inválido: no hay casos definidos")


def catalog_stats(catalog: dict[str, Any]) -> dict[str, Any]:
    domains = catalog.get("domains", [])
    total_cases = sum(len(d.get("cases", [])) for d in domains)
    return {
        "domains": len(domains),
        "cases": total_cases,
        "by_domain": {d.get("id", "unknown"): len(d.get("cases", [])) for d in domains},
    }


def upsert_catalog_to_db(
    connection_string: str,
    catalog: dict[str, Any],
    *,
    source: str = "json",
) -> str:
    """Sincroniza catálogo a BD y activa la versión declarada en JSON."""
    if not PSYCOPG2_AVAILABLE:
        raise RuntimeError("psycopg2 no disponible")

    validate_catalog(catalog)
    version = str(catalog.get("version", "1.0.0"))
    description = catalog.get("description", "Catalogo guiado")

    with psycopg2.connect(connection_string) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO guided_catalog_versions (version, source, description, is_active)
                VALUES (%s, %s, %s, FALSE)
                ON CONFLICT (version)
                DO UPDATE SET source = EXCLUDED.source, description = EXCLUDED.description
                RETURNING id
                """,
                (version, source, description),
            )
            version_id = cur.fetchone()[0]

            cur.execute("DELETE FROM guided_catalog_domains WHERE version_id = %s", (version_id,))
            cur.execute("DELETE FROM guided_catalog_cases WHERE version_id = %s", (version_id,))

            for d_idx, domain in enumerate(catalog.get("domains", []), start=1):
                cur.execute(
                    """
                    INSERT INTO guided_catalog_domains (version_id, domain_key, label, enabled, sort_order)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        version_id,
                        domain.get("id"),
                        domain.get("label", domain.get("id")),
                        bool(domain.get("enabled", True)),
                        d_idx,
                    ),
                )

                for c_idx, case in enumerate(domain.get("cases", []), start=1):
                    cur.execute(
                        """
                        INSERT INTO guided_catalog_cases (
                            version_id, domain_key, case_key, label, description, sql_template_id,
                            default_chart, enabled, tables_json, filters_json, groupings_json, sort_order
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            version_id,
                            domain.get("id"),
                            case.get("id"),
                            case.get("label", case.get("id")),
                            case.get("description", ""),
                            case.get("sql_template_id", ""),
                            case.get("default_chart", "table"),
                            bool(case.get("enabled", True)),
                            Json(case.get("tables", [])),
                            Json(case.get("allowed_filters", [])),
                            Json(case.get("allowed_groupings", [])),
                            c_idx,
                        ),
                    )

            cur.execute("UPDATE guided_catalog_versions SET is_active = FALSE WHERE is_active = TRUE")
            cur.execute("UPDATE guided_catalog_versions SET is_active = TRUE WHERE id = %s", (version_id,))

    return version


def load_active_catalog_from_db(connection_string: str) -> dict[str, Any]:
    """Carga el catálogo activo desde BD y lo reconstruye en forma JSON."""
    if not PSYCOPG2_AVAILABLE:
        raise RuntimeError("psycopg2 no disponible")

    with psycopg2.connect(connection_string) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, version, description
                FROM guided_catalog_versions
                WHERE is_active = TRUE
                LIMIT 1
                """
            )
            row = cur.fetchone()
            if not row:
                raise RuntimeError("No hay version activa de catalogo guiado en BD")

            version_id, version, description = row

            cur.execute(
                """
                SELECT domain_key, label, enabled, sort_order
                FROM guided_catalog_domains
                WHERE version_id = %s
                ORDER BY sort_order
                """,
                (version_id,),
            )
            domains_rows = cur.fetchall()

            cur.execute(
                """
                SELECT domain_key, case_key, label, description, sql_template_id,
                       default_chart, enabled, tables_json, filters_json, groupings_json, sort_order
                FROM guided_catalog_cases
                WHERE version_id = %s
                ORDER BY domain_key, sort_order
                """,
                (version_id,),
            )
            cases_rows = cur.fetchall()

    cases_by_domain: dict[str, list[dict[str, Any]]] = {}
    for (
        domain_key,
        case_key,
        label,
        case_description,
        sql_template_id,
        default_chart,
        enabled,
        tables_json,
        filters_json,
        groupings_json,
        _sort_order,
    ) in cases_rows:
        cases_by_domain.setdefault(domain_key, []).append(
            {
                "id": case_key,
                "label": label,
                "description": case_description,
                "sql_template_id": sql_template_id,
                "tables": tables_json or [],
                "allowed_filters": filters_json or [],
                "allowed_groupings": groupings_json or [],
                "default_chart": default_chart,
                "enabled": bool(enabled),
            }
        )

    domains = []
    for domain_key, label, enabled, _sort_order in domains_rows:
        domains.append(
            {
                "id": domain_key,
                "label": label,
                "enabled": bool(enabled),
                "cases": cases_by_domain.get(domain_key, []),
            }
        )

    catalog = {
        "version": version,
        "mode": "guided-query-catalog",
        "description": description,
        "domains": domains,
    }
    validate_catalog(catalog)
    return catalog


def load_runtime_catalog(
    *,
    connection_string: Optional[str] = None,
    prefer_db: bool = False,
    empresa_id: Optional[str] = None,
    json_path: Optional[str] = None,
) -> dict[str, Any]:
    """Carga catálogo para runtime con fallback seguro a JSON local."""
    base_catalog: dict[str, Any]
    if prefer_db and connection_string:
        try:
            base_catalog = load_active_catalog_from_db(connection_string)
        except Exception:
            base_catalog = load_catalog_from_json(path=json_path)
    else:
        base_catalog = load_catalog_from_json(path=json_path)

    if connection_string and empresa_id:
        try:
            overrides = load_tenant_overrides(connection_string, empresa_id)
            if overrides:
                return apply_tenant_overrides(base_catalog, overrides)
        except Exception:
            pass

    return base_catalog


def load_tenant_overrides(connection_string: str, empresa_id: str) -> list[dict[str, Any]]:
    """Carga overrides de rollout para un tenant."""
    if not PSYCOPG2_AVAILABLE:
        return []

    with psycopg2.connect(connection_string) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT domain_key, case_key, enabled
                FROM guided_catalog_tenant_overrides
                WHERE empresa_id = %s::uuid
                ORDER BY updated_at DESC
                """,
                (empresa_id,),
            )
            rows = cur.fetchall()

    return [
        {
            "domain_key": str(domain_key),
            "case_key": str(case_key),
            "enabled": bool(enabled),
        }
        for domain_key, case_key, enabled in rows
    ]


def apply_tenant_overrides(catalog: dict[str, Any], overrides: list[dict[str, Any]]) -> dict[str, Any]:
    """Aplica overrides de tenant sobre un catálogo base."""
    updated_catalog = copy.deepcopy(catalog)

    domain_overrides: dict[str, bool] = {}
    case_overrides: dict[tuple[str, str], bool] = {}

    for override in overrides:
        domain_key = str(override.get("domain_key", "*") or "*")
        case_key = str(override.get("case_key", "*") or "*")
        enabled = bool(override.get("enabled", True))
        if case_key == "*":
            domain_overrides[domain_key] = enabled
        else:
            case_overrides[(domain_key, case_key)] = enabled

    for domain in updated_catalog.get("domains", []):
        domain_id = str(domain.get("id", ""))

        if "*" in domain_overrides:
            domain["enabled"] = bool(domain_overrides["*"])
        if domain_id in domain_overrides:
            domain["enabled"] = bool(domain_overrides[domain_id])

        for case in domain.get("cases", []):
            case_id = str(case.get("id", ""))
            if ("*", case_id) in case_overrides:
                case["enabled"] = bool(case_overrides[("*", case_id)])
            if (domain_id, case_id) in case_overrides:
                case["enabled"] = bool(case_overrides[(domain_id, case_id)])

    return updated_catalog


def upsert_tenant_override(
    connection_string: str,
    *,
    empresa_id: str,
    domain_key: str = "*",
    case_key: str = "*",
    enabled: bool,
) -> None:
    """Crea o actualiza un override de rollout por tenant."""
    if not PSYCOPG2_AVAILABLE:
        raise RuntimeError("psycopg2 no disponible")

    with psycopg2.connect(connection_string) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO guided_catalog_tenant_overrides (
                    empresa_id, domain_key, case_key, enabled, updated_at
                )
                VALUES (%s::uuid, %s, %s, %s, NOW())
                ON CONFLICT (empresa_id, domain_key, case_key)
                DO UPDATE SET enabled = EXCLUDED.enabled, updated_at = NOW()
                """,
                (empresa_id, domain_key, case_key, bool(enabled)),
            )


def list_tenant_overrides(connection_string: str, empresa_id: str) -> list[dict[str, Any]]:
    """Lista overrides de rollout para un tenant."""
    return load_tenant_overrides(connection_string, empresa_id)
