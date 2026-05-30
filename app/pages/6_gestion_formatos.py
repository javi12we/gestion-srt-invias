from app.pages_admin import admin_formatos
from app.core.sesion import obtener_sesion

admin_formatos.render(obtener_sesion())
