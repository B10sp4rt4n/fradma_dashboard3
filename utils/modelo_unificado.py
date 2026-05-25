"""
modelo_unificado.py
Modelo de datos relacional unificado para CIMA: ventas → facturas → cxc.

REGLAS ESTRUCTURALES OBLIGATORIAS (no negociables):
────────────────────────────────────────────────────
  1. Un CxC siempre tiene una factura válida (id_factura → facturas.id_factura).
  2. Una factura siempre tiene una venta válida (id_venta → ventas.id_venta).
  3. El campo `estatus` de CxC es DERIVADO (calculado), nunca editable ni cargable
     manualmente desde Excel o cualquier otra fuente externa.
  4. No existen tablas físicas separadas cxc_vigentes / cxc_vencidas.
     Son VISTAS derivadas del DataFrame unificado `cxc`.

MODELO FÍSICO:
──────────────
  ventas:    id_venta (PK) | cliente_id | vendedor_id | fecha_venta | importe_total
  facturas:  id_factura (PK) | id_venta (FK) | folio | fecha_emision | importe_facturado
  cxc:       id_cxc (PK) | id_factura (FK) | fecha_vencimiento | saldo_actual
             estatus → DERIVADO (Pagada / Vigente / Vencida)

LÓGICA CANÓNICA DE ESTATUS:
────────────────────────────
  if saldo_actual == 0          → "Pagada"
  elif hoy <= fecha_vencimiento → "Vigente"
  else                          → "Vencida"

VISTAS DERIVADAS (Python/Pandas):
───────────────────────────────────
  vista_cxc_vigentes(df) → df[estatus == 'Vigente']
  vista_cxc_vencidas(df) → df[estatus == 'Vencida']

USO:
────
  from utils.modelo_unificado import (
      calcular_estatus_cxc,
      aplicar_estatus_a_dataframe,
      vista_cxc_vigentes,
      vista_cxc_vencidas,
      validar_integridad_referencial,
      normalizar_cxc_desde_excel,
      calcular_aging_real,
  )
"""

from __future__ import annotations

import pandas as pd
import numpy as np
from datetime import date, datetime
from typing import Dict, List, Optional, Tuple

from utils.logger import configurar_logger

logger = configurar_logger("modelo_unificado", nivel="INFO")

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTES DEL MODELO
# ─────────────────────────────────────────────────────────────────────────────

ESTATUS_PAGADA  = "Pagada"
ESTATUS_VIGENTE = "Vigente"
ESTATUS_VENCIDA = "Vencida"
VALORES_ESTATUS_VALIDOS = frozenset({ESTATUS_PAGADA, ESTATUS_VIGENTE, ESTATUS_VENCIDA})

# Nombres canónicos de columnas en cada tabla
CAMPOS_VENTAS = {
    "pk":           "id_venta",
    "cliente":      "cliente_id",
    "vendedor":     "vendedor_id",
    "fecha":        "fecha_venta",
    "importe":      "importe_total",
}

CAMPOS_FACTURAS = {
    "pk":           "id_factura",
    "fk_venta":     "id_venta",
    "folio":        "folio",
    "fecha":        "fecha_emision",
    "importe":      "importe_facturado",
}

CAMPOS_CXC = {
    "pk":               "id_cxc",
    "fk_factura":       "id_factura",
    "vencimiento":      "fecha_vencimiento",
    "saldo":            "saldo_actual",
    "estatus_derivado": "estatus",   # Solo lectura — siempre calculado
}

# Columnas que NO deben importarse desde Excel (estatus manual)
COLUMNAS_ESTATUS_PROHIBIDAS = frozenset({
    "estatus", "status", "estado", "pagado", "pagada",
    "condicion", "situacion", "flag_pagado",
})


# ─────────────────────────────────────────────────────────────────────────────
# LÓGICA CANÓNICA DE ESTATUS (Sección 2)
# ─────────────────────────────────────────────────────────────────────────────

def calcular_estatus_cxc(
    saldo_actual: float,
    fecha_vencimiento,
    hoy: Optional[date] = None,
) -> str:
    """
    Calcula el estatus de una CxC según la lógica canónica obligatoria.

    Args:
        saldo_actual:       Saldo pendiente de cobro.
        fecha_vencimiento:  Fecha límite de pago (date, Timestamp o str).
        hoy:                Fecha de referencia. Si None usa la fecha actual.

    Returns:
        "Pagada" | "Vigente" | "Vencida"
    """
    if hoy is None:
        hoy = date.today()

    # Normalizar hoy a date
    if isinstance(hoy, (datetime, pd.Timestamp)):
        hoy = hoy.date()

    # Normalizar saldo
    try:
        saldo = float(saldo_actual) if pd.notna(saldo_actual) else None
    except (TypeError, ValueError):
        saldo = None

    if saldo is None:
        return ESTATUS_VENCIDA  # Sin información de saldo → conservador

    if saldo == 0:
        return ESTATUS_PAGADA

    # Normalizar fecha_vencimiento
    try:
        fv = pd.Timestamp(fecha_vencimiento)
        if pd.isna(fv):
            return ESTATUS_VENCIDA  # Sin fecha → conservador
        fv_date = fv.date()
    except (TypeError, ValueError):
        return ESTATUS_VENCIDA

    if hoy <= fv_date:
        return ESTATUS_VIGENTE
    return ESTATUS_VENCIDA


def aplicar_estatus_a_dataframe(
    df: pd.DataFrame,
    col_saldo: str = "saldo_actual",
    col_vencimiento: str = "fecha_vencimiento",
    col_estatus_out: str = "estatus",
    fecha_corte=None,
) -> pd.DataFrame:
    """
    Aplica `calcular_estatus_cxc` vectorizado a todo un DataFrame de CxC.

    Sobreescribe o crea la columna `col_estatus_out`.
    Nunca lee el estatus de una columna ya existente.

    Args:
        df:               DataFrame de CxC.
        col_saldo:        Columna de saldo actual.
        col_vencimiento:  Columna de fecha de vencimiento.
        col_estatus_out:  Nombre de la columna de salida.
        fecha_corte:      Fecha de referencia (None = hoy).

    Returns:
        DataFrame con `col_estatus_out` calculado.
    """
    df = df.copy()
    hoy = pd.Timestamp(fecha_corte).date() if fecha_corte else date.today()

    if col_saldo not in df.columns:
        logger.warning("Columna saldo '%s' no encontrada. Estatus = Vencida.", col_saldo)
        df[col_estatus_out] = ESTATUS_VENCIDA
        return df

    if col_vencimiento not in df.columns:
        logger.warning(
            "Columna vencimiento '%s' no encontrada. Estatus = Vencida.", col_vencimiento
        )
        df[col_estatus_out] = ESTATUS_VENCIDA
        return df

    saldos = pd.to_numeric(df[col_saldo], errors="coerce")
    fechas = pd.to_datetime(df[col_vencimiento], errors="coerce")

    condicion_pagada  = saldos == 0
    condicion_vigente = (~condicion_pagada) & (fechas.dt.date >= hoy) & fechas.notna()
    condicion_vencida = (~condicion_pagada) & (
        (fechas.dt.date < hoy) | fechas.isna()
    )

    df[col_estatus_out] = np.select(
        [condicion_pagada, condicion_vigente, condicion_vencida],
        [ESTATUS_PAGADA,   ESTATUS_VIGENTE,   ESTATUS_VENCIDA],
        default=ESTATUS_VENCIDA,
    )

    logger.debug(
        "Estatus aplicado: Pagadas=%d Vigentes=%d Vencidas=%d",
        int(condicion_pagada.sum()),
        int(condicion_vigente.sum()),
        int(condicion_vencida.sum()),
    )
    return df


# ─────────────────────────────────────────────────────────────────────────────
# VISTAS DERIVADAS (Sección 3)
# ─────────────────────────────────────────────────────────────────────────────

def vista_cxc_vigentes(df_cxc: pd.DataFrame, fecha_corte=None) -> pd.DataFrame:
    """
    Vista derivada de CxC con estatus 'Vigente'.
    Equivale a: SELECT * FROM cxc WHERE estatus = 'Vigente'

    El estatus se recalcula antes de filtrar para garantizar consistencia.
    """
    df = aplicar_estatus_a_dataframe(df_cxc, fecha_corte=fecha_corte)
    return df[df["estatus"] == ESTATUS_VIGENTE].copy()


def vista_cxc_vencidas(df_cxc: pd.DataFrame, fecha_corte=None) -> pd.DataFrame:
    """
    Vista derivada de CxC con estatus 'Vencida'.
    Equivale a: SELECT * FROM cxc WHERE estatus = 'Vencida'

    El estatus se recalcula antes de filtrar para garantizar consistencia.
    """
    df = aplicar_estatus_a_dataframe(df_cxc, fecha_corte=fecha_corte)
    return df[df["estatus"] == ESTATUS_VENCIDA].copy()


def vista_cxc_pagadas(df_cxc: pd.DataFrame, fecha_corte=None) -> pd.DataFrame:
    """
    Vista derivada de CxC con estatus 'Pagada'.
    Equivale a: SELECT * FROM cxc WHERE estatus = 'Pagada'
    """
    df = aplicar_estatus_a_dataframe(df_cxc, fecha_corte=fecha_corte)
    return df[df["estatus"] == ESTATUS_PAGADA].copy()


# ─────────────────────────────────────────────────────────────────────────────
# VALIDACIONES ESTRUCTURALES OBLIGATORIAS (Sección 4)
# ─────────────────────────────────────────────────────────────────────────────

def validar_integridad_referencial(
    df_ventas: Optional[pd.DataFrame],
    df_facturas: Optional[pd.DataFrame],
    df_cxc: Optional[pd.DataFrame],
    tolerancia_importe: float = 0.01,
) -> Dict:
    """
    Ejecuta las validaciones estructurales obligatorias del modelo.

    Validaciones:
      E1  Factura sin venta asociada → error estructural
      E2  CxC sin factura asociada   → error estructural
      A1  importe_total (venta) ≠ suma importe_facturado → alerta
      A2  importe_facturado ≠ saldo_inicial CxC         → alerta

    Args:
        df_ventas:   DataFrame con al menos 'id_venta', 'importe_total'.
        df_facturas: DataFrame con al menos 'id_factura', 'id_venta', 'importe_facturado'.
        df_cxc:      DataFrame con al menos 'id_cxc', 'id_factura', 'saldo_actual'.
        tolerancia_importe: Diferencia permitida en importes (default 0.01).

    Returns:
        dict con claves:
          'errores'      List[str]  — errores estructurales (integridad rota)
          'alertas'      List[str]  — alertas de importe
          'valido'       bool       — True si no hay errores estructurales
          'resumen'      dict       — conteos de inconsistencias
    """
    errores: List[str] = []
    alertas: List[str] = []
    resumen: Dict = {}

    # ── Preparar conjuntos de IDs ──────────────────────────────────────────
    ids_ventas   = set(df_ventas["id_venta"].dropna())   if df_ventas   is not None and not df_ventas.empty   else set()
    ids_facturas = set(df_facturas["id_factura"].dropna()) if df_facturas is not None and not df_facturas.empty else set()
    ids_cxc_fk   = set(df_cxc["id_factura"].dropna())   if df_cxc      is not None and not df_cxc.empty      else set()

    # ── E1: Factura sin venta válida ───────────────────────────────────────
    if df_facturas is not None and not df_facturas.empty and "id_venta" in df_facturas.columns:
        fk_ventas_en_facturas = set(df_facturas["id_venta"].dropna())
        huerfanas = fk_ventas_en_facturas - ids_ventas
        resumen["facturas_sin_venta"] = len(huerfanas)
        if huerfanas:
            errores.append(
                f"[E1] {len(huerfanas)} factura(s) referencian ventas inexistentes: "
                f"{sorted(huerfanas)[:10]}"
            )

    # ── E2: CxC sin factura válida ─────────────────────────────────────────
    if df_cxc is not None and not df_cxc.empty and "id_factura" in df_cxc.columns:
        huerfanas_cxc = ids_cxc_fk - ids_facturas
        resumen["cxc_sin_factura"] = len(huerfanas_cxc)
        if huerfanas_cxc:
            errores.append(
                f"[E2] {len(huerfanas_cxc)} CxC referencian facturas inexistentes: "
                f"{sorted(huerfanas_cxc)[:10]}"
            )

    # ── A1: Importe venta ≠ suma de facturas ──────────────────────────────
    if (
        df_ventas is not None and not df_ventas.empty
        and df_facturas is not None and not df_facturas.empty
        and "id_venta" in df_facturas.columns
        and "importe_facturado" in df_facturas.columns
        and "importe_total" in df_ventas.columns
    ):
        suma_facturas = (
            df_facturas.groupby("id_venta")["importe_facturado"]
            .sum()
            .reset_index(name="suma_facturado")
        )
        chk = df_ventas[["id_venta", "importe_total"]].merge(suma_facturas, on="id_venta", how="left")
        chk["suma_facturado"] = chk["suma_facturado"].fillna(0)
        chk["diferencia"] = (chk["importe_total"] - chk["suma_facturado"]).abs()
        inconsistentes = chk[chk["diferencia"] > tolerancia_importe]
        resumen["ventas_con_importe_diferente_facturas"] = len(inconsistentes)
        if not inconsistentes.empty:
            alertas.append(
                f"[A1] {len(inconsistentes)} venta(s) con importe ≠ suma de facturas. "
                f"Diferencia máx: {inconsistentes['diferencia'].max():,.2f}"
            )

    # ── A2: Importe factura ≠ saldo inicial CxC ───────────────────────────
    if (
        df_facturas is not None and not df_facturas.empty
        and df_cxc is not None and not df_cxc.empty
        and "id_factura" in df_cxc.columns
        and "saldo_actual" in df_cxc.columns
        and "importe_facturado" in df_facturas.columns
    ):
        suma_cxc = (
            df_cxc.groupby("id_factura")["saldo_actual"]
            .sum()
            .reset_index(name="saldo_total_cxc")
        )
        chk2 = df_facturas[["id_factura", "importe_facturado"]].merge(
            suma_cxc, on="id_factura", how="left"
        )
        chk2["saldo_total_cxc"] = chk2["saldo_total_cxc"].fillna(0)
        chk2["diferencia"] = (chk2["importe_facturado"] - chk2["saldo_total_cxc"]).abs()
        # Solo alertar en facturas que no están totalmente cobradas
        inconsistentes2 = chk2[chk2["diferencia"] > tolerancia_importe]
        resumen["facturas_con_saldo_diferente_cxc"] = len(inconsistentes2)
        if not inconsistentes2.empty:
            alertas.append(
                f"[A2] {len(inconsistentes2)} factura(s) con importe_facturado ≠ saldo CxC. "
                f"Diferencia máx: {inconsistentes2['diferencia'].max():,.2f}"
            )

    # ── Detectar ventas sin factura (informativo) ──────────────────────────
    if ids_ventas and ids_facturas:
        fk_ventas_facturadas = set()
        if df_facturas is not None and "id_venta" in df_facturas.columns:
            fk_ventas_facturadas = set(df_facturas["id_venta"].dropna())
        ventas_sin_factura = ids_ventas - fk_ventas_facturadas
        resumen["ventas_sin_factura"] = len(ventas_sin_factura)
        if ventas_sin_factura:
            alertas.append(
                f"[INFO] {len(ventas_sin_factura)} venta(s) sin factura asociada "
                "(ventas no facturadas)."
            )

    # ── Detectar facturas sin CxC (informativo) ───────────────────────────
    if ids_facturas:
        facturas_en_cxc = ids_cxc_fk & ids_facturas
        facturas_sin_cxc = ids_facturas - facturas_en_cxc
        resumen["facturas_sin_cxc"] = len(facturas_sin_cxc)
        if facturas_sin_cxc:
            alertas.append(
                f"[INFO] {len(facturas_sin_cxc)} factura(s) sin CxC asociada "
                "(facturas no cobradas / sin registro de cobro)."
            )

    valido = len(errores) == 0
    return {
        "valido":   valido,
        "errores":  errores,
        "alertas":  alertas,
        "resumen":  resumen,
    }


# ─────────────────────────────────────────────────────────────────────────────
# ADAPTADOR DE INGESTA DESDE EXCEL (Sección 5)
# ─────────────────────────────────────────────────────────────────────────────

# Alias de columnas que pueden llegar en Excel y deben mapearse a los campos canónicos
_ALIAS_VENTAS: Dict[str, List[str]] = {
    "id_venta":       ["id_venta", "venta_id", "folio_venta", "orden"],
    "cliente_id":     ["cliente_id", "cliente", "razon_social", "deudor", "nombre_cliente"],
    "vendedor_id":    ["vendedor_id", "vendedor", "agente", "ejecutivo", "rep"],
    "fecha_venta":    ["fecha_venta", "fecha", "fecha_documento", "fecha_registro"],
    "importe_total":  ["importe_total", "importe", "monto", "total", "valor_mxn", "ventas_usd"],
    # OBLIGATORIOS: toda línea de venta debe referenciar una factura
    "id_factura":     ["id_factura", "factura_id", "uuid_factura"],
    "folio_factura":  ["folio_factura", "folio", "serie_folio", "numero_factura", "folio_fact"],
}

_ALIAS_FACTURAS: Dict[str, List[str]] = {
    "id_factura":        ["id_factura", "factura_id", "uuid", "folio"],
    "id_venta":          ["id_venta", "venta_id"],
    "folio":             ["folio", "serie_folio", "numero_factura"],
    "fecha_emision":     ["fecha_emision", "fecha_factura", "fecha"],
    "importe_facturado": ["importe_facturado", "importe", "total", "monto_facturado"],
}

_ALIAS_CXC: Dict[str, List[str]] = {
    "id_cxc":             ["id_cxc", "cxc_id", "id"],
    "id_factura":         ["id_factura", "factura_id", "folio", "uuid"],
    "fecha_vencimiento":  ["fecha_vencimiento", "vencimiento", "fecha_venc", "due_date",
                           "fecha_limite_pago"],
    "saldo_actual":       ["saldo_actual", "saldo_adeudado", "saldo", "adeudo",
                           "saldo_adeudo", "balance", "importe_pendiente"],
}


def _mapear_columnas(df: pd.DataFrame, alias_map: Dict[str, List[str]]) -> pd.DataFrame:
    """Renombra columnas del DataFrame según el mapa de alias."""
    rename = {}
    for campo_canonico, aliases in alias_map.items():
        if campo_canonico in df.columns:
            continue  # Ya existe con el nombre correcto
        for alias in aliases:
            if alias in df.columns:
                rename[alias] = campo_canonico
                break
    if rename:
        df = df.rename(columns=rename)
    return df


def _forzar_claves_unicas(df: pd.DataFrame, col_pk: str, nombre_tabla: str) -> Tuple[pd.DataFrame, List[str]]:
    """
    Fuerza unicidad en la columna PK. Elimina duplicados y registra cuántos.
    """
    alertas: List[str] = []
    if col_pk not in df.columns:
        return df, alertas
    duplicados = df.duplicated(subset=[col_pk], keep="first").sum()
    if duplicados > 0:
        alertas.append(
            f"[EXCEL] {duplicados} fila(s) duplicadas en {nombre_tabla}.{col_pk} eliminadas."
        )
        df = df.drop_duplicates(subset=[col_pk], keep="first").reset_index(drop=True)
    return df, alertas


def _eliminar_estatus_manual(df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
    """
    Elimina cualquier columna de estatus manual que provenga del Excel.
    El estatus se calculará siempre de forma derivada.
    """
    alertas: List[str] = []
    columnas_eliminadas = [
        col for col in df.columns if col.lower() in COLUMNAS_ESTATUS_PROHIBIDAS
    ]
    if columnas_eliminadas:
        df = df.drop(columns=columnas_eliminadas)
        alertas.append(
            f"[EXCEL] Columna(s) de estatus manual ignoradas: {columnas_eliminadas}. "
            "El estatus se calcula automáticamente."
        )
    return df, alertas


def normalizar_ventas_desde_excel(
    df_raw: pd.DataFrame,
    ids_facturas_validos: Optional[set] = None,
) -> Tuple[pd.DataFrame, List[str], List[str]]:
    """
    Normaliza un DataFrame de ventas proveniente de Excel al modelo canónico.

    Campos OBLIGATORIOS en cada línea de venta:
      - id_factura    → no puede ser nulo/vacío; debe existir en ids_facturas_validos
      - folio_factura → no puede ser nulo/vacío

    Si alguna fila viola estas reglas se genera un error estructural que bloquea
    la carga.  El llamador debe detener el proceso si `errores` no está vacío.

    Args:
        df_raw:               DataFrame crudo de ventas.
        ids_facturas_validos: Conjunto de id_factura válidos para validar FK.
                              Si se omite se valida presencia pero no existencia.

    Returns:
        (df_normalizado, lista_alertas, lista_errores)
        lista_errores no vacía → bloquear carga.
    """
    alertas: List[str] = []
    errores: List[str] = []
    df = df_raw.copy()

    # Homologar nombres de columnas
    df = _mapear_columnas(df, _ALIAS_VENTAS)

    # ── Validar id_factura (OBLIGATORIO) ───────────────────────────────────
    if "id_factura" not in df.columns:
        errores.append(
            "[E-VENTAS-1] La columna 'id_factura' es obligatoria en la plantilla de ventas "
            "y no se encontró en el archivo. "
            "Cada línea de venta debe referenciar una factura válida."
        )
    else:
        # Detectar nulos/vacíos
        mascara_nulos = df["id_factura"].isna() | (
            df["id_factura"].astype(str).str.strip() == ""
        )
        n_nulos = int(mascara_nulos.sum())
        if n_nulos > 0:
            filas = df.index[mascara_nulos].tolist()[:10]
            errores.append(
                f"[E-VENTAS-2] {n_nulos} fila(s) de ventas sin id_factura "
                f"(filas: {filas}{'...' if n_nulos > 10 else ''}). "
                "No se permite cargar ventas sin factura asociada."
            )

        # Validar contra conjunto de facturas conocidas
        if ids_facturas_validos is not None and not mascara_nulos.all():
            ids_ventas_fk = set(
                df.loc[~mascara_nulos, "id_factura"].astype(str).str.strip()
            )
            inexistentes = ids_ventas_fk - {str(x) for x in ids_facturas_validos}
            if inexistentes:
                errores.append(
                    f"[E-VENTAS-3] {len(inexistentes)} id_factura en ventas no existe "
                    f"en la tabla de facturas: {sorted(inexistentes)[:10]}. "
                    "Carga bloqueada: corrige o recarga el archivo."
                )

        # Detectar duplicados inconsistentes de id_factura en ventas
        if "id_venta" in df.columns:
            dup_fk = df.dropna(subset=["id_factura"]).groupby("id_factura")["id_venta"].nunique()
            multi = dup_fk[dup_fk > 1]
            if not multi.empty:
                alertas.append(
                    f"[A-VENTAS-1] {len(multi)} id_factura está asociado a más de una "
                    f"id_venta: {multi.index.tolist()[:5]}. Revisar duplicados."
                )

    # ── Validar folio_factura (OBLIGATORIO) ───────────────────────────────
    if "folio_factura" not in df.columns:
        errores.append(
            "[E-VENTAS-4] La columna 'folio_factura' es obligatoria en la plantilla de ventas "
            "y no se encontró en el archivo."
        )
    else:
        mascara_folio = df["folio_factura"].isna() | (
            df["folio_factura"].astype(str).str.strip() == ""
        )
        n_folio = int(mascara_folio.sum())
        if n_folio > 0:
            filas_f = df.index[mascara_folio].tolist()[:10]
            errores.append(
                f"[E-VENTAS-5] {n_folio} fila(s) de ventas sin folio_factura "
                f"(filas: {filas_f}{'...' if n_folio > 10 else ''}). "
                "No se permite cargar ventas sin folio de factura."
            )

    # ── Si hay errores estructurales, no continuar procesando ─────────────
    if errores:
        return df, alertas, errores

    # Forzar unicidad en PK
    df, alts = _forzar_claves_unicas(df, "id_venta", "ventas")
    alertas.extend(alts)

    # Generar id_venta auto si no existe
    if "id_venta" not in df.columns:
        df["id_venta"] = [f"V{i+1:05d}" for i in range(len(df))]
        alertas.append("[EXCEL] id_venta generado automáticamente (no existía en el archivo).")

    # Normalizar fechas
    if "fecha_venta" in df.columns:
        df["fecha_venta"] = pd.to_datetime(df["fecha_venta"], errors="coerce")

    # Normalizar importes
    if "importe_total" in df.columns:
        df["importe_total"] = pd.to_numeric(df["importe_total"], errors="coerce").fillna(0)

    return df, alertas, errores


def normalizar_facturas_desde_excel(
    df_raw: pd.DataFrame,
    ids_ventas_validos: Optional[set] = None,
) -> Tuple[pd.DataFrame, List[str], List[str]]:
    """
    Normaliza un DataFrame de facturas proveniente de Excel al modelo canónico.

    Args:
        df_raw:              DataFrame crudo de facturas.
        ids_ventas_validos:  Conjunto de id_venta válidos para validar FK.

    Returns:
        (df_normalizado, lista_alertas, lista_errores)
    """
    alertas: List[str] = []
    errores: List[str] = []
    df = df_raw.copy()

    df = _mapear_columnas(df, _ALIAS_FACTURAS)
    df, alts = _forzar_claves_unicas(df, "id_factura", "facturas")
    alertas.extend(alts)

    if "id_factura" not in df.columns:
        df["id_factura"] = [f"F{i+1:05d}" for i in range(len(df))]
        alertas.append("[EXCEL] id_factura generado automáticamente.")

    if "fecha_emision" in df.columns:
        df["fecha_emision"] = pd.to_datetime(df["fecha_emision"], errors="coerce")

    if "importe_facturado" in df.columns:
        df["importe_facturado"] = pd.to_numeric(df["importe_facturado"], errors="coerce").fillna(0)

    # Validar FK hacia ventas
    if ids_ventas_validos is not None and "id_venta" in df.columns:
        fk_invalidas = set(df["id_venta"].dropna()) - ids_ventas_validos
        if fk_invalidas:
            errores.append(
                f"[E1] {len(fk_invalidas)} factura(s) referencian id_venta inexistente: "
                f"{sorted(fk_invalidas)[:10]}"
            )

    return df, alertas, errores


def normalizar_cxc_desde_excel(
    df_raw: pd.DataFrame,
    ids_facturas_validos: Optional[set] = None,
    fecha_corte=None,
) -> Tuple[pd.DataFrame, List[str], List[str]]:
    """
    Normaliza un DataFrame de CxC proveniente de Excel al modelo canónico.

    Reglas obligatorias:
      - Elimina cualquier columna de estatus manual.
      - Valida FK hacia facturas si se proporciona el conjunto.
      - Calcula el estatus derivado tras normalización.
      - Fuerza claves únicas en id_cxc.

    Args:
        df_raw:                DataFrame crudo de CxC.
        ids_facturas_validos:  Conjunto de id_factura válidos para validar FK.
        fecha_corte:           Fecha de referencia para cálculo de estatus.

    Returns:
        (df_normalizado, lista_alertas, lista_errores)
    """
    alertas: List[str] = []
    errores: List[str] = []
    df = df_raw.copy()

    # Eliminar estatus manual ANTES de cualquier mapeo
    df, alts_estatus = _eliminar_estatus_manual(df)
    alertas.extend(alts_estatus)

    df = _mapear_columnas(df, _ALIAS_CXC)
    df, alts = _forzar_claves_unicas(df, "id_cxc", "cxc")
    alertas.extend(alts)

    if "id_cxc" not in df.columns:
        df["id_cxc"] = [f"CXC{i+1:06d}" for i in range(len(df))]
        alertas.append("[EXCEL] id_cxc generado automáticamente.")

    if "fecha_vencimiento" in df.columns:
        df["fecha_vencimiento"] = pd.to_datetime(df["fecha_vencimiento"], errors="coerce")

    if "saldo_actual" in df.columns:
        df["saldo_actual"] = pd.to_numeric(df["saldo_actual"], errors="coerce").fillna(0)

    # Validar FK hacia facturas
    if ids_facturas_validos is not None and "id_factura" in df.columns:
        fk_invalidas = set(df["id_factura"].dropna()) - ids_facturas_validos
        if fk_invalidas:
            errores.append(
                f"[E2] {len(fk_invalidas)} CxC referencian id_factura inexistente: "
                f"{sorted(fk_invalidas)[:10]}"
            )
            # Marcar inconsistencias en el DataFrame
            df["_inconsistencia_fk"] = df["id_factura"].isin(fk_invalidas)

    # Calcular estatus derivado (nunca manual)
    if "saldo_actual" in df.columns and "fecha_vencimiento" in df.columns:
        df = aplicar_estatus_a_dataframe(df, fecha_corte=fecha_corte)
    else:
        missing = [c for c in ("saldo_actual", "fecha_vencimiento") if c not in df.columns]
        alertas.append(
            f"[EXCEL] No se puede calcular estatus derivado: faltan columnas {missing}."
        )

    return df, alertas, errores


# ─────────────────────────────────────────────────────────────────────────────
# AGING REAL (Sección 6)
# ─────────────────────────────────────────────────────────────────────────────

def calcular_aging_real(
    df_cxc: pd.DataFrame,
    df_ventas: Optional[pd.DataFrame] = None,
    fecha_corte=None,
    col_vendedor_ventas: str = "vendedor_id",
) -> pd.DataFrame:
    """
    Calcula el aging real de CxC con métricas por vencimiento.

    El DataFrame resultante incluye:
      - estatus     (derivado, nunca manual)
      - dias_vencido (calculado desde fecha_vencimiento)
      - bucket       (Por vencer / 1-30 / 31-60 / 61-90 / 91-180 / >180)
      - vendedor_id  (si se cruza con df_ventas)

    Args:
        df_cxc:              DataFrame normalizado de CxC.
        df_ventas:           DataFrame de ventas para cruzar vendedor (opcional).
        fecha_corte:         Fecha de referencia (None = hoy).
        col_vendedor_ventas: Columna de vendedor en df_ventas.

    Returns:
        DataFrame enriquecido con columnas de aging.
    """
    df = df_cxc.copy()
    hoy_ts = pd.Timestamp(fecha_corte) if fecha_corte else pd.Timestamp.today().normalize()

    # Calcular estatus derivado
    df = aplicar_estatus_a_dataframe(df, fecha_corte=fecha_corte)

    # Calcular días vencido
    if "fecha_vencimiento" in df.columns:
        fechas = pd.to_datetime(df["fecha_vencimiento"], errors="coerce")
        df["dias_vencido"] = (hoy_ts - fechas).dt.days
        # Negativo = aún vigente (días restantes)
    else:
        df["dias_vencido"] = np.nan

    # Clasificar en buckets de aging
    def _bucket(row):
        dias = row.get("dias_vencido")
        estatus = row.get("estatus")
        if estatus == ESTATUS_PAGADA:
            return "Pagada"
        if pd.isna(dias):
            return "Sin fecha"
        if dias <= 0:
            return "Por vencer"
        if dias <= 30:
            return "1-30 días"
        if dias <= 60:
            return "31-60 días"
        if dias <= 90:
            return "61-90 días"
        if dias <= 180:
            return "91-180 días"
        return ">180 días"

    df["bucket"] = df.apply(_bucket, axis=1)

    # Cruzar vendedor desde ventas si hay datos relacionales disponibles
    if (
        df_ventas is not None
        and not df_ventas.empty
        and "id_factura" in df.columns
        and "id_venta" in df.columns
    ):
        cols_ventas = ["id_venta", col_vendedor_ventas]
        cols_presentes = [c for c in cols_ventas if c in df_ventas.columns]
        if len(cols_presentes) == 2:
            df = df.merge(
                df_ventas[cols_presentes].drop_duplicates("id_venta"),
                on="id_venta",
                how="left",
            )

    return df


# ─────────────────────────────────────────────────────────────────────────────
# MÉTRICAS DERIVADAS (para dashboards)
# ─────────────────────────────────────────────────────────────────────────────

def calcular_metricas_modelo(
    df_cxc: pd.DataFrame,
    df_ventas: Optional[pd.DataFrame] = None,
    df_facturas: Optional[pd.DataFrame] = None,
    fecha_corte=None,
) -> Dict:
    """
    Calcula el conjunto completo de métricas del modelo unificado.

    Incluye:
      - Total adeudado, vigente, vencido
      - Aging real por bucket
      - Ventas no facturadas
      - Facturas no cobradas
      - Métricas por vendedor (si hay df_ventas con vendedor_id)

    Returns:
        dict con todas las métricas calculadas.
    """
    df_aging = calcular_aging_real(df_cxc, df_ventas=df_ventas, fecha_corte=fecha_corte)

    total_adeudado = df_aging.loc[df_aging["estatus"] != ESTATUS_PAGADA, "saldo_actual"].sum() if "saldo_actual" in df_aging.columns else 0.0
    vigente_monto  = df_aging.loc[df_aging["estatus"] == ESTATUS_VIGENTE, "saldo_actual"].sum() if "saldo_actual" in df_aging.columns else 0.0
    vencida_monto  = df_aging.loc[df_aging["estatus"] == ESTATUS_VENCIDA, "saldo_actual"].sum() if "saldo_actual" in df_aging.columns else 0.0

    pct_vigente = (vigente_monto / total_adeudado * 100) if total_adeudado > 0 else 0.0
    pct_vencida = (vencida_monto / total_adeudado * 100) if total_adeudado > 0 else 0.0

    # Buckets de aging
    buckets = {}
    if "bucket" in df_aging.columns and "saldo_actual" in df_aging.columns:
        buckets = (
            df_aging.groupby("bucket")["saldo_actual"]
            .sum()
            .to_dict()
        )

    # Ventas sin factura
    ventas_sin_factura = 0
    if df_ventas is not None and df_facturas is not None and not df_ventas.empty:
        ids_venta_facturadas = set(df_facturas["id_venta"].dropna()) if "id_venta" in df_facturas.columns else set()
        ventas_sin_factura = len(set(df_ventas["id_venta"].dropna()) - ids_venta_facturadas)

    # Facturas sin cobro (CxC)
    facturas_sin_cobro = 0
    if df_facturas is not None and not df_facturas.empty:
        ids_factura_con_cxc = set(df_aging["id_factura"].dropna()) if "id_factura" in df_aging.columns else set()
        facturas_sin_cobro = len(set(df_facturas["id_factura"].dropna()) - ids_factura_con_cxc)

    # Métricas por vendedor
    metricas_vendedor: Dict = {}
    if "vendedor_id" in df_aging.columns and "saldo_actual" in df_aging.columns:
        grp = df_aging[df_aging["estatus"] != ESTATUS_PAGADA].groupby("vendedor_id")
        metricas_vendedor = (
            grp["saldo_actual"]
            .agg(total_cartera="sum", num_cxc="count")
            .to_dict(orient="index")
        )

    return {
        "total_adeudado":     float(total_adeudado),
        "vigente_monto":      float(vigente_monto),
        "vencida_monto":      float(vencida_monto),
        "pct_vigente":        float(pct_vigente),
        "pct_vencida":        float(pct_vencida),
        "buckets":            buckets,
        "ventas_sin_factura": ventas_sin_factura,
        "facturas_sin_cobro": facturas_sin_cobro,
        "metricas_vendedor":  metricas_vendedor,
        "df_aging":           df_aging,
    }
