import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.pages_admin import admin_grupos
from app.core.sesion import obtener_sesion

admin_grupos.render(obtener_sesion())
