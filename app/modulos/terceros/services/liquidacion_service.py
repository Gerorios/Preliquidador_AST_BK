"""Generar y actualizar la quincena: traer las cinco fuentes y guardarlas.

Etapa 5 del plan. Hasta acá el módulo leía los orígenes en vivo en cada request;
desde acá los lee una vez, al generar, y las pantallas leen lo guardado.

**Generar no congela nada.** Es una foto que se puede volver a sacar mientras el
recibo no se haya emitido. Lo que congela es la Emisión, que es por Tercero y
llega en la etapa 11.

Actualizar no borra y vuelve a cargar: **reconcilia por clave**, que es el mismo
mecanismo que usa Preliquidación al regenerar una quincena. Por cada conjunto:

  1. Arma una clave con los datos propios del hecho (fecha, máquina, cantidad…).
  2. Cuenta cuántas filas tiene el origen por clave y cuántas tiene la base.
  3. Si sobran en la base, borra — sacrificando **primero las que no tienen
     trabajo manual**. Las que tienen quincena efectiva con motivo, o marca de
     no cobrar, se protegen y se borran últimas.
  4. Si faltan, inserta sólo las nuevas.

Así se puede actualizar diez veces sin perder lo que el liquidador cargó a mano.

Un caso que conviene conocer: si alguien **edita** un hecho en el origen —le
cambia la finca a un viaje, por ejemplo— su clave cambia, así que acá se ve como
"desapareció uno y apareció otro". Es el comportamiento correcto, pero si esa
fila tenía trabajo manual encima, ese trabajo se pierde.
"""
from collections import defaultdict
from datetime import date, datetime

from sqlalchemy.orm import Session

from app.modulos.terceros.models import (
    CargaCombustible, CuotaRepuesto, HoraReparacion, HoraServicio, Liquidacion,
    PrecioSeguro, Repuesto, TarifaServicio, Viaje,
)
from app.modulos.terceros.services.consulta_externa import nombre_de_maquina


def _fecha(valor) -> date | None:
    """Los orígenes no tipan parejo: unos devuelven date y otros texto ISO."""
    if valor is None or valor == "":
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    return date.fromisoformat(str(valor)[:10])


def _texto(valor) -> str | None:
    """Limpia lo que viene con espacios de más, como la patente (' FAP480')."""
    if valor is None:
        return None
    limpio = str(valor).strip()
    return limpio or None


# ─── Cómo se trae y se guarda cada conjunto ─────────────────────────────────
#
# Cada entrada declara: de dónde sale, a qué tabla va, cómo se traduce una fila
# del origen a una fila nuestra, y con qué campos se arma su clave. La
# reconciliación de abajo es una sola y sirve para los cinco.

def _mapear_viaje(f: dict) -> dict:
    return {
        # En el sistema de campo el nombre del colectivo ES el de su dueño.
        "tercero": _texto(f.get("colectivo_nombre")),
        "colectivo_nombre": _texto(f.get("colectivo_nombre")),
        "colectivo_patente": _texto(f.get("colectivo_patente")),
        "fecha_uso": _fecha(f.get("fecha_uso")),
        "fecha_carga": _fecha(f.get("fecha_carga")),
        "cliente": _texto(f.get("cliente")),
        "finca": _texto(f.get("finca")),
        "tarea": _texto(f.get("nombre_tarea")),
        "supervisor": _texto(f.get("nombre_supervisor")),
        "capataz": _texto(f.get("nombre_capataz")),
        "chofer": _texto(f.get("nombre_chofer")),
        "cantidad_viajes": f.get("cantidadviajes"),
        "cant_personas": f.get("cantpersonas"),
    }


def _mapear_carga(f: dict) -> dict:
    return {
        "tercero": _texto(f.get("colectivo_nombre")),
        "colectivo_nombre": _texto(f.get("colectivo_nombre")),
        "colectivo_patente": _texto(f.get("colectivo_patente")),
        "fecha_uso": _fecha(f.get("fecha_uso")),
        "fecha_carga": _fecha(f.get("fecha_carga")),
        "litros": f.get("litros_cargados"),
        "vale": _texto(f.get("vale")),
        "origen": _texto(f.get("origen_combustible")),
        "usuario_carga": _texto(f.get("usuario_carga")),
        "observacion": _texto(f.get("observacion")),
    }


def _mapear_hora_servicio(f: dict) -> dict:
    return {
        "tercero": _texto(f.get("tercero")),
        "fecha": _fecha(f.get("fecha")),
        "planilla": _texto(f.get("planilla")),
        "cliente": _texto(f.get("cliente")),
        "finca": _texto(f.get("finca")),
        "tarea": _texto(f.get("tarea")),
        "maquinaria": _texto(f.get("maquinaria")),
        "id_maquinaria": f.get("id_maquinaria"),
        "supervisor": _texto(f.get("supervisor")),
        "horas_maquina": f.get("horas_maquina"),
        # Fuera de la clave a propósito: así las filas ya guardadas, que no lo
        # tenían, se refrescan en vez de rehacerse y perder lo cargado a mano.
        "horas_jornal": f.get("horas_jornal"),
        "unidades": f.get("unidades"),
        "unidad": _texto(f.get("unidad")),
    }


def _mapear_repuesto(f: dict) -> dict:
    return {
        # El dueño lo pone `_repuestos_con_dueno`, desde el sistema de campo.
        "tercero": _texto(f.get("tercero")) or None,
        "id_maquina": f.get("id_maquina"),
        "maquina": _texto(f.get("maquina")),
        "fecha": _fecha(f.get("fecha")),
        "fecha_descarga": _fecha(f.get("fecha_descarga")),
        "tipo_insumo": _texto(f.get("tipo_insumo")),
        "rubro": _texto(f.get("rubro")),
        "repuesto": _texto(f.get("repuesto")),
        "cantidad": f.get("cantidad"),
        "precio_unitario": f.get("precargas"),
        "monto_total": f.get("monto_total"),
        "reparacion": _texto(f.get("reparacion")),
        "proveedor": _texto(f.get("nombreprove")),
        # Explícito: el insert en lote no pasa por los defaults del ORM.
        "no_cobrar": False,
    }


def _mapear_hora_reparacion(f: dict) -> dict:
    return {
        "tercero": _texto(f.get("tercero")),
        "id_maquina": f.get("id_maquina"),
        "maquina": _texto(f.get("maquina")),
        "tipo_maquina": _texto(f.get("tipo_maquina")),
        "fecha": _fecha(f.get("fecha")),
        "rubro": _texto(f.get("rubro")),
        "sub_rubro": _texto(f.get("sub_rubro")),
        "finca": _texto(f.get("finca")),
        "lugar": _texto(f.get("lugar")),
        "estado": _texto(f.get("estado")),
        "horas": f.get("horas"),
        "horas_preparacion": f.get("horas_preparacion"),
        "horas_traslado": f.get("horas_traslado"),
        "horas_total": f.get("horas_total"),
    }


# clave: los campos que identifican al hecho. No incluyen lo manual ni el id,
# porque tienen que dar lo mismo mirando el origen o mirando la base.
CONJUNTOS = (
    {
        "nombre": "viajes",
        "modelo": Viaje,
        "mapear": _mapear_viaje,
        "clave": ("fecha_uso", "colectivo_patente", "cliente", "finca", "tarea",
                  "capataz", "chofer", "cantidad_viajes", "cant_personas"),
    },
    {
        "nombre": "horas_servicio",
        "modelo": HoraServicio,
        "mapear": _mapear_hora_servicio,
        # La máquina por su id y no por su nombre: renombrarla en el sistema de
        # campo no rehace la fila ni pierde lo que se movió de quincena.
        "clave": ("fecha", "planilla", "id_maquinaria", "cliente", "finca", "tarea",
                  "horas_maquina", "unidades"),
    },
    {
        "nombre": "combustible",
        "modelo": CargaCombustible,
        "mapear": _mapear_carga,
        "clave": ("fecha_uso", "colectivo_patente", "vale", "litros"),
    },
    {
        "nombre": "repuestos",
        "modelo": Repuesto,
        "mapear": _mapear_repuesto,
        "clave": ("fecha", "id_maquina", "repuesto", "cantidad", "monto_total"),
    },
    {
        "nombre": "horas_reparacion",
        "modelo": HoraReparacion,
        "mapear": _mapear_hora_reparacion,
        "clave": ("fecha", "id_maquina", "sub_rubro", "estado", "horas_total"),
    },
)

# Lo que el liquidador carga a mano y que una actualización tiene que respetar.
CAMPOS_MANUALES = ("quincena_efectiva", "motivo_efectiva", "motivo_no_cobrar")
# `no_cobrar` va aparte porque su valor manual es False tanto como True: el
# mapeo del origen lo trae siempre en False, así que refrescarlo sería pisar la
# decisión de no cobrarle algo a alguien.
NO_SE_REFRESCAN = CAMPOS_MANUALES + ("no_cobrar",)


def tiene_trabajo_manual(fila) -> bool:
    if getattr(fila, "no_cobrar", False):
        return True
    return any(getattr(fila, campo, None) for campo in CAMPOS_MANUALES)


def _misma_persona(a: str, b: str) -> bool:
    """Si dos nombres son la misma persona escrita de otra forma: las mismas
    palabras, sin importar la coma ni el orden ("ANA FERREYRA" y "FERREYRA,
    ANA"). Un cambio de dueño de verdad no pasa esto, y no tiene que pasarlo:
    el precio se pactó con otra persona."""
    def palabras(s):
        return sorted(s.upper().replace(",", " ").split())
    return palabras(a) == palabras(b)


def _normalizar(v):
    """Cómo se compara un valor del origen contra uno de la base.

    Los dos lados tipan distinto para el mismo dato: los litros llegan del
    sistema de campo como el texto `'150'` y están guardados como
    `Decimal('150.00')`. Sin esto, cada carga de combustible parecería haber
    cambiado en cada actualización.
    """
    if v is None:
        return ""
    if isinstance(v, (int,)) and not isinstance(v, bool):
        return str(v)
    try:
        return str(float(v))          # Decimal, float, numérico en texto
    except (TypeError, ValueError):
        return str(v).strip().upper()


def _clave(datos: dict, campos: tuple) -> tuple:
    """La clave se arma normalizando cada campo, para que un Decimal('6.00')
    leído del origen y un Decimal('6.0000') leído de MySQL no parezcan hechos
    distintos."""
    return tuple(_normalizar(datos.get(c)) for c in campos)


class LiquidacionService:
    """Las quincenas generadas del módulo."""

    def __init__(self, db_propia: Session, externa, taller):
        self.db = db_propia
        self.externa = externa
        self.taller = taller

    # ─── Lectura ────────────────────────────────────────────────────────────

    def listar(self) -> list[dict]:
        """Las quincenas generadas, de la más nueva a la más vieja."""
        filas = (self.db.query(Liquidacion)
                 .order_by(Liquidacion.quincena.desc()).all())
        return [self._resumen(liq) for liq in filas]

    def obtener(self, quincena: date) -> Liquidacion | None:
        return (self.db.query(Liquidacion)
                .filter(Liquidacion.quincena == quincena).first())

    def _resumen(self, liq: Liquidacion) -> dict:
        conteos = {
            c["nombre"]: (self.db.query(c["modelo"])
                          .filter(c["modelo"].liquidacion_id == liq.id).count())
            for c in CONJUNTOS
        }
        return {
            "id": liq.id,
            "quincena": liq.quincena,
            "generada_en": liq.generada_en,
            "actualizada_en": liq.actualizada_en,
            "filas": conteos,
            "total_filas": sum(conteos.values()),
        }

    # ─── Generar / actualizar ───────────────────────────────────────────────

    def _seguir_renombres(self, liq: Liquidacion) -> None:
        """Las tarifas y los seguros toman el nombre actual de su máquina o su
        bien, buscándolo por id (2026-10-07). La tarifa de servicio toma
        también cómo está escrito ahora su dueño ("ANA FERREYRA" pasó a
        "FERREYRA, ANA", 2026-10-14), pero sólo si es la misma persona: hay
        reglas de una máquina a nombre de otros terceros, y esas no son de él.

        El cruce con los hechos sigue siendo por nombre, pero el nombre ya no
        puede quedar viejo: cambia acá, en la misma actualización que trae a los
        hechos con el nombre nuevo. Lo que chocaría con una regla que ya tiene
        ese nombre se deja como está, a la vista, en vez de pisarla.
        """
        # Las horas recién actualizadas todavía no están en la base, y la
        # sesión de la app no se vacía sola: sin esto se leerían los nombres
        # viejos y el renombre llegaría recién en la actualización siguiente.
        self.db.flush()
        actuales = {i: (maquina, dueno) for i, maquina, dueno in
                    self.db.query(HoraServicio.id_maquinaria, HoraServicio.maquinaria,
                                  HoraServicio.tercero)
                    .filter(HoraServicio.liquidacion_id == liq.id,
                            HoraServicio.id_maquinaria.isnot(None)).distinct()}
        for tarifa in (self.db.query(TarifaServicio)
                       .filter(TarifaServicio.id_maquinaria.in_(actuales)).all()):
            maquina, dueno = actuales[tarifa.id_maquinaria]
            nuevo = {"maquinaria": maquina}
            # Una regla sin tercero vale para cualquiera y así sigue; y una
            # máquina que se quedó sin dueño no le borra el que la regla tenía.
            if tarifa.tercero and dueno and _misma_persona(tarifa.tercero, dueno):
                nuevo["tercero"] = dueno
            if any(getattr(tarifa, c) != v for c, v in nuevo.items()) and not self._choca(
                    TarifaServicio, tarifa, **nuevo):
                for campo, valor in nuevo.items():
                    setattr(tarifa, campo, valor)
                # La sesión no se vacía sola: sin esto, dos reglas que pasan al
                # mismo nombre no se ven entre sí y chocan en la base.
                self.db.flush()

        # El chofer no: el mismo chofer aparece con cada dueño para el que
        # manejó, así que su id no alcanza para saber de quién es la póliza.
        bienes = {(b["origen"], b["id_origen"]): b
                  for b in self.externa.bienes_terceros() if b["origen"] != "chofer"}
        for seguro in (self.db.query(PrecioSeguro)
                       .filter(PrecioSeguro.id_origen.isnot(None),
                               PrecioSeguro.origen != "chofer").all()):
            bien = bienes.get((seguro.origen, seguro.id_origen))
            if bien is None or not bien["tercero"]:
                continue
            nuevo = {"tercero": bien["tercero"], "sujeto": bien["nombre"],
                     "referencia": bien["patente"]}
            if any(getattr(seguro, c) != v for c, v in nuevo.items()) and not self._choca(
                    PrecioSeguro, seguro, **nuevo):
                for campo, valor in nuevo.items():
                    setattr(seguro, campo, valor)
                self.db.flush()

    def _choca(self, modelo, fila, **cambios) -> bool:
        """Si con esos cambios quedaría igual a otra regla de su quincena."""
        consulta = self.db.query(modelo).filter(modelo.quincena == fila.quincena,
                                                modelo.id != fila.id)
        for d in modelo.DIMENSIONES:
            consulta = consulta.filter(getattr(modelo, d) == cambios.get(d, getattr(fila, d)))
        return consulta.first() is not None

    def _repuestos_con_dueno(self, filas: list[dict]) -> list[dict]:
        """Cada repuesto, con el dueño que el sistema de campo le da a su
        máquina, buscada por el id que La Falda guarda de ella (decidido con el
        usuario el 2026-10-07). Antes se deducía del nombre, y lo de una misma
        persona caía en varias órdenes. Una máquina sin ese id queda sin dueño:
        se ve, y se resuelve cargándolo en La Falda.

        El id de un colectivo es el del maestro de colectivos, no el de
        maquinaria (2026-10-14): el mismo número es otra cosa en cada uno."""
        maquinas = self.externa.duenos_por_id()
        colectivos = self.externa.duenos_de_colectivos_por_id()
        return [{**f, "tercero": (colectivos if f.get("es_colectivo") else maquinas)
                 .get(f.get("id_chinagro"))} for f in filas]

    def _con_dueno_del_maestro(self, horas: list[dict]) -> list[dict]:
        """Cada hora del taller, con el dueño que el maestro de maquinaria del
        sistema de campo le da a su máquina (ver `QUERY_DUENOS_MAQUINARIA`).
        La que no está en el maestro queda sin dueño: se ve y no se cobra."""
        duenos = self.externa.duenos_de_maquinas()
        return [{**h, "tercero": duenos.get(nombre_de_maquina(h.get("maquina")))}
                for h in horas]

    def generar(self, quincena: date, usuario_id: int | None = None) -> dict:
        """Trae las cinco fuentes y las guarda. Si la quincena ya existe,
        reconcilia en vez de rehacerla."""
        liq = self.obtener(quincena)
        nueva = liq is None
        if nueva:
            liq = Liquidacion(quincena=quincena, generada_por=usuario_id)
            self.db.add(liq)
            self.db.flush()
        else:
            liq.actualizada_en = datetime.now()

        origenes = {
            "viajes": lambda: self.externa.viajes(quincena),
            "horas_servicio": lambda: self.externa.horas_servicio(quincena),
            "combustible": lambda: self.externa.cargas_combustible(quincena),
            "repuestos": lambda: self._repuestos_con_dueno(self.externa.repuestos(quincena)),
            "horas_reparacion": lambda: self._con_dueno_del_maestro(
                self.taller.horas_quincena(quincena)),
        }

        detalle = {}
        for conjunto in CONJUNTOS:
            detalle[conjunto["nombre"]] = self._reconciliar(
                liq, conjunto, origenes[conjunto["nombre"]]()
            )
        self._seguir_renombres(liq)

        self.db.commit()
        return {
            "quincena": quincena,
            "nueva": nueva,
            "detalle": detalle,
            **self._resumen(liq),
        }

    def _reconciliar(self, liq: Liquidacion, conjunto: dict, filas_origen: list[dict]) -> dict:
        """Deja la tabla igual al origen, respetando el trabajo manual."""
        modelo, mapear, campos = conjunto["modelo"], conjunto["mapear"], conjunto["clave"]

        del_origen = defaultdict(list)
        for f in filas_origen:
            datos = mapear(f)
            del_origen[_clave(datos, campos)].append(datos)

        guardadas = defaultdict(list)
        for fila in self.db.query(modelo).filter(modelo.liquidacion_id == liq.id).all():
            datos = {c: getattr(fila, c) for c in campos}
            guardadas[_clave(datos, campos)].append(fila)

        # Un repuesto repartido en cuotas es trabajo manual aunque no tenga
        # ningún campo propio cargado: el plan vive en otra tabla.
        con_cuotas = self._con_cuotas(liq) if modelo is Repuesto else set()

        def manual(fila) -> bool:
            return tiene_trabajo_manual(fila) or fila.id in con_cuotas

        # Sobran: se borran, sacrificando primero las que no tienen nada a mano.
        a_borrar = []
        for clave, filas in guardadas.items():
            exceso = len(filas) - len(del_origen.get(clave, ()))
            if exceso <= 0:
                continue
            sin_manual = [f for f in filas if not manual(f)]
            con_manual = [f for f in filas if manual(f)]
            a_borrar.extend((sin_manual + con_manual)[:exceso])
        cuotas_borradas = 0
        if a_borrar:
            ids = [f.id for f in a_borrar]
            # Si el repuesto dejó de existir en compras, sus cuotas no tienen
            # qué descontar. Se cuentan aparte para que se vea: que desaparezca
            # un plan de cuotas es algo que el liquidador tiene que saber.
            planes = [i for i in ids if i in con_cuotas]
            if planes:
                cuotas_borradas = len(planes)
                (self.db.query(CuotaRepuesto)
                 .filter(CuotaRepuesto.repuesto_id.in_(planes))
                 .delete(synchronize_session=False))
            (self.db.query(modelo).filter(modelo.id.in_(ids))
             .delete(synchronize_session=False))
        borradas = len(a_borrar)

        # Faltan: se insertan. En lote y no una por una — con `add()` por fila,
        # generar una quincena de mil filas tardaba 82 segundos contra los 16
        # que cuesta leer los orígenes: casi todo el tiempo era ida y vuelta a
        # la base. Por eso el mapeo incluye los valores por defecto de forma
        # explícita: bulk_insert_mappings no pasa por los defaults del ORM.
        nuevas = []
        for clave, filas in del_origen.items():
            faltan = len(filas) - len(guardadas.get(clave, ()))
            for datos in filas[:max(faltan, 0)]:
                nuevas.append({"liquidacion_id": liq.id, **datos})
        if nuevas:
            self.db.bulk_insert_mappings(modelo, nuevas)
        insertadas = len(nuevas)

        # Las que siguen: se les refrescan los campos que son del origen.
        #
        # Hace falta porque la clave no lleva todos los campos. El dueño de un
        # colectivo, por ejemplo, no está en la clave de un viaje —la clave usa
        # la patente—, así que cuando el sistema de campo corrige la ficha de
        # un colectivo, sin esto la corrección no llegaba nunca: la fila ya
        # existía, no sobraba ni faltaba, y se quedaba con el nombre viejo.
        # Actualizar prometía "dejar la tabla igual al origen" y no lo cumplía.
        #
        # Lo manual no se toca: eso es lo que distingue actualizar de rehacer.
        sin_borrar = {f.id for f in a_borrar}
        refrescadas = 0
        for clave, filas in guardadas.items():
            quedan = [f for f in filas if f.id not in sin_borrar]
            for fila, datos in zip(quedan, del_origen.get(clave, ())):
                cambios = {
                    c: v for c, v in datos.items()
                    if c not in NO_SE_REFRESCAN
                    and _normalizar(getattr(fila, c)) != _normalizar(v)
                }
                if cambios:
                    for campo, valor in cambios.items():
                        setattr(fila, campo, valor)
                    refrescadas += 1

        return {
            "origen": len(filas_origen),
            "insertadas": insertadas,
            "borradas": borradas,
            "refrescadas": refrescadas,
            "sin_cambios": len(filas_origen) - insertadas - refrescadas,
            "planes_de_cuotas_borrados": cuotas_borradas,
        }

    def _con_cuotas(self, liq: Liquidacion) -> set[int]:
        """Los repuestos de esta quincena que se descuentan en cuotas."""
        return {i for (i,) in (self.db.query(CuotaRepuesto.repuesto_id)
                               .join(Repuesto, Repuesto.id == CuotaRepuesto.repuesto_id)
                               .filter(Repuesto.liquidacion_id == liq.id)
                               .distinct())}
