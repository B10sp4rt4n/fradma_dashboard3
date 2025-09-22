# main/analisis_productos_agentes.py
import pandas as pd
import streamlit as st
import altair as alt

def run(df):
    # Asegurarse de que las columnas estén normalizadas
    if 'linea_producto' not in df.columns or 'agente' not in df.columns:
        st.error("❌ Las columnas necesarias no están presentes en el DataFrame normalizado.")
        return

    # Agrupar por producto (linea_producto) y calcular las ventas totales y cantidad
    product_analysis = df.groupby(['linea_producto']).agg(
        total_cantidad=('cantidad', 'sum'),
        total_ventas=('valor_usd', 'sum')
    ).reset_index()
    
    # Producto con mayor cantidad vendida
    top_quantity_product = product_analysis.sort_values(by='total_cantidad', ascending=False).iloc[0]
    
    # Producto con mayor monto vendido
    top_value_product = product_analysis.sort_values(by='total_ventas', ascending=False).iloc[0]
    
    # Mostrar los productos champions
    st.subheader("Productos Champions")
    st.write("Producto con mayor cantidad vendida:")
    st.write(f"**{top_quantity_product['linea_producto']}** con **{top_quantity_product['total_cantidad']}** unidades.")
    st.write("Producto con mayor monto vendido:")
    st.write(f"**{top_value_product['linea_producto']}** con **{top_value_product['total_ventas']} USD**.")
    
    # Agrupar por producto y agente (vendedor)
    agent_sales_analysis = df.groupby(['linea_producto', 'agente']).agg(
        total_ventas_mxn=('valor_usd', 'sum'),
        total_cantidad_vendida=('cantidad', 'sum')
    ).reset_index()

    # Identificar el agente que más vende el producto de mayor valor (total ventas)
    top_value_agent = agent_sales_analysis.loc[agent_sales_analysis['total_ventas_mxn'].idxmax()]
    
    # Identificar el agente que más vende el producto de mayor cantidad vendida
    top_quantity_agent = agent_sales_analysis.loc[agent_sales_analysis['total_cantidad_vendida'].idxmax()]
    
    # Mostrar los agentes champions
    st.subheader("Agentes Champions")
    st.write("Agente que más vende el producto con mayor monto:")
    st.write(f"**{top_value_agent['agente']}** vendió el producto **{top_value_agent['linea_producto']}** con un total de **{top_value_agent['total_ventas_mxn']} USD**.")
    
    st.write("Agente que más vende el producto con mayor cantidad:")
    st.write(f"**{top_quantity_agent['agente']}** vendió el producto **{top_quantity_agent['linea_producto']}** con un total de **{top_quantity_agent['total_cantidad_vendida']} unidades**.")
    
    # Visualización de los Top 5 productos por cantidad
    st.subheader("Top 5 Productos por Cantidad Vendida")
    top_quantity_chart = alt.Chart(product_analysis.head(5)).mark_bar().encode(
        x=alt.X('linea_producto:N', sort='-y'),
        y='total_cantidad:Q',
        color='linea_producto:N'
    ).properties(title='Top 5 Productos por Cantidad Vendida')
    
    st.altair_chart(top_quantity_chart, use_container_width=True)
    
    # Visualización de los Top 5 agentes por ventas
    st.subheader("Top 5 Agentes por Ventas (USD)")
    top_value_chart = alt.Chart(agent_sales_analysis.head(5)).mark_bar().encode(
        x=alt.X('agente:N', sort='-y'),
        y='total_ventas_mxn:Q',
        color='agente:N'
    ).properties(title='Top 5 Agentes por Ventas')
    
    st.altair_chart(top_value_chart, use_container_width=True)
