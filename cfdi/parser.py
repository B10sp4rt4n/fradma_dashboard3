"""
Parser de CFDI 4.0 - Extrae datos estructurados de XMLs de SAT

Soporta:
- CFDI 4.0 (factura electrónica estándar)
- Complemento de pagos 2.0
- Multi-moneda (MXN, USD, EUR)
"""

import xml.etree.ElementTree as ET
from typing import Dict, Optional, List
from datetime import datetime
from decimal import Decimal
import uuid


# Namespaces CFDI 4.0
NAMESPACES = {
    'cfdi': 'http://www.sat.gob.mx/cfd/4',
    'tfd': 'http://www.sat.gob.mx/TimbreFiscalDigital',
    'pago20': 'http://www.sat.gob.mx/Pagos20'
}


class CFDIParser:
    """Parser para CFDI 4.0"""
    
    def __init__(self):
        self.namespaces = NAMESPACES
    
    def parse_cfdi_venta(self, xml_path: str) -> Dict:
        """
        Parsea un CFDI de venta (emitido) y extrae datos estructurados
        
        Args:
            xml_path: Ruta al archivo XML o contenido XML como string
            
        Returns:
            Dict con datos estructurados del CFDI
        """
        try:
            # Parsear XML
            if xml_path.startswith('<') or xml_path.startswith('\ufeff<'):
                # Es contenido XML directo
                # Eliminar BOM si existe
                content = xml_path.lstrip('\ufeff')
                root = ET.fromstring(content)
            else:
                # Es ruta de archivo
                # Abrir con encoding utf-8-sig para manejar BOM automáticamente
                with open(xml_path, 'r', encoding='utf-8-sig') as f:
                    content = f.read()
                root = ET.fromstring(content)
            
            # Extraer datos del comprobante (nodo raíz)
            comprobante = self._extract_comprobante(root)
            
            # Extraer datos del emisor
            emisor = self._extract_emisor(root)
            
            # Extraer datos del receptor (cliente)
            receptor = self._extract_receptor(root)
            
            # Extraer conceptos (líneas de producto/servicio)
            conceptos = self._extract_conceptos(root)
            
            # Extraer timbre fiscal digital (UUID del SAT)
            timbre = self._extract_timbre(root)

            # Extraer impuestos del comprobante (traslados + retenciones)
            impuestos_data = self._extract_impuestos(root)

            # Consolidar datos
            result = {
                **comprobante,
                'emisor': emisor,
                'receptor': receptor,
                'conceptos': conceptos,
                'timbre': timbre,
                'iva_trasladado': impuestos_data['iva_trasladado'],
                'iva_retenido':   impuestos_data['iva_retenido'],
                'isr_retenido':   impuestos_data['isr_retenido'],
                'xml_original': ET.tostring(root, encoding='unicode')
            }
            
            return result
            
        except Exception as e:
            raise ValueError(f"Error parsing CFDI: {str(e)}")
    
    def _extract_comprobante(self, root: ET.Element) -> Dict:
        """Extrae datos del nodo Comprobante"""
        return {
            'version': root.get('Version'),
            'serie': root.get('Serie', ''),
            'folio': root.get('Folio', ''),
            'fecha': self._parse_datetime(root.get('Fecha')),
            'sello': root.get('Sello', ''),
            'forma_pago': root.get('FormaPago', ''),
            'no_certificado': root.get('NoCertificado', ''),
            'certificado': root.get('Certificado', ''),
            'subtotal': Decimal(root.get('SubTotal', '0')),
            'descuento': Decimal(root.get('Descuento', '0')),
            'moneda': root.get('Moneda', 'MXN'),
            'tipo_cambio': Decimal(root.get('TipoCambio', '1')),
            'total': Decimal(root.get('Total', '0')),
            'tipo_de_comprobante': root.get('TipoDeComprobante', 'I'),
            'metodo_pago': root.get('MetodoPago', ''),
            'lugar_expedicion': root.get('LugarExpedicion', ''),
            'exportacion': root.get('Exportacion', '01'),
        }
    
    def _extract_emisor(self, root: ET.Element) -> Dict:
        """Extrae datos del Emisor"""
        emisor = root.find('cfdi:Emisor', self.namespaces)
        if emisor is None:
            return {}
        
        return {
            'rfc': emisor.get('Rfc', ''),
            'nombre': emisor.get('Nombre', ''),
            'regimen_fiscal': emisor.get('RegimenFiscal', '')
        }
    
    def _extract_receptor(self, root: ET.Element) -> Dict:
        """Extrae datos del Receptor (cliente)"""
        receptor = root.find('cfdi:Receptor', self.namespaces)
        if receptor is None:
            return {}
        
        return {
            'rfc': receptor.get('Rfc', ''),
            'nombre': receptor.get('Nombre', ''),
            'domicilio_fiscal_receptor': receptor.get('DomicilioFiscalReceptor', ''),
            'residencia_fiscal': receptor.get('ResidenciaFiscal', ''),
            'regimen_fiscal_receptor': receptor.get('RegimenFiscalReceptor', ''),
            'uso_cfdi': receptor.get('UsoCFDI', '')
        }
    
    def _extract_conceptos(self, root: ET.Element) -> List[Dict]:
        """Extrae conceptos (productos/servicios)"""
        conceptos_node = root.find('cfdi:Conceptos', self.namespaces)
        if conceptos_node is None:
            return []
        
        conceptos = []
        for concepto in conceptos_node.findall('cfdi:Concepto', self.namespaces):
            conceptos.append({
                'clave_prod_serv': concepto.get('ClaveProdServ', ''),
                'no_identificacion': concepto.get('NoIdentificacion', ''),
                'cantidad': Decimal(concepto.get('Cantidad', '0')),
                'clave_unidad': concepto.get('ClaveUnidad', ''),
                'unidad': concepto.get('Unidad', ''),
                'descripcion': concepto.get('Descripcion', ''),
                'valor_unitario': Decimal(concepto.get('ValorUnitario', '0')),
                'importe': Decimal(concepto.get('Importe', '0')),
                'descuento': Decimal(concepto.get('Descuento', '0')),
                'objeto_imp': concepto.get('ObjetoImp', '02')
            })
        
        return conceptos
    
    def _extract_impuestos(self, root: ET.Element) -> Dict:
        """Extrae traslados y retenciones del nodo cfdi:Impuestos del comprobante."""
        result = {
            'iva_trasladado': Decimal('0'),
            'isr_retenido':   Decimal('0'),
            'iva_retenido':   Decimal('0'),
        }
        impuestos_node = root.find('cfdi:Impuestos', self.namespaces)
        if impuestos_node is None:
            return result

        # Traslados
        traslados = impuestos_node.find('cfdi:Traslados', self.namespaces)
        if traslados is not None:
            for t in traslados.findall('cfdi:Traslado', self.namespaces):
                if t.get('Impuesto') == '002':  # IVA
                    result['iva_trasladado'] += Decimal(t.get('Importe', '0'))

        # Retenciones
        retenciones = impuestos_node.find('cfdi:Retenciones', self.namespaces)
        if retenciones is not None:
            for r in retenciones.findall('cfdi:Retencion', self.namespaces):
                impuesto = r.get('Impuesto', '')
                importe  = Decimal(r.get('Importe', '0'))
                if impuesto == '001':   # ISR
                    result['isr_retenido'] += importe
                elif impuesto == '002': # IVA retenido
                    result['iva_retenido'] += importe

        return result

    def _extract_timbre(self, root: ET.Element) -> Dict:
        """Extrae datos del Timbre Fiscal Digital"""
        complemento = root.find('cfdi:Complemento', self.namespaces)
        if complemento is None:
            return {}
        
        timbre = complemento.find('tfd:TimbreFiscalDigital', self.namespaces)
        if timbre is None:
            return {}
        
        return {
            'uuid': timbre.get('UUID', ''),
            'fecha_timbrado': self._parse_datetime(timbre.get('FechaTimbrado')),
            'rfc_prov_certif': timbre.get('RfcProvCertif', ''),
            'sello_sat': timbre.get('SelloSAT', ''),
            'no_certificado_sat': timbre.get('NoCertificadoSAT', '')
        }
    
    def _parse_datetime(self, date_str: Optional[str]) -> Optional[datetime]:
        """Convierte string de fecha CFDI a datetime"""
        if not date_str:
            return None
        
        try:
            # Formato: 2024-02-26T10:30:00
            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        except:
            return None


class ComplementoPagoParser:
    """Parser para Complemento de Pagos 2.0"""
    
    def __init__(self):
        self.namespaces = NAMESPACES
    
    def parse_complemento_pago(self, xml_path: str) -> List[Dict]:
        """
        Parsea un complemento de pago y extrae registros de cobranza
        
        Args:
            xml_path: Ruta al archivo XML o contenido XML como string
            
        Returns:
            Lista de dicts con pagos documentados
        """
        try:
            if xml_path.startswith('<') or xml_path.startswith('\ufeff<'):
                root = ET.fromstring(xml_path.lstrip('\ufeff'))
            else:
                tree = ET.parse(xml_path)
                root = tree.getroot()
            
            # Buscar complemento de pagos
            complemento = root.find('cfdi:Complemento', self.namespaces)
            if complemento is None:
                return []
            
            pagos_node = complemento.find('pago20:Pagos', self.namespaces)
            if pagos_node is None:
                return []
            
            # Extraer UUID del complemento
            timbre = complemento.find('tfd:TimbreFiscalDigital', self.namespaces)
            uuid_complemento = timbre.get('UUID', '') if timbre is not None else ''
            
            pagos = []
            for pago in pagos_node.findall('.//pago20:Pago', self.namespaces):
                # Extraer documentos relacionados (facturas cobradas)
                for doc in pago.findall('pago20:DoctoRelacionado', self.namespaces):
                    pagos.append({
                        'uuid_complemento': uuid_complemento,
                        'fecha_pago': self._parse_datetime(pago.get('FechaPago')),
                        'forma_pago': pago.get('FormaDePagoP', ''),
                        'moneda': pago.get('MonedaP', 'MXN'),
                        'tipo_cambio': Decimal(pago.get('TipoCambioP', '1')),
                        'monto': Decimal(pago.get('Monto', '0')),
                        'uuid_documento': doc.get('IdDocumento', ''),
                        'serie': doc.get('Serie', ''),
                        'folio': doc.get('Folio', ''),
                        'moneda_dr': doc.get('MonedaDR', 'MXN'),
                        'imp_saldo_ant': Decimal(doc.get('ImpSaldoAnt', '0')),
                        'imp_pagado': Decimal(doc.get('ImpPagado', '0')),
                        'imp_saldo_insoluto': Decimal(doc.get('ImpSaldoInsoluto', '0')),
                        'num_parcialidad': int(doc.get('NumParcialidad', '1'))
                    })
            
            return pagos
            
        except Exception as e:
            raise ValueError(f"Error parsing complemento de pago: {str(e)}")
    
    def _parse_datetime(self, date_str: Optional[str]) -> Optional[datetime]:
        """Convierte string de fecha a datetime"""
        if not date_str:
            return None
        
        try:
            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        except:
            return None


def parse_cfdi_batch(xml_files: List[str], empresa_id: str) -> Dict:
    """
    Procesa múltiples CFDIs en batch
    
    Args:
        xml_files: Lista de rutas a archivos XML
        empresa_id: UUID de la empresa propietaria
        
    Returns:
        Dict con resultados: {
            'ventas': [],
            'pagos': [],
            'errores': []
        }
    """
    parser_venta = CFDIParser()
    parser_pago = ComplementoPagoParser()
    
    results = {
        'ventas': [],
        'pagos': [],
        'errores': []
    }
    
    for xml_file in xml_files:
        try:
            # Intentar parsear como venta
            venta = parser_venta.parse_cfdi_venta(xml_file)
            venta['empresa_id'] = empresa_id

            # Los CFDI tipo 'P' son complementos de pago, no facturas de ingreso.
            # Solo se agregan a ventas si son tipo 'I' (ingreso) u otros tipos no-pago.
            if venta.get('tipo_de_comprobante') != 'P':
                results['ventas'].append(venta)

            # Si tiene complemento de pago, también parsearlo
            try:
                pagos = parser_pago.parse_complemento_pago(xml_file)
                results['pagos'].extend(pagos)
            except:
                pass  # No todos los CFDIs tienen complemento de pago
                
        except Exception as e:
            # Extraer solo el nombre del archivo, no la ruta completa
            import os
            filename = os.path.basename(xml_file) if isinstance(xml_file, str) else 'desconocido'
            results['errores'].append({
                'archivo': filename,
                'error': str(e)
            })
    
    return results
