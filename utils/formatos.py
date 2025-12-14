"""
Módulo de utilidades para formateo consistente de datos en el dashboard.
Proporciona funciones helper para monedas, porcentajes y números.
"""

def formato_moneda(valor, decimales=2):
    """
    Formatea un valor numérico como moneda USD con separadores de miles.
    
    Args:
        valor: Número a formatear
        decimales: Número de decimales (default: 2)
    
    Returns:
        String formateado como "$1,234.56"
    """
    if valor is None or (isinstance(valor, float) and (valor != valor)):  # Check for NaN
        return "$0.00"
    
    try:
        valor_num = float(valor)
        if decimales == 0:
            return f"${valor_num:,.0f}"
        elif decimales == 2:
            return f"${valor_num:,.2f}"
        else:
            return f"${valor_num:,.{decimales}f}"
    except (ValueError, TypeError):
        return "$0.00"


def formato_numero(valor, decimales=0):
    """
    Formatea un número con separadores de miles.
    
    Args:
        valor: Número a formatear
        decimales: Número de decimales (default: 0)
    
    Returns:
        String formateado como "1,234" o "1,234.56"
    """
    if valor is None or (isinstance(valor, float) and (valor != valor)):
        return "0"
    
    try:
        valor_num = float(valor)
        if decimales == 0:
            return f"{valor_num:,.0f}"
        else:
            return f"{valor_num:,.{decimales}f}"
    except (ValueError, TypeError):
        return "0"


def formato_porcentaje(valor, decimales=1):
    """
    Formatea un valor como porcentaje.
    
    Args:
        valor: Número a formatear (puede ser 0-1 o 0-100)
        decimales: Número de decimales (default: 1)
    
    Returns:
        String formateado como "12.3%"
    """
    if valor is None or (isinstance(valor, float) and (valor != valor)):
        return "0.0%"
    
    try:
        valor_num = float(valor)
        # Si el valor está entre 0 y 1, asumimos que es proporción y multiplicamos por 100
        if 0 <= valor_num <= 1:
            valor_num *= 100
        
        if decimales == 0:
            return f"{valor_num:.0f}%"
        elif decimales == 1:
            return f"{valor_num:.1f}%"
        else:
            return f"{valor_num:.{decimales}f}%"
    except (ValueError, TypeError):
        return "0.0%"


def formato_delta_moneda(valor, decimales=2):
    """
    Formatea un delta de moneda para usar en st.metric().
    
    Args:
        valor: Valor del delta
        decimales: Número de decimales (default: 2)
    
    Returns:
        String formateado como "$1,234.56" o "-$1,234.56"
    """
    if valor is None or (isinstance(valor, float) and (valor != valor)):
        return "$0.00"
    
    try:
        valor_num = float(valor)
        signo = "" if valor_num >= 0 else "-"
        valor_abs = abs(valor_num)
        
        if decimales == 0:
            return f"{signo}${valor_abs:,.0f}"
        elif decimales == 2:
            return f"{signo}${valor_abs:,.2f}"
        else:
            return f"{signo}${valor_abs:,.{decimales}f}"
    except (ValueError, TypeError):
        return "$0.00"


def formato_compacto(valor):
    """
    Formatea números grandes de manera compacta (K, M, B).
    
    Args:
        valor: Número a formatear
    
    Returns:
        String formateado como "1.2M", "345.6K", etc.
    """
    if valor is None or (isinstance(valor, float) and (valor != valor)):
        return "0"
    
    try:
        valor_num = float(valor)
        signo = "" if valor_num >= 0 else "-"
        valor_abs = abs(valor_num)
        
        if valor_abs >= 1_000_000_000:
            return f"{signo}{valor_abs/1_000_000_000:.1f}B"
        elif valor_abs >= 1_000_000:
            return f"{signo}{valor_abs/1_000_000:.1f}M"
        elif valor_abs >= 1_000:
            return f"{signo}{valor_abs/1_000:.1f}K"
        else:
            return f"{signo}{valor_abs:.0f}"
    except (ValueError, TypeError):
        return "0"


def formato_dias(dias):
    """
    Formatea días con texto descriptivo.
    
    Args:
        dias: Número de días
    
    Returns:
        String formateado como "30 días", "1 día", etc.
    """
    if dias is None or (isinstance(dias, float) and (dias != dias)):
        return "0 días"
    
    try:
        dias_num = int(float(dias))
        if dias_num == 1:
            return "1 día"
        else:
            return f"{dias_num} días"
    except (ValueError, TypeError):
        return "0 días"


# Diccionarios de formato para usar con DataFrame.style.format()
FORMATO_MONEDA_DICT = '${:,.2f}'
FORMATO_MONEDA_SIN_DECIMALES_DICT = '${:,.0f}'
FORMATO_NUMERO_DICT = '{:,.0f}'
FORMATO_NUMERO_DECIMAL_DICT = '{:,.2f}'
FORMATO_PORCENTAJE_DICT = '{:.1f}%'
FORMATO_PORCENTAJE_2DEC_DICT = '{:.2f}%'
