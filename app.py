import streamlit as st
import pandas as pd
import os
from datetime import datetime
from dotenv import load_dotenv
from unidecode import unidecode

try:
    import plotly.graph_objects as go
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

try:
    from streamlit_option_menu import option_menu
    OPTION_MENU_AVAILABLE = True
except ImportError:
    OPTION_MENU_AVAILABLE = False

# Cargar variables de entorno desde .env (si existe)
load_dotenv()

# Logo por defecto (incluido en el repositorio)
_LOGO_PATH = os.path.join(os.path.dirname(__file__), "Logo de CIMA Analytics y SynAppsSys.png")
_DEFAULT_LOGO = open(_LOGO_PATH, "rb").read() if os.path.exists(_LOGO_PATH) else None

from main import main_kpi, main_comparativo, heatmap_ventas
from main import kpi_cpc, reporte_ejecutivo, ytd_lineas, ytd_productos, reporte_consolidado
from main import vendedores_cxc, herramientas_financieras, ingesta_cfdi
from main import universo_cfdi
from main import fiscal
from main import mapa_clientes
from main import knowledge_base
from main import data_assistant
from utils.data_cleaner import limpiar_columnas_texto, detectar_duplicados_similares
from utils.data_normalizer import normalizar_columnas
from utils.logger import configurar_logger, log_dataframe_info, log_execution_time
from utils.filters import (
    aplicar_filtro_fechas, 
    aplicar_filtro_cliente, 
    aplicar_filtro_monto,
    aplicar_filtro_categoria_riesgo,
    mostrar_resumen_filtros,
    render_filtros_inline,
)
from utils.export_helper import crear_excel_metricas_cxc, crear_reporte_html
from utils.cache_helper import GestorCache, decorador_medicion_tiempo
from utils.auth import AuthManager, UserRole, get_current_user
from utils.admin_panel import mostrar_info_usuario, mostrar_panel_usuarios, mostrar_panel_configuracion
from utils.roi_tracker import init_roi_tracker
from utils.neon_loader import cargar_cfdi_como_df
from utils.sovereign_periods import build_sovereign_index

# Configurar logger de la aplicación
logger = configurar_logger("dashboard_app", nivel="INFO")

# Inicializar gestor de autenticación
auth_manager = AuthManager()

# Inicializar gestor de caché
gestor_cache = GestorCache()  # TTL se especifica en cada llamada a obtener_o_calcular()

# Configuración de página con tema mejorado
st.set_page_config(
    layout="wide",
    page_title="Cima Analytics",
    page_icon="�",
    initial_sidebar_state="expanded"
)


# ── CSS global: corrige visibilidad de iconos en nav-link-selected ──────────
st.markdown("""
<style>
/* Ítem seleccionado: texto e ícono siempre blancos */
[data-testid="stSidebar"] .nav-link.active i,
[data-testid="stSidebar"] .nav-link.active span {{
    color: white !important;
}}
/* Ítem normal: texto naranja */
[data-testid="stSidebar"] .nav-link:not(.active) {{
    color: #FF6B35 !important;
}}
[data-testid="stSidebar"] .nav-link:not(.active) i {{
    color: #FF6B35 !important;
}}
</style>
""", unsafe_allow_html=True)

# =====================================================================
# PANTALLA DE LOGIN — MULTI-USUARIO
# =====================================================================

if "user" not in st.session_state:
    st.session_state["user"] = None
if "empresa_id" not in st.session_state:
    st.session_state["empresa_id"] = None
if "rfc_empresa" not in st.session_state:
    st.session_state["rfc_empresa"] = None
if "empresa_nombre" not in st.session_state:
    st.session_state["empresa_nombre"] = None
# Estado auxiliar de login (RFC lookup)
if "_login_empresa" not in st.session_state:
    st.session_state["_login_empresa"] = None
if "_login_view" not in st.session_state:
    st.session_state["_login_view"] = "login"  # "login" | "register"

if st.session_state["user"] is None:
    # Ocultar sidebar y menús en pantalla de login
    st.markdown("""
    <style>
        [data-testid="stSidebar"] { display: none !important; }
        #MainMenu { visibility: hidden; }
        footer { visibility: hidden; }
        header { visibility: hidden; }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("<br><br>", unsafe_allow_html=True)
    col_l, col_c, col_r = st.columns([1, 1.2, 1])

    with col_c:
        # Logo
        if _DEFAULT_LOGO:
            import base64
            b64 = base64.b64encode(_DEFAULT_LOGO).decode()
            st.markdown(
                f'<div style="display:flex;justify-content:center;">'
                f'<img src="data:image/png;base64,{b64}" width="300"></div>',
                unsafe_allow_html=True
            )
        else:
            st.markdown("<div style='text-align:center;font-size:56px;'>📈</div>", unsafe_allow_html=True)

        st.markdown(
            """
            <div style='text-align:center; margin:20px 0;'>
                <h3>Cima Analytics</h3>
                <p style='font-size:14px; color:#6b7280;'>Plataforma de Análisis de Ventas y CxC</p>
            </div>
            """,
            unsafe_allow_html=True
        )

        # ----------------------------------------------------------------
        # Vista: LOGIN
        # ----------------------------------------------------------------
        if st.session_state["_login_view"] == "login":

            # RFC lookup (identifica el tenant antes de iniciar sesión)
            rfc_input = st.text_input(
                "RFC de tu empresa",
                placeholder="Ej. XAXX010101000",
                key="login_rfc",
                help="Ingresa el RFC de la empresa para identificar tu cuenta. Déjalo vacío si eres superadministrador.",
            )

            # Mostrar nombre de empresa al escribir el RFC
            empresa_encontrada = None
            if rfc_input and len(rfc_input) >= 3:
                empresa_encontrada = auth_manager.get_empresa_by_rfc(rfc_input)
                if empresa_encontrada:
                    st.success(
                        f"🏢 **{empresa_encontrada['razon_social']}** "
                        f"· Plan: {empresa_encontrada.get('plan', '—').capitalize()}"
                    )
                else:
                    st.warning("⚠️ RFC no encontrado. Verifica o contacta al administrador.")

            st.markdown("---")

            # Formulario de credenciales
            with st.form("login_form", clear_on_submit=False):
                username = st.text_input(
                    "Usuario",
                    placeholder="Tu usuario",
                    label_visibility="collapsed",
                    key="login_username",
                )
                password = st.text_input(
                    "Contraseña",
                    type="password",
                    placeholder="Tu contraseña",
                    label_visibility="collapsed",
                    key="login_password",
                )
                submitted = st.form_submit_button(
                    "Ingresar →",
                    use_container_width=True,
                    type="primary",
                )

                if submitted:
                    if not username or not password:
                        st.error("❌ Ingresa usuario y contraseña")
                    else:
                        user = auth_manager.authenticate(username, password)

                        if user:
                            # Validar que el RFC indicado pertenece a alguna empresa del usuario
                            rfc_val = rfc_input.strip().upper() if rfc_input else None
                            rfcs_del_usuario = {e["rfc"].upper() for e in user.empresas}
                            if (
                                rfc_val
                                and rfcs_del_usuario
                                and rfc_val not in rfcs_del_usuario
                            ):
                                logger.warning(
                                    f"Login rechazado: {username} no pertenece a RFC {rfc_val}"
                                )
                                st.error(
                                    f"❌ El usuario '{username}' no tiene acceso a la empresa con RFC `{rfc_val}`."
                                )
                            else:
                                st.session_state["user"] = user
                                st.session_state["_login_empresa"] = None
                                # Auto-seleccionar empresa si solo tiene una (o es superadmin)
                                if user.is_superadmin or len(user.empresas) <= 1:
                                    st.session_state["empresa_id"] = user.empresa_id
                                    st.session_state["rfc_empresa"] = user.rfc_empresa
                                    st.session_state["empresa_nombre"] = user.empresa_nombre
                                else:
                                    # Múltiples empresas → pantalla de selección
                                    st.session_state["empresa_id"] = None
                                    st.session_state["rfc_empresa"] = None
                                    st.session_state["empresa_nombre"] = None
                                logger.info(
                                    f"Login exitoso: {user.username} ({user.role}) "
                                    f"empresas={len(user.empresas)}"
                                )
                                st.success(f"¡Bienvenido, {user.name}! 👋")
                                st.rerun()
                        else:
                            logger.warning(f"Login fallido para: {username}")
                            st.error("❌ Usuario o contraseña incorrectos")

            # Enlace a solicitar acceso
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button(
                "¿No tienes cuenta? Solicitar acceso →",
                use_container_width=True,
                key="btn_go_register",
            ):
                st.session_state["_login_view"] = "register"
                st.rerun()

            # Ayuda
            st.markdown(
                """
                <div style='text-align:center; margin-top:16px; font-size:12px; color:#999;'>
                    💡 Primer acceso: usuario <code>admin</code>, password por defecto<br>
                    ¿Problemas? Contacta al administrador
                </div>
                """,
                unsafe_allow_html=True,
            )

        # ----------------------------------------------------------------
        # Vista: SOLICITAR ACCESO (auto-registro)
        # ----------------------------------------------------------------
        else:
            st.markdown("#### 📝 Solicitar Acceso")
            st.info(
                "Completa el formulario. Tu cuenta quedará **pendiente de aprobación** "
                "por el administrador de tu empresa."
            )

            with st.form("register_form", clear_on_submit=True):
                reg_rfc = st.text_input(
                    "RFC de tu empresa *",
                    placeholder="Ej. XAXX010101000",
                    help="RFC del emisor CFDI de tu empresa (12 o 13 caracteres)",
                )

                # Mostrar nombre de empresa en tiempo real (al hacer submit ya se valida)
                reg_name = st.text_input("Nombre completo *", placeholder="Juan Pérez López")
                reg_email = st.text_input("Email *", placeholder="juan@empresa.com")

                col_u, col_p = st.columns(2)
                with col_u:
                    reg_username = st.text_input(
                        "Usuario *",
                        placeholder="juanperez",
                        help="Mínimo 3 caracteres. Se usará para iniciar sesión.",
                    )
                with col_p:
                    reg_password = st.text_input(
                        "Contraseña *",
                        type="password",
                        help="Mínimo 6 caracteres",
                    )

                reg_submitted = st.form_submit_button(
                    "Enviar solicitud →",
                    use_container_width=True,
                    type="primary",
                )

                if reg_submitted:
                    ok, msg = auth_manager.register_user_request(
                        username=reg_username,
                        email=reg_email,
                        name=reg_name,
                        password=reg_password,
                        rfc_empresa=reg_rfc,
                    )
                    if ok:
                        st.success(f"✅ {msg}")
                        st.session_state["_login_view"] = "login"
                        st.rerun()
                    else:
                        st.error(f"❌ {msg}")

            if st.button("← Volver al login", key="btn_back_login"):
                st.session_state["_login_view"] = "login"
                st.rerun()

    st.stop()

# =====================================================================
# SELECTOR DE EMPRESA — si el usuario tiene acceso a múltiples tenants
# =====================================================================
_user_sel = st.session_state.get("user")
if (
    _user_sel
    and not _user_sel.is_superadmin
    and _user_sel.tiene_multiples_empresas
    and not st.session_state.get("empresa_id")
):
    st.markdown("""
    <style>
        [data-testid="stSidebar"] { display: none !important; }
        #MainMenu { visibility: hidden; }
        footer { visibility: hidden; }
        header { visibility: hidden; }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("<br><br>", unsafe_allow_html=True)
    col_l, col_c, col_r = st.columns([1, 1.6, 1])
    with col_c:
        if _DEFAULT_LOGO:
            import base64 as _b64
            _b64_logo = _b64.b64encode(_DEFAULT_LOGO).decode()
            st.markdown(
                f'<div style="display:flex;justify-content:center;">'
                f'<img src="data:image/png;base64,{_b64_logo}" width="240"></div>',
                unsafe_allow_html=True,
            )

        st.markdown(
            f"""
            <div style='text-align:center; margin:20px 0;'>
                <h3>Selecciona tu empresa</h3>
                <p style='color:#6b7280;'>Hola <strong>{_user_sel.name}</strong>, tienes acceso a
                {len(_user_sel.empresas)} empresas. ¿Con cuál deseas continuar?</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        for emp in _user_sel.empresas:
            with st.container(border=True):
                col_info, col_btn = st.columns([3, 1])
                with col_info:
                    plan_label = emp.get("plan", "essential").capitalize()
                    st.markdown(
                        f"**{emp['razon_social']}**  \n"
                        f"`{emp['rfc']}` &nbsp;·&nbsp; Plan: {plan_label}"
                    )
                with col_btn:
                    if st.button(
                        "Entrar →",
                        key=f"sel_emp_{emp['id']}",
                        use_container_width=True,
                        type="primary",
                    ):
                        st.session_state["empresa_id"] = emp["id"]
                        st.session_state["rfc_empresa"] = emp["rfc"]
                        st.session_state["empresa_nombre"] = emp["razon_social"]
                        # Actualizar campos activos en el objeto User
                        _user_sel.empresa_id = emp["id"]
                        _user_sel.rfc_empresa = emp["rfc"]
                        _user_sel.empresa_nombre = emp["razon_social"]
                        st.session_state["user"] = _user_sel
                        logger.info(
                            f"{_user_sel.username} seleccionó empresa {emp['rfc']}"
                        )
                        st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🚪 Cerrar sesión", key="btn_logout_selector", use_container_width=True):
            st.session_state.clear()
            st.rerun()

    st.stop()

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
    if st.session_state.get("company_logo"):
        st.image(st.session_state["company_logo"], width=120)
    elif _DEFAULT_LOGO:
        st.image(_DEFAULT_LOGO, width=120)
    else:
        st.markdown("# 📈")

with col_title:
    st.title("Cima Analytics")
    st.caption("Plataforma de Análisis de Ventas y CxC")

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
        elif any(h.lower() in ("vtas sae", "ventas sae", "ventas", "vtas") for h in hojas):
            # Formato CIMA/SAE: hoja de ventas con nombre conocido
            hoja = next(h for h in hojas if h.lower() in ("vtas sae", "ventas sae", "ventas", "vtas"))
            metadata["es_vtas_sae"] = True
        else:
            # Si no se especificó hoja y no existe X AGENTE, usar la primera
            hoja = hojas[0]
        
        metadata["hoja_leida"] = hoja
        df = pd.read_excel(xls, sheet_name=hoja)
        df = normalizar_columnas(df)

        # Generación virtual de columnas año y mes desde columna fecha
        if hoja == "X AGENTE" or metadata.get("es_vtas_sae"):
            if hoja == "X AGENTE":
                metadata["es_x_agente"] = True
            if "fecha" in df.columns:
                try:
                    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
                    if "año" not in df.columns:
                        df["año"] = df["fecha"].dt.year
                    if "mes" not in df.columns:
                        df["mes"] = df["fecha"].dt.month
                    metadata["fecha_procesada"] = True
                except Exception as e:
                    logger.exception(f"Error al procesar fecha: {e}")
                    metadata["fecha_error"] = str(e)
            else:
                logger.warning(f"Columna 'fecha' no encontrada en hoja '{hoja}'")
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
    elif metadata.get("es_vtas_sae"):
        st.info(f"📌 Hoja de ventas **'{metadata['hoja_leida']}'** detectada automáticamente (formato SAE/CIMA).")
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
        "YTD por Productos": {
            "obligatorias": ["fecha", "producto"],
            "variantes_obligatorias": {
                "ventas_usd": ["ventas_usd", "ventas_usd_con_iva", "ventas_usd_sin_iva", "importe", "valor_usd", "monto_usd", "total_usd", "valor", "venta"]
            },
            "recomendadas": ["vendedor", "agente", "ejecutivo", "cliente"],
            "opcionales": ["linea_de_negocio", "categoria", "familia"]
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

# Info de usuario y panel de administración en sidebar
with st.sidebar:
    mostrar_info_usuario()  # Muestra info del usuario + botón logout + panel admin

st.sidebar.markdown("### 📂 Carga de Datos")

modo_debug = st.sidebar.checkbox(
    "🧪 Modo debug",
    value=False,
    help="Muestra secciones de diagnóstico (columnas detectadas, etc.)"
)
st.session_state["modo_debug"] = modo_debug

# ── Auto-carga desde Neon (tenant isolation por empresa_id) ──────────────────
_empresa_id_actual = st.session_state.get("empresa_id")
_neon_url = os.environ.get("NEON_DATABASE_URL") or (
    st.secrets.get("NEON_DATABASE_URL") if hasattr(st, "secrets") else None
)

if _empresa_id_actual and _neon_url:
    # Carga automática la primera vez que hay empresa_id pero aún no hay df de CFDI
    _df_fuente = st.session_state.get("_df_fuente")  # 'cfdi' | 'excel' | None
    if _df_fuente != 'excel' and "df" not in st.session_state:
        with st.spinner("⏳ Cargando tus CFDI desde la nube..."):
            try:
                _df_neon = cargar_cfdi_como_df(_empresa_id_actual, _neon_url)
                if not _df_neon.empty:
                    st.session_state["df"] = _df_neon
                    st.session_state["_df_fuente"] = "cfdi"
                    # Reconstruir índice soberano con datos de Neon
                    _sov = build_sovereign_index(_df_neon)
                    st.session_state["sovereign_index"] = _sov
                    _sov_meses = _sov.get("meses", [])
                    if _sov_meses:
                        st.session_state["sovereign_desde"] = _sov_meses[0]
                        st.session_state["sovereign_hasta"] = _sov_meses[-1]
                        st.session_state.setdefault("sovereign_granularidad", "mensual")
                    empresa_badge = st.session_state.get("empresa_nombre", "")
                    st.sidebar.success(
                        f"✅ {len(_df_neon):,} facturas CFDI cargadas"
                        + (f" — {empresa_badge}" if empresa_badge else "")
                    )
            except Exception as _e:
                st.sidebar.warning(f"⚠️ No se pudo cargar CFDI: {_e}")

    # Botón para recargar manualmente los CFDI
    if _empresa_id_actual and _neon_url:
        if st.sidebar.button("🔄 Recargar mis CFDI", help="Vuelve a cargar facturas desde la base de datos"):
            with st.spinner("⏳ Recargando CFDI..."):
                try:
                    _df_neon = cargar_cfdi_como_df(_empresa_id_actual, _neon_url)
                    if not _df_neon.empty:
                        st.session_state["df"] = _df_neon
                        st.session_state["_df_fuente"] = "cfdi"
                        st.session_state.pop("archivo_path", None)
                        # Reconstruir índice soberano con datos frescos de Neon
                        _sov = build_sovereign_index(_df_neon)
                        st.session_state["sovereign_index"] = _sov
                        _sov_meses = _sov.get("meses", [])
                        if _sov_meses:
                            st.session_state["sovereign_desde"] = _sov_meses[0]
                            st.session_state["sovereign_hasta"] = _sov_meses[-1]
                        st.sidebar.success(f"✅ {len(_df_neon):,} facturas actualizadas")
                        st.rerun()
                    else:
                        st.sidebar.warning("⚠️ No hay facturas CFDI para esta empresa")
                except Exception as _e:
                    st.sidebar.error(f"❌ Error al recargar: {_e}")

st.sidebar.markdown("**— o sube un archivo —**")

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
            
            # Si hay múltiples hojas y no existe X AGENTE ni hoja de ventas conocida, permitir selección
            _HOJAS_VENTAS_CONOCIDAS = {"vtas sae", "ventas sae", "ventas", "vtas", "x agente"}
            hoja_seleccionada = None
            if len(hojas) > 1 and not any(h.lower() in _HOJAS_VENTAS_CONOCIDAS for h in hojas):
                st.warning("⚠️ Múltiples hojas detectadas. Selecciona la hoja a leer:")
                hoja_seleccionada = st.sidebar.selectbox("📄 Selecciona la hoja a leer", hojas)
            
            df = detectar_y_cargar_archivo(archivo_bytes, archivo.name, hoja_seleccionada)
            logger.info(f"Excel cargado en {(pd.Timestamp.now() - inicio_carga).total_seconds():.2f}s")

            # ── Pre-cargar hojas CxC para módulos KPI CxC y Vendedores+CxC ──
            _hojas_cxc = [h for h in hojas if "cxc" in h.lower() or "cuenta" in h.lower() or "cobrar" in h.lower()]
            if _hojas_cxc:
                _dfs_cxc = []
                for _h in _hojas_cxc:
                    try:
                        _df_h = normalizar_columnas(pd.read_excel(archivo_bytes, sheet_name=_h))
                        _df_h["_hoja_origen"] = _h

                        # ── Preservar clasificación vigente/vencida del Excel ──────────
                        # Problema: si dias_vencido existe pero está vacío (todo NaN),
                        # calcular_dias_overdue cae al fallback fecha_pago y clasifica
                        # mal (todo vigente o todo vencido según la fecha tentativa).
                        # Solución: verificar que la columna exista Y tenga valores reales.
                        _nh = _h.upper()
                        _es_vigente_hoja = any(k in _nh for k in ("VG", "VIGENTE", "VIGENTES"))
                        _es_vencida_hoja = any(k in _nh for k in ("VCD", "VENCID"))

                        def _col_tiene_valores(df, col):
                            if col not in df.columns:
                                return False
                            return pd.to_numeric(df[col], errors="coerce").notna().any()

                        # ¿El Excel tiene columnas con valores reales para calcular vencimiento?
                        _tiene_dias_validos = any(
                            _col_tiene_valores(_df_h, c)
                            for c in ("dias_vencido", "dias_restante", "dias_restantes",
                                      "vencimiento", "fecha_vencimiento")
                        )

                        if not _tiene_dias_validos:
                            # Sin datos propios: clasificar por nombre de hoja
                            if _es_vigente_hoja:
                                _df_h["dias_vencido"] = -1
                            elif _es_vencida_hoja:
                                _df_h["dias_vencido"] = 1
                        # Si hay columnas con valores reales → no tocar nada

                        _dfs_cxc.append(_df_h)
                    except Exception as _e:
                        logger.warning(f"No se pudo leer hoja CxC '{_h}': {_e}")
                if _dfs_cxc:
                    st.session_state["df_cxc"] = pd.concat(_dfs_cxc, ignore_index=True)
                    logger.info(f"Hojas CxC pre-cargadas en session_state: {_hojas_cxc}")

            # ── Pre-cargar hoja CXPG (Cuentas por Pagar) si existe ───────────
            _hojas_cxp = [h for h in hojas if h.upper().startswith("CXPG") or "pagar" in h.lower() or h.upper() in ("CXP", "CX PAG")]
            if _hojas_cxp:
                try:
                    _df_cxp = normalizar_columnas(pd.read_excel(archivo_bytes, sheet_name=_hojas_cxp[0]))
                    st.session_state["df_cxp"] = _df_cxp
                    logger.info(f"Hoja CxP pre-cargada: {_hojas_cxp[0]}")
                except Exception as _e:
                    logger.warning(f"No se pudo leer hoja CxP '{_hojas_cxp[0]}': {_e}")

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

        # ── Info del archivo + validación en un único expander ───────────
        validacion = validar_columnas_requeridas(df)
        total_errores    = sum(1 for m in validacion.values() for i in m if i["status"] == "❌")
        total_advertencias = sum(1 for m in validacion.values() for i in m if i["status"] == "⚠️")

        if total_errores > 0:
            _info_icon = "🚨"
        elif total_advertencias > 0:
            _info_icon = "⚠️"
        else:
            _info_icon = "✅"

        with st.sidebar.expander(f"{_info_icon} Info del archivo", expanded=False):
            st.success(f"**{archivo.name}**")
            st.info(f"📊 {len(df):,} registros | {len(df.columns)} columnas")

            if not columna_encontrada:
                st.warning("⚠️ No se detectó columna de ventas estándar")
                st.write(df.columns.tolist())

            st.markdown("---")
            st.markdown("**📋 Validación de columnas**")

            # ── Tabla resumen alineada por columnas ────────────────────
            _filas_html = ""
            _detalles_html = ""
            for modulo, checklist in validacion.items():
                if not checklist:
                    continue
                errores_m = sum(1 for i in checklist if i["status"] == "❌")
                advert_m  = sum(1 for i in checklist if i["status"] == "⚠️")
                ok_m      = sum(1 for i in checklist if i["status"] == "✅")
                icono_m   = "🔴" if errores_m > 0 else ("🟡" if advert_m > 0 else "🟢")
                _filas_html += (
                    f"<tr>"
                    f"<td style='padding:2px 6px'>{icono_m} <b>{modulo}</b></td>"
                    f"<td style='padding:2px 6px;text-align:center'>✅ {ok_m}</td>"
                    f"<td style='padding:2px 6px;text-align:center'>⚠️ {advert_m}</td>"
                    f"<td style='padding:2px 6px;text-align:center'>❌ {errores_m}</td>"
                    f"</tr>"
                )
                items = checklist if modo_debug else [i for i in checklist if i["status"] != "✅"]
                for item in items:
                    _detalles_html += (
                        f"<tr>"
                        f"<td style='padding:1px 4px'>{item['status']}</td>"
                        f"<td style='padding:1px 4px;font-size:11px'><code>{item['col']}</code></td>"
                        f"<td style='padding:1px 4px;font-size:11px;color:#aaa'>{item['mensaje']}</td>"
                        f"</tr>"
                    )
            st.markdown(
                f"<table style='width:100%;border-collapse:collapse;font-size:12px'>"
                f"<thead><tr>"
                f"<th style='text-align:left;padding:2px 6px'>Módulo</th>"
                f"<th style='text-align:center;padding:2px 6px'>OK</th>"
                f"<th style='text-align:center;padding:2px 6px'>Aviso</th>"
                f"<th style='text-align:center;padding:2px 6px'>Error</th>"
                f"</tr></thead>"
                f"<tbody>{_filas_html}</tbody>"
                f"</table>",
                unsafe_allow_html=True
            )
            if _detalles_html:
                st.markdown(
                    f"<table style='width:100%;border-collapse:collapse;margin-top:6px;font-size:12px'>"
                    f"<tbody>{_detalles_html}</tbody></table>",
                    unsafe_allow_html=True
                )

            if total_errores == 0 and total_advertencias == 0:
                st.success("✅ Todas las columnas críticas presentes")



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
        st.session_state["_df_fuente"] = "excel"
        st.session_state["archivo_path"] = archivo

        # ── Índice soberano de períodos ──────────────────────────────
        _sovereign = build_sovereign_index(df)
        st.session_state["sovereign_index"] = _sovereign
        # Inicializar período activo al rango completo del dataset
        _meses = _sovereign.get("meses", [])
        if _meses:
            st.session_state.setdefault("sovereign_desde", _meses[0])
            st.session_state.setdefault("sovereign_hasta", _meses[-1])
            st.session_state.setdefault("sovereign_granularidad", "mensual")

        if "año" in df.columns:
            st.session_state.setdefault("año_base", sorted(df["año"].dropna().unique())[-1] if not df["año"].dropna().empty else None)
        else:
            st.sidebar.warning("⚠️ No se encontró columna 'año'")

# =====================================================================
# (Los filtros avanzados se aplican después de definir menu — ver abajo)
# =====================================================================

# Placeholder — FILTROS_POR_VISTA se define tras la definición de menu
# (Los filtros avanzados se aplican después de definir menu — ver sección FILTROS AVANZADOS)




# =====================================================================
# EXPORTACIÓN DE REPORTES (SPRINT 4)
# =====================================================================


# =====================================================================
# NAVEGACIÓN MEJORADA CON TABS Y TOOLTIPS
# =====================================================================

# Inicializar estado de IA en session_state
if "ia_premium_activada" not in st.session_state:
    st.session_state["ia_premium_activada"] = False
if "openai_api_key" not in st.session_state:
    st.session_state["openai_api_key"] = None
if "passkey_valido" not in st.session_state:
    st.session_state["passkey_valido"] = False

PASSKEY_PREMIUM = os.getenv("PASSKEY_PREMIUM", "fradma2026")

st.sidebar.markdown("### 🧭 Navegación")

user = get_current_user()

# ── Construir grupos y opciones dinámicamente ──────────────────────────────
_grupos = {
    "Resumen": {
        "icon": "speedometer2",
        "items": [
            ("🎯 Reporte Ejecutivo",     "file-earmark-bar-chart"),
            ("📊 Reporte Consolidado",   "grid-1x2"),
        ]
    },
    "Ventas": {
        "icon": "graph-up-arrow",
        "items": [
            ("📈 KPIs Generales",            "bar-chart-line"),
            ("📊 Comparativo Año vs Año",    "arrow-left-right"),
            ("📉 YTD por Línea de Negocio",  "diagram-3"),
            ("🔷 YTD por Producto",          "box-seam"),
            ("🔥 Heatmap Ventas",            "fire"),
        ]
    },
    "Cartera": {
        "icon": "credit-card",
        "items": [
            ("💳 KPI Cartera CxC",   "wallet2"),
            ("👥 Vendedores + CxC",  "people"),
        ]
    },
    "CFDI y Fiscal": {
        "icon": "receipt",
        "items": [
            ("📂 Cargar mis facturas", "cloud-upload"),
            ("📋 Universo de CFDIs",   "collection"),
            ("🧾 Desglose Fiscal",     "journal-text"),
        ]
    },
    "Herramientas": {
        "icon": "tools",
        "items": [
            ("🧰 Herramientas Financieras", "calculator"),
            ("📍 Mapa de Clientes",         "geo-alt"),
            ("📚 Knowledge Base",           "book"),
        ]
    },
}

# Agregar IA si el usuario tiene acceso
if user and user.can_use_ai():
    _grupos["Herramientas"]["items"].append(("🤖 Asistente de Datos", "robot"))

# Agregar Admin si aplica
if user and user.can_manage_users():
    _grupos["Admin"] = {
        "icon": "shield-lock",
        "items": [
            ("⚙️ Gestión de Usuarios", "person-gear"),
            ("🔧 Configuración",       "sliders"),
        ]
    }

# ── Ordenar grupo de opciones en una lista plana (para compatibilidad) ──────
_todas_opciones = [item for g in _grupos.values() for item, _ in g["items"]]
_todos_iconos   = [icon for g in _grupos.values() for _, icon in g["items"]]

if OPTION_MENU_AVAILABLE:
    with st.sidebar:
        _menu_default = 0
        if "_menu_navegar_a" in st.session_state:
            _destino = st.session_state.pop("_menu_navegar_a")
            if _destino in _todas_opciones:
                _menu_default = _todas_opciones.index(_destino)
        menu = option_menu(
            menu_title=None,
            options=_todas_opciones,
            icons=_todos_iconos,
            menu_icon="cast",
            default_index=_menu_default,
            styles={
                "container":        {"padding": "0 !important", "background-color": "transparent"},
                "icon":             {"font-size": "14px", "color": "#1F4E79"},
                "nav-link":         {"font-size": "13px", "text-align": "left", "margin": "1px 0",
                                     "padding": "6px 10px", "--hover-color": "#dce8f7",
                                     "color": "#FF6B35"},
                "nav-link-selected":{"background-color": "#1F4E79", "color": "white",
                                     "font-weight": "600"},
            },
        )
else:
    # Fallback: radio simple si no está instalado option_menu
    menu = st.sidebar.radio("Selecciona una vista:", _todas_opciones)


# ─── Configuración y ajustes al fondo del sidebar ───────────────────────────
with st.sidebar:
    st.markdown("---")

    # Filtros de datos (se poblará más abajo, luego de definir _filtros_vista)
    # ─ placeholder ─

with st.sidebar:
    # ----------------------------------------------------------------
    # WIDGET ROI: Muestra el valor generado en tiempo real
    # ----------------------------------------------------------------
    try:
        roi_tracker = init_roi_tracker(st.session_state)
        roi_summary = roi_tracker.get_summary()

        with st.expander("💰 Tu ROI", expanded=False):

            # ── Mini-tabla compacta con colores diferenciados ──────────
            _hoy_hrs  = roi_summary['today']['hrs']
            _hoy_val  = roi_summary['today']['value']
            _mes_hrs  = roi_summary['month']['hrs']
            _mes_val  = roi_summary['month']['value']
            _mes_dias = roi_summary['month']['workdays']
            _año_val  = roi_summary['year']['value']
            _año_dias = roi_summary['year']['workdays']

            # colores: clasificación=azul tenue, KPI resultante=verde tenue
            _CL = "#1a3a5c"   # fondo clasificación (azul oscuro)
            _KP = "#1a4a2a"   # fondo KPI resultante (verde oscuro)
            _TC = "#90CAF9"   # texto clasificación (azul claro)
            _TK = "#81C784"   # texto KPI resultante (verde claro)

            st.markdown(f"""
<style>
.roi-mini-table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 12px;
    font-family: 'Segoe UI', Arial, sans-serif;
}}
.roi-mini-table td {{
    padding: 4px 6px;
    border-radius: 4px;
}}
.roi-cl {{ background:{_CL}; color:{_TC}; font-weight:600; }}
.roi-kp {{ background:{_KP}; color:{_TK}; font-weight:700; text-align:right; }}
.roi-sep {{ height: 4px; }}
</style>
<table class="roi-mini-table">
  <tr><td class="roi-cl">⏱️ Hoy — horas</td><td class="roi-kp">{_hoy_hrs:.1f} h</td></tr>
  <tr><td class="roi-cl">💵 Hoy — valor</td><td class="roi-kp">${_hoy_val:,.0f}</td></tr>
  <tr class="roi-sep"><td colspan="2"></td></tr>
  <tr><td class="roi-cl">📅 Mes — horas</td><td class="roi-kp">{_mes_hrs:.1f} h</td></tr>
  <tr><td class="roi-cl">📅 Mes — días lab.</td><td class="roi-kp">{_mes_dias:.1f} d</td></tr>
  <tr><td class="roi-cl">💵 Mes — valor</td><td class="roi-kp">${_mes_val:,.0f}</td></tr>
  <tr class="roi-sep"><td colspan="2"></td></tr>
  <tr><td class="roi-cl">📊 Año — valor</td><td class="roi-kp">${_año_val:,.0f}</td></tr>
  <tr><td class="roi-cl">📊 Año — días lab.</td><td class="roi-kp">{_año_dias:.1f} d</td></tr>
</table>
""", unsafe_allow_html=True)

            # ── Justificación compacta ─────────────────────────────────
            if _mes_hrs > 0:
                _ae = roi_summary['month']['analyst_equiv']
                st.markdown("---")
                st.caption(
                    f"👤 Equiv. **{_ae['months_analyst']:.3f} mes(es)** analista · "
                    f"Ref. ${_ae['analyst_salary']:,}/mes"
                )
                if _mes_dias >= 0.5:
                    st.caption(
                        f"🎯 Proy. anual: **${_ae['monthly_savings']*12:,.0f} MXN** · "
                        f"{_mes_dias*12:.1f} días/año"
                    )

            # ── Actividad de hoy ───────────────────────────────────────
            if roi_summary['today']['actions'] > 0:
                _all_act = roi_tracker.session_state.roi_data.get("actions", [])
                _da_q = len([
                    a for a in _all_act
                    if a.get("module") == "data_assistant"
                    and a.get("action") in ["nl2sql_query", "nl2sql_complex_query"]
                    and a.get("timestamp").date() == datetime.now().date()
                ])
                if _da_q > 0:
                    st.caption(f"✨ {_da_q} consulta(s) IA hoy")
                else:
                    st.caption(f"✨ {roi_summary['today']['actions']} acción(es) hoy")
            else:
                st.caption("💡 Completa acciones para ver tu ROI crecer")

    except Exception as e:
        logger.warning(f"Error en widget ROI: {e}")
        pass

    # IA Premium — al fondo
    st.markdown("---")
    _ia_label = "🤖 IA Premium ✅" if st.session_state.get("ia_premium_activada") else "🤖 Análisis Premium con IA"
    with st.expander(_ia_label, expanded=False):
        passkey_input = st.text_input(
            "🔑 Passkey Premium",
            type="password",
            placeholder="Ingresa tu passkey",
            help="Activa funciones premium de análisis con IA"
        )

        if passkey_input == PASSKEY_PREMIUM:
            if not st.session_state["passkey_valido"]:
                st.session_state["passkey_valido"] = True
                st.success("✅ Passkey válido!")

            st.markdown("**Configuración de IA**")
            api_key_env = os.getenv("OPENAI_API_KEY", "")

            if api_key_env:
                st.session_state["openai_api_key"] = api_key_env
                st.success("🔑 API key detectada desde variable de entorno")
                st.session_state["ia_premium_activada"] = True
            else:
                openai_api_key = st.text_input(
                    "OpenAI API Key",
                    type="password",
                    placeholder="sk-...",
                    help="Ingresa tu API key de OpenAI para habilitar análisis con IA"
                )

                if openai_api_key:
                    from utils.ai_helper import validar_api_key
                    if validar_api_key(openai_api_key):
                        st.session_state["openai_api_key"] = openai_api_key
                        st.session_state["ia_premium_activada"] = True
                        st.success("✅ API key válida")
                    else:
                        st.error("❌ API key inválida")
                        st.session_state["ia_premium_activada"] = False
                else:
                    st.session_state["ia_premium_activada"] = False

            if st.session_state["ia_premium_activada"]:
                st.success("✅ IA Premium activa — ve al Reporte Ejecutivo para usarla")

        else:
            st.session_state["passkey_valido"] = False
            st.session_state["ia_premium_activada"] = False
            st.session_state["openai_api_key"] = None

            if passkey_input:
                st.error("❌ Passkey incorrecto")
            else:
                st.caption("🔐 Ingresa el passkey para acceder a funciones premium")

    # Exportar Reportes — al fondo
    if "df" in st.session_state and "archivo_excel" in st.session_state:
        st.markdown("---")
        with st.expander("📥 Exportar Reportes", expanded=False):
            # ── Cargar datos CxC ──────────────────────────────────────────
            _exp_cxc = None
            _exp_cxc_proc = None
            _exp_metricas = None
            try:
                _xls = pd.ExcelFile(st.session_state["archivo_excel"])
                _hojas = _xls.sheet_names
                if "CXC VIGENTES" in _hojas and "CXC VENCIDAS" in _hojas:
                    _df_vig = normalizar_columnas(pd.read_excel(_xls, sheet_name='CXC VIGENTES'))
                    _df_ven = normalizar_columnas(pd.read_excel(_xls, sheet_name='CXC VENCIDAS'))
                    _exp_cxc = pd.concat([_df_vig, _df_ven], ignore_index=True, sort=False)
                else:
                    for _h in _hojas:
                        if "cxc" in _h.lower() or "cuenta" in _h.lower():
                            _exp_cxc = normalizar_columnas(pd.read_excel(_xls, sheet_name=_h))
                            break

                if _exp_cxc is not None:
                    if "saldo_adeudado" not in _exp_cxc.columns:
                        for _c in ["saldo", "saldo_adeudo", "adeudo", "importe", "monto", "total", "saldo_usd"]:
                            if _c in _exp_cxc.columns:
                                _exp_cxc = _exp_cxc.rename(columns={_c: "saldo_adeudado"})
                                break
                    if "saldo_adeudado" in _exp_cxc.columns:
                        _s = _exp_cxc["saldo_adeudado"].astype(str).str.replace(",", "", regex=False).str.replace("$", "", regex=False)
                        _exp_cxc["saldo_adeudado"] = pd.to_numeric(_s, errors="coerce").fillna(0)
                    else:
                        _exp_cxc["saldo_adeudado"] = 0

                    from utils.cxc_helper import calcular_metricas_basicas, preparar_datos_cxc
                    _, _exp_cxc_proc, _ = preparar_datos_cxc(_exp_cxc)
                    _exp_metricas = calcular_metricas_basicas(_exp_cxc_proc)
            except Exception as _e:
                logger.exception(f"Error cargando CxC para exportación: {_e}")

            # ── Excel ─────────────────────────────────────────────────────
            if _exp_cxc_proc is not None and _exp_metricas is not None:
                try:
                    _excel_buf = crear_excel_metricas_cxc(_exp_metricas, _exp_cxc_proc)
                    st.download_button(
                        label="📊 Excel",
                        data=_excel_buf,
                        file_name="reporte_cxc.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                    )
                except Exception as _e:
                    st.warning(f"⚠️ Excel no disponible: {_e}")
            else:
                st.caption("⚠️ Sin datos CxC para Excel")

            # ── HTML ──────────────────────────────────────────────────────
            if _exp_cxc_proc is not None and _exp_metricas is not None:
                st.markdown("---")
                st.caption("**Secciones del reporte HTML:**")
                _inc_res = st.checkbox("📈 Resumen Ejecutivo", value=True, key="exp_inc_res")
                _inc_ven = st.checkbox("💼 Ventas Detalladas",  value=True, key="exp_inc_ven")
                _inc_cxc = st.checkbox("🏦 CxC Detallada",      value=True, key="exp_inc_cxc")
                _inc_ant = st.checkbox("📅 Tabla Antigüedad",   value=False, key="exp_inc_ant")
                _inc_scr = st.checkbox("🎯 Score de Salud",     value=True, key="exp_inc_scr")
                _inc_top = st.checkbox("👥 Top 5 Deudores",     value=False, key="exp_inc_top")

                _secciones = []
                if _inc_res: _secciones.append('resumen_ejecutivo')
                if _inc_ven: _secciones.append('ventas')
                if _inc_cxc: _secciones.append('cxc')
                if _inc_ant: _secciones.append('antiguedad')
                if _inc_scr: _secciones.append('score')
                if _inc_top: _secciones.append('top_clientes')

                if _secciones:
                    try:
                        _html = crear_reporte_html(
                            _exp_metricas, _exp_cxc_proc,
                            df_ventas=st.session_state.get("df"),
                            secciones=_secciones,
                        )
                        st.download_button(
                            label="🌐 Descargar HTML",
                            data=_html,
                            file_name="reporte_ejecutivo.html",
                            mime="text/html",
                            use_container_width=True,
                        )
                    except Exception as _e:
                        st.warning(f"⚠️ HTML no disponible: {_e}")
                else:
                    st.warning("⚠️ Selecciona al menos una sección")


    st.markdown("---")
    _user_for_admin = get_current_user()
    if _user_for_admin and _user_for_admin.can_manage_users():
        with st.expander("⚙️ Administración", expanded=False):
            if st.button("👥 Usuarios", use_container_width=True, key="admin_nav_usuarios"):
                st.session_state["_menu_navegar_a"] = "⚙️ Gestión de Usuarios"
                st.rerun()
            if st.button("🔧 Configuración", use_container_width=True, key="admin_nav_config"):
                st.session_state["_menu_navegar_a"] = "🔧 Configuración"
                st.rerun()
    with st.expander("🎨 Personalización CIMA", expanded=False):
        st.markdown("**🖼️ Logo de empresa**")
        logo_file = st.file_uploader(
            "Sube tu logo (PNG, JPG)",
            type=["png", "jpg", "jpeg", "svg", "webp"],
            key="logo_uploader",
            label_visibility="collapsed",
            help="Se mostrará en el encabezado del dashboard."
        )
        if logo_file is not None:
            st.session_state["company_logo"] = logo_file.getvalue()
            st.session_state["company_logo_name"] = logo_file.name
            st.success("Logo actualizado ✓")
        if st.session_state.get("company_logo"):
            st.image(st.session_state["company_logo"], use_container_width=True)
            if st.button("🗑️ Quitar logo", key="btn_remove_logo", use_container_width=True):
                st.session_state.pop("company_logo", None)
                st.session_state.pop("company_logo_name", None)
                st.rerun()

    with st.expander("⚙️ Ajustes ROI", expanded=False):
        st.markdown("**💼 Sueldo de Referencia**")
        roi_tracker_config = init_roi_tracker(st.session_state)
        current_salary = roi_tracker_config.get_analyst_salary()
        new_salary = st.number_input(
            "Sueldo mensual de analista (MXN)",
            min_value=5000,
            max_value=100000,
            value=int(current_salary),
            step=1000,
            help="Ajusta el sueldo de referencia para calcular equivalencias. Típico: $20k-$30k MXN/mes"
        )
        if new_salary != current_salary:
            roi_tracker_config.set_analyst_salary(new_salary)
            st.success(f"✅ Sueldo actualizado a ${new_salary:,} MXN/mes")
            st.info("💡 Los cálculos de ROI usarán este nuevo valor de referencia")

    st.markdown("---")
    st.toggle(
        "📌 Widgets flotantes",
        value=st.session_state.get("mostrar_widgets_flotantes", True),
        key="mostrar_widgets_flotantes",
        help="Muestra u oculta los indicadores fijos de ROI y filtros en la esquina de la pantalla",
    )

    # =====================================================================
    # FILTROS AVANZADOS — contextuales por vista (SPRINT 4)
# =====================================================================

_FILTROS_POR_VISTA = {
    "🎯 Reporte Ejecutivo": {
        "filtros": ["fecha", "cliente", "monto"],
        "descripcion": "Filtra los datos que alimentan los KPIs, tendencias y top clientes del reporte ejecutivo.",
        "ayuda": {
            "fecha":   "Restringe el período analizado en KPIs y gráfica de tendencias.",
            "cliente": "Muestra solo las métricas del cliente o clientes seleccionados.",
            "monto":   "Excluye operaciones fuera del rango de monto definido.",
        }
    },
    "📊 Reporte Consolidado": {
        "filtros": ["fecha", "cliente", "monto"],
        "descripcion": "Afecta todas las métricas, tablas y gráficas del reporte consolidado.",
        "ayuda": {
            "fecha":   "Define el período de análisis del reporte.",
            "cliente": "Consolida solo las operaciones del cliente seleccionado.",
            "monto":   "Limita el análisis a operaciones dentro del rango de monto.",
        }
    },
    "📈 KPIs Generales": {
        "filtros": ["fecha", "cliente", "monto"],
        "descripcion": "Filtra las ventas que se usan para calcular todos los KPIs de esta vista.",
        "ayuda": {
            "fecha":   "Cambia el período de los KPIs (ventas, ticket promedio, crecimiento).",
            "cliente": "Calcula los KPIs solo para el cliente o clientes seleccionados.",
            "monto":   "Excluye ventas fuera del rango de monto al calcular KPIs.",
        }
    },
    "📊 Comparativo Año vs Año": {
        "filtros": ["cliente", "monto", "año"],
        "descripcion": "Filtra qué operaciones entran en la comparación entre años. Las fechas se controlan directamente en la vista.",
        "ayuda": {
            "cliente": "Compara el desempeño año vs año solo para el cliente seleccionado.",
            "monto":   "Excluye operaciones de bajo/alto monto al comparar períodos.",
            "año":     "Selecciona el año base para el análisis comparativo.",
        }
    },
    "📉 YTD por Línea de Negocio": {
        "filtros": ["fecha", "monto"],
        "descripcion": "Filtra las ventas que alimentan las gráficas YTD de cada línea de negocio.",
        "ayuda": {
            "fecha":  "Acota el período YTD analizado por línea.",
            "monto":  "Excluye operaciones pequeñas o grandes del análisis por línea.",
        }
    },
    "🔷 YTD por Producto": {
        "filtros": ["fecha", "cliente", "monto"],
        "descripcion": "Filtra qué ventas se incluyen en el ranking y evolución de productos.",
        "ayuda": {
            "fecha":   "Define el período del análisis YTD por producto.",
            "cliente": "Muestra solo los productos comprados por el cliente seleccionado.",
            "monto":   "Filtra productos por volumen de venta mínimo/máximo.",
        }
    },
    "🔥 Heatmap Ventas": {
        "filtros": ["fecha", "cliente"],
        "descripcion": "Afecta qué celdas del heatmap se colorean (intensidad de ventas por período).",
        "ayuda": {
            "fecha":   "Restringe los meses/semanas visibles en el mapa de calor.",
            "cliente": "Muestra la concentración de ventas de un cliente específico.",
        }
    },
    "📍 Mapa de Clientes": {
        "filtros": ["cliente", "monto"],
        "descripcion": "Controla qué clientes aparecen marcados en el mapa geográfico.",
        "ayuda": {
            "cliente": "Selecciona clientes específicos para resaltar en el mapa.",
            "monto":   "Muestra solo clientes con operaciones dentro del rango de monto.",
        }
    },
    "💳 KPI Cartera CxC":          {"filtros": [], "descripcion": ""},
    "👥 Vendedores + CxC":         {"filtros": [], "descripcion": ""},
    "🧰 Herramientas Financieras": {"filtros": [], "descripcion": ""},
    "📂 Cargar mis facturas":      {"filtros": [], "descripcion": ""},
    "📋 Universo de CFDIs":        {"filtros": [], "descripcion": ""},
    "🧾 Desglose Fiscal":          {"filtros": [], "descripcion": ""},
    "📚 Knowledge Base":           {"filtros": [], "descripcion": ""},
    "🤖 Asistente de Datos":       {"filtros": [], "descripcion": ""},
    "⚙️ Gestión de Usuarios":      {"filtros": [], "descripcion": ""},
    "🔧 Configuración":            {"filtros": [], "descripcion": ""},
}

_cfg_vista     = _FILTROS_POR_VISTA.get(menu, {"filtros": [], "descripcion": ""})
_filtros_vista = _cfg_vista["filtros"]
_desc_vista    = _cfg_vista.get("descripcion", "")
_ayuda_vista   = _cfg_vista.get("ayuda", {})

# ── Filtros en sidebar (expander colapsable al final del menú) ────────────
if "df" not in st.session_state or not _filtros_vista:
    if "df" in st.session_state:
        st.session_state["df_original_pre_filtro"] = st.session_state["df"].copy()
elif "df" in st.session_state:
    st.session_state["df_original_pre_filtro"] = st.session_state["df"].copy()

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
    elif menu == "🔷 YTD por Producto":
        st.markdown("""
        **Reporte Year-to-Date (YTD) por Producto**
        
        - Ventas acumuladas del año
        - Comparativa vs año anterior
        - Análisis detallado por producto individual
        - Top clientes por producto
        - Proyección y tendencias
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
    elif menu == "🧰 Herramientas Financieras":
        st.markdown("""
        **Calculadoras y utilidades financieras**
        
        - Conversor de monedas en tiempo real
        - Calculadora de descuento por pronto pago
        - Calculadora DSO (Days Sales Outstanding)
        - Herramientas para el día a día
        - Sin necesidad de datos cargados
        """)
    elif menu == "📂 Cargar mis facturas":
        st.markdown("""
        **Carga tus facturas electrónicas del SAT**
        
        - Sube un ZIP con tus CFDIs (.xml)
        - Procesamiento automático en segundos
        - Disponibles inmediatamente en el Asistente de Datos
        """)
    elif menu == "📚 Knowledge Base":
        st.markdown("""
        **Wiki interna y buscador de documentación**
        
        - Búsqueda full-text en toda la documentación
        - Navegación por categorías
        - Vista de documentos con tabla de contenidos
        - Documentos relacionados automáticos
        - Sin necesidad de datos cargados
        """)
    elif menu == "🤖 Asistente de Datos":
        st.markdown("""
        **Consultas en lenguaje natural sobre datos CFDI**
        
        - Pregunta en español sobre tus facturas
        - Traduce automáticamente a SQL seguro
        - Tablas, gráficas e interpretación IA
        - SQL Playground para consultas directas
        - Historial de consultas y exportación CSV
        """)
    elif menu == "⚙️ Gestión de Usuarios":
        st.markdown("""
        **Panel de administración de usuarios** (Solo Admin)
        
        - Crear nuevos usuarios
        - Modificar roles y permisos
        - Resetear contraseñas
        - Ver historial de accesos
        - Activar/desactivar usuarios
        """)
    elif menu == "🔧 Configuración":
        st.markdown("""
        **Configuración del sistema** (Solo Admin)
        
        - Umbrales de CxC
        - Parámetros de alertas
        - Configuración de reportes
        - Ajustes generales
        """)

# (filtros se aplican en el área de contenido, justo antes de cada vista)

# =====================================================================
# WIDGET ROI FLOTANTE — siempre visible al hacer scroll
# =====================================================================
if st.session_state.get("mostrar_widgets_flotantes", True):
  try:
    _roi_tracker_float = init_roi_tracker(st.session_state)
    _roi_sum = _roi_tracker_float.get_summary()

    _hrs_hoy   = _roi_sum['today']['hrs']
    _val_hoy   = _roi_sum['today']['value']
    _hrs_mes   = _roi_sum['month']['hrs']
    _val_mes   = _roi_sum['month']['value']
    _dias_mes  = _roi_sum['month']['workdays']
    _acciones  = _roi_sum['today']['actions']

    # Color del indicador según actividad de hoy
    _color_badge = "#27ae60" if _hrs_hoy > 0 else "#7f8c8d"
    _dot_color   = "#2ecc71" if _hrs_hoy > 0 else "#bdc3c7"

    st.markdown(f"""
    <style>
    #roi-float-widget {{
        position: fixed;
        bottom: 24px;
        right: 24px;
        z-index: 99999;
        background: linear-gradient(145deg, #1a3a5c, #1F4E79);
        color: white;
        border-radius: 14px;
        padding: 14px 18px;
        box-shadow: 0 6px 24px rgba(0,0,0,0.35);
        min-width: 190px;
        max-width: 220px;
        font-family: 'Segoe UI', Arial, sans-serif;
        font-size: 13px;
        line-height: 1.4;
        border: 1px solid rgba(255,255,255,0.1);
        transition: box-shadow 0.2s;
    }}
    #roi-float-widget:hover {{
        box-shadow: 0 8px 32px rgba(0,0,0,0.5);
    }}
    #roi-float-title {{
        font-size: 10px;
        font-weight: 700;
        letter-spacing: 1.2px;
        text-transform: uppercase;
        opacity: 0.65;
        margin-bottom: 6px;
        display: flex;
        align-items: center;
        gap: 5px;
    }}
    #roi-float-dot {{
        width: 7px;
        height: 7px;
        border-radius: 50%;
        background: {_dot_color};
        display: inline-block;
        animation: pulse-dot 2s infinite;
    }}
    @keyframes pulse-dot {{
        0%   {{ opacity: 1; }}
        50%  {{ opacity: 0.4; }}
        100% {{ opacity: 1; }}
    }}
    #roi-float-main {{
        font-size: 22px;
        font-weight: 700;
        letter-spacing: -0.5px;
    }}
    #roi-float-sub {{
        font-size: 11px;
        opacity: 0.7;
        margin-top: 2px;
    }}
    #roi-float-divider {{
        border: none;
        border-top: 1px solid rgba(255,255,255,0.15);
        margin: 9px 0;
    }}
    #roi-float-mes-label {{
        font-size: 10px;
        opacity: 0.6;
        text-transform: uppercase;
        letter-spacing: 0.8px;
    }}
    #roi-float-mes-val {{
        font-size: 15px;
        font-weight: 600;
        margin-top: 2px;
    }}
    #roi-float-mes-sub {{
        font-size: 10px;
        opacity: 0.6;
        margin-top: 2px;
    }}
    #roi-float-acciones {{
        margin-top: 8px;
        font-size: 10px;
        background: rgba(255,255,255,0.1);
        border-radius: 6px;
        padding: 4px 8px;
        text-align: center;
    }}
    </style>

    <div id="roi-float-widget">
        <div id="roi-float-title">
            <span id="roi-float-dot"></span> ROI en tiempo real
        </div>
        <div id="roi-float-main">{_hrs_hoy:.1f} hrs</div>
        <div id="roi-float-sub">hoy · ${_val_hoy:,.0f} MXN</div>
        <hr id="roi-float-divider">
        <div id="roi-float-mes-label">📅 Este mes</div>
        <div id="roi-float-mes-val">${_val_mes:,.0f}</div>
        <div id="roi-float-mes-sub">{_hrs_mes:.1f} hrs · {_dias_mes:.1f} días lab.</div>
        <div id="roi-float-acciones">
            {'✨ ' + str(_acciones) + ' acción(es) hoy' if _acciones > 0 else '💡 Sin actividad aún hoy'}
        </div>
    </div>
    """, unsafe_allow_html=True)

  except Exception:
      pass  # Widget silencioso si falla

if st.session_state.get("mostrar_widgets_flotantes", True):
  try:
    if "df" in st.session_state and "df_original_pre_filtro" in st.session_state:
        _df_filt    = st.session_state["df"]
        _df_orig    = st.session_state["df_original_pre_filtro"]
        _n_filt     = len(_df_filt)
        _n_orig     = len(_df_orig)
        _activos    = _n_filt < _n_orig
        _pct        = (_n_filt / _n_orig * 100) if _n_orig > 0 else 100

        # Leer keys de filtro del session_state
        _fi         = st.session_state.get("filtro_fecha_inicio", None)
        _ff         = st.session_state.get("filtro_fecha_fin", None)
        _clientes   = st.session_state.get("filtro_cliente_select", [])
        _monto_tipo = st.session_state.get("filtro_monto_tipo", None)

        _lineas_filtro = []
        if _fi and _ff:
            _lineas_filtro.append(f"📅 {_fi} → {_ff}")
        if _clientes:
            _lineas_filtro.append(f"👤 {len(_clientes)} cliente(s)")
        if _monto_tipo and _monto_tipo != "Sin filtro de monto":
            _lineas_filtro.append(f"💲 Monto filtrado")

        _color_chip  = "#c0392b" if _activos else "#27ae60"
        _bg_chip     = "linear-gradient(145deg, #5d1a1a, #922b21)" if _activos else "linear-gradient(145deg, #1a5d2d, #1e8449)"
        _label_chip  = "FILTROS ACTIVOS" if _activos else "SIN FILTROS"
        _dot_chip    = "#e74c3c" if _activos else "#2ecc71"

        _detalles_html = "".join(
            f'<div style="font-size:11px;opacity:0.85;margin-top:3px;">{l}</div>'
            for l in _lineas_filtro
        ) if _lineas_filtro else '<div style="font-size:11px;opacity:0.65;margin-top:3px;">Todos los registros</div>'

        st.markdown(f"""
        <style>
        #filtros-float-widget {{
            position: fixed;
            bottom: 24px;
            right: 250px;
            z-index: 99999;
            background: {_bg_chip};
            color: white;
            border-radius: 14px;
            padding: 12px 16px;
            box-shadow: 0 6px 24px rgba(0,0,0,0.35);
            min-width: 170px;
            max-width: 200px;
            font-family: 'Segoe UI', Arial, sans-serif;
            border: 1px solid rgba(255,255,255,0.1);
        }}
        #filtros-float-title {{
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 1.2px;
            text-transform: uppercase;
            opacity: 0.65;
            margin-bottom: 5px;
            display: flex;
            align-items: center;
            gap: 5px;
        }}
        #filtros-float-dot {{
            width: 7px; height: 7px;
            border-radius: 50%;
            background: {_dot_chip};
            display: inline-block;
        }}
        #filtros-float-main {{
            font-size: 18px;
            font-weight: 700;
        }}
        #filtros-float-sub {{
            font-size: 11px;
            opacity: 0.7;
            margin-top: 2px;
        }}
        </style>
        <div id="filtros-float-widget">
            <div id="filtros-float-title">
                <span id="filtros-float-dot"></span> {_label_chip}
            </div>
            <div id="filtros-float-main">{_n_filt:,} <span style="font-size:13px;font-weight:400">regs.</span></div>
            <div id="filtros-float-sub">de {_n_orig:,} · {_pct:.1f}%</div>
            {_detalles_html}
        </div>
        """, unsafe_allow_html=True)

  except Exception:
      pass  # Widget silencioso si falla

# =====================================================================
# FILTROS DE DATOS — área de contenido, encima de cada sección
# =====================================================================
if "df" in st.session_state and _filtros_vista:
    _df_orig = st.session_state.get("df_original_pre_filtro", st.session_state["df"].copy())
    st.session_state["df_original_pre_filtro"] = _df_orig
    _df_filt = _df_orig.copy()

    with st.expander("🔍 Filtrar datos", expanded=False):
        col_izq, col_der = st.columns([3, 1])
        with col_der:
            if st.button("🗑️ Quitar filtros", use_container_width=True, key="content_limpiar_filtros"):
                for _k in list(st.session_state.keys()):
                    if _k.startswith("filtro_") or _k.startswith("inline_filtro_"):
                        del st.session_state[_k]
                st.rerun()

        if "fecha" in _filtros_vista and "fecha" in _df_filt.columns:
            st.markdown("**📅 Rango de fechas**")
            _df_filt = aplicar_filtro_fechas(_df_filt, "fecha")
            st.markdown("---")

        if "cliente" in _filtros_vista and "cliente" in _df_filt.columns:
            st.markdown("**👤 Filtrar por cliente**")
            _df_filt = aplicar_filtro_cliente(_df_filt, "cliente")
            st.markdown("---")

        if "monto" in _filtros_vista:
            _col_v = st.session_state.get("columna_ventas")
            if _col_v and _col_v in _df_filt.columns:
                st.markdown("**💲 Filtrar por monto de venta**")
                _df_filt = aplicar_filtro_monto(_df_filt, _col_v)

        if "año" in _filtros_vista and "año" in _df_filt.columns:
            st.markdown("---")
            st.markdown("**📅 Año base (comparativo)**")
            _años_disp = sorted(_df_filt["año"].dropna().unique())
            if _años_disp:
                _año_actual = st.session_state.get("año_base", _años_disp[-1])
                _idx_actual = _años_disp.index(_año_actual) if _año_actual in _años_disp else len(_años_disp) - 1
                _año_sel = st.selectbox(
                    "Año principal para análisis",
                    _años_disp,
                    index=_idx_actual,
                    key="año_base_filtro",
                    label_visibility="collapsed",
                    help="Año de referencia en el comparativo Año vs Año",
                )
                st.session_state["año_base"] = _año_sel

        if len(_df_filt) < len(_df_orig):
            pct = len(_df_filt) / len(_df_orig) * 100
            st.success(f"✅ Mostrando {len(_df_filt):,} de {len(_df_orig):,} registros ({pct:.0f}%)")

    st.session_state["df"] = _df_filt

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
                hojas = xls.sheet_names
                
                # Prioridad 1: Usar hojas específicas de CxC (igual que KPI CxC)
                if "CXC VIGENTES" in hojas and "CXC VENCIDAS" in hojas:
                    df_vigentes = pd.read_excel(xls, sheet_name='CXC VIGENTES')
                    df_vencidas = pd.read_excel(xls, sheet_name='CXC VENCIDAS')
                    
                    # Normalizar columnas para ambas hojas
                    for df_temp in [df_vigentes, df_vencidas]:
                        nuevas_columnas = []
                        for col in df_temp.columns:
                            col_str = str(col).lower().strip().replace(" ", "_")
                            col_str = unidecode(col_str)
                            nuevas_columnas.append(col_str)
                        df_temp.columns = nuevas_columnas
                    
                    # Registros de CXC VIGENTES son por definición vigentes:
                    # negar dias_vencido para que queden negativos (= días restantes)
                    for col_dias in ['dias_vencido', 'dias_vencidos']:
                        if col_dias in df_vigentes.columns:
                            df_vigentes[col_dias] = -pd.to_numeric(df_vigentes[col_dias], errors='coerce').abs()
                            break
                    
                    # Combinar ambas hojas
                    df_cxc = pd.concat([df_vigentes, df_vencidas], ignore_index=True, sort=False)
                    
                # Prioridad 2: Buscar hoja genérica de CxC
                else:
                    hoja_cxc = None
                    for nombre_hoja in hojas:
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

elif menu == "🔷 YTD por Producto":
    if "df" in st.session_state:
        # Pasar parámetros de IA premium al módulo
        ia_habilitada = st.session_state.get("ia_premium_activada", False)
        api_key = st.session_state.get("openai_api_key", None)
        ytd_productos.run(st.session_state["df"], habilitar_ia=ia_habilitada, openai_api_key=api_key)
    else:
        st.warning("⚠️ Primero sube un archivo para visualizar el reporte YTD por Producto.")
        st.info("📂 Este reporte requiere datos de ventas con: fecha, producto, ventas_usd")

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

elif menu == "🧰 Herramientas Financieras":
    # Las herramientas financieras no requieren datos cargados
    herramientas_financieras.run()

elif menu == "📂 Cargar mis facturas":
    # La ingesta de CFDIs no requiere datos cargados previamente
    ingesta_cfdi.main()

elif menu == "📋 Universo de CFDIs":
    universo_cfdi.run()

elif menu == "🧾 Desglose Fiscal":
    fiscal.run()

elif menu == "📍 Mapa de Clientes":
    mapa_clientes.run()

elif menu == "🤖 Asistente de Datos":
    # Asistente de consultas en lenguaje natural sobre DB CFDI
    data_assistant.run()

elif menu == "📚 Knowledge Base":
    # Knowledge Base no requiere datos cargados
    knowledge_base.run()

elif menu == "📊 Reporte Consolidado":
    if "df" in st.session_state and "archivo_excel" in st.session_state:
        with st.spinner("📊 Generando reporte consolidado..."):
            try:
                # Obtener datos de ventas (igual que Reporte Ejecutivo)
                df_ventas = st.session_state["df"]
                
                # Obtener datos de CxC (misma lógica que Reporte Ejecutivo)
                archivo_excel = st.session_state["archivo_excel"]
                xls = pd.ExcelFile(archivo_excel)
                hojas = xls.sheet_names
                
                # Prioridad 1: Usar hojas específicas de CxC (igual que KPI CxC)
                if "CXC VIGENTES" in hojas and "CXC VENCIDAS" in hojas:
                    df_vigentes = pd.read_excel(xls, sheet_name='CXC VIGENTES')
                    df_vencidas = pd.read_excel(xls, sheet_name='CXC VENCIDAS')
                    
                    # Normalizar columnas para ambas hojas
                    for df_temp in [df_vigentes, df_vencidas]:
                        nuevas_columnas = []
                        for col in df_temp.columns:
                            col_str = str(col).lower().strip().replace(" ", "_")
                            col_str = unidecode(col_str)
                            nuevas_columnas.append(col_str)
                        df_temp.columns = nuevas_columnas
                    
                    # Registros de CXC VIGENTES son por definición vigentes:
                    # negar dias_vencido para que queden negativos (= días restantes)
                    for col_dias in ['dias_vencido', 'dias_vencidos']:
                        if col_dias in df_vigentes.columns:
                            df_vigentes[col_dias] = -pd.to_numeric(df_vigentes[col_dias], errors='coerce').abs()
                            break
                    
                    # Combinar ambas hojas
                    df_cxc = pd.concat([df_vigentes, df_vencidas], ignore_index=True, sort=False)
                    
                # Prioridad 2: Combinar todas las hojas CxC respetando VG=vigente / VCD=vencida
                else:
                    _hojas_cxc_rc = [
                        h for h in hojas
                        if "cxc" in h.lower() or "cuenta" in h.lower() or "cobrar" in h.lower()
                    ]
                    if _hojas_cxc_rc:
                        _dfs_rc = []
                        for _h in _hojas_cxc_rc:
                            _df_h = normalizar_columnas(pd.read_excel(xls, sheet_name=_h))
                            _n = _h.upper()
                            if any(k in _n for k in ("VG", "VIGENTE")):
                                # Forzar dias_vencido negativo para que preparar_datos_cxc lo marque como vigente
                                for _c in ("dias_vencido", "dias_vencidos"):
                                    if _c in _df_h.columns:
                                        _df_h[_c] = -pd.to_numeric(_df_h[_c], errors="coerce").abs()
                                        break
                            elif any(k in _n for k in ("VCD", "VENCID")):
                                # Forzar dias_vencido positivo si está vacío
                                for _c in ("dias_vencido", "dias_vencidos"):
                                    if _c in _df_h.columns:
                                        _vals = pd.to_numeric(_df_h[_c], errors="coerce")
                                        _df_h[_c] = _vals.where(_vals.notna() & (_vals > 0), 1)
                                        break
                                    else:
                                        _df_h["dias_vencido"] = 1
                                        break
                            _dfs_rc.append(_df_h)
                        df_cxc = pd.concat(_dfs_rc, ignore_index=True, sort=False) if _dfs_rc else pd.DataFrame()
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

elif menu == "⚙️ Gestión de Usuarios":
    user = get_current_user()
    if user and user.can_manage_users():
        mostrar_panel_usuarios()
    else:
        st.error("❌ No tienes permisos para acceder a esta sección")
        st.info("💡 Solo los administradores pueden gestionar usuarios")

elif menu == "🔧 Configuración":
    user = get_current_user()
    if user and user.can_manage_users():
        mostrar_panel_configuracion()
    else:
        st.error("❌ No tienes permisos para acceder a esta sección")
        st.info("💡 Solo los administradores pueden modificar la configuración del sistema")
