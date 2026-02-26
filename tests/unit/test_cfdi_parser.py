"""
Tests unitarios para el parser de CFDI 4.0
"""

import pytest
from datetime import datetime
from decimal import Decimal
from cfdi.parser import CFDIParser, ComplementoPagoParser


# XML de ejemplo simplificado (CFDI 4.0)
CFDI_EJEMPLO = """<?xml version="1.0" encoding="UTF-8"?>
<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4" 
                   xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital"
                   Version="4.0" 
                   Fecha="2026-02-26T10:30:00" 
                   Folio="12345"
                   Serie="A"
                   SubTotal="1000.00" 
                   Total="1160.00"
                   Moneda="MXN"
                   TipoDeComprobante="I"
                   MetodoPago="PPD"
                   LugarExpedicion="64000">
    <cfdi:Emisor Rfc="XAXX010101000" Nombre="Empresa Test SA" RegimenFiscal="601"/>
    <cfdi:Receptor Rfc="XEXX010101000" 
                    Nombre="Cliente Test SA" 
                    DomicilioFiscalReceptor="64000"
                    RegimenFiscalReceptor="601"
                    UsoCFDI="G03"/>
    <cfdi:Conceptos>
        <cfdi:Concepto ClaveProdServ="43211500"
                       Cantidad="10"
                       ClaveUnidad="H87"
                       Descripcion="Producto de Prueba"
                       ValorUnitario="100.00"
                       Importe="1000.00"
                       ObjetoImp="02"/>
    </cfdi:Conceptos>
    <cfdi:Complemento>
        <tfd:TimbreFiscalDigital xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital"
                                  Version="1.1"
                                  UUID="12345678-1234-1234-1234-123456789012"
                                  FechaTimbrado="2026-02-26T10:31:00"
                                  RfcProvCertif="SAT970701NN3"
                                  SelloSAT="abcdef123456"/>
    </cfdi:Complemento>
</cfdi:Comprobante>
"""


class TestCFDIParser:
    """Tests para CFDIParser"""
    
    def test_parse_cfdi_basico(self):
        """Debe parsear correctamente un CFDI válido"""
        parser = CFDIParser()
        resultado = parser.parse_cfdi_venta(CFDI_EJEMPLO)
        
        # Verificar datos del comprobante
        assert resultado['version'] == '4.0'
        assert resultado['serie'] == 'A'
        assert resultado['folio'] == '12345'
        assert resultado['total'] == Decimal('1160.00')
        assert resultado['moneda'] == 'MXN'
        
        # Verificar emisor
        assert resultado['emisor']['rfc'] == 'XAXX010101000'
        assert resultado['emisor']['nombre'] == 'Empresa Test SA'
        
        # Verificar receptor
        assert resultado['receptor']['rfc'] == 'XEXX010101000'
        assert resultado['receptor']['nombre'] == 'Cliente Test SA'
        assert resultado['receptor']['uso_cfdi'] == 'G03'
        
        # Verificar timbre
        assert resultado['timbre']['uuid'] == '12345678-1234-1234-1234-123456789012'
        assert 'fecha_timbrado' in resultado['timbre']
    
    def test_parse_conceptos(self):
        """Debe extraer conceptos correctamente"""
        parser = CFDIParser()
        resultado = parser.parse_cfdi_venta(CFDI_EJEMPLO)
        
        conceptos = resultado['conceptos']
        assert len(conceptos) == 1
        
        concepto = conceptos[0]
        assert concepto['clave_prod_serv'] == '43211500'
        assert concepto['cantidad'] == Decimal('10')
        assert concepto['descripcion'] == 'Producto de Prueba'
        assert concepto['valor_unitario'] == Decimal('100.00')
        assert concepto['importe'] == Decimal('1000.00')
    
    def test_parse_fechas(self):
        """Debe convertir fechas correctamente"""
        parser = CFDIParser()
        resultado = parser.parse_cfdi_venta(CFDI_EJEMPLO)
        
        assert isinstance(resultado['fecha'], datetime)
        assert resultado['fecha'].year == 2026
        assert resultado['fecha'].month == 2
        assert resultado['fecha'].day == 26
    
    def test_xml_invalido_lanza_error(self):
        """Debe lanzar error con XML inválido"""
        parser = CFDIParser()
        
        with pytest.raises(ValueError):
            parser.parse_cfdi_venta("<xml>invalido</xml>")


class TestComplementoPagoParser:
    """Tests para ComplementoPagoParser"""
    
    def test_parse_complemento_basico(self):
        """Debe parsear complemento de pago correctamente"""
        # TODO: Agregar XML de ejemplo de complemento de pago
        parser = ComplementoPagoParser()
        
        # Placeholder - implementar cuando tengamos XML de ejemplo real
        assert parser is not None


class TestIntegracion:
    """Tests de integración end-to-end"""
    
    def test_batch_processing(self):
        """Debe procesar múltiples CFDIs en batch"""
        from cfdi.parser import parse_cfdi_batch
        
        # Simular batch de 2 XMLs iguales
        xmls = [CFDI_EJEMPLO, CFDI_EJEMPLO]
        empresa_id = "test-uuid-123"
        
        resultado = parse_cfdi_batch(xmls, empresa_id)
        
        assert len(resultado['ventas']) == 2
        assert resultado['ventas'][0]['empresa_id'] == empresa_id
        assert len(resultado['errores']) == 0


# =====================================================================
# Fixtures para testing
# =====================================================================

@pytest.fixture
def cfdi_parser():
    """Fixture: instancia de CFDIParser"""
    return CFDIParser()


@pytest.fixture
def pago_parser():
    """Fixture: instancia de ComplementoPagoParser"""
    return ComplementoPagoParser()


@pytest.fixture
def cfdi_muestra():
    """Fixture: XML de CFDI de muestra"""
    return CFDI_EJEMPLO
