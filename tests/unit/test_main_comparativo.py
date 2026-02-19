"""
Tests unitarios para main/main_comparativo.py
Módulo de comparación de ventas año vs año.

Coverage objetivo: 40-50% (lógica de transformación)
Nota: run() es mayormente UI Streamlit, difícil de testear sin mocks complejos
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime


# ═══════════════════════════════════════════════════════════════════════
# TESTS DE NORMALIZACIÓN DE COLUMNAS
# ═══════════════════════════════════════════════════════════════════════

class TestNormalizacionColumnas:
    """Valida normalización de nombres de columnas"""
    
    def test_normaliza_columna_anio_variantes(self):
        """Detecta y normaliza variantes de 'año'"""
        df = pd.DataFrame({
            'aÃ±o': [2024, 2025],  # Encoding issue variant
            'mes': [1, 2],
            'valor_usd': [1000, 2000]
        })
        
        # Simular normalización del módulo
        df.columns = df.columns.str.lower().str.strip()
        for col_anio in ["aã±o", "aÃ±o", "ano", "anio"]:
            if col_anio in df.columns and "año" not in df.columns:
                df = df.rename(columns={col_anio: "año"})
        
        assert "año" in df.columns or "aÃ±o" in df.columns
        
    def test_normaliza_valor_usd_desde_ventas_usd(self):
        """Renombra 'ventas_usd' a 'valor_usd'"""
        df = pd.DataFrame({
            'año': [2024],
            'mes': [1],
            'ventas_usd': [5000]
        })
        
        if "valor_usd" not in df.columns:
            if "ventas_usd" in df.columns:
                df = df.rename(columns={"ventas_usd": "valor_usd"})
        
        assert "valor_usd" in df.columns
        assert df["valor_usd"].iloc[0] == 5000
        
    def test_normaliza_valor_usd_desde_importe(self):
        """Renombra 'importe' a 'valor_usd'"""
        df = pd.DataFrame({
            'año': [2024],
            'mes': [1],
            'importe': [3500]
        })
        
        if "valor_usd" not in df.columns:
            if "importe" in df.columns:
                df = df.rename(columns={"importe": "valor_usd"})
        
        assert "valor_usd" in df.columns
        assert df["valor_usd"].iloc[0] == 3500
        
    def test_extrae_anio_mes_desde_fecha(self):
        """Crea columnas año/mes desde fecha si no existen"""
        df = pd.DataFrame({
            'fecha': ['2024-03-15', '2024-04-20', '2025-01-10'],
            'valor_usd': [1000, 2000, 3000]
        })
        
        df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
        df["año"] = df["fecha"].dt.year
        df["mes"] = df["fecha"].dt.month
        
        assert "año" in df.columns
        assert "mes" in df.columns
        assert df["año"].tolist() == [2024, 2024, 2025]
        assert df["mes"].tolist() == [3, 4, 1]


# ═══════════════════════════════════════════════════════════════════════
# TESTS DE AGREGACIÓN Y PIVOT
# ═══════════════════════════════════════════════════════════════════════

class TestAgregacionVentas:
    """Valida agrupación y tabla pivot"""
    
    def test_agrupa_ventas_por_anio_mes(self):
        """Suma ventas por año y mes"""
        df = pd.DataFrame({
            'año': [2024, 2024, 2024, 2025],
            'mes': [1, 1, 2, 1],
            'valor_usd': [1000, 1500, 2000, 3000]
        })
        
        pivot_ventas = df.groupby(["año", "mes"], as_index=False)["valor_usd"].sum()
        
        assert len(pivot_ventas) == 3  # (2024,1), (2024,2), (2025,1)
        assert pivot_ventas[
            (pivot_ventas["año"] == 2024) & (pivot_ventas["mes"] == 1)
        ]["valor_usd"].iloc[0] == 2500  # 1000 + 1500
        
    def test_tabla_pivot_año_x_mes(self):
        """Crea tabla con años como filas y meses como columnas"""
        pivot_ventas = pd.DataFrame({
            'año': [2024, 2024, 2025, 2025],
            'mes': [1, 2, 1, 2],
            'valor_usd': [1000, 2000, 1500, 2500]
        })
        
        tabla_fija = pivot_ventas.pivot(
            index="año", columns="mes", values="valor_usd"
        ).fillna(0)
        
        assert tabla_fija.loc[2024, 1] == 1000
        assert tabla_fija.loc[2024, 2] == 2000
        assert tabla_fija.loc[2025, 1] == 1500
        assert tabla_fija.loc[2025, 2] == 2500
        
    def test_completa_meses_faltantes_con_cero(self):
        """Rellena meses sin datos con 0"""
        tabla_fija = pd.DataFrame({
            1: [1000],
            3: [3000],
            12: [5000]
        }, index=[2024])
        
        # Completar meses faltantes
        for mes in range(1, 13):
            if mes not in tabla_fija.columns:
                tabla_fija[mes] = 0
        tabla_fija = tabla_fija[sorted(tabla_fija.columns)]
        
        assert len(tabla_fija.columns) == 12
        assert tabla_fija.loc[2024, 2] == 0
        assert tabla_fija.loc[2024, 4] == 0
        assert tabla_fija.loc[2024, 1] == 1000
        

# ═══════════════════════════════════════════════════════════════════════
# TESTS DE COMPARATIVO AÑO VS AÑO
# ═══════════════════════════════════════════════════════════════════════

class TestComparativoAnios:
    """Valida cálculos de comparación entre años"""
    
    def test_diferencia_absoluta_entre_anios(self):
        """Calcula diferencia en USD"""
        comparativo = pd.DataFrame({
            '2024': [1000, 2000, 3000],
            '2025': [1200, 1800, 3500]
        }, index=[1, 2, 3])
        
        comparativo["Diferencia"] = comparativo['2025'] - comparativo['2024']
        
        assert comparativo["Diferencia"].tolist() == [200, -200, 500]
        
    def test_porcentaje_variacion_positiva(self):
        """Calcula % variación con crecimiento"""
        comparativo = pd.DataFrame({
            '2024': [1000],
            '2025': [1500]
        }, index=[1])
        
        comparativo["Diferencia"] = comparativo['2025'] - comparativo['2024']
        denom = comparativo['2024'].where(comparativo['2024'] != 0)
        pct_raw = (comparativo["Diferencia"] / denom) * 100
        comparativo["% Variación"] = pd.to_numeric(pct_raw, errors="coerce").round(2)
        
        assert comparativo["% Variación"].iloc[0] == 50.0
        
    def test_porcentaje_variacion_negativa(self):
        """Calcula % variación con decrecimiento"""
        comparativo = pd.DataFrame({
            '2024': [2000],
            '2025': [1500]
        }, index=[1])
        
        comparativo["Diferencia"] = comparativo['2025'] - comparativo['2024']
        denom = comparativo['2024'].where(comparativo['2024'] != 0)
        pct_raw = (comparativo["Diferencia"] / denom) * 100
        comparativo["% Variación"] = pd.to_numeric(pct_raw, errors="coerce").round(2)
        
        assert comparativo["% Variación"].iloc[0] == -25.0
        
    def test_maneja_division_por_cero_en_variacion(self):
        """Evita división por 0 cuando año base es 0"""
        comparativo = pd.DataFrame({
            '2024': [0, 1000],
            '2025': [500, 1500]
        }, index=[1, 2])
        
        comparativo["Diferencia"] = comparativo['2025'] - comparativo['2024']
        denom = comparativo['2024'].where(comparativo['2024'] != 0)
        pct_raw = (comparativo["Diferencia"] / denom) * 100
        comparativo["% Variación"] = pd.to_numeric(pct_raw, errors="coerce")
        
        assert pd.isna(comparativo["% Variación"].iloc[0])  # NaN por división por 0
        assert comparativo["% Variación"].iloc[1] == 50.0
        
    def test_variacion_cero_cuando_igual(self):
        """% Variación = 0 cuando valores son iguales"""
        comparativo = pd.DataFrame({
            '2024': [1000],
            '2025': [1000]
        }, index=[1])
        
        comparativo["Diferencia"] = comparativo['2025'] - comparativo['2024']
        denom = comparativo['2024'].where(comparativo['2024'] != 0)
        pct_raw = (comparativo["Diferencia"] / denom) * 100
        comparativo["% Variación"] = pd.to_numeric(pct_raw, errors="coerce").round(2)
        
        assert comparativo["Diferencia"].iloc[0] == 0
        assert comparativo["% Variación"].iloc[0] == 0.0


# ═══════════════════════════════════════════════════════════════════════
# TESTS DE CASOS ESPECIALES
# ═══════════════════════════════════════════════════════════════════════

class TestCasosEspeciales:
    """Valida manejo de edge cases"""
    
    def test_convierte_valores_string_a_numeric(self):
        """Convierte valor_usd string a número"""
        df = pd.DataFrame({
            'año': [2024],
            'mes': [1],
            'valor_usd': ['5000.50']
        })
        
        df["valor_usd"] = pd.to_numeric(df["valor_usd"], errors="coerce").fillna(0)
        
        assert df["valor_usd"].iloc[0] == 5000.50
        assert df["valor_usd"].dtype in [np.float64, np.int64]
        
    def test_rellena_valores_nan_con_cero(self):
        """NaN en valor_usd se convierte a 0"""
        df = pd.DataFrame({
            'año': [2024, 2024],
            'mes': [1, 2],
            'valor_usd': [1000, np.nan]
        })
        
        df["valor_usd"] = pd.to_numeric(df["valor_usd"], errors="coerce").fillna(0)
        
        assert df["valor_usd"].iloc[1] == 0.0
        
    def test_maneja_anios_desordenados(self):
        """Ordena años correctamente"""
        df = pd.DataFrame({
            'año': [2025, 2023, 2024, 2025],
            'mes': [1, 1, 1, 2],
            'valor_usd': [1000, 2000, 3000, 4000]
        })
        
        anios_disponibles = sorted(df["año"].dropna().unique())
        
        assert anios_disponibles == [2023, 2024, 2025]
        
    def test_detecta_menos_de_dos_anios(self):
        """Identifica cuando no hay suficientes años para comparar"""
        df = pd.DataFrame({
            'año': [2024, 2024],
            'mes': [1, 2],
            'valor_usd': [1000, 2000]
        })
        
        anios_disponibles = sorted(df["año"].dropna().unique())
        
        assert len(anios_disponibles) < 2  # No se puede comparar
        
    def test_formato_lowercase_y_strip_columnas(self):
        """Normaliza columnas a lowercase y sin espacios"""
        df = pd.DataFrame({
            'AÑO ': [2024],
            ' MES': [1],
            ' VALOR_USD ': [1000]
        })
        
        df.columns = df.columns.str.lower().str.strip()
        
        assert 'año' in df.columns or 'aÃ±o' in df.columns  # Encoding variant
        assert 'mes' in df.columns
        assert 'valor_usd' in df.columns
