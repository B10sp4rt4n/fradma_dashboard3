# 🤝 Guía de Contribución - Fradma Dashboard

¡Gracias por tu interés en contribuir al proyecto! Esta guía te ayudará a empezar.

---

## 📋 Tabla de Contenidos

- [Configuración del Entorno](#configuración-del-entorno)
- [Flujo de Trabajo](#flujo-de-trabajo)
- [Estándares de Código](#estándares-de-código)
- [Testing](#testing)
- [Commits](#commits)
- [Pull Requests](#pull-requests)

---

## 🛠️ Configuración del Entorno

### 1. Fork y Clone

```bash
# Fork el repositorio en GitHub
# Luego clona tu fork
git clone https://github.com/TU_USUARIO/fradma_dashboard3.git
cd fradma_dashboard3
```

### 2. Instalar Dependencias

```bash
# Dependencias de producción
pip install -r requirements.txt

# Dependencias de desarrollo
pip install -r requirements-dev.txt
```

### 3. Verificar Instalación

```bash
# Ejecutar tests
pytest

# Debería mostrar: 69 passed, 91% coverage
```

---

## 🔄 Flujo de Trabajo

### 1. Crear una Rama

```bash
# Para nuevas características
git checkout -b feature/nombre-descriptivo

# Para correcciones
git checkout -b fix/descripcion-bug

# Para refactorización
git checkout -b refactor/area-mejorada
```

### 2. Hacer Cambios

- Escribe código siguiendo los [estándares](#estándares-de-código)
- Agrega tests para nuevas funcionalidades
- Actualiza documentación si es necesario

### 3. Ejecutar Tests

```bash
# Ejecutar todos los tests
pytest

# Ver coverage
pytest --cov-report=term-missing

# Debe pasar >= 85% coverage
```

### 4. Commit y Push

```bash
git add .
git commit -m "tipo: descripción clara"
git push origin tu-rama
```

### 5. Crear Pull Request

- Ve a GitHub y crea un PR hacia `main`
- Completa la plantilla de PR
- Espera el CI/CD (debe pasar en verde ✅)
- Solicita code review

---

## 📝 Estándares de Código

### Estructura de Archivos

```
main/          # Módulos principales de la aplicación
utils/         # Utilidades reutilizables
tests/         # Suite de tests
  └── unit/    # Tests unitarios
```

### Convenciones de Nombres

```python
# Variables y funciones: snake_case
dias_vencido = 30
def calcular_dias_overdue():
    pass

# Clases: PascalCase
class UmbralesCxC:
    pass

# Constantes: UPPER_SNAKE_CASE
DIAS_ALTO_RIESGO = 90
```

### Type Hints (Requerido para nuevas funciones)

```python
from typing import Dict, List, Optional
import pandas as pd

def calcular_metricas(
    df: pd.DataFrame,
    columna_saldo: str = 'saldo_adeudado'
) -> Dict[str, float]:
    """
    Calcula métricas básicas de CxC.
    
    Args:
        df: DataFrame con datos de CxC
        columna_saldo: Nombre de la columna de saldo
        
    Returns:
        Diccionario con métricas calculadas
    """
    return {'total': df[columna_saldo].sum()}
```

### Docstrings (Requerido)

```python
def mi_funcion(parametro: str) -> int:
    """
    Una línea de descripción breve.
    
    Descripción más detallada si es necesario.
    Explica qué hace la función y por qué.
    
    Args:
        parametro: Descripción del parámetro
        
    Returns:
        Descripción del valor retornado
        
    Raises:
        ValueError: Cuando el parámetro es inválido
        
    Example:
        >>> mi_funcion("test")
        42
    """
    return len(parametro)
```

### Importaciones

```python
# 1. Standard library
import os
from datetime import datetime
from typing import Dict, List

# 2. Third-party
import pandas as pd
import streamlit as st
import plotly.express as px

# 3. Local
from utils.constantes import UmbralesCxC
from utils.cxc_helper import calcular_dias_overdue
```

---

## 🧪 Testing

### Escribir Tests

```python
import pytest
import pandas as pd
from utils.cxc_helper import calcular_dias_overdue

class TestCalcularDiasOverdue:
    """Tests para la función calcular_dias_overdue."""
    
    def test_con_dias_vencido_directo(self):
        """Debe calcular correctamente con columna dias_vencido."""
        df = pd.DataFrame({'dias_vencido': [10, 20, -5]})
        result = calcular_dias_overdue(df)
        assert result.tolist() == [10, 20, -5]
    
    def test_con_valores_nulos(self):
        """Debe manejar valores NaN correctamente."""
        df = pd.DataFrame({'dias_vencido': [10, None, 20]})
        result = calcular_dias_overdue(df)
        assert pd.isna(result.iloc[1])
```

### Usar Fixtures

```python
# En tests/conftest.py ya existen fixtures compartidos
def test_metricas_basicas(df_cxc_completo):
    """Usa el fixture df_cxc_completo."""
    metricas = calcular_metricas_basicas(df_cxc_completo)
    assert 'total_adeudado' in metricas
```

### Ejecutar Tests Específicos

```bash
# Un archivo
pytest tests/unit/test_cxc_helper.py

# Una clase
pytest tests/unit/test_cxc_helper.py::TestCalcularDiasOverdue

# Un test específico
pytest tests/unit/test_cxc_helper.py::TestCalcularDiasOverdue::test_con_dias_vencido_directo

# Con verbose
pytest -v
```

### Coverage

```bash
# Ver coverage en terminal
pytest --cov-report=term-missing

# Generar reporte HTML
pytest --cov-report=html
open htmlcov/index.html

# Mínimo requerido: 85%
```

---

## 💬 Commits

### Formato de Commit Messages

Usamos [Conventional Commits](https://www.conventionalcommits.org/):

```
tipo(scope): descripción breve

Descripción más detallada si es necesario.
Explica QUÉ cambió y POR QUÉ (no cómo).

BREAKING CHANGE: describe cambios incompatibles
```

### Tipos de Commit

| Tipo | Descripción | Ejemplo |
|------|-------------|---------|
| `feat` | Nueva característica | `feat: agregar cálculo de DSO` |
| `fix` | Corrección de bug | `fix: corregir cálculo de días mora` |
| `refactor` | Refactorización | `refactor: extraer lógica de semáforos` |
| `test` | Agregar/modificar tests | `test: agregar tests para formatos` |
| `docs` | Documentación | `docs: actualizar README` |
| `style` | Formato de código | `style: aplicar black formatter` |
| `perf` | Mejora de performance | `perf: cachear cálculo de métricas` |
| `ci` | CI/CD | `ci: agregar GitHub Actions` |
| `chore` | Tareas de mantenimiento | `chore: actualizar dependencias` |

### Ejemplos

```bash
# Bueno ✅
git commit -m "feat(cxc): agregar cálculo de DSO en métricas"
git commit -m "fix(formatos): corregir redondeo en formato_moneda"
git commit -m "test(cxc_helper): agregar tests para edge cases"

# Evitar ❌
git commit -m "cambios"
git commit -m "fix bug"
git commit -m "update"
```

---

## 🔀 Pull Requests

### Antes de Crear el PR

✅ **Checklist:**
- [ ] Los tests pasan localmente (`pytest`)
- [ ] Coverage >= 85% (`pytest --cov`)
- [ ] Código formateado (`black .`)
- [ ] Sin errores de linting (`flake8 .`)
- [ ] Documentación actualizada
- [ ] Commits con mensajes descriptivos

### Crear el PR

1. **Título descriptivo:**
   ```
   feat(cxc): Implementar cálculo de DSO y aging de cartera
   ```

2. **Descripción completa:**
   ```markdown
   ## 📋 Descripción
   Implementa el cálculo de Days Sales Outstanding (DSO) y análisis de aging
   de cartera por rangos de días.
   
   ## 🎯 Motivación
   Los usuarios necesitan ver el DSO para medir eficiencia de cobranza.
   
   ## 🔧 Cambios
   - Agregar función `calcular_dso()` en `utils/cxc_helper.py`
   - Agregar visualización de DSO en dashboard
   - Agregar 5 tests unitarios
   
   ## 🧪 Testing
   - [x] Tests unitarios agregados (coverage: 95%)
   - [x] Tested manualmente en dashboard
   
   ## 📸 Screenshots
   (Si aplica)
   
   ## 🔗 Issues Relacionados
   Closes #123
   ```

### Durante el Review

- **Responde a comentarios** rápidamente
- **Haz cambios solicitados** en la misma rama
- **Mantén el PR actualizado** con main:
  ```bash
  git checkout main
  git pull origin main
  git checkout tu-rama
  git rebase main
  git push --force-with-lease
  ```

### Criterios de Aprobación

Para que tu PR sea aprobado debe:
- ✅ CI/CD en verde (tests, linting, coverage)
- ✅ Coverage >= 85%
- ✅ Al menos 1 aprobación de code review
- ✅ No conflictos con main
- ✅ Documentación actualizada
- ✅ Commits limpios y descriptivos

---

## 🐛 Reportar Bugs

### Plantilla de Issue

```markdown
## 🐛 Descripción del Bug
Una descripción clara del problema.

## 📋 Pasos para Reproducir
1. Ir a '...'
2. Hacer click en '...'
3. Ver error

## 🎯 Comportamiento Esperado
Qué debería pasar.

## 📸 Screenshots
Si aplica.

## 🔧 Entorno
- OS: [Windows/Mac/Linux]
- Python: [3.11/3.12]
- Branch: [main/refactor/...]

## 📎 Información Adicional
Logs, stack traces, etc.
```

---

## 💡 Sugerir Mejoras

### Plantilla de Feature Request

```markdown
## 💡 Descripción de la Mejora
Una descripción clara de la funcionalidad propuesta.

## 🎯 Problema que Resuelve
Qué problema del usuario resuelve esto.

## 🔧 Solución Propuesta
Cómo se implementaría.

## 🤔 Alternativas Consideradas
Otras opciones que consideraste.

## 📊 Impacto
- Usuarios afectados: [todos/algunos]
- Prioridad: [alta/media/baja]
- Esfuerzo estimado: [horas/días]
```

---

## 📚 Recursos Adicionales

### Documentación del Proyecto

- [README.md](README.md) - Guía principal
- [TESTING_SUMMARY.md](TESTING_SUMMARY.md) - Documentación de tests
- [REFACTOR_SUMMARY.md](REFACTOR_SUMMARY.md) - Historia de refactorización
- [.github-analysis.md](.github-analysis.md) - Análisis de calidad (94/100)

### Herramientas Recomendadas

- **Editor:** VSCode con Python extension
- **Formatter:** Black (`pip install black`)
- **Linter:** Flake8 (`pip install flake8`)
- **Type Checker:** mypy (`pip install mypy`)

### Comandos Útiles

```bash
# Formatear código
black .

# Linting
flake8 .

# Type checking
mypy utils/ --ignore-missing-imports

# Tests con verbose
pytest -v

# Tests con coverage detallado
pytest --cov-report=html

# Ejecutar solo tests rápidos
pytest -m "not slow"
```

---

## 🤝 Código de Conducta

- Sé respetuoso y profesional
- Acepta críticas constructivas
- Enfócate en el problema, no en la persona
- Ayuda a otros desarrolladores
- Mantén conversaciones técnicas y objetivas

---

## ❓ Preguntas

Si tienes preguntas:
1. Revisa la [documentación](README.md)
2. Busca en [Issues existentes](https://github.com/B10sp4rt4n/fradma_dashboard3/issues)
3. Crea un nuevo Issue con la etiqueta `question`

---

## 🎉 Gracias por Contribuir

Cada contribución, grande o pequeña, ayuda a mejorar el proyecto. ¡Gracias por tu tiempo y esfuerzo! 🚀

---

*Última actualización: 15 de diciembre de 2025*
