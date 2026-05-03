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


def _cargar_retenciones(empresa_id: str, neon_url: str) -> pd.DataFrame:
    """Carga facturas con retenciones (IVA retenido, ISR retenido)."""
    query = """
        SELECT
            uuid_sat,
            fecha_emision::date                                      AS fecha,
            receptor_rfc,
            receptor_nombre,
            linea_negocio,
            metodo_pago,
            ROUND(subtotal   * COALESCE(tipo_cambio,1), 2)         AS subtotal_mxn,
            ROUND(impuestos  * COALESCE(tipo_cambio,1), 2)         AS iva_trasladado_mxn,
            ROUND(iva_retenido * COALESCE(tipo_cambio,1), 2)       AS iva_retenido_mxn,
            ROUND(isr_retenido * COALESCE(tipo_cambio,1), 2)       AS isr_retenido_mxn,
            ROUND(
                (iva_retenido + isr_retenido) * COALESCE(tipo_cambio,1), 2
            )                                                        AS total_retenido_mxn,
            ROUND(total      * COALESCE(tipo_cambio,1), 2)         AS total_mxn
        FROM cfdi_ventas
        WHERE empresa_id = %s
          AND tipo_comprobante = 'I'
          AND estatus = 'vigente'
          AND (iva_retenido > 0 OR isr_retenido > 0)
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
        logger.error(f"Error cargando retenciones: {e}")
        return pd.DataFrame()
    finally:
        if conn:
            conn.close()


def _cargar_nomina(empresa_id: str, neon_url: str) -> pd.DataFrame:
    """Carga CFDIs de nómina (tipo_comprobante = 'N')."""
    query = """
        SELECT
            uuid_sat,
            fecha_emision::date                                 AS fecha,
            receptor_rfc                                        AS empleado_rfc,
            receptor_nombre                                     AS empleado_nombre,
            moneda,
            ROUND(subtotal   * COALESCE(tipo_cambio,1), 2)    AS percepciones_mxn,
            ROUND(descuento  * COALESCE(tipo_cambio,1), 2)    AS deducciones_mxn,
            ROUND(isr_retenido * COALESCE(tipo_cambio,1), 2)  AS isr_retenido_mxn,
            ROUND(total      * COALESCE(tipo_cambio,1), 2)    AS neto_pagado_mxn
        FROM cfdi_ventas
        WHERE empresa_id = %s
          AND tipo_comprobante = 'N'
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
        logger.error(f"Error cargando nómina: {e}")
        return pd.DataFrame()
    finally:
        if conn:
            conn.close()


def _cargar_tendencia_nomina(empresa_id: str, neon_url: str) -> pd.DataFrame:
    """Tendencia mensual de nómina: percepciones, deducciones, ISR, neto."""
    query = """
        SELECT
            DATE_TRUNC('month', fecha_emision)::date           AS mes,
            COUNT(*)                                            AS num_recibos,
            COUNT(DISTINCT receptor_rfc)                        AS num_empleados,
            ROUND(SUM(subtotal   * COALESCE(tipo_cambio,1)), 2) AS percepciones_mxn,
            ROUND(SUM(descuento  * COALESCE(tipo_cambio,1)), 2) AS deducciones_mxn,
            ROUND(SUM(isr_retenido * COALESCE(tipo_cambio,1)), 2) AS isr_retenido_mxn,
            ROUND(SUM(total      * COALESCE(tipo_cambio,1)), 2) AS neto_pagado_mxn
        FROM cfdi_ventas
        WHERE empresa_id = %s
          AND tipo_comprobante = 'N'
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
        logger.error(f"Error cargando tendencia nómina: {e}")
        return pd.DataFrame()
    finally:
        if conn:
            conn.close()


def _run_nomina(empresa_id: str, empresa_nombre: str, neon_url: str):
    """Vista de desglose fiscal — Nómina."""
    with st.spinner("Consultando nómina..."):
        df_nom = _cargar_nomina(empresa_id, neon_url)
        df_tend = _cargar_tendencia_nomina(empresa_id, neon_url)

    if df_nom.empty:
        st.info(
            "📭 No hay recibos de nómina registrados.\n\n"
            "Asegúrate de haber subido XMLs con `TipoDeComprobante='N'` "
            "mediante el módulo **📦 Ingesta CFDIs**."
        )
        return

    for col in ["percepciones_mxn", "deducciones_mxn", "isr_retenido_mxn", "neto_pagado_mxn"]:
        df_nom[col] = pd.to_numeric(df_nom[col], errors="coerce").fillna(0)

    # ── KPIs ─────────────────────────────────────────────────────────────────
    num_recibos     = len(df_nom)
    num_empleados   = df_nom["empleado_rfc"].nunique()
    total_percepciones = df_nom["percepciones_mxn"].sum()
    total_deducciones  = df_nom["deducciones_mxn"].sum()
    total_isr       = df_nom["isr_retenido_mxn"].sum()
    total_neto      = df_nom["neto_pagado_mxn"].sum()
    pct_deduccion   = (total_deducciones / total_percepciones * 100) if total_percepciones else 0

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Recibos",             f"{num_recibos:,}")
    c2.metric("Empleados únicos",    f"{num_empleados:,}")
    c3.metric("Percepciones (MXN)",  f"${total_percepciones:,.0f}",
              help="Salario bruto total antes de deducciones")
    c4.metric("Deducciones (MXN)",   f"${total_deducciones:,.0f}",
              delta=f"{pct_deduccion:.1f}% de percepciones", delta_color="inverse")
    c5.metric("ISR retenido (MXN)",  f"${total_isr:,.0f}",
              help="ISR descontado al empleado según tabla SAT")
    c6.metric("Neto pagado (MXN)",   f"${total_neto:,.0f}",
              help="Percepciones − Deducciones = importe depositado")

    st.markdown("---")

    tab_tend, tab_emp, tab_det = st.tabs(
        ["📅 Tendencia mensual", "👷 Por Empleado", "📄 Detalle recibos"]
    )

    # ── Tab 1: Tendencia mensual ──────────────────────────────────────────────
    with tab_tend:
        if df_tend.empty:
            st.info("Sin datos de tendencia.")
        else:
            for col in ["percepciones_mxn", "deducciones_mxn", "isr_retenido_mxn", "neto_pagado_mxn"]:
                df_tend[col] = pd.to_numeric(df_tend[col], errors="coerce").fillna(0)
            df_tend["mes"] = pd.to_datetime(df_tend["mes"])
            df_t = df_tend.sort_values("mes")

            # Barras: percepciones vs deducciones vs neto
            fig_bar = go.Figure()
            fig_bar.add_trace(go.Bar(
                x=df_t["mes"], y=df_t["percepciones_mxn"],
                name="Percepciones (bruto)",
                marker_color="#2196F3",
                text=df_t["percepciones_mxn"].apply(lambda x: f"${x:,.0f}"),
                textposition="inside",
            ))
            fig_bar.add_trace(go.Bar(
                x=df_t["mes"], y=df_t["deducciones_mxn"],
                name="Deducciones",
                marker_color="#F44336",
                text=df_t["deducciones_mxn"].apply(lambda x: f"${x:,.0f}"),
                textposition="inside",
            ))
            fig_bar.add_trace(go.Bar(
                x=df_t["mes"], y=df_t["isr_retenido_mxn"],
                name="ISR retenido",
                marker_color="#FF9800",
            ))
            fig_bar.update_layout(
                barmode="group",
                title="Nómina mensual: percepciones vs deducciones",
                height=400, xaxis_tickformat="%b %Y", yaxis_title="MXN",
                legend=dict(orientation="h", y=1.08),
            )
            st.plotly_chart(fig_bar, use_container_width=True)

            # Línea: neto pagado + empleados
            fig_neto = go.Figure()
            fig_neto.add_trace(go.Scatter(
                x=df_t["mes"], y=df_t["neto_pagado_mxn"],
                name="Neto pagado", mode="lines+markers",
                line=dict(color="#4CAF50", width=2), yaxis="y1",
            ))
            fig_neto.add_trace(go.Scatter(
                x=df_t["mes"], y=df_t["num_empleados"],
                name="Empleados", mode="lines+markers",
                line=dict(color="#9C27B0", width=2, dash="dot"), yaxis="y2",
            ))
            fig_neto.update_layout(
                title="Neto pagado y empleados por mes",
                height=320, xaxis_tickformat="%b %Y",
                yaxis=dict(title="Neto pagado (MXN)", side="left"),
                yaxis2=dict(title="Empleados", side="right", overlaying="y"),
                legend=dict(orientation="h", y=1.08),
            )
            st.plotly_chart(fig_neto, use_container_width=True)

            # Tabla mensual
            disp_t = df_t[[
                "mes", "num_recibos", "num_empleados",
                "percepciones_mxn", "deducciones_mxn", "isr_retenido_mxn", "neto_pagado_mxn"
            ]].copy()
            disp_t["mes"] = disp_t["mes"].dt.strftime("%b %Y")
            disp_t.columns = [
                "Mes", "Recibos", "Empleados",
                "Percepciones", "Deducciones", "ISR retenido", "Neto pagado"
            ]
            for col in ["Percepciones", "Deducciones", "ISR retenido", "Neto pagado"]:
                disp_t[col] = disp_t[col].apply(lambda x: f"${x:,.2f}")
            st.dataframe(disp_t, use_container_width=True, hide_index=True)

    # ── Tab 2: Por Empleado ───────────────────────────────────────────────────
    with tab_emp:
        df_emp = (
            df_nom.groupby(["empleado_rfc", "empleado_nombre"], as_index=False)
            .agg(
                recibos=("uuid_sat", "count"),
                percepciones=("percepciones_mxn", "sum"),
                deducciones=("deducciones_mxn", "sum"),
                isr=("isr_retenido_mxn", "sum"),
                neto=("neto_pagado_mxn", "sum"),
            )
            .sort_values("percepciones", ascending=False)
        )
        df_emp["pct_deduccion"] = (df_emp["deducciones"] / df_emp["percepciones"] * 100).round(1)

        top_n = min(15, len(df_emp))
        df_top = df_emp.head(top_n).sort_values("percepciones", ascending=True)

        col_g1, col_g2 = st.columns([3, 2])
        with col_g1:
            fig_emp = go.Figure()
            fig_emp.add_trace(go.Bar(
                y=df_top["empleado_nombre"], x=df_top["percepciones"],
                name="Percepciones", orientation="h", marker_color="#2196F3",
            ))
            fig_emp.add_trace(go.Bar(
                y=df_top["empleado_nombre"], x=df_top["neto"],
                name="Neto pagado", orientation="h", marker_color="#4CAF50",
            ))
            fig_emp.update_layout(
                barmode="overlay", height=max(350, top_n * 40),
                title=f"Top {top_n} empleados — percepciones vs neto",
                xaxis_title="MXN", yaxis_title="",
                legend=dict(orientation="h", y=1.05),
            )
            st.plotly_chart(fig_emp, use_container_width=True)

        with col_g2:
            fig_isr = px.pie(
                df_emp.head(10),
                names="empleado_nombre", values="isr",
                title="ISR retenido — top 10 empleados",
                hole=0.4,
                color_discrete_sequence=px.colors.sequential.Oranges_r,
            )
            fig_isr.update_traces(textinfo="percent+label")
            fig_isr.update_layout(showlegend=False, height=350)
            st.plotly_chart(fig_isr, use_container_width=True)

        disp_emp = df_emp.copy()
        for col in ["percepciones", "deducciones", "isr", "neto"]:
            disp_emp[col] = disp_emp[col].apply(lambda x: f"${x:,.2f}")
        disp_emp.columns = [
            "RFC", "Empleado", "Recibos",
            "Percepciones", "Deducciones", "ISR retenido", "Neto pagado", "% Deducción"
        ]
        st.dataframe(disp_emp, use_container_width=True, hide_index=True)

    # ── Tab 3: Detalle recibos ────────────────────────────────────────────────
    with tab_det:
        buscar = st.text_input("Buscar empleado (nombre o RFC)", "")
        df_det = df_nom.copy()
        if buscar:
            mask = (
                df_det["empleado_nombre"].str.contains(buscar, case=False, na=False) |
                df_det["empleado_rfc"].str.contains(buscar, case=False, na=False)
            )
            df_det = df_det[mask]

        st.caption(f"**{len(df_det):,}** recibos")

        disp_det = df_det[[
            "fecha", "empleado_nombre", "empleado_rfc",
            "percepciones_mxn", "deducciones_mxn", "isr_retenido_mxn",
            "neto_pagado_mxn", "moneda", "uuid_sat"
        ]].copy()
        disp_det.columns = [
            "Fecha", "Empleado", "RFC",
            "Percepciones", "Deducciones", "ISR retenido",
            "Neto pagado", "Moneda", "UUID SAT"
        ]
        st.dataframe(
            disp_det.style.format({
                "Percepciones":  "${:,.2f}",
                "Deducciones":   "${:,.2f}",
                "ISR retenido":  "${:,.2f}",
                "Neto pagado":   "${:,.2f}",
            }),
            use_container_width=True, hide_index=True, height=480,
        )
        csv_n = df_det.to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ Descargar CSV nómina",
            data=csv_n,
            file_name="nomina_fiscal.csv",
            mime="text/csv",
        )





def _cargar_impuestos_por_concepto(empresa_id: str, neon_url: str) -> pd.DataFrame:
    """
    Consolida impuestos estimados por clave de producto SAT.

    Usa cfdi_conceptos JOIN cfdi_ventas para distribuir la base gravable
    por concepto según objeto_imp:
      - '02' → gravado (tasa IVA implícita del comprobante)
      - '01' → exento / no objeto
    """
    query = """
        SELECT
            cc.clave_prod_serv,
            cc.descripcion,
            cc.objeto_imp,
            cc.categoria,
            cv.linea_negocio,
            COUNT(DISTINCT cc.cfdi_venta_id)                         AS num_facturas,
            ROUND(SUM((cc.importe - COALESCE(cc.descuento,0))
                      * COALESCE(cv.tipo_cambio,1)), 2)              AS base_mxn,
            -- IVA estimado solo para conceptos gravados (objeto_imp = '02')
            ROUND(SUM(
                CASE WHEN cc.objeto_imp = '02'
                     THEN (cc.importe - COALESCE(cc.descuento,0))
                          * COALESCE(cv.tipo_cambio,1) * 0.16
                     ELSE 0
                END
            ), 2)                                                     AS iva_estimado_mxn
        FROM cfdi_conceptos cc
        JOIN cfdi_ventas cv ON cv.id = cc.cfdi_venta_id
        WHERE cv.empresa_id = %s
          AND cv.tipo_comprobante = 'I'
          AND cv.estatus = 'vigente'
        GROUP BY cc.clave_prod_serv, cc.descripcion, cc.objeto_imp, cc.categoria, cv.linea_negocio
        ORDER BY base_mxn DESC
        LIMIT 500
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
        logger.error(f"Error cargando impuestos por concepto: {e}")
        return pd.DataFrame()
    finally:
        if conn:
            conn.close()


def _run_ventas(empresa_id: str, empresa_nombre: str, neon_url: str):
    """Vista de desglose fiscal — Ventas / Ingresos (tipo_comprobante='I')."""
    with st.spinner("Consultando base de datos..."):
        df           = _cargar_fiscal(empresa_id, neon_url)
        df_tendencia = _cargar_tendencia_fiscal(empresa_id, neon_url)
        df_ret       = _cargar_retenciones(empresa_id, neon_url)
        df_conceptos = _cargar_impuestos_por_concepto(empresa_id, neon_url)

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

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
        ["📅 Tendencia mensual", "👥 Por Cliente", "📦 Por Línea de Negocio",
         "📄 Detalle", "🏦 Retenciones", "🏷️ Por Concepto SAT"]
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

    # ── Tab 5: Retenciones ───────────────────────────────────────────────────
    with tab5:
        st.subheader("Retenciones fiscales — IVA retenido e ISR retenido")

        # KPIs de retenciones globales (todos los registros, no solo los que tienen)
        conn_r = None
        try:
            conn_r = psycopg2.connect(neon_url)
            cur_r = conn_r.cursor()
            cur_r.execute("""
                SELECT
                    COUNT(*) FILTER (WHERE iva_retenido > 0 OR isr_retenido > 0) AS facturas_con_ret,
                    ROUND(SUM(iva_retenido  * COALESCE(tipo_cambio,1)), 2)        AS total_iva_ret,
                    ROUND(SUM(isr_retenido  * COALESCE(tipo_cambio,1)), 2)        AS total_isr_ret,
                    ROUND(SUM((iva_retenido + isr_retenido) * COALESCE(tipo_cambio,1)), 2) AS total_ret,
                    ROUND(SUM(impuestos * COALESCE(tipo_cambio,1)), 2)            AS total_iva_tras
                FROM cfdi_ventas
                WHERE empresa_id = %s
                  AND tipo_comprobante = 'I'
                  AND estatus = 'vigente'
            """, (empresa_id,))
            kpi = cur_r.fetchone()
        except Exception:
            kpi = None
        finally:
            if conn_r:
                conn_r.close()

        if kpi:
            n_ret, iva_ret, isr_ret, tot_ret, iva_tras = kpi
            iva_ret   = float(iva_ret   or 0)
            isr_ret   = float(isr_ret   or 0)
            tot_ret   = float(tot_ret   or 0)
            iva_tras  = float(iva_tras  or 0)
            pct_ret   = (tot_ret / iva_tras * 100) if iva_tras else 0

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Facturas con retención",  f"{int(n_ret or 0):,}")
            c2.metric("IVA retenido (MXN)",       f"${iva_ret:,.2f}",
                      help="IVA que el receptor retiene al emisor (Art. 1-A LIVA)")
            c3.metric("ISR retenido (MXN)",       f"${isr_ret:,.2f}",
                      help="ISR que el receptor retiene al emisor (Art. 106/127 LISR)")
            c4.metric("Total retenido (MXN)",     f"${tot_ret:,.2f}",
                      delta=f"{pct_ret:.1f}% del IVA trasladado" if iva_tras else None,
                      delta_color="off")

        st.markdown("---")

        if df_ret.empty:
            st.info(
                "📭 No hay facturas con retenciones registradas para esta empresa.\n\n"
                "Las retenciones aplican principalmente a:\n"
                "- **Personas Físicas** con actividad empresarial o servicios profesionales\n"
                "- **Plataformas tecnológicas** (retención especial)\n"
                "- **Arrendamiento**\n\n"
                "Si subiste XMLs con retenciones y no aparecen, verifica que el campo "
                "`<cfdi:Retencion>` esté presente en el XML original."
            )
        else:
            for col in ["subtotal_mxn", "iva_trasladado_mxn", "iva_retenido_mxn",
                        "isr_retenido_mxn", "total_retenido_mxn", "total_mxn"]:
                df_ret[col] = pd.to_numeric(df_ret[col], errors="coerce").fillna(0)

            # Gráfica por tipo de retención
            tipos = {
                "IVA retenido":  float(df_ret["iva_retenido_mxn"].sum()),
                "ISR retenido":  float(df_ret["isr_retenido_mxn"].sum()),
            }
            fig_tipos = go.Figure(go.Bar(
                x=list(tipos.keys()),
                y=list(tipos.values()),
                marker_color=["#FF9800", "#9C27B0"],
                text=[f"${v:,.2f}" for v in tipos.values()],
                textposition="outside",
            ))
            fig_tipos.update_layout(
                title="IVA retenido vs ISR retenido (MXN)",
                height=320, yaxis_title="MXN", showlegend=False
            )
            st.plotly_chart(fig_tipos, use_container_width=True)

            # Tabla detallada
            st.caption(f"**{len(df_ret):,}** facturas con retenciones")
            disp_ret = df_ret[[
                "fecha", "receptor_nombre", "receptor_rfc",
                "subtotal_mxn", "iva_trasladado_mxn",
                "iva_retenido_mxn", "isr_retenido_mxn",
                "total_retenido_mxn", "total_mxn", "uuid_sat"
            ]].copy()
            disp_ret.columns = [
                "Fecha", "Receptor", "RFC",
                "Subtotal", "IVA trasladado",
                "IVA retenido", "ISR retenido",
                "Total retenido", "Total c/IVA", "UUID SAT"
            ]
            st.dataframe(
                disp_ret.style.format({
                    "Subtotal":        "${:,.2f}",
                    "IVA trasladado":  "${:,.2f}",
                    "IVA retenido":    "${:,.2f}",
                    "ISR retenido":    "${:,.2f}",
                    "Total retenido":  "${:,.2f}",
                    "Total c/IVA":     "${:,.2f}",
                }),
                use_container_width=True,
                hide_index=True,
                height=420,
            )

            csv_ret = df_ret.to_csv(index=False).encode("utf-8")
            st.download_button(
                "⬇️ Descargar CSV retenciones",
                data=csv_ret,
                file_name="retenciones.csv",
                mime="text/csv",
            )

    # ── Tab 6: Por Concepto SAT ──────────────────────────────────────────────
    with tab6:
        st.subheader("Impuestos estimados por clave de concepto SAT")
        st.caption(
            "Base gravable e IVA estimado (16%) calculados desde `cfdi_conceptos`. "
            "Los conceptos con **objeto_imp = '01'** son exentos."
        )

        if df_conceptos.empty:
            st.info(
                "📭 No hay datos de conceptos para esta empresa. "
                "Verifica que los XMLs hayan sido ingresados con sus conceptos."
            )
        else:
            for col in ["base_mxn", "iva_estimado_mxn", "num_facturas"]:
                df_conceptos[col] = pd.to_numeric(df_conceptos[col], errors="coerce").fillna(0)

            # KPIs
            base_total_c  = df_conceptos["base_mxn"].sum()
            iva_total_c   = df_conceptos["iva_estimado_mxn"].sum()
            exentos_base  = df_conceptos.loc[df_conceptos["objeto_imp"] == "01", "base_mxn"].sum()
            pct_exento    = (exentos_base / base_total_c * 100) if base_total_c else 0

            c1, c2, c3 = st.columns(3)
            c1.metric("Base gravable total (MXN)", f"${base_total_c:,.0f}")
            c2.metric("IVA estimado 16% (MXN)",    f"${iva_total_c:,.0f}")
            c3.metric("Base exenta (MXN)",          f"${exentos_base:,.0f}",
                      delta=f"{pct_exento:.1f}% del total", delta_color="off")

            st.markdown("---")

            # Gráfica top 10 por base gravable
            top10 = df_conceptos.nlargest(10, "base_mxn")
            fig_c = go.Figure(go.Bar(
                x=top10["base_mxn"],
                y=top10["clave_prod_serv"] + " — " + top10["descripcion"].str[:40],
                orientation="h",
                marker_color="#1565C0",
                text=[f"${v:,.0f}" for v in top10["base_mxn"]],
                textposition="outside",
            ))
            fig_c.update_layout(
                title="Top 10 conceptos por base gravable (MXN)",
                height=380,
                xaxis_title="MXN",
                yaxis={"autorange": "reversed"},
                showlegend=False,
            )
            st.plotly_chart(fig_c, use_container_width=True)

            # Tabla completa
            disp_c = df_conceptos[[
                "clave_prod_serv", "descripcion", "objeto_imp",
                "categoria", "linea_negocio", "num_facturas",
                "base_mxn", "iva_estimado_mxn",
            ]].copy()
            disp_c.columns = [
                "Clave SAT", "Descripción", "Obj. Imp",
                "Categoría", "Línea", "# Facturas",
                "Base (MXN)", "IVA est. (MXN)",
            ]
            st.dataframe(
                disp_c.style.format({
                    "Base (MXN)":     "${:,.2f}",
                    "IVA est. (MXN)": "${:,.2f}",
                }),
                use_container_width=True,
                hide_index=True,
                height=450,
            )

            csv_c = df_conceptos.to_csv(index=False).encode("utf-8")
            st.download_button(
                "⬇️ Descargar CSV por concepto",
                data=csv_c,
                file_name="impuestos_por_concepto.csv",
                mime="text/csv",
            )


def run():
    """Punto de entrada del módulo Desglose Fiscal."""
    empresa_id     = st.session_state.get("empresa_id")
    empresa_nombre = st.session_state.get("empresa_nombre", "")
    neon_url       = _get_neon_url()

    if not empresa_id or not neon_url:
        st.warning("⚠️ Debes iniciar sesión para ver este reporte.")
        return

    st.title("🧾 Desglose Fiscal")

    modo = st.radio(
        "Tipo de comprobante:",
        ["🧾 Ventas / Ingresos", "💼 Nómina"],
        horizontal=True,
        key="fiscal_modo",
    )

    st.markdown("---")

    if modo == "🧾 Ventas / Ingresos":
        _run_ventas(empresa_id, empresa_nombre, neon_url)
    else:
        _run_nomina(empresa_id, empresa_nombre, neon_url)
