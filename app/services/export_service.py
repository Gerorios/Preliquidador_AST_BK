import io
from decimal import Decimal

from openpyxl import Workbook
from openpyxl.styles import Font
from sqlalchemy.orm import Session, joinedload

from app.models.models import Preliquidacion, PreliquidacionLinea


# ─── Export a Excel de una quincena ───────────────────────────────────────────
#
# Grano: una fila por cada ConceptoAdicional de cada línea. Las líneas sin
# conceptos (p.ej. incompletas) igual emiten una fila, con las columnas de
# concepto en blanco — así ninguna línea de la preliquidación queda afuera
# del Excel aunque todavía no tenga nada cargado.

COLUMNAS = [
    "Empresa", "planilla", "fecha_tarea", "nombre_cliente", "nombre_finca",
    "nombre_tarea", "nombre_tractor", "legajo", "nombre_empleado",
    "codigo", "cantidad", "precio", "importe", "grupo_pago", "duplicado",
]


def _num(valor):
    """Convierte Decimal/None a float/None para que openpyxl lo escriba como número."""
    if valor is None:
        return None
    if isinstance(valor, Decimal):
        return float(valor)
    return valor


def generar_export_excel(db: Session, preliq_id: int) -> io.BytesIO:
    """Arma el Excel de exportación de una preliquidación (quincena).

    Devuelve un io.BytesIO ya posicionado al inicio (buffer.seek(0)), listo
    para ser devuelto en una StreamingResponse. Lanza ValueError si la
    preliquidación no existe.
    """
    preliquidacion = db.query(Preliquidacion).filter(
        Preliquidacion.id == preliq_id
    ).first()
    if not preliquidacion:
        raise ValueError(f"Preliquidación {preliq_id} no encontrada")

    lineas = (
        db.query(PreliquidacionLinea)
        .options(joinedload(PreliquidacionLinea.conceptos))
        .filter(PreliquidacionLinea.preliquidacion_id == preliq_id)
        .order_by(
            PreliquidacionLinea.empresa_asignada,
            PreliquidacionLinea.nombre_empleado,
            PreliquidacionLinea.fecha_tarea,
        )
        .all()
    )

    wb = Workbook()
    ws = wb.active
    ws.title = "Preliquidacion"

    ws.append(COLUMNAS)
    for celda in ws[1]:
        celda.font = Font(bold=True)

    for linea in lineas:
        base = [
            linea.empresa_asignada,
            linea.planilla,
            linea.fecha_tarea,
            linea.nombre_cliente,
            linea.nombre_finca,
            linea.nombre_tarea,
            linea.nombre_tractor,
            linea.legajo_asignado,
            linea.nombre_empleado,
        ]
        cola = [
            linea.grupo_pago_aplicado,
            "SI" if linea.es_duplicado else "",
        ]

        if linea.conceptos:
            for concepto in linea.conceptos:
                fila = base + [
                    concepto.codigo_concepto,
                    _num(concepto.cantidad),
                    _num(concepto.precio),
                    _num(concepto.importe),
                ] + cola
                ws.append(fila)
        else:
            fila = base + [None, None, None, None] + cola
            ws.append(fila)

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer
