"""
Módulo: Reporte Consolidado - Dashboard Ejecutivo
Autor: Dashboard Fradma
Fecha: Febrero 2026

Funcionalidad:
- Consolidación de ventas y CxC en un solo reporte
- Análisis por período: semanal, mensual, trimestral, anual
- Visualizaciones ejecutivas de alto nivel
- Integración con análisis de IA
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import os
from utils.logger import configurar_logger
from utils.ai_helper import validar_api_key, generar_analisis_consolidado_ia
from utils.filters_helper import obtener_lineas_filtradas, generar_contexto_filtros
from utils.cxc_helper import calcular_metricas_basicas, calcular_score_salud, clasificar_score_salud, calcular_dias_overdue
from utils.data_normalizer import normalizar_datos_cxc, normalizar_columna_fecha, detectar_columnas_cxc
from utils.constantes import DIAS_CREDITO_ESTANDAR

# Configurar logger
logger = configurar_logger("reporte_consolidado", nivel="INFO")


def agrupar_por_periodo(df, tipo_periodo='mensual'):
    """
    Agrupa un DataFrame de ventas por el período especificado.
    
    Args:
        df: DataFrame con columna 'fecha' y valores numéricos
        tipo_periodo: 'semanal', 'mensual', 'trimestral', 'anual'
        
    Returns:
        DataFrame agrupado con período como índice
    """
    df = df.copy()
    df['fecha'] = pd.to_datetime(df['fecha'], errors='coerce')
    df = df.dropna(subset=['fecha'])
    
    if tipo_periodo == 'semanal':
        df['periodo'] = df['fecha'].dt.to_period('W').dt.start_time
        df['periodo_label'] = df['fecha'].dt.strftime('Sem %U - %Y')
    elif tipo_periodo == 'mensual':
        df['periodo'] = df['fecha'].dt.to_period('M').dt.start_time
        df['periodo_label'] = df['fecha'].dt.strftime('%b %Y')
    elif tipo_periodo == 'trimestral':
        df['periodo'] = df['fecha'].dt.to_period('Q').dt.start_time
        df['periodo_label'] = df['fecha'].dt.to_period('Q').astype(str)
    elif tipo_periodo == 'anual':
        df['periodo'] = df['fecha'].dt.to_period('Y').dt.start_time
        df['periodo_label'] = df['fecha'].dt.year.astype(str)
    else:
        raise ValueError(f"Tipo de período no válido: {tipo_periodo}")
    
    return df


def crear_grafico_ventas_periodo(df_agrupado, tipo_periodo):
    """Crea un gráfico de barras/líneas de ventas por período."""
    
    # Agrupar y sumar ventas
    ventas_periodo = df_agrupado.groupby(['periodo', 'periodo_label'])['ventas_usd'].sum().reset_index()
    ventas_periodo = ventas_periodo.sort_values('periodo')
    
    # Crear gráfico combinado
    fig = go.Figure()
    
    # Barras
    fig.add_trace(go.Bar(
        x=ventas_periodo['periodo_label'],
        y=ventas_periodo['ventas_usd'],
        name='Ventas',
        marker_color='#1f77b4',
        text=ventas_periodo['ventas_usd'],
        texttemplate='$%{text:,.0f}',
        textposition='outside'
    ))
    
    # Línea de tendencia
    fig.add_trace(go.Scatter(
        x=ventas_periodo['periodo_label'],
        y=ventas_periodo['ventas_usd'],
        name='Tendencia',
        mode='lines+markers',
        line=dict(color='#ff7f0e', width=3),
        marker=dict(size=8)
    ))
    
    titulo_periodo = {
        'semanal': 'Ventas por Semana',
        'mensual': 'Ventas por Mes',
        'trimestral': 'Ventas por Trimestre',
        'anual': 'Ventas por Año'
    }
    
    fig.update_layout(
        title=titulo_periodo.get(tipo_periodo, 'Ventas por Período'),
        xaxis_title='Período',
        yaxis_title='Ventas USD',
        hovermode='x unified',
        showlegend=True,
        height=450,
        template='plotly_white'
    )
    
    return fig


def crear_pie_cxc(metricas_cxc):
    """Crea un gráfico de pie para distribución de CxC."""
    
    labels = ['Vigente', 'Vencida 0-30', 'Vencida 31-60', 'Vencida 61-90', 'Alto Riesgo >90']
    values = [
        metricas_cxc.get('vigente', 0),
        metricas_cxc.get('vencida_0_30', 0),
        metricas_cxc.get('vencida_31_60', 0),
        metricas_cxc.get('vencida_61_90', 0),
        metricas_cxc.get('alto_riesgo', 0)
    ]
    colors = ['#4CAF50', '#FFC107', '#FF9800', '#FF5722', '#F44336']
    
    fig = go.Figure(data=[go.Pie(
        labels=labels,
        values=values,
        marker=dict(colors=colors),
        hole=0.4,
        textinfo='label+percent+value',
        texttemplate='%{label}<br>%{percent}<br>$%{value:,.0f}',
        hovertemplate='<b>%{label}</b><br>Monto: $%{value:,.2f}<br>Porcentaje: %{percent}<extra></extra>'
    )])
    
    fig.update_layout(
        title='Distribución de Cuentas por Cobrar',
        showlegend=True,
        height=450,
        template='plotly_white'
    )
    
    return fig


# =====================================================================
# FUNCIONES HELPER PRIVADAS
# =====================================================================

def _preparar_datos_iniciales(df_ventas, df_cxc):
    """
    Normaliza y prepara datos iniciales de ventas y CxC.
    
    Returns:
        Tuple (df_ventas, df_cxc) normalizados
    """
    # Usar normalización centralizada
    df_ventas, df_cxc = normalizar_datos_cxc(df_ventas, df_cxc)
    
    # Normalizar fechas
    df_ventas = normalizar_columna_fecha(df_ventas, 'fecha')
    
    # NOTA: No hace falta calcular dias_overdue aquí porque preparar_datos_cxc()
    # lo hace automáticamente en _calcular_metricas_cxc
    
    return df_ventas, df_cxc


def _obtener_configuracion_ui(habilitar_ia=False, openai_api_key=None):
    """
    Obtiene configuración de periodicidad desde sidebar.
    Los parámetros de IA vienen del passkey premium global.
    
    Args:
        habilitar_ia: Estado de IA desde passkey premium
        openai_api_key: API key desde passkey premium
        
    Returns:
        Dict con configuración {'tipo_periodo', 'habilitar_ia', 'api_key'}
    """
    st.sidebar.markdown("---")
    st.sidebar.header("⚙️ Configuración del Reporte")
    
    # Selector de periodicidad
    tipo_periodo = st.sidebar.selectbox(
        "📅 Periodicidad",
        options=['semanal', 'mensual', 'trimestral', 'anual'],
        index=1,
        format_func=lambda x: {
            'semanal': '📆 Semanal',
            'mensual': '📅 Mensual',
            'trimestral': '📊 Trimestral',
            'anual': '📈 Anual'
        }[x],
        help="Selecciona el período de agrupación para el análisis",
        key="consolidado_periodicidad"
    )
    
    # IA controlada desde el passkey premium global (no checkbox local)

    
    return {
        'tipo_periodo': tipo_periodo,
        'habilitar_ia': habilitar_ia,
        'api_key': openai_api_key
    }


def _calcular_metricas_ventas(df_ventas, tipo_periodo):
    """
    Agrupa ventas por período y calcula métricas.
    
    Returns:
        Dict con métricas de ventas
    """
    # Renombrar para compatibilidad
    df_ventas_proc = df_ventas.rename(columns={'valor_usd': 'ventas_usd'})
    
    # Agrupar por período
    df_agrupado = agrupar_por_periodo(df_ventas_proc, tipo_periodo)
    
    # Calcular métricas
    total_ventas = df_agrupado['ventas_usd'].sum()
    ventas_por_periodo = df_agrupado.groupby('periodo')['ventas_usd'].sum().sort_index()
    periodos_count = len(ventas_por_periodo)
    promedio_periodo = total_ventas / periodos_count if periodos_count > 0 else 0
    
    # Calcular crecimiento
    crecimiento_pct = 0
    if len(ventas_por_periodo) >= 2:
        ultimo = ventas_por_periodo.iloc[-1]
        penultimo = ventas_por_periodo.iloc[-2]
        if penultimo > 0:
            crecimiento_pct = ((ultimo - penultimo) / penultimo) * 100
    
    return {
        'df_agrupado': df_agrupado,
        'total': total_ventas,
        'promedio': promedio_periodo,
        'total_periodos': periodos_count,
        'crecimiento_pct': crecimiento_pct
    }


def _calcular_metricas_cxc(df_cxc):
    """
    Calcula métricas de CxC.
    
    Returns:
        Dict con métricas de CxC o None si no hay datos
    """
    if df_cxc is None or df_cxc.empty:
        return None
    
    try:
        # IMPORTANTE: Usar preparar_datos_cxc para excluir registros pagados
        # calcular_metricas_basicas espera recibir SOLO registros no pagados (df_np)
        from utils.cxc_helper import preparar_datos_cxc
        _, df_cxc_no_pagados, _ = preparar_datos_cxc(df_cxc)
        
        # Ahora calcular métricas sobre datos no pagados
        metricas = calcular_metricas_basicas(df_cxc_no_pagados)
        score = calcular_score_salud(
            metricas['pct_vigente'], 
            metricas['pct_critica'],
            metricas.get('pct_vencida_0_30', 0),
            metricas.get('pct_vencida_31_60', 0),
            metricas.get('pct_vencida_61_90', 0),
            metricas.get('pct_alto_riesgo', 0)
        )
        status, _ = clasificar_score_salud(score)
        
        return {
            'metricas': metricas,
            'score': score,
            'status': status
        }
    except Exception as e:
        logger.error(f"Error calculando métricas CxC: {e}")
        return None


# =====================================================================
# FUNCIONES DE RENDERIZADO
# =====================================================================

def _renderizar_kpis(total_ventas, promedio_periodo, crecimiento_ventas_pct, 
                     periodos_count, metricas_cxc, score_salud_cxc, 
                     score_status_cxc, config):
    """
    Sección 1: Renderiza los KPIs principales.
    
    Args:
        total_ventas: Total de ventas en USD
        promedio_periodo: Promedio de ventas por período
        crecimiento_ventas_pct: Porcentaje de crecimiento
        periodos_count: Número de períodos analizados
        metricas_cxc: Dict con métricas de CxC o None
        score_salud_cxc: Score de salud CxC o None
        score_status_cxc: Status textual del score o None
        config: Dict con configuración (tipo_periodo, etc)
    """
    st.header("📈 Métricas Principales")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="💰 Total Ventas",
            value=f"${total_ventas:,.0f}",
            delta=f"{crecimiento_ventas_pct:+.1f}% vs período anterior" if crecimiento_ventas_pct != 0 else None
        )
    
    with col2:
        st.metric(
            label=f"📊 Promedio por {config['tipo_periodo'].capitalize()}",
            value=f"${promedio_periodo:,.0f}",
            delta=f"{periodos_count} períodos"
        )
    
    with col3:
        if metricas_cxc:
            st.metric(
                label="💳 Total CxC",
                value=f"${metricas_cxc['total_adeudado']:,.0f}",
                delta=f"{metricas_cxc['pct_vigente']:.1f}% vigente"
            )
        else:
            st.metric(
                label="💳 CxC",
                value="N/A",
                delta="Sin datos"
            )
    
    with col4:
        if score_salud_cxc:
            st.metric(
                label="🏥 Salud CxC",
                value=f"{score_salud_cxc:.0f}/100",
                delta=score_status_cxc
            )
        else:
            st.metric(
                label="🏥 Salud CxC",
                value="N/A",
                delta="Sin datos"
            )
    
    st.markdown("---")


def _renderizar_visualizaciones(df_ventas_agrupado, metricas_cxc, config):
    """
    Sección 2: Renderiza gráficos de ventas y CxC.
    
    Args:
        df_ventas_agrupado: DataFrame con ventas agrupadas por período
        metricas_cxc: Dict con métricas de CxC o None
        config: Dict con configuración (tipo_periodo, etc)
    """
    col_left, col_right = st.columns([6, 4])
    
    with col_left:
        st.subheader(f"📊 Evolución de Ventas ({config['tipo_periodo'].capitalize()})")
        fig_ventas = crear_grafico_ventas_periodo(df_ventas_agrupado, config['tipo_periodo'])
        st.plotly_chart(fig_ventas, use_container_width=True)
    
    with col_right:
        if metricas_cxc:
            st.subheader("💳 Distribución de CxC")
            fig_cxc = crear_pie_cxc(metricas_cxc)
            st.plotly_chart(fig_cxc, use_container_width=True)
        else:
            st.info("📋 Datos de CxC no disponibles\n\nSube un archivo de CxC en la sección correspondiente para ver esta visualización.")
    
    st.markdown("---")


def _renderizar_analisis_ia(total_ventas, crecimiento_ventas_pct, metricas_cxc, 
                            score_salud_cxc, config, lineas_filtrar=None):
    """
    Sección 4: Renderiza análisis con IA (opcional, al final como skill avanzado).
    
    Args:
        total_ventas: Total de ventas en USD
        crecimiento_ventas_pct: Porcentaje de crecimiento
        metricas_cxc: Dict con métricas de CxC o None
        score_salud_cxc: Score de salud CxC o None
        lineas_filtrar: Lista de líneas de negocio filtradas o None
        config: Dict con configuración (habilitar_ia, api_key, tipo_periodo)
    """
    if not config['habilitar_ia'] or not config['api_key']:
        return
    
    # Asegurar que lineas_filtrar sea siempre una lista
    if lineas_filtrar is None:
        lineas_filtrar = []
    
    # Separador visual para indicar nueva sección avanzada
    st.markdown("---")
    st.markdown("## 🤖 Análisis Avanzado con Inteligencia Artificial")
    st.caption("💡 Insights generados por IA basados en los datos anteriores")
    
    # Obtener filtros configurados
    periodo_seleccionado = st.session_state.get("analisis_periodo", "Todos los datos")
    lineas_seleccionadas = st.session_state.get("analisis_lineas", ["Todas"])
    
    st.info(
        f"📋 **Configuración:** Periodo: {periodo_seleccionado} | "
        f"Líneas: {', '.join(lineas_seleccionadas[:3])}{'...' if len(lineas_seleccionadas) > 3 else ''}"
    )
    
    periodo_label = {
        'semanal': 'Análisis Semanal',
        'mensual': 'Análisis Mensual',
        'trimestral': 'Análisis Trimestral',
        'anual': 'Análisis Anual'
    }[config['tipo_periodo']]
    
    # Valores de CxC (usar 0 si no hay datos)
    _total_cxc = metricas_cxc['total_adeudado'] if metricas_cxc else 0
    _pct_vigente = metricas_cxc['pct_vigente'] if metricas_cxc else 0
    _pct_critica = metricas_cxc['pct_critica'] if metricas_cxc else 0
    _score_salud = score_salud_cxc if score_salud_cxc else 0
    
    # Botón para ejecutar análisis
    if st.button("🚀 Generar Análisis con IA", type="primary", use_container_width=True, key="btn_ia_consolidado"):
        with st.spinner("🔄 Generando análisis ejecutivo consolidado con GPT-4o-mini..."):
            try:
                # Preparar contexto de filtros para IA
                contexto_filtros = generar_contexto_filtros(lineas_filtrar) if lineas_filtrar else None
                
                analisis = generar_analisis_consolidado_ia(
                    total_ventas=total_ventas,
                    crecimiento_ventas_pct=crecimiento_ventas_pct,
                    total_cxc=_total_cxc,
                    pct_vigente_cxc=_pct_vigente,
                    pct_critica_cxc=_pct_critica,
                    score_salud_cxc=_score_salud,
                    periodo_analisis=periodo_label,
                    api_key=config['api_key'],
                    contexto_filtros=contexto_filtros
                )
                
                # Mostrar análisis
                if analisis:
                    st.markdown("### 📋 Resumen Ejecutivo")
                    st.info(analisis.get('resumen_ejecutivo', 'No disponible'))
                    
                    col_izq, col_der = st.columns(2)
                    
                    with col_izq:
                        st.markdown("### ⭐ Highlights Clave")
                        highlights = analisis.get('highlights_clave', [])
                        if highlights:
                            for h in highlights:
                                st.markdown(f"- {h}")
                        else:
                            st.caption("No disponible")
                        
                        st.markdown("")
                        st.markdown("### 💡 Insights Principales")
                        insights = analisis.get('insights_principales', [])
                        if insights:
                            for i in insights:
                                st.markdown(f"- {i}")
                        else:
                            st.caption("No disponible")
                    
                    with col_der:
                        st.markdown("### ⚠️ Áreas de Atención")
                        areas = analisis.get('areas_atencion', [])
                        if areas:
                            for a in areas:
                                st.markdown(f"- {a}")
                        else:
                            st.caption("No hay áreas críticas")
                        
                        st.markdown("")
                        st.markdown("### 🎯 Recomendaciones Ejecutivas")
                        recs = analisis.get('recomendaciones_ejecutivas', [])
                        if recs:
                            for r in recs:
                                st.markdown(f"- {r}")
                        else:
                            st.caption("No disponible")
                    
                    st.caption("🤖 Análisis generado por OpenAI GPT-4o-mini")
                else:
                    st.warning("⚠️ No se pudo generar el análisis")
            
            except Exception as e:
                st.error(f"❌ Error al generar análisis con IA: {str(e)}")
                logger.error(f"Error en análisis IA consolidado: {e}", exc_info=True)
    else:
        st.caption("👆 Presiona el botón para generar análisis consolidado según tus filtros")


def _renderizar_tabla_detalle(df_ventas_agrupado, periodos_count, config):
    """
    Sección 3: Renderiza tabla detallada por período (análisis natural).
    
    Args:
        df_ventas_agrupado: DataFrame con ventas agrupadas
        periodos_count: Número de períodos analizados
        config: Dict con configuración (tipo_periodo, etc)
    """
    st.header(f"📋 Detalle por {config['tipo_periodo'].capitalize()}")
    
    # Preparar tabla resumen
    tabla_resumen = df_ventas_agrupado.groupby(['periodo', 'periodo_label']).agg({
        'ventas_usd': 'sum'
    }).reset_index()
    tabla_resumen = tabla_resumen.sort_values('periodo', ascending=False)
    
    # Calcular crecimiento período a período
    tabla_resumen['crecimiento'] = tabla_resumen['ventas_usd'].pct_change(periods=-1) * 100
    
    # Formatear para display
    tabla_display = tabla_resumen[['periodo_label', 'ventas_usd', 'crecimiento']].copy()
    tabla_display.columns = ['Período', 'Ventas USD', 'Crecimiento %']
    
    st.dataframe(
        tabla_display.style.format({
            'Ventas USD': '${:,.2f}',
            'Crecimiento %': '{:+.1f}%'
        }).background_gradient(subset=['Crecimiento %'], cmap='RdYlGn', vmin=-20, vmax=20),
        use_container_width=True,
        hide_index=True
    )


def run(df_ventas, df_cxc=None, habilitar_ia=False, openai_api_key=None):
    """
    Función principal del Reporte Consolidado.
    
    Args:
        df_ventas: DataFrame con datos de ventas
        df_cxc: DataFrame opcional con datos de CxC
        habilitar_ia: Booleano para activar análisis con IA (default: False)
        openai_api_key: API key de OpenAI para análisis premium (default: None)
    """
    st.title("📊 Reporte Consolidado - Dashboard Ejecutivo")
    st.markdown("---")
    
    # =====================================================================
    # PASO 1: PREPARAR Y NORMALIZAR DATOS
    # =====================================================================
    df_ventas, df_cxc = _preparar_datos_iniciales(df_ventas, df_cxc)
    
    # =====================================================================
    # PASO 2: VALIDACIONES BÁSICAS
    # =====================================================================
    if "valor_usd" not in df_ventas.columns or "fecha" not in df_ventas.columns:
        st.error("❌ El DataFrame de ventas no tiene las columnas requeridas (valor_usd, fecha)")
        with st.expander("🔍 Ver columnas disponibles"):
            st.write("**Columnas detectadas:**")
            st.write(sorted(df_ventas.columns.tolist()))
        st.info("💡 Este reporte requiere: **fecha** y **ventas_usd** (o sus variantes)")
        return
    
    # Limpiar datos sin fecha o ventas
    df_ventas_limpio = df_ventas.dropna(subset=['fecha', 'valor_usd'])
    df_ventas_limpio = df_ventas_limpio[df_ventas_limpio['valor_usd'] > 0]
    
    if len(df_ventas_limpio) == 0:
        st.warning("⚠️ No hay datos de ventas válidos para procesar")
        return
    
    logger.info(f"Procesando {len(df_ventas_limpio)} registros válidos de ventas")
    
    # =====================================================================
    # PASO 3: OBTENER CONFIGURACIÓN DE UI Y FILTROS
    # =====================================================================
    config = _obtener_configuracion_ui(habilitar_ia, openai_api_key)
    
    # Inicializar lineas_filtrar al inicio para que esté disponible en todo el scope
    lineas_seleccionadas = st.session_state.get("analisis_lineas", ["Todas"])
    try:
        lineas_filtrar = obtener_lineas_filtradas(lineas_seleccionadas)
    except Exception as e:
        logger.warning(f"Error al obtener líneas filtradas: {e}")
        lineas_filtrar = []  # Asegurar que siempre esté definida
    
    # =====================================================================
    # PASO 3.5: APLICAR FILTROS DE LÍNEAS DE NEGOCIO (para análisis IA)
    # =====================================================================
    if lineas_filtrar:
        # Filtrar ventas
        if "linea_de_negocio" in df_ventas_limpio.columns:
            df_ventas_limpio = df_ventas_limpio[df_ventas_limpio['linea_de_negocio'].isin(lineas_filtrar)]
            logger.info(f"✅ Datos filtrados por líneas: {lineas_filtrar}. Registros: {len(df_ventas_limpio)}")
        else:
            logger.warning(f"❌ Columna 'linea_de_negocio' no existe. Columnas disponibles: {df_ventas_limpio.columns.tolist()}")
        
        # Filtrar CxC
        if df_cxc is not None and "linea_negocio" in df_cxc.columns:
            df_cxc = df_cxc[df_cxc['linea_negocio'].isin(lineas_filtrar)]
            logger.info(f"✅ CxC filtrado por líneas. Registros: {len(df_cxc)}")
    
    # =====================================================================
    # PASO 4: CALCULAR MÉTRICAS (con datos ya filtrados)
    # =====================================================================
    # Renombrar para compatibilidad con funciones de agrupamiento
    df_ventas_limpio = df_ventas_limpio.rename(columns={'valor_usd': 'ventas_usd'})
    
    metricas_ventas = _calcular_metricas_ventas(df_ventas_limpio, config['tipo_periodo'])
    metricas_cxc_dict = _calcular_metricas_cxc(df_cxc)
    
    # Validar que se obtuvieron datos agrupados
    if metricas_ventas is None or metricas_ventas['df_agrupado'] is None:
        st.error("❌ Error al procesar datos de ventas")
        return
    
    # Extraer métricas de ventas
    df_ventas_agrupado = metricas_ventas['df_agrupado']
    total_ventas = metricas_ventas['total']
    promedio_periodo = metricas_ventas['promedio']
    crecimiento_ventas_pct = metricas_ventas['crecimiento_pct']
    periodos_count = metricas_ventas['total_periodos']
    
    # Extraer métricas de CxC (si están disponibles)
    metricas_cxc = metricas_cxc_dict.get('metricas', None) if metricas_cxc_dict else None
    score_salud_cxc = metricas_cxc_dict.get('score', None) if metricas_cxc_dict else None
    score_status_cxc = metricas_cxc_dict.get('status', None) if metricas_cxc_dict else None
    
    # =====================================================================
    # PASO 5: RENDERIZAR REPORTES (Orden: análisis natural → análisis IA)
    # =====================================================================
    
    # Sección 1: KPIs principales
    _renderizar_kpis(
        total_ventas, promedio_periodo, crecimiento_ventas_pct, 
        periodos_count, metricas_cxc, score_salud_cxc, 
        score_status_cxc, config
    )
    
    # Sección 2: Visualizaciones (gráficos de ventas y CxC)
    _renderizar_visualizaciones(df_ventas_agrupado, metricas_cxc, config)
    
    # Sección 3: Tabla detallada por período (análisis natural)
    _renderizar_tabla_detalle(df_ventas_agrupado, periodos_count, config)
    
    # Sección 4: Análisis con IA (opcional, al final como skill avanzado)
    _renderizar_analisis_ia(
        total_ventas, crecimiento_ventas_pct, metricas_cxc, 
        score_salud_cxc, config, lineas_filtrar
    )
    
    # =====================================================================
    # FOOTER: Información del reporte
    # =====================================================================
    st.markdown("---")
    st.caption(f"📅 Reporte generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | "
              f"Período: {config['tipo_periodo'].capitalize()} | "
              f"Períodos analizados: {periodos_count}")
