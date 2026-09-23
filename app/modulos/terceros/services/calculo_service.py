"""El cálculo del neto: aplicarle a cada hecho la tarifa que le corresponde.

Etapa 7 del plan. Hasta acá los hechos eran la foto de los orígenes y el
tarifario era un maestro de precios, sin nada que los uniera. Acá se unen.

**La regla más específica gana.** Una tarifa alcanza a un hecho cuando cada una
de sus dimensiones o está vacía —"esta regla no discrimina por eso"— o coincide
con la del hecho. Entre las que lo alcanzan gana la que tiene más dimensiones
cargadas. Si dos empatan en esa cuenta, el hecho queda `TARIFA_AMBIGUA` y lo
desempata una persona: el módulo no elige, porque elegir mal es cobrarle de más
o de menos a alguien y nadie se entera.

**Nada paga cero en silencio.** Un hecho sin precio no vale 0: queda con un
estado que dice *por qué* no tiene importe, y esos estados se resuelven con
gente distinta —el sistema de campo, el liquidador, el taller—. Por eso son
siete estados con nombre y no un importe en NULL.

**Recalcular es idempotente.** Se corre al generar y cada vez que cambia una
tarifa. No acumula ni ensucia: vuelve a mirar todo y reescribe el resultado.

**El importe se guarda, no se calcula al vuelo.** Dos razones: en la etapa 11 el
recibo se congela al emitirse, y no se congela algo que se recalcula en cada
request; y la grilla de la etapa 8 filtra y exporta sobre estas columnas.
"""
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import case, func, update
from sqlalchemy.orm import Session

from app.modulos.terceros.models import (
    CALCULADO, NO_APROBADA, NO_COBRAR, SIGNO, SIN_CANTIDAD, SIN_DIMENSION,
    SIN_TARIFA, SIN_TERCERO, TARIFA_AMBIGUA, UNIDAD_HORA_MAQUINA,
    CargaCombustible, HoraReparacion, HoraServicio, Liquidacion, PrecioSeguro,
    Repuesto, Viaje,
)
from app.modulos.terceros.services.consulta_taller import ESTADO_APROBADO
from app.modulos.terceros.services.tarifario_service import TIPOS, especificidad

CERO = Decimal("0")

# Cuántas filas entran en un UPDATE. Ver `_actualizar_en_lote`.
LOTE = 400


class LiquidacionInexistente(ValueError):
    """Se pidió calcular una quincena que nadie generó todavía."""


def _clave(texto) -> str:
    """Cómo se comparan dos nombres.

    Los orígenes no vienen prolijos —la patente llega como `' FAP480'`— y las
    tarifas se tipean a mano. Se compara sin espacios de sobra y sin distinguir
    mayúsculas, que es como los lee una persona. Dos reglas que sólo difieren en
    eso son la misma regla, y que queden ambiguas es lo correcto: son un error
    de carga, no una excepción.
    """
    return " ".join(str(texto or "").split()).upper()


# ─── Elegir la tarifa ───────────────────────────────────────────────────────

class Buscador:
    """Las reglas de un tarifario, listas para preguntarles por un hecho.

    Se indexan por tercero porque es la dimensión que está en los cinco
    tarifarios y la que más corta: para un hecho sólo hay que mirar las reglas
    de su dueño más las que no discriminan por dueño.
    """

    def __init__(self, tarifas, dimensiones: tuple[str, ...]):
        self.dimensiones = dimensiones
        self.por_tercero: dict[str, list] = defaultdict(list)
        for t in tarifas:
            self.por_tercero[_clave(t.tercero)].append(t)

    def _alcanza(self, tarifa, hecho: dict) -> bool:
        for d in self.dimensiones:
            valor = getattr(tarifa, d, SIN_DIMENSION)
            if not valor:
                continue          # la regla no discrimina por esta dimensión
            if _clave(valor) != _clave(hecho.get(d)):
                return False
        return True

    def buscar(self, hecho: dict):
        """Devuelve (tarifa, ambigua). Sin ganadora clara, tarifa es None."""
        candidatas = (self.por_tercero.get(_clave(hecho.get("tercero")), [])
                      + self.por_tercero.get(SIN_DIMENSION, []))
        alcanzan = [t for t in candidatas if self._alcanza(t, hecho)]
        if not alcanzan:
            return None, False
        mas = max(especificidad(t) for t in alcanzan)
        ganadoras = [t for t in alcanzan if especificidad(t) == mas]
        if len(ganadoras) > 1:
            return None, True
        return ganadoras[0], False


# ─── Qué se calcula y cómo ──────────────────────────────────────────────────
#
# Cada concepto declara de qué tabla salen sus hechos, con qué tarifario se
# tarifan, qué dimensiones del hecho se le preguntan a la regla, y qué cantidad
# se multiplica por el precio.
#
# `bloqueo` corre antes de buscar tarifa y devuelve un estado cuando la línea no
# se cobra por una razón anterior al precio: no se le busca tarifa a algo que
# nadie va a cobrar.

def _cant_servicio(hecho, tarifa):
    """La tarifa elige la medida: la hora de máquina o lo que midió la tarea."""
    if tarifa.unidad_base == UNIDAD_HORA_MAQUINA:
        return hecho.horas_maquina, UNIDAD_HORA_MAQUINA
    return hecho.unidades, tarifa.unidad_base


CONCEPTOS = {
    "viajes": {
        "modelo": Viaje,
        "tarifario": "viajes",
        "dimensiones": lambda h: {"tercero": h.tercero, "cliente": h.cliente,
                                  "finca": h.finca, "capataz": h.capataz},
        "cantidad": lambda h, t: (h.cantidad_viajes, None),
        "bloqueo": None,
        "etiqueta": "Viajes",
    },
    "servicio": {
        "modelo": HoraServicio,
        "tarifario": "servicio",
        "dimensiones": lambda h: {"tercero": h.tercero, "cliente": h.cliente,
                                  "finca": h.finca, "tarea": h.tarea},
        "cantidad": _cant_servicio,
        "bloqueo": None,
        "etiqueta": "Horas de servicio",
    },
    "combustible": {
        "modelo": CargaCombustible,
        "tarifario": "combustible",
        "dimensiones": lambda h: {"tercero": h.tercero},
        "cantidad": lambda h, t: (h.litros, None),
        "bloqueo": None,
        "etiqueta": "Combustible",
    },
    "reparacion": {
        "modelo": HoraReparacion,
        "tarifario": "reparacion",
        "dimensiones": lambda h: {"tercero": h.tercero},
        "cantidad": lambda h, t: (h.horas_total, None),
        # Sólo se cobran las aprobadas. Las pendientes esperan a la quincena en
        # que se aprueben; las rechazadas no llegan hasta acá.
        "bloqueo": lambda h: (None if _clave(h.estado) == ESTADO_APROBADO
                              else NO_APROBADA),
        "etiqueta": "Horas de reparación",
    },
    # El repuesto no se tarifa: su monto viene calculado del sistema de compras
    # y el módulo no lo recalcula. Lo único que se decide acá es si se cobra.
    "repuestos": {
        "modelo": Repuesto,
        "tarifario": None,
        "dimensiones": None,
        "cantidad": None,
        "bloqueo": lambda h: NO_COBRAR if h.no_cobrar else None,
        "etiqueta": "Repuestos",
    },
}

# Los seguros no tienen tabla de hechos: la tarifa ES la línea. Se cargan por
# tercero y quincena, y entran al total sin nada que multiplicar.
CONCEPTO_SEGUROS = "seguros"


def _redondear(valor: Decimal) -> Decimal:
    return valor.quantize(Decimal("0.01"))


class CalculoService:
    def __init__(self, db: Session):
        self.db = db
        self._buscadores: dict[tuple[str, date], Buscador] = {}

    # ─── Calcular ───────────────────────────────────────────────────────────

    def calcular(self, quincena: date, conceptos: tuple[str, ...] | None = None) -> dict:
        """Le pone precio a los hechos de una quincena. Idempotente.

        `conceptos` limita el recálculo a los que se piden. Es lo que se usa al
        cargar un precio: tocar la tarifa de un viaje no puede cambiar lo que
        vale un repuesto, así que recorrer las cinco tablas sería pagar cinco
        veces el viaje a la base por una cuenta que ya se sabe cuál es.
        """
        liquidacion = (self.db.query(Liquidacion)
                       .filter(Liquidacion.quincena == quincena).first())
        if liquidacion is None:
            raise LiquidacionInexistente(
                "La quincena del %s no está generada. Generala antes de "
                "ponerle precios." % quincena.isoformat())

        resumen = {}
        for concepto, conf in CONCEPTOS.items():
            if conceptos is not None and concepto not in conceptos:
                continue
            resumen[concepto] = self._calcular_concepto(
                concepto, conf, liquidacion)

        liquidacion.calculada_en = datetime.now()
        self.db.commit()
        return resumen

    def _calcular_concepto(self, concepto: str, conf: dict,
                           liquidacion: Liquidacion) -> dict:
        modelo = conf["modelo"]
        hechos = (self.db.query(modelo)
                  .filter(modelo.liquidacion_id == liquidacion.id).all())

        cambios, cuenta = [], defaultdict(int)
        for hecho in hechos:
            fila = self._calcular_hecho(concepto, conf, hecho, liquidacion)
            cuenta[fila["estado_calculo"]] += 1
            cambios.append({"id": hecho.id, **fila})

        self._actualizar_en_lote(modelo, cambios)
        return {"hechos": len(hechos), "por_estado": dict(cuenta)}

    def _actualizar_en_lote(self, modelo, cambios: list[dict]) -> None:
        """Un UPDATE por lote de filas, en vez de uno por fila.

        La base está en otro servidor, así que lo que se paga no es el trabajo
        sino el viaje de ida y vuelta. Con `bulk_update_mappings` cada hecho era
        una consulta y una quincena de 750 viajes no terminaba en dos minutos;
        con un CASE por columna, cada lote de %d filas es una sola consulta.

        Se arma con Core y no con SQL de texto a propósito: así cada valor viaja
        con el tipo de su columna. En texto, un Decimal llega como objeto suelto
        y el driver de sqlite lo rechaza.
        """ % LOTE
        if not cambios:
            return
        tabla = modelo.__table__
        columnas = sorted({c for fila in cambios for c in fila} - {"id"})
        for desde in range(0, len(cambios), LOTE):
            lote = cambios[desde:desde + LOTE]
            ids = [fila["id"] for fila in lote]
            valores = {
                columna: case({fila["id"]: fila.get(columna) for fila in lote},
                              value=tabla.c.id)
                for columna in columnas
            }
            self.db.execute(
                update(tabla).where(tabla.c.id.in_(ids)).values(**valores))

    def _calcular_hecho(self, concepto: str, conf: dict, hecho,
                        liquidacion: Liquidacion) -> dict:
        """Lo que hay que escribirle a un hecho. No toca la base."""
        # Un concepto sin tarifario —los repuestos— sólo se enciende o se apaga:
        # su monto ya viene calculado del sistema de compras.
        if conf["tarifario"] is None:
            bloqueo = conf["bloqueo"](hecho)
            if bloqueo:
                return {"importe": CERO, "estado_calculo": bloqueo}
            if not _clave(hecho.tercero):
                return {"importe": CERO, "estado_calculo": SIN_TERCERO}
            return {"importe": _redondear(Decimal(str(hecho.monto_total or 0))),
                    "estado_calculo": CALCULADO}

        vacio = {"tarifa_id": None, "precio_aplicado": None, "importe": CERO}
        if concepto == "viajes":
            vacio["tipo_viaje"] = None
        if concepto == "servicio":
            vacio.update({"unidad_base": None, "cantidad_base": None})

        if conf["bloqueo"]:
            bloqueo = conf["bloqueo"](hecho)
            if bloqueo:
                return {**vacio, "estado_calculo": bloqueo}

        # Sin dueño no hay a quién cobrarle, por más que exista una regla
        # general que lo alcance: la línea no entra a ningún recibo.
        if not _clave(hecho.tercero):
            return {**vacio, "estado_calculo": SIN_TERCERO}

        dimensiones = conf["dimensiones"](hecho)
        buscador = self._buscador(conf["tarifario"],
                                  self._quincena_liquidacion(hecho, liquidacion))
        tarifa, ambigua = buscador.buscar(dimensiones)
        if tarifa is None:
            return {**vacio,
                    "estado_calculo": TARIFA_AMBIGUA if ambigua else SIN_TARIFA}

        cantidad, unidad = conf["cantidad"](hecho, tarifa)
        # Cero es un importe válido —medio viaje puede ser cero viajes—; que la
        # medida no exista es otra cosa, y esa no se paga en cero callando.
        if cantidad is None:
            return {**vacio, "estado_calculo": SIN_CANTIDAD}

        precio = Decimal(str(tarifa.precio))
        importe = _redondear(Decimal(str(cantidad)) * precio)

        salida = {"tarifa_id": tarifa.id, "precio_aplicado": precio,
                  "importe": importe, "estado_calculo": CALCULADO}
        if concepto == "viajes":
            # El tipo no es clave de la regla sino su resultado: la misma regla
            # que fija el precio dice si el viaje es corto o largo.
            salida["tipo_viaje"] = tarifa.tipo_viaje
        if concepto == "servicio":
            salida.update({"unidad_base": unidad,
                           "cantidad_base": Decimal(str(cantidad or 0))})
        return salida

    def recalcular_si_existe(self, quincena: date,
                             conceptos: tuple[str, ...] | None = None) -> dict:
        """Como `calcular`, pero callado si la quincena no está generada.

        Es el que se llama al cargar un precio. Se pueden pactar tarifas de una
        quincena que todavía no se trajo de los orígenes; ahí no hay hechos que
        recalcular, y hacer fallar la carga del precio por eso sería obligar a
        generar antes de poder pactar.
        """
        try:
            return self.calcular(quincena, conceptos)
        except LiquidacionInexistente:
            return {}

    # ─── Los totales del recibo ─────────────────────────────────────────────

    def totales(self, quincena: date) -> list[dict]:
        """Por tercero: Total a facturar, seguros y Total a pagar.

        El Total a facturar **no lleva los seguros**: es la cifra que el Tercero
        copia en su factura, y el seguro no es un servicio que él preste sino
        una cuota que la empresa le adelantó y le recupera al pagarle. Los
        seguros se restan después, y esa resta es el Total a pagar.
        """
        por_tercero: dict[str, dict] = {}

        def entrada(tercero: str) -> dict:
            if tercero not in por_tercero:
                por_tercero[tercero] = {
                    "tercero": tercero,
                    **{c: CERO for c in CONCEPTOS},
                    "seguros": CERO,
                    "total_a_facturar": CERO,
                    "total_a_pagar": CERO,
                }
            return por_tercero[tercero]

        for concepto, conf in CONCEPTOS.items():
            for tercero, suma in self._sumar(conf["modelo"], quincena):
                entrada(tercero)[concepto] = suma

        for tercero, suma in self._sumar_seguros(quincena):
            entrada(tercero)["seguros"] = suma

        for fila in por_tercero.values():
            fila["total_a_facturar"] = sum(
                (SIGNO[c] * fila[c] for c in CONCEPTOS), CERO)
            fila["total_a_pagar"] = (fila["total_a_facturar"]
                                     + SIGNO["seguros"] * fila["seguros"])
        return sorted(por_tercero.values(), key=lambda f: f["tercero"])

    def _sumar(self, modelo, quincena: date):
        """Suma por tercero lo calculado que cae en esta quincena.

        Un hecho cae en la quincena en la que *se liquida*, que es su quincena
        efectiva si el liquidador le cargó una, y si no la de su liquidación.
        Por eso se cruza contra `terceros_liquidacion` en vez de filtrar por
        `liquidacion_id`: un hecho traído en una quincena puede cobrarse en otra.
        """
        quincena_liq = func.coalesce(modelo.quincena_efectiva,
                                     Liquidacion.quincena)
        return (self.db.query(modelo.tercero, func.sum(modelo.importe))
                .join(Liquidacion, Liquidacion.id == modelo.liquidacion_id)
                .filter(quincena_liq == quincena)
                .filter(modelo.estado_calculo == CALCULADO)
                .filter(modelo.tercero.isnot(None))
                .group_by(modelo.tercero).all())

    def _sumar_seguros(self, quincena: date):
        return (self.db.query(PrecioSeguro.tercero,
                              func.sum(PrecioSeguro.importe))
                .filter(PrecioSeguro.quincena == quincena)
                .group_by(PrecioSeguro.tercero).all())

    # ─── Lo que quedó sin calcular ──────────────────────────────────────────

    def pendientes(self, quincena: date) -> dict:
        """Cuántas líneas quedaron sin importe y por qué, concepto por concepto.

        Es la lista de lo que falta para poder liquidar. Cada estado se resuelve
        con gente distinta, así que se cuentan por separado y no como un total.
        """
        salida = {}
        for concepto, conf in CONCEPTOS.items():
            modelo = conf["modelo"]
            quincena_liq = func.coalesce(modelo.quincena_efectiva,
                                         Liquidacion.quincena)
            filas = (self.db.query(modelo.estado_calculo, func.count())
                     .join(Liquidacion, Liquidacion.id == modelo.liquidacion_id)
                     .filter(quincena_liq == quincena)
                     .filter(modelo.estado_calculo != CALCULADO)
                     .group_by(modelo.estado_calculo).all())
            if filas:
                salida[concepto] = {estado: cuenta for estado, cuenta in filas}
        return salida

    # ─── Interno ────────────────────────────────────────────────────────────

    def _quincena_liquidacion(self, hecho, liquidacion: Liquidacion) -> date:
        """En qué quincena se cobra este hecho, que es la del tarifario que le
        toca: si se difirió, paga los precios de la quincena a la que se fue."""
        return hecho.quincena_efectiva or liquidacion.quincena

    def _buscador(self, tipo: str, quincena: date) -> Buscador:
        clave = (tipo, quincena)
        if clave not in self._buscadores:
            conf = TIPOS[tipo]
            modelo = conf["modelo"]
            tarifas = (self.db.query(modelo)
                       .filter(modelo.quincena == quincena).all())
            self._buscadores[clave] = Buscador(tarifas, conf["dimensiones"])
        return self._buscadores[clave]
