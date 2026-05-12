from datetime import datetime, timedelta, timezone
import pandas as pd
from app.repositories.correspondencia_repo import CorrespondenciaRepositorio


class ReporteService:
    """Servicio de reportes enfocado en la gestión operativa de correspondencia."""

    def __init__(self) -> None:
        self.repo = CorrespondenciaRepositorio()

    def resumen_operativo(self) -> dict:
        """Obtiene métricas clave de alto nivel."""
        total = self.repo.contar({})
        activos = self.repo.contar({"estado_actual": {"$in": ["pendiente", "en_tramite", "en_revision"]}})
        finalizados = self.repo.contar({"estado_actual": {"$in": ["respondido", "archivado", "traslado_competencia"]}})
        
        hoy = datetime.now(timezone.utc)
        vencidos = self.repo.contar({
            "estado_actual": {"$in": ["pendiente", "en_tramite", "en_revision"]},
            "fecha_vencimiento": {"$lt": hoy}
        })

        return {
            "total_historico": total,
            "tramites_activos": activos,
            "tramites_finalizados": finalizados,
            "vencidos_criticos": vencidos,
            "porcentaje_cumplimiento": round((finalizados / total * 100), 1) if total > 0 else 0
        }

    def distribucion_por_estado(self) -> pd.DataFrame:
        """Datos para gráfico de torta de estados."""
        pipeline = [
            {"$group": {"_id": "$estado_actual", "cantidad": {"$sum": 1}}},
            {"$project": {"estado": "$_id", "cantidad": 1, "_id": 0}}
        ]
        datos = list(self.repo.coleccion.aggregate(pipeline))
        if not datos:
            return pd.DataFrame(columns=["estado", "cantidad"])
        df = pd.DataFrame(datos)
        df["estado"] = df["estado"].apply(lambda x: x.replace("_", " ").title())
        return df

    def carga_por_usuario(self) -> pd.DataFrame:
        """Datos para gráfico de barras de carga de trabajo por usuario (solo activos)."""
        pipeline = [
            {"$match": {"estado_actual": {"$in": ["pendiente", "en_tramite", "en_revision"]}}},
            {"$group": {"_id": "$responsable_actual.nombre", "cantidad": {"$sum": 1}}},
            {"$project": {"usuario": {"$ifNull": ["$_id", "Sin Asignar"]}, "cantidad": 1, "_id": 0}},
            {"$sort": {"cantidad": -1}}
        ]
        datos = list(self.repo.coleccion.aggregate(pipeline))
        return pd.DataFrame(datos) if datos else pd.DataFrame(columns=["usuario", "cantidad"])

    def analisis_vencimiento(self) -> pd.DataFrame:
        """Clasifica los trámites activos por su proximidad al vencimiento."""
        hoy = datetime.now(timezone.utc)
        activos = self.repo.listar({"estado_actual": {"$in": ["pendiente", "en_tramite", "en_revision"]}}, limit=10000)
        
        categorias = {"Vencidos": 0, "Urgentes (0-5d)": 0, "A Tiempo (>5d)": 0}
        
        for c in activos:
            f_venc = c.get("fecha_vencimiento")
            if not f_venc: continue
            
            if f_venc.tzinfo is None: f_venc = f_venc.replace(tzinfo=timezone.utc)
            
            dias = (f_venc - hoy).days
            if dias < 0:
                categorias["Vencidos"] += 1
            elif dias <= 5:
                categorias["Urgentes (0-5d)"] += 1
            else:
                categorias["A Tiempo (>5d)"] += 1
        
        return pd.DataFrame([{"categoria": k, "cantidad": v} for k, v in categorias.items()])

    def tendencia_diaria(self, dias: int = 30) -> pd.DataFrame:
        """Tendencia de radicación diaria en los últimos N días."""
        fecha_desde = datetime.now(timezone.utc) - timedelta(days=dias)
        pipeline = [
            {"$match": {"fecha_radicacion": {"$gte": fecha_desde}}},
            {"$group": {
                "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$fecha_radicacion"}},
                "cantidad": {"$sum": 1}
            }},
            {"$sort": {"_id": 1}}
        ]
        datos = list(self.repo.coleccion.aggregate(pipeline))
        resultado = [{"fecha": d["_id"], "radicados": d["cantidad"]} for d in datos]
        return pd.DataFrame(resultado) if resultado else pd.DataFrame(columns=["fecha", "radicados"])

    def analisis_tiempos_respuesta(self) -> pd.DataFrame:
        """Calcula el tiempo promedio de respuesta/cierre por tipo de correspondencia."""
        finalizados = self.repo.listar({"estado_actual": {"$in": ["respondido", "archivado", "traslado_competencia"]}}, limit=5000)
        if not finalizados:
            return pd.DataFrame(columns=["tipo", "dias_promedio"])
        
        datos = []
        for c in finalizados:
            f_rad = c.get("fecha_radicacion")
            f_cierre = None
            
            # Prioridad 1: Fecha de salida de la respuesta
            if c.get("estado_actual") == "respondido":
                f_cierre = c.get("respuesta", {}).get("fecha_salida")
            
            # Prioridad 2: Último evento de trazabilidad
            if not f_cierre:
                traz = c.get("trazabilidad", [])
                if traz:
                    f_cierre = traz[-1].get("fecha")
            
            if f_rad and f_cierre:
                if f_rad.tzinfo is None: f_rad = f_rad.replace(tzinfo=timezone.utc)
                if f_cierre.tzinfo is None: f_cierre = f_cierre.replace(tzinfo=timezone.utc)
                
                diff_seg = (f_cierre - f_rad).total_seconds()
                diff_dias = round(diff_seg / (24 * 3600), 1)
                datos.append({"tipo": c.get("tipo", "otro"), "dias": diff_dias})
        
        if not datos:
            return pd.DataFrame(columns=["tipo", "dias_promedio"])
            
        df_tiempos = pd.DataFrame(datos)
        resumen = df_tiempos.groupby("tipo")["dias"].mean().reset_index()
        resumen.columns = ["Tipo", "Días Promedio"]
        resumen["Días Promedio"] = resumen["Días Promedio"].round(1)
        return resumen


