"""Helper para conversión de zona horaria UTC → Bogotá (UTC-5)."""

from datetime import datetime
import pytz

# Zona horaria de Bogotá
ZONA_BOGOTA = pytz.timezone("America/Bogota")


def utc_a_bogota(fecha_utc: datetime | None) -> datetime | None:
    """Convierte una fecha UTC a zona horaria de Bogotá.
    
    Args:
        fecha_utc: datetime con tzinfo=UTC (de MongoDB)
    
    Returns:
        datetime en zona horaria Bogotá, o None si la entrada es None
    """
    if not fecha_utc:
        return None
    
    # Si es naive (sin timezone), asumir que es UTC
    if fecha_utc.tzinfo is None:
        fecha_utc = fecha_utc.replace(tzinfo=pytz.UTC)
    
    # Convertir a Bogotá
    return fecha_utc.astimezone(ZONA_BOGOTA)


def formato_fecha_bogota(fecha_utc: datetime | None, formato: str = "%d/%m/%Y %H:%M:%S") -> str:
    """Convierte y formatea una fecha UTC a zona horaria de Bogotá.
    
    Args:
        fecha_utc: datetime con tzinfo=UTC
        formato: string de formato (default: "dd/mm/yyyy hh:mm:ss")
    
    Returns:
        String con fecha formateada en Bogotá
    """
    if not fecha_utc:
        return "-"
    
    fecha_bogota = utc_a_bogota(fecha_utc)
    return fecha_bogota.strftime(formato)


def formato_duracion(segundos: int | None) -> str:
    """Formatea duración en segundos a formato legible (HH:MM:SS).
    
    Args:
        segundos: duración en segundos
    
    Returns:
        String formato "1h 23m 45s" o "-" si es None
    """
    if segundos is None or segundos < 0:
        return "-"
    
    horas = segundos // 3600
    minutos = (segundos % 3600) // 60
    secs = segundos % 60
    
    if horas > 0:
        return f"{horas}h {minutos}m {secs}s"
    elif minutos > 0:
        return f"{minutos}m {secs}s"
    else:
        return f"{secs}s"
