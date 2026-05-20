"""
cxc_aging_engine.py
Motor centralizado de Aging y Score Salud de Cuentas por Cobrar — CIMA.

Fuente única de verdad para:
  - Normalización de columnas (saldo, fecha, dias_vencido, estatus)
  - Clasificación por antigüedad (buckets vigente / 0-30 / 31-60 / 61-90 / >90)
  - Cálculo de cartera vigente, vencida y crítica
  - Score de salud CxC (fórmula canónica, ver abajo)
  - Exclusión de registros pagados / cerrados
  - Validación de consistencia total ↔ suma de buckets
  - Diagnóstico técnico auditble

TODOS los módulos de CIMA que necesiten métricas de CxC deben importar
`prepare_cxc_metrics` de aquí.  Nunca calcular aging o score en módulos
individuales.

SCORE SALUD (fórmula canónica — documentada para todas las vistas):
    score = (pct_vigente  * 100
           + pct_0_30    *  70
           + pct_31_60   *  40
           + pct_61_90   *  20
           + pct_mas_90  *   0) / 100
    Normalizado a [0, 100], redondeado a entero.

PRIORIDAD DE CÁLCULO DE días vencido:
    1. dias_vencido / dias_vencidos        — si existe y es numérico válido
    2. fecha_vencimiento / vencimiento     — (fecha_corte - fecha_venc).days
    3. fecha_emision + dias_credito        — fecha_venc calculada, luego igual
    4. fecha sola + 30 días estándar       — estimado, se registra en diagnostico

RESTRICCIONES:
  - No conectores reales
  - No Neon, S3, SAE, CONTPAQi
  - No modifica dashboards existentes fuera de CxC
  - No toca lógica de ventas
"""

from __future__ import annotations

import pandas as pd
from typing import Dict, List, Optional

from utils.cxc_helper import (
    calcular_cxc_aging,
    clasificar_score_salud,
    detectar_columna,
)
from utils.constantes import COLUMNAS_ESTATUS
from utils.logger import configurar_logger

logger = configurar_logger("cxc_aging_engine", nivel="INFO")

# ── Identificador de fuente (para diagnóstico) ─────────────────────────────
_FUENTE = "utils/cxc_aging_engine.py"

# ── Columnas normalizadas aceptadas ────────────────────────────────────────
COLUMNAS_CLIENTE     = ["cliente", "deudor", "razon_social", "receptor_nombre"]
COLUMNAS_SALDO       = [
    "saldo_adeudado", "saldo", "saldo_usd", "saldo_mxn",
    "adeudo", "saldo_adeudo", "open_amount", "balance",
]
COLUMNAS_FECHA       = ["fecha", "fecha_emision", "fecha_factura", "fecha_documento"]
COLUMNAS_VENCIMIENTO = [
    "fecha_vencimiento", "vencimiento", "fecha_venc", "due_date", "fecha_limite_pago",
]
COLUMNAS_DIAS_VENCIDO = [
    "dias_vencido", "dias_vencidos", "dias_mora", "dias_de_mora", "overdue_days",
]
COLUMNAS_DIAS_CREDITO = ["dias_credito", "dias_de_credito", "credit_days"]
COLUMNAS_FACTURA      = ["factura", "folio", "documento", "invoice", "invoice_number"]
COLUMNAS_VENDEDOR     = ["vendedor", "agente", "ejecutivo", "seller", "rep"]

# Estatus que indican documento cerrado / pagado
_ESTATUS_CERRADO = frozenset({
    "pagado", "paid", "cerrado", "liquidado", "cancelado",
    "pagada", "cobrado", "cobrada", "saldado", "saldada",
    "finiquitado", "finiquitada",
})


# ══════════════════════════════════════════════════════════════════════════════
# FUNCIÓN CANÓNICA PÚBLICA
# ══════════════════════════════════════════════════════════════════════════════

def prepare_cxc_metrics(
    df_cxc: pd.DataFrame,
    fecha_corte=None,
    config: Optional[Dict] = None,
) -> Dict:
    """
    Función canónica para preparar métricas de Cuentas por Cobrar.

    Recibe un DataFrame de CxC ya cargado o combinado (VIGENTES + VENCIDAS).
    Llama al motor base ``calcular_cxc_aging`` de ``utils.cxc_helper`` y
    construye el diccionario estándar de métricas.

    Args:
        df_cxc:      DataFrame con datos de CxC (brutos o normalizados).
        fecha_corte: datetime/str/None.  Si None usa fecha actual del sistema.
        config:      dict opcional de configuración:
                       • col_estatus   (str)  — nombre de columna de estatus
                       • columna_fecha (str)  — columna de fecha preferida

    Returns:
        dict — métricas estándar + DataFrames + diagnóstico.  Ver sección
        "Returns" del docstring de ``calcular_cxc_aging`` para campos raw.

    Schema de retorno (campos garantizados):
        total_adeudado         float
        vigente_monto          float
        vigente_pct            float
        vencido_monto          float
        vencido_pct            float
        bucket_vigente         float   (alias de vigente_monto)
        bucket_0_30            float
        bucket_31_60           float
        bucket_61_90           float
        bucket_mas_90          float
        critica_mas_30         float
        score_salud            int
        clasificacion_salud    str     (Crítico/Malo/Regular/Bueno/Excelente)
        fecha_corte_usada      str     YYYY-MM-DD
        fecha_corte_ts         Timestamp
        columna_fecha_usada    str
        columna_monto_usada    str
        filas_consideradas     int
        filas_descartadas      int
        monto_validado_total   float
        suma_buckets           float
        diferencia_total_vs_buckets  float
        df_normalizado         DataFrame  (registros no pagados)
        df_prep                DataFrame  (todos, con dias_overdue)
        mask_pagado            Series[bool]
        diagnostico            List[str]
        fuente_calculo         str
        ── Aliases para compatibilidad ──────────────────────
        pct_vigente            float
        pct_vencida            float
        pct_critica            float
        pct_vencida_0_30       float
        pct_vencida_31_60      float
        pct_vencida_61_90      float
        pct_alto_riesgo        float
        vigente                float   (= vigente_monto)
        vencida                float   (= vencido_monto)
        vencida_0_30           float
        vencida_31_60          float
        vencida_61_90          float
        alto_riesgo            float   (= bucket_mas_90)
        critica                float   (= critica_mas_30)
        score                  int     (= score_salud)
        status                 str     (= clasificacion_salud)
        df_np                  DataFrame  (= df_normalizado)
    """
    config = config or {}
    diagnostico: List[str] = []

    # ── Motor base ─────────────────────────────────────────────────────────
    resultado = calcular_cxc_aging(df_cxc, fecha_corte=fecha_corte, config=config)

    # ── Extraer campos principales ─────────────────────────────────────────
    total_adeudado = resultado["total_adeudado"]
    vigente        = resultado["vigente_monto"]
    b030           = resultado["bucket_0_30"]
    b3160          = resultado["bucket_31_60"]
    b6190          = resultado["bucket_61_90"]
    bmas90         = resultado["bucket_mas_90"]
    critica        = resultado["critica_mas_30"]

    suma_buckets = vigente + b030 + b3160 + b6190 + bmas90

    mask_pagado     = resultado.get("mask_pagado", pd.Series(False, dtype=bool))
    filas_descartadas = int(mask_pagado.sum()) if isinstance(mask_pagado, pd.Series) else 0

    # ── Diagnóstico ────────────────────────────────────────────────────────
    if resultado.get("columna_fecha_usada") is None:
        diagnostico.append(
            "Sin columna de fecha detectada. "
            "Aging estimado con 30 días de crédito estándar."
        )

    _df_prep_diag = resultado.get("df_prep", pd.DataFrame())
    _col_estatus = detectar_columna(_df_prep_diag, COLUMNAS_ESTATUS)
    if _col_estatus is None:
        diagnostico.append(
            "Sin columna de estatus; se asume que todos los registros "
            "representan saldo abierto."
        )
    elif filas_descartadas > 0:
        diagnostico.append(
            f"{filas_descartadas} registro(s) excluidos por estar marcados como "
            f"pagados/cerrados en columna '{_col_estatus}'."
        )

    dif_abs = abs(resultado["diferencia_total_buckets"])
    if dif_abs > 1.0:
        diagnostico.append(
            f"Advertencia: diferencia entre total_adeudado ({total_adeudado:,.2f}) "
            f"y suma_buckets ({suma_buckets:,.2f}) = "
            f"{resultado['diferencia_total_buckets']:.2f}. "
            "Revisar duplicados o saldos negativos en el archivo fuente."
        )

    # ── Tipo de fecha usada ────────────────────────────────────────────────
    col_fecha_usada = resultado.get("columna_fecha_usada") or ""
    if col_fecha_usada in ("fecha_vencimiento", "vencimiento", "fecha_venc"):
        diagnostico.append(
            f"Aging calculado desde columna de vencimiento: '{col_fecha_usada}'."
        )
    elif col_fecha_usada:
        diagnostico.append(
            f"Aging calculado desde columna de fecha: '{col_fecha_usada}' "
            "(con crédito estándar o dias_credito si disponible)."
        )

    # ── Metadata de fecha de corte ─────────────────────────────────────────
    fecha_corte_ts  = resultado["fecha_corte_usada"]
    fecha_corte_str = str(fecha_corte_ts.date()) if pd.notna(fecha_corte_ts) else ""

    col_monto_usada = (resultado.get("columnas_monto_detectadas") or ["saldo_adeudado"])[0]

    logger.info(
        "prepare_cxc_metrics: total=%.2f score=%s buckets=%.2f/%.2f/%.2f/%.2f/%.2f "
        "fecha_corte=%s fuente=%s",
        total_adeudado,
        resultado["score_salud"],
        vigente, b030, b3160, b6190, bmas90,
        fecha_corte_str,
        _FUENTE,
    )

    # ── Dict de retorno ────────────────────────────────────────────────────
    return {
        # Métricas principales
        "total_adeudado":              total_adeudado,
        "vigente_monto":               vigente,
        "vigente_pct":                 resultado["vigente_pct"],
        "vencido_monto":               resultado["vencido_monto"],
        "vencido_pct":                 resultado["vencido_pct"],
        # Buckets
        "bucket_vigente":              vigente,
        "bucket_0_30":                 b030,
        "bucket_31_60":                b3160,
        "bucket_61_90":                b6190,
        "bucket_mas_90":               bmas90,
        # Crítica
        "critica_mas_30":              critica,
        # Score
        "score_salud":                 resultado["score_salud"],
        "clasificacion_salud":         resultado["clasificacion_salud"],
        # Diagnóstico técnico
        "fecha_corte_str":             fecha_corte_str,
        "fecha_corte_usada":           fecha_corte_ts,        # Timestamp (compat)
        "fecha_corte_ts":              fecha_corte_ts,
        "columna_fecha_usada":         col_fecha_usada,
        "columna_monto_usada":         col_monto_usada,
        "filas_consideradas":          resultado["filas_consideradas"],
        "filas_descartadas":           filas_descartadas,
        "monto_validado_total":        resultado["monto_validado_total"],
        "suma_buckets":                suma_buckets,
        "diferencia_total_vs_buckets": resultado["diferencia_total_buckets"],
        # DataFrames
        "df_normalizado":              resultado["df_np"],
        "df_prep":                     resultado["df_prep"],
        "mask_pagado":                 mask_pagado,
        # Diagnóstico
        "diagnostico":                 diagnostico,
        "fuente_calculo":              _FUENTE,
        # Porcentajes extendidos
        "pct_vigente":                 resultado["vigente_pct"],
        "pct_vencida":                 resultado["vencido_pct"],
        "pct_critica":                 resultado["pct_critica"],
        "pct_vencida_0_30":            resultado["pct_vencida_0_30"],
        "pct_vencida_31_60":           resultado["pct_vencida_31_60"],
        "pct_vencida_61_90":           resultado["pct_vencida_61_90"],
        "pct_alto_riesgo":             resultado["pct_alto_riesgo"],
        "fecha_min":                   resultado.get("fecha_min"),
        "fecha_max":                   resultado.get("fecha_max"),
        # Aliases para compatibilidad con módulos existentes
        "vigente":                     vigente,
        "vencida":                     resultado["vencido_monto"],
        "vencida_0_30":                b030,
        "vencida_31_60":               b3160,
        "vencida_61_90":               b6190,
        "alto_riesgo":                 bmas90,
        "critica":                     critica,
        "score":                       resultado["score_salud"],
        "status":                      resultado["clasificacion_salud"],
        "df_np":                       resultado["df_np"],
    }
