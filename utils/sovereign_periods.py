"""
Módulo: Períodos Soberanos
==========================
Construye un índice de rangos de tiempo deterministas derivado directamente
del DataFrame cargado. El índice se inyecta en el system prompt del asistente
de datos y se presenta en la UI como un slider, garantizando que el modelo
nunca infiera fechas sino que opere sobre hechos conocidos del dataset.

Estructura de cada entrada del índice:
    {
        "nombre":       str   — etiqueta en lenguaje natural
        "desde":        str   — "YYYY-MM-DD"
        "hasta":        str   — "YYYY-MM-DD" (inclusive último día del período)
        "hasta_excl":   str   — "YYYY-MM-DD" (exclusive, para WHERE col < hasta_excl)
        "granularidad": str   — "mensual" | "trimestral" | "anual" | "total"
        "tipo":         str   — "mes" | "trimestre" | "año" | "rango" | "alias"
    }
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta
from typing import Optional

import pandas as pd


# ── Nombres en español ──────────────────────────────────────────────────────
_MESES_ES = [
    "", "Ene", "Feb", "Mar", "Abr", "May", "Jun",
    "Jul", "Ago", "Sep", "Oct", "Nov", "Dic",
]
_MESES_FULL = [
    "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]
_TRIMESTRES = {1: "Q1 (Ene–Mar)", 2: "Q2 (Abr–Jun)", 3: "Q3 (Jul–Sep)", 4: "Q4 (Oct–Dic)"}


def _first_day(year: int, month: int) -> date:
    return date(year, month, 1)


def _last_day_excl(year: int, month: int) -> date:
    """Primer día del mes siguiente (para WHERE fecha < last_day_excl)."""
    if month == 12:
        return date(year + 1, 1, 1)
    return date(year, month + 1, 1)


def _quarter_range(year: int, q: int) -> tuple[date, date]:
    """Devuelve (primer día del trimestre, primer día del trimestre siguiente)."""
    start_month = (q - 1) * 3 + 1
    end_month = start_month + 2
    return _first_day(year, start_month), _last_day_excl(year, end_month)


def _entry(nombre: str, desde: date, hasta_excl: date,
           granularidad: str, tipo: str) -> dict:
    hasta = hasta_excl - timedelta(days=1)
    return {
        "nombre":       nombre,
        "desde":        desde.isoformat(),
        "hasta":        hasta.isoformat(),
        "hasta_excl":   hasta_excl.isoformat(),
        "granularidad": granularidad,
        "tipo":         tipo,
    }


# ── Construcción del índice soberano ────────────────────────────────────────

def build_sovereign_index(df: pd.DataFrame,
                          fecha_col: str = "fecha") -> dict:
    """
    Construye el índice soberano a partir del DataFrame.

    Parámetros
    ----------
    df        : DataFrame con los datos de ventas
    fecha_col : nombre de la columna de fecha (default: "fecha")

    Retorna
    -------
    dict con:
        "periodos"  : list[dict]  — índice completo de períodos disponibles
        "meses"     : list[str]   — etiquetas de meses para el slider (sorted)
        "min_fecha" : str         — fecha mínima "YYYY-MM-DD"
        "max_fecha" : str         — fecha máxima "YYYY-MM-DD"
        "anos"      : list[int]   — años presentes en el dataset
    """
    periodos: list[dict] = []

    # ── Detectar columna de fecha ───────────────────────────────────────────
    if fecha_col not in df.columns:
        for c in ["fecha", "fecha_emision", "date", "fecha_registro"]:
            if c in df.columns:
                fecha_col = c
                break
        else:
            return _empty_index()

    fechas = pd.to_datetime(df[fecha_col], errors="coerce").dropna()
    if fechas.empty:
        return _empty_index()

    min_fecha = fechas.min().date()
    max_fecha = fechas.max().date()

    # ── Calcular meses presentes ────────────────────────────────────────────
    meses_presentes: list[tuple[int, int]] = sorted(
        {(d.year, d.month) for d in fechas.dt.date}
    )

    anos_presentes = sorted({y for y, _ in meses_presentes})

    # ── 1. Entradas mensuales ───────────────────────────────────────────────
    for year, month in meses_presentes:
        nombre = f"{_MESES_FULL[month]} {year}"
        periodos.append(_entry(
            nombre,
            _first_day(year, month),
            _last_day_excl(year, month),
            granularidad="total",
            tipo="mes",
        ))

    # ── 2. Entradas trimestrales ────────────────────────────────────────────
    trimestres_presentes: set[tuple[int, int]] = set()
    for year, month in meses_presentes:
        q = (month - 1) // 3 + 1
        trimestres_presentes.add((year, q))

    for year, q in sorted(trimestres_presentes):
        nombre = f"{_TRIMESTRES[q]} {year}"
        inicio, fin_excl = _quarter_range(year, q)
        periodos.append(_entry(
            nombre, inicio, fin_excl,
            granularidad="mensual",
            tipo="trimestre",
        ))

    # ── 3. Entradas anuales ─────────────────────────────────────────────────
    for year in anos_presentes:
        nombre = f"Año {year} completo"
        periodos.append(_entry(
            nombre,
            date(year, 1, 1),
            date(year + 1, 1, 1),
            granularidad="mensual",
            tipo="año",
        ))

    # ── 4. Rango completo del dataset ───────────────────────────────────────
    if len(anos_presentes) > 1:
        nombre_rango = (
            f"{_MESES_ES[min_fecha.month]} {min_fecha.year} – "
            f"{_MESES_ES[max_fecha.month]} {max_fecha.year}"
        )
        periodos.append(_entry(
            nombre_rango,
            _first_day(min_fecha.year, min_fecha.month),
            _last_day_excl(max_fecha.year, max_fecha.month),
            granularidad="mensual",
            tipo="rango",
        ))

    # ── 5. Aliases en lenguaje natural ──────────────────────────────────────
    hoy = date.today()
    ano_actual = hoy.year
    ano_anterior = hoy.year - 1

    if ano_actual in anos_presentes:
        periodos.append(_entry(
            "Este año (año en curso)",
            date(ano_actual, 1, 1),
            date(ano_actual + 1, 1, 1),
            granularidad="mensual",
            tipo="alias",
        ))

    if ano_anterior in anos_presentes:
        periodos.append(_entry(
            "El año pasado",
            date(ano_anterior, 1, 1),
            date(ano_anterior + 1, 1, 1),
            granularidad="mensual",
            tipo="alias",
        ))

    # Semestres por año
    for year in anos_presentes:
        meses_del_ano = [m for y, m in meses_presentes if y == year]
        if any(m <= 6 for m in meses_del_ano):
            periodos.append(_entry(
                f"Primer semestre {year}",
                date(year, 1, 1),
                date(year, 7, 1),
                granularidad="mensual",
                tipo="alias",
            ))
        if any(m >= 7 for m in meses_del_ano):
            periodos.append(_entry(
                f"Segundo semestre {year}",
                date(year, 7, 1),
                date(year + 1, 1, 1),
                granularidad="mensual",
                tipo="alias",
            ))

    # Etiquetas de meses para el slider (solo tipo "mes", en orden)
    etiquetas_meses = [
        p["nombre"] for p in periodos if p["tipo"] == "mes"
    ]

    return {
        "periodos":   periodos,
        "meses":      etiquetas_meses,
        "min_fecha":  min_fecha.isoformat(),
        "max_fecha":  max_fecha.isoformat(),
        "anos":       anos_presentes,
    }


def _empty_index() -> dict:
    return {"periodos": [], "meses": [], "min_fecha": None, "max_fecha": None, "anos": []}


# ── Búsqueda en el índice ────────────────────────────────────────────────────

def find_period(index: dict, nombre: str) -> Optional[dict]:
    """Busca un período por nombre exacto en el índice."""
    for p in index.get("periodos", []):
        if p["nombre"] == nombre:
            return p
    return None


def get_active_period(index: dict,
                      desde_label: str,
                      hasta_label: str,
                      granularidad: str = "mensual") -> dict:
    """
    Construye el período activo a partir de dos etiquetas del slider
    (primer mes seleccionado, último mes seleccionado) y la granularidad.

    Retorna un dict con:
        desde, hasta, hasta_excl, granularidad, label
    """
    p_desde = find_period(index, desde_label)
    p_hasta = find_period(index, hasta_label)

    if not p_desde or not p_hasta:
        return {}

    # El "hasta" final es el último día (inclusive) del mes final
    label = (
        desde_label if desde_label == hasta_label
        else f"{desde_label} – {hasta_label}"
    )

    return {
        "label":        label,
        "desde":        p_desde["desde"],
        "hasta":        p_hasta["hasta"],
        "hasta_excl":   p_hasta["hasta_excl"],
        "granularidad": granularidad,
    }


# ── Generación del bloque para el system prompt ──────────────────────────────

def build_prompt_context(periodo_activo: dict, index: dict) -> str:
    """
    Genera el texto que se inyecta en el system prompt del asistente,
    con el período activo y el inventario de períodos disponibles.
    """
    if not periodo_activo:
        return ""

    gran = periodo_activo.get("granularidad", "mensual")
    gran_sql = {
        "mensual":     "DATE_TRUNC('month', fecha_emision)",
        "trimestral":  "DATE_TRUNC('quarter', fecha_emision)",
        "anual":       "DATE_TRUNC('year', fecha_emision)",
        "total":       "— Sin GROUP BY temporal (suma total del período)",
    }.get(gran, "DATE_TRUNC('month', fecha_emision)")

    anos = index.get("anos", [])
    anos_str = ", ".join(str(a) for a in anos)

    meses = index.get("meses", [])
    meses_str = ", ".join(meses[:6])
    if len(meses) > 6:
        meses_str += f" ... ({len(meses)} meses en total)"

    return f"""
══════════════════════════════════════════════════════
CONTEXTO TEMPORAL — PERÍODO SOBERANO (OBLIGATORIO)
══════════════════════════════════════════════════════
PERÍODO ACTIVO SELECCIONADO POR EL USUARIO:
  Nombre       : {periodo_activo['label']}
  Desde        : {periodo_activo['desde']}
  Hasta        : {periodo_activo['hasta']}  (inclusive)
  Hasta excl.  : {periodo_activo['hasta_excl']}  (para WHERE fecha < X)
  Granularidad : {gran}

REGLAS TEMPORALES ABSOLUTAS (prioridad máxima — no negociables):
1. SIEMPRE filtra: fecha_emision >= '{periodo_activo['desde']}' AND fecha_emision < '{periodo_activo['hasta_excl']}'
2. NUNCA uses CURRENT_DATE, NOW(), CURRENT_TIMESTAMP para definir períodos.
3. NUNCA uses EXTRACT(YEAR FROM CURRENT_DATE).
4. Si el usuario menciona "este año" o "el año pasado", REEMPLAZA con el período activo arriba.
5. Para GROUP BY temporal usa: {gran_sql}
6. Si el usuario pide desglose mensual explícito, usa DATE_TRUNC('month', fecha_emision) sin importar la granularidad activa.

INVENTARIO DE DATOS DISPONIBLES:
  Años en el dataset : {anos_str}
  Primeros meses     : {meses_str}
══════════════════════════════════════════════════════
"""


# ── Validador pre-vuelo ───────────────────────────────────────────────────────

def validate_question(pregunta: str, periodo_activo: dict, index: dict) -> dict:
    """
    Valida la pregunta del usuario contra el período activo y el índice soberano.

    Retorna:
        {
            "ok":       bool,
            "nivel":    "ok" | "aviso" | "bloqueo",
            "mensaje":  str,
            "sugerencia": str | None,
        }
    """
    if not periodo_activo or not index:
        return {"ok": True, "nivel": "ok", "mensaje": "", "sugerencia": None}

    q = pregunta.lower()
    anos = index.get("anos", [])
    desde = periodo_activo.get("desde", "")
    hasta = periodo_activo.get("hasta", "")
    ano_desde = int(desde[:4]) if desde else None
    ano_hasta = int(hasta[:4]) if hasta else None

    # ── Detectar años mencionados en la pregunta ────────────────────────────
    import re
    anos_mencionados = [int(m) for m in re.findall(r'\b(20[2-3]\d)\b', q)]

    for ano_mencionado in anos_mencionados:
        if ano_mencionado not in anos:
            return {
                "ok":       False,
                "nivel":    "bloqueo",
                "mensaje":  f"⚠️ El año {ano_mencionado} no existe en los datos.",
                "sugerencia": f"Los años disponibles son: {', '.join(str(a) for a in anos)}",
            }

    # ── Detectar referencias temporales ambiguas ────────────────────────────
    if any(kw in q for kw in ["este año", "año actual", "año en curso"]):
        if ano_desde:
            return {
                "ok":       True,
                "nivel":    "aviso",
                "mensaje":  f"🗓️ 'Este año' se interpretará como el período activo: {periodo_activo['label']}",
                "sugerencia": None,
            }

    if any(kw in q for kw in ["el año pasado", "año pasado", "año anterior"]):
        if ano_desde:
            return {
                "ok":       True,
                "nivel":    "aviso",
                "mensaje":  f"🗓️ 'El año pasado' se interpretará como el período activo: {periodo_activo['label']}",
                "sugerencia": None,
            }

    # ── Detectar conflicto de granularidad ──────────────────────────────────
    gran = periodo_activo.get("granularidad", "mensual")
    if gran == "total" and any(kw in q for kw in ["mes a mes", "por mes", "mensual", "desglose mensual"]):
        return {
            "ok":       True,
            "nivel":    "aviso",
            "mensaje":  "🔬 Tu granularidad activa es 'total'. La pregunta pide desglose mensual — se usará granularidad mensual para esta consulta.",
            "sugerencia": None,
        }

    return {"ok": True, "nivel": "ok", "mensaje": "", "sugerencia": None}
