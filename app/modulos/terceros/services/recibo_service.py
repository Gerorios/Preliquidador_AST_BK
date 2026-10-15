"""El recibo de cada tercero, su factura, su pago y la cuenta corriente.

Etapa 11 del plan. Hasta acá cada quincena se calculaba en vivo. El recibo es
lo que se le **manda** a un tercero, y por eso al emitirse se congela: guarda
una foto de sus líneas y sus totales, y de ahí en más se lee la foto.

─── Los bloques ─────────────────────────────────────────────────────────────

Lo que se le liquida en una quincena se parte en tres, para que el tercero
entienda de qué es cada cosa (lo pidió el usuario, 2026-09-30):

  - **De esta quincena**: lo que se generó en ella y se liquida en ella.
  - **Cuotas de repuestos**: «cuota 2 de 5».
  - **Ajustes de otras quincenas**: lo que se movió hasta acá, por concepto
    y con su motivo («ajuste viajes: llegó tarde»).

Los tres suman al **Total a facturar**. Los seguros van aparte, después: el
tercero no los factura (ver «Total a facturar» en CONTEXT-terceros.md).

─── La cuenta corriente ─────────────────────────────────────────────────────

El saldo anterior de una quincena es el saldo inicial del tercero más, por
cada recibo emitido antes, lo que tenía que cobrar menos lo que se le pagó.
Se suma y no se arrastra de recibo en recibo: así un pago cargado tarde sobre
una quincena vieja corrige solo todas las que siguen.

Una quincena **en revisión** no suma: está en discusión con el tercero, y se
muestra aparte para que no se olvide sin ensuciar el número que factura.

─── Lo que llega tarde ──────────────────────────────────────────────────────

Un recibo emitido es una foto, pero los orígenes siguen cambiando: un viaje se
carga tarde, una hora de taller se aprueba, alguien borra algo ya pagado. Para
cada recibo emitido se compara la foto contra lo que esa quincena liquidaría
hoy, línea por línea, y lo que no coincide se propone en el recibo abierto:

  - lo que **llegó después** se propone mover;
  - lo que **desapareció** o **cambió de importe**, un ajuste por la diferencia.

Nada se hace solo: el sistema propone y el liquidador decide (plan, 3.3). Se
compara contra la foto y no contra fechas de carga porque no todas las fuentes
las tienen, y la foto está para todas.
"""
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.modulos.terceros.models import (
    AJUSTE_CONCEPTOS, CALCULADO, EMPRESAS, FACTURA_APROBADA, FACTURA_RECHAZADA,
    FACTURA_RECIBIDA, PAGO_PARCIAL, PAGO_TOTAL, SIN_CANTIDAD, SIN_DIMENSION,
    SIN_TARIFA, TARIFA_AMBIGUA, Ajuste, CuotaRepuesto, Liquidacion,
    LlegadaDescartada, Recibo, ReciboEvento, ReciboFactura, Repuesto, SaldoInicial,
)
from app.modulos.terceros.services import quincenas
from app.modulos.terceros.services.calculo_service import CONCEPTOS
from app.modulos.terceros.services.grilla_service import GrillaService

CERO = Decimal("0.00")

# Lo que frena la emisión: líneas que tendrían que cobrarse y no tienen
# importe. «Nada paga cero en silencio»: emitir con esto sería mandarle al
# tercero un recibo incompleto como si estuviera completo.
#
# No frenan NO_COBRAR ni NO_APROBADA: las dos son decisiones, no faltas. Una
# hora de taller sin aprobar se cobra en la quincena en que se apruebe.
PENDIENTES = (SIN_TARIFA, TARIFA_AMBIGUA, SIN_CANTIDAD, SIN_DIMENSION)

# El orden del recibo: primero lo que se le paga, después lo que se le descuenta.
ORDEN = ("viajes", "servicio", "combustible", "repuestos", "reparacion")

# Cómo se titula cada grupo del bloque de ajustes. Junta lo movido de otra
# quincena y lo cargado a mano del mismo concepto: para el tercero las dos
# cosas son «un ajuste de combustible».
TITULO_AJUSTE = {
    "viajes": "Ajuste viajes",
    "servicio": "Ajuste horas de servicio",
    "combustible": "Ajuste combustible",
    "repuestos": "Ajuste repuestos",
    "reparacion": "Ajuste horas de reparación",
    "otro": "Otros ajustes",
}

# Los bloques que suman al Total a facturar. Los seguros van aparte.
BLOQUES_COBRABLES = ("quincena", "cuotas", "ajustes")

UN_CENTAVO = Decimal("0.01")


class ReciboInvalido(ValueError):
    """Lo que se pidió no se puede hacer, y el mensaje dice por qué."""


def quincenas_emitidas(db: Session, tercero: str, quincenas) -> set[date]:
    """De esas quincenas, en cuáles el recibo del tercero ya está emitido.

    Lo usa quien mueve hechos: una línea de un recibo emitido quedaría a la
    vez en la foto congelada y en el recibo al que se la mueva.
    """
    quincenas = [q for q in quincenas if q]
    if not tercero or not quincenas:
        return set()
    return {q for (q,) in (db.query(Recibo.quincena)
                           .filter(Recibo.tercero == tercero,
                                   Recibo.quincena.in_(quincenas),
                                   Recibo.emitido_en.isnot(None)).all())}


def _serializable(v):
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    if isinstance(v, Decimal):
        return str(v)
    return v


def _dec(v) -> Decimal:
    return Decimal(str(v)) if v not in (None, "") else CERO


def _pesos(v) -> str:
    """$ 1.234.567,89, como se lee en pantalla."""
    texto = format(_dec(v), ",.2f").replace(",", "X").replace(".", ",").replace("X", ".")
    return "$ " + texto


def _bloque_de(linea: dict) -> str:
    if linea["concepto"] == "seguros":
        return "seguros"
    if linea.get("cuota"):
        return "cuotas"
    if linea["concepto"] == "ajustes" or linea.get("viene_de"):
        return "ajustes"
    return "quincena"


def _grupo_de(bloque: str, linea: dict) -> str:
    """En el bloque de ajustes se agrupa por de qué es, no por de dónde vino."""
    if bloque == "ajustes":
        return linea.get("ajuste_de") or linea["concepto"]
    return linea["concepto"]


def clave_linea(linea: dict) -> str:
    """Cómo se identifica una línea entre la foto y lo de hoy: «viajes:123», o
    «repuestos:45:2 de 3» si es una cuota. El id solo no alcanza: un repuesto
    en cuotas es la misma fila en varias quincenas."""
    partes = [linea["concepto"], str(linea["id"])]
    if linea.get("cuota"):
        partes.append(str(linea["cuota"]))
    return ":".join(partes)


def _efecto(linea: dict) -> Decimal:
    """Lo que la línea mueve el Total a facturar, con su signo."""
    return int(linea["signo"]) * _dec(linea["importe"])


def _cobrable(linea: dict) -> bool:
    return linea["estado"] == CALCULADO and bool(linea.get("importe"))


def _lineas_de_la_foto(recibo) -> dict[str, dict]:
    """Las líneas que suman al Total a facturar de un recibo emitido."""
    salida = {}
    for bloque in BLOQUES_COBRABLES:
        for grupo in (recibo.contenido or {}).get(bloque, []):
            for linea in grupo["lineas"]:
                salida[clave_linea(linea)] = linea
    return salida


def en_alguna_foto(db: Session, tercero: str, concepto: str, id_: int,
                   quincenas_) -> bool:
    """Si esa línea está en la foto de un recibo emitido de esas quincenas.

    Lo usa quien mueve hechos: lo que está en una foto ya se le liquidó al
    tercero, y moverlo lo pondría también en otro recibo. Lo que llegó después
    de emitir no está en la foto, y ése sí se tiene que poder mover.
    """
    quincenas_ = [q for q in quincenas_ if q]
    if not tercero or not quincenas_:
        return False
    recibos = (db.query(Recibo)
               .filter(Recibo.tercero == tercero, Recibo.quincena.in_(quincenas_),
                       Recibo.emitido_en.isnot(None)).all())
    return any(l["concepto"] == concepto and int(l["id"]) == int(id_)
               for r in recibos for l in _lineas_de_la_foto(r).values())


def armar(lineas: list[dict], saldo_anterior: Decimal) -> dict:
    """Los bloques y los totales, a partir de las líneas de un tercero.

    Es puro: no mira la base. Lo usan igual el recibo en vivo y el que se
    emite, así los dos no pueden armarse distinto.
    """
    cobrables = [f for f in lineas if f["estado"] == CALCULADO and f.get("importe")]
    pendientes = [f for f in lineas if f["estado"] in PENDIENTES]

    bloques = {"quincena": defaultdict(list), "cuotas": defaultdict(list),
               "ajustes": defaultdict(list), "seguros": defaultdict(list)}
    for f in cobrables:
        bloque = _bloque_de(f)
        bloques[bloque][_grupo_de(bloque, f)].append(
            {k: _serializable(v) for k, v in f.items()})

    def grupos(bloque: str) -> list[dict]:
        salida = []
        for clave in ORDEN + ("otro", "seguros"):
            filas = bloques[bloque].get(clave)
            if not filas:
                continue
            salida.append({
                "concepto": clave,
                "label": (TITULO_AJUSTE.get(clave, clave) if bloque == "ajustes"
                          else filas[0]["concepto_label"]),
                "signo": filas[0]["signo"],
                "subtotal": str(sum((_dec(f["importe"]) for f in filas), CERO)),
                # Con signo. Un grupo de ajustes puede mezclar lo que se le
                # paga y lo que se le descuenta, así que su total es éste y no
                # el subtotal con el signo de la primera línea.
                "neto": str(sum((_efecto(f) for f in filas), CERO)),
                "lineas": filas,
            })
        return salida

    contenido = {b: grupos(b) for b in ("quincena", "cuotas", "ajustes", "seguros")}

    def neto(bloque: str) -> Decimal:
        return sum((_dec(g["neto"]) for g in contenido[bloque]), CERO)

    total_a_facturar = neto("quincena") + neto("cuotas") + neto("ajustes")
    seguros = sum((_dec(g["subtotal"]) for g in contenido["seguros"]), CERO)
    total_a_pagar = total_a_facturar - seguros
    return {
        "contenido": contenido,
        "total_a_facturar": total_a_facturar,
        "seguros": seguros,
        "total_a_pagar": total_a_pagar,
        "saldo_anterior": saldo_anterior,
        "total": total_a_pagar + saldo_anterior,
        "pendientes": len(pendientes),
    }


class ReciboService:
    def __init__(self, db: Session):
        self.db = db

    # ─── Leer ───────────────────────────────────────────────────────────────

    def listar(self, quincena: date) -> list[dict]:
        """Un renglón por tercero de la quincena: en vivo si no se emitió, la
        foto si ya se emitió, y cuánto cambió desde entonces."""
        por_tercero = defaultdict(list)
        for f in GrillaService(self.db).lineas(quincena):
            if f["tercero"]:
                por_tercero[f["tercero"]].append(f)
        recibos = {r.tercero: r for r in (self.db.query(Recibo)
                                          .filter(Recibo.quincena == quincena).all())}
        tarde = self.llegadas(quincena)
        terceros = set(por_tercero) | set(recibos) | set(tarde)
        saldos = self._saldos_anteriores(quincena, terceros)

        salida = []
        for tercero in sorted(terceros):
            vivo = armar(por_tercero.get(tercero, []), saldos.get(tercero, CERO))
            recibo = recibos.get(tercero)
            datos = self._foto(recibo, vivo) if self._esta_emitido(recibo) else vivo
            salida.append({**self._renglon(tercero, quincena, datos, recibo),
                           "llegadas": len(tarde.get(tercero, []))})
        return salida

    def detalle(self, quincena: date, tercero: str) -> dict:
        """El recibo de un tercero: la foto si está emitido, en vivo si no."""
        recibo = self._recibo(quincena, tercero)
        vivo = self._en_vivo(quincena, tercero)
        datos = self._foto(recibo, vivo) if self._esta_emitido(recibo) else vivo
        tarde = self.llegadas(quincena, tercero).get(tercero, [])
        return {**self._renglon(tercero, quincena, datos, recibo),
                "contenido": datos["contenido"],
                "llegadas_detalle": tarde,
                "llegadas": len(tarde),
                "ajustes": [self._ajuste_a_dict(a) for a in self.ajustes_de(quincena, tercero)],
                "eventos": [self._evento_a_dict(e) for e in (recibo.eventos if recibo else [])]}

    def saldo_anterior(self, quincena: date, tercero: str) -> Decimal:
        return self._saldos_anteriores(quincena, {tercero}).get(tercero, CERO)

    # ─── Emitir y reabrir ───────────────────────────────────────────────────

    def emitir(self, quincena: date, tercero: str, empresa: str | None = None,
               usuario_id: int | None = None) -> Recibo:
        """Congela el recibo: guarda la foto y desde ahí se lee la foto.

        Con `empresa`, todo se le factura a ésa: es el caso de siempre, y el de
        emitir en lote. Sin ella, se usa el reparto que ya se eligió.
        """
        if empresa is not None and empresa not in EMPRESAS:
            raise ReciboInvalido(
                "La empresa tiene que ser una de: %s." % ", ".join(EMPRESAS))
        if self.db.query(Liquidacion).filter(Liquidacion.quincena == quincena).first() is None:
            raise ReciboInvalido("Esa quincena no está generada.")

        recibo = self._recibo(quincena, tercero)
        if recibo is not None and recibo.emitido_en is not None:
            raise ReciboInvalido(
                "La orden de facturación de %s ya está emitida." % tercero)

        datos = self._en_vivo(quincena, tercero)
        if datos["pendientes"]:
            raise ReciboInvalido(
                "%s tiene %d línea(s) sin precio en esta quincena. Se emite "
                "cuando estén resueltas: si no, la orden diría menos de lo que es."
                % (tercero, datos["pendientes"]))
        if not any(datos["contenido"].values()):
            raise ReciboInvalido("%s no tiene nada que liquidar en esta quincena." % tercero)

        if recibo is None:
            recibo = Recibo(quincena=quincena, tercero=tercero)
            self.db.add(recibo)
        if empresa is not None:
            self._poner_reparto(recibo, [(empresa, None)])
        self._validar_reparto(recibo, tercero, datos["total_a_facturar"])
        # Con una sola empresa, lo que se le factura es el Total a facturar: se
        # escribe ahora, que ya no cambia.
        if len(recibo.facturas) == 1:
            recibo.facturas[0].importe = datos["total_a_facturar"]
        recibo.emitido_en = datetime.now()
        recibo.emitido_por = usuario_id
        recibo.contenido = datos["contenido"]
        recibo.total_a_facturar = datos["total_a_facturar"]
        recibo.seguros = datos["seguros"]
        recibo.total_a_pagar = datos["total_a_pagar"]
        recibo.saldo_anterior = datos["saldo_anterior"]
        self.db.flush()
        self._evento(recibo, "EMITIDO", usuario_id, detalle={
            "empresas": [{"empresa": f.empresa, "importe": str(f.importe)}
                         for f in recibo.facturas],
            "total_a_facturar": str(datos["total_a_facturar"]),
            "total_a_pagar": str(datos["total_a_pagar"])})
        self.db.commit()
        return recibo

    def reabrir(self, quincena: date, tercero: str, motivo: str,
                usuario_id: int | None = None) -> Recibo:
        """Vuelve a armarlo en vivo. Pide motivo y deja el rastro."""
        recibo = self._emitido(quincena, tercero)
        motivo = (motivo or "").strip()
        if not motivo:
            raise ReciboInvalido("Reabrir una orden de facturación pide el motivo.")
        if recibo.pago:
            raise ReciboInvalido(
                "Esta orden ya tiene el pago registrado. Reabrirla cambiaría un "
                "saldo que ya se saldó: primero hay que sacar el pago.")

        detalle = {"total_a_pagar": str(recibo.total_a_pagar)}
        # Una factura aprobada se aprobó contra estos montos, que pueden
        # cambiar: vuelve a quedar por aprobar.
        for factura in recibo.facturas:
            if factura.estado == FACTURA_APROBADA:
                factura.estado = FACTURA_RECIBIDA
                detalle["factura"] = "vuelve a quedar por aprobar"
        # Con una sola empresa, lo que se le factura vuelve a seguir al total.
        if len(recibo.facturas) == 1:
            recibo.facturas[0].importe = None

        recibo.emitido_en = None
        recibo.emitido_por = None
        recibo.contenido = None
        recibo.total_a_facturar = recibo.seguros = recibo.total_a_pagar = None
        recibo.saldo_anterior = None
        self._evento(recibo, "REABIERTO", usuario_id, motivo=motivo, detalle=detalle)
        self.db.commit()
        return recibo

    def elegir_empresa(self, quincena: date, tercero: str, empresa: str | None,
                       usuario_id: int | None = None) -> Recibo | None:
        """Todo se le factura a una sola empresa. Vacío saca la elección."""
        empresa = (empresa or "").strip() or None
        return self.repartir(quincena, tercero,
                             [{"empresa": empresa}] if empresa else [], usuario_id)

    def repartir(self, quincena: date, tercero: str, partes: list[dict],
                 usuario_id: int | None = None) -> Recibo | None:
        """A qué empresas le factura y cuánto a cada una, elegido antes de emitir.

        Queda en el recibo y el borrador ya lo muestra (lo pidió el usuario,
        2026-10-05). Con una sola empresa no hace falta el importe: es el Total
        a facturar. Con más, cada una lleva el suyo, y que sumen el total se
        controla al emitir: hasta entonces el total todavía puede cambiar.
        No deja evento: el que cuenta es el de la emisión.

        Un recibo emitido no cambia de empresas: ya se mandó así, y cambiarlo
        por debajo haría que el papel y el sistema digan cosas distintas.
        """
        reparto = []
        for parte in partes or []:
            empresa = (parte.get("empresa") or "").strip()
            if empresa not in EMPRESAS:
                raise ReciboInvalido(
                    "La empresa tiene que ser una de: %s." % ", ".join(EMPRESAS))
            if any(e == empresa for e, _ in reparto):
                raise ReciboInvalido("%s está dos veces." % empresa)
            reparto.append((empresa, parte.get("importe")))
        if len(reparto) == 1:
            reparto = [(reparto[0][0], None)]
        else:
            for empresa, importe in reparto:
                if importe in (None, "") or _dec(importe) <= CERO:
                    raise ReciboInvalido("Falta cuánto se le factura a %s." % empresa)
            reparto = [(e, _dec(i)) for e, i in reparto]

        if self.db.query(Liquidacion).filter(Liquidacion.quincena == quincena).first() is None:
            raise ReciboInvalido("Esa quincena no está generada.")
        recibo = self._recibo(quincena, tercero)
        if recibo is not None and recibo.emitido_en is not None:
            raise ReciboInvalido(
                "La orden de facturación de %s ya está emitida. Para cambiar a "
                "quién factura, primero hay que reabrirla." % tercero)
        if recibo is None and not reparto:
            return None
        recibo = recibo or self._recibo_o_nuevo(quincena, tercero)
        self._poner_reparto(recibo, reparto)
        self.db.commit()
        return recibo

    # ─── La factura ─────────────────────────────────────────────────────────

    def registrar_factura(self, quincena: date, tercero: str, numero: str,
                          fecha: date | None, importe, usuario_id: int | None = None,
                          empresa: str | None = None) -> Recibo:
        """La factura que mandó el tercero para una empresa. Registrar de nuevo
        reemplaza la anterior: es lo que pasa cuando una se rechaza y llega la
        corregida. Con una sola empresa no hace falta decir cuál."""
        recibo = self._emitido(quincena, tercero)
        factura = self._factura_de(recibo, empresa)
        numero = (numero or "").strip()
        if not numero:
            raise ReciboInvalido("La factura necesita su número.")
        if importe in (None, ""):
            raise ReciboInvalido("La factura necesita su importe.")
        if factura.estado == FACTURA_APROBADA:
            raise ReciboInvalido("La factura de %s ya está aprobada." % factura.empresa)

        factura.numero = numero
        factura.fecha = fecha
        factura.importe_factura = _dec(importe)
        factura.estado = FACTURA_RECIBIDA
        factura.motivo = None
        self._evento(recibo, "FACTURA", usuario_id, detalle={
            "empresa": factura.empresa, "numero": numero,
            "importe": str(factura.importe_factura), "coincide": self._coincide(factura)})
        self.db.commit()
        return recibo

    def aprobar_factura(self, quincena: date, tercero: str,
                        usuario_id: int | None = None, empresa: str | None = None) -> Recibo:
        """Se aprueba aunque el importe no coincida: puede haber razones, y la
        decisión es de quien la revisa. La pantalla avisa la diferencia."""
        recibo, factura = self._con_factura(quincena, tercero, empresa)
        factura.estado = FACTURA_APROBADA
        factura.motivo = None
        self._evento(recibo, "APROBADA", usuario_id, detalle={
            "empresa": factura.empresa, "coincide": self._coincide(factura)})
        self.db.commit()
        return recibo

    def rechazar_factura(self, quincena: date, tercero: str, motivo: str,
                         usuario_id: int | None = None, empresa: str | None = None) -> Recibo:
        recibo, factura = self._con_factura(quincena, tercero, empresa)
        motivo = (motivo or "").strip()
        if not motivo:
            raise ReciboInvalido(
                "Rechazar una factura pide el motivo: es lo que el tercero tiene "
                "que corregir.")
        factura.estado = FACTURA_RECHAZADA
        factura.motivo = motivo
        self._evento(recibo, "RECHAZADA", usuario_id, motivo=motivo,
                     detalle={"empresa": factura.empresa})
        self.db.commit()
        return recibo

    # ─── El pago ────────────────────────────────────────────────────────────

    def registrar_pago(self, quincena: date, tercero: str, tipo: str | None,
                       importe=None, fecha: date | None = None,
                       usuario_id: int | None = None) -> Recibo:
        """Entero o parcial. `tipo` en None saca el pago.

        Entero es todo lo que se le debía a esta quincena, saldo anterior
        incluido, y se guarda el número: si no, el saldo dependería de cuándo
        se lo mire.
        """
        recibo = self._emitido(quincena, tercero)
        # Un pago posterior ya cuenta lo que se debía hasta acá: el entero de la
        # 2da incluye lo que quedó de la 1ra. Tocar un pago anterior después
        # contaría dos veces la misma deuda, a favor o en contra del tercero.
        posterior = (self.db.query(Recibo.quincena)
                     .filter(Recibo.tercero == tercero, Recibo.quincena > quincena,
                             Recibo.pago.isnot(None))
                     .order_by(Recibo.quincena).first())
        if posterior is not None:
            raise ReciboInvalido(
                "%s ya tiene registrado el pago de %s, que cuenta lo que se debía "
                "hasta acá. Para tocar este, primero hay que sacar ese."
                % (tercero, quincenas.nombre(posterior[0])))

        if tipo is None:
            recibo.pago = recibo.pago_importe = recibo.pago_fecha = None
            self._evento(recibo, "PAGO", usuario_id, detalle={"pago": "sacado"})
            self.db.commit()
            return recibo

        if tipo == PAGO_TOTAL:
            monto = self.saldo_anterior(quincena, tercero) + _dec(recibo.total_a_pagar)
        elif tipo == PAGO_PARCIAL:
            if importe in (None, "") or _dec(importe) == CERO:
                raise ReciboInvalido("Un pago parcial necesita el importe que se pagó.")
            monto = _dec(importe)
        else:
            raise ReciboInvalido("El pago es TOTAL o PARCIAL.")

        recibo.pago = tipo
        recibo.pago_importe = monto
        recibo.pago_fecha = fecha or date.today()
        self._evento(recibo, "PAGO", usuario_id,
                     detalle={"pago": tipo, "importe": str(monto)})
        self.db.commit()
        return recibo

    def marcar_revision(self, quincena: date, tercero: str, en_revision: bool,
                        motivo: str | None = None, usuario_id: int | None = None) -> Recibo:
        recibo = self._emitido(quincena, tercero)
        motivo = (motivo or "").strip()
        if en_revision and not motivo:
            raise ReciboInvalido(
                "Poner una quincena en revisión pide el motivo: es lo que está "
                "en discusión con el tercero.")
        recibo.en_revision = en_revision
        recibo.motivo_revision = motivo if en_revision else None
        self._evento(recibo, "REVISION", usuario_id, motivo=motivo or None,
                     detalle={"en_revision": en_revision})
        self.db.commit()
        return recibo

    # ─── Los ajustes ────────────────────────────────────────────────────────

    def ajustes_de(self, quincena: date, tercero: str) -> list[Ajuste]:
        return (self.db.query(Ajuste)
                .filter(Ajuste.quincena == quincena, Ajuste.tercero == tercero)
                .order_by(Ajuste.id).all())

    def crear_ajuste(self, quincena: date, tercero: str, concepto: str, importe,
                     motivo: str, quincena_origen: date | None = None,
                     origen_clave: str | None = None,
                     usuario_id: int | None = None) -> Ajuste:
        """Una corrección con signo sobre el recibo abierto del tercero."""
        tercero = (tercero or "").strip()
        if not tercero:
            raise ReciboInvalido("Falta el tercero.")
        if not quincenas.es_inicio_valido(quincena):
            raise ReciboInvalido("Una quincena se identifica por su primer día: el 1 o el 16.")
        if self.db.query(Liquidacion).filter(Liquidacion.quincena == quincena).first() is None:
            raise ReciboInvalido("Esa quincena no está generada.")
        self._abierto(quincena, tercero)
        ajuste = Ajuste(quincena=quincena, tercero=tercero, creado_por=usuario_id)
        self._completar_ajuste(ajuste, concepto, importe, motivo, quincena_origen)
        ajuste.origen_clave = (origen_clave or "").strip() or None
        self.db.add(ajuste)
        self.db.flush()
        self._evento(self._recibo_o_nuevo(quincena, tercero), "AJUSTE", usuario_id,
                     motivo=ajuste.motivo, detalle={
                         "concepto": ajuste.concepto, "importe": str(ajuste.importe)})
        self.db.commit()
        return ajuste

    def editar_ajuste(self, id_: int, concepto: str, importe, motivo: str,
                      quincena_origen: date | None = None,
                      usuario_id: int | None = None) -> Ajuste:
        ajuste = self._ajuste(id_)
        self._abierto(ajuste.quincena, ajuste.tercero)
        antes = str(ajuste.importe)
        self._completar_ajuste(ajuste, concepto, importe, motivo, quincena_origen)
        self._evento(self._recibo_o_nuevo(ajuste.quincena, ajuste.tercero), "AJUSTE",
                     usuario_id, motivo=ajuste.motivo, detalle={
                         "concepto": ajuste.concepto, "antes": antes,
                         "importe": str(ajuste.importe)})
        self.db.commit()
        return ajuste

    def borrar_ajuste(self, id_: int, usuario_id: int | None = None) -> None:
        ajuste = self._ajuste(id_)
        self._abierto(ajuste.quincena, ajuste.tercero)
        self._evento(self._recibo_o_nuevo(ajuste.quincena, ajuste.tercero), "AJUSTE",
                     usuario_id, motivo=ajuste.motivo, detalle={
                         "concepto": ajuste.concepto, "borrado": str(ajuste.importe)})
        self.db.delete(ajuste)
        self.db.commit()

    # ─── Lo que llegó tarde ─────────────────────────────────────────────────

    def tiene_emitidos(self, quincena: date) -> bool:
        return (self.db.query(Recibo.id)
                .filter(Recibo.quincena == quincena, Recibo.emitido_en.isnot(None))
                .first() is not None)

    def llegadas(self, quincena: date, tercero: str | None = None) -> dict[str, list[dict]]:
        """Lo que cambió en recibos ya emitidos de quincenas anteriores, para
        proponerlo en el recibo abierto de `quincena`.

        Un tercero cuyo recibo de esta quincena ya se emitió no aparece: lo
        suyo se va a proponer en el recibo siguiente.
        """
        consulta = (self.db.query(Recibo)
                    .filter(Recibo.quincena < quincena, Recibo.emitido_en.isnot(None)))
        if tercero:
            consulta = consulta.filter(Recibo.tercero == tercero)
        cerrados = {t for (t,) in (self.db.query(Recibo.tercero)
                                   .filter(Recibo.quincena == quincena,
                                           Recibo.emitido_en.isnot(None)).all())}
        por_quincena = defaultdict(list)
        for r in consulta.all():
            if r.tercero not in cerrados:
                por_quincena[r.quincena].append(r)

        salida = defaultdict(list)
        for origen in sorted(por_quincena):
            recibos = por_quincena[origen]
            # Si nada que se liquida en esa quincena se tocó después de emitir,
            # la foto y lo de hoy son lo mismo y no hace falta armarla.
            tocada = self._tocada_en(origen)
            recibos = [r for r in recibos if tocada and tocada >= r.emitido_en]
            if not recibos:
                continue
            hoy = defaultdict(dict)
            for linea in GrillaService(self.db).lineas(origen):
                if linea["tercero"] and linea["concepto"] != "seguros" and _cobrable(linea):
                    hoy[linea["tercero"]][clave_linea(linea)] = linea
            for r in recibos:
                salida[r.tercero] += self._diferencias(
                    r, _lineas_de_la_foto(r), hoy.get(r.tercero, {}))
        return dict(salida)

    def descartar_llegada(self, quincena_origen: date, tercero: str, clave: str,
                          motivo: str, usuario_id: int | None = None) -> None:
        """Dejar como está algo que llegó tarde. Pide motivo y deja de avisar."""
        motivo = (motivo or "").strip()
        if not motivo:
            raise ReciboInvalido("Descartar pide el motivo: es lo que explica por "
                                 "qué no se movió ni se ajustó.")
        recibo = self._emitido(quincena_origen, tercero)
        existe = (self.db.query(LlegadaDescartada)
                  .filter(LlegadaDescartada.quincena == quincena_origen,
                          LlegadaDescartada.tercero == tercero,
                          LlegadaDescartada.clave == clave).first())
        if existe is None:
            self.db.add(LlegadaDescartada(quincena=quincena_origen, tercero=tercero,
                                          clave=clave, motivo=motivo,
                                          creado_por=usuario_id))
        self._evento(recibo, "DESCARTADA", usuario_id, motivo=motivo,
                     detalle={"clave": clave})
        self.db.commit()

    # ─── El saldo inicial ───────────────────────────────────────────────────

    def listar_saldos_iniciales(self) -> list[SaldoInicial]:
        return self.db.query(SaldoInicial).order_by(SaldoInicial.tercero).all()

    def cargar_saldo_inicial(self, tercero: str, quincena: date, importe,
                             motivo: str | None = None,
                             usuario_id: int | None = None) -> SaldoInicial:
        """Uno por tercero. Cargarlo de nuevo lo corrige, mientras ningún
        recibo desde esa quincena se haya emitido: después ya se le informó un
        saldo que salía de este número."""
        tercero = (tercero or "").strip()
        if not tercero:
            raise ReciboInvalido("Falta el tercero.")
        emitido = (self.db.query(Recibo.id)
                   .filter(Recibo.tercero == tercero, Recibo.quincena >= quincena,
                           Recibo.emitido_en.isnot(None)).first())
        if emitido is not None:
            raise ReciboInvalido(
                "%s ya tiene órdenes de facturación emitidas desde esa quincena: "
                "el saldo inicial ya se usó. Reabrilas antes de cambiarlo." % tercero)

        saldo = self.db.query(SaldoInicial).filter(SaldoInicial.tercero == tercero).first()
        if saldo is None:
            saldo = SaldoInicial(tercero=tercero)
            self.db.add(saldo)
        saldo.quincena = quincena
        saldo.importe = _dec(importe)
        saldo.motivo = (motivo or "").strip() or None
        saldo.creado_por = usuario_id
        self.db.commit()
        return saldo

    # ─── Interno ────────────────────────────────────────────────────────────

    def _en_vivo(self, quincena: date, tercero: str) -> dict:
        lineas = [f for f in GrillaService(self.db).lineas(quincena)
                  if f["tercero"] == tercero]
        return armar(lineas, self.saldo_anterior(quincena, tercero))

    def _saldos_anteriores(self, quincena: date, terceros: set[str]) -> dict:
        if not terceros:
            return {}
        iniciales = {s.tercero: s for s in (self.db.query(SaldoInicial)
                                           .filter(SaldoInicial.tercero.in_(terceros)).all())}
        saldos = {t: (_dec(s.importe) if s.quincena <= quincena else CERO)
                  for t, s in iniciales.items()}
        previos = (self.db.query(Recibo)
                   .filter(Recibo.tercero.in_(terceros), Recibo.quincena < quincena,
                           Recibo.emitido_en.isnot(None),
                           Recibo.en_revision.is_(False)).all())
        for r in previos:
            inicial = iniciales.get(r.tercero)
            # Lo de antes del saldo inicial ya está adentro de ese número.
            if inicial is not None and r.quincena < inicial.quincena:
                continue
            saldos[r.tercero] = (saldos.get(r.tercero, CERO)
                                 + _dec(r.total_a_pagar) - _dec(r.pago_importe))
        return saldos

    @staticmethod
    def _esta_emitido(recibo: Recibo | None) -> bool:
        return recibo is not None and recibo.emitido_en is not None

    @staticmethod
    def _foto(recibo: Recibo, vivo: dict) -> dict:
        """Lo que dice el recibo emitido, más cuánto daría hoy en vivo."""
        return {
            "contenido": recibo.contenido,
            "total_a_facturar": recibo.total_a_facturar,
            "seguros": recibo.seguros,
            "total_a_pagar": recibo.total_a_pagar,
            "saldo_anterior": recibo.saldo_anterior,
            "total": _dec(recibo.total_a_pagar) + _dec(recibo.saldo_anterior),
            "pendientes": 0,
            "vivo": vivo["total_a_pagar"],
        }

    def _renglon(self, tercero: str, quincena: date, datos: dict,
                 recibo: Recibo | None) -> dict:
        emitido = self._esta_emitido(recibo)
        salida = {
            "quincena": quincena, "tercero": tercero,
            "emitido": emitido,
            "emitido_en": recibo.emitido_en if recibo else None,
            "facturas": [self._factura_a_dict(f, datos["total_a_facturar"], recibo)
                         for f in (recibo.facturas if recibo else [])],
            "total_a_facturar": datos["total_a_facturar"],
            "seguros": datos["seguros"],
            "total_a_pagar": datos["total_a_pagar"],
            "saldo_anterior": datos["saldo_anterior"],
            "total": datos["total"],
            "pendientes": datos["pendientes"],
            "en_revision": bool(recibo.en_revision) if recibo else False,
            "motivo_revision": recibo.motivo_revision if recibo else None,
            "pago": recibo.pago if recibo else None,
            "pago_importe": recibo.pago_importe if recibo else None,
            "pago_fecha": recibo.pago_fecha if recibo else None,
        }
        # Lo que cambió en vivo desde la emisión: hechos que llegaron tarde o
        # se corrigieron en el origen. No toca el recibo; avisa.
        salida["cambio_desde_emision"] = None
        if emitido and "vivo" in datos:
            salida["cambio_desde_emision"] = datos["vivo"] - _dec(recibo.total_a_pagar)
        return salida

    def _diferencias(self, recibo: Recibo, foto: dict, hoy: dict) -> list[dict]:
        """Lo que no coincide entre la foto de un recibo y lo de hoy, menos lo
        que ya se ajustó o se descartó."""
        origen, tercero = recibo.quincena, recibo.tercero
        descartadas = {c for (c,) in (self.db.query(LlegadaDescartada.clave)
                                      .filter(LlegadaDescartada.quincena == origen,
                                              LlegadaDescartada.tercero == tercero).all())}
        # Lo ajustado por cada línea, en cualquier recibo posterior: así un
        # ajuste parcial deja el resto pendiente, y uno completo lo resuelve.
        ajustado = defaultdict(lambda: CERO)
        for clave, importe in (self.db.query(Ajuste.origen_clave, Ajuste.importe)
                               .filter(Ajuste.quincena_origen == origen,
                                       Ajuste.tercero == tercero,
                                       Ajuste.origen_clave.isnot(None)).all()):
            ajustado[clave] += _dec(importe)

        def item(tipo, linea, diferencia):
            se_mueve = (tipo == "llego" and linea["concepto"] in CONCEPTOS
                        and not linea.get("cuota"))
            return {
                "quincena_origen": origen, "tercero": tercero,
                "clave": clave_linea(linea), "tipo": tipo,
                "propuesta": "mover" if se_mueve else "ajuste",
                "concepto": linea["concepto"],
                "concepto_label": linea.get("concepto_label") or linea["concepto"],
                "id": int(linea["id"]), "cuota": linea.get("cuota"),
                "diferencia": diferencia,
                "linea": {k: _serializable(v) for k, v in linea.items()},
            }

        salida = []
        for clave in sorted(set(foto) | set(hoy)):
            if clave in descartadas:
                continue
            antes, ahora = foto.get(clave), hoy.get(clave)
            if antes is None:
                tipo, diferencia, linea = "llego", _efecto(ahora), ahora
            elif ahora is None:
                tipo, diferencia, linea = "desaparecio", -_efecto(antes), antes
            else:
                tipo, diferencia, linea = "cambio", _efecto(ahora) - _efecto(antes), ahora
            diferencia -= ajustado.get(clave, CERO)
            if abs(diferencia) < UN_CENTAVO:
                continue
            salida.append(item(tipo, linea, diferencia))
        return salida

    def _tocada_en(self, quincena: date):
        """La última vez que se actualizó o se recalculó algo que se liquida en
        esa quincena: la suya, y las de los hechos que se movieron hasta ella."""
        ids = {i for (i,) in (self.db.query(Liquidacion.id)
                              .filter(Liquidacion.quincena == quincena).all())}
        for conf in CONCEPTOS.values():
            modelo = conf["modelo"]
            ids |= {i for (i,) in (self.db.query(modelo.liquidacion_id)
                                   .filter(modelo.quincena_efectiva == quincena)
                                   .distinct().all())}
        ids |= {i for (i,) in (self.db.query(Repuesto.liquidacion_id)
                               .join(CuotaRepuesto, CuotaRepuesto.repuesto_id == Repuesto.id)
                               .filter(CuotaRepuesto.quincena == quincena)
                               .distinct().all())}
        if not ids:
            return None
        momentos = [t for liq in self.db.query(Liquidacion).filter(Liquidacion.id.in_(ids))
                    for t in (liq.generada_en, liq.actualizada_en, liq.calculada_en) if t]
        return max(momentos) if momentos else None

    def _abierto(self, quincena: date, tercero: str) -> None:
        recibo = self._recibo(quincena, tercero)
        if self._esta_emitido(recibo):
            raise ReciboInvalido(
                "La orden de facturación de %s de %s ya está emitida. Los "
                "ajustes van en la orden abierta." % (tercero, quincenas.nombre(quincena)))

    def _recibo_o_nuevo(self, quincena: date, tercero: str) -> Recibo:
        """El recibo de la quincena, aunque todavía no se haya emitido: lo que
        se le hace antes de emitir también queda en su historia."""
        recibo = self._recibo(quincena, tercero)
        if recibo is None:
            recibo = Recibo(quincena=quincena, tercero=tercero)
            self.db.add(recibo)
            self.db.flush()
        return recibo

    def _ajuste(self, id_: int) -> Ajuste:
        ajuste = self.db.get(Ajuste, id_)
        if ajuste is None:
            raise ReciboInvalido("No existe ese ajuste.")
        return ajuste

    @staticmethod
    def _completar_ajuste(ajuste: Ajuste, concepto: str, importe, motivo: str,
                          quincena_origen: date | None) -> None:
        if concepto not in AJUSTE_CONCEPTOS:
            raise ReciboInvalido("El concepto del ajuste tiene que ser uno de: %s."
                                 % ", ".join(AJUSTE_CONCEPTOS))
        if importe in (None, "") or _dec(importe) == CERO:
            raise ReciboInvalido("Un ajuste necesita un importe distinto de cero.")
        motivo = (motivo or "").strip()
        if not motivo:
            raise ReciboInvalido("Un ajuste pide el motivo: es lo que el tercero "
                                 "lee en la orden de facturación.")
        if quincena_origen is not None:
            if not quincenas.es_inicio_valido(quincena_origen):
                raise ReciboInvalido("La quincena de origen se identifica por su "
                                     "primer día: el 1 o el 16.")
            if quincena_origen >= ajuste.quincena:
                raise ReciboInvalido("La quincena de origen tiene que ser anterior "
                                     "a la de la orden de facturación.")
        ajuste.concepto = concepto
        ajuste.importe = _dec(importe)
        ajuste.motivo = motivo
        ajuste.quincena_origen = quincena_origen

    @staticmethod
    def _ajuste_a_dict(a: Ajuste) -> dict:
        return {"id": a.id, "concepto": a.concepto, "importe": a.importe,
                "motivo": a.motivo, "quincena_origen": a.quincena_origen,
                "origen_clave": a.origen_clave}

    def _recibo(self, quincena: date, tercero: str) -> Recibo | None:
        return (self.db.query(Recibo)
                .filter(Recibo.quincena == quincena, Recibo.tercero == tercero).first())

    def _emitido(self, quincena: date, tercero: str) -> Recibo:
        recibo = self._recibo(quincena, tercero)
        if recibo is None or recibo.emitido_en is None:
            raise ReciboInvalido(
                "La orden de facturación de %s no está emitida." % tercero)
        return recibo

    def _con_factura(self, quincena: date, tercero: str,
                     empresa: str | None) -> tuple[Recibo, ReciboFactura]:
        recibo = self._emitido(quincena, tercero)
        factura = self._factura_de(recibo, empresa)
        if factura.estado is None:
            raise ReciboInvalido(
                "Todavía no se registró la factura de %s." % factura.empresa)
        return recibo, factura

    @staticmethod
    def _factura_de(recibo: Recibo, empresa: str | None) -> ReciboFactura:
        """La de esa empresa. Con una sola, no hace falta nombrarla."""
        if empresa is None:
            if len(recibo.facturas) == 1:
                return recibo.facturas[0]
            raise ReciboInvalido(
                "Esta orden se factura a %s: falta decir de cuál es la factura."
                % " y ".join(f.empresa for f in recibo.facturas))
        for factura in recibo.facturas:
            if factura.empresa == empresa:
                return factura
        raise ReciboInvalido("Esta orden no se le factura a %s." % empresa)

    def _poner_reparto(self, recibo: Recibo,
                       reparto: list[tuple[str, Decimal | None]]) -> None:
        """Deja en el recibo exactamente esas empresas, en el orden en que se
        eligieron: es el que se imprime. La factura que ya tenía cargada una
        empresa se conserva: cambiarle el importe no la borra."""
        anteriores = {f.empresa: f for f in recibo.facturas}
        nuevas = []
        for empresa, importe in reparto:
            nueva = ReciboFactura(empresa=empresa, importe=importe)
            vieja = anteriores.get(empresa)
            if vieja is not None:
                for campo in ("numero", "fecha", "importe_factura", "estado", "motivo"):
                    setattr(nueva, campo, getattr(vieja, campo))
            nuevas.append(nueva)
        # Primero se borran las de antes: la nueva de una empresa que ya estaba
        # chocaría con la vieja en el índice único.
        recibo.facturas = []
        self.db.flush()
        recibo.facturas = nuevas

    @staticmethod
    def _validar_reparto(recibo: Recibo, tercero: str, total_a_facturar) -> None:
        if not recibo.facturas:
            raise ReciboInvalido("Falta elegir a qué empresa le factura %s." % tercero)
        if len(recibo.facturas) == 1:
            return
        suma = sum((_dec(f.importe) for f in recibo.facturas), CERO)
        if suma != _dec(total_a_facturar):
            raise ReciboInvalido(
                "A %s se le reparte %s entre las empresas y el Total a facturar es "
                "%s: tienen que dar lo mismo."
                % (tercero, _pesos(suma), _pesos(total_a_facturar)))

    @classmethod
    def _factura_a_dict(cls, factura: ReciboFactura, total_a_facturar,
                        recibo: Recibo) -> dict:
        # Con una sola empresa y la orden abierta, lo que se le factura es el
        # Total a facturar de hoy: se muestra ése y no un vacío.
        importe = factura.importe
        if importe is None and len(recibo.facturas) == 1:
            importe = total_a_facturar
        return {"empresa": factura.empresa, "importe": importe,
                "numero": factura.numero, "fecha": factura.fecha,
                "importe_factura": factura.importe_factura, "estado": factura.estado,
                "motivo": factura.motivo, "coincide": cls._coincide(factura)}

    @staticmethod
    def _coincide(factura: ReciboFactura) -> bool | None:
        """Si la factura dice lo mismo que lo que se le factura a esa empresa,
        al peso."""
        if factura.importe_factura is None or factura.importe is None:
            return None
        return abs(_dec(factura.importe_factura) - _dec(factura.importe)) < Decimal("1")

    def _evento(self, recibo: Recibo, tipo: str, usuario_id: int | None,
                motivo: str | None = None, detalle: dict | None = None) -> None:
        self.db.add(ReciboEvento(recibo=recibo, tipo=tipo, motivo=motivo,
                                 detalle=detalle, creado_por=usuario_id))

    @staticmethod
    def _evento_a_dict(e: ReciboEvento) -> dict:
        return {"tipo": e.tipo, "motivo": e.motivo, "detalle": e.detalle,
                "creado_en": e.creado_en, "creado_por": e.creado_por}
