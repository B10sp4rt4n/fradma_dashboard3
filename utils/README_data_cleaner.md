# 🧹 Sistema de Limpieza de Datos

## Normalización Automática

El sistema ahora normaliza automáticamente todos los campos de texto al cargar datos:

### ¿Qué hace?
- **Convierte a minúsculas**: "JOSE" → "jose"
- **Elimina acentos**: "José" → "jose"  
- **Limpia espacios**: "Maria  Lopez" → "maria lopez"

### Columnas normalizadas:
- `agente`, `vendedor`, `ejecutivo`
- `linea_producto`, `linea_de_negocio`
- `cliente`
- `producto`

## Aliases Manuales

Para casos que la normalización automática no resuelve, edita `config/aliases.json`:

```json
{
  "agente": {
    "jose garcia": ["José García M.", "Jose Garcia (vendedor)", "J. Garcia"],
    "maria lopez": ["María López S.", "Ma. Lopez", "M Lopez"]
  },
  "linea_producto": {
    "ferreteria": ["Ferretería", "Ferreter\u00eda", "FERRETERIA", "Linea Ferretera"],
    "plomeria": ["Plomería", "Plomer\u00eda", "PLOMERIA"]
  }
}
```

## Detección de Duplicados

Al cargar un archivo, el sistema detecta automáticamente valores similares:

- Si encuentra "José García" y "Jose Garcia" con 95% similitud
- Muestra advertencia en un expander
- Sugiere unificarlos vía `config/aliases.json`

## Ejemplos

### Antes (sin normalización):
```
Agente: José García, Jose Garcia, JOSE GARCIA
→ 3 vendedores diferentes
→ Ventas separadas
```

### Después (con normalización):
```
Agente: jose garcia, jose garcia, jose garcia  
→ 1 vendedor unificado
→ Ventas consolidadas
```

## Ventajas

✅ **Automático**: No requiere configuración inicial  
✅ **Flexible**: Aliases para casos especiales  
✅ **Inteligente**: Detecta duplicados potenciales  
✅ **Transparente**: Muestra qué se normalizó  
✅ **Reversible**: No modifica archivo original
