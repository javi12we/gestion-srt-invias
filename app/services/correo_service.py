"""Envío de correos por SMTP (cuenta remitente configurada en `.env`)."""

import os
import smtplib
from email.message import EmailMessage
from email.utils import formataddr

from app.config import configuracion
from app.core.plantillas_correo import CID_LOGO

_RUTA_LOGO = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "invias_logo.png")


class CorreoService:
    def __init__(self, cfg=configuracion) -> None:
        self.cfg = cfg
        self._smtp = None

    def configurado(self) -> bool:
        return bool(self.cfg.correo_remitente and self.cfg.correo_password_app)

    def construir_mensaje(self, destinatario: str, asunto: str, html: str, texto: str) -> EmailMessage:
        mensaje = EmailMessage()
        mensaje["Subject"] = asunto
        mensaje["From"] = formataddr((self.cfg.correo_nombre_remitente, self.cfg.correo_remitente))
        mensaje["To"] = destinatario
        mensaje.set_content(texto)
        mensaje.add_alternative(html, subtype="html")
        # El logo viaja dentro del correo (imagen embebida), no como enlace a una URL.
        with open(_RUTA_LOGO, "rb") as archivo:
            mensaje.get_payload()[1].add_related(
                archivo.read(), maintype="image", subtype="png", cid=f"<{CID_LOGO}>"
            )
        return mensaje

    def conectar(self) -> None:
        if not self.configurado():
            raise ValueError(
                "Falta configurar el correo remitente: define CORREO_REMITENTE y CORREO_PASSWORD_APP."
            )
        self._smtp = smtplib.SMTP_SSL(self.cfg.correo_smtp_host, self.cfg.correo_smtp_puerto, timeout=30)
        # Google muestra la contraseña de aplicación en cuatro grupos separados por
        # espacios; se aceptan pegados tal cual.
        self._smtp.login(self.cfg.correo_remitente.strip(), self.cfg.correo_password_app.replace(" ", ""))

    def enviar(self, destinatario: str, asunto: str, html: str, texto: str) -> None:
        if self._smtp is None:
            self.conectar()
        self._smtp.send_message(self.construir_mensaje(destinatario, asunto, html, texto))

    def cerrar(self) -> None:
        if self._smtp is not None:
            try:
                self._smtp.quit()
            except smtplib.SMTPException:
                pass
            self._smtp = None
