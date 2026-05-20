"""
schema_validator.py
Valida un DataFrame contra un esquema del registro.

Reglas:
- Un archivo es valido si cumple todos los campos obligatorios.
- Campos recomendados faltantes no bloquean; se marcan como diagnostico limitado.
- Columnas desconocidas se conservan como no_mapeadas.
- No modifica el DataFrame original.
- Lanza KeyError solo si schema_id no existe o df no es valido.
"""

import pandas as pd
from typing import Union

from .schema_registry import get_schema
from .column_mapper import map_columns, get_detected_canonical_fields
from .context_score import calculate_context_score


def validate_dataframe_against_schema(
    df: pd.DataFrame,
    schema_id: str,
) -> dict:
    """
    Valida un DataFrame contra un esquema del registro.

    Args:
        df:        DataFrame a validar (no se modifica)
        schema_id: ID del esquema (e.g. 'ventas_comercial_v1')

    Returns:
        dict con resultado completo de la validacion:
        {
            "schema_id":                    str,
            "valido":                       bool,
            "campos_detectados":            list[str],   # canonicos
            "campos_faltantes_obligatorios":list[str],
            "campos_faltantes_recomendados":list[str],
            "campos_opcionales_detectados": list[str],
            "columnas_mapeadas":            dict,        # original -> canonico
            "columnas_no_mapeadas":         list[str],
            "diagnosticos_disponibles":     list[str],
            "diagnosticos_limitados":       list[str],
            "score_contexto":               int (0-100),
            "observaciones":                list[str],
        }

    Raises:
        KeyError:  Si schema_id no existe en el registro
        TypeError: Si df no es un DataFrame
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"Se esperaba un pandas DataFrame, recibido: {type(df)}")

    schema = get_schema(schema_id)  # lanza KeyError si no existe

    obligatorios  = schema.get("campos_obligatorios", [])
    recomendados  = schema.get("campos_recomendados", [])
    opcionales    = schema.get("campos_opcionales", [])
    salidas_todas = schema.get("salidas_disponibles", [])

    # ── Mapear columnas del DataFrame ──────────────────────────────────
    columnas_df        = list(df.columns)
    mapping            = map_columns(columnas_df)
    canonicos_detect   = get_detected_canonical_fields(columnas_df)
    no_mapeadas        = [c for c, v in mapping.items() if v is None]

    # ── Detectar presencia de campos por nombre canonico ───────────────
    faltantes_oblig   = [f for f in obligatorios  if f not in canonicos_detect]
    faltantes_recom   = [f for f in recomendados  if f not in canonicos_detect]
    opcionales_detect = [f for f in opcionales    if f in canonicos_detect]

    valido = len(faltantes_oblig) == 0

    # ── Determinar diagnosticos disponibles vs limitados ───────────────
    disponibles = []
    limitados   = []
    for salida in salidas_todas:
        if _salida_requiere_campos(salida, faltantes_oblig, faltantes_recom):
            limitados.append(salida)
        else:
            disponibles.append(salida)

    # ── Score de contexto ──────────────────────────────────────────────
    score_result  = calculate_context_score(canonicos_detect, schema_id=schema_id)
    score_contexto = score_result["score"]

    # ── Observaciones legibles ─────────────────────────────────────────
    observaciones = _construir_observaciones(
        valido, faltantes_oblig, faltantes_recom, no_mapeadas, schema_id
    )

    return {
        "schema_id":                     schema_id,
        "valido":                         valido,
        "campos_detectados":              canonicos_detect,
        "campos_faltantes_obligatorios":  faltantes_oblig,
        "campos_faltantes_recomendados":  faltantes_recom,
        "campos_opcionales_detectados":   opcionales_detect,
        "columnas_mapeadas":              {k: v for k, v in mapping.items() if v is not None},
        "columnas_no_mapeadas":           no_mapeadas,
        "diagnosticos_disponibles":       disponibles,
        "diagnosticos_limitados":         limitados,
        "score_contexto":                 score_contexto,
        "observaciones":                  observaciones,
    }


# =====================================================================
# HELPERS INTERNOS
# =====================================================================

def _salida_requiere_campos(salida: str, faltantes_oblig: list, faltantes_recom: list) -> bool:
    """
    Heuristica simple: si hay obligatorios faltantes, todas las salidas
    son limitadas. Si solo faltan recomendados, salidas que dependen de
    esos campos se marcan como limitadas.
    """
    if faltantes_oblig:
        return True  # bloqueo total

    # Salidas que dependen de campos recomendados especificos
    dependencias = {
        "top_clientes":              ["cliente"],
        "desempeno_vendedor":        ["vendedor"],
        "ventas_por_linea":          ["linea_de_negocio"],
        "ventas_por_producto":       ["producto"],
        "heatmap_ventas":            ["linea_de_negocio"],
        "ytd_lineas":                ["linea_de_negocio"],
        "ytd_productos":             ["producto"],
        "aging_buckets":             ["fecha_vencimiento", "dias_vencido"],
        "score_salud_cxc":           ["dias_vencido"],
        "plan_cobranza":             ["dias_vencido", "vendedor"],
        "desempeno_cobranza_vendedor": ["vendedor"],
        "clientes_activos":          ["cliente"],
        "comparativo_anual":         ["fecha"],
        "series_temporales":         ["fecha"],
    }

    reqs = dependencias.get(salida, [])
    return any(r in faltantes_recom for r in reqs)


def _construir_observaciones(
    valido: bool,
    faltantes_oblig: list,
    faltantes_recom: list,
    no_mapeadas: list,
    schema_id: str,
) -> list:
    obs = []
    if valido:
        obs.append(f"El archivo cumple los campos obligatorios del schema '{schema_id}'.")
    else:
        obs.append(
            f"INVALIDO: Faltan campos obligatorios: {faltantes_oblig}. "
            "El modulo no podra activarse con este archivo."
        )
    if faltantes_recom:
        obs.append(
            f"Campos recomendados faltantes: {faltantes_recom}. "
            "Algunos diagnosticos estaran limitados."
        )
    if no_mapeadas:
        obs.append(
            f"{len(no_mapeadas)} columna(s) no reconocidas (se conservan tal cual): "
            f"{no_mapeadas[:5]}{'...' if len(no_mapeadas) > 5 else ''}."
        )
    return obs
