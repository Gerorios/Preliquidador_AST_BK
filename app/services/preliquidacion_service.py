from datetime import date
from decimal import Decimal
from typing import Optional
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import and_, or_, func, case, text as sql_text

from app.models.models import (
    Preliquidacion, PreliquidacionLinea, ConceptoAdicional,
    AjusteManual, ConceptoLiquidacion, UnidadBaseConcepto, CategoriaOperario,
)
from app.services.consulta_externa import ConsultaExternaService
from app.services.motor_reglas import MotorReglas
from app.services.sueldos_service import SueldosService
from app.schemas.schemas import LineaUpdateRequest, ConceptoAdicionalRequest


def _n(v) -> str:
    if v is None: return "None"
    try: return f"{float(str(v)):.2f}"
    except: return "None"


def _clave_linea(fila: dict) -> tuple:
    return (
        str(fila.get("planilla", "") or "").strip().upper(),
        str(fila.get("fecha_tarea", "") or ""),
        str(fila.get("legajo", "") or "").strip(),
        str(fila.get("nombre_empleado", "") or "").strip().upper(),
        str(fila.get("nombre_tarea", "") or "").strip().upper(),
        str(fila.get("nombre_cliente", "") or "").strip().upper(),
        str(fila.get("nombre_finca", "") or "").strip().upper(),
        str(fila.get("nombre_tractor", "") or "").strip().upper(),
        _n(fila.get("hsjornal")),
        _n(fila.get("hsmaquina")),
        _n(fila.get("tancadas")),
        _n(fila.get("unidades")),
    )


class PreliquidacionService:

    def __init__(self, db_propia: Session, db_externa: Session = None, db_sueldos: Session = None):
        self.db = db_propia
        self.sueldos = SueldosService(db_sueldos) if db_sueldos else None
        self.motor = MotorReglas(db_propia, self.sueldos)
        self.externa = ConsultaExternaService(db_externa) if db_externa else None

    # ─── Generar / Actualizar ─────────────────────────────────────────────────

    def generar(self, quincena: date, usuario_id: int) -> dict:
        existente = self.db.query(Preliquidacion).filter(
            Preliquidacion.quincena == quincena
        ).first()
        if existente:
            return self.actualizar_quincena(existente, usuario_id)

        preliq = Preliquidacion(quincena=quincena, creado_por=usuario_id)
        self.db.add(preliq)
        self.db.flush()

        filas = self.externa.obtener_tareas_quincena(quincena)
        insertadas = 0

        if filas:
            cache = self._construir_cache(quincena)
            indices_duplicados = self.motor.detectar_duplicados(filas)
            dias_asturiana = self._contar_dias_asturiana(filas)

            lineas_y_reglas = []
            for i, fila in enumerate(filas):
                linea, reglas = self._procesar_fila_con_cache(
                    fila=fila,
                    quincena=quincena,
                    preliquidacion_id=preliq.id,
                    es_duplicado=(i in indices_duplicados),
                    dias_asturiana=dias_asturiana,
                    cache=cache,
                )
                lineas_y_reglas.append((linea, reglas))

            # No optimizable sin RETURNING: cada ConceptoAdicional necesita el
            # linea.id generado por el INSERT de PreliquidacionLinea. Un
            # bulk_insert_mappings evitaría el flush por-fila, pero en MySQL 8
            # (motor real) no soporta RETURNING, así que no devolvería los ids
            # y no podríamos linkear los conceptos sin una query extra (que
            # anularía la ganancia y arriesgaría el orden/matching). Se deja
            # el flush único de abajo, que ya agrupa el add() en un solo lote
            # y hace un solo round-trip de INSERT+flush para todas las líneas.
            for linea, _ in lineas_y_reglas:
                self.db.add(linea)
            self.db.flush()
            insertadas = len(lineas_y_reglas)

            conceptos_auto = []
            for linea, reglas in lineas_y_reglas:
                if reglas:
                    nuevos = self._generar_conceptos_automaticos(linea, reglas)
                    conceptos_auto.extend(nuevos)
                    extra = sum(c.importe for c in nuevos)
                    linea.importe_total = (linea.importe_base or Decimal("0")) + extra

            if conceptos_auto:
                self.db.bulk_save_objects(conceptos_auto)

        self.db.commit()
        self.db.refresh(preliq)
        return {"preliquidacion_id": preliq.id, "insertadas": insertadas, "eliminadas": 0, "sin_cambios": 0}

    def actualizar_quincena(self, preliq: Preliquidacion, usuario_id: int) -> dict:
        quincena = preliq.quincena

        filas_campo = self.externa.obtener_tareas_quincena(quincena)
        claves_campo = {_clave_linea(f): f for f in filas_campo}

        rows = self.db.execute(sql_text("""
            SELECT id, planilla, fecha_tarea, legajo_campo, nombre_empleado,
                   nombre_tarea, nombre_cliente, nombre_finca, nombre_tractor,
                   hsjornal, hsmaquina, tancadas, unidades
            FROM preliquidacion_linea
            WHERE preliquidacion_id = :pid
        """), {"pid": preliq.id}).fetchall()

        claves_existentes = {}
        ids_por_clave = {}
        for row in rows:
            clave = (
                str(row[1] or "").strip().upper(),
                str(row[2] or ""),
                str(row[3] or "").strip(),
                str(row[4] or "").strip().upper(),
                str(row[5] or "").strip().upper(),
                str(row[6] or "").strip().upper(),
                str(row[7] or "").strip().upper(),
                str(row[8] or "").strip().upper(),
                _n(row[9]), _n(row[10]), _n(row[11]), _n(row[12]),
            )
            claves_existentes[clave] = True
            ids_por_clave[clave] = row[0]

        claves_a_eliminar = set(ids_por_clave.keys()) - set(claves_campo.keys())
        eliminadas = 0
        if claves_a_eliminar:
            ids_eliminar = tuple(ids_por_clave[c] for c in claves_a_eliminar)
            self.db.execute(sql_text("DELETE FROM ajuste_manual WHERE linea_id IN :ids"), {"ids": ids_eliminar})
            self.db.execute(sql_text("DELETE FROM concepto_adicional WHERE linea_id IN :ids"), {"ids": ids_eliminar})
            self.db.execute(sql_text("DELETE FROM preliquidacion_linea WHERE id IN :ids"), {"ids": ids_eliminar})
            eliminadas = len(ids_eliminar)

        claves_a_insertar = set(claves_campo.keys()) - set(claves_existentes.keys())
        insertadas = 0

        if claves_a_insertar:
            filas_nuevas = [claves_campo[c] for c in claves_a_insertar]
            cache = self._construir_cache(quincena)
            indices_duplicados = self.motor.detectar_duplicados(filas_nuevas)
            dias_asturiana = self._contar_dias_asturiana(filas_campo)

            nuevas_lineas_y_reglas = []
            for i, fila in enumerate(filas_nuevas):
                linea, reglas = self._procesar_fila_con_cache(
                    fila=fila,
                    quincena=quincena,
                    preliquidacion_id=preliq.id,
                    es_duplicado=(i in indices_duplicados),
                    dias_asturiana=dias_asturiana,
                    cache=cache,
                )
                nuevas_lineas_y_reglas.append((linea, reglas))

            # Mismo motivo que en generar(): no optimizable a bulk_insert sin
            # RETURNING (MySQL 8 real no lo soporta) porque los
            # ConceptoAdicional necesitan el linea.id recién generado.
            for linea, _ in nuevas_lineas_y_reglas:
                self.db.add(linea)
            self.db.flush()
            insertadas = len(nuevas_lineas_y_reglas)

            conceptos_auto = []
            for linea, reglas in nuevas_lineas_y_reglas:
                if reglas:
                    nuevos = self._generar_conceptos_automaticos(linea, reglas)
                    conceptos_auto.extend(nuevos)
                    extra = sum(c.importe for c in nuevos)
                    linea.importe_total = (linea.importe_base or Decimal("0")) + extra

            if conceptos_auto:
                self.db.bulk_save_objects(conceptos_auto)

        sin_cambios = len(claves_existentes) - eliminadas
        self.db.commit()
        return {"preliquidacion_id": preliq.id, "insertadas": insertadas, "eliminadas": eliminadas, "sin_cambios": sin_cambios}

    # ─── Cache en memoria ─────────────────────────────────────────────────────

    def _construir_cache(self, quincena: date) -> dict:
        """
        Cache del maestro unificado para la quincena dada.

        Cuatro caminos de matching (ADR-0011) — sin grupo_pago:
        - comunes:        clave = tarea.upper()
        - por_cliente:    clave = (tarea.upper(), cliente.upper())  [cliente sin finca]
        - especificos:    clave = (tarea.upper(), cliente.upper(), finca.upper())
        - por_supervisor: clave = (tarea.upper(), supervisor.upper())

        Una fila con supervisor va SOLO a por_supervisor (excluyente con
        cliente/finca). El grupo_pago_aplicado de la línea viene del catálogo
        externo, no del maestro de conceptos.
        """
        conceptos = self.db.query(ConceptoLiquidacion).filter(
            ConceptoLiquidacion.quincena == quincena
        ).all()

        cache_comunes, cache_por_cliente, cache_especificos, cache_por_supervisor = \
            self._clasificar_conceptos(conceptos)

        tareas = self.externa.obtener_tareas()
        cache_grupo_tarea = {
            t["nombre"].strip().upper(): (t["grupo_tarea"] or "").strip().upper()
            for t in tareas
        }
        cache_grupo_pago_catalogo = {
            t["nombre"].strip().upper(): (t["grupo_pago"] or "").strip().upper()
            for t in tareas
        }

        return {
            "comunes": cache_comunes,
            "por_cliente": cache_por_cliente,
            "especificos": cache_especificos,
            "por_supervisor": cache_por_supervisor,
            "grupo_tarea": cache_grupo_tarea,
            "grupo_pago_catalogo": cache_grupo_pago_catalogo,
            "categoria_por_cuil": self._categoria_por_cuil(quincena),
        }

    @staticmethod
    def _clasificar_conceptos(conceptos: list) -> tuple:
        """
        Clasifica filas del maestro en los 4 caminos de matching (ADR-0011).
        Devuelve (comunes, por_cliente, especificos, por_supervisor):
        - comunes:        tarea -> [ConceptoLiquidacion]           (sin cliente ni supervisor)
        - por_cliente:    (tarea, cliente) -> [...]                (cliente sin finca)
        - especificos:    (tarea, cliente, finca) -> [...]
        - por_supervisor: (tarea, supervisor) -> [...]             (una fila con supervisor
                          va SOLO acá, aunque tuviera cliente cargado — no debería, el
                          API valida cliente XOR supervisor)
        Compartido entre el path de generación (_construir_cache) y el de
        recálculo reactivo (_cache_conceptos_quincena) para que ambos queden
        consistentes.
        """
        comunes, por_cliente, especificos, por_supervisor = {}, {}, {}, {}
        for c in conceptos:
            t = c.tarea_nombre.strip().upper()
            if c.supervisor_nombre is not None and c.supervisor_nombre.strip():
                sup = c.supervisor_nombre.strip().upper()
                por_supervisor.setdefault((t, sup), []).append(c)
            elif c.cliente_nombre is None:
                comunes.setdefault(t, []).append(c)
            else:
                cl = c.cliente_nombre.strip().upper()
                fn = (c.finca_nombre or "").strip().upper()
                if fn:
                    especificos.setdefault((t, cl, fn), []).append(c)
                else:
                    por_cliente.setdefault((t, cl), []).append(c)
        return comunes, por_cliente, especificos, por_supervisor

    def _categoria_por_cuil(self, quincena: date) -> dict:
        """Mapa {cuil -> categoria} de categoria_operario para la quincena
        (ADR-0008). Alimenta el filtro de conceptos de Mantenimiento mecánico
        por categoría."""
        rows = self.db.query(CategoriaOperario).filter(
            CategoriaOperario.quincena == quincena
        ).all()
        return {r.cuil.strip(): r.categoria for r in rows}

    def _filtrar_por_categoria(self, conceptos: list, cuil, categoria_por_cuil: dict) -> list:
        """Un concepto con categoria=NULL pasa siempre (comportamiento actual
        intacto). Un concepto con categoria=X pasa solo si la persona de la
        línea (por CUIL) tiene esa categoría asignada en la quincena."""
        categoria_persona = categoria_por_cuil.get((cuil or "").strip())
        return [c for c in conceptos if c.categoria is None or c.categoria == categoria_persona]

    def _aplicar_reemplazo_comun(self, no_comunes: list, com: list) -> list:
        """
        WS11 / ADR-0011: `no_comunes` es la lista unificada de reglas NO
        comunes que matchean la línea (específicos + por cliente + por
        supervisor). Si CUALQUIERA de ellas tiene reemplaza_comun=True, se
        descartan SOLO los comunes (com) — los niveles no-comunes nunca se
        apagan entre sí. Si ninguna lo tiene, todos suman (no_comunes + com).
        Compartido entre el path de generación (_buscar_conceptos_cache) y el
        de recálculo (_aplicar_conceptos_a_lineas).
        """
        if any(c.reemplaza_comun for c in no_comunes):
            return no_comunes
        return no_comunes + com

    def _buscar_conceptos_cache(
        self, tarea: str, cliente: str, finca: str, cache: dict, cuil: str = None,
        supervisor: str = None,
    ) -> list:
        """
        Devuelve todas las reglas que matchean esta línea, juntando los 4
        caminos (ADR-0011): específicos (tarea+cliente+finca), por cliente
        (tarea+cliente, cualquier finca), por supervisor (tarea+supervisor)
        y comunes (tarea sola). Los 4 SUMAN, salvo que alguna regla no-común
        tenga el tilde reemplaza_comun: en ese caso se descartan SOLO los
        comunes. Además, filtra por categoría (ADR-0008) en todos los niveles:
        reglas con categoria=NULL pasan siempre, reglas con categoria=X solo
        si el cuil dado tiene esa categoría asignada en la quincena.
        """
        t   = tarea.strip().upper()
        cl  = (cliente or "").strip().upper()
        fn  = (finca or "").strip().upper()
        sup = (supervisor or "").strip().upper()

        esp     = cache["especificos"].get((t, cl, fn), [])
        por_cli = cache["por_cliente"].get((t, cl), []) if cl else []
        por_sup = cache["por_supervisor"].get((t, sup), []) if sup else []
        com     = cache["comunes"].get(t, [])
        categoria_por_cuil = cache.get("categoria_por_cuil", {})
        no_comunes = self._filtrar_por_categoria(esp + por_cli + por_sup, cuil, categoria_por_cuil)
        com        = self._filtrar_por_categoria(com, cuil, categoria_por_cuil)
        return self._aplicar_reemplazo_comun(no_comunes, com)

    def _procesar_fila_con_cache(
        self,
        fila: dict,
        quincena: date,
        preliquidacion_id: int,
        es_duplicado: bool,
        dias_asturiana: dict,
        cache: dict,
        nuevos_conceptos: dict = None,  # ya no se usa, se mantiene por compatibilidad
    ):
        legajo         = str(fila.get("legajo", "") or "")
        nombre_cliente = fila.get("nombre_cliente", "") or ""
        nombre_finca   = fila.get("nombre_finca", "") or ""
        nombre_tarea   = fila.get("nombre_tarea", "") or ""

        dias_en_ast     = dias_asturiana.get(legajo, 0)
        nombre_empleado = fila.get("nombre_empleado", "") or ""
        grupo_tarea_linea = cache["grupo_tarea"].get(nombre_tarea.strip().upper(), "")

        empresa, alerta_empresa = self.motor.resolver_empresa(
            nombre_cliente, nombre_tarea, legajo, dias_en_ast, nombre_empleado, grupo_tarea_linea
        )
        legajo_asignado, alerta_legajo = self._resolver_legajo_cache(legajo, empresa, cache)
        alerta_legajo = alerta_legajo or alerta_empresa

        # grupo_pago es informativo (control de PLANTA); no participa del cálculo de importe
        grupo_pago = cache["grupo_pago_catalogo"].get(nombre_tarea.strip().upper(), "")

        # Buscar reglas del maestro: los 4 caminos suman (ADR-0011), filtradas
        # por categoría de la persona (ADR-0008)
        cuil = str(fila.get("cuit", "") or "")
        nombre_supervisor = fila.get("nombre_supervisor", "") or ""
        reglas = self._buscar_conceptos_cache(
            nombre_tarea, nombre_cliente, nombre_finca, cache, cuil=cuil,
            supervisor=nombre_supervisor,
        )
        reglas_con_codigo = [r for r in reglas if r.codigo is not None]
        # Completa = tiene código Y precio (lo único que realmente genera un
        # ConceptoAdicional); un código sin precio no cuenta como completa.
        reglas_completas = [r for r in reglas_con_codigo if r.precio is not None]
        linea_incompleta = len(reglas_completas) == 0
        codigo_liquidacion = reglas_completas[0].codigo if reglas_completas else None

        # precio_a: primera regla con precio definido (para importe base)
        precio_a = next((r.precio for r in reglas if r.precio is not None), None)

        hsjornal  = self._to_decimal(fila.get("hsjornal"))
        tancadas  = self._to_decimal(fila.get("tancadas"))
        unidades  = self._to_decimal(fila.get("unidades"))

        # importe_base = 0 siempre — el total es la suma de ConceptoAdicional
        importe_base = Decimal("0")

        linea = PreliquidacionLinea(
            preliquidacion_id=preliquidacion_id,
            planilla=fila.get("planilla"),
            fecha_tarea=fila.get("fecha_tarea"),
            nombre_cliente=nombre_cliente,
            nombre_finca=nombre_finca,
            nombre_tarea=nombre_tarea,
            nombre_tractor=fila.get("nombre_tractor"),
            legajo_campo=legajo,
            nombre_empleado=fila.get("nombre_empleado"),
            cuit=str(fila.get("cuit", "") or ""),
            nombre_supervisor=fila.get("nombre_supervisor"),
            nombre_capataz=fila.get("nombre_capataz"),
            implemento=fila.get("implemento"),
            unidades=unidades,
            tancadas=tancadas,
            hsjornal=hsjornal,
            hsmaquina=self._to_decimal(fila.get("hsmaquina")),
            cantidad=self._to_decimal(fila.get("cantidad")),
            empresa_asignada=empresa,
            legajo_asignado=legajo_asignado,
            grupo_pago_aplicado=grupo_pago,
            codigo_liquidacion=codigo_liquidacion,
            precio_a=precio_a,
            importe_base=Decimal("0"),
            importe_total=Decimal("0"),
            es_duplicado=es_duplicado,
            alerta_legajo=alerta_legajo,
            alerta_empresa=alerta_empresa,
            linea_incompleta=linea_incompleta,
        )
        return linea, reglas_con_codigo

    def _generar_conceptos_automaticos(self, linea, reglas) -> list:
        conceptos = []
        for regla in reglas:
            # Un concepto sin precio NO genera fila: evita pagar 0 en silencio.
            # (La marca de "línea incompleta" se unifica en WS3.)
            if regla.precio is None:
                continue
            unidad = regla.unidad_base.value if hasattr(regla.unidad_base, "value") else regla.unidad_base
            cantidad = self.motor.calcular_cantidad_concepto(
                unidad_base=unidad,
                hsjornal=linea.hsjornal,
                hsmaquina=linea.hsmaquina,
                tancadas=linea.tancadas,
                unidades=linea.unidades,
            )
            importe = (cantidad * regla.precio).quantize(Decimal("0.01"))
            conceptos.append(ConceptoAdicional(
                linea_id=linea.id,
                descripcion=f"Concepto {regla.codigo}",
                codigo_concepto=regla.codigo,
                tipo=regla.tipo,
                unidad_base=unidad,
                precio=regla.precio,
                cantidad=cantidad,
                concepto_liquidacion_id=regla.id,
                importe=importe,
                ingresado_por=None,
            ))
        return conceptos

    def _resolver_legajo_cache(self, legajo_campo, empresa_asignada, cache):
        if self.sueldos:
            return self.sueldos.resolver_legajo(legajo_campo, empresa_asignada)
        return legajo_campo, False

    def _contar_dias_asturiana(self, filas):
        pares = {
            (str(fila.get("legajo", "")), fila.get("fecha_tarea"))
            for fila in filas
            if str(fila.get("nombre_cliente", "")).upper() != "CITRUSVIL"
            and fila.get("legajo") and fila.get("fecha_tarea")
        }
        resultado = {}
        for legajo, _ in pares:
            resultado[legajo] = resultado.get(legajo, 0) + 1
        return resultado

    def _to_decimal(self, valor) -> Optional[Decimal]:
        if valor is None:
            return None
        try:
            return Decimal(str(valor))
        except Exception:
            return None

    # ─── Aplicar conceptos ────────────────────────────────────────────────────

    def _cache_conceptos_quincena(self, quincena):
        """Cache de los 4 caminos del maestro vigente para una quincena (solo
        con código). Devuelve (comunes, por_cliente, especificos, por_supervisor)
        con la misma clasificación que _construir_cache (ADR-0011)."""
        conceptos = self.db.query(ConceptoLiquidacion).filter(
            ConceptoLiquidacion.quincena == quincena,
            ConceptoLiquidacion.codigo.isnot(None),
        ).all()
        return self._clasificar_conceptos(conceptos)

    def _aplicar_conceptos_a_lineas(self, quincena, lineas: list) -> dict:
        """
        Reconstruye los ConceptoAdicional automáticos de las líneas dadas según
        el maestro vigente de esa quincena, y recalcula su importe_total.
        Preserva los conceptos manuales (ingresado_por is not None).
        """
        if not lineas:
            return {"actualizadas": 0, "sin_reglas": 0}

        linea_ids = [l.id for l in lineas]

        # Snapshot del importe manual de cada línea ANTES de tocar la sesión.
        # linea.conceptos ya viene con joinedload desde el caller: no dispara queries.
        importe_manual = {
            l.id: sum(
                (c.importe for c in l.conceptos
                 if c.ingresado_por is not None and c.importe is not None),
                Decimal("0"),
            )
            for l in lineas
        }

        # Borrar automáticos existentes de esas líneas SIN COMMIT: nos quedamos en la
        # misma transacción para que los objetos ya cargados no expiren (evita N+1).
        self.db.query(ConceptoAdicional).filter(
            ConceptoAdicional.linea_id.in_(linea_ids),
            ConceptoAdicional.ingresado_por.is_(None),
        ).delete(synchronize_session=False)

        cache_comunes, cache_por_cliente, cache_especificos, cache_por_supervisor = \
            self._cache_conceptos_quincena(quincena)
        categoria_por_cuil = self._categoria_por_cuil(quincena)

        actualizadas = sin_reglas = 0
        conceptos_nuevos = []

        for linea in lineas:
            t   = (linea.nombre_tarea       or "").strip().upper()
            cl  = (linea.nombre_cliente     or "").strip().upper()
            fn  = (linea.nombre_finca       or "").strip().upper()
            sup = (linea.nombre_supervisor  or "").strip().upper()

            esp     = cache_especificos.get((t, cl, fn), [])
            por_cli = cache_por_cliente.get((t, cl), []) if cl else []
            por_sup = cache_por_supervisor.get((t, sup), []) if sup else []
            com     = cache_comunes.get(t, [])
            no_comunes = self._filtrar_por_categoria(esp + por_cli + por_sup, linea.cuit, categoria_por_cuil)
            com        = self._filtrar_por_categoria(com, linea.cuit, categoria_por_cuil)
            reglas = self._aplicar_reemplazo_comun(no_comunes, com)

            # nuevos ya viene filtrado por precio (ver _generar_conceptos_automaticos):
            # una línea solo está completa si al menos una regla generó un concepto real.
            nuevos = self._generar_conceptos_automaticos(linea, reglas) if reglas else []
            manual = importe_manual.get(linea.id, Decimal("0"))

            if not nuevos:
                linea.codigo_liquidacion = None
                linea.importe_total      = manual
                if not linea.linea_incompleta:
                    linea.linea_incompleta = True
                    actualizadas += 1
                else:
                    sin_reglas += 1
                continue

            conceptos_nuevos.extend(nuevos)
            linea.codigo_liquidacion = nuevos[0].codigo_concepto
            linea.linea_incompleta   = False
            linea.importe_total      = manual + sum(n.importe for n in nuevos)
            actualizadas += 1

        if conceptos_nuevos:
            self.db.bulk_save_objects(conceptos_nuevos)
        self.db.commit()

        return {"actualizadas": actualizadas, "sin_reglas": sin_reglas}

    def aplicar_conceptos(self, preliq_id: int) -> dict:
        """
        Recalcula TODA la quincena con el maestro vigente. No es un paso del
        flujo del liquidador (el impacto del maestro es reactivo, ver
        recalcular_por_concepto) — uso interno, ej. tras copiar conceptos
        de otra quincena (ver precios.py, copiar_quincena).
        """
        preliq = self.db.query(Preliquidacion).filter(
            Preliquidacion.id == preliq_id
        ).first()
        if not preliq:
            raise ValueError(f"Preliquidacion {preliq_id} no encontrada")

        lineas = self.db.query(PreliquidacionLinea).filter(
            PreliquidacionLinea.preliquidacion_id == preliq_id,
        ).options(joinedload(PreliquidacionLinea.conceptos)).all()

        return self._aplicar_conceptos_a_lineas(preliq.quincena, lineas)

    # ─── Impacto reactivo del maestro (ADR-0002) ─────────────────────────────

    def _lineas_por_match(self, preliq_id, tarea_nombre, cliente_nombre=None,
                          finca_nombre=None, supervisor_nombre=None) -> list:
        """Líneas de una preliquidación que matchean el alcance de una regla
        (ADR-0011): tarea sola (común), tarea+supervisor (por supervisor),
        tarea+cliente en cualquier finca (por cliente, finca_nombre vacío) o
        tarea+cliente+finca (específico)."""
        t = (tarea_nombre or "").strip().upper()
        lineas = self.db.query(PreliquidacionLinea).filter(
            PreliquidacionLinea.preliquidacion_id == preliq_id,
            func.upper(func.trim(PreliquidacionLinea.nombre_tarea)) == t,
        ).options(joinedload(PreliquidacionLinea.conceptos)).all()

        if supervisor_nombre:
            sup = supervisor_nombre.strip().upper()
            lineas = [l for l in lineas if (l.nombre_supervisor or "").strip().upper() == sup]
        if cliente_nombre:
            cl = cliente_nombre.strip().upper()
            lineas = [l for l in lineas if (l.nombre_cliente or "").strip().upper() == cl]
            if finca_nombre:
                fn = finca_nombre.strip().upper()
                lineas = [l for l in lineas if (l.nombre_finca or "").strip().upper() == fn]
        return lineas

    def recalcular_por_concepto(self, quincena, actual: dict, anterior: dict = None) -> dict:
        """
        Impacto reactivo de un concepto creado/editado/borrado: recalcula las
        líneas que matchean su estado actual y, si sus claves de match
        (tarea/cliente/finca/supervisor) cambiaron, también las que matcheaba
        antes (unión) — evita ConceptoAdicional fantasma en líneas que dejaron
        de matchear.
        """
        preliq = self.db.query(Preliquidacion).filter(
            Preliquidacion.quincena == quincena
        ).first()
        if not preliq:
            return {"lineas_afectadas": 0}

        vistas = {}
        for clave in filter(None, [actual, anterior]):
            for linea in self._lineas_por_match(
                preliq.id,
                clave.get("tarea_nombre"),
                clave.get("cliente_nombre"),
                clave.get("finca_nombre"),
                clave.get("supervisor_nombre"),
            ):
                vistas[linea.id] = linea

        lineas = list(vistas.values())
        resultado = self._aplicar_conceptos_a_lineas(preliq.quincena, lineas)
        return {"lineas_afectadas": len(lineas), **resultado}

    # ─── Mantenimiento mecánico por categoría (ADR-0008) ─────────────────────

    def _tareas_con_categoria(self, quincena: date) -> list:
        """Nombres de tarea (normalizados) que en el maestro de esa quincena
        tienen al menos un concepto con categoria NOT NULL — son las tareas
        de "taller" que dependen de la categoría del operario."""
        rows = self.db.query(ConceptoLiquidacion.tarea_nombre).filter(
            ConceptoLiquidacion.quincena == quincena,
            ConceptoLiquidacion.categoria.isnot(None),
        ).distinct().all()
        return [r[0].strip().upper() for r in rows if r[0]]

    def recalcular_por_categoria(self, quincena: date, cuil: str) -> dict:
        """
        Impacto reactivo de cambiar la categoría asignada a una persona:
        regenera las líneas de esa quincena, de esa persona (por CUIL), cuya
        tarea tenga conceptos por categoría en el maestro vigente. Reusa
        _aplicar_conceptos_a_lineas (borra automáticos, preserva manuales).
        """
        preliq = self.db.query(Preliquidacion).filter(
            Preliquidacion.quincena == quincena
        ).first()
        if not preliq:
            return {"lineas_afectadas": 0}

        tareas = self._tareas_con_categoria(quincena)
        if not tareas:
            return {"lineas_afectadas": 0}

        cuil_norm = (cuil or "").strip().upper()
        lineas = self.db.query(PreliquidacionLinea).filter(
            PreliquidacionLinea.preliquidacion_id == preliq.id,
            func.upper(func.trim(PreliquidacionLinea.cuit)) == cuil_norm,
            func.upper(func.trim(PreliquidacionLinea.nombre_tarea)).in_(tareas),
        ).options(joinedload(PreliquidacionLinea.conceptos)).all()

        resultado = self._aplicar_conceptos_a_lineas(preliq.quincena, lineas)
        return {"lineas_afectadas": len(lineas), **resultado}

    def operarios_mantenimiento(self, preliq_id: int) -> list:
        """
        Personas (agrupadas por CUIL) que tienen líneas de "taller" en la
        quincena — es decir, líneas cuya tarea matchea algún concepto del
        maestro con categoria NOT NULL. Incluye la categoría ya asignada
        (o None si todavía no se asignó).
        """
        preliq = self.obtener(preliq_id)
        if not preliq:
            raise ValueError(f"Preliquidacion {preliq_id} no encontrada")

        tareas = self._tareas_con_categoria(preliq.quincena)
        if not tareas:
            return []

        lineas = self.db.query(PreliquidacionLinea).filter(
            PreliquidacionLinea.preliquidacion_id == preliq_id,
            func.upper(func.trim(PreliquidacionLinea.nombre_tarea)).in_(tareas),
        ).all()

        categoria_por_cuil = self._categoria_por_cuil(preliq.quincena)

        por_cuil = {}
        for linea in lineas:
            cuil = (linea.cuit or "").strip()
            if not cuil:
                continue
            if cuil not in por_cuil:
                por_cuil[cuil] = {
                    "cuil": cuil,
                    "nombre_empleado": linea.nombre_empleado,
                    "legajo": linea.legajo_asignado,
                    "categoria": categoria_por_cuil.get(cuil),
                }

        resultado = list(por_cuil.values())
        resultado.sort(key=lambda x: (x["nombre_empleado"] or ""))
        return resultado

    def set_categoria_operario(self, preliq_id: int, cuil: str, categoria: Optional[int]) -> dict:
        """
        Upsert de la categoría de una persona para la quincena de esta
        preliquidación. categoria=None borra la asignación (la persona vuelve
        a no tener categoría asignada). Dispara el recálculo reactivo de sus
        líneas de taller.
        """
        preliq = self.obtener(preliq_id)
        if not preliq:
            raise ValueError(f"Preliquidacion {preliq_id} no encontrada")

        cuil_norm = (cuil or "").strip()
        if not cuil_norm:
            raise ValueError("Se requiere cuil")

        existente = self.db.query(CategoriaOperario).filter(
            CategoriaOperario.quincena == preliq.quincena,
            CategoriaOperario.cuil == cuil_norm,
        ).first()

        if categoria is None:
            if existente:
                self.db.delete(existente)
                self.db.commit()
        else:
            if existente:
                existente.categoria = categoria
            else:
                self.db.add(CategoriaOperario(
                    quincena=preliq.quincena, cuil=cuil_norm, categoria=categoria,
                ))
            self.db.commit()

        resultado = self.recalcular_por_categoria(preliq.quincena, cuil_norm)
        return {
            "cuil": cuil_norm,
            "categoria": categoria,
            "lineas_afectadas": resultado["lineas_afectadas"],
        }

    def heredar_categorias_operario(self, preliq_id: int) -> dict:
        """
        Copia las asignaciones de categoria_operario de la quincena
        inmediatamente anterior (la mayor quincena con asignaciones cargadas,
        anterior a la actual) hacia la quincena de esta preliquidación —
        solo para los CUIL que todavía no tengan asignación en la actual.
        Recalcula las líneas de las personas heredadas.
        """
        preliq = self.obtener(preliq_id)
        if not preliq:
            raise ValueError(f"Preliquidacion {preliq_id} no encontrada")

        fila_anterior = self.db.query(CategoriaOperario.quincena).filter(
            CategoriaOperario.quincena < preliq.quincena
        ).order_by(CategoriaOperario.quincena.desc()).first()
        if not fila_anterior:
            return {"heredados": 0}
        quincena_anterior = fila_anterior[0]

        existentes_actual = {
            r[0] for r in self.db.query(CategoriaOperario.cuil).filter(
                CategoriaOperario.quincena == preliq.quincena
            ).all()
        }

        asignaciones_anteriores = self.db.query(CategoriaOperario).filter(
            CategoriaOperario.quincena == quincena_anterior
        ).all()

        cuils_heredados = []
        for asignacion in asignaciones_anteriores:
            if asignacion.cuil in existentes_actual:
                continue
            self.db.add(CategoriaOperario(
                quincena=preliq.quincena, cuil=asignacion.cuil, categoria=asignacion.categoria,
            ))
            cuils_heredados.append(asignacion.cuil)
        self.db.commit()

        # Recálculo en un solo lote (antes: un recalcular_por_categoria por
        # CUIL heredado, cada uno reconstruyendo caches y commiteando aparte).
        # Mismo resultado: unimos las líneas de taller de TODOS los CUIL
        # heredados y aplicamos los conceptos una única vez.
        if cuils_heredados:
            tareas = self._tareas_con_categoria(preliq.quincena)
            if tareas:
                cuils_norm = {(c or "").strip().upper() for c in cuils_heredados}
                lineas = self.db.query(PreliquidacionLinea).filter(
                    PreliquidacionLinea.preliquidacion_id == preliq.id,
                    func.upper(func.trim(PreliquidacionLinea.cuit)).in_(cuils_norm),
                    func.upper(func.trim(PreliquidacionLinea.nombre_tarea)).in_(tareas),
                ).options(joinedload(PreliquidacionLinea.conceptos)).all()
                if lineas:
                    self._aplicar_conceptos_a_lineas(preliq.quincena, lineas)

        return {"heredados": len(cuils_heredados)}

    # ─── Dashboard de verificación ────────────────────────────────────────────

    def dashboard_verificacion(self, preliq_id: int) -> dict:
        # Sin joinedload(conceptos): este método no lee linea.conceptos en
        # ningún punto, así que el joinedload solo multiplicaba filas sin uso.
        lineas = self.db.query(PreliquidacionLinea).filter(
            PreliquidacionLinea.preliquidacion_id == preliq_id
        ).all()

        # El caller ya no hace el obtener() previo (costaba un round-trip por
        # carga); solo se verifica existencia si la quincena vino vacía.
        if not lineas and not self.obtener(preliq_id):
            raise ValueError(f"Preliquidacion {preliq_id} no encontrada")

        por_empleado_fecha = {}
        for linea in lineas:
            legajo = linea.legajo_asignado or linea.legajo_campo or ""
            fecha  = str(linea.fecha_tarea) if linea.fecha_tarea else ""
            clave  = (legajo, fecha)
            if clave not in por_empleado_fecha:
                por_empleado_fecha[clave] = {
                    "legajo": legajo, "nombre_empleado": linea.nombre_empleado,
                    "fecha": fecha, "hsjornal": Decimal("0"),
                    "tancadas": Decimal("0"), "plantas": Decimal("0"), "lineas": [],
                }
            g = por_empleado_fecha[clave]
            g["hsjornal"] += linea.hsjornal or Decimal("0")
            g["tancadas"] += linea.tancadas or Decimal("0")
            if (linea.grupo_pago_aplicado or "").strip().upper() == "PLANTA":
                g["plantas"] += linea.unidades or Decimal("0")
            g["lineas"].append({
                "id": linea.id, "nombre_tarea": linea.nombre_tarea,
                "nombre_cliente": linea.nombre_cliente, "nombre_finca": linea.nombre_finca,
                "grupo_pago_aplicado": linea.grupo_pago_aplicado,
                "hsjornal": float(linea.hsjornal or 0),
                "tancadas": float(linea.tancadas or 0),
                "unidades": float(linea.unidades or 0),
            })

        exceso_horas = exceso_tancadas = exceso_plantas = []
        exceso_horas    = [{"legajo": g["legajo"], "nombre_empleado": g["nombre_empleado"], "fecha": g["fecha"], "lineas": g["lineas"], "valor": float(g["hsjornal"])} for g in por_empleado_fecha.values() if g["hsjornal"] > 13]
        exceso_tancadas = [{"legajo": g["legajo"], "nombre_empleado": g["nombre_empleado"], "fecha": g["fecha"], "lineas": g["lineas"], "valor": float(g["tancadas"])} for g in por_empleado_fecha.values() if g["tancadas"] > 35]
        exceso_plantas  = [{"legajo": g["legajo"], "nombre_empleado": g["nombre_empleado"], "fecha": g["fecha"], "lineas": g["lineas"], "valor": float(g["plantas"])}  for g in por_empleado_fecha.values() if g["plantas"] > 6000]
        for lst in [exceso_horas, exceso_tancadas, exceso_plantas]:
            lst.sort(key=lambda x: -x["valor"])

        por_empleado = {}
        for linea in lineas:
            legajo = linea.legajo_asignado or linea.legajo_campo or ""
            if legajo not in por_empleado:
                por_empleado[legajo] = {
                    "legajo": legajo, "nombre_empleado": linea.nombre_empleado,
                    "empresa_asignada": linea.empresa_asignada,
                    "importe_total": Decimal("0"), "fechas": set(), "lineas": [],
                }
            emp = por_empleado[legajo]
            emp["importe_total"] += linea.importe_total or Decimal("0")
            if linea.fecha_tarea:
                emp["fechas"].add(str(linea.fecha_tarea))
            emp["lineas"].append({
                "id": linea.id,
                "fecha_tarea": str(linea.fecha_tarea) if linea.fecha_tarea else None,
                "nombre_tarea": linea.nombre_tarea, "nombre_cliente": linea.nombre_cliente,
                "nombre_finca": linea.nombre_finca, "hsjornal": float(linea.hsjornal or 0),
                "importe_total": float(linea.importe_total or 0),
            })

        resumen_empleados = []
        for emp in por_empleado.values():
            dias = len(emp["fechas"])
            importe = float(emp["importe_total"])
            resumen_empleados.append({
                "legajo": emp["legajo"], "nombre_empleado": emp["nombre_empleado"],
                "empresa_asignada": emp["empresa_asignada"], "importe_total": importe,
                "dias_trabajados": dias,
                "importe_por_dia": round(importe / dias, 2) if dias else 0,
                "lineas": sorted(emp["lineas"], key=lambda l: l["fecha_tarea"] or ""),
            })
        resumen_empleados.sort(key=lambda x: -x["importe_total"])

        return {
            "exceso_horas": exceso_horas, "exceso_tancadas": exceso_tancadas,
            "exceso_plantas": exceso_plantas, "resumen_empleados": resumen_empleados,
        }

    # ─── Controles de razonabilidad (Plantas / Tancadas vs Jornal) ────────────

    def _sumar_por_unidad_base(self, preliq_id: int, unidad_base: str, columnas: list,
                               grupo_pago: str = None) -> list:
        """Agregado en SQL (GROUP BY) de las líneas que tienen al menos un
        concepto aplicado con esa unidad base (ej. "unidades", "tancadas").

        `grupo_pago` (opcional) acota además por grupo de pago de la línea.
        Es necesario para PLANTAS: la unidad base "unidades" la comparten las
        plantas y la carga de fruta por bins, así que filtrar solo por unidad
        base metía los bins en la tabla Plantas vs Jornal. El grupo de pago
        "PLANTA" es el que distingue el trabajo de planta real (mismo marcador
        que usa el exceso de plantas del dashboard).

        Antes traía las líneas completas a Python y sumaba ahí; ahora suma
        directo en SQL por (cliente, finca, tarea). Devuelve tuplas
        (nombre_cliente, nombre_finca, nombre_tarea, suma_col1, suma_col2, ...)
        en el orden de `columnas`.
        """
        filtros = [
            PreliquidacionLinea.preliquidacion_id == preliq_id,
            ConceptoAdicional.unidad_base == unidad_base,
        ]
        if grupo_pago is not None:
            filtros.append(
                func.upper(func.trim(PreliquidacionLinea.grupo_pago_aplicado)) == grupo_pago.strip().upper()
            )
        ids_subq = (
            self.db.query(PreliquidacionLinea.id)
            .join(ConceptoAdicional, ConceptoAdicional.linea_id == PreliquidacionLinea.id)
            .filter(*filtros)
        )
        sumas = [func.sum(getattr(PreliquidacionLinea, col)) for col in columnas]
        return (
            self.db.query(
                PreliquidacionLinea.nombre_cliente,
                PreliquidacionLinea.nombre_finca,
                PreliquidacionLinea.nombre_tarea,
                *sumas,
            )
            .filter(PreliquidacionLinea.id.in_(ids_subq))
            .group_by(
                PreliquidacionLinea.nombre_cliente,
                PreliquidacionLinea.nombre_finca,
                PreliquidacionLinea.nombre_tarea,
            )
            .all()
        )

    def _precio_comun_especial(self, precio_esp: dict, precio_com: dict, tarea, cliente, finca):
        """Separa el precio del maestro para (tarea,cliente,finca) en común
        (tarea, cliente_nombre IS NULL) y especial (cliente+finca exactos),
        cada uno como Decimal promedio o None si no hay ninguno cargado.
        Reusa los mismos caches (precio_esp/precio_com) que ya arma
        precio_planta / precio_tancada, solo expone los dos valores por
        separado en vez de "especial si hay, si no común"."""
        t  = (tarea or "").strip().upper()
        cl = (cliente or "").strip().upper()
        fn = (finca or "").strip().upper()
        precios_com = precio_com.get(t)
        precios_esp = precio_esp.get((t, cl, fn))
        comun    = (sum(precios_com) / len(precios_com)) if precios_com else None
        especial = (sum(precios_esp) / len(precios_esp)) if precios_esp else None
        return comun, especial

    def _var_pct(self, comun, especial) -> Optional[float]:
        if comun is None or especial is None or comun == 0:
            return None
        return round(float((especial - comun) / comun), 4)

    def control_plantas_jornal(self, preliq_id: int) -> dict:
        preliq = self.db.query(Preliquidacion).filter(
            Preliquidacion.id == preliq_id
        ).first()
        if not preliq:
            raise ValueError(f"Preliquidacion {preliq_id} no encontrada")

        # Las líneas de este control son las de trabajo de PLANTA: concepto
        # aplicado con unidad_base = "unidades" Y grupo de pago "PLANTA". La
        # unidad "unidades" sola no alcanza porque la carga de fruta por bins
        # también se paga por unidades y se colaba en esta tabla; el grupo de
        # pago "PLANTA" es el que distingue la planta real (excluye los bins).
        agregados = self._sumar_por_unidad_base(preliq_id, "unidades", ["unidades", "hsmaquina"],
                                                grupo_pago="PLANTA")

        # Precio por planta: del PAGO REAL (Σ importe / Σ cantidad de los
        # conceptos adicionales con unidad "unidades"), NO del maestro. El
        # matching ya lo hizo el motor al pagar — venga el precio del camino
        # que venga (común, por cliente, específico o por supervisor, ADR-0011),
        # acá solo se lee el snapshot congelado. La comparativa común vs
        # especial que vivía acá se eliminó (se rearmará aparte).
        pagos = {}   # (cliente, finca, tarea) -> [Σ importe, Σ cantidad]
        for cliente, finca, tarea, imp, cant in (
            self.db.query(
                PreliquidacionLinea.nombre_cliente,
                PreliquidacionLinea.nombre_finca,
                PreliquidacionLinea.nombre_tarea,
                func.sum(ConceptoAdicional.importe),
                func.sum(ConceptoAdicional.cantidad),
            )
            .join(ConceptoAdicional, ConceptoAdicional.linea_id == PreliquidacionLinea.id)
            .filter(
                PreliquidacionLinea.preliquidacion_id == preliq_id,
                ConceptoAdicional.unidad_base == "unidades",
                func.upper(func.trim(PreliquidacionLinea.grupo_pago_aplicado)) == "PLANTA",
            )
            .group_by(
                PreliquidacionLinea.nombre_cliente,
                PreliquidacionLinea.nombre_finca,
                PreliquidacionLinea.nombre_tarea,
            )
            .all()
        ):
            pagos[(cliente, finca, tarea)] = [float(imp or 0), float(cant or 0)]

        # Valor de la jornada de 8 hs cargado por el liquidador (sin recargo).
        # Sin cargar, las columnas de comparación van en null (no 0, para no
        # mentir) — mismo criterio que valor_hora_pulv en Tancadas.
        vj = float(preliq.valor_jornal_planta) if preliq.valor_jornal_planta is not None else None

        filas = []
        for cliente, finca, tarea, suma_unidades, suma_hs in agregados:
            importe_pagado, cantidad_pagada = pagos.get((cliente, finca, tarea), [0.0, 0.0])
            pp = (importe_pagado / cantidad_pagada) if cantidad_pagada else 0.0
            u  = float(suma_unidades or 0); h = float(suma_hs or 0)
            phsm = (u / h) if h else 0
            prom_jornal = phsm * 8 * pp        # costo de una jornada pagada por planta
            jornadas = h / 8
            total_jornal = (jornadas * vj) if vj is not None else None
            # Signo como en Tancadas: (pagado por planta − a jornal) / a jornal.
            diff_total = diff_total_pct = None
            if total_jornal:
                diff_total     = round(importe_pagado - total_jornal, 2)
                diff_total_pct = round((importe_pagado - total_jornal) / total_jornal, 4)
            diff_jornada_pct = (
                round((prom_jornal - vj) / vj, 4) if (vj and h) else None
            )
            filas.append({
                "nombre_cliente": cliente, "nombre_finca": finca,
                "nombre_tarea": tarea, "precio_promedio": round(pp, 2),
                "unidades": round(u, 2), "hs": round(h, 2),
                "plantas_por_hsm": round(phsm, 2), "plantas_por_hsm_x8": round(phsm * 8, 2),
                "prom_jornal": round(prom_jornal, 2),
                "total_planta": round(importe_pagado, 2),
                "jornadas": round(jornadas, 2),
                "total_jornal": round(total_jornal, 2) if total_jornal is not None else None,
                "diff_total": diff_total,
                "diff_total_pct": diff_total_pct,
                "diff_jornada_pct": diff_jornada_pct,
            })
        filas.sort(key=lambda f: (f["nombre_cliente"] or "", f["nombre_finca"] or "", f["nombre_tarea"] or ""))

        # Totales recalculados sobre las sumas (NO promedio de los % por fila,
        # que mentiría).
        tu = sum(f["unidades"] for f in filas); th = sum(f["hs"] for f in filas)
        ttp = sum(f["total_planta"] for f in filas)
        tcant = sum(pagos[k][1] for k in pagos)
        tprecio = (ttp / tcant) if tcant else 0
        tphsm = (tu / th) if th else 0
        tjornadas = th / 8
        ttj = (tjornadas * vj) if vj is not None else None
        tdiff = tdiff_pct = None
        if ttj:
            tdiff     = round(ttp - ttj, 2)
            tdiff_pct = round((ttp - ttj) / ttj, 4)
        return {
            "valor_jornal_planta": vj,
            "filas": filas,
            "totales": {
                "unidades": round(tu, 2), "hs": round(th, 2),
                "precio_promedio": round(tprecio, 2), "plantas_por_hsm": round(tphsm, 2),
                "plantas_por_hsm_x8": round(tphsm * 8, 2),
                "prom_jornal": round(tphsm * 8 * tprecio, 2),
                "total_planta": round(ttp, 2),
                "jornadas": round(tjornadas, 2),
                "total_jornal": round(ttj, 2) if ttj is not None else None,
                "diff_total": tdiff,
                "diff_total_pct": tdiff_pct,
            },
        }

    def set_valor_jornal_planta(self, preliq_id: int, valor):
        """Setea (o limpia con None) el valor de la jornada de 8 hs del control
        Plantas vs Jornal. Devuelve la Preliquidacion actualizada."""
        preliq = self.obtener(preliq_id)
        if not preliq:
            raise ValueError(f"Preliquidacion {preliq_id} no encontrada")
        preliq.valor_jornal_planta = valor
        self.db.commit()
        self.db.refresh(preliq)
        return preliq

    # Recargo fijo de pulverización sobre el valor hora de jornal (ADR-0007).
    RECARGO_PULV = Decimal("1.3")

    def control_tancadas_jornal(self, preliq_id: int) -> dict:
        """Compara, por (cliente, finca, tarea), lo que costó pagar el trabajo
        "a tancada" contra lo que habría costado "a jornal" de pulverización.
        La tancada se cuenta ida y vuelta, así que el dato viene doblado y se
        divide /2 al valorizar (ver glosario: Tancada)."""
        preliq = self.db.query(Preliquidacion).filter(
            Preliquidacion.id == preliq_id
        ).first()
        if not preliq:
            raise ValueError(f"Preliquidacion {preliq_id} no encontrada")

        agregados = self._sumar_por_unidad_base(preliq_id, "tancadas", ["tancadas", "hsjornal", "hsmaquina"])

        # Precio de la tancada: del maestro (concepto con unidad_base = tancadas),
        # promedio de específicos + comunes de la quincena. Misma mecánica que
        # precio_planta en Plantas vs Jornal.
        precio_esp: dict[tuple, list] = {}   # (tarea, cliente, finca) -> [precios]
        precio_com: dict[str, list] = {}     # tarea -> [precios]
        for c in self.db.query(ConceptoLiquidacion).filter(
            ConceptoLiquidacion.quincena == preliq.quincena,
            ConceptoLiquidacion.unidad_base == UnidadBaseConcepto.TANCADAS,
            ConceptoLiquidacion.precio.isnot(None),
        ).all():
            t = c.tarea_nombre.strip().upper()
            if c.cliente_nombre is None:
                precio_com.setdefault(t, []).append(c.precio)
            else:
                clave_esp = (t, c.cliente_nombre.strip().upper(), (c.finca_nombre or "").strip().upper())
                precio_esp.setdefault(clave_esp, []).append(c.precio)

        def precio_tancada(tarea, cliente, finca):
            t  = (tarea or "").strip().upper()
            cl = (cliente or "").strip().upper()
            fn = (finca or "").strip().upper()
            precios = precio_esp.get((t, cl, fn)) or precio_com.get(t)
            if not precios:
                return Decimal("0")
            return sum(precios) / len(precios)

        # Valor hora de jornal de pulverización (con recargo fijo). Si el
        # liquidador no lo cargó, no se puede valorizar "a jornal": VALOR S/JORNAL
        # y DIFF quedan en null en toda la tabla (no en 0, para no mentir).
        valor_hora_pulv = preliq.valor_hora_pulv
        valor_hs_pulv = (valor_hora_pulv * self.RECARGO_PULV) if valor_hora_pulv is not None else None

        filas = []
        for cliente, finca, tarea, suma_tancadas, suma_hsjornal, suma_hsmaquina in agregados:
            precio    = precio_tancada(tarea, cliente, finca)
            precio_comun, precio_especial = self._precio_comun_especial(
                precio_esp, precio_com, tarea, cliente, finca
            )
            tancadas  = suma_tancadas or Decimal("0")
            hsjornal  = suma_hsjornal or Decimal("0")
            hsmaquina = suma_hsmaquina or Decimal("0")
            # /2: la tancada es ida y vuelta (dato doblado).
            valor_jornal  = (hsjornal / 2 * valor_hs_pulv) if valor_hs_pulv is not None else None
            valor_tancada = tancadas / 2 * precio
            valor_tancada_comun = (
                (tancadas / 2 * precio_comun) if precio_comun is not None else None
            )
            valor_tancada_especial = (
                (tancadas / 2 * precio_especial) if precio_especial is not None else None
            )
            # DIFF = (tancada - jornal) / jornal. null si no hay jornal contra
            # qué comparar (valor hora sin cargar, o jornal = 0 por hsjornal 0).
            diff = None
            if valor_jornal is not None and valor_jornal != 0:
                diff = round(float((valor_tancada - valor_jornal) / valor_jornal), 4)
            filas.append({
                "nombre_cliente": cliente, "nombre_finca": finca,
                "nombre_tarea": tarea,
                "tancadas": round(float(tancadas), 2),
                "hsjornal": round(float(hsjornal), 2),
                "hsmaquina": round(float(hsmaquina), 2),
                "valor_jornal": round(float(valor_jornal), 2) if valor_jornal is not None else None,
                "precio": round(float(precio), 2),
                "valor_tancada": round(float(valor_tancada), 2),
                "diff": diff,
                "precio_comun": round(float(precio_comun), 2) if precio_comun is not None else None,
                "precio_especial": round(float(precio_especial), 2) if precio_especial is not None else None,
                "valor_tancada_comun": (
                    round(float(valor_tancada_comun), 2) if valor_tancada_comun is not None else None
                ),
                "valor_tancada_especial": (
                    round(float(valor_tancada_especial), 2) if valor_tancada_especial is not None else None
                ),
                "var_pct": self._var_pct(precio_comun, precio_especial),
            })
        filas.sort(key=lambda f: (f["nombre_cliente"] or "", f["nombre_finca"] or "", f["nombre_tarea"] or ""))

        # Totales: sumas donde corresponde, precio promediado, DIFF recalculado
        # sobre los totales (NO promedio de los DIFF por fila, que mentiría).
        tt  = sum(f["tancadas"]  for f in filas)
        thj = sum(f["hsjornal"]  for f in filas)
        thm = sum(f["hsmaquina"] for f in filas)
        tvt = sum(f["valor_tancada"] for f in filas)
        tp  = sum(f["precio"] for f in filas) / len(filas) if filas else 0
        if valor_hs_pulv is not None:
            tvj = sum(f["valor_jornal"] for f in filas)
            total_diff = round(float((tvt - tvj) / tvj), 4) if tvj else None
        else:
            tvj = None
            total_diff = None

        return {
            "valor_hora_pulv": float(valor_hora_pulv) if valor_hora_pulv is not None else None,
            "filas": filas,
            "totales": {
                "tancadas": round(tt, 2), "hsjornal": round(thj, 2), "hsmaquina": round(thm, 2),
                "valor_jornal": round(tvj, 2) if tvj is not None else None,
                "precio": round(tp, 2),
                "valor_tancada": round(tvt, 2),
                "diff": total_diff,
            },
        }

    def set_valor_hora_pulv(self, preliq_id: int, valor):
        """Setea (o limpia con None) el valor hora de pulverización de la
        quincena. Devuelve la Preliquidacion actualizada."""
        preliq = self.obtener(preliq_id)
        if not preliq:
            raise ValueError(f"Preliquidacion {preliq_id} no encontrada")
        preliq.valor_hora_pulv = valor
        self.db.commit()
        self.db.refresh(preliq)
        return preliq

    # ─── Consultas ────────────────────────────────────────────────────────────

    def listar(self) -> list[Preliquidacion]:
        return self.db.query(Preliquidacion).order_by(Preliquidacion.quincena.desc()).all()

    def obtener(self, preliq_id: int) -> Optional[Preliquidacion]:
        return self.db.query(Preliquidacion).filter(Preliquidacion.id == preliq_id).first()

    def listar_lineas(self, preliq_id: int, empresa=None, solo_alertas=None, nombre_empleado=None):
        # selectinload (no joinedload): con uno-a-muchos el join multiplica
        # filas (línea × conceptos) sobre la BD remota; selectinload trae
        # líneas y conceptos en 2 queries planas — menos bytes por el WAN.
        q = (
            self.db.query(PreliquidacionLinea)
            .options(selectinload(PreliquidacionLinea.conceptos))
            .filter(PreliquidacionLinea.preliquidacion_id == preliq_id)
        )
        if empresa:
            q = q.filter(PreliquidacionLinea.empresa_asignada == empresa.upper())
        if solo_alertas:
            q = q.filter(
                (PreliquidacionLinea.es_duplicado == True) |
                (PreliquidacionLinea.alerta_legajo == True) |
                (PreliquidacionLinea.linea_incompleta == True)
            )
        if nombre_empleado:
            q = q.filter(PreliquidacionLinea.nombre_empleado.ilike(f"%{nombre_empleado}%"))
        return q.order_by(
            PreliquidacionLinea.empresa_asignada,
            PreliquidacionLinea.nombre_empleado,
            PreliquidacionLinea.fecha_tarea,
        ).all()

    # ─── Actualizar línea ─────────────────────────────────────────────────────

    def actualizar_linea(self, linea_id, datos: LineaUpdateRequest, usuario_id) -> PreliquidacionLinea:
        linea = self.db.query(PreliquidacionLinea).filter(PreliquidacionLinea.id == linea_id).first()
        if not linea:
            raise ValueError(f"Línea {linea_id} no encontrada")

        campos = {
            "empresa_asignada": datos.empresa_asignada,
            "legajo_asignado": datos.legajo_asignado,
            "grupo_pago_aplicado": datos.grupo_pago_aplicado,
            "observacion": datos.observacion,
        }
        for campo, valor_nuevo in campos.items():
            if valor_nuevo is None:
                continue
            valor_anterior = getattr(linea, campo)
            if str(valor_anterior) == str(valor_nuevo):
                continue
            self.db.add(AjusteManual(
                linea_id=linea_id, campo_modificado=campo,
                valor_anterior=str(valor_anterior), valor_nuevo=str(valor_nuevo),
                motivo=datos.motivo_ajuste, usuario_id=usuario_id,
            ))
            setattr(linea, campo, valor_nuevo)

        self._recalcular_importe(linea)
        if datos.empresa_asignada:
            linea.alerta_legajo = False
        self.db.commit()
        self.db.refresh(linea)
        return linea

    def _recalcular_importe(self, linea: PreliquidacionLinea):
        # importe_base = 0 siempre. El total es la suma de ConceptoAdicional.
        linea.importe_base = Decimal("0")
        suma_conceptos = sum(c.importe for c in linea.conceptos if c.importe)
        linea.importe_total = suma_conceptos

    # ─── Conceptos adicionales ────────────────────────────────────────────────

    def agregar_concepto(self, linea_id, datos: ConceptoAdicionalRequest, usuario_id) -> ConceptoAdicional:
        linea = self.db.query(PreliquidacionLinea).filter(
            PreliquidacionLinea.id == linea_id
        ).options(joinedload(PreliquidacionLinea.conceptos)).first()
        if not linea:
            raise ValueError(f"Línea {linea_id} no encontrada")
        concepto = ConceptoAdicional(
            linea_id=linea_id, descripcion=datos.descripcion,
            tipo=datos.tipo, importe=datos.importe, ingresado_por=usuario_id,
        )
        self.db.add(concepto)
        self.db.flush()
        # linea.conceptos se cargó ANTES del insert (el concepto nuevo no está
        # en la colección): _recalcular_importe lo dejaba afuera y el total
        # quedaba sin el importe recién agregado. Mismo patrón que el masivo.
        linea.importe_base = Decimal("0")
        suma_existente = sum(c.importe for c in linea.conceptos if c.importe)
        linea.importe_total = suma_existente + (concepto.importe or Decimal("0"))
        self.db.commit()
        self.db.refresh(concepto)
        return concepto

    def eliminar_concepto(self, concepto_id, usuario_id):
        concepto = self.db.query(ConceptoAdicional).filter(ConceptoAdicional.id == concepto_id).first()
        if not concepto:
            raise ValueError(f"Concepto {concepto_id} no encontrado")
        linea = concepto.linea
        self.db.delete(concepto)
        self.db.flush()
        self._recalcular_importe(linea)
        self.db.commit()

    def agregar_concepto_por_codigo(self, linea_id: int, codigo: int, usuario_id: int) -> ConceptoAdicional:
        linea = self.db.query(PreliquidacionLinea).filter(
            PreliquidacionLinea.id == linea_id
        ).options(joinedload(PreliquidacionLinea.conceptos)).first()
        if not linea:
            raise ValueError(f"Línea {linea_id} no encontrada")

        quincena = linea.preliquidacion.quincena
        regla = self.db.query(ConceptoLiquidacion).filter(
            ConceptoLiquidacion.codigo == codigo,
            ConceptoLiquidacion.quincena == quincena,
        ).first()
        if not regla:
            raise ValueError(f"No existe el código {codigo} en el maestro de esta quincena")

        nuevos = self._generar_conceptos_automaticos(linea, [regla])
        concepto = nuevos[0]
        concepto.ingresado_por = usuario_id
        concepto.descripcion = f"Concepto {regla.codigo} (agregado manual)"
        self.db.add(concepto)
        self.db.flush()
        # Igual que en agregar_concepto: el concepto nuevo no está en la
        # colección ya cargada — se suma a mano para no perderlo del total.
        linea.importe_base = Decimal("0")
        suma_existente = sum(c.importe for c in linea.conceptos if c.importe)
        linea.importe_total = suma_existente + (concepto.importe or Decimal("0"))
        self.db.commit()
        self.db.refresh(concepto)
        return concepto

    # ─── Estadísticas ────────────────────────────────────────────────────────

    def estadisticas(self, preliq_id: int) -> dict:
        """Conteos agregados en SQL (antes: traía todas las líneas a RAM y
        contaba en Python). Devuelve exactamente las mismas claves de siempre."""
        fila = self.db.query(
            func.count(PreliquidacionLinea.id),
            func.sum(case(
                (or_(
                    PreliquidacionLinea.es_duplicado.is_(True),
                    PreliquidacionLinea.alerta_legajo.is_(True),
                    PreliquidacionLinea.linea_incompleta.is_(True),
                ), 1), else_=0,
            )),
            func.sum(case((PreliquidacionLinea.linea_incompleta.is_(True), 1), else_=0)),
            func.sum(case((PreliquidacionLinea.es_duplicado.is_(True), 1), else_=0)),
            func.sum(case((PreliquidacionLinea.alerta_legajo.is_(True), 1), else_=0)),
        ).filter(PreliquidacionLinea.preliquidacion_id == preliq_id).one()

        total, con_alerta, incompletas, duplicados, alerta_legajo = fila

        return {
            "total_lineas": total or 0,
            "lineas_con_alerta": int(con_alerta or 0),
            "incompletas": int(incompletas or 0),
            "duplicados": int(duplicados or 0),
            "alerta_legajo": int(alerta_legajo or 0),
            "por_empresa": self._agrupar_por_empresa_sql(preliq_id),
        }

    def _agrupar_por_empresa_sql(self, preliq_id: int) -> dict:
        filas = self.db.query(
            PreliquidacionLinea.empresa_asignada,
            func.count(PreliquidacionLinea.id),
        ).filter(
            PreliquidacionLinea.preliquidacion_id == preliq_id
        ).group_by(PreliquidacionLinea.empresa_asignada).all()

        resultado: dict = {}
        for emp, total in filas:
            clave = emp or "SIN EMPRESA"
            if clave not in resultado:
                resultado[clave] = {"total": 0}
            resultado[clave]["total"] += total
        return resultado

    def estadisticas_batch(self, preliq_ids: list[int]) -> dict[int, dict]:
        """Igual que `estadisticas()` pero para varias preliquidaciones en dos
        queries (una para los conteos, otra para el agrupado por empresa) en
        vez de N llamadas independientes. Devuelve {preliq_id: dict-con-las-
        mismas-claves-que-estadisticas()}."""
        resultado: dict[int, dict] = {
            pid: {
                "total_lineas": 0,
                "lineas_con_alerta": 0,
                "incompletas": 0,
                "duplicados": 0,
                "alerta_legajo": 0,
                "por_empresa": {},
            }
            for pid in preliq_ids
        }
        if not preliq_ids:
            return resultado

        filas = self.db.query(
            PreliquidacionLinea.preliquidacion_id,
            func.count(PreliquidacionLinea.id),
            func.sum(case(
                (or_(
                    PreliquidacionLinea.es_duplicado.is_(True),
                    PreliquidacionLinea.alerta_legajo.is_(True),
                    PreliquidacionLinea.linea_incompleta.is_(True),
                ), 1), else_=0,
            )),
            func.sum(case((PreliquidacionLinea.linea_incompleta.is_(True), 1), else_=0)),
            func.sum(case((PreliquidacionLinea.es_duplicado.is_(True), 1), else_=0)),
            func.sum(case((PreliquidacionLinea.alerta_legajo.is_(True), 1), else_=0)),
        ).filter(
            PreliquidacionLinea.preliquidacion_id.in_(preliq_ids)
        ).group_by(PreliquidacionLinea.preliquidacion_id).all()

        for pid, total, con_alerta, incompletas, duplicados, alerta_legajo in filas:
            resultado[pid]["total_lineas"] = total or 0
            resultado[pid]["lineas_con_alerta"] = int(con_alerta or 0)
            resultado[pid]["incompletas"] = int(incompletas or 0)
            resultado[pid]["duplicados"] = int(duplicados or 0)
            resultado[pid]["alerta_legajo"] = int(alerta_legajo or 0)

        empresa_filas = self.db.query(
            PreliquidacionLinea.preliquidacion_id,
            PreliquidacionLinea.empresa_asignada,
            func.count(PreliquidacionLinea.id),
        ).filter(
            PreliquidacionLinea.preliquidacion_id.in_(preliq_ids)
        ).group_by(
            PreliquidacionLinea.preliquidacion_id, PreliquidacionLinea.empresa_asignada
        ).all()

        for pid, emp, total in empresa_filas:
            clave = emp or "SIN EMPRESA"
            por_empresa = resultado[pid]["por_empresa"]
            if clave not in por_empresa:
                por_empresa[clave] = {"total": 0}
            por_empresa[clave]["total"] += total

        return resultado

    # ─── Operaciones masivas ──────────────────────────────────────────────────

    def agregar_concepto_masivo(self, linea_ids: list[int], codigo: int, usuario_id: int) -> dict:
        primera = self.db.query(PreliquidacionLinea).filter(
            PreliquidacionLinea.id == linea_ids[0]
        ).first()
        quincena = primera.preliquidacion.quincena if primera else None

        regla = self.db.query(ConceptoLiquidacion).filter(
            ConceptoLiquidacion.codigo == codigo,
            ConceptoLiquidacion.quincena == quincena,
        ).first()
        if not regla:
            raise ValueError(f"No existe el código {codigo} en el maestro de esta quincena")

        # Antes: una query + flush + recálculo POR linea_id (N+1). Ahora: una
        # sola query trae todas las líneas (con sus conceptos ya cargados vía
        # joinedload), se procesan en memoria y se persisten en un solo lote.
        lineas = self.db.query(PreliquidacionLinea).filter(
            PreliquidacionLinea.id.in_(linea_ids)
        ).options(joinedload(PreliquidacionLinea.conceptos)).all()
        lineas_por_id = {l.id: l for l in lineas}

        aplicadas = 0
        conceptos_nuevos = []
        for linea_id in linea_ids:
            linea = lineas_por_id.get(linea_id)
            if not linea:
                continue
            nuevos = self._generar_conceptos_automaticos(linea, [regla])
            concepto = nuevos[0]
            concepto.ingresado_por = usuario_id
            concepto.descripcion = f"Concepto {regla.codigo} (masivo)"
            conceptos_nuevos.append(concepto)
            # _recalcular_importe suma linea.conceptos (ya cargados) + el
            # concepto nuevo, que todavía no está en la sesión ni en la
            # colección — lo sumamos a mano para no depender de un flush.
            linea.importe_base = Decimal("0")
            suma_existente = sum(c.importe for c in linea.conceptos if c.importe)
            linea.importe_total = suma_existente + (concepto.importe or Decimal("0"))
            aplicadas += 1

        if conceptos_nuevos:
            self.db.bulk_save_objects(conceptos_nuevos)
        self.db.commit()
        return {"aplicadas": aplicadas}

    def eliminar_concepto_masivo(self, linea_ids: list[int], codigo: int) -> dict:
        if not linea_ids:
            return {"eliminados": 0, "lineas": 0}
        result = self.db.execute(sql_text("""
            DELETE FROM concepto_adicional
            WHERE linea_id IN :ids AND codigo_concepto = :codigo
        """), {"ids": tuple(linea_ids), "codigo": codigo})
        eliminados = result.rowcount
        self.db.commit()
        lineas = self.db.query(PreliquidacionLinea).filter(
            PreliquidacionLinea.id.in_(linea_ids)
        ).options(joinedload(PreliquidacionLinea.conceptos)).all()
        for linea in lineas:
            self._recalcular_importe(linea)
        self.db.commit()
        return {"eliminados": eliminados, "lineas": len(lineas)}

    # ─── Reasignación masiva de empresa ───────────────────────────────────────

    def legajos_disponibles_por_cuil(self, linea_ids: list[int]) -> dict:
        """
        Agrupa las líneas seleccionadas por CUIL (una persona puede tener
        varios legajos, uno por empresa) y, para cada una, devuelve los
        pares (empresa, legajo) que esa persona realmente tiene — para que
        el liquidador solo pueda elegir una empresa donde la persona ya
        está dada de alta.
        """
        if not self.sueldos:
            raise ValueError("Servicio de sueldos no disponible")

        lineas = self.db.query(PreliquidacionLinea).filter(
            PreliquidacionLinea.id.in_(linea_ids)
        ).all()

        grupos: dict[str, dict] = {}
        sin_cuil = []
        for linea in lineas:
            cuil = (linea.cuit or "").strip()
            if not cuil:
                sin_cuil.append(linea.id)
                continue
            if cuil not in grupos:
                grupos[cuil] = {
                    "cuil": cuil,
                    "nombre_empleado": linea.nombre_empleado,
                    "linea_ids": [],
                    "legajos_disponibles": [
                        {"empresa": r["empresa"], "legajo": r["legajo"]}
                        for r in self.sueldos.legajos_por_cuil(cuil)
                    ],
                }
            grupos[cuil]["linea_ids"].append(linea.id)

        return {"grupos": list(grupos.values()), "sin_cuil": sin_cuil}

    def legajos_disponibles_de_linea(self, linea_id: int) -> dict:
        """
        Pares (empresa, legajo) reales de la persona de UNA línea (por su
        CUIL), para el desplegable del panel individual. Devuelve lista vacía
        si la línea no tiene CUIL o el maestro de sueldos no está disponible
        — en ese caso el front cae al campo de legajo manual.
        """
        linea = self.db.query(PreliquidacionLinea).filter(
            PreliquidacionLinea.id == linea_id
        ).first()
        if not linea:
            raise ValueError(f"Línea {linea_id} no encontrada")

        cuil = (linea.cuit or "").strip()
        disponibles = []
        if cuil and self.sueldos:
            disponibles = [
                {"empresa": r["empresa"], "legajo": r["legajo"]}
                for r in self.sueldos.legajos_por_cuil(cuil)
            ]

        return {
            "cuil": cuil or None,
            "empresa_asignada": linea.empresa_asignada,
            "legajo_asignado": linea.legajo_asignado,
            "legajos_disponibles": disponibles,
        }

    def reasignar_empresa_masivo(
        self, linea_ids: list[int], empresa: str, usuario_id: int, motivo: str = None
    ) -> dict:
        """
        Reasigna empresa_asignada (+ legajo_asignado correcto) a las líneas
        dadas, solo si la persona (por CUIL) realmente tiene legajo en esa
        empresa. Audita cada cambio en AjusteManual, igual que actualizar_linea.
        Ningún recálculo posterior pisa esta asignación (ADR-0002/plan WS4).
        """
        if not self.sueldos:
            raise ValueError("Servicio de sueldos no disponible")

        empresa = empresa.strip().upper()
        lineas = self.db.query(PreliquidacionLinea).filter(
            PreliquidacionLinea.id.in_(linea_ids)
        ).all()

        reasignadas = []
        sin_legajo_en_empresa = []
        for linea in lineas:
            cuil = (linea.cuit or "").strip()
            legajo_nuevo = self.sueldos.legajo_por_cuil_y_empresa(cuil, empresa) if cuil else None
            if not legajo_nuevo:
                sin_legajo_en_empresa.append(linea.id)
                continue

            for campo, valor_nuevo in (
                ("empresa_asignada", empresa),
                ("legajo_asignado", legajo_nuevo),
            ):
                valor_anterior = getattr(linea, campo)
                if str(valor_anterior) == str(valor_nuevo):
                    continue
                self.db.add(AjusteManual(
                    linea_id=linea.id, campo_modificado=campo,
                    valor_anterior=str(valor_anterior), valor_nuevo=str(valor_nuevo),
                    motivo=motivo, usuario_id=usuario_id,
                ))
                setattr(linea, campo, valor_nuevo)

            linea.alerta_legajo = False
            reasignadas.append(linea.id)

        self.db.commit()
        return {
            "reasignadas": len(reasignadas),
            "sin_legajo_en_empresa": sin_legajo_en_empresa,
        }