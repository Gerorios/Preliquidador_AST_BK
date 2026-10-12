"""Reglas puras del Comprobante: normalización, clave de identidad, importe y
total con signo (plan de la E2, sección 3.1, reglas 1, 3 y 5).

Sin base ni sesión: las usan el alta y la edición a mano (comprobantes_service)
y la migración del histórico (historico.py), y las dos tienen que llegar a la
misma clave y al mismo importe para el mismo dato.
"""
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

FACTURA = "factura"
NOTA_CREDITO = "nota_credito"
TIPOS = (FACTURA, NOTA_CREDITO)

CERO = Decimal("0.00")
CENTAVO = Decimal("0.01")

# Separa las partes de clave_identidad. El número es la última parte y no la
# puede contener, así que la clave se lee sin ambigüedad aunque la Empresa sí.
SEPARADOR = "|"


class NumeroInvalido(ValueError):
    """El número del Comprobante quedó vacío o trae la barra separadora."""


def normalizar_numero(numero) -> str:
    """Recorta los extremos, colapsa los espacios y pasa a mayúsculas.

    No toca los ceros ni el formato: el número es texto libre, copiado tal cual
    figura en el PDF (pregunta 11). Normalizar es lo que hace que " a 12" y
    "A 12" sean el mismo Comprobante para el 409 de repetido.

    Rechaza el vacío (sólo la migración crea Comprobantes sin número, y no pasa
    por acá) y la barra, que separa las partes de clave_identidad."""
    normalizado = " ".join((numero or "").split()).upper()
    if not normalizado:
        raise NumeroInvalido("El número del comprobante no puede quedar vacío.")
    if SEPARADOR in normalizado:
        raise NumeroInvalido(
            f"El número del comprobante no puede llevar «{SEPARADOR}»."
        )
    return normalizado


def normalizar_empresa(empresa) -> str:
    """Recorte y mayúsculas (regla 1). Que sea obligatoria lo controla el alta."""
    return (empresa or "").strip().upper()


def clave_identidad(
    *,
    historico: bool,
    numero=None,
    empresa=None,
    tipo=None,
    cliente_id=None,
    fecha_a_facturar: date | None = None,
) -> str:
    """La clave única del Comprobante, que calcula el servicio y hace cumplir
    la base (UNIQUE de `clave_identidad`).

    Hace falta porque el histórico no tiene Empresa, MySQL acepta varios NULL
    en un UNIQUE y en la planilla el mismo número aparece para dos Clientes.
    Tres formas:
    - cargado a mano: `E|<empresa>|<tipo>|<numero>`, con el tipo tal cual
      (`factura` o `nota_credito`). El número es único por Empresa emisora y
      tipo, sin importar el Cliente: Facturas y Notas de crédito numeran
      aparte (lo confirmó el usuario el 2026-10-12);
    - histórico con número: `H|<cliente_id>|<numero>`. Sin tipo: los
      históricos son siempre Facturas;
    - histórico sin número: `S|<cliente_id>|<fecha a facturar AAAA-MM-DD>`,
      uno por Cliente y FECHA A FACTURAR (pregunta 4).

    Normaliza adentro, así ningún llamador puede armar dos claves distintas
    para el mismo Comprobante."""
    if not historico:
        empresa_normalizada = normalizar_empresa(empresa)
        if not empresa_normalizada:
            raise ValueError("Un comprobante cargado a mano necesita Empresa.")
        if tipo not in TIPOS:
            raise ValueError(f"Tipo de comprobante desconocido: {tipo!r}.")
        return SEPARADOR.join(
            ("E", empresa_normalizada, tipo, normalizar_numero(numero)))

    if cliente_id is None:
        raise ValueError("Un comprobante histórico necesita Cliente.")
    if numero is not None:
        return SEPARADOR.join(("H", str(cliente_id), normalizar_numero(numero)))
    if fecha_a_facturar is None:
        raise ValueError(
            "Un histórico sin número necesita la fecha a facturar."
        )
    return SEPARADOR.join(("S", str(cliente_id), fecha_a_facturar.isoformat()))


def _decimal(valor) -> Decimal:
    # Por str para que un float no arrastre su error binario (0.005 no existe
    # exacto en binario).
    return valor if isinstance(valor, Decimal) else Decimal(str(valor))


def calcular_importe(cantidad, precio_unitario) -> Decimal:
    """round(cantidad × precio, 2) con ROUND_HALF_UP (regla 3).

    Lo calcula siempre el backend. El front repite la cuenta en centavos con
    BigInt para mostrarla mientras se tipea (FA1, mismos casos fijos): con el
    redondeo bancario de Python (HALF_EVEN) 0.125 daría 0.12 acá y 0.13 en la
    pantalla."""
    return (_decimal(cantidad) * _decimal(precio_unitario)).quantize(
        CENTAVO, rounding=ROUND_HALF_UP,
    )


def total_firmado(tipo: str, importes) -> Decimal:
    """La suma de los importes de las Líneas, negativa en una Nota de crédito.

    Los importes se guardan siempre >= 0 y el signo lo da el tipo, como en
    Terceros (regla 5)."""
    if tipo not in TIPOS:
        raise ValueError(f"Tipo de comprobante desconocido: {tipo!r}.")
    total = sum((_decimal(i) for i in importes), CERO)
    # CERO - total y no -total: con 0.00, -total daría "-0.00".
    return CERO - total if tipo == NOTA_CREDITO else total
