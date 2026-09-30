import subprocess
import sys
import textwrap
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]


def test_stdout_queda_line_buffered_cuando_no_es_terminal():
    """
    Bajo systemd stdout es un pipe, no una terminal, y Python lo guarda en un
    buffer por bloques: el banner de arranque (único lugar con los nombres de
    tablas y columnas faltantes) no llega al journal hasta que el proceso
    termina. app.main debe dejar stdout con line_buffering al importarse.
    """
    script = textwrap.dedent("""
        import sys
        import app.main  # noqa: F401 — dispara la reconfiguración de stdout
        sys.stderr.write(f"line_buffering={sys.stdout.line_buffering}\\n")
    """)
    resultado = subprocess.run(
        [sys.executable, "-c", script],
        cwd=RAIZ,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        # el arranque en frío importa toda la app; bajo carga superaba 20 s
        timeout=60,
    )
    assert resultado.returncode == 0, (
        f"stdout: {resultado.stdout}\nstderr: {resultado.stderr}"
    )
    assert "line_buffering=True" in resultado.stderr, resultado.stderr
