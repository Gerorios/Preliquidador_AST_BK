"""Migración del histórico de la planilla de facturación (plan de la E2,
sección 3.1, "Migración del histórico").

Toda la lógica pura vive acá, sin base de campo ni sesión, para probarla con
datos inventados; el script `scripts/migrar_historico_facturacion.py` es una
capa fina encima. Esta parte lee la planilla exportada: el CSV, los números
es-AR y las fechas. Lo que no se puede leer se marca ilegible y no se adivina:
quien clasifica omite el Comprobante entero y lo lista.
"""
import csv
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

# Los encabezados que se usan, recortados y en mayúsculas. QUINCENA A FACTURAR,
# GRUPO TAREA y Nosotros se ignoran, así que no se exigen.
ENCABEZADOS = (
    "FECHA A FACTURAR",
    "CLIENTE",
    "FINCA",
    "TAREA",
    "UM",
    "CANT FACTURA",
    "PRECIO UNIT",
    "FACTURA",
    "FACT N°",
    "FECHA FAC",
)

# Con coma: la coma es el decimal y los puntos, de miles en grupos de 3.
_CON_COMA = re.compile(r"^(?:\d+|\d{1,3}(?:\.\d{3})+),(\d+)$")
# Sin coma: sólo dígitos, o puntos de miles en grupos de 3. Un punto en otro
# lugar ("12.5") no se interpreta: queda ilegible.
_SIN_COMA = re.compile(r"^(?:\d+|\d{1,3}(?:\.\d{3})+)$")
_FECHA = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4}|\d{2})$")


class ValorIlegible(ValueError):
    """Una celda con algo que no es un número o una fecha válida."""


class PlanillaInvalida(ValueError):
    """La planilla no trae los encabezados que se usan."""

    def __init__(self, faltantes: list[str]):
        self.faltantes = faltantes
        super().__init__(
            "A la planilla le faltan estos encabezados: " + ", ".join(faltantes) + "."
        )


@dataclass(frozen=True)
class FilaPlanilla:
    """Una fila de la planilla, con las celdas tal cual vienen. `fila` es el
    número de fila del CSV (el encabezado es la 1), para poder listarla."""

    fila: int
    fecha_a_facturar: str
    cliente: str
    finca: str
    tarea: str
    um: str
    cantidad: str
    precio: str
    importe: str
    numero: str
    fecha_factura: str


# Qué encabezado va a cada campo de FilaPlanilla.
_CAMPOS = {
    "fecha_a_facturar": "FECHA A FACTURAR",
    "cliente": "CLIENTE",
    "finca": "FINCA",
    "tarea": "TAREA",
    "um": "UM",
    "cantidad": "CANT FACTURA",
    "precio": "PRECIO UNIT",
    "importe": "FACTURA",
    "numero": "FACT N°",
    "fecha_factura": "FECHA FAC",
}


def leer_numero_ar(texto, decimales: int) -> Decimal | None:
    """Un número en formato es-AR ("1.234,56", "$ 1.234,56", "1234").

    Vacío da None: qué significa un vacío lo decide cada columna. Lo que no es
    un número ("-", "#VALUE!") o trae más decimales que `decimales`, los de su
    columna, da ValorIlegible. El negativo se lee; omitirlo es de quien
    clasifica (pregunta 7)."""
    original = (texto or "").strip()
    if not original:
        return None
    # Sin "$" ni espacios: "$ -1.234,56" y "-$ 1.234,56" quedan "-1.234,56".
    limpio = "".join(original.replace("$", "").split())
    negativo = limpio.startswith("-")
    if negativo:
        limpio = limpio[1:]

    con_coma = _CON_COMA.match(limpio)
    if con_coma:
        if len(con_coma.group(1)) > decimales:
            raise ValorIlegible(f"«{original}» tiene más de {decimales} decimales.")
        valor = Decimal(limpio.replace(".", "").replace(",", "."))
    elif _SIN_COMA.match(limpio):
        valor = Decimal(limpio.replace(".", ""))
    else:
        raise ValorIlegible(f"«{original}» no es un número.")
    return -valor if negativo else valor


def leer_fecha(texto) -> date | None:
    """Una fecha `d/m/aaaa` o `d/m/aa` (el año de dos cifras es del 2000).

    Vacía da None, porque FECHA FAC vacía es un caso real; cualquier otra cosa
    que no sea una fecha válida da ValorIlegible."""
    original = (texto or "").strip()
    if not original:
        return None
    partes = _FECHA.match(original)
    if not partes:
        raise ValorIlegible(f"«{original}» no es una fecha d/m/aaaa.")
    dia, mes, anio = (int(p) for p in partes.groups())
    if len(partes.group(3)) == 2:
        anio += 2000
    try:
        return date(anio, mes, dia)
    except ValueError:
        raise ValorIlegible(f"«{original}» no es una fecha válida.") from None


def leer_planilla(ruta) -> list[FilaPlanilla]:
    """Lee el CSV exportado: UTF-8 con o sin BOM, CRLF o LF, separado por `,` o
    `;` según cuál aparezca más en el encabezado, con o sin comillas.

    Los encabezados se buscan por nombre, recortados y en mayúsculas, así el
    orden de las columnas no importa. Si falta alguno de ENCABEZADOS, da
    PlanillaInvalida con todos los que faltan, en el orden de ENCABEZADOS."""
    with Path(ruta).open(encoding="utf-8-sig", newline="") as archivo:
        primera = archivo.readline()
        separador = ";" if primera.count(";") > primera.count(",") else ","
        archivo.seek(0)
        lector = csv.reader(archivo, delimiter=separador)

        encabezado = next(lector, [])
        posicion: dict[str, int] = {}
        for indice, nombre in enumerate(encabezado):
            posicion.setdefault(nombre.strip().upper(), indice)
        faltantes = [e for e in ENCABEZADOS if e not in posicion]
        if faltantes:
            raise PlanillaInvalida(faltantes)

        filas = []
        for numero_fila, celdas in enumerate(lector, start=2):
            if not celdas:
                continue
            filas.append(FilaPlanilla(
                fila=numero_fila,
                **{
                    campo: celdas[posicion[nombre]] if posicion[nombre] < len(celdas) else ""
                    for campo, nombre in _CAMPOS.items()
                },
            ))
        return filas
