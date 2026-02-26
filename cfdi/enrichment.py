"""
Módulo de enriquecimiento de datos CFDI con IA.

Este módulo usa GPT-4 para clasificar automáticamente conceptos de CFDI
en líneas de negocio específicas, mejorar descripciones y detectar anomalías.

Autor: Fradma Dashboard Team
Fecha: Febrero 2026
"""

import logging
import hashlib
import json
from typing import Dict, List, Optional, Tuple
from decimal import Decimal
import os

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logging.warning("OpenAI no disponible. Instalar con: pip install openai")

# Configurar logging
logger = logging.getLogger(__name__)


# Líneas de negocio B2B México
LINEAS_NEGOCIO = [
    "ferreteria_herramientas",
    "ferreteria_industrial",
    "materiales_construccion",
    "plasticos_industriales",
    "equipos_hidraulicos",
    "equipos_electricos",
    "pinturas_recubrimientos",
    "quimicos_industriales",
    "seguridad_industrial",
    "textiles_industriales",
    "automotriz_refacciones",
    "empaque_embalaje",
    "limpieza_industrial",
    "otro"
]


# Mapeo de aliases comunes (acelera clasificación sin IA)
ALIASES_DIRECTOS = {
    # Ferretería
    "tornillo": "ferreteria_industrial",
    "tuerca": "ferreteria_industrial",
    "clavo": "ferreteria_herramientas",
    "martillo": "ferreteria_herramientas",
    "desarmador": "ferreteria_herramientas",
    "taladro": "ferreteria_herramientas",
    "llave": "ferreteria_herramientas",
    
    # Construcción
    "cemento": "materiales_construccion",
    "arena": "materiales_construccion",
    "grava": "materiales_construccion",
    "ladrillo": "materiales_construccion",
    "block": "materiales_construccion",
    "varilla": "materiales_construccion",
    "alambrón": "materiales_construccion",
    
    # Plásticos
    "polietileno": "plasticos_industriales",
    "pvc": "plasticos_industriales",
    "polipropileno": "plasticos_industriales",
    "pet": "plasticos_industriales",
    
    # Hidráulica
    "bomba": "equipos_hidraulicos",
    "tubería": "equipos_hidraulicos",
    "válvula": "equipos_hidraulicos",
    "manguera": "equipos_hidraulicos",
    
    # Eléctricos
    "cable": "equipos_electricos",
    "transformador": "equipos_electricos",
    "interruptor": "equipos_electricos",
    "contacto": "equipos_electricos",
    
    # Pintura
    "pintura": "pinturas_recubrimientos",
    "barniz": "pinturas_recubrimientos",
    "esmalte": "pinturas_recubrimientos",
    "laca": "pinturas_recubrimientos",
    
    # Químicos
    "solvente": "quimicos_industriales",
    "ácido": "quimicos_industriales",
    "resina": "quimicos_industriales",
    
    # Seguridad
    "casco": "seguridad_industrial",
    "guantes": "seguridad_industrial",
    "lentes": "seguridad_industrial",
    "botas": "seguridad_industrial",
}


class CFDIEnrichment:
    """
    Clase para enriquecimiento de conceptos CFDI con IA.
    
    Características:
    - Clasificación automática en líneas de negocio
    - Sistema de caché para evitar llamadas duplicadas
    - Fallback a clasificación por palabras clave
    - Batch processing eficiente
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4o-mini",
        use_cache: bool = True
    ):
        """
        Inicializa el enriquecedor.
        
        Args:
            api_key: API key de OpenAI (si None, usa OPENAI_API_KEY env var)
            model: Modelo a usar (gpt-4o-mini es más económico)
            use_cache: Si True, cachea clasificaciones para evitar duplicados
        """
        self.model = model
        self.use_cache = use_cache
        self.cache: Dict[str, str] = {}
        
        # Inicializar cliente OpenAI si está disponible
        if OPENAI_AVAILABLE:
            api_key = api_key or os.getenv('OPENAI_API_KEY')
            if api_key:
                self.client = OpenAI(api_key=api_key)
                logger.info(f"OpenAI inicializado con modelo {model}")
            else:
                self.client = None
                logger.warning("OPENAI_API_KEY no encontrada, usando clasificación básica")
        else:
            self.client = None
            logger.warning("OpenAI no disponible, usando clasificación básica")
    
    def _get_cache_key(self, descripcion: str) -> str:
        """
        Genera una clave de caché para una descripción.
        
        Args:
            descripcion: Descripción del producto
            
        Returns:
            Hash MD5 de la descripción normalizada
        """
        normalized = descripcion.lower().strip()
        return hashlib.md5(normalized.encode('utf-8')).hexdigest()
    
    def _clasificar_por_keywords(self, descripcion: str) -> str:
        """
        Clasificación básica usando palabras clave (fallback sin IA).
        
        Args:
            descripcion: Descripción del producto
            
        Returns:
            Línea de negocio estimada
        """
        desc_lower = descripcion.lower()
        
        # Buscar aliases directos
        for keyword, linea in ALIASES_DIRECTOS.items():
            if keyword in desc_lower:
                logger.debug(f"Clasificación directa: '{descripcion}' → {linea}")
                return linea
        
        # Si no hay match, retornar "otro"
        logger.debug(f"Sin clasificación directa para: '{descripcion}'")
        return "otro"
    
    def _clasificar_con_gpt(self, descripcion: str) -> Optional[str]:
        """
        Clasificación usando GPT-4.
        
        Args:
            descripcion: Descripción del producto
            
        Returns:
            Línea de negocio clasificada, o None si hay error
        """
        if not self.client:
            return None
        
        try:
            prompt = f"""Clasifica el siguiente producto industrial en UNA de estas categorías:

{chr(10).join(f"- {linea}" for linea in LINEAS_NEGOCIO)}

Producto: {descripcion}

Responde SOLO con el nombre de la categoría, sin explicación. Si no estás seguro, responde "otro".

Categoría:"""

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "Eres un experto en clasificación de productos industriales B2B en México. Respondes de forma concisa."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.1,
                max_tokens=50
            )
            
            clasificacion = response.choices[0].message.content.strip().lower()
            
            # Validar que la clasificación sea una línea válida
            if clasificacion in LINEAS_NEGOCIO:
                logger.debug(f"GPT clasificó '{descripcion}' → {clasificacion}")
                return clasificacion
            else:
                logger.warning(f"GPT retornó clasificación inválida: {clasificacion}")
                return "otro"
                
        except Exception as e:
            logger.error(f"Error en clasificación GPT: {e}")
            return None
    
    def clasificar_concepto(
        self,
        descripcion: str,
        clave_prod_serv: Optional[str] = None,
        usar_gpt: bool = True
    ) -> str:
        """
        Clasifica un concepto en una línea de negocio.
        
        Args:
            descripcion: Descripción del producto/servicio
            clave_prod_serv: Clave SAT opcional (puede ayudar en clasificación)
            usar_gpt: Si False, solo usa keywords (más rápido, menos preciso)
            
        Returns:
            Línea de negocio clasificada
            
        Ejemplo:
            >>> enricher = CFDIEnrichment()
            >>> enricher.clasificar_concepto("Tornillo hexagonal 1/4 x 2 pulgadas")
            'ferreteria_industrial'
        """
        # Verificar caché
        if self.use_cache:
            cache_key = self._get_cache_key(descripcion)
            if cache_key in self.cache:
                logger.debug(f"Cache hit: {descripcion}")
                return self.cache[cache_key]
        
        # Intentar clasificación básica primero
        clasificacion_basica = self._clasificar_por_keywords(descripcion)
        
        if clasificacion_basica != "otro":
            # Si encontramos match directo, usarlo
            if self.use_cache:
                self.cache[cache_key] = clasificacion_basica
            return clasificacion_basica
        
        # Si no hay match básico y tenemos GPT, usarlo
        if usar_gpt:
            clasificacion_gpt = self._clasificar_con_gpt(descripcion)
            if clasificacion_gpt:
                if self.use_cache:
                    self.cache[cache_key] = clasificacion_gpt
                return clasificacion_gpt
        
        # Fallback: retornar "otro"
        if self.use_cache:
            self.cache[cache_key] = "otro"
        return "otro"
    
    def enriquecer_conceptos_batch(
        self,
        conceptos: List[Dict],
        usar_gpt: bool = True,
        max_gpt_calls: Optional[int] = None
    ) -> List[Dict]:
        """
        Enriquece una lista de conceptos con clasificación.
        
        Args:
            conceptos: Lista de diccionarios con conceptos
                Cada concepto debe tener al menos 'descripcion'
            usar_gpt: Si False, solo usa keywords
            max_gpt_calls: Límite de llamadas a GPT (para controlar costo)
            
        Returns:
            Lista de conceptos enriquecidos (con campo 'linea_negocio')
            
        Ejemplo:
            >>> conceptos = [
            ...     {'descripcion': 'Tornillo 1/4', 'importe': 100},
            ...     {'descripcion': 'Cemento gris 50kg', 'importe': 200}
            ... ]
            >>> enricher = CFDIEnrichment()
            >>> enriquecidos = enricher.enriquecer_conceptos_batch(conceptos)
            >>> enriquecidos[0]['linea_negocio']
            'ferreteria_industrial'
        """
        conceptos_enriquecidos = []
        gpt_calls = 0
        
        for concepto in conceptos:
            descripcion = concepto.get('descripcion', '')
            clave_prod_serv = concepto.get('clave_prod_serv')
            
            if not descripcion:
                # Si no hay descripción, usar "otro"
                concepto_nuevo = {**concepto, 'linea_negocio': 'otro'}
                conceptos_enriquecidos.append(concepto_nuevo)
                continue
            
            # Verificar límite de llamadas GPT
            if max_gpt_calls and gpt_calls >= max_gpt_calls:
                usar_gpt_ahora = False
            else:
                usar_gpt_ahora = usar_gpt
            
            # Verificar si ya está en caché
            cache_key = self._get_cache_key(descripcion)
            ya_en_cache = self.use_cache and cache_key in self.cache
            
            # Clasificar  
            linea = self.clasificar_concepto(
                descripcion=descripcion,
                clave_prod_serv=clave_prod_serv,
                usar_gpt=usar_gpt_ahora
            )
            
            # Incrementar contador si usamos GPT y no estaba en caché
            if usar_gpt_ahora and not ya_en_cache:
                # Si la clasificación básica no funcionó (retorna "otro")
                # entonces se usó GPT
                clasificacion_basica = self._clasificar_por_keywords(descripcion)
                if clasificacion_basica == "otro":
                    gpt_calls += 1
            
            # Agregar línea de negocio al concepto
            concepto_nuevo = {**concepto, 'linea_negocio': linea}
            conceptos_enriquecidos.append(concepto_nuevo)
        
        logger.info(
            f"Enriquecidos {len(conceptos)} conceptos "
            f"({gpt_calls} llamadas GPT)"
        )
        
        return conceptos_enriquecidos
    
    def detectar_anomalias(
        self,
        concepto: Dict,
        historico: Optional[List[Dict]] = None
    ) -> List[str]:
        """
        Detecta posibles anomalías en un concepto.
        
        Args:
            concepto: Diccionario con datos del concepto
            historico: Lista opcional de conceptos similares históricos
            
        Returns:
            Lista de alertas (vacía si todo normal)
            
        Ejemplo:
            >>> concepto = {
            ...     'descripcion': 'Tornillo',
            ...     'cantidad': 10000,
            ...     'valor_unitario': 100.00
            ... }
            >>> enricher = CFDIEnrichment()
            >>> anomalias = enricher.detectar_anomalias(concepto)
            >>> anomalias
            ['Cantidad inusualmente alta: 10,000 unidades']
        """
        alertas = []
        
        # Verificar cantidad anormal
        cantidad = concepto.get('cantidad', 0)
        if cantidad > 10000:
            alertas.append(f"Cantidad inusualmente alta: {cantidad:,.0f} unidades")
        elif cantidad == 0:
            alertas.append("Cantidad en cero")
        
        # Verificar precio anormal
        valor_unitario = concepto.get('valor_unitario', 0)
        if isinstance(valor_unitario, (int, float, Decimal)):
            if valor_unitario <= 0:
                alertas.append("Precio unitario <= 0")
            elif valor_unitario > 1000000:
                alertas.append(f"Precio muy alto: ${valor_unitario:,.2f}")
        
        # Verificar descripción muy corta
        descripcion = concepto.get('descripcion', '')
        if len(descripcion) < 5:
            alertas.append("Descripción muy corta o vacía")
        
        # Si hay histórico, comparar precios
        if historico:
            precios_historicos = [
                float(h.get('valor_unitario', 0))
                for h in historico
                if h.get('valor_unitario')
            ]
            
            if precios_historicos and valor_unitario:
                promedio = sum(precios_historicos) / len(precios_historicos)
                desviacion = abs(float(valor_unitario) - promedio) / promedio
                
                if desviacion > 0.5:  # 50% de desviación
                    alertas.append(
                        f"Precio difiere {desviacion*100:.0f}% del histórico "
                        f"(promedio: ${promedio:,.2f})"
                    )
        
        return alertas
    
    def generar_resumen(self, conceptos: List[Dict]) -> Dict:
        """
        Genera un resumen estadístico de conceptos enriquecidos.
        
        Args:
            conceptos: Lista de conceptos con 'linea_negocio'
            
        Returns:
            Diccionario con estadísticas por línea de negocio
            
        Ejemplo:
            >>> conceptos = [
            ...     {'descripcion': 'Tornillo', 'linea_negocio': 'ferreteria_industrial', 'importe': 100},
            ...     {'descripcion': 'Cemento', 'linea_negocio': 'materiales_construccion', 'importe': 200}
            ... ]
            >>> enricher = CFDIEnrichment()
            >>> resumen = enricher.generar_resumen(conceptos)
            >>> resumen['ferreteria_industrial']
            {'total_conceptos': 1, 'importe_total': 100.0}
        """
        resumen = {}
        
        for concepto in conceptos:
            linea = concepto.get('linea_negocio', 'otro')
            importe = float(concepto.get('importe', 0))
            
            if linea not in resumen:
                resumen[linea] = {
                    'total_conceptos': 0,
                    'importe_total': 0.0,
                    'conceptos_ejemplo': []
                }
            
            resumen[linea]['total_conceptos'] += 1
            resumen[linea]['importe_total'] += importe
            
            # Guardar ejemplos (max 3)
            if len(resumen[linea]['conceptos_ejemplo']) < 3:
                resumen[linea]['conceptos_ejemplo'].append(
                    concepto.get('descripcion', 'Sin descripción')
                )
        
        return resumen
    
    def export_cache(self, filepath: str):
        """
        Exporta el caché a un archivo JSON.
        
        Args:
            filepath: Ruta del archivo donde guardar el caché
        """
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.cache, f, ensure_ascii=False, indent=2)
        logger.info(f"Caché exportado a {filepath} ({len(self.cache)} entradas)")
    
    def import_cache(self, filepath: str):
        """
        Importa un caché desde un archivo JSON.
        
        Args:
            filepath: Ruta del archivo con el caché
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                self.cache = json.load(f)
            logger.info(f"Caché importado desde {filepath} ({len(self.cache)} entradas)")
        except FileNotFoundError:
            logger.warning(f"Archivo de caché no encontrado: {filepath}")
        except Exception as e:
            logger.error(f"Error importando caché: {e}")


def clasificar_rapido(descripcion: str) -> str:
    """
    Función helper para clasificación rápida sin instanciar clase.
    Solo usa keywords, sin GPT.
    
    Args:
        descripcion: Descripción del producto
        
    Returns:
        Línea de negocio clasificada
        
    Ejemplo:
        >>> clasificar_rapido("Tornillo hexagonal")
        'ferreteria_industrial'
    """
    enricher = CFDIEnrichment()
    return enricher._clasificar_por_keywords(descripcion)
