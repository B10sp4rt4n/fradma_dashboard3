"""
Módulo: Vendedores + CxC
Cruza datos de ventas con cartera de cuentas por cobrar por vendedor.

Métricas clave:
- Ratio deuda vencida / ventas por vendedor
- % cartera sana vs vencida generada por cada vendedor
- Score de calidad de cartera por vendedor
- Ranking mixto: volumen de ventas vs calidad de cartera
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime

from utils.cxc_helper import preparar_datos_cxc, calcular_dias_overdue
from utils.data_normalizer import normalizar_columnas
from utils.logger import configurar_logger

logger = configurar_logger("vendedores_cxc", nivel="INFO")


# ── Helpers internos ──────────────────────────────────────────────────────────

def _detectar_col_vendedor(df: pd.DataFrame) -> str | None:
    """Retorna el nombre de la primera columna que sea vendedor/agente/ejecutivo."""
    for col in df.columns:
        if col.lower() in ("vendedor", "agente", "ejecutivo", "seller", "rep"):
            return col
    return None


def _detectar_col_ventas(df: pd.DataFrame) -> str | None:
    """Detecta columna de ventas con búsqueda flexible."""
    # Primera pasada: búsqueda exacta
    for col in ("valor_usd", "ventas_usd", "ventas_usd_con_iva", "ventas_usd_sin_iva",
                "importe", "monto_usd", "total_usd", "venta", "monto", "total"):
        if col in df.columns:
            return col
    
    # Segunda pasada: búsqueda parcial (case insensitive)
    for col in df.columns:
        col_lower = col.lower()
        if any(keyword in col_lower for keyword in 
               ["valor", "venta", "importe", "monto", "total", "usd"]):
            # Excluir columnas que claramente no son de ventas
            if not any(excl in col_lower for excl in 
                      ["fecha", "cliente", "vendedor", "producto", "linea", "saldo", "adeudo"]):
                return col
    
    return None


def _detectar_col_cliente(df: pd.DataFrame) -> str | None:
    for col in ("cliente", "deudor", "razon_social", "nombre_cliente"):
        if col in df.columns:
            return col
    return None


def _score_calidad(pct_vencida: float) -> tuple[float, str]:
    """Score 0-100 de calidad de cartera (100 = sin deuda vencida)."""
    score = max(0.0, 100.0 - pct_vencida)
    if score >= 85:
        return score, "🟢 Excelente"
    elif score >= 65:
        return score, "🟡 Aceptable"
    elif score >= 40:
        return score, "🟠 Riesgo"
    else:
        return score, "🔴 Crítico"


# ── Función principal ─────────────────────────────────────────────────────────

def run():
    st.title("👥 Vendedores + CxC")
    st.caption(
        "Cruza ventas con cartera: qué vendedor genera más deuda vencida "
        "relativa a sus ventas. Útil para políticas de comisiones y límites de crédito."
    )

    # ── Validar datos disponibles ─────────────────────────────────────────────
    if "df" not in st.session_state:
        st.warning("⚠️ Carga primero un archivo de ventas en el sidebar.")
        return

    if "archivo_excel" not in st.session_state:
        st.warning("⚠️ Este módulo requiere el archivo Excel original para leer la hoja CxC.")
        return

    df_ventas = st.session_state["df"].copy()

    # Normalizar columna de ventas
    col_ventas = _detectar_col_ventas(df_ventas)
    if col_ventas and col_ventas != "valor_usd":
        logger.info(f"Columna de ventas detectada: '{col_ventas}' → renombrada a 'valor_usd'")
        df_ventas = df_ventas.rename(columns={col_ventas: "valor_usd"})
        col_ventas = "valor_usd"

    col_vendedor_v = _detectar_col_vendedor(df_ventas)
    if col_vendedor_v and col_vendedor_v != "vendedor":
        logger.info(f"Columna de vendedor detectada: '{col_vendedor_v}' → renombrada a 'vendedor'")
        df_ventas = df_ventas.rename(columns={col_vendedor_v: "vendedor"})
        col_vendedor_v = "vendedor"

    col_cliente_v = _detectar_col_cliente(df_ventas)

    if not col_ventas:
        st.error("❌ No se encontró columna de ventas (valor_usd / ventas_usd / importe).")
        st.info(f"📋 Columnas disponibles: {', '.join(df_ventas.columns.tolist())}")
        logger.error(f"No se detectó columna de ventas. Columnas disponibles: {df_ventas.columns.tolist()}")
        return

    if not col_vendedor_v:
        st.error(
            "❌ No se encontró columna de vendedor/agente en el archivo de ventas. "
            "El cruce no es posible sin esta columna."
        )
        st.info(f"📋 Columnas disponibles: {', '.join(df_ventas.columns.tolist())}")
        logger.error(f"No se detectó columna de vendedor. Columnas disponibles: {df_ventas.columns.tolist()}")
        return

    # ── Cargar CxC ────────────────────────────────────────────────────────────
    df_cxc_raw = None
    try:
        archivo_excel = st.session_state["archivo_excel"]
        hojas = pd.ExcelFile(archivo_excel).sheet_names
        hoja_cxc = next(
            (h for h in hojas if "cxc" in h.lower() or "cuenta" in h.lower()), None
        )
        if hoja_cxc:
            df_cxc_raw = normalizar_columnas(pd.read_excel(archivo_excel, sheet_name=hoja_cxc))
    except Exception as e:
        logger.exception(f"Error leyendo hoja CxC: {e}")

    if df_cxc_raw is None or df_cxc_raw.empty:
        st.error(
            "❌ No se encontró una hoja CxC en el archivo Excel. "
            "El archivo debe tener una hoja con 'cxc' o 'cuenta' en el nombre."
        )
        return

    # Normalizar saldo
    for candidato in ("saldo_adeudado", "saldo", "saldo_adeudo", "adeudo", "importe", "monto", "total"):
        if candidato in df_cxc_raw.columns:
            if candidato != "saldo_adeudado":
                df_cxc_raw = df_cxc_raw.rename(columns={candidato: "saldo_adeudado"})
            break

    if "saldo_adeudado" not in df_cxc_raw.columns:
        st.error("❌ No se encontró columna de saldo en la hoja CxC.")
        return

    saldo_txt = df_cxc_raw["saldo_adeudado"].astype(str).str.replace(",", "", regex=False).str.replace("$", "", regex=False)
    df_cxc_raw["saldo_adeudado"] = pd.to_numeric(saldo_txt, errors="coerce").fillna(0)

    col_vendedor_c = _detectar_col_vendedor(df_cxc_raw)
    col_cliente_c  = _detectar_col_cliente(df_cxc_raw)

    # Preparar CxC (calcular dias_overdue)
    _, df_np, _ = preparar_datos_cxc(df_cxc_raw)

    # ── Detectar si hay columna vendedor en CxC ───────────────────────────────
    tiene_vendedor_cxc = col_vendedor_c is not None
    tiene_cliente_comun = (col_cliente_v is not None and col_cliente_c is not None)

    if not tiene_vendedor_cxc and not tiene_cliente_comun:
        st.error(
            "❌ Para cruzar ventas con CxC se necesita al menos una de estas condiciones:\n\n"
            "1. La hoja CxC tiene columna vendedor/agente, **o**\n"
            "2. Ambas hojas tienen columna cliente (para unir por cliente → vendedor)."
        )
        return

    # ── Construir tabla de cruce ──────────────────────────────────────────────
    # Método A: CxC tiene vendedor directo
    if tiene_vendedor_cxc:
        if col_vendedor_c != "vendedor":
            df_np = df_np.rename(columns={col_vendedor_c: "vendedor"})
        df_cxc_vend = df_np.copy()

    # Método B: Unir por cliente → heredar vendedor de ventas
    else:
        # Mapa cliente → vendedor desde ventas
        mapa = (
            df_ventas.dropna(subset=[col_cliente_v, "vendedor"])
            .groupby(col_cliente_v)["vendedor"]
            .agg(lambda x: x.mode().iloc[0] if len(x) > 0 else None)
            .reset_index()
            .rename(columns={col_cliente_v: "deudor"})
        )
        if col_cliente_c != "deudor":
            df_np = df_np.rename(columns={col_cliente_c: "deudor"})
        df_cxc_vend = df_np.merge(mapa, on="deudor", how="left")
        sin_vendedor = df_cxc_vend["vendedor"].isna().sum()
        if sin_vendedor > 0:
            st.info(
                f"ℹ️ {sin_vendedor} registros CxC no pudieron asociarse a un vendedor "
                "(clientes sin historial de ventas en el archivo)."
            )

    df_cxc_vend = df_cxc_vend.dropna(subset=["vendedor"])

    if df_cxc_vend.empty:
        st.warning("⚠️ No se pudo asociar ningún registro CxC a un vendedor.")
        return

    # ── Agregar métricas por vendedor ─────────────────────────────────────────
    agg_ventas = (
        df_ventas.groupby("vendedor")
        .agg(
            ventas_totales=("valor_usd", "sum"),
            num_operaciones=("valor_usd", "count"),
        )
        .reset_index()
    )

    agg_cxc = (
        df_cxc_vend.groupby("vendedor")
        .apply(lambda g: pd.Series({
            "cartera_total":   g["saldo_adeudado"].sum(),
            "cartera_vigente": g.loc[g["dias_overdue"] <= 0, "saldo_adeudado"].sum(),
            "cartera_vencida": g.loc[g["dias_overdue"] > 0,  "saldo_adeudado"].sum(),
            "cartera_alto_riesgo": g.loc[g["dias_overdue"] > 90, "saldo_adeudado"].sum(),
            "clientes_unicos": g["deudor"].nunique() if "deudor" in g.columns else 0,
            "dias_max":        g["dias_overdue"].max(),
        }))
        .reset_index()
    )

    df_cruce = agg_ventas.merge(agg_cxc, on="vendedor", how="outer").fillna(0)

    # Ratios y score
    df_cruce["ticket_promedio"] = (
        df_cruce["ventas_totales"] / df_cruce["num_operaciones"].replace(0, 1)
    )
    df_cruce["pct_vencida"] = (
        df_cruce["cartera_vencida"] / df_cruce["cartera_total"].replace(0, 1) * 100
    )
    df_cruce["pct_alto_riesgo"] = (
        df_cruce["cartera_alto_riesgo"] / df_cruce["cartera_total"].replace(0, 1) * 100
    )
    df_cruce["ratio_deuda_ventas"] = (
        df_cruce["cartera_vencida"] / df_cruce["ventas_totales"].replace(0, 1) * 100
    )
    df_cruce[["score_calidad", "nivel_calidad"]] = df_cruce["pct_vencida"].apply(
        lambda p: pd.Series(_score_calidad(p))
    )
    df_cruce = df_cruce.sort_values("ventas_totales", ascending=False).reset_index(drop=True)

    # ── UI: Resumen general ───────────────────────────────────────────────────
    st.subheader("📊 Resumen General")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Vendedores analizados", len(df_cruce))
    col2.metric(
        "💰 Ventas Totales",
        f"${df_cruce['ventas_totales'].sum():,.0f}",
    )
    col3.metric(
        "📋 Cartera Total CxC",
        f"${df_cruce['cartera_total'].sum():,.0f}",
    )
    mejor = df_cruce.loc[df_cruce["score_calidad"].idxmax()]
    col4.metric(
        "🏆 Mejor Calidad Cartera",
        mejor["vendedor"],
        delta=f"Score {mejor['score_calidad']:.0f}/100",
    )

    # ── Tabla comparativa ─────────────────────────────────────────────────────
    st.subheader("📋 Tabla Comparativa por Vendedor")

    df_tabla = df_cruce[[
        "vendedor", "ventas_totales", "ticket_promedio", "num_operaciones",
        "cartera_total", "cartera_vencida", "pct_vencida",
        "ratio_deuda_ventas", "dias_max", "score_calidad", "nivel_calidad"
    ]].copy()

    st.dataframe(
        df_tabla,
        use_container_width=True,
        hide_index=True,
        column_config={
            "vendedor":          st.column_config.TextColumn("Vendedor",         width="medium"),
            "ventas_totales":    st.column_config.NumberColumn("Ventas ($)",      width="medium", format="$%.0f"),
            "ticket_promedio":   st.column_config.NumberColumn("Ticket Prom ($)", width="medium", format="$%.0f"),
            "num_operaciones":   st.column_config.NumberColumn("# Ops",           width="small"),
            "cartera_total":     st.column_config.NumberColumn("Cartera ($)",     width="medium", format="$%.0f"),
            "cartera_vencida":   st.column_config.NumberColumn("Vencida ($)",     width="medium", format="$%.0f"),
            "pct_vencida":       st.column_config.NumberColumn("% Vencida",       width="small",  format="%.1f%%"),
            "ratio_deuda_ventas":st.column_config.ProgressColumn(
                                    "Deuda/Ventas %", width="medium",
                                    min_value=0, max_value=100, format="%.1f%%"),
            "dias_max":          st.column_config.NumberColumn("Días Máx",        width="small"),
            "score_calidad":     st.column_config.ProgressColumn(
                                    "Score Calidad", width="medium",
                                    min_value=0, max_value=100, format="%.0f"),
            "nivel_calidad":     st.column_config.TextColumn("Nivel",            width="small"),
        },
    )

    with st.expander("ℹ️ ¿Cómo interpretar estas métricas?"):
        st.markdown("""
        | Columna | Qué mide |
        |---------|----------|
        | **Deuda/Ventas %** | Cartera vencida ÷ ventas totales. Si es alto, el vendedor cierra ventas pero no ayuda a cobrar |
        | **Score Calidad** | 100 − % vencida. 100 = toda la cartera del vendedor está vigente |
        | **Días Máx** | La factura más vencida de los clientes de ese vendedor |
        | **% Vencida** | Del total de cartera que generó el vendedor, cuánto está vencido |

        **Señales de alerta:**
        - 🔴 Score < 40 → revisar política de crédito para ese vendedor
        - Deuda/Ventas > 20% → el vendedor puede estar aceptando malos pagadores para cerrar ventas
        """)

    # ── Gráfico: Ventas vs % Vencida (bubble = cartera total) ────────────────
    st.subheader("📈 Ventas vs Calidad de Cartera")

    fig_scatter = px.scatter(
        df_cruce,
        x="ventas_totales",
        y="pct_vencida",
        size="cartera_total",
        color="nivel_calidad",
        hover_name="vendedor",
        color_discrete_map={
            "🟢 Excelente": "#4CAF50",
            "🟡 Aceptable": "#FFEB3B",
            "🟠 Riesgo":    "#FF9800",
            "🔴 Crítico":   "#F44336",
        },
        labels={
            "ventas_totales": "Ventas Totales ($)",
            "pct_vencida":    "% Cartera Vencida",
            "cartera_total":  "Cartera Total ($)",
            "nivel_calidad":  "Calidad",
        },
        title="Cuadrante: Volumen de Ventas vs Calidad de Cartera",
    )

    # Línea de referencia: media de % vencida
    media_pct = df_cruce["pct_vencida"].mean()
    fig_scatter.add_hline(
        y=media_pct, line_dash="dash", line_color="gray",
        annotation_text=f"Promedio {media_pct:.1f}%", annotation_position="top right",
    )
    fig_scatter.update_layout(height=440, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig_scatter, use_container_width=True)

    st.caption(
        "💡 Ideal: esquina inferior derecha (muchas ventas, baja cartera vencida). "
        "Riesgo: esquina superior derecha (muchas ventas + mucha cartera vencida)."
    )

    # ── Gráfico: Score de calidad ranking ────────────────────────────────────
    st.subheader("🏅 Ranking de Calidad de Cartera")

    df_rank = df_cruce.sort_values("score_calidad", ascending=True)
    colores_rank = df_rank["nivel_calidad"].map({
        "🟢 Excelente": "#4CAF50",
        "🟡 Aceptable": "#FFEB3B",
        "🟠 Riesgo":    "#FF9800",
        "🔴 Crítico":   "#F44336",
    }).fillna("#9E9E9E")

    fig_rank = go.Figure(go.Bar(
        x=df_rank["score_calidad"],
        y=df_rank["vendedor"],
        orientation="h",
        marker_color=colores_rank,
        text=df_rank["score_calidad"].apply(lambda s: f"{s:.0f}/100"),
        textposition="outside",
        hovertemplate="%{y}<br>Score: %{x:.0f}<br>% Vencida: " +
                      df_rank["pct_vencida"].apply(lambda p: f"{p:.1f}%").values + "<extra></extra>",
    ))
    fig_rank.update_layout(
        title="Score de Calidad de Cartera por Vendedor (mayor = mejor)",
        xaxis=dict(range=[0, 115], title="Score (0–100)"),
        yaxis_title="",
        height=max(350, len(df_rank) * 45),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig_rank, use_container_width=True)

    # ── Gráfico: Composición de cartera por vendedor (stacked bar) ───────────
    st.subheader("📊 Composición de Cartera por Vendedor")

    df_stack = df_cruce.sort_values("cartera_total", ascending=False).head(15)

    fig_stack = go.Figure()
    fig_stack.add_trace(go.Bar(
        name="Vigente",
        x=df_stack["vendedor"],
        y=df_stack["cartera_vigente"],
        marker_color="#4CAF50",
        hovertemplate="%{x}<br>Vigente: $%{y:,.0f}<extra></extra>",
    ))
    fig_stack.add_trace(go.Bar(
        name="Vencida (no crítica)",
        x=df_stack["vendedor"],
        y=df_stack["cartera_vencida"] - df_stack["cartera_alto_riesgo"],
        marker_color="#FF9800",
        hovertemplate="%{x}<br>Vencida: $%{y:,.0f}<extra></extra>",
    ))
    fig_stack.add_trace(go.Bar(
        name=">90 días (alto riesgo)",
        x=df_stack["vendedor"],
        y=df_stack["cartera_alto_riesgo"],
        marker_color="#F44336",
        hovertemplate="%{x}<br>Alto riesgo: $%{y:,.0f}<extra></extra>",
    ))
    fig_stack.update_layout(
        barmode="stack",
        title="Composición de Cartera por Vendedor (Top 15)",
        xaxis_title="",
        yaxis_title="Saldo ($)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=420,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig_stack, use_container_width=True)

    # ── Alertas automáticas ───────────────────────────────────────────────────
    st.subheader("🚨 Alertas de Vendedores")

    alertas_vend = []
    for _, row in df_cruce.iterrows():
        if row["pct_vencida"] > 40:
            alertas_vend.append(
                f"🔴 **{row['vendedor']}**: {row['pct_vencida']:.1f}% de su cartera está vencida "
                f"(${row['cartera_vencida']:,.0f})"
            )
        elif row["ratio_deuda_ventas"] > 20:
            alertas_vend.append(
                f"🟠 **{row['vendedor']}**: ratio deuda/ventas de {row['ratio_deuda_ventas']:.1f}% "
                f"— posible aceptación de clientes de alto riesgo"
            )
        elif row["dias_max"] > 120:
            alertas_vend.append(
                f"🟡 **{row['vendedor']}**: factura más vencida con {row['dias_max']:.0f} días — "
                "revisar cliente específico"
            )

    if alertas_vend:
        for a in alertas_vend:
            st.markdown(a)
    else:
        st.success("✅ Todos los vendedores tienen indicadores dentro de rangos normales.")

    # ── Descarga CSV ──────────────────────────────────────────────────────────
    st.write("---")
    csv_bytes = df_cruce.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇️ Descargar tabla completa (.csv)",
        data=csv_bytes,
        file_name=f"vendedores_cxc_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv",
    )
