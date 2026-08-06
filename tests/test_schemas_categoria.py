"""Validación de rango de 'categoria' (1..12, ADR-0008) en los schemas de
entrada que la reciben: ConceptoUnifRequest, ConceptoUnifUpdateRequest y
CategoriaOperarioRequest. None sigue siendo válido (sin categoría / borra
asignación)."""
from datetime import date

import pytest
from pydantic import ValidationError

from app.schemas.schemas import (
    CategoriaOperarioRequest,
    ConceptoUnifRequest,
    ConceptoUnifUpdateRequest,
)


@pytest.mark.parametrize("schema_cls, kwargs", [
    (CategoriaOperarioRequest, {"cuil": "20111111119"}),
    (ConceptoUnifRequest, {"quincena": date(2026, 5, 1), "tarea_nombre": "PODA"}),
    (ConceptoUnifUpdateRequest, {}),
])
class TestCategoriaRango:
    def test_categoria_12_se_acepta(self, schema_cls, kwargs):
        obj = schema_cls(categoria=12, **kwargs)
        assert obj.categoria == 12

    def test_categoria_1_se_acepta(self, schema_cls, kwargs):
        obj = schema_cls(categoria=1, **kwargs)
        assert obj.categoria == 1

    def test_categoria_0_se_rechaza(self, schema_cls, kwargs):
        with pytest.raises(ValidationError):
            schema_cls(categoria=0, **kwargs)

    def test_categoria_13_se_rechaza(self, schema_cls, kwargs):
        with pytest.raises(ValidationError):
            schema_cls(categoria=13, **kwargs)

    def test_categoria_none_se_acepta(self, schema_cls, kwargs):
        obj = schema_cls(categoria=None, **kwargs)
        assert obj.categoria is None
