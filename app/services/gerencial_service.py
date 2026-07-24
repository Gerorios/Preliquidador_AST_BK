# ─── Servicio de KPIs gerenciales ────────────────────────────────────────────
#
# Vista gerencial (solo lectura): mano de obra gastada por período, por
# cliente, por grupo de tareas, y desvíos por persona contra su propia media
# histórica. Ver CONTEXT.md: "Mano de obra gastada", "Grupo de tareas",
# "Desvío por persona".
#
# Todas las agregaciones usan PreliquidacionLinea.importe_total, que ya es la
# suma de los conceptos adicionales de la línea (manuales incluidos) — no hace
# falta joinear concepto_adicional.
#
# Período: una quincena exacta (fecha) o un mes calendario ("YYYY-MM" = sus
# quincenas presentes en la base). El desvío por persona compara promedios
# POR QUINCENA (no totales del período) para que quincena y mes sean
# comparables entre sí y contra la historia.

from collections import defaultdict
from datetime import date

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.models import Preliquidacion, PreliquidacionLinea


# Desvío por persona (ver CONTEXT.md): últimas 6 quincenas con actividad,
# mínimo 3 para que la comparación exista. El umbral es configurable por
# request; esto es solo el default.
VENTANA_HISTORICA = 6
MINIMO_QUINCENAS_HISTORIA = 3
UMBRAL_DESVIO_DEFAULT = 30.0


class PeriodoInvalidoError(ValueError):
    pass


class GerencialService:
    def __init__(self, db_propia: Session):
        self.db = db_propia

    # ─── Períodos ────────────────────────────────────────────────────────────

    def quincenas_disponibles(self) -> list[date]:
        filas = self.db.query(Preliquidacion.quincena).order_by(
            Preliquidacion.quincena.desc()
        ).all()
        return [q for (q,) in filas]

    def _quincenas_del_mes(self, mes: str) -> list[date]:
        try:
            anio, nro_mes = (int(p) for p in mes.split("-"))
        except ValueError:
            raise PeriodoInvalidoError(f"Mes inválido: {mes!r} (formato YYYY-MM)")
        return [
            q for q in self.quincenas_disponibles()
            if q.year == anio and q.month == nro_mes
        ]

    def _resolver_periodo(self, quincena: date | None, mes: str | None) -> list[date]:
        """Devuelve las quincenas que componen el período pedido."""
        if (quincena is None) == (mes is None):
            raise PeriodoInvalidoError("Indicar exactamente uno: quincena o mes")
        if quincena is not None:
            if quincena not in self.quincenas_disponibles():
                raise PeriodoInvalidoError(f"No existe preliquidación de la quincena {quincena}")
            return [quincena]
        quincenas = self._quincenas_del_mes(mes)
        if not quincenas:
            raise PeriodoInvalidoError(f"No hay preliquidaciones en el mes {mes}")
        return quincenas

    def _periodo_anterior(self, quincena: date | None, mes: str | None) -> list[date]:
        """Quincenas del período inmediato anterior con datos (para comparar)."""
        disponibles = sorted(self.quincenas_disponibles())
        if quincena is not None:
            previas = [q for q in disponibles if q < quincena]
            return previas[-1:] if previas else []
        quincenas_mes = self._quincenas_del_mes(mes)
        inicio = min(quincenas_mes)
        previas = [q for q in disponibles if q < inicio]
        if not previas:
            return []
        ultima = previas[-1]
        return [q for q in previas if (q.year, q.month) == (ultima.year, ultima.month)]

    # ─── Agregaciones base ───────────────────────────────────────────────────

    def _lineas_periodo(self, quincenas: list[date], empresa: str | None):
        q = (
            self.db.query(PreliquidacionLinea)
            .join(Preliquidacion)
            .filter(Preliquidacion.quincena.in_(quincenas))
        )
        if empresa:
            q = q.filter(PreliquidacionLinea.empresa_asignada == empresa)
        return q

    def _totales(self, quincenas: list[date], empresa: str | None) -> dict:
        fila = (
            self._lineas_periodo(quincenas, empresa)
            .with_entities(
                func.coalesce(func.sum(PreliquidacionLinea.importe_total), 0),
                func.count(func.distinct(PreliquidacionLinea.cuit)),
                func.count(PreliquidacionLinea.id),
            )
            .one()
        )
        return {
            "total": float(fila[0]),
            "personas": int(fila[1]),
            "lineas": int(fila[2]),
        }

    # ─── Paneles ─────────────────────────────────────────────────────────────

    def resumen(self, quincena: date | None, mes: str | None, empresa: str | None) -> dict:
        quincenas = self._resolver_periodo(quincena, mes)
        actual = self._totales(quincenas, empresa)

        anteriores = self._periodo_anterior(quincena, mes)
        anterior = self._totales(anteriores, empresa) if anteriores else None

        variacion_pct = None
        if anterior and anterior["total"] > 0:
            variacion_pct = round((actual["total"] / anterior["total"] - 1) * 100, 1)

        return {
            "quincenas": [str(q) for q in quincenas],
            "empresa": empresa,
            "total": actual["total"],
            "personas": actual["personas"],
            "lineas": actual["lineas"],
            "periodo_anterior": {
                "quincenas": [str(q) for q in anteriores],
                "total": anterior["total"],
            } if anterior else None,
            "variacion_pct": variacion_pct,
        }

    def evolucion(self, empresa: str | None, limite: int = 24) -> list[dict]:
        q = self.db.query(
            Preliquidacion.quincena,
            func.coalesce(func.sum(PreliquidacionLinea.importe_total), 0),
            func.count(func.distinct(PreliquidacionLinea.cuit)),
        ).join(PreliquidacionLinea)
        if empresa:
            q = q.filter(PreliquidacionLinea.empresa_asignada == empresa)
        filas = (
            q.group_by(Preliquidacion.quincena)
            .order_by(Preliquidacion.quincena.desc())
            .limit(limite)
            .all()
        )
        return [
            {"quincena": str(qq), "total": float(total), "personas": int(personas)}
            for qq, total, personas in reversed(filas)
        ]

    def por_cliente(self, quincena: date | None, mes: str | None, empresa: str | None) -> list[dict]:
        quincenas = self._resolver_periodo(quincena, mes)
        filas = (
            self._lineas_periodo(quincenas, empresa)
            .with_entities(
                PreliquidacionLinea.nombre_cliente,
                func.coalesce(func.sum(PreliquidacionLinea.importe_total), 0),
                func.count(PreliquidacionLinea.id),
            )
            .group_by(PreliquidacionLinea.nombre_cliente)
            .all()
        )
        total_general = float(sum(f[1] for f in filas)) or 1.0
        resultado = [
            {
                "cliente": cliente or "SIN CLIENTE",
                "total": float(total),
                "lineas": int(lineas),
                "porcentaje": round(float(total) / total_general * 100, 1),
            }
            for cliente, total, lineas in filas
        ]
        return sorted(resultado, key=lambda r: r["total"], reverse=True)

    def por_grupo_tarea(
        self,
        quincena: date | None,
        mes: str | None,
        empresa: str | None,
        grupos_catalogo: dict[str, str],
        grupo: str | None = None,
    ) -> list[dict]:
        """Desglose por grupo_tarea del catálogo (resuelto por nombre de tarea).
        Con `grupo`, drill: devuelve las tareas de ese grupo. Las tareas que ya
        no están en el catálogo caen en "SIN GRUPO"."""
        quincenas = self._resolver_periodo(quincena, mes)
        filas = (
            self._lineas_periodo(quincenas, empresa)
            .with_entities(
                PreliquidacionLinea.nombre_tarea,
                func.coalesce(func.sum(PreliquidacionLinea.importe_total), 0),
                func.count(PreliquidacionLinea.id),
            )
            .group_by(PreliquidacionLinea.nombre_tarea)
            .all()
        )
        total_general = float(sum(f[1] for f in filas)) or 1.0

        if grupo is not None:
            tareas = [
                {
                    "tarea": tarea,
                    "total": float(total),
                    "lineas": int(lineas),
                    "porcentaje": round(float(total) / total_general * 100, 1),
                }
                for tarea, total, lineas in filas
                if grupos_catalogo.get(tarea, "SIN GRUPO") == grupo
            ]
            return sorted(tareas, key=lambda r: r["total"], reverse=True)

        acumulado: dict[str, dict] = defaultdict(lambda: {"total": 0.0, "lineas": 0, "tareas": 0})
        for tarea, total, lineas in filas:
            g = grupos_catalogo.get(tarea, "SIN GRUPO")
            acumulado[g]["total"] += float(total)
            acumulado[g]["lineas"] += int(lineas)
            acumulado[g]["tareas"] += 1
        resultado = [
            {
                "grupo": g,
                "total": datos["total"],
                "lineas": datos["lineas"],
                "tareas": datos["tareas"],
                "porcentaje": round(datos["total"] / total_general * 100, 1),
            }
            for g, datos in acumulado.items()
        ]
        return sorted(resultado, key=lambda r: r["total"], reverse=True)

    def desvios_por_persona(
        self,
        quincena: date | None,
        mes: str | None,
        empresa: str | None,
        umbral_pct: float = UMBRAL_DESVIO_DEFAULT,
    ) -> dict:
        """Cada persona contra su propia media histórica (ver CONTEXT.md,
        "Desvío por persona"). Se comparan promedios POR QUINCENA: para un mes,
        el promedio de sus quincenas con actividad."""
        quincenas_periodo = set(self._resolver_periodo(quincena, mes))
        inicio_periodo = min(quincenas_periodo)

        q = self.db.query(
            Preliquidacion.quincena,
            PreliquidacionLinea.cuit,
            func.max(PreliquidacionLinea.nombre_empleado),
            func.coalesce(func.sum(PreliquidacionLinea.importe_total), 0),
        ).join(PreliquidacionLinea)
        if empresa:
            q = q.filter(PreliquidacionLinea.empresa_asignada == empresa)
        q = q.group_by(Preliquidacion.quincena, PreliquidacionLinea.cuit)

        por_persona: dict[str, dict] = {}
        for qcna, cuil, nombre, total in q.all():
            datos = por_persona.setdefault(cuil, {"nombre": nombre, "actual": [], "historia": {}})
            datos["nombre"] = nombre or datos["nombre"]
            if qcna in quincenas_periodo:
                datos["actual"].append(float(total))
            elif qcna < inicio_periodo:
                datos["historia"][qcna] = float(total)

        comparables, sin_historial = [], []
        for cuil, datos in por_persona.items():
            if not datos["actual"]:
                continue  # sin actividad en el período
            promedio_actual = sum(datos["actual"]) / len(datos["actual"])
            historia = [
                total for _, total in sorted(datos["historia"].items(), reverse=True)
            ][:VENTANA_HISTORICA]
            persona = {
                "cuil": cuil,
                "nombre": datos["nombre"],
                "promedio_quincenal": round(promedio_actual, 2),
                "quincenas_historia": len(historia),
            }
            if len(historia) < MINIMO_QUINCENAS_HISTORIA:
                sin_historial.append(persona)
                continue
            media = sum(historia) / len(historia)
            desvio = round((promedio_actual / media - 1) * 100, 1) if media > 0 else None
            persona.update({
                "media_historica": round(media, 2),
                "desvio_pct": desvio,
                "supera_umbral": desvio is not None and desvio >= umbral_pct,
            })
            comparables.append(persona)

        comparables.sort(key=lambda p: (p["desvio_pct"] is None, -(p["desvio_pct"] or 0)))
        sin_historial.sort(key=lambda p: -p["promedio_quincenal"])
        return {
            "umbral_pct": umbral_pct,
            "ventana_quincenas": VENTANA_HISTORICA,
            "minimo_quincenas": MINIMO_QUINCENAS_HISTORIA,
            "personas": comparables,
            "sin_historial": sin_historial,
        }
