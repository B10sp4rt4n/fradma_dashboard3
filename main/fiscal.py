"""
Módulo: Desglose Fiscal
Análisis de la distribución de impuestos: base gravable, IVA trasladado,
descuentos y total. Todo sin mezclar IVA con los importes de venta.
"""

import os
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import psycopg2
from utils.logger import configurar_logger

logger = configurar_logger("fiscal", nivel="INFO")


def _get_neon_url() -> str | None:
    url = os.environ.get("NEON_DATABASE_URL")
    if not url:
        try:
            url = st.secrets.get("NEON_DATABASE_URL")
        except Exception:
            pass
    return url


def _cargar_fiscal(empresa_id: str, neon_url: str) -> pd.DataFrame:
    """Carga detalle fiscal por factura (Ingresos vigentes)."""
    query = """
        SELECT
            uuid_sat,
            fecha_emision::date                                 AS fecha,
            receptor_rfc,
            receptor_nombre,
            linea_negocio,
            vendedor_asignado,
            moneda,
            ROUND(subtotal   * COALESCE(tipo_cambio,1), 2)    AS subtotal_mxn,
            ROUND(descuento  * COALESCE(tipo_cambio,1), 2)    AS descuento_mxn,
            ROUND(impuestos  * COALESCE(tipo_cambio,1), 2)    AS iva_mxn,
            ROUND(total      * COALESCE(tipo_cambio,1), 2)    AS total_mxn,
            ROUND(
                (subtotal - COALESCE(descuento,0)) * COALESCE(tipo_cambio,1), 2
            )                                                  AS base_gravable_mxn
        FROM cfdi_ventas
        WHERE empresa_id = %s
          AND tipo_comprobante = 'I'
          AND estatus = 'vigente'
        ORDER BY fecha_emision DESC
    """
    conn = None
    try:
        conn = psycopg2.connect(neon_url)
        cur = conn.cursor()
        cur.execute(query, (empresa_id,))
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
        return pd.DataFrame(rows, columns=cols)
    except Exception as e:
        logger.error(f"Error cargando fiscal: {e}")
        st.error(f"❌ Error al consultar la base de datos: {e}")
        return pd.DataFrame()
    finally:
        if conn:
            conn.close()


def _cargar_tendencia_fiscal(empresa_id: str, neon_url: str) -> pd.DataFrame:
    """Tendencia mensual de base gravable e IVA."""
    query = """
        SELECT
            DATE_TRUNC('month', fecha_emision)::date           AS mes,
            COUNT(*)                                            AS num_facturas,
            ROUND(SUM((subtotal - COALESCE(descuento,0))
                      * COALESCE(tipo_cambio,1)), 2)            AS base_gravable_mxn,
            ROUND(SUM(impuestos  * COALESCE(tipo_cambio,1)), 2) AS iva_mxn,
            ROUND(SUM(total      * COALESCE(tipo_cambio,1)), 2) AS total_mxn,
            ROUND(SUM(descuento  * COALESCE(tipo_cambio,1)), 2) AS descuento_mxn
        FROM cfdi_ventas
        WHERE empresa_id = %s
          AND tipo_comprobante = 'I'
          AND estatus = 'vigente'
        GROUP BY 1
        ORDER BY 1 DESC
    """
    conn = None
    try:
        conn = psycopg2.connect(neon_url)
        cur = conn.cursor()
        cur.execute(query, (empresa_id,))
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
        return pd.DataFrame(rows, columns=cols)
    except Exception as e:
        logger.error(f"Error cargando tendencia fiscal: {e}")
        return pd.DataFrame()
    finally:
        if conn:
            conn.close()


def run():
    st.title("🧾 Desglose Fiscal")
    st.caption("Base gravable, IVA trasladado y total — solo facturas de Ingreso vigentes")

    empresa_id    = st.session_state.get("empresa_id")
    empresa_nombre = st.session_state.get("empresa_nombre", "")
    neon_url      = _get_neon_url()

    if not empresa_id or not neon_url:
        st.warning("⚠️ Debes iniciar sesión para ver este reporte.")
        return

    with st.spinner("Consultando base de datos..."):
        df          = _cargar_fiscal(empresa_id, neon_url)
        df_tendencia = _cargar_tendencia_fiscal(empresa_id, neon_url)

    if df.empty:
        st.info("📭 No hay facturas de ingreso registradas para esta empresa.")
        return

    # Tipos numéricos
    for col in ["subtotal_mxn", "descuento_mxn", "iva_mxn", "total_mxn", "base_gravable_mxn"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    if empresa_nombre:
        st.markdown(f"**Empresa:** {empresa_nombre}")
    st.markdown("---")

    # ── KPIs ────────────────────────────────────────────────────────────────
    total_facturas   = len(df)
    base_total       = df["base_gravable_mxn"].sum()
    iva_total        = df["iva_mxn"].sum()
    descuento_total  = df["descuento_mxn"].sum()
    total_con_iva    = df["total_mxn"].sum()
    pct_iva          = (iva_total / total_con_iva * 100) if total_con_iva else 0
    tasa_efectiva    = (iva_total / base_total * 100) if base_total else 0

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Facturas",               f"{total_facturas:,}")
    c2.metric("Base gravable (MXN)",    f"${base_total:,.0f}",
              help="Subtotal − Descuentos (sin IVA)")
    c3.metric("IVA trasladado (MXN)",   f"${iva_total:,.0f}",
              delta=f"{tasa_efectiva:.1f}% tasa efectiva", delta_color="off")
    c4.metric("Total con IVA (MXN)",    f"${total_con_iva:,.0f}")
    c5.metric("Descuentos (MXN)",       f"${descuento_total:,.0f}",
              help="Suma de descuentos aplicados")

    st.markdown("---")

    tab1, tab2, tab3, tab4 = st.tabs(
        ["📅 Tendencia mensual", "👥 Por Cliente", "📦 Por Línea de Negocio", "📄 Detalle"]
    )

    # ── Tab 1: Tendencia mensual ─────────────────────────────────────────────
    with tab1:
        if df_tendencia.empty:
            st.info("Sin datos de tendencia.")
        else:
            df_tendencia["mes"] = pd.to_datetime(df_tendencia["mes"])
            for col in ["base_gravable_mxn", "iva_mxn", "total_mxn", "descuento_mxn"]:
                df_tendencia[col] = pd.to_numeric(df_tendencia[col], errors="coerce").fillna(0)

            # Gráfica apilada: base gravable + IVA = total
            fig_stack = go.Figure()
            df_t = df_tendencia.sort_values("mes")
            fig_stack.add_trace(go.Bar(
                x=df_t["mes"], y=df_t["base_gravable_mxn"],
                name="Base gravable (sin IVA)",
                marker_color="#2196F3",
                text=df_t["base_gravable_mxn"].apply(lambda x: f"${x:,.0f}"),
                textposition="inside",
            ))
            fig_stack.add_trace(go.Bar(
                x=df_t["mes"], y=df_t["iva_mxn"],
                name="IVA trasladado",
                marker_color="#FF9800",
                text=df_t["iva_mxn"].apply(lambda x: f"${x:,.0f}"),
                textposition="inside",
            ))
            fig_stack.update_layout(
                barmode="stack",
                title="Facturación mensual: base gravable + IVA",
                height=420,
                xaxis_tickformat="%b %Y",
                yaxis_title="MXN",
                legend=dict(orientation="h", y=1.08),
            )
            st.plotly_chart(fig_stack, use_container_width=True)

            # Línea: número de facturas + tasa IVA efectiva por mes
            df_t = df_t.copy()
            df_t["tasa_iva"] = (df_t["iva_mxn"] / df_t["base_gravable_mxn"] * 100).round(2)

            fig_tasa = px.line(
                df_t, x="mes", y="tasa_iva",
                title="Tasa de IVA efectiva mensual (%)",
                markers=True,
                labels={"mes": "Mes", "tasa_iva": "IVA / Base (%)"},
            )
            fig_tasa.update_layout(height=320, xaxis_tickformat="%b %Y")
            fig_tasa.add_hline(y=16, line_dash="dash", line_color="orange",
                               annotation_text="16% estándar")
            st.plotly_chart(fig_tasa, use_container_width=True)

            # Tabla mensual
            disp_t = df_t[[
                "mes", "num_facturas", "base_gravable_mxn", "iva_mxn",
                "descuento_mxn", "total_mxn", "tasa_iva"
            ]].copy()
            disp_t["mes"] = disp_t["mes"].dt.strftime("%b %Y")
            disp_t.columns = [
                "Mes", "Facturas", "Base gravable", "IVA",
                "Descuentos", "Total c/IVA", "Tasa IVA %"
            ]
            for col in ["Base gravable", "IVA", "Descuentos", "Total c/IVA"]:
                disp_t[col] = disp_t[col].apply(lambda x: f"${x:,.2f}")
            st.dataframe(disp_t, use_container_width=True, hide_index=True)

    # ── Tab 2: Por Cliente ───────────────────────────────────────────────────
    with tab2:
        df_cli = (
            df.groupby(["receptor_rfc", "receptor_nombre"], as_index=False)
            .agg(
                facturas=("uuid_sat", "count"),
                base_gravable=("base_gravable_mxn", "sum"),
                iva=("iva_mxn", "sum"),
                total=("total_mxn", "sum"),
            )
            .sort_values("iva", ascending=False)
        )

        col_g1, col_g2 = st.columns([1, 1])
        with col_g1:
            top_n = min(15, len(df_cli))
            df_top = df_cli.head(top_n).sort_values("iva", ascending=True)
            fig_cli = px.bar(
                df_top,
                x="iva", y="receptor_nombre",
                orientation="h",
                title=f"Top {top_n} clientes por IVA generado (MXN)",
                color="iva",
                color_continuous_scale="Blues",
                text=df_top["iva"].apply(lambda x: f"${x:,.0f}"),
            )
            fig_cli.update_traces(textposition="outside")
            fig_cli.update_layout(showlegend=False, height=420,
                                  coloraxis_showscale=False,
                                  xaxis_title="IVA (MXN)", yaxis_title="")
            st.plotly_chart(fig_cli, use_container_width=True)

        with col_g2:
            fig_pie = px.pie(
                df_cli.head(10),
                names="receptor_nombre",
                values="base_gravable",
                title="Top 10 clientes — base gravable",
                hole=0.4,
            )
            fig_pie.update_traces(textinfo="percent+label")
            fig_pie.update_layout(showlegend=False, height=420)
            st.plotly_chart(fig_pie, use_container_width=True)

        # Tabla clientes
        disp_cli = df_cli.copy()
        for col in ["base_gravable", "iva", "total"]:
            disp_cli[col] = disp_cli[col].apply(lambda x: f"${x:,.2f}")
        disp_cli.columns = ["RFC", "Cliente", "Facturas", "Base gravable", "IVA", "Total c/IVA"]
        st.dataframe(disp_cli, use_container_width=True, hide_index=True)

    # ── Tab 3: Por Línea de Negocio ──────────────────────────────────────────
    with tab3:
        df["linea_negocio"] = df["linea_negocio"].fillna("Sin clasificar")
        df_linea = (
            df.groupby("linea_negocio", as_index=False)
            .agg(
                facturas=("uuid_sat", "count"),
                base_gravable=("base_gravable_mxn", "sum"),
                iva=("iva_mxn", "sum"),
                total=("total_mxn", "sum"),
            )
            .sort_values("base_gravable", ascending=False)
        )

        # Sunburst base gravable vs IVA por línea
        df_sun = pd.concat([
            df_linea.assign(concepto="Base gravable", valor=df_linea["base_gravable"]),
            df_linea.assign(concepto="IVA",           valor=df_linea["iva"]),
        ])
        fig_sun = px.sunburst(
            df_sun,
            path=["linea_negocio", "concepto"],
            values="valor",
            title="Composición fiscal por línea de negocio",
            color="concepto",
            color_discrete_map={"Base gravable": "#2196F3", "IVA": "#FF9800"},
        )
        fig_sun.update_layout(height=420)
        st.plotly_chart(fig_sun, use_container_width=True)

        # Barras apiladas
        df_linea_sorted = df_linea.sort_values("base_gravable", ascending=True)
        fig_bar = go.Figure()
        fig_bar.add_trace(go.Bar(
            y=df_linea_sorted["linea_negocio"], x=df_linea_sorted["base_gravable"],
            name="Base gravable", orientation="h", marker_color="#2196F3",
            text=df_linea_sorted["base_gravable"].apply(lambda x: f"${x:,.0f}"),
            textposition="inside",
        ))
        fig_bar.add_trace(go.Bar(
            y=df_linea_sorted["linea_negocio"], x=df_linea_sorted["iva"],
            name="IVA", orientation="h", marker_color="#FF9800",
            text=df_linea_sorted["iva"].apply(lambda x: f"${x:,.0f}"),
            textposition="inside",
        ))
        fig_bar.update_layout(
            barmode="stack",
            title="Base gravable + IVA por línea de negocio",
            height=max(300, len(df_linea) * 50),
            xaxis_title="MXN", yaxis_title="",
            legend=dict(orientation="h", y=1.05),
        )
        st.plotly_chart(fig_bar, use_container_width=True)

        disp_lin = df_linea.copy()
        for col in ["base_gravable", "iva", "total"]:
            disp_lin[col] = disp_lin[col].apply(lambda x: f"${x:,.2f}")
        disp_lin.columns = ["Línea de negocio", "Facturas", "Base gravable", "IVA", "Total c/IVA"]
        st.dataframe(disp_lin, use_container_width=True, hide_index=True)

    # ── Tab 4: Detalle ───────────────────────────────────────────────────────
    with tab4:
        # Filtros
        col_f1, col_f2 = st.columns(2)
        lineas = ["Todas"] + sorted(df["linea_negocio"].unique().tolist())
        sel_linea  = col_f1.selectbox("Línea de negocio", lineas)
        buscar_cli = col_f2.text_input("Buscar cliente (nombre o RFC)", "")

        df_det = df.copy()
        if sel_linea != "Todas":
            df_det = df_det[df_det["linea_negocio"] == sel_linea]
        if buscar_cli:
            mask = (
                df_det["receptor_nombre"].str.contains(buscar_cli, case=False, na=False) |
                df_det["receptor_rfc"].str.contains(buscar_cli, case=False, na=False)
            )
            df_det = df_det[mask]

        st.caption(f"**{len(df_det):,}** facturas")

        disp_det = df_det[[
            "fecha", "receptor_nombre", "receptor_rfc",
            "base_gravable_mxn", "descuento_mxn", "iva_mxn", "total_mxn",
            "moneda", "linea_negocio", "uuid_sat"
        ]].copy()
        disp_det.columns = [
            "Fecha", "Cliente", "RFC",
            "Base gravable", "Descuento", "IVA", "Total c/IVA",
            "Moneda", "Línea", "UUID SAT"
        ]

        st.dataframe(
            disp_det.style.format({
                "Base gravable": "${:,.2f}",
                "Descuento":     "${:,.2f}",
                "IVA":           "${:,.2f}",
                "Total c/IVA":   "${:,.2f}",
            }),
            use_container_width=True,
            hide_index=True,
            height=480,
        )

        csv = df_det.to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ Descargar CSV",
            data=csv,
            file_name="desglose_fiscal.csv",
            mime="text/csv",
        )
