import streamlit as st


def show_dataframe(df, hide_index=True):
    """Mostrar un DataFrame en Streamlit con compatibilidad de versiones.

    Intenta usar la API nueva `width='stretch'`. Si esto lanza TypeError
    (versiones intermedias que esperan un entero), cae a
    `use_container_width=True`. Si todo falla, llama a `st.dataframe` sin
    argumentos de anchura.
    """
    try:
        # Intentar la API recomendada para 2026+ y aviso de deprecación
        st.dataframe(df, width="stretch", hide_index=hide_index)
        return
    except TypeError:
        # Entornos que todavía esperan int para width
        try:
            st.dataframe(df, use_container_width=True, hide_index=hide_index)
            return
        except Exception:
            # Último recurso: mostrar sin parámetros de anchura
            st.dataframe(df, hide_index=hide_index)
            return
    except Exception:
        # Cualquier otro error, intentar la ruta fallback
        try:
            st.dataframe(df, use_container_width=True, hide_index=hide_index)
        except Exception:
            st.dataframe(df, hide_index=hide_index)
