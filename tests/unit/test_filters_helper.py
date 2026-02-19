"""
Tests unitarios para utils.filters_helper.

Valida:
- obtener_lineas_filtradas(): Filtrado correcto de líneas
- generar_contexto_filtros(): Generación de mensajes contextuales
- aplicar_filtro_dataframe(): Aplicación segura de filtros
"""

import pytest
import pandas as pd
from utils.filters_helper import (
    obtener_lineas_filtradas,
    generar_contexto_filtros,
    aplicar_filtro_dataframe
)


class TestObtenerLineasFiltradas:
    """Tests para obtener_lineas_filtradas()"""
    
    def test_filtrar_todas_con_especificas(self):
        """Debe remover 'Todas' cuando hay líneas específicas"""
        resultado = obtener_lineas_filtradas(["Todas", "repi", "ultra plast"])
        assert resultado == ["repi", "ultra plast"]
    
    def test_solo_todas(self):
        """Debe retornar lista vacía cuando solo está 'Todas'"""
        resultado = obtener_lineas_filtradas(["Todas"])
        assert resultado == []
    
    def test_sin_todas(self):
        """Debe mantener todas las líneas cuando no hay 'Todas'"""
        resultado = obtener_lineas_filtradas(["repi", "ultra plast"])
        assert resultado == ["repi", "ultra plast"]
    
    def test_entrada_none(self):
        """Debe manejar None sin errores"""
        resultado = obtener_lineas_filtradas(None)
        assert resultado == []
    
    def test_lista_vacia(self):
        """Debe manejar lista vacía"""
        resultado = obtener_lineas_filtradas([])
        assert resultado == []
    
    def test_filtrar_strings_vacios(self):
        """Debe remover strings vacíos"""
        resultado = obtener_lineas_filtradas(["repi", "", "ultra plast", "  "])
        # Solo el string vacío se filtra, espacios se mantienen (truthy)
        assert "repi" in resultado
        assert "ultra plast" in resultado
        assert "" not in resultado
    
    def test_orden_preservado(self):
        """Debe preservar el orden original"""
        resultado = obtener_lineas_filtradas(["Todas", "c", "a", "b"])
        assert resultado == ["c", "a", "b"]


class TestGenerarContextoFiltros:
    """Tests para generar_contexto_filtros()"""
    
    def test_con_filtros(self):
        """Debe generar mensaje cuando hay filtros"""
        resultado = generar_contexto_filtros(["repi", "ultra plast"])
        assert resultado is not None
        assert "repi, ultra plast" in resultado
        assert "ÚNICAMENTE" in resultado
        assert "SOLO" in resultado
    
    def test_sin_filtros(self):
        """Debe retornar None cuando no hay filtros"""
        resultado = generar_contexto_filtros([])
        assert resultado is None
    
    def test_single_filtro(self):
        """Debe funcionar con un solo filtro"""
        resultado = generar_contexto_filtros(["repi"])
        assert "repi" in resultado
        assert "ÚNICAMENTE" in resultado
    
    def test_formato_mensaje(self):
        """Debe contener los elementos clave del mensaje"""
        resultado = generar_contexto_filtros(["test"])
        assert "líneas de negocio" in resultado
        assert "ventas y métricas" in resultado
        assert "no todo el negocio" in resultado


class TestAplicarFiltroDataframe:
    """Tests para aplicar_filtro_dataframe()"""
    
    def test_filtrar_correctamente(self):
        """Debe filtrar DataFrame correctamente"""
        df = pd.DataFrame({
            'linea_negocio': ['repi', 'ultra', 'repi', 'mega'],
            'ventas': [100, 200, 150, 300]
        })
        
        resultado = aplicar_filtro_dataframe(
            df, 
            columna='linea_negocio',
            lineas_filtrar=['repi', 'mega']
        )
        
        assert len(resultado) == 3
        assert resultado['linea_negocio'].tolist() == ['repi', 'repi', 'mega']
    
    def test_sin_filtros(self):
        """Debe retornar DataFrame original si no hay filtros"""
        df = pd.DataFrame({
            'linea_negocio': ['repi', 'ultra', 'mega'],
            'ventas': [100, 200, 300]
        })
        
        resultado = aplicar_filtro_dataframe(
            df,
            columna='linea_negocio',
            lineas_filtrar=[]
        )
        
        assert len(resultado) == 3
        assert resultado.equals(df)
    
    def test_columna_no_existe_con_validacion(self):
        """Debe retornar original si columna no existe (con validación)"""
        df = pd.DataFrame({
            'otra_columna': ['a', 'b', 'c'],
            'ventas': [100, 200, 300]
        })
        
        resultado = aplicar_filtro_dataframe(
            df,
            columna='linea_negocio',  # No existe
            lineas_filtrar=['repi'],
            validar_columna=True
        )
        
        assert resultado.equals(df)
    
    def test_columna_no_existe_sin_validacion(self):
        """Debe fallar si columna no existe y validación desactivada"""
        df = pd.DataFrame({
            'otra_columna': ['a', 'b', 'c'],
            'ventas': [100, 200, 300]
        })
        
        with pytest.raises(KeyError):
            aplicar_filtro_dataframe(
                df,
                columna='linea_negocio',  # No existe
                lineas_filtrar=['repi'],
                validar_columna=False
            )
    
    def test_filtro_sin_coincidencias(self):
        """Debe retornar DataFrame vacío si no hay coincidencias"""
        df = pd.DataFrame({
            'linea_negocio': ['repi', 'ultra', 'mega'],
            'ventas': [100, 200, 300]
        })
        
        resultado = aplicar_filtro_dataframe(
            df,
            columna='linea_negocio',
            lineas_filtrar=['inexistente']
        )
        
        assert len(resultado) == 0
        assert list(resultado.columns) == ['linea_negocio', 'ventas']


class TestIntegracion:
    """Tests de integración del flujo completo"""
    
    def test_flujo_completo_con_filtros(self):
        """Simula el flujo completo: obtener filtros → generar contexto → aplicar a DF"""
        # Paso 1: Obtener líneas filtradas
        lineas_seleccionadas = ["Todas", "repi", "ultra plast"]
        lineas_filtrar = obtener_lineas_filtradas(lineas_seleccionadas)
        
        assert lineas_filtrar == ["repi", "ultra plast"]
        
        # Paso 2: Generar contexto
        contexto = generar_contexto_filtros(lineas_filtrar)
        
        assert contexto is not None
        assert "repi, ultra plast" in contexto
        
        # Paso 3: Aplicar a DataFrame
        df = pd.DataFrame({
            'linea_de_negocio': ['repi', 'mega', 'ultra plast', 'repi'],
            'ventas': [100, 200, 300, 150]
        })
        
        df_filtrado = aplicar_filtro_dataframe(
            df,
            columna='linea_de_negocio',
            lineas_filtrar=lineas_filtrar
        )
        
        assert len(df_filtrado) == 3
        assert df_filtrado['ventas'].sum() == 550
    
    def test_flujo_completo_sin_filtros(self):
        """Simula el flujo cuando solo está seleccionado 'Todas'"""
        # Paso 1: Obtener líneas filtradas
        lineas_seleccionadas = ["Todas"]
        lineas_filtrar = obtener_lineas_filtradas(lineas_seleccionadas)
        
        assert lineas_filtrar == []
        
        # Paso 2: Generar contexto
        contexto = generar_contexto_filtros(lineas_filtrar)
        
        assert contexto is None
        
        # Paso 3: Aplicar a DataFrame (no se filtra)
        df = pd.DataFrame({
            'linea_de_negocio': ['repi', 'mega', 'ultra plast'],
            'ventas': [100, 200, 300]
        })
        
        df_filtrado = aplicar_filtro_dataframe(
            df,
            columna='linea_de_negocio',
            lineas_filtrar=lineas_filtrar
        )
        
        assert len(df_filtrado) == 3
        assert df_filtrado.equals(df)
