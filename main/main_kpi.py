import io

import streamlit as st
import pandas as pd
import altair as alt
import plotly.express as px
from utils.ai_helper_premium import generar_insights_kpi_vendedores
from utils.constantes import COLUMNAS_VENTAS
from utils.filters_helper import obtener_lineas_filtradas, generar_contexto_filtros
from utils.logger import configurar_logger
from utils.auth import get_current_user

logger = configurar_logger("main_kpi", nivel="INFO")


def _detectar_columna(df, candidatos):
    for col in df.columns:
        if col.lower() in candidatos:
            return col
    return None


def _detectar_columna_existente(df, candidatos):
    return next((col for col in candidatos if col in df.columns), None)


def _normalizar_columna_ventas(df):
    if "valor_mxn" in df.columns:
        df["valor_mxn"] = pd.to_numeric(df["valor_mxn"], errors="coerce").fillna(0)
        return df, "valor_mxn"

    col_ventas = _detectar_columna_existente(df, COLUMNAS_VENTAS)
    if not col_ventas:
        return df, None

    if col_ventas != "valor_mxn":
        logger.info(f"Columna de ventas detectada: '{col_ventas}' → renombrada a 'valor_mxn'")
        df = df.rename(columns={col_ventas: "valor_mxn"})

    df["valor_mxn"] = pd.to_numeric(df["valor_mxn"], errors="coerce").fillna(0)
    return df, "valor_mxn"


def _dataframe_to_excel_bytes(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="ranking")
    return output.getvalue()

def run(habilitar_ia=False, openai_api_key=None):
    st.title("📈 Desempeño Comercial")

    if "df" not in st.session_state:
        st.warning("Primero debes cargar un archivo CSV o Excel en el menú lateral.")
        return

    df = st.session_state["df"].copy()

    df, col_ventas = _normalizar_columna_ventas(df)

    if not col_ventas:
        st.error(
            "No se encontró una columna de ventas válida. "
            "Se aceptan aliases como valor_mxn, ventas_usd, ventas_usd_con_iva, "
            "importe, monto_usd, total_usd, valor o venta."
        )
        st.info(f"Columnas disponibles: {', '.join(df.columns.tolist())}")
        return

    df["anio"] = pd.to_datetime(df["fecha"], errors="coerce").dt.year

    total_usd_base = df["valor_mxn"].sum()
    total_operaciones_base = len(df)

    # === Filtros opcionales ===
    st.subheader("Filtros del análisis")

    columna_agente = _detectar_columna(df, {"agente", "vendedor", "ejecutivo"})
    columna_linea = _detectar_columna_existente(df, ["linea_de_negocio", "linea_producto"])
    columna_cliente = _detectar_columna_existente(df, ["cliente", "receptor_nombre", "razon_social"])

    if columna_agente:
        df["agente"] = df[columna_agente]  # Ya normalizado en app.py
        agentes = sorted(df["agente"].dropna().unique())
        agente_sel = st.selectbox("Selecciona Ejecutivo:", ["Todos"] + agentes)

        if agente_sel != "Todos":
            df = df[df["agente"] == agente_sel]
    else:
        st.warning("⚠️ No se encontró columna 'agente', 'vendedor' o 'ejecutivo'.")

    # Filtro adicional: línea de negocio o producto
    if columna_linea:
        lineas = sorted(df[columna_linea].dropna().astype(str).unique())
        linea_sel = st.selectbox("Selecciona Línea (opcional):", ["Todas"] + list(lineas))
    else:
        linea_sel = "Todas"

    if linea_sel != "Todas" and columna_linea:
        df = df[df[columna_linea].astype(str) == linea_sel]

    # Filtro adicional: forma de pago
    _FORMA_PAGO_LABELS = {
        "01": "Efectivo", "02": "Cheque nominativo", "03": "Transferencia electrónica",
        "04": "Tarjeta de crédito", "05": "Monedero electrónico", "06": "Dinero electrónico",
        "08": "Vales de despensa", "12": "Dación en pago", "13": "Pago por subrogación",
        "14": "Pago por consignación", "15": "Condonación", "17": "Compensación",
        "23": "Novación", "24": "Confusión", "25": "Remisión de deuda",
        "26": "Prescripción o caducidad", "27": "A satisfacción del acreedor",
        "28": "Tarjeta de débito", "29": "Tarjeta de servicios",
        "30": "Aplicación de anticipos", "31": "Intermediario pagos",
        "99": "Por definir",
    }
    forma_pago_sel = "Todas"
    if "forma_pago" in df.columns:
        fps = sorted(df["forma_pago"].dropna().astype(str).unique())
        fps_labels = [f"{fp} – {_FORMA_PAGO_LABELS.get(fp, fp)}" for fp in fps]
        fp_sel_label = st.selectbox(
            "Forma de pago (opcional):", ["Todas"] + fps_labels
        )
        if fp_sel_label != "Todas":
            forma_pago_sel = fp_sel_label.split(" – ")[0]
            df = df[df["forma_pago"].astype(str) == forma_pago_sel]

    st.caption(
        f"Contexto activo: Ejecutivo = {agente_sel if columna_agente else 'No disponible'} | "
        f"Línea = {linea_sel} | Forma de pago = {forma_pago_sel}"
    )

    # KPIs del contexto filtrado
    st.subheader("KPIs del contexto")
    total_filtrado_usd = df["valor_mxn"].sum()
    operaciones_filtradas = len(df)
    ticket_promedio = total_filtrado_usd / operaciones_filtradas if operaciones_filtradas > 0 else 0
    vendedores_activos = df["agente"].nunique() if "agente" in df.columns else 0
    clientes_unicos = df[columna_cliente].nunique() if columna_cliente else 0
    operaciones_promedio_vendedor = (
        operaciones_filtradas / vendedores_activos
        if vendedores_activos > 0 else 0
    )

    colf1, colf2, colf3, colf4 = st.columns(4)
    colf1.metric(
        "💰 Ventas USD",
        f"${total_filtrado_usd:,.2f}",
        delta=f"{(total_filtrado_usd / total_usd_base * 100):.1f}% del total" if total_usd_base > 0 else None,
        help="📐 Total de ventas después de aplicar filtros"
    )
    colf2.metric(
        "📦 Operaciones",
        f"{operaciones_filtradas:,}",
        delta=(
            f"{operaciones_promedio_vendedor:,.0f} prom./vendedor"
            if vendedores_activos > 0 else None
        ),
        help="📐 Número total de transacciones que cumplen los filtros"
    )
    colf3.metric(
        "💳 Ticket Prom./Operación",
        f"${ticket_promedio:,.2f}",
        help="📐 Promedio ponderado del contexto: ventas totales / operaciones"
    )
    if columna_cliente:
        colf4.metric(
            "👥 Clientes Únicos",
            f"{clientes_unicos:,}",
            help="📐 Clientes distintos dentro del contexto filtrado"
        )
    else:
        colf4.metric(
            "👤 Vendedores Activos",
            f"{vendedores_activos:,}",
            help="📐 Vendedores con actividad dentro del contexto filtrado"
        )

    with st.expander("📋 Ver detalle de ventas filtradas", expanded=False):
        st.dataframe(df.sort_values("fecha", ascending=False).head(50), use_container_width=True)

    # Ranking de vendedores
    if "agente" in df.columns and df["agente"].nunique() > 1:
        st.subheader("🏆 Ranking de Vendedores")

        # =====================================================================
        # KPIs DE EFICIENCIA POR VENDEDOR
        # =====================================================================
        # Calcular métricas de eficiencia
        vendedores_eficiencia = []
        
        for agente in df["agente"].unique():
            agente_data = df[df["agente"] == agente]
            
            total_ventas = agente_data["valor_mxn"].sum()
            operaciones_count = len(agente_data)
            
            # Ticket promedio (ventas por operación)
            ticket_promedio = total_ventas / operaciones_count if operaciones_count > 0 else 0
            
            # Clientes únicos (si existe columna cliente)
            if 'cliente' in agente_data.columns:
                clientes_unicos = agente_data['cliente'].nunique()
                ventas_por_cliente = total_ventas / clientes_unicos if clientes_unicos > 0 else 0
            else:
                clientes_unicos = 0
                ventas_por_cliente = 0
            
            vendedores_eficiencia.append({
                'agente': agente,
                'total_ventas': total_ventas,
                'operaciones': operaciones_count,
                'ticket_promedio': ticket_promedio,
                'clientes_unicos': clientes_unicos,
                'ventas_por_cliente': ventas_por_cliente
            })
        
        df_eficiencia_ventas = pd.DataFrame(vendedores_eficiencia)

        mediana_ops = df_eficiencia_ventas['operaciones'].median()
        mediana_ticket = df_eficiencia_ventas['ticket_promedio'].median()

        def clasificar_vendedor(row):
            if row['operaciones'] > mediana_ops and row['ticket_promedio'] > mediana_ticket:
                return "🌟 Elite"
            elif row['operaciones'] > mediana_ops:
                return "📊 Alto Volumen"
            elif row['ticket_promedio'] > mediana_ticket:
                return "💎 Alto Ticket"
            else:
                return "🔄 En Desarrollo"

        df_eficiencia_ventas['clasificacion'] = df_eficiencia_ventas.apply(clasificar_vendedor, axis=1)

        criterio_labels = {
            "total_ventas": "Ventas Totales",
            "operaciones": "Operaciones",
            "ticket_promedio": "Ticket Promedio",
            "ventas_por_cliente": "Venta por Cliente",
        }
        criterio_ranking = st.selectbox(
            "Ordenar ranking por:",
            options=list(criterio_labels.keys()),
            format_func=lambda key: criterio_labels[key],
            key="ranking_criterio_kpi",
        )

        ranking_df = (
            df_eficiencia_ventas
            .sort_values(criterio_ranking, ascending=False)
            .reset_index(drop=True)
            .copy()
        )
        ranking_df.insert(0, "ranking", range(1, len(ranking_df) + 1))

        podio = ranking_df.head(3)
        podio_cols = st.columns(3)
        medallas = ["🥇", "🥈", "🥉"]
        for idx, (_, row) in enumerate(podio.iterrows()):
            with podio_cols[idx]:
                cont = st.container(border=True)
                cont.markdown(f"### {medallas[idx]} {row['agente']}")
                cont.metric("Ventas", f"${row['total_ventas']:,.0f}")
                cont.caption(
                    f"Ops: {int(row['operaciones'])} | Ticket: ${row['ticket_promedio']:,.0f} | "
                    f"Clientes: {int(row['clientes_unicos']) if row['clientes_unicos'] > 0 else 0}"
                )
                cont.caption(row['clasificacion'])

        ranking_export = ranking_df[[
            "ranking", "agente", "total_ventas", "operaciones", "ticket_promedio",
            "clientes_unicos", "ventas_por_cliente", "clasificacion"
        ]].copy()
        ranking_export.columns = [
            "Ranking", "Vendedor", "Ventas Totales", "Operaciones", "Ticket Promedio",
            "Clientes", "Venta por Cliente", "Clasificacion"
        ]

        col_descarga_1, col_descarga_2 = st.columns(2)
        with col_descarga_1:
            st.download_button(
                "Descargar ranking CSV",
                data=ranking_export.to_csv(index=False).encode("utf-8-sig"),
                file_name="ranking_vendedores.csv",
                mime="text/csv",
                use_container_width=True,
            )
        with col_descarga_2:
            st.download_button(
                "Descargar ranking Excel",
                data=_dataframe_to_excel_bytes(ranking_export),
                file_name="ranking_vendedores.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

        ranking_display = ranking_export.copy()
        ranking_display["Medalla"] = ranking_display["Ranking"].map({1: "🥇", 2: "🥈", 3: "🥉"}).fillna("")
        ranking_display = ranking_display[[
            "Ranking", "Medalla", "Vendedor", "Ventas Totales", "Operaciones",
            "Ticket Promedio", "Clientes", "Venta por Cliente", "Clasificacion"
        ]]
        ranking_styler = (
            ranking_display.style
            .format({
                "Ranking": "{:,.0f}",
                "Ventas Totales": "${:,.0f}",
                "Operaciones": "{:,.0f}",
                "Ticket Promedio": "${:,.2f}",
                "Clientes": "{:,.0f}",
                "Venta por Cliente": "${:,.2f}",
            })
            .bar(subset=["Ventas Totales", "Operaciones"], color="#ff4b4b")
        )
        st.markdown(
            ranking_styler.hide(axis="index").to_html(),
            unsafe_allow_html=True,
        )

        st.subheader("⚡ KPIs de Eficiencia por Vendedor")
        st.caption(
            "Estos indicadores comparan vendedores entre sí. "
            "No equivalen al ticket promedio por operación mostrado arriba."
        )
        
        # Mostrar métricas principales
        col_ef1, col_ef2, col_ef3, col_ef4 = st.columns(4)
        
        mejor_ticket = df_eficiencia_ventas.loc[df_eficiencia_ventas['ticket_promedio'].idxmax()]
        mayor_volumen = df_eficiencia_ventas.loc[df_eficiencia_ventas['operaciones'].idxmax()]
        
        col_ef1.metric("💰 Mejor Ticket por Vendedor", 
                      f"${mejor_ticket['ticket_promedio']:,.2f}",
                      delta=mejor_ticket['agente'])
        col_ef2.metric("📊 Mayor Volumen de Ops", 
                      f"{mayor_volumen['operaciones']:,.0f}",
                      delta=mayor_volumen['agente'])
        col_ef3.metric("💵 Ticket Prom. por Vendedor", 
                      f"${df_eficiencia_ventas['ticket_promedio'].mean():,.2f}")
        col_ef4.metric("👤 Vendedores Evaluados", 
                      f"{len(df_eficiencia_ventas):,.0f}")
        
        # Matriz de Eficiencia vs Volumen
        st.write("### 📈 Matriz de Eficiencia vs Volumen")
        
        fig_matriz = px.scatter(
            df_eficiencia_ventas,
            x='operaciones',
            y='ticket_promedio',
            size='total_ventas',
            color='clasificacion',
            hover_name='agente',
            labels={
                'operaciones': 'Número de Operaciones',
                'ticket_promedio': 'Ticket Promedio (USD)',
                'total_ventas': 'Ventas Totales',
                'clasificacion': 'Clasificación'
            },
            title='Análisis de Vendedores: Eficiencia vs Volumen'
        )
        
        # Añadir líneas de referencia (medianas)
        fig_matriz.add_hline(y=mediana_ticket, line_dash="dash", line_color="gray", 
                            annotation_text="Mediana Ticket")
        fig_matriz.add_vline(x=mediana_ops, line_dash="dash", line_color="gray",
                            annotation_text="Mediana Ops")
        
        fig_matriz.update_layout(height=500)
        st.plotly_chart(fig_matriz, width='stretch')
        
        # Resumen ejecutivo por cuadrantes
        st.write("### 🧭 Mapa de Cuadrantes")
        q1, q2, q3, q4 = st.columns(4)
        q1.metric("🌟 Elite", f"{(df_eficiencia_ventas['clasificacion'] == '🌟 Elite').sum()}")
        q2.metric("📊 Alto Volumen", f"{(df_eficiencia_ventas['clasificacion'] == '📊 Alto Volumen').sum()}")
        q3.metric("💎 Alto Ticket", f"{(df_eficiencia_ventas['clasificacion'] == '💎 Alto Ticket').sum()}")
        q4.metric("🔄 En Desarrollo", f"{(df_eficiencia_ventas['clasificacion'] == '🔄 En Desarrollo').sum()}")
        
        # Insights y recomendaciones
        st.write("### 💡 Insights y Recomendaciones")
        
        elite = df_eficiencia_ventas[df_eficiencia_ventas['clasificacion'].str.contains('Elite')]
        alto_vol = df_eficiencia_ventas[df_eficiencia_ventas['clasificacion'].str.contains('Alto Volumen') & 
                                       ~df_eficiencia_ventas['clasificacion'].str.contains('Elite')]
        alta_ef = df_eficiencia_ventas[df_eficiencia_ventas['clasificacion'].str.contains('Alto Ticket')]
        en_desarrollo = df_eficiencia_ventas[df_eficiencia_ventas['clasificacion'].str.contains('Desarrollo')]
        
        col_ins1, col_ins2 = st.columns(2)
        
        with col_ins1:
            if len(elite) > 0:
                st.success(f"🌟 **Vendedores Elite ({len(elite)})**")
                st.write("Mantienen alto volumen y alta eficiencia:")
                for _, v in elite.iterrows():
                    st.write(f"- {v['agente']}: ${v['total_ventas']:,.2f} ({v['operaciones']} ops)")
            
            if len(alto_vol) > 0:
                st.info(f"📊 **Alto Volumen ({len(alto_vol)})**")
                st.write("Oportunidad: Mejorar ticket promedio")
                for _, v in alto_vol.head(3).iterrows():
                    st.write(f"- {v['agente']}: {v['operaciones']} ops, ticket ${v['ticket_promedio']:,.2f}")
        
        with col_ins2:
            if len(alta_ef) > 0:
                st.info(f"💎 **Alta Eficiencia ({len(alta_ef)})**")
                st.write("Oportunidad: Aumentar volumen de operaciones")
                for _, v in alta_ef.head(3).iterrows():
                    st.write(f"- {v['agente']}: Ticket ${v['ticket_promedio']:,.2f}, {v['operaciones']} ops")
            
            if len(en_desarrollo) > 0:
                st.warning(f"🔄 **En Desarrollo ({len(en_desarrollo)})**")
                st.write("Requieren capacitación y seguimiento:")
                for _, v in en_desarrollo.head(3).iterrows():
                    st.write(f"- {v['agente']}: ${v['total_ventas']:,.2f} total")
        
        st.write("---")
    elif "agente" in df.columns and df["agente"].nunique() == 1:
        st.info("El contexto filtrado deja un solo vendedor; se omite el ranking comparativo.")

    # Gráficos por agente
    if "agente" in df.columns and not df.empty:
        st.subheader("📊 Visualización de Ventas por Vendedor")

        chart_type = st.selectbox(
            "Selecciona tipo de gráfico:",
            ["Pie Chart", "Barras Horizontales", "Ventas por Año"]
        )

        df_chart = df[["agente", "anio", "valor_mxn"]].dropna()

        # Agrupación base para todos los gráficos
        resumen_agente = (
            df_chart.groupby(["agente", "anio"])
            .agg(
                total_ventas=("valor_mxn", "sum"),
                operaciones=("valor_mxn", "count")
            )
            .reset_index()
        )
        resumen_agente["ventas_moneda"] = resumen_agente["total_ventas"].apply(lambda x: f"${x:,.2f}")

        if chart_type == "Pie Chart":
            pie_data = (
                resumen_agente.groupby("agente")
                .agg(
                    total_ventas=("total_ventas", "sum"),
                    operaciones=("operaciones", "sum")
                )
                .reset_index()
                .sort_values("total_ventas", ascending=False)
            )
            pie_data["ventas_moneda"] = pie_data["total_ventas"].apply(lambda x: f"${x:,.2f}")
            pie_data["pct_ventas"] = pie_data["total_ventas"] / pie_data["total_ventas"].sum()
            pie_data["etiqueta_visible"] = pie_data.apply(
                lambda row: f"{row['agente']}<br>{row['pct_ventas']:.1%}"
                if row["pct_ventas"] >= 0.02 else "",
                axis=1,
            )

            chart = px.pie(
                pie_data,
                names="agente",
                values="total_ventas",
                title="Participación de Vendedores (USD)",
                custom_data=["ventas_moneda", "operaciones", "pct_ventas", "etiqueta_visible"],
                hole=0.35,
            )
            chart.update_traces(
                pull=[0.03] * len(pie_data),
                domain=dict(x=[0.0, 0.68], y=[0.02, 0.98]),
                textposition="outside",
                texttemplate="%{customdata[3]}",
                textfont_size=14,
                hovertemplate=(
                    "<b>%{label}</b><br>"
                    "Ventas: %{customdata[0]}<br>"
                    "Operaciones: %{customdata[1]:,.0f}<br>"
                    "Participación: %{customdata[2]:.1%}<extra></extra>"
                )
            )
            chart.update_layout(
                showlegend=False,
                height=680,
                margin=dict(t=70, b=40, l=70, r=140),
                uniformtext_minsize=13,
                uniformtext_mode="hide",
            )

            tabla_pct_html = (
                pie_data[["agente", "ventas_moneda", "pct_ventas"]]
                .rename(columns={
                    "agente": "Vendedor",
                    "ventas_moneda": "Ventas",
                    "pct_ventas": "% Ventas",
                })
                .assign(**{"% Ventas": lambda df_tmp: df_tmp["% Ventas"].map(lambda v: f"{v:.1%}")})
                .to_html(index=False, escape=False, classes="pie-summary-table", justify="center")
            )
            tabla_pct_bloque_html = f"""
            <div style=\"height: 680px; display: flex; align-items: center; justify-content: center;\">
                <div style=\"width: 100%; max-width: 360px;\">
                    <h4 style=\"text-align: center; margin: 0 0 16px 0;\">% de ventas</h4>
                    <style>
                        .pie-summary-table {{
                            margin: 0 auto;
                            border-collapse: collapse;
                        }}
                        .pie-summary-table th,
                        .pie-summary-table td {{
                            text-align: center;
                            vertical-align: middle;
                        }}
                    </style>
                    <div style=\"display: flex; justify-content: center; text-align: center;\">{tabla_pct_html}</div>
                </div>
            </div>
            """

        elif chart_type == "Barras Horizontales":
            bar_data = (
                resumen_agente.groupby("agente")
                .agg(
                    total_ventas=("total_ventas", "sum"),
                    operaciones=("operaciones", "sum")
                )
                .reset_index()
                .sort_values("total_ventas", ascending=True)
            )
            bar_data["ventas_moneda"] = bar_data["total_ventas"].apply(lambda x: f"${x:,.2f}")

            chart = alt.Chart(bar_data).mark_bar().encode(
                x="total_ventas:Q",
                y=alt.Y("agente:N", sort="-x"),
                tooltip=["agente:N", "ventas_moneda:N", "operaciones:Q"]
            ).properties(title="Ventas Totales por Vendedor (USD)")

        elif chart_type == "Ventas por Año":
            resumen_agente["anio"] = resumen_agente["anio"].astype(str)
            chart = alt.Chart(resumen_agente).mark_bar().encode(
                x=alt.X("anio:N", title="Año"),
                y=alt.Y("total_ventas:Q", title="Ventas USD"),
                color="agente:N",
                tooltip=["anio:N", "agente:N", "ventas_moneda:N", "operaciones:Q"]
            ).properties(title="Ventas por Vendedor en el Tiempo")

        if chart_type == "Pie Chart":
            col_chart, col_tabla = st.columns([2.4, 1])
            with col_chart:
                st.plotly_chart(chart, width='stretch')
            with col_tabla:
                st.markdown(tabla_pct_bloque_html, unsafe_allow_html=True)
        else:
            st.altair_chart(chart, width='stretch')    
    st.markdown("---")
    
    # =====================================================================
    # ANÁLISIS PREMIUM CON IA - INSIGHTS ESTRATÉGICOS DE EQUIPO DE VENTAS
    # =====================================================================
    # Verificar que el usuario tenga permisos para usar IA
    user = get_current_user()
    puede_usar_ia = user and user.can_use_ai()
    
    if habilitar_ia and openai_api_key and puede_usar_ia:
        st.header("🤖 Insights Estratégicos Premium - Equipo de Ventas")
        
        # Obtener filtros configurados
        periodo_seleccionado = st.session_state.get("analisis_periodo", "Todos los datos")
        lineas_seleccionadas = st.session_state.get("analisis_lineas", ["Todas"])
        
        st.info(
            f"📋 **Configuración:** Periodo: {periodo_seleccionado} | "
            f"Líneas: {', '.join(lineas_seleccionadas[:3])}{'...' if len(lineas_seleccionadas) > 3 else ''}"
        )
        
        # Botón para ejecutar análisis
        if st.button("🚀 Generar Análisis con IA", type="primary", use_container_width=True, key="btn_ia_kpi"):
            with st.spinner("🔄 Analizando patrones del equipo con IA..."):
                try:
                    # Aplicar filtro de líneas de negocio si existe
                    df_analisis = df.copy()
                    
                    # Filtrar líneas específicas
                    lineas_filtrar = obtener_lineas_filtradas(lineas_seleccionadas)
                    
                    if lineas_filtrar:
                        if "linea_de_negocio" in df_analisis.columns:
                            df_analisis = df_analisis[df_analisis['linea_de_negocio'].isin(lineas_filtrar)]
                        elif "linea_producto" in df_analisis.columns:
                            df_analisis = df_analisis[df_analisis['linea_producto'].isin(lineas_filtrar)]
                    
                    # Preparar datos para el análisis con datos filtrados
                    df_chart_filtrado = df_analisis[["agente", "anio", "valor_mxn"]].dropna()
                    
                    resumen_agente_filtrado = (
                        df_chart_filtrado.groupby(["agente", "anio"])
                        .agg(
                            total_ventas=("valor_mxn", "sum"),
                            operaciones=("valor_mxn", "count")
                        )
                        .reset_index()
                    )
                    
                    # Agrupar por agente (sin año) para tener totales por vendedor
                    resumen_por_vendedor = (
                        resumen_agente_filtrado.groupby("agente")
                        .agg(
                            total_ventas=("total_ventas", "sum"),
                            operaciones=("operaciones", "sum")
                        )
                        .reset_index()
                    )
                    # Calcular ticket promedio por vendedor
                    resumen_por_vendedor["ticket_promedio"] = (
                        resumen_por_vendedor["total_ventas"] / resumen_por_vendedor["operaciones"]
                    ).fillna(0)
                    
                    num_vendedores = len(resumen_por_vendedor)
                    total_operaciones_equipo = resumen_por_vendedor["operaciones"].sum()
                    total_ventas_equipo = resumen_por_vendedor["total_ventas"].sum()
                    ticket_promedio_general = (
                        total_ventas_equipo / total_operaciones_equipo if total_operaciones_equipo > 0 else 0
                    )
                    
                    # Señal útil para IA: porcentaje del equipo con ticket arriba del promedio general
                    eficiencia_general = (
                        (resumen_por_vendedor["ticket_promedio"] >= ticket_promedio_general).mean() * 100
                        if num_vendedores > 0 and ticket_promedio_general > 0 else 0
                    )
                    
                    # Top y bottom performers
                    sorted_vendedores = resumen_por_vendedor.sort_values("total_ventas", ascending=False)
                    vendedor_top = sorted_vendedores.iloc[0]["agente"]
                    ventas_vendedor_top = sorted_vendedores.iloc[0]["total_ventas"]
                    vendedor_bottom = sorted_vendedores.iloc[-1]["agente"]
                    ventas_vendedor_bottom = sorted_vendedores.iloc[-1]["total_ventas"]
                    
                    # Concentración top 3
                    top3_ventas = sorted_vendedores.head(3)["total_ventas"].sum()
                    total_ventas = resumen_por_vendedor["total_ventas"].sum()
                    concentracion_top3_pct = (top3_ventas / total_ventas * 100) if total_ventas > 0 else 0
                    
                    # Preparar lista de vendedores
                    datos_vendedores = []
                    for _, row in sorted_vendedores.head(10).iterrows():
                        datos_vendedores.append({
                            'nombre': row['agente'],
                            'ventas': row['total_ventas'],
                            'ticket_avg': row['ticket_promedio']
                        })
                    
                    # Preparar contexto de filtros para IA
                    contexto_filtros = generar_contexto_filtros(lineas_filtrar)
                    
                    # Generar insights con IA
                    insights = generar_insights_kpi_vendedores(
                        num_vendedores=num_vendedores,
                        ticket_promedio_general=ticket_promedio_general,
                        eficiencia_general=eficiencia_general,
                        vendedor_top=vendedor_top,
                        ventas_vendedor_top=ventas_vendedor_top,
                        vendedor_bottom=vendedor_bottom,
                        ventas_vendedor_bottom=ventas_vendedor_bottom,
                        concentracion_top3_pct=concentracion_top3_pct,
                        api_key=openai_api_key,
                        datos_vendedores=datos_vendedores,
                        contexto_filtros=contexto_filtros
                    )
                    
                    if insights:
                        # Insight principal
                        st.info(f"💡 **{insights.get('insight_clave', 'No disponible')}**")
                        
                        # Columnas para organizar insights
                        col_izq, col_der = st.columns(2)
                        
                        with col_izq:
                            st.markdown("### 👥 Recomendaciones de Equipo")
                            recomendaciones = insights.get('recomendaciones_equipos', [])
                            if recomendaciones:
                                for rec in recomendaciones:
                                    st.markdown(f"- {rec}")
                            else:
                                st.caption("No disponible")
                            
                            st.markdown("")
                            
                            st.markdown("### 🎯 Oportunidades de Mejora")
                            oportunidades = insights.get('oportunidades_mejora', [])
                            if oportunidades:
                                for opp in oportunidades:
                                    st.markdown(f"- {opp}")
                            else:
                                st.caption("No disponible")
                        
                        with col_der:
                            st.markdown("### ⚠️ Alertas Estratégicas")
                            alertas = insights.get('alertas_estrategicas', [])
                            if alertas:
                                for alerta in alertas:
                                    st.markdown(f"- {alerta}")
                            else:
                                st.caption("No hay alertas críticas")
                        
                        st.caption("🤖 Análisis generado por OpenAI GPT-4o-mini")
                    else:
                        st.warning("⚠️ No se pudo generar el análisis de IA")
                
                except Exception as e:
                    st.error(f"❌ Error al generar insights de IA: {str(e)}")
                    logger.error(f"Error en análisis de IA vendedores: {e}", exc_info=True)
        else:
            st.caption("👆 Presiona el botón para generar insights estratégicos según tus filtros")
        
        st.markdown("---")
    elif habilitar_ia and openai_api_key and not puede_usar_ia:
        st.warning("⚠️ Esta función está disponible solo para usuarios con rol **Analyst** o **Admin**")
        st.info("💡 Contacta al administrador para solicitar acceso a análisis con IA")
    
    # =====================================================================
    # PANEL DE DEFINICIONES Y FÓRMULAS
    # =====================================================================
    with st.expander("📐 **Definiciones y Fórmulas de KPIs**"):
        st.markdown("""
        ### 📊 KPIs del Contexto
        
        **💰 Ventas USD**
        - **Definición**: Suma de las ventas dentro del contexto filtrado actual
        - **Fórmula**: `Σ valor_mxn (con filtros activos)`
        - **Fuente**: Columna `ventas_usd`, `ventas_usd_con_iva` o `valor_usd`
        
        **📦 Operaciones**
        - **Definición**: Número de transacciones/facturas dentro del contexto filtrado
        - **Fórmula**: `COUNT(registros filtrados)`
        - **Nota**: Cada fila = 1 operación
        
        **💳 Ticket Promedio**
        - **Definición**: Valor promedio por operación dentro del contexto activo
        - **Fórmula**: `Ventas USD / Operaciones`
        - **Uso**: Detectar calidad del ingreso, no solo volumen

        **👥 Clientes Únicos / 👤 Vendedores Activos**
        - **Definición**: Cuarta métrica contextual según la disponibilidad de columnas
        - **Uso**: Medir cobertura comercial del subconjunto analizado
        
        ---
        
        ### ⚡ Métricas de Eficiencia por Vendedor
        
        **💵 Ticket Promedio**
        - **Definición**: Valor promedio de cada transacción
        - **Fórmula**: `Total Ventas USD / Número de Operaciones`
        - **Interpretación**: Mayor ticket = Ventas de mayor valor unitario
        - **Ejemplo**: $100,000 en 10 ops = $10,000 de ticket promedio
        
        **📊 Total Ventas**
        - **Definición**: Suma acumulada de ventas del vendedor
        - **Fórmula**: `Σ ventas_usd (por agente)`
        
        **🔢 Operaciones**
        - **Definición**: Cantidad de transacciones generadas
        - **Fórmula**: `COUNT(ventas por agente)`
        
        ---
        
        ### 🎯 Clasificación de Vendedores
        
        Los vendedores se clasifican en 4 cuadrantes según su desempeño:
        
        **🏆 Alto Volumen (Alto Ticket)**
        - **Criterios**: 
          - Ticket promedio ≥ Mediana general
          - Total de operaciones ≥ Mediana general
        - **Perfil**: Vendedores élite - cierran grandes ventas con frecuencia
        - **Estrategia**: Retener, reconocer, replicar best practices
        
        **📈 Alto Volumen (Bajo Ticket)**
        - **Criterios**:
          - Ticket promedio < Mediana general
          - Total de operaciones ≥ Mediana general
        - **Perfil**: Generadores de volumen - muchas ventas pequeñas
        - **Oportunidad**: Capacitación en upselling/cross-selling para aumentar ticket
        
        **💎 Alto Ticket (Eficiencia)**
        - **Criterios**:
          - Ticket promedio ≥ Mediana general
          - Total de operaciones < Mediana general
        - **Perfil**: Especialistas - cierran deals grandes ocasionalmente
        - **Oportunidad**: Aumentar frecuencia/volumen de operaciones
        - **Nota**: Antes llamado "Alta Eficiencia" (se renombró por claridad)
        
        **🔄 En Desarrollo**
        - **Criterios**:
          - Ticket promedio < Mediana general
          - Total de operaciones < Mediana general
        - **Perfil**: Vendedores junior o con bajo desempeño
        - **Acción**: Capacitación intensiva, seguimiento cercano, planes de mejora
        
        ---
        
        ### 📈 Visualizaciones
        
        **Pie Chart (Gráfico de Pastel)**
        - Muestra participación porcentual de cada vendedor en ventas totales
        - Útil para identificar distribución de contribución
        
        **Barras Horizontales**
        - Compara ventas absolutas entre vendedores
        - Ordenado de mayor a menor
        
        **Ventas por Año**
        - Evolución temporal de ventas por vendedor
        - Útil para identificar tendencias y estacionalidad
        
        ---
        
        ### 🏅 Ranking de Vendedores
        
        **Criterio**: Ordenado por Total Ventas USD (descendente)
        - **Ranking #1**: Vendedor con mayor monto acumulado
        - **Columnas**:
          - Total USD: Suma de ventas
          - Operaciones: Cantidad de transacciones
        
        ---
        
        ### 📝 Notas Importantes
        
        - **Columna de agente**: Se detecta automáticamente como `agente`, `vendedor` o `ejecutivo`
        - **Filtros**: Aplicables por ejecutivo y por `linea_de_negocio` o `linea_producto`
        - **Años**: Se extrae automáticamente de la columna `fecha`
        - **Mediana vs Promedio**: Se usa mediana para evitar distorsión por outliers
        """)