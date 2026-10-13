"""Migración del histórico de la planilla de facturación (plan de la E2,
sección 3.1, "Migración del histórico").

Toda la lógica vive acá, sin base de campo, para probarla con datos
inventados y SQLite; el script `scripts/migrar_historico_facturacion.py` es
una capa fina encima. Tiene cuatro partes:
- la lectura de la planilla exportada: el CSV, los números es-AR, las fechas,
  la UM y el número del Comprobante. Lo que no se puede leer se marca ilegible
  y no se adivina;
- la clasificación (`clasificar`): resuelve Cliente, tarea y finca contra los
  maestros que recibe y agrupa las filas en Comprobantes. Una Línea mala omite
  su Comprobante entero con su motivo, y queda listado;
- la aplicación (`aplicar`): lleva los grupos a la base propia sin duplicar,
  por `clave_identidad`. No confirma la transacción: lo decide el script;
- la conciliación (`conciliar` y `codigo_de_salida`): planilla, omitido y
  base por Cliente y mes, que es como se acepta la migración. No imprime
  nada: la consola y el informe son del script.
"""
import csv
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from sqlalchemy.orm import Session

from app.modulos.facturacion.models import Comprobante, LineaComprobante
from app.modulos.facturacion.services.comprobantes_service import (
    CANTIDAD, IMPORTE, LARGO_NUMERO, PRECIO,
)
from app.modulos.facturacion.services.reglas_comprobante import (
    FACTURA, NumeroInvalido, clave_identidad, normalizar_numero,
)
from app.modulos.facturacion.unidades import normalizar_texto, traducir_unidad

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
    """Una celda con algo que no es un número o una fecha válida, o un FACT N°
    con la barra que separa las partes de clave_identidad."""


class NumeroDemasiadoLargo(ValueError):
    """Un FACT N° que, normalizado, no entra en la columna `numero`. No es
    ilegible: se omite su grupo con su propio motivo, para que se corrija en la
    planilla."""


# Lo que en FACT N° significa "sin número" (pregunta 4), además del vacío.
SIN_NUMERO = "-"


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


def leer_unidad(texto) -> str | None:
    """La clave de unidad de una UM, comparada sin acentos, en mayúsculas y con
    los espacios colapsados (la tabla vive en `unidades.UNIDAD_DE_PLANILLA`).

    NO FACTURABLE, vacía o cualquier otra dan None: su Comprobante se omite y
    se lista (pregunta 2). No se usa la Unidad sugerida, porque adivina."""
    clave, _no_facturable = traducir_unidad(texto)
    return clave


def leer_numero_comprobante(texto) -> str | None:
    """El FACT N° normalizado como el de un Comprobante cargado a mano (regla 1),
    para que el mismo número dé la misma clave venga de donde venga.

    Vacío o "-" dan None: la fila va a un Comprobante sin número (pregunta 4).
    Un compuesto ("10 - 11", "F.10 - NC 11") o cualquier otro texto se migra
    tal cual (pregunta 3). La barra da ValorIlegible, porque separa las partes
    de clave_identidad; más de LARGO_NUMERO caracteres, ya normalizado, da
    NumeroDemasiadoLargo."""
    recortado = (texto or "").strip()
    if not recortado or recortado == SIN_NUMERO:
        return None
    try:
        numero = normalizar_numero(recortado)
    except NumeroInvalido as error:
        raise ValorIlegible(str(error)) from None
    if len(numero) > LARGO_NUMERO:
        raise NumeroDemasiadoLargo(
            f"«{numero}» tiene más de {LARGO_NUMERO} caracteres."
        )
    return numero


# ─── Clasificación y agrupado ───────────────────────────────────────────────

# Un grupo sin número con FECHA A FACTURAR hasta este día cuenta como
# facturado (se facturó y no se anotó el número); uno posterior queda
# pendiente_de_facturar, por las dudas. Lo decidió el usuario el 2026-10-12.
SIN_NUMERO_FACTURADO_HASTA = date(2026, 7, 31)

# Motivos por los que se omite un Comprobante. Son los que lista el script y
# los que abre la conciliación.
CLIENTE_NO_ENCONTRADO = "cliente_no_encontrado"
CLIENTE_AMBIGUO = "cliente_ambiguo"
NUMERO_ILEGIBLE = "numero_ilegible"
NUMERO_DEMASIADO_LARGO = "numero_demasiado_largo"
SIN_NUMERO_SIN_FECHA = "sin_numero_sin_fecha_a_facturar"
FECHA_A_FACTURAR_VACIA = "fecha_a_facturar_vacia"
FECHA_A_FACTURAR_ILEGIBLE = "fecha_a_facturar_ilegible"
ANTERIOR_A_DESDE = "anterior_a_desde"
TAREA_NO_ENCONTRADA = "tarea_no_encontrada"
TAREA_AMBIGUA = "tarea_ambigua"
UM_NO_TRADUCIBLE = "um_no_traducible"
CANTIDAD_VACIA = "cantidad_vacia"
CANTIDAD_ILEGIBLE = "cantidad_ilegible"
PRECIO_VACIO = "precio_vacio"
PRECIO_ILEGIBLE = "precio_ilegible"
IMPORTE_VACIO = "importe_vacio"
IMPORTE_ILEGIBLE = "importe_ilegible"
VALOR_NEGATIVO = "valor_negativo"
FECHA_FACTURA_ILEGIBLE = "fecha_factura_ilegible"
FECHA_FACTURA_EN_CONFLICTO = "fecha_factura_en_conflicto"

# Avisos: no omiten nada, la Línea queda sin finca.
FINCA_NO_ENCONTRADA = "finca_no_encontrada"
FINCA_AMBIGUA = "finca_ambigua"


@dataclass(frozen=True)
class Maestros:
    """Los maestros del campo, con la forma que devuelve la consulta externa
    de Facturación, para que el script los pase tal cual:
    - clientes: `clientes(incluir_baja=True)`, cada uno {id, nombre, activo};
    - tareas: `obtener_tareas(incluir_baja=True)`, cada una {tarea_id, nombre, ...};
    - fincas: `todas_las_fincas()`, cada una {id, nombre, cliente_id}.
    Clientes y tareas incluyen los dados de baja, porque el histórico los
    muestra."""

    clientes: list[dict]
    tareas: list[dict]
    fincas: list[dict]


@dataclass(frozen=True)
class LineaHistorica:
    """Una Línea lista para guardar. Los nombres son los del maestro; los
    valores, los de la planilla, sin recalcular el importe."""

    fila: int
    fecha: date
    tarea_id: int
    tarea_nombre: str
    unidad: str
    finca_id: int | None
    finca_nombre: str | None
    cantidad: Decimal
    precio_unitario: Decimal
    importe: Decimal


@dataclass
class GrupoHistorico:
    """Un Comprobante histórico (siempre Factura y sin Empresa).

    Con número, se agrupa por (Cliente, número) y `fecha_a_facturar` queda
    None. Sin número (`numero` None), por (Cliente, FECHA A FACTURAR), que va
    en `fecha_a_facturar`. `fecha` es la única FECHA FAC del grupo, o None."""

    cliente_id: int
    cliente_nombre: str
    numero: str | None
    fecha_a_facturar: date | None
    fecha: date | None
    pendiente_de_facturar: bool
    lineas: list[LineaHistorica]


@dataclass(frozen=True)
class Omitido:
    """Un Comprobante que no se migra: todas sus filas, en el orden del CSV,
    con el motivo y el valor de la primera Línea mala (`fila_mala`).

    `clave` es la `S|...` de un grupo sin número, cuando se puede calcular
    (Cliente resuelto y FECHA A FACTURAR legible): con ella, aplicar sabe que
    ese sin número todavía tiene filas en el CSV y no lo borra. En los demás,
    None."""

    motivo: str
    detalle: str
    fila_mala: int
    filas: list[FilaPlanilla]
    clave: str | None = None


@dataclass(frozen=True)
class Aviso:
    """Algo que se informa y no frena: hoy, una finca que no se encuentra."""

    fila: int
    motivo: str
    detalle: str


@dataclass
class Clasificacion:
    """El resultado de clasificar la planilla.

    `no_resueltos` cuenta las filas de cada Cliente o tarea que no se pudo
    resolver, por (motivo, nombre normalizado), en todas las filas: también en
    las de un Comprobante que se omitió por otro motivo."""

    grupos: list[GrupoHistorico] = field(default_factory=list)
    omitidos: list[Omitido] = field(default_factory=list)
    avisos: list[Aviso] = field(default_factory=list)
    no_resueltos: Counter = field(default_factory=Counter)


class _LineaMala(Exception):
    """Por qué una fila no puede ser Línea: el motivo y el valor que falló."""

    def __init__(self, motivo: str, detalle: str):
        super().__init__(motivo)
        self.motivo = motivo
        self.detalle = detalle


@dataclass
class _Analisis:
    """Lo que salió de una fila: su Línea, o el motivo por el que no sirve."""

    fila: FilaPlanilla
    linea: LineaHistorica | None = None
    fecha_factura: date | None = None
    avisos: list[Aviso] = field(default_factory=list)
    error: _LineaMala | None = None


def _nombre(entrada) -> str:
    return normalizar_texto(entrada["nombre"])


def _indice(entradas, clave=_nombre) -> dict:
    """Clave normalizada -> entradas con esa clave. Más de una es ambiguo."""
    indice: dict = {}
    for entrada in entradas:
        valor = clave(entrada)
        if valor:
            indice.setdefault(valor, []).append(entrada)
    return indice


def _resolver(indice, nombre, no_encontrado, ambiguo):
    """La única entrada con ese nombre, o _LineaMala. Por nombre exacto ya
    normalizado: no hay parecido de nombres (pregunta 14)."""
    encontradas = indice.get(nombre, [])
    if len(encontradas) == 1:
        return encontradas[0]
    raise _LineaMala(ambiguo if encontradas else no_encontrado, nombre)


def _cliente_unico(encontrados: list[dict]) -> dict | None:
    """El Cliente de un nombre: el único candidato, o, entre varios, el único
    activo (paso C7a: el maestro repite nombres con uno de baja). Con dos o más
    activos, o todos de baja, None: es ambiguo. Sólo para el Cliente."""
    if len(encontrados) == 1:
        return encontrados[0]
    activos = [c for c in encontrados if c.get("activo")]
    return activos[0] if len(activos) == 1 else None


def _resolver_cliente(indice, nombre) -> dict:
    encontrados = indice.get(nombre, [])
    cliente = _cliente_unico(encontrados)
    if cliente is not None:
        return cliente
    raise _LineaMala(CLIENTE_AMBIGUO if encontrados else CLIENTE_NO_ENCONTRADO, nombre)


def _leer_valor(texto, decimales, vacio, ilegible) -> Decimal:
    """Un valor obligatorio de la Línea: sus columnas no admiten NULL, y
    completar un vacío sería adivinar."""
    try:
        valor = leer_numero_ar(texto, decimales)
    except ValorIlegible:
        raise _LineaMala(ilegible, (texto or "").strip()) from None
    if valor is None:
        raise _LineaMala(vacio, "")
    return valor


def _redondear_cantidad(cantidad: Decimal) -> Decimal:
    """La cantidad con más decimales que su columna se redondea a esos, mitad
    hacia arriba: la planilla trae bins con 3 (paso C7b). Con los que entran,
    queda tal cual. El importe no se recalcula."""
    escala = Decimal(1).scaleb(-CANTIDAD[1])
    if cantidad.as_tuple().exponent >= -CANTIDAD[1]:
        return cantidad
    return cantidad.quantize(escala, rounding=ROUND_HALF_UP)


def _leer_fecha(texto, ilegible) -> date | None:
    try:
        return leer_fecha(texto)
    except ValorIlegible:
        raise _LineaMala(ilegible, (texto or "").strip()) from None


def _clave_de_grupo(fila: FilaPlanilla) -> tuple:
    """(Cliente, "N", número) o, sin número, (Cliente, "S", FECHA A FACTURAR).
    Se arma aunque algo no se pueda leer, así las filas malas caen juntas en
    su grupo y se omiten juntas. El Cliente va por nombre normalizado, que
    resuelve a un solo id."""
    cliente = normalizar_texto(fila.cliente)
    try:
        numero = leer_numero_comprobante(fila.numero)
    except (ValorIlegible, NumeroDemasiadoLargo):
        return cliente, "N", " ".join(fila.numero.split()).upper()
    if numero is not None:
        return cliente, "N", numero
    try:
        return cliente, "S", leer_fecha(fila.fecha_a_facturar)
    except ValorIlegible:
        return cliente, "S", fila.fecha_a_facturar.strip()


def _analizar(fila, indices, desde, no_resueltos) -> _Analisis:
    """Lee y resuelve una fila. Se queda con el primer problema, en este orden:
    Cliente, número, FECHA A FACTURAR (y `desde`), tarea, UM, cantidad,
    precio, importe, negativos y FECHA FAC. Los nombres no resueltos se
    cuentan siempre, aunque la fila ya tenga otro problema."""
    clientes, tareas, fincas = indices
    analisis = _Analisis(fila=fila)
    cliente = tarea = tarea_mala = None
    try:
        cliente = _resolver_cliente(clientes, normalizar_texto(fila.cliente))
    except _LineaMala as error:
        no_resueltos[(error.motivo, error.detalle)] += 1
        analisis.error = error
    try:
        tarea = _resolver(tareas, normalizar_texto(fila.tarea),
                          TAREA_NO_ENCONTRADA, TAREA_AMBIGUA)
    except _LineaMala as error:
        no_resueltos[(error.motivo, error.detalle)] += 1
        tarea_mala = error
    if analisis.error:
        return analisis

    try:
        try:
            numero = leer_numero_comprobante(fila.numero)
        except ValorIlegible:
            raise _LineaMala(NUMERO_ILEGIBLE, fila.numero.strip()) from None
        except NumeroDemasiadoLargo:
            raise _LineaMala(NUMERO_DEMASIADO_LARGO, fila.numero.strip()) from None

        fecha = _leer_fecha(fila.fecha_a_facturar, FECHA_A_FACTURAR_ILEGIBLE)
        if fecha is None:
            # La fecha de la Línea no admite NULL. Sin número, además, es la
            # que agrupa (pregunta 4).
            raise _LineaMala(
                SIN_NUMERO_SIN_FECHA if numero is None else FECHA_A_FACTURAR_VACIA, "")
        if fecha < desde:
            raise _LineaMala(ANTERIOR_A_DESDE, fecha.isoformat())

        if tarea_mala:
            raise tarea_mala
        unidad = leer_unidad(fila.um)
        if unidad is None:
            raise _LineaMala(UM_NO_TRADUCIBLE, fila.um.strip())

        # La cantidad se lee con todos sus decimales y se redondea más abajo
        # (paso C7b); precio e importe con decimales de más son ilegibles. El
        # largo del texto es una cota de cuántos decimales puede traer.
        cantidad = _leer_valor(fila.cantidad, len(fila.cantidad or ""),
                               CANTIDAD_VACIA, CANTIDAD_ILEGIBLE)
        precio = _leer_valor(fila.precio, PRECIO[1], PRECIO_VACIO, PRECIO_ILEGIBLE)
        importe = _leer_valor(fila.importe, IMPORTE[1], IMPORTE_VACIO, IMPORTE_ILEGIBLE)
        # Todo histórico entra como Factura: un negativo sería una Nota de
        # crédito que la planilla no distingue (pregunta 7). Va antes de
        # redondear, para que un negativo chico no pase como 0.
        for valor, texto in ((cantidad, fila.cantidad), (precio, fila.precio),
                             (importe, fila.importe)):
            if valor < 0:
                raise _LineaMala(VALOR_NEGATIVO, texto.strip())
        cantidad = _redondear_cantidad(cantidad)

        # En FECHA FAC, "-" es el vacío que muestra la planilla: el Comprobante
        # queda sin fecha (paso C7a). En FECHA A FACTURAR sigue ilegible.
        fecha_factura = "" if (fila.fecha_factura or "").strip() == "-" else fila.fecha_factura
        analisis.fecha_factura = _leer_fecha(fecha_factura, FECHA_FACTURA_ILEGIBLE)
    except _LineaMala as error:
        analisis.error = error
        return analisis

    finca_id = finca_nombre = None
    nombre_finca = normalizar_texto(fila.finca)
    if nombre_finca:
        encontradas = fincas.get((cliente["id"], nombre_finca), [])
        if len(encontradas) == 1:
            finca_id, finca_nombre = encontradas[0]["id"], encontradas[0]["nombre"]
        else:
            analisis.avisos.append(Aviso(
                fila=fila.fila,
                motivo=FINCA_AMBIGUA if encontradas else FINCA_NO_ENCONTRADA,
                detalle=fila.finca.strip(),
            ))

    analisis.linea = LineaHistorica(
        fila=fila.fila, fecha=fecha, tarea_id=tarea["tarea_id"],
        tarea_nombre=tarea["nombre"], unidad=unidad, finca_id=finca_id,
        finca_nombre=finca_nombre, cantidad=cantidad, precio_unitario=precio,
        importe=importe,
    )
    return analisis


def _clave_sin_numero(clave_grupo: tuple, clientes: dict) -> str | None:
    """La `S|...` de un grupo sin número omitido, si el Cliente se resuelve a
    uno solo (con la misma regla que las Líneas) y la FECHA A FACTURAR es una
    fecha; si no, None."""
    cliente, tipo, valor = clave_grupo
    encontrado = _cliente_unico(clientes.get(cliente, []))
    if tipo != "S" or not isinstance(valor, date) or encontrado is None:
        return None
    return clave_identidad(historico=True, cliente_id=encontrado["id"],
                           fecha_a_facturar=valor)


def _fincas_del_cliente(finca) -> tuple:
    return finca["cliente_id"], normalizar_texto(finca["nombre"])


def clasificar(filas: list[FilaPlanilla], maestros: Maestros, desde: date) -> Clasificacion:
    """Agrupa las filas en Comprobantes históricos, en el orden del CSV.

    - Con número, por (Cliente, número); sin número (vacío o "-"), por
      (Cliente, FECHA A FACTURAR), y queda pendiente_de_facturar si esa fecha
      es posterior a SIN_NUMERO_FACTURADO_HASTA.
    - Todo o nada: la primera Línea mala omite su Comprobante entero, con su
      motivo. También lo omiten una Línea anterior a `desde` y dos FECHA FAC
      distintas en el grupo.
    - Una finca que no se encuentra entre las del Cliente deja la Línea sin
      finca y da un aviso; los avisos son sólo de los Comprobantes que se
      migran."""
    indices = (
        _indice(maestros.clientes),
        _indice(maestros.tareas),
        _indice(maestros.fincas, clave=_fincas_del_cliente),
    )
    resultado = Clasificacion()
    por_grupo: dict[tuple, list[_Analisis]] = {}
    for fila in filas:
        analisis = _analizar(fila, indices, desde, resultado.no_resueltos)
        por_grupo.setdefault(_clave_de_grupo(fila), []).append(analisis)

    for clave_grupo, analizadas in por_grupo.items():
        filas_del_grupo = [a.fila for a in analizadas]
        mala = next((a for a in analizadas if a.error), None)
        if mala:
            resultado.omitidos.append(Omitido(
                motivo=mala.error.motivo, detalle=mala.error.detalle,
                fila_mala=mala.fila.fila, filas=filas_del_grupo,
                clave=_clave_sin_numero(clave_grupo, indices[0]),
            ))
            continue

        fechas: list[date] = []
        conflicto = None
        for a in analizadas:
            if a.fecha_factura is not None and a.fecha_factura not in fechas:
                fechas.append(a.fecha_factura)
                if len(fechas) == 2:
                    conflicto = a
                    break
        if conflicto:
            resultado.omitidos.append(Omitido(
                motivo=FECHA_FACTURA_EN_CONFLICTO,
                detalle=" y ".join(f.isoformat() for f in fechas),
                fila_mala=conflicto.fila.fila, filas=filas_del_grupo,
                clave=_clave_sin_numero(clave_grupo, indices[0]),
            ))
            continue

        primera = analizadas[0]
        cliente = _resolver_cliente(indices[0], normalizar_texto(primera.fila.cliente))
        numero = leer_numero_comprobante(primera.fila.numero)
        fecha_a_facturar = primera.linea.fecha if numero is None else None
        resultado.grupos.append(GrupoHistorico(
            cliente_id=cliente["id"],
            cliente_nombre=cliente["nombre"],
            numero=numero,
            fecha_a_facturar=fecha_a_facturar,
            fecha=fechas[0] if fechas else None,
            pendiente_de_facturar=(
                fecha_a_facturar is not None
                and fecha_a_facturar > SIN_NUMERO_FACTURADO_HASTA
            ),
            lineas=[a.linea for a in analizadas],
        ))
        resultado.avisos.extend(aviso for a in analizadas for aviso in a.avisos)
    return resultado


# ─── Aplicar ────────────────────────────────────────────────────────────────

@dataclass
class ResultadoAplicar:
    """Qué hizo (o haría, si quien llama deshace) una corrida, por
    `clave_identidad`, en el orden del CSV; los que no vienen del CSV
    (ausentes, y sin número borrados o bloqueados que quedaron sin filas), en
    el orden de la base.

    - `cambiados`: históricos con número que cambiaron y no se tocaron (falta
      `--reemplazar-cambiados`). Los que sí se reemplazaron, y los sin número
      recalculados, van en `reemplazados`.
    - `sin_numero_bloqueados`: sin número con Adjuntos que habría que cambiar
      o borrar y no se tocan. Con alguno, la salida no puede ser 0
      (`bloqueado`).
    - `sin_numero_omitidos`: sin número de la base cuyas filas siguen en el
      CSV pero salieron omitidas. No se tocan: nunca se destruye dato porque
      la planilla se rompió, y la conciliación muestra la diferencia."""

    nuevos: list[str] = field(default_factory=list)
    iguales: list[str] = field(default_factory=list)
    cambiados: list[str] = field(default_factory=list)
    reemplazados: list[str] = field(default_factory=list)
    omitidos_por_carga_a_mano: list[GrupoHistorico] = field(default_factory=list)
    ausentes_del_csv: list[str] = field(default_factory=list)
    sin_numero_borrados: list[str] = field(default_factory=list)
    sin_numero_bloqueados: list[str] = field(default_factory=list)
    sin_numero_omitidos: list[str] = field(default_factory=list)

    @property
    def bloqueado(self) -> bool:
        return bool(self.sin_numero_bloqueados)

    def conteos(self) -> dict[str, int]:
        return {
            "nuevos": len(self.nuevos),
            "iguales": len(self.iguales),
            "cambiados": len(self.cambiados),
            "reemplazados": len(self.reemplazados),
            "omitidos_por_carga_a_mano": len(self.omitidos_por_carga_a_mano),
            "ausentes_del_csv": len(self.ausentes_del_csv),
            "sin_numero_borrados": len(self.sin_numero_borrados),
            "sin_numero_bloqueados": len(self.sin_numero_bloqueados),
            "sin_numero_omitidos": len(self.sin_numero_omitidos),
        }


def clave_de_grupo(grupo: GrupoHistorico) -> str:
    """`H|<cliente_id>|<numero>`, o `S|<cliente_id>|<fecha a facturar>` sin
    número: la misma función que usa la carga a mano (reglas_comprobante)."""
    return clave_identidad(
        historico=True, numero=grupo.numero, cliente_id=grupo.cliente_id,
        fecha_a_facturar=grupo.fecha_a_facturar,
    )


def _firma_de_linea(fecha, tarea_id, unidad, finca_id, cantidad, precio, importe) -> tuple:
    """Lo que se compara de una Línea. Sin los nombres: son copias del maestro,
    y renombrar una tarea en el campo no es un cambio de la planilla. Los
    Decimal se comparan por valor ("25" es igual a "25.00")."""
    return (fecha, tarea_id, unidad, finca_id, Decimal(cantidad), Decimal(precio),
            Decimal(importe))


def _cambio(existente: Comprobante, grupo: GrupoHistorico) -> bool:
    """Cambió la fecha o el multiconjunto de Líneas (el orden no cuenta)."""
    en_base = Counter(
        _firma_de_linea(li.fecha, li.tarea_id, li.unidad, li.finca_id,
                        li.cantidad, li.precio_unitario, li.importe)
        for li in existente.lineas
    )
    en_csv = Counter(
        _firma_de_linea(li.fecha, li.tarea_id, li.unidad, li.finca_id,
                        li.cantidad, li.precio_unitario, li.importe)
        for li in grupo.lineas
    )
    return existente.fecha != grupo.fecha or en_base != en_csv


def _lineas_del_grupo(grupo: GrupoHistorico) -> list[LineaComprobante]:
    return [
        LineaComprobante(
            orden=orden, fecha=li.fecha, tarea_id=li.tarea_id,
            tarea_nombre=li.tarea_nombre, unidad=li.unidad, finca_id=li.finca_id,
            finca_nombre=li.finca_nombre, cantidad=li.cantidad,
            precio_unitario=li.precio_unitario, importe=li.importe,
        )
        for orden, li in enumerate(grupo.lineas, start=1)
    ]


def _reemplazar(existente: Comprobante, grupo: GrupoHistorico) -> None:
    """Las Líneas y la fecha nuevas, con el mismo id y sus Adjuntos (pregunta
    8). No sella actualizado_en: el reemplazo del script no es una edición."""
    existente.fecha = grupo.fecha
    existente.pendiente_de_facturar = grupo.pendiente_de_facturar
    existente.lineas = _lineas_del_grupo(grupo)


def aplicar(db: Session, clasificacion: Clasificacion,
            reemplazar_cambiados: bool = False) -> ResultadoAplicar:
    """Lleva los grupos de la clasificación a la base, sin duplicar.

    Por `clave_identidad`:
    - si no existe, se crea un histórico: Factura, sin Empresa ni autor;
    - si existe igual, no se toca;
    - si cambió y tiene número, se informa; con `reemplazar_cambiados`, se le
      reemplazan las Líneas y la fecha;
    - si el mismo Cliente ya tiene una Factura cargada a mano con ese número,
      se omite el grupo, para no contar dos veces (las Notas de crédito
      numeran aparte, R3);
    - un histórico con número que ya no está en el CSV se informa y no se
      borra.
    Los sin número se recalculan siempre, sin esperar al flag: si una fila
    ganó número, pasa a su Comprobante numerado y sale del sin número, y uno
    que queda sin filas se borra; así una fila nunca cuenta dos veces. Uno con
    Adjuntos no se cambia ni se borra: queda en `sin_numero_bloqueados`.
    "Sin filas" es que ninguna fila sin número del CSV cae en su clave: uno
    cuyas filas salieron omitidas (su clave está en un `Omitido`) no se toca y
    queda en `sin_numero_omitidos`.

    Hace flush, para que un error de la base salga acá, pero no commit."""
    resultado = ResultadoAplicar()
    historicos = {
        c.clave_identidad: c
        for c in db.query(Comprobante)
                   .filter(Comprobante.es_historico.is_(True))
                   .order_by(Comprobante.id)
    }
    cargados_a_mano = {
        (cliente_id, numero)
        for cliente_id, numero in db.query(Comprobante.cliente_id, Comprobante.numero)
                                    .filter(Comprobante.es_historico.is_(False),
                                            Comprobante.tipo == FACTURA)
    }

    claves_del_csv = set()
    for grupo in clasificacion.grupos:
        if grupo.numero is not None and (grupo.cliente_id, grupo.numero) in cargados_a_mano:
            resultado.omitidos_por_carga_a_mano.append(grupo)
            continue
        clave = clave_de_grupo(grupo)
        claves_del_csv.add(clave)
        existente = historicos.get(clave)

        if existente is None:
            db.add(Comprobante(
                tipo=FACTURA, cliente_id=grupo.cliente_id,
                cliente_nombre=grupo.cliente_nombre, empresa_emisora=None,
                numero=grupo.numero, fecha=grupo.fecha, es_historico=True,
                pendiente_de_facturar=grupo.pendiente_de_facturar,
                clave_identidad=clave, creado_por=None,
                lineas=_lineas_del_grupo(grupo),
            ))
            resultado.nuevos.append(clave)
        elif not _cambio(existente, grupo):
            resultado.iguales.append(clave)
        elif grupo.numero is None:
            if existente.adjuntos:
                resultado.sin_numero_bloqueados.append(clave)
            else:
                _reemplazar(existente, grupo)
                resultado.reemplazados.append(clave)
        elif reemplazar_cambiados:
            _reemplazar(existente, grupo)
            resultado.reemplazados.append(clave)
        else:
            resultado.cambiados.append(clave)

    claves_omitidas = {o.clave for o in clasificacion.omitidos if o.clave}
    for clave, existente in historicos.items():
        if clave in claves_del_csv:
            continue
        if existente.numero is not None:
            resultado.ausentes_del_csv.append(clave)
        elif clave in claves_omitidas:
            resultado.sin_numero_omitidos.append(clave)
        elif existente.adjuntos:
            resultado.sin_numero_bloqueados.append(clave)
        else:
            db.delete(existente)
            resultado.sin_numero_borrados.append(clave)

    db.flush()
    return resultado


# ─── Conciliación por (Cliente, mes) ────────────────────────────────────────

# Motivo de omisión que pone aplicar, no la clasificación: el mismo Cliente y
# número ya tiene una Factura cargada a mano.
CARGADO_A_MANO = "cargado_a_mano"

# La celda de las filas sin FECHA A FACTURAR legible: no tienen mes, y sin
# ellas la planilla de su Cliente no cerraría. Siempre están omitidas.
SIN_MES = "sin mes"


@dataclass
class Celda:
    """Las sumas de importe de un Cliente en un mes (el de FECHA A FACTURAR,
    pregunta 10).

    - `planilla`: las filas con importe legible, desde la fecha de inicio;
    - `sin_numero`: la parte de lo migrable que va a un Comprobante sin
      número, y `pendiente`, la parte de esa posterior al corte (informativa);
    - `omitido`: por motivo;
    - `en_base`: las Líneas de los históricos de la base."""

    planilla: Decimal = Decimal("0")
    sin_numero: Decimal = Decimal("0")
    pendiente: Decimal = Decimal("0")
    omitido: Counter = field(default_factory=Counter)
    en_base: Decimal = Decimal("0")

    @property
    def migrable(self) -> Decimal:
        return self.planilla - sum(self.omitido.values(), Decimal("0"))

    @property
    def diferencia(self) -> Decimal:
        return self.migrable - self.en_base


@dataclass
class Conciliacion:
    """Las celdas por (Cliente, mes). El Cliente es el nombre normalizado
    (sin acentos, espacios colapsados, mayúsculas): el de la planilla para
    las filas, y la copia guardada para la base, que coinciden porque el
    Cliente se resuelve por ese mismo nombre. Así una fila con un Cliente que
    no se resolvió también tiene su celda. El mes es "AAAA-MM", o SIN_MES."""

    celdas: dict[tuple[str, str], Celda] = field(default_factory=dict)

    def celda(self, cliente: str, mes: str) -> Celda:
        return self.celdas.setdefault((cliente, mes), Celda())

    def con_diferencia(self) -> list[tuple[tuple[str, str], Celda]]:
        """Sólo las celdas con diferencia distinta de 0, ordenadas."""
        return sorted(
            ((clave, c) for clave, c in self.celdas.items() if c.diferencia != 0),
            key=lambda par: par[0],
        )


def _mes(fecha: date) -> str:
    return f"{fecha.year:04d}-{fecha.month:02d}"


def conciliar(db: Session, clasificacion: Clasificacion, resultado: ResultadoAplicar,
              desde: date) -> Conciliacion:
    """Planilla, omitido y base por Cliente y mes.

    Cada fila del CSV con importe legible cae en una sola celda, como migrable
    o como omitida, así planilla = migrable + omitido en cada una:
    - las de los grupos: migrables, salvo las de un grupo que aplicar omitió
      porque ya estaba cargado a mano (motivo CARGADO_A_MANO);
    - las de los omitidos, con el motivo de su grupo. Una fila anterior a
      `desde` no es planilla; una sin FECHA A FACTURAR legible va a SIN_MES.
    `en_base` lee la sesión: corrida después de aplicar, ve lo que quedaría
    en la base (confirmado o no)."""
    conciliacion = Conciliacion()
    a_mano = {clave_de_grupo(g) for g in resultado.omitidos_por_carga_a_mano}

    for grupo in clasificacion.grupos:
        cliente = normalizar_texto(grupo.cliente_nombre)
        a_mano_este = clave_de_grupo(grupo) in a_mano
        for linea in grupo.lineas:
            celda = conciliacion.celda(cliente, _mes(linea.fecha))
            celda.planilla += linea.importe
            if a_mano_este:
                celda.omitido[CARGADO_A_MANO] += linea.importe
                continue
            if grupo.numero is None:
                celda.sin_numero += linea.importe
                if grupo.pendiente_de_facturar:
                    celda.pendiente += linea.importe

    for omitido in clasificacion.omitidos:
        for fila in omitido.filas:
            try:
                importe = leer_numero_ar(fila.importe, IMPORTE[1])
            except ValorIlegible:
                continue
            if importe is None:
                continue
            try:
                fecha = leer_fecha(fila.fecha_a_facturar)
            except ValorIlegible:
                fecha = None
            if fecha is not None and fecha < desde:
                continue
            mes = _mes(fecha) if fecha is not None else SIN_MES
            celda = conciliacion.celda(normalizar_texto(fila.cliente), mes)
            celda.planilla += importe
            celda.omitido[omitido.motivo] += importe

    lineas_en_base = (
        db.query(Comprobante.cliente_nombre, LineaComprobante.fecha,
                 LineaComprobante.importe)
        .join(LineaComprobante, LineaComprobante.comprobante_id == Comprobante.id)
        .filter(Comprobante.es_historico.is_(True))
    )
    for cliente_nombre, fecha, importe in lineas_en_base:
        celda = conciliacion.celda(normalizar_texto(cliente_nombre), _mes(fecha))
        celda.en_base += Decimal(importe)

    return conciliacion


def codigo_de_salida(resultado: ResultadoAplicar, conciliacion: Conciliacion) -> int:
    """0 sólo si no queda nada nuevo ni cambiado y todas las diferencias son 0.

    "Cambiado" incluye lo que aplicar reemplazó o borró y los sin número
    bloqueados por Adjuntos: en una simulación es trabajo pendiente, y una
    segunda simulación después de aplicar no tiene ninguno."""
    pendiente = (
        resultado.nuevos or resultado.cambiados or resultado.reemplazados
        or resultado.sin_numero_borrados or resultado.bloqueado
    )
    return 1 if pendiente or conciliacion.con_diferencia() else 0
