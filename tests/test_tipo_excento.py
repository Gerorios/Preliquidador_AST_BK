"""Tipo de concepto EXCENTO (WS14): etiqueta pura agregada al enum
TipoConcepto. Grafía deliberada ('EXCENTO', no 'exento') — ver CONTEXT.md.
Ningún cálculo la distingue; solo verificamos que el enum y los schemas de
entrada la aceptan."""
from datetime import date

from app.models.models import TipoConcepto
from app.schemas.schemas import ConceptoAdicionalRequest, ConceptoUnifRequest


def test_tipo_concepto_excento_value():
    assert TipoConcepto.EXCENTO.value == "EXCENTO"


def test_concepto_unif_request_acepta_tipo_excento():
    obj = ConceptoUnifRequest(
        quincena=date(2026, 5, 1),
        tarea_nombre="PODA",
        tipo="EXCENTO",
    )
    assert obj.tipo == TipoConcepto.EXCENTO


def test_concepto_adicional_request_acepta_tipo_excento():
    obj = ConceptoAdicionalRequest(
        descripcion="Adicional exento",
        tipo="EXCENTO",
        importe="100.00",
    )
    assert obj.tipo == TipoConcepto.EXCENTO
