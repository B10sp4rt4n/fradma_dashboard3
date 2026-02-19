import streamlit as st
import pandas as pd
import os
from dotenv import load_dotenv
from unidecode import unidecode

# Cargar variables de entorno desde .env (si existe)
load_dotenv()
from main import main_kpi, main_comparativo, heatmap_ventas
from main import kpi_cpc, reporte_ejecutivo, ytd_lineas, reporte_consolidado
from main import vendedores_cxc
from utils.data_cleaner import limpiar_columnas_texto, detectar_duplicados_similares
from utils.data_normalizer import normalizar_columnas
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
gestor_cache = GestorCache()  # TTL se especifica en cada llamada a obtener_o_calcular()

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

# 🛠️ FUNCIÓN: Obtener hojas disponibles de un Excel
def obtener_hojas_excel(archivo_bytes):
    """Obtiene la lista de hojas de un archivo Excel."""
    try:
        xls = pd.ExcelFile(archivo_bytes)
        return xls.sheet_names
    except FileNotFoundError:
        logger.error("Archivo Excel no encontrado")
        return []
    except pd.errors.EmptyDataError:
        logger.error("El archivo Excel está vacío")
        return []
    except ValueError as e:
        logger.error(f"Formato de Excel inválido: {e}")
        return []
    except Exception as e:
        logger.exception(f"Error inesperado al leer Excel: {e}")
        return []

# 🛠️ FUNCIÓN: Carga de Excel con detección de múltiples hojas y CONTPAQi (SIN WIDGETS)
@st.cache_data(ttl=300, show_spinner="📂 Cargando archivo desde caché...")
@decorador_medicion_tiempo
def cargar_excel_puro(archivo_bytes, archivo_nombre, hoja_seleccionada=None):
    """
    Carga archivos Excel sin widgets de UI (versión cacheable).
    
    Args:
        archivo_bytes: Contenido del archivo en bytes
        archivo_nombre: Nombre del archivo para logging
        hoja_seleccionada: Hoja específica a leer (opcional)
        
    Returns:
        Tupla (DataFrame, dict con metadata) o (None, dict con error)
    """
    logger.info(f"Iniciando carga de archivo: {archivo_nombre}")
    metadata = {"error": None, "hoja_leida": None, "es_contpaqi": False, "es_x_agente": False}
    
    try:
        xls = pd.ExcelFile(archivo_bytes)
    except pd.errors.EmptyDataError:
        logger.error("Archivo Excel vacío")
        metadata["error"] = "empty"
        return None, metadata
    except ValueError as e:
        logger.error(f"Formato Excel inválido: {e}")
        metadata["error"] = "invalid_format"
        return None, metadata
    except PermissionError:
        logger.error("Sin permisos para leer el archivo")
        metadata["error"] = "permission"
        return None, metadata
    except Exception as e:
        logger.exception(f"Error inesperado al leer Excel: {e}")
        metadata["error"] = f"unexpected: {str(e)}"
        return None, metadata
        
    hojas = xls.sheet_names
    logger.debug(f"Hojas encontradas: {hojas}")

    # Caso 1: Si hay múltiples hojas → Forzar lectura de "X AGENTE" o usar la seleccionada
    if len(hojas) > 1:
        if hoja_seleccionada:
            hoja = hoja_seleccionada
        elif "X AGENTE" in hojas:
            hoja = "X AGENTE"
            metadata["es_x_agente"] = True
        else:
            # Si no se especificó hoja y no existe X AGENTE, usar la primera
            hoja = hojas[0]
        
        metadata["hoja_leida"] = hoja
        df = pd.read_excel(xls, sheet_name=hoja)
        df = normalizar_columnas(df)

        # Generación virtual de columnas año y mes para X AGENTE
        if hoja == "X AGENTE":
            metadata["es_x_agente"] = True
            if "fecha" in df.columns:
                try:
                    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
                    df["año"] = df["fecha"].dt.year
                    df["mes"] = df["fecha"].dt.month
                    metadata["fecha_procesada"] = True
                except Exception as e:
                    logger.exception(f"Error al procesar fecha: {e}")
                    metadata["fecha_error"] = str(e)
            else:
                logger.warning("Columna 'fecha' no encontrada en X AGENTE")
                metadata["fecha_no_encontrada"] = True

    else:
        # Caso 2: Solo una hoja → Detectar si es CONTPAQi
        hoja = hojas[0]
        logger.info(f"Una sola hoja encontrada: {hoja}")
        metadata["hoja_leida"] = hoja
        metadata["unica_hoja"] = True
        
        preview = pd.read_excel(xls, sheet_name=hoja, nrows=5, header=None)
        contiene_contpaqi = preview.iloc[0, 0]
        skiprows = 3 if isinstance(contiene_contpaqi, str) and "contpaqi" in contiene_contpaqi.lower() else 0
        
        if skiprows:
            logger.info("Formato CONTPAQi detectado, saltando 3 filas")
            metadata["es_contpaqi"] = True
            
        df = pd.read_excel(xls, sheet_name=hoja, skiprows=skiprows)
        df = normalizar_columnas(df)

    log_dataframe_info(logger, df, f"Archivo cargado: {archivo_nombre}")
    return df, metadata


def detectar_y_cargar_archivo(archivo_bytes, archivo_nombre, hoja_seleccionada=None):
    """
    Wrapper con UI para cargar_excel_puro.
    Muestra mensajes y widgets basados en la metadata.
    """
    df, metadata = cargar_excel_puro(archivo_bytes, archivo_nombre, hoja_seleccionada)
    
    # Manejar errores
    if metadata.get("error"):
        if metadata["error"] == "empty":
            st.error("❌ El archivo Excel está vacío. Por favor, verifica que contenga datos.")
        elif metadata["error"] == "invalid_format":
            st.error("❌ Formato de Excel no válido. Asegúrate de usar .xlsx o .xls")
        elif metadata["error"] == "permission":
            st.error("❌ No se tienen permisos para leer el archivo. Verifica los permisos.")
        else:
            st.error(f"❌ Error al leer el archivo Excel: {metadata['error']}")
        return None
    
    # Mostrar mensajes informativos
    if metadata.get("es_x_agente"):
        st.info("📌 Archivo con múltiples hojas detectado. Leyendo hoja 'X AGENTE'.")
        if metadata.get("fecha_procesada"):
            st.success("✅ Columnas virtuales 'año' y 'mes' generadas correctamente desde 'fecha' en X AGENTE.")
        elif metadata.get("fecha_no_encontrada"):
            st.error("❌ No existe columna 'fecha' en X AGENTE para poder generar 'año' y 'mes'.")
        elif metadata.get("fecha_error"):
            st.error(f"❌ Error al procesar la columna 'fecha' en X AGENTE: {metadata['fecha_error']}")
    elif metadata.get("unica_hoja"):
        st.info(f"✅ Solo una hoja encontrada: **{metadata['hoja_leida']}**. Procediendo con detección CONTPAQi.")
        if metadata.get("es_contpaqi"):
            st.info("📌 Archivo CONTPAQi detectado. Saltando primeras 3 filas.")
    elif hoja_seleccionada:
        st.info(f"📌 Leyendo hoja seleccionada: {metadata['hoja_leida']}")
    
    # Mostrar debug si está activado
    if st.session_state.get("modo_debug") and df is not None:
        with st.expander("🛠️ Debug - Columnas leídas"):
            st.write(df.columns.tolist())
    
    return df

# =====================================================================
# FUNCIÓN: VALIDAR COLUMNAS REQUERIDAS
# =====================================================================

def validar_columnas_requeridas(df):
    """
    Valida columnas del DataFrame contra las requeridas por cada módulo.
    Retorna un diccionario con el checklist de validación.
    NO MODIFICA el DataFrame ni rompe la lógica existente.
    """
    columnas_df = set(df.columns)
    
    # Definición de columnas por módulo (según código actual)
    modulos = {
        "YTD por Líneas": {
            "obligatorias": ["fecha", "linea_de_negocio"],
            "variantes_obligatorias": {
                "ventas_usd": ["ventas_usd", "ventas_usd_con_iva", "ventas_usd_sin_iva", "importe", "valor_usd", "monto_usd", "total_usd", "valor", "venta"]
            },
            "recomendadas": ["vendedor", "agente", "ejecutivo", "cliente"],
            "opcionales": ["producto"]
        },
        "Dashboard CxC": {
            "obligatorias": ["cliente", "fecha"],
            "variantes_obligatorias": {
                "saldo_adeudado": ["saldo_adeudado", "saldo", "saldo_adeudo", "adeudo", "importe", "monto", "total", "saldo_usd"]
            },
            "recomendadas": ["factura", "dias_de_credito", "estatus", "vendedor"],
            "opcionales": ["linea_de_negocio", "dias_restantes", "dias_vencido", "fecha_de_pago"]
        },
        "KPIs Generales": {
            "obligatorias": ["fecha"],
            "variantes_obligatorias": {
                "valor_usd": ["valor_usd", "ventas_usd", "ventas_usd_con_iva", "importe"]
            },
            "recomendadas": ["agente", "vendedor", "ejecutivo"],
            "opcionales": ["linea_producto", "linea_de_negocio"]
        },
        "Reporte Ejecutivo": {
            "obligatorias": ["fecha"],
            "variantes_obligatorias": {
                "valor_usd": ["valor_usd", "ventas_usd", "ventas_usd_con_iva"],
                "saldo_adeudado": ["saldo_adeudado", "saldo", "adeudo"]
            },
            "recomendadas": ["cliente"],
            "opcionales": ["vendedor", "dias_vencido"]
        }
    }
    
    resultados = {}
    
    for modulo, cols in modulos.items():
        checklist = []
        
        # Validar obligatorias
        for col in cols.get("obligatorias", []):
            if col in columnas_df:
                checklist.append({"col": col, "status": "✅", "tipo": "Obligatoria", "mensaje": "Encontrada"})
            else:
                checklist.append({"col": col, "status": "❌", "tipo": "Obligatoria", "mensaje": "NO ENCONTRADA - El módulo puede fallar"})
        
        # Validar obligatorias con variantes
        for col_principal, variantes in cols.get("variantes_obligatorias", {}).items():
            encontrada = next((v for v in variantes if v in columnas_df), None)
            if encontrada:
                if encontrada == col_principal:
                    checklist.append({"col": col_principal, "status": "✅", "tipo": "Obligatoria", "mensaje": "Encontrada"})
                else:
                    checklist.append({"col": col_principal, "status": "⚠️", "tipo": "Obligatoria", "mensaje": f"Encontrada como '{encontrada}'"})
            else:
                checklist.append({"col": col_principal, "status": "❌", "tipo": "Obligatoria", "mensaje": f"NO ENCONTRADA - Buscar: {', '.join(variantes[:3])}"})
        
        # Validar recomendadas
        for col in cols.get("recomendadas", []):
            if col in columnas_df:
                checklist.append({"col": col, "status": "✅", "tipo": "Recomendada", "mensaje": "Encontrada"})
            else:
                # No mostrar recomendadas faltantes para no saturar
                pass
        
        # Validar opcionales encontradas (no mostrar las que faltan)
        for col in cols.get("opcionales", []):
            if col in columnas_df:
                checklist.append({"col": col, "status": "✅", "tipo": "Opcional", "mensaje": "Disponible"})
        
        resultados[modulo] = checklist
    
    return resultados

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
            
            # Obtener hojas disponibles (sin caché)
            hojas = obtener_hojas_excel(archivo_bytes)
            
            # Si hay múltiples hojas y no existe X AGENTE, permitir selección
            hoja_seleccionada = None
            if len(hojas) > 1 and "X AGENTE" not in hojas:
                st.warning("⚠️ Múltiples hojas detectadas. Selecciona la hoja a leer:")
                hoja_seleccionada = st.sidebar.selectbox("📄 Selecciona la hoja a leer", hojas)
            
            df = detectar_y_cargar_archivo(archivo_bytes, archivo.name, hoja_seleccionada)
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
        
        # ================================================================
        # CHECKLIST DE VALIDACIÓN DE COLUMNAS
        # ================================================================
        validacion = validar_columnas_requeridas(df)
        
        # Contar problemas
        total_errores = sum(1 for modulo in validacion.values() for item in modulo if item["status"] == "❌")
        total_advertencias = sum(1 for modulo in validacion.values() for item in modulo if item["status"] == "⚠️")
        
        # Mostrar resumen en sidebar
        if total_errores > 0:
            st.sidebar.error(f"🚨 {total_errores} columna(s) crítica(s) faltante(s)")
        elif total_advertencias > 0:
            st.sidebar.warning(f"⚠️ {total_advertencias} columna(s) con variantes detectadas")
        else:
            st.sidebar.success("✅ Todas las columnas críticas encontradas")
        
        # Panel expandible con detalle de validación
        with st.sidebar.expander("📋 Validación de Columnas Requeridas"):
            st.markdown("**Referencia:** Ver [docs/COLUMNAS_REQUERIDAS.md](docs/COLUMNAS_REQUERIDAS.md)")
            st.markdown("---")
            
            for modulo, checklist in validacion.items():
                if not checklist:  # Saltar si está vacío
                    continue
                
                # Contar por tipo de status en este módulo
                errores_modulo = sum(1 for item in checklist if item["status"] == "❌")
                advertencias_modulo = sum(1 for item in checklist if item["status"] == "⚠️")
                ok_modulo = sum(1 for item in checklist if item["status"] == "✅")
                
                # Color del header según problemas
                if errores_modulo > 0:
                    st.markdown(f"### 🔴 {modulo}")
                elif advertencias_modulo > 0:
                    st.markdown(f"### 🟡 {modulo}")
                else:
                    st.markdown(f"### 🟢 {modulo}")
                
                st.caption(f"✅ {ok_modulo} | ⚠️ {advertencias_modulo} | ❌ {errores_modulo}")
                
                # Mostrar solo problemas o todo si en modo debug
                items_a_mostrar = checklist if modo_debug else [item for item in checklist if item["status"] != "✅"]
                
                if items_a_mostrar:
                    for item in items_a_mostrar:
                        st.markdown(f"{item['status']} **{item['col']}** ({item['tipo']}): {item['mensaje']}")
                elif not modo_debug:
                    st.success("Todas las columnas críticas presentes")
                
                st.markdown("---")
            
            # Link a documentación
            st.info("💡 **Tip:** Consulta la guía completa en `docs/COLUMNAS_REQUERIDAS.md` para mapear desde CRMs/ERPs")

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
    
    # Inicializar estado de filtros si no existe
    if "filtros_aplicados" not in st.session_state:
        st.session_state["filtros_aplicados"] = {}
    
    # Inicializar botón de reset
    if "reset_filtros" not in st.session_state:
        st.session_state["reset_filtros"] = False
    
    # Opción para activar/desactivar filtros
    usar_filtros = st.sidebar.checkbox(
        "Activar filtros avanzados",
        value=st.session_state.get("reset_filtros", False) == False,
        help="Activa esta opción para aplicar filtros por fecha y/o cliente"
    )
    
    if usar_filtros:
        df_filtrado = df_original.copy()
        
        # Filtro por Fecha (sin expander)
        st.sidebar.markdown("#### 📅 Filtro por Fecha")
        if "fecha" in df_filtrado.columns:
            df_filtrado = aplicar_filtro_fechas(df_filtrado, "fecha")
        else:
            st.sidebar.warning("⚠️ No hay columna 'fecha' disponible")
        
        st.sidebar.markdown("---")
        
        # Filtro por Cliente (sin expander)
        st.sidebar.markdown("#### 👤 Filtro por Cliente")
        if "cliente" in df_filtrado.columns:
            df_filtrado = aplicar_filtro_cliente(df_filtrado, "cliente")
        else:
            st.sidebar.warning("⚠️ No hay columna 'cliente' disponible")
        
        st.sidebar.markdown("---")
        
        # Filtro por Monto
        columna_ventas = st.session_state.get("columna_ventas", None)
        if columna_ventas and columna_ventas in df_filtrado.columns:
            df_filtrado = aplicar_filtro_monto(df_filtrado, columna_ventas)
        else:
            st.sidebar.warning("⚠️ No hay columna de ventas disponible")
        
        # Botón para limpiar filtros
        st.sidebar.markdown("---")
        if st.sidebar.button("🗑️ Limpiar todos los filtros", use_container_width=True):
            st.session_state["filtros_aplicados"] = {}
            st.session_state["reset_filtros"] = True
            # Limpiar las keys de los widgets de filtro
            for key in list(st.session_state.keys()):
                if key.startswith("filtro_"):
                    del st.session_state[key]
            st.rerun()
        
        # Actualizar DataFrame filtrado en session_state
        st.session_state["df"] = df_filtrado
        st.session_state["reset_filtros"] = False
        
        # Mostrar resumen de filtros aplicados
        if len(df_filtrado) < len(df_original):
            st.sidebar.success(f"✅ Filtros aplicados: {len(df_filtrado):,} de {len(df_original):,} registros")
            mostrar_resumen_filtros(df_original, df_filtrado)
    else:
        # Si no se activan filtros, usar DataFrame original
        pass

# =====================================================================
# EXPORTACIÓN DE REPORTES (SPRINT 4)
# =====================================================================

if "df" in st.session_state and "archivo_excel" in st.session_state:
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📥 Exportar Reportes")
    
    # Intentar obtener datos de CxC primero
    df_cxc = None
    df_cxc_procesado = None
    metricas = None
    
    try:
        archivo_excel = st.session_state["archivo_excel"]
        
        # Leer todas las hojas disponibles directamente desde el archivo
        hojas_disponibles = pd.ExcelFile(archivo_excel).sheet_names
        hoja_cxc = None
        
        for nombre_hoja in hojas_disponibles:
            if "cxc" in nombre_hoja.lower() or "cuenta" in nombre_hoja.lower():
                hoja_cxc = nombre_hoja
                break
        
        if hoja_cxc:
            # Leer la hoja de CxC directamente
            df_cxc_raw = pd.read_excel(archivo_excel, sheet_name=hoja_cxc)
            df_cxc = normalizar_columnas(df_cxc_raw)
            
            # Asegurar que existe la columna saldo_adeudado
            if "saldo_adeudado" not in df_cxc.columns:
                for candidato in ["saldo", "saldo_adeudo", "adeudo", "importe", "monto", "total", "saldo_usd"]:
                    if candidato in df_cxc.columns:
                        df_cxc = df_cxc.rename(columns={candidato: "saldo_adeudado"})
                        break
            
            # Limpiar y convertir columna de saldo
            if "saldo_adeudado" in df_cxc.columns:
                saldo_txt = df_cxc["saldo_adeudado"].astype(str)
                saldo_txt = saldo_txt.str.replace(",", "", regex=False)
                saldo_txt = saldo_txt.str.replace("$", "", regex=False)
                df_cxc["saldo_adeudado"] = pd.to_numeric(saldo_txt, errors="coerce").fillna(0)
            else:
                df_cxc["saldo_adeudado"] = 0
            
            # DEBUG: Ver columnas y valores de dias
            logger.info(f"=== DEBUG CxC COLUMNAS ===")
            logger.info(f"Columnas disponibles: {list(df_cxc.columns)}")
            if 'dias_restante' in df_cxc.columns:
                logger.info(f"dias_restante - min: {df_cxc['dias_restante'].min()}, max: {df_cxc['dias_restante'].max()}, muestra: {df_cxc['dias_restante'].head(5).tolist()}")
            if 'dias_restantes' in df_cxc.columns:
                logger.info(f"dias_restantes - min: {df_cxc['dias_restantes'].min()}, max: {df_cxc['dias_restantes'].max()}, muestra: {df_cxc['dias_restantes'].head(5).tolist()}")
            if 'dias_vencido' in df_cxc.columns:
                logger.info(f"dias_vencido - min: {df_cxc['dias_vencido'].min()}, max: {df_cxc['dias_vencido'].max()}, muestra: {df_cxc['dias_vencido'].head(5).tolist()}")
            
            # Preparar métricas básicas para exportación
            from utils.cxc_helper import calcular_metricas_basicas, preparar_datos_cxc
            
            # preparar_datos_cxc retorna una tupla: (df_prep, df_no_pagados, mask_pagado)
            df_prep, df_cxc_procesado, _ = preparar_datos_cxc(df_cxc)
            
            # DEBUG: Ver dias_overdue calculado
            logger.info(f"dias_overdue calculado - min: {df_cxc_procesado['dias_overdue'].min()}, max: {df_cxc_procesado['dias_overdue'].max()}")
            logger.info(f"Registros vigentes (dias_overdue <= 0): {(df_cxc_procesado['dias_overdue'] <= 0).sum()}")
            logger.info(f"Registros vencidos (dias_overdue > 0): {(df_cxc_procesado['dias_overdue'] > 0).sum()}")
            
            metricas = calcular_metricas_basicas(df_cxc_procesado)
            
    except KeyError as e:
        logger.error(f"Columna requerida no encontrada en CxC: {e}")
        df_cxc = None
        df_cxc_procesado = None
        metricas = None
    except ValueError as e:
        logger.error(f"Valor inválido en datos CxC: {e}")
        df_cxc = None
        df_cxc_procesado = None
        metricas = None
    except Exception as e:
        logger.exception(f"Error inesperado cargando datos CxC para exportación: {e}")
        df_cxc = None
        df_cxc_procesado = None
        metricas = None
    
    # Excel (arriba)
    if df_cxc_procesado is not None and metricas is not None:
        try:
            # Generar Excel con métricas completas
            excel_buffer = crear_excel_metricas_cxc(metricas, df_cxc_procesado)
            st.sidebar.download_button(
                label="📊 Excel",
                data=excel_buffer,
                file_name="reporte_cxc.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        except ImportError:
            st.sidebar.warning("⚠️ Librería xlsxwriter no disponible. Instala con: pip install xlsxwriter")
            logger.error("Falta dependencia xlsxwriter")
        except MemoryError:
            st.sidebar.warning("⚠️ Datos demasiado grandes para generar Excel")
            logger.error("Memoria insuficiente para generar Excel")
        except Exception as e:
            st.sidebar.warning(f"⚠️ Excel no disponible: {str(e)}")
            logger.exception(f"Error generando Excel: {e}")
    else:
        st.sidebar.caption("⚠️ Sin datos CxC")
    
    # HTML (abajo)
    if df_cxc_procesado is not None and metricas is not None:
        # Inicializar lista de secciones
        secciones_seleccionadas = []
        
        # Configuración de secciones del reporte HTML
        with st.sidebar.expander("⚙️ Configurar Reporte HTML", expanded=False):
            st.caption("Selecciona las secciones a incluir:")
            
            incluir_resumen = st.checkbox("📈 Resumen Ejecutivo", value=True, 
                                          help="KPIs consolidados (Ventas + CxC)")
            incluir_ventas = st.checkbox("💼 Ventas Detalladas", value=True,
                                        help="Métricas de desempeño de ventas")
            incluir_cxc = st.checkbox("🏦 CxC Detallada", value=True,
                                     help="Desglose de cuentas por cobrar")
            incluir_antiguedad = st.checkbox("📅 Tabla Antigüedad", value=False,
                                            help="Distribución detallada por rangos")
            incluir_score = st.checkbox("🎯 Score de Salud", value=True,
                                       help="Puntuación de salud financiera")
            incluir_top = st.checkbox("👥 Top 5 Deudores", value=False,
                                     help="Clientes con mayor adeudo")
            
            # Construir lista de secciones
            if incluir_resumen:
                secciones_seleccionadas.append('resumen_ejecutivo')
            if incluir_ventas:
                secciones_seleccionadas.append('ventas')
            if incluir_cxc:
                secciones_seleccionadas.append('cxc')
            if incluir_antiguedad:
                secciones_seleccionadas.append('antiguedad')
            if incluir_score:
                secciones_seleccionadas.append('score')
            if incluir_top:
                secciones_seleccionadas.append('top_clientes')
            
            if secciones_seleccionadas:
                st.caption(f"✅ {len(secciones_seleccionadas)} sección(es) seleccionada(s)")
            else:
                st.warning("⚠️ Selecciona al menos una sección")
        
        try:
            # Obtener df_ventas si está disponible
            df_ventas_export = None
            if "df" in st.session_state:
                df_ventas_export = st.session_state["df"]
            
            # Generar HTML con configuración personalizada
            if secciones_seleccionadas:
                html_content = crear_reporte_html(
                    metricas, 
                    df_cxc_procesado,
                    df_ventas=df_ventas_export,
                    secciones=secciones_seleccionadas
                )
                
                st.sidebar.download_button(
                    label="🌐 Descargar HTML",
                    data=html_content,
                    file_name="reporte_ejecutivo.html",
                    mime="text/html",
                    use_container_width=True,
                    help="Reporte ejecutivo configurable en formato HTML"
                )
            else:
                st.sidebar.button(
                    "🌐 Descargar HTML",
                    disabled=True,
                    use_container_width=True,
                    help="Selecciona al menos una sección"
                )
        except KeyError as e:
            st.sidebar.warning(f"⚠️ Falta columna requerida para HTML: {e}")
            logger.error(f"Columna faltante en reporte HTML: {e}")
        except MemoryError:
            st.sidebar.warning("⚠️ Datos demasiado grandes para generar HTML")
            logger.error("Memoria insuficiente para generar HTML")
        except Exception as e:
            st.sidebar.warning(f"⚠️ HTML no disponible: {str(e)}")
            logger.exception(f"Error generando HTML: {e}")
    else:
        st.sidebar.caption("⚠️ Sin datos CxC")

# =====================================================================
# NAVEGACIÓN MEJORADA CON TABS Y TOOLTIPS
# =====================================================================

# =====================================================================
# SISTEMA DE PASSKEY PREMIUM - ANÁLISIS CON IA
# =====================================================================

st.sidebar.markdown("---")
st.sidebar.markdown("### 🤖 Análisis Premium con IA")

# Inicializar estado de IA en session_state
if "ia_premium_activada" not in st.session_state:
    st.session_state["ia_premium_activada"] = False
if "openai_api_key" not in st.session_state:
    st.session_state["openai_api_key"] = None
if "passkey_valido" not in st.session_state:
    st.session_state["passkey_valido"] = False

# Passkey desde variable de entorno con fallback a valor por defecto (desarrollo)
# PRODUCCIÓN: Definir PASSKEY_PREMIUM en .env o variable de entorno del servidor
PASSKEY_PREMIUM = os.getenv("PASSKEY_PREMIUM", "fradma2026")

# Widget para ingresar passkey
passkey_input = st.sidebar.text_input(
    "🔑 Passkey Premium",
    type="password",
    placeholder="Ingresa tu passkey",
    help="Activa funciones premium de análisis con IA"
)

if passkey_input == PASSKEY_PREMIUM:
    if not st.session_state["passkey_valido"]:
        st.session_state["passkey_valido"] = True
        st.sidebar.success("✅ Passkey válido!")
    
    # Solicitar API key de OpenAI
    st.sidebar.markdown("**Configuración de IA**")
    
    # Intentar obtener la API key de variable de entorno primero
    api_key_env = os.getenv("OPENAI_API_KEY", "")
    
    if api_key_env:
        st.session_state["openai_api_key"] = api_key_env
        st.sidebar.success("🔑 API key detectada desde variable de entorno")
        st.session_state["ia_premium_activada"] = True
    else:
        openai_api_key = st.sidebar.text_input(
            "OpenAI API Key",
            type="password",
            placeholder="sk-...",
            help="Ingresa tu API key de OpenAI para habilitar análisis con IA"
        )
        
        if openai_api_key:
            # Validar la API key
            from utils.ai_helper import validar_api_key
            
            if validar_api_key(openai_api_key):
                st.session_state["openai_api_key"] = openai_api_key
                st.session_state["ia_premium_activada"] = True
                st.sidebar.success("✅ API key válida")
            else:
                st.sidebar.error("❌ API key inválida")
                st.session_state["ia_premium_activada"] = False
        else:
            st.session_state["ia_premium_activada"] = False
    
    if st.session_state["ia_premium_activada"]:
        st.sidebar.markdown("**Configuración de Análisis**")
        
        # Control: Solo analizar cuando se presione el botón
        with st.sidebar.expander("⚙️ Filtros de Análisis", expanded=False):
            st.caption("Define qué datos analizar con IA:")
            
            # Filtro de periodo
            analisis_periodo = st.selectbox(
                "📅 Periodo a analizar",
                ["Todos los datos", "Año actual", "Último trimestre", "Último mes", "Personalizado"],
                help="Selecciona el rango temporal del análisis"
            )
            
            if analisis_periodo == "Personalizado" and "df" in st.session_state:
                df_temp = st.session_state["df"]
                if "fecha" in df_temp.columns:
                    fecha_desde = st.date_input("Desde", value=df_temp["fecha"].min())
                    fecha_hasta = st.date_input("Hasta", value=df_temp["fecha"].max())
                    st.session_state["analisis_fecha_desde"] = fecha_desde
                    st.session_state["analisis_fecha_hasta"] = fecha_hasta
            
            # Filtro de productos/líneas
            if "df" in st.session_state:
                df_temp = st.session_state["df"]
                if "linea_de_negocio" in df_temp.columns:
                    lineas_disponibles = df_temp["linea_de_negocio"].dropna().unique().tolist()
                    analisis_lineas = st.multiselect(
                        "📦 Líneas de negocio",
                        options=["Todas"] + lineas_disponibles,
                        default=["Todas"],
                        help="Selecciona líneas específicas o todas"
                    )
                    st.session_state["analisis_lineas"] = analisis_lineas
                
                # Filtro de clientes
                if "cliente" in df_temp.columns:
                    top_clientes = df_temp.groupby("cliente")["valor_usd"].sum().nlargest(20).index.tolist() if "valor_usd" in df_temp.columns else []
                    if top_clientes:
                        analisis_clientes = st.multiselect(
                            "👥 Clientes (Top 20)",
                            options=["Todos"] + top_clientes,
                            default=["Todos"],
                            help="Selecciona clientes específicos o todos"
                        )
                        st.session_state["analisis_clientes"] = analisis_clientes
        
        # Guardar configuración en session_state
        st.session_state["analisis_periodo"] = analisis_periodo
        
        st.sidebar.info("💡 Análisis con IA: Presiona el botón en cada módulo para ejecutar")
    
else:
    st.session_state["passkey_valido"] = False
    st.session_state["ia_premium_activada"] = False
    st.session_state["openai_api_key"] = None
    
    if passkey_input:
        st.sidebar.error("❌ Passkey incorrecto")
    else:
        st.sidebar.caption("🔐 Ingresa el passkey para acceder a funciones premium")

st.sidebar.markdown("---")
st.sidebar.markdown("### 🧭 Navegación")

menu = st.sidebar.radio(
    "Selecciona una vista:",
    [
        "🎯 Reporte Ejecutivo",
        "📊 Reporte Consolidado",
        "📈 KPIs Generales",
        "📊 Comparativo Año vs Año",
        "📉 YTD por Línea de Negocio",
        "🔥 Heatmap Ventas",
        "💳 KPI Cartera CxC",
        "👥 Vendedores + CxC"
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
    elif menu == "📊 Reporte Consolidado":
        st.markdown("""
        **Dashboard ejecutivo integral**
        
        - Ventas por período (semanal/mensual/trimestral/anual)
        - Estado de cuentas por cobrar
        - Gráficos ejecutivos consolidados
        - Análisis con IA del estado del negocio
        - Métricas de desempeño integral
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
        - Análisis de crecimiento
        - Tendencias históricas
        """)
    elif menu == "📉 YTD por Línea de Negocio":
        st.markdown("""
        **Reporte Year-to-Date (YTD)**
        
        - Ventas acumuladas del año
        - Comparativa vs año anterior
        - Análisis por línea de negocio
        - Top productos y clientes
        - Proyección anual
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
    elif menu == "👥 Vendedores + CxC":
        st.markdown("""
        **Cruce ventas × cartera por vendedor**

        - Ratio deuda vencida / ventas
        - Score de calidad de cartera
        - Ranking mixto volumen + calidad
        - Alertas automáticas por vendedor
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
                
                # Pasar parámetros de IA premium al módulo
                ia_habilitada = st.session_state.get("ia_premium_activada", False)
                api_key = st.session_state.get("openai_api_key", None)
                reporte_ejecutivo.mostrar_reporte_ejecutivo(df_ventas, df_cxc, habilitar_ia=ia_habilitada, openai_api_key=api_key)
            except KeyError as e:
                st.error(f"❌ Columna requerida no encontrada: {e}")
                st.info("💡 Verifica que el archivo contenga las columnas: fecha, ventas, cliente, saldo")
                logger.error(f"Columna faltante en reporte ejecutivo: {e}")
            except ValueError as e:
                st.error(f"❌ Error en los valores de datos: {e}")
                st.info("💡 Revisa que los montos y fechas tengan formato válido")
                logger.error(f"Valor inválido en reporte ejecutivo: {e}")
            except Exception as e:
                st.error(f"❌ Error al generar el reporte ejecutivo: {str(e)}")
                st.info("💡 Asegúrate de haber subido un archivo con datos de ventas y CxC")
                logger.exception(f"Error inesperado en reporte ejecutivo: {e}")
    else:
        st.warning("⚠️ Primero sube un archivo para visualizar el Reporte Ejecutivo.")
        st.info("📂 Usa el menú lateral para cargar tu archivo de datos.")

elif menu == "📈 KPIs Generales":
    # Pasar parámetros de IA premium al módulo
    ia_habilitada = st.session_state.get("ia_premium_activada", False)
    api_key = st.session_state.get("openai_api_key", None)
    main_kpi.run(habilitar_ia=ia_habilitada, openai_api_key=api_key)

elif menu == "📊 Comparativo Año vs Año":
    if "df" in st.session_state:
        año_base = st.session_state.get("año_base", None)
        main_comparativo.run(st.session_state["df"], año_base=año_base)
    else:
        st.warning("⚠️ Primero sube un archivo para visualizar el comparativo año vs año.")

elif menu == "📉 YTD por Línea de Negocio":
    if "df" in st.session_state:
        # Pasar parámetros de IA premium al módulo
        ia_habilitada = st.session_state.get("ia_premium_activada", False)
        api_key = st.session_state.get("openai_api_key", None)
        ytd_lineas.run(st.session_state["df"], habilitar_ia=ia_habilitada, openai_api_key=api_key)
    else:
        st.warning("⚠️ Primero sube un archivo para visualizar el reporte YTD.")
        st.info("📂 Este reporte requiere datos de ventas con: fecha, linea_de_negocio, ventas_usd")

elif menu == "🔥 Heatmap Ventas":
    if "df" in st.session_state:
        heatmap_ventas.run(st.session_state["df"])
    else:
        st.warning("⚠️ Primero sube un archivo para visualizar el Heatmap.")

elif menu == "💳 KPI Cartera CxC":
    if "archivo_excel" in st.session_state:
        # Pasar parámetros de IA premium al módulo
        ia_habilitada = st.session_state.get("ia_premium_activada", False)
        api_key = st.session_state.get("openai_api_key", None)
        kpi_cpc.run(st.session_state["archivo_excel"], habilitar_ia=ia_habilitada, openai_api_key=api_key)
    else:
        st.warning("⚠️ Primero sube un archivo para visualizar CXC.")

elif menu == "👥 Vendedores + CxC":
    vendedores_cxc.run()

elif menu == "📊 Reporte Consolidado":
    if "df" in st.session_state and "archivo_excel" in st.session_state:
        with st.spinner("📊 Generando reporte consolidado..."):
            try:
                # Obtener datos de ventas (igual que Reporte Ejecutivo)
                df_ventas = st.session_state["df"]
                
                # Obtener datos de CxC (misma lógica que Reporte Ejecutivo)
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
                    df_cxc = pd.DataFrame()
                
                # Pasar parámetros de IA premium al módulo
                ia_habilitada = st.session_state.get("ia_premium_activada", False)
                api_key = st.session_state.get("openai_api_key", None)
                reporte_consolidado.run(df_ventas, df_cxc, habilitar_ia=ia_habilitada, openai_api_key=api_key)
            except Exception as e:
                st.error(f"❌ Error al generar el reporte consolidado: {str(e)}")
                logger.exception(f"Error en reporte consolidado: {e}")
    elif "df" in st.session_state:
        # Pasar parámetros de IA premium al módulo
        ia_habilitada = st.session_state.get("ia_premium_activada", False)
        api_key = st.session_state.get("openai_api_key", None)
        reporte_consolidado.run(st.session_state["df"], None, habilitar_ia=ia_habilitada, openai_api_key=api_key)
    else:
        st.warning("⚠️ Primero sube un archivo para visualizar el Reporte Consolidado.")
