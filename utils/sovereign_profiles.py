"""
Módulo: Perfiles Soberanos
==========================
Define perfiles predefinidos de análisis que acotan el universo semántico
del asistente de datos. Cada perfil combina:
  - Tipos de comprobante CFDI habilitados (I, E, P, N)
  - Tipos de impuesto en scope
  - Métodos de pago habilitados
  - Conceptos analíticos disponibles
  - Hint de tono/estilo para el system prompt

El usuario selecciona un perfil (botón) y opcionalmente ajusta sus
checkboxes. El perfil activo se inyecta en el system prompt y se
aplica como filtro post-generación en el SQL.
"""

from __future__ import annotations
import re
from typing import Optional

# ── Catálogos estáticos ─────────────────────────────────────────────────────

TIPOS_COMPROBANTE = {
    "I": "Ingresos (facturas emitidas)",
    "E": "Egresos (notas de crédito / devoluciones)",
    "P": "Pagos (complementos de pago)",
    "N": "Nómina",
    "T": "Traslados",
}

TIPOS_IMPUESTO = {
    "iva_trasladado": "IVA trasladado (cobrado)",
    "iva_retenido":   "IVA retenido",
    "isr_retenido":   "ISR retenido",
}

METODOS_PAGO = {
    "PUE": "PUE — Pago en una sola exhibición",
    "PPD": "PPD — Pago en parcialidades / diferido",
}

# ── Perfiles predefinidos ───────────────────────────────────────────────────

PERFILES: dict[str, dict] = {
    "resumen_ejecutivo": {
        "label":              "Resumen Ejecutivo",
        "icono":              "📊",
        "descripcion":        "Totales y tendencias de ventas para dirección",
        "tipos_comprobante":  ["I"],
        "impuestos":          ["iva_trasladado"],
        "metodos_pago":       ["PUE", "PPD"],
        "multi_moneda":       False,
        "prompt_hint": (
            "Responde con lenguaje ejecutivo, orientado a decisiones. "
            "Enfócate en totales, variaciones porcentuales y top rankings. "
            "Evita tecnicismos fiscales."
        ),
    },
    "auditoria_fiscal": {
        "label":              "Auditoría Fiscal",
        "icono":              "🔍",
        "descripcion":        "Revisión de impuestos, retenciones y diferencias SAT",
        "tipos_comprobante":  ["I", "E"],
        "impuestos":          ["iva_trasladado", "iva_retenido", "isr_retenido"],
        "metodos_pago":       ["PUE", "PPD"],
        "multi_moneda":       False,
        "prompt_hint": (
            "Responde con precisión técnica fiscal. Incluye claves SAT cuando sean relevantes. "
            "Distingue entre traslados y retenciones. Señala anomalías o diferencias."
        ),
    },
    "cobranza": {
        "label":              "Cobranza",
        "icono":              "💰",
        "descripcion":        "Seguimiento de complementos de pago y cuentas por cobrar",
        "tipos_comprobante":  ["P"],
        "impuestos":          [],
        "metodos_pago":       ["PPD"],
        "multi_moneda":       False,
        "prompt_hint": (
            "Enfócate en pagos recibidos, saldos pendientes y antigüedad de cartera. "
            "Menciona UUIDs de documentos relacionados cuando estén disponibles."
        ),
    },
    "rentabilidad": {
        "label":              "Rentabilidad",
        "icono":              "📈",
        "descripcion":        "Análisis de margen por producto, cliente o periodo",
        "enabled":            False,
        "blocked_reason":     "Depende de costos, descuentos y comisiones integrados y verificados.",
        "tipos_comprobante":  ["I", "E"],
        "impuestos":          ["iva_trasladado"],
        "metodos_pago":       ["PUE", "PPD"],
        "multi_moneda":       True,
        "prompt_hint": (
            "Analiza márgenes, costos y rentabilidad. Normaliza a MXN cuando haya multi-moneda. "
            "Compara periodos y segmenta por producto o cliente cuando sea útil."
        ),
    },
    "conciliacion": {
        "label":              "Conciliación",
        "icono":              "⚖️",
        "descripcion":        "Cuadre contable completo — ingresos, egresos y pagos",
        "enabled":            False,
        "blocked_reason":     "Depende de tablas de reconciliación y snapshots de cartera implementados y verificados.",
        "tipos_comprobante":  ["I", "E", "P"],
        "impuestos":          ["iva_trasladado", "iva_retenido", "isr_retenido"],
        "metodos_pago":       ["PUE", "PPD"],
        "multi_moneda":       True,
        "prompt_hint": (
            "Verifica que los montos cuadren. Detecta diferencias entre facturas emitidas "
            "y pagos recibidos. Incluye cancelaciones si las hay."
        ),
    },
    "nomina": {
        "label":              "Nómina",
        "icono":              "👥",
        "descripcion":        "Revisión de dispersión de nómina e ISR retenido",
        "tipos_comprobante":  ["N"],
        "impuestos":          ["isr_retenido"],
        "metodos_pago":       [],
        "multi_moneda":       False,
        "prompt_hint": (
            "IMPORTANTE: No existe tabla cfdi_nomina. Los comprobantes de nómina "
            "están en cfdi_ventas con tipo_comprobante = 'N'. "
            "Usa siempre FROM cfdi_ventas WHERE tipo_comprobante = 'N'. "
            "Analiza totales, impuestos retenidos y tendencias de nómina. "
            "Agrupa por receptor (empleado) o periodo según corresponda."
        ),
    },
}

# Perfil por defecto al iniciar sesión
PERFIL_DEFAULT = "resumen_ejecutivo"


# ── Funciones de utilidad ───────────────────────────────────────────────────

def get_perfil(perfil_key: str) -> dict:
    """Retorna el perfil por clave, o el default si no existe."""
    return PERFILES.get(perfil_key, PERFILES[PERFIL_DEFAULT])


def build_sovereign_profile_context(perfil: dict) -> str:
    """
    Construye el bloque de contexto soberano de perfil para inyectar
    al inicio del system prompt del modelo.

    Parámetros
    ----------
    perfil : dict — perfil activo (de PERFILES o ajustado por el usuario)

    Retorna
    -------
    str con el bloque de instrucción soberana de perfil
    """
    tipos = perfil.get("tipos_comprobante", [])
    impuestos = perfil.get("impuestos", [])
    metodos = perfil.get("metodos_pago", [])
    multi_moneda = perfil.get("multi_moneda", False)
    hint = perfil.get("prompt_hint", "")

    tipos_str = ", ".join(
        f"{k} ({TIPOS_COMPROBANTE.get(k, k)})" for k in tipos
    ) if tipos else "todos"

    impuestos_str = ", ".join(
        TIPOS_IMPUESTO.get(i, i) for i in impuestos
    ) if impuestos else "ninguno"

    metodos_str = ", ".join(metodos) if metodos else "todos"

    moneda_str = "Normaliza a MXN usando tipo_cambio cuando haya multi-moneda." if multi_moneda else \
                 "Esta sesión es solo MXN. Ignora registros en otras monedas."

    out = f"""══════════════════════════════════════════════════
PERFIL SOBERANO ACTIVO: {perfil.get('label', 'Personalizado')}
══════════════════════════════════════════════════
SCOPE DE ESTA SESIÓN — RESTRICCIONES ABSOLUTAS:
• Tipos de comprobante: {tipos_str}
• Impuestos en análisis: {impuestos_str}
• Métodos de pago: {metodos_str}
• Moneda: {moneda_str}

INSTRUCCIÓN DE ESTILO:
{hint}

Si la pregunta requiere datos fuera de este scope, responde:
"Ese análisis está fuera del perfil activo ({perfil.get('label', 'actual')})."
══════════════════════════════════════════════════
"""
    return out


def apply_profile_sql_filter(sql: str, perfil: dict) -> str:
    """
    Inyecta filtros de tipo_comprobante y metodo_pago en el SQL generado
    si el perfil restringe esos campos y el SQL no los incluye ya.

    Solo actúa sobre la tabla cfdi_ventas.
    """
    tipos = perfil.get("tipos_comprobante", [])
    metodos = perfil.get("metodos_pago", [])

    sql_upper = sql.upper()

    def _top_level_from_table(sql_text: str) -> Optional[str]:
        depth = 0
        sql_upper_text = sql_text.upper()
        idx = 0
        while idx < len(sql_upper_text):
            char = sql_upper_text[idx]
            if char == '(':
                depth += 1
                idx += 1
                continue
            if char == ')':
                depth = max(0, depth - 1)
                idx += 1
                continue
            if depth == 0 and sql_upper_text.startswith("FROM ", idx):
                match = re.match(r'FROM\s+(\w+)', sql_text[idx:], flags=re.IGNORECASE)
                if match:
                    return match.group(1).lower()
            idx += 1
        return None

    def _inject_into_cfdi_ventas_subquery(sql_text: str, condition: str) -> str:
        stack: list[int] = []
        for idx, char in enumerate(sql_text):
            if char == '(':
                stack.append(idx)
            elif char == ')' and stack:
                start = stack.pop()
                inner = sql_text[start + 1:idx]
                if re.search(r'\bSELECT\b', inner, re.IGNORECASE) and re.search(r'\bFROM\s+cfdi_ventas\b', inner, re.IGNORECASE):
                    updated_inner = _inject_and_condition(inner, condition).rstrip().rstrip(';')
                    return sql_text[:start + 1] + updated_inner + sql_text[idx:]
        return sql_text

    top_level_table = _top_level_from_table(sql)

    # Solo actuar si la query principal es cfdi_ventas o si hay un subquery explícito a cfdi_ventas.
    if top_level_table != "cfdi_ventas" and "CFDI_VENTAS" not in sql_upper:
        return sql

    # ── Filtro tipo_comprobante ───────────────────────────────────────────
    if tipos and "TIPO_COMPROBANTE" not in sql_upper:
        if len(tipos) == 1:
            tipo_clause = f"tipo_comprobante = '{tipos[0]}'"
        else:
            lista = ", ".join(f"'{t}'" for t in tipos)
            tipo_clause = f"tipo_comprobante IN ({lista})"

        if top_level_table == "cfdi_ventas":
            sql = _inject_and_condition(sql, tipo_clause)
        else:
            sql = _inject_into_cfdi_ventas_subquery(sql, tipo_clause)

    # ── Filtro metodo_pago ──────────────────────────────────────────────────
    if metodos and "METODO_PAGO" not in sql_upper:
        if len(metodos) == 1:
            mp_clause = f"metodo_pago = '{metodos[0]}'"
        else:
            lista = ", ".join(f"'{m}'" for m in metodos)
            mp_clause = f"metodo_pago IN ({lista})"

        if top_level_table == "cfdi_ventas":
            sql = _inject_and_condition(sql, mp_clause)
        else:
            sql = _inject_into_cfdi_ventas_subquery(sql, mp_clause)

    return sql


def _inject_and_condition(sql: str, condition: str) -> str:
    """
    Inyecta una condición AND en el WHERE existente, o crea uno new.
    Inyecta antes de GROUP BY / ORDER BY / LIMIT si no hay WHERE.
    """
    def _find_top_level_clause_index(sql_text: str, keywords: list[str]) -> Optional[int]:
        sql_upper = sql_text.upper()
        candidates: list[int] = []
        depth = 0

        for idx, char in enumerate(sql_upper):
            if char == '(':
                depth += 1
                continue
            if char == ')':
                depth = max(0, depth - 1)
                continue

            if depth != 0:
                continue

            for keyword in keywords:
                keyword_upper = keyword.upper()
                if not sql_upper.startswith(keyword_upper, idx):
                    continue

                prev_char = sql_upper[idx - 1] if idx > 0 else ' '
                next_idx = idx + len(keyword_upper)
                next_char = sql_upper[next_idx] if next_idx < len(sql_upper) else ' '
                if (prev_char.isalnum() or prev_char == '_') or (next_char.isalnum() or next_char == '_'):
                    continue

                candidates.append(idx)

        return min(candidates) if candidates else None

    sql_upper = sql.upper()

    if "WHERE" in sql_upper:
        # Agregar al final del bloque WHERE (antes de GROUP/ORDER/LIMIT)
        idx = _find_top_level_clause_index(sql, ["GROUP BY", "ORDER BY", "LIMIT", "HAVING"])
        if idx is not None:
            return sql[:idx] + f"AND {condition} " + sql[idx:]
        # WHERE sin GROUP/ORDER/LIMIT → agregar al final antes de ;
        sql = sql.rstrip(";").rstrip()
        return sql + f" AND {condition};"
    else:
        idx = _find_top_level_clause_index(sql, ["GROUP BY", "ORDER BY", "LIMIT", "HAVING"])
        if idx is not None:
            return sql[:idx] + f"WHERE {condition} " + sql[idx:]
        sql = sql.rstrip(";").rstrip()
        return sql + f" WHERE {condition};"
