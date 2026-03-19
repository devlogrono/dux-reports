import streamlit.components.v1 as components

from modules.auth_system import auth_config

if auth_config.SERVER_ENV == "prod":
    _cookie_component = components.declare_component(
        "cookie_manager",
        url=auth_config.COMPONENT_DOMAIN
    )
else:
    _cookie_component = components.declare_component(
        name="cookie_manager",
        url="http://localhost:3001",  # usando modo development
    )

def cookie_set(name: str, value: str, days: int = 7, **kwargs):
    return _cookie_component(
        action="set",
        name=name,
        value=value,
        days=days,
        **kwargs
    )

def cookie_get(name: str, **kwargs):
    return _cookie_component(
        action="get",
        name=name,
        **kwargs
    )

def cookie_delete(name: str, **kwargs):
    return _cookie_component(
        action="delete",
        name=name,
        **kwargs
    )