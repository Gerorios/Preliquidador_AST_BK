"""La grilla de la quincena: los seis conceptos en una sola lista.

Etapa 8 del plan. Reemplaza a las cuatro pantallas de solo lectura de la etapa
2, que obligaban a mirar cada origen por separado y no dejaban ver el neto.

**Una lista y no seis solapas.** El liquidador no revisa "los viajes" y después
"el combustible": revisa a un tercero. Con solapas, ver todo lo de CORNEJO son
seis clics y seis búsquedas; con una lista filtrable es un filtro. El concepto
pasa a ser una columna más, que es lo que en realidad es.

**Cada dato en su campo, no un `detalle` armado.** Una columna que diga
"HIH521 · MEDINA, HECTOR MARTIN · CORTO" no se puede ordenar por patente, ni
filtrar por chofer, ni sumar. La pantalla decide qué columnas muestra según el
concepto que se esté mirando; acá se entregan todos los campos por separado y
los que no aplican quedan en None.

**Las líneas salen tal como quedaron calculadas.** Esto no recalcula nada: lee
`importe` y `estado_calculo` de cada hecho. Si una quincena se ve con ceros es
porque no se calculó, y eso se arregla calculando, no mirando acá.
"""
from datetime import date

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.modulos.terceros.models import (
    CALCULADO, SIGNO, CargaCombustible, HoraReparacion, HoraServicio,
    Liquidacion, PrecioSeguro, Repuesto, Viaje,
)

# Cómo se llama cada concepto en la pantalla. El orden es el del recibo: primero
# lo que se le paga al tercero, después lo que se le descuenta.
ETIQUETAS = {
    "viajes": "Viajes",
    "servicio": "Horas de servicio",
    "combustible": "Combustible",
    "repuestos": "Repuestos",
    "reparacion": "Horas de reparación",
    "seguros": "Seguros",
}

UNIDAD_VIAJE = "viaje"
UNIDAD_LITRO = "litro"
UNIDAD_HORA = "hora"
UNIDAD_POLIZA = "póliza"


def _limpio(v) -> str | None:
    """El origen manda la patente como ' FAP480' y el vale a veces vacío."""
    if v is None:
        return None
    texto = str(v).strip()
    return texto or None


def _linea(concepto: str, **campos) -> dict:
    """Una fila de la grilla.

    Todas tienen la misma forma aunque no usen todos los campos: un repuesto no
    tiene capataz y un seguro no tiene fecha. Lo que no aplica queda en None y
    la pantalla ni siquiera muestra esa columna para ese concepto.
    """
    base = {
        "concepto": concepto,
        "concepto_label": ETIQUETAS[concepto],
        "signo": SIGNO[concepto],
        # Comunes
        "fecha": None, "tercero": None, "cliente": None, "finca": None,
        "capataz": None, "tarea": None,
        # Propios de uno o dos conceptos
        "patente": None, "chofer": None, "tipo_viaje": None,
        "vale": None, "estacion": None,
        "maquina": None, "planilla": None, "supervisor": None,
        "repuesto": None, "rubro": None,
        "sub_rubro": None, "estado_taller": None,
        "sujeto": None, "referencia": None, "tipo_seguro": None,
        # El cálculo
        "cantidad": None, "unidad": None, "precio": None,
        "importe": None, "estado": CALCULADO,
    }
    base.update(campos)
    return base


class GrillaService:
    def __init__(self, db: Session):
        self.db = db

    def lineas(self, quincena: date) -> list[dict]:
        """Todas las líneas de la quincena, de la más vieja a la más nueva.

        Incluye las que no tienen importe: son las que hay que resolver, y
        esconderlas del listado sería esconder el trabajo pendiente.
        """
        filas = []
        filas += self._viajes(quincena)
        filas += self._servicio(quincena)
        filas += self._combustible(quincena)
        filas += self._repuestos(quincena)
        filas += self._reparacion(quincena)
        filas += self._seguros(quincena)
        # Sin fecha van al final: son los seguros, que son de la quincena entera.
        return sorted(filas, key=lambda f: (f["fecha"] is None, f["fecha"] or date.min,
                                            f["tercero"] or ""))

    # ─── Un método por concepto ─────────────────────────────────────────────
    #
    # No se unifican en una tabla de configuración a propósito: cada uno mapea
    # los campos que ese concepto tiene, y una tabla que resuelva eso con
    # lambdas sería más difícil de leer que seis métodos de diez líneas.

    def _de(self, modelo, quincena: date):
        """Los hechos que se liquidan en esta quincena.

        Se cruza contra `terceros_liquidacion` en vez de filtrar por
        `liquidacion_id` porque un hecho traído en una quincena puede cobrarse
        en otra, si el liquidador le cargó una quincena efectiva.
        """
        quincena_liq = func.coalesce(modelo.quincena_efectiva, Liquidacion.quincena)
        return (self.db.query(modelo)
                .join(Liquidacion, Liquidacion.id == modelo.liquidacion_id)
                .filter(quincena_liq == quincena).all())

    def _viajes(self, quincena: date) -> list[dict]:
        return [_linea(
            "viajes", id=v.id, fecha=v.fecha_uso, tercero=v.tercero,
            cliente=v.cliente, finca=v.finca, capataz=v.capataz, tarea=v.tarea,
            patente=_limpio(v.colectivo_patente), chofer=v.chofer,
            # Lo resuelve la tarifa, no el origen: hasta que no se calcula, un
            # viaje no es corto ni largo.
            tipo_viaje=v.tipo_viaje,
            cantidad=v.cantidad_viajes, unidad=UNIDAD_VIAJE,
            precio=v.precio_aplicado, importe=v.importe,
            estado=v.estado_calculo,
        ) for v in self._de(Viaje, quincena)]

    def _servicio(self, quincena: date) -> list[dict]:
        return [_linea(
            "servicio", id=h.id, fecha=h.fecha, tercero=h.tercero,
            cliente=h.cliente, finca=h.finca, tarea=h.tarea,
            maquina=h.maquinaria, planilla=h.planilla, supervisor=h.supervisor,
            # Si todavía no se calculó no hay unidad base elegida, y mostrar una
            # de las dos medidas al azar diría que se paga por esa.
            cantidad=h.cantidad_base, unidad=h.unidad_base,
            precio=h.precio_aplicado, importe=h.importe,
            estado=h.estado_calculo,
        ) for h in self._de(HoraServicio, quincena)]

    def _combustible(self, quincena: date) -> list[dict]:
        return [_linea(
            "combustible", id=c.id, fecha=c.fecha_uso, tercero=c.tercero,
            patente=_limpio(c.colectivo_patente), estacion=c.origen,
            vale=_limpio(c.vale),
            cantidad=c.litros, unidad=UNIDAD_LITRO,
            precio=c.precio_aplicado, importe=c.importe,
            estado=c.estado_calculo,
        ) for c in self._de(CargaCombustible, quincena)]

    def _repuestos(self, quincena: date) -> list[dict]:
        # El repuesto no lleva precio unitario acá: el que tiene es el del
        # sistema de compras, no uno que se haya pactado con el tercero.
        return [_linea(
            "repuestos", id=r.id, fecha=r.fecha, tercero=r.tercero,
            maquina=r.maquina, repuesto=r.repuesto, rubro=r.rubro,
            cantidad=r.cantidad, importe=r.importe,
            estado=r.estado_calculo,
        ) for r in self._de(Repuesto, quincena)]

    def _reparacion(self, quincena: date) -> list[dict]:
        return [_linea(
            "reparacion", id=h.id, fecha=h.fecha, tercero=h.tercero,
            finca=h.finca, maquina=h.maquina, rubro=h.rubro,
            sub_rubro=h.sub_rubro,
            # El del taller (Aprobado / Pendiente), que no es el del cálculo.
            estado_taller=h.estado,
            cantidad=h.horas_total, unidad=UNIDAD_HORA,
            precio=h.precio_aplicado, importe=h.importe,
            estado=h.estado_calculo,
        ) for h in self._de(HoraReparacion, quincena)]

    def _seguros(self, quincena: date) -> list[dict]:
        """Los seguros no tienen tabla de hechos: la tarifa **es** la línea.

        Por eso no tienen fecha —son de la quincena entera— ni estado distinto
        de CALCULADO: si están cargados, se cobran.
        """
        polizas = (self.db.query(PrecioSeguro)
                   .filter(PrecioSeguro.quincena == quincena).all())
        return [_linea(
            "seguros", id=p.id, tercero=p.tercero,
            sujeto=p.sujeto, referencia=p.referencia, tipo_seguro=p.tipo_seguro,
            cantidad=1, unidad=UNIDAD_POLIZA,
            precio=p.importe, importe=p.importe,
        ) for p in polizas]
