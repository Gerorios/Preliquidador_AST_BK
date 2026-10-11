"""scripts/refrescar_testing.py sólo copia tablas que el modelo conoce.

El script hace DROP + CREATE de cada tabla de TABLAS en `testing` a partir de
producción. Una tabla que ya no está en el modelo (como `usuario_modulo`, que se
borra en core/003) no tiene que seguir en la lista.
"""
import importlib.util
from pathlib import Path

import dotenv

# Importar app.main registra en Base.metadata las tablas del núcleo y las de
# los módulos activos, igual que al arrancar la app.
import app.main  # noqa: F401
from app.core.database import Base

RUTA_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "refrescar_testing.py"


def _cargar_script(monkeypatch):
    # El script llama a load_dotenv() al importarse: se anula para que no cargue
    # ningún .env en el entorno del proceso de tests.
    monkeypatch.setattr(dotenv, "load_dotenv", lambda *a, **k: False)
    spec = importlib.util.spec_from_file_location("refrescar_testing", RUTA_SCRIPT)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_cada_tabla_del_script_existe_en_el_modelo(monkeypatch):
    script = _cargar_script(monkeypatch)

    fuera_del_modelo = [t for t in script.TABLAS if t not in Base.metadata.tables]

    assert fuera_del_modelo == []
