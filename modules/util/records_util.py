import streamlit as st

# def resolver_jugadora_final(jugadora_header, jug_df_filtrado, jug_df, tipo):

#     # Si no hay NINGUNA jugadora disponible → fin
#     if jug_df_filtrado.empty:
#         st.session_state["last_player_id"] = None
#         st.error(f"No hay más jugadoras disponibles para registrar {tipo}")
#         st.stop()

#     # ID actual entregado por el header
#     new_id = str(jugadora_header["id_jugadora"]) if jugadora_header else None

#     # IDs válidos en el filtrado actual
#     current_ids = jug_df_filtrado["id_jugadora"].astype(str).tolist()

#     # ID bloqueado previamente
#     prev_id = st.session_state.get("last_player_id")

#     # ------------------------------
#     # 1. Primera asignación
#     # ------------------------------
#     if prev_id is None:
#         if new_id is not None:
#             st.session_state["last_player_id"] = new_id
#         else:
#             # Si no había selección, tomamos la PRIMERA jugadora disponible
#             st.session_state["last_player_id"] = current_ids[0]

#     else:
#         # ------------------------------
#         # 2. Si cambia la jugadora del header
#         # ------------------------------
#         if new_id != prev_id:

#             # Si la jugadora anterior ya no existe → reset a la primera disponible
#             if prev_id not in current_ids:
#                 st.session_state["last_player_id"] = current_ids[0]
#                 st.warning("La jugadora seleccionada ya no se encontraba disponible.")
#                 st.rerun()

#             # Cambio manual → actualizar bloqueada
#             st.session_state["last_player_id"] = new_id

#     # ------------------------------
#     # 3. Jugadora final bloqueada
#     # ------------------------------
#     locked_id = st.session_state.get("last_player_id")

#     if locked_id is None:
#         st.error("Error interno: No se pudo resolver la jugadora seleccionada.")
#         st.rerun()

#     # Buscar jugadora final exacta
#     jugadora_rows = jug_df[jug_df["id_jugadora"].astype(str) == locked_id]

#     if jugadora_rows.empty:
#         st.session_state["last_player_id"] = None
#         st.error("La jugadora seleccionada ya no se encuentra disponible.")
#         st.stop()

#     # Devolver jugadora final
#     return jugadora_rows.iloc[0].to_dict()

import streamlit as st

def resolver_jugadora_final(jugadora_header, jug_df_filtrado, jug_df, tipo, ctx_key: str):
    """
    ctx_key debe ser estable por (session_id + plantel + tipo + turno).
    Así evitamos que un cambio de turno/plantel rompa la selección.
    """
    # if jug_df_filtrado.empty:
    #     st.session_state[f"last_player_id__{ctx_key}"] = None
    #     st.error(f"No hay más jugadoras disponibles para registrar {tipo}")
    #     st.stop()

    current_ids = jug_df_filtrado["id_jugadora"].astype(str).tolist()
    state_key = f"last_player_id__{ctx_key}"

    prev_id = st.session_state.get(state_key)
    new_id = str(jugadora_header["id_jugadora"]) if jugadora_header else None

    # 1) Si no había bloqueada aún
    if prev_id is None:
        st.session_state[state_key] = new_id if (new_id in current_ids) else current_ids[0]

    # 2) Cambio manual real: solo si el nuevo id existe en el filtrado actual
    elif new_id and new_id != prev_id and new_id in current_ids:
        st.session_state[state_key] = new_id

    # 3) Si la bloqueada ya no existe, fallback
    locked_id = st.session_state.get(state_key)
    if locked_id not in current_ids:
        locked_id = current_ids[0]
        st.session_state[state_key] = locked_id
        print("no encontrada")

    # 4) Resolver jugadora final desde el DF completo
    rows = jug_df[jug_df["id_jugadora"].astype(str) == locked_id]
    if rows.empty:
        st.session_state[state_key] = None
        st.error("La jugadora seleccionada ya no se encuentra disponible.")
        st.stop()

    return rows.iloc[0].to_dict()
