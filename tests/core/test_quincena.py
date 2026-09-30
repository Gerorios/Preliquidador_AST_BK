"""Una quincena se identifica por su fecha de inicio: día 1 o día 16 (CONTEXT.md).
Cualquier otra fecha se rechaza en el borde, no se normaliza en silencio."""
from datetime import date

import pytest
from pydantic import BaseModel, ValidationError

from app.core.quincena import Quincena, validar_quincena


@pytest.mark.parametrize("dia", [1, 16])
def test_acepta_inicio_de_quincena(dia):
    d = date(2026, 9, dia)
    assert validar_quincena(d) == d


@pytest.mark.parametrize("dia", [2, 15, 17, 30])
def test_rechaza_cualquier_otro_dia(dia):
    with pytest.raises(ValueError) as exc:
        validar_quincena(date(2026, 9, dia))
    assert "1 o el 16" in str(exc.value)


def test_el_tipo_quincena_valida_dentro_de_un_esquema():
    class Req(BaseModel):
        quincena: Quincena

    assert Req(quincena="2026-09-16").quincena == date(2026, 9, 16)
    with pytest.raises(ValidationError) as exc:
        Req(quincena="2026-09-17")
    assert "1 o el 16" in str(exc.value)
