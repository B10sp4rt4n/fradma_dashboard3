"""
Módulo: Herramientas Financieras
Autor: Dashboard Fradma
Fecha: Febrero 2026

Funcionalidad:
- Conversor de monedas en tiempo real
- Calculadora de descuento por pronto pago
- Calculadora DSO (Days Sales Outstanding)
- Digestor de facturas XML (CFDI)
- Otras calculadoras financieras de uso frecuente
"""

import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
from utils.formatos import now_mx
import json
import xml.etree.ElementTree as ET
from io import BytesIO
import zipfile
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
        'date': now_mx().strftime('%Y-%m-%d'),
        'base': 'USD',
        'fallback': True
    }

def get_nombres_monedas():
    """Retorna diccionario con nombres completos de monedas."""
    return {
        'USD': 'Dólar Estadounidense',
        'MXN': 'Peso Mexicano',
        'EUR': 'Euro',
        'CAD': 'Dólar Canadiense',
        'GBP': 'Libra Esterlina',
        'JPY': 'Yen Japonés',
        'CNY': 'Yuan Chino',
        'BRL': 'Real Brasileño',
        'COP': 'Peso Colombiano',
        'ARS': 'Peso Argentino',
        'CHF': 'Franco Suizo',
        'AUD': 'Dólar Australiano',
        'NZD': 'Dólar Neozelandés',
        'SEK': 'Corona Sueca',
        'NOK': 'Corona Noruega',
        'DKK': 'Corona Danesa',
        'INR': 'Rupia India',
        'KRW': 'Won Surcoreano',
        'SGD': 'Dólar de Singapur',
        'HKD': 'Dólar de Hong Kong',
        'ZAR': 'Rand Sudafricano',
        'THB': 'Baht Tailandés',
        'PLN': 'Zloty Polaco',
        'CZK': 'Corona Checa',
        'HUF': 'Forinto Húngaro',
        'TRY': 'Lira Turca',
        'ILS': 'Shekel Israelí',
        'CLP': 'Peso Chileno',
        'PEN': 'Sol Peruano',
        'PHP': 'Peso Filipino',
        'MYR': 'Ringgit Malayo',
        'IDR': 'Rupia Indonesia',
        'RUB': 'Rublo Ruso'
    }

def mostrar_conversor_monedas():
    """Muestra interfaz del conversor de monedas."""
    
    st.header("💱 Conversor de Monedas")
    
    # Obtener tasas de cambio
    tasas_data = obtener_tasas_cambio()
    
    if tasas_data is None:
        st.error("❌ No se pudieron obtener tasas de la API. Usando valores de referencia limitados.")
        tasas_data = get_tasas_fallback()
        es_fallback = True
    else:
        es_fallback = tasas_data.get('fallback', False)
    
    tasas = tasas_data['rates']
    fecha_actualizacion = tasas_data['date']
    
    # Barra de información en la parte superior - SIEMPRE VISIBLE
    if len(tasas) < 20:
        st.error(f"🚨 PROBLEMA: Solo {len(tasas)} monedas disponibles (se esperan 166)")
        st.warning(f"Modo: {'FALLBACK' if es_fallback else 'API'} | Fecha: {fecha_actualizacion}")
    else:
        st.success(f"✅ {len(tasas)} monedas disponibles | Fecha: {fecha_actualizacion} | API Conectada")
    
    col_btn1, col_btn2 = st.columns([6, 1])
    with col_btn2:
        if st.button("🔄", help="Actualizar tasas de cambio"):
            st.cache_data.clear()
            st.rerun()
    
    st.markdown("---")
    
    # Obtener nombres de monedas
    nombres_monedas = get_nombres_monedas()
    
    # Selector de monedas - Preparar listas
    monedas_principales = ['USD', 'MXN', 'EUR', 'CAD', 'GBP', 'JPY', 'CNY', 'BRL']
    todas_las_monedas = sorted(tasas.keys())
    
    # Organizar monedas: principales primero, luego el resto
    monedas_ordenadas = []
    
    # Primero agregar las principales que existan
    for moneda in monedas_principales:
        if moneda in todas_las_monedas:
            monedas_ordenadas.append(moneda)
    
    # Luego agregar todas las demás alfabéticamente
    for moneda in todas_las_monedas:
        if moneda not in monedas_principales and moneda not in monedas_ordenadas:
            monedas_ordenadas.append(moneda)
    
    # Log para debug en consola
    logger.info(f"Conversor: {len(todas_las_monedas)} monedas de API, {len(monedas_ordenadas)} en lista final, fallback={es_fallback}")
    
    # MOSTRAR DEBUG MUY VISIBLE
    st.info(f"📊 Debug: {len(monedas_ordenadas)} monedas en selectores | Primeras 10: {', '.join(monedas_ordenadas[:10])}")
    
    # Función para formatear opciones del selectbox
    def format_moneda(codigo):
        nombre = nombres_monedas.get(codigo, codigo)
        return f"{codigo} - {nombre}"
    
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
            key="monto_origen",
            help="Ingresa el monto a convertir"
        )
        
        moneda_origen = st.selectbox(
            "Moneda de origen",
            options=monedas_ordenadas,
            format_func=format_moneda,
            index=0 if 'USD' in monedas_ordenadas else 0,
            key="moneda_origen",
            help="Selecciona la moneda de origen. Las primeras 8 son las más usadas."
        )
    
    with col2:
        st.markdown("####  ")
        st.markdown("")
        st.markdown("")
        st.markdown("### ➡️")
    
    with col3:
        st.markdown("#### A:")
        
        # Dejar espacio equivalente al number_input
        st.markdown("")
        st.markdown("")
        st.markdown("")
        
        moneda_destino = st.selectbox(
            "Moneda de destino",
            options=monedas_ordenadas,
            format_func=format_moneda,
            index=monedas_ordenadas.index('MXN') if 'MXN' in monedas_ordenadas else 1,
            key="moneda_destino",
            help="Selecciona la moneda de destino. Las primeras 8 son las más usadas."
        )
    
    # Botón para intercambiar monedas
    if st.button("🔄 Intercambiar Monedas", help="Invertir origen y destino"):
        # Usar session_state para intercambiar
        st.session_state.intercambiar = True
        st.rerun()
    
    # Verificar si hay que intercambiar (esto solo se ejecuta después del rerun)
    if 'intercambiar' in st.session_state and st.session_state.intercambiar:
        st.session_state.intercambiar = False
        # El intercambio se hará automáticamente en el siguiente render
    
    # Validar que las monedas sean diferentes para advertencia
    if moneda_origen == moneda_destino:
        st.warning("⚠️ La moneda de origen y destino son iguales. Selecciona monedas diferentes para convertir.")
    
    # Calcular conversión
    if moneda_origen == moneda_destino:
        monto_destino = monto_origen
        tasa = 1.0
        tasa_inversa = 1.0
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
        tasa_inversa = 1 / tasa if tasa != 0 else 0
    
    # Mostrar resultado
    st.markdown("---")
    st.markdown("### 💵 Resultado de Conversión")
    
    # Obtener nombres completos para mostrar
    nombre_origen = nombres_monedas.get(moneda_origen, moneda_origen)
    nombre_destino = nombres_monedas.get(moneda_destino, moneda_destino)
    
    # Resultado principal destacado
    st.markdown(f"""
    <div style="background-color: #f0f2f6; padding: 20px; border-radius: 10px; border-left: 5px solid #1f77b4;">
        <h3 style="margin: 0; color: #1f77b4;">{monto_destino:,.2f} {moneda_destino}</h3>
        <p style="margin: 5px 0 0 0; color: #666;">{nombre_destino}</p>
        <p style="margin: 10px 0 0 0; font-size: 14px; color: #888;">Original: {monto_origen:,.2f} {moneda_origen} ({nombre_origen})</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("")
    
    # Tasas de cambio bidireccionales
    col_res1, col_res2, col_res3 = st.columns(3)
    with col_res1:
        st.metric(
            label=f"Tasa {moneda_origen} → {moneda_destino}",
            value=f"{tasa:.6f}",
            help=f"1 {moneda_origen} = {tasa:.6f} {moneda_destino}"
        )
    
    with col_res2:
        st.metric(
            label=f"Tasa {moneda_destino} → {moneda_origen}",
            value=f"{tasa_inversa:.6f}",
            help=f"1 {moneda_destino} = {tasa_inversa:.6f} {moneda_origen}"
        )
    
    with col_res3:
        diferencia_porcentual = ((tasa - 1) * 100) if moneda_origen == 'USD' else 0
        st.metric(
            label="Base USD",
            value=f"USD {tasas.get('USD', 1.0)}",
            help="Todas las conversiones usan USD como moneda base"
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
# CALCULADORA DE INTERÉS MORATORIO
# =====================================================================

def mostrar_calculadora_interes_moratorio():
    """Calculadora de interés moratorio por pagos vencidos."""
    
    st.header("💰 Calculadora de Interés Moratorio")
    st.markdown("Calcula intereses por mora sobre facturas vencidas")
    
    st.markdown("---")
    
    # Información sobre interés moratorio
    with st.expander("ℹ️ ¿Qué es el interés moratorio y cómo se calcula?"):
        st.markdown("""
        **Interés Moratorio** es el cargo adicional que se cobra al cliente por pagar después del plazo convenido.
        
        **Métodos de cálculo:**
        
        1. **Interés Simple:**
           ```
           Interés = Capital × (Tasa Anual / 365) × Días de Mora
           ```
        
        2. **Interés Compuesto:**
           ```
           Monto Final = Capital × (1 + Tasa Diaria)^Días
           Interés = Monto Final - Capital
           ```
        
        **Tasas de referencia en México:**
        - TIIE + X puntos porcentuales
        - Tasa moratoria típica: 24% - 36% anual
        - Límite legal: Generalmente no más del doble de la tasa ordinaria
        
        **Ejemplo:** 
        - Factura: $10,000
        - Mora: 30 días
        - Tasa: 24% anual
        - Interés simple: $10,000 × (0.24/365) × 30 = $197.26
        """)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 📋 Datos de la Factura")
        
        monto_principal = st.number_input(
            "Monto Original de la Factura (USD)",
            min_value=0.0,
            value=10000.0,
            step=100.0,
            format="%.2f",
            help="Monto original adeudado (antes de intereses)"
        )
        
        fecha_vencimiento = st.date_input(
            "Fecha de Vencimiento Original",
            value=now_mx().date() - timedelta(days=30),
            help="Fecha en que la factura debió pagarse"
        )
        
        fecha_calculo = st.date_input(
            "Fecha de Cálculo / Pago",
            value=now_mx().date(),
            help="Fecha hasta la cual calcular el interés (hoy o fecha proyectada de pago)"
        )
        
        # Calcular días de mora
        dias_mora = (fecha_calculo - fecha_vencimiento).days
        
        if dias_mora < 0:
            st.warning("⚠️ La fecha de cálculo es anterior al vencimiento. No hay mora.")
            dias_mora = 0
        else:
            st.info(f"📅 **Días de mora:** {dias_mora} días")
    
    with col2:
        st.markdown("#### ⚙️ Parámetros de Cálculo")
        
        tasa_moratoria_anual = st.number_input(
            "Tasa Moratoria Anual (%)",
            min_value=0.0,
            value=24.0,
            step=0.5,
            format="%.2f",
            help="Tasa de interés moratorio anual (típicamente 24%-36%)"
        )
        
        metodo_calculo = st.radio(
            "Método de Cálculo",
            options=["Simple", "Compuesto"],
            index=0,
            help="Simple: Interés sobre capital original. Compuesto: Interés sobre interés"
        )
        
        incluir_iva_interes = st.checkbox(
            "Incluir IVA sobre Interés",
            value=True,
            help="En México, el interés moratorio causa IVA (16%)"
        )
        
        st.markdown("")
        st.info("💡 **Tip Legal:** Consulta con legal antes de cobrar intereses. Algunos contratos no los permiten.")
    
    st.markdown("---")
    
    # Cálculos
    if dias_mora > 0 and monto_principal > 0:
        tasa_diaria = tasa_moratoria_anual / 100 / 365
        
        if metodo_calculo == "Simple":
            interes_moratorio = monto_principal * tasa_diaria * dias_mora
        else:  # Compuesto
            monto_final = monto_principal * ((1 + tasa_diaria) ** dias_mora)
            interes_moratorio = monto_final - monto_principal
        
        # IVA sobre interés (México: 16%)
        iva_interes = interes_moratorio * 0.16 if incluir_iva_interes else 0
        interes_total = interes_moratorio + iva_interes
        
        total_a_cobrar = monto_principal + interes_total
        
        # Tasa efectiva anual
        if dias_mora > 0:
            factor_anual = 365 / dias_mora
            tasa_efectiva = ((total_a_cobrar / monto_principal) ** factor_anual - 1) * 100
        else:
            tasa_efectiva = 0
        
        # Mostrar resultados
        st.markdown("### 📊 Resultado del Cálculo")
        
        col_r1, col_r2, col_r3, col_r4 = st.columns(4)
        
        with col_r1:
            st.metric(
                label="💰 Interés Moratorio",
                value=f"${interes_moratorio:,.2f}",
                help=f"Interés calculado por {dias_mora} días de mora"
            )
        
        with col_r2:
            if incluir_iva_interes:
                st.metric(
                    label="📊 IVA sobre Interés",
                    value=f"${iva_interes:,.2f}",
                    help="IVA 16% sobre el interés moratorio"
                )
            else:
                st.metric(
                    label="📊 IVA sobre Interés",
                    value="$0.00",
                    help="IVA no aplicado"
                )
        
        with col_r3:
            st.metric(
                label="💵 Interés Total",
                value=f"${interes_total:,.2f}",
                help="Interés + IVA (si aplica)"
            )
        
        with col_r4:
            st.metric(
                label="💸 Total a Cobrar",
                value=f"${total_a_cobrar:,.2f}",
                delta=f"+${interes_total:,.2f}",
                help="Capital + Interés + IVA"
            )
        
        st.markdown("---")
        
        # Desglose detallado
        col_det1, col_det2 = st.columns(2)
        
        with col_det1:
            st.markdown("### 📝 Desglose del Cobro")
            
            desglose_data = {
                'Concepto': [
                    'Capital Original',
                    f'Interés Moratorio ({metodo_calculo})',
                    'IVA sobre Interés (16%)' if incluir_iva_interes else 'IVA sobre Interés',
                    'TOTAL A COBRAR'
                ],
                'Monto': [
                    f"${monto_principal:,.2f}",
                    f"${interes_moratorio:,.2f}",
                    f"${iva_interes:,.2f}",
                    f"${total_a_cobrar:,.2f}"
                ]
            }
            
            df_desglose = pd.DataFrame(desglose_data)
            st.dataframe(df_desglose, use_container_width=True, hide_index=True)
        
        with col_det2:
            st.markdown("### 📈 Información Adicional")
            
            st.write(f"**Método:** {metodo_calculo}")
            st.write(f"**Tasa Moratoria Anual:** {tasa_moratoria_anual:.2f}%")
            st.write(f"**Tasa Diaria:** {tasa_diaria*100:.4f}%")
            st.write(f"**Días de Mora:** {dias_mora} días")
            st.write(f"**Tasa Efectiva Anual:** {tasa_efectiva:.2f}%")
            
            # Interés promedio por día
            interes_diario = interes_total / dias_mora if dias_mora > 0 else 0
            st.write(f"**Interés Promedio/Día:** ${interes_diario:,.2f}")
        
        # Proyección de intereses futuros
        with st.expander("📅 Proyección de Intereses Futuros"):
            st.markdown("#### ¿Cuánto costará si no paga pronto?")
            
            dias_proyeccion = [7, 15, 30, 60, 90]
            proyecciones = []
            
            for dias_extra in dias_proyeccion:
                dias_total = dias_mora + dias_extra
                
                if metodo_calculo == "Simple":
                    int_proyectado = monto_principal * tasa_diaria * dias_total
                else:
                    monto_proy = monto_principal * ((1 + tasa_diaria) ** dias_total)
                    int_proyectado = monto_proy - monto_principal
                
                iva_proy = int_proyectado * 0.16 if incluir_iva_interes else 0
                int_total_proy = int_proyectado + iva_proy
                total_proy = monto_principal + int_total_proy
                
                proyecciones.append({
                    'Días Adicionales': f"+{dias_extra}",
                    'Total Días Mora': dias_total,
                    'Interés Total': f"${int_total_proy:,.2f}",
                    'Total a Pagar': f"${total_proy:,.2f}"
                })
            
            df_proy = pd.DataFrame(proyecciones)
            st.dataframe(df_proy, use_container_width=True, hide_index=True)
            
            st.caption(f"💡 Cada día adicional cuesta aproximadamente ${interes_diario:,.2f} en intereses")
    
    else:
        st.info("👆 Ingresa los datos de la factura para calcular el interés moratorio")

# =====================================================================
# PANEL DE INDICADORES ECONÓMICOS
# =====================================================================

@st.cache_data(ttl=3600)  # Cache por 1 hora
def obtener_indicadores_economicos():
    """
    Obtiene indicadores económicos básicos.
    Por ahora usa el tipo de cambio de la API existente.
    """
    try:
        # Obtener tipo de cambio
        tasas_data = obtener_tasas_cambio()
        
        if tasas_data:
            usd_mxn = tasas_data['rates'].get('MXN', 17.20)
            fecha = tasas_data['date']
            
            return {
                'usd_mxn': usd_mxn,
                'fecha': fecha,
                'success': True
            }
        else:
            return {
                'usd_mxn': 17.20,
                'fecha': now_mx().strftime('%Y-%m-%d'),
                'success': False
            }
    except Exception as e:
        logger.error(f"Error al obtener indicadores: {e}")
        return {
            'usd_mxn': 17.20,
            'fecha': now_mx().strftime('%Y-%m-%d'),
            'success': False
        }

def mostrar_indicadores_economicos():
    """Muestra panel con indicadores económicos de referencia."""
    
    st.header("📊 Indicadores Económicos")
    st.markdown("Información económica y financiera de referencia")
    
    st.markdown("---")
    
    # Obtener indicadores
    indicadores = obtener_indicadores_economicos()
    
    # Estado de actualización
    col_status = st.columns([3, 1])
    with col_status[0]:
        if indicadores['success']:
            st.caption(f"✅ Última actualización: {indicadores['fecha']}")
        else:
            st.caption("⚠️ Usando valores de referencia")
    
    with col_status[1]:
        if st.button("🔄 Actualizar", key="refresh_indicadores"):
            st.cache_data.clear()
            st.rerun()
    
    st.markdown("---")
    
    # Tipo de Cambio USD/MXN
    st.markdown("### 💱 Tipo de Cambio")
    
    col1, col2, col3 = st.columns([2, 2, 2])
    
    with col1:
        usd_mxn = indicadores['usd_mxn']
        st.metric(
            label="USD/MXN",
            value=f"${usd_mxn:.2f}",
            help="Pesos mexicanos por dólar estadounidense"
        )
    
    with col2:
        # Calcular inverso (cuántos dólares por peso)
        mxn_usd = 1 / usd_mxn if usd_mxn > 0 else 0
        st.metric(
            label="MXN/USD",
            value=f"${mxn_usd:.4f}",
            help="Dólares por peso mexicano"
        )
    
    with col3:
        # Referencia de 1000 USD
        mil_usd_en_mxn = 1000 * usd_mxn
        st.metric(
            label="1,000 USD =",
            value=f"${mil_usd_en_mxn:,.2f} MXN",
            help="Equivalencia de mil dólares en pesos"
        )
    
    st.markdown("---")
    
    # Tasas de Interés de Referencia
    st.markdown("### 📈 Tasas de Interés de Referencia")
    
    st.info("""
    **💡 Tasas de referencia comunes en México (2026):**
    
    - **TIIE 28 días:** ~10.50% - 11.50% (referencia interbancaria)
    - **Tasa Objetivo Banxico:** ~11.00%
    - **Tasa Pasiva (ahorro):** ~8.00% - 10.00%
    - **Tasa Activa (préstamos empresariales):** ~14.00% - 18.00%
    - **Tarjetas de crédito:** ~35.00% - 50.00%
    
    *Nota: Estas son tasas de referencia. Consulta con tu banco para tasas actuales.*
    """)
    
    st.markdown("---")
    
    # Calculadora rápida de equivalencias
    st.markdown("### 🔢 Calculadora Rápida de Equivalencias")
    
    col_calc1, col_calc2 = st.columns(2)
    
    with col_calc1:
        monto_convertir = st.number_input(
            "Monto a convertir",
            min_value=0.0,
            value=1000.0,
            step=100.0,
            key="monto_equiv"
        )
    
    with col_calc2:
        direccion = st.radio(
            "Dirección",
            options=["USD → MXN", "MXN → USD"],
            horizontal=True,
            key="direccion_equiv"
        )
    
    if direccion == "USD → MXN":
        resultado = monto_convertir * usd_mxn
        st.success(f"**${monto_convertir:,.2f} USD** = **${resultado:,.2f} MXN**")
    else:
        resultado = monto_convertir / usd_mxn
        st.success(f"**${monto_convertir:,.2f} MXN** = **${resultado:,.2f} USD**")
    
    st.markdown("---")
    
    # Tabla de referencia rápida
    with st.expander("📋 Tabla de Referencia Rápida USD ↔ MXN"):
        montos_ref = [100, 500, 1000, 5000, 10000, 50000, 100000]
        
        tabla_ref = []
        for monto in montos_ref:
            tabla_ref.append({
                'USD': f"${monto:,}",
                'MXN': f"${monto * usd_mxn:,.2f}",
                '←': '→',
                'MXN ': f"${monto:,}",
                'USD ': f"${monto / usd_mxn:,.2f}"
            })
        
        df_ref = pd.DataFrame(tabla_ref)
        st.dataframe(df_ref, use_container_width=True, hide_index=True)

# =====================================================================
# DIGESTOR DE FACTURAS XML (CFDI)
# =====================================================================

def parsear_xml_cfdi(archivo_xml):
    """
    Parsea un archivo XML de factura CFDI (México).
    
    Args:
        archivo_xml: Archivo XML subido
        
    Returns:
        dict: Diccionario con la información extraída o None si hay error
    """
    try:
        # Asegurar que el archivo esté al inicio del buffer
        if hasattr(archivo_xml, 'seek'):
            archivo_xml.seek(0)
        
        # Leer contenido del archivo
        contenido = archivo_xml.read()
        
        # Parsear XML
        root = ET.fromstring(contenido)
        
        # Namespaces comunes en CFDI
        ns = {
            'cfdi': 'http://www.sat.gob.mx/cfd/4',
            'cfdi3': 'http://www.sat.gob.mx/cfd/3',
            'tfd': 'http://www.sat.gob.mx/TimbreFiscalDigital'
        }
        
        # Intentar con namespace 4.0 o 3.3
        if root.tag.endswith('Comprobante'):
            # Determinar namespace
            if 'http://www.sat.gob.mx/cfd/4' in root.tag:
                ns_cfdi = 'cfdi'
            else:
                ns_cfdi = 'cfdi3'
        else:
            return None
        
        # Extraer información del comprobante
        datos = {}
        
        # Atributos del comprobante
        datos['Fecha'] = root.get('Fecha', 'N/A')
        datos['Folio'] = root.get('Folio', 'N/A')
        datos['Serie'] = root.get('Serie', 'N/A')
        datos['FormaPago'] = root.get('FormaPago', 'N/A')
        datos['MetodoPago'] = root.get('MetodoPago', 'N/A')
        datos['TipoDeComprobante'] = root.get('TipoDeComprobante', 'N/A')
        datos['Moneda'] = root.get('Moneda', 'MXN')
        datos['TipoCambio'] = root.get('TipoCambio', '1.0')
        datos['SubTotal'] = float(root.get('SubTotal', '0'))
        datos['Total'] = float(root.get('Total', '0'))
        
        # Emisor
        emisor = root.find(f'{{{ns[ns_cfdi]}}}Emisor')
        if emisor is not None:
            datos['EmisorRFC'] = emisor.get('Rfc', 'N/A')
            datos['EmisorNombre'] = emisor.get('Nombre', 'N/A')
            datos['EmisorRegimenFiscal'] = emisor.get('RegimenFiscal', 'N/A')
        else:
            datos['EmisorRFC'] = 'N/A'
            datos['EmisorNombre'] = 'N/A'
            datos['EmisorRegimenFiscal'] = 'N/A'
        
        # Receptor
        receptor = root.find(f'{{{ns[ns_cfdi]}}}Receptor')
        if receptor is not None:
            datos['ReceptorRFC'] = receptor.get('Rfc', 'N/A')
            datos['ReceptorNombre'] = receptor.get('Nombre', 'N/A')
            datos['ReceptorUsoCFDI'] = receptor.get('UsoCFDI', 'N/A')
        else:
            datos['ReceptorRFC'] = 'N/A'
            datos['ReceptorNombre'] = 'N/A'
            datos['ReceptorUsoCFDI'] = 'N/A'
        
        # Conceptos
        conceptos = []
        conceptos_elem = root.find(f'{{{ns[ns_cfdi]}}}Conceptos')
        if conceptos_elem is not None:
            for concepto in conceptos_elem.findall(f'{{{ns[ns_cfdi]}}}Concepto'):
                conceptos.append({
                    'Cantidad': concepto.get('Cantidad', '0'),
                    'Unidad': concepto.get('Unidad', concepto.get('ClaveUnidad', 'N/A')),
                    'Descripcion': concepto.get('Descripcion', 'N/A'),
                    'ValorUnitario': float(concepto.get('ValorUnitario', '0')),
                    'Importe': float(concepto.get('Importe', '0'))
                })
        datos['Conceptos'] = conceptos
        
        # Impuestos
        impuestos = root.find(f'{{{ns[ns_cfdi]}}}Impuestos')
        if impuestos is not None:
            datos['TotalImpuestosTrasladados'] = float(impuestos.get('TotalImpuestosTrasladados', '0'))
            datos['TotalImpuestosRetenidos'] = float(impuestos.get('TotalImpuestosRetenidos', '0'))
        else:
            datos['TotalImpuestosTrasladados'] = 0
            datos['TotalImpuestosRetenidos'] = 0
        
        # Complemento - Timbre Fiscal Digital
        complemento = root.find(f'{{{ns[ns_cfdi]}}}Complemento')
        if complemento is not None:
            timbre = complemento.find(f'{{{ns["tfd"]}}}TimbreFiscalDigital')
            if timbre is not None:
                datos['UUID'] = timbre.get('UUID', 'N/A')
                datos['FechaTimbrado'] = timbre.get('FechaTimbrado', 'N/A')
                datos['SelloCFD'] = timbre.get('SelloCFD', 'N/A')[:50] + '...'  # Truncar
            else:
                datos['UUID'] = 'N/A'
                datos['FechaTimbrado'] = 'N/A'
        else:
            datos['UUID'] = 'N/A'
            datos['FechaTimbrado'] = 'N/A'
        
        # Calcular IVA
        datos['IVA'] = datos['TotalImpuestosTrasladados']
        
        return datos
        
    except Exception as e:
        logger.error(f"Error al parsear XML: {e}")
        return None

def mostrar_digestor_xml():
    """Muestra interfaz para digerir facturas XML (CFDI)."""
    
    st.header("📄 Digestor de Facturas XML (CFDI)")
    st.markdown("Extrae información de facturas electrónicas en formato XML")
    
    st.markdown("---")
    
    # Información sobre CFDI
    with st.expander("ℹ️ ¿Qué es un CFDI y cómo usar esta herramienta?"):
        st.markdown("""
        **CFDI (Comprobante Fiscal Digital por Internet)** es el formato oficial de facturación electrónica en México.
        
        **Esta herramienta te permite:**
        - 📤 Subir uno o múltiples archivos XML
        - 📊 Extraer automáticamente: RFC, montos, fechas, UUID, conceptos
        - 📥 Exportar a Excel para análisis
        - 💰 Calcular totales y resúmenes
        
        **Formatos soportados:**
        - CFDI 4.0
        - CFDI 3.3
        - Archivos individuales (.xml)
        - Archivos comprimidos (.zip con múltiples XMLs)
        
        **Información extraída:**
        - Datos del emisor (RFC, nombre, régimen fiscal)
        - Datos del receptor (RFC, nombre, uso CFDI)
        - Montos (subtotal, IVA, total)
        - Folio fiscal (UUID)
        - Conceptos/partidas
        - Forma y método de pago
        """)
    
    st.markdown("### 📤 Cargar Archivos XML")
    
    # Opciones de carga
    tipo_carga = st.radio(
        "Tipo de carga:",
        options=["Archivos individuales", "Archivo ZIP"],
        horizontal=True,
        help="Selecciona cómo quieres cargar las facturas"
    )
    
    # Variables para almacenar archivos cargados
    archivos_disponibles = []
    contenidos_archivos = {}
    
    if tipo_carga == "Archivos individuales":
        archivos_xml = st.file_uploader(
            "Selecciona archivos XML de facturas",
            type=['xml'],
            accept_multiple_files=True,
            help="Puedes seleccionar múltiples archivos XML a la vez"
        )
        
        if archivos_xml:
            st.success(f"✅ {len(archivos_xml)} archivo(s) cargado(s)")
            for archivo in archivos_xml:
                archivos_disponibles.append(archivo.name)
                contenidos_archivos[archivo.name] = archivo
    
    else:  # ZIP
        archivo_zip = st.file_uploader(
            "Selecciona archivo ZIP con XMLs",
            type=['zip'],
            help="El ZIP debe contener archivos .xml"
        )
        
        if archivo_zip:
            try:
                with zipfile.ZipFile(BytesIO(archivo_zip.read())) as z:
                    xml_files = [f for f in z.namelist() if f.lower().endswith('.xml')]
                    
                    st.success(f"✅ {len(xml_files)} archivos XML encontrados en el ZIP")
                    
                    for xml_file in xml_files:
                        archivos_disponibles.append(xml_file)
                        with z.open(xml_file) as f:
                            # Crear un objeto similar a UploadedFile
                            class FakeFile:
                                def __init__(self, content, name):
                                    self.content = content
                                    self.name = name
                                def read(self):
                                    return self.content
                            
                            contenidos_archivos[xml_file] = FakeFile(f.read(), xml_file)
            except Exception as e:
                st.error(f"❌ Error al leer ZIP: {str(e)}")
    
    # Selector de archivos a procesar
    facturas_procesadas = []
    
    if archivos_disponibles:
        st.markdown("---")
        st.markdown("### 🎯 Selección de Archivos a Procesar")
        
        col_sel1, col_sel2 = st.columns([3, 1])
        
        with col_sel1:
            # Opción para procesar todos o seleccionar
            modo_procesamiento = st.radio(
                "Modo de procesamiento:",
                options=["Procesar todos", "Seleccionar archivos específicos"],
                horizontal=True,
                help="Elige si procesar todos los archivos o seleccionar cuáles procesar"
            )
        
        with col_sel2:
            st.metric("Archivos disponibles", len(archivos_disponibles))
        
        # Selección de archivos
        archivos_seleccionados = []
        
        if modo_procesamiento == "Seleccionar archivos específicos":
            archivos_seleccionados = st.multiselect(
                "Selecciona los archivos XML que deseas procesar:",
                options=archivos_disponibles,
                default=[],
                help="Mantén presionada la tecla Ctrl/Cmd para seleccionar múltiples archivos"
            )
            
            if archivos_seleccionados:
                st.info(f"📋 {len(archivos_seleccionados)} archivo(s) seleccionado(s)")
        else:
            archivos_seleccionados = archivos_disponibles
            st.info(f"📋 Se procesarán todos los {len(archivos_seleccionados)} archivos")
        
        # Botón para procesar
        if archivos_seleccionados:
            if st.button("🚀 Procesar Archivos Seleccionados", type="primary"):
                with st.spinner(f"📊 Procesando {len(archivos_seleccionados)} archivo(s)..."):
                    progress_bar = st.progress(0)
                    
                    for idx, nombre_archivo in enumerate(archivos_seleccionados):
                        archivo_obj = contenidos_archivos[nombre_archivo]
                        datos = parsear_xml_cfdi(archivo_obj)
                        
                        if datos:
                            datos['Archivo'] = nombre_archivo
                            facturas_procesadas.append(datos)
                        else:
                            st.warning(f"⚠️ No se pudo procesar: {nombre_archivo}")
                        
                        # Actualizar barra de progreso
                        progress_bar.progress((idx + 1) / len(archivos_seleccionados))
                    
                    progress_bar.empty()
                    
                    if facturas_procesadas:
                        st.success(f"✅ {len(facturas_procesadas)} factura(s) procesada(s) exitosamente")
        else:
            st.warning("⚠️ Selecciona al menos un archivo para procesar")
    
    # Mostrar resultados
    if facturas_procesadas:
        st.markdown("---")
        st.markdown(f"### ✅ {len(facturas_procesadas)} Factura(s) Procesada(s)")
        
        # Resumen general
        col_res1, col_res2, col_res3, col_res4 = st.columns(4)
        
        total_subtotal = sum(f['SubTotal'] for f in facturas_procesadas)
        total_iva = sum(f['IVA'] for f in facturas_procesadas)
        total_general = sum(f['Total'] for f in facturas_procesadas)
        
        with col_res1:
            st.metric(
                label="📊 Total Facturas",
                value=len(facturas_procesadas)
            )
        
        with col_res2:
            st.metric(
                label="💵 Subtotal",
                value=f"${total_subtotal:,.2f}"
            )
        
        with col_res3:
            st.metric(
                label="💰 IVA",
                value=f"${total_iva:,.2f}"
            )
        
        with col_res4:
            st.metric(
                label="💸 Total General",
                value=f"${total_general:,.2f}"
            )
        
        st.markdown("---")
        
        # Tabs para diferentes vistas
        tab_resumen, tab_detalle, tab_conceptos = st.tabs([
            "📋 Resumen",
            "📄 Detalle por Factura",
            "📦 Conceptos"
        ])
        
        with tab_resumen:
            st.markdown("#### 📊 Tabla Resumen de Facturas")
            
            # Crear DataFrame resumen para VISUALIZACIÓN (con textos truncados)
            df_resumen_display = pd.DataFrame([
                {
                    'Archivo': f['Archivo'],
                    'Fecha': f['Fecha'][:10] if len(f['Fecha']) > 10 else f['Fecha'],
                    'Folio': f['Folio'],
                    'Serie': f['Serie'],
                    'Emisor RFC': f['EmisorRFC'],
                    'Emisor': f['EmisorNombre'][:30] + '...' if len(f['EmisorNombre']) > 30 else f['EmisorNombre'],
                    'UUID': f['UUID'][:20] + '...' if len(f['UUID']) > 20 else f['UUID'],
                    'Subtotal': f['SubTotal'],
                    'IVA': f['IVA'],
                    'Total': f['Total'],
                    'Moneda': f['Moneda']
                }
                for f in facturas_procesadas
            ])
            
            # Crear DataFrame completo para EXPORTACIÓN (sin truncar)
            df_resumen_completo = pd.DataFrame([
                {
                    'Archivo': f['Archivo'],
                    'Fecha': f['Fecha'][:10] if len(f['Fecha']) > 10 else f['Fecha'],
                    'Folio': f['Folio'],
                    'Serie': f['Serie'],
                    'Emisor RFC': f['EmisorRFC'],
                    'Emisor Nombre': f['EmisorNombre'],  # Nombre completo sin truncar
                    'Receptor RFC': f['ReceptorRFC'],
                    'Receptor Nombre': f['ReceptorNombre'],
                    'UUID': f['UUID'],  # UUID completo sin truncar
                    'Forma Pago': f['FormaPago'],
                    'Método Pago': f['MetodoPago'],
                    'Subtotal': f['SubTotal'],
                    'IVA': f['IVA'],
                    'Total': f['Total'],
                    'Moneda': f['Moneda']
                }
                for f in facturas_procesadas
            ])
            
            # Mostrar resumen en pantalla (versión truncada)
            st.dataframe(
                df_resumen_display.style.format({
                    'Subtotal': '${:,.2f}',
                    'IVA': '${:,.2f}',
                    'Total': '${:,.2f}'
                }),
                use_container_width=True,
                hide_index=True
            )
            
            # Preparar archivo Excel para descarga (versión completa)
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_resumen_completo.to_excel(writer, sheet_name='Resumen', index=False)
                
                # Obtener el workbook y worksheet para ajustar formatos
                workbook = writer.book
                worksheet = writer.sheets['Resumen']
                
                # Formato de moneda
                money_format = workbook.add_format({'num_format': '$#,##0.00'})
                
                # Formato para encabezados con ajuste de texto
                header_format = workbook.add_format({
                    'bold': True,
                    'text_wrap': True,
                    'valign': 'top',
                    'bg_color': '#D7E4BD',
                    'border': 1
                })
                
                # Formato para celdas de texto con ajuste
                text_format = workbook.add_format({
                    'text_wrap': False,  # No wrap para que se vea todo en una línea
                    'valign': 'vcenter'
                })
                
                # Ajustar anchos de columnas (AUMENTADOS significativamente)
                worksheet.set_column('A:A', 40, text_format)   # Archivo
                worksheet.set_column('B:B', 12, text_format)   # Fecha
                worksheet.set_column('C:C', 10, text_format)   # Folio
                worksheet.set_column('D:D', 10, text_format)   # Serie
                worksheet.set_column('E:E', 15, text_format)   # Emisor RFC
                worksheet.set_column('F:F', 70, text_format)   # Emisor Nombre (MUY AMPLIO para nombres largos)
                worksheet.set_column('G:G', 15, text_format)   # Receptor RFC
                worksheet.set_column('H:H', 70, text_format)   # Receptor Nombre (MUY AMPLIO)
                worksheet.set_column('I:I', 45, text_format)   # UUID (UUID completo visible)
                worksheet.set_column('J:J', 18, text_format)   # Forma Pago
                worksheet.set_column('K:K', 18, text_format)   # Método Pago
                worksheet.set_column('L:L', 15, money_format)  # Subtotal
                worksheet.set_column('M:M', 15, money_format)  # IVA
                worksheet.set_column('N:N', 15, money_format)  # Total
                worksheet.set_column('O:O', 10, text_format)   # Moneda
                
                # Aplicar formato de moneda a columnas numéricas (sobrescribir los valores)
                for row in range(1, len(df_resumen_completo) + 1):
                    worksheet.write(row, 11, df_resumen_completo.iloc[row-1]['Subtotal'], money_format)
                    worksheet.write(row, 12, df_resumen_completo.iloc[row-1]['IVA'], money_format)
                    worksheet.write(row, 13, df_resumen_completo.iloc[row-1]['Total'], money_format)
                
                # Hoja adicional con totales
                df_totales = pd.DataFrame([{
                    'Concepto': 'Total Facturas',
                    'Cantidad': len(facturas_procesadas)
                }, {
                    'Concepto': 'Subtotal',
                    'Cantidad': f'${total_subtotal:,.2f}'
                }, {
                    'Concepto': 'IVA',
                    'Cantidad': f'${total_iva:,.2f}'
                }, {
                    'Concepto': 'Total General',
                    'Cantidad': f'${total_general:,.2f}'
                }])
                df_totales.to_excel(writer, sheet_name='Totales', index=False)
            
            output.seek(0)
            
            # Mensaje informativo sobre el Excel
            st.info("💡 **Nota:** El Excel contiene los nombres completos. Las columnas están pre-ajustadas a 70 caracteres de ancho. Si ves texto cortado, es solo la visualización de Excel - haz doble clic en la celda para ver el contenido completo.")
            
            # Botón de descarga directo
            st.download_button(
                label="⬇️ Descargar Resumen en Excel",
                data=output,
                file_name=f"facturas_resumen_{now_mx().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
                use_container_width=True
            )
        
        with tab_detalle:
            st.markdown("#### 📄 Detalle Completo por Factura")
            
            # Selector de factura
            factura_seleccionada = st.selectbox(
                "Selecciona una factura para ver detalle:",
                options=range(len(facturas_procesadas)),
                format_func=lambda i: f"{facturas_procesadas[i]['Archivo']} - {facturas_procesadas[i]['EmisorNombre'][:40]}"
            )
            
            factura = facturas_procesadas[factura_seleccionada]
            
            # Información completa
            col_det1, col_det2 = st.columns(2)
            
            with col_det1:
                st.markdown("**📋 Información General**")
                st.write(f"**Archivo:** {factura['Archivo']}")
                st.write(f"**Fecha:** {factura['Fecha']}")
                st.write(f"**Folio:** {factura['Folio']}")
                st.write(f"**Serie:** {factura['Serie']}")
                st.write(f"**Tipo:** {factura['TipoDeComprobante']}")
                st.write(f"**Forma Pago:** {factura['FormaPago']}")
                st.write(f"**Método Pago:** {factura['MetodoPago']}")
                
                st.markdown("**👤 Emisor**")
                st.write(f"**RFC:** {factura['EmisorRFC']}")
                st.write(f"**Nombre:** {factura['EmisorNombre']}")
                st.write(f"**Régimen:** {factura['EmisorRegimenFiscal']}")
            
            with col_det2:
                st.markdown("**👥 Receptor**")
                st.write(f"**RFC:** {factura['ReceptorRFC']}")
                st.write(f"**Nombre:** {factura['ReceptorNombre']}")
                st.write(f"**Uso CFDI:** {factura['ReceptorUsoCFDI']}")
                
                st.markdown("**💰 Montos**")
                st.write(f"**Moneda:** {factura['Moneda']}")
                st.write(f"**Subtotal:** ${factura['SubTotal']:,.2f}")
                st.write(f"**IVA:** ${factura['IVA']:,.2f}")
                st.write(f"**Total:** ${factura['Total']:,.2f}")
                
                st.markdown("**🔐 Timbre Fiscal**")
                st.write(f"**UUID:** {factura['UUID']}")
                st.write(f"**Fecha Timbrado:** {factura.get('FechaTimbrado', 'N/A')}")
        
        with tab_conceptos:
            st.markdown("#### 📦 Conceptos / Partidas")
            
            # Consolidar todos los conceptos
            todos_conceptos = []
            for idx, factura in enumerate(facturas_procesadas):
                for concepto in factura['Conceptos']:
                    todos_conceptos.append({
                        'Factura': factura['Archivo'],
                        'Folio': factura['Folio'],
                        'Cantidad': concepto['Cantidad'],
                        'Unidad': concepto['Unidad'],
                        'Descripción': concepto['Descripcion'],
                        'Valor Unitario': concepto['ValorUnitario'],
                        'Importe': concepto['Importe']
                    })
            
            if todos_conceptos:
                df_conceptos = pd.DataFrame(todos_conceptos)
                
                st.dataframe(
                    df_conceptos.style.format({
                        'Valor Unitario': '${:,.2f}',
                        'Importe': '${:,.2f}'
                    }),
                    use_container_width=True,
                    hide_index=True
                )
                
                st.info(f"📦 Total de conceptos: {len(todos_conceptos)}")
            else:
                st.warning("⚠️ No se encontraron conceptos en las facturas")
    
    else:
        st.info("👆 Sube archivos XML para comenzar")

# =====================================================================
# FUNCIÓN PRINCIPAL
# =====================================================================

def run():
    """Función principal del módulo de herramientas financieras."""
    
    st.title("🧰 Herramientas Financieras")
    st.markdown("Calculadoras y utilidades para el día a día")
    st.markdown("---")
    
    # Tabs para las diferentes herramientas
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "💱 Conversor de Monedas",
        "🧮 Descuento Pronto Pago",
        "📈 Calculadora DSO",
        "💰 Interés Moratorio",
        "📊 Indicadores Económicos",
        "📄 Digestor CFDI/XML"
    ])
    
    with tab1:
        mostrar_conversor_monedas()
    
    with tab2:
        mostrar_calculadora_descuento_pronto_pago()
    
    with tab3:
        mostrar_calculadora_dso()
    
    with tab4:
        mostrar_calculadora_interes_moratorio()
    
    with tab5:
        mostrar_indicadores_economicos()
    
    with tab6:
        mostrar_digestor_xml()
