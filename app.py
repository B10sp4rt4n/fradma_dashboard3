import streamlit as st
import pandas as pd
from unidecode import unidecode
from main import main_kpi, main_comparativo, heatmap_ventas
from main import kpi_cpc, reporte_ejecutivo
from utils.data_cleaner import limpiar_columnas_texto, detectar_duplicados_similares
from utils.logger import configurar_logger, log_dataframe_info, log_execution_time
from utils.filters import (
    aplicar_filtro_fechas, 
    aplicar_filtro_cliente, 
    aplicar_filtro_monto,
    aplicar_filtro_categoria_riesgo,
    mostrar_resumen_filtros
)
from utils.export_helper import crear_excel_metricas_cxc, crear_reporte_html
from utils.cache_helper import GestorCache, decorador_medicion_tiempo

# Configurar logger de la aplicación
logger = configurar_logger("dashboard_app", nivel="INFO")

# Inicializar gestor de caché
gestor_cache = GestorCache(ttl=300)  # 5 minutos de TTL

# Configuración de página con tema mejorado
st.set_page_config(
    layout="wide",
    page_title="Fradma Dashboard",
    page_icon="📊",
    initial_sidebar_state="expanded"
)

# =====================================================================
# ESTILOS PERSONALIZADOS CSS
# =====================================================================

st.markdown("""
<style>
    /* Mejorar métricas */
    [data-testid="stMetricValue"] {
        font-size: 28px;
        font-weight: 600;
    }
    
    /* Estilo para headers */
    h1 {
        color: #1f77b4;
        padding-bottom: 10px;
        border-bottom: 3px solid #1f77b4;
    }
    
    h2 {
        color: #2c3e50;
        margin-top: 20px;
    }
    
    h3 {
        color: #34495e;
    }
    
    /* Mejorar tablas */
    [data-testid="stDataFrame"] {
        border: 1px solid #e0e0e0;
        border-radius: 5px;
    }
    
    /* Sidebar mejorado */
    [data-testid="stSidebar"] {
        background-color: #f8f9fa;
    }
    
    /* Botones de descarga */
    .stDownloadButton button {
        background-color: #1f77b4;
        color: white;
        border-radius: 5px;
        padding: 10px 20px;
        font-weight: 600;
    }
    
    .stDownloadButton button:hover {
        background-color: #1557a0;
    }
    
    /* Expanders */
    [data-testid="stExpander"] {
        border: 1px solid #e0e0e0;
        border-radius: 5px;
        margin-bottom: 10px;
    }
    
    /* Success/Warning/Error boxes */
    .stAlert {
        border-radius: 5px;
        padding: 15px;
    }
    
    /* Tooltips más visibles */
    [data-testid="stTooltipIcon"] {
        color: #1f77b4;
    }

    /* Sidebar (menú) en azul oscuro */
    [data-testid="stSidebar"] > div:first-child {
        background-color: #0b1f3a;
    }

    /* Texto y labels del sidebar en claro para contraste */
    [data-testid="stSidebar"],
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] span,
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3,
    [data-testid="stSidebar"] h4 {
        color: #ffffff;
    }

    /* Inputs del sidebar con fondo claro (para que se vean) */
    [data-testid="stSidebar"] input,
    [data-testid="stSidebar"] textarea,
    [data-testid="stSidebar"] select {
        color: #111827;
        background-color: #ffffff;
    }

    /* Contenedores de widgets (radio/checkbox/select) */
    [data-testid="stSidebar"] [data-baseweb="radio"],
    [data-testid="stSidebar"] [data-baseweb="checkbox"],
    [data-testid="stSidebar"] [data-baseweb="select"] {
        color: #ffffff;
    }
</style>
""", unsafe_allow_html=True)

# =====================================================================
# HEADER DEL DASHBOARD
# =====================================================================

col_logo, col_title = st.columns([1, 4])

with col_logo:
    st.markdown("# 📊")

with col_title:
    st.title("Fradma Dashboard")
    st.caption("Sistema Integrado de Análisis de Ventas y CxC")

st.markdown("---")

# 🛠️ FUNCIÓN: Normalización de encabezados
def normalizar_columnas(df):
    nuevas_columnas = []
    for col in df.columns:
        col_str = str(col).lower().strip().replace(" ", "_")
        col_str = unidecode(col_str)
        nuevas_columnas.append(col_str)
    df.columns = nuevas_columnas
    return df

# 🛠️ FUNCIÓN: Carga de Excel con detección de múltiples hojas y CONTPAQi
@st.cache_data(ttl=300, show_spinner="📂 Cargando archivo desde caché...")
@decorador_medicion_tiempo
def detectar_y_cargar_archivo(archivo_bytes, archivo_nombre):
    """
    Detecta y carga archivos Excel con soporte para múltiples hojas y formato CONTPAQi.
    
    Args:
        archivo_bytes: Contenido del archivo en bytes
        archivo_nombre: Nombre del archivo para logging
        
    Returns:
        DataFrame con datos cargados y normalizados
    """
    logger.info(f"Iniciando carga de archivo: {archivo_nombre}")
    
    try:
        xls = pd.ExcelFile(archivo_bytes)
    except Exception as e:
        logger.error(f"Error al leer Excel: {e}", exc_info=True)
        st.error(f"❌ Error al leer el archivo Excel: {e}")
        return None
        
    hojas = xls.sheet_names
    logger.debug(f"Hojas encontradas: {hojas}")

    # Caso 1: Si hay múltiples hojas → Forzar lectura de "X AGENTE"
    if len(hojas) > 1:
        if "X AGENTE" in hojas:
            hoja = "X AGENTE"
            st.info(f"📌 Archivo con múltiples hojas detectado. Leyendo hoja 'X AGENTE'.")
        else:
            st.warning("⚠️ Múltiples hojas detectadas pero no se encontró la hoja 'X AGENTE'. Selecciona manualmente.")
            hoja = st.sidebar.selectbox("📄 Selecciona la hoja a leer", hojas)
        df = pd.read_excel(xls, sheet_name=hoja)
        df = normalizar_columnas(df)

        if st.session_state.get("modo_debug"):
            with st.expander("🛠️ Debug - Columnas leídas desde X AGENTE"):
                st.write(df.columns.tolist())

        # Generación virtual de columnas año y mes para X AGENTE
        if hoja == "X AGENTE":
            if "fecha" in df.columns:
                try:
                    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
                    df["año"] = df["fecha"].dt.year
                    df["mes"] = df["fecha"].dt.month
                    st.success("✅ Columnas virtuales 'año' y 'mes' generadas correctamente desde 'fecha' en X AGENTE.")
                except Exception as e:
                    st.error(f"❌ Error al procesar la columna 'fecha' en X AGENTE: {e}")
            else:
                st.error("❌ No existe columna 'fecha' en X AGENTE para poder generar 'año' y 'mes'.")
                logger.warning("Columna 'fecha' no encontrada en X AGENTE")

    else:
        # Caso 2: Solo una hoja → Detectar si es CONTPAQi
        hoja = hojas[0]
        logger.info(f"Una sola hoja encontrada: {hoja}")
        st.info(f"✅ Solo una hoja encontrada: **{hoja}**. Procediendo con detección CONTPAQi.")
        preview = pd.read_excel(xls, sheet_name=hoja, nrows=5, header=None)
        contiene_contpaqi = preview.iloc[0, 0]
        skiprows = 3 if isinstance(contiene_contpaqi, str) and "contpaqi" in contiene_contpaqi.lower() else 0
        if skiprows:
            logger.info("Formato CONTPAQi detectado, saltando 3 filas")
            st.info("📌 Archivo CONTPAQi detectado. Saltando primeras 3 filas.")
        df = pd.read_excel(xls, sheet_name=hoja, skiprows=skiprows)
        df = normalizar_columnas(df)

    log_dataframe_info(logger, df, f"Archivo cargado: {archivo_nombre}")
    return df

# =====================================================================
# SIDEBAR: CARGA DE ARCHIVO Y FILTROS GLOBALES
# =====================================================================

st.sidebar.markdown("### 📂 Carga de Datos")

modo_debug = st.sidebar.checkbox(
    "🧪 Modo debug",
    value=False,
    help="Muestra secciones de diagnóstico (columnas detectadas, etc.)"
)
st.session_state["modo_debug"] = modo_debug

archivo = st.sidebar.file_uploader(
    "Sube archivo de ventas",
    type=["csv", "xlsx"],
    help="Formatos soportados: CSV, Excel (.xlsx). Detección automática de formato CONTPAQi"
)

if archivo:
    logger.info(f"Archivo subido: {archivo.name}, tamaño: {archivo.size / 1024:.2f} KB")
    
    with st.spinner("⏳ Procesando archivo..."):
        inicio_carga = pd.Timestamp.now()
        
        if archivo.name.endswith(".csv"):
            df = pd.read_csv(archivo)
            df = normalizar_columnas(df)
            log_dataframe_info(logger, df, "CSV cargado")
            logger.info(f"CSV cargado en {(pd.Timestamp.now() - inicio_carga).total_seconds():.2f}s")
        else:
            # Pasar bytes y nombre para que sea cacheable
            archivo_bytes = archivo.getvalue()
            df = detectar_y_cargar_archivo(archivo_bytes, archivo.name)
            logger.info(f"Excel cargado en {(pd.Timestamp.now() - inicio_carga).total_seconds():.2f}s")

        # Guardar archivo original para KPI CxC
        st.session_state["archivo_excel"] = archivo

        # Detectar y renombrar columna de año
        for col in df.columns:
            if col in ["ano", "anio", "año", "aÃ±o", "aã±o"]:
                df = df.rename(columns={col: "año"})
                break

        if "año" in df.columns:
            df["año"] = pd.to_numeric(df["año"], errors="coerce")

        for col in df.select_dtypes(include='object').columns:
            df[col] = df[col].astype(str)

        # Detectar columna de ventas (solo USD)
        columnas_ventas_usd = ["valor_usd", "ventas_usd", "ventas_usd_con_iva", "importe", "valor", "venta"]
        columna_encontrada = next((col for col in columnas_ventas_usd if col in df.columns), None)

        st.sidebar.success(f"✅ Archivo cargado: **{archivo.name}**")
        st.sidebar.info(f"📊 {len(df):,} registros | {len(df.columns)} columnas")
        
        if columna_encontrada:
            st.session_state["columna_ventas"] = columna_encontrada
        else:
            st.sidebar.warning("⚠️ No se detectó columna de ventas estándar")
            with st.sidebar.expander("🔍 Ver columnas disponibles"):
                st.write(df.columns.tolist())

        if "fecha" in df.columns:
            df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")

        # Aplicar normalización de columnas de texto
        columnas_a_normalizar = ['agente', 'vendedor', 'ejecutivo', 'linea_producto', 
                                  'linea_de_negocio', 'cliente', 'producto']
        columnas_existentes = [col for col in columnas_a_normalizar if col in df.columns]
        
        if columnas_existentes:
            df = limpiar_columnas_texto(df, columnas=columnas_existentes, usar_aliases=True)
            logger.info(f"Columnas normalizadas: {', '.join(columnas_existentes)}")
            
            # Mostrar aviso de duplicados solo en modo debug
            if modo_debug:
                duplicados_totales = 0
                for col in columnas_existentes:
                    duplicados = detectar_duplicados_similares(df[col], umbral_similitud=0.85)
                    if duplicados and len(duplicados) > 0:
                        duplicados_totales += len(duplicados)
                        with st.sidebar.expander(f"⚠️ Duplicados en '{col}' ({len(duplicados)})"):
                            for val1, val2, sim in duplicados[:3]:
                                st.write(f"- '{val1}' ≈ '{val2}'")
                            if len(duplicados) > 3:
                                st.write(f"... y {len(duplicados)-3} más")
                
                if duplicados_totales > 0:
                    st.sidebar.info("💡 Edita config/aliases.json para unificar")

        st.session_state["df"] = df
        st.session_state["archivo_path"] = archivo

        if "año" in df.columns:
            años_disponibles = sorted(df["año"].dropna().unique())
            año_base = st.sidebar.selectbox(
                "📅 Año base",
                años_disponibles,
                help="Selecciona el año principal para análisis comparativo"
            )
            st.session_state["año_base"] = año_base
        else:
            st.sidebar.warning("⚠️ No se encontró columna 'año'")

# =====================================================================
# FILTROS AVANZADOS (SPRINT 4)
# =====================================================================

if "df" in st.session_state:
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🔍 Filtros Avanzados")
    
    df_original = st.session_state["df"].copy()
    df_filtrado = df_original.copy()
    
    # Inicializar estado de filtros si no existe
    if "filtros_aplicados" not in st.session_state:
        st.session_state["filtros_aplicados"] = {}
    
    with st.sidebar.expander("📅 Filtro por Fecha", expanded=False):
        if "fecha" in df_filtrado.columns:
            df_filtrado, info_fecha = aplicar_filtro_fechas(df_filtrado, "fecha")
            if info_fecha:
                st.session_state["filtros_aplicados"]["fecha"] = info_fecha
                st.info(f"✅ {info_fecha['registros_filtrados']:,} registros en el rango")
        else:
            st.warning("⚠️ No hay columna 'fecha' disponible")
    
    with st.sidebar.expander("👤 Filtro por Cliente", expanded=False):
        if "cliente" in df_filtrado.columns:
            df_filtrado, info_cliente = aplicar_filtro_cliente(df_filtrado, "cliente")
            if info_cliente:
                st.session_state["filtros_aplicados"]["cliente"] = info_cliente
                st.info(f"✅ {info_cliente['registros_filtrados']:,} registros encontrados")
        else:
            st.warning("⚠️ No hay columna 'cliente' disponible")
    
    with st.sidebar.expander("💰 Filtro por Monto", expanded=False):
        columna_ventas = st.session_state.get("columna_ventas", None)
        if columna_ventas and columna_ventas in df_filtrado.columns:
            df_filtrado, info_monto = aplicar_filtro_monto(df_filtrado, columna_ventas)
            if info_monto:
                st.session_state["filtros_aplicados"]["monto"] = info_monto
                st.info(f"✅ {info_monto['registros_filtrados']:,} registros en el rango")
        else:
            st.warning("⚠️ No hay columna de ventas disponible")
    
    # Botón para limpiar filtros
    if st.session_state["filtros_aplicados"]:
        if st.sidebar.button("🗑️ Limpiar todos los filtros", use_container_width=True):
            st.session_state["filtros_aplicados"] = {}
            df_filtrado = df_original.copy()
            st.rerun()
    
    # Actualizar DataFrame filtrado en session_state
    if len(df_filtrado) < len(df_original):
        st.session_state["df"] = df_filtrado
        resumen = mostrar_resumen_filtros(st.session_state["filtros_aplicados"])
        with st.sidebar:
            st.success(f"✅ Filtros aplicados: {len(df_filtrado):,} de {len(df_original):,} registros")

# =====================================================================
# EXPORTACIÓN DE REPORTES (SPRINT 4)
# =====================================================================

if "df" in st.session_state and "archivo_excel" in st.session_state:
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📥 Exportar Reportes")
    
    col_excel, col_html = st.sidebar.columns(2)
    
    with col_excel:
        try:
            # Obtener datos de CxC si están disponibles
            archivo_excel = st.session_state["archivo_excel"]
            xls = pd.ExcelFile(archivo_excel)
            hoja_cxc = None
            
            for nombre_hoja in xls.sheet_names:
                if "cxc" in nombre_hoja.lower() or "cuenta" in nombre_hoja.lower():
                    hoja_cxc = nombre_hoja
                    break
            
            if hoja_cxc:
                df_cxc_raw = pd.read_excel(xls, sheet_name=hoja_cxc)
                df_cxc = normalizar_columnas(df_cxc_raw)
                
                # Generar Excel
                excel_buffer = crear_excel_metricas_cxc(df_cxc)
                st.download_button(
                    label="📊 Excel",
                    data=excel_buffer,
                    file_name="reporte_cxc.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
        except Exception as e:
            st.warning("⚠️ Excel no disponible")
            logger.error(f"Error generando Excel: {e}")
    
    with col_html:
        try:
            if hoja_cxc:
                # Generar HTML
                html_content = crear_reporte_html(df_cxc)
                st.download_button(
                    label="🌐 HTML",
                    data=html_content,
                    file_name="reporte_cxc.html",
                    mime="text/html",
                    use_container_width=True
                )
        except Exception as e:
            st.warning("⚠️ HTML no disponible")
            logger.error(f"Error generando HTML: {e}")

# =====================================================================
# NAVEGACIÓN MEJORADA CON TABS Y TOOLTIPS
# =====================================================================

st.sidebar.markdown("---")
st.sidebar.markdown("### 🧭 Navegación")

menu = st.sidebar.radio(
    "Selecciona una vista:",
    [
        "🎯 Reporte Ejecutivo",
        "📈 KPIs Generales",
        "📊 Comparativo Año vs Año",
        "🔥 Heatmap Ventas",
        "💳 KPI Cartera CxC"
    ],
    help="Selecciona el módulo de análisis que deseas visualizar"
)

# Información contextual según el menú seleccionado
st.sidebar.markdown("---")
with st.sidebar.expander("ℹ️ Acerca de esta vista"):
    if menu == "🎯 Reporte Ejecutivo":
        st.markdown("""
        **Vista consolidada para dirección ejecutiva**
        
        - KPIs financieros clave
        - Alertas críticas de negocio
        - Tendencias de ventas y CxC
        - Análisis de top performers
        - Insights estratégicos
        """)
    elif menu == "📈 KPIs Generales":
        st.markdown("""
        **Análisis general de ventas**
        
        - Total ventas y operaciones
        - Filtros por ejecutivo y línea
        - Ranking de vendedores
        - KPIs de eficiencia
        """)
    elif menu == "📊 Comparativo Año vs Año":
        st.markdown("""
        **Comparación interanual**
        
        - Evolución por mes
        - Comparación año actual vs anterior
        - Análisis de crecimiento
        """)
    elif menu == "🔥 Heatmap Ventas":
        st.markdown("""
        **Mapa de calor de ventas**
        
        - Visualización por períodos
        - Comparación secuencial o YoY
        - Análisis de tendencias
        """)
    elif menu == "💳 KPI Cartera CxC":
        st.markdown("""
        **Gestión de cuentas por cobrar**
        
        - Estado de cartera
        - Análisis de morosidad
        - Priorización de cobros
        - Eficiencia de agentes
        - Reportes y cartas de cobranza
        """)

# =====================================================================
# RENDERIZADO DE VISTAS
# =====================================================================

if menu == "🎯 Reporte Ejecutivo":
    if "df" in st.session_state and "archivo_excel" in st.session_state:
        with st.spinner("📊 Generando reporte ejecutivo..."):
            try:
                # Obtener datos de ventas
                df_ventas = st.session_state["df"]
                
                # Obtener datos de CxC
                archivo_excel = st.session_state["archivo_excel"]
                xls = pd.ExcelFile(archivo_excel)
                
                # Buscar hoja de CxC
                hoja_cxc = None
                for nombre_hoja in xls.sheet_names:
                    if "cxc" in nombre_hoja.lower() or "cuenta" in nombre_hoja.lower() or "cobrar" in nombre_hoja.lower():
                        hoja_cxc = nombre_hoja
                        break
                
                if hoja_cxc:
                    df_cxc_raw = pd.read_excel(xls, sheet_name=hoja_cxc)
                    
                    # Normalizar columnas
                    df_cxc = df_cxc_raw.copy()
                    nuevas_columnas = []
                    for col in df_cxc.columns:
                        col_str = str(col).lower().strip().replace(" ", "_")
                        col_str = unidecode(col_str)
                        nuevas_columnas.append(col_str)
                    df_cxc.columns = nuevas_columnas
                else:
                    # Si no hay hoja específica, crear DataFrame vacío
                    df_cxc = pd.DataFrame(columns=['cliente', 'saldo_adeudado', 'dias_vencido'])
                
                reporte_ejecutivo.mostrar_reporte_ejecutivo(df_ventas, df_cxc)
            except Exception as e:
                st.error(f"❌ Error al generar el reporte ejecutivo: {str(e)}")
                st.info("💡 Asegúrate de haber subido un archivo con datos de ventas y CxC")
    else:
        st.warning("⚠️ Primero sube un archivo para visualizar el Reporte Ejecutivo.")
        st.info("📂 Usa el menú lateral para cargar tu archivo de datos.")

elif menu == "📈 KPIs Generales":
    main_kpi.run()

elif menu == "📊 Comparativo Año vs Año":
    if "df" in st.session_state:
        año_base = st.session_state.get("año_base", None)
        main_comparativo.run(st.session_state["df"], año_base=año_base)
    else:
        st.warning("⚠️ Primero sube un archivo para visualizar el comparativo año vs año.")

elif menu == "🔥 Heatmap Ventas":
    if "df" in st.session_state:
        heatmap_ventas.run(st.session_state["df"])
    else:
        st.warning("⚠️ Primero sube un archivo para visualizar el Heatmap.")

elif menu == "💳 KPI Cartera CxC":
    if "archivo_excel" in st.session_state:
        kpi_cpc.run(st.session_state["archivo_excel"])
    else:
        st.warning("⚠️ Primero sube un archivo para visualizar CXC.")
