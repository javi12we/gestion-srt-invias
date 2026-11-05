"""Script de inicialización de la base de datos Mongo.

Ejecuta:
- aseguramiento de colecciones e índices (MongoBootstrapService)
- inserción de roles y permisos base (CatalogoService)
- creación del admin inicial si ADMIN_INICIAL_PASSWORD está definido
- semilla de política de tratamiento de datos v1 (idempotente)

Usage:
    python -m app.scripts.init_db
"""

import datetime

from app.services.mongo_bootstrap_service import MongoBootstrapService
from app.services.catalogo_service import CatalogoService
from app.services.usuario_service import UsuarioService
from app.services.politica_service import PoliticaService
from app.services.instructivo_service import InstructivoService
from app.db.mongo import obtener_base_datos
from app.core.catalogos import GRUPOS_TRABAJO_BASE
from app.repositories.grupo_repo import GrupoRepositorio
from app.config import configuracion

CONTENIDO_POLITICA_V1 = """
<p style="font-size:14.5px; line-height:1.75; color:#222222; text-align:justify; margin-bottom:14px;">
    El aplicativo <strong style="color:#E67A00;">"Gestiones correspondencia SRTI"</strong>
    recopila y almacena datos personales y administrativos suministrados por sus usuarios,
    tales como nombre, identificación, correo electrónico, información contractual,
    información de correspondencia y demás datos necesarios para el funcionamiento de la
    plataforma.
</p>
<p style="font-size:14.5px; line-height:1.75; color:#222222; text-align:justify; margin-bottom:14px;">
    Esta información será utilizada <strong style="color:#222222;">exclusivamente</strong> para fines relacionados
    con la gestión, administración, seguimiento y operación del aplicativo, así como para
    garantizar la seguridad, trazabilidad y correcto uso de los servicios ofrecidos de
    forma interna.
</p>
<p style="font-size:14.5px; line-height:1.75; color:#222222; text-align:justify; margin-bottom:14px;">
    Los datos serán tratados de manera <strong style="color:#222222;">confidencial</strong> y se adoptarán medidas
    razonables para protegerlos contra el acceso, uso, modificación o divulgación no
    autorizada. La información <strong style="color:#222222;">no será compartida con terceros</strong>.
</p>
<p style="font-size:14.5px; line-height:1.75; color:#222222; text-align:justify; margin-bottom:14px;">
    Al registrarse, acceder o utilizar el Aplicativo
    <strong style="color:#E67A00;">"Gestiones correspondencia SRTI"</strong>, el usuario
    declara haber leído y aceptado la presente política, autorizando de manera
    <em style="color:#444444;">libre, previa, expresa e informada</em> el tratamiento de sus datos personales
    para las finalidades aquí descritas.
</p>
<div style="
    margin-top:4px; margin-bottom:18px;
    padding: 12px 16px;
    background: rgba(255,140,0,0.10);
    border-left: 3px solid #FF8C00;
    border-radius: 0 8px 8px 0;
    font-size: 13px;
    color: #C05E00;
    font-style: italic;
    font-weight: 600;
">
    ⚠️ La aceptación de esta política es requisito para el acceso y uso del Aplicativo SRTI.
</div>
""".strip()


def _asegurar_politica_v1() -> None:
    """Inserta la política v1 si no existe ninguna versión en la BD."""
    svc = PoliticaService()
    versiones = svc.listar_versiones()
    if versiones:
        print(f"  Política ya existe ({len(versiones)} versión(es)). No se siembra de nuevo.")
        return

    ahora = datetime.datetime.now(datetime.timezone.utc)
    svc.repo.crear_politica({
        "numero_version": 1,
        "titulo": "Política de Tratamiento de Datos Personales",
        "contenido": CONTENIDO_POLITICA_V1,
        "activa": True,
        "fecha_vigencia": ahora,
        "fecha_creacion": ahora,
        "creada_por": "sistema",
    })
    print("  Política de tratamiento de datos v1 sembrada.")


def _asegurar_instructivos_iniciales() -> None:
    """Migra los instructivos del .env a MongoDB si la colección está vacía."""
    svc = InstructivoService()
    if svc.hay_instructivos():
        print("  Instructivos ya existen en la BD. No se siembran de nuevo.")
        return

    sembrados = 0
    if configuracion.instructivo_pdf_url:
        svc.crear(
            titulo="Instructivo Matriz de correspondencia SRTI",
            url=configuracion.instructivo_pdf_url,
            tipo="pdf",
            icono="📄",
            embed_height=850,
            creado_por="sistema",
        )
        sembrados += 1

    if configuracion.instructivo_video_url:
        svc.crear(
            titulo="Capacitación Matriz de correspondencia SRTI",
            url=configuracion.instructivo_video_url,
            tipo="video",
            icono="▶️",
            embed_height=540,
            creado_por="sistema",
        )
        sembrados += 1

    if sembrados:
        print(f"  {sembrados} instructivo(s) sembrado(s) desde configuración .env.")
    else:
        print("  No hay URLs de instructivos en .env; colección queda vacía.")


def _asegurar_grupos_trabajo() -> None:
    repo = GrupoRepositorio()
    creados = sum(1 for g in GRUPOS_TRABAJO_BASE if repo.asegurar(dict(g)))
    if creados:
        print(f"  {creados} grupo(s) de trabajo sembrado(s).")


def main():
    print("Arrancando bootstrap de MongoDB...")
    mb = MongoBootstrapService()
    mb.asegurar_estructura()
    print("Estructura y validadores asegurados.")

    cs = CatalogoService()
    cs.asegurar_catalogos_base()
    print("Catálogos base asegurados (roles y permisos).")

    us = UsuarioService()
    resultado = us.asegurar_usuario_admin_inicial()
    if resultado:
        print(f"Usuario admin creado con id: {resultado}")
    else:
        print("Usuario admin ya existente o ADMIN_INICIAL_PASSWORD no definido.")

    print("Sembrando catálogos de política de datos...")
    _asegurar_politica_v1()

    print("Sembrando grupos de trabajo...")
    _asegurar_grupos_trabajo()

    print("Sembrando instructivos iniciales...")
    _asegurar_instructivos_iniciales()

    # Resumen de conteos
    db = obtener_base_datos()
    print("Conteos por colección:")
    colecciones = [
        "usuarios", "roles", "permisos", "sesiones",
        "opciones_configuracion", "certificaciones",
        "politicas_datos", "aceptaciones_politica", "firmas", "instructivos",
        "grupos_trabajo", "asignaciones_grupo",
    ]
    for nombre in colecciones:
        try:
            print(f" - {nombre}: {db[nombre].count_documents({})}")
        except Exception as e:
            print(f" - {nombre}: error al contar -> {e}")


if __name__ == "__main__":
    main()
