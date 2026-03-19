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
        neon_url = st.session_state.get("nl2sql_neon_url", "")
        api_key = st.session_state.get("nl2sql_api_key", "")

        if not neon_url or not api_key:
            return None

        try:
            engine = NL2SQLEngine(
                connection_string=neon_url,
                api_key=api_key,
                model=st.session_state.get("nl2sql_model", "gpt-4o"),
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

    # Aplicar formato de moneda/porcentaje
    display_num_cols = display_df.select_dtypes(include=['int64', 'float64', 'int32', 'float32']).columns
    # Excluir columnas de conteo del formato monetario
    count_keywords = ['num_', 'count', 'cantidad', 'total_clientes', 'total_facturas', 'conteo']
    col_config = {}
    for col in display_num_cols:
        is_count = any(kw in col.lower() for kw in count_keywords)
        if 'pct' in col.lower() or 'porcentaje' in col.lower() or col.lower().endswith('_pct') or '%' in col:
            col_config[col] = st.column_config.NumberColumn(format="%.1f%%")
        elif not is_count and any(kw in col.lower() for kw in ['total', 'monto', 'facturacion', 'venta', 'importe', 'saldo', 'mxn', 'compra', 'promedio', 'media', 'desviacion', 'minimo', 'maximo', 'precio']):
            col_config[col] = st.column_config.NumberColumn(format="$%.2f")

    st.dataframe(display_df, use_container_width=True, hide_index=True, column_config=col_config)


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
        st.dataframe(df, use_container_width=True, hide_index=True)
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
            donut_df = plot_df.head(15).copy()
            if donut_df[x_col].dtype != 'object':
                donut_df[x_col] = donut_df[x_col].astype(str)
            fig = px.pie(
                donut_df,
                names=x_col,
                values=y_col,
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
    count_keywords = ['num_', 'count', 'cantidad', 'total_clientes', 'total_facturas', 'conteo']
    col_config = {}
    for col in num_cols:
        is_count = any(kw in col.lower() for kw in count_keywords)
        if 'pct' in col.lower() or 'porcentaje' in col.lower() or col.lower().endswith('_pct') or '%' in col:
            col_config[col] = st.column_config.NumberColumn(format="%.1f%%")
        elif not is_count and any(kw in col.lower() for kw in ['total', 'monto', 'facturacion', 'venta', 'importe', 'saldo', 'mxn', 'compra']):
            col_config[col] = st.column_config.NumberColumn(format="$%.2f")

    st.dataframe(df, use_container_width=True, hide_index=True, column_config=col_config)


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
                    {"Métrica": c.replace('_', ' ').title(), "Valor": float(df[c].iloc[0])}
                    for c in comparable_cols
                ]
                stat_df = pd.DataFrame(stat_data)
                fig = px.bar(
                    stat_df, x="Valor", y="Métrica",
                    orientation="h",
                    title=f"📐 {title}",
                    color="Valor",
                    color_continuous_scale="Viridis",
                    text_auto="$,.2f",
                )
                fig.update_layout(
                    yaxis=dict(autorange="reversed"),
                    showlegend=False,
                    height=max(300, len(stat_data) * 50),
                )
                fig.update_traces(textposition="outside")
                _render_plotly_chart_and_save(fig, use_container_width=True)

            # Si hay percentiles → box plot simulado
            p25_col = next((c for c in percentile_cols if '25' in c), None)
            p50_col = next((c for c in percentile_cols + central_cols if any(k in c.lower() for k in ['mediana', 'median', '50'])), None)
            p75_col = next((c for c in percentile_cols if '75' in c), None)
            min_col = next((c for c in range_cols if any(k in c.lower() for k in ['min'])), None)
            max_col = next((c for c in range_cols if any(k in c.lower() for k in ['max'])), None)

            if p25_col and p75_col:
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

                fig = go.Figure()
                # Box plot horizontal para mejor legibilidad
                fig.add_trace(go.Box(
                    q1=[p25], median=[p50], q3=[p75],
                    lowerfence=[fence_lo], upperfence=[fence_hi],
                    mean=[avg_val],
                    name="",
                    marker_color="#2196F3",
                    boxmean=True,
                    orientation="h",
                    hoverinfo="text",
                    hovertext=(
                        f"Mín: ${mn:,.2f}<br>"
                        f"P25: ${p25:,.2f}<br>"
                        f"Mediana: ${p50:,.2f}<br>"
                        f"Media: ${avg_val:,.2f}<br>"
                        f"P75: ${p75:,.2f}<br>"
                        f"Máx: ${mx:,.2f}"
                    ),
                ))

                # Marcar outliers como puntos separados
                all_outliers = outliers_lo + outliers_hi
                if all_outliers:
                    fig.add_trace(go.Scatter(
                        x=all_outliers,
                        y=[0] * len(all_outliers),
                        mode="markers+text",
                        marker=dict(color="#FF5722", size=12, symbol="diamond"),
                        text=[f"${v:,.2f}" for v in all_outliers],
                        textposition="top center",
                        name="Outliers",
                        hoverinfo="text",
                        hovertext=[f"Outlier: ${v:,.2f}" for v in all_outliers],
                    ))

                # Anotaciones de valores clave
                for val, label, color in [
                    (p25, "P25", "#64B5F6"),
                    (p50, "Mediana", "#FFFFFF"),
                    (p75, "P75", "#64B5F6"),
                    (avg_val, "μ", "#FFC107"),
                ]:
                    fig.add_annotation(
                        x=val, y=0,
                        text=f"{label}: ${val:,.2f}",
                        showarrow=True, arrowhead=2,
                        font=dict(size=10, color=color),
                        arrowcolor=color,
                        ax=0, ay=-35 if label in ("P25", "P75") else 35,
                    )

                fig.update_layout(
                    title=f"📦 Distribución — {title}",
                    showlegend=bool(all_outliers),
                    height=350,
                    xaxis=dict(
                        title="Valor ($)",
                        tickformat="$,.0f",
                    ),
                    yaxis=dict(showticklabels=False),
                    margin=dict(l=20, r=20, t=50, b=40),
                )
                _render_plotly_chart_and_save(fig, use_container_width=True)

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
    st.dataframe(df, use_container_width=True, hide_index=True)


# =====================================================================
# Componentes de UI
# =====================================================================
def _render_hero():
    """Hero banner."""
    st.markdown(ASSISTANT_CSS, unsafe_allow_html=True)
    st.markdown("""
    <div class="assistant-hero">
        <h2>🤖 Asistente de Datos</h2>
        <p>Haz preguntas en español sobre tus datos de facturación CFDI y obtén 
        respuestas instantáneas con tablas, gráficas e interpretación inteligente.</p>
    </div>
    """, unsafe_allow_html=True)


def _auto_connect_from_env():
    """Si las credenciales están en variables de entorno y no hay sesión activa, conecta automáticamente."""
    if st.session_state.get("nl2sql_connected"):
        return  # Ya conectado, nada que hacer

    neon_url = os.getenv("NEON_DATABASE_URL", "")
    api_key = os.getenv("OPENAI_API_KEY", "")

    if not neon_url or not api_key:
        return  # Sin env vars → mostrar formulario manual

    # Establecer credenciales en session_state silenciosamente
    st.session_state["nl2sql_neon_url"] = neon_url
    st.session_state["nl2sql_api_key"] = api_key
    if "nl2sql_model" not in st.session_state:
        st.session_state["nl2sql_model"] = "gpt-4o"

    engine = _get_engine()
    if engine:
        ok, _ = engine.test_connection()
        if ok:
            st.session_state["nl2sql_connected"] = True


def _render_connection_setup():
    """Panel de configuración de conexión."""
    st.markdown("### 🔌 Configurar Conexión")

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
            value=st.session_state.get("nl2sql_neon_url", os.getenv("NEON_DATABASE_URL", "")),
            help="postgresql://user:pass@host/db?sslmode=require",
            key="input_neon_url",
        )

    with col2:
        api_key = st.text_input(
            "API Key de OpenAI",
            type="password",
            value=st.session_state.get("nl2sql_api_key", os.getenv("OPENAI_API_KEY", "")),
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


def _render_sidebar_examples():
    """Preguntas de ejemplo en la barra lateral derecha."""
    examples = get_example_questions()

    st.markdown("### 💡 Preguntas de ejemplo")
    st.caption("Haz clic para copiar una pregunta")

    for cat in examples:
        with st.expander(f"{cat['icon']} {cat['category']}", expanded=False):
            for q in cat["questions"]:
                if st.button(
                    q,
                    key=f"ex_{hash(q)}",
                    use_container_width=True,
                ):
                    st.session_state["nl2sql_pending_question"] = q
                    st.rerun()


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
        counts = engine.get_table_counts()
        date_range = engine.get_date_range()

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

    # Verificar si hay pregunta pendiente (de ejemplo)
    pending = st.session_state.pop("nl2sql_pending_question", None)

    # Input de chat
    question = st.chat_input(
        "Escribe tu pregunta sobre los datos...",
        key="nl2sql_chat_input"
    )

    # Usar la pregunta pendiente si existe
    if pending and not question:
        question = pending

    if question:
        # Mostrar pregunta del usuario
        with st.chat_message("user", avatar="🧑‍💼"):
            st.markdown(question)

        st.session_state["nl2sql_messages"].append({
            "role": "user",
            "content": question,
        })

        # Procesar con el engine
        with st.chat_message("assistant", avatar="🤖"):
            with st.spinner("🔍 Analizando pregunta y consultando datos..."):
                # empresa_id: primero del usuario logueado (multiempresa), si no hay usa el override manual
                empresa_id = (
                    st.session_state.get("empresa_id")          # seteado en login por usuario
                    or st.session_state.get("nl2sql_empresa_id")  # override manual (superadmin)
                )
                result = engine.ask(question, empresa_id=empresa_id)

            # --- ROI Tracking ---
            _track_query_roi(result)

            # Renderizar resultado
            msg_data = _build_result_message(result, question)
            new_idx = len(st.session_state["nl2sql_messages"])
            _render_result_message(msg_data, new_idx)

            st.session_state["nl2sql_messages"].append(msg_data)


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
        msg["dataframe_json"] = result.dataframe.to_json(orient="split", date_format="iso")

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
            # Tabla cruda completa con formato de moneda/porcentaje
            display_num_cols = df.select_dtypes(include=['int64', 'float64', 'int32', 'float32']).columns
            count_keywords = ['num_', 'count', 'cantidad', 'total_clientes', 'total_facturas', 'conteo']
            col_config = {}
            for col in display_num_cols:
                is_count = any(kw in col.lower() for kw in count_keywords)
                if 'pct' in col.lower() or 'porcentaje' in col.lower() or col.lower().endswith('_pct') or '%' in col:
                    col_config[col] = st.column_config.NumberColumn(format="%.1f%%")
                elif not is_count and any(kw in col.lower() for kw in ['total', 'monto', 'facturacion', 'venta',
                                                                        'importe', 'saldo', 'mxn', 'compra',
                                                                        'promedio', 'media', 'desviacion',
                                                                        'minimo', 'maximo', 'precio',
                                                                        'mediana', 'percentil']):
                    col_config[col] = st.column_config.NumberColumn(format="$%.2f")
            st.dataframe(df, use_container_width=True, hide_index=True, column_config=col_config)
            st.caption(f"📋 {len(df)} fila(s) · {len(df.columns)} columna(s)")

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

                # Mostrar formato de moneda automáticamente
                num_cols = df.select_dtypes(include=['int64', 'float64']).columns
                col_config = {}
                for col in num_cols:
                    if any(kw in col.lower() for kw in ['total', 'monto', 'venta', 'importe', 'saldo']):
                        col_config[col] = st.column_config.NumberColumn(format="$%.2f")

                st.dataframe(df, use_container_width=True, hide_index=True, column_config=col_config)

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

    # Hero
    _render_hero()

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
            _invalidate_engine()
            st.session_state["nl2sql_messages"] = []
            st.rerun()

    # Navegación horizontal
    mode = st.radio(
        "Modo:",
        ["💬 Chat", "🛠️ SQL Playground", "🗄️ Esquema", "🕰️ Historial", "💰 ROI"],
        horizontal=True,
        key="nl2sql_mode",
    )

    st.markdown("---")

    # Layout: contenido principal + sidebar de ejemplos
    if mode == "💬 Chat":
        col_main, col_side = st.columns([3, 1])

        with col_main:
            _render_chat_interface()

        with col_side:
            _render_sidebar_examples()
            st.markdown("---")
            _render_roi_compact()

    elif mode == "🛠️ SQL Playground":
        _render_sql_playground()

    elif mode == "🗄️ Esquema":
        _render_schema_explorer()

    elif mode == "🕰️ Historial":
        _render_history()

    elif mode == "💰 ROI":
        _render_roi_panel()


if __name__ == "__main__":
    run()
