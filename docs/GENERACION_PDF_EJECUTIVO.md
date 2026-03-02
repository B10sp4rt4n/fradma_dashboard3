# 📄 Generación de Reportes PDF Ejecutivos

## Descripción

La plataforma ahora puede generar reportes ejecutivos en PDF de forma automática a partir de cualquier consulta realizada en el **Data Assistant**.

## Características

### 🎨 Diseño Profesional
- **Encabezado corporativo** con nombre de empresa y fecha
- **Sección de pregunta** destacada con estilo itálico
- **Análisis e interpretación** con formato limpio y legible
- **Tabla de datos** con formato profesional (máximo 20 filas)
- **Información de ROI** (si está disponible)
- **SQL ejecutado** en segunda página (opcional)
- **Pie de página** con branding de Fradma FIP

### 📊 Elementos Incluidos

1. **Consulta Original**: La pregunta que hizo el usuario
2. **Análisis**: Interpretación generada por IA con formato
3. **Datos**: Tabla con los resultados (primeras 20 filas)
4. **ROI Tracker**: Tiempo ahorrado y valor generado
5. **SQL**: Query ejecutado para transparencia
6. **Metadatos**: Tipo de gráfica sugerida, fecha, empresa

## Cómo Usar

### Desde el Data Assistant

1. **Haz cualquier pregunta** en el Data Assistant
   - Ejemplo: "¿Cuánto facturé este mes?"
   - Ejemplo: "Muestra los top 10 clientes"
   - Ejemplo: "Análisis de ventas por producto"

2. **Ve a la pestaña "Tabla"** en los resultados

3. **Haz clic en "📄 Descargar PDF Ejecutivo"**
   - Se generará automáticamente un PDF profesional
   - El archivo se descarga como `reporte_ejecutivo.pdf`

### Desde Código

```python
from utils.export_helper import crear_reporte_pdf_ejecutivo
import pandas as pd

# Preparar datos
pregunta = "¿Cuánto facturé en enero?"
interpretacion = "La facturación de enero fue **$150,000 MXN**"
df = pd.DataFrame({
    'mes': ['Enero'],
    'total': [150000]
})
sql = "SELECT DATE_TRUNC('month', fecha_emision) AS mes, SUM(total) AS total FROM cfdi_ventas WHERE mes = '2026-01';"

# Generar PDF
pdf_bytes = crear_reporte_pdf_ejecutivo(
    pregunta=pregunta,
    interpretacion=interpretacion,
    df=df,
    sql=sql,
    chart_type="bar",
    empresa="Mi Empresa S.A.",
    roi_info={
        'tiempo_ahorrado_hrs': 2.5,
        'valor_generado': 7500,
        'costo_consultor': 7500
    }
)

# Guardar archivo
with open('mi_reporte.pdf', 'wb') as f:
    f.write(pdf_bytes)
```

## Ventajas vs Otros Sistemas

| Característica | Fradma FIP | Power BI | Tableau | Excel |
|---------------|-----------|----------|---------|-------|
| **Generación automática desde NL** | ✅ | ❌ | ❌ | ❌ |
| **Template ejecutivo integrado** | ✅ | Plugin | Plugin | Manual |
| **ROI incluido en reporte** | ✅ | ❌ | ❌ | ❌ |
| **Un clic desde consulta** | ✅ | ❌ | ❌ | ❌ |
| **Formato profesional auto** | ✅ | Configurable | Configurable | Manual |
| **SQL incluido** | ✅ | ❌ | ❌ | N/A |

## Casos de Uso

### 1. **CFO - Reportes Mensuales**
```
Pregunta: "Dame un reporte tipo CFO de las ventas con todo y graficos que consideres importantes para CEO"
→ PDF con KPIs, tendencias, análisis completo
```

### 2. **Auditoría - Documentación**
```
Pregunta: "Facturas mayores a $100,000 en enero"
→ PDF con detalle + SQL para auditoría
```

### 3. **Reuniones Ejecutivas**
```
Pregunta: "Top 10 clientes por facturación"
→ PDF listo para compartir en reunión
```

### 4. **Análisis Ad-hoc**
```
Pregunta: "Crecimiento mensual de ventas últimos 6 meses"
→ PDF con análisis + valor del tiempo ahorrado
```

## Personalización

### Cambiar Colores Corporativos

Edita en `/workspaces/fradma_dashboard3/utils/export_helper.py`:

```python
# Línea ~1090
titulo_style = ParagraphStyle(
    'CustomTitle',
    textColor=colors.HexColor('#TU_COLOR_AQUÍ'),  # ← Cambiar
    ...
)
```

### Agregar Logo

```python
# Después de la línea ~1127
from reportlab.platypus import Image

if os.path.exists('path/to/logo.png'):
    logo = Image('path/to/logo.png', width=2*inch, height=1*inch)
    story.insert(0, logo)
    story.insert(1, Spacer(1, 0.2*inch))
```

### Cambiar Tamaño de Página

```python
# Línea ~1066
doc = SimpleDocTemplate(
    output,
    pagesize=A4,  # ← Cambiar de letter a A4
    ...
)
```

## Limitaciones Actuales

1. **Máximo 20 filas** en la tabla del PDF (para mantener legibilidad)
   - Si hay más datos, se muestra nota al pie
   - Descarga CSV para datos completos

2. **Sin gráficas embebidas** (solo tabla de datos)
   - Próxima versión incluirá gráficas Plotly → PNG → PDF

3. **Formato fijo** (no personalizable por usuario)
   - Template profesional único
   - Personalización requiere editar código

## Roadmap

### Versión 1.1 (Próxima)
- [ ] Gráficas Plotly embebidas en PDF
- [ ] Selector de template (Ejecutivo / Técnico / Auditoría)
- [ ] Logo personalizado por empresa
- [ ] Múltiples consultas en un solo PDF

### Versión 1.2
- [ ] Generación automática al decir "generame un reporte"
- [ ] Reportes programados (diario/semanal/mensual)
- [ ] Envío automático por email
- [ ] Comparativas periodo anterior en PDF

### Versión 2.0
- [ ] Editor visual de templates
- [ ] PDF multiidioma
- [ ] Firma digital
- [ ] Watermark personalizado

## Tecnología

- **ReportLab 4.2.5**: Generación de PDFs
- **Pillow**: Manejo de imágenes (futuro)
- **Pandas**: Procesamiento de datos
- **Python 3.12+**: Compatible

## Soporte

Para problemas o sugerencias sobre la generación de PDFs:
- Revisa logs en `/tmp/streamlit.log`
- Verifica que reportlab esté instalado: `pip list | grep reportlab`
- Contacta al equipo de desarrollo

---

**Generado para**: Fradma Fiscal Intelligence Platform  
**Fecha**: Marzo 2026  
**Versión**: 1.0
