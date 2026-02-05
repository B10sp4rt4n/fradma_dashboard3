"""
Módulo: Reporte YTD (Year-to-Date) por Línea de Negocio
Autor: Dashboard Fradma
Fecha: Enero 2026

Funcionalidad:
- Análisis de ventas acumuladas del año en curso por línea de negocio
- Comparación con año anterior
- Visualizaciones interactivas de alto impacto
- Exportación a Excel y PDF
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, date
import io
from utils.logger import configurar_logger

# Configurar logger para este módulo
logger = configurar_logger("ytd_lineas", nivel="INFO")

# Paleta de colores base
_COLORES_BASE = {
    'Ultra Plast': '#1f77b4',   # Azul vibrante
    'Dykem': '#ff7f0e',         # Naranja brillante
    'ACMOS': '#2ca02c',         # Verde intenso
    'Repi': '#d62728',          # Rojo fuerte
    'Schutze': '#9467bd',       # Púrpura
    'EZ-KOTE': '#8c564b',       # Café
    'Kemiekote': '#e377c2',     # Rosa
    'Otro.Ing': '#7f7f7f',      # Gris medio
    'Franklynn': '#bcbd22',     # Verde lima
    'Otro': '#17becf',          # Cian
    'LPS': '#ff1493',           # Rosa fuerte (Deep Pink)
    'X-Trimkote': '#00bfff',    # Azul cielo
    'Glo-Mold': '#ffa500',      # Naranja dorado
    'ZERUST': '#9400d3',        # Violeta oscuro
    'OKS': '#32cd32',           # Verde lima brillante
    'CARMEL': '#ff6347',        # Tomate
    'Health Care': '#4169e1',   # Azul real
    'Otros': '#696969'          # Gris oscuro
}

# Generar diccionario robusto (insensible a mayúsculas/minúsculas)
COLORES_LINEAS = _COLORES_BASE.copy()
for k, v in _COLORES_BASE.items():
    COLORES_LINEAS[k.lower()] = v
    COLORES_LINEAS[k.upper()] = v
    # Casos especiales
    if ' ' in k:
        COLORES_LINEAS[k.replace(' ', '-').lower()] = v
        COLORES_LINEAS[k.replace('-', ' ').lower()] = v

def calcular_ytd(df, año, fecha_corte=None):
    """
    Calcula ventas YTD hasta una fecha específica.
    
    Args:
        df: DataFrame con columnas 'fecha' y 'ventas_usd'
        año: Año a analizar
        fecha_corte: Fecha límite (si None, usa fecha actual)
    
    Returns:
        DataFrame filtrado con ventas YTD
    """
    if fecha_corte is None:
        fecha_corte = datetime.now()
    
    # Filtrar año y hasta fecha de corte
    df_año = df[df['fecha'].dt.year == año].copy()
    df_ytd = df_año[df_año['fecha'] <= fecha_corte].copy()
    
    # Logging para debug
    total_registros_año = len(df_año)
    total_registros_ytd = len(df_ytd)
    total_ventas = df_ytd['ventas_usd'].sum()
    
    logger.info(f"calcular_ytd() - Año: {año}, Fecha corte: {fecha_corte.strftime('%Y-%m-%d')}")
    logger.info(f"  Registros totales del año {año}: {total_registros_año}")
    logger.info(f"  Registros YTD hasta {fecha_corte.strftime('%Y-%m-%d')}: {total_registros_ytd}")
    logger.info(f"  Total ventas YTD: ${total_ventas:,.2f}")
    
    if total_registros_ytd > 0:
        fecha_min = df_ytd['fecha'].min()
        fecha_max = df_ytd['fecha'].max()
        logger.info(f"  Rango de fechas: {fecha_min.strftime('%Y-%m-%d')} a {fecha_max.strftime('%Y-%m-%d')}")
    
    return df_ytd

def calcular_metricas_ytd(df_ytd):
    """Calcula métricas agregadas YTD."""
    total_ytd = df_ytd['ventas_usd'].sum()
    dias_transcurridos = (datetime.now() - datetime(datetime.now().year, 1, 1)).days + 1
    promedio_diario = total_ytd / dias_transcurridos if dias_transcurridos > 0 else 0
    proyeccion_anual = promedio_diario * 365
    
    return {
        'total_ytd': total_ytd,
        'dias_transcurridos': dias_transcurridos,
        'promedio_diario': promedio_diario,
        'proyeccion_anual': proyeccion_anual
    }

def crear_grafico_lineas_acumulado(df, año_actual, año_anterior=None):
    """
    Crea gráfico de líneas con ventas acumuladas por mes.
    
    Args:
        df: DataFrame con datos de ventas
        año_actual: Año principal a mostrar
        año_anterior: Año para comparación (opcional)
    
    Returns:
        Figura de Plotly
    """
    fig = go.Figure()
    
    # Datos año actual
    df_actual = df[df['fecha'].dt.year == año_actual].copy()
    df_actual['mes'] = df_actual['fecha'].dt.month
    
    # Agrupar por línea y mes
    for linea in df_actual['linea_de_negocio'].unique():
        df_linea = df_actual[df_actual['linea_de_negocio'] == linea]
        ventas_mes = df_linea.groupby('mes')['ventas_usd'].sum().sort_index()
        ventas_acumuladas = ventas_mes.cumsum()
        
        color = COLORES_LINEAS.get(linea, '#808080')
        logger.info(f"YTD Gráfico - Línea: '{linea}' -> Color asignado: {color}")
        
        fig.add_trace(go.Scatter(
            x=ventas_acumuladas.index,
            y=ventas_acumuladas.values,
            mode='lines+markers',
            name=f"{linea} {año_actual}",
            line=dict(color=color, width=6),
            marker=dict(size=14, color=color, line=dict(width=3, color='white')),
            hovertemplate='<b>%{fullData.name}</b><br>' +
                         'Mes: %{x}<br>' +
                         'Acumulado: $%{y:,.2f}<extra></extra>',
            visible=True
        ))
    
    # Datos año anterior si existe
    if año_anterior:
        df_anterior = df[df['fecha'].dt.year == año_anterior].copy()
        df_anterior['mes'] = df_anterior['fecha'].dt.month
        
        for linea in df_anterior['linea_de_negocio'].unique():
            df_linea = df_anterior[df_anterior['linea_de_negocio'] == linea]
            ventas_mes = df_linea.groupby('mes')['ventas_usd'].sum().sort_index()
            ventas_acumuladas = ventas_mes.cumsum()
            
            color = COLORES_LINEAS.get(linea, '#808080')
            
            fig.add_trace(go.Scatter(
                x=ventas_acumuladas.index,
                y=ventas_acumuladas.values,
                mode='lines+markers',
                name=f"{linea} {año_anterior}",
                line=dict(color=color, width=2.5, dash='dot'),
                marker=dict(size=6, color=color, symbol='diamond'),
                opacity=0.7,
                hovertemplate='<b>%{fullData.name}</b><br>' +
                             'Mes: %{x}<br>' +
                             'Acumulado: $%{y:,.2f}<extra></extra>'
            ))
    
    fig.update_layout(
        title={
            'text': f'<b>Ventas Acumuladas YTD - Año {año_actual}</b>',
            'x': 0.5,
            'xanchor': 'center',
            'font': {'size': 20}
        },
        xaxis_title='Mes',
        yaxis_title='Ventas USD Acumuladas',
        hovermode='x unified',
        height=500,
        template=None,
        paper_bgcolor='white',
        plot_bgcolor='white',
        legend=dict(
            orientation="v",
            yanchor="top",
            y=1,
            xanchor="left",
            x=1.05
        ),
        xaxis=dict(
            tickmode='array',
            tickvals=list(range(1, 13)),
            ticktext=['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 
                     'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'],
            gridcolor='lightgray',
            showgrid=True
        ),
        yaxis=dict(
            gridcolor='lightgray',
            showgrid=True
        )
    )
    
    return fig

def crear_grafico_barras_comparativo(df, año_actual, año_anterior, usar_año_completo_anterior=True):
    """
    Crea gráfico de barras comparando año actual vs anterior por línea.
    
    Args:
        df: DataFrame con datos
        año_actual: Año en curso
        año_anterior: Año anterior para comparar
        usar_año_completo_anterior: Si True, usa todo el año anterior. Si False, usa YTD del año anterior
    """
    
    # Calcular YTD para año actual
    fecha_corte = datetime.now()
    df_actual = calcular_ytd(df, año_actual, fecha_corte)
    
    # Para año anterior: usar año completo o YTD según parámetro
    if usar_año_completo_anterior:
        # Usar TODO el año anterior completo (hasta 31 de diciembre)
        fecha_corte_anterior = datetime(año_anterior, 12, 31)
        logger.info(f"Comparativo - Año {año_actual} YTD vs Año {año_anterior} COMPLETO")
    else:
        # Usar YTD del año anterior (misma fecha que año actual)
        mes_actual = fecha_corte.month
        dia_actual = fecha_corte.day
        try:
            fecha_corte_anterior = datetime(año_anterior, mes_actual, dia_actual)
        except ValueError:
            fecha_corte_anterior = datetime(año_anterior, mes_actual, 28)
            logger.warning(f"Ajustando fecha de corte anterior a {fecha_corte_anterior}")
        logger.info(f"Comparativo YTD - Ambos años hasta misma fecha del calendario")
    
    logger.info(f"Fecha corte actual: {fecha_corte.strftime('%Y-%m-%d')}, anterior: {fecha_corte_anterior.strftime('%Y-%m-%d')}")
    
    df_anterior = calcular_ytd(df, año_anterior, fecha_corte_anterior)
    
    logger.info(f"Registros - Año {año_actual}: {len(df_actual)}, Año {año_anterior}: {len(df_anterior)}")
    logger.info(f"Total ventas - Año {año_actual}: ${df_actual['ventas_usd'].sum():,.2f}, Año {año_anterior}: ${df_anterior['ventas_usd'].sum():,.2f}")
    
    # Agrupar por línea
    ventas_actual = df_actual.groupby('linea_de_negocio')['ventas_usd'].sum().reset_index()
    ventas_actual.columns = ['linea_de_negocio', 'ventas_actual']
    
    ventas_anterior = df_anterior.groupby('linea_de_negocio')['ventas_usd'].sum().reset_index()
    ventas_anterior.columns = ['linea_de_negocio', 'ventas_anterior']
    
    # Merge
    comparativo = ventas_actual.merge(ventas_anterior, on='linea_de_negocio', how='outer').fillna(0)
    
    # Calcular crecimiento manejando casos especiales
    def calcular_crecimiento_seguro(row):
        actual = row['ventas_actual']
        anterior = row['ventas_anterior']
        
        if anterior == 0:
            if actual == 0:
                return 0.0  # Sin ventas en ambos períodos
            else:
                return 100.0  # Nueva línea o crecimiento desde cero
        else:
            return ((actual - anterior) / anterior) * 100
    
    comparativo['crecimiento'] = comparativo.apply(calcular_crecimiento_seguro, axis=1)
    
    # Log de resumen para debugging
    logger.debug(f"Comparativo generado con {len(comparativo)} líneas de negocio")
    
    # Crear lista de colores en el orden correcto
    colores = [COLORES_LINEAS.get(linea, '#808080') for linea in comparativo['linea_de_negocio']]
    
    # Crear figura con dos trazas: año anterior y año actual
    fig = go.Figure()
    
    # Barra año anterior - todos los datos
    label_anterior = f"Año {año_anterior}" + (" (Completo)" if usar_año_completo_anterior else " (YTD)")
    label_actual = f"Año {año_actual} (YTD)"
    
    fig.add_trace(go.Bar(
        name=label_anterior,
        x=comparativo['linea_de_negocio'],
        y=comparativo['ventas_anterior'],
        marker=dict(
            color=colores,
            opacity=0.6,
            line=dict(color='white', width=2)
        ),
        text=comparativo['ventas_anterior'].apply(lambda x: f'${x:,.0f}'),
        textposition='outside',
        hovertemplate='<b>%{x}</b><br>' +
                     f'{label_anterior}: $%{{y:,.2f}}<extra></extra>'
    ))
    
    # Barra año actual - todos los datos
    fig.add_trace(go.Bar(
        name=label_actual,
        x=comparativo['linea_de_negocio'],
        y=comparativo['ventas_actual'],
        marker=dict(
            color=colores,
            opacity=1.0,
            line=dict(color='rgba(0,0,0,0.3)', width=1)
        ),
        text=comparativo['ventas_actual'].apply(lambda x: f'${x:,.0f}'),
        textposition='outside',
        hovertemplate='<b>%{x}</b><br>' +
                     f'{label_actual}: $%{{y:,.2f}}<extra></extra>'
    ))
    
    titulo_comparativo = f'<b>Comparativo: {año_actual} YTD vs {año_anterior}'
    if usar_año_completo_anterior:
        titulo_comparativo += ' (Año Completo)</b>'
    else:
        titulo_comparativo += ' YTD</b>'
    
    fig.update_layout(
        title={
            'text': titulo_comparativo,
            'x': 0.5,
            'xanchor': 'center',
            'font': {'size': 18}
        },
        barmode='group',
        xaxis_title='Línea de Negocio',
        yaxis_title='Ventas USD',
        height=450,
        template=None,
        paper_bgcolor='white',
        plot_bgcolor='white',
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="center",
            x=0.5
        ),
        xaxis=dict(
            gridcolor='lightgray',
            showgrid=False
        ),
        yaxis=dict(
            gridcolor='lightgray',
            showgrid=True
        )
    )
    
    return fig, comparativo

def crear_treemap_participacion(df_ytd):
    """Crea treemap mostrando participación de cada línea."""
    
    ventas_linea = df_ytd.groupby('linea_de_negocio')['ventas_usd'].sum().reset_index()
    ventas_linea['participacion'] = (ventas_linea['ventas_usd'] / ventas_linea['ventas_usd'].sum() * 100).round(2)
    ventas_linea = ventas_linea.sort_values('ventas_usd', ascending=False)
    
    fig = px.treemap(
        ventas_linea,
        path=['linea_de_negocio'],
        values='ventas_usd',
        color='linea_de_negocio',
        color_discrete_map=COLORES_LINEAS,
        custom_data=['participacion']
    )
    
    fig.update_traces(
        texttemplate='<b>%{label}</b><br>%{customdata[0]:.1f}%<br>$%{value:,.0f}',
        textposition='middle center',
        textfont_size=14
    )
    
    fig.update_layout(
        title={
            'text': '<b>Participación % en Ventas YTD</b>',
            'x': 0.5,
            'xanchor': 'center',
            'font': {'size': 16}
        },
        height=400
    )
    
    return fig

def crear_tabla_top_productos(df_ytd, n=10):
    """Crea tabla con top productos del período."""
    
    if 'producto' not in df_ytd.columns:
        return None
    
    top_productos = df_ytd.groupby(['producto', 'linea_de_negocio'])['ventas_usd'].sum().reset_index()
    top_productos = top_productos.sort_values('ventas_usd', ascending=False).head(n)
    # No formatear a string aquí para permitir estilos posteriores
    top_productos.columns = ['Producto', 'Línea', 'Ventas USD']
    
    return top_productos

def crear_tabla_top_clientes(df_ytd, n=10):
    """Crea tabla con top clientes del período."""
    
    if 'cliente' not in df_ytd.columns:
        return None
    
    top_clientes = df_ytd.groupby(['cliente', 'linea_de_negocio'])['ventas_usd'].sum().reset_index()
    top_clientes = top_clientes.sort_values('ventas_usd', ascending=False).head(n)
    # No formatear a string aquí para permitir estilos posteriores
    top_clientes.columns = ['Cliente', 'Línea', 'Ventas USD']
    
    return top_clientes

def exportar_excel_ytd(df_ytd, año, comparativo_df=None):
    """Genera archivo Excel con reporte YTD completo."""
    
    output = io.BytesIO()
    
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        # Hoja 1: Resumen Ejecutivo
        metricas = calcular_metricas_ytd(df_ytd)
        resumen_data = {
            'Métrica': [
                'Total Ventas YTD',
                'Días Transcurridos',
                'Promedio Diario',
                'Proyección Anual',
                'Fecha de Reporte'
            ],
            'Valor': [
                f"${metricas['total_ytd']:,.2f}",
                metricas['dias_transcurridos'],
                f"${metricas['promedio_diario']:,.2f}",
                f"${metricas['proyeccion_anual']:,.2f}",
                datetime.now().strftime('%Y-%m-%d')
            ]
        }
        df_resumen = pd.DataFrame(resumen_data)
        df_resumen.to_excel(writer, sheet_name='Resumen Ejecutivo', index=False)
        
        # Hoja 2: Ventas por Línea
        ventas_linea = df_ytd.groupby('linea_de_negocio')['ventas_usd'].sum().reset_index()
        ventas_linea.columns = ['Línea de Negocio', 'Ventas USD YTD']
        ventas_linea['Participación %'] = (ventas_linea['Ventas USD YTD'] / 
                                            ventas_linea['Ventas USD YTD'].sum() * 100).round(2)
        ventas_linea = ventas_linea.sort_values('Ventas USD YTD', ascending=False)
        ventas_linea.to_excel(writer, sheet_name='Por Línea', index=False)
        
        # Hoja 3: Desglose Mensual
        df_ytd_copy = df_ytd.copy()
        df_ytd_copy['mes'] = df_ytd_copy['fecha'].dt.month
        desglose_mes = df_ytd_copy.groupby(['linea_de_negocio', 'mes'])['ventas_usd'].sum().reset_index()
        pivot_mes = desglose_mes.pivot(index='linea_de_negocio', columns='mes', values='ventas_usd').fillna(0)
        pivot_mes.columns = [f'Mes {int(m)}' for m in pivot_mes.columns]
        pivot_mes['Total'] = pivot_mes.sum(axis=1)
        pivot_mes.to_excel(writer, sheet_name='Desglose Mensual')
        
        # Hoja 4: Comparativo (si existe)
        if comparativo_df is not None:
            comparativo_df.to_excel(writer, sheet_name='Comparativo Años', index=False)
        
        # Hoja 5: Top Productos
        if 'producto' in df_ytd.columns:
            top_prod = df_ytd.groupby(['producto', 'linea_de_negocio'])['ventas_usd'].sum().reset_index()
            top_prod = top_prod.sort_values('ventas_usd', ascending=False).head(20)
            top_prod.columns = ['Producto', 'Línea', 'Ventas USD']
            top_prod.to_excel(writer, sheet_name='Top Productos', index=False)
        
        # Hoja 6: Top Clientes
        if 'cliente' in df_ytd.columns:
            top_cli = df_ytd.groupby(['cliente', 'linea_de_negocio'])['ventas_usd'].sum().reset_index()
            top_cli = top_cli.sort_values('ventas_usd', ascending=False).head(20)
            top_cli.columns = ['Cliente', 'Línea', 'Ventas USD']
            top_cli.to_excel(writer, sheet_name='Top Clientes', index=False)
    
    output.seek(0)
    return output

def run(df):
    """
    Función principal del módulo YTD por Líneas.
    
    Args:
        df: DataFrame con datos de ventas (requiere: fecha, linea_de_negocio, ventas_usd)
    """
    st.title("📊 Reporte YTD por Línea de Negocio")
    st.markdown("---")
    
    # Validar columnas requeridas
    required_cols = ['fecha', 'linea_de_negocio', 'ventas_usd']
    missing_cols = [col for col in required_cols if col not in df.columns]
    
    if missing_cols:
        st.error(f"❌ Faltan columnas requeridas: {', '.join(missing_cols)}")
        st.info("💡 Este reporte requiere datos de ventas con columnas: fecha, linea_de_negocio, ventas_usd")
        return
    
    # Asegurar que fecha es datetime
    df['fecha'] = pd.to_datetime(df['fecha'], errors='coerce')
    df = df.dropna(subset=['fecha'])
    
    # Obtener años disponibles
    años_disponibles = sorted(df['fecha'].dt.year.unique(), reverse=True)
    
    if len(años_disponibles) == 0:
        st.error("❌ No hay datos de ventas disponibles")
        return
    
    # =====================================================================
    # SECCIÓN 1: CONTROLES
    # =====================================================================
    st.sidebar.header("⚙️ Configuración")
    
    año_actual = st.sidebar.selectbox(
        "📅 Año a Analizar",
        options=años_disponibles,
        index=0
    )
    
    comparar_año = st.sidebar.checkbox("📊 Comparar con año anterior", value=True)
    
    # Modo de comparación
    modo_comparacion = "año_completo"
    if comparar_año:
        st.sidebar.markdown("**Tipo de Comparación:**")
        modo_comparacion = st.sidebar.radio(
            "Selecciona el modo",
            options=["año_completo", "ytd_equivalente"],
            format_func=lambda x: {
                "año_completo": "📅 Año Anterior Completo vs YTD Actual",
                "ytd_equivalente": "📆 YTD Equivalente (mismo período)"
            }[x],
            help="Año Completo: Compara YTD actual con todo el año anterior | YTD Equivalente: Compara mismo período en ambos años",
            label_visibility="collapsed"
        )
    
    año_anterior = None
    if comparar_año and (año_actual - 1) in años_disponibles:
        año_anterior = año_actual - 1
    elif comparar_año:
        st.sidebar.warning(f"⚠️ No hay datos para {año_actual - 1}")
    
    # Filtros adicionales
    st.sidebar.markdown("---")
    st.sidebar.subheader("🔍 Filtros Adicionales")
    
    lineas_disponibles = sorted(df['linea_de_negocio'].unique())
    seleccion_lineas = st.sidebar.multiselect(
        "Líneas de Negocio",
        options=lineas_disponibles,
        default=lineas_disponibles
    )
    
    # Control para número de líneas a mostrar en detalle
    num_total_lineas = len(lineas_disponibles)
    num_lineas_mostrar = st.sidebar.slider(
        "📊 Líneas en Panel Detallado",
        min_value=1,
        max_value=num_total_lineas,
        value=min(10, num_total_lineas),
        help="Número de líneas de negocio a mostrar en el panel de detalles expandibles"
    )
    
    # Aplicar filtros
    df_filtrado = df[df['linea_de_negocio'].isin(seleccion_lineas)].copy()
    
    # Calcular YTD
    df_ytd_actual = calcular_ytd(df_filtrado, año_actual)
    
    if df_ytd_actual.empty:
        st.warning(f"⚠️ No hay datos YTD para {año_actual}")
        return
    
    # =====================================================================
    # SECCIÓN 2: KPIs PRINCIPALES
    # =====================================================================
    st.header("📈 Indicadores Clave")
    
    metricas = calcular_metricas_ytd(df_ytd_actual)
    
    # Calcular crecimiento si hay año anterior
    crecimiento_pct = 0
    total_anterior = 0
    if año_anterior:
        # Determinar fecha de corte según modo de comparación
        if modo_comparacion == "año_completo":
            # Usar TODO el año anterior completo
            fecha_corte_anterior = datetime(año_anterior, 12, 31)
            label_comparacion = f"Año completo {año_anterior}"
        else:
            # Usar YTD equivalente (misma fecha del calendario)
            fecha_corte = datetime.now()
            mes_actual = fecha_corte.month
            dia_actual = fecha_corte.day
            try:
                fecha_corte_anterior = datetime(año_anterior, mes_actual, dia_actual)
            except ValueError:
                fecha_corte_anterior = datetime(año_anterior, mes_actual, 28)
            label_comparacion = f"YTD {año_anterior}"
        
        df_ytd_anterior = calcular_ytd(df_filtrado, año_anterior, fecha_corte_anterior)
        total_anterior = df_ytd_anterior['ventas_usd'].sum()
        
        logger.info(f"KPIs - YTD {año_actual}: ${metricas['total_ytd']:,.2f}, {label_comparacion}: ${total_anterior:,.2f}")
        
        if total_anterior > 0:
            crecimiento_pct = ((metricas['total_ytd'] - total_anterior) / total_anterior) * 100
        elif metricas['total_ytd'] > 0:
            crecimiento_pct = 100.0  # Crecimiento desde cero
    
    # Línea top
    linea_top = df_ytd_actual.groupby('linea_de_negocio')['ventas_usd'].sum().idxmax()
    ventas_linea_top = df_ytd_actual.groupby('linea_de_negocio')['ventas_usd'].sum().max()
    
    # Mostrar métricas
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if año_anterior:
            if modo_comparacion == "año_completo":
                delta_label = f"vs {año_anterior} completo: ${total_anterior:,.0f}"
            else:
                delta_label = f"vs YTD {año_anterior}: ${total_anterior:,.0f}"
        else:
            delta_label = None
            
        st.metric(
            label="💰 Total YTD",
            value=f"${metricas['total_ytd']:,.0f}",
            delta=delta_label
        )
    
    with col2:
        if año_anterior:
            if modo_comparacion == "año_completo":
                label_crec = f"📈 vs {año_anterior} Completo"
            else:
                label_crec = f"📈 vs YTD {año_anterior}"
        else:
            label_crec = "📈 Crecimiento"
            
        st.metric(
            label=label_crec,
            value=f"{crecimiento_pct:+.1f}%" if año_anterior else "N/A",
            delta_color="off"
        )
    
    with col3:
        st.metric(
            label="🏆 Línea #1",
            value=linea_top,
            delta=f"${ventas_linea_top:,.0f}"
        )
    
    with col4:
        st.metric(
            label="📅 Días Transcurridos",
            value=f"{metricas['dias_transcurridos']} días",
            delta=f"de 365 ({metricas['dias_transcurridos']/365*100:.1f}%)"
        )
    
    st.markdown("---")
    
    # =====================================================================
    # SECCIÓN 3: VISUALIZACIONES PRINCIPALES
    # =====================================================================
    st.header("📊 Análisis Visual")
    
    # Gráfico de líneas acumulado
    fig_lineas = crear_grafico_lineas_acumulado(df_filtrado, año_actual, año_anterior)
    st.plotly_chart(fig_lineas, use_container_width=True)
    
    # Layout de dos columnas
    col_left, col_right = st.columns([6, 4])
    
    with col_left:
        # Gráfico de barras comparativo
        if año_anterior:
            usar_año_completo = (modo_comparacion == "año_completo")
            fig_barras, comparativo_df = crear_grafico_barras_comparativo(
                df_filtrado, 
                año_actual, 
                año_anterior, 
                usar_año_completo_anterior=usar_año_completo
            )
            st.plotly_chart(fig_barras, use_container_width=True)
            
            # Panel extendible con detalles por línea de negocio
            st.subheader("📊 Detalle Comparativo por Línea")
            
            # Ordenar por ventas actuales descendente
            comparativo_ordenado = comparativo_df.sort_values('ventas_actual', ascending=False)
            
            # Limitar según slider del usuario
            comparativo_a_mostrar = comparativo_ordenado.head(num_lineas_mostrar)
            
            # Mostrar información del filtro
            total_lineas = len(comparativo_ordenado)
            if num_lineas_mostrar < total_lineas:
                st.info(f"📋 Mostrando las top {num_lineas_mostrar} de {total_lineas} líneas disponibles. Ajusta el slider en el panel lateral para ver más.")
            
            # Crear expanders para cada línea de negocio
            for idx, row in comparativo_a_mostrar.iterrows():
                linea = row['linea_de_negocio']
                ventas_actual = row['ventas_actual']
                ventas_anterior = row['ventas_anterior']
                crecimiento = row['crecimiento']
                
                # Calcular variación absoluta
                variacion_absoluta = ventas_actual - ventas_anterior
                
                # Obtener color de la línea
                color_linea = COLORES_LINEAS.get(linea, '#808080')
                
                # Determinar emoji basado en crecimiento
                if crecimiento > 0:
                    emoji_trend = "📈"
                    delta_color = "normal"
                elif crecimiento < 0:
                    emoji_trend = "📉"
                    delta_color = "inverse"
                else:
                    emoji_trend = "➖"
                    delta_color = "off"
                
                # Crear expander con título informativo
                with st.expander(f"{emoji_trend} **{linea}** - ${ventas_actual:,.0f} ({crecimiento:+.1f}%)", expanded=False):
                    # Mostrar métricas en columnas
                    col_a, col_b, col_c = st.columns(3)
                    
                    with col_a:
                        st.metric(
                            label=f"Año {año_actual}",
                            value=f"${ventas_actual:,.0f}",
                            delta=None
                        )
                    
                    with col_b:
                        st.metric(
                            label=f"Año {año_anterior}",
                            value=f"${ventas_anterior:,.0f}",
                            delta=None
                        )
                    
                    with col_c:
                        st.metric(
                            label="Crecimiento",
                            value=f"{crecimiento:+.1f}%",
                            delta=f"${variacion_absoluta:+,.0f}",
                            delta_color=delta_color
                        )
                    
                    # Barra visual de comparación
                    if ventas_anterior > 0:
                        ratio = ventas_actual / ventas_anterior
                        st.markdown(f"**Ratio:** {ratio:.2f}x")
                        
                        # Crear mini gráfico de barras comparativo
                        import plotly.graph_objects as go
                        
                        fig_mini = go.Figure()
                        fig_mini.add_trace(go.Bar(
                            x=[f'{año_anterior}', f'{año_actual}'],
                            y=[ventas_anterior, ventas_actual],
                            marker=dict(color=[color_linea, color_linea], opacity=[0.6, 1.0]),
                            text=[f'${ventas_anterior:,.0f}', f'${ventas_actual:,.0f}'],
                            textposition='outside'
                        ))
                        
                        fig_mini.update_layout(
                            height=200,
                            margin=dict(l=0, r=0, t=0, b=0),
                            showlegend=False,
                            yaxis=dict(showgrid=True, gridcolor='lightgray'),
                            xaxis=dict(showgrid=False),
                            paper_bgcolor='rgba(0,0,0,0)',
                            plot_bgcolor='rgba(0,0,0,0)'
                        )
                        
                        st.plotly_chart(fig_mini, use_container_width=True)
                    else:
                        st.info("💡 Sin datos del año anterior para comparar")
        else:
            st.info("💡 Selecciona 'Comparar con año anterior' para ver análisis comparativo")
    
    with col_right:
        # Treemap de participación (limitado según slider)
        # Filtrar top N líneas para el treemap
        top_lineas = df_ytd_actual.groupby('linea_de_negocio')['ventas_usd'].sum()\
            .sort_values(ascending=False).head(num_lineas_mostrar).index.tolist()
        df_ytd_treemap = df_ytd_actual[df_ytd_actual['linea_de_negocio'].isin(top_lineas)]
        
        fig_treemap = crear_treemap_participacion(df_ytd_treemap)
        st.plotly_chart(fig_treemap, use_container_width=True)
        
        # Tabla resumen por línea con colores
        st.subheader("📋 Resumen por Línea")
        ventas_linea = df_ytd_actual.groupby('linea_de_negocio')['ventas_usd'].sum().reset_index()
        ventas_linea['participacion'] = (ventas_linea['ventas_usd'] / ventas_linea['ventas_usd'].sum() * 100)
        ventas_linea = ventas_linea.sort_values('ventas_usd', ascending=False)
        
        # Limitar según slider del usuario
        ventas_linea_mostrar = ventas_linea.head(num_lineas_mostrar)
        
        # Mostrar información del filtro
        total_lineas_tabla = len(ventas_linea)
        if num_lineas_mostrar < total_lineas_tabla:
            st.caption(f"Mostrando top {num_lineas_mostrar} de {total_lineas_tabla} líneas")
        
        ventas_linea_mostrar.columns = ['Línea', 'Ventas USD', 'Part. %']
        
        # Función para aplicar colores de fondo a la columna Línea
        def aplicar_color_fondo(val):
            color = COLORES_LINEAS.get(val, 'white')
            # Calcular brillo para decidir color de texto (blanco o negro)
            # Fórmula de luminancia relativa
            if color.startswith('#'):
                r = int(color[1:3], 16)
                g = int(color[3:5], 16)
                b = int(color[5:7], 16)
                luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
                text_color = 'white' if luminance < 0.5 else 'black'
            else:
                text_color = 'black'
                
            return f'background-color: {color}; color: {text_color}'

        # Aplicar estilos usando Pandas Styler
        st_tabla = ventas_linea_mostrar.style\
            .format({'Ventas USD': '${:,.2f}', 'Part. %': '{:.2f}%'})\
            .applymap(aplicar_color_fondo, subset=['Línea'])
            
        st.dataframe(
            st_tabla, 
            hide_index=True, 
            use_container_width=True,
            column_config={
                "Línea": st.column_config.TextColumn("Línea de Negocio"),
                "Ventas USD": st.column_config.NumberColumn("Ventas USD", format="$%.2f"),
                "Part. %": st.column_config.ProgressColumn(
                    "Participación", 
                    format="%.2f%%", 
                    min_value=0, 
                    max_value=100
                )
            }
        )
    
    st.markdown("---")
    
    # =====================================================================
    # SECCIÓN 4: ANÁLISIS DETALLADO (TABS)
    # =====================================================================
    st.header("🔍 Análisis Detallado")
    
    tab1, tab2, tab3 = st.tabs(["📋 Desglose Mensual", "👥 Top Clientes", "📦 Top Productos"])
    
    with tab1:
        st.subheader("Ventas Mensuales por Línea")
        df_ytd_copy = df_ytd_actual.copy()
        df_ytd_copy['mes'] = df_ytd_copy['fecha'].dt.month
        df_ytd_copy['mes_nombre'] = df_ytd_copy['fecha'].dt.strftime('%B')
        
        desglose_mes = df_ytd_copy.groupby(['linea_de_negocio', 'mes', 'mes_nombre'])['ventas_usd'].sum().reset_index()
        pivot_mes = desglose_mes.pivot(index='linea_de_negocio', columns='mes', values='ventas_usd').fillna(0)
        pivot_mes.columns = [f'{datetime(2000, int(m), 1).strftime("%b")}' for m in pivot_mes.columns]
        pivot_mes['Total'] = pivot_mes.sum(axis=1)
        pivot_mes = pivot_mes.style.format('${:,.2f}').background_gradient(cmap='Blues', subset=pivot_mes.columns[:-1])
        
        st.dataframe(pivot_mes, use_container_width=True)
    
    with tab2:
        st.subheader("Top 10 Clientes YTD")
        tabla_clientes = crear_tabla_top_clientes(df_ytd_actual, n=10)
        if tabla_clientes is not None:
            # Reutilizar función de estilo definida anteriormente si es posible, o redefinir
            def aplicar_color_fondo_local(val):
                color = COLORES_LINEAS.get(val, 'white')
                if color.startswith('#'):
                    r = int(color[1:3], 16)
                    g = int(color[3:5], 16)
                    b = int(color[5:7], 16)
                    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
                    text_color = 'white' if luminance < 0.5 else 'black'
                else:
                    text_color = 'black'
                return f'background-color: {color}; color: {text_color}'

            st_clientes = tabla_clientes.style\
                .format({'Ventas USD': '${:,.2f}'})\
                .applymap(aplicar_color_fondo_local, subset=['Línea'])
                
            st.dataframe(
                st_clientes, 
                hide_index=True, 
                use_container_width=True,
                column_config={
                    "Ventas USD": st.column_config.NumberColumn("Ventas USD", format="$%.2f")
                }
            )
        else:
            st.info("💡 No hay información de clientes disponible")
    
    with tab3:
        st.subheader("Top 10 Productos YTD")
        tabla_productos = crear_tabla_top_productos(df_ytd_actual, n=10)
        if tabla_productos is not None:
            # Redefinir (o usar la misma si estuviera en scope, pero por seguridad repito lambda o def)
            # Como st_clientes ya usó su propia def, aquí creo st_productos
            
            st_productos = tabla_productos.style\
                .format({'Ventas USD': '${:,.2f}'})\
                .applymap(aplicar_color_fondo_local, subset=['Línea']) # aplicar_color_fondo_local está en el scope del with tab2? No necesariamente en Python block scope es function scope, pero tab2 y tab3 están al mismo nivel.
            
            # Python variables leak from blocks (except functions), so aplicar_color_fondo_local should be available if defined before
            # Para estar seguro y limpio:
            
            st.dataframe(
                st_productos, 
                hide_index=True, 
                use_container_width=True,
                column_config={
                    "Ventas USD": st.column_config.NumberColumn("Ventas USD", format="$%.2f")
                }
            )
        else:
            st.info("💡 No hay información de productos disponible")
    
    st.markdown("---")
    
    # =====================================================================
    # SECCIÓN 5: EXPORTACIÓN
    # =====================================================================
    st.header("📥 Exportar Reporte")
    
    col_exp1, col_exp2 = st.columns(2)
    
    with col_exp1:
        st.subheader("📊 Excel Completo")
        comparativo_df_export = None
        if año_anterior:
            usar_año_completo = (modo_comparacion == "año_completo")
            _, comparativo_df_export = crear_grafico_barras_comparativo(
                df_filtrado, 
                año_actual, 
                año_anterior,
                usar_año_completo_anterior=usar_año_completo
            )
        
        excel_buffer = exportar_excel_ytd(df_ytd_actual, año_actual, comparativo_df_export)
        
        st.download_button(
            label="📥 Descargar Excel",
            data=excel_buffer,
            file_name=f"Reporte_YTD_{año_actual}_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        st.caption(f"Incluye: Resumen ejecutivo, desglose mensual, top productos y clientes")
    
    with col_exp2:
        st.subheader("📊 Datos Brutos")
        csv_buffer = df_ytd_actual.to_csv(index=False).encode('utf-8')
        
        st.download_button(
            label="📥 Descargar CSV",
            data=csv_buffer,
            file_name=f"Datos_YTD_{año_actual}_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
        st.caption(f"Datos crudos YTD {año_actual} ({len(df_ytd_actual)} registros)")
    
    # Footer con información
    st.markdown("---")
    st.caption(f"📅 Reporte generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | "
              f"Período analizado: 01/01/{año_actual} - {datetime.now().strftime('%d/%m/%Y')}")
