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
from utils.cxc_helper import calcular_metricas_basicas, calcular_score_salud, clasificar_score_salud, calcular_dias_overdue

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
    
    labels = ['Vigente', 'Vencida 0-30', 'Vencida 30-60', 'Vencida 60-90', 'Crítica >90']
    values = [
        metricas_cxc.get('vigente', 0),
        metricas_cxc.get('vencida_0_30', 0),
        metricas_cxc.get('vencida_30_60', 0),
        metricas_cxc.get('vencida_60_90', 0),
        metricas_cxc.get('critica', 0)
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


def run(df_ventas, df_cxc=None):
    """
    Función principal del Reporte Consolidado.
    
    Args:
        df_ventas: DataFrame con datos de ventas
        df_cxc: DataFrame opcional con datos de CxC
    """
    st.title("📊 Reporte Consolidado - Dashboard Ejecutivo")
    st.markdown("---")
    
    # =====================================================================
    # NORMALIZACIÓN - Igual que Reporte Ejecutivo
    # =====================================================================
    
    # Trabajar sobre copias locales
    df_ventas = df_ventas.copy() if df_ventas is not None else pd.DataFrame()
    df_cxc = df_cxc.copy() if df_cxc is not None else pd.DataFrame()
    
    # Normalizar columna de ventas
    if "valor_usd" not in df_ventas.columns:
        for candidato in ["ventas_usd_con_iva", "ventas_usd", "importe", "monto_usd", "total_usd", "valor"]:
            if candidato in df_ventas.columns:
                df_ventas = df_ventas.rename(columns={candidato: "valor_usd"})
                break
    
    if "valor_usd" in df_ventas.columns:
        df_ventas["valor_usd"] = pd.to_numeric(df_ventas["valor_usd"], errors="coerce").fillna(0)
    else:
        df_ventas["valor_usd"] = 0
        st.warning("⚠️ No se encontró columna de ventas en USD")
        return
    
    # Normalizar columna de fecha
    if "fecha" in df_ventas.columns:
        df_ventas["fecha"] = pd.to_datetime(df_ventas["fecha"], errors="coerce")
    else:
        st.warning("⚠️ No se encontró columna de fecha")
        return
    
    # Normalizar CxC si está disponible
    if not df_cxc.empty:
        if "saldo_adeudado" not in df_cxc.columns:
            for candidato in ["saldo", "saldo_adeudo", "adeudo", "importe", "monto", "total", "saldo_usd"]:
                if candidato in df_cxc.columns:
                    df_cxc = df_cxc.rename(columns={candidato: "saldo_adeudado"})
                    break
        
        if "saldo_adeudado" in df_cxc.columns:
            saldo_txt = df_cxc["saldo_adeudado"].astype(str)
            saldo_txt = saldo_txt.str.replace(",", "", regex=False).str.replace("$", "", regex=False)
            df_cxc["saldo_adeudado"] = pd.to_numeric(saldo_txt, errors="coerce").fillna(0)
    
    # =====================================================================
    # SI NO HAY HOJA CXC SEPARADA, USAR DATOS DE VENTAS (IGUAL QUE REPORTE EJECUTIVO)
    # =====================================================================
    if df_cxc.empty:
        cols_cartera = {
            "saldo", "saldo_usd", "saldo_adeudado",
            "dias_restante", "dias_restantes", "dias_de_credito", "dias_de_credit",
            "vencimient", "vencimiento",
            "fecha_de_pago", "fecha_pago", "fecha_tentativa_de_pag", "fecha_tentativa_de_pago",
            "estatus", "status", "pagado",
        }
        if len(cols_cartera.intersection(set(df_ventas.columns))) > 0:
            df_cxc = df_ventas.copy()
            logger.info("CxC: usando datos de la hoja de ventas (X AGENTE)")
    
    # Normalizar saldo de CxC si se tomó de ventas
    if not df_cxc.empty and "saldo_adeudado" not in df_cxc.columns:
        for candidato in ["saldo", "saldo_adeudo", "adeudo", "saldo_usd"]:
            if candidato in df_cxc.columns:
                df_cxc = df_cxc.rename(columns={candidato: "saldo_adeudado"})
                break
    
    if not df_cxc.empty and "saldo_adeudado" in df_cxc.columns:
        saldo_txt = df_cxc["saldo_adeudado"].astype(str)
        saldo_txt = saldo_txt.str.replace(",", "", regex=False).str.replace("$", "", regex=False)
        df_cxc["saldo_adeudado"] = pd.to_numeric(saldo_txt, errors="coerce").fillna(0)
        
        # Excluir pagados
        col_estatus = None
        for col in ["estatus", "status", "pagado"]:
            if col in df_cxc.columns:
                col_estatus = col
                break
        if col_estatus:
            estatus_norm = df_cxc[col_estatus].astype(str).str.strip().str.lower()
            df_cxc = df_cxc[~estatus_norm.str.contains("pagado", na=False)]
        
        # Calcular dias_overdue usando función robusta de cxc_helper
        if "dias_overdue" not in df_cxc.columns:
            # Verificar qué columnas están disponibles para el cálculo
            columnas_cxc_disponibles = set(df_cxc.columns)
            columnas_ideales = {"vencimiento", "fecha_vencimiento", "dias_restantes", "dias_restante", "dias_vencido"}
            
            if not columnas_cxc_disponibles.intersection(columnas_ideales):
                st.warning("⚠️ Los datos de CxC no contienen columnas de vencimiento. Se estimará usando fecha de factura + 30 días de crédito estándar.")
                logger.warning(f"CxC sin columnas de vencimiento. Usando estimación. Columnas disponibles: {list(df_cxc.columns)}")
            
            df_cxc["dias_overdue"] = calcular_dias_overdue(df_cxc)
            logger.info(f"dias_overdue calculado - min: {df_cxc['dias_overdue'].min():.0f}, max: {df_cxc['dias_overdue'].max():.0f}")
            logger.info(f"Registros vigentes (dias_overdue <= 0): {(df_cxc['dias_overdue'] <= 0).sum()}")
            logger.info(f"Registros vencidos (dias_overdue > 0): {(df_cxc['dias_overdue'] > 0).sum()}")
        
        logger.info(f"CxC normalizado: {len(df_cxc)} registros, saldo total: ${df_cxc['saldo_adeudado'].sum():,.2f}")
    
    # =====================================================================
    # CONFIGURACIÓN
    # =====================================================================
    
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
    
    # Configuración de IA
    st.sidebar.markdown("---")
    st.sidebar.subheader("🤖 Análisis con IA")
    
    habilitar_ia = st.sidebar.checkbox(
        "Habilitar Análisis Consolidado con IA",
        value=False,
        help="Genera insights ejecutivos integrales sobre ventas y CxC",
        key="consolidado_habilitar_ia"
    )
    
    openai_api_key = None
    if habilitar_ia:
        api_key_env = os.getenv("OPENAI_API_KEY", "")
        
        if api_key_env:
            openai_api_key = api_key_env
            st.sidebar.success("✅ API key detectada desde variable de entorno")
        else:
            openai_api_key = st.sidebar.text_input(
                "OpenAI API Key",
                type="password",
                help="Ingresa tu API key de OpenAI",
                key="consolidado_api_key"
            )
            
            if openai_api_key:
                if validar_api_key(openai_api_key):
                    st.sidebar.success("✅ API key válida")
                else:
                    st.sidebar.error("❌ API key inválida")
                    openai_api_key = None
        
        st.sidebar.caption("💡 El análisis con IA conecta ventas con liquidez y salud financiera")
    
    # =====================================================================
    # PROCESAMIENTO DE DATOS DE VENTAS
    # =====================================================================
    
    logger.info("Validando columnas requeridas...")
    
    # Validar que existan las columnas requeridas después de normalización
    required_cols = ['fecha', 'valor_usd']
    missing_cols = [col for col in required_cols if col not in df_ventas.columns]
    
    if missing_cols:
        logger.error(f"Faltan columnas: {missing_cols}")
        logger.error(f"Columnas disponibles después de normalización: {list(df_ventas.columns)}")
        st.error(f"❌ Faltan columnas requeridas: {', '.join(missing_cols)}")
        with st.expander("🔍 Ver columnas disponibles"):
            st.write("**Columnas detectadas:**")
            st.write(sorted(df_ventas.columns.tolist()))
        st.info("💡 Este reporte requiere: **fecha** y **ventas_usd** (o sus variantes)")
        return
    
    logger.info("✅ Columnas requeridas encontradas")
    
    # Limpiar datos: eliminar filas sin fecha o ventas nulas/cero
    registros_original = len(df_ventas)
    df_ventas_limpio = df_ventas.dropna(subset=['fecha', 'valor_usd'])
    df_ventas_limpio = df_ventas_limpio[df_ventas_limpio['valor_usd'] > 0]
    registros_limpio = len(df_ventas_limpio)
    
    logger.info(f"Limpieza de datos: {registros_original} → {registros_limpio} registros")
    
    if len(df_ventas_limpio) == 0:
        logger.error("No hay datos válidos después de limpieza")
        st.warning("⚠️ No hay datos de ventas válidos para procesar")
        st.info(f"Registros originales: {registros_original}, después de limpieza: 0")
        st.info("💡 Verifica que la columna de ventas tenga valores > 0 y fechas válidas")
        return
    
    logger.info(f"Procesando con {registros_limpio} registros válidos")
    
    # Renombrar para compatibilidad con funciones de agrupamiento
    df_ventas_limpio = df_ventas_limpio.rename(columns={'valor_usd': 'ventas_usd'})
    
    # Agrupar ventas por período
    try:
        df_ventas_agrupado = agrupar_por_periodo(df_ventas_limpio, tipo_periodo)
        logger.info(f"Datos agrupados por {tipo_periodo}: {len(df_ventas_agrupado)} registros")
    except Exception as e:
        st.error(f"❌ Error al agrupar datos: {str(e)}")
        logger.error(f"Error en agrupar_por_periodo: {e}", exc_info=True)
        return
    
    # Calcular métricas de ventas
    total_ventas = df_ventas_agrupado['ventas_usd'].sum()
    ventas_por_periodo = df_ventas_agrupado.groupby('periodo')['ventas_usd'].sum().sort_index()
    periodos_count = len(ventas_por_periodo)
    promedio_periodo = total_ventas / periodos_count if periodos_count > 0 else 0
    
    logger.info(f"Métricas: Total=${total_ventas:,.2f}, Períodos={periodos_count}, Promedio=${promedio_periodo:,.2f}")
    
    # Calcular crecimiento
    crecimiento_ventas_pct = 0
    if len(ventas_por_periodo) >= 2:
        ultimo_periodo = ventas_por_periodo.iloc[-1]
        penultimo_periodo = ventas_por_periodo.iloc[-2]
        if penultimo_periodo > 0:
            crecimiento_ventas_pct = ((ultimo_periodo - penultimo_periodo) / penultimo_periodo) * 100
    
    # =====================================================================
    # PROCESAMIENTO DE DATOS DE CXC (SI ESTÁ DISPONIBLE)
    # =====================================================================
    
    metricas_cxc = None
    score_salud_cxc = None
    score_status_cxc = None
    
    if df_cxc is not None and not df_cxc.empty:
        try:
            metricas_cxc = calcular_metricas_basicas(df_cxc)
            score_salud_cxc = calcular_score_salud(
                metricas_cxc['pct_vigente'],
                metricas_cxc['pct_critica']
            )
            score_status_cxc, _ = clasificar_score_salud(score_salud_cxc)
        except Exception as e:
            logger.error(f"Error calculando métricas CxC: {e}")
            metricas_cxc = None
    
    # =====================================================================
    # SECCIÓN 1: KPIs PRINCIPALES
    # =====================================================================
    
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
            label=f"📊 Promedio por {tipo_periodo.capitalize()}",
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
    
    # =====================================================================
    # SECCIÓN 2: VISUALIZACIONES PRINCIPALES
    # =====================================================================
    
    col_left, col_right = st.columns([6, 4])
    
    with col_left:
        st.subheader(f"📊 Evolución de Ventas ({tipo_periodo.capitalize()})")
        fig_ventas = crear_grafico_ventas_periodo(df_ventas_agrupado, tipo_periodo)
        st.plotly_chart(fig_ventas, use_container_width=True)
    
    with col_right:
        if metricas_cxc:
            st.subheader("💳 Distribución de CxC")
            fig_cxc = crear_pie_cxc(metricas_cxc)
            st.plotly_chart(fig_cxc, use_container_width=True)
        else:
            st.info("📋 Datos de CxC no disponibles\n\nSube un archivo de CxC en la sección correspondiente para ver esta visualización.")
    
    st.markdown("---")
    
    # =====================================================================
    # SECCIÓN 3: ANÁLISIS CON IA (OPCIONAL)
    # =====================================================================
    
    if habilitar_ia and openai_api_key:
        st.header("🤖 Análisis Ejecutivo con IA")
        
        periodo_label = {
            'semanal': 'Análisis Semanal',
            'mensual': 'Análisis Mensual',
            'trimestral': 'Análisis Trimestral',
            'anual': 'Análisis Anual'
        }[tipo_periodo]
        
        # Valores de CxC (usar 0 si no hay datos)
        _total_cxc = metricas_cxc['total_adeudado'] if metricas_cxc else 0
        _pct_vigente = metricas_cxc['pct_vigente'] if metricas_cxc else 0
        _pct_critica = metricas_cxc['pct_critica'] if metricas_cxc else 0
        _score_salud = score_salud_cxc if score_salud_cxc else 0
        
        # Crear clave única para cachear análisis (sin periodo - para que persista al cambiar vista)
        cache_key = f"analisis_consolidado_{int(total_ventas)}_{int(_total_cxc)}_{int(crecimiento_ventas_pct)}"
        
        # Botón para regenerar análisis
        col_titulo, col_boton = st.columns([4, 1])
        with col_boton:
            if st.button("🔄 Regenerar", key="btn_regenerar_ia_consolidado", help="Genera un nuevo análisis con IA"):
                if cache_key in st.session_state:
                    del st.session_state[cache_key]
                st.rerun()
        
        # Verificar si ya existe análisis en session_state
        analisis = st.session_state.get(cache_key)
        
        if analisis is None:
            with st.spinner("🔄 Generando análisis ejecutivo consolidado con GPT-4o-mini..."):
                try:
                    analisis = generar_analisis_consolidado_ia(
                        total_ventas=total_ventas,
                        crecimiento_ventas_pct=crecimiento_ventas_pct,
                        total_cxc=_total_cxc,
                        pct_vigente_cxc=_pct_vigente,
                        pct_critica_cxc=_pct_critica,
                        score_salud_cxc=_score_salud,
                        periodo_analisis=periodo_label,
                        api_key=openai_api_key
                    )
                    
                    # Guardar en session_state para que persista al cambiar periodo
                    if analisis:
                        st.session_state[cache_key] = analisis
                except Exception as e:
                    st.error(f"❌ Error al generar análisis: {str(e)}")
                    logger.error(f"Error en análisis IA consolidado: {e}", exc_info=True)
                    analisis = None
        
        # Mostrar análisis (ya sea nuevo o cacheado)
        if analisis:
            try:
                # Resumen ejecutivo
                st.markdown("### 📋 Resumen Ejecutivo")
                st.info(analisis.get('resumen_ejecutivo', 'No disponible'))
                
                # Columnas para contenido
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
            except Exception as e:
                st.error(f"❌ Error al mostrar análisis: {str(e)}")
                logger.error(f"Error mostrando análisis IA consolidado: {e}", exc_info=True)
        else:
            st.warning("⚠️ No se pudo generar el análisis")
        
        st.markdown("---")
    
    # =====================================================================
    # SECCIÓN 4: TABLA DETALLADA POR PERÍODO
    # =====================================================================
    
    st.header(f"📋 Detalle por {tipo_periodo.capitalize()}")
    
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
    
    # Footer
    st.markdown("---")
    st.caption(f"📅 Reporte generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | "
              f"Período: {tipo_periodo.capitalize()} | "
              f"Períodos analizados: {periodos_count}")
