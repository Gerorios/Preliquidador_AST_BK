from datetime import date
from decimal import Decimal
from typing import Optional
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, text as sql_text

from app.models.models import (
    Preliquidacion, PreliquidacionLinea, ConceptoAdicional,
    AjusteManual, PrecioUsado, ConceptoLiquidacion,
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

    def __init__(self, db_propia: Session, db_externa: Session, db_sueldos: Session = None):
        self.db = db_propia
        self.sueldos = SueldosService(db_sueldos) if db_sueldos else None
        self.motor = MotorReglas(db_propia, self.sueldos)
        self.externa = ConsultaExternaService(db_externa)

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
        alerta_sin_codigo = len(reglas_con_codigo) == 0
        alerta_sin_precio = len(reglas) == 0
        codigo_liquidacion = reglas_con_codigo[0].codigo if reglas_con_codigo else None

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
            precio_b=None,
            precio_usado=PrecioUsado.A,
            importe_base=Decimal("0"),
            importe_total=Decimal("0"),
            revisado=False,
            es_duplicado=es_duplicado,
            alerta_legajo=alerta_legajo,
            alerta_empresa=alerta_empresa,
            alerta_sin_precio=alerta_sin_precio,
            alerta_sin_codigo=alerta_sin_codigo,
        )
        return linea, reglas_con_codigo

    def _generar_conceptos_automaticos(self, linea, reglas) -> list:
        conceptos = []
        for regla in reglas:
            unidad = regla.unidad_base.value if hasattr(regla.unidad_base, "value") else regla.unidad_base
            cantidad = self.motor.calcular_cantidad_concepto(
                unidad_base=unidad,
                hsjornal=linea.hsjornal,
                hsmaquina=linea.hsmaquina,
                tancadas=linea.tancadas,
                unidades=linea.unidades,
            )
            precio = regla.precio if regla.precio is not None else (linea.precio_a or Decimal("0"))
            importe = (cantidad * precio).quantize(Decimal("0.01"))
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

    # ─── Recalcular precios ───────────────────────────────────────────────────

    def recalcular_precios(self, preliq_id: int) -> dict:
        """
        Con el modelo unificado, el importe_base siempre es 0.
        El importe_total = suma de todos los ConceptoAdicional.
        precio_a se guarda solo para referencia/display.
        """
        preliq = self.db.query(Preliquidacion).filter(
            Preliquidacion.id == preliq_id
        ).first()
        if not preliq:
            raise ValueError(f"Preliquidacion {preliq_id} no encontrada")

        quincena = preliq.quincena

        # Paso 0: resetear precio_a para que los pasos siguientes partan de NULL
        self.db.execute(sql_text("""
            UPDATE preliquidacion_linea
            SET precio_a = NULL, alerta_sin_precio = 1
            WHERE preliquidacion_id = :pid
        """), {"pid": preliq_id})

        # Paso 1: marcar precio_a desde concepto específico (solo referencia)
        self.db.execute(sql_text("""
            UPDATE preliquidacion_linea pl
            INNER JOIN concepto_liquidacion cl
                ON  cl.quincena        = :quincena
                AND cl.tarea_nombre    = pl.nombre_tarea
                AND cl.cliente_nombre  = pl.nombre_cliente
                AND cl.finca_nombre    = pl.nombre_finca
                AND cl.precio IS NOT NULL
            SET
                pl.precio_a          = cl.precio,
                pl.alerta_sin_precio = 0,
                pl.importe_base      = 0
            WHERE pl.preliquidacion_id = :pid
        """), {"pid": preliq_id, "quincena": quincena})

        # Paso 2: fallback desde concepto común
        self.db.execute(sql_text("""
            UPDATE preliquidacion_linea pl
            INNER JOIN concepto_liquidacion cl
                ON  cl.quincena          = :quincena
                AND cl.tarea_nombre      = pl.nombre_tarea
                AND cl.cliente_nombre IS NULL
                AND cl.precio IS NOT NULL
            SET
                pl.precio_a          = cl.precio,
                pl.alerta_sin_precio = 0,
                pl.importe_base      = 0
            WHERE pl.preliquidacion_id = :pid
              AND (pl.precio_a IS NULL OR pl.alerta_sin_precio = 1)
        """), {"pid": preliq_id, "quincena": quincena})

        # Paso 3: marcar sin precio las que no matchearon
        self.db.execute(sql_text("""
            UPDATE preliquidacion_linea
            SET precio_a = NULL, importe_base = 0, alerta_sin_precio = 1
            WHERE preliquidacion_id = :pid
              AND precio_a IS NULL
        """), {"pid": preliq_id})

        self.db.commit()

        stats = self.db.execute(sql_text("""
            SELECT
                SUM(CASE WHEN alerta_sin_precio = 0 THEN 1 ELSE 0 END),
                SUM(CASE WHEN alerta_sin_precio = 1 THEN 1 ELSE 0 END)
            FROM preliquidacion_linea
            WHERE preliquidacion_id = :pid
        """), {"pid": preliq_id}).fetchone()

        return {"actualizadas": stats[0] or 0, "sin_precio": stats[1] or 0}

    # ─── Aplicar conceptos ────────────────────────────────────────────────────

    def aplicar_conceptos(self, preliq_id: int) -> dict:
        """
        Regenera los ConceptoAdicional automáticos desde el maestro unificado.
        Matching: tarea + cliente + finca (sin grupo_pago).
        Específicos + comunes siempre suman.
        Anti-lock: DELETE masivo primero, bulk INSERT después.
        """
        preliq = self.db.query(Preliquidacion).filter(
            Preliquidacion.id == preliq_id
        ).first()
        if not preliq:
            raise ValueError(f"Preliquidacion {preliq_id} no encontrada")

        quincena = preliq.quincena

        # Paso 1: borrar automáticos en un solo DELETE
        self.db.execute(sql_text("""
            DELETE ca FROM concepto_adicional ca
            INNER JOIN preliquidacion_linea pl ON pl.id = ca.linea_id
            WHERE pl.preliquidacion_id = :pid
              AND ca.ingresado_por IS NULL
        """), {"pid": preliq_id})
        self.db.commit()

        # Paso 2: cache del maestro para esta quincena
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

        lineas = self.db.query(PreliquidacionLinea).filter(
            PreliquidacionLinea.preliquidacion_id == preliq_id,
        ).options(joinedload(PreliquidacionLinea.conceptos)).all()

        actualizadas = sin_reglas = 0
        conceptos_nuevos = []
        ids_con_conceptos = set()

        # Paso 3: emparejar reglas con cada línea
        for linea in lineas:
            t  = (linea.nombre_tarea   or "").strip().upper()
            cl = (linea.nombre_cliente or "").strip().upper()
            fn = (linea.nombre_finca   or "").strip().upper()

            esp    = cache_especificos.get((t, cl, fn), [])
            com    = cache_comunes.get(t, [])
            reglas = esp + com

            if not reglas:
                if not linea.alerta_sin_codigo:
                    linea.codigo_liquidacion = None
                    linea.alerta_sin_codigo  = True
                    self._recalcular_importe(linea)
                    actualizadas += 1
                else:
                    sin_reglas += 1
                continue

            nuevos = self._generar_conceptos_automaticos(linea, reglas)
            conceptos_nuevos.extend(nuevos)
            ids_con_conceptos.add(linea.id)
            linea.codigo_liquidacion = reglas[0].codigo
            linea.alerta_sin_codigo  = False
            actualizadas += 1

        # Paso 4: insertar y commitear
        if conceptos_nuevos:
            self.db.bulk_save_objects(conceptos_nuevos)
        self.db.commit()

        # Paso 5: recalcular importe_total con los conceptos ya insertados
        if ids_con_conceptos:
            for linea in self.db.query(PreliquidacionLinea).filter(
                PreliquidacionLinea.id.in_(ids_con_conceptos)
            ).options(joinedload(PreliquidacionLinea.conceptos)).all():
                self._recalcular_importe(linea)
            self.db.commit()

        return {"actualizadas": actualizadas, "sin_reglas": sin_reglas}

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
        lineas = self.db.query(PreliquidacionLinea).filter(
            PreliquidacionLinea.preliquidacion_id == preliq_id,
            PreliquidacionLinea.grupo_pago_aplicado == "PLANTA",
        ).all()

        grupos = {}
        for linea in lineas:
            clave = (linea.nombre_cliente or "", linea.nombre_finca or "", linea.nombre_tarea or "")
            if clave not in grupos:
                grupos[clave] = {"nombre_cliente": linea.nombre_cliente, "nombre_finca": linea.nombre_finca,
                                 "nombre_tarea": linea.nombre_tarea, "suma_precio": Decimal("0"),
                                 "cantidad_precios": 0, "unidades": Decimal("0"), "hs": Decimal("0")}
            g = grupos[clave]
            if linea.precio_a is not None:
                g["suma_precio"] += linea.precio_a
                g["cantidad_precios"] += 1
            g["unidades"] += linea.unidades or Decimal("0")
            g["hs"] += linea.hsmaquina or Decimal("0")

        filas = []
        for g in grupos.values():
            pp = float(g["suma_precio"] / g["cantidad_precios"]) if g["cantidad_precios"] else 0
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
        """Recalcula precios y aplica conceptos en una sola operación."""
        r1 = self.recalcular_precios(preliq_id)
        r2 = self.aplicar_conceptos(preliq_id)
        return {
            "actualizadas": r1.get("actualizadas", 0),
            "sin_precio": r1.get("sin_precio", 0),
            "conceptos_aplicados": r2.get("actualizadas", 0),
        }

    def listar(self) -> list[Preliquidacion]:
        return self.db.query(Preliquidacion).order_by(Preliquidacion.quincena.desc()).all()

    def obtener(self, preliq_id: int) -> Optional[Preliquidacion]:
        return self.db.query(Preliquidacion).filter(Preliquidacion.id == preliq_id).first()

    def listar_lineas(self, preliq_id: int, empresa=None, revisado=None, solo_alertas=None, nombre_empleado=None):
        q = (
            self.db.query(PreliquidacionLinea)
            .options(joinedload(PreliquidacionLinea.conceptos))
            .filter(PreliquidacionLinea.preliquidacion_id == preliq_id)
        )
        if empresa:
            q = q.filter(PreliquidacionLinea.empresa_asignada == empresa.upper())
        if revisado is not None:
            q = q.filter(PreliquidacionLinea.revisado == revisado)
        if solo_alertas:
            q = q.filter(
                (PreliquidacionLinea.es_duplicado == True) |
                (PreliquidacionLinea.alerta_legajo == True) |
                (PreliquidacionLinea.alerta_sin_precio == True) |
                (PreliquidacionLinea.alerta_sin_codigo == True)
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
            "precio_b": datos.precio_b,
            "precio_usado": datos.precio_usado,
            "revisado": datos.revisado,
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
            "lineas_revisadas": sum(1 for l in lineas if l.revisado),
            "lineas_con_alerta": sum(1 for l in lineas if l.es_duplicado or l.alerta_legajo or l.alerta_sin_precio or l.alerta_sin_codigo),
            "sin_precio": sum(1 for l in lineas if l.alerta_sin_precio),
            "sin_codigo": sum(1 for l in lineas if l.alerta_sin_codigo),
            "duplicados": sum(1 for l in lineas if l.es_duplicado),
            "alerta_legajo": sum(1 for l in lineas if l.alerta_legajo),
            "por_empresa": self._agrupar_por_empresa(lineas),
        }

    def _agrupar_por_empresa(self, lineas: list) -> dict:
        resultado = {}
        for linea in lineas:
            emp = linea.empresa_asignada or "SIN EMPRESA"
            if emp not in resultado:
                resultado[emp] = {"total": 0, "revisadas": 0}
            resultado[emp]["total"] += 1
            if linea.revisado:
                resultado[emp]["revisadas"] += 1
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