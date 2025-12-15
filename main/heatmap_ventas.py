import streamlit as st
import pandas as pd
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
import plotly.graph_objects as go
import io
import unicodedata

def run(df):
    st.title("📊 Heatmap de Ventas (Entrada Genérica)")

    def clean_columns(columns):
        return (
            columns.astype(str)
            .str.strip()
            .str.lower()
            .map(lambda x: unicodedata.normalize('NFKD', x).encode('ascii', errors='ignore').decode('utf-8'))
        )

    def detectar_columna(df, posibles_nombres):
        for posible in posibles_nombres:
            for col in df.columns:
                if unicodedata.normalize('NFKD', col.lower().strip()).encode('ascii', errors='ignore').decode('utf-8') == unicodedata.normalize('NFKD', posible.lower().strip()).encode('ascii', errors='ignore').decode('utf-8'):
                    return col
        return None

    mapa_columnas = {
        "linea": ["linea_prodcucto", "linea_producto", "linea_de_negocio", "linea producto", "linea_de_producto"],
        "importe": ["valor_usd", "ventas_usd", "importe"],
        "producto": ["producto", "articulo", "item", "descripcion", "producto_nombre"]
    }

    df.columns = clean_columns(df.columns)
    df['mes_anio'] = df['fecha'].dt.strftime('%b-%Y')
    df['anio'] = df['fecha'].dt.year
    df['trimestre'] = df['fecha'].dt.to_period('Q').astype(str)

    columna_linea = detectar_columna(df, mapa_columnas["linea"])
    columna_importe = detectar_columna(df, mapa_columnas["importe"])
    columna_producto = detectar_columna(df, mapa_columnas["producto"])

    if columna_linea is None or columna_importe is None:
        st.error("❌ No se encontraron las columnas clave necesarias para 'línea' e 'importe'.")
        st.write(f"Columnas detectadas en tu archivo: {df.columns.tolist()}")
        return

    with st.sidebar:
        st.header("⚙️ Opciones de análisis")
        periodo_tipo = st.selectbox(
            "🗓️ Tipo de periodo:",
            ["Mensual", "Trimestral", "Anual", "Rango Personalizado"]
        )
        mostrar_crecimiento = st.checkbox("📈 Mostrar % de crecimiento")
        
        if mostrar_crecimiento:
            tipo_comparacion = st.radio(
                "Comparar contra:",
                ["Período anterior", "Mismo período año anterior"],
                help="Período anterior: mes vs mes previo, trimestre vs trimestre previo, etc.\nMismo período año anterior: ene-24 vs ene-23, Q1-24 vs Q1-23, etc."
            )

    def generar_periodo_id(row, periodo_tipo):
        """Genera el identificador del periodo de forma segura"""
        try:
            # Obtener año de forma segura
            if 'anio' in row.index:
                year_val = row['anio']
            elif 'año' in row.index:
                year_val = row['año']
            else:
                return ""
            
            # Validar que year_val no sea NaN
            if pd.isna(year_val):
                return ""
            
            year_short = str(int(float(year_val)))[-2:]
            
            # Obtener mes de forma segura
            if 'fecha' in row.index and pd.notna(row['fecha']):
                if hasattr(row['fecha'], 'month'):
                    month_num = row['fecha'].month
                else:
                    # Si no es datetime, intentar convertir
                    fecha_dt = pd.to_datetime(row['fecha'], errors='coerce')
                    if pd.notna(fecha_dt):
                        month_num = fecha_dt.month
                    else:
                        month_num = 1
            else:
                month_num = 1
            
            trimestre = (month_num - 1) // 3 + 1

            if periodo_tipo == "Mensual":
                return f"{year_short}.{month_num:02d}"
            elif periodo_tipo == "Trimestral":
                return f"{year_short}.Q{trimestre}"
            elif periodo_tipo == "Anual":
                return f"{year_short}"
            else:
                return f"{year_short}.{month_num:02d}"
        except Exception as e:
            st.warning(f"Error generando periodo_id: {e}")
            return ""

    # Asegurar que la columna fecha esté en formato datetime
    if 'fecha' in df.columns:
        df['fecha'] = pd.to_datetime(df['fecha'], errors='coerce')
    
    df['periodo_id'] = df.apply(lambda row: generar_periodo_id(row, periodo_tipo), axis=1)

    if periodo_tipo == "Mensual":
        df['periodo'] = df['mes_anio']
        growth_lag_secuencial = 1  # Comparar con mes anterior
        growth_lag_yoy = 12  # Comparar con mismo mes año anterior
    elif periodo_tipo == "Trimestral":
        df['periodo'] = df['trimestre']
        growth_lag_secuencial = 1  # Comparar con trimestre anterior
        growth_lag_yoy = 4  # Comparar con mismo trimestre año anterior
    elif periodo_tipo == "Anual":
        df['periodo'] = df['anio'].astype(str)
        growth_lag_secuencial = 1  # Comparar con año anterior
        growth_lag_yoy = 1  # Comparar con año anterior (mismo)
    elif periodo_tipo == "Rango Personalizado":
        with st.sidebar:
            start_date = st.date_input("📅 Fecha inicio:", value=df['fecha'].min())
            end_date = st.date_input("📅 Fecha fin:", value=df['fecha'].max())
        df = df[(df['fecha'] >= pd.to_datetime(start_date)) & (df['fecha'] <= pd.to_datetime(end_date))]
        df['periodo'] = "Rango Personalizado"
        growth_lag_secuencial = None
        growth_lag_yoy = None

    # Convertir a string antes de concatenar para evitar errores de tipo
    df['periodo_etiqueta'] = df['periodo_id'].astype(str) + " - " + df['periodo'].astype(str)
    df = df.sort_values('periodo_id')

    pivot_table = df.pivot_table(
        index='periodo_etiqueta',
        columns=columna_linea,
        values=columna_importe,
        aggfunc='sum',
        fill_value=0
    )

    period_id_lookup = df.drop_duplicates('periodo_etiqueta').set_index('periodo_etiqueta')['periodo_id']
    df_period_ids = period_id_lookup.reindex(pivot_table.index)

    lineas_disponibles = list(pivot_table.columns)

    selected_lineas = st.multiselect(
        "📌 Selecciona las líneas de negocio:",
        lineas_disponibles,
        default=lineas_disponibles
    )

    if selected_lineas:
        df_filtered = pivot_table.loc[:, selected_lineas]

        with st.sidebar:
            # Obtener min y max de forma segura
            valores_min = df_filtered.min().min()
            valores_max = df_filtered.max().max()
            
            # Validar que los valores sean válidos y diferentes
            if pd.notna(valores_min) and pd.notna(valores_max) and valores_min < valores_max:
                min_importe, max_importe = st.slider(
                    "💰 Filtro por importe ($):",
                    min_value=float(valores_min),
                    max_value=float(valores_max),
                    value=(float(valores_min), float(valores_max))
                )
            else:
                # Si no hay rango válido, usar valores por defecto
                min_importe = float(valores_min) if pd.notna(valores_min) else 0.0
                max_importe = float(valores_max) if pd.notna(valores_max) else 0.0
                st.sidebar.info("ℹ️ No hay rango de importes suficiente para filtrar")

            top_n = st.number_input(
                "🏅 Top N líneas de negocio:",
                min_value=1,
                max_value=len(selected_lineas),
                value=min(10, len(selected_lineas)),
                step=1
            )

        df_filtered = df_filtered.map(lambda x: x if min_importe <= x <= max_importe else np.nan)
        total_por_linea = df_filtered.sum(axis=0)
        top_lineas = total_por_linea.sort_values(ascending=False).head(top_n).index.tolist()
        df_filtered = df_filtered[top_lineas]

        def format_currency(value):
            if pd.notna(value):
                return f"${value:,.2f}"
            else:
                return ""

        annot_data = df_filtered.copy().astype(str)
        nuevas_lineas = set()

        if mostrar_crecimiento and growth_lag_secuencial:
            try:
                # Calcular crecimiento según tipo de comparación seleccionado
                df_growth = df_filtered.copy()
                
                # Ordenar por periodo_id para asegurar orden cronológico
                df_growth['periodo_id_num'] = df_period_ids.loc[df_filtered.index]
                df_growth = df_growth.sort_values('periodo_id_num')
                df_growth = df_growth.drop(columns='periodo_id_num')
                
                if periodo_tipo != "Rango Personalizado":
                    # Determinar el lag según tipo de comparación
                    if tipo_comparacion == "Período anterior":
                        lag = growth_lag_secuencial
                        comparacion_label = "vs período anterior"
                    else:  # "Mismo período año anterior"
                        lag = growth_lag_yoy
                        comparacion_label = "vs mismo período año anterior"
                    
                    # pct_change con el lag correspondiente
                    growth_table = df_growth.pct_change(periods=lag) * 100
                    growth_table = growth_table.loc[:, df_filtered.columns]
                else:
                    growth_table = None
                    comparacion_label = ""

                for row in annot_data.index:
                    for col in annot_data.columns:
                        val = df_filtered.loc[row, col]
                        growth = growth_table.loc[row, col] if growth_table is not None else np.nan
                        if pd.notna(val):
                            if pd.notna(growth) and not np.isinf(growth):
                                annot_data.loc[row, col] = f"{format_currency(val)}\n({growth:.1f}%)"
                            elif np.isinf(growth):
                                annot_data.loc[row, col] = f"{format_currency(val)}\nNEW"
                                nuevas_lineas.add(col)
                            else:
                                annot_data.loc[row, col] = f"{format_currency(val)}"

                if nuevas_lineas:
                    st.info(f"🟢 **Líneas con ventas nuevas o reiniciadas** ({comparacion_label}):")
                    for linea in sorted(nuevas_lineas):
                        st.markdown(f"- {linea}")

            except Exception as e:
                st.warning(f"⚠️ Error calculando crecimiento: {e}")
                annot_data = df_filtered.map(lambda x: format_currency(x))
        else:
            annot_data = df_filtered.map(lambda x: format_currency(x))

        fig, ax = plt.subplots(figsize=(max(10, len(top_lineas)*1.5), max(5, len(df_filtered.index)*0.6)))
        sns.heatmap(
            df_filtered,
            annot=False,
            fmt="",
            cmap="Greens",
            cbar_kws={'label': 'Importe ($)'},
            linewidths=0.5,
            linecolor='gray',
            ax=ax
        )

        norm = plt.Normalize(vmin=df_filtered.min().min(), vmax=df_filtered.max().max())

        for i in range(len(df_filtered.index)):
            for j in range(len(df_filtered.columns)):
                value = df_filtered.iloc[i, j]
                text = annot_data.iloc[i, j]

                if pd.notna(value):
                    intensity = norm(value)
                    if text == "NEW":
                        text_color = 'lime'
                    elif intensity > 0.6:
                        text_color = 'white'
                    else:
                        text_color = 'black'

                    ax.text(
                        j + 0.5, i + 0.5, text,
                        ha='center', va='center',
                        color=text_color,
                        fontsize=8
                    )

        ax.set_xlabel("Línea de Negocio", fontsize=12)
        ax.set_ylabel("Periodo", fontsize=12)
        ax.set_xticklabels(ax.get_xticklabels(), rotation=45, ha='right', fontsize=10)
        ax.set_yticklabels(ax.get_yticklabels(), rotation=0, fontsize=10)
        plt.title(f"Heatmap de Ventas ({periodo_tipo})", fontsize=14, pad=20)
        plt.tight_layout()
        st.pyplot(fig)

        # Pie chart de líneas de negocio más vendidas
        st.write("---")
        st.subheader("🥧 Ventas por Línea de Negocio")
        
        # Calcular ventas por línea de negocio
        ventas_linea = df.groupby(columna_linea)[columna_importe].sum().sort_values(ascending=False)
        
        # Top N + Otros
        top_n_lineas = st.slider("🔢 Número de líneas a mostrar:", min_value=5, max_value=20, value=10, step=1)
        
        if len(ventas_linea) > top_n_lineas:
            top_lineas_pie = ventas_linea.head(top_n_lineas)
            otros = ventas_linea.iloc[top_n_lineas:].sum()
            top_lineas_pie['Otros'] = otros
        else:
            top_lineas_pie = ventas_linea
        
        # Crear pie chart con Plotly
        fig_pie = go.Figure(data=[go.Pie(
            labels=top_lineas_pie.index.astype(str).tolist(),
            values=top_lineas_pie.values.tolist(),
            hole=0.4,
            textinfo='label+percent',
            textposition='auto',
            hovertemplate='<b>%{label}</b><br>Ventas: $%{value:,.2f}<br>%{percent}<extra></extra>'
        )])
        
        fig_pie.update_layout(
            title=f"Top {top_n_lineas} Líneas de Negocio por Ventas",
            height=500,
            showlegend=True,
            legend=dict(
                orientation="v",
                yanchor="middle",
                y=0.5,
                xanchor="left",
                x=1.05
            )
        )
        
        st.plotly_chart(fig_pie, width='stretch')
        
        # Mostrar tabla de resumen
        with st.expander("📋 Ver tabla de líneas de negocio"):
            df_lineas_tabla = pd.DataFrame({
                'Línea de Negocio': top_lineas_pie.index,
                'Ventas': top_lineas_pie.values
            })
            df_lineas_tabla['% del Total'] = (df_lineas_tabla['Ventas'] / ventas_linea.sum() * 100).round(2)
            df_lineas_tabla['Ventas'] = df_lineas_tabla['Ventas'].apply(lambda x: f"${x:,.2f}")
            df_lineas_tabla['% del Total'] = df_lineas_tabla['% del Total'].apply(lambda x: f"{x:.2f}%")
            st.dataframe(df_lineas_tabla, width='stretch', hide_index=True)

        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            df_filtered.to_excel(writer, sheet_name='Heatmap_Filtrado')
        buffer.seek(0)

        st.download_button(
            label="📥 Descargar tabla filtrada como Excel",
            data=buffer.getvalue(),
            file_name="heatmap_filtrado.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
