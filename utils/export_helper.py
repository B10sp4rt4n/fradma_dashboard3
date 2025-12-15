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
            ('Crítica (>90 días)', metricas.get('critica', 0), formato_moneda),
            ('Alto Riesgo (>120 días)', metricas.get('alto_riesgo', 0), formato_moneda),
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
    incluir_graficos: bool = False
) -> str:
    """
    Crea un reporte HTML profesional con métricas CxC.
    
    Args:
        metricas: Diccionario con métricas calculadas
        df_detalle: DataFrame con detalle de cuentas
        nombre_empresa: Nombre de la empresa
        incluir_graficos: Si incluir gráficos (requiere matplotlib/plotly)
        
    Returns:
        str: HTML del reporte
        
    Examples:
        >>> html = crear_reporte_html(metricas, df_detalle)
        >>> with open('reporte.html', 'w') as f:
        ...     f.write(html)
    """
    fecha_actual = datetime.now().strftime("%d de %B de %Y, %H:%M")
    
    # CSS personalizado
    css = """
    <style>
        body {
            font-family: 'Segoe UI', Arial, sans-serif;
            margin: 40px;
            background-color: #f5f5f5;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background-color: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h1 {
            color: #1f77b4;
            border-bottom: 3px solid #1f77b4;
            padding-bottom: 10px;
        }
        .header-info {
            color: #666;
            margin-bottom: 30px;
        }
        .metricas-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin: 30px 0;
        }
        .metrica-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        .metrica-card.vigente {
            background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%);
        }
        .metrica-card.vencida {
            background: linear-gradient(135deg, #fa709a 0%, #fee140 100%);
        }
        .metrica-card.critica {
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        }
        .metrica-label {
            font-size: 14px;
            opacity: 0.9;
            margin-bottom: 5px;
        }
        .metrica-valor {
            font-size: 28px;
            font-weight: bold;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }
        th {
            background-color: #1f77b4;
            color: white;
            padding: 12px;
            text-align: left;
        }
        td {
            padding: 10px;
            border-bottom: 1px solid #ddd;
        }
        tr:hover {
            background-color: #f5f5f5;
        }
        .footer {
            margin-top: 40px;
            text-align: center;
            color: #999;
            font-size: 12px;
        }
    </style>
    """
    
    # Construcción del HTML
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Reporte CxC - {nombre_empresa}</title>
        {css}
    </head>
    <body>
        <div class="container">
            <h1>📊 Reporte de Cuentas por Cobrar</h1>
            <div class="header-info">
                <strong>{nombre_empresa}</strong><br>
                Generado: {fecha_actual}
            </div>
            
            <div class="metricas-grid">
                <div class="metrica-card">
                    <div class="metrica-label">Total Adeudado</div>
                    <div class="metrica-valor">{formato_moneda(metricas.get('total_adeudado', 0))}</div>
                </div>
                
                <div class="metrica-card vigente">
                    <div class="metrica-label">Saldo Vigente</div>
                    <div class="metrica-valor">{formato_moneda(metricas.get('vigente', 0))}</div>
                    <div class="metrica-label">{formato_porcentaje(metricas.get('pct_vigente', 0))}</div>
                </div>
                
                <div class="metrica-card vencida">
                    <div class="metrica-label">Saldo Vencido</div>
                    <div class="metrica-valor">{formato_moneda(metricas.get('vencida', 0))}</div>
                    <div class="metrica-label">{formato_porcentaje(metricas.get('pct_vencida', 0))}</div>
                </div>
                
                <div class="metrica-card critica">
                    <div class="metrica-label">Deuda Crítica (>90 días)</div>
                    <div class="metrica-valor">{formato_moneda(metricas.get('critica', 0))}</div>
                    <div class="metrica-label">{formato_porcentaje(metricas.get('pct_critica', 0))}</div>
                </div>
            </div>
            
            <h2>Distribución por Antigüedad</h2>
            <table>
                <thead>
                    <tr>
                        <th>Categoría</th>
                        <th>Monto</th>
                        <th>Porcentaje</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>Vigente (0 días)</td>
                        <td>{formato_moneda(metricas.get('vigente', 0))}</td>
                        <td>{formato_porcentaje(metricas.get('pct_vigente', 0))}</td>
                    </tr>
                    <tr>
                        <td>Vencida 0-30 días</td>
                        <td>{formato_moneda(metricas.get('vencida_0_30', 0))}</td>
                        <td>{formato_porcentaje(metricas.get('pct_vencida_0_30', 0))}</td>
                    </tr>
                    <tr>
                        <td>Vencida 31-60 días</td>
                        <td>{formato_moneda(metricas.get('vencida_31_60', 0))}</td>
                        <td>{formato_porcentaje(metricas.get('pct_vencida_31_60', 0))}</td>
                    </tr>
                    <tr>
                        <td>Vencida 61-90 días</td>
                        <td>{formato_moneda(metricas.get('vencida_61_90', 0))}</td>
                        <td>{formato_porcentaje(metricas.get('pct_vencida_61_90', 0))}</td>
                    </tr>
                    <tr style="background-color: #ffe6e6;">
                        <td><strong>Crítica (>90 días)</strong></td>
                        <td><strong>{formato_moneda(metricas.get('critica', 0))}</strong></td>
                        <td><strong>{formato_porcentaje(metricas.get('pct_critica', 0))}</strong></td>
                    </tr>
                </tbody>
            </table>
            
            <h2>Score de Salud Financiera</h2>
            <div class="metrica-card">
                <div class="metrica-label">Puntuación</div>
                <div class="metrica-valor">{metricas.get('score_salud', 0):.1f} / 100</div>
                <div class="metrica-label">Clasificación: {metricas.get('clasificacion_salud', 'N/A')}</div>
            </div>
            
            <div class="footer">
                Reporte generado automáticamente por FRADMA Dashboard<br>
                © {datetime.now().year} - Todos los derechos reservados
            </div>
        </div>
    </body>
    </html>
    """
    
    return html


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
