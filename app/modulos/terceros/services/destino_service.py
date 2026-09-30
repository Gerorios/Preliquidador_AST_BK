"""En qué quincena se liquida cada hecho.

Un hecho se liquida, por defecto, en la quincena en la que se trajo. Hay dos
formas de cambiar eso, y las dos las decide el liquidador a mano:

  - **Mover** un hecho entero a otra quincena. Es la `quincena_efectiva` que
    los cinco hechos tienen desde la migración 001: un viaje que llegó tarde, o
    un descuento que se posterga para no ahogar a un tercero. Lleva motivo,
    porque el recibo lo va a mostrar como un ajuste y alguien tiene que poder
    leer por qué.
  - **Repartir** un repuesto en cuotas quincenales iguales. Sólo repuestos: es
    el único concepto que llega con un monto grande de una vez.

Un repuesto con cuotas deja de descontarse en su quincena y se descuenta en
cada una de las de sus cuotas. Por eso no se lo puede además mover: serían dos
respuestas distintas a la misma pregunta.

**Mover no cambia el precio.** Se cobra siempre con el tarifario de la quincena
en la que se generó el hecho (lo decidió el usuario, 2026-09-30): un viaje que
llegó tarde se paga lo que valía cuando se hizo. Y el repuesto no tiene
tarifario: su importe es el que trajo compras, y el de cada cuota queda escrito
al repartirlo.
"""
from datetime import date
from decimal import ROUND_DOWN, Decimal

from sqlalchemy.orm import Session

from app.modulos.terceros.models import CALCULADO, CuotaRepuesto, Repuesto
from app.modulos.terceros.services import quincenas
from app.modulos.terceros.services.calculo_service import CONCEPTOS

# Un año de quincenas. No es una regla del negocio: es la baranda contra un
# cero de más tipeado sin querer, que repartiría un repuesto en 240 cuotas.
MAXIMO_CUOTAS = 24

CENTAVO = Decimal("0.01")


class DestinoInvalido(ValueError):
    """Lo que se pidió no se puede hacer, y el mensaje dice por qué."""


def repartir(importe: Decimal, cuotas: int) -> list[Decimal]:
    """Cuotas iguales al centavo; la última absorbe la diferencia.

    Hacia abajo y no redondeando: así la diferencia que absorbe la última es
    siempre positiva, y la cuota final nunca queda más chica que las demás
    —se leería como un error—.
    """
    base = (importe / cuotas).quantize(CENTAVO, rounding=ROUND_DOWN)
    return [base] * (cuotas - 1) + [importe - base * (cuotas - 1)]


class DestinoService:
    def __init__(self, db: Session):
        self.db = db

    # ─── Mover un hecho entero ──────────────────────────────────────────────

    def mover(self, concepto: str, id_: int, quincena: date,
              motivo: str | None) -> object:
        """Que un hecho se liquide en otra quincena, al mismo precio.

        Mandarlo a la quincena en la que se trajo es deshacer el movimiento, y
        eso no pide motivo: volver a lo normal no hay que explicarlo.
        """
        conf = CONCEPTOS.get(concepto)
        if conf is None:
            raise DestinoInvalido("No existe el concepto %r." % concepto)
        if not quincenas.es_inicio_valido(quincena):
            raise DestinoInvalido(
                "Una quincena se identifica por su primer día: el 1 o el 16.")

        hecho = self.db.get(conf["modelo"], id_)
        if hecho is None:
            raise DestinoInvalido("No existe esa línea.")
        if concepto == "repuestos" and self._tiene_cuotas(id_):
            raise DestinoInvalido(
                "Este repuesto se descuenta en cuotas. Para cambiar cuándo, "
                "cambiá las cuotas.")

        origen = hecho.liquidacion.quincena
        if quincena == origen:
            hecho.quincena_efectiva = None
            hecho.motivo_efectiva = None
        else:
            motivo = (motivo or "").strip()
            if not motivo:
                raise DestinoInvalido(
                    "Mover una línea de quincena pide el motivo: el recibo lo "
                    "muestra como un ajuste y tiene que poder leerse por qué.")
            hecho.quincena_efectiva = quincena
            hecho.motivo_efectiva = motivo
        # Sin recalcular: el precio sale del tarifario de la quincena en la que
        # se generó, así que moverlo cambia cuándo se cobra y no cuánto.
        self.db.commit()
        return hecho

    # ─── Repartir un repuesto en cuotas ─────────────────────────────────────

    def repartir_en_cuotas(self, repuesto_id: int, desde: date, cuotas: int,
                           motivo: str | None = None,
                           usuario_id: int | None = None) -> list[CuotaRepuesto]:
        """Reemplaza el plan del repuesto por uno nuevo.

        Reemplaza y no suma: un repuesto tiene un solo plan, y dos planes a la
        vez le descontarían el mismo repuesto dos veces.
        """
        if not quincenas.es_inicio_valido(desde):
            raise DestinoInvalido(
                "Una quincena se identifica por su primer día: el 1 o el 16.")
        if not 2 <= cuotas <= MAXIMO_CUOTAS:
            raise DestinoInvalido(
                "Las cuotas van de 2 a %d. En una sola es un descuento total."
                % MAXIMO_CUOTAS)

        repuesto = self.db.get(Repuesto, repuesto_id)
        if repuesto is None:
            raise DestinoInvalido("No existe ese repuesto.")
        # Sin importe no hay qué repartir, y una cuota de cero pasaría por un
        # descuento hecho.
        if repuesto.estado_calculo != CALCULADO or not repuesto.importe:
            raise DestinoInvalido(
                "Este repuesto no tiene un importe que descontar, así que no "
                "se puede repartir en cuotas.")

        self._borrar_cuotas(repuesto_id)
        # El plan manda sobre cualquier movimiento anterior: con cuotas, la
        # quincena del repuesto ya no dice nada.
        repuesto.quincena_efectiva = None
        repuesto.motivo_efectiva = None

        motivo = (motivo or "").strip() or None
        quincena = desde
        nuevas = []
        for numero, importe in enumerate(
                repartir(Decimal(str(repuesto.importe)), cuotas), start=1):
            nuevas.append(CuotaRepuesto(
                repuesto_id=repuesto_id, numero=numero, de=cuotas,
                quincena=quincena, importe=importe, motivo=motivo,
                creado_por=usuario_id))
            quincena = quincenas.siguiente(quincena)
        self.db.add_all(nuevas)
        self.db.commit()
        return nuevas

    def quitar_cuotas(self, repuesto_id: int) -> int:
        """Vuelve a descontarlo entero, en su quincena."""
        n = self._borrar_cuotas(repuesto_id)
        self.db.commit()
        return n

    def cuotas_de(self, repuesto_id: int) -> list[CuotaRepuesto]:
        return (self.db.query(CuotaRepuesto)
                .filter(CuotaRepuesto.repuesto_id == repuesto_id)
                .order_by(CuotaRepuesto.numero).all())

    # ─── Interno ────────────────────────────────────────────────────────────

    def _tiene_cuotas(self, repuesto_id: int) -> bool:
        return (self.db.query(CuotaRepuesto.id)
                .filter(CuotaRepuesto.repuesto_id == repuesto_id).first()
                is not None)

    def _borrar_cuotas(self, repuesto_id: int) -> int:
        return (self.db.query(CuotaRepuesto)
                .filter(CuotaRepuesto.repuesto_id == repuesto_id)
                .delete(synchronize_session=False))
