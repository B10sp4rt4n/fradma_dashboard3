"""
Módulo: Herramientas Financieras
Autor: Dashboard Fradma
Fecha: Febrero 2026

Funcionalidad:
- Conversor de monedas en tiempo real
- Calculadora de descuento por pronto pago
- Calculadora DSO (Days Sales Outstanding)
- Otras calculadoras financieras de uso frecuente
"""

import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import json
from utils.logger import configurar_logger

logger = configurar_logger("herramientas_financieras", nivel="INFO")

# =====================================================================
# CONVERSOR DE MONEDAS
# =====================================================================

@st.cache_data(ttl=3600)  # Cache por 1 hora
def obtener_tasas_cambio():
    """
    Obtiene tasas de cambio actualizadas desde API gratuita.
    Cache de 1 hora para evitar requests excesivos.
    
    Returns:
        dict: Diccionario con tasas de cambio o None si falla
    """
    try:
        # Usar exchangerate-api.com (tier gratuito, 1500 requests/mes)
        url = "https://api.exchangerate-api.com/v4/latest/USD"
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            logger.info("Tasas de cambio obtenidas exitosamente")
            return {
                'rates': data['rates'],
                'date': data['date'],
                'base': data['base']
            }
        else:
            logger.warning(f"Error al obtener tasas: Status {response.status_code}")
            return None
    except Exception as e:
        logger.error(f"Error al obtener tasas de cambio: {e}")
        return None

def get_tasas_fallback():
    """Tasas de respaldo en caso de fallo de API."""
    return {
        'rates': {
            'USD': 1.0,
            'MXN': 17.20,
            'EUR': 0.92,
            'CAD': 1.36,
            'GBP': 0.79,
            'JPY': 149.50,
            'CNY': 7.24,
            'BRL': 4.98,
            'COP': 3950.00,
            'ARS': 850.00
        },
        'date': datetime.now().strftime('%Y-%m-%d'),
        'base': 'USD',
        'fallback': True
    }

def mostrar_conversor_monedas():
    """Muestra interfaz del conversor de monedas."""
    
    st.header("💱 Conversor de Monedas")
    st.markdown("Tipos de cambio actualizados en tiempo real")
    
    # Obtener tasas de cambio
    tasas_data = obtener_tasas_cambio()
    
    if tasas_data is None:
        st.warning("⚠️ No se pudieron obtener tasas en tiempo real. Usando valores de referencia.")
        tasas_data = get_tasas_fallback()
        es_fallback = True
    else:
        es_fallback = tasas_data.get('fallback', False)
    
    tasas = tasas_data['rates']
    fecha_actualizacion = tasas_data['date']
    
    # Mostrar info de actualización
    col_info1, col_info2 = st.columns([3, 1])
    with col_info1:
        if es_fallback:
            st.caption("⚠️ Tasas de referencia (no en tiempo real)")
        else:
            st.caption(f"✅ Última actualización: {fecha_actualizacion}")
    with col_info2:
        if st.button("🔄 Actualizar", help="Actualizar tasas de cambio"):
            st.cache_data.clear()
            st.rerun()
    
    st.markdown("---")
    
    # Selector de monedas más usadas
    monedas_principales = ['USD', 'MXN', 'EUR', 'CAD', 'GBP']
    monedas_disponibles = sorted([k for k in tasas.keys() if k in monedas_principales])
    todas_las_monedas = sorted(tasas.keys())
    
    # Layout del conversor
    col1, col2, col3 = st.columns([2, 1, 2])
    
    with col1:
        st.markdown("#### De:")
        monto_origen = st.number_input(
            "Monto",
            min_value=0.0,
            value=1000.0,
            step=100.0,
            format="%.2f",
            key="monto_origen"
        )
        
        # Pestañas para monedas principales vs todas
        tab1, tab2 = st.tabs(["💰 Principales", "🌍 Todas"])
        with tab1:
            moneda_origen = st.selectbox(
                "Moneda de origen",
                options=monedas_disponibles,
                index=monedas_disponibles.index('USD') if 'USD' in monedas_disponibles else 0,
                key="moneda_origen_principal"
            )
        with tab2:
            moneda_origen = st.selectbox(
                "Moneda de origen",
                options=todas_las_monedas,
                index=todas_las_monedas.index('USD') if 'USD' in todas_las_monedas else 0,
                key="moneda_origen_todas"
            )
    
    with col2:
        st.markdown("####  ")
        st.markdown("")
        st.markdown("")
        st.markdown("### ➡️")
    
    with col3:
        st.markdown("#### A:")
        
        # Pestañas para monedas principales vs todas
        tab1, tab2 = st.tabs(["💰 Principales", "🌍 Todas"])
        with tab1:
            moneda_destino = st.selectbox(
                "Moneda de destino",
                options=monedas_disponibles,
                index=monedas_disponibles.index('MXN') if 'MXN' in monedas_disponibles else 1,
                key="moneda_destino_principal"
            )
        with tab2:
            moneda_destino = st.selectbox(
                "Moneda de destino",
                options=todas_las_monedas,
                index=todas_las_monedas.index('MXN') if 'MXN' in todas_las_monedas else 1,
                key="moneda_destino_todas"
            )
    
    # Calcular conversión
    if moneda_origen == moneda_destino:
        monto_destino = monto_origen
        tasa = 1.0
    else:
        # Convertir a USD primero, luego a moneda destino
        if moneda_origen == 'USD':
            tasa = tasas[moneda_destino]
        elif moneda_destino == 'USD':
            tasa = 1 / tasas[moneda_origen]
        else:
            # Convertir origen -> USD -> destino
            tasa = tasas[moneda_destino] / tasas[moneda_origen]
        
        monto_destino = monto_origen * tasa
    
    # Mostrar resultado
    st.markdown("---")
    st.markdown("### 💵 Resultado")
    
    col_res1, col_res2 = st.columns(2)
    with col_res1:
        st.metric(
            label=f"Monto en {moneda_destino}",
            value=f"{monto_destino:,.2f}",
            help=f"Conversión de {monto_origen:,.2f} {moneda_origen}"
        )
    
    with col_res2:
        st.metric(
            label="Tipo de Cambio",
            value=f"1 {moneda_origen} = {tasa:.4f} {moneda_destino}",
            help="Tasa de conversión aplicada"
        )
    
    # Tabla de conversiones rápidas
    with st.expander("📊 Tabla de Conversiones Rápidas"):
        st.markdown(f"**{moneda_origen} → {moneda_destino}**")
        
        montos_referencia = [100, 500, 1000, 5000, 10000, 50000, 100000]
        conversiones = []
        
        for monto in montos_referencia:
            conversion = monto * tasa
            conversiones.append({
                moneda_origen: f"{monto:,.0f}",
                moneda_destino: f"{conversion:,.2f}"
            })
        
        df_conv = pd.DataFrame(conversiones)
        st.dataframe(df_conv, use_container_width=True, hide_index=True)

# =====================================================================
# CALCULADORA DE DESCUENTO POR PRONTO PAGO
# =====================================================================

def mostrar_calculadora_descuento_pronto_pago():
    """Calculadora para evaluar si conviene dar descuento por pronto pago."""
    
    st.header("🧮 Calculadora de Descuento por Pronto Pago")
    st.markdown("¿Te conviene dar descuento si el cliente paga antes?")
    
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 📋 Datos de la Factura")
        
        monto_factura = st.number_input(
            "Monto de la Factura (USD)",
            min_value=0.0,
            value=10000.0,
            step=500.0,
            format="%.2f",
            help="Monto total de la factura a cobrar"
        )
        
        dias_plazo_original = st.number_input(
            "Plazo Original (días)",
            min_value=1,
            value=30,
            help="Días de crédito otorgados originalmente"
        )
        
        descuento_ofrecido = st.number_input(
            "Descuento Ofrecido (%)",
            min_value=0.0,
            max_value=100.0,
            value=2.5,
            step=0.1,
            format="%.2f",
            help="Porcentaje de descuento que el cliente solicita por pagar hoy"
        )
    
    with col2:
        st.markdown("#### 💰 Parámetros Financieros")
        
        tasa_costo_capital = st.number_input(
            "Costo de Capital Anual (%)",
            min_value=0.0,
            value=12.0,
            step=0.5,
            format="%.2f",
            help="Tasa de interés que pagas por financiamiento o el rendimiento que podrías obtener"
        )
        
        dias_pago_anticipado = st.number_input(
            "Días de Anticipación",
            min_value=1,
            value=30,
            help="Cuántos días antes pagará el cliente (normalmente = plazo original si paga hoy)"
        )
        
        st.markdown("")
        st.info("💡 **Tip:** Si tu costo de capital es 12% anual y el cliente paga 30 días antes, estás ganando ~1% en ese período.")
    
    st.markdown("---")
    
    # Cálculos
    monto_con_descuento = monto_factura * (1 - descuento_ofrecido / 100)
    costo_descuento = monto_factura - monto_con_descuento
    
    # Calcular tasa diaria
    tasa_diaria = (tasa_costo_capital / 100) / 365
    
    # Valor del dinero en el tiempo
    valor_adelanto_pago = monto_con_descuento * tasa_diaria * dias_pago_anticipado
    
    # Decisión
    diferencia = valor_adelanto_pago - costo_descuento
    conviene = diferencia > 0
    
    # Tasa efectiva anual del descuento
    if dias_pago_anticipado > 0:
        tasa_efectiva_desc = (descuento_ofrecido / (100 - descuento_ofrecido)) * (365 / dias_pago_anticipado) * 100
    else:
        tasa_efectiva_desc = 0
    
    # Mostrar resultados
    st.markdown("### 📊 Resultado del Análisis")
    
    col_r1, col_r2, col_r3 = st.columns(3)
    
    with col_r1:
        st.metric(
            label="💵 Monto a Recibir",
            value=f"${monto_con_descuento:,.2f}",
            delta=f"-${costo_descuento:,.2f}",
            delta_color="inverse",
            help="Monto que recibirás si das el descuento"
        )
    
    with col_r2:
        st.metric(
            label="💰 Valor del Adelanto",
            value=f"${valor_adelanto_pago:,.2f}",
            help=f"Valor financiero de recibir el pago {dias_pago_anticipado} días antes"
        )
    
    with col_r3:
        st.metric(
            label="📈 Tasa Efectiva del Descuento",
            value=f"{tasa_efectiva_desc:.2f}%",
            help="Tasa de interés anualizada que estás pagando por el adelanto"
        )
    
    st.markdown("---")
    
    # Recomendación
    if conviene:
        st.success(f"""
        ### ✅ **¡SÍ CONVIENE DAR EL DESCUENTO!**
        
        **Análisis:**
        - Recibirás el pago **{dias_pago_anticipado} días antes**
        - El valor del adelanto (${valor_adelanto_pago:,.2f}) **SUPERA** el costo del descuento (${costo_descuento:,.2f})
        - Ganancia neta: **${diferencia:,.2f}**
        - La tasa efectiva del descuento ({tasa_efectiva_desc:.2f}%) es **menor** que tu costo de capital ({tasa_costo_capital:.2f}%)
        
        **Recomendación:** Acepta el descuento y cobra hoy.
        """)
    else:
        st.error(f"""
        ### ❌ **NO CONVIENE DAR EL DESCUENTO**
        
        **Análisis:**
        - El costo del descuento (${costo_descuento:,.2f}) **SUPERA** el valor del adelanto (${valor_adelanto_pago:,.2f})
        - Pérdida neta: **${abs(diferencia):,.2f}**
        - La tasa efectiva del descuento ({tasa_efectiva_desc:.2f}%) es **mayor** que tu costo de capital ({tasa_costo_capital:.2f}%)
        
        **Recomendación:** Mejor espera al plazo original o negocia un descuento menor.
        """)
    
    # Punto de equilibrio
    with st.expander("🎯 Punto de Equilibrio - ¿Qué descuento máximo puedo dar?"):
        descuento_max = (tasa_diaria * dias_pago_anticipado) * 100
        monto_desc_max = monto_factura * (1 - descuento_max / 100)
        
        st.markdown(f"""
        **Descuento máximo recomendado:** {descuento_max:.3f}%
        
        Con este descuento:
        - Monto a recibir: ${monto_desc_max:,.2f}
        - El valor del adelanto = Costo del descuento
        - Punto de indiferencia (ni ganas ni pierdes)
        
        **Regla práctica:**
        - Si te ofrecen **menos** de {descuento_max:.3f}%: ✅ ACEPTA
        - Si te piden **más** de {descuento_max:.3f}%: ❌ RECHAZA o negocia
        """)

# =====================================================================
# CALCULADORA DSO (DAYS SALES OUTSTANDING)
# =====================================================================

def mostrar_calculadora_dso():
    """Calculadora de DSO - Días de ventas pendientes de cobro."""
    
    st.header("📈 Calculadora DSO (Days Sales Outstanding)")
    st.markdown("Mide la eficiencia de tu gestión de cobranza")
    
    st.markdown("---")
    
    # Información del cálculo
    with st.expander("ℹ️ ¿Qué es DSO y cómo se calcula?"):
        st.markdown("""
        **DSO (Days Sales Outstanding)** mide el promedio de días que tardan en cobrarse las ventas a crédito.
        
        **Fórmula:**
        ```
        DSO = (Cuentas por Cobrar / Ventas a Crédito) × Días del Período
        ```
        
        **Interpretación:**
        - DSO < 30 días: ✅ Excelente gestión de cobranza
        - DSO 30-45 días: ✅ Buena gestión
        - DSO 45-60 días: ⚠️ Atención necesaria
        - DSO > 60 días: ❌ Problemas de cobranza
        
        **Ejemplo:** Si tu DSO es 45 días, significa que en promedio tardas 45 días en cobrar desde que se realiza la venta.
        """)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 📊 Datos del Período")
        
        cuentas_por_cobrar = st.number_input(
            "Cuentas por Cobrar Totales (USD)",
            min_value=0.0,
            value=150000.0,
            step=1000.0,
            format="%.2f",
            help="Saldo total de cuentas por cobrar al final del período"
        )
        
        ventas_credito = st.number_input(
            "Ventas a Crédito del Período (USD)",
            min_value=0.01,
            value=300000.0,
            step=1000.0,
            format="%.2f",
            help="Total de ventas a crédito en el período analizado"
        )
        
        dias_periodo = st.selectbox(
            "Período de Análisis",
            options=[30, 60, 90, 365],
            format_func=lambda x: {30: "Mensual (30 días)", 60: "Bimestral (60 días)", 
                                   90: "Trimestral (90 días)", 365: "Anual (365 días)"}[x],
            index=3,
            help="Período de tiempo sobre el que se calculan las ventas"
        )
    
    with col2:
        st.markdown("#### 🎯 Objetivos y Benchmarks")
        
        dso_objetivo = st.number_input(
            "DSO Objetivo (días)",
            min_value=1,
            value=30,
            help="Tu meta de DSO ideal"
        )
        
        plazo_credito_promedio = st.number_input(
            "Plazo de Crédito Promedio (días)",
            min_value=1,
            value=30,
            help="Plazo de crédito que otorgas a tus clientes en promedio"
        )
        
        st.markdown("")
        st.info("💡 **Tip:** Un DSO cercano a tu plazo de crédito promedio indica buena gestión de cobranza.")
    
    # Cálculos
    ventas_promedio_diarias = ventas_credito / dias_periodo
    dso_actual = (cuentas_por_cobrar / ventas_promedio_diarias) if ventas_promedio_diarias > 0 else 0
    
    # Análisis
    diferencia_objetivo = dso_actual - dso_objetivo
    diferencia_plazo = dso_actual - plazo_credito_promedio
    
    # Cálculo de capital inmovilizado
    capital_inmovilizado_extra = 0
    if dso_actual > dso_objetivo:
        dias_extra = dso_actual - dso_objetivo
        capital_inmovilizado_extra = ventas_promedio_diarias * dias_extra
    
    st.markdown("---")
    st.markdown("### 📊 Resultados")
    
    col_r1, col_r2, col_r3, col_r4 = st.columns(4)
    
    with col_r1:
        st.metric(
            label="📅 DSO Actual",
            value=f"{dso_actual:.1f} días",
            delta=f"{diferencia_objetivo:+.1f} vs objetivo",
            delta_color="inverse",
            help="Días promedio de cobro actual"
        )
    
    with col_r2:
        st.metric(
            label="💵 Ventas Diarias",
            value=f"${ventas_promedio_diarias:,.0f}",
            help="Promedio de ventas a crédito por día"
        )
    
    with col_r3:
        st.metric(
            label="⏱️ vs Plazo Crédito",
            value=f"{diferencia_plazo:+.1f} días",
            delta_color="inverse",
            help="Diferencia entre DSO y plazo de crédito otorgado"
        )
    
    with col_r4:
        st.metric(
            label="💰 Capital Inmovilizado Extra",
            value=f"${capital_inmovilizado_extra:,.0f}",
            help="Dinero atrapado por exceso de DSO vs objetivo"
        )
    
    st.markdown("---")
    
    # Interpretación y recomendaciones
    if dso_actual <= dso_objetivo:
        st.success(f"""
        ### ✅ **Excelente Gestión de Cobranza**
        
        Tu DSO de {dso_actual:.1f} días está **dentro del objetivo** ({dso_objetivo} días).
        
        **Indicadores positivos:**
        - Cobranza eficiente
        - Buen flujo de efectivo
        - Riesgo de incobrabilidad bajo
        """)
    elif dso_actual <= plazo_credito_promedio * 1.5:
        st.warning(f"""
        ### ⚠️ **Atención Necesaria**
        
        Tu DSO de {dso_actual:.1f} días está **{diferencia_objetivo:.1f} días** por encima del objetivo.
        
        **Impacto:**
        - Capital inmovilizado extra: ${capital_inmovilizado_extra:,.0f}
        - Esto representa {capital_inmovilizado_extra / cuentas_por_cobrar * 100:.1f}% de tus CxC
        
        **Acciones recomendadas:**
        1. Revisar proceso de cobranza
        2. Identificar clientes morosos
        3. Considerar incentivos por pronto pago
        """)
    else:
        st.error(f"""
        ### ❌ **Problemas Críticos de Cobranza**
        
        Tu DSO de {dso_actual:.1f} días está **{diferencia_objetivo:.1f} días** por encima del objetivo.
        
        **Impacto severo:**
        - Capital inmovilizado extra: ${capital_inmovilizado_extra:,.0f}
        - Riesgo alto de incobrabilidad
        - Afectación severa al flujo de efectivo
        
        **Acciones urgentes:**
        1. ⚠️ Auditar cartera vencida inmediatamente
        2. 📞 Intensificar gestión de cobranza
        3. 💰 Revisar política de otorgamiento de crédito
        4. 👥 Considerar apoyo de despacho de cobranza
        """)
    
    # Proyección de mejora
    with st.expander("🎯 Simulador de Mejora de DSO"):
        st.markdown("#### ¿Qué pasa si mejoro mi DSO?")
        
        dso_meta_simulacion = st.slider(
            "DSO Meta a simular",
            min_value=int(dso_objetivo),
            max_value=int(dso_actual),
            value=int(dso_objetivo),
            help="Desliza para ver el impacto de reducir tu DSO"
        )
        
        dias_reduccion = dso_actual - dso_meta_simulacion
        efectivo_liberado = ventas_promedio_diarias * dias_reduccion
        porcentaje_liberado = (efectivo_liberado / cuentas_por_cobrar) * 100
        
        col_s1, col_s2 = st.columns(2)
        
        with col_s1:
            st.metric(
                label="💵 Efectivo Liberado",
                value=f"${efectivo_liberado:,.0f}",
                help="Dinero que recuperarías al reducir el DSO"
            )
        
        with col_s2:
            st.metric(
                label="📊 % de CxC Liberado",
                value=f"{porcentaje_liberado:.1f}%",
                help="Porcentaje de tus cuentas por cobrar que se convertirían en efectivo"
            )
        
        if efectivo_liberado > 0:
            st.success(f"""
            **Impacto de reducir DSO de {dso_actual:.1f} a {dso_meta_simulacion} días:**
            
            - ✅ Liberarías ${efectivo_liberado:,.0f} en efectivo
            - ✅ Mejorarías tu flujo de caja en {porcentaje_liberado:.1f}%
            - ✅ Reducirías riesgo de incobrabilidad
            - ✅ Podrías reinvertir ese capital o reducir financiamiento
            """)

# =====================================================================
# FUNCIÓN PRINCIPAL
# =====================================================================

def run():
    """Función principal del módulo de herramientas financieras."""
    
    st.title("🧰 Herramientas Financieras")
    st.markdown("Calculadoras y utilidades para el día a día")
    st.markdown("---")
    
    # Tabs para las diferentes herramientas
    tab1, tab2, tab3 = st.tabs([
        "💱 Conversor de Monedas",
        "🧮 Descuento Pronto Pago",
        "📈 Calculadora DSO"
    ])
    
    with tab1:
        mostrar_conversor_monedas()
    
    with tab2:
        mostrar_calculadora_descuento_pronto_pago()
    
    with tab3:
        mostrar_calculadora_dso()
