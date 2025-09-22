import streamlit as st
import pandas as pd
import altair as alt

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

    if "valor_usd" not in df.columns:
        st.error("No se encontró la columna 'valor_usd', 'ventas_usd' ni 'ventas_usd_con_iva'.")
        return

    # Asegurarse de que la columna 'ano' exista para los filtros y gráficos
    if "ano" not in df.columns and "fecha" in df.columns:
        df["ano"] = pd.to_datetime(df["fecha"], errors="coerce").dt.year

    # Mostrar dimensiones generales
    st.subheader("Resumen General de Ventas (USD)")

    total_usd = df["valor_usd"].sum()
    total_operaciones = len(df)

    col1, col2 = st.columns(2)
    col1.metric("Total Ventas (USD)", f"${total_usd:,.2f}")
    col2.metric("Total Operaciones", f"{total_operaciones:,}")

    # === Filtros opcionales ===
    st.subheader("Filtros")

    # Buscar dinámicamente si la columna se llama 'agente', 'vendedor' o 'ejecutivo'
    columna_agente = next((col for col in df.columns if col.lower() in ["agente", "vendedor", "ejecutivo"]), None)

    if columna_agente:
        df["agente"] = df[columna_agente].astype(str)  # Estandarizar
        agentes = sorted(df["agente"].dropna().unique())
        agente_sel = st.selectbox("Selecciona Ejecutivo:", ["Todos"] + agentes)

        if agente_sel != "Todos":
            df = df[df["agente"] == agente_sel]
    else:
        st.info("ℹ️ No se encontró columna de vendedor (agente, vendedor, ejecutivo) para filtrar.")

    # Filtro adicional: línea de producto
    if "linea_producto" in df.columns:
        linea_producto = sorted(df["linea_producto"].dropna().unique())
        if linea_producto:
            linea_sel = st.selectbox("Selecciona Línea de Producto:", ["Todas"] + linea_producto)
            if linea_sel != "Todas":
                df = df[df["linea_producto"] == linea_sel]

    # KPIs filtrados
    st.subheader("Resultados Filtrados (USD)")
    total_filtrado_usd = df["valor_usd"].sum()
    operaciones_filtradas = len(df)

    colf1, colf2 = st.columns(2)
    colf1.metric("Ventas (USD)", f"${total_filtrado_usd:,.2f}")
    colf2.metric("Operaciones", f"{operaciones_filtradas:,}")

    # Tabla de detalle
    st.subheader("Detalle de Ventas Recientes")
    columnas_a_mostrar = [col for col in ["fecha", "agente", "cliente", "linea_producto", "valor_usd"] if col in df.columns]
    st.dataframe(df[columnas_a_mostrar].sort_values("fecha", ascending=False).head(50).style.format({"valor_usd": "${:,.2f}"}))

    # Ranking de vendedores
    if "agente" in df.columns:
        st.subheader("🏆 Ranking de Vendedores (USD)")

        ranking = (
            df.groupby("agente")
            .agg(total_usd=("valor_usd", "sum"), operaciones=("valor_usd", "count"))
            .sort_values("total_usd", ascending=False)
            .reset_index()
        )

        if not ranking.empty:
            ranking.insert(0, "Ranking", range(1, len(ranking) + 1))
            
            st.dataframe(ranking.style.format({
                "total_usd": "${:,.2f}",
                "operaciones": "{:,}"
            }))

    # Gráficos por agente
    if "agente" in df.columns and "ano" in df.columns and not df.empty:
        st.subheader("📊 Visualización de Ventas por Vendedor (USD)")

        chart_type = st.selectbox(
            "Selecciona tipo de gráfico:",
            ["Participación (Pie Chart)", "Ventas Totales (Barras)", "Ventas por Año"]
        )

        df_chart = df[["agente", "ano", "valor_usd"]].dropna()

        if chart_type == "Participación (Pie Chart)":
            pie_data = df_chart.groupby("agente").agg(total_ventas=("valor_usd", "sum")).reset_index()
            pie_data["tooltip_ventas"] = pie_data["total_ventas"].apply(lambda x: f"${x:,.2f}")

            chart = alt.Chart(pie_data).mark_arc(innerRadius=50).encode(
                theta=alt.Theta(field="total_ventas", type="quantitative"),
                color=alt.Color(field="agente", type="nominal"),
                tooltip=["agente:N", "tooltip_ventas:N"]
            ).properties(title="Participación de Vendedores sobre Ventas Totales (USD)")

        elif chart_type == "Ventas Totales (Barras)":
            bar_data = df_chart.groupby("agente").agg(total_ventas=("valor_usd", "sum")).reset_index()
            bar_data["tooltip_ventas"] = bar_data["total_ventas"].apply(lambda x: f"${x:,.2f}")

            chart = alt.Chart(bar_data).mark_bar().encode(
                x=alt.X("total_ventas:Q", title="Ventas Totales (USD)"),
                y=alt.Y("agente:N", sort="-x", title="Vendedor"),
                tooltip=["agente:N", "tooltip_ventas:N"]
            ).properties(title="Ventas Totales por Vendedor (USD)")

        elif chart_type == "Ventas por Año":
            line_data = df_chart.groupby(["ano", "agente"]).agg(total_ventas=("valor_usd", "sum")).reset_index()
            line_data["tooltip_ventas"] = line_data["total_ventas"].apply(lambda x: f"${x:,.2f}")

            chart = alt.Chart(line_data).mark_line(point=True).encode(
                x=alt.X("ano:O", title="Año"),
                y=alt.Y("total_ventas:Q", title="Ventas (USD)"),
                color="agente:N",
                tooltip=["ano:O", "agente:N", "tooltip_ventas:N"]
            ).properties(title="Evolución de Ventas por Vendedor (USD)")

        st.altair_chart(chart, use_container_width=True)
    elif "agente" not in df.columns:
        st.info("ℹ️ Gráficos por vendedor no disponibles. Se requiere una columna 'agente', 'vendedor' o 'ejecutivo'.")
    elif "ano" not in df.columns:
        st.info("ℹ️ Gráfico de 'Ventas por Año' no disponible. Se requiere una columna 'ano' o 'fecha'.")
