"""
Módulo: Reporte YTD (Year-to-Date) por Producto
Autor: Dashboard Fradma
Fecha: Enero 2026

Funcionalidad:
- Análisis de ventas acumuladas del año en curso por producto
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
import os
from utils.logger import configurar_logger
from utils.ai_helper import generar_resumen_ejecutivo_ytd, validar_api_key
from utils.auth import get_current_user

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
    
    # Obtener el año de los datos (no usar año actual si estamos analizando histórico)
    if len(df_ytd) > 0:
        año_datos = df_ytd['fecha'].max().year
        inicio_año = datetime(año_datos, 1, 1)
        # Si es año actual, usar fecha actual; si es histórico, usar 31 dic
        if año_datos == datetime.now().year:
            fecha_fin = datetime.now()
        else:
            fecha_fin = datetime(año_datos, 12, 31)
        dias_transcurridos = (fecha_fin - inicio_año).days + 1
    else:
        dias_transcurridos = 1
    
    promedio_diario = total_ytd / dias_transcurridos if dias_transcurridos > 0 else 0
    proyeccion_anual = promedio_diario * 365
    
    return {
        'total_ytd': total_ytd,
        'dias_transcurridos': dias_transcurridos,
        'promedio_diario': promedio_diario,
        'proyeccion_anual': proyeccion_anual
    }

def crear_grafico_temporal_producto(df, producto, año_actual, año_anterior=None):
    """
    Crea gráfico de evolución temporal de un producto específico.
    
    Args:
        df: DataFrame con datos de ventas
        producto: Nombre del producto a analizar
        año_actual: Año principal a mostrar
        año_anterior: Año para comparación (opcional)
    
    Returns:
        Figura de Plotly
    """
    fig = go.Figure()
    
    color_producto = COLORES_LINEAS.get(producto, '#2E86AB')
    
    # Datos año actual
    df_actual = df[(df['fecha'].dt.year == año_actual) & (df['producto'] == producto)].copy()
    if not df_actual.empty:
        df_actual['mes'] = df_actual['fecha'].dt.month
        ventas_mes = df_actual.groupby('mes')['ventas_usd'].sum().sort_index()
        ventas_acumuladas = ventas_mes.cumsum()
        
        fig.add_trace(go.Scatter(
            x=ventas_acumuladas.index,
            y=ventas_acumuladas.values,
            mode='lines+markers',
            name=f"{año_actual}",
            line=dict(color=color_producto, width=4),
            marker=dict(size=12, color=color_producto, line=dict(width=2, color='white')),
            hovertemplate='<b>%{fullData.name}</b><br>' +
                         'Mes: %{x}<br>' +
                         'Acumulado: $%{y:,.2f}<extra></extra>',
            fill='tozeroy',
            fillcolor=f'rgba({int(color_producto[1:3], 16)}, {int(color_producto[3:5], 16)}, {int(color_producto[5:7], 16)}, 0.1)'
        ))
    
    # Datos año anterior si existe
    if año_anterior:
        df_anterior = df[(df['fecha'].dt.year == año_anterior) & (df['producto'] == producto)].copy()
        if not df_anterior.empty:
            df_anterior['mes'] = df_anterior['fecha'].dt.month
            ventas_mes_ant = df_anterior.groupby('mes')['ventas_usd'].sum().sort_index()
            ventas_acumuladas_ant = ventas_mes_ant.cumsum()
            
            fig.add_trace(go.Scatter(
                x=ventas_acumuladas_ant.index,
                y=ventas_acumuladas_ant.values,
                mode='lines+markers',
                name=f"{año_anterior}",
                line=dict(color=color_producto, width=2, dash='dash'),
                marker=dict(size=6, color=color_producto, symbol='diamond'),
                opacity=0.6,
                hovertemplate='<b>%{fullData.name}</b><br>' +
                             'Mes: %{x}<br>' +
                             'Acumulado: $%{y:,.2f}<extra></extra>'
            ))
    
    fig.update_layout(
        title={
            'text': f'<b>Evolución Temporal YTD - {producto}</b>',
            'x': 0.5,
            'xanchor': 'center',
            'font': {'size': 18}
        },
        xaxis_title='Mes',
        yaxis_title='Ventas USD Acumuladas',
        hovermode='x unified',
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
            tickmode='array',
            tickvals=list(range(1, 13)),
            ticktext=['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 
                     'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'],
            gridcolor='lightgray',
            showgrid=True
        ),
        yaxis=dict(
            gridcolor='lightgray',
            showgrid=True,
            tickformat='$,.0f'
        )
    )
    
    return fig

def crear_treemap_clientes_producto(df_ytd, producto):
    """
    Crea treemap de clientes que compran un producto específico.
    
    Args:
        df_ytd: DataFrame con datos YTD
        producto: Nombre del producto
    
    Returns:
        Figura de Plotly
    """
    # Filtrar solo el producto seleccionado
    df_producto = df_ytd[df_ytd['producto'] == producto].copy()
    
    if df_producto.empty:
        # Retornar figura vacía si no hay datos
        fig = go.Figure()
        fig.add_annotation(
            text="No hay datos de clientes para este producto",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16)
        )
        return fig
    
    # Agrupar por cliente
    ventas_clientes = df_producto.groupby('cliente')['ventas_usd'].sum().reset_index()
    ventas_clientes = ventas_clientes.sort_values('ventas_usd', ascending=False)
    
    # Agregar columna de producto para el treemap
    ventas_clientes['producto'] = producto
    
    # Crear columna de texto con formato
    ventas_clientes['texto'] = ventas_clientes.apply(
        lambda row: f"{row['cliente']}<br>${row['ventas_usd']:,.0f}", 
        axis=1
    )
    
    # Calcular participación
    ventas_clientes['participacion'] = (ventas_clientes['ventas_usd'] / ventas_clientes['ventas_usd'].sum() * 100).round(2)
    
    fig = px.treemap(
        ventas_clientes,
        path=['producto', 'cliente'],
        values='ventas_usd',
        title=f'<b>Distribución de Clientes - {producto}</b>',
        color='ventas_usd',
        color_continuous_scale='Blues',
        hover_data={'ventas_usd': ':$,.2f', 'participacion': ':.2f%'},
        custom_data=['participacion']
    )
    
    fig.update_traces(
        textposition="middle center",
        marker=dict(line=dict(width=2, color='white')),
        hovertemplate='<b>%{label}</b><br>' +
                     'Ventas: %{value:$,.2f}<br>' +
                     'Participación: %{customdata[0]:.2f}%<extra></extra>'
    )
    
    fig.update_layout(
        height=500,
        title_x=0.5,
        title_font_size=18,
        margin=dict(t=50, l=10, r=10, b=10)
    )
    
    return fig

def crear_treemap_productos_top(df_ytd, año, top_n=10):
    """
    Crea treemap de productos top con resto agrupado como 'Otros'.
    Escala de colores: $0 - $1.5M.
    
    Args:
        df_ytd: DataFrame con datos YTD
        año: Año del análisis
        top_n: Número de productos top a mostrar individualmente (1-30)
    
    Returns:
        Figura de Plotly
    """
    # Agrupar por producto y calcular ventas totales
    ventas_productos = df_ytd.groupby('producto')['ventas_usd'].sum().reset_index()
    ventas_productos = ventas_productos.sort_values('ventas_usd', ascending=False)
    
    # Separar top N y el resto
    top_productos = ventas_productos.head(top_n).copy()
    otros_productos = ventas_productos.iloc[top_n:].copy()
    
    # Si hay productos en "Otros", agregarlos
    if len(otros_productos) > 0:
        ventas_otros = otros_productos['ventas_usd'].sum()
        otros_row = pd.DataFrame({
            'producto': ['Otros'],
            'ventas_usd': [ventas_otros]
        })
        productos_para_treemap = pd.concat([top_productos, otros_row], ignore_index=True)
    else:
        productos_para_treemap = top_productos
    
    # Calcular participación
    total_ventas = productos_para_treemap['ventas_usd'].sum()
    productos_para_treemap['participacion'] = (productos_para_treemap['ventas_usd'] / total_ventas * 100).round(2)
    
    # Crear columna parent para el treemap (todos bajo "Total")
    productos_para_treemap['parent'] = ''
    
    # Crear treemap
    fig = px.treemap(
        productos_para_treemap,
        path=['parent', 'producto'],
        values='ventas_usd',
        title=f'<b>Productos Top {top_n} - YTD {año}</b>' + (f' ({len(otros_productos)} en "Otros")' if len(otros_productos) > 0 else ''),
        color='ventas_usd',
        color_continuous_scale='RdYlGn',
        range_color=[0, 1_500_000],
        hover_data={'ventas_usd': ':$,.2f', 'participacion': ':.2f%'},
        custom_data=['participacion']
    )
    
    fig.update_traces(
        textposition="middle center",
        marker=dict(line=dict(width=2, color='white')),
        hovertemplate='<b>%{label}</b><br>' +
                     'Ventas: %{value:$,.2f}<br>' +
                     'Participación: %{customdata[0]:.2f}%<extra></extra>',
        textfont=dict(size=14, color='white')
    )
    
    fig.update_layout(
        height=500,
        title_x=0.5,
        title_font_size=18,
        margin=dict(t=60, l=10, r=10, b=10)
    )
    
    return fig

def crear_grafico_lineas_acumulado(df, año_actual, año_anterior=None):
    """
    Crea gráfico de productos con ventas acumuladas por mes.
    
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
    
    # Agrupar por producto y mes
    for linea in df_actual['producto'].unique():
        df_linea = df_actual[df_actual['producto'] == linea]
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
        
        for linea in df_anterior['producto'].unique():
            df_linea = df_anterior[df_anterior['producto'] == linea]
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
    Crea gráfico de barras comparando año actual vs anterior por producto.
    
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
    
    # Agrupar por producto
    ventas_actual = df_actual.groupby('producto')['ventas_usd'].sum().reset_index()
    ventas_actual.columns = ['producto', 'ventas_actual']
    
    ventas_anterior = df_anterior.groupby('producto')['ventas_usd'].sum().reset_index()
    ventas_anterior.columns = ['producto', 'ventas_anterior']
    
    # Merge
    comparativo = ventas_actual.merge(ventas_anterior, on='producto', how='outer').fillna(0)
    
    # Calcular crecimiento manejando casos especiales
    def calcular_crecimiento_seguro(row):
        actual = row['ventas_actual']
        anterior = row['ventas_anterior']
        
        if anterior == 0:
            if actual == 0:
                return 0.0  # Sin ventas en ambos períodos
            else:
                # Nueva línea o crecimiento desde cero - retornar valor muy alto pero calculable
                # para mantener proporciones (999% cap para no romper escalas visuales)
                return min(999.0, (actual / 1000) * 100)  # Escala relativa, cap en 999%
        else:
            return ((actual - anterior) / anterior) * 100
    
    comparativo['crecimiento'] = comparativo.apply(calcular_crecimiento_seguro, axis=1)
    
    # Log de resumen para debugging
    logger.debug(f"Comparativo generado con {len(comparativo)} productos de negocio")
    
    # Crear lista de colores en el orden correcto
    colores = [COLORES_LINEAS.get(linea, '#808080') for linea in comparativo['producto']]
    
    # Crear figura con dos trazas: año anterior y año actual
    fig = go.Figure()
    
    # Barra año anterior - todos los datos
    label_anterior = f"Año {año_anterior}" + (" (Completo)" if usar_año_completo_anterior else " (YTD)")
    label_actual = f"Año {año_actual} (YTD)"
    
    fig.add_trace(go.Bar(
        name=label_anterior,
        x=comparativo['producto'],
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
        x=comparativo['producto'],
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
        xaxis_title='Producto',
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
    
    ventas_producto = df_ytd.groupby('producto')['ventas_usd'].sum().reset_index()
    ventas_producto['participacion'] = (ventas_producto['ventas_usd'] / ventas_producto['ventas_usd'].sum() * 100).round(2)
    ventas_producto = ventas_producto.sort_values('ventas_usd', ascending=False)
    
    fig = px.treemap(
        ventas_producto,
        path=['producto'],
        values='ventas_usd',
        color='producto',
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

def crear_grafico_comparativo_anos_completos(df, años_disponibles):
    """
    Crea gráfico de barras comparando ventas totales de años completos.
    
    Args:
        df: DataFrame con datos de ventas
        años_disponibles: Lista de años disponibles en los datos
    
    Returns:
        Figura de Plotly con comparativo de años completos
    """
    # Filtrar solo los últimos 5 años para no sobrecargar el gráfico
    años_a_mostrar = sorted(años_disponibles, reverse=True)[:5]
    años_a_mostrar = sorted(años_a_mostrar)  # Ordenar ascendente para el gráfico
    
    # Calcular ventas totales por año
    ventas_por_año = []
    for año in años_a_mostrar:
        df_año = df[df['fecha'].dt.year == año]
        total_año = df_año['ventas_usd'].sum()
        ventas_por_año.append({
            'año': str(año),
            'ventas': total_año
        })
    
    df_años = pd.DataFrame(ventas_por_año)
    
    # Calcular crecimiento año a año
    crecimiento = []
    for i in range(len(df_años)):
        if i == 0:
            crecimiento.append(None)
        else:
            venta_actual = df_años.iloc[i]['ventas']
            venta_anterior = df_años.iloc[i-1]['ventas']
            if venta_anterior > 0:
                crec_pct = ((venta_actual - venta_anterior) / venta_anterior) * 100
                crecimiento.append(crec_pct)
            else:
                crecimiento.append(None)
    
    df_años['crecimiento'] = crecimiento
    
    # Crear gráfico de barras
    fig = go.Figure()
    
    # Añadir barras con colores según crecimiento
    colores = []
    for i, row in df_años.iterrows():
        if row['crecimiento'] is None or pd.isna(row['crecimiento']):
            colores.append('#808080')  # Gris para primer año
        elif row['crecimiento'] > 0:
            colores.append('#2ca02c')  # Verde para crecimiento positivo
        else:
            colores.append('#d62728')  # Rojo para decrecimiento
    
    fig.add_trace(go.Bar(
        x=df_años['año'],
        y=df_años['ventas'],
        marker_color=colores,
        text=df_años['ventas'],
        texttemplate='$%{text:,.0f}',
        textposition='outside',
        hovertemplate='<b>Año %{x}</b><br>' +
                     'Ventas Totales: $%{y:,.2f}<br>' +
                     '<extra></extra>'
    ))
    
    # Añadir etiquetas de crecimiento
    for i, row in df_años.iterrows():
        if row['crecimiento'] is not None and not pd.isna(row['crecimiento']):
            fig.add_annotation(
                x=row['año'],
                y=row['ventas'] / 2,
                text=f"{row['crecimiento']:+.1f}%",
                showarrow=False,
                font=dict(size=14, color='white', family='Arial Black'),
                bgcolor='rgba(0,0,0,0.6)',
                borderpad=4
            )
    
    fig.update_layout(
        title={
            'text': '<b>Comparativo de Ventas Totales por Año Completo</b>',
            'x': 0.5,
            'xanchor': 'center',
            'font': {'size': 20}
        },
        xaxis_title='Año',
        yaxis_title='Ventas USD Totales',
        height=450,
        template=None,
        paper_bgcolor='white',
        plot_bgcolor='white',
        showlegend=False,
        xaxis=dict(
            gridcolor='lightgray',
            showgrid=True
        ),
        yaxis=dict(
            gridcolor='lightgray',
            showgrid=True
        )
    )
    
    return fig

def crear_tabla_top_productos(df_ytd, n=10):
    """Crea tabla con top productos del período."""
    
    if 'producto' not in df_ytd.columns:
        return None
    
    top_productos = df_ytd.groupby('producto')['ventas_usd'].sum().reset_index()
    top_productos = top_productos.sort_values('ventas_usd', ascending=False).head(n)
    # No formatear a string aquí para permitir estilos posteriores
    top_productos.columns = ['Producto', 'Ventas USD']
    
    return top_productos

def crear_tabla_top_clientes(df_ytd, n=10):
    """Crea tabla con top clientes del período."""
    
    if 'cliente' not in df_ytd.columns:
        return None
    
    top_clientes = df_ytd.groupby(['cliente', 'producto'])['ventas_usd'].sum().reset_index()
    top_clientes = top_clientes.sort_values('ventas_usd', ascending=False).head(n)
    # No formatear a string aquí para permitir estilos posteriores
    top_clientes.columns = ['Cliente', 'Producto', 'Ventas USD']
    
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
        ventas_producto = df_ytd.groupby('producto')['ventas_usd'].sum().reset_index()
        ventas_producto.columns = ['Producto', 'Ventas USD YTD']
        ventas_producto['Participación %'] = (ventas_producto['Ventas USD YTD'] / 
                                            ventas_producto['Ventas USD YTD'].sum() * 100).round(2)
        ventas_producto = ventas_producto.sort_values('Ventas USD YTD', ascending=False)
        ventas_producto.to_excel(writer, sheet_name='Por Producto', index=False)
        
        # Hoja 3: Desglose Mensual
        df_ytd_copy = df_ytd.copy()
        df_ytd_copy['mes'] = df_ytd_copy['fecha'].dt.month
        desglose_mes = df_ytd_copy.groupby(['producto', 'mes'])['ventas_usd'].sum().reset_index()
        pivot_mes = desglose_mes.pivot(index='producto', columns='mes', values='ventas_usd').fillna(0)
        pivot_mes.columns = [f'Mes {int(m)}' for m in pivot_mes.columns]
        pivot_mes['Total'] = pivot_mes.sum(axis=1)
        pivot_mes.to_excel(writer, sheet_name='Desglose Mensual')
        
        # Hoja 4: Comparativo (si existe)
        if comparativo_df is not None:
            comparativo_df.to_excel(writer, sheet_name='Comparativo Años', index=False)
        
        # Hoja 5: Top Productos
        if 'producto' in df_ytd.columns:
            top_prod = df_ytd.groupby('producto')['ventas_usd'].sum().reset_index()
            top_prod = top_prod.sort_values('ventas_usd', ascending=False).head(20)
            top_prod.columns = ['Producto', 'Ventas USD']
            top_prod.to_excel(writer, sheet_name='Top Productos', index=False)
        
        # Hoja 6: Top Clientes
        if 'cliente' in df_ytd.columns:
            top_cli = df_ytd.groupby(['cliente', 'producto'])['ventas_usd'].sum().reset_index()
            top_cli = top_cli.sort_values('ventas_usd', ascending=False).head(20)
            top_cli.columns = ['Cliente', 'Producto', 'Ventas USD']
            top_cli.to_excel(writer, sheet_name='Top Clientes', index=False)
    
    output.seek(0)
    return output

def run(df, habilitar_ia=False, openai_api_key=None):
    """
    Función principal del módulo YTD por Líneas.
    
    Args:
        df: DataFrame con datos de ventas (requiere: fecha, linea_de_negocio, ventas_usd)
        habilitar_ia: Booleano para activar análisis con IA (default: False)
        openai_api_key: API key de OpenAI para análisis premium (default: None)
    """
    st.title("📊 Reporte YTD por Producto")
    st.markdown("---")
    
    # =====================================================================
    # NORMALIZACIÓN Y MAPEO AUTOMÁTICO DE COLUMNAS
    # =====================================================================
    
    # Hacer una copia para no modificar el original
    df = df.copy()
    
    # 1. Detectar y mapear columna de ventas (ventas_usd)
    if 'ventas_usd' not in df.columns:
        # Variantes comunes de columna de ventas
        variantes_ventas = [
            'valor_usd', 'ventas_usd_con_iva', 'venta_usd', 'ventas', 'venta',
            'importe_usd', 'importe', 'monto_usd', 'monto', 'total_usd', 'total'
        ]
        
        for variante in variantes_ventas:
            if variante in df.columns:
                df['ventas_usd'] = df[variante]
                logger.info(f"Columna de ventas mapeada: '{variante}' → 'ventas_usd'")
                break
    
    # 2. Detectar y mapear columna de producto
    if 'producto' not in df.columns:
        variantes_producto = [
            'linea_de_negocio', 'linea', 'linea_negocio', 'categoria', 'familia', 
            'linea_producto', 'tipo_producto', 'division', 'cod_producto', 'descripcion'
        ]
        
        for variante in variantes_producto:
            if variante in df.columns:
                df['producto'] = df[variante]
                logger.info(f"Columna de producto mapeada: '{variante}' → 'producto'")
                break
    else:
        logger.info("Columna 'producto' encontrada directamente")
    
    # 3. Normalizar nombre de columna fecha si tiene variantes
    if 'fecha' not in df.columns:
        variantes_fecha = ['date', 'fecha_factura', 'fecha_documento', 'fecha_emision']
        
        for variante in variantes_fecha:
            if variante in df.columns:
                df['fecha'] = df[variante]
                logger.info(f"Columna de fecha mapeada: '{variante}' → 'fecha'")
                break
    
    # =====================================================================
    # VALIDACIÓN DE COLUMNAS REQUERIDAS
    # =====================================================================
    
    required_cols = ['fecha', 'producto', 'ventas_usd']
    missing_cols = [col for col in required_cols if col not in df.columns]
    
    if missing_cols:
        st.error(f"❌ Faltan columnas requeridas: {', '.join(missing_cols)}")
        st.info("💡 Este reporte requiere datos de ventas con columnas: **fecha**, **linea_de_negocio**, **ventas_usd** (o variantes)")
        
        # Mostrar columnas disponibles para ayudar al usuario
        with st.expander("🔍 Ver columnas disponibles en el archivo"):
            st.write("**Columnas detectadas:**")
            cols_ordenadas = sorted(df.columns.tolist())
            for i in range(0, len(cols_ordenadas), 3):
                cols_chunk = cols_ordenadas[i:i+3]
                st.write(", ".join(f"`{col}`" for col in cols_chunk))
            
            st.markdown("---")
            st.markdown("""
            **💡 Variantes aceptadas automáticamente:**
            - **Ventas:** `valor_usd`, `ventas_usd_con_iva`, `venta_usd`, `ventas`, `importe_usd`, `monto_usd`, etc.
            - **Línea:** `linea`, `linea_negocio`, `producto`, `categoria`, `familia`, `division`, etc.
            - **Fecha:** `date`, `fecha_factura`, `fecha_documento`, `fecha_emision`, etc.
            """)
        
        logger.warning(f"Columnas faltantes en YTD: {missing_cols}")
        logger.debug(f"Columnas disponibles: {df.columns.tolist()}")
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
    # SECCIÓN 1: CONFIGURACIÓN DE ANÁLISIS (MAIN SECTION)
    # =====================================================================
    st.header("🔧 Configuración del Análisis")
    
    # Layout en 3 columnas para configuración completa
    col_año, col_comparacion, col_producto = st.columns([1, 1, 2])
    
    with col_año:
        año_actual = st.selectbox(
            "📅 Año a Analizar",
            options=años_disponibles,
            index=0,
            help="Selecciona el año principal para análisis YTD"
        )
    
    with col_comparacion:
        comparar_año = st.checkbox(
            "📊 Comparar con año anterior", 
            value=True,
            help="Activa para ver comparativo año vs año"
        )
    
    # Determinar año anterior
    año_anterior = None
    if comparar_año and (año_actual - 1) in años_disponibles:
        año_anterior = año_actual - 1
    elif comparar_año:
        st.warning(f"⚠️ No hay datos para {año_actual - 1}")
        comparar_año = False
    
    # Modo de comparación (si está activado)
    modo_comparacion = "ytd_equivalente"
    if comparar_año:
        col_modo1, col_modo2 = st.columns(2)
        
        with col_modo1:
            st.markdown("**🎯 Tipo de Comparación:**")
        
        with col_modo2:
            modo_comparacion = st.selectbox(
                "Modo",
                options=["ytd_equivalente", "año_completo"],
                format_func=lambda x: {
                    "año_completo": "📅 Año Anterior Completo",
                    "ytd_equivalente": "📆 YTD Equivalente ✓"
                }[x],
                help=(
                    "📆 YTD Equivalente (recomendado): Compara el MISMO periodo en ambos años\n\n"
                    "📅 Año Completo: Compara YTD actual contra TODO el año anterior"
                ),
                index=0,
                label_visibility="collapsed"
            )
        
        # Advertencia si selecciona año completo
        if modo_comparacion == "año_completo":
            st.warning(
                "⚠️ Comparando YTD actual vs año anterior **completo**. "
                "Si estás en inicio de año, verás crecimientos negativos normales."
            )
    
    # Selector de producto con búsqueda dinámica
    with col_producto:
        productos_disponibles = sorted(df['producto'].unique())
        
        # Calcular producto con más ventas para usarlo como default
        df_temp_ytd = calcular_ytd(df, año_actual)
        if not df_temp_ytd.empty:
            ventas_por_producto = df_temp_ytd.groupby('producto')['ventas_usd'].sum().sort_values(ascending=False)
            producto_default = ventas_por_producto.index[0] if len(ventas_por_producto) > 0 else productos_disponibles[0]
        else:
            producto_default = productos_disponibles[0] if productos_disponibles else None
        
        # Buscador de productos
        st.markdown("**📦 Buscador de Producto**")
        busqueda_producto = st.text_input(
            "🔍 Buscar producto",
            value="",
            placeholder="Escribe para filtrar productos...",
            help="Escribe palabras clave para filtrar la lista de productos",
            label_visibility="collapsed"
        )
        
        # Filtrar productos según búsqueda
        if busqueda_producto:
            # Filtro case-insensitive
            productos_filtrados = [p for p in productos_disponibles if busqueda_producto.lower() in p.lower()]
        else:
            productos_filtrados = productos_disponibles
        
        # Mostrar contador de resultados
        if busqueda_producto:
            if len(productos_filtrados) == 0:
                st.warning(f"⚠️ No se encontraron productos con '{busqueda_producto}'")
                # Mostrar todos si no hay resultados
                productos_filtrados = productos_disponibles
            else:
                st.caption(f"✅ {len(productos_filtrados)} producto(s) encontrado(s) de {len(productos_disponibles)} totales")
        else:
            st.caption(f"📋 {len(productos_disponibles)} productos disponibles")
        
        # Determinar producto a seleccionar
        # Mantener el previamente seleccionado si está en los filtrados
        if 'producto_seleccionado_ytd' in st.session_state and st.session_state.producto_seleccionado_ytd in productos_filtrados:
            index_default = productos_filtrados.index(st.session_state.producto_seleccionado_ytd)
        elif producto_default in productos_filtrados:
            index_default = productos_filtrados.index(producto_default)
        else:
            index_default = 0
        
        # Selectbox con productos filtrados
        if len(productos_filtrados) > 0:
            producto_seleccionado = st.selectbox(
                "Selecciona producto",
                options=productos_filtrados,
                index=index_default,
                help="Selecciona un producto para ver su análisis detallado",
                label_visibility="collapsed"
            )
            # Guardar en session state
            st.session_state.producto_seleccionado_ytd = producto_seleccionado
        else:
            st.error("❌ No hay productos disponibles")
            return
    
    # Resumen visual de la configuración
    st.markdown("---")
    
    # Configuración adicional para treemap
    st.markdown("**🗺️ Configuración de Vista General de Productos**")
    col_treemap_conf1, col_treemap_conf2, col_treemap_conf3 = st.columns([2, 2, 1])
    
    with col_treemap_conf1:
        periodo_treemap = st.radio(
            "Periodo para Treemap",
            options=["ytd_actual", "historico_completo", "año_especifico"],
            format_func=lambda x: {
                "ytd_actual": f"📅 YTD {año_actual}",
                "historico_completo": "📊 Todo el Histórico",
                "año_especifico": "🎯 Año Específico"
            }[x],
            horizontal=True,
            help="Selecciona el periodo de datos para calcular los productos top",
            label_visibility="collapsed"
        )
    
    with col_treemap_conf2:
        # Inicializar año_treemap
        año_treemap = año_actual
        
        if periodo_treemap == "año_especifico":
            año_treemap = st.selectbox(
                "Año para Treemap",
                options=años_disponibles,
                index=años_disponibles.index(año_actual) if año_actual in años_disponibles else 0,
                help="Selecciona un año específico para el treemap",
                label_visibility="collapsed"
            )
        else:
            # Mostrar placeholder cuando no es año específico
            st.caption("Periodo configurado →")
    
    with col_treemap_conf3:
        top_n_productos = st.slider(
            "Top N",
            min_value=1,
            max_value=30,
            value=10,
            step=1,
            help="Productos top a mostrar. El resto se agrupa como 'Otros'",
            label_visibility="collapsed"
        )
    
    st.markdown("---")
    
    # Resumen de configuración principal
    col_resumen1, col_resumen2, col_resumen3 = st.columns(3)
    
    with col_resumen1:
        st.info(f"📅 **Periodo:** {año_actual}" + (f" vs {año_anterior}" if año_anterior else ""))
    
    with col_resumen2:
        if año_anterior:
            modo_texto = "YTD Equivalente" if modo_comparacion == "ytd_equivalente" else "Año Completo"
            st.info(f"🎯 **Modo:** {modo_texto}")
        else:
            st.info("🎯 **Modo:** Individual")
    
    with col_resumen3:
        st.success(f"📦 **Producto:** {producto_seleccionado}")
    
    st.markdown("---")
    
    # =====================================================================
    # SIDEBAR: SOLO RESUMEN
    # =====================================================================
    st.sidebar.header("📊 Resumen de Configuración")
    st.sidebar.markdown(f"**Año:** {año_actual}")
    if año_anterior:
        st.sidebar.markdown(f"**Comparación:** {año_anterior}")
        st.sidebar.markdown(f"**Modo:** {'YTD Equiv.' if modo_comparacion == 'ytd_equivalente' else 'Año Completo'}")
    st.sidebar.markdown(f"**Producto:** {producto_seleccionado}")
    st.sidebar.markdown("---")
    st.sidebar.markdown("**🗺️ Treemap:**")
    if periodo_treemap == "ytd_actual":
        st.sidebar.markdown(f"- Periodo: YTD {año_actual}")
    elif periodo_treemap == "historico_completo":
        st.sidebar.markdown("- Periodo: Histórico completo")
    else:
        st.sidebar.markdown(f"- Periodo: Año {año_treemap}")
    st.sidebar.markdown(f"- Top: {top_n_productos} productos")
    st.sidebar.markdown("---")
    
    # =====================================================================
    # CONFIGURACIÓN DE ANÁLISIS CON IA - TEMPORALMENTE DESHABILITADO
    # =====================================================================
    # TODO: Reactivar cuando se simplifique la integración de IA
    # st.sidebar.markdown("---")
    # st.sidebar.subheader("🤖 Análisis con IA")
    # 
    # habilitar_ia = st.sidebar.checkbox(
    #     "Habilitar Análisis Ejecutivo con IA",
    #     value=False,
    #     help="Genera insights automáticos usando OpenAI GPT-4o-mini"
    # )
    # 
    # openai_api_key = None
    # if habilitar_ia:
    #     # Intentar obtener la API key de variable de entorno primero
    #     api_key_env = os.getenv("OPENAI_API_KEY", "")
    #     
    #     if api_key_env:
    #         openai_api_key = api_key_env
    #         st.sidebar.success("✅ API key detectada desde variable de entorno")
    #     else:
    #         openai_api_key = st.sidebar.text_input(
    #             "OpenAI API Key",
    #             type="password",
    #             help="Ingresa tu API key de OpenAI para habilitar el análisis con IA"
    #         )
    #         
    #         if openai_api_key:
    #             # Validar la API key
    #             if validar_api_key(openai_api_key):
    #                 st.sidebar.success("✅ API key válida")
    #             else:
    #                 st.sidebar.error("❌ API key inválida")
    #                 openai_api_key = None
    #     
    #     st.sidebar.caption("💡 Los análisis con IA son generados por GPT-4o-mini y pueden tardar unos segundos")
    
    # IA controlada desde el passkey premium en app.py (se recibe como parámetro)
    # habilitar_ia y openai_api_key vienen de los parámetros de la función
    
    # Aplicar filtro de producto individual
    df_filtrado = df[df['producto'] == producto_seleccionado].copy()
    
    # Calcular YTD
    df_ytd_actual = calcular_ytd(df_filtrado, año_actual)
    
    if df_ytd_actual.empty:
        st.warning(f"⚠️ No hay datos YTD para {año_actual}")
        return
    
    # =====================================================================
    # SECCIÓN 2: KPIs PRINCIPALES
    # =====================================================================
    st.header("📈 Indicadores Clave")
    
    # Mostrar contexto de comparación de periodos
    if año_anterior:
        fecha_inicio_actual = datetime(año_actual, 1, 1)
        fecha_fin_actual = df_ytd_actual['fecha'].max() if len(df_ytd_actual) > 0 else datetime.now()
        dias_ytd_actual = (fecha_fin_actual - fecha_inicio_actual).days + 1
        
        with st.expander("ℹ️ Contexto de Comparación YTD", expanded=False):
            col_info1, col_info2 = st.columns(2)
            
            with col_info1:
                st.markdown(f"**📅 YTD {año_actual} (Actual):**")
                st.info(
                    f"Del **{fecha_inicio_actual.strftime('%d/%m/%Y')}** "
                    f"al **{fecha_fin_actual.strftime('%d/%m/%Y')}**\n\n"
                    f"({dias_ytd_actual} días transcurridos)"
                )
            
            with col_info2:
                if modo_comparacion == "año_completo":
                    fecha_inicio_anterior = datetime(año_anterior, 1, 1)
                    fecha_fin_anterior = datetime(año_anterior, 12, 31)
                    dias_anterior = 365
                    st.markdown(f"**📅 Año {año_anterior} (Completo):**")
                    st.warning(
                        f"Del **{fecha_inicio_anterior.strftime('%d/%m/%Y')}** "
                        f"al **{fecha_fin_anterior.strftime('%d/%m/%Y')}**\n\n"
                        f"({dias_anterior} días - **año completo**)"
                    )
                else:  # ytd_equivalente
                    fecha_inicio_anterior = datetime(año_anterior, 1, 1)
                    # Misma fecha del calendario
                    try:
                        fecha_fin_anterior = datetime(año_anterior, fecha_fin_actual.month, fecha_fin_actual.day)
                    except ValueError:
                        fecha_fin_anterior = datetime(año_anterior, fecha_fin_actual.month, 28)
                    dias_anterior = (fecha_fin_anterior - fecha_inicio_anterior).days + 1
                    st.markdown(f"**📅 YTD {año_anterior} (Equivalente):**")
                    st.success(
                        f"Del **{fecha_inicio_anterior.strftime('%d/%m/%Y')}** "
                        f"al **{fecha_fin_anterior.strftime('%d/%m/%Y')}**\n\n"
                        f"({dias_anterior} días - **mismo periodo**)"
                    )
            
            if modo_comparacion == "año_completo":
                st.markdown(
                    "⚠️ **Modo: Año Completo** - Comparando YTD actual contra TODO el año anterior. "
                    "Esta comparación puede generar crecimientos negativos/bajos si estamos en inicio de año. "
                    "Se recomienda usar **YTD Equivalente** para comparaciones justas."
                )
            else:
                st.markdown(
                    "✅ **Modo: YTD Equivalente** - Comparando periodos equivalentes "
                    f"({dias_ytd_actual} días en ambos años). Esta es la comparación más justa "
                    "para medir crecimiento real."
                )
    
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
    
    # Análisis de clientes del producto
    clientes_del_producto = df_ytd_actual['cliente'].nunique()
    top_cliente = df_ytd_actual.groupby('cliente')['ventas_usd'].sum().idxmax() if len(df_ytd_actual) > 0 else "N/A"
    ventas_top_cliente = df_ytd_actual.groupby('cliente')['ventas_usd'].sum().max() if len(df_ytd_actual) > 0 else 0
    
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
            label="💰 Total YTD Producto",
            value=f"${metricas['total_ytd']:,.0f}",
            delta=delta_label,
            help=f"📐 Ventas totales del producto **{producto_seleccionado}** desde inicio de año"
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
            delta_color="off",
            help=f"📐 Crecimiento del producto **{producto_seleccionado}** vs año anterior"
        )
    
    with col3:
        st.metric(
            label="👥 Clientes Compradores",
            value=f"{clientes_del_producto}",
            delta=f"Top: {top_cliente[:20]}..." if len(top_cliente) > 20 else f"Top: {top_cliente}",
            help=f"📐 Número de clientes únicos que compraron **{producto_seleccionado}** este año"
        )
    
    with col4:
        st.metric(
            label="📅 Días Transcurridos",
            value=f"{metricas['dias_transcurridos']} días",
            delta=f"de 365 ({metricas['dias_transcurridos']/365*100:.1f}%)",
            help="📐 Días corridos del año que se han completado. Si analizas 2026: días desde 01/Ene/2026 hasta hoy. Si analizas 2024: días desde 01/Ene/2024 hasta la última venta registrada ese año. Se usa para calcular la proyección anual (estimado de ventas a 365 días)."
        )
    
    st.markdown("---")
    
    # =====================================================================
    # SECCIÓN 2.5: TREEMAP GENERAL DE PRODUCTOS
    # =====================================================================
    # Determinar título según periodo seleccionado
    if periodo_treemap == "ytd_actual":
        titulo_treemap = f"🗺️ Vista General de Productos - YTD {año_actual}"
    elif periodo_treemap == "historico_completo":
        titulo_treemap = "🗺️ Vista General de Productos - Todo el Histórico"
    else:  # año_especifico
        titulo_treemap = f"🗺️ Vista General de Productos - Año {año_treemap}"
    
    st.header(titulo_treemap)
    
    # Calcular datos según periodo seleccionado
    df_todos_productos = df.copy()
    
    if periodo_treemap == "ytd_actual":
        # Solo YTD del año actual
        df_ytd_todos = calcular_ytd(df_todos_productos, año_actual)
        periodo_label = f"YTD {año_actual}"
    elif periodo_treemap == "historico_completo":
        # Todo el histórico (primer registro hasta último)
        fecha_inicio = df_todos_productos['fecha'].min()
        fecha_fin = df_todos_productos['fecha'].max()
        df_ytd_todos = df_todos_productos.copy()
        periodo_label = f"Histórico ({fecha_inicio.year}-{fecha_fin.year})"
        st.caption(f"📅 Periodo completo: {fecha_inicio.strftime('%d/%m/%Y')} hasta {fecha_fin.strftime('%d/%m/%Y')}")
    else:  # año_especifico
        # Año completo específico
        df_ytd_todos = df_todos_productos[df_todos_productos['fecha'].dt.year == año_treemap].copy()
        periodo_label = f"Año {año_treemap}"
        if not df_ytd_todos.empty:
            fecha_inicio_año = df_ytd_todos['fecha'].min()
            fecha_fin_año = df_ytd_todos['fecha'].max()
            st.caption(f"📅 Periodo: {fecha_inicio_año.strftime('%d/%m/%Y')} hasta {fecha_fin_año.strftime('%d/%m/%Y')}")
    
    if not df_ytd_todos.empty:
        # Crear treemap de productos top
        fig_treemap_productos = crear_treemap_productos_top(df_ytd_todos, periodo_label, top_n_productos)
        st.plotly_chart(fig_treemap_productos, use_container_width=True)
        
        # Mostrar tabla resumen de productos
        with st.expander("📋 Ver detalle de productos", expanded=False):
            productos_resumen = df_ytd_todos.groupby('producto')['ventas_usd'].sum().reset_index()
            productos_resumen = productos_resumen.sort_values('ventas_usd', ascending=False)
            productos_resumen['participacion'] = (productos_resumen['ventas_usd'] / productos_resumen['ventas_usd'].sum() * 100).round(2)
            productos_resumen['ranking'] = range(1, len(productos_resumen) + 1)
            productos_resumen = productos_resumen[['ranking', 'producto', 'ventas_usd', 'participacion']]
            productos_resumen.columns = ['Rank', 'Producto', 'Ventas USD', 'Participación %']
            
            # Highlight del producto seleccionado
            def highlight_selected(row):
                if row['Producto'] == producto_seleccionado:
                    return ['background-color: #90EE90'] * len(row)
                return [''] * len(row)
            
            productos_styled = productos_resumen.style\
                .format({'Ventas USD': '${:,.2f}', 'Participación %': '{:.2f}%'})\
                .apply(highlight_selected, axis=1)
            
            st.dataframe(productos_styled, hide_index=True, use_container_width=True)
            
            st.caption(f"💡 El producto **{producto_seleccionado}** está resaltado en verde. Total de productos: {len(productos_resumen)}")
    else:
        st.warning("⚠️ No hay datos de productos para mostrar")
    
    st.markdown("---")
    
    # =====================================================================
    # SECCIÓN 2.6: ANÁLISIS EJECUTIVO CON IA - FUNCIÓN PREMIUM
    # =====================================================================
    user = get_current_user()
    puede_usar_ia = user and user.can_use_ai()
    
    if habilitar_ia and openai_api_key and puede_usar_ia:
        st.header("🤖 Análisis Ejecutivo con IA Premium")
        
        # Obtener filtros configurados
        periodo_seleccionado = st.session_state.get("analisis_periodo", "Todos los datos")
        lineas_seleccionadas = st.session_state.get("analisis_lineas", ["Todas"])
        
        st.info(
            f"📋 **Configuración:** Periodo: {periodo_seleccionado} | "
            f"Líneas: {', '.join(lineas_seleccionadas[:3])}{'...' if len(lineas_seleccionadas) > 3 else ''}"
        )
        
        # Botón para ejecutar análisis
        if st.button("🚀 Generar Análisis con IA", type="primary", use_container_width=True):
            with st.spinner("🔄 Generando análisis ejecutivo con GPT-4o-mini..."):
                try:
                    # Preparar datos del producto seleccionado
                    df_analisis = df_ytd_actual.copy()
                    
                    # Calcular métricas específicas del producto
                    ventas_ytd_actual_producto = df_analisis['ventas_usd'].sum()
                    num_clientes = df_analisis['cliente'].nunique()
                    ticket_promedio = ventas_ytd_actual_producto / num_clientes if num_clientes > 0 else 0
                    
                    # Recalcular anterior para el producto
                    ventas_ytd_anterior_producto = 0
                    if año_anterior and not df_ytd_anterior.empty:
                        ventas_ytd_anterior_producto = df_ytd_anterior['ventas_usd'].sum()
                    
                    # Recalcular crecimiento del producto
                    if ventas_ytd_anterior_producto > 0:
                        crecimiento_pct_producto = ((ventas_ytd_actual_producto - ventas_ytd_anterior_producto) / ventas_ytd_anterior_producto) * 100
                    elif ventas_ytd_actual_producto > 0:
                        crecimiento_pct_producto = 100.0
                    else:
                        crecimiento_pct_producto = 0
                    
                    # Recalcular proyección del producto
                    dias_transcurridos_producto = metricas['dias_transcurridos']
                    if dias_transcurridos_producto > 0:
                        proyeccion_anual_producto = (ventas_ytd_actual_producto / dias_transcurridos_producto) * 365
                    else:
                        proyeccion_anual_producto = 0
                    
                    # Top clientes del producto
                    top_clientes = df_analisis.groupby('cliente')['ventas_usd'].sum().sort_values(ascending=False).head(5)
                    
                    # Preparar contexto específico para el producto
                    contexto_filtros = f"Análisis del producto: **{producto_seleccionado}**\n"
                    contexto_filtros += f"- Total de clientes que compran este producto: {num_clientes}\n"
                    contexto_filtros += f"- Ticket promedio: ${ticket_promedio:,.2f}\n"
                    contexto_filtros += f"- Top 3 clientes: {', '.join(top_clientes.head(3).index.tolist())}"
                    
                    # Datos del producto para IA
                    datos_lineas = {
                        producto_seleccionado: {
                            'ventas': ventas_ytd_actual_producto,
                            'crecimiento': crecimiento_pct_producto,
                            'clientes': num_clientes,
                            'ticket_promedio': ticket_promedio
                        }
                    }
                    
                    analisis = generar_resumen_ejecutivo_ytd(
                        ventas_ytd_actual=ventas_ytd_actual_producto,
                        ventas_ytd_anterior=ventas_ytd_anterior_producto,
                        crecimiento_pct=crecimiento_pct_producto,
                        dias_transcurridos=dias_transcurridos_producto,
                        proyeccion_anual=proyeccion_anual_producto,
                        producto_top=producto_seleccionado,
                        ventas_producto_top=ventas_ytd_actual_producto,
                        api_key=openai_api_key,
                        datos_lineas=datos_lineas,
                        contexto_filtros=contexto_filtros
                    )
                    
                    # Mostrar análisis estructurado
                    if analisis:
                        # Resumen ejecutivo principal
                        st.markdown("### 📋 Resumen Ejecutivo")
                        st.info(analisis.get('resumen_ejecutivo', 'No disponible'))
                        
                        # Crear columnas para organizar el contenido
                        col_izq, col_der = st.columns(2)
                        
                        with col_izq:
                            # Highlights clave
                            st.markdown("### ✨ Highlights Clave")
                            highlights = analisis.get('highlights_clave', [])
                            if highlights:
                                for highlight in highlights:
                                    st.markdown(f"- {highlight}")
                            else:
                                st.caption("No disponible")
                            
                            st.markdown("")
                            
                            # Insights principales
                            st.markdown("### 💡 Insights Principales")
                            insights = analisis.get('insights_principales', [])
                            if insights:
                                for insight in insights:
                                    st.markdown(f"- {insight}")
                            else:
                                st.caption("No disponible")
                        
                        with col_der:
                            # Áreas de atención
                            st.markdown("### ⚠️ Áreas de Atención")
                            areas = analisis.get('areas_atencion', [])
                            if areas:
                                for area in areas:
                                    st.markdown(f"- {area}")
                            else:
                                st.caption("No hay áreas críticas identificadas")
                            
                            st.markdown("")
                            
                            # Recomendaciones ejecutivas
                            st.markdown("### 🎯 Recomendaciones Ejecutivas")
                            recomendaciones = analisis.get('recomendaciones_ejecutivas', [])
                            if recomendaciones:
                                for rec in recomendaciones:
                                    st.markdown(f"- {rec}")
                            else:
                                st.caption("No disponible")
                        
                        st.caption("🤖 Análisis generado por OpenAI GPT-4o-mini")
                    else:
                        st.warning("⚠️ No se pudo generar el análisis ejecutivo")
                    
                except Exception as e:
                    st.error(f"❌ Error al generar análisis con IA: {str(e)}")
                    logger.error(f"Error en análisis con IA: {e}", exc_info=True)
        else:
            st.caption("👆 Presiona el botón para generar análisis personalizado según tus filtros")
        
        st.markdown("---")
    elif habilitar_ia and openai_api_key and not puede_usar_ia:
        st.warning("⚠️ El análisis con IA está disponible solo para usuarios con rol **Analyst** o **Admin**")
        st.info("💡 Contacta al administrador para solicitar acceso a funciones de IA")
    
    # =====================================================================
    # SECCIÓN 3: VISUALIZACIONES PRINCIPALES
    # =====================================================================
    st.header("📊 Análisis Visual")
    
    # Gráfico temporal del producto individual
    st.subheader(f"📈 Evolución Temporal - {producto_seleccionado}")
    fig_temporal = crear_grafico_temporal_producto(df_filtrado, producto_seleccionado, año_actual, año_anterior)
    st.plotly_chart(fig_temporal, use_container_width=True)
    
    # Análisis de clientes que compran el producto
    st.markdown("---")
    
    # Determinar periodo para análisis de clientes (consistente con configuración del treemap)
    if periodo_treemap == "ytd_actual":
        df_analisis_clientes = df_ytd_actual.copy()
        subtitulo_clientes = f"👥 Análisis de Clientes - {producto_seleccionado} (YTD {año_actual})"
    elif periodo_treemap == "historico_completo":
        df_analisis_clientes = df_filtrado.copy()
        subtitulo_clientes = f"👥 Análisis de Clientes - {producto_seleccionado} (Histórico Completo)"
    else:  # año_especifico
        df_analisis_clientes = df_filtrado[df_filtrado['fecha'].dt.year == año_treemap].copy()
        subtitulo_clientes = f"👥 Análisis de Clientes - {producto_seleccionado} (Año {año_treemap})"
    
    st.subheader(subtitulo_clientes)
    
    col_left, col_right = st.columns([6, 4])
    
    with col_left:
        # Treemap de clientes que compran el producto
        fig_treemap_clientes = crear_treemap_clientes_producto(df_analisis_clientes, producto_seleccionado)
        st.plotly_chart(fig_treemap_clientes, use_container_width=True)
    
    with col_right:
        # Tabla de top clientes que compran el producto
        st.subheader("🏆 Top Clientes")
        clientes_producto = df_analisis_clientes.groupby('cliente')['ventas_usd'].sum().reset_index()
        clientes_producto = clientes_producto.sort_values('ventas_usd', ascending=False).head(10)
        clientes_producto['participacion'] = (clientes_producto['ventas_usd'] / clientes_producto['ventas_usd'].sum() * 100)
        clientes_producto.columns = ['Cliente', 'Ventas USD', 'Part. %']
        
        st_clientes = clientes_producto.style\
            .format({'Ventas USD': '${:,.2f}', 'Part. %': '{:.2f}%'})
        
        st.dataframe(
            st_clientes, 
            hide_index=True, 
            use_container_width=True,
            column_config={
                "Ventas USD": st.column_config.NumberColumn("Ventas USD", format="$%.2f"),
                "Part. %": st.column_config.ProgressColumn(
                    "Participación", 
                    format="%.2f%%", 
                    min_value=0, 
                    max_value=100
                )
            }
        )
        
        # Estadísticas adicionales (consistente con periodo del treemap)
        st.markdown("---")
        st.markdown("**📊 Estadísticas de Clientes**")
        total_clientes = len(df_analisis_clientes['cliente'].unique())
        ticket_promedio = df_analisis_clientes['ventas_usd'].sum() / total_clientes if total_clientes > 0 else 0
        
        col_stat1, col_stat2 = st.columns(2)
        with col_stat1:
            st.metric("Total Clientes", total_clientes)
        with col_stat2:
            st.metric("Ticket Promedio", f"${ticket_promedio:,.0f}")
    
    # Comparativo año vs año del producto
    if año_anterior:
        st.markdown("---")
        st.subheader(f"📊 Comparativo {año_actual} vs {año_anterior}")
        
        # Calcular ventas del año anterior para el producto
        df_anterior_producto = df[(df['fecha'].dt.year == año_anterior) & (df['producto'] == producto_seleccionado)].copy()
        
        if not df_anterior_producto.empty:
            # Determinar fecha de corte según modo de comparación
            if modo_comparacion == "año_completo":
                fecha_corte_anterior = datetime(año_anterior, 12, 31)
            else:
                fecha_corte = datetime.now()
                try:
                    fecha_corte_anterior = datetime(año_anterior, fecha_corte.month, fecha_corte.day)
                except ValueError:
                    fecha_corte_anterior = datetime(año_anterior, fecha_corte.month, 28)
            
            df_ytd_anterior_producto = calcular_ytd(df_anterior_producto, año_anterior, fecha_corte_anterior)
            ventas_anterior_producto = df_ytd_anterior_producto['ventas_usd'].sum()
            ventas_actual_producto = df_ytd_actual['ventas_usd'].sum()
            
            # Calcular crecimiento
            if ventas_anterior_producto > 0:
                crecimiento_producto = ((ventas_actual_producto - ventas_anterior_producto) / ventas_anterior_producto) * 100
            elif ventas_actual_producto > 0:
                crecimiento_producto = 100.0
            else:
                crecimiento_producto = 0
            
            # Determinar emoji y color
            if crecimiento_producto > 0:
                emoji_trend = "📈"
                delta_color = "normal"
            elif crecimiento_producto < 0:
                emoji_trend = "📉"
                delta_color = "inverse"
            else:
                emoji_trend = "➖"
                delta_color = "off"
            
            # Mostrar métricas comparativas
            col_comp1, col_comp2, col_comp3 = st.columns(3)
            
            with col_comp1:
                st.metric(
                    label=f"Año {año_actual}",
                    value=f"${ventas_actual_producto:,.0f}"
                )
            
            with col_comp2:
                st.metric(
                    label=f"Año {año_anterior}",
                    value=f"${ventas_anterior_producto:,.0f}"
                )
            
            with col_comp3:
                st.metric(
                    label=f"{emoji_trend} Crecimiento",
                    value=f"{crecimiento_producto:+.1f}%",
                    delta=f"${ventas_actual_producto - ventas_anterior_producto:+,.0f}",
                    delta_color=delta_color
                )
            
            # Crear mini gráfico de barras comparativo
            color_producto = COLORES_LINEAS.get(producto_seleccionado, '#2E86AB')
            
            fig_comp = go.Figure()
            fig_comp.add_trace(go.Bar(
                x=[f'{año_anterior}', f'{año_actual}'],
                y=[ventas_anterior_producto, ventas_actual_producto],
                marker=dict(color=[color_producto, color_producto], opacity=[0.6, 1.0]),
                text=[f'${ventas_anterior_producto:,.0f}', f'${ventas_actual_producto:,.0f}'],
                textposition='outside'
            ))
            
            fig_comp.update_layout(
                title=f"<b>Ventas YTD - {producto_seleccionado}</b>",
                height=350,
                margin=dict(l=0, r=0, t=50, b=0),
                showlegend=False,
                yaxis=dict(showgrid=True, gridcolor='lightgray', title='Ventas USD'),
                xaxis=dict(showgrid=False, title='Año'),
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)'
            )
            
            st.plotly_chart(fig_comp, use_container_width=True)
        else:
            st.info(f"💡 No hay datos del producto **{producto_seleccionado}** para el año {año_anterior}")
    else:
        st.info("💡 Selecciona 'Comparar con año anterior' para ver análisis comparativo")
    
    st.markdown("---")
    
    # =====================================================================
    # SECCIÓN 4: ANÁLISIS DETALLADO (TABS)
    # =====================================================================
    st.header("🔍 Análisis Detallado")
    
    tab1, tab2 = st.tabs(["📋 Desglose Mensual", "👥 Detalle Clientes"])
    
    with tab1:
        st.subheader(f"Ventas Mensuales - {producto_seleccionado} (YTD {año_actual})")
        st.caption(f"📅 Desglose mensual del año {año_actual}. Para cambiar el periodo del análisis de clientes, usa el selector de periodo en Configuración.")
        df_ytd_copy = df_ytd_actual.copy()
        df_ytd_copy['mes'] = df_ytd_copy['fecha'].dt.month
        df_ytd_copy['mes_nombre'] = df_ytd_copy['fecha'].dt.strftime('%B')
        
        # Desglose mensual del producto
        desglose_mes = df_ytd_copy.groupby(['mes', 'mes_nombre'])['ventas_usd'].sum().reset_index()
        desglose_mes = desglose_mes.sort_values('mes')
        desglose_mes['ventas_acum'] = desglose_mes['ventas_usd'].cumsum()
        
        # Crear tabla pivote con meses como columnas
        st.markdown("**📊 Ventas por Mes**")
        tabla_meses = desglose_mes[['mes_nombre', 'ventas_usd', 'ventas_acum']].copy()
        tabla_meses.columns = ['Mes', 'Ventas', 'Acumulado']
        
        tabla_styled = tabla_meses.style\
            .format({'Ventas': '${:,.2f}', 'Acumulado': '${:,.2f}'})\
            .background_gradient(cmap='Blues', subset=['Ventas'])
        
        st.dataframe(tabla_styled, use_container_width=True, hide_index=True)
        
        # Gráfico de barras por mes
        fig_barras_mes = go.Figure()
        fig_barras_mes.add_trace(go.Bar(
            x=desglose_mes['mes_nombre'],
            y=desglose_mes['ventas_usd'],
            marker=dict(color=COLORES_LINEAS.get(producto_seleccionado, '#2E86AB')),
            text=desglose_mes['ventas_usd'],
            texttemplate='$%{text:,.0f}',
            textposition='outside'
        ))
        
        fig_barras_mes.update_layout(
            title=f"<b>Ventas Mensuales - {producto_seleccionado}</b>",
            xaxis_title='Mes',
            yaxis_title='Ventas USD',
            height=400,
            showlegend=False
        )
        
        st.plotly_chart(fig_barras_mes, use_container_width=True)
    
    with tab2:
        # Usar datos consistentes con el periodo del treemap
        if periodo_treemap == "ytd_actual":
            periodo_tab_label = f"YTD {año_actual}"
        elif periodo_treemap == "historico_completo":
            periodo_tab_label = "Histórico Completo"
        else:
            periodo_tab_label = f"Año {año_treemap}"
        
        st.subheader(f"Detalle de Clientes - {producto_seleccionado} ({periodo_tab_label})")
        
        # Análisis por cliente usando datos del periodo configurado
        clientes_detalle = df_analisis_clientes.groupby('cliente').agg({
            'ventas_usd': ['sum', 'count', 'mean']
        }).reset_index()
        
        clientes_detalle.columns = ['Cliente', 'Total Ventas', 'Num. Transacciones', 'Ticket Promedio']
        clientes_detalle = clientes_detalle.sort_values('Total Ventas', ascending=False)
        clientes_detalle['% Participación'] = (clientes_detalle['Total Ventas'] / clientes_detalle['Total Ventas'].sum() * 100)
        
        # Reordenar columnas
        clientes_detalle = clientes_detalle[['Cliente', 'Total Ventas', 'Num. Transacciones', 'Ticket Promedio', '% Participación']]
        
        st_detalle = clientes_detalle.style\
            .format({
                'Total Ventas': '${:,.2f}',
                'Num. Transacciones': '{:.0f}',
                'Ticket Promedio': '${:,.2f}',
                '% Participación': '{:.2f}%'
            })\
            .background_gradient(cmap='Greens', subset=['Total Ventas'])
        
        st.dataframe(
            st_detalle,
            hide_index=True,
            use_container_width=True,
            column_config={
                "Total Ventas": st.column_config.NumberColumn("Total Ventas", format="$%.2f"),
                "Num. Transacciones": st.column_config.NumberColumn("Transacciones", format="%.0f"),
                "Ticket Promedio": st.column_config.NumberColumn("Ticket Promedio", format="$%.2f"),
                "% Participación": st.column_config.ProgressColumn(
                    "Participación",
                    format="%.2f%%",
                    min_value=0,
                    max_value=100
                )
            }
        )
    
    st.markdown("---")
    
    # =====================================================================
    # PANEL DE DEFINICIONES Y FÓRMULAS
    # =====================================================================
    with st.expander("📐 **Definiciones y Fórmulas de KPIs**"):
        st.markdown("""
        ### 📊 Métricas Principales
        
        **💰 Total YTD (Year-To-Date)**
        - **Definición**: Suma acumulada de ventas desde el 1 de enero hasta la fecha de corte
        - **Fórmula**: `Σ Ventas (desde 01/Ene hasta fecha actual)`
        - **Uso**: Medir desempeño acumulado del año en curso
        
        **📈 Crecimiento YTD**
        - **Definición**: Variación porcentual respecto al mismo período del año anterior
        - **Fórmula**: `((YTD Actual - YTD Anterior) / YTD Anterior) × 100%`
        - **Interpretación**: 
          - ✅ Positivo = Crecimiento en ventas
          - ❌ Negativo = Decrecimiento
        
        **🏆 Línea #1**
        - **Definición**: Línea de negocio con mayor contribución a ventas YTD
        - **Cálculo**: `MAX(Σ Ventas por Línea)`
        - **Importancia**: Identificar drivers principales de ingresos
        
        **📅 Días Transcurridos**
        - **Definición**: Días corridos del año que se han completado
        - **Fórmula**: `(Fecha Corte - 01/Ene) + 1 día`
        - **Ejemplos**:
          - Si estamos analizando 2026 y hoy es 17/Feb: son 48 días
          - Si analizas 2024 completo: son los días hasta la última venta de 2024 (ej: 31/Dic = 366 días)
        - **Uso**: Base para calcular proyección anual (extrapolar ventas a 365 días)
        
        **🎯 Proyección Anual**
        - **Definición**: Estimación de ventas totales al cierre del año
        - **Fórmula**: `(Total YTD / Días Transcurridos) × 365 días`
        - **Supuesto**: Ritmo de ventas constante (promedio diario)
        - **Ejemplo**: Si en 48 días vendiste $100K, proyección = ($100K ÷ 48) × 365 = $760.4K
        
        **📊 Participación de Mercado (% Share)**
        - **Definición**: Contribución de cada línea al total de ventas
        - **Fórmula**: `(Ventas Línea / Total YTD) × 100%`
        - **Suma**: Siempre = 100%
        
        ---
        
        ### 🔄 Modos de Comparación
        
        **YTD vs YTD** (Recomendado)
        - Compara mismo período de días en ambos años
        - Ejemplo: Primeros 48 días de 2025 vs primeros 48 días de 2024
        - ✅ Comparación justa y balanceada
        
        **YTD vs Año Completo**
        - Compara YTD actual contra año anterior completo (365 días)
        - ⚠️ Útil para ver progreso hacia meta anual
        - No recomendado para calcular crecimiento real
        
        ---
        
        ### 📝 Notas Importantes
        
        - **Crecimiento desde $0**: Cuando año anterior = 0, el crecimiento se escala relativamente (cap 999%)
        - **Días del Año Actual vs Histórico**: 
          - Año actual (ej: 2026): Días desde 01/Ene hasta HOY (fecha real del sistema)
          - Años pasados (ej: 2024): Días desde 01/Ene hasta la ÚLTIMA VENTA registrada ese año
          - Ejemplo: Si la última venta de 2024 fue el 31/Dic, días transcurridos = 366
        - **Colores en Gráficos**: Asignados consistentemente por producto
        - **Filtros**: Aplicables por vendedor, cliente o producto
        """)
    
    st.markdown("---")
    
    # =====================================================================
    # SECCIÓN 5: EXPORTACIÓN
    # =====================================================================
    user = get_current_user()
    puede_exportar = user and user.can_export()
    
    if puede_exportar:
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
            
            # Opción 1: CSV YTD actual
            csv_buffer = df_ytd_actual.to_csv(index=False).encode('utf-8')
            st.download_button(
                label=f"📥 CSV - YTD {año_actual}",
                data=csv_buffer,
                file_name=f"Datos_YTD_{año_actual}_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                key="csv_ytd_actual"
            )
            st.caption(f"Datos YTD {año_actual} ({len(df_ytd_actual)} registros)")
            
            # Opción 2: CSV del periodo del treemap (si es diferente)
            if periodo_treemap != "ytd_actual":
                csv_periodo = df_analisis_clientes.to_csv(index=False).encode('utf-8')
                if periodo_treemap == "historico_completo":
                    label_csv = "📥 CSV - Histórico Completo"
                    fname_csv = f"Datos_Historico_{producto_seleccionado}_{datetime.now().strftime('%Y%m%d')}.csv"
                else:
                    label_csv = f"📥 CSV - Año {año_treemap}"
                    fname_csv = f"Datos_{año_treemap}_{producto_seleccionado}_{datetime.now().strftime('%Y%m%d')}.csv"
                
                st.download_button(
                    label=label_csv,
                    data=csv_periodo,
                    file_name=fname_csv,
                    mime="text/csv",
                    key="csv_periodo_treemap"
                )
                st.caption(f"Datos del periodo configurado ({len(df_analisis_clientes)} registros)")
    else:
        st.warning("⚠️ Las funciones de exportación están disponibles solo para usuarios con rol **Analyst** o **Admin**")
        st.info("💡 Contacta al administrador para solicitar acceso a exportaciones")
    
    # Footer con información
    st.markdown("---")
    # Footer: mostrar periodo real analizado
    if periodo_treemap == "ytd_actual":
        periodo_footer = f"YTD {año_actual} (01/01/{año_actual} - {datetime.now().strftime('%d/%m/%Y')})"
    elif periodo_treemap == "historico_completo":
        fecha_min_hist = df['fecha'].min()
        fecha_max_hist = df['fecha'].max()
        periodo_footer = f"Histórico Completo ({fecha_min_hist.strftime('%d/%m/%Y')} - {fecha_max_hist.strftime('%d/%m/%Y')})"
    else:
        periodo_footer = f"Año {año_treemap}"
    
    st.caption(
        f"📅 Reporte generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | "
        f"Producto: {producto_seleccionado} | "
        f"Periodo principal: YTD {año_actual} | "
        f"Periodo treemap/clientes: {periodo_footer}"
    )
