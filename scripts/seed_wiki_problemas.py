"""
Seed de problemas recurrentes resueltos en la wiki.
Ejecutar: python scripts/seed_wiki_problemas.py

Requiere NEON_DATABASE_URL en el entorno o en .env
"""
import os
import sys
from pathlib import Path

# Asegurar que el root del proyecto esté en el path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from utils.problem_wiki import add_problem, Problema

NEON_URL = os.environ.get("NEON_DATABASE_URL", "")
if not NEON_URL:
    print("❌ NEON_DATABASE_URL no configurado. Agrégalo al .env")
    sys.exit(1)

PROBLEMAS = [
    Problema(
        codigo="DA-001",
        titulo="Donut chart muestra porcentajes incorrectos cuando hay >15 clientes",
        modulo="data_assistant",
        sintoma="La gráfica donut en concentración de clientes muestra al cliente top como 44-45% cuando en realidad es ~32%. El texto de interpretación del LLM muestra números distintos a la gráfica.",
        causa_raiz="El renderer del donut hacía head(15) antes de pasar a Plotly. Plotly recalcula los porcentajes sobre las filas visibles, descartando el resto del universo del denominador.",
        solucion="1) SQL devuelve top 10 + fila 'Otros' que agrupa el resto (UNION ALL), garantizando que sumen 100%. 2) El renderer detecta si ya hay 'Otros' y usa todas las filas; si no, agrega 'Otros' manualmente antes de pasar a px.pie().",
        intentos=[
            {"descripcion": "Aumentar head(15) a head(25)", "resultado": "No resuelve, sigue descartando clientes pequeños del denominador"},
        ],
        leccion="Para gráficas de distribución (pie/donut), SIEMPRE usar el universo completo o agregar fila 'Otros'. Nunca cortar filas antes de calcular proporciones.",
        tags=["donut", "pie", "porcentajes", "concentración", "data_assistant", "gráfica"],
        resuelto=True,
    ),
    Problema(
        codigo="DA-002",
        titulo="Columnas con nombre 'pct_*' llegan como Decimal/object y no se formatean con '%'",
        modulo="data_assistant",
        sintoma="La tabla del asistente de datos muestra valores como '0.14' en columnas tipo pct_del_total en lugar de '14.0%'. El signo % nunca aparece.",
        causa_raiz="_coerce_numeric_like_columns() solo convierte a float64 columnas cuyos nombres coincidan con count_keywords o money_keywords. Las columnas 'pct_*'/'porcentaje_*' no estaban en ninguna lista, por lo que llegaban como Decimal de psycopg2 o string y select_dtypes(include='number') las ignoraba. _format_numeric_display_dataframe() nunca las procesaba.",
        solucion="Agregar condición 'pct' in col_lower or 'porcentaje' in col_lower or col_lower.endswith('_pct') al check looks_numeric en _coerce_numeric_like_columns().",
        intentos=[
            {"descripcion": "Agregar 'pct' a money_keywords", "resultado": "Hubiera funcionado pero es semánticamente incorrecto (no es dinero)"},
        ],
        leccion="Al agregar nuevas columnas SQL con prefijo 'pct_', verificar que _coerce_numeric_like_columns las reconozca. Los tipos Decimal de psycopg2 no son detectados por select_dtypes('number') hasta convertirlos explícitamente.",
        tags=["pct", "porcentaje", "formato", "tabla", "data_assistant", "decimal", "psycopg2"],
        resuelto=True,
    ),
    Problema(
        codigo="CI-001",
        titulo="CI falla por cobertura insuficiente al incluir módulos de infraestructura",
        modulo="pytest / CI",
        sintoma="El pipeline de GitHub Actions reporta 'Coverage failure: total of 55% is less than fail-under=85%'. Tests pasan localmente pero CI falla.",
        causa_raiz="pytest.ini medía cobertura sobre todo utils/ incluyendo módulos que requieren infraestructura externa (DB Neon, OpenAI API, Streamlit UI): admin_panel.py, nl2sql.py, auth.py, neon_loader.py, sovereign_periods.py, problem_wiki.py, guided_usage_metrics.py, guided_catalog_store.py. Estos tienen 0-15% de cobertura al no poder ejecutarse sin sus dependencias externas.",
        solucion="Agregar sección [coverage:run] omit en pytest.ini excluyendo los módulos de infraestructura/LLM/UI que no pueden testearse en CI sin conexiones externas.",
        intentos=[],
        leccion="Al agregar módulos nuevos que dependan de DB/API externas, agregarlos inmediatamente al omit de [coverage:run] en pytest.ini para evitar romper el threshold de cobertura en CI.",
        tags=["coverage", "pytest", "CI", "infraestructura", "neon", "omit"],
        resuelto=True,
    ),
]

if __name__ == "__main__":
    ok = 0
    fail = 0
    for p in PROBLEMAS:
        result = add_problem(NEON_URL, p)
        if result:
            print(f"  ✅ {p.codigo} — {p.titulo[:60]}")
            ok += 1
        else:
            print(f"  ❌ {p.codigo} — falló inserción")
            fail += 1

    print(f"\n{ok} insertados, {fail} fallidos.")
