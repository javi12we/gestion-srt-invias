"""Componentes de UI reutilizables para el balance general del contrato, prórroga y plan de pagos.

Se utilizan tanto en la administración de usuarios (`pages_admin/admin_usuarios.py`)
como en el perfil del contratista (`pages/2_mi_perfil.py`).
"""

import pandas as pd
import streamlit as st
from datetime import datetime, date

from app.core.balance_contrato import calcular_balance_pagos
from app.core.ui_pesos import entrada_pesos, interpretar_pesos

_MAX_PAGOS = 20

_COL_NUM = "N° Pago"
_COL_FECHA = "Fecha"
_COL_BRUTO = "Valor Bruto"
_COL_DEDUC = "Deducciones"
_COL_NETO = "Valor Neto"
_COLUMNAS_PAGO = [_COL_NUM, _COL_FECHA, _COL_BRUTO, _COL_DEDUC, _COL_NETO]
_COLUMNAS_VALOR = [_COL_BRUTO, _COL_DEDUC, _COL_NETO]


def _filas_desde_pagos(pagos: list) -> list:
    """Pagos guardados en la BD -> filas de la tabla de pagos."""
    filas = []
    for p in pagos:
        fecha = p.get("fecha_pago")
        if fecha and hasattr(fecha, "date"):
            fecha = fecha.date()
        numero = p.get("numero_pago") or ""
        if numero.startswith("Pago No."):
            numero = ""
        filas.append({
            _COL_NUM: numero,
            _COL_FECHA: fecha,
            _COL_BRUTO: int(p.get("valor_bruto_pago") or 0),
            _COL_DEDUC: int(p.get("deducciones_pago") or 0),
            _COL_NETO: int(p.get("valor_neto_pago") or 0),
        })
    return filas


def _tabla_pagos(filas: list) -> pd.DataFrame:
    """Los valores van como texto ("$ 3.057.600") y no como columnas numéricas: así
    lo que se pega en una celda lo interpreta interpretar_pesos y no el navegador."""
    df = pd.DataFrame(filas, columns=_COLUMNAS_PAGO)
    df[_COL_NUM] = df[_COL_NUM].astype("object")
    df[_COL_FECHA] = pd.to_datetime(df[_COL_FECHA])
    for columna in _COLUMNAS_VALOR:
        df[columna] = df[columna].map(_formato_cop).astype("object")
    return df


def _filas_desde_tabla(df: pd.DataFrame) -> tuple[list, list]:
    """Tabla editada -> (filas limpias, avisos de celdas con un valor no numérico).
    Las celdas vacías quedan como '' / None / 0."""
    filas = []
    avisos = []
    for posicion, registro in enumerate(df.to_dict("records"), start=1):
        numero = registro[_COL_NUM]
        fecha = registro[_COL_FECHA]
        fila = {
            _COL_NUM: "" if pd.isna(numero) else str(numero).strip(),
            _COL_FECHA: None if pd.isna(fecha) else pd.Timestamp(fecha).date(),
        }
        for columna in _COLUMNAS_VALOR:
            crudo = registro[columna]
            valor = 0 if pd.isna(crudo) else interpretar_pesos(crudo)
            if valor is None:
                avisos.append(f"Pago #{posicion}, {columna}: «{crudo}» no es un valor válido y se toma como 0.")
                valor = 0
            fila[columna] = valor
        filas.append(fila)
    return filas, avisos


def _miles(valor) -> str:
    return f"{int(valor):,}".replace(",", ".")


def _formato_cop(valor: int) -> str:
    return "$ " + _miles(valor)


def _firma_pagos(pagos: list) -> list:
    """Huella de los pagos guardados en la BD, para detectar que cambiaron por
    fuera de este formulario (cargue masivo desde Excel u otra sesión)."""
    return [
        (
            p.get("numero_pago"),
            str(p.get("fecha_pago")),
            p.get("valor_bruto_pago"),
            p.get("deducciones_pago"),
            p.get("valor_neto_pago"),
        )
        for p in pagos
    ]


def render_balance_y_pagos(prefijo: str, c: dict, deshabilitado: bool = False, valor_contrato=None):
    """Renderiza el Balance General, Prórroga y el Plan de Pagos interactivo de un contrato.
    
    ``valor_contrato`` es el "Valor total de contrato" tal como está digitado en el
    formulario que contiene este componente (si no se pasa, el guardado en ``c``).

    Devuelve un diccionario con los campos listos para enviar al servicio de actualización.
    """
    c = c or {}
    if valor_contrato is None:
        valor_contrato = c.get("valor")
    
    # Inyectar CSS para seguridad adicional, botón rojo y tooltips dinámicos idénticos a los de Información Laboral
    bg_color = "#FFFFFF"
    text_color = "#333333"
    border_color = "#E0E0E0"
    strong_color = "#111111"
    
    st.markdown(
        f"""
        <style>
        /* Ocultar el ícono de enlace (anchor link) y sus contenedores */
        a.header-anchor, [data-testid="stHeaderActionElements"] {{
            display: none !important;
            visibility: hidden !important;
        }}
        /* Hacer el botón toggle de color rojo oscuro/tenue y más compacto */
        button[key*="_btn_toggle_balance"] {{
            background-color: #d32f2f !important;
            background: #d32f2f !important;
            color: white !important;
            font-weight: bold !important;
            padding: 10px 20px !important;
            font-size: 15px !important;
            border-radius: 8px !important;
            border: none !important;
        }}
        button[key*="_btn_toggle_balance"]:hover {{
            background-color: #b71c1c !important;
            background: #b71c1c !important;
        }}
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
            margin-left: 6px;
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
            width: 320px; /* Ancho optimizado para evitar desbordes */
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

        /* Variante para alinear a la derecha cuando el tooltip está en la última columna */
        .srti-tooltip-container.srti-tooltip-align-right .srti-tooltip-content {{
            left: auto !important;
            right: 0 !important;
        }}

        /* Flecha apuntando hacia arriba */
        .srti-tooltip-content::after {{
            content: "";
            position: absolute;
            bottom: 100%;
            left: 8px;
            transform: none;
            border-width: 6px;
            border-style: solid;
            border-color: transparent transparent {bg_color} transparent;
        }}
        
        /* Flecha para la variante de la derecha */
        .srti-tooltip-container.srti-tooltip-align-right .srti-tooltip-content::after {{
            left: auto !important;
            right: 8px !important;
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
        </style>
        """,
        unsafe_allow_html=True
    )
    
    # Control del estado desplegado/oculto
    show_key = f"{prefijo}_show_balance_general"
    if show_key not in st.session_state:
        st.session_state[show_key] = False
        
    btn_label = "⬇️ Mostrar Balance general y consolidado de pagos" if not st.session_state[show_key] else "⬆️ Ocultar Balance general y consolidado de pagos"
    
    # Botón tipo toggle rojo
    if st.button(btn_label, key=f"{prefijo}_btn_toggle_balance", type="primary", use_container_width=True):
        st.session_state[show_key] = not st.session_state[show_key]
        st.rerun()

    # Si está oculto, devolvemos los valores actuales para que al guardar el formulario no se borren
    if not st.session_state[show_key]:
        return {
            "tiene_inventario": bool(c.get("tiene_inventario")),
            "desc_inventario": c.get("desc_inventario"),
            "prorrogra_contrato": c.get("prorrogra_contrato") or {"tiene_prorroga": False, "fecha_prorrogra": None, "radicado_prorrogra": None},
            "adiciones_contrato": c.get("adiciones_contrato") or {"tiene_adiciones": False, "valor_adicion": None},
            "pagos": c.get("pagos") or []
        }
        
    st.write("")
    if deshabilitado:
        st.info("⚠️ Este contrato está finalizado. La información de balance, prórroga y pagos está en modo de solo lectura.")

    # Renderizamos el título de la sección y su tooltip dinámico alineado a la derecha (sobresale a la izquierda)
    st.markdown(
        """
        <div style="display: flex; align-items: center; gap: 8px;">
            <h3 style="margin: 0; padding: 0;">⚖️ Balance general y consolidado de pagos</h3>
            <div class="srti-tooltip-container srti-tooltip-align-right">
                <span class="srti-tooltip-icon" tabindex="0">ⓘ
                    <div class="srti-tooltip-content">
                        <h4>⚖️ Balance general y consolidado de pagos</h4>
                        <p>Este balance de pagos se realizará antes de finalizar el contrato.</p>
                        <p>Se debe ingresar cada uno de los valores presupuestales del contrato que se encontrarán dentro del repositorio de balances antes de finalizar el contrato.</p>
                    </div>
                </span>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    st.write("")
    
    # 1. Sección: Inventario con Tooltip alineado a la izquierda (sobresale a la derecha)
    st.markdown(
        """
        <div style="display: flex; align-items: center; gap: 8px; margin-top: 10px; margin-bottom: 5px;">
            <strong style="font-size: 16px; margin: 0; padding: 0;">📦 Inventario del Contrato</strong>
            <div class="srti-tooltip-container" style="margin: 0;">
                <span class="srti-tooltip-icon" tabindex="0">ⓘ
                    <div class="srti-tooltip-content">
                        <h4>📦 Inventario del Contrato</h4>
                        <p>Esta opción debe marcarse únicamente si al contratista se le asignaron bienes de propiedad de la institución durante la vigencia del contrato.</p>
                        <p><strong>Ejemplo:</strong> Equipos de cómputo (computador portátil/escritorio), periféricos, herramientas de hardware u otros activos institucionales devueltos o por devolver.</p>
                    </div>
                </span>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    c1, c2 = st.columns([1, 3])
    with c1:
        tiene_inv = st.checkbox(
            "¿Tiene inventario?",
            value=bool(c.get("tiene_inventario")),
            key=f"{prefijo}_tiene_inv",
            disabled=deshabilitado
        )
    with c2:
        desc_inv = None
        if tiene_inv:
            desc_inv = st.text_input(
                "Descripción de inventario (90/max)",
                value=c.get("desc_inventario") or "",
                key=f"{prefijo}_desc_inv",
                placeholder="Ingresa la descripción del inventario...",
                disabled=deshabilitado,
                max_chars=90
            )
            
    # 2. Sección: Valores financieros con Tooltip alineado a la izquierda (sobresale a la derecha)
    st.markdown(
        """
        <div style="display: flex; align-items: center; gap: 8px; margin-top: 15px; margin-bottom: 5px;">
            <strong style="font-size: 16px; margin: 0; padding: 0;">💵 Balance Financiero</strong>
            <div class="srti-tooltip-container" style="margin: 0;">
                <span class="srti-tooltip-icon" tabindex="0">ⓘ
                    <div class="srti-tooltip-content">
                        <h4>💵 Balance Financiero</h4>
                        <p>El contratista deberá registrar el balance financiero de su contrato para poder generar el documento de balance financiero al finalizar el contrato.</p>
                    </div>
                </span>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    # Función helper inline para renderizar una etiqueta junto con su tooltip con diseño idéntico
    def render_label_con_tooltip(label: str, tooltip_titulo: str, tooltip_contenido: str, align_right: bool = False):
        align_class = " srti-tooltip-align-right" if align_right else ""
        st.markdown(
            f"""
            <div style="display: flex; align-items: center; gap: 6px;">
                <span style="font-size: 14px; font-weight: 500; color: #333333;">{label}</span>
                <div class="srti-tooltip-container{align_class}" style="margin: 0; display: inline-flex;">
                    <span class="srti-tooltip-icon" tabindex="0" style="margin: 0; width: 16px; height: 16px; font-size: 12px;">ⓘ
                        <div class="srti-tooltip-content" style="font-weight: normal;">
                            <h4>{tooltip_titulo}</h4>
                            <p>{tooltip_contenido}</p>
                        </div>
                    </span>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

    # Los dos valores del balance no se digitan: se calculan con los pagos del
    # consolidado. Se ubican aquí pero se llenan al final de la función, cuando
    # ya se conocen las filas de pago de este render.
    contenedor_balance = st.container()

    # 3. Sección: Prórroga del contrato con Tooltip (sobresale a la derecha)
    st.markdown(
        """
        <div style="display: flex; align-items: center; gap: 8px; margin-top: 15px; margin-bottom: 5px;">
            <strong style="font-size: 16px; margin: 0; padding: 0;">⏳ Prórroga del contrato</strong>
            <div class="srti-tooltip-container" style="margin: 0;">
                <span class="srti-tooltip-icon" tabindex="0">ⓘ
                    <div class="srti-tooltip-content">
                        <h4>⏳ Prórroga del contrato</h4>
                        <p>Es la extensión del plazo de vigencia de un contrato.</p>
                        <p>Se debe indicar si tiene una prórroga y, en caso afirmativo, describirla ingresando el radicado o memorando que la valida junto con su fecha de vencimiento.</p>
                    </div>
                </span>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    prorrogra_c = c.get("prorrogra_contrato") or {}
    
    tiene_pror = st.checkbox(
        "¿Tiene prórroga?",
        value=bool(prorrogra_c.get("tiene_prorroga")),
        key=f"{prefijo}_tiene_pror",
        disabled=deshabilitado
    )
    
    fecha_pror = None
    radicado_pror = None
    if tiene_pror:
        cp1, cp2 = st.columns(2)
        with cp1:
            fecha_pror_val = prorrogra_c.get("fecha_prorrogra")
            if fecha_pror_val and hasattr(fecha_pror_val, "date"):
                fecha_pror_val = fecha_pror_val.date()
            elif isinstance(fecha_pror_val, datetime):
                fecha_pror_val = fecha_pror_val.date()
            
            fecha_pror = st.date_input(
                "Fecha de la prórroga",
                value=fecha_pror_val,
                format="DD/MM/YYYY",
                key=f"{prefijo}_fecha_pror",
                disabled=deshabilitado
            )
        with cp2:
            radicado_pror = st.text_input(
                "Doc. / Des / Radicado de la prórroga",
                value=prorrogra_c.get("radicado_prorrogra") or "",
                key=f"{prefijo}_rad_pror",
                disabled=deshabilitado
            )

    # 3.5 Sección: Adiciones del contrato
    st.markdown(
        """
        <div style="display: flex; align-items: center; gap: 8px; margin-top: 15px; margin-bottom: 5px;">
            <strong style="font-size: 16px; margin: 0; padding: 0;">➕ Adiciones del contrato</strong>
            <div class="srti-tooltip-container" style="margin: 0;">
                <span class="srti-tooltip-icon" tabindex="0">ⓘ
                    <div class="srti-tooltip-content">
                        <h4>Adiciones</h4>
                        <p>Dinero incluido al contrato por cualquier otro medio extra al contrato que incremente la suma total del contrato.</p>
                    </div>
                </span>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    adiciones_c = c.get("adiciones_contrato") or {}
    tiene_adi = st.checkbox(
        "¿Tiene adiciones?",
        value=bool(adiciones_c.get("tiene_adiciones")),
        key=f"{prefijo}_tiene_adi",
        disabled=deshabilitado
    )
    
    val_adicion = None
    if tiene_adi:
        val_adicion_val = adiciones_c.get("valor_adicion")
        val_adicion = entrada_pesos(
            "Valor de la adición (COP)",
            minimo=1,
            value=val_adicion_val,
            key=f"{prefijo}_val_adicion",
            disabled=deshabilitado
        )

    # 4. Sección: Pagos con Tooltip detallado (sobresale a la derecha)
    st.markdown(
        """
<div style="display: flex; align-items: center; gap: 8px; margin-top: 15px; margin-bottom: 5px;">
<strong style="font-size: 16px; margin: 0; padding: 0;">💳 Consolidado de Pagos</strong>
<div class="srti-tooltip-container" style="margin: 0;">
<span class="srti-tooltip-icon" tabindex="0">ⓘ
<div class="srti-tooltip-content" style="width: 400px;">
<h4>💳 Consolidado de Pagos</h4>
<p>El consolidado de pagos se encuentra en el balance enviado previamente al contratista, ya sea por correo electrónico o URL, en el cual deberá copiar y pegar o diligenciar los datos correspondientes a este balance.</p>
<p><strong>Detalles de los campos:</strong></p>
<p><strong>• Número de pago:</strong> Es el número interno del pago que emite Gestión Financiera.</p>
<p><strong>• Fecha de pago:</strong> Es la fecha de realización del pago, se encuentra en la base de datos entregada.</p>
<p><strong>• Deducciones:</strong> Las deducciones son descuentos o reducciones aplicadas al contrato. Deberá colocar lo que indica el balance enviado para ese pago.</p>
<p><strong>• Valor neto:</strong> Será el valor del pago correspondiente a ese mes, este valor deberá ser exacto según la información enviada al contratista.</p>
</div>
</span>
</div>
</div>
        """,
        unsafe_allow_html=True
    )
    pagos_lista = c.get("pagos") or []

    base_key = f"{prefijo}_pagos_base"
    borrador_key = f"{prefijo}_pagos_borrador"
    firma_key = f"{prefijo}_pagos_firma"
    version_key = f"{prefijo}_pagos_version"

    # La tabla se siembra con los pagos de la BD. Si esos pagos cambian por fuera
    # de este formulario (cargue masivo desde Excel, otra sesión, o un guardado),
    # el borrador se descarta y la tabla se vuelve a sembrar: de lo contrario la
    # pantalla mostraría pagos viejos y el siguiente guardado pisaría los nuevos.
    firma_bd = _firma_pagos(pagos_lista)
    # (base_key puede faltar con la firma ya puesta: sesiones abiertas desde antes
    # de que los pagos fueran una tabla guardaban la firma pero no la base.)
    if st.session_state.get(firma_key) != firma_bd or base_key not in st.session_state:
        st.session_state[firma_key] = firma_bd
        st.session_state[base_key] = _filas_desde_pagos(pagos_lista)
        st.session_state.pop(borrador_key, None)
        st.session_state[version_key] = st.session_state.get(version_key, 0) + 1

    # Streamlit borra el estado de la tabla cuando no se dibuja (sección oculta,
    # otra página). El borrador sobrevive y se usa como nueva base para no perder
    # lo tecleado sin guardar.
    editor_key = f"{prefijo}_pagos_editor_{st.session_state[version_key]}"
    if editor_key not in st.session_state and borrador_key in st.session_state:
        st.session_state[base_key] = st.session_state[borrador_key]

    df_pagos = st.data_editor(
        _tabla_pagos(st.session_state[base_key]),
        key=editor_key,
        num_rows="fixed" if deshabilitado else "dynamic",
        disabled=deshabilitado,
        hide_index=True,
        use_container_width=True,
        column_config={
            _COL_NUM: st.column_config.TextColumn(
                _COL_NUM, required=True, max_chars=40, width="small", alignment="center"
            ),
            _COL_FECHA: st.column_config.DateColumn(
                _COL_FECHA, format="DD/MM/YYYY", required=True, default=date.today(), width="small",
                alignment="center",
            ),
            **{
                columna: st.column_config.TextColumn(
                    columna, required=True, default=_formato_cop(0), max_chars=25, alignment="center"
                )
                for columna in _COLUMNAS_VALOR
            },
        },
    )

    filas_pagos, avisos_pagos = _filas_desde_tabla(df_pagos)
    st.session_state[borrador_key] = filas_pagos
    for aviso in avisos_pagos:
        st.error(aviso)

    if not deshabilitado:
        st.caption(
            f"{len(filas_pagos)} de {_MAX_PAGOS} pagos. Edita directamente en la tabla: la última fila "
            "agrega un pago y, al seleccionar una fila, la papelera la elimina. Los valores se toman en "
            "pesos sin decimales (1000,00 se toma como 1.000)."
        )
    if len(filas_pagos) > _MAX_PAGOS:
        st.warning(
            f"Un contrato admite máximo {_MAX_PAGOS} pagos: solo se guardarán los primeros {_MAX_PAGOS} de la tabla."
        )

    pagos_retorno = [
        {
            "numero_pago": fila[_COL_NUM],
            "fecha_pago": fila[_COL_FECHA],
            "valor_bruto_pago": fila[_COL_BRUTO],
            "deducciones_pago": fila[_COL_DEDUC],
            "valor_neto_pago": fila[_COL_NETO],
        }
        for fila in filas_pagos[:_MAX_PAGOS]
        if fila[_COL_NUM] and fila[_COL_FECHA]
    ]
    if len(pagos_retorno) < len(filas_pagos[:_MAX_PAGOS]):
        st.warning("Los pagos sin número o sin fecha no se guardan.")

    st.markdown("<hr style='margin:15px 0; border: 1.5px solid #FF8C00;'>", unsafe_allow_html=True)

    # Mismo criterio que el servicio al guardar: un pago sin número no se guarda.
    pagos_contables = [p for p in pagos_retorno if (p["numero_pago"] or "").strip()]
    val_tot_pagado, val_total_por_pagar = calcular_balance_pagos(valor_contrato, pagos_contables)
    clave_por_pagar = f"{prefijo}_val_total_por_pagar_calc"
    clave_pagado = f"{prefijo}_val_tot_pagado_calc"
    st.session_state[clave_por_pagar] = _formato_cop(val_total_por_pagar)
    st.session_state[clave_pagado] = _formato_cop(val_tot_pagado)
    with contenedor_balance:
        col1, col3 = st.columns(2)
        with col1:
            render_label_con_tooltip(
                "Valor Total por Pagar del contrato (COP)",
                "Valor total por pagar",
                "Se calcula automáticamente: Valor total de contrato menos Valor total pagado del contrato."
            )
            st.text_input("label_oculto_total_por_pagar", key=clave_por_pagar, disabled=True, label_visibility="collapsed")
        with col3:
            render_label_con_tooltip(
                "Valor total pagado del contrato (COP)",
                "Valor total pagado del contrato",
                "Se calcula automáticamente: suma de los valores brutos de todos los pagos del consolidado.",
                align_right=True
            )
            st.text_input("label_oculto_total_pagado", key=clave_pagado, disabled=True, label_visibility="collapsed")
        st.caption(
            "Estos dos valores se calculan solos con el consolidado de pagos y alimentan el formato Balance General CPS."
        )
        if val_tot_pagado > int(valor_contrato or 0):
            st.warning(
                "La suma de los pagos supera el Valor total de contrato. Revisa el valor del contrato o los pagos registrados."
            )

    return {
        "tiene_inventario": tiene_inv,
        "desc_inventario": desc_inv if tiene_inv else None,
        "prorrogra_contrato": {
            "tiene_prorroga": tiene_pror,
            "fecha_prorrogra": fecha_pror if tiene_pror else None,
            "radicado_prorrogra": radicado_pror if tiene_pror else None
        },
        "adiciones_contrato": {
            "tiene_adiciones": tiene_adi,
            "valor_adicion": val_adicion if tiene_adi else None
        },
        "pagos": pagos_retorno
    }

def limpiar_estado_balance_pagos(prefijo: str):
    """Limpia el estado de sesión para el balance de pagos de un prefijo dado."""
    for key in list(st.session_state.keys()):
        if key.startswith(f"{prefijo}_"):
            del st.session_state[key]
