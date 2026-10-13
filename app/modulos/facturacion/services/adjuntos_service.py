"""Adjuntos de un Comprobante: PDF o imagen, guardados en la carpeta de
adjuntos del VPS (plan de la E2, sección 3.1, "Adjuntos"; ADR-0019).

El tipo sale del contenido, por la firma de los primeros bytes, y nunca del
nombre ni del `Content-Type` que manda el navegador: es el que se guarda y el
que se devuelve al abrirlo. Un HTML o un SVG servido con otro tipo sería un
XSS sobre la sesión de quien lo abre. No hay ninguna librería de detección en
las dependencias, y para tres formatos alcanza con las firmas a mano.

La carpeta se valida en cada uso y no al arrancar: si falta o está mal, sólo
los adjuntos responden 503 y el resto de la app anda.

El nombre en disco lo genera el sistema y la ruta se arma siempre desde la
fila, buscada por (Comprobante, Adjunto): nunca con algo que mande el cliente.
Un archivo nunca queda sin su fila por un error al subir; al quitar se borra
primero la fila, porque un archivo huérfano es menos grave que una fila que
apunta a la nada.
"""
import logging
import os
import unicodedata
from pathlib import Path
from typing import BinaryIO, NamedTuple
from uuid import uuid4

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.modulos.facturacion import config as config_facturacion
from app.modulos.facturacion.config import MAXIMO_POR_COMPROBANTE, TAMANO_MAXIMO
from app.modulos.facturacion.models import Adjunto, Comprobante

_log = logging.getLogger(__name__)

# La raíz del código: app/modulos/facturacion/services/ está cuatro niveles
# más abajo.
RAIZ_CODIGO = Path(__file__).resolve().parents[4]

# El largo de `nombre_original` (facturacion/003).
LARGO_NOMBRE = 255


class TipoAdjunto(NamedTuple):
    """El tipo detectado: el `Content-Type` con que se sirve y la extensión
    con que se guarda en disco (`uuid4().hex` + extensión)."""
    tipo_contenido: str
    extension: str
    etiqueta: str


PDF = TipoAdjunto("application/pdf", ".pdf", "PDF")
PNG = TipoAdjunto("image/png", ".png", "PNG")
JPEG = TipoAdjunto("image/jpeg", ".jpg", "JPG")

# La firma va al principio del archivo; en cualquier otro lugar no cuenta.
FIRMAS = (
    (b"%PDF-", PDF),
    (b"\x89PNG\r\n\x1a\n", PNG),
    (b"\xff\xd8\xff", JPEG),
)

# Las extensiones admitidas y el tipo con que tienen que coincidir. Sin SVG,
# que es XML con scripts, ni HEIC, que el navegador no muestra.
EXTENSIONES = {
    ".pdf": PDF,
    ".png": PNG,
    ".jpg": JPEG,
    ".jpeg": JPEG,
}


# ─── Excepciones ────────────────────────────────────────────────────────────
# Las traduce el router a los códigos y al `detail` del contrato (sección 3.2).
# El mensaje lo lee una persona: dice qué corregir, no qué falló por dentro.

class ErrorAdjunto(Exception):
    mensaje = "No se pudo procesar el adjunto."

    def __init__(self, mensaje: str | None = None):
        if mensaje:
            self.mensaje = mensaje
        super().__init__(self.mensaje)


class AdjuntoNoEncontrado(ErrorAdjunto):
    """404 con texto: no existe el Comprobante, o el Adjunto no es de ese
    Comprobante."""
    mensaje = "No existe ese adjunto."


class ArchivoNoEncontrado(ErrorAdjunto):
    """404 `archivo_no_encontrado`: la fila existe y el archivo no, por
    ejemplo en `testing` con filas copiadas de producción (ADR-0019)."""
    mensaje = ("El archivo de este adjunto no está en el servidor. Quitalo y "
               "volvé a subirlo.")


class LimiteAdjuntos(ErrorAdjunto):
    """409 `limite_adjuntos`."""
    mensaje = (f"Un comprobante admite hasta {MAXIMO_POR_COMPROBANTE} "
               f"adjuntos. Quitá uno para subir otro.")


class AdjuntoMuyGrande(ErrorAdjunto):
    """413 `adjunto_muy_grande`."""
    mensaje = (f"El archivo pesa más de {TAMANO_MAXIMO // (1024 * 1024)} MB, "
               f"el máximo por adjunto.")


class AdjuntoInvalido(ErrorAdjunto):
    """422 `adjunto_invalido`: la extensión no es una de las admitidas, el
    contenido no es un PDF, PNG ni JPG, o no coinciden."""


class AdjuntosSinConfigurar(ErrorAdjunto):
    """503 `adjuntos_sin_configurar`: la carpeta de adjuntos falta o está mal.

    El mensaje nombra la variable y no la ruta: lo lee quien usa la pantalla,
    y la ruta del servidor no tiene por qué salir de ahí."""


def detectar_tipo(contenido: bytes) -> TipoAdjunto | None:
    """El tipo por la firma de los primeros bytes, o None si no es ninguno."""
    for firma, tipo in FIRMAS:
        if contenido.startswith(firma):
            return tipo
    return None


def _extension(nombre: str | None) -> str:
    # La del último punto del último tramo del nombre: el navegador puede
    # mandar una ruta (con barras de los dos lados) y un nombre con puntos.
    base = (nombre or "").strip().replace("\\", "/").rsplit("/", 1)[-1]
    if "." not in base:
        return ""
    return "." + base.rsplit(".", 1)[-1].lower()


def validar_tipo(nombre: str | None, contenido: bytes) -> TipoAdjunto:
    """El tipo del archivo, si la extensión es admitida **y** coincide con lo
    que dice el contenido; si no, `AdjuntoInvalido`.

    Las dos cosas: la firma frena el archivo disfrazado, y la extensión hace
    que lo que se descarga abra con el programa que se espera."""
    esperado = EXTENSIONES.get(_extension(nombre))
    if esperado is None:
        raise AdjuntoInvalido(
            "Sólo se aceptan archivos .pdf, .png, .jpg o .jpeg.")
    detectado = detectar_tipo(contenido)
    if detectado is None:
        raise AdjuntoInvalido(
            "El archivo no es un PDF, PNG o JPG válido.")
    if detectado != esperado:
        raise AdjuntoInvalido(
            f"El archivo dice ser {esperado.etiqueta} pero por dentro es "
            f"{detectado.etiqueta}. Cambiale la extensión o subí el archivo "
            f"correcto.")
    return detectado


def carpeta_adjuntos() -> Path:
    """La carpeta de adjuntos, resuelta, o `AdjuntosSinConfigurar`.

    Se lee la configuración en cada llamada (no al importar) para que los
    tests la puedan cambiar con monkeypatch. Tiene que estar fuera del código:
    adentro, el deploy (swap de carpeta) se llevaría los archivos subidos."""
    valor = config_facturacion.config.facturacion_adjuntos_dir.strip()
    if not valor:
        raise AdjuntosSinConfigurar(
            "Los adjuntos no están habilitados en este servidor: falta "
            "configurar FACTURACION_ADJUNTOS_DIR.")
    ruta = Path(valor)
    if not ruta.is_absolute():
        # Relativa, dependería de la carpeta desde la que arrancó el backend.
        raise AdjuntosSinConfigurar(
            "Los adjuntos no están habilitados en este servidor: "
            "FACTURACION_ADJUNTOS_DIR tiene que ser una ruta absoluta.")
    if not ruta.is_dir():
        raise AdjuntosSinConfigurar(
            "Los adjuntos no están habilitados en este servidor: la carpeta "
            "de FACTURACION_ADJUNTOS_DIR no existe.")
    # resolve() antes de comparar: con ".." o un enlace, una ruta que parece
    # de afuera puede caer adentro.
    ruta = ruta.resolve()
    if ruta == RAIZ_CODIGO or RAIZ_CODIGO in ruta.parents:
        raise AdjuntosSinConfigurar(
            "Los adjuntos no están habilitados en este servidor: la carpeta "
            "de FACTURACION_ADJUNTOS_DIR está dentro del código y tiene que "
            "estar fuera.")
    return ruta


def sanear_nombre(nombre: str | None, extension: str) -> str:
    """El nombre del usuario, sólo para mostrar: sin la ruta, sin caracteres
    de control ni de formato (el que invierte el texto haría que un ".exe" se
    viera como ".pdf") y hasta LARGO_NOMBRE, cortando antes de la extensión.

    `extension` es la del tipo detectado, para el nombre de repuesto si no
    queda nada."""
    base = (nombre or "").replace("\\", "/").rsplit("/", 1)[-1]
    limpio = "".join(
        c for c in base if not unicodedata.category(c).startswith("C")).strip()
    if not limpio:
        return "adjunto" + extension
    if len(limpio) > LARGO_NOMBRE:
        punto = limpio.rfind(".")
        sufijo = limpio[punto:] if punto > 0 else ""
        limpio = limpio[:LARGO_NOMBRE - len(sufijo)] + sufijo
    return limpio


def _ruta_en_carpeta(carpeta: Path, nombre_en_disco: str) -> Path | None:
    """La ruta del archivo, o None si no queda directo en la carpeta.

    El nombre lo generó el sistema, pero se controla igual antes de abrir o
    borrar: una fila alterada (`../x`) no puede llevar a otro archivo del
    servidor."""
    ruta = (carpeta / nombre_en_disco).resolve()
    if ruta.parent != carpeta:
        _log.warning("Adjunto con nombre en disco fuera de la carpeta: %r",
                     nombre_en_disco)
        return None
    return ruta


def _escribir(destino: Path, contenido: bytes) -> None:
    # A un temporal en la misma carpeta y después os.replace, que en el mismo
    # disco es atómico: nunca queda a la vista un archivo a medio escribir.
    temporal = destino.with_name(f".{destino.name}.subiendo")
    try:
        with open(temporal, "xb") as archivo:
            archivo.write(contenido)
            archivo.flush()
            os.fsync(archivo.fileno())
        os.replace(temporal, destino)
    except BaseException:
        temporal.unlink(missing_ok=True)
        raise


def borrar_archivos(carpeta: Path, nombres_en_disco: list[str]) -> None:
    """Borra los archivos de filas que ya se borraron, tolerando que falten.

    Va después del commit, así que no puede fallar: lo que no se pueda borrar
    queda huérfano y en el log."""
    for nombre in nombres_en_disco:
        ruta = _ruta_en_carpeta(carpeta, nombre)
        if ruta is None:
            continue
        try:
            ruta.unlink(missing_ok=True)
        except OSError:
            _log.warning("No se pudo borrar el archivo del adjunto %r",
                         nombre, exc_info=True)


class ArchivoAdjunto(NamedTuple):
    """Lo que necesita la descarga: los bytes, el tipo detectado al subir
    (nunca el del navegador) y el nombre para mostrar."""
    contenido: bytes
    tipo_contenido: str
    nombre_original: str


class AdjuntosService:
    """Subir, abrir y quitar. Los históricos también: sus adjuntos sí se
    suben y se quitan (regla 7). El borrado de los adjuntos junto con su
    Comprobante lo hace `ComprobantesService.borrar`, con `borrar_archivos`."""

    def __init__(self, db: Session):
        self.db = db

    def subir(self, comprobante_id: int, nombre: str | None,
              archivo: BinaryIO, usuario_id: int | None = None) -> Adjunto:
        """Guarda el archivo y su fila, o nada.

        El límite se cuenta con el Comprobante bloqueado y con un conteo
        bloqueante: en MySQL una lectura común ve la foto del principio de la
        transacción, y dos subidas a la vez pasarían las dos con 4 adjuntos;
        la bloqueante ve lo último confirmado (en SQLite no hace nada). El
        orden, primero el Comprobante y después sus adjuntos, es el mismo de
        `quitar` y de `ComprobantesService.borrar`, para que no se traben
        entre ellas. El archivo se escribe antes del commit y, si algo falla
        después, se borra: nunca queda un archivo sin su fila."""
        destino = None
        try:
            comprobante = (self.db.query(Comprobante)
                           .filter(Comprobante.id == comprobante_id)
                           .with_for_update()
                           .first())
            if comprobante is None:
                raise AdjuntoNoEncontrado("No existe ese comprobante.")
            carpeta = carpeta_adjuntos()
            cantidad = (self.db.query(func.count(Adjunto.id))
                        .filter(Adjunto.comprobante_id == comprobante_id)
                        .with_for_update()
                        .scalar())
            if cantidad >= MAXIMO_POR_COMPROBANTE:
                raise LimiteAdjuntos()
            # Un byte de más alcanza para saber que se pasa, sin leer todo.
            contenido = archivo.read(TAMANO_MAXIMO + 1)
            if len(contenido) > TAMANO_MAXIMO:
                raise AdjuntoMuyGrande()
            tipo = validar_tipo(nombre, contenido)

            destino = carpeta / f"{uuid4().hex}{tipo.extension}"
            _escribir(destino, contenido)
            adjunto = Adjunto(
                comprobante_id=comprobante_id,
                nombre_original=sanear_nombre(nombre, tipo.extension),
                nombre_en_disco=destino.name,
                tipo_contenido=tipo.tipo_contenido,
                tamano_bytes=len(contenido),
                subido_por=usuario_id,
            )
            self.db.add(adjunto)
            self.db.commit()
        except BaseException:
            # También suelta el bloqueo del Comprobante.
            self.db.rollback()
            if destino is not None:
                destino.unlink(missing_ok=True)
            raise
        self.db.refresh(adjunto)
        return adjunto

    def abrir(self, comprobante_id: int, adjunto_id: int) -> ArchivoAdjunto:
        adjunto = self._adjunto(comprobante_id, adjunto_id)
        ruta = _ruta_en_carpeta(carpeta_adjuntos(), adjunto.nombre_en_disco)
        if ruta is None or not ruta.is_file():
            raise ArchivoNoEncontrado()
        try:
            contenido = ruta.read_bytes()
        except FileNotFoundError:
            raise ArchivoNoEncontrado() from None
        return ArchivoAdjunto(contenido, adjunto.tipo_contenido,
                              adjunto.nombre_original)

    def quitar(self, comprobante_id: int, adjunto_id: int) -> None:
        """Primero la fila y después el archivo, tolerando que falte. La
        carpeta se controla antes de tocar nada: sin ella, el archivo no se
        podría borrar y quedaría huérfano sin necesidad.

        Bloquea el Comprobante antes de tocar el adjunto: el mismo orden que
        `subir` y `ComprobantesService.borrar`."""
        comprobante = (self.db.query(Comprobante.id)
                       .filter(Comprobante.id == comprobante_id)
                       .with_for_update()
                       .first())
        if comprobante is None:
            raise AdjuntoNoEncontrado("No existe ese comprobante.")
        adjunto = self._adjunto(comprobante_id, adjunto_id)
        carpeta = carpeta_adjuntos()
        nombre = adjunto.nombre_en_disco
        self.db.delete(adjunto)
        try:
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise
        borrar_archivos(carpeta, [nombre])

    def _adjunto(self, comprobante_id: int, adjunto_id: int) -> Adjunto:
        """Por los dos ids: un Adjunto de otro Comprobante no se encuentra."""
        adjunto = (self.db.query(Adjunto)
                   .filter(Adjunto.id == adjunto_id,
                           Adjunto.comprobante_id == comprobante_id)
                   .first())
        if adjunto is None:
            raise AdjuntoNoEncontrado()
        return adjunto
