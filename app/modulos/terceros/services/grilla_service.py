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
    CALCULADO, SIGNO, CargaCombustible, CuotaRepuesto, HoraReparacion,
    HoraServicio, Liquidacion, PrecioSeguro, Repuesto, Viaje,
)
from app.modulos.terceros.services.calculo_service import sin_cuotas
from app.modulos.terceros.services.estaciones_service import EstacionesService

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
        "vale": None, "estacion": None, "observacion": None,
        # Si la estación facturó esta carga. Nulo cuando no se subió el archivo
        # de esa estación: no es lo mismo "no está facturada" que "todavía no
        # sabemos", y mostrarlo igual haría que se reclame de gusto.
        "facturada": None,
        "maquina": None, "planilla": None, "supervisor": None,
        "repuesto": None, "rubro": None,
        "sub_rubro": None, "estado_taller": None,
        "sujeto": None, "referencia": None, "tipo_seguro": None,
        # De qué quincena viene, cuando no es de ésta, y por qué se movió.
        # Es lo que el recibo va a mostrar como un ajuste.
        "viene_de": None, "motivo": None,
        # «2 de 5», en un repuesto que se descuenta en cuotas.
        "cuota": None,
        # El cálculo
        "cantidad": None, "unidad": None, "precio": None,
        "importe": None, "estado": CALCULADO,
    }
    base.update(campos)
    return base


def _movido(hecho) -> dict:
    """De dónde viene un hecho que se liquida en otra quincena.

    Vacío si se liquida en la suya, que es casi siempre: la liquidación se lee
    del mapa de identidad de la sesión, así que cuesta una consulta por
    quincena de origen y no una por fila.
    """
    if not hecho.quincena_efectiva:
        return {}
    return {"viene_de": hecho.liquidacion.quincena, "motivo": hecho.motivo_efectiva}


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
        filas += self._cuotas(quincena)
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
        consulta = (self.db.query(modelo)
                    .join(Liquidacion, Liquidacion.id == modelo.liquidacion_id)
                    .filter(quincena_liq == quincena))
        return sin_cuotas(consulta, modelo).all()

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
            estado=v.estado_calculo, **_movido(v),
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
            estado=h.estado_calculo, **_movido(h),
        ) for h in self._de(HoraServicio, quincena)]

    def _combustible(self, quincena: date) -> list[dict]:
        # Lo que las estaciones facturaron en esta quincena, para poder marcar
        # cada carga. Sin ningún archivo subido, `facturada` queda en nulo en
        # todas: decir que no están facturadas sería afirmar algo que no se sabe.
        facturados = EstacionesService(self.db).vales_facturados(quincena)
        hay_archivos = bool(facturados)

        return [_linea(
            "combustible", id=c.id, fecha=c.fecha_uso, tercero=c.tercero,
            patente=_limpio(c.colectivo_patente), estacion=c.origen,
            vale=_limpio(c.vale), observacion=_limpio(c.observacion),
            facturada=(_limpio(c.vale) in facturados if hay_archivos else None),
            cantidad=c.litros, unidad=UNIDAD_LITRO,
            precio=c.precio_aplicado, importe=c.importe,
            estado=c.estado_calculo, **_movido(c),
        ) for c in self._de(CargaCombustible, quincena)]

    def _repuestos(self, quincena: date) -> list[dict]:
        # El repuesto no lleva precio unitario acá: el que tiene es el del
        # sistema de compras, no uno que se haya pactado con el tercero.
        return [_linea(
            "repuestos", id=r.id, fecha=r.fecha, tercero=r.tercero,
            maquina=r.maquina, repuesto=r.repuesto, rubro=r.rubro,
            cantidad=r.cantidad, importe=r.importe,
            estado=r.estado_calculo, **_movido(r),
        ) for r in self._de(Repuesto, quincena)]

    def _cuotas(self, quincena: date) -> list[dict]:
        """Las cuotas de repuestos que se descuentan en esta quincena.

        Van como repuestos y con el id del repuesto: para quien liquida es el
        mismo repuesto, en partes. No chocan con las filas de `_repuestos`
        porque un repuesto con cuotas no aparece ahí, y un repuesto tiene a lo
        sumo una cuota por quincena.
        """
        cuotas = (self.db.query(CuotaRepuesto)
                  .filter(CuotaRepuesto.quincena == quincena).all())
        filas = []
        for c in cuotas:
            r = c.repuesto
            origen = r.liquidacion.quincena
            filas.append(_linea(
                "repuestos", id=r.id, fecha=r.fecha, tercero=r.tercero,
                maquina=r.maquina, repuesto=r.repuesto, rubro=r.rubro,
                cantidad=r.cantidad, estado=r.estado_calculo,
                importe=c.importe if r.estado_calculo == CALCULADO else 0,
                cuota="%d de %d" % (c.numero, c.de),
                viene_de=origen if origen != quincena else None,
                motivo=c.motivo,
            ))
        return filas

    def _reparacion(self, quincena: date) -> list[dict]:
        return [_linea(
            "reparacion", id=h.id, fecha=h.fecha, tercero=h.tercero,
            finca=h.finca, maquina=h.maquina, rubro=h.rubro,
            sub_rubro=h.sub_rubro,
            # El del taller (Aprobado / Pendiente), que no es el del cálculo.
            estado_taller=h.estado,
            cantidad=h.horas_total, unidad=UNIDAD_HORA,
            precio=h.precio_aplicado, importe=h.importe,
            estado=h.estado_calculo, **_movido(h),
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
