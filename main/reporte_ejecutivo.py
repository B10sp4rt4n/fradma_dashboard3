"""
Módulo de Reporte Ejecutivo para el Dashboard Fradma.
Vista consolidada con KPIs críticos para dirección ejecutiva (CEO/CFO).
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
from utils.formatos import formato_moneda, formato_porcentaje, formato_compacto, now_mx
from utils.logger import configurar_logger
from utils.ai_helper_premium import generar_insights_ejecutivo_consolidado
from utils.cxc_helper import calcular_score_salud
from utils.roi_tracker import init_roi_tracker

# Configurar logger para este módulo
logger = configurar_logger("reporte_ejecutivo", nivel="INFO")


def mostrar_reporte_ejecutivo(df_ventas, df_cxc, habilitar_ia=False, openai_api_key=None):
    """
    Muestra el reporte ejecutivo consolidado con métricas clave de negocio.
    
    Args:
        df_ventas: DataFrame con datos de ventas
        df_cxc: DataFrame con datos de cuentas por cobrar
        habilitar_ia: Booleano para activar análisis con IA (default: False)
        openai_api_key: API key de OpenAI para análisis premium (default: None)
    """

    # Trabajar sobre copias locales para evitar efectos colaterales
    df_ventas = df_ventas.copy() if df_ventas is not None else pd.DataFrame()
    df_cxc = df_cxc.copy() if df_cxc is not None else pd.DataFrame()
    
    # === TRACKING ROI: Registrar generación de reporte ejecutivo ===
    try:
        roi_tracker = init_roi_tracker(st.session_state)
        roi_info = roi_tracker.track_action(
            module="exec_report",
            action="generate_exec_report",
            quantity=1.0,
            show_toast=False
        )
        # Mostrar toast al inicio
        st.toast(
            f"✨ Reporte Ejecutivo generado · 💰 Ahorraste {roi_info['hrs_saved']:.1f} hrs",
            icon="📈"
        )
    except Exception as e:
        # Continuar silenciosamente si hay error
        pass

    # -----------------------------------------------------------------
    # Normalización defensiva de columnas requeridas
    # -----------------------------------------------------------------

    # Asegurar compatibilidad de columna monetaria (USD)
    if "valor_usd" not in df_ventas.columns:
        for candidato in [
            "ventas_usd_con_iva",
            "ventas_usd",
            "importe",
            "monto_usd",
            "total_usd",
            "valor",
        ]:
            if candidato in df_ventas.columns:
                df_ventas = df_ventas.rename(columns={candidato: "valor_usd"})
                break

    if "valor_usd" in df_ventas.columns:
        df_ventas["valor_usd"] = pd.to_numeric(df_ventas["valor_usd"], errors="coerce").fillna(0)
    else:
        # Degradar de forma segura: el reporte sigue cargando, pero sin ventas
        df_ventas["valor_usd"] = 0
        st.warning(
            "⚠️ No se encontró columna de ventas en USD. "
            "Se esperaba 'valor_usd' (o alternativas como 'ventas_usd' / 'ventas_usd_con_iva' / 'importe')."
        )

    # Fecha (si existe) a datetime para cálculos mensuales
    if "fecha" in df_ventas.columns:
        df_ventas["fecha"] = pd.to_datetime(df_ventas["fecha"], errors="coerce")

    # Si no hay hoja de CxC separada, pero X AGENTE contiene columnas de cartera,
    # reutilizar df_ventas para construir la vista de CxC.
    if df_cxc.empty:
        cols_cartera = {
            "saldo",
            "saldo_usd",
            "saldo_adeudado",
            "dias_restante",
            "dias_de_credito",
            "dias_de_credit",
            "vencimient",
            "vencimiento",
            "fecha_de_pago",
            "fecha_pago",
            "fecha_tentativa_de_pag",
            "fecha_tentativa_de_pago",
            "estatus",
            "status",
            "pagado",
        }
        if len(cols_cartera.intersection(set(df_ventas.columns))) > 0:
            df_cxc = df_ventas.copy()

    # -------------------------
    # CxC: coerción numérica
    # -------------------------

    # Asegurar columna de saldo
    if "saldo_adeudado" not in df_cxc.columns:
        for candidato in [
            "saldo",
            "saldo_adeudo",
            "adeudo",
            "importe",
            "monto",
            "total",
            "saldo_usd",
        ]:
            if candidato in df_cxc.columns:
                df_cxc = df_cxc.rename(columns={candidato: "saldo_adeudado"})
                break

    if "saldo_adeudado" in df_cxc.columns:
        # Limpieza típica: quitar separadores de miles y símbolos
        saldo_txt = df_cxc["saldo_adeudado"].astype(str)
        saldo_txt = saldo_txt.str.replace(",", "", regex=False)
        saldo_txt = saldo_txt.str.replace("$", "", regex=False)
        df_cxc["saldo_adeudado"] = pd.to_numeric(saldo_txt, errors="coerce").fillna(0)
    else:
        df_cxc["saldo_adeudado"] = 0
    
    st.title("📊 Reporte Ejecutivo")
    st.markdown("### Vista Consolidada del Negocio — Dashboard para Dirección")

    # =====================================================================
    # SELECTOR DE PERIODO (global, aplica a las 3 tabs)
    # =====================================================================
    def _filtrar_periodo(df, modo):
        if "fecha" not in df.columns or df.empty:
            return df
        df = df.copy()
        df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
        df = df.dropna(subset=["fecha"])
        if df.empty:
            return df
        fmax = df["fecha"].max()
        if modo == "Último mes":
            return df[df["fecha"] >= fmax.replace(day=1)]
        elif modo == "Último trimestre":
            return df[df["fecha"] >= (fmax - pd.DateOffset(months=3))]
        elif modo == "Año actual":
            return df[df["fecha"].dt.year == fmax.year]
        return df

    periodo_opciones = {
        "Último mes":        lambda df: _filtrar_periodo(df, "Último mes"),
        "Último trimestre":  lambda df: _filtrar_periodo(df, "Último trimestre"),
        "Año actual":        lambda df: _filtrar_periodo(df, "Año actual"),
        "Todo el historial": lambda df: df,
    }

    col_periodo, col_info = st.columns([2, 3])
    with col_periodo:
        periodo_sel = st.selectbox(
            "📅 Período de análisis",
            list(periodo_opciones.keys()),
            index=3,
            help="Filtra los datos de ventas que se usan en todo el reporte",
        )
    
    # Aplicar filtro de periodo a ventas
    if "fecha" in df_ventas.columns and not df_ventas.empty:
        df_ventas["fecha"] = pd.to_datetime(df_ventas["fecha"], errors="coerce")
        df_v = periodo_opciones[periodo_sel](df_ventas)
        fecha_min_datos = df_v["fecha"].min() if not df_v.empty else None
        fecha_max_datos = df_v["fecha"].max() if not df_v.empty else None
    else:
        df_v = df_ventas
        fecha_min_datos = fecha_max_datos = None

    with col_info:
        if fecha_min_datos and fecha_max_datos:
            st.info(
                f"📅 **{periodo_sel}**: "
                f"{fecha_min_datos.strftime('%d/%m/%Y')} → {fecha_max_datos.strftime('%d/%m/%Y')}"
                f"  |  **{len(df_v):,}** registros"
            )

    st.markdown("---")

    # =====================================================================
    # TABS PRINCIPALES
    # =====================================================================
    tab_general, tab_comercial, tab_cxc = st.tabs([
        "📋 General",
        "📈 Comercial",
        "🏦 Cuentas por Cobrar",
    ])

    # ─────────────────────────────────────────────────────────────────────
    # CÁLCULOS COMPARTIDOS (necesarios en varias tabs)
    # ─────────────────────────────────────────────────────────────────────
    total_ventas    = df_v["valor_usd"].sum() if not df_v.empty else 0
    total_ops       = len(df_v)
    ticket_promedio = total_ventas / total_ops if total_ops > 0 else 0
    clientes_unicos = df_v["cliente"].nunique() if "cliente" in df_v.columns else 0

    # Variación mensual para alertas
    variacion_ventas = 0
    mes_actual_nombre = ""
    mes_anterior_nombre = ""
    dia_actual_en_mes = 0
    if "fecha" in df_v.columns and not df_v.empty:
        fecha_max = df_v["fecha"].max()
        mes_actual = fecha_max.replace(day=1)
        dia_actual_en_mes = fecha_max.day
        mes_anterior = (mes_actual - timedelta(days=1)).replace(day=1)
        fecha_limite_mes_anterior = mes_anterior.replace(
            day=min(dia_actual_en_mes, (mes_actual - timedelta(days=1)).day)
        )
        ventas_mes_actual   = df_v[df_v["fecha"] >= mes_actual]["valor_usd"].sum()
        ventas_mes_anterior = df_v[
            (df_v["fecha"] >= mes_anterior) & (df_v["fecha"] <= fecha_limite_mes_anterior)
        ]["valor_usd"].sum()
        variacion_ventas    = ((ventas_mes_actual - ventas_mes_anterior) / ventas_mes_anterior * 100) if ventas_mes_anterior > 0 else 0
        mes_actual_nombre   = fecha_max.strftime("%B %Y")
        mes_anterior_nombre = mes_anterior.strftime("%B %Y")
    else:
        ventas_mes_actual = total_ventas

    # CxC: normalizar y calcular métricas (compartido entre General y CxC tab)
    df_cxc_local = df_cxc.copy()
    col_estatus = next((c for c in ["estatus", "status", "pagado"] if c in df_cxc_local.columns), None)
    mask_pagado    = df_cxc_local[col_estatus].astype(str).str.strip().str.lower().str.contains("pagado") if col_estatus else pd.Series(False, index=df_cxc_local.index)
    mask_no_pagado = ~mask_pagado
    # Guardar máscaras antes de reasignar df_cxc (evitar dependencia de índice posterior)
    _mask_no_pagado_idx = mask_no_pagado.values

    if "saldo_adeudado" not in df_cxc_local.columns:
        for candidato in ["saldo_usd", "saldo", "adeudo", "importe", "monto", "total"]:
            if candidato in df_cxc_local.columns:
                df_cxc_local = df_cxc_local.rename(columns={candidato: "saldo_adeudado"})
                break
    saldo_txt = df_cxc_local.get("saldo_adeudado", pd.Series(0, index=df_cxc_local.index)).astype(str)
    saldo_txt = saldo_txt.str.replace(",", "", regex=False).str.replace("$", "", regex=False)
    df_cxc_local["saldo_adeudado"] = pd.to_numeric(saldo_txt, errors="coerce").fillna(0)
    total_adeudado = df_cxc_local.loc[mask_no_pagado, "saldo_adeudado"].sum()

    # Días vencidos
    col_dias = None
    if "dias_vencido" in df_cxc_local.columns:
        dias_overdue = pd.to_numeric(df_cxc_local["dias_vencido"].astype(str).str.replace(",", "", regex=False), errors="coerce").fillna(0)
    elif "dias_restante" in df_cxc_local.columns:
        dias_overdue = -pd.to_numeric(df_cxc_local["dias_restante"].astype(str).str.replace(",", "", regex=False), errors="coerce").fillna(0)
    else:
        col_venc = next((c for c in ["vencimient", "vencimiento", "fecha_vencimiento"] if c in df_cxc_local.columns), None)
        if col_venc:
            venc = pd.to_datetime(df_cxc_local[col_venc], errors="coerce")
        else:
            col_fp = next((c for c in ["fecha_de_pago", "fecha_pago", "fecha_tentativa_de_pag"] if c in df_cxc_local.columns), None)
            col_cr = next((c for c in ["dias_de_credito", "dias_de_credit", "dias_credito"] if c in df_cxc_local.columns), None)
            fecha_base = pd.to_datetime(df_cxc_local[col_fp], errors="coerce") if col_fp else pd.NaT
            dias_credito = pd.to_numeric(df_cxc_local[col_cr].astype(str).str.replace(",", "", regex=False), errors="coerce").fillna(0).astype(int) if col_cr else pd.Series(0, index=df_cxc_local.index)
            venc = fecha_base + pd.to_timedelta(dias_credito, unit="D")
        dias_overdue = (pd.Timestamp.today().normalize() - venc).apply(lambda x: x.days if pd.notna(x) else 0)
        dias_overdue = pd.to_numeric(dias_overdue, errors="coerce").fillna(0)

    df_cxc_local["dias_overdue"] = days_ov = pd.to_numeric(dias_overdue, errors="coerce").fillna(0)
    col_dias = "dias_overdue"
    df_cxc = df_cxc_local
    # Recalcular máscara sobre el df ya enriquecido con dias_overdue
    mask_no_pagado = pd.Series(_mask_no_pagado_idx, index=df_cxc.index)

    vigente      = df_cxc.loc[mask_no_pagado & (days_ov <= 0), "saldo_adeudado"].sum()
    vencida_0_30 = df_cxc.loc[mask_no_pagado & (days_ov > 0)  & (days_ov <= 30),  "saldo_adeudado"].sum()
    vencida_31_60= df_cxc.loc[mask_no_pagado & (days_ov > 30) & (days_ov <= 60),  "saldo_adeudado"].sum()
    vencida_61_90= df_cxc.loc[mask_no_pagado & (days_ov > 60) & (days_ov <= 90),  "saldo_adeudado"].sum()
    critica      = df_cxc.loc[mask_no_pagado & (days_ov > 30), "saldo_adeudado"].sum()
    alto_riesgo  = df_cxc.loc[mask_no_pagado & (days_ov > 90), "saldo_adeudado"].sum()

    pct_vigente        = (vigente      / total_adeudado * 100) if total_adeudado else 100
    pct_vencida_0_30   = (vencida_0_30 / total_adeudado * 100) if total_adeudado else 0
    pct_critica        = (critica      / total_adeudado * 100) if total_adeudado else 0
    pct_vencida_total  = pct_vencida_0_30 + pct_critica
    pct_vencida        = pct_vencida_total
    pct_alto_riesgo    = (alto_riesgo  / total_adeudado * 100) if total_adeudado else 0
    # DSO estándar: (Cartera / Ventas_anualizadas) × 365
    # Usa ventas de los últimos 12 meses para anualizar; si hay menos historial usa lo disponible
    if total_adeudado > 0 and total_ventas > 0 and "fecha" in df_v.columns and not df_v.empty:
        _hoy_dso = pd.Timestamp.today().normalize()
        _hace_12m = _hoy_dso - pd.DateOffset(months=12)
        _col_v = next((c for c in ["valor_usd", "ventas_usd", "ventas", "total"] if c in df_v.columns), None)
        if _col_v:
            _ventas_12m = df_v.loc[df_v["fecha"] >= _hace_12m, _col_v].sum()
            _ventas_base = _ventas_12m if _ventas_12m > 0 else total_ventas
        else:
            _ventas_base = total_ventas
        dso = round((total_adeudado / _ventas_base) * 365)
    elif total_ventas > 0:
        dso = round((total_adeudado / total_ventas) * 365)
    else:
        dso = 0
    eficiencia_ops     = (total_ventas / total_adeudado) if total_adeudado else 0

    score_salud_cxc = calcular_score_salud(
        pct_vigente, pct_critica,
        pct_vencida_0_30, 0, 0, pct_alto_riesgo
    )
    # Columna cliente normalizada (compartida entre tabs)
    _col_cliente_cxc = next((c for c in ["cliente", "receptor_nombre", "razon_social"] if c in df_cxc.columns), None)
    _col_cliente_v   = next((c for c in ["cliente", "receptor_nombre", "razon_social"] if c in df_v.columns), None)

    # ═════════════════════════════════════════════════════════════════════
    # TAB 1 — GENERAL
    # ═════════════════════════════════════════════════════════════════════
    with tab_general:
        st.subheader("📋 Resumen del Período")

        # KPIs en fila de 4
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("💵 Total Ventas", formato_moneda(total_ventas),
                  delta=f"{variacion_ventas:+.1f}% vs {mes_anterior_nombre}" if mes_anterior_nombre else None)
        k2.metric("🛍️ Operaciones", f"{total_ops:,}")
        k3.metric("🎯 Ticket Promedio", formato_moneda(ticket_promedio))
        k4.metric("👥 Clientes Activos", f"{clientes_unicos:,}")

        st.markdown("---")

        # Segunda fila: CxC resumen + score salud + liquidez
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("💰 Cartera Total", formato_moneda(total_adeudado))
        c2.metric("✅ Vigente", formato_moneda(vigente), delta=f"{pct_vigente:.1f}%")
        c3.metric("⚠️ 0-30d", formato_moneda(vencida_0_30), delta=f"{pct_vencida_0_30:.1f}%", delta_color="inverse")
        c4.metric("🔴 Crítica >30d", formato_moneda(critica), delta=f"{pct_critica:.1f}%", delta_color="inverse")
        score_emoji = "🟢" if score_salud_cxc >= 80 else "🟡" if score_salud_cxc >= 60 else "🔴"
        c5.metric(f"{score_emoji} Salud CxC", f"{score_salud_cxc:.0f}/100")
        dso_delta = "🟢 saludable" if dso <= 30 else "🟡 atención" if dso <= 60 else "🔴 alto"
        c6.metric("📆 DSO (días cobro)", f"{dso:.0f} días",
                  delta=dso_delta,
                  delta_color="off",
                  help="Days Sales Outstanding: cuántos días tarda en promedio en cobrarse la cartera. <30d=saludable, 30-60d=atención, >60d=riesgo")

        st.markdown("---")
        st.subheader("🚨 Alertas")

        alertas = []
        if pct_vencida_total > 30:
            alertas.append(("🔴 CRÍTICO", f"Morosidad elevada: {pct_vencida_total:.1f}% de la cartera vencida", "Acelerar cobranza y revisar políticas de crédito"))
        elif pct_vencida_total > 20:
            alertas.append(("🟠 ALERTA",  f"Morosidad en aumento: {pct_vencida_total:.1f}%", "Ejecutar plan de cobranza preventivo"))
        if pct_alto_riesgo > 15:
            alertas.append(("🔴 CRÍTICO", f"Alto riesgo de incobrabilidad: {formato_moneda(alto_riesgo)} (>{pct_alto_riesgo:.1f}%)", "Evaluar provisión e iniciar acciones legales"))
        if variacion_ventas < -10:
            alertas.append(("🟠 ALERTA",  f"Caída en ventas: {variacion_ventas:.1f}% vs mes anterior", "Revisar estrategia comercial"))
        if _col_cliente_cxc and total_adeudado > 0:
            top_deudor_pct = (df_cxc.groupby(_col_cliente_cxc)["saldo_adeudado"].sum().max() / total_adeudado * 100)
            if top_deudor_pct > 30:
                alertas.append(("🟡 PRECAUCIÓN", f"Concentración de cartera: un cliente representa {top_deudor_pct:.1f}%", "Diversificar cartera"))

        if alertas:
            for nivel, msg, accion in alertas:
                with st.expander(f"{nivel} — {msg}", expanded=("CRÍTICO" in nivel)):
                    st.write(f"**Acción recomendada:** {accion}")
        else:
            st.success("✅ Sin alertas críticas. Todos los indicadores en parámetros normales.")

        st.markdown("---")
        st.subheader("💡 Insights Estratégicos")
        insights_list = []
        if variacion_ventas > 0:
            insights_list.append(f"📈 **Crecimiento positivo:** ventas aumentaron {variacion_ventas:.1f}% vs mes anterior.")
        elif variacion_ventas < 0:
            insights_list.append(f"📉 **Atención:** ventas cayeron {abs(variacion_ventas):.1f}%. Revisar estrategia comercial.")
        if pct_vigente > 80:
            insights_list.append(f"✅ **Cartera saludable:** {pct_vigente:.1f}% vigente. Buena gestión de cobranza.")
        elif pct_vigente < 60:
            insights_list.append(f"⚠️ **Cartera en riesgo:** solo {pct_vigente:.1f}% vigente. Plan de recuperación urgente.")
        if eficiencia_ops > 2:
            insights_list.append(f"🎯 **Alta eficiencia:** Ventas/Cartera {eficiencia_ops:.2f}x.")
        elif eficiencia_ops < 1:
            insights_list.append(f"⚠️ **Baja conversión:** ratio {eficiencia_ops:.2f}x. Acelerar ciclo de cobro.")
        for i, ins in enumerate(insights_list, 1):
            st.markdown(f"{i}. {ins}")

        st.markdown("---")
        # IA premium
        if habilitar_ia and openai_api_key:
            st.subheader("🤖 Análisis Ejecutivo con IA")
            col_f1, col_f2 = st.columns(2)
            tipo_receptor = col_f1.selectbox("👤 Análisis dirigido a", ["CEO", "CFO", "Director Comercial", "Gerente de Cobranza"])
            if col_f2.button("🚀 Generar diagnóstico con IA", type="primary", use_container_width=True):
                with st.spinner("🔄 Generando diagnóstico integral..."):
                    try:
                        top_linea_ventas = df_v.groupby("linea_de_negocio")["valor_usd"].sum().idxmax() if "linea_de_negocio" in df_v.columns and not df_v.empty else "N/A"
                        casos_urgentes   = int(df_cxc[df_cxc["dias_overdue"] > 90].shape[0]) if "dias_overdue" in df_cxc.columns else 0
                        insights = generar_insights_ejecutivo_consolidado(
                            total_ventas_periodo=total_ventas,
                            crecimiento_ventas_pct=variacion_ventas,
                            score_salud_cxc=score_salud_cxc,
                            pct_morosidad=pct_vencida_total,
                            top_linea_ventas=top_linea_ventas,
                            top_linea_cxc_critica="N/A",
                            casos_urgentes_cxc=casos_urgentes,
                            api_key=openai_api_key,
                        )
                        if insights:
                            st.markdown(f"### 🔍 Diagnóstico — {tipo_receptor}")
                            st.info(insights.get("diagnostico_integral", "No disponible"))
                            col_izq, col_der = st.columns(2)
                            with col_izq:
                                st.markdown("**🚨 Riesgos Ocultos**")
                                for r in insights.get("riesgos_ocultos", []):
                                    st.markdown(f"- {r}")
                                st.markdown("**🔮 Escenario Proyectado**")
                                st.markdown(f"_{insights.get('escenario_proyectado','N/A')}_")
                            with col_der:
                                st.markdown("**📋 Decisiones Críticas**")
                                for d in insights.get("decisiones_criticas", []):
                                    st.markdown(f"- {d}")
                    except Exception as e:
                        st.error(f"❌ Error en análisis IA: {e}")

    # ═════════════════════════════════════════════════════════════════════
    # TAB 2 — COMERCIAL
    # ═════════════════════════════════════════════════════════════════════
    with tab_comercial:
        st.subheader("📈 Desempeño Comercial")

        # Banner de período activo
        if fecha_min_datos and fecha_max_datos:
            st.info(
                f"📅 Mostrando datos del período: **{periodo_sel}** "
                f"({fecha_min_datos.strftime('%d/%m/%Y')} → {fecha_max_datos.strftime('%d/%m/%Y')}) "
                f"· **{len(df_v):,}** registros · "
                f"Cambia el período en el selector de arriba ↑"
            )
        else:
            st.warning("⚠️ Sin columna 'fecha' — mostrando todos los registros sin filtro de período.")

        # Tendencia de ventas
        if "fecha" in df_v.columns and not df_v.empty:
            df_v_tmp = df_v.copy()
            df_v_tmp["mes"] = df_v_tmp["fecha"].dt.to_period("M").astype(str)
            ventas_mes = df_v_tmp.groupby("mes").agg(Ventas=("valor_usd", "sum"), Ops=("valor_usd", "count")).reset_index()

            fig_ventas = go.Figure()
            fig_ventas.add_trace(go.Bar(
                x=ventas_mes["mes"], y=ventas_mes["Ventas"],
                name="Ventas", marker_color="#1F4E79",
                hovertemplate="<b>%{x}</b><br>Ventas: $%{y:,.0f}<extra></extra>",
            ))
            fig_ventas.update_layout(
                title="Evolución de Ventas por Mes",
                xaxis_title="Mes", yaxis_title="Ventas (MXN/USD)",
                height=380, showlegend=False,
            )
            st.plotly_chart(fig_ventas, use_container_width=True)
        else:
            st.info("📊 Se requiere columna 'fecha' para mostrar tendencias.")

        st.markdown("---")
        col_top, col_cli = st.columns(2)

        with col_top:
            st.markdown("#### 🌟 Top 5 Vendedores")
            col_vendedor = next((c for c in ["agente", "vendedor"] if c in df_v.columns), None)
            if col_vendedor:
                top_vend = df_v.groupby(col_vendedor).agg(Ventas=("valor_usd", "sum"), Ops=("valor_usd", "count")).reset_index()
                top_vend.columns = ["Vendedor", "Ventas", "Ops"]
                top_vend["Ticket"] = top_vend["Ventas"] / top_vend["Ops"]
                top_vend = top_vend.sort_values("Ventas", ascending=False).head(5)
                top_vend_d = top_vend.copy()
                top_vend_d["Ventas"] = top_vend_d["Ventas"].apply(formato_moneda)
                top_vend_d["Ticket"] = top_vend_d["Ticket"].apply(formato_moneda)
                top_vend_d.insert(0, "🏅", ["🥇","🥈","🥉","④","⑤"][:len(top_vend_d)])
                st.dataframe(top_vend_d, use_container_width=True, hide_index=True)
            else:
                st.info("Sin columna de vendedor disponible.")

        with col_cli:
            st.markdown("#### 👥 Top 5 Clientes por Venta")
            if _col_cliente_v:
                top_cli = df_v.groupby(_col_cliente_v).agg(Ventas=("valor_usd", "sum"), Ops=("valor_usd", "count")).reset_index()
                top_cli.columns = ["Cliente", "Ventas", "Ops"]
                top_cli = top_cli.sort_values("Ventas", ascending=False).head(5)
                top_cli_d = top_cli.copy()
                top_cli_d["Ventas"] = top_cli_d["Ventas"].apply(formato_moneda)
                top_cli_d.insert(0, "🏅", ["🥇","🥈","🥉","④","⑤"][:len(top_cli_d)])
                st.dataframe(top_cli_d, use_container_width=True, hide_index=True)
            else:
                st.info("Sin columna de cliente disponible.")

        # Acciones comerciales
        st.markdown("---")
        st.markdown("#### 🎯 Próximas Acciones Comerciales")
        a1, a2, a3 = st.columns(3)
        with a1:
            st.markdown("**📞 Cobranza**")
            if pct_alto_riesgo > 10:
                st.markdown("- Contactar clientes >90 días\n- Iniciar proceso legal si aplica")
            else:
                st.markdown("- Seguimiento preventivo\n- Mantener políticas actuales")
        with a2:
            st.markdown("**💼 Ventas**")
            if variacion_ventas < 0:
                st.markdown("- Revisar pipeline de ventas\n- Capacitar equipo comercial")
            else:
                st.markdown("- Escalar estrategias exitosas\n- Ampliar líneas productivas")
        with a3:
            st.markdown("**📊 Gestión**")
            st.markdown("- Revisar políticas de crédito\n- Monitorear KPIs semanalmente")

    # ═════════════════════════════════════════════════════════════════════
    # TAB 3 — CUENTAS POR COBRAR
    # ═════════════════════════════════════════════════════════════════════
    with tab_cxc:
        st.subheader("🏦 Cuentas por Cobrar")

        if fecha_min_datos and fecha_max_datos:
            st.info(
                f"📅 Ventas del período: **{periodo_sel}** "
                f"({fecha_min_datos.strftime('%d/%m/%Y')} → {fecha_max_datos.strftime('%d/%m/%Y')}) "
                f"· CxC: todos los saldos pendientes (sin filtro de fecha)"
            )
        # KPIs CxC — fila 1
        cx1, cx2, cx3, cx4, cx5 = st.columns(5)
        cx1.metric("💰 Cartera Total",  formato_moneda(total_adeudado))
        cx2.metric("✅ Vigente",        formato_moneda(vigente),      delta=f"{pct_vigente:.1f}%")
        cx3.metric("⚠️ 0-30 días",     formato_moneda(vencida_0_30),  delta=f"{pct_vencida_0_30:.1f}%", delta_color="inverse")
        cx4.metric("🔴 Crítica >30d",  formato_moneda(critica),       delta=f"{pct_critica:.1f}%", delta_color="inverse")
        score_emoji_cxc = "🟢" if score_salud_cxc >= 80 else "🟡" if score_salud_cxc >= 60 else "🔴"
        cx5.metric(f"{score_emoji_cxc} Score Salud", f"{score_salud_cxc:.0f}/100",
                   help="0=crítico · 60=aceptable · 80=saludable · 100=excelente")

        st.markdown("---")

        # ── FILA 1: Gauge score salud + Plan de cobro por segmento ────────
        col_gauge, col_plan = st.columns([1, 2])

        with col_gauge:
            st.markdown("#### 🎯 Score de Salud")
            color_gauge = "#2ecc71" if score_salud_cxc >= 80 else "#f39c12" if score_salud_cxc >= 60 else "#e74c3c"
            fig_gauge = go.Figure(go.Indicator(
                mode="gauge+number",
                value=score_salud_cxc,
                number={"suffix": "/100", "font": {"size": 28}},
                gauge={
                    "axis": {"range": [0, 100], "tickwidth": 1},
                    "bar": {"color": color_gauge},
                    "steps": [
                        {"range": [0,  60], "color": "#fadbd8"},
                        {"range": [60, 80], "color": "#fdebd0"},
                        {"range": [80, 100], "color": "#d5f5e3"},
                    ],
                    "threshold": {"line": {"color": "white", "width": 3}, "value": score_salud_cxc},
                },
            ))
            fig_gauge.update_layout(height=220, margin=dict(t=20, b=10, l=20, r=20))
            st.plotly_chart(fig_gauge, use_container_width=True)

        with col_plan:
            st.markdown("#### 📆 Plan de Cobro por Segmento")
            cobrable_semana = vigente * 0.3   # estimado conservador
            cobrable_mes    = vencida_0_30
            con_gestion     = max(0, float(critica) - float(alto_riesgo))
            provisionable   = alto_riesgo
            plan_df = pd.DataFrame({
                "Horizonte":  ["Esta semana", "Este mes", "Con gestión (30-90d)", "Provisionable (>90d)"],
                "Monto":      [cobrable_semana, cobrable_mes, con_gestion, provisionable],
                "Acción":     ["Cobro rutinario", "Seguimiento activo", "Negociación / acuerdo", "Evaluar provisión"],
                "Semáforo":   ["🟢", "🟡", "🟠", "🔴"],
            })
            plan_df["% Cartera"] = (plan_df["Monto"] / total_adeudado * 100).round(1) if total_adeudado else 0
            plan_df_d = plan_df.copy()
            plan_df_d["Monto"]     = plan_df_d["Monto"].apply(formato_moneda)
            plan_df_d["% Cartera"] = plan_df_d["% Cartera"].apply(lambda x: f"{x}%")
            st.dataframe(plan_df_d[["Semáforo", "Horizonte", "Monto", "% Cartera", "Acción"]],
                         use_container_width=True, hide_index=True)

        st.markdown("---")

        # ── FILA 2: Pie antigüedad + Concentración de riesgo ──────────────
        col_pie, col_conc = st.columns(2)

        with col_pie:
            st.markdown("#### 🥧 Composición por Antigüedad")
            vencida_31_90_val = max(0, float(critica) - float(alto_riesgo))
            cartera_df = pd.DataFrame({
                "Categoría": ["Vigente", "1-30 días", "31-90 días", ">90 días"],
                "Monto":     [float(vigente), float(vencida_0_30), vencida_31_90_val, float(alto_riesgo)],
            })
            cartera_df = cartera_df[cartera_df["Monto"] > 0]
            if not cartera_df.empty:
                fig_pie = go.Figure(data=[go.Pie(
                    labels=cartera_df["Categoría"],
                    values=cartera_df["Monto"],
                    marker=dict(colors=["#2ecc71", "#3498db", "#f39c12", "#e74c3c"]),
                    textinfo="label+percent",
                    hovertemplate="<b>%{label}</b><br>$%{value:,.0f}<br>%{percent}<extra></extra>",
                )])
                fig_pie.update_layout(height=300, margin=dict(t=10, b=10))
                st.plotly_chart(fig_pie, use_container_width=True)
            else:
                st.info("Sin saldo pendiente para mostrar.")

        with col_conc:
            st.markdown("#### ⚠️ Concentración de Riesgo")
            if _col_cliente_cxc and total_adeudado > 0:
                conc = df_cxc.groupby(_col_cliente_cxc)["saldo_adeudado"].sum().sort_values(ascending=False)
                top3_pct  = conc.head(3).sum()  / total_adeudado * 100
                top1_pct  = conc.head(1).sum()  / total_adeudado * 100
                top10_pct = conc.head(10).sum() / total_adeudado * 100
                r1, r2, r3 = st.columns(3)
                r1.metric("Top 1 cliente",  f"{top1_pct:.1f}%",
                          delta="⚠️ alto" if top1_pct > 30 else "✅ ok", delta_color="off")
                r2.metric("Top 3 clientes", f"{top3_pct:.1f}%",
                          delta="⚠️ alto" if top3_pct > 50 else "✅ ok", delta_color="off")
                r3.metric("Top 10 clientes", f"{top10_pct:.1f}%")

                fig_conc = px.bar(
                    x=conc.head(10).values,
                    y=conc.head(10).index,
                    orientation="h",
                    color=conc.head(10).values,
                    color_continuous_scale="Reds",
                    labels={"x": "Saldo ($)", "y": ""},
                )
                fig_conc.update_layout(height=220, showlegend=False,
                                       coloraxis_showscale=False, margin=dict(t=5, b=5))
                st.plotly_chart(fig_conc, use_container_width=True)
            else:
                st.info("Sin datos de cliente para calcular concentración.")

        st.markdown("---")

        # ── FILA 3: Urgentes + Por vendedor ───────────────────────────────
        col_urg, col_vend = st.columns(2)

        with col_urg:
            st.markdown("#### 🚨 Cobro Urgente (>60 días)")
            if _col_cliente_cxc:
                df_urgentes = df_cxc[mask_no_pagado & (days_ov > 60)].copy()
                if not df_urgentes.empty:
                    urg = df_urgentes.groupby(_col_cliente_cxc).agg(
                        Adeudo=("saldo_adeudado", "sum"),
                        Días=("dias_overdue", "max"),
                    ).reset_index()
                    urg.columns = ["Cliente", "Adeudo", "Días"]
                    urg = urg.sort_values("Adeudo", ascending=False)
                    urg["Nivel"] = urg["Días"].apply(lambda x: "🔴 >90d" if x > 90 else "🟠 60-90d")
                    urg_d = urg.copy()
                    urg_d["Adeudo"] = urg_d["Adeudo"].apply(formato_moneda)
                    urg_d["Días"]   = urg_d["Días"].apply(lambda x: f"{x:.0f}")
                    st.dataframe(urg_d, use_container_width=True, hide_index=True)
                    st.caption(f"Total en riesgo: **{formato_moneda(df_urgentes['saldo_adeudado'].sum())}**")
                else:
                    st.success("✅ Sin facturas con más de 60 días vencidas.")
            else:
                st.info("Sin columna de cliente disponible.")

        with col_vend:
            st.markdown("#### 👤 Cartera Vencida por Vendedor")
            col_vend_cxc = next((c for c in ["vendedor", "agente"] if c in df_cxc.columns), None)
            if col_vend_cxc:
                df_venc_vend = df_cxc[mask_no_pagado & (days_ov > 0)].groupby(col_vend_cxc).agg(
                    Vencido=("saldo_adeudado", "sum"),
                    Clientes=(_col_cliente_cxc, "nunique") if _col_cliente_cxc else ("saldo_adeudado", "count"),
                ).reset_index()
                df_venc_vend.columns = ["Vendedor", "Vencido", "Clientes"]
                df_venc_vend["% Total"] = (df_venc_vend["Vencido"] / critica * 100).round(1) if critica else 0
                df_venc_vend = df_venc_vend.sort_values("Vencido", ascending=False)
                df_venc_vend_d = df_venc_vend.copy()
                df_venc_vend_d["Vencido"]  = df_venc_vend_d["Vencido"].apply(formato_moneda)
                df_venc_vend_d["% Total"]  = df_venc_vend_d["% Total"].apply(lambda x: f"{x}%")
                st.dataframe(df_venc_vend_d, use_container_width=True, hide_index=True)
            else:
                st.info("Sin columna de vendedor/agente en los datos de CxC.")

    st.markdown("---")
    st.caption(f"📅 Reporte generado: {now_mx().strftime('%d/%m/%Y %H:%M')}")
