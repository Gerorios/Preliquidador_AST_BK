"""El asistente de ayuda arma su conocimiento con los documentos de `_DOCS`.
Si uno falta, `_system_prompt` lo saltea en silencio: estos tests evitan que un
movimiento de archivos deje al asistente sin glosario sin que nadie se entere."""
import pytest

from app.core.asistente import _BASE_DIR, _DOCS, _system_prompt


@pytest.mark.parametrize("nombre", _DOCS)
def test_cada_documento_existe_y_no_esta_vacio(nombre):
    ruta = _BASE_DIR / nombre
    assert ruta.is_file(), f"{nombre} no existe: el asistente lo saltearía"
    assert ruta.read_text(encoding="utf-8").strip()


def test_carga_el_glosario_del_nucleo_y_el_de_preliquidacion():
    assert "CONTEXT.md" in _DOCS
    assert "docs/modulos/preliquidacion/CONTEXT-preliquidacion.md" in _DOCS


@pytest.mark.parametrize("termino", ["**Tarjeta**", "**Reemplaza al común**"])
def test_el_prompt_incluye_terminos_de_los_dos_glosarios(termino):
    _system_prompt.cache_clear()
    assert termino in _system_prompt()
