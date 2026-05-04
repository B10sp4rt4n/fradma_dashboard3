from utils.guided_catalog_store import load_catalog_from_json, apply_tenant_overrides


def test_apply_tenant_overrides_can_disable_domain():
    catalog = load_catalog_from_json("config/guided_query_catalog.json")
    updated = apply_tenant_overrides(
        catalog,
        [
            {"domain_key": "clientes", "case_key": "*", "enabled": False},
        ],
    )

    clientes = next(d for d in updated["domains"] if d["id"] == "clientes")
    assert clientes["enabled"] is False


def test_apply_tenant_overrides_can_disable_single_case():
    catalog = load_catalog_from_json("config/guided_query_catalog.json")
    updated = apply_tenant_overrides(
        catalog,
        [
            {"domain_key": "ventas", "case_key": "ventas_top_clientes", "enabled": False},
        ],
    )

    ventas = next(d for d in updated["domains"] if d["id"] == "ventas")
    top_clientes = next(c for c in ventas["cases"] if c["id"] == "ventas_top_clientes")
    resumen = next(c for c in ventas["cases"] if c["id"] == "ventas_resumen_ejecutivo")
    assert top_clientes["enabled"] is False
    assert resumen["enabled"] is True
