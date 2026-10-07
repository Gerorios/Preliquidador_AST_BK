from decimal import Decimal, ROUND_HALF_UP
from typing import Optional
from sqlalchemy.orm import Session


def normalizar_decimal(v) -> str:
    """Representación canónica a 2 decimales de un valor de campo, idéntica a
    lo que la columna DECIMAL(x,2) guarda: half-up (como MySQL), sin cero
    negativo (MySQL no lo tiene) y 'None' para nulos/no-numéricos/NaN/inf.
    La usan la clave del diff de actualización y la detección de duplicados:
    el formateo por float redondeaba '12.985' a '12.98' (MySQL guarda 12.99)
    y la línea churneaba en cada actualización."""
    if v is None:
        return "None"
    try:
        d = Decimal(str(v)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except Exception:
        return "None"
    if not d.is_finite():
        return "None"
    if d == 0:
        d = abs(d)
    return str(d)


def clave_posible_duplicado(linea: dict) -> tuple:
    """Clave de una línea de campo sin las horas (jornal y máquina): nombres
    con `.strip().upper()`, legajo con `.strip()`, fecha con `str()` y las
    cantidades con `normalizar_decimal`. `detectar_duplicados` le suma las
    horas, así hay una sola definición de "misma línea"."""
    norm = normalizar_decimal
    return (
        str(linea.get("planilla") or "").strip().upper(),
        str(linea.get("fecha_tarea") or ""),
        str(linea.get("legajo") or "").strip(),
        str(linea.get("nombre_empleado") or "").strip().upper(),
        str(linea.get("nombre_tarea") or "").strip().upper(),
        str(linea.get("nombre_cliente") or "").strip().upper(),
        str(linea.get("nombre_finca") or "").strip().upper(),
        str(linea.get("nombre_tractor") or "").strip().upper(),
        norm(linea.get("tancadas")),
        norm(linea.get("unidades")),
    )


def paga_cantidad(linea: dict) -> bool:
    """True si la línea trae unidades o tancadas no nulas y mayores a 0, con
    la misma normalización que la clave (a 2 decimales, como se guarda)."""
    for campo in ("unidades", "tancadas"):
        valor = normalizar_decimal(linea.get(campo))
        if valor != "None" and Decimal(valor) > 0:
            return True
    return False


class MotorReglas:

    def __init__(self, db_propia: Session, sueldos_service=None):
        self.db = db_propia
        self.sueldos = sueldos_service

    # ─── Empresa ─────────────────────────────────────────────────────────────

    GRUPOS_COSECHA = {
        "SERVICIOS DE CARGA FRUTA",
        "SERVICIOS DE MOVIMIENTO DE FRUTA",
        "SERVICIOS DE COSECHA",
    }

    def resolver_empresa(
        self,
        nombre_cliente: str,
        nombre_tarea: str,
        legajo_campo: str,
        dias_en_asturiana: int = 0,
        nombre_empleado: str = "",
        grupo_tarea: str = "",
    ) -> tuple[str, bool]:
        if self.sueldos:
            empresa, alerta = self.sueldos.resolver_empresa_por_legajo(
                legajo_campo, nombre_empleado
            )
        else:
            empresa, alerta = "LA ASTURIANA", False

        es_maquinaria = self._es_tarea_maquinaria(grupo_tarea)
        es_citrusvil = nombre_cliente.upper() == "CITRUSVIL"
        if es_maquinaria and es_citrusvil:
            if dias_en_asturiana >= 10:
                empresa = "LA ASTURIANA"
            else:
                empresa = "PAMPLONA"
            alerta = False

        return empresa, alerta

    def _es_tarea_maquinaria(self, grupo_tarea: str) -> bool:
        if not grupo_tarea:
            return False
        return grupo_tarea.strip().upper() not in self.GRUPOS_COSECHA

    # ─── Legajo ───────────────────────────────────────────────────────────────

    def resolver_legajo(self, legajo_campo: str, empresa_asignada: str) -> tuple[str, bool]:
        if self.sueldos:
            return self.sueldos.resolver_legajo(legajo_campo, empresa_asignada)
        return legajo_campo, False

    # ─── Conceptos de liquidación automáticos ────────────────────────────────

    def calcular_cantidad_concepto(
        self,
        unidad_base: str,
        hsjornal: Optional[Decimal],
        hsmaquina: Optional[Decimal],
        tancadas: Optional[Decimal],
        unidades: Optional[Decimal],
    ) -> Decimal:
        """
        jornal_tope1: >= 5hs → 1, > 0 < 5hs → 0.5, 0 → 0
        jornal_tope1_mas_excedente: igual a jornal_tope1 hasta 10hs;
            > 10hs → hsjornal/10 redondeado a 2 decimales (cantidad es Numeric(10,2))
        """
        hsjornal  = hsjornal  or Decimal("0")
        hsmaquina = hsmaquina or Decimal("0")
        tancadas  = tancadas  or Decimal("0")
        unidades  = unidades  or Decimal("0")

        if unidad_base == "hsjornal":    return hsjornal
        if unidad_base == "hsmaquina":   return hsmaquina
        if unidad_base == "tancadas":    return tancadas
        if unidad_base == "unidades":    return unidades
        if unidad_base == "jornal_tope1":
            if hsjornal >= Decimal("5"):  return Decimal("1")
            elif hsjornal > Decimal("0"): return Decimal("0.5")
            else:                         return Decimal("0")
        if unidad_base == "jornal_tope1_mas_excedente":
            if hsjornal > Decimal("10"):
                return (hsjornal / Decimal("10")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            elif hsjornal >= Decimal("5"): return Decimal("1")
            elif hsjornal > Decimal("0"):  return Decimal("0.5")
            else:                          return Decimal("0")
        if unidad_base == "fijo":        return Decimal("1")
        return Decimal("0")

    # ─── Duplicados ───────────────────────────────────────────────────────────

    def detectar_duplicados(self, lineas: list[dict]) -> set[int]:
        norm = normalizar_decimal
        vistos = {}
        duplicados = set()
        for i, linea in enumerate(lineas):
            clave = clave_posible_duplicado(linea) + (
                norm(linea.get("hsjornal")),
                norm(linea.get("hsmaquina")),
            )
            if clave in vistos:
                duplicados.add(i)
                duplicados.add(vistos[clave])
            else:
                vistos[clave] = i
        return duplicados

    def detectar_posibles_duplicados(
        self, lineas: list[dict], duplicados=frozenset()
    ) -> set[int]:
        """Índices de las líneas que son posible duplicado: otra línea de la
        misma lista es igual en planilla, fecha, legajo, empleado, tarea,
        cliente, finca, tractor, unidades y tancadas (la clave de
        `clave_posible_duplicado`), paga una cantidad mayor a 0 y tiene horas
        distintas (jornal o máquina).

        Sólo cuentan las líneas con cantidad > 0: sin ese filtro, las tareas
        por hora (misma cantidad nula, horas distintas) salen como posibles y
        casi siempre son trabajo real.

        Excluyente con Duplicado: los índices de `duplicados` (lo que devolvió
        `detectar_duplicados`) nunca se marcan. Un grupo se marca sólo si tiene
        dos o más pares distintos de horas; si todas sus líneas son idénticas
        entre sí, ya son duplicadas y no hay duda que marcar."""
        norm = normalizar_decimal
        grupos: dict[tuple, list[int]] = {}
        for i, linea in enumerate(lineas):
            if paga_cantidad(linea):
                grupos.setdefault(clave_posible_duplicado(linea), []).append(i)

        posibles = set()
        for indices in grupos.values():
            horas = {
                (norm(lineas[i].get("hsjornal")), norm(lineas[i].get("hsmaquina")))
                for i in indices
            }
            if len(horas) >= 2:
                posibles.update(i for i in indices if i not in duplicados)
        return posibles