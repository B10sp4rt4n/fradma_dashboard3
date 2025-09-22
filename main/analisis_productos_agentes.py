# main/analisis_productos_agentes.py
import pandas as pd
import streamlit as st
import altair as alt

def run(df):
    st.title("📊 Análisis de Productos y Agentes")

    # --- 1. ESTANDARIZACIÓN DE COLUMNAS ---
    mapa_nombres = {
        "linea_producto": ["linea_de_negocio", "linea_producto", "producto", "descripcion"],
        "agente": ["vendedor", "agente", "ejecutivo"],
        "cantidad": ["cantidad", "unidades", "piezas", "importe"],
        "valor_usd": ["valor_usd", "ventas_usd", "total_usd"]
    }

    for estandar, posibles in mapa_nombres.items():
        col_encontrada = next((p for p in posibles if p in df.columns), None)
        if col_encontrada and estandar not in df.columns:
            df = df.rename(columns={col_encontrada: estandar})

    columnas_clave = {"linea_producto", "agente", "cantidad", "valor_usd"}
    if not columnas_clave.issubset(df.columns):
        faltantes = columnas_clave - set(df.columns)
        st.error(f"❌ Faltan columnas esenciales para el análisis: **{', '.join(faltantes)}**.")
        st.info(f"Asegúrate de que tu archivo contenga columnas para: {', '.join(mapa_nombres.keys())}")
        st.info(f"Columnas detectadas en el archivo: {df.columns.tolist()}")
        return

    # --- 2. LIMPIEZA DE DATOS ---
    df["cantidad"] = pd.to_numeric(df["cantidad"], errors='coerce').fillna(0)
    df["valor_usd"] = pd.to_numeric(df["valor_usd"], errors='coerce').fillna(0)
    
    # --- 3. ANÁLISIS DE PRODUCTOS ---
    st.subheader("🏆 Productos Campeones")
    
    product_analysis = df.groupby('linea_producto').agg(
        total_cantidad=('cantidad', 'sum'),
        total_ventas=('valor_usd', 'sum')
    ).reset_index()

    # Métricas de productos
    top_quantity_product = product_analysis.sort_values(by='total_cantidad', ascending=False).iloc[0]
    top_value_product = product_analysis.sort_values(by='total_ventas', ascending=False).iloc[0]

    col1, col2 = st.columns(2)
    col1.metric("Producto con Mayor Cantidad Vendida", 
                top_quantity_product['linea_producto'], 
                f"{top_quantity_product['total_cantidad']:,.0f} unidades")
    col2.metric("Producto con Mayor Monto de Venta (USD)", 
                top_value_product['linea_producto'], 
                f"${top_value_product['total_ventas']:,.2f}")

    # Gráfico Top 5 Productos por Ventas
    st.write("Top 5 Productos por Ventas (USD)")
    top_products_chart = alt.Chart(product_analysis.nlargest(5, 'total_ventas')).mark_bar().encode(
        x=alt.X('linea_producto:N', sort='-y', title="Producto"),
        y=alt.Y('total_ventas:Q', title="Ventas (USD)"),
        tooltip=[
            alt.Tooltip('linea_producto', title="Producto"),
            alt.Tooltip('total_ventas', title="Ventas (USD)", format="$,.2f"),
            alt.Tooltip('total_cantidad', title="Cantidad", format=",.0f")
        ]
    ).properties(
        title='Top 5 Productos con Mayor Venta'
    )
    st.altair_chart(top_products_chart, use_container_width=True)

    st.markdown("---")

    # --- 4. ANÁLISIS DE AGENTES ---
    st.subheader("🥇 Agentes Campeones")

    agent_total_sales = df.groupby('agente').agg(
        total_ventas_usd=('valor_usd', 'sum'),
        total_cantidad_vendida=('cantidad', 'sum')
    ).reset_index()

    top_selling_agent = agent_total_sales.nlargest(1, 'total_ventas_usd').iloc[0]

    st.metric("Agente con Mayor Venta Total (USD)",
              top_selling_agent['agente'],
              f"${top_selling_agent['total_ventas_usd']:,.2f}")

    # Gráfico Top 5 Agentes por Ventas
    st.write("Top 5 Agentes por Ventas (USD)")
    top_agents_chart = alt.Chart(agent_total_sales.nlargest(5, 'total_ventas_usd')).mark_bar().encode(
        x=alt.X('agente:N', sort='-y', title="Agente"),
        y=alt.Y('total_ventas_usd:Q', title="Ventas (USD)"),
        tooltip=[
            alt.Tooltip('agente', title="Agente"),
            alt.Tooltip('total_ventas_usd', title="Ventas (USD)", format="$,.2f"),
            alt.Tooltip('total_cantidad_vendida', title="Cantidad Total", format=",.0f")
        ]
    ).properties(
        title='Top 5 Agentes con Mayor Venta'
    )
    st.altair_chart(top_agents_chart, use_container_width=True)
    
    st.markdown("---")

    # --- 5. ANÁLISIS DETALLADO AGENTE-PRODUCTO ---
    st.subheader("🔍 Detalle por Agente y Producto")
    
    agent_product_sales = df.groupby(['agente', 'linea_producto']).agg(
        total_ventas_usd=('valor_usd', 'sum'),
        total_cantidad_vendida=('cantidad', 'sum')
    ).reset_index()

    top_combo = agent_product_sales.nlargest(1, 'total_ventas_usd').iloc[0]

    st.info(f"La combinación más exitosa es **{top_combo['agente']}** vendiendo **{top_combo['linea_producto']}** con un total de **${top_combo['total_ventas_usd']:,.2f}**.")

    with st.expander("Ver tabla detallada de ventas por Agente y Producto"):
        st.dataframe(agent_product_sales.sort_values("total_ventas_usd", ascending=False).style.format({
            "total_ventas_usd": "${:,.2f}",
            "total_cantidad_vendida": "{:,.0f}"
        }))

