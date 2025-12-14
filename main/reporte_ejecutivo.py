"""
Módulo de Reporte Ejecutivo para el Dashboard Fradma.
Vista consolidada con KPIs críticos para dirección ejecutiva (CEO/CFO).
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
from utils.formatos import formato_moneda, formato_porcentaje, formato_compacto


def mostrar_reporte_ejecutivo(df_ventas, df_cxc):
    """
    Muestra el reporte ejecutivo consolidado con métricas clave de negocio.
    
    Args:
        df_ventas: DataFrame con datos de ventas
        df_cxc: DataFrame con datos de cuentas por cobrar
    """
    
    st.title("📊 Reporte Ejecutivo")
    st.markdown("### Vista Consolidada del Negocio - Dashboard para Dirección")
    
    # =====================================================================
    # SECCIÓN 1: RESUMEN FINANCIERO (2 columnas grandes)
    # =====================================================================
    
    st.markdown("---")
    st.subheader("💰 Resumen Financiero")
    
    col_ventas, col_cxc = st.columns(2)
    
    with col_ventas:
        st.markdown("#### 📈 Ventas")
        # Calcular métricas de ventas
        total_ventas = df_ventas["valor_usd"].sum() if "valor_usd" in df_ventas.columns else 0
        total_ops = len(df_ventas) if not df_ventas.empty else 0
        ticket_promedio = total_ventas / total_ops if total_ops > 0 else 0
        
        # Ventas del mes actual vs mes anterior (si hay columna fecha)
        if "fecha" in df_ventas.columns:
            df_ventas["fecha"] = pd.to_datetime(df_ventas["fecha"], errors="coerce")
            mes_actual = df_ventas["fecha"].max().replace(day=1) if not df_ventas.empty else datetime.now().replace(day=1)
            mes_anterior = (mes_actual - timedelta(days=1)).replace(day=1)
            
            ventas_mes_actual = df_ventas[df_ventas["fecha"] >= mes_actual]["valor_usd"].sum()
            ventas_mes_anterior = df_ventas[
                (df_ventas["fecha"] >= mes_anterior) & (df_ventas["fecha"] < mes_actual)
            ]["valor_usd"].sum()
            
            variacion_ventas = ((ventas_mes_actual - ventas_mes_anterior) / ventas_mes_anterior * 100) if ventas_mes_anterior > 0 else 0
        else:
            ventas_mes_actual = total_ventas
            variacion_ventas = 0
        
        st.metric("💵 Total Ventas", formato_moneda(total_ventas), 
                 delta=f"{variacion_ventas:+.1f}% vs mes anterior" if "fecha" in df_ventas.columns else None)
        
        col_v1, col_v2 = st.columns(2)
        col_v1.metric("🛒 Operaciones", f"{total_ops:,}")
        col_v2.metric("🎯 Ticket Promedio", formato_moneda(ticket_promedio))
    
    with col_cxc:
        st.markdown("#### 🏦 Cuentas por Cobrar")
        # Calcular métricas de CxC
        total_adeudado = df_cxc["saldo_adeudado"].sum() if "saldo_adeudado" in df_cxc.columns else 0
        
        # Determinar columnas de días
        col_dias = None
        for col in ["dias_vencido", "dias_transcurridos", "dias"]:
            if col in df_cxc.columns:
                col_dias = col
                break
        
        if col_dias:
            vigente = df_cxc[df_cxc[col_dias] <= 0]["saldo_adeudado"].sum()
            vencida = df_cxc[df_cxc[col_dias] > 0]["saldo_adeudado"].sum()
            alto_riesgo = df_cxc[df_cxc[col_dias] > 90]["saldo_adeudado"].sum()
        else:
            vigente = total_adeudado * 0.7  # Estimación conservadora
            vencida = total_adeudado * 0.3
            alto_riesgo = total_adeudado * 0.1
        
        pct_vigente = (vigente / total_adeudado * 100) if total_adeudado > 0 else 100
        pct_vencida = (vencida / total_adeudado * 100) if total_adeudado > 0 else 0
        pct_alto_riesgo = (alto_riesgo / total_adeudado * 100) if total_adeudado > 0 else 0
        
        st.metric("💰 Cartera Total", formato_moneda(total_adeudado),
                 delta=f"{pct_vigente:.1f}% Vigente")
        
        col_c1, col_c2 = st.columns(2)
        col_c1.metric("⚠️ Vencida", formato_moneda(vencida),
                     delta=f"{pct_vencida:.1f}%",
                     delta_color="inverse")
        col_c2.metric("🔴 Alto Riesgo (>90d)", formato_moneda(alto_riesgo),
                     delta=f"{pct_alto_riesgo:.1f}%",
                     delta_color="inverse")
    
    # =====================================================================
    # SECCIÓN 2: INDICADORES CLAVE (4 columnas)
    # =====================================================================
    
    st.markdown("---")
    st.subheader("🎯 Indicadores Clave de Desempeño (KPIs)")
    
    col1, col2, col3, col4 = st.columns(4)
    
    # KPI 1: Salud Financiera General (Score 0-100)
    score_ventas = min(100, (ventas_mes_actual / 1_000_000) * 50) if "fecha" in df_ventas.columns else 50
    score_cartera = pct_vigente * 0.7 + max(0, 100 - pct_vencida * 2) * 0.3
    score_general = (score_ventas + score_cartera) / 2
    
    color_score = "🟢" if score_general >= 80 else "🟡" if score_general >= 60 else "🟠" if score_general >= 40 else "🔴"
    col1.metric(f"{color_score} Salud Financiera", f"{score_general:.0f}/100")
    
    # KPI 2: Índice de Liquidez
    indice_liquidez = (vigente + ventas_mes_actual) / (vencida + 1) if vencida > 0 else 10
    color_liquidez = "🟢" if indice_liquidez >= 3 else "🟡" if indice_liquidez >= 1.5 else "🔴"
    col2.metric(f"{color_liquidez} Índice Liquidez", f"{indice_liquidez:.1f}x")
    
    # KPI 3: Eficiencia Operativa
    eficiencia_ops = (total_ventas / total_adeudado) if total_adeudado > 0 else 0
    color_eficiencia = "🟢" if eficiencia_ops >= 2 else "🟡" if eficiencia_ops >= 1 else "🔴"
    col3.metric(f"{color_eficiencia} Ventas/Cartera", f"{eficiencia_ops:.2f}x")
    
    # KPI 4: Clientes Únicos
    clientes_unicos = df_ventas["cliente"].nunique() if "cliente" in df_ventas.columns else 0
    col4.metric("👥 Clientes Activos", f"{clientes_unicos:,}")
    
    # =====================================================================
    # SECCIÓN 3: ALERTAS CRÍTICAS
    # =====================================================================
    
    st.markdown("---")
    st.subheader("🚨 Alertas Críticas")
    
    alertas = []
    
    # Alerta 1: Morosidad alta
    if pct_vencida > 30:
        alertas.append({
            "nivel": "🔴 CRÍTICO",
            "mensaje": f"Morosidad elevada: {pct_vencida:.1f}% de la cartera está vencida",
            "accion": "Revisar políticas de crédito y acelerar cobranza"
        })
    elif pct_vencida > 20:
        alertas.append({
            "nivel": "🟠 ALERTA",
            "mensaje": f"Morosidad en aumento: {pct_vencida:.1f}% vencida",
            "accion": "Monitorear clientes morosos y ejecutar plan de cobranza"
        })
    
    # Alerta 2: Alto riesgo
    if pct_alto_riesgo > 15:
        alertas.append({
            "nivel": "🔴 CRÍTICO",
            "mensaje": f"Alto riesgo de incobrabilidad: {formato_moneda(alto_riesgo)} (>{pct_alto_riesgo:.1f}%)",
            "accion": "Evaluar provisión de cartera vencida e iniciar acciones legales"
        })
    
    # Alerta 3: Caída de ventas
    if "fecha" in df_ventas.columns and variacion_ventas < -10:
        alertas.append({
            "nivel": "🟠 ALERTA",
            "mensaje": f"Caída en ventas: {variacion_ventas:.1f}% vs mes anterior",
            "accion": "Analizar causas y implementar estrategias de recuperación"
        })
    
    # Alerta 4: Concentración de cartera
    if "cliente" in df_cxc.columns:
        top_deudor = df_cxc.groupby("cliente")["saldo_adeudado"].sum().sort_values(ascending=False)
        if len(top_deudor) > 0:
            pct_top_deudor = (top_deudor.iloc[0] / total_adeudado * 100) if total_adeudado > 0 else 0
            if pct_top_deudor > 30:
                alertas.append({
                    "nivel": "🟡 PRECAUCIÓN",
                    "mensaje": f"Concentración de cartera: Un cliente representa {pct_top_deudor:.1f}% del total",
                    "accion": "Diversificar cartera y evaluar riesgo de concentración"
                })
    
    # Alerta 5: Ticket promedio bajo
    if ticket_promedio < 1000:
        alertas.append({
            "nivel": "🟡 PRECAUCIÓN",
            "mensaje": f"Ticket promedio bajo: {formato_moneda(ticket_promedio)}",
            "accion": "Implementar estrategias de up-selling y cross-selling"
        })
    
    if alertas:
        for alerta in alertas:
            with st.expander(f"{alerta['nivel']} - {alerta['mensaje']}", expanded=(alerta['nivel'] == "🔴 CRÍTICO")):
                st.write(f"**Acción recomendada:** {alerta['accion']}")
    else:
        st.success("✅ No hay alertas críticas. Todos los indicadores están dentro de parámetros normales.")
    
    # =====================================================================
    # SECCIÓN 4: GRÁFICOS DE TENDENCIAS (2 columnas)
    # =====================================================================
    
    st.markdown("---")
    st.subheader("📊 Tendencias y Análisis")
    
    col_graf1, col_graf2 = st.columns(2)
    
    with col_graf1:
        st.markdown("#### Evolución de Ventas")
        
        if "fecha" in df_ventas.columns and not df_ventas.empty:
            # Agrupar ventas por mes
            df_ventas_temp = df_ventas.copy()
            df_ventas_temp["mes"] = df_ventas_temp["fecha"].dt.to_period("M").astype(str)
            ventas_por_mes = df_ventas_temp.groupby("mes").agg({
                "valor_usd": "sum",
                "fecha": "count"
            }).reset_index()
            ventas_por_mes.columns = ["Mes", "Ventas", "Operaciones"]
            
            # Crear gráfico de líneas
            fig_ventas = go.Figure()
            fig_ventas.add_trace(go.Scatter(
                x=ventas_por_mes["Mes"],
                y=ventas_por_mes["Ventas"],
                mode="lines+markers",
                name="Ventas USD",
                line=dict(color="#1f77b4", width=3),
                marker=dict(size=8),
                hovertemplate="<b>%{x}</b><br>Ventas: $%{y:,.2f}<extra></extra>"
            ))
            
            fig_ventas.update_layout(
                title="Ventas Mensuales (USD)",
                xaxis_title="Mes",
                yaxis_title="Ventas (USD)",
                height=350,
                hovermode="x unified",
                showlegend=False
            )
            
            st.plotly_chart(fig_ventas, use_container_width=True)
        else:
            st.info("📊 Se requiere columna 'fecha' para mostrar tendencias de ventas")
    
    with col_graf2:
        st.markdown("#### Composición de Cartera CxC")
        
        if col_dias:
            # Crear categorías de antigüedad
            df_cxc_temp = df_cxc.copy()
            
            def categorizar_antiguedad(dias):
                if dias <= 0:
                    return "Vigente"
                elif dias <= 30:
                    return "1-30 días"
                elif dias <= 60:
                    return "31-60 días"
                elif dias <= 90:
                    return "61-90 días"
                else:
                    return ">90 días (Crítico)"
            
            df_cxc_temp["categoria"] = df_cxc_temp[col_dias].apply(categorizar_antiguedad)
            
            cartera_por_categoria = df_cxc_temp.groupby("categoria")["saldo_adeudado"].sum().reset_index()
            cartera_por_categoria.columns = ["Categoría", "Monto"]
            
            # Ordenar categorías
            orden = ["Vigente", "1-30 días", "31-60 días", "61-90 días", ">90 días (Crítico)"]
            cartera_por_categoria["orden"] = cartera_por_categoria["Categoría"].apply(
                lambda x: orden.index(x) if x in orden else 99
            )
            cartera_por_categoria = cartera_por_categoria.sort_values("orden")
            
            # Colores por categoría
            colores = {
                "Vigente": "#2ecc71",
                "1-30 días": "#3498db",
                "31-60 días": "#f39c12",
                "61-90 días": "#e67e22",
                ">90 días (Crítico)": "#e74c3c"
            }
            
            fig_cartera = go.Figure(data=[
                go.Pie(
                    labels=cartera_por_categoria["Categoría"],
                    values=cartera_por_categoria["Monto"],
                    marker=dict(colors=[colores.get(cat, "#95a5a6") for cat in cartera_por_categoria["Categoría"]]),
                    textinfo="label+percent",
                    hovertemplate="<b>%{label}</b><br>Monto: $%{value:,.2f}<br>%{percent}<extra></extra>"
                )
            ])
            
            fig_cartera.update_layout(
                title="Distribución de Cartera por Antigüedad",
                height=350
            )
            
            st.plotly_chart(fig_cartera, use_container_width=True)
        else:
            # Gráfico simple vigente vs vencido
            fig_simple = go.Figure(data=[
                go.Pie(
                    labels=["Vigente", "Vencida"],
                    values=[vigente, vencida],
                    marker=dict(colors=["#2ecc71", "#e74c3c"]),
                    textinfo="label+percent",
                    hovertemplate="<b>%{label}</b><br>Monto: $%{value:,.2f}<br>%{percent}<extra></extra>"
                )
            ])
            
            fig_simple.update_layout(
                title="Cartera Vigente vs Vencida",
                height=350
            )
            
            st.plotly_chart(fig_simple, use_container_width=True)
    
    # =====================================================================
    # SECCIÓN 5: TOP PERFORMERS Y BOTTOM PERFORMERS
    # =====================================================================
    
    st.markdown("---")
    st.subheader("🏆 Top Performers y 📉 Áreas de Mejora")
    
    col_top, col_bottom = st.columns(2)
    
    with col_top:
        st.markdown("#### 🌟 Top 5 Vendedores")
        
        if "agente" in df_ventas.columns or "vendedor" in df_ventas.columns:
            col_vendedor = "agente" if "agente" in df_ventas.columns else "vendedor"
            
            top_vendedores = df_ventas.groupby(col_vendedor).agg({
                "valor_usd": ["sum", "count"]
            }).reset_index()
            top_vendedores.columns = ["Vendedor", "Ventas", "Ops"]
            top_vendedores["Ticket"] = top_vendedores["Ventas"] / top_vendedores["Ops"]
            top_vendedores = top_vendedores.sort_values("Ventas", ascending=False).head(5)
            
            # Formatear tabla
            top_vendedores_display = top_vendedores.copy()
            top_vendedores_display["Ventas"] = top_vendedores_display["Ventas"].apply(lambda x: formato_moneda(x))
            top_vendedores_display["Ticket"] = top_vendedores_display["Ticket"].apply(lambda x: formato_moneda(x))
            top_vendedores_display.insert(0, "🏅", ["🥇", "🥈", "🥉", "④", "⑤"])
            
            st.dataframe(top_vendedores_display, use_container_width=True, hide_index=True)
        else:
            st.info("No hay información de vendedores disponible")
    
    with col_bottom:
        st.markdown("#### ⚠️ Top 5 Deudores")
        
        if "cliente" in df_cxc.columns:
            top_deudores = df_cxc.groupby("cliente").agg({
                "saldo_adeudado": "sum"
            }).reset_index()
            top_deudores.columns = ["Cliente", "Adeudo"]
            
            if col_dias:
                dias_promedio = df_cxc.groupby("cliente")[col_dias].mean().reset_index()
                dias_promedio.columns = ["Cliente", "Días Prom"]
                top_deudores = top_deudores.merge(dias_promedio, on="Cliente", how="left")
            
            top_deudores = top_deudores.sort_values("Adeudo", ascending=False).head(5)
            top_deudores["% Total"] = (top_deudores["Adeudo"] / total_adeudado * 100).round(1)
            
            # Formatear tabla
            top_deudores_display = top_deudores.copy()
            top_deudores_display["Adeudo"] = top_deudores_display["Adeudo"].apply(lambda x: formato_moneda(x))
            top_deudores_display["% Total"] = top_deudores_display["% Total"].apply(lambda x: f"{x}%")
            
            if col_dias:
                top_deudores_display["Días Prom"] = top_deudores_display["Días Prom"].apply(lambda x: f"{x:.0f}" if pd.notna(x) else "N/A")
                top_deudores_display["Riesgo"] = top_deudores["Días Prom"].apply(
                    lambda x: "🔴" if pd.notna(x) and x > 90 else "🟡" if pd.notna(x) and x > 60 else "🟢"
                )
            
            st.dataframe(top_deudores_display, use_container_width=True, hide_index=True)
        else:
            st.info("No hay información de deudores disponible")
    
    # =====================================================================
    # SECCIÓN 6: INSIGHTS Y RECOMENDACIONES ESTRATÉGICAS
    # =====================================================================
    
    st.markdown("---")
    st.subheader("💡 Insights Estratégicos")
    
    insights = []
    
    # Insight 1: Análisis de ventas
    if "fecha" in df_ventas.columns and variacion_ventas > 0:
        insights.append(f"📈 **Crecimiento positivo:** Las ventas aumentaron {variacion_ventas:.1f}% vs mes anterior. Mantener estrategias actuales.")
    elif "fecha" in df_ventas.columns and variacion_ventas < 0:
        insights.append(f"📉 **Atención requerida:** Ventas cayeron {abs(variacion_ventas):.1f}%. Revisar estrategia comercial y condiciones de mercado.")
    
    # Insight 2: Salud de cartera
    if pct_vigente > 80:
        insights.append(f"✅ **Cartera saludable:** {pct_vigente:.1f}% de la cartera está vigente. Excelente gestión de cobranza.")
    elif pct_vigente < 60:
        insights.append(f"⚠️ **Cartera en riesgo:** Solo {pct_vigente:.1f}% está vigente. Urgente implementar plan de recuperación.")
    
    # Insight 3: Eficiencia operativa
    if eficiencia_ops > 2:
        insights.append(f"🎯 **Alta eficiencia:** Ratio Ventas/Cartera de {eficiencia_ops:.2f}x indica buena conversión de cartera en ventas.")
    elif eficiencia_ops < 1:
        insights.append(f"⚠️ **Baja conversión:** Ratio {eficiencia_ops:.2f}x sugiere acumulación de cartera. Acelerar ciclo de cobro.")
    
    # Insight 4: Diversificación
    if clientes_unicos < 10:
        insights.append(f"⚠️ **Riesgo de concentración:** Solo {clientes_unicos} clientes activos. Ampliar base de clientes para reducir riesgo.")
    elif clientes_unicos > 50:
        insights.append(f"✅ **Cartera diversificada:** {clientes_unicos} clientes activos reducen riesgo de concentración.")
    
    # Insight 5: Ticket promedio
    if ticket_promedio > 5000:
        insights.append(f"💎 **Alto valor transaccional:** Ticket promedio de {formato_moneda(ticket_promedio)} indica ventas de alto valor.")
    
    for i, insight in enumerate(insights, 1):
        st.markdown(f"{i}. {insight}")
    
    # =====================================================================
    # FOOTER CON ACCIONES RECOMENDADAS
    # =====================================================================
    
    st.markdown("---")
    st.markdown("### 🎯 Próximas Acciones Recomendadas")
    
    col_acc1, col_acc2, col_acc3 = st.columns(3)
    
    with col_acc1:
        st.markdown("**📞 Cobranza**")
        if pct_alto_riesgo > 10:
            st.markdown("- Contactar clientes >90 días")
            st.markdown("- Iniciar proceso legal si aplica")
        else:
            st.markdown("- Seguimiento preventivo")
            st.markdown("- Mantener políticas actuales")
    
    with col_acc2:
        st.markdown("**💼 Ventas**")
        if variacion_ventas < 0:
            st.markdown("- Revisar pipeline de ventas")
            st.markdown("- Capacitar equipo comercial")
        else:
            st.markdown("- Escalar estrategias exitosas")
            st.markdown("- Ampliar líneas productivas")
    
    with col_acc3:
        st.markdown("**📊 Gestión**")
        st.markdown("- Revisar políticas de crédito")
        st.markdown("- Optimizar procesos de aprobación")
        st.markdown("- Monitorear KPIs semanalmente")
    
    st.markdown("---")
    st.caption(f"📅 Reporte generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
