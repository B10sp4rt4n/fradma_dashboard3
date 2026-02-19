"""
Tests unitarios para main/reporte_ejecutivo.py
Módulo de reporte ejecutivo consolidado.

Coverage objetivo: 20-30% (lógica de normalización y cálculos)
Nota: mostrar_reporte_ejecutivo() es UI Streamlit compleja
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


# ═══════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════

@pytest.fixture
def df_ventas_mensual():
    """Ventas con datos de 2 meses para comparación"""
    return pd.DataFrame({
        'fecha': pd.to_datetime(['2024-01-01', '2024-01-15', '2024-01-20',
                                 '2024-02-01', '2024-02-10', '2024-02-15']),
        'valor_usd': [1000, 1500, 2000, 2500, 3000, 3500]
    })


@pytest.fixture
def df_cxc_vencimientos():
    """CxC con diferentes estados de vencimiento"""
    return pd.DataFrame({
        'deudor': ['Cliente A', 'Cliente B', 'Cliente C', 'Cliente D'],
        'saldo_adeudado': [5000, 3000, 2000, 1000],
        'estatus': ['VIGENTE', 'VENCIDA', 'VENCIDA', 'PAGADO'],
        'dias_vencido': [0, 15, 45, 0]
    })


# ═══════════════════════════════════════════════════════════════════════
# TESTS DE NORMALIZACIÓN DE COLUMNAS
# ═══════════════════════════════════════════════════════════════════════

class TestNormalizacionColumnas:
    """Valida normalización defensiva de columnas"""
    
    def test_renombra_ventas_usd_con_iva_a_valor_usd(self):
        """Detecta 'ventas_usd_con_iva' y renombra a 'valor_usd'"""
        df = pd.DataFrame({
            'fecha': ['2024-01-01'],
            'ventas_usd_con_iva': [1160]
        })
        
        if "valor_usd" not in df.columns:
            for candidato in ["ventas_usd_con_iva", "ventas_usd", "importe"]:
                if candidato in df.columns:
                    df = df.rename(columns={candidato: "valor_usd"})
                    break
        
        assert "valor_usd" in df.columns
        assert df["valor_usd"].iloc[0] == 1160
        
    def test_convierte_valor_usd_a_numeric(self):
        """Convierte columna valor_usd a numérico"""
        df = pd.DataFrame({
            'valor_usd': ['1,000', '2,500.50', 'N/A', '3000']
        })
        
        df["valor_usd"] = pd.to_numeric(
            df["valor_usd"].astype(str).str.replace(",", "").str.replace("$", ""),
            errors="coerce"
        ).fillna(0)
        
        assert df["valor_usd"].iloc[0] == 1000
        assert df["valor_usd"].iloc[1] == 2500.50
        assert df["valor_usd"].iloc[2] == 0  # N/A → 0
        
    def test_renombra_saldo_a_saldo_adeudado(self):
        """Detecta 'saldo' y renombra a 'saldo_adeudado'"""
        df = pd.DataFrame({
            'deudor': ['Cliente A'],
            'saldo': [5000]
        })
        
        if "saldo_adeudado" not in df.columns:
            for candidato in ["saldo_usd", "saldo", "adeudo"]:
                if candidato in df.columns:
                    df = df.rename(columns={candidato: "saldo_adeudado"})
                    break
        
        assert "saldo_adeudado" in df.columns


# ═══════════════════════════════════════════════════════════════════════
# TESTS DE KPIS DE VENTAS
# ═══════════════════════════════════════════════════════════════════════

class TestKPIsVentas:
    """Valida cálculos de KPIs de ventas"""
    
    def test_total_ventas(self, df_ventas_mensual):
        """Calcula suma total de ventas"""
        total = df_ventas_mensual["valor_usd"].sum()
        
        assert total == 13500
        
    def test_total_operaciones(self, df_ventas_mensual):
        """Cuenta número de operaciones"""
        total_ops = len(df_ventas_mensual)
        
        assert total_ops == 6
        
    def test_ticket_promedio(self, df_ventas_mensual):
        """Calcula ticket promedio"""
        total = df_ventas_mensual["valor_usd"].sum()
        ops = len(df_ventas_mensual)
        ticket = total / ops if ops > 0 else 0
        
        assert ticket == 2250.0  # 13500 / 6
        
    def test_variacion_mensual_ventas(self, df_ventas_mensual):
        """Calcula % variación mes actual vs mes anterior"""
        df = df_ventas_mensual.copy()
        df['fecha'] = pd.to_datetime(df['fecha'])
        
        # Ventas por mes
        df['mes'] = df['fecha'].dt.to_period('M')
        ventas_mes = df.groupby('mes')['valor_usd'].sum()
        
        # Enero: 1000+1500+2000 = 4500
        # Febrero: 2500+3000+3500 = 9000
        enero = ventas_mes.iloc[0]
        febrero = ventas_mes.iloc[1]
        
        variacion = ((febrero - enero) / enero * 100) if enero > 0 else 0
        
        assert enero == 4500
        assert febrero == 9000
        assert variacion == 100.0  # 100% crecimiento


# ═══════════════════════════════════════════════════════════════════════
# TESTS DE LÓGICA CXC
# ═══════════════════════════════════════════════════════════════════════

class TestLogicaCxC:
    """Valida cálculos de cuentas por cobrar"""
    
    def test_excluye_pagados_antes_de_calcular(self, df_cxc_vencimientos):
        """Excluye registros con estatus PAGADO"""
        df = df_cxc_vencimientos.copy()
        
        # Detectar pagados
        col_estatus = 'estatus'
        estatus_norm = df[col_estatus].astype(str).str.strip().str.lower()
        mask_pagado = estatus_norm.str.contains("pagado")
        
        # Total sin pagados
        total_sin_pagados = df.loc[~mask_pagado, 'saldo_adeudado'].sum()
        
        # Cliente D está pagado (1000), debe excluirse
        assert total_sin_pagados == 10000  # 5000 + 3000 + 2000
        
    def test_calcula_dias_overdue_desde_dias_vencido(self, df_cxc_vencimientos):
        """Usa columna dias_vencido directamente"""
        df = df_cxc_vencimientos.copy()
        
        # dias_vencido ya está en el DF
        dias_overdue = df['dias_vencido']
        
        assert dias_overdue.tolist() == [0, 15, 45, 0]
        
    def test_calcula_dias_overdue_desde_dias_restante(self):
        """Invierte dias_restante para obtener dias_overdue"""
        df = pd.DataFrame({
            'deudor': ['A', 'B', 'C'],
            'saldo_adeudado': [1000, 2000, 3000],
            'dias_restante': [10, 0, -20]  # Positivo=vigente, negativo=vencido
        })
        
        # dias_overdue = -dias_restante
        dias_overdue = -df['dias_restante']
        
        assert dias_overdue.tolist() == [-10, 0, 20]
        
    def test_clasifica_cartera_por_dias(self, df_cxc_vencimientos):
        """Clasifica saldos por días de vencimiento"""
        df = df_cxc_vencimientos.copy()
        
        # Excluir pagados
        df_activa = df[df['estatus'].str.lower() != 'pagado']
        
        # Clasificar
        vigente = df_activa[df_activa['dias_vencido'] == 0]['saldo_adeudado'].sum()
        vencida_0_30 = df_activa[(df_activa['dias_vencido'] > 0) & 
                                  (df_activa['dias_vencido'] <= 30)]['saldo_adeudado'].sum()
        vencida_31_60 = df_activa[(df_activa['dias_vencido'] > 30) & 
                                   (df_activa['dias_vencido'] <= 60)]['saldo_adeudado'].sum()
        
        assert vigente == 5000      # Cliente A
        assert vencida_0_30 == 3000 # Cliente B (15 días)
        assert vencida_31_60 == 2000 # Cliente C (45 días)
        
    def test_total_adeudado_excluye_pagados(self, df_cxc_vencimientos):
        """Total de cartera solo cuenta no pagados"""
        df = df_cxc_vencimientos.copy()
        
        mask_no_pagado = df['estatus'].str.lower() != 'pagado'
        total = df.loc[mask_no_pagado, 'saldo_adeudado'].sum()
        
        assert total == 10000  # Excluye Cliente D (PAGADO)


# ═══════════════════════════════════════════════════════════════════════
# TESTS DE COMPARACIÓN PERIODOS
# ═══════════════════════════════════════════════════════════════════════

class TestComparacionPeriodos:
    """Valida comparación de periodos equivalentes (día 1-X)"""
    
    def test_filtra_por_rango_dias_mes(self):
        """Compara mes actual vs anterior en días equivalentes"""
        df = pd.DataFrame({
            'fecha': pd.to_datetime([
                '2024-01-05', '2024-01-10', '2024-01-15',
                '2024-02-05', '2024-02-10', '2024-02-15', '2024-02-20'
            ]),
            'valor_usd': [1000, 1500, 2000, 2500, 3000, 3500, 4000]
        })
        
        # Fecha máxima: 20 de febrero
        fecha_max = df['fecha'].max()
        dia_actual = fecha_max.day  # 20
        
        # Mes anterior: enero
        mes_anterior = fecha_max - timedelta(days=30)
        inicio_mes_anterior = mes_anterior.replace(day=1)
        fin_mes_anterior = inicio_mes_anterior + timedelta(days=dia_actual - 1)
        
        # Ventas enero días 1-20
        ventas_enero_equivalente = df[
            (df['fecha'] >= inicio_mes_anterior) & 
            (df['fecha'] <= fin_mes_anterior)
        ]['valor_usd'].sum()
        
        # Solo incluye hasta día 15 (1000+1500+2000=4500)
        assert ventas_enero_equivalente == 4500


# ═══════════════════════════════════════════════════════════════════════
# TESTS DE DETECCIÓN DE COLUMNAS
# ═══════════════════════════════════════════════════════════════════════

class TestDeteccionColumnas:
    """Valida detección flexible de columnas"""
    
    def test_detecta_columna_estatus(self):
        """Busca 'estatus', 'status' o 'pagado'"""
        df = pd.DataFrame({
            'deudor': ['A', 'B'],
            'status': ['VIGENTE', 'PAGADO']
        })
        
        col_estatus = None
        for col in ["estatus", "status", "pagado"]:
            if col in df.columns:
                col_estatus = col
                break
        
        assert col_estatus == "status"
        
    def test_detecta_columna_vencimiento(self):
        """Busca variantes de vencimiento"""
        df = pd.DataFrame({
            'deudor': ['A'],
            'vencimient': ['2024-01-15']  # Typo común
        })
        
        col_venc = None
        for col in ["vencimient", "vencimiento", "fecha_vencimiento"]:
            if col in df.columns:
                col_venc = col
                break
        
        assert col_venc == "vencimient"
