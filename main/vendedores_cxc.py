"""
Módulo: Vendedores + CxC
Cruza datos de ventas con cartera de cuentas por cobrar por vendedor.

Métricas clave:
- Ratio deuda vencida / ventas por vendedor
- % cartera sana vs vencida generada por cada vendedor
- Score de calidad de cartera por vendedor
- Ranking mixto: volumen de ventas vs calidad de cartera
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
from unidecode import unidecode
import re

from utils.cxc_helper import preparar_datos_cxc, calcular_dias_overdue
from utils.data_normalizer import normalizar_columnas
from utils.logger import configurar_logger

logger = configurar_logger("vendedores_cxc", nivel="INFO")


# ── Helpers internos ──────────────────────────────────────────────────────────

def _normalizar_nombre_cliente(texto: str) -> str:
    """
    Normaliza nombre de cliente para mejorar matching entre archivos.
    - Elimina acentos
    - Convierte a minúsculas
    - Elimina espacios extra y caracteres especiales
    - Trim espacios
    """
    if pd.isna(texto):
        return ""
    # Convertir a string y eliminar acentos
    texto = unidecode(str(texto))
    # Minúsculas
    texto = texto.lower()
    # Eliminar caracteres especiales (mantener solo letras, números y espacios)
    texto = re.sub(r'[^a-z0-9\s]', '', texto)
    # Eliminar espacios extra
    texto = re.sub(r'\s+', ' ', texto)
    # Trim
    texto = texto.strip()
    return texto

def _detectar_col_vendedor(df: pd.DataFrame) -> str | None:
    """Retorna el nombre de la primera columna que sea vendedor/agente/ejecutivo."""
    for col in df.columns:
        if col.lower() in ("vendedor", "agente", "ejecutivo", "seller", "rep"):
            return col
    return None


def _detectar_col_ventas(df: pd.DataFrame) -> str | None:
    """Detecta columna de ventas con búsqueda flexible."""
    # Primera pasada: búsqueda exacta
    for col in ("valor_usd", "ventas_usd", "ventas_usd_con_iva", "ventas_usd_sin_iva",
                "importe", "monto_usd", "total_usd", "venta", "monto", "total"):
        if col in df.columns:
            return col
    
    # Segunda pasada: búsqueda parcial (case insensitive)
    for col in df.columns:
        col_lower = col.lower()
        if any(keyword in col_lower for keyword in 
               ["valor", "venta", "importe", "monto", "total", "usd"]):
            # Excluir columnas que claramente no son de ventas
            if not any(excl in col_lower for excl in 
                      ["fecha", "cliente", "vendedor", "producto", "linea", "saldo", "adeudo"]):
                return col
    
    return None


def _detectar_col_cliente(df: pd.DataFrame) -> str | None:
    for col in ("cliente", "deudor", "razon_social", "nombre_cliente"):
        if col in df.columns:
            return col
    return None


def _score_calidad(pct_vigente: float, pct_1_30: float, pct_31_60: float, 
                   pct_61_90: float, pct_mas_90: float) -> tuple[float, str]:
    """
    Score 0-100 de calidad de cartera ponderado por antigüedad de deuda.
    
    Fórmula:
    - Vigente (≤0 días):   100 puntos
    - Vencida 1-30 días:    85 puntos (penalidad leve)
    - Vencida 31-60 días:   60 puntos (penalidad media)
    - Vencida 61-90 días:   30 puntos (penalidad alta)
    - Vencida >90 días:      0 puntos (penalidad máxima)
    
    Score = Σ(porcentaje × puntos) / 100
    """
    score = (
        pct_vigente * 100 +
        pct_1_30 * 85 +
        pct_31_60 * 60 +
        pct_61_90 * 30 +
        pct_mas_90 * 0
    ) / 100
    
    score = max(0.0, min(100.0, score))  # Asegurar rango 0-100
    
    if score >= 85:
        return score, "🟢 Excelente"
    elif score >= 65:
        return score, "🟡 Aceptable"
    elif score >= 40:
        return score, "🟠 Riesgo"
    else:
        return score, "🔴 Crítico"


# ── Función principal ─────────────────────────────────────────────────────────

def run():
    st.title("👥 Vendedores + CxC")
    st.caption(
        "Cruza ventas con cartera: qué vendedor genera más deuda vencida "
        "relativa a sus ventas. Útil para políticas de comisiones y límites de crédito."
    )

    # ── Validar datos disponibles ─────────────────────────────────────────────
    if "df" not in st.session_state:
        st.warning("⚠️ Carga primero un archivo de ventas en el sidebar.")
        return

    if "archivo_excel" not in st.session_state:
        st.warning("⚠️ Este módulo requiere el archivo Excel original para leer la hoja CxC.")
        return

    df_ventas = st.session_state["df"].copy()

    # Normalizar columna de ventas
    col_ventas = _detectar_col_ventas(df_ventas)
    if col_ventas and col_ventas != "valor_usd":
        logger.info(f"Columna de ventas detectada: '{col_ventas}' → renombrada a 'valor_usd'")
        df_ventas = df_ventas.rename(columns={col_ventas: "valor_usd"})
        col_ventas = "valor_usd"

    col_vendedor_v = _detectar_col_vendedor(df_ventas)
    if col_vendedor_v and col_vendedor_v != "vendedor":
        logger.info(f"Columna de vendedor detectada: '{col_vendedor_v}' → renombrada a 'vendedor'")
        df_ventas = df_ventas.rename(columns={col_vendedor_v: "vendedor"})
        col_vendedor_v = "vendedor"

    col_cliente_v = _detectar_col_cliente(df_ventas)

    if not col_ventas:
        st.error("❌ No se encontró columna de ventas (valor_usd / ventas_usd / importe).")
        st.info(f"📋 Columnas disponibles: {', '.join(df_ventas.columns.tolist())}")
        logger.error(f"No se detectó columna de ventas. Columnas disponibles: {df_ventas.columns.tolist()}")
        return

    if not col_vendedor_v:
        st.error(
            "❌ No se encontró columna de vendedor/agente en el archivo de ventas. "
            "El cruce no es posible sin esta columna."
        )
        st.info(f"📋 Columnas disponibles: {', '.join(df_ventas.columns.tolist())}")
        logger.error(f"No se detectó columna de vendedor. Columnas disponibles: {df_ventas.columns.tolist()}")
        return

    # ── Cargar CxC ────────────────────────────────────────────────────────────
    df_cxc_raw = None
    try:
        archivo_excel = st.session_state["archivo_excel"]
        hojas = pd.ExcelFile(archivo_excel).sheet_names
        hoja_cxc = next(
            (h for h in hojas if "cxc" in h.lower() or "cuenta" in h.lower()), None
        )
        if hoja_cxc:
            df_cxc_raw = normalizar_columnas(pd.read_excel(archivo_excel, sheet_name=hoja_cxc))
    except Exception as e:
        logger.exception(f"Error leyendo hoja CxC: {e}")

    if df_cxc_raw is None or df_cxc_raw.empty:
        st.error(
            "❌ No se encontró una hoja CxC en el archivo Excel. "
            "El archivo debe tener una hoja con 'cxc' o 'cuenta' en el nombre."
        )
        return

    # Normalizar saldo
    for candidato in ("saldo_adeudado", "saldo", "saldo_adeudo", "adeudo", "importe", "monto", "total"):
        if candidato in df_cxc_raw.columns:
            if candidato != "saldo_adeudado":
                df_cxc_raw = df_cxc_raw.rename(columns={candidato: "saldo_adeudado"})
            break

    if "saldo_adeudado" not in df_cxc_raw.columns:
        st.error("❌ No se encontró columna de saldo en la hoja CxC.")
        return

    saldo_txt = df_cxc_raw["saldo_adeudado"].astype(str).str.replace(",", "", regex=False).str.replace("$", "", regex=False)
    df_cxc_raw["saldo_adeudado"] = pd.to_numeric(saldo_txt, errors="coerce").fillna(0)

    col_vendedor_c = _detectar_col_vendedor(df_cxc_raw)
    col_cliente_c  = _detectar_col_cliente(df_cxc_raw)

    # Preparar CxC (calcular dias_overdue)
    _, df_np, _ = preparar_datos_cxc(df_cxc_raw)

    # ── Detectar si hay columna vendedor en CxC ───────────────────────────────
    tiene_vendedor_cxc = col_vendedor_c is not None
    tiene_cliente_comun = (col_cliente_v is not None and col_cliente_c is not None)

    if not tiene_vendedor_cxc and not tiene_cliente_comun:
        st.error(
            "❌ Para cruzar ventas con CxC se necesita al menos una de estas condiciones:\n\n"
            "1. La hoja CxC tiene columna vendedor/agente, **o**\n"
            "2. Ambas hojas tienen columna cliente (para unir por cliente → vendedor)."
        )
        return

    # ── Construir tabla de cruce ──────────────────────────────────────────────
    # Método A: CxC tiene vendedor directo
    if tiene_vendedor_cxc:
        if col_vendedor_c != "vendedor":
            df_np = df_np.rename(columns={col_vendedor_c: "vendedor"})
        df_cxc_vend = df_np.copy()

    # Método B: Unir por cliente → heredar vendedor de ventas
    else:
        # Normalizar nombres de clientes en ambos DataFrames para mejorar matching
        logger.info("Normalizando nombres de clientes para matching...")
        
        # Crear columna normalizada en ventas
        df_ventas["_cliente_norm"] = df_ventas[col_cliente_v].apply(_normalizar_nombre_cliente)
        
        # Crear columna normalizada en CxC
        if col_cliente_c != "deudor":
            df_np = df_np.rename(columns={col_cliente_c: "deudor"})
        df_np["_cliente_norm"] = df_np["deudor"].apply(_normalizar_nombre_cliente)
        
        # Mapa cliente normalizado → vendedor desde ventas
        mapa = (
            df_ventas.dropna(subset=["_cliente_norm", "vendedor"])
            .groupby("_cliente_norm")["vendedor"]
            .agg(lambda x: x.mode().iloc[0] if len(x) > 0 else None)
            .reset_index()
        )
        
        # Merge por nombre normalizado
        df_cxc_vend = df_np.merge(mapa, on="_cliente_norm", how="left")
        
        # Estadísticas de matching
        sin_vendedor = df_cxc_vend["vendedor"].isna().sum()
        total_cxc = len(df_cxc_vend)
        con_vendedor = total_cxc - sin_vendedor
        pct_match = (con_vendedor / total_cxc * 100) if total_cxc > 0 else 0
        
        logger.info(f"Matching completado: {con_vendedor}/{total_cxc} registros ({pct_match:.1f}%)")
        
        if sin_vendedor > 0:
            # Separar registros sin match para análisis
            df_sin_match = df_cxc_vend[df_cxc_vend["vendedor"].isna()].copy()
            
            # Calcular estadísticas
            monto_sin_match = df_sin_match["saldo_adeudado"].sum()
            monto_total_cxc = df_cxc_vend["saldo_adeudado"].sum()
            pct_monto_sin_match = (monto_sin_match / monto_total_cxc * 100) if monto_total_cxc > 0 else 0
            
            st.info(
                f"ℹ️ **{sin_vendedor} registros CxC no asociados** "
                f"({pct_match:.1f}% match rate) | "
                f"Monto: ${monto_sin_match:,.0f} ({pct_monto_sin_match:.1f}% del total)"
            )
            
            # Expander con detalles de registros no asociados
            with st.expander("📋 Ver detalles de registros sin vendedor asociado"):
                st.write(f"**{sin_vendedor} clientes sin historial de ventas en el archivo**")
                
                # Top 10 clientes sin match por saldo
                top_sin_match = (
                    df_sin_match.groupby("deudor")["saldo_adeudado"]
                    .sum()
                    .sort_values(ascending=False)
                    .head(10)
                    .reset_index()
                )
                top_sin_match.columns = ["Cliente", "Saldo Adeudado"]
                
                col_stats1, col_stats2 = st.columns([2, 1])
                
                with col_stats1:
                    st.write("**Top 10 Clientes (por saldo)**")
                    st.dataframe(
                        top_sin_match.style.format({"Saldo Adeudado": "${:,.0f}"}),
                        hide_index=True,
                        use_container_width=True
                    )
                
                with col_stats2:
                    st.metric("💰 Total sin asociar", f"${monto_sin_match:,.0f}")
                    st.metric("📊 % del total", f"{pct_monto_sin_match:.1f}%")
                    st.metric("👥 Clientes únicos", df_sin_match["deudor"].nunique())
                    
                    # Antigüedad promedio si existe dias_overdue
                    if "dias_overdue" in df_sin_match.columns:
                        dias_prom = df_sin_match["dias_overdue"].mean()
                        st.metric("📅 Días prom. vencido", f"{dias_prom:.0f}")
                
                # =====================================================================
                # MAPA TEMPORAL DE ADEUDOS
                # =====================================================================
                if "dias_overdue" in df_sin_match.columns:
                    st.write("---")
                    st.write("### 🗓️ Mapa Temporal de Adeudos")
                    
                    # Clasificar por rangos de antigüedad
                    def clasificar_antiguedad_detallado(dias):
                        if pd.isna(dias) or dias <= 0:
                            return "Por vencer"
                        elif dias <= 30:
                            return "1-30 días"
                        elif dias <= 60:
                            return "31-60 días"
                        elif dias <= 90:
                            return "61-90 días"
                        elif dias <= 180:
                            return "91-180 días"
                        else:
                            return ">180 días"
                    
                    df_sin_match["rango_antiguedad"] = df_sin_match["dias_overdue"].apply(
                        clasificar_antiguedad_detallado
                    )
                    
                    # Calcular distribución
                    dist_antiguedad = (
                        df_sin_match.groupby("rango_antiguedad")
                        .agg({
                            "saldo_adeudado": "sum",
                            "deudor": "count"
                        })
                        .reset_index()
                    )
                    dist_antiguedad.columns = ["Rango", "Monto", "Facturas"]
                    
                    # Ordenar por severidad
                    orden_rangos = ["Por vencer", "1-30 días", "31-60 días", "61-90 días", 
                                   "91-180 días", ">180 días"]
                    dist_antiguedad["orden"] = dist_antiguedad["Rango"].apply(
                        lambda x: orden_rangos.index(x) if x in orden_rangos else 999
                    )
                    dist_antiguedad = dist_antiguedad.sort_values("orden").drop(columns=["orden"])
                    
                    col_viz1, col_viz2 = st.columns(2)
                    
                    with col_viz1:
                        st.write("**Distribución por Antigüedad**")
                        
                        # Pie chart de distribución de monto
                        colores_rangos = {
                            "Por vencer": "#4CAF50",
                            "1-30 días": "#8BC34A",
                            "31-60 días": "#FFEB3B",
                            "61-90 días": "#FF9800",
                            "91-180 días": "#F44336",
                            ">180 días": "#B71C1C"
                        }
                        
                        colors_pie = [colores_rangos.get(r, "#999999") for r in dist_antiguedad["Rango"]]
                        
                        fig_pie_antiguedad = go.Figure(data=[go.Pie(
                            labels=dist_antiguedad["Rango"],
                            values=dist_antiguedad["Monto"],
                            marker=dict(colors=colors_pie),
                            textinfo='label+percent',
                            textposition='outside',
                            hole=0.4
                        )])
                        fig_pie_antiguedad.update_layout(
                            showlegend=True,
                            height=300,
                            margin=dict(t=20, b=20, l=20, r=20)
                        )
                        st.plotly_chart(fig_pie_antiguedad, use_container_width=True)
                    
                    with col_viz2:
                        st.write("**Monto por Rango Temporal**")
                        
                        # Gráfico de barras horizontales
                        fig_barras = px.bar(
                            dist_antiguedad,
                            y="Rango",
                            x="Monto",
                            orientation='h',
                            color="Rango",
                            color_discrete_map=colores_rangos,
                            text="Monto"
                        )
                        fig_barras.update_traces(
                            texttemplate='$%{text:,.0f}',
                            textposition='outside'
                        )
                        fig_barras.update_layout(
                            showlegend=False,
                            height=300,
                            margin=dict(t=20, b=20, l=20, r=20),
                            xaxis_title="Monto Adeudado ($)",
                            yaxis_title=""
                        )
                        st.plotly_chart(fig_barras, use_container_width=True)
                    
                    # Tabla resumen
                    st.write("**Resumen por Rango Temporal**")
                    dist_antiguedad_display = dist_antiguedad.copy()
                    dist_antiguedad_display["% Monto"] = (
                        dist_antiguedad_display["Monto"] / dist_antiguedad_display["Monto"].sum() * 100
                    )
                    st.dataframe(
                        dist_antiguedad_display[["Rango", "Facturas", "Monto", "% Monto"]].style.format({
                            "Monto": "${:,.0f}",
                            "% Monto": "{:.1f}%"
                        }),
                        hide_index=True,
                        use_container_width=True
                    )
                
                st.caption(
                    "💡 **Nota:** Estos clientes tienen deuda pero no aparecen en el archivo de ventas. "
                    "Pueden ser clientes antiguos, dados de baja, o tener nombres inconsistentes."
                )
        
        # Limpiar columna temporal
        df_cxc_vend = df_cxc_vend.drop(columns=["_cliente_norm"])

    df_cxc_vend = df_cxc_vend.dropna(subset=["vendedor"])

    if df_cxc_vend.empty:
        st.warning("⚠️ No se pudo asociar ningún registro CxC a un vendedor.")
        
        # Mostrar ejemplos de clientes para diagnóstico
        st.write("**Diagnóstico:**")
        
        col_diag1, col_diag2 = st.columns(2)
        
        with col_diag1:
            st.write("**Clientes en CxC (5 primeros):**")
            clientes_cxc = df_np["deudor"].dropna().unique()[:5].tolist()
            for c in clientes_cxc:
                st.caption(f"• {c}")
        
        with col_diag2:
            st.write("**Clientes en Ventas (5 primeros):**")
            if col_cliente_v:
                clientes_ventas = df_ventas[col_cliente_v].dropna().unique()[:5].tolist()
                for c in clientes_ventas:
                    st.caption(f"• {c}")
            else:
                st.caption("(No se detectó columna de cliente)")
        
        st.info(
            "💡 **Tip:** Los nombres de clientes deben coincidir entre archivos. "
            "Verifica que los nombres sean consistentes (mayúsculas, acentos, espacios)."
        )
        
        return

    # ── Agregar métricas por vendedor ─────────────────────────────────────────
    agg_ventas = (
        df_ventas.groupby("vendedor")
        .agg(
            ventas_totales=("valor_usd", "sum"),
            num_operaciones=("valor_usd", "count"),
        )
        .reset_index()
    )

    agg_cxc = (
        df_cxc_vend.groupby("vendedor")
        .apply(lambda g: pd.Series({
            "cartera_total":       g["saldo_adeudado"].sum(),
            "cartera_vigente":     g.loc[g["dias_overdue"] <= 0, "saldo_adeudado"].sum(),
            "cartera_vencida":     g.loc[g["dias_overdue"] > 0,  "saldo_adeudado"].sum(),
            "cartera_1_30":        g.loc[(g["dias_overdue"] > 0) & (g["dias_overdue"] <= 30), "saldo_adeudado"].sum(),
            "cartera_31_60":       g.loc[(g["dias_overdue"] > 30) & (g["dias_overdue"] <= 60), "saldo_adeudado"].sum(),
            "cartera_61_90":       g.loc[(g["dias_overdue"] > 60) & (g["dias_overdue"] <= 90), "saldo_adeudado"].sum(),
            "cartera_alto_riesgo": g.loc[g["dias_overdue"] > 90, "saldo_adeudado"].sum(),
            "clientes_unicos":     g["deudor"].nunique() if "deudor" in g.columns else 0,
            "dias_max":            g["dias_overdue"].max(),
        }))
        .reset_index()
    )

    df_cruce = agg_ventas.merge(agg_cxc, on="vendedor", how="outer").fillna(0)

    # Ratios y score
    df_cruce["ticket_promedio"] = (
        df_cruce["ventas_totales"] / df_cruce["num_operaciones"].replace(0, 1)
    )
    df_cruce["pct_vencida"] = (
        df_cruce["cartera_vencida"] / df_cruce["cartera_total"].replace(0, 1) * 100
    )
    df_cruce["pct_alto_riesgo"] = (
        df_cruce["cartera_alto_riesgo"] / df_cruce["cartera_total"].replace(0, 1) * 100
    )
    df_cruce["ratio_deuda_ventas"] = (
        df_cruce["cartera_vencida"] / df_cruce["ventas_totales"].replace(0, 1) * 100
    )
    
    # Calcular porcentajes por rango de antigüedad
    df_cruce["pct_vigente"] = (df_cruce["cartera_vigente"] / df_cruce["cartera_total"].replace(0, 1) * 100)
    df_cruce["pct_1_30"] = (df_cruce["cartera_1_30"] / df_cruce["cartera_total"].replace(0, 1) * 100)
    df_cruce["pct_31_60"] = (df_cruce["cartera_31_60"] / df_cruce["cartera_total"].replace(0, 1) * 100)
    df_cruce["pct_61_90"] = (df_cruce["cartera_61_90"] / df_cruce["cartera_total"].replace(0, 1) * 100)
    df_cruce["pct_mas_90"] = (df_cruce["cartera_alto_riesgo"] / df_cruce["cartera_total"].replace(0, 1) * 100)
    
    # Calcular score de calidad ponderado por antigüedad
    df_cruce[["score_calidad", "nivel_calidad"]] = df_cruce.apply(
        lambda row: pd.Series(_score_calidad(
            row["pct_vigente"], row["pct_1_30"], row["pct_31_60"], 
            row["pct_61_90"], row["pct_mas_90"]
        )), axis=1
    )
    df_cruce = df_cruce.sort_values("ventas_totales", ascending=False).reset_index(drop=True)

    # ── UI: Resumen general ───────────────────────────────────────────────────
    st.subheader("📊 Resumen General")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Vendedores analizados", len(df_cruce))
    col2.metric(
        "💰 Ventas Totales",
        f"${df_cruce['ventas_totales'].sum():,.0f}",
    )
    col3.metric(
        "📋 Cartera Total CxC",
        f"${df_cruce['cartera_total'].sum():,.0f}",
    )
    mejor = df_cruce.loc[df_cruce["score_calidad"].idxmax()]
    col4.metric(
        "🏆 Mejor Calidad Cartera",
        mejor["vendedor"],
        delta=f"Score {mejor['score_calidad']:.0f}/100",
    )

    # ── Tabla comparativa ─────────────────────────────────────────────────────
    st.subheader("📋 Tabla Comparativa por Vendedor")

    df_tabla = df_cruce[[
        "vendedor", "ventas_totales", "ticket_promedio", "num_operaciones",
        "cartera_total", "cartera_vencida", "pct_vencida",
        "ratio_deuda_ventas", "dias_max", "score_calidad", "nivel_calidad"
    ]].copy()

    st.dataframe(
        df_tabla,
        use_container_width=True,
        hide_index=True,
        column_config={
            "vendedor":          st.column_config.TextColumn("Vendedor",         width="medium"),
            "ventas_totales":    st.column_config.NumberColumn("Ventas ($)",      width="medium", format="$%.0f"),
            "ticket_promedio":   st.column_config.NumberColumn("Ticket Prom ($)", width="medium", format="$%.0f"),
            "num_operaciones":   st.column_config.NumberColumn("# Ops",           width="small"),
            "cartera_total":     st.column_config.NumberColumn("Cartera ($)",     width="medium", format="$%.0f"),
            "cartera_vencida":   st.column_config.NumberColumn("Vencida ($)",     width="medium", format="$%.0f"),
            "pct_vencida":       st.column_config.NumberColumn("% Vencida",       width="small",  format="%.1f%%"),
            "ratio_deuda_ventas":st.column_config.ProgressColumn(
                                    "Deuda/Ventas %", width="medium",
                                    min_value=0, max_value=100, format="%.1f%%"),
            "dias_max":          st.column_config.NumberColumn("Días Máx",        width="small"),
            "score_calidad":     st.column_config.ProgressColumn(
                                    "Score Calidad", width="medium",
                                    min_value=0, max_value=100, format="%.0f"),
            "nivel_calidad":     st.column_config.TextColumn("Nivel",            width="small"),
        },
    )

    with st.expander("ℹ️ ¿Cómo interpretar estas métricas?"):
        st.markdown("""
        | Columna | Qué mide |
        |---------|----------|
        | **Deuda/Ventas %** | Cartera vencida ÷ ventas totales. Si es alto, el vendedor cierra ventas pero no ayuda a cobrar |
        | **Score Calidad** | Score ponderado 0-100 que penaliza más la deuda antigua:<br>• Vigente = 100 pts<br>• 1-30 días = 85 pts<br>• 31-60 días = 60 pts<br>• 61-90 días = 30 pts<br>• >90 días = 0 pts |
        | **Días Máx** | La factura más vencida de los clientes de ese vendedor |
        | **% Vencida** | Del total de cartera que generó el vendedor, cuánto está vencido |

        **Señales de alerta:**
        - 🔴 Score < 40 → revisar política de crédito para ese vendedor
        - 🟠 Score 40-65 → monitorear de cerca, tiene deuda antigua
        - 🟡 Score 65-85 → aceptable, pero hay espacio de mejora
        - 🟢 Score ≥85 → excelente gestión de cartera
        - Deuda/Ventas > 20% → el vendedor puede estar aceptando malos pagadores para cerrar ventas
        """)

    # ── Gráfico: Ventas vs % Vencida (bubble = cartera total) ────────────────
    st.subheader("📈 Ventas vs Calidad de Cartera")

    fig_scatter = px.scatter(
        df_cruce,
        x="ventas_totales",
        y="pct_vencida",
        size="cartera_total",
        color="nivel_calidad",
        hover_name="vendedor",
        color_discrete_map={
            "🟢 Excelente": "#4CAF50",
            "🟡 Aceptable": "#FFEB3B",
            "🟠 Riesgo":    "#FF9800",
            "🔴 Crítico":   "#F44336",
        },
        labels={
            "ventas_totales": "Ventas Totales ($)",
            "pct_vencida":    "% Cartera Vencida",
            "cartera_total":  "Cartera Total ($)",
            "nivel_calidad":  "Calidad",
        },
        title="Cuadrante: Volumen de Ventas vs Calidad de Cartera",
    )

    # Línea de referencia: media de % vencida
    media_pct = df_cruce["pct_vencida"].mean()
    fig_scatter.add_hline(
        y=media_pct, line_dash="dash", line_color="gray",
        annotation_text=f"Promedio {media_pct:.1f}%", annotation_position="top right",
    )
    fig_scatter.update_layout(height=440, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig_scatter, use_container_width=True)

    st.caption(
        "💡 Ideal: esquina inferior derecha (muchas ventas, baja cartera vencida). "
        "Riesgo: esquina superior derecha (muchas ventas + mucha cartera vencida)."
    )

    # ── Gráfico: Score de calidad ranking ────────────────────────────────────
    st.subheader("🏅 Ranking de Calidad de Cartera")

    df_rank = df_cruce.sort_values("score_calidad", ascending=True)
    colores_rank = df_rank["nivel_calidad"].map({
        "🟢 Excelente": "#4CAF50",
        "🟡 Aceptable": "#FFEB3B",
        "🟠 Riesgo":    "#FF9800",
        "🔴 Crítico":   "#F44336",
    }).fillna("#9E9E9E")

    fig_rank = go.Figure(go.Bar(
        x=df_rank["score_calidad"],
        y=df_rank["vendedor"],
        orientation="h",
        marker_color=colores_rank,
        text=df_rank["score_calidad"].apply(lambda s: f"{s:.0f}/100"),
        textposition="outside",
        hovertemplate="%{y}<br>Score: %{x:.0f}<br>% Vencida: " +
                      df_rank["pct_vencida"].apply(lambda p: f"{p:.1f}%").values + "<extra></extra>",
    ))
    fig_rank.update_layout(
        title="Score de Calidad de Cartera por Vendedor (mayor = mejor)",
        xaxis=dict(range=[0, 115], title="Score (0–100)"),
        yaxis_title="",
        height=max(350, len(df_rank) * 45),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig_rank, use_container_width=True)

    # ── Gráfico: Composición de cartera por vendedor (stacked bar) ───────────
    st.subheader("📊 Composición de Cartera por Vendedor")

    df_stack = df_cruce.sort_values("cartera_total", ascending=False).head(15)

    fig_stack = go.Figure()
    fig_stack.add_trace(go.Bar(
        name="Vigente",
        x=df_stack["vendedor"],
        y=df_stack["cartera_vigente"],
        marker_color="#4CAF50",
        hovertemplate="%{x}<br>Vigente: $%{y:,.0f}<extra></extra>",
    ))
    fig_stack.add_trace(go.Bar(
        name="Vencida (no crítica)",
        x=df_stack["vendedor"],
        y=df_stack["cartera_vencida"] - df_stack["cartera_alto_riesgo"],
        marker_color="#FF9800",
        hovertemplate="%{x}<br>Vencida: $%{y:,.0f}<extra></extra>",
    ))
    fig_stack.add_trace(go.Bar(
        name=">90 días (alto riesgo)",
        x=df_stack["vendedor"],
        y=df_stack["cartera_alto_riesgo"],
        marker_color="#F44336",
        hovertemplate="%{x}<br>Alto riesgo: $%{y:,.0f}<extra></extra>",
    ))
    fig_stack.update_layout(
        barmode="stack",
        title="Composición de Cartera por Vendedor (Top 15)",
        xaxis_title="",
        yaxis_title="Saldo ($)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=420,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig_stack, use_container_width=True)

    # ── Alertas automáticas ───────────────────────────────────────────────────
    st.subheader("🚨 Alertas de Vendedores")

    alertas_vend = []
    for _, row in df_cruce.iterrows():
        if row["pct_vencida"] > 40:
            alertas_vend.append(
                f"🔴 **{row['vendedor']}**: {row['pct_vencida']:.1f}% de su cartera está vencida "
                f"(${row['cartera_vencida']:,.0f})"
            )
        elif row["ratio_deuda_ventas"] > 20:
            alertas_vend.append(
                f"🟠 **{row['vendedor']}**: ratio deuda/ventas de {row['ratio_deuda_ventas']:.1f}% "
                f"— posible aceptación de clientes de alto riesgo"
            )
        elif row["dias_max"] > 120:
            alertas_vend.append(
                f"🟡 **{row['vendedor']}**: factura más vencida con {row['dias_max']:.0f} días — "
                "revisar cliente específico"
            )

    if alertas_vend:
        for a in alertas_vend:
            st.markdown(a)
    else:
        st.success("✅ Todos los vendedores tienen indicadores dentro de rangos normales.")

    # ── Descarga CSV ──────────────────────────────────────────────────────────
    st.write("---")
    csv_bytes = df_cruce.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇️ Descargar tabla completa (.csv)",
        data=csv_bytes,
        file_name=f"vendedores_cxc_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv",
    )
