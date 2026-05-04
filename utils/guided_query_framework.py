from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Callable, Optional
import time

import pandas as pd


TemplateBuilder = Callable[[dict[str, Any]], str]


@dataclass
class GuidedExecutionResult:
    case_id: str
    case_label: str
    sql: str
    dataframe: pd.DataFrame
    row_count: int
    chart: str
    summary: str
    execution_time: float


def _safe_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except Exception:
        return default
    return max(minimum, min(maximum, parsed))


def _safe_text(value: Any, *, max_len: int = 120) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    return text[:max_len]


def _sql_quote(value: str) -> str:
    return value.replace("'", "''")


def _normalize_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()
    text = str(value).strip()
    return datetime.strptime(text, "%Y-%m-%d").date()


def _compute_period_bounds(params: dict[str, Any]) -> tuple[Optional[date], Optional[date]]:
    mode = str(params.get("period_mode", "ultimos_12_meses")).lower()
    today = date.today()

    if mode == "todo":
        return None, None

    if mode == "este_ano":
        return date(today.year, 1, 1), today

    if mode == "ultimos_12_meses":
        return today - timedelta(days=365), today

    if mode == "ultimos_6_meses":
        return today - timedelta(days=180), today

    if mode == "rango_personalizado":
        start_date = _normalize_date(params.get("start_date"))
        end_date = _normalize_date(params.get("end_date"))
        if start_date > end_date:
            raise ValueError("start_date no puede ser mayor que end_date")
        return start_date, end_date

    raise ValueError(f"period_mode no soportado: {mode}")


def _build_period_condition(params: dict[str, Any], *, field: str = "v.fecha_emision") -> str:
    start_date, end_date = _compute_period_bounds(params)
    clauses: list[str] = []

    if start_date:
        clauses.append(f"{field} >= '{start_date.isoformat()}'")
    if end_date:
        end_plus_one = end_date + timedelta(days=1)
        clauses.append(f"{field} < '{end_plus_one.isoformat()}'")

    return " AND ".join(clauses)


def _append_common_sales_filters(clauses: list[str], params: dict[str, Any], *, alias: str = "v") -> None:
    period_clause = _build_period_condition(params, field=f"{alias}.fecha_emision")
    if period_clause:
        clauses.append(period_clause)

    tipo = _safe_text(params.get("tipo_comprobante"), max_len=5).upper()
    if tipo and tipo != "TODOS":
        clauses.append(f"{alias}.tipo_comprobante = '{_sql_quote(tipo)}'")

    metodo = _safe_text(params.get("metodo_pago"), max_len=10).upper()
    if metodo and metodo != "TODOS":
        clauses.append(f"{alias}.metodo_pago = '{_sql_quote(metodo)}'")

    cliente = _safe_text(params.get("cliente"), max_len=80)
    if cliente:
        clauses.append(f"{alias}.receptor_nombre ILIKE '%{_sql_quote(cliente)}%'")


def _where_clause(clauses: list[str]) -> str:
    if not clauses:
        return ""
    return "WHERE " + " AND ".join(clauses)


def _top_n(params: dict[str, Any]) -> int:
    return _safe_int(params.get("top_n", 10), default=10, minimum=1, maximum=100)


def _grouping_expression(params: dict[str, Any], *, field: str = "v.fecha_emision") -> str:
    grouping = str(params.get("grouping", "mensual")).lower()
    if grouping == "mensual":
        return f"DATE_TRUNC('month', {field})"
    if grouping == "trimestral":
        return f"DATE_TRUNC('quarter', {field})"
    if grouping == "anual":
        return f"DATE_TRUNC('year', {field})"
    return "NULL"


def _tpl_ventas_resumen_ejecutivo(params: dict[str, Any]) -> str:
    clauses: list[str] = []
    _append_common_sales_filters(clauses, params, alias="v")
    where_sql = _where_clause(clauses)
    return (
        "SELECT "
        "COUNT(*) AS total_facturas, "
        "ROUND(SUM(COALESCE(v.total, 0))::numeric, 2) AS ventas, "
        "ROUND(AVG(COALESCE(v.total, 0))::numeric, 2) AS promedio, "
        "ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY COALESCE(v.total, 0))::numeric, 2) AS mediana, "
        "ROUND(STDDEV(COALESCE(v.total, 0))::numeric, 2) AS desviacion "
        "FROM cfdi_ventas v "
        f"{where_sql};"
    )


def _tpl_ventas_por_mes(params: dict[str, Any]) -> str:
    clauses: list[str] = []
    _append_common_sales_filters(clauses, params, alias="v")
    where_sql = _where_clause(clauses)
    bucket = _grouping_expression(params)
    if bucket == "NULL":
        bucket = "DATE_TRUNC('month', v.fecha_emision)"

    return (
        "SELECT "
        f"{bucket} AS mes, "
        "ROUND(SUM(COALESCE(v.total, 0))::numeric, 2) AS ventas, "
        "ROUND(AVG(SUM(COALESCE(v.total, 0))) OVER (ORDER BY "
        f"{bucket} ROWS BETWEEN 2 PRECEDING AND CURRENT ROW)::numeric, 2) AS promedio_movil_3m "
        "FROM cfdi_ventas v "
        f"{where_sql} "
        f"GROUP BY {bucket} "
        "ORDER BY mes;"
    )


def _tpl_ventas_top_clientes(params: dict[str, Any]) -> str:
    clauses: list[str] = []
    _append_common_sales_filters(clauses, params, alias="v")
    where_sql = _where_clause(clauses)
    top_n = _top_n(params)

    return (
        "SELECT "
        "v.receptor_nombre AS cliente, "
        "COUNT(*) AS facturas, "
        "ROUND(SUM(COALESCE(v.total, 0))::numeric, 2) AS ventas "
        "FROM cfdi_ventas v "
        f"{where_sql} "
        "GROUP BY v.receptor_nombre "
        "ORDER BY ventas DESC "
        f"LIMIT {top_n};"
    )


def _tpl_ventas_top_productos(params: dict[str, Any]) -> str:
    clauses: list[str] = []
    _append_common_sales_filters(clauses, params, alias="v")

    producto = _safe_text(params.get("producto"), max_len=100)
    if producto:
        clauses.append(f"c.descripcion ILIKE '%{_sql_quote(producto)}%'")

    where_sql = _where_clause(clauses)
    top_n = _top_n(params)
    return (
        "SELECT "
        "c.descripcion AS producto, "
        "ROUND(SUM(COALESCE(c.importe, COALESCE(c.cantidad, 0) * COALESCE(c.valor_unitario, 0)))::numeric, 2) AS ventas "
        "FROM cfdi_conceptos c "
        "JOIN cfdi_ventas v ON v.id = c.cfdi_venta_id "
        f"{where_sql} "
        "GROUP BY c.descripcion "
        "ORDER BY ventas DESC "
        f"LIMIT {top_n};"
    )


def _tpl_ventas_concentracion_clientes(params: dict[str, Any]) -> str:
    clauses: list[str] = []
    _append_common_sales_filters(clauses, params, alias="v")
    where_sql = _where_clause(clauses)
    top_n = _top_n(params)

    return (
        "WITH por_cliente AS ("
        "SELECT v.receptor_nombre AS cliente, SUM(COALESCE(v.total, 0)) AS ventas "
        "FROM cfdi_ventas v "
        f"{where_sql} "
        "GROUP BY v.receptor_nombre"
        "), ranked AS ("
        "SELECT cliente, ventas, "
        "ROW_NUMBER() OVER (ORDER BY ventas DESC) AS rn, "
        "SUM(ventas) OVER () AS total_general, "
        "SUM(ventas) OVER (ORDER BY ventas DESC) AS acumulado "
        "FROM por_cliente"
        ") "
        "SELECT cliente, "
        "ROUND(ventas::numeric, 2) AS ventas, "
        "ROUND((ventas / NULLIF(total_general, 0) * 100)::numeric, 2) AS pct_cliente, "
        "ROUND((acumulado / NULLIF(total_general, 0) * 100)::numeric, 2) AS pct_acumulado "
        "FROM ranked "
        f"WHERE rn <= {top_n} "
        "ORDER BY rn;"
    )


def _tpl_productos_precios_estadisticas(params: dict[str, Any]) -> str:
    clauses: list[str] = []
    _append_common_sales_filters(clauses, params, alias="v")
    producto = _safe_text(params.get("producto"), max_len=100)
    if producto:
        clauses.append(f"c.descripcion ILIKE '%{_sql_quote(producto)}%'")
    where_sql = _where_clause(clauses)

    return (
        "SELECT "
        "COUNT(*) AS registros, "
        "ROUND(AVG(COALESCE(c.valor_unitario, 0))::numeric, 2) AS promedio, "
        "ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY COALESCE(c.valor_unitario, 0))::numeric, 2) AS mediana, "
        "ROUND(MIN(COALESCE(c.valor_unitario, 0))::numeric, 2) AS minimo, "
        "ROUND(MAX(COALESCE(c.valor_unitario, 0))::numeric, 2) AS maximo "
        "FROM cfdi_conceptos c "
        "JOIN cfdi_ventas v ON v.id = c.cfdi_venta_id "
        f"{where_sql};"
    )


def _tpl_productos_top_facturacion(params: dict[str, Any]) -> str:
    return _tpl_ventas_top_productos(params)


def _tpl_productos_menor_venta(params: dict[str, Any]) -> str:
    sql = _tpl_ventas_top_productos(params)
    return sql.replace("ORDER BY ventas DESC", "ORDER BY ventas ASC")


def _tpl_productos_participacion_mix(params: dict[str, Any]) -> str:
    clauses: list[str] = []
    _append_common_sales_filters(clauses, params, alias="v")
    where_sql = _where_clause(clauses)
    top_n = _top_n(params)

    return (
        "WITH por_producto AS ("
        "SELECT c.descripcion AS producto, "
        "SUM(COALESCE(c.importe, COALESCE(c.cantidad, 0) * COALESCE(c.valor_unitario, 0))) AS ventas "
        "FROM cfdi_conceptos c "
        "JOIN cfdi_ventas v ON v.id = c.cfdi_venta_id "
        f"{where_sql} "
        "GROUP BY c.descripcion"
        "), ranked AS ("
        "SELECT producto, ventas, "
        "ROW_NUMBER() OVER (ORDER BY ventas DESC) AS rn, "
        "SUM(ventas) OVER () AS total_general "
        "FROM por_producto"
        ") "
        "SELECT producto, ROUND(ventas::numeric, 2) AS ventas, "
        "ROUND((ventas / NULLIF(total_general, 0) * 100)::numeric, 2) AS porcentaje "
        "FROM ranked "
        f"WHERE rn <= {top_n} "
        "ORDER BY ventas DESC;"
    )


def _tpl_clientes_ranking(params: dict[str, Any]) -> str:
    return _tpl_ventas_top_clientes(params)


def _tpl_clientes_recurrentes(params: dict[str, Any]) -> str:
    clauses: list[str] = []
    _append_common_sales_filters(clauses, params, alias="v")
    where_sql = _where_clause(clauses)
    top_n = _top_n(params)

    return (
        "SELECT "
        "v.receptor_nombre AS cliente, "
        "COUNT(*) AS facturas, "
        "ROUND(SUM(COALESCE(v.total, 0))::numeric, 2) AS ventas "
        "FROM cfdi_ventas v "
        f"{where_sql} "
        "GROUP BY v.receptor_nombre "
        "HAVING COUNT(*) >= 2 "
        "ORDER BY facturas DESC, ventas DESC "
        f"LIMIT {top_n};"
    )


def _tpl_clientes_nuevos_periodo(params: dict[str, Any]) -> str:
    start_date, end_date = _compute_period_bounds(params)
    if not start_date or not end_date:
        end_date = date.today()
        start_date = end_date - timedelta(days=365)

    return (
        "WITH primera_compra AS ("
        "SELECT receptor_rfc, MIN(fecha_emision) AS primera_fecha "
        "FROM cfdi_ventas "
        "GROUP BY receptor_rfc"
        ") "
        "SELECT DATE_TRUNC('month', primera_fecha) AS mes, "
        "COUNT(*) AS clientes_nuevos "
        "FROM primera_compra "
        f"WHERE primera_fecha >= '{start_date.isoformat()}' "
        f"AND primera_fecha < '{(end_date + timedelta(days=1)).isoformat()}' "
        "GROUP BY DATE_TRUNC('month', primera_fecha) "
        "ORDER BY mes;"
    )


def _tpl_clientes_crecimiento(params: dict[str, Any]) -> str:
    start_date, end_date = _compute_period_bounds(params)
    if not start_date or not end_date:
        end_date = date.today()
        start_date = end_date - timedelta(days=365)

    days = (end_date - start_date).days
    midpoint = start_date + timedelta(days=max(days // 2, 1))
    top_n = _top_n(params)

    return (
        "SELECT "
        "v.receptor_nombre AS cliente, "
        "ROUND(SUM(CASE WHEN v.fecha_emision < '{mid}' THEN COALESCE(v.total, 0) ELSE 0 END)::numeric, 2) AS ventas_periodo_1, "
        "ROUND(SUM(CASE WHEN v.fecha_emision >= '{mid}' THEN COALESCE(v.total, 0) ELSE 0 END)::numeric, 2) AS ventas_periodo_2, "
        "ROUND((SUM(CASE WHEN v.fecha_emision >= '{mid}' THEN COALESCE(v.total, 0) ELSE 0 END) - "
        "SUM(CASE WHEN v.fecha_emision < '{mid}' THEN COALESCE(v.total, 0) ELSE 0 END))::numeric, 2) AS delta "
        "FROM cfdi_ventas v "
        "WHERE v.fecha_emision >= '{start}' "
        "AND v.fecha_emision < '{end}' "
        "GROUP BY v.receptor_nombre "
        "ORDER BY delta DESC "
        "LIMIT {limit};"
    ).format(
        mid=midpoint.isoformat(),
        start=start_date.isoformat(),
        end=(end_date + timedelta(days=1)).isoformat(),
        limit=top_n,
    )


def _tpl_cobranza_pendientes(params: dict[str, Any]) -> str:
    clauses: list[str] = ["v.metodo_pago = 'PPD'"]
    _append_common_sales_filters(clauses, params, alias="v")
    where_sql = _where_clause(clauses)
    top_n = _top_n(params)

    return (
        "SELECT "
        "v.folio, "
        "v.receptor_nombre AS cliente, "
        "v.fecha_emision, "
        "ROUND(COALESCE(v.total, 0)::numeric, 2) AS saldo_estimado "
        "FROM cfdi_ventas v "
        f"{where_sql} "
        "ORDER BY v.fecha_emision ASC "
        f"LIMIT {top_n};"
    )


def _tpl_cobranza_pagadas(params: dict[str, Any]) -> str:
    clauses: list[str] = ["v.metodo_pago = 'PUE'"]
    _append_common_sales_filters(clauses, params, alias="v")
    where_sql = _where_clause(clauses)
    top_n = _top_n(params)

    return (
        "SELECT "
        "v.folio, "
        "v.receptor_nombre AS cliente, "
        "v.fecha_emision, "
        "ROUND(COALESCE(v.total, 0)::numeric, 2) AS monto "
        "FROM cfdi_ventas v "
        f"{where_sql} "
        "ORDER BY v.fecha_emision DESC "
        f"LIMIT {top_n};"
    )


def _tpl_cobranza_parciales(params: dict[str, Any]) -> str:
    clauses: list[str] = ["v.metodo_pago = 'PPD'"]
    _append_common_sales_filters(clauses, params, alias="v")
    where_sql = _where_clause(clauses)
    top_n = _top_n(params)

    return (
        "SELECT "
        "v.receptor_nombre AS cliente, "
        "COUNT(*) AS facturas_ppd, "
        "ROUND(SUM(COALESCE(v.total, 0))::numeric, 2) AS cartera_ppd "
        "FROM cfdi_ventas v "
        f"{where_sql} "
        "GROUP BY v.receptor_nombre "
        "ORDER BY cartera_ppd DESC "
        f"LIMIT {top_n};"
    )


def _tpl_cobranza_antiguedad_cartera(params: dict[str, Any]) -> str:
    clauses: list[str] = ["v.metodo_pago = 'PPD'"]
    _append_common_sales_filters(clauses, params, alias="v")
    where_sql = _where_clause(clauses)

    return (
        "WITH base AS ("
        "SELECT "
        "CASE "
        "WHEN CURRENT_DATE - v.fecha_emision::date <= 30 THEN '00-30' "
        "WHEN CURRENT_DATE - v.fecha_emision::date <= 60 THEN '31-60' "
        "WHEN CURRENT_DATE - v.fecha_emision::date <= 90 THEN '61-90' "
        "ELSE '90+' END AS bucket, "
        "COALESCE(v.total, 0) AS monto "
        "FROM cfdi_ventas v "
        f"{where_sql}"
        ") "
        "SELECT bucket AS antiguedad, "
        "COUNT(*) AS facturas, "
        "ROUND(SUM(monto)::numeric, 2) AS saldo "
        "FROM base "
        "GROUP BY bucket "
        "ORDER BY bucket;"
    )


def _tpl_fiscal_resumen_ingresos(params: dict[str, Any]) -> str:
    clauses: list[str] = []
    _append_common_sales_filters(clauses, params, alias="v")
    where_sql = _where_clause(clauses)

    return (
        "SELECT "
        "ROUND(SUM(COALESCE(v.subtotal, 0))::numeric, 2) AS subtotal, "
        "ROUND(SUM(COALESCE(v.total, 0))::numeric, 2) AS total, "
        "ROUND(SUM(COALESCE(v.impuestos, 0))::numeric, 2) AS iva_trasladado, "
        "ROUND(SUM(COALESCE(v.iva_retenido, 0))::numeric, 2) AS iva_retenido, "
        "ROUND(SUM(COALESCE(v.isr_retenido, 0))::numeric, 2) AS isr_retenido "
        "FROM cfdi_ventas v "
        f"{where_sql};"
    )


def _tpl_fiscal_impuestos_retenidos_trasladados(params: dict[str, Any]) -> str:
    clauses: list[str] = []
    _append_common_sales_filters(clauses, params, alias="v")
    where_sql = _where_clause(clauses)
    bucket = _grouping_expression(params)
    if bucket == "NULL":
        bucket = "DATE_TRUNC('month', v.fecha_emision)"

    return (
        "SELECT "
        f"{bucket} AS periodo, "
        "ROUND(SUM(COALESCE(v.impuestos, 0))::numeric, 2) AS iva_trasladado, "
        "ROUND(SUM(COALESCE(v.iva_retenido, 0))::numeric, 2) AS iva_retenido, "
        "ROUND(SUM(COALESCE(v.isr_retenido, 0))::numeric, 2) AS isr_retenido "
        "FROM cfdi_ventas v "
        f"{where_sql} "
        f"GROUP BY {bucket} "
        "ORDER BY periodo;"
    )


def _tpl_fiscal_egresos_notas_credito(params: dict[str, Any]) -> str:
    clauses: list[str] = ["v.tipo_comprobante = 'E'"]
    _append_common_sales_filters(clauses, params, alias="v")
    where_sql = _where_clause(clauses)
    bucket = _grouping_expression(params)
    if bucket == "NULL":
        bucket = "DATE_TRUNC('month', v.fecha_emision)"

    return (
        "SELECT "
        f"{bucket} AS periodo, "
        "COUNT(*) AS notas_credito, "
        "ROUND(SUM(COALESCE(v.total, 0))::numeric, 2) AS monto "
        "FROM cfdi_ventas v "
        f"{where_sql} "
        f"GROUP BY {bucket} "
        "ORDER BY periodo;"
    )


VENTAS_TEMPLATE_REGISTRY: dict[str, TemplateBuilder] = {
    "tpl_ventas_resumen_ejecutivo": _tpl_ventas_resumen_ejecutivo,
    "tpl_ventas_por_mes": _tpl_ventas_por_mes,
    "tpl_ventas_top_clientes": _tpl_ventas_top_clientes,
    "tpl_ventas_top_productos": _tpl_ventas_top_productos,
    "tpl_ventas_concentracion_clientes": _tpl_ventas_concentracion_clientes,
}

PRODUCTOS_TEMPLATE_REGISTRY: dict[str, TemplateBuilder] = {
    "tpl_productos_precios_estadisticas": _tpl_productos_precios_estadisticas,
    "tpl_productos_top_facturacion": _tpl_productos_top_facturacion,
    "tpl_productos_menor_venta": _tpl_productos_menor_venta,
    "tpl_productos_participacion_mix": _tpl_productos_participacion_mix,
}

CLIENTES_TEMPLATE_REGISTRY: dict[str, TemplateBuilder] = {
    "tpl_clientes_ranking": _tpl_clientes_ranking,
    "tpl_clientes_recurrentes": _tpl_clientes_recurrentes,
    "tpl_clientes_nuevos_periodo": _tpl_clientes_nuevos_periodo,
    "tpl_clientes_crecimiento": _tpl_clientes_crecimiento,
}

COBRANZA_TEMPLATE_REGISTRY: dict[str, TemplateBuilder] = {
    "tpl_cobranza_pendientes": _tpl_cobranza_pendientes,
    "tpl_cobranza_pagadas": _tpl_cobranza_pagadas,
    "tpl_cobranza_parciales": _tpl_cobranza_parciales,
    "tpl_cobranza_antiguedad_cartera": _tpl_cobranza_antiguedad_cartera,
}

FISCAL_TEMPLATE_REGISTRY: dict[str, TemplateBuilder] = {
    "tpl_fiscal_resumen_ingresos": _tpl_fiscal_resumen_ingresos,
    "tpl_fiscal_impuestos_retenidos_trasladados": _tpl_fiscal_impuestos_retenidos_trasladados,
    "tpl_fiscal_egresos_notas_credito": _tpl_fiscal_egresos_notas_credito,
}

TEMPLATE_REGISTRY: dict[str, TemplateBuilder] = {
    **VENTAS_TEMPLATE_REGISTRY,
    **PRODUCTOS_TEMPLATE_REGISTRY,
    **CLIENTES_TEMPLATE_REGISTRY,
    **COBRANZA_TEMPLATE_REGISTRY,
    **FISCAL_TEMPLATE_REGISTRY,
}


class GuidedQueryFramework:
    """Framework deterministico para ejecutar casos guiados sin NL libre."""

    def __init__(self, catalog: dict[str, Any]):
        self.catalog = catalog
        self.case_index: dict[str, dict[str, Any]] = {}
        for domain in self.catalog.get("domains", []):
            for case in domain.get("cases", []):
                self.case_index[case["id"]] = {
                    **case,
                    "domain_id": domain.get("id"),
                    "domain_label": domain.get("label", domain.get("id", "")),
                }

    def list_enabled_domains(self) -> list[dict[str, Any]]:
        return [domain for domain in self.catalog.get("domains", []) if bool(domain.get("enabled", True))]

    def list_enabled_cases(self, domain_id: str) -> list[dict[str, Any]]:
        domain = next((d for d in self.catalog.get("domains", []) if d.get("id") == domain_id), None)
        if not domain:
            return []
        return [case for case in domain.get("cases", []) if bool(case.get("enabled", True))]

    def get_case(self, case_id: str) -> dict[str, Any]:
        case = self.case_index.get(case_id)
        if not case:
            raise ValueError(f"Caso no encontrado: {case_id}")
        if not bool(case.get("enabled", True)):
            raise ValueError(f"Caso deshabilitado: {case_id}")
        return case

    def build_query(self, case_id: str, params: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
        case = self.get_case(case_id)
        template_id = case.get("sql_template_id")
        builder = TEMPLATE_REGISTRY.get(template_id)
        if not builder:
            raise ValueError(f"Template no implementado: {template_id}")
        sql = builder(params)
        return sql, case.get("default_chart", "table"), case

    def execute_case(self, engine: Any, case_id: str, params: dict[str, Any], *, empresa_id: Optional[str] = None) -> GuidedExecutionResult:
        sql, chart, case = self.build_query(case_id, params)

        t0 = time.time()
        dataframe = engine.execute_query(sql, empresa_id=empresa_id)
        elapsed = time.time() - t0

        summary = (
            f"Caso guiado ejecutado: {case.get('label', case_id)}. "
            f"Se obtuvieron {len(dataframe)} filas con plantilla {case.get('sql_template_id', 'n/a')}."
        )

        return GuidedExecutionResult(
            case_id=case_id,
            case_label=case.get("label", case_id),
            sql=sql,
            dataframe=dataframe,
            row_count=len(dataframe),
            chart=chart,
            summary=summary,
            execution_time=elapsed,
        )
