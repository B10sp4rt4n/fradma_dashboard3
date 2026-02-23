# 🏗️ Arquitectura Escalable - Motor de Análisis Multi-Usuario

> **Objetivo**: Diseñar sistema desacoplado que soporte **20-50 usuarios concurrentes**  
> **Enfoque**: Separación Frontend/Backend con workers asíncronos  
> **Baseline actual**: 3-5 usuarios concurrentes (Streamlit síncrono)

---

## 📊 ANÁLISIS DE BOTTLENECKS ACTUALES

### 🔴 Cuellos de Botella Identificados

```python
# PROBLEMA 1: Operaciones síncronas bloqueantes en Streamlit
# Localización: main/kpi_cpc.py, vendedores_cxc.py, ytd_lineas.py

# Operación pesada en hilo principal:
df_cruce = df_ventas.merge(df_cxc, on='cliente')  # 10K+ rows
df.groupby(['vendedor', 'producto']).apply(lambda g: calculo_complejo(g))  # O(n^2)
df['score'] = df.apply(calcular_score_fila, axis=1)  # Row-by-row, sin vectorización

# IMPACTO: 2-5 segundos por dashboard
# CONCURRENCIA: Cada usuario bloquea el GIL de Python
```

```python
# PROBLEMA 2: Cache en memoria (st.session_state)
# Localización: utils/cache_helper.py

st.session_state['cache_key'] = resultado  # ❌ Por navegador, no compartido
# User A calcula métricas → User B recalcula las mismas
# Sin persistencia → restart = pérdida total de cache

# IMPACTO: Duplicación de cálculos entre usuarios
# CAPACIDAD: RAM limitada (~2GB por instancia Streamlit)
```

```python
# PROBLEMA 3: Carga de Excel síncrona
# Localización: app.py líneas 230-350

@st.cache_data(ttl=300)
def cargar_excel_puro(archivo_bytes):
    xls = pd.ExcelFile(archivo_bytes)  # Bloqueante
    df = xls.parse(sheet_name)  # Bloqueante
    df = normalizar_columnas(df)  # CPU-intensive
    return df

# IMPACTO: 1-3 segundos bloqueando UI
# CONCURRENCIA: 5 usuarios subiendo archivos = 15 segundos de bloqueo acumulado
```

### ⚙️ Benchmark de Performance (10K registros)

```bash
# Ejecutar: python scripts/profile_performance.py

RESULTADOS:
├─ calcular_dias_overdue:      ~50ms   ✅ Aceptable
├─ preparar_datos_cxc:         ~200ms  ⚠️ Optimizable
├─ calcular_metricas_basicas:  ~50ms   ✅ Aceptable
├─ groupby + apply (complejo): ~2000ms 🔴 CRÍTICO
└─ Renderizado Plotly:         ~800ms  ⚠️ Optimizable

TOTAL PIPELINE: ~3.1 segundos por dashboard
THROUGHPUT: 3,200 registros/segundo (pandas puro)
```

### 📉 Capacidad Actual (Arquitectura Síncrona)

```
CONFIGURACIÓN BASE:
- Servidor: 4 vCPUs, 8GB RAM
- Streamlit: 1 proceso, GIL de Python
- Cache: session_state (memoria local)

CAPACIDAD TEÓRICA:
- Usuarios simultáneos visualizando: 10-15 (bajo CPU)
- Usuarios simultáneos calculando: 2-3 (GIL bottleneck)
- Tiempo de respuesta p95: 5-8 segundos

LIMITACIONES:
❌ No escala horizontalmente (session_state local)
❌ No hay cola de trabajos (FIFO degrada a todos)
❌ Sin priorización (admin espera igual que viewer)
❌ Sin fallover (1 crash = todos desconectados)
```

---

## 🚀 ARQUITECTURA DESACOPLADA PROPUESTA

### 🎯 Principios de Diseño

1. **Separación de responsabilidades**: Frontend solo renderiza, Backend calcula
2. **Asincronía**: Trabajos pesados en workers independientes
3. **Cache distribuido**: Redis compartido entre instancias
4. **Escalamiento horizontal**: Agregar workers sin tocar frontend
5. **Resiliencia**: Cola de mensajes para retry automático

---

## 📐 Diagrama de Arquitectura

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CAPA DE USUARIO                              │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  FRONTEND: Streamlit (Múltiples Instancias)                         │
│  ├─ app.py (UI + manejo de estado)                                  │
│  ├─ Login/Auth (JWT, roles)                                         │
│  ├─ Renderizado de dashboards (solo visualización)                  │
│  └─ API client para comunicación con backend                        │
│                                                                       │
│  DEPLOYMENT: Docker Swarm / K8s (escalamiento horizontal)            │
│  ESCALADO: 2-5 replicas según carga                                 │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼ HTTP/WebSocket
┌─────────────────────────────────────────────────────────────────────┐
│  LOAD BALANCER: Nginx / Traefik                                     │
│  ├─ Round-robin entre frontends                                     │
│  ├─ Sticky sessions (WebSocket)                                     │
│  └─ Health checks                                                   │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  BACKEND API: FastAPI (Stateless)                                   │
│  ├─ Endpoints REST:                                                 │
│  │   POST /api/calcular-cxc                                         │
│  │   POST /api/calcular-ytd                                         │
│  │   GET  /api/resultados/{job_id}                                  │
│  │   POST /api/upload-excel                                         │
│  │                                                                   │
│  ├─ Validación y autenticación (JWT)                                │
│  ├─ Encolamiento de trabajos pesados                                │
│  └─ Consulta de resultados cacheados                                │
│                                                                       │
│  DEPLOYMENT: Docker + Gunicorn (worker processes)                   │
│  ESCALADO: 3-8 workers según CPU                                    │
└─────────────────────────────────────────────────────────────────────┘
            │                                          │
            │ Publish Job                              │ Query Cache
            ▼                                          ▼
┌──────────────────────────┐            ┌──────────────────────────────┐
│  COLA DE MENSAJES        │            │  CACHE DISTRIBUIDO           │
│  (Redis + RQ/Celery)     │            │  (Redis)                     │
│                          │            │                              │
│  ├─ Queue: high_priority │            │  ├─ Métricas CxC             │
│  ├─ Queue: normal        │            │  ├─ YTD calculado            │
│  └─ Queue: low_priority  │            │  ├─ DataFrames procesados    │
│                          │            │  └─ TTL: 5-30 min            │
│  TTL Jobs: 1 hora        │            │                              │
└──────────────────────────┘            │  CAPACIDAD: 4GB RAM          │
            │                            └──────────────────────────────┘
            │ Consume                                  ▲
            ▼                                          │ Write/Read
┌──────────────────────────────────────────────────────────────────────┐
│  WORKERS: Python (Async/Parallel)                                    │
│  ├─ worker_cxc.py     → Cálculos de CxC                             │
│  ├─ worker_ventas.py  → Análisis de ventas                          │
│  ├─ worker_excel.py   → Procesamiento de archivos                   │
│  └─ worker_ia.py      → Análisis con OpenAI (rate-limited)          │
│                                                                       │
│  EJECUCIÓN:                                                          │
│  ├─ Pandas vectorizado (multicore)                                  │
│  ├─ Numpy acelerado                                                 │
│  └─ Retry automático en fallos                                      │
│                                                                       │
│  DEPLOYMENT: Procesos independientes (supervisor/systemd)            │
│  ESCALADO: 4-10 workers según carga                                 │
└──────────────────────────────────────────────────────────────────────┘
                                │
                                ▼ Read/Write
┌──────────────────────────────────────────────────────────────────────┐
│  BASE DE DATOS: PostgreSQL                                           │
│  ├─ Tablas:                                                          │
│  │   users (autenticación)                                           │
│  │   ventas (historización)                                          │
│  │   cxc (historización)                                             │
│  │   audit_log (quién vio qué)                                       │
│  │                                                                    │
│  ├─ Índices optimizados (tenant_id, fecha, vendedor)                │
│  └─ Particionamiento por año                                         │
│                                                                       │
│  DEPLOYMENT: PostgreSQL 15 + replicación                             │
│  CAPACIDAD: Millones de registros                                    │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 🛠️ IMPLEMENTACIÓN TÉCNICA

### **1. Backend API (FastAPI)**

```python
# api/main.py

from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.security import HTTPBearer
from redis import Redis
from rq import Queue
import pandas as pd
from typing import Optional
import hashlib

app = FastAPI(title="FRADMA Analytics API", version="2.0")
redis_conn = Redis(host='redis', port=6379, db=0)
queue_high = Queue('high', connection=redis_conn)
queue_normal = Queue('normal', connection=redis_conn)

security = HTTPBearer()

# ============================================================================
# ENDPOINT: Calcular Métricas de CxC (Asíncrono)
# ============================================================================

@app.post("/api/calcular-cxc")
async def calcular_cxc(
    archivo_id: str,
    usuario: dict = Depends(verificar_token)
):
    """
    Encola trabajo de cálculo de métricas CxC.
    
    Flujo:
    1. Validar acceso del usuario
    2. Verificar si resultado ya existe en cache
    3. Si no, encolar trabajo en RQ
    4. Retornar job_id para polling
    """
    
    # Generar cache key basado en archivo + filtros
    cache_key = f"cxc_metricas:{archivo_id}:{usuario['id']}"
    
    # Verificar cache
    resultado_cache = redis_conn.get(cache_key)
    if resultado_cache:
        return {
            "status": "completed",
            "job_id": None,
            "resultado": json.loads(resultado_cache),
            "cache_hit": True
        }
    
    # Encolar trabajo
    from workers.worker_cxc import calcular_metricas_cxc_worker
    
    job = queue_high.enqueue(
        calcular_metricas_cxc_worker,
        args=(archivo_id, usuario['id']),
        job_timeout=300,  # 5 minutos max
        result_ttl=3600,  # Mantener resultado 1 hora
        description=f"CxC para usuario {usuario['email']}"
    )
    
    return {
        "status": "queued",
        "job_id": job.id,
        "estimated_time": 10,  # segundos
        "position_in_queue": len(queue_high)
    }


@app.get("/api/resultados/{job_id}")
async def obtener_resultado(
    job_id: str,
    usuario: dict = Depends(verificar_token)
):
    """
    Consulta estado de trabajo encolado.
    
    Estados posibles:
    - queued: Esperando en cola
    - started: Ejecutándose
    - finished: Completado con éxito
    - failed: Error
    """
    from rq.job import Job
    
    try:
        job = Job.fetch(job_id, connection=redis_conn)
        
        if job.is_finished:
            return {
                "status": "completed",
                "resultado": job.result,
                "duration": job.ended_at - job.started_at
            }
        elif job.is_failed:
            return {
                "status": "failed",
                "error": str(job.exc_info)
            }
        elif job.is_started:
            return {
                "status": "running",
                "progress": job.meta.get('progress', 0)
            }
        else:
            return {
                "status": "queued",
                "position": job.get_position()
            }
    
    except Exception as e:
        raise HTTPException(status_code=404, detail="Job no encontrado")


# ============================================================================
# ENDPOINT: Subir y Procesar Excel
# ============================================================================

@app.post("/api/upload-excel")
async def upload_excel(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    usuario: dict = Depends(verificar_token)
):
    """
    Procesa archivo Excel en background.
    
    Flujo:
    1. Guardar archivo temporalmente en S3/local
    2. Encolar procesamiento (detección de formato, normalización)
    3. Retornar archivo_id para consultas posteriores
    """
    
    # Validar tamaño (max 50MB)
    if file.size > 50 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Archivo muy grande (max 50MB)")
    
    # Guardar en storage
    archivo_id = hashlib.sha256(f"{usuario['id']}{file.filename}".encode()).hexdigest()[:16]
    archivo_path = f"uploads/{usuario['id']}/{archivo_id}.xlsx"
    
    # Aquí guardarías en S3 o filesystem compartido
    # await save_to_storage(file, archivo_path)
    
    # Encolar procesamiento
    from workers.worker_excel import procesar_excel_worker
    
    job = queue_normal.enqueue(
        procesar_excel_worker,
        args=(archivo_path, archivo_id),
        job_timeout=600
    )
    
    return {
        "archivo_id": archivo_id,
        "job_id": job.id,
        "filename": file.filename
    }
```

---

### **2. Workers Asíncronos (RQ)**

```python
# workers/worker_cxc.py

import pandas as pd
import redis
from rq import get_current_job
from utils.cxc_helper import preparar_datos_cxc, calcular_metricas_basicas
from utils.data_normalizer import normalizar_columnas
import json

def calcular_metricas_cxc_worker(archivo_id: str, user_id: str):
    """
    Worker para cálculos pesados de CxC.
    
    Ventajas:
    - No bloquea UI
    - Puede usar múltiples cores (sin GIL)
    - Retry automático en fallos
    - Progress tracking
    """
    
    job = get_current_job()
    redis_conn = redis.Redis(host='redis', port=6379, db=0)
    
    try:
        # 1. Cargar datos desde storage
        job.meta['progress'] = 10
        job.save_meta()
        
        archivo_path = f"uploads/{user_id}/{archivo_id}.xlsx"
        df = pd.read_excel(archivo_path)
        
        # 2. Normalizar columnas
        job.meta['progress'] = 30
        job.save_meta()
        
        df = normalizar_columnas(df)
        
        # 3. Preparar datos CxC
        job.meta['progress'] = 50
        job.save_meta()
        
        df_prep, df_np, mask_pagado = preparar_datos_cxc(df)
        
        # 4. Calcular métricas (operación pesada)
        job.meta['progress'] = 80
        job.save_meta()
        
        metricas = calcular_metricas_basicas(df_np)
        
        # Agregar análisis por vendedor (groupby pesado)
        metricas['por_vendedor'] = (
            df_np.groupby('vendedor')
            .agg({
                'saldo_adeudado': 'sum',
                'dias_overdue': 'mean',
                'deudor': 'nunique'
            })
            .to_dict('index')
        )
        
        # 5. Guardar en cache (Redis)
        job.meta['progress'] = 95
        job.save_meta()
        
        cache_key = f"cxc_metricas:{archivo_id}:{user_id}"
        redis_conn.setex(
            cache_key,
            1800,  # 30 minutos TTL
            json.dumps(metricas, default=str)
        )
        
        job.meta['progress'] = 100
        job.save_meta()
        
        return {
            "success": True,
            "metricas": metricas,
            "registros_procesados": len(df),
            "cache_key": cache_key
        }
    
    except Exception as e:
        # Log del error
        logger.error(f"Error en worker_cxc: {e}", exc_info=True)
        raise


# ============================================================================
# SUPERVISOR DE WORKERS
# ============================================================================

# supervisord.conf
"""
[program:worker_cxc_high]
command=rq worker high --url redis://redis:6379
numprocs=2
process_name=%(program_name)s_%(process_num)02d
autostart=true
autorestart=true

[program:worker_cxc_normal]
command=rq worker normal --url redis://redis:6379
numprocs=4
process_name=%(program_name)s_%(process_num)02d
autostart=true
autorestart=true
"""
```

---

### **3. Frontend Streamlit (Cliente API)**

```python
# app.py (MODIFICADO)

import streamlit as st
import requests
import time
from datetime import datetime

API_BASE_URL = "http://backend-api:8000/api"

def obtener_token():
    """Obtiene JWT del usuario autenticado"""
    return st.session_state.get('auth_token')

def calcular_cxc_async(archivo):
    """
    Inicia cálculo asíncrono de CxC.
    
    Flujo:
    1. Subir archivo → obtener archivo_id
    2. Solicitar cálculo → obtener job_id
    3. Polling de status hasta completar
    4. Renderizar resultados
    """
    
    # Paso 1: Subir archivo
    with st.spinner("📤 Subiendo archivo..."):
        files = {'file': archivo}
        headers = {'Authorization': f'Bearer {obtener_token()}'}
        
        response = requests.post(
            f"{API_BASE_URL}/upload-excel",
            files=files,
            headers=headers,
            timeout=60
        )
        
        if response.status_code != 200:
            st.error("Error al subir archivo")
            return
        
        archivo_id = response.json()['archivo_id']
    
    # Paso 2: Solicitar cálculo
    response = requests.post(
        f"{API_BASE_URL}/calcular-cxc",
        json={'archivo_id': archivo_id},
        headers=headers
    )
    
    data = response.json()
    
    if data.get('cache_hit'):
        # Resultado inmediato desde cache
        st.success("⚡ Resultados obtenidos desde cache")
        renderizar_dashboard_cxc(data['resultado'])
        return
    
    # Paso 3: Polling de status
    job_id = data['job_id']
    progreso = st.progress(0)
    status_text = st.empty()
    
    while True:
        response = requests.get(
            f"{API_BASE_URL}/resultados/{job_id}",
            headers=headers
        )
        
        resultado = response.json()
        status = resultado['status']
        
        if status == 'completed':
            progreso.progress(100)
            status_text.success("✅ Cálculo completado")
            renderizar_dashboard_cxc(resultado['resultado'])
            break
        
        elif status == 'failed':
            st.error(f"❌ Error: {resultado['error']}")
            break
        
        elif status == 'running':
            progress_pct = resultado.get('progress', 0)
            progreso.progress(progress_pct)
            status_text.info(f"⏳ Procesando... {progress_pct}%")
        
        else:  # queued
            position = resultado.get('position', 0)
            status_text.info(f"⏳ En cola (posición {position})")
        
        time.sleep(1)  # Polling cada segundo


def renderizar_dashboard_cxc(metricas):
    """
    Renderiza dashboard de CxC con datos pre-calculados.
    
    IMPORTANTE: Frontend solo visualiza, NO calcula.
    """
    
    st.subheader("📊 Métricas de Cuentas por Cobrar")
    
    col1, col2, col3 = st.columns(3)
    
    col1.metric(
        "Total Adeudado",
        f"${metricas['total_adeudado']:,.0f}"
    )
    
    col2.metric(
        "Cartera Vencida",
        f"{metricas['pct_vencida']:.1f}%",
        delta=f"-{metricas['delta_mes_anterior']:.1f}%" if 'delta_mes_anterior' in metricas else None
    )
    
    col3.metric(
        "Días Promedio",
        f"{metricas['dias_promedio']:.0f}",
        delta=f"+{metricas['delta_dias']:.0f}" if 'delta_dias' in metricas else None
    )
    
    # Gráficos (datos ya vienen procesados)
    st.plotly_chart(crear_grafico_antiguedad(metricas))
```

---

## 📈 CAPACIDAD DEL SISTEMA DESACOPLADO

### **Configuración de Referencia**

```yaml
# docker-compose.yml

version: '3.8'

services:
  # Frontend: Escalamiento horizontal
  streamlit:
    image: fradma/frontend:2.0
    deploy:
      replicas: 3  # 3 instancias
      resources:
        limits:
          cpus: '0.5'
          memory: 512M
    environment:
      - API_BACKEND_URL=http://backend:8000
  
  # Backend API: Workers de Gunicorn
  backend:
    image: fradma/backend:2.0
    deploy:
      replicas: 2
      resources:
        limits:
          cpus: '2'
          memory: 2G
    command: gunicorn -w 4 -k uvicorn.workers.UvicornWorker api.main:app
  
  # Workers de cálculo: Procesos independientes
  worker_high:
    image: fradma/workers:2.0
    deploy:
      replicas: 2
      resources:
        limits:
          cpus: '2'
          memory: 4G
    command: rq worker high --url redis://redis:6379
  
  worker_normal:
    image: fradma/workers:2.0
    deploy:
      replicas: 4
      resources:
        limits:
          cpus: '1'
          memory: 2G
    command: rq worker normal --url redis://redis:6379
  
  # Cache distribuido
  redis:
    image: redis:7-alpine
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 4G
    command: redis-server --maxmemory 4gb --maxmemory-policy allkeys-lru
  
  # Base de datos
  postgres:
    image: postgres:15
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
```

### **Cálculo de Capacidad (Base: 16 vCPUs, 32GB RAM)**

```
┌──────────────────────────────────────────────────────────────────────┐
│  DISTRIBUCIÓN DE RECURSOS                                            │
├──────────────────────────────────────────────────────────────────────┤
│  Streamlit (3 replicas):     3 × 0.5 CPU = 1.5 vCPU, 1.5GB RAM      │
│  Backend API (2 replicas):   2 × 2 CPU   = 4 vCPU, 4GB RAM          │
│  Workers High (2 replicas):  2 × 2 CPU   = 4 vCPU, 8GB RAM          │
│  Workers Normal (4 replicas): 4 × 1 CPU  = 4 vCPU, 8GB RAM          │
│  Redis:                      1 CPU, 4GB RAM                          │
│  PostgreSQL:                 2 CPU, 4GB RAM                          │
├──────────────────────────────────────────────────────────────────────┤
│  TOTAL:                      16.5 vCPU, 29.5GB RAM                   │
└──────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│  CAPACIDAD DE USUARIOS CONCURRENTES                                  │
├──────────────────────────────────────────────────────────────────────┤
│  ESCENARIO 1: Solo visualización (dashboards ya cacheados)          │
│  └─ Frontend handle: 50-100 usuarios                                 │
│      Bottleneck: Nginx/LB                                            │
│      Latencia: <200ms                                                │
│                                                                       │
│  ESCENARIO 2: Usuarios calculando activamente                        │
│  └─ Workers High (prioridad alta): 2 trabajos simultáneos            │
│  └─ Workers Normal: 4 trabajos simultáneos                           │
│  └─ Throughput: ~20 cálculos/minuto (3s cada uno)                   │
│  └─ Cola: 100+ trabajos sin degradación                             │
│                                                                       │
│  ESCENARIO 3: Mix realista (80% view, 20% calc)                     │
│  └─ Usuarios concurrentes: 30-50                                     │
│  └─ Cola promedio: <5 trabajos                                      │
│  └─ Tiempo de espera p95: <10 segundos                              │
│                                                                       │
│  ESCENARIO 4: Pico de tráfico (todos calculando)                    │
│  └─ Queue capacity: 200 trabajos                                    │
│  └─ Degradación graceful (TTL en cola)                              │
│  └─ Auto-scaling de workers: +2-4 replicas                          │
└──────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│  OPTIMIZACIONES CRÍTICAS                                             │
├──────────────────────────────────────────────────────────────────────┤
│  1. Cache Hit Rate: 70-80% (Redis compartido)                        │
│     └─ Si 8 usuarios consultan mismo período → 7 cache hits         │
│     └─ Reducción de carga: 8x                                       │
│                                                                       │
│  2. Priorización de Colas:                                           │
│     └─ Admin/Analyst → queue:high (2 workers dedicados)             │
│     └─ Viewer → queue:normal (4 workers)                            │
│     └─ IA análisis → queue:low (procesamiento nocturno)             │
│                                                                       │
│  3. Vectorización Pandas:                                            │
│     └─ Reemplazar .apply() → operaciones nativas                    │
│     └─ Ganancia: 10-100x en groupby complejos                       │
│                                                                       │
│  4. Compresión de Resultados:                                        │
│     └─ JSON → MessagePack (50% menos memoria)                       │
│     └─ DataFrame → Parquet (10x compresión)                         │
└──────────────────────────────────────────────────────────────────────┘
```

### **Benchmark de Performance Esperada**

```python
# ARQUITECTURA ACTUAL (Síncrona)
Tiempo de respuesta (cálculo CxC, 10K registros):
├─ Mejor caso (cache local):     100ms
├─ Caso típico (sin cache):      3,100ms
└─ Peor caso (5 usuarios):       15,000ms (cola serializada)

Usuarios concurrentes:            3-5

# ARQUITECTURA DESACOPLADA (Asíncrona)
Tiempo de respuesta (cálculo CxC, 10K registros):
├─ Mejor caso (cache Redis):     50ms (hit rate 70%)
├─ Caso típico (cálculo async):  3,500ms (incluye queue + network)
└─ Peor caso (cola llena):       10,000ms (pero UI no bloquea)

Usuarios concurrentes:            30-50

GANANCIA NETA: 10x en concurrencia
```

---

## 🛠️ PLAN DE IMPLEMENTACIÓN (3-4 semanas)

### **Semana 1: Infraestructura Base**

```bash
# Día 1-2: Backend API
✅ Crear FastAPI app básica
✅ Endpoints REST (upload, calcular, resultados)
✅ JWT autenticación
✅ Dockerizar backend

# Día 3-4: Redis + RQ
✅ Configurar Redis
✅ Implementar colas (high, normal, low)
✅ Workers básicos (calcular_cxc_worker)

# Día 5: Testing
✅ Tests de integración API + Workers
✅ Benchmark de throughput
```

### **Semana 2: Migración de Lógica**

```bash
# Día 1-3: Migrar cálculos a workers
✅ worker_cxc.py (60% del código de kpi_cpc.py)
✅ worker_ventas.py (main_kpi, ytd_lineas)
✅ worker_excel.py (carga y normalización)

# Día 4-5: Optimización
✅ Vectorizar operaciones .apply()
✅ Implementar batching de queries
✅ Profiling y optimización de bottlenecks
```

### **Semana 3: Frontend Asíncrono**

```bash
# Día 1-3: Modificar app.py
✅ Reemplazar cálculos locales por API calls
✅ Implementar polling de jobs
✅ Progress bars y manejo de errores

# Día 4-5: UX Mejorada
✅ Indicadores de cola ("3 usuarios delante de ti")
✅ Notificaciones cuando trabajo completa
✅ Modo offline (degradar a cache antiguo)
```

### **Semana 4: Deploy y Escalamiento**

```bash
# Día 1-2: Infraestructura
✅ Docker Compose multi-servicio
✅ Nginx como reverse proxy
✅ Certificados SSL (Let's Encrypt)

# Día 3: Monitoreo
✅ Prometheus + Grafana
✅ Alertas (queue > 50, latency > 10s)
✅ Dashboard de métricas de sistema

# Día 4-5: Testing de carga
✅ Locust/K6 para simular 50 usuarios
✅ Identificar límites reales
✅ Documentación de troubleshooting
```

---

## 📊 MÉTRICAS DE ÉXITO

```yaml
KPIs del Sistema:

Performance:
  - Tiempo de respuesta p50: < 2 segundos
  - Tiempo de respuesta p95: < 10 segundos
  - Cache hit rate: > 70%
  - Throughput: > 15 cálculos/minuto

Escalabilidad:
  - Usuarios concurrentes: 30-50
  - Pico de tráfico: 100+ (con degradación controlada)
  - Auto-scaling: < 30 segundos para agregar worker

Disponibilidad:
  - Uptime: > 99.5%
  - MTTR: < 10 minutos
  - Zero-downtime deploys

Costos:
  - Infraestructura: $150-300/mes (AWS t3.xlarge × 2)
  - vs Alternativa: Looker ($1,500/mes), Tableau ($2,000/mes)
  - ROI: Break-even en 1 mes
```

---

## 🚀 ESCALAMIENTO FUTURO (50+ usuarios)

```python
# Auto-scaling con Kubernetes
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: worker-cxc-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: worker-cxc
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: External  # Custom metric: queue length
    external:
      metric:
        name: rq_queue_length
      target:
        type: Value
        value: "20"
```

```bash
# Reglas de auto-scaling
IF queue_length > 20 THEN
    scale_workers += 2
    max_workers = 10

IF cpu_usage > 80% FOR 2min THEN
    scale_backend += 1
    max_backend = 5

IF cache_hit_rate < 50% THEN
    alert_to_slack("Cache ineficiente, revisar TTL")
```

---

## 💰 COMPARATIVA DE COSTOS

| Escala | Arquitectura Actual | Arquitectura Desacoplada | Diferencia |
|--------|---------------------|--------------------------|------------|
| **1-5 usuarios** | $50/mes (t3.small) | $100/mes (overhead innecesario) | ❌ +$50 |
| **10-20 usuarios** | $200/mes (t3.large, saturado) | $150/mes (t3.xlarge × 1) | ✅ -$50 |
| **30-50 usuarios** | ❌ No soportado | $300/mes (t3.xlarge × 2) | ✅ Viable |
| **100+ usuarios** | ❌ No soportado | $600/mes (K8s cluster) | ✅ Viable |

**Conclusión**: Migrar cuando tengas **>10 usuarios activos diarios**.

---

## 🎯 RECOMENDACIÓN FINAL

### **Para tu caso:**

```
ESCENARIO A) 1-10 usuarios actuales:
└─ Mantener arquitectura actual
└─ Optimizar código (vectorización, cache)
└─ Preparar terreno (modularizar cálculos)
└─ Timeline: No migrar aún

ESCENARIO B) 10-30 usuarios proyectados:
└─ Implementar arquitectura desacoplada
└─ Prioridad: Backend API + Workers
└─ Timeline: 3-4 semanas

ESCENARIO C) 50+ usuarios proyectados:
└─ Ir directo a K8s + auto-scaling
└─ Considerar SaaS multi-tenant
└─ Timeline: 2-3 meses
```

**¿Cuántos usuarios tienes actualmente y cuántos proyectas en 6 meses?**  
Te puedo dar un plan específico basado en tu realidad.
