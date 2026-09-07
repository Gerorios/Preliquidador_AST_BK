"""Solapamiento por cliente (CONTEXT.md).

Para la misma quincena y tarea, una regla POR CLIENTE (cliente sin finca, sin
supervisor) y una o más ESPECÍFICAS (cliente + finca) de ESE MISMO cliente
matchean las mismas líneas y, por ADR-0011, SUMAN. No es un error del
modelo: es un riesgo de pago doble que el liquidador debe controlar. Este
módulo lo detecta (para la compuerta del POST y para el listado vigente);
NO cambia el matching.

Reglas:
- La categoría participa: dos categorías explícitas y distintas NO solapan
  (pagan a personas distintas). NULL en alguna, o iguales → solapan.
- El código coincidente es agravante (se informa), no condición.
- El cruce con el eje supervisor y el común vs no-común NO son solapamiento.
"""
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from sqlalchemy import func

from app.modulos.preliquidacion.models import ConceptoLiquidacion, Preliquidacion
from app.modulos.preliquidacion.services.preliquidacion_service import PreliquidacionService

DIRECCION_POR_CLIENTE = "por_cliente_sobre_especificos"
DIRECCION_ESPECIFICO = "especifico_sobre_por_cliente"


def _norm(s: Optional[str]) -> str:
    return (s or "").strip().upper()


def categorias_compatibles(a: Optional[int], b: Optional[int]) -> bool:
    """Dos reglas pueden matchear a la misma persona si alguna no tiene
    categoría o si tienen la misma."""
    return a is None or b is None or a == b


def _precio_str(p) -> Optional[str]:
    return None if p is None else str(p)


def _regla_por_cliente_dict(c: ConceptoLiquidacion) -> dict:
    return {"id": c.id, "codigo": c.codigo, "precio": _precio_str(c.precio),
            "categoria": c.categoria}


def _especifico_dict(c: ConceptoLiquidacion, codigos_otro_lado: set) -> dict:
    return {"id": c.id, "finca_nombre": c.finca_nombre, "codigo": c.codigo,
            "precio": _precio_str(c.precio), "categoria": c.categoria,
            "mismo_codigo": c.codigo is not None and c.codigo in codigos_otro_lado}


def _sin_supervisor():
    """Predicado "la regla NO es del eje supervisor": NULL o vacío/espacios.
    Una fila con supervisor_nombre = '' y cliente cargado matchea por el eje
    cliente y suma, así que participa del solapamiento. `coalesce` + `trim`
    funcionan igual en MySQL y en sqlite."""
    return func.coalesce(func.trim(ConceptoLiquidacion.supervisor_nombre), "") == ""


def _reglas_eje_cliente(db, quincena: date, tarea_nombre: str, cliente_nombre: str):
    """Todas las reglas de esa quincena/tarea/cliente (normalizado), sin
    supervisor. Devuelve (por_cliente, especificos)."""
    reglas = db.query(ConceptoLiquidacion).filter(
        ConceptoLiquidacion.quincena == quincena,
        func.upper(func.trim(ConceptoLiquidacion.tarea_nombre)) == _norm(tarea_nombre),
        func.upper(func.trim(ConceptoLiquidacion.cliente_nombre)) == _norm(cliente_nombre),
        _sin_supervisor(),
    ).all()
    por_cliente = [c for c in reglas if not (c.finca_nombre or "").strip()]
    especificos = [c for c in reglas if (c.finca_nombre or "").strip()]
    return por_cliente, especificos


@dataclass
class _ContextoLineas:
    """Invariantes de la quincena, calculados UNA vez y compartidos por todos
    los pares (tarea, cliente) que se arman: la preliquidación generada, el
    mapa de categorías por CUIL (ADR-0008) y un memo de líneas por par. Sin
    esto el listado hace N+1 consultas (una preliquidación, un scan de
    categoria_operario y una query de líneas por par)."""
    svc: Optional[PreliquidacionService] = None
    preliq_id: Optional[int] = None
    cat_por_cuil: dict = field(default_factory=dict)
    lineas_por_tarea_cliente: dict = field(default_factory=dict)

    def lineas(self, tarea_nombre: str, cliente_nombre: str) -> list:
        """Líneas de la quincena para (tarea, cliente), con expansión de alias
        de pago (ADR-0012). Sin preliquidación generada no hay consulta."""
        if self.preliq_id is None:
            return []
        clave = (_norm(tarea_nombre), _norm(cliente_nombre))
        if clave not in self.lineas_por_tarea_cliente:
            self.lineas_por_tarea_cliente[clave] = self.svc._lineas_por_match(
                self.preliq_id, tarea_nombre, cliente_nombre, con_conceptos=False,
            )
        return self.lineas_por_tarea_cliente[clave]


def _contexto(db, quincena: date) -> _ContextoLineas:
    preliq = db.query(Preliquidacion).filter(Preliquidacion.quincena == quincena).first()
    if not preliq:
        return _ContextoLineas()
    svc = PreliquidacionService(db)
    return _ContextoLineas(svc=svc, preliq_id=preliq.id,
                           cat_por_cuil=svc._categoria_por_cuil(quincena))


def _contar_lineas_doble_match(ctx: _ContextoLineas, tarea_nombre: str, cliente_nombre: str,
                               lado_pc: list, lado_esp: list) -> int:
    """Líneas de la quincena (tarea + cliente) para las que pasa al menos una
    regla por cliente Y al menos una específica de su finca, aplicando el
    filtro de categoría de cada regla a la persona de la línea (ADR-0008).

    lado_pc / lado_esp son listas de dicts {"finca_nombre"?, "categoria"}:
    sirven tanto para reglas existentes como para el candidato que todavía
    no está en la base.
    """
    if ctx.preliq_id is None or not lado_pc or not lado_esp:
        return 0
    lineas = ctx.lineas(tarea_nombre, cliente_nombre)

    def pasa(regla: dict, cuil) -> bool:
        # Misma derivación de clave que PreliquidacionService._filtrar_por_categoria.
        cat = regla.get("categoria")
        return cat is None or cat == ctx.cat_por_cuil.get((cuil or "").strip())

    esp_por_finca: dict = {}
    for e in lado_esp:
        esp_por_finca.setdefault(_norm(e.get("finca_nombre")), []).append(e)

    total = 0
    for l in lineas:
        if not any(pasa(pc, l.cuit) for pc in lado_pc):
            continue
        candidatas = esp_por_finca.get(_norm(l.nombre_finca), [])
        if any(pasa(e, l.cuit) for e in candidatas):
            total += 1
    return total


def _fincas_para_mostrar(lado_esp_dicts: list) -> list:
    """Nombres de finca tal como están escritos en el maestro (una entrada por
    finca distinta, con la primera grafía vista). Las comparaciones internas
    siguen siendo normalizadas."""
    vistas: dict = {}
    for d in lado_esp_dicts:
        crudo = (d.get("finca_nombre") or "").strip()
        vistas.setdefault(crudo.upper(), crudo)
    return sorted(vistas.values())


def _armar(tarea_nombre, cliente_nombre, direccion, por_cliente: list,
           especificos: list, lado_pc_dicts: list, lado_esp_dicts: list,
           ctx: _ContextoLineas) -> dict:
    codigos_pc = {d.get("codigo") for d in lado_pc_dicts if d.get("codigo") is not None}
    codigos_esp = {d.get("codigo") for d in lado_esp_dicts if d.get("codigo") is not None}
    return {
        "tarea_nombre": tarea_nombre,
        "cliente_nombre": cliente_nombre,
        "direccion": direccion,
        "reglas_por_cliente": [_regla_por_cliente_dict(c) for c in por_cliente],
        "especificos": [_especifico_dict(c, codigos_pc) for c in especificos],
        "fincas": _fincas_para_mostrar(lado_esp_dicts),
        "codigos_coincidentes": sorted(codigos_pc & codigos_esp),
        "lineas_afectadas": _contar_lineas_doble_match(
            ctx, tarea_nombre, cliente_nombre, lado_pc_dicts, lado_esp_dicts,
        ),
    }


def detectar_solapamiento_candidato(
    db, quincena: date, tarea_nombre: str, cliente_nombre: Optional[str],
    finca_nombre: Optional[str], supervisor_nombre: Optional[str],
    codigo: Optional[int], categoria: Optional[int],
) -> Optional[dict]:
    """¿La regla que se quiere crear solapa con reglas ya existentes del eje
    cliente? None si no (común, por supervisor, o sin contraparte)."""
    if not (cliente_nombre or "").strip() or (supervisor_nombre or "").strip():
        return None  # común o por supervisor: no participan
    tarea_n = _norm(tarea_nombre)
    cliente_n = _norm(cliente_nombre)
    por_cliente, especificos = _reglas_eje_cliente(db, quincena, tarea_n, cliente_n)

    # La finca del candidato va con su grafía cruda (se muestra tal cual); las
    # comparaciones contra las líneas la normalizan.
    candidato = {"codigo": codigo, "categoria": categoria,
                 "finca_nombre": (finca_nombre or "").strip() or None}

    if candidato["finca_nombre"] is None:
        # Candidato POR CLIENTE: contraparte = específicas compatibles.
        contra = [e for e in especificos if categorias_compatibles(e.categoria, categoria)]
        if not contra:
            return None
        esp_dicts = [{"finca_nombre": e.finca_nombre, "categoria": e.categoria, "codigo": e.codigo}
                     for e in contra]
        return _armar(tarea_n, cliente_n, DIRECCION_POR_CLIENTE,
                      por_cliente=[], especificos=contra,
                      lado_pc_dicts=[candidato], lado_esp_dicts=esp_dicts,
                      ctx=_contexto(db, quincena))

    # Candidato ESPECÍFICO: contraparte = reglas por cliente compatibles.
    contra = [pc for pc in por_cliente if categorias_compatibles(pc.categoria, categoria)]
    if not contra:
        return None
    pc_dicts = [{"categoria": pc.categoria, "codigo": pc.codigo} for pc in contra]
    return _armar(tarea_n, cliente_n, DIRECCION_ESPECIFICO,
                  por_cliente=contra, especificos=[],
                  lado_pc_dicts=pc_dicts, lado_esp_dicts=[candidato],
                  ctx=_contexto(db, quincena))


def listar_solapamientos(db, quincena: date) -> list[dict]:
    """Solapamientos por cliente VIGENTES en la quincena: un ítem por par
    (tarea, cliente) con al menos una regla por cliente y al menos una
    específica compatible por categoría. Alimenta la franja de aviso de la
    página de Conceptos y el detalle de la copia entre quincenas."""
    reglas = db.query(ConceptoLiquidacion).filter(
        ConceptoLiquidacion.quincena == quincena,
        ConceptoLiquidacion.cliente_nombre.isnot(None),
        _sin_supervisor(),
    ).all()

    pares: dict = {}
    for c in reglas:
        if not _norm(c.cliente_nombre):
            continue
        clave = (_norm(c.tarea_nombre), _norm(c.cliente_nombre))
        pc, esp = pares.setdefault(clave, ([], []))
        (esp if (c.finca_nombre or "").strip() else pc).append(c)

    resultado = []
    ctx = _contexto(db, quincena)   # invariantes de la quincena: una sola vez
    for (tarea_n, cliente_n), (por_cliente, especificos) in sorted(pares.items()):
        if not por_cliente or not especificos:
            continue
        compatibles = [
            e for e in especificos
            if any(categorias_compatibles(e.categoria, pc.categoria) for pc in por_cliente)
        ]
        if not compatibles:
            continue
        pc_dicts = [{"categoria": pc.categoria, "codigo": pc.codigo} for pc in por_cliente]
        esp_dicts = [{"finca_nombre": e.finca_nombre, "categoria": e.categoria, "codigo": e.codigo}
                     for e in compatibles]
        resultado.append(_armar(
            tarea_n, cliente_n, DIRECCION_POR_CLIENTE,
            por_cliente=por_cliente, especificos=compatibles,
            lado_pc_dicts=pc_dicts, lado_esp_dicts=esp_dicts, ctx=ctx,
        ))
    return resultado
