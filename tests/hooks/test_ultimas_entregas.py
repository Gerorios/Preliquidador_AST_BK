"""Hook SessionStart `.claude/hooks/ultimas-entregas.mjs`.

Cada sesión de Claude Code arranca con lo que este hook imprime: las 2 últimas
entradas de `docs/BITACORA.md`. Si se rompe, la sesión arranca sin saber qué se
hizo último y nadie se entera (el hook sale 0 siempre, a propósito). Estos
tests lo corren con `node` sobre bitácoras de juguete armadas en `tmp_path`,
imitando los lugares donde se abren las sesiones: la carpeta que contiene los
dos repos, el repo del backend, un worktree del front y un clon con otro nombre.
"""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[2] / ".claude" / "hooks" / "ultimas-entregas.mjs"
NODE = shutil.which("node")

pytestmark = pytest.mark.skipif(NODE is None, reason="node no está instalado")

ENCABEZADO_BITACORA = "# Bitácora\n\nIntroducción del diario: no es una entrada.\n\n"
ENTRADA_A = "## 2026-01-01 — A\n\ncuerpo-A\n\n"
ENTRADA_B = "## 2026-01-02 — B\n\ncuerpo-B\n\n"
ENTRADA_C = "## 2026-01-03 — C\n\ncuerpo-C\n"
TRES_ENTRADAS = ENCABEZADO_BITACORA + ENTRADA_A + ENTRADA_B + ENTRADA_C


def _escribir_bitacora(docs: Path, contenido: str, eol: str = "\n") -> Path:
    docs.mkdir(parents=True, exist_ok=True)
    ruta = docs / "BITACORA.md"
    # newline="" para que Python no traduzca los saltos: el caso CRLF necesita
    # los \r\n tal cual en el archivo.
    with open(ruta, "w", encoding="utf-8", newline="") as f:
        f.write(contenido.replace("\n", eol))
    return ruta


def _correr(proyecto: Path) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    # La sesión que corre los tests puede traer su propio CLAUDE_PROJECT_DIR:
    # se pisa siempre, para que el hook mire sólo la carpeta de juguete.
    env["CLAUDE_PROJECT_DIR"] = str(proyecto)
    resultado = subprocess.run(
        [NODE, str(HOOK)], cwd=proyecto, env=env, capture_output=True, timeout=30
    )
    # Bytes, no text=True: en Windows text=True convierte \r\n en \n y el caso
    # CRLF no podría ver si el hook dejó pasar retornos de carro.
    resultado.stdout = resultado.stdout.decode("utf-8")
    resultado.stderr = resultado.stderr.decode("utf-8", errors="replace")
    return resultado


def _assert_b_y_c_en_orden(salida: str):
    assert "cuerpo-A" not in salida
    assert "## 2026-01-02 — B" in salida and "cuerpo-B" in salida
    assert "## 2026-01-03 — C" in salida and "cuerpo-C" in salida
    assert salida.index("cuerpo-B") < salida.index("cuerpo-C")
    assert "Introducción del diario" not in salida


# (1) Sesión abierta en la carpeta que contiene los dos repos.
def test_desde_la_carpeta_de_los_dos_repos_imprime_las_dos_ultimas(tmp_path):
    bitacora = _escribir_bitacora(tmp_path / "backend_preliquidacion" / "docs", TRES_ENTRADAS)
    r = _correr(tmp_path)
    assert r.returncode == 0, r.stderr
    _assert_b_y_c_en_orden(r.stdout)
    assert str(bitacora) in r.stdout


# (2) Sesión abierta en el repo del backend.
def test_desde_el_backend_imprime_las_dos_ultimas(tmp_path):
    backend = tmp_path / "backend_preliquidacion"
    bitacora = _escribir_bitacora(backend / "docs", TRES_ENTRADAS)
    r = _correr(backend)
    assert r.returncode == 0, r.stderr
    _assert_b_y_c_en_orden(r.stdout)
    assert str(bitacora) in r.stdout


# (3) Worktree del front: la bitácora del backend está subiendo por los ancestros.
def test_desde_un_worktree_del_front_encuentra_la_del_backend(tmp_path):
    bitacora = _escribir_bitacora(tmp_path / "backend_preliquidacion" / "docs", TRES_ENTRADAS)
    worktree = tmp_path / "frontend_preliquidacion" / ".claude" / "worktrees" / "x"
    worktree.mkdir(parents=True)
    r = _correr(worktree)
    assert r.returncode == 0, r.stderr
    _assert_b_y_c_en_orden(r.stdout)
    assert str(bitacora) in r.stdout


# (4) Clon del backend con otro nombre de carpeta: usa su propia docs/BITACORA.md.
def test_clon_con_otro_nombre_usa_su_propia_bitacora(tmp_path):
    clon = tmp_path / "otro_nombre"
    bitacora = _escribir_bitacora(clon / "docs", TRES_ENTRADAS)
    r = _correr(clon)
    assert r.returncode == 0, r.stderr
    _assert_b_y_c_en_orden(r.stdout)
    assert str(bitacora) in r.stdout


# (5) Sin bitácora en ningún lado: no imprime nada y no frena la sesión.
def test_sin_bitacora_no_imprime_nada_y_sale_cero(tmp_path):
    r = _correr(tmp_path)
    assert r.returncode == 0, r.stderr
    assert r.stdout == ""


# (6) Una sola entrada: la imprime.
def test_con_una_sola_entrada_la_imprime(tmp_path):
    _escribir_bitacora(tmp_path / "docs", ENCABEZADO_BITACORA + ENTRADA_A)
    r = _correr(tmp_path)
    assert r.returncode == 0, r.stderr
    assert "## 2026-01-01 — A" in r.stdout and "cuerpo-A" in r.stdout
    assert "Introducción del diario" not in r.stdout


# (7) Entradas largas: recorta con aviso y queda bajo el tope de 10.000 de Claude Code.
def test_entradas_largas_se_recortan_con_aviso(tmp_path):
    larga_b = "## 2026-01-02 — B\n\n" + ("b" * 6000) + "\n\n"
    larga_c = "## 2026-01-03 — C\n\n" + ("c" * 6000) + "\n"
    _escribir_bitacora(tmp_path / "docs", ENCABEZADO_BITACORA + ENTRADA_A + larga_b + larga_c)
    r = _correr(tmp_path)
    assert r.returncode == 0, r.stderr
    assert "recortado" in r.stdout
    assert len(r.stdout) < 10000
    # La penúltima entra entera; la última es la que se corta.
    assert "b" * 6000 in r.stdout
    assert "c" * 6000 not in r.stdout


# (8) Bitácora con CRLF (así está la real en Windows): corta bien y no arrastra \r.
def test_bitacora_con_crlf(tmp_path):
    _escribir_bitacora(tmp_path / "docs", TRES_ENTRADAS, eol="\r\n")
    r = _correr(tmp_path)
    assert r.returncode == 0, r.stderr
    _assert_b_y_c_en_orden(r.stdout)
    assert "\r" not in r.stdout


# (9) El encabezado dice el orden y dónde está lo pendiente.
def test_encabezado_dice_el_orden_y_la_ruta_del_estado(tmp_path):
    docs = tmp_path / "backend_preliquidacion" / "docs"
    bitacora = _escribir_bitacora(docs, TRES_ENTRADAS)
    r = _correr(tmp_path)
    assert r.returncode == 0, r.stderr
    encabezado = r.stdout.split("## ", 1)[0]
    assert "la más reciente al final" in encabezado
    assert str(bitacora) in encabezado
    assert str(docs / "estado.md") in encabezado
