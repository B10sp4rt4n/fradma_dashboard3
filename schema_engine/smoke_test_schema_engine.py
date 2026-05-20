"""
smoke_test_schema_engine.py
Tests basicos del modulo schema_engine.

No requiere Streamlit, Neon, ni APIs externas.
Se ejecuta con: python schema_engine/smoke_test_schema_engine.py
"""

import sys
import os

# Asegurar que el directorio raiz del proyecto este en el path
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# =====================================================================
# HELPERS DE TEST
# =====================================================================

_PASSED = 0
_FAILED = 0
_ERRORS = []


def ok(msg: str) -> None:
    global _PASSED
    _PASSED += 1
    print(f"  [OK]  {msg}")


def fail(msg: str) -> None:
    global _FAILED
    _FAILED += 1
    _ERRORS.append(msg)
    print(f"  [FAIL] {msg}")


def section(title: str) -> None:
    print(f"\n--- {title} ---")


# =====================================================================
# TESTS
# =====================================================================

def test_schema_registry():
    section("schema_registry")
    from schema_engine.schema_registry import (
        get_schema, list_schemas, list_schemas_by_source,
        get_required_fields, get_recommended_fields,
    )

    schemas = list_schemas()
    if len(schemas) >= 8:
        ok(f"list_schemas retorna {len(schemas)} esquemas")
    else:
        fail(f"list_schemas retorna solo {len(schemas)} esquemas, esperaba >= 8")

    try:
        s = get_schema("ventas_comercial_v1")
        ok(f"get_schema('ventas_comercial_v1') retorna schema con nombre: {s.get('nombre')}")
    except Exception as e:
        fail(f"get_schema('ventas_comercial_v1') lanzo excepcion: {e}")

    try:
        get_schema("schema_inexistente")
        fail("get_schema con ID invalido deberia lanzar KeyError")
    except KeyError:
        ok("get_schema con ID invalido lanza KeyError correctamente")

    ventas = list_schemas_by_source("ventas_excel")
    if ventas:
        ok(f"list_schemas_by_source('ventas_excel') retorna {len(ventas)} esquemas")
    else:
        fail("list_schemas_by_source('ventas_excel') retorna lista vacia")

    reqs = get_required_fields("cxc_aging_v1")
    if reqs:
        ok(f"get_required_fields('cxc_aging_v1') retorna {len(reqs)} campos obligatorios")
    else:
        fail("get_required_fields('cxc_aging_v1') retorna lista vacia")


def test_column_mapper():
    section("column_mapper")
    from schema_engine.column_mapper import (
        normalize_column_name, get_canonical_field, map_columns,
        detect_unmapped_columns, get_detected_canonical_fields,
    )

    tests = [
        ("Fecha de Venta", "fecha"),
        ("MONTO TOTAL", "monto"),
        ("Nombre del Cliente", "cliente"),
        ("Vendedor", "vendedor"),
        ("Linea", "linea_de_negocio"),
        ("Saldo", "saldo_adeudado"),
    ]
    for raw, expected in tests:
        canonical = get_canonical_field(raw)
        if canonical == expected:
            ok(f"get_canonical_field('{raw}') -> '{canonical}'")
        else:
            fail(f"get_canonical_field('{raw}') retorno '{canonical}', esperaba '{expected}'")

    cols = ["Fecha", "Monto", "Cliente", "Vendedor", "ColumnaExtraDesconocida"]
    mapping = map_columns(cols)
    if len(mapping) >= 4:
        ok(f"map_columns mapeó {len(mapping)} de {len(cols)} columnas")
    else:
        fail(f"map_columns mapeó solo {len(mapping)} columnas")

    unmapped = detect_unmapped_columns(cols)
    if "ColumnaExtraDesconocida".lower().replace(" ", "_") in [u.lower().replace(" ", "_") for u in unmapped] or unmapped:
        ok(f"detect_unmapped_columns detectó {len(unmapped)} columna(s) no mapeada(s)")
    else:
        fail("detect_unmapped_columns no detectó la columna desconocida")


def test_schema_validator():
    section("schema_validator")
    try:
        import pandas as pd
    except ImportError:
        fail("pandas no disponible — omitiendo test_schema_validator")
        return

    from schema_engine.schema_validator import validate_dataframe_against_schema

    df_ok = pd.DataFrame({
        "fecha":   ["2026-01-15"],
        "monto":   [12500.0],
        "cliente": ["Empresa ABC"],
    })
    result = validate_dataframe_against_schema(df_ok, "ventas_minimo_v1")
    if result["valido"]:
        ok(f"validate con ventas_minimo_v1 valido=True, score={result['score_contexto']}")
    else:
        fail(f"validate con df valido retorno valido=False: {result.get('observaciones')}")

    df_bad = pd.DataFrame({"descripcion": ["algo"]})
    result2 = validate_dataframe_against_schema(df_bad, "ventas_minimo_v1")
    if not result2["valido"]:
        ok("validate con df sin campos obligatorios retorna valido=False correctamente")
    else:
        fail("validate con df sin campos obligatorios retorna valido=True incorrectamente")


def test_context_score():
    section("context_score")
    from schema_engine.context_score import calculate_context_score, score_label

    # Campos completos
    detected_full = {"fecha", "monto", "cliente", "vendedor", "linea_de_negocio", "estatus"}
    result = calculate_context_score(detected_full)
    score = result["score"]
    label = score_label(score)
    ok(f"context_score (campos completos) = {score} ({label})")

    # Campos minimos
    detected_min = {"monto"}
    result2 = calculate_context_score(detected_min)
    score2 = result2["score"]
    label2 = score_label(score2)
    ok(f"context_score (solo monto) = {score2} ({label2})")

    if score > score2:
        ok("Score con mas campos es mayor que con menos campos")
    else:
        fail(f"Score con mas campos ({score}) deberia ser mayor que con menos ({score2})")


def test_module_requirements():
    section("module_requirements")
    from schema_engine.module_requirements import get_activable_modules

    sources   = {"ventas_excel"}
    fields    = {"fecha", "monto", "cliente", "vendedor", "linea_de_negocio", "producto", "region"}
    df_cols   = ["fecha", "monto", "cliente", "vendedor", "linea_de_negocio", "producto", "region"]

    result = get_activable_modules(sources, fields, df_cols)
    activables = result["modulos_activables"]
    parciales  = result["modulos_parciales"]
    ok(f"modulos_activables: {activables}")
    ok(f"modulos_parciales: {parciales}")

    if activables or parciales:
        ok("Se detectaron modulos activables o parciales correctamente")
    else:
        fail("No se detectaron modulos — verificar logica de get_activable_modules")


def test_connector_registry():
    section("connector_registry")
    from schema_engine.connector_registry import (
        list_connectors, get_connector_metadata,
        list_connectors_by_capability, list_active_connectors,
    )

    connectors = list_connectors()
    if len(connectors) >= 6:
        ok(f"list_connectors retorna {len(connectors)} conectores")
    else:
        fail(f"list_connectors retorna solo {len(connectors)}, esperaba >= 6")

    meta = get_connector_metadata("neon")
    if meta.get("status") == "active":
        ok("get_connector_metadata('neon') retorna status='active'")
    else:
        fail(f"get_connector_metadata('neon') status inesperado: {meta.get('status')}")

    cfdi_connectors = list_connectors_by_capability("cfdi")
    if cfdi_connectors:
        ok(f"list_connectors_by_capability('cfdi') retorna {len(cfdi_connectors)} conector(es)")
    else:
        fail("list_connectors_by_capability('cfdi') retorna lista vacia")

    active = list_active_connectors()
    if "neon" in active:
        ok(f"list_active_connectors incluye 'neon': {active}")
    else:
        fail(f"list_active_connectors no incluye 'neon': {active}")


def test_source_contracts():
    section("source_contracts")
    from schema_engine.source_contracts import (
        get_contracts_for_source, source_supports_contract, get_sources_for_contract,
    )

    contracts = get_contracts_for_source("ventas_excel")
    if "canonical_sales_v1" in contracts:
        ok(f"get_contracts_for_source('ventas_excel') incluye canonical_sales_v1")
    else:
        fail(f"Contratos de ventas_excel no incluyen canonical_sales_v1: {contracts}")

    if source_supports_contract("cxc_excel", "canonical_cxc_v1"):
        ok("source_supports_contract('cxc_excel', 'canonical_cxc_v1') = True")
    else:
        fail("source_supports_contract('cxc_excel', 'canonical_cxc_v1') deberia ser True")

    sources = get_sources_for_contract("canonical_sales_v1")
    if "ventas_excel" in sources:
        ok(f"get_sources_for_contract('canonical_sales_v1') incluye 'ventas_excel'")
    else:
        fail(f"Fuentes para canonical_sales_v1 no incluyen ventas_excel: {sources}")


def test_schema_generator():
    section("schema_generator")
    from schema_engine.schema_generator import (
        get_template_columns, generate_csv_template,
    )

    cols = get_template_columns("ventas_comercial_v1")
    if "fecha" in cols and "monto" in cols:
        ok(f"get_template_columns('ventas_comercial_v1') incluye fecha y monto: {cols[:5]}...")
    else:
        fail(f"get_template_columns('ventas_comercial_v1') no incluye campos basicos: {cols}")

    csv_str = generate_csv_template("ventas_minimo_v1")
    if isinstance(csv_str, str) and "fecha" in csv_str and "monto" in csv_str:
        lines = csv_str.strip().split("\n")
        ok(f"generate_csv_template('ventas_minimo_v1') genera CSV con {len(lines)} lineas")
    else:
        fail(f"generate_csv_template devolvio tipo inesperado o sin encabezados: {type(csv_str)}")


def test_translators():
    section("connections.translators")
    from connections.translators.canonical_sales_translator import translate_to_canonical_sales
    from connections.translators.canonical_cxc_translator   import translate_to_canonical_cxc
    from connections.translators.canonical_customer_translator import translate_to_canonical_customer
    from connections.translators.canonical_product_translator  import translate_to_canonical_product

    sales = translate_to_canonical_sales(
        {"fecha": "2026-01-15", "monto": 12500, "cliente": "ABC"},
        source_id="ventas_excel",
    )
    if sales["fuente_origen"] == "ventas_excel" and "extracted_at" in sales:
        ok("translate_to_canonical_sales agrega fuente_origen y extracted_at")
    else:
        fail(f"translate_to_canonical_sales falta campos de auditoria: {sales}")

    cxc = translate_to_canonical_cxc(
        {"cliente": "ABC", "saldo_adeudado": 8500},
        source_id="cxc_excel",
    )
    if cxc["fuente_origen"] == "cxc_excel":
        ok("translate_to_canonical_cxc funciona correctamente")
    else:
        fail("translate_to_canonical_cxc sin fuente_origen")

    customer = translate_to_canonical_customer(
        {"receptor_nombre": "Empresa ABC", "receptor_rfc": "EAB860101AAA"},
        source_id="cfdi_xml",
    )
    if customer["cliente"] == "Empresa ABC" and customer["rfc"] == "EAB860101AAA":
        ok("translate_to_canonical_customer mapea receptor_nombre y receptor_rfc")
    else:
        fail(f"translate_to_canonical_customer mapeo incorrecto: {customer}")

    product = translate_to_canonical_product(
        {"descripcion": "EDR-Pro", "categoria": "Ciberseguridad", "precio": 12500},
        source_id="sae",
    )
    if product["producto"] == "EDR-Pro" and product["linea_de_negocio"] == "Ciberseguridad":
        ok("translate_to_canonical_product mapea descripcion y categoria")
    else:
        fail(f"translate_to_canonical_product mapeo incorrecto: {product}")


# =====================================================================
# RUNNER
# =====================================================================

def main():
    print("=" * 60)
    print("CIMA Schema Engine — Smoke Test")
    print("=" * 60)

    test_schema_registry()
    test_column_mapper()
    test_schema_validator()
    test_context_score()
    test_module_requirements()
    test_connector_registry()
    test_source_contracts()
    test_schema_generator()
    test_translators()

    print("\n" + "=" * 60)
    print(f"RESULTADO: {_PASSED} OK  /  {_FAILED} FAIL")
    if _ERRORS:
        print("\nFALLAS:")
        for e in _ERRORS:
            print(f"  - {e}")
    print("=" * 60)

    sys.exit(0 if _FAILED == 0 else 1)


if __name__ == "__main__":
    main()
