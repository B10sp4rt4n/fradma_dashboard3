"""
Módulo de ingesta de CFDIs desde ZIP.

Esta página permite a los usuarios subir un archivo ZIP con XMLs de CFDIs
y procesarlos automáticamente para:
- Parsear los XMLs
- Enriquecer con clasificación IA
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
    from cfdi.enrichment import CFDIEnrichment
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


def mostrar_estadisticas_procesamiento(ventas_parseadas: list, conceptos_enriquecidos: list):
    """
    Muestra estadísticas bonitas del procesamiento.
    
    Args:
        ventas_parseadas: Lista de ventas parseadas
        conceptos_enriquecidos: Lista de conceptos enriquecidos
    """
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


def mostrar_resumen_lineas_negocio(resumen: dict):
    """
    Muestra el resumen por línea de negocio con gráficas.
    
    Args:
        resumen: Diccionario con estadísticas por línea
    """
    st.subheader("📊 Distribución por Línea de Negocio")
    
    # Convertir a DataFrame
    df_resumen = pd.DataFrame([
        {
            'Línea de Negocio': linea.replace('_', ' ').title(),
            'Conceptos': data['total_conceptos'],
            'Importe Total': data['importe_total']
        }
        for linea, data in resumen.items()
    ])
    
    df_resumen = df_resumen.sort_values('Importe Total', ascending=False)
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Gráfica de pastel
        fig_pie = px.pie(
            df_resumen,
            values='Importe Total',
            names='Línea de Negocio',
            title='Distribución de Facturación por Línea',
            hole=0.4
        )
        fig_pie.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig_pie, use_container_width=True)
    
    with col2:
        # Gráfica de barras
        fig_bar = px.bar(
            df_resumen,
            x='Línea de Negocio',
            y='Conceptos',
            title='Número de Conceptos por Línea',
            color='Importe Total',
            color_continuous_scale='Viridis'
        )
        fig_bar.update_xaxes(tickangle=-45)
        st.plotly_chart(fig_bar, use_container_width=True)
    
    # Tabla detallada expandible
    with st.expander("📋 Ver tabla detallada por línea de negocio"):
        df_display = df_resumen.copy()
        df_display['Importe Total'] = df_display['Importe Total'].apply(lambda x: f"${x:,.2f}")
        st.dataframe(df_display, use_container_width=True, hide_index=True)
        
        # Mostrar ejemplos de cada línea
        for linea, data in resumen.items():
            with st.expander(f"Ejemplos: {linea.replace('_', ' ').title()}"):
                ejemplos = data.get('conceptos_ejemplo', [])
                for i, ejemplo in enumerate(ejemplos, 1):
                    st.text(f"{i}. {ejemplo}")


def main():
    """Función principal de la página."""
    
    st.title("📦 Ingesta de CFDIs desde ZIP")
    
    st.markdown("""
    Esta herramienta te permite procesar facturas electrónicas (CFDIs) de forma masiva.
    
    **Características:**
    - ✅ Parseo automático de CFDI 4.0
    - 🤖 Clasificación con IA (GPT-4)
    - 📊 Reportes consolidados
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
        
        usar_ia = st.checkbox(
            "🤖 Usar IA para clasificación",
            value=True,
            help="Usa GPT-4 para clasificar productos. Más preciso pero más lento."
        )
        
        if usar_ia:
            openai_api_key = st.text_input(
                "OpenAI API Key",
                type="password",
                help="Tu API key de OpenAI. Se puede configurar en .env también.",
                value=os.getenv('OPENAI_API_KEY', '')
            )
            
            max_gpt_calls = st.number_input(
                "Máximo de llamadas GPT",
                min_value=0,
                max_value=10000,
                value=1000,
                step=100,
                help="Límite de llamadas a GPT para controlar costos"
            )
        else:
            openai_api_key = None
            max_gpt_calls = 0
        
        guardar_cache = st.checkbox(
            "💾 Guardar caché de clasificaciones",
            value=True,
            help="Guarda clasificaciones previas para acelerar futuros procesamientos"
        )
    
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
            empresa_id = None
    
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
        
        # Leer XMLs
        progress_bar = st.progress(0, text="Leyendo archivos XML...")
        xml_contents, errores_lectura = read_xml_contents(xml_files)
        progress_bar.progress(20, text="Parseando CFDIs...")
        
        if errores_lectura:
            st.warning(f"⚠️ {len(errores_lectura)} archivos no se pudieron leer")
        
        # Parsear CFDIs
        try:
            ventas_parseadas = parse_cfdi_batch(xml_contents)
            progress_bar.progress(50, text=f"✅ {len(ventas_parseadas)} CFDIs parseados correctamente")
        except Exception as e:
            st.error(f"❌ Error parseando CFDIs: {e}")
            progress_bar.empty()
            return
        
        # Enriquecer con IA
        progress_bar.progress(60, text="Enriqueciendo con IA...")
        
        # Extraer todos los conceptos
        todos_conceptos = []
        for venta in ventas_parseadas:
            conceptos = venta.get('conceptos', [])
            todos_conceptos.extend(conceptos)
        
        # Enriquecer
        enricher = CFDIEnrichment(
            api_key=openai_api_key if usar_ia else None,
            use_cache=guardar_cache
        )
        
        conceptos_enriquecidos = enricher.enriquecer_conceptos_batch(
            todos_conceptos,
            usar_gpt=usar_ia,
            max_gpt_calls=max_gpt_calls if usar_ia else 0
        )
        
        progress_bar.progress(80, text="Generando reportes...")
        
        # Generar resumen
        resumen = enricher.generar_resumen(conceptos_enriquecidos)
        
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
        mostrar_estadisticas_procesamiento(ventas_parseadas, conceptos_enriquecidos)
        
        st.markdown("---")
        
        # Resumen por línea de negocio
        mostrar_resumen_lineas_negocio(resumen)
        
        st.markdown("---")
        
        # Opciones de exportación
        st.subheader("💾 Exportar Resultados")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # Exportar resumen como CSV
            df_export = pd.DataFrame([
                {
                    'Línea': linea,
                    'Conceptos': data['total_conceptos'],
                    'Importe': data['importe_total']
                }
                for linea, data in resumen.items()
            ])
            
            csv = df_export.to_csv(index=False)
            st.download_button(
                "📥 Descargar CSV",
                csv,
                "resumen_cfdi.csv",
                "text/csv"
            )
        
        with col2:
            if guardar_cache and len(enricher.cache) > 0:
                st.download_button(
                    "💾 Descargar Caché",
                    str(enricher.cache),
                    "cache_clasificaciones.json",
                    "application/json",
                    help=f"{len(enricher.cache)} clasificaciones en caché"
                )
        
        # Limpiar archivos temporales
        import shutil
        shutil.rmtree(temp_dir) 
        
        st.success("🎉 ¡Procesamiento completado exitosamente!")


if __name__ == "__main__":
    main()
