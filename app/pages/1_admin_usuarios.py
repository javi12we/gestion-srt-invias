from app.pages_admin import admin_usuarios
from app.core.sesion import obtener_sesion


def main():
    admin_usuarios.render(obtener_sesion())


if __name__ == "__main__":
    main()
