"""El núcleo no conoce a los módulos (ADR-0013, GUIA-MODULOS §4.1 regla 2)."""
import ast
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
CORE = RAIZ / "app" / "core"


def _imports(archivo: Path):
    """Yields (nombre, level) para cada import. `level` es 0 para imports
    absolutos y el número de puntos para relativos (`from . import x` → 1,
    `from .. import x` → 2, etc.)."""
    arbol = ast.parse(archivo.read_text(encoding="utf-8"))
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            for alias in nodo.names:
                yield alias.name, 0
        elif isinstance(nodo, ast.ImportFrom):
            yield nodo.module or "", nodo.level


def test_core_no_importa_modulos():
    # Un import relativo con level >= 2 en app/core sube por encima de
    # app/core/ — el núcleo no tiene por qué subir (no puede terminar
    # importando app.modulos).
    violaciones = [
        f"{a.relative_to(RAIZ)}: {imp or '.' * level}"
        for a in CORE.rglob("*.py")
        for imp, level in _imports(a)
        if imp.startswith("app.modulos") or level >= 2
    ]
    assert violaciones == [], "\n".join(violaciones)


def test_modulos_no_se_importan_entre_si():
    modulos_dir = RAIZ / "app" / "modulos"
    violaciones = []
    for mod in [d for d in modulos_dir.iterdir() if d.is_dir() and not d.name.startswith("__")]:
        for a in mod.rglob("*.py"):
            for imp, _level in _imports(a):
                partes = imp.split(".")
                if imp == "app.modulos" or (imp.startswith("app.modulos.") and partes[2] != mod.name):
                    violaciones.append(f"{a.relative_to(RAIZ)}: {imp}")
    assert violaciones == [], "\n".join(violaciones)
