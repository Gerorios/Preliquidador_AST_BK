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
from datetime import date
from typing import Optional

from sqlalchemy import func

from app.models.models import ConceptoLiquidacion, Preliquidacion
from app.services.preliquidacion_service import PreliquidacionService

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


def _reglas_eje_cliente(db, quincena: date, tarea_nombre: str, cliente_nombre: str):
    """Todas las reglas de esa quincena/tarea/cliente (normalizado), sin
    supervisor. Devuelve (por_cliente, especificos)."""
    reglas = db.query(ConceptoLiquidacion).filter(
        ConceptoLiquidacion.quincena == quincena,
        func.upper(func.trim(ConceptoLiquidacion.tarea_nombre)) == _norm(tarea_nombre),
        func.upper(func.trim(ConceptoLiquidacion.cliente_nombre)) == _norm(cliente_nombre),
        ConceptoLiquidacion.supervisor_nombre.is_(None),
    ).all()
    por_cliente = [c for c in reglas if not (c.finca_nombre or "").strip()]
    especificos = [c for c in reglas if (c.finca_nombre or "").strip()]
    return por_cliente, especificos


def _contar_lineas_doble_match(db, quincena: date, tarea_nombre: str, cliente_nombre: str,
                               lado_pc: list, lado_esp: list) -> int:
    """Líneas de la quincena (tarea + cliente) para las que pasa al menos una
    regla por cliente Y al menos una específica de su finca, aplicando el
    filtro de categoría de cada regla a la persona de la línea (ADR-0008).

    lado_pc / lado_esp son listas de dicts {"finca_nombre"?, "categoria"}:
    sirven tanto para reglas existentes como para el candidato que todavía
    no está en la base.
    """
    preliq = db.query(Preliquidacion).filter(Preliquidacion.quincena == quincena).first()
    if not preliq or not lado_pc or not lado_esp:
        return 0
    svc = PreliquidacionService(db)
    cat_por_cuil = svc._categoria_por_cuil(quincena)
    lineas = svc._lineas_por_match(preliq.id, tarea_nombre, cliente_nombre)

    def pasa(regla: dict, cuil) -> bool:
        cat = regla.get("categoria")
        return cat is None or cat == cat_por_cuil.get(_norm(cuil))

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


def _armar(quincena, tarea_nombre, cliente_nombre, direccion, por_cliente: list,
           especificos: list, lado_pc_dicts: list, lado_esp_dicts: list, db) -> dict:
    codigos_pc = {d.get("codigo") for d in lado_pc_dicts if d.get("codigo") is not None}
    codigos_esp = {d.get("codigo") for d in lado_esp_dicts if d.get("codigo") is not None}
    return {
        "tarea_nombre": tarea_nombre,
        "cliente_nombre": cliente_nombre,
        "direccion": direccion,
        "reglas_por_cliente": [_regla_por_cliente_dict(c) for c in por_cliente],
        "especificos": [_especifico_dict(c, codigos_pc) for c in especificos],
        "fincas": sorted({_norm(d.get("finca_nombre")) for d in lado_esp_dicts}),
        "codigos_coincidentes": sorted(codigos_pc & codigos_esp),
        "lineas_afectadas": _contar_lineas_doble_match(
            db, quincena, tarea_nombre, cliente_nombre, lado_pc_dicts, lado_esp_dicts,
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

    candidato = {"codigo": codigo, "categoria": categoria,
                 "finca_nombre": _norm(finca_nombre) or None}

    if candidato["finca_nombre"] is None:
        # Candidato POR CLIENTE: contraparte = específicas compatibles.
        contra = [e for e in especificos if categorias_compatibles(e.categoria, categoria)]
        if not contra:
            return None
        esp_dicts = [{"finca_nombre": e.finca_nombre, "categoria": e.categoria, "codigo": e.codigo}
                     for e in contra]
        return _armar(quincena, tarea_n, cliente_n, DIRECCION_POR_CLIENTE,
                      por_cliente=[], especificos=contra,
                      lado_pc_dicts=[candidato], lado_esp_dicts=esp_dicts, db=db)

    # Candidato ESPECÍFICO: contraparte = reglas por cliente compatibles.
    contra = [pc for pc in por_cliente if categorias_compatibles(pc.categoria, categoria)]
    if not contra:
        return None
    pc_dicts = [{"categoria": pc.categoria, "codigo": pc.codigo} for pc in contra]
    return _armar(quincena, tarea_n, cliente_n, DIRECCION_ESPECIFICO,
                  por_cliente=contra, especificos=[],
                  lado_pc_dicts=pc_dicts, lado_esp_dicts=[candidato], db=db)


def listar_solapamientos(db, quincena: date) -> list:
    """Solapamientos por cliente VIGENTES en la quincena: un ítem por par
    (tarea, cliente) con al menos una regla por cliente y al menos una
    específica compatible por categoría. Alimenta la franja de aviso de la
    página de Conceptos y el detalle de la copia entre quincenas."""
    reglas = db.query(ConceptoLiquidacion).filter(
        ConceptoLiquidacion.quincena == quincena,
        ConceptoLiquidacion.cliente_nombre.isnot(None),
        ConceptoLiquidacion.supervisor_nombre.is_(None),
    ).all()

    pares: dict = {}
    for c in reglas:
        if not _norm(c.cliente_nombre):
            continue
        clave = (_norm(c.tarea_nombre), _norm(c.cliente_nombre))
        pc, esp = pares.setdefault(clave, ([], []))
        (esp if (c.finca_nombre or "").strip() else pc).append(c)

    resultado = []
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
            quincena, tarea_n, cliente_n, DIRECCION_POR_CLIENTE,
            por_cliente=por_cliente, especificos=compatibles,
            lado_pc_dicts=pc_dicts, lado_esp_dicts=esp_dicts, db=db,
        ))
    return resultado
