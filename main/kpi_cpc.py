import streamlit as st
import pandas as pd
import numpy as np
import os
from unidecode import unidecode
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import plotly.graph_objects as go
import plotly.express as px

# Importar utilidades centralizadas
from utils.constantes import (
    UmbralesCxC, ScoreSalud, PrioridadCobranza, ConfigVisualizacion,
    BINS_ANTIGUEDAD, LABELS_ANTIGUEDAD, COLORES_ANTIGUEDAD,
    BINS_ANTIGUEDAD_AGENTES, LABELS_ANTIGUEDAD_AGENTES, COLORES_ANTIGUEDAD_AGENTES
)
from utils.cxc_helper import (
    calcular_dias_overdue, preparar_datos_cxc, calcular_metricas_basicas,
    calcular_score_salud, clasificar_score_salud, clasificar_antiguedad,
    obtener_semaforo_morosidad, obtener_semaforo_riesgo, obtener_semaforo_concentracion
)
from utils.cxc_metricas_cliente import (
    calcular_metricas_por_cliente, obtener_top_n_clientes, obtener_facturas_cliente
)
from utils.data_normalizer import normalizar_columnas
from utils.ai_helper import generar_resumen_ejecutivo_cxc, validar_api_key
from utils.filters_helper import obtener_lineas_filtradas, generar_contexto_filtros
from utils.logger import configurar_logger

# Configurar logger
logger = configurar_logger("kpi_cpc", nivel="INFO")

# Mapeo de nivel de riesgo a colores según severidad
MAPA_COLORES_RIESGO = {
    'Por vencer': '#4CAF50',      # Verde - Sin riesgo
    '1-30 días': '#8BC34A',       # Verde claro - Riesgo bajo
    '31-60 días': '#FFEB3B',      # Amarillo - Precaución
    '61-90 días': '#FF9800',      # Naranja - Alerta
    '91-180 días': '#F44336',     # Rojo - Crítico
    '>180 días': '#B71C1C'        # Rojo oscuro - Crítico severo
}


def _detectar_col_vendedor(df: pd.DataFrame) -> str | None:
    """
    Detecta la columna de vendedor/agente/ejecutivo en el dataframe.
    Retorna el nombre original de la columna encontrada o None.
    """
    # Búsqueda case-insensitive
    for col in df.columns:
        col_lower = str(col).lower()
        if col_lower in ("vendedor", "agente", "ejecutivo", "seller", "rep", "representante"):
            return col
    return None


def run(archivo, habilitar_ia=False, openai_api_key=None):
    """
    Función principal del módulo KPI CxC (Cuentas por Cobrar).
    
    Args:
        archivo: Ruta o buffer del archivo Excel con datos CxC
        habilitar_ia: Booleano para activar análisis con IA (default: False)
        openai_api_key: API key de OpenAI para análisis premium (default: None)
    """
    if not archivo.name.endswith(('.xls', '.xlsx')):
        st.error("❌ Solo se aceptan archivos Excel para el reporte de deudas.")
        return

    # =====================================================================
    # CONFIGURACIÓN DE ANÁLISIS CON IA - FUNCIÓN PREMIUM
    # =====================================================================
    # La IA se habilita desde el passkey premium en el sidebar principal
    # habilitar_ia y openai_api_key vienen de los parámetros de la función

    try:
        xls = pd.ExcelFile(archivo)
        hojas = xls.sheet_names
        
        if "CXC VIGENTES" not in hojas or "CXC VENCIDAS" not in hojas:
            st.error("❌ No se encontraron las hojas requeridas: 'CXC VIGENTES' y 'CXC VENCIDAS'.")
            return

        st.info("✅ Fuente: Hojas 'CXC VIGENTES' y 'CXC VENCIDAS'")

        # Leer y normalizar datos
        df_vigentes = pd.read_excel(xls, sheet_name='CXC VIGENTES')
        df_vencidas = pd.read_excel(xls, sheet_name='CXC VENCIDAS')
        
        df_vigentes = normalizar_columnas(df_vigentes)
        df_vencidas = normalizar_columnas(df_vencidas)
        
        # Renombrar columnas clave - PRIORIZAR COLUMNA F (CLIENTE)
        for df in [df_vigentes, df_vencidas]:
            # 1. Priorizar columna 'cliente' (columna F)
            if 'cliente' in df.columns:
                df.rename(columns={'cliente': 'deudor'}, inplace=True)
                
                # Si también existe 'razon_social', eliminarla
                if 'razon_social' in df.columns:
                    df.drop(columns=['razon_social'], inplace=True)
                    
            # 2. Si no existe 'cliente', usar 'razon_social' como respaldo
            elif 'razon_social' in df.columns:
                df.rename(columns={'razon_social': 'deudor'}, inplace=True)
            
            # 3. Detectar y normalizar columna de vendedor/agente
            col_vendedor = _detectar_col_vendedor(df)
            if col_vendedor and col_vendedor != 'vendedor':
                df.rename(columns={col_vendedor: 'vendedor'}, inplace=True)
                logger.info(f"Columna '{col_vendedor}' renombrada a 'vendedor'")
            
            # Renombrar otras columnas importantes
            column_rename = {
                'linea_de_negocio': 'linea_negocio',
                'saldo': 'saldo_adeudado',
                'saldo_usd': 'saldo_adeudado',
                'estatus': 'estatus',
                'vencimiento': 'fecha_vencimiento'
            }
            
            for original, nuevo in column_rename.items():
                if original in df.columns and nuevo not in df.columns:
                    df.rename(columns={original: nuevo}, inplace=True)
        
        # Agregar origen
        df_vigentes['origen'] = 'VIGENTE'
        df_vencidas['origen'] = 'VENCIDA'
        
        # Unificar columnas
        common_cols = list(set(df_vigentes.columns) & set(df_vencidas.columns))
        df_deudas = pd.concat([
            df_vigentes[common_cols], 
            df_vencidas[common_cols]
        ], ignore_index=True)
        
        # Limpieza
        df_deudas = df_deudas.dropna(axis=1, how='all')
        
        # Manejar duplicados
        duplicados = df_deudas.columns[df_deudas.columns.duplicated()]
        if not duplicados.empty:
            df_deudas = df_deudas.loc[:, ~df_deudas.columns.duplicated(keep='first')]

        # Validar columna clave
        if 'saldo_adeudado' not in df_deudas.columns:
            st.error("❌ No existe columna de saldo en los datos.")
            st.write("Columnas disponibles:", df_deudas.columns.tolist())
            return
            
        # Validar columna de deudor
        if 'deudor' not in df_deudas.columns:
            st.error("❌ No se encontró columna para identificar deudores.")
            st.write("Se esperaba 'cliente' o 'razon_social' en los encabezados")
            return
            
        # Convertir saldo
        saldo_serie = df_deudas['saldo_adeudado'].astype(str)
        saldo_limpio = saldo_serie.str.replace(r'[^\d.]', '', regex=True)
        df_deudas['saldo_adeudado'] = pd.to_numeric(saldo_limpio, errors='coerce').fillna(0)

        # ---------------------------------------------------------------------
        # Normalización de CxC alineada con Reporte Ejecutivo usando funciones helper
        # ---------------------------------------------------------------------
        df_deudas, df_np, mask_pagado = preparar_datos_cxc(df_deudas)

        # ---------------------------------------------------------------------
        # REPORTE DE DEUDAS A FRADMA (USANDO COLUMNA CORRECTA)
        # ---------------------------------------------------------------------
        st.header("📊 Reporte de Deudas a Fradma")
        
        # KPIs principales usando función helper
        metricas = calcular_metricas_basicas(df_np)
        total_adeudado = metricas['total_adeudado']
        vigente = metricas['vigente']
        vencida = metricas['vencida']
        vencida_0_30 = metricas['vencida_0_30']
        critica = metricas['critica']
        deuda_alto_riesgo = metricas['alto_riesgo']
        
        # Métricas principales en columnas
        col1, col2, col3 = st.columns(3)
        col1.metric("💰 Total Adeudado a Fradma", f"${total_adeudado:,.2f}")
        col2.metric("✅ Cartera Vigente", f"${vigente:,.2f}", 
                   delta=f"{(vigente/total_adeudado*100):.1f}%")
        col3.metric("⚠️ Deuda Vencida", f"${vencida:,.2f}", 
                   delta=f"{(vencida/total_adeudado*100):.1f}%",
                   delta_color="inverse")
        
        # Pie Chart: Vigente vs Vencido
        st.subheader("📊 Distribución General de Cartera")
        col_pie1, col_pie2 = st.columns(2)
        
        with col_pie1:
            st.write("**Vigente vs Vencido**")
            fig_vigente = go.Figure(data=[go.Pie(
                labels=['Vigente', 'Vencido'],
                values=[vigente, vencida],
                marker=dict(colors=['#4CAF50', '#F44336']),
                hole=0.4,
                textinfo='label+percent',
                textposition='outside'
            )])
            fig_vigente.update_layout(
                showlegend=True,
                height=350,
                margin=dict(t=20, b=20, l=20, r=20)
            )
            st.plotly_chart(fig_vigente, width='stretch')

        # Top 5 deudores (USANDO COLUMNA F - CLIENTE)
        st.subheader("🔝 Principales Deudores (Columna Cliente)")
        top_deudores = df_np.groupby('deudor')['saldo_adeudado'].sum().nlargest(5)
        
        # =====================================================================
        # ANÁLISIS DETALLADO POR CLIENTE: 3 MÉTODOS DE CÁLCULO DE DÍAS
        # =====================================================================
        st.write("---")
        st.subheader("📊 Análisis Detallado de Antigüedad por Cliente")
        
        # Calcular métricas por cliente con 3 métodos
        df_metricas_cliente = calcular_metricas_por_cliente(df_np)
        
        if not df_metricas_cliente.empty:
            # Selector de modo de visualización
            col_mode, col_params = st.columns([1, 3])
            
            with col_mode:
                modo_vista = st.radio(
                    "Modo de visualización",
                    options=["📊 Top N Clientes", "🔍 Buscar Cliente"],
                    index=0,
                    help="Elige cómo visualizar los datos"
                )
            
            df_display_raw = None  # DataFrame a mostrar (será filtrado según el modo)
            
            # ==== MODO 1: TOP N CLIENTES ====
            if modo_vista == "📊 Top N Clientes":
                with col_params:
                    col_num, col_btn = st.columns([2, 1])
                    with col_num:
                        num_clientes = st.selectbox(
                            "Número de clientes",
                            options=[10, 20, 50, 100],
                            index=0,
                            help="Selecciona cuántos clientes mostrar ordenados por saldo"
                        )
                    with col_btn:
                        st.write("")  # Espaciador
                        btn_actualizar = st.button("🔄 Actualizar", key="btn_top_n", use_container_width=True)
                
                # Solo actualizar cuando se presione el botón o sea la primera vez
                if btn_actualizar or 'df_top_clientes_cache' not in st.session_state:
                    st.session_state.df_top_clientes_cache = obtener_top_n_clientes(df_metricas_cliente, n=num_clientes)
                    st.session_state.num_clientes_cache = num_clientes
                
                df_display_raw = st.session_state.df_top_clientes_cache
                titulo_tabla = f"**Top {st.session_state.num_clientes_cache} Clientes por Saldo Adeudado**"
            
            # ==== MODO 2: BUSCAR CLIENTE ESPECÍFICO ====
            else:
                with col_params:
                    col_search, col_btn = st.columns([3, 1])
                    with col_search:
                        buscar_cliente = st.text_input(
                            "Nombre del cliente",
                            placeholder="Escribe el nombre o parte del nombre...",
                            help="Busca clientes por nombre (no distingue mayúsculas)"
                        )
                    with col_btn:
                        st.write("")  # Espaciador
                        btn_buscar = st.button("🔍 Buscar", key="btn_buscar_cliente", use_container_width=True)
                
                # Solo buscar cuando se presione el botón
                if btn_buscar and buscar_cliente.strip():
                    # Filtrar clientes que contengan el texto buscado (case-insensitive)
                    texto_busqueda = buscar_cliente.strip().lower()
                    mask = df_metricas_cliente['deudor'].str.lower().str.contains(texto_busqueda, na=False)
                    st.session_state.df_busqueda_cache = df_metricas_cliente[mask]
                    st.session_state.texto_busqueda_cache = buscar_cliente.strip()
                
                # Mostrar resultados de búsqueda si existen
                if 'df_busqueda_cache' in st.session_state and not st.session_state.df_busqueda_cache.empty:
                    df_display_raw = st.session_state.df_busqueda_cache
                    num_resultados = len(df_display_raw)
                    plural_cliente = 's' if num_resultados > 1 else ''
                    plural_encontrado = 's' if num_resultados > 1 else ''
                    titulo_tabla = f"**{num_resultados} Cliente{plural_cliente} encontrado{plural_encontrado} para: '{st.session_state.texto_busqueda_cache}'**"
                elif 'df_busqueda_cache' in st.session_state and st.session_state.df_busqueda_cache.empty:
                    st.warning(f"⚠️ No se encontraron clientes que contengan '{st.session_state.texto_busqueda_cache}'")
                    df_display_raw = None
                else:
                    st.info("👆 Escribe un nombre de cliente y presiona 'Buscar'")
                    df_display_raw = None
            
            # Explicación de las 3 métricas
            with st.expander("ℹ️ **Explicación: 3 Métodos de Cálculo de Días Vencidos**", expanded=False):
                st.markdown("""
                Cuando un cliente tiene **múltiples facturas vencidas**, hay 3 formas de calcular "cuántos días debe":
                
                1. **📊 Promedio Ponderado** (Recomendado para análisis):
                   - Toma cada factura y la pondera por su monto
                   - Fórmula: `Σ(días_factura × monto_factura) / total_cliente`
                   - **Ejemplo**: Cliente con 2 facturas:
                     - Factura A: $10,000 a 45 días → $450,000
                     - Factura B: $2,000 a 10 días → $20,000
                     - **Promedio ponderado = $470,000 / $12,000 = 39.2 días**
                   - **Uso**: Métrica más realista para scoring y análisis
                
                2. **⏰ Factura Más Antigua** (Peor caso):
                   - Toma la factura con más días vencidos
                   - **Ejemplo**: 45 días (Factura A del ejemplo anterior)
                   - **Uso**: Para cobranza agresiva - atacar primero la más vieja
                
                3. **🆕 Factura Más Reciente** (Última actividad):
                   - Toma la factura con menos días vencidos
                   - **Ejemplo**: 10 días (Factura B del ejemplo anterior)
                   - **Uso**: Para detectar clientes que siguen comprando pero no pagan
                
                💡 **La columna "Rango" usa el Promedio Ponderado** porque es la métrica más equilibrada.
                """)
            
            # Mostrar tabla si hay datos
            if df_display_raw is not None and not df_display_raw.empty:
                st.write(titulo_tabla)
                
                # Formatear DataFrame para display
                df_display = df_display_raw.copy()
                df_display['saldo_total'] = df_display['saldo_total'].apply(lambda x: f"${x:,.0f}")
                
                st.dataframe(
                    df_display,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "deudor": st.column_config.TextColumn("Cliente", width="large"),
                        "saldo_total": st.column_config.TextColumn("Saldo Total", width="medium"),
                        "num_facturas": st.column_config.NumberColumn("# Facturas", width="small"),
                        "dias_promedio_ponderado": st.column_config.NumberColumn(
                            "📊 Días Promedio Ponderado", 
                            width="medium",
                            help="Promedio de días vencidos ponderado por monto de cada factura"
                        ),
                        "dias_factura_mas_antigua": st.column_config.NumberColumn(
                            "⏰ Días Factura Más Antigua", 
                            width="medium",
                            help="Días vencidos de la factura más vieja del cliente"
                        ),
                        "dias_factura_mas_reciente": st.column_config.NumberColumn(
                            "🆕 Días Factura Más Reciente", 
                            width="medium",
                            help="Días vencidos de la factura más nueva del cliente"
                        ),
                        "rango_antiguedad": st.column_config.TextColumn("Rango", width="small")
                    }
                )
            
            # Resumen estadístico
            col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
            with col_stat1:
                st.metric(
                    "Clientes Totales", 
                    f"{len(df_metricas_cliente):,}",
                    help="Número total de clientes con saldo pendiente"
                )
            with col_stat2:
                clientes_criticos = len(df_metricas_cliente[df_metricas_cliente['rango_antiguedad'] == '>90 días'])
                st.metric(
                    "Clientes >90 días", 
                    f"{clientes_criticos:,}",
                    delta=f"{clientes_criticos/len(df_metricas_cliente)*100:.1f}%",
                    delta_color="inverse",
                    help="Clientes con promedio ponderado >90 días vencidos"
                )
            with col_stat3:
                prom_ponderado_global = (
                    (df_metricas_cliente['dias_promedio_ponderado'] * df_metricas_cliente['saldo_total']).sum() /
                    df_metricas_cliente['saldo_total'].sum()
                )
                st.metric(
                    "Promedio Global", 
                    f"{prom_ponderado_global:.1f} días",
                    help="Promedio ponderado de días vencidos de toda la cartera"
                )
            with col_stat4:
                max_dias_cliente = df_metricas_cliente['dias_factura_mas_antigua'].max()
                st.metric(
                    "Factura Más Antigua", 
                    f"{max_dias_cliente:.0f} días",
                    delta_color="inverse",
                    help="Factura más antigua en toda la cartera"
                )
        else:
            st.info("No hay datos de clientes para mostrar métricas detalladas")

        # =====================================================================
        # DRILL-DOWN: FACTURAS POR CLIENTE
        # =====================================================================
        if not df_metricas_cliente.empty:
            st.subheader("🔎 Detalle de Facturas por Cliente")

            # Poblar lista de clientes desde la tabla actualmente visible o del total
            lista_clientes = sorted(df_metricas_cliente['deudor'].dropna().unique().tolist())

            cliente_seleccionado = st.selectbox(
                "Selecciona un cliente para ver sus facturas:",
                options=["— Selecciona un cliente —"] + lista_clientes,
                index=0,
                key="selectbox_drill_down"
            )

            if cliente_seleccionado != "— Selecciona un cliente —":
                df_facturas = obtener_facturas_cliente(df_np, cliente_seleccionado)

                if df_facturas.empty:
                    st.warning(f"No se encontraron facturas para '{cliente_seleccionado}'")
                else:
                    # Resumen rápido del cliente
                    fila_cliente = df_metricas_cliente[
                        df_metricas_cliente['deudor'].str.strip().str.lower() ==
                        cliente_seleccionado.strip().lower()
                    ]
                    if not fila_cliente.empty:
                        r = fila_cliente.iloc[0]
                        col_d1, col_d2, col_d3, col_d4 = st.columns(4)
                        col_d1.metric("💰 Saldo Total", f"${r['saldo_total']:,.0f}")
                        col_d2.metric("📄 # Facturas", int(r['num_facturas']))
                        col_d3.metric("📊 Días Prom. Ponderado", f"{r['dias_promedio_ponderado']:.0f}")
                        col_d4.metric("⏰ Factura Más Antigua", f"{r['dias_factura_mas_antigua']:.0f} días")

                    # Formatear tabla de facturas
                    df_facturas_display = df_facturas.copy()
                    if 'saldo_adeudado' in df_facturas_display.columns:
                        df_facturas_display['saldo_adeudado'] = df_facturas_display['saldo_adeudado'].apply(
                            lambda x: f"${x:,.0f}" if pd.notna(x) else "-"
                        )

                    # Mapa de colores para la columna rango
                    col_config_facturas = {}
                    if 'saldo_adeudado' in df_facturas_display.columns:
                        col_config_facturas["saldo_adeudado"] = st.column_config.TextColumn("Saldo", width="medium")
                    if 'factura' in df_facturas_display.columns:
                        col_config_facturas["factura"] = st.column_config.TextColumn("Factura", width="medium")
                    if 'fecha' in df_facturas_display.columns:
                        col_config_facturas["fecha"] = st.column_config.DateColumn("Fecha", width="medium")
                    if 'dias_overdue' in df_facturas_display.columns:
                        col_config_facturas["dias_overdue"] = st.column_config.NumberColumn("Días Vencidos", width="small")
                    if 'rango' in df_facturas_display.columns:
                        col_config_facturas["rango"] = st.column_config.TextColumn("Rango", width="medium")
                    if 'estatus' in df_facturas_display.columns:
                        col_config_facturas["estatus"] = st.column_config.TextColumn("Estatus", width="small")

                    st.dataframe(
                        df_facturas_display,
                        use_container_width=True,
                        hide_index=True,
                        column_config=col_config_facturas
                    )
                    st.caption(f"📄 {len(df_facturas)} factura(s) para **{cliente_seleccionado}**")

        # =====================================================================
        # GRÁFICO: EVOLUCIÓN DE MOROSIDAD
        # =====================================================================
        st.subheader("📈 Evolución de Morosidad en el Tiempo")

        # Detectar columna de fecha disponible
        col_fecha = None
        for _c in ['fecha', 'fecha_factura', 'fecha_emision', 'fecha_doc']:
            if _c in df_np.columns:
                col_fecha = _c
                break

        if col_fecha is None:
            st.info(
                "ℹ️ No se detectó una columna de fecha en los datos. "
                "Para ver la evolución de morosidad, el archivo debe incluir una columna de fecha de factura."
            )
        else:
            df_evol = df_np[[col_fecha, 'saldo_adeudado', 'dias_overdue']].copy()
            df_evol[col_fecha] = pd.to_datetime(df_evol[col_fecha], errors='coerce')
            df_evol = df_evol.dropna(subset=[col_fecha])

            # Clasificar rango por fila
            def _rango_evol(d):
                if d <= 0:   return 'Vigente'
                elif d <= 30: return '0-30 días'
                elif d <= 60: return '31-60 días'
                elif d <= 90: return '61-90 días'
                else:         return '>90 días'

            df_evol['rango'] = df_evol['dias_overdue'].apply(_rango_evol)
            df_evol['mes'] = df_evol[col_fecha].dt.to_period('M').astype(str)

            meses_unicos = df_evol['mes'].nunique()

            if meses_unicos < 2:
                st.info(
                    "ℹ️ Se necesitan datos de **al menos 2 meses** para mostrar la evolución. "
                    f"El archivo actual contiene datos de {meses_unicos} periodo(s)."
                )
            else:
                # Pivot: mes × rango → saldo
                pivot = (
                    df_evol.groupby(['mes', 'rango'])['saldo_adeudado']
                    .sum()
                    .unstack(fill_value=0)
                    .reset_index()
                )
                pivot = pivot.sort_values('mes')

                orden_rangos  = ['Vigente', '0-30 días', '31-60 días', '61-90 días', '>90 días']
                colores_rangos = {
                    'Vigente':    '#4CAF50',
                    '0-30 días':  '#8BC34A',
                    '31-60 días': '#FFEB3B',
                    '61-90 días': '#FF9800',
                    '>90 días':   '#F44336',
                }

                fig_evol = go.Figure()
                for rango in orden_rangos:
                    if rango in pivot.columns:
                        fig_evol.add_trace(go.Bar(
                            name=rango,
                            x=pivot['mes'],
                            y=pivot[rango],
                            marker_color=colores_rangos.get(rango, '#999'),
                            hovertemplate='%{x}<br>' + rango + ': $%{y:,.0f}<extra></extra>'
                        ))

                fig_evol.update_layout(
                    barmode='stack',
                    title='Evolución mensual de cartera por rango de antigüedad',
                    xaxis_title='Mes',
                    yaxis_title='Saldo Adeudado ($)',
                    legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
                    height=420,
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                )
                st.plotly_chart(fig_evol, use_container_width=True)
                st.caption(
                    f"Periodos analizados: {pivot['mes'].iloc[0]} → {pivot['mes'].iloc[-1]} "
                    f"({meses_unicos} meses)"
                )

        # =====================================================================
        # FASE 2: DASHBOARD DE SALUD FINANCIERA
        # =====================================================================
        st.header("🏥 Dashboard de Salud Financiera")
        
        # Calcular métricas de salud
        pct_vigente = metricas['pct_vigente']
        pct_critica = metricas['pct_critica']
        pct_vencida_total = metricas['pct_vencida']
        pct_alto_riesgo = metricas['pct_alto_riesgo']
        
        # Extraer porcentajes por rangos para el score
        pct_vencida_0_30 = metricas.get('pct_vencida_0_30', 0)
        pct_vencida_31_60 = metricas.get('pct_vencida_31_60', 0)
        pct_vencida_61_90 = metricas.get('pct_vencida_61_90', 0)
        
        # Concentración top 3
        top3_deuda = df_np.groupby('deudor')['saldo_adeudado'].sum().nlargest(3).sum()
        pct_concentracion = (top3_deuda / total_adeudado * 100) if total_adeudado > 0 else 0
        
        # Score usando función helper con todos los rangos
        score_salud = calcular_score_salud(
            pct_vigente, pct_critica,
            pct_vencida_0_30, pct_vencida_31_60, pct_vencida_61_90, pct_alto_riesgo
        )
        score_status, score_color = clasificar_score_salud(score_salud)
        
        # Gauge principal de salud — reemplazado por métricas directas
        col_health1, col_health2 = st.columns([1, 2])
        
        with col_health1:
            st.write("### 📊 Resumen de Cartera")
            st.metric("💰 Cartera Total", f"${total_adeudado:,.0f}")
            st.metric("✅ Vigente", f"{pct_vigente:.1f}%", 
                     delta=f"{pct_vigente - 70:.1f}pp vs objetivo 70%",
                     help="📐 Porcentaje de cartera que aún no ha vencido (días restantes > 0). Objetivo: ≥ 70%")
            st.metric("⚠️ Vencida Total", f"{pct_vencida_total:.1f}%",
                     delta_color="inverse",
                     help="📐 Porcentaje de cartera vencida sobre total")
        
        with col_health2:
            st.write("### 📊 Indicadores Clave de Desempeño (KPIs)")
            
            # Calcular KPIs
            # NOTA: DSO y Rotación CxC requieren datos de ventas que no están en este módulo
            # Por ahora se omiten para evitar mostrar datos incorrectos (antes eran constantes hardcodeadas)
            
            # Índice de Morosidad (alineado: % vencida total sobre cartera no pagada)
            indice_morosidad = pct_vencida_total
            morosidad_objetivo = UmbralesCxC.MOROSIDAD_OBJETIVO
            morosidad_status = obtener_semaforo_morosidad(indice_morosidad)
            
            # Índice de Concentración
            concentracion_status = obtener_semaforo_concentracion(pct_concentracion)
            
            # Tabla de KPIs (solo los calculables con datos de CxC)
            kpis_data = {
                'KPI': [
                    'Índice de Morosidad',
                    'Concentración Top 3',
                    'Riesgo Alto (>90 días)'
                ],
                'Valor Actual': [
                    f"{indice_morosidad:.1f}%",
                    f"{pct_concentracion:.1f}%",
                    f"{pct_alto_riesgo:.1f}%"
                ],
                'Objetivo': [
                    f"<{morosidad_objetivo}%",
                    "<30%",
                    "<10%"
                ],
                'Estado': [
                    morosidad_status,
                    concentracion_status,
                    "🟢" if pct_alto_riesgo <= 10 else "🟡" if pct_alto_riesgo <= 20 else "🔴"
                ],
                'Monto/Detalle': [
                    f"${vencida:,.2f}",
                    f"${top3_deuda:,.2f}",
                    f"${deuda_alto_riesgo:,.2f}"
                ]
            }
            
            df_kpis = pd.DataFrame(kpis_data)
            
            # Mostrar tabla con estilo
            st.dataframe(
                df_kpis,
                width='stretch',
                hide_index=True,
                column_config={
                    "KPI": st.column_config.TextColumn("KPI", width="medium"),
                    "Valor Actual": st.column_config.TextColumn("Valor Actual", width="small"),
                    "Objetivo": st.column_config.TextColumn("Objetivo", width="small"),
                    "Estado": st.column_config.TextColumn("Estado", width="small"),
                    "Monto/Detalle": st.column_config.TextColumn("Monto/Detalle", width="medium")
                }
            )
            
            # Nota sobre KPIs que requieren datos externos
            st.caption("💡 **Nota:** DSO y Rotación CxC requieren datos de ventas para cálculo preciso (módulo de ventas separado)")
        
        st.write("---")
        
        # =====================================================================
        # FASE 2.5: ANÁLISIS EJECUTIVO CON IA - FUNCIÓN PREMIUM
        # =====================================================================
        if habilitar_ia and openai_api_key:
            st.header("🤖 Análisis Ejecutivo con IA Premium")
            
            # Obtener filtros configurados
            periodo_seleccionado = st.session_state.get("analisis_periodo", "Todos los datos")
            lineas_seleccionadas = st.session_state.get("analisis_lineas", ["Todas"])
            
            st.info(
                f"📋 **Configuración:** Periodo: {periodo_seleccionado} | "
                f"Líneas: {', '.join(lineas_seleccionadas[:3])}{'...' if len(lineas_seleccionadas) > 3 else ''}"
            )
            
            # Botón para ejecutar análisis
            if st.button("🚀 Generar Análisis con IA", type="primary", use_container_width=True, key="btn_ia_cxc"):
                with st.spinner("🔄 Generando análisis ejecutivo con GPT-4o-mini..."):
                    try:
                        # Filtrar datos según configuración
                        df_analisis = df_np.copy()
                        
                        # Filtrar líneas específicas
                        lineas_filtrar = obtener_lineas_filtradas(lineas_seleccionadas)
                        
                        # Aplicar filtro de líneas si existe la columna
                        if "linea_negocio" in df_analisis.columns and lineas_filtrar:
                            df_analisis = df_analisis[df_analisis['linea_negocio'].isin(lineas_filtrar)]
                        
                        # Recalcular métricas con datos filtrados
                        total_adeudado_filtrado = df_analisis['saldo_adeudado'].sum()
                        vigente_filtrado = df_analisis[df_analisis['dias_overdue'] <= 0]['saldo_adeudado'].sum()
                        vencida_filtrado = df_analisis[df_analisis['dias_overdue'] > 0]['saldo_adeudado'].sum()
                        critica_filtrado = df_analisis[df_analisis['dias_overdue'] > 90]['saldo_adeudado'].sum()
                        
                        pct_vigente_filtrado = (vigente_filtrado / total_adeudado_filtrado * 100) if total_adeudado_filtrado > 0 else 0
                        pct_critica_filtrado = (critica_filtrado / total_adeudado_filtrado * 100) if total_adeudado_filtrado > 0 else 0
                        
                        # Preparar datos de top deudores para el análisis
                        top_deudores_lista = []
                        top_deudores_df = df_analisis.groupby('deudor')['saldo_adeudado'].sum().nlargest(5)
                        for nombre, monto in top_deudores_df.items():
                            pct = (monto / total_adeudado_filtrado * 100) if total_adeudado_filtrado > 0 else 0
                            top_deudores_lista.append({
                                'nombre': nombre,
                                'monto': monto,
                                'porcentaje': pct
                            })
                        
                        # Contar alertas (calcular antes si no está disponible)
                        try:
                            # Intentar contar alertas de los datos disponibles
                            umbral_critico = UmbralesCxC.CRITICO_MONTO
                            clientes_criticos = df_analisis[df_analisis['saldo_adeudado'] >= umbral_critico]
                            alertas_count = len(clientes_criticos)
                        except:
                            alertas_count = 0
                        
                        # Contar casos urgentes
                        try:
                            urgente_count = len(df_analisis[df_analisis['prioridad_cobranza'] == 'URGENTE'])
                        except:
                            urgente_count = 0
                        
                        # Calcular índice de morosidad
                        indice_morosidad = (vencida_filtrado / total_adeudado_filtrado * 100) if total_adeudado_filtrado > 0 else 0
                        
                        # Calcular porcentajes de rangos con datos filtrados
                        vencida_0_30_filtrado = df_analisis[(df_analisis['dias_overdue'] > 0) & (df_analisis['dias_overdue'] <= 30)]['saldo_adeudado'].sum()
                        vencida_31_60_filtrado = df_analisis[(df_analisis['dias_overdue'] > 30) & (df_analisis['dias_overdue'] <= 60)]['saldo_adeudado'].sum()
                        vencida_61_90_filtrado = df_analisis[(df_analisis['dias_overdue'] > 60) & (df_analisis['dias_overdue'] <= 90)]['saldo_adeudado'].sum()
                        alto_riesgo_filtrado = critica_filtrado
                        
                        pct_vencida_0_30_filtrado = (vencida_0_30_filtrado / total_adeudado_filtrado * 100) if total_adeudado_filtrado > 0 else 0
                        pct_vencida_31_60_filtrado = (vencida_31_60_filtrado / total_adeudado_filtrado * 100) if total_adeudado_filtrado > 0 else 0
                        pct_vencida_61_90_filtrado = (vencida_61_90_filtrado / total_adeudado_filtrado * 100) if total_adeudado_filtrado > 0 else 0
                        pct_alto_riesgo_filtrado = (alto_riesgo_filtrado / total_adeudado_filtrado * 100) if total_adeudado_filtrado > 0 else 0
                        
                        score_salud_filtrado = calcular_score_salud(
                            pct_vigente_filtrado, pct_critica_filtrado,
                            pct_vencida_0_30_filtrado, pct_vencida_31_60_filtrado, pct_vencida_61_90_filtrado, 
                            pct_alto_riesgo_filtrado
                        )
                        score_status_filtrado, _ = clasificar_score_salud(score_salud_filtrado)
                        
                        # Preparar contexto de filtros para IA
                        contexto_filtros = generar_contexto_filtros(lineas_filtrar)
                        
                        # Generar análisis
                        analisis = generar_resumen_ejecutivo_cxc(
                            total_adeudado=total_adeudado_filtrado,
                            vigente=vigente_filtrado,
                            vencida=vencida_filtrado,
                            critica=critica_filtrado,
                            pct_vigente=pct_vigente_filtrado,
                            pct_critica=pct_critica_filtrado,
                            score_salud=score_salud_filtrado,
                            score_status=score_status_filtrado,
                            top_deudor=top_deudores_df.index[0] if len(top_deudores_df) > 0 else "N/A",
                            monto_top_deudor=top_deudores_df.iloc[0] if len(top_deudores_df) > 0 else 0,
                            indice_morosidad=indice_morosidad,
                            casos_urgentes=urgente_count,
                            alertas_count=alertas_count,
                            api_key=openai_api_key,
                            datos_top_deudores=top_deudores_lista,
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
                        logger.error(f"Error en análisis con IA CxC: {e}", exc_info=True)
            else:
                st.caption("👆 Presiona el botón para generar análisis personalizado según tus filtros")
            
            st.write("---")
        
        # =====================================================================
        # FASE 3: ALERTAS INTELIGENTES Y PRIORIDADES DE COBRANZA
        # =====================================================================
        st.header("🚨 Alertas Inteligentes")
        
        alertas = []
        
        # Alerta 1: Clientes que superan umbral crítico
        umbral_critico = UmbralesCxC.CRITICO_MONTO
        clientes_criticos = df_np.groupby('deudor')['saldo_adeudado'].sum()
        clientes_sobre_umbral = clientes_criticos[clientes_criticos > umbral_critico]
        
        if len(clientes_sobre_umbral) > 0:
            alertas.append({
                'tipo': '⚠️ ALTO MONTO',
                'mensaje': f"{len(clientes_sobre_umbral)} cliente(s) superan ${umbral_critico:,.2f} individual",
                'detalle': ', '.join([f"{c} (${m:,.2f})" for c, m in clientes_sobre_umbral.head(3).items()]),
                'prioridad': 'ALTA'
            })
        
        # Alerta 2: Deuda >90 días significativa
        if pct_alto_riesgo > 15:
            alertas.append({
                'tipo': '🔴 RIESGO CRÍTICO',
                'mensaje': f"Deuda >90 días representa {pct_alto_riesgo:.1f}% del total",
                'detalle': f"${deuda_alto_riesgo:,.2f} en alto riesgo de incobrabilidad",
                'prioridad': 'URGENTE'
            })
        
        # Alerta 3: Alta concentración
        if pct_concentracion > 50:
            top3_clientes = df_np.groupby('deudor')['saldo_adeudado'].sum().nlargest(3)
            alertas.append({
                'tipo': '📊 CONCENTRACIÓN',
                'mensaje': f"Top 3 clientes concentran {pct_concentracion:.1f}% de la cartera",
                'detalle': f"Riesgo alto de dependencia: {', '.join(top3_clientes.index.tolist())}",
                'prioridad': 'MEDIA'
            })
        
        # Alerta 4: Clientes con aumento significativo
        # (Requeriría histórico - simulamos detección)
        if 'dias_overdue' in df_deudas.columns:
            clientes_deterioro = df_np[df_np['dias_overdue'] > UmbralesCxC.DIAS_DETERIORO_SEVERO].groupby('deudor')['saldo_adeudado'].sum()
            if len(clientes_deterioro) > 0:
                alertas.append({
                    'tipo': '📈 DETERIORO',
                    'mensaje': f"{len(clientes_deterioro)} cliente(s) con deuda >120 días",
                    'detalle': f"Total en deterioro severo: ${clientes_deterioro.sum():,.2f}",
                    'prioridad': 'ALTA'
                })
        
        # Alerta 5: Score de salud bajo
        if score_salud < 40:
            alertas.append({
                'tipo': '🏥 SALUD CRÍTICA',
                'mensaje': f"Score de salud financiera: {score_salud:.0f}/100 ({score_status})",
                'detalle': "Se requiere acción inmediata de recuperación",
                'prioridad': 'URGENTE'
            })
        
        # Mostrar alertas
        if alertas:
            # Ordenar por prioridad
            prioridad_orden = {'URGENTE': 0, 'ALTA': 1, 'MEDIA': 2}
            alertas_ordenadas = sorted(alertas, key=lambda x: prioridad_orden.get(x['prioridad'], 3))
            
            for alerta in alertas_ordenadas:
                color = {
                    'URGENTE': '#F44336',
                    'ALTA': '#FF9800',
                    'MEDIA': '#FFC107'
                }.get(alerta['prioridad'], '#9E9E9E')
                
                st.markdown(
                    f"""
                    <div style="background-color:{color}20; border-left: 5px solid {color}; padding: 15px; margin: 10px 0; border-radius: 5px;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <div>
                                <h4 style="margin: 0; color: {color};">{alerta['tipo']}</h4>
                                <p style="margin: 5px 0 0 0; font-size: 16px; font-weight: bold;">{alerta['mensaje']}</p>
                                <p style="margin: 5px 0 0 0; font-size: 14px; color: #666;">{alerta['detalle']}</p>
                            </div>
                            <span style="background-color: {color}; color: white; padding: 5px 15px; border-radius: 20px; font-weight: bold; font-size: 12px;">
                                {alerta['prioridad']}
                            </span>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
        else:
            st.success("✅ No hay alertas críticas. La cartera está bajo control.")
        
        st.write("---")

        # =====================================================================
        # PRIORIDADES DE COBRANZA — Dashboard Proactivo
        # =====================================================================
        st.header("📋 Dashboard de Cobranza Proactiva")

        from utils.export_helper import crear_excel_cobranza_semanal

        # ── Calcular score de prioridad enriquecido ──────────────────────────
        # Score 0-100 basado en 4 factores:
        #   monto relativo (30%) · días máx vencido (35%) · # documentos (15%)
        #   · % de cartera en alto riesgo del cliente (20%)
        total_cartera = df_np['saldo_adeudado'].sum() if not df_np.empty else 1

        deudor_prioridad = []
        for deudor in df_np['deudor'].unique():
            dd = df_np[df_np['deudor'] == deudor]
            monto_total = dd['saldo_adeudado'].sum()
            dias_max    = dd['dias_overdue'].max()   if 'dias_overdue' in dd.columns else 0
            dias_prom   = dd['dias_overdue'].mean()  if 'dias_overdue' in dd.columns else 0
            num_docs    = len(dd)

            monto_alto_riesgo = dd[dd['dias_overdue'] > 90]['saldo_adeudado'].sum() \
                                if 'dias_overdue' in dd.columns else 0
            pct_riesgo = (monto_alto_riesgo / monto_total * 100) if monto_total > 0 else 0

            # Normalizar cada factor sobre el máximo de la cartera
            max_monto = df_np.groupby('deudor')['saldo_adeudado'].sum().max()
            score_monto  = min(monto_total / max(max_monto, 1) * 100, 100) * 0.30
            score_dias   = min(dias_max / 180 * 100, 100)                  * 0.35
            score_docs   = min(num_docs / 20 * 100, 100)                   * 0.15
            score_riesgo = min(pct_riesgo, 100)                            * 0.20
            score_total  = score_monto + score_dias + score_docs + score_riesgo

            if score_total >= 65:
                nivel, nivel_num = "🔴 URGENTE", 1
            elif score_total >= 40:
                nivel, nivel_num = "🟠 ALTA",    2
            elif score_total >= 20:
                nivel, nivel_num = "🟡 MEDIA",   3
            else:
                nivel, nivel_num = "🟢 BAJA",    4

            # Acción recomendada automática
            if nivel_num == 1:
                accion = "⚡ Contacto inmediato — evaluar plan de pagos / suspender crédito"
            elif nivel_num == 2:
                accion = "📞 Llamar en 48 h — comprometer fecha de pago"
            elif nivel_num == 3:
                accion = "📧 Enviar estado de cuenta + recordatorio por correo"
            else:
                accion = "🔔 Monitoreo semanal de rutina"

            deudor_prioridad.append({
                'deudor':     deudor,
                'monto':      monto_total,
                'dias_max':   dias_max,
                'dias_prom':  round(dias_prom, 1),
                'documentos': num_docs,
                'pct_riesgo': round(pct_riesgo, 1),
                'score':      round(score_total, 1),
                'nivel':      nivel,
                'nivel_num':  nivel_num,
                'accion':     accion,
            })

        df_prioridades = pd.DataFrame(deudor_prioridad).sort_values(
            ['nivel_num', 'score'], ascending=[True, False]
        ).reset_index(drop=True)

        # ── Métricas por nivel ───────────────────────────────────────────────
        col_acc1, col_acc2, col_acc3, col_acc4 = st.columns(4)
        for col_ui, niv_num, emoji, label in [
            (col_acc1, 1, "🔴", "Urgente"),
            (col_acc2, 2, "🟠", "Alta"),
            (col_acc3, 3, "🟡", "Media"),
            (col_acc4, 4, "🟢", "Baja"),
        ]:
            sub = df_prioridades[df_prioridades['nivel_num'] == niv_num]
            col_ui.metric(
                f"{emoji} {label}",
                f"{len(sub)} clientes",
                delta=f"${sub['monto'].sum():,.0f}",
                delta_color="inverse" if niv_num <= 2 else "normal",
            )

        st.write("")

        # ── Filtro interactivo de nivel ──────────────────────────────────────
        nivel_filtro = st.multiselect(
            "Filtrar por nivel de prioridad:",
            options=["🔴 URGENTE", "🟠 ALTA", "🟡 MEDIA", "🟢 BAJA"],
            default=["🔴 URGENTE", "🟠 ALTA"],
            key="filtro_nivel_cobranza",
        )

        df_vista = df_prioridades[df_prioridades['nivel'].isin(nivel_filtro)] \
                   if nivel_filtro else df_prioridades

        # ── Tabla principal ──────────────────────────────────────────────────
        st.write(f"**{len(df_vista)} cliente(s) en los niveles seleccionados**")

        df_tabla = df_vista[[
            'nivel', 'deudor', 'monto', 'dias_max', 'dias_prom',
            'documentos', 'pct_riesgo', 'score', 'accion'
        ]].copy()

        st.dataframe(
            df_tabla,
            use_container_width=True,
            hide_index=True,
            column_config={
                "nivel":      st.column_config.TextColumn("Prioridad",       width="small"),
                "deudor":     st.column_config.TextColumn("Cliente",         width="large"),
                "monto":      st.column_config.NumberColumn("Saldo ($)",     width="medium",
                              format="$%.0f"),
                "dias_max":   st.column_config.NumberColumn("Días Máx.",     width="small"),
                "dias_prom":  st.column_config.NumberColumn("Días Prom.",    width="small"),
                "documentos": st.column_config.NumberColumn("# Docs",        width="small"),
                "pct_riesgo": st.column_config.NumberColumn("% Alto Riesgo", width="small",
                              format="%.1f%%"),
                "score":      st.column_config.ProgressColumn(
                              "Score", width="small", min_value=0, max_value=100, format="%.1f"),
                "accion":     st.column_config.TextColumn("Acción Recomendada", width="large"),
            },
        )

        # ── Explicación del score ────────────────────────────────────────────
        with st.expander("ℹ️ ¿Cómo se calcula el Score de Prioridad?"):
            st.markdown("""
            El **Score de Prioridad** (0–100) combina 4 factores para identificar
            qué clientes requieren atención **antes** de que la deuda se deteriore:

            | Factor | Peso | Descripción |
            |--------|------|-------------|
            | 💰 **Monto relativo** | 30 % | Saldo del cliente vs. el mayor deudor de la cartera |
            | ⏰ **Días máx. vencido** | 35 % | Factura más antigua vencida (normalizada a 180 días) |
            | 📄 **# Documentos** | 15 % | Cantidad de facturas pendientes (normalizada a 20) |
            | 🔴 **% en Alto Riesgo** | 20 % | Porcentaje del saldo del cliente con >90 días vencido |

            **Umbral de niveles:**
            - 🔴 URGENTE: Score ≥ 65
            - 🟠 ALTA: Score 40–64
            - 🟡 MEDIA: Score 20–39
            - 🟢 BAJA: Score < 20
            """)

        # ── Descarga Excel semanal ───────────────────────────────────────────
        st.write("---")
        st.write("### 📥 Exportar Lista de Cobranza Semanal")
        col_dl1, col_dl2 = st.columns([2, 3])

        with col_dl1:
            nivel_export = st.multiselect(
                "Incluir niveles en el Excel:",
                options=["🔴 URGENTE", "🟠 ALTA", "🟡 MEDIA", "🟢 BAJA"],
                default=["🔴 URGENTE", "🟠 ALTA"],
                key="nivel_export_cobranza",
            )

        with col_dl2:
            st.write("")
            st.write("")
            if nivel_export:
                df_export_cobranza = df_prioridades[
                    df_prioridades['nivel'].isin(nivel_export)
                ].copy()
                try:
                    excel_bytes = crear_excel_cobranza_semanal(df_export_cobranza)
                    fecha_archivo = datetime.now().strftime("%Y%m%d")
                    st.download_button(
                        label=f"⬇️ Descargar Excel ({len(df_export_cobranza)} clientes)",
                        data=excel_bytes,
                        file_name=f"cobranza_semanal_{fecha_archivo}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                    )
                    st.caption(
                        "El Excel incluye: semáforo de colores por prioridad, "
                        "acción recomendada y columnas vacías para Gestor, Notas y Fecha de Compromiso."
                    )
                except Exception as e:
                    st.error(f"Error al generar Excel: {e}")
            else:
                st.info("Selecciona al menos un nivel para habilitar la descarga.")

        st.write("---")

        # ── Gráfico: distribución de saldo por nivel ─────────────────────────
        if not df_prioridades.empty:
            resumen_niv = (
                df_prioridades.groupby('nivel')['monto']
                .sum()
                .reset_index()
                .rename(columns={'nivel': 'Nivel', 'monto': 'Saldo'})
            )
            orden = ["🔴 URGENTE", "🟠 ALTA", "🟡 MEDIA", "🟢 BAJA"]
            colores_niv = {
                "🔴 URGENTE": "#F44336",
                "🟠 ALTA":    "#FF9800",
                "🟡 MEDIA":   "#FFEB3B",
                "🟢 BAJA":    "#4CAF50",
            }
            resumen_niv['Nivel'] = pd.Categorical(resumen_niv['Nivel'], categories=orden, ordered=True)
            resumen_niv = resumen_niv.sort_values('Nivel')

            fig_prio = px.bar(
                resumen_niv, x='Nivel', y='Saldo',
                color='Nivel',
                color_discrete_map=colores_niv,
                title='Saldo por Nivel de Prioridad',
                text_auto='.3s',
                labels={'Saldo': 'Saldo Adeudado ($)'},
            )
            fig_prio.update_layout(
                showlegend=False,
                height=320,
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                xaxis_title='',
            )
            st.plotly_chart(fig_prio, use_container_width=True)

        # Top 5 deudores con tabla mejorada
        st.dataframe(top_deudores.reset_index().rename(
            columns={'deudor': 'Cliente (Col F)', 'saldo_adeudado': 'Monto Adeudado ($)'}
        ).style.format({'Monto Adeudado ($)': '${:,.2f}'}))

        # Gráfico de concentración
        st.bar_chart(top_deudores)

        # =====================================================================
        # FASE 4: ANÁLISIS POR LÍNEA DE NEGOCIO
        # =====================================================================
        if 'linea_negocio' in df_deudas.columns or 'linea_de_negocio' in df_deudas.columns:
            st.header("🏭 Análisis por Línea de Negocio")
            
            # Normalizar nombre de columna
            col_linea = 'linea_negocio' if 'linea_negocio' in df_deudas.columns else 'linea_de_negocio'
            
            # Limpiar valores nulos
            df_lineas = df_deudas[df_deudas[col_linea].notna()].copy()

            # -------------------------------------------------
            # Alinear cálculo con Reporte Ejecutivo usando helper
            # -------------------------------------------------
            df_lineas, df_lineas_np, _ = preparar_datos_cxc(df_lineas)
            df_lineas = df_lineas_np  # Usar solo no pagados
            
            if len(df_lineas) > 0:
                # Calcular métricas por línea
                lineas_metricas = []
                
                for linea in df_lineas[col_linea].unique():
                    linea_data = df_lineas[df_lineas[col_linea] == linea]
                    total_linea = linea_data['saldo_adeudado'].sum()
                    
                    # Calcular índice de morosidad ponderado por antigüedad
                    # En lugar de binario (vencido/no vencido), usar escala basada en gravedad
                    if total_linea > 0:
                        # Segmentar cartera por antigüedad
                        vigente = linea_data[linea_data['dias_overdue'] <= 0]['saldo_adeudado'].sum()
                        dias_1_30 = linea_data[(linea_data['dias_overdue'] > 0) & (linea_data['dias_overdue'] <= 30)]['saldo_adeudado'].sum()
                        dias_31_60 = linea_data[(linea_data['dias_overdue'] > 30) & (linea_data['dias_overdue'] <= 60)]['saldo_adeudado'].sum()
                        dias_61_90 = linea_data[(linea_data['dias_overdue'] > 60) & (linea_data['dias_overdue'] <= 90)]['saldo_adeudado'].sum()
                        dias_mas_90 = linea_data[linea_data['dias_overdue'] > 90]['saldo_adeudado'].sum()
                        
                        # Calcular porcentajes
                        pct_vigente = (vigente / total_linea * 100)
                        pct_1_30 = (dias_1_30 / total_linea * 100)
                        pct_31_60 = (dias_31_60 / total_linea * 100)
                        pct_61_90 = (dias_61_90 / total_linea * 100)
                        pct_mas_90 = (dias_mas_90 / total_linea * 100)
                        
                        # Índice de morosidad ponderado (0-100)
                        # Vigente: 0 puntos, 1-30: 15 puntos, 31-60: 40 puntos, 61-90: 70 puntos, >90: 100 puntos
                        pct_morosidad = (
                            pct_vigente * 0 +
                            pct_1_30 * 15 +
                            pct_31_60 * 40 +
                            pct_61_90 * 70 +
                            pct_mas_90 * 100
                        ) / 100
                    else:
                        pct_morosidad = 0
                        pct_mas_90 = 0
                    
                    alto_riesgo_linea = linea_data[linea_data['dias_overdue'] > 90]['saldo_adeudado'].sum()
                    pct_alto_riesgo = (alto_riesgo_linea / total_linea * 100) if total_linea > 0 else 0
                    
                    # Concentración (top cliente de la línea)
                    top_cliente_linea = linea_data.groupby('deudor')['saldo_adeudado'].sum().max()
                    pct_concentracion_linea = (top_cliente_linea / total_linea * 100) if total_linea > 0 else 0
                    
                    lineas_metricas.append({
                        'linea': linea,
                        'total': total_linea,
                        'pct_morosidad': pct_morosidad,
                        'pct_alto_riesgo': pct_alto_riesgo,
                        'pct_concentracion': pct_concentracion_linea,
                        'clientes': linea_data['deudor'].nunique(),
                        'docs': len(linea_data)
                    })
                
                df_lineas_metricas = pd.DataFrame(lineas_metricas)
                df_lineas_metricas = df_lineas_metricas.sort_values('total', ascending=False)
                
                # Gauges por línea de negocio
                st.write("### 🎯 Indicadores por Línea de Negocio")
                
                # Mostrar gauges de CxC por línea (top 6)
                top_lineas = df_lineas_metricas.head(6)
                
                for i in range(0, len(top_lineas), 3):
                    cols_linea = st.columns(3)
                    
                    for j in range(3):
                        if i + j < len(top_lineas):
                            row = top_lineas.iloc[i + j]
                            linea = row['linea']
                            total = row['total']
                            pct_total = (total / total_adeudado * 100) if total_adeudado > 0 else 0
                            morosidad = row['pct_morosidad']
                            
                            # Color según morosidad usando constantes
                            if morosidad < UmbralesCxC.MOROSIDAD_BAJA:
                                color_linea = ScoreSalud.COLOR_EXCELENTE
                            elif morosidad < UmbralesCxC.MOROSIDAD_MEDIA:
                                color_linea = ScoreSalud.COLOR_REGULAR
                            elif morosidad < UmbralesCxC.MOROSIDAD_ALTA:
                                color_linea = ScoreSalud.COLOR_MALO
                            else:
                                color_linea = ScoreSalud.COLOR_CRITICO
                            
                            with cols_linea[j]:
                                fig_linea = go.Figure(go.Indicator(
                                    mode="gauge+number",
                                    value=pct_total,
                                    domain={'x': [0, 1], 'y': [0, 1]},
                                    title={'text': f"<b>{linea}</b><br>${total:,.2f}", 'font': {'size': 12}},
                                    number={'suffix': '%', 'font': {'size': 18}},
                                    gauge={
                                        'axis': {'range': [None, 100], 'tickwidth': 1},
                                        'bar': {'color': color_linea, 'thickness': 0.75},
                                        'bgcolor': "white",
                                        'borderwidth': 1,
                                        'bordercolor': "gray",
                                        'steps': [
                                            {'range': [0, 25], 'color': '#E8F5E9'},
                                            {'range': [25, 50], 'color': '#FFF9C4'},
                                            {'range': [50, 100], 'color': '#FFEBEE'}
                                        ]
                                    }
                                ))
                                fig_linea.update_layout(
                                    height=200,
                                    margin=dict(t=60, b=10, l=10, r=10)
                                )
                                st.plotly_chart(fig_linea, width='stretch')
                                st.caption(f"Morosidad: {morosidad:.1f}% | Clientes: {row['clientes']}")
                
                st.write("---")
                
                # Tabla comparativa de líneas
                st.write("### 📊 Comparativa de Líneas de Negocio")
                
                df_comparativa = df_lineas_metricas.copy()
                df_comparativa['% del Total'] = (df_comparativa['total'] / total_adeudado * 100)
                
                # Agregar semáforos de morosidad usando helper
                df_comparativa['Alerta Morosidad'] = df_comparativa['pct_morosidad'].apply(obtener_semaforo_morosidad)
                
                df_comparativa['Alerta Riesgo Alto'] = df_comparativa['pct_alto_riesgo'].apply(obtener_semaforo_riesgo)
                
                # Formatear para display
                df_display = df_comparativa[[
                    'linea', 'total', '% del Total', 'pct_morosidad', 
                    'Alerta Morosidad', 'pct_alto_riesgo', 'Alerta Riesgo Alto',
                    'pct_concentracion', 'clientes', 'docs'
                ]].copy()
                
                df_display['total'] = df_display['total'].apply(lambda x: f"${x:,.2f}")
                df_display['% del Total'] = df_display['% del Total'].apply(lambda x: f"{x:.1f}%")
                df_display['pct_morosidad'] = df_display['pct_morosidad'].apply(lambda x: f"{x:.1f}%")
                df_display['pct_alto_riesgo'] = df_display['pct_alto_riesgo'].apply(lambda x: f"{x:.1f}%")
                df_display['pct_concentracion'] = df_display['pct_concentracion'].apply(lambda x: f"{x:.1f}%")
                
                df_display.columns = [
                    'Línea', 'Monto Total', '% Total', 'Morosidad', '🚦 Morosidad',
                    'Riesgo Alto', '🚦 Riesgo Alto', 'Concentración', 'Clientes', 'Docs'
                ]
                
                st.dataframe(df_display, width='stretch', hide_index=True)
                
                # =====================================================================
                # SISTEMA DE SCORING Y PRIORIZACIÓN DE RIESGOS
                # =====================================================================
                st.write("### ⚠️ Líneas que Requieren Atención")
                
                # Calcular score de riesgo ponderado (0-100)
                # Pesos: Morosidad 50%, Riesgo Alto 35%, Concentración 15%
                df_lineas_metricas['score_riesgo'] = (
                    df_lineas_metricas['pct_morosidad'] * 0.50 +
                    df_lineas_metricas['pct_alto_riesgo'] * 0.35 +
                    df_lineas_metricas['pct_concentracion'] * 0.15
                )
                
                # Clasificar por nivel de riesgo
                def clasificar_riesgo(score):
                    if score >= 60:
                        return '🔴 Crítico'
                    elif score >= 40:
                        return '🟠 Alto'
                    elif score >= 25:
                        return '🟡 Medio'
                    else:
                        return '🟢 Bajo'
                
                df_lineas_metricas['nivel_riesgo'] = df_lineas_metricas['score_riesgo'].apply(clasificar_riesgo)
                
                # Filtrar líneas que requieren atención (score >= 25)
                lineas_problematicas = df_lineas_metricas[
                    df_lineas_metricas['score_riesgo'] >= 25
                ].copy()
                
                # Ordenar por score de riesgo (descendente)
                lineas_problematicas = lineas_problematicas.sort_values('score_riesgo', ascending=False)
                
                if len(lineas_problematicas) > 0:
                    # Gráfico de distribución de riesgos (Pie Chart)
                    col_pie, col_list = st.columns([1, 2])
                    
                    with col_pie:
                        st.write("**Clasificación de Riesgos**")
                        
                        # Contar líneas por nivel de riesgo
                        conteo_riesgos = df_lineas_metricas['nivel_riesgo'].value_counts().sort_index()
                        
                        fig_pie_riesgo = go.Figure(data=[go.Pie(
                            labels=conteo_riesgos.index,
                            values=conteo_riesgos.values,
                            marker=dict(colors=['#B71C1C', '#FF9800', '#FFEB3B', '#4CAF50']),
                            textinfo='label+percent',
                            textposition='outside',
                            hole=0.4
                        )])
                        fig_pie_riesgo.update_layout(
                            showlegend=True,
                            height=300,
                            margin=dict(t=20, b=20, l=20, r=20)
                        )
                        st.plotly_chart(fig_pie_riesgo, use_container_width=True)
                    
                    with col_list:
                        st.write("**Líneas Priorizadas por Riesgo**")
                        
                        # Mostrar lista ordenada con detalles
                        for idx, linea_prob in lineas_problematicas.iterrows():
                            problemas = []
                            if linea_prob['pct_morosidad'] > 25:
                                problemas.append(f"Morosidad alta: {linea_prob['pct_morosidad']:.1f}%")
                            if linea_prob['pct_alto_riesgo'] > 15:
                                problemas.append(f"Riesgo alto: {linea_prob['pct_alto_riesgo']:.1f}%")
                            if linea_prob['pct_concentracion'] > 50:
                                problemas.append(f"Alta concentración: {linea_prob['pct_concentracion']:.1f}%")
                            
                            # Mostrar con badge de nivel y score
                            nivel_emoji = linea_prob['nivel_riesgo']
                            score = linea_prob['score_riesgo']
                            
                            st.warning(
                                f"{nivel_emoji} **{linea_prob['linea']}** "
                                f"(Score: {score:.1f}%)\n\n"
                                f"{' | '.join(problemas)}"
                            )
                else:
                    st.success("✅ Todas las líneas de negocio están dentro de parámetros aceptables")
                
                # Gráfico de comparación
                st.write("### 📈 Comparación Visual por Línea")
                
                col_chart1, col_chart2 = st.columns(2)
                
                with col_chart1:
                    # Gráfico de monto por línea
                    fig_monto_lineas = px.bar(
                        df_lineas_metricas,
                        x='linea',
                        y='total',
                        title='Monto CxC por Línea de Negocio',
                        labels={'linea': 'Línea', 'total': 'Monto ($)'},
                        color='pct_morosidad',
                        color_continuous_scale=['green', 'yellow', 'orange', 'red'],
                        range_color=[0, 100]  # Fijar escala de 0 a 100%
                    )
                    fig_monto_lineas.update_layout(height=400)
                    st.plotly_chart(fig_monto_lineas, width='stretch')
                
                with col_chart2:
                    # Gráfico de morosidad por línea
                    fig_morosidad_lineas = px.bar(
                        df_lineas_metricas,
                        x='linea',
                        y='pct_morosidad',
                        title='Índice de Morosidad por Línea',
                        labels={'linea': 'Línea', 'pct_morosidad': 'Morosidad (%)'},
                        color='pct_morosidad',
                        color_continuous_scale=['green', 'yellow', 'orange', 'red'],
                        range_color=[0, 100]  # Fijar escala de 0 a 100%
                    )
                    fig_morosidad_lineas.update_layout(height=400)
                    st.plotly_chart(fig_morosidad_lineas, width='stretch')
                
                st.write("---")
            else:
                st.info("ℹ️ No hay datos de línea de negocio disponibles para análisis")
        else:
            st.info("ℹ️ No se encontró información de línea de negocio en los datos")

        # Análisis de riesgo por antigüedad
        st.subheader("📅 Perfil de Riesgo por Antigüedad")
        if 'dias_overdue' in df_deudas.columns:
            try:
                df_riesgo = df_np.copy()
                
                # Clasificación de riesgo usando constantes
                df_riesgo['nivel_riesgo'] = clasificar_antiguedad(df_riesgo, tipo='completo')
                
                # Resumen de riesgo
                riesgo_df = df_riesgo.groupby('nivel_riesgo', observed=True)['saldo_adeudado'].sum().reset_index()
                riesgo_df['porcentaje'] = (riesgo_df['saldo_adeudado'] / total_adeudado) * 100
                
                # Ordenar por nivel de riesgo
                riesgo_df = riesgo_df.sort_values('nivel_riesgo')
                
                # Pie Chart: Distribución por antigüedad
                with col_pie2:
                    st.write("**Distribución por Antigüedad**")
                    # Asignar colores según severidad de cada categoría
                    colores_pie = [MAPA_COLORES_RIESGO.get(nivel, '#808080') for nivel in riesgo_df['nivel_riesgo']]
                    fig_antiguedad = go.Figure(data=[go.Pie(
                        labels=riesgo_df['nivel_riesgo'].tolist(),
                        values=riesgo_df['saldo_adeudado'].tolist(),
                        marker=dict(colors=colores_pie),
                        hole=ConfigVisualizacion.PIE_HOLE,
                        textinfo='label+percent',
                        textposition='outside'
                    )])
                    fig_antiguedad.update_layout(
                        showlegend=True,
                        height=ConfigVisualizacion.PIE_HEIGHT,
                        margin=dict(t=20, b=20, l=20, r=20)
                    )
                    st.plotly_chart(fig_antiguedad, width='stretch')
                
                # Gauges por categoría de riesgo
                st.write("### 🎯 Indicadores de Riesgo por Antigüedad")
                
                # Crear gauges en filas de 3
                num_categorias = len(riesgo_df)
                for i in range(0, num_categorias, 3):
                    cols_gauge = st.columns(3)
                    
                    for j in range(3):
                        if i + j < num_categorias:
                            row = riesgo_df.iloc[i + j]
                            nivel = row['nivel_riesgo']
                            pct = row['porcentaje']
                            monto = row['saldo_adeudado']
                            # Asignar color según severidad del nivel, no según índice
                            color = MAPA_COLORES_RIESGO.get(nivel, '#808080')  # Gris por defecto
                            
                            with cols_gauge[j]:
                                # Crear gauge con plotly
                                fig_gauge = go.Figure(go.Indicator(
                                    mode="gauge+number+delta",
                                    value=pct,
                                    domain={'x': [0, 1], 'y': [0, 1]},
                                    title={'text': f"{nivel}<br>${monto:,.2f}", 'font': {'size': 14}},
                                    delta={'reference': 100/num_categorias, 'suffix': 'pp'},
                                    number={'suffix': '%', 'font': {'size': 20}},
                                    gauge={
                                        'axis': {'range': [None, 100], 'tickwidth': 1, 'tickcolor': "darkgray"},
                                        'bar': {'color': color},
                                        'bgcolor': "white",
                                        'borderwidth': 2,
                                        'bordercolor': "gray",
                                        'steps': [
                                            {'range': [0, 50], 'color': '#E8F5E9'},
                                            {'range': [50, 100], 'color': '#FFEBEE'}
                                        ],
                                        'threshold': {
                                            'line': {'color': "red", 'width': 4},
                                            'thickness': 0.75,
                                            'value': 100/num_categorias
                                        }
                                    }
                                ))
                                fig_gauge.update_layout(
                                    height=ConfigVisualizacion.GAUGE_HEIGHT,
                                    margin=dict(t=50, b=0, l=20, r=20)
                                )
                                st.plotly_chart(fig_gauge, width='stretch')
                
                st.write("---")
                
                # Mostrar tabla resumen (reemplaza tarjetas HTML)
                st.write("### 📋 Resumen Detallado por Categoría")
                resumen_tabla = riesgo_df.copy()
                resumen_tabla['Monto'] = resumen_tabla['saldo_adeudado'].apply(lambda x: f"${x:,.2f}")
                resumen_tabla['% del Total'] = resumen_tabla['porcentaje'].apply(lambda x: f"{x:.1f}%")
                resumen_tabla = resumen_tabla[['nivel_riesgo', 'Monto', '% del Total']]
                resumen_tabla.columns = ['Categoría', 'Monto Adeudado', '% del Total']
                st.dataframe(resumen_tabla, width='stretch', hide_index=True)
                
                # Gráfico de barras con colores por categoría
                st.write("### 📊 Distribución de Deuda por Antigüedad")
                fig, ax = plt.subplots(figsize=(10, 5))
                # Asignar colores según severidad de cada categoría
                colores_barras = [MAPA_COLORES_RIESGO.get(nivel, '#808080') for nivel in riesgo_df['nivel_riesgo']]
                bars = ax.bar(riesgo_df['nivel_riesgo'], riesgo_df['saldo_adeudado'], color=colores_barras)
                ax.set_title('Distribución por Antigüedad de Deuda')
                ax.set_ylabel('Monto Adeudado ($)')
                ax.yaxis.set_major_formatter('${x:,.2f}')
                plt.xticks(rotation=45)
                
                # Agregar etiquetas de valor
                for bar in bars:
                    height = bar.get_height()
                    ax.annotate(f'${height:,.2f}',
                                xy=(bar.get_x() + bar.get_width() / 2, height),
                                xytext=(0, 3),  # 3 points vertical offset
                                textcoords="offset points",
                                ha='center', va='bottom')
                
                st.pyplot(fig, clear_figure=True)
                plt.close(fig)
                
            except KeyError as e:
                st.error(f"❌ Columna requerida no encontrada: {e}")
                logger.error(f"Columna faltante en análisis de vencimientos: {e}")
            except ValueError as e:
                st.error(f"❌ Error en valores de vencimientos: {e}")
                logger.error(f"Valor inválido en vencimientos: {e}")
            except Exception as e:
                st.error(f"❌ Error en análisis de vencimientos: {str(e)}")
                logger.exception(f"Error inesperado en vencimientos: {e}")
        else:
            st.warning("ℹ️ No se encontró columna de vencimiento")
            
        # =====================================================================
        # ANÁLISIS DE AGENTES (VENDEDORES) CON LÓGICA DE ANTIGÜEDAD
        # =====================================================================
        st.subheader("👤 Distribución de Deuda por Agente")
        
        if 'vendedor' in df_deudas.columns:
            # Usar cartera NO pagada y días de atraso estándar
            df_agentes = df_np.copy()

            if 'dias_overdue' in df_agentes.columns:
                # Definir categorías usando constantes
                df_agentes['categoria_agente'] = clasificar_antiguedad(df_agentes, tipo='agentes')
                
                # Agrupar por agente y categoría
                agente_categoria = df_agentes.groupby(['vendedor', 'categoria_agente'], observed=True)['saldo_adeudado'].sum().unstack().fillna(0)
                
                # Ordenar por el total de deuda
                agente_categoria['Total'] = agente_categoria.sum(axis=1)
                agente_categoria = agente_categoria.sort_values('Total', ascending=False)

                # Pies solicitados: % deuda por agente y antigüedad (por agente)
                st.write("### 🥧 % de Deuda por Agente y por Antigüedad")
                col_pie_ag1, col_pie_ag2 = st.columns(2)

                with col_pie_ag1:
                    fig_pie_agente = go.Figure(data=[go.Pie(
                        labels=agente_categoria.index.astype(str).tolist(),
                        values=agente_categoria['Total'].tolist(),
                        hole=0.4,
                        textinfo='label+percent'
                    )])
                    fig_pie_agente.update_layout(
                        title="Deuda por Agente (% del total)",
                        height=360,
                        margin=dict(t=50, b=20, l=20, r=20)
                    )
                    st.plotly_chart(fig_pie_agente, width='stretch')

                with col_pie_ag2:
                    agentes_list = agente_categoria.index.astype(str).tolist()
                    agente_sel = st.selectbox("Agente", agentes_list, index=0, key="pie_agente_antiguedad") if agentes_list else None
                    if agente_sel:
                        fila = agente_categoria.loc[agente_sel].drop(labels=['Total'], errors='ignore')
                        fila = fila.reindex(LABELS_ANTIGUEDAD_AGENTES).fillna(0)
                        fig_pie_ant = go.Figure(data=[go.Pie(
                            labels=fila.index.tolist(),
                            values=fila.values.tolist(),
                            hole=ConfigVisualizacion.PIE_HOLE,
                            marker=dict(colors=COLORES_ANTIGUEDAD_AGENTES),
                            textinfo='label+percent'
                        )])
                        fig_pie_ant.update_layout(
                            title=f"Antigüedad de la Deuda ({agente_sel})",
                            height=360,
                            margin=dict(t=50, b=20, l=20, r=20)
                        )
                        st.plotly_chart(fig_pie_ant, width='stretch')
                
                # Crear gráfico de barras apiladas
                st.write("### 📊 Distribución por Agente y Antigüedad")
                fig, ax = plt.subplots(figsize=(12, 6))
                
                # Preparar datos para el gráfico usando constantes
                bottom = np.zeros(len(agente_categoria))
                for i, categoria in enumerate(LABELS_ANTIGUEDAD_AGENTES):
                    if categoria in agente_categoria.columns:
                        valores = agente_categoria[categoria]
                        ax.bar(agente_categoria.index, valores, bottom=bottom, label=categoria, color=COLORES_ANTIGUEDAD_AGENTES[i])
                        bottom += valores
                
                # Personalizar gráfico
                ax.set_title('Deuda por Agente y Antigüedad', fontsize=14)
                ax.set_ylabel('Monto Adeudado ($)', fontsize=12)
                ax.set_xlabel('Agente', fontsize=12)
                ax.tick_params(axis='x', rotation=45)
                ax.legend(title='Días Vencidos', loc='upper right')
                ax.yaxis.set_major_formatter('${x:,.2f}')
                
                st.pyplot(fig)
                
                # Mostrar tabla resumen
                st.write("### 📋 Resumen por Agente")
                resumen_agente = agente_categoria.copy()
                resumen_agente = resumen_agente.sort_values('Total', ascending=False)
                
                # Formatear valores
                for col in resumen_agente.columns:
                    if col != 'Total':
                        resumen_agente[col] = resumen_agente[col].apply(lambda x: f"${x:,.2f}" if x > 0 else "")
                resumen_agente['Total'] = resumen_agente['Total'].apply(lambda x: f"${x:,.2f}")
                
                st.dataframe(resumen_agente)
                
                # =====================================================================
                # EFICIENCIA DE COBRANZA POR AGENTE
                # =====================================================================
                st.write("---")
                st.subheader("⚡ Eficiencia de Cobranza por Agente")
                
                # Calcular métricas de eficiencia por agente
                agentes_eficiencia = []
                
                for agente in df_agentes['vendedor'].unique():
                    agente_data = df_agentes[df_agentes['vendedor'] == agente]
                    
                    total_agente = agente_data['saldo_adeudado'].sum()
                    vigente_agente = agente_data[agente_data['dias_overdue'] <= 0]['saldo_adeudado'].sum()
                    vencido_agente = total_agente - vigente_agente
                    
                    # % Efectividad (cartera vigente)
                    efectividad = (vigente_agente / total_agente * 100) if total_agente > 0 else 0
                    
                    # Tiempo promedio de cobro
                    dias_promedio = agente_data['dias_overdue'].mean() if len(agente_data) > 0 else 0
                    
                    # Cantidad de clientes y documentos
                    clientes_agente = agente_data['deudor'].nunique()
                    docs_agente = len(agente_data)
                    
                    # Casos críticos (>90 días)
                    casos_criticos = len(agente_data[agente_data['dias_overdue'] > 90])
                    pct_criticos = (casos_criticos / docs_agente * 100) if docs_agente > 0 else 0
                    
                    # Monto promedio por cliente
                    monto_promedio = total_agente / clientes_agente if clientes_agente > 0 else 0
                    
                    # Score de eficiencia (0-100)
                    # Factores: efectividad (50%), días promedio (30%), casos críticos (20%)
                    score_efectividad = efectividad * 0.5
                    score_dias = max(0, 100 - (dias_promedio / 90 * 100)) * 0.3
                    score_criticos = max(0, 100 - pct_criticos) * 0.2
                    
                    score_eficiencia = score_efectividad + score_dias + score_criticos
                    
                    agentes_eficiencia.append({
                        'agente': agente,
                        'total': total_agente,
                        'efectividad': efectividad,
                        'dias_promedio': dias_promedio,
                        'clientes': clientes_agente,
                        'docs': docs_agente,
                        'casos_criticos': casos_criticos,
                        'pct_criticos': pct_criticos,
                        'monto_promedio': monto_promedio,
                        'score': score_eficiencia
                    })
                
                df_eficiencia = pd.DataFrame(agentes_eficiencia)
                df_eficiencia = df_eficiencia.sort_values('score', ascending=False)
                
                # Gauges de eficiencia por agente (top 6)
                st.write("### 🎯 Score de Eficiencia por Agente")
                
                top_agentes_ef = df_eficiencia.head(6)
                
                for i in range(0, len(top_agentes_ef), 3):
                    cols_agente = st.columns(3)
                    
                    for j in range(3):
                        if i + j < len(top_agentes_ef):
                            row = top_agentes_ef.iloc[i + j]
                            agente = row['agente']
                            score = row['score']
                            efectividad = row['efectividad']
                            
                            # Color según score
                            if score >= 80:
                                color_agente = "#4CAF50"
                                nivel_agente = "Excelente"
                            elif score >= 60:
                                color_agente = "#8BC34A"
                                nivel_agente = "Bueno"
                            elif score >= 40:
                                color_agente = "#FFEB3B"
                                nivel_agente = "Regular"
                            elif score >= 20:
                                color_agente = "#FF9800"
                                nivel_agente = "Bajo"
                            else:
                                color_agente = "#F44336"
                                nivel_agente = "Crítico"
                            
                            with cols_agente[j]:
                                fig_agente_ef = go.Figure(go.Indicator(
                                    mode="gauge+number",
                                    value=score,
                                    domain={'x': [0, 1], 'y': [0, 1]},
                                    title={'text': f"<b>{agente}</b><br>{nivel_agente}", 'font': {'size': 11}},
                                    number={'suffix': '', 'font': {'size': 20}},
                                    gauge={
                                        'axis': {'range': [None, 100], 'tickwidth': 1},
                                        'bar': {'color': color_agente, 'thickness': 0.75},
                                        'bgcolor': "white",
                                        'borderwidth': 1,
                                        'bordercolor': "gray",
                                        'steps': [
                                            {'range': [0, 20], 'color': '#FFCDD2'},
                                            {'range': [20, 40], 'color': '#FFE0B2'},
                                            {'range': [40, 60], 'color': '#FFF9C4'},
                                            {'range': [60, 80], 'color': '#DCEDC8'},
                                            {'range': [80, 100], 'color': '#C8E6C9'}
                                        ],
                                        'threshold': {
                                            'line': {'color': "black", 'width': 3},
                                            'thickness': 0.75,
                                            'value': 60
                                        }
                                    }
                                ))
                                fig_agente_ef.update_layout(
                                    height=220,
                                    margin=dict(t=60, b=10, l=10, r=10)
                                )
                                st.plotly_chart(fig_agente_ef, width='stretch')
                                st.caption(f"Efectividad: {efectividad:.1f}% | Clientes: {row['clientes']}")
                
                # Tabla comparativa de eficiencia
                st.write("### 📊 Tabla Comparativa de Eficiencia")
                
                df_ef_display = df_eficiencia.copy()
                
                # Agregar semáforos
                df_ef_display['🚦 Score'] = df_ef_display['score'].apply(
                    lambda x: "🟢" if x >= 80 else "�" if x >= 60 else "🟠" if x >= 40 else "🟠" if x >= 20 else "🔴"
                )
                
                df_ef_display['🚦 Efectividad'] = df_ef_display['efectividad'].apply(
                    lambda x: "🟢" if x >= 80 else "🟡" if x >= 60 else "🟠" if x >= 40 else "🔴"
                )
                
                # Formatear
                df_ef_table = df_ef_display[[
                    'agente', 'score', '🚦 Score', 'efectividad', '🚦 Efectividad',
                    'dias_promedio', 'casos_criticos', 'pct_criticos', 'clientes', 'total'
                ]].copy()
                
                df_ef_table['score'] = df_ef_table['score'].apply(lambda x: f"{x:.1f}")
                df_ef_table['efectividad'] = df_ef_table['efectividad'].apply(lambda x: f"{x:.1f}%")
                df_ef_table['dias_promedio'] = df_ef_table['dias_promedio'].apply(lambda x: f"{x:.0f} días")
                df_ef_table['pct_criticos'] = df_ef_table['pct_criticos'].apply(lambda x: f"{x:.1f}%")
                df_ef_table['total'] = df_ef_table['total'].apply(lambda x: f"${x:,.2f}")
                
                df_ef_table.columns = [
                    'Agente', 'Score', '🚦 Score', 'Efectividad', '🚦 Efectividad',
                    'Días Prom.', 'Casos >90d', '% Críticos', 'Clientes', 'Cartera Total'
                ]
                
                st.dataframe(df_ef_table, width='stretch', hide_index=True)
                
                # Ranking y reconocimiento
                st.write("### 🏆 Ranking de Eficiencia")
                
                col_rank1, col_rank2, col_rank3 = st.columns(3)
                
                if len(df_eficiencia) >= 1:
                    mejor_agente = df_eficiencia.iloc[0]
                    col_rank1.success(f"🥇 **Mejor Eficiencia**\n\n{mejor_agente['agente']}\n\nScore: {mejor_agente['score']:.1f}/100")
                
                if len(df_eficiencia) >= 2:
                    segundo_agente = df_eficiencia.iloc[1]
                    col_rank2.info(f"🥈 **Segunda Posición**\n\n{segundo_agente['agente']}\n\nScore: {segundo_agente['score']:.1f}/100")
                
                if len(df_eficiencia) >= 3:
                    tercer_agente = df_eficiencia.iloc[2]
                    col_rank3.info(f"🥉 **Tercera Posición**\n\n{tercer_agente['agente']}\n\nScore: {tercer_agente['score']:.1f}/100")
                
                # Agentes que necesitan mejora
                agentes_mejora = df_eficiencia[df_eficiencia['score'] < 40]
                
                if len(agentes_mejora) > 0:
                    st.warning("⚠️ **Agentes que Requieren Capacitación/Apoyo:**")
                    for _, agente_m in agentes_mejora.iterrows():
                        problemas = []
                        if agente_m['efectividad'] < 60:
                            problemas.append(f"Efectividad baja: {agente_m['efectividad']:.1f}%")
                        if agente_m['dias_promedio'] > 60:
                            problemas.append(f"Días promedio alto: {agente_m['dias_promedio']:.0f}")
                        if agente_m['pct_criticos'] > 20:
                            problemas.append(f"Casos críticos: {agente_m['pct_criticos']:.1f}%")
                        
                        st.write(f"- **{agente_m['agente']}** (Score: {agente_m['score']:.1f}): {' | '.join(problemas)}")
                else:
                    st.success("✅ Todos los agentes mantienen niveles aceptables de eficiencia")

            else:
                st.warning("ℹ️ No se pudo calcular la antigüedad (días vencidos) para los agentes")

                # Fallback: resumen simple por agente sin segmentación de antigüedad
                resumen_simple = (
                    df_deudas.groupby('vendedor', dropna=False)['saldo_adeudado']
                    .sum()
                    .sort_values(ascending=False)
                    .reset_index()
                )
                resumen_simple.columns = ['Agente', 'Cartera Total']
                resumen_simple['Cartera Total'] = resumen_simple['Cartera Total'].apply(lambda x: f"${x:,.2f}")
                st.dataframe(resumen_simple, width='stretch', hide_index=True)
        else:
            st.warning("ℹ️ No se encontró información de agentes (vendedores)")

        # Desglose detallado por deudor (CLIENTE - COLUMNA F)
        st.subheader("🔍 Detalle Completo por Deudor (Columna Cliente)")
        deudores = df_deudas['deudor'].unique().tolist()
        selected_deudor = st.selectbox("Seleccionar Deudor", deudores)
        
        # Filtrar datos
        deudor_df = df_deudas[df_deudas['deudor'] == selected_deudor]
        total_deudor = deudor_df['saldo_adeudado'].sum()
        
        st.metric(f"Total Adeudado por {selected_deudor}", f"${total_deudor:,.2f}")
        
        # Mostrar documentos pendientes
        st.write("**Documentos pendientes:**")
        cols = ['fecha_vencimiento', 'saldo_adeudado', 'estatus', 'dias_vencido'] 
        cols = [c for c in cols if c in deudor_df.columns]
        
        # Determinar columna para ordenar (prioridad: fecha_vencimiento, dias_vencido, saldo_adeudado)
        sort_col = None
        if 'fecha_vencimiento' in cols:
            sort_col = 'fecha_vencimiento'
        elif 'dias_vencido' in cols:
            sort_col = 'dias_vencido'
        elif 'saldo_adeudado' in cols:
            sort_col = 'saldo_adeudado'
        
        if sort_col and len(cols) > 0:
            st.dataframe(deudor_df[cols].sort_values(sort_col, ascending=False))
        elif len(cols) > 0:
            st.dataframe(deudor_df[cols])
        else:
            st.warning("No hay columnas disponibles para mostrar")

        # =====================================================================
        # FASE 5: EXPORTACIÓN Y REPORTES
        # =====================================================================
        st.header("📥 Exportación y Reportes")
        
        col_export1, col_export2 = st.columns(2)
        
        with col_export1:
            st.subheader("📊 Reporte Excel Completo")
            st.write("Descarga análisis completo en Excel con múltiples hojas:")
            
            # Crear Excel con múltiples hojas
            from io import BytesIO
            
            buffer = BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                # Hoja 1: Resumen Ejecutivo
                resumen_data = {
                    'Métrica': [
                        'Total Adeudado',
                        'Cartera Vigente',
                        'Deuda Vencida',
                        'Score de Salud',
                        'Índice de Morosidad',
                        'Concentración Top 3',
                        'Riesgo Alto (>90 días)',
                        'Principal Deudor',
                        'Monto Principal Deudor'
                    ],
                    'Valor': [
                        f"${total_adeudado:,.2f}",
                        f"${vigente:,.2f}",
                        f"${vencida:,.2f}",
                        f"{score_salud:.1f}/100 ({score_status})",
                        f"{indice_morosidad:.1f}%",
                        f"{pct_concentracion:.1f}%",
                        f"{pct_alto_riesgo:.1f}% (${deuda_alto_riesgo:,.2f})",
                        top_deudores.index[0],
                        f"${top_deudores.iloc[0]:,.2f}"
                    ]
                }
                df_resumen = pd.DataFrame(resumen_data)
                df_resumen.to_excel(writer, sheet_name='Resumen Ejecutivo', index=False)
                
                # Hoja 2: Detalle Completo - construir con columnas disponibles
                export_cols = ['deudor', 'saldo_adeudado']
                export_cols_optional = ['estatus', 'origen', 'dias_vencido', 'vendedor', col_linea]
                
                # Agregar columnas opcionales que existan
                for col in export_cols_optional:
                    if col and col in df_deudas.columns:
                        export_cols.append(col)
                
                df_detalle_export = df_deudas[export_cols].copy()
                
                # Renombrar col_linea si existe
                if col_linea in df_detalle_export.columns:
                    df_detalle_export = df_detalle_export.rename(columns={col_linea: 'linea_negocio'})
                    
                df_detalle_export.to_excel(writer, sheet_name='Detalle Completo', index=False)
                
                # Hoja 3: Top Deudores
                df_top_export = top_deudores.reset_index()
                df_top_export.columns = ['Cliente', 'Saldo Adeudado']
                df_top_export.to_excel(writer, sheet_name='Top Deudores', index=False)
                
                # Hoja 4: Prioridades de Cobranza
                df_prioridades[['nivel', 'deudor', 'monto', 'dias_max', 'documentos', 'score']].to_excel(
                    writer, sheet_name='Prioridades', index=False
                )
                
                # Hoja 5: Por Línea de Negocio (si existe)
                if 'df_lineas_metricas' in locals():
                    df_lineas_metricas.to_excel(writer, sheet_name='Por Línea Negocio', index=False)
                
                # Hoja 6: Alertas
                if alertas:
                    df_alertas = pd.DataFrame(alertas)
                    df_alertas.to_excel(writer, sheet_name='Alertas', index=False)
            
            buffer.seek(0)
            
            st.download_button(
                label="📥 Descargar Reporte Excel",
                data=buffer.getvalue(),
                file_name=f"reporte_cxc_fradma_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                help="Descarga reporte completo con todas las hojas de análisis"
            )
        
        with col_export2:
            st.subheader("📄 Plantillas de Cobranza")
            st.write("Genera cartas personalizadas de cobranza:")
            
            # Selector de cliente para carta
            cliente_carta = st.selectbox(
                "Seleccionar cliente para carta:",
                options=df_prioridades['deudor'].head(20).tolist(),
                help="Selecciona un cliente de las prioridades de cobranza"
            )
            
            if cliente_carta:
                cliente_info = df_deudas[df_deudas['deudor'] == cliente_carta].iloc[0]
                monto_cliente = df_deudas[df_deudas['deudor'] == cliente_carta]['saldo_adeudado'].sum()
                
                if 'dias_vencido' in df_deudas.columns:
                    dias_vencido_max = df_deudas[df_deudas['deudor'] == cliente_carta]['dias_vencido'].max()
                else:
                    dias_vencido_max = 0
                
                # Determinar tono de la carta según prioridad
                prioridad_cliente = df_prioridades[df_prioridades['deudor'] == cliente_carta]['nivel'].iloc[0]
                
                if "URGENTE" in prioridad_cliente:
                    tono = "Urgente - Última Notificación"
                    apertura = "Por medio de la presente, nos dirigimos a usted con carácter de URGENTE"
                elif "ALTA" in prioridad_cliente:
                    tono = "Recordatorio Formal"
                    apertura = "Por medio de la presente, nos permitimos recordarle"
                else:
                    tono = "Recordatorio Amistoso"
                    apertura = "Nos comunicamos con usted para recordarle amablemente"
                
                # Generar carta
                carta = f"""
**CARTA DE COBRANZA - {tono.upper()}**

Fecha: {datetime.now().strftime('%d de %B de %Y')}

Estimado(a) Cliente: **{cliente_carta}**

{apertura} que a la fecha mantiene un saldo pendiente de pago con nuestra empresa.

**DETALLE DE LA DEUDA:**

- **Monto Total Adeudado:** ${monto_cliente:,.2f} USD
- **Días de Vencimiento:** {int(dias_vencido_max)} días
- **Estado:** {prioridad_cliente}

De acuerdo con nuestros registros, el saldo pendiente corresponde a facturas vencidas que requieren su atención inmediata.

**ACCIONES REQUERIDAS:**

{"⚠️ **ACCIÓN INMEDIATA REQUERIDA:** Le solicitamos contactar a nuestro departamento de crédito y cobranza en las próximas 48 horas para regularizar su situación. De lo contrario, nos veremos en la necesidad de suspender el crédito y/o iniciar acciones legales correspondientes." if "URGENTE" in prioridad_cliente else ""}

{"Le solicitamos ponerse en contacto con nosotros en un plazo no mayor a 5 días hábiles para establecer un plan de pagos o regularizar su situación." if "ALTA" in prioridad_cliente else ""}

{"Le agradeceremos realizar el pago correspondiente a la brevedad posible o contactarnos para cualquier aclaración." if "MEDIA" in prioridad_cliente or "BAJA" in prioridad_cliente else ""}

**DATOS DE CONTACTO:**

- Departamento: Crédito y Cobranza
- Email: cobranza@fradma.com
- Teléfono: (XXX) XXX-XXXX
- Horario: Lunes a Viernes, 9:00 AM - 6:00 PM

Agradecemos su pronta atención y quedamos a su disposición para cualquier aclaración.

Atentamente,

**FRADMA**
Departamento de Crédito y Cobranza

---
*Este documento es un recordatorio generado automáticamente. Para mayor información, favor de contactar a nuestro departamento.*
"""
                
                st.text_area(
                    "Vista previa de carta:",
                    carta,
                    height=400,
                    help="Puedes copiar y personalizar esta carta"
                )
                
                # Botón para descargar carta en txt
                st.download_button(
                    label="📄 Descargar Carta (.txt)",
                    data=carta,
                    file_name=f"carta_cobranza_{cliente_carta.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.txt",
                    mime="text/plain"
                )
        
        st.write("---")

        # Resumen ejecutivo
        st.subheader("📝 Resumen Ejecutivo para Dirección")

        # urgente_count: clientes en nivel URGENTE (calculado desde df_prioridades)
        urgente_count = len(df_prioridades[df_prioridades['nivel_num'] == 1]) \
                        if 'df_prioridades' in dir() and not df_prioridades.empty else 0
        
        # Crear resumen en formato de reporte ejecutivo
        col_resumen1, col_resumen2, col_resumen3 = st.columns(3)
        
        with col_resumen1:
            st.metric("💰 Cartera Total", f"${total_adeudado:,.2f}",
                     help="📐 Suma de todos los saldos adeudados pendientes de pago")
            st.metric("📊 Calificación", f"{score_salud:.0f}/100",
                     help="📐 Score ponderado: 40% liquidez + 30% concentración + 30% morosidad")
            st.caption(f"**{score_status}**")
        
        with col_resumen2:
            st.metric("✅ Vigente", f"{pct_vigente:.1f}%",
                     help="📐 Cartera que aún no ha vencido / Cartera total")
            st.metric("⚠️ Vencida", f"{pct_vencida_total:.1f}%",
                     help="📐 Cartera total vencida (con atraso, sin importar días) / Cartera total")
            st.caption(f"${vencida:,.2f} en atraso")
        
        with col_resumen3:
            st.metric("🎯 Casos Urgentes", urgente_count,
                     help="📐 Número de facturas vencidas > 90 días que requieren atención inmediata")
            st.metric("� Alto Riesgo >90d", f"{pct_alto_riesgo:.1f}%",
                     help="📐 Cartera con más de 90 días vencida / Cartera total (subconjunto crítico de vencida)")
            st.caption(f"${deuda_alto_riesgo:,.2f}")
        
        st.write("**Observaciones Clave:**")
        st.write(f"- Fradma tiene **${total_adeudado:,.2f}** en cuentas por cobrar")
        st.write(f"- El principal deudor es **{top_deudores.index[0]}** con **${top_deudores.iloc[0]:,.2f}** ({(top_deudores.iloc[0]/total_adeudado*100):.1f}% del total)")
        
        if 'dias_vencido' in df_deudas.columns:
            deuda_vencida_total = df_deudas[df_deudas['dias_vencido'] > 0]['saldo_adeudado'].sum()
            st.write(f"- **${deuda_vencida_total:,.2f}** en deuda vencida ({(deuda_vencida_total/total_adeudado*100):.1f}% del total)")
        
        st.write(f"- **{urgente_count} casos** requieren acción urgente inmediata")
        
        if alertas:
            st.write(f"- **{len(alertas)} alertas** activas requieren atención")
        
        st.markdown("---")
        
        # =====================================================================
        # PANEL DE DEFINICIONES Y FÓRMULAS CXC
        # =====================================================================
        with st.expander("📐 **Definiciones y Fórmulas de KPIs CxC**"):
            st.markdown("""
            ### 📊 Métricas de Salud de Cartera
            
            **💰 Cartera Total (Total Adeudado)**
            - **Definición**: Suma de todos los saldos pendientes de cobro
            - **Fórmula**: `Σ Saldo Adeudado (todas las facturas)`
            - **Incluye**: Facturas vigentes + vencidas
            
            **📊 Calificación de Salud (Score 0-100)**
            - **Definición**: Indicador compuesto de la salud financiera de la cartera
            - **Fórmula**: `(40% × Liquidez) + (30% × Concentración) + (30% × Morosidad)`
            - **Escala**: 
              - 🟢 80-100 = Excelente
              - 🟡 60-79 = Buena
              - 🟠 40-59 = Regular
              - 🔴 <40 = Crítica
            
            **✅ Cartera Vigente (%)**
            - **Definición**: Porcentaje de deuda que aún no ha vencido
            - **Fórmula**: `(Saldo con días_restantes > 0 / Total Adeudado) × 100%`
            - **Objetivo**: ≥ 70%
            - **Interpretación**: Mayor % = Mejor salud de cobro
            
            **⚠️ Cartera Vencida - Alto Riesgo (%)**
            - **Definición**: Porcentaje de deuda vencida hace más de 90 días
            - **Fórmula**: `(Saldo con días_vencido > 90 / Total Adeudado) × 100%`
            - **Meta**: < 10%
            - **Criticidad**: Alto - requiere acción legal/cobranza intensiva
            
            **📈 Índice de Morosidad (%)**
            - **Definición**: Porcentaje total de cartera vencida (cualquier cantidad de días)
            - **Fórmula**: `(Saldo total vencido / Total Adeudado) × 100%`
            - **Objetivo**: < 15%
            - **Nota**: Incluye vencimientos de 1-30, 31-60, 61-90, >90 días
            
            **🎯 Casos Urgentes**
            - **Definición**: Número de facturas individuales con vencimiento > 90 días
            - **Fórmula**: `COUNT(Facturas con días_vencido > 90)`
            - **Acción Requerida**: Gestión inmediata de cobranza o provisión
            
            **🏢 Concentración de Riesgo (%)**
            - **Definición**: Porcentaje de cartera concentrado en el top 3 de deudores
            - **Fórmula**: `(Σ Saldo Top 3 Clientes / Total Adeudado) × 100%`
            - **Umbrales**:
              - 🟢 <30% = Riesgo bajo (diversificado)
              - 🟡 30-50% = Riesgo moderado
              - 🔴 >50% = Riesgo alto (concentrado)
            
            ---
            
            ### 📅 Clasificación por Antigüedad
            
            **Vigente (0 días)**
            - Sin vencimiento, aún dentro del plazo de crédito
            - **Fórmula días restantes**: `días_de_credito - días_desde_factura`
            
            **Vencida 1-30 días**
            - Vencimiento reciente, gestión preventiva
            - Riesgo: Bajo
            
            **Vencida 31-60 días**
            - Requiere seguimiento activo
            - Riesgo: Medio
            
            **Vencida 61-90 días**
            - Requiere escalamiento a gerencia
            - Riesgo: Alto
            
            **Vencida >90 días**
            - Requiere acción legal o provisión
            - Riesgo: Crítico
            
            ---
            
            ### 🎨 Escala de Eficiencia en Ventas (para vendedores)
            
            **Score de Eficiencia Individual (%)** 
            - **Fórmula**: `(30% × Liquidez) + (30% × Morosidad⁻¹) + (40% × Recuperación)`
            - **Donde**:
              - Liquidez = % vigente del vendedor
              - Morosidad⁻¹ = 100% - % morosidad
              - Recuperación = % cobrado vs total asignado
            
            **Clasificación**:
            - 🟢 80-100% = Alta eficiencia
            - 🟡 60-79% = Media eficiencia
            - 🟠 40-59% = Baja eficiencia
            - 🔴 <40% = Muy baja eficiencia
            
            ---
            
            ### ⚠️ Métricas NO Disponibles
            
            **DSO (Days Sales Outstanding)**
            - ❌ No calculable sin datos de ventas diarias
            - Requiere: Ventas a crédito del período
            - Fórmula teórica: `(CxC Promedio / Ventas Crédito) × Días`
            
            **Rotación de CxC**
            - ❌ No calculable sin datos de ventas
            - Requiere: Ventas anuales a crédito
            - Fórmula teórica: `Ventas Crédito Anual / CxC Promedio`
            
            **Provisión de Incobrables**
            - ℹ️ Requiere política contable definida
            - Estándar: 1-5% de cartera vencida >90 días
            
            ---
            
            ### 📝 Notas Importantes
            
            - **Columna de identificación**: Se usa "Cliente" (columna F) para agrupar deudores
            - **Cálculo de días**: Basado en columna `dias_restantes` (positivo = vigente) o `dias_vencido` (negativo = overdue)
            - **Moneda**: Todos los montos en USD (convertidos según TC si aplica)
            - **Actualización**: Datos actualizados a la fecha de última factura registrada
            """)
        
        st.info("📌 Este reporte se basa en la columna 'Cliente' (F) para identificar deudores.")

    except KeyError as e:
        st.error(f"❌ Columna requerida no encontrada: {e}")
        st.info("💡 Verifica que el Excel contenga las hojas 'CXC VIGENTES' y 'CXC VENCIDAS'")
        logger.error(f"Columna faltante en CxC: {e}")
    except ValueError as e:
        st.error(f"❌ Error en formato de datos: {e}")
        st.info("💡 Revisa que los montos sean numéricos y fechas válidas")
        logger.error(f"Valor inválido en CxC: {e}")
    except Exception as e:
        st.error(f"❌ Error crítico: {str(e)}")
        logger.exception(f"Error inesperado en CxC: {e}")