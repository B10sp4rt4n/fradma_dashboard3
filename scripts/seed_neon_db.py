"""Script para poblar la base de datos Neon con datos CFDI de ejemplo."""
import psycopg2
from psycopg2.extras import execute_values
import random
from datetime import datetime, timedelta
from decimal import Decimal
import uuid

CONN = 'postgresql://neondb_owner:npg_jn0JPIoE1bKz@ep-solitary-math-aimeehli-pooler.c-4.us-east-1.aws.neon.tech/neondb?sslmode=require'

random.seed(42)

conn = psycopg2.connect(CONN)
conn.autocommit = False
cur = conn.cursor()

print("Insertando datos de ejemplo...")

# 1. Empresa
empresa_id = str(uuid.uuid4())
cur.execute("""
    INSERT INTO empresas (id, razon_social, rfc, email, telefono, plan, industria, tamaño_empresa, status)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
""", (empresa_id, 'Distribuidora Fradma SA de CV', 'DFR260228ABC', 'admin@fradma.com',
      '5551234567', 'business', 'distribucion_ferreteria', '50-200', 'activo'))
print(f"✓ Empresa: {empresa_id[:8]}...")

# 2. Clientes
clientes = [
    ('Ferretería Industrial del Norte SA', 'FIN850101AB1', 'distribuidor', 'A'),
    ('Construcciones Monterrey SA de CV', 'CMO900215XY2', 'mayorista', 'A'),
    ('Plásticos y Derivados SA', 'PYD951030ZW3', 'distribuidor', 'A'),
    ('Grupo Hidráulico Central SA de CV', 'GHC880520KL4', 'mayorista', 'B'),
    ('Eléctricos y Cables del Bajío SA', 'ECB920710MN5', 'distribuidor', 'B'),
    ('Pinturas Profesionales SA de CV', 'PPR870305PQ6', 'minorista', 'B'),
    ('Seguridad Industrial Total SA', 'SIT940815RS7', 'distribuidor', 'B'),
    ('Materiales García Hermanos SA', 'MGH910425TU8', 'minorista', 'C'),
    ('Químicos Industriales del Norte', 'QIN960110VW9', 'mayorista', 'C'),
    ('Tornillería Express SA de CV', 'TEX980620XY0', 'minorista', 'C'),
    ('Gobierno del Estado de Nuevo León', 'GEN840101AB1', 'gobierno', 'A'),
    ('Aceros y Metales del Pacífico SA', 'AMP870315CD2', 'distribuidor', 'B'),
    ('Soldaduras y Equipos SA de CV', 'SEQ910925EF3', 'minorista', 'C'),
    ('Herramientas Pro SA de CV', 'HPR950810GH4', 'distribuidor', 'B'),
    ('Distribuidora de Válvulas SA', 'DVA880625IJ5', 'mayorista', 'C'),
]

clientes_rows = []
for nombre, rfc, tipo, segmento in clientes:
    clientes_rows.append((str(uuid.uuid4()), empresa_id, rfc, nombre, tipo, segmento, True))

execute_values(cur, """
    INSERT INTO clientes_master (id, empresa_id, rfc, razon_social, tipo_cliente, segmento, is_activo)
    VALUES %s
""", clientes_rows)
print(f"✓ {len(clientes)} clientes")

# 3. Facturas + Conceptos + Pagos
lineas = ['ferreteria_herramientas', 'ferreteria_industrial', 'materiales_construccion',
          'plasticos_industriales', 'equipos_hidraulicos', 'equipos_electricos',
          'pinturas_recubrimientos', 'seguridad_industrial']
vendedores = ['Carlos Mendoza', 'Ana García', 'Roberto Sánchez', 'María López',
              'José Hernández', 'Laura Martínez', 'Fernando Ruiz']
productos = [
    ('Tornillo hexagonal galvanizado 1/2"', '27112900', 100, 0.85, 5.50),
    ('Tuerca hexagonal zincada 3/8"', '27112900', 200, 0.45, 2.80),
    ('Cemento Portland CPC 30R 50kg', '30111601', 50, 155.00, 195.00),
    ('Varilla corrugada 3/8" 12m', '30102400', 20, 85.00, 125.00),
    ('Tubo PVC hidráulico 2" 6m', '40171502', 30, 65.00, 95.00),
    ('Cable THW calibre 12 100m', '26121600', 15, 450.00, 680.00),
    ('Pintura vinílica blanca 19L', '31211501', 10, 580.00, 850.00),
    ('Casco de seguridad industrial', '46181504', 25, 120.00, 195.00),
    ('Guantes de nitrilo caja 100', '46181504', 40, 180.00, 290.00),
    ('Martillo bola 16oz', '27111701', 8, 95.00, 165.00),
    ('Llave combinada juego 12pz', '27111701', 5, 350.00, 550.00),
    ('Bomba centrífuga 1HP', '40141700', 3, 2800.00, 4500.00),
    ('Válvula esférica 1"', '40141700', 12, 180.00, 310.00),
    ('Soldadura 6013 3/32" 5kg', '23271800', 15, 195.00, 320.00),
    ('Disco corte metal 4 1/2"', '23271800', 50, 18.00, 35.00),
    ('Barniz poliuretano 4L', '31211501', 8, 420.00, 650.00),
    ('Arena sílica 25kg', '11101700', 30, 45.00, 75.00),
    ('Resina epóxica 1gal', '12161800', 6, 850.00, 1350.00),
    ('Interruptor termomagnético 2x30A', '26121600', 10, 280.00, 450.00),
    ('Botas industriales punta acero', '46181604', 8, 650.00, 980.00),
]

start_date = datetime(2024, 8, 1)
days_range = (datetime(2026, 2, 28) - start_date).days

ventas_rows = []
conceptos_rows = []
pagos_rows = []

for i in range(500):
    fecha = start_date + timedelta(days=random.randint(0, days_range))
    cliente = random.choice(clientes)
    vendedor = random.choice(vendedores)
    linea = random.choice(lineas)

    moneda = 'USD' if random.random() < 0.15 else 'MXN'
    tipo_cambio = round(random.uniform(17.0, 20.5), 4) if moneda == 'USD' else 1.0

    n_conceptos = random.randint(1, 5)
    seleccion = random.sample(productos, min(n_conceptos, len(productos)))

    subtotal = 0.0
    venta_id = str(uuid.uuid4())
    uuid_sat = str(uuid.uuid4())
    serie = random.choice(['A', 'B', 'F'])
    folio = str(1000 + i)
    metodo = random.choice(['PUE', 'PPD'])
    forma = random.choice(['01', '03', '04', '99'])

    conceptos_temp = []
    for prod in seleccion:
        nombre_prod, clave_sat, max_qty, p_min, p_max = prod
        cantidad = random.randint(1, max_qty)
        precio = round(random.uniform(p_min, p_max), 2)
        importe = round(cantidad * precio, 2)
        subtotal += importe
        conceptos_rows.append((
            str(uuid.uuid4()), venta_id, clave_sat, f'SKU-{random.randint(1000,9999)}',
            nombre_prod, cantidad, 'H87', 'Pieza', precio, importe, 0, linea
        ))

    descuento = round(subtotal * random.uniform(0, 0.05), 2)
    base = subtotal - descuento
    iva = round(base * 0.16, 2)
    total = round(base + iva, 2)

    ventas_rows.append((
        venta_id, empresa_id, uuid_sat, serie, folio,
        fecha, fecha + timedelta(minutes=random.randint(1, 60)),
        'DFR260228ABC', 'Distribuidora Fradma SA de CV', '601',
        cliente[1], cliente[0], 'G03',
        subtotal, descuento, iva, total,
        moneda, tipo_cambio, 'I', metodo, forma, '64000',
        linea, vendedor, moneda == 'USD'
    ))

    # Pagos para PPD
    if metodo == 'PPD' and random.random() < 0.6:
        dias_pago = random.randint(15, 90)
        parcialidades = random.randint(1, 3)
        monto_parc = round(total / parcialidades, 2)
        for parc in range(1, parcialidades + 1):
            fecha_parc = fecha + timedelta(days=dias_pago + (parc - 1) * 30)
            saldo_ant = round(total - monto_parc * (parc - 1), 2)
            saldo_ins = max(0, round(saldo_ant - monto_parc, 2))
            pagos_rows.append((
                str(uuid.uuid4()), empresa_id, str(uuid.uuid4()), uuid_sat,
                serie, folio, fecha_parc, '03', moneda, tipo_cambio,
                monto_parc, saldo_ant, saldo_ins, parc, dias_pago + (parc - 1) * 30
            ))

print(f"   Preparados: {len(ventas_rows)} ventas, {len(conceptos_rows)} conceptos, {len(pagos_rows)} pagos")

# Batch insert
print("   Insertando ventas...")
execute_values(cur, """
    INSERT INTO cfdi_ventas (
        id, empresa_id, uuid_sat, serie, folio,
        fecha_emision, fecha_timbrado,
        emisor_rfc, emisor_nombre, emisor_regimen_fiscal,
        receptor_rfc, receptor_nombre, receptor_uso_cfdi,
        subtotal, descuento, impuestos, total,
        moneda, tipo_cambio, tipo_comprobante, metodo_pago, forma_pago, lugar_expedicion,
        linea_negocio, vendedor_asignado, es_exportacion
    ) VALUES %s
""", ventas_rows, page_size=100)

print("   Insertando conceptos...")
execute_values(cur, """
    INSERT INTO cfdi_conceptos (
        id, cfdi_venta_id, clave_prod_serv, no_identificacion,
        descripcion, cantidad, clave_unidad, unidad, valor_unitario, importe, descuento, categoria
    ) VALUES %s
""", conceptos_rows, page_size=200)

print("   Insertando pagos...")
execute_values(cur, """
    INSERT INTO cfdi_pagos (
        id, empresa_id, uuid_complemento, cfdi_venta_uuid,
        serie, folio, fecha_pago, forma_pago, moneda, tipo_cambio,
        monto_pagado, saldo_anterior, saldo_insoluto, num_parcialidad, dias_credito
    ) VALUES %s
""", pagos_rows, page_size=100)

conn.commit()
print("✅ Commit exitoso")

# Verificar
for t in ['empresas', 'cfdi_ventas', 'cfdi_conceptos', 'cfdi_pagos', 'clientes_master']:
    cur.execute(f'SELECT COUNT(*) FROM {t}')
    print(f"   {t}: {cur.fetchone()[0]}")

cur.execute("SELECT MIN(fecha_emision)::date, MAX(fecha_emision)::date FROM cfdi_ventas")
fmin, fmax = cur.fetchone()
print(f"   📅 Rango: {fmin} a {fmax}")

cur.execute("SELECT moneda, COUNT(*), ROUND(SUM(total)::numeric, 2) FROM cfdi_ventas GROUP BY moneda")
for m, c, t in cur.fetchall():
    print(f"   💰 {m}: {c} facturas, ${t:,.2f}")

cur.close()
conn.close()
print("\n✅ Base de datos lista para el Asistente de Datos")
