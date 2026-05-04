from datetime import datetime, timedelta, timezone

import pandas as pd

from app.repositories.sesion_repo import SesionRepositorio


class ReporteService:
    """Servicio de reportes simplificado: solo analiza sesiones (login/logout/duración).
    No hay tracking de eventos granulares.
    """

    def __init__(self) -> None:
        self.sesiones = SesionRepositorio()

    def resumen_general(self, dias: int = 30) -> dict:
        """Resumen de sesiones: total, activas, cerradas, duración promedio."""
        fecha_desde = datetime.now(timezone.utc) - timedelta(days=dias)
        filtro = {"fecha_inicio": {"$gte": fecha_desde}}
        sesiones = self.sesiones.listar(filtro=filtro, limite=5000)

        activas = [s for s in sesiones if s.get("estado") == "activa"]
        cerradas = [s for s in sesiones if s.get("estado") == "cerrada"]
        duraciones = [s.get("duracion_segundos") for s in cerradas if s.get("duracion_segundos") is not None]
        promedio = round(sum(duraciones) / len(duraciones), 2) if duraciones else 0

        return {
            "sesiones_total": len(sesiones),
            "sesiones_activas": len(activas),
            "sesiones_cerradas": len(cerradas),
            "duracion_promedio_segundos": promedio,
        }

    def por_usuario(self, dias: int = 30) -> pd.DataFrame:
        """Tabla: usuario, cantidad de sesiones, duración promedio."""
        fecha_desde = datetime.now(timezone.utc) - timedelta(days=dias)
        sesiones = self.sesiones.listar({"fecha_inicio": {"$gte": fecha_desde}}, limite=5000)
        if not sesiones:
            return pd.DataFrame(columns=["usuario", "sesiones", "duracion_promedio_segundos"])

        sesiones_df = pd.DataFrame(sesiones)
        if not sesiones_df.empty:
            # Convertir duracion_segundos a numérico (None → NaN)
            sesiones_df["duracion_segundos"] = pd.to_numeric(sesiones_df["duracion_segundos"], errors="coerce")
            agrupadas = (
                sesiones_df.groupby("usuario")
                .agg(
                    sesiones=("id_sesion", "count"),
                    duracion_promedio_segundos=("duracion_segundos", "mean"),
                )
                .reset_index()
            )
            agrupadas["duracion_promedio_segundos"] = agrupadas["duracion_promedio_segundos"].round(2).fillna(0)
            return agrupadas.sort_values("sesiones", ascending=False)
        return pd.DataFrame(columns=["usuario", "sesiones", "duracion_promedio_segundos"])

    def linea_tiempo(self, dias: int = 30) -> pd.DataFrame:
        """Tabla: fecha, cantidad de sesiones iniciadas por día."""
        fecha_desde = datetime.now(timezone.utc) - timedelta(days=dias)
        sesiones = self.sesiones.listar({"fecha_inicio": {"$gte": fecha_desde}}, limite=5000)
        if not sesiones:
            return pd.DataFrame(columns=["fecha", "cantidad"])

        df = pd.DataFrame(sesiones)
        if df.empty:
            return pd.DataFrame(columns=["fecha", "cantidad"])

        # Agrupar por fecha (sin hora)
        df["fecha"] = pd.to_datetime(df["fecha_inicio"]).dt.date
        agrupada = df.groupby("fecha").size().reset_index(name="cantidad")
        return agrupada.sort_values("fecha")

    def ultimas_sesiones(self, limite: int = 20) -> list:
        """Lista de últimas sesiones cerradas con duración."""
        return self.sesiones.listar({"estado": "cerrada"}, limite=limite)
