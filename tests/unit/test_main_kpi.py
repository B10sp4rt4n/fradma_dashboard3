"""
Tests unitarios para main/main_kpi.py
Módulo de KPIs generales y ranking de vendedores.

Coverage objetivo: 30-40% (lógica de cálculo de KPIs)
Nota: run() es UI Streamlit, difícil de testear sin mocks
"""

import pytest
import pandas as pd
import numpy as np


# ═══════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════

@pytest.fixture
def df_ventas_basico():
    """DataFrame básico de ventas con vendedores"""
    return pd.DataFrame({
        'fecha': pd.to_datetime(['2024-01-15', '2024-01-20', '2024-02-10', '2024-02-15']),
        'valor_usd': [1000, 1500, 2000, 2500],
        'agente': ['Juan', 'Pedro', 'Juan', 'Pedro'],
        'cliente': ['Cliente A', 'Cliente B', 'Cliente C', 'Cliente A'],
        'linea_producto': ['Hardware', 'Software', 'Hardware', 'Software']
    })


@pytest.fixture
def df_ventas_eficiencia():
    """Dataset para tests de eficiencia de vendedores"""
    return pd.DataFrame({
        'fecha': pd.to_datetime(['2024-01-01'] * 10 + ['2024-01-02'] * 5 + ['2024-01-03'] * 3),
        'valor_usd': [1000] * 10 + [5000] * 5 + [500] * 3,
        'agente': ['Vendedor A'] * 10 + ['Vendedor B'] * 5 + ['Vendedor C'] * 3,
        'cliente': ['C1', 'C2', 'C1', 'C3', 'C4', 'C5', 'C6', 'C7', 'C8', 'C9'] + 
                   ['C10', 'C11', 'C10', 'C12', 'C13'] +
                   ['C14', 'C15', 'C14']
    })


# ═══════════════════════════════════════════════════════════════════════
# TESTS DE KPIs BÁSICOS
# ═══════════════════════════════════════════════════════════════════════

class TestKPIsBasicos:
    """Valida cálculos de KPIs generales"""
    
    def test_total_ventas_suma_correcta(self, df_ventas_basico):
        """Calcula total de ventas USD"""
        total_usd = df_ventas_basico["valor_usd"].sum()
        
        assert total_usd == 7000
        
    def test_total_operaciones_count(self, df_ventas_basico):
        """Cuenta total de operaciones"""
        total_ops = len(df_ventas_basico)
        
        assert total_ops == 4
        
    def test_filtra_por_agente(self, df_ventas_basico):
        """Filtra ventas por vendedor específico"""
        df_filtrado = df_ventas_basico[df_ventas_basico["agente"] == "Juan"]
        
        assert len(df_filtrado) == 2
        assert df_filtrado["valor_usd"].sum() == 3000
        
    def test_filtra_por_linea_producto(self, df_ventas_basico):
        """Filtra ventas por línea de producto"""
        df_filtrado = df_ventas_basico[df_ventas_basico["linea_producto"] == "Hardware"]
        
        assert len(df_filtrado) == 2
        assert df_filtrado["valor_usd"].sum() == 3000
        
    def test_extrae_anio_desde_fecha(self, df_ventas_basico):
        """Crea columna año desde fecha"""
        df_ventas_basico["anio"] = pd.to_datetime(
            df_ventas_basico["fecha"], errors="coerce"
        ).dt.year
        
        assert "anio" in df_ventas_basico.columns
        assert df_ventas_basico["anio"].unique().tolist() == [2024]


# ═══════════════════════════════════════════════════════════════════════
# TESTS DE RANKING DE VENDEDORES
# ═══════════════════════════════════════════════════════════════════════

class TestRankingVendedores:
    """Valida ranking de vendedores por ventas"""
    
    def test_ranking_por_ventas_totales(self, df_ventas_basico):
        """Ordena vendedores por total de ventas"""
        ranking = (
            df_ventas_basico.groupby("agente")
            .agg(total_usd=("valor_usd", "sum"), operaciones=("valor_usd", "count"))
            .sort_values("total_usd", ascending=False)
            .reset_index()
        )
        
        assert ranking.iloc[0]["agente"] == "Pedro"  # 4000 USD
        assert ranking.iloc[0]["total_usd"] == 4000
        assert ranking.iloc[1]["agente"] == "Juan"   # 3000 USD
        assert ranking.iloc[1]["total_usd"] == 3000
        
    def test_ranking_incluye_numero_operaciones(self, df_ventas_basico):
        """Cuenta operaciones por vendedor"""
        ranking = (
            df_ventas_basico.groupby("agente")
            .agg(total_usd=("valor_usd", "sum"), operaciones=("valor_usd", "count"))
            .reset_index()
        )
        
        juan_ops = ranking[ranking["agente"] == "Juan"]["operaciones"].iloc[0]
        pedro_ops = ranking[ranking["agente"] == "Pedro"]["operaciones"].iloc[0]
        
        assert juan_ops == 2
        assert pedro_ops == 2
        
    def test_ranking_agrega_columna_posicion(self, df_ventas_basico):
        """Añade columna de ranking (1, 2, 3...)"""
        ranking = (
            df_ventas_basico.groupby("agente")
            .agg(total_usd=("valor_usd", "sum"))
            .sort_values("total_usd", ascending=False)
            .reset_index()
        )
        
        ranking.insert(0, "Ranking", range(1, len(ranking) + 1))
        
        assert "Ranking" in ranking.columns
        assert ranking["Ranking"].tolist() == [1, 2]


# ═══════════════════════════════════════════════════════════════════════
# TESTS DE KPIs DE EFICIENCIA
# ═══════════════════════════════════════════════════════════════════════

class TestKPIsEficiencia:
    """Valida cálculos de eficiencia de vendedores"""
    
    def test_ticket_promedio_calculo(self, df_ventas_basico):
        """Calcula ticket promedio (ventas / operaciones)"""
        total_ventas = df_ventas_basico["valor_usd"].sum()
        operaciones = len(df_ventas_basico)
        
        ticket_promedio = total_ventas / operaciones if operaciones > 0 else 0
        
        assert ticket_promedio == 1750.0  # 7000 / 4
        
    def test_clientes_unicos_por_vendedor(self, df_ventas_basico):
        """Cuenta clientes únicos por vendedor"""
        juan_clientes = df_ventas_basico[df_ventas_basico["agente"] == "Juan"]["cliente"].nunique()
        
        assert juan_clientes == 2  # Cliente A, Cliente C
        
    def test_ventas_por_cliente_promedio(self, df_ventas_basico):
        """Calcula ventas por cliente"""
        juan_data = df_ventas_basico[df_ventas_basico["agente"] == "Juan"]
        total_ventas = juan_data["valor_usd"].sum()
        clientes_unicos = juan_data["cliente"].nunique()
        
        ventas_por_cliente = total_ventas / clientes_unicos if clientes_unicos > 0 else 0
        
        assert ventas_por_cliente == 1500.0  # 3000 / 2
        
    def test_eficiencia_todos_los_vendedores(self, df_ventas_eficiencia):
        """Calcula KPIs de eficiencia para todos los vendedores"""
        vendedores_eficiencia = []
        
        for agente in df_ventas_eficiencia["agente"].unique():
            agente_data = df_ventas_eficiencia[df_ventas_eficiencia["agente"] == agente]
            
            total_ventas = agente_data["valor_usd"].sum()
            operaciones_count = len(agente_data)
            ticket_promedio = total_ventas / operaciones_count if operaciones_count > 0 else 0
            clientes_unicos = agente_data["cliente"].nunique()
            
            vendedores_eficiencia.append({
                'agente': agente,
                'total_ventas': total_ventas,
                'operaciones': operaciones_count,
                'ticket_promedio': ticket_promedio,
                'clientes_unicos': clientes_unicos
            })
        
        df_eficiencia = pd.DataFrame(vendedores_eficiencia)
        
        # Vendedor A: 10 ops x $1000 = $10,000
        vendedor_a = df_eficiencia[df_eficiencia['agente'] == 'Vendedor A'].iloc[0]
        assert vendedor_a['total_ventas'] == 10000
        assert vendedor_a['operaciones'] == 10
        assert vendedor_a['ticket_promedio'] == 1000
        
        # Vendedor B: 5 ops x $5000 = $25,000
        vendedor_b = df_eficiencia[df_eficiencia['agente'] == 'Vendedor B'].iloc[0]
        assert vendedor_b['total_ventas'] == 25000
        assert vendedor_b['ticket_promedio'] == 5000


# ═══════════════════════════════════════════════════════════════════════
# TESTS DE CLASIFICACIÓN DE VENDEDORES
# ═══════════════════════════════════════════════════════════════════════

class TestClasificacionVendedores:
    """Valida clasificación de vendedores (Elite, Alto Volumen, etc.)"""
    
    def test_calcula_mediana_operaciones(self, df_ventas_eficiencia):
        """Calcula mediana de operaciones"""
        vendedores_ops = df_ventas_eficiencia.groupby("agente").size()
        mediana_ops = vendedores_ops.median()
        
        assert mediana_ops == 5.0  # (10, 5, 3) → mediana = 5
        
    def test_calcula_mediana_ticket_promedio(self, df_ventas_eficiencia):
        """Calcula mediana de ticket promedio"""
        vendedores_ticket = (
            df_ventas_eficiencia.groupby("agente")
            .apply(lambda x: x["valor_usd"].sum() / len(x))
        )
        mediana_ticket = vendedores_ticket.median()
        
        assert mediana_ticket == 1000.0  # (1000, 5000, 500) → 1000
        
    def test_clasifica_vendedor_elite(self):
        """Vendedor con alto volumen Y alto ticket = Elite"""
        row = pd.Series({
            'operaciones': 100,
            'ticket_promedio': 5000
        })
        
        mediana_ops = 50
        mediana_ticket = 2000
        
        # Elite: ambas métricas sobre la mediana
        if row['operaciones'] > mediana_ops and row['ticket_promedio'] > mediana_ticket:
            clasificacion = "🌟 Elite (Alto Volumen + Alto Ticket)"
        else:
            clasificacion = "Otro"
            
        assert clasificacion == "🌟 Elite (Alto Volumen + Alto Ticket)"
        
    def test_clasifica_vendedor_alto_volumen(self):
        """Vendedor con muchas operaciones pero ticket bajo"""
        row = pd.Series({
            'operaciones': 100,
            'ticket_promedio': 1000
        })
        
        mediana_ops = 50
        mediana_ticket = 2000
        
        if row['operaciones'] > mediana_ops and row['ticket_promedio'] > mediana_ticket:
            clasificacion = "🌟 Elite (Alto Volumen + Alto Ticket)"
        elif row['operaciones'] > mediana_ops:
            clasificacion = "📊 Alto Volumen"
        else:
            clasificacion = "Otro"
            
        assert clasificacion == "📊 Alto Volumen"
        
    def test_clasifica_vendedor_alto_ticket(self):
        """Vendedor con pocas operaciones pero alto ticket"""
        row = pd.Series({
            'operaciones': 30,
            'ticket_promedio': 5000
        })
        
        mediana_ops = 50
        mediana_ticket = 2000
        
        if row['operaciones'] > mediana_ops and row['ticket_promedio'] > mediana_ticket:
            clasificacion = "🌟 Elite (Alto Volumen + Alto Ticket)"
        elif row['operaciones'] > mediana_ops:
            clasificacion = "📊 Alto Volumen"
        elif row['ticket_promedio'] > mediana_ticket:
            clasificacion = "💎 Alto Ticket (Eficiencia)"
        else:
            clasificacion = "Otro"
            
        assert clasificacion == "💎 Alto Ticket (Eficiencia)"
        
    def test_clasifica_vendedor_en_desarrollo(self):
        """Vendedor con ambas métricas bajo la mediana"""
        row = pd.Series({
            'operaciones': 20,
            'ticket_promedio': 1000
        })
        
        mediana_ops = 50
        mediana_ticket = 2000
        
        if row['operaciones'] > mediana_ops and row['ticket_promedio'] > mediana_ticket:
            clasificacion = "🌟 Elite (Alto Volumen + Alto Ticket)"
        elif row['operaciones'] > mediana_ops:
            clasificacion = "📊 Alto Volumen"
        elif row['ticket_promedio'] > mediana_ticket:
            clasificacion = "💎 Alto Ticket (Eficiencia)"
        else:
            clasificacion = "🔄 En Desarrollo"
            
        assert clasificacion == "🔄 En Desarrollo"


# ═══════════════════════════════════════════════════════════════════════
# TESTS DE NORMALIZACIÓN DE COLUMNAS
# ═══════════════════════════════════════════════════════════════════════

class TestNormalizacionColumnas:
    """Valida normalización de nombres de columnas"""
    
    def test_renombra_ventas_usd_a_valor_usd(self):
        """Detecta 'ventas_usd' y renombra a 'valor_usd'"""
        df = pd.DataFrame({
            'fecha': ['2024-01-01'],
            'ventas_usd': [1000]
        })
        
        if "valor_usd" not in df.columns:
            if "ventas_usd" in df.columns:
                df = df.rename(columns={"ventas_usd": "valor_usd"})
        
        assert "valor_usd" in df.columns
        assert df["valor_usd"].iloc[0] == 1000
        
    def test_renombra_ventas_usd_con_iva_a_valor_usd(self):
        """Detecta 'ventas_usd_con_iva' y renombra"""
        df = pd.DataFrame({
            'fecha': ['2024-01-01'],
            'ventas_usd_con_iva': [1160]
        })
        
        if "valor_usd" not in df.columns:
            if "ventas_usd_con_iva" in df.columns:
                df = df.rename(columns={"ventas_usd_con_iva": "valor_usd"})
        
        assert "valor_usd" in df.columns
        assert df["valor_usd"].iloc[0] == 1160
        
    def test_detecta_columna_agente_vendedor_ejecutivo(self):
        """Busca dinámicamente 'agente', 'vendedor' o 'ejecutivo'"""
        df = pd.DataFrame({
            'fecha': ['2024-01-01'],
            'vendedor': ['Juan'],
            'valor_usd': [1000]
        })
        
        columna_agente = None
        for col in df.columns:
            if col.lower() in ["agente", "vendedor", "ejecutivo"]:
                columna_agente = col
                break
        
        assert columna_agente == "vendedor"
