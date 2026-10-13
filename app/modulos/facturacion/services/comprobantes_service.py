"""Comprobantes cargados a mano: alta (plan de la E2, sección 3.1, reglas 1 a
6), edición y borrado (regla 7), y el listado y el detalle (sección 3.2).

Lo que se guarda del campo son copias (nombre del Cliente, de la tarea y de la
finca): el listado y el detalle no leen la base de campo, que es lenta y se
puede caer. Por eso la consulta se usa sólo al escribir, y se recibe por
parámetro para que los tests usen una falsa.

Las reglas puras (normalizar, clave, importe) viven en `reglas_comprobante`,
porque la migración del histórico tiene que llegar a la misma clave para el
mismo dato.
"""
from decimal import Decimal

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.models import ahora_utc
from app.modulos.facturacion.models import Adjunto, Comprobante, LineaComprobante
from app.modulos.facturacion.schemas import ComprobanteEntrada, LineaEntrada
from app.modulos.facturacion.services.adjuntos_service import (
    borrar_archivos, carpeta_adjuntos,
)
from app.modulos.facturacion.services.reglas_comprobante import (
    CENTAVO, FACTURA, NOTA_CREDITO, TIPOS, NumeroInvalido, calcular_importe,
    clave_identidad, normalizar_empresa, normalizar_numero, total_firmado,
)
from app.modulos.facturacion.unidades import UNIDADES

# Los largos y las precisiones de las columnas (facturacion/003). Se controlan
# antes de escribir para que lo que no entra salga como un 422 con su campo y
# no como un error de MySQL (un 500), o redondeado sin aviso por la base.
LARGO_NUMERO = 30
LARGO_EMPRESA = 100
# (dígitos en total, decimales), como DECIMAL(14,2) y DECIMAL(14,4).
CANTIDAD = (14, 2)
PRECIO = (14, 4)
IMPORTE = (14, 2)


# ─── Excepciones ────────────────────────────────────────────────────────────
# Las traduce el router a los códigos y al `detail` del contrato (sección 3.2).
# El mensaje lo lee una persona: dice qué corregir, no qué falló por dentro.

class ErrorComprobante(Exception):
    mensaje = "No se pudo guardar el comprobante."

    def __init__(self, mensaje: str | None = None):
        if mensaje:
            self.mensaje = mensaje
        super().__init__(self.mensaje)


class ComprobanteNoEncontrado(ErrorComprobante):
    mensaje = "No existe ese comprobante."


class ComprobanteRepetido(ErrorComprobante):
    """409 `comprobante_repetido`: esa Empresa ya tiene ese número."""

    def __init__(self, comprobante_id: int):
        self.comprobante_id = comprobante_id
        super().__init__("Esa Empresa ya tiene un comprobante con ese número.")


class HistoricoMismoNumero(ErrorComprobante):
    """409 `historico_mismo_numero`: el Cliente ya tiene un histórico con ese
    número. Evita contarlo dos veces mientras la planilla siga viva."""

    def __init__(self, comprobante_id: int):
        self.comprobante_id = comprobante_id
        super().__init__(
            "Ese Cliente ya tiene un comprobante histórico con ese número, "
            "migrado de la planilla.")


class HistoricoNoEditable(ErrorComprobante):
    mensaje = ("Un comprobante histórico no se edita ni se borra. Sus adjuntos "
               "sí se pueden subir y quitar.")


class FacturaConNotas(ErrorComprobante):
    mensaje = ("Esta factura tiene notas de crédito: no se puede borrar ni "
               "cambiar de Cliente o de tipo.")


class ComprobanteModificado(ErrorComprobante):
    """409 `comprobante_modificado`: el PUT trae un `actualizado_en` que ya
    no es el de la base, porque otra persona lo guardó mientras tanto
    (pregunta 18)."""
    mensaje = ("Otra persona cambió este comprobante mientras lo editabas. "
               "Volvé a abrirlo para ver sus cambios antes de guardar.")


class ComprobanteInvalido(ErrorComprobante):
    """422 `comprobante_invalido`, con el campo de la cabecera que falla."""

    def __init__(self, campo: str, mensaje: str):
        self.campo = campo
        super().__init__(mensaje)


class LineaInvalida(ErrorComprobante):
    """422 `linea_invalida`, con la fila (desde 1) y el campo que falla."""

    def __init__(self, fila: int, campo: str, mensaje: str):
        self.fila = fila
        self.campo = campo
        super().__init__(mensaje)


def _cabe(valor: Decimal, precision: tuple[int, int]) -> bool:
    """Si el valor entra en un DECIMAL(digitos, decimales) sin redondear."""
    digitos, decimales = precision
    signo, cifras, exponente = valor.normalize().as_tuple()
    decimales_del_valor = max(0, -exponente)
    enteros_del_valor = max(0, len(cifras) + exponente)
    return (decimales_del_valor <= decimales
            and enteros_del_valor <= digitos - decimales)


class ComprobantesService:

    def __init__(self, db: Session, consulta):
        """`consulta` es la ConsultaExternaService del módulo (o una falsa):
        se usa sólo al escribir, para validar contra el maestro y copiar los
        nombres."""
        self.db = db
        self.consulta = consulta

    # ─── Alta ───────────────────────────────────────────────────────────────

    def crear(self, entrada: ComprobanteEntrada, usuario_id: int | None = None) -> Comprobante:
        cabecera = self._validar_cabecera(entrada)
        lineas = self._validar_lineas(entrada.lineas, entrada.cliente_id)

        existente = self._por_clave(cabecera["clave_identidad"])
        if existente is not None:
            raise ComprobanteRepetido(existente.id)
        historico = self._historico_con_numero(
            entrada.tipo, entrada.cliente_id, cabecera["numero"])
        if historico is not None:
            raise HistoricoMismoNumero(historico.id)

        comprobante = Comprobante(
            **cabecera, es_historico=False, creado_por=usuario_id,
            lineas=[LineaComprobante(**linea) for linea in lineas],
        )
        self.db.add(comprobante)
        self._guardar(cabecera["clave_identidad"])
        self.db.refresh(comprobante)
        return comprobante

    # ─── Edición y borrado (regla 7) ────────────────────────────────────────

    def editar(self, comprobante_id: int, entrada: ComprobanteEntrada,
               usuario_id: int | None = None) -> Comprobante:
        """El PUT: reemplaza la cabecera y todas las Líneas, con las mismas
        validaciones que el alta, y sella quién y cuándo editó (el modelo no
        tiene onupdate a propósito: el reemplazo de un histórico por el script
        no es una edición)."""
        comprobante = self._modificable(comprobante_id)
        cambia_cliente_o_tipo = (entrada.cliente_id != comprobante.cliente_id
                                 or entrada.tipo != comprobante.tipo)
        # Edición simultánea (pregunta 18): el PUT trae el `actualizado_en`
        # que le dio el detalle (null si nunca se editó). Si no es el de la
        # base, otra persona guardó en el medio y no se pisa su trabajo. Se
        # compara exacto porque el sello va sin microsegundos (ver abajo).
        if entrada.actualizado_en != comprobante.actualizado_en:
            raise ComprobanteModificado()
        # Una Factura con Notas de crédito no cambia de Cliente ni de tipo: las
        # Notas quedarían corrigiendo una factura de otro Cliente, o una que ya
        # no es factura.
        if cambia_cliente_o_tipo and self._tiene_notas(comprobante.id):
            raise FacturaConNotas()

        cabecera = self._validar_cabecera(entrada, actual=comprobante)
        # Las fincas que ya tenía se conservan sólo si el Cliente no cambia:
        # con otro Cliente, una finca del anterior no es suya.
        fincas_previas = (
            {l.finca_id: l.finca_nombre for l in comprobante.lineas
             if l.finca_id is not None}
            if entrada.cliente_id == comprobante.cliente_id else None)
        lineas = self._validar_lineas(
            entrada.lineas, entrada.cliente_id,
            tareas_previas={l.tarea_id: l.tarea_nombre for l in comprobante.lineas},
            fincas_previas=fincas_previas)

        # El propio número no es un repetido: la clave recalculada puede ser
        # la misma que ya tenía.
        existente = self._por_clave(cabecera["clave_identidad"])
        if existente is not None and existente.id != comprobante.id:
            raise ComprobanteRepetido(existente.id)
        historico = self._historico_con_numero(
            entrada.tipo, entrada.cliente_id, cabecera["numero"])
        if historico is not None:
            raise HistoricoMismoNumero(historico.id)

        # Sin microsegundos: MySQL guarda DATETIME sin fracción (y la
        # redondea), así que con ella el valor que devuelve el detalle no
        # sería el que se guardó, y la comparación de arriba fallaría contra
        # sí misma.
        sello = ahora_utc().replace(microsecond=0)
        # La comparación de arriba no alcanza: entre ella y el commit se
        # consulta el campo, y otro guardado puede confirmarse en el medio.
        # Si siguiera, borraría por id las Líneas que leyó (que el otro ya
        # reemplazó) y sumaría las suyas a las del otro. Por eso, antes de
        # tocar las Líneas, la cabecera se sella con un UPDATE condicionado al
        # `actualizado_en` leído (null-safe: uno nunca editado tiene null). En
        # MySQL el UPDATE toma el lock de la fila y compara contra lo último
        # confirmado: el segundo guardado espera al primero y no afecta
        # ninguna fila.
        sellado = self.db.execute(
            update(Comprobante)
            .where(Comprobante.id == comprobante.id,
                   Comprobante.actualizado_en.is_not_distinct_from(
                       comprobante.actualizado_en))
            .values(actualizado_en=sello, actualizado_por=usuario_id)
            .execution_options(synchronize_session=False))
        if sellado.rowcount != 1:
            self.db.rollback()
            raise ComprobanteModificado()
        # Crear una Nota no toca el `actualizado_en` de su Factura, así que el
        # UPDATE de arriba no ve una Nota cargada en el medio (R4). Con la fila
        # ya sellada, el control de Notas se repite con lectura bloqueante: en
        # MySQL ve lo último confirmado, y una Nota que llega después espera a
        # este guardado (ver _validar_factura_corregida).
        if cambia_cliente_o_tipo and self._tiene_notas(comprobante.id, bloquear=True):
            self.db.rollback()
            raise FacturaConNotas()

        # Sin autoflush: reemplazar la colección carga las Líneas viejas, y esa
        # consulta escribiría la cabecera nueva antes de tiempo. Un choque con
        # la clave tiene que salir del commit de _guardar, que lo traduce.
        with self.db.no_autoflush:
            for campo, valor in cabecera.items():
                setattr(comprobante, campo, valor)
            # Las Líneas que salen de la lista se borran (delete-orphan).
            comprobante.lineas = [LineaComprobante(**linea) for linea in lineas]
            # Los mismos valores que ya escribió el UPDATE de arriba, para que
            # el objeto los tenga.
            comprobante.actualizado_por = usuario_id
            comprobante.actualizado_en = sello
        self._guardar(cabecera["clave_identidad"], propio_id=comprobante.id)
        self.db.refresh(comprobante)
        return comprobante

    def borrar(self, comprobante_id: int) -> None:
        """El DELETE: se lleva el Comprobante, sus Líneas y sus Adjuntos con
        sus archivos (pregunta 15).

        Como al quitar un Adjunto, primero las filas y después los archivos:
        si el commit falla, los archivos siguen ahí con sus filas. Sin la
        carpeta de adjuntos, uno que tiene Adjuntos no se borra (503): sus
        archivos quedarían huérfanos. Uno sin Adjuntos no la necesita.

        Bloquea primero el Comprobante y después sus Adjuntos, el mismo orden
        que `AdjuntosService.subir` y `quitar`: así no se traban entre ellas,
        y una subida a la vez no deja un archivo sin borrar."""
        comprobante = self._modificable(comprobante_id, bloquear=True)
        if self._tiene_notas(comprobante.id):
            raise FacturaConNotas()
        # Las filas de los Adjuntos se borran a mano: la relación no tiene
        # cascada a propósito (ver Comprobante.adjuntos).
        adjuntos = (self.db.query(Adjunto)
                    .filter(Adjunto.comprobante_id == comprobante.id)
                    .with_for_update()
                    .all())
        carpeta = carpeta_adjuntos() if adjuntos else None
        nombres_en_disco = [a.nombre_en_disco for a in adjuntos]
        for adjunto in adjuntos:
            self.db.delete(adjunto)
        self.db.delete(comprobante)
        try:
            self.db.commit()
        except IntegrityError:
            # Si otra persona le cargó una Nota de crédito entre el control y
            # el DELETE, la FK de `factura_corregida_id` lo frena: es el mismo
            # 409 que el control, no un 500. Cualquier otro choque sigue de
            # largo.
            self.db.rollback()
            if self._tiene_notas(comprobante_id):
                raise FacturaConNotas() from None
            raise
        if adjuntos:
            borrar_archivos(carpeta, nombres_en_disco)

    def _modificable(self, comprobante_id: int, bloquear: bool = False) -> Comprobante:
        """El Comprobante a editar o borrar: existe y no es histórico (la
        idempotencia de la migración depende de que no cambie, pregunta 6).
        Con `bloquear`, lectura bloqueante: `get` consulta la base aunque la
        fila ya esté en la sesión (en SQLite no hace nada)."""
        comprobante = self.db.get(Comprobante, comprobante_id,
                                  with_for_update=True if bloquear else None)
        if comprobante is None:
            raise ComprobanteNoEncontrado()
        if comprobante.es_historico:
            raise HistoricoNoEditable()
        return comprobante

    def _tiene_notas(self, comprobante_id: int, bloquear: bool = False) -> bool:
        """Si alguna Nota de crédito corrige este Comprobante. Con `bloquear`,
        la lectura es bloqueante compartida (en SQLite no hace nada)."""
        consulta = (self.db.query(Comprobante.id)
                    .filter(Comprobante.factura_corregida_id == comprobante_id))
        if bloquear:
            consulta = consulta.with_for_update(read=True)
        return consulta.first() is not None

    # ─── Lecturas (sección 3.2) ─────────────────────────────────────────────
    # No leen la base de campo: usan las copias guardadas al escribir.

    def listar(self) -> list[dict]:
        """Las filas del listado (`ComprobanteFila`), de la más nueva a la más
        vieja por `fecha` o, si falta, por la fecha de la primera Línea.

        Una sola consulta, sin importar cuántos Comprobantes haya: los conteos
        y el total salen de subconsultas agrupadas y la fecha de la primera
        Línea de una subconsulta correlacionada."""
        por_lineas = (
            select(LineaComprobante.comprobante_id.label("comprobante_id"),
                   func.count(LineaComprobante.id).label("cantidad"),
                   func.sum(LineaComprobante.importe).label("total"))
            .group_by(LineaComprobante.comprobante_id)
            .subquery())
        por_adjuntos = (
            select(Adjunto.comprobante_id.label("comprobante_id"),
                   func.count(Adjunto.id).label("cantidad"))
            .group_by(Adjunto.comprobante_id)
            .subquery())
        # "Primera" es la de menor orden, no la de fecha más vieja: el mes del
        # listado es el de la primera Línea (pregunta 10).
        primera_fecha = (
            select(LineaComprobante.fecha)
            .where(LineaComprobante.comprobante_id == Comprobante.id)
            .order_by(LineaComprobante.orden, LineaComprobante.id)
            .limit(1)
            .correlate(Comprobante)
            .scalar_subquery())

        consulta = (
            select(Comprobante, por_lineas.c.cantidad, por_lineas.c.total,
                   por_adjuntos.c.cantidad, primera_fecha)
            .outerjoin(por_lineas, por_lineas.c.comprobante_id == Comprobante.id)
            .outerjoin(por_adjuntos, por_adjuntos.c.comprobante_id == Comprobante.id)
            .order_by(func.coalesce(Comprobante.fecha, primera_fecha).desc(),
                      Comprobante.id.desc()))

        return [
            self._fila(c, cantidad_lineas or 0, cantidad_adjuntos or 0,
                       [total] if total is not None else [], fecha_primera)
            for c, cantidad_lineas, total, cantidad_adjuntos, fecha_primera
            in self.db.execute(consulta).all()
        ]

    def detalle(self, comprobante_id: int) -> dict:
        """El `ComprobanteDetalle`: los campos de la fila, la Factura que
        corrige (en una NC), sus Notas de crédito (en una Factura), las Líneas
        con el importe positivo (el front lo muestra negativo en una NC) y los
        Adjuntos."""
        c = self.db.get(Comprobante, comprobante_id)
        if c is None:
            raise ComprobanteNoEncontrado()

        lineas = list(c.lineas)
        adjuntos = list(c.adjuntos)
        notas = (self.db.query(Comprobante.id, Comprobante.numero, Comprobante.fecha)
                 .filter(Comprobante.factura_corregida_id == c.id)
                 .order_by(Comprobante.id)
                 .all())
        corregida = c.factura_corregida

        return {
            **self._fila(c, len(lineas), len(adjuntos),
                         [l.importe for l in lineas],
                         lineas[0].fecha if lineas else None),
            "factura_corregida": (
                {"id": corregida.id, "numero": corregida.numero, "fecha": corregida.fecha}
                if corregida is not None else None),
            "notas_credito": [{"id": id_, "numero": numero, "fecha": fecha}
                              for id_, numero, fecha in notas],
            "lineas": [{
                "id": l.id, "orden": l.orden, "fecha": l.fecha,
                "tarea_id": l.tarea_id, "tarea_nombre": l.tarea_nombre,
                "unidad": l.unidad, "finca_id": l.finca_id,
                "finca_nombre": l.finca_nombre, "cantidad": l.cantidad,
                "precio_unitario": l.precio_unitario, "importe": l.importe,
            } for l in lineas],
            "adjuntos": [{
                "id": a.id, "nombre_original": a.nombre_original,
                "tipo_contenido": a.tipo_contenido, "tamano_bytes": a.tamano_bytes,
                "subido_en": a.subido_en,
            } for a in adjuntos],
            "creado_en": c.creado_en,
            "actualizado_en": c.actualizado_en,
        }

    @staticmethod
    def _fila(c: Comprobante, cantidad_lineas: int, cantidad_adjuntos: int,
              importes: list, fecha_primera_linea) -> dict:
        """Los campos de `ComprobanteFila`, comunes al listado y al detalle.
        `total_neto` va con signo (negativo en una NC) y redondeado a
        centavos: una suma en SQLite puede traer más decimales."""
        return {
            "id": c.id,
            "tipo": c.tipo,
            "numero": c.numero,
            "fecha": c.fecha,
            "mes": (fecha_primera_linea.strftime("%Y-%m")
                    if fecha_primera_linea is not None else None),
            "cliente_id": c.cliente_id,
            "cliente_nombre": c.cliente_nombre,
            "empresa_emisora": c.empresa_emisora,
            "es_historico": bool(c.es_historico),
            "pendiente_de_facturar": bool(c.pendiente_de_facturar),
            "cantidad_lineas": cantidad_lineas,
            "cantidad_adjuntos": cantidad_adjuntos,
            "total_neto": total_firmado(c.tipo, importes).quantize(CENTAVO),
        }

    # ─── Validación ─────────────────────────────────────────────────────────

    def _validar_cabecera(self, entrada: ComprobanteEntrada,
                          actual: Comprobante | None = None) -> dict:
        """Las reglas 1, 2 y 5. Devuelve los campos listos para el modelo:
        normalizados, con el nombre del Cliente copiado y la clave calculada.

        `actual` es el Comprobante que se edita (None en el alta)."""
        if entrada.tipo not in TIPOS:
            raise ComprobanteInvalido(
                "tipo", "El tipo tiene que ser Factura o Nota de crédito.")

        empresa = normalizar_empresa(entrada.empresa_emisora)
        if not empresa:
            raise ComprobanteInvalido("empresa_emisora", "Falta la Empresa emisora.")
        if len(empresa) > LARGO_EMPRESA:
            raise ComprobanteInvalido(
                "empresa_emisora",
                f"La Empresa emisora tiene hasta {LARGO_EMPRESA} caracteres.")

        try:
            numero = normalizar_numero(entrada.numero)
        except NumeroInvalido as error:
            raise ComprobanteInvalido("numero", str(error)) from None
        if len(numero) > LARGO_NUMERO:
            raise ComprobanteInvalido(
                "numero", f"El número tiene hasta {LARGO_NUMERO} caracteres.")

        if entrada.fecha is None:
            raise ComprobanteInvalido("fecha", "Falta la fecha del comprobante.")
        if not entrada.lineas:
            raise ComprobanteInvalido("lineas", "El comprobante necesita al menos una línea.")

        # Sólo los activos: un Cliente de baja no recibe comprobantes nuevos.
        # Pero un Comprobante que se edita puede conservar el suyo aunque haya
        # pasado a baja (regla 7): ahí se busca también entre las bajas, para
        # copiar el nombre.
        conserva_cliente = actual is not None and entrada.cliente_id == actual.cliente_id
        cliente = next((c for c in self.consulta.clientes(incluir_baja=conserva_cliente)
                        if c["id"] == entrada.cliente_id), None)
        if cliente is None:
            raise ComprobanteInvalido(
                "cliente_id", "Ese Cliente no existe o está dado de baja.")

        self._validar_factura_corregida(
            entrada, propio_id=actual.id if actual is not None else None)

        return {
            "tipo": entrada.tipo,
            "cliente_id": entrada.cliente_id,
            "cliente_nombre": cliente["nombre"],
            "empresa_emisora": empresa,
            "numero": numero,
            "fecha": entrada.fecha,
            "factura_corregida_id": entrada.factura_corregida_id,
            "clave_identidad": clave_identidad(
                historico=False, numero=numero, empresa=empresa, tipo=entrada.tipo),
        }

    def _validar_factura_corregida(self, entrada: ComprobanteEntrada,
                                   propio_id: int | None = None) -> None:
        """Regla 5: una Nota de crédito corrige una Factura del mismo Cliente,
        que puede ser histórica. La Empresa no se compara con la de la
        Factura: el histórico no la tiene.

        `propio_id` es el Comprobante que se edita: no se corrige a sí mismo,
        porque después del PUT sería una Nota de crédito y no una Factura."""
        if entrada.tipo == FACTURA:
            # Si una Factura guardara una, aparecería como Nota de crédito de
            # otra en el detalle.
            if entrada.factura_corregida_id is not None:
                raise ComprobanteInvalido(
                    "factura_corregida_id",
                    "Sólo una Nota de crédito corrige una factura.")
            return

        if entrada.factura_corregida_id is None:
            raise ComprobanteInvalido(
                "factura_corregida_id",
                "Una Nota de crédito tiene que decir qué factura corrige.")
        # Lectura bloqueante compartida (R4): si otra persona está cambiando
        # de tipo o de Cliente esa Factura, en MySQL se espera a que confirme
        # y se valida contra lo confirmado. Con with_for_update, `get` consulta
        # la base (y toma el bloqueo) aunque la fila ya esté en la sesión.
        factura = self.db.get(Comprobante, entrada.factura_corregida_id,
                              with_for_update={"read": True})
        if (factura is None or factura.id == propio_id or factura.tipo != FACTURA
                or factura.cliente_id != entrada.cliente_id):
            raise ComprobanteInvalido(
                "factura_corregida_id",
                "La Nota de crédito tiene que corregir una factura del mismo Cliente.")

    def _validar_lineas(self, lineas: list[LineaEntrada], cliente_id: int,
                        tareas_previas: dict[int, str] | None = None,
                        fincas_previas: dict[int, str] | None = None) -> list[dict]:
        """La regla 3, fila por fila (desde 1). Devuelve los campos de cada
        Línea listos para el modelo, con los nombres copiados del maestro y el
        importe calculado. Una tarea No facturable se acepta (regla 6): el
        aviso lo muestra el front.

        `tareas_previas` son las tareas que ya tenía el Comprobante que se
        edita ({tarea_id: nombre copiado}). Una de ellas que pasó a baja se
        conserva (regla 7) con el nombre de su copia, así no hace falta leer
        las bajas del campo; una tarea de baja nueva sigue siendo inválida.

        `fincas_previas` hace lo mismo con las fincas ({finca_id: nombre
        copiado}): la lectura del campo no trae las de baja. Sólo llegan si el
        Cliente no cambia."""
        tareas = {t["tarea_id"]: t["nombre"] for t in self.consulta.obtener_tareas()}
        for tarea_id, nombre in (tareas_previas or {}).items():
            tareas.setdefault(tarea_id, nombre)
        # Las fincas se leen sólo si alguna Línea tiene una.
        fincas = None
        if any(l.finca_id is not None for l in lineas):
            fincas = {f["id"]: f["nombre"]
                      for f in self.consulta.fincas_de_cliente(cliente_id)}
            for finca_id, nombre in (fincas_previas or {}).items():
                fincas.setdefault(finca_id, nombre)

        salida = []
        for fila, linea in enumerate(lineas, start=1):
            if linea.tarea_id not in tareas:
                raise LineaInvalida(fila, "tarea_id",
                                    "Esa tarea no existe o está dada de baja.")
            if linea.unidad not in UNIDADES:
                raise LineaInvalida(fila, "unidad", "Esa unidad no es una de las nueve.")
            finca_nombre = None
            if linea.finca_id is not None:
                if linea.finca_id not in fincas:
                    raise LineaInvalida(fila, "finca_id",
                                        "Esa finca no es del Cliente del comprobante.")
                finca_nombre = fincas[linea.finca_id]

            if not linea.cantidad.is_finite() or linea.cantidad <= 0:
                raise LineaInvalida(fila, "cantidad", "La cantidad tiene que ser mayor que 0.")
            if not _cabe(linea.cantidad, CANTIDAD):
                raise LineaInvalida(
                    fila, "cantidad",
                    "La cantidad tiene hasta 2 decimales y 12 cifras enteras.")
            if not linea.precio_unitario.is_finite() or linea.precio_unitario < 0:
                raise LineaInvalida(fila, "precio_unitario",
                                    "El precio no puede ser negativo.")
            if not _cabe(linea.precio_unitario, PRECIO):
                raise LineaInvalida(
                    fila, "precio_unitario",
                    "El precio tiene hasta 4 decimales y 10 cifras enteras.")
            importe = calcular_importe(linea.cantidad, linea.precio_unitario)
            if not _cabe(importe, IMPORTE):
                raise LineaInvalida(fila, "importe",
                                    "El importe de la línea es demasiado grande.")

            salida.append({
                "orden": fila,
                "fecha": linea.fecha,
                "tarea_id": linea.tarea_id,
                "tarea_nombre": tareas[linea.tarea_id],
                "unidad": linea.unidad,
                "finca_id": linea.finca_id,
                "finca_nombre": finca_nombre,
                "cantidad": linea.cantidad,
                "precio_unitario": linea.precio_unitario,
                "importe": importe,
            })
        return salida

    # ─── Repetidos ──────────────────────────────────────────────────────────

    def _por_clave(self, clave: str) -> Comprobante | None:
        return (self.db.query(Comprobante)
                .filter(Comprobante.clave_identidad == clave).first())

    def _historico_con_numero(self, tipo: str, cliente_id: int,
                              numero: str) -> Comprobante | None:
        """Regla 4: el histórico del mismo Cliente con ese número. La
        migración normaliza el número con la misma regla, así que se compara
        igual.

        Sólo frena a una Factura: los históricos son siempre Facturas, y las
        Notas de crédito numeran aparte (R3)."""
        if tipo != FACTURA:
            return None
        return (self.db.query(Comprobante)
                .filter(Comprobante.es_historico.is_(True),
                        Comprobante.cliente_id == cliente_id,
                        Comprobante.numero == numero)
                .first())

    def _guardar(self, clave: str, propio_id: int | None = None) -> None:
        """Commit que convierte el choque con el UNIQUE de la clave en un
        repetido. Pasa cuando dos personas cargan el mismo comprobante a la
        vez (pregunta 18): las dos pasan el control previo y la base frena a
        la segunda, que tiene que recibir el 409 con el id y no un 500.

        `propio_id` es el que se edita: si la clave la tiene él, el choque fue
        con otra cosa y el error sigue de largo."""
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            existente = self._por_clave(clave)
            if existente is None or existente.id == propio_id:
                raise
            raise ComprobanteRepetido(existente.id) from None
