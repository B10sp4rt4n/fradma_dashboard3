import streamlit as st
import pandas as pd
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
import io

def run(df):
    st.title("Heatmap de Ventas (USD)")

    # --- 1. VALIDACIÓN DE DATOS ---
    columna_ventas = st.session_state.get("columna_ventas", "valor_usd")
    if columna_ventas not in df.columns:
        st.error(f"Columna de ventas '{columna_ventas}' no encontrada.")
        return

    columnas_requeridas = {"fecha", "linea_producto", "ano", "mes"}
    if not columnas_requeridas.issubset(df.columns):
        st.error(f"Faltan columnas requeridas. Se necesitan: {', '.join(columnas_requeridas - set(df.columns))}")
        return

    df[columna_ventas] = pd.to_numeric(df[columna_ventas], errors='coerce').fillna(0)

    # --- 2. OPCIONES Y FILTROS EN SIDEBAR ---
    with st.sidebar:
        st.header("⚙️ Opciones de Análisis")
        periodo_tipo = st.selectbox(
            "🗓️ Agrupar por:",
            ["Mensual", "Trimestral", "Anual"],
            index=0
        )
        mostrar_crecimiento = st.checkbox("📈 Mostrar % Crecimiento vs. Periodo Anterior")

    # --- 3. PROCESAMIENTO DE PERIODOS ---
    if periodo_tipo == "Mensual":
        df['periodo'] = df['fecha'].dt.strftime('%Y-%m')
    elif periodo_tipo == "Trimestral":
        df['periodo'] = df['fecha'].dt.to_period('Q').astype(str)
    else: # Anual
        df['periodo'] = df['ano'].astype(str)
    
    df = df.sort_values('periodo')

    # --- 4. CREACIÓN DE TABLA PIVOTE ---
    pivot_table = df.pivot_table(
        index='periodo',
        columns='linea_producto',
        values=columna_ventas,
        aggfunc='sum',
        fill_value=0
    )

    # --- 5. FILTROS INTERACTIVOS ---
    lineas_disponibles = sorted(pivot_table.columns.tolist())
    selected_lineas = st.multiselect(
        "📌 Selecciona Líneas de Producto:",
        lineas_disponibles,
        default=lineas_disponibles
    )

    if not selected_lineas:
        st.warning("Por favor, selecciona al menos una línea de producto.")
        return

    df_filtered = pivot_table[selected_lineas]

    with st.sidebar:
        top_n = st.number_input(
            "🏅 Mostrar Top N Líneas (por venta total):",
            min_value=1,
            max_value=len(selected_lineas),
            value=min(10, len(selected_lineas)),
            step=1
        )

    total_por_linea = df_filtered.sum().nlargest(top_n)
    df_filtered = df_filtered[total_por_linea.index]

    # --- 6. CÁLCULO DE CRECIMIENTO Y ANOTACIONES ---
    annot_data = df_filtered.applymap(lambda x: f"${x:,.2f}")
    nuevas_lineas = set()

    if mostrar_crecimiento:
        periods_lag = 1 # Para anual y trimestral
        if periodo_tipo == "Mensual":
            # Para mensual, el lag es 1 si los datos son continuos, pero puede ser complejo
            # si hay saltos. pct_change(1) es lo más directo.
            periods_lag = 1
        
        growth_table = df_filtered.pct_change(periods=periods_lag) * 100

        for row in annot_data.index:
            for col in annot_data.columns:
                val = df_filtered.loc[row, col]
                growth = growth_table.loc[row, col]
                
                if pd.notna(val) and val > 0:
                    if pd.notna(growth):
                        if np.isinf(growth):
                            annot_data.loc[row, col] += "\n(Nuevo)"
                            nuevas_lineas.add(col)
                        else:
                            annot_data.loc[row, col] += f"\n({growth:.1f}%)"
    
    if nuevas_lineas:
        st.info(f"**Nuevas Ventas Detectadas en:** {', '.join(sorted(list(nuevas_lineas)))}")

    # --- 7. GENERACIÓN DEL HEATMAP ---
    st.subheader(f"Heatmap de Ventas en USD ({periodo_tipo})")
    
    fig, ax = plt.subplots(figsize=(max(10, len(df_filtered.columns) * 1.2), max(6, len(df_filtered.index) * 0.5)))
    
    sns.heatmap(
        df_filtered,
        annot=annot_data,
        fmt="",
        cmap="Greens",
        cbar_kws={'label': 'Ventas (USD)'},
        linewidths=0.5,
        linecolor='gray',
        ax=ax,
        annot_kws={"size": 8} # Ajustar tamaño de fuente de anotaciones
    )

    # Coloreado dinámico del texto para mejor legibilidad
    norm = plt.Normalize(df_filtered.min().min(), df_filtered.max().max())
    for text in ax.texts:
        value_str = text.get_text().split('\n')[0].replace('$', '').replace(',', '')
        try:
            value = float(value_str)
            intensity = norm(value)
            text.set_color('white' if intensity > 0.6 else 'black')
            if "(Nuevo)" in text.get_text():
                text.set_weight('bold')
        except ValueError:
            text.set_color('black')


    ax.set_xlabel("Línea de Producto", fontsize=12)
    ax.set_ylabel("Periodo", fontsize=12)
    ax.tick_params(axis='x', rotation=45)
    plt.title(f"Heatmap de Ventas por Línea de Producto ({periodo_tipo})", fontsize=14, pad=20)
    plt.tight_layout()
    st.pyplot(fig)

    # --- 8. BOTÓN DE DESCARGA ---
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        df_filtered.to_excel(writer, sheet_name='Heatmap_Filtrado')
    
    st.download_button(
        label="📥 Descargar Tabla como Excel",
        data=buffer.getvalue(),
        file_name=f"heatmap_ventas_{periodo_tipo.lower()}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )