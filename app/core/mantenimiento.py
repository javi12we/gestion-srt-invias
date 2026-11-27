"""Ventana de mantenimiento: aviso previo y cierre total de la aplicación.

Se controla con MANTENIMIENTO_INICIO (.env). Sin valor, no hace nada.
- Antes de esa hora: banner fijo en la parte superior de todas las pantallas.
- Desde esa hora: la app muestra solo la pantalla de mantenimiento (sin login),
  también a quienes ya tenían la sesión abierta, porque main.py lo evalúa en
  cada recarga.
"""

from datetime import datetime

import streamlit as st

from app.config import configuracion
from app.core.zona_horaria import ZONA_BOGOTA

_MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
          "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
_DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def _inicio() -> datetime | None:
    texto = (configuracion.mantenimiento_inicio or "").strip()
    if not texto:
        return None
    try:
        fecha = datetime.fromisoformat(texto)
    except ValueError:
        return None  # valor mal escrito: no bloquear la app por error de configuración
    if fecha.tzinfo is None:
        fecha = ZONA_BOGOTA.localize(fecha)
    return fecha


def _html(texto: str) -> str:
    """Quita sangrías y líneas vacías: markdown trataría el HTML sangrado como código."""
    return "\n".join(l.strip() for l in texto.splitlines() if l.strip())


def estado() -> str:
    """'ninguno' | 'aviso' (antes del inicio) | 'cerrado' (desde el inicio)."""
    inicio = _inicio()
    if inicio is None:
        return "ninguno"
    return "cerrado" if datetime.now(ZONA_BOGOTA) >= inicio else "aviso"


def _texto_aviso() -> str:
    inicio = _inicio().astimezone(ZONA_BOGOTA)
    hoy = datetime.now(ZONA_BOGOTA).date()
    if inicio.date() == hoy:
        cuando = "hoy"
    else:
        cuando = f"el {_DIAS[inicio.weekday()]} {inicio.day} de {_MESES[inicio.month - 1]}"
    hora = inicio.strftime("%I:%M").lstrip("0") + (" a. m." if inicio.hour < 12 else " p. m.")
    return (f"Aviso: {cuando} a las {hora} la plataforma dejará de estar disponible "
            "por mantenimiento durante el fin de semana.")


def mostrar_aviso() -> None:
    """Banner fijo arriba; desplaza el encabezado de Streamlit para no taparlo."""
    st.markdown(
        _html("""
        <style>
        .aviso-mant{position:fixed;top:0;left:0;right:0;height:44px;z-index:1000001;
          display:flex;align-items:center;justify-content:center;gap:10px;padding:0 16px;
          background:repeating-linear-gradient(-45deg,#FFC400 0 18px,#1A1A1A 18px 36px);
          box-shadow:0 2px 8px rgba(0,0,0,.35);}
        .aviso-mant span{background:#1A1A1A;color:#FFC400;font:600 14px/1.2 -apple-system,
          "Segoe UI",Roboto,Arial,sans-serif;padding:6px 14px;border-radius:6px;text-align:center;}
        [data-testid="stHeader"]{top:44px !important;}
        [data-testid="stAppViewContainer"]{padding-top:44px;}
        [data-testid="stSidebar"]{padding-top:44px;}
        @media (max-width:640px){.aviso-mant{height:60px}.aviso-mant span{font-size:12px}
          [data-testid="stHeader"]{top:60px !important;}
          [data-testid="stAppViewContainer"],[data-testid="stSidebar"]{padding-top:60px;}}
        </style>
        <div class="aviso-mant"><span>🚧 """ + _texto_aviso() + """</span></div>
        """),
        unsafe_allow_html=True,
    )


_ESCENA_SVG = """
<svg viewBox="0 0 640 260" xmlns="http://www.w3.org/2000/svg" class="mant-escena" role="img"
     aria-label="Obra en construcción">
  <rect width="640" height="260" fill="#FFE0B2"/>
  <circle cx="540" cy="60" r="30" fill="#FFB300"/>
  <rect y="185" width="640" height="75" fill="#4A4A4A"/>
  <g class="linea"><rect x="0" y="219" width="50" height="6" fill="#F5F5F5"/>
    <rect x="90" y="219" width="50" height="6" fill="#F5F5F5"/>
    <rect x="180" y="219" width="50" height="6" fill="#F5F5F5"/>
    <rect x="270" y="219" width="50" height="6" fill="#F5F5F5"/>
    <rect x="360" y="219" width="50" height="6" fill="#F5F5F5"/>
    <rect x="450" y="219" width="50" height="6" fill="#F5F5F5"/>
    <rect x="540" y="219" width="50" height="6" fill="#F5F5F5"/>
    <rect x="630" y="219" width="50" height="6" fill="#F5F5F5"/></g>
  <!-- barrera -->
  <rect x="60" y="150" width="8" height="45" fill="#333"/><rect x="232" y="150" width="8" height="45" fill="#333"/>
  <rect x="50" y="140" width="200" height="26" rx="3" fill="#F5F5F5" stroke="#333" stroke-width="2"/>
  <g fill="#E65100"><polygon points="55,140 80,140 65,166 50,166"/><polygon points="105,140 130,140 115,166 100,166"/>
    <polygon points="155,140 180,140 165,166 150,166"/><polygon points="205,140 230,140 215,166 200,166"/></g>
  <circle class="luz" cx="64" cy="128" r="9" fill="#FFC400"/><circle class="luz l2" cx="236" cy="128" r="9" fill="#FFC400"/>
  <!-- conos -->
  <g><polygon points="300,195 320,195 316,160 304,160" fill="#FF6D00"/><rect x="298" y="195" width="24" height="5" fill="#333"/>
    <rect x="304" y="172" width="12" height="6" fill="#fff"/></g>
  <g><polygon points="580,195 600,195 596,160 584,160" fill="#FF6D00"/><rect x="578" y="195" width="24" height="5" fill="#333"/>
    <rect x="584" y="172" width="12" height="6" fill="#fff"/></g>
  <!-- obrero -->
  <g transform="translate(420,95)">
    <path d="M-14,18 a14,12 0 0 1 28,0 z" fill="#FFC400"/><rect x="-17" y="17" width="34" height="4" rx="2" fill="#FFB300"/>
    <circle cx="0" cy="30" r="11" fill="#E0A97A"/>
    <rect x="-13" y="42" width="26" height="42" rx="6" fill="#FF6D00"/>
    <rect x="-13" y="58" width="26" height="5" fill="#F5F5F5"/>
    <rect x="-12" y="84" width="10" height="42" fill="#37474F"/><rect x="2" y="84" width="10" height="42" fill="#37474F"/>
    <g class="martillo"><rect x="8" y="50" width="6" height="50" rx="2" fill="#8D6E63" transform="rotate(25 11 50)"/>
      <rect x="-2" y="94" width="34" height="14" rx="2" fill="#607D8B" transform="rotate(25 11 94)"/></g>
  </g>
  <rect x="350" y="170" width="140" height="14" rx="4" fill="#795548" opacity=".45"/>
</svg>
"""


def pantalla_cierre() -> None:
    """Pantalla única de la app durante el mantenimiento."""
    contacto = (configuracion.mantenimiento_contacto or "").strip()
    linea_contacto = (f"<p class='mant-contacto'>Para consultas escríbenos a "
                      f"<b>{contacto}</b></p>") if contacto else ""
    st.markdown(
        _html("""
        <style>
        [data-testid="stSidebar"],[data-testid="stSidebarCollapsedControl"],
        [data-testid="stHeader"],[data-testid="stToolbar"]{display:none !important;}
        .stApp{background:linear-gradient(135deg,#E87A1E 0%,#A65012 55%,#3D1E0A 100%) !important;}
        .mant-caja{max-width:680px;margin:6vh auto 0;background:#FFFDF8;border-radius:18px;
          overflow:hidden;box-shadow:0 18px 50px rgba(0,0,0,.4);
          font-family:-apple-system,"Segoe UI",Roboto,Arial,sans-serif;}
        .mant-franja{height:16px;background:repeating-linear-gradient(-45deg,#FFC400 0 18px,#1A1A1A 18px 36px);}
        .mant-escena{display:block;width:100%;height:auto;}
        .mant-texto{padding:22px 28px 30px;text-align:center;}
        .mant-texto h1{color:#B85C00 !important;font-size:1.9rem;margin:0 0 8px;padding:0;}
        .mant-texto p{color:#4A3B2A !important;font-size:1.05rem;margin:6px 0;}
        .mant-contacto{font-size:.95rem !important;margin-top:16px !important;}
        .mant-escena .linea{animation:mant-carretera 1.6s linear infinite;}
        .mant-escena .luz{animation:mant-parpadeo 1s steps(1) infinite;}
        .mant-escena .l2{animation-delay:.5s;}
        .mant-escena .martillo{transform-origin:11px 52px;transform-box:fill-box;
          animation:mant-golpe .8s ease-in-out infinite;}
        @keyframes mant-carretera{to{transform:translateX(-90px);}}
        @keyframes mant-parpadeo{50%{opacity:.15;}}
        @keyframes mant-golpe{0%,100%{transform:rotate(-25deg);}50%{transform:rotate(30deg);}}
        </style>
        <div class="mant-caja">
          <div class="mant-franja"></div>
          """ + _ESCENA_SVG + """
          <div class="mant-franja"></div>
          <div class="mant-texto">
            <h1>Estamos en mantenimiento</h1>
            <p>La plataforma de Gestión de Correspondencia SRTI-INVIAS no se encuentra disponible
            en este momento.</p>
            <p>Gracias por tu paciencia.</p>
            """ + linea_contacto + """
          </div>
        </div>
        """),
        unsafe_allow_html=True,
    )
