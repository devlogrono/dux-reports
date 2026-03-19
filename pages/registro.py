
import streamlit as st

from modules.app_config import config
from modules.db.db_absences import load_active_absences_db
from modules.db.db_competitions import load_competitions_db
from modules.db.db_players import load_players_db
from modules.util.records_util import resolver_jugadora_final
config.init_config()

from modules.auth_system.auth_core import init_app_state, validate_login
from modules.i18n.i18n import t
from modules.db.db_records import get_records_db
from modules.db.db_catalogs import load_catalog_list_db
from modules.ui.absents_ui import absents_form, filtrar_jugadoras_ausentes

from modules.ui.ui_components import selection_header_registro
from modules.ui.template_ui import template_form

# Authentication gate
init_app_state()
is_valid = validate_login()

##:red[:material/check_in_out:]
st.header(t("Registro"), divider="red")

# Load reference data
template_df = get_records_db()
jug_df = load_players_db()
comp_df = load_competitions_db()

tipo_ausencia_df = load_catalog_list_db("tipo_ausencia", as_df=True)
ausencias_df = load_active_absences_db()

jug_df = filtrar_jugadoras_ausentes(jug_df, ausencias_df)

tab1, tab2 = st.tabs([ "template :material/check_in_out:", "Ausencias :material/event_busy:"])

with tab1:
    jugadora, tipo, turno, jug_df_filtrado = selection_header_registro(jug_df, comp_df, template_df)
    
    if st.session_state.get("submitted"):
        st.session_state["submitted"] = False
 
    template_form(jugadora, tipo, turno)
    
with tab2:
     absents_form(comp_df, jug_df, tipo_ausencia_df, ausencias_df, template_df)
