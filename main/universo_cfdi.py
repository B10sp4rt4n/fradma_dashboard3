"""
Módulo: Universo de CFDIs
Muestra la composición completa del portafolio de CFDIs por tipo y estatus.
"""

import os
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import psycopg2
from utils.logger import configurar_logger

logger = configurar_logger("universo_cfdi", nivel="INFO")

# ─── Etiquetas descriptivas ──────────────────────────────────────────────────
TIPO_LABEL = {
    "I": "Ingreso",
    "E": "Egreso / Nota de crédito",
    "T": "Traslado",
    "N": "Nómina",
    "P": "Pago (Complemento)",
}
TIPO_COLOR = {
    "Ingreso":                     "#2196F3",
    "Egreso / Nota de crédito":    "#FF9800",
    "Traslado":                    "#9C27B0",
    "Nómina":                      "#4CAF50",
    "Pago (Complemento)":          "#00BCD4",
}
ESTATUS_COLOR = {
    "vigente":   "#4CAF50",
    "cancelado": "#F44336",
}


def _get_neon_url() -> str | None:
    url = os.environ.get("NEON_DATABASE_URL")
    if not url:
        try:
            url = st.secrets.get("NEON_DATABASE_URL")
        except Exception:
            pass
    return url


def _cargar_datos(empresa_id: str, neon_url: str) -> pd.DataFrame:
    """Carga el resumen de CFDIs por tipo y estatus desde Neon."""
    query = """
        SELECT
            tipo_comprobante,
            estatus,
            moneda,
            metodo_pago,
            COUNT(*)                                    AS cantidad,
            SUM(total * COALESCE(tipo_cambio, 1))       AS total_mxn,
            SUM(subtotal * COALESCE(tipo_cambio, 1))    AS subtotal_mxn,
            SUM(impuestos * COALESCE(tipo_cambio, 1))   AS impuestos_mxn,
            MIN(fecha_emision)                          AS primera_fecha,
            MAX(fecha_emision)                          AS ultima_fecha
        FROM cfdi_ventas
        WHERE empresa_id = %s
        GROUP BY tipo_comprobante, estatus, moneda, metodo_pago
        ORDER BY cantidad DESC
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
        logger.error(f"Error cargando universo CFDI: {e}")
        st.error(f"❌ Error al consultar la base de datos: {e}")
        return pd.DataFrame()
    finally:
        if conn:
            conn.close()


def _cargar_detalle(empresa_id: str, neon_url: str,
                    tipo: str | None, estatus: str | None) -> pd.DataFrame:
    """Carga detalle individual de CFDIs con filtros opcionales."""
    conditions = ["empresa_id = %s"]
    params: list = [empresa_id]
    if tipo:
        conditions.append("tipo_comprobante = %s")
        params.append(tipo)
    if estatus:
        conditions.append("estatus = %s")
        params.append(estatus)

    where = " AND ".join(conditions)
    query = f"""
        SELECT
            uuid_sat,
            serie,
            folio,
            fecha_emision::date      AS fecha,
            emisor_rfc,
            receptor_rfc,
            receptor_nombre,
            tipo_comprobante,
            estatus,
            moneda,
            total,
            tipo_cambio,
            ROUND(total * COALESCE(tipo_cambio,1), 2) AS total_mxn,
            metodo_pago
        FROM cfdi_ventas
        WHERE {where}
        ORDER BY fecha_emision DESC
        LIMIT 5000
    """
    conn = None
    try:
        conn = psycopg2.connect(neon_url)
        cur = conn.cursor()
        cur.execute(query, params)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
        return pd.DataFrame(rows, columns=cols)
    except Exception as e:
        logger.error(f"Error cargando detalle: {e}")
        return pd.DataFrame()
    finally:
        if conn:
            conn.close()


def _cargar_tendencia(empresa_id: str, neon_url: str) -> pd.DataFrame:
    """Tendencia mensual de CFDIs emitidos (vigentes vs cancelados)."""
    query = """
        SELECT
            DATE_TRUNC('month', fecha_emision)::date AS mes,
            tipo_comprobante,
            estatus,
            COUNT(*)                                 AS cantidad,
            SUM(total * COALESCE(tipo_cambio,1))     AS total_mxn
        FROM cfdi_ventas
        WHERE empresa_id = %s
        GROUP BY 1, 2, 3
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
        logger.error(f"Error cargando tendencia: {e}")
        return pd.DataFrame()
    finally:
        if conn:
            conn.close()


def run():
    st.title("📋 Universo de CFDIs")
    st.caption("Composición completa del portafolio: tipo de comprobante y estatus")

    empresa_id = st.session_state.get("empresa_id")
    empresa_nombre = st.session_state.get("empresa_nombre", "")
    neon_url = _get_neon_url()

    if not empresa_id or not neon_url:
        st.warning("⚠️ Debes iniciar sesión para ver este reporte.")
        return

    # ─── Carga ───────────────────────────────────────────────────────────────
    with st.spinner("Consultando base de datos..."):
        df_resumen = _cargar_datos(empresa_id, neon_url)
        df_tendencia = _cargar_tendencia(empresa_id, neon_url)

    if df_resumen.empty:
        st.info("📭 No hay CFDIs registrados para esta empresa.")
        return

    # Mapear etiquetas
    df_resumen["tipo_label"] = df_resumen["tipo_comprobante"].map(TIPO_LABEL).fillna(df_resumen["tipo_comprobante"])
    df_resumen["total_mxn"] = pd.to_numeric(df_resumen["total_mxn"], errors="coerce").fillna(0)
    df_resumen["cantidad"] = pd.to_numeric(df_resumen["cantidad"], errors="coerce").fillna(0).astype(int)

    # ─── KPIs globales ───────────────────────────────────────────────────────
    total_cfdi = int(df_resumen["cantidad"].sum())
    total_vigentes = int(df_resumen.loc[df_resumen["estatus"] == "vigente", "cantidad"].sum())
    total_cancelados = int(df_resumen.loc[df_resumen["estatus"] == "cancelado", "cantidad"].sum())
    monto_vigente = float(df_resumen.loc[df_resumen["estatus"] == "vigente", "total_mxn"].sum())
    monto_cancelado = float(df_resumen.loc[df_resumen["estatus"] == "cancelado", "total_mxn"].sum())
    pct_cancelado = (total_cancelados / total_cfdi * 100) if total_cfdi else 0

    if empresa_nombre:
        st.markdown(f"**Empresa:** {empresa_nombre}")
    st.markdown("---")

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Total CFDIs", f"{total_cfdi:,}")
    col2.metric("Vigentes", f"{total_vigentes:,}", help="Con estatus vigente")
    col3.metric("Cancelados", f"{total_cancelados:,}",
                delta=f"{pct_cancelado:.1f}% del total" if total_cancelados else None,
                delta_color="off")
    col4.metric("Monto vigente (MXN)", f"${monto_vigente:,.0f}")
    col5.metric("Monto cancelado (MXN)", f"${monto_cancelado:,.0f}")

    st.markdown("---")

    # ─── Gráficas principales ─────────────────────────────────────────────────
    tab1, tab2, tab3, tab4 = st.tabs(
        ["🥧 Por Tipo", "🔴 Por Estatus", "📅 Tendencia mensual", "🔍 Detalle"]
    )

    # ── Tab 1: Por tipo ──────────────────────────────────────────────────────
    with tab1:
        # Agrupar por tipo independiente de estatus
        df_tipo = (
            df_resumen.groupby("tipo_label", as_index=False)
            .agg(cantidad=("cantidad", "sum"), total_mxn=("total_mxn", "sum"))
            .sort_values("cantidad", ascending=False)
        )

        col_a, col_b = st.columns([1, 1])
        with col_a:
            fig = px.pie(
                df_tipo,
                names="tipo_label",
                values="cantidad",
                title="CFDIs por tipo (cantidad)",
                color="tipo_label",
                color_discrete_map=TIPO_COLOR,
                hole=0.4,
            )
            fig.update_traces(textinfo="percent+label+value")
            fig.update_layout(showlegend=False, height=380)
            st.plotly_chart(fig, use_container_width=True)

        with col_b:
            fig2 = px.bar(
                df_tipo.sort_values("total_mxn", ascending=True),
                x="total_mxn",
                y="tipo_label",
                orientation="h",
                title="Monto total por tipo (MXN)",
                color="tipo_label",
                color_discrete_map=TIPO_COLOR,
                text=df_tipo.sort_values("total_mxn", ascending=True)["total_mxn"].apply(lambda x: f"${x:,.0f}"),
            )
            fig2.update_traces(textposition="outside")
            fig2.update_layout(showlegend=False, height=380, xaxis_title="MXN", yaxis_title="")
            st.plotly_chart(fig2, use_container_width=True)

        st.dataframe(
            df_tipo.rename(columns={"tipo_label": "Tipo", "cantidad": "CFDIs", "total_mxn": "Total MXN"})
                   .assign(**{"Total MXN": lambda d: d["Total MXN"].apply(lambda x: f"${x:,.2f}")}),
            use_container_width=True, hide_index=True
        )

    # ── Tab 2: Por estatus ───────────────────────────────────────────────────
    with tab2:
        # Tabla cruzada tipo × estatus
        df_cross = df_resumen.pivot_table(
            index="tipo_label",
            columns="estatus",
            values="cantidad",
            aggfunc="sum",
            fill_value=0,
        ).reset_index()

        df_cross_monto = df_resumen.pivot_table(
            index="tipo_label",
            columns="estatus",
            values="total_mxn",
            aggfunc="sum",
            fill_value=0,
        ).reset_index()

        col_a, col_b = st.columns([1, 1])
        with col_a:
            df_est = df_resumen.groupby("estatus", as_index=False).agg(
                cantidad=("cantidad", "sum"), total_mxn=("total_mxn", "sum")
            )
            fig = go.Figure()
            for _, row in df_est.iterrows():
                color = ESTATUS_COLOR.get(row["estatus"], "#888")
                fig.add_trace(go.Bar(
                    name=row["estatus"].capitalize(),
                    x=[row["estatus"].capitalize()],
                    y=[row["cantidad"]],
                    marker_color=color,
                    text=[f'{int(row["cantidad"]):,}'],
                    textposition="outside",
                ))
            fig.update_layout(title="CFDIs por estatus", height=380,
                              showlegend=False, yaxis_title="Cantidad")
            st.plotly_chart(fig, use_container_width=True)

        with col_b:
            # Sunburst tipo → estatus
            df_sun = df_resumen[df_resumen["cantidad"] > 0].copy()
            fig_sun = px.sunburst(
                df_sun,
                path=["tipo_label", "estatus"],
                values="cantidad",
                title="Composición tipo × estatus",
                color="estatus",
                color_discrete_map=ESTATUS_COLOR,
            )
            fig_sun.update_layout(height=380)
            st.plotly_chart(fig_sun, use_container_width=True)

        st.subheader("Tabla cruzada tipo × estatus (cantidad)")
        st.dataframe(df_cross.rename(columns={"tipo_label": "Tipo"}),
                     use_container_width=True, hide_index=True)

        st.subheader("Tabla cruzada tipo × estatus (monto MXN)")
        disp_monto = df_cross_monto.copy()
        for col in disp_monto.columns:
            if col != "tipo_label":
                disp_monto[col] = disp_monto[col].apply(lambda x: f"${x:,.2f}")
        st.dataframe(disp_monto.rename(columns={"tipo_label": "Tipo"}),
                     use_container_width=True, hide_index=True)

    # ── Tab 3: Tendencia mensual ─────────────────────────────────────────────
    with tab3:
        if df_tendencia.empty:
            st.info("Sin datos de tendencia.")
        else:
            df_tendencia["mes"] = pd.to_datetime(df_tendencia["mes"])
            df_tendencia["tipo_label"] = df_tendencia["tipo_comprobante"].map(TIPO_LABEL).fillna(df_tendencia["tipo_comprobante"])
            df_tendencia["total_mxn"] = pd.to_numeric(df_tendencia["total_mxn"], errors="coerce").fillna(0)

            # Filtros rápidos
            col_f1, col_f2 = st.columns(2)
            tipos_disp = sorted(df_tendencia["tipo_label"].unique())
            sel_tipo = col_f1.multiselect("Tipo de comprobante", tipos_disp, default=tipos_disp)
            sel_est = col_f2.multiselect("Estatus", ["vigente", "cancelado"], default=["vigente", "cancelado"])

            df_t = df_tendencia[
                df_tendencia["tipo_label"].isin(sel_tipo) &
                df_tendencia["estatus"].isin(sel_est)
            ].copy()
            df_t["etiqueta"] = df_t["tipo_label"] + " / " + df_t["estatus"]

            fig_tend = px.bar(
                df_t,
                x="mes",
                y="cantidad",
                color="etiqueta",
                title="CFDIs emitidos por mes (tipo y estatus)",
                barmode="stack",
                labels={"mes": "Mes", "cantidad": "CFDIs", "etiqueta": ""},
            )
            fig_tend.update_layout(height=420, xaxis_tickformat="%b %Y")
            st.plotly_chart(fig_tend, use_container_width=True)

            fig_monto = px.line(
                df_t,
                x="mes",
                y="total_mxn",
                color="etiqueta",
                title="Monto facturado por mes (MXN)",
                markers=True,
                labels={"mes": "Mes", "total_mxn": "MXN", "etiqueta": ""},
            )
            fig_monto.update_layout(height=380, xaxis_tickformat="%b %Y")
            st.plotly_chart(fig_monto, use_container_width=True)

    # ── Tab 4: Detalle individual ────────────────────────────────────────────
    with tab4:
        st.subheader("Filtros")
        col_f1, col_f2, col_f3 = st.columns(3)

        tipos_opt = {v: k for k, v in TIPO_LABEL.items()}
        tipos_opt["Todos"] = None
        sel_tipo_det = col_f1.selectbox(
            "Tipo de comprobante",
            ["Todos"] + list(TIPO_LABEL.values()),
            index=0,
        )
        sel_est_det = col_f2.selectbox(
            "Estatus", ["Todos", "vigente", "cancelado"], index=0
        )
        col_f3.write("")

        tipo_filter = tipos_opt.get(sel_tipo_det)     # None si "Todos"
        est_filter  = None if sel_est_det == "Todos" else sel_est_det

        with st.spinner("Cargando detalle..."):
            df_det = _cargar_detalle(empresa_id, neon_url, tipo_filter, est_filter)

        if df_det.empty:
            st.info("No hay registros con esos filtros.")
        else:
            df_det["tipo_label"] = df_det["tipo_comprobante"].map(TIPO_LABEL).fillna(df_det["tipo_comprobante"])
            df_det["total_mxn"] = pd.to_numeric(df_det["total_mxn"], errors="coerce")
            df_det["total"]     = pd.to_numeric(df_det["total"], errors="coerce")

            st.caption(f"**{len(df_det):,}** CFDIs encontrados")

            def _color_estatus(val):
                if val == "cancelado":
                    return "background-color: #ffebee; color: #c62828"
                return ""

            disp = df_det[[
                "uuid_sat", "fecha", "receptor_nombre", "receptor_rfc",
                "tipo_label", "estatus", "moneda", "total", "total_mxn", "metodo_pago"
            ]].copy()
            disp.columns = [
                "UUID", "Fecha", "Receptor", "RFC Receptor",
                "Tipo", "Estatus", "Moneda", "Total orig.", "Total MXN", "Método pago"
            ]

            st.dataframe(
                disp.style.applymap(_color_estatus, subset=["Estatus"]),
                use_container_width=True,
                hide_index=True,
                height=500,
            )

            # Descarga CSV
            csv = df_det.to_csv(index=False).encode("utf-8")
            st.download_button(
                "⬇️ Descargar CSV",
                data=csv,
                file_name="universo_cfdi.csv",
                mime="text/csv",
            )
