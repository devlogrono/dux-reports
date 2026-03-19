import sys, os

# Ruta raíz del proyecto
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Nueva ruta donde está tu código real
MODULES_PATH = os.path.join(ROOT, "modules")

print(">> PYTEST LOADING CONFTEXT — ADDING:", MODULES_PATH)

# Insertar modules/ al path
sys.path.insert(0, MODULES_PATH)
