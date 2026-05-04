from app.pages_admin import admin_roles
from app.core.sesion import obtener_sesion


def main():
    admin_roles.render(obtener_sesion())


if __name__ == "__main__":
    main()
