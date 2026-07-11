from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db_propia
from app.models.models import Preliquidacion
from app.services.export_service import generar_export_excel

router = APIRouter(prefix="/api/preliquidacion", tags=["Export"])


@router.get("/{preliq_id}/export-excel")
def export_excel(preliq_id: int, db: Session = Depends(get_db_propia)):
    preliquidacion = db.query(Preliquidacion).filter(
        Preliquidacion.id == preliq_id
    ).first()
    if not preliquidacion:
        raise HTTPException(status_code=404, detail="Preliquidación no encontrada")

    try:
        buffer = generar_export_excel(db, preliq_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    nombre_archivo = f"preliquidacion-{preliquidacion.quincena}.xlsx"
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{nombre_archivo}"'},
    )
