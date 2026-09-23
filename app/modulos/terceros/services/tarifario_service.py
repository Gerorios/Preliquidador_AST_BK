"""El Tarifario: los precios que se pactan con cada tercero, por quincena.

Etapa 6 del plan. Cinco tablas, una por cada cosa que se paga o se descuenta.
Ninguna se deriva de los datos — cada precio es una negociación, no un cálculo.

Dos cosas que hacen que esto no sea un ABM cualquiera:

  - **Copiar desde otra quincena.** El flujo real es cargar los precios una vez
    y después traerlos de la quincena que se elija. Lo copiado entra marcado
    como **heredado**: paga igual, pero queda resaltado hasta que alguien lo
    confirme, para no arrastrar un precio viejo sin darse cuenta si hubo
    aumento. Es el mismo criterio del ADR-0004 de Preliquidación.

  - **Las dimensiones vacías son `''` y no `NULL`.** Así el índice único de la
    base impide cargar dos reglas idénticas, que es el empate que el módulo no
    sabe resolver. La regla más específica es la que tiene más dimensiones
    distintas de `''`.
"""
from datetime import date
from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import Session

from app.modulos.terceros.models import (
    SIN_DIMENSION, TIPOS_SEGURO, TIPOS_VIAJE, UNIDADES_BASE,
    PrecioCombustible, PrecioReparacion, PrecioSeguro,
    TarifaServicio, TarifaViaje,
)


class TarifaInvalida(ValueError):
    """Lo que se quiso cargar no es una tarifa válida. El mensaje lo lee una
    persona, así que dice qué falta y no qué constraint se violó."""


# Cada tipo declara su tabla, sus dimensiones, qué campos propios tiene y
# cuáles de esas dimensiones son obligatorias. El resto del servicio es uno
# solo y sirve para los cinco.
TIPOS = {
    "viajes": {
        "modelo": TarifaViaje,
        "dimensiones": ("tercero", "cliente", "finca", "capataz"),
        "obligatorias": (),          # una regla puede no discriminar por nada
        "valores": ("precio", "tipo_viaje"),
        "importe": "precio",
        "etiqueta": "tarifa de viaje",
    },
    "servicio": {
        "modelo": TarifaServicio,
        "dimensiones": ("tercero", "cliente", "finca", "tarea"),
        "obligatorias": (),
        "valores": ("precio", "unidad_base"),
        "importe": "precio",
        "etiqueta": "tarifa de servicio",
    },
    "combustible": {
        "modelo": PrecioCombustible,
        "dimensiones": ("tercero",),
        "obligatorias": ("tercero",),
        "valores": ("precio",),
        "importe": "precio",
        "etiqueta": "precio del combustible",
    },
    "reparacion": {
        "modelo": PrecioReparacion,
        "dimensiones": ("tercero",),
        "obligatorias": ("tercero",),
        "valores": ("precio",),
        "importe": "precio",
        "etiqueta": "precio de la hora de reparación",
    },
    "seguros": {
        "modelo": PrecioSeguro,
        # El sujeto puede ser una máquina o una persona: el tipo dice cuál.
        "dimensiones": ("tercero", "tipo_seguro", "sujeto"),
        "obligatorias": ("tercero", "tipo_seguro", "sujeto"),
        "valores": ("importe", "referencia"),
        "importe": "importe",
        "etiqueta": "precio del seguro",
    },
}


def tipo_o_error(tipo: str) -> dict:
    if tipo not in TIPOS:
        raise TarifaInvalida(
            "No existe un tarifario de «%s». Los que hay: %s."
            % (tipo, ", ".join(sorted(TIPOS)))
        )
    return TIPOS[tipo]


def _texto(v) -> str:
    return (str(v).strip() if v is not None else SIN_DIMENSION)


def _monto(v, etiqueta: str) -> Decimal:
    try:
        monto = Decimal(str(v))
    except (InvalidOperation, TypeError, ValueError):
        raise TarifaInvalida("El %s tiene que ser un número." % etiqueta)
    if monto < 0:
        raise TarifaInvalida("El %s no puede ser negativo." % etiqueta)
    return monto


def especificidad(fila) -> int:
    """Cuántas dimensiones tiene cargadas. Es lo que decide qué regla gana."""
    return sum(1 for d in fila.DIMENSIONES if getattr(fila, d, SIN_DIMENSION))


class TarifarioService:
    def __init__(self, db: Session):
        self.db = db

    # ─── Leer ───────────────────────────────────────────────────────────────

    def listar(self, tipo: str, quincena: date) -> list:
        conf = tipo_o_error(tipo)
        modelo = conf["modelo"]
        filas = (self.db.query(modelo)
                 .filter(modelo.quincena == quincena)
                 .order_by(*[getattr(modelo, d) for d in conf["dimensiones"]])
                 .all())
        # De la más general a la más específica: es como se leen las excepciones.
        return sorted(filas, key=especificidad)

    def resumen(self, quincena: date) -> dict:
        """Cuántas reglas tiene cada tabla y cuántas están sin confirmar."""
        salida = {}
        for tipo, conf in TIPOS.items():
            modelo = conf["modelo"]
            base = self.db.query(modelo).filter(modelo.quincena == quincena)
            salida[tipo] = {
                "cargadas": base.count(),
                "heredadas": base.filter(modelo.heredada.is_(True)).count(),
            }
        return salida

    # ─── Escribir ───────────────────────────────────────────────────────────

    def crear(self, tipo: str, quincena: date, datos: dict, usuario_id: int | None = None):
        conf = tipo_o_error(tipo)
        valores = self._validar(conf, datos)

        if self._buscar_igual(conf, quincena, valores):
            raise TarifaInvalida(
                "Ya hay una %s para esa combinación en esta quincena. "
                "Editá la que está en vez de crear otra: dos reglas iguales "
                "dejarían el precio ambiguo." % conf["etiqueta"]
            )

        fila = conf["modelo"](quincena=quincena, heredada=False,
                              creado_por=usuario_id, **valores)
        self.db.add(fila)
        self.db.commit()
        self.db.refresh(fila)
        return fila

    def actualizar(self, tipo: str, id_: int, datos: dict):
        """Cambiar un precio **confirma la regla**: si estaba heredada deja de
        estarlo, porque alguien la miró y decidió."""
        conf = tipo_o_error(tipo)
        fila = self._obtener(conf, id_)
        for campo in conf["valores"]:
            if campo in datos:
                setattr(fila, campo, self._validar_valor(conf, campo, datos[campo]))
        fila.heredada = False
        self.db.commit()
        self.db.refresh(fila)
        return fila

    def confirmar(self, tipo: str, id_: int):
        """Dejar el precio como está, pero dicho por una persona."""
        conf = tipo_o_error(tipo)
        fila = self._obtener(conf, id_)
        fila.heredada = False
        self.db.commit()
        self.db.refresh(fila)
        return fila

    def quincena_de(self, tipo: str, id_: int) -> date:
        """De qué quincena es esa tarifa. Hace falta antes de borrarla, para
        saber qué hay que recalcular una vez que ya no esté."""
        return self._obtener(tipo_o_error(tipo), id_).quincena

    def eliminar(self, tipo: str, id_: int) -> None:
        conf = tipo_o_error(tipo)
        self.db.delete(self._obtener(conf, id_))
        self.db.commit()

    # ─── Copiar de otra quincena ────────────────────────────────────────────

    def copiar(self, desde: date, hasta: date, tipos: tuple[str, ...] | None = None) -> dict:
        """Trae las reglas de otra quincena, marcadas como heredadas.

        Lo que ya existe en el destino **no se toca**: copiar es traer lo que
        falta, nunca pisar lo que alguien ya cargó a mano para esta quincena.
        """
        if desde == hasta:
            raise TarifaInvalida("El origen y el destino son la misma quincena.")

        detalle = {}
        for tipo in (tipos or tuple(TIPOS)):
            conf = tipo_o_error(tipo)
            modelo, dimensiones = conf["modelo"], conf["dimensiones"]

            existentes = {
                tuple(getattr(f, d) for d in dimensiones)
                for f in self.db.query(modelo).filter(modelo.quincena == hasta).all()
            }
            origen = self.db.query(modelo).filter(modelo.quincena == desde).all()

            nuevas = []
            for f in origen:
                clave = tuple(getattr(f, d) for d in dimensiones)
                if clave in existentes:
                    continue
                datos = {d: getattr(f, d) for d in dimensiones}
                datos.update({c: getattr(f, c) for c in conf["valores"]})
                nuevas.append({"quincena": hasta, "heredada": True,
                               "creado_por": f.creado_por, **datos})
            if nuevas:
                self.db.bulk_insert_mappings(modelo, nuevas)
            detalle[tipo] = {
                "en_origen": len(origen),
                "copiadas": len(nuevas),
                "ya_estaban": len(origen) - len(nuevas),
            }
        self.db.commit()
        return detalle

    # ─── Interno ────────────────────────────────────────────────────────────

    def _obtener(self, conf: dict, id_: int):
        fila = self.db.query(conf["modelo"]).filter(conf["modelo"].id == id_).first()
        if fila is None:
            raise TarifaInvalida("No existe esa %s." % conf["etiqueta"])
        return fila

    def _buscar_igual(self, conf: dict, quincena: date, valores: dict):
        modelo = conf["modelo"]
        consulta = self.db.query(modelo).filter(modelo.quincena == quincena)
        for d in conf["dimensiones"]:
            consulta = consulta.filter(getattr(modelo, d) == valores[d])
        return consulta.first()

    def _validar(self, conf: dict, datos: dict) -> dict:
        valores = {}
        for d in conf["dimensiones"]:
            texto = _texto(datos.get(d))
            if d == "tipo_seguro" and texto and texto not in TIPOS_SEGURO:
                raise TarifaInvalida(
                    "El tipo de seguro tiene que ser uno de %s: dice si la póliza "
                    "cubre una máquina o a una persona." % ", ".join(TIPOS_SEGURO))
            if not texto and d in conf["obligatorias"]:
                raise TarifaInvalida(
                    "Falta %s: sin eso no se sabe a quién se le aplica este %s."
                    % (d, conf["etiqueta"])
                )
            valores[d] = texto
        for campo in conf["valores"]:
            valores[campo] = self._validar_valor(conf, campo, datos.get(campo))
        return valores

    def _validar_valor(self, conf: dict, campo: str, valor):
        if campo in ("precio", "importe"):
            return _monto(valor, conf["etiqueta"])
        if campo == "unidad_base":
            if valor not in UNIDADES_BASE:
                raise TarifaInvalida(
                    "La unidad base tiene que ser una de %s: dice sobre qué se "
                    "calcula el precio, por hora de máquina o por cantidad."
                    % ", ".join(UNIDADES_BASE)
                )
            return valor
        if campo == "referencia":
            return _texto(valor) or None
        if campo == "tipo_seguro":
            if valor not in TIPOS_SEGURO:
                raise TarifaInvalida(
                    "El tipo de seguro tiene que ser uno de %s: dice si la póliza "
                    "cubre una máquina o a una persona." % ", ".join(TIPOS_SEGURO))
            return valor
        if campo == "tipo_viaje":
            if valor in (None, ""):
                return None
            if valor not in TIPOS_VIAJE:
                raise TarifaInvalida(
                    "El tipo de viaje tiene que ser %s." % " o ".join(TIPOS_VIAJE))
            return valor
        return valor
