"""
Tests unitarios para utils/formatos.py
Funciones de formateo de datos.
"""
import pytest
import math
from utils.formatos import (
    formato_moneda,
    formato_numero,
    formato_porcentaje,
    formato_compacto,
    formato_dias,
    formato_delta_moneda
)


class TestFormatoMoneda:
    """Tests para formateo de moneda."""
    
    def test_formato_basico(self):
        assert formato_moneda(1234.56) == "$1,234.56"
        assert formato_moneda(1000000) == "$1,000,000.00"
    
    def test_valores_negativos(self):
        assert formato_moneda(-500.25) == "$-500.25"
    
    def test_cero(self):
        assert formato_moneda(0) == "$0.00"
    
    def test_valores_nulos(self):
        assert formato_moneda(None) == "$0.00"
        assert formato_moneda(float('nan')) == "$0.00"
    
    def test_decimales_personalizados(self):
        assert formato_moneda(1234.5678, decimales=0) == "$1,235"
        assert formato_moneda(1234.5678, decimales=3) == "$1,234.568"
        assert formato_moneda(1234.5678, decimales=4) == "$1,234.5678"  # Cubre líneas 31-32
    
    def test_numeros_grandes(self):
        assert formato_moneda(1234567.89) == "$1,234,567.89"
    
    def test_valores_invalidos(self):
        """Test: Maneja valores inválidos retornando $0.00."""
        assert formato_moneda("texto") == "$0.00"
        assert formato_moneda([1, 2, 3]) == "$0.00"


class TestFormatoNumero:
    """Tests para formateo de números."""
    
    def test_sin_decimales(self):
        assert formato_numero(1234) == "1,234"
        assert formato_numero(1234567) == "1,234,567"
    
    def test_con_decimales(self):
        assert formato_numero(1234.56, decimales=2) == "1,234.56"
        assert formato_numero(1234.567, decimales=3) == "1,234.567"  # Cubre líneas 55-56
    
    def test_valores_nulos(self):
        assert formato_numero(None) == "0"
        assert formato_numero(float('nan')) == "0"
    
    def test_cero(self):
        assert formato_numero(0) == "0"
    
    def test_valores_invalidos(self):
        """Test: Maneja valores inválidos retornando 0."""
        assert formato_numero("texto") == "0"
        assert formato_numero({"key": "value"}) == "0"


class TestFormatoPorcentaje:
    """Tests para formateo de porcentajes."""
    
    def test_porcentaje_basico(self):
        assert formato_porcentaje(25.5) == "25.5%"
        assert formato_porcentaje(100) == "100.0%"
    
    def test_conversion_de_proporcion(self):
        """Convierte 0-1 a porcentaje"""
        assert formato_porcentaje(0.255) == "25.5%"
        assert formato_porcentaje(1.0) == "100.0%"
    
    def test_decimales_personalizados(self):
        assert formato_porcentaje(25.567, decimales=0) == "26%"
        assert formato_porcentaje(25.567, decimales=2) == "25.57%"
        assert formato_porcentaje(25.567, decimales=3) == "25.567%"  # Cubre líneas 85-86
    
    def test_valores_nulos(self):
        assert formato_porcentaje(None) == "0.0%"
        assert formato_porcentaje(float('nan')) == "0.0%"
    
    def test_valores_invalidos(self):
        """Test: Maneja valores inválidos retornando 0.0%."""
        assert formato_porcentaje("texto") == "0.0%"
        assert formato_porcentaje([1, 2]) == "0.0%"


class TestFormatoCompacto:
    """Tests para formateo compacto (K, M, B)."""
    
    def test_miles(self):
        assert formato_compacto(1500) == "1.5K"
        assert formato_compacto(999) == "999"
    
    def test_millones(self):
        assert formato_compacto(2500000) == "2.5M"
        assert formato_compacto(1200000) == "1.2M"
    
    def test_billones(self):
        assert formato_compacto(3500000000) == "3.5B"
    
    def test_numeros_pequenos(self):
        assert formato_compacto(500) == "500"
        assert formato_compacto(0) == "0"
    
    def test_negativos(self):
        assert formato_compacto(-1500) == "-1.5K"
        assert formato_compacto(-2500000) == "-2.5M"
    
    def test_valores_nulos(self):
        assert formato_compacto(None) == "0"
        assert formato_compacto(float('nan')) == "0"
    
    def test_valores_invalidos(self):
        """Test: Maneja valores inválidos retornando 0 (líneas 144-145)."""
        assert formato_compacto("texto") == "0"
        assert formato_compacto({"key": 123}) == "0"


class TestFormatoDias:
    """Tests para formateo de días."""
    
    def test_singular(self):
        assert formato_dias(1) == "1 día"
    
    def test_plural(self):
        assert formato_dias(5) == "5 días"
        assert formato_dias(30) == "30 días"
    
    def test_cero(self):
        assert formato_dias(0) == "0 días"
    
    def test_valores_nulos(self):
        assert formato_dias(None) == "0 días"
        assert formato_dias(float('nan')) == "0 días"
    
    def test_valores_invalidos(self):
        """Test: Maneja valores inválidos retornando 0 días (líneas 167-168)."""
        assert formato_dias("texto") == "0 días"
        assert formato_dias([1, 2]) == "0 días"


class TestFormatoDeltaMoneda:
    """Tests para formateo de deltas de moneda."""
    
    def test_positivo(self):
        assert formato_delta_moneda(1234.56) == "$1,234.56"
    
    def test_negativo(self):
        result = formato_delta_moneda(-1234.56)
        # Debe incluir el signo negativo
        assert "-" in result
        assert "1,234.56" in result
    
    def test_decimales_personalizados(self):
        """Test: Cubre líneas 109 y 113-115 (decimales 0 y arbitrarios)."""
        assert formato_delta_moneda(1234.56, decimales=0) == "$1,235"
        assert formato_delta_moneda(-1234.56, decimales=0) == "-$1,235"
        assert formato_delta_moneda(1234.567, decimales=3) == "$1,234.567"
        assert formato_delta_moneda(-1234.567, decimales=3) == "-$1,234.567"
    
    def test_valores_nulos(self):
        """Test: Cubre línea 101."""
        assert formato_delta_moneda(None) == "$0.00"
        assert formato_delta_moneda(float('nan')) == "$0.00"
    
    def test_valores_invalidos(self):
        """Test: Maneja valores inválidos retornando $0.00."""
        assert formato_delta_moneda("texto") == "$0.00"
        assert formato_delta_moneda([1, 2]) == "$0.00"
    
    def test_cero(self):
        assert formato_delta_moneda(0) == "$0.00"
