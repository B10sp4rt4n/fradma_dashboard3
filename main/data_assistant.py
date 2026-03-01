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
    background: #f8f9fa;
    border: 1px solid #dee2e6;
    border-radius: 8px;
    padding: 0.5rem 1rem;
    cursor: pointer;
    transition: all 0.2s;
    margin: 0.25rem 0;
    width: 100%;
    text-align: left;
}
.example-btn:hover {
    background: #e9ecef;
    border-color: #adb5bd;
}
.schema-table {
    background: #f8f9fa;
    border: 1px solid #dee2e6;
    border-radius: 8px;
    padding: 0.75rem 1rem;
    margin: 0.25rem 0;
    font-size: 0.85rem;
}
.history-entry {
    background: #fff;
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    padding: 0.75rem 1rem;
    margin: 0.5rem 0;
    cursor: pointer;
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

    spec = chart_spec or {}
    num_cols = df.select_dtypes(include=['int64', 'float64', 'int32', 'float32']).columns.tolist()
    cat_cols = df.select_dtypes(include=['object', 'datetime64']).columns.tolist()

    # Auto-detect mejores columnas si spec no las indica
    x_col = spec.get("x") or (cat_cols[0] if cat_cols else df.columns[0])
    y_col = spec.get("y") or (num_cols[0] if num_cols else df.columns[-1])
    color_col = spec.get("color")
    title = spec.get("title") or question[:100]
    top_n = spec.get("top_n", 30)
    sort_order = spec.get("sort")  # "asc" | "desc" | None

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

    # Si es consulta estadística con 1 fila → stats_summary
    if len(df) == 1 and len(num_cols) >= 3 and (is_stats_query or has_stat_cols):
        chart_type = "stats_summary"
    # Si tiene varias filas con columnas estadísticas → aún puede ser stats o box
    elif len(df) > 1 and has_stat_cols and chart_type in ("table", "metric"):
        chart_type = "stats_summary"
    # Si 1 fila y numéricos pero NO stats → metric cards
    elif len(df) == 1 and len(num_cols) >= 1 and chart_type not in ("stats_summary", "gauge"):
        chart_type = "metric"
    if len(df) <= 2 and not num_cols:
        chart_type = "table"

    # Preparar subset
    plot_df = df.head(top_n).copy()
    if sort_order == "desc" and y_col in plot_df.columns:
        plot_df = plot_df.sort_values(y_col, ascending=False)
    elif sort_order == "asc" and y_col in plot_df.columns:
        plot_df = plot_df.sort_values(y_col, ascending=True)

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
            st.plotly_chart(fig, use_container_width=True)
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
            st.plotly_chart(fig, use_container_width=True)
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
            st.plotly_chart(fig, use_container_width=True)
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
            st.plotly_chart(fig, use_container_width=True)
            return

        # --- BAR (vertical) ---
        if chart_type == "bar" and num_cols:
            fig = px.bar(
                plot_df, x=x_col, y=y_col,
                title=title,
                color=color_col or y_col,
                color_continuous_scale="Viridis" if not color_col else None,
                color_discrete_sequence=CHART_COLORS if color_col else None,
                text_auto=True,
            )
            fig.update_layout(xaxis_tickangle=-45, showlegend=bool(color_col))
            fig.update_traces(textposition="outside", texttemplate="%{y:,.0f}")
            st.plotly_chart(fig, use_container_width=True)
            return

        # --- HBAR (horizontal) ---
        if chart_type == "hbar" and num_cols:
            fig = px.bar(
                plot_df, x=y_col, y=x_col,
                title=title,
                orientation="h",
                color=color_col or y_col,
                color_continuous_scale="Viridis" if not color_col else None,
                text_auto=True,
            )
            fig.update_layout(yaxis=dict(autorange="reversed"), showlegend=bool(color_col))
            fig.update_traces(textposition="outside", texttemplate="%{x:,.0f}")
            st.plotly_chart(fig, use_container_width=True)
            return

        # --- STACKED BAR ---
        if chart_type == "stacked_bar" and color_col and num_cols:
            fig = px.bar(
                plot_df, x=x_col, y=y_col,
                color=color_col,
                title=title,
                color_discrete_sequence=CHART_COLORS,
                barmode="stack",
                text_auto=True,
            )
            fig.update_layout(xaxis_tickangle=-45)
            st.plotly_chart(fig, use_container_width=True)
            return

        # --- GROUPED BAR ---
        if chart_type == "grouped_bar" and color_col and num_cols:
            fig = px.bar(
                plot_df, x=x_col, y=y_col,
                color=color_col,
                title=title,
                color_discrete_sequence=CHART_COLORS,
                barmode="group",
                text_auto=True,
            )
            fig.update_layout(xaxis_tickangle=-45)
            st.plotly_chart(fig, use_container_width=True)
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
            st.plotly_chart(fig, use_container_width=True)
            return

        # --- AREA ---
        if chart_type == "area" and num_cols:
            fig = px.area(
                plot_df, x=x_col, y=y_col,
                title=title,
                color=color_col,
                color_discrete_sequence=CHART_COLORS,
            )
            st.plotly_chart(fig, use_container_width=True)
            return

        # --- PIE ---
        if chart_type == "pie" and cat_cols and num_cols:
            fig = px.pie(
                plot_df.head(15),
                names=x_col,
                values=y_col,
                title=title,
                color_discrete_sequence=CHART_COLORS,
            )
            fig.update_traces(textposition="inside", textinfo="percent+label")
            st.plotly_chart(fig, use_container_width=True)
            return

        # --- DONUT ---
        if chart_type == "donut" and cat_cols and num_cols:
            fig = px.pie(
                plot_df.head(15),
                names=x_col,
                values=y_col,
                title=title,
                hole=0.45,
                color_discrete_sequence=CHART_COLORS,
            )
            fig.update_traces(textposition="inside", textinfo="percent+label")
            st.plotly_chart(fig, use_container_width=True)
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
            st.plotly_chart(fig, use_container_width=True)
            return

        # --- TREEMAP ---
        if chart_type == "treemap" and cat_cols and num_cols:
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
            st.plotly_chart(fig, use_container_width=True)
            return

        # --- FUNNEL ---
        if chart_type == "funnel" and cat_cols and num_cols:
            fig = px.funnel(
                plot_df, x=y_col, y=x_col,
                title=title,
                color_discrete_sequence=CHART_COLORS,
            )
            st.plotly_chart(fig, use_container_width=True)
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
            st.plotly_chart(fig, use_container_width=True)
            return

    except Exception:
        pass  # Fallback a tabla

    # Default: tabla con formato
    col_config = {}
    for col in num_cols:
        if any(kw in col.lower() for kw in ['total', 'monto', 'factur', 'venta', 'importe', 'saldo', 'mxn', 'compra']):
            col_config[col] = st.column_config.NumberColumn(format="$%.2f")
        elif 'pct' in col.lower() or 'porcentaje' in col.lower() or '%' in col:
            col_config[col] = st.column_config.NumberColumn(format="%.1f%%")

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
    try:
        # --- ESCENARIO A: 1 fila con múltiples estadísticas ---
        if len(df) == 1:
            st.markdown(f"#### 📊 {title}")

            # Clasificar columnas por tipo de estadística
            count_cols = [c for c in num_cols if any(k in c.lower() for k in ['count', 'num_factura', 'num_concepto', 'total_factura', 'total_concepto'])]
            central_cols = [c for c in num_cols if any(k in c.lower() for k in ['media', 'promedio', 'avg', 'mediana', 'median', 'moda', 'precio_promedio', 'precio_mediana'])]
            dispersion_cols = [c for c in num_cols if any(k in c.lower() for k in ['desviacion', 'stddev', 'varianza', 'variance'])]
            range_cols = [c for c in num_cols if any(k in c.lower() for k in ['minimo', 'min', 'maximo', 'max'])]
            percentile_cols = [c for c in num_cols if any(k in c.lower() for k in ['percentil', 'quartil', 'p25', 'p50', 'p75'])]
            other_cols = [c for c in num_cols if c not in count_cols + central_cols + dispersion_cols + range_cols + percentile_cols]

            # Tarjetas de conteo
            if count_cols:
                st.markdown("**📋 Muestra**")
                cols_ui = st.columns(len(count_cols))
                for i, col in enumerate(count_cols):
                    with cols_ui[i]:
                        v = df[col].iloc[0]
                        st.metric(col.replace('_', ' ').title(), f"{v:,.0f}" if isinstance(v, (int, float)) else str(v))

            # Medidas de tendencia central
            if central_cols:
                st.markdown("**📍 Tendencia Central**")
                cols_ui = st.columns(min(len(central_cols), 4))
                for i, col in enumerate(central_cols[:4]):
                    with cols_ui[i]:
                        v = df[col].iloc[0]
                        st.metric(col.replace('_', ' ').title(),
                                  f"${v:,.2f}" if isinstance(v, (int, float)) and abs(v) > 1 else f"{v:,.4f}")

            # Dispersión
            if dispersion_cols:
                st.markdown("**📏 Dispersión**")
                cols_ui = st.columns(min(len(dispersion_cols), 4))
                for i, col in enumerate(dispersion_cols[:4]):
                    with cols_ui[i]:
                        v = df[col].iloc[0]
                        st.metric(col.replace('_', ' ').title(),
                                  f"${v:,.2f}" if isinstance(v, (int, float)) and abs(v) > 1 else f"{v:,.4f}")

            # Rango
            if range_cols:
                st.markdown("**↕️ Rango**")
                cols_ui = st.columns(min(len(range_cols), 4))
                for i, col in enumerate(range_cols[:4]):
                    with cols_ui[i]:
                        v = df[col].iloc[0]
                        st.metric(col.replace('_', ' ').title(),
                                  f"${v:,.2f}" if isinstance(v, (int, float)) and abs(v) > 1 else f"{v:,.4f}")

            # Percentiles
            if percentile_cols:
                st.markdown("**📊 Percentiles**")
                cols_ui = st.columns(min(len(percentile_cols), 4))
                for i, col in enumerate(percentile_cols[:4]):
                    with cols_ui[i]:
                        v = df[col].iloc[0]
                        st.metric(col.replace('_', ' ').title(),
                                  f"${v:,.2f}" if isinstance(v, (int, float)) and abs(v) > 1 else f"{v:,.4f}")

            # Otros
            if other_cols:
                cols_ui = st.columns(min(len(other_cols), 4))
                for i, col in enumerate(other_cols[:4]):
                    with cols_ui[i]:
                        v = df[col].iloc[0]
                        st.metric(col.replace('_', ' ').title(),
                                  f"${v:,.2f}" if isinstance(v, (int, float)) and abs(v) > 1 else f"{v:,.4f}")

            # Gráfica de barras horizontal con todas las métricas
            stat_data = []
            for col in num_cols:
                if col not in count_cols:
                    stat_data.append({"Métrica": col.replace('_', ' ').title(), "Valor": float(df[col].iloc[0])})
            if stat_data:
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
                st.plotly_chart(fig, use_container_width=True)

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

                fig = go.Figure()
                fig.add_trace(go.Box(
                    q1=[p25], median=[p50], q3=[p75],
                    lowerfence=[mn], upperfence=[mx], mean=[avg_val],
                    name="Distribución",
                    marker_color="#2196F3",
                    boxmean=True,
                ))
                fig.update_layout(
                    title=f"📦 Distribución — {title}",
                    showlegend=False,
                    height=300,
                )
                st.plotly_chart(fig, use_container_width=True)

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

            st.plotly_chart(fig, use_container_width=True)

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
                st.plotly_chart(fig2, use_container_width=True)

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
                st.plotly_chart(fig, use_container_width=True)
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
    """Widget ROI compacto para la barra lateral del chat."""
    try:
        tracker = init_roi_tracker(st.session_state)
        da_actions = [a for a in tracker.session_state.roi_data.get("actions", [])
                      if a.get("module") == "data_assistant"]
        da_hrs = sum(a.get("hrs_saved", 0) for a in da_actions)
        da_value = sum(a.get("value", 0) for a in da_actions)
        da_count = len(da_actions)

        st.markdown("### 💰 Tu ROI")
        st.metric("⏱️ Hrs ahorradas", f"{da_hrs:.1f}")
        st.metric("💵 Valor", f"${da_value:,.0f} MXN")
        st.caption(f"🔢 {da_count} consulta(s) esta sesión")
    except Exception:
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
                empresa_id = st.session_state.get("nl2sql_empresa_id")
                result = engine.ask(question, empresa_id=empresa_id)

            # --- ROI Tracking ---
            _track_query_roi(result)

            # Renderizar resultado
            msg_data = _build_result_message(result)
            new_idx = len(st.session_state["nl2sql_messages"])
            _render_result_message(msg_data, new_idx)

            st.session_state["nl2sql_messages"].append(msg_data)


def _build_result_message(result: NL2SQLResult) -> dict:
    """Construye un mensaje de resultado para almacenar en session_state."""
    msg = {
        "role": "assistant",
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
            df = pd.read_json(msg["dataframe_json"], orient="split")
        except Exception:
            df = None

    if df is not None and not df.empty:
        # Gráfica automática con spec de IA
        chart_type = msg.get("chart_suggestion", "table")
        chart_spec = msg.get("chart_spec", {})
        question = msg.get("content", "")

        # Pestañas: Gráfica | Tabla | SQL
        tab_chart, tab_table, tab_sql = st.tabs(["📊 Gráfica", "📋 Tabla", "🔍 SQL"])

        with tab_chart:
            _auto_chart(df, chart_type, question, chart_spec=chart_spec)

        with tab_table:
            st.dataframe(df, use_container_width=True, hide_index=True)

            # Exportar
            csv = df.to_csv(index=False)
            st.download_button(
                "📥 Descargar CSV",
                csv,
                "resultado_consulta.csv",
                "text/csv",
                key=f"dl_{msg_idx}_{hash(msg.get('sql', ''))}",
            )

        with tab_sql:
            st.code(msg.get("sql", ""), language="sql")
            exec_time = msg.get("execution_time", 0)
            row_count = msg.get("row_count", 0)
            st.caption(f"⏱️ {exec_time:.2f}s · {row_count} filas")
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
