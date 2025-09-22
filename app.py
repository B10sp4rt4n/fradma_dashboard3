import streamlit as st
import pandas as pd
from unidecode import unidecode
from main import main_kpi, main_comparativo, heatmap_ventas
from main import kpi_cpc
from main.analisis_productos_agentes import run as analisis_productos_agentes  # Importación corregida

st.set_page_config(layout="wide")

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
def detectar_y_cargar_archivo(archivo):
    """
    Carga un archivo Excel, detectando si es de CONTPAQi o si tiene múltiples hojas.
    Normaliza las columnas y genera columnas de fecha si es necesario.
    """
    try:
        xls = pd.ExcelFile(archivo)
        hojas = xls.sheet_names

        df = None
        hoja_seleccionada = None

        # Caso 1: Múltiples hojas
        if len(hojas) > 1:
            if "X AGENTE" in hojas:
                hoja_seleccionada = "X AGENTE"
                st.info("📌 Archivo con múltiples hojas. Leyendo automáticamente la hoja 'X AGENTE'.")
            else:
                st.warning("⚠️ No se encontró la hoja 'X AGENTE'. Por favor, selecciona una manualmente.")
                hoja_seleccionada = st.sidebar.selectbox("📄 Selecciona la hoja a analizar", hojas)
        
        # Caso 2: Una sola hoja
        else:
            hoja_seleccionada = hojas[0]

        if hoja_seleccionada:
            # Detección de CONTPAQi (solo si no es 'X AGENTE' para evitar lecturas innecesarias)
            skiprows = 0
            if hoja_seleccionada != "X AGENTE":
                preview = pd.read_excel(xls, sheet_name=hoja_seleccionada, nrows=1, header=None)
                # Comprueba si 'contpaqi' está en alguna de las celdas de la primera fila
                if any("contpaqi" in str(cell).lower() for cell in preview.iloc[0]):
                    skiprows = 3
                    st.info("📌 Archivo tipo CONTPAQi detectado. Se omitirán las primeras 3 filas.")

            df = pd.read_excel(xls, sheet_name=hoja_seleccionada, skiprows=skiprows)
            df = normalizar_columnas(df)

            # Generación de columnas de fecha si 'fecha' existe
            if "fecha" in df.columns:
                df["fecha"] = pd.to_datetime(df["fecha"], errors='coerce')
                # Solo crea las columnas si la conversión fue exitosa en al menos una fila
                if not df["fecha"].isnull().all():
                    df["ano"] = df["fecha"].dt.year
                    df["mes"] = df["fecha"].dt.month
                    st.success("✅ Columnas 'ano' y 'mes' generadas a partir de la columna 'fecha'.")
        
        return df

    except Exception as e:
        st.error(f"❌ Error al leer el archivo Excel: {e}")
        return None

archivo = st.sidebar.file_uploader("📂 Sube tu archivo de ventas (.csv o .xlsx)", type=["csv", "xlsx"])

if archivo:
    df = None
    if archivo.name.endswith('.csv'):
        df = pd.read_csv(archivo)
        df = normalizar_columnas(df)
    else:
        df = detectar_y_cargar_archivo(archivo)

    if df is not None:
        # Guardar archivo original para KPI CxC
        st.session_state["archivo_excel"] = archivo

        # Estandarizar columna de año a 'ano'
        for col in ["ano", "anio", "año", "aã±o", "aã±o"]:
            if col in df.columns:
                df = df.rename(columns={col: "ano"})
                break
        
        if "ano" in df.columns:
            df["ano"] = pd.to_numeric(df["ano"], errors='coerce').dropna()

        # Detectar columna de ventas
        columnas_ventas_usd = ["valor_usd", "ventas_usd", "ventas_usd_con_iva"]
        columna_encontrada = next((col for col in columnas_ventas_usd if col in df.columns), None)

        if not columna_encontrada:
            st.warning("⚠️ No se encontró una columna de ventas compatible ('valor_usd', 'ventas_usd', etc.).")
            with st.expander("Columnas detectadas"):
                st.write(df.columns.tolist())
        else:
            st.success(f"✅ Columna de ventas detectada: **{columna_encontrada}**")
            st.session_state["columna_ventas"] = columna_encontrada

        st.session_state["df"] = df

        if "ano" in df.columns:
            años_disponibles = sorted(df["ano"].dropna().unique().astype(int))
            if años_disponibles:
                año_base = st.sidebar.selectbox("📅 Selecciona el año base", años_disponibles, index=len(años_disponibles)-1)
                st.session_state["año_base"] = año_base
                st.success(f"📌 Año base seleccionado: {año_base}")
            else:
                st.warning("⚠️ No se encontraron años válidos en la columna 'ano'.")
        else:
            st.warning("⚠️ No se encontró la columna 'ano'. No se pueden filtrar datos por año.")

menu = st.sidebar.radio("Navegación", [
    "📈 KPIs Generales",
    "📊 Comparativo Año vs Año",
    "🔥 Heatmap Ventas",
    "💳 KPI Cartera CxC",
    "📊 Análisis Productos y Agentes"  # Opción para análisis de productos y agentes
])

if menu == "📈 KPIs Generales":
    main_kpi.run()

elif menu == "📊 Comparativo Año vs Año":
    if "df" in st.session_state and "ano" in st.session_state["df"].columns:
        año_base = st.session_state.get("año_base")
        if año_base:
            main_comparativo.run(st.session_state["df"], año_base=año_base)
        else:
            st.warning("⚠️ Por favor, selecciona un año base para continuar.")
    else:
        st.warning("⚠️ Sube un archivo con la columna 'ano' para ver el comparativo.")

elif menu == "🔥 Heatmap Ventas":
    if "df" in st.session_state:
        heatmap_ventas.run(st.session_state["df"])
    else:
        st.warning("⚠️ Primero sube un archivo para visualizar el Heatmap.")

elif menu == "💳 KPI Cartera CxC":
    if "archivo_excel" in st.session_state:
        kpi_cpc.run(st.session_state["archivo_excel"])
    else:
        st.warning("⚠️ Primero sube un archivo para visualizar el KPI de Cartera CxC.")

elif menu == "📊 Análisis Productos y Agentes":
    if "df" in st.session_state:
        analisis_productos_agentes(st.session_state["df"])  # Llamada a la función run del módulo de análisis
    else:
        st.warning("⚠️ Primero sube un archivo válido para visualizar el análisis de productos y agentes.")
