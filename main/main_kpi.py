import streamlit as st
import pandas as pd
import altair as alt
import plotly.express as px

def run():
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
    col1.metric("Total Ventas USD", f"${total_usd:,.2f}")
    col2.metric("Operaciones", f"{total_operaciones:,}")

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
    colf1.metric("Ventas USD (filtro)", f"${total_filtrado_usd:,.2f}")
    colf2.metric("Operaciones (filtro)", f"{operaciones_filtradas:,}")

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
