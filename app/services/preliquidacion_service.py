from datetime import date
from decimal import Decimal
from typing import Optional
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_

from app.models.models import (
    Preliquidacion, PreliquidacionLinea, ConceptoAdicional,
    AjusteManual, PrecioUsado,
    PrecioMaestro, PrecioComun, ConceptoLiquidacion,
)
from app.services.consulta_externa import ConsultaExternaService
from app.services.motor_reglas import MotorReglas
from app.services.sueldos_service import SueldosService
from app.schemas.schemas import LineaUpdateRequest, ConceptoAdicionalRequest


def _n(v) -> str:
    """Normaliza un valor numérico a string con 2 decimales para comparación de claves."""
    if v is None: return "None"
    try: return f"{float(str(v)):.2f}"
    except: return "None"


def _clave_linea(fila: dict) -> tuple:
    """
    Clave única que identifica una línea de campo (12 campos).
    Se usa para detectar nuevas, existentes y eliminadas.
    Debe coincidir exactamente con la clave construida en actualizar_quincena.
    """
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
        """
        Primera generación: crea la preliquidación y carga todas las líneas.
        Si ya existe → actualiza incrementalmente.
        """
        existente = self.db.query(Preliquidacion).filter(
            Preliquidacion.quincena == quincena
        ).first()

        if existente:
            return self.actualizar_quincena(existente, usuario_id)

        preliq = Preliquidacion(
            quincena=quincena,
            creado_por=usuario_id,
        )
        self.db.add(preliq)
        self.db.flush()

        filas = self.externa.obtener_tareas_quincena(quincena)
        insertadas = 0

        if filas:
            cache = self._construir_cache(quincena)
            indices_duplicados = self.motor.detectar_duplicados(filas)
            dias_asturiana = self._contar_dias_asturiana(filas)

            nuevos_conceptos = {}

            lineas_y_reglas = []
            for i, fila in enumerate(filas):
                linea, reglas = self._procesar_fila_con_cache(
                    fila=fila,
                    quincena=quincena,
                    preliquidacion_id=preliq.id,
                    es_duplicado=(i in indices_duplicados),
                    dias_asturiana=dias_asturiana,
                    cache=cache,
                    nuevos_conceptos=nuevos_conceptos,
                )
                lineas_y_reglas.append((linea, reglas))

            # Agregar líneas y hacer flush para obtener sus IDs
            for linea, _ in lineas_y_reglas:
                self.db.add(linea)
            self.db.flush()
            insertadas = len(lineas_y_reglas)

            # Generar conceptos automáticos y actualizar importe_total
            conceptos_auto = []
            for linea, reglas in lineas_y_reglas:
                if reglas:
                    nuevos = self._generar_conceptos_automaticos(linea, reglas)
                    conceptos_auto.extend(nuevos)
                    extra = sum(c.importe for c in nuevos)
                    linea.importe_total = (linea.importe_base or Decimal("0")) + extra

            if conceptos_auto:
                self.db.bulk_save_objects(conceptos_auto)

            # Insertar combinaciones nuevas de concepto sin reglas (para completar después)
            self._insertar_conceptos_nuevos(nuevos_conceptos)

        self.db.commit()
        self.db.refresh(preliq)

        return {
            "preliquidacion_id": preliq.id,
            "insertadas": insertadas,
            "eliminadas": 0,
            "sin_cambios": 0,
        }

    def actualizar_quincena(self, preliq: Preliquidacion, usuario_id: int) -> dict:
        """
        Actualización incremental optimizada:
        - Trae solo los campos necesarios para construir claves
        - Inserta líneas nuevas que llegaron de campo
        - Elimina líneas que ya no están en campo
        - Ignora las que ya existen (preserva ajustes del liquidador)
        """
        from sqlalchemy import text as sql_text

        quincena = preliq.quincena

        filas_campo = self.externa.obtener_tareas_quincena(quincena)
        claves_campo = {_clave_linea(f): f for f in filas_campo}

        rows = self.db.execute(
            sql_text("""
                SELECT id, planilla, fecha_tarea, legajo_campo, nombre_empleado,
                       nombre_tarea, nombre_cliente, nombre_finca, nombre_tractor,
                       hsjornal, hsmaquina, tancadas, unidades
                FROM preliquidacion_linea
                WHERE preliquidacion_id = :pid
            """),
            {"pid": preliq.id}
        ).fetchall()

        claves_existentes = {}
        ids_por_clave = {}
        for row in rows:
            clave = (
                str(row[1] or "").strip().upper(),   # planilla
                str(row[2] or ""),                    # fecha_tarea
                str(row[3] or "").strip(),            # legajo_campo
                str(row[4] or "").strip().upper(),    # nombre_empleado
                str(row[5] or "").strip().upper(),    # nombre_tarea
                str(row[6] or "").strip().upper(),    # nombre_cliente
                str(row[7] or "").strip().upper(),    # nombre_finca
                str(row[8] or "").strip().upper(),    # nombre_tractor
                _n(row[9]),                           # hsjornal
                _n(row[10]),                          # hsmaquina
                _n(row[11]),                          # tancadas
                _n(row[12]),                          # unidades
            )
            claves_existentes[clave] = True
            ids_por_clave[clave] = row[0]

        # ── Eliminar las que ya no están en campo ────────────────────────────
        claves_a_eliminar = set(ids_por_clave.keys()) - set(claves_campo.keys())
        eliminadas = 0
        if claves_a_eliminar:
            ids_eliminar = tuple(ids_por_clave[c] for c in claves_a_eliminar)
            self.db.execute(
                sql_text("DELETE FROM ajuste_manual WHERE linea_id IN :ids"),
                {"ids": ids_eliminar}
            )
            self.db.execute(
                sql_text("DELETE FROM concepto_adicional WHERE linea_id IN :ids"),
                {"ids": ids_eliminar}
            )
            self.db.execute(
                sql_text("DELETE FROM preliquidacion_linea WHERE id IN :ids"),
                {"ids": ids_eliminar}
            )
            eliminadas = len(ids_eliminar)

        # ── Insertar las nuevas ───────────────────────────────────────────────
        claves_a_insertar = set(claves_campo.keys()) - set(claves_existentes.keys())
        insertadas = 0

        if claves_a_insertar:
            filas_nuevas = [claves_campo[c] for c in claves_a_insertar]
            cache = self._construir_cache(quincena)
            indices_duplicados = self.motor.detectar_duplicados(filas_nuevas)
            dias_asturiana = self._contar_dias_asturiana(filas_campo)

            nuevos_conceptos = {}

            nuevas_lineas_y_reglas = []
            for i, fila in enumerate(filas_nuevas):
                linea, reglas = self._procesar_fila_con_cache(
                    fila=fila,
                    quincena=quincena,
                    preliquidacion_id=preliq.id,
                    es_duplicado=(i in indices_duplicados),
                    dias_asturiana=dias_asturiana,
                    cache=cache,
                    nuevos_conceptos=nuevos_conceptos,
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

            self._insertar_conceptos_nuevos(nuevos_conceptos)

        sin_cambios = len(claves_existentes) - eliminadas

        self.db.commit()

        return {
            "preliquidacion_id": preliq.id,
            "insertadas": insertadas,
            "eliminadas": eliminadas,
            "sin_cambios": sin_cambios,
        }

    # ─── Cache en memoria ────────────────────────────────────────────────────

    def _construir_cache(self, quincena: date) -> dict:
        precios_maestro = self.db.query(PrecioMaestro).filter(
            PrecioMaestro.quincena == quincena
        ).all()
        cache_precios = {
            (p.cliente_nombre, p.finca_nombre, p.tarea_nombre): p
            for p in precios_maestro
        }

        precios_comunes = self.db.query(PrecioComun).filter(
            PrecioComun.quincena == quincena
        ).all()
        cache_comunes = {p.tarea_nombre: p for p in precios_comunes}

        # Maestro de conceptos: detalle normalizado → lista de reglas
        conceptos = self.db.query(ConceptoLiquidacion).all()
        cache_conceptos = {}
        for c in conceptos:
            clave = c.detalle.strip().upper()
            cache_conceptos.setdefault(clave, []).append(c)

        # Mapa nombre_tarea -> grupo_tarea, usado para la regla Citrusvil
        # (maquinaria vs cosecha). Viene de la BD externa de campo.
        tareas = self.externa.obtener_tareas()
        cache_grupo_tarea = {
            t["nombre"].strip().upper(): (t["grupo_tarea"] or "").strip().upper()
            for t in tareas
        }
        # Mapa nombre_tarea -> grupo_pago DE CATÁLOGO (fijo, no depende de si
        # ya se cargó un precio). Se usa para armar el `detalle` del maestro
        # de conceptos de forma estable, sin importar el orden de carga.
        cache_grupo_pago_catalogo = {
            t["nombre"].strip().upper(): (t["grupo_pago"] or "").strip().upper()
            for t in tareas
        }

        return {
            "precios": cache_precios,
            "comunes": cache_comunes,
            "conceptos": cache_conceptos,
            "grupo_tarea": cache_grupo_tarea,
            "grupo_pago_catalogo": cache_grupo_pago_catalogo,
        }

    def _armar_detalle_concepto(self, nombre_tarea, nombre_cliente, nombre_finca, grupo_pago) -> str:
        """
        Concatena en el mismo orden del maestro de conceptos:
        TAREA + CLIENTE + FINCA + GRUPO_PAGO
        """
        partes = [
            (nombre_tarea or "").strip(),
            (nombre_cliente or "").strip(),
            (nombre_finca or "").strip(),
            (grupo_pago or "").strip(),
        ]
        return " ".join(p for p in partes if p).upper()

    def _insertar_conceptos_nuevos(self, nuevos_conceptos: dict):
        """
        Inserta en concepto_liquidacion las combinaciones nuevas detectadas
        que no existían, sin reglas (para que el liquidador las complete
        después). Usa INSERT IGNORE para evitar duplicados.
        """
        if not nuevos_conceptos:
            return
        from sqlalchemy import text as sql_text
        for detalle in nuevos_conceptos:
            self.db.execute(
                sql_text(
                    "INSERT IGNORE INTO concepto_liquidacion (detalle, codigo, unidad_base, tipo) "
                    "VALUES (:d, NULL, 'fijo', 'OTRO')"
                ),
                {"d": detalle}
            )

    def _procesar_fila_con_cache(
        self,
        fila: dict,
        quincena: date,
        preliquidacion_id: int,
        es_duplicado: bool,
        dias_asturiana: dict,
        cache: dict,
        nuevos_conceptos: dict = None,
    ):
        legajo = str(fila.get("legajo", "") or "")
        nombre_cliente = fila.get("nombre_cliente", "") or ""
        nombre_finca = fila.get("nombre_finca", "") or ""
        nombre_tarea = fila.get("nombre_tarea", "") or ""

        dias_en_ast = dias_asturiana.get(legajo, 0)
        nombre_empleado = fila.get("nombre_empleado", "") or ""
        grupo_tarea_linea = cache["grupo_tarea"].get(nombre_tarea.strip().upper(), "")
        empresa, alerta_empresa = self.motor.resolver_empresa(
            nombre_cliente, nombre_tarea, legajo, dias_en_ast, nombre_empleado, grupo_tarea_linea
        )
        legajo_asignado, alerta_legajo = self._resolver_legajo_cache(legajo, empresa, cache)
        alerta_legajo = alerta_legajo or alerta_empresa
        precio_a, grupo_pago, sin_precio = self._buscar_precio_cache(
            nombre_cliente, nombre_finca, nombre_tarea, legajo, cache
        )

        # ── Resolver reglas de concepto de liquidación ──
        # Usa el grupo_pago de CATÁLOGO (fijo, de la tabla de tareas de campo),
        # no el grupo_pago_aplicado (que depende de si ya se cargó un precio
        # y por lo tanto puede variar el detalle según el orden de carga).
        grupo_pago_catalogo = cache["grupo_pago_catalogo"].get(nombre_tarea.strip().upper(), "")
        detalle_concepto = self._armar_detalle_concepto(
            nombre_tarea, nombre_cliente, nombre_finca, grupo_pago_catalogo
        )
        reglas = cache["conceptos"].get(detalle_concepto, [])
        # Solo cuentan como "reglas aplicables" las que tienen código asignado
        reglas_con_codigo = [r for r in reglas if r.codigo is not None]
        alerta_sin_codigo = len(reglas_con_codigo) == 0
        codigo_liquidacion = reglas_con_codigo[0].codigo if reglas_con_codigo else None

        # Si es una combinación nueva (no existe ninguna fila para ese detalle), marcarla
        if detalle_concepto and detalle_concepto not in cache["conceptos"] and nuevos_conceptos is not None:
            nuevos_conceptos[detalle_concepto] = True
            cache["conceptos"][detalle_concepto] = []

        hsjornal = self._to_decimal(fila.get("hsjornal"))
        tancadas = self._to_decimal(fila.get("tancadas"))
        unidades = self._to_decimal(fila.get("unidades"))

        importe_base = Decimal("0")
        if precio_a and not sin_precio:
            importe_base = self.motor.calcular_importe(
                precio=precio_a,
                grupo_pago=grupo_pago,
                hsjornal=hsjornal,
                tancadas=tancadas,
                unidades=unidades,
                nombre_cliente=nombre_cliente,
            )

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
            detalle_concepto=detalle_concepto,
            precio_a=precio_a,
            precio_b=None,
            precio_usado=PrecioUsado.A,
            importe_base=importe_base,
            importe_total=importe_base,
            revisado=False,
            es_duplicado=es_duplicado,
            alerta_legajo=alerta_legajo,
            alerta_empresa=alerta_empresa,
            alerta_sin_precio=sin_precio,
            alerta_sin_codigo=alerta_sin_codigo,
        )
        return linea, reglas_con_codigo

    def _generar_conceptos_automaticos(
        self,
        linea: PreliquidacionLinea,
        reglas: list,
    ) -> list[ConceptoAdicional]:
        """
        Genera los ConceptoAdicional automáticos a partir de las reglas
        del maestro de conceptos que matchean el detalle de la línea.
        Cada regla define: código, unidad_base, precio (opcional) y tipo.
        """
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
                ingresado_por=None,  # automático, no manual
            ))
        return conceptos

    def _resolver_legajo_cache(self, legajo_campo, empresa_asignada, cache):
        if self.sueldos:
            return self.sueldos.resolver_legajo(legajo_campo, empresa_asignada)
        return legajo_campo, False

    def _buscar_precio_cache(self, nombre_cliente, nombre_finca, nombre_tarea, legajo, cache):
        if "MANTENIMIENTO" in nombre_tarea.upper() and "TALLER" in nombre_tarea.upper():
            categoria = self.sueldos.obtener_categoria(legajo) if self.sueldos else None
            if categoria:
                nombre_concepto = f"MANTENIMIENTOS MECANICOS (TALLERES) {categoria}"
                comun = cache["comunes"].get(nombre_concepto)
                if comun:
                    return comun.precio, comun.grupo_pago, False
            return None, "HORAS TALLER", True

        registro = cache["precios"].get((nombre_cliente, nombre_finca, nombre_tarea))
        if registro:
            grupo = registro.grupo_pago_override or registro.grupo_pago_default
            return registro.precio_a, grupo, registro.precio_a is None

        comun = cache["comunes"].get(nombre_tarea)
        if comun:
            return comun.precio, comun.grupo_pago, False

        return None, "", True

    def _contar_dias_asturiana(self, filas):
        conteo = {}
        for fila in filas:
            if str(fila.get("nombre_cliente", "")).upper() != "CITRUSVIL":
                legajo = str(fila.get("legajo", ""))
                fecha = fila.get("fecha_tarea")
                if legajo and fecha:
                    clave = (legajo, fecha)
                    if clave not in conteo:
                        conteo[clave] = True
        resultado = {}
        for legajo, _ in conteo:
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
        Recalcula precios e importes de todas las líneas usando UPDATE SQL
        masivo en vez de loop Python — entre 10 y 50x más rápido porque
        evita el overhead de red por cada fila y deja que MySQL haga el
        trabajo en memoria con sus índices.

        Casos especiales (MANTENIMIENTO TALLER) se siguen procesando en
        Python porque dependen de datos externos (categoría del legajo).
        """
        from sqlalchemy import text as sql_text

        preliq = self.db.query(Preliquidacion).filter(
            Preliquidacion.id == preliq_id
        ).first()
        if not preliq:
            raise ValueError(f"Preliquidacion {preliq_id} no encontrada")

        quincena = preliq.quincena

        # ── Paso 1: aplicar precios desde precio_maestro ─────────────────
        self.db.execute(sql_text("""
            UPDATE preliquidacion_linea pl
            INNER JOIN precio_maestro pm
                ON pm.cliente_nombre = pl.nombre_cliente
                AND pm.finca_nombre  = pl.nombre_finca
                AND pm.tarea_nombre  = pl.nombre_tarea
                AND pm.quincena      = :quincena
            SET
                pl.precio_a              = pm.precio_a,
                pl.grupo_pago_aplicado   = COALESCE(pm.grupo_pago_override, pm.grupo_pago_default),
                pl.alerta_sin_precio     = CASE WHEN pm.precio_a IS NULL THEN 1 ELSE 0 END,
                pl.importe_base = CASE
                    WHEN pm.precio_a IS NULL THEN 0
                    WHEN UPPER(COALESCE(pm.grupo_pago_override, pm.grupo_pago_default)) IN ('TANCADA')
                        THEN pm.precio_a * COALESCE(pl.tancadas, 0)
                    WHEN UPPER(COALESCE(pm.grupo_pago_override, pm.grupo_pago_default)) IN ('PLANTA','BINS')
                        THEN pm.precio_a * COALESCE(pl.unidades, 0)
                    WHEN UPPER(COALESCE(pm.grupo_pago_override, pm.grupo_pago_default)) IN (
                        'HORAS TRACTOR','HORAS PEON','HORAS SUPERVISOR',
                        'HORAS SERENO','HORAS ENGANCHADOR',
                        'HORAS PEON - COSECHA','HORAS COLECTIVO'
                    ) THEN pm.precio_a * COALESCE(pl.hsjornal, 0)
                    ELSE 0
                END,
                pl.importe_total = CASE
                    WHEN pm.precio_a IS NULL THEN COALESCE(pl.importe_total, 0)
                    WHEN UPPER(COALESCE(pm.grupo_pago_override, pm.grupo_pago_default)) IN ('TANCADA')
                        THEN pm.precio_a * COALESCE(pl.tancadas, 0)
                    WHEN UPPER(COALESCE(pm.grupo_pago_override, pm.grupo_pago_default)) IN ('PLANTA','BINS')
                        THEN pm.precio_a * COALESCE(pl.unidades, 0)
                    WHEN UPPER(COALESCE(pm.grupo_pago_override, pm.grupo_pago_default)) IN (
                        'HORAS TRACTOR','HORAS PEON','HORAS SUPERVISOR',
                        'HORAS SERENO','HORAS ENGANCHADOR',
                        'HORAS PEON - COSECHA','HORAS COLECTIVO'
                    ) THEN pm.precio_a * COALESCE(pl.hsjornal, 0)
                    ELSE 0
                END
            WHERE pl.preliquidacion_id = :pid
        """), {"pid": preliq_id, "quincena": quincena})

        # ── Paso 2: precio_comun como fallback ────────────────────────────
        self.db.execute(sql_text("""
            UPDATE preliquidacion_linea pl
            INNER JOIN precio_comun pc
                ON pc.tarea_nombre = pl.nombre_tarea
                AND pc.quincena    = :quincena
            SET
                pl.precio_a            = pc.precio,
                pl.grupo_pago_aplicado = pc.grupo_pago,
                pl.alerta_sin_precio   = 0,
                pl.importe_base = CASE
                    WHEN UPPER(pc.grupo_pago) IN ('TANCADA')
                        THEN pc.precio * COALESCE(pl.tancadas, 0)
                    WHEN UPPER(pc.grupo_pago) IN ('PLANTA','BINS')
                        THEN pc.precio * COALESCE(pl.unidades, 0)
                    WHEN UPPER(pc.grupo_pago) IN (
                        'HORAS TRACTOR','HORAS PEON','HORAS SUPERVISOR',
                        'HORAS SERENO','HORAS ENGANCHADOR',
                        'HORAS PEON - COSECHA','HORAS COLECTIVO'
                    ) THEN pc.precio * COALESCE(pl.hsjornal, 0)
                    ELSE 0
                END,
                pl.importe_total = CASE
                    WHEN UPPER(pc.grupo_pago) IN ('TANCADA')
                        THEN pc.precio * COALESCE(pl.tancadas, 0)
                    WHEN UPPER(pc.grupo_pago) IN ('PLANTA','BINS')
                        THEN pc.precio * COALESCE(pl.unidades, 0)
                    WHEN UPPER(pc.grupo_pago) IN (
                        'HORAS TRACTOR','HORAS PEON','HORAS SUPERVISOR',
                        'HORAS SERENO','HORAS ENGANCHADOR',
                        'HORAS PEON - COSECHA','HORAS COLECTIVO'
                    ) THEN pc.precio * COALESCE(pl.hsjornal, 0)
                    ELSE 0
                END
            WHERE pl.preliquidacion_id = :pid
              AND (pl.precio_a IS NULL OR pl.alerta_sin_precio = 1)
              AND pl.nombre_tarea NOT LIKE '%MANTENIMIENTO%'
        """), {"pid": preliq_id, "quincena": quincena})

        # ── Paso 3: marcar sin precio las que no matchearon ningún maestro ─
        self.db.execute(sql_text("""
            UPDATE preliquidacion_linea
            SET precio_a          = NULL,
                importe_base      = 0,
                alerta_sin_precio = 1
            WHERE preliquidacion_id = :pid
              AND precio_a IS NULL
              AND nombre_tarea NOT LIKE '%MANTENIMIENTO%'
        """), {"pid": preliq_id})

        self.db.commit()

        # ── Paso 4: MANTENIMIENTO TALLER — caso especial en Python ────────
        actualizadas_taller = 0
        if self.sueldos:
            lineas_taller = self.db.query(PreliquidacionLinea).filter(
                PreliquidacionLinea.preliquidacion_id == preliq_id,
                PreliquidacionLinea.nombre_tarea.ilike("%MANTENIMIENTO%"),
                PreliquidacionLinea.nombre_tarea.ilike("%TALLER%"),
            ).options(joinedload(PreliquidacionLinea.conceptos)).all()

            if lineas_taller:
                cache = self._construir_cache(quincena)
                for linea in lineas_taller:
                    precio_a, grupo_pago, sin_p = self._buscar_precio_cache(
                        linea.nombre_cliente or '',
                        linea.nombre_finca or '',
                        linea.nombre_tarea or '',
                        linea.legajo_campo or '',
                        cache,
                    )
                    linea.precio_a = precio_a
                    linea.grupo_pago_aplicado = grupo_pago
                    linea.alerta_sin_precio = sin_p
                    if not sin_p:
                        linea.importe_base = self.motor.calcular_importe(
                            precio=precio_a,
                            grupo_pago=grupo_pago,
                            hsjornal=linea.hsjornal,
                            tancadas=linea.tancadas,
                            unidades=linea.unidades,
                            nombre_cliente=linea.nombre_cliente or '',
                        )
                    else:
                        linea.importe_base = Decimal("0")
                    suma_conceptos = sum(c.importe for c in linea.conceptos if c.importe)
                    linea.importe_total = (linea.importe_base or Decimal("0")) + suma_conceptos
                    actualizadas_taller += 1
                self.db.commit()

        # ── Conteo final ──────────────────────────────────────────────────
        stats = self.db.execute(sql_text("""
            SELECT
                SUM(CASE WHEN alerta_sin_precio = 0 THEN 1 ELSE 0 END) AS actualizadas,
                SUM(CASE WHEN alerta_sin_precio = 1 THEN 1 ELSE 0 END) AS sin_precio
            FROM preliquidacion_linea
            WHERE preliquidacion_id = :pid
        """), {"pid": preliq_id}).fetchone()

        return {
            "actualizadas": (stats[0] or 0) + actualizadas_taller,
            "sin_precio": stats[1] or 0,
        }

    # ─── Backfill de detalles en maestro de conceptos ─────────────────────────

    def backfill_detalles_conceptos(self, preliq_id: int) -> dict:
        """
        Recorre las líneas existentes de una preliquidación y asegura que
        cada `detalle` (tarea+cliente+finca+grupo_pago) exista en
        concepto_liquidacion, aunque sea sin reglas. Útil para poblar
        el maestro por primera vez o después de un reset de la tabla.
        """
        from sqlalchemy import text as sql_text

        preliq = self.db.query(Preliquidacion).filter(
            Preliquidacion.id == preliq_id
        ).first()
        if not preliq:
            raise ValueError(f"Preliquidacion {preliq_id} no encontrada")

        tareas = self.externa.obtener_tareas()
        grupo_pago_catalogo = {
            t["nombre"].strip().upper(): (t["grupo_pago"] or "").strip().upper()
            for t in tareas
        }

        lineas = self.db.query(PreliquidacionLinea).filter(
            PreliquidacionLinea.preliquidacion_id == preliq_id
        ).all()

        detalles = set()
        for linea in lineas:
            gp_catalogo = grupo_pago_catalogo.get((linea.nombre_tarea or "").strip().upper(), "")
            detalle = linea.detalle_concepto or self._armar_detalle_concepto(
                linea.nombre_tarea, linea.nombre_cliente,
                linea.nombre_finca, gp_catalogo,
            )
            if detalle:
                detalles.add(detalle)
                if not linea.detalle_concepto:
                    # Congelar el detalle en líneas viejas que no lo tenían
                    linea.detalle_concepto = detalle

        insertados = 0
        for detalle in detalles:
            existe = self.db.execute(
                sql_text("SELECT 1 FROM concepto_liquidacion WHERE detalle = :d LIMIT 1"),
                {"d": detalle}
            ).fetchone()
            if not existe:
                self.db.execute(
                    sql_text(
                        "INSERT INTO concepto_liquidacion (detalle, codigo, unidad_base, tipo) "
                        "VALUES (:d, NULL, 'fijo', 'OTRO')"
                    ),
                    {"d": detalle}
                )
                insertados += 1

        self.db.commit()
        return {"detalles_unicos": len(detalles), "insertados": insertados}

    # ─── Aplicar conceptos automáticos (pasivo) ───────────────────────────────

    def aplicar_conceptos(self, preliq_id: int) -> dict:
        """
        Recorre las líneas y, si existen reglas en el maestro de conceptos
        para su detalle, genera/regenera los ConceptoAdicional automáticos
        (jornal remunerativo, no remunerativo, plus bins, etc.)

        Optimización anti-lock: en vez de hacer DELETE fila por fila dentro
        de un loop (que acumula locks de InnoDB durante toda la transacción
        y causa 'Lock wait timeout exceeded'), borra TODOS los automáticos
        de la preliquidación en un solo SQL al inicio, commitea para liberar
        los locks, y después inserta los nuevos en un segundo commit.
        """
        from sqlalchemy import text as sql_text

        preliq = self.db.query(Preliquidacion).filter(
            Preliquidacion.id == preliq_id
        ).first()
        if not preliq:
            raise ValueError(f"Preliquidacion {preliq_id} no encontrada")

        # ── Paso 1: borrar TODOS los conceptos automáticos de esta preliq ──
        # Un solo DELETE masivo libera los locks en un commit rápido,
        # sin acumularlos línea por línea durante el loop que sigue.
        self.db.execute(sql_text("""
            DELETE ca FROM concepto_adicional ca
            INNER JOIN preliquidacion_linea pl ON pl.id = ca.linea_id
            WHERE pl.preliquidacion_id = :pid
              AND ca.ingresado_por IS NULL
        """), {"pid": preliq_id})
        self.db.commit()

        # ── Paso 2: construir cache de reglas y datos ─────────────────────
        conceptos = self.db.query(ConceptoLiquidacion).all()
        cache_reglas = {}
        for c in conceptos:
            if c.codigo is None:
                continue
            clave = c.detalle.strip().upper()
            cache_reglas.setdefault(clave, []).append(c)

        tareas = self.externa.obtener_tareas()
        grupo_pago_catalogo = {
            t["nombre"].strip().upper(): (t["grupo_pago"] or "").strip().upper()
            for t in tareas
        }

        lineas = self.db.query(PreliquidacionLinea).filter(
            PreliquidacionLinea.preliquidacion_id == preliq_id,
        ).options(joinedload(PreliquidacionLinea.conceptos)).all()

        actualizadas = 0
        sin_reglas = 0
        conceptos_nuevos = []

        # ── Paso 3: generar nuevos conceptos automáticos ──────────────────
        for linea in lineas:
            gp_catalogo = grupo_pago_catalogo.get((linea.nombre_tarea or "").strip().upper(), "")
            detalle = linea.detalle_concepto or self._armar_detalle_concepto(
                linea.nombre_tarea, linea.nombre_cliente,
                linea.nombre_finca, gp_catalogo,
            )
            reglas = cache_reglas.get(detalle.strip().upper(), [])

            if not reglas:
                if linea.alerta_sin_codigo:
                    sin_reglas += 1
                else:
                    # Tenía código pero ya no tiene reglas: marcar alerta
                    linea.codigo_liquidacion = None
                    linea.alerta_sin_codigo = True
                    self._recalcular_importe(linea)
                    actualizadas += 1
                continue

            nuevos = self._generar_conceptos_automaticos(linea, reglas)
            conceptos_nuevos.extend(nuevos)

            linea.codigo_liquidacion = reglas[0].codigo
            linea.alerta_sin_codigo = False
            self._recalcular_importe(linea)
            actualizadas += 1

        # ── Paso 4: insertar todos los nuevos de una sola vez y commitear ─
        if conceptos_nuevos:
            self.db.bulk_save_objects(conceptos_nuevos)

        self.db.commit()

        # ── Paso 5: recalcular importes con los conceptos ya insertados ───
        # bulk_save_objects no actualiza los ids en memoria, así que
        # recargamos las líneas modificadas para recalcular importe_total.
        ids_actualizadas = {l.id for l in lineas if any(
            cache_reglas.get((l.detalle_concepto or "").strip().upper(), [])
        )}
        if ids_actualizadas:
            lineas_recarga = self.db.query(PreliquidacionLinea).filter(
                PreliquidacionLinea.id.in_(ids_actualizadas)
            ).options(joinedload(PreliquidacionLinea.conceptos)).all()
            for linea in lineas_recarga:
                self._recalcular_importe(linea)
            self.db.commit()

        return {"actualizadas": actualizadas, "sin_reglas": sin_reglas}

    # ─── Dashboard de verificación ────────────────────────────────────────────

    def dashboard_verificacion(self, preliq_id: int) -> dict:
        """
        Controles diarios para que el liquidador detecte registros a revisar:
        - >13 hs jornal por empleado+fecha (sumando todas sus líneas del día)
        - >35 tancadas por empleado+fecha
        - >6000 unidades (plantas) por empleado+fecha — SOLO cuenta líneas
          cuyo grupo_pago_aplicado es "PLANTA"; bins, poda, fertilización
          y otras tareas que también usan la columna `unidades` no entran
          en este control (no representan plantas).
        Y el resumen por empleado: importe total, días trabajados, $/día,
        con el desglose de líneas crudas debajo de cada uno.
        """
        lineas = self.db.query(PreliquidacionLinea).filter(
            PreliquidacionLinea.preliquidacion_id == preliq_id
        ).options(joinedload(PreliquidacionLinea.conceptos)).all()

        # Agrupar por (legajo_asignado o legajo_campo, fecha) para los controles diarios
        por_empleado_fecha = {}
        for linea in lineas:
            legajo = linea.legajo_asignado or linea.legajo_campo or ""
            fecha = str(linea.fecha_tarea) if linea.fecha_tarea else ""
            clave = (legajo, fecha)
            if clave not in por_empleado_fecha:
                por_empleado_fecha[clave] = {
                    "legajo": legajo,
                    "nombre_empleado": linea.nombre_empleado,
                    "fecha": fecha,
                    "hsjornal": Decimal("0"),
                    "tancadas": Decimal("0"),
                    "plantas": Decimal("0"),
                    "lineas": [],
                }
            grupo = por_empleado_fecha[clave]
            grupo["hsjornal"] += linea.hsjornal or Decimal("0")
            grupo["tancadas"] += linea.tancadas or Decimal("0")
            es_plantas = (linea.grupo_pago_aplicado or "").strip().upper() == "PLANTA"
            if es_plantas:
                grupo["plantas"] += linea.unidades or Decimal("0")
            grupo["lineas"].append({
                "id": linea.id,
                "nombre_tarea": linea.nombre_tarea,
                "nombre_cliente": linea.nombre_cliente,
                "nombre_finca": linea.nombre_finca,
                "grupo_pago_aplicado": linea.grupo_pago_aplicado,
                "hsjornal": float(linea.hsjornal or 0),
                "tancadas": float(linea.tancadas or 0),
                "unidades": float(linea.unidades or 0),
            })

        exceso_horas = []
        exceso_tancadas = []
        exceso_plantas = []

        for grupo in por_empleado_fecha.values():
            base = {
                "legajo": grupo["legajo"],
                "nombre_empleado": grupo["nombre_empleado"],
                "fecha": grupo["fecha"],
                "lineas": grupo["lineas"],
            }
            if grupo["hsjornal"] > 13:
                exceso_horas.append({**base, "valor": float(grupo["hsjornal"])})
            if grupo["tancadas"] > 35:
                exceso_tancadas.append({**base, "valor": float(grupo["tancadas"])})
            if grupo["plantas"] > 6000:
                exceso_plantas.append({**base, "valor": float(grupo["plantas"])})

        exceso_horas.sort(key=lambda x: -x["valor"])
        exceso_tancadas.sort(key=lambda x: -x["valor"])
        exceso_plantas.sort(key=lambda x: -x["valor"])

        # Resumen por empleado: importe total + días trabajados + $/día,
        # con desglose de líneas crudas
        por_empleado = {}
        for linea in lineas:
            legajo = linea.legajo_asignado or linea.legajo_campo or ""
            if legajo not in por_empleado:
                por_empleado[legajo] = {
                    "legajo": legajo,
                    "nombre_empleado": linea.nombre_empleado,
                    "empresa_asignada": linea.empresa_asignada,
                    "importe_total": Decimal("0"),
                    "fechas": set(),
                    "lineas": [],
                }
            emp = por_empleado[legajo]
            emp["importe_total"] += linea.importe_total or Decimal("0")
            if linea.fecha_tarea:
                emp["fechas"].add(str(linea.fecha_tarea))
            emp["lineas"].append({
                "id": linea.id,
                "fecha_tarea": str(linea.fecha_tarea) if linea.fecha_tarea else None,
                "nombre_tarea": linea.nombre_tarea,
                "nombre_cliente": linea.nombre_cliente,
                "nombre_finca": linea.nombre_finca,
                "hsjornal": float(linea.hsjornal or 0),
                "importe_total": float(linea.importe_total or 0),
            })

        resumen_empleados = []
        for emp in por_empleado.values():
            dias = len(emp["fechas"])
            importe = float(emp["importe_total"])
            resumen_empleados.append({
                "legajo": emp["legajo"],
                "nombre_empleado": emp["nombre_empleado"],
                "empresa_asignada": emp["empresa_asignada"],
                "importe_total": importe,
                "dias_trabajados": dias,
                "importe_por_dia": round(importe / dias, 2) if dias else 0,
                "lineas": sorted(emp["lineas"], key=lambda l: l["fecha_tarea"] or ""),
            })
        resumen_empleados.sort(key=lambda x: -x["importe_total"])

        return {
            "exceso_horas": exceso_horas,
            "exceso_tancadas": exceso_tancadas,
            "exceso_plantas": exceso_plantas,
            "resumen_empleados": resumen_empleados,
        }

    # ─── Control Plantas vs Jornal (análisis gerencial) ───────────────────────

    def control_plantas_jornal(self, preliq_id: int) -> dict:
        """
        Agrupa por cliente→finca→tarea (solo líneas con grupo_pago_aplicado
        = "PLANTA") y calcula:
        - precio_promedio: AVG(precio_a)
        - unidades: SUM(unidades) — plantas totales
        - hs: SUM(hsmaquina)
        - plantas_por_hsm: unidades / hs
        - plantas_por_hsm_x8: plantas_por_hsm * 8 (rendimiento en un jornal de 8hs)
        - prom_jornal: plantas_por_hsm_x8 * precio_promedio — cuánto cobraría
          ese jornal a ese ritmo y precio; el liquidador y el gerente usan
          este número para decidir cuánto pagarle a cada persona.
        """
        lineas = self.db.query(PreliquidacionLinea).filter(
            PreliquidacionLinea.preliquidacion_id == preliq_id,
            PreliquidacionLinea.grupo_pago_aplicado == "PLANTA",
        ).all()

        grupos = {}
        for linea in lineas:
            clave = (
                linea.nombre_cliente or "",
                linea.nombre_finca or "",
                linea.nombre_tarea or "",
            )
            if clave not in grupos:
                grupos[clave] = {
                    "nombre_cliente": linea.nombre_cliente,
                    "nombre_finca": linea.nombre_finca,
                    "nombre_tarea": linea.nombre_tarea,
                    "suma_precio": Decimal("0"),
                    "cantidad_precios": 0,
                    "unidades": Decimal("0"),
                    "hs": Decimal("0"),
                }
            g = grupos[clave]
            if linea.precio_a is not None:
                g["suma_precio"] += linea.precio_a
                g["cantidad_precios"] += 1
            g["unidades"] += linea.unidades or Decimal("0")
            g["hs"] += linea.hsmaquina or Decimal("0")

        filas = []
        for g in grupos.values():
            precio_prom = (
                float(g["suma_precio"] / g["cantidad_precios"])
                if g["cantidad_precios"] else 0
            )
            unidades = float(g["unidades"])
            hs = float(g["hs"])
            plantas_por_hsm = (unidades / hs) if hs else 0
            plantas_por_hsm_x8 = plantas_por_hsm * 8
            prom_jornal = plantas_por_hsm_x8 * precio_prom

            filas.append({
                "nombre_cliente": g["nombre_cliente"],
                "nombre_finca": g["nombre_finca"],
                "nombre_tarea": g["nombre_tarea"],
                "precio_promedio": round(precio_prom, 2),
                "unidades": round(unidades, 2),
                "hs": round(hs, 2),
                "plantas_por_hsm": round(plantas_por_hsm, 2),
                "plantas_por_hsm_x8": round(plantas_por_hsm_x8, 2),
                "prom_jornal": round(prom_jornal, 2),
            })

        filas.sort(key=lambda f: (f["nombre_cliente"] or "", f["nombre_finca"] or "", f["nombre_tarea"] or ""))

        # Totales generales
        total_unidades = sum(f["unidades"] for f in filas)
        total_hs = sum(f["hs"] for f in filas)
        total_precio_prom = (
            sum(f["precio_promedio"] for f in filas) / len(filas) if filas else 0
        )
        total_plantas_hsm = (total_unidades / total_hs) if total_hs else 0
        total_plantas_hsm_x8 = total_plantas_hsm * 8
        total_prom_jornal = total_plantas_hsm_x8 * total_precio_prom

        return {
            "filas": filas,
            "totales": {
                "unidades": round(total_unidades, 2),
                "hs": round(total_hs, 2),
                "precio_promedio": round(total_precio_prom, 2),
                "plantas_por_hsm": round(total_plantas_hsm, 2),
                "plantas_por_hsm_x8": round(total_plantas_hsm_x8, 2),
                "prom_jornal": round(total_prom_jornal, 2),
            },
        }

    # ─── Consultas ────────────────────────────────────────────────────────────

    def listar(self) -> list[Preliquidacion]:
        return self.db.query(Preliquidacion).order_by(
            Preliquidacion.quincena.desc()
        ).all()

    def obtener(self, preliq_id: int) -> Optional[Preliquidacion]:
        return self.db.query(Preliquidacion).filter(
            Preliquidacion.id == preliq_id
        ).first()

    def listar_lineas(
        self,
        preliq_id: int,
        empresa: Optional[str] = None,
        revisado: Optional[bool] = None,
        solo_alertas: Optional[bool] = None,
        nombre_empleado: Optional[str] = None,
    ) -> list[PreliquidacionLinea]:
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
            q = q.filter(
                PreliquidacionLinea.nombre_empleado.ilike(f"%{nombre_empleado}%")
            )
        return q.order_by(
            PreliquidacionLinea.empresa_asignada,
            PreliquidacionLinea.nombre_empleado,
            PreliquidacionLinea.fecha_tarea,
        ).all()

    # ─── Actualizar línea ─────────────────────────────────────────────────────

    def actualizar_linea(self, linea_id, datos: LineaUpdateRequest, usuario_id) -> PreliquidacionLinea:
        linea = self.db.query(PreliquidacionLinea).filter(
            PreliquidacionLinea.id == linea_id
        ).first()
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
                linea_id=linea_id,
                campo_modificado=campo,
                valor_anterior=str(valor_anterior),
                valor_nuevo=str(valor_nuevo),
                motivo=datos.motivo_ajuste,
                usuario_id=usuario_id,
            ))
            setattr(linea, campo, valor_nuevo)

        self._recalcular_importe(linea)
        if datos.empresa_asignada:
            linea.alerta_legajo = False

        self.db.commit()
        self.db.refresh(linea)
        return linea

    def _recalcular_importe(self, linea: PreliquidacionLinea):
        precio = (
            linea.precio_b
            if linea.precio_usado == PrecioUsado.B and linea.precio_b
            else linea.precio_a
        )
        if precio and linea.grupo_pago_aplicado:
            linea.importe_base = self.motor.calcular_importe(
                precio=precio,
                grupo_pago=linea.grupo_pago_aplicado,
                hsjornal=linea.hsjornal,
                tancadas=linea.tancadas,
                unidades=linea.unidades,
                nombre_cliente=linea.nombre_cliente or "",
            )
        suma_conceptos = sum(c.importe for c in linea.conceptos if c.importe)
        linea.importe_total = (linea.importe_base or Decimal("0")) + suma_conceptos

    # ─── Conceptos adicionales ────────────────────────────────────────────────

    def agregar_concepto(self, linea_id, datos: ConceptoAdicionalRequest, usuario_id) -> ConceptoAdicional:
        linea = self.db.query(PreliquidacionLinea).filter(
            PreliquidacionLinea.id == linea_id
        ).options(joinedload(PreliquidacionLinea.conceptos)).first()
        if not linea:
            raise ValueError(f"Línea {linea_id} no encontrada")

        concepto = ConceptoAdicional(
            linea_id=linea_id,
            descripcion=datos.descripcion,
            tipo=datos.tipo,
            importe=datos.importe,
            ingresado_por=usuario_id,
        )
        self.db.add(concepto)
        self.db.flush()
        self._recalcular_importe(linea)
        self.db.commit()
        self.db.refresh(concepto)
        return concepto

    def eliminar_concepto(self, concepto_id, usuario_id):
        concepto = self.db.query(ConceptoAdicional).filter(
            ConceptoAdicional.id == concepto_id
        ).first()
        if not concepto:
            raise ValueError(f"Concepto {concepto_id} no encontrado")
        linea = concepto.linea
        self.db.delete(concepto)
        self.db.flush()
        self._recalcular_importe(linea)
        self.db.commit()

    # ─── Agregar concepto por código (manual) ────────────────────────────────

    def agregar_concepto_por_codigo(self, linea_id: int, codigo: int, usuario_id: int) -> ConceptoAdicional:
        """
        El liquidador busca un código del maestro de conceptos y lo agrega
        a esta línea puntual. Si el código tiene varias reglas con el mismo
        número (poco común), usa la primera. El importe se calcula con la
        unidad_base/precio de esa regla aplicada a esta línea.
        """
        linea = self.db.query(PreliquidacionLinea).filter(
            PreliquidacionLinea.id == linea_id
        ).options(joinedload(PreliquidacionLinea.conceptos)).first()
        if not linea:
            raise ValueError(f"Línea {linea_id} no encontrada")

        regla = self.db.query(ConceptoLiquidacion).filter(
            ConceptoLiquidacion.codigo == codigo
        ).first()
        if not regla:
            raise ValueError(f"No existe ningún concepto con código {codigo} en el maestro")

        nuevos = self._generar_conceptos_automaticos(linea, [regla])
        concepto = nuevos[0]
        concepto.ingresado_por = usuario_id  # manual, no automático
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
            "lineas_con_alerta": sum(
                1 for l in lineas
                if l.es_duplicado or l.alerta_legajo or l.alerta_sin_precio or l.alerta_sin_codigo
            ),
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

    # ─── Operaciones masivas por empleado ─────────────────────────────────────

    def agregar_concepto_masivo(self, linea_ids: list[int], codigo: int, usuario_id: int) -> dict:
        """
        Agrega un concepto por código a múltiples líneas de una vez.
        El liquidador selecciona las líneas con checkboxes y aplica el mismo
        concepto a todas sin tener que ir línea por línea.
        """
        regla = self.db.query(ConceptoLiquidacion).filter(
            ConceptoLiquidacion.codigo == codigo
        ).first()
        if not regla:
            raise ValueError(f"No existe ningún concepto con código {codigo} en el maestro")

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
        """
        Elimina todos los ConceptoAdicional con ese código de las líneas indicadas.
        Permite deshacer una aplicación masiva de un solo golpe.
        """
        from sqlalchemy import text as sql_text

        if not linea_ids:
            return {"eliminados": 0, "lineas": 0}

        # Eliminar en un solo DELETE masivo para evitar locks
        result = self.db.execute(sql_text("""
            DELETE FROM concepto_adicional
            WHERE linea_id IN :ids
              AND codigo_concepto = :codigo
        """), {"ids": tuple(linea_ids), "codigo": codigo})
        eliminados = result.rowcount
        self.db.commit()

        # Recalcular importes de las líneas afectadas
        lineas = self.db.query(PreliquidacionLinea).filter(
            PreliquidacionLinea.id.in_(linea_ids)
        ).options(joinedload(PreliquidacionLinea.conceptos)).all()
        for linea in lineas:
            self._recalcular_importe(linea)
        self.db.commit()

        return {"eliminados": eliminados, "lineas": len(lineas)}