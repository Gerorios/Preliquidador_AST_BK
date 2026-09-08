import subprocess
import sys
import textwrap


def test_prints_de_lifespan_no_crashean_con_stdout_no_utf8():
    """
    En este entorno (Windows, sin PYTHONIOENCODING/PYTHONUTF8 seteados), el
    stdout de Python por defecto usa el codepage de la consola (cp1252/850,
    no UTF-8). Los print() de app.main.lifespan usan caracteres como
    '─', '✓', '✗' que NO existen en cp1252: sin la reconfiguración a UTF-8
    que hace main.py al importarse, esto revienta con UnicodeEncodeError
    y tira abajo el arranque completo del servidor (bug real reproducido
    con uvicorn real, no solo con este test).
    """
    script = textwrap.dedent("""
        import app.main  # dispara la reconfiguración de stdout/stderr a UTF-8
        print("─" * 50)
        print("  Sistema de Preliquidación — La Asturiana SRL")
        print(f"  BD sueldos:  {'✓ OK'}")
        print(f"  BD externa:  {'✗ ERROR'}")
    """)
    resultado = subprocess.run(
        [sys.executable, "-c", script],
        cwd=".",
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert resultado.returncode == 0, (
        f"stdout: {resultado.stdout}\nstderr: {resultado.stderr}"
    )
    assert "UnicodeEncodeError" not in resultado.stderr
