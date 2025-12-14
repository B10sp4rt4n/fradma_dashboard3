import streamlit as st
import pandas as pd
import numpy as np
from unidecode import unidecode
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import plotly.graph_objects as go
import plotly.express as px

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
    if not archivo.name.endswith(('.xls', '.xlsx')):
        st.error("❌ Solo se aceptan archivos Excel para el reporte de deudas.")
        return

    try:
        xls = pd.ExcelFile(archivo)
        hojas = xls.sheet_names
        
        if "CXC VIGENTES" not in hojas or "CXC VENCIDAS" not in hojas:
            st.error("❌ No se encontraron las hojas requeridas: 'CXC VIGENTES' y 'CXC VENCIDAS'.")
            return

        st.info("✅ Fuente: Hojas 'CXC VIGENTES' y 'CXC VENCIDAS'")

        # Leer y normalizar datos
        df_vigentes = pd.read_excel(xls, sheet_name='CXC VIGENTES')
        df_vencidas = pd.read_excel(xls, sheet_name='CXC VENCIDAS')
        
        df_vigentes = normalizar_columnas(df_vigentes)
        df_vencidas = normalizar_columnas(df_vencidas)
        
        # Renombrar columnas clave - PRIORIZAR COLUMNA F (CLIENTE)
        for df in [df_vigentes, df_vencidas]:
            # 1. Priorizar columna 'cliente' (columna F)
            if 'cliente' in df.columns:
                df.rename(columns={'cliente': 'deudor'}, inplace=True)
                
                # Si también existe 'razon_social', eliminarla
                if 'razon_social' in df.columns:
                    df.drop(columns=['razon_social'], inplace=True)
                    
            # 2. Si no existe 'cliente', usar 'razon_social' como respaldo
            elif 'razon_social' in df.columns:
                df.rename(columns={'razon_social': 'deudor'}, inplace=True)
            
            # Renombrar otras columnas importantes
            column_rename = {
                'linea_de_negocio': 'linea_negocio',
                'vendedor': 'vendedor',
                'saldo': 'saldo_adeudado',
                'saldo_usd': 'saldo_adeudado',
                'estatus': 'estatus',
                'vencimiento': 'fecha_vencimiento'
            }
            
            for original, nuevo in column_rename.items():
                if original in df.columns and nuevo not in df.columns:
                    df.rename(columns={original: nuevo}, inplace=True)
        
        # Agregar origen
        df_vigentes['origen'] = 'VIGENTE'
        df_vencidas['origen'] = 'VENCIDA'
        
        # Unificar columnas
        common_cols = list(set(df_vigentes.columns) & set(df_vencidas.columns))
        df_deudas = pd.concat([
            df_vigentes[common_cols], 
            df_vencidas[common_cols]
        ], ignore_index=True)
        
        # Limpieza
        df_deudas = df_deudas.dropna(axis=1, how='all')
        
        # Manejar duplicados
        duplicados = df_deudas.columns[df_deudas.columns.duplicated()]
        if not duplicados.empty:
            df_deudas = df_deudas.loc[:, ~df_deudas.columns.duplicated(keep='first')]

        # Validar columna clave
        if 'saldo_adeudado' not in df_deudas.columns:
            st.error("❌ No existe columna de saldo en los datos.")
            st.write("Columnas disponibles:", df_deudas.columns.tolist())
            return
            
        # Validar columna de deudor
        if 'deudor' not in df_deudas.columns:
            st.error("❌ No se encontró columna para identificar deudores.")
            st.write("Se esperaba 'cliente' o 'razon_social' en los encabezados")
            return
            
        # Convertir saldo
        saldo_serie = df_deudas['saldo_adeudado'].astype(str)
        saldo_limpio = saldo_serie.str.replace(r'[^\d.]', '', regex=True)
        df_deudas['saldo_adeudado'] = pd.to_numeric(saldo_limpio, errors='coerce').fillna(0)

        # ---------------------------------------------------------------------
        # REPORTE DE DEUDAS A FRADMA (USANDO COLUMNA CORRECTA)
        # ---------------------------------------------------------------------
        st.header("📊 Reporte de Deudas a Fradma")
        
        # KPIs principales
        total_adeudado = df_deudas['saldo_adeudado'].sum()
        
        # Calcular vencimientos para el total
        try:
            mask_vencida = df_deudas['estatus'].str.contains('VENCID', na=False)
            vencida = df_deudas[mask_vencida]['saldo_adeudado'].sum()
            vigente = total_adeudado - vencida
        except:
            vencida = 0
            vigente = total_adeudado
        
        # Métricas principales en columnas
        col1, col2, col3 = st.columns(3)
        col1.metric("💰 Total Adeudado a Fradma", f"${total_adeudado:,.2f}")
        col2.metric("✅ Cartera Vigente", f"${vigente:,.2f}", 
                   delta=f"{(vigente/total_adeudado*100):.1f}%")
        col3.metric("⚠️ Deuda Vencida", f"${vencida:,.2f}", 
                   delta=f"{(vencida/total_adeudado*100):.1f}%",
                   delta_color="inverse")
        
        # Pie Chart: Vigente vs Vencido
        st.subheader("📊 Distribución General de Cartera")
        col_pie1, col_pie2 = st.columns(2)
        
        with col_pie1:
            st.write("**Vigente vs Vencido**")
            fig_vigente = go.Figure(data=[go.Pie(
                labels=['Vigente', 'Vencido'],
                values=[vigente, vencida],
                marker=dict(colors=['#4CAF50', '#F44336']),
                hole=0.4,
                textinfo='label+percent',
                textposition='outside'
            )])
            fig_vigente.update_layout(
                showlegend=True,
                height=350,
                margin=dict(t=20, b=20, l=20, r=20)
            )
            st.plotly_chart(fig_vigente, use_container_width=True)

        # Top 5 deudores (USANDO COLUMNA F - CLIENTE)
        st.subheader("🔝 Principales Deudores (Columna Cliente)")
        top_deudores = df_deudas.groupby('deudor')['saldo_adeudado'].sum().nlargest(5)
        
        # =====================================================================
        # FASE 2: DASHBOARD DE SALUD FINANCIERA
        # =====================================================================
        st.header("🏥 Dashboard de Salud Financiera")
        
        # Calcular métricas de salud
        pct_vigente = (vigente / total_adeudado * 100) if total_adeudado > 0 else 0
        
        # Riesgo alto (>90 días)
        if 'dias_vencido' in df_deudas.columns:
            deuda_alto_riesgo = df_deudas[df_deudas['dias_vencido'] > 90]['saldo_adeudado'].sum()
        else:
            deuda_alto_riesgo = 0
        pct_alto_riesgo = (deuda_alto_riesgo / total_adeudado * 100) if total_adeudado > 0 else 0
        
        # Concentración top 3
        top3_deuda = df_deudas.groupby('deudor')['saldo_adeudado'].sum().nlargest(3).sum()
        pct_concentracion = (top3_deuda / total_adeudado * 100) if total_adeudado > 0 else 0
        
        # Calcular Score de Salud (0-100)
        # Fórmula: 100 - (peso_riesgo_alto * 0.5 + peso_concentracion * 0.3 + peso_vencido * 0.2)
        score_salud = 100 - (pct_alto_riesgo * 0.5 + min(pct_concentracion, 100) * 0.3 + (100 - pct_vigente) * 0.2)
        score_salud = max(0, min(100, score_salud))  # Limitar entre 0-100
        
        # Determinar color del score
        if score_salud >= 80:
            score_color = "#4CAF50"  # Verde
            score_status = "Excelente"
        elif score_salud >= 60:
            score_color = "#8BC34A"  # Verde claro
            score_status = "Bueno"
        elif score_salud >= 40:
            score_color = "#FFEB3B"  # Amarillo
            score_status = "Regular"
        elif score_salud >= 20:
            score_color = "#FF9800"  # Naranja
            score_status = "Malo"
        else:
            score_color = "#F44336"  # Rojo
            score_status = "Crítico"
        
        # Gauge principal de salud
        col_health1, col_health2 = st.columns([1, 2])
        
        with col_health1:
            st.write("### 💚 Score de Salud Financiera")
            fig_health = go.Figure(go.Indicator(
                mode="gauge+number+delta",
                value=score_salud,
                domain={'x': [0, 1], 'y': [0, 1]},
                title={'text': f"<b>{score_status}</b>", 'font': {'size': 20}},
                number={'suffix': '', 'font': {'size': 40}},
                gauge={
                    'axis': {'range': [None, 100], 'tickwidth': 2, 'tickcolor': "darkgray"},
                    'bar': {'color': score_color, 'thickness': 0.8},
                    'bgcolor': "white",
                    'borderwidth': 2,
                    'bordercolor': "gray",
                    'steps': [
                        {'range': [0, 20], 'color': '#FFCDD2'},
                        {'range': [20, 40], 'color': '#FFE0B2'},
                        {'range': [40, 60], 'color': '#FFF9C4'},
                        {'range': [60, 80], 'color': '#DCEDC8'},
                        {'range': [80, 100], 'color': '#C8E6C9'}
                    ],
                    'threshold': {
                        'line': {'color': "black", 'width': 4},
                        'thickness': 0.75,
                        'value': 60
                    }
                }
            ))
            fig_health.update_layout(
                height=350,
                margin=dict(t=80, b=20, l=20, r=20)
            )
            st.plotly_chart(fig_health, use_container_width=True)
            
            # Métricas auxiliares
            st.metric("Liquidez (Vigente)", f"{pct_vigente:.1f}%", 
                     delta=f"{pct_vigente - 70:.1f}pp vs objetivo 70%")
        
        with col_health2:
            st.write("### 📊 Indicadores Clave de Desempeño (KPIs)")
            
            # Calcular KPIs
            # DSO (Days Sales Outstanding) - Aproximación: (CxC / Ventas diarias promedio)
            # Como no tenemos ventas, usamos un estimado de 90 días como benchmark
            dso_estimado = 45  # Placeholder - necesitaría datos de ventas reales
            dso_objetivo = 30
            dso_status = "🟢" if dso_estimado <= dso_objetivo else "🟡" if dso_estimado <= 45 else "🔴"
            
            # Índice de Morosidad
            indice_morosidad = (vencida / total_adeudado * 100) if total_adeudado > 0 else 0
            morosidad_objetivo = 5
            morosidad_status = "🟢" if indice_morosidad <= morosidad_objetivo else "🟡" if indice_morosidad <= 15 else "🔴"
            
            # Rotación CxC (estimado)
            rotacion_cxc = 8  # Placeholder - necesitaría datos de ventas
            rotacion_objetivo = 12
            rotacion_status = "🟢" if rotacion_cxc >= rotacion_objetivo else "🟡" if rotacion_cxc >= 8 else "🔴"
            
            # Índice de Concentración
            concentracion_status = "🟢" if pct_concentracion <= 30 else "🟡" if pct_concentracion <= 50 else "🔴"
            
            # Tabla de KPIs
            kpis_data = {
                'KPI': [
                    'DSO (Días de Cobro)',
                    'Índice de Morosidad',
                    'Rotación CxC',
                    'Concentración Top 3',
                    'Riesgo Alto (>90 días)'
                ],
                'Valor Actual': [
                    f"{dso_estimado} días",
                    f"{indice_morosidad:.1f}%",
                    f"{rotacion_cxc}x/año",
                    f"{pct_concentracion:.1f}%",
                    f"{pct_alto_riesgo:.1f}%"
                ],
                'Objetivo': [
                    f"<{dso_objetivo} días",
                    f"<{morosidad_objetivo}%",
                    f">{rotacion_objetivo}x",
                    "<30%",
                    "<10%"
                ],
                'Estado': [
                    dso_status,
                    morosidad_status,
                    rotacion_status,
                    concentracion_status,
                    "🟢" if pct_alto_riesgo <= 10 else "🟡" if pct_alto_riesgo <= 20 else "🔴"
                ],
                'Monto/Detalle': [
                    f"${total_adeudado / (dso_estimado if dso_estimado > 0 else 1):,.0f}/día",
                    f"${vencida:,.0f}",
                    f"${total_adeudado / (rotacion_cxc if rotacion_cxc > 0 else 1):,.0f}/rotación",
                    f"${top3_deuda:,.0f}",
                    f"${deuda_alto_riesgo:,.0f}"
                ]
            }
            
            df_kpis = pd.DataFrame(kpis_data)
            
            # Mostrar tabla con estilo
            st.dataframe(
                df_kpis,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "KPI": st.column_config.TextColumn("KPI", width="medium"),
                    "Valor Actual": st.column_config.TextColumn("Valor Actual", width="small"),
                    "Objetivo": st.column_config.TextColumn("Objetivo", width="small"),
                    "Estado": st.column_config.TextColumn("Estado", width="small"),
                    "Monto/Detalle": st.column_config.TextColumn("Monto/Detalle", width="medium")
                }
            )
            
            # Nota informativa
            st.info("💡 **Nota:** DSO y Rotación CxC son estimados. Para cálculos precisos, se requieren datos de ventas.")
        
        st.write("---")
        
        # =====================================================================
        # FASE 3: ALERTAS INTELIGENTES Y PRIORIDADES DE COBRANZA
        # =====================================================================
        st.header("🚨 Alertas Inteligentes")
        
        alertas = []
        
        # Alerta 1: Clientes que superan umbral crítico ($50K)
        umbral_critico = 50000
        clientes_criticos = df_deudas.groupby('deudor')['saldo_adeudado'].sum()
        clientes_sobre_umbral = clientes_criticos[clientes_criticos > umbral_critico]
        
        if len(clientes_sobre_umbral) > 0:
            alertas.append({
                'tipo': '⚠️ ALTO MONTO',
                'mensaje': f"{len(clientes_sobre_umbral)} cliente(s) superan ${umbral_critico:,.0f} individual",
                'detalle': ', '.join([f"{c} (${m:,.0f})" for c, m in clientes_sobre_umbral.head(3).items()]),
                'prioridad': 'ALTA'
            })
        
        # Alerta 2: Deuda >90 días significativa
        if pct_alto_riesgo > 15:
            alertas.append({
                'tipo': '🔴 RIESGO CRÍTICO',
                'mensaje': f"Deuda >90 días representa {pct_alto_riesgo:.1f}% del total",
                'detalle': f"${deuda_alto_riesgo:,.2f} en alto riesgo de incobrabilidad",
                'prioridad': 'URGENTE'
            })
        
        # Alerta 3: Alta concentración
        if pct_concentracion > 50:
            top3_clientes = df_deudas.groupby('deudor')['saldo_adeudado'].sum().nlargest(3)
            alertas.append({
                'tipo': '📊 CONCENTRACIÓN',
                'mensaje': f"Top 3 clientes concentran {pct_concentracion:.1f}% de la cartera",
                'detalle': f"Riesgo alto de dependencia: {', '.join(top3_clientes.index.tolist())}",
                'prioridad': 'MEDIA'
            })
        
        # Alerta 4: Clientes con aumento significativo
        # (Requeriría histórico - simulamos detección)
        if 'dias_vencido' in df_deudas.columns:
            clientes_deterioro = df_deudas[df_deudas['dias_vencido'] > 120].groupby('deudor')['saldo_adeudado'].sum()
            if len(clientes_deterioro) > 0:
                alertas.append({
                    'tipo': '📈 DETERIORO',
                    'mensaje': f"{len(clientes_deterioro)} cliente(s) con deuda >120 días",
                    'detalle': f"Total en deterioro severo: ${clientes_deterioro.sum():,.2f}",
                    'prioridad': 'ALTA'
                })
        
        # Alerta 5: Score de salud bajo
        if score_salud < 40:
            alertas.append({
                'tipo': '🏥 SALUD CRÍTICA',
                'mensaje': f"Score de salud financiera: {score_salud:.0f}/100 ({score_status})",
                'detalle': "Se requiere acción inmediata de recuperación",
                'prioridad': 'URGENTE'
            })
        
        # Mostrar alertas
        if alertas:
            # Ordenar por prioridad
            prioridad_orden = {'URGENTE': 0, 'ALTA': 1, 'MEDIA': 2}
            alertas_ordenadas = sorted(alertas, key=lambda x: prioridad_orden.get(x['prioridad'], 3))
            
            for alerta in alertas_ordenadas:
                color = {
                    'URGENTE': '#F44336',
                    'ALTA': '#FF9800',
                    'MEDIA': '#FFC107'
                }.get(alerta['prioridad'], '#9E9E9E')
                
                st.markdown(
                    f"""
                    <div style="background-color:{color}20; border-left: 5px solid {color}; padding: 15px; margin: 10px 0; border-radius: 5px;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <div>
                                <h4 style="margin: 0; color: {color};">{alerta['tipo']}</h4>
                                <p style="margin: 5px 0 0 0; font-size: 16px; font-weight: bold;">{alerta['mensaje']}</p>
                                <p style="margin: 5px 0 0 0; font-size: 14px; color: #666;">{alerta['detalle']}</p>
                            </div>
                            <span style="background-color: {color}; color: white; padding: 5px 15px; border-radius: 20px; font-weight: bold; font-size: 12px;">
                                {alerta['prioridad']}
                            </span>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
        else:
            st.success("✅ No hay alertas críticas. La cartera está bajo control.")
        
        st.write("---")
        
        # =====================================================================
        # PRIORIDADES DE COBRANZA
        # =====================================================================
        st.header("📋 Prioridades de Cobranza")
        
        # Calcular score de prioridad para cada deudor
        deudor_prioridad = []
        
        for deudor in df_deudas['deudor'].unique():
            deudor_data = df_deudas[df_deudas['deudor'] == deudor]
            monto_total = deudor_data['saldo_adeudado'].sum()
            
            # Calcular días promedio vencido
            if 'dias_vencido' in deudor_data.columns:
                dias_prom = deudor_data['dias_vencido'].mean()
                dias_max = deudor_data['dias_vencido'].max()
            else:
                dias_prom = 0
                dias_max = 0
            
            # Score de prioridad (0-100)
            # Factores: monto (40%), días vencido (40%), cantidad documentos (20%)
            score_monto = min((monto_total / 100000) * 100, 100) * 0.4
            score_dias = min((dias_max / 180) * 100, 100) * 0.4
            score_docs = min((len(deudor_data) / 10) * 100, 100) * 0.2
            
            score_prioridad = score_monto + score_dias + score_docs
            
            # Clasificar nivel
            if score_prioridad >= 75:
                nivel = "🔴 URGENTE"
                nivel_num = 1
            elif score_prioridad >= 50:
                nivel = "🟠 ALTA"
                nivel_num = 2
            elif score_prioridad >= 25:
                nivel = "🟡 MEDIA"
                nivel_num = 3
            else:
                nivel = "🟢 BAJA"
                nivel_num = 4
            
            deudor_prioridad.append({
                'deudor': deudor,
                'monto': monto_total,
                'dias_max': dias_max,
                'documentos': len(deudor_data),
                'score': score_prioridad,
                'nivel': nivel,
                'nivel_num': nivel_num
            })
        
        # Crear DataFrame y ordenar
        df_prioridades = pd.DataFrame(deudor_prioridad)
        df_prioridades = df_prioridades.sort_values(['nivel_num', 'score'], ascending=[True, False])
        
        # Mostrar top 10 prioridades
        st.write("### 🎯 Top 10 Acciones Inmediatas")
        
        df_top_prioridades = df_prioridades.head(10)[['nivel', 'deudor', 'monto', 'dias_max', 'documentos', 'score']].copy()
        df_top_prioridades['monto'] = df_top_prioridades['monto'].apply(lambda x: f"${x:,.2f}")
        df_top_prioridades['dias_max'] = df_top_prioridades['dias_max'].apply(lambda x: f"{int(x)} días")
        df_top_prioridades['score'] = df_top_prioridades['score'].apply(lambda x: f"{x:.1f}/100")
        
        df_top_prioridades.columns = ['Prioridad', 'Cliente', 'Monto Adeudado', 'Días Máx.', 'Docs.', 'Score']
        
        st.dataframe(
            df_top_prioridades,
            use_container_width=True,
            hide_index=True
        )
        
        # Resumen de acciones por nivel
        col_acc1, col_acc2, col_acc3, col_acc4 = st.columns(4)
        
        urgente_count = len(df_prioridades[df_prioridades['nivel_num'] == 1])
        alta_count = len(df_prioridades[df_prioridades['nivel_num'] == 2])
        media_count = len(df_prioridades[df_prioridades['nivel_num'] == 3])
        baja_count = len(df_prioridades[df_prioridades['nivel_num'] == 4])
        
        col_acc1.metric("🔴 Urgente", urgente_count, 
                       delta=f"${df_prioridades[df_prioridades['nivel_num'] == 1]['monto'].sum():,.0f}")
        col_acc2.metric("🟠 Alta", alta_count,
                       delta=f"${df_prioridades[df_prioridades['nivel_num'] == 2]['monto'].sum():,.0f}")
        col_acc3.metric("🟡 Media", media_count,
                       delta=f"${df_prioridades[df_prioridades['nivel_num'] == 3]['monto'].sum():,.0f}")
        col_acc4.metric("🟢 Baja", baja_count,
                       delta=f"${df_prioridades[df_prioridades['nivel_num'] == 4]['monto'].sum():,.0f}")
        
        # Recomendaciones
        st.write("### 💡 Recomendaciones de Acción")
        st.markdown("""
        **Para casos URGENTES (🔴):**
        - Contacto inmediato con cliente
        - Evaluación de plan de pagos o reestructuración
        - Considerar suspensión de crédito hasta regularización
        
        **Para casos de prioridad ALTA (🟠):**
        - Seguimiento telefónico en próximos 3 días
        - Enviar estado de cuenta actualizado
        - Establecer compromiso de pago con fecha específica
        
        **Para casos de prioridad MEDIA (🟡):**
        - Recordatorio por correo electrónico
        - Monitoreo semanal
        
        **Para casos de prioridad BAJA (🟢):**
        - Seguimiento de rutina
        - Mantener comunicación regular
        """)
        
        st.write("---")
        
        # Top 5 deudores con tabla mejorada
        st.dataframe(top_deudores.reset_index().rename(
            columns={'deudor': 'Cliente (Col F)', 'saldo_adeudado': 'Monto Adeudado ($)'}
        ).style.format({'Monto Adeudado ($)': '${:,.2f}'}))
        
        # Gráfico de concentración
        st.bar_chart(top_deudores)
        
        # =====================================================================
        # FASE 4: ANÁLISIS POR LÍNEA DE NEGOCIO
        # =====================================================================
        if 'linea_negocio' in df_deudas.columns or 'linea_de_negocio' in df_deudas.columns:
            st.header("🏭 Análisis por Línea de Negocio")
            
            # Normalizar nombre de columna
            col_linea = 'linea_negocio' if 'linea_negocio' in df_deudas.columns else 'linea_de_negocio'
            
            # Limpiar valores nulos
            df_lineas = df_deudas[df_deudas[col_linea].notna()].copy()
            
            if len(df_lineas) > 0:
                # Calcular métricas por línea
                lineas_metricas = []
                
                for linea in df_lineas[col_linea].unique():
                    linea_data = df_lineas[df_lineas[col_linea] == linea]
                    total_linea = linea_data['saldo_adeudado'].sum()
                    
                    # Calcular vencido de esta línea
                    if 'dias_vencido' in linea_data.columns:
                        vencido_linea = linea_data[linea_data['dias_vencido'] > 0]['saldo_adeudado'].sum()
                        pct_morosidad = (vencido_linea / total_linea * 100) if total_linea > 0 else 0
                        alto_riesgo_linea = linea_data[linea_data['dias_vencido'] > 90]['saldo_adeudado'].sum()
                        pct_alto_riesgo = (alto_riesgo_linea / total_linea * 100) if total_linea > 0 else 0
                    else:
                        pct_morosidad = 0
                        pct_alto_riesgo = 0
                    
                    # Concentración (top cliente de la línea)
                    top_cliente_linea = linea_data.groupby('deudor')['saldo_adeudado'].sum().max()
                    pct_concentracion_linea = (top_cliente_linea / total_linea * 100) if total_linea > 0 else 0
                    
                    lineas_metricas.append({
                        'linea': linea,
                        'total': total_linea,
                        'pct_morosidad': pct_morosidad,
                        'pct_alto_riesgo': pct_alto_riesgo,
                        'pct_concentracion': pct_concentracion_linea,
                        'clientes': linea_data['deudor'].nunique(),
                        'docs': len(linea_data)
                    })
                
                df_lineas_metricas = pd.DataFrame(lineas_metricas)
                df_lineas_metricas = df_lineas_metricas.sort_values('total', ascending=False)
                
                # Gauges por línea de negocio
                st.write("### 🎯 Indicadores por Línea de Negocio")
                
                # Mostrar gauges de CxC por línea (top 6)
                top_lineas = df_lineas_metricas.head(6)
                
                for i in range(0, len(top_lineas), 3):
                    cols_linea = st.columns(3)
                    
                    for j in range(3):
                        if i + j < len(top_lineas):
                            row = top_lineas.iloc[i + j]
                            linea = row['linea']
                            total = row['total']
                            pct_total = (total / total_adeudado * 100) if total_adeudado > 0 else 0
                            morosidad = row['pct_morosidad']
                            
                            # Color según morosidad
                            if morosidad < 10:
                                color_linea = "#4CAF50"
                            elif morosidad < 25:
                                color_linea = "#FFEB3B"
                            elif morosidad < 50:
                                color_linea = "#FF9800"
                            else:
                                color_linea = "#F44336"
                            
                            with cols_linea[j]:
                                fig_linea = go.Figure(go.Indicator(
                                    mode="gauge+number",
                                    value=pct_total,
                                    domain={'x': [0, 1], 'y': [0, 1]},
                                    title={'text': f"<b>{linea}</b><br>${total:,.0f}", 'font': {'size': 12}},
                                    number={'suffix': '%', 'font': {'size': 18}},
                                    gauge={
                                        'axis': {'range': [None, 100], 'tickwidth': 1},
                                        'bar': {'color': color_linea, 'thickness': 0.75},
                                        'bgcolor': "white",
                                        'borderwidth': 1,
                                        'bordercolor': "gray",
                                        'steps': [
                                            {'range': [0, 25], 'color': '#E8F5E9'},
                                            {'range': [25, 50], 'color': '#FFF9C4'},
                                            {'range': [50, 100], 'color': '#FFEBEE'}
                                        ]
                                    }
                                ))
                                fig_linea.update_layout(
                                    height=200,
                                    margin=dict(t=60, b=10, l=10, r=10)
                                )
                                st.plotly_chart(fig_linea, use_container_width=True)
                                st.caption(f"Morosidad: {morosidad:.1f}% | Clientes: {row['clientes']}")
                
                st.write("---")
                
                # Tabla comparativa de líneas
                st.write("### 📊 Comparativa de Líneas de Negocio")
                
                df_comparativa = df_lineas_metricas.copy()
                df_comparativa['% del Total'] = (df_comparativa['total'] / total_adeudado * 100)
                
                # Agregar semáforos de morosidad
                df_comparativa['Alerta Morosidad'] = df_comparativa['pct_morosidad'].apply(
                    lambda x: "🟢" if x < 10 else "🟡" if x < 25 else "🟠" if x < 50 else "🔴"
                )
                
                df_comparativa['Alerta Riesgo Alto'] = df_comparativa['pct_alto_riesgo'].apply(
                    lambda x: "🟢" if x < 5 else "🟡" if x < 15 else "🟠" if x < 30 else "🔴"
                )
                
                # Formatear para display
                df_display = df_comparativa[[
                    'linea', 'total', '% del Total', 'pct_morosidad', 
                    'Alerta Morosidad', 'pct_alto_riesgo', 'Alerta Riesgo Alto',
                    'pct_concentracion', 'clientes', 'docs'
                ]].copy()
                
                df_display['total'] = df_display['total'].apply(lambda x: f"${x:,.2f}")
                df_display['% del Total'] = df_display['% del Total'].apply(lambda x: f"{x:.1f}%")
                df_display['pct_morosidad'] = df_display['pct_morosidad'].apply(lambda x: f"{x:.1f}%")
                df_display['pct_alto_riesgo'] = df_display['pct_alto_riesgo'].apply(lambda x: f"{x:.1f}%")
                df_display['pct_concentracion'] = df_display['pct_concentracion'].apply(lambda x: f"{x:.1f}%")
                
                df_display.columns = [
                    'Línea', 'Monto Total', '% Total', 'Morosidad', '🚦',
                    'Riesgo Alto', '🚦', 'Concentración', 'Clientes', 'Docs'
                ]
                
                st.dataframe(df_display, use_container_width=True, hide_index=True)
                
                # Identificar líneas problemáticas
                st.write("### ⚠️ Líneas que Requieren Atención")
                
                lineas_problematicas = df_lineas_metricas[
                    (df_lineas_metricas['pct_morosidad'] > 25) | 
                    (df_lineas_metricas['pct_alto_riesgo'] > 15)
                ].copy()
                
                if len(lineas_problematicas) > 0:
                    for _, linea_prob in lineas_problematicas.iterrows():
                        problemas = []
                        if linea_prob['pct_morosidad'] > 25:
                            problemas.append(f"Morosidad alta: {linea_prob['pct_morosidad']:.1f}%")
                        if linea_prob['pct_alto_riesgo'] > 15:
                            problemas.append(f"Riesgo alto: {linea_prob['pct_alto_riesgo']:.1f}%")
                        if linea_prob['pct_concentracion'] > 50:
                            problemas.append(f"Alta concentración: {linea_prob['pct_concentracion']:.1f}%")
                        
                        st.warning(f"**{linea_prob['linea']}**: {' | '.join(problemas)}")
                else:
                    st.success("✅ Todas las líneas de negocio están dentro de parámetros aceptables")
                
                # Gráfico de comparación
                st.write("### 📈 Comparación Visual por Línea")
                
                col_chart1, col_chart2 = st.columns(2)
                
                with col_chart1:
                    # Gráfico de monto por línea
                    fig_monto_lineas = px.bar(
                        df_lineas_metricas,
                        x='linea',
                        y='total',
                        title='Monto CxC por Línea de Negocio',
                        labels={'linea': 'Línea', 'total': 'Monto ($)'},
                        color='pct_morosidad',
                        color_continuous_scale=['green', 'yellow', 'orange', 'red']
                    )
                    fig_monto_lineas.update_layout(height=400)
                    st.plotly_chart(fig_monto_lineas, use_container_width=True)
                
                with col_chart2:
                    # Gráfico de morosidad por línea
                    fig_morosidad_lineas = px.bar(
                        df_lineas_metricas,
                        x='linea',
                        y='pct_morosidad',
                        title='Índice de Morosidad por Línea',
                        labels={'linea': 'Línea', 'pct_morosidad': 'Morosidad (%)'},
                        color='pct_morosidad',
                        color_continuous_scale=['green', 'yellow', 'orange', 'red']
                    )
                    fig_morosidad_lineas.update_layout(height=400)
                    st.plotly_chart(fig_morosidad_lineas, use_container_width=True)
                
                st.write("---")
            else:
                st.info("ℹ️ No hay datos de línea de negocio disponibles para análisis")
        else:
            st.info("ℹ️ No se encontró información de línea de negocio en los datos")

        # Análisis de riesgo por antigüedad
        st.subheader("📅 Perfil de Riesgo por Antigüedad")
        if 'fecha_vencimiento' in df_deudas.columns:
            try:
                df_deudas['fecha_vencimiento'] = pd.to_datetime(
                    df_deudas['fecha_vencimiento'], errors='coerce', dayfirst=True
                )
                
                hoy = pd.Timestamp.today()
                df_deudas['dias_vencido'] = (hoy - df_deudas['fecha_vencimiento']).dt.days
                
                # Clasificación de riesgo con colores
                bins = [-np.inf, 0, 30, 60, 90, 180, np.inf]
                labels = ['Por vencer', 
                         '1-30 días', 
                         '31-60 días', 
                         '61-90 días', 
                         '91-180 días', 
                         '>180 días']
                colores = ['#4CAF50', '#8BC34A', '#FFEB3B', '#FF9800', '#F44336', '#B71C1C']  # Verde, verde claro, amarillo, naranja, rojo, rojo oscuro
                
                df_deudas['nivel_riesgo'] = pd.cut(
                    df_deudas['dias_vencido'], 
                    bins=bins, 
                    labels=labels
                )
                
                # Resumen de riesgo
                riesgo_df = df_deudas.groupby('nivel_riesgo')['saldo_adeudado'].sum().reset_index()
                riesgo_df['porcentaje'] = (riesgo_df['saldo_adeudado'] / total_adeudado) * 100
                
                # Ordenar por nivel de riesgo
                riesgo_df = riesgo_df.sort_values('nivel_riesgo')
                
                # Pie Chart: Distribución por antigüedad
                with col_pie2:
                    st.write("**Distribución por Antigüedad**")
                    fig_antiguedad = go.Figure(data=[go.Pie(
                        labels=riesgo_df['nivel_riesgo'].tolist(),
                        values=riesgo_df['saldo_adeudado'].tolist(),
                        marker=dict(colors=colores),
                        hole=0.4,
                        textinfo='label+percent',
                        textposition='outside'
                    )])
                    fig_antiguedad.update_layout(
                        showlegend=True,
                        height=350,
                        margin=dict(t=20, b=20, l=20, r=20)
                    )
                    st.plotly_chart(fig_antiguedad, use_container_width=True)
                
                # Gauges por categoría de riesgo
                st.write("### 🎯 Indicadores de Riesgo por Antigüedad")
                
                # Crear gauges en filas de 3
                num_categorias = len(riesgo_df)
                for i in range(0, num_categorias, 3):
                    cols_gauge = st.columns(3)
                    
                    for j in range(3):
                        if i + j < num_categorias:
                            row = riesgo_df.iloc[i + j]
                            nivel = row['nivel_riesgo']
                            pct = row['porcentaje']
                            monto = row['saldo_adeudado']
                            color = colores[i + j]
                            
                            with cols_gauge[j]:
                                # Crear gauge con plotly
                                fig_gauge = go.Figure(go.Indicator(
                                    mode="gauge+number+delta",
                                    value=pct,
                                    domain={'x': [0, 1], 'y': [0, 1]},
                                    title={'text': f"{nivel}<br>${monto:,.0f}", 'font': {'size': 14}},
                                    delta={'reference': 100/num_categorias, 'suffix': 'pp'},
                                    number={'suffix': '%', 'font': {'size': 20}},
                                    gauge={
                                        'axis': {'range': [None, 100], 'tickwidth': 1, 'tickcolor': "darkgray"},
                                        'bar': {'color': color},
                                        'bgcolor': "white",
                                        'borderwidth': 2,
                                        'bordercolor': "gray",
                                        'steps': [
                                            {'range': [0, 50], 'color': '#E8F5E9'},
                                            {'range': [50, 100], 'color': '#FFEBEE'}
                                        ],
                                        'threshold': {
                                            'line': {'color': "red", 'width': 4},
                                            'thickness': 0.75,
                                            'value': 100/num_categorias
                                        }
                                    }
                                ))
                                fig_gauge.update_layout(
                                    height=250,
                                    margin=dict(t=50, b=0, l=20, r=20)
                                )
                                st.plotly_chart(fig_gauge, use_container_width=True)
                
                st.write("---")
                
                # Mostrar tabla resumen (reemplaza tarjetas HTML)
                st.write("### 📋 Resumen Detallado por Categoría")
                resumen_tabla = riesgo_df.copy()
                resumen_tabla['Monto'] = resumen_tabla['saldo_adeudado'].apply(lambda x: f"${x:,.2f}")
                resumen_tabla['% del Total'] = resumen_tabla['porcentaje'].apply(lambda x: f"{x:.1f}%")
                resumen_tabla = resumen_tabla[['nivel_riesgo', 'Monto', '% del Total']]
                resumen_tabla.columns = ['Categoría', 'Monto Adeudado', '% del Total']
                st.dataframe(resumen_tabla, use_container_width=True, hide_index=True)
                
                # Gráfico de barras con colores por categoría
                st.write("### 📊 Distribución de Deuda por Antigüedad")
                fig, ax = plt.subplots()
                bars = ax.bar(riesgo_df['nivel_riesgo'], riesgo_df['saldo_adeudado'], color=colores)
                ax.set_title('Distribución por Antigüedad de Deuda')
                ax.set_ylabel('Monto Adeudado ($)')
                ax.yaxis.set_major_formatter('${x:,.0f}')
                plt.xticks(rotation=45)
                
                # Agregar etiquetas de valor
                for bar in bars:
                    height = bar.get_height()
                    ax.annotate(f'${height:,.0f}',
                                xy=(bar.get_x() + bar.get_width() / 2, height),
                                xytext=(0, 3),  # 3 points vertical offset
                                textcoords="offset points",
                                ha='center', va='bottom')
                
                st.pyplot(fig)
                
            except Exception as e:
                st.error(f"❌ Error en análisis de vencimientos: {str(e)}")
        else:
            st.warning("ℹ️ No se encontró columna de vencimiento")
            
        # =====================================================================
        # ANÁLISIS DE AGENTES (VENDEDORES) CON LÓGICA DE ANTIGÜEDAD
        # =====================================================================
        st.subheader("👤 Distribución de Deuda por Agente")
        
        if 'vendedor' in df_deudas.columns:
            # Asegurar que tenemos los días vencidos calculados
            if 'dias_vencido' not in df_deudas.columns and 'fecha_vencimiento' in df_deudas.columns:
                try:
                    hoy = pd.Timestamp.today()
                    df_deudas['dias_vencido'] = (hoy - pd.to_datetime(df_deudas['fecha_vencimiento'], errors='coerce')).dt.days
                except:
                    pass
            
            if 'dias_vencido' in df_deudas.columns:
                # Definir categorías y colores para agentes
                bins_agentes = [-np.inf, 0, 30, 60, 90, np.inf]
                labels_agentes = ['Por vencer', '1-30 días', '31-60 días', '61-90 días', '>90 días']
                colores_agentes = ['#4CAF50', '#8BC34A', '#FFEB3B', '#FF9800', '#F44336']  # Verde, verde claro, amarillo, naranja, rojo
                
                # Clasificar la deuda de los agentes
                df_deudas['categoria_agente'] = pd.cut(
                    df_deudas['dias_vencido'], 
                    bins=bins_agentes, 
                    labels=labels_agentes
                )
                
                # Agrupar por agente y categoría
                agente_categoria = df_deudas.groupby(['vendedor', 'categoria_agente'])['saldo_adeudado'].sum().unstack().fillna(0)
                
                # Ordenar por el total de deuda
                agente_categoria['Total'] = agente_categoria.sum(axis=1)
                agente_categoria = agente_categoria.sort_values('Total', ascending=False)
                
                # Crear gráfico de barras apiladas
                st.write("### 📊 Distribución por Agente y Antigüedad")
                fig, ax = plt.subplots(figsize=(12, 6))
                
                # Preparar datos para el gráfico
                bottom = np.zeros(len(agente_categoria))
                for i, categoria in enumerate(labels_agentes):
                    if categoria in agente_categoria.columns:
                        valores = agente_categoria[categoria]
                        ax.bar(agente_categoria.index, valores, bottom=bottom, label=categoria, color=colores_agentes[i])
                        bottom += valores
                
                # Personalizar gráfico
                ax.set_title('Deuda por Agente y Antigüedad', fontsize=14)
                ax.set_ylabel('Monto Adeudado ($)', fontsize=12)
                ax.set_xlabel('Agente', fontsize=12)
                ax.tick_params(axis='x', rotation=45)
                ax.legend(title='Días Vencidos', loc='upper right')
                ax.yaxis.set_major_formatter('${x:,.0f}')
                
                st.pyplot(fig)
                
                # Mostrar tabla resumen
                st.write("### 📋 Resumen por Agente")
                resumen_agente = agente_categoria.copy()
                resumen_agente = resumen_agente.sort_values('Total', ascending=False)
                
                # Formatear valores
                for col in resumen_agente.columns:
                    if col != 'Total':
                        resumen_agente[col] = resumen_agente[col].apply(lambda x: f"${x:,.2f}" if x > 0 else "")
                resumen_agente['Total'] = resumen_agente['Total'].apply(lambda x: f"${x:,.2f}")
                
                st.dataframe(resumen_agente)
                
            else:
                st.warning("ℹ️ No se pudo calcular la antigüedad para los agentes")
        else:
            st.warning("ℹ️ No se encontró información de agentes (vendedores)")

        # Desglose detallado por deudor (CLIENTE - COLUMNA F)
        st.subheader("🔍 Detalle Completo por Deudor (Columna Cliente)")
        deudores = df_deudas['deudor'].unique().tolist()
        selected_deudor = st.selectbox("Seleccionar Deudor", deudores)
        
        # Filtrar datos
        deudor_df = df_deudas[df_deudas['deudor'] == selected_deudor]
        total_deudor = deudor_df['saldo_adeudado'].sum()
        
        st.metric(f"Total Adeudado por {selected_deudor}", f"${total_deudor:,.2f}")
        
        # Mostrar documentos pendientes
        st.write("**Documentos pendientes:**")
        cols = ['fecha_vencimiento', 'saldo_adeudado', 'estatus', 'dias_vencido'] 
        cols = [c for c in cols if c in deudor_df.columns]
        st.dataframe(deudor_df[cols].sort_values('fecha_vencimiento', ascending=False))

        # Resumen ejecutivo
        st.subheader("📝 Resumen Ejecutivo")
        st.write(f"Fradma tiene **${total_adeudado:,.2f}** en deudas pendientes de cobro")
        st.write(f"El principal deudor es **{top_deudores.index[0]}** con **${top_deudores.iloc[0]:,.2f}**")
        
        if 'dias_vencido' in df_deudas.columns:
            deuda_vencida = df_deudas[df_deudas['dias_vencido'] > 0]['saldo_adeudado'].sum()
            st.write(f"- **${deuda_vencida:,.2f} en deuda vencida**")
        
        st.write("Este reporte se basa en la columna 'Cliente' (F) para identificar deudores.")

    except Exception as e:
        st.error(f"❌ Error crítico: {str(e)}")
        import traceback
        st.error(traceback.format_exc())