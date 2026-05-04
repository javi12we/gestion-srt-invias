from dataclasses import dataclass
import os

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Configuracion:
    mongodb_uri: str = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    mongodb_db: str = os.getenv("MONGODB_DB", "gestion_srt")
    secret_key: str = os.getenv("SECRET_KEY", "cambia_esta_clave_por_una_muy_larga_y_segura")
    admin_inicial_password: str | None = os.getenv("ADMIN_INICIAL_PASSWORD")


configuracion = Configuracion()
