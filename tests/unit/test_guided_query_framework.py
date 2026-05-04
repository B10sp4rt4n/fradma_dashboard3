from utils.guided_catalog_store import load_catalog_from_json
from utils.guided_query_framework import (
    GuidedQueryFramework,
    TEMPLATE_REGISTRY,
    VENTAS_TEMPLATE_REGISTRY,
    PRODUCTOS_TEMPLATE_REGISTRY,
    CLIENTES_TEMPLATE_REGISTRY,
    COBRANZA_TEMPLATE_REGISTRY,
    FISCAL_TEMPLATE_REGISTRY,
)


def test_guided_framework_builds_top_clients_query_with_limit_clamp():
    catalog = load_catalog_from_json("config/guided_query_catalog.json")
    framework = GuidedQueryFramework(catalog)

    sql, chart, case = framework.build_query(
        "ventas_top_clientes",
        {
            "period_mode": "ultimos_12_meses",
            "top_n": 500,
            "metodo_pago": "PUE",
        },
    )

    assert "FROM cfdi_ventas v" in sql
    assert "ORDER BY ventas DESC" in sql
    assert "LIMIT 100" in sql
    assert chart == "hbar"
    assert case["sql_template_id"] == "tpl_ventas_top_clientes"


def test_guided_framework_builds_custom_period_query():
    catalog = load_catalog_from_json("config/guided_query_catalog.json")
    framework = GuidedQueryFramework(catalog)

    sql, _chart, _case = framework.build_query(
        "ventas_resumen_ejecutivo",
        {
            "period_mode": "rango_personalizado",
            "start_date": "2025-01-01",
            "end_date": "2025-03-31",
            "tipo_comprobante": "I",
        },
    )

    assert "v.fecha_emision >= '2025-01-01'" in sql
    assert "v.fecha_emision < '2025-04-01'" in sql
    assert "v.tipo_comprobante = 'I'" in sql


def test_guided_framework_lists_enabled_domains_and_cases():
    catalog = load_catalog_from_json("config/guided_query_catalog.json")
    framework = GuidedQueryFramework(catalog)

    domains = framework.list_enabled_domains()
    ventas_cases = framework.list_enabled_cases("ventas")

    assert len(domains) == 5
    assert len(ventas_cases) == 5


def test_guided_framework_rejects_unknown_case():
    catalog = load_catalog_from_json("config/guided_query_catalog.json")
    framework = GuidedQueryFramework(catalog)

    try:
        framework.build_query("caso_inexistente", {"period_mode": "todo"})
        assert False, "Se esperaba ValueError para caso inexistente"
    except ValueError as exc:
        assert "Caso no encontrado" in str(exc)


def test_template_registry_is_split_by_domain_and_merged():
    split_total = (
        len(VENTAS_TEMPLATE_REGISTRY)
        + len(PRODUCTOS_TEMPLATE_REGISTRY)
        + len(CLIENTES_TEMPLATE_REGISTRY)
        + len(COBRANZA_TEMPLATE_REGISTRY)
        + len(FISCAL_TEMPLATE_REGISTRY)
    )
    assert split_total == len(TEMPLATE_REGISTRY)
    assert len(TEMPLATE_REGISTRY) == 20


def test_guided_framework_builds_sql_for_all_catalog_cases():
    catalog = load_catalog_from_json("config/guided_query_catalog.json")
    framework = GuidedQueryFramework(catalog)

    base_params = {
        "period_mode": "rango_personalizado",
        "start_date": "2025-01-01",
        "end_date": "2025-12-31",
        "top_n": 10,
        "metodo_pago": "PUE",
        "tipo_comprobante": "I",
        "cliente": "",
        "producto": "",
        "grouping": "mensual",
    }

    built_cases = []
    for domain in catalog["domains"]:
        for case in domain["cases"]:
            sql, chart, case_meta = framework.build_query(case["id"], dict(base_params))
            assert isinstance(sql, str) and sql.strip()
            assert sql.lstrip().upper().startswith(("SELECT", "WITH"))
            assert chart
            assert case_meta["id"] == case["id"]
            built_cases.append(case["id"])

    assert len(built_cases) == 20
