
import streamlit as st
import pandas as pd
import altair as alt


def run(df, año_base=None):
    st.title("Comparativo de Ventas (USD)")

    # --- 1. PREPARACIÓN Y VALIDACIÓN DEL DATAFRAME ---
    df.columns = df.columns.str.lower().str.strip()

    # Estandarizar columna de ventas a 'valor_usd'
    columna_ventas = st.session_state.get("columna_ventas", "valor_usd")
    if columna_ventas not in df.columns:
        st.error(f"La columna de ventas '{columna_ventas}' no se encontró en los datos.")
        return
    
    # Estandarizar columna de año a 'ano'
    if "ano" not in df.columns:
        if "año" in df.columns:
            df = df.rename(columns={"año": "ano"})
        elif "fecha" in df.columns:
            df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
            df["ano"] = df["fecha"].dt.year
            df["mes"] = df["fecha"].dt.month
        else:
            st.error("No se encontró una columna de año ('ano', 'año') o 'fecha' para el análisis.")
            return

    if "mes" not in df.columns and "fecha" in df.columns:
        df["mes"] = pd.to_datetime(df["fecha"], errors="coerce").dt.month

    df[columna_ventas] = pd.to_numeric(df[columna_ventas], errors="coerce").fillna(0)
    df["ano"] = pd.to_numeric(df["ano"], errors="coerce").dropna()
    df["mes"] = pd.to_numeric(df["mes"], errors="coerce").dropna()

    # --- 2. TABLA PIVOTE DE VENTAS POR MES Y AÑO ---
    st.subheader("Ventas Mensuales por Año (USD)")
    
    pivot_ventas = df.groupby(["ano", "mes"])[columna_ventas].sum().unstack(fill_value=0)
    
    # Asegurar que todos los meses (1-12) existan
    for mes in range(1, 13):
        if mes not in pivot_ventas.columns:
            pivot_ventas[mes] = 0
    pivot_ventas = pivot_ventas[sorted(pivot_ventas.columns)]

    # Formatear tabla para visualización
    st.dataframe(pivot_ventas.style.format("${:,.2f}"))

    # --- 3. GRÁFICO DE EVOLUCIÓN ANUAL ---
    st.subheader("Evolución de Ventas Anuales (USD)")
    
    df_chart = pivot_ventas.reset_index().melt(id_vars="ano", var_name="mes", value_name="ventas")
    df_chart["tooltip_ventas"] = df_chart["ventas"].apply(lambda x: f"${x:,.2f}")

    chart = alt.Chart(df_chart).mark_line(point=True).encode(
        x=alt.X("mes:O", title="Mes"),
        y=alt.Y("ventas:Q", title="Ventas (USD)"),
        color="ano:N",
        tooltip=["ano:N", "mes:O", "tooltip_ventas:N"]
    ).properties(
        title="Ventas Mensuales por Año"
    )
    st.altair_chart(chart, use_container_width=True)

    # --- 4. COMPARATIVO AÑO VS AÑO ---
    st.subheader("Comparativo Año vs Año (USD)")

    años_disponibles = sorted(pivot_ventas.index.unique().astype(int))
    
    if len(años_disponibles) >= 2:
        # Selección de años a comparar
        col1, col2 = st.columns(2)
        año_actual = año_base if año_base in años_disponibles else años_disponibles[-1]
        año_anterior = años_disponibles[años_disponibles.index(año_actual) - 1] if año_actual > años_disponibles[0] else años_disponibles[0]
        
        año_1 = col1.selectbox("Selecciona el Año Base", años_disponibles, index=años_disponibles.index(año_anterior))
        año_2 = col2.selectbox("Selecciona el Año a Comparar", años_disponibles, index=años_disponibles.index(año_actual))

        if año_1 != año_2:
            ventas_y1 = pivot_ventas.loc[año_1]
            ventas_y2 = pivot_ventas.loc[año_2]

            comparativo = pd.DataFrame({
                f"Ventas {año_1}": ventas_y1,
                f"Ventas {año_2}": ventas_y2
            })
            comparativo["Diferencia Absoluta"] = comparativo[f"Ventas {año_2}"] - comparativo[f"Ventas {año_1}"]
            comparativo["Variación %"] = (comparativo["Diferencia Absoluta"] / comparativo[f"Ventas {año_1}"].replace(0, pd.NA)) * 100

            # Formatear tabla comparativa
            st.dataframe(comparativo.style.format({
                f"Ventas {año_1}": "${:,.2f}",
                f"Ventas {año_2}": "${:,.2f}",
                "Diferencia Absoluta": "${:,.2f}",
                "Variación %": "{:.2f}%"
            }))

            # Gráfico comparativo
            df_comp_chart = comparativo[[f"Ventas {año_1}", f"Ventas {año_2}"]].reset_index().melt(id_vars="mes", var_name="Año", value_name="Ventas")
            df_comp_chart["tooltip_ventas"] = df_comp_chart["Ventas"].apply(lambda x: f"${x:,.2f}")

            chart_comp = alt.Chart(df_comp_chart).mark_line(point=True).encode(
                x=alt.X("mes:O", title="Mes"),
                y=alt.Y("Ventas:Q", title="Ventas (USD)"),
                color="Año:N",
                tooltip=["Año:N", "mes:O", "tooltip_ventas:N"]
            ).properties(
                title=f"Comparativo de Ventas: {año_1} vs {año_2}"
            )
            st.altair_chart(chart_comp, use_container_width=True)
        else:
            st.warning("Selecciona dos años diferentes para poder comparar.")
    else:
        st.info("Se necesitan datos de al menos dos años para realizar una comparación.")
