"""Componentes de UI reutilizables para información laboral y firma del usuario.

Se usan tanto en la administración de usuarios (`pages_admin/admin_usuarios.py`)
como en el perfil propio (`pages/2_mi_perfil.py`). Toda la sección se renderiza
SIN `st.form`, porque los dependientes se agregan/eliminan con botones, que
Streamlit no permite dentro de un form.
"""

import streamlit as st

from app.core.catalogos import TIPOS_DOC_DEPENDIENTE
from app.core.ui_pesos import entrada_pesos
from app.services.firma_service import FirmaService, componer_sobre_fondo, validar_y_procesar
from app.services.opciones_service import OpcionesService

# (clave en doc, etiqueta visible, categoría de catálogo)
_AFILIACIONES = [
    ("eps", "EPS", "eps"),
    ("arl", "ARL", "arl"),
    ("afp", "Fondo de pensiones (AFP)", "afp"),
    ("ccf", "Caja de compensación (CCF)", "ccf"),
]
_CATEGORIAS = ["eps", "arl", "afp", "ccf", "banco", "tipo_dependiente", "regimen_tributario"]

# Cómo se cubre el aporte de seguridad social (no es catálogo: opciones fijas).
# El valor interno "entidad" se conserva por compatibilidad; la etiqueta visible
# es genérica ("por otro medio") para no explicitar quién realiza el pago.
_MAPA_PAGA = {
    "": "— Seleccionar —",
    "contratista": "La pago yo",
    "entidad": "Se paga por otro medio",
}


def _paga_inicial(af: dict) -> str:
    """Determina la opción 'quién paga' inicial, infiriéndola en registros antiguos."""
    paga = af.get("paga")
    if paga in ("contratista", "entidad"):
        return paga
    if af.get("valor"):
        return "contratista"
    if af.get("radicado"):
        return "entidad"
    return ""


# ── Catálogos ─────────────────────────────────────────────────────────────────

def _mapa_opciones(op_service, categoria, etiqueta_vacio="— Seleccionar —"):
    mapa = {"": etiqueta_vacio}
    for o in op_service.obtener_opciones(categoria):
        mapa[o["clave"]] = o["etiqueta"]
    return mapa


def construir_mapas_catalogos():
    """{categoria: {clave: etiqueta}} para los selects de información laboral."""
    op = OpcionesService()
    return {cat: _mapa_opciones(op, cat) for cat in _CATEGORIAS}


# ── Helpers de estado de widgets ──────────────────────────────────────────────

def _preseed(key, value):
    """Fija el valor inicial de un widget vía session_state (solo si aún no existe)."""
    if key not in st.session_state:
        st.session_state[key] = value


def _select_keyed(label, mapa, valor_inicial, key, **kwargs):
    claves = list(mapa.keys())
    _preseed(key, valor_inicial if valor_inicial in claves else "")
    return st.selectbox(label, options=claves, format_func=lambda k: mapa[k], key=key, **kwargs)


def limpiar_estado_laboral(prefijo):
    """Elimina las claves de session_state de los widgets laborales de un prefijo."""
    for k in [k for k in st.session_state.keys() if k.startswith(prefijo + "_")]:
        del st.session_state[k]


# ── Sección de información laboral ────────────────────────────────────────────

_CAMPOS_NO_APLICAN_PENSIONADO = {"afp", "ccf"}


def inputs_informacion_laboral(prefijo, il, mapas):
    """Renderiza los campos de información laboral y devuelve el dict crudo."""
    il = il or {}
    ss = il.get("seguridad_social") or {}
    bancaria = il.get("bancaria") or {}
    tributaria = il.get("tributaria") or {}
    deps = il.get("dependientes") or []

    dark_mode = st.session_state.get("dark_mode", False)
    bg_color = "#202030" if dark_mode else "#ffffff"
    text_color = "#E2E8F0" if dark_mode else "#2D3748"
    border_color = "#3F3F5F" if dark_mode else "#E2E8F0"
    strong_color = "#FFFFFF" if dark_mode else "#1A202C"

    st.markdown(
        f"""
        <style>
        /* Contenedor del Tooltip */
        .srti-tooltip-container {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            font-size: 14px;
            font-weight: 500;
            margin-top: 10px;
            margin-bottom: 4px;
            position: relative;
            z-index: 99;
        }}

        .srti-tooltip-container:hover,
        .srti-tooltip-container:focus-within {{
            z-index: 999999 !important;
        }}

        /* Ícono de información */
        .srti-tooltip-icon {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            position: relative;
            cursor: pointer;
            color: #FF8C00;
            font-size: 14px;
            width: 18px;
            height: 18px;
            border-radius: 50%;
            background-color: rgba(255, 140, 0, 0.1);
            transition: background-color 0.2s, transform 0.2s;
            user-select: none;
            outline: none;
            z-index: 99999;
        }}

        .srti-tooltip-icon:hover, .srti-tooltip-icon:focus {{
            background-color: rgba(255, 140, 0, 0.25);
            transform: scale(1.1);
            z-index: 999999 !important;
        }}

        /* Contenido del Tooltip */
        .srti-tooltip-content {{
            display: none;
            position: absolute;
            top: 125%;
            left: 0;
            transform: none;
            width: 500px;
            max-width: 90vw;
            background-color: {bg_color} !important;
            color: {text_color} !important;
            padding: 16px;
            border-radius: 8px;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.15), 0 10px 10px -5px rgba(0, 0, 0, 0.08);
            border: 1px solid {border_color};
            z-index: 999999;
            max-height: 450px;
            overflow-y: auto;
            font-size: 13px;
            font-weight: normal;
            line-height: 1.5;
            text-align: left;
            white-space: normal;
        }}

        /* Flecha apuntando hacia arriba */
        .srti-tooltip-content::after {{
            content: "";
            position: absolute;
            bottom: 100%;
            left: 4px;
            transform: none;
            border-width: 6px;
            border-style: solid;
            border-color: transparent transparent {bg_color} transparent;
        }}

        /* Mostrar tooltip al pasar el cursor o hacer focus */
        .srti-tooltip-icon:hover .srti-tooltip-content,
        .srti-tooltip-icon:focus .srti-tooltip-content,
        .srti-tooltip-icon:focus-within .srti-tooltip-content {{
            display: block;
        }}

        /* Estilos de texto en el tooltip */
        .srti-tooltip-content h4 {{
            margin-top: 0;
            margin-bottom: 12px;
            color: #FF8C00 !important;
            font-size: 14px;
            font-weight: 700;
            letter-spacing: 0.5px;
            border-bottom: 1px solid {border_color};
            padding-bottom: 8px;
        }}

        .srti-tooltip-content ul {{
            margin: 0;
            padding-left: 0;
            list-style-type: none;
            background-color: transparent !important;
        }}

        .srti-tooltip-content li {{
            margin-bottom: 10px;
            color: {text_color} !important;
            background-color: transparent !important;
        }}

        .srti-tooltip-content li:last-child {{
            margin-bottom: 0;
        }}

        .srti-tooltip-content strong {{
            color: {strong_color} !important;
            background-color: transparent !important;
        }}

        .srti-tooltip-content p {{
            margin-top: 0;
            margin-bottom: 10px;
            color: {text_color} !important;
            background-color: transparent !important;
        }}

        .srti-tooltip-content p:last-child {{
            margin-bottom: 0;
        }}

        /* Forzar que las columnas y bloques de Streamlit permitan ver elementos flotantes sin recorte */
        div[data-testid="column"], div.element-container, div[data-testid="stVerticalBlock"], div[data-testid="stBlock"] {{
            overflow: visible !important;
        }}

        /* Ajustes Responsive y posicionamiento */
        @media (max-width: 768px) {{
            .srti-tooltip-content {{
                position: fixed !important;
                bottom: auto !important;
                top: 20% !important;
                left: 5% !important;
                right: 5% !important;
                width: auto !important;
                max-width: 90% !important;
                transform: none !important;
                box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.2) !important;
            }}
            .srti-tooltip-content::after {{
                display: none !important;
            }}
        }}
        </style>
        """,
        unsafe_allow_html=True
    )

    _preseed(f"{prefijo}_es_pensionado", bool(il.get("es_pensionado")))
    es_pensionado = st.session_state.get(f"{prefijo}_es_pensionado", False)

    _preseed(f"{prefijo}_planilla_mes_vencido", bool(il.get("planilla_mes_vencido")))
    planilla_mes_vencido = st.session_state.get(f"{prefijo}_planilla_mes_vencido", False)


    st.markdown(
        """
        <div class="srti-tooltip-container">
          <span>Grupo de trabajo</span>
          <span class="srti-tooltip-icon" tabindex="0">ⓘ
            <div class="srti-tooltip-content">
              <h4 style="color: #FF8C00 !important; margin-bottom: 12px; font-weight: 700;">GRUPOS DE TRABAJO</h4>
              <p>En la SRTI existen varios sub grupos de trabajo, debe elegir uno segun su funcion en la subdirección. Si pertenece a 2 de ellos elija en el que desempeña su labor principal.</p>
            </div>
          </span>
        </div>
        """,
        unsafe_allow_html=True
    )
    from app.core.catalogos import GRUPOS_TRABAJO
    grupo_trabajo = _select_keyed(
        "Grupo de trabajo",
        GRUPOS_TRABAJO,
        il.get("grupo_trabajo") or "",
        f"{prefijo}_grupo_trabajo",
        label_visibility="collapsed"
    )





    st.markdown("##### 🏥 Seguridad social y aportes")
    st.caption("Indica si el aporte lo pagas tú (registra el valor mensual) o se paga por otro medio (registra el número de radicado). Para generar los formatos de primera y última cuenta, es indispensable diligenciar los datos de la planilla junto con sus respectivos valores.")
    
    st.checkbox(
        "Planilla a mes vencido",
        key=f"{prefijo}_planilla_mes_vencido",
        help="Marca esta opción si pagas la planilla a mes vencido."
    )
    
    st.markdown(
        """<div class="srti-tooltip-container">
<span>Ingreso Base de Cotización - Prestaciones sociales (opcional)</span>
<span class="srti-tooltip-icon" tabindex="0">ⓘ
<div class="srti-tooltip-content">
<h4 style="color: #FF8C00 !important; margin-top: 0; margin-bottom: 12px; font-weight: 700; font-size: 14px; border-bottom: 1px solid #E2E8F0; padding-bottom: 8px;">GUÍA RÁPIDA: CÁLCULO DEL IBC</h4>
<p style="margin-bottom: 10px;">El <strong>Ingreso Base de Cotización (IBC)</strong> para contratistas independientes en Colombia se calcula con la regla del <strong>40%</strong> del valor mensualizado del contrato (sin incluir IVA).</p>
<p style="margin-bottom: 10px;"><strong>1. Mensualiza el contrato</strong><br>
Divide el valor total del contrato por el número de meses de ejecución.<br>
Fórmula: <code>Valor total ÷ Meses de duración = Ingreso Mensual</code><br>
<em>Ejemplo: Contrato de $30.000.000 a 6 meses = $5.000.000 mensuales.</em></p>
<p style="margin-bottom: 10px;"><strong>2. Aplica el 40%</strong><br>
El IBC mínimo legal sobre el cual debes cotizar es el 40% de ese valor mensual.<br>
Fórmula: <code>Ingreso Mensual × 40% = IBC</code><br>
<em>Ejemplo: $5.000.000 × 40% = $2.000.000 (Este es tu IBC).</em></p>
<p style="margin-bottom: 10px;"><strong>3. Verifica los topes legales</strong><br>
• <strong>Piso mínimo:</strong> No puede ser menor a 1 Salario Mínimo Mensual Legal Vigente (SMMLV). Si el 40% es menor, cotizas sobre 1 SMMLV.<br>
• <strong>Techo máximo:</strong> No puede superar los 25 SMMLV.</p>
<p style="margin-bottom: 10px;"><strong>4. Calcula tus aportes de ley (sobre el IBC)</strong><br>
• <strong>Salud (12.5%):</strong> IBC × 12.5% (Ej: $2.000.000 × 12.5% = $250.000)<br>
• <strong>Pensión (16%):</strong> IBC × 16% (Ej: $2.000.000 × 16% = $320.000)<br>
• <strong>ARL (Varía según riesgo):</strong> Lo paga el contratista, excepto si es nivel de riesgo IV o V, que lo asume el contratante.</p>
</div>
</span>
</div>""",
        unsafe_allow_html=True
    )
    ibc_ps = entrada_pesos(
        "Ingreso Base de Cotización - Prestaciones sociales (opcional)",
        value=int(il.get("ibc_prestaciones_sociales") or 0),
        key=f"{prefijo}_ibc_prestaciones_sociales",
        label_visibility="collapsed",
    )
    
    resultado_ss = {}
    for cod, etiqueta, cat in _AFILIACIONES:
        af = ss.get(cod) or {}
        if es_pensionado and cod in _CAMPOS_NO_APLICAN_PENSIONADO:
            st.caption(f"**{etiqueta}** — No aplica (pensionado/a)")
            resultado_ss[cod] = af  # preservar datos existentes sin modificar
            continue
        c1, c2, c3, c4, c5 = st.columns([2, 1.3, 1.1, 1.1, 1.1])
        with c1:
            entidad = _select_keyed(etiqueta, mapas[cat], af.get("entidad") or "", f"{prefijo}_{cod}_ent")
        with c2:
            paga = _select_keyed("¿Quién paga?", _MAPA_PAGA, _paga_inicial(af), f"{prefijo}_{cod}_paga")
        if paga == "entidad":
            with c3:
                _preseed(f"{prefijo}_{cod}_rad", af.get("radicado") or "")
                radicado = st.text_input("N° de radicado", key=f"{prefijo}_{cod}_rad", placeholder="Radicado del pago")
            valor_primer_mes, valor, valor_ultimo_mes = 0, 0, 0
        elif paga == "contratista":
            with c3:
                valor_primer_mes = entrada_pesos(
                    "Valor mensual primera cuenta", value=int(af.get("valor_primer_mes") or 0),
                    key=f"{prefijo}_{cod}_val_primer",
                )
            with c4:
                valor = entrada_pesos("Valor mensual", value=int(af.get("valor") or 0), key=f"{prefijo}_{cod}_val")
            with c5:
                valor_ultimo_mes = entrada_pesos(
                    "Valor mensual última cuenta", value=int(af.get("valor_ultimo_mes") or 0),
                    key=f"{prefijo}_{cod}_val_ultimo",
                )
            radicado = ""
        else:
            with c3:
                st.caption("Selecciona quién paga el aporte.")
            valor_primer_mes, valor, valor_ultimo_mes, radicado = 0, 0, 0, ""
        resultado_ss[cod] = {
            "entidad": entidad,
            "paga": paga,
            "valor": valor,
            "valor_primer_mes": valor_primer_mes,
            "valor_ultimo_mes": valor_ultimo_mes,
            "radicado": radicado,
        }

    st.markdown("##### 🏦 Información bancaria")
    cb1, cb2, cb3 = st.columns(3)
    with cb1:
        banco = _select_keyed("Banco", mapas["banco"], bancaria.get("banco") or "", f"{prefijo}_banco")
    with cb2:
        _preseed(f"{prefijo}_num_cuenta", bancaria.get("numero_cuenta") or "")
        num_cuenta = st.text_input("Número de cuenta", key=f"{prefijo}_num_cuenta", placeholder="Sin puntos ni espacios")
    with cb3:
        from app.core.catalogos import TIPOS_CUENTA_BANCARIA
        tipo_cuenta = _select_keyed(
            "Tipo de cuenta",
            TIPOS_CUENTA_BANCARIA,
            bancaria.get("tipo_cuenta") or "",
            f"{prefijo}_tipo_cuenta"
        )

    st.markdown("##### 🧾 Información tributaria")
    ct1, ct2 = st.columns(2)
    with ct1:
        _preseed(f"{prefijo}_rut", tributaria.get("rut") or "")
        rut = st.text_input("RUT", key=f"{prefijo}_rut")
        st.markdown(
            """
            <div class="srti-tooltip-container">
              <span>Tipo de régimen</span>
              <span class="srti-tooltip-icon" tabindex="0">ⓘ
                <div class="srti-tooltip-content">
                  <h4 style="color: #FF8C00 !important; margin-bottom: 12px; font-weight: 700;">TIPOS DE RÉGIMEN</h4>
                  <p><strong>No responsables de IVA</strong><br>
                  Personas naturales que no cumplen con los topes de ingresos o condiciones de ley para ser responsables de declarar/cobrar IVA (anteriormente régimen simplificado).</p>
                  <p><strong>Responsables de IVA</strong><br>
                  Personas jurídicas o naturales que superan los topes legales de ingresos o requisitos y por tanto deben facturar, recaudar y declarar el IVA (anteriormente régimen común).</p>
                  <p><strong>Régimen Simple de Tributación (RST)</strong><br>
                  Sistema de tributación opcional que unifica varios impuestos (renta, ICA, IVA si aplica) para facilitar y simplificar el cumplimiento tributario.</p>
                  <p><strong>Régimen Tributario Especial (RTE)</strong><br>
                  Aplica a entidades sin ánimo de lucro (fundaciones, asociaciones, corporaciones) que cumplen requisitos de ley y tienen un tratamiento tributario preferencial.</p>
                </div>
              </span>
            </div>
            """,
            unsafe_allow_html=True
        )
        regimen_db = tributaria.get("regimen") or ""
        regimenes_validos = {"no_responsable_iva", "responsable_iva", "simple_rst", "especial_rte"}
        regimen_invalido = regimen_db != "" and regimen_db not in regimenes_validos
        
        # Usamos un div contenedor con un id o clase para aplicar el estilo únicamente a este selectbox
        if regimen_invalido:
            st.markdown(
                f"""
                <style>
                /* Forzar el borde rojo ÚNICAMENTE en el selectbox de régimen */
                div.element-container:has(iframe), 
                div.element-container:has(div[data-testid="stSelectbox"] select[aria-label="Tipo de régimen"]) {{
                    border: 1px solid #FF4B4B !important;
                    border-radius: 4px;
                }}
                /* Alternativa usando el id único que genera Streamlit en base al key del widget */
                div[data-testid="stSelectbox"]:has(input[id^="{prefijo}_regimen"]) {{
                    border: 1px solid #FF4B4B !important;
                    border-radius: 4px;
                }}
                </style>
                """,
                unsafe_allow_html=True
            )
            
        regimen = _select_keyed(
            "Tipo de régimen", mapas["regimen_tributario"],
            tributaria.get("regimen") or "", f"{prefijo}_regimen",
            label_visibility="collapsed"
        )
        
        if regimen_invalido:
            st.markdown(
                f'<span style="color: #FF4B4B; font-size: 0.85em; font-weight: 500;">⚠️ El régimen guardado actual ("{regimen_db}") está desactualizado. Selecciona uno nuevo.</span>',
                unsafe_allow_html=True
            )

        # Si el régimen elegido es responsable de IVA, forzamos automáticamente paga_iva en True
        if regimen == "responsable_iva":
            st.session_state[f"{prefijo}_paga_iva"] = True
        
        # Si paga IVA, mostramos el input para el valor
        _preseed(f"{prefijo}_paga_iva", bool(il.get("paga_iva")))
        paga_iva = st.session_state.get(f"{prefijo}_paga_iva", False)
        
        valor_iva = None
        if paga_iva:
            valor_iva = entrada_pesos("Valor del IVA", value=int(il.get("valor_iva") or 0), key=f"{prefijo}_valor_iva")
            
    with ct2:
        _preseed(f"{prefijo}_declarante", bool(tributaria.get("declarante_renta")))
        declarante = st.checkbox("¿Declarante de renta?", key=f"{prefijo}_declarante")
        
        paga_iva = st.checkbox(
            "¿Paga IVA?",
            key=f"{prefijo}_paga_iva",
            help="Marca esta opción si estás obligado/a a facturar y cobrar IVA en tus contratos."
        )

        st.checkbox(
            "¿Eres pensionado/a?",
            key=f"{prefijo}_es_pensionado",
            help="Si estás pensionado/a, los campos de AFP y Caja de Compensación Familiar no aplican y no serán requeridos para descargar los formatos.",
        )


    st.markdown("##### 👨‍👩‍👧 Dependientes económicos")
    dependientes = _inputs_dependientes(prefijo, deps, mapas)

    return {
        "es_pensionado": es_pensionado,
        "planilla_mes_vencido": planilla_mes_vencido,
        "grupo_trabajo": grupo_trabajo if grupo_trabajo else None,
        "ibc_prestaciones_sociales": ibc_ps if ibc_ps > 0 else None,
        "paga_iva": paga_iva,
        "valor_iva": valor_iva if paga_iva else None,
        "seguridad_social": resultado_ss,
        "bancaria": {"banco": banco, "numero_cuenta": num_cuenta, "tipo_cuenta": tipo_cuenta},
        "tributaria": {"rut": rut, "declarante_renta": declarante, "regimen": regimen},
        "dependientes": dependientes,
    }


def _inputs_dependientes(prefijo, deps, mapas):
    """Lista dinámica de dependientes con agregar/eliminar por fila (IDs estables)."""
    # Estilos CSS ahora se cargan dinámicamente al inicio de inputs_informacion_laboral.

    ids_key = f"{prefijo}_dep_ids"
    seq_key = f"{prefijo}_dep_seq"
    datos_key = f"{prefijo}_dep_datos"
    tdoc_keys = list(TIPOS_DOC_DEPENDIENTE.keys())
    tipo_mapa = mapas["tipo_dependiente"]
    tipo_keys = list(tipo_mapa.keys())

    # Inicialización: un ID estable por dependiente existente. Los valores se
    # guardan en un espejo programático (datos_key) además de las claves de
    # widget: Streamlit borra las claves de widget cuando la sección no se
    # renderiza (navegar a otra página, o un st.rerun() que interrumpe el run
    # antes de dibujar la fila); el espejo sobrevive y permite re-sembrarlas.
    # Sin él, las filas quedaban vacías y el siguiente guardado borraba los
    # dependientes en la BD.
    if ids_key not in st.session_state:
        st.session_state[seq_key] = 0
        ids = []
        datos = {}
        for dep in deps:
            rid = st.session_state[seq_key]
            st.session_state[seq_key] += 1
            ids.append(rid)
            tdoc = dep.get("tipo_documento") or ""
            tipo = dep.get("tipo") or ""
            datos[rid] = {
                "nombre": dep.get("nombre") or "",
                "ndoc": dep.get("numero_documento") or "",
                "tdoc": tdoc if tdoc in tdoc_keys else "",
                "tipo": tipo if tipo in tipo_keys else "",
            }
        st.session_state[ids_key] = ids
        st.session_state[datos_key] = datos

    ids = st.session_state[ids_key]
    datos = st.session_state[datos_key]

    # Re-sembrar desde el espejo toda clave de widget que Streamlit haya limpiado.
    for rid in ids:
        fila = datos.get(rid) or {"nombre": "", "ndoc": "", "tdoc": "", "tipo": ""}
        _preseed(f"{prefijo}_dep_nombre_{rid}", fila["nombre"])
        _preseed(f"{prefijo}_dep_ndoc_{rid}", fila["ndoc"])
        _preseed(f"{prefijo}_dep_tdoc_{rid}", fila["tdoc"])
        _preseed(f"{prefijo}_dep_tipo_{rid}", fila["tipo"])
    if not ids:
        st.caption("Sin dependientes. Usa “➕ Agregar dependiente” si necesitas registrar alguno.")

    dependientes = []
    for pos, rid in enumerate(list(ids)):
        cab, bdel = st.columns([6, 1])
        with cab:
            st.markdown(f"**Dependiente {pos + 1}**")
        with bdel:
            if st.button("🗑️", key=f"{prefijo}_dep_del_{rid}", help="Eliminar este dependiente"):
                st.session_state[ids_key].remove(rid)
                datos.pop(rid, None)
                st.rerun()
        cd1, cd2 = st.columns(2)
        with cd1:
            nombre = st.text_input("Nombre completo", key=f"{prefijo}_dep_nombre_{rid}")
            tdoc = st.selectbox(
                "Tipo de documento", options=tdoc_keys,
                format_func=lambda k: TIPOS_DOC_DEPENDIENTE[k], key=f"{prefijo}_dep_tdoc_{rid}",
            )
        with cd2:
            ndoc = st.text_input("Número de documento", key=f"{prefijo}_dep_ndoc_{rid}")
            if ndoc and not ndoc.strip().isdigit():
                st.error("El número de documento debe contener únicamente números.")
            st.markdown(
                """
                <div class="srti-tooltip-container">
                  <span>Tipo de dependiente</span>
                  <span class="srti-tooltip-icon" tabindex="0">ⓘ
                    <div class="srti-tooltip-content">
                      <h4 style="color: #FF8C00 !important;">TIPOS DE DEPENDIENTES</h4>
                      <ul>
                        <li><strong>A.</strong> Hijo(s) que tiene(n) hasta 18 años de edad y depende(n) económicamente del declarante.</li>
                        <li><strong>B.</strong> Hijo(s) entre 18 y 23 años, cuya educación está a cargo del declarante en instituciones formales de educación superior certificadas por el ICFES o la autoridad competente, o en programas técnicos de educación no formal debidamente acreditados.</li>
                        <li><strong>C.</strong> Hijo(s) mayores de 23 años que se encuentren en situación de dependencia por condiciones físicas o psicológicas certificadas por Medicina Legal.</li>
                        <li><strong>D.</strong> Cónyuge o compañero(a) permanente en situación de dependencia por ausencia de ingresos o ingresos anuales inferiores a 260 UVT, certificados por contador público, o por dependencia originada por factores físicos o psicológicos certificados por Medicina Legal.</li>
                        <li><strong>E.</strong> Padres y/o hermanos en situación de dependencia por ausencia de ingresos o ingresos anuales inferiores a 260 UVT, certificados por contador público, o por dependencia originada por factores físicos o psicológicos certificados por Medicina Legal.</li>
                      </ul>
                    </div>
                  </span>
                </div>
                """,
                unsafe_allow_html=True
            )
            tipo = st.selectbox(
                "Tipo de dependiente", options=tipo_keys,
                format_func=lambda k: tipo_mapa[k], key=f"{prefijo}_dep_tipo_{rid}",
                label_visibility="collapsed"
            )
        # Actualizar el espejo con lo tecleado en este render.
        datos[rid] = {"nombre": nombre, "ndoc": ndoc, "tdoc": tdoc, "tipo": tipo}
        dependientes.append({
            "nombre": nombre, "tipo_documento": tdoc,
            "numero_documento": ndoc, "tipo": tipo,
        })

    if st.button("➕ Agregar dependiente", key=f"{prefijo}_dep_add"):
        nid = st.session_state[seq_key]
        st.session_state[seq_key] += 1
        datos[nid] = {"nombre": "", "ndoc": "", "tdoc": "", "tipo": ""}
        st.session_state[ids_key].append(nid)
        st.rerun()

    return dependientes


def hay_cambios_laboral(prefijo, il_raw) -> bool:
    """True si el formulario laboral difiere de su estado inicial en pantalla.

    En el primer render guarda una "foto" normalizada del formulario en
    session_state (clave ``{prefijo}_snapshot_il``) y en renders posteriores
    compara los valores actuales contra ella. Se normaliza con la misma rutina
    del servicio para que la comparación refleje exactamente lo que se guardaría
    (evita falsos positivos por None/0/campos ausentes o registros antiguos).
    El snapshot se borra junto con el resto del estado del prefijo al guardar
    (ver ``limpiar_estado_laboral``), así que tras guardar se toma uno nuevo.
    """
    from app.services.usuario_service import UsuarioService
    actual = UsuarioService._construir_informacion_laboral(il_raw)
    snap_key = f"{prefijo}_snapshot_il"
    if snap_key not in st.session_state:
        st.session_state[snap_key] = actual
        return False
    return st.session_state[snap_key] != actual


def boton_guardar_laboral(prefijo, il_raw, key) -> bool:
    """Aviso de estado ("cambios sin guardar" / "al día") + botón de guardado.

    Centraliza el indicador para que el perfil propio y la administración se
    comporten igual. Devuelve True cuando el usuario pulsa el botón.
    """
    cambios = hay_cambios_laboral(prefijo, il_raw)
    if cambios:
        st.warning(
            "⚠️ **Tienes cambios sin guardar.** Lo que ves aquí todavía **no está "
            "registrado**. Pulsa **💾 Guardar información laboral** para conservarlo; "
            "de lo contrario se perderá al recargar la página o cerrar sesión."
        )
    else:
        st.caption("✔️ Información laboral al día — no hay cambios pendientes por guardar.")
    return st.button(
        "💾 Guardar información laboral",
        use_container_width=True,
        type="primary" if cambios else "secondary",
        key=key,
    )


def laboral_vacia(il):
    """True si el bloque de información laboral no tiene ningún dato diligenciado."""
    if il.get("grupo_trabajo"):
        return False
    ss = il.get("seguridad_social") or {}
    if any(
        (a.get("entidad") or a.get("valor") or a.get("valor_primer_mes") or a.get("valor_ultimo_mes") or a.get("radicado"))
        for a in ss.values()
    ):
        return False
    bancaria = il.get("bancaria") or {}
    if bancaria.get("banco") or bancaria.get("numero_cuenta"):
        return False
    tributaria = il.get("tributaria") or {}
    if tributaria.get("rut") or tributaria.get("declarante_renta"):
        return False
    if any((d.get("nombre") or "").strip() for d in (il.get("dependientes") or [])):
        return False
    return True


# ── Sección de firma ──────────────────────────────────────────────────────────

def render_seccion_firma(usuario_id, actualizado_por, prefijo, al_terminar=None):
    """Subir / previsualizar / guardar / eliminar la firma del usuario.

    al_terminar: callable(mensaje) opcional, ejecutado tras guardar/eliminar y antes
    del rerun (para que la página decida feedback/navegación). Si es None, usa toast.
    """
    servicio = FirmaService()
    firma_actual = servicio.obtener_imagen(usuario_id)

    def _finalizar(mensaje):
        if al_terminar:
            al_terminar(mensaje)
        else:
            st.toast(mensaje)
        st.rerun()

    if firma_actual:
        st.image(firma_actual, caption="Firma registrada", width=240)
        if st.button("🗑️ Eliminar firma", key=f"{prefijo}_del_firma"):
            servicio.eliminar_firma(usuario_id)
            _finalizar("Firma eliminada.")
    else:
        st.caption("No hay firma registrada.")

    archivo = st.file_uploader(
        "Subir firma (PNG/JPG sobre fondo blanco o claro, máx. 5 MB)",
        type=["png", "jpg", "jpeg"], key=f"{prefijo}_up_firma",
    )
    if archivo is not None:
        try:
            png = validar_y_procesar(archivo.name, archivo.getvalue())
            st.markdown("**Vista previa** (los cuadros indican transparencia; si ves un bloque sólido tapándolos, el fondo no se eliminó bien):")
            st.image(componer_sobre_fondo(png), width=240)
            st.warning(
                "⚠️ Esta firma **aún no está guardada** — solo es una vista previa. "
                "Pulsa **💾 Guardar firma** para registrarla."
            )
            if st.button("💾 Guardar firma", key=f"{prefijo}_save_firma", type="primary"):
                servicio.guardar_firma(usuario_id, archivo.name, archivo.getvalue(), usuario_actual=actualizado_por)
                _finalizar("Firma guardada correctamente.")
        except ValueError as e:
            st.error(str(e))
