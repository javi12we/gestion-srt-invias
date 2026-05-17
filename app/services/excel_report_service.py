import io
from datetime import datetime, timezone
import pandas as pd
from app.repositories.correspondencia_repo import CorrespondenciaRepositorio

class ExcelReportService:
    def __init__(self):
        self.repo = CorrespondenciaRepositorio()

    def _obtener_datos_kawak(self) -> list:
        # Filtros: PQRD, Permisos, Cerrados (respondido, pero no archivado ni traslado)
        query = {
            "estado_actual": "respondido",
            "grupo": {"$regex": "^permisos$", "$options": "i"}
        }
        
        docs = self.repo.listar(query, limit=10000)
        
        datos_filtrados = []
        for doc in docs:
            if "PQRD" not in str(doc.get("tipo", "")).upper():
                continue
                
            datos_filtrados.append(doc)
            
        return datos_filtrados

    def generar_excel_kawak(self) -> tuple[io.BytesIO, str]:
        buffer = io.BytesIO()
        hoy = datetime.now()
        
        # Calcular Trimestre (Q1, Q2, Q3, Q4)
        trimestre = (hoy.month - 1) // 3 + 1
        
        fecha_str = hoy.strftime("%Y-%m-%d")
        nombre_archivo = f"PQRD - Permisos T{trimestre} {fecha_str}.xlsx"
        
        datos = self._obtener_datos_kawak()
        
        filas = []
        for doc in datos:
            radicado = doc.get("numero_radicado", "S/N")
            
            f_radicacion = doc.get("fecha_radicacion")
            f_rad_str = f_radicacion.strftime("%Y-%m-%d") if f_radicacion else ""
            
            peticionario_raw = doc.get("peticionario", {})
            peticionario = peticionario_raw.get("nombre", "") if isinstance(peticionario_raw, dict) else str(peticionario_raw)
            
            asunto = doc.get("asunto", "")
            estado = str(doc.get("estado_actual", "")).capitalize()
            
            responsable_raw = doc.get("responsable_actual", {})
            responsable = responsable_raw.get("nombre", "Sin Asignar") if isinstance(responsable_raw, dict) else str(responsable_raw)
            
            respuesta_obj = doc.get("respuesta", {})
            if isinstance(respuesta_obj, dict):
                respuesta = respuesta_obj.get("numero_oficio", "")
                f_respuesta = respuesta_obj.get("fecha_salida")
            else:
                respuesta = str(respuesta_obj)
                f_respuesta = None
                
            f_resp_str = f_respuesta.strftime("%Y-%m-%d") if f_respuesta else ""
            
            clase_raw = doc.get("clase", "")
            clase_limpia = str(clase_raw).replace("_", " ").capitalize() if clase_raw else "Sin clase"
            
            filas.append({
                "Radicado": radicado,
                "F.Radicado": f_rad_str,
                "Peticionario": peticionario,
                "Asunto": asunto,
                "Estado": estado,
                "Responsable": responsable,
                "Respuesta": respuesta,
                "Fecha de respuesta": f_resp_str,
                "Clase": clase_limpia
            })
            
        df = pd.DataFrame(filas)
        
        if df.empty:
            df = pd.DataFrame(columns=["Radicado", "F.Radicado", "Peticionario", "Asunto", "Estado", "Responsable", "Respuesta", "Fecha de respuesta", "Clase"])
            
        with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
            df.to_excel(writer, sheet_name="PQRD", index=False)
            
            workbook = writer.book
            worksheet = writer.sheets["PQRD"]
            
            # Estilos
            header_format = workbook.add_format({
                "bold": True,
                "font_color": "white",
                "bg_color": "#E26B0A",
                "align": "center",
                "valign": "vcenter",
                "border": 1,
                "font_size": 10
            })
            
            cell_format = workbook.add_format({
                "border": 1,
                "valign": "vcenter",
                "text_wrap": True,
                "font_size": 10
            })
            
            # Aplicar estilos a cabeceras
            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_format)
                
            # Aplicar formato de datos y ajustar ancho
            for col_num, col_name in enumerate(df.columns):
                # Calcular ancho basado en la cabecera y en los datos
                max_len = max([len(str(val)) for val in df[col_name]] + [len(col_name)]) if not df.empty else len(col_name)
                
                if col_name == "Asunto":
                    nuevo_ancho = min((max_len + 4) * 2, 120)  # Doble para Asunto (con tope más alto)
                else:
                    nuevo_ancho = min(max_len + 4, 60)         # Normal para el resto
                    
                worksheet.set_column(col_num, col_num, nuevo_ancho)
                
            # Autofiltro y sobreescribir datos con bordes
            if not df.empty:
                worksheet.autofilter(0, 0, len(df), len(df.columns) - 1)
                for row_num in range(1, len(df) + 1):
                    for col_num in range(len(df.columns)):
                        worksheet.write(row_num, col_num, df.iloc[row_num - 1, col_num], cell_format)
                
            # Tabla de resumen a la derecha
            import os
            start_col = len(df.columns) + 1
            
            # Insertar logo INVIAS
            logo_path = os.path.join("app", "assets", "INVIAS.png")
            if os.path.exists(logo_path):
                worksheet.insert_image(0, start_col, logo_path, {'x_scale': 0.12, 'y_scale': 0.12})
                
            # Desplazar la tabla de resumen hacia abajo
            row_offset = 7
            worksheet.write(row_offset, start_col, "Resumen por Clase", header_format)
            worksheet.write(row_offset, start_col + 1, "Cantidad", header_format)
            
            if not df.empty:
                resumen = df["Clase"].value_counts().reset_index()
                resumen.columns = ["Clase", "Cantidad"]
                
                for row_num, (index, row) in enumerate(resumen.iterrows(), start=row_offset + 1):
                    worksheet.write(row_num, start_col, str(row["Clase"]), cell_format)
                    worksheet.write(row_num, start_col + 1, row["Cantidad"], cell_format)
                
                worksheet.set_column(start_col, start_col, 25) # Ancho leíble fijo para el título
                worksheet.set_column(start_col + 1, start_col + 1, 15)
            else:
                worksheet.write(row_offset + 1, start_col, "Sin datos", cell_format)
                worksheet.write(row_offset + 1, start_col + 1, 0, cell_format)
                worksheet.set_column(start_col, start_col, 25)
                worksheet.set_column(start_col + 1, start_col + 1, 15)
                
        buffer.seek(0)
        return buffer, nombre_archivo
