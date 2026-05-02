import streamlit as st
import pandas as pd
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
import plotly.graph_objects as go
import io
import logging
import unicodedata
from utils.auth import get_current_user

logger = logging.getLogger(__name__)

PARETO_TARGET_PCT = 80
LINEA_RELEVANTE_PCT = 10
DETALLE_BAR_COLOR = "#2f6b3f"
DETALLE_TREND_COLOR = "#2d7ff9"
DETALLE_TREND_MARKER_BORDER = "#f8fafc"

TITULOS_HEATMAP = {
    "sidebar": "⚙️ Configuración del heatmap",
    "segmentacion": "#### 1. Corte comercial",
    "temporal": "#### 2. Corte temporal",
    "visual": "#### 3. Visualización",
    "lectura_rapida": "### Lectura rápida",
    "ranking": "📊 Ranking y concentración de líneas",
    "pareto": "📈 Pareto de líneas",
    "detalle": "🔎 Detalle de línea",
}


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


def obtener_mapa_columnas():
    return {
        "linea": ["linea_prodcucto", "linea_producto", "linea_de_negocio", "linea producto", "linea_de_producto"],
        "importe": ["valor_usd", "ventas_usd", "importe"],
        "producto": ["producto", "articulo", "item", "descripcion", "producto_nombre", "producto nombre"],
        "cliente": ["cliente", "razon_social", "razon social", "deudor", "nombre_cliente", "nombre cliente"],
        "vendedor": ["vendedor", "agente", "ejecutivo", "vendedor_asignado", "vendedor asignado", "seller", "rep"],
    }


def preparar_dataframe_base(df):
    df = df.copy()
    df.columns = clean_columns(df.columns)

    if 'fecha' not in df.columns:
        return None, "❌ No se encontró la columna 'fecha' necesaria para construir el Heatmap de Ventas."

    df['fecha'] = pd.to_datetime(df['fecha'], errors='coerce')

    if df['fecha'].isna().all():
        return None, "❌ La columna 'fecha' no contiene valores válidos para construir el Heatmap de Ventas."

    df['mes_anio'] = df['fecha'].dt.strftime('%b-%Y')
    df['anio'] = df['fecha'].dt.year
    df['trimestre'] = df['fecha'].dt.to_period('Q').astype(str)
    return df, None


def resolver_columnas_clave(df):
    mapa_columnas = obtener_mapa_columnas()
    columna_linea = detectar_columna(df, mapa_columnas["linea"])
    columna_importe = detectar_columna(df, mapa_columnas["importe"])
    columna_producto = detectar_columna(df, mapa_columnas["producto"])
    columna_cliente = detectar_columna(df, mapa_columnas["cliente"])
    columna_vendedor = detectar_columna(df, mapa_columnas["vendedor"])
    return columna_linea, columna_importe, columna_producto, columna_cliente, columna_vendedor


def aplicar_filtros_comerciales(df, columna_cliente=None, columna_vendedor=None):
    df_filtrado = df.copy()

    with st.sidebar:
        st.markdown(TITULOS_HEATMAP["segmentacion"])
        st.caption("Recorta la vista por responsable o cuenta antes del análisis temporal.")

        if columna_vendedor is not None:
            vendedores_disponibles = sorted(df_filtrado[columna_vendedor].dropna().astype(str).unique().tolist())
            if vendedores_disponibles:
                vendedores_seleccionados = st.multiselect(
                    "👤 Filtrar por vendedor:",
                    vendedores_disponibles,
                    default=vendedores_disponibles,
                    key="heatmap_filtro_vendedor"
                )
                if vendedores_seleccionados:
                    df_filtrado = df_filtrado[df_filtrado[columna_vendedor].astype(str).isin(vendedores_seleccionados)]

        if columna_cliente is not None:
            clientes_disponibles = sorted(df_filtrado[columna_cliente].dropna().astype(str).unique().tolist())
            if clientes_disponibles:
                clientes_seleccionados = st.multiselect(
                    "🏢 Filtrar por cliente:",
                    clientes_disponibles,
                    default=clientes_disponibles,
                    key="heatmap_filtro_cliente"
                )
                if clientes_seleccionados:
                    df_filtrado = df_filtrado[df_filtrado[columna_cliente].astype(str).isin(clientes_seleccionados)]

    return df_filtrado


def construir_periodo_y_lags(df, periodo_tipo):
    df = df.copy()

    if periodo_tipo == "Mensual":
        df['periodo_inicio'] = df['fecha'].dt.to_period('M').dt.to_timestamp()
        df['periodo_id'] = df['periodo_inicio'].dt.strftime('%y.%m')
        df['periodo'] = df['mes_anio']
        growth_lag_secuencial = 1
        growth_lag_yoy = 12
    elif periodo_tipo == "Trimestral":
        df['periodo_inicio'] = df['fecha'].dt.to_period('Q').dt.start_time
        df['periodo_id'] = (
            df['periodo_inicio'].dt.strftime('%y')
            + '.Q'
            + df['periodo_inicio'].dt.quarter.astype(str)
        )
        df['periodo'] = df['trimestre']
        growth_lag_secuencial = 1
        growth_lag_yoy = 4
    elif periodo_tipo == "Anual":
        df['periodo_inicio'] = df['fecha'].dt.to_period('Y').dt.to_timestamp()
        df['periodo_id'] = df['periodo_inicio'].dt.strftime('%y')
        df['periodo'] = df['anio'].astype(str)
        growth_lag_secuencial = 1
        growth_lag_yoy = 1
    else:
        fecha_inicio_rango = df['fecha'].min().normalize()
        df['periodo_inicio'] = fecha_inicio_rango
        df['periodo_id'] = fecha_inicio_rango.strftime('%y.%m')
        df['periodo'] = "Rango Personalizado"
        growth_lag_secuencial = None
        growth_lag_yoy = None

    return df, growth_lag_secuencial, growth_lag_yoy


def construir_tabla_pivot(df, columna_linea, columna_importe):
    pivot_table = df.pivot_table(
        index='periodo_etiqueta',
        columns=columna_linea,
        values=columna_importe,
        aggfunc='sum',
        fill_value=0
    )

    period_order_lookup = df.drop_duplicates('periodo_etiqueta').set_index('periodo_etiqueta')['periodo_inicio']
    df_period_order = period_order_lookup.reindex(pivot_table.index)
    return pivot_table, df_period_order


def obtener_offset_comparacion(periodo_tipo, tipo_comparacion):
    if tipo_comparacion == "Período anterior":
        if periodo_tipo == "Mensual":
            return pd.DateOffset(months=1), "vs período anterior"
        if periodo_tipo == "Trimestral":
            return pd.DateOffset(months=3), "vs período anterior"
        return pd.DateOffset(years=1), "vs período anterior"

    return pd.DateOffset(years=1), "vs mismo período año anterior"


def calcular_tabla_crecimiento(df_filtered, df_period_order, periodo_tipo, tipo_comparacion):
    offset, comparacion_label = obtener_offset_comparacion(periodo_tipo, tipo_comparacion)

    periodos_ordenados = df_period_order.loc[df_filtered.index].sort_values()
    etiquetas_ordenadas = periodos_ordenados.index.tolist()
    etiqueta_por_periodo = {periodo: etiqueta for etiqueta, periodo in periodos_ordenados.items()}

    growth_table = pd.DataFrame(index=etiquetas_ordenadas, columns=df_filtered.columns, dtype=float)
    status_table = pd.DataFrame(index=etiquetas_ordenadas, columns=df_filtered.columns, dtype=object)

    for etiqueta_actual in etiquetas_ordenadas:
        periodo_actual = df_period_order.loc[etiqueta_actual]
        if pd.isna(periodo_actual):
            continue

        periodo_base = periodo_actual - offset
        etiqueta_base = etiqueta_por_periodo.get(periodo_base)

        if etiqueta_base is None:
            status_table.loc[etiqueta_actual] = 'sin_comparable'
            continue

        valores_actuales = df_filtered.loc[etiqueta_actual]
        valores_base = df_filtered.loc[etiqueta_base]

        base_limpia = valores_base.replace(0, np.nan)
        crecimiento = ((valores_actuales - valores_base) / base_limpia) * 100

        crecimiento[(valores_base == 0) & (valores_actuales > 0)] = np.inf
        crecimiento[(valores_base == 0) & (valores_actuales == 0)] = np.nan
        growth_table.loc[etiqueta_actual] = crecimiento

        estados = pd.Series('comparable', index=df_filtered.columns, dtype=object)
        estados[(valores_base == 0) & (valores_actuales > 0)] = 'nuevo'
        estados[(valores_base == 0) & (valores_actuales == 0)] = 'sin_actividad'
        status_table.loc[etiqueta_actual] = estados

    return growth_table.reindex(df_filtered.index), status_table.reindex(df_filtered.index), comparacion_label


def construir_resumen_heatmap(df_filtered, growth_table=None):
    total_visible = np.nansum(df_filtered.to_numpy(dtype=float))
    periodos_visibles = len(df_filtered.index)
    lineas_visibles = len(df_filtered.columns)
    ultimo_periodo = df_filtered.index[-1] if periodos_visibles else None

    ventas_por_linea = df_filtered.sum(axis=0).sort_values(ascending=False)
    linea_lider = ventas_por_linea.index[0] if not ventas_por_linea.empty else None
    ventas_linea_lider = ventas_por_linea.iloc[0] if not ventas_por_linea.empty else None

    mejor_linea = None
    mejor_crecimiento = None
    if growth_table is not None and ultimo_periodo is not None:
        crecimiento_ultimo = growth_table.loc[ultimo_periodo].replace([np.inf, -np.inf], np.nan).dropna()
        if not crecimiento_ultimo.empty:
            mejor_linea = crecimiento_ultimo.idxmax()
            mejor_crecimiento = crecimiento_ultimo.max()

    return {
        "total_visible": total_visible,
        "periodos_visibles": periodos_visibles,
        "lineas_visibles": lineas_visibles,
        "ultimo_periodo": ultimo_periodo,
        "linea_lider": linea_lider,
        "ventas_linea_lider": ventas_linea_lider,
        "mejor_linea": mejor_linea,
        "mejor_crecimiento": mejor_crecimiento,
    }


def format_currency(value):
    if pd.notna(value):
        return f"${value:,.2f}"
    return ""


def calcular_metricas_concentracion(ventas_linea):
    total_ventas = ventas_linea.sum()
    if total_ventas == 0:
        return 0, 0, 0

    top_1_share = (ventas_linea.head(1).sum() / total_ventas) * 100
    top_3_share = (ventas_linea.head(min(3, len(ventas_linea))).sum() / total_ventas) * 100
    lineas_relevantes = int((ventas_linea / total_ventas * 100 >= LINEA_RELEVANTE_PCT).sum())
    return top_1_share, top_3_share, lineas_relevantes


def construir_pareto_dataframe(ventas_linea):
    pareto_df = pd.DataFrame({
        'linea': ventas_linea.index.astype(str),
        'ventas': ventas_linea.values,
    })
    pareto_df['participacion_pct'] = (pareto_df['ventas'] / pareto_df['ventas'].sum() * 100)
    pareto_df['acumulado_pct'] = pareto_df['participacion_pct'].cumsum()
    return pareto_df


def resumir_pareto(pareto_df):
    lineas_objetivo = int((pareto_df['acumulado_pct'] < PARETO_TARGET_PCT).sum() + 1)
    lineas_objetivo = min(lineas_objetivo, len(pareto_df))
    cobertura_objetivo = pareto_df.iloc[lineas_objetivo - 1]['acumulado_pct'] if not pareto_df.empty else 0
    return lineas_objetivo, cobertura_objetivo

def run(df):
    st.title("🔥 Heatmap de Ventas por Línea de Negocio")
    st.caption(
        "Vista de concentración y evolución por período. Úsala para detectar líneas dominantes,"
        " rebotes y caídas en la secuencia temporal seleccionada."
    )

    df, error_preparacion = preparar_dataframe_base(df)
    if error_preparacion:
        st.error(error_preparacion)
        if df is not None:
            st.write(f"Columnas detectadas en tu archivo: {df.columns.tolist()}")
        return

    columna_linea, columna_importe, columna_producto, columna_cliente, columna_vendedor = resolver_columnas_clave(df)

    if columna_linea is None or columna_importe is None:
        st.error("❌ No se encontraron las columnas clave necesarias para 'línea' e 'importe'.")
        st.write(f"Columnas detectadas en tu archivo: {df.columns.tolist()}")
        return

    df = aplicar_filtros_comerciales(
        df,
        columna_cliente=columna_cliente,
        columna_vendedor=columna_vendedor,
    )

    if df.empty:
        st.warning("⚠️ Los filtros comerciales dejaron la vista sin registros para analizar.")
        return

    with st.sidebar:
        st.header(TITULOS_HEATMAP["sidebar"])
        st.markdown(TITULOS_HEATMAP["temporal"])
        st.caption("Define el horizonte de lectura y la base de comparación.")
        periodo_tipo = st.selectbox(
            "🗓️ Tipo de periodo:",
            ["Mensual", "Trimestral", "Anual", "Rango Personalizado"],
            key="heatmap_periodo_tipo"
        )
        mostrar_crecimiento = st.checkbox("📈 Mostrar % de crecimiento", key="heatmap_mostrar_crecimiento")
        
        if mostrar_crecimiento:
            tipo_comparacion = st.radio(
                "Comparar contra:",
                ["Período anterior", "Mismo período año anterior"],
                help="Período anterior: mes vs mes previo, trimestre vs trimestre previo, etc.\nMismo período año anterior: ene-24 vs ene-23, Q1-24 vs Q1-23, etc.",
                key="heatmap_tipo_comparacion"
            )

        if periodo_tipo == "Rango Personalizado":
            start_date = st.date_input("📅 Fecha inicio:", value=df['fecha'].min(), key="heatmap_fecha_inicio")
            end_date = st.date_input("📅 Fecha fin:", value=df['fecha'].max(), key="heatmap_fecha_fin")
        else:
            start_date = None
            end_date = None

    if periodo_tipo == "Rango Personalizado":
        df = df[(df['fecha'] >= pd.to_datetime(start_date)) & (df['fecha'] <= pd.to_datetime(end_date))]

    df, growth_lag_secuencial, growth_lag_yoy = construir_periodo_y_lags(df, periodo_tipo)

    # Convertir a string antes de concatenar para evitar errores de tipo
    df['periodo_etiqueta'] = df['periodo_id'].astype(str) + " - " + df['periodo'].astype(str)
    df = df.sort_values('periodo_inicio')

    pivot_table, df_period_order = construir_tabla_pivot(df, columna_linea, columna_importe)

    lineas_disponibles = list(pivot_table.columns)

    with st.sidebar:
        st.markdown(TITULOS_HEATMAP["visual"])
        st.caption("Ajusta el recorte visible que alimenta heatmap, ranking, Pareto y detalle.")
        selected_lineas = st.multiselect(
            "📌 Líneas visibles:",
            lineas_disponibles,
            default=lineas_disponibles,
            key="heatmap_lineas_seleccionadas"
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
                    "💰 Rango visible por importe ($):",
                    min_value=float(valores_min),
                    max_value=float(valores_max),
                    value=(float(valores_min), float(valores_max)),
                    key="heatmap_slider_importe"
                )
            else:
                # Si no hay rango válido, usar valores por defecto
                min_importe = float(valores_min) if pd.notna(valores_min) else 0.0
                max_importe = float(valores_max) if pd.notna(valores_max) else 0.0
                st.sidebar.info("ℹ️ No hay rango de importes suficiente para filtrar")

            top_n = st.number_input(
                "🏅 Máximo de líneas en heatmap:",
                min_value=1,
                max_value=len(selected_lineas),
                value=min(10, len(selected_lineas)),
                step=1,
                key="heatmap_top_n"
            )

        df_filtered = df_filtered.map(lambda x: x if min_importe <= x <= max_importe else np.nan)
        total_por_linea = df_filtered.sum(axis=0)
        top_lineas = total_por_linea.sort_values(ascending=False).head(top_n).index.tolist()
        df_filtered = df_filtered[top_lineas]

        annot_data = df_filtered.copy().astype(str)
        nuevas_lineas = set()
        lineas_sin_base = set()
        growth_table = None
        status_table = None
        comparacion_label = ""

        if mostrar_crecimiento and growth_lag_secuencial:
            try:
                if periodo_tipo != "Rango Personalizado":
                    growth_table, status_table, comparacion_label = calcular_tabla_crecimiento(
                        df_filtered,
                        df_period_order,
                        periodo_tipo,
                        tipo_comparacion
                    )
                else:
                    growth_table = None
                    status_table = None
                    comparacion_label = ""

                for row in annot_data.index:
                    for col in annot_data.columns:
                        val = df_filtered.loc[row, col]
                        growth = growth_table.loc[row, col] if growth_table is not None else np.nan
                        status = status_table.loc[row, col] if status_table is not None else None
                        if pd.notna(val):
                            if status == 'comparable' and pd.notna(growth) and not np.isinf(growth):
                                annot_data.loc[row, col] = f"{format_currency(val)}\n({growth:.1f}%)"
                            elif status == 'nuevo' or np.isinf(growth):
                                annot_data.loc[row, col] = f"{format_currency(val)}\nNuevo"
                                nuevas_lineas.add(col)
                            elif status == 'sin_comparable':
                                annot_data.loc[row, col] = f"{format_currency(val)}\nSin base"
                                lineas_sin_base.add(col)
                            else:
                                annot_data.loc[row, col] = f"{format_currency(val)}"

                if nuevas_lineas:
                    st.info(f"🟢 **Líneas con ventas nuevas** ({comparacion_label}):")
                    for linea in sorted(nuevas_lineas):
                        st.markdown(f"- {linea}")

                if lineas_sin_base:
                    st.info(f"ℹ️ **Líneas sin base comparable disponible** ({comparacion_label}):")
                    for linea in sorted(lineas_sin_base):
                        st.markdown(f"- {linea}")

            except Exception as e:
                st.warning(f"⚠️ Error calculando crecimiento: {e}")
                annot_data = df_filtered.map(lambda x: format_currency(x))
        else:
            annot_data = df_filtered.map(lambda x: format_currency(x))

        resumen = construir_resumen_heatmap(df_filtered, growth_table)
        st.write(TITULOS_HEATMAP["lectura_rapida"])
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Ventas visibles", format_currency(resumen["total_visible"]))
        col2.metric("Períodos visibles", f"{resumen['periodos_visibles']}")
        col3.metric(
            "Línea líder",
            resumen["linea_lider"] or "N/D",
            format_currency(resumen["ventas_linea_lider"]) if resumen["ventas_linea_lider"] is not None else None
        )
        if resumen["mejor_linea"] is not None and resumen["mejor_crecimiento"] is not None:
            col4.metric(
                "Mayor crecimiento comparable",
                resumen["mejor_linea"],
                f"{resumen['mejor_crecimiento']:.1f}%"
            )
        else:
            col4.metric("Mayor crecimiento comparable", "N/D")

        if resumen["ultimo_periodo"]:
            st.caption(
                f"Último período visible: {resumen['ultimo_periodo']}"
                + (f" | Comparación activa: {comparacion_label}" if comparacion_label else "")
            )

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
                    if "Nuevo" in text:
                        text_color = 'lime'
                    elif "Sin base" in text:
                        text_color = '#1f3c5c'
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
        st.pyplot(fig, clear_figure=True)
        plt.close(fig)

        st.write("---")
        st.subheader(TITULOS_HEATMAP["ranking"])
        st.caption(
            "Esta vista complementa al heatmap con magnitud comparable entre líneas."
            " Evita la distorsión visual del gráfico circular y mantiene el foco en el peso comercial real."
        )

        ventas_linea = df_filtered.sum(axis=0).sort_values(ascending=False)
        total_lineas_disponibles = len(ventas_linea)

        if total_lineas_disponibles == 0 or ventas_linea.sum() == 0:
            st.info("No hay datos visibles para construir el ranking comercial.")
        else:
            max_lineas_ranking = min(15, total_lineas_disponibles)
            valor_inicial_ranking = min(8, total_lineas_disponibles)

            if total_lineas_disponibles > 3:
                top_n_lineas = st.slider(
                    "🔢 Número de líneas a mostrar:",
                    min_value=3,
                    max_value=max_lineas_ranking,
                    value=max(3, valor_inicial_ranking),
                    step=1,
                    key="heatmap_ranking_top_n"
                )
            else:
                top_n_lineas = total_lineas_disponibles
                st.caption(f"Mostrando las {total_lineas_disponibles} líneas visibles")

            top_lineas_ranking = ventas_linea.head(top_n_lineas).sort_values(ascending=True)
            participacion_linea = (top_lineas_ranking / ventas_linea.sum() * 100)
            participacion_acumulada = participacion_linea.cumsum()

            top_1_share, top_3_share, lineas_relevantes = calcular_metricas_concentracion(ventas_linea)

            conc1, conc2, conc3 = st.columns(3)
            conc1.metric("Concentración Top 1", f"{top_1_share:.1f}%")
            conc2.metric("Concentración Top 3", f"{top_3_share:.1f}%")
            conc3.metric(f"Líneas con peso > {LINEA_RELEVANTE_PCT}%", f"{lineas_relevantes}")

            fig_rank = go.Figure()
            fig_rank.add_trace(go.Bar(
                x=top_lineas_ranking.values.tolist(),
                y=top_lineas_ranking.index.astype(str).tolist(),
                orientation='h',
                marker=dict(color=participacion_linea.values.tolist(), colorscale='Greens'),
                text=[f"{value:,.0f}" for value in top_lineas_ranking.values.tolist()],
                textposition='outside',
                customdata=np.column_stack([
                    participacion_linea.values,
                    participacion_acumulada.values,
                ]),
                hovertemplate=(
                    '<b>%{y}</b><br>'
                    'Ventas: $%{x:,.2f}<br>'
                    'Participación: %{customdata[0]:.1f}%<br>'
                    'Participación acumulada: %{customdata[1]:.1f}%<extra></extra>'
                )
            ))

            fig_rank.update_layout(
                title=f"Top {top_n_lineas} líneas por ventas visibles",
                height=max(420, top_n_lineas * 40),
                xaxis_title="Ventas visibles ($)",
                yaxis_title="Línea de negocio",
                margin=dict(l=20, r=20, t=60, b=20),
                coloraxis_showscale=False,
            )

            st.plotly_chart(fig_rank, use_container_width=True)

            with st.expander("📋 Ver tabla de concentración"):
                df_lineas_tabla = pd.DataFrame({
                    'Línea de Negocio': ventas_linea.index,
                    'Ventas': ventas_linea.values,
                })
                df_lineas_tabla['% del Total'] = (df_lineas_tabla['Ventas'] / ventas_linea.sum() * 100).round(2)
                df_lineas_tabla['% Acumulado'] = df_lineas_tabla['% del Total'].cumsum().round(2)
                df_lineas_tabla['Ventas'] = df_lineas_tabla['Ventas'].apply(lambda x: f"${x:,.2f}")
                df_lineas_tabla['% del Total'] = df_lineas_tabla['% del Total'].apply(lambda x: f"{x:.2f}%")
                df_lineas_tabla['% Acumulado'] = df_lineas_tabla['% Acumulado'].apply(lambda x: f"{x:.2f}%")
                st.dataframe(df_lineas_tabla, use_container_width=True, hide_index=True)

            st.write("---")
            st.subheader(TITULOS_HEATMAP["pareto"])
            st.caption(
                "Muestra cuántas líneas explican la mayor parte de las ventas visibles."
                " Es la vista correcta para detectar concentración comercial real."
            )

            pareto_df = construir_pareto_dataframe(ventas_linea)
            lineas_80, cobertura_80 = resumir_pareto(pareto_df)

            st.info(
                f"📌 **{lineas_80} líneas** explican **{cobertura_80:.1f}%** de las ventas visibles."
            )

            fig_pareto = go.Figure()
            fig_pareto.add_trace(go.Bar(
                x=pareto_df['linea'].tolist(),
                y=pareto_df['ventas'].tolist(),
                name='Ventas visibles',
                marker_color='#5c8f6a',
                hovertemplate='<b>%{x}</b><br>Ventas: $%{y:,.2f}<extra></extra>'
            ))
            fig_pareto.add_trace(go.Scatter(
                x=pareto_df['linea'].tolist(),
                y=pareto_df['acumulado_pct'].tolist(),
                name='% acumulado',
                mode='lines+markers',
                line=dict(color='#f1c40f', width=3),
                marker=dict(color='#f1c40f'),
                yaxis='y2',
                hovertemplate='<b>%{x}</b><br>Acumulado: %{y:.1f}%<extra></extra>'
            ))
            fig_pareto.add_trace(go.Scatter(
                x=pareto_df['linea'].tolist(),
                y=[PARETO_TARGET_PCT] * len(pareto_df),
                name=f'Referencia {PARETO_TARGET_PCT}%',
                mode='lines',
                line=dict(color='#b03a2e', width=2, dash='dash'),
                yaxis='y2',
                hoverinfo='skip'
            ))

            fig_pareto.update_layout(
                title='Concentración acumulada por línea visible',
                height=460,
                xaxis_title='Línea de negocio',
                yaxis=dict(title='Ventas visibles ($)'),
                yaxis2=dict(
                    title='% acumulado',
                    overlaying='y',
                    side='right',
                    range=[0, 105]
                ),
                legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='left', x=0),
                margin=dict(l=20, r=20, t=60, b=80)
            )

            st.plotly_chart(fig_pareto, use_container_width=True)

            st.write("---")
            st.subheader(TITULOS_HEATMAP["detalle"])
            st.caption(
                "Permite bajar del mapa general a una lectura puntual por línea usando exactamente"
                " el mismo recorte visible del heatmap."
            )

            linea_detalle = st.selectbox(
                "Selecciona una línea para revisar su secuencia:",
                ventas_linea.index.tolist(),
                key="heatmap_linea_detalle"
            )

            serie_linea = df_filtered[linea_detalle].dropna()

            if not serie_linea.empty:
                total_linea = float(serie_linea.sum())
                participacion_linea_total = (total_linea / ventas_linea.sum()) * 100 if ventas_linea.sum() else 0
                mejor_periodo_linea = serie_linea.idxmax()
                mejor_valor_linea = float(serie_linea.max())
                ultimo_periodo_linea = serie_linea.index[-1]
                ultimo_valor_linea = float(serie_linea.iloc[-1])

                ultimo_crecimiento_linea = None
                if growth_table is not None and linea_detalle in growth_table.columns:
                    crecimiento_linea = growth_table[linea_detalle].replace([np.inf, -np.inf], np.nan).dropna()
                    if not crecimiento_linea.empty:
                        ultimo_crecimiento_linea = float(crecimiento_linea.iloc[-1])

                d1, d2, d3, d4 = st.columns(4)
                d1.metric("Ventas visibles línea", format_currency(total_linea))
                d2.metric("Participación visible", f"{participacion_linea_total:.1f}%")
                d3.metric("Pico del período", format_currency(mejor_valor_linea), mejor_periodo_linea)
                if ultimo_crecimiento_linea is not None:
                    d4.metric("Último crecimiento comparable", f"{ultimo_crecimiento_linea:.1f}%", ultimo_periodo_linea)
                else:
                    d4.metric("Último período visible", format_currency(ultimo_valor_linea), ultimo_periodo_linea)

                fig_detalle = go.Figure()
                fig_detalle.add_trace(go.Bar(
                    x=serie_linea.index.astype(str).tolist(),
                    y=serie_linea.values.tolist(),
                    name="Ventas",
                    marker_color=DETALLE_BAR_COLOR,
                    hovertemplate='<b>%{x}</b><br>Ventas: $%{y:,.2f}<extra></extra>'
                ))
                fig_detalle.add_trace(go.Scatter(
                    x=serie_linea.index.astype(str).tolist(),
                    y=serie_linea.values.tolist(),
                    name="Tendencia visible",
                    mode='lines+markers',
                    line=dict(color=DETALLE_TREND_COLOR, width=4),
                    marker=dict(
                        color=DETALLE_TREND_COLOR,
                        size=8,
                        symbol="diamond",
                        line=dict(color=DETALLE_TREND_MARKER_BORDER, width=1.5)
                    ),
                    hoverinfo='skip'
                ))

                fig_detalle.update_layout(
                    title=f"Secuencia visible de {linea_detalle}",
                    height=420,
                    xaxis_title="Período",
                    yaxis_title="Ventas ($)",
                    margin=dict(l=20, r=20, t=60, b=20),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0)
                )

                st.plotly_chart(fig_detalle, use_container_width=True)

                with st.expander("📄 Ver tabla del detalle seleccionado"):
                    df_detalle_linea = pd.DataFrame({
                        'Período': serie_linea.index,
                        'Ventas': serie_linea.values,
                    })
                    df_detalle_linea['Ventas'] = df_detalle_linea['Ventas'].apply(lambda x: f"${x:,.2f}")
                    st.dataframe(df_detalle_linea, use_container_width=True, hide_index=True)

        user = get_current_user()
        puede_exportar = user and user.can_export()
        
        if puede_exportar:        
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
        else:
            st.warning("⚠️ Las funciones de exportación están disponibles solo para usuarios con rol **Analyst** o **Admin**")
            st.info("💡 Contacta al administrador para solicitar acceso")
