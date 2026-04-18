"""
Componentes de filtrado avanzado para el dashboard Streamlit.

Proporciona widgets interactivos para filtrar datos de ventas y CxC
por múltiples criterios.
"""

import streamlit as st
import pandas as pd
from typing import Tuple, Optional, List
from datetime import datetime, timedelta


def aplicar_filtro_fechas(
    df: pd.DataFrame,
    columna_fecha: str = 'fecha',
    mostrar_widget: bool = True
) -> pd.DataFrame:
    """
    Aplica filtro de fechas al DataFrame con múltiples modos de comparación.
    
    Modos disponibles:
    - Rango de fechas: Selección directa de fecha inicio y fin
    - Periodo vs periodo: Comparación entre periodos (mensual, trimestral, anual)
    
    Args:
        df: DataFrame a filtrar
        columna_fecha: Nombre de la columna con fechas
        mostrar_widget: Si mostrar el widget en el sidebar
        
    Returns:
        DataFrame filtrado
        
    Examples:
        >>> df_filtrado = aplicar_filtro_fechas(df, 'fecha_venta')
    """
    if columna_fecha not in df.columns:
        if mostrar_widget:
            st.warning(f"⚠️ Columna '{columna_fecha}' no encontrada")
        return df
    
    # Convertir a datetime si no lo es
    if not pd.api.types.is_datetime64_any_dtype(df[columna_fecha]):
        df[columna_fecha] = pd.to_datetime(df[columna_fecha], errors='coerce')
    
    # Eliminar valores nulos
    df_con_fechas = df.dropna(subset=[columna_fecha]).copy()
    
    if df_con_fechas.empty:
        if mostrar_widget:
            st.warning("⚠️ No hay fechas válidas para filtrar")
        return df
    
    if not mostrar_widget:
        return df
    
    fecha_min = df_con_fechas[columna_fecha].min().date()
    fecha_max = df_con_fechas[columna_fecha].max().date()

    df_filtrado = df_con_fechas.copy()

    st.caption(f"📅 Disponible: {fecha_min} — {fecha_max}")

    modo_filtro = st.radio(
        "Modo",
        options=["rango_fechas", "periodo_vs_periodo"],
        format_func=lambda x: {"rango_fechas": "Rango de fechas", "periodo_vs_periodo": "Periodo vs Periodo"}[x],
        key="modo_filtro_fechas",
        horizontal=True,
    )

    if modo_filtro == "rango_fechas":
        col1, col2 = st.columns(2)
        with col1:
            fecha_inicio = st.date_input("Desde", value=fecha_min, min_value=fecha_min, max_value=fecha_max, key="filtro_fecha_inicio")
        with col2:
            fecha_fin = st.date_input("Hasta", value=fecha_max, min_value=fecha_min, max_value=fecha_max, key="filtro_fecha_fin")

        if fecha_inicio > fecha_fin:
            st.error("⚠️ Fecha inicio debe ser ≤ fecha fin")
            return df

        mask = (df_con_fechas[columna_fecha].dt.date >= fecha_inicio) & \
               (df_con_fechas[columna_fecha].dt.date <= fecha_fin)
        df_filtrado = df_con_fechas[mask].copy()
        dias = (fecha_fin - fecha_inicio).days + 1
        st.info(f"📊 {len(df_filtrado):,} registros · {dias} días")

    elif modo_filtro == "periodo_vs_periodo":
        df_con_fechas['_año'] = df_con_fechas[columna_fecha].dt.year
        df_con_fechas['_mes'] = df_con_fechas[columna_fecha].dt.month
        df_con_fechas['_trimestre'] = df_con_fechas[columna_fecha].dt.quarter
        años_disponibles = sorted(df_con_fechas['_año'].unique())

        granularidad = st.selectbox(
            "Granularidad",
            options=["mensual", "trimestral", "anual"],
            format_func=lambda x: {"mensual": "📆 Mensual", "trimestral": "📈 Trimestral", "anual": "📅 Anual"}[x],
            key="granularidad_periodo",
        )

        if granularidad == "mensual":
            meses_nombres = {1:"Enero",2:"Febrero",3:"Marzo",4:"Abril",5:"Mayo",6:"Junio",
                             7:"Julio",8:"Agosto",9:"Septiembre",10:"Octubre",11:"Noviembre",12:"Diciembre"}
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Periodo 1**")
                año_1 = st.selectbox("Año", años_disponibles, index=len(años_disponibles)-1, key="periodo1_año", label_visibility="collapsed")
                meses_año_1 = sorted(df_con_fechas[df_con_fechas['_año']==año_1]['_mes'].unique())
                mes_1 = st.selectbox("Mes", meses_año_1, format_func=lambda x: meses_nombres[x], key="periodo1_mes", label_visibility="collapsed")
            with col2:
                st.markdown("**Periodo 2**")
                año_2 = st.selectbox("Año", años_disponibles, index=max(0,len(años_disponibles)-2), key="periodo2_año", label_visibility="collapsed")
                meses_año_2 = sorted(df_con_fechas[df_con_fechas['_año']==año_2]['_mes'].unique())
                mes_2 = st.selectbox("Mes", meses_año_2, format_func=lambda x: meses_nombres[x], key="periodo2_mes", label_visibility="collapsed")
            mask = (((df_con_fechas['_año']==año_1)&(df_con_fechas['_mes']==mes_1))|
                    ((df_con_fechas['_año']==año_2)&(df_con_fechas['_mes']==mes_2)))
            df_filtrado = df_con_fechas[mask].copy()
            p1 = len(df_con_fechas[(df_con_fechas['_año']==año_1)&(df_con_fechas['_mes']==mes_1)])
            p2 = len(df_con_fechas[(df_con_fechas['_año']==año_2)&(df_con_fechas['_mes']==mes_2)])
            st.success(f"✅ {meses_nombres[mes_1]} {año_1}: {p1:,} · {meses_nombres[mes_2]} {año_2}: {p2:,}")

        elif granularidad == "trimestral":
            trimestres_nombres = {1:"Q1 (Ene-Mar)",2:"Q2 (Abr-Jun)",3:"Q3 (Jul-Sep)",4:"Q4 (Oct-Dic)"}
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Periodo 1**")
                año_1 = st.selectbox("Año", años_disponibles, index=len(años_disponibles)-1, key="periodo1_año_trim", label_visibility="collapsed")
                trims_1 = sorted(df_con_fechas[df_con_fechas['_año']==año_1]['_trimestre'].unique())
                trim_1 = st.selectbox("Trimestre", trims_1, format_func=lambda x: trimestres_nombres[x], key="periodo1_trim", label_visibility="collapsed")
            with col2:
                st.markdown("**Periodo 2**")
                año_2 = st.selectbox("Año", años_disponibles, index=max(0,len(años_disponibles)-2), key="periodo2_año_trim", label_visibility="collapsed")
                trims_2 = sorted(df_con_fechas[df_con_fechas['_año']==año_2]['_trimestre'].unique())
                trim_2 = st.selectbox("Trimestre", trims_2, format_func=lambda x: trimestres_nombres[x], key="periodo2_trim", label_visibility="collapsed")
            mask = (((df_con_fechas['_año']==año_1)&(df_con_fechas['_trimestre']==trim_1))|
                    ((df_con_fechas['_año']==año_2)&(df_con_fechas['_trimestre']==trim_2)))
            df_filtrado = df_con_fechas[mask].copy()
            p1 = len(df_con_fechas[(df_con_fechas['_año']==año_1)&(df_con_fechas['_trimestre']==trim_1)])
            p2 = len(df_con_fechas[(df_con_fechas['_año']==año_2)&(df_con_fechas['_trimestre']==trim_2)])
            st.success(f"✅ {trimestres_nombres[trim_1]} {año_1}: {p1:,} · {trimestres_nombres[trim_2]} {año_2}: {p2:,}")

        elif granularidad == "anual":
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Año 1**")
                año_1 = st.selectbox("Año 1", años_disponibles, index=len(años_disponibles)-1, key="periodo1_año_anual", label_visibility="collapsed")
            with col2:
                st.markdown("**Año 2**")
                año_2 = st.selectbox("Año 2", años_disponibles, index=max(0,len(años_disponibles)-2), key="periodo2_año_anual", label_visibility="collapsed")
            mask = (df_con_fechas['_año']==año_1)|(df_con_fechas['_año']==año_2)
            df_filtrado = df_con_fechas[mask].copy()
            p1 = len(df_con_fechas[df_con_fechas['_año']==año_1])
            p2 = len(df_con_fechas[df_con_fechas['_año']==año_2])
            st.success(f"✅ Año {año_1}: {p1:,} · Año {año_2}: {p2:,}")

        df_filtrado = df_filtrado.drop(columns=['_año', '_mes', '_trimestre'], errors='ignore')

    return df_filtrado


def aplicar_filtro_cliente(
    df: pd.DataFrame,
    columna_cliente: str = 'cliente',
    mostrar_widget: bool = True,
    max_opciones: int = 50
) -> pd.DataFrame:
    """
    Aplica filtro de selección de clientes con búsqueda intuitiva.
    
    Args:
        df: DataFrame a filtrar
        columna_cliente: Nombre de la columna con clientes
        mostrar_widget: Si mostrar el widget en el sidebar
        max_opciones: Máximo de clientes a mostrar en el selector
        
    Returns:
        DataFrame filtrado
        
    Examples:
        >>> df_filtrado = aplicar_filtro_cliente(df, 'nombre_cliente')
    """
    if columna_cliente not in df.columns:
        if mostrar_widget:
            st.warning(f"⚠️ Columna '{columna_cliente}' no encontrada")
        return df
    
    # Obtener clientes únicos y ordenarlos
    clientes_unicos = sorted([str(c) for c in df[columna_cliente].dropna().unique() if str(c).strip()])
    
    if len(clientes_unicos) == 0:
        if mostrar_widget:
            st.warning("⚠️ No hay clientes para filtrar")
        return df
    
    if not mostrar_widget:
        return df
    
    st.write(f"**Total de clientes:** {len(clientes_unicos):,}")
    
    # Campo de búsqueda intuitiva
    busqueda = st.text_input(
        "🔍 Buscar cliente (empieza a escribir)",
        key="filtro_cliente_busqueda",
        placeholder="Escribe parte del nombre del cliente...",
        help="La búsqueda filtra clientes que contengan el texto ingresado"
    )
    
    # Filtrar clientes según búsqueda
    if busqueda:
        clientes_filtrados = [c for c in clientes_unicos if busqueda.lower() in c.lower()]
        st.caption(f"✅ {len(clientes_filtrados)} cliente(s) encontrado(s)")
    else:
        clientes_filtrados = clientes_unicos[:max_opciones]  # Mostrar solo los primeros
        if len(clientes_unicos) > max_opciones:
            st.caption(f"ℹ️ Mostrando {max_opciones} de {len(clientes_unicos)} clientes. Usa la búsqueda para encontrar más.")
    
    # Selector de clientes
    clientes_seleccionados = st.multiselect(
        "Seleccionar cliente(s)",
        options=clientes_filtrados,
        default=[],
        key="filtro_cliente_select",
        help="Puedes seleccionar múltiples clientes"
    )
    
    # Aplicar filtro si hay clientes seleccionados
    if clientes_seleccionados:
        df_filtrado = df[df[columna_cliente].isin(clientes_seleccionados)].copy()
        registros_filtrados = len(df_filtrado)
        registros_totales = len(df)
        st.success(f"📊 Filtrando {registros_filtrados:,} de {registros_totales:,} registros ({len(clientes_seleccionados)} cliente(s))")
        return df_filtrado
    
    return df


def aplicar_filtro_monto(
    df: pd.DataFrame,
    columna_monto: str = 'monto',
    mostrar_widget: bool = True
) -> pd.DataFrame:
    """
    Aplica filtro de rango de montos.
    
    Args:
        df: DataFrame a filtrar
        columna_monto: Nombre de la columna con montos
        mostrar_widget: Si mostrar el widget en el sidebar
        
    Returns:
        DataFrame filtrado
        
    Examples:
        >>> df_filtrado = aplicar_filtro_monto(df, 'saldo_adeudado')
    """
    if columna_monto not in df.columns:
        if mostrar_widget:
            st.warning(f"⚠️ Columna '{columna_monto}' no encontrada")
        return df
    
    # Convertir a numérico
    df_con_montos = df.copy()
    df_con_montos[columna_monto] = pd.to_numeric(df_con_montos[columna_monto], errors='coerce')
    df_con_montos = df_con_montos.dropna(subset=[columna_monto])
    
    if df_con_montos.empty:
        if mostrar_widget:
            st.warning("⚠️ No hay montos válidos para filtrar")
        return df
    
    if mostrar_widget:
        monto_min = float(df_con_montos[columna_monto].min())
        monto_max = float(df_con_montos[columna_monto].max())
        
        # Evitar error de slider cuando min == max
        if monto_min >= monto_max:
            monto_max = monto_min + 1.0
        
        # Rangos predefinidos
        rangos_predefinidos = {
            "Todos los montos": (monto_min, monto_max),
            "Menor a $10,000": (monto_min, 10000),
            "$10,000 - $50,000": (10000, 50000),
            "$50,000 - $100,000": (50000, 100000),
            "Mayor a $100,000": (100000, monto_max)
        }
        
        tipo_filtro = st.radio(
            "Tipo de filtro",
            ["Rango personalizado", "Rangos predefinidos"],
            key="filtro_monto_tipo"
        )
        
        if tipo_filtro == "Rango personalizado":
            rango_seleccionado = st.slider(
                "Rango de monto",
                min_value=monto_min,
                max_value=monto_max,
                value=(monto_min, monto_max),
                format="$%.0f",
                key="filtro_monto_slider"
            )
            monto_inicio, monto_fin = rango_seleccionado
        else:
            rango_nombre = st.selectbox(
                "Seleccionar rango",
                options=list(rangos_predefinidos.keys()),
                key="filtro_monto_predefinido"
            )
            monto_inicio, monto_fin = rangos_predefinidos[rango_nombre]
        
        # Aplicar filtro
        mask = (df_con_montos[columna_monto] >= monto_inicio) & \
               (df_con_montos[columna_monto] <= monto_fin)
        
        df_filtrado = df_con_montos[mask]
        
        # Mostrar info
        registros_filtrados = len(df_filtrado)
        registros_totales = len(df_con_montos)
        suma_filtrada = df_filtrado[columna_monto].sum()
        
        st.caption(f"📊 {registros_filtrados:,} de {registros_totales:,} registros")
        st.caption(f"💵 Total: ${suma_filtrada:,.2f}")
        
        return df_filtrado
    
    return df


def aplicar_filtro_categoria_riesgo(
    df: pd.DataFrame,
    columna_dias: str = 'dias_overdue',
    mostrar_widget: bool = True
) -> pd.DataFrame:
    """
    Aplica filtro por categoría de riesgo basado en días de atraso.
    
    Args:
        df: DataFrame a filtrar
        columna_dias: Nombre de la columna con días de atraso
        mostrar_widget: Si mostrar el widget en el sidebar
        
    Returns:
        DataFrame filtrado
        
    Examples:
        >>> df_filtrado = aplicar_filtro_categoria_riesgo(df)
    """
    if columna_dias not in df.columns:
        if mostrar_widget:
            st.warning(f"⚠️ Columna '{columna_dias}' no encontrada")
        return df
    
    # Convertir a numérico
    df_con_dias = df.copy()
    df_con_dias[columna_dias] = pd.to_numeric(df_con_dias[columna_dias], errors='coerce')
    df_con_dias = df_con_dias.dropna(subset=[columna_dias])
    
    if df_con_dias.empty:
        if mostrar_widget:
            st.warning("⚠️ No hay días de atraso válidos")
        return df
    
    if mostrar_widget:
        st.markdown("#### ⚠️ Filtro por Riesgo")
        
        # Categorías de riesgo
        categorias = {
            "🟢 Vigente (≤0 días)": lambda x: x <= 0,
            "🟡 Bajo Riesgo (1-30 días)": lambda x: (x > 0) & (x <= 30),
            "🟠 Medio Riesgo (31-60 días)": lambda x: (x > 30) & (x <= 60),
            "🔴 Alto Riesgo (61-90 días)": lambda x: (x > 60) & (x <= 90),
            "🔴🔴 Crítico (>90 días)": lambda x: x > 90
        }
        
        categorias_seleccionadas = st.multiselect(
            "Categorías de riesgo",
            options=list(categorias.keys()),
            default=list(categorias.keys()),
            key="filtro_riesgo_select"
        )
        
        if not categorias_seleccionadas:
            st.warning("⚠️ Selecciona al menos una categoría")
            return df_con_dias
        
        # Aplicar filtros combinados
        mask_total = pd.Series([False] * len(df_con_dias), index=df_con_dias.index)
        
        for categoria in categorias_seleccionadas:
            condicion = categorias[categoria]
            mask_total |= condicion(df_con_dias[columna_dias])
        
        df_filtrado = df_con_dias[mask_total]
        
        # Mostrar estadísticas
        registros_filtrados = len(df_filtrado)
        registros_totales = len(df_con_dias)
        
        st.caption(f"📊 {registros_filtrados:,} de {registros_totales:,} registros")
        
        # Distribución por categoría seleccionada
        if len(categorias_seleccionadas) > 1:
            st.caption("**Distribución:**")
            for cat in categorias_seleccionadas:
                condicion = categorias[cat]
                count = condicion(df_filtrado[columna_dias]).sum()
                pct = (count / registros_filtrados * 100) if registros_filtrados > 0 else 0
                st.caption(f"  {cat.split()[0]} {count} ({pct:.1f}%)")
        
        return df_filtrado
    
    return df


def mostrar_resumen_filtros(
    df_original: pd.DataFrame,
    df_filtrado: pd.DataFrame,
    mostrar_widget: bool = True
) -> None:
    """
    Muestra un resumen de los filtros aplicados.
    
    Args:
        df_original: DataFrame antes de filtrar
        df_filtrado: DataFrame después de filtrar
        mostrar_widget: Si mostrar el resumen
        
    Examples:
        >>> mostrar_resumen_filtros(df_original, df_filtrado)
    """
    if not mostrar_widget:
        return
    
    total_original = len(df_original)
    total_filtrado = len(df_filtrado)
    registros_excluidos = total_original - total_filtrado
    pct_mantenido = (total_filtrado / total_original * 100) if total_original > 0 else 0
    
    st.markdown("---")
    st.markdown("### 📊 Resumen de Filtros")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric(
            "Total Original",
            f"{total_original:,}",
            delta=None
        )
    
    with col2:
        st.metric(
            "Después de Filtros",
            f"{total_filtrado:,}",
            delta=f"-{registros_excluidos:,}" if registros_excluidos > 0 else "Sin cambios"
        )
    
    # Barra de progreso visual
    st.sidebar.progress(pct_mantenido / 100)
    st.caption(f"**{pct_mantenido:.1f}%** de datos mantenidos")
    
    # Botón para limpiar filtros
    if st.sidebar.button("🔄 Limpiar todos los filtros", key="limpiar_filtros"):
        # Limpiar session state
        keys_to_clear = [k for k in st.session_state.keys() if k.startswith('filtro_')]
        for key in keys_to_clear:
            del st.session_state[key]
        st.rerun()


def render_filtros_inline(
    df: pd.DataFrame,
    filtros: list,
    ayuda: dict = {},
    columna_fecha: str = 'fecha',
    columna_cliente: str = 'cliente',
    columna_monto: str = None,
) -> pd.DataFrame:
    """
    Renderiza controles de filtro compactos integrados en la zona de contenido
    de cada vista (no en el sidebar). Devuelve el DataFrame filtrado.

    Args:
        df: DataFrame original a filtrar
        filtros: Lista con los tipos de filtro a mostrar (["fecha","cliente","monto"])
        ayuda: Diccionario con textos de ayuda por tipo de filtro
        columna_fecha: Nombre de la columna de fechas
        columna_cliente: Nombre de la columna de clientes
        columna_monto: Nombre de la columna de montos (None = omitir)
    """
    if not filtros or df is None or df.empty:
        return df

    # Determinar qué filtros aplican con los datos disponibles
    filtros_activos = []
    if "fecha" in filtros and columna_fecha in df.columns:
        filtros_activos.append("fecha")
    if "cliente" in filtros and columna_cliente in df.columns:
        filtros_activos.append("cliente")
    if "monto" in filtros and columna_monto and columna_monto in df.columns:
        filtros_activos.append("monto")

    if not filtros_activos:
        return df

    df_filtrado = df.copy()

    with st.container():
        # Proporciones: 2 por filtro + 1 para el botón limpiar
        widths = [2] * len(filtros_activos) + [1]
        cols = st.columns(widths, gap="small")
        col_idx = 0

        # ── FECHA ─────────────────────────────────────────────────────
        if "fecha" in filtros_activos:
            with cols[col_idx]:
                if not pd.api.types.is_datetime64_any_dtype(df_filtrado[columna_fecha]):
                    df_filtrado[columna_fecha] = pd.to_datetime(df_filtrado[columna_fecha], errors='coerce')
                df_f = df_filtrado.dropna(subset=[columna_fecha])
                if not df_f.empty:
                    f_min = df_f[columna_fecha].min().date()
                    f_max = df_f[columna_fecha].max().date()
                    c1, c2 = st.columns(2)
                    with c1:
                        fi = st.date_input(
                            "📅 Desde",
                            value=f_min, min_value=f_min, max_value=f_max,
                            key="inline_filtro_fecha_ini",
                            help=ayuda.get("fecha", ""),
                        )
                    with c2:
                        ff = st.date_input(
                            "📅 Hasta",
                            value=f_max, min_value=f_min, max_value=f_max,
                            key="inline_filtro_fecha_fin",
                        )
                    if fi and ff and fi <= ff:
                        mask = (
                            (df_filtrado[columna_fecha].dt.date >= fi) &
                            (df_filtrado[columna_fecha].dt.date <= ff)
                        )
                        df_filtrado = df_filtrado[mask]
            col_idx += 1

        # ── CLIENTE ───────────────────────────────────────────────────
        if "cliente" in filtros_activos:
            with cols[col_idx]:
                clientes = sorted([
                    str(c) for c in df[columna_cliente].dropna().unique()
                    if str(c).strip()
                ])
                selecc = st.multiselect(
                    "👤 Cliente",
                    options=clientes[:500],
                    key="inline_filtro_cliente",
                    placeholder="Todos los clientes",
                    help=ayuda.get("cliente", ""),
                )
                if selecc:
                    df_filtrado = df_filtrado[df_filtrado[columna_cliente].isin(selecc)]
            col_idx += 1

        # ── MONTO ─────────────────────────────────────────────────────
        if "monto" in filtros_activos:
            with cols[col_idx]:
                monto_series = pd.to_numeric(df[columna_monto], errors='coerce').dropna()
                if not monto_series.empty:
                    mn = float(monto_series.min())
                    mx = float(monto_series.max())
                    if mn >= mx:
                        mx = mn + 1.0
                    rango = st.slider(
                        "💲 Monto",
                        min_value=mn, max_value=mx, value=(mn, mx),
                        format="$%.0f",
                        key="inline_filtro_monto",
                        help=ayuda.get("monto", ""),
                    )
                    mask_m = (
                        (pd.to_numeric(df_filtrado[columna_monto], errors='coerce') >= rango[0]) &
                        (pd.to_numeric(df_filtrado[columna_monto], errors='coerce') <= rango[1])
                    )
                    df_filtrado = df_filtrado[mask_m]
            col_idx += 1

        # ── LIMPIAR ───────────────────────────────────────────────────
        with cols[-1]:
            st.write("")
            if st.button(
                "🗑️ Limpiar",
                key="inline_limpiar_filtros",
                use_container_width=True,
                help="Restablecer todos los filtros de esta vista",
            ):
                for k in list(st.session_state.keys()):
                    if k.startswith("inline_filtro_"):
                        del st.session_state[k]
                st.rerun()

        # Resumen si hay filtrado activo
        if len(df_filtrado) < len(df):
            pct = len(df_filtrado) / len(df) * 100
            st.caption(
                f"✅ **{len(df_filtrado):,}** de {len(df):,} registros ({pct:.0f}%)"
            )

        st.divider()

    return df_filtrado


if __name__ == "__main__":
    # Demo de filtros
    print("🧪 Demo de filters.py\n")
    
    # Crear datos de prueba
    df_demo = pd.DataFrame({
        'fecha': pd.date_range('2024-01-01', periods=100, freq='D'),
        'cliente': ['Cliente A', 'Cliente B', 'Cliente C'] * 33 + ['Cliente A'],
        'monto': pd.np.random.uniform(1000, 150000, 100),
        'dias_overdue': pd.np.random.randint(-10, 150, 100)
    })
    
    print(f"✅ DataFrame de prueba creado: {len(df_demo)} registros")
    print(f"   - Fechas: {df_demo['fecha'].min()} a {df_demo['fecha'].max()}")
    print(f"   - Clientes únicos: {df_demo['cliente'].nunique()}")
    print(f"   - Rango de montos: ${df_demo['monto'].min():.2f} - ${df_demo['monto'].max():.2f}")
    print(f"   - Días overdue: {df_demo['dias_overdue'].min()} a {df_demo['dias_overdue'].max()}")
    
    print("\n✅ Módulo de filtros listo para usar!")
