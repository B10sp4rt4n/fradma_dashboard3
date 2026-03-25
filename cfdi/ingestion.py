"""
Módulo de ingesta de datos CFDI a Neon PostgreSQL.

Este módulo maneja la inserción eficiente y segura de datos parseados
de CFDIs a la base de datos Neon, con deduplicación automática y manejo
robusto de errores.

Autor: Fradma Dashboard Team
Fecha: Febrero 2026
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from decimal import Decimal
import psycopg2
from psycopg2 import sql, extras
from psycopg2.extensions import connection

# Configurar logging
logger = logging.getLogger(__name__)


class NeonIngestion:
    """
    Clase para manejar la ingesta de datos CFDI a Neon PostgreSQL.
    
    Características:
    - Deduplicación automática por UUID
    - Transacciones ACID
    - Batch inserts eficientes
    - Manejo robusto de errores
    - Logging detallado
    """
    
    def __init__(self, connection_string: str):
        """
        Inicializa conexión a Neon.
        
        Args:
            connection_string: String de conexión PostgreSQL
                Ejemplo: "postgresql://user:pass@host:5432/dbname?sslmode=require"
        """
        self.connection_string = connection_string.strip()
        # Sanitizar: quitar prefijo psql y comillas
        if self.connection_string.lower().startswith("psql "):
            self.connection_string = self.connection_string[5:].strip()
        if (self.connection_string.startswith('"') and self.connection_string.endswith('"')) or \
           (self.connection_string.startswith("'") and self.connection_string.endswith("'")):
            self.connection_string = self.connection_string[1:-1]
        self.conn: Optional[connection] = None
        
    def __enter__(self):
        """Context manager - establece conexión."""
        self.connect()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager - cierra conexión."""
        self.close()
        
    def connect(self):
        """Establece conexión a Neon."""
        try:
            self.conn = psycopg2.connect(self.connection_string)
            logger.info("Conexión establecida a Neon PostgreSQL")
        except Exception as e:
            logger.error(f"Error conectando a Neon: {e}")
            raise
            
    def close(self):
        """Cierra conexión a Neon."""
        if self.conn:
            self.conn.close()
            logger.info("Conexión a Neon cerrada")
            
    def _uuid_exists(self, cursor, uuid: str) -> bool:
        """
        Verifica si un UUID ya existe en cfdi_ventas.
        
        Args:
            cursor: Cursor de psycopg2
            uuid: UUID del CFDI
            
        Returns:
            True si existe, False si no
        """
        cursor.execute(
            "SELECT 1 FROM cfdi_ventas WHERE uuid_sat = %s LIMIT 1",
            (uuid,)
        )
        return cursor.fetchone() is not None

    def _upsert_cliente(self, cursor, empresa_id: str, rfc: str,
                        nombre: str, uso_cfdi: str = '',
                        domicilio_fiscal: str = '',
                        regimen_fiscal: str = '',
                        fecha_emision=None, total=None) -> None:
        """
        Inserta o actualiza un cliente en clientes_master.
        Extrae datos del receptor del CFDI.
        """
        if not rfc or rfc == 'XAXX010101000':  # Público en general
            return

        cursor.execute("""
            INSERT INTO clientes_master (
                empresa_id, rfc, razon_social, domicilio_fiscal,
                total_ventas_historico, total_facturas,
                fecha_primera_venta, fecha_ultima_venta
            ) VALUES (
                %s, %s, %s, %s, COALESCE(%s, 0), 1, %s, %s
            )
            ON CONFLICT (empresa_id, rfc) DO UPDATE SET
                razon_social = COALESCE(EXCLUDED.razon_social, clientes_master.razon_social),
                domicilio_fiscal = COALESCE(EXCLUDED.domicilio_fiscal, clientes_master.domicilio_fiscal),
                total_ventas_historico = clientes_master.total_ventas_historico + COALESCE(EXCLUDED.total_ventas_historico, 0),
                total_facturas = clientes_master.total_facturas + 1,
                fecha_primera_venta = LEAST(clientes_master.fecha_primera_venta, EXCLUDED.fecha_primera_venta),
                fecha_ultima_venta = GREATEST(clientes_master.fecha_ultima_venta, EXCLUDED.fecha_ultima_venta),
                updated_at = NOW();
        """, (
            empresa_id, rfc, nombre, domicilio_fiscal or None,
            total, fecha_emision, fecha_emision
        ))

    def insert_venta(
        self,
        empresa_id: str,
        venta_data: Dict,
        skip_duplicates: bool = True
    ) -> Tuple[bool, Optional[str]]:
        """
        Inserta una factura de venta (CFDI) con sus conceptos y actualiza clientes.
        
        El parser produce un dict con:
          - Datos planos del comprobante (subtotal, total, moneda, etc.)
          - 'emisor': {rfc, nombre, regimen_fiscal}
          - 'receptor': {rfc, nombre, uso_cfdi, domicilio_fiscal_receptor, regimen_fiscal_receptor}
          - 'timbre': {uuid, fecha_timbrado}
          - 'conceptos': [{clave_prod_serv, no_identificacion, cantidad, ...}]
        
        Args:
            empresa_id: UUID de la empresa en tabla empresas
            venta_data: Diccionario con datos parseados del CFDI
            skip_duplicates: Si True, ignora CFDIs con UUID duplicado
            
        Returns:
            Tupla (éxito: bool, mensaje: str o None)
        """
        if not self.conn:
            raise RuntimeError("No hay conexión activa. Usa connect() o context manager.")
            
        cursor = self.conn.cursor()
        
        try:
            # Extraer sub-dicts del parser
            emisor = venta_data.get('emisor', {})
            receptor = venta_data.get('receptor', {})
            timbre = venta_data.get('timbre', {})

            # UUID del timbre fiscal (identificador único del CFDI)
            uuid_sat = timbre.get('uuid') or venta_data.get('uuid') or venta_data.get('uuid_sat')
            if not uuid_sat:
                return False, "UUID faltante en venta_data"
                
            if skip_duplicates and self._uuid_exists(cursor, uuid_sat):
                logger.info(f"UUID {uuid_sat} ya existe, saltando inserción")
                return True, f"UUID {uuid_sat} ya existe (duplicado)"
            
            # Mapear datos del parser → columnas reales del schema
            fecha_emision = venta_data.get('fecha') or venta_data.get('fecha_emision')
            fecha_timbrado = timbre.get('fecha_timbrado') or venta_data.get('fecha_timbrado')
            subtotal = venta_data.get('subtotal', Decimal('0'))
            descuento = venta_data.get('descuento', Decimal('0'))
            total = venta_data.get('total', Decimal('0'))
            # impuestos = total - subtotal + descuento (si no viene directo)
            impuestos     = venta_data.get('impuestos') or (total - subtotal + descuento)
            iva_retenido  = venta_data.get('iva_retenido',  Decimal('0'))
            isr_retenido  = venta_data.get('isr_retenido',  Decimal('0'))

            emisor_rfc = emisor.get('rfc') or venta_data.get('emisor_rfc', '')
            emisor_nombre = emisor.get('nombre') or venta_data.get('emisor_nombre', '')
            emisor_regimen = emisor.get('regimen_fiscal') or venta_data.get('emisor_regimen_fiscal', '')
            receptor_rfc = receptor.get('rfc') or venta_data.get('receptor_rfc', '')
            receptor_nombre = receptor.get('nombre') or venta_data.get('receptor_nombre', '')
            receptor_uso_cfdi = receptor.get('uso_cfdi') or venta_data.get('uso_cfdi', '')
            receptor_domicilio = receptor.get('domicilio_fiscal_receptor') or venta_data.get('receptor_domicilio_fiscal', '')
            receptor_regimen = receptor.get('regimen_fiscal_receptor') or venta_data.get('receptor_regimen_fiscal', '')

            exportacion = venta_data.get('exportacion', '01')
            es_exportacion = exportacion != '01'

            # 1) Insertar en cfdi_ventas (columnas reales del schema)
            insert_venta_sql = """
                INSERT INTO cfdi_ventas (
                    empresa_id, uuid_sat, serie, folio,
                    fecha_emision, fecha_timbrado,
                    emisor_rfc, emisor_nombre, emisor_regimen_fiscal,
                    receptor_rfc, receptor_nombre, receptor_uso_cfdi,
                    receptor_domicilio_fiscal, receptor_regimen_fiscal,
                    subtotal, descuento, impuestos, total,
                    moneda, tipo_cambio, tipo_comprobante,
                    metodo_pago, forma_pago, lugar_expedicion,
                    es_exportacion, xml_original,
                    iva_retenido, isr_retenido
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s
                ) RETURNING id
            """
            
            cursor.execute(insert_venta_sql, (
                empresa_id,
                uuid_sat,
                venta_data.get('serie', ''),
                venta_data.get('folio', ''),
                fecha_emision,
                fecha_timbrado,
                emisor_rfc,
                emisor_nombre,
                emisor_regimen,
                receptor_rfc,
                receptor_nombre,
                receptor_uso_cfdi,
                receptor_domicilio,
                receptor_regimen,
                subtotal,
                descuento,
                impuestos,
                total,
                venta_data.get('moneda', 'MXN'),
                venta_data.get('tipo_cambio', Decimal('1.0')),
                venta_data.get('tipo_de_comprobante') or venta_data.get('tipo_comprobante', 'I'),
                venta_data.get('metodo_pago', ''),
                venta_data.get('forma_pago', ''),
                venta_data.get('lugar_expedicion', ''),
                es_exportacion,
                venta_data.get('xml_original'),
                iva_retenido,
                isr_retenido,
            ))
            
            cfdi_id = cursor.fetchone()[0]
            
            # 2) Insertar conceptos (columnas reales del schema)
            conceptos = venta_data.get('conceptos', [])
            if conceptos:
                insert_conceptos_sql = """
                    INSERT INTO cfdi_conceptos (
                        cfdi_venta_id, clave_prod_serv, no_identificacion,
                        descripcion, cantidad, clave_unidad, unidad,
                        valor_unitario, importe, descuento, objeto_imp
                    ) VALUES %s
                """
                
                conceptos_values = [
                    (
                        cfdi_id,
                        c.get('clave_prod_serv', ''),
                        c.get('no_identificacion', ''),
                        c.get('descripcion', ''),
                        c.get('cantidad', 0),
                        c.get('clave_unidad', ''),
                        c.get('unidad', ''),
                        c.get('valor_unitario', 0),
                        c.get('importe', 0),
                        c.get('descuento', 0),
                        c.get('objeto_imp', '02')
                    )
                    for c in conceptos
                ]
                
                extras.execute_values(
                    cursor,
                    insert_conceptos_sql,
                    conceptos_values,
                    template="(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
                )

            # 3) Upsert cliente en clientes_master
            self._upsert_cliente(
                cursor, empresa_id,
                rfc=receptor_rfc,
                nombre=receptor_nombre,
                uso_cfdi=receptor_uso_cfdi,
                domicilio_fiscal=receptor_domicilio,
                regimen_fiscal=receptor_regimen,
                fecha_emision=fecha_emision,
                total=total
            )
            
            self.conn.commit()
            return True, f"CFDI {uuid_sat} insertado correctamente ({len(conceptos)} conceptos)"
            
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error insertando CFDI: {e}")
            return False, str(e)
            
        finally:
            cursor.close()
            
    def insert_ventas_batch(
        self,
        empresa_id: str,
        ventas_list: List[Dict],
        skip_duplicates: bool = True
    ) -> Dict[str, any]:
        """
        Inserta múltiples facturas en batch.
        
        Args:
            empresa_id: ID de la empresa
            ventas_list: Lista de diccionarios con datos parseados
            skip_duplicates: Si True, ignora CFDIs duplicados
            
        Returns:
            Diccionario con estadísticas:
            {
                'total': int,
                'insertados': int,
                'duplicados': int,
                'errores': int,
                'detalles_errores': List[Dict]
            }
            
        Ejemplo:
            >>> from cfdi.parser import parse_cfdi_batch
            >>> ventas = parse_cfdi_batch(xml_files)
            >>> ingestion = NeonIngestion(conn_string)
            >>> stats = ingestion.insert_ventas_batch(empresa_id=1, ventas_list=ventas)
            >>> print(f"Insertados: {stats['insertados']}/{stats['total']}")
        """
        stats = {
            'total': len(ventas_list),
            'insertados': 0,
            'duplicados': 0,
            'errores': 0,
            'detalles_errores': []
        }
        
        logger.info(f"Iniciando inserción batch de {stats['total']} CFDIs")
        
        for i, venta_data in enumerate(ventas_list, 1):
            uuid = venta_data.get('uuid', f'desconocido_{i}')
            
            try:
                success, msg = self.insert_venta(
                    empresa_id=empresa_id,
                    venta_data=venta_data,
                    skip_duplicates=skip_duplicates
                )
                
                if success:
                    if 'duplicado' in msg.lower():
                        stats['duplicados'] += 1
                    else:
                        stats['insertados'] += 1
                else:
                    stats['errores'] += 1
                    stats['detalles_errores'].append({
                        'uuid': uuid,
                        'error': msg
                    })
                    
            except Exception as e:
                stats['errores'] += 1
                stats['detalles_errores'].append({
                    'uuid': uuid,
                    'error': str(e)
                })
                logger.error(f"Error procesando CFDI {uuid}: {e}")
                
            # Log progreso cada 100 CFDIs
            if i % 100 == 0:
                logger.info(f"Progreso: {i}/{stats['total']} CFDIs procesados")
        
        logger.info(
            f"Batch completado: {stats['insertados']} insertados, "
            f"{stats['duplicados']} duplicados, {stats['errores']} errores"
        )
        
        return stats
        
    def insert_pago(
        self,
        empresa_id: str,
        pago_data: Dict,
        skip_duplicates: bool = True
    ) -> Tuple[bool, Optional[str]]:
        """
        Inserta un complemento de pago.
        
        Args:
            empresa_id: ID de la empresa
            pago_data: Diccionario con datos del complemento de pago
                Debe incluir: uuid_pago, cfdi_relacionados (lista)
            skip_duplicates: Si True, ignora pagos con UUID duplicado
            
        Returns:
            Tupla (éxito: bool, mensaje: str o None)
        """
        if not self.conn:
            raise RuntimeError("No hay conexión activa. Usa connect() o context manager.")
            
        cursor = self.conn.cursor()
        
        try:
            uuid_pago = pago_data.get('uuid_pago')
            if not uuid_pago:
                return False, "UUID de pago faltante"
            
            # Verificar duplicados
            if skip_duplicates:
                cursor.execute(
                    "SELECT 1 FROM cfdi_pagos WHERE uuid_pago = %s LIMIT 1",
                    (uuid_pago,)
                )
                if cursor.fetchone():
                    logger.info(f"UUID pago {uuid_pago} ya existe, saltando")
                    return True, f"UUID pago {uuid_pago} ya existe (duplicado)"
            
            # Insertar cada CFDI relacionado en el complemento de pago
            cfdi_relacionados = pago_data.get('cfdi_relacionados', [])
            insertados = 0
            
            for rel in cfdi_relacionados:
                # Buscar el cfdi_id correspondiente al UUID de la venta
                cursor.execute(
                    "SELECT id FROM cfdi_ventas WHERE uuid = %s AND empresa_id = %s LIMIT 1",
                    (rel.get('uuid_venta'), empresa_id)
                )
                result = cursor.fetchone()
                
                if not result:
                    logger.warning(
                        f"CFDI venta {rel.get('uuid_venta')} no encontrado, "
                        f"saltando pago relacionado"
                    )
                    continue
                    
                cfdi_id = result[0]
                
                insert_pago_sql = """
                    INSERT INTO cfdi_pagos (
                        empresa_id, cfdi_id, uuid_pago, fecha_pago,
                        forma_pago_p, moneda_p, tipo_cambio_p,
                        monto_pagado, monto_pagado_mxn, saldo_anterior,
                        saldo_insoluto, num_parcialidad
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                """
                
                cursor.execute(insert_pago_sql, (
                    empresa_id,
                    cfdi_id,
                    uuid_pago,
                    pago_data.get('fecha_pago'),
                    rel.get('forma_pago'),
                    rel.get('moneda', 'MXN'),
                    rel.get('tipo_cambio', Decimal('1.0')),
                    rel.get('monto_pagado'),
                    rel.get('monto_pagado_mxn'),
                    rel.get('saldo_anterior'),
                    rel.get('saldo_insoluto'),
                    rel.get('num_parcialidad')
                ))
                
                insertados += 1
            
            self.conn.commit()
            logger.info(
                f"Complemento de pago {uuid_pago} insertado: "
                f"{insertados} CFDIs relacionados"
            )
            return True, f"Pago {uuid_pago} insertado con {insertados} relaciones"
            
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error insertando pago {uuid_pago}: {e}")
            return False, str(e)
            
        finally:
            cursor.close()
            
    def get_empresa_stats(self, empresa_id: str) -> Dict:
        """
        Obtiene estadísticas de la empresa.
        
        Args:
            empresa_id: ID de la empresa
            
        Returns:
            Diccionario con estadísticas
        """
        if not self.conn:
            raise RuntimeError("No hay conexión activa.")
            
        cursor = self.conn.cursor()
        
        try:
            stats = {}
            
            # Contar CFDIs
            cursor.execute(
                "SELECT COUNT(*) FROM cfdi_ventas WHERE empresa_id = %s",
                (empresa_id,)
            )
            stats['total_cfdis'] = cursor.fetchone()[0]
            
            # Contar conceptos
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM cfdi_conceptos cc
                JOIN cfdi_ventas cv ON cc.cfdi_id = cv.id
                WHERE cv.empresa_id = %s
                """,
                (empresa_id,)
            )
            stats['total_conceptos'] = cursor.fetchone()[0]
            
            # Contar pagos
            cursor.execute(
                "SELECT COUNT(*) FROM cfdi_pagos WHERE empresa_id = %s",
                (empresa_id,)
            )
            stats['total_pagos'] = cursor.fetchone()[0]
            
            # Rango de fechas
            cursor.execute(
                """
                SELECT MIN(fecha_emision), MAX(fecha_emision)
                FROM cfdi_ventas
                WHERE empresa_id = %s
                """,
                (empresa_id,)
            )
            fecha_min, fecha_max = cursor.fetchone()
            stats['fecha_primer_cfdi'] = fecha_min
            stats['fecha_ultimo_cfdi'] = fecha_max
            
            # Total facturado
            cursor.execute(
                """
                SELECT SUM(total), moneda
                FROM cfdi_ventas
                WHERE empresa_id = %s
                GROUP BY moneda
                """,
                (empresa_id,)
            )
            stats['totales_por_moneda'] = {
                row[1]: float(row[0]) for row in cursor.fetchall()
            }
            
            return stats
            
        finally:
            cursor.close()


def verify_connection(connection_string: str) -> bool:
    """
    Verifica la conexión a Neon.
    
    Args:
        connection_string: String de conexión PostgreSQL
        
    Returns:
        True si la conexión es exitosa, False en caso contrario
    """
    try:
        # Sanitizar input
        cs = connection_string.strip()
        if cs.lower().startswith("psql "):
            cs = cs[5:].strip()
        if (cs.startswith('"') and cs.endswith('"')) or \
           (cs.startswith("'") and cs.endswith("'")):
            cs = cs[1:-1]

        conn = psycopg2.connect(cs)
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()
        logger.info(f"Conexión exitosa a PostgreSQL: {version[0]}")
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Error probando conexión: {e}")
        return False
