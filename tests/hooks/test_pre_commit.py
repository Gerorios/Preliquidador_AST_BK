"""Hook git `scripts/hooks/pre-commit`.

Frena los commits en `main`: todo cambio va por rama y PR. La única excepción
es un commit que sólo toque `docs/BITACORA.md` y/o `docs/estado.md`, que van
directo a `main` (ver "Bitácora y estado" en AGENTS.md). Si la excepción se
abre de más, cualquier archivo se cuela a `main` sin PR; si se cierra de más,
la bitácora y el estado no se pueden anotar.

Estos tests arman un repo de juguete en `tmp_path`, le copian el hook a
`.git/hooks/pre-commit` y prueban commits reales. Nunca tocan los repos de
verdad: el repo de juguete tiene su propia config local y la global/sistema de
la máquina se aísla por variables de entorno.
"""
import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[2] / "scripts" / "hooks" / "pre-commit"
GIT = shutil.which("git")

pytestmark = pytest.mark.skipif(GIT is None, reason="git no está instalado")


def _entorno(tmp_path: Path) -> dict:
    env = dict(os.environ)
    # Si los tests corren dentro de un hook o de otra herramienta de git, estas
    # variables apuntarían al repo real: se sacan todas.
    for clave in list(env):
        if clave.startswith("GIT_"):
            del env[clave]
    # Config global y de sistema aisladas: un core.hooksPath global haría que
    # git ignore el hook copiado a .git/hooks.
    global_vacia = tmp_path / "gitconfig-global"
    global_vacia.touch()
    env["GIT_CONFIG_GLOBAL"] = str(global_vacia)
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    return env


def _git(repo: Path, env: dict, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    resultado = subprocess.run(
        [GIT, *args], cwd=repo, env=env, capture_output=True, timeout=60
    )
    resultado.stdout = resultado.stdout.decode("utf-8", errors="replace")
    resultado.stderr = resultado.stderr.decode("utf-8", errors="replace")
    if check:
        assert resultado.returncode == 0, (args, resultado.stdout, resultado.stderr)
    return resultado


@pytest.fixture
def repo(tmp_path):
    """Repo de juguete en `main` con un commit inicial y el hook instalado."""
    raiz = tmp_path / "repo"
    raiz.mkdir()
    env = _entorno(tmp_path)

    if _git(raiz, env, "init", "-b", "main", check=False).returncode != 0:
        # git viejo sin `init -b`.
        _git(raiz, env, "init")
        _git(raiz, env, "symbolic-ref", "HEAD", "refs/heads/main")
    _git(raiz, env, "config", "user.name", "Test")
    _git(raiz, env, "config", "user.email", "test@example.invalid")
    _git(raiz, env, "config", "commit.gpgsign", "false")
    _git(raiz, env, "config", "core.autocrlf", "false")

    (raiz / "docs").mkdir()
    (raiz / "docs" / "BITACORA.md").write_text("# Bitácora\n", encoding="utf-8")
    (raiz / "docs" / "estado.md").write_text("# Estado\n", encoding="utf-8")
    (raiz / "README.md").write_text("# Juguete\n", encoding="utf-8")
    _git(raiz, env, "add", "-A")
    # Semilla: el único commit que saltea el hook (todavía no está instalado,
    # pero el --no-verify deja explícito que no es parte de lo que se prueba).
    _git(raiz, env, "commit", "--no-verify", "-m", "semilla")

    destino = raiz / ".git" / "hooks" / "pre-commit"
    destino.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(HOOK, destino)
    destino.chmod(destino.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return raiz, env


def _tocar(raiz: Path, *rutas: str):
    for ruta in rutas:
        archivo = raiz / ruta
        with open(archivo, "a", encoding="utf-8", newline="\n") as f:
            f.write("cambio\n")


def _commitear(raiz: Path, env: dict, *rutas: str) -> subprocess.CompletedProcess:
    _tocar(raiz, *rutas)
    _git(raiz, env, "add", *rutas)
    return _git(raiz, env, "commit", "-m", "prueba", check=False)


# (1) En main, sólo la bitácora: pasa (la excepción de siempre).
def test_main_solo_bitacora_pasa(repo):
    raiz, env = repo
    r = _commitear(raiz, env, "docs/BITACORA.md")
    assert r.returncode == 0, r.stderr


# (2) En main, sólo el estado: pasa (excepción ampliada).
def test_main_solo_estado_pasa(repo):
    raiz, env = repo
    r = _commitear(raiz, env, "docs/estado.md")
    assert r.returncode == 0, r.stderr


# (3) En main, bitácora y estado juntos: pasa (así los commitea /bitacora).
def test_main_bitacora_y_estado_juntos_pasa(repo):
    raiz, env = repo
    r = _commitear(raiz, env, "docs/BITACORA.md", "docs/estado.md")
    assert r.returncode == 0, r.stderr


# (4) En main, estado mezclado con otro archivo: frena.
def test_main_estado_con_otro_archivo_frena(repo):
    raiz, env = repo
    r = _commitear(raiz, env, "docs/estado.md", "README.md")
    assert r.returncode == 1
    assert "Commit frenado" in r.stderr


# (5) En main, cualquier otro archivo solo: frena.
def test_main_otro_archivo_frena(repo):
    raiz, env = repo
    r = _commitear(raiz, env, "README.md")
    assert r.returncode == 1
    assert "Commit frenado" in r.stderr


# (6) En una rama, cualquier archivo: pasa.
def test_en_rama_cualquier_archivo_pasa(repo):
    raiz, env = repo
    _git(raiz, env, "checkout", "-b", "docs/prueba")
    r = _commitear(raiz, env, "README.md")
    assert r.returncode == 0, r.stderr


# (7) En main, borrar un archivo de la excepción pasa, pero renombrar otro
# archivo encima de ese nombre frena: si no, un `git mv` borra código sin PR
# (git lista sólo el nombre nuevo del renombre).
@pytest.mark.parametrize("excepcion", ["docs/estado.md", "docs/BITACORA.md"])
def test_main_renombre_sobre_excepcion_frena(repo, excepcion):
    raiz, env = repo
    _git(raiz, env, "rm", "-q", excepcion)
    r = _git(raiz, env, "commit", "-m", "borra", check=False)
    assert r.returncode == 0, r.stderr

    _git(raiz, env, "mv", "README.md", excepcion)
    r = _git(raiz, env, "commit", "-m", "renombra", check=False)
    assert r.returncode == 1, (r.stdout, r.stderr)
    assert "Commit frenado" in r.stderr
