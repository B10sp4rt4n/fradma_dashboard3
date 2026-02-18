"""
Utilidades para exportar reportes del dashboard a Excel y PDF.

Proporciona funciones para generar reportes profesionales con formato
que pueden compartirse con stakeholders.
"""

import pandas as pd
import io
from typing import Dict, Optional, List
from datetime import datetime
from utils.formatos import formato_moneda, formato_porcentaje


def crear_excel_metricas_cxc(
    metricas: Dict,
    df_detalle: pd.DataFrame,
    df_antiguedad: Optional[pd.DataFrame] = None,
    nombre_empresa: str = "FRADMA"
) -> bytes:
    """
    Crea un archivo Excel con múltiples hojas de métricas CxC.
    
    Args:
        metricas: Diccionario con métricas calculadas
        df_detalle: DataFrame con detalle de cuentas por cobrar
        df_antiguedad: DataFrame con tabla de antigüedad (opcional)
        nombre_empresa: Nombre de la empresa para el reporte
        
    Returns:
        bytes: Contenido del archivo Excel
        
    Examples:
        >>> excel_bytes = crear_excel_metricas_cxc(metricas, df_detalle)
        >>> with open('reporte_cxc.xlsx', 'wb') as f:
        ...     f.write(excel_bytes)
    """
    output = io.BytesIO()
    
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        workbook = writer.book
        
        # Formatos personalizados
        formato_titulo = workbook.add_format({
            'bold': True,
            'font_size': 16,
            'font_color': '#1f77b4',
            'align': 'center'
        })
        
        formato_header = workbook.add_format({
            'bold': True,
            'bg_color': '#1f77b4',
            'font_color': 'white',
            'align': 'center',
            'border': 1
        })
        
        formato_moneda = workbook.add_format({
            'num_format': '$#,##0.00',
            'align': 'right'
        })
        
        formato_porcentaje = workbook.add_format({
            'num_format': '0.00%',
            'align': 'right'
        })
        
        formato_numero = workbook.add_format({
            'num_format': '#,##0',
            'align': 'right'
        })
        
        # Hoja 1: Resumen Ejecutivo
        worksheet = workbook.add_worksheet('Resumen Ejecutivo')
        writer.sheets['Resumen Ejecutivo'] = worksheet
        
        # Título
        fecha_actual = datetime.now().strftime("%d/%m/%Y %H:%M")
        worksheet.write('A1', f'Reporte de Cuentas por Cobrar - {nombre_empresa}', formato_titulo)
        worksheet.write('A2', f'Generado: {fecha_actual}')
        worksheet.write('A3', '')
        
        # Métricas principales
        fila = 4
        worksheet.write(fila, 0, 'Métrica', formato_header)
        worksheet.write(fila, 1, 'Valor', formato_header)
        worksheet.set_column('A:A', 30)
        worksheet.set_column('B:B', 20)
        
        metricas_resumen = [
            ('Total Adeudado', metricas.get('total_adeudado', 0), formato_moneda),
            ('Saldo Vigente', metricas.get('vigente', 0), formato_moneda),
            ('Saldo Vencido', metricas.get('vencida', 0), formato_moneda),
            ('% Vigente', metricas.get('pct_vigente', 0) / 100, formato_porcentaje),
            ('% Vencida', metricas.get('pct_vencida', 0) / 100, formato_porcentaje),
            ('', '', None),  # Separador
            ('Vencida 0-30 días', metricas.get('vencida_0_30', 0), formato_moneda),
            ('Vencida 31-60 días', metricas.get('vencida_31_60', 0), formato_moneda),
            ('Vencida 61-90 días', metricas.get('vencida_61_90', 0), formato_moneda),
            ('Crítica (>30 días)', metricas.get('critica', 0), formato_moneda),
            ('Alto Riesgo (>90 días)', metricas.get('alto_riesgo', 0), formato_moneda),
            ('', '', None),  # Separador
            ('Score de Salud', metricas.get('score_salud', 0), formato_numero),
            ('Clasificación', metricas.get('clasificacion_salud', 'N/A'), None),
        ]
        
        for metrica, valor, fmt in metricas_resumen:
            fila += 1
            worksheet.write(fila, 0, metrica)
            if fmt:
                worksheet.write(fila, 1, valor, fmt)
            else:
                worksheet.write(fila, 1, valor)
        
        # Hoja 2: Detalle de Cuentas
        df_export = df_detalle.copy()
        
        # Formatear columnas para export
        if 'dias_overdue' in df_export.columns:
            df_export['dias_overdue'] = df_export['dias_overdue'].fillna(0).astype(int)
        
        df_export.to_excel(writer, sheet_name='Detalle CxC', index=False)
        
        worksheet_detalle = writer.sheets['Detalle CxC']
        
        # Aplicar formato a headers
        for col_num, value in enumerate(df_export.columns.values):
            worksheet_detalle.write(0, col_num, value, formato_header)
        
        # Auto-ajustar anchos de columna
        for idx, col in enumerate(df_export.columns):
            max_len = max(
                df_export[col].astype(str).apply(len).max(),
                len(str(col))
            ) + 2
            worksheet_detalle.set_column(idx, idx, min(max_len, 50))
        
        # Hoja 3: Tabla de Antigüedad (si está disponible)
        if df_antiguedad is not None and not df_antiguedad.empty:
            df_antiguedad.to_excel(writer, sheet_name='Antigüedad', index=False)
            
            worksheet_ant = writer.sheets['Antigüedad']
            
            # Headers
            for col_num, value in enumerate(df_antiguedad.columns.values):
                worksheet_ant.write(0, col_num, value, formato_header)
            
            # Auto-ajustar anchos
            for idx, col in enumerate(df_antiguedad.columns):
                max_len = max(
                    df_antiguedad[col].astype(str).apply(len).max(),
                    len(str(col))
                ) + 2
                worksheet_ant.set_column(idx, idx, min(max_len, 30))
    
    output.seek(0)
    return output.getvalue()


def crear_reporte_html(
    metricas: Dict,
    df_detalle: pd.DataFrame,
    nombre_empresa: str = "FRADMA",
    incluir_graficos: bool = False,
    df_ventas: Optional[pd.DataFrame] = None,
    secciones: Optional[List[str]] = None
) -> str:
    """
    Crea un reporte HTML ejecutivo profesional con métricas configurables.
    
    Args:
        metricas: Diccionario con métricas CxC calculadas
        df_detalle: DataFrame con detalle de cuentas por cobrar
        nombre_empresa: Nombre de la empresa
        incluir_graficos: Si incluir gráficos (requiere matplotlib/plotly)
        df_ventas: DataFrame con datos de ventas (opcional)
        secciones: Lista de secciones a incluir. Opciones:
            - 'resumen_ejecutivo': KPIs principales consolidados
            - 'ventas': Métricas de ventas
            - 'cxc': Métricas de cuentas por cobrar
            - 'antiguedad': Tabla de antigüedad de cartera
            - 'score': Score de salud financiera
            - 'top_clientes': Top deudores
            Si None, incluye todas las secciones disponibles
        
    Returns:
        str: HTML del reporte ejecutivo
        
    Examples:
        >>> # Reporte completo
        >>> html = crear_reporte_html(metricas, df_cxc, df_ventas=df_ventas)
        
        >>> # Solo CxC y score
        >>> html = crear_reporte_html(metricas, df_cxc, 
        ...                          secciones=['cxc', 'score'])
        
        >>> # Reporte ejecutivo conciso
        >>> html = crear_reporte_html(metricas, df_cxc, df_ventas=df_ventas,
        ...                          secciones=['resumen_ejecutivo', 'score'])
    """
    fecha_actual = datetime.now().strftime("%d de %B de %Y, %H:%M")
    
    # Determinar secciones a incluir
    if secciones is None:
        # Por defecto: reporte ejecutivo conciso
        secciones = ['resumen_ejecutivo', 'ventas', 'cxc', 'score']
    
    # Calcular métricas de ventas si están disponibles
    metricas_ventas = {}
    if df_ventas is not None and not df_ventas.empty and 'ventas' in secciones:
        try:
            # Asegurar columna valor_usd
            col_valor = None
            for col in ['valor_usd', 'ventas_usd', 'ventas_usd_con_iva', 'importe', 'monto_usd']:
                if col in df_ventas.columns:
                    col_valor = col
                    break
            
            if col_valor:
                total_ventas = df_ventas[col_valor].sum()
                num_ops = len(df_ventas)
                ticket_prom = total_ventas / num_ops if num_ops > 0 else 0
                
                # Por línea de negocio
                if 'linea_de_negocio' in df_ventas.columns:
                    ventas_linea = df_ventas.groupby('linea_de_negocio')[col_valor].sum().sort_values(ascending=False)
                    top_linea = ventas_linea.index[0] if len(ventas_linea) > 0 else 'N/A'
                    monto_top_linea = ventas_linea.iloc[0] if len(ventas_linea) > 0 else 0
                else:
                    top_linea = 'N/A'
                    monto_top_linea = 0
                
                # Crecimiento si hay fecha
                crecimiento_pct = None
                if 'fecha' in df_ventas.columns:
                    df_ventas_tmp = df_ventas.copy()
                    df_ventas_tmp['fecha'] = pd.to_datetime(df_ventas_tmp['fecha'], errors='coerce')
                    fecha_max = df_ventas_tmp['fecha'].max()
                    mes_actual_inicio = fecha_max.replace(day=1)
                    mes_anterior_inicio = (mes_actual_inicio - pd.Timedelta(days=1)).replace(day=1)
                    
                    ventas_mes_actual = df_ventas_tmp[df_ventas_tmp['fecha'] >= mes_actual_inicio][col_valor].sum()
                    ventas_mes_anterior = df_ventas_tmp[
                        (df_ventas_tmp['fecha'] >= mes_anterior_inicio) & 
                        (df_ventas_tmp['fecha'] < mes_actual_inicio)
                    ][col_valor].sum()
                    
                    if ventas_mes_anterior > 0:
                        crecimiento_pct = ((ventas_mes_actual - ventas_mes_anterior) / ventas_mes_anterior) * 100
                
                metricas_ventas = {
                    'total_ventas': total_ventas,
                    'num_operaciones': num_ops,
                    'ticket_promedio': ticket_prom,
                    'top_linea': top_linea,
                    'monto_top_linea': monto_top_linea,
                    'crecimiento_pct': crecimiento_pct
                }
        except Exception:
            metricas_ventas = {}
    
    # CSS personalizado mejorado
    css = """
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            color: #333;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
            background-color: white;
            border-radius: 16px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
            overflow: hidden;
        }
        header {
            background: linear-gradient(135deg, #1f77b4 0%, #155a8a 100%);
            color: white;
            padding: 30px 40px;
        }
        header h1 {
            font-size: 32px;
            font-weight: 700;
            margin-bottom: 8px;
        }
        .header-info {
            opacity: 0.9;
            font-size: 14px;
        }
        .content {
            padding: 40px;
        }
        .section {
            margin-bottom: 40px;
        }
        .section-title {
            font-size: 20px;
            font-weight: 600;
            color: #1f77b4;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #e0e0e0;
        }
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .metric-card {
            background: white;
            border-left: 4px solid #1f77b4;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            transition: transform 0.2s;
        }
        .metric-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.12);
        }
        .metric-card.ventas {
            border-left-color: #2ecc71;
        }
        .metric-card.cxc {
            border-left-color: #f39c12;
        }
        .metric-card.vigente {
            border-left-color: #27ae60;
        }
        .metric-card.vencida {
            border-left-color: #e67e22;
        }
        .metric-card.critica {
            border-left-color: #e74c3c;
        }
        .metric-label {
            font-size: 13px;
            color: #7f8c8d;
            text-transform: uppercase;
            font-weight: 600;
            letter-spacing: 0.5px;
            margin-bottom: 8px;
        }
        .metric-value {
            font-size: 32px;
            font-weight: 700;
            color: #2c3e50;
            margin-bottom: 4px;
        }
        .metric-subtitle {
            font-size: 13px;
            color: #95a5a6;
        }
        .metric-delta {
            font-size: 14px;
            font-weight: 600;
            margin-top: 8px;
        }
        .metric-delta.positive {
            color: #27ae60;
        }
        .metric-delta.negative {
            color: #e74c3c;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            background: white;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }
        thead {
            background-color: #34495e;
            color: white;
        }
        th {
            padding: 16px;
            text-align: left;
            font-weight: 600;
            font-size: 13px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        td {
            padding: 14px 16px;
            border-bottom: 1px solid #ecf0f1;
        }
        tr:last-child td {
            border-bottom: none;
        }
        tbody tr:hover {
            background-color: #f8f9fa;
        }
        tr.highlight {
            background-color: #fff3cd;
            font-weight: 600;
        }
        .score-container {
            text-align: center;
            padding: 30px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 12px;
            color: white;
        }
        .score-value {
            font-size: 64px;
            font-weight: 700;
            margin: 10px 0;
        }
        .score-label {
            font-size: 18px;
            opacity: 0.9;
        }
        .score-classification {
            font-size: 24px;
            font-weight: 600;
            margin-top: 10px;
            padding: 10px 20px;
            background: rgba(255,255,255,0.2);
            border-radius: 20px;
            display: inline-block;
        }
        footer {
            background-color: #f8f9fa;
            padding: 20px 40px;
            text-align: center;
            color: #7f8c8d;
            font-size: 12px;
            border-top: 1px solid #e0e0e0;
        }
        .badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 600;
        }
        .badge.success {
            background-color: #d4edda;
            color: #155724;
        }
        .badge.warning {
            background-color: #fff3cd;
            color: #856404;
        }
        .badge.danger {
            background-color: #f8d7da;
            color: #721c24;
        }
        @media print {
            body {
                background: white;
                padding: 0;
            }
            .metric-card {
                page-break-inside: avoid;
            }
        }
    </style>
    """
    
    # Construcción del HTML con secciones configurables
    header_html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Reporte Ejecutivo - {nombre_empresa}</title>
    {css}
</head>
<body>
    <div class="container">
        <header>
            <h1>&#128202; Reporte Ejecutivo</h1>
            <div class="header-info">
                <strong>{nombre_empresa}</strong> | Generado: {fecha_actual}
            </div>
        </header>
        
        <div class="content">"""
    
    html_parts = [header_html]
    
    # SECCIÓN: Resumen Ejecutivo (KPIs consolidados)
    if 'resumen_ejecutivo' in secciones:
        html_parts.append("""
                <div class="section">
                    <h2 class="section-title">&#128200; Resumen Ejecutivo</h2>
                    <div class="metrics-grid">
        """)
        
        # Ventas
        if metricas_ventas:
            delta_html = ""
            if metricas_ventas.get('crecimiento_pct') is not None:
                crecimiento = metricas_ventas['crecimiento_pct']
                clase = 'positive' if crecimiento >= 0 else 'negative'
                simbolo = '▲' if crecimiento >= 0 else '▼'
                delta_html = f'<div class="metric-delta {clase}">{simbolo} {abs(crecimiento):.1f}% vs mes anterior</div>'
            
            html_parts.append(f"""
                        <div class="metric-card ventas">
                            <div class="metric-label">&#128176; Total Ventas</div>
                            <div class="metric-value">{formato_moneda(metricas_ventas['total_ventas'])}</div>
                            <div class="metric-subtitle">{metricas_ventas['num_operaciones']:,} operaciones</div>
                            {delta_html}
                        </div>
            """)
        
        # CxC Total
        html_parts.append(f"""
                        <div class="metric-card cxc">
                            <div class="metric-label">&#127974; Cuentas por Cobrar</div>
                            <div class="metric-value">{formato_moneda(metricas.get('total_adeudado', 0))}</div>
                            <div class="metric-subtitle">Cartera total</div>
                        </div>
        """)
        
        # Morosidad
        pct_vencida = metricas.get('pct_vencida', 0)
        badge_class = 'success' if pct_vencida < 10 else ('warning' if pct_vencida < 25 else 'danger')
        html_parts.append(f"""
                        <div class="metric-card vencida">
                            <div class="metric-label">&#9888; Morosidad</div>
                            <div class="metric-value">{formato_porcentaje(pct_vencida)}</div>
                            <div class="metric-subtitle">
                                <span class="badge {badge_class}">
                                    {'Excelente' if pct_vencida < 10 else ('Aceptable' if pct_vencida < 25 else 'Crítico')}
                                </span>
                            </div>
                        </div>
        """)
        
        # Cartera Crítica
        html_parts.append(f"""
                        <div class="metric-card critica">
                            <div class="metric-label">&#128680; Cartera Crítica</div>
                            <div class="metric-value">{formato_moneda(metricas.get('critica', 0))}</div>
                            <div class="metric-subtitle">{formato_porcentaje(metricas.get('pct_critica', 0))} del total</div>
                        </div>
        """)
        
        html_parts.append("""
                    </div>
                </div>
        """)
    
    # SECCIÓN: Ventas Detalladas
    if 'ventas' in secciones and metricas_ventas:
        html_parts.append(f"""
                <div class="section">
                    <h2 class="section-title">&#128188; Desempe&ntilde;o de Ventas</h2>
                    <div class="metrics-grid">
                        <div class="metric-card">
                            <div class="metric-label">&#127919; Ticket Promedio</div>
                            <div class="metric-value">{formato_moneda(metricas_ventas['ticket_promedio'])}</div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-label">&#11088; L&iacute;nea Top</div>
                            <div class="metric-value" style="font-size: 20px;">{metricas_ventas['top_linea']}</div>
                            <div class="metric-subtitle">{formato_moneda(metricas_ventas['monto_top_linea'])}</div>
                        </div>
                    </div>
                </div>
        """)
    
    # SECCIÓN: CxC Detallada
    if 'cxc' in secciones:
        html_parts.append(f"""
                <div class="section">
                    <h2 class="section-title">&#127974; Cuentas por Cobrar</h2>
                    <div class="metrics-grid">
                        <div class="metric-card vigente">
                            <div class="metric-label">&#9989; Saldo Vigente</div>
                            <div class="metric-value">{formato_moneda(metricas.get('vigente', 0))}</div>
                            <div class="metric-subtitle">{formato_porcentaje(metricas.get('pct_vigente', 0))}</div>
                        </div>
                        <div class="metric-card vencida">
                            <div class="metric-label">&#9200; Saldo Vencido</div>
                            <div class="metric-value">{formato_moneda(metricas.get('vencida', 0))}</div>
                            <div class="metric-subtitle">{formato_porcentaje(metricas.get('pct_vencida', 0))}</div>
                        </div>
                        <div class="metric-card critica">
                            <div class="metric-label">&#128308; Alto Riesgo (&gt;90 d&iacute;as)</div>
                            <div class="metric-value">{formato_moneda(metricas.get('alto_riesgo', 0))}</div>
                            <div class="metric-subtitle">{formato_porcentaje(metricas.get('pct_alto_riesgo', 0))}</div>
                        </div>
                    </div>
                </div>
        """)
    
    # SECCIÓN: Tabla de Antigüedad
    if 'antiguedad' in secciones:
        html_parts.append("""
                <div class="section">
                    <h2 class="section-title">&#128197; Distribuci&oacute;n por Antig&uuml;edad</h2>
                    <table>
                        <thead>
                            <tr>
                                <th>Categoría</th>
                                <th>Monto</th>
                                <th>Porcentaje</th>
                                <th>Estado</th>
                            </tr>
                        </thead>
                        <tbody>
        """)
        
        categorias = [
            ('Vigente (0 días)', 'vigente', 'pct_vigente', 'success'),
            ('Vencida 0-30 días', 'vencida_0_30', 'pct_vencida_0_30', 'success'),
            ('Vencida 31-60 días', 'vencida_31_60', 'pct_vencida_31_60', 'warning'),
            ('Vencida 61-90 días', 'vencida_61_90', 'pct_vencida_61_90', 'warning'),
            ('Alto Riesgo (>90 días)', 'alto_riesgo', 'pct_alto_riesgo', 'danger')
        ]
        
        for label, key_monto, key_pct, badge in categorias:
            monto = metricas.get(key_monto, 0)
            pct = metricas.get(key_pct, 0)
            tr_class = ' class="highlight"' if badge == 'danger' else ''
            html_parts.append(f"""
                            <tr{tr_class}>
                                <td>{label}</td>
                                <td>{formato_moneda(monto)}</td>
                                <td>{formato_porcentaje(pct)}</td>
                                <td><span class="badge {badge}">{'OK' if badge == 'success' else ('Precaución' if badge == 'warning' else 'Urgente')}</span></td>
                            </tr>
            """)
        
        html_parts.append("""
                        </tbody>
                    </table>
                </div>
        """)
    
    # SECCIÓN: Score de Salud
    if 'score' in secciones:
        score = metricas.get('score_salud', 0)
        clasificacion = metricas.get('clasificacion_salud', 'N/A')
        
        # Calcular desglose del score para explicación
        pct_vig = metricas.get('pct_vigente', 0)
        pct_0_30 = metricas.get('pct_vencida_0_30', 0)
        pct_31_60 = metricas.get('pct_vencida_31_60', 0)
        pct_61_90 = metricas.get('pct_vencida_61_90', 0)
        pct_90plus = metricas.get('pct_alto_riesgo', 0)
        
        html_parts.append(f"""
                <div class="section">
                    <h2 class="section-title">&#127919; Score de Salud de Cartera</h2>
                    <div class="score-container">
                        <div class="score-label">Puntuaci&oacute;n General</div>
                        <div class="score-value">{score:.1f}<span style="font-size: 32px; opacity: 0.7;">/100</span></div>
                        <div class="score-classification">{clasificacion}</div>
                    </div>
                    <div style="margin-top: 20px; padding: 20px; background: white; border-radius: 8px;">
                        <h3 style="font-size: 16px; margin-bottom: 10px; color: #2c3e50;">&#128200; C&oacute;mo se calcula el Score</h3>
                        <p style="font-size: 14px; color: #7f8c8d; margin-bottom: 15px;">
                            El score pondera cada rango de antig&uuml;edad seg&uacute;n su nivel de riesgo:
                        </p>
                        <table style="width: 100%; font-size: 13px; margin-top: 10px;">
                            <tr>
                                <td style="padding: 8px; border-bottom: 1px solid #ecf0f1;">Vigente (&le;0 d&iacute;as)</td>
                                <td style="padding: 8px; border-bottom: 1px solid #ecf0f1; text-align: right;">{pct_vig:.1f}% &times; 100 pts</td>
                                <td style="padding: 8px; border-bottom: 1px solid #ecf0f1; text-align: right; font-weight: 600;">= {pct_vig * 100 / 100:.1f}</td>
                            </tr>
                            <tr>
                                <td style="padding: 8px; border-bottom: 1px solid #ecf0f1;">Vencida 0-30 d&iacute;as</td>
                                <td style="padding: 8px; border-bottom: 1px solid #ecf0f1; text-align: right;">{pct_0_30:.1f}% &times; 70 pts</td>
                                <td style="padding: 8px; border-bottom: 1px solid #ecf0f1; text-align: right; font-weight: 600;">= {pct_0_30 * 70 / 100:.1f}</td>
                            </tr>
                            <tr>
                                <td style="padding: 8px; border-bottom: 1px solid #ecf0f1;">Vencida 31-60 d&iacute;as</td>
                                <td style="padding: 8px; border-bottom: 1px solid #ecf0f1; text-align: right;">{pct_31_60:.1f}% &times; 40 pts</td>
                                <td style="padding: 8px; border-bottom: 1px solid #ecf0f1; text-align: right; font-weight: 600;">= {pct_31_60 * 40 / 100:.1f}</td>
                            </tr>
                            <tr>
                                <td style="padding: 8px; border-bottom: 1px solid #ecf0f1;">Vencida 61-90 d&iacute;as</td>
                                <td style="padding: 8px; border-bottom: 1px solid #ecf0f1; text-align: right;">{pct_61_90:.1f}% &times; 20 pts</td>
                                <td style="padding: 8px; border-bottom: 1px solid #ecf0f1; text-align: right; font-weight: 600;">= {pct_61_90 * 20 / 100:.1f}</td>
                            </tr>
                            <tr>
                                <td style="padding: 8px; border-bottom: 2px solid #34495e;">Alto Riesgo (&gt;90 d&iacute;as)</td>
                                <td style="padding: 8px; border-bottom: 2px solid #34495e; text-align: right;">{pct_90plus:.1f}% &times; 0 pts</td>
                                <td style="padding: 8px; border-bottom: 2px solid #34495e; text-align: right; font-weight: 600;">= {pct_90plus * 0 / 100:.1f}</td>
                            </tr>
                            <tr style="background: #f8f9fa;">
                                <td style="padding: 12px; font-weight: 700;">SCORE TOTAL</td>
                                <td></td>
                                <td style="padding: 12px; text-align: right; font-size: 18px; font-weight: 700; color: #2c3e50;">{score:.1f}/100</td>
                            </tr>
                        </table>
                        <p style="font-size: 12px; color: #95a5a6; margin-top: 15px; font-style: italic;">
                            * Un score de 100 = 100% vigente. Un score de 0 = 100% en alto riesgo (&gt;90 d&iacute;as).
                        </p>
                    </div>
                </div>
        """)
    
    # SECCIÓN: Top Deudores
    if 'top_clientes' in secciones and not df_detalle.empty:
        try:
            # Detectar columnas
            col_cliente = None
            for col in ['cliente', 'nombre_cliente', 'razon_social', 'nombre']:
                if col in df_detalle.columns:
                    col_cliente = col
                    break
            
            col_saldo = None
            for col in ['saldo_adeudado', 'saldo', 'adeudo', 'importe']:
                if col in df_detalle.columns:
                    col_saldo = col
                    break
            
            if col_cliente and col_saldo:
                top_deudores = df_detalle.groupby(col_cliente)[col_saldo].sum().nlargest(5)
                
                html_parts.append("""
                <div class="section">
                    <h2 class="section-title">&#128101; Top 5 Deudores</h2>
                    <table>
                        <thead>
                            <tr>
                                <th>#</th>
                                <th>Cliente</th>
                                <th>Saldo</th>
                                <th>% del Total</th>
                            </tr>
                        </thead>
                        <tbody>
                """)
                
                total_adeudado = metricas.get('total_adeudado', 1)
                for idx, (cliente, saldo) in enumerate(top_deudores.items(), 1):
                    pct_del_total = (saldo / total_adeudado * 100) if total_adeudado > 0 else 0
                    html_parts.append(f"""
                            <tr>
                                <td><strong>{idx}</strong></td>
                                <td>{cliente}</td>
                                <td>{formato_moneda(saldo)}</td>
                                <td>{pct_del_total:.1f}%</td>
                            </tr>
                    """)
                
                html_parts.append("""
                        </tbody>
                    </table>
                </div>
                """)
        except Exception:
            pass  # Skip si hay error en top clientes
    
    # Footer
    html_parts.append(f"""
            </div>
            
            <footer>
                <p>Reporte generado automáticamente por FRADMA Dashboard</p>
                <p>© {datetime.now().year} - Todos los derechos reservados</p>
            </footer>
        </div>
    </body>
    </html>
    """)
    
    return ''.join(html_parts)


def preparar_datos_para_export(df: pd.DataFrame) -> pd.DataFrame:
    """
    Prepara DataFrame para exportación limpiando y formateando datos.
    
    Args:
        df: DataFrame a preparar
        
    Returns:
        DataFrame limpio y formateado
        
    Examples:
        >>> df_limpio = preparar_datos_para_export(df_raw)
    """
    df_export = df.copy()
    
    # Eliminar columnas internas si existen
    columnas_internas = ['index', 'Unnamed: 0', 'level_0']
    df_export = df_export.drop(columns=[c for c in columnas_internas if c in df_export.columns], errors='ignore')
    
    # Renombrar columnas a español si están en inglés
    renombrar = {
        'customer': 'Cliente',
        'balance': 'Saldo',
        'days_overdue': 'Días Vencido',
        'status': 'Estatus',
        'due_date': 'Fecha Vencimiento',
        'amount': 'Monto',
        'dias_overdue': 'Días Vencido',
        'saldo_adeudado': 'Saldo Adeudado',
        'antiguedad': 'Antigüedad'
    }
    
    df_export = df_export.rename(columns={k: v for k, v in renombrar.items() if k in df_export.columns})
    
    # Redondear columnas numéricas
    for col in df_export.select_dtypes(include=['float64']).columns:
        df_export[col] = df_export[col].round(2)
    
    return df_export


def crear_excel_cobranza_semanal(
    df_prioridades: pd.DataFrame,
    nombre_empresa: str = "FRADMA"
) -> bytes:
    """
    Crea un Excel de lista semanal de cobranza listo para compartir con el equipo.

    Genera un archivo con dos hojas:
    - "Lista Cobranza": tabla completa con colores por nivel de prioridad,
      columna de "Acción Recomendada" y campo vacío "Gestión / Notas"
    - "Resumen": métricas agregadas por nivel

    Args:
        df_prioridades: DataFrame con columnas:
            - deudor (str)
            - monto (float)
            - dias_max (float)
            - documentos (int)
            - score (float)
            - nivel (str): "🔴 URGENTE" | "🟠 ALTA" | "🟡 MEDIA" | "🟢 BAJA"
            - nivel_num (int): 1-4 para ordenación
        nombre_empresa: Nombre de la empresa para el encabezado

    Returns:
        bytes: Contenido del archivo Excel (.xlsx)
    """
    output = io.BytesIO()

    # Colores de fondo por nivel (RGB hex para xlsxwriter: sin #)
    COLOR_BG = {
        "🔴 URGENTE": "FFCCCC",   # rojo claro
        "🟠 ALTA":    "FFE0CC",   # naranja claro
        "🟡 MEDIA":   "FFFACC",   # amarillo claro
        "🟢 BAJA":    "CCFFCC",   # verde claro
    }
    COLOR_FONT = {
        "🔴 URGENTE": "990000",
        "🟠 ALTA":    "7D3C00",
        "🟡 MEDIA":   "7D6608",
        "🟢 BAJA":    "1A5C1A",
    }
    ACCION = {
        "🔴 URGENTE": "⚡ Contacto INMEDIATO - Evaluar plan de pagos / suspender crédito",
        "🟠 ALTA":    "📞 Llamar en las próximas 48 h - Comprometer fecha de pago",
        "🟡 MEDIA":   "📧 Enviar estado de cuenta + recordatorio por correo",
        "🟢 BAJA":    "🔔 Seguimiento de rutina - monitoreo semanal",
    }

    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        wb = writer.book

        # ── Formatos base ──────────────────────────────────────────────────
        fmt_titulo = wb.add_format({
            "bold": True, "font_size": 15,
            "font_color": "#1f77b4", "align": "center", "valign": "vcenter",
        })
        fmt_fecha = wb.add_format({"italic": True, "font_color": "#666666", "font_size": 10})
        fmt_header = wb.add_format({
            "bold": True, "bg_color": "2C3E50", "font_color": "FFFFFF",
            "align": "center", "valign": "vcenter", "border": 1,
            "text_wrap": True,
        })
        fmt_moneda = wb.add_format({"num_format": '$#,##0.00', "align": "right"})
        fmt_numero = wb.add_format({"num_format": '#,##0', "align": "center"})
        fmt_decimal = wb.add_format({"num_format": '0.0', "align": "center"})
        fmt_center  = wb.add_format({"align": "center", "valign": "vcenter"})

        # Fábrica de formatos por nivel (bg + font)
        def _fmt_nivel(nivel, extra=None):
            cfg = {
                "bg_color": COLOR_BG.get(nivel, "FFFFFF"),
                "font_color": COLOR_FONT.get(nivel, "000000"),
                "valign": "vcenter", "border": 1,
            }
            if extra:
                cfg.update(extra)
            return wb.add_format(cfg)

        # ── Hoja 1: Lista de Cobranza ──────────────────────────────────────
        ws = wb.add_worksheet("Lista Cobranza")
        writer.sheets["Lista Cobranza"] = ws

        fecha_str = datetime.now().strftime("%d/%m/%Y %H:%M")
        semana_str = datetime.now().strftime("Semana %W · %Y")

        ws.set_row(0, 28)
        ws.merge_range("A1:J1", f"Lista de Cobranza — {nombre_empresa}  |  {semana_str}", fmt_titulo)
        ws.write("A2", f"Generado: {fecha_str}", fmt_fecha)

        # Encabezados (fila 3, índice 2)
        headers = [
            "Prioridad", "Cliente", "Saldo Adeudado ($)",
            "Días Máx Vencido", "# Documentos", "Score",
            "Acción Recomendada", "Gestor Asignado", "Gestión / Notas", "Fecha Compromiso",
        ]
        ws.set_row(2, 36)
        for col_n, h in enumerate(headers):
            ws.write(2, col_n, h, fmt_header)

        # Anchos de columna
        anchos = [14, 34, 20, 16, 12, 8, 52, 20, 32, 16]
        for col_n, w in enumerate(anchos):
            ws.set_column(col_n, col_n, w)

        # Filas de datos
        df_sorted = df_prioridades.sort_values(
            ["nivel_num", "score"], ascending=[True, False]
        ).reset_index(drop=True)

        for row_n, row in df_sorted.iterrows():
            nivel = row.get("nivel", "🟢 BAJA")
            excel_row = row_n + 3   # offset: título + fecha + header
            ws.set_row(excel_row, 20)

            fmt_txt  = _fmt_nivel(nivel)
            fmt_mon  = _fmt_nivel(nivel, {"num_format": '$#,##0.00', "align": "right"})
            fmt_num  = _fmt_nivel(nivel, {"num_format": '#,##0',     "align": "center"})
            fmt_dec  = _fmt_nivel(nivel, {"num_format": '0.0',       "align": "center"})
            fmt_acc  = _fmt_nivel(nivel, {"text_wrap": True, "italic": True})
            fmt_vac  = _fmt_nivel(nivel, {"font_color": "AAAAAA", "italic": True})

            ws.write(excel_row, 0, nivel,                                  fmt_txt)
            ws.write(excel_row, 1, str(row.get("deudor", "")),             fmt_txt)
            ws.write(excel_row, 2, float(row.get("monto", 0)),             fmt_mon)
            ws.write(excel_row, 3, int(row.get("dias_max", 0)),            fmt_num)
            ws.write(excel_row, 4, int(row.get("documentos", 0)),          fmt_num)
            ws.write(excel_row, 5, round(float(row.get("score", 0)), 1),   fmt_dec)
            ws.write(excel_row, 6, ACCION.get(nivel, ""),                  fmt_acc)
            ws.write(excel_row, 7, "",                                      fmt_vac)  # Gestor
            ws.write(excel_row, 8, "",                                      fmt_vac)  # Notas
            ws.write(excel_row, 9, "",                                      fmt_vac)  # Fecha compromiso

        # Inmovilizar fila de encabezado
        ws.freeze_panes(3, 0)

        # ── Hoja 2: Resumen ────────────────────────────────────────────────
        ws_res = wb.add_worksheet("Resumen")
        writer.sheets["Resumen"] = ws_res

        ws_res.merge_range("A1:E1", f"Resumen Ejecutivo — {semana_str}", fmt_titulo)
        ws_res.write("A2", f"Generado: {fecha_str}", fmt_fecha)

        res_headers = ["Nivel", "# Clientes", "Saldo Total ($)", "Score Promedio", "% del Total Saldo"]
        ws_res.set_row(2, 30)
        for col_n, h in enumerate(res_headers):
            ws_res.write(2, col_n, h, fmt_header)

        ws_res.set_column(0, 0, 16)
        ws_res.set_column(1, 1, 12)
        ws_res.set_column(2, 2, 20)
        ws_res.set_column(3, 3, 16)
        ws_res.set_column(4, 4, 18)

        total_monto = df_prioridades["monto"].sum() if "monto" in df_prioridades.columns else 0

        for row_n, nivel in enumerate(["🔴 URGENTE", "🟠 ALTA", "🟡 MEDIA", "🟢 BAJA"]):
            sub = df_prioridades[df_prioridades["nivel"] == nivel]
            excel_row = row_n + 3

            fmt_txt  = _fmt_nivel(nivel)
            fmt_mon  = _fmt_nivel(nivel, {"num_format": '$#,##0.00', "align": "right"})
            fmt_num  = _fmt_nivel(nivel, {"num_format": '#,##0',     "align": "center"})
            fmt_pct  = _fmt_nivel(nivel, {"num_format": '0.00%',     "align": "center"})
            fmt_dec  = _fmt_nivel(nivel, {"num_format": '0.0',       "align": "center"})

            saldo_nivel = sub["monto"].sum() if len(sub) else 0
            score_prom  = sub["score"].mean() if len(sub) else 0
            pct_saldo   = (saldo_nivel / total_monto) if total_monto > 0 else 0

            ws_res.write(excel_row, 0, nivel,           fmt_txt)
            ws_res.write(excel_row, 1, len(sub),        fmt_num)
            ws_res.write(excel_row, 2, saldo_nivel,     fmt_mon)
            ws_res.write(excel_row, 3, score_prom,      fmt_dec)
            ws_res.write(excel_row, 4, pct_saldo,       fmt_pct)

        # Fila de TOTAL
        total_row = 3 + 4
        fmt_bold = wb.add_format({"bold": True, "border": 1, "align": "center"})
        fmt_bold_mon = wb.add_format({"bold": True, "border": 1, "num_format": '$#,##0.00', "align": "right"})
        ws_res.write(total_row, 0, "TOTAL",                     fmt_bold)
        ws_res.write(total_row, 1, len(df_prioridades),         fmt_bold)
        ws_res.write(total_row, 2, total_monto,                 fmt_bold_mon)
        ws_res.write(total_row, 3, "",                          fmt_bold)
        ws_res.write(total_row, 4, 1.0,
                     wb.add_format({"bold": True, "border": 1, "num_format": '0.00%', "align": "center"}))

    output.seek(0)
    return output.getvalue()


if __name__ == "__main__":
    # Demo de export
    print("🧪 Demo de export_helper.py\n")
    
    # Datos de prueba
    metricas = {
        'total_adeudado': 1500000,
        'vigente': 900000,
        'vencida': 600000,
        'pct_vigente': 60.0,
        'pct_vencida': 40.0,
        'vencida_0_30': 200000,
        'vencida_31_60': 150000,
        'vencida_61_90': 100000,
        'critica': 150000,
        'alto_riesgo': 80000,
        'pct_critica': 10.0,
        'score_salud': 72.5,
        'clasificacion_salud': 'Bueno'
    }
    
    df_detalle = pd.DataFrame({
        'cliente': ['Cliente A', 'Cliente B', 'Cliente C'],
        'saldo_adeudado': [100000, 50000, 75000],
        'dias_overdue': [15, 45, 95]
    })
    
    # Crear Excel
    print("📊 Creando Excel...")
    excel_bytes = crear_excel_metricas_cxc(metricas, df_detalle)
    print(f"✅ Excel creado: {len(excel_bytes)} bytes\n")
    
    # Crear HTML
    print("📄 Creando HTML...")
    html = crear_reporte_html(metricas, df_detalle)
    print(f"✅ HTML creado: {len(html)} caracteres\n")
    
    print("✅ Demo completado!")
