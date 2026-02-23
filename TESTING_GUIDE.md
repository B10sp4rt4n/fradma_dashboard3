# 🧪 Guía de Testing - fradma_dashboard3

## 📚 Tabla de Contenidos

1. [Introducción](#introducción)
2. [Quick Start](#quick-start)
3. [Estructura de Tests](#estructura-de-tests)
4. [Convenciones de Naming](#convenciones-de-naming)
5. [Fixtures Disponibles](#fixtures-disponibles)
6. [Estrategias de Mocking](#estrategias-de-mocking)
7. [Agregando Nuevos Tests](#agregando-nuevos-tests)
8. [Best Practices](#best-practices)
9. [Troubleshooting](#troubleshooting)

---

## Introducción

Este proyecto usa **pytest** como framework de testing con **94.39% de coverage** en módulos `utils/`. Los tests están organizados en:

- **Tests Unitarios** (`tests/unit/`): Funciones individuales aisladas
- **Tests de Integración** (`tests/integration/`): Flujos completos de datos

### Filosofía de Testing

✅ **Testear lógica de negocio crítica** (cálculos, validaciones, transformaciones)  
✅ **Alta cobertura en utils/** (funciones reutilizables)  
❌ **No testear UI de Streamlit** (usar Playwright para E2E si es necesario)  
❌ **No sobre-testear** (ROI > 0)

---

## Quick Start

### Instalación

```bash
# Clonar repositorio
git clone https://github.com/B10sp4rt4n/fradma_dashboard3.git
cd fradma_dashboard3

# Instalar dependencias de desarrollo
pip install -r requirements-dev.txt
```

### Ejecutar Tests

```bash
# Todos los tests
pytest

# Con coverage
pytest --cov=utils --cov-report=term-missing

# modo verbose
pytest -v

# Solo un archivo
pytest tests/unit/test_cxc_helper.py

# Solo un test específico
pytest tests/unit/test_formatos.py::TestFormatoMoneda::test_formato_basico
```

### Ver Reporte HTML

```bash
pytest --cov=utils --cov-report=html
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
start htmlcov/index.html  # Windows
```

---

## Estructura de Tests

```
tests/
├── __init__.py
├── conftest.py              # Fixtures compartidos (12 fixtures)
│
├── integration/             # Tests de flujos completos
│   ├── __init__.py
│   ├── test_kpi_cpc_core.py         # Dashboard CxC (25 tests)
│   ├── test_pipeline_cxc.py         # Pipeline de datos (8 tests)
│   └── test_formatos_integration.py # Formateo en DataFrames (7 tests)
│
└── unit/                    # Tests de funciones individuales
    ├── __init__.py
    ├── test_ai_helper.py            # OpenAI integration (15 tests)
    ├── test_ai_helper_premium.py    # GPT-4o premium (8 tests)
    ├── test_cxc_helper.py           # Helpers CxC (43 tests)
    ├── test_cxc_metricas_cliente.py # Métricas por cliente (19 tests)
    ├── test_data_normalizer.py      # Normalización (14 tests)
    ├── test_data_normalizer_extended.py  # Normalización avanzada (15 tests)
    ├── test_formatos.py             # Formateo (36 tests)
    ├── test_vendedores_cxc.py       # Vendedores helpers (17 tests)
    └── test_ytd_lineas.py           # YTD logic (16 tests)
```

### ¿Unit o Integration?

| Criterio | Unit Test | Integration Test |
|----------|-----------|------------------|
| **Scope** | 1 función | Flujo completo |
| **Dependencies** | Mocked | Reales (dentro del proyecto) |
| **Velocidad** | <0.01s | <0.1s |
| **Ejemplo** | `formato_moneda()` | `preparar_datos_cxc()` pipeline |

**Regla:** Si tu test necesita > 1 función real del proyecto → **Integration**

---

## Convenciones de Naming

### Archivos de Test

```python
# ✅ CORRECTO
test_cxc_helper.py          # Testea utils/cxc_helper.py
test_formatos.py            # Testea utils/formatos.py
test_kpi_cpc_core.py        # Integration test para main/kpi_cpc.py

# ❌ INCORRECTO
cxc_helper_test.py          # pytest no lo detecta
test_utils.py               # Demasiado genérico
```

### Nombres de Test Functions

```python
# ✅ CORRECTO: test_<funcion>_<escenario>
def test_calcular_score_excelente():
    """Test: Score de salud retorna 100 con cartera perfecta."""
    ...

def test_formato_moneda_valores_negativos():
    """Test: Formatea correctamente montos negativos."""
    ...

def test_excluir_pagados_case_insensitive():
    """Test: Excluye PAGADO, Pagado, pagado."""
    ...

# ❌ INCORRECTO
def test_1():                     # No descriptivo
def testCalcularScore():          # CamelCase (usar snake_case)
def test_score():                 # Falta escenario específico
```

### Test Classes (Opcional pero Recomendado)

```python
# ✅ Agrupar tests relacionados
class TestFormatoMoneda:
    """Tests para formato_moneda()."""
    
    def test_formato_basico(self):
        assert formato_moneda(1234.56) == "$1,234.56"
    
    def test_valores_negativos(self):
        assert formato_moneda(-500) == "$-500.00"

class TestFormatoPorcentaje:
    """Tests para formato_porcentaje()."""
    
    def test_conversion_de_proporcion(self):
        assert formato_porcentaje(0.75) == "75.0%"
```

**Beneficio:** Organización clara + output agrupado en pytest

---

## Fixtures Disponibles

Todas las fixtures están en `tests/conftest.py` y son **automáticamente detectadas** por pytest.

### 1. DataFrames de CxC

#### `df_cxc_simple`
```python
@pytest.fixture
def df_cxc_simple():
    """DataFrame básico 3 filas para tests unitarios."""
    return pd.DataFrame({
        'deudor': ['Cliente A', 'Cliente B', 'Cliente C'],
        'saldo_adeudado': [10000, 5000, 3000],
        'dias_vencido': [45, 10, 90]
    })

# Uso
def test_mi_funcion(df_cxc_simple):
    resultado = mi_funcion(df_cxc_simple)
    assert len(resultado) == 3
```

#### `df_cxc_con_pagados`
```python
@pytest.fixture
def df_cxc_con_pagados():
    """Mix de registros pagados y no pagados."""
    return pd.DataFrame({
        'deudor': ['Cliente A', 'Cliente B', 'Cliente C'],
        'saldo_adeudado': [10000, 5000, 0],
        'estatus': ['PENDIENTE', 'VENCIDO', 'PAGADO']
    })
```

#### `df_cxc_completo`
```python
@pytest.fixture
def df_cxc_completo():
    """5 filas realistas con todas las columnas."""
    return pd.DataFrame({
        'deudor': ['Cliente A', 'Cliente B', 'Cliente C', 'Cliente D', 'Cliente E'],
        'saldo_adeudado': [50000, 30000, 15000, 8000, 2000],
        'dias_vencido': [120, 45, 25, 5, 0],
        'linea_de_negocio': ['Producto A', 'Producto B', ...]
    })
```

#### `df_con_fechas`
```python
@pytest.fixture
def df_con_fechas():
    """DataFrame con fechas para calcular dias_vencido."""
    return pd.DataFrame({
        'deudor': ['Cliente A', '...'],
        'fecha_vencimiento': [pd.Timestamp('2024-12-01'), ...],
        'saldo_adeudado': [10000, ...]
    })
```

#### `df_cxc_multiple_methods`
```python
@pytest.fixture
def df_cxc_multiple_methods():
    """Test de múltiples métodos de cálculo de días."""
    # Incluye: dias_vencido, dias_restante, fecha_vencimiento, etc.
```

### 2. DataFrames para Métricas por Cliente

#### `df_multiples_clientes`
```python
@pytest.fixture
def df_multiples_clientes():
    """Múltiples clientes con antigüedad y montos variados."""
```

### 3. DataFrames de Ventas/YTD

#### `df_ventas_ytd`
```python
@pytest.fixture
def df_ventas_ytd():
    """2 años completos de ventas (2025 + parcial 2026)."""
    # 365 + 46 registros diarios
```

#### `df_ventas_sin_opcionales`
```python
@pytest.fixture
def df_ventas_sin_opcionales():
    """Sin columnas 'producto' ni 'cliente'."""
```

### 4. Mocks para OpenAI

#### `fake_api_key`
```python
@pytest.fixture
def fake_api_key():
    """API key ficticia para tests."""
    return "sk-test-fake-openai-key-abc123"
```

#### `mock_openai_ytd_response`
```python
@pytest.fixture
def mock_openai_ytd_response():
    """Mock de respuesta OpenAI para análisis YTD."""
    mock = Mock()
    mock.choices[0].message.content = json.dumps({
        "diagnostico_general": "...",
        "fortalezas": ["..."],
        # ...
    })
    return mock
```

#### `mock_openai_cxc_response`
```python
# Similar pero para análisis CxC
```

#### `mock_openai_consolidado_response`
```python
# Para análisis consolidado (ventas + CxC)
```

---

## Estrategias de Mocking

### 1. Mocking OpenAI API (Patrón Estándar)

**Problema:** No queremos llamar a la API real (costo, lentitud, no determinístico)

**Solución:** Mock completo con `unittest.mock.patch`

```python
import pytest
from unittest.mock import patch, Mock
import json

@patch('utils.ai_helper.OpenAI')  # ← Mockear la clase OpenAI
def test_generar_resumen_ytd_exitoso(mock_openai_class, fake_api_key):
    """Test: generar_resumen_ejecutivo_ytd retorna análisis correcto."""
    from utils.ai_helper import generar_resumen_ejecutivo_ytd
    
    # 1. Configurar mock de respuesta
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message.content = json.dumps({
        "diagnostico_general": "Crecimiento del 15%",
        "fortalezas": ["Ventas aumentaron", "Producto A líder"],
        "areas_atencion": ["Producto C bajo"],
        "recomendaciones_estrategicas": ["Invertir más en A"]
    })
    
    # 2. Configurar mock de cliente
    mock_client = Mock()
    mock_client.chat.completions.create.return_value = mock_response
    mock_openai_class.return_value = mock_client
    
    # 3. Ejecutar función REAL (no llama a OpenAI)
    resultado = generar_resumen_ejecutivo_ytd(
        ventas_ytd_actual=2500000,
        ventas_ytd_anterior=2200000,
        crecimiento_pct=13.6,
        dias_transcurridos=45,
        proyeccion_anual=20000000,
        linea_top="Producto A",
        ventas_linea_top=1200000,
        api_key=fake_api_key
    )
    
    # 4. Validar resultado
    assert isinstance(resultado, dict)
    assert 'diagnostico_general' in resultado
    assert "Crecimiento" in resultado['diagnostico_general']
    
    # 5. Verificar que se llamó con parámetros correctos
    mock_client.chat.completions.create.assert_called_once()
    call_args = mock_client.chat.completions.create.call_args
    assert call_args.kwargs['model'] == 'gpt-4o-mini'
    assert call_args.kwargs['temperature'] == 0.7
```

**Ventajas:**
- ✅ 0 costo (no llama a API)
- ✅ Tests rápidos (<0.01s)
- ✅ Tests determinísticos (siempre mismo resultado)
- ✅ Permiten testear manejo de errores (rate limits, JSON inválido)

### 2. Mocking Fechas Determinísticas

```python
from datetime import datetime
from unittest.mock import patch

@patch('utils.cxc_helper.datetime')
def test_calcular_dias_con_fecha_fija(mock_datetime, df_con_fechas):
    # Fijar fecha "hoy" a 2025-01-15
    mock_datetime.now.return_value = datetime(2025, 1, 15)
    mock_datetime.strptime = datetime.strptime  # Keep real strptime
    
    resultado = calcular_dias_overdue(df_con_fechas)
    
    # Ahora sabemos exactamente cuántos días deberían calcularse
    assert resultado.loc[0, 'dias_vencido'] == 45  # 2025-01-15 - 2024-12-01
```

### 3. Parametrización de Tests (Sin Mocking)

```python
@pytest.mark.parametrize("valor,esperado", [
    (1234.56, "$1,234.56"),
    (-500, "$-500.00"),
    (0, "$0.00"),
    (None, "$0.00"),
    (float('nan'), "$0.00"),
])
def test_formato_moneda_multiples_casos(valor, esperado):
    from utils.formatos import formato_moneda
    assert formato_moneda(valor) == esperado
```

**Beneficio:** 1 función de test → 5 escenarios testeados

---

## Agregando Nuevos Tests

### Paso 1: Identificar el Módulo a Testear

```bash
# Ver coverage actual
pytest --cov=utils --cov-report=term-missing

# Ver líneas sin cubrir de un módulo específico
pytest --cov=utils/mi_modulo --cov-report=term-missing
```

### Paso 2: Crear Archivo de Test (si no existe)

```bash
# Para utils/mi_modulo.py → crear tests/unit/test_mi_modulo.py
touch tests/unit/test_mi_modulo.py
```

### Paso 3: Estructura Básica del Archivo

```python
"""
Tests unitarios para utils/mi_modulo.py
Descripción breve del módulo.

Coverage objetivo: 85%+
"""

import pytest
import pandas as pd
from utils.mi_modulo import (
    funcion_a_testear,
    otra_funcion
)


# ═══════════════════════════════════════════════════════════════════════
# FIXTURES (si son específicos de este módulo)
# ═══════════════════════════════════════════════════════════════════════

@pytest.fixture
def mi_fixture_local():
    """Datos específicos para estos tests."""
    return pd.DataFrame({...})


# ═══════════════════════════════════════════════════════════════════════
# TESTS: funcion_a_testear
# ═══════════════════════════════════════════════════════════════════════

def test_funcion_a_testear_caso_exitoso():
    """Test: Descripción del caso feliz."""
    # Arrange (preparar datos)
    valor_entrada = 100
    
    # Act (ejecutar función)
    resultado = funcion_a_testear(valor_entrada)
    
    # Assert (validar resultado)
    assert resultado == 200
    assert isinstance(resultado, int)


def test_funcion_a_testear_caso_error():
    """Test: Maneja valores inválidos correctamente."""
    with pytest.raises(ValueError):
        funcion_a_testear(-100)


def test_funcion_a_testear_con_dataframe(mi_fixture_local):
    """Test: Funciona con DataFrames."""
    resultado = funcion_a_testear(mi_fixture_local)
    assert len(resultado) > 0


# ═══════════════════════════════════════════════════════════════════════
# TESTS: otra_funcion
# ═══════════════════════════════════════════════════════════════════════

class TestOtraFuncion:
    """Tests para otra_funcion() agrupados."""
    
    def test_caso_basico(self):
        """Test: Caso básico exitoso."""
        assert otra_funcion(10) == 20
    
    def test_caso_edge(self):
        """Test: Maneja edge cases."""
        assert otra_funcion(0) == 0
```

### Paso 4: Ejecutar y Validar Coverage

```bash
# Ejecutar solo tu nuevo archivo
pytest tests/unit/test_mi_modulo.py -v

# Ver coverage del módulo específico
pytest tests/unit/test_mi_modulo.py --cov=utils/mi_modulo --cov-report=term-missing

# ¿Qué líneas faltan cubrir?
# Output mostrará: Missing: 45-50, 78, 92-95
```

### Paso 5: Iterar hasta 85%+

Repite: **Escribir test → Ejecutar → Ver líneas faltantes → Escribir test**

**Target:** 85%+ coverage (el 100% no siempre es necesario)

---

## Best Practices

### 1. Patrón AAA (Arrange, Act, Assert)

```python
def test_calcular_score_excelente():
    # Arrange: Preparar datos de entrada
    vigente = 100000
    vencida = 0
    critica = 0
    
    # Act: Ejecutar la función
    score = calcular_score_salud(vigente, vencida, critica)
    
    # Assert: Validar resultado
    assert score == 100
```

### 2. Un Assert Principal por Test

```python
# ✅ CORRECTO: Test enfocado
def test_formato_moneda_basico():
    assert formato_moneda(1234.56) == "$1,234.56"

# ❌ EVITAR: Test hace demasiado
def test_formato_moneda():
    assert formato_moneda(1234) == "$1,234.00"
    assert formato_moneda(-500) == "$-500.00"
    assert formato_moneda(None) == "$0.00"
    # Mejor: 3 tests separados
```

**Excepción:** Asserts auxiliares para validar estructura están OK:
```python
def test_generar_reporte():
    resultado = generar_reporte()
    assert isinstance(resultado, dict)  # ← Auxiliar
    assert 'total' in resultado  # ← Auxiliar
    assert resultado['total'] == 1000  # ← Assert principal
```

### 3. Docstrings Descriptivos

```python
def test_excluir_pagados_case_insensitive():
    """Test: Excluye registros PAGADO independientemente del case.
    
    La función debe reconocer 'PAGADO', 'Pagado', 'pagado' como
    registros pagados y excluirlos del análisis.
    """
    ...
```

**Beneficio:** Cuando falla, sabes exactamente qué se esperaba

### 4. Fixtures sobre Código Duplicado

```python
# ❌ EVITAR: Código duplicado
def test_funcion_a():
    df = pd.DataFrame({'col1': [1, 2, 3]})
    resultado = funcion_a(df)
    ...

def test_funcion_b():
    df = pd.DataFrame({'col1': [1, 2, 3]})  # ← Duplicado
    resultado = funcion_b(df)
    ...

# ✅ CORRECTO: Usar fixture
@pytest.fixture
def df_basico():
    return pd.DataFrame({'col1': [1, 2, 3]})

def test_funcion_a(df_basico):
    resultado = funcion_a(df_basico)
    ...

def test_funcion_b(df_basico):
    resultado = funcion_b(df_basico)
    ...
```

### 5. Nombres de Variables Claros

```python
# ❌ EVITAR
def test_calc():
    x = 100
    y = 50
    z = func(x, y)
    assert z == 150

# ✅ CORRECTO
def test_calcular_total_suma_dos_valores():
    valor_a = 100
    valor_b = 50
    resultado = calcular_total(valor_a, valor_b)
    assert resultado == 150
```

### 6. Testear Casos Edge

```python
def test_formatear_dias_casos_edge():
    """Test: Maneja casos edge correctamente."""
    assert formato_dias(0) == "0 días"
    assert formato_dias(1) == "1 día"  # ← Singular
    assert formato_dias(2) == "2 días"  # ← Plural
 assert formato_dias(None) == "0 días"  # ← Valor nulo
    assert formato_dias(float('nan')) == "0 días"  # ← NaN
```

---

## Troubleshooting

### Problema: "No module named 'utils'"

**Causa:** pytest no encuentra los módulos Python

**Solución 1:** Ejecutar desde el root del proyecto
```bash
cd /path/to/fradma_dashboard3
pytest
```

**Solución 2:** Agregar proyecto al PYTHONPATH
```bash
export PYTHONPATH="${PYTHONPATH}:/path/to/fradma_dashboard3"
pytest
```

**Solución 3:** Instalar en modo editable
```bash
pip install -e .
```

### Problema: "Fixture 'df_cxc_simple' not found"

**Causa:** Fixture no definida o typo en el nombre

**Solución:**
1. Verificar que `conftest.py` existe en `tests/`
2. Verificar nombre exacto del fixture
3. Ejecutar con `-v` para debugging:
```bash
pytest tests/unit/test_mi_modulo.py -v
```

### Problema: Tests pasan localmente pero fallan en CI

**Causa:** Dependencias de entorno (rutas, fechas, random)

**Solución:**
- Usar fixtures para datos determinísticos
- Mockear `datetime.now()` con fecha fija
- Evitar dependencias externas (archivos, DB)

### Problema: Coverage no aumenta aunque agregué tests

**Causa:** Los tests no están ejecutando las líneas esperadas

**Solución:**
```bash
# Ver líneas exactas faltantes
pytest --cov=utils/mi_modulo --cov-report=term-missing

# ¿Las funciones nuevas tienen imports correctos?
# ¿Los tests realmente ejecutan las ramas del código?
```

### Problema: Tests muy lentos

**Diagnóstico:**
```bash
pytest --durations=10
```

**Soluciones:**
- Reducir tamaño de DataFrames en fixtures (100 filas max)
- Mockear llamadas externas (API, DB)
- Usar `pytest-xdist` para paralelización:
```bash
pip install pytest-xdist
pytest -n auto  # Auto-detecta CPUs
```

---

## Referencias Rápidas

### Comandos Esenciales

```bash
# Run
pytest                                    # Todos los tests
pytest tests/unit/                        # Solo unitarios
pytest -k "test_formato"                  # Que contengan "test_formato"
pytest -x                                 # Parar en primer fallo

# Coverage
pytest --cov=utils --cov-report=term      # Coverage en terminal
pytest --cov=utils --cov-report=html      # Coverage HTML

# Debugging
pytest -v                                 # Verbose
pytest -s                                 # Ver prints
pytest --pdb                              # Debugger on error

# Performance
pytest --durations=10                     # Top 10 más lentos
pytest -n auto                            # Paralelización
```

### Assertions Comunes

```python
# Valores
assert resultado == esperado
assert resultado != valor
assert resultado is None
assert resultado is not None

# Tipos
assert isinstance(resultado, dict)
assert isinstance(resultado, pd.DataFrame)
assert isinstance(resultado, (int, float))

# Contenido
assert 'key' in diccionario
assert valor in lista
assert len(lista) == 5
assert lista  # Lista no vacía
assert not lista  # Lista vacía

# Numéricos
assert abs(resultado - esperado) < 0.001  # Float comparison
assert resultado > 0
assert 10 <= resultado <= 20

# Strings
assert "texto" in resultado
assert resultado.startswith("prefix")
assert resultado.endswith(".txt")

# DataFrames
assert len(df) == 10
assert 'columna' in df.columns
assert df['col'].sum() == 100
assert df.empty
assert not df.empty

# Excepciones
with pytest.raises(ValueError):
    funcion_que_falla()

with pytest.raises(ValueError, match="mensaje específico"):
    funcion_que_falla()
```

### Decoradores Útiles

```python
@pytest.mark.parametrize()    # Tests parametrizados
@pytest.mark.skip()            # Saltar test
@pytest.mark.skipif()          # Saltar si condición
@pytest.mark.xfail()           # Expected failure
@patch()                       # Mockear función/clase
```

---

## Recursos Adicionales

- **pytest docs:** https://docs.pytest.org/
- **Coverage.py docs:** https://coverage.readthedocs.io/
- **unittest.mock:** https://docs.python.org/3/library/unittest.mock.html
- **TESTING_SUMMARY.md:** Ver resultados actuales del proyecto

---

*Última actualización: 2026-02-19*  
*Versión: 1.0*
