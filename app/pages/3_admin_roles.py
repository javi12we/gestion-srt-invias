from app.pages_admin import admin_roles
from app.core.sesion import obtener_sesion

admin_roles.render(obtener_sesion())
