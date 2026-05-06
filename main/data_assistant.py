"""
Módulo: Asistente de Datos — Consultas en lenguaje natural sobre CFDIs.

Interfaz conversacional que permite hacer preguntas sobre los datos
de facturación ingestados en Neon PostgreSQL y obtener respuestas
con tablas, gráficas e interpretación IA.

Autor: Fradma Dashboard Team
Fecha: Febrero 2026
"""

import os
import json
from io import StringIO
from datetime import date
from typing import Optional
import streamlit as st
import pandas as pd

try:
    import plotly.express as px
    import plotly.graph_objects as go
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

from utils.nl2sql import (
    NL2SQLEngine,
    NL2SQLResult,
    validate_sql_static,
    get_example_questions,
    ALLOWED_TABLES,
    SCHEMA_CONTEXT,
    PSYCOPG2_AVAILABLE,
    OPENAI_AVAILABLE,
)

from utils.roi_tracker import init_roi_tracker
from utils.logger import configurar_logger
from utils.auth import get_current_user

try:
    from utils.guided_catalog_store import load_runtime_catalog, catalog_stats
    GUIDED_CATALOG_AVAILABLE = True
except ImportError:
    GUIDED_CATALOG_AVAILABLE = False

try:
    from utils.guided_query_framework import GuidedQueryFramework
    GUIDED_FRAMEWORK_AVAILABLE = True
except ImportError:
    GUIDED_FRAMEWORK_AVAILABLE = False

try:
    from utils.guided_usage_metrics import (
        record_session_guided_usage,
        get_session_guided_usage_summary,
        record_db_guided_usage,
        get_db_guided_usage_summary,
        get_db_guided_usage_timeseries,
    )
    GUIDED_USAGE_METRICS_AVAILABLE = True
except ImportError:
    GUIDED_USAGE_METRICS_AVAILABLE = False

# Configurar logger para data_assistant
logger = configurar_logger("data_assistant", nivel="INFO")


# =====================================================================
# CSS personalizado
# =====================================================================
ASSISTANT_CSS = """
<style>
.assistant-hero {
    background: linear-gradient(135deg, #0f2027 0%, #203a43 50%, #2c5364 100%);
    padding: 2rem 2.5rem;
    border-radius: 16px;
    color: white;
    margin-bottom: 1.5rem;
}
.assistant-hero h2 {
    margin: 0 0 0.5rem 0;
    font-size: 1.8rem;
}
.assistant-hero p {
    margin: 0;
    opacity: 0.85;
    font-size: 1rem;
}
.chat-msg-user {
    background: #e8f4f8;
    border-left: 4px solid #2196F3;
    padding: 1rem 1.25rem;
    border-radius: 0 12px 12px 0;
    margin: 0.5rem 0;
}
.chat-msg-assistant {
    background: #f0f7f0;
    border-left: 4px solid #4CAF50;
    padding: 1rem 1.25rem;
    border-radius: 0 12px 12px 0;
    margin: 0.5rem 0;
}
.sql-block {
    background: #1e1e2e;
    color: #cdd6f4;
    padding: 1rem;
    border-radius: 8px;
    font-family: 'Consolas', 'Monaco', monospace;
    font-size: 0.85rem;
    overflow-x: auto;
    margin: 0.5rem 0;
}
.metric-card {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    padding: 1.5rem;
    border-radius: 12px;
    text-align: center;
}
.metric-card .value {
    font-size: 2rem;
    font-weight: 700;
}
.metric-card .label {
    font-size: 0.9rem;
    opacity: 0.85;
}
.example-btn {
    background: rgba(255,255,255,0.07);
    border: 1px solid rgba(255,255,255,0.15);
    border-radius: 8px;
    padding: 0.5rem 1rem;
    cursor: pointer;
    transition: all 0.2s;
    margin: 0.25rem 0;
    width: 100%;
    text-align: left;
    color: #e0e0e0;
}
.example-btn:hover {
    background: rgba(255,255,255,0.12);
    border-color: rgba(255,255,255,0.25);
}
.schema-table {
    background: rgba(255,255,255,0.07);
    border: 1px solid rgba(255,255,255,0.15);
    border-radius: 8px;
    padding: 0.75rem 1rem;
    margin: 0.25rem 0;
    font-size: 0.85rem;
    color: #e0e0e0;
}
.history-entry {
    background: rgba(255,255,255,0.07);
    border: 1px solid rgba(255,255,255,0.15);
    border-radius: 8px;
    padding: 0.75rem 1rem;
    margin: 0.5rem 0;
    cursor: pointer;
    color: #e0e0e0;
}
.status-badge {
    display: inline-block;
    padding: 0.2rem 0.6rem;
    border-radius: 12px;
    font-size: 0.75rem;
    font-weight: 600;
}
.status-ok { background: #d4edda; color: #155724; }
.status-err { background: #f8d7da; color: #721c24; }
</style>
"""


# =====================================================================
# Inicialización del engine
# =====================================================================
def _get_engine() -> NL2SQLEngine:
    """Obtiene o crea la instancia del engine NL2SQL."""
    if "nl2sql_engine" not in st.session_state:
        neon_url, api_key, model = _get_runtime_credentials()

        if not neon_url or not api_key:
            return None

        try:
            engine = NL2SQLEngine(
                connection_string=neon_url,
                api_key=api_key,
                model=model,
            )
            st.session_state["nl2sql_engine"] = engine
        except Exception as e:
            st.error(f"Error inicializando motor: {e}")
            return None

    return st.session_state.get("nl2sql_engine")


def _invalidate_engine():
    """Invalida la instancia del engine para recrearla."""
    if "nl2sql_engine" in st.session_state:
        del st.session_state["nl2sql_engine"]


# =====================================================================
# Visualización automática (con specs de IA)
# =====================================================================

# Paleta de colores profesional
CHART_COLORS = [
    "#2196F3", "#4CAF50", "#FF9800", "#E91E63", "#9C27B0",
    "#00BCD4", "#FF5722", "#607D8B", "#795548", "#8BC34A",
    "#3F51B5", "#FFEB3B", "#009688", "#F44336", "#673AB7",
]

MAX_CHAT_MESSAGES = 40
MAX_SESSION_RESULT_ROWS = 300


def _append_chat_message(msg: dict):
    """Agrega un mensaje al chat y limita el tamaño de la sesión."""
    if "nl2sql_messages" not in st.session_state:
        st.session_state["nl2sql_messages"] = []
    st.session_state["nl2sql_messages"].append(msg)
    st.session_state["nl2sql_messages"] = st.session_state["nl2sql_messages"][-MAX_CHAT_MESSAGES:]


def _get_active_empresa_id():
    """Obtiene el empresa_id efectivo del contexto actual."""
    user = get_current_user()
    if user and not user.is_superadmin:
        return st.session_state.get("empresa_id") or user.empresa_id
    return st.session_state.get("empresa_id") or st.session_state.get("nl2sql_empresa_id")


def _can_configure_connection(user) -> bool:
    """Define quién puede configurar manualmente la conexión del asistente."""
    return bool(user and user.is_superadmin)


def _get_nested_secret_value(secret_obj, path) -> str:
    """Resuelve una ruta anidada dentro de Streamlit secrets."""
    current = secret_obj
    for key in path:
        if current is None:
            return ""
        if hasattr(current, "get"):
            current = current.get(key)
        else:
            try:
                current = current[key]
            except Exception:
                return ""
    return current if isinstance(current, str) else ""


def _get_server_credential_details(key: str) -> tuple[str, str]:
    """Obtiene una credencial del servidor y la fuente, sin exponer el valor."""
    value = os.getenv(key, "")
    if value:
        return value, "env"

    aliases = {
        "NEON_DATABASE_URL": [
            (("NEON_DATABASE_URL",), "secrets.NEON_DATABASE_URL"),
            (("DATABASE_URL",), "secrets.DATABASE_URL"),
            (("connections", "neon", "url"), "secrets.connections.neon.url"),
            (("connections", "postgresql", "url"), "secrets.connections.postgresql.url"),
        ],
        "OPENAI_API_KEY": [
            (("OPENAI_API_KEY",), "secrets.OPENAI_API_KEY"),
            (("openai_api_key",), "secrets.openai_api_key"),
            (("api_key",), "secrets.api_key"),
            (("openai", "api_key"), "secrets.openai.api_key"),
            (("connections", "openai", "api_key"), "secrets.connections.openai.api_key"),
        ],
    }

    try:
        for path, source in aliases.get(key, [((key,), f"secrets.{key}")]):
            secret_value = _get_nested_secret_value(st.secrets, path)
            if secret_value:
                return secret_value, source
    except Exception:
        pass

    return "", "missing"


def _is_premium_passkey_valid() -> bool:
    """Indica si la sesión actual tiene Premium activado vía passkey."""
    return bool(st.session_state.get("passkey_valido"))


def _get_runtime_api_key_details() -> tuple[str, str]:
    """Resuelve la API key activa para el asistente sin exponer su valor."""
    if not _is_premium_passkey_valid():
        return "", "premium-locked"

    server_api, server_source = _get_server_credential_details("OPENAI_API_KEY")
    if server_api:
        return server_api, server_source

    session_api_key = st.session_state.get("openai_api_key", "")
    if isinstance(session_api_key, str) and session_api_key.strip():
        return session_api_key.strip(), "session.openai_api_key"

    return "", "missing"


def _get_server_credential(key: str) -> str:
    """Obtiene una credencial del servidor desde env o Streamlit secrets."""
    value, _source = _get_server_credential_details(key)
    return value


def _get_runtime_credentials():
    """Resuelve credenciales del motor sin exponer secretos del servidor al frontend."""
    user = get_current_user()
    model = st.session_state.get("nl2sql_model", "gpt-4o")
    server_neon = _get_server_credential("NEON_DATABASE_URL")
    runtime_api_key, _runtime_api_source = _get_runtime_api_key_details()

    if user and not _can_configure_connection(user):
        return server_neon, runtime_api_key, model

    neon_url = st.session_state.get("nl2sql_neon_url", "").strip() or server_neon
    api_key = st.session_state.get("nl2sql_api_key", "").strip() or runtime_api_key
    return neon_url, api_key, model


def _render_stats_kpi(df: pd.DataFrame):
    """
    Renderiza 1 fila estadística como tarjetas KPI agrupadas por significado.
    Más legible que una tabla horizontal con 8+ columnas.
    """
    row = df.iloc[0]
    cols = df.columns.tolist()

    def _fmt(v, is_count=False):
        if not isinstance(v, (int, float)):
            return str(v)
        if is_count:
            return f"{int(v):,}"
        return f"${v:,.2f}" if abs(v) >= 1 else f"{v:.4f}"

    # Clasificar columnas por rol estadístico
    count_kws   = ['total_factura', 'total_concepto', 'num_factura', 'num_concepto',
                   'count', 'conteo', 'n_empresas']
    central_kws = ['promedio', 'media', 'avg', 'mediana', 'median',
                   'precio_promedio', 'precio_mediana', 'moda']
    disp_kws    = ['desviacion', 'stddev', 'varianza', 'variance']
    range_kws   = ['minimo', 'min', 'maximo', 'max', 'precio_minimo', 'precio_maximo']
    pct_kws     = ['percentil', 'quartil', 'p25', 'p50', 'p75']

    def _match(c, kws): return any(k in c.lower() for k in kws)

    count_c   = [c for c in cols if _match(c, count_kws)]
    central_c = [c for c in cols if _match(c, central_kws) and c not in count_c]
    disp_c    = [c for c in cols if _match(c, disp_kws)]
    range_c   = [c for c in cols if _match(c, range_kws)]
    pct_c     = [c for c in cols if _match(c, pct_kws)]
    other_c   = [c for c in cols if c not in count_c + central_c + disp_c + range_c + pct_c]

    # ── 1. Número héroe: total de registros ──────────────────────────────
    if count_c:
        v = row[count_c[0]]
        label = count_c[0].replace('_', ' ').title()
        st.markdown(
            f"<div style='text-align:center; padding:8px 0 4px'>"
            f"<span style='font-size:2rem; font-weight:700; color:#2196F3'>"
            f"{_fmt(v, is_count=True)}</span>"
            f"<br><span style='font-size:0.85rem; color:#888'>{label}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )
        st.markdown("---")

    # ── 2. Tendencia central (promedio vs mediana con delta) ──────────────
    if central_c:
        st.markdown("##### 📍 Tendencia Central")
        ui_cols = st.columns(min(len(central_c), 4))
        vals_central = {}
        for i, c in enumerate(central_c[:4]):
            v = float(row[c])
            vals_central[c] = v
            with ui_cols[i]:
                st.metric(c.replace('_', ' ').title(), _fmt(v))

        # Insight automático promedio vs mediana
        avg_v = next((vals_central[c] for c in central_c if _match(c, ['promedio', 'media', 'avg', 'precio_promedio'])), None)
        med_v = next((vals_central[c] for c in central_c if _match(c, ['mediana', 'median', 'precio_mediana'])), None)
        if avg_v is not None and med_v is not None and med_v > 0:
            ratio = avg_v / med_v
            if ratio > 1.5:
                st.caption("⚠️ **Promedio >> Mediana**: existen facturas de alto valor que distorsionan el promedio. La mediana es más representativa del cliente típico.")
            elif ratio < 0.8:
                st.caption("ℹ️ **Promedio < Mediana**: hay facturas pequeñas o créditos que bajan el promedio.")
            else:
                st.caption("✅ **Promedio ≈ Mediana**: distribución equilibrada, sin outliers extremos.")

    # ── 3. Rango min / max ───────────────────────────────────────────────
    if range_c:
        st.markdown("##### ↕️ Rango")
        ui_cols = st.columns(min(len(range_c), 4))
        for i, c in enumerate(range_c[:4]):
            v = float(row[c])
            with ui_cols[i]:
                icon = "🔻" if _match(c, ['min', 'minimo']) else "🔺"
                st.metric(f"{icon} {c.replace('_', ' ').title()}", _fmt(v))

    # ── 4. Dispersión ────────────────────────────────────────────────────
    if disp_c:
        st.markdown("##### 📏 Dispersión")
        ui_cols = st.columns(min(len(disp_c), 3))
        for i, c in enumerate(disp_c[:3]):
            v = float(row[c])
            with ui_cols[i]:
                st.metric(c.replace('_', ' ').title(), _fmt(v))
        # Insight: CV (coef de variación) si hay promedio
        avg_v2 = next((float(row[c]) for c in central_c if _match(c, ['promedio', 'media', 'avg'])), None)
        std_v  = float(row[disp_c[0]]) if disp_c else None
        if avg_v2 and std_v and avg_v2 > 0:
            cv = std_v / avg_v2 * 100
            if cv > 100:
                st.caption(f"⚠️ **Alta variabilidad** (CV={cv:.0f}%): los montos son muy dispares entre clientes.")
            elif cv > 50:
                st.caption(f"📊 **Variabilidad moderada** (CV={cv:.0f}%): hay diferencias significativas entre facturas.")
            else:
                st.caption(f"✅ **Baja variabilidad** (CV={cv:.0f}%): los montos son relativamente homogéneos.")

    # ── 5. Percentiles (caja de distribución) ───────────────────────────
    if pct_c:
        st.markdown("##### 📊 Percentiles")
        ui_cols = st.columns(min(len(pct_c), 4))
        for i, c in enumerate(pct_c[:4]):
            v = float(row[c])
            with ui_cols[i]:
                st.metric(c.replace('_', ' ').replace('Percentil ', 'P').title(), _fmt(v))
        p25_v = next((float(row[c]) for c in pct_c if '25' in c), None)
        p75_v = next((float(row[c]) for c in pct_c if '75' in c), None)
        if p25_v is not None and p75_v is not None:
            iqr = p75_v - p25_v
            st.caption(f"📦 **Rango intercuartil (IQR):** {_fmt(iqr)} — el 50% central de las facturas está en este rango.")

    # ── 6. Otras columnas numéricas ──────────────────────────────────────
    if other_c:
        ui_cols = st.columns(min(len(other_c), 4))
        for i, c in enumerate(other_c[:4]):
            v = row[c]
            with ui_cols[i]:
                st.metric(c.replace('_', ' ').title(), _fmt(v) if isinstance(v, (int, float)) else str(v))


def _render_smart_table(df: pd.DataFrame):
    """
    Renderiza tabla inteligente: detecta columnas con valor constante
    (estadísticos globales repetidos en cada fila) y las muestra como
    resumen separado, dejando la tabla limpia solo con el detalle.
    """
    if df.empty:
        st.dataframe(df, use_container_width=True, hide_index=True)
        return

    num_cols = df.select_dtypes(include=['int64', 'float64', 'int32', 'float32']).columns.tolist()

    # ── Caso especial: 1 fila con columnas estadísticas → KPI cards ──────
    stat_kws = ['promedio', 'media', 'avg', 'mediana', 'desviacion', 'stddev',
                'minimo', 'maximo', 'percentil', 'varianza', 'precio_promedio',
                'precio_mediana', 'precio_minimo', 'precio_maximo', 'total_facturas',
                'total_conceptos', 'num_facturas', 'num_conceptos']
    if len(df) == 1 and any(any(kw in c.lower() for kw in stat_kws) for c in num_cols):
        _render_stats_kpi(df)
        return

    # Solo separar si hay más de 3 filas (con 1-2 filas no tiene sentido)
    if len(df) > 3:
        # Detectar columnas numéricas con valor constante (mismo valor en todas las filas)
        stat_keywords = ['promedio', 'media', 'avg', 'desviacion', 'stddev', 'varianza',
                         'minimo', 'maximo', 'moda', 'percentil', 'total_clientes',
                         'total_facturas', 'conteo', 'count']
        const_cols = []
        for col in num_cols:
            if df[col].nunique() == 1 and any(kw in col.lower() for kw in stat_keywords):
                const_cols.append(col)

        if const_cols:
            # Mostrar resumen de estadísticos globales como métricas
            st.markdown("**📊 Resumen estadístico global**")
            cols_ui = st.columns(min(len(const_cols), 4))
            for i, col in enumerate(const_cols):
                with cols_ui[i % min(len(const_cols), 4)]:
                    v = df[col].iloc[0]
                    label = col.replace('_', ' ').title()
                    if isinstance(v, (int, float)):
                        if any(kw in col.lower() for kw in ['total_clientes', 'conteo', 'count', 'total_facturas']):
                            st.metric(label, f"{v:,.0f}")
                        elif abs(v) >= 100:
                            st.metric(label, f"${v:,.2f}")
                        else:
                            st.metric(label, f"{v:,.2f}")
                    else:
                        st.metric(label, str(v))

            # Si hay más de 4, mostrar siguiente fila
            if len(const_cols) > 4:
                cols_ui2 = st.columns(min(len(const_cols) - 4, 4))
                for i, col in enumerate(const_cols[4:8]):
                    with cols_ui2[i]:
                        v = df[col].iloc[0]
                        label = col.replace('_', ' ').title()
                        if isinstance(v, (int, float)) and abs(v) >= 100:
                            st.metric(label, f"${v:,.2f}")
                        else:
                            st.metric(label, f"{v:,.2f}" if isinstance(v, (int, float)) else str(v))

            st.markdown("---")
            st.markdown("**📋 Detalle por registro**")
            # Tabla solo con columnas variables
            detail_cols = [c for c in df.columns if c not in const_cols]
            display_df = df[detail_cols] if detail_cols else df
        else:
            display_df = df
    else:
        display_df = df

    st.dataframe(_format_numeric_display_dataframe(display_df), use_container_width=True, hide_index=True)


def _build_numeric_column_config(df: pd.DataFrame) -> dict:
    """Construye un formato consistente para números en tablas del asistente."""
    numeric_cols = df.select_dtypes(include=['number']).columns
    count_keywords = ['num_', 'count', 'cantidad', 'total_clientes', 'total_facturas', 'conteo', 'registros', 'facturas', 'ranking']
    money_keywords = [
        'total', 'monto', 'facturacion', 'venta', 'ventas', 'ventas_mes', 'importe',
        'saldo', 'mxn', 'compra', 'cobrado', 'promedio', 'media', 'desviacion',
        'minimo', 'maximo', 'precio', 'mediana', 'percentil', 'acumulado',
        'promedio_movil', 'monetario', 'ingreso', 'valor'
    ]

    col_config = {}
    for col in numeric_cols:
        is_count = any(kw in col.lower() for kw in count_keywords)
        if 'pct' in col.lower() or 'porcentaje' in col.lower() or col.lower().endswith('_pct') or '%' in col:
            col_config[col] = st.column_config.NumberColumn(format="%,.1f%%")
        elif not is_count and any(kw in col.lower() for kw in money_keywords):
            col_config[col] = st.column_config.NumberColumn(format="$%,.2f")
        elif is_count:
            col_config[col] = st.column_config.NumberColumn(format="%,.0f")
        else:
            col_config[col] = st.column_config.NumberColumn(format="%,.2f")

    return col_config


def _coerce_numeric_like_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Convierte columnas numéricas serializadas como texto para habilitar sort y formato correcto."""
    if df is None or df.empty:
        return df

    count_keywords = ['num_', 'count', 'cantidad', 'total_clientes', 'total_facturas', 'conteo', 'registros', 'facturas', 'ranking']
    money_keywords = [
        'total', 'monto', 'facturacion', 'venta', 'ventas', 'ventas_mes', 'importe',
        'saldo', 'mxn', 'compra', 'cobrado', 'promedio', 'media', 'desviacion',
        'minimo', 'maximo', 'precio', 'mediana', 'percentil', 'acumulado',
        'promedio_movil', 'monetario', 'ingreso', 'valor'
    ]

    converted_df = df.copy()
    for col in converted_df.columns:
        if pd.api.types.is_numeric_dtype(converted_df[col]):
            continue

        col_lower = str(col).lower()
        looks_numeric = any(kw in col_lower for kw in count_keywords + money_keywords) or \
                        'pct' in col_lower or 'porcentaje' in col_lower or col_lower.endswith('_pct')
        if not looks_numeric:
            continue

        raw_series = converted_df[col].astype(str).str.strip()
        cleaned_series = (
            raw_series
            .str.replace("$", "", regex=False)
            .str.replace(",", "", regex=False)
            .str.replace("%", "", regex=False)
            .replace({"": None, "None": None, "nan": None, "NaN": None, "NULL": None, "null": None})
        )
        numeric_series = pd.to_numeric(cleaned_series, errors='coerce')

        non_null_count = cleaned_series.notna().sum()
        if non_null_count == 0:
            continue

        parse_ratio = numeric_series.notna().sum() / non_null_count
        if parse_ratio < 0.8:
            continue

        # Usar dtypes numpy (float64) para que select_dtypes(include='number') los detecte
        converted_df[col] = numeric_series.astype('float64')

    return converted_df


def _format_numeric_display_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Aplica formato visible a columnas numéricas para tablas del asistente.

    Itera sobre TODOS los nombres de columna (no solo select_dtypes) para que
    columnas Decimal de psycopg2 –almacenadas como object– también reciban formato.
    """
    count_keywords = ['num_', 'count', 'cantidad', 'total_clientes', 'total_facturas', 'conteo', 'registros', 'facturas', 'ranking']
    money_keywords = [
        'total', 'monto', 'facturacion', 'venta', 'ventas', 'ventas_mes', 'importe',
        'saldo', 'mxn', 'compra', 'cobrado', 'promedio', 'media', 'desviacion',
        'minimo', 'maximo', 'precio', 'mediana', 'percentil', 'acumulado',
        'promedio_movil', 'monetario', 'ingreso', 'valor'
    ]

    display_df = df.copy()

    for col in display_df.columns:
        col_lower = col.lower()
        is_count   = any(kw in col_lower for kw in count_keywords)
        is_percent = 'pct' in col_lower or 'porcentaje' in col_lower or col_lower.endswith('_pct') or '%' in col
        is_money   = not is_count and any(kw in col_lower for kw in money_keywords)

        if not (is_count or is_percent or is_money):
            # Solo formatear si la columna ya es numérica
            if not pd.api.types.is_numeric_dtype(display_df[col]):
                continue

        def _safe_fmt(value, fmt):
            try:
                v = float(value)
                if pd.isna(v):
                    return ""
                return fmt(v)
            except (ValueError, TypeError):
                return str(value) if value is not None else ""

        if is_percent:
            display_df[col] = display_df[col].map(
                lambda v: _safe_fmt(v, lambda x: f"{round(x, 2):,.2f}%")
            )
        elif is_money:
            display_df[col] = display_df[col].map(
                lambda v: _safe_fmt(v, lambda x: f"${x:,.2f}")
            )
        elif is_count:
            display_df[col] = display_df[col].map(
                lambda v: _safe_fmt(v, lambda x: f"{int(x):,}")
            )
        else:
            display_df[col] = display_df[col].map(
                lambda v: _safe_fmt(v, lambda x: f"{x:,.2f}")
            )

    return display_df


def _render_kpi_tab(df: pd.DataFrame):
    """
    Tab KPIs: calcula y muestra métricas clave de cualquier DataFrame.
    - Formato kpi/valor/unidad → cards ejecutivas
    - 1 fila estadística       → usa _render_stats_kpi
    - Multicol numérica        → suma, conteo, promedio, top/bottom
    """
    if df.empty:
        st.info("Sin datos para calcular KPIs.")
        return

    if {"ventas", "promedio_movil_3m"}.issubset(df.columns):
        st.markdown("##### 📊 Resumen global")
        total_ventas = float(df["ventas"].sum())
        promedio_ventas = float(df["ventas"].mean())
        ultimo_promedio_movil = float(df["promedio_movil_3m"].dropna().iloc[-1]) if not df["promedio_movil_3m"].dropna().empty else 0.0

        cols_ui = st.columns(4)
        with cols_ui[0]:
            st.metric("📋 Registros", f"{len(df):,}")
        with cols_ui[1]:
            st.metric("Σ Ventas", f"${total_ventas:,.2f}", f"Prom: ${promedio_ventas:,.2f}")
        with cols_ui[2]:
            st.metric("Promedio mensual", f"${promedio_ventas:,.2f}")
        with cols_ui[3]:
            st.metric("Último Promedio Móvil 3M", f"${ultimo_promedio_movil:,.2f}")

        if "mes" in df.columns:
            st.markdown("---")
            top_n = df.nlargest(3, "ventas")[["mes", "ventas"]]
            bot_n = df.nsmallest(3, "ventas")[["mes", "ventas"]]

            col_top, col_bot = st.columns(2)
            with col_top:
                st.markdown("##### 🏆 Top 3 por Ventas")
                for _, row in top_n.iterrows():
                    st.markdown(f"**{row['mes']}** — ${float(row['ventas']):,.2f}")
            with col_bot:
                st.markdown("##### 🔻 Menor 3 por Ventas")
                for _, row in bot_n.iterrows():
                    st.markdown(f"**{row['mes']}** — ${float(row['ventas']):,.2f}")
        return

    cols_lower = [c.lower() for c in df.columns]

    # ── Caso especial: resultado con columnas kpi + valor + unidad ────────
    has_kpi_col   = any(c in ('kpi', 'indicador', 'metrica', 'nombre') for c in cols_lower)
    has_valor_col = any(c in ('valor', 'value') for c in cols_lower)
    if has_kpi_col and has_valor_col:
        kpi_col   = df.columns[cols_lower.index(next(c for c in cols_lower if c in ('kpi', 'indicador', 'metrica', 'nombre')))]
        valor_col = df.columns[cols_lower.index(next(c for c in cols_lower if c in ('valor', 'value')))]
        unidad_col = next((df.columns[i] for i, c in enumerate(cols_lower) if c in ('unidad', 'unit', 'tipo')), None)

        ICONS = {
            'facturac': '💰', 'venta': '💰', 'mxn': '💰',
            'factura': '📄', 'ticket': '🎫',
            'cliente': '👥', 'crecimiento': '📈', '%': '📊',
        }

        def _kpi_icon(name: str) -> str:
            nl = name.lower()
            for k, ico in ICONS.items():
                if k in nl:
                    return ico
            return '📊'

        def _fmt_val(raw_val, unidad: str = '') -> str:
            try:
                v = float(str(raw_val).replace(',', ''))
            except (ValueError, TypeError):
                return str(raw_val)
            import math
            if math.isnan(v) or math.isinf(v):
                return "—"
            u = (unidad or '').lower()
            if 'mxn' in u or 'facturaci' in u:
                return f"${v:,.2f}"
            if '%' in u or 'crecimiento' in u:
                return f"{v:,.1f}%"
            if 'factura' in u or 'cliente' in u or 'registro' in u:
                return f"{int(v):,}"
            if abs(v) >= 1000:
                return f"${v:,.2f}"
            return f"{v:,.2f}"

        rows = df[[kpi_col, valor_col] + ([unidad_col] if unidad_col else [])].values.tolist()

        # Render en filas de 3 o 4 tarjetas
        n_per_row = 4 if len(rows) >= 6 else 3
        for i in range(0, len(rows), n_per_row):
            chunk = rows[i:i + n_per_row]
            ui_cols = st.columns(len(chunk))
            for j, row in enumerate(chunk):
                nombre = str(row[0])
                raw    = row[1]
                unidad = str(row[2]) if unidad_col else ''
                ico    = _kpi_icon(nombre)
                val_fmt = _fmt_val(raw, unidad)
                with ui_cols[j]:
                    st.metric(f"{ico} {nombre}", val_fmt)
        return
        return

    # Caso especial: 1 fila con columnas estadísticas
    stat_kws = ['promedio', 'media', 'avg', 'mediana', 'desviacion', 'stddev',
                'minimo', 'maximo', 'percentil', 'varianza', 'precio_promedio',
                'precio_mediana', 'precio_minimo', 'precio_maximo', 'total_facturas',
                'total_conceptos', 'num_facturas', 'num_conceptos']
    num_cols = df.select_dtypes(include=['int64', 'float64', 'int32', 'float32']).columns.tolist()
    if len(df) == 1 and any(any(kw in c.lower() for kw in stat_kws) for c in num_cols):
        _render_stats_kpi(df)
        return

    # ── KPIs calculados desde el DataFrame ───────────────────────────────
    count_kws  = ['num_', 'count', 'cantidad', 'facturas', 'conteo', 'registros']
    money_kws  = ['total', 'monto', 'facturacion', 'venta', 'importe', 'saldo',
                  'mxn', 'compra', 'cobrado', 'monetario', 'ventas']
    pct_kws    = ['pct', 'porcentaje', 'crecimiento', 'tasa']

    def _is_count(c): return any(k in c.lower() for k in count_kws)
    def _is_money(c): return any(k in c.lower() for k in money_kws)
    def _is_pct(c):   return any(k in c.lower() for k in pct_kws)

    def _fmt(v, col=""):
        if not isinstance(v, (int, float)): return str(v)
        if _is_count(col): return f"{int(v):,}"
        if _is_pct(col):   return f"{v:,.1f}%"
        if _is_money(col) or abs(v) >= 1000: return f"${v:,.2f}"
        return f"{v:,.2f}"

    str_cols = df.select_dtypes(include=['object']).columns.tolist()

    # ── Fila 1: métricas globales ───────────────────────────────────────
    st.markdown("##### 📊 Resumen global")
    kpi_items = []

    # Número de registros siempre
    kpi_items.append(("📋 Registros", f"{len(df):,}", None))

    # Por columna numérica: suma si dinero/count, promedio si otro
    for col in num_cols[:4]:
        total_val = df[col].sum()
        avg_val   = df[col].mean()
        if _is_count(col):
            kpi_items.append((f"Σ {col.replace('_',' ').title()}", f"{int(total_val):,}", None))
        elif _is_money(col):
            kpi_items.append((f"Σ {col.replace('_',' ').title()}", f"${total_val:,.2f}", f"Prom: ${avg_val:,.2f}"))
        elif _is_pct(col):
            kpi_items.append((f"Prom {col.replace('_',' ').title()}", f"{avg_val:,.1f}%", None))
        else:
            kpi_items.append((f"Σ {col.replace('_',' ').title()}", _fmt(total_val, col), f"Prom: {_fmt(avg_val, col)}"))

    cols_ui = st.columns(min(len(kpi_items), 4))
    for i, (label, val, delta) in enumerate(kpi_items[:4]):
        with cols_ui[i]:
            st.metric(label, val, delta)
    if len(kpi_items) > 4:
        cols_ui2 = st.columns(min(len(kpi_items) - 4, 4))
        for i, (label, val, delta) in enumerate(kpi_items[4:8]):
            with cols_ui2[i]:
                st.metric(label, val, delta)

    # ── Fila 2: top / bottom ────────────────────────────────────────────
    if str_cols and num_cols:
        st.markdown("---")
        dim_col = str_cols[0]
        val_col = next((c for c in num_cols if _is_money(c)), num_cols[0])

        top_n = df.nlargest(3, val_col)[[dim_col, val_col]]
        bot_n = df.nsmallest(3, val_col)[[dim_col, val_col]]

        col_top, col_bot = st.columns(2)
        with col_top:
            st.markdown(f"##### 🏆 Top 3 por {val_col.replace('_', ' ').title()}")
            for _, row in top_n.iterrows():
                st.markdown(
                    f"**{row[dim_col]}** — {_fmt(float(row[val_col]), val_col)}"
                )
        with col_bot:
            st.markdown(f"##### 🔻 Menor 3 por {val_col.replace('_', ' ').title()}")
            for _, row in bot_n.iterrows():
                st.markdown(
                    f"**{row[dim_col]}** — {_fmt(float(row[val_col]), val_col)}"
                )

        # ── Concentración: % que representa el top 1 ────────────────────
        if len(df) > 1:
            total_sum = df[val_col].sum()
            top1_val  = df[val_col].max()
            if total_sum > 0:
                pct_top1 = top1_val / total_sum * 100
                top1_name = df.loc[df[val_col].idxmax(), dim_col]
                st.markdown("---")
                if pct_top1 > 30:
                    st.warning(f"⚠️ **{top1_name}** concentra el **{pct_top1:.1f}%** del total — riesgo de dependencia.")
                else:
                    st.info(f"ℹ️ **{top1_name}** es el principal con **{pct_top1:.1f}%** del total.")


def _render_plotly_chart_and_save(fig, use_container_width=True):
    """Renderiza figura de Plotly y la guarda en session_state para exportación."""
    # Guardar en session_state para uso posterior (ej. PDF)
    st.session_state['last_plotly_fig'] = fig
    # Renderizar normalmente con Streamlit
    st.plotly_chart(fig, use_container_width=use_container_width)

def _auto_chart(df: pd.DataFrame, chart_type: str, question: str, chart_spec: dict = None):
    """
    Genera gráficas inteligentes basadas en especificaciones de la IA.

    Args:
        df: DataFrame con resultados
        chart_type: Tipo de gráfica (bar, hbar, line, area, pie, donut,
                     scatter, treemap, funnel, stacked_bar, grouped_bar,
                     waterfall, metric, table, stats_summary, box,
                     histogram, gauge, heatmap)
        question: Pregunta original para título
        chart_spec: Especificaciones detalladas de la gráfica generadas por IA
                    {x, y, color, title, orientation, labels, sort, top_n, ...}
    """
    if not PLOTLY_AVAILABLE or df.empty:
        df = _coerce_numeric_like_columns(df)
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config=_build_numeric_column_config(df),
        )
        return

    # ── Detección temprana: formato kpi/valor/unidad → dashboard de cards ──
    cols_lower = [c.lower() for c in df.columns]
    _has_kpi   = any(c in ('kpi', 'indicador', 'metrica', 'nombre') for c in cols_lower)
    _has_valor = any(c in ('valor', 'value') for c in cols_lower)
    if _has_kpi and _has_valor:
        _render_kpi_tab(df)
        return

    spec = chart_spec or {}
    
    # DEBUG: Log de chart_spec recibido
    logger.info(f"📊 Renderizando gráfico tipo '{chart_type}' con spec: {spec}")
    
    num_cols = df.select_dtypes(include=['int64', 'float64', 'int32', 'float32']).columns.tolist()
    cat_cols = df.select_dtypes(include=['object', 'datetime64']).columns.tolist()

    # Detectar columnas temporales
    temporal_cols = [col for col in df.columns if any(
        time_word in str(col).lower() 
        for time_word in ['mes', 'fecha', 'date', 'time', 'periodo', 'trimestre', 'año', 'year', 'month']
    )]
    # También incluir columnas con dtype datetime
    for col in df.columns:
        if df[col].dtype in ['datetime64[ns]', 'datetime64'] and col not in temporal_cols:
            temporal_cols.append(col)

    # Auto-detect mejores columnas si spec no las indica
    x_col = spec.get("x") or (cat_cols[0] if cat_cols else df.columns[0])
    y_col = spec.get("y") or (num_cols[0] if num_cols else df.columns[-1])
    color_col = spec.get("color")
    title = spec.get("title") or question[:100]
    top_n = spec.get("top_n", 30)
    sort_order = spec.get("sort")  # "asc" | "desc" | None
    user_orientation = spec.get("orientation", "").lower()  # "h"/"horizontal" o "v"/"vertical"
    
    # DEBUG: Log de orientación detectada
    if user_orientation:
        logger.info(f"🔄 Orientación especificada por usuario: '{user_orientation}'")

    # Validar que columnas existen
    if x_col not in df.columns:
        x_col = cat_cols[0] if cat_cols else df.columns[0]
    if y_col not in df.columns:
        y_col = num_cols[0] if num_cols else df.columns[-1]
    if color_col and color_col not in df.columns:
        color_col = None

    if {"ventas", "promedio_movil_3m"}.issubset(df.columns) and "mes" in df.columns:
        combo_df = df.copy()
        fig = go.Figure()
        fig.add_trace(
            go.Bar(
                x=combo_df["mes"],
                y=combo_df["ventas"],
                name="Ventas",
                marker_color="#4C78A8",
                hovertemplate="%{x}<br>Ventas: $%{y:,.2f}<extra></extra>",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=combo_df["mes"],
                y=combo_df["promedio_movil_3m"],
                name="Promedio móvil 3M",
                mode="lines+markers",
                line=dict(color="#F58518", width=3),
                marker=dict(size=7),
                hovertemplate="%{x}<br>Promedio móvil 3M: $%{y:,.2f}<extra></extra>",
            )
        )
        fig.update_layout(
            title=title,
            xaxis_title="mes",
            yaxis_title="MXN",
            xaxis_tickangle=-45,
            legend_title_text="Serie",
            hovermode="x unified",
        )
        _render_plotly_chart_and_save(fig, use_container_width=True)
        return

    # --- Auto-detect estadísticas ---
    stat_keywords = ['media', 'mediana', 'promedio', 'desviacion', 'stddev',
                     'varianza', 'percentil', 'minimo', 'maximo', 'moda']
    is_stats_query = any(kw in question.lower() for kw in ['estadistic', 'media', 'mediana',
                                                            'desviacion', 'promedio', 'percentil'])
    has_stat_cols = any(any(kw in col.lower() for kw in stat_keywords) for col in df.columns)
    
    # Detectar si el usuario pidió gráficas explícitamente
    user_wants_chart = any(kw in question.lower() for kw in [
        'grafico', 'gráfico', 'graficos', 'gráficos', 'grafica', 'gráfica',
        'graficas', 'gráficas', 'con grafic', 'con gráfic', 'chart', 
        'visualiz', 'dibuja', 'muestra en',
        'barras', 'barra', 'vertical', 'horizontal', 'dona', 'donut',
        'pay', 'pastel', 'pie', 'linea', 'línea', 'area', 'área',
        'scatter', 'pareto', 'treemap', 'heatmap', 'funnel',
        'reporte', 'report', 'ceo', 'cfo', 'ejecutivo', 'auditoria', 'auditoría'
    ])
    
    # También considerar que la IA ya asignó un tipo visual (no table/metric/stats)
    ai_assigned_visual = chart_type not in ("table", "stats_summary", "metric", "")

    logger.info(f"📊 _auto_chart: chart_type_in={chart_type}, rows={len(df)}, num_cols={len(num_cols)}, user_wants_chart={user_wants_chart}, ai_visual={ai_assigned_visual}")
    
    # Si es consulta estadística con 1 fila → forzar SIEMPRE stats_summary
    # (un scatter/line de 1 fila con columnas desviacion/percentil no tiene sentido)
    # EXCEPTO si el usuario explícitamente pidió gráfica/visualización
    if len(df) == 1 and len(num_cols) >= 3 and has_stat_cols:
        if not user_wants_chart:
            # IA puede haber asignado "line", "scatter", etc. — ignorarla aquí
            chart_type = "stats_summary"
            logger.info("📊 Forzando stats_summary (1 fila con cols estadísticas, sin petición de gráfica)")
        else:
            # Usuario pidió gráficas con 1 fila → bar chart de las columnas numéricas
            chart_type = "bar"
            logger.info(f"📊 Forzando bar chart para 1 fila estadística (usuario quiere chart)")
    # Si es stats por pregunta (no por columnas) y 1 fila
    elif len(df) == 1 and len(num_cols) >= 3 and is_stats_query:
        if not user_wants_chart and not ai_assigned_visual:
            chart_type = "stats_summary"
        elif (user_wants_chart or ai_assigned_visual) and chart_type in ("table", "stats_summary", "metric"):
            chart_type = "bar"
            logger.info(f"📊 Forzando bar chart para 1 fila con {len(num_cols)} columnas numéricas")
    # Si tiene varias filas con columnas estadísticas → aún puede ser stats o box
    elif len(df) > 1 and has_stat_cols and chart_type in ("table", "metric"):
        if not user_wants_chart and not ai_assigned_visual:
            chart_type = "stats_summary"
    # Si 1 fila y numéricos pero NO stats → metric cards o bar
    elif len(df) == 1 and len(num_cols) >= 1 and chart_type not in ("stats_summary", "gauge"):
        if not user_wants_chart and not ai_assigned_visual:
            chart_type = "metric"
        elif (user_wants_chart or ai_assigned_visual) and chart_type in ("table", "metric"):
            chart_type = "bar"
            logger.info(f"📊 Forzando bar chart para 1 fila (user/ai quiere chart)")
    if len(df) <= 2 and not num_cols:
        chart_type = "table"
    
    logger.info(f"📊 _auto_chart: chart_type_final={chart_type}")
    logger.info(f"📊 _auto_chart: cat_cols={cat_cols}, num_cols={num_cols}, x_col={x_col}, y_col={y_col}")

    # --- FIX CRÍTICO: Para pie/donut/treemap/funnel, x_col debe ser categórica ---
    # Si x_col es numérica (ej: forma_pago=3,99) pero se usa como nombres/categorías,
    # convertirla a string para que Plotly la trate como categórica
    if chart_type in ("pie", "donut", "treemap", "funnel") and x_col in num_cols:
        logger.info(f"📊 FIX: Convirtiendo x_col '{x_col}' de numérica a categórica para {chart_type}")
        df[x_col] = df[x_col].astype(str)
        # Actualizar listas de columnas
        num_cols = [c for c in num_cols if c != x_col]
        cat_cols = [x_col] + [c for c in cat_cols if c != x_col]
        logger.info(f"📊 FIX resultado: cat_cols={cat_cols}, num_cols={num_cols}")

    # Para series temporales, NO limitar filas (necesitamos todos los periodos)
    # y NO ordenar por valor (mantener orden cronológico)
    is_x_temporal = x_col in temporal_cols or df[x_col].dtype in ['datetime64[ns]', 'datetime64']

    # Si color_col o cualquier otra columna es temporal (ej: x=cliente, color=mes),
    # tampoco limitar — un "año" implica 12 meses y head(top_n) los cortaría
    is_any_temporal = is_x_temporal or (
        color_col and (
            color_col in temporal_cols or
            (color_col in df.columns and df[color_col].dtype in ['datetime64[ns]', 'datetime64'])
        )
    ) or any(
        c in temporal_cols or df[c].dtype in ['datetime64[ns]', 'datetime64']
        for c in df.columns
    )

    # Preparar subset: datos con dimensión temporal usan todas las filas; otros usan top_n
    if is_any_temporal:
        plot_df = df.copy()
    else:
        plot_df = df.head(top_n).copy()

    if not is_any_temporal:
        # Solo ordenar si NO hay ninguna dimensión temporal
        if sort_order == "desc" and y_col in plot_df.columns:
            plot_df = plot_df.sort_values(y_col, ascending=False)
        elif sort_order == "asc" and y_col in plot_df.columns:
            plot_df = plot_df.sort_values(y_col, ascending=True)
    else:
        # Si hay dimensión temporal, ordenar por la columna temporal dominante
        # Prioridad: x_col temporal > color_col temporal > cualquier temporal
        _temporal_sort_col = (
            x_col if is_x_temporal else
            (color_col if color_col and color_col in temporal_cols else
             next((c for c in df.columns if c in temporal_cols), x_col))
        )
        # Detectar etiquetas "Mes YYYY" (ej: "Ene 2025") generadas por el post-procesador
        _MES_NUM = {
            'Ene': 1, 'Feb': 2, 'Mar': 3, 'Abr': 4, 'May': 5, 'Jun': 6,
            'Jul': 7, 'Ago': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dic': 12,
        }
        _sample = plot_df[_temporal_sort_col].dropna().astype(str).head(5)
        _is_mes_label = _sample.str.match(
            r'^(Ene|Feb|Mar|Abr|May|Jun|Jul|Ago|Sep|Oct|Nov|Dic)\s+\d{4}$'
        ).any()
        if _is_mes_label:
            def _mes_sort_key(s):
                parts = str(s).split()
                if len(parts) == 2:
                    return int(parts[1]) * 12 + _MES_NUM.get(parts[0], 0)
                return 0
            plot_df = plot_df.iloc[plot_df[_temporal_sort_col].map(_mes_sort_key).argsort().values]
        elif _temporal_sort_col in plot_df.columns:
            plot_df = plot_df.sort_values(_temporal_sort_col, ascending=True)

    # --- Helper: truncar etiquetas largas y auto-switch a horizontal ---
    def _smart_label_prep(df_in, label_col, max_chars=45):
        """Trunca etiquetas largas y decide si conviene horizontal."""
        df_out = df_in.copy()
        if label_col in df_out.columns and df_out[label_col].dtype == "object":
            max_len = df_out[label_col].astype(str).str.len().max()
            avg_len = df_out[label_col].astype(str).str.len().mean()
            n_rows = len(df_out)
            # Truncar etiquetas largas
            df_out[label_col] = df_out[label_col].astype(str).apply(
                lambda s: s[:max_chars] + "…" if len(s) > max_chars else s
            )
            # Auto-switch a horizontal si muchas filas o labels largos
            use_hbar = (max_len > 25 and n_rows > 3) or (avg_len > 18 and n_rows > 5) or n_rows > 12
            # Altura dinámica
            height = max(400, min(n_rows * 38, 900)) if use_hbar else None
            return df_out, use_hbar, height
        return df_out, False, None

    try:
        # --- METRIC CARDS ---
        if chart_type == "metric" and num_cols:
            cols = st.columns(min(len(num_cols), 4))
            for i, col_name in enumerate(num_cols[:4]):
                value = df[col_name].iloc[0]
                with cols[i]:
                    if isinstance(value, (int, float)):
                        if abs(value) >= 1000:
                            st.metric(col_name, f"${value:,.2f}")
                        else:
                            st.metric(col_name, f"{value:,.2f}")
                    else:
                        st.metric(col_name, str(value))
            return

        # --- STATS SUMMARY (resumen estadístico visual) ---
        if chart_type == "stats_summary" and num_cols:
            _render_stats_chart(df, num_cols, cat_cols, title, spec)
            return

        # --- BOX PLOT ---
        if chart_type == "box" and num_cols:
            if cat_cols:
                fig = px.box(
                    plot_df, x=x_col, y=y_col,
                    title=title,
                    color=x_col,
                    color_discrete_sequence=CHART_COLORS,
                    points="outliers",
                )
            else:
                fig = px.box(
                    plot_df, y=y_col,
                    title=title,
                    color_discrete_sequence=CHART_COLORS,
                    points="outliers",
                )
            fig.update_layout(showlegend=False)
            _render_plotly_chart_and_save(fig, use_container_width=True)
            return

        # --- HISTOGRAM ---
        if chart_type == "histogram" and num_cols:
            fig = px.histogram(
                plot_df, x=y_col,
                title=title,
                nbins=spec.get("bins", 20),
                color_discrete_sequence=[CHART_COLORS[0]],
                marginal="box",
            )
            fig.update_layout(bargap=0.05)
            _render_plotly_chart_and_save(fig, use_container_width=True)
            return

        # --- GAUGE (indicador tipo velocímetro) ---
        if chart_type == "gauge" and num_cols:
            value = df[num_cols[0]].iloc[0]
            max_val = spec.get("max_val", value * 1.5 if value > 0 else 100)
            fig = go.Figure(go.Indicator(
                mode="gauge+number+delta",
                value=value,
                title={"text": title},
                gauge={
                    "axis": {"range": [0, max_val]},
                    "bar": {"color": "#2196F3"},
                    "steps": [
                        {"range": [0, max_val*0.33], "color": "#E8F5E9"},
                        {"range": [max_val*0.33, max_val*0.66], "color": "#FFF9C4"},
                        {"range": [max_val*0.66, max_val], "color": "#FFEBEE"},
                    ],
                    "threshold": {
                        "line": {"color": "red", "width": 4},
                        "thickness": 0.75,
                        "value": max_val * 0.8,
                    },
                },
            ))
            fig.update_layout(height=300)
            _render_plotly_chart_and_save(fig, use_container_width=True)
            return

        # --- HEATMAP ---
        if chart_type == "heatmap" and num_cols and len(cat_cols) >= 2:
            pivot_df = plot_df.pivot_table(
                index=cat_cols[0], columns=cat_cols[1],
                values=y_col, aggfunc="sum"
            ).fillna(0)
            fig = px.imshow(
                pivot_df,
                title=title,
                color_continuous_scale="RdYlGn",
                text_auto=".0f",
                aspect="auto",
            )
            _render_plotly_chart_and_save(fig, use_container_width=True)
            return

        # --- BAR CHART ESPECIAL: 1 fila con múltiples métricas (reporte ejecutivo) ---
        if chart_type == "bar" and len(df) == 1 and len(num_cols) >= 2:
            logger.info(f"📊 Generando bar chart transpuesto para 1 fila con {len(num_cols)} métricas")
            # Transponer: cada columna numérica se convierte en una barra
            metrics_data = []
            for col in num_cols:
                val = df[col].iloc[0]
                if isinstance(val, (int, float)):
                    label = col.replace('_', ' ').title()
                    metrics_data.append({"Métrica": label, "Valor": val})
            
            if metrics_data:
                import pandas as pd
                metrics_df = pd.DataFrame(metrics_data)
                fig = px.bar(
                    metrics_df, x="Métrica", y="Valor",
                    title=title,
                    color="Métrica",
                    color_discrete_sequence=CHART_COLORS,
                    text_auto=True,
                )
                fig.update_layout(
                    showlegend=False,
                    xaxis_tickangle=-25,
                    margin=dict(l=10, r=40, t=50, b=20),
                )
                fig.update_traces(textposition="outside", texttemplate="%{y:,.0f}")
                _render_plotly_chart_and_save(fig, use_container_width=True)
                return

        # --- BAR (vertical) — auto-switch a horizontal si labels largos ---
        if chart_type == "bar" and num_cols:
            # Detectar si X es temporal (evitar horizontal para series temporales)
            is_temporal = (
                x_col in temporal_cols or 
                df[x_col].dtype in ['datetime64[ns]', 'datetime64'] or
                any(kw in str(x_col).lower() for kw in ['mes', 'fecha', 'date', 'time', 'periodo', 'trimestre'])
            )
            
            bar_df, use_hbar, dyn_height = _smart_label_prep(plot_df, x_col)
            
            # Respetar orientación del usuario si la especifica
            if user_orientation in ['h', 'horizontal']:
                use_hbar = True
            elif user_orientation in ['v', 'vertical']:
                use_hbar = False
            # No usar horizontal para series temporales (solo si usuario no especificó)
            elif is_temporal:
                use_hbar = False
            
            if use_hbar:
                # Cambiar a horizontal para legibilidad
                bar_df = bar_df.sort_values(y_col, ascending=True)
                fig = px.bar(
                    bar_df, x=y_col, y=x_col,
                    title=title,
                    orientation="h",
                    color=color_col or y_col,
                    color_continuous_scale="Viridis" if not color_col else None,
                    color_discrete_sequence=CHART_COLORS if color_col else None,
                )
                fig.update_traces(texttemplate="")
                fig.update_layout(
                    height=dyn_height,
                    yaxis=dict(autorange="reversed", tickfont=dict(size=11)),
                    showlegend=bool(color_col),
                    margin=dict(l=10, r=40, t=50, b=20),
                )
                # Si hay color_col (barras apiladas/agrupadas), anotar total por fila
                if color_col:
                    _bar_totals = bar_df.groupby(x_col, sort=False)[y_col].sum()
                    for cat, total in _bar_totals.items():
                        fig.add_annotation(
                            x=total, y=cat,
                            text=f"${total:,.0f}" if total >= 1000 else f"{total:,.2f}",
                            showarrow=False, xshift=5, xanchor="left",
                            font=dict(size=11, color="white"),
                        )
                else:
                    fig.update_traces(textposition="outside", texttemplate="%{x:,.0f}")
            else:
                fig = px.bar(
                    bar_df, x=x_col, y=y_col,
                    title=title,
                    color=color_col or y_col,
                    color_continuous_scale="Viridis" if not color_col else None,
                    color_discrete_sequence=CHART_COLORS if color_col else None,
                )
                fig.update_traces(texttemplate="")
                # Formatear eje X para fechas
                if is_temporal:
                    fig.update_xaxes(tickformat="%b %Y", tickangle=-45)
                else:
                    fig.update_layout(xaxis_tickangle=-45)
                fig.update_layout(showlegend=bool(color_col))
                # Si hay color_col (múltiples series), anotar total por nodo
                if color_col:
                    _bar_totals = bar_df.groupby(x_col, sort=False)[y_col].sum()
                    for cat, total in _bar_totals.items():
                        fig.add_annotation(
                            x=cat, y=total,
                            text=f"${total:,.0f}" if total >= 1000 else f"{total:,.2f}",
                            showarrow=False, yshift=10, yanchor="bottom",
                            font=dict(size=11, color="white"),
                        )
                else:
                    fig.update_traces(textposition="outside", texttemplate="%{y:,.0f}")
            _render_plotly_chart_and_save(fig, use_container_width=True)
            return

        # --- HBAR (horizontal) ---
        if chart_type == "hbar" and num_cols:
            hbar_df, _, dyn_height = _smart_label_prep(plot_df, x_col)
            if not dyn_height:
                dyn_height = max(400, min(len(hbar_df) * 38, 900))
            
            # Respetar orientación del usuario si la especifica
            force_vertical = user_orientation in ['v', 'vertical']
            
            if force_vertical:
                # Usuario pidió vertical, renderizar como bar vertical
                fig = px.bar(
                    hbar_df, x=x_col, y=y_col,
                    title=title,
                    color=color_col or y_col,
                    color_continuous_scale="Viridis" if not color_col else None,
                    color_discrete_sequence=CHART_COLORS if color_col else None,
                    text_auto=True,
                )
                fig.update_layout(xaxis_tickangle=-45, showlegend=bool(color_col))
                fig.update_traces(textposition="outside", texttemplate="%{y:,.0f}")
            else:
                # Horizontal por defecto
                fig = px.bar(
                    hbar_df, x=y_col, y=x_col,
                    title=title,
                    orientation="h",
                    color=color_col or y_col,
                    color_continuous_scale="Viridis" if not color_col else None,
                    text_auto=True,
                )
                fig.update_layout(
                    height=dyn_height,
                    yaxis=dict(autorange="reversed", tickfont=dict(size=11)),
                    showlegend=bool(color_col),
                    margin=dict(l=10, r=40, t=50, b=20),
                )
                fig.update_traces(textposition="outside", texttemplate="%{x:,.0f}")
            _render_plotly_chart_and_save(fig, use_container_width=True)
            return

        # --- STACKED BAR ---
        if chart_type == "stacked_bar" and color_col and num_cols:
            sb_df, use_hbar, dyn_height = _smart_label_prep(plot_df, x_col)
            # Respetar orientación del usuario si la especifica
            if user_orientation in ['h', 'horizontal']:
                use_hbar = True
            elif user_orientation in ['v', 'vertical']:
                use_hbar = False

            # Calcular total por nodo (mes/categoría) para mostrar encima de cada barra
            _totals = sb_df.groupby(x_col, sort=False)[y_col].sum()

            def _fmt_total(v):
                return f"${v:,.0f}" if v >= 1000 else f"{v:,.2f}"

            if use_hbar:
                fig = px.bar(
                    sb_df, x=y_col, y=x_col,
                    color=color_col,
                    title=title,
                    orientation="h",
                    color_discrete_sequence=CHART_COLORS,
                    barmode="stack",
                )
                fig.update_traces(texttemplate="")  # Sin texto en segmentos
                # Total al final (derecha) de cada barra — usando anotaciones
                for cat, total in _totals.items():
                    fig.add_annotation(
                        x=total, y=cat, text=_fmt_total(total),
                        showarrow=False, xshift=5, xanchor="left",
                        font=dict(size=11, color="white"),
                    )
                fig.update_layout(height=dyn_height, yaxis=dict(autorange="reversed", tickfont=dict(size=11)))
            else:
                fig = px.bar(
                    sb_df, x=x_col, y=y_col,
                    color=color_col,
                    title=title,
                    color_discrete_sequence=CHART_COLORS,
                    barmode="stack",
                )
                fig.update_traces(texttemplate="")  # Sin texto en segmentos
                # Total encima de cada barra apilada — usando anotaciones
                for cat, total in _totals.items():
                    fig.add_annotation(
                        x=cat, y=total, text=_fmt_total(total),
                        showarrow=False, yshift=10, yanchor="bottom",
                        font=dict(size=11, color="white"),
                    )
                fig.update_layout(xaxis_tickangle=-45)
            _render_plotly_chart_and_save(fig, use_container_width=True)
            return

        # --- GROUPED BAR ---
        if chart_type == "grouped_bar" and color_col and num_cols:
            gb_df, use_hbar, dyn_height = _smart_label_prep(plot_df, x_col)
            # Respetar orientación del usuario si la especifica
            if user_orientation in ['h', 'horizontal']:
                use_hbar = True
            elif user_orientation in ['v', 'vertical']:
                use_hbar = False
            if use_hbar:
                fig = px.bar(
                    gb_df, x=y_col, y=x_col,
                    color=color_col,
                    title=title,
                    orientation="h",
                    color_discrete_sequence=CHART_COLORS,
                    barmode="group",
                    text_auto=True,
                )
                fig.update_layout(height=dyn_height, yaxis=dict(autorange="reversed", tickfont=dict(size=11)))
            else:
                fig = px.bar(
                    gb_df, x=x_col, y=y_col,
                    color=color_col,
                    title=title,
                    color_discrete_sequence=CHART_COLORS,
                    barmode="group",
                    text_auto=True,
                )
                fig.update_layout(xaxis_tickangle=-45)
            _render_plotly_chart_and_save(fig, use_container_width=True)
            return

        # --- PARETO (barras descendentes + línea % acumulado) ---
        if chart_type == "pareto" and num_cols:
            pareto_df = plot_df.copy()
            
            # Detectar columna de % acumulado si existe
            pct_col = None
            for c in pareto_df.columns:
                if any(kw in c.lower() for kw in ['pct_acum', 'acumulado', 'cumul', 'pct_total']):
                    pct_col = c
                    break
            
            # Si no hay columna de % acumulado, calcularla
            if pct_col is None:
                pareto_df = pareto_df.sort_values(y_col, ascending=False)
                total = pareto_df[y_col].sum()
                if total > 0:
                    pareto_df['_pct_acumulado'] = (pareto_df[y_col].cumsum() / total * 100).round(2)
                else:
                    pareto_df['_pct_acumulado'] = 0
                pct_col = '_pct_acumulado'
            else:
                pareto_df = pareto_df.sort_values(y_col, ascending=False)
            
            # Detectar columna de clasificación ABC si existe
            abc_col = None
            for c in pareto_df.columns:
                if any(kw in c.lower() for kw in ['clasificacion', 'abc', 'categoria', 'segmento']):
                    abc_col = c
                    break
            
            # Crear figura con eje Y secundario
            from plotly.subplots import make_subplots
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            
            # Colores por clasificación ABC si existe
            if abc_col and abc_col in pareto_df.columns:
                color_map = {'A': '#2ecc71', 'B': '#f39c12', 'C': '#e74c3c'}
                bar_colors = [color_map.get(str(v).upper(), '#3498db') for v in pareto_df[abc_col]]
            else:
                bar_colors = '#3498db'
            
            # Barras de valores
            fig.add_trace(
                go.Bar(
                    x=pareto_df[x_col],
                    y=pareto_df[y_col],
                    name=y_col.replace('_', ' ').title(),
                    marker_color=bar_colors,
                    text=[f"${v:,.0f}" if v >= 1000 else f"{v:,.2f}" for v in pareto_df[y_col]],
                    textposition="outside",
                ),
                secondary_y=False,
            )
            
            # Línea de % acumulado
            fig.add_trace(
                go.Scatter(
                    x=pareto_df[x_col],
                    y=pareto_df[pct_col],
                    name="% Acumulado",
                    mode="lines+markers+text",
                    line=dict(color="#e74c3c", width=3),
                    marker=dict(size=8, color="#e74c3c"),
                    text=[f"{v:.1f}%" for v in pareto_df[pct_col]],
                    textposition="top center",
                    textfont=dict(size=10, color="#e74c3c"),
                ),
                secondary_y=True,
            )
            
            # Línea horizontal al 80%
            fig.add_hline(
                y=80, line_dash="dash", line_color="green",
                annotation_text="80%", annotation_position="right",
                secondary_y=True,
            )
            
            n_items = len(pareto_df)
            fig.update_layout(
                title=title or "Análisis de Pareto (80/20)",
                height=max(450, min(n_items * 40, 700)),
                xaxis_tickangle=-45,
                xaxis_title=x_col.replace('_', ' ').title(),
                showlegend=True,
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                margin=dict(l=10, r=40, t=80, b=100),
            )
            fig.update_yaxes(title_text=y_col.replace('_', ' ').title(), secondary_y=False)
            fig.update_yaxes(title_text="% Acumulado", range=[0, 105], secondary_y=True)
            
            _render_plotly_chart_and_save(fig, use_container_width=True)
            
            # Mostrar resumen ABC si hay clasificación
            if abc_col and abc_col in pareto_df.columns:
                counts = pareto_df[abc_col].value_counts()
                cols_abc = st.columns(3)
                for i, (cat, emoji) in enumerate([('A', '🟢'), ('B', '🟡'), ('C', '🔴')]):
                    with cols_abc[i]:
                        n = counts.get(cat, 0)
                        total_cat = pareto_df[pareto_df[abc_col] == cat][y_col].sum()
                        st.metric(
                            f"{emoji} Categoría {cat}",
                            f"{n} clientes",
                            f"${total_cat:,.0f}" if total_cat >= 1000 else f"${total_cat:,.2f}",
                        )
            return

        # --- LINE ---
        if chart_type == "line" and num_cols:
            fig = px.line(
                plot_df, x=x_col, y=y_col,
                title=title,
                color=color_col,
                color_discrete_sequence=CHART_COLORS,
                markers=True,
            )
            fig.update_traces(line_width=3, marker_size=8)
            _render_plotly_chart_and_save(fig, use_container_width=True)
            return

        # --- AREA ---
        if chart_type == "area" and num_cols:
            fig = px.area(
                plot_df, x=x_col, y=y_col,
                title=title,
                color=color_col,
                color_discrete_sequence=CHART_COLORS,
            )
            _render_plotly_chart_and_save(fig, use_container_width=True)
            return

        # --- PIE ---
        if chart_type == "pie" and num_cols and (cat_cols or x_col in plot_df.columns):
            logger.info(f"📊 Renderizando PIE: names={x_col}, values={y_col}, rows={len(plot_df)}")
            # Asegurar que x_col sea string para names
            pie_df = plot_df.head(15).copy()
            if pie_df[x_col].dtype != 'object':
                pie_df[x_col] = pie_df[x_col].astype(str)
            fig = px.pie(
                pie_df,
                names=x_col,
                values=y_col,
                title=title,
                color_discrete_sequence=CHART_COLORS,
            )
            fig.update_traces(textposition="inside", textinfo="percent+label")
            _render_plotly_chart_and_save(fig, use_container_width=True)
            return

        # --- DONUT ---
        if chart_type == "donut" and num_cols and (cat_cols or x_col in plot_df.columns):
            logger.info(f"📊 Renderizando DONUT: names={x_col}, values={y_col}, rows={len(plot_df)}")
            # Si hay columna de monto absoluto Y columna de porcentaje, preferir el monto absoluto.
            # Plotly recalcula elem/suma_total por sí solo — usar pct como values infla los %.
            money_keywords_donut = ['total_mxn', 'total', 'monto', 'importe', 'venta', 'facturacion']
            money_col = next(
                (c for c in plot_df.select_dtypes(include='number').columns
                 if any(kw in c.lower() for kw in money_keywords_donut)),
                None
            )
            donut_values_col = money_col if money_col else y_col

            # Si ya viene con fila 'Otros' del SQL usamos todas las filas; si no, top 12 + 'Otros'
            has_otros = (plot_df[x_col].astype(str).str.upper() == "OTROS").any() if x_col in plot_df.columns else False
            if has_otros or len(plot_df) <= 15:
                donut_df = plot_df.copy()
            else:
                top = plot_df.head(12).copy()
                otros_val = plot_df.iloc[12:][donut_values_col].sum()
                otros_row = {c: (0 if c in plot_df.select_dtypes("number").columns else "") for c in plot_df.columns}
                otros_row[x_col] = "Otros"
                otros_row[donut_values_col] = otros_val
                import pandas as _pd
                donut_df = _pd.concat([top, _pd.DataFrame([otros_row])], ignore_index=True)
            if donut_df[x_col].dtype != 'object':
                donut_df[x_col] = donut_df[x_col].astype(str)
            # Excluir filas con valor 0 o NaN para no distorsionar proporciones
            donut_df = donut_df[pd.to_numeric(donut_df[donut_values_col], errors='coerce').fillna(0) > 0].copy()
            fig = px.pie(
                donut_df,
                names=x_col,
                values=donut_values_col,
                title=title,
                hole=0.45,
                color_discrete_sequence=CHART_COLORS,
            )
            fig.update_traces(textposition="inside", textinfo="percent+label")
            _render_plotly_chart_and_save(fig, use_container_width=True)
            return

        # --- SCATTER ---
        if chart_type == "scatter" and len(num_cols) >= 2:
            x_s = num_cols[0] if not spec.get("x") else x_col
            y_s = num_cols[1] if not spec.get("y") else y_col
            fig = px.scatter(
                plot_df, x=x_s, y=y_s,
                title=title,
                color=color_col,
                color_discrete_sequence=CHART_COLORS,
                size=num_cols[2] if len(num_cols) >= 3 else None,
                hover_data=cat_cols[:2] if cat_cols else None,
            )
            fig.update_traces(marker_size=10)
            _render_plotly_chart_and_save(fig, use_container_width=True)
            return

        # --- TREEMAP ---
        if chart_type == "treemap" and num_cols and (cat_cols or x_col in plot_df.columns):
            path_cols = [x_col]
            if color_col and color_col in cat_cols and color_col != x_col:
                path_cols = [color_col, x_col]
            fig = px.treemap(
                plot_df, path=path_cols,
                values=y_col,
                title=title,
                color=y_col,
                color_continuous_scale="RdYlGn",
            )
            _render_plotly_chart_and_save(fig, use_container_width=True)
            return

        # --- FUNNEL ---
        if chart_type == "funnel" and num_cols and (cat_cols or x_col in plot_df.columns):
            fig = px.funnel(
                plot_df, x=y_col, y=x_col,
                title=title,
                color_discrete_sequence=CHART_COLORS,
            )
            _render_plotly_chart_and_save(fig, use_container_width=True)
            return

        # --- WATERFALL ---
        if chart_type == "waterfall" and num_cols:
            fig = go.Figure(go.Waterfall(
                name="", orientation="v",
                x=plot_df[x_col].astype(str).tolist(),
                y=plot_df[y_col].tolist(),
                connector={"line": {"color": "rgb(63, 63, 63)"}},
                increasing={"marker": {"color": "#4CAF50"}},
                decreasing={"marker": {"color": "#F44336"}},
                totals={"marker": {"color": "#2196F3"}},
            ))
            fig.update_layout(title=title, showlegend=False)
            _render_plotly_chart_and_save(fig, use_container_width=True)
            return

    except Exception as chart_err:
        logger.error(f"❌ Error renderizando gráfico tipo '{chart_type}': {chart_err}")
        import traceback
        logger.error(traceback.format_exc())

    # Default: tabla con formato
    df = _coerce_numeric_like_columns(df)
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config=_build_numeric_column_config(df),
    )


def _render_stats_chart(df: pd.DataFrame, num_cols: list, cat_cols: list,
                        title: str, spec: dict):
    """
    Renderiza visualización estadística inteligente.

    Maneja 3 escenarios:
    A) 1 fila, múltiples métricas → bullet/gauge cards + bar de métricas
    B) Múltiples filas con stats por grupo (ej. por cliente) → grouped bar + tabla
    C) Datos raw → box plot + histograma automático
    """
    def _fmt_money(v):
        """Formato consistente: siempre $ con 2 decimales para valores monetarios."""
        if not isinstance(v, (int, float)):
            return str(v)
        return f"${v:,.2f}"

    def _fmt_count(v):
        """Formato para conteos: sin decimales, sin $."""
        if not isinstance(v, (int, float)):
            return str(v)
        return f"{v:,.0f}"

    try:
        # --- ESCENARIO A: 1 fila con múltiples estadísticas ---
        if len(df) == 1:
            st.markdown(f"#### 📊 {title}")

            # Clasificar columnas por tipo de estadística
            count_cols = [c for c in num_cols if any(k in c.lower() for k in
                          ['count', 'num_factura', 'num_concepto', 'total_factura',
                           'total_concepto', 'total_registro', 'n_empresa'])]
            central_cols = [c for c in num_cols if any(k in c.lower() for k in
                            ['media', 'promedio', 'avg', 'mediana', 'median',
                             'moda', 'precio_promedio', 'precio_mediana'])]
            dispersion_cols = [c for c in num_cols if any(k in c.lower() for k in
                               ['desviacion', 'stddev', 'varianza', 'variance'])]
            range_cols = [c for c in num_cols if any(k in c.lower() for k in
                          ['minimo', 'min_', 'maximo', 'max_', 'precio_minimo',
                           'precio_maximo']) or c.lower() in ('minimo', 'maximo', 'min', 'max')]
            percentile_cols = [c for c in num_cols if any(k in c.lower() for k in
                               ['percentil', 'quartil', 'p25', 'p50', 'p75'])]
            other_cols = [c for c in num_cols if c not in
                          count_cols + central_cols + dispersion_cols + range_cols + percentile_cols]

            # Tarjetas de conteo
            if count_cols:
                st.markdown("**📋 Muestra**")
                cols_ui = st.columns(len(count_cols))
                for i, col in enumerate(count_cols):
                    with cols_ui[i]:
                        v = df[col].iloc[0]
                        st.metric(col.replace('_', ' ').title(), _fmt_count(v))

            # Medidas de tendencia central
            if central_cols:
                st.markdown("**📍 Tendencia Central**")
                cols_ui = st.columns(min(len(central_cols), 4))
                for i, col in enumerate(central_cols[:4]):
                    with cols_ui[i]:
                        v = df[col].iloc[0]
                        st.metric(col.replace('_', ' ').title(), _fmt_money(v))

            # Dispersión
            if dispersion_cols:
                st.markdown("**📏 Dispersión**")
                cols_ui = st.columns(min(len(dispersion_cols), 4))
                for i, col in enumerate(dispersion_cols[:4]):
                    with cols_ui[i]:
                        v = df[col].iloc[0]
                        st.metric(col.replace('_', ' ').title(), _fmt_money(v))

            # Rango
            if range_cols:
                st.markdown("**↕️ Rango**")
                cols_ui = st.columns(min(len(range_cols), 4))
                for i, col in enumerate(range_cols[:4]):
                    with cols_ui[i]:
                        v = df[col].iloc[0]
                        st.metric(col.replace('_', ' ').title(), _fmt_money(v))

            # Percentiles
            if percentile_cols:
                st.markdown("**📊 Percentiles**")
                cols_ui = st.columns(min(len(percentile_cols), 4))
                for i, col in enumerate(percentile_cols[:4]):
                    with cols_ui[i]:
                        v = df[col].iloc[0]
                        st.metric(col.replace('_', ' ').title(), _fmt_money(v))

            # Otros
            if other_cols:
                cols_ui = st.columns(min(len(other_cols), 4))
                for i, col in enumerate(other_cols[:4]):
                    with cols_ui[i]:
                        v = df[col].iloc[0]
                        st.metric(col.replace('_', ' ').title(),
                                  _fmt_money(v) if isinstance(v, (int, float)) else str(v))

            # Gráfica de barras: solo comparar valores de la misma categoría (central vs percentiles)
            # Evitar mezclar escalas completamente dispares (desviación enorme vs percentil_25 pequeño)
            comparable_cols = central_cols + percentile_cols  # misma escala: promedios y percentiles
            if not comparable_cols:
                comparable_cols = [c for c in num_cols if c not in count_cols]

            if comparable_cols:
                stat_data = [
                    {
                        "Métrica": c.replace('_', ' ').title(),
                        "Valor": float(df[c].iloc[0]),
                        "Etiqueta": _fmt_money(float(df[c].iloc[0])),
                    }
                    for c in comparable_cols
                ]
                stat_df = pd.DataFrame(stat_data).sort_values("Valor", ascending=False)
                fig = px.bar(
                    stat_df,
                    x="Valor",
                    y="Métrica",
                    orientation="h",
                    title=f"📐 {title}",
                    color_discrete_sequence=["#4DD0E1"],
                    text="Etiqueta",
                )
                fig.update_layout(
                    yaxis=dict(autorange="reversed"),
                    showlegend=False,
                    height=max(320, len(stat_data) * 58),
                    margin=dict(l=20, r=120, t=60, b=30),
                    xaxis=dict(title="Valor", tickformat="$,.0f"),
                    coloraxis_showscale=False,
                )
                fig.update_traces(
                    textposition="outside",
                    cliponaxis=False,
                    hovertemplate="%{y}: %{text}<extra></extra>",
                    marker_line_width=0,
                )
                _render_plotly_chart_and_save(fig, use_container_width=True)

            # Si hay percentiles → box plot simulado
            p25_col = next((c for c in percentile_cols if '25' in c), None)
            p50_col = next((c for c in percentile_cols + central_cols if any(k in c.lower() for k in ['mediana', 'median', '50'])), None)
            p75_col = next((c for c in percentile_cols if '75' in c), None)
            min_col = next((c for c in range_cols if any(k in c.lower() for k in ['min'])), None)
            max_col = next((c for c in range_cols if any(k in c.lower() for k in ['max'])), None)

            if p25_col and p75_col:
                from plotly.subplots import make_subplots

                p25 = float(df[p25_col].iloc[0])
                p75 = float(df[p75_col].iloc[0])
                p50 = float(df[p50_col].iloc[0]) if p50_col else (p25 + p75) / 2
                mn = float(df[min_col].iloc[0]) if min_col else p25 - 1.5 * (p75 - p25)
                mx = float(df[max_col].iloc[0]) if max_col else p75 + 1.5 * (p75 - p25)
                avg_val = float(df[central_cols[0]].iloc[0]) if central_cols else p50
                iqr = p75 - p25

                # Calcular fences estadísticos (1.5 * IQR)
                fence_lo = max(mn, p25 - 1.5 * iqr)
                fence_hi = min(mx, p75 + 1.5 * iqr)
                # Puntos outlier fuera de los fences
                outliers_lo = [mn] if mn < fence_lo else []
                outliers_hi = [mx] if mx > fence_hi else []
                all_outliers = outliers_lo + outliers_hi
                extreme_scale_gap = bool(all_outliers) and (mx / max(p75, 1) >= 8)

                if extreme_scale_gap:
                    fig = make_subplots(
                        rows=1,
                        cols=2,
                        shared_yaxes=True,
                        column_widths=[0.72, 0.28],
                        horizontal_spacing=0.08,
                        subplot_titles=("Rango central", "Outliers"),
                    )
                else:
                    fig = go.Figure()

                def _add_trace(trace, col: int = 1):
                    if extreme_scale_gap:
                        fig.add_trace(trace, row=1, col=col)
                    else:
                        fig.add_trace(trace)

                _add_trace(go.Scatter(
                    x=[fence_lo, fence_hi],
                    y=[0, 0],
                    mode="lines",
                    line=dict(color="#90CAF9", width=4),
                    name="Rango útil",
                    hovertemplate=f"Rango útil: {_fmt_money(fence_lo)} - {_fmt_money(fence_hi)}<extra></extra>",
                ), col=1)
                _add_trace(go.Scatter(
                    x=[p25, p75],
                    y=[0, 0],
                    mode="lines",
                    line=dict(color="#26A69A", width=16),
                    name="IQR",
                    hovertemplate=f"IQR: {_fmt_money(p25)} - {_fmt_money(p75)}<extra></extra>",
                ), col=1)
                _add_trace(go.Scatter(
                    x=[mn, mx],
                    y=[0, 0],
                    mode="markers",
                    marker=dict(color="#B0BEC5", size=10, symbol="line-ns-open"),
                    name="Mín/Máx",
                    hovertemplate="Valor: %{x:$,.2f}<extra></extra>",
                ), col=1)

                key_points = pd.DataFrame([
                    {"x": p25, "label": "P25", "color": "#64B5F6", "symbol": "circle"},
                    {"x": p50, "label": "Mediana", "color": "#FFFFFF", "symbol": "diamond"},
                    {"x": p75, "label": "P75", "color": "#64B5F6", "symbol": "circle"},
                    {"x": avg_val, "label": "Promedio", "color": "#FFC107", "symbol": "triangle-up"},
                ])
                for _, point in key_points.iterrows():
                    _add_trace(go.Scatter(
                        x=[point["x"]],
                        y=[0],
                        mode="markers",
                        marker=dict(color=point["color"], size=14, symbol=point["symbol"], line=dict(width=1, color="#111827")),
                        name=point["label"],
                        hovertemplate=f"{point['label']}: {_fmt_money(float(point['x']))}<extra></extra>",
                    ), col=1)

                # Marcar outliers como puntos separados
                if all_outliers:
                    _add_trace(go.Scatter(
                        x=all_outliers,
                        y=[0] * len(all_outliers),
                        mode="markers+text",
                        marker=dict(color="#FF5722", size=12, symbol="diamond"),
                        text=[f"${v:,.2f}" for v in all_outliers],
                        textposition="top center",
                        name="Outliers",
                        hoverinfo="text",
                        hovertext=[f"Outlier: ${v:,.2f}" for v in all_outliers],
                    ), col=2 if extreme_scale_gap else 1)

                central_left = min(mn, p25, p50, avg_val) * 0.95 if min(mn, p25, p50, avg_val) > 0 else 0
                central_right = max(fence_hi, p75, p50, avg_val) * 1.15

                if extreme_scale_gap:
                    fig.update_xaxes(title_text="Valor ($)", tickformat="$,.0f", range=[central_left, central_right], row=1, col=1)
                    outlier_min = min(all_outliers) * 0.95 if min(all_outliers) > 0 else 0
                    outlier_max = max(all_outliers) * 1.05
                    fig.update_xaxes(title_text="Outliers ($)", tickformat="$,.0f", range=[outlier_min, outlier_max], row=1, col=2)
                    fig.update_yaxes(showticklabels=False, row=1, col=1)
                    fig.update_yaxes(showticklabels=False, row=1, col=2)
                    fig.update_layout(
                        title=f"📦 Distribución — {title}",
                        showlegend=True,
                        height=340,
                        margin=dict(l=20, r=20, t=80, b=40),
                        legend=dict(orientation="h", yanchor="bottom", y=1.10, xanchor="left", x=0),
                    )
                    fig.add_annotation(
                        x=0.5,
                        y=-0.28,
                        xref="paper",
                        yref="paper",
                        text="El panel derecho separa valores extremos para no aplastar el rango central.",
                        showarrow=False,
                        font=dict(size=11, color="#94A3B8"),
                    )
                else:
                    fig.update_layout(
                        title=f"📦 Distribución — {title}",
                        showlegend=True,
                        height=320,
                        xaxis=dict(
                            title="Valor ($)",
                            tickformat="$,.0f",
                            range=[central_left, max(mx, central_right)],
                        ),
                        yaxis=dict(showticklabels=False),
                        margin=dict(l=20, r=20, t=70, b=40),
                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
                    )
                _render_plotly_chart_and_save(fig, use_container_width=True)

                st.caption(
                    " | ".join([
                        f"Mín {_fmt_money(mn)}",
                        f"P25 {_fmt_money(p25)}",
                        f"Mediana {_fmt_money(p50)}",
                        f"Promedio {_fmt_money(avg_val)}",
                        f"P75 {_fmt_money(p75)}",
                        f"Máx {_fmt_money(mx)}",
                    ])
                )

            return

        # --- ESCENARIO B: Múltiples filas con stats por grupo ---
        if len(df) > 1 and cat_cols:
            group_col = cat_cols[0]
            st.markdown(f"#### 📊 {title}")

            # Detectar columnas de stats
            stat_y_cols = [c for c in num_cols if any(k in c.lower() for k in
                          ['promedio', 'media', 'avg', 'desviacion', 'stddev',
                           'minimo', 'min', 'maximo', 'max', 'mediana'])]
            main_y = stat_y_cols[0] if stat_y_cols else num_cols[0]

            # Bar chart principal
            fig = px.bar(
                df.head(20), x=group_col, y=main_y,
                title=title,
                color=main_y,
                color_continuous_scale="Viridis",
                text_auto="$,.2f",
            )
            fig.update_layout(xaxis_tickangle=-45, showlegend=False)
            fig.update_traces(textposition="outside")

            # Si hay min y max, agregar barras de error
            min_c = next((c for c in num_cols if any(k in c.lower() for k in ['minimo', 'min'])), None)
            max_c = next((c for c in num_cols if any(k in c.lower() for k in ['maximo', 'max'])), None)
            if min_c and max_c and main_y not in (min_c, max_c):
                error_minus = (df[main_y] - df[min_c]).clip(lower=0).head(20)
                error_plus = (df[max_c] - df[main_y]).clip(lower=0).head(20)
                fig.update_traces(
                    error_y=dict(
                        type="data",
                        symmetric=False,
                        array=error_plus.tolist(),
                        arrayminus=error_minus.tolist(),
                        color="rgba(0,0,0,0.3)",
                    )
                )

            _render_plotly_chart_and_save(fig, use_container_width=True)

            # Si hay desviación, mostrar gráfica adicional
            dev_col = next((c for c in num_cols if any(k in c.lower() for k in ['desviacion', 'stddev'])), None)
            if dev_col:
                fig2 = px.bar(
                    df.head(20), x=group_col, y=dev_col,
                    title=f"📏 Dispersión: {dev_col.replace('_', ' ').title()}",
                    color=dev_col,
                    color_continuous_scale="Reds",
                    text_auto="$,.2f",
                )
                fig2.update_layout(xaxis_tickangle=-45, showlegend=False)
                _render_plotly_chart_and_save(fig2, use_container_width=True)

            return

        # --- ESCENARIO C: Datos raw → box + histogram ---
        if len(df) > 5 and num_cols:
            y_stat = spec.get("y") or num_cols[0]
            if y_stat in df.columns:
                fig = px.histogram(
                    df, x=y_stat,
                    title=f"📊 Distribución de {y_stat}",
                    nbins=min(30, len(df)),
                    color_discrete_sequence=[CHART_COLORS[0]],
                    marginal="box",
                )
                fig.update_layout(bargap=0.05)
                _render_plotly_chart_and_save(fig, use_container_width=True)
                return

    except Exception:
        pass  # Fallback a tabla si falla

    # Fallback: tabla formateada
    st.dataframe(df, use_container_width=True, hide_index=True, column_config=_build_numeric_column_config(df))


# =====================================================================
# Componentes de UI
# =====================================================================
def _render_hero():
    """Hero banner."""
    st.markdown(ASSISTANT_CSS, unsafe_allow_html=True)

    empresa_nombre = st.session_state.get("empresa_nombre")
    rfc_empresa = st.session_state.get("rfc_empresa")

    if empresa_nombre:
        empresa_badge = f'<span style="background:#e8f4f8;border:1px solid #b0d4e8;border-radius:20px;padding:3px 12px;font-size:0.85rem;color:#1a5276;font-weight:600;">🏢 {empresa_nombre}</span>'
        if rfc_empresa:
            empresa_badge += f' <span style="background:#f0f3f4;border:1px solid #d5dbdb;border-radius:20px;padding:3px 10px;font-size:0.8rem;color:#555;">RFC: {rfc_empresa}</span>'
    else:
        empresa_badge = '<span style="background:#fef9e7;border:1px solid #f9e79f;border-radius:20px;padding:3px 12px;font-size:0.85rem;color:#7d6608;">👑 Vista superadmin — todas las empresas</span>'

    st.markdown(f"""
    <div class="assistant-hero">
        <h2>🤖 Asistente de Datos</h2>
        <p>Haz preguntas en español sobre tus datos de facturación CFDI y obtén
        respuestas instantáneas con tablas, gráficas e interpretación inteligente.</p>
        <div style="margin-top:8px;">{empresa_badge}</div>
    </div>
    """, unsafe_allow_html=True)


def _auto_connect_from_env():
    """Si las credenciales están en variables de entorno y no hay sesión activa, conecta automáticamente."""
    if st.session_state.get("nl2sql_connected") or st.session_state.get("nl2sql_disable_auto_connect"):
        return  # Ya conectado, nada que hacer

    neon_url = _get_server_credential("NEON_DATABASE_URL")
    api_key, _api_source = _get_runtime_api_key_details()

    if not neon_url or not api_key:
        return  # Sin env vars → mostrar formulario manual

    if "nl2sql_model" not in st.session_state:
        st.session_state["nl2sql_model"] = "gpt-4o"

    engine = _get_engine()
    if engine:
        ok, _ = engine.test_connection()
        if ok:
            st.session_state["nl2sql_connected"] = True
            st.session_state["nl2sql_disable_auto_connect"] = False


def _render_connection_setup():
    """Panel de configuración de conexión."""
    st.markdown("### 🔌 Configurar Conexión")

    user = get_current_user()
    server_neon, neon_source = _get_server_credential_details("NEON_DATABASE_URL")
    server_api, api_source = _get_runtime_api_key_details()

    neon_status = f"Neon: {'detectado' if server_neon else 'no detectado'} ({neon_source})"
    api_status = f"OpenAI: {'detectado' if server_api else 'no detectado'} ({api_source})"
    st.caption(f"Diagnóstico servidor: {neon_status} · {api_status}")

    if user and not _can_configure_connection(user):
        if server_neon and server_api:
            st.success("✅ El asistente usa credenciales seguras del servidor para tu sesión.")
            if st.button("🔌 Conectar", type="primary", use_container_width=True):
                st.session_state["nl2sql_disable_auto_connect"] = False
                engine = _get_engine()
                if engine:
                    with st.spinner("Probando conexión..."):
                        ok, msg = engine.test_connection()
                    if ok:
                        st.session_state["nl2sql_connected"] = True
                        st.rerun()
                    st.error(f"❌ {msg}")
            return st.session_state.get("nl2sql_connected", False)

        st.warning("El Asistente de Datos requiere credenciales del servidor. Contacta al administrador.")
        return False

    st.info(
        "Para usar el Asistente de Datos necesitas:\n"
        "1. **URL de Neon PostgreSQL** con datos CFDI ingestados\n"
        "2. **API Key de OpenAI** para la generación de SQL e interpretación"
    )

    col1, col2 = st.columns(2)

    with col1:
        neon_url = st.text_input(
            "URL de Neon PostgreSQL",
            type="password",
            value=st.session_state.get("nl2sql_neon_url", ""),
            help="postgresql://user:pass@host/db?sslmode=require",
            key="input_neon_url",
        )

    with col2:
        api_key = st.text_input(
            "API Key de OpenAI",
            type="password",
            value=st.session_state.get("nl2sql_api_key", ""),
            help="sk-...",
            key="input_api_key",
        )

    col_model, col_btn = st.columns([2, 1])

    with col_model:
        model = st.selectbox(
            "Modelo de IA",
            ["gpt-4o", "gpt-4o-mini"],
            index=0,
            help="gpt-4o genera SQL más preciso; gpt-4o-mini es más económico",
            key="input_model",
        )

    with col_btn:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔌 Conectar", type="primary", use_container_width=True):
            if not neon_url:
                st.error("Ingresa la URL de Neon")
                return False
            if not api_key:
                st.error("Ingresa la API Key de OpenAI")
                return False

            # Sanitizar URL: quitar prefijo "psql " si el usuario copió el comando CLI
            neon_url = neon_url.strip()
            if neon_url.lower().startswith("psql "):
                neon_url = neon_url[5:].strip()
            # Quitar comillas envolventes
            if (neon_url.startswith('"') and neon_url.endswith('"')) or \
               (neon_url.startswith("'") and neon_url.endswith("'")):
                neon_url = neon_url[1:-1]
            # Validar formato básico
            if not neon_url.startswith(("postgresql://", "postgres://")):
                st.error(
                    "La URL debe comenzar con `postgresql://` o `postgres://`.\n\n"
                    "Ejemplo: `postgresql://user:pass@host/db?sslmode=require`"
                )
                return False

            st.session_state["nl2sql_neon_url"] = neon_url
            st.session_state["nl2sql_api_key"] = api_key
            st.session_state["nl2sql_model"] = model
            st.session_state["nl2sql_disable_auto_connect"] = False
            _invalidate_engine()

            engine = _get_engine()
            if engine:
                with st.spinner("Probando conexión..."):
                    ok, msg = engine.test_connection()
                if ok:
                    st.success(f"✅ {msg}")
                    st.session_state["nl2sql_connected"] = True
                    st.rerun()
                else:
                    st.error(f"❌ {msg}")
                    st.session_state["nl2sql_connected"] = False
            return False

    return st.session_state.get("nl2sql_connected", False)


def _get_stage_mode_config() -> tuple[list[str], list[dict[str, str]]]:
    """Define qué funciones están activas hoy y cuáles pasan a second stage."""
    current_stage_modes = ["💬 Chat", "🧭 Guiado"]
    second_stage_options = [
        {
            "label": "🛠️ SQL Playground",
            "description": "Ejecución SQL guiada y auditada para una siguiente etapa.",
        },
        {
            "label": "🗄️ Esquema",
            "description": "Exploración asistida de tablas y contexto técnico en segunda etapa.",
        },
        {
            "label": "🕰️ Historial",
            "description": "Trazabilidad persistente de consultas y resultados en segunda etapa.",
        },
        {
            "label": "💰 ROI",
            "description": "Panel dedicado de ahorro y productividad cuando el flujo esté estabilizado.",
        },
    ]
    return current_stage_modes, second_stage_options


def _render_second_stage_options(second_stage_options: list[dict[str, str]]):
    """Muestra funciones reservadas para una siguiente etapa sin habilitarlas aún."""
    with st.expander("Second Stage · Opciones Futuras", expanded=False):
        st.caption("Estas funciones quedan reservadas para una segunda etapa. Se mantienen bloqueadas por ahora.")
        for option in second_stage_options:
            st.button(option["label"], disabled=True, use_container_width=True, key=f"future_{option['label']}")
            st.caption(option["description"])

        guided_info = st.session_state.get("guided_catalog_info")
        if guided_info:
            st.markdown("---")
            st.caption(
                f"🧭 Catálogo guiado cargado · fuente: {guided_info.get('source', 'json')} · "
                f"dominios: {guided_info.get('domains', 0)} · casos: {guided_info.get('cases', 0)}"
            )


def _load_guided_catalog_runtime():
    """Carga catálogo guiado en sesión (BD preferente opcional, fallback JSON)."""
    if not GUIDED_CATALOG_AVAILABLE:
        return

    tenant_id = _get_active_empresa_id()
    cached_tenant = st.session_state.get("guided_catalog_tenant_id")
    if cached_tenant and str(cached_tenant) != str(tenant_id):
        st.session_state.pop("guided_catalog", None)
        st.session_state.pop("guided_catalog_info", None)
        st.session_state.pop("guided_framework", None)

    if "guided_catalog" in st.session_state and "guided_catalog_info" in st.session_state:
        return

    prefer_db = os.getenv("GUIDED_CATALOG_SOURCE", "json").lower() in {"db", "database", "postgres"}
    connection_string = ""
    engine = st.session_state.get("nl2sql_engine")
    if engine and getattr(engine, "connection_string", None):
        connection_string = engine.connection_string
    if not connection_string:
        connection_string = _get_server_credential("NEON_DATABASE_URL")

    try:
        catalog = load_runtime_catalog(
            connection_string=connection_string or None,
            prefer_db=prefer_db,
            empresa_id=str(tenant_id) if tenant_id else None,
        )
        stats = catalog_stats(catalog)
        st.session_state["guided_catalog"] = catalog
        st.session_state["guided_catalog_tenant_id"] = str(tenant_id) if tenant_id else ""
        st.session_state["guided_catalog_info"] = {
            "source": "db" if prefer_db and connection_string else "json",
            "domains": stats.get("domains", 0),
            "cases": stats.get("cases", 0),
            "tenant": str(tenant_id) if tenant_id else "global",
        }
    except Exception as exc:
        logger.warning(f"No se pudo cargar catálogo guiado runtime: {exc}")
        st.session_state["guided_catalog_info"] = {
            "source": "unavailable",
            "domains": 0,
            "cases": 0,
            "tenant": str(tenant_id) if tenant_id else "global",
        }


def _get_or_build_guided_framework():
    """Construye el runtime del framework guiado usando el catálogo en sesión."""
    if not GUIDED_FRAMEWORK_AVAILABLE:
        return None

    existing = st.session_state.get("guided_framework")
    if existing is not None:
        return existing

    catalog = st.session_state.get("guided_catalog")
    if not catalog:
        _load_guided_catalog_runtime()
        catalog = st.session_state.get("guided_catalog")

    if not catalog:
        return None

    framework = GuidedQueryFramework(catalog)
    st.session_state["guided_framework"] = framework
    return framework


def _render_guided_interface():
    """Interfaz determinística de dominio -> caso -> parámetros -> ejecución."""
    engine = _get_engine()
    if not engine:
        return

    framework = _get_or_build_guided_framework()
    if not framework:
        st.warning("No se pudo inicializar el framework guiado. Verifica el catálogo.")
        return

    domains = framework.list_enabled_domains()
    if not domains:
        st.warning("No hay dominios guiados habilitados en el catálogo.")
        return

    domain_options = {f"{domain.get('label', domain.get('id'))}": domain.get("id") for domain in domains}
    selected_domain_label = st.selectbox("Dominio", list(domain_options.keys()), key="guided_domain_select")
    selected_domain_id = domain_options[selected_domain_label]

    cases = framework.list_enabled_cases(selected_domain_id)
    if not cases:
        st.info("No hay casos habilitados para este dominio.")
        return

    case_options = {f"{case.get('label', case.get('id'))}": case.get("id") for case in cases}
    selected_case_label = st.selectbox("Analisis", list(case_options.keys()), key="guided_case_select")
    selected_case_id = case_options[selected_case_label]
    selected_case = framework.get_case(selected_case_id)

    st.caption(selected_case.get("description", ""))
    st.caption(f"Template: {selected_case.get('sql_template_id', 'n/a')}")

    if GUIDED_USAGE_METRICS_AVAILABLE:
        usage_summary = get_session_guided_usage_summary(st.session_state)
        if usage_summary.get("events", 0) > 0:
            st.caption(
                f"Uso guiado en sesion: {usage_summary['events']} ejecuciones · "
                f"Top caso: {usage_summary['top_cases'][0][0]} ({usage_summary['top_cases'][0][1]})"
            )

        with st.expander("📈 Adopción guiada", expanded=False):
            conn_str = getattr(engine, "connection_string", "") or _get_server_credential("NEON_DATABASE_URL")
            tenant_id = str(_get_active_empresa_id()) if _get_active_empresa_id() else None
            viewer_user = get_current_user()

            controls_col1, controls_col2 = st.columns(2)
            with controls_col1:
                scope_options = ["Tenant actual"]
                if viewer_user and viewer_user.is_superadmin:
                    scope_options.append("Global")
                selected_scope = st.selectbox(
                    "Alcance",
                    options=scope_options,
                    key="guided_adoption_scope",
                )
            with controls_col2:
                selected_days = st.radio(
                    "Ventana",
                    options=[7, 30, 90],
                    horizontal=True,
                    key="guided_adoption_days",
                )

            filter_empresa_id = None if selected_scope == "Global" else tenant_id

            try:
                db_summary = get_db_guided_usage_summary(
                    conn_str,
                    empresa_id=filter_empresa_id,
                    days=int(selected_days),
                )
                series = get_db_guided_usage_timeseries(
                    conn_str,
                    empresa_id=filter_empresa_id,
                    days=int(selected_days),
                )

                kpi_cols = st.columns(3)
                with kpi_cols[0]:
                    st.metric("Eventos", db_summary.get("events", 0))
                with kpi_cols[1]:
                    st.metric("Tasa éxito", f"{db_summary.get('success_rate', 0.0) * 100:.2f}%")
                with kpi_cols[2]:
                    st.metric("Latencia prom. (s)", f"{db_summary.get('avg_execution_time', 0.0):.3f}")

                if series:
                    ts_df = pd.DataFrame(series)
                    ts_df["day"] = pd.to_datetime(ts_df["day"]) 
                    ts_df["success_pct"] = ts_df["success_rate"] * 100.0

                    if PLOTLY_AVAILABLE:
                        fig_events = px.line(
                            ts_df,
                            x="day",
                            y="events",
                            markers=True,
                            title="Eventos diarios",
                        )
                        st.plotly_chart(fig_events, use_container_width=True)

                        fig_success = px.bar(
                            ts_df,
                            x="day",
                            y="success_pct",
                            title="Tasa de éxito diaria (%)",
                        )
                        st.plotly_chart(fig_success, use_container_width=True)

                    st.dataframe(
                        ts_df[["day", "events", "success_pct", "avg_execution_time"]],
                        use_container_width=True,
                        hide_index=True,
                    )
                else:
                    st.info("No hay eventos en la ventana seleccionada.")

                if db_summary.get("top_cases"):
                    st.caption("Top casos")
                    st.dataframe(
                        pd.DataFrame(db_summary["top_cases"], columns=["case_key", "usos"]),
                        use_container_width=True,
                        hide_index=True,
                    )
                if db_summary.get("top_domains"):
                    st.caption("Top dominios")
                    st.dataframe(
                        pd.DataFrame(db_summary["top_domains"], columns=["domain_key", "usos"]),
                        use_container_width=True,
                        hide_index=True,
                    )
            except Exception as exc:
                st.caption(f"Sin métricas BD disponibles: {exc}")

    allowed_filters = set(selected_case.get("allowed_filters", []))
    allowed_groupings = selected_case.get("allowed_groupings", [])

    params: dict[str, object] = {}
    period_mode = st.selectbox(
        "Periodo",
        ["todo", "este_ano", "ultimos_12_meses", "ultimos_6_meses", "rango_personalizado"],
        index=2,
        key="guided_period_mode",
    )
    params["period_mode"] = period_mode

    if period_mode == "rango_personalizado" or "start_date" in allowed_filters or "end_date" in allowed_filters:
        col_start, col_end = st.columns(2)
        with col_start:
            start_date = st.date_input("Fecha inicio", value=date.today().replace(day=1), key="guided_start_date")
        with col_end:
            end_date = st.date_input("Fecha fin", value=date.today(), key="guided_end_date")
        params["start_date"] = start_date.isoformat()
        params["end_date"] = end_date.isoformat()

    if "top_n" in allowed_filters:
        params["top_n"] = st.number_input("Top N", min_value=1, max_value=100, value=10, step=1, key="guided_top_n")

    if "metodo_pago" in allowed_filters:
        params["metodo_pago"] = st.selectbox("Metodo de pago", ["todos", "PUE", "PPD"], key="guided_metodo_pago")

    if "tipo_comprobante" in allowed_filters:
        params["tipo_comprobante"] = st.selectbox("Tipo de comprobante", ["todos", "I", "E", "P"], key="guided_tipo_comp")

    if "cliente" in allowed_filters:
        params["cliente"] = st.text_input("Cliente contiene", value="", key="guided_cliente")

    if "producto" in allowed_filters:
        params["producto"] = st.text_input("Producto contiene", value="", key="guided_producto")

    if allowed_groupings:
        params["grouping"] = st.selectbox("Agrupacion", allowed_groupings, key="guided_grouping")

    if st.button("▶ Ejecutar analisis guiado", type="primary", use_container_width=True, key="guided_execute"):
        with st.spinner("Ejecutando caso guiado..."):
            empresa_id = _get_active_empresa_id()
            current_user = get_current_user()
            try:
                guided_result = framework.execute_case(
                    engine,
                    selected_case_id,
                    params,
                    empresa_id=empresa_id,
                )
            except Exception as exc:
                if GUIDED_USAGE_METRICS_AVAILABLE:
                    record_session_guided_usage(
                        st.session_state,
                        domain_key=selected_case.get("domain_id", selected_domain_id),
                        case_key=selected_case_id,
                    )
                    try:
                        record_db_guided_usage(
                            getattr(engine, "connection_string", ""),
                            domain_key=selected_case.get("domain_id", selected_domain_id),
                            case_key=selected_case_id,
                            success=False,
                            execution_time_sec=None,
                            row_count=None,
                            empresa_id=str(empresa_id) if empresa_id else None,
                            user_email=getattr(current_user, "email", None),
                            source="streamlit-guided",
                        )
                    except Exception:
                        pass
                st.error(f"Error ejecutando caso guiado: {exc}")
                return

        if GUIDED_USAGE_METRICS_AVAILABLE:
            record_session_guided_usage(
                st.session_state,
                domain_key=selected_case.get("domain_id", selected_domain_id),
                case_key=selected_case_id,
            )
            try:
                record_db_guided_usage(
                    getattr(engine, "connection_string", ""),
                    domain_key=selected_case.get("domain_id", selected_domain_id),
                    case_key=selected_case_id,
                    success=True,
                    execution_time_sec=guided_result.execution_time,
                    row_count=guided_result.row_count,
                    empresa_id=str(empresa_id) if empresa_id else None,
                    user_email=getattr(current_user, "email", None),
                    source="streamlit-guided",
                )
            except Exception:
                pass

        user_prompt = f"Caso guiado: {selected_case_label}"
        _append_chat_message({"role": "user", "content": user_prompt})

        result_msg = {
            "role": "assistant",
            "question": user_prompt,
            "content": guided_result.summary,
            "sql": guided_result.sql,
            "success": True,
            "execution_time": guided_result.execution_time,
            "row_count": guided_result.row_count,
            "chart_suggestion": guided_result.chart,
            "chart_spec": {},
            "error": None,
        }

        if guided_result.dataframe is not None and not guided_result.dataframe.empty:
            truncated_df = guided_result.dataframe.head(MAX_SESSION_RESULT_ROWS)
            result_msg["dataframe_json"] = truncated_df.to_json(orient="split", date_format="iso")
            result_msg["dataframe_truncated"] = len(guided_result.dataframe) > len(truncated_df)

        _append_chat_message(result_msg)
        st.rerun()


BLOCKED_EXAMPLE_QUESTIONS = {
    "¿Qué clientes no han comprado en los últimos 3 meses?": "Depende de una base maestra de clientes y reglas de inactividad verificadas.",
    "¿Cuál es el promedio de días de crédito?": "Depende de reglas de crédito homologadas y verificadas por cliente/documento.",
    "¿Cuál es la tendencia de nuevos clientes por mes?": "Depende de una definición validada de alta de cliente y primera compra.",
    "¿Cuáles clientes compran cada vez menos?": "Depende de una metodología de deterioro de compra validada por negocio.",
    "Segmentación RFM de clientes": "Depende de una metodología RFM validada y umbrales por tenant.",
    "Detectar facturas anómalas (outliers)": "Depende de un criterio estadístico de anomalías validado.",
    "¿Cuál es el DSO y tasa de cobro de los últimos 3 meses?": "Depende de una definición financiera validada de DSO y cobranza efectiva.",
}


def _get_sidebar_examples_config() -> list[dict]:
    """Anota qué preguntas ejemplo están activas hoy y cuáles quedan visibles pero bloqueadas."""
    examples = get_example_questions()
    annotated_examples = []

    for category in examples:
        annotated_questions = []
        for question in category["questions"]:
            blocked_reason = BLOCKED_EXAMPLE_QUESTIONS.get(question)
            annotated_questions.append(
                {
                    "text": question,
                    "enabled": blocked_reason is None,
                    "blocked_reason": blocked_reason,
                }
            )

        annotated_examples.append(
            {
                "category": category["category"],
                "icon": category["icon"],
                "questions": annotated_questions,
            }
        )

    return annotated_examples


def _get_chat_guidance_lists() -> tuple[list[str], list[str]]:
    """Resume ejemplos activos hoy vs preguntas que quedan para después."""
    examples = _get_sidebar_examples_config()
    active_questions = []
    future_questions = []

    for category in examples:
        for question in category["questions"]:
            if question["enabled"]:
                active_questions.append(question["text"])
            else:
                future_questions.append(question["text"])

    return active_questions, future_questions


def _render_chat_guidance_empty_state():
    """Aclara el alcance actual del chat antes de la primera consulta."""
    active_questions, future_questions = _get_chat_guidance_lists()

    active_preview = "\n".join(f"- {question}" for question in active_questions[:4])
    future_preview = "\n".join(f"- {question}" for question in future_questions[:4])

    st.info(
        "Hoy puedes consultar ventas, cobranza, productos, tendencias y estadísticas descriptivas."
    )
    st.markdown(
        "**Disponible hoy**\n"
        f"{active_preview}"
    )
    st.markdown(
        "**Visible pero no activo todavía**\n"
        f"{future_preview}"
    )
    st.caption(
        "Las preguntas avanzadas quedan visibles como referencia, pero siguen bloqueadas hasta validar sus dependencias de negocio y datos."
    )


def _render_sidebar_examples():
    """Preguntas de ejemplo en la barra lateral derecha."""
    examples = _get_sidebar_examples_config()

    st.markdown("### 💡 Preguntas de ejemplo")
    st.caption("Las preguntas activas se pueden cargar al chat. Las demás quedan visibles como referencia futura.")

    for cat in examples:
        with st.expander(f"{cat['icon']} {cat['category']}", expanded=False):
            for q in cat["questions"]:
                if st.button(
                    q["text"],
                    key=f"ex_{hash(q['text'])}",
                    use_container_width=True,
                    disabled=not q["enabled"],
                ):
                    st.session_state["nl2sql_pending_question"] = q["text"]
                    st.rerun()
                if not q["enabled"] and q.get("blocked_reason"):
                    st.caption(f"Depende de: {q['blocked_reason']}")


def _render_schema_explorer():
    """Explorador del esquema de base de datos."""
    st.markdown("### 🗄️ Esquema de Datos")
    st.caption("Tablas y vistas disponibles para consulta")

    engine = _get_engine()
    if not engine:
        st.warning("Conecta primero a la base de datos")
        return

    # Obtener conteos
    with st.spinner("Obteniendo información del esquema..."):
        counts = engine.get_table_counts(empresa_id=_get_active_empresa_id())
        date_range = engine.get_date_range(empresa_id=_get_active_empresa_id())

    # Mostrar rango de datos
    if date_range:
        st.success(f"📅 Datos disponibles: **{date_range[0]}** a **{date_range[1]}**")

    # Tablas
    for table in ALLOWED_TABLES:
        icon = "📋" if not table.startswith("v_") else "👁️"
        count = counts.get(table, "—")
        count_str = f"{count:,}" if isinstance(count, int) and count >= 0 else "N/A"

        st.markdown(
            f"""<div class="schema-table">
            {icon} <strong>{table}</strong> — {count_str} registros
            </div>""",
            unsafe_allow_html=True,
        )

    # Schema completo en expander
    with st.expander("📖 Ver esquema completo"):
        st.code(SCHEMA_CONTEXT, language="markdown")

    # Track ROI de exploración de esquema
    try:
        tracker = init_roi_tracker(st.session_state)
        tracker.track_action(
            module="data_assistant",
            action="nl2sql_schema_explore",
            quantity=1.0,
        )
    except Exception:
        pass


# =====================================================================
# ROI Tracking helpers
# =====================================================================
def _track_query_roi(result: NL2SQLResult):
    """Rastrea el ROI de una consulta NL2SQL."""
    try:
        tracker = init_roi_tracker(st.session_state)

        if result.success:
            # Determinar complejidad: si tiene JOIN/GROUP BY/subquery → complex
            sql_upper = (result.sql or "").upper()
            is_complex = any(kw in sql_upper for kw in ["JOIN", "GROUP BY", "HAVING", "UNION", "WITH "])
            action = "nl2sql_complex_query" if is_complex else "nl2sql_query"

            roi_info = tracker.track_action(
                module="data_assistant",
                action=action,
                quantity=1.0,
            )

            # Interpretación IA
            if result.interpretation:
                tracker.track_action(
                    module="data_assistant",
                    action="nl2sql_interpretation",
                    quantity=1.0,
                )

            # Generación de gráfica
            if result.chart_spec or result.chart_suggestion:
                tracker.track_action(
                    module="data_assistant",
                    action="nl2sql_chart",
                    quantity=1.0,
                )

            # Feedback inline: mostrar ahorro de esta consulta
            total_hrs = roi_info.get("hrs_saved", 0)
            total_val = roi_info.get("value", 0)
            if result.interpretation:
                total_hrs += 0.3
                total_val += 0.3 * tracker.get_user_hourly_rate()
            if result.chart_spec or result.chart_suggestion:
                total_hrs += 0.25
                total_val += 0.25 * tracker.get_user_hourly_rate()

            st.toast(
                f"💰 Ahorraste {total_hrs:.1f} hrs ≈ ${total_val:,.0f} MXN con esta consulta",
                icon="✅",
            )
    except Exception:
        pass  # No interrumpir el flujo por errores de tracking


# ─── Wiki: tracking de fallos y oferta de documentación ──────────────────────

_WIKI_MAX_FAILURES = 2  # Cuántos fallos consecutivos antes de ofrecer documentar


def _track_wiki_failure(result: NL2SQLResult, question: str):
    """
    Registra fallos consecutivos en session_state.
    Si hay éxito después de fallos, guarda el contexto de resolución.
    """
    if "wiki_failure_log" not in st.session_state:
        st.session_state["wiki_failure_log"] = []

    if not result.success:
        st.session_state["wiki_failure_log"].append({
            "question": question,
            "sql":      result.sql or "",
            "error":    result.error or "Error desconocido",
        })
        st.session_state.pop("wiki_successful_resolution", None)
    else:
        # Éxito: si había fallos previos, guardar el contexto completo de resolución
        if st.session_state.get("wiki_failure_log"):
            st.session_state["wiki_successful_resolution"] = {
                "question":       question,
                "sql":            result.sql or "",
                "interpretation": result.interpretation or "",
            }


def _offer_wiki_documentation(result: NL2SQLResult, question: str):
    """
    Muestra una oferta de documentación en la wiki cuando:
    - Hay N+ fallos consecutivos sin resolver, O
    - Hay fallos previos y ahora hubo éxito (problema resuelto)
    La oferta desaparece en cuanto el usuario acepta o descarta.
    """
    failures = st.session_state.get("wiki_failure_log", [])
    resolution = st.session_state.get("wiki_successful_resolution")

    # --- Caso 1: problema persistente sin resolver ---
    if not result.success and len(failures) >= _WIKI_MAX_FAILURES:
        st.warning(
            f"⚠️ Este problema lleva **{len(failures)} intentos fallidos** sin resolverse. "
            "¿Quieres guardarlo en la wiki para análisis posterior?",
            icon="📚",
        )
        col1, col2 = st.columns([1, 4])
        with col1:
            if st.button("📚 Documentar", key="wiki_doc_persistent", type="primary"):
                _auto_save_wiki(failures, resolved=False)
        with col2:
            if st.button("✕ Ignorar", key="wiki_ignore_persistent"):
                st.session_state["wiki_failure_log"] = []

    # --- Caso 2: resuelto después de fallos ---
    elif result.success and resolution and failures:
        st.success(
            f"✅ Problema resuelto tras **{len(failures)} intento(s) fallido(s)**. "
            "¿Quieres que lo documente en la wiki?",
            icon="🧠",
        )
        col1, col2 = st.columns([1, 4])
        with col1:
            if st.button("🧠 Sí, documentar", key="wiki_doc_resolved", type="primary"):
                _auto_save_wiki(failures, resolved=True, resolution=resolution)
        with col2:
            if st.button("✕ No", key="wiki_ignore_resolved"):
                st.session_state["wiki_failure_log"] = []
                st.session_state.pop("wiki_successful_resolution", None)


def _auto_save_wiki(
    failures: list[dict],
    resolved: bool,
    resolution: Optional[dict] = None,
):
    """Llama a GPT para generar la entrada wiki y la guarda en Neon."""
    from utils.problem_wiki import auto_generate_entry, add_problem

    conn_str = st.session_state.get("neon_url") or os.environ.get("NEON_DATABASE_URL", "")
    api_key  = st.session_state.get("openai_api_key") or os.environ.get("OPENAI_API_KEY", "")

    if not conn_str or not api_key:
        st.error("❌ Faltan credenciales para auto-documentar.")
        return

    with st.spinner("🧠 Generando entrada wiki con IA..."):
        problema = auto_generate_entry(
            connection_string=conn_str,
            openai_api_key=api_key,
            failed_attempts=failures,
            successful_attempt=resolution,
        )

    if problema is None:
        st.error("No se pudo generar la entrada wiki. Inténtalo manualmente.")
        return

    ok = add_problem(conn_str, problema)
    if ok:
        st.success(f"✅ Documentado como **{problema.codigo}**: *{problema.titulo}*")
        st.session_state["wiki_failure_log"] = []
        st.session_state.pop("wiki_successful_resolution", None)
    else:
        st.error("Error al guardar en la wiki. Revisa la conexión.")


def _track_export_roi():
    """Rastrea el ROI de una exportación CSV."""
    try:
        tracker = init_roi_tracker(st.session_state)
        tracker.track_action(
            module="data_assistant",
            action="nl2sql_export",
            quantity=1.0,
        )
    except Exception:
        pass


def _track_pdf_roi(has_chart: bool = False):
    """Rastrea el ROI de una exportación a PDF.
    
    Args:
        has_chart: Si el PDF incluye gráfica embebida
    """
    try:
        tracker = init_roi_tracker(st.session_state)
        
        # Trackear generación base del PDF
        pdf_roi = tracker.track_action(
            module="data_assistant",
            action="nl2sql_pdf_report",
            quantity=1.0,
        )
        
        # Valor adicional si incluye gráfica (ahorra screenshot manual)
        if has_chart:
            chart_roi = tracker.track_action(
                module="data_assistant",
                action="nl2sql_pdf_with_chart",
                quantity=1.0,
            )
            
            # Mostrar feedback combinado
            total_hrs = pdf_roi.get("hrs_saved", 0) + chart_roi.get("hrs_saved", 0)
            total_val = pdf_roi.get("value", 0) + chart_roi.get("value", 0)
            st.toast(
                f"📊 PDF con gráfica generado: {total_hrs:.2f} hrs ≈ ${total_val:,.0f} MXN ahorrados",
                icon="✅",
            )
        else:
            st.toast(
                f"📄 PDF generado: {pdf_roi.get('hrs_saved', 0):.2f} hrs ≈ ${pdf_roi.get('value', 0):,.0f} MXN ahorrados",
                icon="✅",
            )
    except Exception:
        pass


def _render_roi_panel():
    """Renderiza el panel de ROI en tiempo real para el Data Assistant."""
    try:
        tracker = init_roi_tracker(st.session_state)
        summary = tracker.get_summary()
        recent = tracker.get_recent_actions(limit=5)

        # Filtrar acciones del data_assistant
        da_actions = [a for a in tracker.session_state.roi_data.get("actions", [])
                      if a.get("module") == "data_assistant"]
        da_hrs = sum(a.get("hrs_saved", 0) for a in da_actions)
        da_value = sum(a.get("value", 0) for a in da_actions)
        da_count = len(da_actions)

        st.markdown("### 💰 ROI en Tiempo Real")

        # Métricas del Data Assistant esta sesión
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(
                "⏱️ Hrs ahorradas",
                f"{da_hrs:.1f}",
                help="Horas ahorradas con el Asistente de Datos esta sesión",
            )
        with col2:
            st.metric(
                "💵 Valor generado",
                f"${da_value:,.0f}",
                help="Valor monetario ahorrado (MXN)",
            )
        with col3:
            st.metric(
                "🔢 Consultas",
                f"{da_count}",
                help="Total de consultas procesadas",
            )

        # Desglose
        if da_actions:
            with st.expander("📋 Detalle de acciones", expanded=False):
                for a in reversed(da_actions[-10:]):
                    ts = a.get("timestamp")
                    ts_str = ts.strftime("%H:%M:%S") if hasattr(ts, "strftime") else str(ts)
                    action_label = {
                        "nl2sql_query": "🔍 Consulta SQL",
                        "nl2sql_complex_query": "🧠 Consulta compleja",
                        "nl2sql_interpretation": "💡 Interpretación IA",
                        "nl2sql_chart": "📊 Gráfica generada",
                        "nl2sql_export": "📥 Exportación CSV",
                        "nl2sql_schema_explore": "🗄️ Exploración schema",
                    }.get(a.get("action", ""), a.get("action", ""))
                    st.markdown(
                        f"**{ts_str}** · {action_label} · "
                        f"`{a.get('hrs_saved', 0):.2f} hrs` · "
                        f"`${a.get('value', 0):,.0f} MXN`"
                    )

        # Resumen global (toda la plataforma)
        with st.expander("🌐 ROI global de la plataforma", expanded=False):
            gcol1, gcol2 = st.columns(2)
            with gcol1:
                st.metric("Hoy total", f"${summary['today']['value']:,.0f}",
                          delta=f"{summary['today']['hrs']:.1f} hrs")
            with gcol2:
                st.metric("Este mes", f"${summary['month']['value']:,.0f}",
                          delta=f"{summary['month']['hrs']:.0f} hrs")
            if summary['today']['actions'] > 0:
                st.success(f"✨ {summary['today']['actions']} acciones hoy en toda la plataforma")

    except Exception:
        pass  # Silencioso si falla


def _render_roi_compact():
    """Widget ROI compacto para la barra lateral del chat con visualización de reloj circular."""
    try:
        tracker = init_roi_tracker(st.session_state)
        da_actions = [a for a in tracker.session_state.roi_data.get("actions", [])
                      if a.get("module") == "data_assistant"]
        da_hrs = sum(a.get("hrs_saved", 0) for a in da_actions)
        da_value = sum(a.get("value", 0) for a in da_actions)
        
        # Contar consultas únicas
        da_queries = len([a for a in da_actions if a.get("action") in ["nl2sql_query", "nl2sql_complex_query"]])
        
        # Contar reportes/exportaciones
        da_reports = len([a for a in da_actions if a.get("action") in ["nl2sql_pdf_report", "nl2sql_export"]])
        
        # Calcular días laborales
        da_workdays = da_hrs / 8.0  # 8 horas = 1 día laboral

        st.markdown("### 💰 Tu ROI")
        
        # Crear gauge circular tipo reloj para las horas ahorradas
        if PLOTLY_AVAILABLE and da_hrs > 0:
            # Gauge circular con apariencia de reloj
            max_hours = max(8, da_hrs * 1.2)  # Max dinámico basado en horas acumuladas
            
            fig = go.Figure(go.Indicator(
                mode="gauge+number",
                value=da_hrs,
                number={'suffix': " hrs", 'font': {'size': 24, 'color': '#2196F3'}},
                title={'text': "⏱️ Horas Ahorradas", 'font': {'size': 14}},
                gauge={
                    'axis': {'range': [0, max_hours], 'tickwidth': 1, 'tickcolor': "darkgray"},
                    'bar': {'color': '#2196F3', 'thickness': 0.75},
                    'bgcolor': "white",
                    'borderwidth': 2,
                    'bordercolor': "gray",
                    'steps': [
                        {'range': [0, max_hours * 0.33], 'color': '#E3F2FD'},
                        {'range': [max_hours * 0.33, max_hours * 0.67], 'color': '#BBDEFB'},
                        {'range': [max_hours * 0.67, max_hours], 'color': '#90CAF9'},
                    ],
                    'threshold': {
                        'line': {'color': "#4CAF50", 'width': 3},
                        'thickness': 0.75,
                        'value': da_hrs
                    }
                }
            ))
            
            fig.update_layout(
                height=200,
                margin=dict(l=20, r=20, t=40, b=20),
                paper_bgcolor="rgba(0,0,0,0)",
                font={'color': "darkgray", 'family': "Arial"},
            )
            
            st.plotly_chart(fig, use_container_width=True, key="roi_gauge")
            
            # Mostrar días laborales destacados
            if da_workdays >= 0.1:
                st.info(f"📅 **{da_workdays:.1f} días laborales** ahorrados (8 hrs = 1 día)")
        else:
            # Fallback si no hay plotly o no hay horas
            st.metric("⏱️ Hrs ahorradas", f"{da_hrs:.1f}")
        
        # Métrica de valor y acciones realizadas
        col1, col2 = st.columns(2)
        with col1:
            st.metric("💵 Valor", f"${da_value:,.0f}")
        with col2:
            # Mostrar desglose de acciones
            total_actions = da_queries + da_reports
            if da_reports > 0:
                action_label = f"{da_queries} consulta(s) + {da_reports} reporte(s)"
            else:
                action_label = f"{da_queries} consulta(s)"
            
            st.metric(
                "📊 Acciones", 
                f"{total_actions}",
                help=f"{action_label}. Las consultas incluyen: SQL + interpretación IA + gráfica. Los reportes incluyen: exportación formato profesional."
            )
        
        # Justificación de inversión - SIEMPRE visible si hay horas
        if da_hrs > 0:
            months_analyst = da_workdays / 22.0  # 22 días laborales por mes
            analyst_salary = tracker.get_analyst_salary()  # Obtener sueldo configurable
            annual_projection = da_value * 12 if da_hrs >= 1 else 0  # Solo proyección anual si hay >= 1 hora/mes
            
            st.markdown("---")
            st.markdown("### 💼 Justificación de Inversión")
            
            # Desglose de acciones completadas
            action_details = []
            if da_queries > 0:
                action_details.append(
                    f"**{da_queries} consulta(s):**\n"
                    f"  • ⚡ SQL automático\n"
                    f"  • 🤖 Interpretación IA\n"
                    f"  • 📊 Gráfica inteligente"
                )
            if da_reports > 0:
                action_details.append(
                    f"**{da_reports} reporte(s):**\n"
                    f"  • 📄 Exportación PDF/CSV\n"
                    f"  • 🎨 Formato profesional\n"
                    f"  • ✅ Listo para presentar"
                )
            
            if action_details:
                st.caption("ℹ️ " + "\n\n".join(action_details))
            
            # Equivalencia con analista
            if months_analyst >= 0.01:
                st.info(
                    f"📊 **Equivalencia de costo:**\n\n"
                    f"⏱️ {da_hrs:.1f} hrs = {da_workdays:.2f} días laborales\n\n"
                    f"👤 = **{months_analyst:.3f} mes(es)** de un analista\n\n"
                    f"💰 Costo evitado: **${months_analyst * analyst_salary:,.0f}** MXN"
                )
            
            # Proyección anual (solo si tiene suficientes datos)
            if da_hrs >= 1.0:
                st.success(
                    f"🎯 **Proyección anual:**\n\n"
                    f"Si mantienes este ritmo, ahorrarás aproximadamente:\n\n"
                    f"📅 {da_workdays * 12:.1f} días/año\n\n"
                    f"💵 **${annual_projection:,.0f}** MXN/año"
                )
            else:
                st.caption("💡 Acumula más horas para ver proyección anual")
            
    except Exception as e:
        logger.error(f"Error renderizando ROI compact: {e}")
        pass


def _render_chat_interface():
    """Interfaz principal de chat."""
    engine = _get_engine()
    if not engine:
        return

    # Inicializar historial de mensajes
    if "nl2sql_messages" not in st.session_state:
        st.session_state["nl2sql_messages"] = []

    # Mostrar mensajes existentes
    for msg_idx, msg in enumerate(st.session_state["nl2sql_messages"]):
        if msg["role"] == "user":
            with st.chat_message("user", avatar="🧑‍💼"):
                st.markdown(msg["content"])
        else:
            with st.chat_message("assistant", avatar="🤖"):
                _render_result_message(msg, msg_idx)

    # ── Selector de perfil soberano ───────────────────────────────────────────
    try:
        from utils.sovereign_profiles import PERFILES, PERFIL_DEFAULT, get_perfil, TIPOS_COMPROBANTE, TIPOS_IMPUESTO, METODOS_PAGO
        _perfiles_disponibles = PERFILES

        # Inicializar perfil activo en session_state
        if "sovereign_profile_key" not in st.session_state:
            st.session_state["sovereign_profile_key"] = PERFIL_DEFAULT
        _perfil_actual = _perfiles_disponibles.get(st.session_state["sovereign_profile_key"], {})
        if not _perfil_actual.get("enabled", True):
            st.session_state["sovereign_profile_key"] = PERFIL_DEFAULT

        with st.expander("🎯 Modo de análisis", expanded=True):
            # ── Botones de perfil predefinido ─────────────────────────────
            st.caption("Selecciona un perfil o personaliza los parámetros:")
            _blocked_profiles = [
                _p for _p in _perfiles_disponibles.values() if not _p.get("enabled", True)
            ]
            for _blocked in _blocked_profiles:
                st.caption(
                    f"{_blocked['icono']} {_blocked['label']} bloqueado hoy: {_blocked.get('blocked_reason', 'pendiente de dependencias.')}"
                )
            _cols = st.columns(3)
            _profile_keys = list(_perfiles_disponibles.keys())
            for _i, _pkey in enumerate(_profile_keys):
                _p = _perfiles_disponibles[_pkey]
                with _cols[_i % 3]:
                    _is_active = st.session_state["sovereign_profile_key"] == _pkey
                    _is_enabled = _p.get("enabled", True)
                    _help_text = _p["descripcion"]
                    if not _is_enabled and _p.get("blocked_reason"):
                        _help_text = f"{_help_text} Depende de: {_p['blocked_reason']}"
                    if st.button(
                        f"{_p['icono']} {_p['label']}",
                        key=f"profile_btn_{_pkey}",
                        help=_help_text,
                        use_container_width=True,
                        type="primary" if _is_active and _is_enabled else "secondary",
                        disabled=not _is_enabled,
):
                        st.session_state["sovereign_profile_key"] = _pkey
                        st.session_state.pop("sovereign_profile_custom", None)
                        # Setear explícitamente cada checkbox con los valores del nuevo perfil
                        for _tc in TIPOS_COMPROBANTE:
                            st.session_state[f"sc_tipo_{_tc}"] = _tc in _p["tipos_comprobante"]
                        for _ik in TIPOS_IMPUESTO:
                            st.session_state[f"sc_imp_{_ik}"] = _ik in _p["impuestos"]
                        for _mk in METODOS_PAGO:
                            st.session_state[f"sc_mp_{_mk}"] = _mk in _p["metodos_pago"]
                        st.session_state["sc_multi_moneda"] = _p.get("multi_moneda", False)
                        st.rerun()
                    if not _is_enabled and _p.get("blocked_reason"):
                        st.caption(f"Depende de: {_p['blocked_reason']}")

            st.divider()

            # ── Checkboxes de ajuste fino ─────────────────────────────────
            _pkey_activo = st.session_state["sovereign_profile_key"]
            _perfil_base = get_perfil(_pkey_activo)

            # Inicializar valores de checkboxes en session_state si no existen (primera carga)
            for _tc in TIPOS_COMPROBANTE:
                if f"sc_tipo_{_tc}" not in st.session_state:
                    st.session_state[f"sc_tipo_{_tc}"] = _tc in _perfil_base.get("tipos_comprobante", [])
            for _ik in TIPOS_IMPUESTO:
                if f"sc_imp_{_ik}" not in st.session_state:
                    st.session_state[f"sc_imp_{_ik}"] = _ik in _perfil_base.get("impuestos", [])
            for _mk in METODOS_PAGO:
                if f"sc_mp_{_mk}" not in st.session_state:
                    st.session_state[f"sc_mp_{_mk}"] = _mk in _perfil_base.get("metodos_pago", [])
            if "sc_multi_moneda" not in st.session_state:
                st.session_state["sc_multi_moneda"] = _perfil_base.get("multi_moneda", False)

            _col_a, _col_b, _col_c = st.columns(3)

            with _col_a:
                st.caption("**Tipo de comprobante**")
                _tipos_sel = []
                for _tc, _tc_label in TIPOS_COMPROBANTE.items():
                    if _tc == "T":
                        continue
                    if st.checkbox(_tc_label, key=f"sc_tipo_{_tc}"):
                        _tipos_sel.append(_tc)

            with _col_b:
                st.caption("**Impuestos**")
                _imp_sel = []
                for _ik, _il in TIPOS_IMPUESTO.items():
                    if st.checkbox(_il, key=f"sc_imp_{_ik}"):
                        _imp_sel.append(_ik)

            with _col_c:
                st.caption("**Método de pago**")
                _mp_sel = []
                for _mk, _ml in METODOS_PAGO.items():
                    if st.checkbox(_ml, key=f"sc_mp_{_mk}"):
                        _mp_sel.append(_mk)

                st.caption("**Moneda**")
                _multi_moneda = st.checkbox(
                    "Multi-moneda (USD/EUR → MXN)",
                    key="sc_multi_moneda",
                )

            # Construir perfil activo con ajustes del usuario
            _perfil_activo = {
                **_perfil_base,
                "tipos_comprobante": _tipos_sel,
                "impuestos":         _imp_sel,
                "metodos_pago":      _mp_sel,
                "multi_moneda":      _multi_moneda,
            }
            st.session_state["sovereign_profile_custom"] = _perfil_activo
            st.session_state["sovereign_profile_activo"] = _perfil_activo

            # Badge de scope activo
            _scope_parts = []
            if _tipos_sel:
                _scope_parts.append("Tipos: " + ", ".join(_tipos_sel))
            if _imp_sel:
                _scope_parts.append("Imp: " + ", ".join(_imp_sel))
            if _mp_sel:
                _scope_parts.append("Pago: " + ", ".join(_mp_sel))
            st.caption("📌 Scope activo: " + (" · ".join(_scope_parts) if _scope_parts else "Sin restricciones"))

    except ImportError:
        st.session_state["sovereign_profile_activo"] = None

    # ── Selector de período soberano ──────────────────────────────────────────
    _sovereign = st.session_state.get("sovereign_index", {})
    _meses = _sovereign.get("meses", [])

    if _meses:
        with st.expander("📅 Período de análisis", expanded=True):
            _col_slider, _col_gran = st.columns([3, 1])

            with _col_slider:
                _desde_default = st.session_state.get("sovereign_desde", _meses[0])
                _hasta_default = st.session_state.get("sovereign_hasta", _meses[-1])
                # Asegurar que los defaults existen en la lista
                if _desde_default not in _meses:
                    _desde_default = _meses[0]
                if _hasta_default not in _meses:
                    _hasta_default = _meses[-1]

                _rango = st.select_slider(
                    "Selecciona el rango de meses",
                    options=_meses,
                    value=(_desde_default, _hasta_default),
                    key="sovereign_slider",
                    label_visibility="collapsed",
                )
                st.session_state["sovereign_desde"] = _rango[0]
                st.session_state["sovereign_hasta"] = _rango[1]

            with _col_gran:
                _gran = st.radio(
                    "Granularidad",
                    options=["mensual", "trimestral", "anual", "total"],
                    index=["mensual", "trimestral", "anual", "total"].index(
                        st.session_state.get("sovereign_granularidad", "mensual")
                    ),
                    key="sovereign_granularidad",
                    help="Cómo se agrupa el tiempo en las consultas",
                )

            # Construir y guardar el período activo
            from utils.sovereign_periods import get_active_period
            _periodo_activo = get_active_period(
                _sovereign,
                st.session_state["sovereign_desde"],
                st.session_state["sovereign_hasta"],
                st.session_state["sovereign_granularidad"],
            )
            st.session_state["sovereign_periodo_activo"] = _periodo_activo

            if _periodo_activo:
                st.caption(
                    f"📌 **{_periodo_activo['label']}** · "
                    f"{_periodo_activo['desde']} → {_periodo_activo['hasta']} · "
                    f"granularidad: *{_periodo_activo['granularidad']}*"
                )
    else:
        st.session_state["sovereign_periodo_activo"] = {}

    # Verificar si hay pregunta pendiente (de ejemplo)
    pending = st.session_state.pop("nl2sql_pending_question", None)

    if not st.session_state["nl2sql_messages"]:
        _render_chat_guidance_empty_state()

    # Input de chat
    question = st.chat_input(
        "Escribe tu pregunta sobre los datos...",
        key="nl2sql_chat_input"
    )

    # Usar la pregunta pendiente si existe
    if pending and not question:
        question = pending

    if question:
        # ── Validador pre-vuelo ───────────────────────────────────────────
        from utils.sovereign_periods import validate_question
        _periodo_activo = st.session_state.get("sovereign_periodo_activo", {})
        _val = validate_question(question, _periodo_activo, _sovereign)

        if _val["nivel"] == "bloqueo":
            with st.chat_message("assistant", avatar="🤖"):
                st.error(_val["mensaje"])
                if _val.get("sugerencia"):
                    st.info(_val["sugerencia"])
            _append_chat_message({
                "role": "assistant",
                "content": f"{_val['mensaje']}\n\n{_val.get('sugerencia', '')}",
                "type": "error",
            })
            return

        if _val["nivel"] == "aviso":
            with st.chat_message("assistant", avatar="🤖"):
                st.warning(_val["mensaje"])

        # Mostrar pregunta del usuario
        with st.chat_message("user", avatar="🧑‍💼"):
            st.markdown(question)

        _append_chat_message({
            "role": "user",
            "content": question,
        })

        # Procesar con el engine
        with st.chat_message("assistant", avatar="🤖"):
            with st.spinner("🔍 Analizando pregunta y consultando datos..."):
                # empresa_id: primero del usuario logueado (multiempresa), si no hay usa el override manual
                empresa_id = _get_active_empresa_id()
                result = engine.ask(
                    question,
                    empresa_id=empresa_id,
                    periodo_soberano=st.session_state.get("sovereign_periodo_activo"),
                    sovereign_index=st.session_state.get("sovereign_index"),
                    sovereign_profile=st.session_state.get("sovereign_profile_activo"),
                )

            # --- ROI Tracking ---
            _track_query_roi(result)

            # --- Wiki: rastrear fallos para detección de problema persistente ---
            _track_wiki_failure(result, question)

            # Renderizar resultado
            msg_data = _build_result_message(result, question)
            new_idx = len(st.session_state["nl2sql_messages"])
            _render_result_message(msg_data, new_idx)

            _append_chat_message(msg_data)

        # --- Wiki: ofrecer documentar si hay problema persistente ---
        _offer_wiki_documentation(result, question)


def _build_result_message(result: NL2SQLResult, question: str = "") -> dict:
    """Construye un mensaje de resultado para almacenar en session_state."""
    msg = {
        "role": "assistant",
        "question": question,  # Guardar la pregunta original
        "content": result.interpretation or result.error or "Sin resultado",
        "sql": result.sql,
        "success": result.success,
        "execution_time": result.execution_time,
        "row_count": result.row_count,
        "chart_suggestion": result.chart_suggestion,
        "chart_spec": result.chart_spec,
        "error": result.error,
    }

    # Serializar DataFrame para session_state
    if result.dataframe is not None and not result.dataframe.empty:
        truncated_df = result.dataframe.head(MAX_SESSION_RESULT_ROWS)
        msg["dataframe_json"] = truncated_df.to_json(orient="split", date_format="iso")
        msg["dataframe_truncated"] = len(result.dataframe) > len(truncated_df)

    return msg


def _render_result_message(msg: dict, msg_idx: int = 0):
    """Renderiza un mensaje de resultado del asistente."""
    if msg.get("error"):
        st.error(msg["error"])
        if msg.get("sql"):
            with st.expander("🔍 SQL generado"):
                st.code(msg["sql"], language="sql")
        return

    # Interpretación
    st.markdown(msg["content"])

    # DataFrame
    df = None
    if "dataframe_json" in msg:
        try:
            df = pd.read_json(StringIO(msg["dataframe_json"]), orient="split")
            df = _coerce_numeric_like_columns(df)
        except Exception:
            df = None

    if df is not None and not df.empty:
        # Gráfica automática con spec de IA
        chart_type = msg.get("chart_suggestion", "table")
        chart_spec = msg.get("chart_spec", {})
        # IMPORTANTE: usar la pregunta ORIGINAL del usuario, no la interpretación de la IA
        question = msg.get("question", "") or msg.get("content", "")
        logger.info(f"📊 Render msg: chart_type={chart_type}, question='{question[:80]}', spec={chart_spec}")

        # Detectar si el resultado es un dashboard de KPIs (columnas kpi/valor/unidad)
        _cols_lower = [c.lower() for c in df.columns]
        _is_kpi_dashboard = (
            any(c in ('kpi', 'indicador', 'metrica', 'nombre') for c in _cols_lower)
            and any(c in ('valor', 'value') for c in _cols_lower)
        )

        # ============================================================
        # Pestañas: Gráfica | KPIs | Tabla | SQL
        # ============================================================
        if _is_kpi_dashboard:
            # KPI dashboard: no tiene sentido graficar — mostrar solo cards
            tab_kpi, tab_table, tab_sql = st.tabs(["📊 KPIs", "📋 Tabla", "🔍 SQL"])
            with tab_kpi:
                _render_kpi_tab(df)
        else:
            tab_chart, tab_kpi, tab_table, tab_sql = st.tabs(["📊 Gráfica", "📊 KPIs", "📋 Tabla", "🔍 SQL"])
            with tab_chart:
                _auto_chart(df, chart_type, question, chart_spec=chart_spec)
            with tab_kpi:
                _render_kpi_tab(df)

        with tab_table:
            table_df = _coerce_numeric_like_columns(df.copy())
            if "ranking" in table_df.columns:
                fact_col = None
                if "facturas" in table_df.columns:
                    fact_col = "facturas"
                elif "num_facturas" in table_df.columns:
                    fact_col = "num_facturas"

                if fact_col:
                    fact_values = pd.to_numeric(table_df[fact_col], errors="coerce").fillna(0)
                    tie_values = pd.Series([0.0] * len(table_df), index=table_df.index)
                    if "total_mxn" in table_df.columns:
                        tie_values = pd.to_numeric(table_df["total_mxn"], errors="coerce").fillna(0)

                    ranked_view = (
                        table_df.assign(_fact=fact_values, _tie=tie_values)
                        .sort_values(by=["_fact", "_tie"], ascending=[False, False], kind="mergesort")
                    )
                    ranked_view["_ranking_calc"] = range(1, len(ranked_view) + 1)
                    table_df["ranking"] = ranked_view["_ranking_calc"].reindex(table_df.index).astype(int)

            sort_options = ["(sin ordenar)"] + list(df.columns)
            default_sort_col = "(sin ordenar)"
            if "facturas" in table_df.columns:
                default_sort_col = "facturas"
            elif "num_facturas" in table_df.columns:
                default_sort_col = "num_facturas"

            sort_col = st.selectbox(
                "Ordenar tabla por",
                options=sort_options,
                index=sort_options.index(default_sort_col),
                key=f"table_sort_col_{msg_idx}",
            )
            sort_desc = st.toggle(
                "Descendente",
                value=True,
                key=f"table_sort_desc_{msg_idx}",
            )

            if sort_col != "(sin ordenar)":
                ascending = not sort_desc
                if pd.api.types.is_numeric_dtype(table_df[sort_col]):
                    table_df = table_df.sort_values(by=sort_col, ascending=ascending, kind="mergesort")
                else:
                    numeric_candidate = pd.to_numeric(
                        table_df[sort_col]
                        .astype(str)
                        .str.replace("$", "", regex=False)
                        .str.replace(",", "", regex=False)
                        .str.replace("%", "", regex=False),
                        errors="coerce",
                    )
                    if numeric_candidate.notna().any():
                        table_df = (
                            table_df.assign(_sort_key=numeric_candidate)
                            .sort_values(by="_sort_key", ascending=ascending, kind="mergesort")
                            .drop(columns=["_sort_key"])
                        )
                    else:
                        table_df = table_df.sort_values(by=sort_col, ascending=ascending, kind="mergesort")

            # Sort numérico ya aplicado — formatear a string para visualización con $, comas, etc.
            st.dataframe(
                _format_numeric_display_dataframe(table_df),
                use_container_width=True,
                hide_index=True,
            )
            st.caption(f"📋 {len(df)} fila(s) · {len(df.columns)} columna(s)")
            if msg.get("dataframe_truncated"):
                st.caption(
                    f"⚠️ Vista reducida a las primeras {MAX_SESSION_RESULT_ROWS} filas en el historial de sesión."
                )

        with tab_sql:
            st.code(msg.get("sql", ""), language="sql")
            exec_time = msg.get("execution_time", 0)
            row_count = msg.get("row_count", 0)
            st.caption(f"⏱️ {exec_time:.2f}s · {row_count} filas")

        # ============================================================
        # Generar PDF y CSV DESPUÉS de _auto_chart (para tener la fig)
        # ============================================================
        pdf_bytes = None
        pdf_error = None
        try:
            from utils.export_helper import crear_reporte_pdf_ejecutivo
            
            # Recuperar figura guardada por _auto_chart
            fig_for_pdf = st.session_state.get('last_plotly_fig', None)
            
            # Generar PDF
            pdf_bytes = crear_reporte_pdf_ejecutivo(
                pregunta=msg.get("question", question),
                interpretacion=msg.get("content", ""),
                df=df,
                sql=msg.get("sql", ""),
                chart_type=chart_type,
                empresa=st.session_state.get("empresa_actual", {}).get("nombre", "CIMA"),
                fig=fig_for_pdf
            )
        except Exception as e:
            logger.error(f"Error generando PDF: {e}")
            pdf_error = str(e)
        
        # Generar CSV
        csv = df.to_csv(index=False)

        # Botones destacados para exportar
        st.markdown("---")
        col_export_pdf, col_export_csv, col_spacer = st.columns([2, 2, 6])
        
        with col_export_pdf:
            if pdf_bytes:
                # Detectar si se incluyó gráfica
                has_chart = fig_for_pdf is not None
                
                # Mostrar botón de descarga
                if st.download_button(
                    "📄 Generar Reporte PDF",
                    pdf_bytes,
                    "reporte_ejecutivo.pdf",
                    "application/pdf",
                    key=f"btn_pdf_{msg_idx}_{hash(msg.get('sql', ''))}",
                    use_container_width=True
                ):
                    # Track ROI cuando se hace clic
                    _track_pdf_roi(has_chart=has_chart)
            else:
                st.button(
                    "📄 PDF no disponible", 
                    disabled=True, 
                    use_container_width=True,
                    key=f"btn_pdf_disabled_{msg_idx}_{hash(msg.get('sql', ''))}"
                )
                if pdf_error:
                    st.caption(f"⚠️ Error: {pdf_error[:50]}...")
        
        with col_export_csv:
            st.download_button(
                "📥 Descargar CSV",
                csv,
                "resultado_consulta.csv",
                "text/csv",
                key=f"btn_csv_{msg_idx}_{hash(msg.get('sql', ''))}",
                use_container_width=True
            )
        
        st.markdown("---")

    else:
        # Solo SQL si no hay datos
        if msg.get("sql"):
            with st.expander("🔍 SQL generado"):
                st.code(msg["sql"], language="sql")


def _render_history():
    """Panel de historial de consultas."""
    st.markdown("### 🕰️ Historial de Consultas")

    engine = _get_engine()
    if not engine:
        st.info("Conecta primero para ver el historial")
        return

    history = engine.get_history()

    if not history:
        st.info("Aún no has hecho consultas. ¡Pregunta algo!")
        return

    col_clear, _ = st.columns([1, 3])
    with col_clear:
        if st.button("🗑️ Limpiar historial"):
            engine.clear_history()
            st.session_state["nl2sql_messages"] = []
            st.rerun()

    for i, result in enumerate(history[:20]):
        status = "✅" if result.success else "❌"
        time_str = result.timestamp.strftime("%H:%M")

        with st.expander(
            f"{status} {time_str} — {result.question[:60]}...",
            expanded=False,
        ):
            if result.success:
                st.markdown(f"**Interpretación:** {result.interpretation}")
                st.code(result.sql, language="sql")
                st.caption(
                    f"⏱️ {result.execution_time:.2f}s · "
                    f"{result.row_count} filas · "
                    f"📊 {result.chart_suggestion}"
                )
            else:
                # Aviso de perfil soberano → naranja, no rojo
                if result.error and result.error.startswith("🎯"):
                    st.warning(result.error)
                else:
                    st.error(result.error)
                if result.sql:
                    st.code(result.sql, language="sql")

            # Re-ejecutar pregunta
            if st.button(
                "🔁 Repetir consulta",
                key=f"retry_{i}_{hash(result.question)}",
            ):
                st.session_state["nl2sql_pending_question"] = result.question
                st.rerun()


def _render_sql_playground():
    """Playground para escribir SQL directamente."""
    st.markdown("### 🛠️ SQL Playground")
    st.caption("Escribe y ejecuta SQL directamente (solo SELECT)")

    user = get_current_user()
    if not user or not user.is_superadmin:
        st.warning("🔒 El SQL Playground está disponible solo para superadmin.")
        return

    engine = _get_engine()
    if not engine:
        st.warning("Conecta primero a la base de datos")
        return

    sql_input = st.text_area(
        "Escribe tu consulta SQL:",
        height=150,
        placeholder="SELECT receptor_nombre, COUNT(*) AS facturas, SUM(total) AS total\nFROM cfdi_ventas\nGROUP BY receptor_nombre\nORDER BY total DESC\nLIMIT 10;",
        key="sql_playground_input",
    )

    col1, col2 = st.columns([1, 3])

    with col1:
        execute_btn = st.button("▶️ Ejecutar", type="primary", use_container_width=True)

    with col2:
        # Validación en tiempo real
        if sql_input:
            is_valid, err_msg = validate_sql_static(sql_input)
            if is_valid:
                st.success("✅ SQL válido")
            else:
                st.error(f"🛡️ {err_msg}")

    if execute_btn and sql_input:
        is_valid, err_msg = validate_sql_static(sql_input)
        if not is_valid:
            st.error(f"🛡️ Validación fallida: {err_msg}")
            return

        with st.spinner("Ejecutando consulta..."):
            try:
                import time
                t0 = time.time()
                df = engine.execute_query(sql_input)
                elapsed = time.time() - t0

                st.success(f"✅ {len(df)} filas en {elapsed:.2f}s")

                df = _coerce_numeric_like_columns(df)

                st.dataframe(
                    df,
                    use_container_width=True,
                    hide_index=True,
                    column_config=_build_numeric_column_config(df),
                )

                # Exportar
                csv = df.to_csv(index=False)
                st.download_button("📥 Descargar CSV", csv, "sql_result.csv", "text/csv")

            except Exception as e:
                st.error(f"❌ Error: {e}")


# =====================================================================
# Función principal
# =====================================================================
def run():
    """Punto de entrada del módulo Asistente de Datos."""

    # Verificar dependencias
    if not PSYCOPG2_AVAILABLE:
        st.error("❌ psycopg2 no está instalado. Ejecuta: `pip install psycopg2-binary`")
        return
    if not OPENAI_AVAILABLE:
        st.error("❌ openai no está instalado. Ejecuta: `pip install openai`")
        return

    # Verificar permiso de rol
    _user = get_current_user()
    if _user and not _user.can_use_ai():
        st.warning("🔒 Tu rol no tiene acceso al Asistente de Datos. Contacta al administrador.")
        return

    # Hero
    _render_hero()

    if not _is_premium_passkey_valid():
        st.warning("🔒 El Asistente de Datos requiere que actives primero el Passkey Premium en el sidebar.")
        return

    # Auto-conectar si las credenciales están en variables de entorno (modo SaaS)
    _auto_connect_from_env()

    # Verificar conexión
    is_connected = st.session_state.get("nl2sql_connected", False)

    if not is_connected:
        _render_connection_setup()
        return

    # Barra de estado de conexión
    col_status, col_disconnect = st.columns([4, 1])
    with col_status:
        model = st.session_state.get("nl2sql_model", "gpt-4o")
        st.success(f"🟢 Conectado a Neon · Modelo: **{model}**")
    with col_disconnect:
        if st.button("🔌 Desconectar"):
            st.session_state["nl2sql_connected"] = False
            st.session_state["nl2sql_disable_auto_connect"] = True
            _invalidate_engine()
            st.session_state["nl2sql_messages"] = []
            st.rerun()

    # Cargar catálogo y framework guiado para runtime
    _load_guided_catalog_runtime()
    _get_or_build_guided_framework()

    current_stage_modes, second_stage_options = _get_stage_mode_config()
    if st.session_state.get("nl2sql_mode") not in current_stage_modes:
        st.session_state["nl2sql_mode"] = current_stage_modes[0]

    # Navegación horizontal
    mode = st.radio(
        "Modo:",
        current_stage_modes,
        horizontal=True,
        key="nl2sql_mode",
    )

    _render_second_stage_options(second_stage_options)

    st.markdown("---")

    # Layout: contenido principal + sidebar de ejemplos
    if mode == "💬 Chat":
        col_main, col_side = st.columns([3, 1])

        with col_main:
            _render_chat_interface()

        with col_side:
            _render_sidebar_examples()

    elif mode == "🧭 Guiado":
        _render_guided_interface()


if __name__ == "__main__":
    run()
