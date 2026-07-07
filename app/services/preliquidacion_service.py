from datetime import date
from decimal import Decimal
from typing import Optional
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, func, text as sql_text

from app.models.models import (
    Preliquidacion, PreliquidacionLinea, ConceptoAdicional,
    AjusteManual, ConceptoLiquidacion, UnidadBaseConcepto,
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

        Matching solo por tarea + cliente + finca — sin grupo_pago.
        - comunes:    clave = tarea.upper()
        - específicos: clave = (tarea.upper(), cliente.upper(), finca.upper())

        El grupo_pago_aplicado de la línea viene del catálogo externo,
        no del maestro de conceptos.
        """
        conceptos = self.db.query(ConceptoLiquidacion).filter(
            ConceptoLiquidacion.quincena == quincena
        ).all()

        cache_comunes = {}      # tarea -> [ConceptoLiquidacion]
        cache_especificos = {}  # (tarea, cliente, finca) -> [ConceptoLiquidacion]

        for c in conceptos:
            t = c.tarea_nombre.strip().upper()
            if c.cliente_nombre is None:
                cache_comunes.setdefault(t, []).append(c)
            else:
                cl = c.cliente_nombre.strip().upper()
                fn = (c.finca_nombre or "").strip().upper()
                cache_especificos.setdefault((t, cl, fn), []).append(c)

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
            "especificos": cache_especificos,
            "grupo_tarea": cache_grupo_tarea,
            "grupo_pago_catalogo": cache_grupo_pago_catalogo,
        }

    def _buscar_conceptos_cache(
        self, tarea: str, cliente: str, finca: str, cache: dict
    ) -> list:
        """
        Devuelve todas las reglas que matchean esta línea.
        Específicos + comunes siempre suman.
        Matching: tarea + cliente + finca exactos (sin grupo_pago).
        """
        t  = tarea.strip().upper()
        cl = (cliente or "").strip().upper()
        fn = (finca or "").strip().upper()

        esp = cache["especificos"].get((t, cl, fn), [])
        com = cache["comunes"].get(t, [])
        return esp + com

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

        # grupo_pago para el importe base viene del catálogo externo
        grupo_pago = cache["grupo_pago_catalogo"].get(nombre_tarea.strip().upper(), "")

        # Buscar reglas del maestro: específicos + comunes suman
        reglas = self._buscar_conceptos_cache(nombre_tarea, nombre_cliente, nombre_finca, cache)
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
        """Cache comunes/específicos del maestro vigente para una quincena (solo con código)."""
        conceptos = self.db.query(ConceptoLiquidacion).filter(
            ConceptoLiquidacion.quincena == quincena,
            ConceptoLiquidacion.codigo.isnot(None),
        ).all()

        cache_comunes = {}
        cache_especificos = {}
        for c in conceptos:
            t = c.tarea_nombre.strip().upper()
            if c.cliente_nombre is None:
                cache_comunes.setdefault(t, []).append(c)
            else:
                cl = c.cliente_nombre.strip().upper()
                fn = (c.finca_nombre or "").strip().upper()
                cache_especificos.setdefault((t, cl, fn), []).append(c)
        return cache_comunes, cache_especificos

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

        cache_comunes, cache_especificos = self._cache_conceptos_quincena(quincena)

        actualizadas = sin_reglas = 0
        conceptos_nuevos = []

        for linea in lineas:
            t  = (linea.nombre_tarea   or "").strip().upper()
            cl = (linea.nombre_cliente or "").strip().upper()
            fn = (linea.nombre_finca   or "").strip().upper()

            esp    = cache_especificos.get((t, cl, fn), [])
            com    = cache_comunes.get(t, [])
            reglas = esp + com

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
        Recalcula TODA la quincena. Ya no es un paso obligatorio del flujo
        (el impacto del maestro es reactivo, ver recalcular_por_concepto) —
        se conserva como acción manual de "recalcular todo" por si hace
        falta forzarlo.
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

    def _lineas_por_match(self, preliq_id, tarea_nombre, cliente_nombre=None, finca_nombre=None) -> list:
        """Líneas de una preliquidación que matchean tarea (+cliente+finca si se pasan)."""
        t = (tarea_nombre or "").strip().upper()
        lineas = self.db.query(PreliquidacionLinea).filter(
            PreliquidacionLinea.preliquidacion_id == preliq_id,
            func.upper(func.trim(PreliquidacionLinea.nombre_tarea)) == t,
        ).options(joinedload(PreliquidacionLinea.conceptos)).all()

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
        (tarea/cliente/finca) cambiaron, también las que matcheaba antes
        (unión) — evita ConceptoAdicional fantasma en líneas que dejaron de
        matchear.
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
            ):
                vistas[linea.id] = linea

        lineas = list(vistas.values())
        resultado = self._aplicar_conceptos_a_lineas(preliq.quincena, lineas)
        return {"lineas_afectadas": len(lineas), **resultado}

    # ─── Dashboard de verificación ────────────────────────────────────────────

    def dashboard_verificacion(self, preliq_id: int) -> dict:
        lineas = self.db.query(PreliquidacionLinea).filter(
            PreliquidacionLinea.preliquidacion_id == preliq_id
        ).options(joinedload(PreliquidacionLinea.conceptos)).all()

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

    # ─── Control Plantas vs Jornal ────────────────────────────────────────────

    def control_plantas_jornal(self, preliq_id: int) -> dict:
        preliq = self.db.query(Preliquidacion).filter(
            Preliquidacion.id == preliq_id
        ).first()
        if not preliq:
            raise ValueError(f"Preliquidacion {preliq_id} no encontrada")

        lineas = self.db.query(PreliquidacionLinea).filter(
            PreliquidacionLinea.preliquidacion_id == preliq_id,
            PreliquidacionLinea.grupo_pago_aplicado == "PLANTA",
        ).all()

        # Precio por planta: sale del maestro (concepto con unidad_base = unidades),
        # no del difunto precio_a. Cache específicos + comunes de la quincena.
        precio_esp: dict[tuple, list] = {}   # (tarea, cliente, finca) -> [precios]
        precio_com: dict[str, list] = {}     # tarea -> [precios]
        for c in self.db.query(ConceptoLiquidacion).filter(
            ConceptoLiquidacion.quincena == preliq.quincena,
            ConceptoLiquidacion.unidad_base == UnidadBaseConcepto.UNIDADES,
            ConceptoLiquidacion.precio.isnot(None),
        ).all():
            t = c.tarea_nombre.strip().upper()
            if c.cliente_nombre is None:
                precio_com.setdefault(t, []).append(c.precio)
            else:
                clave_esp = (t, c.cliente_nombre.strip().upper(), (c.finca_nombre or "").strip().upper())
                precio_esp.setdefault(clave_esp, []).append(c.precio)

        def precio_planta(tarea, cliente, finca):
            t  = (tarea or "").strip().upper()
            cl = (cliente or "").strip().upper()
            fn = (finca or "").strip().upper()
            precios = precio_esp.get((t, cl, fn)) or precio_com.get(t)
            if not precios:
                return Decimal("0")
            return sum(precios) / len(precios)

        grupos = {}
        for linea in lineas:
            clave = (linea.nombre_cliente or "", linea.nombre_finca or "", linea.nombre_tarea or "")
            if clave not in grupos:
                grupos[clave] = {"nombre_cliente": linea.nombre_cliente, "nombre_finca": linea.nombre_finca,
                                 "nombre_tarea": linea.nombre_tarea,
                                 "precio": precio_planta(linea.nombre_tarea, linea.nombre_cliente, linea.nombre_finca),
                                 "unidades": Decimal("0"), "hs": Decimal("0")}
            g = grupos[clave]
            g["unidades"] += linea.unidades or Decimal("0")
            g["hs"] += linea.hsmaquina or Decimal("0")

        filas = []
        for g in grupos.values():
            pp = float(g["precio"])
            u  = float(g["unidades"]); h = float(g["hs"])
            phsm = (u / h) if h else 0
            filas.append({
                "nombre_cliente": g["nombre_cliente"], "nombre_finca": g["nombre_finca"],
                "nombre_tarea": g["nombre_tarea"], "precio_promedio": round(pp, 2),
                "unidades": round(u, 2), "hs": round(h, 2),
                "plantas_por_hsm": round(phsm, 2), "plantas_por_hsm_x8": round(phsm * 8, 2),
                "prom_jornal": round(phsm * 8 * pp, 2),
            })
        filas.sort(key=lambda f: (f["nombre_cliente"] or "", f["nombre_finca"] or "", f["nombre_tarea"] or ""))

        tu = sum(f["unidades"] for f in filas); th = sum(f["hs"] for f in filas)
        tp = sum(f["precio_promedio"] for f in filas) / len(filas) if filas else 0
        tphsm = (tu / th) if th else 0
        return {
            "filas": filas,
            "totales": {
                "unidades": round(tu, 2), "hs": round(th, 2),
                "precio_promedio": round(tp, 2), "plantas_por_hsm": round(tphsm, 2),
                "plantas_por_hsm_x8": round(tphsm * 8, 2), "prom_jornal": round(tphsm * 8 * tp, 2),
            },
        }

    # ─── Consultas ────────────────────────────────────────────────────────────


    def aplicar(self, preliq_id: int) -> dict:
        """
        Recalcula manualmente TODA la quincena (acción de emergencia; el
        impacto normal es reactivo, ver recalcular_por_concepto).
        """
        resultado = self.aplicar_conceptos(preliq_id)
        return {"conceptos_aplicados": resultado.get("actualizadas", 0)}

    def listar(self) -> list[Preliquidacion]:
        return self.db.query(Preliquidacion).order_by(Preliquidacion.quincena.desc()).all()

    def obtener(self, preliq_id: int) -> Optional[Preliquidacion]:
        return self.db.query(Preliquidacion).filter(Preliquidacion.id == preliq_id).first()

    def listar_lineas(self, preliq_id: int, empresa=None, solo_alertas=None, nombre_empleado=None):
        q = (
            self.db.query(PreliquidacionLinea)
            .options(joinedload(PreliquidacionLinea.conceptos))
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
        self._recalcular_importe(linea)
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
        self._recalcular_importe(linea)
        self.db.commit()
        self.db.refresh(concepto)
        return concepto

    # ─── Estadísticas ────────────────────────────────────────────────────────

    def estadisticas(self, preliq_id: int) -> dict:
        lineas = self.db.query(PreliquidacionLinea).filter(
            PreliquidacionLinea.preliquidacion_id == preliq_id
        ).all()
        return {
            "total_lineas": len(lineas),
            "lineas_con_alerta": sum(1 for l in lineas if l.es_duplicado or l.alerta_legajo or l.linea_incompleta),
            "incompletas": sum(1 for l in lineas if l.linea_incompleta),
            "duplicados": sum(1 for l in lineas if l.es_duplicado),
            "alerta_legajo": sum(1 for l in lineas if l.alerta_legajo),
            "por_empresa": self._agrupar_por_empresa(lineas),
        }

    def _agrupar_por_empresa(self, lineas: list) -> dict:
        resultado = {}
        for linea in lineas:
            emp = linea.empresa_asignada or "SIN EMPRESA"
            if emp not in resultado:
                resultado[emp] = {"total": 0}
            resultado[emp]["total"] += 1
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

        aplicadas = 0
        for linea_id in linea_ids:
            linea = self.db.query(PreliquidacionLinea).filter(
                PreliquidacionLinea.id == linea_id
            ).options(joinedload(PreliquidacionLinea.conceptos)).first()
            if not linea:
                continue
            nuevos = self._generar_conceptos_automaticos(linea, [regla])
            concepto = nuevos[0]
            concepto.ingresado_por = usuario_id
            concepto.descripcion = f"Concepto {regla.codigo} (masivo)"
            self.db.add(concepto)
            self.db.flush()
            self._recalcular_importe(linea)
            aplicadas += 1

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