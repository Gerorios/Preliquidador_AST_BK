"""Script `scripts/verificar_agents_comun.sh` corrido desde el hook `pre-commit`.

El script compara el bloque común de AGENTS.md con el del repo hermano, que
busca al lado del checkout principal por su origin. Dentro de un hook git
exporta `GIT_DIR` cuando el commit se hace desde un worktree (desde el
checkout principal sólo pasa un `GIT_INDEX_FILE` relativo): si el script no
las saca para mirar otras carpetas, lee el origin del repo propio en todas,
nunca encuentra al hermano y el aviso del hook no compara nada.

Estos tests arman dos repos de juguete al lado (origins del backend y del
front) en `tmp_path`. Nunca tocan los repos de verdad.
"""
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

from tests.hooks.test_pre_commit import GIT, _entorno, _git

RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "scripts" / "verificar_agents_comun.sh"
HOOK = RAIZ / "scripts" / "hooks" / "pre-commit"
SH = shutil.which("sh")

pytestmark = pytest.mark.skipif(
    GIT is None or SH is None, reason="hacen falta git y sh"
)

BLOQUE = "<!-- comun:inicio -->\nregla común\n<!-- comun:fin -->\n"


def _clon(clones: Path, nombre: str, origin: str, env: dict, script: bool = False) -> Path:
    raiz = clones / nombre
    raiz.mkdir()
    if _git(raiz, env, "init", "-b", "main", check=False).returncode != 0:
        _git(raiz, env, "init")
        _git(raiz, env, "symbolic-ref", "HEAD", "refs/heads/main")
    _git(raiz, env, "config", "user.name", "Test")
    _git(raiz, env, "config", "user.email", "test@example.invalid")
    _git(raiz, env, "config", "commit.gpgsign", "false")
    _git(raiz, env, "config", "core.autocrlf", "false")
    _git(raiz, env, "remote", "add", "origin", origin)
    (raiz / "AGENTS.md").write_text(f"# {nombre}\n\n{BLOQUE}", encoding="utf-8")
    if script:
        # Commiteado, para que el worktree del caso (2) también lo tenga.
        (raiz / "scripts").mkdir()
        shutil.copyfile(SCRIPT, raiz / "scripts" / "verificar_agents_comun.sh")
    _git(raiz, env, "add", "-A")
    _git(raiz, env, "commit", "--no-verify", "-m", "semilla")
    return raiz


@pytest.fixture
def clones(tmp_path):
    """Backend y front de juguete, clonados uno al lado del otro."""
    env = _entorno(tmp_path)
    carpeta = tmp_path / "clones"
    carpeta.mkdir()
    bk = _clon(
        carpeta, "bk", "https://github.com/Gerorios/Preliquidador_AST_BK.git", env, script=True
    )
    ft = _clon(carpeta, "ft", "git@github.com:Gerorios/Preliquidador_AST_FT.git", env)
    return bk, ft, env


# (1) Con GIT_DIR exportado, como dentro de un hook: encuentra al hermano y
# compara (bloques iguales, exit 0) en vez de fallar con exit 2.
def test_con_git_dir_exportado_encuentra_al_hermano(clones):
    bk, _, env = clones
    git_dir = _git(bk, env, "rev-parse", "--absolute-git-dir").stdout.strip()
    r = subprocess.run(
        [SH, "scripts/verificar_agents_comun.sh"],
        cwd=bk, env={**env, "GIT_DIR": git_dir}, capture_output=True, timeout=60,
    )
    assert r.returncode == 0, r.stderr.decode("utf-8", errors="replace")


# (2) Con el pre-commit real instalado, commiteando desde un worktree (como se
# trabaja en este proyecto): un cambio en el bloque común avisa que difiere del
# hermano (y no frena, porque está en una rama).
def test_pre_commit_compara_con_el_hermano(clones):
    bk, _, env = clones
    destino = bk / ".git" / "hooks" / "pre-commit"
    destino.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(HOOK, destino)
    destino.chmod(destino.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    wt = bk / ".claude" / "worktrees" / "prueba"
    _git(bk, env, "worktree", "add", "-b", "docs/prueba", str(wt))
    agents = wt / "AGENTS.md"
    agents.write_text(
        agents.read_text(encoding="utf-8").replace("regla común", "regla cambiada"),
        encoding="utf-8",
    )
    _git(wt, env, "add", "AGENTS.md")
    r = _git(wt, env, "commit", "-m", "prueba", check=False)
    assert r.returncode == 0, r.stderr
    assert "difiere del repo hermano" in r.stderr, r.stderr
