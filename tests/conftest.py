"""
Pytest configuration and shared fixtures.
"""
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


@pytest.fixture
def df_cxc_simple():
    """DataFrame básico para tests simples."""
    return pd.DataFrame({
        'saldo_adeudado': [1000, 2000, 3000],
        'dias_overdue': [-5, 10, 60],
        'estatus': ['Vigente', 'Vencido', 'Crítico']
    })


@pytest.fixture
def df_cxc_con_pagados():
    """DataFrame con registros pagados y no pagados."""
    return pd.DataFrame({
        'saldo_adeudado': [1000, 2000, 3000, 4000],
        'dias_overdue': [10, 20, 30, 40],
        'estatus': ['Pendiente', 'Pagado', 'Vencido', 'Pagado']
    })


@pytest.fixture
def df_cxc_completo():
    """DataFrame completo con datos realistas de CxC."""
    return pd.DataFrame({
        'deudor': ['Cliente A', 'Cliente B', 'Cliente C', 'Cliente D', 'Cliente E'],
        'saldo_adeudado': [50000, 30000, 20000, 10000, 5000],
        'dias_vencido': [15, 45, 90, -10, 120],
        'estatus': ['Vencido', 'Vencido', 'Crítico', 'Vigente', 'Crítico'],
        'linea_negocio': ['Línea 1', 'Línea 2', 'Línea 1', 'Línea 3', 'Línea 2'],
        'vendedor': ['Juan', 'María', 'Juan', 'Pedro', 'María']
    })


@pytest.fixture
def df_con_fechas():
    """DataFrame con columnas de fecha para testing."""
    hoy = pd.Timestamp.today().normalize()
    return pd.DataFrame({
        'fecha_vencimiento': [
            hoy - timedelta(days=30),
            hoy + timedelta(days=15),
            hoy,
            hoy - timedelta(days=90)
        ],
        'fecha_de_pago': [
            hoy - timedelta(days=60),
            hoy - timedelta(days=45),
            hoy - timedelta(days=30),
            hoy - timedelta(days=150)
        ],
        'dias_de_credito': [30, 60, 30, 60],
        'saldo_adeudado': [1000, 2000, 3000, 4000]
    })


@pytest.fixture
def mock_fecha_hoy(monkeypatch):
    """Mock de fecha actual para tests determinísticos."""
    fecha_fija = pd.Timestamp('2025-01-15')
    
    class MockTimestamp:
        @staticmethod
        def today():
            return fecha_fija
        
        @staticmethod
        def normalize():
            return fecha_fija
    
    monkeypatch.setattr('pandas.Timestamp.today', lambda: fecha_fija)
    return fecha_fija
