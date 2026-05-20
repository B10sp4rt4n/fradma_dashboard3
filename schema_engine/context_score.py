"""
context_score.py
Calcula el score de completitud contextual de 0 a 100.

Dimensiones y pesos:
  Tiempo           25 pts  fecha, fecha_emision, fecha_vencimiento
  Valor economico  25 pts  monto, saldo_adeudado, total_mxn, importe
  Actor            20 pts  cliente, vendedor, receptor_rfc, receptor_nombre
  Clasificacion    15 pts  linea_de_negocio, producto, canal, region, categoria
  Estado/condicion 15 pts  estatus, dias_vencido, dias_credito, fecha_pago, forma_pago
"""

from typing import Optional


# =====================================================================
# DEFINICION DE DIMENSIONES
# =====================================================================

CONTEXT_DIMENSIONS = {
    "tiempo": {
        "max": 25,
        "campos": ["fecha", "fecha_emision", "fecha_vencimiento", "fecha_pago"],
        "descripcion": "Dimension temporal: fechas que permiten analisis cronologico",
    },
    "valor": {
        "max": 25,
        "campos": ["monto", "saldo_adeudado", "total_mxn", "importe", "subtotal"],
        "descripcion": "Valor economico: montos que permiten calcular KPIs financieros",
    },
    "actor": {
        "max": 20,
        "campos": ["cliente", "vendedor", "receptor_rfc", "receptor_nombre", "proveedor"],
        "descripcion": "Actores: partes involucradas en la transaccion",
    },
    "clasificacion": {
        "max": 15,
        "campos": ["linea_de_negocio", "producto", "canal", "region", "categoria", "familia"],
        "descripcion": "Clasificacion: segmentacion del negocio",
    },
    "estado": {
        "max": 15,
        "campos": ["estatus", "dias_vencido", "dias_credito", "forma_pago", "metodo_pago", "moneda"],
        "descripcion": "Estado/condicion: calidad e informacion de cobro",
    },
}


# =====================================================================
# FUNCION PRINCIPAL
# =====================================================================

def calculate_context_score(
    detected_canonical_fields: list,
    schema_id: Optional[str] = None,
) -> dict:
    """
    Calcula el score de completitud contextual basado en campos canonicos detectados.

    Args:
        detected_canonical_fields: Lista de nombres canonicos detectados en el DataFrame
                                   (resultado de get_detected_canonical_fields())
        schema_id:                 Opcional. ID del schema para contexto en el resultado.

    Returns:
        {
            "score":   int (0-100),
            "schema_id": str o None,
            "detalle": {
                "tiempo":        {"puntos": int, "max": 25, "campos_detectados": [...]},
                "valor":         {"puntos": int, "max": 25, "campos_detectados": [...]},
                "actor":         {"puntos": int, "max": 20, "campos_detectados": [...]},
                "clasificacion": {"puntos": int, "max": 15, "campos_detectados": [...]},
                "estado":        {"puntos": int, "max": 15, "campos_detectados": [...]},
            }
        }

    Example:
        fields = ["fecha", "monto", "cliente", "vendedor"]
        result = calculate_context_score(fields)
        # result["score"] -> 70  (25 tiempo + 25 valor + 20 actor + 0 clasificacion + 0 estado)
    """
    detected_set = set(detected_canonical_fields)
    detalle = {}
    total_score = 0

    for dim_name, dim_config in CONTEXT_DIMENSIONS.items():
        max_pts     = dim_config["max"]
        dim_campos  = dim_config["campos"]
        detectados  = [c for c in dim_campos if c in detected_set]

        if not dim_campos:
            puntos = 0
        else:
            # Puntuacion proporcional: detectados / total_campos * max_pts
            ratio  = len(detectados) / len(dim_campos)
            puntos = int(round(ratio * max_pts))
            # Garantizar que al menos 1 campo da puntaje parcial visible
            if detectados and puntos == 0:
                puntos = 1

        total_score += puntos
        detalle[dim_name] = {
            "puntos":            puntos,
            "max":               max_pts,
            "campos_detectados": detectados,
        }

    # Asegurar rango 0-100
    total_score = max(0, min(100, total_score))

    return {
        "score":     total_score,
        "schema_id": schema_id,
        "detalle":   detalle,
    }


def score_label(score: int) -> str:
    """
    Retorna una etiqueta descriptiva para el score.

    Args:
        score: Valor entre 0 y 100

    Returns:
        str con etiqueta (Critico / Limitado / Funcional / Bueno / Completo)
    """
    if score >= 85:
        return "Completo"
    if score >= 65:
        return "Bueno"
    if score >= 40:
        return "Funcional"
    if score >= 15:
        return "Limitado"
    return "Critico"
