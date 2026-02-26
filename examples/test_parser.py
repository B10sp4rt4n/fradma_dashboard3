"""
Script de ejemplo para probar el parser de CFDI

Uso:
    python examples/test_parser.py path/to/factura.xml
"""

import sys
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from cfdi.parser import CFDIParser, ComplementoPagoParser


def main():
    """Parsear un CFDI de ejemplo y mostrar resultados"""
    
    if len(sys.argv) < 2:
        print("❌ Error: Debes especificar la ruta al XML")
        print("Uso: python examples/test_parser.py path/to/factura.xml")
        sys.exit(1)
    
    xml_path = sys.argv[1]
    
    if not Path(xml_path).exists():
        print(f"❌ Error: Archivo no encontrado: {xml_path}")
        sys.exit(1)
    
    print(f"📄 Parseando CFDI: {xml_path}\n")
    
    try:
        # Parsear
        parser = CFDIParser()
        datos = parser.parse_cfdi_venta(xml_path)
        
        # Mostrar resultados
        print("=" * 60)
        print("✅ CFDI PARSEADO EXITOSAMENTE")
        print("=" * 60)
        
        print(f"\n📋 DATOS GENERALES:")
        print(f"   UUID:         {datos['timbre']['uuid']}")
        print(f"   Serie-Folio:  {datos['serie']}-{datos['folio']}")
        print(f"   Fecha:        {datos['fecha']}")
        print(f"   Total:        ${datos['total']:,.2f} {datos['moneda']}")
        print(f"   Método pago:  {datos['metodo_pago']}")
        
        print(f"\n🏢 EMISOR:")
        print(f"   RFC:          {datos['emisor']['rfc']}")
        print(f"   Nombre:       {datos['emisor']['nombre']}")
        
        print(f"\n👤 RECEPTOR (Cliente):")
        print(f"   RFC:          {datos['receptor']['rfc']}")
        print(f"   Nombre:       {datos['receptor']['nombre']}")
        print(f"   Uso CFDI:     {datos['receptor']['uso_cfdi']}")
        
        print(f"\n📦 CONCEPTOS:")
        for i, concepto in enumerate(datos['conceptos'], 1):
            print(f"   {i}. {concepto['descripcion']}")
            print(f"      Cantidad:  {concepto['cantidad']}")
            print(f"      Unitario:  ${concepto['valor_unitario']:,.2f}")
            print(f"      Importe:   ${concepto['importe']:,.2f}")
        
        print(f"\n💰 TOTALES:")
        print(f"   Subtotal:     ${datos['subtotal']:,.2f}")
        if datos['descuento'] > 0:
            print(f"   Descuento:    ${datos['descuento']:,.2f}")
        print(f"   Total:        ${datos['total']:,.2f}")
        
        print("\n" + "=" * 60)
        
        # Intentar parsear complemento de pago si existe
        try:
            pago_parser = ComplementoPagoParser()
            pagos = pago_parser.parse_complemento_pago(xml_path)
            
            if pagos:
                print("\n💸 COMPLEMENTO DE PAGO DETECTADO:")
                for pago in pagos:
                    print(f"   Fecha pago:   {pago['fecha_pago']}")
                    print(f"   Monto:        ${pago['monto']:,.2f}")
                    print(f"   Factura:      {pago['serie']}-{pago['folio']}")
        except:
            pass  # No tiene complemento de pago
        
    except Exception as e:
        print(f"❌ ERROR AL PARSEAR CFDI:")
        print(f"   {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
