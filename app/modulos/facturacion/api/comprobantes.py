"""Endpoints de Comprobantes del módulo Facturación (plan de la E2, sección
3.2).

Tres grupos, todos de la pantalla `comprobantes`:

  - **Comprobantes**: listado, detalle, alta, edición y borrado. Las reglas
    viven en ComprobantesService; acá sólo se traducen sus excepciones al
    código y al `detail` del contrato.
  - **Adjuntos**: subir, abrir y quitar. Las reglas viven en
    AdjuntosService (adjuntos_service).
  - **Lecturas del campo y de sueldos** que usa el alta: clientes activos,
    fincas de un cliente, Empresas emisoras y tareas con su Unidad sugerida.

Si el campo o sueldos no responden, la consulta levanta ExternaNoDisponible y
`app/main.py` la convierte en 503 para todos los módulos: no se repite acá.
"""
import unicodedata
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db_externa, get_db_propia, get_db_sueldos
from app.modulos.facturacion.permisos import editar_comprobantes, ver_comprobantes
from app.modulos.facturacion.schemas import (
    AdjuntoSalida, ComprobanteDetalle, ComprobanteEntrada, ComprobanteFila,
    OpcionMaestro, TareaCampo,
)
from app.modulos.facturacion.services.adjuntos_service import (
    AdjuntoInvalido, AdjuntoMuyGrande, AdjuntoNoEncontrado, AdjuntosService,
    AdjuntosSinConfigurar, ArchivoNoEncontrado, ErrorAdjunto, LimiteAdjuntos,
)
from app.modulos.facturacion.services.comprobantes_service import (
    ComprobanteInvalido, ComprobanteModificado, ComprobanteNoEncontrado,
    ComprobanteRepetido, ComprobantesService, ErrorComprobante,
    FacturaConNotas, HistoricoMismoNumero, HistoricoNoEditable, LineaInvalida,
)
from app.modulos.facturacion.services.consulta_externa import ConsultaExternaService

# Permisos por pantalla (ADR-0020): cada endpoint declara el suyo y el router
# no tiene dependencia propia. El alta y la edición reciben a la persona de la
# dependencia de permiso, para sellar quién escribió. El mapa lo fija
# tests/facturacion/test_mapa_permisos.py.
router = APIRouter(
    prefix="/api/facturacion",
    tags=["Facturación"],
)


def get_consulta_externa(
    db_externa: Session = Depends(get_db_externa),
    db_sueldos: Session = Depends(get_db_sueldos),
) -> ConsultaExternaService:
    # Las sesiones no conectan hasta la primera consulta: el listado y el
    # detalle, que no leen el campo, no abren conexión.
    return ConsultaExternaService(db_externa, db_sueldos)


def get_comprobantes(
    db_propia: Session = Depends(get_db_propia),
    consulta: ConsultaExternaService = Depends(get_consulta_externa),
) -> ComprobantesService:
    return ComprobantesService(db_propia, consulta)


def get_adjuntos(db_propia: Session = Depends(get_db_propia)) -> AdjuntosService:
    return AdjuntosService(db_propia)


# Los 409 del contrato: el `tipo` es lo que la pantalla usa para reaccionar
# (GUIA, regla 15). Los dos repetidos llevan además el id del existente, para
# que la pantalla ofrezca ir a verlo.
_TIPOS_409 = {
    ComprobanteRepetido: "comprobante_repetido",
    HistoricoMismoNumero: "historico_mismo_numero",
    HistoricoNoEditable: "historico_no_editable",
    FacturaConNotas: "factura_con_notas",
    ComprobanteModificado: "comprobante_modificado",
}


def _http(error: ErrorComprobante) -> HTTPException:
    """La excepción del servicio, con el código y el `detail` del contrato
    (sección 3.2, "Errores"). Una que no esté acá es un error de programación
    y sigue de largo como 500, en vez de disfrazarse de otro código."""
    if isinstance(error, ComprobanteNoEncontrado):
        return HTTPException(status_code=404, detail=error.mensaje)
    if isinstance(error, ComprobanteInvalido):
        return HTTPException(status_code=422, detail={
            "tipo": "comprobante_invalido", "mensaje": error.mensaje,
            "campo": error.campo,
        })
    if isinstance(error, LineaInvalida):
        return HTTPException(status_code=422, detail={
            "tipo": "linea_invalida", "mensaje": error.mensaje,
            "fila": error.fila, "campo": error.campo,
        })
    tipo = _TIPOS_409.get(type(error))
    if tipo is None:
        raise error
    detail = {"tipo": tipo, "mensaje": error.mensaje}
    if isinstance(error, (ComprobanteRepetido, HistoricoMismoNumero)):
        detail["comprobante_id"] = error.comprobante_id
    return HTTPException(status_code=409, detail=detail)


# Los errores de adjuntos con `detail` objeto: el código y el `tipo` del
# contrato. El front de adjuntos arma el mensaje por el código, porque el
# `detail` de una descarga como blob no se puede leer (sección 3.1).
_ERRORES_ADJUNTOS = {
    ArchivoNoEncontrado: (404, "archivo_no_encontrado"),
    LimiteAdjuntos: (409, "limite_adjuntos"),
    AdjuntoMuyGrande: (413, "adjunto_muy_grande"),
    AdjuntoInvalido: (422, "adjunto_invalido"),
    AdjuntosSinConfigurar: (503, "adjuntos_sin_configurar"),
}


def _http_adjunto(error: ErrorAdjunto) -> HTTPException:
    """Como _http, para los errores de adjuntos. Un Comprobante o un Adjunto
    que no existe es un 404 de texto, como el de los Comprobantes."""
    if isinstance(error, AdjuntoNoEncontrado):
        return HTTPException(status_code=404, detail=error.mensaje)
    codigo_y_tipo = _ERRORES_ADJUNTOS.get(type(error))
    if codigo_y_tipo is None:
        raise error
    codigo, tipo = codigo_y_tipo
    return HTTPException(status_code=codigo,
                         detail={"tipo": tipo, "mensaje": error.mensaje})


def _content_disposition(nombre: str) -> str:
    """`inline` con el nombre dos veces: en ASCII para los navegadores viejos
    y codificado (RFC 5987) para el resto. En el ASCII, lo que no es ASCII
    pierde el acento o pasa a "_", y las comillas y la barra invertida, que
    cerrarían el valor entre comillas, también."""
    ascii_ = "".join(
        c if c.isascii() and c not in '"\\' else "_"
        for c in unicodedata.normalize("NFKD", nombre)
        if not unicodedata.combining(c))
    return (f'inline; filename="{ascii_}"; '
            f"filename*=UTF-8''{quote(nombre, safe='')}")


# ─── Comprobantes ───────────────────────────────────────────────────────────

@router.get("/comprobantes", response_model=list[ComprobanteFila],
            dependencies=[Depends(ver_comprobantes)])
def listar_comprobantes(servicio: ComprobantesService = Depends(get_comprobantes)):
    """Todos, de la más nueva a la más vieja. Sin paginar: son cientos y la
    pantalla filtra y ordena."""
    return servicio.listar()


@router.get("/comprobantes/{comprobante_id}", response_model=ComprobanteDetalle,
            dependencies=[Depends(ver_comprobantes)])
def detalle_comprobante(
    comprobante_id: int,
    servicio: ComprobantesService = Depends(get_comprobantes),
):
    try:
        return servicio.detalle(comprobante_id)
    except ErrorComprobante as error:
        raise _http(error) from None


@router.post("/comprobantes", response_model=ComprobanteDetalle, status_code=201)
def crear_comprobante(
    entrada: ComprobanteEntrada,
    usuario=Depends(editar_comprobantes),
    servicio: ComprobantesService = Depends(get_comprobantes),
):
    """Devuelve el detalle, el mismo que el GET: la pantalla sigue con el
    Comprobante recién guardado sin pedirlo otra vez."""
    try:
        comprobante = servicio.crear(entrada, usuario_id=getattr(usuario, "id", None))
        return servicio.detalle(comprobante.id)
    except ErrorComprobante as error:
        raise _http(error) from None


@router.put("/comprobantes/{comprobante_id}", response_model=ComprobanteDetalle)
def editar_comprobante(
    comprobante_id: int,
    entrada: ComprobanteEntrada,
    usuario=Depends(editar_comprobantes),
    servicio: ComprobantesService = Depends(get_comprobantes),
):
    """Reemplaza la cabecera y todas las Líneas. La entrada trae el
    `actualizado_en` que dio el detalle: si otra persona guardó en el medio,
    409 `comprobante_modificado` (pregunta 18)."""
    try:
        comprobante = servicio.editar(
            comprobante_id, entrada, usuario_id=getattr(usuario, "id", None))
        return servicio.detalle(comprobante.id)
    except ErrorComprobante as error:
        raise _http(error) from None


@router.delete("/comprobantes/{comprobante_id}", status_code=204,
               dependencies=[Depends(editar_comprobantes)])
def borrar_comprobante(
    comprobante_id: int,
    servicio: ComprobantesService = Depends(get_comprobantes),
):
    try:
        servicio.borrar(comprobante_id)
    except ErrorComprobante as error:
        raise _http(error) from None
    except ErrorAdjunto as error:
        # Sin la carpeta, uno con adjuntos no se borra (503): sus archivos
        # quedarían huérfanos (decisión del usuario, fila 5 del contrato).
        raise _http_adjunto(error) from None


# ─── Adjuntos (filas 6 a 8) ─────────────────────────────────────────────────
# También en los históricos: sus adjuntos sí se suben y se quitan (regla 7).

@router.post("/comprobantes/{comprobante_id}/adjuntos",
             response_model=AdjuntoSalida, status_code=201)
def subir_adjunto(
    comprobante_id: int,
    archivo: UploadFile = File(...),
    usuario=Depends(editar_comprobantes),
    servicio: AdjuntosService = Depends(get_adjuntos),
):
    """Un PDF, PNG o JPG de hasta 10 MB. El tipo sale del contenido; el
    `Content-Type` que declara el navegador no se usa."""
    try:
        adjunto = servicio.subir(comprobante_id, archivo.filename, archivo.file,
                                 usuario_id=getattr(usuario, "id", None))
    except ErrorAdjunto as error:
        raise _http_adjunto(error) from None
    return AdjuntoSalida.model_validate(adjunto, from_attributes=True)


@router.get("/comprobantes/{comprobante_id}/adjuntos/{adjunto_id}",
            dependencies=[Depends(ver_comprobantes)])
def abrir_adjunto(
    comprobante_id: int,
    adjunto_id: int,
    servicio: AdjuntosService = Depends(get_adjuntos),
):
    """El archivo, con el tipo detectado al subir. `nosniff` para que el
    navegador no adivine otro, y sin caché: es un documento de un Cliente."""
    try:
        archivo = servicio.abrir(comprobante_id, adjunto_id)
    except ErrorAdjunto as error:
        raise _http_adjunto(error) from None
    return Response(
        content=archivo.contenido,
        media_type=archivo.tipo_contenido,
        headers={
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
            "Content-Disposition": _content_disposition(archivo.nombre_original),
        },
    )


@router.delete("/comprobantes/{comprobante_id}/adjuntos/{adjunto_id}",
               status_code=204, dependencies=[Depends(editar_comprobantes)])
def quitar_adjunto(
    comprobante_id: int,
    adjunto_id: int,
    servicio: AdjuntosService = Depends(get_adjuntos),
):
    try:
        servicio.quitar(comprobante_id, adjunto_id)
    except ErrorAdjunto as error:
        raise _http_adjunto(error) from None


# ─── Lecturas del campo y de sueldos ────────────────────────────────────────
# Con la caché de 10 minutos de la consulta. Sólo Ver: las necesita también
# quien abre un Comprobante en sólo lectura.

@router.get("/clientes", response_model=list[OpcionMaestro],
            dependencies=[Depends(ver_comprobantes)])
def listar_clientes(consulta: ConsultaExternaService = Depends(get_consulta_externa)):
    """Sólo los activos: un Cliente de baja no recibe comprobantes nuevos. El
    nombre de uno de baja ya guardado lo trae el detalle."""
    return consulta.clientes()


@router.get("/clientes/{cliente_id}/fincas", response_model=list[OpcionMaestro],
            dependencies=[Depends(ver_comprobantes)])
def listar_fincas(
    cliente_id: int,
    consulta: ConsultaExternaService = Depends(get_consulta_externa),
):
    return consulta.fincas_de_cliente(cliente_id)


@router.get("/empresas", response_model=list[str],
            dependencies=[Depends(ver_comprobantes)])
def listar_empresas(consulta: ConsultaExternaService = Depends(get_consulta_externa)):
    """Las Empresas emisoras, de la base de sueldos (pregunta 9)."""
    return consulta.empresas()


@router.get("/tareas", response_model=list[TareaCampo],
            dependencies=[Depends(ver_comprobantes)])
def listar_tareas(consulta: ConsultaExternaService = Depends(get_consulta_externa)):
    """Las tareas activas, con la Unidad sugerida y la marca No facturable
    leídas en vivo del campo: la grilla precarga la unidad y avisa."""
    return consulta.obtener_tareas()
