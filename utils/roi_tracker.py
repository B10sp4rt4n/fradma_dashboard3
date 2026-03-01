"""
ROI Tracker - Sistema de seguimiento de retorno de inversión
Calcula y rastrea el valor generado por cada acción en la plataforma
"""
from datetime import datetime
from typing import Dict, Optional


class ROITracker:
    """
    Tracker de ROI para medir el valor generado por el uso de la plataforma.
    
    En MVP (Fase 1): Usa session state, sin persistencia DB
    En Fase 2: Se agregará persistencia a base de datos
    """
    
    # Benchmarks de tiempo ahorrado por acción (en horas)
    BENCHMARKS = {
        # Módulo CFDIs
        "process_cfdis_10": 0.5,        # Por cada 10 XMLs procesados
        "process_cfdis_50": 2.0,        # Por cada 50 XMLs
        "process_cfdis_100": 4.9,       # Por cada 100 XMLs
        "analyze_cfdis": 1.5,           # Análisis completo de CFDIs
        "export_cfdi_data": 0.3,        # Exportación de datos
        
        # Módulo Reporte Ejecutivo
        "generate_exec_report": 1.9,    # Generar reporte ejecutivo
        "analyze_top_clients": 0.95,    # Análisis top clientes
        "review_kpis": 0.5,             # Revisar KPIs principales
        
        # Módulo CxC
        "cxc_analysis": 1.4,            # Análisis de cartera
        "cxc_aging_report": 0.8,        # Reporte antigüedad saldos
        "detect_risk_clients": 4.0,     # Identificar clientes riesgo (manual)
        
        # Módulo Asistente de Datos (NL2SQL)
        "nl2sql_query": 0.5,            # Consulta SQL manual → automática
        "nl2sql_interpretation": 0.3,   # Interpretación de resultados por IA
        "nl2sql_chart": 0.25,           # Generación automática de gráfica
        "nl2sql_export": 0.15,          # Exportar datos a CSV
        "nl2sql_schema_explore": 0.2,   # Explorar esquema manualmente
        "nl2sql_complex_query": 1.0,    # Consulta compleja (joins, aggregates)
        
        # Otros módulos
        "year_comparison": 2.8,         # Comparativo año vs año
        "vendors_dashboard": 2.4,       # Dashboard vendedores
        "forecast_generation": 5.8,     # Forecast manual en Excel
        "consolidated_report": 3.5,     # Reporte consolidado
    }
    
    # Costos por hora según rol (default)
    DEFAULT_HOURLY_RATES = {
        "admin": 5000,      # CEO/Director
        "cfo": 3000,        # CFO
        "manager": 1500,    # Gerente
        "accountant": 500,  # Contador
        "analyst": 300,     # Analista
        "user": 500,        # Usuario estándar
    }
    
    def __init__(self, session_state):
        """
        Inicializa el tracker con el session_state de Streamlit
        
        Args:
            session_state: st.session_state de Streamlit
        """
        self.session_state = session_state
        self._init_session()
    
    def _init_session(self):
        """Inicializa la estructura de datos en session_state si no existe"""
        if "roi_data" not in self.session_state:
            self.session_state.roi_data = {
                "total_hrs_saved": 0.0,
                "total_value": 0.0,
                "actions": [],
                "session_start": datetime.now(),
                "today": {
                    "hrs": 0.0,
                    "value": 0.0,
                    "actions_count": 0
                },
                "month": {
                    "hrs": 0.0,
                    "value": 0.0,
                    "actions_count": 0
                },
                "year": {
                    "hrs": 0.0,
                    "value": 0.0,
                    "actions_count": 0
                }
            }
    
    def get_user_hourly_rate(self, user=None) -> float:
        """
        Obtiene el costo por hora del usuario actual
        
        Args:
            user: Objeto usuario (opcional, usa session_state.user por defecto)
            
        Returns:
            float: Costo por hora en MXN
        """
        if user is None and hasattr(self.session_state, 'user'):
            user = self.session_state.user
        
        if user and hasattr(user, 'role'):
            role = user.role.value if hasattr(user.role, 'value') else str(user.role)
            return self.DEFAULT_HOURLY_RATES.get(role.lower(), 500)
        
        return 500  # Default
    
    def track_action(
        self, 
        module: str, 
        action: str, 
        quantity: float = 1.0,
        custom_hrs_saved: Optional[float] = None,
        show_toast: bool = True
    ) -> Dict:
        """
        Rastrea una acción y calcula el ROI automáticamente
        
        Args:
            module: Nombre del módulo (ej: "cfdi", "exec_report", "cxc")
            action: Nombre de la acción (debe estar en BENCHMARKS)
            quantity: Multiplicador de la acción (ej: 2.5 para 250 CFDIs)
            custom_hrs_saved: Horas ahorradas custom (sobrescribe benchmark)
            show_toast: Si mostrar toast notification
            
        Returns:
            Dict con información del tracking: {
                "hrs_saved": float,
                "value": float,
                "message": str
            }
        """
        # Calcular horas ahorradas
        if custom_hrs_saved is not None:
            hrs_saved = custom_hrs_saved
        else:
            base_hrs = self.BENCHMARKS.get(action, 0)
            hrs_saved = base_hrs * quantity
        
        # Calcular valor monetario
        hourly_rate = self.get_user_hourly_rate()
        value = hrs_saved * hourly_rate
        
        # Guardar en session state
        action_record = {
            "timestamp": datetime.now(),
            "module": module,
            "action": action,
            "hrs_saved": hrs_saved,
            "value": value,
            "hourly_rate": hourly_rate
        }
        
        self.session_state.roi_data["actions"].append(action_record)
        self.session_state.roi_data["total_hrs_saved"] += hrs_saved
        self.session_state.roi_data["total_value"] += value
        
        # Actualizar contadores por período
        self.session_state.roi_data["today"]["hrs"] += hrs_saved
        self.session_state.roi_data["today"]["value"] += value
        self.session_state.roi_data["today"]["actions_count"] += 1
        
        self.session_state.roi_data["month"]["hrs"] += hrs_saved
        self.session_state.roi_data["month"]["value"] += value
        self.session_state.roi_data["month"]["actions_count"] += 1
        
        self.session_state.roi_data["year"]["hrs"] += hrs_saved
        self.session_state.roi_data["year"]["value"] += value
        self.session_state.roi_data["year"]["actions_count"] += 1
        
        result = {
            "hrs_saved": hrs_saved,
            "value": value,
            "message": f"✅ Ahorraste {hrs_saved:.1f} hrs = ${value:,.0f} MXN"
        }
        
        return result
    
    def track_risk_avoided(
        self, 
        module: str,
        risk_type: str,
        value: float,
        description: str = ""
    ) -> Dict:
        """
        Rastrea un riesgo detectado y evitado (requiere IA Premium)
        
        Args:
            module: Módulo donde se detectó (ej: "cxc", "exec_report")
            risk_type: Tipo de riesgo (ej: "morosidad", "churn", "perdida_cliente")
            value: Valor del riesgo evitado en MXN
            description: Descripción del riesgo
            
        Returns:
            Dict con información del riesgo
        """
        risk_record = {
            "timestamp": datetime.now(),
            "module": module,
            "risk_type": risk_type,
            "value": value,
            "description": description,
            "category": "risk_avoided"
        }
        
        self.session_state.roi_data["actions"].append(risk_record)
        self.session_state.roi_data["total_value"] += value
        
        # Actualizar contadores
        self.session_state.roi_data["today"]["value"] += value
        self.session_state.roi_data["month"]["value"] += value
        self.session_state.roi_data["year"]["value"] += value
        
        return {
            "value": value,
            "message": f"🚨 Riesgo evitado: ${value:,.0f} MXN"
        }
    
    def get_summary(self) -> Dict:
        """
        Obtiene resumen del ROI acumulado
        
        Returns:
            Dict con métricas: today, month, year, total
        """
        return {
            "today": {
                "hrs": self.session_state.roi_data["today"]["hrs"],
                "value": self.session_state.roi_data["today"]["value"],
                "actions": self.session_state.roi_data["today"]["actions_count"]
            },
            "month": {
                "hrs": self.session_state.roi_data["month"]["hrs"],
                "value": self.session_state.roi_data["month"]["value"],
                "actions": self.session_state.roi_data["month"]["actions_count"]
            },
            "year": {
                "hrs": self.session_state.roi_data["year"]["hrs"],
                "value": self.session_state.roi_data["year"]["value"],
                "actions": self.session_state.roi_data["year"]["actions_count"]
            },
            "total": {
                "hrs": self.session_state.roi_data["total_hrs_saved"],
                "value": self.session_state.roi_data["total_value"],
                "actions": len(self.session_state.roi_data["actions"])
            }
        }
    
    def get_recent_actions(self, limit: int = 5) -> list:
        """
        Obtiene las últimas acciones rastreadas
        
        Args:
            limit: Número máximo de acciones a retornar
            
        Returns:
            Lista de acciones recientes
        """
        actions = self.session_state.roi_data["actions"]
        return actions[-limit:] if len(actions) > limit else actions
    
    def reset_session(self):
        """Reinicia el tracking de la sesión actual (útil para testing)"""
        self._init_session()


# Helper functions para uso rápido
def init_roi_tracker(session_state):
    """
    Inicializa el ROI tracker en el session state
    
    Args:
        session_state: st.session_state de Streamlit
        
    Returns:
        ROITracker instance
    """
    if "roi_tracker" not in session_state:
        session_state.roi_tracker = ROITracker(session_state)
    return session_state.roi_tracker


def quick_track(session_state, module: str, action: str, quantity: float = 1.0):
    """
    Función rápida para trackear una acción
    
    Args:
        session_state: st.session_state
        module: Nombre del módulo
        action: Nombre de la acción
        quantity: Multiplicador
    """
    tracker = init_roi_tracker(session_state)
    return tracker.track_action(module, action, quantity)
