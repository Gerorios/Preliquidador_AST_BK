"""Adjuntos de un Comprobante (plan de la E2, sección 3.1, "Adjuntos"; pasos
B1 a B3).

Lo que cuidan estos tests:
- que el tipo salga del contenido (la firma de los primeros bytes) y no del
  nombre ni de lo que declara el navegador: un HTML o un SVG que se sirva como
  si fuera un PDF es un XSS sobre la sesión de quien lo abre;
- que la extensión sea una de las cuatro admitidas **y** coincida con el tipo
  detectado, así el archivo que se descarga abre con el programa que se espera;
- que el tipo devuelto traiga el `Content-Type` y la extensión con que se
  guarda en disco, para que nadie los arme por su cuenta;
- que la carpeta de adjuntos esté fuera del código: adentro, un deploy (swap
  de carpeta) se llevaría los PDFs, y quedarían al lado de lo que se sirve. Si
  falta o está mal, los adjuntos responden 503 y el resto de la app anda;
- que nunca quede un archivo sin su fila por un error al subir (tamaño,
  contenido, commit), ni una fila que apunte a la nada al quitar: ahí se borra
  primero la fila, porque un archivo huérfano es menos grave;
- que la ruta en disco la arme siempre el sistema y no salga de la carpeta,
  aunque la fila diga otra cosa.

Contenidos inventados: sólo los primeros bytes de cada formato.
"""
import io
import re
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.modulos.facturacion import config as config_facturacion
from app.modulos.facturacion.config import (
    MAXIMO_POR_COMPROBANTE,
    TAMANO_MAXIMO,
    ConfigFacturacion,
)
from app.modulos.facturacion.models import Adjunto, Comprobante, LineaComprobante
from app.modulos.facturacion.services.adjuntos_service import (
    AdjuntoInvalido,
    AdjuntoMuyGrande,
    AdjuntoNoEncontrado,
    AdjuntosService,
    AdjuntosSinConfigurar,
    ArchivoNoEncontrado,
    ErrorAdjunto,
    LimiteAdjuntos,
    carpeta_adjuntos,
    sanear_nombre,
    validar_tipo,
)
from app.modulos.facturacion.services.comprobantes_service import (
    ComprobantesService,
)

# La raíz del repo (o del worktree) en que corren los tests.
RAIZ_REPO = Path(__file__).resolve().parents[2]

PDF = b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<< >>\nendobj\n"
PNG = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01"


# ─── Las tres firmas ────────────────────────────────────────────────────────

@pytest.mark.parametrize("nombre, contenido, tipo_contenido, extension", [
    ("factura.pdf", PDF, "application/pdf", ".pdf"),
    ("captura.png", PNG, "image/png", ".png"),
    ("foto.jpg", JPEG, "image/jpeg", ".jpg"),
])
def test_acepta_las_tres_firmas(nombre, contenido, tipo_contenido, extension):
    tipo = validar_tipo(nombre, contenido)
    assert tipo.tipo_contenido == tipo_contenido
    assert tipo.extension == extension


# ─── Contenidos que no son ninguno de los tres ──────────────────────────────

@pytest.mark.parametrize("contenido", [
    pytest.param(b"Hola, esto es texto plano.\n", id="texto"),
    pytest.param(b"<!DOCTYPE html><html><script>alert(1)</script></html>",
                 id="html"),
    pytest.param(b'<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg">'
                 b"<script>alert(1)</script></svg>", id="svg"),
    pytest.param(b"PK\x03\x04\x14\x00\x00\x00\x08\x00", id="zip"),
    pytest.param(b"", id="vacio"),
    # La firma tiene que estar al principio, no en cualquier lado.
    pytest.param(b"<html>%PDF-1.7</html>", id="firma-corrida"),
])
def test_rechaza_contenidos_sin_firma_admitida(contenido):
    with pytest.raises(AdjuntoInvalido) as error:
        validar_tipo("factura.pdf", contenido)
    assert "PDF, PNG o JPG" in error.value.mensaje


def test_rechaza_un_pdf_que_por_dentro_es_un_png():
    with pytest.raises(AdjuntoInvalido) as error:
        validar_tipo("factura.pdf", PNG)
    # Dice qué es de verdad, para que la persona entienda por qué se rechaza.
    assert "PNG" in error.value.mensaje


def test_rechaza_un_png_que_por_dentro_es_un_pdf():
    with pytest.raises(AdjuntoInvalido):
        validar_tipo("captura.png", PDF)


# ─── Extensión ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("nombre, contenido, extension", [
    ("FACTURA.PDF", PDF, ".pdf"),
    ("foto.jpeg", JPEG, ".jpg"),
    ("Foto.JPG", JPEG, ".jpg"),
    ("captura.Png", PNG, ".png"),
    # La extensión es la del último punto; el resto del nombre no importa.
    ("factura.v2.pdf", PDF, ".pdf"),
])
def test_la_extension_no_distingue_mayusculas_y_jpeg_vale_como_jpg(
        nombre, contenido, extension):
    assert validar_tipo(nombre, contenido).extension == extension


@pytest.mark.parametrize("nombre", [
    "dibujo.svg",
    "foto.heic",
    "programa.exe",
    "sin_extension",
    "factura.pdf.exe",
    "",
    None,
])
def test_rechaza_extensiones_no_admitidas_aunque_el_contenido_sirva(nombre):
    # Contenido de PDF válido: lo que se rechaza es la extensión.
    with pytest.raises(AdjuntoInvalido) as error:
        validar_tipo(nombre, PDF)
    assert ".pdf" in error.value.mensaje


# ─── Carpeta de adjuntos (B2) ───────────────────────────────────────────────

def _con_carpeta(monkeypatch, valor: str) -> None:
    monkeypatch.setattr(
        config_facturacion.config, "facturacion_adjuntos_dir", valor)


def test_las_constantes_del_plan():
    assert TAMANO_MAXIMO == 10 * 1024 * 1024
    assert MAXIMO_POR_COMPROBANTE == 5


def test_sin_la_variable_la_configuracion_carga_igual(monkeypatch):
    # El arranque no se frena: sin la variable, la carpeta queda vacía y sólo
    # los adjuntos responden 503.
    monkeypatch.delenv("FACTURACION_ADJUNTOS_DIR", raising=False)
    assert ConfigFacturacion(_env_file=None).facturacion_adjuntos_dir == ""


def test_una_carpeta_fuera_del_repo_sirve(monkeypatch, tmp_path):
    _con_carpeta(monkeypatch, str(tmp_path))
    assert carpeta_adjuntos() == tmp_path.resolve()


def test_se_lee_en_cada_llamada(monkeypatch, tmp_path):
    # No queda fijada al importar: un cambio en la configuración se ve en la
    # llamada siguiente (y los tests la pueden cambiar con monkeypatch).
    primera, segunda = tmp_path / "a", tmp_path / "b"
    primera.mkdir()
    segunda.mkdir()
    _con_carpeta(monkeypatch, str(primera))
    assert carpeta_adjuntos() == primera.resolve()
    _con_carpeta(monkeypatch, str(segunda))
    assert carpeta_adjuntos() == segunda.resolve()


def _motivo(monkeypatch, valor: str) -> str:
    _con_carpeta(monkeypatch, valor)
    with pytest.raises(AdjuntosSinConfigurar) as error:
        carpeta_adjuntos()
    assert isinstance(error.value, ErrorAdjunto)
    return error.value.mensaje


@pytest.mark.parametrize("valor", ["", "   "])
def test_vacia_no_esta_configurada(monkeypatch, valor):
    assert "FACTURACION_ADJUNTOS_DIR" in _motivo(monkeypatch, valor)


def test_inexistente_no_esta_configurada(monkeypatch, tmp_path):
    assert "no existe" in _motivo(monkeypatch, str(tmp_path / "no-esta"))


def test_un_archivo_no_sirve_de_carpeta(monkeypatch, tmp_path):
    archivo = tmp_path / "adjuntos"
    archivo.write_bytes(b"")
    assert "no existe" in _motivo(monkeypatch, str(archivo))


@pytest.mark.parametrize("dentro", [
    pytest.param(RAIZ_REPO, id="la-raiz"),
    pytest.param(RAIZ_REPO / "tests", id="una-subcarpeta"),
    # Con "..", la ruta escrita parece de afuera pero cae adentro.
    pytest.param(RAIZ_REPO / "tests" / ".." / "app", id="con-puntos"),
])
def test_dentro_del_repo_no_esta_configurada(monkeypatch, dentro):
    assert "dentro del código" in _motivo(monkeypatch, str(dentro))


def test_relativa_no_esta_configurada(monkeypatch):
    # Relativa dependería de la carpeta desde la que se arrancó el backend.
    assert "absoluta" in _motivo(monkeypatch, "adjuntos")


def test_cada_motivo_tiene_su_mensaje(monkeypatch, tmp_path):
    mensajes = {
        _motivo(monkeypatch, ""),
        _motivo(monkeypatch, str(tmp_path / "no-esta")),
        _motivo(monkeypatch, str(RAIZ_REPO / "tests")),
        _motivo(monkeypatch, "adjuntos"),
    }
    assert len(mensajes) == 4


def test_el_mensaje_no_muestra_la_ruta(monkeypatch, tmp_path):
    # Llega a quien usa la pantalla: la ruta del servidor no tiene que salir.
    ruta = tmp_path / "no-esta"
    assert str(ruta) not in _motivo(monkeypatch, str(ruta))


# ─── Subir, abrir y quitar (B3) ─────────────────────────────────────────────

USUARIO = 5


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    sesion = sessionmaker(bind=engine)()
    yield sesion
    sesion.close()
    engine.dispose()


@pytest.fixture()
def carpeta(monkeypatch, tmp_path):
    """La carpeta de adjuntos, dentro de `tmp_path` pero no en su raíz: así un
    `..` en el nombre en disco cae en `tmp_path`, donde se puede mirar."""
    ruta = tmp_path / "adjuntos"
    ruta.mkdir()
    _con_carpeta(monkeypatch, str(ruta))
    return ruta.resolve()


@pytest.fixture()
def servicio(db):
    return AdjuntosService(db)


def comprobante(db, numero="A 0001", **campos):
    """Un Comprobante cargado a mano, con una Línea, armado directo en la base:
    acá no importa cómo se validó."""
    base = dict(
        tipo="factura", cliente_id=1, cliente_nombre="CLIENTE UNO",
        empresa_emisora="EMPRESA UNO", numero=numero, fecha=date(2026, 10, 5),
        clave_identidad=f"E|EMPRESA UNO|factura|{numero}",
        lineas=[LineaComprobante(
            orden=1, fecha=date(2026, 9, 16), tarea_id=10,
            tarea_nombre="TAREA A", unidad="plantas", cantidad=1,
            precio_unitario=10, importe=10)],
    )
    c = Comprobante(**{**base, **campos})
    db.add(c)
    db.commit()
    return c


def historico(db):
    return comprobante(db, numero="B 0007", empresa_emisora=None,
                       es_historico=True, clave_identidad="H|1|B 0007")


def subir(servicio, c, nombre="factura.pdf", contenido=PDF):
    return servicio.subir(c.id, nombre, io.BytesIO(contenido),
                          usuario_id=USUARIO)


def archivos(carpeta: Path) -> list[str]:
    return sorted(p.name for p in carpeta.iterdir())


def test_subir_guarda_el_archivo_con_nombre_propio_y_la_fila_saneada(
        servicio, db, carpeta):
    c = comprobante(db)

    a = subir(servicio, c, nombre="../../x.pdf")

    assert re.fullmatch(r"[0-9a-f]{32}\.pdf", a.nombre_en_disco)
    assert archivos(carpeta) == [a.nombre_en_disco]
    assert (carpeta / a.nombre_en_disco).read_bytes() == PDF
    db.expire_all()
    fila = db.get(Adjunto, a.id)
    assert fila.comprobante_id == c.id
    assert fila.nombre_original == "x.pdf"
    assert fila.tipo_contenido == "application/pdf"
    assert fila.tamano_bytes == len(PDF)
    assert fila.subido_por == USUARIO
    assert fila.subido_en is not None


def test_la_extension_en_disco_es_la_del_tipo_detectado(servicio, db, carpeta):
    c = comprobante(db)
    assert subir(servicio, c, "FOTO.JPEG", JPEG).nombre_en_disco.endswith(".jpg")
    assert subir(servicio, c, "captura.png", PNG).nombre_en_disco.endswith(".png")


@pytest.mark.parametrize("nombre, saneado", [
    ("../../x.pdf", "x.pdf"),
    ("C:\\fakepath\\factura.pdf", "factura.pdf"),
    ("/etc/factura.pdf", "factura.pdf"),
    ("  factura\x00\x1f de octubre\n.pdf  ", "factura de octubre.pdf"),
    # El que invierte el texto haría que "xfdp.exe" se viera como "exe.pdf".
    ("fact\u202eura.pdf", "factura.pdf"),
    ("Factura ñandú.pdf", "Factura ñandú.pdf"),
])
def test_sanear_nombre(nombre, saneado):
    assert sanear_nombre(nombre, ".pdf") == saneado


def test_sanear_un_nombre_largo_lo_corta_a_255_conservando_la_extension():
    saneado = sanear_nombre("a" * 300 + ".pdf", ".pdf")
    assert len(saneado) == 255
    assert saneado.endswith("a.pdf")


def test_sanear_un_nombre_que_queda_vacio_le_pone_uno():
    assert sanear_nombre("\x00\x01", ".pdf") == "adjunto.pdf"


def test_un_historico_tambien_recibe_adjuntos(servicio, db, carpeta):
    viejo = historico(db)
    a = subir(servicio, viejo)
    assert archivos(carpeta) == [a.nombre_en_disco]


def test_subir_a_un_comprobante_que_no_existe(servicio, carpeta):
    with pytest.raises(AdjuntoNoEncontrado):
        servicio.subir(999, "factura.pdf", io.BytesIO(PDF))
    assert archivos(carpeta) == []


def test_el_sexto_adjunto_da_limite(servicio, db, carpeta):
    c = comprobante(db)
    for i in range(MAXIMO_POR_COMPROBANTE):
        subir(servicio, c, nombre=f"factura{i}.pdf")

    with pytest.raises(LimiteAdjuntos) as error:
        subir(servicio, c)
    assert str(MAXIMO_POR_COMPROBANTE) in error.value.mensaje
    assert len(archivos(carpeta)) == MAXIMO_POR_COMPROBANTE
    assert db.query(Adjunto).count() == MAXIMO_POR_COMPROBANTE


def test_el_limite_es_por_comprobante(servicio, db, carpeta):
    lleno, otro = comprobante(db), comprobante(db, numero="A 0002")
    for _ in range(MAXIMO_POR_COMPROBANTE):
        subir(servicio, lleno)
    subir(servicio, otro)
    assert db.query(Adjunto).filter_by(comprobante_id=otro.id).count() == 1


def test_el_maximo_justo_entra(servicio, db, carpeta):
    c = comprobante(db)
    contenido = PDF + b"0" * (TAMANO_MAXIMO - len(PDF))
    a = subir(servicio, c, contenido=contenido)
    assert a.tamano_bytes == TAMANO_MAXIMO


def test_mas_de_10_mb_da_muy_grande_sin_dejar_archivo(servicio, db, carpeta):
    c = comprobante(db)
    contenido = PDF + b"0" * (TAMANO_MAXIMO + 1 - len(PDF))

    with pytest.raises(AdjuntoMuyGrande) as error:
        subir(servicio, c, contenido=contenido)
    assert "10 MB" in error.value.mensaje
    assert archivos(carpeta) == []
    assert db.query(Adjunto).count() == 0


def test_un_contenido_invalido_no_deja_archivo(servicio, db, carpeta):
    c = comprobante(db)
    with pytest.raises(AdjuntoInvalido):
        subir(servicio, c, nombre="factura.pdf", contenido=PNG)
    assert archivos(carpeta) == []
    assert db.query(Adjunto).count() == 0


def test_un_commit_fallido_no_deja_archivo(servicio, db, carpeta, monkeypatch):
    c = comprobante(db)

    def commit():
        raise RuntimeError("la base se cayó")
    monkeypatch.setattr(db, "commit", commit)

    with pytest.raises(RuntimeError):
        subir(servicio, c)
    monkeypatch.undo()
    # Ni el definitivo ni el temporal.
    assert archivos(carpeta) == []
    assert db.query(Adjunto).count() == 0


def test_un_error_al_escribir_no_deja_el_temporal(
        servicio, db, carpeta, monkeypatch):
    c = comprobante(db)

    def replace(origen, destino):
        raise OSError("disco lleno")
    monkeypatch.setattr(
        "app.modulos.facturacion.services.adjuntos_service.os.replace", replace)

    with pytest.raises(OSError):
        subir(servicio, c)
    monkeypatch.undo()
    assert archivos(carpeta) == []
    assert db.query(Adjunto).count() == 0


def test_abrir_devuelve_el_contenido_y_el_tipo_detectado(servicio, db, carpeta):
    c = comprobante(db)
    a = subir(servicio, c, nombre="captura.png", contenido=PNG)

    archivo = servicio.abrir(c.id, a.id)

    assert archivo.contenido == PNG
    assert archivo.tipo_contenido == "image/png"
    assert archivo.nombre_original == "captura.png"


def test_abrir_un_adjunto_de_otro_comprobante_no_lo_encuentra(
        servicio, db, carpeta):
    dueno, otro = comprobante(db), comprobante(db, numero="A 0002")
    a = subir(servicio, dueno)

    with pytest.raises(AdjuntoNoEncontrado):
        servicio.abrir(otro.id, a.id)
    with pytest.raises(AdjuntoNoEncontrado):
        servicio.abrir(dueno.id, a.id + 1)


def test_abrir_uno_cuyo_archivo_falta_da_archivo_no_encontrado(
        servicio, db, carpeta):
    # Pasa en `testing` si se copian las filas de producción sin los archivos.
    c = comprobante(db)
    a = subir(servicio, c)
    (carpeta / a.nombre_en_disco).unlink()

    with pytest.raises(ArchivoNoEncontrado):
        servicio.abrir(c.id, a.id)


@pytest.mark.parametrize("alterado", ["../x", "../adjuntos/../x", "sub/x"])
def test_un_nombre_en_disco_alterado_no_sale_de_la_carpeta(
        servicio, db, carpeta, alterado):
    c = comprobante(db)
    a = subir(servicio, c)
    (carpeta / a.nombre_en_disco).unlink()
    ajeno = carpeta.parent / "x"
    ajeno.write_bytes(b"de otro lado")
    (carpeta / "sub").mkdir()
    (carpeta / "sub" / "x").write_bytes(b"de una subcarpeta")
    a.nombre_en_disco = alterado
    db.commit()

    with pytest.raises(ArchivoNoEncontrado):
        servicio.abrir(c.id, a.id)

    # Quitar se lleva la fila pero no toca lo que está fuera de la carpeta.
    servicio.quitar(c.id, a.id)
    assert ajeno.read_bytes() == b"de otro lado"
    assert (carpeta / "sub" / "x").exists()
    assert db.query(Adjunto).count() == 0


def test_quitar_borra_la_fila_y_el_archivo(servicio, db, carpeta):
    c = comprobante(db)
    a = subir(servicio, c)
    queda = subir(servicio, c, nombre="otra.pdf")

    servicio.quitar(c.id, a.id)

    assert archivos(carpeta) == [queda.nombre_en_disco]
    db.expire_all()
    assert db.get(Adjunto, a.id) is None
    assert db.get(Adjunto, queda.id) is not None


def test_quitar_tolera_que_el_archivo_falte(servicio, db, carpeta):
    c = comprobante(db)
    a = subir(servicio, c)
    (carpeta / a.nombre_en_disco).unlink()

    servicio.quitar(c.id, a.id)
    assert db.query(Adjunto).count() == 0


def test_quitar_uno_de_otro_comprobante_no_lo_encuentra(servicio, db, carpeta):
    dueno, otro = comprobante(db), comprobante(db, numero="A 0002")
    a = subir(servicio, dueno)

    with pytest.raises(AdjuntoNoEncontrado):
        servicio.quitar(otro.id, a.id)
    assert archivos(carpeta) == [a.nombre_en_disco]
    assert db.query(Adjunto).count() == 1


def test_si_falla_el_commit_al_quitar_el_archivo_queda(
        servicio, db, carpeta, monkeypatch):
    c = comprobante(db)
    a = subir(servicio, c)

    def commit():
        raise RuntimeError("la base se cayó")
    monkeypatch.setattr(db, "commit", commit)

    with pytest.raises(RuntimeError):
        servicio.quitar(c.id, a.id)
    monkeypatch.undo()
    assert archivos(carpeta) == [a.nombre_en_disco]
    db.expire_all()
    assert db.query(Adjunto).count() == 1


def test_un_historico_tambien_quita_sus_adjuntos(servicio, db, carpeta):
    viejo = historico(db)
    a = subir(servicio, viejo)
    servicio.quitar(viejo.id, a.id)
    assert archivos(carpeta) == []


def test_sin_carpeta_subir_abrir_y_quitar_dan_503_sin_tocar_nada(
        servicio, db, carpeta, monkeypatch):
    c = comprobante(db)
    a = subir(servicio, c)
    _con_carpeta(monkeypatch, "")

    with pytest.raises(AdjuntosSinConfigurar):
        subir(servicio, c)
    with pytest.raises(AdjuntosSinConfigurar):
        servicio.abrir(c.id, a.id)
    with pytest.raises(AdjuntosSinConfigurar):
        servicio.quitar(c.id, a.id)
    assert archivos(carpeta) == [a.nombre_en_disco]
    assert db.query(Adjunto).count() == 1


# ─── Borrar el Comprobante se lleva sus adjuntos (pregunta 15) ──────────────

def test_borrar_el_comprobante_borra_sus_adjuntos_y_sus_archivos(
        servicio, db, carpeta):
    c = comprobante(db)
    queda = comprobante(db, numero="A 0002")
    subir(servicio, c)
    subir(servicio, c, nombre="foto.jpg", contenido=JPEG)
    del_otro = subir(servicio, queda)

    ComprobantesService(db, consulta=None).borrar(c.id)

    db.expire_all()
    assert db.get(Comprobante, c.id) is None
    assert [a.id for a in db.query(Adjunto).all()] == [del_otro.id]
    assert archivos(carpeta) == [del_otro.nombre_en_disco]


def test_borrar_el_comprobante_tolera_que_falte_un_archivo(servicio, db, carpeta):
    c = comprobante(db)
    a = subir(servicio, c)
    (carpeta / a.nombre_en_disco).unlink()

    ComprobantesService(db, consulta=None).borrar(c.id)
    db.expire_all()
    assert db.get(Comprobante, c.id) is None


def test_si_falla_el_borrado_del_comprobante_sus_archivos_quedan(
        servicio, db, carpeta, monkeypatch):
    c = comprobante(db)
    a = subir(servicio, c)

    def commit():
        raise RuntimeError("la base se cayó")
    monkeypatch.setattr(db, "commit", commit)

    with pytest.raises(RuntimeError):
        ComprobantesService(db, consulta=None).borrar(c.id)
    monkeypatch.undo()
    db.rollback()
    assert archivos(carpeta) == [a.nombre_en_disco]
    db.expire_all()
    assert db.get(Comprobante, c.id) is not None
    assert db.query(Adjunto).count() == 1


def test_borrar_un_comprobante_sin_adjuntos_no_necesita_la_carpeta(
        db, monkeypatch):
    c = comprobante(db)
    _con_carpeta(monkeypatch, "")

    ComprobantesService(db, consulta=None).borrar(c.id)
    db.expire_all()
    assert db.get(Comprobante, c.id) is None


def test_sin_carpeta_un_comprobante_con_adjuntos_no_se_borra(
        servicio, db, carpeta, monkeypatch):
    c = comprobante(db)
    a = subir(servicio, c)
    _con_carpeta(monkeypatch, "")

    with pytest.raises(AdjuntosSinConfigurar):
        ComprobantesService(db, consulta=None).borrar(c.id)
    db.expire_all()
    assert db.get(Comprobante, c.id) is not None
    assert db.query(Adjunto).count() == 1
    assert archivos(carpeta) == [a.nombre_en_disco]
