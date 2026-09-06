import io
from datetime import datetime, timezone
import pandas as pd
from app.repositories.correspondencia_repo import CorrespondenciaRepositorio
from app.repositories.usuario_repo import UsuarioRepositorio

class ExcelReportService:
    def __init__(self):
        self.repo = CorrespondenciaRepositorio()

    def _obtener_datos_kawak(self, anio: int, trimestre: int) -> list:
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
                
            f_rad = doc.get("fecha_radicacion")
            f_resp = doc.get("respuesta", {}).get("fecha_salida") if isinstance(doc.get("respuesta"), dict) else None
            
            # Usar fecha de respuesta si está disponible, o fecha de radicación en su defecto
            fecha_ref = f_resp or f_rad
            if not fecha_ref:
                continue
                
            ref_year = fecha_ref.year
            ref_trimestre = (fecha_ref.month - 1) // 3 + 1
            
            if ref_year == anio and ref_trimestre == trimestre:
                datos_filtrados.append(doc)
            
        return datos_filtrados

    def _construir_dataframe(self, datos: list) -> pd.DataFrame:
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
            
            grupo_raw = doc.get("grupo", "")
            grupo_map = {
                "despacho": "DESPACHO",
                "normativa": "NORMATIVA",
                "normativa_tecnica": "NORMATIVA",
                "innovacion": "INNOVACIÓN",
                "innovacion_tecnica": "INNOVACIÓN",
                "permisos": "PERMISOS"
            }
            grupo_limpio = grupo_map.get(str(grupo_raw).lower(), str(grupo_raw).upper()) if grupo_raw else "SIN GRUPO"
            
            filas.append({
                "Radicado": radicado,
                "F.Radicado": f_rad_str,
                "Peticionario": peticionario,
                "Asunto": asunto,
                "Estado": estado,
                "Responsable": responsable,
                "Respuesta": respuesta,
                "Fecha de respuesta": f_resp_str,
                "Grupo": grupo_limpio,
                "Clase": clase_limpia
            })
            
        df = pd.DataFrame(filas)

        if df.empty:
            df = pd.DataFrame(columns=["Radicado", "F.Radicado", "Peticionario", "Asunto", "Estado", "Responsable", "Respuesta", "Fecha de respuesta", "Grupo", "Clase"])

        return df

    def _escribir_hoja(self, writer, workbook, sheet_name: str, df: pd.DataFrame, datos: list,
                        incluir_resumen_extra: bool = False, filtro_estado_activo: bool = False) -> None:
            df.to_excel(writer, sheet_name=sheet_name, index=False)

            worksheet = writer.sheets[sheet_name]

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
                "align": "center",
                "text_wrap": True,
                "font_size": 10
            })
            
            # Aplicar estilos a cabeceras y establecer su altura
            worksheet.set_row(0, 37.5)
            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_format)
                
            # Aplicar formato de datos y ajustar ancho
            for col_num, col_name in enumerate(df.columns):
                max_len = max([len(str(val)) for val in df[col_name]] + [len(col_name)]) if not df.empty else len(col_name)
                
                if col_name == "Asunto":
                    nuevo_ancho = 45.57
                elif col_name in ("Respuesta", "Fecha de respuesta"):
                    nuevo_ancho = 27.71
                elif col_name == "Grupo":
                    nuevo_ancho = 18.0
                else:
                    nuevo_ancho = min(max_len + 4, 60)
                    
                worksheet.set_column(col_num, col_num, nuevo_ancho)

            # Autofiltro y sobreescribir datos con bordes y altura de fila
            if not df.empty:
                worksheet.autofilter(0, 0, len(df), len(df.columns) - 1)

                if filtro_estado_activo and "Estado" in df.columns:
                    estado_col_idx = df.columns.get_loc("Estado")
                    worksheet.filter_column(estado_col_idx, 'x == "En_tramite"')

                for row_num in range(1, len(df) + 1):
                    fila_oculta = filtro_estado_activo and str(df.iloc[row_num - 1]["Estado"]) != "En_tramite"
                    if fila_oculta:
                        worksheet.set_row(row_num, 37.5, None, {"hidden": True})
                    else:
                        worksheet.set_row(row_num, 37.5)
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
            row_offset = 3
            worksheet.write(row_offset, start_col, "Resumen por Clase", header_format)
            worksheet.write(row_offset, start_col + 1, "Cantidad", header_format)
            
            if not df.empty:
                resumen = df["Clase"].value_counts().reset_index()
                resumen.columns = ["Clase", "Cantidad"]
                
                for row_num, (index, row) in enumerate(resumen.iterrows(), start=row_offset + 1):
                    worksheet.write(row_num, start_col, str(row["Clase"]), cell_format)
                    worksheet.write(row_num, start_col + 1, row["Cantidad"], cell_format)
                
                worksheet.set_column(start_col, start_col, 25)
                worksheet.set_column(start_col + 1, start_col + 1, 15)
            else:
                worksheet.write(row_offset + 1, start_col, "Sin datos", cell_format)
                worksheet.write(row_offset + 1, start_col + 1, 0, cell_format)
                worksheet.set_column(start_col, start_col, 25)
                worksheet.set_column(start_col + 1, start_col + 1, 15)

            if incluir_resumen_extra:
                # Columna O/P: resumen por tipo de correspondencia (PQRD/Memorandos/Oficios)
                start_col_tipo = start_col + 3
                worksheet.write(row_offset, start_col_tipo, "Tipo", header_format)
                worksheet.write(row_offset, start_col_tipo + 1, "Cantidad", header_format)

                tipo_map = {"pqrds": "PQRD", "memorandos": "MEMORANDOS", "oficios": "OFICIOS"}
                tipos_limpios = [
                    tipo_map.get(str(doc.get("tipo", "")).lower(), "SIN TIPO")
                    for doc in datos
                ]
                resumen_tipo = pd.Series(tipos_limpios, dtype=object).value_counts().reset_index()
                resumen_tipo.columns = ["Tipo", "Cantidad"]

                if not resumen_tipo.empty:
                    for row_num, (_, row) in enumerate(resumen_tipo.iterrows(), start=row_offset + 1):
                        worksheet.write(row_num, start_col_tipo, str(row["Tipo"]), cell_format)
                        worksheet.write(row_num, start_col_tipo + 1, row["Cantidad"], cell_format)
                else:
                    worksheet.write(row_offset + 1, start_col_tipo, "Sin datos", cell_format)
                    worksheet.write(row_offset + 1, start_col_tipo + 1, 0, cell_format)

                worksheet.set_column(start_col_tipo, start_col_tipo, 25)
                worksheet.set_column(start_col_tipo + 1, start_col_tipo + 1, 15)

                # Columna R/S: resumen por responsable (deja Q vacía como separador con la tabla de Tipo)
                start_col_resp = start_col_tipo + 3
                worksheet.write(row_offset, start_col_resp, "Responsable", header_format)
                worksheet.write(row_offset, start_col_resp + 1, "Cantidad", header_format)

                if not df.empty:
                    resumen_resp = df["Responsable"].value_counts().reset_index()
                    resumen_resp.columns = ["Responsable", "Cantidad"]
                    for row_num, (_, row) in enumerate(resumen_resp.iterrows(), start=row_offset + 1):
                        worksheet.write(row_num, start_col_resp, str(row["Responsable"]), cell_format)
                        worksheet.write(row_num, start_col_resp + 1, row["Cantidad"], cell_format)
                else:
                    worksheet.write(row_offset + 1, start_col_resp, "Sin datos", cell_format)
                    worksheet.write(row_offset + 1, start_col_resp + 1, 0, cell_format)

                worksheet.set_column(start_col_resp, start_col_resp, 25)
                worksheet.set_column(start_col_resp + 1, start_col_resp + 1, 15)

    def _crear_excel_reporte(self, datos: list, sheet_name: str, incluir_resumen_extra: bool = False) -> io.BytesIO:
        buffer = io.BytesIO()
        df = self._construir_dataframe(datos)

        with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
            self._escribir_hoja(writer, writer.book, sheet_name, df, datos, incluir_resumen_extra=incluir_resumen_extra)

        buffer.seek(0)
        return buffer

    def generar_excel_kawak(self, anio: int, trimestre: int) -> tuple[io.BytesIO, str]:
        hoy = datetime.now()
        fecha_str = hoy.strftime("%Y-%m-%d")
        nombre_archivo = f"PQRD - Permisos T{trimestre} {anio} {fecha_str}.xlsx"
        
        datos = self._obtener_datos_kawak(anio, trimestre)
        buffer = self._crear_excel_reporte(datos, "PQRD")
        return buffer, nombre_archivo

    def _obtener_datos_kawak_general(self, anio: int, trimestre: int) -> list:
        # Filtros: PQRD, Cerrados (respondido, pero no archivado ni traslado) - SIN filtro de grupo permisos
        query = {
            "estado_actual": "respondido"
        }
        
        docs = self.repo.listar(query, limit=10000)
        
        datos_filtrados = []
        for doc in docs:
            if "PQRD" not in str(doc.get("tipo", "")).upper():
                continue
                
            f_rad = doc.get("fecha_radicacion")
            f_resp = doc.get("respuesta", {}).get("fecha_salida") if isinstance(doc.get("respuesta"), dict) else None
            
            # Usar fecha de respuesta si está disponible, o fecha de radicación en su defecto
            fecha_ref = f_resp or f_rad
            if not fecha_ref:
                continue
                
            ref_year = fecha_ref.year
            ref_trimestre = (fecha_ref.month - 1) // 3 + 1
            
            if ref_year == anio and ref_trimestre == trimestre:
                datos_filtrados.append(doc)
            
        return datos_filtrados

    def generar_excel_kawak_general(self, anio: int, trimestre: int) -> tuple[io.BytesIO, str]:
        hoy = datetime.now()
        fecha_str = hoy.strftime("%Y-%m-%d")
        nombre_archivo = f"Conglomerado PQRD - Grupos Trimestral T{trimestre} {anio} {fecha_str}.xlsx"
        
        datos = self._obtener_datos_kawak_general(anio, trimestre)
        buffer = self._crear_excel_reporte(datos, "PQRD")
        return buffer, nombre_archivo

    def _obtener_datos_consolidado_anual(self, anio: int) -> list:
        start_date = datetime(anio, 1, 1)
        end_date = datetime(anio + 1, 1, 1)
        query = {
            "fecha_radicacion": {
                "$gte": start_date,
                "$lt": end_date
            }
        }
        return self.repo.listar(query, limit=10000)

    def generar_excel_consolidado_anual(self, anio: int) -> tuple[io.BytesIO, str]:
        hoy = datetime.now()
        fecha_str = hoy.strftime("%Y-%m-%d")
        nombre_archivo = f"Consolidado Correspondencia Anual {anio} {fecha_str}.xlsx"
        
        datos = self._obtener_datos_consolidado_anual(anio)
        buffer = self._crear_excel_reporte(datos, "Correspondencia", incluir_resumen_extra=True)
        return buffer, nombre_archivo

    def _nombre_hoja_valido(self, nombre: str, usados: set) -> str:
        caracteres_invalidos = ["\\", "/", "?", "*", "[", "]", ":"]
        limpio = nombre
        for c in caracteres_invalidos:
            limpio = limpio.replace(c, "")
        limpio = limpio.strip()[:31] or "Sin Nombre"

        base = limpio
        contador = 2
        while limpio.lower() in usados:
            sufijo = f" ({contador})"
            limpio = base[:31 - len(sufijo)] + sufijo
            contador += 1

        usados.add(limpio.lower())
        return limpio

    def generar_excel_conglomerado_persona(self, anio: int) -> tuple[io.BytesIO, str]:
        hoy = datetime.now()
        fecha_str = hoy.strftime("%Y-%m-%d")
        nombre_archivo = f"Conglomerado Correspondencia por Persona {anio} {fecha_str}.xlsx"

        datos = self._obtener_datos_consolidado_anual(anio)

        grupos = {}
        for doc in datos:
            responsable_raw = doc.get("responsable_actual", {})
            nombre_resp = responsable_raw.get("nombre", "Sin Asignar") if isinstance(responsable_raw, dict) else str(responsable_raw)
            if not nombre_resp:
                nombre_resp = "Sin Asignar"
            grupos.setdefault(nombre_resp, []).append(doc)

        if not grupos:
            grupos = {"Sin datos": []}

        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
            workbook = writer.book
            nombres_hoja_usados = set()
            for nombre_resp in sorted(grupos.keys(), key=lambda n: n.lower()):
                datos_persona = grupos[nombre_resp]
                df_persona = self._construir_dataframe(datos_persona)
                nombre_hoja = self._nombre_hoja_valido(nombre_resp, nombres_hoja_usados)
                self._escribir_hoja(
                    writer, workbook, nombre_hoja, df_persona, datos_persona,
                    incluir_resumen_extra=True, filtro_estado_activo=True
                )

        buffer.seek(0)
        return buffer, nombre_archivo

    def generar_excel_usuarios(self) -> tuple[io.BytesIO, str]:
        hoy = datetime.now()
        fecha_str = hoy.strftime("%Y-%m-%d")
        nombre_archivo = f"Reporte_Usuarios_Registrados_{fecha_str}.xlsx"
        
        repo_usr = UsuarioRepositorio()
        usuarios = repo_usr.listar()
        
        import pytz
        ZONA_BOGOTA = pytz.timezone("America/Bogota")
        hoy_bog = datetime.now(ZONA_BOGOTA).date()
        
        filas = []
        con_contrato_count = 0
        sin_contrato_count = 0
        
        for u in usuarios:
            usuario = u.get("usuario", "")
            nombre = u.get("nombre_completo", "")
            email = u.get("email", "")
            
            tipo_doc = u.get("tipo_documento") or ""
            num_doc = u.get("numero_documento") or ""
            documento = f"{tipo_doc} {num_doc}".strip() if (tipo_doc or num_doc) else "—"
            
            roles_list = u.get("roles") or []
            roles = ", ".join(roles_list).upper() if roles_list else "—"
            
            info_laboral = u.get("informacion_laboral") or {}
            grupo_trabajo_raw = info_laboral.get("grupo_trabajo") or ""
            grupo_trabajo_map = {
                "despacho": "DESPACHO",
                "normativa": "NORMATIVA",
                "normativa_tecnica": "NORMATIVA",
                "innovacion": "INNOVACIÓN",
                "innovacion_tecnica": "INNOVACIÓN",
                "permisos": "PERMISOS"
            }
            grupo_trabajo = grupo_trabajo_map.get(str(grupo_trabajo_raw).lower(), str(grupo_trabajo_raw).upper()) if grupo_trabajo_raw else "SIN ESPECIFICAR"
            
            estado_usr = "ACTIVO" if u.get("activo") else "INACTIVO"
            
            # Verificar si tiene contrato activo
            tiene_activo = False
            contratos = u.get("contratos") or []
            ultimo_contrato_num = "—"
            
            # Encontrar el último por fecha de inicio para mostrar en la columna
            if contratos:
                def parse_fecha(c):
                    return c.get("fecha_inicio") or datetime.min
                contratos_ordenados = sorted(contratos, key=parse_fecha, reverse=True)
                ultimo_contrato_num = contratos_ordenados[0].get("numero", "—")
                
            for c in contratos:
                fecha_fin = c.get("fecha_fin")
                if not fecha_fin:
                    tiene_activo = True
                    break
                else:
                    if fecha_fin.tzinfo is None:
                        fecha_fin = fecha_fin.replace(tzinfo=timezone.utc)
                    if fecha_fin.astimezone(ZONA_BOGOTA).date() >= hoy_bog:
                        tiene_activo = True
                        break
            
            if tiene_activo:
                con_contrato_count += 1
                vigencia_contrato = "ACTIVO"
            else:
                sin_contrato_count += 1
                vigencia_contrato = "SIN CONTRATO ACTIVO"
                
            filas.append({
                "Usuario": usuario,
                "Nombre Completo": nombre,
                "Email": email,
                "Documento": documento,
                "Roles": roles,
                "Grupo Trabajo": grupo_trabajo,
                "Estado Usuario": estado_usr,
                "Último Contrato": ultimo_contrato_num,
                "Vigencia Contrato": vigencia_contrato
            })
            
        df = pd.DataFrame(filas)
        if df.empty:
            df = pd.DataFrame(columns=["Usuario", "Nombre Completo", "Email", "Documento", "Roles", "Grupo Trabajo", "Estado Usuario", "Último Contrato", "Vigencia Contrato"])
            
        buffer = io.BytesIO()
        sheet_name = "Usuarios"
        with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
            df.to_excel(writer, sheet_name=sheet_name, index=False)
            
            workbook = writer.book
            worksheet = writer.sheets[sheet_name]
            
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
                "align": "center",
                "text_wrap": True,
                "font_size": 10
            })
            
            # Aplicar estilos a cabeceras y establecer su altura
            worksheet.set_row(0, 37.5)
            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_format)
                
            # Aplicar formato de datos y ajustar ancho
            for col_num, col_name in enumerate(df.columns):
                max_len = max([len(str(val)) for val in df[col_name]] + [len(col_name)]) if not df.empty else len(col_name)
                
                if col_name == "Nombre Completo":
                    nuevo_ancho = 35.0
                elif col_name == "Email":
                    nuevo_ancho = 30.0
                elif col_name == "Grupo Trabajo":
                    nuevo_ancho = 20.0
                else:
                    nuevo_ancho = min(max_len + 4, 60)
                    
                worksheet.set_column(col_num, col_num, nuevo_ancho)
                
            # Autofiltro y sobreescribir datos con bordes y altura de fila
            if not df.empty:
                worksheet.autofilter(0, 0, len(df), len(df.columns) - 1)
                for row_num in range(1, len(df) + 1):
                    worksheet.set_row(row_num, 37.5)
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
            row_offset = 3
            worksheet.write(row_offset, start_col, "Resumen de Contratos", header_format)
            worksheet.write(row_offset, start_col + 1, "Cantidad", header_format)
            
            # Escribir filas del resumen
            worksheet.write(row_offset + 1, start_col, "Con contrato activo", cell_format)
            worksheet.write(row_offset + 1, start_col + 1, con_contrato_count, cell_format)
            
            worksheet.write(row_offset + 2, start_col, "Sin contrato activo", cell_format)
            worksheet.write(row_offset + 2, start_col + 1, sin_contrato_count, cell_format)
            
            worksheet.set_column(start_col, start_col, 25)
            worksheet.set_column(start_col + 1, start_col + 1, 15)
            
        buffer.seek(0)
        return buffer, nombre_archivo
