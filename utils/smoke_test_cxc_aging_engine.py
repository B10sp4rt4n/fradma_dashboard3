"""
smoke_test_cxc_aging_engine.py
Smoke test para utils/cxc_aging_engine.prepare_cxc_metrics.
Valida los invariantes de negocio más importantes del motor de CxC.

Ejecución:
    python utils/smoke_test_cxc_aging_engine.py

Salida esperada (sin fallos):
    CXC Aging Engine smoke test:
    8 OK / 0 FAIL
"""

from __future__ import annotations

import sys
import traceback
from datetime import date, timedelta
from typing import List, Tuple

import pandas as pd

# ── Asegurar que el directorio raíz está en sys.path ─────────────────────
import os
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from utils.cxc_aging_engine import prepare_cxc_metrics

# ══════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════

FECHA_CORTE = pd.Timestamp(date.today())


def _ok(nombre: str, resultados: list) -> Tuple[bool, str]:
    """Devuelve (passed, mensaje) para un caso de prueba."""
    fallas = [r for r in resultados if r is not None]
    if not fallas:
        return True, f"OK  {nombre}"
    return False, f"FAIL {nombre}: " + "; ".join(fallas)


def _assert(cond: bool, mensaje: str):
    """Devuelve None si la condición se cumple, mensaje de error si no."""
    return None if cond else mensaje


# ══════════════════════════════════════════════════════════════════════════
# Casos de prueba
# ══════════════════════════════════════════════════════════════════════════

def caso_01_todo_vigente():
    """Caso 1: Todo vigente (dias_vencido ≤ 0 en todas las filas)."""
    df = pd.DataFrame({
        "cliente":       ["A", "B", "C"],
        "saldo_adeudado": [100_000.0, 200_000.0, 50_000.0],
        "dias_vencido":   [-10, 0, -5],
    })
    m = prepare_cxc_metrics(df)
    total = 350_000.0
    res = [
        _assert(abs(m["total_adeudado"] - total) < 0.01, f"total esperado {total}, got {m['total_adeudado']}"),
        _assert(m["bucket_0_30"]  == 0.0, f"bucket_0_30 debe ser 0, got {m['bucket_0_30']}"),
        _assert(m["bucket_31_60"] == 0.0, f"bucket_31_60 debe ser 0, got {m['bucket_31_60']}"),
        _assert(m["bucket_61_90"] == 0.0, f"bucket_61_90 debe ser 0, got {m['bucket_61_90']}"),
        _assert(m["bucket_mas_90"] == 0.0, f"bucket_mas_90 debe ser 0, got {m['bucket_mas_90']}"),
        _assert(m["score_salud"] == 100, f"score debe ser 100, got {m['score_salud']}"),
    ]
    return _ok("Caso 1 — Todo vigente", res)


def caso_02_cartera_distribuida():
    """Caso 2: Cartera distribuida en todos los buckets."""
    df = pd.DataFrame({
        "cliente":       ["A", "B", "C", "D", "E"],
        "saldo_adeudado": [100_000.0, 50_000.0, 30_000.0, 20_000.0, 10_000.0],
        "dias_vencido":   [-5,         15,        45,        75,        120],
    })
    m = prepare_cxc_metrics(df)
    total = 210_000.0
    res = [
        _assert(abs(m["total_adeudado"] - total) < 0.01, f"total {total} != {m['total_adeudado']}"),
        _assert(abs(m["bucket_vigente"] - 100_000) < 0.01, f"vigente 100000 != {m['bucket_vigente']}"),
        _assert(abs(m["bucket_0_30"]   -  50_000) < 0.01, f"0-30 50000 != {m['bucket_0_30']}"),
        _assert(abs(m["bucket_31_60"]  -  30_000) < 0.01, f"31-60 30000 != {m['bucket_31_60']}"),
        _assert(abs(m["bucket_61_90"]  -  20_000) < 0.01, f"61-90 20000 != {m['bucket_61_90']}"),
        _assert(abs(m["bucket_mas_90"] -  10_000) < 0.01, f">90 10000 != {m['bucket_mas_90']}"),
    ]
    return _ok("Caso 2 — Cartera distribuida", res)


def caso_03_dias_vencido_directo():
    """Caso 3: Usar dias_vencido directo (prioridad 1 de la cadena)."""
    df = pd.DataFrame({
        "cliente":       ["X", "Y"],
        "saldo_adeudado": [500_000.0, 100_000.0],
        "dias_vencido":   [-1,         95],
        # También incluimos vencimiento (fecha pasada) para verificar que
        # dias_vencido toma prioridad sobre la fecha de vencimiento
        "vencimiento":   [
            (date.today() - timedelta(days=120)).isoformat(),
            (date.today() - timedelta(days=95)).isoformat(),
        ],
    })
    m = prepare_cxc_metrics(df)
    res = [
        _assert(abs(m["bucket_vigente"]  - 500_000) < 0.01,
                f"X debe ser vigente (dias_vencido=-1 tiene prioridad), got bucket_vigente={m['bucket_vigente']}"),
        _assert(abs(m["bucket_mas_90"] - 100_000) < 0.01,
                f"Y debe estar en >90d, got bucket_mas_90={m['bucket_mas_90']}"),
    ]
    return _ok("Caso 3 — dias_vencido directo (prioridad 1)", res)


def caso_04_fecha_vencimiento():
    """Caso 4: Calcular dias_vencido desde columna fecha_vencimiento (prioridad 2)."""
    df = pd.DataFrame({
        "cliente":         ["P", "Q"],
        "saldo_adeudado":   [80_000.0, 40_000.0],
        "fecha_vencimiento": [
            (date.today() + timedelta(days=15)).isoformat(),   # P: aún vigente
            (date.today() - timedelta(days=45)).isoformat(),   # Q: vencido 45 días
        ],
        # Sin columna dias_vencido → debe usar fecha_vencimiento
    })
    m = prepare_cxc_metrics(df)
    res = [
        _assert(m["bucket_vigente"] > 0, "P vigente esperado"),
        _assert(m["bucket_31_60"] > 0,   "Q en 31-60d esperado"),
        _assert(m["bucket_0_30"] == 0.0,  f"bucket_0_30 debe ser 0, got {m['bucket_0_30']}"),
    ]
    return _ok("Caso 4 — fecha_vencimiento (prioridad 2)", res)


def caso_05_fecha_mas_dias_credito():
    """Caso 5: Calcular vencimiento desde fecha + dias_credito (prioridad 3)."""
    df = pd.DataFrame({
        "cliente":      ["R"],
        "saldo_adeudado": [100_000.0],
        "fecha":        [(date.today() - timedelta(days=50)).isoformat()],
        "dias_credito": [30],   # Vence a los 30d → vencimiento hace 20 días → bucket 0-30
    })
    m = prepare_cxc_metrics(df)
    res = [
        _assert(
            m["bucket_0_30"] > 0 or m["bucket_31_60"] > 0,
            f"R vencido esperado (0-30 o 31-60), got vigente={m['bucket_vigente']} 0-30={m['bucket_0_30']} 31-60={m['bucket_31_60']}"
        ),
    ]
    return _ok("Caso 5 — fecha + dias_credito (prioridad 3)", res)


def caso_06_excluir_pagados():
    """Caso 6: Registros pagados deben excluirse del cálculo."""
    df = pd.DataFrame({
        "cliente":       ["S", "T", "U"],
        "saldo_adeudado": [200_000.0, 50_000.0, 75_000.0],
        "dias_vencido":   [5,          10,        -3],
        "estatus":        ["pagado",    "abierto", "Abierto"],
    })
    m = prepare_cxc_metrics(df)
    # S está pagado → excluido → total debe ser 125_000
    res = [
        _assert(
            abs(m["total_adeudado"] - 125_000.0) < 0.01,
            f"total esperado 125000, got {m['total_adeudado']} (S pagado debe excluirse)"
        ),
        _assert(m["filas_descartadas"] == 1, f"filas_descartadas esperado 1, got {m['filas_descartadas']}"),
    ]
    return _ok("Caso 6 — Excluir registros pagados", res)


def caso_07_suma_buckets():
    """Caso 7: Suma de buckets debe ser igual a total_adeudado."""
    import random
    random.seed(42)
    n = 50
    montos = [round(random.uniform(1_000, 100_000), 2) for _ in range(n)]
    dias   = [random.randint(-10, 200) for _ in range(n)]
    df = pd.DataFrame({
        "cliente":       [f"CLI_{i}" for i in range(n)],
        "saldo_adeudado": montos,
        "dias_vencido":   dias,
    })
    m = prepare_cxc_metrics(df)
    diff = abs(m["diferencia_total_vs_buckets"])
    res = [
        _assert(diff < 0.02, f"diferencia total vs buckets debe ser <0.02, got {diff:.6f}"),
    ]
    return _ok("Caso 7 — suma_buckets == total_adeudado", res)


def caso_08_score_decae_con_mora():
    """Caso 8: Score es más bajo cuando aumenta cartera vencida."""
    df_sano = pd.DataFrame({
        "cliente":       ["V1", "V2"],
        "saldo_adeudado": [100_000.0, 10_000.0],
        "dias_vencido":   [-1,         20],
    })
    df_moroso = pd.DataFrame({
        "cliente":       ["M1", "M2"],
        "saldo_adeudado": [10_000.0, 100_000.0],
        "dias_vencido":   [-1,        95],
    })
    m_sano   = prepare_cxc_metrics(df_sano)
    m_moroso = prepare_cxc_metrics(df_moroso)
    res = [
        _assert(
            m_sano["score_salud"] > m_moroso["score_salud"],
            f"Score sano ({m_sano['score_salud']}) debe ser > moroso ({m_moroso['score_salud']})"
        ),
    ]
    return _ok("Caso 8 — Score decae con mayor mora", res)


# ══════════════════════════════════════════════════════════════════════════
# Ejecución
# ══════════════════════════════════════════════════════════════════════════

CASOS = [
    caso_01_todo_vigente,
    caso_02_cartera_distribuida,
    caso_03_dias_vencido_directo,
    caso_04_fecha_vencimiento,
    caso_05_fecha_mas_dias_credito,
    caso_06_excluir_pagados,
    caso_07_suma_buckets,
    caso_08_score_decae_con_mora,
]


def main():
    ok_count = 0
    fail_count = 0
    for fn in CASOS:
        try:
            passed, msg = fn()
        except Exception as exc:
            passed, msg = False, f"FAIL {fn.__name__}: EXCEPCION — {exc}"
            traceback.print_exc()
        print(msg)
        if passed:
            ok_count += 1
        else:
            fail_count += 1

    print(f"\nCXC Aging Engine smoke test:\n{ok_count} OK / {fail_count} FAIL")
    sys.exit(0 if fail_count == 0 else 1)


if __name__ == "__main__":
    main()
