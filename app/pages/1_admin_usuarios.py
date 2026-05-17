from app.pages_admin import admin_usuarios
from app.core.sesion import obtener_sesion

admin_usuarios.render(obtener_sesion())
