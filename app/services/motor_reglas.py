from datetime import date
from decimal import Decimal
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.models.models import PrecioMaestro, PrecioComun

GRUPOS_PAGO_HORAS = {
    "HORAS TRACTOR", "HORAS PEON", "HORAS SUPERVISOR",
    "HORAS TALLER", "HORAS SERENO", "HORAS ENGANCHADOR",
    "HORAS PEON - COSECHA", "HORAS COLECTIVO",
}
GRUPOS_PAGO_TANCADA = {"TANCADA"}
GRUPOS_PAGO_UNIDADES = {"PLANTA", "BINS"}
CLIENTES_JORNAL_PROPORCIONAL: set[str] = set()
VALOR_JORNAL = Decimal("45000.00")
VALOR_BIN = Decimal("150.00")
HORAS_MINIMAS_JORNAL = Decimal("5")


class MotorReglas:

    def __init__(self, db_propia: Session, sueldos_service=None):
        self.db = db_propia
        self.sueldos = sueldos_service

    # ─── Empresa ─────────────────────────────────────────────────────────────

    # Grupos de tarea que NO cuentan como "maquinaria" para la regla Citrusvil.
    # Son los grupos de cosecha — confirmados por el liquidador.
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
        """
        Devuelve (empresa_asignada, alerta_empresa).
        Prioridad: sistema de sueldos → regla Citrusvil → default Asturiana

        Regla Citrusvil: si la tarea es de "maquinaria" (cualquier grupo_tarea
        que NO sea de cosecha) y el cliente es Citrusvil → Pamplona
        (salvo que la persona ya tenga 10+ días en Asturiana esta quincena).
        """
        # Resolver desde sistema de sueldos con doble validación legajo + nombre
        if self.sueldos:
            empresa, alerta = self.sueldos.resolver_empresa_por_legajo(
                legajo_campo, nombre_empleado
            )
        else:
            empresa, alerta = "LA ASTURIANA", False

        # Aplicar regla especial Citrusvil sobre lo que devolvió sueldos
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
        """
        Una tarea es de "maquinaria" si su grupo_tarea NO es uno de los
        grupos de cosecha. Si no se conoce el grupo_tarea (vacío), se
        considera que NO es maquinaria (más conservador: evita asignar
        Pamplona por error cuando falta el dato).
        """
        if not grupo_tarea:
            return False
        return grupo_tarea.strip().upper() not in self.GRUPOS_COSECHA

    # ─── Legajo ───────────────────────────────────────────────────────────────

    def resolver_legajo(
        self,
        legajo_campo: str,
        empresa_asignada: str,
    ) -> tuple[str, bool]:
        if self.sueldos:
            return self.sueldos.resolver_legajo(legajo_campo, empresa_asignada)
        return legajo_campo, False

    # ─── Precio ───────────────────────────────────────────────────────────────

    def buscar_precio(
        self,
        nombre_cliente: str,
        nombre_finca: str,
        nombre_tarea: str,
        quincena: date,
        legajo: Optional[str] = None,
    ) -> tuple[Optional[Decimal], str, bool]:

        if "MANTENIMIENTO" in nombre_tarea.upper() and "TALLER" in nombre_tarea.upper():
            return self._precio_mantenimiento_taller(legajo, quincena)

        registro = self.db.query(PrecioMaestro).filter(
            and_(
                PrecioMaestro.cliente_nombre == nombre_cliente,
                PrecioMaestro.finca_nombre == nombre_finca,
                PrecioMaestro.tarea_nombre == nombre_tarea,
                PrecioMaestro.quincena == quincena,
            )
        ).first()

        if registro:
            grupo = registro.grupo_pago_override or registro.grupo_pago_default
            return registro.precio_a, grupo, registro.precio_a is None

        comun = self.db.query(PrecioComun).filter(
            and_(
                PrecioComun.tarea_nombre == nombre_tarea,
                PrecioComun.quincena == quincena,
            )
        ).first()

        if comun:
            return comun.precio, comun.grupo_pago, False

        return None, "", True

    def _precio_mantenimiento_taller(
        self,
        legajo: Optional[str],
        quincena: date,
    ) -> tuple[Optional[Decimal], str, bool]:

        if not legajo:
            return None, "HORAS TALLER", True

        categoria = self.sueldos.obtener_categoria(legajo) if self.sueldos else None
        if not categoria:
            return None, "HORAS TALLER", True

        nombre_concepto = f"MANTENIMIENTOS MECANICOS (TALLERES) {categoria}"
        comun = self.db.query(PrecioComun).filter(
            and_(
                PrecioComun.tarea_nombre == nombre_concepto,
                PrecioComun.quincena == quincena,
            )
        ).first()

        if comun:
            return comun.precio, comun.grupo_pago, False

        return None, "HORAS TALLER", True

    # ─── Importe ──────────────────────────────────────────────────────────────

    def calcular_importe(
        self,
        precio: Decimal,
        grupo_pago: str,
        hsjornal: Optional[Decimal],
        tancadas: Optional[Decimal],
        unidades: Optional[Decimal],
        nombre_cliente: str = "",
    ) -> Decimal:
        if precio is None:
            return Decimal("0")
        gp = grupo_pago.upper()
        if gp in GRUPOS_PAGO_TANCADA:
            return precio * (tancadas or Decimal("0"))
        if gp in GRUPOS_PAGO_UNIDADES:
            return precio * (unidades or Decimal("0"))
        if gp in GRUPOS_PAGO_HORAS:
            return precio * (hsjornal or Decimal("0"))
        return Decimal("0")

    def calcular_jornal(self, hsjornal: Decimal, nombre_cliente: str = "") -> Optional[Decimal]:
        if hsjornal is None or hsjornal <= HORAS_MINIMAS_JORNAL:
            return None
        cliente_upper = nombre_cliente.upper()
        if cliente_upper in CLIENTES_JORNAL_PROPORCIONAL:
            if hsjornal >= 12:
                multiplicador = Decimal("1.2")
            elif hsjornal >= 11:
                multiplicador = Decimal("1.1")
            else:
                multiplicador = Decimal("1.0")
        else:
            multiplicador = Decimal("1.0")
        return VALOR_JORNAL * multiplicador

    def calcular_bins(self, bins: Decimal) -> Decimal:
        return VALOR_BIN * (bins or Decimal("0"))

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
        Calcula la cantidad sobre la que se aplica el precio de un
        concepto de liquidación, según su unidad_base.

        jornal_tope1: cuenta como 1 jornal si hsjornal >= 5hs,
        como 0.5 jornal si 0 < hsjornal < 5, y como 0 si no hay horas.
        """
        hsjornal = hsjornal or Decimal("0")
        hsmaquina = hsmaquina or Decimal("0")
        tancadas = tancadas or Decimal("0")
        unidades = unidades or Decimal("0")

        if unidad_base == "hsjornal":
            return hsjornal
        if unidad_base == "hsmaquina":
            return hsmaquina
        if unidad_base == "tancadas":
            return tancadas
        if unidad_base == "unidades":
            return unidades
        if unidad_base == "jornal_tope1":
            if hsjornal >= Decimal("5"):
                return Decimal("1")
            elif hsjornal > Decimal("0"):
                return Decimal("0.5")
            else:
                return Decimal("0")
        if unidad_base == "fijo":
            return Decimal("1")
        return Decimal("0")

    # ─── Duplicados ───────────────────────────────────────────────────────────

    def detectar_duplicados(self, lineas: list[dict]) -> set[int]:
        def norm(v) -> str:
            if v is None:
                return "None"
            try:
                return f"{float(str(v)):.2f}"
            except Exception:
                return "None"

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