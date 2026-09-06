import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.pages_admin import gestores_permisos
from app.core.sesion import obtener_sesion

gestores_permisos.render(obtener_sesion())
