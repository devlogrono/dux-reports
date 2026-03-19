import json
import streamlit as st
from pathlib import Path

_LANG_DIR = Path(__file__).parent / "lang"

#@st.cache_resource(show_spinner=False)
def _load_lang(lang: str) -> dict:
    """Carga el archivo de idioma (lang/en.json, lang/pt.json, etc.)."""
    path = _LANG_DIR / f"{lang}.json"
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def t(text: str) -> str:
    """
    Devuelve la traducción del texto original según el idioma activo.
    Si el idioma es español ('es') o no se encuentra traducción, devuelve el texto original.
    """
    lang = st.session_state.get("lang", "es")

    # Español = texto original
    if lang == "es":
        return text

    data = _load_lang(lang)
    #st.text(f"Idioma seleccionado: {lang}")
    return data.get(text, text)

def language_selector(label: str = ":material/language: Idioma / Language", default: str = "es"):
    """Selector de idioma persistente en la barra lateral."""
    languages = {"Español": "es", "English": "en", "Português": "pt", "Français": "fr"}

    if "lang" not in st.session_state:
        st.session_state["lang"] = default

    lang = st.session_state["lang"]
    #st.text(f"Ultimo Idioma seleccionado: {st.session_state['lang']}")
    
    choice = st.sidebar.selectbox(
        label,
        list(languages.keys()),
        index=list(languages.values()).index(lang),
        key="lang_selector"
    )
    st.session_state["lang"] = languages[choice]
    return st.session_state["lang"]
