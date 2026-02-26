#!/usr/bin/env python3
"""
Script de ejemplo: Ingesta completa de CFDIs a Neon PostgreSQL.

Este script demuestra el flujo end-to-end:
1. Leer múltiples XMLs de CFDI (puede ser de un ZIP o carpeta)
2. Parsear cada XML con CFDIParser
3. Insertar en Neon PostgreSQL con NeonIngestion
4. Reportar estadísticas de procesamiento

Uso:
    python examples/ingest_cfdi_to_neon.py \\
        --xml-folder /ruta/a/cfdi_xmls/ \\
        --empresa-id 1 \\
        --neon-url "postgresql://user:pass@host/db?sslmode=require"
        
    O desde un ZIP:
    python examples/ingest_cfdi_to_neon.py \\
        --xml-zip facturas_2025.zip \\
        --empresa-id 1 \\
        --neon-url "postgresql://user:pass@host/db?sslmode=require"

Autor: Fradma Dashboard Team
Fecha: Febrero 2026
"""

import argparse
import logging
import os
import sys
import zipfile
import tempfile
from pathlib import Path
from typing import List
from datetime import datetime

# Agregar directorio padre al path para importar módulos
sys.path.insert(0, str(Path(__file__).parent.parent))

from cfdi.parser import parse_cfdi_batch
from cfdi.ingestion import NeonIngestion, verify_connection

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def extract_zip_to_temp(zip_path: str) -> str:
    """
    Extrae un ZIP de XMLs a una carpeta temporal.
    
    Args:
        zip_path: Ruta al archivo ZIP
        
    Returns:
        Ruta a la carpeta temporal con los XMLs extraídos
    """
    logger.info(f"Extrayendo {zip_path}...")
    temp_dir = tempfile.mkdtemp(prefix='cfdi_')
    
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        # Filtrar solo archivos XML
        xml_files = [f for f in zip_ref.namelist() if f.lower().endswith('.xml')]
        logger.info(f"Encontrados {len(xml_files)} archivos XML en el ZIP")
        
        for xml_file in xml_files:
            zip_ref.extract(xml_file, temp_dir)
    
    return temp_dir


def find_xml_files(folder_path: str) -> List[str]:
    """
    Encuentra todos los archivos XML en una carpeta (recursivo).
    
    Args:
        folder_path: Ruta a la carpeta
        
    Returns:
        Lista de rutas completas a archivos XML
    """
    xml_files = []
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            if file.lower().endswith('.xml'):
                xml_files.append(os.path.join(root, file))
    
    return xml_files


def read_xml_contents(xml_files: List[str]) -> List[str]:
    """
    Lee el contenido de múltiples archivos XML.
    
    Args:
        xml_files: Lista de rutas a archivos XML
        
    Returns:
        Lista de strings con el contenido de cada XML
    """
    contents = []
    errores = 0
    
    for xml_file in xml_files:
        try:
            with open(xml_file, 'r', encoding='utf-8') as f:
                contents.append(f.read())
        except Exception as e:
            logger.warning(f"Error leyendo {xml_file}: {e}")
            errores += 1
    
    if errores > 0:
        logger.warning(f"{errores} archivos no se pudieron leer")
    
    return contents


def print_stats_summary(stats: dict):
    """
    Imprime un resumen bonito de las estadísticas de ingesta.
    
    Args:
        stats: Diccionario de estadísticas retornado por insert_ventas_batch
    """
    print("\n" + "="*60)
    print("📊 RESUMEN DE INGESTA")
    print("="*60)
    print(f"Total XMLs procesados:    {stats['total']}")
    print(f"✅ Insertados correctamente: {stats['insertados']}")
    print(f"⚠️  Duplicados (saltados):    {stats['duplicados']}")
    print(f"❌ Errores:                  {stats['errores']}")
    
    if stats['errores'] > 0:
        print("\n❌ Detalles de errores:")
        for i, error in enumerate(stats['detalles_errores'][:10], 1):
            print(f"  {i}. UUID: {error['uuid']}")
            print(f"     Error: {error['error'][:100]}...")
        
        if len(stats['detalles_errores']) > 10:
            print(f"  ... y {len(stats['detalles_errores']) - 10} errores más")
    
    print("="*60 + "\n")


def print_empresa_stats(ingestion: NeonIngestion, empresa_id: int):
    """
    Imprime estadísticas de la empresa después de la ingesta.
    
    Args:
        ingestion: Instancia de NeonIngestion conectada
        empresa_id: ID de la empresa
    """
    try:
        stats = ingestion.get_empresa_stats(empresa_id)
        
        print("\n" + "="*60)
        print(f"📈 ESTADÍSTICAS EMPRESA ID {empresa_id}")
        print("="*60)
        print(f"Total CFDIs almacenados:  {stats['total_cfdis']:,}")
        print(f"Total conceptos:          {stats['total_conceptos']:,}")
        print(f"Total pagos registrados:  {stats['total_pagos']:,}")
        
        if stats['fecha_primer_cfdi'] and stats['fecha_ultimo_cfdi']:
            print(f"\nRango de fechas:")
            print(f"  Primer CFDI: {stats['fecha_primer_cfdi'].strftime('%Y-%m-%d')}")
            print(f"  Último CFDI: {stats['fecha_ultimo_cfdi'].strftime('%Y-%m-%d')}")
        
        if stats['totales_por_moneda']:
            print(f"\nTotal facturado por moneda:")
            for moneda, total in stats['totales_por_moneda'].items():
                print(f"  {moneda}: ${total:,.2f}")
        
        print("="*60 + "\n")
        
    except Exception as e:
        logger.warning(f"No se pudieron obtener estadísticas: {e}")


def main():
    """Función principal del script."""
    parser = argparse.ArgumentParser(
        description='Ingesta masiva de CFDIs a Neon PostgreSQL',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # Argumentos de entrada
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        '--xml-folder',
        help='Carpeta con archivos XML de CFDIs'
    )
    input_group.add_argument(
        '--xml-zip',
        help='Archivo ZIP con XMLs de CFDIs'
    )
    
    # Argumentos de destino
    parser.add_argument(
        '--empresa-id',
        type=int,
        required=True,
        help='ID de la empresa en tabla empresas'
    )
    parser.add_argument(
        '--neon-url',
        required=True,
        help='URL de conexión a Neon PostgreSQL'
    )
    
    # Opciones
    parser.add_argument(
        '--skip-duplicates',
        action='store_true',
        default=True,
        help='Saltar CFDIs con UUID duplicado (default: True)'
    )
    parser.add_argument(
        '--show-stats',
        action='store_true',
        default=True,
        help='Mostrar estadísticas de empresa al final (default: True)'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Modo verbose (muestra logs detallados)'
    )
    
    args = parser.parse_args()
    
    # Configurar nivel de logging
    if args.verbose:
        logging.getLogger('cfdi').setLevel(logging.DEBUG)
    
    # Paso 1: Obtener lista de archivos XML
    logger.info("="*60)
    logger.info("🚀 INICIANDO INGESTA DE CFDIs A NEON")
    logger.info("="*60)
    
    if args.xml_zip:
        logger.info(f"Fuente: ZIP - {args.xml_zip}")
        temp_folder = extract_zip_to_temp(args.xml_zip)
        xml_files = find_xml_files(temp_folder)
    else:
        logger.info(f"Fuente: Carpeta - {args.xml_folder}")
        xml_files = find_xml_files(args.xml_folder)
    
    if not xml_files:
        logger.error("❌ No se encontraron archivos XML")
        return 1
    
    logger.info(f"📄 Encontrados {len(xml_files)} archivos XML")
    
    # Paso 2: Verificar conexión a Neon
    logger.info("🔌 Verificando conexión a Neon...")
    if not verify_connection(args.neon_url):
        logger.error("❌ No se pudo conectar a Neon. Verifica la URL de conexión.")
        return 1
    
    logger.info("✅ Conexión a Neon exitosa")
    
    # Paso 3: Leer y parsear XMLs
    logger.info("📖 Leyendo archivos XML...")
    xml_contents = read_xml_contents(xml_files)
    
    logger.info("🔍 Parseando CFDIs...")
    start_time = datetime.now()
    ventas_parseadas = parse_cfdi_batch(xml_contents)
    parse_time = (datetime.now() - start_time).total_seconds()
    
    logger.info(f"✅ {len(ventas_parseadas)} CFDIs parseados en {parse_time:.2f}s")
    
    # Paso 4: Insertar en Neon
    logger.info(f"💾 Insertando en Neon (empresa_id={args.empresa_id})...")
    
    with NeonIngestion(args.neon_url) as ingestion:
        start_time = datetime.now()
        
        stats = ingestion.insert_ventas_batch(
            empresa_id=args.empresa_id,
            ventas_list=ventas_parseadas,
            skip_duplicates=args.skip_duplicates
        )
        
        insert_time = (datetime.now() - start_time).total_seconds()
        
        # Imprimir resultados
        print_stats_summary(stats)
        
        logger.info(f"⏱️  Tiempo de inserción: {insert_time:.2f}s")
        logger.info(f"⚡ Throughput: {len(xml_files)/insert_time:.1f} CFDIs/segundo")
        
        # Mostrar estadísticas finales
        if args.show_stats:
            print_empresa_stats(ingestion, args.empresa_id)
    
    logger.info("✅ Proceso completado exitosamente")
    
    # Limpiar carpeta temporal si se usó ZIP
    if args.xml_zip:
        import shutil
        shutil.rmtree(temp_folder)
        logger.info(f"🧹 Carpeta temporal limpiada")
    
    return 0


if __name__ == '__main__':
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("\n⚠️  Proceso interrumpido por el usuario")
        sys.exit(130)
    except Exception as e:
        logger.exception(f"❌ Error inesperado: {e}")
        sys.exit(1)
