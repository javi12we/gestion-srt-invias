import os
import io
from datetime import datetime, timezone, timedelta
import pandas as pd
import holidays

from reportlab.lib.pagesizes import letter
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Spacer,
    Paragraph,
    KeepTogether,
    Image
)
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.colors import HexColor

from app.repositories.correspondencia_repo import CorrespondenciaRepositorio

class PDFReportService:
    def __init__(self):
        self.repo = CorrespondenciaRepositorio()
        self.co_holidays = holidays.CO()
        self.ruta_logo = os.path.join("app", "assets", "INVIAS.png")

    def _calcular_dias_habiles(self, fecha_inicio: datetime, fecha_fin: datetime) -> int:
        if not fecha_inicio or not fecha_fin:
            return 0
        if fecha_inicio.tzinfo:
            fecha_inicio = fecha_inicio.replace(tzinfo=None)
        if fecha_fin.tzinfo:
            fecha_fin = fecha_fin.replace(tzinfo=None)
            
        fecha_inicio_date = fecha_inicio.date()
        fecha_fin_date = fecha_fin.date()
        
        if fecha_inicio_date > fecha_fin_date:
            return 0
            
        dias = 0
        actual = fecha_inicio_date
        while actual < fecha_fin_date:
            if actual.weekday() < 5 and actual not in self.co_holidays:
                dias += 1
            actual += timedelta(days=1)
        return dias

    def _fondo_pdf(self, canvas, doc):
        canvas.setFillColor(HexColor("#FFF4E6"))
        canvas.rect(0, 0, doc.pagesize[0], doc.pagesize[1], stroke=0, fill=1)

    def _agregar_logo(self, elementos):
        if os.path.exists(self.ruta_logo):
            logo = Image(self.ruta_logo)
            logo.drawHeight = 60
            logo.drawWidth = 160
            logo.hAlign = "CENTER"
            elementos.append(logo)
            elementos.append(Spacer(1, 15))

    def _obtener_datos_activos(self) -> list:
        return self.repo.listar({"estado_actual": {"$in": ["pendiente", "en_tramite", "en_revision"]}}, limit=10000)

    def _construir_tabla_resumen(self, df_reporte, col_usuario):
        if df_reporte.empty:
            return None
        
        resumen = df_reporte[col_usuario].value_counts().reset_index()
        resumen.columns = ["Usuario Responsable", "Atrasados"]
        
        data_resumen = [resumen.columns.tolist()] + resumen.astype(str).values.tolist()
        tabla = Table(data_resumen, repeatRows=1)
        
        tabla.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.orange),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ALIGN", (1, 1), (-1, -1), "CENTER"),
        ]))
        return tabla

    def generar_pdf_pqrd(self) -> io.BytesIO:
        buffer = io.BytesIO()
        fecha_hoy = datetime.now().strftime("%Y-%m-%d")
        hoy = datetime.now(timezone.utc)
        
        datos = self._obtener_datos_activos()
        filas = []
        
        for doc in datos:
            # Fix Problema 2: Permitir "pqrds" o "pqrd"
            if "PQRD" not in str(doc.get("tipo", "")).upper():
                continue
                
            responsable = doc.get("responsable_actual", {}).get("nombre", "Sin Asignar")
            if not responsable or responsable.strip() == "Gladys Gutierrez Buitrago":
                continue
                
            f_vencimiento = doc.get("fecha_vencimiento")
            if not f_vencimiento:
                continue
            
            if isinstance(f_vencimiento, datetime):
                if f_vencimiento.tzinfo is None:
                    f_vencimiento = f_vencimiento.replace(tzinfo=timezone.utc)
                if f_vencimiento.tzinfo != timezone.utc:
                    f_vencimiento = f_vencimiento.astimezone(timezone.utc)
            
            # Calcular días de atraso en días completos/calendario
            if hoy > f_vencimiento:
                dias_retraso = (hoy - f_vencimiento).days
                if dias_retraso > 0:
                    filas.append({
                        "NO. RADICADO": doc.get("numero_radicado", "S/N"),
                        "Usuario Responsable": responsable,
                        "Días sin respuesta": dias_retraso
                    })
                
        df_reporte = pd.DataFrame(filas)
        if not df_reporte.empty:
            df_reporte = df_reporte.sort_values(by="Días sin respuesta", ascending=False)
            
        styles = getSampleStyleSheet()
        elementos = []
        
        self._agregar_logo(elementos)
        
        titulo = Paragraph(f"<b>Reporte VUVR PQRD ({fecha_hoy})</b>", styles["Title"])
        elementos.append(titulo)
        elementos.append(Spacer(1, 25))
        
        elementos.append(Paragraph("<b>1. Resumen</b>", styles["Heading2"]))
        elementos.append(Spacer(1, 10))
        tabla_resumen = self._construir_tabla_resumen(df_reporte, "Usuario Responsable")
        if tabla_resumen:
            elementos.append(tabla_resumen)
        else:
            elementos.append(Paragraph("No hay radicados PQRD atrasados.", styles["Normal"]))
        elementos.append(Spacer(1, 30))
        
        elementos.append(Paragraph("<b>2. Reporte Detallado</b>", styles["Heading2"]))
        elementos.append(Spacer(1, 10))
        
        if df_reporte.empty:
            elementos.append(Paragraph("No hay datos para el reporte detallado.", styles["Normal"]))
        else:
            data_reporte = [df_reporte.columns.tolist()] + df_reporte.astype(str).values.tolist()
            tabla_reporte = Table(data_reporte, repeatRows=1)
            
            estilos = [
                ("BACKGROUND", (0, 0), (-1, 0), colors.orange),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (2, 1), (2, -1), "CENTER"),
            ]
            
            col_index = 2
            for i, fila in enumerate(data_reporte[1:], start=1):
                try:
                    dias = int(fila[col_index])
                    if dias <= 14:
                        estilos.append(("BACKGROUND", (col_index, i), (col_index, i), HexColor("#C6EFCE")))
                    elif 15 <= dias <= 20:
                        estilos.append(("BACKGROUND", (col_index, i), (col_index, i), HexColor("#FFF2CC")))
                    elif dias > 20:
                        estilos.append(("BACKGROUND", (col_index, i), (col_index, i), HexColor("#F8CBAD")))
                except:
                    pass
                    
            tabla_reporte.setStyle(TableStyle(estilos))
            elementos.append(tabla_reporte)
            
        pdf = SimpleDocTemplate(buffer, pagesize=letter)
        pdf.build(elementos, onFirstPage=self._fondo_pdf, onLaterPages=self._fondo_pdf)
        
        buffer.seek(0)
        return buffer

    def generar_pdf_conglomerado(self) -> io.BytesIO:
        from reportlab.platypus import PageBreak
        buffer = io.BytesIO()
        fecha_hoy = datetime.now().strftime("%Y-%m-%d")
        hoy = datetime.now(timezone.utc)
        
        datos = self._obtener_datos_activos()
        filas = []
        
        for doc in datos:
            responsable = doc.get("responsable_actual", {}).get("nombre", "Sin Asignar")
            if not responsable or responsable.strip() == "Gladys Gutierrez Buitrago":
                continue
                
            f_vencimiento = doc.get("fecha_vencimiento")
            if not f_vencimiento:
                continue
            
            if isinstance(f_vencimiento, datetime):
                if f_vencimiento.tzinfo is None:
                    f_vencimiento = f_vencimiento.replace(tzinfo=timezone.utc)
                if f_vencimiento.tzinfo != timezone.utc:
                    f_vencimiento = f_vencimiento.astimezone(timezone.utc)
            
            # Calcular días de atraso en días completos/calendario
            if hoy > f_vencimiento:
                dias_retraso = (hoy - f_vencimiento).days
                if dias_retraso > 0:
                    filas.append({
                        "No. Radicado": doc.get("numero_radicado", "S/N"),
                        "Usuario Responsable": responsable,
                        "Días sin respuesta": dias_retraso
                    })
                
        df_reporte = pd.DataFrame(filas)
        
        styles = getSampleStyleSheet()
        elementos = []
        
        self._agregar_logo(elementos)
        
        titulo = Paragraph(f"<b>Reporte Matriz de asignación a la correspondencia ({fecha_hoy}) SRTI</b>", styles["Title"])
        elementos.append(titulo)
        elementos.append(Spacer(1, 25))
        
        elementos.append(Paragraph("<b>1. Resumen</b>", styles["Heading2"]))
        elementos.append(Spacer(1, 10))
        tabla_resumen = self._construir_tabla_resumen(df_reporte, "Usuario Responsable")
        if tabla_resumen:
            elementos.append(tabla_resumen)
        else:
            elementos.append(Paragraph("No hay radicados activos atrasados.", styles["Normal"]))
        elementos.append(Spacer(1, 30))
        
        elementos.append(Paragraph("<b>2. Reporte Detallado</b>", styles["Heading2"]))
        elementos.append(Spacer(1, 10))
        
        if df_reporte.empty:
            elementos.append(Paragraph("No hay datos para el reporte detallado.", styles["Normal"]))
        else:
            usuarios = df_reporte["Usuario Responsable"].unique()
            for usuario in sorted(usuarios):
                df_usuario = df_reporte[df_reporte["Usuario Responsable"] == usuario]
                df_usuario = df_usuario.sort_values(by="Días sin respuesta", ascending=False)
                
                subtitulo = Paragraph(f"<b>Nombre: {usuario}</b>", styles["Heading3"])
                
                data = [df_usuario.columns.tolist()] + df_usuario.astype(str).values.tolist()
                tabla = Table(data)
                
                estilos = [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.orange),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("ALIGN", (2, 1), (2, -1), "CENTER"),
                ]
                
                for i, fila in enumerate(data[1:], start=1):
                    try:
                        dias = int(fila[2])
                        if 10 <= dias <= 14:
                            estilos.append(("BACKGROUND", (2, i), (2, i), HexColor("#C6EFCE")))
                        elif 15 <= dias <= 20:
                            estilos.append(("BACKGROUND", (2, i), (2, i), HexColor("#FFF2CC")))
                        elif dias > 20:
                            estilos.append(("BACKGROUND", (2, i), (2, i), HexColor("#F8CBAD")))
                    except:
                        pass
                
                tabla.setStyle(TableStyle(estilos))
                
                bloque = KeepTogether([
                    subtitulo,
                    Spacer(1, 10),
                    tabla,
                    Spacer(1, 30)
                ])
                elementos.append(bloque)
                
        pdf = SimpleDocTemplate(buffer, pagesize=letter)
        pdf.build(elementos, onFirstPage=self._fondo_pdf, onLaterPages=self._fondo_pdf)
        
        buffer.seek(0)
        return buffer
