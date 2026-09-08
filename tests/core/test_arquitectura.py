"""El núcleo no conoce a los módulos (ADR-0013, GUIA-MODULOS §4.1 regla 2)."""
import ast
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
CORE = RAIZ / "app" / "core"


def _imports(archivo: Path):
    arbol = ast.parse(archivo.read_text(encoding="utf-8"))
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            for alias in nodo.names:
                yield alias.name
        elif isinstance(nodo, ast.ImportFrom) and nodo.module:
            yield nodo.module


def test_core_no_importa_modulos():
    violaciones = [
        f"{a.relative_to(RAIZ)}: {imp}"
        for a in CORE.rglob("*.py")
        for imp in _imports(a)
        if imp.startswith("app.modulos")
    ]
    assert violaciones == [], "\n".join(violaciones)


def test_modulos_no_se_importan_entre_si():
    modulos_dir = RAIZ / "app" / "modulos"
    violaciones = []
    for mod in [d for d in modulos_dir.iterdir() if d.is_dir() and not d.name.startswith("__")]:
        for a in mod.rglob("*.py"):
            for imp in _imports(a):
                if imp.startswith("app.modulos.") and not imp.startswith(f"app.modulos.{mod.name}"):
                    violaciones.append(f"{a.relative_to(RAIZ)}: {imp}")
    assert violaciones == [], "\n".join(violaciones)
