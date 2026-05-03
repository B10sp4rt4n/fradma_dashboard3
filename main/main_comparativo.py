
import io

import altair as alt
import pandas as pd
import streamlit as st


MESES = {
    1: "Ene", 2: "Feb", 3: "Mar", 4: "Abr", 5: "May", 6: "Jun",
    7: "Jul", 8: "Ago", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dic",
}
ORDEN_MESES = list(MESES.values())


def _dataframe_to_excel_bytes(sheets):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for sheet_name, frame in sheets.items():
            frame.to_excel(writer, index=False, sheet_name=sheet_name[:31])
    return output.getvalue()


def _normalizar_df(df):
    df = df.copy()
    df.columns = df.columns.str.lower().str.strip()

    for col_anio in ["aã±o", "aÃ±o", "ano", "anio"]:
        if col_anio in df.columns and "año" not in df.columns:
            df = df.rename(columns={col_anio: "año"})

    if "valor_usd" not in df.columns:
        if "valor usd" in df.columns:
            df = df.rename(columns={"valor usd": "valor_usd"})
        elif "ventas_usd" in df.columns:
            df = df.rename(columns={"ventas_usd": "valor_usd"})
        elif "importe" in df.columns:
            df = df.rename(columns={"importe": "valor_usd"})

    if "valor_usd" not in df.columns:
        return None

    if "fecha" in df.columns and ("año" not in df.columns or "mes" not in df.columns):
        df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
        df["año"] = df["fecha"].dt.year
        df["mes"] = df["fecha"].dt.month

    if "año" not in df.columns or "mes" not in df.columns:
        return None

    df["valor_usd"] = pd.to_numeric(df["valor_usd"], errors="coerce").fillna(0)
    df = df.dropna(subset=["año", "mes"]).copy()
    df["año"] = df["año"].astype(int)
    df["mes"] = df["mes"].astype(int)
    return df


def _construir_historico(pivot_ventas):
    tabla = pivot_ventas.pivot(index="año", columns="mes", values="valor_usd").fillna(0)
    for mes in range(1, 13):
        if mes not in tabla.columns:
            tabla[mes] = 0
    tabla = tabla[sorted(tabla.columns)]
    tabla.columns = [MESES[m] for m in tabla.columns]
    return tabla.sort_index(ascending=False)


def _ultimo_mes_con_datos(pivot_ventas, anio):
    meses = pivot_ventas.loc[pivot_ventas["año"] == anio, "mes"]
    return int(meses.max()) if not meses.empty else 0


def _construir_comparativo(pivot_ventas, anio_base, anio_comp, modo):
    serie_base = pivot_ventas[pivot_ventas["año"] == anio_base].set_index("mes")["valor_usd"]
    serie_comp = pivot_ventas[pivot_ventas["año"] == anio_comp].set_index("mes")["valor_usd"]

    ultimo_base = _ultimo_mes_con_datos(pivot_ventas, anio_base)
    ultimo_comp = _ultimo_mes_con_datos(pivot_ventas, anio_comp)
    ultimo_comparable = min(ultimo_base, ultimo_comp)

    if modo == "YTD":
        meses = list(range(1, ultimo_comparable + 1)) if ultimo_comparable > 0 else []
    else:
        meses = list(range(1, 13))

    comparativo = pd.DataFrame({
        f"{anio_base}": serie_base,
        f"{anio_comp}": serie_comp,
    }).reindex(meses).fillna(0)

    comparativo[f"{anio_base}"] = pd.to_numeric(comparativo[f"{anio_base}"], errors="coerce").fillna(0)
    comparativo[f"{anio_comp}"] = pd.to_numeric(comparativo[f"{anio_comp}"], errors="coerce").fillna(0)
    comparativo["Diferencia"] = comparativo[f"{anio_comp}"] - comparativo[f"{anio_base}"]

    denom = comparativo[f"{anio_base}"].where(comparativo[f"{anio_base}"] != 0)
    comparativo["% Variación"] = ((comparativo["Diferencia"] / denom) * 100).round(2)
    comparativo["Mes"] = [MESES[m] for m in comparativo.index]
    comparativo["Resultado"] = comparativo["Diferencia"].apply(
        lambda x: "🟢 Favorable" if x > 0 else ("🔴 Desfavorable" if x < 0 else "⚪ Sin cambio")
    )
    return comparativo.reset_index(names="Mes_num"), ultimo_comparable


def _crear_chart_anual(df_chart):
    return alt.Chart(df_chart).mark_line(point=True).encode(
        x=alt.X("mes:O", title="Mes", sort=ORDEN_MESES),
        y=alt.Y("valor_usd:Q", title="Ventas USD"),
        color=alt.Color("año:N", title="Año"),
        tooltip=["año", "mes", alt.Tooltip("valor_usd:Q", format=",.2f")],
    ).properties(height=380)


def _crear_chart_comparativo(comparativo_chart):
    return alt.Chart(comparativo_chart).mark_line(point=True).encode(
        x=alt.X("Mes:O", title="Mes", sort=ORDEN_MESES),
        y=alt.Y("Ventas USD:Q", title="Ventas USD"),
        color=alt.Color("Año:N", title="Serie"),
        tooltip=["Mes", "Año", alt.Tooltip("Ventas USD:Q", format=",.2f")],
    ).properties(height=380)


def _crear_chart_diferencia(comparativo):
    return alt.Chart(comparativo).mark_bar().encode(
        x=alt.X("Mes:O", title="Mes", sort=ORDEN_MESES),
        y=alt.Y("Diferencia:Q", title="Diferencia USD"),
        color=alt.condition("datum.Diferencia >= 0", alt.value("#2E7D32"), alt.value("#C62828")),
        tooltip=["Mes", alt.Tooltip("Diferencia:Q", format=",.2f"), alt.Tooltip("% Variación:Q", format=",.2f")],
    ).properties(height=320)


def _crear_heatmap_historico(df_heatmap):
    return alt.Chart(df_heatmap).mark_rect().encode(
        x=alt.X("Mes:O", title="Mes", sort=ORDEN_MESES),
        y=alt.Y("Año:O", title="Año", sort="descending"),
        color=alt.Color("Ventas USD:Q", title="Ventas USD", scale=alt.Scale(scheme="blues")),
        tooltip=["Año", "Mes", alt.Tooltip("Ventas USD:Q", format=",.2f")],
    ).properties(height=320)


def _crear_chart_totales_anuales(resumen_anual):
    return alt.Chart(resumen_anual).mark_bar().encode(
        x=alt.X("Año:O", title="Año", sort="descending"),
        y=alt.Y("Ventas Totales:Q", title="Ventas Totales USD"),
        color=alt.Color("Año:O", legend=None),
        tooltip=["Año", alt.Tooltip("Ventas Totales:Q", format=",.2f"), "Operaciones", alt.Tooltip("Ticket Promedio:Q", format=",.2f")],
    ).properties(height=320)


def _crear_chart_acumulado_historico(df_acumulado):
    return alt.Chart(df_acumulado).mark_line(point=True).encode(
        x=alt.X("Mes:O", title="Mes", sort=ORDEN_MESES),
        y=alt.Y("Ventas Acumuladas:Q", title="Ventas Acumuladas USD"),
        color=alt.Color("Año:N", title="Año"),
        tooltip=["Año", "Mes", alt.Tooltip("Ventas Acumuladas:Q", format=",.2f")],
    ).properties(height=360)


def run(df, año_base=None):
    st.title("📊 Comparativo Año vs Año")

    df = _normalizar_df(df)
    if df is None:
        st.error("No se pudieron identificar las columnas necesarias: valor_usd, año y mes/fecha.")
        return

    pivot_ventas = df.groupby(["año", "mes"], as_index=False)["valor_usd"].sum()
    historico = _construir_historico(pivot_ventas)
    df_chart = historico.reset_index().melt(id_vars="año", var_name="mes", value_name="valor_usd")

    anios_disponibles = sorted(df["año"].dropna().unique(), reverse=True)
    if len(anios_disponibles) < 2:
        st.info("Se necesitan al menos dos años para comparar.")
        return

    default_index_1 = anios_disponibles.index(año_base) if año_base in anios_disponibles else 1 if len(anios_disponibles) > 1 else 0
    default_index_2 = 0 if anios_disponibles[0] != anios_disponibles[default_index_1] else 1

    ctrl1, ctrl2, ctrl3 = st.columns([1, 1, 1])
    with ctrl1:
        anio_1 = st.selectbox("Año base", anios_disponibles, index=default_index_1)
    opciones_anio_2 = [anio for anio in anios_disponibles if anio != anio_1]
    with ctrl2:
        anio_2 = st.selectbox("Año comparación", opciones_anio_2, index=min(default_index_2, len(opciones_anio_2) - 1))
    with ctrl3:
        modo = st.radio("Modo comparativo", ["Completo", "YTD"], horizontal=True)

    comparativo, ultimo_comparable = _construir_comparativo(pivot_ventas, anio_1, anio_2, modo)
    if comparativo.empty:
        st.warning("No hay meses comparables suficientes para construir el análisis.")
        return

    total_anio_1 = comparativo[str(anio_1)].sum()
    total_anio_2 = comparativo[str(anio_2)].sum()
    total_diff = total_anio_2 - total_anio_1
    total_pct = (total_diff / total_anio_1 * 100) if total_anio_1 else None
    meses_favorables = int((comparativo["Diferencia"] > 0).sum())
    meses_desfavorables = int((comparativo["Diferencia"] < 0).sum())

    tab_resumen, tab_detalle, tab_hallazgos, tab_descargas, tab_historico = st.tabs([
        "Resumen Ejecutivo", "Detalle Mensual", "Hallazgos", "Descargas", "Panorama Histórico"
    ])

    with tab_resumen:
        k1, k2, k3, k4 = st.columns(4)
        k1.metric(f"Ventas {anio_1}", f"${total_anio_1:,.0f}")
        k2.metric(f"Ventas {anio_2}", f"${total_anio_2:,.0f}", delta=f"${total_diff:,.0f}")
        k3.metric("Variación Total", f"{total_pct:.1f}%" if total_pct is not None else "N/A")
        k4.metric("Meses Favorables", f"{meses_favorables}", delta=f"{meses_desfavorables} desfavorables")

        if modo == "YTD":
            st.info(f"Comparativo YTD activo: ambos años se comparan hasta {MESES.get(ultimo_comparable, 'N/D')}.")
        else:
            st.info("Comparativo de año completo: se muestran los 12 meses de cada año.")

        resumen_texto = (
            f"{anio_2} {'supera' if total_diff >= 0 else 'queda por debajo de'} {anio_1} por "
            f"${abs(total_diff):,.0f} ({abs(total_pct):.1f}%{' de crecimiento' if total_diff >= 0 else ' de caída'})"
            if total_pct is not None else
            f"{anio_2} registra ${total_anio_2:,.0f} frente a ${total_anio_1:,.0f} de {anio_1}."
        )
        st.success(f"Resumen ejecutivo: {resumen_texto}.")

        comparativo_chart = pd.concat([
            comparativo[["Mes", str(anio_1)]].rename(columns={str(anio_1): "Ventas USD"}).assign(Año=str(anio_1)),
            comparativo[["Mes", str(anio_2)]].rename(columns={str(anio_2): "Ventas USD"}).assign(Año=str(anio_2)),
        ], ignore_index=True)

        st.subheader("Tendencia año vs año")
        st.altair_chart(_crear_chart_comparativo(comparativo_chart), width='stretch')

        st.subheader("Diferencia mensual")
        st.altair_chart(_crear_chart_diferencia(comparativo), width='stretch')

    with tab_detalle:
        st.subheader("Histórico mensual por año")
        st.dataframe(historico.style.format("${:,.2f}"), width='stretch')

        st.subheader("Detalle mensual del comparativo")
        st.dataframe(
            comparativo[["Mes", str(anio_1), str(anio_2), "Diferencia", "% Variación", "Resultado"]],
            use_container_width=True,
            hide_index=True,
            column_config={
                "Mes": st.column_config.TextColumn("Mes", width="small"),
                str(anio_1): st.column_config.NumberColumn(str(anio_1), format="$%.2f"),
                str(anio_2): st.column_config.NumberColumn(str(anio_2), format="$%.2f"),
                "Diferencia": st.column_config.NumberColumn("Diferencia", format="$%.2f"),
                "% Variación": st.column_config.NumberColumn("% Variación", format="%.2f%%"),
                "Resultado": st.column_config.TextColumn("Lectura", width="medium"),
            },
        )

        st.subheader("Evolución histórica por año")
        st.altair_chart(_crear_chart_anual(df_chart), width='stretch')

    with tab_hallazgos:
        ganadores = comparativo.sort_values("Diferencia", ascending=False).head(3)
        perdedores = comparativo.sort_values("Diferencia", ascending=True).head(3)
        mes_top_anio_1 = comparativo.loc[comparativo[str(anio_1)].idxmax(), "Mes"]
        mes_top_anio_2 = comparativo.loc[comparativo[str(anio_2)].idxmax(), "Mes"]

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("### 🟢 Meses que impulsan el resultado")
            for _, row in ganadores.iterrows():
                st.write(
                    f"- {row['Mes']}: ${row['Diferencia']:,.0f} "
                    f"({row['% Variación'] if pd.notna(row['% Variación']) else 0:.1f}%)"
                )

            st.markdown("")
            st.markdown(f"**Pico de {anio_1}:** {mes_top_anio_1}")

        with c2:
            st.markdown("### 🔴 Meses que deterioran el resultado")
            for _, row in perdedores.iterrows():
                st.write(
                    f"- {row['Mes']}: ${row['Diferencia']:,.0f} "
                    f"({row['% Variación'] if pd.notna(row['% Variación']) else 0:.1f}%)"
                )

            st.markdown("")
            st.markdown(f"**Pico de {anio_2}:** {mes_top_anio_2}")

        st.markdown("### 🧠 Lectura rápida")
        if total_diff >= 0:
            st.success(
                f"El año {anio_2} muestra una trayectoria superior a {anio_1}, con {meses_favorables} meses favorables "
                f"y una ganancia acumulada de ${total_diff:,.0f}."
            )
        else:
            st.warning(
                f"El año {anio_2} queda por debajo de {anio_1}, con {meses_desfavorables} meses en retroceso "
                f"y una caída acumulada de ${abs(total_diff):,.0f}."
            )

    with tab_descargas:
        comparativo_export = comparativo[["Mes", str(anio_1), str(anio_2), "Diferencia", "% Variación", "Resultado"]].copy()
        historico_export = historico.reset_index()

        d1, d2 = st.columns(2)
        with d1:
            st.download_button(
                "Descargar comparativo CSV",
                data=comparativo_export.to_csv(index=False).encode("utf-8-sig"),
                file_name=f"comparativo_{anio_1}_vs_{anio_2}_{modo.lower()}.csv",
                mime="text/csv",
                use_container_width=True,
            )
        with d2:
            st.download_button(
                "Descargar comparativo Excel",
                data=_dataframe_to_excel_bytes({
                    "comparativo": comparativo_export,
                    "historico": historico_export,
                }),
                file_name=f"comparativo_{anio_1}_vs_{anio_2}_{modo.lower()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

    with tab_historico:
        st.subheader("Panorama histórico de todos los años")

        df_heatmap = df.groupby(["año", "mes"], as_index=False)["valor_usd"].sum()
        df_heatmap["Mes"] = df_heatmap["mes"].map(MESES)
        df_heatmap["Año"] = df_heatmap["año"].astype(str)
        df_heatmap = df_heatmap.rename(columns={"valor_usd": "Ventas USD"})

        vista_historica = st.radio(
            "Vista histórica principal",
            ["Heatmap mensual", "Línea acumulada por año"],
            horizontal=True,
        )

        df_acumulado = df.groupby(["año", "mes"], as_index=False)["valor_usd"].sum().sort_values(["año", "mes"])
        df_acumulado["Ventas Acumuladas"] = df_acumulado.groupby("año")["valor_usd"].cumsum()
        df_acumulado["Mes"] = df_acumulado["mes"].map(MESES)
        df_acumulado["Año"] = df_acumulado["año"].astype(str)

        col_hist_1, col_hist_2 = st.columns([1.2, 1])
        with col_hist_1:
            if vista_historica == "Heatmap mensual":
                st.markdown("### 🗓️ Heatmap mensual por año")
                st.altair_chart(_crear_heatmap_historico(df_heatmap), width='stretch')
            else:
                st.markdown("### 📈 Carrera acumulada por año")
                st.altair_chart(_crear_chart_acumulado_historico(df_acumulado), width='stretch')

        resumen_anual = (
            df.groupby("año", as_index=False)
            .agg(
                ventas_totales=("valor_usd", "sum"),
                operaciones=("valor_usd", "count"),
            )
            .sort_values("año", ascending=False)
        )
        resumen_anual["ticket_promedio"] = resumen_anual["ventas_totales"] / resumen_anual["operaciones"]
        resumen_anual["variacion_vs_prev"] = resumen_anual["ventas_totales"].pct_change(periods=-1) * 100
        resumen_anual_chart = resumen_anual.rename(columns={
            "año": "Año",
            "ventas_totales": "Ventas Totales",
            "operaciones": "Operaciones",
            "ticket_promedio": "Ticket Promedio",
        })

        with col_hist_2:
            st.markdown("### 📊 Total anual")
            st.altair_chart(_crear_chart_totales_anuales(resumen_anual_chart), width='stretch')

        mejor_anio = resumen_anual_chart.loc[resumen_anual_chart["Ventas Totales"].idxmax(), "Año"]
        peor_anio = resumen_anual_chart.loc[resumen_anual_chart["Ventas Totales"].idxmin(), "Año"]
        ranking_final = resumen_anual_chart.sort_values("Ventas Totales", ascending=False).reset_index(drop=True).copy()
        ranking_final.insert(0, "Posición", range(1, len(ranking_final) + 1))

        h1, h2, h3 = st.columns(3)
        h1.metric("🏆 Mejor Año", str(mejor_anio))
        h2.metric("📉 Año más Débil", str(peor_anio))
        h3.metric("📚 Años Analizados", f"{resumen_anual_chart['Año'].nunique()}")

        if vista_historica == "Línea acumulada por año":
            st.markdown("### 🥇 Llegada final por año")
            st.dataframe(
                ranking_final[["Posición", "Año", "Ventas Totales", "Operaciones", "Ticket Promedio"]],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Posición": st.column_config.NumberColumn("#", format="%d"),
                    "Año": st.column_config.NumberColumn("Año", format="%d"),
                    "Ventas Totales": st.column_config.ProgressColumn(
                        "Ventas Totales",
                        format="$%.0f",
                        min_value=0,
                        max_value=float(ranking_final["Ventas Totales"].max()) if not ranking_final.empty else 0,
                    ),
                    "Operaciones": st.column_config.NumberColumn("Operaciones", format="%d"),
                    "Ticket Promedio": st.column_config.NumberColumn("Ticket Promedio", format="$%.2f"),
                },
            )

        st.markdown("### 📋 Resumen anual")
        st.dataframe(
            resumen_anual_chart[["Año", "Ventas Totales", "Operaciones", "Ticket Promedio", "variacion_vs_prev"]],
            use_container_width=True,
            hide_index=True,
            column_config={
                "Año": st.column_config.NumberColumn("Año", format="%d"),
                "Ventas Totales": st.column_config.NumberColumn("Ventas Totales", format="$%.2f"),
                "Operaciones": st.column_config.NumberColumn("Operaciones", format="%d"),
                "Ticket Promedio": st.column_config.NumberColumn("Ticket Promedio", format="$%.2f"),
                "variacion_vs_prev": st.column_config.NumberColumn("% vs Año Previo", format="%.2f%%"),
            },
        )
