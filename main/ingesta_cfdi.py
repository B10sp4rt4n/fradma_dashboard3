"""
Módulo de ingesta de CFDIs desde ZIP.

Esta página permite a los usuarios subir un archivo ZIP con XMLs de CFDIs
y procesarlos automáticamente para:
- Parsear los XMLs
- Analizar distribuciones por empresa y producto
- Insertar en base de datos Neon (opcional)
- Generar reportes consolidados

Autor: Fradma Dashboard Team
Fecha: Febrero 2026
"""

import streamlit as st
import zipfile
import tempfile
import os
from pathlib import Path
from datetime import datetime
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# Importar módulos CFDI
try:
    from cfdi.parser import parse_cfdi_batch
    from cfdi.ingestion import NeonIngestion, verify_connection
    CFDI_MODULES_AVAILABLE = True
except ImportError as e:
    st.error(f"Error importando módulos CFDI: {e}")
    CFDI_MODULES_AVAILABLE = False


def extract_zip_to_temp(uploaded_file) -> tuple:
    """
    Extrae un ZIP subido a una carpeta temporal.
    
    Args:
        uploaded_file: Archivo subido por Streamlit
        
    Returns:
        Tupla (temp_dir, xml_files)
    """
    temp_dir = tempfile.mkdtemp(prefix='cfdi_upload_')
    xml_files = []
    
    with zipfile.ZipFile(uploaded_file, 'r') as zip_ref:
        # Listar archivos XML
        all_files = zip_ref.namelist()
        xml_filenames = [f for f in all_files if f.lower().endswith('.xml')]
        
        # Extraer solo XMLs
        for xml_file in xml_filenames:
            zip_ref.extract(xml_file, temp_dir)
            xml_files.append(os.path.join(temp_dir, xml_file))
    
    return temp_dir, xml_files


def read_xml_contents(xml_files: list) -> list:
    """Lee el contenido de múltiples archivos XML."""
    contents = []
    errores = []
    
    for xml_file in xml_files:
        try:
            with open(xml_file, 'r', encoding='utf-8') as f:
                contents.append(f.read())
        except Exception as e:
            errores.append((xml_file, str(e)))
    
    return contents, errores


def mostrar_estadisticas_procesamiento(ventas_parseadas: list, conceptos_enriquecidos: list, 
                                        errores_parseo: list = None, total_archivos: int = None):
    """
    Muestra estadísticas generales del procesamiento.
    
    Args:
        ventas_parseadas: Lista de ventas parseadas
        conceptos_enriquecidos: Lista de conceptos enriquecidos
        errores_parseo: Lista de errores de parseo (opcional)
        total_archivos: Número total de archivos procesados (opcional)
    """
    # Mostrar tasa de éxito si tenemos información de errores
    if errores_parseo is not None and total_archivos is not None:
        exitos = len(ventas_parseadas)
        errores = len(errores_parseo)
        tasa_exito = (exitos / total_archivos * 100) if total_archivos > 0 else 0
        
        col_ex1, col_ex2, col_ex3 = st.columns(3)
        with col_ex1:
            st.metric("✅ CFDIs Exitosos", f"{exitos:,}", f"{tasa_exito:.1f}% del total")
        with col_ex2:
            st.metric("❌ CFDIs con Errores", f"{errores:,}", delta=f"-{errores}" if errores > 0 else None, delta_color="inverse")
        with col_ex3:
            st.metric("📦 Total Archivos", f"{total_archivos:,}")
        
        st.markdown("---")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Total CFDIs",
            f"{len(ventas_parseadas):,}",
            help="Facturas procesadas exitosamente"
        )
    
    with col2:
        total_conceptos = sum(len(v.get('conceptos', [])) for v in ventas_parseadas)
        st.metric(
            "Total Conceptos",
            f"{total_conceptos:,}",
            help="Líneas de productos/servicios"
        )
    
    with col3:
        total_mxn = sum(
            float(v.get('total', 0)) * float(v.get('tipo_cambio', 1))
            for v in ventas_parseadas
        )
        st.metric(
            "Total Facturado",
            f"${total_mxn:,.0f} MXN",
            help="Suma de totales convertidos a MXN"
        )
    
    with col4:
        # Rango de fechas
        fechas = [v.get('fecha_emision') for v in ventas_parseadas if v.get('fecha_emision')]
        if fechas:
            fecha_min = min(fechas)
            fecha_max = max(fechas)
            rango_dias = (fecha_max - fecha_min).days
            st.metric(
                "Rango Temporal",
                f"{rango_dias} días",
                help=f"{fecha_min.strftime('%Y-%m-%d')} a {fecha_max.strftime('%Y-%m-%d')}"
            )


def crear_dataframe_conceptos(ventas_parseadas: list) -> pd.DataFrame:
    """
    Crea un DataFrame completo con todos los conceptos de las facturas.
    
    Args:
        ventas_parseadas: Lista de ventas parseadas
        
    Returns:
        DataFrame con todos los conceptos
    """
    registros = []
    
    for venta in ventas_parseadas:
        # Datos del comprobante
        fecha = venta.get('fecha', '')
        if isinstance(fecha, datetime):
            fecha = fecha.strftime('%Y-%m-%d')
        
        serie = venta.get('serie', '')
        folio = venta.get('folio', '')
        emisor_nombre = venta.get('emisor', {}).get('nombre', '')
        receptor_nombre = venta.get('receptor', {}).get('nombre', '')
        receptor_rfc = venta.get('receptor', {}).get('rfc', '')
        moneda = venta.get('moneda', 'MXN')
        tipo_cambio = float(venta.get('tipo_cambio', 1))
        uuid = venta.get('timbre', {}).get('uuid', '')
        
        # Extraer conceptos
        conceptos = venta.get('conceptos', [])
        
        for concepto in conceptos:
            descripcion = concepto.get('descripcion', '')
            no_identificacion = concepto.get('no_identificacion', '')
            
            registro = {
                'Fecha': fecha,
                'Serie': serie,
                'Folio': folio,
                'UUID': uuid,
                'Emisor': emisor_nombre,
                'Receptor': receptor_nombre,
                'RFC Receptor': receptor_rfc,
                'Clave Producto': no_identificacion,
                'Descripción': descripcion,
                'Cantidad': float(concepto.get('cantidad', 0)),
                'Unidad': concepto.get('unidad', ''),
                'Valor Unitario': float(concepto.get('valor_unitario', 0)),
                'Importe': float(concepto.get('importe', 0)),
                'Moneda': moneda,
                'Tipo Cambio': tipo_cambio,
                'Importe MXN': float(concepto.get('importe', 0)) * tipo_cambio,
            }
            
            registros.append(registro)
    
    return pd.DataFrame(registros)


def mostrar_distribuciones(df_conceptos: pd.DataFrame):
    """
    Muestra distribuciones por empresa y producto.
    
    Args:
        df_conceptos: DataFrame con todos los conceptos
    """
    st.subheader("📊 Distribuciones y Análisis")
    
    tab1, tab2, tab3 = st.tabs(["Por Cliente", "Por Producto", "Por Mes"])
    
    with tab1:
        st.markdown("### 💼 Distribución por Cliente (Receptor)")
        
        # Agrupar por receptor
        df_receptor = df_conceptos.groupby('Receptor').agg({
            'Importe MXN': 'sum',
            'Folio': 'count'
        }).reset_index()
        df_receptor.columns = ['Receptor', 'Total Facturado', 'Número de Conceptos']
        df_receptor = df_receptor.sort_values('Total Facturado', ascending=False)
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Top 10 clientes
            df_top10 = df_receptor.head(10)
            fig_bar = px.bar(
                df_top10,
                x='Total Facturado',
                y='Receptor',
                orientation='h',
                title='Top 10 Clientes por Facturación',
                labels={'Total Facturado': 'Importe MXN'},
                text='Total Facturado'
            )
            fig_bar.update_traces(texttemplate='$%{text:,.0f}', textposition='outside')
            fig_bar.update_layout(yaxis={'categoryorder':'total ascending'})
            st.plotly_chart(fig_bar, use_container_width=True)
        
        with col2:
            # Gráfica de pastel
            fig_pie = px.pie(
                df_top10,
                values='Total Facturado',
                names='Receptor',
                title='Distribución Top 10 Clientes',
                hole=0.4
            )
            fig_pie.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig_pie, use_container_width=True)
        
        # Tabla completa
        with st.expander("📋 Ver todos los clientes"):
            df_display = df_receptor.copy()
            df_display['Total Facturado'] = df_display['Total Facturado'].apply(lambda x: f"${x:,.2f}")
            st.dataframe(df_display, use_container_width=True, hide_index=True)
    
    with tab2:
        st.markdown("### 📦 Distribución por Producto/Servicio")
        
        # Agrupar por descripción
        df_producto = df_conceptos.groupby('Descripción').agg({
            'Importe MXN': 'sum',
            'Cantidad': 'sum',
            'Folio': 'count'
        }).reset_index()
        df_producto.columns = ['Producto/Servicio', 'Total Facturado', 'Cantidad Total', 'Veces Facturado']
        df_producto = df_producto.sort_values('Total Facturado', ascending=False)
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Top 15 productos
            df_top15 = df_producto.head(15)
            fig_bar = px.bar(
                df_top15,
                x='Total Facturado',
                y='Producto/Servicio',
                orientation='h',
                title='Top 15 Productos/Servicios',
                labels={'Total Facturado': 'Importe MXN'},
                color='Total Facturado',
                color_continuous_scale='Viridis'
            )
            fig_bar.update_layout(yaxis={'categoryorder':'total ascending'})
            st.plotly_chart(fig_bar, use_container_width=True)
        
        with col2:
            # Scatter: cantidad vs importe
            fig_scatter = px.scatter(
                df_producto.head(30),
                x='Cantidad Total',
                y='Total Facturado',
                size='Veces Facturado',
                hover_data=['Producto/Servicio'],
                title='Relación Cantidad vs Facturación',
                labels={'Total Facturado': 'Importe MXN', 'Veces Facturado': 'Frecuencia'}
            )
            st.plotly_chart(fig_scatter, use_container_width=True)
        
        # Tabla completa
        with st.expander("📋 Ver todos los productos"):
            df_display = df_producto.copy()
            df_display['Total Facturado'] = df_display['Total Facturado'].apply(lambda x: f"${x:,.2f}")
            df_display['Cantidad Total'] = df_display['Cantidad Total'].apply(lambda x: f"{x:,.2f}")
            st.dataframe(df_display, use_container_width=True, hide_index=True)
    
    with tab3:
        st.markdown("### 📅 Evolución Mensual")
        
        # Convertir fecha a datetime y extraer mes
        df_temp = df_conceptos.copy()
        df_temp['Fecha_dt'] = pd.to_datetime(df_temp['Fecha'], errors='coerce')
        df_temp['Año-Mes'] = df_temp['Fecha_dt'].dt.to_period('M').astype(str)
        
        # Agrupar por mes
        df_mes = df_temp.groupby('Año-Mes').agg({
            'Importe MXN': 'sum',
            'UUID': 'count'
        }).reset_index()
        df_mes.columns = ['Mes', 'Total Facturado', 'Número de Facturas']
        df_mes = df_mes.sort_values('Mes')
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Línea de tiempo - Facturación
            fig_line = px.line(
                df_mes,
                x='Mes',
                y='Total Facturado',
                title='Evolución de Facturación Mensual',
                markers=True,
                labels={'Total Facturado': 'Importe MXN'}
            )
            fig_line.update_traces(line_color='#1f77b4', line_width=3)
            st.plotly_chart(fig_line, use_container_width=True)
        
        with col2:
            # Barras - Número de facturas
            fig_bar = px.bar(
                df_mes,
                x='Mes',
                y='Número de Facturas',
                title='Número de Facturas por Mes',
                color='Total Facturado',
                color_continuous_scale='Blues'
            )
            st.plotly_chart(fig_bar, use_container_width=True)
        
        # Tabla
        with st.expander("📋 Ver datos mensuales"):
            df_display = df_mes.copy()
            df_display['Total Facturado'] = df_display['Total Facturado'].apply(lambda x: f"${x:,.2f}")
            st.dataframe(df_display, use_container_width=True, hide_index=True)


def mostrar_analisis_avanzados(df_conceptos: pd.DataFrame):
    """
    Muestra análisis avanzados sin IA: Pareto, tickets promedio, frecuencia, etc.
    
    Args:
        df_conceptos: DataFrame con todos los conceptos
    """
    st.subheader("🔍 Análisis Avanzados")
    
    tab1, tab2, tab3, tab4 = st.tabs(["💰 KPIs Financieros", "📊 Análisis Pareto", "🔄 Frecuencia", "🎯 Matriz Cliente-Producto"])
    
    with tab1:
        st.markdown("### 💰 Indicadores Financieros Clave")
        
        # KPIs generales
        col1, col2, col3, col4 = st.columns(4)
        
        # Ticket promedio
        ticket_promedio = df_conceptos.groupby(['Serie', 'Folio'])['Importe MXN'].sum().mean()
        with col1:
            st.metric("Ticket Promedio", f"${ticket_promedio:,.2f}")
        
        # Valor promedio por línea
        valor_linea = df_conceptos['Importe MXN'].mean()
        with col2:
            st.metric("Valor Promedio/Línea", f"${valor_linea:,.2f}")
        
        # Cantidad promedio
        cantidad_promedio = df_conceptos['Cantidad'].mean()
        with col3:
            st.metric("Cantidad Promedio", f"{cantidad_promedio:.2f}")
        
        # Precio unitario promedio
        precio_promedio = df_conceptos['Valor Unitario'].mean()
        with col4:
            st.metric("Precio Unit. Promedio", f"${precio_promedio:,.2f}")
        
        st.markdown("---")
        
        # Análisis por cliente
        st.markdown("#### 📈 Métricas por Cliente")
        
        df_cliente_metricas = df_conceptos.groupby('Receptor').agg({
            'Importe MXN': ['sum', 'mean', 'count'],
            'Serie': lambda x: x.nunique(),
            'Folio': lambda x: len(set(zip(x.index, x)))  # Facturas únicas
        }).reset_index()
        
        df_cliente_metricas.columns = ['Cliente', 'Total Comprado', 'Ticket Promedio', 'Líneas Compradas', 'Series Usadas', 'Facturas']
        df_cliente_metricas = df_cliente_metricas.sort_values('Total Comprado', ascending=False)
        
        # Agregar columnas calculadas
        df_cliente_metricas['Valor Promedio/Factura'] = df_cliente_metricas['Total Comprado'] / df_cliente_metricas['Facturas']
        df_cliente_metricas['Líneas/Factura'] = df_cliente_metricas['Líneas Compradas'] / df_cliente_metricas['Facturas']
        
        # Mostrar top 10
        st.dataframe(
            df_cliente_metricas.head(10),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Total Comprado": st.column_config.NumberColumn(format="$%.2f"),
                "Ticket Promedio": st.column_config.NumberColumn(format="$%.2f"),
                "Valor Promedio/Factura": st.column_config.NumberColumn(format="$%.2f"),
                "Líneas/Factura": st.column_config.NumberColumn(format="%.1f"),
            }
        )
        
        # Gráfica de dispersión: Frecuencia vs Ticket
        fig_scatter = px.scatter(
            df_cliente_metricas.head(30),
            x='Facturas',
            y='Ticket Promedio',
            size='Total Comprado',
            hover_data=['Cliente'],
            title='Frecuencia vs Ticket Promedio (Top 30 Clientes)',
            labels={'Facturas': 'Número de Facturas', 'Ticket Promedio': 'Ticket Promedio MXN'}
        )
        st.plotly_chart(fig_scatter, use_container_width=True)
    
    with tab2:
        st.markdown("### 📊 Análisis Pareto (Regla 80/20)")
        
        # Análisis Pareto por cliente
        df_pareto = df_conceptos.groupby('Receptor').agg({
            'Importe MXN': 'sum'
        }).reset_index()
        df_pareto = df_pareto.sort_values('Importe MXN', ascending=False)
        df_pareto['% Acumulado'] = (df_pareto['Importe MXN'].cumsum() / df_pareto['Importe MXN'].sum()) * 100
        df_pareto['Cliente Número'] = range(1, len(df_pareto) + 1)
        df_pareto['% Clientes'] = (df_pareto['Cliente Número'] / len(df_pareto)) * 100
        
        # Encontrar el 80%
        clientes_80 = len(df_pareto[df_pareto['% Acumulado'] <= 80])
        porcentaje_clientes_80 = (clientes_80 / len(df_pareto)) * 100
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Clientes", len(df_pareto))
        with col2:
            st.metric("Clientes Top 80%", f"{clientes_80} ({porcentaje_clientes_80:.1f}%)")
        with col3:
            concentracion = df_pareto.head(10)['Importe MXN'].sum() / df_pareto['Importe MXN'].sum() * 100
            st.metric("Concentración Top 10", f"{concentracion:.1f}%")
        
        # Gráfica de Pareto
        fig_pareto = go.Figure()
        
        # Barras
        fig_pareto.add_trace(go.Bar(
            x=df_pareto['Cliente Número'].head(50),
            y=df_pareto['Importe MXN'].head(50),
            name='Facturación',
            yaxis='y',
            marker_color='#1f77b4'
        ))
        
        # Línea acumulada
        fig_pareto.add_trace(go.Scatter(
            x=df_pareto['Cliente Número'].head(50),
            y=df_pareto['% Acumulado'].head(50),
            name='% Acumulado',
            yaxis='y2',
            line=dict(color='red', width=3),
            mode='lines+markers'
        ))
        
        # Línea del 80%
        fig_pareto.add_hline(y=80, line_dash="dash", line_color="green", yref='y2', annotation_text="80%")
        
        fig_pareto.update_layout(
            title='Curva de Pareto - Clientes',
            xaxis=dict(title='Cliente (ordenado por facturación)'),
            yaxis=dict(title='Facturación MXN', side='left'),
            yaxis2=dict(title='% Acumulado', side='right', overlaying='y', range=[0, 100]),
            legend=dict(x=0.7, y=0.95)
        )
        
        st.plotly_chart(fig_pareto, use_container_width=True)
        
        # Tabla de segmentación
        st.markdown("#### 🎯 Segmentación de Clientes")
        
        df_pareto['Segmento'] = 'C - Cola Larga'
        df_pareto.loc[df_pareto['% Acumulado'] <= 80, 'Segmento'] = 'A - Top 80%'
        df_pareto.loc[(df_pareto['% Acumulado'] > 80) & (df_pareto['% Acumulado'] <= 95), 'Segmento'] = 'B - Medio'
        
        segmentos = df_pareto.groupby('Segmento').agg({
            'Receptor': 'count',
            'Importe MXN': 'sum'
        }).reset_index()
        segmentos.columns = ['Segmento', 'Número de Clientes', 'Facturación Total']
        segmentos['% Facturación'] = (segmentos['Facturación Total'] / segmentos['Facturación Total'].sum()) * 100
        
        st.dataframe(
            segmentos,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Facturación Total": st.column_config.NumberColumn(format="$%.2f"),
                "% Facturación": st.column_config.NumberColumn(format="%.1f%%"),
            }
        )
    
    with tab3:
        st.markdown("### 🔄 Análisis de Frecuencia y Recurrencia")
        
        # Frecuencia de compra por cliente
        df_frecuencia = df_conceptos.copy()
        df_frecuencia['Fecha_dt'] = pd.to_datetime(df_frecuencia['Fecha'], errors='coerce')
        
        df_freq_cliente = df_frecuencia.groupby('Receptor').agg({
            'Folio': 'count',
            'Importe MXN': 'sum',
            'Fecha_dt': ['min', 'max']
        }).reset_index()
        
        df_freq_cliente.columns = ['Cliente', 'Total Transacciones', 'Facturación Total', 'Primera Compra', 'Última Compra']
        df_freq_cliente['Días Activo'] = (df_freq_cliente['Última Compra'] - df_freq_cliente['Primera Compra']).dt.days + 1
        df_freq_cliente['Frecuencia (días)'] = df_freq_cliente['Días Activo'] / df_freq_cliente['Total Transacciones']
        df_freq_cliente = df_freq_cliente.sort_values('Facturación Total', ascending=False)
        
        # Clasificar clientes
        df_freq_cliente['Tipo Cliente'] = 'Ocasional'
        df_freq_cliente.loc[df_freq_cliente['Total Transacciones'] >= 5, 'Tipo Cliente'] = 'Frecuente'
        df_freq_cliente.loc[df_freq_cliente['Total Transacciones'] >= 10, 'Tipo Cliente'] = 'VIP'
        
        col1, col2, col3 = st.columns(3)
        
        tipo_counts = df_freq_cliente['Tipo Cliente'].value_counts()
        with col1:
            st.metric("Clientes Ocasionales", tipo_counts.get('Ocasional', 0))
        with col2:
            st.metric("Clientes Frecuentes", tipo_counts.get('Frecuente', 0))
        with col3:
            st.metric("Clientes VIP", tipo_counts.get('VIP', 0))
        
        # Gráfica de distribución
        fig_tipo = px.pie(
            df_freq_cliente,
            names='Tipo Cliente',
            values='Facturación Total',
            title='Distribución de Facturación por Tipo de Cliente',
            hole=0.4,
            color='Tipo Cliente',
            color_discrete_map={'Ocasional': '#ff7f0e', 'Frecuente': '#2ca02c', 'VIP': '#d62728'}
        )
        st.plotly_chart(fig_tipo, use_container_width=True)
        
        # Tabla top clientes frecuentes
        st.markdown("#### 🏆 Top Clientes por Frecuencia")
        df_display = df_freq_cliente[['Cliente', 'Total Transacciones', 'Facturación Total', 'Frecuencia (días)', 'Tipo Cliente']].head(15)
        st.dataframe(
            df_display,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Facturación Total": st.column_config.NumberColumn(format="$%.2f"),
                "Frecuencia (días)": st.column_config.NumberColumn(format="%.1f"),
            }
        )
    
    with tab4:
        st.markdown("### 🎯 Matriz Cliente-Producto")
        
        st.info("💡 Identifica qué productos compra cada cliente y encuentra oportunidades de cross-selling")
        
        # Top productos por cliente
        df_matriz = df_conceptos.groupby(['Receptor', 'Descripción']).agg({
            'Importe MXN': 'sum',
            'Cantidad': 'sum'
        }).reset_index()
        df_matriz = df_matriz.sort_values('Importe MXN', ascending=False)
        
        # Seleccionar cliente
        clientes_top = df_conceptos.groupby('Receptor')['Importe MXN'].sum().nlargest(20).index.tolist()
        cliente_seleccionado = st.selectbox("Selecciona un cliente para ver su cartera:", clientes_top)
        
        if cliente_seleccionado:
            df_cliente_productos = df_matriz[df_matriz['Receptor'] == cliente_seleccionado]
            
            col1, col2 = st.columns(2)
            
            with col1:
                # Gráfica de productos del cliente
                fig_productos_cliente = px.bar(
                    df_cliente_productos.head(10),
                    x='Importe MXN',
                    y='Descripción',
                    orientation='h',
                    title=f'Top 10 Productos de {cliente_seleccionado}',
                    labels={'Importe MXN': 'Facturación'},
                    color='Importe MXN',
                    color_continuous_scale='Blues'
                )
                fig_productos_cliente.update_layout(yaxis={'categoryorder':'total ascending'})
                st.plotly_chart(fig_productos_cliente, use_container_width=True)
            
            with col2:
                # Estadísticas del cliente
                st.markdown("#### 📊 Estadísticas del Cliente")
                total_productos = len(df_cliente_productos)
                total_facturado = df_cliente_productos['Importe MXN'].sum()
                producto_top = df_cliente_productos.iloc[0]['Descripción']
                concentracion_top = (df_cliente_productos.head(3)['Importe MXN'].sum() / total_facturado) * 100
                
                st.metric("Productos Diferentes", total_productos)
                st.metric("Total Facturado", f"${total_facturado:,.2f}")
                st.metric("Producto Principal", producto_top[:30] + "...")
                st.metric("Concentración Top 3", f"{concentracion_top:.1f}%")
        
        st.markdown("---")
        
        # Análisis de diversificación
        st.markdown("#### 📦 Diversificación de Cartera por Cliente")
        
        df_diversificacion = df_conceptos.groupby('Receptor').agg({
            'Descripción': 'nunique',
            'Importe MXN': 'sum'
        }).reset_index()
        df_diversificacion.columns = ['Cliente', 'Productos Únicos', 'Facturación Total']
        df_diversificacion = df_diversificacion.sort_values('Facturación Total', ascending=False)
        
        # Gráfica de diversificación
        fig_div = px.scatter(
            df_diversificacion.head(30),
            x='Productos Únicos',
            y='Facturación Total',
            size='Productos Únicos',
            hover_data=['Cliente'],
            title='Diversificación: Productos vs Facturación (Top 30)',
            labels={'Productos Únicos': 'Número de Productos Diferentes'}
        )
        st.plotly_chart(fig_div, use_container_width=True)


def mostrar_analisis_precios(df_conceptos: pd.DataFrame):
    """
    Muestra análisis de precios y variaciones.
    
    Args:
        df_conceptos: DataFrame con todos los conceptos
    """
    st.subheader("💵 Análisis de Precios y Variaciones")
    
    tab1, tab2 = st.tabs(["📊 Variación de Precios", "🔍 Productos con Mayor Variación"])
    
    with tab1:
        st.markdown("### 📊 Análisis de Variabilidad de Precios")
        
        st.info("💡 Detecta productos con diferentes precios de venta para identificar oportunidades o inconsistencias")
        
        # Analizar variación de precios por producto
        df_precios = df_conceptos[df_conceptos['Valor Unitario'] > 0].groupby('Descripción').agg({
            'Valor Unitario': ['mean', 'min', 'max', 'std', 'count'],
            'Importe MXN': 'sum'
        }).reset_index()
        
        df_precios.columns = ['Producto', 'Precio Promedio', 'Precio Mínimo', 'Precio Máximo', 'Desv. Estándar', 'Veces Vendido', 'Facturación Total']
        
        # Calcular coeficiente de variación
        df_precios['Coef. Variación %'] = (df_precios['Desv. Estándar'] / df_precios['Precio Promedio']) * 100
        df_precios['Rango de Precio'] = df_precios['Precio Máximo'] - df_precios['Precio Mínimo']
        df_precios['% Variación'] = ((df_precios['Precio Máximo'] - df_precios['Precio Mínimo']) / df_precios['Precio Mínimo']) * 100
        
        # Filtrar productos con más de 1 venta
        df_precios_var = df_precios[df_precios['Veces Vendido'] > 1].copy()
        df_precios_var = df_precios_var.sort_values('Coef. Variación %', ascending=False)
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            productos_estables = len(df_precios_var[df_precios_var['Coef. Variación %'] < 5])
            st.metric("Productos Estables", productos_estables, help="Coef. Variación < 5%")
        
        with col2:
            productos_variables = len(df_precios_var[(df_precios_var['Coef. Variación %'] >= 5) & (df_precios_var['Coef. Variación %'] < 20)])
            st.metric("Productos Variables", productos_variables, help="5% ≤ Coef. Variación < 20%")
        
        with col3:
            productos_muy_variables = len(df_precios_var[df_precios_var['Coef. Variación %'] >= 20])
            st.metric("Muy Variables", productos_muy_variables, help="Coef. Variación ≥ 20%")
        
        with col4:
            precio_promedio_general = df_conceptos['Valor Unitario'].mean()
            st.metric("Precio Unit. Promedio", f"${precio_promedio_general:,.2f}")
        
        # Gráfica de dispersión: Precio promedio vs Variabilidad
        fig_var = px.scatter(
            df_precios_var.head(50),
            x='Precio Promedio',
            y='Coef. Variación %',
            size='Facturación Total',
            hover_data=['Producto', 'Veces Vendido'],
            title='Precio vs Variabilidad (Top 50 productos)',
            labels={'Coef. Variación %': 'Coeficiente de Variación %'}
        )
        fig_var.add_hline(y=20, line_dash="dash", line_color="red", annotation_text="Alta variabilidad")
        fig_var.add_hline(y=5, line_dash="dash", line_color="orange", annotation_text="Variabilidad moderada")
        st.plotly_chart(fig_var, use_container_width=True)
        
        # Mostrar tabla
        with st.expander("📋 Ver productos con mayor variación de precio"):
            df_display = df_precios_var.head(20)
            st.dataframe(
                df_display,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Precio Promedio": st.column_config.NumberColumn(format="$%.2f"),
                    "Precio Mínimo": st.column_config.NumberColumn(format="$%.2f"),
                    "Precio Máximo": st.column_config.NumberColumn(format="$%.2f"),
                    "Desv. Estándar": st.column_config.NumberColumn(format="%.2f"),
                    "Coef. Variación %": st.column_config.NumberColumn(format="%.1f%%"),
                    "% Variación": st.column_config.NumberColumn(format="%.1f%%"),
                    "Facturación Total": st.column_config.NumberColumn(format="$%.2f"),
                }
            )
    
    with tab2:
        st.markdown("### 🔍 Productos con Mayor Variación - Detalle")
        
        # Seleccionar top productos para análisis detallado
        productos_analizar = df_precios_var.head(15)['Producto'].tolist()
        
        if productos_analizar:
            producto_seleccionado = st.selectbox(
                "Selecciona un producto para ver su historial de precios:",
                productos_analizar
            )
            
            if producto_seleccionado:
                # Filtrar datos del producto
                df_producto = df_conceptos[df_conceptos['Descripción'] == producto_seleccionado].copy()
                df_producto['Fecha_dt'] = pd.to_datetime(df_producto['Fecha'], errors='coerce')
                df_producto = df_producto.sort_values('Fecha_dt')
                
                col1, col2 = st.columns(2)
                
                with col1:
                    # Estadísticas del producto
                    st.markdown("#### 📊 Estadísticas")
                    info_producto = df_precios_var[df_precios_var['Producto'] == producto_seleccionado].iloc[0]
                    
                    st.metric("Precio Promedio", f"${info_producto['Precio Promedio']:,.2f}")
                    st.metric("Rango de Precio", f"${info_producto['Precio Mínimo']:,.2f} - ${info_producto['Precio Máximo']:,.2f}")
                    st.metric("Variación", f"{info_producto['% Variación']:.1f}%")
                    st.metric("Veces Vendido", f"{int(info_producto['Veces Vendido'])}")
                
                with col2:
                    # Gráfica de evolución temporal
                    fig_temporal = px.scatter(
                        df_producto,
                        x='Fecha_dt',
                        y='Valor Unitario',
                        size='Cantidad',
                        hover_data=['Receptor', 'Folio'],
                        title=f'Evolución de Precio: {producto_seleccionado[:40]}...',
                        labels={'Fecha_dt': 'Fecha', 'Valor Unitario': 'Precio Unitario'}
                    )
                    fig_temporal.add_hline(
                        y=info_producto['Precio Promedio'],
                        line_dash="dash",
                        line_color="green",
                        annotation_text="Promedio"
                    )
                    st.plotly_chart(fig_temporal, use_container_width=True)
                
                # Tabla de transacciones
                st.markdown("#### 📋 Historial de Transacciones")
                df_historial = df_producto[['Fecha', 'Receptor', 'Folio', 'Cantidad', 'Valor Unitario', 'Importe MXN']].copy()
                st.dataframe(
                    df_historial,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Valor Unitario": st.column_config.NumberColumn(format="$%.2f"),
                        "Importe MXN": st.column_config.NumberColumn(format="$%.2f"),
                    }
                )
                
                # Análisis por cliente
                st.markdown("#### 👥 Precios por Cliente")
                df_precio_cliente = df_producto.groupby('Receptor').agg({
                    'Valor Unitario': 'mean',
                    'Cantidad': 'sum',
                    'Importe MXN': 'sum'
                }).reset_index()
                df_precio_cliente.columns = ['Cliente', 'Precio Promedio', 'Cantidad Total', 'Facturación']
                df_precio_cliente = df_precio_cliente.sort_values('Facturación', ascending=False)
                
                st.dataframe(
                    df_precio_cliente,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Precio Promedio": st.column_config.NumberColumn(format="$%.2f"),
                        "Facturación": st.column_config.NumberColumn(format="$%.2f"),
                    }
                )


def main():
    """Función principal de la página."""
    
    st.title("📦 Ingesta de CFDIs desde ZIP")
    
    st.markdown("""
    Esta herramienta te permite procesar facturas electrónicas (CFDIs) de forma masiva.
    
    **Características:**
    - ✅ Parseo automático de CFDI 4.0
    - 📊 Distribución por empresa y producto
    - 📈 Reportes consolidados personalizables
    - 💾 Guardado opcional en base de datos
    """)
    
    if not CFDI_MODULES_AVAILABLE:
        st.error("Los módulos CFDI no están disponibles. Verifica la instalación.")
        return
    
    # Tabs para organizar la interfaz
    tab1, tab2, tab3 = st.tabs(["📤 Upload", "⚙️ Configuración", "💾 Base de Datos"])
    
    with tab1:
        st.subheader("Subir archivo ZIP")
        
        uploaded_file = st.file_uploader(
            "Selecciona un archivo ZIP con XMLs de CFDIs",
            type=['zip'],
            help="El ZIP debe contener archivos .xml de facturas CFDI 4.0"
        )
        
        if uploaded_file:
            st.success(f"✅ Archivo subido: {uploaded_file.name} ({uploaded_file.size / 1024:.1f} KB)")
    
    with tab2:
        st.subheader("Configuración de Procesamiento")
        
        st.info("ℹ️ Los CFDIs se procesarán sin clasificación automática. Puedes analizar los datos por empresa y producto directamente.")
    
    with tab3:
        st.subheader("Guardar en Base de Datos Neon")
        
        guardar_neon = st.checkbox(
            "💾 Guardar en Neon PostgreSQL",
            value=False,
            help="Guarda los CFDIs procesados en base de datos"
        )
        
        if guardar_neon:
            neon_url = st.text_input(
                "URL de conexión Neon",
                type="password",
                help="postgresql://user:pass@host/db",
                value=os.getenv('NEON_DATABASE_URL', '')
            )
            
            empresa_id = st.number_input(
                "ID de Empresa",
                min_value=1,
                value=1,
                help="ID de la empresa en tabla empresas"
            )
            
            if neon_url and st.button("🔌 Probar conexión"):
                with st.spinner("Probando conexión a Neon..."):
                    if verify_connection(neon_url):
                        st.success("✅ Conexión exitosa a Neon")
                    else:
                        st.error("❌ No se pudo conectar a Neon")
        else:
            neon_url = None
            empresa_id = 1  # ID por defecto si no se guarda en Neon
    
    # Botón principal de procesamiento
    st.markdown("---")
    
    if st.button("🚀 Procesar CFDIs", type="primary", use_container_width=True):
        if not uploaded_file:
            st.error("⚠️ Debes subir un archivo ZIP primero")
            return
        
        # Contenedor para logs y progreso
        st.subheader("📋 Procesamiento")
        
        # Extraer ZIP
        with st.spinner("Extrayendo archivo ZIP..."):
            temp_dir, xml_files = extract_zip_to_temp(uploaded_file)
            st.info(f"📄 Encontrados {len(xml_files)} archivos XML")
        
        if not xml_files:
            st.error("❌ No se encontraron archivos XML en el ZIP")
            return
        
        # Parsear CFDIs directamente desde los archivos
        progress_bar = st.progress(20, text="Parseando CFDIs...")
        
        # Parsear CFDIs
        try:
            resultados = parse_cfdi_batch(xml_files, str(empresa_id))
            ventas_parseadas = resultados['ventas']
            errores_parseo = resultados.get('errores', [])
            
            progress_bar.progress(50, text=f"✅ {len(ventas_parseadas)} CFDIs parseados correctamente")
            
            if errores_parseo:
                st.warning(f"⚠️ {len(errores_parseo)} CFDIs con errores de parseo")
                
                # Mostrar detalles de los errores
                with st.expander("📋 Ver detalles de archivos con errores", expanded=False):
                    st.markdown("**Archivos que no se pudieron procesar:**")
                    
                    # Crear DataFrame con errores
                    df_errores = pd.DataFrame([
                        {
                            'Archivo': err.get('archivo', 'Desconocido'),
                            'Error': str(err.get('error', 'Error desconocido'))[:100]  # Limitar a 100 chars
                        }
                        for err in errores_parseo
                    ])
                    
                    st.dataframe(df_errores, use_container_width=True, hide_index=True)
                    
                    # Botón para descargar reporte de errores
                    csv_errores = df_errores.to_csv(index=False)
                    st.download_button(
                        "📥 Descargar reporte de errores",
                        csv_errores,
                        "errores_parseo_cfdi.csv",
                        "text/csv",
                        help="Descarga un CSV con los detalles de los archivos que fallaron"
                    )
        except Exception as e:
            st.error(f"❌ Error parseando CFDIs: {e}")
            progress_bar.empty()
            return
        
        # Preparar datos
        progress_bar.progress(80, text="Preparando datos...")
        
        # Crear DataFrame completo con todos los conceptos
        df_conceptos = crear_dataframe_conceptos(ventas_parseadas)
        
        # Guardar a Neon si está configurado
        if guardar_neon and neon_url:
            progress_bar.progress(90, text="Guardando en Neon...")
            try:
                with NeonIngestion(neon_url) as ingestion:
                    stats = ingestion.insert_ventas_batch(
                        empresa_id=empresa_id,
                        ventas_list=ventas_parseadas,
                        skip_duplicates=True
                    )
                    
                    st.success(
                        f"💾 Guardado en Neon: "
                        f"{stats['insertados']} insertados, "
                        f"{stats['duplicados']} duplicados, "
                        f"{stats['errores']} errores"
                    )
            except Exception as e:
                st.error(f"❌ Error guardando en Neon: {e}")
        
        progress_bar.progress(100, text="✅ Procesamiento completado")
        progress_bar.empty()
        
        # Mostrar resultados
        st.markdown("---")
        st.subheader("📊 Resultados del Procesamiento")
        
        # Estadísticas generales
        total_archivos = len(xml_files)
        mostrar_estadisticas_procesamiento(
            ventas_parseadas, 
            [],
            errores_parseo=errores_parseo,
            total_archivos=total_archivos
        )
        
        st.markdown("---")
        
        # Tabla completa de conceptos
        st.subheader("📄 Datos Completos de Facturas")
        
        st.info("💡 **Tip:** Esta tabla contiene todos los conceptos parseados. Puedes exportarla a Excel para crear tus propios reportes.")
        
        # Mostrar estadísticas de la tabla
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Registros", f"{len(df_conceptos):,}")
        with col2:
            total_importe = df_conceptos['Importe MXN'].sum()
            st.metric("Importe Total MXN", f"${total_importe:,.2f}")
        with col3:
            receptores_unicos = df_conceptos['Receptor'].nunique()
            st.metric("Receptores Únicos", f"{receptores_unicos}")
        
        # Filtros para la tabla
        with st.expander("🔍 Filtros", expanded=False):
            col_f1, col_f2 = st.columns(2)
            
            with col_f1:
                # Filtro por receptor
                receptores = ['Todos'] + sorted(df_conceptos['Receptor'].unique().tolist())
                receptor_filtro = st.selectbox("Filtrar por Receptor", receptores)
            
            with col_f2:
                # Filtro por rango de fechas
                if 'Fecha' in df_conceptos.columns and not df_conceptos['Fecha'].empty:
                    fechas_unicas = pd.to_datetime(df_conceptos['Fecha'], errors='coerce').dropna()
                    if not fechas_unicas.empty:
                        fecha_min = fechas_unicas.min().date()
                        fecha_max = fechas_unicas.max().date()
                        fecha_filtro = st.date_input(
                            "Rango de Fechas",
                            value=(fecha_min, fecha_max),
                            min_value=fecha_min,
                            max_value=fecha_max
                        )
        
        # Aplicar filtros
        df_filtrado = df_conceptos.copy()
        
        if receptor_filtro != 'Todos':
            df_filtrado = df_filtrado[df_filtrado['Receptor'] == receptor_filtro]
        
        if 'fecha_filtro' in locals() and len(fecha_filtro) == 2:
            df_filtrado['Fecha_dt'] = pd.to_datetime(df_filtrado['Fecha'], errors='coerce')
            df_filtrado = df_filtrado[
                (df_filtrado['Fecha_dt'].dt.date >= fecha_filtro[0]) &
                (df_filtrado['Fecha_dt'].dt.date <= fecha_filtro[1])
            ]
            df_filtrado = df_filtrado.drop('Fecha_dt', axis=1)
        
        # Mostrar tabla
        st.dataframe(
            df_filtrado,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Valor Unitario": st.column_config.NumberColumn(format="$%.2f"),
                "Importe": st.column_config.NumberColumn(format="$%.2f"),
                "Importe MXN": st.column_config.NumberColumn(format="$%.2f"),
                "Tipo Cambio": st.column_config.NumberColumn(format="%.4f"),
            }
        )
        
        st.markdown("---")
        
        # Distribuciones por empresa y producto
        mostrar_distribuciones(df_conceptos)
        
        st.markdown("---")
        
        # Análisis avanzados sin IA
        mostrar_analisis_avanzados(df_conceptos)
        
        st.markdown("---")
        
        # Análisis de precios y variaciones
        mostrar_analisis_precios(df_conceptos)
        
        st.markdown("---")
        
        # Opciones de exportación
        st.subheader("💾 Exportar Datos")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # Exportar tabla completa como CSV
            csv_completo = df_filtrado.to_csv(index=False)
            st.download_button(
                "📥 Descargar CSV Completo",
                csv_completo,
                "facturas_cfdi_completo.csv",
                "text/csv",
                help="Descarga todos los conceptos en formato CSV"
            )
        
        with col2:
            # Exportar a Excel con formato
            import io
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                df_filtrado.to_excel(writer, sheet_name='Facturas', index=False)
                
                # Obtener el workbook y worksheet
                workbook = writer.book
                worksheet = writer.sheets['Facturas']
                
                # Formato para moneda
                money_fmt = workbook.add_format({'num_format': '$#,##0.00'})
                
                # Aplicar formato a columnas de dinero
                for col_num, col_name in enumerate(df_filtrado.columns):
                    if col_name in ['Valor Unitario', 'Importe', 'Importe MXN']:
                        worksheet.set_column(col_num, col_num, 15, money_fmt)
            
            buffer.seek(0)
            st.download_button(
                "📊 Descargar Excel",
                buffer,
                "facturas_cfdi_completo.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                help="Descarga todos los conceptos en formato Excel con formato"
            )
        
        with col3:
            # Exportar datos agrupados por receptor
            df_por_receptor = df_filtrado.groupby('Receptor').agg({
                'Importe MXN': 'sum',
                'Folio': 'count'
            }).reset_index()
            df_por_receptor.columns = ['Receptor', 'Total Facturado', 'Número de Conceptos']
            df_por_receptor = df_por_receptor.sort_values('Total Facturado', ascending=False)
            
            csv_receptor = df_por_receptor.to_csv(index=False)
            st.download_button(
                "📊 Resumen por Cliente",
                csv_receptor,
                "resumen_por_cliente.csv",
                "text/csv",
                help="Resumen con totales por cliente"
            )
        
        # Limpiar archivos temporales
        import shutil
        shutil.rmtree(temp_dir) 
        
        st.success("🎉 ¡Procesamiento completado exitosamente!")


if __name__ == "__main__":
    main()
