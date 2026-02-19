import streamlit as st
import pandas as pd
import altair as alt
import plotly.express as px
from utils.ai_helper_premium import generar_insights_kpi_vendedores
from utils.logger import configurar_logger

logger = configurar_logger("main_kpi", nivel="INFO")

def run(habilitar_ia=False, openai_api_key=None):
    st.title("📈 KPIs Generales")

    if "df" not in st.session_state:
        st.warning("Primero debes cargar un archivo CSV o Excel en el menú lateral.")
        return

    df = st.session_state["df"].copy()

    # Asegurar compatibilidad: valor_usd = ventas_usd_con_iva o ventas_usd
    if "valor_usd" not in df.columns:
        if "ventas_usd" in df.columns:
            df = df.rename(columns={"ventas_usd": "valor_usd"})
        elif "ventas_usd_con_iva" in df.columns:
            df = df.rename(columns={"ventas_usd_con_iva": "valor_usd"})

    if "valor_usd" not in df.columns:
        st.error("No se encontró la columna 'valor_usd', 'ventas_usd' ni 'ventas_usd_con_iva'.")
        return

    df["anio"] = pd.to_datetime(df["fecha"], errors="coerce").dt.year

    # Mostrar dimensiones generales
    st.subheader("Resumen General de Ventas")

    total_usd = df["valor_usd"].sum()
    total_operaciones = len(df)

    col1, col2 = st.columns(2)
    col1.metric("Total Ventas USD", f"${total_usd:,.2f}",
                help="📐 Suma total de ventas en USD de todos los registros en el archivo")
    col2.metric("Operaciones", f"{total_operaciones:,}",
                help="📐 Número total de transacciones/facturas registradas")

    # === Filtros opcionales ===
    st.subheader("Filtros por Ejecutivo")

    # Buscar dinámicamente si la columna se llama 'agente', 'vendedor' o 'ejecutivo'
    columna_agente = None
    for col in df.columns:
        if col.lower() in ["agente", "vendedor", "ejecutivo"]:
            columna_agente = col
            break

    if columna_agente:
        df["agente"] = df[columna_agente]  # Ya normalizado en app.py
        agentes = sorted(df["agente"].dropna().unique())
        agente_sel = st.selectbox("Selecciona Ejecutivo:", ["Todos"] + agentes)

        if agente_sel != "Todos":
            df = df[df["agente"] == agente_sel]
    else:
        st.warning("⚠️ No se encontró columna 'agente', 'vendedor' o 'ejecutivo'.")

    # Filtro adicional: línea de producto
    linea_producto = df["linea_producto"].dropna().unique() if "linea_producto" in df.columns else []
    linea_sel = st.selectbox("Selecciona Línea de Producto (opcional):", ["Todas"] + list(linea_producto)) if len(linea_producto) > 0 else "Todas"

    if linea_sel != "Todas" and "linea_producto" in df.columns:
        df = df[df["linea_producto"] == linea_sel]

    # KPIs filtrados
    st.subheader("KPIs Filtrados")
    total_filtrado_usd = df["valor_usd"].sum()
    operaciones_filtradas = len(df)

    colf1, colf2 = st.columns(2)
    colf1.metric("Ventas USD (filtro)", f"${total_filtrado_usd:,.2f}",
                 help="📐 Total de ventas después de aplicar filtros de ejecutivo/línea")
    colf2.metric("Operaciones (filtro)", f"{operaciones_filtradas:,}",
                 help="📐 Número de transacciones que cumplen con los filtros aplicados")

    # Tabla de detalle
    st.subheader("Detalle de ventas")
    st.dataframe(df.sort_values("fecha", ascending=False).head(50))

    # Ranking de vendedores
    if "agente" in df.columns:
        st.subheader("🏆 Ranking de Vendedores")

        ranking = (
            df.groupby("agente")
            .agg(total_usd=("valor_usd", "sum"), operaciones=("valor_usd", "count"))
            .sort_values("total_usd", ascending=False)
            .reset_index()
        )

        ranking.insert(0, "Ranking", range(1, len(ranking) + 1))
        ranking["total_usd"] = ranking["total_usd"].round(0)

        st.dataframe(ranking.style.format({
            "total_usd": "${:,.2f}",
            "operaciones": "{:,}"
        }))
        
        # =====================================================================
        # KPIs DE EFICIENCIA POR VENDEDOR
        # =====================================================================
        st.subheader("⚡ KPIs de Eficiencia por Vendedor")
        
        # Calcular métricas de eficiencia
        vendedores_eficiencia = []
        
        for agente in df["agente"].unique():
            agente_data = df[df["agente"] == agente]
            
            total_ventas = agente_data["valor_usd"].sum()
            operaciones_count = len(agente_data)
            
            # Ticket promedio (ventas por operación)
            ticket_promedio = total_ventas / operaciones_count if operaciones_count > 0 else 0
            
            # Clientes únicos (si existe columna cliente)
            if 'cliente' in agente_data.columns:
                clientes_unicos = agente_data['cliente'].nunique()
                ventas_por_cliente = total_ventas / clientes_unicos if clientes_unicos > 0 else 0
            else:
                clientes_unicos = 0
                ventas_por_cliente = 0
            
            vendedores_eficiencia.append({
                'agente': agente,
                'total_ventas': total_ventas,
                'operaciones': operaciones_count,
                'ticket_promedio': ticket_promedio,
                'clientes_unicos': clientes_unicos,
                'ventas_por_cliente': ventas_por_cliente
            })
        
        df_eficiencia_ventas = pd.DataFrame(vendedores_eficiencia)
        
        # Clasificar vendedores
        # Alto volumen = muchas operaciones, Alto ticket = mayor valor por operación
        mediana_ops = df_eficiencia_ventas['operaciones'].median()
        mediana_ticket = df_eficiencia_ventas['ticket_promedio'].median()
        
        def clasificar_vendedor(row):
            if row['operaciones'] > mediana_ops and row['ticket_promedio'] > mediana_ticket:
                return "🌟 Elite (Alto Volumen + Alto Ticket)"
            elif row['operaciones'] > mediana_ops:
                return "📊 Alto Volumen"
            elif row['ticket_promedio'] > mediana_ticket:
                return "💎 Alto Ticket (Eficiencia)"
            else:
                return "🔄 En Desarrollo"
        
        df_eficiencia_ventas['clasificacion'] = df_eficiencia_ventas.apply(clasificar_vendedor, axis=1)
        
        # Mostrar métricas principales
        col_ef1, col_ef2, col_ef3, col_ef4 = st.columns(4)
        
        mejor_ticket = df_eficiencia_ventas.loc[df_eficiencia_ventas['ticket_promedio'].idxmax()]
        mayor_volumen = df_eficiencia_ventas.loc[df_eficiencia_ventas['operaciones'].idxmax()]
        
        col_ef1.metric("💰 Mejor Ticket Promedio", 
                      f"${mejor_ticket['ticket_promedio']:,.2f}",
                      delta=mejor_ticket['agente'])
        col_ef2.metric("📊 Mayor Volumen Ops", 
                      f"{mayor_volumen['operaciones']:,.0f}",
                      delta=mayor_volumen['agente'])
        col_ef3.metric("💵 Ticket Prom. General", 
                      f"${df_eficiencia_ventas['ticket_promedio'].mean():,.2f}")
        col_ef4.metric("🎯 Ops Promedio", 
                      f"{df_eficiencia_ventas['operaciones'].mean():,.0f}")
        
        # Matriz de Eficiencia vs Volumen
        st.write("### 📈 Matriz de Eficiencia vs Volumen")
        
        fig_matriz = px.scatter(
            df_eficiencia_ventas,
            x='operaciones',
            y='ticket_promedio',
            size='total_ventas',
            color='clasificacion',
            hover_name='agente',
            labels={
                'operaciones': 'Número de Operaciones',
                'ticket_promedio': 'Ticket Promedio (USD)',
                'total_ventas': 'Ventas Totales',
                'clasificacion': 'Clasificación'
            },
            title='Análisis de Vendedores: Eficiencia vs Volumen'
        )
        
        # Añadir líneas de referencia (medianas)
        fig_matriz.add_hline(y=mediana_ticket, line_dash="dash", line_color="gray", 
                            annotation_text="Mediana Ticket")
        fig_matriz.add_vline(x=mediana_ops, line_dash="dash", line_color="gray",
                            annotation_text="Mediana Ops")
        
        fig_matriz.update_layout(height=500)
        st.plotly_chart(fig_matriz, width='stretch')
        
        # Tabla detallada de eficiencia
        st.write("### 📋 Tabla Detallada de Eficiencia")
        
        df_ef_display = df_eficiencia_ventas.sort_values('total_ventas', ascending=False).copy()
        
        # Formatear columnas
        df_ef_table = df_ef_display[['agente', 'total_ventas', 'operaciones', 'ticket_promedio', 
                                     'clientes_unicos', 'ventas_por_cliente', 'clasificacion']].copy()
        
        df_ef_table['total_ventas'] = df_ef_table['total_ventas'].apply(lambda x: f"${x:,.2f}")
        df_ef_table['ticket_promedio'] = df_ef_table['ticket_promedio'].apply(lambda x: f"${x:,.2f}")
        df_ef_table['ventas_por_cliente'] = df_ef_table['ventas_por_cliente'].apply(
            lambda x: f"${x:,.2f}" if x > 0 else "N/A"
        )
        df_ef_table['clientes_unicos'] = df_ef_table['clientes_unicos'].apply(
            lambda x: f"{int(x)}" if x > 0 else "N/A"
        )
        
        df_ef_table.columns = [
            'Vendedor', 'Ventas Totales', 'Operaciones', 'Ticket Promedio',
            'Clientes', 'Venta/Cliente', 'Clasificación'
        ]
        
        st.dataframe(df_ef_table, width='stretch', hide_index=True)
        
        # Insights y recomendaciones
        st.write("### 💡 Insights y Recomendaciones")
        
        elite = df_eficiencia_ventas[df_eficiencia_ventas['clasificacion'].str.contains('Elite')]
        alto_vol = df_eficiencia_ventas[df_eficiencia_ventas['clasificacion'].str.contains('Alto Volumen') & 
                                       ~df_eficiencia_ventas['clasificacion'].str.contains('Elite')]
        alta_ef = df_eficiencia_ventas[df_eficiencia_ventas['clasificacion'].str.contains('Alta Eficiencia')]
        en_desarrollo = df_eficiencia_ventas[df_eficiencia_ventas['clasificacion'].str.contains('Desarrollo')]
        
        col_ins1, col_ins2 = st.columns(2)
        
        with col_ins1:
            if len(elite) > 0:
                st.success(f"🌟 **Vendedores Elite ({len(elite)})**")
                st.write("Mantienen alto volumen y alta eficiencia:")
                for _, v in elite.iterrows():
                    st.write(f"- {v['agente']}: ${v['total_ventas']:,.2f} ({v['operaciones']} ops)")
            
            if len(alto_vol) > 0:
                st.info(f"📊 **Alto Volumen ({len(alto_vol)})**")
                st.write("Oportunidad: Mejorar ticket promedio")
                for _, v in alto_vol.head(3).iterrows():
                    st.write(f"- {v['agente']}: {v['operaciones']} ops, ticket ${v['ticket_promedio']:,.2f}")
        
        with col_ins2:
            if len(alta_ef) > 0:
                st.info(f"💎 **Alta Eficiencia ({len(alta_ef)})**")
                st.write("Oportunidad: Aumentar volumen de operaciones")
                for _, v in alta_ef.head(3).iterrows():
                    st.write(f"- {v['agente']}: Ticket ${v['ticket_promedio']:,.2f}, {v['operaciones']} ops")
            
            if len(en_desarrollo) > 0:
                st.warning(f"🔄 **En Desarrollo ({len(en_desarrollo)})**")
                st.write("Requieren capacitación y seguimiento:")
                for _, v in en_desarrollo.head(3).iterrows():
                    st.write(f"- {v['agente']}: ${v['total_ventas']:,.2f} total")
        
        st.write("---")

    # Gráficos por agente
    if "agente" in df.columns and not df.empty:
        st.subheader("📊 Visualización de Ventas por Vendedor")

        chart_type = st.selectbox(
            "Selecciona tipo de gráfico:",
            ["Pie Chart", "Barras Horizontales", "Ventas por Año"]
        )

        df_chart = df[["agente", "anio", "valor_usd"]].dropna()

        # Agrupación base para todos los gráficos
        resumen_agente = (
            df_chart.groupby(["agente", "anio"])
            .agg(
                total_ventas=("valor_usd", "sum"),
                operaciones=("valor_usd", "count")
            )
            .reset_index()
        )
        resumen_agente["ventas_moneda"] = resumen_agente["total_ventas"].apply(lambda x: f"${x:,.2f}")

        if chart_type == "Pie Chart":
            pie_data = (
                resumen_agente.groupby("agente")
                .agg(
                    total_ventas=("total_ventas", "sum"),
                    operaciones=("operaciones", "sum")
                )
                .reset_index()
            )
            pie_data["ventas_moneda"] = pie_data["total_ventas"].apply(lambda x: f"${x:,.2f}")

            chart = alt.Chart(pie_data).mark_arc(innerRadius=50).encode(
                theta="total_ventas:Q",
                color="agente:N",
                tooltip=["agente:N", "ventas_moneda:N", "operaciones:Q"]
            ).properties(title="Participación de Vendedores (USD)")

        elif chart_type == "Barras Horizontales":
            bar_data = (
                resumen_agente.groupby("agente")
                .agg(
                    total_ventas=("total_ventas", "sum"),
                    operaciones=("operaciones", "sum")
                )
                .reset_index()
                .sort_values("total_ventas", ascending=True)
            )
            bar_data["ventas_moneda"] = bar_data["total_ventas"].apply(lambda x: f"${x:,.2f}")

            chart = alt.Chart(bar_data).mark_bar().encode(
                x="total_ventas:Q",
                y=alt.Y("agente:N", sort="-x"),
                tooltip=["agente:N", "ventas_moneda:N", "operaciones:Q"]
            ).properties(title="Ventas Totales por Vendedor (USD)")

        elif chart_type == "Ventas por Año":
            resumen_agente["anio"] = resumen_agente["anio"].astype(str)
            chart = alt.Chart(resumen_agente).mark_bar().encode(
                x=alt.X("anio:N", title="Año"),
                y=alt.Y("total_ventas:Q", title="Ventas USD"),
                color="agente:N",
                tooltip=["anio:N", "agente:N", "ventas_moneda:N", "operaciones:Q"]
            ).properties(title="Ventas por Vendedor en el Tiempo")

        st.altair_chart(chart, width='stretch')    
    st.markdown("---")
    
    # =====================================================================
    # ANÁLISIS PREMIUM CON IA - INSIGHTS ESTRATÉGICOS DE EQUIPO DE VENTAS
    # =====================================================================
    if habilitar_ia and openai_api_key:
        st.header("🤖 Insights Estratégicos Premium - Equipo de Ventas")
        
        # Obtener filtros configurados
        periodo_seleccionado = st.session_state.get("analisis_periodo", "Todos los datos")
        lineas_seleccionadas = st.session_state.get("analisis_lineas", ["Todas"])
        
        st.info(
            f"📋 **Configuración:** Periodo: {periodo_seleccionado} | "
            f"Líneas: {', '.join(lineas_seleccionadas[:3])}{'...' if len(lineas_seleccionadas) > 3 else ''}"
        )
        
        # Botón para ejecutar análisis
        if st.button("🚀 Generar Análisis con IA", type="primary", use_container_width=True, key="btn_ia_kpi"):
            with st.spinner("🔄 Analizando patrones del equipo con IA..."):
                try:
                    # Preparar datos para el análisis
                    # Primero agrupar por agente (sin año) para tener totales por vendedor
                    resumen_por_vendedor = (
                        resumen_agente.groupby("agente")
                        .agg(
                            total_ventas=("total_ventas", "sum"),
                            operaciones=("operaciones", "sum")
                        )
                        .reset_index()
                    )
                    # Calcular ticket promedio por vendedor
                    resumen_por_vendedor["ticket_promedio"] = (
                        resumen_por_vendedor["total_ventas"] / resumen_por_vendedor["operaciones"]
                    ).fillna(0)
                    
                    num_vendedores = len(resumen_por_vendedor)
                    ticket_promedio_general = resumen_por_vendedor["total_ventas"].sum() / resumen_por_vendedor["operaciones"].sum()
                    
                    # Calcular eficiencia general (simplificado)
                    eficiencia_general = 100 * (resumen_por_vendedor["total_ventas"].sum() / (resumen_por_vendedor["operaciones"].sum() * ticket_promedio_general))
                    
                    # Top y bottom performers
                    sorted_vendedores = resumen_por_vendedor.sort_values("total_ventas", ascending=False)
                    vendedor_top = sorted_vendedores.iloc[0]["agente"]
                    ventas_vendedor_top = sorted_vendedores.iloc[0]["total_ventas"]
                    vendedor_bottom = sorted_vendedores.iloc[-1]["agente"]
                    ventas_vendedor_bottom = sorted_vendedores.iloc[-1]["total_ventas"]
                    
                    # Concentración top 3
                    top3_ventas = sorted_vendedores.head(3)["total_ventas"].sum()
                    total_ventas = resumen_por_vendedor["total_ventas"].sum()
                    concentracion_top3_pct = (top3_ventas / total_ventas * 100) if total_ventas > 0 else 0
                    
                    # Preparar lista de vendedores
                    datos_vendedores = []
                    for _, row in sorted_vendedores.head(10).iterrows():
                        datos_vendedores.append({
                            'nombre': row['agente'],
                            'ventas': row['total_ventas'],
                            'ticket_avg': row['ticket_promedio']
                        })
                    
                    # Preparar contexto de filtros para IA
                    if "Todas" not in lineas_seleccionadas:
                        lineas_texto = ", ".join(lineas_seleccionadas)
                        contexto_filtros = f"Este análisis se enfoca ÚNICAMENTE en las siguientes líneas de negocio: {lineas_texto}. Las ventas y métricas reflejan SOLO estas líneas, no todo el negocio."
                    else:
                        contexto_filtros = None
                    
                    # Generar insights con IA
                    insights = generar_insights_kpi_vendedores(
                        num_vendedores=num_vendedores,
                        ticket_promedio_general=ticket_promedio_general,
                        eficiencia_general=eficiencia_general,
                        vendedor_top=vendedor_top,
                        ventas_vendedor_top=ventas_vendedor_top,
                        vendedor_bottom=vendedor_bottom,
                        ventas_vendedor_bottom=ventas_vendedor_bottom,
                        concentracion_top3_pct=concentracion_top3_pct,
                        api_key=openai_api_key,
                        datos_vendedores=datos_vendedores,
                        contexto_filtros=contexto_filtros
                    )
                    
                    if insights:
                        # Insight principal
                        st.info(f"💡 **{insights.get('insight_clave', 'No disponible')}**")
                        
                        # Columnas para organizar insights
                        col_izq, col_der = st.columns(2)
                        
                        with col_izq:
                            st.markdown("### 👥 Recomendaciones de Equipo")
                            recomendaciones = insights.get('recomendaciones_equipos', [])
                            if recomendaciones:
                                for rec in recomendaciones:
                                    st.markdown(f"- {rec}")
                            else:
                                st.caption("No disponible")
                            
                            st.markdown("")
                            
                            st.markdown("### 🎯 Oportunidades de Mejora")
                            oportunidades = insights.get('oportunidades_mejora', [])
                            if oportunidades:
                                for opp in oportunidades:
                                    st.markdown(f"- {opp}")
                            else:
                                st.caption("No disponible")
                        
                        with col_der:
                            st.markdown("### ⚠️ Alertas Estratégicas")
                            alertas = insights.get('alertas_estrategicas', [])
                            if alertas:
                                for alerta in alertas:
                                    st.markdown(f"- {alerta}")
                            else:
                                st.caption("No hay alertas críticas")
                        
                        st.caption("🤖 Análisis generado por OpenAI GPT-4o-mini")
                    else:
                        st.warning("⚠️ No se pudo generar el análisis de IA")
                
                except Exception as e:
                    st.error(f"❌ Error al generar insights de IA: {str(e)}")
                    logger.error(f"Error en análisis de IA vendedores: {e}", exc_info=True)
        else:
            st.caption("👆 Presiona el botón para generar insights estratégicos según tus filtros")
        
        st.markdown("---")
    
    # =====================================================================
    # PANEL DE DEFINICIONES Y FÓRMULAS
    # =====================================================================
    with st.expander("📐 **Definiciones y Fórmulas de KPIs**"):
        st.markdown("""
        ### 📊 Métricas Generales
        
        **💰 Total Ventas USD**
        - **Definición**: Suma de todas las ventas registradas en dólares
        - **Fórmula**: `Σ valor_usd (todos los registros)`
        - **Fuente**: Columna `ventas_usd`, `ventas_usd_con_iva` o `valor_usd`
        
        **📦 Operaciones**
        - **Definición**: Número total de transacciones/facturas
        - **Fórmula**: `COUNT(registros)`
        - **Nota**: Cada fila = 1 operación
        
        **🎯 Ventas USD (filtro)**
        - **Definición**: Total de ventas después de aplicar filtros de ejecutivo/línea
        - **Uso**: Analizar desempeño segmentado
        
        ---
        
        ### ⚡ Métricas de Eficiencia por Vendedor
        
        **💵 Ticket Promedio**
        - **Definición**: Valor promedio de cada transacción
        - **Fórmula**: `Total Ventas USD / Número de Operaciones`
        - **Interpretación**: Mayor ticket = Ventas de mayor valor unitario
        - **Ejemplo**: $100,000 en 10 ops = $10,000 de ticket promedio
        
        **📊 Total Ventas**
        - **Definición**: Suma acumulada de ventas del vendedor
        - **Fórmula**: `Σ ventas_usd (por agente)`
        
        **🔢 Operaciones**
        - **Definición**: Cantidad de transacciones generadas
        - **Fórmula**: `COUNT(ventas por agente)`
        
        ---
        
        ### 🎯 Clasificación de Vendedores
        
        Los vendedores se clasifican en 4 cuadrantes según su desempeño:
        
        **🏆 Alto Volumen (Alto Ticket)**
        - **Criterios**: 
          - Ticket promedio ≥ Mediana general
          - Total de operaciones ≥ Mediana general
        - **Perfil**: Vendedores élite - cierran grandes ventas con frecuencia
        - **Estrategia**: Retener, reconocer, replicar best practices
        
        **📈 Alto Volumen (Bajo Ticket)**
        - **Criterios**:
          - Ticket promedio < Mediana general
          - Total de operaciones ≥ Mediana general
        - **Perfil**: Generadores de volumen - muchas ventas pequeñas
        - **Oportunidad**: Capacitación en upselling/cross-selling para aumentar ticket
        
        **💎 Alto Ticket (Eficiencia)**
        - **Criterios**:
          - Ticket promedio ≥ Mediana general
          - Total de operaciones < Mediana general
        - **Perfil**: Especialistas - cierran deals grandes ocasionalmente
        - **Oportunidad**: Aumentar frecuencia/volumen de operaciones
        - **Nota**: Antes llamado "Alta Eficiencia" (se renombró por claridad)
        
        **🔄 En Desarrollo**
        - **Criterios**:
          - Ticket promedio < Mediana general
          - Total de operaciones < Mediana general
        - **Perfil**: Vendedores junior o con bajo desempeño
        - **Acción**: Capacitación intensiva, seguimiento cercano, planes de mejora
        
        ---
        
        ### 📈 Visualizaciones
        
        **Pie Chart (Gráfico de Pastel)**
        - Muestra participación porcentual de cada vendedor en ventas totales
        - Útil para identificar distribución de contribución
        
        **Barras Horizontales**
        - Compara ventas absolutas entre vendedores
        - Ordenado de mayor a menor
        
        **Ventas por Año**
        - Evolución temporal de ventas por vendedor
        - Útil para identificar tendencias y estacionalidad
        
        ---
        
        ### 🏅 Ranking de Vendedores
        
        **Criterio**: Ordenado por Total Ventas USD (descendente)
        - **Ranking #1**: Vendedor con mayor monto acumulado
        - **Columnas**:
          - Total USD: Suma de ventas
          - Operaciones: Cantidad de transacciones
        
        ---
        
        ### 📝 Notas Importantes
        
        - **Columna de agente**: Se detecta automáticamente como `agente`, `vendedor` o `ejecutivo`
        - **Filtros**: Aplicables por ejecutivo y línea de producto
        - **Años**: Se extrae automáticamente de la columna `fecha`
        - **Mediana vs Promedio**: Se usa mediana para evitar distorsión por outliers
        """)