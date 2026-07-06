from decimal import Decimal
from typing import Optional
from sqlalchemy.orm import Session


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
        if unidad_base == "fijo":        return Decimal("1")
        return Decimal("0")

    # ─── Duplicados ───────────────────────────────────────────────────────────

    def detectar_duplicados(self, lineas: list[dict]) -> set[int]:
        def norm(v) -> str:
            if v is None: return "None"
            try: return f"{float(str(v)):.2f}"
            except: return "None"

        vistos = {}
        duplicados = set()
        for i, linea in enumerate(lineas):
            clave = (
                str(linea.get("planilla") or "").strip().upper(),
                str(linea.get("fecha_tarea") or ""),
                str(linea.get("legajo") or "").strip(),
                str(linea.get("nombre_empleado") or "").strip().upper(),
                str(linea.get("nombre_tarea") or "").strip().upper(),
                str(linea.get("nombre_cliente") or "").strip().upper(),
                str(linea.get("nombre_finca") or "").strip().upper(),
                str(linea.get("nombre_tractor") or "").strip().upper(),
                norm(linea.get("hsjornal")),
                norm(linea.get("hsmaquina")),
                norm(linea.get("tancadas")),
                norm(linea.get("unidades")),
            )
            if clave in vistos:
                duplicados.add(i)
                duplicados.add(vistos[clave])
            else:
                vistos[clave] = i
        return duplicados 