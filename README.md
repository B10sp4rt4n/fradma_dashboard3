# Fradma Dashboard

[![Tests](https://github.com/B10sp4rt4n/fradma_dashboard3/actions/workflows/ci.yml/badge.svg)](https://github.com/B10sp4rt4n/fradma_dashboard3/actions/workflows/ci.yml)
[![Coverage](https://img.shields.io/badge/coverage-91%25-brightgreen)](./htmlcov/index.html)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue)](https://www.python.org/)
[![Code Quality](https://img.shields.io/badge/score-94%2F100-brightgreen)](./.github-analysis.md)

Plataforma de análisis comercial para FRADMA. Esta aplicación construida en Streamlit permite visualizar KPIs de ventas, comparar años históricos y evaluar el desempeño por línea de producto de manera interactiva.

## 🎯 Características

- 📊 **Dashboard CxC (Cuentas por Cobrar)**: Score de salud, semáforos de riesgo, antigüedad de saldos
- 📈 **KPIs Generales**: Métricas consolidadas de ventas y cobranza
- 📊 **Comparativo Año vs Año**: Análisis histórico de desempeño
- 🔥 **Heatmap de Ventas**: Visualización de tendencias por período

## 🚀 Inicio Rápido

### Instalación

```bash
git clone https://github.com/B10sp4rt4n/fradma_dashboard3.git
cd fradma_dashboard3
pip install -r requirements.txt
streamlit run app.py
```

### Desarrollo

```bash
# Instalar dependencias de desarrollo
pip install -r requirements-dev.txt

# Ejecutar tests
pytest

# Ver coverage
pytest --cov-report=html
open htmlcov/index.html
```

## 📁 Estructura del Proyecto

```
fradma_dashboard3/
├── app.py                      # Entry point de la aplicación
├── requirements.txt            # Dependencias de producción
├── requirements-dev.txt        # Dependencias de desarrollo
├── pytest.ini                  # Configuración de tests
├── .gitignore
├── README.md
├── main/                       # Módulos principales
│   ├── kpi_cpc.py             # Dashboard CxC (1,385 líneas)
│   ├── reporte_ejecutivo.py   # Reporte ejecutivo
│   ├── heatmap_ventas.py      # Visualización de heatmaps
│   └── main_*.py              # Otros módulos
├── utils/                      # Utilidades reutilizables
│   ├── constantes.py          # Constantes centralizadas (100% coverage)
│   ├── cxc_helper.py          # Helpers CxC (93% coverage)
│   ├── formatos.py            # Formateo (82% coverage)
│   └── data_cleaner.py        # Limpieza de datos
├── tests/                      # Suite de tests (70 tests)
│   ├── conftest.py            # Fixtures compartidos
│   └── unit/
│       ├── test_cxc_helper.py # 43 tests
│       └── test_formatos.py   # 27 tests
└── data/                       # Archivos de datos

```

## 🧪 Testing

**Coverage: 91.30%** | **Tests: 70** | **Tiempo: 0.56s**

```bash
# Ejecutar todos los tests
pytest

# Ver cobertura detallada
pytest --cov-report=term-missing

# Ejecutar tests específicos
pytest tests/unit/test_cxc_helper.py
pytest tests/unit/test_formatos.py -v
```

Ver [TESTING_SUMMARY.md](TESTING_SUMMARY.md) para detalles completos.

## 📊 Calidad del Código

**Score: 94/100** 🟢 Excelente

| Categoría | Score | Estado |
|-----------|-------|--------|
| Arquitectura | 90/100 | 🟢 |
| Mantenibilidad | 92/100 | 🟢 |
| Testing | 91/100 | 🟢 |
| Performance | 88/100 | 🟢 |
| Best Practices | 95/100 | 🟢 |

Ver [.github-analysis.md](./.github-analysis.md) para análisis completo.

## 🤝 Contribuir

¿Quieres contribuir al proyecto? ¡Genial! Lee nuestra [Guía de Contribución](CONTRIBUTING.md).

### Proceso Rápido

1. **Fork** el repositorio
2. **Crea** una rama (`git checkout -b feature/amazing-feature`)
3. **Commit** tus cambios (`git commit -m 'feat: Add amazing feature'`)
4. **Push** a la rama (`git push origin feature/amazing-feature`)
5. **Abre** un Pull Request

Ver [CONTRIBUTING.md](CONTRIBUTING.md) para detalles completos sobre:
- Configuración del entorno
- Estándares de código
- Guía de testing
- Proceso de PR

## 🔧 Tecnologías

- **Framework**: Streamlit 1.40+
- **Data**: Pandas, NumPy
- **Visualización**: Plotly, Matplotlib
- **Testing**: pytest, pytest-cov
- **Type Checking**: mypy
- **Python**: 3.11, 3.12

## 📝 Documentación Adicional

- [CONTRIBUTING.md](CONTRIBUTING.md) - Guía de contribución
- [REFACTOR_SUMMARY.md](REFACTOR_SUMMARY.md) - Resumen de refactorización
- [TESTING_SUMMARY.md](TESTING_SUMMARY.md) - Documentación de testing
- [EXECUTIVE_SUMMARY.md](EXECUTIVE_SUMMARY.md) - Resumen ejecutivo
- [.github-analysis.md](.github-analysis.md) - Análisis de calidad

## 📜 Licencia

Este proyecto es privado y confidencial.

## 👥 Autores

- [@B10sp4rt4n](https://github.com/B10sp4rt4n)

---

*Este proyecto está en fase de estructuración. Los datos reales o funciones sensibles no están incluidos en esta versión pública.*
