import streamlit as st

# --- Obtener parámetros del query ---
target = st.session_state.get("target_page", None)

# --- Redirigir según el parámetro ---
if target:
    # Mapear los valores permitidos
    page_map = {
        "registro": "pages/registro.py"
    }

    if target in page_map:
        st.switch_page(page_map[target])
    else:
        st.error(f"❌ Página '{target}' no encontrada.")
else:
    st.warning("⚠️ No se ha especificado ninguna página en el parámetro 'page'.")
