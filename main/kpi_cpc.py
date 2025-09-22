import streamlit as st
import pandas as pd
import numpy as np
from unidecode import unidecode
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import altair as alt

def normalizar_columnas(df):
    nuevas_columnas = []
    contador = {}
    for col in df.columns:
        col_str = str(col).lower().strip().replace(" ", "_")
        col_str = unidecode(col_str)
        
        if col_str in contador:
            contador[col_str] += 1
            col_str = f"{col_str}_{contador[col_str]}"
        else:
            contador[col_str] = 1
            
        nuevas_columnas.append(col_str)
    df.columns = nuevas_columnas
    return df

def run(archivo):
    st.title("💳 KPI Cartera por Cobrar (CxC)")

    # --- 1. LECTURA Y VALIDACIÓN INICIAL ---
    if not archivo.name.endswith(('.xls', '.xlsx')):
        st.error("❌ Solo se aceptan archivos Excel para el reporte de CxC.")
        return

    try:
        xls = pd.ExcelFile(archivo)
        # Detección flexible de hojas
        hoja_cxc = next((h for h in xls.sheet_names if "cxc" in h.lower()), None)
        if not hoja_cxc:
            st.error("❌ No se encontró una hoja con 'CXC' en su nombre.")
            st.info(f"Hojas disponibles: {xls.sheet_names}")
            return
        
        st.success(f"✅ Leyendo datos desde la hoja: '{hoja_cxc}'")
        df = pd.read_excel(xls, sheet_name=hoja_cxc)
        df = normalizar_columnas(df)

    except Exception as e:
        st.error(f"❌ Error al leer el archivo Excel: {e}")
        return

    # --- 2. ESTANDARIZACIÓN DE COLUMNAS ---
    # Mapeo de posibles nombres a nombres estándar
    mapa_nombres = {
        "deudor": ["cliente", "razon_social", "deudor"],
        "agente": ["vendedor", "agente", "ejecutivo"],
        "saldo": ["saldo", "saldo_usd", "saldo_adeudado", "importe"],
        "fecha_emision": ["fecha", "fecha_de_emision", "fecha_factura"],
        "dias_credito": ["dias_de_credito", "plazo", "dias_credito"]
    }

    for estandar, posibles in mapa_nombres.items():
        col_encontrada = next((p for p in posibles if p in df.columns), None)
        if col_encontrada and estandar not in df.columns:
            df = df.rename(columns={col_encontrada: estandar})

    columnas_clave = {"deudor", "agente", "saldo", "fecha_emision", "dias_credito"}
    if not columnas_clave.issubset(df.columns):
        faltantes = columnas_clave - set(df.columns)
        st.error(f"❌ Faltan columnas esenciales para el análisis: **{', '.join(faltantes)}**.")
        st.info(f"Asegúrate de que tu archivo contenga columnas para: {', '.join(mapa_nombres.keys())}")
        return

    # --- 3. LIMPIEZA Y CÁLCULO DE VENCIMIENTO ---
    df["saldo"] = pd.to_numeric(df["saldo"], errors='coerce').fillna(0)
    df["fecha_emision"] = pd.to_datetime(df["fecha_emision"], errors='coerce')
    df["dias_credito"] = pd.to_numeric(df["dias_credito"], errors='coerce').fillna(0)
    df = df.dropna(subset=["fecha_emision"])

    # Lógica de vencimiento precisa
    hoy = datetime.now()
    df["fecha_vencimiento"] = df["fecha_emision"] + pd.to_timedelta(df["dias_credito"], unit='d')
    df["dias_vencidos"] = (hoy - df["fecha_vencimiento"]).dt.days
    
    df["estado"] = np.where(df["dias_vencidos"] > 0, "Vencida", "Corriente")

    # --- 4. KPIs GENERALES DE CARTERA ---
    st.subheader("Resumen General de la Cartera")
    
    total_cartera = df["saldo"].sum()
    cartera_vencida = df[df["estado"] == "Vencida"]["saldo"].sum()
    cartera_corriente = total_cartera - cartera_vencida
    pct_vencido = (cartera_vencida / total_cartera * 100) if total_cartera > 0 else 0

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Cartera (USD)", f"${total_cartera:,.2f}")
    col2.metric("Cartera Corriente (USD)", f"${cartera_corriente:,.2f}")
    col3.metric("Cartera Vencida (USD)", f"${cartera_vencida:,.2f}", delta=f"{pct_vencido:.1f}% Vencido", delta_color="inverse")

    # --- 5. SEMÁFORO DE SALUD DE CARTERA POR AGENTE ---
    st.subheader("🚦 Semáforo de Salud por Agente")

    resumen_agente = df.groupby("agente").agg(
        total_agente=("saldo", "sum"),
        vencido_agente=("saldo", lambda x: df.loc[x.index, "estado"].eq("Vencida").multiply(x).sum())
    ).reset_index()
    
    resumen_agente["pct_vencido"] = (resumen_agente["vencido_agente"] / resumen_agente["total_agente"] * 100).fillna(0)

    def semaforo(pct):
        if pct <= 5: return "🟢"  # Saludable
        if pct <= 15: return "🟡" # Precaución
        return "🔴" # Riesgo
    
    resumen_agente["salud"] = resumen_agente["pct_vencido"].apply(semaforo)
    resumen_agente = resumen_agente.sort_values("pct_vencido", ascending=False)

    st.dataframe(resumen_agente[["salud", "agente", "total_agente", "vencido_agente", "pct_vencido"]].style.format({
        "total_agente": "${:,.2f}",
        "vencido_agente": "${:,.2f}",
        "pct_vencido": "{:.1f}%"
    }))

    # --- 6. ANÁLISIS DE ANTIGÜEDAD DE SALDOS (AGING) ---
    st.subheader("📅 Antigüedad de Saldos Vencidos")
    
    df_vencido = df[df["estado"] == "Vencida"].copy()
    bins = [1, 30, 60, 90, 180, np.inf]
    labels = ['1-30 días', '31-60 días', '61-90 días', '91-180 días', '>180 días']
    df_vencido["rango_vencimiento"] = pd.cut(df_vencido["dias_vencidos"], bins=bins, labels=labels, right=False)

    aging_summary = df_vencido.groupby("rango_vencimiento")["saldo"].sum().reset_index()
    
    # Gráfico de Antigüedad
    chart = alt.Chart(aging_summary).mark_bar().encode(
        x=alt.X('rango_vencimiento', sort=labels, title="Rango de Vencimiento"),
        y=alt.Y('saldo', title="Saldo Vencido (USD)"),
        tooltip=[
            alt.Tooltip('rango_vencimiento', title="Rango"),
            alt.Tooltip('saldo', title="Saldo (USD)", format="$,.2f")
        ]
    ).properties(
        title="Distribución de la Cartera Vencida"
    )
    st.altair_chart(chart, use_container_width=True)

    # --- 7. DETALLE Y FILTROS ---
    st.subheader("🔍 Análisis Detallado")
    
    agentes = ["Todos"] + sorted(df["agente"].unique().tolist())
    agente_seleccionado = st.selectbox("Filtrar por Agente:", agentes)

    df_filtrado = df.copy()
    if agente_seleccionado != "Todos":
        df_filtrado = df_filtrado[df_filtrado["agente"] == agente_seleccionado]

    st.dataframe(df_filtrado[[
        "deudor", "agente", "saldo", "fecha_emision", 
        "dias_credito", "fecha_vencimiento", "dias_vencidos", "estado"
    ]].sort_values("dias_vencidos", ascending=False).style.format({
        "saldo": "${:,.2f}",
        "fecha_emision": "{:%Y-%m-%d}",
        "fecha_vencimiento": "{:%Y-%m-%d}"
    }))